from __future__ import annotations

import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from transformers import AutoTokenizer


INPUT_PATH = Path(
    "data/processed/"
    "agentdojo_turkish_pilot_v0.1.3/"
    "agentdojo_turkish_bert_training_view_v0.1.3.jsonl"
)

OUTPUT_PATH = Path(
    "data/processed/"
    "agentdojo_turkish_pilot_v0.1.3/"
    "agentdojo_turkish_tokenizer_analysis_v0.1.3.json"
)

MODELS = (
    "dbmdz/bert-base-turkish-cased",
    "google-bert/bert-base-multilingual-cased",
)

THRESHOLDS = (
    128,
    256,
    384,
    512,
)

EXPECTED_ROW_COUNT = 24
EXPECTED_LABEL_COUNTS = {
    0: 12,
    1: 12,
}


def load_jsonl(
    path: Path,
) -> list[dict[str, Any]]:

    if not path.exists():
        raise FileNotFoundError(
            f"Missing input file: {path}"
        )

    rows = []

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:

        for line_number, line in enumerate(
            file,
            start=1,
        ):
            line = line.strip()

            if not line:
                continue

            try:
                rows.append(
                    json.loads(line)
                )

            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid JSONL at line "
                    f"{line_number}."
                ) from error

    return rows


def percentile(
    values: list[int],
    percentile_value: float,
) -> float:

    if not values:
        raise ValueError(
            "Cannot calculate percentile "
            "for an empty list."
        )

    ordered = sorted(
        values
    )

    if len(ordered) == 1:
        return float(
            ordered[0]
        )

    position = (
        len(ordered) - 1
    ) * percentile_value

    lower_index = math.floor(
        position
    )

    upper_index = math.ceil(
        position
    )

    if lower_index == upper_index:
        return float(
            ordered[
                lower_index
            ]
        )

    fraction = (
        position
        -
        lower_index
    )

    return (
        ordered[lower_index]
        +
        (
            ordered[upper_index]
            -
            ordered[lower_index]
        )
        *
        fraction
    )


def summarize(
    lengths: list[int],
) -> dict[str, Any]:

    return {
        "count": len(lengths),

        "minimum": min(lengths),

        "mean": statistics.mean(
            lengths
        ),

        "median": statistics.median(
            lengths
        ),

        "p90": percentile(
            lengths,
            0.90,
        ),

        "p95": percentile(
            lengths,
            0.95,
        ),

        "p99": percentile(
            lengths,
            0.99,
        ),

        "maximum": max(lengths),

        "thresholds": {
            str(threshold): {
                "rows_over_limit": sum(
                    length > threshold
                    for length in lengths
                ),

                "rows_at_or_under_limit": sum(
                    length <= threshold
                    for length in lengths
                ),

                "truncation_rate": (
                    sum(
                        length > threshold
                        for length in lengths
                    )
                    /
                    len(lengths)
                ),
            }
            for threshold in THRESHOLDS
        },
    }


def main() -> None:

    rows = load_jsonl(
        INPUT_PATH
    )

    if len(rows) != EXPECTED_ROW_COUNT:
        raise ValueError(
            "Expected 24 rows, found "
            f"{len(rows)}."
        )

    label_counts = Counter(
        int(
            row[
                "general_risk_label"
            ]
        )
        for row in rows
    )

    if dict(label_counts) != (
        EXPECTED_LABEL_COUNTS
    ):
        raise ValueError(
            "Unexpected label counts: "
            f"{dict(label_counts)}"
        )

    results = {}

    for model_name in MODELS:

        tokenizer = (
            AutoTokenizer
            .from_pretrained(
                model_name
            )
        )

        row_results = []
        all_lengths = []
        lengths_by_split = (
            defaultdict(list)
        )
        lengths_by_suite = (
            defaultdict(list)
        )
        lengths_by_variant = (
            defaultdict(list)
        )

        for row in rows:

            encoded = tokenizer(
                row["text"],
                add_special_tokens=True,
                truncation=False,
                return_attention_mask=False,
                return_token_type_ids=False,
            )

            token_length = len(
                encoded[
                    "input_ids"
                ]
            )

            all_lengths.append(
                token_length
            )

            lengths_by_split[
                str(row["split"])
            ].append(
                token_length
            )

            lengths_by_suite[
                str(row["suite"])
            ].append(
                token_length
            )

            lengths_by_variant[
                str(row["variant"])
            ].append(
                token_length
            )

            row_results.append(
                {
                    "row_id": (
                        row["row_id"]
                    ),

                    "pair_id": (
                        row["pair_id"]
                    ),

                    "split": (
                        row["split"]
                    ),

                    "suite": (
                        row["suite"]
                    ),

                    "variant": (
                        row["variant"]
                    ),

                    "general_risk_label": (
                        row[
                            "general_risk_label"
                        ]
                    ),

                    "token_length": (
                        token_length
                    ),
                }
            )

        longest_rows = sorted(
            row_results,
            key=lambda item: (
                item[
                    "token_length"
                ]
            ),
            reverse=True,
        )[:5]

        results[
            model_name
        ] = {
            "tokenizer_class": (
                tokenizer
                .__class__
                .__name__
            ),

            "vocab_size": (
                tokenizer.vocab_size
            ),

            "model_max_length": (
                tokenizer
                .model_max_length
            ),

            "overall": summarize(
                all_lengths
            ),

            "by_split": {
                split: summarize(
                    lengths
                )
                for split, lengths
                in sorted(
                    lengths_by_split
                    .items()
                )
            },

            "by_suite": {
                suite: summarize(
                    lengths
                )
                for suite, lengths
                in sorted(
                    lengths_by_suite
                    .items()
                )
            },

            "by_variant": {
                variant: summarize(
                    lengths
                )
                for variant, lengths
                in sorted(
                    lengths_by_variant
                    .items()
                )
            },

            "longest_rows": (
                longest_rows
            ),
        }

    berturk_mean = results[
        MODELS[0]
    ][
        "overall"
    ][
        "mean"
    ]

    mbert_mean = results[
        MODELS[1]
    ][
        "overall"
    ][
        "mean"
    ]

    report = {
        "artifact_version": "0.1.3",

        "dataset": (
            "agentdojo_turkish_pilot"
        ),

        "source_row_count": (
            len(rows)
        ),

        "models": results,

        "comparison": {
            "berturk_mean_tokens": (
                berturk_mean
            ),

            "mbert_mean_tokens": (
                mbert_mean
            ),

            "berturk_token_reduction_vs_mbert": (
                (
                    mbert_mean
                    -
                    berturk_mean
                )
                /
                mbert_mean
            ),
        },

        "important_note": (
            "This is a tokenizer and sequence-"
            "length pilot based on 24 Turkish "
            "runtime rows. It is not sufficient "
            "for final model selection."
        ),
    }

    OUTPUT_PATH.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("=" * 80)

    print(
        "AGENTDOJO TURKISH TOKENIZER "
        "ANALYSIS v0.1.3 COMPLETED"
    )

    print("=" * 80)

    print()

    for model_name in MODELS:

        overall = results[
            model_name
        ][
            "overall"
        ]

        print(model_name)

        print(
            "  Minimum:",
            overall["minimum"],
        )

        print(
            "  Mean:",
            round(
                overall["mean"],
                2,
            ),
        )

        print(
            "  Median:",
            overall["median"],
        )

        print(
            "  P90:",
            round(
                overall["p90"],
                2,
            ),
        )

        print(
            "  P95:",
            round(
                overall["p95"],
                2,
            ),
        )

        print(
            "  Maximum:",
            overall["maximum"],
        )

        for threshold in THRESHOLDS:

            threshold_result = (
                overall[
                    "thresholds"
                ][
                    str(threshold)
                ]
            )

            print(
                f"  > {threshold}:",
                threshold_result[
                    "rows_over_limit"
                ],
                "rows | rate:",
                round(
                    threshold_result[
                        "truncation_rate"
                    ],
                    4,
                ),
            )

        print()

    print(
        "BERTurk token reduction "
        "vs mBERT:",
        round(
            report[
                "comparison"
            ][
                "berturk_token_reduction_vs_mbert"
            ]
            *
            100,
            2,
        ),
        "%",
    )

    print()

    print(
        "Report:",
        OUTPUT_PATH,
    )


if __name__ == "__main__":
    main()

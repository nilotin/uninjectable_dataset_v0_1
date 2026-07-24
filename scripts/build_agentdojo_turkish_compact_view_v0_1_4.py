from __future__ import annotations

import hashlib
import json
import math
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

from transformers import AutoTokenizer


INPUT_PATH = Path(
    "data/processed/"
    "agentdojo_turkish_pilot_v0.1.3/"
    "agentdojo_turkish_contextual_action_attempt_pilot_v0.1.3.jsonl"
)

OUTPUT_DIRECTORY = Path(
    "data/processed/"
    "agentdojo_turkish_pilot_v0.1.3"
)

OUTPUT_ALL_PATH = (
    OUTPUT_DIRECTORY
    / "agentdojo_turkish_bert_compact_view_v0.1.4.jsonl"
)

OUTPUT_TRAIN_PATH = (
    OUTPUT_DIRECTORY
    / "agentdojo_turkish_bert_compact_view_v0.1.4_train.jsonl"
)

OUTPUT_VALIDATION_PATH = (
    OUTPUT_DIRECTORY
    / "agentdojo_turkish_bert_compact_view_v0.1.4_validation.jsonl"
)

OUTPUT_REPORT_PATH = (
    OUTPUT_DIRECTORY
    / "agentdojo_turkish_compact_tokenizer_analysis_v0.1.4.json"
)


MODELS = (
    "dbmdz/bert-base-turkish-cased",
    "google-bert/bert-base-multilingual-cased",
)

THRESHOLDS = (
    256,
    384,
    512,
)

SOURCE_FIELDS = (
    "trust_level",
    "source_type",
    "surface_type",
    "retrieval_channel",
)

EXPECTED_ROWS = 24

FORBIDDEN_MARKERS = (
    "general_risk_label",
    "human_review_decision",
    "approve_translation",
    "translation_status",
    "label_source",
)


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


def write_jsonl(
    path: Path,
    rows: list[dict[str, Any]],
) -> None:

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
    ) as file:

        for row in rows:
            file.write(
                json.dumps(
                    row,
                    ensure_ascii=False,
                )
            )
            file.write("\n")


def sha256_text(
    text: str,
) -> str:

    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


def parse_key_value_section(
    section: str,
) -> dict[str, str]:

    values = {}

    for line in section.splitlines():
        if "=" not in line:
            continue

        key, value = line.split(
            "=",
            1,
        )

        values[
            key.strip()
        ] = value.strip()

    return values


def serialize_blocks(
    blocks: list[tuple[str, str]],
) -> str:

    serialized = []

    for name, value in blocks:
        value = value.strip()

        if not value:
            raise ValueError(
                f"Empty compact section: {name}"
            )

        serialized.append(
            f"[{name}]\n{value}"
        )

    return "\n\n".join(
        serialized
    )


def percentile(
    values: list[int],
    value: float,
) -> float:

    ordered = sorted(values)

    position = (
        len(ordered) - 1
    ) * value

    lower = math.floor(position)
    upper = math.ceil(position)

    if lower == upper:
        return float(
            ordered[lower]
        )

    fraction = position - lower

    return (
        ordered[lower]
        +
        (
            ordered[upper]
            -
            ordered[lower]
        )
        *
        fraction
    )


def summary(
    lengths: list[int],
) -> dict[str, Any]:

    return {
        "minimum": min(lengths),
        "mean": statistics.mean(lengths),
        "median": statistics.median(lengths),
        "p90": percentile(lengths, 0.90),
        "p95": percentile(lengths, 0.95),
        "maximum": max(lengths),
    }


def main() -> None:

    source_rows = load_jsonl(
        INPUT_PATH
    )

    if len(source_rows) != EXPECTED_ROWS:
        raise ValueError(
            f"Expected 24 rows, found "
            f"{len(source_rows)}."
        )

    compact_rows = []

    for source_row in source_rows:

        sections = source_row[
            "sections"
        ]

        agent_values = (
            parse_key_value_section(
                sections[
                    "agent_context"
                ]
            )
        )

        source_values = (
            parse_key_value_section(
                sections[
                    "source"
                ]
            )
        )

        attempted_values = (
            parse_key_value_section(
                sections[
                    "attempted_action"
                ]
            )
        )

        attempted_tool = (
            attempted_values.get(
                "tool_name"
            )
        )

        if not attempted_tool:
            raise ValueError(
                f"Missing attempted tool: "
                f"{source_row['row_id']}"
            )

        allowed_tools_raw = (
            agent_values.get(
                "allowed_tools",
                "",
            )
        )

        allowed_tools = {
            item.strip()
            for item in allowed_tools_raw.split(",")
            if item.strip()
        }

        attempted_tool_allowed = (
            attempted_tool
            in
            allowed_tools
        )

        agent_role = (
            agent_values.get(
                "agent_role",
                "unknown",
            )
        )

        source_lines = []

        for field in SOURCE_FIELDS:
            if field in source_values:
                source_lines.append(
                    f"{field}="
                    f"{source_values[field]}"
                )

        if not source_lines:
            raise ValueError(
                f"No source facts found: "
                f"{source_row['row_id']}"
            )

        agent_facts = (
            f"agent_role={agent_role}\n"
            f"attempted_tool_allowed="
            f"{str(attempted_tool_allowed).lower()}"
        )

        priority_blocks = [
            (
                "USER_GOAL",
                sections[
                    "user_goal"
                ],
            ),
            (
                "USER_AUTHORIZATION",
                sections[
                    "user_authorization"
                ],
            ),
            (
                "ATTEMPTED_ACTION",
                sections[
                    "attempted_action"
                ],
            ),
        ]

        core_blocks = [
            *priority_blocks,
            (
                "RETRIEVED_CONTENT",
                sections[
                    "retrieved_content"
                ],
            ),
        ]

        all_blocks = [
            *core_blocks,
            (
                "SOURCE",
                "\n".join(
                    source_lines
                ),
            ),
            (
                "AGENT_FACTS",
                agent_facts,
            ),
        ]

        priority_text = serialize_blocks(
            priority_blocks
        )

        core_text = serialize_blocks(
            core_blocks
        )

        compact_text = serialize_blocks(
            all_blocks
        )

        for marker in FORBIDDEN_MARKERS:
            if marker.lower() in compact_text.lower():
                raise ValueError(
                    f"Leakage marker detected in "
                    f"{source_row['row_id']}: "
                    f"{marker}"
                )

        label = int(
            source_row[
                "label"
            ][
                "general_risk_label"
            ]
        )

        compact_rows.append(
            {
                "schema_version": (
                    "agentdojo_turkish_bert_"
                    "compact_view_v0.1.4"
                ),
                "row_id": (
                    source_row[
                        "row_id"
                    ]
                ),
                "pair_id": (
                    source_row[
                        "pair_id"
                    ]
                ),
                "source_pair_id": (
                    source_row[
                        "source_pair_id"
                    ]
                ),
                "session_group_id": (
                    source_row[
                        "session_group_id"
                    ]
                ),
                "crosslingual_group_id": (
                    source_row[
                        "crosslingual_group_id"
                    ]
                ),
                "suite": (
                    source_row[
                        "suite"
                    ]
                ),
                "split": (
                    source_row[
                        "split"
                    ]
                ),
                "language": "tr",
                "variant": (
                    source_row[
                        "variant"
                    ]
                ),
                "text": compact_text,
                "text_sha256": (
                    sha256_text(
                        compact_text
                    )
                ),
                "priority_prefix_text": (
                    priority_text
                ),
                "core_prefix_text": (
                    core_text
                ),
                "general_risk_label": (
                    label
                ),
                "label_source": (
                    "agentdojo_v0.1.5_"
                    "plus_turkish_human_review_"
                    "v0.1.2"
                ),
                "compact_serialization": {
                    "removed_sections": [
                        "CONTEXT_BINDINGS",
                        "POLICY_CONTEXT",
                        "full_allowed_tools",
                    ],
                    "derived_runtime_facts": {
                        "attempted_tool_allowed": (
                            attempted_tool_allowed
                        ),
                    },
                    "priority_order": [
                        "USER_GOAL",
                        "USER_AUTHORIZATION",
                        "ATTEMPTED_ACTION",
                        "RETRIEVED_CONTENT",
                        "SOURCE",
                        "AGENT_FACTS",
                    ],
                },
            }
        )

    if len({
        row["text_sha256"]
        for row in compact_rows
    }) != EXPECTED_ROWS:
        raise ValueError(
            "Duplicate compact model inputs."
        )

    label_counts = Counter(
        row["general_risk_label"]
        for row in compact_rows
    )

    if dict(label_counts) != {
        0: 12,
        1: 12,
    }:
        raise ValueError(
            f"Unexpected label counts: "
            f"{dict(label_counts)}"
        )

    train_rows = [
        row
        for row in compact_rows
        if row["split"] == "train"
    ]

    validation_rows = [
        row
        for row in compact_rows
        if row["split"] == "validation"
    ]

    if len(train_rows) != 16:
        raise ValueError(
            f"Expected 16 train rows, "
            f"found {len(train_rows)}."
        )

    if len(validation_rows) != 8:
        raise ValueError(
            f"Expected 8 validation rows, "
            f"found {len(validation_rows)}."
        )

    if any(
        row["split"] == "test"
        for row in compact_rows
    ):
        raise ValueError(
            "Test row entered compact pilot."
        )

    write_jsonl(
        OUTPUT_ALL_PATH,
        compact_rows,
    )

    write_jsonl(
        OUTPUT_TRAIN_PATH,
        train_rows,
    )

    write_jsonl(
        OUTPUT_VALIDATION_PATH,
        validation_rows,
    )

    tokenizer_results = {}

    for model_name in MODELS:

        tokenizer = (
            AutoTokenizer.from_pretrained(
                model_name
            )
        )

        original_max_length = (
            tokenizer.model_max_length
        )

        tokenizer.model_max_length = (
            1_000_000
        )

        total_lengths = []
        priority_lengths = []
        core_lengths = []

        for row in compact_rows:

            total_lengths.append(
                len(
                    tokenizer(
                        row["text"],
                        add_special_tokens=True,
                        truncation=False,
                    )["input_ids"]
                )
            )

            priority_lengths.append(
                len(
                    tokenizer(
                        row[
                            "priority_prefix_text"
                        ],
                        add_special_tokens=True,
                        truncation=False,
                    )["input_ids"]
                )
            )

            core_lengths.append(
                len(
                    tokenizer(
                        row[
                            "core_prefix_text"
                        ],
                        add_special_tokens=True,
                        truncation=False,
                    )["input_ids"]
                )
            )

        tokenizer.model_max_length = (
            original_max_length
        )

        threshold_results = {}

        for threshold in THRESHOLDS:

            threshold_results[
                str(threshold)
            ] = {
                "full_text_fits": sum(
                    length <= threshold
                    for length in total_lengths
                ),
                "full_text_truncated": sum(
                    length > threshold
                    for length in total_lengths
                ),
                "priority_prefix_preserved": sum(
                    length <= threshold
                    for length in priority_lengths
                ),
                "core_prefix_preserved": sum(
                    length <= threshold
                    for length in core_lengths
                ),
            }

        tokenizer_results[
            model_name
        ] = {
            "full_text": summary(
                total_lengths
            ),
            "priority_prefix": summary(
                priority_lengths
            ),
            "core_prefix": summary(
                core_lengths
            ),
            "thresholds": (
                threshold_results
            ),
        }

    report = {
        "artifact_version": "0.1.4",
        "row_count": len(
            compact_rows
        ),
        "train_row_count": len(
            train_rows
        ),
        "validation_row_count": len(
            validation_rows
        ),
        "test_row_count": 0,
        "label_counts": {
            str(key): value
            for key, value in sorted(
                label_counts.items()
            )
        },
        "duplicate_model_inputs": 0,
        "label_or_review_leakage": 0,
        "tokenizer_analysis": (
            tokenizer_results
        ),
        "outputs": {
            "all": str(
                OUTPUT_ALL_PATH
            ),
            "train": str(
                OUTPUT_TRAIN_PATH
            ),
            "validation": str(
                OUTPUT_VALIDATION_PATH
            ),
        },
        "important_note": (
            "The canonical Turkish structured "
            "pool was not modified."
        ),
    }

    OUTPUT_REPORT_PATH.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("=" * 80)
    print(
        "AGENTDOJO TURKISH COMPACT "
        "VIEW v0.1.4 CREATED"
    )
    print("=" * 80)
    print()

    print(
        "Rows:",
        len(compact_rows),
    )
    print(
        "Train / validation:",
        len(train_rows),
        "/",
        len(validation_rows),
    )
    print(
        "Labels:",
        dict(label_counts),
    )
    print(
        "Duplicate inputs:",
        0,
    )
    print(
        "Leakage:",
        0,
    )
    print()

    for model_name in MODELS:

        result = tokenizer_results[
            model_name
        ]

        print(model_name)
        print(
            "  Full mean:",
            round(
                result[
                    "full_text"
                ][
                    "mean"
                ],
                2,
            ),
        )
        print(
            "  Full max:",
            result[
                "full_text"
            ][
                "maximum"
            ],
        )
        print(
            "  Action-prefix max:",
            result[
                "priority_prefix"
            ][
                "maximum"
            ],
        )
        print(
            "  Core-prefix max:",
            result[
                "core_prefix"
            ][
                "maximum"
            ],
        )

        for threshold in THRESHOLDS:

            threshold_result = (
                result[
                    "thresholds"
                ][
                    str(threshold)
                ]
            )

            print(
                f"  max_length={threshold}:",
                "full fits",
                threshold_result[
                    "full_text_fits"
                ],
                "/24 | action preserved",
                threshold_result[
                    "priority_prefix_preserved"
                ],
                "/24 | retrieved preserved",
                threshold_result[
                    "core_prefix_preserved"
                ],
                "/24",
            )

        print()

    print(
        "Compact view:",
        OUTPUT_ALL_PATH,
    )
    print(
        "Train view:",
        OUTPUT_TRAIN_PATH,
    )
    print(
        "Validation view:",
        OUTPUT_VALIDATION_PATH,
    )
    print(
        "Report:",
        OUTPUT_REPORT_PATH,
    )
    print()
    print(
        "Canonical structured pool modified: no"
    )
    print(
        "Test split opened: no"
    )


if __name__ == "__main__":
    main()

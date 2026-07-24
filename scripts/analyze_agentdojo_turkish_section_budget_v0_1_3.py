from __future__ import annotations

import json
import re
import statistics
from collections import defaultdict
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
    "agentdojo_turkish_section_budget_analysis_v0.1.3.json"
)

MODELS = (
    "dbmdz/bert-base-turkish-cased",
    "google-bert/bert-base-multilingual-cased",
)

SECTION_ORDER = (
    "USER_GOAL",
    "AGENT_CONTEXT",
    "SOURCE",
    "CONTEXT_BINDINGS",
    "RETRIEVED_CONTENT",
    "USER_AUTHORIZATION",
    "POLICY_CONTEXT",
    "ATTEMPTED_ACTION",
)

MAX_LENGTH = 512
EXPECTED_ROW_COUNT = 24


def load_jsonl(
    path: Path,
) -> list[dict[str, Any]]:
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


def extract_sections(
    text: str,
) -> dict[str, str]:
    pattern = re.compile(
        r"^\[([A-Z_]+)\]\n"
        r"(.*?)"
        r"(?=^\[[A-Z_]+\]\n|\Z)",
        flags=re.MULTILINE | re.DOTALL,
    )

    sections = {
        match.group(1): match.group(2).strip()
        for match in pattern.finditer(text)
    }

    missing = [
        section
        for section in SECTION_ORDER
        if section not in sections
    ]

    if missing:
        raise ValueError(
            f"Missing sections: {missing}"
        )

    return sections


def mean(values: list[int]) -> float:
    return round(
        statistics.mean(values),
        2,
    )


def main() -> None:
    rows = load_jsonl(
        INPUT_PATH
    )

    if len(rows) != EXPECTED_ROW_COUNT:
        raise ValueError(
            f"Expected 24 rows, found "
            f"{len(rows)}."
        )

    report_models = {}

    for model_name in MODELS:
        tokenizer = AutoTokenizer.from_pretrained(
            model_name
        )

        special_token_count = (
            tokenizer.num_special_tokens_to_add(
                pair=False
            )
        )

        content_budget = (
            MAX_LENGTH
            -
            special_token_count
        )

        section_lengths: dict[
            str,
            list[int],
        ] = defaultdict(list)

        prefix_before_action_lengths = []
        action_lengths = []
        action_visible_token_counts = []

        action_started_count = 0
        action_fully_preserved_count = 0
        action_fully_removed_count = 0
        action_partially_preserved_count = 0

        row_results = []

        action_marker = (
            "\n\n[ATTEMPTED_ACTION]\n"
        )

        for row in rows:
            text = str(
                row["text"]
            )

            sections = extract_sections(
                text
            )

            for section_name in SECTION_ORDER:
                section_block = (
                    f"[{section_name}]\n"
                    f"{sections[section_name]}"
                )

                section_token_count = len(
                    tokenizer(
                        section_block,
                        add_special_tokens=False,
                    )["input_ids"]
                )

                section_lengths[
                    section_name
                ].append(
                    section_token_count
                )

            if action_marker not in text:
                raise ValueError(
                    f"ATTEMPTED_ACTION marker "
                    f"missing in {row['row_id']}."
                )

            prefix_text, action_content = (
                text.split(
                    action_marker,
                    1,
                )
            )

            prefix_token_count = len(
                tokenizer(
                    prefix_text,
                    add_special_tokens=False,
                )["input_ids"]
            )

            action_block = (
                "[ATTEMPTED_ACTION]\n"
                +
                action_content
            )

            action_token_count = len(
                tokenizer(
                    action_block,
                    add_special_tokens=False,
                )["input_ids"]
            )

            remaining_budget = max(
                0,
                content_budget
                -
                prefix_token_count,
            )

            visible_action_tokens = min(
                action_token_count,
                remaining_budget,
            )

            prefix_before_action_lengths.append(
                prefix_token_count
            )

            action_lengths.append(
                action_token_count
            )

            action_visible_token_counts.append(
                visible_action_tokens
            )

            if visible_action_tokens == 0:
                action_fully_removed_count += 1

            elif (
                visible_action_tokens
                ==
                action_token_count
            ):
                action_started_count += 1
                action_fully_preserved_count += 1

            else:
                action_started_count += 1
                action_partially_preserved_count += 1

            row_results.append(
                {
                    "row_id": row["row_id"],
                    "pair_id": row["pair_id"],
                    "suite": row["suite"],
                    "split": row["split"],
                    "variant": row["variant"],
                    "prefix_tokens_before_action": (
                        prefix_token_count
                    ),
                    "attempted_action_tokens": (
                        action_token_count
                    ),
                    "visible_action_tokens_at_512": (
                        visible_action_tokens
                    ),
                    "action_visibility_ratio": (
                        visible_action_tokens
                        /
                        action_token_count
                    ),
                    "action_fully_preserved": (
                        visible_action_tokens
                        ==
                        action_token_count
                    ),
                }
            )

        report_models[
            model_name
        ] = {
            "max_length": MAX_LENGTH,
            "special_token_count": (
                special_token_count
            ),
            "content_token_budget": (
                content_budget
            ),
            "section_token_lengths": {
                section_name: {
                    "minimum": min(lengths),
                    "mean": mean(lengths),
                    "median": statistics.median(
                        lengths
                    ),
                    "maximum": max(lengths),
                }
                for section_name, lengths
                in section_lengths.items()
            },
            "prefix_before_attempted_action": {
                "minimum": min(
                    prefix_before_action_lengths
                ),
                "mean": mean(
                    prefix_before_action_lengths
                ),
                "median": statistics.median(
                    prefix_before_action_lengths
                ),
                "maximum": max(
                    prefix_before_action_lengths
                ),
            },
            "attempted_action": {
                "minimum_tokens": min(
                    action_lengths
                ),
                "mean_tokens": mean(
                    action_lengths
                ),
                "maximum_tokens": max(
                    action_lengths
                ),
                "mean_visible_tokens_at_512": (
                    mean(
                        action_visible_token_counts
                    )
                ),
                "started_count": (
                    action_started_count
                ),
                "fully_preserved_count": (
                    action_fully_preserved_count
                ),
                "partially_preserved_count": (
                    action_partially_preserved_count
                ),
                "fully_removed_count": (
                    action_fully_removed_count
                ),
            },
            "rows": row_results,
        }

    report = {
        "artifact_version": "0.1.3",
        "dataset": (
            "agentdojo_turkish_pilot"
        ),
        "row_count": len(rows),
        "models": report_models,
        "important_note": (
            "Analysis assumes standard right-side "
            "truncation with max_length=512."
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
        "AGENTDOJO TURKISH SECTION "
        "BUDGET ANALYSIS COMPLETED"
    )
    print("=" * 80)
    print()

    for model_name in MODELS:
        result = report_models[
            model_name
        ]

        print(model_name)
        print(
            "  Content budget:",
            result[
                "content_token_budget"
            ],
        )

        print(
            "  Mean tokens before action:",
            result[
                "prefix_before_attempted_action"
            ][
                "mean"
            ],
        )

        print(
            "  Mean attempted-action tokens:",
            result[
                "attempted_action"
            ][
                "mean_tokens"
            ],
        )

        print(
            "  Action fully preserved:",
            result[
                "attempted_action"
            ][
                "fully_preserved_count"
            ],
            "/",
            EXPECTED_ROW_COUNT,
        )

        print(
            "  Action partially preserved:",
            result[
                "attempted_action"
            ][
                "partially_preserved_count"
            ],
            "/",
            EXPECTED_ROW_COUNT,
        )

        print(
            "  Action fully removed:",
            result[
                "attempted_action"
            ][
                "fully_removed_count"
            ],
            "/",
            EXPECTED_ROW_COUNT,
        )

        print()
        print("  Mean section token lengths:")

        for section_name in SECTION_ORDER:
            section_result = result[
                "section_token_lengths"
            ][
                section_name
            ]

            print(
                f"    {section_name}:",
                section_result["mean"],
            )

        print()

    print(
        "Report:",
        OUTPUT_PATH,
    )


if __name__ == "__main__":
    main()

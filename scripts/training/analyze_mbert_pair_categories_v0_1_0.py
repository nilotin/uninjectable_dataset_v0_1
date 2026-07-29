from __future__ import annotations

import ast
import csv
import json
import re
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VALIDATION_PATH = Path(
    "data/processed/"
    "agentdojo_turkish_training_package_v0.1.0/"
    "agentdojo_turkish_training_v0.1.0_validation.jsonl"
)

PAIR_MARGIN_PATH = Path(
    "artifacts/training_reports/"
    "mbert_agentdojo_turkish_multiseed_v0.1.0/"
    "mbert_agentdojo_turkish_multiseed_pair_margins_v0.1.0.csv"
)

OUTPUT_CSV = Path(
    "artifacts/training_reports/"
    "mbert_agentdojo_turkish_multiseed_v0.1.0/"
    "mbert_agentdojo_turkish_pair_category_analysis_v0.1.0.csv"
)

OUTPUT_JSON = Path(
    "artifacts/training_reports/"
    "mbert_agentdojo_turkish_multiseed_v0.1.0/"
    "mbert_agentdojo_turkish_pair_category_analysis_v0.1.0.json"
)

EXPECTED_PAIRS = 15


def canonical_pair_id(value: str) -> str:
    return value[:-3] if value.endswith("_tr") else value


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]


def extract_field(
    text: str,
    field_name: str,
    section: str,
) -> str:
    section_pattern = (
        rf"\[{re.escape(section)}\]\n"
        rf"(.*?)(?=\n\[[A-Z_]+\]|\Z)"
    )

    section_match = re.search(
        section_pattern,
        text,
        flags=re.DOTALL,
    )

    if not section_match:
        raise ValueError(
            f"Section not found: {section}"
        )

    field_match = re.search(
        rf"^{re.escape(field_name)}=(.+)$",
        section_match.group(1),
        flags=re.MULTILINE,
    )

    if not field_match:
        raise ValueError(
            f"Field not found: "
            f"{section}.{field_name}"
        )

    return field_match.group(1).strip()


def normalize_expression(value: str) -> str:
    return re.sub(
        r"\s+",
        "",
        value,
    )


def strip_placeholder_underscores(
    value: str,
) -> str:
    return re.sub(
        r"\bself\._([A-Z][A-Z0-9_]*)\b",
        r"self.\1",
        value,
    )


def classify_pair(
    safe_text: str,
    risky_text: str,
) -> dict[str, Any]:
    authorized_tool = extract_field(
        safe_text,
        "authorized_tool",
        "USER_AUTHORIZATION",
    )

    authorized_args = extract_field(
        safe_text,
        "authorized_args",
        "USER_AUTHORIZATION",
    )

    safe_tool = extract_field(
        safe_text,
        "tool_name",
        "ATTEMPTED_ACTION",
    )

    safe_args = extract_field(
        safe_text,
        "args",
        "ATTEMPTED_ACTION",
    )

    risky_tool = extract_field(
        risky_text,
        "tool_name",
        "ATTEMPTED_ACTION",
    )

    risky_args = extract_field(
        risky_text,
        "args",
        "ATTEMPTED_ACTION",
    )

    if safe_tool != risky_tool:
        category = "tool_mismatch"

    elif normalize_expression(
        safe_args
    ) != normalize_expression(risky_args):
        safe_normalized = strip_placeholder_underscores(
            normalize_expression(safe_args)
        )

        risky_normalized = strip_placeholder_underscores(
            normalize_expression(risky_args)
        )

        if safe_normalized == risky_normalized:
            category = (
                "placeholder_only_or_"
                "subtle_argument_mismatch"
            )
        else:
            category = "argument_mismatch"

    else:
        category = "other"

    return {
        "category": category,
        "authorized_tool": authorized_tool,
        "authorized_args": authorized_args,
        "safe_tool": safe_tool,
        "safe_args": safe_args,
        "risky_tool": risky_tool,
        "risky_args": risky_args,
    }


def summarize(
    values: list[float],
) -> dict[str, float]:
    return {
        "minimum": float(min(values)),
        "maximum": float(max(values)),
        "mean": float(
            statistics.mean(values)
        ),
        "median": float(
            statistics.median(values)
        ),
    }


def main() -> None:
    validation_rows = load_jsonl(
        VALIDATION_PATH
    )

    grouped: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)

    for row in validation_rows:
        grouped[
            canonical_pair_id(
                str(row["pair_id"])
            )
        ].append(row)

    if len(grouped) != EXPECTED_PAIRS:
        raise ValueError(
            f"Expected {EXPECTED_PAIRS} pairs, "
            f"found {len(grouped)}."
        )

    with PAIR_MARGIN_PATH.open(
        encoding="utf-8",
        newline="",
    ) as handle:
        margin_rows = list(
            csv.DictReader(handle)
        )

    margin_by_pair = {
        row["pair_id"]: row
        for row in margin_rows
    }

    output_rows: list[
        dict[str, Any]
    ] = []

    for pair_id, members in sorted(
        grouped.items()
    ):
        safe = next(
            row
            for row in members
            if int(row["label"]) == 0
        )

        risky = next(
            row
            for row in members
            if int(row["label"]) == 1
        )

        classification = classify_pair(
            str(safe["text"]),
            str(risky["text"]),
        )

        margin = margin_by_pair[pair_id]

        output_rows.append(
            {
                "pair_id": pair_id,
                "suite": safe["suite"],
                **classification,
                "ensemble_safe_score": float(
                    margin[
                        "ensemble_safe_score"
                    ]
                ),
                "ensemble_risky_score": float(
                    margin[
                        "ensemble_risky_score"
                    ]
                ),
                "ensemble_margin": float(
                    margin["ensemble_margin"]
                ),
                "ensemble_ranking_correct": (
                    margin[
                        "ensemble_ranking_correct"
                    ]
                    == "True"
                ),
                "correct_seed_count": int(
                    margin[
                        "correct_seed_count"
                    ]
                ),
            }
        )

    category_groups: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)

    for row in output_rows:
        category_groups[
            str(row["category"])
        ].append(row)

    category_summary: dict[
        str,
        Any,
    ] = {}

    for category, rows in sorted(
        category_groups.items()
    ):
        margins = [
            float(row["ensemble_margin"])
            for row in rows
        ]

        category_summary[category] = {
            "pairs": len(rows),
            "correct_rankings": sum(
                bool(
                    row[
                        "ensemble_ranking_correct"
                    ]
                )
                for row in rows
            ),
            "pair_ranking_accuracy": (
                sum(
                    bool(
                        row[
                            "ensemble_ranking_correct"
                        ]
                    )
                    for row in rows
                )
                / len(rows)
            ),
            "margin_summary": summarize(
                margins
            ),
            "pair_ids": [
                row["pair_id"]
                for row in rows
            ],
        }

    output_rows.sort(
        key=lambda row: (
            str(row["category"]),
            float(row["ensemble_margin"]),
        )
    )

    with OUTPUT_CSV.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(
                output_rows[0].keys()
            ),
        )
        writer.writeheader()
        writer.writerows(output_rows)

    report = {
        "analysis": (
            "mbert_agentdojo_turkish_"
            "pair_categories_v0.1.0"
        ),
        "completed_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "pairs": len(output_rows),
        "category_definition": {
            "tool_mismatch": (
                "Safe and risky variants attempt "
                "different tools."
            ),
            "argument_mismatch": (
                "Tool remains the same but attempted "
                "arguments differ materially."
            ),
            (
                "placeholder_only_or_"
                "subtle_argument_mismatch"
            ): (
                "Difference disappears after normalizing "
                "leading underscores in placeholders."
            ),
            "other": (
                "No tool or attempted-argument difference "
                "was detected."
            ),
        },
        "category_summary": category_summary,
        "rows": output_rows,
    }

    OUTPUT_JSON.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print("=" * 80)
    print(
        "MBERT TURKISH PAIR CATEGORY "
        "ANALYSIS v0.1.0"
    )
    print("=" * 80)
    print()

    for category, summary in (
        category_summary.items()
    ):
        print(category)
        print(
            "  pairs:",
            summary["pairs"],
        )
        print(
            "  ranking accuracy:",
            round(
                summary[
                    "pair_ranking_accuracy"
                ],
                6,
            ),
        )
        print(
            "  mean margin:",
            round(
                summary[
                    "margin_summary"
                ]["mean"],
                6,
            ),
        )
        print(
            "  median margin:",
            round(
                summary[
                    "margin_summary"
                ]["median"],
                6,
            ),
        )
        print(
            "  pair IDs:",
            ", ".join(
                summary["pair_ids"]
            ),
        )
        print()

    print("CSV:", OUTPUT_CSV)
    print("JSON:", OUTPUT_JSON)
    print()
    print(
        "Pair category analysis: PASSED"
    )


if __name__ == "__main__":
    main()

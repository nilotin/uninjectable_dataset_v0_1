from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PACKAGE_DIR = Path(
    "data/processed/"
    "agentdojo_turkish_training_package_v0.1.0"
)

SPLIT_PATHS = {
    "train": (
        PACKAGE_DIR
        / "agentdojo_turkish_training_v0.1.0_train.jsonl"
    ),
    "validation": (
        PACKAGE_DIR
        / "agentdojo_turkish_training_v0.1.0_validation.jsonl"
    ),
}

OUTPUT_DIR = Path(
    "artifacts/training_reports/"
    "mbert_agentdojo_turkish_multiseed_v0.1.0"
)

OUTPUT_CSV = (
    OUTPUT_DIR
    / "agentdojo_turkish_pair_category_audit_v0.1.0.csv"
)

OUTPUT_JSON = (
    OUTPUT_DIR
    / "agentdojo_turkish_pair_category_audit_v0.1.0.json"
)

EXPECTED_ROWS = {
    "train": 134,
    "validation": 30,
}

EXPECTED_PAIRS = {
    "train": 67,
    "validation": 15,
}


def load_jsonl(
    path: Path,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue

        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"{path}:{line_number}: invalid JSON."
            ) from exc

    return rows


def canonical_pair_id(value: str) -> str:
    return value[:-3] if value.endswith("_tr") else value


def extract_field(
    text: str,
    field_name: str,
    section_name: str,
) -> str:
    section_pattern = (
        rf"\[{re.escape(section_name)}\]\n"
        rf"(.*?)(?=\n\[[A-Z_]+\]|\Z)"
    )

    section_match = re.search(
        section_pattern,
        text,
        flags=re.DOTALL,
    )

    if not section_match:
        raise ValueError(
            f"Section not found: {section_name}"
        )

    field_match = re.search(
        rf"^{re.escape(field_name)}=(.+)$",
        section_match.group(1),
        flags=re.MULTILINE,
    )

    if not field_match:
        raise ValueError(
            f"Field not found: "
            f"{section_name}.{field_name}"
        )

    return field_match.group(1).strip()


def normalize_expression(value: str) -> str:
    return re.sub(r"\s+", "", value)


def normalize_placeholder_underscores(
    value: str,
) -> str:
    normalized = re.sub(
        r"\bself\._([A-Za-z][A-Za-z0-9_]*)\b",
        r"self.\1",
        value,
    )

    normalized = re.sub(
        r"\b_([A-Z][A-Z0-9_]*)\b",
        r"\1",
        normalized,
    )

    return normalized


def classify_pair(
    safe_text: str,
    risky_text: str,
) -> dict[str, str]:
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

    risky_tool = extract_field(
        risky_text,
        "tool_name",
        "ATTEMPTED_ACTION",
    )

    safe_args = extract_field(
        safe_text,
        "args",
        "ATTEMPTED_ACTION",
    )

    risky_args = extract_field(
        risky_text,
        "args",
        "ATTEMPTED_ACTION",
    )

    safe_tool_normalized = normalize_expression(
        safe_tool
    )
    risky_tool_normalized = normalize_expression(
        risky_tool
    )

    safe_args_normalized = normalize_expression(
        safe_args
    )
    risky_args_normalized = normalize_expression(
        risky_args
    )

    if safe_tool_normalized != risky_tool_normalized:
        category = "tool_mismatch"

    elif safe_args_normalized != risky_args_normalized:
        if (
            normalize_placeholder_underscores(
                safe_args_normalized
            )
            == normalize_placeholder_underscores(
                risky_args_normalized
            )
        ):
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


def main() -> None:
    output_rows: list[dict[str, Any]] = []

    split_summary: dict[str, Any] = {}

    for split, path in SPLIT_PATHS.items():
        if not path.exists():
            raise FileNotFoundError(path)

        rows = load_jsonl(path)

        if len(rows) != EXPECTED_ROWS[split]:
            raise ValueError(
                f"{split}: expected "
                f"{EXPECTED_ROWS[split]} rows, "
                f"found {len(rows)}."
            )

        grouped: dict[
            str,
            list[dict[str, Any]],
        ] = defaultdict(list)

        for row in rows:
            grouped[
                canonical_pair_id(
                    str(row["pair_id"])
                )
            ].append(row)

        if len(grouped) != EXPECTED_PAIRS[split]:
            raise ValueError(
                f"{split}: expected "
                f"{EXPECTED_PAIRS[split]} pairs, "
                f"found {len(grouped)}."
            )

        category_counts: Counter[str] = Counter()
        suite_counts: Counter[str] = Counter()
        category_suite_counts: Counter[
            tuple[str, str]
        ] = Counter()

        for pair_id, members in sorted(
            grouped.items()
        ):
            if len(members) != 2:
                raise ValueError(
                    f"{pair_id}: expected 2 rows, "
                    f"found {len(members)}."
                )

            by_label = {
                int(member["label"]): member
                for member in members
            }

            if set(by_label) != {0, 1}:
                raise ValueError(
                    f"{pair_id}: expected labels 0 and 1."
                )

            safe = by_label[0]
            risky = by_label[1]

            if safe["suite"] != risky["suite"]:
                raise ValueError(
                    f"{pair_id}: suite mismatch."
                )

            classification = classify_pair(
                str(safe["text"]),
                str(risky["text"]),
            )

            category = classification["category"]
            suite = str(safe["suite"])

            category_counts[category] += 1
            suite_counts[suite] += 1
            category_suite_counts[
                (category, suite)
            ] += 1

            output_rows.append(
                {
                    "split": split,
                    "pair_id": pair_id,
                    "suite": suite,
                    **classification,
                }
            )

        split_summary[split] = {
            "rows": len(rows),
            "pairs": len(grouped),
            "category_counts": dict(
                sorted(category_counts.items())
            ),
            "category_proportions": {
                category: (
                    count / len(grouped)
                )
                for category, count
                in sorted(category_counts.items())
            },
            "suite_counts": dict(
                sorted(suite_counts.items())
            ),
            "category_by_suite": {
                f"{category}::{suite}": count
                for (category, suite), count
                in sorted(
                    category_suite_counts.items()
                )
            },
        }

    total_category_counts = Counter(
        row["category"]
        for row in output_rows
    )

    total_suite_counts = Counter(
        row["suite"]
        for row in output_rows
    )

    total_pairs = len(output_rows)

    expected_total_pairs = sum(
        EXPECTED_PAIRS.values()
    )

    if total_pairs != expected_total_pairs:
        raise ValueError(
            f"Expected {expected_total_pairs} total pairs, "
            f"found {total_pairs}."
        )

    output_rows.sort(
        key=lambda row: (
            str(row["split"]),
            str(row["category"]),
            str(row["pair_id"]),
        )
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
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
        "audit": (
            "agentdojo_turkish_pair_"
            "category_audit_v0.1.0"
        ),
        "completed_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "classification_scope": (
            "Train and validation pairs from the "
            "frozen Turkish training package."
        ),
        "category_definition": {
            "tool_mismatch": (
                "Safe and risky variants attempt "
                "different tools."
            ),
            "argument_mismatch": (
                "Tool remains the same while attempted "
                "arguments differ materially."
            ),
            (
                "placeholder_only_or_"
                "subtle_argument_mismatch"
            ): (
                "The argument difference disappears "
                "after placeholder underscore "
                "normalization."
            ),
            "other": (
                "No attempted-tool or attempted-argument "
                "difference was detected."
            ),
        },
        "total": {
            "rows": sum(EXPECTED_ROWS.values()),
            "pairs": total_pairs,
            "category_counts": dict(
                sorted(
                    total_category_counts.items()
                )
            ),
            "category_proportions": {
                category: count / total_pairs
                for category, count
                in sorted(
                    total_category_counts.items()
                )
            },
            "suite_counts": dict(
                sorted(total_suite_counts.items())
            ),
        },
        "splits": split_summary,
        "rows": output_rows,
        "limitations": [
            (
                "Categories are generated by deterministic "
                "string comparison heuristics."
            ),
            (
                "The audit does not infer semantic "
                "differences outside attempted tool "
                "and attempted arguments."
            ),
            (
                "All rare categories require manual "
                "review before drawing conclusions."
            ),
        ],
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
        "AGENTDOJO TURKISH PAIR CATEGORY "
        "AUDIT v0.1.0"
    )
    print("=" * 80)
    print()

    for split in ("train", "validation"):
        summary = split_summary[split]

        print(split.upper())
        print("  pairs:", summary["pairs"])

        for category, count in (
            summary["category_counts"].items()
        ):
            proportion = (
                summary[
                    "category_proportions"
                ][category]
            )

            print(
                f"  {category}: "
                f"{count} "
                f"({proportion:.2%})"
            )

        print()

    print("TOTAL")
    print("  pairs:", total_pairs)

    for category, count in sorted(
        total_category_counts.items()
    ):
        print(
            f"  {category}: "
            f"{count} "
            f"({count / total_pairs:.2%})"
        )

    print()
    print("CSV:", OUTPUT_CSV)
    print("JSON:", OUTPUT_JSON)
    print()
    print("Pair category audit: PASSED")


if __name__ == "__main__":
    main()

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


SOURCE_PATH = Path(
    "data/interim/"
    "agentdojo_user_task_structure_pool_v0.1.jsonl"
)

OUTPUT_DIR = Path(
    "data/interim"
)

REVIEW_DIR = Path(
    "data/interim/review_batches"
)

AUDIT_POOL_PATH = (
    OUTPUT_DIR /
    "agentdojo_legitimate_task_audit_pool_v0.1.csv"
)

BATCH_PATHS = [
    (
        REVIEW_DIR /
        "agentdojo_legitimate_task_audit_batch_017.csv"
    ),
    (
        REVIEW_DIR /
        "agentdojo_legitimate_task_audit_batch_018.csv"
    ),
    (
        REVIEW_DIR /
        "agentdojo_legitimate_task_audit_batch_019.csv"
    ),
    (
        REVIEW_DIR /
        "agentdojo_legitimate_task_audit_batch_020.csv"
    ),
]


def load_jsonl(
    path: Path,
) -> list[dict[str, Any]]:

    records = []

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:

        for line in file:

            line = line.strip()

            if line:
                records.append(
                    json.loads(line)
                )

    return records


def suggested_value(
    action_classes: list[str],
) -> str:

    high_value_classes = {
        "financial_write_candidate",
        "access_control_write_candidate",
        "external_communication_write_candidate",
        "state_changing_candidate",
    }

    if (
        set(action_classes)
        &
        high_value_classes
    ):
        return (
            "high_value_legitimate_structure"
        )

    return "usable_legitimate_structure"


def suggested_impact(
    action_classes: list[str],
) -> str:

    classes = set(
        action_classes
    )

    if classes & {
        "financial_write_candidate",
        "access_control_write_candidate",
    }:
        return "high"

    if classes & {
        "external_communication_write_candidate",
        "state_changing_candidate",
    }:
        return "medium"

    return "low"


def write_csv(
    path: Path,
    rows: list[dict[str, Any]],
) -> None:

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fieldnames = list(
        rows[0].keys()
    )

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(rows)


def main() -> None:

    records = load_jsonl(
        SOURCE_PATH
    )


    if len(records) != 86:
        raise ValueError(
            "Expected 86 legitimate user-task structures, "
            f"found {len(records)}."
        )


    rows = []


    for record in records:

        action_classes = record.get(
            "suggested_action_classes",
            [],
        )

        functions = record.get(
            "referenced_function_names",
            [],
        )

        action_sequence = record.get(
            "expected_action_sequence",
            [],
        )


        if not action_sequence:
            raise ValueError(
                "Legitimate user task unexpectedly has "
                "an empty action sequence: "
                f"{record['structure_id']}"
            )


        rows.append(
            {
                "structure_id": (
                    record["structure_id"]
                ),

                "suite": (
                    record["suite"]
                ),

                "task_id": (
                    record["task_id"]
                ),

                "effective_from_version": (
                    record["source"][
                        "effective_from_version"
                    ]
                ),

                "prompt": (
                    record[
                        "prompt_or_goal"
                    ]
                ),

                "ground_truth_functions": (
                    json.dumps(
                        functions,
                        ensure_ascii=False,
                    )
                ),

                "action_classes": (
                    json.dumps(
                        action_classes,
                        ensure_ascii=False,
                    )
                ),

                "action_sequence_length": (
                    len(action_sequence)
                ),

                "suggested_review_decision": (
                    suggested_value(
                        action_classes
                    )
                ),

                "suggested_action_impact": (
                    suggested_impact(
                        action_classes
                    )
                ),

                "review_decision": "",

                "scenario_family": "",

                "action_impact": "",

                "review_note": "",
            }
        )


    rows.sort(
        key=lambda row: (
            row["suite"],
            int(
                row["task_id"]
                .split("_")[-1]
            ),
        )
    )


    write_csv(
        AUDIT_POOL_PATH,
        rows,
    )


    # 86 examples:
    # 22 + 22 + 21 + 21
    batch_slices = [
        rows[0:22],
        rows[22:44],
        rows[44:65],
        rows[65:86],
    ]


    for path, batch_rows in zip(
        BATCH_PATHS,
        batch_slices,
        strict=True,
    ):
        write_csv(
            path,
            batch_rows,
        )


    suite_counts = Counter(
        row["suite"]
        for row in rows
    )

    suggestion_counts = Counter(
        row[
            "suggested_review_decision"
        ]
        for row in rows
    )

    impact_counts = Counter(
        row[
            "suggested_action_impact"
        ]
        for row in rows
    )


    print("=" * 80)
    print(
        "AGENTDOJO LEGITIMATE TASK AUDIT BATCHES CREATED"
    )
    print("=" * 80)

    print()
    print(
        "Total legitimate structures:",
        len(rows),
    )

    print()
    print(
        "Structures by suite:"
    )

    for suite, count in sorted(
        suite_counts.items()
    ):
        print(
            f"  {suite}: {count}"
        )

    print()
    print(
        "Suggested review decisions:"
    )

    for decision, count in (
        suggestion_counts.items()
    ):
        print(
            f"  {decision}: {count}"
        )

    print()
    print(
        "Suggested action impacts:"
    )

    for impact, count in (
        impact_counts.items()
    ):
        print(
            f"  {impact}: {count}"
        )

    print()
    print(
        "Audit batches:"
    )

    for path, batch_rows in zip(
        BATCH_PATHS,
        batch_slices,
        strict=True,
    ):
        print(
            f"  {path.name}: "
            f"{len(batch_rows)}"
        )

    print()
    print(
        f"Audit pool: {AUDIT_POOL_PATH}"
    )


if __name__ == "__main__":
    main()

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


REVISION_QUEUE_PATH = Path(
    "data/interim/"
    "agentdojo_action_attempt_revision_queue_v0.1.1.csv"
)

PAIR_PLAN_PATH = Path(
    "data/interim/"
    "agentdojo_contextual_pair_plan_v0.1.2_p1_repaired.jsonl"
)

OUTPUT_JSONL_PATH = Path(
    "data/interim/"
    "agentdojo_p2_revision_inventory_v0.1.2.jsonl"
)

OUTPUT_REPORT_PATH = Path(
    "data/interim/"
    "agentdojo_p2_revision_inventory_v0.1.2_report.json"
)


EXPECTED_P2_PAIR_COUNT = 23


def load_csv(
    path: Path,
) -> tuple[list[str], list[dict[str, str]]]:

    if not path.exists():
        raise FileNotFoundError(
            f"Missing revision queue: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:

        reader = csv.DictReader(file)

        if reader.fieldnames is None:
            raise ValueError(
                f"CSV has no header: {path}"
            )

        return list(reader.fieldnames), list(reader)


def load_jsonl(
    path: Path,
) -> list[dict[str, Any]]:

    if not path.exists():
        raise FileNotFoundError(
            f"Missing pair plan: {path}"
        )

    records = []

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
                records.append(json.loads(line))

            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid JSONL at line {line_number}"
                ) from error

    return records


def write_jsonl(
    path: Path,
    records: list[dict[str, Any]],
) -> None:

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
    ) as file:

        for record in records:
            file.write(
                json.dumps(
                    record,
                    ensure_ascii=False,
                )
            )
            file.write("\n")


def first_value(
    row: dict[str, Any],
    candidates: list[str],
) -> Any:

    for key in candidates:

        value = row.get(key)

        if value not in {
            None,
            "",
        }:
            return value

    return None


def normalize_priority(
    value: Any,
) -> str:

    text = str(
        value or ""
    ).strip().upper()

    aliases = {
        "1": "P1",
        "2": "P2",
        "3": "P3",
        "PRIORITY_1": "P1",
        "PRIORITY_2": "P2",
        "PRIORITY_3": "P3",
        "PRIORITY 1": "P1",
        "PRIORITY 2": "P2",
        "PRIORITY 3": "P3",
    }

    return aliases.get(
        text,
        text,
    )


def structure_id(
    context: dict[str, Any],
) -> str:

    return str(
        context.get("structure_id")
        or context.get("blueprint_id")
        or ""
    )


def action_name(
    action: dict[str, Any],
) -> str:

    return str(
        action.get("normalized_function_name")
        or action.get("function")
        or action.get("tool_name")
        or ""
    )


def action_args(
    action: dict[str, Any],
) -> Any:

    if action.get("args") is not None:
        return action["args"]

    return action.get("args_expression")


def main() -> None:

    fieldnames, revision_rows = load_csv(
        REVISION_QUEUE_PATH
    )

    pairs = load_jsonl(
        PAIR_PLAN_PATH
    )

    pair_by_id = {
        str(pair["pair_id"]): pair
        for pair in pairs
    }


    priority_candidates = [
        "repair_priority",
        "revision_priority",
        "priority",
        "human_review_priority",
    ]

    issue_candidates = [
        "issue_category",
        "revision_issue_category",
        "primary_issue_category",
        "review_issue_category",
        "repair_issue_category",
    ]

    note_candidates = [
        "review_note",
        "revision_note",
        "issue_note",
        "repair_note",
        "human_review_note",
    ]


    priority_column = next(
        (
            column
            for column in priority_candidates
            if column in fieldnames
        ),
        None,
    )

    if priority_column is None:
        raise ValueError(
            "No recognizable priority column found.\n"
            f"Columns: {fieldnames}"
        )


    priority_counts = Counter(
        normalize_priority(
            row.get(priority_column)
        )
        for row in revision_rows
    )


    p2_rows = [
        row
        for row in revision_rows
        if normalize_priority(
            row.get(priority_column)
        )
        ==
        "P2"
    ]


    if len(p2_rows) != EXPECTED_P2_PAIR_COUNT:
        raise ValueError(
            "Expected 23 P2 pairs, "
            f"found {len(p2_rows)}.\n"
            f"Priority counts: {dict(priority_counts)}"
        )


    inventory = []


    for revision_row in p2_rows:

        pair_id = str(
            revision_row["pair_id"]
        )

        pair = pair_by_id.get(pair_id)

        if pair is None:
            raise ValueError(
                f"Pair missing from candidate plan: {pair_id}"
            )


        legitimate = pair[
            "legitimate_context"
        ]

        attacker = pair[
            "attacker_context"
        ]

        surface = pair[
            "injection_surface"
        ]

        selected = pair[
            "selected_actions"
        ]

        safe_action = selected[
            "authorized_user_action"
        ]

        risky_action = selected[
            "attacker_target_action"
        ]


        issue_category = first_value(
            revision_row,
            issue_candidates,
        )

        review_note = first_value(
            revision_row,
            note_candidates,
        )


        binding = pair.get(
            "context_bindings",
            {},
        )


        inventory.append(
            {
                "pair_id": pair_id,

                "priority": "P2",

                "suite": pair.get("suite"),

                "issue_category": issue_category,

                "review_note": review_note,

                "legitimate_structure_id": structure_id(
                    legitimate
                ),

                "attacker_structure_id": structure_id(
                    attacker
                ),

                "vector_id": surface.get(
                    "vector_id"
                ),

                "user_goal": legitimate.get(
                    "prompt_or_goal"
                ),

                "attacker_goal": attacker.get(
                    "prompt_or_goal"
                ),

                "surface_type": surface.get(
                    "surface_type"
                ),

                "source_type": surface.get(
                    "source_type"
                ),

                "retrieval_channel": surface.get(
                    "retrieval_channel"
                ),

                "source_locator": (
                    binding.get(
                        "retrieved_object_locator"
                    )
                    or
                    surface.get(
                        "source_locator"
                    )
                ),

                "binding_type": (
                    binding.get(
                        "binding_type"
                    )
                    or
                    surface.get(
                        "binding_type"
                    )
                ),

                "binding_status": (
                    binding.get(
                        "binding_status"
                    )
                    or
                    surface.get(
                        "binding_status"
                    )
                ),

                "safe_tool": action_name(
                    safe_action
                ),

                "safe_args": action_args(
                    safe_action
                ),

                "risky_tool": action_name(
                    risky_action
                ),

                "risky_args": action_args(
                    risky_action
                ),

                "same_tool_pair": (
                    action_name(safe_action)
                    ==
                    action_name(risky_action)
                ),
            }
        )


    inventory.sort(
        key=lambda row: row["pair_id"]
    )


    issue_counts = Counter(
        str(
            row["issue_category"]
            or "<missing>"
        )
        for row in inventory
    )

    suite_counts = Counter(
        str(row["suite"])
        for row in inventory
    )

    same_tool_count = sum(
        bool(row["same_tool_pair"])
        for row in inventory
    )


    write_jsonl(
        OUTPUT_JSONL_PATH,
        inventory,
    )


    report = {
        "artifact_version": "0.1.2",

        "revision_queue": str(
            REVISION_QUEUE_PATH
        ),

        "candidate_pair_plan": str(
            PAIR_PLAN_PATH
        ),

        "revision_queue_columns": fieldnames,

        "priority_column": priority_column,

        "priority_counts": dict(
            priority_counts
        ),

        "p2_pair_count": len(
            inventory
        ),

        "suite_counts": dict(
            suite_counts
        ),

        "issue_category_counts": dict(
            issue_counts
        ),

        "same_tool_pair_count": (
            same_tool_count
        ),

        "pair_ids": [
            row["pair_id"]
            for row in inventory
        ],

        "pair_plan_modified": False,

        "labeled_pool_modified": False,

        "review_decisions_modified": False,
    }


    OUTPUT_REPORT_PATH.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


    print("=" * 80)
    print(
        "AGENTDOJO P2 REVISION INVENTORY "
        "v0.1.2 CREATED"
    )
    print("=" * 80)

    print()
    print(
        "Revision queue rows:",
        len(revision_rows),
    )

    print(
        "Priority column:",
        priority_column,
    )

    print(
        "Priority counts:",
        dict(priority_counts),
    )

    print()
    print(
        "P2 pairs:",
        len(inventory),
    )

    print(
        "Same-tool P2 pairs:",
        same_tool_count,
    )

    print()
    print("P2 suites:")

    for suite, count in sorted(
        suite_counts.items()
    ):
        print(
            f"  {suite}: {count}"
        )

    print()
    print("P2 issue categories:")

    for issue, count in sorted(
        issue_counts.items()
    ):
        print(
            f"  {issue}: {count}"
        )

    print()
    print("P2 pair IDs:")

    for row in inventory:
        print(
            "  "
            f"{row['pair_id']} | "
            f"{row['suite']} | "
            f"{row['issue_category']}"
        )

    print()
    print(
        f"Inventory: {OUTPUT_JSONL_PATH}"
    )

    print(
        f"Report: {OUTPUT_REPORT_PATH}"
    )

    print()
    print(
        "Pair plan modified: no"
    )

    print(
        "Labeled pool modified: no"
    )

    print(
        "Review decisions modified: no"
    )


if __name__ == "__main__":
    main()

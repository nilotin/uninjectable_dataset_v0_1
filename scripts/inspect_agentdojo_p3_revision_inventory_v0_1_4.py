from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


REVISION_QUEUE_PATH = Path(
    "data/interim/"
    "agentdojo_action_attempt_revision_queue_v0.1.1.csv"
)

PAIR_PLAN_PATH = Path(
    "data/interim/"
    "agentdojo_contextual_pair_plan_v0.1.4_"
    "p2_travel_repaired.jsonl"
)

CUMULATIVE_LEDGER_PATH = Path(
    "data/interim/"
    "agentdojo_action_attempt_human_review_master_v0.1.4.csv"
)

OUTPUT_JSONL_PATH = Path(
    "data/interim/"
    "agentdojo_p3_revision_inventory_v0.1.4.jsonl"
)

OUTPUT_REPORT_PATH = Path(
    "data/interim/"
    "agentdojo_p3_revision_inventory_v0.1.4_report.json"
)


EXPECTED_P3_COUNT = 17

EXPECTED_ISSUE_COUNTS = {
    "contextual_alignment_issue": 6,
    "retrieval_query_mismatch": 6,
    "document_content_not_retrieved": 3,
    "retrieval_path_not_guaranteed": 2,
}


def load_csv(
    path: Path,
) -> tuple[list[str], list[dict[str, str]]]:

    if not path.exists():
        raise FileNotFoundError(
            f"Missing CSV file: {path}"
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

        return (
            list(reader.fieldnames),
            list(reader),
        )


def load_jsonl(
    path: Path,
) -> list[dict[str, Any]]:

    if not path.exists():
        raise FileNotFoundError(
            f"Missing JSONL file: {path}"
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
                records.append(
                    json.loads(line)
                )

            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid JSONL in {path}, "
                    f"line {line_number}."
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


def pair_number(
    pair_id: str,
) -> int:

    match = re.search(
        r"(\d+)$",
        pair_id,
    )

    if match is None:
        raise ValueError(
            f"Invalid pair ID: {pair_id}"
        )

    return int(match.group(1))


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


def same_tool(
    pair: dict[str, Any],
) -> bool:

    selected = pair[
        "selected_actions"
    ]

    return (
        action_name(
            selected[
                "authorized_user_action"
            ]
        )
        ==
        action_name(
            selected[
                "attacker_target_action"
            ]
        )
    )


def main() -> None:

    revision_headers, revision_rows = load_csv(
        REVISION_QUEUE_PATH
    )

    pairs = load_jsonl(
        PAIR_PLAN_PATH
    )

    _, ledger_rows = load_csv(
        CUMULATIVE_LEDGER_PATH
    )


    priority_candidates = [
        "repair_priority",
        "priority",
        "revision_priority",
        "review_priority",
    ]

    priority_column = next(
        (
            column
            for column in priority_candidates
            if column in revision_headers
        ),
        None,
    )

    if priority_column is None:
        raise ValueError(
            "Could not find priority column. "
            f"Available columns: {revision_headers}"
        )


    pair_by_id = {
        str(pair["pair_id"]): pair
        for pair in pairs
    }

    ledger_by_id = {
        str(row["pair_id"]): row
        for row in ledger_rows
    }


    p3_revision_rows = [
        row
        for row in revision_rows
        if row.get(
            priority_column,
            ""
        ).strip().upper()
        ==
        "P3"
    ]


    if (
        len(p3_revision_rows)
        !=
        EXPECTED_P3_COUNT
    ):
        raise ValueError(
            "Expected 17 P3 revision rows, "
            f"found {len(p3_revision_rows)}."
        )


    inventory = []


    for revision_row in p3_revision_rows:

        pair_id = str(
            revision_row["pair_id"]
        )

        pair = pair_by_id.get(
            pair_id
        )

        if pair is None:
            raise ValueError(
                f"P3 pair missing from v0.1.4 "
                f"candidate plan: {pair_id}"
            )


        ledger_row = ledger_by_id.get(
            pair_id
        )

        if ledger_row is None:
            raise ValueError(
                f"P3 pair missing from v0.1.4 "
                f"review ledger: {pair_id}"
            )


        if (
            ledger_row.get(
                "cumulative_review_decision"
            )
            !=
            "needs_revision"
        ):
            raise ValueError(
                f"{pair_id} is no longer marked "
                "needs_revision."
            )


        selected = pair[
            "selected_actions"
        ]

        legitimate = pair[
            "legitimate_context"
        ]

        attacker = pair[
            "attacker_context"
        ]

        surface = pair[
            "injection_surface"
        ]

        binding = pair.get(
            "context_bindings",
            {},
        )


        inventory.append(
            {
                "pair_id": pair_id,

                "repair_priority": "P3",

                "issue_category": (
                    revision_row.get(
                        "issue_category",
                        ""
                    )
                ),

                "review_note": (
                    revision_row.get(
                        "review_note",
                        ""
                    )
                ),

                "suite": pair[
                    "suite"
                ],

                "legitimate_structure_id": (
                    structure_id(
                        legitimate
                    )
                ),

                "attacker_structure_id": (
                    structure_id(
                        attacker
                    )
                ),

                "current_vector_id": (
                    surface.get(
                        "vector_id"
                    )
                ),

                "user_goal": legitimate.get(
                    "prompt_or_goal"
                ),

                "attacker_goal": attacker.get(
                    "prompt_or_goal"
                ),

                "safe_action": {
                    "tool": action_name(
                        selected[
                            "authorized_user_action"
                        ]
                    ),

                    "args": action_args(
                        selected[
                            "authorized_user_action"
                        ]
                    ),
                },

                "risky_action": {
                    "tool": action_name(
                        selected[
                            "attacker_target_action"
                        ]
                    ),

                    "args": action_args(
                        selected[
                            "attacker_target_action"
                        ]
                    ),
                },

                "same_tool_pair": same_tool(
                    pair
                ),

                "current_source_locator": (
                    binding.get(
                        "retrieved_object_locator"
                    )
                    or
                    surface.get(
                        "source_locator"
                    )
                ),

                "current_binding_type": (
                    binding.get(
                        "binding_type"
                    )
                    or
                    surface.get(
                        "binding_type"
                    )
                ),

                "current_binding_status": (
                    binding.get(
                        "binding_status"
                    )
                    or
                    surface.get(
                        "binding_status"
                    )
                ),

                "current_parameter_bindings": (
                    binding.get(
                        "parameter_bindings",
                        {},
                    )
                ),

                "current_environment_locations": (
                    surface.get(
                        "environment_locations",
                        [],
                    )
                ),

                "cumulative_review_decision": (
                    ledger_row.get(
                        "cumulative_review_decision"
                    )
                ),

                "repair_decision": None,

                "repair_note": None,
            }
        )


    inventory.sort(
        key=lambda row: pair_number(
            row["pair_id"]
        )
    )


    issue_counts = Counter(
        row[
            "issue_category"
        ]
        for row in inventory
    )

    suite_counts = Counter(
        row[
            "suite"
        ]
        for row in inventory
    )

    same_tool_count = sum(
        bool(
            row[
                "same_tool_pair"
            ]
        )
        for row in inventory
    )


    if dict(issue_counts) != (
        EXPECTED_ISSUE_COUNTS
    ):
        raise ValueError(
            "Unexpected P3 issue distribution:\n"
            f"Expected: {EXPECTED_ISSUE_COUNTS}\n"
            f"Found: {dict(issue_counts)}"
        )


    write_jsonl(
        OUTPUT_JSONL_PATH,
        inventory,
    )


    report = {
        "artifact_version": "0.1.4",

        "source_revision_queue": str(
            REVISION_QUEUE_PATH
        ),

        "source_candidate_pair_plan": str(
            PAIR_PLAN_PATH
        ),

        "source_cumulative_review_ledger": str(
            CUMULATIVE_LEDGER_PATH
        ),

        "priority_column": priority_column,

        "p3_pair_count": len(
            inventory
        ),

        "same_tool_p3_pair_count": (
            same_tool_count
        ),

        "suite_counts": dict(
            suite_counts
        ),

        "issue_counts": dict(
            issue_counts
        ),

        "pair_ids": [
            row[
                "pair_id"
            ]
            for row in inventory
        ],

        "output_inventory": str(
            OUTPUT_JSONL_PATH
        ),

        "pair_plan_modified": False,

        "labeled_pool_modified": False,

        "review_decisions_modified": False,

        "final_labels_modified": False,
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
        "AGENTDOJO P3 REVISION INVENTORY "
        "v0.1.4 CREATED"
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
        "P3 pairs:",
        len(inventory),
    )

    print(
        "Same-tool P3 pairs:",
        same_tool_count,
    )

    print()

    print("P3 suites:")

    for suite, count in sorted(
        suite_counts.items()
    ):
        print(
            f"  {suite}: {count}"
        )

    print()

    print("P3 issue categories:")

    for issue, count in sorted(
        issue_counts.items()
    ):
        print(
            f"  {issue}: {count}"
        )

    print()

    print("P3 pairs:")

    for row in inventory:

        print(
            "  "
            f"{row['pair_id']} | "
            f"{row['suite']} | "
            f"{row['issue_category']} | "
            f"vector={row['current_vector_id']} | "
            f"locator={row['current_source_locator']}"
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

    print(
        "Final labels modified: no"
    )


if __name__ == "__main__":
    main()

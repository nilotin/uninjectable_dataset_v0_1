from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SOURCE_PATH = Path(
    "data/interim/"
    "agentdojo_effective_task_inventory_v1.2.2.json"
)

OUTPUT_DIR = Path(
    "data/interim"
)

REVIEW_BATCH_DIR = Path(
    "data/interim/review_batches"
)

USER_POOL_PATH = (
    OUTPUT_DIR /
    "agentdojo_user_task_structure_pool_v0.1.jsonl"
)

INJECTION_POOL_PATH = (
    OUTPUT_DIR /
    "agentdojo_injection_task_structure_pool_v0.1.jsonl"
)

TOOL_CATALOG_PATH = (
    OUTPUT_DIR /
    "agentdojo_tool_action_catalog_v0.1.csv"
)

REPORT_PATH = (
    OUTPUT_DIR /
    "agentdojo_structure_pools_v0.1_report.json"
)

INJECTION_AUDIT_POOL_PATH = (
    OUTPUT_DIR /
    "agentdojo_injection_task_audit_pool_v0.1.csv"
)

BATCH_015_PATH = (
    REVIEW_BATCH_DIR /
    "agentdojo_injection_task_audit_batch_015.csv"
)

BATCH_016_PATH = (
    REVIEW_BATCH_DIR /
    "agentdojo_injection_task_audit_batch_016.csv"
)


def load_inventory() -> dict[str, Any]:
    return json.loads(
        SOURCE_PATH.read_text(
            encoding="utf-8"
        )
    )


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


def normalized_function_name(
    value: Any,
) -> str:

    if value is None:
        return ""

    value = str(value).strip()

    if not value:
        return ""

    # Preserve the original value elsewhere, but use the final
    # component for lexical capability classification.
    return value.split(".")[-1]


def infer_action_class(
    function_name: str,
) -> str:

    name = normalized_function_name(
        function_name
    ).lower()

    if not name:
        return "unknown_or_no_action"

    read_prefixes = (
        "get_",
        "read_",
        "search_",
        "list_",
        "find_",
        "check_",
        "fetch_",
        "view_",
        "lookup_",
    )

    if name.startswith(
        read_prefixes
    ):
        return "read_only_candidate"

    if any(
        token in name
        for token in (
            "send_money",
            "transfer_money",
            "make_payment",
            "pay_",
            "purchase",
        )
    ):
        return "financial_write_candidate"

    if any(
        token in name
        for token in (
            "add_user",
            "remove_user",
            "invite_user",
            "change_permission",
            "grant_access",
            "revoke_access",
        )
    ):
        return "access_control_write_candidate"

    if any(
        token in name
        for token in (
            "send_email",
            "send_message",
            "send_direct_message",
            "post_message",
            "reply_",
            "forward_",
        )
    ):
        return "external_communication_write_candidate"

    if any(
        token in name
        for token in (
            "create_",
            "update_",
            "edit_",
            "delete_",
            "remove_",
            "add_",
            "cancel_",
            "book_",
            "reserve_",
            "schedule_",
            "upload_",
            "share_",
        )
    ):
        return "state_changing_candidate"

    return "manual_review_required"


def build_structure_record(
    task: dict[str, Any],
    repository_commit: str,
    benchmark_version: str,
) -> dict[str, Any]:

    task_kind = task[
        "task_kind"
    ]

    structure_role = (
        "legitimate_user_goal"
        if task_kind == "user_task"
        else "attacker_goal"
    )

    expected_calls = []

    for position, call in enumerate(
        task.get(
            "ground_truth_calls",
            []
        ),
        start=1,
    ):

        original_function = call.get(
            "function"
        )

        function_name = (
            normalized_function_name(
                original_function
            )
        )

        expected_calls.append(
            {
                "sequence_position": position,
                "function": original_function,
                "normalized_function_name": function_name,
                "suggested_action_class": (
                    infer_action_class(
                        function_name
                    )
                ),
                "args": call.get("args"),
                "args_expression": call.get(
                    "args_expression"
                ),
                "placeholder_args": call.get(
                    "placeholder_args"
                ),
                "placeholder_args_expression": call.get(
                    "placeholder_args_expression"
                ),
            }
        )

    structure_id = (
        f"agentdojo_{task['suite']}_"
        f"{task_kind}_{task['task_number']:03d}"
    )

    return {
        "structure_id": structure_id,
        "scenario_source": "agentdojo",
        "suite": task["suite"],
        "structure_role": structure_role,
        "task_kind": task_kind,
        "task_id": task["task_id"],
        "task_number": task["task_number"],
        "prompt_or_goal": task.get(
            "prompt_or_goal"
        ),
        "comment": task.get(
            "comment"
        ),
        "difficulty_expression": task.get(
            "difficulty_expression"
        ),
        "expected_action_sequence": (
            expected_calls
        ),
        "referenced_function_names": [
            call[
                "normalized_function_name"
            ]
            for call in expected_calls
            if call[
                "normalized_function_name"
            ]
        ],
        "suggested_action_classes": sorted(
            {
                call[
                    "suggested_action_class"
                ]
                for call in expected_calls
            }
        ),
        "source": {
            "repository_commit": (
                repository_commit
            ),
            "benchmark_version": (
                benchmark_version
            ),
            "effective_from_version": task.get(
                "effective_from_version_string"
            ),
            "source_file": task.get(
                "source_file"
            ),
            "revision_count_up_to_target": task.get(
                "revision_count_up_to_target"
            ),
            "available_revision_versions_up_to_target": (
                task.get(
                    "available_revision_versions_up_to_target",
                    [],
                )
            ),
        },
        "curation": {
            "status": (
                "unreviewed_structure_candidate"
            ),
            "include_for_composition": False,
            "review_decision": None,
            "review_note": None,
        },
        "important_note": (
            "This is a scenario-structure source record, "
            "not a Phase-1 BERT training example and not "
            "a runtime general_risk_label."
        ),
    }


def build_tool_catalog(
    structures: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    catalog: dict[
        str,
        dict[str, Any]
    ] = {}

    for structure in structures:

        seen_in_structure = set()

        for call in structure[
            "expected_action_sequence"
        ]:

            function_name = call[
                "normalized_function_name"
            ]

            if not function_name:
                continue

            if function_name not in catalog:
                catalog[
                    function_name
                ] = {
                    "function_name": (
                        function_name
                    ),
                    "suggested_action_class": (
                        call[
                            "suggested_action_class"
                        ]
                    ),
                    "total_call_references": 0,
                    "user_task_references": 0,
                    "injection_task_references": 0,
                    "unique_structure_count": 0,
                    "suites": set(),
                    "example_structure_ids": [],
                    "manual_review_status": (
                        "unreviewed"
                    ),
                    "manual_capability_class": "",
                    "review_note": "",
                }

            entry = catalog[
                function_name
            ]

            entry[
                "total_call_references"
            ] += 1

            if (
                structure["task_kind"]
                ==
                "user_task"
            ):
                entry[
                    "user_task_references"
                ] += 1
            else:
                entry[
                    "injection_task_references"
                ] += 1

            entry["suites"].add(
                structure["suite"]
            )

            if (
                structure["structure_id"]
                not in entry[
                    "example_structure_ids"
                ]
                and len(
                    entry[
                        "example_structure_ids"
                    ]
                ) < 5
            ):
                entry[
                    "example_structure_ids"
                ].append(
                    structure[
                        "structure_id"
                    ]
                )

            seen_in_structure.add(
                function_name
            )

        for function_name in (
            seen_in_structure
        ):
            catalog[
                function_name
            ][
                "unique_structure_count"
            ] += 1

    records = []

    for function_name in sorted(
        catalog
    ):

        entry = catalog[
            function_name
        ]

        entry["suites"] = sorted(
            entry["suites"]
        )

        records.append(
            entry
        )

    return records


def write_tool_catalog(
    records: list[dict[str, Any]],
) -> None:

    TOOL_CATALOG_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fieldnames = [
        "function_name",
        "suggested_action_class",
        "total_call_references",
        "user_task_references",
        "injection_task_references",
        "unique_structure_count",
        "suites",
        "example_structure_ids",
        "manual_review_status",
        "manual_capability_class",
        "review_note",
    ]

    with TOOL_CATALOG_PATH.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        for record in records:

            row = dict(record)

            row["suites"] = json.dumps(
                row["suites"],
                ensure_ascii=False,
            )

            row[
                "example_structure_ids"
            ] = json.dumps(
                row[
                    "example_structure_ids"
                ],
                ensure_ascii=False,
            )

            writer.writerow(row)


def build_injection_audit_csv(
    structures: list[dict[str, Any]],
) -> None:

    rows = []

    for structure in structures:

        rows.append(
            {
                "structure_id": (
                    structure[
                        "structure_id"
                    ]
                ),
                "suite": (
                    structure["suite"]
                ),
                "task_id": (
                    structure["task_id"]
                ),
                "effective_from_version": (
                    structure["source"][
                        "effective_from_version"
                    ]
                ),
                "goal": (
                    structure[
                        "prompt_or_goal"
                    ]
                ),
                "ground_truth_functions": (
                    json.dumps(
                        structure[
                            "referenced_function_names"
                        ],
                        ensure_ascii=False,
                    )
                ),
                "suggested_action_classes": (
                    json.dumps(
                        structure[
                            "suggested_action_classes"
                        ],
                        ensure_ascii=False,
                    )
                ),
                "source_file": (
                    structure["source"][
                        "source_file"
                    ]
                ),
                "review_decision": "",
                "scenario_family": "",
                "target_action_risk": "",
                "review_note": "",
            }
        )

    rows.sort(
        key=lambda row: (
            row["suite"],
            row["task_id"],
        )
    )

    fieldnames = list(
        rows[0].keys()
    )

    INJECTION_AUDIT_POOL_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with INJECTION_AUDIT_POOL_PATH.open(
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

    batches = [
        (
            BATCH_015_PATH,
            rows[:18],
        ),
        (
            BATCH_016_PATH,
            rows[18:],
        ),
    ]

    REVIEW_BATCH_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    for path, batch_rows in batches:

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
            writer.writerows(
                batch_rows
            )


def main() -> None:

    inventory = load_inventory()

    repository_commit = inventory[
        "source"
    ][
        "repository_commit"
    ]

    benchmark_version = inventory[
        "target_benchmark_version"
    ]

    structures = [
        build_structure_record(
            task=task,
            repository_commit=(
                repository_commit
            ),
            benchmark_version=(
                benchmark_version
            ),
        )
        for task in inventory["tasks"]
    ]

    user_structures = [
        structure
        for structure in structures
        if structure[
            "task_kind"
        ] == "user_task"
    ]

    injection_structures = [
        structure
        for structure in structures
        if structure[
            "task_kind"
        ] == "injection_task"
    ]

    if len(structures) != 121:
        raise ValueError(
            "Expected 121 structures, "
            f"found {len(structures)}."
        )

    if len(user_structures) != 86:
        raise ValueError(
            "Expected 86 user-task structures, "
            f"found {len(user_structures)}."
        )

    if len(injection_structures) != 35:
        raise ValueError(
            "Expected 35 injection-task structures, "
            f"found {len(injection_structures)}."
        )

    write_jsonl(
        USER_POOL_PATH,
        user_structures,
    )

    write_jsonl(
        INJECTION_POOL_PATH,
        injection_structures,
    )

    tool_catalog = build_tool_catalog(
        structures
    )

    write_tool_catalog(
        tool_catalog
    )

    build_injection_audit_csv(
        injection_structures
    )

    suite_user_counts = Counter(
        structure["suite"]
        for structure in user_structures
    )

    suite_injection_counts = Counter(
        structure["suite"]
        for structure in injection_structures
    )

    action_class_counts = Counter(
        call["suggested_action_class"]
        for structure in structures
        for call in structure[
            "expected_action_sequence"
        ]
    )

    report = {
        "dataset": "agentdojo",
        "structure_pool_version": "0.1",
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "repository_commit": (
            repository_commit
        ),
        "benchmark_version": (
            benchmark_version
        ),
        "total_effective_structures": (
            len(structures)
        ),
        "user_task_structures": (
            len(user_structures)
        ),
        "injection_task_structures": (
            len(injection_structures)
        ),
        "user_tasks_by_suite": dict(
            sorted(
                suite_user_counts.items()
            )
        ),
        "injection_tasks_by_suite": dict(
            sorted(
                suite_injection_counts.items()
            )
        ),
        "unique_referenced_functions": (
            len(tool_catalog)
        ),
        "suggested_action_class_reference_counts": (
            dict(
                action_class_counts
            )
        ),
        "important_note": (
            "The action classes are conservative lexical "
            "suggestions and require manual review. AgentDojo "
            "structures are scenario-source records, not final "
            "Uninjectable runtime-risk training labels."
        ),
    }

    REPORT_PATH.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("=" * 80)
    print(
        "AGENTDOJO STRUCTURE POOLS v0.1 CREATED"
    )
    print("=" * 80)

    print()
    print(
        "Total effective structures:",
        len(structures),
    )

    print(
        "Legitimate user-task structures:",
        len(user_structures),
    )

    print(
        "Injection-task structures:",
        len(injection_structures),
    )

    print(
        "Unique referenced functions:",
        len(tool_catalog),
    )

    print()
    print(
        "User tasks by suite:"
    )

    for suite, count in sorted(
        suite_user_counts.items()
    ):
        print(
            f"  {suite}: {count}"
        )

    print()
    print(
        "Injection tasks by suite:"
    )

    for suite, count in sorted(
        suite_injection_counts.items()
    ):
        print(
            f"  {suite}: {count}"
        )

    print()
    print(
        "Suggested action-class references:"
    )

    for action_class, count in (
        action_class_counts.most_common()
    ):
        print(
            f"  {action_class}: {count}"
        )

    print()
    print(
        "Injection audit batches:"
    )

    print(
        "  Batch 015: 18"
    )

    print(
        "  Batch 016: 17"
    )

    print()
    print(
        f"User pool: {USER_POOL_PATH}"
    )

    print(
        f"Injection pool: {INJECTION_POOL_PATH}"
    )

    print(
        f"Tool catalog: {TOOL_CATALOG_PATH}"
    )

    print(
        f"Report: {REPORT_PATH}"
    )


if __name__ == "__main__":
    main()

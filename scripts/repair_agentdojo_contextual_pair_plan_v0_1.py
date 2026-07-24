from __future__ import annotations

import csv
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PAIR_PATH = Path(
    "data/interim/"
    "agentdojo_contextual_pair_plan_v0.1.jsonl"
)

BLUEPRINT_PATH = Path(
    "data/processed/"
    "agentdojo_contextual_composition_blueprint_pool_v0.1.jsonl"
)

AUDIT_PATH = Path(
    "data/interim/"
    "agentdojo_contextual_pair_plan_audit_v0.1.csv"
)

REPORT_PATH = Path(
    "data/interim/"
    "agentdojo_contextual_pair_plan_v0.1_report.json"
)

PAIR_BACKUP_PATH = Path(
    "data/interim/"
    "agentdojo_contextual_pair_plan_v0.1_pre_semantic_repair.jsonl"
)

AUDIT_BACKUP_PATH = Path(
    "data/interim/"
    "agentdojo_contextual_pair_plan_audit_v0.1_pre_semantic_repair.csv"
)


REPAIRS = {
    "agentdojo_pair_017": {
        "expected_vector_id": (
            "injection_address_change"
        ),
        "replacement_structure_id": (
            "agentdojo_banking_user_task_013"
        ),
        "expected_environment_object": (
            "address-change.txt"
        ),
        "expected_authorized_action": (
            "update_user_info"
        ),
        "expected_attacker_action": (
            "send_money"
        ),
        "reason": (
            "Align the address-change injection vector "
            "with the legitimate task that reads "
            "address-change.txt."
        ),
    },

    "agentdojo_pair_018": {
        "expected_vector_id": (
            "injection_bill_text"
        ),
        "replacement_structure_id": (
            "agentdojo_banking_user_task_000"
        ),
        "expected_environment_object": (
            "bill-december-2023.txt"
        ),
        "expected_authorized_action": (
            "send_money"
        ),
        "expected_attacker_action": (
            "send_money"
        ),
        "reason": (
            "Align the bill injection vector with the "
            "legitimate bill-payment workflow that reads "
            "bill-december-2023.txt."
        ),
    },

    "agentdojo_pair_020": {
        "expected_vector_id": (
            "injection_landloard_notice"
        ),
        "replacement_structure_id": (
            "agentdojo_banking_user_task_002"
        ),
        "expected_environment_object": (
            "landlord-notices.txt"
        ),
        "expected_authorized_action": (
            "update_scheduled_transaction"
        ),
        "expected_attacker_action": (
            "update_scheduled_transaction"
        ),
        "reason": (
            "Align the landlord-notice injection vector "
            "with the legitimate rent-adjustment workflow "
            "that reads landlord-notices.txt."
        ),
    },
}


IMPACT_RANK = {
    "low": 1,
    "medium": 2,
    "high": 3,
}


WRITE_CAPABILITY_CLASSES = {
    "access_control_write",
    "booking_or_reservation_write",
    "credential_or_account_write",
    "destructive_or_revocation_write",
    "external_communication_write",
    "financial_write",
    "state_changing_write",
    "private_communication_read_with_state_change",
}


def load_jsonl(
    path: Path,
) -> list[dict[str, Any]]:

    records: list[dict[str, Any]] = []

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


def action_function_name(
    action: dict[str, Any],
) -> str:

    return str(
        action.get(
            "normalized_function_name"
        )
        or
        action.get(
            "function"
        )
        or
        ""
    )


def action_impact(
    action: dict[str, Any],
) -> str:

    return str(
        action.get(
            "tool_metadata",
            {},
        ).get(
            "action_impact",
            ""
        )
    )


def action_capability(
    action: dict[str, Any],
) -> str:

    return str(
        action.get(
            "tool_metadata",
            {},
        ).get(
            "capability_class",
            ""
        )
    )


def select_target_action(
    blueprint: dict[str, Any],
) -> dict[str, Any]:

    sequence = (
        blueprint[
            "action_semantics"
        ][
            "reference_action_sequence"
        ]
    )

    if not sequence:
        raise ValueError(
            "Replacement blueprint has no "
            "reference action sequence: "
            f"{blueprint['blueprint_id']}"
        )

    def score(
        action: dict[str, Any],
    ) -> tuple[int, int, int]:

        return (
            IMPACT_RANK.get(
                action_impact(
                    action
                ),
                0,
            ),
            (
                1
                if action_capability(
                    action
                )
                in
                WRITE_CAPABILITY_CLASSES
                else 0
            ),
            int(
                action.get(
                    "sequence_position",
                    0,
                )
                or
                0
            ),
        )

    return max(
        sequence,
        key=score,
    )


def compact_structure(
    blueprint: dict[str, Any],
) -> dict[str, Any]:

    structure = blueprint[
        "structure"
    ]

    curation = structure.get(
        "curation",
        {},
    )

    return {
        "blueprint_id": (
            blueprint[
                "blueprint_id"
            ]
        ),

        "structure_id": (
            structure[
                "structure_id"
            ]
        ),

        "task_kind": (
            structure[
                "task_kind"
            ]
        ),

        "structure_role": (
            structure[
                "structure_role"
            ]
        ),

        "prompt_or_goal": (
            structure[
                "prompt_or_goal"
            ]
        ),

        "scenario_family": (
            curation.get(
                "scenario_family"
            )
        ),

        "quality_tier": (
            curation.get(
                "quality_tier"
            )
        ),

        "source": structure.get(
            "source",
            {},
        ),
    }


def compact_action(
    action: dict[str, Any],
) -> dict[str, Any]:

    return {
        "sequence_position": (
            action.get(
                "sequence_position"
            )
        ),

        "function": (
            action_function_name(
                action
            )
        ),

        "args": action.get(
            "args"
        ),

        "args_expression": (
            action.get(
                "args_expression"
            )
        ),

        "placeholder_args": (
            action.get(
                "placeholder_args"
            )
        ),

        "placeholder_args_expression": (
            action.get(
                "placeholder_args_expression"
            )
        ),

        "capability_class": (
            action_capability(
                action
            )
        ),

        "action_impact": (
            action_impact(
                action
            )
        ),
    }


def compute_pairing_score(
    pair: dict[str, Any],
) -> int:

    safe_action = (
        pair[
            "selected_actions"
        ][
            "authorized_user_action"
        ]
    )

    risky_action = (
        pair[
            "selected_actions"
        ][
            "attacker_target_action"
        ]
    )

    score = 40

    score += (
        IMPACT_RANK.get(
            risky_action[
                "action_impact"
            ],
            0,
        )
        *
        8
    )

    score += (
        IMPACT_RANK.get(
            safe_action[
                "action_impact"
            ],
            0,
        )
        *
        4
    )

    same_tool = (
        safe_action[
            "function"
        ]
        ==
        risky_action[
            "function"
        ]
    )

    attacker_marker_present = bool(
        pair[
            "pairing_diagnostics"
        ].get(
            "attacker_marker_present",
            False,
        )
    )

    if not same_tool:
        score += 10

    elif attacker_marker_present:
        score += 7

    else:
        score += 2

    if (
        pair[
            "legitimate_context"
        ].get(
            "quality_tier"
        )
        ==
        "A"
    ):
        score += 3

    if (
        pair[
            "attacker_context"
        ].get(
            "quality_tier"
        )
        ==
        "A"
    ):
        score += 3

    return score


def load_audit_rows(
    path: Path,
) -> tuple[
    list[str],
    list[dict[str, str]],
]:

    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:

        reader = csv.DictReader(
            file
        )

        if reader.fieldnames is None:
            raise ValueError(
                "Audit CSV has no header."
            )

        return (
            list(
                reader.fieldnames
            ),
            list(reader),
        )


def write_audit_rows(
    path: Path,
    fieldnames: list[str],
    rows: list[dict[str, str]],
) -> None:

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

    pairs = load_jsonl(
        PAIR_PATH
    )

    blueprints = load_jsonl(
        BLUEPRINT_PATH
    )


    if len(pairs) != 100:
        raise ValueError(
            f"Expected 100 pairs, found {len(pairs)}."
        )


    if not PAIR_BACKUP_PATH.exists():
        shutil.copy2(
            PAIR_PATH,
            PAIR_BACKUP_PATH,
        )

    if not AUDIT_BACKUP_PATH.exists():
        shutil.copy2(
            AUDIT_PATH,
            AUDIT_BACKUP_PATH,
        )


    blueprint_by_structure_id = {
        str(
            blueprint[
                "structure"
            ][
                "structure_id"
            ]
        ): blueprint
        for blueprint in blueprints
    }

    pair_by_id = {
        str(
            pair[
                "pair_id"
            ]
        ): pair
        for pair in pairs
    }


    repair_timestamp = datetime.now(
        timezone.utc
    ).isoformat()


    for pair_id, repair in REPAIRS.items():

        pair = pair_by_id.get(
            pair_id
        )

        if pair is None:
            raise ValueError(
                f"Missing pair: {pair_id}"
            )


        actual_vector_id = (
            pair[
                "injection_surface"
            ][
                "vector_id"
            ]
        )

        if (
            actual_vector_id
            !=
            repair[
                "expected_vector_id"
            ]
        ):
            raise ValueError(
                f"Unexpected vector for {pair_id}: "
                f"{actual_vector_id}"
            )


        replacement_blueprint = (
            blueprint_by_structure_id.get(
                repair[
                    "replacement_structure_id"
                ]
            )
        )

        if replacement_blueprint is None:
            raise ValueError(
                "Missing replacement blueprint: "
                f"{repair['replacement_structure_id']}"
            )


        if (
            replacement_blueprint[
                "suite"
            ]
            !=
            pair[
                "suite"
            ]
        ):
            raise ValueError(
                f"Suite mismatch for {pair_id}."
            )


        replacement_goal = str(
            replacement_blueprint[
                "structure"
            ][
                "prompt_or_goal"
            ]
        )

        expected_object = (
            repair[
                "expected_environment_object"
            ]
        )

        if (
            expected_object
            not in
            replacement_goal
        ):
            raise ValueError(
                "Replacement goal does not reference "
                f"{expected_object}: {replacement_goal}"
            )


        replacement_sequence = (
            replacement_blueprint[
                "action_semantics"
            ][
                "reference_action_sequence"
            ]
        )

        replacement_functions = {
            action_function_name(
                action
            )
            for action in replacement_sequence
        }

        if "read_file" not in (
            replacement_functions
        ):
            raise ValueError(
                f"{pair_id} replacement does not "
                "contain read_file."
            )


        authorized_action = (
            select_target_action(
                replacement_blueprint
            )
        )

        authorized_function = (
            action_function_name(
                authorized_action
            )
        )

        if (
            authorized_function
            !=
            repair[
                "expected_authorized_action"
            ]
        ):
            raise ValueError(
                f"Unexpected authorized action for "
                f"{pair_id}: {authorized_function}"
            )


        attacker_action = (
            pair[
                "selected_actions"
            ][
                "attacker_target_action"
            ]
        )

        if (
            attacker_action[
                "function"
            ]
            !=
            repair[
                "expected_attacker_action"
            ]
        ):
            raise ValueError(
                f"Unexpected attacker action for "
                f"{pair_id}: "
                f"{attacker_action['function']}"
            )


        previous_structure_id = (
            pair[
                "legitimate_context"
            ][
                "structure_id"
            ]
        )


        pair[
            "legitimate_context"
        ] = compact_structure(
            replacement_blueprint
        )

        pair[
            "selected_actions"
        ][
            "authorized_user_action"
        ] = compact_action(
            authorized_action
        )


        same_tool = (
            authorized_function
            ==
            attacker_action[
                "function"
            ]
        )


        pair[
            "pairing_diagnostics"
        ][
            "surface_matches_legitimate_workflow"
        ] = True

        pair[
            "pairing_diagnostics"
        ][
            "surface_matches_exact_environment_object"
        ] = True

        pair[
            "pairing_diagnostics"
        ][
            "exact_environment_object"
        ] = expected_object

        pair[
            "pairing_diagnostics"
        ][
            "same_tool_name_across_variants"
        ] = same_tool

        pair[
            "pairing_diagnostics"
        ][
            "pairing_score"
        ] = compute_pairing_score(
            pair
        )


        repair_history = pair.setdefault(
            "repair_history",
            [],
        )

        repair_history.append(
            {
                "repair_version": (
                    "semantic_alignment_v0.1"
                ),

                "repaired_at": (
                    repair_timestamp
                ),

                "reason": (
                    repair[
                        "reason"
                    ]
                ),

                "vector_id": (
                    actual_vector_id
                ),

                "environment_object": (
                    expected_object
                ),

                "previous_user_structure_id": (
                    previous_structure_id
                ),

                "replacement_user_structure_id": (
                    repair[
                        "replacement_structure_id"
                    ]
                ),
            }
        )


    # --------------------------------------------------------
    # Global pair validation
    # --------------------------------------------------------

    mismatch_pairs = [
        pair[
            "pair_id"
        ]
        for pair in pairs
        if not pair[
            "pairing_diagnostics"
        ][
            "surface_matches_legitimate_workflow"
        ]
    ]

    if mismatch_pairs:
        raise ValueError(
            "Surface/workflow mismatches remain: "
            f"{mismatch_pairs}"
        )


    planned_rows = sum(
        int(
            pair[
                "composition_state"
            ][
                "planned_runtime_row_count"
            ]
        )
        for pair in pairs
    )

    if planned_rows != 200:
        raise ValueError(
            f"Expected 200 planned rows, found {planned_rows}."
        )


    same_tool_count = sum(
        1
        for pair in pairs
        if pair[
            "pairing_diagnostics"
        ][
            "same_tool_name_across_variants"
        ]
    )

    suite_counts = Counter(
        str(
            pair[
                "suite"
            ]
        )
        for pair in pairs
    )

    user_usage = Counter(
        str(
            pair[
                "legitimate_context"
            ][
                "structure_id"
            ]
        )
        for pair in pairs
    )

    attacker_usage = Counter(
        str(
            pair[
                "attacker_context"
            ][
                "structure_id"
            ]
        )
        for pair in pairs
    )

    vector_usage = Counter(
        (
            f"{pair['suite']}:"
            f"{pair['injection_surface']['vector_id']}"
        )
        for pair in pairs
    )


    write_jsonl(
        PAIR_PATH,
        pairs,
    )


    # --------------------------------------------------------
    # Update audit CSV
    # --------------------------------------------------------

    fieldnames, audit_rows = (
        load_audit_rows(
            AUDIT_PATH
        )
    )

    audit_by_pair_id = {
        row[
            "pair_id"
        ]: row
        for row in audit_rows
    }


    for pair_id in REPAIRS:

        pair = pair_by_id[
            pair_id
        ]

        row = audit_by_pair_id.get(
            pair_id
        )

        if row is None:
            raise ValueError(
                f"Missing audit row: {pair_id}"
            )


        row[
            "user_structure_id"
        ] = (
            pair[
                "legitimate_context"
            ][
                "structure_id"
            ]
        )

        row[
            "user_scenario_family"
        ] = str(
            pair[
                "legitimate_context"
            ].get(
                "scenario_family",
                "",
            )
            or
            ""
        )

        row[
            "surface_matches_workflow"
        ] = "True"

        row[
            "authorized_action"
        ] = (
            pair[
                "selected_actions"
            ][
                "authorized_user_action"
            ][
                "function"
            ]
        )

        row[
            "authorized_action_impact"
        ] = (
            pair[
                "selected_actions"
            ][
                "authorized_user_action"
            ][
                "action_impact"
            ]
        )

        row[
            "same_tool_name"
        ] = str(
            pair[
                "pairing_diagnostics"
            ][
                "same_tool_name_across_variants"
            ]
        )

        row[
            "pairing_score"
        ] = str(
            pair[
                "pairing_diagnostics"
            ][
                "pairing_score"
            ]
        )


    write_audit_rows(
        AUDIT_PATH,
        fieldnames,
        audit_rows,
    )


    # --------------------------------------------------------
    # Update report
    # --------------------------------------------------------

    report = json.loads(
        REPORT_PATH.read_text(
            encoding="utf-8"
        )
    )

    report[
        "semantic_repair_version"
    ] = "0.1"

    report[
        "semantic_repair_timestamp"
    ] = repair_timestamp

    report[
        "semantic_repair_pair_count"
    ] = len(REPAIRS)

    report[
        "semantic_repaired_pair_ids"
    ] = sorted(
        REPAIRS
    )

    report[
        "surface_match_count"
    ] = 100

    report[
        "surface_mismatch_count"
    ] = 0

    report[
        "same_tool_pair_count"
    ] = same_tool_count

    report[
        "different_tool_pair_count"
    ] = (
        len(pairs)
        -
        same_tool_count
    )

    report[
        "suite_pair_counts"
    ] = dict(
        suite_counts
    )

    report[
        "unique_user_structure_count"
    ] = len(
        user_usage
    )

    report[
        "unique_attacker_structure_count"
    ] = len(
        attacker_usage
    )

    report[
        "unique_vector_count"
    ] = len(
        vector_usage
    )

    report[
        "maximum_user_structure_reuse"
    ] = max(
        user_usage.values()
    )

    report[
        "maximum_attacker_structure_reuse"
    ] = max(
        attacker_usage.values()
    )

    report[
        "maximum_vector_reuse"
    ] = max(
        vector_usage.values()
    )

    report[
        "runtime_label_count"
    ] = 0


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
        "AGENTDOJO CONTEXTUAL PAIR PLAN "
        "SEMANTIC REPAIR v0.1 APPLIED"
    )
    print("=" * 80)

    print()
    print(
        "Repaired pairs:",
        len(REPAIRS),
    )

    for pair_id, repair in REPAIRS.items():

        pair = pair_by_id[
            pair_id
        ]

        print(
            "  "
            f"{pair_id}: "
            f"{repair['expected_vector_id']} → "
            f"{pair['legitimate_context']['structure_id']} → "
            f"{repair['expected_environment_object']}"
        )

    print()
    print(
        "Surface/workflow matches:",
        100,
    )

    print(
        "Surface/workflow mismatches:",
        0,
    )

    print(
        "Same-tool minimal pairs:",
        same_tool_count,
    )

    print(
        "Different-tool pairs:",
        (
            len(pairs)
            -
            same_tool_count
        ),
    )

    print()
    print(
        "Unique user structures:",
        len(user_usage),
    )

    print(
        "Unique attacker structures:",
        len(attacker_usage),
    )

    print(
        "Unique vectors:",
        len(vector_usage),
    )

    print()
    print(
        "Planned runtime rows:",
        planned_rows,
    )

    print(
        "Runtime labels generated: 0"
    )

    print()
    print(
        f"Pair-plan backup: "
        f"{PAIR_BACKUP_PATH}"
    )

    print(
        f"Audit backup: "
        f"{AUDIT_BACKUP_PATH}"
    )

    print(
        f"Updated pair plan: "
        f"{PAIR_PATH}"
    )


if __name__ == "__main__":
    main()

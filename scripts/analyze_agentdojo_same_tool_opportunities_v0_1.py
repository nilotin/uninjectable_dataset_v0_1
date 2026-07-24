from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


PROCESSED_DIR = Path("data/processed")
INTERIM_DIR = Path("data/interim")

PAIR_PATH = (
    INTERIM_DIR
    / "agentdojo_contextual_pair_plan_v0.1.jsonl"
)

BLUEPRINT_PATH = (
    PROCESSED_DIR
    / "agentdojo_contextual_composition_blueprint_pool_v0.1.jsonl"
)

CANDIDATE_PATH = (
    INTERIM_DIR
    / "agentdojo_same_tool_conversion_candidates_v0.1.jsonl"
)

AUDIT_PATH = (
    INTERIM_DIR
    / "agentdojo_same_tool_conversion_candidates_v0.1.csv"
)

REPORT_PATH = (
    INTERIM_DIR
    / "agentdojo_same_tool_conversion_candidates_v0.1_report.json"
)


EXPECTED_PAIR_COUNT = 100
EXPECTED_CURRENT_SAME_TOOL_COUNT = 4
MAX_CANDIDATES_PER_PAIR = 10


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


RETRIEVAL_TOOLS_BY_CHANNEL = {
    "filesystem_document_read": {
        "read_file",
    },

    "bank_transaction_history_read": {
        "get_balance",
        "get_iban",
        "get_most_recent_transactions",
        "get_scheduled_transactions",
    },

    "external_web_fetch": {
        "get_webpage",
    },

    "slack_channel_discovery": {
        "get_channels",
        "get_users_in_channel",
        "read_channel_messages",
    },

    "third_party_review_retrieval": {
        "get_rating_reviews_for_car_rental",
        "get_rating_reviews_for_hotels",
        "get_rating_reviews_for_restaurants",
    },

    "calendar_search_or_read": {
        "get_day_calendar_events",
        "search_calendar_events",
    },

    "cloud_drive_search_or_read": {
        "get_file_by_id",
        "list_files",
        "search_files",
        "search_files_by_filename",
    },

    "email_search_or_read": {
        "get_draft_emails",
        "get_received_emails",
        "get_sent_emails",
        "get_unread_emails",
        "search_emails",
    },
}


EXACT_OBJECT_BY_VECTOR_ID = {
    "injection_address_change": (
        "address-change.txt"
    ),

    "injection_bill_text": (
        "bill-december-2023.txt"
    ),

    "injection_landloard_notice": (
        "landlord-notices.txt"
    ),
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


def write_csv(
    path: Path,
    rows: list[dict[str, Any]],
) -> None:

    if not rows:
        raise ValueError(
            "Candidate CSV cannot be empty."
        )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=list(
                rows[0].keys()
            ),
        )

        writer.writeheader()
        writer.writerows(rows)


def stable_hash_number(
    *values: Any,
) -> int:

    text = "||".join(
        str(value)
        for value in values
    )

    digest = hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()

    return int(
        digest[:16],
        16,
    )


def canonical_json(
    value: Any,
) -> str:

    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
    )


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
            "",
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
            "",
        )
    )


def action_selection_score(
    action: dict[str, Any],
) -> tuple[int, int, int]:

    impact = action_impact(
        action
    )

    capability = action_capability(
        action
    )

    position = int(
        action.get(
            "sequence_position",
            0,
        )
        or
        0
    )

    return (
        IMPACT_RANK.get(
            impact,
            0,
        ),
        (
            1
            if capability
            in WRITE_CAPABILITY_CLASSES
            else 0
        ),
        position,
    )


def select_target_action(
    blueprint: dict[str, Any],
) -> dict[str, Any] | None:

    sequence = (
        blueprint.get(
            "action_semantics",
            {},
        ).get(
            "reference_action_sequence",
            [],
        )
    )

    if not sequence:
        return None

    return max(
        sequence,
        key=action_selection_score,
    )


def referenced_tools(
    blueprint: dict[str, Any],
) -> set[str]:

    sequence = (
        blueprint.get(
            "action_semantics",
            {},
        ).get(
            "reference_action_sequence",
            [],
        )
    )

    return {
        action_function_name(
            action
        )
        for action in sequence
        if action_function_name(
            action
        )
    }


def surface_alignment(
    user_blueprint: dict[str, Any],
    pair: dict[str, Any],
) -> tuple[bool, str]:

    vector = pair[
        "injection_surface"
    ]

    vector_id = str(
        vector[
            "vector_id"
        ]
    )

    retrieval_channel = str(
        vector[
            "retrieval_channel"
        ]
    )

    expected_tools = (
        RETRIEVAL_TOOLS_BY_CHANNEL.get(
            retrieval_channel,
            set(),
        )
    )

    if not (
        referenced_tools(
            user_blueprint
        )
        &
        expected_tools
    ):
        return (
            False,
            "retrieval_channel_mismatch",
        )


    exact_object = (
        EXACT_OBJECT_BY_VECTOR_ID.get(
            vector_id
        )
    )

    if exact_object is None:
        return (
            True,
            "retrieval_channel_match",
        )


    prompt = str(
        user_blueprint[
            "structure"
        ].get(
            "prompt_or_goal",
            "",
        )
    )

    if exact_object not in prompt:
        return (
            False,
            "environment_object_mismatch",
        )


    return (
        True,
        "exact_environment_object_match",
    )


def action_arguments(
    action: dict[str, Any],
) -> Any:

    return (
        action.get(
            "args_expression"
        )
        or
        action.get(
            "args"
        )
    )


def actions_are_identical(
    first: dict[str, Any],
    second: dict[str, Any],
) -> bool:

    if (
        action_function_name(first)
        !=
        action_function_name(second)
    ):
        return False

    return (
        canonical_json(
            action_arguments(first)
        )
        ==
        canonical_json(
            action_arguments(second)
        )
    )


def blueprint_tier(
    blueprint: dict[str, Any],
) -> str:

    return str(
        blueprint[
            "structure"
        ].get(
            "curation",
            {},
        ).get(
            "quality_tier",
            "",
        )
    )


def candidate_change_type(
    current_user_id: str,
    current_attacker_id: str,
    candidate_user_id: str,
    candidate_attacker_id: str,
) -> str:

    user_changed = (
        current_user_id
        !=
        candidate_user_id
    )

    attacker_changed = (
        current_attacker_id
        !=
        candidate_attacker_id
    )

    if (
        user_changed
        and
        attacker_changed
    ):
        return "both_changed"

    if user_changed:
        return "user_only"

    if attacker_changed:
        return "attacker_only"

    return "unchanged"


def change_rank(
    change_type: str,
) -> int:

    return {
        "unchanged": 4,
        "user_only": 3,
        "attacker_only": 3,
        "both_changed": 1,
    }.get(
        change_type,
        0,
    )


def alignment_rank(
    alignment_type: str,
) -> int:

    return {
        "exact_environment_object_match": 2,
        "retrieval_channel_match": 1,
    }.get(
        alignment_type,
        0,
    )


def main() -> None:

    pairs = load_jsonl(
        PAIR_PATH
    )

    blueprints = load_jsonl(
        BLUEPRINT_PATH
    )


    if len(pairs) != (
        EXPECTED_PAIR_COUNT
    ):
        raise ValueError(
            f"Expected 100 pairs, found {len(pairs)}."
        )


    blueprint_by_id = {
        str(
            blueprint[
                "blueprint_id"
            ]
        ): blueprint
        for blueprint in blueprints
    }


    users_by_suite: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)

    attackers_by_suite: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)


    for blueprint in blueprints:

        suite = str(
            blueprint[
                "suite"
            ]
        )

        task_kind = str(
            blueprint[
                "structure"
            ][
                "task_kind"
            ]
        )

        if task_kind == "user_task":

            users_by_suite[
                suite
            ].append(
                blueprint
            )

        elif (
            task_kind
            ==
            "injection_task"
            and
            select_target_action(
                blueprint
            )
            is not None
        ):

            attackers_by_suite[
                suite
            ].append(
                blueprint
            )


    current_same_tool_pairs = [
        pair
        for pair in pairs
        if pair[
            "pairing_diagnostics"
        ][
            "same_tool_name_across_variants"
        ]
    ]


    if len(
        current_same_tool_pairs
    ) != (
        EXPECTED_CURRENT_SAME_TOOL_COUNT
    ):
        raise ValueError(
            "Expected four current same-tool pairs, "
            f"found {len(current_same_tool_pairs)}."
        )


    candidate_records: list[
        dict[str, Any]
    ] = []

    audit_rows: list[
        dict[str, Any]
    ] = []

    convertible_pair_ids: set[str] = set()

    suite_candidate_counts: Counter[
        str
    ] = Counter()

    tool_candidate_counts: Counter[
        str
    ] = Counter()

    best_change_type_counts: Counter[
        str
    ] = Counter()

    best_alignment_counts: Counter[
        str
    ] = Counter()


    for pair in pairs:

        pair_id = str(
            pair[
                "pair_id"
            ]
        )

        if pair[
            "pairing_diagnostics"
        ][
            "same_tool_name_across_variants"
        ]:
            continue


        suite = str(
            pair[
                "suite"
            ]
        )

        current_user_id = str(
            pair[
                "legitimate_context"
            ][
                "blueprint_id"
            ]
        )

        current_attacker_id = str(
            pair[
                "attacker_context"
            ][
                "blueprint_id"
            ]
        )


        pair_candidates: list[
            dict[str, Any]
        ] = []


        for user_blueprint in (
            users_by_suite[
                suite
            ]
        ):

            aligned, alignment_type = (
                surface_alignment(
                    user_blueprint,
                    pair,
                )
            )

            if not aligned:
                continue


            user_action = (
                select_target_action(
                    user_blueprint
                )
            )

            if user_action is None:
                continue


            for attacker_blueprint in (
                attackers_by_suite[
                    suite
                ]
            ):

                attacker_action = (
                    select_target_action(
                        attacker_blueprint
                    )
                )

                if attacker_action is None:
                    continue


                user_tool = (
                    action_function_name(
                        user_action
                    )
                )

                attacker_tool = (
                    action_function_name(
                        attacker_action
                    )
                )

                if user_tool != attacker_tool:
                    continue


                if actions_are_identical(
                    user_action,
                    attacker_action,
                ):
                    continue


                candidate_user_id = str(
                    user_blueprint[
                        "blueprint_id"
                    ]
                )

                candidate_attacker_id = str(
                    attacker_blueprint[
                        "blueprint_id"
                    ]
                )


                change_type = (
                    candidate_change_type(
                        current_user_id,
                        current_attacker_id,
                        candidate_user_id,
                        candidate_attacker_id,
                    )
                )


                score_tuple = (
                    alignment_rank(
                        alignment_type
                    ),

                    change_rank(
                        change_type
                    ),

                    (
                        1
                        if blueprint_tier(
                            user_blueprint
                        )
                        ==
                        "A"
                        else 0
                    ),

                    (
                        1
                        if blueprint_tier(
                            attacker_blueprint
                        )
                        ==
                        "A"
                        else 0
                    ),

                    IMPACT_RANK.get(
                        action_impact(
                            attacker_action
                        ),
                        0,
                    ),

                    IMPACT_RANK.get(
                        action_impact(
                            user_action
                        ),
                        0,
                    ),

                    stable_hash_number(
                        pair_id,
                        candidate_user_id,
                        candidate_attacker_id,
                    ),
                )


                pair_candidates.append(
                    {
                        "pair_id": pair_id,

                        "suite": suite,

                        "vector_id": (
                            pair[
                                "injection_surface"
                            ][
                                "vector_id"
                            ]
                        ),

                        "retrieval_channel": (
                            pair[
                                "injection_surface"
                            ][
                                "retrieval_channel"
                            ]
                        ),

                        "alignment_type": (
                            alignment_type
                        ),

                        "change_type": (
                            change_type
                        ),

                        "current_user_blueprint_id": (
                            current_user_id
                        ),

                        "candidate_user_blueprint_id": (
                            candidate_user_id
                        ),

                        "candidate_user_structure_id": (
                            user_blueprint[
                                "structure"
                            ][
                                "structure_id"
                            ]
                        ),

                        "candidate_user_goal": (
                            user_blueprint[
                                "structure"
                            ][
                                "prompt_or_goal"
                            ]
                        ),

                        "current_attacker_blueprint_id": (
                            current_attacker_id
                        ),

                        "candidate_attacker_blueprint_id": (
                            candidate_attacker_id
                        ),

                        "candidate_attacker_structure_id": (
                            attacker_blueprint[
                                "structure"
                            ][
                                "structure_id"
                            ]
                        ),

                        "candidate_attacker_goal": (
                            attacker_blueprint[
                                "structure"
                            ][
                                "prompt_or_goal"
                            ]
                        ),

                        "shared_tool_name": (
                            user_tool
                        ),

                        "authorized_action_impact": (
                            action_impact(
                                user_action
                            )
                        ),

                        "attacker_action_impact": (
                            action_impact(
                                attacker_action
                            )
                        ),

                        "authorized_args": (
                            action_arguments(
                                user_action
                            )
                        ),

                        "attacker_args": (
                            action_arguments(
                                attacker_action
                            )
                        ),

                        "candidate_score": list(
                            score_tuple[:-1]
                        ),

                        "_sort_key": (
                            score_tuple
                        ),
                    }
                )


        pair_candidates.sort(
            key=lambda record: (
                record[
                    "_sort_key"
                ]
            ),
            reverse=True,
        )


        if pair_candidates:

            convertible_pair_ids.add(
                pair_id
            )

            best = pair_candidates[0]

            best_change_type_counts[
                best[
                    "change_type"
                ]
            ] += 1

            best_alignment_counts[
                best[
                    "alignment_type"
                ]
            ] += 1


        for rank, candidate in enumerate(
            pair_candidates[
                :MAX_CANDIDATES_PER_PAIR
            ],
            start=1,
        ):

            candidate = dict(
                candidate
            )

            candidate.pop(
                "_sort_key"
            )

            candidate[
                "candidate_rank"
            ] = rank

            candidate_records.append(
                candidate
            )

            suite_candidate_counts[
                suite
            ] += 1

            tool_candidate_counts[
                candidate[
                    "shared_tool_name"
                ]
            ] += 1


            audit_rows.append(
                {
                    "pair_id": (
                        candidate[
                            "pair_id"
                        ]
                    ),

                    "candidate_rank": rank,

                    "suite": suite,

                    "vector_id": (
                        candidate[
                            "vector_id"
                        ]
                    ),

                    "alignment_type": (
                        candidate[
                            "alignment_type"
                        ]
                    ),

                    "change_type": (
                        candidate[
                            "change_type"
                        ]
                    ),

                    "candidate_user_structure_id": (
                        candidate[
                            "candidate_user_structure_id"
                        ]
                    ),

                    "candidate_attacker_structure_id": (
                        candidate[
                            "candidate_attacker_structure_id"
                        ]
                    ),

                    "shared_tool_name": (
                        candidate[
                            "shared_tool_name"
                        ]
                    ),

                    "authorized_action_impact": (
                        candidate[
                            "authorized_action_impact"
                        ]
                    ),

                    "attacker_action_impact": (
                        candidate[
                            "attacker_action_impact"
                        ]
                    ),

                    "candidate_user_goal": (
                        candidate[
                            "candidate_user_goal"
                        ]
                    ),

                    "candidate_attacker_goal": (
                        candidate[
                            "candidate_attacker_goal"
                        ]
                    ),
                }
            )


    different_tool_pair_count = (
        len(pairs)
        -
        len(current_same_tool_pairs)
    )

    convertible_count = len(
        convertible_pair_ids
    )

    nonconvertible_count = (
        different_tool_pair_count
        -
        convertible_count
    )


    write_jsonl(
        CANDIDATE_PATH,
        candidate_records,
    )

    write_csv(
        AUDIT_PATH,
        audit_rows,
    )


    report = {
        "analysis_version": "0.1",

        "pair_count": len(pairs),

        "current_same_tool_pair_count": (
            len(
                current_same_tool_pairs
            )
        ),

        "current_different_tool_pair_count": (
            different_tool_pair_count
        ),

        "structurally_convertible_pair_count": (
            convertible_count
        ),

        "structurally_nonconvertible_pair_count": (
            nonconvertible_count
        ),

        "maximum_theoretical_same_tool_pair_count": (
            len(current_same_tool_pairs)
            +
            convertible_count
        ),

        "stored_candidate_count": (
            len(candidate_records)
        ),

        "maximum_candidates_stored_per_pair": (
            MAX_CANDIDATES_PER_PAIR
        ),

        "best_candidate_change_type_counts": dict(
            best_change_type_counts
        ),

        "best_candidate_alignment_counts": dict(
            best_alignment_counts
        ),

        "stored_candidate_suite_counts": dict(
            suite_candidate_counts
        ),

        "stored_candidate_shared_tool_counts": dict(
            tool_candidate_counts
        ),

        "important_notes": [
            (
                "This is an opportunity analysis only. "
                "No pair-plan records were modified."
            ),
            (
                "Maximum theoretical count ignores global "
                "reuse caps and diversity constraints."
            ),
            (
                "Exact document-object matching is enforced "
                "for the three banking file vectors."
            ),
            (
                "Other vectors require retrieval-channel "
                "alignment at this stage."
            ),
            (
                "Candidates must be human-reviewed before "
                "being applied to the pair plan."
            ),
        ],
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
        "AGENTDOJO SAME-TOOL OPPORTUNITY ANALYSIS v0.1 COMPLETE"
    )
    print("=" * 80)

    print()
    print(
        "Pair plans:",
        len(pairs),
    )

    print(
        "Current same-tool pairs:",
        len(
            current_same_tool_pairs
        ),
    )

    print(
        "Current different-tool pairs:",
        different_tool_pair_count,
    )

    print()
    print(
        "Different-tool pairs with at least "
        "one valid same-tool candidate:",
        convertible_count,
    )

    print(
        "Different-tool pairs without a "
        "same-tool candidate:",
        nonconvertible_count,
    )

    print(
        "Maximum theoretical same-tool pairs:",
        (
            len(
                current_same_tool_pairs
            )
            +
            convertible_count
        ),
    )

    print()
    print(
        "Best-candidate change types:"
    )

    for change_type, count in sorted(
        best_change_type_counts.items()
    ):
        print(
            f"  {change_type}: {count}"
        )

    print()
    print(
        "Best-candidate alignment types:"
    )

    for alignment, count in sorted(
        best_alignment_counts.items()
    ):
        print(
            f"  {alignment}: {count}"
        )

    print()
    print(
        "Stored candidates by shared tool:"
    )

    for tool, count in sorted(
        tool_candidate_counts.items(),
        key=lambda item: (
            -item[1],
            item[0],
        ),
    ):
        print(
            f"  {tool}: {count}"
        )

    print()
    print(
        f"Candidate pool: {CANDIDATE_PATH}"
    )

    print(
        f"Audit CSV: {AUDIT_PATH}"
    )

    print(
        f"Report: {REPORT_PATH}"
    )

    print()
    print(
        "Pair plan modified: no"
    )

    print(
        "Runtime labels generated: 0"
    )


if __name__ == "__main__":
    main()

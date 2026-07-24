from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROCESSED_DIR = Path(
    "data/processed"
)

INTERIM_DIR = Path(
    "data/interim"
)

BLUEPRINT_PATH = (
    PROCESSED_DIR /
    "agentdojo_contextual_composition_blueprint_pool_v0.1.jsonl"
)

VECTOR_PATH = (
    PROCESSED_DIR /
    "agentdojo_curated_injection_vector_catalog_v0.1.jsonl"
)

PAIR_PLAN_PATH = (
    INTERIM_DIR /
    "agentdojo_contextual_pair_plan_v0.1.jsonl"
)

AUDIT_CSV_PATH = (
    INTERIM_DIR /
    "agentdojo_contextual_pair_plan_audit_v0.1.csv"
)

REPORT_PATH = (
    INTERIM_DIR /
    "agentdojo_contextual_pair_plan_v0.1_report.json"
)


PAIR_QUOTAS = {
    "banking": 20,
    "slack": 20,
    "travel": 25,
    "workspace": 35,
}

EXPECTED_BLUEPRINT_COUNT = 117
EXPECTED_USER_BLUEPRINT_COUNT = 82
EXPECTED_ATTACKER_BLUEPRINT_COUNT = 35
EXPECTED_EXPLICIT_ATTACKER_COUNT = 26
EXPECTED_VECTOR_COUNT = 39
EXPECTED_PAIR_COUNT = 100
EXPECTED_PLANNED_ROW_COUNT = 200


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


FORBIDDEN_KEYS = {
    "general_risk_label",
    "ml_risk_score",
    "risk_score",
    "policy_output",
    "runtime_decision",
}


def load_jsonl(
    path: Path,
) -> list[dict[str, Any]]:

    if not path.exists():
        raise FileNotFoundError(
            f"Missing file: {path}"
        )

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
                    f"Invalid JSONL in {path} "
                    f"at line {line_number}."
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
            f"Cannot write empty CSV: {path}"
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


def stable_hash(
    *values: Any,
) -> str:

    text = "||".join(
        str(value)
        for value in values
    )

    return hashlib.sha256(
        text.encode(
            "utf-8"
        )
    ).hexdigest()


def stable_hash_number(
    *values: Any,
) -> int:

    return int(
        stable_hash(
            *values
        )[:16],
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


def action_selection_score(
    action: dict[str, Any],
) -> tuple[int, int, int]:

    impact = action_impact(
        action
    )

    capability = action_capability(
        action
    )

    sequence_position = int(
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
        sequence_position,
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


def referenced_tool_names(
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


def surface_matches_user_workflow(
    user_blueprint: dict[str, Any],
    vector: dict[str, Any],
) -> bool:

    retrieval_channel = str(
        vector.get(
            "composition_metadata",
            {},
        ).get(
            "retrieval_channel",
            ""
        )
    )

    matching_tools = (
        RETRIEVAL_TOOLS_BY_CHANNEL.get(
            retrieval_channel,
            set(),
        )
    )

    return bool(
        referenced_tool_names(
            user_blueprint
        )
        &
        matching_tools
    )


def attacker_indicator_present(
    attacker_blueprint: dict[str, Any],
    attacker_action: dict[str, Any],
) -> bool:

    structure = attacker_blueprint.get(
        "structure",
        {},
    )

    searchable = (
        canonical_json(
            attacker_action
        )
        +
        " "
        +
        str(
            structure.get(
                "prompt_or_goal",
                ""
            )
        )
    ).lower()

    markers = {
        "_attacker",
        "attacker",
        "malicious",
        "exfiltrat",
        "unauthorized",
        "without asking",
        "without confirmation",
    }

    return any(
        marker in searchable
        for marker in markers
    )


def actions_are_identical(
    first: dict[str, Any],
    second: dict[str, Any],
) -> bool:

    if (
        action_function_name(
            first
        )
        !=
        action_function_name(
            second
        )
    ):
        return False

    first_args = (
        first.get(
            "args_expression"
        )
        or
        first.get(
            "args"
        )
    )

    second_args = (
        second.get(
            "args_expression"
        )
        or
        second.get(
            "args"
        )
    )

    return (
        canonical_json(
            first_args
        )
        ==
        canonical_json(
            second_args
        )
    )


def compact_action(
    action: dict[str, Any],
) -> dict[str, Any]:

    return {
        "sequence_position": (
            action.get(
                "sequence_position"
            )
        ),

        "function": action_function_name(
            action
        ),

        "args": action.get(
            "args"
        ),

        "args_expression": action.get(
            "args_expression"
        ),

        "placeholder_args": action.get(
            "placeholder_args"
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


def compact_vector(
    vector: dict[str, Any],
) -> dict[str, Any]:

    review = vector.get(
        "human_review",
        {},
    )

    composition = vector.get(
        "composition_metadata",
        {},
    )

    return {
        "vector_id": (
            vector[
                "vector_id"
            ]
        ),

        "description": (
            vector.get(
                "description"
            )
        ),

        "default_value": (
            vector.get(
                "default_value"
            )
        ),

        "surface_type": (
            review.get(
                "surface_type"
            )
        ),

        "source_type": (
            review.get(
                "source_type"
            )
        ),

        "trust_level": (
            review.get(
                "trust_level"
            )
        ),

        "retrieval_channel": (
            composition.get(
                "retrieval_channel"
            )
        ),

        "environment_locations": (
            vector.get(
                "locations",
                [],
            )
        ),
    }


def find_forbidden_keys(
    value: Any,
    path: str = "",
) -> list[str]:

    matches: list[str] = []

    if isinstance(
        value,
        dict,
    ):

        for key, child in value.items():

            child_path = (
                f"{path}.{key}"
                if path
                else key
            )

            if key in FORBIDDEN_KEYS:
                matches.append(
                    child_path
                )

            matches.extend(
                find_forbidden_keys(
                    child,
                    child_path,
                )
            )

    elif isinstance(
        value,
        list,
    ):

        for index, child in enumerate(
            value
        ):

            matches.extend(
                find_forbidden_keys(
                    child,
                    f"{path}[{index}]",
                )
            )

    return matches


def candidate_score(
    user_blueprint: dict[str, Any],
    attacker_blueprint: dict[str, Any],
    vector: dict[str, Any],
    user_action: dict[str, Any],
    attacker_action: dict[str, Any],
) -> int:

    score = 0

    if surface_matches_user_workflow(
        user_blueprint,
        vector,
    ):
        score += 40

    attacker_impact = IMPACT_RANK.get(
        action_impact(
            attacker_action
        ),
        0,
    )

    user_impact = IMPACT_RANK.get(
        action_impact(
            user_action
        ),
        0,
    )

    score += attacker_impact * 8
    score += user_impact * 4

    same_tool = (
        action_function_name(
            user_action
        )
        ==
        action_function_name(
            attacker_action
        )
    )

    if not same_tool:
        score += 10

    elif attacker_indicator_present(
        attacker_blueprint,
        attacker_action,
    ):
        score += 7

    else:
        score += 2

    user_tier = (
        user_blueprint[
            "structure"
        ].get(
            "curation",
            {},
        ).get(
            "quality_tier"
        )
    )

    attacker_tier = (
        attacker_blueprint[
            "structure"
        ].get(
            "curation",
            {},
        ).get(
            "quality_tier"
        )
    )

    if user_tier == "A":
        score += 3

    if attacker_tier == "A":
        score += 3

    return score


def main() -> None:

    blueprints = load_jsonl(
        BLUEPRINT_PATH
    )

    vectors = load_jsonl(
        VECTOR_PATH
    )


    if len(blueprints) != (
        EXPECTED_BLUEPRINT_COUNT
    ):
        raise ValueError(
            "Expected "
            f"{EXPECTED_BLUEPRINT_COUNT} blueprints, "
            f"found {len(blueprints)}."
        )

    if len(vectors) != (
        EXPECTED_VECTOR_COUNT
    ):
        raise ValueError(
            "Expected "
            f"{EXPECTED_VECTOR_COUNT} vectors, "
            f"found {len(vectors)}."
        )


    users_by_suite: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)

    attackers_by_suite: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)

    vectors_by_suite: dict[
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

        elif task_kind == "injection_task":
            attackers_by_suite[
                suite
            ].append(
                blueprint
            )

        else:
            raise ValueError(
                f"Unexpected task kind: {task_kind}"
            )


    for vector in vectors:

        vectors_by_suite[
            str(
                vector[
                    "suite"
                ]
            )
        ].append(
            vector
        )


    total_users = sum(
        len(records)
        for records
        in users_by_suite.values()
    )

    total_attackers = sum(
        len(records)
        for records
        in attackers_by_suite.values()
    )

    explicit_attackers = [
        blueprint
        for records
        in attackers_by_suite.values()
        for blueprint
        in records
        if select_target_action(
            blueprint
        )
        is not None
    ]


    if total_users != (
        EXPECTED_USER_BLUEPRINT_COUNT
    ):
        raise ValueError(
            f"Expected 82 user blueprints, found {total_users}."
        )

    if total_attackers != (
        EXPECTED_ATTACKER_BLUEPRINT_COUNT
    ):
        raise ValueError(
            f"Expected 35 attacker blueprints, found {total_attackers}."
        )

    if len(explicit_attackers) != (
        EXPECTED_EXPLICIT_ATTACKER_COUNT
    ):
        raise ValueError(
            "Expected 26 attacker structures with explicit "
            f"actions, found {len(explicit_attackers)}."
        )


    pair_records: list[
        dict[str, Any]
    ] = []

    audit_rows: list[
        dict[str, Any]
    ] = []

    suite_selected_counts: Counter[
        str
    ] = Counter()

    user_usage: Counter[
        str
    ] = Counter()

    attacker_usage: Counter[
        str
    ] = Counter()

    vector_usage: Counter[
        str
    ] = Counter()

    surface_match_count = 0
    same_tool_count = 0
    attacker_marker_count = 0

    selected_user_impacts: Counter[
        str
    ] = Counter()

    selected_attacker_impacts: Counter[
        str
    ] = Counter()


    for suite, quota in (
        PAIR_QUOTAS.items()
    ):

        users = sorted(
            users_by_suite[
                suite
            ],
            key=lambda record: (
                record[
                    "structure"
                ][
                    "structure_id"
                ]
            ),
        )

        attackers = sorted(
            [
                record
                for record
                in attackers_by_suite[
                    suite
                ]
                if select_target_action(
                    record
                )
                is not None
            ],
            key=lambda record: (
                record[
                    "structure"
                ][
                    "structure_id"
                ]
            ),
        )

        suite_vectors = sorted(
            vectors_by_suite[
                suite
            ],
            key=lambda record: (
                record[
                    "vector_id"
                ]
            ),
        )


        if not users:
            raise ValueError(
                f"No user structures for suite {suite}."
            )

        if not attackers:
            raise ValueError(
                f"No explicit attacker structures for suite {suite}."
            )

        if not suite_vectors:
            raise ValueError(
                f"No vectors for suite {suite}."
            )


        user_cap = (
            math.ceil(
                quota
                /
                len(users)
            )
            +
            1
        )

        attacker_cap = (
            math.ceil(
                quota
                /
                len(attackers)
            )
            +
            1
        )


        used_triples: set[
            tuple[str, str, str]
        ] = set()


        for pair_index in range(
            quota
        ):

            vector = suite_vectors[
                pair_index
                %
                len(
                    suite_vectors
                )
            ]

            vector_id = str(
                vector[
                    "vector_id"
                ]
            )

            candidates = []


            for user_blueprint in users:

                user_id = str(
                    user_blueprint[
                        "structure"
                    ][
                        "structure_id"
                    ]
                )

                if (
                    user_usage[
                        user_id
                    ]
                    >=
                    user_cap
                ):
                    continue


                user_action = select_target_action(
                    user_blueprint
                )

                if user_action is None:
                    continue


                for attacker_blueprint in attackers:

                    attacker_id = str(
                        attacker_blueprint[
                            "structure"
                        ][
                            "structure_id"
                        ]
                    )

                    if (
                        attacker_usage[
                            attacker_id
                        ]
                        >=
                        attacker_cap
                    ):
                        continue


                    attacker_action = select_target_action(
                        attacker_blueprint
                    )

                    if attacker_action is None:
                        continue


                    triple = (
                        user_id,
                        attacker_id,
                        vector_id,
                    )

                    if triple in used_triples:
                        continue


                    if actions_are_identical(
                        user_action,
                        attacker_action,
                    ):
                        continue


                    surface_match = (
                        surface_matches_user_workflow(
                            user_blueprint,
                            vector,
                        )
                    )

                    score = candidate_score(
                        user_blueprint,
                        attacker_blueprint,
                        vector,
                        user_action,
                        attacker_action,
                    )

                    fairness_score = (
                        -user_usage[
                            user_id
                        ],
                        -attacker_usage[
                            attacker_id
                        ],
                    )

                    deterministic_tiebreak = (
                        stable_hash_number(
                            suite,
                            user_id,
                            attacker_id,
                            vector_id,
                        )
                    )


                    candidates.append(
                        {
                            "user_blueprint": (
                                user_blueprint
                            ),

                            "attacker_blueprint": (
                                attacker_blueprint
                            ),

                            "vector": vector,

                            "user_action": (
                                user_action
                            ),

                            "attacker_action": (
                                attacker_action
                            ),

                            "surface_match": (
                                surface_match
                            ),

                            "score": score,

                            "fairness_score": (
                                fairness_score
                            ),

                            "tiebreak": (
                                deterministic_tiebreak
                            ),
                        }
                    )


            if not candidates:
                raise ValueError(
                    "Could not fill pairing quota for "
                    f"{suite} at index {pair_index}."
                )


            selected = max(
                candidates,
                key=lambda candidate: (
                    1
                    if candidate[
                        "surface_match"
                    ]
                    else 0,
                    candidate[
                        "fairness_score"
                    ][0],
                    candidate[
                        "fairness_score"
                    ][1],
                    candidate[
                        "score"
                    ],
                    candidate[
                        "tiebreak"
                    ],
                ),
            )


            user_blueprint = selected[
                "user_blueprint"
            ]

            attacker_blueprint = selected[
                "attacker_blueprint"
            ]

            user_action = selected[
                "user_action"
            ]

            attacker_action = selected[
                "attacker_action"
            ]


            user_id = str(
                user_blueprint[
                    "structure"
                ][
                    "structure_id"
                ]
            )

            attacker_id = str(
                attacker_blueprint[
                    "structure"
                ][
                    "structure_id"
                ]
            )


            used_triples.add(
                (
                    user_id,
                    attacker_id,
                    vector_id,
                )
            )

            user_usage[
                user_id
            ] += 1

            attacker_usage[
                attacker_id
            ] += 1

            vector_usage[
                f"{suite}:{vector_id}"
            ] += 1


            pair_number = (
                len(pair_records)
                +
                1
            )

            pair_id = (
                f"agentdojo_pair_"
                f"{pair_number:03d}"
            )

            split_group_id = (
                f"agentdojo_group_"
                f"{pair_number:03d}"
            )


            same_tool = (
                action_function_name(
                    user_action
                )
                ==
                action_function_name(
                    attacker_action
                )
            )

            marker_present = (
                attacker_indicator_present(
                    attacker_blueprint,
                    attacker_action,
                )
            )


            record = {
                "pair_id": pair_id,

                "pair_plan_version": (
                    "0.1"
                ),

                "scenario_source": (
                    "agentdojo"
                ),

                "suite": suite,

                "session_group_id": (
                    split_group_id
                ),

                "legitimate_context": (
                    compact_structure(
                        user_blueprint
                    )
                ),

                "attacker_context": (
                    compact_structure(
                        attacker_blueprint
                    )
                ),

                "injection_surface": (
                    compact_vector(
                        vector
                    )
                ),

                "shared_context_plan": {
                    "user_goal_source": (
                        "legitimate_context."
                        "prompt_or_goal"
                    ),

                    "embedded_payload_source": (
                        "attacker_context."
                        "prompt_or_goal"
                    ),

                    "surface_source": (
                        "injection_surface"
                    ),

                    "source_trust_level": (
                        "untrusted"
                    ),

                    "same_payload_for_both_variants": (
                        True
                    ),

                    "same_user_goal_for_both_variants": (
                        True
                    ),

                    "same_policy_context_for_both_variants": (
                        True
                    ),
                },

                "selected_actions": {
                    "authorized_user_action": (
                        compact_action(
                            user_action
                        )
                    ),

                    "attacker_target_action": (
                        compact_action(
                            attacker_action
                        )
                    ),
                },

                "planned_variants": [
                    {
                        "variant_id": (
                            f"{pair_id}::safe"
                        ),

                        "expected_contextual_class": (
                            "contextually_safe"
                        ),

                        "attempted_action_source": (
                            "authorized_user_action"
                        ),

                        "authorization_alignment": (
                            "aligned_with_explicit_user_goal"
                        ),

                        "important_note": (
                            "The untrusted injected payload "
                            "is present but is not followed."
                        ),
                    },

                    {
                        "variant_id": (
                            f"{pair_id}::risky"
                        ),

                        "expected_contextual_class": (
                            "contextually_risky"
                        ),

                        "attempted_action_source": (
                            "attacker_target_action"
                        ),

                        "authorization_alignment": (
                            "conflicts_with_explicit_user_goal"
                        ),

                        "important_note": (
                            "The attempted action follows "
                            "the untrusted injected goal."
                        ),
                    },
                ],

                "pairing_diagnostics": {
                    "surface_matches_legitimate_workflow": (
                        selected[
                            "surface_match"
                        ]
                    ),

                    "same_tool_name_across_variants": (
                        same_tool
                    ),

                    "attacker_marker_present": (
                        marker_present
                    ),

                    "pairing_score": (
                        selected[
                            "score"
                        ]
                    ),
                },

                "review": {
                    "status": (
                        "pending_human_review"
                    ),

                    "include_for_smoke_test": (
                        None
                    ),

                    "review_note": (
                        None
                    ),
                },

                "composition_state": {
                    "status": (
                        "pair_plan_only"
                    ),

                    "runtime_rows_created": (
                        False
                    ),

                    "planned_runtime_row_count": (
                        2
                    ),

                    "important_note": (
                        "No runtime label is stored in "
                        "this planning artifact. Numeric "
                        "labels may be assigned only after "
                        "the complete action.attempt rows "
                        "are composed and reviewed."
                    ),
                },
            }


            forbidden_paths = find_forbidden_keys(
                record
            )

            if forbidden_paths:
                raise ValueError(
                    f"Forbidden keys in {pair_id}: "
                    f"{forbidden_paths}"
                )


            pair_records.append(
                record
            )


            audit_rows.append(
                {
                    "pair_id": pair_id,
                    "session_group_id": (
                        split_group_id
                    ),
                    "suite": suite,
                    "user_structure_id": (
                        user_id
                    ),
                    "user_scenario_family": (
                        user_blueprint[
                            "structure"
                        ].get(
                            "curation",
                            {},
                        ).get(
                            "scenario_family",
                            "",
                        )
                    ),
                    "attacker_structure_id": (
                        attacker_id
                    ),
                    "attacker_scenario_family": (
                        attacker_blueprint[
                            "structure"
                        ].get(
                            "curation",
                            {},
                        ).get(
                            "scenario_family",
                            "",
                        )
                    ),
                    "vector_id": (
                        vector_id
                    ),
                    "surface_type": (
                        vector.get(
                            "human_review",
                            {},
                        ).get(
                            "surface_type",
                            "",
                        )
                    ),
                    "retrieval_channel": (
                        vector.get(
                            "composition_metadata",
                            {},
                        ).get(
                            "retrieval_channel",
                            "",
                        )
                    ),
                    "surface_matches_workflow": (
                        selected[
                            "surface_match"
                        ]
                    ),
                    "authorized_action": (
                        action_function_name(
                            user_action
                        )
                    ),
                    "authorized_action_impact": (
                        action_impact(
                            user_action
                        )
                    ),
                    "attacker_action": (
                        action_function_name(
                            attacker_action
                        )
                    ),
                    "attacker_action_impact": (
                        action_impact(
                            attacker_action
                        )
                    ),
                    "same_tool_name": (
                        same_tool
                    ),
                    "attacker_marker_present": (
                        marker_present
                    ),
                    "pairing_score": (
                        selected[
                            "score"
                        ]
                    ),
                    "planned_variants": 2,
                    "review_status": (
                        "pending_human_review"
                    ),
                    "include_for_smoke_test": "",
                    "review_note": "",
                }
            )


            suite_selected_counts[
                suite
            ] += 1

            if selected[
                "surface_match"
            ]:
                surface_match_count += 1

            if same_tool:
                same_tool_count += 1

            if marker_present:
                attacker_marker_count += 1

            selected_user_impacts[
                action_impact(
                    user_action
                )
            ] += 1

            selected_attacker_impacts[
                action_impact(
                    attacker_action
                )
            ] += 1


    # --------------------------------------------------------
    # Final validation
    # --------------------------------------------------------

    if len(pair_records) != (
        EXPECTED_PAIR_COUNT
    ):
        raise ValueError(
            "Expected "
            f"{EXPECTED_PAIR_COUNT} pair plans, "
            f"found {len(pair_records)}."
        )

    if dict(
        suite_selected_counts
    ) != PAIR_QUOTAS:
        raise ValueError(
            "Unexpected suite pair counts.\n"
            f"Expected: {PAIR_QUOTAS}\n"
            f"Found: "
            f"{dict(suite_selected_counts)}"
        )


    planned_row_count = sum(
        record[
            "composition_state"
        ][
            "planned_runtime_row_count"
        ]
        for record in pair_records
    )

    if planned_row_count != (
        EXPECTED_PLANNED_ROW_COUNT
    ):
        raise ValueError(
            "Expected "
            f"{EXPECTED_PLANNED_ROW_COUNT} "
            "planned rows, found "
            f"{planned_row_count}."
        )


    pair_ids = [
        record[
            "pair_id"
        ]
        for record in pair_records
    ]

    if len(pair_ids) != len(
        set(pair_ids)
    ):
        raise ValueError(
            "Duplicate pair_id detected."
        )


    # --------------------------------------------------------
    # Write outputs
    # --------------------------------------------------------

    write_jsonl(
        PAIR_PLAN_PATH,
        pair_records,
    )

    write_csv(
        AUDIT_CSV_PATH,
        audit_rows,
    )


    report = {
        "dataset": "agentdojo",

        "pair_plan_version": (
            "0.1"
        ),

        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "pair_count": (
            len(pair_records)
        ),

        "planned_runtime_row_count": (
            planned_row_count
        ),

        "planned_variant_counts": {
            "contextually_safe": 100,
            "contextually_risky": 100,
        },

        "suite_pair_counts": dict(
            suite_selected_counts
        ),

        "available_user_structure_counts": {
            suite: len(
                records
            )
            for suite, records
            in sorted(
                users_by_suite.items()
            )
        },

        "available_attacker_structure_counts": {
            suite: len(
                records
            )
            for suite, records
            in sorted(
                attackers_by_suite.items()
            )
        },

        "explicit_attacker_structure_counts": {
            suite: sum(
                1
                for record in records
                if select_target_action(
                    record
                )
                is not None
            )
            for suite, records
            in sorted(
                attackers_by_suite.items()
            )
        },

        "surface_match_count": (
            surface_match_count
        ),

        "surface_mismatch_count": (
            len(pair_records)
            -
            surface_match_count
        ),

        "same_tool_pair_count": (
            same_tool_count
        ),

        "different_tool_pair_count": (
            len(pair_records)
            -
            same_tool_count
        ),

        "attacker_marker_present_count": (
            attacker_marker_count
        ),

        "selected_authorized_action_impacts": dict(
            selected_user_impacts
        ),

        "selected_attacker_action_impacts": dict(
            selected_attacker_impacts
        ),

        "unique_user_structure_count": (
            len(user_usage)
        ),

        "unique_attacker_structure_count": (
            len(attacker_usage)
        ),

        "unique_vector_count": (
            len(vector_usage)
        ),

        "maximum_user_structure_reuse": (
            max(
                user_usage.values()
            )
        ),

        "maximum_attacker_structure_reuse": (
            max(
                attacker_usage.values()
            )
        ),

        "maximum_vector_reuse": (
            max(
                vector_usage.values()
            )
        ),

        "runtime_label_count": 0,

        "important_notes": [
            (
                "Each plan is intended to generate one "
                "safe and one risky action.attempt row."
            ),
            (
                "Both variants preserve the same user "
                "goal, injection surface, attacker "
                "payload, and policy context."
            ),
            (
                "The attempted action and authorization "
                "alignment differ between the variants."
            ),
            (
                "The two variants share session_group_id "
                "and must remain in the same train, "
                "validation, or test split."
            ),
            (
                "No numeric runtime label is stored in "
                "this pair-planning artifact."
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
        "AGENTDOJO CONTEXTUAL PAIR PLAN v0.1 CREATED"
    )
    print("=" * 80)

    print()
    print(
        "Pair plans:",
        len(pair_records),
    )

    print(
        "Planned runtime rows:",
        planned_row_count,
    )

    print()
    print(
        "Suite pair counts:"
    )

    for suite, count in sorted(
        suite_selected_counts.items()
    ):
        print(
            f"  {suite}: {count}"
        )

    print()
    print(
        "Source/task inventory:"
    )

    print(
        "  user structures:",
        total_users,
    )

    print(
        "  attacker structures:",
        total_attackers,
    )

    print(
        "  attackers with explicit actions:",
        len(explicit_attackers),
    )

    print()
    print(
        "Pairing diagnostics:"
    )

    print(
        "  surface/workflow matches:",
        surface_match_count,
    )

    print(
        "  surface/workflow mismatches:",
        (
            len(pair_records)
            -
            surface_match_count
        ),
    )

    print(
        "  same-tool minimal pairs:",
        same_tool_count,
    )

    print(
        "  different-tool pairs:",
        (
            len(pair_records)
            -
            same_tool_count
        ),
    )

    print(
        "  attacker markers present:",
        attacker_marker_count,
    )

    print()
    print(
        "Selected authorized action impacts:"
    )

    for impact, count in sorted(
        selected_user_impacts.items()
    ):
        print(
            f"  {impact}: {count}"
        )

    print()
    print(
        "Selected attacker action impacts:"
    )

    for impact, count in sorted(
        selected_attacker_impacts.items()
    ):
        print(
            f"  {impact}: {count}"
        )

    print()
    print(
        "Unique structures/surfaces used:"
    )

    print(
        "  users:",
        len(user_usage),
    )

    print(
        "  attackers:",
        len(attacker_usage),
    )

    print(
        "  vectors:",
        len(vector_usage),
    )

    print()
    print(
        "Runtime labels generated: 0"
    )

    print()
    print(
        f"Pair plan: {PAIR_PLAN_PATH}"
    )

    print(
        f"Audit CSV: {AUDIT_CSV_PATH}"
    )

    print(
        f"Report: {REPORT_PATH}"
    )


if __name__ == "__main__":
    main()

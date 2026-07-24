from __future__ import annotations

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

REPORT_PATH = Path(
    "data/interim/"
    "agentdojo_contextual_pair_plan_v0.1_report.json"
)

BACKUP_PATH = Path(
    "data/interim/"
    "agentdojo_contextual_pair_plan_v0.1_"
    "pre_duplicate_semantic_repair.jsonl"
)


REPAIRS = {
    "agentdojo_pair_008": {
        "expected_vector": (
            "injection_landloard_notice"
        ),

        "user_structure_id": (
            "agentdojo_banking_user_task_002"
        ),

        "attacker_structure_id": None,

        "source_locator": (
            "landlord-notices.txt"
        ),

        "binding_type": (
            "exact_document_reference"
        ),

        "reason": (
            "The landlord-notice injection must be paired "
            "with a legitimate workflow that reads "
            "landlord-notices.txt."
        ),
    },

    "agentdojo_pair_012": {
        "expected_vector": (
            "injection_landloard_notice"
        ),

        "user_structure_id": (
            "agentdojo_banking_user_task_012"
        ),

        "attacker_structure_id": None,

        "source_locator": (
            "landlord-notices.txt"
        ),

        "binding_type": (
            "exact_document_reference"
        ),

        "reason": (
            "The landlord-notice injection must be paired "
            "with the legitimate task that explicitly reads "
            "landlord-notices.txt."
        ),
    },

    "agentdojo_pair_028": {
        "expected_vector": (
            "injection_phishing_1"
        ),

        "user_structure_id": (
            "agentdojo_slack_user_task_000"
        ),

        "attacker_structure_id": None,

        "source_locator": (
            "www.true-informations.com"
        ),

        "binding_type": (
            "parameterized_web_url_binding"
        ),

        "reason": (
            "The external webpage injection is bound to the "
            "generic legitimate webpage-reading task, with "
            "its URL parameter set to the injected webpage."
        ),
    },

    "agentdojo_pair_039": {
        "expected_vector": (
            "injection_dora_0"
        ),

        "user_structure_id": (
            "agentdojo_slack_user_task_000"
        ),

        "attacker_structure_id": (
            "agentdojo_slack_injection_task_002"
        ),

        "source_locator": (
            "www.dora-website.com"
        ),

        "binding_type": (
            "parameterized_web_url_binding"
        ),

        "reason": (
            "Dora's webpage injection is bound to the generic "
            "webpage-reading task. A different attacker goal "
            "prevents reproduction of pair_028."
        ),
    },
}


IMPACT_RANK = {
    "low": 1,
    "medium": 2,
    "high": 3,
}


WRITE_CAPABILITIES = {
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


def function_name(
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


def action_metadata(
    action: dict[str, Any],
    key: str,
) -> str:

    return str(
        action.get(
            "tool_metadata",
            {},
        ).get(
            key,
            "",
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
            "Blueprint has no explicit action sequence: "
            f"{blueprint['blueprint_id']}"
        )

    def score(
        action: dict[str, Any],
    ) -> tuple[int, int, int]:

        impact = action_metadata(
            action,
            "action_impact",
        )

        capability = action_metadata(
            action,
            "capability_class",
        )

        return (
            IMPACT_RANK.get(
                impact,
                0,
            ),

            (
                1
                if capability
                in WRITE_CAPABILITIES
                else 0
            ),

            int(
                action.get(
                    "sequence_position",
                    0,
                )
                or 0
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
        "blueprint_id": blueprint[
            "blueprint_id"
        ],

        "structure_id": structure[
            "structure_id"
        ],

        "task_kind": structure[
            "task_kind"
        ],

        "structure_role": structure[
            "structure_role"
        ],

        "prompt_or_goal": structure[
            "prompt_or_goal"
        ],

        "scenario_family": curation.get(
            "scenario_family"
        ),

        "quality_tier": curation.get(
            "quality_tier"
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
        "sequence_position": action.get(
            "sequence_position"
        ),

        "function": function_name(
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

        "placeholder_args_expression": action.get(
            "placeholder_args_expression"
        ),

        "capability_class": action_metadata(
            action,
            "capability_class",
        ),

        "action_impact": action_metadata(
            action,
            "action_impact",
        ),
    }


def canonical_action(
    action: dict[str, Any],
) -> str:

    value = (
        action.get(
            "args_expression"
        )
        or
        action.get(
            "args"
        )
    )

    return json.dumps(
        {
            "function": function_name(
                action
            ),
            "args": value,
        },
        sort_keys=True,
        ensure_ascii=False,
    )


def attacker_marker_present(
    blueprint: dict[str, Any],
    action: dict[str, Any],
) -> bool:

    text = (
        str(
            blueprint[
                "structure"
            ].get(
                "prompt_or_goal",
                "",
            )
        )
        +
        " "
        +
        json.dumps(
            action,
            ensure_ascii=False,
        )
    ).lower()

    markers = {
        "_attacker",
        "attacker",
        "phishing",
        "without asking",
        "security code",
        "_recipient",
    }

    return any(
        marker in text
        for marker in markers
    )


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
            risky_action.get(
                "action_impact",
                "",
            ),
            0,
        )
        * 8
    )

    score += (
        IMPACT_RANK.get(
            safe_action.get(
                "action_impact",
                "",
            ),
            0,
        )
        * 4
    )

    if (
        safe_action[
            "function"
        ]
        ==
        risky_action[
            "function"
        ]
    ):
        score += (
            7
            if pair[
                "pairing_diagnostics"
            ].get(
                "attacker_marker_present",
                False,
            )
            else 2
        )

    else:
        score += 10

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

    if not BACKUP_PATH.exists():
        shutil.copy2(
            PAIR_PATH,
            BACKUP_PATH,
        )


    blueprint_by_id = {
        str(
            blueprint[
                "blueprint_id"
            ]
        ): blueprint
        for blueprint in blueprints
    }

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


    repaired_at = datetime.now(
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


        actual_vector = (
            pair[
                "injection_surface"
            ][
                "vector_id"
            ]
        )

        if (
            actual_vector
            !=
            repair[
                "expected_vector"
            ]
        ):
            raise ValueError(
                f"Unexpected vector for {pair_id}: "
                f"{actual_vector}"
            )


        user_blueprint = (
            blueprint_by_structure_id.get(
                repair[
                    "user_structure_id"
                ]
            )
        )

        if user_blueprint is None:
            raise ValueError(
                "Missing user blueprint: "
                f"{repair['user_structure_id']}"
            )


        attacker_structure_id = (
            repair[
                "attacker_structure_id"
            ]
        )

        if attacker_structure_id is None:

            current_attacker_blueprint_id = (
                pair[
                    "attacker_context"
                ][
                    "blueprint_id"
                ]
            )

            attacker_blueprint = (
                blueprint_by_id.get(
                    current_attacker_blueprint_id
                )
            )

        else:

            attacker_blueprint = (
                blueprint_by_structure_id.get(
                    attacker_structure_id
                )
            )


        if attacker_blueprint is None:
            raise ValueError(
                f"Missing attacker blueprint for {pair_id}."
            )


        if (
            user_blueprint[
                "suite"
            ]
            !=
            pair[
                "suite"
            ]
            or
            attacker_blueprint[
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


        user_goal = str(
            user_blueprint[
                "structure"
            ][
                "prompt_or_goal"
            ]
        )

        locator = repair[
            "source_locator"
        ]


        if (
            repair[
                "binding_type"
            ]
            ==
            "exact_document_reference"
            and
            locator not in user_goal
        ):
            raise ValueError(
                f"{pair_id} user goal does not "
                f"reference {locator}."
            )


        authorized_action = (
            select_target_action(
                user_blueprint
            )
        )

        attacker_action = (
            select_target_action(
                attacker_blueprint
            )
        )


        if (
            canonical_action(
                authorized_action
            )
            ==
            canonical_action(
                attacker_action
            )
        ):
            raise ValueError(
                f"{pair_id} actions became identical."
            )


        previous_user = (
            pair[
                "legitimate_context"
            ][
                "structure_id"
            ]
        )

        previous_attacker = (
            pair[
                "attacker_context"
            ][
                "structure_id"
            ]
        )


        pair[
            "legitimate_context"
        ] = compact_structure(
            user_blueprint
        )

        pair[
            "attacker_context"
        ] = compact_structure(
            attacker_blueprint
        )

        pair[
            "selected_actions"
        ][
            "authorized_user_action"
        ] = compact_action(
            authorized_action
        )

        pair[
            "selected_actions"
        ][
            "attacker_target_action"
        ] = compact_action(
            attacker_action
        )


        pair[
            "injection_surface"
        ][
            "source_locator"
        ] = locator


        pair[
            "context_bindings"
        ] = {
            "retrieved_object_locator": (
                locator
            ),

            "binding_type": repair[
                "binding_type"
            ],

            "binding_source": (
                "human_semantic_repair"
            ),

            "binding_status": (
                "confirmed"
            ),

            "important_note": (
                "The legitimate task's document or URL "
                "parameter is bound to this concrete "
                "environment object."
            ),
        }


        safe_function = function_name(
            authorized_action
        )

        risky_function = function_name(
            attacker_action
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
        ] = locator

        pair[
            "pairing_diagnostics"
        ][
            "same_tool_name_across_variants"
        ] = (
            safe_function
            ==
            risky_function
        )

        pair[
            "pairing_diagnostics"
        ][
            "attacker_marker_present"
        ] = attacker_marker_present(
            attacker_blueprint,
            attacker_action,
        )

        pair[
            "pairing_diagnostics"
        ][
            "pairing_score"
        ] = compute_pairing_score(
            pair
        )


        pair.setdefault(
            "repair_history",
            [],
        ).append(
            {
                "repair_version": (
                    "duplicate_semantic_repair_v0.1"
                ),

                "repaired_at": repaired_at,

                "reason": repair[
                    "reason"
                ],

                "vector_id": actual_vector,

                "source_locator": locator,

                "previous_user_structure_id": (
                    previous_user
                ),

                "replacement_user_structure_id": (
                    repair[
                        "user_structure_id"
                    ]
                ),

                "previous_attacker_structure_id": (
                    previous_attacker
                ),

                "replacement_attacker_structure_id": (
                    attacker_blueprint[
                        "structure"
                    ][
                        "structure_id"
                    ]
                ),
            }
        )


    # --------------------------------------------------------
    # Global validation
    # --------------------------------------------------------

    if any(
        not pair[
            "pairing_diagnostics"
        ][
            "surface_matches_legitimate_workflow"
        ]
        for pair in pairs
    ):
        raise ValueError(
            "A surface/workflow mismatch remains."
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

    if same_tool_count != 17:
        raise ValueError(
            "Expected 17 same-tool pairs, "
            f"found {same_tool_count}."
        )


    triples = [
        (
            pair[
                "legitimate_context"
            ][
                "blueprint_id"
            ],

            pair[
                "attacker_context"
            ][
                "blueprint_id"
            ],

            pair[
                "injection_surface"
            ][
                "vector_id"
            ],
        )
        for pair in pairs
    ]

    duplicate_triples = [
        triple
        for triple, count in Counter(
            triples
        ).items()
        if count > 1
    ]

    if duplicate_triples:
        raise ValueError(
            "Duplicate composition triples remain: "
            f"{duplicate_triples}"
        )


    user_usage = Counter(
        pair[
            "legitimate_context"
        ][
            "structure_id"
        ]
        for pair in pairs
    )

    attacker_usage = Counter(
        pair[
            "attacker_context"
        ][
            "structure_id"
        ]
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


    report = json.loads(
        REPORT_PATH.read_text(
            encoding="utf-8"
        )
    )

    report[
        "duplicate_semantic_repair_version"
    ] = "0.1"

    report[
        "duplicate_semantic_repair_timestamp"
    ] = repaired_at

    report[
        "duplicate_semantic_repaired_pair_count"
    ] = len(
        REPAIRS
    )

    report[
        "duplicate_semantic_repaired_pair_ids"
    ] = sorted(
        REPAIRS
    )

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
        "surface_match_count"
    ] = 100

    report[
        "surface_mismatch_count"
    ] = 0

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
        "AGENTDOJO DUPLICATE-PAIR SEMANTIC "
        "REPAIR v0.1 APPLIED"
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
            f"{repair['expected_vector']} → "
            f"{pair['legitimate_context']['structure_id']} "
            f"+ "
            f"{pair['attacker_context']['structure_id']} "
            f"→ {repair['source_locator']}"
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
        "Same-tool pairs:",
        same_tool_count,
    )

    print(
        "Duplicate composition triples:",
        0,
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
        "Runtime labels generated: 0"
    )

    print()
    print(
        f"Backup: {BACKUP_PATH}"
    )

    print(
        f"Updated pair plan: {PAIR_PATH}"
    )


if __name__ == "__main__":
    main()

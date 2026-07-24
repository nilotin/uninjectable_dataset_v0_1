from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


INTERIM_DIR = Path("data/interim")
PROCESSED_DIR = Path("data/processed")


REVISION_QUEUE_PATH = (
    INTERIM_DIR
    / "agentdojo_action_attempt_revision_queue_v0.1.1.csv"
)

PAIR_PLAN_PATH = (
    INTERIM_DIR
    / "agentdojo_contextual_pair_plan_v0.1.jsonl"
)

BLUEPRINT_PATH = (
    PROCESSED_DIR
    / "agentdojo_contextual_composition_blueprint_pool_v0.1.jsonl"
)

DOSSIER_PATH = (
    INTERIM_DIR
    / "agentdojo_action_attempt_p1_repair_dossier_v0.1.1.jsonl"
)

REPORT_PATH = (
    INTERIM_DIR
    / "agentdojo_action_attempt_p1_repair_dossier_v0.1.1_report.json"
)


EXPECTED_P1_PAIR_IDS = {
    "agentdojo_pair_016",
    "agentdojo_pair_031",
    "agentdojo_pair_040",
    "agentdojo_pair_091",
    "agentdojo_pair_095",
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
    "private_communication_read_with_state_change",
    "state_changing_write",
}


STOPWORDS = {
    "a",
    "an",
    "and",
    "at",
    "be",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "please",
    "the",
    "to",
    "with",
    "you",
    "your",
}


def load_jsonl(
    path: Path,
) -> list[dict[str, Any]]:

    if not path.exists():
        raise FileNotFoundError(
            f"Missing JSONL file: {path}"
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
                    f"Invalid JSONL in {path}, "
                    f"line {line_number}."
                ) from error

    return records


def load_csv(
    path: Path,
) -> list[dict[str, str]]:

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

        return list(reader)


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


def canonical_json(
    value: Any,
) -> str:

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def normalize_function_name(
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
        action.get(
            "tool_name"
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
            key
        )
        or
        action.get(
            key
        )
        or
        ""
    )


def action_args(
    action: dict[str, Any],
) -> Any:

    if action.get(
        "args"
    ) is not None:
        return action.get(
            "args"
        )

    return action.get(
        "args_expression"
    )


def compact_action(
    action: dict[str, Any],
) -> dict[str, Any]:

    return {
        "tool_name": normalize_function_name(
            action
        ),

        "args": action_args(
            action
        ),

        "capability_class": action_metadata(
            action,
            "capability_class",
        ),

        "action_impact": action_metadata(
            action,
            "action_impact",
        ),

        "sequence_position": action.get(
            "sequence_position"
        ),
    }


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
                if capability in WRITE_CAPABILITIES
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


def is_user_blueprint(
    blueprint: dict[str, Any],
) -> bool:

    structure_id = str(
        blueprint[
            "structure"
        ][
            "structure_id"
        ]
    )

    role = str(
        blueprint[
            "structure"
        ].get(
            "structure_role",
            "",
        )
    ).lower()

    return (
        "_user_task_" in structure_id
        or
        "legitimate" in role
        or
        role == "user_task"
    )


def is_attacker_blueprint(
    blueprint: dict[str, Any],
) -> bool:

    structure_id = str(
        blueprint[
            "structure"
        ][
            "structure_id"
        ]
    )

    role = str(
        blueprint[
            "structure"
        ].get(
            "structure_role",
            "",
        )
    ).lower()

    return (
        "_injection_task_" in structure_id
        or
        "attacker" in role
        or
        "injection" in role
    )


def tokenize(
    value: Any,
) -> set[str]:

    if value is None:
        return set()

    if not isinstance(
        value,
        str,
    ):
        value = canonical_json(
            value
        )

    tokens = {
        token
        for token in re.findall(
            r"[a-z0-9]+",
            value.lower(),
        )
        if (
            len(token) >= 3
            and
            token not in STOPWORDS
        )
    }

    return tokens


def lexical_hint_score(
    context: Any,
    candidate: Any,
) -> int:

    context_tokens = tokenize(
        context
    )

    candidate_tokens = tokenize(
        candidate
    )

    return len(
        context_tokens
        &
        candidate_tokens
    )


def short_text(
    value: Any,
    max_chars: int = 500,
) -> str:

    if value is None:
        return ""

    if isinstance(
        value,
        str,
    ):
        text = value
    else:
        text = canonical_json(
            value
        )

    text = text.replace(
        "\n",
        "\\n",
    )

    if len(text) <= max_chars:
        return text

    return (
        text[:max_chars]
        +
        "... [TRUNCATED]"
    )


def pair_number(
    pair_id: str,
) -> int:

    match = re.search(
        r"(\d+)$",
        pair_id,
    )

    if match is None:
        raise ValueError(
            f"Could not parse pair ID: {pair_id}"
        )

    return int(
        match.group(1)
    )


def main() -> None:

    revision_rows = load_csv(
        REVISION_QUEUE_PATH
    )

    pairs = load_jsonl(
        PAIR_PLAN_PATH
    )

    blueprints = load_jsonl(
        BLUEPRINT_PATH
    )


    p1_rows = [
        row
        for row in revision_rows
        if row[
            "repair_priority"
        ] == "P1"
    ]


    p1_pair_ids = {
        row[
            "pair_id"
        ]
        for row in p1_rows
    }


    if p1_pair_ids != EXPECTED_P1_PAIR_IDS:
        raise ValueError(
            "Unexpected P1 pair inventory.\n"
            f"Expected: {sorted(EXPECTED_P1_PAIR_IDS)}\n"
            f"Found: {sorted(p1_pair_ids)}"
        )


    pair_by_id = {
        str(
            pair[
                "pair_id"
            ]
        ): pair
        for pair in pairs
    }


    user_blueprints = [
        blueprint
        for blueprint in blueprints
        if is_user_blueprint(
            blueprint
        )
    ]

    attacker_blueprints = [
        blueprint
        for blueprint in blueprints
        if is_attacker_blueprint(
            blueprint
        )
    ]


    vector_catalog: dict[
        tuple[str, str],
        dict[str, Any],
    ] = {}

    vector_pair_ids: dict[
        tuple[str, str],
        list[str],
    ] = defaultdict(list)


    for pair in pairs:

        suite = str(
            pair[
                "suite"
            ]
        )

        surface = pair[
            "injection_surface"
        ]

        vector_id = str(
            surface[
                "vector_id"
            ]
        )

        key = (
            suite,
            vector_id,
        )

        vector_pair_ids[
            key
        ].append(
            str(
                pair[
                    "pair_id"
                ]
            )
        )

        if key not in vector_catalog:

            vector_catalog[
                key
            ] = {
                "suite": suite,

                "vector_id": vector_id,

                "surface_type": surface.get(
                    "surface_type"
                ),

                "source_type": surface.get(
                    "source_type"
                ),

                "retrieval_channel": surface.get(
                    "retrieval_channel"
                ),

                "source_locator": surface.get(
                    "source_locator"
                ),

                "environment_locations": surface.get(
                    "environment_locations",
                    [],
                ),

                "default_value": surface.get(
                    "default_value"
                ),

                "trust_level": surface.get(
                    "trust_level"
                ),
            }


    dossier_records: list[
        dict[str, Any]
    ] = []


    for review_row in sorted(
        p1_rows,
        key=lambda row: pair_number(
            row[
                "pair_id"
            ]
        ),
    ):

        pair_id = review_row[
            "pair_id"
        ]

        pair = pair_by_id.get(
            pair_id
        )

        if pair is None:
            raise ValueError(
                f"Pair missing from pair plan: {pair_id}"
            )


        suite = str(
            pair[
                "suite"
            ]
        )

        surface = pair[
            "injection_surface"
        ]

        current_user = pair[
            "legitimate_context"
        ]

        current_attacker = pair[
            "attacker_context"
        ]

        selected_actions = pair[
            "selected_actions"
        ]

        safe_action = selected_actions[
            "authorized_user_action"
        ]

        risky_action = selected_actions[
            "attacker_target_action"
        ]

        safe_tool = normalize_function_name(
            safe_action
        )

        risky_tool = normalize_function_name(
            risky_action
        )


        if safe_tool != risky_tool:
            raise ValueError(
                f"P1 pair is no longer same-tool: {pair_id}"
            )


        vector_context = {
            "vector_id": surface.get(
                "vector_id"
            ),

            "source_locator": surface.get(
                "source_locator"
            ),

            "environment_locations": surface.get(
                "environment_locations",
                [],
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

            "review_note": review_row.get(
                "review_note"
            ),
        }


        user_replacement_candidates = []

        for blueprint in user_blueprints:

            if str(
                blueprint.get(
                    "suite"
                )
            ) != suite:
                continue

            structure = blueprint[
                "structure"
            ]

            if (
                structure[
                    "structure_id"
                ]
                ==
                current_user[
                    "structure_id"
                ]
            ):
                continue

            target_action = select_target_action(
                blueprint
            )

            if target_action is None:
                continue

            if (
                normalize_function_name(
                    target_action
                )
                !=
                risky_tool
            ):
                continue

            prompt = structure.get(
                "prompt_or_goal",
                "",
            )

            score = lexical_hint_score(
                vector_context,
                {
                    "prompt": prompt,
                    "action": compact_action(
                        target_action
                    ),
                },
            )

            user_replacement_candidates.append(
                {
                    "lexical_hint_score": score,

                    "blueprint_id": blueprint[
                        "blueprint_id"
                    ],

                    "structure_id": structure[
                        "structure_id"
                    ],

                    "prompt_or_goal": prompt,

                    "target_action": compact_action(
                        target_action
                    ),

                    "scenario_family": structure.get(
                        "curation",
                        {},
                    ).get(
                        "scenario_family"
                    ),

                    "quality_tier": structure.get(
                        "curation",
                        {},
                    ).get(
                        "quality_tier"
                    ),
                }
            )


        user_replacement_candidates.sort(
            key=lambda candidate: (
                -candidate[
                    "lexical_hint_score"
                ],
                candidate[
                    "structure_id"
                ],
            )
        )


        attacker_replacement_candidates = []

        for blueprint in attacker_blueprints:

            if str(
                blueprint.get(
                    "suite"
                )
            ) != suite:
                continue

            structure = blueprint[
                "structure"
            ]

            if (
                structure[
                    "structure_id"
                ]
                ==
                current_attacker[
                    "structure_id"
                ]
            ):
                continue

            target_action = select_target_action(
                blueprint
            )

            if target_action is None:
                continue

            if (
                normalize_function_name(
                    target_action
                )
                !=
                safe_tool
            ):
                continue

            prompt = structure.get(
                "prompt_or_goal",
                "",
            )

            score = lexical_hint_score(
                vector_context,
                {
                    "prompt": prompt,
                    "action": compact_action(
                        target_action
                    ),
                },
            )

            attacker_replacement_candidates.append(
                {
                    "lexical_hint_score": score,

                    "blueprint_id": blueprint[
                        "blueprint_id"
                    ],

                    "structure_id": structure[
                        "structure_id"
                    ],

                    "prompt_or_goal": prompt,

                    "target_action": compact_action(
                        target_action
                    ),

                    "scenario_family": structure.get(
                        "curation",
                        {},
                    ).get(
                        "scenario_family"
                    ),

                    "quality_tier": structure.get(
                        "curation",
                        {},
                    ).get(
                        "quality_tier"
                    ),
                }
            )


        attacker_replacement_candidates.sort(
            key=lambda candidate: (
                -candidate[
                    "lexical_hint_score"
                ],
                candidate[
                    "structure_id"
                ],
            )
        )


        compatible_vector_candidates = []

        for (
            candidate_suite,
            candidate_vector_id,
        ), candidate_vector in (
            vector_catalog.items()
        ):

            if candidate_suite != suite:
                continue

            if (
                candidate_vector_id
                ==
                surface[
                    "vector_id"
                ]
            ):
                continue

            same_surface = (
                candidate_vector.get(
                    "surface_type"
                )
                ==
                surface.get(
                    "surface_type"
                )
            )

            same_source = (
                candidate_vector.get(
                    "source_type"
                )
                ==
                surface.get(
                    "source_type"
                )
            )

            same_channel = (
                candidate_vector.get(
                    "retrieval_channel"
                )
                ==
                surface.get(
                    "retrieval_channel"
                )
            )

            if not (
                same_surface
                and
                same_source
                and
                same_channel
            ):
                continue

            score = lexical_hint_score(
                current_user.get(
                    "prompt_or_goal",
                    "",
                ),
                candidate_vector,
            )

            compatible_vector_candidates.append(
                {
                    "lexical_hint_score": score,

                    **candidate_vector,

                    "observed_pair_ids": sorted(
                        vector_pair_ids[
                            (
                                candidate_suite,
                                candidate_vector_id,
                            )
                        ],
                        key=pair_number,
                    ),
                }
            )


        compatible_vector_candidates.sort(
            key=lambda candidate: (
                -candidate[
                    "lexical_hint_score"
                ],
                candidate[
                    "vector_id"
                ],
            )
        )


        dossier_records.append(
            {
                "pair_id": pair_id,

                "repair_priority": (
                    review_row[
                        "repair_priority"
                    ]
                ),

                "suite": suite,

                "issue_category": (
                    review_row[
                        "issue_category"
                    ]
                ),

                "review_note": (
                    review_row[
                        "review_note"
                    ]
                ),

                "suggested_repair_strategy": (
                    review_row[
                        "suggested_repair_strategy"
                    ]
                ),

                "current_pair": {
                    "legitimate_context": (
                        current_user
                    ),

                    "attacker_context": (
                        current_attacker
                    ),

                    "injection_surface": (
                        surface
                    ),

                    "context_bindings": pair.get(
                        "context_bindings",
                        {},
                    ),

                    "safe_action": compact_action(
                        safe_action
                    ),

                    "risky_action": compact_action(
                        risky_action
                    ),

                    "same_tool_name": safe_tool,

                    "pairing_diagnostics": pair.get(
                        "pairing_diagnostics",
                        {},
                    ),
                },

                "repair_options": {
                    "binding_only_possible": (
                        bool(
                            surface.get(
                                "source_locator"
                            )
                        )
                        or
                        bool(
                            surface.get(
                                "environment_locations"
                            )
                        )
                    ),

                    "same_tool_user_replacement_candidates": (
                        user_replacement_candidates
                    ),

                    "same_tool_attacker_replacement_candidates": (
                        attacker_replacement_candidates
                    ),

                    "compatible_vector_candidates": (
                        compatible_vector_candidates
                    ),
                },

                "human_repair_decision": None,

                "selected_replacement_user_structure_id": None,

                "selected_replacement_attacker_structure_id": None,

                "selected_replacement_vector_id": None,

                "selected_source_locator": None,

                "repair_note": None,
            }
        )


    write_jsonl(
        DOSSIER_PATH,
        dossier_records,
    )


    user_candidate_counts = {
        record[
            "pair_id"
        ]: len(
            record[
                "repair_options"
            ][
                "same_tool_user_replacement_candidates"
            ]
        )
        for record in dossier_records
    }

    attacker_candidate_counts = {
        record[
            "pair_id"
        ]: len(
            record[
                "repair_options"
            ][
                "same_tool_attacker_replacement_candidates"
            ]
        )
        for record in dossier_records
    }

    vector_candidate_counts = {
        record[
            "pair_id"
        ]: len(
            record[
                "repair_options"
            ][
                "compatible_vector_candidates"
            ]
        )
        for record in dossier_records
    }


    report = {
        "artifact_version": "0.1.1",

        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "p1_pair_count": len(
            dossier_records
        ),

        "p1_pair_ids": [
            record[
                "pair_id"
            ]
            for record in dossier_records
        ],

        "issue_category_counts": dict(
            Counter(
                record[
                    "issue_category"
                ]
                for record in dossier_records
            )
        ),

        "user_replacement_candidate_counts": (
            user_candidate_counts
        ),

        "attacker_replacement_candidate_counts": (
            attacker_candidate_counts
        ),

        "compatible_vector_candidate_counts": (
            vector_candidate_counts
        ),

        "dossier_path": str(
            DOSSIER_PATH
        ),

        "important_notes": [
            (
                "This script performs diagnostics only and "
                "does not modify the pair plan, smoke pool, "
                "review ledger, or final labels."
            ),
            (
                "User replacement candidates preserve the "
                "current attacker target tool."
            ),
            (
                "Attacker replacement candidates preserve the "
                "current authorized user-action tool."
            ),
            (
                "Compatible vector candidates match the same "
                "suite, surface type, source type, and retrieval "
                "channel."
            ),
            (
                "Lexical hint scores are triage aids only and "
                "must not be treated as repair decisions."
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
        "AGENTDOJO P1 SAME-TOOL REPAIR "
        "DOSSIER v0.1.1 CREATED"
    )
    print("=" * 80)

    print()
    print(
        "P1 pairs:",
        len(
            dossier_records
        ),
    )


    for record in dossier_records:

        current = record[
            "current_pair"
        ]

        options = record[
            "repair_options"
        ]

        print()
        print("=" * 110)

        print(
            "PAIR:",
            record[
                "pair_id"
            ],
        )

        print(
            "SUITE:",
            record[
                "suite"
            ],
        )

        print(
            "ISSUE:",
            record[
                "issue_category"
            ],
        )

        print(
            "REVIEW NOTE:",
            record[
                "review_note"
            ],
        )

        print()

        print(
            "VECTOR:",
            current[
                "injection_surface"
            ][
                "vector_id"
            ],
        )

        print(
            "SURFACE:",
            current[
                "injection_surface"
            ].get(
                "surface_type"
            ),
        )

        print(
            "SOURCE LOCATOR:",
            current[
                "injection_surface"
            ].get(
                "source_locator"
            )
            or
            "<none>",
        )

        print(
            "ENVIRONMENT LOCATIONS:",
            short_text(
                current[
                    "injection_surface"
                ].get(
                    "environment_locations",
                    [],
                ),
                max_chars=1000,
            ),
        )

        print(
            "CURRENT BINDINGS:",
            short_text(
                current.get(
                    "context_bindings",
                    {},
                ),
                max_chars=1000,
            ),
        )

        print()

        print(
            "USER STRUCTURE:",
            current[
                "legitimate_context"
            ][
                "structure_id"
            ],
        )

        print(
            "USER GOAL:",
            current[
                "legitimate_context"
            ][
                "prompt_or_goal"
            ],
        )

        print()

        print(
            "ATTACKER STRUCTURE:",
            current[
                "attacker_context"
            ][
                "structure_id"
            ],
        )

        print(
            "ATTACKER GOAL:",
            current[
                "attacker_context"
            ][
                "prompt_or_goal"
            ],
        )

        print()

        print(
            "SAME TOOL:",
            current[
                "same_tool_name"
            ],
        )

        print(
            "SAFE ARGS:",
            short_text(
                current[
                    "safe_action"
                ][
                    "args"
                ],
                max_chars=900,
            ),
        )

        print(
            "RISKY ARGS:",
            short_text(
                current[
                    "risky_action"
                ][
                    "args"
                ],
                max_chars=900,
            ),
        )

        print()

        print(
            "BINDING-ONLY POSSIBLE:",
            options[
                "binding_only_possible"
            ],
        )

        print(
            "SAME-TOOL USER CANDIDATES:",
            len(
                options[
                    "same_tool_user_replacement_candidates"
                ]
            ),
        )

        for candidate in (
            options[
                "same_tool_user_replacement_candidates"
            ][:8]
        ):

            print(
                "  "
                f"[score={candidate['lexical_hint_score']}] "
                f"{candidate['structure_id']} — "
                f"{short_text(candidate['prompt_or_goal'], 220)}"
            )

        print(
            "SAME-TOOL ATTACKER CANDIDATES:",
            len(
                options[
                    "same_tool_attacker_replacement_candidates"
                ]
            ),
        )

        for candidate in (
            options[
                "same_tool_attacker_replacement_candidates"
            ][:8]
        ):

            print(
                "  "
                f"[score={candidate['lexical_hint_score']}] "
                f"{candidate['structure_id']} — "
                f"{short_text(candidate['prompt_or_goal'], 220)}"
            )

        print(
            "COMPATIBLE VECTOR CANDIDATES:",
            len(
                options[
                    "compatible_vector_candidates"
                ]
            ),
        )

        for candidate in (
            options[
                "compatible_vector_candidates"
            ][:10]
        ):

            print(
                "  "
                f"[score={candidate['lexical_hint_score']}] "
                f"{candidate['vector_id']} — "
                f"locator="
                f"{candidate.get('source_locator') or '<none>'} — "
                f"used_by="
                f"{','.join(candidate['observed_pair_ids'])}"
            )


    print()
    print("=" * 80)

    print(
        f"Dossier: {DOSSIER_PATH}"
    )

    print(
        f"Report: {REPORT_PATH}"
    )

    print()
    print(
        "Pair plan modified: no"
    )

    print(
        "Smoke pool modified: no"
    )

    print(
        "Final labels modified: no"
    )


if __name__ == "__main__":
    main()

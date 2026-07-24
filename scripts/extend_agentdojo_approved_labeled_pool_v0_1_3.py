from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import re
import statistics
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BASE_MATERIALIZER_PATH = Path(
    "scripts/materialize_agentdojo_approved_labeled_pool_v0_1_2.py"
)

PAIR_PLAN_PATH = Path(
    "data/interim/"
    "agentdojo_contextual_pair_plan_v0.1.3_"
    "p2_deterministic_repaired.jsonl"
)

SOURCE_SMOKE_POOL_PATH = Path(
    "data/interim/"
    "agentdojo_contextual_action_attempt_smoke_pool_v0.1.1.jsonl"
)

SOURCE_STRUCTURED_POOL_PATH = Path(
    "data/processed/"
    "agentdojo_contextual_action_attempt_labeled_pool_v0.1.2.jsonl"
)

SOURCE_TRAINING_VIEW_PATH = Path(
    "data/processed/"
    "agentdojo_bert_training_view_v0.1.2.jsonl"
)

SOURCE_REVIEW_LEDGER_PATH = Path(
    "data/interim/"
    "agentdojo_action_attempt_human_review_master_v0.1.2.csv"
)

P2_SECOND_REVIEW_PATH = Path(
    "data/interim/"
    "agentdojo_p2_deterministic_second_review_queue_v0.1.3.csv"
)

V012_HASH_MANIFEST_PATH = Path(
    "data/processed/"
    "agentdojo_v0.1.2_sha256.txt"
)


OUTPUT_STRUCTURED_POOL_PATH = Path(
    "data/processed/"
    "agentdojo_contextual_action_attempt_labeled_pool_v0.1.3.jsonl"
)

OUTPUT_TRAINING_VIEW_PATH = Path(
    "data/processed/"
    "agentdojo_bert_training_view_v0.1.3.jsonl"
)

OUTPUT_REVIEW_LEDGER_PATH = Path(
    "data/interim/"
    "agentdojo_action_attempt_human_review_master_v0.1.3.csv"
)

REPORT_PATH = Path(
    "data/processed/"
    "agentdojo_contextual_action_attempt_labeled_pool_v0.1.3_report.json"
)


EXPECTED_SOURCE_PAIR_COUNT = 60
EXPECTED_SOURCE_ROW_COUNT = 120

EXPECTED_NEW_PAIR_COUNT = 9
EXPECTED_NEW_ROW_COUNT = 18

EXPECTED_FINAL_PAIR_COUNT = 69
EXPECTED_FINAL_ROW_COUNT = 138
EXPECTED_SAFE_COUNT = 69
EXPECTED_RISKY_COUNT = 69

EXPECTED_PENDING_PAIR_COUNT = 31
EXPECTED_SAME_TOOL_PAIR_COUNT = 17


EXPECTED_P2_PAIR_IDS = {
    "agentdojo_pair_002",
    "agentdojo_pair_005",
    "agentdojo_pair_009",
    "agentdojo_pair_026",
    "agentdojo_pair_027",
    "agentdojo_pair_035",
    "agentdojo_pair_073",
    "agentdojo_pair_089",
    "agentdojo_pair_092",
}


def load_base_module():

    if not BASE_MATERIALIZER_PATH.exists():
        raise FileNotFoundError(
            f"Missing base materializer: "
            f"{BASE_MATERIALIZER_PATH}"
        )

    specification = (
        importlib.util.spec_from_file_location(
            "agentdojo_materializer_v012",
            BASE_MATERIALIZER_PATH,
        )
    )

    if (
        specification is None
        or specification.loader is None
    ):
        raise ImportError(
            "Could not load the v0.1.2 materializer."
        )

    module = importlib.util.module_from_spec(
        specification
    )

    specification.loader.exec_module(
        module
    )

    return module


def sha256_file(
    path: Path,
) -> str:

    digest = hashlib.sha256()

    with path.open(
        "rb"
    ) as file:

        while True:

            chunk = file.read(
                1024 * 1024
            )

            if not chunk:
                break

            digest.update(
                chunk
            )

    return digest.hexdigest()


def verify_v012_checkpoint() -> None:

    if not V012_HASH_MANIFEST_PATH.exists():
        raise FileNotFoundError(
            "Missing v0.1.2 hash manifest: "
            f"{V012_HASH_MANIFEST_PATH}"
        )

    verified = 0

    for line in V012_HASH_MANIFEST_PATH.read_text(
        encoding="utf-8"
    ).splitlines():

        line = line.strip()

        if not line:
            continue

        parts = line.split(
            None,
            1,
        )

        if len(parts) != 2:
            raise ValueError(
                f"Invalid hash-manifest line: {line}"
            )

        expected_hash, raw_path = parts

        artifact_path = Path(
            raw_path.strip()
        )

        if not artifact_path.exists():
            raise FileNotFoundError(
                f"Checkpoint artifact missing: "
                f"{artifact_path}"
            )

        actual_hash = sha256_file(
            artifact_path
        )

        if actual_hash != expected_hash:
            raise ValueError(
                "v0.1.2 checkpoint integrity failure:\n"
                f"Artifact: {artifact_path}\n"
                f"Expected: {expected_hash}\n"
                f"Actual:   {actual_hash}"
            )

        verified += 1

    if verified != 4:
        raise ValueError(
            "Expected four v0.1.2 checkpoint hashes, "
            f"verified {verified}."
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
            f"Invalid pair ID: {pair_id}"
        )

    return int(
        match.group(1)
    )


def variant_order(
    variant_name: str,
) -> int:

    return {
        "safe": 0,
        "risky": 1,
    }[
        variant_name
    ]


def canonical_hash(
    value: Any,
) -> str:

    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode(
            "utf-8"
        )
    ).hexdigest()


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
    fieldnames: list[str],
    rows: list[dict[str, Any]],
) -> None:

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
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(
            rows
        )


def materialize_new_pair(
    *,
    base: Any,
    pair: dict[str, Any],
    suite_template: dict[str, Any],
    review_row: dict[str, str],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
]:

    pair_id = str(
        pair[
            "pair_id"
        ]
    )

    suite = str(
        pair[
            "suite"
        ]
    )

    session_group_id = str(
        pair[
            "session_group_id"
        ]
    )


    legitimate_context = pair[
        "legitimate_context"
    ]

    attacker_context = pair[
        "attacker_context"
    ]

    injection_surface = pair[
        "injection_surface"
    ]

    selected_actions = pair[
        "selected_actions"
    ]


    user_goal = str(
        legitimate_context[
            "prompt_or_goal"
        ]
    )

    attacker_goal = str(
        attacker_context[
            "prompt_or_goal"
        ]
    )


    retrieved_content = (
        base.compose_retrieved_content(
            injection_surface.get(
                "default_value"
            ),
            attacker_goal,
        )
    )


    binding = base.resolve_context_binding(
        pair
    )


    agent_context = deepcopy(
        suite_template[
            "agent_context"
        ]
    )

    policy_context = deepcopy(
        suite_template[
            "policy_context"
        ]
    )


    source = {
        "type": (
            "retrieved_environment_content"
        ),

        "trust_level": injection_surface[
            "trust_level"
        ],

        "surface_type": injection_surface[
            "surface_type"
        ],

        "source_type": injection_surface[
            "source_type"
        ],

        "vector_id": injection_surface[
            "vector_id"
        ],

        "source_locator": binding[
            "retrieved_object_locator"
        ],
    }


    retrieval_context = {
        "retrieval_channel": injection_surface[
            "retrieval_channel"
        ],

        "content_redacted": retrieved_content,

        "environment_locations": (
            injection_surface.get(
                "environment_locations",
                [],
            )
        ),

        "content_origin": (
            "agentdojo_environment_plus_"
            "attacker_goal"
        ),

        "source_locator": binding[
            "retrieved_object_locator"
        ],

        "context_binding": binding,
    }


    authorized_action = base.compact_action(
        selected_actions[
            "authorized_user_action"
        ]
    )


    authorization_context = {
        "authorization_source": (
            "explicit_user_goal"
        ),

        "user_goal": user_goal,

        "authorized_action": (
            authorized_action
        ),

        "important_note": (
            "The authorized action records the "
            "scope inferred from the explicit user "
            "request. It is not a runtime decision."
        ),

        "parameter_bindings": binding[
            "parameter_bindings"
        ],
    }


    shared_context_payload = {
        "user_goal": user_goal,

        "agent_context": (
            agent_context
        ),

        "source": source,

        "retrieval_context": (
            retrieval_context
        ),

        "authorization_context": (
            authorization_context
        ),

        "policy_context": (
            policy_context
        ),
    }


    shared_context_fingerprint = (
        base.stable_hash(
            shared_context_payload
        )
    )


    diagnostics = pair.get(
        "pairing_diagnostics",
        {},
    )


    surface_workflow_match = (
        diagnostics.get(
            "surface_matches_legitimate_workflow"
        )
    )

    if surface_workflow_match is None:

        surface_workflow_match = (
            diagnostics.get(
                "surface_workflow_match"
            )
        )

    if surface_workflow_match is None:
        surface_workflow_match = True


    review_note = review_row.get(
        "second_review_note",
        "",
    )


    variant_specs = [
        {
            "name": "safe",

            "role": (
                "authorized_action_attempt"
            ),

            "expected_contextual_class": (
                "contextually_safe"
            ),

            "label": 0,

            "attempted_action": (
                base.compact_action(
                    selected_actions[
                        "authorized_user_action"
                    ]
                )
            ),
        },

        {
            "name": "risky",

            "role": (
                "injection_following_action_attempt"
            ),

            "expected_contextual_class": (
                "contextually_risky"
            ),

            "label": 1,

            "attempted_action": (
                base.compact_action(
                    selected_actions[
                        "attacker_target_action"
                    ]
                )
            ),
        },
    ]


    structured_rows = []
    training_rows = []


    for variant_index, specification in enumerate(
        variant_specs,
        start=1,
    ):

        variant_name = specification[
            "name"
        ]

        final_label = int(
            specification[
                "label"
            ]
        )

        attempted_action = specification[
            "attempted_action"
        ]


        event_id = (
            f"{pair_id}::"
            f"{variant_name}::action_attempt"
        )


        model_input_payload = {
            "user_goal": user_goal,
            "agent_context": agent_context,
            "source": source,
            "retrieval_context": retrieval_context,
            "authorization_context": (
                authorization_context
            ),
            "policy_context": policy_context,
            "attempted_action": attempted_action,
        }


        forbidden_paths = (
            base.find_forbidden_keys(
                model_input_payload
            )
        )

        if forbidden_paths:
            raise ValueError(
                "Forbidden fields found in new "
                f"model input for {event_id}: "
                f"{forbidden_paths}"
            )


        model_input_text = (
            base.serialize_model_input(
                user_goal=user_goal,
                agent_context=agent_context,
                source=source,
                retrieval_context=(
                    retrieval_context
                ),
                authorization_context=(
                    authorization_context
                ),
                policy_context=policy_context,
                attempted_action=(
                    attempted_action
                ),
                binding=binding,
            )
        )


        structured_row = {
            "row_id": event_id,

            # Artifact v0.1.3 extends the dataset,
            # but the row schema itself is unchanged.
            "schema_version": (
                "action_attempt_context_v0.1.2"
            ),

            "scenario_source": "agentdojo",

            "pair_id": pair_id,

            "session_group_id": (
                session_group_id
            ),

            "event_id": event_id,

            "session_id": (
                f"session::{pair_id}"
            ),

            "trace_id": (
                f"trace::{session_group_id}"
            ),

            "span_id": (
                f"span::{pair_id}::"
                f"{variant_index:02d}"
            ),

            "parent_span_id": (
                f"span::{pair_id}::retrieval"
            ),

            "event_type": (
                "action.attempt"
            ),

            "suite": suite,

            "variant": {
                "name": variant_name,

                "role": specification[
                    "role"
                ],
            },

            "user_context": {
                "goal": user_goal,

                "legitimate_structure_id": (
                    base.structure_id(
                        legitimate_context
                    )
                ),

                "scenario_family": (
                    legitimate_context.get(
                        "scenario_family"
                    )
                ),
            },

            "agent_context": agent_context,

            "source": source,

            "retrieval_context": (
                retrieval_context
            ),

            "authorization_context": (
                authorization_context
            ),

            "policy_context": (
                policy_context
            ),

            "action": attempted_action,

            "model_input": {
                "serialization_version": (
                    "bert_context_v0.1.2"
                ),

                "text": model_input_text,

                "shared_context_fingerprint": (
                    shared_context_fingerprint
                ),

                "attempted_action_fingerprint": (
                    base.stable_hash(
                        attempted_action
                    )
                ),

                "included_sections": [
                    "user_goal",
                    "agent_context",
                    "source",
                    "context_bindings",
                    "retrieved_content",
                    "user_authorization",
                    "policy_context",
                    "attempted_action",
                ],

                "excluded_from_input": [
                    "review metadata",
                    "proposed label",
                    "final label",
                    "expected contextual class",
                    "runtime decision",
                    "risk score",
                    "policy-engine output",
                ],
            },

            "review": {
                "status": (
                    "human_reviewed_approved"
                ),

                "expected_contextual_class": (
                    specification[
                        "expected_contextual_class"
                    ]
                ),

                "proposed_binary_label": (
                    final_label
                ),

                "final_binary_label": (
                    final_label
                ),

                "review_decision": (
                    "approve_pair"
                ),

                "review_note": review_note,

                "label_source": (
                    "human_review_p2_"
                    "deterministic_second_round"
                ),
            },

            "provenance": {
                "source_pair_plan_version": (
                    pair.get(
                        "active_pair_plan_version"
                    )
                    or
                    pair.get(
                        "pair_plan_version",
                        "0.1",
                    )
                ),

                "active_pair_plan_artifact": (
                    "agentdojo_contextual_pair_plan_"
                    "v0.1.3_p2_deterministic_repaired"
                ),

                "legitimate_structure_id": (
                    base.structure_id(
                        legitimate_context
                    )
                ),

                "attacker_structure_id": (
                    base.structure_id(
                        attacker_context
                    )
                ),

                "injection_vector_id": (
                    injection_surface[
                        "vector_id"
                    ]
                ),

                "same_tool_minimal_pair": (
                    base.derive_same_tool(
                        pair
                    )
                ),

                "surface_workflow_match": (
                    bool(
                        surface_workflow_match
                    )
                ),

                "source_binding_type": (
                    binding[
                        "binding_type"
                    ]
                ),

                "source_binding_status": (
                    binding[
                        "binding_status"
                    ]
                ),

                "source_locator_present": bool(
                    binding[
                        "retrieved_object_locator"
                    ]
                ),

                "human_review_round": (
                    "human_review_p2_"
                    "deterministic_second_round"
                ),

                "p1_repaired_pair": False,

                "p2_deterministic_repaired_pair": True,

                "repair_metadata": pair.get(
                    "repair_metadata"
                ),
            },

            "important_note": (
                "This is a human-approved contextual "
                "action.attempt row added during the "
                "v0.1.3 incremental extension. Final "
                "labels remain excluded from "
                "model_input.text."
            ),
        }


        training_row = {
            "row_id": event_id,

            "pair_id": pair_id,

            "session_group_id": (
                session_group_id
            ),

            "suite": suite,

            "variant": variant_name,

            "text": model_input_text,

            "general_risk_label": (
                final_label
            ),

            "text_sha256": (
                base.text_hash(
                    model_input_text
                )
            ),

            "label_source": (
                "human_review_p2_"
                "deterministic_second_round"
            ),

            "schema_version": (
                "bert_training_view_v0.1.2"
            ),
        }


        structured_rows.append(
            structured_row
        )

        training_rows.append(
            training_row
        )


    return (
        structured_rows,
        training_rows,
    )


def main() -> None:

    verify_v012_checkpoint()

    base = load_base_module()


    candidate_pairs = base.load_jsonl(
        PAIR_PLAN_PATH
    )

    source_smoke_rows = base.load_jsonl(
        SOURCE_SMOKE_POOL_PATH
    )

    source_structured_rows = base.load_jsonl(
        SOURCE_STRUCTURED_POOL_PATH
    )

    source_training_rows = base.load_jsonl(
        SOURCE_TRAINING_VIEW_PATH
    )

    (
        ledger_fieldnames,
        ledger_rows,
    ) = base.load_csv(
        SOURCE_REVIEW_LEDGER_PATH
    )

    (
        _,
        p2_review_rows,
    ) = base.load_csv(
        P2_SECOND_REVIEW_PATH
    )


    if len(candidate_pairs) != 100:
        raise ValueError(
            "Expected 100 candidate pairs, "
            f"found {len(candidate_pairs)}."
        )


    source_pair_ids = {
        row[
            "pair_id"
        ]
        for row in source_structured_rows
    }


    if (
        len(source_pair_ids)
        !=
        EXPECTED_SOURCE_PAIR_COUNT
    ):
        raise ValueError(
            "Expected 60 source approved pairs, "
            f"found {len(source_pair_ids)}."
        )


    if (
        len(source_structured_rows)
        !=
        EXPECTED_SOURCE_ROW_COUNT
    ):
        raise ValueError(
            "Expected 120 source structured rows, "
            f"found {len(source_structured_rows)}."
        )


    if (
        len(source_training_rows)
        !=
        EXPECTED_SOURCE_ROW_COUNT
    ):
        raise ValueError(
            "Expected 120 source training rows, "
            f"found {len(source_training_rows)}."
        )


    p2_review_by_id = {
        str(
            row[
                "pair_id"
            ]
        ): row
        for row in p2_review_rows
    }


    if (
        set(p2_review_by_id)
        !=
        EXPECTED_P2_PAIR_IDS
    ):
        raise ValueError(
            "Unexpected P2 second-review inventory.\n"
            f"Expected: "
            f"{sorted(EXPECTED_P2_PAIR_IDS)}\n"
            f"Found: "
            f"{sorted(p2_review_by_id)}"
        )


    for pair_id, review_row in (
        p2_review_by_id.items()
    ):

        if (
            review_row.get(
                "second_review_decision"
            )
            !=
            "approve_pair"
        ):
            raise ValueError(
                f"P2 pair has not been approved: "
                f"{pair_id}"
            )


    if (
        source_pair_ids
        &
        EXPECTED_P2_PAIR_IDS
    ):
        raise ValueError(
            "A newly approved P2 pair already exists "
            "inside the v0.1.2 labeled pool."
        )


    pair_by_id = {
        str(
            pair[
                "pair_id"
            ]
        ): pair
        for pair in candidate_pairs
    }


    suite_template_by_name: dict[
        str,
        dict[str, Any],
    ] = {}


    for row in source_smoke_rows:

        suite = str(
            row[
                "suite"
            ]
        )

        suite_template_by_name.setdefault(
            suite,
            row,
        )


    if set(
        suite_template_by_name
    ) != {
        "banking",
        "slack",
        "travel",
        "workspace",
    }:
        raise ValueError(
            "Unexpected suite-template inventory."
        )


    new_structured_rows = []
    new_training_rows = []


    for pair_id in sorted(
        EXPECTED_P2_PAIR_IDS,
        key=pair_number,
    ):

        pair = pair_by_id[
            pair_id
        ]

        suite = str(
            pair[
                "suite"
            ]
        )


        structured_rows, training_rows = (
            materialize_new_pair(
                base=base,
                pair=pair,
                suite_template=(
                    suite_template_by_name[
                        suite
                    ]
                ),
                review_row=(
                    p2_review_by_id[
                        pair_id
                    ]
                ),
            )
        )


        new_structured_rows.extend(
            structured_rows
        )

        new_training_rows.extend(
            training_rows
        )


    if (
        len(new_structured_rows)
        !=
        EXPECTED_NEW_ROW_COUNT
    ):
        raise ValueError(
            "Expected 18 newly materialized rows, "
            f"found {len(new_structured_rows)}."
        )


    combined_structured_rows = [
        deepcopy(row)
        for row in source_structured_rows
    ] + new_structured_rows


    combined_training_rows = [
        deepcopy(row)
        for row in source_training_rows
    ] + new_training_rows


    combined_structured_rows.sort(
        key=lambda row: (
            pair_number(
                row[
                    "pair_id"
                ]
            ),
            variant_order(
                row[
                    "variant"
                ][
                    "name"
                ]
            ),
        )
    )


    combined_training_rows.sort(
        key=lambda row: (
            pair_number(
                row[
                    "pair_id"
                ]
            ),
            variant_order(
                row[
                    "variant"
                ]
            ),
        )
    )


    # Existing v0.1.2 rows must remain semantically
    # identical inside the v0.1.3 extension.
    output_existing_by_id = {
        row[
            "row_id"
        ]: row
        for row in combined_structured_rows
        if row[
            "pair_id"
        ] in source_pair_ids
    }


    for source_row in source_structured_rows:

        output_row = output_existing_by_id.get(
            source_row[
                "row_id"
            ]
        )

        if output_row is None:
            raise ValueError(
                "Existing v0.1.2 row disappeared: "
                f"{source_row['row_id']}"
            )

        if (
            canonical_hash(
                source_row
            )
            !=
            canonical_hash(
                output_row
            )
        ):
            raise ValueError(
                "Existing v0.1.2 row changed during "
                f"extension: {source_row['row_id']}"
            )


    if (
        len(combined_structured_rows)
        !=
        EXPECTED_FINAL_ROW_COUNT
    ):
        raise ValueError(
            "Expected 138 combined rows, "
            f"found {len(combined_structured_rows)}."
        )


    combined_pair_ids = {
        row[
            "pair_id"
        ]
        for row in combined_structured_rows
    }


    if (
        len(combined_pair_ids)
        !=
        EXPECTED_FINAL_PAIR_COUNT
    ):
        raise ValueError(
            "Expected 69 combined approved pairs, "
            f"found {len(combined_pair_ids)}."
        )


    row_ids = [
        row[
            "row_id"
        ]
        for row in combined_structured_rows
    ]

    if len(row_ids) != len(
        set(row_ids)
    ):
        raise ValueError(
            "Duplicate row IDs detected."
        )


    rows_by_pair: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)


    for row in combined_structured_rows:

        rows_by_pair[
            row[
                "pair_id"
            ]
        ].append(
            row
        )


    final_label_counts = Counter()
    variant_counts = Counter()

    shared_context_passed = 0
    distinct_action_passed = 0
    session_group_passed = 0
    label_pair_passed = 0


    for pair_id, pair_rows in (
        rows_by_pair.items()
    ):

        if len(pair_rows) != 2:
            raise ValueError(
                f"{pair_id} has "
                f"{len(pair_rows)} rows."
            )


        shared_fingerprints = {
            row[
                "model_input"
            ][
                "shared_context_fingerprint"
            ]
            for row in pair_rows
        }

        if len(shared_fingerprints) != 1:
            raise ValueError(
                "Shared context differs for "
                f"{pair_id}."
            )

        shared_context_passed += 1


        action_fingerprints = {
            row[
                "model_input"
            ][
                "attempted_action_fingerprint"
            ]
            for row in pair_rows
        }

        if len(action_fingerprints) != 2:
            raise ValueError(
                "Attempted actions are identical for "
                f"{pair_id}."
            )

        distinct_action_passed += 1


        session_groups = {
            row[
                "session_group_id"
            ]
            for row in pair_rows
        }

        if len(session_groups) != 1:
            raise ValueError(
                "Session groups differ for "
                f"{pair_id}."
            )

        session_group_passed += 1


        labels = {
            int(
                row[
                    "review"
                ][
                    "final_binary_label"
                ]
            )
            for row in pair_rows
        }

        if labels != {
            0,
            1,
        }:
            raise ValueError(
                f"Invalid label pair for {pair_id}."
            )

        label_pair_passed += 1


        for row in pair_rows:

            label = int(
                row[
                    "review"
                ][
                    "final_binary_label"
                ]
            )

            variant = row[
                "variant"
            ][
                "name"
            ]

            final_label_counts[
                label
            ] += 1

            variant_counts[
                variant
            ] += 1


    if final_label_counts != {
        0: EXPECTED_SAFE_COUNT,
        1: EXPECTED_RISKY_COUNT,
    }:
        raise ValueError(
            "Unexpected label counts: "
            f"{dict(final_label_counts)}"
        )


    if variant_counts != {
        "safe": EXPECTED_SAFE_COUNT,
        "risky": EXPECTED_RISKY_COUNT,
    }:
        raise ValueError(
            "Unexpected variant counts: "
            f"{dict(variant_counts)}"
        )


    model_input_texts = [
        row[
            "model_input"
        ][
            "text"
        ]
        for row in combined_structured_rows
    ]


    duplicate_model_input_count = (
        len(model_input_texts)
        -
        len(
            set(model_input_texts)
        )
    )


    if duplicate_model_input_count != 0:
        raise ValueError(
            "Duplicate model inputs detected: "
            f"{duplicate_model_input_count}"
        )


    leakage_violations = []


    for row in combined_structured_rows:

        lowered = row[
            "model_input"
        ][
            "text"
        ].lower()

        leaked = sorted(
            marker
            for marker in (
                base.FORBIDDEN_TEXT_MARKERS
            )
            if marker in lowered
        )

        if leaked:

            leakage_violations.append(
                {
                    "row_id": row[
                        "row_id"
                    ],
                    "markers": leaked,
                }
            )


    if leakage_violations:
        raise ValueError(
            "Label/review leakage detected:\n"
            f"{leakage_violations}"
        )


    same_tool_pair_count = sum(
        bool(
            row_group[0][
                "provenance"
            ][
                "same_tool_minimal_pair"
            ]
        )
        for row_group in rows_by_pair.values()
    )


    if (
        same_tool_pair_count
        !=
        EXPECTED_SAME_TOOL_PAIR_COUNT
    ):
        raise ValueError(
            "Expected 17 same-tool approved pairs, "
            f"found {same_tool_pair_count}."
        )


    # --------------------------------------------------------
    # Update cumulative review ledger
    # --------------------------------------------------------

    additional_columns = [
        "cumulative_review_note",
        "cumulative_reviewed_at",
    ]


    output_fieldnames = list(
        ledger_fieldnames
    )

    for column in additional_columns:

        if column not in output_fieldnames:
            output_fieldnames.append(
                column
            )


    ledger_by_id = {
        str(
            row[
                "pair_id"
            ]
        ): dict(row)
        for row in ledger_rows
    }


    for pair_id in EXPECTED_P2_PAIR_IDS:

        ledger_row = ledger_by_id.get(
            pair_id
        )

        if ledger_row is None:
            raise ValueError(
                f"Missing ledger row: {pair_id}"
            )


        if (
            ledger_row.get(
                "cumulative_review_decision"
            )
            !=
            "needs_revision"
        ):
            raise ValueError(
                f"{pair_id} was not pending in "
                "the v0.1.2 ledger."
            )


        pair = pair_by_id[
            pair_id
        ]

        binding = (
            base.resolve_context_binding(
                pair
            )
        )

        review_row = p2_review_by_id[
            pair_id
        ]


        ledger_row[
            "cumulative_review_decision"
        ] = "approve_pair"

        ledger_row[
            "cumulative_human_review_status"
        ] = (
            "human_reviewed_approved_after_"
            "p2_deterministic_repair"
        )

        ledger_row[
            "cumulative_review_round"
        ] = (
            "p2_deterministic_second_human_review"
        )

        ledger_row[
            "cumulative_safe_label_final"
        ] = "0"

        ledger_row[
            "cumulative_risky_label_final"
        ] = "1"

        ledger_row[
            "label_eligible"
        ] = "true"

        ledger_row[
            "cumulative_review_note"
        ] = review_row.get(
            "second_review_note",
            "",
        )

        ledger_row[
            "cumulative_reviewed_at"
        ] = review_row.get(
            "second_reviewed_at",
            "",
        )

        ledger_row[
            "active_legitimate_structure_id"
        ] = base.structure_id(
            pair[
                "legitimate_context"
            ]
        )

        ledger_row[
            "active_attacker_structure_id"
        ] = base.structure_id(
            pair[
                "attacker_context"
            ]
        )

        ledger_row[
            "active_vector_id"
        ] = pair[
            "injection_surface"
        ][
            "vector_id"
        ]

        ledger_row[
            "active_source_locator"
        ] = (
            binding[
                "retrieved_object_locator"
            ]
            or
            ""
        )

        ledger_row[
            "active_binding_type"
        ] = binding[
            "binding_type"
        ]

        ledger_row[
            "active_binding_status"
        ] = binding[
            "binding_status"
        ]


    output_ledger_rows = sorted(
        ledger_by_id.values(),
        key=lambda row: pair_number(
            row[
                "pair_id"
            ]
        ),
    )


    cumulative_counts = Counter(
        row[
            "cumulative_review_decision"
        ]
        for row in output_ledger_rows
    )


    if cumulative_counts != {
        "approve_pair": (
            EXPECTED_FINAL_PAIR_COUNT
        ),

        "needs_revision": (
            EXPECTED_PENDING_PAIR_COUNT
        ),
    }:
        raise ValueError(
            "Unexpected cumulative review counts: "
            f"{dict(cumulative_counts)}"
        )


    # --------------------------------------------------------
    # Write new versioned artifacts
    # --------------------------------------------------------

    write_jsonl(
        OUTPUT_STRUCTURED_POOL_PATH,
        combined_structured_rows,
    )

    write_jsonl(
        OUTPUT_TRAINING_VIEW_PATH,
        combined_training_rows,
    )

    write_csv(
        OUTPUT_REVIEW_LEDGER_PATH,
        output_fieldnames,
        output_ledger_rows,
    )


    generated_at = datetime.now(
        timezone.utc
    ).isoformat()


    model_input_lengths = [
        len(text)
        for text in model_input_texts
    ]


    report = {
        "dataset": "agentdojo",

        "artifact_version": "0.1.3",

        "generated_at": generated_at,

        "artifact_status": (
            "human_reviewed_approved_subset"
        ),

        "extension_strategy": (
            "preserve_v0.1.2_rows_and_append_"
            "p2_deterministic_approved_rows"
        ),

        "v0.1.2_checkpoint_hashes_verified": 4,

        "source_approved_pair_count": (
            EXPECTED_SOURCE_PAIR_COUNT
        ),

        "source_runtime_row_count": (
            EXPECTED_SOURCE_ROW_COUNT
        ),

        "newly_approved_pair_count": (
            EXPECTED_NEW_PAIR_COUNT
        ),

        "newly_materialized_runtime_row_count": (
            EXPECTED_NEW_ROW_COUNT
        ),

        "approved_pair_count": (
            EXPECTED_FINAL_PAIR_COUNT
        ),

        "remaining_needs_revision_pair_count": (
            EXPECTED_PENDING_PAIR_COUNT
        ),

        "runtime_row_count": (
            EXPECTED_FINAL_ROW_COUNT
        ),

        "variant_counts": dict(
            variant_counts
        ),

        "final_general_risk_label_counts": {
            str(label): count
            for label, count in sorted(
                final_label_counts.items()
            )
        },

        "same_tool_approved_pair_count": (
            same_tool_pair_count
        ),

        "unique_model_input_count": len(
            set(model_input_texts)
        ),

        "duplicate_model_input_count": (
            duplicate_model_input_count
        ),

        "label_or_review_leakage_count": len(
            leakage_violations
        ),

        "shared_context_pair_validation": {
            "passed": shared_context_passed,
            "failed": 0,
        },

        "distinct_attempted_action_validation": {
            "passed": distinct_action_passed,
            "failed": 0,
        },

        "session_group_integrity_validation": {
            "passed": session_group_passed,
            "failed": 0,
        },

        "safe_risky_label_pair_validation": {
            "passed": label_pair_passed,
            "failed": 0,
        },

        "preserved_v0.1.2_structured_rows": (
            EXPECTED_SOURCE_ROW_COUNT
        ),

        "changed_v0.1.2_structured_rows": 0,

        "new_p2_pair_ids": sorted(
            EXPECTED_P2_PAIR_IDS,
            key=pair_number,
        ),

        "model_input_character_length": {
            "minimum": min(
                model_input_lengths
            ),

            "median": statistics.median(
                model_input_lengths
            ),

            "maximum": max(
                model_input_lengths
            ),

            "mean": (
                sum(model_input_lengths)
                /
                len(model_input_lengths)
            ),
        },

        "outputs": {
            "structured_labeled_pool": str(
                OUTPUT_STRUCTURED_POOL_PATH
            ),

            "bert_training_view": str(
                OUTPUT_TRAINING_VIEW_PATH
            ),

            "cumulative_review_ledger": str(
                OUTPUT_REVIEW_LEDGER_PATH
            ),
        },

        "important_notes": [
            (
                "All 120 v0.1.2 structured rows were "
                "preserved without semantic changes."
            ),

            (
                "Only the 18 rows belonging to the nine "
                "newly approved P2 deterministic repairs "
                "were materialized."
            ),

            (
                "The 31 pairs still awaiting repair remain "
                "excluded from labeled artifacts."
            ),

            (
                "Final labels remain outside "
                "model_input.text."
            ),

            (
                "The v0.1.2 checkpoint artifacts were "
                "verified against their SHA-256 manifest "
                "before extension."
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
        "AGENTDOJO APPROVED LABELED POOL "
        "v0.1.3 EXTENDED"
    )
    print("=" * 80)

    print()
    print(
        "v0.1.2 checkpoint hashes verified:",
        4,
    )

    print()
    print(
        "Preserved approved pairs:",
        EXPECTED_SOURCE_PAIR_COUNT,
    )

    print(
        "Newly approved P2 pairs:",
        EXPECTED_NEW_PAIR_COUNT,
    )

    print(
        "Total approved pairs:",
        EXPECTED_FINAL_PAIR_COUNT,
    )

    print(
        "Remaining revision pairs:",
        EXPECTED_PENDING_PAIR_COUNT,
    )

    print()
    print(
        "Preserved runtime rows:",
        EXPECTED_SOURCE_ROW_COUNT,
    )

    print(
        "New runtime rows:",
        EXPECTED_NEW_ROW_COUNT,
    )

    print(
        "Total runtime rows:",
        EXPECTED_FINAL_ROW_COUNT,
    )

    print()
    print(
        "Safe / label 0:",
        final_label_counts[0],
    )

    print(
        "Risky / label 1:",
        final_label_counts[1],
    )

    print()
    print(
        "Same-tool approved pairs:",
        same_tool_pair_count,
    )

    print()
    print(
        "Shared-context validation:",
        f"{shared_context_passed} / "
        f"{EXPECTED_FINAL_PAIR_COUNT} passed",
    )

    print(
        "Distinct-action validation:",
        f"{distinct_action_passed} / "
        f"{EXPECTED_FINAL_PAIR_COUNT} passed",
    )

    print(
        "Session-group validation:",
        f"{session_group_passed} / "
        f"{EXPECTED_FINAL_PAIR_COUNT} passed",
    )

    print(
        "Label-pair validation:",
        f"{label_pair_passed} / "
        f"{EXPECTED_FINAL_PAIR_COUNT} passed",
    )

    print()
    print(
        "Unique model inputs:",
        len(
            set(model_input_texts)
        ),
    )

    print(
        "Duplicate model inputs:",
        duplicate_model_input_count,
    )

    print(
        "Label/review leakage:",
        len(leakage_violations),
    )

    print()
    print(
        f"Structured labeled pool: "
        f"{OUTPUT_STRUCTURED_POOL_PATH}"
    )

    print(
        f"BERT training view: "
        f"{OUTPUT_TRAINING_VIEW_PATH}"
    )

    print(
        f"Cumulative review ledger: "
        f"{OUTPUT_REVIEW_LEDGER_PATH}"
    )

    print(
        f"Report: {REPORT_PATH}"
    )

    print()
    print(
        "v0.1.2 checkpoint modified: no"
    )

    print(
        "v0.1.3 candidate pair plan modified: no"
    )


if __name__ == "__main__":
    main()

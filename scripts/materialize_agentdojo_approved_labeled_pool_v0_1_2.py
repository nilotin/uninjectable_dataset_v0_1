from __future__ import annotations

import csv
import hashlib
import json
import re
import statistics
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


INTERIM_DIR = Path("data/interim")
PROCESSED_DIR = Path("data/processed")


CANDIDATE_PAIR_PLAN_PATH = (
    INTERIM_DIR
    / "agentdojo_contextual_pair_plan_v0.1.2_p1_repaired.jsonl"
)

SOURCE_SMOKE_POOL_PATH = (
    INTERIM_DIR
    / "agentdojo_contextual_action_attempt_smoke_pool_v0.1.1.jsonl"
)

MASTER_REVIEW_PATH = (
    INTERIM_DIR
    / "agentdojo_action_attempt_human_review_master_v0.1.1.csv"
)

P1_SECOND_REVIEW_PATH = (
    INTERIM_DIR
    / "agentdojo_p1_second_review_queue_v0.1.2.csv"
)


OUTPUT_STRUCTURED_POOL_PATH = (
    PROCESSED_DIR
    / "agentdojo_contextual_action_attempt_labeled_pool_v0.1.2.jsonl"
)

OUTPUT_TRAINING_VIEW_PATH = (
    PROCESSED_DIR
    / "agentdojo_bert_training_view_v0.1.2.jsonl"
)

OUTPUT_CUMULATIVE_REVIEW_PATH = (
    INTERIM_DIR
    / "agentdojo_action_attempt_human_review_master_v0.1.2.csv"
)

REPORT_PATH = (
    PROCESSED_DIR
    / "agentdojo_contextual_action_attempt_labeled_pool_v0.1.2_report.json"
)


EXPECTED_CANDIDATE_PAIR_COUNT = 100
EXPECTED_SOURCE_ROW_COUNT = 200

EXPECTED_FIRST_ROUND_APPROVED_PAIR_COUNT = 55
EXPECTED_P1_APPROVED_PAIR_COUNT = 5

EXPECTED_APPROVED_PAIR_COUNT = 60
EXPECTED_PENDING_PAIR_COUNT = 40
EXPECTED_EXCLUDED_PAIR_COUNT = 0

EXPECTED_RUNTIME_ROW_COUNT = 120
EXPECTED_SAFE_ROW_COUNT = 60
EXPECTED_RISKY_ROW_COUNT = 60
EXPECTED_SAME_TOOL_APPROVED_PAIR_COUNT = 17

EXPECTED_DUPLICATE_MODEL_INPUT_COUNT = 0


P1_REPAIRED_PAIR_IDS = {
    "agentdojo_pair_016",
    "agentdojo_pair_031",
    "agentdojo_pair_040",
    "agentdojo_pair_091",
    "agentdojo_pair_095",
}


FORBIDDEN_MODEL_INPUT_KEYS = {
    "general_risk_label",
    "proposed_binary_label",
    "final_binary_label",
    "expected_contextual_class",
    "review_decision",
    "authorization_alignment",
    "runtime_decision",
    "risk_score",
    "ml_risk_score",
    "policy_output",
}


FORBIDDEN_TEXT_MARKERS = {
    "general_risk_label",
    "proposed_binary_label",
    "final_binary_label",
    "expected_contextual_class",
    "review_decision",
    "runtime_decision",
    "risk_score",
    "ml_risk_score",
    "policy_output",
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

        reader = csv.DictReader(
            file
        )

        if reader.fieldnames is None:
            raise ValueError(
                f"CSV has no header: {path}"
            )

        return (
            list(reader.fieldnames),
            list(reader),
        )


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
        writer.writerows(rows)


def canonical_json(
    value: Any,
) -> str:

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def stable_hash(
    value: Any,
) -> str:

    return hashlib.sha256(
        canonical_json(
            value
        ).encode(
            "utf-8"
        )
    ).hexdigest()


def text_hash(
    text: str,
) -> str:

    return hashlib.sha256(
        text.encode(
            "utf-8"
        )
    ).hexdigest()


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


def normalize_text(
    value: Any,
) -> str:

    if value is None:
        return ""

    text = str(
        value
    ).strip()

    if text.lower() in {
        "",
        "<na>",
        "nan",
        "none",
        "null",
    }:
        return ""

    return text


def action_name(
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


def action_args(
    action: dict[str, Any],
) -> Any:

    if action.get(
        "args"
    ) is not None:
        return action[
            "args"
        ]

    return action.get(
        "args_expression"
    )


def action_metadata(
    action: dict[str, Any],
    key: str,
) -> Any:

    return (
        action.get(
            key
        )
        or
        action.get(
            "tool_metadata",
            {},
        ).get(
            key
        )
    )


def compact_action(
    action: dict[str, Any],
) -> dict[str, Any]:

    tool_name = action_name(
        action
    )

    if not tool_name:
        raise ValueError(
            f"Action has no tool name: {action}"
        )

    return {
        "tool_name": tool_name,

        "args": action_args(
            action
        ),

        "args_expression": action.get(
            "args_expression"
        ),

        "placeholder_args": action.get(
            "placeholder_args"
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


def structure_id(
    context: dict[str, Any],
) -> str:

    return str(
        context.get(
            "structure_id"
        )
        or
        context.get(
            "blueprint_id"
        )
        or
        ""
    )


def compose_retrieved_content(
    default_value: Any,
    attacker_goal: Any,
) -> str:

    default_text = normalize_text(
        default_value
    )

    attacker_text = normalize_text(
        attacker_goal
    )

    sections = []

    if default_text:
        sections.append(
            default_text
        )

    if attacker_text:
        sections.append(
            attacker_text
        )

    return "\n\n".join(
        sections
    )


def serialize_value(
    value: Any,
) -> str:

    if isinstance(
        value,
        str,
    ):
        return value

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
    )


def resolve_context_binding(
    pair: dict[str, Any],
) -> dict[str, Any]:

    pair_binding = deepcopy(
        pair.get(
            "context_bindings",
            {},
        )
    )

    surface = pair.get(
        "injection_surface",
        {},
    )


    locator = (
        pair_binding.get(
            "retrieved_object_locator"
        )
        or
        surface.get(
            "source_locator"
        )
    )


    binding_type = (
        pair_binding.get(
            "binding_type"
        )
        or
        surface.get(
            "binding_type"
        )
        or
        "surface_level_binding"
    )


    binding_status = (
        pair_binding.get(
            "binding_status"
        )
        or
        surface.get(
            "binding_status"
        )
    )


    if not binding_status:

        binding_status = (
            "confirmed"
            if locator
            else
            "surface_level_only"
        )


    parameter_bindings = deepcopy(
        pair_binding.get(
            "parameter_bindings",
            {},
        )
    )


    if (
        not parameter_bindings
        and
        binding_type
        ==
        "parameterized_web_url_binding"
        and
        locator
    ):
        parameter_bindings[
            "URL"
        ] = locator


    binding_source = (
        pair_binding.get(
            "binding_source"
        )
        or
        (
            "human_repair_and_second_review"
            if pair[
                "pair_id"
            ] in P1_REPAIRED_PAIR_IDS
            else
            (
                "human_semantic_repair"
                if (
                    locator
                    or
                    binding_status
                    not in {
                        "",
                        "surface_level_only",
                    }
                )
                else
                "suite_surface_metadata"
            )
        )
    )


    return {
        "binding_type": binding_type,

        "binding_status": binding_status,

        "retrieved_object_locator": locator,

        "parameter_bindings": (
            parameter_bindings
        ),

        "binding_source": binding_source,

        "binding_evidence": pair_binding.get(
            "binding_evidence"
        ),
    }


def serialize_model_input(
    *,
    user_goal: str,
    agent_context: dict[str, Any],
    source: dict[str, Any],
    retrieval_context: dict[str, Any],
    authorization_context: dict[str, Any],
    policy_context: dict[str, Any],
    attempted_action: dict[str, Any],
    binding: dict[str, Any],
) -> str:

    allowed_tools = ", ".join(
        agent_context[
            "allowed_tools"
        ]
    )


    policy_text = "\n".join(
        f"- {constraint}"
        for constraint in policy_context[
            "constraints"
        ]
    )


    authorized_action = (
        authorization_context[
            "authorized_action"
        ]
    )


    source_lines = [
        (
            "trust_level="
            f"{source['trust_level']}"
        ),

        (
            "surface_type="
            f"{source['surface_type']}"
        ),

        (
            "source_type="
            f"{source['source_type']}"
        ),

        (
            "retrieval_channel="
            f"{retrieval_context['retrieval_channel']}"
        ),
    ]


    locator = binding.get(
        "retrieved_object_locator"
    )

    if locator:

        source_lines.append(
            f"source_locator={locator}"
        )


    binding_lines = [
        (
            "binding_type="
            f"{binding['binding_type']}"
        ),

        (
            "binding_status="
            f"{binding['binding_status']}"
        ),
    ]


    if locator:

        binding_lines.append(
            "retrieved_object_locator="
            f"{locator}"
        )


    parameter_bindings = binding.get(
        "parameter_bindings",
        {},
    )

    if parameter_bindings:

        binding_lines.append(
            "parameter_bindings="
            f"{serialize_value(parameter_bindings)}"
        )


    sections = [
        (
            "[USER_GOAL]\n"
            f"{user_goal}"
        ),

        (
            "[AGENT_CONTEXT]\n"
            f"agent_role={agent_context['agent_role']}\n"
            f"allowed_tools={allowed_tools}"
        ),

        (
            "[SOURCE]\n"
            +
            "\n".join(
                source_lines
            )
        ),

        (
            "[CONTEXT_BINDINGS]\n"
            +
            "\n".join(
                binding_lines
            )
        ),

        (
            "[RETRIEVED_CONTENT]\n"
            f"{retrieval_context['content_redacted']}"
        ),

        (
            "[USER_AUTHORIZATION]\n"
            "authorized_tool="
            f"{authorized_action['tool_name']}\n"
            "authorized_args="
            f"{serialize_value(authorized_action['args'])}"
        ),

        (
            "[POLICY_CONTEXT]\n"
            f"{policy_text}"
        ),

        (
            "[ATTEMPTED_ACTION]\n"
            f"tool_name={attempted_action['tool_name']}\n"
            f"args={serialize_value(attempted_action['args'])}\n"
            "capability_class="
            f"{attempted_action['capability_class']}\n"
            "action_impact="
            f"{attempted_action['action_impact']}"
        ),
    ]


    text = "\n\n".join(
        sections
    )


    lowered = text.lower()

    leaked_markers = sorted(
        marker
        for marker in FORBIDDEN_TEXT_MARKERS
        if marker in lowered
    )

    if leaked_markers:

        raise ValueError(
            "Review or label metadata leaked into "
            f"model input: {leaked_markers}"
        )


    return text


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

            if key in FORBIDDEN_MODEL_INPUT_KEYS:

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


def derive_same_tool(
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


def review_note_for_pair(
    pair_id: str,
    master_by_id: dict[str, dict[str, str]],
    p1_by_id: dict[str, dict[str, str]],
) -> tuple[str, str]:

    if pair_id in P1_REPAIRED_PAIR_IDS:

        row = p1_by_id[
            pair_id
        ]

        return (
            row.get(
                "second_review_note",
                "",
            ),

            "human_review_p1_second_round",
        )


    row = master_by_id[
        pair_id
    ]

    return (
        row.get(
            "review_note",
            "",
        ),

        "human_review_first_round",
    )


def main() -> None:

    candidate_pairs = load_jsonl(
        CANDIDATE_PAIR_PLAN_PATH
    )

    source_rows = load_jsonl(
        SOURCE_SMOKE_POOL_PATH
    )

    (
        master_fieldnames,
        master_rows,
    ) = load_csv(
        MASTER_REVIEW_PATH
    )

    (
        _,
        p1_rows,
    ) = load_csv(
        P1_SECOND_REVIEW_PATH
    )


    if (
        len(candidate_pairs)
        !=
        EXPECTED_CANDIDATE_PAIR_COUNT
    ):
        raise ValueError(
            "Expected 100 candidate pairs, "
            f"found {len(candidate_pairs)}."
        )


    if (
        len(source_rows)
        !=
        EXPECTED_SOURCE_ROW_COUNT
    ):
        raise ValueError(
            "Expected 200 source smoke rows, "
            f"found {len(source_rows)}."
        )


    if len(master_rows) != 100:
        raise ValueError(
            "Expected 100 master-review rows, "
            f"found {len(master_rows)}."
        )


    pair_by_id = {
        str(
            pair[
                "pair_id"
            ]
        ): pair
        for pair in candidate_pairs
    }


    master_by_id = {
        str(
            row[
                "pair_id"
            ]
        ): row
        for row in master_rows
    }


    p1_by_id = {
        str(
            row[
                "pair_id"
            ]
        ): row
        for row in p1_rows
    }


    if (
        set(p1_by_id)
        !=
        P1_REPAIRED_PAIR_IDS
    ):
        raise ValueError(
            "Unexpected P1 second-review inventory.\n"
            f"Expected: {sorted(P1_REPAIRED_PAIR_IDS)}\n"
            f"Found: {sorted(p1_by_id)}"
        )


    first_round_approved_ids = {
        pair_id
        for pair_id, row in master_by_id.items()
        if row.get(
            "review_decision"
        )
        ==
        "approve_pair"
    }


    first_round_revision_ids = {
        pair_id
        for pair_id, row in master_by_id.items()
        if row.get(
            "review_decision"
        )
        ==
        "needs_revision"
    }


    first_round_excluded_ids = {
        pair_id
        for pair_id, row in master_by_id.items()
        if row.get(
            "review_decision"
        )
        ==
        "exclude_pair"
    }


    if (
        len(first_round_approved_ids)
        !=
        EXPECTED_FIRST_ROUND_APPROVED_PAIR_COUNT
    ):
        raise ValueError(
            "Expected 55 first-round approved pairs, "
            f"found {len(first_round_approved_ids)}."
        )


    if first_round_excluded_ids:

        raise ValueError(
            "Unexpected first-round exclusions: "
            f"{sorted(first_round_excluded_ids)}"
        )


    for pair_id in P1_REPAIRED_PAIR_IDS:

        if (
            pair_id
            not in
            first_round_revision_ids
        ):
            raise ValueError(
                f"P1 repaired pair was not originally "
                f"needs_revision: {pair_id}"
            )

        if (
            p1_by_id[
                pair_id
            ].get(
                "second_review_decision"
            )
            !=
            "approve_pair"
        ):
            raise ValueError(
                f"P1 pair has not passed second review: "
                f"{pair_id}"
            )


    approved_pair_ids = (
        first_round_approved_ids
        |
        P1_REPAIRED_PAIR_IDS
    )


    if (
        len(approved_pair_ids)
        !=
        EXPECTED_APPROVED_PAIR_COUNT
    ):
        raise ValueError(
            "Expected 60 cumulative approved pairs, "
            f"found {len(approved_pair_ids)}."
        )


    all_pair_ids = set(
        pair_by_id
    )

    pending_pair_ids = (
        all_pair_ids
        -
        approved_pair_ids
    )


    if (
        len(pending_pair_ids)
        !=
        EXPECTED_PENDING_PAIR_COUNT
    ):
        raise ValueError(
            "Expected 40 pending pairs, "
            f"found {len(pending_pair_ids)}."
        )


    # Use the existing v0.1.1 rows only as trusted
    # suite-level templates for agent and policy context.
    template_by_suite: dict[
        str,
        dict[str, Any],
    ] = {}


    for row in source_rows:

        suite = str(
            row[
                "suite"
            ]
        )

        if suite not in template_by_suite:

            template_by_suite[
                suite
            ] = row


    expected_suites = {
        "banking",
        "slack",
        "travel",
        "workspace",
    }

    if set(template_by_suite) != expected_suites:

        raise ValueError(
            "Unexpected smoke-pool suite inventory: "
            f"{sorted(template_by_suite)}"
        )


    materialized_rows: list[
        dict[str, Any]
    ] = []

    training_rows: list[
        dict[str, Any]
    ] = []

    rows_by_pair: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)


    variant_counts: Counter[
        str
    ] = Counter()

    final_label_counts: Counter[
        int
    ] = Counter()

    suite_pair_counts: Counter[
        str
    ] = Counter()

    suite_row_counts: Counter[
        str
    ] = Counter()

    binding_status_pair_counts: Counter[
        str
    ] = Counter()

    binding_type_pair_counts: Counter[
        str
    ] = Counter()

    model_input_lengths: list[
        int
    ] = []


    same_tool_approved_pair_count = 0

    concrete_binding_pair_ids = set()


    for pair_id in sorted(
        approved_pair_ids,
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

        suite_pair_counts[
            suite
        ] += 1


        template = template_by_suite[
            suite
        ]


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
            compose_retrieved_content(
                injection_surface.get(
                    "default_value"
                ),
                attacker_goal,
            )
        )


        binding = resolve_context_binding(
            pair
        )


        if binding[
            "retrieved_object_locator"
        ]:

            concrete_binding_pair_ids.add(
                pair_id
            )


        binding_status_pair_counts[
            binding[
                "binding_status"
            ]
        ] += 1

        binding_type_pair_counts[
            binding[
                "binding_type"
            ]
        ] += 1


        agent_context = deepcopy(
            template[
                "agent_context"
            ]
        )

        policy_context = deepcopy(
            template[
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


        authorized_action = compact_action(
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


        same_tool = derive_same_tool(
            pair
        )

        if same_tool:
            same_tool_approved_pair_count += 1


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


        shared_context_fingerprint = stable_hash(
            shared_context_payload
        )


        review_note, label_source = (
            review_note_for_pair(
                pair_id,
                master_by_id,
                p1_by_id,
            )
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

                "final_label": 0,

                "attempted_action": compact_action(
                    selected_actions[
                        "authorized_user_action"
                    ]
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

                "final_label": 1,

                "attempted_action": compact_action(
                    selected_actions[
                        "attacker_target_action"
                    ]
                ),
            },
        ]


        for variant_index, specification in enumerate(
            variant_specs,
            start=1,
        ):

            variant_name = specification[
                "name"
            ]

            attempted_action = specification[
                "attempted_action"
            ]

            final_label = int(
                specification[
                    "final_label"
                ]
            )


            event_id = (
                f"{pair_id}::"
                f"{variant_name}::action_attempt"
            )

            session_group_id = str(
                pair[
                    "session_group_id"
                ]
            )


            model_input_payload = {
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

                "attempted_action": (
                    attempted_action
                ),
            }


            forbidden_paths = find_forbidden_keys(
                model_input_payload
            )

            if forbidden_paths:

                raise ValueError(
                    "Forbidden review or label fields "
                    f"found for {event_id}: "
                    f"{forbidden_paths}"
                )


            model_input_text = (
                serialize_model_input(
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


            row = {
                "row_id": event_id,

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
                        structure_id(
                            legitimate_context
                        )
                    ),

                    "scenario_family": (
                        legitimate_context.get(
                            "scenario_family"
                        )
                    ),
                },

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
                        stable_hash(
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

                    "label_source": label_source,
                },

                "provenance": {
                    "source_pair_plan_version": (
                        pair.get(
                            "pair_plan_version",
                            "0.1",
                        )
                    ),

                    "active_pair_plan_artifact": (
                        "agentdojo_contextual_pair_plan_"
                        "v0.1.2_p1_repaired"
                    ),

                    "legitimate_structure_id": (
                        structure_id(
                            legitimate_context
                        )
                    ),

                    "attacker_structure_id": (
                        structure_id(
                            attacker_context
                        )
                    ),

                    "injection_vector_id": (
                        injection_surface[
                            "vector_id"
                        ]
                    ),

                    "same_tool_minimal_pair": (
                        same_tool
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
                        label_source
                    ),

                    "p1_repaired_pair": (
                        pair_id
                        in
                        P1_REPAIRED_PAIR_IDS
                    ),

                    "repair_metadata": (
                        pair.get(
                            "repair_metadata"
                        )
                    ),
                },

                "important_note": (
                    "This is a human-approved contextual "
                    "action.attempt row using serialization "
                    "v0.1.2. The final label is stored only "
                    "in review metadata and remains excluded "
                    "from model_input.text."
                ),
            }


            materialized_rows.append(
                row
            )

            rows_by_pair[
                pair_id
            ].append(
                row
            )

            variant_counts[
                variant_name
            ] += 1

            final_label_counts[
                final_label
            ] += 1

            suite_row_counts[
                suite
            ] += 1

            model_input_lengths.append(
                len(
                    model_input_text
                )
            )


            training_rows.append(
                {
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

                    "text_sha256": text_hash(
                        model_input_text
                    ),

                    "label_source": (
                        label_source
                    ),

                    "schema_version": (
                        "bert_training_view_v0.1.2"
                    ),
                }
            )


    # --------------------------------------------------------
    # Structural validation
    # --------------------------------------------------------

    if (
        len(materialized_rows)
        !=
        EXPECTED_RUNTIME_ROW_COUNT
    ):
        raise ValueError(
            "Expected 120 runtime rows, "
            f"found {len(materialized_rows)}."
        )


    if variant_counts != {
        "safe": EXPECTED_SAFE_ROW_COUNT,
        "risky": EXPECTED_RISKY_ROW_COUNT,
    }:
        raise ValueError(
            "Unexpected variant counts: "
            f"{dict(variant_counts)}"
        )


    if final_label_counts != {
        0: EXPECTED_SAFE_ROW_COUNT,
        1: EXPECTED_RISKY_ROW_COUNT,
    }:
        raise ValueError(
            "Unexpected final-label counts: "
            f"{dict(final_label_counts)}"
        )


    if (
        same_tool_approved_pair_count
        !=
        EXPECTED_SAME_TOOL_APPROVED_PAIR_COUNT
    ):
        raise ValueError(
            "Expected 17 same-tool approved pairs, "
            f"found {same_tool_approved_pair_count}."
        )


    row_ids = [
        row[
            "row_id"
        ]
        for row in materialized_rows
    ]

    if len(row_ids) != len(
        set(row_ids)
    ):
        raise ValueError(
            "Duplicate row_id detected."
        )


    shared_context_passed = 0
    attempted_action_passed = 0
    group_integrity_passed = 0
    label_pair_passed = 0


    for pair_id, pair_rows in rows_by_pair.items():

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
                "Shared context differs across "
                f"variants for {pair_id}."
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
                "Attempted actions are identical "
                f"for {pair_id}."
            )

        attempted_action_passed += 1


        session_groups = {
            row[
                "session_group_id"
            ]
            for row in pair_rows
        }

        if len(session_groups) != 1:

            raise ValueError(
                "Pair variants have different "
                f"session_group_id values: {pair_id}"
            )

        group_integrity_passed += 1


        pair_labels = {
            int(
                row[
                    "review"
                ][
                    "final_binary_label"
                ]
            )
            for row in pair_rows
        }

        if pair_labels != {
            0,
            1,
        }:

            raise ValueError(
                f"{pair_id} does not contain "
                "one final label 0 and one 1."
            )

        label_pair_passed += 1


        safe_row = next(
            row
            for row in pair_rows
            if row[
                "variant"
            ][
                "name"
            ]
            ==
            "safe"
        )

        risky_row = next(
            row
            for row in pair_rows
            if row[
                "variant"
            ][
                "name"
            ]
            ==
            "risky"
        )


        if (
            safe_row[
                "review"
            ][
                "final_binary_label"
            ]
            !=
            0
        ):
            raise ValueError(
                f"Safe row has wrong label: {pair_id}"
            )


        if (
            risky_row[
                "review"
            ][
                "final_binary_label"
            ]
            !=
            1
        ):
            raise ValueError(
                f"Risky row has wrong label: {pair_id}"
            )


    model_input_texts = [
        row[
            "model_input"
        ][
            "text"
        ]
        for row in materialized_rows
    ]


    duplicate_model_input_count = (
        len(model_input_texts)
        -
        len(
            set(model_input_texts)
        )
    )


    if (
        duplicate_model_input_count
        !=
        EXPECTED_DUPLICATE_MODEL_INPUT_COUNT
    ):

        duplicate_groups: dict[
            str,
            list[str],
        ] = defaultdict(list)

        for row in materialized_rows:

            duplicate_groups[
                row[
                    "model_input"
                ][
                    "text"
                ]
            ].append(
                row[
                    "row_id"
                ]
            )


        duplicates = [
            row_ids
            for row_ids in duplicate_groups.values()
            if len(row_ids) > 1
        ]


        raise ValueError(
            "Exact duplicate model inputs detected.\n"
            f"Excess count: "
            f"{duplicate_model_input_count}\n"
            f"Groups: {duplicates}"
        )


    leakage_violation_rows = []


    for row in materialized_rows:

        lowered_text = (
            row[
                "model_input"
            ][
                "text"
            ].lower()
        )

        leaked_markers = sorted(
            marker
            for marker in FORBIDDEN_TEXT_MARKERS
            if marker in lowered_text
        )

        if leaked_markers:

            leakage_violation_rows.append(
                {
                    "row_id": row[
                        "row_id"
                    ],

                    "markers": leaked_markers,
                }
            )


    if leakage_violation_rows:

        raise ValueError(
            "Label/review leakage detected:\n"
            f"{leakage_violation_rows}"
        )


    output_pair_ids = {
        row[
            "pair_id"
        ]
        for row in materialized_rows
    }


    if output_pair_ids != approved_pair_ids:

        raise ValueError(
            "Output pair inventory does not match "
            "the cumulative approved inventory."
        )


    if output_pair_ids & pending_pair_ids:

        raise ValueError(
            "Pending pairs were included in the "
            "labeled output."
        )


    # --------------------------------------------------------
    # Build cumulative pair-level review ledger
    # --------------------------------------------------------

    cumulative_columns = [
        "cumulative_review_decision",
        "cumulative_human_review_status",
        "cumulative_review_round",
        "cumulative_safe_label_final",
        "cumulative_risky_label_final",
        "label_eligible",
        "active_legitimate_structure_id",
        "active_attacker_structure_id",
        "active_vector_id",
        "active_source_locator",
        "active_binding_type",
        "active_binding_status",
    ]


    cumulative_fieldnames = list(
        master_fieldnames
    )

    for column in cumulative_columns:

        if column not in cumulative_fieldnames:

            cumulative_fieldnames.append(
                column
            )


    cumulative_review_rows = []


    for master_row in master_rows:

        pair_id = str(
            master_row[
                "pair_id"
            ]
        )

        pair = pair_by_id[
            pair_id
        ]

        binding = resolve_context_binding(
            pair
        )

        output_row = dict(
            master_row
        )


        if pair_id in first_round_approved_ids:

            cumulative_decision = (
                "approve_pair"
            )

            cumulative_status = (
                "human_reviewed_approved"
            )

            cumulative_round = (
                "first_human_review"
            )

            safe_label = "0"
            risky_label = "1"
            label_eligible = "true"


        elif pair_id in P1_REPAIRED_PAIR_IDS:

            cumulative_decision = (
                "approve_pair"
            )

            cumulative_status = (
                "human_reviewed_approved_after_p1_repair"
            )

            cumulative_round = (
                "p1_second_human_review"
            )

            safe_label = "0"
            risky_label = "1"
            label_eligible = "true"


        else:

            cumulative_decision = (
                "needs_revision"
            )

            cumulative_status = (
                "human_reviewed_needs_revision"
            )

            cumulative_round = (
                "awaiting_p2_or_p3_repair"
            )

            safe_label = ""
            risky_label = ""
            label_eligible = "false"


        output_row[
            "cumulative_review_decision"
        ] = cumulative_decision

        output_row[
            "cumulative_human_review_status"
        ] = cumulative_status

        output_row[
            "cumulative_review_round"
        ] = cumulative_round

        output_row[
            "cumulative_safe_label_final"
        ] = safe_label

        output_row[
            "cumulative_risky_label_final"
        ] = risky_label

        output_row[
            "label_eligible"
        ] = label_eligible

        output_row[
            "active_legitimate_structure_id"
        ] = structure_id(
            pair[
                "legitimate_context"
            ]
        )

        output_row[
            "active_attacker_structure_id"
        ] = structure_id(
            pair[
                "attacker_context"
            ]
        )

        output_row[
            "active_vector_id"
        ] = pair[
            "injection_surface"
        ][
            "vector_id"
        ]

        output_row[
            "active_source_locator"
        ] = (
            binding[
                "retrieved_object_locator"
            ]
            or
            ""
        )

        output_row[
            "active_binding_type"
        ] = binding[
            "binding_type"
        ]

        output_row[
            "active_binding_status"
        ] = binding[
            "binding_status"
        ]


        cumulative_review_rows.append(
            output_row
        )


    cumulative_review_rows.sort(
        key=lambda row: pair_number(
            row[
                "pair_id"
            ]
        )
    )


    cumulative_decision_counts = Counter(
        row[
            "cumulative_review_decision"
        ]
        for row in cumulative_review_rows
    )


    if cumulative_decision_counts != {
        "approve_pair": (
            EXPECTED_APPROVED_PAIR_COUNT
        ),

        "needs_revision": (
            EXPECTED_PENDING_PAIR_COUNT
        ),
    }:

        raise ValueError(
            "Unexpected cumulative review counts: "
            f"{dict(cumulative_decision_counts)}"
        )


    # --------------------------------------------------------
    # Write artifacts
    # --------------------------------------------------------

    write_jsonl(
        OUTPUT_STRUCTURED_POOL_PATH,
        materialized_rows,
    )

    write_jsonl(
        OUTPUT_TRAINING_VIEW_PATH,
        training_rows,
    )

    write_csv(
        OUTPUT_CUMULATIVE_REVIEW_PATH,
        cumulative_fieldnames,
        cumulative_review_rows,
    )


    generated_at = datetime.now(
        timezone.utc
    ).isoformat()


    report = {
        "dataset": "agentdojo",

        "artifact_version": "0.1.2",

        "generated_at": generated_at,

        "artifact_status": (
            "human_reviewed_approved_subset"
        ),

        "candidate_pair_plan": str(
            CANDIDATE_PAIR_PLAN_PATH
        ),

        "source_smoke_pool": str(
            SOURCE_SMOKE_POOL_PATH
        ),

        "structured_labeled_pool": str(
            OUTPUT_STRUCTURED_POOL_PATH
        ),

        "bert_training_view": str(
            OUTPUT_TRAINING_VIEW_PATH
        ),

        "cumulative_review_ledger": str(
            OUTPUT_CUMULATIVE_REVIEW_PATH
        ),

        "candidate_pair_count": len(
            candidate_pairs
        ),

        "approved_pair_count": len(
            approved_pair_ids
        ),

        "first_round_approved_pair_count": len(
            first_round_approved_ids
        ),

        "p1_repaired_approved_pair_count": len(
            P1_REPAIRED_PAIR_IDS
        ),

        "remaining_needs_revision_pair_count": len(
            pending_pair_ids
        ),

        "excluded_pair_count": (
            EXPECTED_EXCLUDED_PAIR_COUNT
        ),

        "runtime_row_count": len(
            materialized_rows
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

        "suite_pair_counts": dict(
            sorted(
                suite_pair_counts.items()
            )
        ),

        "suite_row_counts": dict(
            sorted(
                suite_row_counts.items()
            )
        ),

        "same_tool_approved_pair_count": (
            same_tool_approved_pair_count
        ),

        "same_tool_approved_runtime_row_count": (
            same_tool_approved_pair_count
            *
            2
        ),

        "concrete_source_binding_pair_count": len(
            concrete_binding_pair_ids
        ),

        "concrete_source_binding_pair_ids": sorted(
            concrete_binding_pair_ids,
            key=pair_number,
        ),

        "binding_status_pair_counts": dict(
            binding_status_pair_counts
        ),

        "binding_type_pair_counts": dict(
            binding_type_pair_counts
        ),

        "unique_model_input_count": len(
            set(model_input_texts)
        ),

        "duplicate_model_input_count": (
            duplicate_model_input_count
        ),

        "label_or_review_leakage_count": len(
            leakage_violation_rows
        ),

        "shared_context_pair_validation": {
            "passed": shared_context_passed,
            "failed": 0,
        },

        "distinct_attempted_action_validation": {
            "passed": attempted_action_passed,
            "failed": 0,
        },

        "session_group_integrity_validation": {
            "passed": group_integrity_passed,
            "failed": 0,
        },

        "safe_risky_label_pair_validation": {
            "passed": label_pair_passed,
            "failed": 0,
        },

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

        "approved_pair_ids": sorted(
            approved_pair_ids,
            key=pair_number,
        ),

        "remaining_revision_pair_ids": sorted(
            pending_pair_ids,
            key=pair_number,
        ),

        "important_notes": [
            (
                "Only human-approved pairs are included "
                "in the structured labeled pool and BERT "
                "training view."
            ),

            (
                "The 40 pairs still awaiting P2 or P3 "
                "repair are excluded from the labeled "
                "artifacts."
            ),

            (
                "Each approved pair contributes one safe "
                "label-0 row and one risky label-1 row."
            ),

            (
                "Final labels exist only in review metadata "
                "and the separate training target field."
            ),

            (
                "Final labels, review decisions, risk scores, "
                "and policy-engine outputs remain excluded "
                "from model_input.text."
            ),

            (
                "Both rows belonging to a pair share the same "
                "session_group_id and must remain together "
                "during dataset splitting."
            ),

            (
                "The source v0.1.1 smoke pool, original pair "
                "plan, and original human-review ledger were "
                "not modified."
            ),
        ],
    }


    REPORT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

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
        "v0.1.2 MATERIALIZED"
    )
    print("=" * 80)

    print()
    print(
        "Candidate pairs:",
        len(candidate_pairs),
    )

    print(
        "Approved pairs materialized:",
        len(approved_pair_ids),
    )

    print(
        "Pending pairs excluded:",
        len(pending_pair_ids),
    )

    print(
        "Excluded pairs:",
        EXPECTED_EXCLUDED_PAIR_COUNT,
    )

    print()
    print(
        "Runtime rows:",
        len(materialized_rows),
    )

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
        same_tool_approved_pair_count,
    )

    print(
        "Concrete binding pairs:",
        len(concrete_binding_pair_ids),
    )

    print()
    print(
        "Shared-context validation:",
        f"{shared_context_passed} / "
        f"{len(approved_pair_ids)} pairs passed",
    )

    print(
        "Distinct attempted-action validation:",
        f"{attempted_action_passed} / "
        f"{len(approved_pair_ids)} pairs passed",
    )

    print(
        "Session-group integrity:",
        f"{group_integrity_passed} / "
        f"{len(approved_pair_ids)} pairs passed",
    )

    print(
        "Safe/risky label-pair validation:",
        f"{label_pair_passed} / "
        f"{len(approved_pair_ids)} pairs passed",
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
        "Label/review leakage violations:",
        len(leakage_violation_rows),
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
        f"{OUTPUT_CUMULATIVE_REVIEW_PATH}"
    )

    print(
        f"Report: {REPORT_PATH}"
    )

    print()
    print(
        "Original smoke pool modified: no"
    )

    print(
        "Original review ledger modified: no"
    )

    print(
        "Candidate pair plan modified: no"
    )


if __name__ == "__main__":
    main()

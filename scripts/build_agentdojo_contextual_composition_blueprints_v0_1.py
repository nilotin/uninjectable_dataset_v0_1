from __future__ import annotations

import csv
import json
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

STRUCTURE_PATH = (
    PROCESSED_DIR /
    "agentdojo_combined_structure_pool_v0.1.jsonl"
)

TOOL_CATALOG_PATH = (
    PROCESSED_DIR /
    "agentdojo_curated_suite_tool_catalog_v0.1.jsonl"
)

VECTOR_CATALOG_PATH = (
    PROCESSED_DIR /
    "agentdojo_curated_injection_vector_catalog_v0.1.jsonl"
)

ENVIRONMENT_TEMPLATE_PATH = (
    PROCESSED_DIR /
    "agentdojo_suite_environment_template_catalog_v0.1.jsonl"
)

BLUEPRINT_PATH = (
    PROCESSED_DIR /
    "agentdojo_contextual_composition_blueprint_pool_v0.1.jsonl"
)

AUDIT_CSV_PATH = (
    INTERIM_DIR /
    "agentdojo_contextual_composition_blueprint_audit_v0.1.csv"
)

REPORT_PATH = (
    PROCESSED_DIR /
    "agentdojo_contextual_composition_blueprint_pool_v0.1_report.json"
)


EXPECTED_STRUCTURE_COUNT = 117
EXPECTED_TOOL_INSTANCE_COUNT = 74
EXPECTED_VECTOR_COUNT = 39
EXPECTED_SEQUENCE_RECORD_COUNT = 108
EXPECTED_EMPTY_SEQUENCE_COUNT = 9
EXPECTED_ACTION_STEP_COUNT = 315

EXPECTED_SUITE_STRUCTURE_COUNTS = {
    "banking": 24,
    "slack": 20,
    "travel": 26,
    "workspace": 47,
}

EXPECTED_TASK_KIND_COUNTS = {
    "user_task": 82,
    "injection_task": 35,
}

EXPECTED_SUITE_TOOL_COUNTS = {
    "banking": 11,
    "slack": 11,
    "travel": 28,
    "workspace": 24,
}

EXPECTED_SUITE_VECTOR_COUNTS = {
    "banking": 4,
    "slack": 6,
    "travel": 13,
    "workspace": 16,
}

FORBIDDEN_RUNTIME_KEYS = {
    "general_risk_label",
    "ml_risk_score",
    "risk_score",
    "runtime_decision",
    "policy_output",
}


IMPACT_RANK = {
    "low": 1,
    "medium": 2,
    "high": 3,
}


def load_jsonl(
    path: Path,
) -> list[dict[str, Any]]:

    if not path.exists():
        raise FileNotFoundError(
            f"Missing input file: {path}"
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
            f"Cannot write an empty CSV: {path}"
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


def safe_int(
    value: Any,
    fallback: int = 1_000_000,
) -> int:

    try:
        return int(value)
    except (
        TypeError,
        ValueError,
    ):
        return fallback


def argument_representation(
    value: Any,
) -> str:

    if value is None:
        return "absent"

    if isinstance(
        value,
        dict,
    ):
        return "resolved_mapping"

    if isinstance(
        value,
        str,
    ):
        return "upstream_expression_string"

    if isinstance(
        value,
        list,
    ):
        return "resolved_list"

    return (
        f"resolved_{type(value).__name__}"
    )


def compact_tool_record(
    record: dict[str, Any],
) -> dict[str, Any]:

    human_review = record.get(
        "human_review",
        {},
    )

    return {
        "tool_name": record[
            "tool_name"
        ],

        "tool_position": record.get(
            "tool_position"
        ),

        "description": record.get(
            "description"
        ),

        "public_parameters": record.get(
            "public_parameters",
            [],
        ),

        "environment_dependencies": record.get(
            "environment_dependencies",
            [],
        ),

        "return_annotation": record.get(
            "return_annotation"
        ),

        "capability_class": human_review.get(
            "capability_class"
        ),

        "action_impact": human_review.get(
            "action_impact"
        ),

        "capability_review_decision": (
            human_review.get(
                "review_decision"
            )
        ),

        "implementation": {
            "file": record.get(
                "implementation_file"
            ),

            "source_line": record.get(
                "source_line"
            ),
        },
    }


def compact_vector_record(
    record: dict[str, Any],
) -> dict[str, Any]:

    human_review = record.get(
        "human_review",
        {},
    )

    composition_metadata = record.get(
        "composition_metadata",
        {},
    )

    return {
        "vector_id": record[
            "vector_id"
        ],

        "description": record.get(
            "description"
        ),

        "default_value": record.get(
            "default_value"
        ),

        "surface_type": human_review.get(
            "surface_type"
        ),

        "source_type": human_review.get(
            "source_type"
        ),

        "trust_level": human_review.get(
            "trust_level"
        ),

        "retrieval_channel": (
            composition_metadata.get(
                "retrieval_channel"
            )
        ),

        "environment_locations": record.get(
            "locations",
            [],
        ),

        "surface_review_decision": (
            human_review.get(
                "review_decision"
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

            if key in FORBIDDEN_RUNTIME_KEYS:
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


def maximum_impact(
    impacts: list[str],
) -> str | None:

    valid_impacts = [
        impact
        for impact in impacts
        if impact in IMPACT_RANK
    ]

    if not valid_impacts:
        return None

    return max(
        valid_impacts,
        key=lambda impact: (
            IMPACT_RANK[impact]
        ),
    )


def main() -> None:

    structures = load_jsonl(
        STRUCTURE_PATH
    )

    tool_instances = load_jsonl(
        TOOL_CATALOG_PATH
    )

    vectors = load_jsonl(
        VECTOR_CATALOG_PATH
    )


    # --------------------------------------------------------
    # Input validation
    # --------------------------------------------------------

    if len(structures) != (
        EXPECTED_STRUCTURE_COUNT
    ):
        raise ValueError(
            "Expected "
            f"{EXPECTED_STRUCTURE_COUNT} structures, "
            f"found {len(structures)}."
        )

    if len(tool_instances) != (
        EXPECTED_TOOL_INSTANCE_COUNT
    ):
        raise ValueError(
            "Expected "
            f"{EXPECTED_TOOL_INSTANCE_COUNT} "
            "suite tool instances, found "
            f"{len(tool_instances)}."
        )

    if len(vectors) != (
        EXPECTED_VECTOR_COUNT
    ):
        raise ValueError(
            "Expected "
            f"{EXPECTED_VECTOR_COUNT} vectors, "
            f"found {len(vectors)}."
        )


    structure_ids = [
        str(
            record["structure_id"]
        )
        for record in structures
    ]

    if len(
        set(structure_ids)
    ) != len(
        structure_ids
    ):
        raise ValueError(
            "Duplicate structure_id detected."
        )


    # --------------------------------------------------------
    # Tool indexes
    # --------------------------------------------------------

    tool_lookup: dict[
        tuple[str, str],
        dict[str, Any],
    ] = {}

    tools_by_suite: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)


    for record in tool_instances:

        suite = str(
            record["suite"]
        )

        tool_name = str(
            record["tool_name"]
        )

        key = (
            suite,
            tool_name,
        )

        if key in tool_lookup:
            raise ValueError(
                "Duplicate suite-level tool: "
                f"{suite}:{tool_name}"
            )

        tool_lookup[key] = record

        tools_by_suite[
            suite
        ].append(record)


    for suite in tools_by_suite:

        tools_by_suite[
            suite
        ].sort(
            key=lambda record: (
                safe_int(
                    record.get(
                        "tool_position"
                    )
                ),
                str(
                    record[
                        "tool_name"
                    ]
                ),
            )
        )


    actual_suite_tool_counts = {
        suite: len(records)
        for suite, records
        in tools_by_suite.items()
    }

    if (
        actual_suite_tool_counts
        !=
        EXPECTED_SUITE_TOOL_COUNTS
    ):
        raise ValueError(
            "Unexpected suite tool counts.\n"
            f"Expected: "
            f"{EXPECTED_SUITE_TOOL_COUNTS}\n"
            f"Found: "
            f"{actual_suite_tool_counts}"
        )


    # --------------------------------------------------------
    # Injection-vector indexes
    # --------------------------------------------------------

    vectors_by_suite: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)

    vector_keys: set[
        tuple[str, str]
    ] = set()


    for record in vectors:

        suite = str(
            record["suite"]
        )

        vector_id = str(
            record["vector_id"]
        )

        key = (
            suite,
            vector_id,
        )

        if key in vector_keys:
            raise ValueError(
                "Duplicate injection vector: "
                f"{suite}:{vector_id}"
            )

        vector_keys.add(
            key
        )

        vectors_by_suite[
            suite
        ].append(record)


    for suite in vectors_by_suite:

        vectors_by_suite[
            suite
        ].sort(
            key=lambda record: str(
                record[
                    "vector_id"
                ]
            )
        )


    actual_suite_vector_counts = {
        suite: len(records)
        for suite, records
        in vectors_by_suite.items()
    }

    if (
        actual_suite_vector_counts
        !=
        EXPECTED_SUITE_VECTOR_COUNTS
    ):
        raise ValueError(
            "Unexpected suite vector counts.\n"
            f"Expected: "
            f"{EXPECTED_SUITE_VECTOR_COUNTS}\n"
            f"Found: "
            f"{actual_suite_vector_counts}"
        )


    # --------------------------------------------------------
    # Build four canonical suite environment templates
    # --------------------------------------------------------

    environment_templates: list[
        dict[str, Any]
    ] = []

    environment_template_lookup: dict[
        str,
        dict[str, Any],
    ] = {}


    for suite in sorted(
        EXPECTED_SUITE_TOOL_COUNTS
    ):

        template_id = (
            f"agentdojo_{suite}_"
            "environment_template_v0.1"
        )

        available_tools = [
            compact_tool_record(
                record
            )
            for record
            in tools_by_suite[suite]
        ]

        candidate_surfaces = [
            compact_vector_record(
                record
            )
            for record
            in vectors_by_suite[suite]
        ]

        template = {
            "environment_template_id": (
                template_id
            ),

            "suite": suite,

            "benchmark_version": (
                "v1.2.2"
            ),

            "available_tool_count": (
                len(available_tools)
            ),

            "available_tools": (
                available_tools
            ),

            "candidate_injection_surface_count": (
                len(candidate_surfaces)
            ),

            "candidate_injection_surfaces": (
                candidate_surfaces
            ),

            "composition_status": (
                "environment_template_only"
            ),

            "important_notes": [
                (
                    "Candidate injection surfaces are "
                    "suite-level options. No surface has "
                    "yet been assigned to a contextual "
                    "runtime scenario."
                ),
                (
                    "Tool capability and action impact "
                    "are stable metadata, not runtime "
                    "general_risk_label values."
                ),
                (
                    "Trust level describes source "
                    "provenance rather than whether a "
                    "particular payload is malicious."
                ),
            ],
        }

        environment_templates.append(
            template
        )

        environment_template_lookup[
            suite
        ] = template


    # --------------------------------------------------------
    # Build structure-level composition blueprints
    # --------------------------------------------------------

    blueprints: list[
        dict[str, Any]
    ] = []

    audit_rows: list[
        dict[str, Any]
    ] = []

    missing_referenced_tools: list[
        dict[str, str]
    ] = []

    sequence_record_count = 0
    empty_sequence_count = 0
    action_step_count = 0

    evaluation_mode_counts: Counter[
        str
    ] = Counter()

    sequence_status_counts: Counter[
        str
    ] = Counter()

    task_kind_counts: Counter[
        str
    ] = Counter()

    suite_structure_counts: Counter[
        str
    ] = Counter()

    structure_role_counts: Counter[
        str
    ] = Counter()

    scenario_families: set[
        str
    ] = set()


    for structure in structures:

        structure_id = str(
            structure[
                "structure_id"
            ]
        )

        suite = str(
            structure[
                "suite"
            ]
        )

        task_kind = str(
            structure[
                "task_kind"
            ]
        )

        structure_role = str(
            structure[
                "structure_role"
            ]
        )

        curation = structure.get(
            "curation",
            {},
        )

        if (
            curation.get(
                "include_for_composition"
            )
            is False
        ):
            raise ValueError(
                "Combined pool contains an excluded "
                f"structure: {structure_id}"
            )


        top_level_sequence = structure.get(
            "expected_action_sequence",
            [],
        )

        execution_semantics = structure.get(
            "execution_semantics",
            {},
        )

        nested_sequence = (
            execution_semantics.get(
                "reference_action_sequence",
                [],
            )
        )


        if (
            top_level_sequence
            !=
            nested_sequence
        ):
            raise ValueError(
                "Top-level and nested action sequences "
                f"do not match for {structure_id}."
            )


        referenced_function_names = (
            structure.get(
                "referenced_function_names",
                [],
            )
        )

        sequence_function_names = [
            str(
                step.get(
                    "normalized_function_name"
                )
                or
                step.get(
                    "function"
                )
            )
            for step in top_level_sequence
        ]


        if (
            sequence_function_names
            !=
            referenced_function_names
        ):
            raise ValueError(
                "referenced_function_names does not "
                "match expected_action_sequence for "
                f"{structure_id}.\n"
                f"Sequence: "
                f"{sequence_function_names}\n"
                f"Referenced: "
                f"{referenced_function_names}"
            )


        if top_level_sequence:
            sequence_record_count += 1
        else:
            empty_sequence_count += 1


        enriched_sequence: list[
            dict[str, Any]
        ] = []

        referenced_tool_summary: list[
            dict[str, Any]
        ] = []

        summary_lookup: dict[
            str,
            dict[str, Any],
        ] = {}


        for step in top_level_sequence:

            action_step_count += 1

            function_name = str(
                step.get(
                    "normalized_function_name"
                )
                or
                step.get(
                    "function"
                )
            )

            tool_key = (
                suite,
                function_name,
            )

            tool_record = tool_lookup.get(
                tool_key
            )

            if tool_record is None:

                missing_referenced_tools.append(
                    {
                        "structure_id": (
                            structure_id
                        ),
                        "suite": suite,
                        "tool_name": (
                            function_name
                        ),
                    }
                )

                continue


            human_review = tool_record.get(
                "human_review",
                {},
            )

            capability_class = (
                human_review.get(
                    "capability_class"
                )
            )

            action_impact = (
                human_review.get(
                    "action_impact"
                )
            )


            enriched_step = dict(
                step
            )

            enriched_step[
                "argument_representation"
            ] = argument_representation(
                step.get(
                    "args"
                )
            )

            enriched_step[
                "placeholder_argument_representation"
            ] = argument_representation(
                step.get(
                    "placeholder_args"
                )
            )

            enriched_step[
                "tool_metadata"
            ] = {
                "capability_class": (
                    capability_class
                ),

                "action_impact": (
                    action_impact
                ),

                "review_decision": (
                    human_review.get(
                        "review_decision"
                    )
                ),

                "label_source": (
                    "human_review"
                ),
            }

            enriched_sequence.append(
                enriched_step
            )


            if (
                function_name
                not in
                summary_lookup
            ):

                summary = {
                    "tool_name": (
                        function_name
                    ),

                    "sequence_positions": [],

                    "capability_class": (
                        capability_class
                    ),

                    "action_impact": (
                        action_impact
                    ),
                }

                summary_lookup[
                    function_name
                ] = summary

                referenced_tool_summary.append(
                    summary
                )


            summary_lookup[
                function_name
            ][
                "sequence_positions"
            ].append(
                step.get(
                    "sequence_position"
                )
            )


        referenced_impacts = [
            str(
                record.get(
                    "action_impact"
                )
            )
            for record
            in referenced_tool_summary
        ]


        environment_template = (
            environment_template_lookup[
                suite
            ]
        )

        scenario_family = str(
            curation.get(
                "scenario_family",
                ""
            )
        )

        if scenario_family:
            scenario_families.add(
                scenario_family
            )


        evaluation_mode = str(
            execution_semantics.get(
                "evaluation_mode",
                ""
            )
        )

        sequence_status = str(
            execution_semantics.get(
                "reference_action_sequence_status",
                ""
            )
        )


        blueprint = {
            "blueprint_id": (
                f"composition_blueprint::"
                f"{structure_id}"
            ),

            "blueprint_version": (
                "0.1"
            ),

            "scenario_source": (
                "agentdojo"
            ),

            "suite": suite,

            "structure": {
                "structure_id": (
                    structure_id
                ),

                "structure_role": (
                    structure_role
                ),

                "task_kind": (
                    task_kind
                ),

                "task_id": structure.get(
                    "task_id"
                ),

                "task_number": structure.get(
                    "task_number"
                ),

                "prompt_or_goal": (
                    structure.get(
                        "prompt_or_goal"
                    )
                ),

                "comment": structure.get(
                    "comment"
                ),

                "difficulty_expression": (
                    structure.get(
                        "difficulty_expression"
                    )
                ),

                "composition_role": (
                    structure.get(
                        "composition_role"
                    )
                ),

                "curation": curation,

                "source": structure.get(
                    "source",
                    {},
                ),

                "important_note": (
                    structure.get(
                        "important_note"
                    )
                ),
            },

            "suite_environment": {
                "environment_template_id": (
                    environment_template[
                        "environment_template_id"
                    ]
                ),

                "available_tool_count": (
                    environment_template[
                        "available_tool_count"
                    ]
                ),

                "available_tool_names": [
                    record[
                        "tool_name"
                    ]
                    for record
                    in environment_template[
                        "available_tools"
                    ]
                ],

                "candidate_injection_surface_count": (
                    environment_template[
                        "candidate_injection_surface_count"
                    ]
                ),

                "candidate_injection_vector_ids": [
                    record[
                        "vector_id"
                    ]
                    for record
                    in environment_template[
                        "candidate_injection_surfaces"
                    ]
                ],

                "injection_surface_assignment_status": (
                    "not_assigned"
                ),
            },

            "action_semantics": {
                "evaluation_mode": (
                    evaluation_mode
                ),

                "reference_action_sequence_status": (
                    sequence_status
                ),

                "reference_action_sequence": (
                    enriched_sequence
                ),

                "reference_action_step_count": (
                    len(
                        enriched_sequence
                    )
                ),

                "referenced_tools": (
                    referenced_tool_summary
                ),

                "maximum_referenced_action_impact": (
                    maximum_impact(
                        referenced_impacts
                    )
                ),

                "operational_effects": (
                    execution_semantics.get(
                        "operational_effects",
                        [],
                    )
                ),

                "semantic_action_candidates": (
                    execution_semantics.get(
                        "semantic_action_candidates",
                        [],
                    )
                ),

                "operational_effect_source": (
                    execution_semantics.get(
                        "operational_effect_source"
                    )
                ),

                "sequence_note": (
                    execution_semantics.get(
                        "sequence_note"
                    )
                ),

                "important_note": (
                    "String action arguments are retained "
                    "as upstream Python expressions and "
                    "must not be evaluated as code."
                ),
            },

            "pairing_metadata": {
                "pair_within_suite_only": True,

                "eligible_as_legitimate_base_context": (
                    task_kind
                    ==
                    "user_task"
                ),

                "eligible_as_adversarial_goal": (
                    task_kind
                    ==
                    "injection_task"
                ),

                "scenario_family": (
                    scenario_family
                    or
                    None
                ),

                "quality_tier": (
                    curation.get(
                        "quality_tier"
                    )
                ),
            },

            "composition_state": {
                "status": (
                    "blueprint_only"
                ),

                "runtime_training_row_created": (
                    False
                ),

                "training_row_unit": (
                    "action.attempt"
                ),

                "retrieved_content_status": (
                    "not_composed"
                ),

                "authorization_context_status": (
                    "not_composed"
                ),

                "policy_context_status": (
                    "not_composed"
                ),

                "attempted_action_status": (
                    "not_composed"
                ),

                "general_risk_label_status": (
                    "not_assigned"
                ),

                "important_notes": [
                    (
                        "The structure role, source trust, "
                        "tool capability, and action impact "
                        "must not independently determine "
                        "the runtime label."
                    ),
                    (
                        "A runtime label may be assigned "
                        "only after user intent, retrieved "
                        "content, authorization, policy, "
                        "and attempted action are composed."
                    ),
                    (
                        "The deterministic policy engine "
                        "remains responsible for the final "
                        "allow, review, or block decision."
                    ),
                ],
            },
        }


        forbidden_paths = find_forbidden_keys(
            blueprint
        )

        if forbidden_paths:
            raise ValueError(
                "Forbidden runtime-output fields were "
                f"generated for {structure_id}: "
                f"{forbidden_paths}"
            )


        blueprints.append(
            blueprint
        )


        audit_rows.append(
            {
                "blueprint_id": (
                    blueprint[
                        "blueprint_id"
                    ]
                ),

                "structure_id": (
                    structure_id
                ),

                "suite": suite,

                "task_kind": task_kind,

                "structure_role": (
                    structure_role
                ),

                "scenario_family": (
                    scenario_family
                ),

                "quality_tier": (
                    curation.get(
                        "quality_tier",
                        "",
                    )
                ),

                "evaluation_mode": (
                    evaluation_mode
                ),

                "reference_sequence_status": (
                    sequence_status
                ),

                "reference_action_step_count": (
                    len(
                        enriched_sequence
                    )
                ),

                "referenced_function_names": (
                    json.dumps(
                        referenced_function_names,
                        ensure_ascii=False,
                    )
                ),

                "maximum_referenced_action_impact": (
                    maximum_impact(
                        referenced_impacts
                    )
                    or
                    ""
                ),

                "environment_template_id": (
                    environment_template[
                        "environment_template_id"
                    ]
                ),

                "available_tool_count": (
                    environment_template[
                        "available_tool_count"
                    ]
                ),

                "candidate_injection_surface_count": (
                    environment_template[
                        "candidate_injection_surface_count"
                    ]
                ),

                "runtime_label_status": (
                    "not_assigned"
                ),
            }
        )


        task_kind_counts[
            task_kind
        ] += 1

        suite_structure_counts[
            suite
        ] += 1

        structure_role_counts[
            structure_role
        ] += 1

        evaluation_mode_counts[
            evaluation_mode
        ] += 1

        sequence_status_counts[
            sequence_status
        ] += 1


    # --------------------------------------------------------
    # Final validation
    # --------------------------------------------------------

    if missing_referenced_tools:
        raise ValueError(
            "Referenced tools missing from curated "
            f"suite catalog: {missing_referenced_tools}"
        )

    if sequence_record_count != (
        EXPECTED_SEQUENCE_RECORD_COUNT
    ):
        raise ValueError(
            "Expected "
            f"{EXPECTED_SEQUENCE_RECORD_COUNT} "
            "records with explicit sequence, found "
            f"{sequence_record_count}."
        )

    if empty_sequence_count != (
        EXPECTED_EMPTY_SEQUENCE_COUNT
    ):
        raise ValueError(
            "Expected "
            f"{EXPECTED_EMPTY_SEQUENCE_COUNT} "
            "records with empty sequence, found "
            f"{empty_sequence_count}."
        )

    if action_step_count != (
        EXPECTED_ACTION_STEP_COUNT
    ):
        raise ValueError(
            "Expected "
            f"{EXPECTED_ACTION_STEP_COUNT} "
            "reference action steps, found "
            f"{action_step_count}."
        )

    if dict(
        suite_structure_counts
    ) != EXPECTED_SUITE_STRUCTURE_COUNTS:
        raise ValueError(
            "Unexpected suite structure counts.\n"
            f"Expected: "
            f"{EXPECTED_SUITE_STRUCTURE_COUNTS}\n"
            f"Found: "
            f"{dict(suite_structure_counts)}"
        )

    if dict(
        task_kind_counts
    ) != EXPECTED_TASK_KIND_COUNTS:
        raise ValueError(
            "Unexpected task-kind counts.\n"
            f"Expected: "
            f"{EXPECTED_TASK_KIND_COUNTS}\n"
            f"Found: "
            f"{dict(task_kind_counts)}"
        )

    if len(blueprints) != (
        EXPECTED_STRUCTURE_COUNT
    ):
        raise ValueError(
            "Unexpected blueprint count: "
            f"{len(blueprints)}"
        )

    if len(
        environment_templates
    ) != 4:
        raise ValueError(
            "Expected four suite environment "
            f"templates, found "
            f"{len(environment_templates)}."
        )


    blueprint_ids = [
        record[
            "blueprint_id"
        ]
        for record in blueprints
    ]

    if len(
        blueprint_ids
    ) != len(
        set(blueprint_ids)
    ):
        raise ValueError(
            "Duplicate blueprint_id detected."
        )


    # --------------------------------------------------------
    # Write outputs
    # --------------------------------------------------------

    blueprints.sort(
        key=lambda record: (
            record["suite"],
            record[
                "structure"
            ][
                "task_kind"
            ],
            safe_int(
                record[
                    "structure"
                ][
                    "task_number"
                ]
            ),
            record[
                "structure"
            ][
                "structure_id"
            ],
        )
    )

    write_jsonl(
        ENVIRONMENT_TEMPLATE_PATH,
        environment_templates,
    )

    write_jsonl(
        BLUEPRINT_PATH,
        blueprints,
    )

    write_csv(
        AUDIT_CSV_PATH,
        audit_rows,
    )


    report = {
        "dataset": "agentdojo",

        "benchmark_version": (
            "v1.2.2"
        ),

        "blueprint_version": (
            "0.1"
        ),

        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "environment_template_count": (
            len(environment_templates)
        ),

        "blueprint_count": (
            len(blueprints)
        ),

        "suite_structure_counts": dict(
            sorted(
                suite_structure_counts.items()
            )
        ),

        "task_kind_counts": dict(
            sorted(
                task_kind_counts.items()
            )
        ),

        "structure_role_counts": dict(
            sorted(
                structure_role_counts.items()
            )
        ),

        "evaluation_mode_counts": dict(
            sorted(
                evaluation_mode_counts.items()
            )
        ),

        "reference_sequence_status_counts": dict(
            sorted(
                sequence_status_counts.items()
            )
        ),

        "records_with_explicit_sequence": (
            sequence_record_count
        ),

        "records_with_empty_sequence": (
            empty_sequence_count
        ),

        "reference_action_step_count": (
            action_step_count
        ),

        "missing_referenced_tool_count": (
            len(
                missing_referenced_tools
            )
        ),

        "unique_scenario_family_count": (
            len(
                scenario_families
            )
        ),

        "suite_tool_counts": (
            actual_suite_tool_counts
        ),

        "suite_vector_counts": (
            actual_suite_vector_counts
        ),

        "runtime_label_count": 0,

        "important_notes": [
            (
                "These are contextual composition "
                "blueprints, not BERT training rows."
            ),
            (
                "Each final training row will represent "
                "one action.attempt event."
            ),
            (
                "No injection vector has yet been "
                "assigned to an individual blueprint."
            ),
            (
                "No general_risk_label, risk score, "
                "policy output, or runtime decision is "
                "present in this artifact."
            ),
            (
                "Action arguments stored as expression "
                "strings are preserved without eval or "
                "execution."
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
        "AGENTDOJO CONTEXTUAL COMPOSITION BLUEPRINTS v0.1 FINALIZED"
    )
    print("=" * 80)

    print()
    print(
        "Environment templates:",
        len(environment_templates),
    )

    print(
        "Composition blueprints:",
        len(blueprints),
    )

    print()
    print(
        "Task kinds:"
    )

    for task_kind, count in sorted(
        task_kind_counts.items()
    ):
        print(
            f"  {task_kind}: {count}"
        )

    print()
    print(
        "Suite structures:"
    )

    for suite, count in sorted(
        suite_structure_counts.items()
    ):
        print(
            f"  {suite}: {count}"
        )

    print()
    print(
        "Reference sequences:"
    )

    print(
        "  records with explicit sequence:",
        sequence_record_count,
    )

    print(
        "  records with empty sequence:",
        empty_sequence_count,
    )

    print(
        "  total action steps:",
        action_step_count,
    )

    print(
        "  missing referenced tools:",
        len(
            missing_referenced_tools
        ),
    )

    print()
    print(
        "Evaluation modes:"
    )

    for mode, count in sorted(
        evaluation_mode_counts.items()
    ):
        print(
            f"  {mode}: {count}"
        )

    print()
    print(
        "Suite environment sizes:"
    )

    for suite in sorted(
        EXPECTED_SUITE_TOOL_COUNTS
    ):
        print(
            f"  {suite}: "
            f"{actual_suite_tool_counts[suite]} tools, "
            f"{actual_suite_vector_counts[suite]} "
            "candidate injection surfaces"
        )

    print()
    print(
        "Runtime labels generated: 0"
    )

    print()
    print(
        f"Environment templates: "
        f"{ENVIRONMENT_TEMPLATE_PATH}"
    )

    print(
        f"Blueprint pool: "
        f"{BLUEPRINT_PATH}"
    )

    print(
        f"Audit CSV: "
        f"{AUDIT_CSV_PATH}"
    )

    print(
        f"Report: "
        f"{REPORT_PATH}"
    )


if __name__ == "__main__":
    main()

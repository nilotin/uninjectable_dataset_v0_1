from __future__ import annotations

import csv
import hashlib
import json
import statistics
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


INTERIM_DIR = Path("data/interim")

PAIR_PATH = (
    INTERIM_DIR
    / "agentdojo_contextual_pair_plan_v0.1.jsonl"
)

SOURCE_POOL_PATH = (
    INTERIM_DIR
    / "agentdojo_contextual_action_attempt_smoke_pool_v0.1.jsonl"
)

SOURCE_QUEUE_PATH = (
    INTERIM_DIR
    / "agentdojo_contextual_action_attempt_pair_review_queue_v0.1.csv"
)

OUTPUT_POOL_PATH = (
    INTERIM_DIR
    / "agentdojo_contextual_action_attempt_smoke_pool_v0.1.1.jsonl"
)

OUTPUT_QUEUE_PATH = (
    INTERIM_DIR
    / "agentdojo_contextual_action_attempt_pair_review_queue_v0.1.1.csv"
)

REPORT_PATH = (
    INTERIM_DIR
    / "agentdojo_contextual_action_attempt_smoke_pool_v0.1.1_report.json"
)


EXPECTED_PAIR_COUNT = 100
EXPECTED_ROW_COUNT = 200
EXPECTED_SAME_TOOL_PAIR_COUNT = 17
EXPECTED_CONCRETE_BINDING_PAIR_COUNT = 4
EXPECTED_DUPLICATE_MODEL_INPUT_COUNT = 0


FORBIDDEN_TEXT_MARKERS = {
    "proposed_binary_label",
    "final_binary_label",
    "expected_contextual_class",
    "review_decision",
    "general_risk_label",
    "ml_risk_score",
    "runtime_decision",
    "policy_output",
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
) -> tuple[
    list[str],
    list[dict[str, str]],
]:

    if not path.exists():
        raise FileNotFoundError(
            f"Missing file: {path}"
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

    pair_binding = pair.get(
        "context_bindings",
        {},
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
        "surface_level_binding"
    )

    if locator:

        binding_status = (
            pair_binding.get(
                "binding_status"
            )
            or
            "confirmed"
        )

    else:

        binding_status = (
            "surface_level_only"
        )


    parameter_bindings: dict[
        str,
        Any,
    ] = {}


    if (
        binding_type
        ==
        "parameterized_web_url_binding"
        and
        locator
    ):

        parameter_bindings[
            "URL"
        ] = locator


    return {
        "binding_type": (
            binding_type
        ),

        "binding_status": (
            binding_status
        ),

        "retrieved_object_locator": (
            locator
        ),

        "parameter_bindings": (
            parameter_bindings
        ),

        "binding_source": (
            pair_binding.get(
                "binding_source"
            )
            or
            (
                "human_semantic_repair"
                if locator
                else
                "suite_surface_metadata"
            )
        ),
    }


def serialize_model_input(
    row: dict[str, Any],
    binding: dict[str, Any],
) -> str:

    user_goal = row[
        "user_context"
    ][
        "goal"
    ]

    agent_context = row[
        "agent_context"
    ]

    source = row[
        "source"
    ]

    retrieval_context = row[
        "retrieval_context"
    ]

    authorization_context = row[
        "authorization_context"
    ]

    policy_context = row[
        "policy_context"
    ]

    attempted_action = row[
        "action"
    ]

    authorized_action = (
        authorization_context[
            "authorized_action"
        ]
    )


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


    source_lines = [
        f"trust_level={source['trust_level']}",
        f"surface_type={source['surface_type']}",
        f"source_type={source['source_type']}",
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


def main() -> None:

    pairs = load_jsonl(
        PAIR_PATH
    )

    source_rows = load_jsonl(
        SOURCE_POOL_PATH
    )

    queue_fieldnames, queue_rows = (
        load_csv(
            SOURCE_QUEUE_PATH
        )
    )


    if len(pairs) != EXPECTED_PAIR_COUNT:
        raise ValueError(
            f"Expected 100 pairs, found {len(pairs)}."
        )

    if len(source_rows) != EXPECTED_ROW_COUNT:
        raise ValueError(
            f"Expected 200 source rows, "
            f"found {len(source_rows)}."
        )

    if len(queue_rows) != EXPECTED_PAIR_COUNT:
        raise ValueError(
            f"Expected 100 review rows, "
            f"found {len(queue_rows)}."
        )


    pair_by_id = {
        str(
            pair[
                "pair_id"
            ]
        ): pair
        for pair in pairs
    }


    concrete_binding_pair_ids = {
        pair_id
        for pair_id, pair
        in pair_by_id.items()
        if resolve_context_binding(
            pair
        )[
            "retrieved_object_locator"
        ]
    }


    if (
        len(
            concrete_binding_pair_ids
        )
        !=
        EXPECTED_CONCRETE_BINDING_PAIR_COUNT
    ):
        raise ValueError(
            "Expected four concrete source bindings, "
            f"found "
            f"{len(concrete_binding_pair_ids)}: "
            f"{sorted(concrete_binding_pair_ids)}"
        )


    upgraded_rows: list[
        dict[str, Any]
    ] = []

    rows_by_pair: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)

    binding_status_counts: Counter[
        str
    ] = Counter()

    binding_type_counts: Counter[
        str
    ] = Counter()

    suite_counts: Counter[
        str
    ] = Counter()

    variant_counts: Counter[
        str
    ] = Counter()

    proposed_label_counts: Counter[
        int
    ] = Counter()

    model_input_lengths: list[
        int
    ] = []


    for source_row in source_rows:

        row = deepcopy(
            source_row
        )

        pair_id = str(
            row[
                "pair_id"
            ]
        )

        pair = pair_by_id.get(
            pair_id
        )

        if pair is None:
            raise ValueError(
                f"Missing pair for row: {pair_id}"
            )


        binding = resolve_context_binding(
            pair
        )

        locator = binding[
            "retrieved_object_locator"
        ]


        row[
            "schema_version"
        ] = "action_attempt_context_v0.1.1"


        row[
            "source"
        ][
            "source_locator"
        ] = locator


        row[
            "retrieval_context"
        ][
            "source_locator"
        ] = locator

        row[
            "retrieval_context"
        ][
            "context_binding"
        ] = binding


        row[
            "authorization_context"
        ][
            "parameter_bindings"
        ] = binding[
            "parameter_bindings"
        ]


        model_input_text = (
            serialize_model_input(
                row,
                binding,
            )
        )


        shared_context_payload = {
            "user_goal": row[
                "user_context"
            ][
                "goal"
            ],

            "agent_context": row[
                "agent_context"
            ],

            "source": row[
                "source"
            ],

            "retrieval_context": row[
                "retrieval_context"
            ],

            "authorization_context": row[
                "authorization_context"
            ],

            "policy_context": row[
                "policy_context"
            ],
        }


        row[
            "model_input"
        ][
            "serialization_version"
        ] = "bert_context_v0.1.1"

        row[
            "model_input"
        ][
            "text"
        ] = model_input_text

        row[
            "model_input"
        ][
            "shared_context_fingerprint"
        ] = stable_hash(
            shared_context_payload
        )

        row[
            "model_input"
        ][
            "attempted_action_fingerprint"
        ] = stable_hash(
            row[
                "action"
            ]
        )


        included_sections = row[
            "model_input"
        ].setdefault(
            "included_sections",
            [],
        )

        if (
            "context_bindings"
            not in
            included_sections
        ):

            source_index = (
                included_sections.index(
                    "source"
                )
                +
                1
                if "source"
                in
                included_sections
                else 0
            )

            included_sections.insert(
                source_index,
                "context_bindings",
            )


        row[
            "provenance"
        ][
            "source_binding_type"
        ] = binding[
            "binding_type"
        ]

        row[
            "provenance"
        ][
            "source_binding_status"
        ] = binding[
            "binding_status"
        ]

        row[
            "provenance"
        ][
            "source_locator_present"
        ] = bool(
            locator
        )


        row[
            "important_note"
        ] = (
            "This is an interim contextual "
            "action.attempt row using serialization "
            "v0.1.1. Concrete source-object bindings "
            "are included when human-confirmed. "
            "Review labels remain excluded from "
            "model_input.text."
        )


        upgraded_rows.append(
            row
        )

        rows_by_pair[
            pair_id
        ].append(
            row
        )

        binding_status_counts[
            binding[
                "binding_status"
            ]
        ] += 1

        binding_type_counts[
            binding[
                "binding_type"
            ]
        ] += 1

        suite_counts[
            row[
                "suite"
            ]
        ] += 1

        variant_counts[
            row[
                "variant"
            ][
                "name"
            ]
        ] += 1

        proposed_label_counts[
            int(
                row[
                    "review"
                ][
                    "proposed_binary_label"
                ]
            )
        ] += 1

        model_input_lengths.append(
            len(
                model_input_text
            )
        )


    # --------------------------------------------------------
    # Pair and duplicate validation
    # --------------------------------------------------------

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
                "Shared context differs across "
                f"variants for {pair_id}."
            )


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
                "Attempted actions are not distinct "
                f"for {pair_id}."
            )


        labels = {
            int(
                row[
                    "review"
                ][
                    "proposed_binary_label"
                ]
            )
            for row in pair_rows
        }

        if labels != {
            0,
            1,
        }:
            raise ValueError(
                f"{pair_id} does not contain "
                "one proposed label 0 and one 1."
            )


    model_input_texts = [
        row[
            "model_input"
        ][
            "text"
        ]
        for row in upgraded_rows
    ]

    duplicate_model_input_count = (
        len(model_input_texts)
        -
        len(
            set(
                model_input_texts
            )
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

        for row in upgraded_rows:

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
            for row_ids
            in duplicate_groups.values()
            if len(row_ids) > 1
        ]

        raise ValueError(
            "Exact duplicate model inputs remain.\n"
            f"Count: {duplicate_model_input_count}\n"
            f"Groups: {duplicates}"
        )


    same_tool_pair_count = sum(
        1
        for pair in pairs
        if pair[
            "pairing_diagnostics"
        ][
            "same_tool_name_across_variants"
        ]
    )

    if (
        same_tool_pair_count
        !=
        EXPECTED_SAME_TOOL_PAIR_COUNT
    ):
        raise ValueError(
            "Expected 17 same-tool pairs, "
            f"found {same_tool_pair_count}."
        )


    # --------------------------------------------------------
    # Upgrade pair-review queue
    # --------------------------------------------------------

    new_queue_columns = [
        "source_locator",
        "binding_type",
        "binding_status",
        "parameter_bindings",
    ]


    output_fieldnames = list(
        queue_fieldnames
    )

    for column in new_queue_columns:

        if column not in output_fieldnames:

            output_fieldnames.append(
                column
            )


    upgraded_queue_rows = []


    for queue_row in queue_rows:

        pair_id = str(
            queue_row[
                "pair_id"
            ]
        )

        pair = pair_by_id.get(
            pair_id
        )

        if pair is None:
            raise ValueError(
                f"Missing pair for review row: "
                f"{pair_id}"
            )

        binding = resolve_context_binding(
            pair
        )

        upgraded_queue_row = dict(
            queue_row
        )

        upgraded_queue_row[
            "source_locator"
        ] = (
            binding[
                "retrieved_object_locator"
            ]
            or
            ""
        )

        upgraded_queue_row[
            "binding_type"
        ] = binding[
            "binding_type"
        ]

        upgraded_queue_row[
            "binding_status"
        ] = binding[
            "binding_status"
        ]

        upgraded_queue_row[
            "parameter_bindings"
        ] = json.dumps(
            binding[
                "parameter_bindings"
            ],
            ensure_ascii=False,
            sort_keys=True,
        )

        upgraded_queue_rows.append(
            upgraded_queue_row
        )


    # --------------------------------------------------------
    # Write artifacts
    # --------------------------------------------------------

    write_jsonl(
        OUTPUT_POOL_PATH,
        upgraded_rows,
    )

    write_csv(
        OUTPUT_QUEUE_PATH,
        output_fieldnames,
        upgraded_queue_rows,
    )


    report = {
        "dataset": "agentdojo",

        "artifact_version": "0.1.1",

        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "source_artifact": str(
            SOURCE_POOL_PATH
        ),

        "pair_plan": str(
            PAIR_PATH
        ),

        "artifact_status": (
            "interim_pending_human_review"
        ),

        "pair_count": len(
            rows_by_pair
        ),

        "row_count": len(
            upgraded_rows
        ),

        "variant_counts": dict(
            variant_counts
        ),

        "proposed_binary_label_counts": {
            str(label): count
            for label, count
            in sorted(
                proposed_label_counts.items()
            )
        },

        "suite_row_counts": dict(
            suite_counts
        ),

        "same_tool_pair_count": (
            same_tool_pair_count
        ),

        "same_tool_runtime_row_count": (
            same_tool_pair_count
            *
            2
        ),

        "concrete_source_binding_pair_count": (
            len(
                concrete_binding_pair_ids
            )
        ),

        "concrete_source_binding_row_count": (
            len(
                concrete_binding_pair_ids
            )
            *
            2
        ),

        "concrete_source_binding_pair_ids": (
            sorted(
                concrete_binding_pair_ids
            )
        ),

        "binding_status_row_counts": dict(
            binding_status_counts
        ),

        "binding_type_row_counts": dict(
            binding_type_counts
        ),

        "duplicate_model_input_count": (
            duplicate_model_input_count
        ),

        "unique_model_input_count": len(
            set(
                model_input_texts
            )
        ),

        "shared_context_pair_validation": {
            "passed": len(
                rows_by_pair
            ),
            "failed": 0,
        },

        "distinct_attempted_action_validation": {
            "passed": len(
                rows_by_pair
            ),
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
                sum(
                    model_input_lengths
                )
                /
                len(
                    model_input_lengths
                )
            ),
        },

        "final_general_risk_label_count": 0,

        "important_notes": [
            (
                "Serialization v0.1.1 includes a "
                "CONTEXT_BINDINGS section."
            ),
            (
                "Four human-confirmed pair bindings "
                "include concrete document or webpage "
                "locators."
            ),
            (
                "Webpage URL bindings are represented as "
                "parameter_bindings without evaluating "
                "upstream Python expressions."
            ),
            (
                "Source vector identifiers remain excluded "
                "from model_input.text."
            ),
            (
                "Review labels, policy-engine outputs, "
                "risk scores, and runtime decisions remain "
                "excluded from model input."
            ),
            (
                "All 200 model-input texts are exact-duplicate "
                "free."
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
        "AGENTDOJO CONTEXTUAL ACTION.ATTEMPT "
        "SMOKE POOL v0.1.1 CREATED"
    )
    print("=" * 80)

    print()
    print(
        "Contextual pairs:",
        len(
            rows_by_pair
        ),
    )

    print(
        "Runtime rows:",
        len(
            upgraded_rows
        ),
    )

    print()
    print(
        "Variants:"
    )

    for variant, count in sorted(
        variant_counts.items()
    ):
        print(
            f"  {variant}: {count}"
        )

    print()
    print(
        "Concrete source bindings:"
    )

    print(
        "  pairs:",
        len(
            concrete_binding_pair_ids
        ),
    )

    print(
        "  rows:",
        len(
            concrete_binding_pair_ids
        )
        *
        2,
    )

    for pair_id in sorted(
        concrete_binding_pair_ids
    ):

        binding = resolve_context_binding(
            pair_by_id[
                pair_id
            ]
        )

        print(
            "  "
            f"{pair_id}: "
            f"{binding['retrieved_object_locator']}"
        )

    print()
    print(
        "Same-tool pairs:",
        same_tool_pair_count,
    )

    print(
        "Same-tool runtime rows:",
        same_tool_pair_count
        *
        2,
    )

    print()
    print(
        "Shared-context validation:",
        f"{len(rows_by_pair)} / "
        f"{len(rows_by_pair)} pairs passed",
    )

    print(
        "Distinct attempted-action validation:",
        f"{len(rows_by_pair)} / "
        f"{len(rows_by_pair)} pairs passed",
    )

    print()
    print(
        "Unique model inputs:",
        len(
            set(
                model_input_texts
            )
        ),
    )

    print(
        "Duplicate model inputs:",
        duplicate_model_input_count,
    )

    print()
    print(
        "Final general_risk_label values generated:",
        0,
    )

    print()
    print(
        f"Smoke pool: {OUTPUT_POOL_PATH}"
    )

    print(
        f"Pair review queue: {OUTPUT_QUEUE_PATH}"
    )

    print(
        f"Report: {REPORT_PATH}"
    )


if __name__ == "__main__":
    main()

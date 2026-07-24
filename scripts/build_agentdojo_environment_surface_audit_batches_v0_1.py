from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


SURFACE_DIR = Path(
    "data/interim/"
    "agentdojo_environment_surface_v0.1"
)

TOOL_SOURCE_PATH = (
    SURFACE_DIR /
    "agentdojo_suite_tool_catalog_v0.1.jsonl"
)

VECTOR_SOURCE_PATH = (
    SURFACE_DIR /
    "agentdojo_injection_vector_catalog_v0.1.jsonl"
)

TOOL_AUDIT_POOL_PATH = (
    SURFACE_DIR /
    "agentdojo_unique_tool_capability_audit_pool_v0.1.csv"
)

VECTOR_AUDIT_POOL_PATH = (
    SURFACE_DIR /
    "agentdojo_injection_vector_surface_audit_pool_v0.1.csv"
)

REVIEW_DIR = Path(
    "data/interim/review_batches"
)

TOOL_WRITE_BATCH_PATH = (
    REVIEW_DIR /
    "agentdojo_tool_capability_audit_batch_021.csv"
)

TOOL_READ_BATCH_1_PATH = (
    REVIEW_DIR /
    "agentdojo_tool_capability_audit_batch_022.csv"
)

TOOL_READ_BATCH_2_PATH = (
    REVIEW_DIR /
    "agentdojo_tool_capability_audit_batch_023.csv"
)

VECTOR_BATCH_1_PATH = (
    REVIEW_DIR /
    "agentdojo_injection_vector_surface_audit_batch_024.csv"
)

VECTOR_BATCH_2_PATH = (
    REVIEW_DIR /
    "agentdojo_injection_vector_surface_audit_batch_025.csv"
)


EXPECTED_INSTANCE_COUNT = 74
EXPECTED_UNIQUE_TOOL_COUNT = 69
EXPECTED_WRITE_TOOL_COUNT = 24
EXPECTED_READ_TOOL_COUNT = 45
EXPECTED_VECTOR_COUNT = 39


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
                    f"Invalid JSONL in {path} "
                    f"at line {line_number}."
                ) from error

    return records


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

    fieldnames = list(
        rows[0].keys()
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


def stable_unique_json_values(
    values: list[Any],
) -> list[Any]:

    unique_by_serialized: dict[
        str,
        Any,
    ] = {}

    for value in values:

        serialized = json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False,
        )

        unique_by_serialized[
            serialized
        ] = value

    return [
        unique_by_serialized[key]
        for key in sorted(
            unique_by_serialized
        )
    ]


def build_unique_tool_rows(
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    grouped: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)

    for record in records:
        grouped[
            str(record["tool_name"])
        ].append(record)


    rows: list[dict[str, Any]] = []


    for tool_name, instances in grouped.items():

        suites = sorted(
            {
                str(instance["suite"])
                for instance in instances
            }
        )

        capability_classes = {
            str(
                instance[
                    "suggested_capability_class"
                ]
            )
            for instance in instances
        }

        action_impacts = {
            str(
                instance[
                    "suggested_action_impact"
                ]
            )
            for instance in instances
        }

        if len(capability_classes) != 1:
            raise ValueError(
                f"Inconsistent capability suggestions "
                f"for {tool_name}: "
                f"{sorted(capability_classes)}"
            )

        if len(action_impacts) != 1:
            raise ValueError(
                f"Inconsistent impact suggestions "
                f"for {tool_name}: "
                f"{sorted(action_impacts)}"
            )


        descriptions = sorted(
            {
                str(
                    instance.get(
                        "description",
                        "",
                    )
                )
                for instance in instances
            }
        )

        public_parameters = (
            stable_unique_json_values(
                [
                    instance.get(
                        "public_parameters",
                        [],
                    )
                    for instance in instances
                ]
            )
        )

        environment_dependencies = (
            stable_unique_json_values(
                [
                    instance.get(
                        "environment_dependencies",
                        [],
                    )
                    for instance in instances
                ]
            )
        )

        implementation_locations = [
            {
                "suite": (
                    instance["suite"]
                ),
                "implementation_file": (
                    instance[
                        "implementation_file"
                    ]
                ),
                "source_line": (
                    instance[
                        "source_line"
                    ]
                ),
            }
            for instance in sorted(
                instances,
                key=lambda item: (
                    item["suite"],
                    item[
                        "implementation_file"
                    ],
                    int(
                        item["source_line"]
                    ),
                ),
            )
        ]


        suggested_capability = next(
            iter(
                capability_classes
            )
        )

        suggested_impact = next(
            iter(
                action_impacts
            )
        )


        rows.append(
            {
                "tool_name": tool_name,

                "suites": json.dumps(
                    suites,
                    ensure_ascii=False,
                ),

                "suite_instance_count": (
                    len(instances)
                ),

                "descriptions": json.dumps(
                    descriptions,
                    ensure_ascii=False,
                ),

                "public_parameter_variants": (
                    json.dumps(
                        public_parameters,
                        ensure_ascii=False,
                    )
                ),

                "environment_dependency_variants": (
                    json.dumps(
                        environment_dependencies,
                        ensure_ascii=False,
                    )
                ),

                "implementation_locations": (
                    json.dumps(
                        implementation_locations,
                        ensure_ascii=False,
                    )
                ),

                "suggested_capability_class": (
                    suggested_capability
                ),

                "suggested_action_impact": (
                    suggested_impact
                ),

                "review_priority": (
                    "P1_write_or_side_effect"
                    if suggested_capability
                    !=
                    "read_only"
                    else
                    "P2_read_only_validation"
                ),

                "review_decision": "",

                "capability_class": "",

                "action_impact": "",

                "review_note": "",
            }
        )


    rows.sort(
        key=lambda row: (
            0
            if row[
                "suggested_capability_class"
            ]
            !=
            "read_only"
            else 1,
            row[
                "suggested_capability_class"
            ],
            row["tool_name"],
        )
    )

    return rows


def compact_location_summary(
    locations: list[dict[str, Any]],
) -> str:

    summaries = []

    for location in locations:

        summaries.append(
            (
                f"{location.get('source_file', '')}:"
                f"{location.get('line_number', '')}"
                " | "
                f"{location.get('line_text', '')}"
            )
        )

    return "\n".join(
        summaries
    )


def build_vector_rows(
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    rows: list[dict[str, Any]] = []


    for record in records:

        locations = record.get(
            "locations",
            [],
        )

        if not locations:
            raise ValueError(
                "Injection vector has no located "
                f"environment surface: "
                f"{record['suite']}:"
                f"{record['vector_id']}"
            )


        rows.append(
            {
                "vector_id": (
                    record["vector_id"]
                ),

                "suite": (
                    record["suite"]
                ),

                "description": (
                    record["description"]
                ),

                "default_value": (
                    record["default_value"]
                ),

                "suggested_surface_type": (
                    record[
                        "inferred_surface_type"
                    ]
                ),

                "location_count": (
                    record["location_count"]
                ),

                "location_summary": (
                    compact_location_summary(
                        locations
                    )
                ),

                "locations_json": (
                    json.dumps(
                        locations,
                        ensure_ascii=False,
                    )
                ),

                "suggested_trust_level": (
                    record[
                        "trust_level_suggestion"
                    ]
                ),

                "review_decision": "",

                "surface_type": "",

                "source_type": "",

                "trust_level": "",

                "review_note": "",
            }
        )


    rows.sort(
        key=lambda row: (
            row["suite"],
            row["vector_id"],
        )
    )

    return rows


def main() -> None:

    tool_instances = load_jsonl(
        TOOL_SOURCE_PATH
    )

    vector_records = load_jsonl(
        VECTOR_SOURCE_PATH
    )


    if len(tool_instances) != (
        EXPECTED_INSTANCE_COUNT
    ):
        raise ValueError(
            "Expected "
            f"{EXPECTED_INSTANCE_COUNT} "
            "tool instances, found "
            f"{len(tool_instances)}."
        )

    if len(vector_records) != (
        EXPECTED_VECTOR_COUNT
    ):
        raise ValueError(
            "Expected "
            f"{EXPECTED_VECTOR_COUNT} "
            "injection vectors, found "
            f"{len(vector_records)}."
        )


    tool_rows = build_unique_tool_rows(
        tool_instances
    )

    vector_rows = build_vector_rows(
        vector_records
    )


    if len(tool_rows) != (
        EXPECTED_UNIQUE_TOOL_COUNT
    ):
        raise ValueError(
            "Expected "
            f"{EXPECTED_UNIQUE_TOOL_COUNT} "
            "unique tools, found "
            f"{len(tool_rows)}."
        )


    write_tool_rows = [
        row
        for row in tool_rows
        if row[
            "suggested_capability_class"
        ]
        !=
        "read_only"
    ]

    read_tool_rows = [
        row
        for row in tool_rows
        if row[
            "suggested_capability_class"
        ]
        ==
        "read_only"
    ]


    if len(write_tool_rows) != (
        EXPECTED_WRITE_TOOL_COUNT
    ):
        raise ValueError(
            "Expected "
            f"{EXPECTED_WRITE_TOOL_COUNT} "
            "unique write/side-effect tools, "
            f"found {len(write_tool_rows)}."
        )

    if len(read_tool_rows) != (
        EXPECTED_READ_TOOL_COUNT
    ):
        raise ValueError(
            "Expected "
            f"{EXPECTED_READ_TOOL_COUNT} "
            "unique read-only tools, "
            f"found {len(read_tool_rows)}."
        )


    write_csv(
        TOOL_AUDIT_POOL_PATH,
        tool_rows,
    )

    write_csv(
        VECTOR_AUDIT_POOL_PATH,
        vector_rows,
    )


    # Tool review batches:
    # 24 write tools
    # 23 + 22 read-only tools
    write_csv(
        TOOL_WRITE_BATCH_PATH,
        write_tool_rows,
    )

    write_csv(
        TOOL_READ_BATCH_1_PATH,
        read_tool_rows[:23],
    )

    write_csv(
        TOOL_READ_BATCH_2_PATH,
        read_tool_rows[23:],
    )


    # Injection-vector review batches:
    # 20 + 19
    write_csv(
        VECTOR_BATCH_1_PATH,
        vector_rows[:20],
    )

    write_csv(
        VECTOR_BATCH_2_PATH,
        vector_rows[20:],
    )


    instance_class_counts = Counter(
        record[
            "suggested_capability_class"
        ]
        for record in tool_instances
    )

    unique_class_counts = Counter(
        row[
            "suggested_capability_class"
        ]
        for row in tool_rows
    )

    vector_suite_counts = Counter(
        row["suite"]
        for row in vector_rows
    )


    print("=" * 80)
    print(
        "AGENTDOJO ENVIRONMENT-SURFACE AUDIT BATCHES CREATED"
    )
    print("=" * 80)

    print()
    print(
        "Tool instances:",
        len(tool_instances),
    )

    print(
        "Unique tool names:",
        len(tool_rows),
    )

    print()
    print(
        "Unique tool capability suggestions:"
    )

    for capability, count in sorted(
        unique_class_counts.items()
    ):
        print(
            f"  {capability}: {count}"
        )

    print()
    print(
        "Write / side-effect tools:",
        len(write_tool_rows),
    )

    print(
        "Read-only tools:",
        len(read_tool_rows),
    )

    print()
    print(
        "Tool audit batches:"
    )

    print(
        f"  {TOOL_WRITE_BATCH_PATH.name}: "
        f"{len(write_tool_rows)}"
    )

    print(
        f"  {TOOL_READ_BATCH_1_PATH.name}: "
        f"{len(read_tool_rows[:23])}"
    )

    print(
        f"  {TOOL_READ_BATCH_2_PATH.name}: "
        f"{len(read_tool_rows[23:])}"
    )

    print()
    print(
        "Injection-vector records:",
        len(vector_rows),
    )

    print(
        "Injection vectors by suite:"
    )

    for suite, count in sorted(
        vector_suite_counts.items()
    ):
        print(
            f"  {suite}: {count}"
        )

    print()
    print(
        "Injection-vector audit batches:"
    )

    print(
        f"  {VECTOR_BATCH_1_PATH.name}: "
        f"{len(vector_rows[:20])}"
    )

    print(
        f"  {VECTOR_BATCH_2_PATH.name}: "
        f"{len(vector_rows[20:])}"
    )

    print()
    print(
        f"Tool audit pool: "
        f"{TOOL_AUDIT_POOL_PATH}"
    )

    print(
        f"Vector audit pool: "
        f"{VECTOR_AUDIT_POOL_PATH}"
    )


if __name__ == "__main__":
    main()

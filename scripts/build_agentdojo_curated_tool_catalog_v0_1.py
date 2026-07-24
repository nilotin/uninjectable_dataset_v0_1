from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


SURFACE_DIR = Path(
    "data/interim/"
    "agentdojo_environment_surface_v0.1"
)

SOURCE_INSTANCE_PATH = (
    SURFACE_DIR /
    "agentdojo_suite_tool_catalog_v0.1.jsonl"
)

AUDIT_POOL_PATH = (
    SURFACE_DIR /
    "agentdojo_unique_tool_capability_audit_pool_v0.1.csv"
)

OUTPUT_DIR = Path(
    "data/processed"
)

CURATED_INSTANCE_PATH = (
    OUTPUT_DIR /
    "agentdojo_curated_suite_tool_catalog_v0.1.jsonl"
)

CURATED_UNIQUE_PATH = (
    OUTPUT_DIR /
    "agentdojo_curated_unique_tool_capability_catalog_v0.1.jsonl"
)

REPORT_PATH = (
    OUTPUT_DIR /
    "agentdojo_curated_tool_catalog_v0.1_report.json"
)


EXPECTED_UNIQUE_CAPABILITIES = {
    "access_control_write": 4,
    "booking_or_reservation_write": 3,
    "credential_or_account_write": 2,
    "destructive_or_revocation_write": 4,
    "external_communication_write": 4,
    "financial_data_read": 4,
    "financial_write": 3,
    "ordinary_read": 21,
    "private_communication_read": 6,
    "private_communication_read_with_state_change": 1,
    "sensitive_data_read": 13,
    "state_changing_write": 4,
}

EXPECTED_UNIQUE_IMPACTS = {
    "high": 17,
    "medium": 31,
    "low": 21,
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


def parse_json_cell(
    value: str,
) -> Any:

    if value is None:
        return None

    value = str(value).strip()

    if not value:
        return None

    return json.loads(value)


def main() -> None:

    source_instances = load_jsonl(
        SOURCE_INSTANCE_PATH
    )

    audit_df = pd.read_csv(
        AUDIT_POOL_PATH,
        dtype="string",
    )

    required_columns = {
        "tool_name",
        "suites",
        "suite_instance_count",
        "descriptions",
        "public_parameter_variants",
        "environment_dependency_variants",
        "implementation_locations",
        "suggested_capability_class",
        "suggested_action_impact",
        "review_decision",
        "capability_class",
        "action_impact",
        "review_note",
    }

    missing_columns = (
        required_columns
        -
        set(audit_df.columns)
    )

    if missing_columns:
        raise ValueError(
            "Audit pool is missing columns: "
            f"{sorted(missing_columns)}"
        )

    for column in required_columns:
        audit_df[column] = (
            audit_df[column]
            .fillna("")
            .astype("string")
        )


    # --------------------------------------------------------
    # Validate source and audit
    # --------------------------------------------------------

    if len(source_instances) != 74:
        raise ValueError(
            "Expected 74 suite-level tool instances, "
            f"found {len(source_instances)}."
        )

    if len(audit_df) != 69:
        raise ValueError(
            "Expected 69 unique tool audit rows, "
            f"found {len(audit_df)}."
        )

    if (
        audit_df[
            "review_decision"
        ]
        ==
        ""
    ).any():
        unreviewed = (
            audit_df.loc[
                audit_df[
                    "review_decision"
                ]
                ==
                "",
                "tool_name",
            ]
            .tolist()
        )

        raise ValueError(
            "Tool audit is incomplete. "
            f"Unreviewed tools: {unreviewed}"
        )


    review_decision_counts = (
        audit_df[
            "review_decision"
        ]
        .value_counts()
        .to_dict()
    )

    expected_decisions = {
        "confirmed_capability_metadata": 68,
        "corrected_capability_metadata": 1,
    }

    if (
        review_decision_counts
        !=
        expected_decisions
    ):
        raise ValueError(
            "Unexpected review decisions.\n"
            f"Expected: {expected_decisions}\n"
            f"Found: {review_decision_counts}"
        )


    unique_capability_counts = (
        audit_df[
            "capability_class"
        ]
        .value_counts()
        .to_dict()
    )

    unique_impact_counts = (
        audit_df[
            "action_impact"
        ]
        .value_counts()
        .to_dict()
    )

    if (
        unique_capability_counts
        !=
        EXPECTED_UNIQUE_CAPABILITIES
    ):
        raise ValueError(
            "Unexpected unique capability counts.\n"
            f"Expected: "
            f"{EXPECTED_UNIQUE_CAPABILITIES}\n"
            f"Found: {unique_capability_counts}"
        )

    if (
        unique_impact_counts
        !=
        EXPECTED_UNIQUE_IMPACTS
    ):
        raise ValueError(
            "Unexpected unique impact counts.\n"
            f"Expected: "
            f"{EXPECTED_UNIQUE_IMPACTS}\n"
            f"Found: {unique_impact_counts}"
        )


    source_tool_names = {
        str(
            record["tool_name"]
        )
        for record
        in source_instances
    }

    audit_tool_names = set(
        audit_df[
            "tool_name"
        ].astype(str)
    )

    if (
        source_tool_names
        !=
        audit_tool_names
    ):
        raise ValueError(
            "Source/audit tool-name mismatch.\n"
            f"Missing from audit: "
            f"{sorted(source_tool_names - audit_tool_names)}\n"
            f"Missing from source: "
            f"{sorted(audit_tool_names - source_tool_names)}"
        )


    audit_lookup = {
        str(row["tool_name"]): row
        for _, row in audit_df.iterrows()
    }


    # --------------------------------------------------------
    # Build curated suite-level instance catalog
    # --------------------------------------------------------

    curated_instances = []

    for source_record in source_instances:

        tool_name = str(
            source_record[
                "tool_name"
            ]
        )

        audit_row = audit_lookup[
            tool_name
        ]

        record = dict(
            source_record
        )

        record[
            "human_review"
        ] = {
            "status": "completed",

            "review_decision": str(
                audit_row[
                    "review_decision"
                ]
            ),

            "capability_class": str(
                audit_row[
                    "capability_class"
                ]
            ),

            "action_impact": str(
                audit_row[
                    "action_impact"
                ]
            ),

            "review_note": str(
                audit_row[
                    "review_note"
                ]
            ),

            "label_source": (
                "human_review"
            ),
        }

        record[
            "composition_metadata"
        ] = {
            "available_to_agent": True,

            "tool_scope": (
                "suite_level"
            ),

            "include_in_agent_context": True,

            "important_note": (
                "Capability class and action impact "
                "describe stable tool properties. "
                "They do not determine the runtime "
                "general_risk_label."
            ),
        }

        curated_instances.append(
            record
        )


    curated_instances.sort(
        key=lambda record: (
            record["suite"],
            int(
                record[
                    "tool_position"
                ]
            ),
            record[
                "tool_name"
            ],
        )
    )


    # --------------------------------------------------------
    # Build curated unique-tool catalog
    # --------------------------------------------------------

    curated_unique = []

    for _, row in audit_df.sort_values(
        "tool_name"
    ).iterrows():

        curated_unique.append(
            {
                "tool_name": str(
                    row[
                        "tool_name"
                    ]
                ),

                "suites": parse_json_cell(
                    row[
                        "suites"
                    ]
                ),

                "suite_instance_count": int(
                    row[
                        "suite_instance_count"
                    ]
                ),

                "descriptions": parse_json_cell(
                    row[
                        "descriptions"
                    ]
                ),

                "public_parameter_variants": (
                    parse_json_cell(
                        row[
                            "public_parameter_variants"
                        ]
                    )
                ),

                "environment_dependency_variants": (
                    parse_json_cell(
                        row[
                            "environment_dependency_variants"
                        ]
                    )
                ),

                "implementation_locations": (
                    parse_json_cell(
                        row[
                            "implementation_locations"
                        ]
                    )
                ),

                "human_review": {
                    "status": "completed",

                    "review_decision": str(
                        row[
                            "review_decision"
                        ]
                    ),

                    "capability_class": str(
                        row[
                            "capability_class"
                        ]
                    ),

                    "action_impact": str(
                        row[
                            "action_impact"
                        ]
                    ),

                    "review_note": str(
                        row[
                            "review_note"
                        ]
                    ),

                    "label_source": (
                        "human_review"
                    ),
                },

                "important_note": (
                    "This record describes a tool "
                    "capability, not a runtime event "
                    "or Phase-1 risk label."
                ),
            }
        )


    # --------------------------------------------------------
    # Final validations
    # --------------------------------------------------------

    instance_capability_counts = Counter(
        record[
            "human_review"
        ][
            "capability_class"
        ]
        for record
        in curated_instances
    )

    instance_impact_counts = Counter(
        record[
            "human_review"
        ][
            "action_impact"
        ]
        for record
        in curated_instances
    )

    suite_counts = Counter(
        record[
            "suite"
        ]
        for record
        in curated_instances
    )

    expected_suite_counts = {
        "banking": 11,
        "slack": 11,
        "travel": 28,
        "workspace": 24,
    }

    if dict(
        suite_counts
    ) != expected_suite_counts:
        raise ValueError(
            "Unexpected suite instance counts.\n"
            f"Expected: {expected_suite_counts}\n"
            f"Found: {dict(suite_counts)}"
        )


    corrected_tools = (
        audit_df.loc[
            audit_df[
                "review_decision"
            ]
            ==
            "corrected_capability_metadata",
            "tool_name",
        ]
        .astype(str)
        .tolist()
    )

    if corrected_tools != [
        "get_unread_emails"
    ]:
        raise ValueError(
            "Unexpected corrected-tool list: "
            f"{corrected_tools}"
        )


    # --------------------------------------------------------
    # Write outputs
    # --------------------------------------------------------

    write_jsonl(
        CURATED_INSTANCE_PATH,
        curated_instances,
    )

    write_jsonl(
        CURATED_UNIQUE_PATH,
        curated_unique,
    )


    report = {
        "dataset": "agentdojo",

        "curated_tool_catalog_version": (
            "0.1"
        ),

        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "benchmark_version": "v1.2.2",

        "suite_tool_instance_count": (
            len(curated_instances)
        ),

        "unique_tool_count": (
            len(curated_unique)
        ),

        "suite_instance_counts": dict(
            suite_counts
        ),

        "unique_review_decision_counts": (
            review_decision_counts
        ),

        "unique_capability_class_counts": (
            unique_capability_counts
        ),

        "unique_action_impact_counts": (
            unique_impact_counts
        ),

        "suite_instance_capability_class_counts": dict(
            instance_capability_counts
        ),

        "suite_instance_action_impact_counts": dict(
            instance_impact_counts
        ),

        "corrected_tool_names": (
            corrected_tools
        ),

        "important_notes": [
            (
                "The suite-level catalog contains "
                "74 tool instances because five tool "
                "names appear in multiple suites."
            ),
            (
                "The unique catalog contains "
                "69 human-reviewed tool names."
            ),
            (
                "get_unread_emails was corrected because "
                "it marks returned emails as read and is "
                "therefore not strictly read-only."
            ),
            (
                "Capability class and action impact are "
                "stable tool metadata, not runtime "
                "general_risk_label values."
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
        "AGENTDOJO CURATED TOOL CATALOG v0.1 FINALIZED"
    )
    print("=" * 80)

    print()
    print(
        "Suite-level tool instances:",
        len(curated_instances),
    )

    print(
        "Unique reviewed tools:",
        len(curated_unique),
    )

    print()
    print(
        "Suite instance counts:"
    )

    for suite, count in sorted(
        suite_counts.items()
    ):
        print(
            f"  {suite}: {count}"
        )

    print()
    print(
        "Unique review decisions:"
    )

    for decision, count in (
        review_decision_counts.items()
    ):
        print(
            f"  {decision}: {count}"
        )

    print()
    print(
        "Unique capability classes:"
    )

    for capability, count in sorted(
        unique_capability_counts.items()
    ):
        print(
            f"  {capability}: {count}"
        )

    print()
    print(
        "Unique action impacts:"
    )

    for impact, count in (
        unique_impact_counts.items()
    ):
        print(
            f"  {impact}: {count}"
        )

    print()
    print(
        "Corrected tools:",
        corrected_tools,
    )

    print()
    print(
        f"Suite catalog: "
        f"{CURATED_INSTANCE_PATH}"
    )

    print(
        f"Unique catalog: "
        f"{CURATED_UNIQUE_PATH}"
    )

    print(
        f"Report: "
        f"{REPORT_PATH}"
    )


if __name__ == "__main__":
    main()

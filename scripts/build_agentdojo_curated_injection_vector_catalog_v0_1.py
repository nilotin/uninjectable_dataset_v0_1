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

SOURCE_PATH = (
    SURFACE_DIR /
    "agentdojo_injection_vector_catalog_v0.1.jsonl"
)

AUDIT_PATH = (
    SURFACE_DIR /
    "agentdojo_injection_vector_surface_audit_pool_v0.1.csv"
)

OUTPUT_DIR = Path(
    "data/processed"
)

CURATED_PATH = (
    OUTPUT_DIR /
    "agentdojo_curated_injection_vector_catalog_v0.1.jsonl"
)

REPORT_PATH = (
    OUTPUT_DIR /
    "agentdojo_curated_injection_vector_catalog_v0.1_report.json"
)


EXPECTED_SUITE_COUNTS = {
    "banking": 4,
    "slack": 6,
    "travel": 13,
    "workspace": 16,
}

EXPECTED_DECISION_COUNTS = {
    "confirmed_surface_metadata": 33,
    "corrected_surface_metadata": 6,
}

EXPECTED_SURFACE_COUNTS = {
    "external_web_content_or_review": 18,
    "file_or_cloud_document": 7,
    "calendar_event_or_description": 7,
    "email_message_or_metadata": 5,
    "bank_transaction_or_payment_metadata": 1,
    "slack_channel_metadata": 1,
}

EXPECTED_SOURCE_COUNTS = {
    "third_party_review_content": 13,
    "calendar_event_description": 7,
    "external_webpage_content": 5,
    "email_body_content": 5,
    "cloud_document_content": 4,
    "document_content": 3,
    "transaction_metadata": 1,
    "channel_metadata": 1,
}

EXPECTED_CORRECTED_KEYS = {
    ("slack", "injection_dora_0"),
    ("slack", "injection_phishing_1"),
    ("slack", "injection_web_0"),
    ("slack", "prompt_injection_channel"),
    ("slack", "prompt_injection_eve_blog"),
    ("slack", "prompt_injection_restaurant"),
}


RETRIEVAL_CHANNEL_BY_SOURCE = {
    "third_party_review_content": (
        "third_party_review_retrieval"
    ),

    "calendar_event_description": (
        "calendar_search_or_read"
    ),

    "external_webpage_content": (
        "external_web_fetch"
    ),

    "email_body_content": (
        "email_search_or_read"
    ),

    "cloud_document_content": (
        "cloud_drive_search_or_read"
    ),

    "document_content": (
        "filesystem_document_read"
    ),

    "transaction_metadata": (
        "bank_transaction_history_read"
    ),

    "channel_metadata": (
        "slack_channel_discovery"
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


def normalize_string(
    value: Any,
) -> str | None:

    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    if text.lower() in {
        "<na>",
        "nan",
        "none",
    }:
        return None

    return text


def main() -> None:

    source_records = load_jsonl(
        SOURCE_PATH
    )

    audit_df = pd.read_csv(
        AUDIT_PATH,
        dtype="string",
    )

    required_columns = {
        "vector_id",
        "suite",
        "description",
        "default_value",
        "suggested_surface_type",
        "suggested_trust_level",
        "location_count",
        "locations_json",
        "review_decision",
        "surface_type",
        "source_type",
        "trust_level",
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
    # Structural validation
    # --------------------------------------------------------

    if len(source_records) != 39:
        raise ValueError(
            "Expected 39 source injection vectors, "
            f"found {len(source_records)}."
        )

    if len(audit_df) != 39:
        raise ValueError(
            "Expected 39 audit rows, "
            f"found {len(audit_df)}."
        )

    if (
        audit_df[
            "review_decision"
        ]
        ==
        ""
    ).any():

        unresolved = (
            audit_df.loc[
                audit_df[
                    "review_decision"
                ]
                ==
                "",
                [
                    "suite",
                    "vector_id",
                ],
            ]
            .to_dict(
                orient="records"
            )
        )

        raise ValueError(
            "Injection-vector audit is incomplete. "
            f"Unresolved rows: {unresolved}"
        )


    source_keys = {
        (
            str(record["suite"]),
            str(record["vector_id"]),
        )
        for record in source_records
    }

    audit_keys = {
        (
            str(row["suite"]),
            str(row["vector_id"]),
        )
        for _, row in audit_df.iterrows()
    }

    if source_keys != audit_keys:
        raise ValueError(
            "Source/audit key mismatch.\n"
            f"Missing from audit: "
            f"{sorted(source_keys - audit_keys)}\n"
            f"Missing from source: "
            f"{sorted(audit_keys - source_keys)}"
        )


    decision_counts = (
        audit_df[
            "review_decision"
        ]
        .value_counts()
        .to_dict()
    )

    surface_counts = (
        audit_df[
            "surface_type"
        ]
        .value_counts()
        .to_dict()
    )

    source_type_counts = (
        audit_df[
            "source_type"
        ]
        .value_counts()
        .to_dict()
    )

    trust_counts = (
        audit_df[
            "trust_level"
        ]
        .value_counts()
        .to_dict()
    )

    suite_counts = (
        audit_df[
            "suite"
        ]
        .value_counts()
        .to_dict()
    )


    if decision_counts != EXPECTED_DECISION_COUNTS:
        raise ValueError(
            "Unexpected review-decision counts.\n"
            f"Expected: {EXPECTED_DECISION_COUNTS}\n"
            f"Found: {decision_counts}"
        )

    if surface_counts != EXPECTED_SURFACE_COUNTS:
        raise ValueError(
            "Unexpected surface counts.\n"
            f"Expected: {EXPECTED_SURFACE_COUNTS}\n"
            f"Found: {surface_counts}"
        )

    if source_type_counts != EXPECTED_SOURCE_COUNTS:
        raise ValueError(
            "Unexpected source-type counts.\n"
            f"Expected: {EXPECTED_SOURCE_COUNTS}\n"
            f"Found: {source_type_counts}"
        )

    if trust_counts != {
        "untrusted": 39
    }:
        raise ValueError(
            "All 39 injection vectors must be "
            "marked untrusted."
        )

    if suite_counts != EXPECTED_SUITE_COUNTS:
        raise ValueError(
            "Unexpected suite counts.\n"
            f"Expected: {EXPECTED_SUITE_COUNTS}\n"
            f"Found: {suite_counts}"
        )


    corrected_keys = {
        (
            str(row["suite"]),
            str(row["vector_id"]),
        )
        for _, row in audit_df.loc[
            audit_df[
                "review_decision"
            ]
            ==
            "corrected_surface_metadata"
        ].iterrows()
    }

    if corrected_keys != EXPECTED_CORRECTED_KEYS:
        raise ValueError(
            "Unexpected corrected-vector set.\n"
            f"Expected: "
            f"{sorted(EXPECTED_CORRECTED_KEYS)}\n"
            f"Found: {sorted(corrected_keys)}"
        )


    audit_lookup = {
        (
            str(row["suite"]),
            str(row["vector_id"]),
        ): row
        for _, row in audit_df.iterrows()
    }


    # --------------------------------------------------------
    # Build curated records
    # --------------------------------------------------------

    curated_records: list[
        dict[str, Any]
    ] = []


    for source_record in source_records:

        key = (
            str(source_record["suite"]),
            str(source_record["vector_id"]),
        )

        audit_row = audit_lookup[
            key
        ]

        source_type = str(
            audit_row[
                "source_type"
            ]
        )

        retrieval_channel = (
            RETRIEVAL_CHANNEL_BY_SOURCE.get(
                source_type
            )
        )

        if retrieval_channel is None:
            raise ValueError(
                "No retrieval-channel mapping for "
                f"source type: {source_type}"
            )


        locations = source_record.get(
            "locations",
            []
        )

        if not locations:
            raise ValueError(
                "Curated vector has no environment "
                f"location: {key}"
            )


        curated_record = dict(
            source_record
        )

        curated_record[
            "description"
        ] = normalize_string(
            source_record.get(
                "description"
            )
        )

        curated_record[
            "default_value"
        ] = normalize_string(
            source_record.get(
                "default_value"
            )
        )

        curated_record[
            "human_review"
        ] = {
            "status": "completed",

            "review_decision": str(
                audit_row[
                    "review_decision"
                ]
            ),

            "surface_type": str(
                audit_row[
                    "surface_type"
                ]
            ),

            "source_type": source_type,

            "trust_level": str(
                audit_row[
                    "trust_level"
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

        curated_record[
            "composition_metadata"
        ] = {
            "retrieval_channel": (
                retrieval_channel
            ),

            "source_control": (
                "attacker_controllable_benchmark_slot"
            ),

            "scope": (
                "embedded_environment_field"
            ),

            "include_in_retrieval_context": True,

            "may_contain_benign_default_text": True,

            "important_note": (
                "Untrusted describes source provenance "
                "and attacker controllability. It does "
                "not by itself determine the contextual "
                "general_risk_label."
            ),
        }

        curated_records.append(
            curated_record
        )


    curated_records.sort(
        key=lambda record: (
            record["suite"],
            record["vector_id"],
        )
    )


    # --------------------------------------------------------
    # Final catalog validation
    # --------------------------------------------------------

    curated_surface_counts = Counter(
        record[
            "human_review"
        ][
            "surface_type"
        ]
        for record in curated_records
    )

    curated_source_counts = Counter(
        record[
            "human_review"
        ][
            "source_type"
        ]
        for record in curated_records
    )

    retrieval_channel_counts = Counter(
        record[
            "composition_metadata"
        ][
            "retrieval_channel"
        ]
        for record in curated_records
    )

    total_location_count = sum(
        len(
            record.get(
                "locations",
                []
            )
        )
        for record in curated_records
    )

    multi_location_vectors = [
        {
            "suite": record["suite"],
            "vector_id": record["vector_id"],
            "location_count": len(
                record.get(
                    "locations",
                    []
                )
            ),
        }
        for record in curated_records
        if len(
            record.get(
                "locations",
                []
            )
        )
        >
        1
    ]


    if dict(
        curated_surface_counts
    ) != EXPECTED_SURFACE_COUNTS:
        raise ValueError(
            "Curated surface counts changed "
            "unexpectedly."
        )

    if dict(
        curated_source_counts
    ) != EXPECTED_SOURCE_COUNTS:
        raise ValueError(
            "Curated source counts changed "
            "unexpectedly."
        )


    # --------------------------------------------------------
    # Write outputs
    # --------------------------------------------------------

    write_jsonl(
        CURATED_PATH,
        curated_records,
    )


    report = {
        "dataset": "agentdojo",

        "benchmark_version": "v1.2.2",

        "catalog_version": "0.1",

        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "total_vectors": (
            len(curated_records)
        ),

        "suite_counts": (
            EXPECTED_SUITE_COUNTS
        ),

        "review_decision_counts": (
            EXPECTED_DECISION_COUNTS
        ),

        "surface_type_counts": (
            EXPECTED_SURFACE_COUNTS
        ),

        "source_type_counts": (
            EXPECTED_SOURCE_COUNTS
        ),

        "trust_level_counts": {
            "untrusted": 39,
        },

        "retrieval_channel_counts": dict(
            retrieval_channel_counts
        ),

        "total_environment_locations": (
            total_location_count
        ),

        "multi_location_vectors": (
            multi_location_vectors
        ),

        "corrected_vector_keys": [
            {
                "suite": suite,
                "vector_id": vector_id,
            }
            for suite, vector_id in sorted(
                EXPECTED_CORRECTED_KEYS
            )
        ],

        "important_notes": [
            (
                "All vectors are attacker-controllable "
                "benchmark insertion slots."
            ),
            (
                "Trust level expresses provenance, not "
                "whether the vector's default text is "
                "malicious."
            ),
            (
                "Runtime general_risk_label must be "
                "assigned only after the vector is "
                "composed with user intent, agent "
                "permissions, retrieved content, policy, "
                "and attempted action."
            ),
            (
                "Six Slack-suite vectors required surface "
                "correction because five are web content "
                "and one is channel metadata."
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
        "AGENTDOJO CURATED INJECTION-VECTOR CATALOG v0.1 FINALIZED"
    )
    print("=" * 80)

    print()
    print(
        "Curated vectors:",
        len(curated_records),
    )

    print(
        "Environment locations:",
        total_location_count,
    )

    print()
    print(
        "Review decisions:"
    )

    for decision, count in sorted(
        EXPECTED_DECISION_COUNTS.items()
    ):
        print(
            f"  {decision}: {count}"
        )

    print()
    print(
        "Surface types:"
    )

    for surface, count in sorted(
        EXPECTED_SURFACE_COUNTS.items()
    ):
        print(
            f"  {surface}: {count}"
        )

    print()
    print(
        "Retrieval channels:"
    )

    for channel, count in sorted(
        retrieval_channel_counts.items()
    ):
        print(
            f"  {channel}: {count}"
        )

    print()
    print(
        "Multi-location vectors:"
    )

    for record in multi_location_vectors:
        print(
            "  "
            f"{record['suite']}:"
            f"{record['vector_id']} "
            f"({record['location_count']})"
        )

    print()
    print(
        f"Catalog: {CURATED_PATH}"
    )

    print(
        f"Report: {REPORT_PATH}"
    )


if __name__ == "__main__":
    main()

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


SOURCE_PATH = Path(
    "data/interim/"
    "banking77_balanced_candidate_pool_v0.1.jsonl"
)

AUDIT_PATH = Path(
    "data/interim/"
    "banking77_category_audit_pool_v0.1.csv"
)

OUTPUT_DIR = Path(
    "data/processed"
)

LEDGER_PATH = (
    OUTPUT_DIR /
    "banking77_curated_seed_ledger_v0.1.jsonl"
)

POOL_PATH = (
    OUTPUT_DIR /
    "banking77_curated_seed_pool_v0.1.jsonl"
)

REPORT_PATH = (
    OUTPUT_DIR /
    "banking77_curated_seed_pool_v0.1_report.json"
)


HUMAN_REVIEWED_CATEGORIES = {
    "benign_customer_language_seed",
    "sensitive_but_benign_customer_language",
}


def load_jsonl(
    path: Path,
) -> list[dict[str, Any]]:

    records = []

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:

        for line in file:

            line = line.strip()

            if not line:
                continue

            records.append(
                json.loads(line)
            )

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


def main() -> None:

    source_records = load_jsonl(
        SOURCE_PATH
    )

    audit_df = pd.read_csv(
        AUDIT_PATH,
        dtype="string",
    )

    for column in [
        "review_decision",
        "review_note",
    ]:
        audit_df[column] = (
            audit_df[column]
            .fillna("")
            .astype("string")
        )


    # --------------------------------------------------------
    # Validate source pool
    # --------------------------------------------------------

    if len(source_records) != 385:
        raise ValueError(
            "Expected 385 balanced Banking77 candidates, "
            f"found {len(source_records)}."
        )


    source_seed_ids = [
        record["seed_id"]
        for record
        in source_records
    ]


    if len(
        source_seed_ids
    ) != len(
        set(source_seed_ids)
    ):
        raise ValueError(
            "Duplicate seed_id found in balanced source pool."
        )


    # --------------------------------------------------------
    # Validate human audit
    # --------------------------------------------------------

    if len(audit_df) != 77:
        raise ValueError(
            "Expected 77 audited category representatives, "
            f"found {len(audit_df)}."
        )


    if (
        audit_df[
            "category"
        ].nunique()
        !=
        77
    ):
        raise ValueError(
            "Expected one audited representative "
            "for each of the 77 categories."
        )


    unreviewed_audit_rows = (
        audit_df[
            "review_decision"
        ]
        ==
        ""
    )


    if unreviewed_audit_rows.any():
        raise ValueError(
            "The Banking77 category audit is incomplete."
        )


    unexpected_decisions = (
        set(
            audit_df[
                "review_decision"
            ].unique()
        )
        -
        HUMAN_REVIEWED_CATEGORIES
    )


    if unexpected_decisions:
        raise ValueError(
            "Unexpected human-review categories: "
            f"{sorted(unexpected_decisions)}"
        )


    audit_lookup = {
        str(row["seed_id"]): {
            "review_decision": str(
                row["review_decision"]
            ),
            "review_note": str(
                row["review_note"]
            ),
        }
        for _, row
        in audit_df.iterrows()
    }


    # --------------------------------------------------------
    # Build curated records
    # --------------------------------------------------------

    curated_records = []


    for source_record in source_records:

        record = dict(
            source_record
        )

        seed_id = (
            record["seed_id"]
        )


        if seed_id in audit_lookup:

            human_review = (
                audit_lookup[
                    seed_id
                ]
            )

            seed_category = (
                human_review[
                    "review_decision"
                ]
            )

            curation = {
                "status": (
                    "human_reviewed"
                ),

                "label_source": (
                    "human_review"
                ),

                "quality_tier": "A",

                "include_for_composition": True,

                "review_note": (
                    human_review[
                        "review_note"
                    ]
                ),
            }


        else:

            seed_category = (
                "benign_customer_language_seed"
            )

            curation = {
                "status": (
                    "provisional_not_human_reviewed"
                ),

                "label_source": (
                    "banking77_upstream_category_"
                    "plus_category_level_human_audit_v0.1"
                ),

                "quality_tier": "B",

                "include_for_composition": True,

                "review_note": (
                    "Provisional benign customer-language candidate. "
                    "Not individually human-reviewed. The Banking77 "
                    "category audit reviewed one diversity-selected "
                    "representative from each of the 77 categories; "
                    "all 77 were judged usable benign language."
                ),
            }


        record[
            "seed_category"
        ] = seed_category


        record[
            "curation"
        ] = curation


        record[
            "provenance"
        ][
            "curation_pipeline_version"
        ] = (
            "banking77_seed_curation_v0.1"
        )


        record[
            "provenance"
        ][
            "category_audit_version"
        ] = (
            "banking77_category_audit_v0.1"
        )


        curated_records.append(
            record
        )


    # --------------------------------------------------------
    # Validate final curation counts
    # --------------------------------------------------------

    status_counts = Counter(
        record[
            "curation"
        ][
            "status"
        ]
        for record
        in curated_records
    )


    category_counts = Counter(
        record[
            "seed_category"
        ]
        for record
        in curated_records
    )


    tier_counts = Counter(
        record[
            "curation"
        ][
            "quality_tier"
        ]
        for record
        in curated_records
    )


    expected_status_counts = {
        "human_reviewed": 77,
        "provisional_not_human_reviewed": 308,
    }


    expected_category_counts = {
        "benign_customer_language_seed": 368,
        "sensitive_but_benign_customer_language": 17,
    }


    expected_tier_counts = {
        "A": 77,
        "B": 308,
    }


    if dict(
        status_counts
    ) != expected_status_counts:

        raise ValueError(
            "Unexpected curation status counts.\n"
            f"Expected: {expected_status_counts}\n"
            f"Found: {dict(status_counts)}"
        )


    if dict(
        category_counts
    ) != expected_category_counts:

        raise ValueError(
            "Unexpected seed category counts.\n"
            f"Expected: {expected_category_counts}\n"
            f"Found: {dict(category_counts)}"
        )


    if dict(
        tier_counts
    ) != expected_tier_counts:

        raise ValueError(
            "Unexpected quality tier counts.\n"
            f"Expected: {expected_tier_counts}\n"
            f"Found: {dict(tier_counts)}"
        )


    # --------------------------------------------------------
    # Every balanced Banking77 candidate remains eligible
    # for contextual composition.
    # --------------------------------------------------------

    composition_pool = [
        record
        for record
        in curated_records
        if record[
            "curation"
        ][
            "include_for_composition"
        ]
    ]


    if len(
        composition_pool
    ) != 385:
        raise ValueError(
            "Expected all 385 curated Banking77 seeds "
            "to remain composition-eligible."
        )


    # --------------------------------------------------------
    # Write outputs
    # --------------------------------------------------------

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


    write_jsonl(
        LEDGER_PATH,
        curated_records,
    )


    write_jsonl(
        POOL_PATH,
        composition_pool,
    )


    report = {
        "dataset": "banking77",

        "curated_seed_pool_version": (
            "0.1"
        ),

        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "deduplicated_source_pool_size": (
            13071
        ),

        "balanced_candidate_pool_size": (
            385
        ),

        "category_count": (
            77
        ),

        "curated_ledger_count": (
            len(curated_records)
        ),

        "composition_eligible_count": (
            len(composition_pool)
        ),

        "seed_category_counts": dict(
            category_counts
        ),

        "curation_status_counts": dict(
            status_counts
        ),

        "quality_tier_counts": dict(
            tier_counts
        ),

        "category_audit": {
            "human_reviewed_examples": 77,

            "categories_covered": 77,

            "benign_customer_language_seed": 60,

            "sensitive_but_benign_customer_language": 17,

            "attack_contamination": 0,

            "ambiguous": 0,

            "irrelevant": 0,
        },

        "composition_policy": {
            "tier_A": (
                "Individually human-reviewed "
                "Banking77 seed."
            ),

            "tier_B": (
                "Provisional Banking77 benign-language "
                "candidate; not individually human-reviewed."
            ),

            "all_385_composition_eligible": True,
        },

        "important_note": (
            "Banking77 intent categories are preserved only as "
            "sampling and provenance metadata. Seed categories are "
            "curation labels, not Phase-1 runtime general_risk_label "
            "targets. Final runtime-risk labels are assigned only "
            "after contextual scenario composition."
        ),
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
        "BANKING77 CURATED SEED POOL v0.1 FINALIZED"
    )
    print("=" * 80)

    print()
    print(
        "Curated ledger records:",
        len(curated_records),
    )

    print(
        "Composition eligible:",
        len(composition_pool),
    )

    print()
    print(
        "Seed category counts:"
    )

    for category, count in (
        category_counts.items()
    ):
        print(
            f"  {category}: {count}"
        )

    print()
    print(
        "Curation status counts:"
    )

    for status, count in (
        status_counts.items()
    ):
        print(
            f"  {status}: {count}"
        )

    print()
    print(
        "Quality tier counts:"
    )

    for tier, count in (
        tier_counts.items()
    ):
        print(
            f"  {tier}: {count}"
        )

    print()
    print(
        f"Ledger: {LEDGER_PATH}"
    )

    print(
        f"Composition pool: {POOL_PATH}"
    )

    print(
        f"Report: {REPORT_PATH}"
    )


if __name__ == "__main__":
    main()

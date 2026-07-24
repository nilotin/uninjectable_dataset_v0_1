from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


SOURCE_PATH = Path(
    "data/interim/"
    "deepset_seed_review_queue_with_provisional_v0.1.csv"
)

OUTPUT_DIR = Path(
    "data/processed"
)

LEDGER_PATH = (
    OUTPUT_DIR /
    "deepset_curated_seed_ledger_v0.1.jsonl"
)

POOL_PATH = (
    OUTPUT_DIR /
    "deepset_curated_seed_pool_v0.1.jsonl"
)

REPORT_PATH = (
    OUTPUT_DIR /
    "deepset_curated_seed_pool_v0.1_report.json"
)


COMPOSITION_ELIGIBLE_CATEGORIES = {
    "usable_attack_seed",
    "benign_instruction_seed",
    "benign_language_seed",
}


def normalize_string(
    value: Any,
) -> str:

    if pd.isna(value):
        return ""

    return str(value).strip()


def sha256_text(
    text: str,
) -> str:

    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


def optional_field(
    row: pd.Series,
    name: str,
) -> str:

    if name not in row.index:
        return ""

    return normalize_string(
        row[name]
    )


def resolve_curation(
    row: pd.Series,
) -> dict[str, Any]:

    human_decision = normalize_string(
        row.get(
            "review_decision",
            "",
        )
    )

    provisional_decision = normalize_string(
        row.get(
            "provisional_decision",
            "",
        )
    )


    # --------------------------------------------------------
    # Human-reviewed rows always take precedence.
    # --------------------------------------------------------

    if human_decision:

        include_for_composition = (
            human_decision
            in
            COMPOSITION_ELIGIBLE_CATEGORIES
        )

        return {
            "seed_category": human_decision,
            "curation_status": "human_reviewed",
            "label_source": "human_review",
            "quality_tier": (
                "A"
                if include_for_composition
                else "excluded"
            ),
            "include_for_composition": (
                include_for_composition
            ),
            "review_note": normalize_string(
                row.get(
                    "review_note",
                    "",
                )
            ),
        }


    # --------------------------------------------------------
    # Provisional rows remain explicitly non-human-reviewed.
    # --------------------------------------------------------

    if provisional_decision:

        return {
            "seed_category": provisional_decision,
            "curation_status": (
                "provisional_not_human_reviewed"
            ),
            "label_source": normalize_string(
                row.get(
                    "provisional_label_source",
                    "",
                )
            ),
            "quality_tier": "B",
            "include_for_composition": True,
            "review_note": normalize_string(
                row.get(
                    "provisional_note",
                    "",
                )
            ),
        }


    # --------------------------------------------------------
    # No row should reach this point in the finalized source.
    # --------------------------------------------------------

    raise ValueError(
        "Seed has neither a human review decision "
        "nor a provisional decision: "
        f"{row.get('seed_id', '<unknown>')}"
    )


def build_record(
    row: pd.Series,
) -> dict[str, Any]:

    content = normalize_string(
        row["content"]
    )

    curation = resolve_curation(
        row
    )


    record = {
        "seed_id": normalize_string(
            row["seed_id"]
        ),

        "content": content,

        "content_sha256": sha256_text(
            content
        ),

        "seed_category": curation[
            "seed_category"
        ],

        "curation": {
            "status": curation[
                "curation_status"
            ],
            "label_source": curation[
                "label_source"
            ],
            "quality_tier": curation[
                "quality_tier"
            ],
            "include_for_composition": curation[
                "include_for_composition"
            ],
            "review_note": curation[
                "review_note"
            ],
        },

        "source": {
            "dataset": (
                "deepset_prompt_injections"
            ),
            "upstream_split": optional_field(
                row,
                "upstream_split",
            ),
            "upstream_label": optional_field(
                row,
                "upstream_label",
            ),
            "original_seed_type": optional_field(
                row,
                "original_seed_type",
            ),
        },

        "quality": {
            "word_count": optional_field(
                row,
                "word_count",
            ),
        },

        "provenance": {
            "source_record_id": (
                normalize_string(
                    row["seed_id"]
                )
            ),
            "curation_pipeline_version": (
                "deepset_seed_curation_v0.1"
            ),
            "frozen_heuristic_version": (
                "0.3.2"
            ),
        },
    }


    return record


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

            file.write(
                "\n"
            )


def main() -> None:

    df = pd.read_csv(
        SOURCE_PATH,
        dtype="string",
    )


    required_columns = {
        "seed_id",
        "content",
        "review_decision",
        "provisional_decision",
    }


    missing_columns = (
        required_columns
        -
        set(df.columns)
    )


    if missing_columns:
        raise ValueError(
            "Missing required columns: "
            f"{sorted(missing_columns)}"
        )


    # --------------------------------------------------------
    # Basic source validation
    # --------------------------------------------------------

    if len(df) != 662:
        raise ValueError(
            "Expected 662 Deepset seeds, "
            f"found {len(df)}."
        )


    if df["seed_id"].duplicated().any():

        duplicates = (
            df.loc[
                df[
                    "seed_id"
                ].duplicated(
                    keep=False
                ),
                "seed_id",
            ]
            .tolist()
        )

        raise ValueError(
            "Duplicate seed_id values found: "
            f"{duplicates[:10]}"
        )


    records = [
        build_record(
            row
        )
        for _, row
        in df.iterrows()
    ]


    # --------------------------------------------------------
    # Split into full ledger and composition pool
    # --------------------------------------------------------

    composition_pool = [
        record
        for record
        in records
        if record[
            "curation"
        ][
            "include_for_composition"
        ]
    ]


    excluded_records = [
        record
        for record
        in records
        if not record[
            "curation"
        ][
            "include_for_composition"
        ]
    ]


    # --------------------------------------------------------
    # Expected-count validation
    # --------------------------------------------------------

    category_counts = Counter(
        record[
            "seed_category"
        ]
        for record
        in records
    )


    status_counts = Counter(
        record[
            "curation"
        ][
            "status"
        ]
        for record
        in records
    )


    tier_counts = Counter(
        record[
            "curation"
        ][
            "quality_tier"
        ]
        for record
        in records
    )


    expected_category_counts = {
        "usable_attack_seed": 132,
        "benign_instruction_seed": 89,
        "benign_language_seed": 400,
        "ambiguous_instruction": 37,
        "irrelevant": 4,
    }


    if dict(
        category_counts
    ) != expected_category_counts:

        raise ValueError(
            "Unexpected category counts.\n"
            f"Expected: "
            f"{expected_category_counts}\n"
            f"Found: "
            f"{dict(category_counts)}"
        )


    if len(
        composition_pool
    ) != 621:

        raise ValueError(
            "Expected 621 composition-eligible "
            f"records, found {len(composition_pool)}."
        )


    if len(
        excluded_records
    ) != 41:

        raise ValueError(
            "Expected 41 excluded records, "
            f"found {len(excluded_records)}."
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
        records,
    )


    write_jsonl(
        POOL_PATH,
        composition_pool,
    )


    report = {
        "dataset": (
            "deepset_prompt_injections"
        ),
        "curated_seed_pool_version": (
            "0.1"
        ),
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "source_seed_count": (
            len(records)
        ),

        "composition_eligible_count": (
            len(composition_pool)
        ),

        "excluded_count": (
            len(excluded_records)
        ),

        "category_counts": dict(
            category_counts
        ),

        "curation_status_counts": dict(
            status_counts
        ),

        "quality_tier_counts": dict(
            tier_counts
        ),

        "human_reviewed_count": (
            status_counts[
                "human_reviewed"
            ]
        ),

        "provisional_count": (
            status_counts[
                "provisional_not_human_reviewed"
            ]
        ),

        "composition_policy": {
            "included_categories": sorted(
                COMPOSITION_ELIGIBLE_CATEGORIES
            ),
            "excluded_categories": [
                "ambiguous_instruction",
                "irrelevant",
            ],
            "tier_A": (
                "Human-reviewed and "
                "composition-eligible."
            ),
            "tier_B": (
                "Provisional benign-language "
                "candidate; not human-reviewed."
            ),
        },

        "important_note": (
            "Seed categories are curation labels, "
            "not Phase-1 runtime general_risk_label "
            "targets. Final runtime labels are assigned "
            "only after contextual scenario composition."
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
        "DEEPSET CURATED SEED POOL v0.1 FINALIZED"
    )
    print("=" * 80)

    print()
    print(
        "Total ledger records:",
        len(records),
    )

    print(
        "Composition eligible:",
        len(composition_pool),
    )

    print(
        "Excluded:",
        len(excluded_records),
    )

    print()
    print(
        "Category counts:"
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

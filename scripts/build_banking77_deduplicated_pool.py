from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


SOURCE_DIR = Path(
    "data/raw/"
    "banking77_source/"
    "banking_data"
)

TRAIN_PATH = SOURCE_DIR / "train.csv"
TEST_PATH = SOURCE_DIR / "test.csv"

OUTPUT_DIR = Path(
    "data/interim"
)

POOL_PATH = (
    OUTPUT_DIR /
    "banking77_deduplicated_candidate_pool_v0.1.jsonl"
)

REPORT_PATH = (
    OUTPUT_DIR /
    "banking77_deduplicated_candidate_pool_v0.1_report.json"
)


def normalize_text(text: str) -> str:
    return " ".join(
        str(text)
        .strip()
        .lower()
        .split()
    )


def sha256_text(text: str) -> str:
    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


def load_split(
    path: Path,
    split_name: str,
) -> pd.DataFrame:

    df = pd.read_csv(
        path
    )

    df["source_split"] = (
        split_name
    )

    df[
        "source_record_index"
    ] = range(
        len(df)
    )

    df[
        "normalized_text"
    ] = (
        df["text"]
        .fillna("")
        .astype(str)
        .map(
            normalize_text
        )
    )

    return df


def choose_canonical_row(
    group: pd.DataFrame,
) -> pd.Series:

    candidates = (
        group
        .copy()
    )

    # Prefer the version with the most preserved visible text.
    candidates[
        "stripped_length"
    ] = (
        candidates[
            "text"
        ]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.len()
    )

    # Stable deterministic tie-break:
    # train before test, then lower source index.
    candidates[
        "split_priority"
    ] = (
        candidates[
            "source_split"
        ]
        .map(
            {
                "train": 0,
                "test": 1,
            }
        )
        .fillna(99)
    )

    candidates = (
        candidates
        .sort_values(
            by=[
                "stripped_length",
                "split_priority",
                "source_record_index",
            ],
            ascending=[
                False,
                True,
                True,
            ],
        )
    )

    return candidates.iloc[0]


def main() -> None:

    train_df = load_split(
        TRAIN_PATH,
        "train",
    )

    test_df = load_split(
        TEST_PATH,
        "test",
    )

    df = pd.concat(
        [
            train_df,
            test_df,
        ],
        ignore_index=True,
    )


    records: list[
        dict[str, Any]
    ] = []


    for normalized_text, group in (
        df.groupby(
            "normalized_text",
            sort=True,
        )
    ):

        categories = sorted(
            group[
                "category"
            ]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )

        if len(categories) != 1:
            raise ValueError(
                "Category conflict found for normalized text:\n"
                f"{normalized_text}\n"
                f"Categories: {categories}"
            )


        canonical = (
            choose_canonical_row(
                group
            )
        )

        canonical_text = (
            str(
                canonical[
                    "text"
                ]
            )
            .strip()
        )

        category = (
            categories[0]
        )


        occurrences = []

        for _, row in (
            group
            .sort_values(
                by=[
                    "source_split",
                    "source_record_index",
                ]
            )
            .iterrows()
        ):

            occurrences.append(
                {
                    "split": str(
                        row[
                            "source_split"
                        ]
                    ),
                    "record_index": int(
                        row[
                            "source_record_index"
                        ]
                    ),
                }
            )


        seed_id = (
            "banking77_"
            +
            sha256_text(
                normalized_text
            )[:16]
        )


        record = {
            "seed_id": seed_id,

            "content": (
                canonical_text
            ),

            "content_sha256": (
                sha256_text(
                    canonical_text
                )
            ),

            "normalized_content_sha256": (
                sha256_text(
                    normalized_text
                )
            ),

            "category": category,

            "candidate_seed_type": (
                "benign_customer_language_candidate"
            ),

            "curation_status": (
                "unreviewed_candidate"
            ),

            "source": {
                "dataset": "banking77",
                "occurrence_count": int(
                    len(group)
                ),
                "source_occurrences": (
                    occurrences
                ),
            },

            "quality": {
                "character_count": int(
                    len(
                        canonical_text
                    )
                ),
                "word_count": int(
                    len(
                        canonical_text.split()
                    )
                ),
                "normalized_duplicate": bool(
                    len(group) > 1
                ),
                "duplicate_group_size": int(
                    len(group)
                ),
            },

            "provenance": {
                "transformation": (
                    "normalized_text_deduplication"
                ),
                "pipeline_version": (
                    "banking77_ingestion_v0.1"
                ),
                "upstream_category_usage": (
                    "sampling_and_diversity_metadata_only"
                ),
            },
        }


        records.append(
            record
        )


    category_counts = Counter(
        record[
            "category"
        ]
        for record
        in records
    )


    duplicate_seed_count = sum(
        1
        for record
        in records
        if record[
            "quality"
        ][
            "normalized_duplicate"
        ]
    )


    if len(records) != 13071:
        raise ValueError(
            "Expected 13,071 unique normalized records, "
            f"found {len(records)}."
        )


    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


    with POOL_PATH.open(
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


    report = {
        "dataset": "banking77",
        "version": "0.1",
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "raw_row_count": int(
            len(df)
        ),

        "unique_normalized_seed_count": int(
            len(records)
        ),

        "rows_removed_by_deduplication": int(
            len(df)
            -
            len(records)
        ),

        "duplicate_seed_groups": int(
            duplicate_seed_count
        ),

        "category_count": int(
            len(
                category_counts
            )
        ),

        "category_counts_after_deduplication": dict(
            sorted(
                category_counts.items()
            )
        ),

        "important_note": (
            "Banking77 intent categories are preserved only as "
            "sampling and provenance metadata. They are not "
            "Uninjectable training targets and do not imply a "
            "runtime-risk label."
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
        "BANKING77 DEDUPLICATED CANDIDATE POOL CREATED"
    )
    print("=" * 80)

    print()
    print(
        "Raw rows:",
        len(df),
    )

    print(
        "Unique normalized seeds:",
        len(records),
    )

    print(
        "Rows removed by deduplication:",
        len(df) - len(records),
    )

    print(
        "Duplicate seed groups:",
        duplicate_seed_count,
    )

    print(
        "Categories:",
        len(category_counts),
    )

    print()
    print(
        f"Candidate pool: {POOL_PATH}"
    )

    print(
        f"Report: {REPORT_PATH}"
    )


if __name__ == "__main__":
    main()

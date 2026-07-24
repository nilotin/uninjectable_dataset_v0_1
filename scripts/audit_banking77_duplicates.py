from __future__ import annotations

from pathlib import Path

import pandas as pd


SOURCE_DIR = Path(
    "data/raw/"
    "banking77_source/"
    "banking_data"
)

TRAIN_PATH = SOURCE_DIR / "train.csv"
TEST_PATH = SOURCE_DIR / "test.csv"

OUTPUT_PATH = Path(
    "data/interim/"
    "banking77_duplicate_audit_v0.1.csv"
)


def normalize_text(text: str) -> str:
    return " ".join(
        str(text)
        .strip()
        .lower()
        .split()
    )


def main() -> None:

    train_df = pd.read_csv(
        TRAIN_PATH
    )

    test_df = pd.read_csv(
        TEST_PATH
    )

    train_df[
        "source_split"
    ] = "train"

    test_df[
        "source_split"
    ] = "test"

    train_df[
        "source_record_index"
    ] = range(
        len(train_df)
    )

    test_df[
        "source_record_index"
    ] = range(
        len(test_df)
    )


    df = pd.concat(
        [
            train_df,
            test_df,
        ],
        ignore_index=True,
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


    duplicate_mask = (
        df[
            "normalized_text"
        ]
        .duplicated(
            keep=False
        )
    )


    duplicates = df[
        duplicate_mask
    ].copy()


    # --------------------------------------------------------
    # Group-level metadata
    # --------------------------------------------------------

    group_metadata = (
        duplicates
        .groupby(
            "normalized_text",
            sort=False,
        )
        .agg(
            duplicate_group_size=(
                "normalized_text",
                "size",
            ),
            unique_category_count=(
                "category",
                "nunique",
            ),
            unique_split_count=(
                "source_split",
                "nunique",
            ),
        )
        .reset_index()
    )


    duplicates = duplicates.merge(
        group_metadata,
        on="normalized_text",
        how="left",
    )


    duplicates[
        "has_category_conflict"
    ] = (
        duplicates[
            "unique_category_count"
        ]
        >
        1
    )


    duplicates[
        "is_cross_split_duplicate"
    ] = (
        duplicates[
            "unique_split_count"
        ]
        >
        1
    )


    duplicates = (
        duplicates
        .sort_values(
            by=[
                "has_category_conflict",
                "is_cross_split_duplicate",
                "normalized_text",
                "source_split",
            ],
            ascending=[
                False,
                False,
                True,
                True,
            ],
        )
        .reset_index(
            drop=True
        )
    )


    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )


    duplicates.to_csv(
        OUTPUT_PATH,
        index=False,
    )


    duplicate_group_count = (
        duplicates[
            "normalized_text"
        ]
        .nunique()
    )


    conflict_group_count = (
        duplicates.loc[
            duplicates[
                "has_category_conflict"
            ],
            "normalized_text",
        ]
        .nunique()
    )


    cross_split_group_count = (
        duplicates.loc[
            duplicates[
                "is_cross_split_duplicate"
            ],
            "normalized_text",
        ]
        .nunique()
    )


    print("=" * 80)
    print(
        "BANKING77 DUPLICATE AUDIT"
    )
    print("=" * 80)

    print()
    print(
        "Rows in duplicate groups:",
        len(duplicates),
    )

    print(
        "Duplicate groups:",
        duplicate_group_count,
    )

    print(
        "Groups with category conflicts:",
        conflict_group_count,
    )

    print(
        "Cross-split duplicate groups:",
        cross_split_group_count,
    )


    print()
    print("=" * 80)
    print(
        "DUPLICATE GROUPS"
    )
    print("=" * 80)


    for normalized_text, group in (
        duplicates.groupby(
            "normalized_text",
            sort=False,
        )
    ):

        print()

        print("-" * 80)

        print(
            "TEXT:",
            group.iloc[0][
                "text"
            ],
        )

        print(
            "GROUP SIZE:",
            len(group),
        )

        print(
            "CATEGORY CONFLICT:",
            bool(
                group.iloc[0][
                    "has_category_conflict"
                ]
            ),
        )

        print(
            "CROSS SPLIT:",
            bool(
                group.iloc[0][
                    "is_cross_split_duplicate"
                ]
            ),
        )

        print()

        for _, row in group.iterrows():

            print(
                f"  [{row['source_split']}] "
                f"{row['category']} "
                f"(index={row['source_record_index']})"
            )


    print()
    print("=" * 80)

    print(
        f"Audit export: {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()

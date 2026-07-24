from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import pandas as pd


SOURCE_DIR = Path(
    "data/raw/"
    "banking77_source/"
    "banking_data"
)

TRAIN_PATH = (
    SOURCE_DIR /
    "train.csv"
)

TEST_PATH = (
    SOURCE_DIR /
    "test.csv"
)

CATEGORIES_PATH = (
    SOURCE_DIR /
    "categories.json"
)

OUTPUT_PATH = Path(
    "data/interim/"
    "banking77_inspection_v0.1.json"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file:
        while True:
            chunk = file.read(
                1024 * 1024
            )

            if not chunk:
                break

            digest.update(
                chunk
            )

    return digest.hexdigest()


def normalize_text(text: str) -> str:
    return " ".join(
        str(text)
        .strip()
        .lower()
        .split()
    )


def inspect_split(
    df: pd.DataFrame,
    split_name: str,
) -> dict:

    normalized = (
        df["text"]
        .fillna("")
        .astype(str)
        .map(
            normalize_text
        )
    )

    duplicate_mask = (
        normalized
        .duplicated(
            keep=False
        )
    )

    return {
        "split": split_name,
        "rows": int(
            len(df)
        ),
        "columns": (
            df.columns
            .tolist()
        ),
        "missing_values": {
            column: int(
                df[column]
                .isna()
                .sum()
            )
            for column
            in df.columns
        },
        "unique_normalized_texts": int(
            normalized.nunique()
        ),
        "rows_in_duplicate_groups": int(
            duplicate_mask.sum()
        ),
        "category_counts": (
            df["category"]
            .value_counts()
            .sort_index()
            .to_dict()
        ),
        "text_length": {
            "min_chars": int(
                df["text"]
                .fillna("")
                .astype(str)
                .str.len()
                .min()
            ),
            "max_chars": int(
                df["text"]
                .fillna("")
                .astype(str)
                .str.len()
                .max()
            ),
            "mean_chars": float(
                df["text"]
                .fillna("")
                .astype(str)
                .str.len()
                .mean()
            ),
        },
    }


def main() -> None:

    train_df = pd.read_csv(
        TRAIN_PATH
    )

    test_df = pd.read_csv(
        TEST_PATH
    )

    categories = json.loads(
        CATEGORIES_PATH.read_text(
            encoding="utf-8"
        )
    )


    print("=" * 80)
    print(
        "BANKING77 SOURCE INSPECTION"
    )
    print("=" * 80)

    print()
    print(
        "Train shape:",
        train_df.shape,
    )

    print(
        "Test shape:",
        test_df.shape,
    )

    print()
    print(
        "Train columns:",
        train_df.columns.tolist(),
    )

    print(
        "Test columns:",
        test_df.columns.tolist(),
    )

    print()
    print(
        "Categories:",
        len(categories),
    )


    print()
    print("=" * 80)
    print(
        "TRAIN CATEGORY COUNTS"
    )
    print("=" * 80)

    print(
        train_df[
            "category"
        ]
        .value_counts()
        .sort_index()
        .to_string()
    )


    print()
    print("=" * 80)
    print(
        "TEST CATEGORY COUNTS"
    )
    print("=" * 80)

    print(
        test_df[
            "category"
        ]
        .value_counts()
        .sort_index()
        .to_string()
    )


    # --------------------------------------------------------
    # Cross-split duplicate check
    # --------------------------------------------------------

    train_normalized = set(
        train_df[
            "text"
        ]
        .fillna("")
        .astype(str)
        .map(
            normalize_text
        )
    )

    test_normalized = set(
        test_df[
            "text"
        ]
        .fillna("")
        .astype(str)
        .map(
            normalize_text
        )
    )

    cross_split_duplicates = (
        train_normalized
        &
        test_normalized
    )


    print()
    print("=" * 80)
    print(
        "DUPLICATE CHECKS"
    )
    print("=" * 80)

    print(
        "Cross-split normalized duplicates:",
        len(cross_split_duplicates),
    )


    combined = pd.concat(
        [
            train_df.assign(
                source_split="train"
            ),
            test_df.assign(
                source_split="test"
            ),
        ],
        ignore_index=True,
    )

    combined[
        "normalized_text"
    ] = (
        combined[
            "text"
        ]
        .fillna("")
        .astype(str)
        .map(
            normalize_text
        )
    )


    duplicate_counts = Counter(
        combined[
            "normalized_text"
        ]
    )

    duplicated_texts = {
        text
        for text, count
        in duplicate_counts.items()
        if count > 1
    }


    print(
        "Unique normalized texts:",
        combined[
            "normalized_text"
        ].nunique(),
    )

    print(
        "Rows in duplicate groups:",
        int(
            combined[
                "normalized_text"
            ]
            .isin(
                duplicated_texts
            )
            .sum()
        ),
    )


    report = {
        "dataset": "banking77",

        "source": {
            "repository": (
                "PolyAI-LDN/"
                "task-specific-datasets"
            ),
            "source_directory": str(
                SOURCE_DIR
            ),
            "license": "CC-BY-4.0",
        },

        "files": {
            "train.csv": {
                "sha256": sha256_file(
                    TRAIN_PATH
                ),
            },
            "test.csv": {
                "sha256": sha256_file(
                    TEST_PATH
                ),
            },
            "categories.json": {
                "sha256": sha256_file(
                    CATEGORIES_PATH
                ),
            },
        },

        "category_count": len(
            categories
        ),

        "categories": categories,

        "train": inspect_split(
            train_df,
            "train",
        ),

        "test": inspect_split(
            test_df,
            "test",
        ),

        "total_rows": int(
            len(combined)
        ),

        "unique_normalized_texts": int(
            combined[
                "normalized_text"
            ].nunique()
        ),

        "cross_split_duplicate_count": int(
            len(
                cross_split_duplicates
            )
        ),

        "rows_in_duplicate_groups": int(
            combined[
                "normalized_text"
            ]
            .isin(
                duplicated_texts
            )
            .sum()
        ),
    }


    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


    print()
    print("=" * 80)

    print(
        f"Inspection report: "
        f"{OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()

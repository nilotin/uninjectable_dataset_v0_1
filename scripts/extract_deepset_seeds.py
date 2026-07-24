from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import pandas as pd


SOURCE_DATASET = "deepset/prompt-injections"

SOURCE_DIR = Path(
    "data/raw/deepset_prompt_injections/data"
)

OUTPUT_PATH = Path(
    "data/interim/deepset_seed_pool_v0.1.jsonl"
)

REPORT_PATH = Path(
    "data/interim/deepset_seed_pool_report_v0.1.json"
)


def normalize_text(text: str) -> str:
    """
    Normalize text for duplicate detection only.

    The original text is preserved separately in `content`.
    """
    return " ".join(
        str(text).split()
    ).strip()


def sha256_text(text: str) -> str:
    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


def label_to_seed_type(label: int) -> str:
    """
    Convert the upstream label into a seed candidate type.

    IMPORTANT:
    This is NOT an Uninjectable runtime-risk label.
    """
    if label == 0:
        return "benign_language_candidate"

    if label == 1:
        return "attack_language_candidate"

    return "unknown_language_candidate"


def main() -> None:
    parquet_files = sorted(
        SOURCE_DIR.glob("*.parquet")
    )

    if not parquet_files:
        raise FileNotFoundError(
            f"No parquet files found under {SOURCE_DIR}"
        )

    raw_records = []

    # --------------------------------------------------
    # 1. Load every upstream split
    # --------------------------------------------------

    for parquet_path in parquet_files:
        split_name = parquet_path.name.split(
            "-", 1
        )[0]

        df = pd.read_parquet(
            parquet_path
        )

        required_columns = {
            "text",
            "label",
        }

        missing_columns = (
            required_columns
            - set(df.columns)
        )

        if missing_columns:
            raise ValueError(
                f"{parquet_path} is missing columns: "
                f"{sorted(missing_columns)}"
            )

        for record_index, row in df.iterrows():
            content = str(
                row["text"]
            )

            normalized_content = (
                normalize_text(content)
            )

            upstream_label = int(
                row["label"]
            )

            raw_records.append(
                {
                    "split": split_name,
                    "record_index": int(
                        record_index
                    ),
                    "content": content,
                    "normalized_content": (
                        normalized_content
                    ),
                    "content_sha256": (
                        sha256_text(
                            normalized_content
                        )
                    ),
                    "upstream_label": (
                        upstream_label
                    ),
                }
            )

    # --------------------------------------------------
    # 2. Count normalized duplicate groups
    # --------------------------------------------------

    duplicate_counter = Counter(
        record["content_sha256"]
        for record in raw_records
    )

    # --------------------------------------------------
    # 3. Build normalized atomic seeds
    # --------------------------------------------------

    seeds = []

    for record in raw_records:
        split_name = record["split"]

        record_index = record[
            "record_index"
        ]

        seed_id = (
            f"deepset_"
            f"{split_name}_"
            f"{record_index:06d}"
        )

        duplicate_group_size = (
            duplicate_counter[
                record["content_sha256"]
            ]
        )

        seed = {
            "seed_id": seed_id,

            "seed_type": (
                label_to_seed_type(
                    record["upstream_label"]
                )
            ),

            "content": record["content"],

            "content_sha256": (
                record["content_sha256"]
            ),

            "review_status": "unreviewed",

            "quality": {
                "character_count": len(
                    record["content"]
                ),

                "word_count": len(
                    record["content"].split()
                ),

                "normalized_duplicate": (
                    duplicate_group_size > 1
                ),

                "normalized_duplicate_group_size": (
                    duplicate_group_size
                ),
            },

            "source": {
                "dataset": SOURCE_DATASET,

                "split": split_name,

                "record_index": (
                    record_index
                ),

                "source_record_id": (
                    f"{split_name}:"
                    f"{record_index}"
                ),

                "upstream_label": (
                    record["upstream_label"]
                ),

                "upstream_label_usage": (
                    "Seed candidate typing only; "
                    "not an Uninjectable "
                    "general_risk_label."
                ),
            },
        }

        seeds.append(seed)

    # --------------------------------------------------
    # 4. Write JSONL seed pool
    # --------------------------------------------------

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_PATH.open(
        "w",
        encoding="utf-8",
    ) as file:
        for seed in seeds:
            file.write(
                json.dumps(
                    seed,
                    ensure_ascii=False,
                )
                + "\n"
            )

    # --------------------------------------------------
    # 5. Produce extraction report
    # --------------------------------------------------

    seed_type_counts = Counter(
        seed["seed_type"]
        for seed in seeds
    )

    duplicate_seed_count = sum(
        1
        for seed in seeds
        if seed["quality"][
            "normalized_duplicate"
        ]
    )

    unique_content_hashes = len(
        {
            seed["content_sha256"]
            for seed in seeds
        }
    )

    report = {
        "source_dataset": (
            SOURCE_DATASET
        ),

        "extraction_version": "0.1",

        "total_seeds": len(
            seeds
        ),

        "seed_type_counts": dict(
            seed_type_counts
        ),

        "unique_normalized_contents": (
            unique_content_hashes
        ),

        "seeds_in_duplicate_groups": (
            duplicate_seed_count
        ),

        "important_note": (
            "Upstream labels were used only "
            "to create candidate seed types. "
            "No Uninjectable general risk "
            "labels were generated."
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

    print(
        "=" * 70
    )

    print(
        "DEEPSET SEED EXTRACTION COMPLETE"
    )

    print(
        "=" * 70
    )

    print(
        f"Total seeds: {len(seeds)}"
    )

    print(
        f"Seed type counts: "
        f"{dict(seed_type_counts)}"
    )

    print(
        "Unique normalized contents: "
        f"{unique_content_hashes}"
    )

    print(
        "Seeds in duplicate groups: "
        f"{duplicate_seed_count}"
    )

    print()

    print(
        f"Seed pool: {OUTPUT_PATH}"
    )

    print(
        f"Report: {REPORT_PATH}"
    )


if __name__ == "__main__":
    main()

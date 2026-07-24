from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


SOURCE_PATH = Path(
    "data/interim/"
    "banking77_balanced_candidate_pool_v0.1.jsonl"
)

OUTPUT_DIR = Path(
    "data/interim/"
    "review_batches"
)

AUDIT_POOL_PATH = Path(
    "data/interim/"
    "banking77_category_audit_pool_v0.1.csv"
)


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

            if line:

                records.append(
                    json.loads(
                        line
                    )
                )

    return records


def main() -> None:

    records = load_jsonl(
        SOURCE_PATH
    )


    rows = []

    for record in records:

        rows.append(
            {
                "seed_id": (
                    record["seed_id"]
                ),

                "category": (
                    record["category"]
                ),

                "category_cluster": (
                    record[
                        "balanced_sampling"
                    ][
                        "category_cluster"
                    ]
                ),

                "content": (
                    record["content"]
                ),

                "review_decision": "",

                "review_note": "",
            }
        )


    df = pd.DataFrame(
        rows
    )


    # One representative per category.
    #
    # Cluster 0 is deterministic under the frozen
    # sampling configuration and provides one seed
    # from every Banking77 intent category.
    audit = (
        df[
            df[
                "category_cluster"
            ]
            ==
            0
        ]
        .sort_values(
            by=[
                "category",
                "seed_id",
            ]
        )
        .reset_index(
            drop=True
        )
    )


    if len(audit) != 77:
        raise ValueError(
            "Expected 77 audit examples, "
            f"found {len(audit)}."
        )


    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


    audit.to_csv(
        AUDIT_POOL_PATH,
        index=False,
    )


    batch_013 = (
        audit.iloc[:39]
        .copy()
    )

    batch_014 = (
        audit.iloc[39:]
        .copy()
    )


    path_013 = (
        OUTPUT_DIR /
        "banking77_category_audit_batch_013.csv"
    )

    path_014 = (
        OUTPUT_DIR /
        "banking77_category_audit_batch_014.csv"
    )


    batch_013.to_csv(
        path_013,
        index=False,
    )

    batch_014.to_csv(
        path_014,
        index=False,
    )


    print("=" * 80)
    print(
        "BANKING77 CATEGORY AUDIT BATCHES CREATED"
    )
    print("=" * 80)

    print()
    print(
        "Audit examples:",
        len(audit),
    )

    print(
        "Unique categories:",
        audit[
            "category"
        ].nunique(),
    )

    print()
    print(
        "Batch 013:",
        len(batch_013),
    )

    print(
        "Batch 014:",
        len(batch_014),
    )

    print()
    print(
        f"Audit pool: {AUDIT_POOL_PATH}"
    )

    print(
        f"Batch 013: {path_013}"
    )

    print(
        f"Batch 014: {path_014}"
    )


if __name__ == "__main__":
    main()

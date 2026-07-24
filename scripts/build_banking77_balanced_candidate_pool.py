from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer


SOURCE_PATH = Path(
    "data/interim/"
    "banking77_deduplicated_candidate_pool_v0.1.jsonl"
)

OUTPUT_PATH = Path(
    "data/interim/"
    "banking77_balanced_candidate_pool_v0.1.jsonl"
)

REPORT_PATH = Path(
    "data/interim/"
    "banking77_balanced_candidate_pool_v0.1_report.json"
)

SEEDS_PER_CATEGORY = 5
RANDOM_STATE = 42


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


def select_diverse_examples(
    records: list[dict[str, Any]],
    category: str,
) -> list[dict[str, Any]]:

    if len(records) < SEEDS_PER_CATEGORY:
        raise ValueError(
            f"Category {category} has only "
            f"{len(records)} records."
        )

    texts = [
        record["content"]
        for record
        in records
    ]

    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(3, 5),
        min_df=1,
        max_features=10000,
        sublinear_tf=True,
    )

    matrix = vectorizer.fit_transform(
        texts
    )

    model = KMeans(
        n_clusters=SEEDS_PER_CATEGORY,
        random_state=RANDOM_STATE,
        n_init=20,
    )

    cluster_ids = model.fit_predict(
        matrix
    )

    selected_positions = []

    for cluster_id in range(
        SEEDS_PER_CATEGORY
    ):

        member_positions = np.where(
            cluster_ids == cluster_id
        )[0]

        if len(member_positions) == 0:
            raise ValueError(
                f"Empty cluster in category: {category}"
            )

        member_matrix = matrix[
            member_positions
        ]

        centroid = model.cluster_centers_[
            cluster_id
        ]

        distances = (
            (
                member_matrix.toarray()
                -
                centroid
            )
            ** 2
        ).sum(
            axis=1
        )

        best_position = (
            member_positions[
                int(
                    np.argmin(
                        distances
                    )
                )
            ]
        )

        selected_positions.append(
            best_position
        )

    selected = []

    for cluster_id, position in enumerate(
        selected_positions
    ):

        record = dict(
            records[position]
        )

        record[
            "balanced_sampling"
        ] = {
            "selected": True,
            "category_cluster": (
                cluster_id
            ),
            "clusters_per_category": (
                SEEDS_PER_CATEGORY
            ),
            "sampling_method": (
                "character_ngram_tfidf_kmeans_medoid"
            ),
            "sampling_version": (
                "banking77_balanced_sampling_v0.1"
            ),
        }

        selected.append(
            record
        )

    return selected


def main() -> None:

    records = load_jsonl(
        SOURCE_PATH
    )

    by_category: dict[
        str,
        list[dict[str, Any]]
    ] = {}

    for record in records:

        category = (
            record["category"]
        )

        by_category.setdefault(
            category,
            [],
        ).append(
            record
        )


    if len(by_category) != 77:
        raise ValueError(
            "Expected 77 categories, "
            f"found {len(by_category)}."
        )


    selected_records = []


    for category in sorted(
        by_category
    ):

        selected = (
            select_diverse_examples(
                records=by_category[
                    category
                ],
                category=category,
            )
        )

        selected_records.extend(
            selected
        )


    expected_count = (
        77
        *
        SEEDS_PER_CATEGORY
    )


    if len(
        selected_records
    ) != expected_count:

        raise ValueError(
            f"Expected {expected_count} selected records, "
            f"found {len(selected_records)}."
        )


    category_counts = Counter(
        record["category"]
        for record
        in selected_records
    )


    if set(
        category_counts.values()
    ) != {
        SEEDS_PER_CATEGORY
    }:

        raise ValueError(
            "Not every category has exactly "
            f"{SEEDS_PER_CATEGORY} selected records."
        )


    write_jsonl(
        OUTPUT_PATH,
        selected_records,
    )


    report = {
        "dataset": "banking77",
        "version": "0.1",
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "deduplicated_source_pool_size": (
            len(records)
        ),

        "category_count": (
            len(by_category)
        ),

        "selected_per_category": (
            SEEDS_PER_CATEGORY
        ),

        "balanced_candidate_pool_size": (
            len(selected_records)
        ),

        "sampling_method": (
            "character_ngram_tfidf_kmeans_medoid"
        ),

        "category_counts": dict(
            sorted(
                category_counts.items()
            )
        ),

        "important_note": (
            "Banking77 categories are used only for "
            "balanced sampling and provenance. They are "
            "not Uninjectable runtime-risk labels."
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
        "BANKING77 BALANCED CANDIDATE POOL CREATED"
    )
    print("=" * 80)

    print()
    print(
        "Deduplicated source pool:",
        len(records),
    )

    print(
        "Categories:",
        len(by_category),
    )

    print(
        "Selected per category:",
        SEEDS_PER_CATEGORY,
    )

    print(
        "Balanced candidate pool:",
        len(selected_records),
    )

    print()
    print(
        f"Candidate pool: {OUTPUT_PATH}"
    )

    print(
        f"Report: {REPORT_PATH}"
    )


if __name__ == "__main__":
    main()

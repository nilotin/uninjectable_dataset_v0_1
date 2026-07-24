from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer


SOURCE_PATH = Path(
    "data/interim/"
    "deepset_review_priority_queue_v0.2.1.csv"
)

OUTPUT_PATH = Path(
    "data/interim/"
    "review_batches/"
    "deepset_ambiguous_review_batch_006.csv"
)

TARGET_BATCH_SIZE = 30
RANDOM_STATE = 42


def main() -> None:
    df = pd.read_csv(
        SOURCE_PATH,
        dtype="string",
    )

    pool = df[
        df[
            "suggested_review_category_v0_2_1"
        ]
        ==
        "ambiguous_instruction"
    ].copy()

    if pool.empty:
        raise ValueError(
            "No ambiguous candidates found."
        )

    print(
        f"Ambiguous candidate pool: {len(pool)}"
    )

    n_clusters = min(
        TARGET_BATCH_SIZE,
        len(pool),
    )

    # Character n-grams are useful here because the source
    # contains multiple languages, typos, and noisy text.
    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(3, 5),
        min_df=1,
        max_features=15000,
        sublinear_tf=True,
    )

    matrix = vectorizer.fit_transform(
        pool["content"]
        .fillna("")
        .astype(str)
    )

    model = KMeans(
        n_clusters=n_clusters,
        random_state=RANDOM_STATE,
        n_init=20,
    )

    cluster_ids = model.fit_predict(
        matrix
    )

    pool["diversity_cluster"] = (
        cluster_ids
    )

    selected_indices = []

    # Select the example closest to each cluster centroid.
    for cluster_id in range(
        n_clusters
    ):
        member_positions = np.where(
            cluster_ids == cluster_id
        )[0]

        if len(member_positions) == 0:
            continue

        member_matrix = matrix[
            member_positions
        ]

        centroid = model.cluster_centers_[
            cluster_id
        ]

        # Squared Euclidean distance to centroid.
        distances = (
            (
                member_matrix.toarray()
                - centroid
            )
            ** 2
        ).sum(
            axis=1
        )

        best_local_position = (
            member_positions[
                int(
                    np.argmin(
                        distances
                    )
                )
            ]
        )

        selected_indices.append(
            best_local_position
        )

    batch = pool.iloc[
        selected_indices
    ].copy()

    batch = batch.sort_values(
        by=[
            "diversity_cluster",
            "seed_id",
        ]
    ).reset_index(
        drop=True
    )

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    batch.to_csv(
        OUTPUT_PATH,
        index=False,
    )

    print("=" * 80)
    print(
        "DIVERSE AMBIGUOUS REVIEW BATCH 006 CREATED"
    )
    print("=" * 80)

    print(
        f"Rows: {len(batch)}"
    )

    print(
        f"Unique clusters: "
        f"{batch['diversity_cluster'].nunique()}"
    )

    print(
        f"Path: {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()

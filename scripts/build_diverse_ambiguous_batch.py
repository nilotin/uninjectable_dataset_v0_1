from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer


SOURCE_PATH = Path(
    "data/interim/"
    "deepset_review_priority_queue_v0.2.1.csv"
)

RANDOM_STATE = 42


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a diversity-oriented review batch "
            "from unreviewed ambiguous seed candidates."
        )
    )

    parser.add_argument(
        "--batch-id",
        required=True,
        help="Batch identifier, for example 007.",
    )

    parser.add_argument(
        "--size",
        type=int,
        default=30,
        help="Target batch size.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    output_path = Path(
        "data/interim/"
        "review_batches/"
        f"deepset_ambiguous_review_batch_{args.batch_id}.csv"
    )

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
            "No unreviewed ambiguous candidates found."
        )

    target_size = min(
        args.size,
        len(pool),
    )

    print(
        f"Ambiguous candidate pool: {len(pool)}"
    )

    print(
        f"Requested batch size: {args.size}"
    )

    print(
        f"Actual batch size: {target_size}"
    )

    # Character n-grams work well for:
    # - multilingual data
    # - misspellings
    # - noisy prompt-injection strings
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
        n_clusters=target_size,
        random_state=RANDOM_STATE,
        n_init=20,
    )

    cluster_ids = model.fit_predict(
        matrix
    )

    pool["diversity_cluster"] = (
        cluster_ids
    )

    selected_positions = []

    for cluster_id in range(
        target_size
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

        distances = (
            (
                member_matrix.toarray()
                - centroid
            )
            ** 2
        ).sum(
            axis=1
        )

        best_position = member_positions[
            int(
                np.argmin(
                    distances
                )
            )
        ]

        selected_positions.append(
            best_position
        )

    batch = pool.iloc[
        selected_positions
    ].copy()

    batch = (
        batch
        .sort_values(
            by=[
                "diversity_cluster",
                "seed_id",
            ]
        )
        .reset_index(
            drop=True
        )
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    batch.to_csv(
        output_path,
        index=False,
    )

    print("=" * 80)

    print(
        f"DIVERSE AMBIGUOUS REVIEW "
        f"BATCH {args.batch_id} CREATED"
    )

    print("=" * 80)

    print(
        f"Rows: {len(batch)}"
    )

    print(
        "Unique clusters:",
        batch[
            "diversity_cluster"
        ].nunique(),
    )

    print(
        f"Path: {output_path}"
    )


if __name__ == "__main__":
    main()

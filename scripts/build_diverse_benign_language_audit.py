from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer


SOURCE_PATH = Path(
    "data/interim/"
    "prospective_validation_v0.3.2/"
    "predicted_benign_language_pool.csv"
)

OUTPUT_DIR = Path(
    "data/interim/"
    "review_batches"
)

FULL_AUDIT_PATH = Path(
    "data/interim/"
    "prospective_validation_v0.3.2/"
    "prospective_benign_language_audit_sample.csv"
)

TARGET_SIZE = 60
RANDOM_STATE = 42


def main() -> None:

    df = pd.read_csv(
        SOURCE_PATH,
        dtype="string",
    )

    if df.empty:
        raise ValueError(
            "Predicted benign-language pool is empty."
        )

    target_size = min(
        TARGET_SIZE,
        len(df),
    )

    print(
        "Benign-language candidate pool:",
        len(df),
    )

    print(
        "Target audit sample:",
        target_size,
    )


    # Character n-grams are useful because the source
    # includes multilingual, noisy, and misspelled text.
    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(3, 5),
        min_df=1,
        max_features=20000,
        sublinear_tf=True,
    )

    matrix = vectorizer.fit_transform(
        df["content"]
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

    df["diversity_cluster"] = (
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


    audit = df.iloc[
        selected_positions
    ].copy()


    audit = (
        audit
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


    audit[
        "prospective_audit_source"
    ] = "predicted_benign_language"


    audit[
        "prospective_audit_index"
    ] = range(
        1,
        len(audit) + 1,
    )


    FULL_AUDIT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


    audit.to_csv(
        FULL_AUDIT_PATH,
        index=False,
    )


    batch_011 = audit.iloc[
        :30
    ].copy()

    batch_012 = audit.iloc[
        30:60
    ].copy()


    path_011 = (
        OUTPUT_DIR /
        "deepset_prospective_benign_language_batch_011.csv"
    )

    path_012 = (
        OUTPUT_DIR /
        "deepset_prospective_benign_language_batch_012.csv"
    )


    batch_011.to_csv(
        path_011,
        index=False,
    )

    batch_012.to_csv(
        path_012,
        index=False,
    )


    print("=" * 80)
    print(
        "DIVERSE BENIGN-LANGUAGE AUDIT CREATED"
    )
    print("=" * 80)

    print()
    print(
        "Full candidate pool:",
        len(df),
    )

    print(
        "Selected diverse audit sample:",
        len(audit),
    )

    print(
        "Unique clusters:",
        audit[
            "diversity_cluster"
        ].nunique(),
    )

    print()
    print(
        "Batch 011 rows:",
        len(batch_011),
    )

    print(
        "Batch 012 rows:",
        len(batch_012),
    )

    print()
    print(
        f"Full audit sample: "
        f"{FULL_AUDIT_PATH}"
    )

    print(
        f"Batch 011: {path_011}"
    )

    print(
        f"Batch 012: {path_012}"
    )


if __name__ == "__main__":
    main()

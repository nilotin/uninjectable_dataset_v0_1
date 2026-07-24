from __future__ import annotations

from pathlib import Path

import pandas as pd


SOURCE_PATH = Path(
    "data/interim/"
    "deepset_heuristic_v0.2.1_evaluation.csv"
)

OUTPUT_PATH = Path(
    "data/interim/"
    "deepset_review_priority_queue_v0.2.1.csv"
)


PRIORITY_MAP = {
    "usable_attack_seed": 1,
    "ambiguous_instruction": 2,
    "benign_instruction_seed": 3,
    "benign_language_seed": 4,
}


def main() -> None:

    df = pd.read_csv(
        SOURCE_PATH,
        dtype="string",
    )

    df["review_decision"] = (
        df["review_decision"]
        .fillna("")
        .astype("string")
    )

    df["heuristic_flags_v0_2_1"] = (
        df["heuristic_flags_v0_2_1"]
        .fillna("")
        .astype("string")
    )

    # Only examples that humans have not reviewed yet.
    unreviewed = df[
        df["review_decision"] == ""
    ].copy()

    unreviewed[
        "review_priority"
    ] = (
        unreviewed[
            "suggested_review_category_v0_2_1"
        ]
        .map(PRIORITY_MAP)
        .fillna(99)
        .astype(int)
    )

    # Additional ranking signals.
    #
    # More independent heuristic flags may make the example
    # more useful to inspect early.
    unreviewed[
        "heuristic_signal_count"
    ] = (
        unreviewed[
            "heuristic_flags_v0_2_1"
        ]
        .apply(
            lambda value:
            0
            if not value
            else len(
                [
                    item
                    for item
                    in value.split("|")
                    if item
                ]
            )
        )
    )

    # Prioritize:
    #
    # 1. predicted category
    # 2. examples with more heuristic signals
    # 3. upstream attack candidates before upstream benign
    # 4. stable seed_id ordering
    unreviewed = (
        unreviewed
        .sort_values(
            by=[
                "review_priority",
                "heuristic_signal_count",
                "upstream_label",
                "seed_id",
            ],
            ascending=[
                True,
                False,
                False,
                True,
            ],
        )
        .reset_index(drop=True)
    )

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    unreviewed.to_csv(
        OUTPUT_PATH,
        index=False,
    )

    print("=" * 80)
    print(
        "REVIEW PRIORITY QUEUE v0.2.1 CREATED"
    )
    print("=" * 80)

    print()
    print(
        "Total unreviewed:",
        len(unreviewed),
    )

    print()
    print(
        "Predicted category counts:"
    )

    print(
        unreviewed[
            "suggested_review_category_v0_2_1"
        ]
        .value_counts()
        .to_string()
    )

    print()
    print(
        "Priority counts:"
    )

    print(
        unreviewed[
            "review_priority"
        ]
        .value_counts()
        .sort_index()
        .to_string()
    )

    print()
    print(
        f"Priority queue: {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()

from __future__ import annotations

from pathlib import Path

import pandas as pd


SOURCE_PATH = Path(
    "data/interim/"
    "deepset_heuristic_v0.3.2_evaluation.csv"
)

OUTPUT_DIR = Path(
    "data/interim/"
    "prospective_validation_v0.3.2"
)


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

    unreviewed = df[
        df["review_decision"] == ""
    ].copy()

    if len(unreviewed) != 469:
        print(
            "WARNING: Expected approximately 469 "
            f"unreviewed examples, found {len(unreviewed)}."
        )

    attack_pool = unreviewed[
        unreviewed[
            "suggested_review_category_v0_3_2"
        ]
        ==
        "usable_attack_seed"
    ].copy()

    ambiguous_pool = unreviewed[
        unreviewed[
            "suggested_review_category_v0_3_2"
        ]
        ==
        "ambiguous_instruction"
    ].copy()

    benign_instruction_pool = unreviewed[
        unreviewed[
            "suggested_review_category_v0_3_2"
        ]
        ==
        "benign_instruction_seed"
    ].copy()

    benign_language_pool = unreviewed[
        unreviewed[
            "suggested_review_category_v0_3_2"
        ]
        ==
        "benign_language_seed"
    ].copy()

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    attack_pool.to_csv(
        OUTPUT_DIR /
        "predicted_attack_pool.csv",
        index=False,
    )

    ambiguous_pool.to_csv(
        OUTPUT_DIR /
        "predicted_ambiguous_pool.csv",
        index=False,
    )

    benign_instruction_pool.to_csv(
        OUTPUT_DIR /
        "predicted_benign_instruction_pool.csv",
        index=False,
    )

    benign_language_pool.to_csv(
        OUTPUT_DIR /
        "predicted_benign_language_pool.csv",
        index=False,
    )

    print("=" * 80)
    print(
        "PROSPECTIVE VALIDATION POOLS v0.3.2"
    )
    print("=" * 80)

    print()
    print(
        "Total unreviewed:",
        len(unreviewed),
    )

    print()
    print(
        "Predicted attack:",
        len(attack_pool),
    )

    print(
        "Predicted ambiguous:",
        len(ambiguous_pool),
    )

    print(
        "Predicted benign instruction:",
        len(benign_instruction_pool),
    )

    print(
        "Predicted benign language:",
        len(benign_language_pool),
    )

    print()
    print(
        f"Output directory: {OUTPUT_DIR}"
    )


if __name__ == "__main__":
    main()

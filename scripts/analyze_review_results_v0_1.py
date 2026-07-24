from __future__ import annotations

from pathlib import Path

import pandas as pd


SOURCE_PATH = Path(
    "data/interim/"
    "deepset_seed_review_queue_v0.1.csv"
)

OUTPUT_PATH = Path(
    "data/interim/"
    "deepset_review_analysis_v0.1.csv"
)


def normalize_empty(series: pd.Series) -> pd.Series:
    return (
        series
        .fillna("")
        .astype("string")
        .str.strip()
    )


def main() -> None:
    df = pd.read_csv(
        SOURCE_PATH,
        dtype="string",
    )

    df["review_decision"] = normalize_empty(
        df["review_decision"]
    )

    df["suggested_review_category"] = normalize_empty(
        df["suggested_review_category"]
    )

    df["heuristic_flags"] = normalize_empty(
        df["heuristic_flags"]
    )

    reviewed = df[
        df["review_decision"] != ""
    ].copy()

    if reviewed.empty:
        raise ValueError(
            "No reviewed examples found."
        )

    reviewed["suggestion_matches_human"] = (
        reviewed["suggested_review_category"]
        ==
        reviewed["review_decision"]
    )

    print("=" * 80)
    print("DEEPSET REVIEW ANALYSIS v0.1")
    print("=" * 80)

    print()
    print("Reviewed examples:")
    print(len(reviewed))

    print()
    print("Human decision counts:")
    print(
        reviewed["review_decision"]
        .value_counts()
        .to_string()
    )

    print()
    print("Suggestion accuracy:")
    accuracy = (
        reviewed[
            "suggestion_matches_human"
        ]
        .mean()
    )

    print(
        f"{accuracy:.2%}"
    )

    print()
    print("=" * 80)
    print("SUGGESTION → HUMAN DECISION")
    print("=" * 80)

    confusion = pd.crosstab(
        reviewed[
            "suggested_review_category"
        ],
        reviewed[
            "review_decision"
        ],
        margins=True,
    )

    print(confusion.to_string())

    print()
    print("=" * 80)
    print("HEURISTIC FLAGS → HUMAN DECISION")
    print("=" * 80)

    flag_analysis = pd.crosstab(
        reviewed["heuristic_flags"],
        reviewed["review_decision"],
        margins=True,
    )

    print(flag_analysis.to_string())

    print()
    print("=" * 80)
    print("MISSED USABLE ATTACK SEEDS")
    print("=" * 80)

    missed_attacks = reviewed[
        (
            reviewed[
                "review_decision"
            ]
            ==
            "usable_attack_seed"
        )
        &
        (
            reviewed[
                "suggested_review_category"
            ]
            !=
            "usable_attack_seed"
        )
    ]

    if missed_attacks.empty:
        print(
            "No missed usable attacks."
        )
    else:
        for _, row in missed_attacks.iterrows():
            print()
            print(
                "SEED:",
                row["seed_id"],
            )
            print(
                "SUGGESTION:",
                row[
                    "suggested_review_category"
                ],
            )
            print(
                "FLAGS:",
                row[
                    "heuristic_flags"
                ],
            )
            print(
                "TEXT:",
                row["content"],
            )

    print()
    print("=" * 80)
    print("FALSE ATTACK SUGGESTIONS")
    print("=" * 80)

    false_attack_suggestions = reviewed[
        (
            reviewed[
                "suggested_review_category"
            ]
            ==
            "usable_attack_seed"
        )
        &
        (
            reviewed[
                "review_decision"
            ]
            !=
            "usable_attack_seed"
        )
    ]

    if false_attack_suggestions.empty:
        print(
            "No false attack suggestions."
        )
    else:
        for _, row in false_attack_suggestions.iterrows():
            print()
            print(
                "SEED:",
                row["seed_id"],
            )
            print(
                "HUMAN:",
                row[
                    "review_decision"
                ],
            )
            print(
                "FLAGS:",
                row[
                    "heuristic_flags"
                ],
            )
            print(
                "TEXT:",
                row["content"],
            )

    reviewed.to_csv(
        OUTPUT_PATH,
        index=False,
    )

    print()
    print("=" * 80)
    print(
        f"Analysis export: {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()

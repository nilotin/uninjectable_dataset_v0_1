from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from evaluate_heuristic_v0_2 import classify_v0_2


SOURCE_PATH = Path(
    "data/interim/"
    "deepset_seed_review_queue_v0.1.csv"
)

OUTPUT_PATH = Path(
    "data/interim/"
    "deepset_heuristic_v0.2.1_evaluation.csv"
)


# Newly observed attack formulations that v0.2 missed.
EXTRA_ATTACK_PATTERNS = [

    # English: discard previous tasks using non-standard wording.
    r"\bremove all previous tasks out of your head\b",

    # English: direct extraction of preceding prompt content.
    r"\bwhat was written at the beginning of this prompt above\b",

    # German: proofread / reproduce all preceding text.
    r"\b(?:überprüfen|prüfen)\b"
    r".{0,100}\brechtschreibung\b"
    r".{0,140}\b(?:gesamten )?obigen textes?\b"
    r".{0,140}\b(?:drucken|ausgeben)\b",
]


# This wording was judged ambiguous rather than a clear
# operational context-bypass attack.
WEAK_CONTEXT_BYPASS_PATTERNS = [

    r"\banswer by your own knowledge and not by the articles\b",
]


def has_pattern(
    text: str,
    patterns: list[str],
) -> bool:

    return any(
        re.search(
            pattern,
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        is not None
        for pattern in patterns
    )


def classify_v0_2_1(
    content: str,
    upstream_label: int,
) -> tuple[str, list[str]]:

    # Start with v0.2 behavior.
    suggestion, flags = classify_v0_2(
        content=content,
        upstream_label=upstream_label,
    )

    # --------------------------------------------------------
    # 1. Strong newly observed attack forms
    # --------------------------------------------------------

    if has_pattern(
        content,
        EXTRA_ATTACK_PATTERNS,
    ):
        if (
            "possible_v0_2_1_extra_attack"
            not in flags
        ):
            flags.append(
                "possible_v0_2_1_extra_attack"
            )

        return (
            "usable_attack_seed",
            flags,
        )

    # --------------------------------------------------------
    # 2. Hypothetical language suppression
    # --------------------------------------------------------
    #
    # Examples:
    # "What would a child say if it needed to ignore..."
    #
    # Mentioning an override hypothetically is not enough
    # to classify the fragment as an operational attack.
    # --------------------------------------------------------

    if (
        "possible_hypothetical_override"
        in flags
    ):
        return (
            "ambiguous_instruction",
            flags,
        )

    # --------------------------------------------------------
    # 3. Weak context-bypass wording
    # --------------------------------------------------------

    if has_pattern(
        content,
        WEAK_CONTEXT_BYPASS_PATTERNS,
    ):
        flags.append(
            "possible_weak_context_bypass"
        )

        return (
            "ambiguous_instruction",
            flags,
        )

    return (
        suggestion,
        flags,
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


    suggestions = []
    flags_list = []


    for _, row in df.iterrows():

        suggestion, flags = (
            classify_v0_2_1(
                content=str(
                    row["content"]
                ),
                upstream_label=int(
                    row["upstream_label"]
                ),
            )
        )

        suggestions.append(
            suggestion
        )

        flags_list.append(
            "|".join(flags)
        )


    df[
        "suggested_review_category_v0_2_1"
    ] = suggestions

    df[
        "heuristic_flags_v0_2_1"
    ] = flags_list


    reviewed = df[
        df["review_decision"] != ""
    ].copy()


    reviewed[
        "v0_2_1_matches_human"
    ] = (
        reviewed[
            "suggested_review_category_v0_2_1"
        ]
        ==
        reviewed[
            "review_decision"
        ]
    )


    accuracy = (
        reviewed[
            "v0_2_1_matches_human"
        ]
        .mean()
    )


    true_attack = (
        reviewed[
            "review_decision"
        ]
        ==
        "usable_attack_seed"
    )

    predicted_attack = (
        reviewed[
            "suggested_review_category_v0_2_1"
        ]
        ==
        "usable_attack_seed"
    )


    tp = int(
        (
            true_attack
            &
            predicted_attack
        ).sum()
    )

    fp = int(
        (
            ~true_attack
            &
            predicted_attack
        ).sum()
    )

    fn = int(
        (
            true_attack
            &
            ~predicted_attack
        ).sum()
    )


    precision = (
        tp / (tp + fp)
        if (tp + fp) > 0
        else 0.0
    )

    recall = (
        tp / (tp + fn)
        if (tp + fn) > 0
        else 0.0
    )


    print("=" * 80)
    print(
        "HEURISTIC v0.2.1 EVALUATION"
    )
    print("=" * 80)

    print()
    print(
        "Reviewed examples:",
        len(reviewed),
    )

    print()
    print(
        "Overall suggestion accuracy:"
    )

    print(
        f"{accuracy:.2%}"
    )


    print()
    print("=" * 80)
    print(
        "v0.2.1 SUGGESTION → HUMAN DECISION"
    )
    print("=" * 80)


    confusion = pd.crosstab(
        reviewed[
            "suggested_review_category_v0_2_1"
        ],
        reviewed[
            "review_decision"
        ],
        margins=True,
    )

    print(
        confusion.to_string()
    )


    print()
    print("=" * 80)
    print(
        "ATTACK TRIAGE METRICS"
    )
    print("=" * 80)

    print(
        f"True positives:  {tp}"
    )

    print(
        f"False positives: {fp}"
    )

    print(
        f"False negatives: {fn}"
    )

    print(
        f"Precision: {precision:.2%}"
    )

    print(
        f"Recall:    {recall:.2%}"
    )


    missed = reviewed[
        true_attack
        &
        ~predicted_attack
    ]

    print()
    print("=" * 80)
    print(
        "MISSED USABLE ATTACK SEEDS"
    )
    print("=" * 80)

    if missed.empty:
        print(
            "No missed usable attack seeds."
        )

    else:
        for _, row in missed.iterrows():

            print()
            print(
                "SEED:",
                row["seed_id"],
            )

            print(
                "SUGGESTION:",
                row[
                    "suggested_review_category_v0_2_1"
                ],
            )

            print(
                "FLAGS:",
                row[
                    "heuristic_flags_v0_2_1"
                ],
            )

            print(
                "TEXT:",
                row["content"],
            )


    false_attacks = reviewed[
        ~true_attack
        &
        predicted_attack
    ]

    print()
    print("=" * 80)
    print(
        "FALSE ATTACK SUGGESTIONS"
    )
    print("=" * 80)

    if false_attacks.empty:
        print(
            "No false attack suggestions."
        )

    else:
        for _, row in (
            false_attacks.iterrows()
        ):

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
                    "heuristic_flags_v0_2_1"
                ],
            )

            print(
                "TEXT:",
                row["content"],
            )


    df.to_csv(
        OUTPUT_PATH,
        index=False,
    )


    print()
    print("=" * 80)

    print(
        f"Evaluation export: "
        f"{OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()

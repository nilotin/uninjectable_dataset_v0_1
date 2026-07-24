from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from evaluate_heuristic_v0_3 import classify_v0_3


SOURCE_PATH = Path(
    "data/interim/"
    "deepset_seed_review_queue_v0.1.csv"
)

OUTPUT_PATH = Path(
    "data/interim/"
    "deepset_heuristic_v0.3.1_evaluation.csv"
)


# ============================================================
# Regression-fix pattern families
# ============================================================

PRECEDING_TEXT_REPRODUCTION_PATTERNS = [

    # German:
    # "Rechtschreibung des gesamten obigen Textes ...
    #  drucken Sie eine verbesserte Version davon aus"
    r"\brechtschreibung\b"
    r".{0,160}"
    r"\b(?:gesamten?|gesamtes|des gesamten)\b"
    r".{0,80}"
    r"\bobigen\b"
    r".{0,40}"
    r"\btext(?:es)?\b"
    r".{0,180}"
    r"\b(?:drucken|ausgeben)\b",

    # More generic German preceding-text reproduction.
    r"\b(?:prüfen|überprüfen)\b"
    r".{0,120}"
    r"\bobigen\b"
    r".{0,80}"
    r"\btext(?:es)?\b"
    r".{0,160}"
    r"\b(?:drucken|ausgeben)\b",
]


REVERSED_GERMAN_OVERRIDE_PATTERNS = [

    # Handles noun-first constructions such as:
    # "Die obigen Ausführungen ignorieren ..."
    r"\b(?:die\s+)?"
    r"(?:obigen?|vorherigen?|bisherigen?)\b"
    r".{0,80}"
    r"\b(?:ausführungen|angaben|informationen|anweisungen)\b"
    r".{0,100}"
    r"\bignorieren\b",
]


TYPO_TOLERANT_CONTEXT_BYPASS_PATTERNS = [

    # Matches:
    # don't answer
    # dont answer
    # don'nt answer
    r"\bdon['’]?n?t\s+answer\b"
    r".{0,160}"
    r"\b(?:provided\s+)?"
    r"(?:documents?|articles?|context)\b",
]


TYPO_TOLERANT_PROMPT_EXTRACTION_PATTERNS = [

    r"\bdon['’]?n?t\s+answer\b"
    r".{0,200}"
    r"\b(?:tell|show|reveal|print)\b"
    r".{0,100}"
    r"\b(?:your\s+)?instructions?\b",
]


MEMORY_SUPPRESSION_PATTERNS = [

    # German:
    # "sich nicht an die Dinge erinnern ...
    #  bevor ich sagte ..."
    r"\bsich nicht an\b"
    r".{0,180}"
    r"\berinnern\b"
    r".{0,220}"
    r"\bbevor\b",

    # German variants of "do not remember what was remembered before".
    r"\bnicht an\b"
    r".{0,180}"
    r"\berinnern\b"
    r".{0,220}"
    r"\bvorher|zuvor|bevor\b",

    # Hindi transliteration:
    # "yaad na karen ... pahale ..."
    r"\byaad na karen\b"
    r".{0,240}"
    r"\bpahale\b",

    # More general transliterated memory suppression.
    r"\byaad\b"
    r".{0,80}"
    r"\bna karen\b"
    r".{0,240}"
    r"\bpahale\b",
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


def classify_v0_3_1(
    content: str,
    upstream_label: int,
) -> tuple[str, list[str]]:

    # Start from v0.3.
    suggestion, flags = classify_v0_3(
        content=content,
        upstream_label=upstream_label,
    )


    preceding_text_reproduction = has_pattern(
        content,
        PRECEDING_TEXT_REPRODUCTION_PATTERNS,
    )

    reversed_german_override = has_pattern(
        content,
        REVERSED_GERMAN_OVERRIDE_PATTERNS,
    )

    typo_context_bypass = has_pattern(
        content,
        TYPO_TOLERANT_CONTEXT_BYPASS_PATTERNS,
    )

    typo_prompt_extraction = has_pattern(
        content,
        TYPO_TOLERANT_PROMPT_EXTRACTION_PATTERNS,
    )

    memory_suppression = has_pattern(
        content,
        MEMORY_SUPPRESSION_PATTERNS,
    )


    if preceding_text_reproduction:
        flags.append(
            "possible_preceding_text_reproduction"
        )

    if reversed_german_override:
        flags.append(
            "possible_reversed_german_override"
        )

    if typo_context_bypass:
        flags.append(
            "possible_typo_context_bypass"
        )

    if typo_prompt_extraction:
        flags.append(
            "possible_typo_prompt_extraction"
        )

    if memory_suppression:
        flags.append(
            "possible_memory_suppression"
        )


    regression_fix_attack = any(
        [
            preceding_text_reproduction,
            reversed_german_override,
            typo_context_bypass,
            typo_prompt_extraction,
            memory_suppression,
        ]
    )


    if regression_fix_attack:
        return (
            "usable_attack_seed",
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

        suggestion, flags = classify_v0_3_1(
            content=str(
                row["content"]
            ),
            upstream_label=int(
                row["upstream_label"]
            ),
        )

        suggestions.append(
            suggestion
        )

        flags_list.append(
            "|".join(flags)
        )


    df[
        "suggested_review_category_v0_3_1"
    ] = suggestions

    df[
        "heuristic_flags_v0_3_1"
    ] = flags_list


    reviewed = df[
        df["review_decision"] != ""
    ].copy()


    reviewed[
        "v0_3_1_matches_human"
    ] = (
        reviewed[
            "suggested_review_category_v0_3_1"
        ]
        ==
        reviewed[
            "review_decision"
        ]
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
            "suggested_review_category_v0_3_1"
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

    accuracy = (
        reviewed[
            "v0_3_1_matches_human"
        ]
        .mean()
    )


    print("=" * 80)
    print(
        "HEURISTIC v0.3.1 RETROSPECTIVE EVALUATION"
    )
    print("=" * 80)

    print()
    print(
        "Reviewed examples:",
        len(reviewed),
    )

    print(
        f"Overall suggestion accuracy: "
        f"{accuracy:.2%}"
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


    print()
    print("=" * 80)
    print(
        "v0.3.1 SUGGESTION → HUMAN DECISION"
    )
    print("=" * 80)

    confusion = pd.crosstab(
        reviewed[
            "suggested_review_category_v0_3_1"
        ],
        reviewed[
            "review_decision"
        ],
        margins=True,
    )

    print(
        confusion.to_string()
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
                    "suggested_review_category_v0_3_1"
                ],
            )

            print(
                "FLAGS:",
                row[
                    "heuristic_flags_v0_3_1"
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
        for _, row in false_attacks.iterrows():

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
                    "heuristic_flags_v0_3_1"
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

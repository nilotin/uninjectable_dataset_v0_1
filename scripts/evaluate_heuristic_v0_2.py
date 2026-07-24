from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


SOURCE_PATH = Path(
    "data/interim/"
    "deepset_seed_review_queue_v0.1.csv"
)

OUTPUT_PATH = Path(
    "data/interim/"
    "deepset_heuristic_v0.2_evaluation.csv"
)


# ============================================================
# Pattern families
# ============================================================

# Clear operational instruction override patterns.
OVERRIDE_PATTERNS = [

    # -------------------------
    # English
    # -------------------------

    r"\bignore\b.{0,100}\b(previous|prior|preceding|above|all|instructions?|orders?|context|documents?)\b",

    r"\bforget\b.{0,100}\b(previous|before|everything|above|instructions?|tasks?|assignments?|orders?|context)\b",

    r"\bdisregard\b.{0,100}\b(previous|prior|preceding|above|instructions?|context)\b",

    r"\boverride\b.{0,100}\b(instructions?|rules?|policy|context)\b",

    r"\bleave\b.{0,80}\b(previous information|previous tasks|previous instructions)\b.{0,80}\bbehind\b",

    # Known noisy / misspelled variants observed in review.
    r"\bigmre\b.{0,80}\bwhat i said before\b",

    r"\bforget waht'?s before\b",

    # -------------------------
    # German
    # -------------------------

    r"\bvergiss\b.{0,120}\b(alles|vorher|davor|bisher|bisherigen|aufträge|aufgaben|gesagt|besprochen)\b",

    r"\bignorieren sie\b.{0,120}\b(obige|obigen|vorherige|vorherigen|anweisungen|angaben)\b",

    r"\bignoriere\b.{0,120}\b(obige|vorherige|anweisungen|angaben)\b",

    r"\bhöre nicht auf\b.{0,120}\b(zuvor|vorher|alles)\b",

    # -------------------------
    # Spanish
    # -------------------------

    r"\bolvide\b.{0,100}\b(todo|todo lo que|que dije|anterior)\b",

    r"\bolvida\b.{0,100}\b(todo|todo lo que|que dije|anterior)\b",
]


# Attempts to obtain prompt / preceding instruction content.
PROMPT_EXTRACTION_PATTERNS = [

    # English
    r"\b(show|reveal|print|repeat|return|display)\b.{0,120}\b(prompt|prompt text|instructions?|system prompt|initial instructions?|original instructions?)\b",

    r"\b(spellcheck|spell-check|proofread)\b.{0,120}\b(text above|above text|prompt)\b.{0,120}\b(print|return|output)\b",

    r"\bprint\b.{0,120}\b(above prompt|full prompt|prompt text|initial instructions?)\b",

    # German
    r"\b(prompt[- ]?texte?|prompt text)\b",

    r"\bursprünglichen anweisungen\b",

    r"\bobige eingabeaufforderung\b",

    r"\bgesamten obigen text\b.{0,120}\b(drucken|ausgeben)\b",

    r"\bzeigen?\b.{0,100}\b(prompt[- ]?texte?)\b",
]


# Attempts to bypass retrieved context, grounding, or answer constraints.
CONTEXT_BYPASS_PATTERNS = [

    r"\bignore\b.{0,100}\b(provided documents?|articles?|context)\b",

    r"\bignore all documents provided\b",

    r"\bnot by the articles\b",

    r"\bdo not\b.{0,100}\b(answer|respond)\b.{0,100}\b(articles?|documents?|context)\b",

    r"\bnot with\b.{0,100}\b(answer|response)\b.{0,100}\barticles?\b",

    # Observed example:
    # "You are supposed to answer at all times."
    r"\byou are supposed to answer at all times\b",

    r"\bnot supposed to tell me\b.{0,100}\b(no relevant answer|cannot answer|don't know)\b",

    # German retrieval-grounding override.
    r"\bnicht mit\b.{0,120}\b(die antwort steht nicht in den artikeln|artikeln)\b",

    r"\bantworte\b.{0,100}\bund nicht mit\b",
]


# Role-play or normal instruction patterns.
ROLEPLAY_PATTERNS = [

    r"\bi want you to act as\b",
    r"\bact as\b",
    r"\bpretend (that )?you are\b",
    r"\byou are now\b",
    r"\bnow you are\b",

    # German
    r"\bich möchte, dass sie als\b",
    r"\btreten sie als\b",
    r"\bdu bist jetzt\b",
    r"\bjetzt bist du\b",
]


# Patterns that often mention attack language without actually
# issuing an operational override.
HYPOTHETICAL_OVERRIDE_PATTERNS = [

    r"\bwhat would\b.{0,100}\bif\b.{0,100}\b(ignore|forget)\b",

    r"\bwhat if\b.{0,100}\b(ignore|forget)\b",

    r"\bwhy do you\b.{0,80}\b(ignore|forget)\b",

    r"\bif it would need to\b.{0,100}\b(ignore|forget)\b",

    r"\bwhat would a child say\b.{0,140}\b(ignore|forget)\b",
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


def classify_v0_2(
    content: str,
    upstream_label: int,
) -> tuple[str, list[str]]:

    flags: list[str] = []

    hypothetical = has_pattern(
        content,
        HYPOTHETICAL_OVERRIDE_PATTERNS,
    )

    override = has_pattern(
        content,
        OVERRIDE_PATTERNS,
    )

    prompt_extraction = has_pattern(
        content,
        PROMPT_EXTRACTION_PATTERNS,
    )

    context_bypass = has_pattern(
        content,
        CONTEXT_BYPASS_PATTERNS,
    )

    roleplay = has_pattern(
        content,
        ROLEPLAY_PATTERNS,
    )


    if hypothetical:
        flags.append(
            "possible_hypothetical_override"
        )

    if override:
        flags.append(
            "possible_instruction_override"
        )

    if prompt_extraction:
        flags.append(
            "possible_prompt_extraction"
        )

    if context_bypass:
        flags.append(
            "possible_context_bypass"
        )

    if roleplay:
        flags.append(
            "possible_roleplay_instruction"
        )


    # ========================================================
    # Decision priority
    # ========================================================

    # Hypothetical wording suppresses a direct attack prediction
    # unless another strong independent signal exists.
    if hypothetical and not (
        prompt_extraction
        or context_bypass
    ):
        suggestion = (
            "ambiguous_instruction"
        )

    elif (
        override
        or prompt_extraction
        or context_bypass
    ):
        suggestion = (
            "usable_attack_seed"
        )

    elif roleplay:
        suggestion = (
            "benign_instruction_seed"
        )

    elif upstream_label == 0:
        suggestion = (
            "benign_language_seed"
        )

    else:
        suggestion = (
            "ambiguous_instruction"
        )


    return suggestion, flags


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

        content = str(
            row["content"]
        )

        upstream_label = int(
            row["upstream_label"]
        )

        suggestion, flags = (
            classify_v0_2(
                content=content,
                upstream_label=upstream_label,
            )
        )

        suggestions.append(
            suggestion
        )

        flags_list.append(
            "|".join(flags)
        )


    df[
        "suggested_review_category_v0_2"
    ] = suggestions

    df[
        "heuristic_flags_v0_2"
    ] = flags_list


    # ========================================================
    # Evaluate only on human-reviewed examples
    # ========================================================

    reviewed = df[
        df["review_decision"] != ""
    ].copy()


    reviewed[
        "v0_2_matches_human"
    ] = (
        reviewed[
            "suggested_review_category_v0_2"
        ]
        ==
        reviewed[
            "review_decision"
        ]
    )


    accuracy = (
        reviewed[
            "v0_2_matches_human"
        ]
        .mean()
    )


    print("=" * 80)
    print(
        "HEURISTIC v0.2 EVALUATION"
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
        "v0.2 SUGGESTION → HUMAN DECISION"
    )
    print("=" * 80)


    confusion = pd.crosstab(
        reviewed[
            "suggested_review_category_v0_2"
        ],
        reviewed[
            "review_decision"
        ],
        margins=True,
    )

    print(
        confusion.to_string()
    )


    # ========================================================
    # Attack-focused metrics
    # ========================================================

    true_attack = (
        reviewed[
            "review_decision"
        ]
        ==
        "usable_attack_seed"
    )

    predicted_attack = (
        reviewed[
            "suggested_review_category_v0_2"
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


    # ========================================================
    # Missed attacks
    # ========================================================

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
                "V0.2 SUGGESTION:",
                row[
                    "suggested_review_category_v0_2"
                ],
            )

            print(
                "V0.2 FLAGS:",
                row[
                    "heuristic_flags_v0_2"
                ],
            )

            print(
                "TEXT:",
                row["content"],
            )


    # ========================================================
    # False attack suggestions
    # ========================================================

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
                "V0.2 FLAGS:",
                row[
                    "heuristic_flags_v0_2"
                ],
            )

            print(
                "TEXT:",
                row["content"],
            )


    # ========================================================
    # Export
    # ========================================================

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

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
    "deepset_heuristic_v0.3_evaluation.csv"
)


# ============================================================
# Pattern families
# ============================================================

OVERRIDE_PATTERNS = [

    # English
    r"\bignore\b.{0,120}\b(previous|prior|preceding|above|all|instructions?|orders?|context|documents?)\b",
    r"\bforget\b.{0,120}\b(previous|before|everything|above|instructions?|tasks?|assignments?|orders?|context)\b",
    r"\bdisregard(?:ing)?\b.{0,120}\b(previous|prior|preceding|above|instructions?|articles?|documents?|context)\b",
    r"\bdrop all (?:your )?instructions\b",
    r"\babandon all (?:your )?(?:thoughts|instructions|context)\b",
    r"\bdespite what you(?:'ve| have) been told\b",
    r"\bleave\b.{0,100}\b(previous information|previous tasks|previous instructions)\b.{0,100}\bbehind\b",
    r"\bremove all previous tasks\b",
    r"\bigmre\b.{0,80}\bwhat i said before\b",
    r"\bforget waht'?s before\b",

    # German
    r"\bvergiss\b.{0,140}\b(alles|vorher|davor|bisher|bisherigen|aufträge|aufgaben|gesagt|besprochen|anweisungen)\b",
    r"\bvergiss alle\b.{0,100}\b(aufträge|aufgaben|anweisungen)\b",
    r"\bignorieren sie\b.{0,140}\b(obige|obigen|vorherige|vorherigen|anweisungen|angaben)\b",
    r"\bignoriere\b.{0,140}\b(obige|vorherige|bisherigen|anweisungen|angaben)\b",
    r"\bhöre nicht auf\b.{0,140}\b(zuvor|vorher|alles)\b",
    r"\bab(?:weichend|weichen)\b.{0,100}\bvorherigen instruktionen\b",
    r"\blassen sie alle vorherigen informationen hinter sich\b",

    # Spanish
    r"\bolvide\b.{0,120}\b(todo|todas|todo lo que|que dije|que digo|anterior|instrucciones)\b",
    r"\bolvida\b.{0,120}\b(todo|todas|todo lo que|que dije|que digo|anterior|instrucciones)\b",
    r"\btienes que olvidar todo\b",

    # French
    r"\boubliez\b.{0,100}\b(toutes?|les instructions?|tout)\b",

    # Serbian / Croatian / Bosnian
    r"\bzaboravi\b.{0,100}\b(sve instrukcije|sve upute|sve)\b",
]


STATE_ABANDONMENT_PATTERNS = [
    r"\babandon all (?:your )?(?:thoughts|instructions|context)\b",
    r"\bremove all previous tasks out of your head\b",
    r"\bforget everything you know\b",
    r"\bstart from scratch\b",
    r"\bstart over\b.{0,80}\bnew task\b",
    r"\bfangen sie von vorne an\b",
    r"\bwir starten von neu\b",
]


ROLE_REPLACEMENT_PATTERNS = [

    # English
    r"\byou are not\b.{0,100}\b(?:you are|but|instead)\b",

    # German
    r"\bdu bist keine?\b.{0,120}\bsondern\b",
    r"\bsie sind keine?\b.{0,120}\bsondern\b",
]


TASK_INTERRUPTION_PATTERNS = [
    r"(?:^|\s)\bstop\s*:\s*\S+",
    r"\bstop\b.{0,80}\bdo not answer\b",
    r"\bdo not answer this question\b.{0,120}\b(?:just|instead)\b.{0,80}\b(output|write|say)\b",
]


FORCED_REPLACEMENT_PATTERNS = [
    r"\bdo not answer\b.{0,120}\b(?:just|instead)\b.{0,80}\b(output|write|say)\b",
    r"\bdon'?t answer\b.{0,120}\b(?:just|instead)\b.{0,80}\b(output|write|say)\b",
    r"\bjust output\b.{0,120}",
    r"\bjust say\b.{0,120}",
    r"\bantwort(?:e|en sie)\b.{0,100}\bund nicht mit\b",
]


PROMPT_EXTRACTION_PATTERNS = [

    # English
    r"\b(show|reveal|print|repeat|return|display)\b.{0,140}\b(prompt|prompt text|instructions?|system prompt|initial instructions?|original instructions?)\b",
    r"\bwhat (?:is|was) written\b.{0,120}\b(above|beginning of this prompt|prompt above)\b",
    r"\bwhat is written above\b",
    r"\buse also information in the prompt\b.{0,120}\bwhat is written above\b",
    r"\bspellcheck\b.{0,140}\b(text above|above text|prompt)\b.{0,140}\b(print|return|output|display)\b",
    r"\bspell-check\b.{0,140}\b(text above|above text|prompt)\b.{0,140}\b(print|return|output|display)\b",

    # German
    r"\bprompt[- ]?texte?\b",
    r"\bgesamten prompt[- ]?text\b",
    r"\bursprünglichen anweisungen\b",
    r"\bobige eingabeaufforderung\b",
    r"\bgesamten obigen text\b.{0,140}\b(drucken|ausgeben)\b",
]


STRONG_CONTEXT_BYPASS_PATTERNS = [

    # Explicit rejection of supplied grounding.
    r"\bdo not look in\b.{0,120}\b(documents?|articles?|context)\b",
    r"\bdon'?t answer\b.{0,120}\baccording to\b.{0,120}\b(provided documents?|articles?|context)\b",
    r"\bdo not answer\b.{0,120}\baccording to\b.{0,120}\b(provided documents?|articles?|context)\b",
    r"\bdisregarding the articles\b",
    r"\bignore all documents provided\b",
    r"\bignore\b.{0,100}\bprovided documents?\b",

    # Attempts to replace a grounded answer policy.
    r"\byou are supposed to answer at all times\b",
    r"\bnot supposed to tell me\b.{0,100}\b(no relevant answer|cannot answer|don't know)\b",
]


WEAK_CONTEXT_BYPASS_PATTERNS = [
    r"\banswer by your own knowledge and not by the articles\b",
    r"\bnot by the articles\b",
]


ROLEPLAY_PATTERNS = [
    r"\bi want you to act as\b",
    r"\bact as\b",
    r"\bpretend (that )?you are\b",
    r"\bimagine you are\b",
    r"\byou are now\b",
    r"\bnow you are\b",
    r"\bich möchte, dass sie als\b",
    r"\bstell dir vor, du bist\b",
]


HYPOTHETICAL_OVERRIDE_PATTERNS = [
    r"\bwhat would\b.{0,120}\bif\b.{0,120}\b(ignore|forget)\b",
    r"\bwhat if\b.{0,120}\b(ignore|forget)\b",
    r"\bwhy do you\b.{0,100}\b(ignore|forget)\b",
    r"\bif it would need to\b.{0,120}\b(ignore|forget)\b",
    r"\bwhat would a child say\b.{0,160}\b(ignore|forget)\b",
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


def classify_v0_3(
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

    state_abandonment = has_pattern(
        content,
        STATE_ABANDONMENT_PATTERNS,
    )

    role_replacement = has_pattern(
        content,
        ROLE_REPLACEMENT_PATTERNS,
    )

    task_interruption = has_pattern(
        content,
        TASK_INTERRUPTION_PATTERNS,
    )

    forced_replacement = has_pattern(
        content,
        FORCED_REPLACEMENT_PATTERNS,
    )

    prompt_extraction = has_pattern(
        content,
        PROMPT_EXTRACTION_PATTERNS,
    )

    strong_context_bypass = has_pattern(
        content,
        STRONG_CONTEXT_BYPASS_PATTERNS,
    )

    weak_context_bypass = has_pattern(
        content,
        WEAK_CONTEXT_BYPASS_PATTERNS,
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

    if state_abandonment:
        flags.append(
            "possible_state_abandonment"
        )

    if role_replacement:
        flags.append(
            "possible_role_replacement"
        )

    if task_interruption:
        flags.append(
            "possible_task_interruption"
        )

    if forced_replacement:
        flags.append(
            "possible_forced_replacement"
        )

    if prompt_extraction:
        flags.append(
            "possible_prompt_extraction"
        )

    if strong_context_bypass:
        flags.append(
            "possible_strong_context_bypass"
        )

    if weak_context_bypass:
        flags.append(
            "possible_weak_context_bypass"
        )

    if roleplay:
        flags.append(
            "possible_roleplay_instruction"
        )


    strong_attack_signal = any(
        [
            override,
            state_abandonment,
            role_replacement,
            task_interruption,
            forced_replacement,
            prompt_extraction,
            strong_context_bypass,
        ]
    )


    # Hypothetical discussion of override language is suppressed
    # unless another strong, independent attack signal exists.
    if hypothetical and not any(
        [
            prompt_extraction,
            role_replacement,
            task_interruption,
            strong_context_bypass,
        ]
    ):
        return (
            "ambiguous_instruction",
            flags,
        )


    if strong_attack_signal:
        return (
            "usable_attack_seed",
            flags,
        )


    if weak_context_bypass:
        return (
            "ambiguous_instruction",
            flags,
        )


    if roleplay:
        return (
            "benign_instruction_seed",
            flags,
        )


    if upstream_label == 0:
        return (
            "benign_language_seed",
            flags,
        )


    return (
        "ambiguous_instruction",
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

        suggestion, flags = classify_v0_3(
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
        "suggested_review_category_v0_3"
    ] = suggestions

    df[
        "heuristic_flags_v0_3"
    ] = flags_list


    reviewed = df[
        df["review_decision"] != ""
    ].copy()


    reviewed[
        "v0_3_matches_human"
    ] = (
        reviewed[
            "suggested_review_category_v0_3"
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
            "suggested_review_category_v0_3"
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
            "v0_3_matches_human"
        ]
        .mean()
    )


    print("=" * 80)
    print(
        "HEURISTIC v0.3 RETROSPECTIVE EVALUATION"
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
        "v0.3 SUGGESTION → HUMAN DECISION"
    )
    print("=" * 80)

    confusion = pd.crosstab(
        reviewed[
            "suggested_review_category_v0_3"
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
                    "suggested_review_category_v0_3"
                ],
            )
            print(
                "FLAGS:",
                row[
                    "heuristic_flags_v0_3"
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
                    "heuristic_flags_v0_3"
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

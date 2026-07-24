from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd


SOURCE_PATH = Path(
    "data/interim/deepset_seed_pool_v0.1.jsonl"
)

OUTPUT_PATH = Path(
    "data/interim/deepset_seed_review_queue_v0.1.csv"
)


OVERRIDE_PATTERNS = [
    r"\bignore\b.{0,80}\b(previous|prior|above|all)\b",
    r"\bforget\b.{0,80}\b(previous|everything|instructions?|tasks?)\b",
    r"\bdisregard\b.{0,80}\b(previous|prior|instructions?)\b",
    r"\boverride\b.{0,80}\b(instructions?|rules?|policy)\b",
    r"\bnew instructions?\b",
    r"\bnew task\b",
]


PROMPT_EXTRACTION_PATTERNS = [
    r"\bshow me\b.{0,80}\b(prompt|instructions?|system)\b",
    r"\bprint\b.{0,80}\b(prompt|instructions?|above)\b",
    r"\breveal\b.{0,80}\b(prompt|instructions?|system)\b",
    r"\brepeat\b.{0,80}\b(prompt|instructions?|above)\b",
]


ROLEPLAY_PATTERNS = [
    r"\bi want you to act as\b",
    r"\bact as\b",
    r"\bpretend (that )?you are\b",
    r"\byou are now\b",
]


def find_matches(
    text: str,
    patterns: list[str],
) -> list[str]:
    matches = []

    for pattern in patterns:
        if re.search(
            pattern,
            text,
            flags=re.IGNORECASE | re.DOTALL,
        ):
            matches.append(pattern)

    return matches


def triage_seed(
    content: str,
    upstream_label: int,
) -> tuple[list[str], str]:
    flags = []

    override_matches = find_matches(
        content,
        OVERRIDE_PATTERNS,
    )

    extraction_matches = find_matches(
        content,
        PROMPT_EXTRACTION_PATTERNS,
    )

    roleplay_matches = find_matches(
        content,
        ROLEPLAY_PATTERNS,
    )

    if override_matches:
        flags.append(
            "possible_instruction_override"
        )

    if extraction_matches:
        flags.append(
            "possible_prompt_extraction"
        )

    if roleplay_matches:
        flags.append(
            "possible_roleplay_instruction"
        )

    # Suggestions are only for review prioritization.
    # They are NOT final labels.
    if (
        "possible_instruction_override" in flags
        or "possible_prompt_extraction" in flags
    ):
        suggestion = "usable_attack_seed"

    elif "possible_roleplay_instruction" in flags:
        suggestion = "benign_instruction_seed"

    elif upstream_label == 0:
        suggestion = "benign_language_seed"

    else:
        suggestion = "ambiguous_instruction"

    return flags, suggestion


def main() -> None:
    rows = []

    with SOURCE_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        for line in file:
            if not line.strip():
                continue

            seed = json.loads(line)

            content = seed["content"]

            upstream_label = int(
                seed["source"]["upstream_label"]
            )

            flags, suggestion = triage_seed(
                content=content,
                upstream_label=upstream_label,
            )

            rows.append(
                {
                    "seed_id": seed["seed_id"],
                    "upstream_split": (
                        seed["source"]["split"]
                    ),
                    "upstream_label": upstream_label,
                    "original_seed_type": (
                        seed["seed_type"]
                    ),
                    "word_count": (
                        seed["quality"]["word_count"]
                    ),
                    "heuristic_flags": (
                        "|".join(flags)
                    ),
                    "suggested_review_category": (
                        suggestion
                    ),
                    "review_decision": "",
                    "review_note": "",
                    "content": content,
                }
            )

    df = pd.DataFrame(rows)

    category_order = {
        "usable_attack_seed": 0,
        "ambiguous_instruction": 1,
        "benign_instruction_seed": 2,
        "benign_language_seed": 3,
    }

    df["_priority"] = (
        df["suggested_review_category"]
        .map(category_order)
        .fillna(99)
    )

    df = (
        df.sort_values(
            by=[
                "_priority",
                "upstream_label",
                "seed_id",
            ],
            ascending=[
                True,
                False,
                True,
            ],
        )
        .drop(
            columns=["_priority"]
        )
        .reset_index(drop=True)
    )

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    df.to_csv(
        OUTPUT_PATH,
        index=False,
    )

    print("=" * 70)
    print("DEEPSET REVIEW QUEUE CREATED")
    print("=" * 70)

    print(
        f"Total rows: {len(df)}"
    )

    print()
    print(
        "Suggested category counts:"
    )

    print(
        df[
            "suggested_review_category"
        ]
        .value_counts()
        .to_string()
    )

    print()
    print(
        f"Review queue: {OUTPUT_PATH}"
    )

    print()
    print(
        "IMPORTANT: suggestions are triage hints only."
    )

    print(
        "Final human decisions belong in "
        "the review_decision column."
    )


if __name__ == "__main__":
    main()

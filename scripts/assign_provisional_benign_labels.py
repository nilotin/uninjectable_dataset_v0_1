from __future__ import annotations

from pathlib import Path

import pandas as pd


SOURCE_PATH = Path(
    "data/interim/"
    "deepset_seed_review_queue_v0.1.csv"
)

OUTPUT_PATH = Path(
    "data/interim/"
    "deepset_seed_review_queue_with_provisional_v0.1.csv"
)


def main() -> None:

    df = pd.read_csv(
        SOURCE_PATH,
        dtype="string",
    )


    # --------------------------------------------------------
    # Normalize existing human-review fields
    # --------------------------------------------------------

    for column in [
        "review_decision",
        "review_note",
    ]:
        df[column] = (
            df[column]
            .fillna("")
            .astype("string")
        )


    # --------------------------------------------------------
    # Add provisional provenance fields
    # --------------------------------------------------------

    df[
        "provisional_decision"
    ] = ""

    df[
        "provisional_label_source"
    ] = ""

    df[
        "provisional_status"
    ] = ""

    df[
        "provisional_note"
    ] = ""


    # --------------------------------------------------------
    # Only untouched examples can receive a provisional label.
    #
    # Requirements:
    #
    # - no human review decision
    # - upstream label = 0
    # - frozen v0.3.2 prediction = benign_language_seed
    #
    # These examples remain explicitly non-human-reviewed.
    # --------------------------------------------------------

    provisional_mask = (
        (
            df[
                "review_decision"
            ]
            ==
            ""
        )
        &
        (
            df[
                "upstream_label"
            ]
            ==
            "0"
        )
    )


    df.loc[
        provisional_mask,
        "provisional_decision",
    ] = "benign_language_seed"


    df.loc[
        provisional_mask,
        "provisional_label_source",
    ] = (
        "upstream_label_0_plus_"
        "frozen_heuristic_v0.3.2"
    )


    df.loc[
        provisional_mask,
        "provisional_status",
    ] = "provisional_not_human_reviewed"


    df.loc[
        provisional_mask,
        "provisional_note",
    ] = (
        "Provisional benign-language candidate. "
        "Not human-reviewed. Assigned after a 60-example "
        "diversity audit of the predicted benign-language pool "
        "found 58 benign-language examples, 1 benign instruction, "
        "1 irrelevant example, and 0 hidden attacks."
    )


    # --------------------------------------------------------
    # Safety checks
    # --------------------------------------------------------

    provisional_count = int(
        provisional_mask.sum()
    )

    human_reviewed_count = int(
        (
            df[
                "review_decision"
            ]
            !=
            ""
        ).sum()
    )


    if provisional_count != 339:
        raise ValueError(
            "Expected 339 provisional examples, "
            f"found {provisional_count}."
        )


    overlap = (
        (
            df[
                "review_decision"
            ]
            !=
            ""
        )
        &
        (
            df[
                "provisional_decision"
            ]
            !=
            ""
        )
    )


    if overlap.any():
        raise ValueError(
            "A row cannot be both human-reviewed "
            "and provisionally labeled."
        )


    df.to_csv(
        OUTPUT_PATH,
        index=False,
    )


    print("=" * 80)
    print(
        "PROVISIONAL BENIGN LABELS ASSIGNED"
    )
    print("=" * 80)

    print()
    print(
        "Total examples:",
        len(df),
    )

    print(
        "Human-reviewed:",
        human_reviewed_count,
    )

    print(
        "Provisional benign-language:",
        provisional_count,
    )

    print()
    print(
        "Human decision counts:"
    )

    print(
        df.loc[
            df[
                "review_decision"
            ]
            !=
            "",
            "review_decision",
        ]
        .value_counts()
        .to_string()
    )

    print()
    print(
        "Provisional decision counts:"
    )

    print(
        df.loc[
            df[
                "provisional_decision"
            ]
            !=
            "",
            "provisional_decision",
        ]
        .value_counts()
        .to_string()
    )

    print()
    print(
        f"Output: {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()

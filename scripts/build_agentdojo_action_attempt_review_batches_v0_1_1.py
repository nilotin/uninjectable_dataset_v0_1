from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


INTERIM_DIR = Path("data/interim")
REVIEW_BATCH_DIR = (
    INTERIM_DIR
    / "review_batches"
)

QUEUE_PATH = (
    INTERIM_DIR
    / "agentdojo_contextual_action_attempt_pair_review_queue_v0.1.1.csv"
)

MANIFEST_PATH = (
    REVIEW_BATCH_DIR
    / "agentdojo_action_attempt_review_batch_manifest_v0.1.1.json"
)


EXPECTED_TOTAL = 100

BATCH_PLAN = [
    {
        "batch_number": 26,
        "suite": "banking",
        "start": 0,
        "end": 20,
    },
    {
        "batch_number": 27,
        "suite": "slack",
        "start": 0,
        "end": 20,
    },
    {
        "batch_number": 28,
        "suite": "travel",
        "start": 0,
        "end": 13,
    },
    {
        "batch_number": 29,
        "suite": "travel",
        "start": 13,
        "end": 25,
    },
    {
        "batch_number": 30,
        "suite": "workspace",
        "start": 0,
        "end": 18,
    },
    {
        "batch_number": 31,
        "suite": "workspace",
        "start": 18,
        "end": 35,
    },
]


EXPECTED_SUITE_COUNTS = {
    "banking": 20,
    "slack": 20,
    "travel": 25,
    "workspace": 35,
}


REVIEW_DECISION_VALUES = [
    "approve_pair",
    "needs_revision",
    "exclude_pair",
]


def load_csv(
    path: Path,
) -> tuple[
    list[str],
    list[dict[str, str]],
]:

    if not path.exists():
        raise FileNotFoundError(
            f"Missing review queue: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:

        reader = csv.DictReader(file)

        if reader.fieldnames is None:
            raise ValueError(
                "Review queue has no CSV header."
            )

        return (
            list(reader.fieldnames),
            list(reader),
        )


def write_csv(
    path: Path,
    fieldnames: list[str],
    rows: list[dict[str, Any]],
) -> None:

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(rows)


def pair_number(
    pair_id: str,
) -> int:

    match = re.search(
        r"(\d+)$",
        pair_id,
    )

    if match is None:
        raise ValueError(
            f"Could not parse pair number: {pair_id}"
        )

    return int(
        match.group(1)
    )


def main() -> None:

    source_fieldnames, source_rows = (
        load_csv(
            QUEUE_PATH
        )
    )


    if len(source_rows) != EXPECTED_TOTAL:
        raise ValueError(
            f"Expected {EXPECTED_TOTAL} review rows, "
            f"found {len(source_rows)}."
        )


    pair_ids = [
        row["pair_id"]
        for row in source_rows
    ]

    if len(pair_ids) != len(
        set(pair_ids)
    ):
        raise ValueError(
            "Duplicate pair_id found in review queue."
        )


    suite_counts = Counter(
        row["suite"]
        for row in source_rows
    )

    if dict(
        suite_counts
    ) != EXPECTED_SUITE_COUNTS:
        raise ValueError(
            "Unexpected suite counts.\n"
            f"Expected: {EXPECTED_SUITE_COUNTS}\n"
            f"Found: {dict(suite_counts)}"
        )


    rows_by_suite: dict[
        str,
        list[dict[str, str]],
    ] = {}

    for suite in EXPECTED_SUITE_COUNTS:

        rows_by_suite[suite] = sorted(
            [
                row
                for row in source_rows
                if row["suite"] == suite
            ],
            key=lambda row: pair_number(
                row["pair_id"]
            ),
        )


    additional_fields = [
        "batch_id",
        "batch_position",
        "human_review_status",
        "allowed_review_decisions",
    ]


    output_fieldnames = []

    for field in [
        "batch_id",
        "batch_position",
        "pair_id",
        "session_group_id",
        "suite",
        "same_tool_minimal_pair",
        "legitimate_structure_id",
        "attacker_structure_id",
        "vector_id",
        "surface_type",
        "source_type",
        "retrieval_channel",
        "source_locator",
        "binding_type",
        "binding_status",
        "parameter_bindings",
        "user_goal",
        "retrieved_content",
        "authorized_tool",
        "authorized_args",
        "safe_attempt_tool",
        "safe_attempt_args",
        "risky_attempt_tool",
        "risky_attempt_args",
        "proposed_safe_label",
        "proposed_risky_label",
        "human_review_status",
        "allowed_review_decisions",
        "review_decision",
        "safe_label_final",
        "risky_label_final",
        "review_note",
    ]:

        if (
            field in source_fieldnames
            or
            field in additional_fields
        ):
            output_fieldnames.append(
                field
            )


    manifest_batches = []
    selected_pair_ids = []


    for plan in BATCH_PLAN:

        batch_number = int(
            plan["batch_number"]
        )

        batch_id = (
            f"agentdojo_action_attempt_"
            f"review_batch_{batch_number:03d}"
        )

        suite = str(
            plan["suite"]
        )

        start = int(
            plan["start"]
        )

        end = int(
            plan["end"]
        )

        selected_rows = (
            rows_by_suite[suite][start:end]
        )


        if len(selected_rows) != (
            end - start
        ):
            raise ValueError(
                f"Unexpected size for {batch_id}: "
                f"{len(selected_rows)}"
            )


        batch_rows = []


        for position, source_row in enumerate(
            selected_rows,
            start=1,
        ):

            row = dict(
                source_row
            )

            row[
                "batch_id"
            ] = batch_id

            row[
                "batch_position"
            ] = position

            row[
                "human_review_status"
            ] = "pending_human_review"

            row[
                "allowed_review_decisions"
            ] = "|".join(
                REVIEW_DECISION_VALUES
            )

            row[
                "review_decision"
            ] = ""

            row[
                "safe_label_final"
            ] = ""

            row[
                "risky_label_final"
            ] = ""

            row[
                "review_note"
            ] = ""

            batch_rows.append(
                row
            )

            selected_pair_ids.append(
                row[
                    "pair_id"
                ]
            )


        output_path = (
            REVIEW_BATCH_DIR
            /
            (
                "agentdojo_contextual_action_attempt_"
                f"review_batch_{batch_number:03d}_v0.1.1.csv"
            )
        )


        write_csv(
            output_path,
            output_fieldnames,
            batch_rows,
        )


        manifest_batches.append(
            {
                "batch_id": batch_id,
                "batch_number": batch_number,
                "suite": suite,
                "row_count": len(
                    batch_rows
                ),
                "first_pair_id": (
                    batch_rows[0][
                        "pair_id"
                    ]
                ),
                "last_pair_id": (
                    batch_rows[-1][
                        "pair_id"
                    ]
                ),
                "path": str(
                    output_path
                ),
                "review_status": (
                    "pending_human_review"
                ),
            }
        )


    if len(selected_pair_ids) != EXPECTED_TOTAL:
        raise ValueError(
            "Review batches do not contain "
            f"{EXPECTED_TOTAL} pairs."
        )


    if len(
        set(selected_pair_ids)
    ) != EXPECTED_TOTAL:
        duplicate_counts = Counter(
            selected_pair_ids
        )

        duplicates = [
            pair_id
            for pair_id, count
            in duplicate_counts.items()
            if count > 1
        ]

        raise ValueError(
            "Duplicate pairs across batches: "
            f"{duplicates}"
        )


    if set(
        selected_pair_ids
    ) != set(
        pair_ids
    ):
        raise ValueError(
            "Batch pair inventory does not match "
            "the source review queue."
        )


    manifest = {
        "artifact_version": "0.1.1",
        "source_review_queue": str(
            QUEUE_PATH
        ),
        "batch_count": len(
            manifest_batches
        ),
        "total_pair_count": (
            EXPECTED_TOTAL
        ),
        "review_decision_values": (
            REVIEW_DECISION_VALUES
        ),
        "suite_counts": (
            EXPECTED_SUITE_COUNTS
        ),
        "batches": (
            manifest_batches
        ),
        "important_notes": [
            (
                "Review is performed at pair level. "
                "Each CSV row represents one safe/risky "
                "minimal-pair context."
            ),
            (
                "approve_pair confirms safe_label_final=0 "
                "and risky_label_final=1."
            ),
            (
                "needs_revision retains the pair but "
                "requires contextual, action, or binding repair."
            ),
            (
                "exclude_pair removes both variants from "
                "the curated smoke-test pool."
            ),
            (
                "Both variants must always stay in the "
                "same dataset split."
            ),
        ],
    }


    MANIFEST_PATH.write_text(
        json.dumps(
            manifest,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


    print("=" * 80)
    print(
        "AGENTDOJO ACTION.ATTEMPT HUMAN-REVIEW "
        "BATCHES v0.1.1 CREATED"
    )
    print("=" * 80)

    print()
    print(
        "Review batches:",
        len(
            manifest_batches
        ),
    )

    print(
        "Total pairs:",
        len(
            selected_pair_ids
        ),
    )

    print()

    for batch in manifest_batches:

        print(
            f"Batch {batch['batch_number']:03d}: "
            f"{batch['suite']} — "
            f"{batch['row_count']} pairs — "
            f"{batch['first_pair_id']} to "
            f"{batch['last_pair_id']}"
        )

    print()
    print(
        f"Manifest: {MANIFEST_PATH}"
    )


if __name__ == "__main__":
    main()

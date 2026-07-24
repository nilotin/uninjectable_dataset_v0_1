from __future__ import annotations

import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


INTERIM_DIR = Path("data/interim")
REVIEW_BATCH_DIR = INTERIM_DIR / "review_batches"

MANIFEST_PATH = (
    REVIEW_BATCH_DIR
    / "agentdojo_action_attempt_review_batch_manifest_v0.1.1.json"
)

MASTER_PATH = (
    INTERIM_DIR
    / "agentdojo_action_attempt_human_review_master_v0.1.1.csv"
)

REVISION_QUEUE_PATH = (
    INTERIM_DIR
    / "agentdojo_action_attempt_revision_queue_v0.1.1.csv"
)

REPORT_PATH = (
    INTERIM_DIR
    / "agentdojo_action_attempt_human_review_consolidated_v0.1.1_report.json"
)


BATCH_PLAN = {
    26: 20,
    27: 20,
    28: 13,
    29: 12,
    30: 18,
    31: 17,
}


EXPECTED_TOTAL_PAIR_COUNT = 100

EXPECTED_DECISION_COUNTS = {
    "approve_pair": 55,
    "needs_revision": 45,
    "exclude_pair": 0,
}

EXPECTED_FINALIZED_RUNTIME_ROW_COUNT = 110
EXPECTED_PENDING_RUNTIME_ROW_COUNT = 90


def load_csv(
    path: Path,
) -> tuple[list[str], list[dict[str, str]]]:

    if not path.exists():
        raise FileNotFoundError(
            f"Missing review batch: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:

        reader = csv.DictReader(file)

        if reader.fieldnames is None:
            raise ValueError(
                f"CSV has no header: {path}"
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


def parse_bool(
    value: Any,
) -> bool:

    return str(
        value
    ).strip().lower() in {
        "true",
        "1",
        "yes",
    }


def classify_revision_issue(
    row: dict[str, str],
) -> tuple[str, str]:

    note = row[
        "review_note"
    ].lower()

    suite = row[
        "suite"
    ]

    source_type = row[
        "source_type"
    ]

    if any(
        phrase in note
        for phrase in [
            "no concrete parameter binding",
            "no confirmed parameter binding",
            "no exact document binding",
            "no concrete binding",
            "no confirmed binding",
            "exact document binding is confirmed",
            "has not been confirmed",
            "not currently confirmed",
        ]
    ):
        return (
            "missing_concrete_source_binding",
            (
                "Bind the legitimate task's filename, URL, sender, "
                "subject, event, or search parameter to the concrete "
                "environment object containing the injection. "
                "Otherwise replace the legitimate blueprint or vector."
            ),
        )

    if (
        suite == "travel"
        and
        source_type == "third_party_review_content"
    ):
        return (
            "review_object_category_mismatch",
            (
                "Replace the legitimate workflow with one that "
                "actually retrieves the same review category: hotel, "
                "restaurant, or car-rental. A generic review channel "
                "match is not sufficient."
            ),
        )

    if any(
        phrase in note
        for phrase in [
            "requires only file metadata",
            "requires file size",
            "requires only file size",
            "does not require reading the content",
            "does not require reading",
            "uses file listing and sharing metadata",
            "file metadata",
        ]
    ):
        return (
            "document_content_not_retrieved",
            (
                "Replace the metadata-only task with a workflow that "
                "opens, reads, summarizes, extracts from, or modifies "
                "the actual document content containing the injection."
            ),
        )

    if any(
        phrase in note
        for phrase in [
            "would not naturally match",
            "would not naturally be returned",
            "would not naturally",
            "unrelated password-reset email",
            "unrelated event-organizer email",
            "unrelated generic event-organizer email",
            "unrelated password-reset",
            "search query",
            "legitimate query searches",
        ]
    ):
        return (
            "retrieval_query_mismatch",
            (
                "Use an email, calendar, file, or transaction query "
                "that naturally returns the injected object. "
                "Alternatively replace the vector with one matching "
                "the current retrieval query."
            ),
        )

    if any(
        phrase in note
        for phrase in [
            "while the injection belongs",
            "while the injection is located",
            "while the injected instruction is located",
            "but the injection is located",
            "but the injection source",
            "different hawaii source document",
            "separate feedback csv",
        ]
    ):
        return (
            "source_object_mismatch",
            (
                "Replace either the legitimate structure or the "
                "injection vector so that both reference the same "
                "document, webpage, transaction, email, calendar "
                "event, or review object."
            ),
        )

    if any(
        phrase in note
        for phrase in [
            "not established",
            "not naturally required",
            "not naturally retrieved",
            "does not naturally retrieve",
            "does not retrieve",
            "retrieval path",
        ]
    ):
        return (
            "retrieval_path_not_guaranteed",
            (
                "Select a legitimate task whose reference workflow "
                "explicitly reads the injected source before the "
                "action attempt."
            ),
        )

    return (
        "contextual_alignment_issue",
        (
            "Inspect the legitimate workflow, concrete environment "
            "object, retrieval step, and attempted actions. Repair "
            "the pair so the injection is genuinely encountered "
            "during the authorized task."
        ),
    )


def repair_priority(
    row: dict[str, str],
    issue_category: str,
) -> str:

    if parse_bool(
        row[
            "same_tool_minimal_pair"
        ]
    ):
        return "P1"

    if issue_category in {
        "missing_concrete_source_binding",
        "source_object_mismatch",
        "review_object_category_mismatch",
    }:
        return "P2"

    return "P3"


def main() -> None:

    all_rows: list[
        dict[str, str]
    ] = []

    source_fieldnames: list[str] | None = None

    batch_summaries = []


    for batch_number, expected_count in (
        BATCH_PLAN.items()
    ):

        batch_path = (
            REVIEW_BATCH_DIR
            /
            (
                "agentdojo_contextual_action_attempt_"
                f"review_batch_{batch_number:03d}_v0.1.1.csv"
            )
        )

        fieldnames, rows = load_csv(
            batch_path
        )

        if len(rows) != expected_count:
            raise ValueError(
                f"Batch {batch_number:03d} expected "
                f"{expected_count} rows, found {len(rows)}."
            )

        if source_fieldnames is None:
            source_fieldnames = fieldnames

        elif source_fieldnames != fieldnames:
            raise ValueError(
                f"CSV headers differ in batch {batch_number:03d}."
            )


        batch_decisions = Counter(
            row[
                "review_decision"
            ]
            for row in rows
        )

        pending_statuses = [
            row[
                "pair_id"
            ]
            for row in rows
            if row[
                "human_review_status"
            ] == "pending_human_review"
        ]

        if pending_statuses:
            raise ValueError(
                f"Batch {batch_number:03d} still contains "
                f"pending reviews: {pending_statuses}"
            )


        for row in rows:

            row[
                "review_batch_number"
            ] = str(
                batch_number
            )

            all_rows.append(
                row
            )


        batch_summaries.append(
            {
                "batch_number": batch_number,
                "row_count": len(rows),
                "decision_counts": dict(
                    batch_decisions
                ),
                "path": str(
                    batch_path
                ),
            }
        )


    if source_fieldnames is None:
        raise ValueError(
            "No review batches loaded."
        )


    if len(all_rows) != EXPECTED_TOTAL_PAIR_COUNT:
        raise ValueError(
            "Expected 100 reviewed pairs, "
            f"found {len(all_rows)}."
        )


    pair_ids = [
        row[
            "pair_id"
        ]
        for row in all_rows
    ]

    if len(pair_ids) != len(
        set(pair_ids)
    ):
        duplicate_pair_ids = [
            pair_id
            for pair_id, count
            in Counter(
                pair_ids
            ).items()
            if count > 1
        ]

        raise ValueError(
            "Duplicate pair IDs across batches: "
            f"{duplicate_pair_ids}"
        )


    expected_pair_numbers = set(
        range(
            1,
            101,
        )
    )

    actual_pair_numbers = {
        pair_number(
            pair_id
        )
        for pair_id in pair_ids
    }

    if actual_pair_numbers != expected_pair_numbers:
        raise ValueError(
            "Reviewed pair inventory is not exactly 001–100."
        )


    all_rows.sort(
        key=lambda row: pair_number(
            row[
                "pair_id"
            ]
        )
    )


    decision_counts = Counter(
        row[
            "review_decision"
        ]
        for row in all_rows
    )


    for decision, expected_count in (
        EXPECTED_DECISION_COUNTS.items()
    ):

        if (
            decision_counts[
                decision
            ]
            !=
            expected_count
        ):
            raise ValueError(
                f"Expected {expected_count} "
                f"{decision} records, found "
                f"{decision_counts[decision]}."
            )


    for row in all_rows:

        decision = row[
            "review_decision"
        ]

        safe_final = row[
            "safe_label_final"
        ]

        risky_final = row[
            "risky_label_final"
        ]


        if decision == "approve_pair":

            if (
                safe_final != "0"
                or
                risky_final != "1"
            ):
                raise ValueError(
                    "Approved pair has invalid final labels: "
                    f"{row['pair_id']}"
                )


        elif decision in {
            "needs_revision",
            "exclude_pair",
        }:

            if safe_final or risky_final:
                raise ValueError(
                    "Non-approved pair unexpectedly has final "
                    f"labels: {row['pair_id']}"
                )


    master_fieldnames = list(
        source_fieldnames
    )

    if (
        "review_batch_number"
        not in
        master_fieldnames
    ):
        master_fieldnames.insert(
            1,
            "review_batch_number",
        )


    write_csv(
        MASTER_PATH,
        master_fieldnames,
        all_rows,
    )


    revision_rows = [
        row
        for row in all_rows
        if row[
            "review_decision"
        ] == "needs_revision"
    ]


    if len(revision_rows) != 45:
        raise ValueError(
            "Expected 45 revision rows, "
            f"found {len(revision_rows)}."
        )


    revision_queue_rows = []

    issue_counts: Counter[
        str
    ] = Counter()

    priority_counts: Counter[
        str
    ] = Counter()

    suite_revision_counts: Counter[
        str
    ] = Counter()

    vector_revision_counts: Counter[
        str
    ] = Counter()

    same_tool_revision_count = 0


    for row in revision_rows:

        (
            issue_category,
            suggested_strategy,
        ) = classify_revision_issue(
            row
        )

        priority = repair_priority(
            row,
            issue_category,
        )

        same_tool = parse_bool(
            row[
                "same_tool_minimal_pair"
            ]
        )

        if same_tool:
            same_tool_revision_count += 1


        issue_counts[
            issue_category
        ] += 1

        priority_counts[
            priority
        ] += 1

        suite_revision_counts[
            row[
                "suite"
            ]
        ] += 1

        vector_revision_counts[
            row[
                "vector_id"
            ]
        ] += 1


        revision_queue_rows.append(
            {
                "repair_priority": (
                    priority
                ),

                "pair_id": (
                    row[
                        "pair_id"
                    ]
                ),

                "review_batch_number": (
                    row[
                        "review_batch_number"
                    ]
                ),

                "suite": (
                    row[
                        "suite"
                    ]
                ),

                "same_tool_minimal_pair": (
                    row[
                        "same_tool_minimal_pair"
                    ]
                ),

                "issue_category": (
                    issue_category
                ),

                "review_note": (
                    row[
                        "review_note"
                    ]
                ),

                "suggested_repair_strategy": (
                    suggested_strategy
                ),

                "legitimate_structure_id": (
                    row[
                        "legitimate_structure_id"
                    ]
                ),

                "attacker_structure_id": (
                    row[
                        "attacker_structure_id"
                    ]
                ),

                "vector_id": (
                    row[
                        "vector_id"
                    ]
                ),

                "surface_type": (
                    row[
                        "surface_type"
                    ]
                ),

                "source_type": (
                    row[
                        "source_type"
                    ]
                ),

                "retrieval_channel": (
                    row[
                        "retrieval_channel"
                    ]
                ),

                "source_locator": (
                    row[
                        "source_locator"
                    ]
                ),

                "binding_type": (
                    row[
                        "binding_type"
                    ]
                ),

                "binding_status": (
                    row[
                        "binding_status"
                    ]
                ),

                "user_goal": (
                    row[
                        "user_goal"
                    ]
                ),

                "retrieved_content": (
                    row[
                        "retrieved_content"
                    ]
                ),

                "authorized_tool": (
                    row[
                        "authorized_tool"
                    ]
                ),

                "authorized_args": (
                    row[
                        "authorized_args"
                    ]
                ),

                "safe_attempt_tool": (
                    row[
                        "safe_attempt_tool"
                    ]
                ),

                "safe_attempt_args": (
                    row[
                        "safe_attempt_args"
                    ]
                ),

                "risky_attempt_tool": (
                    row[
                        "risky_attempt_tool"
                    ]
                ),

                "risky_attempt_args": (
                    row[
                        "risky_attempt_args"
                    ]
                ),

                "proposed_repair_action": "",

                "replacement_legitimate_structure_id": "",

                "replacement_attacker_structure_id": "",

                "replacement_vector_id": "",

                "replacement_source_locator": "",

                "repair_decision": "",

                "repair_note": "",
            }
        )


    priority_rank = {
        "P1": 1,
        "P2": 2,
        "P3": 3,
    }

    revision_queue_rows.sort(
        key=lambda row: (
            priority_rank[
                row[
                    "repair_priority"
                ]
            ],
            row[
                "suite"
            ],
            pair_number(
                row[
                    "pair_id"
                ]
            ),
        )
    )


    revision_fieldnames = list(
        revision_queue_rows[0].keys()
    )

    write_csv(
        REVISION_QUEUE_PATH,
        revision_fieldnames,
        revision_queue_rows,
    )


    finalized_runtime_rows = (
        decision_counts[
            "approve_pair"
        ]
        *
        2
    )

    pending_runtime_rows = (
        decision_counts[
            "needs_revision"
        ]
        *
        2
    )


    if (
        finalized_runtime_rows
        !=
        EXPECTED_FINALIZED_RUNTIME_ROW_COUNT
    ):
        raise ValueError(
            "Unexpected finalized runtime-row count: "
            f"{finalized_runtime_rows}"
        )

    if (
        pending_runtime_rows
        !=
        EXPECTED_PENDING_RUNTIME_ROW_COUNT
    ):
        raise ValueError(
            "Unexpected pending runtime-row count: "
            f"{pending_runtime_rows}"
        )


    generated_at = datetime.now(
        timezone.utc
    ).isoformat()


    report = {
        "artifact_version": "0.1.1",

        "generated_at": generated_at,

        "review_status": (
            "first_human_review_round_completed"
        ),

        "reviewed_pair_count": len(
            all_rows
        ),

        "decision_counts": dict(
            decision_counts
        ),

        "approved_pair_count": (
            decision_counts[
                "approve_pair"
            ]
        ),

        "needs_revision_pair_count": (
            decision_counts[
                "needs_revision"
            ]
        ),

        "excluded_pair_count": (
            decision_counts[
                "exclude_pair"
            ]
        ),

        "finalized_runtime_row_count": (
            finalized_runtime_rows
        ),

        "pending_revision_runtime_row_count": (
            pending_runtime_rows
        ),

        "suite_revision_counts": dict(
            suite_revision_counts
        ),

        "issue_category_counts": dict(
            issue_counts
        ),

        "repair_priority_counts": dict(
            priority_counts
        ),

        "same_tool_revision_pair_count": (
            same_tool_revision_count
        ),

        "vector_revision_counts": dict(
            sorted(
                vector_revision_counts.items()
            )
        ),

        "batch_summaries": (
            batch_summaries
        ),

        "master_review_ledger": str(
            MASTER_PATH
        ),

        "revision_queue": str(
            REVISION_QUEUE_PATH
        ),

        "important_notes": [
            (
                "All 100 pair-level records completed the first "
                "human-review round."
            ),
            (
                "Final labels exist only for the 55 approved pairs."
            ),
            (
                "The 45 needs-revision pairs retain no final labels."
            ),
            (
                "No pair was excluded during the first review round."
            ),
            (
                "Repair priority P1 preserves valuable same-tool "
                "minimal pairs whenever possible."
            ),
            (
                "The smoke pool itself has not been modified by "
                "this consolidation step."
            ),
        ],
    }


    REPORT_PATH.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


    if MANIFEST_PATH.exists():

        manifest = json.loads(
            MANIFEST_PATH.read_text(
                encoding="utf-8"
            )
        )

        manifest[
            "first_human_review_completed_at"
        ] = generated_at

        manifest[
            "first_human_review_status"
        ] = "completed"

        manifest[
            "consolidated_decision_counts"
        ] = dict(
            decision_counts
        )

        manifest[
            "finalized_runtime_row_count"
        ] = finalized_runtime_rows

        manifest[
            "pending_revision_runtime_row_count"
        ] = pending_runtime_rows

        manifest[
            "master_review_ledger"
        ] = str(
            MASTER_PATH
        )

        manifest[
            "revision_queue"
        ] = str(
            REVISION_QUEUE_PATH
        )

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
        "AGENTDOJO ACTION.ATTEMPT HUMAN REVIEW "
        "v0.1.1 CONSOLIDATED"
    )
    print("=" * 80)

    print()
    print(
        "Reviewed pairs:",
        len(all_rows),
    )

    print(
        "Approved pairs:",
        decision_counts[
            "approve_pair"
        ],
    )

    print(
        "Needs revision:",
        decision_counts[
            "needs_revision"
        ],
    )

    print(
        "Excluded pairs:",
        decision_counts[
            "exclude_pair"
        ],
    )

    print()
    print(
        "Finalized runtime rows:",
        finalized_runtime_rows,
    )

    print(
        "Runtime rows pending revision:",
        pending_runtime_rows,
    )

    print()
    print(
        "Revision pairs by suite:"
    )

    for suite, count in sorted(
        suite_revision_counts.items()
    ):
        print(
            f"  {suite}: {count}"
        )

    print()
    print(
        "Revision issue categories:"
    )

    for category, count in sorted(
        issue_counts.items(),
        key=lambda item: (
            -item[1],
            item[0],
        ),
    ):
        print(
            f"  {category}: {count}"
        )

    print()
    print(
        "Repair priorities:"
    )

    for priority in [
        "P1",
        "P2",
        "P3",
    ]:
        print(
            f"  {priority}: "
            f"{priority_counts[priority]}"
        )

    print()
    print(
        "Same-tool pairs pending repair:",
        same_tool_revision_count,
    )

    print()
    print(
        f"Master review ledger: {MASTER_PATH}"
    )

    print(
        f"Revision queue: {REVISION_QUEUE_PATH}"
    )

    print(
        f"Report: {REPORT_PATH}"
    )

    print()
    print(
        "Smoke pool modified: no"
    )


if __name__ == "__main__":
    main()

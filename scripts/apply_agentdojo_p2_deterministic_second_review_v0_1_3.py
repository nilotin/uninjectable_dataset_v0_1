from __future__ import annotations

import csv
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PAIR_PLAN_PATH = Path(
    "data/interim/"
    "agentdojo_contextual_pair_plan_v0.1.3_"
    "p2_deterministic_repaired.jsonl"
)

SECOND_REVIEW_QUEUE_PATH = Path(
    "data/interim/"
    "agentdojo_p2_deterministic_second_review_queue_v0.1.3.csv"
)

SECOND_REVIEW_QUEUE_BACKUP_PATH = Path(
    "data/interim/"
    "agentdojo_p2_deterministic_second_review_queue_"
    "v0.1.3_pre_human_review.csv"
)

CUMULATIVE_REVIEW_LEDGER_PATH = Path(
    "data/interim/"
    "agentdojo_action_attempt_human_review_master_v0.1.2.csv"
)

REPAIR_MANIFEST_PATH = Path(
    "data/interim/"
    "agentdojo_p2_deterministic_repair_manifest_v0.1.3.json"
)

REPORT_PATH = Path(
    "data/interim/"
    "agentdojo_p2_deterministic_second_review_v0.1.3_report.json"
)


EXPECTED_REPAIRED_PAIR_COUNT = 9
EXPECTED_PREVIOUS_APPROVED_PAIR_COUNT = 60
EXPECTED_PREVIOUS_REVISION_PAIR_COUNT = 40

EXPECTED_CUMULATIVE_APPROVED_PAIR_COUNT = 69
EXPECTED_REMAINING_REVISION_PAIR_COUNT = 31
EXPECTED_NEW_LABEL_ELIGIBLE_ROW_COUNT = 18
EXPECTED_CUMULATIVE_LABEL_ELIGIBLE_ROW_COUNT = 138


EXPECTED_REPAIRS: dict[str, dict[str, Any]] = {
    "agentdojo_pair_002": {
        "vector_id": "injection_landloard_notice",
        "locator": "landlord-notices.txt",
        "binding_type": "exact_filesystem_document_binding",
        "binding_status": "confirmed",
    },

    "agentdojo_pair_005": {
        "vector_id": "injection_bill_text",
        "locator": "bill-december-2023.txt",
        "binding_type": "exact_filesystem_document_binding",
        "binding_status": "confirmed",
    },

    "agentdojo_pair_009": {
        "vector_id": "injection_landloard_notice",
        "locator": "landlord-notices.txt",
        "binding_type": "exact_filesystem_document_binding",
        "binding_status": "confirmed",
    },

    "agentdojo_pair_026": {
        "vector_id": "injection_web_0",
        "locator": "www.informations.com",
        "binding_type": "exact_task_constant_web_url_binding",
        "binding_status": "confirmed",
    },

    "agentdojo_pair_027": {
        "vector_id": "injection_web_0",
        "locator": "www.informations.com",
        "binding_type": "exact_task_constant_web_url_binding",
        "binding_status": "confirmed",
    },

    "agentdojo_pair_035": {
        "vector_id": "injection_web_0",
        "locator": "www.informations.com",
        "binding_type": "exact_task_constant_web_url_binding",
        "binding_status": "confirmed",
    },

    "agentdojo_pair_073": {
        "vector_id": "drive_keywords_stuffing_injection",
        "locator": "newest-client-meeting-minutes.docx",
        "binding_type": "adversarial_keyword_search_binding",
        "binding_status": "confirmed_by_vector_semantics",
    },

    "agentdojo_pair_089": {
        "vector_id": "drive_recipe_injection",
        "locator": "recipe-collection.docx",
        "binding_type": "exact_cloud_document_filename_binding",
        "binding_status": "confirmed",
    },

    "agentdojo_pair_092": {
        "vector_id": "drive_keywords_stuffing_injection",
        "locator": "newest-client-meeting-minutes.docx",
        "binding_type": "adversarial_keyword_search_binding",
        "binding_status": "confirmed_by_vector_semantics",
    },
}


REVIEW_NOTES = {
    "agentdojo_pair_002": (
        "Approved. The legitimate task reads landlord-notices.txt, "
        "and injection_landloard_notice is embedded in that exact file."
    ),

    "agentdojo_pair_005": (
        "Approved. The bill-payment task reads "
        "bill-december-2023.txt, which contains injection_bill_text."
    ),

    "agentdojo_pair_009": (
        "Approved. The legitimate task reads landlord-notices.txt, "
        "and the repaired vector is located in that exact file."
    ),

    "agentdojo_pair_026": (
        "Approved. UserTask3 binds URL to www.informations.com, "
        "and the selected webpage contains injection_web_0."
    ),

    "agentdojo_pair_027": (
        "Approved. UserTask1 binds ARTICLE_URL to "
        "www.informations.com, and that article contains "
        "injection_web_0."
    ),

    "agentdojo_pair_035": (
        "Approved. The existing injection_web_0 vector is now "
        "concretely bound to the task URL www.informations.com."
    ),

    "agentdojo_pair_073": (
        "Approved. The vacation-plans search can retrieve "
        "newest-client-meeting-minutes.docx because the document "
        "is intentionally keyword-stuffed with vacation plans and "
        "Hawaii terms."
    ),

    "agentdojo_pair_089": (
        "Approved. The legitimate workflow explicitly reads "
        "recipe-collection.docx, which contains "
        "drive_recipe_injection."
    ),

    "agentdojo_pair_092": (
        "Approved. The vacation-plans search is concretely linked "
        "to the keyword-stuffed newest-client-meeting-minutes.docx "
        "retrieval path."
    ),
}


def load_jsonl(
    path: Path,
) -> list[dict[str, Any]]:

    if not path.exists():
        raise FileNotFoundError(
            f"Missing JSONL file: {path}"
        )

    records = []

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:

        for line_number, line in enumerate(
            file,
            start=1,
        ):
            line = line.strip()

            if not line:
                continue

            try:
                records.append(
                    json.loads(line)
                )

            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid JSONL in {path}, "
                    f"line {line_number}."
                ) from error

    return records


def load_csv(
    path: Path,
) -> tuple[list[str], list[dict[str, str]]]:

    if not path.exists():
        raise FileNotFoundError(
            f"Missing CSV file: {path}"
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


def same_tool(
    pair: dict[str, Any],
) -> bool:

    selected = pair[
        "selected_actions"
    ]

    safe_action = selected[
        "authorized_user_action"
    ]

    risky_action = selected[
        "attacker_target_action"
    ]

    safe_name = (
        safe_action.get("normalized_function_name")
        or safe_action.get("function")
        or safe_action.get("tool_name")
    )

    risky_name = (
        risky_action.get("normalized_function_name")
        or risky_action.get("function")
        or risky_action.get("tool_name")
    )

    return safe_name == risky_name


def main() -> None:

    reviewed_at = datetime.now(
        timezone.utc
    ).isoformat()


    pairs = load_jsonl(
        PAIR_PLAN_PATH
    )

    queue_fieldnames, queue_rows = load_csv(
        SECOND_REVIEW_QUEUE_PATH
    )

    _, cumulative_rows = load_csv(
        CUMULATIVE_REVIEW_LEDGER_PATH
    )


    pair_by_id = {
        str(pair["pair_id"]): pair
        for pair in pairs
    }


    expected_pair_ids = set(
        EXPECTED_REPAIRS
    )

    queue_pair_ids = {
        str(row["pair_id"])
        for row in queue_rows
    }


    if len(queue_rows) != EXPECTED_REPAIRED_PAIR_COUNT:
        raise ValueError(
            "Expected nine second-review rows, "
            f"found {len(queue_rows)}."
        )


    if queue_pair_ids != expected_pair_ids:
        raise ValueError(
            "Unexpected second-review inventory.\n"
            f"Expected: {sorted(expected_pair_ids)}\n"
            f"Found: {sorted(queue_pair_ids)}"
        )


    cumulative_counts = Counter(
        row.get(
            "cumulative_review_decision",
            "",
        )
        for row in cumulative_rows
    )


    if (
        cumulative_counts[
            "approve_pair"
        ]
        !=
        EXPECTED_PREVIOUS_APPROVED_PAIR_COUNT
    ):
        raise ValueError(
            "Expected 60 previously approved pairs, "
            f"found "
            f"{cumulative_counts['approve_pair']}."
        )


    if (
        cumulative_counts[
            "needs_revision"
        ]
        !=
        EXPECTED_PREVIOUS_REVISION_PAIR_COUNT
    ):
        raise ValueError(
            "Expected 40 previously pending pairs, "
            f"found "
            f"{cumulative_counts['needs_revision']}."
        )


    cumulative_by_id = {
        str(row["pair_id"]): row
        for row in cumulative_rows
    }


    for pair_id, expectation in (
        EXPECTED_REPAIRS.items()
    ):

        pair = pair_by_id.get(
            pair_id
        )

        if pair is None:
            raise ValueError(
                f"Pair missing from repaired plan: "
                f"{pair_id}"
            )


        previous_review = cumulative_by_id.get(
            pair_id
        )

        if previous_review is None:
            raise ValueError(
                f"Pair missing from cumulative ledger: "
                f"{pair_id}"
            )


        if (
            previous_review.get(
                "cumulative_review_decision"
            )
            !=
            "needs_revision"
        ):
            raise ValueError(
                f"{pair_id} was not pending revision "
                "before this review."
            )


        surface = pair[
            "injection_surface"
        ]

        binding = pair.get(
            "context_bindings",
            {},
        )


        if (
            surface.get("vector_id")
            !=
            expectation["vector_id"]
        ):
            raise ValueError(
                f"Unexpected vector for {pair_id}: "
                f"{surface.get('vector_id')}"
            )


        if (
            binding.get(
                "retrieved_object_locator"
            )
            !=
            expectation["locator"]
        ):
            raise ValueError(
                f"Unexpected locator for {pair_id}: "
                f"{binding.get('retrieved_object_locator')}"
            )


        if (
            binding.get("binding_type")
            !=
            expectation["binding_type"]
        ):
            raise ValueError(
                f"Unexpected binding type for "
                f"{pair_id}."
            )


        if (
            binding.get("binding_status")
            !=
            expectation["binding_status"]
        ):
            raise ValueError(
                f"Unexpected binding status for "
                f"{pair_id}."
            )


        if same_tool(pair):
            raise ValueError(
                f"{pair_id} unexpectedly became "
                "a same-tool pair."
            )


    if SECOND_REVIEW_QUEUE_BACKUP_PATH.exists():
        raise FileExistsError(
            "Backup already exists: "
            f"{SECOND_REVIEW_QUEUE_BACKUP_PATH}"
        )


    shutil.copy2(
        SECOND_REVIEW_QUEUE_PATH,
        SECOND_REVIEW_QUEUE_BACKUP_PATH,
    )


    required_output_columns = [
        "second_review_decision",
        "second_review_note",
        "second_reviewed_at",
        "second_review_status",
        "label_eligible_after_second_review",
    ]


    output_fieldnames = list(
        queue_fieldnames
    )

    for column in required_output_columns:

        if column not in output_fieldnames:
            output_fieldnames.append(
                column
            )


    updated_rows = []


    for row in queue_rows:

        pair_id = str(
            row["pair_id"]
        )

        updated = dict(
            row
        )

        updated[
            "second_review_decision"
        ] = "approve_pair"

        updated[
            "second_review_note"
        ] = REVIEW_NOTES[
            pair_id
        ]

        updated[
            "second_reviewed_at"
        ] = reviewed_at

        updated[
            "second_review_status"
        ] = "human_reviewed_approved"

        updated[
            "label_eligible_after_second_review"
        ] = "true"

        updated_rows.append(
            updated
        )


    write_csv(
        SECOND_REVIEW_QUEUE_PATH,
        output_fieldnames,
        updated_rows,
    )


    decision_counts = Counter(
        row[
            "second_review_decision"
        ]
        for row in updated_rows
    )


    if decision_counts != {
        "approve_pair": 9,
    }:
        raise ValueError(
            "Unexpected second-review decisions: "
            f"{dict(decision_counts)}"
        )


    cumulative_approved = (
        EXPECTED_PREVIOUS_APPROVED_PAIR_COUNT
        +
        len(updated_rows)
    )

    remaining_revision = (
        EXPECTED_PREVIOUS_REVISION_PAIR_COUNT
        -
        len(updated_rows)
    )

    cumulative_label_eligible_rows = (
        cumulative_approved
        *
        2
    )


    if (
        cumulative_approved
        !=
        EXPECTED_CUMULATIVE_APPROVED_PAIR_COUNT
    ):
        raise ValueError(
            "Unexpected cumulative approved count."
        )


    if (
        remaining_revision
        !=
        EXPECTED_REMAINING_REVISION_PAIR_COUNT
    ):
        raise ValueError(
            "Unexpected remaining revision count."
        )


    if (
        cumulative_label_eligible_rows
        !=
        EXPECTED_CUMULATIVE_LABEL_ELIGIBLE_ROW_COUNT
    ):
        raise ValueError(
            "Unexpected cumulative label-eligible "
            "row count."
        )


    manifest = json.loads(
        REPAIR_MANIFEST_PATH.read_text(
            encoding="utf-8"
        )
    )


    manifest[
        "second_human_review"
    ] = {
        "reviewed_at": reviewed_at,

        "reviewed_pair_count": len(
            updated_rows
        ),

        "approved_pair_count": len(
            updated_rows
        ),

        "needs_further_revision_pair_count": 0,

        "excluded_pair_count": 0,

        "newly_label_eligible_runtime_row_count": (
            EXPECTED_NEW_LABEL_ELIGIBLE_ROW_COUNT
        ),

        "cumulative_approved_pair_count": (
            cumulative_approved
        ),

        "remaining_revision_pair_count": (
            remaining_revision
        ),

        "cumulative_label_eligible_runtime_row_count": (
            cumulative_label_eligible_rows
        ),

        "decisions_written_to": str(
            SECOND_REVIEW_QUEUE_PATH
        ),

        "final_labels_modified": False,

        "labeled_pool_modified": False,
    }


    REPAIR_MANIFEST_PATH.write_text(
        json.dumps(
            manifest,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


    report = {
        "artifact_version": "0.1.3",

        "reviewed_at": reviewed_at,

        "candidate_pair_plan": str(
            PAIR_PLAN_PATH
        ),

        "second_review_queue": str(
            SECOND_REVIEW_QUEUE_PATH
        ),

        "second_review_queue_backup": str(
            SECOND_REVIEW_QUEUE_BACKUP_PATH
        ),

        "reviewed_repaired_pair_count": (
            len(updated_rows)
        ),

        "approved_repaired_pair_count": (
            len(updated_rows)
        ),

        "needs_further_revision_pair_count": 0,

        "excluded_pair_count": 0,

        "newly_label_eligible_runtime_row_count": (
            EXPECTED_NEW_LABEL_ELIGIBLE_ROW_COUNT
        ),

        "cumulative_approved_pair_count": (
            cumulative_approved
        ),

        "remaining_revision_pair_count": (
            remaining_revision
        ),

        "cumulative_label_eligible_runtime_row_count": (
            cumulative_label_eligible_rows
        ),

        "approved_pair_ids": sorted(
            expected_pair_ids
        ),

        "validation": {
            "vector_binding_validation_passed": 9,
            "same_tool_repaired_pair_count": 0,
            "all_pairs_previously_needs_revision": True,
        },

        "smoke_pool_modified": False,

        "labeled_pool_modified": False,

        "final_labels_modified": False,

        "pair_plan_modified": False,
    }


    REPORT_PATH.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


    print("=" * 80)
    print(
        "AGENTDOJO P2 DETERMINISTIC SECOND "
        "HUMAN REVIEW v0.1.3 COMPLETED"
    )
    print("=" * 80)

    print()
    print(
        "Reviewed repaired pairs:",
        len(updated_rows),
    )

    print(
        "Approved repaired pairs:",
        len(updated_rows),
    )

    print(
        "Needs further revision:",
        0,
    )

    print(
        "Excluded:",
        0,
    )

    print()
    print(
        "Newly label-eligible runtime rows:",
        EXPECTED_NEW_LABEL_ELIGIBLE_ROW_COUNT,
    )

    print(
        "Cumulative approved pairs:",
        cumulative_approved,
    )

    print(
        "Remaining revision pairs:",
        remaining_revision,
    )

    print(
        "Cumulative label-eligible rows:",
        cumulative_label_eligible_rows,
    )

    print()
    print(
        "Smoke pool modified: no"
    )

    print(
        "Labeled pool modified: no"
    )

    print(
        "Final labels modified: no"
    )

    print(
        "Pair plan modified: no"
    )

    print()
    print(
        f"Updated queue: "
        f"{SECOND_REVIEW_QUEUE_PATH}"
    )

    print(
        f"Backup: "
        f"{SECOND_REVIEW_QUEUE_BACKUP_PATH}"
    )

    print(
        f"Report: {REPORT_PATH}"
    )


if __name__ == "__main__":
    main()

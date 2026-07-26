from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BASE_DIRECTORY = Path(
    "data/interim/"
    "agentdojo_turkish_full_translation_batches_v0.2.0"
)

TRANSLATED_PATH = (
    BASE_DIRECTORY
    / "agentdojo_tr_batch_007_v0.2.1_translated.jsonl"
)

REVIEW_PATH = (
    BASE_DIRECTORY
    / "agentdojo_tr_batch_007_v0.2.1_review.csv"
)

OUTPUT_PATH = (
    BASE_DIRECTORY
    / "agentdojo_tr_batch_007_v0.2.2_reviewed.jsonl"
)

OUTPUT_REPORT_PATH = (
    BASE_DIRECTORY
    / "agentdojo_tr_batch_007_v0.2.2_review_apply_report.json"
)

EXPECTED_ROWS = 10
EXPECTED_BATCH_ID = "agentdojo_tr_batch_007"
ALLOWED_DECISIONS = {
    "approve",
    "needs_revision",
    "exclude",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing input file: {path}")

    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid JSONL in {path} at line "
                    f"{line_number}."
                ) from error

    return rows


def load_review_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing review CSV: {path}")

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        return list(csv.DictReader(file))


def write_jsonl(
    path: Path,
    rows: list[dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as file:
        for row in rows:
            file.write(
                json.dumps(
                    row,
                    ensure_ascii=False,
                )
            )
            file.write("\n")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(
            lambda: file.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def validate_unique_pair_ids(
    rows: list[dict[str, Any]],
    source_name: str,
) -> None:
    pair_ids = [
        str(row.get("pair_id", "")).strip()
        for row in rows
    ]

    missing = [
        index + 1
        for index, pair_id in enumerate(pair_ids)
        if not pair_id
    ]
    if missing:
        raise ValueError(
            f"{source_name}: empty pair_id at rows "
            f"{missing}."
        )

    duplicates = sorted(
        pair_id
        for pair_id, count
        in Counter(pair_ids).items()
        if count > 1
    )
    if duplicates:
        raise ValueError(
            f"{source_name}: duplicate pair IDs: "
            f"{duplicates}"
        )


def validate_review_rows(
    review_rows: list[dict[str, str]],
) -> None:
    required_columns = {
        "pair_id",
        "human_review_decision",
        "reviewer_note",
    }

    if not review_rows:
        raise ValueError("Review CSV is empty.")

    missing_columns = (
        required_columns - set(review_rows[0])
    )
    if missing_columns:
        raise ValueError(
            "Review CSV is missing columns: "
            f"{sorted(missing_columns)}"
        )

    invalid_decisions: list[tuple[str, str]] = []
    empty_notes: list[str] = []

    for row in review_rows:
        pair_id = row["pair_id"].strip()
        decision = (
            row["human_review_decision"]
            .strip()
            .lower()
        )
        note = row["reviewer_note"].strip()

        if decision not in ALLOWED_DECISIONS:
            invalid_decisions.append(
                (pair_id, decision)
            )

        if not note:
            empty_notes.append(pair_id)

    if invalid_decisions:
        raise ValueError(
            "Invalid or empty review decisions: "
            f"{invalid_decisions}"
        )

    if empty_notes:
        raise ValueError(
            "Empty reviewer notes for: "
            f"{empty_notes}"
        )


def review_status_for(decision: str) -> str:
    mapping = {
        "approve": "human_review_approved",
        "needs_revision": (
            "human_review_needs_revision"
        ),
        "exclude": "human_review_excluded",
    }
    return mapping[decision]


def main() -> None:
    translated_sha_before = sha256_file(
        TRANSLATED_PATH
    )
    review_sha_before = sha256_file(REVIEW_PATH)

    translated_rows = load_jsonl(
        TRANSLATED_PATH
    )
    review_rows = load_review_csv(REVIEW_PATH)

    if len(translated_rows) != EXPECTED_ROWS:
        raise ValueError(
            f"Expected {EXPECTED_ROWS} translated rows, "
            f"found {len(translated_rows)}."
        )

    if len(review_rows) != EXPECTED_ROWS:
        raise ValueError(
            f"Expected {EXPECTED_ROWS} review rows, "
            f"found {len(review_rows)}."
        )

    validate_unique_pair_ids(
        translated_rows,
        "translated JSONL",
    )
    validate_unique_pair_ids(
        review_rows,
        "review CSV",
    )
    validate_review_rows(review_rows)

    translated_by_pair = {
        str(row["pair_id"]).strip(): row
        for row in translated_rows
    }

    review_by_pair = {
        row["pair_id"].strip(): row
        for row in review_rows
    }

    translated_pair_ids = set(
        translated_by_pair
    )
    review_pair_ids = set(review_by_pair)

    missing_from_review = sorted(
        translated_pair_ids - review_pair_ids
    )
    extra_in_review = sorted(
        review_pair_ids - translated_pair_ids
    )

    if missing_from_review or extra_in_review:
        raise ValueError(
            "Pair-ID mismatch between translated "
            "artifact and review CSV. "
            f"Missing from review={missing_from_review}; "
            f"extra in review={extra_in_review}"
        )

    reviewed_at = (
        datetime.now(timezone.utc).isoformat()
    )

    reviewed_rows: list[dict[str, Any]] = []

    for translated_row in translated_rows:
        pair_id = str(
            translated_row["pair_id"]
        ).strip()
        review_row = review_by_pair[pair_id]

        decision = (
            review_row[
                "human_review_decision"
            ]
            .strip()
            .lower()
        )
        reviewer_note = (
            review_row["reviewer_note"].strip()
        )

        reviewed_row = dict(translated_row)
        reviewed_row[
            "human_review_decision"
        ] = decision
        reviewed_row[
            "reviewer_note"
        ] = reviewer_note
        reviewed_row[
            "translation_status"
        ] = review_status_for(decision)
        reviewed_row[
            "review_artifact_version"
        ] = "v0.2.2"
        reviewed_row[
            "reviewed_at"
        ] = reviewed_at
        reviewed_row[
            "review_source"
        ] = str(REVIEW_PATH)

        if (
            reviewed_row.get(
                "translation_batch_id"
            )
            != EXPECTED_BATCH_ID
        ):
            raise ValueError(
                f"{pair_id}: unexpected "
                "translation_batch_id="
                f"{reviewed_row.get('translation_batch_id')}"
            )

        reviewed_rows.append(reviewed_row)

    decisions = Counter(
        str(
            row["human_review_decision"]
        )
        for row in reviewed_rows
    )

    statuses = Counter(
        str(row["translation_status"])
        for row in reviewed_rows
    )

    for row in reviewed_rows:
        decision = str(
            row["human_review_decision"]
        )
        expected_status = review_status_for(
            decision
        )

        if (
            row["translation_status"]
            != expected_status
        ):
            raise ValueError(
                f"{row['pair_id']}: decision/status "
                "mismatch."
            )

    write_jsonl(
        OUTPUT_PATH,
        reviewed_rows,
    )

    translated_sha_after = sha256_file(
        TRANSLATED_PATH
    )
    review_sha_after = sha256_file(
        REVIEW_PATH
    )

    if (
        translated_sha_before
        != translated_sha_after
    ):
        raise RuntimeError(
            "Translated source artifact was modified."
        )

    if review_sha_before != review_sha_after:
        raise RuntimeError(
            "Review CSV was modified."
        )

    report = {
        "artifact_version": "v0.2.2",
        "batch_id": EXPECTED_BATCH_ID,
        "translated_input": {
            "path": str(TRANSLATED_PATH),
            "sha256_before": (
                translated_sha_before
            ),
            "sha256_after": (
                translated_sha_after
            ),
            "modified": False,
        },
        "review_input": {
            "path": str(REVIEW_PATH),
            "sha256_before": (
                review_sha_before
            ),
            "sha256_after": (
                review_sha_after
            ),
            "modified": False,
        },
        "row_count": len(reviewed_rows),
        "pair_count": len(
            {
                row["pair_id"]
                for row in reviewed_rows
            }
        ),
        "decision_counts": dict(decisions),
        "translation_status_counts": dict(
            statuses
        ),
        "pair_id_alignment": {
            "matched": True,
            "missing_from_review": [],
            "extra_in_review": [],
        },
        "duplicate_pair_ids": {
            "translated_jsonl": 0,
            "review_csv": 0,
        },
        "output": {
            "reviewed_jsonl": str(
                OUTPUT_PATH
            ),
            "report": str(
                OUTPUT_REPORT_PATH
            ),
        },
        "application_result": "passed",
        "important_note": (
            "Review decisions were joined by pair_id. "
            "The translated JSONL and review CSV were "
            "validated and left unchanged."
        ),
    }

    OUTPUT_REPORT_PATH.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print("=" * 80)
    print(
        "AGENTDOJO TURKISH BATCH 007 "
        "HUMAN REVIEW APPLICATION v0.2.2"
    )
    print("=" * 80)
    print()
    print("Translated rows:", len(translated_rows))
    print("Review rows:", len(review_rows))
    print("Matched pairs:", len(reviewed_rows))
    print("Decisions:", dict(decisions))
    print("Statuses:", dict(statuses))
    print()
    print("Duplicate translated pair IDs: 0")
    print("Duplicate review pair IDs: 0")
    print("Missing review pairs: 0")
    print("Extra review pairs: 0")
    print("Translated artifact modified: no")
    print("Review CSV modified: no")
    print()
    print("Reviewed artifact:", OUTPUT_PATH)
    print("Report:", OUTPUT_REPORT_PATH)
    print()
    print("Review application: PASSED")


if __name__ == "__main__":
    main()

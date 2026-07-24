from __future__ import annotations

import hashlib
import json
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BASE_DIR = Path(
    "data/interim/"
    "agentdojo_turkish_full_translation_batches_v0.2.0"
)

TRANSLATED_PATH = (
    BASE_DIR
    / "agentdojo_tr_batch_001_v0.2.1_translated.jsonl"
)

VALIDATION_REPORT_PATH = (
    BASE_DIR
    / "agentdojo_tr_batch_001_v0.2.1_validation_report.json"
)

OUTPUT_REVIEWED_PATH = (
    BASE_DIR
    / "agentdojo_tr_batch_001_v0.2.2_human_reviewed.jsonl"
)

OUTPUT_REVISION_QUEUE_PATH = (
    BASE_DIR
    / "agentdojo_tr_batch_001_v0.2.2_revision_queue.jsonl"
)

OUTPUT_REPORT_PATH = (
    BASE_DIR
    / "agentdojo_tr_batch_001_v0.2.2_human_review_report.json"
)


APPROVED_PAIR_IDS = {
    "agentdojo_pair_067",
    "agentdojo_pair_007",
    "agentdojo_pair_087",
    "agentdojo_pair_069",
    "agentdojo_pair_061",
    "agentdojo_pair_014",
    "agentdojo_pair_093",
}


REVISION_DECISIONS = {
    "agentdojo_pair_092": {
        "issue_code": (
            "code_like_string_quote_collision"
        ),
        "reviewer_note": (
            "user_goal_tr içindeki Haziran'da apostrofu, "
            "f'...' biçimindeki kod benzeri stringi sözdizimsel "
            "olarak bozuyor. Çift tırnaklı f-string kullanılmalı "
            "veya ifade '13 Haziran tarihinde' olarak yazılmalıdır."
        ),
    },

    "agentdojo_pair_049": {
        "issue_code": (
            "untranslated_natural_language_subject"
        ),
        "reviewer_note": (
            "retrieved_content_tr içindeki doğal dil e-posta konusu "
            "'Travel Information at {hotel_name}' Türkçeleştirilmemiş. "
            "Placeholder korunarak konu Türkçeye çevrilmelidir."
        ),
    },

    "agentdojo_pair_045": {
        "issue_code": (
            "untranslated_natural_language_subject"
        ),
        "reviewer_note": (
            "'All messages with Travel Agency' konusu hem "
            "retrieved_content_tr hem risky_attempted_action_tr "
            "içinde İngilizce kalmış. İki alanda da aynı Türkçe "
            "karşılık kullanılmalıdır."
        ),
    },
}


EXPECTED_PAIR_COUNT = 10
EXPECTED_APPROVED_COUNT = 7
EXPECTED_REVISION_COUNT = 3


def load_jsonl(
    path: Path,
) -> list[dict[str, Any]]:

    if not path.exists():
        raise FileNotFoundError(
            f"Missing JSONL file: {path}"
        )

    rows = []

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
                rows.append(
                    json.loads(line)
                )

            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid JSONL in {path}, "
                    f"line {line_number}."
                ) from error

    return rows


def write_jsonl(
    path: Path,
    rows: list[dict[str, Any]],
) -> None:

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
    ) as file:

        for row in rows:
            file.write(
                json.dumps(
                    row,
                    ensure_ascii=False,
                )
            )
            file.write("\n")


def sha256_file(
    path: Path,
) -> str:

    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def main() -> None:

    translated_hash_before = sha256_file(
        TRANSLATED_PATH
    )

    validation_hash_before = sha256_file(
        VALIDATION_REPORT_PATH
    )

    rows = load_jsonl(
        TRANSLATED_PATH
    )

    validation_report = json.loads(
        VALIDATION_REPORT_PATH.read_text(
            encoding="utf-8"
        )
    )


    if len(rows) != EXPECTED_PAIR_COUNT:
        raise ValueError(
            "Expected 10 translated pairs, "
            f"found {len(rows)}."
        )


    pair_ids = {
        str(row["pair_id"])
        for row in rows
    }


    expected_pair_ids = (
        APPROVED_PAIR_IDS
        |
        set(REVISION_DECISIONS)
    )


    if pair_ids != expected_pair_ids:
        raise ValueError(
            "Unexpected Batch 001 pair inventory.\n"
            f"Missing: "
            f"{sorted(expected_pair_ids - pair_ids)}\n"
            f"Extra: "
            f"{sorted(pair_ids - expected_pair_ids)}"
        )


    automatic_validation = (
        validation_report.get(
            "automatic_validation",
            {},
        )
    )


    required_validation_flags = (
        "all_translated_fields_nonempty",
        "protected_token_checks_passed",
        "authorized_tool_checks_passed",
        "technical_action_checks_passed",
    )


    for flag in required_validation_flags:

        if automatic_validation.get(flag) is not True:
            raise ValueError(
                f"Automatic validation did not "
                f"pass: {flag}"
            )


    if (
        automatic_validation.get(
            "test_pair_count"
        )
        !=
        0
    ):
        raise ValueError(
            "Test pair entered Batch 001."
        )


    reviewed_at = datetime.now(
        timezone.utc
    ).isoformat()


    reviewed_rows = []
    revision_rows = []


    for source_row in rows:

        row = deepcopy(
            source_row
        )

        pair_id = str(
            row["pair_id"]
        )


        if (
            row.get(
                "translation_status"
            )
            !=
            "translated_pending_human_review"
        ):
            raise ValueError(
                f"{pair_id} has unexpected status: "
                f"{row.get('translation_status')}"
            )


        row[
            "human_review_version"
        ] = "v0.2.2"

        row[
            "human_reviewed_at"
        ] = reviewed_at


        if pair_id in APPROVED_PAIR_IDS:

            row[
                "human_review_decision"
            ] = "approve_translation"

            row[
                "translation_status"
            ] = "human_reviewed_approved"

            row[
                "human_review_issue_code"
            ] = ""

            row[
                "reviewer_note"
            ] = (
                "Türkçe çeviri kaynak anlamını, "
                "yetkilendirme kapsamını, teknik belirteçleri "
                "ve safe-risky operasyonel ayrımı korumaktadır."
            )


        else:

            revision = (
                REVISION_DECISIONS[
                    pair_id
                ]
            )

            row[
                "human_review_decision"
            ] = "needs_revision"

            row[
                "translation_status"
            ] = "human_reviewed_needs_revision"

            row[
                "human_review_issue_code"
            ] = revision[
                "issue_code"
            ]

            row[
                "reviewer_note"
            ] = revision[
                "reviewer_note"
            ]

            revision_rows.append(
                deepcopy(row)
            )


        reviewed_rows.append(
            row
        )


    decision_counts = Counter(
        str(
            row[
                "human_review_decision"
            ]
        )
        for row in reviewed_rows
    )


    expected_decision_counts = {
        "approve_translation": (
            EXPECTED_APPROVED_COUNT
        ),
        "needs_revision": (
            EXPECTED_REVISION_COUNT
        ),
    }


    if dict(decision_counts) != (
        expected_decision_counts
    ):
        raise ValueError(
            "Unexpected review counts: "
            f"{dict(decision_counts)}"
        )


    if len(revision_rows) != (
        EXPECTED_REVISION_COUNT
    ):
        raise ValueError(
            "Expected 3 revision rows, "
            f"found {len(revision_rows)}."
        )


    write_jsonl(
        OUTPUT_REVIEWED_PATH,
        reviewed_rows,
    )

    write_jsonl(
        OUTPUT_REVISION_QUEUE_PATH,
        revision_rows,
    )


    if (
        sha256_file(
            TRANSLATED_PATH
        )
        !=
        translated_hash_before
    ):
        raise ValueError(
            "Translated source artifact changed."
        )


    if (
        sha256_file(
            VALIDATION_REPORT_PATH
        )
        !=
        validation_hash_before
    ):
        raise ValueError(
            "Automatic validation report changed."
        )


    report = {
        "artifact_version": "0.2.2",

        "translation_batch_id": (
            "agentdojo_tr_batch_001"
        ),

        "reviewed_pair_count": (
            len(reviewed_rows)
        ),

        "approved_translation_count": (
            decision_counts[
                "approve_translation"
            ]
        ),

        "needs_revision_count": (
            decision_counts[
                "needs_revision"
            ]
        ),

        "excluded_translation_count": 0,

        "currently_label_eligible_pairs": (
            EXPECTED_APPROVED_COUNT
        ),

        "currently_label_eligible_runtime_rows": (
            EXPECTED_APPROVED_COUNT * 2
        ),

        "revision_pair_ids": sorted(
            REVISION_DECISIONS
        ),

        "revision_issue_counts": dict(
            Counter(
                revision[
                    "issue_code"
                ]
                for revision
                in REVISION_DECISIONS.values()
            )
        ),

        "validation": {
            "automatic_validation_confirmed": True,
            "safe_risky_semantics_reviewed": True,
            "natural_turkish_reviewed": True,
            "technical_identifiers_reviewed": True,
            "test_pair_count": 0,
            "source_translated_file_modified": False,
            "source_validation_report_modified": False,
        },

        "source_hashes": {
            "translated_batch": (
                translated_hash_before
            ),
            "automatic_validation_report": (
                validation_hash_before
            ),
        },

        "outputs": {
            "human_reviewed_batch": str(
                OUTPUT_REVIEWED_PATH
            ),
            "revision_queue": str(
                OUTPUT_REVISION_QUEUE_PATH
            ),
        },

        "important_note": (
            "Batch 001 henüz tamamen onaylanmış değildir. "
            "Üç needs_revision pair onarılıp yeniden "
            "incelenmeden batch final eğitim havuzuna "
            "materialize edilmemelidir."
        ),
    }


    OUTPUT_REPORT_PATH.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


    print("=" * 80)

    print(
        "AGENTDOJO TURKISH BATCH 001 "
        "HUMAN REVIEW v0.2.2 COMPLETED"
    )

    print("=" * 80)

    print()

    print(
        "Reviewed pairs:",
        len(reviewed_rows),
    )

    print(
        "Approved translations:",
        decision_counts[
            "approve_translation"
        ],
    )

    print(
        "Needs revision:",
        decision_counts[
            "needs_revision"
        ],
    )

    print(
        "Excluded translations:",
        0,
    )

    print()

    print(
        "Currently label-eligible pairs:",
        EXPECTED_APPROVED_COUNT,
    )

    print(
        "Currently label-eligible runtime rows:",
        EXPECTED_APPROVED_COUNT * 2,
    )

    print()

    print("Revision pairs:")

    for pair_id in sorted(
        REVISION_DECISIONS
    ):

        print(
            " ",
            pair_id,
            "|",
            REVISION_DECISIONS[
                pair_id
            ][
                "issue_code"
            ],
        )

    print()

    print(
        "Reviewed batch:",
        OUTPUT_REVIEWED_PATH,
    )

    print(
        "Revision queue:",
        OUTPUT_REVISION_QUEUE_PATH,
    )

    print(
        "Review report:",
        OUTPUT_REPORT_PATH,
    )

    print()

    print(
        "Source translated file modified: no"
    )

    print(
        "Batch fully approved: no"
    )


if __name__ == "__main__":
    main()

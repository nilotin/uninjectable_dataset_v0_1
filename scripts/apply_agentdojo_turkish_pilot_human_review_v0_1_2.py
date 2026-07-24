from __future__ import annotations

import hashlib
import json
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TRANSLATION_QUEUE_PATH = Path(
    "data/interim/"
    "agentdojo_turkish_translation_pilot_queue_"
    "v0.1.1_translated.jsonl"
)

POLICY_QUEUE_PATH = Path(
    "data/interim/"
    "agentdojo_turkish_policy_template_queue_"
    "v0.1.1_translated.jsonl"
)

VALIDATION_REPORT_PATH = Path(
    "data/interim/"
    "agentdojo_turkish_translation_pilot_"
    "v0.1.1_validation_report.json"
)


OUTPUT_TRANSLATION_QUEUE_PATH = Path(
    "data/interim/"
    "agentdojo_turkish_translation_pilot_queue_"
    "v0.1.2_human_reviewed.jsonl"
)

OUTPUT_POLICY_QUEUE_PATH = Path(
    "data/interim/"
    "agentdojo_turkish_policy_template_queue_"
    "v0.1.2_human_reviewed.jsonl"
)

OUTPUT_REPORT_PATH = Path(
    "data/interim/"
    "agentdojo_turkish_translation_pilot_"
    "v0.1.2_human_review_report.json"
)


EXPECTED_PAIR_IDS = {
    "agentdojo_pair_003",
    "agentdojo_pair_018",
    "agentdojo_pair_015",
    "agentdojo_pair_040",
    "agentdojo_pair_031",
    "agentdojo_pair_021",
    "agentdojo_pair_059",
    "agentdojo_pair_060",
    "agentdojo_pair_050",
    "agentdojo_pair_091",
    "agentdojo_pair_082",
    "agentdojo_pair_095",
}

EXPECTED_PAIR_COUNT = 12
EXPECTED_RUNTIME_ROW_COUNT = 24
EXPECTED_POLICY_TEMPLATE_COUNT = 1

EXPECTED_SUITE_COUNTS = {
    "banking": 3,
    "slack": 3,
    "travel": 3,
    "workspace": 3,
}

EXPECTED_SPLIT_COUNTS = {
    "train": 8,
    "validation": 4,
}

EXPECTED_SAME_TOOL_COUNT = 9


TRANSLATED_FIELDS = (
    "user_goal_tr",
    "retrieved_content_tr",
    "user_authorization_tr",
    "safe_attempted_action_tr",
    "risky_attempted_action_tr",
)


def load_jsonl(
    path: Path,
) -> list[dict[str, Any]]:

    if not path.exists():
        raise FileNotFoundError(
            f"Missing JSONL file: {path}"
        )

    rows: list[dict[str, Any]] = []

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


def extract_line(
    text: str,
    prefix: str,
) -> str | None:

    for line in text.splitlines():

        if line.startswith(prefix):
            return line[len(prefix):]

    return None


def validate_attempted_action(
    pair_id: str,
    variant: str,
    english: str,
    turkish: str,
) -> None:

    for prefix in (
        "tool_name=",
        "capability_class=",
        "action_impact=",
    ):

        english_value = extract_line(
            english,
            prefix,
        )

        turkish_value = extract_line(
            turkish,
            prefix,
        )

        if english_value is None:
            raise ValueError(
                f"{pair_id} {variant}: "
                f"English field missing {prefix}"
            )

        if turkish_value is None:
            raise ValueError(
                f"{pair_id} {variant}: "
                f"Turkish field missing {prefix}"
            )

        if english_value != turkish_value:
            raise ValueError(
                f"{pair_id} {variant}: "
                f"technical value changed for "
                f"{prefix}\n"
                f"EN: {english_value}\n"
                f"TR: {turkish_value}"
            )


def main() -> None:

    source_translation_hash_before = (
        sha256_file(
            TRANSLATION_QUEUE_PATH
        )
    )

    source_policy_hash_before = (
        sha256_file(
            POLICY_QUEUE_PATH
        )
    )

    source_validation_hash_before = (
        sha256_file(
            VALIDATION_REPORT_PATH
        )
    )


    translation_rows = load_jsonl(
        TRANSLATION_QUEUE_PATH
    )

    policy_rows = load_jsonl(
        POLICY_QUEUE_PATH
    )


    if (
        len(translation_rows)
        !=
        EXPECTED_PAIR_COUNT
    ):
        raise ValueError(
            "Expected 12 translation pairs, "
            f"found {len(translation_rows)}."
        )


    pair_ids = {
        str(row["pair_id"])
        for row in translation_rows
    }


    if pair_ids != EXPECTED_PAIR_IDS:
        raise ValueError(
            "Unexpected pilot pair inventory.\n"
            f"Missing: "
            f"{sorted(EXPECTED_PAIR_IDS - pair_ids)}\n"
            f"Extra: "
            f"{sorted(pair_ids - EXPECTED_PAIR_IDS)}"
        )


    if (
        len(policy_rows)
        !=
        EXPECTED_POLICY_TEMPLATE_COUNT
    ):
        raise ValueError(
            "Expected one policy template, "
            f"found {len(policy_rows)}."
        )


    policy_by_id = {
        str(row["policy_template_id"]): row
        for row in policy_rows
    }


    if len(policy_by_id) != 1:
        raise ValueError(
            "Duplicate policy template IDs."
        )


    suite_counts = Counter(
        str(row["suite"])
        for row in translation_rows
    )

    split_counts = Counter(
        str(row["split"])
        for row in translation_rows
    )


    if dict(suite_counts) != EXPECTED_SUITE_COUNTS:
        raise ValueError(
            "Unexpected suite distribution:\n"
            f"{dict(suite_counts)}"
        )


    if dict(split_counts) != EXPECTED_SPLIT_COUNTS:
        raise ValueError(
            "Unexpected split distribution:\n"
            f"{dict(split_counts)}"
        )


    if any(
        str(row["split"]) == "test"
        for row in translation_rows
    ):
        raise ValueError(
            "Test split entered the Turkish pilot."
        )


    same_tool_count = sum(
        bool(
            row[
                "same_tool_minimal_pair"
            ]
        )
        for row in translation_rows
    )


    if (
        same_tool_count
        !=
        EXPECTED_SAME_TOOL_COUNT
    ):
        raise ValueError(
            "Expected 9 same-tool pairs, "
            f"found {same_tool_count}."
        )


    reviewed_at = datetime.now(
        timezone.utc
    ).isoformat()


    reviewed_translation_rows = []


    for source_row in translation_rows:

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
                f"{pair_id} has unexpected "
                "translation status: "
                f"{row.get('translation_status')}"
            )


        for field in TRANSLATED_FIELDS:

            value = row.get(
                field
            )

            if (
                not isinstance(value, str)
                or
                not value.strip()
            ):
                raise ValueError(
                    f"{pair_id} has empty "
                    f"translated field: {field}"
                )


        policy_template_id = str(
            row["policy_template_id"]
        )


        if (
            policy_template_id
            not in
            policy_by_id
        ):
            raise ValueError(
                f"{pair_id} references unknown "
                "policy template: "
                f"{policy_template_id}"
            )


        validate_attempted_action(
            pair_id=pair_id,
            variant="safe",
            english=row[
                "safe_attempted_action_en"
            ],
            turkish=row[
                "safe_attempted_action_tr"
            ],
        )

        validate_attempted_action(
            pair_id=pair_id,
            variant="risky",
            english=row[
                "risky_attempted_action_en"
            ],
            turkish=row[
                "risky_attempted_action_tr"
            ],
        )


        row[
            "translation_status"
        ] = "human_reviewed_approved"

        row[
            "human_review_decision"
        ] = "approve_translation"

        row[
            "human_review_version"
        ] = "v0.1.2"

        row[
            "human_reviewed_at"
        ] = reviewed_at

        row[
            "reviewer_note"
        ] = (
            "Türkçe çeviri anlamsal olarak "
            "kaynak metinle uyumludur. Teknik "
            "belirteçler, placeholder değerleri, "
            "yetkilendirme kapsamı ve safe-risky "
            "operasyonel ayrımı korunmuştur."
        )


        if pair_id == "agentdojo_pair_018":

            row[
                "reviewer_note"
            ] += (
                " Fatura metnindeki \\\\t ve "
                "\\\\n kaçış dizileri kaynak "
                "biçimlendirmesini korumak amacıyla "
                "bilinçli olarak muhafaza edilmiştir."
            )


        reviewed_translation_rows.append(
            row
        )


    reviewed_policy_rows = []


    for source_row in policy_rows:

        row = deepcopy(
            source_row
        )


        if (
            row.get(
                "translation_status"
            )
            !=
            "translated_pending_human_review"
        ):
            raise ValueError(
                "Policy template has unexpected "
                "translation status."
            )


        policy_context_tr = row.get(
            "policy_context_tr"
        )


        if (
            not isinstance(
                policy_context_tr,
                str,
            )
            or
            not policy_context_tr.strip()
        ):
            raise ValueError(
                "Turkish policy translation "
                "is empty."
            )


        row[
            "translation_status"
        ] = "human_reviewed_approved"

        row[
            "human_review_decision"
        ] = "approve_translation"

        row[
            "human_review_version"
        ] = "v0.1.2"

        row[
            "human_reviewed_at"
        ] = reviewed_at

        row[
            "reviewer_note"
        ] = (
            "Türkçe politika metni kaynak "
            "politikanın yetkilendirme, güvenilmeyen "
            "kaynak ve kapsam sınırlandırma "
            "anlamlarını korumaktadır."
        )


        reviewed_policy_rows.append(
            row
        )


    decision_counts = Counter(
        str(
            row[
                "human_review_decision"
            ]
        )
        for row in reviewed_translation_rows
    )


    if dict(decision_counts) != {
        "approve_translation": 12
    }:
        raise ValueError(
            "Unexpected translation-review "
            f"decisions: {dict(decision_counts)}"
        )


    write_jsonl(
        OUTPUT_TRANSLATION_QUEUE_PATH,
        reviewed_translation_rows,
    )

    write_jsonl(
        OUTPUT_POLICY_QUEUE_PATH,
        reviewed_policy_rows,
    )


    source_translation_hash_after = (
        sha256_file(
            TRANSLATION_QUEUE_PATH
        )
    )

    source_policy_hash_after = (
        sha256_file(
            POLICY_QUEUE_PATH
        )
    )

    source_validation_hash_after = (
        sha256_file(
            VALIDATION_REPORT_PATH
        )
    )


    if (
        source_translation_hash_before
        !=
        source_translation_hash_after
    ):
        raise ValueError(
            "Source translation queue changed."
        )


    if (
        source_policy_hash_before
        !=
        source_policy_hash_after
    ):
        raise ValueError(
            "Source policy queue changed."
        )


    if (
        source_validation_hash_before
        !=
        source_validation_hash_after
    ):
        raise ValueError(
            "Source validation report changed."
        )


    report = {
        "artifact_version": "0.1.2",

        "review_type": (
            "turkish_translation_human_review"
        ),

        "reviewed_pair_count": (
            len(reviewed_translation_rows)
        ),

        "approved_translation_count": (
            decision_counts[
                "approve_translation"
            ]
        ),

        "needs_revision_count": 0,

        "excluded_translation_count": 0,

        "approved_policy_template_count": (
            len(reviewed_policy_rows)
        ),

        "newly_label_eligible_runtime_rows": (
            EXPECTED_RUNTIME_ROW_COUNT
        ),

        "suite_counts": dict(
            sorted(
                suite_counts.items()
            )
        ),

        "split_counts": dict(
            sorted(
                split_counts.items()
            )
        ),

        "test_pair_count": 0,

        "same_tool_pair_count": (
            same_tool_count
        ),

        "validation": {
            "all_translated_fields_nonempty": True,
            "technical_action_fields_preserved": True,
            "safe_risky_semantics_reviewed": True,
            "policy_semantics_reviewed": True,
            "source_translation_queue_modified": False,
            "source_policy_queue_modified": False,
            "source_validation_report_modified": False,
        },

        "source_hashes": {
            "translation_queue": (
                source_translation_hash_before
            ),

            "policy_queue": (
                source_policy_hash_before
            ),

            "automatic_validation_report": (
                source_validation_hash_before
            ),
        },

        "outputs": {
            "human_reviewed_translation_queue": str(
                OUTPUT_TRANSLATION_QUEUE_PATH
            ),

            "human_reviewed_policy_queue": str(
                OUTPUT_POLICY_QUEUE_PATH
            ),
        },

        "important_note": (
            "Bu aşama yalnızca Türkçe çeviri "
            "incelemesini tamamlar. Henüz Türkçe "
            "structured pool veya BERT training "
            "view materialize edilmemiştir."
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
        "AGENTDOJO TURKISH PILOT "
        "HUMAN REVIEW v0.1.2 COMPLETED"
    )

    print("=" * 80)

    print()

    print(
        "Reviewed pairs:",
        len(reviewed_translation_rows),
    )

    print(
        "Approved translations:",
        decision_counts[
            "approve_translation"
        ],
    )

    print(
        "Needs revision:",
        0,
    )

    print(
        "Excluded translations:",
        0,
    )

    print()

    print(
        "Approved policy templates:",
        len(reviewed_policy_rows),
    )

    print(
        "Newly label-eligible runtime rows:",
        EXPECTED_RUNTIME_ROW_COUNT,
    )

    print()

    print(
        "Suite counts:",
        dict(
            sorted(
                suite_counts.items()
            )
        ),
    )

    print(
        "Split counts:",
        dict(
            sorted(
                split_counts.items()
            )
        ),
    )

    print(
        "Same-tool pairs:",
        same_tool_count,
    )

    print(
        "Test pairs:",
        0,
    )

    print()

    print(
        "Translation queue:",
        OUTPUT_TRANSLATION_QUEUE_PATH,
    )

    print(
        "Policy queue:",
        OUTPUT_POLICY_QUEUE_PATH,
    )

    print(
        "Report:",
        OUTPUT_REPORT_PATH,
    )

    print()

    print(
        "Source translated files modified: no"
    )

    print(
        "Turkish labeled pool materialized: no"
    )


if __name__ == "__main__":
    main()

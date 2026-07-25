from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


BASE_DIR = Path(
    "data/interim/"
    "agentdojo_turkish_full_translation_batches_v0.2.0"
)

SOURCE_PATH = BASE_DIR / "agentdojo_tr_batch_004.jsonl"
TRANSLATED_PATH = (
    BASE_DIR
    / "agentdojo_tr_batch_004_v0.2.1_translated.jsonl"
)
REPORT_PATH = (
    BASE_DIR
    / "agentdojo_tr_batch_004_v0.2.1_validation_report.json"
)
REVIEW_CSV_PATH = (
    BASE_DIR
    / "agentdojo_tr_batch_004_v0.2.1_review.csv"
)

EXPECTED_ROWS = 10
EXPECTED_BATCH_ID = "agentdojo_tr_batch_004"
EXPECTED_BATCH_ORDER = list(range(1, 11))
EXPECTED_SPLITS = {
    "train": 7,
    "validation": 3,
}

TRANSLATED_FIELDS = (
    "user_goal_tr",
    "retrieved_content_tr",
    "user_authorization_tr",
    "safe_attempted_action_tr",
    "risky_attempted_action_tr",
)

ENGLISH_FIELDS = (
    "user_goal_en",
    "retrieved_content_en",
    "user_authorization_en",
    "safe_attempted_action_en",
    "risky_attempted_action_en",
)

# Preserve placeholders, Python/self references, URLs, e-mails, file names,
# dates, times, tool names and structured field names.
PLACEHOLDER_PATTERN = re.compile(
    r"""
    \{_[A-Z0-9_]+\}
    |
    \{URL\}
    |
    self\.[A-Za-z_][A-Za-z0-9_]*
    |
    pre_environment(?:\.[A-Za-z_][A-Za-z0-9_]*)+
    |
    [A-Za-z_][A-Za-z0-9_]*\[[^\]\n]+\](?:\.[A-Za-z_][A-Za-z0-9_]*)*
    |
    https?://[^\s'"]+
    |
    [A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}
    |
    [A-Za-z0-9_-]+\.(?:txt|docx|pdf|csv|json|jsonl)
    |
    \b\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2})?\b
    """,
    re.VERBOSE,
)

STRUCTURED_LINE_KEYS = (
    "authorized_tool=",
    "authorized_args=",
    "tool_name=",
    "args=",
    "capability_class=",
    "action_impact=",
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")

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
                    f"Invalid JSONL in {path} at line {line_number}."
                ) from error
    return rows


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_unique_pair_ids(
    rows: list[dict[str, Any]],
    source_name: str,
) -> None:
    pair_ids = [str(row.get("pair_id", "")).strip() for row in rows]

    missing = [
        index + 1
        for index, pair_id in enumerate(pair_ids)
        if not pair_id
    ]
    if missing:
        raise ValueError(
            f"{source_name}: empty pair_id at rows {missing}."
        )

    duplicates = sorted(
        pair_id
        for pair_id, count in Counter(pair_ids).items()
        if count > 1
    )
    if duplicates:
        raise ValueError(
            f"{source_name}: duplicate pair IDs: {duplicates}"
        )


def count_exact_tokens(text: str) -> Counter[str]:
    return Counter(PLACEHOLDER_PATTERN.findall(text))


def validate_preserved_tokens(
    pair_id: str,
    source_text: str,
    translated_text: str,
    field_name: str,
) -> list[str]:
    issues: list[str] = []

    source_tokens = count_exact_tokens(source_text)
    translated_tokens = count_exact_tokens(translated_text)

    missing = source_tokens - translated_tokens
    extra = translated_tokens - source_tokens

    if missing:
        issues.append(
            f"{field_name}: missing protected tokens "
            f"{dict(missing)}"
        )

    if extra:
        issues.append(
            f"{field_name}: unexpected protected tokens "
            f"{dict(extra)}"
        )

    return issues


def structured_value(
    text: str,
    key: str,
) -> str | None:
    for line in text.splitlines():
        if line.startswith(key):
            return line[len(key):]
    return None


def validate_structured_contract(
    source_text: str,
    translated_text: str,
    field_name: str,
) -> list[str]:
    issues: list[str] = []

    for key in STRUCTURED_LINE_KEYS:
        source_value = structured_value(source_text, key)
        translated_value = structured_value(translated_text, key)

        if source_value is None and translated_value is None:
            continue

        if source_value is None or translated_value is None:
            issues.append(
                f"{field_name}: structured line mismatch for {key}"
            )
            continue

        # These values are contract metadata and must remain exact.
        if key in {
            "authorized_tool=",
            "tool_name=",
            "capability_class=",
            "action_impact=",
        } and source_value != translated_value:
            issues.append(
                f"{field_name}: protected structured value changed "
                f"for {key}: {source_value!r} -> "
                f"{translated_value!r}"
            )

        # args/authorized_args may contain natural-language values that are
        # legitimately translated. Their protected tokens are validated
        # separately rather than requiring the entire expression to match.

    return issues


def make_review_rows(
    source_rows: list[dict[str, Any]],
    translated_by_pair: dict[str, dict[str, Any]],
    issues_by_pair: dict[str, list[str]],
) -> list[dict[str, str]]:
    review_rows: list[dict[str, str]] = []

    for source in source_rows:
        pair_id = str(source["pair_id"])
        translated = translated_by_pair[pair_id]
        issues = issues_by_pair[pair_id]

        review_rows.append(
            {
                "pair_id": pair_id,
                "suite": str(source["suite"]),
                "split": str(source["split"]),
                "session_group_id": str(
                    source["session_group_id"]
                ),
                "same_tool_minimal_pair": str(
                    source["same_tool_minimal_pair"]
                ).lower(),
                "automatic_validation_status": (
                    "passed" if not issues else "attention_required"
                ),
                "validation_issue_count": str(len(issues)),
                "validation_issues": " | ".join(issues),
                "user_goal_en": str(source["user_goal_en"]),
                "user_goal_tr": str(translated["user_goal_tr"]),
                "retrieved_content_en": str(
                    source["retrieved_content_en"]
                ),
                "retrieved_content_tr": str(
                    translated["retrieved_content_tr"]
                ),
                "user_authorization_en": str(
                    source["user_authorization_en"]
                ),
                "user_authorization_tr": str(
                    translated["user_authorization_tr"]
                ),
                "safe_attempted_action_en": str(
                    source["safe_attempted_action_en"]
                ),
                "safe_attempted_action_tr": str(
                    translated["safe_attempted_action_tr"]
                ),
                "risky_attempted_action_en": str(
                    source["risky_attempted_action_en"]
                ),
                "risky_attempted_action_tr": str(
                    translated["risky_attempted_action_tr"]
                ),
                "human_review_decision": "",
                "reviewer_note": "",
            }
        )

    return review_rows


def write_review_csv(rows: list[dict[str, str]]) -> None:
    REVIEW_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)

    # LF line endings intentionally avoid git diff --check CRLF warnings.
    with REVIEW_CSV_PATH.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=list(rows[0].keys()),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    source_sha_before = sha256_file(SOURCE_PATH)
    translated_sha_before = sha256_file(TRANSLATED_PATH)

    source_rows = load_jsonl(SOURCE_PATH)
    translated_rows = load_jsonl(TRANSLATED_PATH)

    if len(source_rows) != EXPECTED_ROWS:
        raise ValueError(
            f"Expected {EXPECTED_ROWS} source rows, "
            f"found {len(source_rows)}."
        )

    if len(translated_rows) != EXPECTED_ROWS:
        raise ValueError(
            f"Expected {EXPECTED_ROWS} translated rows, "
            f"found {len(translated_rows)}."
        )

    validate_unique_pair_ids(source_rows, "source")
    validate_unique_pair_ids(translated_rows, "translated")

    source_by_pair = {
        str(row["pair_id"]): row
        for row in source_rows
    }
    translated_by_pair = {
        str(row["pair_id"]): row
        for row in translated_rows
    }

    if set(source_by_pair) != set(translated_by_pair):
        raise ValueError(
            "Pair-ID mismatch between source and translated files."
        )

    source_order = [
        int(row["batch_order"])
        for row in source_rows
    ]
    translated_order = [
        int(row["batch_order"])
        for row in translated_rows
    ]

    if source_order != EXPECTED_BATCH_ORDER:
        raise ValueError(
            f"Unexpected source batch order: {source_order}"
        )

    if translated_order != EXPECTED_BATCH_ORDER:
        raise ValueError(
            f"Unexpected translated batch order: {translated_order}"
        )

    split_counts = Counter(
        str(row["split"]) for row in translated_rows
    )
    if dict(split_counts) != EXPECTED_SPLITS:
        raise ValueError(
            f"Unexpected split counts: {dict(split_counts)}"
        )

    issues_by_pair: dict[str, list[str]] = {}

    immutable_top_level_fields = (
        "pair_id",
        "suite",
        "split",
        "session_group_id",
        "same_tool_minimal_pair",
        "safe_row_id",
        "risky_row_id",
        "source_language",
        "target_language",
        "translation_mode",
        "policy_template_id",
        "protected_agent_context",
        "protected_source",
        "protected_context_bindings",
        "global_order",
        "translation_batch_id",
        "batch_order",
        "translation_rules",
    )

    for source in source_rows:
        pair_id = str(source["pair_id"])
        translated = translated_by_pair[pair_id]
        issues: list[str] = []

        for field in immutable_top_level_fields:
            if source.get(field) != translated.get(field):
                issues.append(
                    f"immutable field changed: {field}"
                )

        if (
            translated.get("translation_batch_id")
            != EXPECTED_BATCH_ID
        ):
            issues.append(
                "unexpected translation_batch_id"
            )

        if (
            translated.get("translation_status")
            != "translated_pending_human_review"
        ):
            issues.append(
                "unexpected translation_status"
            )

        if translated.get("human_review_decision") not in {"", None}:
            issues.append(
                "human_review_decision must remain empty"
            )

        if translated.get("reviewer_note") not in {"", None}:
            issues.append(
                "reviewer_note must remain empty"
            )

        for en_field, tr_field in zip(
            ENGLISH_FIELDS,
            TRANSLATED_FIELDS,
        ):
            source_text = str(source.get(en_field, ""))
            translated_text = str(translated.get(tr_field, ""))

            if not translated_text.strip():
                issues.append(f"{tr_field}: empty translation")
                continue

            issues.extend(
                validate_preserved_tokens(
                    pair_id,
                    source_text,
                    translated_text,
                    tr_field,
                )
            )

            if tr_field in {
                "user_authorization_tr",
                "safe_attempted_action_tr",
                "risky_attempted_action_tr",
            }:
                issues.extend(
                    validate_structured_contract(
                        source_text,
                        translated_text,
                        tr_field,
                    )
                )

        issues_by_pair[pair_id] = issues

    review_rows = make_review_rows(
        source_rows,
        translated_by_pair,
        issues_by_pair,
    )
    write_review_csv(review_rows)

    passed_pairs = [
        pair_id
        for pair_id, issues in issues_by_pair.items()
        if not issues
    ]
    attention_pairs = [
        pair_id
        for pair_id, issues in issues_by_pair.items()
        if issues
    ]

    source_sha_after = sha256_file(SOURCE_PATH)
    translated_sha_after = sha256_file(TRANSLATED_PATH)

    if source_sha_before != source_sha_after:
        raise RuntimeError("Source artifact was modified.")

    if translated_sha_before != translated_sha_after:
        raise RuntimeError("Translated artifact was modified.")

    report = {
        "artifact_version": "v0.2.1",
        "batch_id": EXPECTED_BATCH_ID,
        "row_count": len(translated_rows),
        "split_counts": dict(split_counts),
        "passed_pair_count": len(passed_pairs),
        "attention_pair_count": len(attention_pairs),
        "passed_pairs": passed_pairs,
        "attention_pairs": attention_pairs,
        "issues_by_pair": issues_by_pair,
        "batch_order_valid": True,
        "duplicate_pair_ids": {
            "source": 0,
            "translated": 0,
        },
        "pair_id_alignment": True,
        "source_artifact": {
            "path": str(SOURCE_PATH),
            "sha256_before": source_sha_before,
            "sha256_after": source_sha_after,
            "modified": False,
        },
        "translated_artifact": {
            "path": str(TRANSLATED_PATH),
            "sha256_before": translated_sha_before,
            "sha256_after": translated_sha_after,
            "modified": False,
        },
        "review_csv": str(REVIEW_CSV_PATH),
        "test_rows": 0,
        "validation_result": (
            "passed"
            if not attention_pairs
            else "attention_required"
        ),
    }

    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("=" * 80)
    print(
        "AGENTDOJO TURKISH BATCH 004 "
        "AUTOMATIC VALIDATION v0.2.1"
    )
    print("=" * 80)
    print()
    print("Rows:", len(translated_rows))
    print("Splits:", dict(split_counts))
    print("Passed pairs:", len(passed_pairs))
    print("Attention pairs:", len(attention_pairs))
    print(
        "Issue count:",
        sum(len(value) for value in issues_by_pair.values()),
    )
    print("Batch order valid: yes")
    print("Duplicate source pair IDs: 0")
    print("Duplicate translated pair IDs: 0")
    print("Pair-ID alignment: yes")
    print("Source artifact modified: no")
    print("Translated artifact modified: no")
    print("Test rows: 0")
    print()
    print("Review CSV:", REVIEW_CSV_PATH)
    print("Report:", REPORT_PATH)
    print()

    if attention_pairs:
        print("Pairs requiring attention:")
        for pair_id in attention_pairs:
            print(f"  {pair_id}")
            for issue in issues_by_pair[pair_id]:
                print(f"    - {issue}")
        print()
        print("Automatic validation: ATTENTION REQUIRED")
    else:
        print("Automatic validation: PASSED")


if __name__ == "__main__":
    main()

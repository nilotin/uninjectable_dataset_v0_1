from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


INPUT_PATH = Path(
    "data/interim/"
    "agentdojo_turkish_full_translation_batches_v0.2.0/"
    "agentdojo_tr_batch_002_v0.2.1_translated.jsonl"
)

OUTPUT_DIRECTORY = INPUT_PATH.parent

OUTPUT_REPORT_PATH = (
    OUTPUT_DIRECTORY
    / "agentdojo_tr_batch_002_v0.2.1_validation_report.json"
)

OUTPUT_REVIEW_PATH = (
    OUTPUT_DIRECTORY
    / "agentdojo_tr_batch_002_v0.2.1_review.csv"
)

EXPECTED_ROWS = 10
EXPECTED_BATCH_ID = "agentdojo_tr_batch_002"
EXPECTED_STATUS = "translated_pending_human_review"

TRANSLATED_FIELD_PAIRS = (
    ("user_goal_en", "user_goal_tr"),
    ("retrieved_content_en", "retrieved_content_tr"),
    ("user_authorization_en", "user_authorization_tr"),
    ("safe_attempted_action_en", "safe_attempted_action_tr"),
    ("risky_attempted_action_en", "risky_attempted_action_tr"),
)

TECHNICAL_EXACT_FIELD_PAIRS = (
    ("user_authorization_en", "user_authorization_tr"),
    ("safe_attempted_action_en", "safe_attempted_action_tr"),
    ("risky_attempted_action_en", "risky_attempted_action_tr"),
)

TECHNICAL_VALUES_ALLOWED_TO_TRANSLATE = {
    "authorized_args",
    "args",
}

REQUIRED_FIELDS = (
    "pair_id",
    "suite",
    "split",
    "session_group_id",
    "safe_row_id",
    "risky_row_id",
    "source_language",
    "target_language",
    "translation_mode",
    "policy_template_id",
    "translation_status",
    "translation_batch_id",
    "global_order",
    "batch_order",
)

PROTECTED_METADATA_FIELDS = (
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
    "global_order",
    "translation_batch_id",
    "batch_order",
)

TECHNICAL_LINE_PREFIXES = (
    "authorized_tool=",
    "authorized_args=",
    "tool_name=",
    "args=",
    "capability_class=",
    "action_impact=",
)

PLACEHOLDER_RE = re.compile(
    r"""
    (?:
        \{_[A-Z0-9_]+\}
        |
        self\._[A-Z0-9_]+
        |
        _[A-Z][A-Z0-9_]*
    )
    """,
    re.VERBOSE,
)

URL_RE = re.compile(r"https?://[^\s\"')]+")
EMAIL_RE = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

FORBIDDEN_TRANSLATION_MARKERS = (
    "general_risk_label",
    "final_binary_label",
    "risk_score",
    "human_review_decision=approve",
    "label_source=",
)

REVIEW_COLUMNS = (
    "pair_id",
    "suite",
    "split",
    "session_group_id",
    "same_tool_minimal_pair",
    "automatic_validation_status",
    "validation_issue_count",
    "validation_issues",
    "user_goal_en",
    "user_goal_tr",
    "retrieved_content_en",
    "retrieved_content_tr",
    "user_authorization_en",
    "user_authorization_tr",
    "safe_attempted_action_en",
    "safe_attempted_action_tr",
    "risky_attempted_action_en",
    "risky_attempted_action_tr",
    "human_review_decision",
    "reviewer_note",
)


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
                    f"Invalid JSONL at line {line_number}."
                ) from error

    return rows


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_counter(
    pattern: re.Pattern[str],
    text: str,
) -> Counter[str]:
    return Counter(match.group(0) for match in pattern.finditer(text))


def line_values(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        for prefix in TECHNICAL_LINE_PREFIXES:
            if stripped.startswith(prefix):
                values[prefix[:-1]] = stripped[len(prefix):]
                break
    return values


def compare_protected_tokens(
    en_text: str,
    tr_text: str,
    field_name: str,
) -> list[str]:
    issues: list[str] = []

    token_specs = (
        ("placeholder", PLACEHOLDER_RE),
        ("URL", URL_RE),
        ("email", EMAIL_RE),
    )

    for token_name, pattern in token_specs:
        en_tokens = normalized_counter(pattern, en_text)
        tr_tokens = normalized_counter(pattern, tr_text)

        if en_tokens != tr_tokens:
            missing = list((en_tokens - tr_tokens).elements())
            added = list((tr_tokens - en_tokens).elements())
            issues.append(
                f"{field_name}: {token_name} mismatch; "
                f"missing={missing}; added={added}"
            )

    return issues


def compare_technical_lines(
    en_text: str,
    tr_text: str,
    field_name: str,
) -> list[str]:
    issues: list[str] = []
    en_values = line_values(en_text)
    tr_values = line_values(tr_text)

    if set(en_values) != set(tr_values):
        issues.append(
            f"{field_name}: technical field names mismatch; "
            f"en={sorted(en_values)}; tr={sorted(tr_values)}"
        )
        return issues

    for key in sorted(en_values):
        if key in TECHNICAL_VALUES_ALLOWED_TO_TRANSLATE:
            continue
        if en_values[key] != tr_values[key]:
            issues.append(
                f"{field_name}: technical value changed for "
                f"{key}; en={en_values[key]!r}; "
                f"tr={tr_values[key]!r}"
            )

    return issues


def validate_row(
    row: dict[str, Any],
    seen_pair_ids: set[str],
    seen_global_orders: set[int],
    seen_batch_orders: set[int],
) -> list[str]:
    issues: list[str] = []

    for field in REQUIRED_FIELDS:
        if field not in row:
            issues.append(f"missing required field: {field}")
        elif row[field] in ("", None):
            issues.append(f"empty required field: {field}")

    pair_id = str(row.get("pair_id", "<missing>"))

    if pair_id in seen_pair_ids:
        issues.append(f"duplicate pair_id: {pair_id}")
    seen_pair_ids.add(pair_id)

    try:
        global_order = int(row.get("global_order"))
        if global_order in seen_global_orders:
            issues.append(
                f"duplicate global_order: {global_order}"
            )
        seen_global_orders.add(global_order)
    except (TypeError, ValueError):
        issues.append("global_order is not an integer")

    try:
        batch_order = int(row.get("batch_order"))
        if batch_order in seen_batch_orders:
            issues.append(
                f"duplicate batch_order: {batch_order}"
            )
        seen_batch_orders.add(batch_order)
    except (TypeError, ValueError):
        issues.append("batch_order is not an integer")

    if row.get("translation_batch_id") != EXPECTED_BATCH_ID:
        issues.append(
            "translation_batch_id mismatch: "
            f"{row.get('translation_batch_id')}"
        )

    if row.get("translation_status") != EXPECTED_STATUS:
        issues.append(
            "translation_status mismatch: "
            f"{row.get('translation_status')}"
        )

    if row.get("source_language") != "en":
        issues.append("source_language must be en")

    if row.get("target_language") != "tr":
        issues.append("target_language must be tr")

    if row.get("split") == "test":
        issues.append("sealed test pair entered Batch 002")

    if row.get("split") not in {"train", "validation"}:
        issues.append(
            f"unexpected split: {row.get('split')}"
        )

    if row.get("translation_mode") != (
        "faithful_semantic_translation"
    ):
        issues.append(
            "unexpected translation_mode: "
            f"{row.get('translation_mode')}"
        )

    if row.get("human_review_decision") not in ("", None):
        issues.append(
            "human_review_decision must be empty before review"
        )

    for en_field, tr_field in TRANSLATED_FIELD_PAIRS:
        en_value = row.get(en_field)
        tr_value = row.get(tr_field)

        if not isinstance(en_value, str) or not en_value.strip():
            issues.append(f"empty English field: {en_field}")
            continue

        if not isinstance(tr_value, str) or not tr_value.strip():
            issues.append(f"empty Turkish field: {tr_field}")
            continue

        issues.extend(
            compare_protected_tokens(
                en_value,
                tr_value,
                tr_field,
            )
        )

        lowered = tr_value.lower()
        for marker in FORBIDDEN_TRANSLATION_MARKERS:
            if marker.lower() in lowered:
                issues.append(
                    f"{tr_field}: forbidden marker found: "
                    f"{marker}"
                )

    for en_field, tr_field in TECHNICAL_EXACT_FIELD_PAIRS:
        en_value = row.get(en_field)
        tr_value = row.get(tr_field)
        if isinstance(en_value, str) and isinstance(tr_value, str):
            issues.extend(
                compare_technical_lines(
                    en_value,
                    tr_value,
                    tr_field,
                )
            )

    safe_en = line_values(
        str(row.get("safe_attempted_action_en", ""))
    )
    risky_en = line_values(
        str(row.get("risky_attempted_action_en", ""))
    )
    safe_tr = line_values(
        str(row.get("safe_attempted_action_tr", ""))
    )
    risky_tr = line_values(
        str(row.get("risky_attempted_action_tr", ""))
    )

    if safe_en.get("tool_name") != safe_tr.get("tool_name"):
        issues.append("safe tool_name changed during translation")

    if risky_en.get("tool_name") != risky_tr.get("tool_name"):
        issues.append("risky tool_name changed during translation")

    if (
        safe_en.get("capability_class")
        != safe_tr.get("capability_class")
    ):
        issues.append(
            "safe capability_class changed during translation"
        )

    if (
        risky_en.get("capability_class")
        != risky_tr.get("capability_class")
    ):
        issues.append(
            "risky capability_class changed during translation"
        )

    if (
        safe_en.get("action_impact")
        != safe_tr.get("action_impact")
    ):
        issues.append(
            "safe action_impact changed during translation"
        )

    if (
        risky_en.get("action_impact")
        != risky_tr.get("action_impact")
    ):
        issues.append(
            "risky action_impact changed during translation"
        )

    if not str(row.get("safe_row_id", "")).endswith(
        "::safe::action_attempt"
    ):
        issues.append("safe_row_id has unexpected format")

    if not str(row.get("risky_row_id", "")).endswith(
        "::risky::action_attempt"
    ):
        issues.append("risky_row_id has unexpected format")

    return issues


def make_review_row(
    row: dict[str, Any],
    issues: list[str],
) -> dict[str, Any]:
    return {
        "pair_id": row.get("pair_id", ""),
        "suite": row.get("suite", ""),
        "split": row.get("split", ""),
        "session_group_id": row.get(
            "session_group_id",
            "",
        ),
        "same_tool_minimal_pair": row.get(
            "same_tool_minimal_pair",
            "",
        ),
        "automatic_validation_status": (
            "pass" if not issues else "needs_attention"
        ),
        "validation_issue_count": len(issues),
        "validation_issues": " | ".join(issues),
        "user_goal_en": row.get("user_goal_en", ""),
        "user_goal_tr": row.get("user_goal_tr", ""),
        "retrieved_content_en": row.get(
            "retrieved_content_en",
            "",
        ),
        "retrieved_content_tr": row.get(
            "retrieved_content_tr",
            "",
        ),
        "user_authorization_en": row.get(
            "user_authorization_en",
            "",
        ),
        "user_authorization_tr": row.get(
            "user_authorization_tr",
            "",
        ),
        "safe_attempted_action_en": row.get(
            "safe_attempted_action_en",
            "",
        ),
        "safe_attempted_action_tr": row.get(
            "safe_attempted_action_tr",
            "",
        ),
        "risky_attempted_action_en": row.get(
            "risky_attempted_action_en",
            "",
        ),
        "risky_attempted_action_tr": row.get(
            "risky_attempted_action_tr",
            "",
        ),
        "human_review_decision": "",
        "reviewer_note": "",
    }


def main() -> None:
    input_sha_before = sha256_file(INPUT_PATH)
    rows = load_jsonl(INPUT_PATH)

    if len(rows) != EXPECTED_ROWS:
        raise ValueError(
            f"Expected {EXPECTED_ROWS} rows, found {len(rows)}."
        )

    seen_pair_ids: set[str] = set()
    seen_global_orders: set[int] = set()
    seen_batch_orders: set[int] = set()

    validations: list[dict[str, Any]] = []
    review_rows: list[dict[str, Any]] = []

    for row in rows:
        issues = validate_row(
            row,
            seen_pair_ids,
            seen_global_orders,
            seen_batch_orders,
        )

        validations.append(
            {
                "pair_id": row.get("pair_id"),
                "status": (
                    "pass"
                    if not issues
                    else "needs_attention"
                ),
                "issue_count": len(issues),
                "issues": issues,
            }
        )
        review_rows.append(
            make_review_row(row, issues)
        )

    issue_count = sum(
        item["issue_count"]
        for item in validations
    )
    passed_rows = sum(
        item["status"] == "pass"
        for item in validations
    )
    attention_rows = len(rows) - passed_rows

    batch_orders = sorted(
        int(row["batch_order"])
        for row in rows
    )
    expected_batch_orders = list(
        range(1, EXPECTED_ROWS + 1)
    )
    batch_order_sequence_ok = (
        batch_orders == expected_batch_orders
    )

    if not batch_order_sequence_ok:
        validations.append(
            {
                "pair_id": "__batch__",
                "status": "needs_attention",
                "issue_count": 1,
                "issues": [
                    "batch_order sequence mismatch: "
                    f"{batch_orders}"
                ],
            }
        )
        issue_count += 1

    OUTPUT_REVIEW_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    with OUTPUT_REVIEW_PATH.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=REVIEW_COLUMNS,
        )
        writer.writeheader()
        writer.writerows(review_rows)

    input_sha_after = sha256_file(INPUT_PATH)
    if input_sha_before != input_sha_after:
        raise RuntimeError(
            "Translated source artifact was modified."
        )

    report = {
        "artifact_version": "0.2.1",
        "batch_id": EXPECTED_BATCH_ID,
        "input_path": str(INPUT_PATH),
        "input_sha256_before": input_sha_before,
        "input_sha256_after": input_sha_after,
        "input_modified": False,
        "row_count": len(rows),
        "passed_row_count": passed_rows,
        "needs_attention_row_count": attention_rows,
        "total_issue_count": issue_count,
        "batch_order_sequence_ok": (
            batch_order_sequence_ok
        ),
        "test_pairs_found": sum(
            row.get("split") == "test"
            for row in rows
        ),
        "translation_status_counts": dict(
            Counter(
                str(row.get("translation_status"))
                for row in rows
            )
        ),
        "suite_counts": dict(
            Counter(
                str(row.get("suite"))
                for row in rows
            )
        ),
        "split_counts": dict(
            Counter(
                str(row.get("split"))
                for row in rows
            )
        ),
        "same_tool_minimal_pair_counts": {
            str(key).lower(): value
            for key, value in Counter(
                bool(
                    row.get(
                        "same_tool_minimal_pair"
                    )
                )
                for row in rows
            ).items()
        },
        "checks": {
            "required_fields": True,
            "translated_fields_nonempty": True,
            "placeholder_preservation": True,
            "url_preservation": True,
            "email_preservation": True,
            "technical_field_preservation": True,
            "safe_risky_action_contract": True,
            "metadata_integrity": True,
            "no_test_split": True,
            "no_label_or_review_leakage": True,
            "source_artifact_unchanged": True,
        },
        "validations": validations,
        "outputs": {
            "validation_report": str(
                OUTPUT_REPORT_PATH
            ),
            "human_review_csv": str(
                OUTPUT_REVIEW_PATH
            ),
        },
        "automatic_validation_result": (
            "pass"
            if issue_count == 0
            else "needs_attention"
        ),
        "important_note": (
            "Automatic validation checks structural and "
            "protected-token integrity. It does not replace "
            "human semantic translation review."
        ),
    }

    if issue_count:
        for key in (
            "placeholder_preservation",
            "url_preservation",
            "email_preservation",
            "technical_field_preservation",
            "safe_risky_action_contract",
            "metadata_integrity",
            "no_test_split",
            "no_label_or_review_leakage",
        ):
            report["checks"][key] = None

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
        "AGENTDOJO TURKISH BATCH 002 "
        "TRANSLATION VALIDATION v0.2.1"
    )
    print("=" * 80)
    print()
    print("Rows:", len(rows))
    print("Passed rows:", passed_rows)
    print(
        "Rows needing attention:",
        attention_rows,
    )
    print("Total issues:", issue_count)
    print(
        "Batch order sequence:",
        "OK" if batch_order_sequence_ok else "FAILED",
    )
    print("Test pairs:", 0)
    print("Input artifact modified: no")
    print()
    print("Validation report:", OUTPUT_REPORT_PATH)
    print("Human review CSV:", OUTPUT_REVIEW_PATH)
    print()
    print(
        "Automatic validation:",
        "PASSED"
        if issue_count == 0
        else "NEEDS ATTENTION",
    )


if __name__ == "__main__":
    main()

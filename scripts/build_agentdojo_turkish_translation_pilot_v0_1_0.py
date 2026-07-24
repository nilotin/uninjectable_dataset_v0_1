from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


STRUCTURED_POOL_PATH = Path(
    "data/processed/"
    "agentdojo_contextual_action_attempt_labeled_pool_v0.1.5.jsonl"
)

ASSIGNMENTS_PATH = Path(
    "data/processed/"
    "agentdojo_group_aware_split_v0.1.5/"
    "agentdojo_group_split_assignments_v0.1.5.jsonl"
)

DATASET_MANIFEST_PATH = Path(
    "data/processed/"
    "agentdojo_v0.1.5_sha256.txt"
)

SPLIT_MANIFEST_PATH = Path(
    "data/processed/"
    "agentdojo_group_aware_split_v0.1.5/"
    "agentdojo_group_split_v0.1.5_sha256.txt"
)


OUTPUT_JSONL_PATH = Path(
    "data/interim/"
    "agentdojo_turkish_translation_pilot_queue_v0.1.0.jsonl"
)

OUTPUT_CSV_PATH = Path(
    "data/interim/"
    "agentdojo_turkish_translation_pilot_queue_v0.1.0.csv"
)

POLICY_QUEUE_PATH = Path(
    "data/interim/"
    "agentdojo_turkish_policy_template_queue_v0.1.0.jsonl"
)

REPORT_PATH = Path(
    "data/interim/"
    "agentdojo_turkish_translation_pilot_v0.1.0_report.json"
)


SUITES = (
    "banking",
    "slack",
    "travel",
    "workspace",
)

TARGET_PER_SUITE = {
    "train": 2,
    "validation": 1,
}

EXPECTED_PAIR_COUNT = 97
EXPECTED_ROW_COUNT = 194
EXPECTED_PILOT_PAIR_COUNT = 12
EXPECTED_PILOT_RUNTIME_ROW_COUNT = 24

SELECTION_SEED = (
    "agentdojo-turkish-translation-pilot-v0.1.0"
)

SHARED_SECTIONS = (
    "USER_GOAL",
    "AGENT_CONTEXT",
    "SOURCE",
    "CONTEXT_BINDINGS",
    "RETRIEVED_CONTENT",
    "USER_AUTHORIZATION",
    "POLICY_CONTEXT",
)

TRANSLATABLE_SECTIONS = (
    "USER_GOAL",
    "RETRIEVED_CONTENT",
    "USER_AUTHORIZATION",
)

PROTECTED_SECTIONS = (
    "AGENT_CONTEXT",
    "SOURCE",
    "CONTEXT_BINDINGS",
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(
            f"Missing JSONL file: {path}"
        )

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

    with path.open("w", encoding="utf-8") as file:
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
        while True:
            chunk = file.read(1024 * 1024)

            if not chunk:
                break

            digest.update(chunk)

    return digest.hexdigest()


def verify_manifest(path: Path) -> int:
    if not path.exists():
        raise FileNotFoundError(
            f"Missing SHA-256 manifest: {path}"
        )

    verified = 0

    for line in path.read_text(
        encoding="utf-8"
    ).splitlines():
        line = line.strip()

        if not line:
            continue

        parts = line.split(None, 1)

        if len(parts) != 2:
            raise ValueError(
                f"Invalid manifest line: {line}"
            )

        expected_hash, raw_path = parts
        artifact_path = Path(raw_path.strip())

        if not artifact_path.exists():
            raise FileNotFoundError(
                f"Manifest artifact missing: "
                f"{artifact_path}"
            )

        actual_hash = sha256_file(
            artifact_path
        )

        if actual_hash != expected_hash:
            raise ValueError(
                "Checkpoint validation failed:\n"
                f"Artifact: {artifact_path}\n"
                f"Expected: {expected_hash}\n"
                f"Actual:   {actual_hash}"
            )

        verified += 1

    return verified


def variant_name(row: dict[str, Any]) -> str:
    variant = row.get("variant")

    if isinstance(variant, dict):
        variant = variant.get("name")

    return str(variant)


def same_tool_flag(row: dict[str, Any]) -> bool:
    return bool(
        row.get(
            "provenance",
            {},
        ).get(
            "same_tool_minimal_pair",
            False,
        )
    )


def extract_sections(text: str) -> dict[str, str]:
    pattern = re.compile(
        r"^\[([A-Z_]+)\]\n"
        r"(.*?)"
        r"(?=^\[[A-Z_]+\]\n|\Z)",
        flags=re.MULTILINE | re.DOTALL,
    )

    sections = {
        match.group(1): match.group(2).strip()
        for match in pattern.finditer(text)
    }

    if not sections:
        raise ValueError(
            "No serialized model-input sections found."
        )

    return sections


def stable_rank(pair_id: str) -> str:
    return hashlib.sha256(
        (
            SELECTION_SEED
            + "|"
            + pair_id
        ).encode("utf-8")
    ).hexdigest()


def policy_template_id(policy_text: str) -> str:
    digest = hashlib.sha256(
        policy_text.encode("utf-8")
    ).hexdigest()[:12]

    return f"agentdojo_policy_{digest}"


def write_csv(
    path: Path,
    rows: list[dict[str, Any]],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fieldnames = [
        "pilot_order",
        "pair_id",
        "suite",
        "split",
        "session_group_id",
        "same_tool_minimal_pair",
        "safe_row_id",
        "risky_row_id",
        "policy_template_id",
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
        "protected_agent_context",
        "protected_source",
        "protected_context_bindings",
        "translation_status",
        "human_review_decision",
        "reviewer_note",
    ]

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

        for row in rows:
            writer.writerow(
                {
                    field: row.get(field, "")
                    for field in fieldnames
                }
            )


def main() -> None:
    dataset_hashes_before = verify_manifest(
        DATASET_MANIFEST_PATH
    )

    split_hashes_before = verify_manifest(
        SPLIT_MANIFEST_PATH
    )

    structured_rows = load_jsonl(
        STRUCTURED_POOL_PATH
    )

    assignments = load_jsonl(
        ASSIGNMENTS_PATH
    )

    if len(structured_rows) != EXPECTED_ROW_COUNT:
        raise ValueError(
            "Expected 194 structured rows, "
            f"found {len(structured_rows)}."
        )

    assignment_by_pair = {
        str(row["pair_id"]): str(row["split"])
        for row in assignments
    }

    if len(assignment_by_pair) != EXPECTED_PAIR_COUNT:
        raise ValueError(
            "Expected 97 pair assignments, "
            f"found {len(assignment_by_pair)}."
        )

    rows_by_pair: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)

    for row in structured_rows:
        rows_by_pair[
            str(row["pair_id"])
        ].append(row)

    if len(rows_by_pair) != EXPECTED_PAIR_COUNT:
        raise ValueError(
            "Expected 97 structured pairs, "
            f"found {len(rows_by_pair)}."
        )

    pair_records: list[dict[str, Any]] = []

    for pair_id, pair_rows in rows_by_pair.items():
        if len(pair_rows) != 2:
            raise ValueError(
                f"{pair_id} has "
                f"{len(pair_rows)} rows."
            )

        safe_row = next(
            (
                row
                for row in pair_rows
                if variant_name(row) == "safe"
            ),
            None,
        )

        risky_row = next(
            (
                row
                for row in pair_rows
                if variant_name(row) == "risky"
            ),
            None,
        )

        if safe_row is None or risky_row is None:
            raise ValueError(
                f"{pair_id} does not contain "
                "one safe and one risky row."
            )

        safe_sections = extract_sections(
            str(
                safe_row[
                    "model_input"
                ][
                    "text"
                ]
            )
        )

        risky_sections = extract_sections(
            str(
                risky_row[
                    "model_input"
                ][
                    "text"
                ]
            )
        )

        for section in SHARED_SECTIONS:
            if section not in safe_sections:
                raise ValueError(
                    f"{pair_id} safe row missing "
                    f"{section}."
                )

            if section not in risky_sections:
                raise ValueError(
                    f"{pair_id} risky row missing "
                    f"{section}."
                )

            if (
                safe_sections[section]
                !=
                risky_sections[section]
            ):
                raise ValueError(
                    f"{pair_id} shared section "
                    f"differs: {section}"
                )

        if (
            "ATTEMPTED_ACTION"
            not in safe_sections
            or
            "ATTEMPTED_ACTION"
            not in risky_sections
        ):
            raise ValueError(
                f"{pair_id} missing attempted action."
            )

        split = assignment_by_pair[pair_id]

        pair_records.append(
            {
                "pair_id": pair_id,
                "suite": str(safe_row["suite"]),
                "split": split,
                "session_group_id": str(
                    safe_row["session_group_id"]
                ),
                "same_tool_minimal_pair": (
                    same_tool_flag(safe_row)
                ),
                "safe_row_id": str(
                    safe_row["row_id"]
                ),
                "risky_row_id": str(
                    risky_row["row_id"]
                ),
                "safe_sections": safe_sections,
                "risky_sections": risky_sections,
            }
        )

    candidates: dict[
        tuple[str, str],
        list[dict[str, Any]],
    ] = defaultdict(list)

    for record in pair_records:
        if record["split"] not in {
            "train",
            "validation",
        }:
            continue

        candidates[
            (
                record["suite"],
                record["split"],
            )
        ].append(record)

    selected_records: list[dict[str, Any]] = []

    for suite in SUITES:
        for split, target_count in (
            TARGET_PER_SUITE.items()
        ):
            available = candidates[
                (
                    suite,
                    split,
                )
            ]

            if len(available) < target_count:
                raise ValueError(
                    f"Not enough candidates for "
                    f"{suite}/{split}. "
                    f"Needed {target_count}, "
                    f"found {len(available)}."
                )

            ranked = sorted(
                available,
                key=lambda record: (
                    not bool(
                        record[
                            "same_tool_minimal_pair"
                        ]
                    ),
                    stable_rank(
                        str(record["pair_id"])
                    ),
                ),
            )

            selected_records.extend(
                ranked[:target_count]
            )

    if (
        len(selected_records)
        !=
        EXPECTED_PILOT_PAIR_COUNT
    ):
        raise ValueError(
            "Expected 12 selected pilot pairs, "
            f"found {len(selected_records)}."
        )

    selected_pair_ids = {
        str(record["pair_id"])
        for record in selected_records
    }

    if len(selected_pair_ids) != 12:
        raise ValueError(
            "Duplicate pilot pair selection."
        )

    if any(
        record["split"] == "test"
        for record in selected_records
    ):
        raise ValueError(
            "Test split entered translation pilot."
        )

    selected_records.sort(
        key=lambda record: (
            SUITES.index(
                str(record["suite"])
            ),
            (
                0
                if record["split"] == "train"
                else 1
            ),
            stable_rank(
                str(record["pair_id"])
            ),
        )
    )

    policy_templates: dict[
        str,
        dict[str, Any],
    ] = {}

    queue_rows: list[dict[str, Any]] = []

    translation_rules = [
        (
            "Section tags and key names must "
            "remain unchanged."
        ),
        (
            "Translate natural-language content "
            "faithfully into Turkish."
        ),
        (
            "Do not translate tool names, IDs, "
            "URLs, email addresses, file names, "
            "dates, amounts, enum values, variable "
            "names, JSON keys, Python expressions "
            "or placeholders."
        ),
        (
            "Do not localize entities during this "
            "phase. For example, New York must not "
            "be changed to İstanbul and USD must not "
            "be changed to TL."
        ),
        (
            "Safe and risky attempted actions must "
            "retain exactly the same operational "
            "meaning as their English sources."
        ),
    ]

    for pilot_order, record in enumerate(
        selected_records,
        start=1,
    ):
        safe_sections = record["safe_sections"]
        risky_sections = record["risky_sections"]

        policy_text = safe_sections[
            "POLICY_CONTEXT"
        ]

        template_id = policy_template_id(
            policy_text
        )

        policy_templates.setdefault(
            template_id,
            {
                "policy_template_id": template_id,
                "policy_context_en": policy_text,
                "policy_context_tr": "",
                "translation_status": (
                    "awaiting_translation"
                ),
                "human_review_decision": "",
                "reviewer_note": "",
            },
        )

        queue_rows.append(
            {
                "pilot_order": pilot_order,
                "pair_id": record["pair_id"],
                "suite": record["suite"],
                "split": record["split"],
                "session_group_id": (
                    record["session_group_id"]
                ),
                "same_tool_minimal_pair": (
                    record[
                        "same_tool_minimal_pair"
                    ]
                ),
                "safe_row_id": record["safe_row_id"],
                "risky_row_id": (
                    record["risky_row_id"]
                ),
                "source_language": "en",
                "target_language": "tr",
                "translation_mode": (
                    "faithful_semantic_translation"
                ),
                "translation_rules": (
                    translation_rules
                ),
                "policy_template_id": template_id,
                "user_goal_en": safe_sections[
                    "USER_GOAL"
                ],
                "user_goal_tr": "",
                "retrieved_content_en": (
                    safe_sections[
                        "RETRIEVED_CONTENT"
                    ]
                ),
                "retrieved_content_tr": "",
                "user_authorization_en": (
                    safe_sections[
                        "USER_AUTHORIZATION"
                    ]
                ),
                "user_authorization_tr": "",
                "safe_attempted_action_en": (
                    safe_sections[
                        "ATTEMPTED_ACTION"
                    ]
                ),
                "safe_attempted_action_tr": "",
                "risky_attempted_action_en": (
                    risky_sections[
                        "ATTEMPTED_ACTION"
                    ]
                ),
                "risky_attempted_action_tr": "",
                "protected_agent_context": (
                    safe_sections[
                        "AGENT_CONTEXT"
                    ]
                ),
                "protected_source": (
                    safe_sections["SOURCE"]
                ),
                "protected_context_bindings": (
                    safe_sections[
                        "CONTEXT_BINDINGS"
                    ]
                ),
                "translation_status": (
                    "awaiting_translation"
                ),
                "human_review_decision": "",
                "reviewer_note": "",
            }
        )

    policy_rows = sorted(
        policy_templates.values(),
        key=lambda row: row[
            "policy_template_id"
        ],
    )

    write_jsonl(
        OUTPUT_JSONL_PATH,
        queue_rows,
    )

    write_csv(
        OUTPUT_CSV_PATH,
        queue_rows,
    )

    write_jsonl(
        POLICY_QUEUE_PATH,
        policy_rows,
    )

    suite_counts = Counter(
        row["suite"]
        for row in queue_rows
    )

    split_counts = Counter(
        row["split"]
        for row in queue_rows
    )

    same_tool_count = sum(
        bool(
            row["same_tool_minimal_pair"]
        )
        for row in queue_rows
    )

    dataset_hashes_after = verify_manifest(
        DATASET_MANIFEST_PATH
    )

    split_hashes_after = verify_manifest(
        SPLIT_MANIFEST_PATH
    )

    report = {
        "artifact_version": "0.1.0",
        "source_dataset": (
            "agentdojo_contextual_action_attempt_"
            "labeled_pool_v0.1.5"
        ),
        "translation_mode": (
            "faithful_semantic_translation"
        ),
        "pilot_pair_count": len(queue_rows),
        "eventual_runtime_row_count": (
            len(queue_rows) * 2
        ),
        "suite_counts": dict(
            sorted(suite_counts.items())
        ),
        "split_counts": dict(
            sorted(split_counts.items())
        ),
        "test_pair_count": 0,
        "same_tool_pair_count": (
            same_tool_count
        ),
        "unique_policy_template_count": (
            len(policy_rows)
        ),
        "selected_pair_ids": [
            row["pair_id"]
            for row in queue_rows
        ],
        "validation": {
            "dataset_hashes_before": (
                dataset_hashes_before
            ),
            "dataset_hashes_after": (
                dataset_hashes_after
            ),
            "split_hashes_before": (
                split_hashes_before
            ),
            "split_hashes_after": (
                split_hashes_after
            ),
            "source_dataset_modified": False,
            "source_splits_modified": False,
            "test_split_accessed": False,
        },
        "outputs": {
            "translation_queue_jsonl": str(
                OUTPUT_JSONL_PATH
            ),
            "translation_queue_csv": str(
                OUTPUT_CSV_PATH
            ),
            "policy_template_queue": str(
                POLICY_QUEUE_PATH
            ),
        },
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
        "AGENTDOJO TURKISH TRANSLATION "
        "PILOT v0.1.0 CREATED"
    )
    print("=" * 80)
    print()

    print(
        "Selected pilot pairs:",
        len(queue_rows),
    )

    print(
        "Eventual Turkish runtime rows:",
        len(queue_rows) * 2,
    )

    print(
        "Suite counts:",
        dict(sorted(suite_counts.items())),
    )

    print(
        "Split counts:",
        dict(sorted(split_counts.items())),
    )

    print(
        "Test pairs included:",
        0,
    )

    print(
        "Same-tool pilot pairs:",
        same_tool_count,
    )

    print(
        "Unique policy templates:",
        len(policy_rows),
    )

    print()

    print("Selected pairs:")

    for row in queue_rows:
        print(
            f"  {row['pilot_order']:02d}. "
            f"{row['pair_id']} | "
            f"{row['suite']} | "
            f"{row['split']} | "
            f"same_tool="
            f"{row['same_tool_minimal_pair']}"
        )

    print()

    print(
        "Translation queue JSONL:",
        OUTPUT_JSONL_PATH,
    )

    print(
        "Translation queue CSV:",
        OUTPUT_CSV_PATH,
    )

    print(
        "Policy template queue:",
        POLICY_QUEUE_PATH,
    )

    print(
        "Report:",
        REPORT_PATH,
    )

    print()

    print(
        "Source dataset modified: no"
    )

    print(
        "Source split artifacts modified: no"
    )

    print(
        "Test split opened: no"
    )


if __name__ == "__main__":
    main()

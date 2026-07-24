from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any


TRAIN_PATH = Path(
    "data/processed/"
    "agentdojo_group_aware_split_v0.1.5/"
    "agentdojo_contextual_action_attempt_labeled_pool_v0.1.5_train.jsonl"
)

VALIDATION_PATH = Path(
    "data/processed/"
    "agentdojo_group_aware_split_v0.1.5/"
    "agentdojo_contextual_action_attempt_labeled_pool_v0.1.5_validation.jsonl"
)

PILOT_QUEUE_PATH = Path(
    "data/interim/"
    "agentdojo_turkish_translation_pilot_queue_"
    "v0.1.2_human_reviewed.jsonl"
)

PILOT_POLICY_PATH = Path(
    "data/interim/"
    "agentdojo_turkish_policy_template_queue_"
    "v0.1.2_human_reviewed.jsonl"
)


OUTPUT_QUEUE_PATH = Path(
    "data/interim/"
    "agentdojo_turkish_full_translation_queue_v0.2.0.jsonl"
)

OUTPUT_CSV_PATH = Path(
    "data/interim/"
    "agentdojo_turkish_full_translation_queue_v0.2.0.csv"
)

OUTPUT_POLICY_REGISTRY_PATH = Path(
    "data/interim/"
    "agentdojo_turkish_full_policy_registry_v0.2.0.jsonl"
)

OUTPUT_BATCH_DIRECTORY = Path(
    "data/interim/"
    "agentdojo_turkish_full_translation_batches_v0.2.0"
)

OUTPUT_REPORT_PATH = Path(
    "data/interim/"
    "agentdojo_turkish_full_translation_queue_v0.2.0_report.json"
)


EXPECTED_TRAIN_ROWS = 136
EXPECTED_VALIDATION_ROWS = 30

EXPECTED_SOURCE_PAIR_COUNT = 83
EXPECTED_PILOT_PAIR_COUNT = 12
EXPECTED_REMAINING_PAIR_COUNT = 71

EXPECTED_REMAINING_TRAIN_PAIRS = 60
EXPECTED_REMAINING_VALIDATION_PAIRS = 11

EXPECTED_EVENTUAL_RUNTIME_ROWS = 142

BATCH_SIZE = 10

SELECTION_SEED = (
    "agentdojo-turkish-full-translation-"
    "queue-v0.2.0"
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


def write_csv(
    path: Path,
    rows: list[dict[str, Any]],
) -> None:

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fieldnames = [
        "global_order",
        "translation_batch_id",
        "batch_order",
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


def sha256_file(
    path: Path,
) -> str:

    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def stable_rank(
    pair_id: str,
) -> str:

    return hashlib.sha256(
        (
            SELECTION_SEED
            + "|"
            + pair_id
        ).encode("utf-8")
    ).hexdigest()


def policy_template_id(
    policy_text: str,
) -> str:

    digest = hashlib.sha256(
        policy_text.encode("utf-8")
    ).hexdigest()[:12]

    return (
        f"agentdojo_policy_{digest}"
    )


def variant_name(
    row: dict[str, Any],
) -> str:

    variant = row.get(
        "variant"
    )

    if isinstance(
        variant,
        dict,
    ):
        variant = variant.get(
            "name"
        )

    return str(
        variant
    )


def same_tool_flag(
    row: dict[str, Any],
) -> bool:

    return bool(
        row.get(
            "provenance",
            {},
        ).get(
            "same_tool_minimal_pair",
            False,
        )
    )


def extract_sections(
    text: str,
) -> dict[str, str]:

    pattern = re.compile(
        r"^\[([A-Z_]+)\]\n"
        r"(.*?)"
        r"(?=^\[[A-Z_]+\]\n|\Z)",
        flags=re.MULTILINE | re.DOTALL,
    )

    sections = {
        match.group(1): (
            match.group(2).strip()
        )
        for match in pattern.finditer(
            text
        )
    }

    if not sections:
        raise ValueError(
            "No serialized sections found."
        )

    return sections


def main() -> None:

    source_hashes_before = {
        "train": sha256_file(
            TRAIN_PATH
        ),
        "validation": sha256_file(
            VALIDATION_PATH
        ),
        "pilot_queue": sha256_file(
            PILOT_QUEUE_PATH
        ),
        "pilot_policy": sha256_file(
            PILOT_POLICY_PATH
        ),
    }


    train_rows = load_jsonl(
        TRAIN_PATH
    )

    validation_rows = load_jsonl(
        VALIDATION_PATH
    )

    pilot_rows = load_jsonl(
        PILOT_QUEUE_PATH
    )

    approved_policy_rows = load_jsonl(
        PILOT_POLICY_PATH
    )


    if len(train_rows) != EXPECTED_TRAIN_ROWS:
        raise ValueError(
            "Expected 136 train rows, "
            f"found {len(train_rows)}."
        )


    if (
        len(validation_rows)
        !=
        EXPECTED_VALIDATION_ROWS
    ):
        raise ValueError(
            "Expected 30 validation rows, "
            f"found {len(validation_rows)}."
        )


    if (
        len(pilot_rows)
        !=
        EXPECTED_PILOT_PAIR_COUNT
    ):
        raise ValueError(
            "Expected 12 pilot pairs, "
            f"found {len(pilot_rows)}."
        )


    for row in pilot_rows:

        if (
            row.get(
                "human_review_decision"
            )
            !=
            "approve_translation"
        ):
            raise ValueError(
                "Pilot contains a translation "
                "that was not approved."
            )


    pilot_pair_ids = {
        str(row["pair_id"])
        for row in pilot_rows
    }


    if (
        len(pilot_pair_ids)
        !=
        EXPECTED_PILOT_PAIR_COUNT
    ):
        raise ValueError(
            "Duplicate pilot pair IDs."
        )


    approved_policy_by_id = {
        str(row["policy_template_id"]): row
        for row in approved_policy_rows
    }


    if not approved_policy_by_id:
        raise ValueError(
            "No approved Turkish policy "
            "template found."
        )


    for row in approved_policy_rows:

        if (
            row.get(
                "human_review_decision"
            )
            !=
            "approve_translation"
        ):
            raise ValueError(
                "Policy template is not "
                "human-approved."
            )


    rows_with_split: list[
        tuple[str, dict[str, Any]]
    ] = []


    rows_with_split.extend(
        (
            "train",
            row,
        )
        for row in train_rows
    )

    rows_with_split.extend(
        (
            "validation",
            row,
        )
        for row in validation_rows
    )


    source_rows_by_pair: dict[
        str,
        list[
            tuple[str, dict[str, Any]]
        ],
    ] = defaultdict(list)


    for split, row in rows_with_split:

        source_rows_by_pair[
            str(row["pair_id"])
        ].append(
            (
                split,
                row,
            )
        )


    if (
        len(source_rows_by_pair)
        !=
        EXPECTED_SOURCE_PAIR_COUNT
    ):
        raise ValueError(
            "Expected 83 train+validation "
            f"pairs, found "
            f"{len(source_rows_by_pair)}."
        )


    missing_pilot_pairs = (
        pilot_pair_ids
        -
        set(source_rows_by_pair)
    )


    if missing_pilot_pairs:
        raise ValueError(
            "Pilot pair not found in "
            "train+validation source:\n"
            f"{sorted(missing_pilot_pairs)}"
        )


    queue_records = []


    for pair_id, pair_entries in (
        source_rows_by_pair.items()
    ):

        if pair_id in pilot_pair_ids:
            continue


        if len(pair_entries) != 2:
            raise ValueError(
                f"{pair_id} has "
                f"{len(pair_entries)} rows."
            )


        pair_splits = {
            split
            for split, _ in pair_entries
        }


        if len(pair_splits) != 1:
            raise ValueError(
                f"{pair_id} spans multiple "
                f"splits: {pair_splits}"
            )


        split = next(
            iter(pair_splits)
        )


        pair_rows = [
            row
            for _, row in pair_entries
        ]


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


        if (
            safe_row is None
            or
            risky_row is None
        ):
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
                    f"{pair_id} safe row "
                    f"missing {section}."
                )

            if section not in risky_sections:
                raise ValueError(
                    f"{pair_id} risky row "
                    f"missing {section}."
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
                f"{pair_id} missing attempted "
                "action section."
            )


        template_id = policy_template_id(
            safe_sections[
                "POLICY_CONTEXT"
            ]
        )


        if (
            template_id
            not in
            approved_policy_by_id
        ):
            raise ValueError(
                f"{pair_id} uses an unknown "
                f"policy template: {template_id}"
            )


        queue_records.append(
            {
                "pair_id": pair_id,
                "suite": str(
                    safe_row["suite"]
                ),
                "split": split,
                "session_group_id": str(
                    safe_row[
                        "session_group_id"
                    ]
                ),
                "same_tool_minimal_pair": (
                    same_tool_flag(
                        safe_row
                    )
                ),
                "safe_row_id": str(
                    safe_row["row_id"]
                ),
                "risky_row_id": str(
                    risky_row["row_id"]
                ),
                "source_language": "en",
                "target_language": "tr",
                "translation_mode": (
                    "faithful_semantic_translation"
                ),
                "policy_template_id": (
                    template_id
                ),
                "user_goal_en": (
                    safe_sections[
                        "USER_GOAL"
                    ]
                ),
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
                    safe_sections[
                        "SOURCE"
                    ]
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


    if (
        len(queue_records)
        !=
        EXPECTED_REMAINING_PAIR_COUNT
    ):
        raise ValueError(
            "Expected 71 remaining pairs, "
            f"found {len(queue_records)}."
        )


    queue_records.sort(
        key=lambda row: stable_rank(
            str(row["pair_id"])
        )
    )


    for index, row in enumerate(
        queue_records,
        start=1,
    ):

        batch_number = (
            (index - 1)
            //
            BATCH_SIZE
            +
            1
        )

        batch_order = (
            (index - 1)
            %
            BATCH_SIZE
            +
            1
        )

        row[
            "global_order"
        ] = index

        row[
            "translation_batch_id"
        ] = (
            f"agentdojo_tr_batch_"
            f"{batch_number:03d}"
        )

        row[
            "batch_order"
        ] = batch_order

        row[
            "translation_rules"
        ] = [
            (
                "Translate natural-language "
                "content faithfully into Turkish."
            ),
            (
                "Do not translate section tags, "
                "field names, tool names, IDs, "
                "URLs, email addresses, file names, "
                "dates, amounts, enum values, JSON "
                "keys, Python expressions or "
                "placeholders."
            ),
            (
                "Do not localize entities during "
                "this phase."
            ),
            (
                "Safe and risky attempted actions "
                "must retain their original "
                "operational meaning."
            ),
            (
                "Do not introduce risk labels, "
                "review decisions or explanatory "
                "diagnostic text."
            ),
        ]


    split_counts = Counter(
        str(row["split"])
        for row in queue_records
    )


    if dict(split_counts) != {
        "train": (
            EXPECTED_REMAINING_TRAIN_PAIRS
        ),
        "validation": (
            EXPECTED_REMAINING_VALIDATION_PAIRS
        ),
    }:
        raise ValueError(
            "Unexpected remaining split counts: "
            f"{dict(split_counts)}"
        )


    if any(
        row["split"] == "test"
        for row in queue_records
    ):
        raise ValueError(
            "Test pair entered the Turkish "
            "translation queue."
        )


    queue_pair_ids = {
        str(row["pair_id"])
        for row in queue_records
    }


    if (
        queue_pair_ids
        &
        pilot_pair_ids
    ):
        raise ValueError(
            "Pilot pair entered full queue."
        )


    if len(queue_pair_ids) != len(
        queue_records
    ):
        raise ValueError(
            "Duplicate queue pair IDs."
        )


    batch_rows: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)


    for row in queue_records:

        batch_rows[
            str(
                row[
                    "translation_batch_id"
                ]
            )
        ].append(row)


    OUTPUT_BATCH_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )


    for old_batch_file in (
        OUTPUT_BATCH_DIRECTORY.glob(
            "*.jsonl"
        )
    ):
        old_batch_file.unlink()


    for batch_id, rows in sorted(
        batch_rows.items()
    ):

        write_jsonl(
            OUTPUT_BATCH_DIRECTORY
            /
            f"{batch_id}.jsonl",
            rows,
        )


    policy_reference_counts = Counter(
        str(row["policy_template_id"])
        for row in queue_records
    )


    policy_registry = []


    for template_id, count in sorted(
        policy_reference_counts.items()
    ):

        policy_row = deepcopy(
            approved_policy_by_id[
                template_id
            ]
        )

        policy_row[
            "registry_version"
        ] = "v0.2.0"

        policy_row[
            "translation_reused_from"
        ] = (
            "agentdojo_turkish_policy_"
            "template_queue_v0.1.2_"
            "human_reviewed"
        )

        policy_row[
            "referenced_remaining_pair_count"
        ] = count

        policy_registry.append(
            policy_row
        )


    write_jsonl(
        OUTPUT_QUEUE_PATH,
        queue_records,
    )

    write_csv(
        OUTPUT_CSV_PATH,
        queue_records,
    )

    write_jsonl(
        OUTPUT_POLICY_REGISTRY_PATH,
        policy_registry,
    )


    source_hashes_after = {
        "train": sha256_file(
            TRAIN_PATH
        ),
        "validation": sha256_file(
            VALIDATION_PATH
        ),
        "pilot_queue": sha256_file(
            PILOT_QUEUE_PATH
        ),
        "pilot_policy": sha256_file(
            PILOT_POLICY_PATH
        ),
    }


    if (
        source_hashes_before
        !=
        source_hashes_after
    ):
        raise ValueError(
            "A source artifact was modified."
        )


    suite_counts = Counter(
        str(row["suite"])
        for row in queue_records
    )

    same_tool_count = sum(
        bool(
            row[
                "same_tool_minimal_pair"
            ]
        )
        for row in queue_records
    )

    batch_counts = {
        batch_id: len(rows)
        for batch_id, rows in sorted(
            batch_rows.items()
        )
    }


    report = {
        "artifact_version": "0.2.0",

        "queue_type": (
            "agentdojo_full_turkish_"
            "translation_queue"
        ),

        "source_dataset_version": "0.1.5",

        "source_train_pair_count": 68,

        "source_validation_pair_count": 15,

        "source_train_validation_pair_count": (
            EXPECTED_SOURCE_PAIR_COUNT
        ),

        "excluded_completed_pilot_pairs": (
            EXPECTED_PILOT_PAIR_COUNT
        ),

        "remaining_translation_pair_count": (
            len(queue_records)
        ),

        "eventual_runtime_row_count": (
            len(queue_records) * 2
        ),

        "split_counts": dict(
            sorted(
                split_counts.items()
            )
        ),

        "suite_counts": dict(
            sorted(
                suite_counts.items()
            )
        ),

        "same_tool_pair_count": (
            same_tool_count
        ),

        "policy_template_count": (
            len(policy_registry)
        ),

        "policy_translation_reused": True,

        "batch_size": BATCH_SIZE,

        "batch_count": len(
            batch_rows
        ),

        "batch_counts": (
            batch_counts
        ),

        "test_pair_count": 0,

        "validation": {
            "all_pairs_have_safe_and_risky": (
                True
            ),
            "shared_context_matches": True,
            "pilot_pairs_excluded": True,
            "duplicate_pair_count": 0,
            "unknown_policy_template_count": 0,
            "source_files_modified": False,
            "test_split_accessed": False,
        },

        "source_hashes": (
            source_hashes_before
        ),

        "outputs": {
            "translation_queue_jsonl": str(
                OUTPUT_QUEUE_PATH
            ),
            "translation_queue_csv": str(
                OUTPUT_CSV_PATH
            ),
            "policy_registry": str(
                OUTPUT_POLICY_REGISTRY_PATH
            ),
            "batch_directory": str(
                OUTPUT_BATCH_DIRECTORY
            ),
        },
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
        "AGENTDOJO TURKISH FULL "
        "TRANSLATION QUEUE v0.2.0 CREATED"
    )
    print("=" * 80)
    print()

    print(
        "Source train+validation pairs:",
        EXPECTED_SOURCE_PAIR_COUNT,
    )

    print(
        "Completed pilot pairs excluded:",
        EXPECTED_PILOT_PAIR_COUNT,
    )

    print(
        "Remaining translation pairs:",
        len(queue_records),
    )

    print(
        "Eventual Turkish runtime rows:",
        len(queue_records) * 2,
    )

    print()

    print(
        "Split counts:",
        dict(
            sorted(
                split_counts.items()
            )
        ),
    )

    print(
        "Suite counts:",
        dict(
            sorted(
                suite_counts.items()
            )
        ),
    )

    print(
        "Same-tool pairs:",
        same_tool_count,
    )

    print(
        "Policy templates reused:",
        len(policy_registry),
    )

    print()

    print(
        "Translation batches:",
        len(batch_rows),
    )

    for batch_id, count in (
        batch_counts.items()
    ):
        print(
            f"  {batch_id}: "
            f"{count} pairs"
        )

    print()

    print(
        "Queue JSONL:",
        OUTPUT_QUEUE_PATH,
    )

    print(
        "Queue CSV:",
        OUTPUT_CSV_PATH,
    )

    print(
        "Policy registry:",
        OUTPUT_POLICY_REGISTRY_PATH,
    )

    print(
        "Batch directory:",
        OUTPUT_BATCH_DIRECTORY,
    )

    print(
        "Report:",
        OUTPUT_REPORT_PATH,
    )

    print()

    print(
        "Pilot pairs included: no"
    )

    print(
        "Test split accessed: no"
    )

    print(
        "Source artifacts modified: no"
    )


if __name__ == "__main__":
    main()

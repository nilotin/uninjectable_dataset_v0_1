from __future__ import annotations

import hashlib
import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SOURCE_STRUCTURED_POOL_PATH = Path(
    "data/processed/"
    "agentdojo_contextual_action_attempt_labeled_pool_v0.1.5.jsonl"
)

SOURCE_ASSIGNMENTS_PATH = Path(
    "data/processed/"
    "agentdojo_group_aware_split_v0.1.5/"
    "agentdojo_group_split_assignments_v0.1.5.jsonl"
)

SOURCE_DATASET_MANIFEST_PATH = Path(
    "data/processed/"
    "agentdojo_v0.1.5_sha256.txt"
)

SOURCE_SPLIT_MANIFEST_PATH = Path(
    "data/processed/"
    "agentdojo_group_aware_split_v0.1.5/"
    "agentdojo_group_split_v0.1.5_sha256.txt"
)

TRANSLATION_QUEUE_PATH = Path(
    "data/interim/"
    "agentdojo_turkish_translation_pilot_queue_"
    "v0.1.2_human_reviewed.jsonl"
)

POLICY_QUEUE_PATH = Path(
    "data/interim/"
    "agentdojo_turkish_policy_template_queue_"
    "v0.1.2_human_reviewed.jsonl"
)


OUTPUT_DIRECTORY = Path(
    "data/processed/"
    "agentdojo_turkish_pilot_v0.1.3"
)

OUTPUT_STRUCTURED_POOL_PATH = (
    OUTPUT_DIRECTORY
    / "agentdojo_turkish_contextual_action_attempt_pilot_v0.1.3.jsonl"
)

OUTPUT_BERT_VIEW_PATH = (
    OUTPUT_DIRECTORY
    / "agentdojo_turkish_bert_training_view_v0.1.3.jsonl"
)

OUTPUT_TRAIN_VIEW_PATH = (
    OUTPUT_DIRECTORY
    / "agentdojo_turkish_bert_training_view_v0.1.3_train.jsonl"
)

OUTPUT_VALIDATION_VIEW_PATH = (
    OUTPUT_DIRECTORY
    / "agentdojo_turkish_bert_training_view_v0.1.3_validation.jsonl"
)

OUTPUT_REPORT_PATH = (
    OUTPUT_DIRECTORY
    / "agentdojo_turkish_pilot_v0.1.3_report.json"
)


EXPECTED_PAIR_COUNT = 12
EXPECTED_RUNTIME_ROW_COUNT = 24

EXPECTED_TRAIN_PAIR_COUNT = 8
EXPECTED_TRAIN_ROW_COUNT = 16

EXPECTED_VALIDATION_PAIR_COUNT = 4
EXPECTED_VALIDATION_ROW_COUNT = 8

EXPECTED_POLICY_TEMPLATE_COUNT = 1
EXPECTED_SAME_TOOL_PAIR_COUNT = 9


SECTION_ORDER = (
    "USER_GOAL",
    "AGENT_CONTEXT",
    "SOURCE",
    "CONTEXT_BINDINGS",
    "RETRIEVED_CONTENT",
    "USER_AUTHORIZATION",
    "POLICY_CONTEXT",
    "ATTEMPTED_ACTION",
)

FORBIDDEN_MODEL_INPUT_MARKERS = (
    "general_risk_label",
    "final_binary_label",
    "human_review_decision",
    "approve_translation",
    "translation_status",
    "label_source",
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


def sha256_bytes(
    value: str,
) -> str:

    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def sha256_file(
    path: Path,
) -> str:

    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def verify_manifest(
    path: Path,
    expected_count: int,
) -> int:

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

        parts = line.split(
            None,
            1,
        )

        if len(parts) != 2:
            raise ValueError(
                f"Invalid manifest line: {line}"
            )

        expected_hash, raw_path = parts
        artifact_path = Path(
            raw_path.strip()
        )

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
                "Checkpoint verification failed:\n"
                f"Artifact: {artifact_path}\n"
                f"Expected: {expected_hash}\n"
                f"Actual:   {actual_hash}"
            )

        verified += 1

    if verified != expected_count:
        raise ValueError(
            f"Expected {expected_count} manifest "
            f"entries, verified {verified}."
        )

    return verified


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


def variant_order(
    variant: str,
) -> int:

    mapping = {
        "safe": 0,
        "risky": 1,
    }

    if variant not in mapping:
        raise ValueError(
            f"Unexpected variant: {variant}"
        )

    return mapping[
        variant
    ]


def serialize_sections(
    sections: dict[str, str],
) -> str:

    missing_sections = [
        section
        for section in SECTION_ORDER
        if section not in sections
    ]

    if missing_sections:
        raise ValueError(
            "Missing serialized sections: "
            f"{missing_sections}"
        )

    blocks = []

    for section in SECTION_ORDER:

        value = sections[
            section
        ].strip()

        if not value:
            raise ValueError(
                f"Empty section: {section}"
            )

        blocks.append(
            f"[{section}]\n{value}"
        )

    return "\n\n".join(
        blocks
    )


def shared_context_text(
    sections: dict[str, str],
) -> str:

    return "\n\n".join(
        f"[{section}]\n"
        f"{sections[section].strip()}"
        for section in SECTION_ORDER
        if section != "ATTEMPTED_ACTION"
    )


def main() -> None:

    source_dataset_hashes_before = (
        verify_manifest(
            SOURCE_DATASET_MANIFEST_PATH,
            expected_count=4,
        )
    )

    source_split_hashes_before = (
        verify_manifest(
            SOURCE_SPLIT_MANIFEST_PATH,
            expected_count=8,
        )
    )


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


    source_rows = load_jsonl(
        SOURCE_STRUCTURED_POOL_PATH
    )

    assignment_rows = load_jsonl(
        SOURCE_ASSIGNMENTS_PATH
    )

    translation_rows = load_jsonl(
        TRANSLATION_QUEUE_PATH
    )

    policy_rows = load_jsonl(
        POLICY_QUEUE_PATH
    )


    if len(translation_rows) != EXPECTED_PAIR_COUNT:
        raise ValueError(
            "Expected 12 reviewed translation "
            f"pairs, found {len(translation_rows)}."
        )


    if (
        len(policy_rows)
        !=
        EXPECTED_POLICY_TEMPLATE_COUNT
    ):
        raise ValueError(
            "Expected one reviewed policy "
            f"template, found {len(policy_rows)}."
        )


    policy_by_id = {
        str(row["policy_template_id"]): row
        for row in policy_rows
    }


    for policy_row in policy_rows:

        if (
            policy_row.get(
                "human_review_decision"
            )
            !=
            "approve_translation"
        ):
            raise ValueError(
                "Policy translation is not "
                "human-approved."
            )

        if (
            policy_row.get(
                "translation_status"
            )
            !=
            "human_reviewed_approved"
        ):
            raise ValueError(
                "Policy translation has an "
                "unexpected status."
            )


    assignment_by_pair = {
        str(row["pair_id"]): str(row["split"])
        for row in assignment_rows
    }


    source_rows_by_pair: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)


    for row in source_rows:

        source_rows_by_pair[
            str(row["pair_id"])
        ].append(row)


    structured_output_rows: list[
        dict[str, Any]
    ] = []

    bert_output_rows: list[
        dict[str, Any]
    ] = []


    generated_at = datetime.now(
        timezone.utc
    ).isoformat()


    for translation_row in translation_rows:

        source_pair_id = str(
            translation_row["pair_id"]
        )

        localized_pair_id = (
            f"{source_pair_id}_tr"
        )

        split = str(
            translation_row["split"]
        )


        if split not in {
            "train",
            "validation",
        }:
            raise ValueError(
                f"{source_pair_id} has forbidden "
                f"pilot split: {split}"
            )


        if (
            assignment_by_pair.get(
                source_pair_id
            )
            !=
            split
        ):
            raise ValueError(
                f"{source_pair_id} translation "
                "split does not match the source "
                "assignment."
            )


        if (
            translation_row.get(
                "human_review_decision"
            )
            !=
            "approve_translation"
        ):
            raise ValueError(
                f"{source_pair_id} translation "
                "is not approved."
            )


        if (
            translation_row.get(
                "translation_status"
            )
            !=
            "human_reviewed_approved"
        ):
            raise ValueError(
                f"{source_pair_id} translation "
                "has an unexpected status."
            )


        source_pair_rows = (
            source_rows_by_pair.get(
                source_pair_id
            )
        )


        if (
            source_pair_rows is None
            or
            len(source_pair_rows) != 2
        ):
            raise ValueError(
                f"{source_pair_id} does not have "
                "exactly two source rows."
            )


        source_by_variant = {
            variant_name(row): row
            for row in source_pair_rows
        }


        if set(source_by_variant) != {
            "safe",
            "risky",
        }:
            raise ValueError(
                f"{source_pair_id} source pair "
                "does not contain safe and risky "
                "variants."
            )


        policy_template_id = str(
            translation_row[
                "policy_template_id"
            ]
        )

        policy_row = policy_by_id.get(
            policy_template_id
        )


        if policy_row is None:
            raise ValueError(
                f"{source_pair_id} references "
                "an unknown policy template."
            )


        shared_sections = {
            "USER_GOAL": str(
                translation_row[
                    "user_goal_tr"
                ]
            ),

            "AGENT_CONTEXT": str(
                translation_row[
                    "protected_agent_context"
                ]
            ),

            "SOURCE": str(
                translation_row[
                    "protected_source"
                ]
            ),

            "CONTEXT_BINDINGS": str(
                translation_row[
                    "protected_context_bindings"
                ]
            ),

            "RETRIEVED_CONTENT": str(
                translation_row[
                    "retrieved_content_tr"
                ]
            ),

            "USER_AUTHORIZATION": str(
                translation_row[
                    "user_authorization_tr"
                ]
            ),

            "POLICY_CONTEXT": str(
                policy_row[
                    "policy_context_tr"
                ]
            ),
        }


        shared_fingerprint = sha256_bytes(
            shared_context_text(
                {
                    **shared_sections,
                    "ATTEMPTED_ACTION": (
                        "<excluded>"
                    ),
                }
            )
        )


        for variant in (
            "safe",
            "risky",
        ):

            source_row = source_by_variant[
                variant
            ]


            action_field = (
                "safe_attempted_action_tr"
                if variant == "safe"
                else
                "risky_attempted_action_tr"
            )


            attempted_action = str(
                translation_row[
                    action_field
                ]
            )


            sections = {
                **shared_sections,
                "ATTEMPTED_ACTION": (
                    attempted_action
                ),
            }


            model_text = serialize_sections(
                sections
            )

            text_hash = sha256_bytes(
                model_text
            )

            action_fingerprint = (
                sha256_bytes(
                    attempted_action.strip()
                )
            )


            for marker in (
                FORBIDDEN_MODEL_INPUT_MARKERS
            ):

                if marker.lower() in (
                    model_text.lower()
                ):
                    raise ValueError(
                        f"Label/review leakage in "
                        f"{source_pair_id}/{variant}: "
                        f"{marker}"
                    )


            source_label = int(
                source_row[
                    "review"
                ][
                    "final_binary_label"
                ]
            )


            expected_label = (
                0
                if variant == "safe"
                else 1
            )


            if source_label != expected_label:
                raise ValueError(
                    f"{source_pair_id}/{variant} "
                    "has an unexpected source label: "
                    f"{source_label}"
                )


            localized_row_id = (
                f"{localized_pair_id}::"
                f"{variant}::action_attempt"
            )


            structured_row = {
                "schema_version": (
                    "agentdojo_turkish_"
                    "localization_v0.1.3"
                ),

                "artifact_version": "0.1.3",

                "language": "tr",

                "source_language": "en",

                "translation_mode": (
                    "faithful_semantic_translation"
                ),

                "suite": str(
                    translation_row[
                        "suite"
                    ]
                ),

                "split": split,

                "source_pair_id": (
                    source_pair_id
                ),

                "pair_id": localized_pair_id,

                "source_row_id": str(
                    source_row[
                        "row_id"
                    ]
                ),

                "row_id": localized_row_id,

                "session_group_id": str(
                    translation_row[
                        "session_group_id"
                    ]
                ),

                "crosslingual_group_id": (
                    source_pair_id
                ),

                "variant": variant,

                "same_tool_minimal_pair": bool(
                    translation_row[
                        "same_tool_minimal_pair"
                    ]
                ),

                "sections": {
                    "user_goal": (
                        shared_sections[
                            "USER_GOAL"
                        ]
                    ),

                    "agent_context": (
                        shared_sections[
                            "AGENT_CONTEXT"
                        ]
                    ),

                    "source": (
                        shared_sections[
                            "SOURCE"
                        ]
                    ),

                    "context_bindings": (
                        shared_sections[
                            "CONTEXT_BINDINGS"
                        ]
                    ),

                    "retrieved_content": (
                        shared_sections[
                            "RETRIEVED_CONTENT"
                        ]
                    ),

                    "user_authorization": (
                        shared_sections[
                            "USER_AUTHORIZATION"
                        ]
                    ),

                    "policy_context": (
                        shared_sections[
                            "POLICY_CONTEXT"
                        ]
                    ),

                    "attempted_action": (
                        attempted_action
                    ),
                },

                "model_input": {
                    "serialization_version": (
                        "agentdojo_turkish_"
                        "serialization_v0.1.3"
                    ),

                    "included_sections": list(
                        SECTION_ORDER
                    ),

                    "excluded_from_input": [
                        "general_risk_label",
                        "review_metadata",
                        "translation_review_decision",
                        "translation_status",
                        "split_assignment",
                    ],

                    "shared_context_fingerprint": (
                        shared_fingerprint
                    ),

                    "attempted_action_fingerprint": (
                        action_fingerprint
                    ),

                    "text": model_text,

                    "text_sha256": text_hash,
                },

                "label": {
                    "general_risk_label": (
                        source_label
                    ),

                    "label_source": (
                        "agentdojo_v0.1.5_"
                        "source_label"
                    ),
                },

                "translation_review": {
                    "decision": (
                        "approve_translation"
                    ),

                    "review_version": (
                        translation_row.get(
                            "human_review_version",
                            "v0.1.2",
                        )
                    ),

                    "reviewed_at": (
                        translation_row.get(
                            "human_reviewed_at"
                        )
                    ),

                    "reviewer_note": (
                        translation_row.get(
                            "reviewer_note",
                            "",
                        )
                    ),

                    "policy_template_id": (
                        policy_template_id
                    ),
                },

                "provenance": {
                    "source_dataset": (
                        "agentdojo_v0.1.5"
                    ),

                    "source_structured_pool": str(
                        SOURCE_STRUCTURED_POOL_PATH
                    ),

                    "source_translation_queue": str(
                        TRANSLATION_QUEUE_PATH
                    ),

                    "source_policy_queue": str(
                        POLICY_QUEUE_PATH
                    ),

                    "source_split_assignment": (
                        split
                    ),

                    "generated_at": generated_at,
                },
            }


            bert_row = {
                "schema_version": (
                    "agentdojo_turkish_bert_"
                    "training_view_v0.1.3"
                ),

                "row_id": localized_row_id,

                "pair_id": localized_pair_id,

                "source_pair_id": (
                    source_pair_id
                ),

                "session_group_id": str(
                    translation_row[
                        "session_group_id"
                    ]
                ),

                "crosslingual_group_id": (
                    source_pair_id
                ),

                "suite": str(
                    translation_row[
                        "suite"
                    ]
                ),

                "split": split,

                "language": "tr",

                "variant": variant,

                "text": model_text,

                "text_sha256": text_hash,

                "general_risk_label": (
                    source_label
                ),

                "label_source": (
                    "agentdojo_v0.1.5_"
                    "source_label_plus_"
                    "turkish_translation_"
                    "human_review_v0.1.2"
                ),
            }


            structured_output_rows.append(
                structured_row
            )

            bert_output_rows.append(
                bert_row
            )


    structured_output_rows.sort(
        key=lambda row: (
            str(row["suite"]),
            str(row["source_pair_id"]),
            variant_order(
                str(row["variant"])
            ),
        )
    )

    bert_output_rows.sort(
        key=lambda row: (
            str(row["suite"]),
            str(row["source_pair_id"]),
            variant_order(
                str(row["variant"])
            ),
        )
    )


    if (
        len(structured_output_rows)
        !=
        EXPECTED_RUNTIME_ROW_COUNT
    ):
        raise ValueError(
            "Expected 24 Turkish structured "
            f"rows, found "
            f"{len(structured_output_rows)}."
        )


    if (
        len(bert_output_rows)
        !=
        EXPECTED_RUNTIME_ROW_COUNT
    ):
        raise ValueError(
            "Expected 24 Turkish BERT rows, "
            f"found {len(bert_output_rows)}."
        )


    localized_pair_ids = {
        str(row["pair_id"])
        for row in structured_output_rows
    }


    if (
        len(localized_pair_ids)
        !=
        EXPECTED_PAIR_COUNT
    ):
        raise ValueError(
            "Expected 12 localized pair IDs, "
            f"found {len(localized_pair_ids)}."
        )


    rows_by_pair: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)


    for row in structured_output_rows:

        rows_by_pair[
            str(row["pair_id"])
        ].append(row)


    shared_context_validation = 0
    distinct_action_validation = 0
    label_pair_validation = 0
    split_pair_validation = 0


    for pair_id, pair_rows in (
        rows_by_pair.items()
    ):

        if len(pair_rows) != 2:
            raise ValueError(
                f"{pair_id} has "
                f"{len(pair_rows)} rows."
            )


        if {
            int(
                row[
                    "label"
                ][
                    "general_risk_label"
                ]
            )
            for row in pair_rows
        } != {0, 1}:
            raise ValueError(
                f"{pair_id} does not contain "
                "one label 0 and one label 1."
            )

        label_pair_validation += 1


        if len({
            str(
                row[
                    "model_input"
                ][
                    "shared_context_fingerprint"
                ]
            )
            for row in pair_rows
        }) != 1:
            raise ValueError(
                f"{pair_id} shared context differs."
            )

        shared_context_validation += 1


        if len({
            str(
                row[
                    "model_input"
                ][
                    "attempted_action_fingerprint"
                ]
            )
            for row in pair_rows
        }) != 2:
            raise ValueError(
                f"{pair_id} attempted actions "
                "are identical."
            )

        distinct_action_validation += 1


        if len({
            str(row["split"])
            for row in pair_rows
        }) != 1:
            raise ValueError(
                f"{pair_id} spans multiple splits."
            )

        split_pair_validation += 1


    row_ids = [
        str(row["row_id"])
        for row in structured_output_rows
    ]


    if len(row_ids) != len(set(row_ids)):
        raise ValueError(
            "Duplicate localized row IDs."
        )


    model_texts = [
        str(
            row[
                "model_input"
            ][
                "text"
            ]
        )
        for row in structured_output_rows
    ]


    duplicate_model_input_count = (
        len(model_texts)
        -
        len(set(model_texts))
    )


    if duplicate_model_input_count != 0:
        raise ValueError(
            "Duplicate Turkish model inputs "
            f"detected: "
            f"{duplicate_model_input_count}"
        )


    label_counts = Counter(
        int(
            row[
                "general_risk_label"
            ]
        )
        for row in bert_output_rows
    )


    if dict(label_counts) != {
        0: 12,
        1: 12,
    }:
        raise ValueError(
            "Unexpected total label counts: "
            f"{dict(label_counts)}"
        )


    train_rows = [
        row
        for row in bert_output_rows
        if row["split"] == "train"
    ]

    validation_rows = [
        row
        for row in bert_output_rows
        if row["split"] == "validation"
    ]

    test_rows = [
        row
        for row in bert_output_rows
        if row["split"] == "test"
    ]


    if len(train_rows) != EXPECTED_TRAIN_ROW_COUNT:
        raise ValueError(
            "Expected 16 Turkish train rows, "
            f"found {len(train_rows)}."
        )


    if (
        len(validation_rows)
        !=
        EXPECTED_VALIDATION_ROW_COUNT
    ):
        raise ValueError(
            "Expected 8 Turkish validation rows, "
            f"found {len(validation_rows)}."
        )


    if test_rows:
        raise ValueError(
            "Test rows entered the Turkish pilot."
        )


    train_label_counts = Counter(
        int(row["general_risk_label"])
        for row in train_rows
    )

    validation_label_counts = Counter(
        int(row["general_risk_label"])
        for row in validation_rows
    )


    if dict(train_label_counts) != {
        0: 8,
        1: 8,
    }:
        raise ValueError(
            "Unexpected train labels: "
            f"{dict(train_label_counts)}"
        )


    if dict(validation_label_counts) != {
        0: 4,
        1: 4,
    }:
        raise ValueError(
            "Unexpected validation labels: "
            f"{dict(validation_label_counts)}"
        )


    train_pair_count = len({
        row["pair_id"]
        for row in train_rows
    })

    validation_pair_count = len({
        row["pair_id"]
        for row in validation_rows
    })


    if (
        train_pair_count
        !=
        EXPECTED_TRAIN_PAIR_COUNT
    ):
        raise ValueError(
            "Expected 8 Turkish train pairs, "
            f"found {train_pair_count}."
        )


    if (
        validation_pair_count
        !=
        EXPECTED_VALIDATION_PAIR_COUNT
    ):
        raise ValueError(
            "Expected 4 Turkish validation pairs, "
            f"found {validation_pair_count}."
        )


    same_tool_pair_count = sum(
        bool(pair_rows[0][
            "same_tool_minimal_pair"
        ])
        for pair_rows in rows_by_pair.values()
    )


    if (
        same_tool_pair_count
        !=
        EXPECTED_SAME_TOOL_PAIR_COUNT
    ):
        raise ValueError(
            "Expected 9 same-tool Turkish "
            f"pairs, found "
            f"{same_tool_pair_count}."
        )


    OUTPUT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )


    write_jsonl(
        OUTPUT_STRUCTURED_POOL_PATH,
        structured_output_rows,
    )

    write_jsonl(
        OUTPUT_BERT_VIEW_PATH,
        bert_output_rows,
    )

    write_jsonl(
        OUTPUT_TRAIN_VIEW_PATH,
        train_rows,
    )

    write_jsonl(
        OUTPUT_VALIDATION_VIEW_PATH,
        validation_rows,
    )


    source_dataset_hashes_after = (
        verify_manifest(
            SOURCE_DATASET_MANIFEST_PATH,
            expected_count=4,
        )
    )

    source_split_hashes_after = (
        verify_manifest(
            SOURCE_SPLIT_MANIFEST_PATH,
            expected_count=8,
        )
    )


    if (
        source_translation_hash_before
        !=
        sha256_file(
            TRANSLATION_QUEUE_PATH
        )
    ):
        raise ValueError(
            "Human-reviewed translation queue "
            "was modified."
        )


    if (
        source_policy_hash_before
        !=
        sha256_file(
            POLICY_QUEUE_PATH
        )
    ):
        raise ValueError(
            "Human-reviewed policy queue "
            "was modified."
        )


    text_lengths = [
        len(text)
        for text in model_texts
    ]


    report = {
        "artifact_version": "0.1.3",

        "dataset": (
            "agentdojo_turkish_translation_pilot"
        ),

        "language": "tr",

        "source_language": "en",

        "source_dataset_version": "0.1.5",

        "translation_review_version": "0.1.2",

        "localized_pair_count": (
            EXPECTED_PAIR_COUNT
        ),

        "runtime_row_count": (
            EXPECTED_RUNTIME_ROW_COUNT
        ),

        "train_pair_count": (
            train_pair_count
        ),

        "train_row_count": (
            len(train_rows)
        ),

        "validation_pair_count": (
            validation_pair_count
        ),

        "validation_row_count": (
            len(validation_rows)
        ),

        "test_pair_count": 0,

        "test_row_count": 0,

        "label_counts": {
            str(label): count
            for label, count in sorted(
                label_counts.items()
            )
        },

        "train_label_counts": {
            str(label): count
            for label, count in sorted(
                train_label_counts.items()
            )
        },

        "validation_label_counts": {
            str(label): count
            for label, count in sorted(
                validation_label_counts.items()
            )
        },

        "same_tool_pair_count": (
            same_tool_pair_count
        ),

        "unique_model_input_count": (
            len(set(model_texts))
        ),

        "duplicate_model_input_count": (
            duplicate_model_input_count
        ),

        "validation": {
            "shared_context_pairs_passed": (
                shared_context_validation
            ),

            "distinct_action_pairs_passed": (
                distinct_action_validation
            ),

            "label_pairs_passed": (
                label_pair_validation
            ),

            "split_pairs_passed": (
                split_pair_validation
            ),

            "label_or_review_leakage_count": 0,

            "source_dataset_hashes_before": (
                source_dataset_hashes_before
            ),

            "source_dataset_hashes_after": (
                source_dataset_hashes_after
            ),

            "source_split_hashes_before": (
                source_split_hashes_before
            ),

            "source_split_hashes_after": (
                source_split_hashes_after
            ),

            "source_dataset_modified": False,

            "source_split_artifacts_modified": (
                False
            ),

            "reviewed_translation_queue_modified": (
                False
            ),

            "reviewed_policy_queue_modified": (
                False
            ),
        },

        "model_input_character_length": {
            "minimum": min(text_lengths),

            "median": statistics.median(
                text_lengths
            ),

            "maximum": max(text_lengths),

            "mean": (
                sum(text_lengths)
                /
                len(text_lengths)
            ),
        },

        "outputs": {
            "structured_pool": str(
                OUTPUT_STRUCTURED_POOL_PATH
            ),

            "bert_training_view": str(
                OUTPUT_BERT_VIEW_PATH
            ),

            "train_view": str(
                OUTPUT_TRAIN_VIEW_PATH
            ),

            "validation_view": str(
                OUTPUT_VALIDATION_VIEW_PATH
            ),
        },

        "important_notes": [
            (
                "The Turkish pilot contains only "
                "human-reviewed translations."
            ),

            (
                "The original English AgentDojo "
                "v0.1.5 artifacts were not modified."
            ),

            (
                "Turkish rows retain the same "
                "crosslingual group and split as "
                "their English source pairs."
            ),

            (
                "No test examples were translated "
                "or materialized during the pilot."
            ),

            (
                "Labels and review metadata remain "
                "outside model_input.text."
            ),
        ],
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
        "v0.1.3 MATERIALIZED"
    )

    print("=" * 80)

    print()

    print(
        "Localized pairs:",
        EXPECTED_PAIR_COUNT,
    )

    print(
        "Runtime rows:",
        EXPECTED_RUNTIME_ROW_COUNT,
    )

    print()

    print(
        "Train pairs / rows:",
        train_pair_count,
        "/",
        len(train_rows),
    )

    print(
        "Validation pairs / rows:",
        validation_pair_count,
        "/",
        len(validation_rows),
    )

    print(
        "Test pairs / rows:",
        0,
        "/",
        0,
    )

    print()

    print(
        "Total labels:",
        dict(label_counts),
    )

    print(
        "Train labels:",
        dict(train_label_counts),
    )

    print(
        "Validation labels:",
        dict(
            validation_label_counts
        ),
    )

    print()

    print(
        "Same-tool pairs:",
        same_tool_pair_count,
    )

    print(
        "Unique model inputs:",
        len(set(model_texts)),
    )

    print(
        "Duplicate model inputs:",
        duplicate_model_input_count,
    )

    print(
        "Label/review leakage:",
        0,
    )

    print()

    print(
        "Shared-context validation:",
        f"{shared_context_validation} / "
        f"{EXPECTED_PAIR_COUNT} passed",
    )

    print(
        "Distinct-action validation:",
        f"{distinct_action_validation} / "
        f"{EXPECTED_PAIR_COUNT} passed",
    )

    print(
        "Label-pair validation:",
        f"{label_pair_validation} / "
        f"{EXPECTED_PAIR_COUNT} passed",
    )

    print(
        "Split-pair validation:",
        f"{split_pair_validation} / "
        f"{EXPECTED_PAIR_COUNT} passed",
    )

    print()

    print(
        "Structured pool:",
        OUTPUT_STRUCTURED_POOL_PATH,
    )

    print(
        "BERT training view:",
        OUTPUT_BERT_VIEW_PATH,
    )

    print(
        "Train view:",
        OUTPUT_TRAIN_VIEW_PATH,
    )

    print(
        "Validation view:",
        OUTPUT_VALIDATION_VIEW_PATH,
    )

    print(
        "Report:",
        OUTPUT_REPORT_PATH,
    )

    print()

    print(
        "Original AgentDojo dataset modified: no"
    )

    print(
        "Original split artifacts modified: no"
    )

    print(
        "Test split opened: no"
    )


if __name__ == "__main__":
    main()

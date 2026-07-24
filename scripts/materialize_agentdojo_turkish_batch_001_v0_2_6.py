from __future__ import annotations

import ast
import hashlib
import json
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any

from transformers import AutoTokenizer


MODEL_NAME = "google-bert/bert-base-multilingual-cased"
MAX_LENGTH = 512

BASE_INTERIM = Path(
    "data/interim/"
    "agentdojo_turkish_full_translation_batches_v0.2.0"
)

TRANSLATION_PATH = (
    BASE_INTERIM
    / "agentdojo_tr_batch_001_v0.2.4_final_human_reviewed.jsonl"
)

TRANSLATION_REPORT_PATH = (
    BASE_INTERIM
    / "agentdojo_tr_batch_001_v0.2.4_final_report.json"
)

TRAIN_SOURCE_PATH = Path(
    "data/processed/"
    "agentdojo_group_aware_split_v0.1.5/"
    "agentdojo_contextual_action_attempt_labeled_pool_v0.1.5_train.jsonl"
)

VALIDATION_SOURCE_PATH = Path(
    "data/processed/"
    "agentdojo_group_aware_split_v0.1.5/"
    "agentdojo_contextual_action_attempt_labeled_pool_v0.1.5_validation.jsonl"
)

POLICY_REGISTRY_PATH = Path(
    "data/interim/"
    "agentdojo_turkish_full_policy_registry_v0.2.0.jsonl"
)

OUTPUT_DIR = Path(
    "data/processed/"
    "agentdojo_turkish_batch_001_v0.2.6"
)

STRUCTURED_ALL_PATH = (
    OUTPUT_DIR
    / "agentdojo_turkish_batch_001_structured_v0.2.6.jsonl"
)

STRUCTURED_TRAIN_PATH = (
    OUTPUT_DIR
    / "agentdojo_turkish_batch_001_structured_v0.2.6_train.jsonl"
)

STRUCTURED_VALIDATION_PATH = (
    OUTPUT_DIR
    / "agentdojo_turkish_batch_001_structured_v0.2.6_validation.jsonl"
)

COMPACT_ALL_PATH = (
    OUTPUT_DIR
    / "agentdojo_turkish_batch_001_bert_compact_v0.2.6.jsonl"
)

COMPACT_TRAIN_PATH = (
    OUTPUT_DIR
    / "agentdojo_turkish_batch_001_bert_compact_v0.2.6_train.jsonl"
)

COMPACT_VALIDATION_PATH = (
    OUTPUT_DIR
    / "agentdojo_turkish_batch_001_bert_compact_v0.2.6_validation.jsonl"
)

REPORT_PATH = (
    OUTPUT_DIR
    / "agentdojo_turkish_batch_001_v0.2.6_report.json"
)

MANIFEST_PATH = (
    OUTPUT_DIR
    / "agentdojo_turkish_batch_001_v0.2.6_sha256.txt"
)

EXPECTED_PAIR_COUNT = 10
EXPECTED_ROW_COUNT = 20

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

FORBIDDEN_INPUT_MARKERS = (
    "general_risk_label",
    "final_binary_label",
    "review_decision",
    "approve_translation",
    "needs_revision",
    "human_review_decision",
)


def load_jsonl(
    path: Path,
) -> list[dict[str, Any]]:

    if not path.exists():
        raise FileNotFoundError(
            f"Missing file: {path}"
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
    value: bytes,
) -> str:

    return hashlib.sha256(value).hexdigest()


def sha256_text(
    value: str,
) -> str:

    return sha256_bytes(
        value.encode("utf-8")
    )


def sha256_file(
    path: Path,
) -> str:

    return sha256_bytes(
        path.read_bytes()
    )


def serialize_sections(
    sections: dict[str, str],
    order: tuple[str, ...],
) -> str:

    blocks = []

    for section_name in order:
        value = str(
            sections[section_name]
        ).strip()

        if not value:
            raise ValueError(
                f"Empty serialized section: "
                f"{section_name}"
            )

        blocks.append(
            f"[{section_name}]\n{value}"
        )

    return "\n\n".join(blocks)


def parse_key_values(
    text: str,
) -> dict[str, str]:

    values = {}

    for line in text.splitlines():
        if "=" not in line:
            continue

        key, value = line.split(
            "=",
            1,
        )

        values[key.strip()] = value.strip()

    return values


def line_value(
    text: str,
    prefix: str,
) -> str | None:

    for line in text.splitlines():
        if line.startswith(prefix):
            return line[len(prefix):]

    return None


def variant_name(
    row: dict[str, Any],
) -> str:

    variant = row.get("variant")

    if isinstance(variant, dict):
        variant = variant.get("name")

    return str(variant)


def try_literal_args(
    serialized_action: str,
) -> Any | None:

    expression = line_value(
        serialized_action,
        "args=",
    )

    if expression is None:
        return None

    try:
        return ast.literal_eval(expression)
    except (
        ValueError,
        SyntaxError,
    ):
        return None


def validate_no_leakage(
    text: str,
    row_id: str,
) -> None:

    lowered = text.lower()

    for marker in FORBIDDEN_INPUT_MARKERS:
        if marker.lower() in lowered:
            raise ValueError(
                f"Input leakage in {row_id}: "
                f"{marker}"
            )


def make_full_sections(
    translation: dict[str, Any],
    attempted_action_tr: str,
    policy_text_tr: str,
) -> dict[str, str]:

    return {
        "USER_GOAL": (
            translation["user_goal_tr"]
        ),
        "AGENT_CONTEXT": (
            translation[
                "protected_agent_context"
            ]
        ),
        "SOURCE": (
            translation[
                "protected_source"
            ]
        ),
        "CONTEXT_BINDINGS": (
            translation[
                "protected_context_bindings"
            ]
        ),
        "RETRIEVED_CONTENT": (
            translation[
                "retrieved_content_tr"
            ]
        ),
        "USER_AUTHORIZATION": (
            translation[
                "user_authorization_tr"
            ]
        ),
        "POLICY_CONTEXT": (
            policy_text_tr
        ),
        "ATTEMPTED_ACTION": (
            attempted_action_tr
        ),
    }


def make_compact_text(
    translation: dict[str, Any],
    attempted_action_tr: str,
) -> tuple[str, dict[str, Any]]:

    agent_values = parse_key_values(
        translation[
            "protected_agent_context"
        ]
    )

    source_values = parse_key_values(
        translation[
            "protected_source"
        ]
    )

    action_values = parse_key_values(
        attempted_action_tr
    )

    attempted_tool = action_values.get(
        "tool_name"
    )

    if not attempted_tool:
        raise ValueError(
            f"Missing attempted tool in "
            f"{translation['pair_id']}."
        )

    allowed_tools = {
        item.strip()
        for item in agent_values.get(
            "allowed_tools",
            "",
        ).split(",")
        if item.strip()
    }

    attempted_tool_allowed = (
        attempted_tool in allowed_tools
    )

    source_lines = []

    for field in (
        "trust_level",
        "source_type",
        "surface_type",
        "retrieval_channel",
    ):
        if field in source_values:
            source_lines.append(
                f"{field}="
                f"{source_values[field]}"
            )

    agent_facts = (
        f"agent_role="
        f"{agent_values.get('agent_role', 'unknown')}\n"
        f"attempted_tool_allowed="
        f"{str(attempted_tool_allowed).lower()}"
    )

    # USER_GOAL full structured artifact içinde korunur.
    # Compact BERT view'da ise daha kesin olan
    # USER_AUTHORIZATION alanıyla tekrar ettiği için çıkarılır.
    sections = {
        "USER_AUTHORIZATION": (
            translation[
                "user_authorization_tr"
            ]
        ),
        "ATTEMPTED_ACTION": (
            attempted_action_tr
        ),
        "RETRIEVED_CONTENT": (
            translation[
                "retrieved_content_tr"
            ]
        ),
        "SOURCE": "\n".join(
            source_lines
        ),
        "AGENT_FACTS": agent_facts,
    }

    order = (
        "USER_AUTHORIZATION",
        "ATTEMPTED_ACTION",
        "RETRIEVED_CONTENT",
        "SOURCE",
        "AGENT_FACTS",
    )

    text = serialize_sections(
        sections,
        order,
    )

    return (
        text,
        {
            "attempted_tool": attempted_tool,
            "attempted_tool_allowed": (
                attempted_tool_allowed
            ),
            "priority_order": list(order),
        },
    )


def localize_structured_row(
    canonical: dict[str, Any],
    translation: dict[str, Any],
    attempted_action_tr: str,
    full_text: str,
    full_sections: dict[str, str],
    policy_text_tr: str,
    split: str,
    label: int,
) -> dict[str, Any]:

    row = deepcopy(canonical)

    source_row_id = str(
        canonical["row_id"]
    )

    localized_row_id = (
        f"{source_row_id}::tr"
    )

    crosslingual_group_id = (
        f"agentdojo_crosslingual::"
        f"{translation['pair_id']}"
    )

    row["row_id"] = localized_row_id
    row["event_id"] = localized_row_id

    row["session_id"] = (
        f"{canonical['session_id']}::tr"
    )

    row["trace_id"] = (
        f"{canonical['trace_id']}::tr"
    )

    row["span_id"] = (
        f"{canonical['span_id']}::tr"
    )

    row["parent_span_id"] = (
        f"{canonical['parent_span_id']}::tr"
    )

    row["schema_version"] = (
        "action_attempt_context_tr_v0.2.6"
    )

    row["language"] = "tr"
    row["source_language"] = "en"
    row["split"] = split
    row["crosslingual_group_id"] = (
        crosslingual_group_id
    )
    row["source_row_id"] = source_row_id

    row["user_context"][
        "goal"
    ] = translation["user_goal_tr"]

    row["retrieval_context"][
        "content_redacted"
    ] = translation[
        "retrieved_content_tr"
    ]

    row["authorization_context"][
        "user_goal"
    ] = translation["user_goal_tr"]

    row["authorization_context"][
        "localized_serialized_authorization"
    ] = translation[
        "user_authorization_tr"
    ]

    row["policy_context"][
        "localized_policy_text"
    ] = policy_text_tr

    row["action"][
        "localized_serialized_action"
    ] = attempted_action_tr

    translated_args_expression = (
        line_value(
            attempted_action_tr,
            "args=",
        )
    )

    if translated_args_expression is not None:
        row["action"][
            "args_expression"
        ] = translated_args_expression

    parsed_args = try_literal_args(
        attempted_action_tr
    )

    if parsed_args is not None:
        row["action"]["args"] = parsed_args
        row["action"][
            "localized_args_parse_status"
        ] = "literal_eval_success"
    else:
        row["action"][
            "localized_args_parse_status"
        ] = "expression_preserved"

    shared_context_text = (
        serialize_sections(
            full_sections,
            SECTION_ORDER[:-1],
        )
    )

    row["model_input"] = {
        "serialization_version": (
            "agentdojo_turkish_full_v0.2.6"
        ),
        "included_sections": list(
            SECTION_ORDER
        ),
        "excluded_from_input": [
            "review",
            "label",
            "risk_score",
            "decision",
            "translation_review_metadata",
        ],
        "shared_context_fingerprint": (
            sha256_text(
                shared_context_text
            )
        ),
        "attempted_action_fingerprint": (
            sha256_text(
                attempted_action_tr
            )
        ),
        "text": full_text,
    }

    row["review"] = deepcopy(
        canonical["review"]
    )

    row["review"][
        "translation_approval"
    ] = {
        "decision": (
            translation[
                "human_review_decision"
            ]
        ),
        "translation_status": (
            translation[
                "translation_status"
            ]
        ),
        "human_review_version": (
            translation[
                "human_review_version"
            ]
        ),
    }

    canonical_label = int(
        row["review"][
            "final_binary_label"
        ]
    )

    if canonical_label != label:
        raise ValueError(
            f"Canonical label mismatch for "
            f"{source_row_id}: "
            f"{canonical_label} != {label}"
        )

    row["provenance"] = deepcopy(
        canonical["provenance"]
    )

    row["provenance"].update(
        {
            "translation_batch_id": (
                translation[
                    "translation_batch_id"
                ]
            ),
            "translation_artifact_version": (
                "v0.2.6"
            ),
            "translation_source_version": (
                translation[
                    "human_review_version"
                ]
            ),
            "translation_policy_template_id": (
                translation[
                    "policy_template_id"
                ]
            ),
            "source_language": "en",
            "target_language": "tr",
            "source_row_id": source_row_id,
            "crosslingual_group_id": (
                crosslingual_group_id
            ),
        }
    )

    row["important_note"] = (
        "This is a Turkish localized "
        "action.attempt row derived from the "
        "human-approved English AgentDojo "
        "canonical row. The model input does "
        "not contain labels, review decisions "
        "or policy-engine outputs."
    )

    return row


def main() -> None:

    source_hashes_before = {
        "translations": sha256_file(
            TRANSLATION_PATH
        ),
        "translation_report": sha256_file(
            TRANSLATION_REPORT_PATH
        ),
        "train_source": sha256_file(
            TRAIN_SOURCE_PATH
        ),
        "validation_source": sha256_file(
            VALIDATION_SOURCE_PATH
        ),
        "policy_registry": sha256_file(
            POLICY_REGISTRY_PATH
        ),
    }

    translations = load_jsonl(
        TRANSLATION_PATH
    )

    train_source = load_jsonl(
        TRAIN_SOURCE_PATH
    )

    validation_source = load_jsonl(
        VALIDATION_SOURCE_PATH
    )

    policy_rows = load_jsonl(
        POLICY_REGISTRY_PATH
    )

    if len(translations) != EXPECTED_PAIR_COUNT:
        raise ValueError(
            f"Expected 10 translation pairs, "
            f"found {len(translations)}."
        )

    for translation in translations:

        if (
            translation.get(
                "human_review_decision"
            )
            !=
            "approve_translation"
        ):
            raise ValueError(
                f"Translation not approved: "
                f"{translation['pair_id']}"
            )

        if (
            translation.get(
                "translation_status"
            )
            !=
            "human_reviewed_approved"
        ):
            raise ValueError(
                f"Unexpected translation status: "
                f"{translation['pair_id']}"
            )

        if translation["split"] == "test":
            raise ValueError(
                "Test translation entered "
                "Batch 001 materialization."
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
                "Unapproved policy template."
            )

    canonical_by_row_id = {}

    for split, rows in (
        ("train", train_source),
        ("validation", validation_source),
    ):

        for row in rows:

            row_id = str(row["row_id"])

            if row_id in canonical_by_row_id:
                raise ValueError(
                    f"Duplicate canonical row: "
                    f"{row_id}"
                )

            canonical_by_row_id[row_id] = (
                split,
                row,
            )

    structured_rows = []
    compact_rows = []

    sorted_translations = sorted(
        translations,
        key=lambda row: int(
            row["global_order"]
        ),
    )

    for translation in sorted_translations:

        pair_id = str(
            translation["pair_id"]
        )

        policy_template_id = str(
            translation[
                "policy_template_id"
            ]
        )

        if policy_template_id not in policy_by_id:
            raise ValueError(
                f"Unknown policy template for "
                f"{pair_id}: "
                f"{policy_template_id}"
            )

        policy_text_tr = str(
            policy_by_id[
                policy_template_id
            ][
                "policy_context_tr"
            ]
        )

        variant_specs = (
            (
                "safe",
                str(
                    translation[
                        "safe_row_id"
                    ]
                ),
                str(
                    translation[
                        "safe_attempted_action_tr"
                    ]
                ),
                0,
            ),
            (
                "risky",
                str(
                    translation[
                        "risky_row_id"
                    ]
                ),
                str(
                    translation[
                        "risky_attempted_action_tr"
                    ]
                ),
                1,
            ),
        )

        pair_shared_fingerprints = []

        for (
            expected_variant,
            source_row_id,
            attempted_action_tr,
            expected_label,
        ) in variant_specs:

            if source_row_id not in canonical_by_row_id:
                raise ValueError(
                    f"Canonical row not found: "
                    f"{source_row_id}"
                )

            canonical_split, canonical = (
                canonical_by_row_id[
                    source_row_id
                ]
            )

            if (
                canonical_split
                !=
                translation["split"]
            ):
                raise ValueError(
                    f"Split mismatch for "
                    f"{source_row_id}: "
                    f"{canonical_split} != "
                    f"{translation['split']}"
                )

            if (
                variant_name(canonical)
                !=
                expected_variant
            ):
                raise ValueError(
                    f"Variant mismatch for "
                    f"{source_row_id}."
                )

            canonical_label = int(
                canonical[
                    "review"
                ][
                    "final_binary_label"
                ]
            )

            if canonical_label != expected_label:
                raise ValueError(
                    f"Unexpected canonical label "
                    f"for {source_row_id}: "
                    f"{canonical_label}"
                )

            full_sections = make_full_sections(
                translation,
                attempted_action_tr,
                policy_text_tr,
            )

            full_text = serialize_sections(
                full_sections,
                SECTION_ORDER,
            )

            validate_no_leakage(
                full_text,
                source_row_id,
            )

            structured_row = (
                localize_structured_row(
                    canonical=canonical,
                    translation=translation,
                    attempted_action_tr=(
                        attempted_action_tr
                    ),
                    full_text=full_text,
                    full_sections=full_sections,
                    policy_text_tr=(
                        policy_text_tr
                    ),
                    split=canonical_split,
                    label=expected_label,
                )
            )

            compact_text, compact_metadata = (
                make_compact_text(
                    translation,
                    attempted_action_tr,
                )
            )

            validate_no_leakage(
                compact_text,
                source_row_id,
            )

            compact_row = {
                "schema_version": (
                    "agentdojo_turkish_bert_"
                    "compact_view_v0.2.6"
                ),
                "row_id": (
                    structured_row["row_id"]
                ),
                "source_row_id": (
                    source_row_id
                ),
                "pair_id": pair_id,
                "session_group_id": (
                    translation[
                        "session_group_id"
                    ]
                ),
                "crosslingual_group_id": (
                    structured_row[
                        "crosslingual_group_id"
                    ]
                ),
                "suite": (
                    translation["suite"]
                ),
                "split": canonical_split,
                "language": "tr",
                "source_language": "en",
                "variant": expected_variant,
                "text": compact_text,
                "text_sha256": (
                    sha256_text(
                        compact_text
                    )
                ),
                "general_risk_label": (
                    expected_label
                ),
                "label_source": (
                    canonical[
                        "review"
                    ][
                        "label_source"
                    ]
                ),
                "compact_serialization": {
                    "version": "v0.2.6",
                    "removed_sections": [
                        "USER_GOAL",
                        "CONTEXT_BINDINGS",
                        "POLICY_CONTEXT",
                        "full_allowed_tools",
                    ],
                    **compact_metadata,
                },
            }

            structured_rows.append(
                structured_row
            )

            compact_rows.append(
                compact_row
            )

            pair_shared_fingerprints.append(
                structured_row[
                    "model_input"
                ][
                    "shared_context_fingerprint"
                ]
            )

        if len(
            set(pair_shared_fingerprints)
        ) != 1:
            raise ValueError(
                f"Shared-context mismatch "
                f"inside {pair_id}."
            )

    if len(structured_rows) != EXPECTED_ROW_COUNT:
        raise ValueError(
            f"Expected 20 structured rows, "
            f"found {len(structured_rows)}."
        )

    if len(compact_rows) != EXPECTED_ROW_COUNT:
        raise ValueError(
            f"Expected 20 compact rows, "
            f"found {len(compact_rows)}."
        )

    structured_label_counts = Counter(
        int(
            row[
                "review"
            ][
                "final_binary_label"
            ]
        )
        for row in structured_rows
    )

    compact_label_counts = Counter(
        int(
            row[
                "general_risk_label"
            ]
        )
        for row in compact_rows
    )

    expected_labels = {
        0: 10,
        1: 10,
    }

    if dict(structured_label_counts) != (
        expected_labels
    ):
        raise ValueError(
            "Structured label imbalance: "
            f"{dict(structured_label_counts)}"
        )

    if dict(compact_label_counts) != (
        expected_labels
    ):
        raise ValueError(
            "Compact label imbalance: "
            f"{dict(compact_label_counts)}"
        )

    if len({
        row["row_id"]
        for row in structured_rows
    }) != EXPECTED_ROW_COUNT:
        raise ValueError(
            "Duplicate structured row IDs."
        )

    if len({
        row["text_sha256"]
        for row in compact_rows
    }) != EXPECTED_ROW_COUNT:
        raise ValueError(
            "Duplicate compact model inputs."
        )

    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_NAME,
        local_files_only=True,
    )

    original_model_max_length = (
        tokenizer.model_max_length
    )

    tokenizer.model_max_length = 1_000_000

    token_lengths = []

    for row in compact_rows:

        token_length = len(
            tokenizer(
                row["text"],
                add_special_tokens=True,
                truncation=False,
            )["input_ids"]
        )

        row["tokenization"] = {
            "tokenizer": MODEL_NAME,
            "token_length": token_length,
            "max_length": MAX_LENGTH,
            "requires_truncation": (
                token_length > MAX_LENGTH
            ),
        }

        token_lengths.append(
            token_length
        )

    tokenizer.model_max_length = (
        original_model_max_length
    )

    overflowing_rows = [
        {
            "row_id": row["row_id"],
            "pair_id": row["pair_id"],
            "variant": row["variant"],
            "token_length": (
                row["tokenization"][
                    "token_length"
                ]
            ),
        }
        for row in compact_rows
        if row[
            "tokenization"
        ][
            "requires_truncation"
        ]
    ]

    if overflowing_rows:

        print(
            json.dumps(
                {
                    "error": (
                        "compact_rows_exceed_512"
                    ),
                    "rows": overflowing_rows,
                },
                ensure_ascii=False,
                indent=2,
            )
        )

        raise ValueError(
            f"{len(overflowing_rows)} compact "
            f"rows exceed {MAX_LENGTH} tokens."
        )

    structured_train = [
        row
        for row in structured_rows
        if row["split"] == "train"
    ]

    structured_validation = [
        row
        for row in structured_rows
        if row["split"] == "validation"
    ]

    compact_train = [
        row
        for row in compact_rows
        if row["split"] == "train"
    ]

    compact_validation = [
        row
        for row in compact_rows
        if row["split"] == "validation"
    ]

    if (
        len(structured_train)
        !=
        len(compact_train)
    ):
        raise ValueError(
            "Train structured/compact "
            "count mismatch."
        )

    if (
        len(structured_validation)
        !=
        len(compact_validation)
    ):
        raise ValueError(
            "Validation structured/compact "
            "count mismatch."
        )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    write_jsonl(
        STRUCTURED_ALL_PATH,
        structured_rows,
    )

    write_jsonl(
        STRUCTURED_TRAIN_PATH,
        structured_train,
    )

    write_jsonl(
        STRUCTURED_VALIDATION_PATH,
        structured_validation,
    )

    write_jsonl(
        COMPACT_ALL_PATH,
        compact_rows,
    )

    write_jsonl(
        COMPACT_TRAIN_PATH,
        compact_train,
    )

    write_jsonl(
        COMPACT_VALIDATION_PATH,
        compact_validation,
    )

    source_hashes_after = {
        "translations": sha256_file(
            TRANSLATION_PATH
        ),
        "translation_report": sha256_file(
            TRANSLATION_REPORT_PATH
        ),
        "train_source": sha256_file(
            TRAIN_SOURCE_PATH
        ),
        "validation_source": sha256_file(
            VALIDATION_SOURCE_PATH
        ),
        "policy_registry": sha256_file(
            POLICY_REGISTRY_PATH
        ),
    }

    if source_hashes_before != (
        source_hashes_after
    ):
        raise ValueError(
            "A source artifact was modified."
        )

    split_pair_counts = Counter(
        str(row["split"])
        for row in translations
    )

    report = {
        "artifact_version": "0.2.5",
        "translation_batch_id": (
            "agentdojo_tr_batch_001"
        ),
        "model_name": MODEL_NAME,
        "max_length": MAX_LENGTH,
        "pair_count": (
            EXPECTED_PAIR_COUNT
        ),
        "structured_row_count": (
            len(structured_rows)
        ),
        "compact_row_count": (
            len(compact_rows)
        ),
        "label_counts": {
            str(key): value
            for key, value in sorted(
                compact_label_counts.items()
            )
        },
        "pair_split_counts": dict(
            sorted(
                split_pair_counts.items()
            )
        ),
        "runtime_split_counts": {
            "train": len(
                structured_train
            ),
            "validation": len(
                structured_validation
            ),
            "test": 0,
        },
        "suite_pair_counts": dict(
            Counter(
                str(row["suite"])
                for row in translations
            )
        ),
        "tokenization": {
            "minimum": min(
                token_lengths
            ),
            "maximum": max(
                token_lengths
            ),
            "mean": (
                sum(token_lengths)
                /
                len(token_lengths)
            ),
            "rows_over_512": 0,
            "truncated_rows": 0,
        },
        "validation": {
            "all_translations_approved": True,
            "policy_translation_approved": True,
            "safe_risky_pair_integrity": True,
            "shared_context_integrity": True,
            "label_balance": True,
            "duplicate_row_ids": 0,
            "duplicate_compact_inputs": 0,
            "input_leakage": 0,
            "crosslingual_links_present": True,
            "test_split_accessed": False,
            "source_artifacts_modified": False,
        },
        "source_hashes": (
            source_hashes_before
        ),
        "outputs": {
            "structured_all": str(
                STRUCTURED_ALL_PATH
            ),
            "structured_train": str(
                STRUCTURED_TRAIN_PATH
            ),
            "structured_validation": str(
                STRUCTURED_VALIDATION_PATH
            ),
            "compact_all": str(
                COMPACT_ALL_PATH
            ),
            "compact_train": str(
                COMPACT_TRAIN_PATH
            ),
            "compact_validation": str(
                COMPACT_VALIDATION_PATH
            ),
        },
        "important_note": (
            "This artifact contains only "
            "Batch 001 Turkish train and "
            "validation rows. The AgentDojo "
            "test split was not opened."
        ),
    }

    REPORT_PATH.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    manifest_files = (
        STRUCTURED_ALL_PATH,
        STRUCTURED_TRAIN_PATH,
        STRUCTURED_VALIDATION_PATH,
        COMPACT_ALL_PATH,
        COMPACT_TRAIN_PATH,
        COMPACT_VALIDATION_PATH,
        REPORT_PATH,
    )

    MANIFEST_PATH.write_text(
        "".join(
            f"{sha256_file(path)}  "
            f"{path.as_posix()}\n"
            for path in manifest_files
        ),
        encoding="utf-8",
    )

    for path in manifest_files:

        expected_hash = next(
            line.split()[0]
            for line in (
                MANIFEST_PATH.read_text(
                    encoding="utf-8"
                ).splitlines()
            )
            if path.as_posix() in line
        )

        if sha256_file(path) != (
            expected_hash
        ):
            raise ValueError(
                f"Manifest verification "
                f"failed: {path}"
            )

    print("=" * 80)

    print(
        "AGENTDOJO TURKISH BATCH 001 "
        "MATERIALIZATION v0.2.6 COMPLETED"
    )

    print("=" * 80)

    print()

    print(
        "Pairs:",
        EXPECTED_PAIR_COUNT,
    )

    print(
        "Structured rows:",
        len(structured_rows),
    )

    print(
        "Compact BERT rows:",
        len(compact_rows),
    )

    print(
        "Labels:",
        dict(
            compact_label_counts
        ),
    )

    print()

    print(
        "Train runtime rows:",
        len(structured_train),
    )

    print(
        "Validation runtime rows:",
        len(structured_validation),
    )

    print(
        "Test runtime rows:",
        0,
    )

    print()

    print(
        "Minimum compact tokens:",
        min(token_lengths),
    )

    print(
        "Maximum compact tokens:",
        max(token_lengths),
    )

    print(
        "Rows requiring truncation:",
        0,
    )

    print()

    print(
        "Duplicate structured IDs:",
        0,
    )

    print(
        "Duplicate compact inputs:",
        0,
    )

    print(
        "Input leakage:",
        0,
    )

    print(
        "Crosslingual links:",
        "present",
    )

    print()

    print(
        "Structured artifact:",
        STRUCTURED_ALL_PATH,
    )

    print(
        "Compact artifact:",
        COMPACT_ALL_PATH,
    )

    print(
        "Report:",
        REPORT_PATH,
    )

    print(
        "SHA-256 manifest:",
        MANIFEST_PATH,
    )

    print()

    print(
        "Source artifacts modified: no"
    )

    print(
        "Test split accessed: no"
    )

    print(
        "Materialization: PASSED"
    )


if __name__ == "__main__":
    main()

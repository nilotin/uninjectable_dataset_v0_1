from __future__ import annotations

import hashlib
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from transformers import AutoTokenizer


SOURCE_PATH = Path(
    "data/processed/agentdojo_turkish_pilot_v0.1.3/"
    "agentdojo_turkish_contextual_action_attempt_pilot_v0.1.3.jsonl"
)
OUTPUT_DIRECTORY = Path(
    "data/processed/agentdojo_turkish_pilot_v0.2.6"
)
OUTPUT_ALL_PATH = OUTPUT_DIRECTORY / "agentdojo_turkish_pilot_bert_compact_v0.2.6.jsonl"
OUTPUT_TRAIN_PATH = OUTPUT_DIRECTORY / "agentdojo_turkish_pilot_bert_compact_v0.2.6_train.jsonl"
OUTPUT_VALIDATION_PATH = OUTPUT_DIRECTORY / "agentdojo_turkish_pilot_bert_compact_v0.2.6_validation.jsonl"
OUTPUT_REPORT_PATH = OUTPUT_DIRECTORY / "agentdojo_turkish_pilot_v0.2.6_report.json"
OUTPUT_MANIFEST_PATH = OUTPUT_DIRECTORY / "agentdojo_turkish_pilot_v0.2.6_sha256.txt"

TOKENIZER_NAME = "google-bert/bert-base-multilingual-cased"
MAX_LENGTH = 512

EXPECTED_ROWS = 24
EXPECTED_TRAIN_ROWS = 16
EXPECTED_VALIDATION_ROWS = 8
EXPECTED_LABEL_COUNTS = {0: 12, 1: 12}
EXPECTED_PAIR_COUNT = 12

SOURCE_FIELDS = (
    "trust_level",
    "source_type",
    "surface_type",
    "retrieval_channel",
)

FORBIDDEN_INPUT_MARKERS = (
    "general_risk_label",
    "human_review_decision",
    "approve_translation",
    "translation_status",
    "label_source",
    "reviewer_note",
)

COMPACT_ORDER = (
    "USER_AUTHORIZATION",
    "ATTEMPTED_ACTION",
    "RETRIEVED_CONTENT",
    "SOURCE",
    "AGENT_FACTS",
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
                    f"Invalid JSONL in {path} at line {line_number}."
                ) from error
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False))
            file.write("\n")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_key_values(section: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in section.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def serialize_sections(
    sections: dict[str, str],
    order: tuple[str, ...],
) -> str:
    blocks: list[str] = []
    for name in order:
        value = str(sections.get(name, "")).strip()
        if not value:
            raise ValueError(f"Empty compact section: {name}")
        blocks.append(f"[{name}]\n{value}")
    return "\n\n".join(blocks)


def validate_no_leakage(text: str, row_id: str) -> None:
    lowered = text.lower()
    for marker in FORBIDDEN_INPUT_MARKERS:
        if marker.lower() in lowered:
            raise ValueError(
                f"Input leakage detected in {row_id}: {marker}"
            )


def make_compact_text(
    source_row: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    row_id = str(source_row["row_id"])
    sections = source_row["sections"]

    agent_values = parse_key_values(str(sections["agent_context"]))
    source_values = parse_key_values(str(sections["source"]))
    action_values = parse_key_values(str(sections["attempted_action"]))

    attempted_tool = action_values.get("tool_name")
    if not attempted_tool:
        raise ValueError(f"Missing attempted tool in {row_id}.")

    allowed_tools = {
        item.strip()
        for item in agent_values.get("allowed_tools", "").split(",")
        if item.strip()
    }
    attempted_tool_allowed = attempted_tool in allowed_tools

    source_lines = [
        f"{field}={source_values[field]}"
        for field in SOURCE_FIELDS
        if field in source_values
    ]
    if not source_lines:
        raise ValueError(f"No source facts found in {row_id}.")

    agent_facts = (
        f"agent_role={agent_values.get('agent_role', 'unknown')}\n"
        f"attempted_tool_allowed={str(attempted_tool_allowed).lower()}"
    )

    compact_sections = {
        "USER_AUTHORIZATION": str(sections["user_authorization"]),
        "ATTEMPTED_ACTION": str(sections["attempted_action"]),
        "RETRIEVED_CONTENT": str(sections["retrieved_content"]),
        "SOURCE": "\n".join(source_lines),
        "AGENT_FACTS": agent_facts,
    }

    text = serialize_sections(compact_sections, COMPACT_ORDER)
    return (
        text,
        {
            "attempted_tool": attempted_tool,
            "attempted_tool_allowed": attempted_tool_allowed,
            "priority_order": list(COMPACT_ORDER),
        },
    )


def variant_name(row: dict[str, Any]) -> str:
    variant = row.get("variant")
    if isinstance(variant, dict):
        variant = variant.get("name")
    return str(variant)


def make_compact_row(source_row: dict[str, Any]) -> dict[str, Any]:
    row_id = str(source_row["row_id"])
    compact_text, compact_metadata = make_compact_text(source_row)
    validate_no_leakage(compact_text, row_id)

    return {
        "schema_version": "agentdojo_turkish_bert_compact_view_v0.2.6",
        "row_id": row_id,
        "source_row_id": str(source_row["source_row_id"]),
        "pair_id": str(source_row["pair_id"]),
        "source_pair_id": str(source_row["source_pair_id"]),
        "session_group_id": str(source_row["session_group_id"]),
        "crosslingual_group_id": str(source_row["crosslingual_group_id"]),
        "suite": str(source_row["suite"]),
        "split": str(source_row["split"]),
        "language": "tr",
        "source_language": "en",
        "variant": variant_name(source_row),
        "text": compact_text,
        "text_sha256": sha256_text(compact_text),
        "general_risk_label": int(
            source_row["label"]["general_risk_label"]
        ),
        "label_source": str(source_row["label"]["label_source"]),
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
        "provenance": {
            "source_artifact": str(SOURCE_PATH),
            "source_schema_version": str(
                source_row.get("schema_version")
            ),
            "source_artifact_version": str(
                source_row.get("artifact_version")
            ),
            "migration_script": (
                "scripts/"
                "migrate_agentdojo_turkish_pilot_"
                "compact_to_v0_2_6.py"
            ),
            "structured_source_modified": False,
        },
    }


def validate_rows(
    source_rows: list[dict[str, Any]],
    compact_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    if len(source_rows) != EXPECTED_ROWS:
        raise ValueError(
            f"Expected {EXPECTED_ROWS} source rows, "
            f"found {len(source_rows)}."
        )
    if len(compact_rows) != EXPECTED_ROWS:
        raise ValueError(
            f"Expected {EXPECTED_ROWS} compact rows, "
            f"found {len(compact_rows)}."
        )

    row_ids = [row["row_id"] for row in compact_rows]
    if len(set(row_ids)) != len(row_ids):
        raise ValueError("Duplicate compact row IDs.")

    text_hashes = [row["text_sha256"] for row in compact_rows]
    if len(set(text_hashes)) != len(text_hashes):
        raise ValueError("Duplicate compact model inputs.")

    label_counts = Counter(
        int(row["general_risk_label"])
        for row in compact_rows
    )
    if dict(label_counts) != EXPECTED_LABEL_COUNTS:
        raise ValueError(
            f"Unexpected label counts: {dict(label_counts)}"
        )

    split_counts = Counter(str(row["split"]) for row in compact_rows)
    if split_counts.get("train", 0) != EXPECTED_TRAIN_ROWS:
        raise ValueError(
            f"Expected {EXPECTED_TRAIN_ROWS} train rows, "
            f"found {split_counts.get('train', 0)}."
        )
    if split_counts.get("validation", 0) != EXPECTED_VALIDATION_ROWS:
        raise ValueError(
            f"Expected {EXPECTED_VALIDATION_ROWS} validation rows, "
            f"found {split_counts.get('validation', 0)}."
        )
    if split_counts.get("test", 0):
        raise ValueError("Test row entered Turkish pilot migration.")

    pairs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in compact_rows:
        pairs[str(row["pair_id"])].append(row)

    if len(pairs) != EXPECTED_PAIR_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_PAIR_COUNT} pairs, found {len(pairs)}."
        )

    for pair_id, rows in pairs.items():
        if len(rows) != 2:
            raise ValueError(
                f"Pair {pair_id} does not contain two rows."
            )
        if {
            int(row["general_risk_label"]) for row in rows
        } != {0, 1}:
            raise ValueError(f"Pair {pair_id} is not label-balanced.")
        if {str(row["variant"]) for row in rows} != {"safe", "risky"}:
            raise ValueError(
                f"Pair {pair_id} has invalid variants."
            )
        if len({str(row["split"]) for row in rows}) != 1:
            raise ValueError(f"Pair {pair_id} crosses splits.")
        if len({
            str(row["session_group_id"]) for row in rows
        }) != 1:
            raise ValueError(
                f"Pair {pair_id} crosses session groups."
            )
        if len({
            str(row["crosslingual_group_id"]) for row in rows
        }) != 1:
            raise ValueError(
                f"Pair {pair_id} has inconsistent "
                f"crosslingual links."
            )

    source_by_row_id = {
        str(row["row_id"]): row
        for row in source_rows
    }
    for compact_row in compact_rows:
        source_row = source_by_row_id[str(compact_row["row_id"])]
        if compact_row["general_risk_label"] != int(
            source_row["label"]["general_risk_label"]
        ):
            raise ValueError(
                f"Label mismatch for {compact_row['row_id']}."
            )
        if compact_row["split"] != source_row["split"]:
            raise ValueError(
                f"Split mismatch for {compact_row['row_id']}."
            )

    return {
        "label_counts": dict(label_counts),
        "split_counts": dict(split_counts),
        "pair_count": len(pairs),
        "duplicate_row_ids": 0,
        "duplicate_model_inputs": 0,
        "input_leakage": 0,
        "test_rows": 0,
        "crosslingual_links": "present",
    }


def analyze_token_lengths(
    compact_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    tokenizer = AutoTokenizer.from_pretrained(TOKENIZER_NAME)

    original_max_length = tokenizer.model_max_length
    tokenizer.model_max_length = 1_000_000

    lengths: list[int] = []
    per_row: list[dict[str, Any]] = []

    for row in compact_rows:
        token_count = len(
            tokenizer(
                row["text"],
                add_special_tokens=True,
                truncation=False,
            )["input_ids"]
        )
        lengths.append(token_count)
        per_row.append(
            {
                "row_id": row["row_id"],
                "pair_id": row["pair_id"],
                "split": row["split"],
                "variant": row["variant"],
                "token_count": token_count,
                "requires_truncation": token_count > MAX_LENGTH,
            }
        )

    tokenizer.model_max_length = original_max_length

    overflow = [
        row for row in per_row
        if row["requires_truncation"]
    ]
    if overflow:
        details = ", ".join(
            f"{row['row_id']}={row['token_count']}"
            for row in overflow
        )
        raise ValueError(
            "Compact pilot rows exceed max_length=512: "
            f"{details}"
        )

    return {
        "tokenizer": TOKENIZER_NAME,
        "max_length": MAX_LENGTH,
        "minimum": min(lengths),
        "mean": statistics.mean(lengths),
        "median": statistics.median(lengths),
        "maximum": max(lengths),
        "rows_requiring_truncation": 0,
        "per_row": per_row,
    }


def write_manifest(paths: list[Path]) -> None:
    OUTPUT_MANIFEST_PATH.write_text(
        "".join(
            f"{sha256_file(path)}  {path.name}\n"
            for path in paths
        ),
        encoding="utf-8",
    )


def main() -> None:
    source_hash_before = sha256_file(SOURCE_PATH)

    source_rows = load_jsonl(SOURCE_PATH)
    compact_rows = [
        make_compact_row(row)
        for row in source_rows
    ]
    compact_rows.sort(
        key=lambda row: (
            row["split"],
            row["suite"],
            row["pair_id"],
            row["variant"],
        )
    )

    validation = validate_rows(source_rows, compact_rows)
    token_analysis = analyze_token_lengths(compact_rows)

    train_rows = [
        row for row in compact_rows
        if row["split"] == "train"
    ]
    validation_rows = [
        row for row in compact_rows
        if row["split"] == "validation"
    ]

    write_jsonl(OUTPUT_ALL_PATH, compact_rows)
    write_jsonl(OUTPUT_TRAIN_PATH, train_rows)
    write_jsonl(OUTPUT_VALIDATION_PATH, validation_rows)

    source_hash_after = sha256_file(SOURCE_PATH)
    if source_hash_before != source_hash_after:
        raise RuntimeError(
            "Canonical structured pilot source was modified."
        )

    report = {
        "artifact_version": "0.2.6",
        "migration_type": "compact_serialization_only",
        "source_artifact": str(SOURCE_PATH),
        "source_sha256_before": source_hash_before,
        "source_sha256_after": source_hash_after,
        "source_artifact_modified": False,
        "structured_rows_rewritten": False,
        "compact_schema_version": (
            "agentdojo_turkish_bert_compact_view_v0.2.6"
        ),
        "compact_order": list(COMPACT_ORDER),
        "removed_sections": [
            "USER_GOAL",
            "CONTEXT_BINDINGS",
            "POLICY_CONTEXT",
            "full_allowed_tools",
        ],
        "row_count": len(compact_rows),
        "train_row_count": len(train_rows),
        "validation_row_count": len(validation_rows),
        "test_row_count": 0,
        "validation": validation,
        "tokenizer_analysis": token_analysis,
        "outputs": {
            "all": str(OUTPUT_ALL_PATH),
            "train": str(OUTPUT_TRAIN_PATH),
            "validation": str(OUTPUT_VALIDATION_PATH),
            "report": str(OUTPUT_REPORT_PATH),
            "manifest": str(OUTPUT_MANIFEST_PATH),
        },
        "important_note": (
            "The canonical Turkish structured pilot artifact was not "
            "modified. Only the compact BERT model view was regenerated "
            "under the v0.2.6 serialization contract."
        ),
    }

    OUTPUT_REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    write_manifest(
        [
            OUTPUT_ALL_PATH,
            OUTPUT_TRAIN_PATH,
            OUTPUT_VALIDATION_PATH,
            OUTPUT_REPORT_PATH,
        ]
    )

    print("=" * 80)
    print(
        "AGENTDOJO TURKISH PILOT COMPACT "
        "MIGRATION v0.2.6 COMPLETED"
    )
    print("=" * 80)
    print()
    print("Rows:", len(compact_rows))
    print("Pairs:", validation["pair_count"])
    print(
        "Train / validation:",
        len(train_rows),
        "/",
        len(validation_rows),
    )
    print("Labels:", validation["label_counts"])
    print()
    print(
        "Minimum compact tokens:",
        token_analysis["minimum"],
    )
    print(
        "Maximum compact tokens:",
        token_analysis["maximum"],
    )
    print(
        "Rows requiring truncation:",
        token_analysis["rows_requiring_truncation"],
    )
    print()
    print("Duplicate row IDs: 0")
    print("Duplicate compact inputs: 0")
    print("Input leakage: 0")
    print("Crosslingual links: present")
    print("Test split accessed: no")
    print("Structured source modified: no")
    print()
    print("Compact artifact:", OUTPUT_ALL_PATH)
    print("Train artifact:", OUTPUT_TRAIN_PATH)
    print("Validation artifact:", OUTPUT_VALIDATION_PATH)
    print("Report:", OUTPUT_REPORT_PATH)
    print("SHA-256 manifest:", OUTPUT_MANIFEST_PATH)
    print()
    print("Migration: PASSED")


if __name__ == "__main__":
    main()

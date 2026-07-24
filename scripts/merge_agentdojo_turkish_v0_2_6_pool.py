from __future__ import annotations

import hashlib
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from transformers import AutoTokenizer


PILOT_PATH = Path(
    "data/processed/"
    "agentdojo_turkish_pilot_v0.2.6/"
    "agentdojo_turkish_pilot_bert_compact_v0.2.6.jsonl"
)

BATCH_001_PATH = Path(
    "data/processed/"
    "agentdojo_turkish_batch_001_v0.2.6/"
    "agentdojo_turkish_batch_001_bert_compact_v0.2.6.jsonl"
)

OUTPUT_DIRECTORY = Path(
    "data/processed/"
    "agentdojo_turkish_combined_v0.2.6"
)

OUTPUT_ALL_PATH = (
    OUTPUT_DIRECTORY
    / "agentdojo_turkish_combined_bert_compact_v0.2.6.jsonl"
)
OUTPUT_TRAIN_PATH = (
    OUTPUT_DIRECTORY
    / "agentdojo_turkish_combined_bert_compact_v0.2.6_train.jsonl"
)
OUTPUT_VALIDATION_PATH = (
    OUTPUT_DIRECTORY
    / "agentdojo_turkish_combined_bert_compact_v0.2.6_validation.jsonl"
)
OUTPUT_REPORT_PATH = (
    OUTPUT_DIRECTORY
    / "agentdojo_turkish_combined_v0.2.6_report.json"
)
OUTPUT_MANIFEST_PATH = (
    OUTPUT_DIRECTORY
    / "agentdojo_turkish_combined_v0.2.6_sha256.txt"
)

TOKENIZER_NAME = "google-bert/bert-base-multilingual-cased"
MAX_LENGTH = 512

EXPECTED_SCHEMA = "agentdojo_turkish_bert_compact_view_v0.2.6"
EXPECTED_SERIALIZATION_VERSION = "v0.2.6"
EXPECTED_PRIORITY_ORDER = [
    "USER_AUTHORIZATION",
    "ATTEMPTED_ACTION",
    "RETRIEVED_CONTENT",
    "SOURCE",
    "AGENT_FACTS",
]
EXPECTED_REMOVED_SECTIONS = [
    "USER_GOAL",
    "CONTEXT_BINDINGS",
    "POLICY_CONTEXT",
    "full_allowed_tools",
]

EXPECTED_TOTAL_ROWS = 44
EXPECTED_TRAIN_ROWS = 32
EXPECTED_VALIDATION_ROWS = 12
EXPECTED_TEST_ROWS = 0
EXPECTED_PAIR_COUNT = 22
EXPECTED_LABEL_COUNTS = {0: 22, 1: 22}
EXPECTED_SOURCE_COUNTS = {
    "pilot": 24,
    "batch_001": 20,
}

FORBIDDEN_INPUT_MARKERS = (
    "general_risk_label",
    "human_review_decision",
    "approve_translation",
    "translation_status",
    "label_source",
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


def validate_input_leakage(text: str, row_id: str) -> None:
    lowered = text.lower()
    for marker in FORBIDDEN_INPUT_MARKERS:
        if marker.lower() in lowered:
            raise ValueError(
                f"Input leakage detected in {row_id}: {marker}"
            )


def validate_source_rows(
    rows: list[dict[str, Any]],
    source_name: str,
) -> None:
    expected_count = EXPECTED_SOURCE_COUNTS[source_name]
    if len(rows) != expected_count:
        raise ValueError(
            f"{source_name}: expected {expected_count} rows, "
            f"found {len(rows)}."
        )

    for row in rows:
        row_id = str(row.get("row_id", "<missing-row-id>"))

        if row.get("schema_version") != EXPECTED_SCHEMA:
            raise ValueError(
                f"{source_name}: schema mismatch in {row_id}: "
                f"{row.get('schema_version')}"
            )

        if row.get("language") != "tr":
            raise ValueError(
                f"{source_name}: non-Turkish row: {row_id}"
            )

        if row.get("source_language") != "en":
            raise ValueError(
                f"{source_name}: unexpected source language: {row_id}"
            )

        split = row.get("split")
        if split not in {"train", "validation"}:
            raise ValueError(
                f"{source_name}: invalid or sealed split in "
                f"{row_id}: {split}"
            )

        variant = row.get("variant")
        if variant not in {"safe", "risky"}:
            raise ValueError(
                f"{source_name}: invalid variant in {row_id}: "
                f"{variant}"
            )

        label = int(row.get("general_risk_label"))
        expected_label = 0 if variant == "safe" else 1
        if label != expected_label:
            raise ValueError(
                f"{source_name}: variant/label mismatch in {row_id}."
            )

        text = str(row.get("text", ""))
        if not text:
            raise ValueError(
                f"{source_name}: empty model input in {row_id}."
            )

        calculated_hash = sha256_text(text)
        if calculated_hash != row.get("text_sha256"):
            raise ValueError(
                f"{source_name}: text SHA mismatch in {row_id}."
            )

        validate_input_leakage(text, row_id)

        serialization = row.get("compact_serialization")
        if not isinstance(serialization, dict):
            raise ValueError(
                f"{source_name}: missing compact serialization "
                f"metadata in {row_id}."
            )

        if (
            serialization.get("version")
            != EXPECTED_SERIALIZATION_VERSION
        ):
            raise ValueError(
                f"{source_name}: serialization version mismatch "
                f"in {row_id}."
            )

        if (
            serialization.get("priority_order")
            != EXPECTED_PRIORITY_ORDER
        ):
            raise ValueError(
                f"{source_name}: compact order mismatch in "
                f"{row_id}."
            )

        if (
            serialization.get("removed_sections")
            != EXPECTED_REMOVED_SECTIONS
        ):
            raise ValueError(
                f"{source_name}: removed-section contract "
                f"mismatch in {row_id}."
            )


def normalize_row(
    row: dict[str, Any],
    source_name: str,
    tokenizer: Any,
) -> dict[str, Any]:
    normalized = dict(row)

    token_count = len(
        tokenizer(
            normalized["text"],
            add_special_tokens=True,
            truncation=False,
        )["input_ids"]
    )
    requires_truncation = token_count > MAX_LENGTH

    if requires_truncation:
        raise ValueError(
            f"Row exceeds max_length={MAX_LENGTH}: "
            f"{normalized['row_id']} ({token_count} tokens)"
        )

    normalized["tokenization"] = {
        "tokenizer": TOKENIZER_NAME,
        "token_length": token_count,
        "max_length": MAX_LENGTH,
        "requires_truncation": False,
    }

    provenance = normalized.get("provenance")
    if not isinstance(provenance, dict):
        provenance = {}

    normalized["merge_provenance"] = {
        "combined_artifact_version": "v0.2.6",
        "source_partition": source_name,
        "source_artifact": (
            str(PILOT_PATH)
            if source_name == "pilot"
            else str(BATCH_001_PATH)
        ),
        "source_row_sha256": sha256_text(
            json.dumps(
                row,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        ),
        "existing_provenance_preserved": bool(provenance),
    }

    return normalized


def validate_merged_rows(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    if len(rows) != EXPECTED_TOTAL_ROWS:
        raise ValueError(
            f"Expected {EXPECTED_TOTAL_ROWS} merged rows, "
            f"found {len(rows)}."
        )

    row_ids = [str(row["row_id"]) for row in rows]
    if len(set(row_ids)) != len(row_ids):
        duplicates = sorted(
            row_id
            for row_id, count in Counter(row_ids).items()
            if count > 1
        )
        raise ValueError(
            f"Duplicate row IDs across sources: {duplicates}"
        )

    text_hashes = [str(row["text_sha256"]) for row in rows]
    if len(set(text_hashes)) != len(text_hashes):
        duplicates = sorted(
            text_hash
            for text_hash, count in Counter(text_hashes).items()
            if count > 1
        )
        raise ValueError(
            "Duplicate compact model inputs across sources: "
            f"{duplicates}"
        )

    split_counts = Counter(str(row["split"]) for row in rows)
    expected_split_counts = {
        "train": EXPECTED_TRAIN_ROWS,
        "validation": EXPECTED_VALIDATION_ROWS,
    }
    if dict(split_counts) != expected_split_counts:
        raise ValueError(
            f"Unexpected split counts: {dict(split_counts)}"
        )

    label_counts = Counter(
        int(row["general_risk_label"])
        for row in rows
    )
    if dict(label_counts) != EXPECTED_LABEL_COUNTS:
        raise ValueError(
            f"Unexpected label counts: {dict(label_counts)}"
        )

    source_counts = Counter(
        str(row["merge_provenance"]["source_partition"])
        for row in rows
    )
    if dict(source_counts) != EXPECTED_SOURCE_COUNTS:
        raise ValueError(
            f"Unexpected source counts: {dict(source_counts)}"
        )

    pairs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        pairs[str(row["pair_id"])].append(row)

    if len(pairs) != EXPECTED_PAIR_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_PAIR_COUNT} pairs, "
            f"found {len(pairs)}."
        )

    session_group_to_splits: dict[str, set[str]] = defaultdict(set)
    crosslingual_group_to_splits: dict[str, set[str]] = defaultdict(set)

    for pair_id, pair_rows in pairs.items():
        if len(pair_rows) != 2:
            raise ValueError(
                f"Pair {pair_id} does not contain exactly two rows."
            )

        if {
            int(row["general_risk_label"])
            for row in pair_rows
        } != {0, 1}:
            raise ValueError(
                f"Pair {pair_id} is not label-balanced."
            )

        if {
            str(row["variant"])
            for row in pair_rows
        } != {"safe", "risky"}:
            raise ValueError(
                f"Pair {pair_id} lacks safe/risky variants."
            )

        if len({
            str(row["split"])
            for row in pair_rows
        }) != 1:
            raise ValueError(
                f"Pair {pair_id} crosses train/validation splits."
            )

        if len({
            str(row["session_group_id"])
            for row in pair_rows
        }) != 1:
            raise ValueError(
                f"Pair {pair_id} crosses session groups."
            )

        if len({
            str(row["crosslingual_group_id"])
            for row in pair_rows
        }) != 1:
            raise ValueError(
                f"Pair {pair_id} has inconsistent "
                f"crosslingual groups."
            )

    for row in rows:
        session_group_to_splits[
            str(row["session_group_id"])
        ].add(str(row["split"]))

        crosslingual_group_to_splits[
            str(row["crosslingual_group_id"])
        ].add(str(row["split"]))

    session_leakage = {
        group_id: sorted(splits)
        for group_id, splits in session_group_to_splits.items()
        if len(splits) > 1
    }
    if session_leakage:
        raise ValueError(
            f"Session-group split leakage: {session_leakage}"
        )

    crosslingual_leakage = {
        group_id: sorted(splits)
        for group_id, splits
        in crosslingual_group_to_splits.items()
        if len(splits) > 1
    }
    if crosslingual_leakage:
        raise ValueError(
            "Crosslingual-group split leakage: "
            f"{crosslingual_leakage}"
        )

    token_lengths = [
        int(row["tokenization"]["token_length"])
        for row in rows
    ]

    return {
        "row_count": len(rows),
        "pair_count": len(pairs),
        "source_counts": dict(source_counts),
        "split_counts": dict(split_counts),
        "label_counts": dict(label_counts),
        "duplicate_row_ids": 0,
        "duplicate_model_inputs": 0,
        "session_group_split_leakage": 0,
        "crosslingual_group_split_leakage": 0,
        "input_leakage": 0,
        "test_rows": EXPECTED_TEST_ROWS,
        "token_lengths": {
            "minimum": min(token_lengths),
            "mean": statistics.mean(token_lengths),
            "median": statistics.median(token_lengths),
            "maximum": max(token_lengths),
            "rows_requiring_truncation": 0,
        },
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
    source_hashes_before = {
        "pilot": sha256_file(PILOT_PATH),
        "batch_001": sha256_file(BATCH_001_PATH),
    }

    pilot_rows = load_jsonl(PILOT_PATH)
    batch_rows = load_jsonl(BATCH_001_PATH)

    validate_source_rows(pilot_rows, "pilot")
    validate_source_rows(batch_rows, "batch_001")

    pilot_row_ids = {
        str(row["row_id"])
        for row in pilot_rows
    }
    batch_row_ids = {
        str(row["row_id"])
        for row in batch_rows
    }
    row_id_overlap = pilot_row_ids & batch_row_ids
    if row_id_overlap:
        raise ValueError(
            f"Row-ID overlap between source pools: "
            f"{sorted(row_id_overlap)}"
        )

    tokenizer = AutoTokenizer.from_pretrained(TOKENIZER_NAME)
    original_max_length = tokenizer.model_max_length
    tokenizer.model_max_length = 1_000_000

    try:
        merged_rows = [
            normalize_row(row, "pilot", tokenizer)
            for row in pilot_rows
        ] + [
            normalize_row(row, "batch_001", tokenizer)
            for row in batch_rows
        ]
    finally:
        tokenizer.model_max_length = original_max_length

    split_order = {
        "train": 0,
        "validation": 1,
    }
    variant_order = {
        "safe": 0,
        "risky": 1,
    }

    merged_rows.sort(
        key=lambda row: (
            split_order[str(row["split"])],
            str(row["suite"]),
            str(row["pair_id"]),
            variant_order[str(row["variant"])],
            str(row["row_id"]),
        )
    )

    validation = validate_merged_rows(merged_rows)

    train_rows = [
        row for row in merged_rows
        if row["split"] == "train"
    ]
    validation_rows = [
        row for row in merged_rows
        if row["split"] == "validation"
    ]

    write_jsonl(OUTPUT_ALL_PATH, merged_rows)
    write_jsonl(OUTPUT_TRAIN_PATH, train_rows)
    write_jsonl(
        OUTPUT_VALIDATION_PATH,
        validation_rows,
    )

    source_hashes_after = {
        "pilot": sha256_file(PILOT_PATH),
        "batch_001": sha256_file(BATCH_001_PATH),
    }
    if source_hashes_before != source_hashes_after:
        raise RuntimeError(
            "At least one source artifact was modified."
        )

    report = {
        "artifact_version": "0.2.6",
        "artifact_type": (
            "combined_turkish_compact_bert_pool"
        ),
        "schema_version": EXPECTED_SCHEMA,
        "serialization_version": (
            EXPECTED_SERIALIZATION_VERSION
        ),
        "tokenizer": TOKENIZER_NAME,
        "max_length": MAX_LENGTH,
        "sources": {
            "pilot": {
                "path": str(PILOT_PATH),
                "row_count": len(pilot_rows),
                "sha256_before": (
                    source_hashes_before["pilot"]
                ),
                "sha256_after": (
                    source_hashes_after["pilot"]
                ),
                "modified": False,
            },
            "batch_001": {
                "path": str(BATCH_001_PATH),
                "row_count": len(batch_rows),
                "sha256_before": (
                    source_hashes_before["batch_001"]
                ),
                "sha256_after": (
                    source_hashes_after["batch_001"]
                ),
                "modified": False,
            },
        },
        "compact_contract": {
            "priority_order": (
                EXPECTED_PRIORITY_ORDER
            ),
            "removed_sections": (
                EXPECTED_REMOVED_SECTIONS
            ),
        },
        "validation": validation,
        "outputs": {
            "all": str(OUTPUT_ALL_PATH),
            "train": str(OUTPUT_TRAIN_PATH),
            "validation": str(
                OUTPUT_VALIDATION_PATH
            ),
            "report": str(OUTPUT_REPORT_PATH),
            "sha256_manifest": str(
                OUTPUT_MANIFEST_PATH
            ),
        },
        "important_note": (
            "The pilot and Batch 001 source artifacts "
            "were validated and left unchanged. The "
            "combined pool contains no sealed test rows."
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
        "AGENTDOJO TURKISH COMBINED "
        "COMPACT POOL v0.2.6 CREATED"
    )
    print("=" * 80)
    print()
    print("Sources:")
    print("  Pilot:", len(pilot_rows))
    print("  Batch 001:", len(batch_rows))
    print()
    print("Rows:", validation["row_count"])
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
        "Minimum tokens:",
        validation["token_lengths"]["minimum"],
    )
    print(
        "Maximum tokens:",
        validation["token_lengths"]["maximum"],
    )
    print(
        "Rows requiring truncation:",
        validation[
            "token_lengths"
        ][
            "rows_requiring_truncation"
        ],
    )
    print()
    print("Duplicate row IDs: 0")
    print("Duplicate compact inputs: 0")
    print("Session-group split leakage: 0")
    print("Crosslingual-group split leakage: 0")
    print("Input leakage: 0")
    print("Test rows: 0")
    print("Source artifacts modified: no")
    print()
    print("Combined artifact:", OUTPUT_ALL_PATH)
    print("Train artifact:", OUTPUT_TRAIN_PATH)
    print(
        "Validation artifact:",
        OUTPUT_VALIDATION_PATH,
    )
    print("Report:", OUTPUT_REPORT_PATH)
    print("SHA-256 manifest:", OUTPUT_MANIFEST_PATH)
    print()
    print("Merge validation: PASSED")


if __name__ == "__main__":
    main()

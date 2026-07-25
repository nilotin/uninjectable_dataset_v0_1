from __future__ import annotations

import hashlib
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from transformers import AutoTokenizer


PRIOR_COMBINED_PATH = Path(
    "data/processed/"
    "agentdojo_turkish_combined_through_batch_003_v0.2.6/"
    "agentdojo_turkish_combined_through_batch_003_bert_compact_v0.2.6.jsonl"
)

BATCH_004_PATH = Path(
    "data/processed/"
    "agentdojo_turkish_batch_004_v0.2.6/"
    "agentdojo_turkish_batch_004_bert_compact_v0.2.6.jsonl"
)

OUTPUT_DIR = Path(
    "data/processed/"
    "agentdojo_turkish_combined_through_batch_004_v0.2.6"
)

OUTPUT_ALL = (
    OUTPUT_DIR
    / "agentdojo_turkish_combined_through_batch_004_bert_compact_v0.2.6.jsonl"
)
OUTPUT_TRAIN = (
    OUTPUT_DIR
    / "agentdojo_turkish_combined_through_batch_004_bert_compact_v0.2.6_train.jsonl"
)
OUTPUT_VALIDATION = (
    OUTPUT_DIR
    / "agentdojo_turkish_combined_through_batch_004_bert_compact_v0.2.6_validation.jsonl"
)
OUTPUT_REPORT = (
    OUTPUT_DIR
    / "agentdojo_turkish_combined_through_batch_004_v0.2.6_report.json"
)
OUTPUT_MANIFEST = (
    OUTPUT_DIR
    / "agentdojo_turkish_combined_through_batch_004_v0.2.6_sha256.txt"
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

EXPECTED_SOURCE_COUNTS = {
    "through_batch_003": 82,
    "batch_004": 20,
}
EXPECTED_TOTAL_ROWS = 102
EXPECTED_PAIR_COUNT = 51
EXPECTED_SPLIT_COUNTS = {
    "train": 82,
    "validation": 20,
}
EXPECTED_LABEL_COUNTS = {
    0: 51,
    1: 51,
}

FORBIDDEN_INPUT_MARKERS = (
    "general_risk_label",
    "human_review_decision",
    "approve_translation",
    "translation_status",
    "label_source",
    "reviewer_note",
    "risk_score",
    "final_binary_label",
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
                f"{source_name}: unexpected source language in {row_id}"
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
                f"{source_name}: variant/label mismatch in {row_id}"
            )

        text = str(row.get("text", ""))
        if not text:
            raise ValueError(
                f"{source_name}: empty text in {row_id}"
            )

        if sha256_text(text) != row.get("text_sha256"):
            raise ValueError(
                f"{source_name}: text SHA mismatch in {row_id}"
            )

        lowered = text.lower()
        for marker in FORBIDDEN_INPUT_MARKERS:
            if marker.lower() in lowered:
                raise ValueError(
                    f"{source_name}: input leakage in "
                    f"{row_id}: {marker}"
                )

        serialization = row.get("compact_serialization")
        if not isinstance(serialization, dict):
            raise ValueError(
                f"{source_name}: missing compact metadata in {row_id}"
            )

        if (
            serialization.get("version")
            != EXPECTED_SERIALIZATION_VERSION
        ):
            raise ValueError(
                f"{source_name}: serialization version mismatch "
                f"in {row_id}"
            )

        if (
            serialization.get("priority_order")
            != EXPECTED_PRIORITY_ORDER
        ):
            raise ValueError(
                f"{source_name}: priority order mismatch in {row_id}"
            )

        if (
            serialization.get("removed_sections")
            != EXPECTED_REMOVED_SECTIONS
        ):
            raise ValueError(
                f"{source_name}: removed sections mismatch in {row_id}"
            )


def normalize_row(
    row: dict[str, Any],
    source_name: str,
    source_path: Path,
    tokenizer: Any,
) -> dict[str, Any]:
    normalized = dict(row)

    token_length = len(
        tokenizer(
            normalized["text"],
            add_special_tokens=True,
            truncation=False,
        )["input_ids"]
    )

    if token_length > MAX_LENGTH:
        raise ValueError(
            f"Row exceeds max_length={MAX_LENGTH}: "
            f"{normalized['row_id']} ({token_length} tokens)"
        )

    normalized["tokenization"] = {
        "tokenizer": TOKENIZER_NAME,
        "token_length": token_length,
        "max_length": MAX_LENGTH,
        "requires_truncation": False,
    }

    previous_merge = normalized.get("merge_provenance")

    normalized["merge_provenance"] = {
        "combined_artifact_version": (
            "v0.2.6-through-batch-003"
        ),
        "source_partition": source_name,
        "source_artifact": str(source_path),
        "source_row_sha256": sha256_text(
            json.dumps(
                row,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        ),
        "previous_merge_provenance_preserved": (
            previous_merge
            if isinstance(previous_merge, dict)
            else None
        ),
    }

    return normalized


def validate_merged_rows(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    if len(rows) != EXPECTED_TOTAL_ROWS:
        raise ValueError(
            f"Expected {EXPECTED_TOTAL_ROWS} rows, "
            f"found {len(rows)}."
        )

    row_ids = [str(row["row_id"]) for row in rows]
    duplicate_row_ids = sorted(
        row_id
        for row_id, count in Counter(row_ids).items()
        if count > 1
    )
    if duplicate_row_ids:
        raise ValueError(
            f"Duplicate row IDs: {duplicate_row_ids}"
        )

    text_hashes = [str(row["text_sha256"]) for row in rows]
    duplicate_inputs = sorted(
        value
        for value, count in Counter(text_hashes).items()
        if count > 1
    )
    if duplicate_inputs:
        duplicate_details: dict[str, list[str]] = {}
        for duplicate_hash in duplicate_inputs:
            duplicate_details[duplicate_hash] = [
                str(row["row_id"])
                for row in rows
                if str(row["text_sha256"]) == duplicate_hash
            ]
        raise ValueError(
            "Duplicate compact model inputs across merged pool: "
            f"{duplicate_details}"
        )

    split_counts = Counter(
        str(row["split"]) for row in rows
    )
    if dict(split_counts) != EXPECTED_SPLIT_COUNTS:
        raise ValueError(
            f"Unexpected split counts: {dict(split_counts)}"
        )

    label_counts = Counter(
        int(row["general_risk_label"]) for row in rows
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

    session_to_splits: dict[str, set[str]] = defaultdict(set)
    crosslingual_to_splits: dict[str, set[str]] = defaultdict(set)

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
            str(row["variant"]) for row in pair_rows
        } != {"safe", "risky"}:
            raise ValueError(
                f"Pair {pair_id} lacks safe/risky variants."
            )

        if len({
            str(row["split"]) for row in pair_rows
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
                "crosslingual groups."
            )

    for row in rows:
        session_to_splits[
            str(row["session_group_id"])
        ].add(str(row["split"]))

        crosslingual_to_splits[
            str(row["crosslingual_group_id"])
        ].add(str(row["split"]))

    session_leakage = {
        key: sorted(value)
        for key, value in session_to_splits.items()
        if len(value) > 1
    }
    if session_leakage:
        raise ValueError(
            f"Session-group split leakage: {session_leakage}"
        )

    crosslingual_leakage = {
        key: sorted(value)
        for key, value in crosslingual_to_splits.items()
        if len(value) > 1
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
        "test_rows": 0,
        "token_lengths": {
            "minimum": min(token_lengths),
            "mean": statistics.mean(token_lengths),
            "median": statistics.median(token_lengths),
            "maximum": max(token_lengths),
            "rows_requiring_truncation": 0,
        },
    }


def write_manifest(paths: list[Path]) -> None:
    OUTPUT_MANIFEST.write_text(
        "".join(
            f"{sha256_file(path)}  {path.name}\n"
            for path in paths
        ),
        encoding="utf-8",
    )


def main() -> None:
    source_hashes_before = {
        "through_batch_003": sha256_file(
            PRIOR_COMBINED_PATH
        ),
        "batch_004": sha256_file(BATCH_004_PATH),
    }

    prior_rows = load_jsonl(PRIOR_COMBINED_PATH)
    batch_004_rows = load_jsonl(BATCH_004_PATH)

    validate_source_rows(
        prior_rows,
        "through_batch_003",
    )
    validate_source_rows(
        batch_004_rows,
        "batch_004",
    )

    tokenizer = AutoTokenizer.from_pretrained(
        TOKENIZER_NAME
    )
    original_max_length = tokenizer.model_max_length
    tokenizer.model_max_length = 1_000_000

    try:
        merged_rows = [
            normalize_row(
                row,
                "through_batch_003",
                PRIOR_COMBINED_PATH,
                tokenizer,
            )
            for row in prior_rows
        ] + [
            normalize_row(
                row,
                "batch_004",
                BATCH_004_PATH,
                tokenizer,
            )
            for row in batch_004_rows
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
        row
        for row in merged_rows
        if row["split"] == "train"
    ]
    validation_rows = [
        row
        for row in merged_rows
        if row["split"] == "validation"
    ]

    if len(train_rows) != EXPECTED_SPLIT_COUNTS["train"]:
        raise ValueError(
            f"Unexpected train count: {len(train_rows)}"
        )

    if (
        len(validation_rows)
        != EXPECTED_SPLIT_COUNTS["validation"]
    ):
        raise ValueError(
            "Unexpected validation count: "
            f"{len(validation_rows)}"
        )

    source_hashes_after = {
        "through_batch_003": sha256_file(
            PRIOR_COMBINED_PATH
        ),
        "batch_004": sha256_file(BATCH_004_PATH),
    }

    if source_hashes_before != source_hashes_after:
        raise RuntimeError(
            "One or more source artifacts were modified."
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    write_jsonl(OUTPUT_ALL, merged_rows)
    write_jsonl(OUTPUT_TRAIN, train_rows)
    write_jsonl(
        OUTPUT_VALIDATION,
        validation_rows,
    )

    report = {
        "artifact_version": (
            "agentdojo_turkish_combined_"
            "through_batch_004_v0.2.6"
        ),
        "schema_version": EXPECTED_SCHEMA,
        "serialization_version": (
            EXPECTED_SERIALIZATION_VERSION
        ),
        "tokenizer": TOKENIZER_NAME,
        "max_length": MAX_LENGTH,
        "sources": {
            "through_batch_003": {
                "path": str(PRIOR_COMBINED_PATH),
                "row_count": len(prior_rows),
                "sha256_before": source_hashes_before[
                    "through_batch_003"
                ],
                "sha256_after": source_hashes_after[
                    "through_batch_003"
                ],
                "modified": False,
            },
            "batch_004": {
                "path": str(BATCH_004_PATH),
                "row_count": len(batch_004_rows),
                "sha256_before": source_hashes_before[
                    "batch_004"
                ],
                "sha256_after": source_hashes_after[
                    "batch_004"
                ],
                "modified": False,
            },
        },
        "validation": validation,
        "outputs": {
            "all": str(OUTPUT_ALL),
            "train": str(OUTPUT_TRAIN),
            "validation": str(OUTPUT_VALIDATION),
            "sha256_manifest": str(OUTPUT_MANIFEST),
        },
        "sealed_test_split_accessed": False,
    }

    OUTPUT_REPORT.write_text(
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
            OUTPUT_ALL,
            OUTPUT_TRAIN,
            OUTPUT_VALIDATION,
            OUTPUT_REPORT,
        ]
    )

    print("=" * 80)
    print(
        "AGENTDOJO TURKISH COMBINED THROUGH "
        "BATCH 004 v0.2.6"
    )
    print("=" * 80)
    print()
    print(
        "Prior combined rows:",
        len(prior_rows),
    )
    print(
        "Batch 004 rows:",
        len(batch_004_rows),
    )
    print("Combined rows:", len(merged_rows))
    print("Pairs:", validation["pair_count"])
    print("Train rows:", len(train_rows))
    print(
        "Validation rows:",
        len(validation_rows),
    )
    print("Test rows: 0")
    print("Labels:", validation["label_counts"])
    print(
        "Source counts:",
        validation["source_counts"],
    )
    print()
    print(
        "Minimum compact tokens:",
        validation["token_lengths"]["minimum"],
    )
    print(
        "Maximum compact tokens:",
        validation["token_lengths"]["maximum"],
    )
    print(
        "Rows requiring truncation:",
        validation["token_lengths"][
            "rows_requiring_truncation"
        ],
    )
    print()
    print("Duplicate row IDs: 0")
    print("Duplicate compact inputs: 0")
    print("Session-group leakage: 0")
    print("Crosslingual-group leakage: 0")
    print("Input leakage: 0")
    print("Source artifacts modified: no")
    print("Test split accessed: no")
    print()
    print("Combined artifact:", OUTPUT_ALL)
    print("Train artifact:", OUTPUT_TRAIN)
    print(
        "Validation artifact:",
        OUTPUT_VALIDATION,
    )
    print("Report:", OUTPUT_REPORT)
    print("SHA-256 manifest:", OUTPUT_MANIFEST)
    print()
    print("Combined pool merge: PASSED")


if __name__ == "__main__":
    main()

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


PACKAGE_DIR = Path(
    "data/processed/"
    "agentdojo_turkish_training_package_v0.2.0"
)

TRAIN_PATH = (
    PACKAGE_DIR
    / "agentdojo_turkish_training_v0.2.0_train.jsonl"
)

VALIDATION_PATH = (
    PACKAGE_DIR
    / "agentdojo_turkish_training_v0.2.0_validation.jsonl"
)

METADATA_PATH = (
    PACKAGE_DIR
    / "agentdojo_turkish_training_v0.2.0_metadata.json"
)

MANIFEST_PATH = (
    PACKAGE_DIR
    / "agentdojo_turkish_training_v0.2.0_sha256.txt"
)

CONFIG_PATH = Path(
    "configs/training/"
    "mbert_turkish_baseline_v0.2.0.json"
)

SOURCE_DIR = Path(
    "data/processed/"
    "agentdojo_turkish_corpus_v0.4.0"
)

SOURCE_TRAIN_PATH = (
    SOURCE_DIR
    / "agentdojo_turkish_corpus_v0.4.0_train.jsonl"
)

SOURCE_VALIDATION_PATH = (
    SOURCE_DIR
    / "agentdojo_turkish_corpus_v0.4.0_validation.jsonl"
)

EXPECTED_FIELDS = {
    "label",
    "language",
    "pair_id",
    "row_id",
    "session_group_id",
    "source_text_sha256",
    "split",
    "suite",
    "text",
    "variant",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def canonical_pair_id(pair_id: str) -> str:
    if pair_id.endswith("_tr"):
        return pair_id[:-3]

    return pair_id


def parse_manifest(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}

    for line in path.read_text(
        encoding="utf-8"
    ).splitlines():
        if not line.strip():
            continue

        digest, filename = line.split(
            None,
            1,
        )

        entries[filename.strip()] = digest.strip()

    return entries


def validate_split(
    rows: list[dict[str, Any]],
    split: str,
    expected_rows: int,
    expected_pairs: int,
) -> None:
    if len(rows) != expected_rows:
        raise ValueError(
            f"{split}: expected {expected_rows} rows, "
            f"found {len(rows)}"
        )

    grouped: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)

    row_ids = []
    texts = []

    for row in rows:
        if set(row) != EXPECTED_FIELDS:
            raise ValueError(
                f"{row.get('row_id')}: schema mismatch; "
                f"keys={sorted(row)}"
            )

        if row["split"] != split:
            raise ValueError(
                f"{row['row_id']}: split mismatch"
            )

        if row["language"] != "tr":
            raise ValueError(
                f"{row['row_id']}: invalid language"
            )

        if row["variant"] not in {
            "safe",
            "risky",
        }:
            raise ValueError(
                f"{row['row_id']}: invalid variant"
            )

        expected_label = (
            0
            if row["variant"] == "safe"
            else 1
        )

        if int(row["label"]) != expected_label:
            raise ValueError(
                f"{row['row_id']}: label/variant mismatch"
            )

        observed_hash = hashlib.sha256(
            row["text"].encode("utf-8")
        ).hexdigest()

        if (
            observed_hash
            != row["source_text_sha256"]
        ):
            raise ValueError(
                f"{row['row_id']}: source text hash mismatch"
            )

        row_ids.append(row["row_id"])
        texts.append(row["text"])
        grouped[row["pair_id"]].append(row)

    if len(row_ids) != len(set(row_ids)):
        raise ValueError(
            f"{split}: duplicate row IDs"
        )

    if len(texts) != len(set(texts)):
        raise ValueError(
            f"{split}: duplicate inputs"
        )

    if len(grouped) != expected_pairs:
        raise ValueError(
            f"{split}: expected {expected_pairs} pairs, "
            f"found {len(grouped)}"
        )

    for pair_id, members in grouped.items():
        if len(members) != 2:
            raise ValueError(
                f"{pair_id}: expected 2 rows"
            )

        if {
            row["variant"]
            for row in members
        } != {
            "safe",
            "risky",
        }:
            raise ValueError(
                f"{pair_id}: invalid variants"
            )

        if {
            int(row["label"])
            for row in members
        } != {
            0,
            1,
        }:
            raise ValueError(
                f"{pair_id}: invalid labels"
            )

        if len({
            row["session_group_id"]
            for row in members
        }) != 1:
            raise ValueError(
                f"{pair_id}: session group mismatch"
            )


def main() -> None:
    train_rows = load_jsonl(TRAIN_PATH)
    validation_rows = load_jsonl(
        VALIDATION_PATH
    )

    source_train_rows = load_jsonl(
        SOURCE_TRAIN_PATH
    )

    source_validation_rows = load_jsonl(
        SOURCE_VALIDATION_PATH
    )

    validate_split(
        train_rows,
        split="train",
        expected_rows=170,
        expected_pairs=85,
    )

    validate_split(
        validation_rows,
        split="validation",
        expected_rows=42,
        expected_pairs=21,
    )

    train_pairs = {
        row["pair_id"]
        for row in train_rows
    }

    validation_pairs = {
        row["pair_id"]
        for row in validation_rows
    }

    if train_pairs & validation_pairs:
        raise ValueError(
            "Train/validation pair leakage"
        )

    train_sessions = {
        row["session_group_id"]
        for row in train_rows
    }

    validation_sessions = {
        row["session_group_id"]
        for row in validation_rows
    }

    if train_sessions & validation_sessions:
        raise ValueError(
            "Train/validation session leakage"
        )

    source_by_id = {
        row["row_id"]: row
        for row in (
            source_train_rows
            + source_validation_rows
        )
    }

    source_preservation_failures = []

    for row in train_rows + validation_rows:
        source = source_by_id.get(
            row["row_id"]
        )

        if source is None:
            source_preservation_failures.append(
                f"{row['row_id']}:missing"
            )
            continue

        checks = {
            "pair_id": row["pair_id"],
            "session_group_id": (
                row["session_group_id"]
            ),
            "suite": row["suite"],
            "variant": row["variant"],
            "language": row["language"],
            "split": row["split"],
            "text": row["text"],
            "label": row["label"],
            "source_text_sha256": (
                row["source_text_sha256"]
            ),
        }

        expected = {
            "pair_id": canonical_pair_id(
                str(source["pair_id"])
            ),
            "session_group_id": (
                source["session_group_id"]
            ),
            "suite": source["suite"],
            "variant": source["variant"],
            "language": source["language"],
            "split": source["split"],
            "text": source["text"],
            "label": source[
                "general_risk_label"
            ],
            "source_text_sha256": (
                source["text_sha256"]
            ),
        }

        if checks != expected:
            source_preservation_failures.append(
                f"{row['row_id']}:modified"
            )

    if source_preservation_failures:
        raise ValueError(
            "Source preservation failures: "
            f"{source_preservation_failures[:20]}"
        )

    metadata = json.loads(
        METADATA_PATH.read_text(
            encoding="utf-8"
        )
    )

    expected_metadata = {
        "package": (
            "agentdojo_turkish_training_"
            "package_v0.2.0"
        ),
        "source_corpus": (
            "agentdojo_turkish_corpus_v0.4.0"
        ),
        "config_path": str(CONFIG_PATH),
        "model_name": (
            "google-bert/"
            "bert-base-multilingual-cased"
        ),
        "task_type": (
            "binary_sequence_classification"
        ),
    }

    metadata_failures = {
        key: {
            "expected": expected,
            "observed": metadata.get(key),
        }
        for key, expected
        in expected_metadata.items()
        if metadata.get(key) != expected
    }

    if metadata_failures:
        raise ValueError(
            "Metadata failures: "
            f"{metadata_failures}"
        )

    source_hashes = metadata[
        "source_hashes"
    ]

    observed_source_hashes = {
        "config": sha256_file(CONFIG_PATH),
        "train": sha256_file(
            SOURCE_TRAIN_PATH
        ),
        "validation": sha256_file(
            SOURCE_VALIDATION_PATH
        ),
    }

    if source_hashes != observed_source_hashes:
        raise ValueError(
            "Source hash failures"
        )

    manifest = parse_manifest(
        MANIFEST_PATH
    )

    expected_manifest_files = {
        TRAIN_PATH.name: TRAIN_PATH,
        VALIDATION_PATH.name: (
            VALIDATION_PATH
        ),
        METADATA_PATH.name: METADATA_PATH,
    }

    if (
        set(manifest)
        != set(expected_manifest_files)
    ):
        raise ValueError(
            "Manifest file set mismatch"
        )

    manifest_failures = []

    for filename, path in (
        expected_manifest_files.items()
    ):
        if manifest[filename] != sha256_file(path):
            manifest_failures.append(
                filename
            )

    if manifest_failures:
        raise ValueError(
            "Manifest failures: "
            f"{manifest_failures}"
        )

    train_labels = Counter(
        int(row["label"])
        for row in train_rows
    )

    validation_labels = Counter(
        int(row["label"])
        for row in validation_rows
    )

    print("=" * 80)
    print(
        "AGENTDOJO TURKISH TRAINING "
        "PACKAGE v0.2.0 VALIDATION"
    )
    print("=" * 80)
    print()
    print("Train rows:", len(train_rows))
    print("Train pairs:", len(train_pairs))
    print("Train labels:", dict(train_labels))
    print()
    print(
        "Validation rows:",
        len(validation_rows),
    )
    print(
        "Validation pairs:",
        len(validation_pairs),
    )
    print(
        "Validation labels:",
        dict(validation_labels),
    )
    print()
    print("Schema signatures: 1")
    print("Duplicate row IDs: 0")
    print("Duplicate inputs: 0")
    print("Pair integrity failures: 0")
    print("Pair split leakage: 0")
    print("Session-group leakage: 0")
    print("Source preservation failures: 0")
    print("Source hash failures: 0")
    print("Manifest failures: 0")
    print("Test split accessed: no")
    print()
    print(
        "Training package v0.2.0 "
        "validation: PASSED"
    )


if __name__ == "__main__":
    main()

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


BASE_DIR = Path(
    "data/processed/"
    "agentdojo_turkish_corpus_v0.3.0"
)

EXPANSION_DIR = Path(
    "data/planning/"
    "agentdojo_turkish_argument_mismatch_expansion_v0.1.0"
)

EXPANSION_NAME = (
    "agentdojo_turkish_argument_mismatch_expansion_v0.1.0"
)

EXPANSION_ALL_PATH = (
    EXPANSION_DIR
    / f"{EXPANSION_NAME}.jsonl"
)

EXPANSION_TRAIN_PATH = (
    EXPANSION_DIR
    / f"{EXPANSION_NAME}_train.jsonl"
)

EXPANSION_VALIDATION_PATH = (
    EXPANSION_DIR
    / f"{EXPANSION_NAME}_validation.jsonl"
)

MERGE_PLAN_DIR = Path(
    "data/planning/"
    "agentdojo_turkish_corpus_v0.4.0_merge_plan"
)

BASE_SNAPSHOT_PATH = (
    MERGE_PLAN_DIR
    / "agentdojo_turkish_corpus_v0.3.0_immutable_snapshot_sha256.txt"
)

OUTPUT_DIR = Path(
    "data/processed/"
    "agentdojo_turkish_corpus_v0.4.0"
)

ARTIFACT_NAME = (
    "agentdojo_turkish_corpus_v0.4.0"
)

ALL_PATH = (
    OUTPUT_DIR
    / f"{ARTIFACT_NAME}.jsonl"
)

TRAIN_PATH = (
    OUTPUT_DIR
    / f"{ARTIFACT_NAME}_train.jsonl"
)

VALIDATION_PATH = (
    OUTPUT_DIR
    / f"{ARTIFACT_NAME}_validation.jsonl"
)

METADATA_PATH = (
    OUTPUT_DIR
    / f"{ARTIFACT_NAME}_metadata.json"
)

SHA_PATH = (
    OUTPUT_DIR
    / f"{ARTIFACT_NAME}_sha256.txt"
)

REQUIRED_COMMON_FIELDS = {
    "row_id",
    "pair_id",
    "split",
    "suite",
    "language",
    "source_language",
    "session_group_id",
    "variant",
    "text",
    "text_sha256",
    "general_risk_label",
    "label_source",
    "schema_version",
    "tokenization",
    "merge_provenance",
    "crosslingual_group_id",
}

LEGACY_ONLY_FIELDS = {
    "compact_serialization",
    "provenance",
    "source_row_id",
    "source_pair_id",
}

EXPANSION_ONLY_FIELDS = {
    "category",
    "changed_argument_paths",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(path)

    return [
        json.loads(line)
        for line in path.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


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


def locate_base_split(split: str) -> Path:
    matches = sorted(
        path
        for path in BASE_DIR.glob("*.jsonl")
        if split in path.stem.lower()
    )

    if len(matches) != 1:
        raise ValueError(
            f"Expected exactly one base {split} JSONL, "
            f"found: {matches}"
        )

    return matches[0]


def normalize_text(text: str) -> str:
    return re.sub(
        r"\s+",
        " ",
        text.strip(),
    )


def token_count(row: dict[str, Any]) -> int:
    tokenization = row["tokenization"]

    for field in (
        "token_count",
        "token_length",
        "unpadded_length",
        "input_length",
        "sequence_length",
        "length",
    ):
        value = tokenization.get(field)

        if isinstance(value, int):
            return value

    input_ids = tokenization.get("input_ids")

    if isinstance(input_ids, list):
        return len(input_ids)

    raise ValueError(
        f"{row.get('row_id')}: token count field "
        f"not found; tokenization keys="
        f"{sorted(tokenization)}"
    )


def row_is_truncated(row: dict[str, Any]) -> bool:
    tokenization = row["tokenization"]

    for field in (
        "truncated",
        "requires_truncation",
        "was_truncated",
        "is_truncated",
    ):
        if field in tokenization:
            return bool(tokenization[field])

    return token_count(row) > int(
        tokenization.get(
            "max_length",
            512,
        )
    )


def canonical_row(row: dict[str, Any]) -> str:
    return json.dumps(
        row,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def validate_base_snapshot() -> None:
    snapshot = parse_manifest(
        BASE_SNAPSHOT_PATH
    )

    base_files = sorted(
        path
        for path in BASE_DIR.iterdir()
        if path.is_file()
    )

    expected_names = {
        path.name
        for path in base_files
    }

    if set(snapshot) != expected_names:
        raise ValueError(
            "Base immutable snapshot file set mismatch"
        )

    failures = []

    for path in base_files:
        if snapshot[path.name] != sha256(path):
            failures.append(path.name)

    if failures:
        raise ValueError(
            "Base immutable checksum failures: "
            f"{failures}"
        )


def validate_artifact_manifest() -> None:
    manifest = parse_manifest(SHA_PATH)

    artifact_files = {
        ALL_PATH.name: ALL_PATH,
        TRAIN_PATH.name: TRAIN_PATH,
        VALIDATION_PATH.name: VALIDATION_PATH,
        METADATA_PATH.name: METADATA_PATH,
    }

    if set(manifest) != set(artifact_files):
        raise ValueError(
            "Artifact manifest file set mismatch"
        )

    failures = []

    for filename, path in artifact_files.items():
        if manifest[filename] != sha256(path):
            failures.append(filename)

    if failures:
        raise ValueError(
            "Artifact SHA failures: "
            f"{failures}"
        )


def main() -> None:
    validate_base_snapshot()

    base_train_path = locate_base_split(
        "train"
    )

    base_validation_path = locate_base_split(
        "validation"
    )

    base_train_rows = load_jsonl(
        base_train_path
    )

    base_validation_rows = load_jsonl(
        base_validation_path
    )

    base_rows = (
        base_train_rows
        + base_validation_rows
    )

    expansion_rows = load_jsonl(
        EXPANSION_ALL_PATH
    )

    expansion_train_rows = load_jsonl(
        EXPANSION_TRAIN_PATH
    )

    expansion_validation_rows = load_jsonl(
        EXPANSION_VALIDATION_PATH
    )

    rows = load_jsonl(ALL_PATH)
    train_rows = load_jsonl(TRAIN_PATH)
    validation_rows = load_jsonl(
        VALIDATION_PATH
    )

    metadata = json.loads(
        METADATA_PATH.read_text(
            encoding="utf-8"
        )
    )

    if len(rows) != 212:
        raise ValueError(
            f"Expected 212 rows, found {len(rows)}"
        )

    if len(train_rows) != 170:
        raise ValueError(
            f"Expected 170 train rows, "
            f"found {len(train_rows)}"
        )

    if len(validation_rows) != 42:
        raise ValueError(
            f"Expected 42 validation rows, "
            f"found {len(validation_rows)}"
        )

    grouped: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)

    for row in rows:
        grouped[str(row["pair_id"])].append(row)

    if len(grouped) != 106:
        raise ValueError(
            f"Expected 106 pairs, found {len(grouped)}"
        )

    pair_integrity_failures = []
    split_failures = []
    label_variant_failures = []

    for pair_id, members in grouped.items():
        if len(members) != 2:
            pair_integrity_failures.append(
                pair_id
            )
            continue

        variants = Counter(
            str(row["variant"])
            for row in members
        )

        labels = Counter(
            int(row["general_risk_label"])
            for row in members
        )

        splits = {
            str(row["split"])
            for row in members
        }

        if variants != {
            "safe": 1,
            "risky": 1,
        }:
            pair_integrity_failures.append(
                pair_id
            )

        if labels != {
            0: 1,
            1: 1,
        }:
            pair_integrity_failures.append(
                pair_id
            )

        if len(splits) != 1:
            split_failures.append(
                pair_id
            )

        for row in members:
            variant = str(row["variant"])
            label = int(
                row["general_risk_label"]
            )

            if (
                variant == "safe"
                and label != 0
            ):
                label_variant_failures.append(
                    str(row["row_id"])
                )

            if (
                variant == "risky"
                and label != 1
            ):
                label_variant_failures.append(
                    str(row["row_id"])
                )

    if pair_integrity_failures:
        raise ValueError(
            "Pair integrity failures: "
            f"{sorted(set(pair_integrity_failures))}"
        )

    if split_failures:
        raise ValueError(
            "Pair split failures: "
            f"{sorted(split_failures)}"
        )

    if label_variant_failures:
        raise ValueError(
            "Label/variant failures: "
            f"{sorted(label_variant_failures)}"
        )

    row_ids = [
        str(row["row_id"])
        for row in rows
    ]

    if len(row_ids) != len(set(row_ids)):
        raise ValueError(
            "Duplicate row IDs detected"
        )

    normalized_texts = [
        normalize_text(str(row["text"]))
        for row in rows
    ]

    if len(normalized_texts) != len(
        set(normalized_texts)
    ):
        raise ValueError(
            "Duplicate exact compact inputs detected"
        )

    train_pair_ids = {
        str(row["pair_id"])
        for row in train_rows
    }

    validation_pair_ids = {
        str(row["pair_id"])
        for row in validation_rows
    }

    pair_leakage = (
        train_pair_ids
        & validation_pair_ids
    )

    if pair_leakage:
        raise ValueError(
            "Train/validation pair leakage: "
            f"{sorted(pair_leakage)}"
        )

    train_texts = {
        normalize_text(str(row["text"]))
        for row in train_rows
    }

    validation_texts = {
        normalize_text(str(row["text"]))
        for row in validation_rows
    }

    text_leakage = (
        train_texts
        & validation_texts
    )

    if text_leakage:
        raise ValueError(
            "Train/validation exact-text leakage: "
            f"{len(text_leakage)}"
        )

    expected_train_ids = {
        str(row["row_id"])
        for row in rows
        if row["split"] == "train"
    }

    observed_train_ids = {
        str(row["row_id"])
        for row in train_rows
    }

    if expected_train_ids != observed_train_ids:
        raise ValueError(
            "Train artifact membership mismatch"
        )

    expected_validation_ids = {
        str(row["row_id"])
        for row in rows
        if row["split"] == "validation"
    }

    observed_validation_ids = {
        str(row["row_id"])
        for row in validation_rows
    }

    if (
        expected_validation_ids
        != observed_validation_ids
    ):
        raise ValueError(
            "Validation artifact membership mismatch"
        )

    target_by_id = {
        str(row["row_id"]): row
        for row in rows
    }

    base_preservation_failures = []

    for source_row in base_rows:
        row_id = str(source_row["row_id"])
        target_row = target_by_id.get(row_id)

        if target_row is None:
            base_preservation_failures.append(
                f"{row_id}:missing"
            )
            continue

        if (
            canonical_row(source_row)
            != canonical_row(target_row)
        ):
            base_preservation_failures.append(
                f"{row_id}:modified"
            )

    if base_preservation_failures:
        raise ValueError(
            "Base row preservation failures: "
            f"{base_preservation_failures[:20]}"
        )

    expansion_preservation_failures = []

    for source_row in expansion_rows:
        row_id = str(source_row["row_id"])
        target_row = target_by_id.get(row_id)

        if target_row is None:
            expansion_preservation_failures.append(
                f"{row_id}:missing"
            )
            continue

        if (
            canonical_row(source_row)
            != canonical_row(target_row)
        ):
            expansion_preservation_failures.append(
                f"{row_id}:modified"
            )

    if expansion_preservation_failures:
        raise ValueError(
            "Expansion row preservation failures: "
            f"{expansion_preservation_failures[:20]}"
        )

    for row in rows:
        missing_required = (
            REQUIRED_COMMON_FIELDS
            - set(row)
        )

        if missing_required:
            raise ValueError(
                f"{row['row_id']}: missing required "
                f"fields {sorted(missing_required)}"
            )

        crosslingual = row[
            "crosslingual_group_id"
        ]

        if not (
            crosslingual is None
            or isinstance(crosslingual, str)
        ):
            raise ValueError(
                f"{row['row_id']}: invalid "
                "crosslingual_group_id type"
            )

    base_row_ids = {
        str(row["row_id"])
        for row in base_rows
    }

    expansion_row_ids = {
        str(row["row_id"])
        for row in expansion_rows
    }

    for row in rows:
        row_id = str(row["row_id"])

        if row_id in base_row_ids:
            unexpected = (
                EXPANSION_ONLY_FIELDS
                & set(row)
            )

            if unexpected:
                raise ValueError(
                    f"{row_id}: synthetic expansion "
                    f"fields {sorted(unexpected)}"
                )

        elif row_id in expansion_row_ids:
            unexpected = (
                LEGACY_ONLY_FIELDS
                & set(row)
            )

            if unexpected:
                raise ValueError(
                    f"{row_id}: synthetic legacy "
                    f"fields {sorted(unexpected)}"
                )

        else:
            raise ValueError(
                f"{row_id}: unknown source row"
            )

    text_hash_failures = []

    for row in rows:
        observed = hashlib.sha256(
            str(row["text"]).encode("utf-8")
        ).hexdigest()

        if observed != row["text_sha256"]:
            text_hash_failures.append(
                str(row["row_id"])
            )

    if text_hash_failures:
        raise ValueError(
            "text_sha256 failures: "
            f"{text_hash_failures}"
        )

    truncated_rows = [
        str(row["row_id"])
        for row in rows
        if row_is_truncated(row)
    ]

    if truncated_rows:
        raise ValueError(
            "Truncated rows: "
            f"{truncated_rows}"
        )

    max_token_count = max(
        token_count(row)
        for row in rows
    )

    if max_token_count != 506:
        raise ValueError(
            "Unexpected maximum token count: "
            f"{max_token_count}"
        )

    label_counts = Counter(
        int(row["general_risk_label"])
        for row in rows
    )

    if label_counts != {
        0: 106,
        1: 106,
    }:
        raise ValueError(
            "Invalid label balance: "
            f"{dict(label_counts)}"
        )

    split_row_counts = Counter(
        str(row["split"])
        for row in rows
    )

    if split_row_counts != {
        "train": 170,
        "validation": 42,
    }:
        raise ValueError(
            "Invalid split row counts: "
            f"{dict(split_row_counts)}"
        )

    expected_metadata = {
        "artifact_name": ARTIFACT_NAME,
        "artifact_version": "v0.4.0",
        "status": "built_not_frozen",
        "rows": 212,
        "pairs": 106,
        "train_rows": 170,
        "train_pairs": 85,
        "validation_rows": 42,
        "validation_pairs": 21,
        "maximum_token_count": 506,
        "truncated_rows": 0,
        "base_rows": 164,
        "expansion_rows": 48,
        "crosslingual_group_id_policy": (
            "string_or_null_preserve_source"
        ),
        "legacy_provenance_preserved": True,
        "expansion_metadata_preserved": True,
        "existing_split_assignments_preserved": True,
        "base_corpus_modified": False,
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

    validate_artifact_manifest()

    print("=" * 80)
    print(
        "AGENTDOJO TURKISH CORPUS "
        "V0.4.0 VALIDATION"
    )
    print("=" * 80)
    print()
    print("Rows:", len(rows))
    print("Pairs:", len(grouped))
    print("Train rows:", len(train_rows))
    print("Train pairs:", len(train_pair_ids))
    print(
        "Validation rows:",
        len(validation_rows),
    )
    print(
        "Validation pairs:",
        len(validation_pair_ids),
    )
    print("Labels:", dict(label_counts))
    print("Maximum token count:", max_token_count)
    print("Truncation: 0")
    print("Duplicate row IDs: 0")
    print("Duplicate exact texts: 0")
    print("Train/validation pair leakage: 0")
    print("Train/validation text leakage: 0")
    print("Pair integrity failures: 0")
    print("Label/variant failures: 0")
    print("Base row preservation failures: 0")
    print("Expansion row preservation failures: 0")
    print("Synthetic legacy fields: 0")
    print("Synthetic expansion fields: 0")
    print("text_sha256 failures: 0")
    print("Base immutable checksum failures: 0")
    print("Artifact SHA manifest failures: 0")
    print()
    print(
        "AgentDojo Turkish corpus "
        "v0.4.0 validation: PASSED"
    )


if __name__ == "__main__":
    main()

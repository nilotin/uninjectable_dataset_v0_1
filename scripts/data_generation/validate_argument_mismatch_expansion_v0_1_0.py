from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


EXPANSION_DIR = Path(
    "data/planning/"
    "agentdojo_turkish_argument_mismatch_expansion_v0.1.0"
)

ARTIFACT_NAME = (
    "agentdojo_turkish_argument_mismatch_expansion_v0.1.0"
)

ALL_PATH = (
    EXPANSION_DIR
    / f"{ARTIFACT_NAME}.jsonl"
)

TRAIN_PATH = (
    EXPANSION_DIR
    / f"{ARTIFACT_NAME}_train.jsonl"
)

VALIDATION_PATH = (
    EXPANSION_DIR
    / f"{ARTIFACT_NAME}_validation.jsonl"
)

METADATA_PATH = (
    EXPANSION_DIR
    / f"{ARTIFACT_NAME}_metadata.json"
)

SHA_PATH = (
    EXPANSION_DIR
    / f"{ARTIFACT_NAME}_sha256.txt"
)

FROZEN_DIR = Path(
    "data/processed/"
    "agentdojo_turkish_corpus_v0.3.0"
)

EXPECTED_CATEGORIES = {
    "recipient_mismatch",
    "amount_mismatch",
    "object_or_record_id_mismatch",
    "date_or_time_mismatch",
    "body_or_subject_mismatch",
    "permission_or_scope_mismatch",
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


def normalize_text(text: str) -> str:
    return re.sub(
        r"\s+",
        " ",
        text.strip(),
    )


def locate_frozen_split(split: str) -> Path:
    candidates = sorted(
        path
        for path in FROZEN_DIR.glob("*.jsonl")
        if split in path.stem.lower()
    )

    if len(candidates) != 1:
        raise ValueError(
            f"Expected exactly one frozen {split} JSONL "
            f"under {FROZEN_DIR}, found: {candidates}"
        )

    return candidates[0]


def validate_sha_manifest() -> int:
    expected_entries: dict[str, str] = {}

    for line in SHA_PATH.read_text(
        encoding="utf-8"
    ).splitlines():
        if not line.strip():
            continue

        digest, filename = line.split(
            None,
            1,
        )

        expected_entries[
            filename.strip()
        ] = digest.strip()

    expected_files = {
        ALL_PATH.name: ALL_PATH,
        TRAIN_PATH.name: TRAIN_PATH,
        VALIDATION_PATH.name: VALIDATION_PATH,
        METADATA_PATH.name: METADATA_PATH,
    }

    if set(expected_entries) != set(expected_files):
        raise ValueError(
            "SHA manifest file set mismatch; "
            f"manifest={sorted(expected_entries)}, "
            f"expected={sorted(expected_files)}"
        )

    failures = 0

    for filename, path in expected_files.items():
        observed = sha256(path)
        expected = expected_entries[filename]

        if observed != expected:
            failures += 1
            print(
                "SHA mismatch:",
                filename,
            )

    return failures


def main() -> None:
    frozen_train_path = locate_frozen_split(
        "train"
    )

    frozen_validation_path = locate_frozen_split(
        "validation"
    )

    rows = load_jsonl(ALL_PATH)
    train_rows = load_jsonl(TRAIN_PATH)
    validation_rows = load_jsonl(
        VALIDATION_PATH
    )

    frozen_rows = (
        load_jsonl(frozen_train_path)
        + load_jsonl(frozen_validation_path)
    )

    metadata = json.loads(
        METADATA_PATH.read_text(
            encoding="utf-8"
        )
    )

    if len(rows) != 48:
        raise ValueError(
            f"Expected 48 rows, found {len(rows)}"
        )

    if len(train_rows) != 36:
        raise ValueError(
            f"Expected 36 train rows, "
            f"found {len(train_rows)}"
        )

    if len(validation_rows) != 12:
        raise ValueError(
            f"Expected 12 validation rows, "
            f"found {len(validation_rows)}"
        )

    row_ids = [
        str(row["row_id"])
        for row in rows
    ]

    duplicate_row_ids = (
        len(row_ids)
        - len(set(row_ids))
    )

    if duplicate_row_ids:
        raise ValueError(
            f"Duplicate row IDs: {duplicate_row_ids}"
        )

    grouped: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)

    for row in rows:
        grouped[
            str(row["pair_id"])
        ].append(row)

    if len(grouped) != 24:
        raise ValueError(
            f"Expected 24 pairs, found {len(grouped)}"
        )

    pair_integrity_failures: list[str] = []
    pair_split_failures: list[str] = []
    label_variant_failures: list[str] = []
    pair_category_failures: list[str] = []

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

        categories = {
            str(row["category"])
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
            pair_split_failures.append(
                pair_id
            )

        if len(categories) != 1:
            pair_category_failures.append(
                pair_id
            )

        for row in members:
            variant = str(row["variant"])

            if variant == "safe":
                expected_label = 0
            elif variant == "risky":
                expected_label = 1
            else:
                label_variant_failures.append(
                    str(row["row_id"])
                )
                continue

            if (
                int(row["general_risk_label"])
                != expected_label
            ):
                label_variant_failures.append(
                    str(row["row_id"])
                )

    if pair_integrity_failures:
        raise ValueError(
            "Pair integrity failures: "
            f"{sorted(set(pair_integrity_failures))}"
        )

    if pair_split_failures:
        raise ValueError(
            "Pair split failures: "
            f"{sorted(pair_split_failures)}"
        )

    if pair_category_failures:
        raise ValueError(
            "Pair category failures: "
            f"{sorted(pair_category_failures)}"
        )

    if label_variant_failures:
        raise ValueError(
            "Label/variant failures: "
            f"{sorted(label_variant_failures)}"
        )

    category_pair_counts = Counter(
        str(members[0]["category"])
        for members in grouped.values()
    )

    if set(category_pair_counts) != EXPECTED_CATEGORIES:
        raise ValueError(
            "Unexpected category set: "
            f"{set(category_pair_counts)}"
        )

    if any(
        count != 4
        for count in category_pair_counts.values()
    ):
        raise ValueError(
            "Category pair counts invalid: "
            f"{dict(category_pair_counts)}"
        )

    category_row_counts = Counter(
        str(row["category"])
        for row in rows
    )

    if any(
        count != 8
        for count in category_row_counts.values()
    ):
        raise ValueError(
            "Category row counts invalid: "
            f"{dict(category_row_counts)}"
        )

    label_counts = Counter(
        int(row["general_risk_label"])
        for row in rows
    )

    if label_counts != {
        0: 24,
        1: 24,
    }:
        raise ValueError(
            "Invalid label balance: "
            f"{dict(label_counts)}"
        )

    variant_counts = Counter(
        str(row["variant"])
        for row in rows
    )

    if variant_counts != {
        "safe": 24,
        "risky": 24,
    }:
        raise ValueError(
            "Invalid variant balance: "
            f"{dict(variant_counts)}"
        )

    split_pair_counts = Counter(
        str(members[0]["split"])
        for members in grouped.values()
    )

    if split_pair_counts != {
        "train": 18,
        "validation": 6,
    }:
        raise ValueError(
            "Invalid pair split counts: "
            f"{dict(split_pair_counts)}"
        )

    all_train_row_ids = {
        str(row["row_id"])
        for row in train_rows
    }

    expected_train_row_ids = {
        str(row["row_id"])
        for row in rows
        if row["split"] == "train"
    }

    if all_train_row_ids != expected_train_row_ids:
        raise ValueError(
            "Train artifact membership mismatch"
        )

    all_validation_row_ids = {
        str(row["row_id"])
        for row in validation_rows
    }

    expected_validation_row_ids = {
        str(row["row_id"])
        for row in rows
        if row["split"] == "validation"
    }

    if (
        all_validation_row_ids
        != expected_validation_row_ids
    ):
        raise ValueError(
            "Validation artifact membership mismatch"
        )

    normalized_texts = [
        normalize_text(str(row["text"]))
        for row in rows
    ]

    duplicate_text_count = (
        len(normalized_texts)
        - len(set(normalized_texts))
    )

    if duplicate_text_count:
        raise ValueError(
            "Internal duplicate compact inputs: "
            f"{duplicate_text_count}"
        )

    train_texts = {
        normalize_text(str(row["text"]))
        for row in train_rows
    }

    validation_texts = {
        normalize_text(str(row["text"]))
        for row in validation_rows
    }

    split_text_leakage = (
        train_texts
        & validation_texts
    )

    if split_text_leakage:
        raise ValueError(
            "Train/validation exact-text leakage: "
            f"{len(split_text_leakage)}"
        )

    train_pair_ids = {
        str(row["pair_id"])
        for row in train_rows
    }

    validation_pair_ids = {
        str(row["pair_id"])
        for row in validation_rows
    }

    pair_split_leakage = (
        train_pair_ids
        & validation_pair_ids
    )

    if pair_split_leakage:
        raise ValueError(
            "Pair-ID split leakage: "
            f"{sorted(pair_split_leakage)}"
        )

    frozen_texts = {
        normalize_text(str(row["text"]))
        for row in frozen_rows
    }

    frozen_row_ids = {
        str(row["row_id"])
        for row in frozen_rows
    }

    frozen_pair_ids = {
        str(row["pair_id"])
        for row in frozen_rows
    }

    expansion_texts = set(
        normalized_texts
    )

    expansion_row_ids = set(
        row_ids
    )

    expansion_pair_ids = set(
        grouped
    )

    frozen_exact_duplicates = (
        expansion_texts
        & frozen_texts
    )

    frozen_row_id_collisions = (
        expansion_row_ids
        & frozen_row_ids
    )

    frozen_pair_id_collisions = (
        expansion_pair_ids
        & frozen_pair_ids
    )

    if frozen_exact_duplicates:
        raise ValueError(
            "Frozen corpus exact-text duplicates: "
            f"{len(frozen_exact_duplicates)}"
        )

    if frozen_row_id_collisions:
        raise ValueError(
            "Frozen corpus row-ID collisions: "
            f"{sorted(frozen_row_id_collisions)}"
        )

    if frozen_pair_id_collisions:
        raise ValueError(
            "Frozen corpus pair-ID collisions: "
            f"{sorted(frozen_pair_id_collisions)}"
        )

    truncated_rows = [
        str(row["row_id"])
        for row in rows
        if bool(
            row["tokenization"].get(
                "truncated",
                False,
            )
        )
    ]

    if truncated_rows:
        raise ValueError(
            "Truncated rows: "
            f"{truncated_rows}"
        )

    max_token_count = max(
        int(
            row["tokenization"]["token_count"]
        )
        for row in rows
    )

    if max_token_count > 512:
        raise ValueError(
            "Token length exceeds max_length: "
            f"{max_token_count}"
        )

    text_hash_failures: list[str] = []

    for row in rows:
        observed_hash = hashlib.sha256(
            str(row["text"]).encode("utf-8")
        ).hexdigest()

        if observed_hash != row["text_sha256"]:
            text_hash_failures.append(
                str(row["row_id"])
            )

    if text_hash_failures:
        raise ValueError(
            "text_sha256 failures: "
            f"{text_hash_failures}"
        )

    sha_manifest_failures = (
        validate_sha_manifest()
    )

    if sha_manifest_failures:
        raise ValueError(
            "SHA manifest failures: "
            f"{sha_manifest_failures}"
        )

    expected_metadata = {
        "rows": 48,
        "pairs": 24,
        "train_rows": 36,
        "validation_rows": 12,
        "maximum_token_count": max_token_count,
        "truncated_rows": 0,
        "frozen_corpus_modified": False,
        "training_package_modified": False,
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

    print("=" * 80)
    print(
        "ARGUMENT MISMATCH EXPANSION "
        "VALIDATION v0.1.0"
    )
    print("=" * 80)
    print()
    print("Rows:", len(rows))
    print("Pairs:", len(grouped))
    print(
        "Pair split counts:",
        dict(split_pair_counts),
    )
    print("Labels:", dict(label_counts))
    print("Variants:", dict(variant_counts))
    print(
        "Category pair counts:",
        dict(sorted(category_pair_counts.items())),
    )
    print("Duplicate row IDs: 0")
    print("Internal duplicate texts: 0")
    print("Train/validation text leakage: 0")
    print("Train/validation pair leakage: 0")
    print("Frozen corpus exact duplicates: 0")
    print("Frozen corpus row-ID collisions: 0")
    print("Frozen corpus pair-ID collisions: 0")
    print("Pair integrity failures: 0")
    print("Label/variant failures: 0")
    print("text_sha256 failures: 0")
    print("SHA manifest failures: 0")
    print("Truncation: 0")
    print(
        "Maximum token count:",
        max_token_count,
    )
    print(
        "Frozen train source:",
        frozen_train_path,
    )
    print(
        "Frozen validation source:",
        frozen_validation_path,
    )
    print()
    print(
        "Argument mismatch expansion validation: PASSED"
    )


if __name__ == "__main__":
    main()

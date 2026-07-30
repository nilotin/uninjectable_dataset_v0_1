from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
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


def write_jsonl(
    path: Path,
    rows: list[dict[str, Any]],
) -> None:
    path.write_text(
        "".join(
            json.dumps(
                row,
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


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

        entries[
            filename.strip()
        ] = digest.strip()

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


def variant_rank(variant: str) -> int:
    if variant == "safe":
        return 0

    if variant == "risky":
        return 1

    raise ValueError(
        f"Unexpected variant: {variant}"
    )


def deterministic_sort(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (
            str(row["pair_id"]),
            variant_rank(
                str(row["variant"])
            ),
            str(row["row_id"]),
        ),
    )


def pair_count(
    rows: list[dict[str, Any]],
) -> int:
    return len(
        {
            str(row["pair_id"])
            for row in rows
        }
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

    count = token_count(row)
    max_length = tokenization.get(
        "max_length",
        512,
    )

    return count > int(max_length)


def verify_base_snapshot() -> None:
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
            "Base snapshot file set mismatch"
        )

    failures = []

    for path in base_files:
        expected = snapshot[path.name]
        observed = sha256(path)

        if expected != observed:
            failures.append(path.name)

    if failures:
        raise ValueError(
            "Base immutable checksum failures: "
            f"{failures}"
        )


def verify_split_membership(
    all_rows: list[dict[str, Any]],
    split_rows: list[dict[str, Any]],
    split: str,
) -> None:
    expected_ids = {
        str(row["row_id"])
        for row in all_rows
        if row["split"] == split
    }

    observed_ids = {
        str(row["row_id"])
        for row in split_rows
    }

    if expected_ids != observed_ids:
        raise ValueError(
            f"{split} membership mismatch"
        )


def main() -> None:
    verify_base_snapshot()

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

    expansion_all_rows = load_jsonl(
        EXPANSION_ALL_PATH
    )

    expansion_train_rows = load_jsonl(
        EXPANSION_TRAIN_PATH
    )

    expansion_validation_rows = load_jsonl(
        EXPANSION_VALIDATION_PATH
    )

    verify_split_membership(
        expansion_all_rows,
        expansion_train_rows,
        "train",
    )

    verify_split_membership(
        expansion_all_rows,
        expansion_validation_rows,
        "validation",
    )

    train_rows = deterministic_sort(
        base_train_rows
        + expansion_train_rows
    )

    validation_rows = deterministic_sort(
        base_validation_rows
        + expansion_validation_rows
    )

    all_rows = (
        train_rows
        + validation_rows
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

    if len(all_rows) != 212:
        raise ValueError(
            f"Expected 212 rows, "
            f"found {len(all_rows)}"
        )

    if pair_count(train_rows) != 85:
        raise ValueError(
            "Expected 85 train pairs, "
            f"found {pair_count(train_rows)}"
        )

    if pair_count(validation_rows) != 21:
        raise ValueError(
            "Expected 21 validation pairs, "
            f"found {pair_count(validation_rows)}"
        )

    if pair_count(all_rows) != 106:
        raise ValueError(
            "Expected 106 total pairs, "
            f"found {pair_count(all_rows)}"
        )

    label_counts = Counter(
        int(row["general_risk_label"])
        for row in all_rows
    )

    if label_counts != {
        0: 106,
        1: 106,
    }:
        raise ValueError(
            "Unexpected label counts: "
            f"{dict(label_counts)}"
        )

    grouped: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)

    for row in all_rows:
        grouped[
            str(row["pair_id"])
        ].append(row)

    for pair_id, members in grouped.items():
        if len(members) != 2:
            raise ValueError(
                f"{pair_id}: expected 2 rows, "
                f"found {len(members)}"
            )

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
            raise ValueError(
                f"{pair_id}: invalid variants "
                f"{dict(variants)}"
            )

        if labels != {
            0: 1,
            1: 1,
        }:
            raise ValueError(
                f"{pair_id}: invalid labels "
                f"{dict(labels)}"
            )

        if len(splits) != 1:
            raise ValueError(
                f"{pair_id}: split leakage "
                f"{sorted(splits)}"
            )

    row_ids = [
        str(row["row_id"])
        for row in all_rows
    ]

    if len(row_ids) != len(set(row_ids)):
        raise ValueError(
            "Duplicate row IDs detected"
        )

    pair_ids = [
        str(row["pair_id"])
        for row in all_rows
    ]

    if len(set(pair_ids)) != 106:
        raise ValueError(
            "Unexpected unique pair count"
        )

    text_hash_failures = []

    for row in all_rows:
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

    token_counts = [
        token_count(row)
        for row in all_rows
    ]

    truncated_rows = [
        str(row["row_id"])
        for row in all_rows
        if row_is_truncated(row)
    ]

    if truncated_rows:
        raise ValueError(
            "Truncated rows: "
            f"{truncated_rows}"
        )

    if max(token_counts) > 512:
        raise ValueError(
            "Token count exceeds max_length"
        )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    write_jsonl(
        ALL_PATH,
        all_rows,
    )

    write_jsonl(
        TRAIN_PATH,
        train_rows,
    )

    write_jsonl(
        VALIDATION_PATH,
        validation_rows,
    )

    category_row_counts = Counter(
        str(row["category"])
        for row in expansion_all_rows
    )

    metadata = {
        "artifact_name": ARTIFACT_NAME,
        "artifact_version": "v0.4.0",
        "created_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "status": "built_not_frozen",
        "language": "tr",
        "schema_strategy": "union_schema",
        "tokenizer": (
            "google-bert/"
            "bert-base-multilingual-cased"
        ),
        "max_length": 512,
        "source_artifacts": {
            "base": (
                "agentdojo_turkish_corpus_v0.3.0"
            ),
            "expansion": EXPANSION_NAME,
            "merge_plan": (
                "agentdojo_turkish_corpus_"
                "v0.4.0_merge_plan"
            ),
        },
        "rows": len(all_rows),
        "pairs": pair_count(all_rows),
        "train_rows": len(train_rows),
        "train_pairs": pair_count(
            train_rows
        ),
        "validation_rows": len(
            validation_rows
        ),
        "validation_pairs": pair_count(
            validation_rows
        ),
        "label_counts": {
            str(key): value
            for key, value in sorted(
                label_counts.items()
            )
        },
        "maximum_token_count": max(
            token_counts
        ),
        "minimum_token_count": min(
            token_counts
        ),
        "truncated_rows": 0,
        "base_rows": (
            len(base_train_rows)
            + len(base_validation_rows)
        ),
        "expansion_rows": len(
            expansion_all_rows
        ),
        "expansion_category_row_counts": dict(
            sorted(
                category_row_counts.items()
            )
        ),
        "crosslingual_group_id_policy": (
            "string_or_null_preserve_source"
        ),
        "legacy_provenance_preserved": True,
        "expansion_metadata_preserved": True,
        "existing_split_assignments_preserved": True,
        "base_corpus_modified": False,
    }

    METADATA_PATH.write_text(
        json.dumps(
            metadata,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    artifact_files = [
        ALL_PATH,
        TRAIN_PATH,
        VALIDATION_PATH,
        METADATA_PATH,
    ]

    SHA_PATH.write_text(
        "\n".join(
            f"{sha256(path)}  {path.name}"
            for path in artifact_files
        )
        + "\n",
        encoding="utf-8",
    )

    print("=" * 80)
    print(
        "AGENTDOJO TURKISH CORPUS V0.4.0 BUILD"
    )
    print("=" * 80)
    print()
    print("Base train rows:", len(base_train_rows))
    print(
        "Base validation rows:",
        len(base_validation_rows),
    )
    print(
        "Expansion train rows:",
        len(expansion_train_rows),
    )
    print(
        "Expansion validation rows:",
        len(expansion_validation_rows),
    )
    print()
    print("Target pairs:", pair_count(all_rows))
    print("Target rows:", len(all_rows))
    print(
        "Target train pairs:",
        pair_count(train_rows),
    )
    print("Target train rows:", len(train_rows))
    print(
        "Target validation pairs:",
        pair_count(validation_rows),
    )
    print(
        "Target validation rows:",
        len(validation_rows),
    )
    print("Labels:", dict(label_counts))
    print(
        "Maximum token count:",
        max(token_counts),
    )
    print("Truncation: no")
    print("Base checksum verification: PASSED")
    print()
    print("All rows:", ALL_PATH)
    print("Train rows:", TRAIN_PATH)
    print(
        "Validation rows:",
        VALIDATION_PATH,
    )
    print("Metadata:", METADATA_PATH)
    print("Manifest:", SHA_PATH)
    print()
    print(
        "AgentDojo Turkish corpus v0.4.0 build: PASSED"
    )


if __name__ == "__main__":
    main()

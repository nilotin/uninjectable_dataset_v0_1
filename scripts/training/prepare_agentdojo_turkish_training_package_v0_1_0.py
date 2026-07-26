from __future__ import annotations

import hashlib
import json
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CONFIG_PATH = Path(
    "configs/training/"
    "mbert_turkish_baseline_v0.1.0.json"
)

PACKAGE_DIR = Path(
    "data/processed/"
    "agentdojo_turkish_training_package_v0.1.0"
)

PACKAGE_TRAIN = (
    PACKAGE_DIR
    / "agentdojo_turkish_training_v0.1.0_train.jsonl"
)

PACKAGE_VALIDATION = (
    PACKAGE_DIR
    / "agentdojo_turkish_training_v0.1.0_validation.jsonl"
)

PACKAGE_METADATA = (
    PACKAGE_DIR
    / "agentdojo_turkish_training_v0.1.0_metadata.json"
)

PACKAGE_MANIFEST = (
    PACKAGE_DIR
    / "agentdojo_turkish_training_v0.1.0_sha256.txt"
)

EXPECTED_FIELDS = {
    "row_id",
    "pair_id",
    "session_group_id",
    "suite",
    "variant",
    "language",
    "split",
    "text",
    "general_risk_label",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue

        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"{path}:{line_number}: invalid JSON"
            ) from exc

        rows.append(row)

    return rows


def write_jsonl(
    path: Path,
    rows: list[dict[str, Any]],
) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(
                json.dumps(
                    row,
                    ensure_ascii=False,
                    sort_keys=True,
                )
                + "\n"
            )


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


def validate_rows(
    rows: list[dict[str, Any]],
    expected_split: str,
    expected_count: int,
) -> dict[str, Any]:
    if len(rows) != expected_count:
        raise ValueError(
            f"{expected_split}: expected "
            f"{expected_count} rows, found {len(rows)}."
        )

    row_ids: list[str] = []
    texts: list[str] = []
    pair_groups: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)

    for index, row in enumerate(rows, start=1):
        missing = EXPECTED_FIELDS - set(row)

        if missing:
            raise ValueError(
                f"{expected_split} row {index}: "
                f"missing fields {sorted(missing)}"
            )

        if str(row["split"]) != expected_split:
            raise ValueError(
                f"{row['row_id']}: expected split "
                f"{expected_split!r}, found "
                f"{row['split']!r}."
            )

        if str(row["language"]) != "tr":
            raise ValueError(
                f"{row['row_id']}: language is not tr."
            )

        label = int(row["general_risk_label"])

        if label not in {0, 1}:
            raise ValueError(
                f"{row['row_id']}: invalid label {label}."
            )

        text = str(row["text"])

        if not text.strip():
            raise ValueError(
                f"{row['row_id']}: empty model input."
            )

        row_id = str(row["row_id"])
        pair_id = canonical_pair_id(
            str(row["pair_id"])
        )

        row_ids.append(row_id)
        texts.append(text)
        pair_groups[pair_id].append(row)

    if len(row_ids) != len(set(row_ids)):
        raise ValueError(
            f"{expected_split}: duplicate row IDs."
        )

    if len(texts) != len(set(texts)):
        raise ValueError(
            f"{expected_split}: duplicate model inputs."
        )

    for pair_id, pair_rows in pair_groups.items():
        if len(pair_rows) != 2:
            raise ValueError(
                f"{expected_split} {pair_id}: "
                f"expected 2 rows, found {len(pair_rows)}."
            )

        labels = {
            int(row["general_risk_label"])
            for row in pair_rows
        }

        if labels != {0, 1}:
            raise ValueError(
                f"{expected_split} {pair_id}: "
                f"invalid label pair {sorted(labels)}."
            )

        group_ids = {
            str(row["session_group_id"])
            for row in pair_rows
        }

        if len(group_ids) != 1:
            raise ValueError(
                f"{expected_split} {pair_id}: "
                "session group mismatch."
            )

    return {
        "rows": len(rows),
        "pairs": len(pair_groups),
        "labels": dict(
            sorted(
                Counter(
                    int(row["general_risk_label"])
                    for row in rows
                ).items()
            )
        ),
        "suites": dict(
            sorted(
                Counter(
                    str(row["suite"])
                    for row in rows
                ).items()
            )
        ),
        "duplicate_row_ids": 0,
        "duplicate_inputs": 0,
        "pair_integrity": True,
    }


def make_training_row(
    row: dict[str, Any],
) -> dict[str, Any]:
    return {
        "row_id": str(row["row_id"]),
        "pair_id": canonical_pair_id(
            str(row["pair_id"])
        ),
        "session_group_id": str(
            row["session_group_id"]
        ),
        "suite": str(row["suite"]),
        "variant": str(row["variant"]),
        "language": str(row["language"]),
        "split": str(row["split"]),
        "text": str(row["text"]),
        "label": int(
            row["general_risk_label"]
        ),
        "source_text_sha256": str(
            row["text_sha256"]
        ),
    }


def main() -> None:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(CONFIG_PATH)

    config = json.loads(
        CONFIG_PATH.read_text(encoding="utf-8")
    )

    train_source = Path(
        config["data"]["train_path"]
    )
    validation_source = Path(
        config["data"]["validation_path"]
    )

    for path in (
        train_source,
        validation_source,
    ):
        if not path.exists():
            raise FileNotFoundError(path)

    source_hashes_before = {
        "config": sha256_file(CONFIG_PATH),
        "train": sha256_file(train_source),
        "validation": sha256_file(
            validation_source
        ),
    }

    train_rows = load_jsonl(train_source)
    validation_rows = load_jsonl(
        validation_source
    )

    train_validation = validate_rows(
        train_rows,
        expected_split="train",
        expected_count=int(
            config["data"]["train_rows"]
        ),
    )

    validation_validation = validate_rows(
        validation_rows,
        expected_split="validation",
        expected_count=int(
            config["data"]["validation_rows"]
        ),
    )

    train_groups = {
        str(row["session_group_id"])
        for row in train_rows
    }

    validation_groups = {
        str(row["session_group_id"])
        for row in validation_rows
    }

    leaked_groups = sorted(
        train_groups & validation_groups
    )

    if leaked_groups:
        raise ValueError(
            "Train-validation session leakage: "
            f"{leaked_groups}"
        )

    train_crosslingual = {
        str(row["crosslingual_group_id"])
        for row in train_rows
    }

    validation_crosslingual = {
        str(row["crosslingual_group_id"])
        for row in validation_rows
    }

    leaked_crosslingual = sorted(
        train_crosslingual
        & validation_crosslingual
    )

    if leaked_crosslingual:
        raise ValueError(
            "Train-validation crosslingual leakage: "
            f"{leaked_crosslingual}"
        )

    package_train_rows = [
        make_training_row(row)
        for row in train_rows
    ]

    package_validation_rows = [
        make_training_row(row)
        for row in validation_rows
    ]

    PACKAGE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    write_jsonl(
        PACKAGE_TRAIN,
        package_train_rows,
    )

    write_jsonl(
        PACKAGE_VALIDATION,
        package_validation_rows,
    )

    metadata = {
        "package": (
            "agentdojo_turkish_training_"
            "package_v0.1.0"
        ),
        "created_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "source_corpus": (
            config["data"]["corpus_release"]
        ),
        "config_path": str(CONFIG_PATH),
        "model_name": config["model_name"],
        "task_type": config["task_type"],
        "label_mapping": (
            config["label_mapping"]
        ),
        "risk_score_definition": (
            config["evaluation"][
                "risk_score_definition"
            ]
        ),
        "tokenization": (
            config["tokenization"]
        ),
        "counts": {
            "train": train_validation,
            "validation": (
                validation_validation
            ),
        },
        "validation": {
            "session_group_leakage": 0,
            "crosslingual_group_leakage": 0,
            "test_split_accessed": False,
            "source_artifacts_modified": False,
        },
        "source_hashes": source_hashes_before,
    }

    PACKAGE_METADATA.write_text(
        json.dumps(
            metadata,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    source_hashes_after = {
        "config": sha256_file(CONFIG_PATH),
        "train": sha256_file(train_source),
        "validation": sha256_file(
            validation_source
        ),
    }

    if (
        source_hashes_before
        != source_hashes_after
    ):
        raise ValueError(
            "Source artifacts were modified."
        )

    manifest_paths = [
        PACKAGE_TRAIN,
        PACKAGE_VALIDATION,
        PACKAGE_METADATA,
    ]

    PACKAGE_MANIFEST.write_text(
        "\n".join(
            f"{sha256_file(path)}  {path.name}"
            for path in manifest_paths
        )
        + "\n",
        encoding="utf-8",
    )

    print("=" * 80)
    print(
        "AGENTDOJO TURKISH TRAINING "
        "PACKAGE v0.1.0"
    )
    print("=" * 80)
    print()
    print(
        "Train rows:",
        train_validation["rows"],
    )
    print(
        "Train pairs:",
        train_validation["pairs"],
    )
    print(
        "Train labels:",
        train_validation["labels"],
    )
    print()
    print(
        "Validation rows:",
        validation_validation["rows"],
    )
    print(
        "Validation pairs:",
        validation_validation["pairs"],
    )
    print(
        "Validation labels:",
        validation_validation["labels"],
    )
    print()
    print("Session-group leakage: 0")
    print("Crosslingual-group leakage: 0")
    print("Duplicate inputs: 0")
    print("Test split accessed: no")
    print("Source artifacts modified: no")
    print()
    print(
        "Train artifact:",
        PACKAGE_TRAIN,
    )
    print(
        "Validation artifact:",
        PACKAGE_VALIDATION,
    )
    print(
        "Metadata:",
        PACKAGE_METADATA,
    )
    print(
        "Manifest:",
        PACKAGE_MANIFEST,
    )
    print()
    print("Training package: PASSED")


if __name__ == "__main__":
    main()

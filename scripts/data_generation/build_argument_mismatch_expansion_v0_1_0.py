from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(
    "data/planning/"
    "agentdojo_turkish_argument_mismatch_batch_v0.1.0"
)

OUTPUT_DIR = Path(
    "data/planning/"
    "agentdojo_turkish_argument_mismatch_expansion_v0.1.0"
)

ARTIFACT_NAME = (
    "agentdojo_turkish_argument_mismatch_expansion_v0.1.0"
)

CATEGORY_FILES = {
    "recipient_mismatch": (
        ROOT
        / "recipient_mismatch_rows_v0.1.0"
        / "recipient_mismatch_rows_v0.1.0.jsonl"
    ),
    "amount_mismatch": (
        ROOT
        / "amount_mismatch_rows_v0.1.0"
        / "amount_mismatch_rows_v0.1.0.jsonl"
    ),
    "object_or_record_id_mismatch": (
        ROOT
        / "object_or_record_id_mismatch_rows_v0.1.0"
        / "object_or_record_id_mismatch_rows_v0.1.0.jsonl"
    ),
    "date_or_time_mismatch": (
        ROOT
        / "date_or_time_mismatch_rows_v0.1.0"
        / "date_or_time_mismatch_rows_v0.1.0.jsonl"
    ),
    "body_or_subject_mismatch": (
        ROOT
        / "body_or_subject_mismatch_rows_v0.1.0"
        / "body_or_subject_mismatch_rows_v0.1.0.jsonl"
    ),
    "permission_or_scope_mismatch": (
        ROOT
        / "permission_or_scope_mismatch_rows_v0.1.0"
        / "permission_or_scope_mismatch_rows_v0.1.0.jsonl"
    ),
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


def variant_sort_key(row: dict[str, Any]) -> int:
    variant = str(row["variant"])

    if variant == "safe":
        return 0

    if variant == "risky":
        return 1

    raise ValueError(
        f"Unexpected variant: {variant}"
    )


def main() -> None:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    rows: list[dict[str, Any]] = []

    for expected_category, path in CATEGORY_FILES.items():
        category_rows = load_jsonl(path)

        if len(category_rows) != 8:
            raise ValueError(
                f"{expected_category}: expected 8 rows, "
                f"found {len(category_rows)}"
            )

        for row in category_rows:
            observed_category = row.get("category")

            if observed_category != expected_category:
                raise ValueError(
                    f"{row.get('row_id')}: category mismatch; "
                    f"expected={expected_category}, "
                    f"observed={observed_category}"
                )

        rows.extend(category_rows)

    rows.sort(
        key=lambda row: (
            str(row["pair_id"]),
            variant_sort_key(row),
        )
    )

    if len(rows) != 48:
        raise ValueError(
            f"Expected 48 rows, found {len(rows)}"
        )

    train_rows = [
        row
        for row in rows
        if row["split"] == "train"
    ]

    validation_rows = [
        row
        for row in rows
        if row["split"] == "validation"
    ]

    all_path = (
        OUTPUT_DIR
        / f"{ARTIFACT_NAME}.jsonl"
    )

    train_path = (
        OUTPUT_DIR
        / f"{ARTIFACT_NAME}_train.jsonl"
    )

    validation_path = (
        OUTPUT_DIR
        / f"{ARTIFACT_NAME}_validation.jsonl"
    )

    metadata_path = (
        OUTPUT_DIR
        / f"{ARTIFACT_NAME}_metadata.json"
    )

    sha_path = (
        OUTPUT_DIR
        / f"{ARTIFACT_NAME}_sha256.txt"
    )

    write_jsonl(all_path, rows)
    write_jsonl(train_path, train_rows)
    write_jsonl(
        validation_path,
        validation_rows,
    )

    pair_ids = {
        str(row["pair_id"])
        for row in rows
    }

    label_counts = Counter(
        int(row["general_risk_label"])
        for row in rows
    )

    variant_counts = Counter(
        str(row["variant"])
        for row in rows
    )

    split_counts = Counter(
        str(row["split"])
        for row in rows
    )

    category_row_counts = Counter(
        str(row["category"])
        for row in rows
    )

    category_pair_counts = {
        category: len(
            {
                str(row["pair_id"])
                for row in rows
                if row["category"] == category
            }
        )
        for category in CATEGORY_FILES
    }

    token_counts = [
        int(row["tokenization"]["token_count"])
        for row in rows
    ]

    metadata = {
        "artifact_name": ARTIFACT_NAME,
        "artifact_version": "v0.1.0",
        "created_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "status": "approved_expansion_not_merged",
        "language": "tr",
        "tokenizer": (
            "google-bert/"
            "bert-base-multilingual-cased"
        ),
        "max_length": 512,
        "source_batch": (
            "agentdojo_turkish_"
            "argument_mismatch_batch_v0.1.0"
        ),
        "rows": len(rows),
        "pairs": len(pair_ids),
        "train_rows": len(train_rows),
        "validation_rows": len(
            validation_rows
        ),
        "split_counts": dict(split_counts),
        "label_counts": {
            str(key): value
            for key, value in sorted(
                label_counts.items()
            )
        },
        "variant_counts": dict(
            variant_counts
        ),
        "category_row_counts": dict(
            sorted(category_row_counts.items())
        ),
        "category_pair_counts": dict(
            sorted(category_pair_counts.items())
        ),
        "maximum_token_count": max(
            token_counts
        ),
        "minimum_token_count": min(
            token_counts
        ),
        "truncated_rows": sum(
            bool(
                row["tokenization"].get(
                    "truncated",
                    False,
                )
            )
            for row in rows
        ),
        "frozen_corpus_modified": False,
        "training_package_modified": False,
    }

    metadata_path.write_text(
        json.dumps(
            metadata,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    output_files = [
        all_path,
        train_path,
        validation_path,
        metadata_path,
    ]

    sha_lines = [
        f"{sha256(path)}  {path.name}"
        for path in output_files
    ]

    sha_path.write_text(
        "\n".join(sha_lines) + "\n",
        encoding="utf-8",
    )

    print("=" * 80)
    print(
        "ARGUMENT MISMATCH EXPANSION BUILD v0.1.0"
    )
    print("=" * 80)
    print()
    print("Categories:", len(CATEGORY_FILES))
    print("Pairs:", len(pair_ids))
    print("Rows:", len(rows))
    print("Train rows:", len(train_rows))
    print(
        "Validation rows:",
        len(validation_rows),
    )
    print("Labels:", dict(label_counts))
    print("Variants:", dict(variant_counts))
    print(
        "Maximum token count:",
        max(token_counts),
    )
    print(
        "Truncation:",
        "yes"
        if metadata["truncated_rows"]
        else "no",
    )
    print()
    print("All rows:", all_path)
    print("Train rows:", train_path)
    print(
        "Validation rows:",
        validation_path,
    )
    print("Metadata:", metadata_path)
    print("Manifest:", sha_path)
    print()
    print(
        "Argument mismatch expansion build: PASSED"
    )


if __name__ == "__main__":
    main()

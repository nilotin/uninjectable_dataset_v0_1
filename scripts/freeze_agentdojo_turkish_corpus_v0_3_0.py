from __future__ import annotations

import hashlib
import json
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SOURCE_DIR = Path(
    "data/processed/"
    "agentdojo_turkish_combined_through_batch_008_v0.2.6"
)

SOURCE_ALL = (
    SOURCE_DIR
    / "agentdojo_turkish_combined_through_batch_008_bert_compact_v0.2.6.jsonl"
)

SOURCE_TRAIN = (
    SOURCE_DIR
    / "agentdojo_turkish_combined_through_batch_008_bert_compact_v0.2.6_train.jsonl"
)

SOURCE_VALIDATION = (
    SOURCE_DIR
    / "agentdojo_turkish_combined_through_batch_008_bert_compact_v0.2.6_validation.jsonl"
)

OUTPUT_DIR = Path(
    "data/processed/"
    "agentdojo_turkish_corpus_v0.3.0"
)

OUTPUT_ALL = (
    OUTPUT_DIR
    / "agentdojo_turkish_corpus_v0.3.0.jsonl"
)

OUTPUT_TRAIN = (
    OUTPUT_DIR
    / "agentdojo_turkish_corpus_v0.3.0_train.jsonl"
)

OUTPUT_VALIDATION = (
    OUTPUT_DIR
    / "agentdojo_turkish_corpus_v0.3.0_validation.jsonl"
)

OUTPUT_REPORT = (
    OUTPUT_DIR
    / "agentdojo_turkish_corpus_v0.3.0_report.json"
)

OUTPUT_MANIFEST = (
    OUTPUT_DIR
    / "agentdojo_turkish_corpus_v0.3.0_sha256.txt"
)

EXPECTED_ROWS = 164
EXPECTED_PAIRS = 82
EXPECTED_SPLITS = {
    "train": 134,
    "validation": 30,
}
EXPECTED_LABELS = {
    0: 82,
    1: 82,
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


def main() -> None:
    for path in (
        SOURCE_ALL,
        SOURCE_TRAIN,
        SOURCE_VALIDATION,
    ):
        if not path.exists():
            raise FileNotFoundError(path)

    all_rows = load_jsonl(SOURCE_ALL)
    train_rows = load_jsonl(SOURCE_TRAIN)
    validation_rows = load_jsonl(
        SOURCE_VALIDATION
    )

    if len(all_rows) != EXPECTED_ROWS:
        raise ValueError(
            f"Expected {EXPECTED_ROWS} rows, "
            f"found {len(all_rows)}."
        )

    split_counts = Counter(
        str(row["split"])
        for row in all_rows
    )

    if dict(split_counts) != EXPECTED_SPLITS:
        raise ValueError(
            f"Unexpected split counts: "
            f"{dict(split_counts)}"
        )

    label_counts = Counter(
        int(row["general_risk_label"])
        for row in all_rows
    )

    if dict(label_counts) != EXPECTED_LABELS:
        raise ValueError(
            f"Unexpected label counts: "
            f"{dict(label_counts)}"
        )

    pairs: dict[str, list[dict[str, Any]]] = (
        defaultdict(list)
    )

    for row in all_rows:
        pair_id = canonical_pair_id(
            str(row["pair_id"])
        )
        pairs[pair_id].append(row)

    if len(pairs) != EXPECTED_PAIRS:
        raise ValueError(
            f"Expected {EXPECTED_PAIRS} pairs, "
            f"found {len(pairs)}."
        )

    for pair_id, pair_rows in pairs.items():
        if len(pair_rows) != 2:
            raise ValueError(
                f"{pair_id}: expected 2 rows, "
                f"found {len(pair_rows)}."
            )

        labels = {
            int(row["general_risk_label"])
            for row in pair_rows
        }

        if labels != {0, 1}:
            raise ValueError(
                f"{pair_id}: invalid labels "
                f"{sorted(labels)}."
            )

        splits = {
            str(row["split"])
            for row in pair_rows
        }

        if len(splits) != 1:
            raise ValueError(
                f"{pair_id}: split mismatch "
                f"{sorted(splits)}."
            )

    row_ids = [
        str(row["row_id"])
        for row in all_rows
    ]

    if len(row_ids) != len(set(row_ids)):
        raise ValueError(
            "Duplicate row IDs detected."
        )

    texts = [
        str(row["text"])
        for row in all_rows
    ]

    if len(texts) != len(set(texts)):
        raise ValueError(
            "Duplicate compact inputs detected."
        )

    if len(train_rows) != EXPECTED_SPLITS["train"]:
        raise ValueError(
            "Unexpected train row count."
        )

    if (
        len(validation_rows)
        != EXPECTED_SPLITS["validation"]
    ):
        raise ValueError(
            "Unexpected validation row count."
        )

    source_hashes_before = {
        "all": sha256_file(SOURCE_ALL),
        "train": sha256_file(SOURCE_TRAIN),
        "validation": sha256_file(
            SOURCE_VALIDATION
        ),
    }

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    shutil.copyfile(
        SOURCE_ALL,
        OUTPUT_ALL,
    )

    shutil.copyfile(
        SOURCE_TRAIN,
        OUTPUT_TRAIN,
    )

    shutil.copyfile(
        SOURCE_VALIDATION,
        OUTPUT_VALIDATION,
    )

    output_hashes = {
        "all": sha256_file(OUTPUT_ALL),
        "train": sha256_file(OUTPUT_TRAIN),
        "validation": sha256_file(
            OUTPUT_VALIDATION
        ),
    }

    if source_hashes_before != output_hashes:
        raise ValueError(
            "Frozen artifacts do not match sources."
        )

    source_hashes_after = {
        "all": sha256_file(SOURCE_ALL),
        "train": sha256_file(SOURCE_TRAIN),
        "validation": sha256_file(
            SOURCE_VALIDATION
        ),
    }

    if source_hashes_before != source_hashes_after:
        raise ValueError(
            "Source artifacts were modified."
        )

    report = {
        "release": "agentdojo_turkish_corpus_v0.3.0",
        "created_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "source_release": (
            "agentdojo_turkish_combined_"
            "through_batch_008_v0.2.6"
        ),
        "tokenizer": (
            "google-bert/"
            "bert-base-multilingual-cased"
        ),
        "max_length": 512,
        "counts": {
            "rows": len(all_rows),
            "pairs": len(pairs),
            "splits": dict(split_counts),
            "labels": {
                str(label): count
                for label, count
                in sorted(label_counts.items())
            },
        },
        "coverage": {
            "english_canonical_pairs": 97,
            "sealed_test_pairs": 14,
            "excluded_duplicate_pairs": [
                "agentdojo_pair_020"
            ],
            "usable_turkish_pairs": 82,
        },
        "excluded_pairs": {
            "agentdojo_pair_020": {
                "split": "train",
                "reason": (
                    "Compact Turkish BERT inputs "
                    "duplicate agentdojo_pair_004."
                ),
            }
        },
        "validation": {
            "pair_integrity": True,
            "label_balance": True,
            "split_integrity": True,
            "duplicate_row_ids": 0,
            "duplicate_compact_inputs": 0,
            "source_artifacts_modified": False,
            "test_split_accessed": False,
        },
        "source_hashes": source_hashes_before,
        "output_hashes": output_hashes,
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

    manifest_paths = [
        OUTPUT_ALL,
        OUTPUT_TRAIN,
        OUTPUT_VALIDATION,
        OUTPUT_REPORT,
    ]

    manifest_lines = [
        f"{sha256_file(path)}  {path.name}"
        for path in manifest_paths
    ]

    OUTPUT_MANIFEST.write_text(
        "\n".join(manifest_lines) + "\n",
        encoding="utf-8",
    )

    print("=" * 80)
    print(
        "AGENTDOJO TURKISH CORPUS "
        "FREEZE v0.3.0"
    )
    print("=" * 80)
    print()
    print(f"Rows: {len(all_rows)}")
    print(f"Pairs: {len(pairs)}")
    print(
        f"Train rows: {len(train_rows)}"
    )
    print(
        "Validation rows: "
        f"{len(validation_rows)}"
    )
    print(
        f"Labels: {dict(label_counts)}"
    )
    print()
    print("Duplicate row IDs: 0")
    print("Duplicate compact inputs: 0")
    print("Source artifacts modified: no")
    print("Test split accessed: no")
    print()
    print(f"Frozen artifact: {OUTPUT_ALL}")
    print(f"Report: {OUTPUT_REPORT}")
    print(f"Manifest: {OUTPUT_MANIFEST}")
    print()
    print("Corpus freeze: PASSED")


if __name__ == "__main__":
    main()

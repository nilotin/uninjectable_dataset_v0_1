from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


SOURCE_DIR = Path("data/raw/deepset_prompt_injections")
DATA_DIR = SOURCE_DIR / "data"

MANIFEST_PATH = SOURCE_DIR / "source_manifest.json"
REPORT_PATH = Path(
    "data/interim/deepset_prompt_injections_inspection_v0.1.json"
)


def sha256_file(path: Path) -> str:
    """Return the SHA-256 checksum of a file."""
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def normalize_text(text: str) -> str:
    """
    Minimal normalization used only for duplicate inspection.

    We do NOT modify the raw source data.
    """
    return " ".join(str(text).split()).strip().lower()


def inspect_parquet(path: Path) -> tuple[pd.DataFrame, dict]:
    df = pd.read_parquet(path)

    required_columns = {"text", "label"}
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"{path} is missing required columns: "
            f"{sorted(missing_columns)}"
        )

    normalized_text = df["text"].astype(str).map(normalize_text)

    stats = {
        "filename": path.name,
        "sha256": sha256_file(path),
        "rows": int(len(df)),
        "columns": df.columns.tolist(),
        "missing_values": {
            column: int(value)
            for column, value in df.isna().sum().items()
        },
        "label_counts": {
            str(label): int(count)
            for label, count
            in df["label"].value_counts(dropna=False).sort_index().items()
        },
        "exact_duplicate_rows": int(df.duplicated().sum()),
        "duplicate_normalized_texts": int(
            normalized_text.duplicated().sum()
        ),
        "unique_normalized_texts": int(normalized_text.nunique()),
    }

    return df, stats


def main() -> None:
    parquet_files = sorted(DATA_DIR.glob("*.parquet"))

    if not parquet_files:
        raise FileNotFoundError(
            f"No parquet files found under {DATA_DIR}"
        )

    datasets: dict[str, pd.DataFrame] = {}
    file_reports: list[dict] = []

    for path in parquet_files:
        split_name = path.name.split("-", 1)[0]

        df, stats = inspect_parquet(path)

        datasets[split_name] = df
        file_reports.append(stats)

    total_rows = sum(len(df) for df in datasets.values())

    combined = pd.concat(
        [
            df.assign(_source_split=split_name)
            for split_name, df in datasets.items()
        ],
        ignore_index=True,
    )

    combined["_normalized_text"] = (
        combined["text"]
        .astype(str)
        .map(normalize_text)
    )

    total_label_counts = {
        str(label): int(count)
        for label, count
        in combined["label"]
        .value_counts(dropna=False)
        .sort_index()
        .items()
    }

    cross_split_duplicates = []

    if "train" in datasets and "test" in datasets:
        train_texts = set(
            datasets["train"]["text"]
            .astype(str)
            .map(normalize_text)
        )

        test_texts = set(
            datasets["test"]["text"]
            .astype(str)
            .map(normalize_text)
        )

        cross_split_duplicates = sorted(
            train_texts.intersection(test_texts)
        )

    report = {
        "source_name": "deepset/prompt-injections",
        "inspection_version": "0.1",
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "total_rows": int(total_rows),
        "total_label_counts": total_label_counts,
        "files": file_reports,
        "combined_duplicate_normalized_texts": int(
            combined["_normalized_text"].duplicated().sum()
        ),
        "cross_split_duplicate_count": len(
            cross_split_duplicates
        ),
        "cross_split_duplicate_examples": (
            cross_split_duplicates[:20]
        ),
        "interpretation_notes": [
            (
                "Upstream label values are preserved only as "
                "source metadata."
            ),
            (
                "Upstream label=1 must not automatically become "
                "Uninjectable general_risk_label=1."
            ),
            (
                "The source is intended to provide candidate "
                "language seeds for later contextual composition."
            ),
        ],
    }

    REPORT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    REPORT_PATH.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    manifest = {
        "source_name": "deepset/prompt-injections",
        "source_url": (
            "https://huggingface.co/datasets/"
            "deepset/prompt-injections"
        ),
        "retrieved_at": "2026-07-15",
        "artifact_path": (
            "data/raw/deepset_prompt_injections"
        ),
        "source_format": "parquet",
        "source_splits": {
            split_name: int(len(df))
            for split_name, df in datasets.items()
        },
        "total_rows": int(total_rows),
        "license_identifier": (
            "REVIEW_REQUIRED: Hugging Face page/top-level "
            "metadata says apache-2.0; downloaded README "
            "dataset_info also contains cc-by-4.0"
        ),
        "license_file_path": (
            "data/raw/deepset_prompt_injections/README.md"
        ),
        "allowed_use_notes": (
            "Preserve provenance and attribution. "
            "Do not assume upstream labels are Uninjectable "
            "runtime-risk ground truth. Resolve the inconsistent "
            "license metadata before external redistribution."
        ),
        "attribution_text": (
            "Derived language seeds from "
            "deepset/prompt-injections."
        ),
        "usage_in_uninjectable": (
            "Candidate attack/instruction-like and benign "
            "language seed extraction only."
        ),
        "files": [
            {
                "filename": item["filename"],
                "sha256": item["sha256"],
                "rows": item["rows"],
            }
            for item in file_reports
        ],
    }

    MANIFEST_PATH.write_text(
        json.dumps(
            manifest,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("=" * 70)
    print("SOURCE INSPECTION COMPLETE")
    print("=" * 70)
    print(f"Total rows: {total_rows}")
    print(f"Label counts: {total_label_counts}")
    print(
        "Cross-split duplicate count:",
        len(cross_split_duplicates),
    )
    print()
    print(f"Manifest: {MANIFEST_PATH}")
    print(f"Inspection report: {REPORT_PATH}")


if __name__ == "__main__":
    main()

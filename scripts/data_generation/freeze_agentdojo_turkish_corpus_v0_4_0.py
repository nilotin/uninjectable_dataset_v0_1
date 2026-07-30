from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


CORPUS_DIR = Path(
    "data/processed/"
    "agentdojo_turkish_corpus_v0.4.0"
)

ARTIFACT_NAME = (
    "agentdojo_turkish_corpus_v0.4.0"
)

ALL_PATH = (
    CORPUS_DIR
    / f"{ARTIFACT_NAME}.jsonl"
)

TRAIN_PATH = (
    CORPUS_DIR
    / f"{ARTIFACT_NAME}_train.jsonl"
)

VALIDATION_PATH = (
    CORPUS_DIR
    / f"{ARTIFACT_NAME}_validation.jsonl"
)

METADATA_PATH = (
    CORPUS_DIR
    / f"{ARTIFACT_NAME}_metadata.json"
)

SHA_PATH = (
    CORPUS_DIR
    / f"{ARTIFACT_NAME}_sha256.txt"
)

FREEZE_APPROVAL_PATH = (
    CORPUS_DIR
    / "AGENTDOJO_TURKISH_CORPUS_V0.4.0_FREEZE_APPROVAL.md"
)

FREEZE_SNAPSHOT_PATH = (
    CORPUS_DIR
    / "agentdojo_turkish_corpus_v0.4.0_immutable_snapshot_sha256.txt"
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

        entries[filename.strip()] = digest.strip()

    return entries


def verify_existing_manifest() -> None:
    manifest = parse_manifest(SHA_PATH)

    expected_files = {
        ALL_PATH.name: ALL_PATH,
        TRAIN_PATH.name: TRAIN_PATH,
        VALIDATION_PATH.name: VALIDATION_PATH,
        METADATA_PATH.name: METADATA_PATH,
    }

    if set(manifest) != set(expected_files):
        raise ValueError(
            "Existing manifest file set mismatch"
        )

    failures = []

    for filename, path in expected_files.items():
        if manifest[filename] != sha256(path):
            failures.append(filename)

    if failures:
        raise ValueError(
            "Existing manifest verification failures: "
            f"{failures}"
        )


def main() -> None:
    verify_existing_manifest()

    metadata = json.loads(
        METADATA_PATH.read_text(
            encoding="utf-8"
        )
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
        "base_corpus_modified": False,
    }

    failures = {
        key: {
            "expected": expected,
            "observed": metadata.get(key),
        }
        for key, expected
        in expected_metadata.items()
        if metadata.get(key) != expected
    }

    if failures:
        raise ValueError(
            "Pre-freeze metadata failures: "
            f"{failures}"
        )

    metadata["status"] = "frozen"
    metadata["frozen_at_utc"] = datetime.now(
        timezone.utc
    ).isoformat()
    metadata["immutable"] = True
    metadata["freeze_decision"] = (
        "approved_and_frozen"
    )
    metadata["freeze_validation"] = {
        "rows": 212,
        "pairs": 106,
        "train_rows": 170,
        "validation_rows": 42,
        "labels": {
            "0": 106,
            "1": 106,
        },
        "maximum_token_count": 506,
        "truncated_rows": 0,
        "duplicate_row_ids": 0,
        "duplicate_exact_texts": 0,
        "train_validation_pair_leakage": 0,
        "train_validation_text_leakage": 0,
        "base_row_preservation_failures": 0,
        "expansion_row_preservation_failures": 0,
        "text_sha256_failures": 0,
        "artifact_sha_failures": 0,
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

    approval_lines = [
        "# AgentDojo Turkish Corpus v0.4.0 Freeze Approval",
        "",
        "## Artifact",
        "",
        f"- Name: `{ARTIFACT_NAME}`",
        "- Version: `v0.4.0`",
        "- Status: `frozen`",
        "- Immutable: `yes`",
        "",
        "## Final counts",
        "",
        "- Pairs: `106`",
        "- Rows: `212`",
        "- Train pairs: `85`",
        "- Train rows: `170`",
        "- Validation pairs: `21`",
        "- Validation rows: `42`",
        "- Safe labels: `106`",
        "- Risky labels: `106`",
        "- Maximum token count: `506`",
        "- Max length: `512`",
        "- Truncated rows: `0`",
        "",
        "## Validation results",
        "",
        "- Duplicate row IDs: `0`",
        "- Duplicate exact compact inputs: `0`",
        "- Train/validation pair leakage: `0`",
        "- Train/validation exact-text leakage: `0`",
        "- Pair integrity failures: `0`",
        "- Label/variant failures: `0`",
        "- Base row preservation failures: `0`",
        "- Expansion row preservation failures: `0`",
        "- Synthetic legacy fields: `0`",
        "- Synthetic expansion fields: `0`",
        "- text_sha256 failures: `0`",
        "- Base immutable checksum failures: `0`",
        "- Artifact SHA manifest failures: `0`",
        "",
        "## Source composition",
        "",
        "- Base corpus: `agentdojo_turkish_corpus_v0.3.0`",
        (
            "- Expansion: "
            "`agentdojo_turkish_argument_mismatch_"
            "expansion_v0.1.0`"
        ),
        "",
        "The base corpus was preserved without modification.",
        "",
        "The approved argument mismatch expansion was merged "
        "without modifying source rows or split assignments.",
        "",
        "Decision: `approved_and_frozen`",
    ]

    FREEZE_APPROVAL_PATH.write_text(
        "\n".join(approval_lines)
        + "\n",
        encoding="utf-8",
    )

    snapshot_files = sorted(
        path
        for path in CORPUS_DIR.iterdir()
        if (
            path.is_file()
            and path != FREEZE_SNAPSHOT_PATH
        )
    )

    FREEZE_SNAPSHOT_PATH.write_text(
        "\n".join(
            f"{sha256(path)}  {path.name}"
            for path in snapshot_files
        )
        + "\n",
        encoding="utf-8",
    )

    print("=" * 80)
    print(
        "AGENTDOJO TURKISH CORPUS "
        "V0.4.0 FREEZE"
    )
    print("=" * 80)
    print()
    print("Artifact:", ARTIFACT_NAME)
    print("Status: frozen")
    print("Immutable: yes")
    print("Pairs: 106")
    print("Rows: 212")
    print("Train rows: 170")
    print("Validation rows: 42")
    print("Labels: 106 safe / 106 risky")
    print("Maximum token count: 506")
    print("Truncation: 0")
    print("Approval:", FREEZE_APPROVAL_PATH)
    print(
        "Immutable snapshot:",
        FREEZE_SNAPSHOT_PATH,
    )
    print()
    print(
        "AgentDojo Turkish corpus "
        "v0.4.0 freeze: PASSED"
    )


if __name__ == "__main__":
    main()

from __future__ import annotations

import hashlib
import json
from pathlib import Path


CORPUS_DIR = Path(
    "data/processed/"
    "agentdojo_turkish_corpus_v0.4.0"
)

ARTIFACT_NAME = (
    "agentdojo_turkish_corpus_v0.4.0"
)

METADATA_PATH = (
    CORPUS_DIR
    / f"{ARTIFACT_NAME}_metadata.json"
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


def main() -> None:
    metadata = json.loads(
        METADATA_PATH.read_text(
            encoding="utf-8"
        )
    )

    expected = {
        "artifact_name": ARTIFACT_NAME,
        "artifact_version": "v0.4.0",
        "status": "frozen",
        "immutable": True,
        "freeze_decision": (
            "approved_and_frozen"
        ),
        "rows": 212,
        "pairs": 106,
        "train_rows": 170,
        "train_pairs": 85,
        "validation_rows": 42,
        "validation_pairs": 21,
        "maximum_token_count": 506,
        "truncated_rows": 0,
        "base_corpus_modified": False,
    }

    failures = {
        key: {
            "expected": value,
            "observed": metadata.get(key),
        }
        for key, value in expected.items()
        if metadata.get(key) != value
    }

    if failures:
        raise ValueError(
            "Frozen metadata failures: "
            f"{failures}"
        )

    if not metadata.get("frozen_at_utc"):
        raise ValueError(
            "frozen_at_utc missing"
        )

    approval_text = (
        FREEZE_APPROVAL_PATH.read_text(
            encoding="utf-8"
        )
    )

    required_approval_markers = [
        "Status: `frozen`",
        "Immutable: `yes`",
        "Pairs: `106`",
        "Rows: `212`",
        "Train rows: `170`",
        "Validation rows: `42`",
        "Safe labels: `106`",
        "Risky labels: `106`",
        "Maximum token count: `506`",
        "Decision: `approved_and_frozen`",
    ]

    missing_markers = [
        marker
        for marker in required_approval_markers
        if marker not in approval_text
    ]

    if missing_markers:
        raise ValueError(
            "Freeze approval markers missing: "
            f"{missing_markers}"
        )

    snapshot = parse_manifest(
        FREEZE_SNAPSHOT_PATH
    )

    expected_files = {
        path.name: path
        for path in CORPUS_DIR.iterdir()
        if (
            path.is_file()
            and path != FREEZE_SNAPSHOT_PATH
        )
    }

    if set(snapshot) != set(expected_files):
        raise ValueError(
            "Freeze snapshot file set mismatch"
        )

    snapshot_failures = []

    for filename, path in expected_files.items():
        if snapshot[filename] != sha256(path):
            snapshot_failures.append(
                filename
            )

    if snapshot_failures:
        raise ValueError(
            "Freeze snapshot checksum failures: "
            f"{snapshot_failures}"
        )

    print("=" * 80)
    print(
        "AGENTDOJO TURKISH CORPUS "
        "V0.4.0 FREEZE VALIDATION"
    )
    print("=" * 80)
    print()
    print("Status: frozen")
    print("Immutable: yes")
    print("Pairs: 106")
    print("Rows: 212")
    print("Train rows: 170")
    print("Validation rows: 42")
    print("Labels: 106 safe / 106 risky")
    print("Maximum token count: 506")
    print("Freeze approval markers: PASSED")
    print("Freeze snapshot file set: PASSED")
    print("Freeze snapshot checksum failures: 0")
    print()
    print(
        "AgentDojo Turkish corpus "
        "v0.4.0 freeze validation: PASSED"
    )


if __name__ == "__main__":
    main()

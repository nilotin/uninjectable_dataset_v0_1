from __future__ import annotations

import hashlib
import json
from pathlib import Path


FROZEN_DIR = Path(
    "data/processed/"
    "agentdojo_turkish_corpus_v0.3.0"
)

PLAN_DIR = Path(
    "data/planning/"
    "agentdojo_turkish_corpus_v0.4.0_merge_plan"
)

PLAN_JSON_PATH = (
    PLAN_DIR
    / "agentdojo_turkish_corpus_v0.4.0_merge_plan.json"
)

PLAN_MD_PATH = (
    PLAN_DIR
    / "AGENTDOJO_TURKISH_CORPUS_V0.4.0_MERGE_PLAN.md"
)

FROZEN_SHA_PATH = (
    PLAN_DIR
    / "agentdojo_turkish_corpus_v0.3.0_immutable_snapshot_sha256.txt"
)

PLAN_SHA_PATH = (
    PLAN_DIR
    / "agentdojo_turkish_corpus_v0.4.0_merge_plan_sha256.txt"
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


def main() -> None:
    plan = json.loads(
        PLAN_JSON_PATH.read_text(
            encoding="utf-8"
        )
    )

    target = (
        plan["planned_counts"]["target"]
    )

    expected_target = {
        "pairs": 106,
        "rows": 212,
        "train_pairs": 85,
        "train_rows": 170,
        "validation_pairs": 21,
        "validation_rows": 42,
        "label_counts": {
            "0": 106,
            "1": 106,
        },
    }

    for key, expected in expected_target.items():
        observed = target.get(key)

        if observed != expected:
            raise ValueError(
                f"Target mismatch for {key}: "
                f"expected={expected}, "
                f"observed={observed}"
            )

    required_common = set(
        plan["schema_policy"]
        ["required_common_fields"]
    )

    expected_required = {
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

    if required_common != expected_required:
        raise ValueError(
            "Required common schema mismatch"
        )

    crosslingual_policy = (
        plan["schema_policy"]
        ["crosslingual_group_id"]
    )

    if (
        crosslingual_policy["target_type"]
        != "string_or_null"
    ):
        raise ValueError(
            "Invalid crosslingual target type"
        )

    if not crosslingual_policy[
        "synthetic_values_forbidden"
    ]:
        raise ValueError(
            "Synthetic crosslingual IDs "
            "must be forbidden"
        )

    if not plan["immutability_policy"][
        "v0.3.0_must_not_be_modified"
    ]:
        raise ValueError(
            "v0.3.0 immutability is not enforced"
        )

    if not plan["split_policy"][
        "preserve_existing_split_assignments"
    ]:
        raise ValueError(
            "Split preservation is not enforced"
        )

    if not plan["split_policy"][
        "resplitting_forbidden"
    ]:
        raise ValueError(
            "Re-splitting must be forbidden"
        )

    if not plan["content_policy"][
        "text_must_not_change"
    ]:
        raise ValueError(
            "Text immutability is not enforced"
        )

    if not plan["content_policy"][
        "labels_must_not_change"
    ]:
        raise ValueError(
            "Label immutability is not enforced"
        )

    frozen_manifest = parse_manifest(
        FROZEN_SHA_PATH
    )

    frozen_files = sorted(
        path
        for path in FROZEN_DIR.iterdir()
        if path.is_file()
    )

    expected_frozen_names = {
        path.name
        for path in frozen_files
    }

    if (
        set(frozen_manifest)
        != expected_frozen_names
    ):
        raise ValueError(
            "Frozen checksum snapshot file set mismatch"
        )

    frozen_sha_failures = []

    for path in frozen_files:
        expected = frozen_manifest[
            path.name
        ]

        observed = sha256(path)

        if expected != observed:
            frozen_sha_failures.append(
                path.name
            )

    if frozen_sha_failures:
        raise ValueError(
            "Frozen checksum failures: "
            f"{frozen_sha_failures}"
        )

    plan_manifest = parse_manifest(
        PLAN_SHA_PATH
    )

    plan_files = {
        PLAN_JSON_PATH.name: PLAN_JSON_PATH,
        PLAN_MD_PATH.name: PLAN_MD_PATH,
        FROZEN_SHA_PATH.name: FROZEN_SHA_PATH,
    }

    if set(plan_manifest) != set(plan_files):
        raise ValueError(
            "Plan checksum manifest file set mismatch"
        )

    plan_sha_failures = []

    for filename, path in plan_files.items():
        if (
            plan_manifest[filename]
            != sha256(path)
        ):
            plan_sha_failures.append(
                filename
            )

    if plan_sha_failures:
        raise ValueError(
            "Plan checksum failures: "
            f"{plan_sha_failures}"
        )

    print("=" * 80)
    print(
        "AGENTDOJO TURKISH CORPUS "
        "V0.4.0 MERGE PLAN VALIDATION"
    )
    print("=" * 80)
    print()
    print("Target pairs: 106")
    print("Target rows: 212")
    print("Target train pairs: 85")
    print("Target train rows: 170")
    print("Target validation pairs: 21")
    print("Target validation rows: 42")
    print("Target labels: 106 safe / 106 risky")
    print("Union schema policy: PASSED")
    print(
        "crosslingual_group_id string|null policy: PASSED"
    )
    print("Legacy provenance preservation: PASSED")
    print("Expansion metadata preservation: PASSED")
    print("Split preservation policy: PASSED")
    print("Content immutability policy: PASSED")
    print("Frozen checksum failures: 0")
    print("Plan checksum failures: 0")
    print()
    print("v0.4.0 merge plan validation: PASSED")


if __name__ == "__main__":
    main()

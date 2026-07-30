from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


FROZEN_DIR = Path(
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

EXPANSION_PATH = (
    EXPANSION_DIR
    / f"{EXPANSION_NAME}.jsonl"
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


def locate_frozen_split(split: str) -> Path:
    matches = sorted(
        path
        for path in FROZEN_DIR.glob("*.jsonl")
        if split in path.stem.lower()
    )

    if len(matches) != 1:
        raise ValueError(
            f"Expected exactly one frozen {split} JSONL, "
            f"found: {matches}"
        )

    return matches[0]


def pair_count(rows: list[dict[str, Any]]) -> int:
    return len(
        {
            str(row["pair_id"])
            for row in rows
        }
    )


def main() -> None:
    PLAN_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    frozen_train_path = locate_frozen_split(
        "train"
    )

    frozen_validation_path = locate_frozen_split(
        "validation"
    )

    frozen_train_rows = load_jsonl(
        frozen_train_path
    )

    frozen_validation_rows = load_jsonl(
        frozen_validation_path
    )

    frozen_rows = (
        frozen_train_rows
        + frozen_validation_rows
    )

    expansion_rows = load_jsonl(
        EXPANSION_PATH
    )

    expansion_train_rows = [
        row
        for row in expansion_rows
        if row["split"] == "train"
    ]

    expansion_validation_rows = [
        row
        for row in expansion_rows
        if row["split"] == "validation"
    ]

    planned_train_rows = (
        frozen_train_rows
        + expansion_train_rows
    )

    planned_validation_rows = (
        frozen_validation_rows
        + expansion_validation_rows
    )

    planned_rows = (
        planned_train_rows
        + planned_validation_rows
    )

    planned_label_counts = Counter(
        int(row["general_risk_label"])
        for row in planned_rows
    )

    planned_split_counts = Counter(
        str(row["split"])
        for row in planned_rows
    )

    expansion_category_counts = Counter(
        str(row["category"])
        for row in expansion_rows
    )

    frozen_keys = set().union(
        *(set(row) for row in frozen_rows)
    )

    expansion_keys = set().union(
        *(set(row) for row in expansion_rows)
    )

    union_keys = sorted(
        frozen_keys | expansion_keys
    )

    required_common_fields = [
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
    ]

    optional_legacy_fields = [
        "compact_serialization",
        "provenance",
        "source_row_id",
        "source_pair_id",
    ]

    optional_expansion_fields = [
        "category",
        "changed_argument_paths",
    ]

    merge_plan = {
        "plan_name": (
            "agentdojo_turkish_corpus_"
            "v0.4.0_merge_plan"
        ),
        "plan_version": "v0.1.0",
        "created_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "status": "approved_for_merge_execution",
        "target_artifact": (
            "agentdojo_turkish_corpus_v0.4.0"
        ),
        "source_artifacts": {
            "frozen_base": (
                "agentdojo_turkish_corpus_v0.3.0"
            ),
            "approved_expansion": EXPANSION_NAME,
        },
        "immutability_policy": {
            "v0.3.0_must_not_be_modified": True,
            "v0.3.0_checksum_snapshot_required": True,
            "merge_output_must_use_new_directory": True,
        },
        "planned_counts": {
            "base": {
                "pairs": pair_count(frozen_rows),
                "rows": len(frozen_rows),
                "train_pairs": pair_count(
                    frozen_train_rows
                ),
                "train_rows": len(
                    frozen_train_rows
                ),
                "validation_pairs": pair_count(
                    frozen_validation_rows
                ),
                "validation_rows": len(
                    frozen_validation_rows
                ),
            },
            "expansion": {
                "pairs": pair_count(
                    expansion_rows
                ),
                "rows": len(expansion_rows),
                "train_pairs": pair_count(
                    expansion_train_rows
                ),
                "train_rows": len(
                    expansion_train_rows
                ),
                "validation_pairs": pair_count(
                    expansion_validation_rows
                ),
                "validation_rows": len(
                    expansion_validation_rows
                ),
                "category_row_counts": dict(
                    sorted(
                        expansion_category_counts.items()
                    )
                ),
            },
            "target": {
                "pairs": pair_count(planned_rows),
                "rows": len(planned_rows),
                "train_pairs": pair_count(
                    planned_train_rows
                ),
                "train_rows": len(
                    planned_train_rows
                ),
                "validation_pairs": pair_count(
                    planned_validation_rows
                ),
                "validation_rows": len(
                    planned_validation_rows
                ),
                "split_row_counts": dict(
                    planned_split_counts
                ),
                "label_counts": {
                    str(key): value
                    for key, value in sorted(
                        planned_label_counts.items()
                    )
                },
            },
        },
        "schema_policy": {
            "strategy": "union_schema",
            "required_common_fields": (
                required_common_fields
            ),
            "optional_legacy_fields": (
                optional_legacy_fields
            ),
            "optional_expansion_fields": (
                optional_expansion_fields
            ),
            "all_union_fields": union_keys,
            "crosslingual_group_id": {
                "target_type": "string_or_null",
                "frozen_rows": (
                    "preserve existing string values"
                ),
                "expansion_rows": (
                    "preserve null values"
                ),
                "synthetic_values_forbidden": True,
            },
            "legacy_provenance_policy": {
                "frozen_rows": (
                    "preserve compact_serialization, "
                    "provenance, source_row_id and "
                    "source_pair_id exactly when present"
                ),
                "expansion_rows": (
                    "do not synthesize missing legacy fields"
                ),
            },
            "expansion_metadata_policy": {
                "expansion_rows": (
                    "preserve category and "
                    "changed_argument_paths"
                ),
                "frozen_rows": (
                    "do not synthesize category or "
                    "changed_argument_paths"
                ),
            },
            "merge_provenance_policy": {
                "preserve_existing_objects": True,
                "overwrite_existing_provenance": False,
                "optional_v0_4_wrapper": (
                    "may add a new top-level merge wrapper "
                    "only if previous merge_provenance is "
                    "nested without modification"
                ),
            },
        },
        "split_policy": {
            "preserve_existing_split_assignments": True,
            "resplitting_forbidden": True,
            "pair_split_integrity_required": True,
            "train_validation_pair_leakage_forbidden": True,
        },
        "content_policy": {
            "text_must_not_change": True,
            "text_sha256_must_remain_valid": True,
            "labels_must_not_change": True,
            "tokenization_metadata_must_be_preserved": True,
            "max_length": 512,
            "truncation_forbidden": True,
        },
        "collision_policy": {
            "duplicate_row_ids_forbidden": True,
            "duplicate_pair_ids_forbidden": True,
            "duplicate_exact_text_forbidden": True,
        },
        "execution_sequence": [
            "verify v0.3.0 immutable checksum snapshot",
            "load frozen train and validation rows",
            "load approved expansion train and validation rows",
            "preserve all existing split assignments",
            "merge train with train and validation with validation",
            "sort rows deterministically by pair_id and variant",
            "write new v0.4.0 directory only",
            "validate counts, hashes, leakage and schema policy",
            "write metadata and SHA256 manifest",
            "freeze v0.4.0 only after validation passes",
        ],
    }

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
        observed = (
            merge_plan["planned_counts"]
            ["target"][key]
        )

        if observed != expected:
            raise ValueError(
                f"Target count mismatch for {key}: "
                f"expected={expected}, "
                f"observed={observed}"
            )

    PLAN_JSON_PATH.write_text(
        json.dumps(
            merge_plan,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    frozen_snapshot_files = sorted(
        path
        for path in FROZEN_DIR.iterdir()
        if path.is_file()
    )

    frozen_sha_lines = [
        f"{sha256(path)}  {path.name}"
        for path in frozen_snapshot_files
    ]

    FROZEN_SHA_PATH.write_text(
        "\n".join(frozen_sha_lines)
        + "\n",
        encoding="utf-8",
    )

    md_lines = [
        "# AgentDojo Turkish Corpus v0.4.0 Merge Plan",
        "",
        "## Status",
        "",
        "- Decision: `approved_for_merge_execution`",
        "- Target: `agentdojo_turkish_corpus_v0.4.0`",
        "- Base: `agentdojo_turkish_corpus_v0.3.0`",
        (
            "- Expansion: "
            "`agentdojo_turkish_argument_mismatch_"
            "expansion_v0.1.0`"
        ),
        "- Base corpus immutable: `yes`",
        "- Existing split assignments preserved: `yes`",
        "",
        "## Planned counts",
        "",
        "| Artifact | Pairs | Rows | Train pairs | Train rows | Validation pairs | Validation rows |",
        "|---|---:|---:|---:|---:|---:|---:|",
        "| v0.3.0 | 82 | 164 | 67 | 134 | 15 | 30 |",
        "| expansion | 24 | 48 | 18 | 36 | 6 | 12 |",
        "| v0.4.0 target | 106 | 212 | 85 | 170 | 21 | 42 |",
        "",
        "Target label balance: `106 safe / 106 risky`.",
        "",
        "## Schema policy",
        "",
        "The target uses a union schema.",
        "",
        "Required common fields remain mandatory for every row:",
        "",
    ]

    md_lines.extend(
        f"- `{field}`"
        for field in required_common_fields
    )

    md_lines.extend(
        [
            "",
            "Legacy-only optional fields are preserved only "
            "where they already exist:",
            "",
        ]
    )

    md_lines.extend(
        f"- `{field}`"
        for field in optional_legacy_fields
    )

    md_lines.extend(
        [
            "",
            "Expansion-only optional fields are preserved only "
            "for expansion rows:",
            "",
        ]
    )

    md_lines.extend(
        f"- `{field}`"
        for field in optional_expansion_fields
    )

    md_lines.extend(
        [
            "",
            "## crosslingual_group_id policy",
            "",
            "- Frozen rows retain existing string values.",
            "- Expansion rows retain `null`.",
            "- Target type is `string | null`.",
            "- Synthetic crosslingual IDs are forbidden.",
            "",
            "## Provenance policy",
            "",
            "- Existing provenance objects are never overwritten.",
            "- Frozen legacy provenance remains unchanged.",
            "- Expansion provenance remains unchanged.",
            "- Missing legacy fields are not synthesized.",
            (
                "- Missing expansion metadata is not synthesized "
                "for frozen rows."
            ),
            "",
            "## Split policy",
            "",
            "- Existing train/validation assignments are preserved.",
            "- No re-splitting is allowed.",
            "- Both rows of every pair remain in the same split.",
            "- Train/validation pair leakage is forbidden.",
            "",
            "## Content policy",
            "",
            "- Serialized `text` is immutable.",
            "- `text_sha256` must remain valid.",
            "- Labels are immutable.",
            "- Tokenization metadata is preserved.",
            "- Maximum length remains `512`.",
            "- Truncated rows are forbidden.",
            "",
            "## Execution order",
            "",
        ]
    )

    md_lines.extend(
        f"{index}. {step}"
        for index, step in enumerate(
            merge_plan["execution_sequence"],
            start=1,
        )
    )

    md_lines.extend(
        [
            "",
            "## Merge boundary",
            "",
            "This plan does not itself create or freeze v0.4.0.",
            "It authorizes a separate deterministic merge build "
            "and validation step.",
        ]
    )

    PLAN_MD_PATH.write_text(
        "\n".join(md_lines) + "\n",
        encoding="utf-8",
    )

    plan_files = [
        PLAN_JSON_PATH,
        PLAN_MD_PATH,
        FROZEN_SHA_PATH,
    ]

    PLAN_SHA_PATH.write_text(
        "\n".join(
            f"{sha256(path)}  {path.name}"
            for path in plan_files
        )
        + "\n",
        encoding="utf-8",
    )

    print("=" * 80)
    print(
        "AGENTDOJO TURKISH CORPUS "
        "V0.4.0 MERGE PLAN BUILD"
    )
    print("=" * 80)
    print()
    print("Base pairs:", pair_count(frozen_rows))
    print("Base rows:", len(frozen_rows))
    print(
        "Expansion pairs:",
        pair_count(expansion_rows),
    )
    print(
        "Expansion rows:",
        len(expansion_rows),
    )
    print(
        "Target pairs:",
        pair_count(planned_rows),
    )
    print("Target rows:", len(planned_rows))
    print(
        "Target train rows:",
        len(planned_train_rows),
    )
    print(
        "Target validation rows:",
        len(planned_validation_rows),
    )
    print(
        "Target labels:",
        dict(planned_label_counts),
    )
    print()
    print("Plan JSON:", PLAN_JSON_PATH)
    print("Plan Markdown:", PLAN_MD_PATH)
    print(
        "Frozen checksum snapshot:",
        FROZEN_SHA_PATH,
    )
    print("Plan manifest:", PLAN_SHA_PATH)
    print()
    print("v0.4.0 merge plan build: PASSED")


if __name__ == "__main__":
    main()

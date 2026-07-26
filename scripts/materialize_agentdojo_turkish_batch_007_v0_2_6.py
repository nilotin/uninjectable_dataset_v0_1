from __future__ import annotations

"""
Materialize AgentDojo Turkish Batch 007 with the frozen v0.2.6
structured and compact serialization contract.

This script deliberately reuses the already validated Batch 001
materializer so both batches are guaranteed to share the same output
schema, section ordering, compact view, tokenizer checks, and leakage
rules. Batch 007 review metadata is adapted in memory only; the reviewed
source artifact is never modified.
"""

from pathlib import Path
from typing import Any

import materialize_agentdojo_turkish_batch_001_v0_2_6 as base


BASE_INTERIM = Path(
    "data/interim/"
    "agentdojo_turkish_full_translation_batches_v0.2.0"
)

REVIEWED_TRANSLATION_PATH = (
    BASE_INTERIM
    / "agentdojo_tr_batch_007_v0.2.2_reviewed.jsonl"
)

REVIEW_APPLY_REPORT_PATH = (
    BASE_INTERIM
    / "agentdojo_tr_batch_007_v0.2.2_review_apply_report.json"
)

OUTPUT_DIR = Path(
    "data/processed/"
    "agentdojo_turkish_batch_007_v0.2.6"
)

STRUCTURED_ALL_PATH = (
    OUTPUT_DIR
    / "agentdojo_turkish_batch_007_structured_v0.2.6.jsonl"
)

STRUCTURED_TRAIN_PATH = (
    OUTPUT_DIR
    / "agentdojo_turkish_batch_007_structured_v0.2.6_train.jsonl"
)

STRUCTURED_VALIDATION_PATH = (
    OUTPUT_DIR
    / "agentdojo_turkish_batch_007_structured_v0.2.6_validation.jsonl"
)

COMPACT_ALL_PATH = (
    OUTPUT_DIR
    / "agentdojo_turkish_batch_007_bert_compact_v0.2.6.jsonl"
)

COMPACT_TRAIN_PATH = (
    OUTPUT_DIR
    / "agentdojo_turkish_batch_007_bert_compact_v0.2.6_train.jsonl"
)

COMPACT_VALIDATION_PATH = (
    OUTPUT_DIR
    / "agentdojo_turkish_batch_007_bert_compact_v0.2.6_validation.jsonl"
)

REPORT_PATH = (
    OUTPUT_DIR
    / "agentdojo_turkish_batch_007_v0.2.6_report.json"
)

MANIFEST_PATH = (
    OUTPUT_DIR
    / "agentdojo_turkish_batch_007_v0.2.6_sha256.txt"
)


_original_load_jsonl = base.load_jsonl


def load_jsonl_with_review_compatibility(
    path: Path,
) -> list[dict[str, Any]]:
    """
    Adapt Batch 007 review vocabulary to the frozen Batch 001
    materializer contract in memory.

    Batch 007 reviewed values:
      approve
      human_review_approved
      review_artifact_version=v0.2.2

    Frozen materializer values:
      approve_translation
      human_reviewed_approved
      human_review_version
    """

    rows = _original_load_jsonl(path)

    if path != REVIEWED_TRANSLATION_PATH:
        return rows

    adapted_rows: list[dict[str, Any]] = []

    for row in rows:
        adapted = dict(row)

        pair_id = str(
            adapted.get("pair_id", "<missing-pair-id>")
        )

        decision = adapted.get(
            "human_review_decision"
        )
        status = adapted.get(
            "translation_status"
        )

        if decision != "approve":
            raise ValueError(
                f"{pair_id}: Batch 007 pair is not approved; "
                f"decision={decision!r}"
            )

        if status != "human_review_approved":
            raise ValueError(
                f"{pair_id}: unexpected Batch 007 review "
                f"status={status!r}"
            )

        review_version = adapted.get(
            "review_artifact_version"
        )
        if not review_version:
            raise ValueError(
                f"{pair_id}: missing review_artifact_version"
            )

        adapted[
            "human_review_decision"
        ] = "approve_translation"
        adapted[
            "translation_status"
        ] = "human_reviewed_approved"
        adapted[
            "human_review_version"
        ] = str(review_version)

        adapted_rows.append(adapted)

    return adapted_rows


def configure_base_materializer() -> None:
    """Point the frozen materializer at Batch 007 inputs/outputs."""

    base.TRANSLATION_PATH = (
        REVIEWED_TRANSLATION_PATH
    )
    base.TRANSLATION_REPORT_PATH = (
        REVIEW_APPLY_REPORT_PATH
    )

    base.OUTPUT_DIR = OUTPUT_DIR

    base.STRUCTURED_ALL_PATH = (
        STRUCTURED_ALL_PATH
    )
    base.STRUCTURED_TRAIN_PATH = (
        STRUCTURED_TRAIN_PATH
    )
    base.STRUCTURED_VALIDATION_PATH = (
        STRUCTURED_VALIDATION_PATH
    )

    base.COMPACT_ALL_PATH = (
        COMPACT_ALL_PATH
    )
    base.COMPACT_TRAIN_PATH = (
        COMPACT_TRAIN_PATH
    )
    base.COMPACT_VALIDATION_PATH = (
        COMPACT_VALIDATION_PATH
    )

    base.REPORT_PATH = REPORT_PATH
    base.MANIFEST_PATH = MANIFEST_PATH

    base.EXPECTED_PAIR_COUNT = 10
    base.EXPECTED_ROW_COUNT = 20

    base.load_jsonl = (
        load_jsonl_with_review_compatibility
    )


def main() -> None:
    if not REVIEWED_TRANSLATION_PATH.exists():
        raise FileNotFoundError(
            "Missing reviewed Batch 007 artifact: "
            f"{REVIEWED_TRANSLATION_PATH}"
        )

    if not REVIEW_APPLY_REPORT_PATH.exists():
        raise FileNotFoundError(
            "Missing Batch 007 review report: "
            f"{REVIEW_APPLY_REPORT_PATH}"
        )

    configure_base_materializer()

    print("=" * 80)
    print(
        "AGENTDOJO TURKISH BATCH 007 "
        "MATERIALIZATION v0.2.6"
    )
    print("=" * 80)
    print()
    print(
        "Reusing frozen Batch 001 v0.2.6 "
        "materialization contract."
    )
    print(
        "Review metadata compatibility adaptation: "
        "in-memory only"
    )
    print()

    base.main()


if __name__ == "__main__":
    main()

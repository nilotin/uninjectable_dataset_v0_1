from __future__ import annotations

import json
from pathlib import Path
from typing import Any


BASE_DIR = Path(
    "data/interim/"
    "agentdojo_turkish_full_translation_batches_v0.2.0"
)

FINAL_TRANSLATION_PATH = (
    BASE_DIR
    / "agentdojo_tr_batch_001_v0.2.4_final_human_reviewed.jsonl"
)

TRAIN_PATH = Path(
    "data/processed/"
    "agentdojo_group_aware_split_v0.1.5/"
    "agentdojo_contextual_action_attempt_labeled_pool_v0.1.5_train.jsonl"
)

VALIDATION_PATH = Path(
    "data/processed/"
    "agentdojo_group_aware_split_v0.1.5/"
    "agentdojo_contextual_action_attempt_labeled_pool_v0.1.5_validation.jsonl"
)

POLICY_REGISTRY_PATH = Path(
    "data/interim/"
    "agentdojo_turkish_full_policy_registry_v0.2.0.jsonl"
)


def load_jsonl(
    path: Path,
) -> list[dict[str, Any]]:

    rows = []

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:

        for line_number, line in enumerate(
            file,
            start=1,
        ):
            line = line.strip()

            if not line:
                continue

            try:
                rows.append(
                    json.loads(line)
                )

            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid JSONL in {path}, "
                    f"line {line_number}."
                ) from error

    return rows


def describe_value(
    value: Any,
) -> Any:

    if isinstance(value, dict):
        return {
            "type": "dict",
            "keys": sorted(value.keys()),
        }

    if isinstance(value, list):
        return {
            "type": "list",
            "length": len(value),
        }

    return {
        "type": type(value).__name__,
        "preview": str(value)[:120],
    }


def main() -> None:

    translations = load_jsonl(
        FINAL_TRANSLATION_PATH
    )

    train_rows = load_jsonl(
        TRAIN_PATH
    )

    validation_rows = load_jsonl(
        VALIDATION_PATH
    )

    policy_rows = load_jsonl(
        POLICY_REGISTRY_PATH
    )

    if len(translations) != 10:
        raise ValueError(
            f"Expected 10 translations, "
            f"found {len(translations)}."
        )

    first_translation = translations[0]

    pair_id = str(
        first_translation["pair_id"]
    )

    canonical_rows = [
        row
        for row in (
            train_rows
            +
            validation_rows
        )
        if str(row["pair_id"]) == pair_id
    ]

    if len(canonical_rows) != 2:
        raise ValueError(
            f"Expected two canonical rows for "
            f"{pair_id}, found {len(canonical_rows)}."
        )

    first_canonical = canonical_rows[0]

    summary = {
        "translation_pair_id": pair_id,

        "final_translation": {
            "top_level_keys": sorted(
                first_translation.keys()
            ),
            "field_types": {
                key: describe_value(value)
                for key, value
                in first_translation.items()
            },
        },

        "canonical_source": {
            "top_level_keys": sorted(
                first_canonical.keys()
            ),
            "field_types": {
                key: describe_value(value)
                for key, value
                in first_canonical.items()
            },
        },

        "canonical_pair_variants": [
            {
                "row_id": row.get("row_id"),
                "variant": row.get("variant"),
                "split": row.get("split"),
                "label": row.get("label"),
                "general_risk_label": row.get(
                    "general_risk_label"
                ),
                "model_input": describe_value(
                    row.get("model_input")
                ),
                "sections": describe_value(
                    row.get("sections")
                ),
                "provenance": describe_value(
                    row.get("provenance")
                ),
            }
            for row in canonical_rows
        ],

        "policy_registry": {
            "row_count": len(policy_rows),
            "top_level_keys": (
                sorted(policy_rows[0].keys())
                if policy_rows
                else []
            ),
            "field_types": (
                {
                    key: describe_value(value)
                    for key, value
                    in policy_rows[0].items()
                }
                if policy_rows
                else {}
            ),
        },
    }

    print(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from transformers import AutoTokenizer


INPUT_PATH = Path(
    "data/planning/"
    "agentdojo_turkish_argument_mismatch_batch_v0.1.0/"
    "body_or_subject_mismatch_candidates_v0.1.0.jsonl"
)

OUTPUT_DIR = Path(
    "data/planning/"
    "agentdojo_turkish_argument_mismatch_batch_v0.1.0/"
    "body_or_subject_mismatch_rows_v0.1.0"
)

OUTPUT_ALL = (
    OUTPUT_DIR
    / "body_or_subject_mismatch_rows_v0.1.0.jsonl"
)

OUTPUT_TRAIN = (
    OUTPUT_DIR
    / "body_or_subject_mismatch_rows_v0.1.0_train.jsonl"
)

OUTPUT_VALIDATION = (
    OUTPUT_DIR
    / "body_or_subject_mismatch_rows_v0.1.0_validation.jsonl"
)

OUTPUT_METADATA = (
    OUTPUT_DIR
    / "body_or_subject_mismatch_rows_v0.1.0_metadata.json"
)

OUTPUT_MANIFEST = (
    OUTPUT_DIR
    / "body_or_subject_mismatch_rows_v0.1.0_sha256.txt"
)

TOKENIZER_NAME = (
    "google-bert/"
    "bert-base-multilingual-cased"
)

MAX_LENGTH = 512
EXPECTED_PAIRS = 4
EXPECTED_ROWS = 8


def load_jsonl(
    path: Path,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue

        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"{path}:{line_number}: invalid JSON"
            ) from exc

    return rows


def sha256_text(value: str) -> str:
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


RAW_EXPRESSION_PATTERN = re.compile(
    r"^(?:self|pre_environment)"
    r"(?:\.[A-Za-z_][A-Za-z0-9_]*"
    r"|\[[^\]]+\])+$"
)


def serialize_value(value: Any) -> str:
    if isinstance(value, str):
        if RAW_EXPRESSION_PATTERN.fullmatch(value):
            return value

        return repr(value)

    if isinstance(value, list):
        return (
            "["
            + ", ".join(
                serialize_value(item)
                for item in value
            )
            + "]"
        )

    if isinstance(value, tuple):
        serialized = ", ".join(
            serialize_value(item)
            for item in value
        )

        if len(value) == 1:
            serialized += ","

        return f"({serialized})"

    if isinstance(value, dict):
        return (
            "{"
            + ", ".join(
                f"{repr(key)}: "
                f"{serialize_value(item)}"
                for key, item
                in value.items()
            )
            + "}"
        )

    return repr(value)


def serialize_text(
    pair: dict[str, Any],
    attempted_tool: str,
    attempted_args: dict[str, Any],
) -> str:
    source = pair["source"]
    agent_facts = pair["agent_facts"]

    sections = [
        "[USER_AUTHORIZATION]",
        (
            "authorized_tool="
            f"{pair['authorized_tool']}"
        ),
        (
            "authorized_args="
            f"{serialize_value(pair['authorized_args'])}"
        ),
        "",
        "[ATTEMPTED_ACTION]",
        f"tool_name={attempted_tool}",
        (
            "args="
            f"{serialize_value(attempted_args)}"
        ),
        (
            "capability_class="
            f"{pair['capability_class']}"
        ),
        (
            "action_impact="
            f"{pair['action_impact']}"
        ),
        "",
        "[RETRIEVED_CONTENT]",
        str(pair["retrieved_content"]),
        "",
        "[SOURCE]",
        (
            "trust_level="
            f"{source['trust_level']}"
        ),
        (
            "source_type="
            f"{source['source_type']}"
        ),
        (
            "surface_type="
            f"{source['surface_type']}"
        ),
        (
            "retrieval_channel="
            f"{source['retrieval_channel']}"
        ),
        "",
        "[AGENT_FACTS]",
        (
            "agent_role="
            f"{agent_facts['agent_role']}"
        ),
        (
            "attempted_tool_allowed="
            f"{str(agent_facts['attempted_tool_allowed']).lower()}"
        ),
    ]

    return "\n".join(sections)


def build_row(
    pair: dict[str, Any],
    variant: str,
    tokenizer: Any,
) -> dict[str, Any]:
    if variant == "safe":
        attempted_tool = pair[
            "safe_attempted_tool"
        ]
        attempted_args = pair[
            "safe_attempted_args"
        ]
        label = 0
    elif variant == "risky":
        attempted_tool = pair[
            "risky_attempted_tool"
        ]
        attempted_args = pair[
            "risky_attempted_args"
        ]
        label = 1
    else:
        raise ValueError(
            f"Unsupported variant: {variant}"
        )

    text = serialize_text(
        pair,
        attempted_tool,
        attempted_args,
    )

    encoded_without_truncation = tokenizer(
        text,
        add_special_tokens=True,
        truncation=False,
    )

    token_count = len(
        encoded_without_truncation[
            "input_ids"
        ]
    )

    if token_count > MAX_LENGTH:
        raise ValueError(
            f"{pair['pair_id']}::{variant}: "
            f"{token_count} tokens exceeds "
            f"max_length={MAX_LENGTH}"
        )

    row_id = (
        f"{pair['pair_id']}::"
        f"{variant}::action_attempt::tr"
    )

    return {
        "row_id": row_id,
        "pair_id": pair["pair_id"],
        "session_group_id": (
            pair["session_group_id"]
        ),
        "crosslingual_group_id": (
            pair["crosslingual_group_id"]
        ),
        "suite": pair["suite"],
        "variant": variant,
        "language": "tr",
        "source_language": "tr",
        "split": pair["split"],
        "text": text,
        "general_risk_label": label,
        "label_source": (
            "manual_contrastive_review"
        ),
        "category": pair["category"],
        "changed_argument_paths": (
            pair["changed_argument_paths"]
        ),
        "schema_version": (
            "agentdojo_turkish_argument_"
            "mismatch_row_v0.1.0"
        ),
        "text_sha256": sha256_text(text),
        "tokenization": {
            "tokenizer_name": TOKENIZER_NAME,
            "max_length": MAX_LENGTH,
            "token_count": token_count,
            "truncated": False,
        },
        "merge_provenance": {
            "batch_name": (
                "agentdojo_turkish_argument_"
                "mismatch_batch_v0.1.0"
            ),
            "source_scenario_id": (
                pair["source_scenario_id"]
            ),
            "candidate_pair_id": (
                pair["pair_id"]
            ),
            "created_at": datetime.now(
                timezone.utc
            ).isoformat(),
        },
    }


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


def main() -> None:
    if not INPUT_PATH.exists():
        raise FileNotFoundError(INPUT_PATH)

    pairs = load_jsonl(INPUT_PATH)

    if len(pairs) != EXPECTED_PAIRS:
        raise ValueError(
            f"Expected {EXPECTED_PAIRS} pairs, "
            f"found {len(pairs)}"
        )

    for pair in pairs:
        if pair.get("category") != "body_or_subject_mismatch":
            raise ValueError(
                f"{pair.get('pair_id')}: expected "
                "category=body_or_subject_mismatch"
            )

        allowed_changed_paths = {
            ("body",),
            ("content",),
            ("subject",),
            ("subject", "body"),
        }

        observed_changed_paths = tuple(
            pair.get(
                "changed_argument_paths",
                [],
            )
        )

        if observed_changed_paths not in allowed_changed_paths:
            raise ValueError(
                f"{pair.get('pair_id')}: invalid "
                "body/subject changed paths: "
                f"{observed_changed_paths}"
            )

    tokenizer = AutoTokenizer.from_pretrained(
        TOKENIZER_NAME,
        use_fast=True,
    )

    rows: list[dict[str, Any]] = []

    for pair in pairs:
        rows.append(
            build_row(
                pair,
                "safe",
                tokenizer,
            )
        )
        rows.append(
            build_row(
                pair,
                "risky",
                tokenizer,
            )
        )

    if len(rows) != EXPECTED_ROWS:
        raise ValueError(
            f"Expected {EXPECTED_ROWS} rows, "
            f"found {len(rows)}"
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

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    write_jsonl(
        OUTPUT_ALL,
        rows,
    )

    write_jsonl(
        OUTPUT_TRAIN,
        train_rows,
    )

    write_jsonl(
        OUTPUT_VALIDATION,
        validation_rows,
    )

    metadata = {
        "artifact": (
            "body_or_subject_mismatch_rows_v0.1.0"
        ),
        "created_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "source": str(INPUT_PATH),
        "tokenizer": TOKENIZER_NAME,
        "max_length": MAX_LENGTH,
        "counts": {
            "pairs": len(pairs),
            "rows": len(rows),
            "train_rows": len(train_rows),
            "validation_rows": len(
                validation_rows
            ),
            "safe_rows": sum(
                row["general_risk_label"] == 0
                for row in rows
            ),
            "risky_rows": sum(
                row["general_risk_label"] == 1
                for row in rows
            ),
        },
        "token_counts": {
            "minimum": min(
                row["tokenization"][
                    "token_count"
                ]
                for row in rows
            ),
            "maximum": max(
                row["tokenization"][
                    "token_count"
                ]
                for row in rows
            ),
        },
        "invariants": {
            "tool_unchanged_within_pair": True,
            "only_body_or_subject_arguments_change": True,
            "truncation_detected": False,
            "labels_in_serialized_text": False,
        },
    }

    OUTPUT_METADATA.write_text(
        json.dumps(
            metadata,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    manifest_lines = []

    for path in (
        OUTPUT_ALL,
        OUTPUT_TRAIN,
        OUTPUT_VALIDATION,
        OUTPUT_METADATA,
    ):
        manifest_lines.append(
            f"{sha256_file(path)}  {path.name}"
        )

    OUTPUT_MANIFEST.write_text(
        "\n".join(manifest_lines)
        + "\n",
        encoding="utf-8",
    )

    print("=" * 80)
    print(
        "BODY OR SUBJECT MISMATCH ROW BUILD "
        "v0.1.0"
    )
    print("=" * 80)
    print()
    print("Pairs:", len(pairs))
    print("Rows:", len(rows))
    print("Train rows:", len(train_rows))
    print(
        "Validation rows:",
        len(validation_rows),
    )
    print(
        "Labels:",
        {
            0: sum(
                row["general_risk_label"] == 0
                for row in rows
            ),
            1: sum(
                row["general_risk_label"] == 1
                for row in rows
            ),
        },
    )
    print(
        "Maximum token count:",
        metadata[
            "token_counts"
        ]["maximum"],
    )
    print("Truncation:", "no")
    print()
    print("All rows:", OUTPUT_ALL)
    print("Train rows:", OUTPUT_TRAIN)
    print(
        "Validation rows:",
        OUTPUT_VALIDATION,
    )
    print("Metadata:", OUTPUT_METADATA)
    print("Manifest:", OUTPUT_MANIFEST)
    print()
    print("Body or subject row build: PASSED")


if __name__ == "__main__":
    main()

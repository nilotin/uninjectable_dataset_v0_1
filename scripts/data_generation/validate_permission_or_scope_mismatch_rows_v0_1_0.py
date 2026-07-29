from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


INPUT_PATH = Path(
    "data/planning/"
    "agentdojo_turkish_argument_mismatch_batch_v0.1.0/"
    "permission_or_scope_mismatch_rows_v0.1.0/"
    "permission_or_scope_mismatch_rows_v0.1.0.jsonl"
)

EXPECTED_ROWS = 8
EXPECTED_PAIRS = 4

SECTION_ORDER = [
    "[USER_AUTHORIZATION]",
    "[ATTEMPTED_ACTION]",
    "[RETRIEVED_CONTENT]",
    "[SOURCE]",
    "[AGENT_FACTS]",
]

FORBIDDEN_TEXT_TERMS = [
    "general_risk_label=",
    "label_source=",
    "review_status=",
    "risk_score=",
    "policy_decision=",
    "expected_decision=",
    "category=",
    "changed_argument_paths=",
]


def load_jsonl(
    path: Path,
) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]


def extract_line(
    text: str,
    prefix: str,
) -> str:
    for line in text.splitlines():
        if line.startswith(prefix):
            return line[len(prefix):]

    raise ValueError(
        f"Missing serialized field: {prefix}"
    )


def main() -> None:
    if not INPUT_PATH.exists():
        raise FileNotFoundError(INPUT_PATH)

    rows = load_jsonl(INPUT_PATH)

    if len(rows) != EXPECTED_ROWS:
        raise ValueError(
            f"Expected {EXPECTED_ROWS} rows, "
            f"found {len(rows)}"
        )

    row_ids = [
        str(row["row_id"])
        for row in rows
    ]

    if len(row_ids) != len(set(row_ids)):
        raise ValueError(
            "Duplicate row_id detected"
        )

    text_hashes = [
        str(row["text_sha256"])
        for row in rows
    ]

    if len(text_hashes) != len(
        set(text_hashes)
    ):
        raise ValueError(
            "Duplicate serialized text detected"
        )

    grouped: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)

    for row in rows:
        grouped[
            str(row["pair_id"])
        ].append(row)

        text = str(row["text"])

        positions = [
            text.index(section)
            for section in SECTION_ORDER
        ]

        if positions != sorted(positions):
            raise ValueError(
                f"{row['row_id']}: "
                "section order invalid"
            )

        for forbidden in FORBIDDEN_TEXT_TERMS:
            if forbidden in text:
                raise ValueError(
                    f"{row['row_id']}: "
                    f"forbidden text leak: "
                    f"{forbidden}"
                )

        if (
            row["tokenization"][
                "truncated"
            ]
            is not False
        ):
            raise ValueError(
                f"{row['row_id']}: "
                "truncation detected"
            )

        if (
            int(
                row["tokenization"][
                    "token_count"
                ]
            )
            > 512
        ):
            raise ValueError(
                f"{row['row_id']}: "
                "token limit exceeded"
            )

        if row.get("category") != "permission_or_scope_mismatch":
            raise ValueError(
                f"{row['row_id']}: unexpected category"
            )

        allowed_changed_paths = {
            ("permission",),
            ("recipients",),
            ("participants",),
        }

        observed_changed_paths = tuple(
            row.get(
                "changed_argument_paths",
                [],
            )
        )

        if observed_changed_paths not in allowed_changed_paths:
            raise ValueError(
                f"{row['row_id']}: invalid "
                "permission/scope changed paths: "
                f"{observed_changed_paths}"
            )

        expected_label = (
            0
            if row["variant"] == "safe"
            else 1
        )

        if (
            int(row["general_risk_label"])
            != expected_label
        ):
            raise ValueError(
                f"{row['row_id']}: "
                "variant-label mismatch"
            )

    if len(grouped) != EXPECTED_PAIRS:
        raise ValueError(
            f"Expected {EXPECTED_PAIRS} pairs, "
            f"found {len(grouped)}"
        )

    split_pair_counts = Counter()

    for pair_id, members in grouped.items():
        if len(members) != 2:
            raise ValueError(
                f"{pair_id}: expected 2 rows"
            )

        by_variant = {
            row["variant"]: row
            for row in members
        }

        if set(by_variant) != {
            "safe",
            "risky",
        }:
            raise ValueError(
                f"{pair_id}: missing variant"
            )

        safe = by_variant["safe"]
        risky = by_variant["risky"]

        if (
            safe["session_group_id"]
            != risky["session_group_id"]
        ):
            raise ValueError(
                f"{pair_id}: session mismatch"
            )

        if safe["split"] != risky["split"]:
            raise ValueError(
                f"{pair_id}: split mismatch"
            )

        if (
            safe["suite"]
            != risky["suite"]
        ):
            raise ValueError(
                f"{pair_id}: suite mismatch"
            )

        safe_tool = extract_line(
            safe["text"],
            "tool_name=",
        )

        risky_tool = extract_line(
            risky["text"],
            "tool_name=",
        )

        authorized_tool = extract_line(
            safe["text"],
            "authorized_tool=",
        )

        if not (
            safe_tool
            == risky_tool
            == authorized_tool
        ):
            raise ValueError(
                f"{pair_id}: tool invariant failed"
            )

        safe_authorized_args = extract_line(
            safe["text"],
            "authorized_args=",
        )

        safe_attempted_args = extract_line(
            safe["text"],
            "args=",
        )

        risky_attempted_args = extract_line(
            risky["text"],
            "args=",
        )

        if (
            safe_authorized_args
            != safe_attempted_args
        ):
            raise ValueError(
                f"{pair_id}: safe args mismatch"
            )

        if (
            risky_attempted_args
            == safe_authorized_args
        ):
            raise ValueError(
                f"{pair_id}: risky args "
                "still authorized"
            )

        safe_non_action = safe["text"].split(
            "[ATTEMPTED_ACTION]"
        )[0] + safe["text"].split(
            "[RETRIEVED_CONTENT]"
        )[1]

        risky_non_action = risky["text"].split(
            "[ATTEMPTED_ACTION]"
        )[0] + risky["text"].split(
            "[RETRIEVED_CONTENT]"
        )[1]

        if safe_non_action != risky_non_action:
            raise ValueError(
                f"{pair_id}: non-action "
                "context changed"
            )

        split_pair_counts[
            str(safe["split"])
        ] += 1

    if split_pair_counts != {
        "train": 3,
        "validation": 1,
    }:
        raise ValueError(
            "Unexpected pair split counts: "
            f"{dict(split_pair_counts)}"
        )

    print("=" * 80)
    print(
        "PERMISSION OR SCOPE MISMATCH ROW "
        "VALIDATION v0.1.0"
    )
    print("=" * 80)
    print()
    print("Rows:", len(rows))
    print("Pairs:", len(grouped))
    print(
        "Labels:",
        dict(
            sorted(
                Counter(
                    int(
                        row[
                            "general_risk_label"
                        ]
                    )
                    for row in rows
                ).items()
            )
        ),
    )
    print(
        "Pair split counts:",
        dict(
            sorted(
                split_pair_counts.items()
            )
        ),
    )
    print("Duplicate row IDs: 0")
    print("Duplicate texts: 0")
    print("Tool invariant failures: 0")
    print("Permission/scope isolation failures: 0")
    print("Context drift: 0")
    print("Forbidden metadata leaks: 0")
    print("Truncation: 0")
    print()
    print("Permission or scope rows: PASSED")


if __name__ == "__main__":
    main()

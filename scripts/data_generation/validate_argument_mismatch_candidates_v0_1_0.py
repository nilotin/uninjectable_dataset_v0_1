from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path(
    "data/planning/"
    "agentdojo_turkish_argument_mismatch_batch_v0.1.0/"
    "recipient_mismatch_candidates_v0.1.0.jsonl"
)

ALLOWED_SUITES = {
    "banking",
    "slack",
    "travel",
    "workspace",
}

ALLOWED_SPLITS = {
    "train",
    "validation",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT
    )

    parser.add_argument(
        "--expected-pairs",
        type=int,
        default=4
    )

    parser.add_argument(
        "--category",
        choices=[
            "recipient_mismatch",
            "amount_mismatch",
            "object_or_record_id_mismatch",
            "date_or_time_mismatch",
            "body_or_subject_mismatch",
            "permission_or_scope_mismatch",
        ],
        default="recipient_mismatch",
    )

    return parser.parse_args()


def load_jsonl(
    path: Path
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1
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


def differing_paths(
    left: Any,
    right: Any,
    prefix: str = ""
) -> list[str]:
    if isinstance(left, dict) and isinstance(right, dict):
        paths: list[str] = []

        all_keys = sorted(
            set(left) | set(right)
        )

        for key in all_keys:
            path = (
                f"{prefix}.{key}"
                if prefix
                else str(key)
            )

            if key not in left or key not in right:
                paths.append(path)
                continue

            paths.extend(
                differing_paths(
                    left[key],
                    right[key],
                    path
                )
            )

        return paths

    if isinstance(left, list) and isinstance(right, list):
        paths: list[str] = []

        maximum = max(
            len(left),
            len(right)
        )

        for index in range(maximum):
            path = f"{prefix}[{index}]"

            if index >= len(left) or index >= len(right):
                paths.append(path)
                continue

            paths.extend(
                differing_paths(
                    left[index],
                    right[index],
                    path
                )
            )

        return paths

    if left != right:
        return [prefix]

    return []


def main() -> None:
    args = parse_args()

    if not args.input.exists():
        raise FileNotFoundError(args.input)

    pairs = load_jsonl(args.input)

    if len(pairs) != args.expected_pairs:
        raise ValueError(
            f"Expected {args.expected_pairs} pairs, "
            f"found {len(pairs)}"
        )

    pair_ids = [
        str(pair["pair_id"])
        for pair in pairs
    ]

    if len(pair_ids) != len(set(pair_ids)):
        raise ValueError("Duplicate pair_id detected")

    source_ids = [
        str(pair["source_scenario_id"])
        for pair in pairs
    ]

    if len(source_ids) != len(set(source_ids)):
        raise ValueError(
            "Duplicate source_scenario_id detected"
        )

    split_counts = Counter()
    suite_counts = Counter()

    for pair in pairs:
        pair_id = str(pair["pair_id"])

        required_fields = {
            "pair_id",
            "session_group_id",
            "source_scenario_id",
            "category",
            "suite",
            "split",
            "language",
            "authorized_tool",
            "authorized_args",
            "safe_attempted_tool",
            "safe_attempted_args",
            "risky_attempted_tool",
            "risky_attempted_args",
            "changed_argument_paths",
            "retrieved_content",
            "source",
            "agent_facts",
            "review",
        }

        missing = required_fields - set(pair)

        if missing:
            raise ValueError(
                f"{pair_id}: missing fields: "
                f"{sorted(missing)}"
            )

        if pair["category"] != args.category:
            raise ValueError(
                f"{pair_id}: unexpected category; "
                f"expected={args.category}, "
                f"found={pair['category']}"
            )

        if pair["suite"] not in ALLOWED_SUITES:
            raise ValueError(
                f"{pair_id}: invalid suite"
            )

        if pair["split"] not in ALLOWED_SPLITS:
            raise ValueError(
                f"{pair_id}: invalid split"
            )

        if pair["language"] != "tr":
            raise ValueError(
                f"{pair_id}: expected language=tr"
            )

        authorized_tool = pair["authorized_tool"]
        safe_tool = pair["safe_attempted_tool"]
        risky_tool = pair["risky_attempted_tool"]

        if not (
            authorized_tool
            == safe_tool
            == risky_tool
        ):
            raise ValueError(
                f"{pair_id}: tool invariant failed"
            )

        authorized_args = pair["authorized_args"]
        safe_args = pair["safe_attempted_args"]
        risky_args = pair["risky_attempted_args"]

        if safe_args != authorized_args:
            raise ValueError(
                f"{pair_id}: safe args do not "
                "match authorized args"
            )

        if risky_args == authorized_args:
            raise ValueError(
                f"{pair_id}: risky args still "
                "match authorized args"
            )

        observed_paths_raw = differing_paths(
            safe_args,
            risky_args
        )

        if pair.get("category") == "permission_or_scope_mismatch":
            observed_paths = sorted(
                {
                    changed_path.split("[", 1)[0]
                    for changed_path in observed_paths_raw
                }
            )
        else:
            observed_paths = observed_paths_raw

        declared_paths = list(
            pair["changed_argument_paths"]
        )

        if sorted(observed_paths) != sorted(declared_paths):
            raise ValueError(
                f"{pair_id}: changed paths mismatch; "
                f"declared={declared_paths}, "
                f"observed={observed_paths}, "
                f"observed_raw={observed_paths_raw}"
            )

        allowed_roots_by_category = {
            "recipient_mismatch": {
                "recipient",
                "recipients",
                "participants",
                "destination",
                "channel",
            },
            "amount_mismatch": {
                "amount",
            },
            "object_or_record_id_mismatch": {
                "id",
                "file_id",
                "email_id",
                "event_id",
            },
            "date_or_time_mismatch": {
                "date",
                "day",
                "start_time",
                "end_time",
                "new_start_time",
                "new_end_time",
                "start_day",
                "end_day",
            },
            "body_or_subject_mismatch": {
                "body",
                "subject",
                "content",
            },
            "permission_or_scope_mismatch": {
                "permission",
                "participants",
                "recipients",
            },
        }

        allowed_roots = allowed_roots_by_category[
            args.category
        ]

        for path in observed_paths:
            root = (
                path.split(".", 1)[0]
                .split("[", 1)[0]
            )

            if root not in allowed_roots:
                raise ValueError(
                    f"{pair_id}: unexpected "
                    f"argument changed for "
                    f"{args.category}: {path}"
                )

        source = pair["source"]

        if source.get("trust_level") != "untrusted":
            raise ValueError(
                f"{pair_id}: source must be untrusted"
            )

        agent_facts = pair["agent_facts"]

        if (
            agent_facts.get(
                "attempted_tool_allowed"
            )
            is not True
        ):
            raise ValueError(
                f"{pair_id}: attempted_tool_allowed "
                "must be true"
            )

        if not str(
            pair["retrieved_content"]
        ).strip():
            raise ValueError(
                f"{pair_id}: empty retrieved content"
            )

        expected_session = (
            f"{pair_id}::session"
        )

        if pair["session_group_id"] != expected_session:
            raise ValueError(
                f"{pair_id}: invalid session_group_id"
            )

        split_counts[str(pair["split"])] += 1
        suite_counts[str(pair["suite"])] += 1

    if split_counts != {
        "train": 3,
        "validation": 1,
    }:
        raise ValueError(
            f"Unexpected split counts: "
            f"{dict(split_counts)}"
        )

    print("=" * 80)
    print(
        f"{args.category.upper()} CANDIDATE "
        "VALIDATION v0.1.0"
    )
    print("=" * 80)
    print()
    print("Pairs:", len(pairs))
    print(
        "Split counts:",
        dict(sorted(split_counts.items()))
    )
    print(
        "Suite counts:",
        dict(sorted(suite_counts.items()))
    )
    print("Tool invariants: PASSED")
    print("Argument isolation: PASSED")
    print("Source trust validation: PASSED")
    print()
    print(
        f"{args.category} candidates: PASSED"
    )


if __name__ == "__main__":
    main()

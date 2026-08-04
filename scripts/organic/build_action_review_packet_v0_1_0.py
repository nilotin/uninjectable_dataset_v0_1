from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


REVIEW_FIELDS = [
    "review_task_id",
    "farm_run_id",
    "run_id",
    "scenario_id",
    "event_id",
    "scenario_family",
    "customer_message",
    "authorization_source",
    "authorized_tool",
    "authorized_args",
    "deny_write_actions",
    "attempted_tool",
    "attempted_action_type",
    "policy_decision",
    "policy_risk_score",
    "prompt_injection_indicators",
    "untrusted_read_tools",
    "preceding_tool_trace",
    "final_answer",
    "human_label",
    "human_category",
    "human_reason",
    "review_status",
    "reviewer",
    "reviewed_at",
]


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: invalid JSON") from exc


def json_cell(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Create a human-review packet for organic "
            "agent action attempts."
        )
    )
    parser.add_argument(
        "--runs",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--review-queue",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
    )
    args = parser.parse_args()

    runs = load_json(args.runs)
    review_queue = load_json(args.review_queue)

    results = list(runs["results"])
    action_tasks = list(
        review_queue["action_review_tasks"]
    )

    results_by_run_id = {
        str(result["run_id"]): result
        for result in results
    }

    rows: list[dict[str, Any]] = []

    for task in action_tasks:
        run_id = str(task["run_id"])
        event_id = str(task["event_id"])

        result = results_by_run_id.get(run_id)

        if result is None:
            raise ValueError(
                f"{event_id}: run {run_id} not found."
            )

        response = result["response"]

        attempts_by_event_id = {
            str(attempt["action_attempt_id"]): attempt
            for attempt in response.get(
                "action_attempts",
                [],
            )
        }

        attempt = attempts_by_event_id.get(event_id)

        if attempt is None:
            raise ValueError(
                f"{event_id}: action attempt not found."
            )

        tool_trace = list(
            response.get("tool_trace", [])
        )

        preceding_trace = [
            event
            for event in tool_trace
            if int(event.get("sequence", 0))
            < next(
                int(item.get("sequence", 0))
                for item in tool_trace
                if str(item.get("event_id")) == event_id
            )
        ]

        untrusted_reads = [
            str(event["tool_name"])
            for event in preceding_trace
            if event.get("kind") == "read"
            and event.get("trust_level") == "untrusted"
        ]

        injection_indicators = sorted(
            {
                str(indicator)
                for event in preceding_trace
                for indicator in event.get(
                    "prompt_injection_indicators",
                    [],
                )
            }
        )

        authorization = result.get(
            "user_authorization",
            {},
        )

        dataset_metadata = result.get(
            "dataset_metadata",
            {},
        )

        row = {
            "review_task_id": str(
                task["review_task_id"]
            ),
            "farm_run_id": str(
                runs["farm_run_id"]
            ),
            "run_id": run_id,
            "scenario_id": str(
                task["scenario_id"]
            ),
            "event_id": event_id,
            "scenario_family": str(
                dataset_metadata.get(
                    "scenario_family",
                    "",
                )
            ),
            "customer_message": str(
                result.get(
                    "customer_message",
                    "",
                )
            ),
            "authorization_source": str(
                authorization.get(
                    "authorization_source",
                    "",
                )
            ),
            "authorized_tool": str(
                authorization.get(
                    "authorized_tool",
                    "",
                )
            ),
            "authorized_args": json_cell(
                authorization.get(
                    "authorized_args",
                    {},
                )
            ),
            "deny_write_actions": authorization.get(
                "deny_write_actions",
                "",
            ),
            "attempted_tool": str(
                attempt["tool_name"]
            ),
            "attempted_action_type": str(
                attempt["action_type"]
            ),
            "policy_decision": str(
                task["policy_decision"]
            ),
            "policy_risk_score": int(
                task["policy_risk_score"]
            ),
            "prompt_injection_indicators": json_cell(
                injection_indicators
            ),
            "untrusted_read_tools": json_cell(
                untrusted_reads
            ),
            "preceding_tool_trace": json_cell(
                preceding_trace
            ),
            "final_answer": str(
                response.get(
                    "final_answer",
                    "",
                )
            ),
            "human_label": "",
            "human_category": "",
            "human_reason": "",
            "review_status": "pending_human_review",
            "reviewer": "",
            "reviewed_at": "",
        }

        rows.append(row)

    rows.sort(
        key=lambda row: (
            row["scenario_id"],
            row["event_id"],
        )
    )

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with args.output.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=REVIEW_FIELDS,
        )
        writer.writeheader()
        writer.writerows(rows)

    print("=" * 80)
    print("ORGANIC ACTION REVIEW PACKET")
    print("=" * 80)
    print("Farm run ID:", runs["farm_run_id"])
    print("Rows:", len(rows))
    print("Output:", args.output)


if __name__ == "__main__":
    main()

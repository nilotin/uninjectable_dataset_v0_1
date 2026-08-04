from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: invalid JSON") from exc


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def normalize_manifest_path(raw_path: str) -> Path:
    return Path(raw_path.replace("\\", "/"))


def require_equal(
    actual: Any,
    expected: Any,
    field_name: str,
) -> None:
    if actual != expected:
        raise ValueError(
            f"{field_name}: expected {expected!r}, "
            f"found {actual!r}"
        )


def require_unique(
    values: list[str],
    field_name: str,
) -> None:
    if len(values) != len(set(values)):
        raise ValueError(
            f"Duplicate values detected for {field_name}."
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Validate one organic farm manifest, runs artifact, "
            "and review queue."
        )
    )
    parser.add_argument(
        "manifest",
        type=Path,
        help="Path to the organic farm manifest JSON.",
    )
    args = parser.parse_args()

    manifest_path = args.manifest.resolve()

    if not manifest_path.exists():
        raise FileNotFoundError(manifest_path)

    manifest = load_json(manifest_path)

    runs_name = normalize_manifest_path(
        str(manifest["runs_artifact"])
    ).name
    review_queue_name = normalize_manifest_path(
        str(manifest["review_queue_artifact"])
    ).name

    runs_path = manifest_path.parent / runs_name
    review_queue_path = manifest_path.parent / review_queue_name

    for path in (runs_path, review_queue_path):
        if not path.exists():
            raise FileNotFoundError(path)

    runs = load_json(runs_path)
    review_queue = load_json(review_queue_path)

    actual_runs_sha256 = sha256_file(runs_path)
    actual_review_queue_sha256 = sha256_file(
        review_queue_path
    )

    require_equal(
        actual_runs_sha256,
        manifest["runs_sha256"],
        "runs_sha256",
    )
    require_equal(
        actual_review_queue_sha256,
        manifest["review_queue_sha256"],
        "review_queue_sha256",
    )

    farm_run_id = str(manifest["farm_run_id"])

    require_equal(
        str(runs["farm_run_id"]),
        farm_run_id,
        "runs.farm_run_id",
    )
    require_equal(
        str(review_queue["farm_run_id"]),
        farm_run_id,
        "review_queue.farm_run_id",
    )

    require_equal(
        str(runs["profile"]),
        str(manifest["profile"]),
        "profile",
    )

    results = list(runs["results"])
    run_tasks = list(review_queue["run_tasks"])
    action_review_tasks = list(
        review_queue["action_review_tasks"]
    )

    require_equal(
        len(results),
        int(manifest["completed_run_count"]),
        "completed_run_count",
    )
    require_equal(
        int(runs["completed_count"]),
        int(manifest["completed_run_count"]),
        "runs.completed_count",
    )
    require_equal(
        int(runs["failed_count"]),
        int(manifest["failed_run_count"]),
        "failed_run_count",
    )
    require_equal(
        len(run_tasks),
        int(manifest["run_review_task_count"]),
        "run_review_task_count",
    )
    require_equal(
        len(action_review_tasks),
        int(manifest["action_review_task_count"]),
        "action_review_task_count",
    )
    require_equal(
        int(review_queue["run_task_count"]),
        len(run_tasks),
        "review_queue.run_task_count",
    )
    require_equal(
        int(review_queue["action_review_task_count"]),
        len(action_review_tasks),
        "review_queue.action_review_task_count",
    )

    run_ids = [
        str(result["run_id"])
        for result in results
    ]
    scenario_ids = [
        str(result["scenario_id"])
        for result in results
    ]

    require_unique(run_ids, "run_id")
    require_unique(scenario_ids, "scenario_id")

    result_by_run_id = {
        str(result["run_id"]): result
        for result in results
    }

    review_run_ids = [
        str(task["run_id"])
        for task in run_tasks
    ]

    require_unique(
        review_run_ids,
        "run review task run_id",
    )

    if set(review_run_ids) != set(run_ids):
        raise ValueError(
            "Run review tasks do not exactly match completed runs."
        )

    action_attempts_by_event_id: dict[
        str,
        dict[str, Any],
    ] = {}

    expected_action_count = 0

    for result in results:
        response = result["response"]
        action_attempts = list(
            response.get("action_attempts", [])
        )

        require_equal(
            int(result["action_attempt_count"]),
            len(action_attempts),
            (
                f'{result["run_id"]}.'
                "action_attempt_count"
            ),
        )

        expected_action_count += len(action_attempts)

        for attempt in action_attempts:
            event_id = str(
                attempt["action_attempt_id"]
            )

            if event_id in action_attempts_by_event_id:
                raise ValueError(
                    f"Duplicate action event_id: {event_id}"
                )

            action_attempts_by_event_id[event_id] = {
                "run_id": str(result["run_id"]),
                "scenario_id": str(
                    result["scenario_id"]
                ),
                "tool_name": str(
                    attempt["tool_name"]
                ),
            }

    require_equal(
        expected_action_count,
        len(action_review_tasks),
        "derived action review task count",
    )

    review_event_ids = [
        str(task["event_id"])
        for task in action_review_tasks
    ]

    require_unique(
        review_event_ids,
        "action review event_id",
    )

    if set(review_event_ids) != set(
        action_attempts_by_event_id
    ):
        raise ValueError(
            "Action review tasks do not exactly match "
            "recorded action attempts."
        )

    for task in action_review_tasks:
        event_id = str(task["event_id"])
        attempt = action_attempts_by_event_id[event_id]

        require_equal(
            str(task["run_id"]),
            attempt["run_id"],
            f"{event_id}.run_id",
        )
        require_equal(
            str(task["scenario_id"]),
            attempt["scenario_id"],
            f"{event_id}.scenario_id",
        )
        require_equal(
            str(task["tool_name"]),
            attempt["tool_name"],
            f"{event_id}.tool_name",
        )

        if task["status"] != "pending_human_review":
            raise ValueError(
                f"{event_id}: unexpected review status "
                f'{task["status"]!r}'
            )

    for task in run_tasks:
        run_id = str(task["run_id"])
        result = result_by_run_id[run_id]

        require_equal(
            str(task["scenario_id"]),
            str(result["scenario_id"]),
            f"{run_id}.scenario_id",
        )
        require_equal(
            int(task["action_attempt_count"]),
            int(result["action_attempt_count"]),
            f"{run_id}.action_attempt_count",
        )

        if task["status"] != "pending_human_review":
            raise ValueError(
                f"{run_id}: unexpected review status "
                f'{task["status"]!r}'
            )

    print("=" * 80)
    print("ORGANIC FARM ARTIFACT VALIDATION")
    print("=" * 80)
    print("Manifest:", manifest_path)
    print("Farm run ID:", farm_run_id)
    print("Artifact status:", manifest["artifact_status"])
    print("Profile:", manifest["profile"])
    print("Seed:", manifest["seed"])
    print("Completed runs:", len(results))
    print("Run review tasks:", len(run_tasks))
    print(
        "Action review tasks:",
        len(action_review_tasks),
    )
    print("Runs SHA-256:", actual_runs_sha256)
    print(
        "Review queue SHA-256:",
        actual_review_queue_sha256,
    )
    print()
    print("Validation result: PASS")


if __name__ == "__main__":
    main()

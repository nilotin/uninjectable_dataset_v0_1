from __future__ import annotations

import ast
import csv
import json
import re
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SOURCE_ROOT = Path(
    "data/raw/agentdojo_source"
)

DEFAULT_SUITES_ROOT = (
    SOURCE_ROOT
    / "src"
    / "agentdojo"
    / "default_suites"
)

OUTPUT_DIR = Path(
    "data/interim"
)

JSON_OUTPUT_PATH = (
    OUTPUT_DIR
    / "agentdojo_effective_task_inventory_v1.2.2.json"
)

CSV_OUTPUT_PATH = (
    OUTPUT_DIR
    / "agentdojo_effective_task_inventory_v1.2.2.csv"
)

REPORT_OUTPUT_PATH = (
    OUTPUT_DIR
    / "agentdojo_effective_task_inventory_v1.2.2_report.json"
)

TARGET_VERSION = (1, 2, 2)

SUITES = (
    "banking",
    "slack",
    "travel",
    "workspace",
)


def version_to_string(
    version: tuple[int, int, int],
) -> str:
    return "v" + ".".join(
        str(part)
        for part in version
    )


def parse_version_directory(
    directory_name: str,
) -> tuple[int, int, int] | None:

    if not directory_name.startswith("v"):
        return None

    raw_parts = directory_name[1:].split("_")

    if not all(
        part.isdigit()
        for part in raw_parts
    ):
        return None

    parts = [
        int(part)
        for part in raw_parts
    ]

    while len(parts) < 3:
        parts.append(0)

    if len(parts) != 3:
        return None

    return tuple(parts)


def get_git_commit() -> str:

    result = subprocess.run(
        [
            "git",
            "-C",
            str(SOURCE_ROOT),
            "rev-parse",
            "HEAD",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    return result.stdout.strip()


def expression_source(
    node: ast.AST | None,
) -> str | None:

    if node is None:
        return None

    try:
        return ast.unparse(node)
    except Exception:
        return None


def literal_or_expression(
    node: ast.AST | None,
) -> Any:

    if node is None:
        return None

    try:
        return ast.literal_eval(node)
    except Exception:
        return expression_source(node)


def decorator_name(
    decorator: ast.expr,
) -> str:

    target = (
        decorator.func
        if isinstance(decorator, ast.Call)
        else decorator
    )

    if isinstance(target, ast.Attribute):
        return target.attr

    if isinstance(target, ast.Name):
        return target.id

    return expression_source(target) or ""


def version_from_decorator(
    decorator: ast.expr,
) -> tuple[int, int, int] | None:

    if not isinstance(decorator, ast.Call):
        return None

    if not decorator.args:
        return None

    first_argument = decorator.args[0]

    try:
        value = ast.literal_eval(
            first_argument
        )
    except Exception:
        return None

    if (
        isinstance(value, tuple)
        and len(value) == 3
        and all(
            isinstance(part, int)
            for part in value
        )
    ):
        return value

    return None


def task_version(
    class_node: ast.ClassDef,
    source_directory_version: tuple[int, int, int],
) -> tuple[int, int, int]:

    for decorator in class_node.decorator_list:

        name = decorator_name(
            decorator
        )

        if name in {
            "update_user_task",
            "update_injection_task",
            "register_new_injection_task",
        }:
            explicit_version = version_from_decorator(
                decorator
            )

            if explicit_version is not None:
                return explicit_version

    return source_directory_version


def task_kind_and_number(
    class_name: str,
) -> tuple[str, int] | None:

    user_match = re.fullmatch(
        r"UserTask(\d+)",
        class_name,
    )

    if user_match:
        return (
            "user_task",
            int(user_match.group(1)),
        )

    injection_match = re.fullmatch(
        r"InjectionTask(\d+)",
        class_name,
    )

    if injection_match:
        return (
            "injection_task",
            int(injection_match.group(1)),
        )

    return None


def class_assignments(
    class_node: ast.ClassDef,
) -> dict[str, ast.AST]:

    assignments: dict[str, ast.AST] = {}

    for statement in class_node.body:

        if isinstance(statement, ast.Assign):

            for target in statement.targets:

                if isinstance(target, ast.Name):
                    assignments[target.id] = (
                        statement.value
                    )

        elif isinstance(
            statement,
            ast.AnnAssign,
        ):

            if (
                isinstance(statement.target, ast.Name)
                and statement.value is not None
            ):
                assignments[
                    statement.target.id
                ] = statement.value

    return assignments


def ground_truth_calls(
    class_node: ast.ClassDef,
) -> list[dict[str, Any]]:

    method = None

    for statement in class_node.body:

        if (
            isinstance(
                statement,
                ast.FunctionDef,
            )
            and statement.name == "ground_truth"
        ):
            method = statement
            break

    if method is None:
        return []

    calls = []

    for node in ast.walk(method):

        if not isinstance(node, ast.Call):
            continue

        call_name = ""

        if isinstance(node.func, ast.Name):
            call_name = node.func.id

        elif isinstance(node.func, ast.Attribute):
            call_name = node.func.attr

        if call_name != "FunctionCall":
            continue

        keywords = {
            keyword.arg: keyword.value
            for keyword in node.keywords
            if keyword.arg is not None
        }

        function_value = literal_or_expression(
            keywords.get("function")
        )

        calls.append(
            {
                "function": function_value,
                "args": literal_or_expression(
                    keywords.get("args")
                ),
                "args_expression": expression_source(
                    keywords.get("args")
                ),
                "placeholder_args": literal_or_expression(
                    keywords.get(
                        "placeholder_args"
                    )
                ),
                "placeholder_args_expression": (
                    expression_source(
                        keywords.get(
                            "placeholder_args"
                        )
                    )
                ),
            }
        )

    return calls


def parse_task_file(
    path: Path,
    suite: str,
    directory_version: tuple[int, int, int],
) -> list[dict[str, Any]]:

    source_text = path.read_text(
        encoding="utf-8"
    )

    tree = ast.parse(
        source_text,
        filename=str(path),
    )

    records = []

    for node in tree.body:

        if not isinstance(node, ast.ClassDef):
            continue

        task_identity = task_kind_and_number(
            node.name
        )

        if task_identity is None:
            continue

        kind, task_number = task_identity

        assignments = class_assignments(
            node
        )

        effective_from_version = task_version(
            node,
            directory_version,
        )

        prompt_field = (
            "PROMPT"
            if kind == "user_task"
            else "GOAL"
        )

        prompt_or_goal = literal_or_expression(
            assignments.get(
                prompt_field
            )
        )

        comment = literal_or_expression(
            assignments.get("COMMENT")
        )

        difficulty = expression_source(
            assignments.get("DIFFICULTY")
        )

        calls = ground_truth_calls(
            node
        )

        records.append(
            {
                "suite": suite,
                "task_kind": kind,
                "task_id": (
                    f"{kind}_{task_number}"
                ),
                "task_number": task_number,
                "class_name": node.name,
                "effective_from_version": list(
                    effective_from_version
                ),
                "effective_from_version_string": (
                    version_to_string(
                        effective_from_version
                    )
                ),
                "source_directory_version": list(
                    directory_version
                ),
                "source_directory_version_string": (
                    version_to_string(
                        directory_version
                    )
                ),
                "prompt_or_goal": prompt_or_goal,
                "prompt_field": prompt_field,
                "comment": comment,
                "difficulty_expression": difficulty,
                "ground_truth_calls": calls,
                "ground_truth_function_names": [
                    call["function"]
                    for call in calls
                ],
                "ground_truth_call_count": len(
                    calls
                ),
                "source_file": str(
                    path.relative_to(
                        SOURCE_ROOT
                    )
                ),
            }
        )

    return records


def collect_all_revisions() -> list[dict[str, Any]]:

    records: list[dict[str, Any]] = []

    for version_directory in sorted(
        DEFAULT_SUITES_ROOT.glob("v*")
    ):

        if not version_directory.is_dir():
            continue

        directory_version = (
            parse_version_directory(
                version_directory.name
            )
        )

        if directory_version is None:
            continue

        for suite in SUITES:

            suite_directory = (
                version_directory
                / suite
            )

            if not suite_directory.exists():
                continue

            for filename in (
                "user_tasks.py",
                "injection_tasks.py",
            ):

                path = (
                    suite_directory
                    / filename
                )

                if not path.exists():
                    continue

                records.extend(
                    parse_task_file(
                        path=path,
                        suite=suite,
                        directory_version=(
                            directory_version
                        ),
                    )
                )

    return records


def resolve_effective_snapshot(
    revisions: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    grouped: dict[
        tuple[str, str, str],
        list[dict[str, Any]],
    ] = defaultdict(list)

    for record in revisions:

        version = tuple(
            record[
                "effective_from_version"
            ]
        )

        if version > TARGET_VERSION:
            continue

        key = (
            record["suite"],
            record["task_kind"],
            record["task_id"],
        )

        grouped[key].append(
            record
        )

    effective_records = []

    for key, candidates in grouped.items():

        candidates = sorted(
            candidates,
            key=lambda record: tuple(
                record[
                    "effective_from_version"
                ]
            ),
        )

        selected = dict(
            candidates[-1]
        )

        selected[
            "revision_count_up_to_target"
        ] = len(candidates)

        selected[
            "available_revision_versions_up_to_target"
        ] = [
            candidate[
                "effective_from_version_string"
            ]
            for candidate in candidates
        ]

        effective_records.append(
            selected
        )

    effective_records.sort(
        key=lambda record: (
            record["suite"],
            record["task_kind"],
            record["task_number"],
        )
    )

    return effective_records


def write_csv(
    path: Path,
    records: list[dict[str, Any]],
) -> None:

    fieldnames = [
        "suite",
        "task_kind",
        "task_id",
        "class_name",
        "effective_from_version_string",
        "revision_count_up_to_target",
        "prompt_field",
        "prompt_or_goal",
        "comment",
        "difficulty_expression",
        "ground_truth_call_count",
        "ground_truth_function_names",
        "source_file",
    ]

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        for record in records:

            row = {
                field: record.get(
                    field
                )
                for field in fieldnames
            }

            row[
                "ground_truth_function_names"
            ] = json.dumps(
                record[
                    "ground_truth_function_names"
                ],
                ensure_ascii=False,
            )

            writer.writerow(
                row
            )


def main() -> None:

    commit = get_git_commit()

    revisions = collect_all_revisions()

    effective_records = (
        resolve_effective_snapshot(
            revisions
        )
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    inventory = {
        "source": {
            "dataset": "agentdojo",
            "repository_commit": commit,
        },
        "target_benchmark_version": (
            version_to_string(
                TARGET_VERSION
            )
        ),
        "all_parsed_task_revisions": (
            len(revisions)
        ),
        "effective_task_count": (
            len(effective_records)
        ),
        "tasks": effective_records,
    }

    JSON_OUTPUT_PATH.write_text(
        json.dumps(
            inventory,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    write_csv(
        CSV_OUTPUT_PATH,
        effective_records,
    )

    suite_kind_counts = Counter(
        (
            record["suite"],
            record["task_kind"],
        )
        for record in effective_records
    )

    version_counts = Counter(
        record[
            "effective_from_version_string"
        ]
        for record in effective_records
    )

    ground_truth_function_counts = Counter(
        function_name
        for record in effective_records
        for function_name in (
            record[
                "ground_truth_function_names"
            ]
        )
        if function_name
    )

    report = {
        "dataset": "agentdojo",
        "repository_commit": commit,
        "target_benchmark_version": (
            version_to_string(
                TARGET_VERSION
            )
        ),
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "parsed_revision_count": len(
            revisions
        ),
        "effective_task_count": len(
            effective_records
        ),
        "suite_task_counts": {
            f"{suite}:{kind}": count
            for (suite, kind), count
            in sorted(
                suite_kind_counts.items()
            )
        },
        "selected_task_version_counts": dict(
            sorted(
                version_counts.items()
            )
        ),
        "ground_truth_function_counts": dict(
            ground_truth_function_counts.most_common()
        ),
    }

    REPORT_OUTPUT_PATH.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("=" * 80)
    print(
        "AGENTDOJO EFFECTIVE TASK INVENTORY"
    )
    print("=" * 80)

    print()
    print(
        "Repository commit:",
        commit,
    )

    print(
        "Target benchmark version:",
        version_to_string(
            TARGET_VERSION
        ),
    )

    print(
        "Parsed task revisions:",
        len(revisions),
    )

    print(
        "Effective tasks:",
        len(effective_records),
    )

    print()
    print(
        "Effective tasks by suite and kind:"
    )

    for (
        suite,
        kind,
    ), count in sorted(
        suite_kind_counts.items()
    ):
        print(
            f"  {suite:<10} "
            f"{kind:<15} "
            f"{count}"
        )

    print()
    print(
        "Selected task revisions:"
    )

    for version, count in sorted(
        version_counts.items()
    ):
        print(
            f"  {version}: {count}"
        )

    print()
    print(
        "Most frequent ground-truth functions:"
    )

    for function_name, count in (
        ground_truth_function_counts
        .most_common(20)
    ):
        print(
            f"  {function_name}: {count}"
        )

    print()
    print(
        f"Inventory JSON: {JSON_OUTPUT_PATH}"
    )

    print(
        f"Inventory CSV: {CSV_OUTPUT_PATH}"
    )

    print(
        f"Report: {REPORT_OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()

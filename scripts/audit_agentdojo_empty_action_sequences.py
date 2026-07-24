from __future__ import annotations

import ast
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SOURCE_ROOT = Path(
    "data/raw/agentdojo_source"
)

USER_POOL_PATH = Path(
    "data/interim/"
    "agentdojo_user_task_structure_pool_v0.1.jsonl"
)

INJECTION_POOL_PATH = Path(
    "data/interim/"
    "agentdojo_injection_task_structure_pool_v0.1.jsonl"
)

OUTPUT_DIR = Path(
    "data/interim/"
    "agentdojo_parser_audit_v0.1"
)

CSV_OUTPUT_PATH = (
    OUTPUT_DIR /
    "empty_action_sequence_structures.csv"
)

SNIPPET_OUTPUT_PATH = (
    OUTPUT_DIR /
    "empty_action_sequence_source_snippets.txt"
)

REPORT_OUTPUT_PATH = (
    OUTPUT_DIR /
    "empty_action_sequence_report.json"
)


def load_jsonl(
    path: Path,
) -> list[dict[str, Any]]:

    records = []

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:

        for line in file:

            line = line.strip()

            if line:
                records.append(
                    json.loads(line)
                )

    return records


def expected_class_name(
    record: dict[str, Any],
) -> str:

    prefix = (
        "UserTask"
        if record["task_kind"] == "user_task"
        else "InjectionTask"
    )

    return (
        f"{prefix}"
        f"{record['task_number']}"
    )


def find_class_node(
    tree: ast.Module,
    class_name: str,
) -> ast.ClassDef | None:

    for node in tree.body:

        if (
            isinstance(node, ast.ClassDef)
            and node.name == class_name
        ):
            return node

    return None


def get_ground_truth_shape(
    class_node: ast.ClassDef,
) -> dict[str, Any]:

    method_names = []

    function_call_count = 0
    append_call_count = 0
    helper_call_names = []
    return_expressions = []
    assignments = []

    for statement in class_node.body:

        if isinstance(
            statement,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ):
            method_names.append(
                statement.name
            )

            if statement.name == "ground_truth":

                for node in ast.walk(
                    statement
                ):

                    if isinstance(
                        node,
                        ast.Call,
                    ):

                        function_name = ""

                        if isinstance(
                            node.func,
                            ast.Name,
                        ):
                            function_name = (
                                node.func.id
                            )

                        elif isinstance(
                            node.func,
                            ast.Attribute,
                        ):
                            function_name = (
                                node.func.attr
                            )

                        if (
                            function_name
                            ==
                            "FunctionCall"
                        ):
                            function_call_count += 1

                        elif (
                            function_name
                            ==
                            "append"
                        ):
                            append_call_count += 1

                        elif function_name:
                            helper_call_names.append(
                                function_name
                            )

                    elif isinstance(
                        node,
                        ast.Return,
                    ):

                        try:
                            expression = ast.unparse(
                                node.value
                            )
                        except Exception:
                            expression = None

                        if expression:
                            return_expressions.append(
                                expression
                            )

        elif isinstance(
            statement,
            ast.Assign,
        ):

            for target in statement.targets:

                if isinstance(
                    target,
                    ast.Name,
                ):
                    assignments.append(
                        target.id
                    )

        elif isinstance(
            statement,
            ast.AnnAssign,
        ):

            if isinstance(
                statement.target,
                ast.Name,
            ):
                assignments.append(
                    statement.target.id
                )

    return {
        "method_names": method_names,
        "class_assignments": assignments,
        "has_ground_truth_method": (
            "ground_truth"
            in method_names
        ),
        "literal_function_call_count": (
            function_call_count
        ),
        "append_call_count": (
            append_call_count
        ),
        "helper_call_names": sorted(
            set(
                helper_call_names
            )
        ),
        "ground_truth_return_expressions": (
            return_expressions
        ),
        "base_classes": [
            ast.unparse(base)
            for base in class_node.bases
        ],
    }


def main() -> None:

    records = (
        load_jsonl(
            USER_POOL_PATH
        )
        +
        load_jsonl(
            INJECTION_POOL_PATH
        )
    )

    empty_records = [
        record
        for record in records
        if not record.get(
            "expected_action_sequence"
        )
    ]


    audit_rows = []
    source_snippets = []


    for record in empty_records:

        relative_source_file = Path(
            record["source"][
                "source_file"
            ]
        )

        source_path = (
            SOURCE_ROOT
            /
            relative_source_file
        )

        if not source_path.exists():
            raise FileNotFoundError(
                f"Source file not found: "
                f"{source_path}"
            )

        source_text = source_path.read_text(
            encoding="utf-8"
        )

        tree = ast.parse(
            source_text,
            filename=str(
                source_path
            ),
        )

        class_name = expected_class_name(
            record
        )

        class_node = find_class_node(
            tree,
            class_name,
        )

        if class_node is None:
            raise ValueError(
                f"Could not locate class "
                f"{class_name} in {source_path}"
            )


        shape = get_ground_truth_shape(
            class_node
        )


        try:
            class_source = ast.get_source_segment(
                source_text,
                class_node,
            )
        except Exception:
            class_source = None


        if not class_source:

            class_source = ast.unparse(
                class_node
            )


        audit_rows.append(
            {
                "structure_id": (
                    record[
                        "structure_id"
                    ]
                ),
                "suite": (
                    record["suite"]
                ),
                "task_kind": (
                    record["task_kind"]
                ),
                "task_id": (
                    record["task_id"]
                ),
                "class_name": (
                    class_name
                ),
                "prompt_or_goal": (
                    record[
                        "prompt_or_goal"
                    ]
                ),
                "source_file": str(
                    relative_source_file
                ),
                "effective_from_version": (
                    record["source"][
                        "effective_from_version"
                    ]
                ),
                "has_ground_truth_method": (
                    shape[
                        "has_ground_truth_method"
                    ]
                ),
                "base_classes": json.dumps(
                    shape[
                        "base_classes"
                    ],
                    ensure_ascii=False,
                ),
                "method_names": json.dumps(
                    shape[
                        "method_names"
                    ],
                    ensure_ascii=False,
                ),
                "class_assignments": json.dumps(
                    shape[
                        "class_assignments"
                    ],
                    ensure_ascii=False,
                ),
                "literal_function_call_count": (
                    shape[
                        "literal_function_call_count"
                    ]
                ),
                "append_call_count": (
                    shape[
                        "append_call_count"
                    ]
                ),
                "helper_call_names": json.dumps(
                    shape[
                        "helper_call_names"
                    ],
                    ensure_ascii=False,
                ),
                "ground_truth_return_expressions": (
                    json.dumps(
                        shape[
                            "ground_truth_return_expressions"
                        ],
                        ensure_ascii=False,
                    )
                ),
            }
        )


        source_snippets.append(
            "=" * 100
        )

        source_snippets.append(
            f"STRUCTURE ID: "
            f"{record['structure_id']}"
        )

        source_snippets.append(
            f"SUITE: {record['suite']}"
        )

        source_snippets.append(
            f"TASK KIND: "
            f"{record['task_kind']}"
        )

        source_snippets.append(
            f"CLASS: {class_name}"
        )

        source_snippets.append(
            f"SOURCE: {relative_source_file}"
        )

        source_snippets.append(
            f"EFFECTIVE VERSION: "
            f"{record['source']['effective_from_version']}"
        )

        source_snippets.append("")

        source_snippets.append(
            "PROMPT / GOAL:"
        )

        source_snippets.append(
            str(
                record[
                    "prompt_or_goal"
                ]
            )
        )

        source_snippets.append("")

        source_snippets.append(
            "PARSER SHAPE:"
        )

        source_snippets.append(
            json.dumps(
                shape,
                indent=2,
                ensure_ascii=False,
            )
        )

        source_snippets.append("")

        source_snippets.append(
            "CLASS SOURCE:"
        )

        source_snippets.append(
            class_source
        )

        source_snippets.append("")


    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


    fieldnames = list(
        audit_rows[0].keys()
    )


    with CSV_OUTPUT_PATH.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(
            audit_rows
        )


    SNIPPET_OUTPUT_PATH.write_text(
        "\n".join(
            source_snippets
        ),
        encoding="utf-8",
    )


    kind_counts = Counter(
        record[
            "task_kind"
        ]
        for record in empty_records
    )

    suite_kind_counts = Counter(
        (
            record["suite"],
            record["task_kind"],
        )
        for record in empty_records
    )

    ground_truth_presence_counts = Counter(
        row[
            "has_ground_truth_method"
        ]
        for row in audit_rows
    )


    report = {
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "total_structures_checked": (
            len(records)
        ),

        "empty_action_sequence_count": (
            len(empty_records)
        ),

        "empty_by_task_kind": dict(
            kind_counts
        ),

        "empty_by_suite_and_kind": {
            f"{suite}:{kind}": count
            for (
                suite,
                kind,
            ), count in sorted(
                suite_kind_counts.items()
            )
        },

        "has_ground_truth_method_counts": {
            str(key): value
            for key, value in (
                ground_truth_presence_counts.items()
            )
        },

        "important_note": (
            "An empty extracted action sequence may indicate "
            "a genuinely action-free task, inherited behavior, "
            "dynamic helper-generated ground truth, or an "
            "unsupported AST pattern."
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
        "AGENTDOJO EMPTY ACTION-SEQUENCE AUDIT"
    )
    print("=" * 80)

    print()
    print(
        "Total structures checked:",
        len(records),
    )

    print(
        "Empty action sequences:",
        len(empty_records),
    )

    print()
    print(
        "Empty sequences by task kind:"
    )

    for kind, count in sorted(
        kind_counts.items()
    ):
        print(
            f"  {kind}: {count}"
        )

    print()
    print(
        "Empty sequences by suite and kind:"
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
        "Classes with an explicit "
        "ground_truth method:"
    )

    for value, count in sorted(
        ground_truth_presence_counts.items(),
        key=lambda item: str(
            item[0]
        ),
    ):
        print(
            f"  {value}: {count}"
        )

    print()
    print(
        f"Audit CSV: {CSV_OUTPUT_PATH}"
    )

    print(
        f"Source snippets: "
        f"{SNIPPET_OUTPUT_PATH}"
    )

    print(
        f"Report: {REPORT_OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()

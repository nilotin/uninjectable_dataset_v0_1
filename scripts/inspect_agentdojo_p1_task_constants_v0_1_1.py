from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
from typing import Any


BLUEPRINT_PATH = Path(
    "data/processed/"
    "agentdojo_contextual_composition_blueprint_pool_v0.1.jsonl"
)

OUTPUT_PATH = Path(
    "data/interim/"
    "agentdojo_p1_task_constant_inspection_v0.1.1.json"
)


TARGETS = {
    "agentdojo_pair_091": {
        "structure_id": "agentdojo_workspace_user_task_033",
        "prompt_fragment": (
            "Please send a summary of the file"
        ),
        "interesting_names": {
            "_FILENAME",
            "FILENAME",
            "_FILE_ID",
            "FILE_ID",
            "_EMAIL",
            "EMAIL",
            "_SUBJECT",
            "SUBJECT",
            "_MEETING_DATE",
            "MEETING_DATE",
        },
    },

    "agentdojo_pair_095": {
        "structure_id": "agentdojo_workspace_user_task_013",
        "prompt_fragment": (
            "Please do the actions specified in the email"
        ),
        "interesting_names": {
            "_SENDER",
            "SENDER",
            "_SUBJECT",
            "SUBJECT",
            "_EMAIL_2_SUBJECT",
            "EMAIL_2_SUBJECT",
            "_RECIPIENT",
            "RECIPIENT",
        },
    },
}


def load_jsonl(
    path: Path,
) -> list[dict[str, Any]]:

    records = []

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
                records.append(
                    json.loads(line)
                )

            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid JSONL at {path}:"
                    f"{line_number}"
                ) from error

    return records


def add_unique_path(
    paths: list[Path],
    path: Path,
) -> None:

    path = path.expanduser()

    try:
        resolved = path.resolve()
    except OSError:
        resolved = path

    if (
        resolved.exists()
        and
        resolved not in paths
    ):
        paths.append(
            resolved
        )


def get_agentdojo_source_roots() -> list[Path]:

    import importlib.util
    import json
    import os
    import sys

    roots: list[Path] = []


    def add_root(
        path: Path,
    ) -> None:

        path = path.expanduser()

        try:
            path = path.resolve()
        except OSError:
            pass

        if (
            path.is_dir()
            and
            path not in roots
        ):
            roots.append(
                path
            )


    def infer_package_root(
        path: Path,
    ) -> None:

        path = path.expanduser()

        try:
            path = path.resolve()
        except OSError:
            pass

        if path.is_file():
            current = path.parent
        else:
            current = path


        candidates = [
            current,
            *current.parents,
        ]


        for candidate in candidates:

            # Repository layout:
            # <repo>/src/agentdojo/...
            if (
                candidate.name == "agentdojo"
                and
                candidate.parent.name == "src"
            ):
                add_root(
                    candidate
                )


            # Installed package layout:
            # site-packages/agentdojo/...
            if (
                candidate.name == "agentdojo"
                and
                (
                    candidate
                    /
                    "__init__.py"
                ).exists()
            ):
                add_root(
                    candidate
                )


            if (
                candidate.name == "src"
                and
                (
                    candidate
                    /
                    "agentdojo"
                ).is_dir()
            ):
                add_root(
                    candidate
                    /
                    "agentdojo"
                )


    # --------------------------------------------------------
    # 1. Common local repository locations
    # --------------------------------------------------------

    local_candidates = [
        Path.cwd()
        /
        "src"
        /
        "agentdojo",

        Path.cwd()
        /
        "agentdojo"
        /
        "src"
        /
        "agentdojo",

        Path.cwd().parent
        /
        "agentdojo"
        /
        "src"
        /
        "agentdojo",

        Path.cwd().parent
        /
        "AgentDojo"
        /
        "src"
        /
        "agentdojo",
    ]

    for candidate in local_candidates:
        add_root(
            candidate
        )


    # --------------------------------------------------------
    # 2. Explicit AgentDojo repository path
    # --------------------------------------------------------

    configured_root = os.environ.get(
        "AGENTDOJO_ROOT"
    )

    if configured_root:

        configured_path = Path(
            configured_root
        )

        add_root(
            configured_path
            /
            "src"
            /
            "agentdojo"
        )

        add_root(
            configured_path
            /
            "agentdojo"
        )

        infer_package_root(
            configured_path
        )


    # --------------------------------------------------------
    # 3. Reuse absolute paths resolved by the previous script
    # --------------------------------------------------------

    resolution_report = Path(
        "data/interim/"
        "agentdojo_p1_concrete_object_resolution_v0.1.1.json"
    )

    if resolution_report.exists():

        report = json.loads(
            resolution_report.read_text(
                encoding="utf-8"
            )
        )


        def visit(
            value,
        ) -> None:

            if isinstance(
                value,
                dict,
            ):

                for child in value.values():
                    visit(
                        child
                    )


            elif isinstance(
                value,
                list,
            ):

                for child in value:
                    visit(
                        child
                    )


            elif isinstance(
                value,
                str,
            ):

                if (
                    value.endswith(
                        ".yaml"
                    )
                    or
                    value.endswith(
                        ".yml"
                    )
                    or
                    value.endswith(
                        ".py"
                    )
                ):
                    candidate = Path(
                        value
                    )

                    if candidate.exists():
                        infer_package_root(
                            candidate
                        )


        visit(
            report
        )


    # --------------------------------------------------------
    # 4. Installed Python package
    # --------------------------------------------------------

    spec = importlib.util.find_spec(
        "agentdojo"
    )

    if (
        spec is not None
        and
        spec.origin is not None
    ):

        infer_package_root(
            Path(
                spec.origin
            )
        )


    # --------------------------------------------------------
    # 5. Python import paths
    # --------------------------------------------------------

    for raw_path in sys.path:

        if not raw_path:
            continue

        path = Path(
            raw_path
        )

        add_root(
            path
            /
            "agentdojo"
        )

        add_root(
            path
            /
            "src"
            /
            "agentdojo"
        )


    # --------------------------------------------------------
    # 6. Nearby source discovery fallback
    # --------------------------------------------------------

    search_roots = [
        Path.cwd(),
        Path.cwd().parent,
        Path.home()
        /
        "Downloads",
    ]

    seen_search_roots: set[Path] = set()

    for search_root in search_roots:

        try:
            search_root = (
                search_root
                .expanduser()
                .resolve()
            )
        except OSError:
            continue

        if (
            not search_root.exists()
            or
            search_root in seen_search_roots
        ):
            continue

        seen_search_roots.add(
            search_root
        )


        # These files were already encountered by the
        # concrete-object resolver and provide a reliable
        # anchor back to src/agentdojo.
        for filename in [
            "cloud_drive.yaml",
            "inbox.yaml",
        ]:

            try:
                matches = search_root.rglob(
                    filename
                )

                for match in matches:

                    path_text = (
                        match
                        .as_posix()
                    )

                    if (
                        "/data/suites/"
                        not in path_text
                    ):
                        continue

                    infer_package_root(
                        match
                    )

            except (
                OSError,
                PermissionError,
            ):
                continue


    return roots


def target_name(
    node: ast.expr,
) -> str | None:

    if isinstance(
        node,
        ast.Name,
    ):
        return node.id

    if isinstance(
        node,
        ast.Attribute,
    ):

        if isinstance(
            node.value,
            ast.Name,
        ) and node.value.id == "self":

            return node.attr

        return node.attr

    return None


def value_details(
    node: ast.AST,
    source: str,
) -> dict[str, Any]:

    source_expression = (
        ast.get_source_segment(
            source,
            node,
        )
        or
        ""
    )

    try:
        literal_value = ast.literal_eval(
            node
        )

        literal_resolved = True

    except Exception:
        literal_value = None
        literal_resolved = False

    return {
        "literal_resolved": literal_resolved,
        "literal_value": literal_value,
        "source_expression": source_expression,
    }


def find_containing_class(
    tree: ast.AST,
    line_number: int,
) -> ast.ClassDef | None:

    candidates = []

    for node in ast.walk(
        tree
    ):

        if not isinstance(
            node,
            ast.ClassDef,
        ):
            continue

        start = getattr(
            node,
            "lineno",
            None,
        )

        end = getattr(
            node,
            "end_lineno",
            None,
        )

        if (
            start is not None
            and
            end is not None
            and
            start <= line_number <= end
        ):
            candidates.append(
                node
            )

    if not candidates:
        return None

    return min(
        candidates,
        key=lambda node: (
            node.end_lineno
            -
            node.lineno
        ),
    )


def collect_assignments(
    class_node: ast.ClassDef,
    source: str,
    interesting_names: set[str],
) -> list[dict[str, Any]]:

    assignments = []

    for node in ast.walk(
        class_node
    ):

        targets: list[ast.expr] = []
        value_node: ast.AST | None = None

        if isinstance(
            node,
            ast.Assign,
        ):
            targets = list(
                node.targets
            )
            value_node = node.value

        elif isinstance(
            node,
            ast.AnnAssign,
        ):
            targets = [
                node.target
            ]
            value_node = node.value

        if value_node is None:
            continue

        for target in targets:

            name = target_name(
                target
            )

            if not name:
                continue

            normalized_name = (
                name.upper()
            )

            interesting = (
                name in interesting_names
                or
                normalized_name in interesting_names
                or
                any(
                    keyword in normalized_name
                    for keyword in [
                        "FILE",
                        "FILENAME",
                        "SENDER",
                        "SUBJECT",
                        "EMAIL",
                        "RECIPIENT",
                    ]
                )
            )

            if not interesting:
                continue

            assignments.append(
                {
                    "name": name,
                    "line_number": getattr(
                        node,
                        "lineno",
                        None,
                    ),
                    **value_details(
                        value_node,
                        source,
                    ),
                }
            )

    assignments.sort(
        key=lambda item: (
            item[
                "line_number"
            ]
            or 0,
            item[
                "name"
            ],
        )
    )

    return assignments


def source_snippet(
    lines: list[str],
    matching_line: int,
    radius: int = 45,
) -> str:

    start = max(
        1,
        matching_line - radius,
    )

    end = min(
        len(lines),
        matching_line + radius,
    )

    output_lines = []

    for line_number in range(
        start,
        end + 1,
    ):

        marker = (
            ">>>"
            if line_number == matching_line
            else "   "
        )

        output_lines.append(
            f"{marker} {line_number:04d}: "
            f"{lines[line_number - 1]}"
        )

    return "\n".join(
        output_lines
    )


def search_source(
    roots: list[Path],
    prompt_fragment: str,
    interesting_names: set[str],
) -> list[dict[str, Any]]:

    matches = []

    seen_files: set[Path] = set()

    for root in roots:

        for path in root.rglob(
            "*.py"
        ):

            try:
                resolved_path = path.resolve()
            except OSError:
                resolved_path = path

            if resolved_path in seen_files:
                continue

            seen_files.add(
                resolved_path
            )

            try:
                source = path.read_text(
                    encoding="utf-8"
                )
            except (
                UnicodeDecodeError,
                OSError,
            ):
                continue

            if prompt_fragment not in source:
                continue

            lines = source.splitlines()

            line_numbers = [
                index
                for index, line in enumerate(
                    lines,
                    start=1,
                )
                if prompt_fragment in line
            ]

            try:
                tree = ast.parse(
                    source
                )
            except SyntaxError:
                tree = None

            for line_number in line_numbers:

                class_node = (
                    find_containing_class(
                        tree,
                        line_number,
                    )
                    if tree is not None
                    else None
                )

                assignments = (
                    collect_assignments(
                        class_node,
                        source,
                        interesting_names,
                    )
                    if class_node is not None
                    else []
                )

                matches.append(
                    {
                        "source_file": str(
                            path.resolve()
                        ),

                        "matching_line": line_number,

                        "class_name": (
                            class_node.name
                            if class_node is not None
                            else None
                        ),

                        "class_start_line": (
                            class_node.lineno
                            if class_node is not None
                            else None
                        ),

                        "class_end_line": (
                            class_node.end_lineno
                            if class_node is not None
                            else None
                        ),

                        "assignments": assignments,

                        "snippet": source_snippet(
                            lines,
                            line_number,
                        ),
                    }
                )

    return matches


def main() -> None:

    roots = get_agentdojo_source_roots()

    if not roots:
        raise FileNotFoundError(
            "No AgentDojo Python package/source "
            "directory was found."
        )


    blueprints = load_jsonl(
        BLUEPRINT_PATH
    )

    blueprint_by_structure_id = {
        blueprint[
            "structure"
        ][
            "structure_id"
        ]: blueprint
        for blueprint in blueprints
    }


    results = {
        "searched_roots": [
            str(root)
            for root in roots
        ],

        "pairs": {},
    }


    print("=" * 80)
    print(
        "AGENTDOJO P1 TASK CONSTANT "
        "INSPECTION v0.1.1"
    )
    print("=" * 80)

    print()
    print("SEARCHED ROOTS:")

    for root in roots:
        print(
            f"  {root}"
        )


    for pair_id, specification in (
        TARGETS.items()
    ):

        structure_id = specification[
            "structure_id"
        ]

        blueprint = (
            blueprint_by_structure_id.get(
                structure_id
            )
        )

        matches = search_source(
            roots,
            specification[
                "prompt_fragment"
            ],
            specification[
                "interesting_names"
            ],
        )


        pair_result = {
            "structure_id": structure_id,

            "blueprint_source_metadata": (
                blueprint[
                    "structure"
                ].get(
                    "source",
                    {},
                )
                if blueprint is not None
                else None
            ),

            "matches": matches,
        }

        results[
            "pairs"
        ][
            pair_id
        ] = pair_result


        print()
        print("=" * 110)

        print(
            "PAIR:",
            pair_id,
        )

        print(
            "STRUCTURE:",
            structure_id,
        )

        print(
            "SOURCE MATCHES:",
            len(matches),
        )


        for match_index, match in enumerate(
            matches,
            start=1,
        ):

            print()
            print(
                f"MATCH {match_index}:"
            )

            print(
                "SOURCE FILE:",
                match[
                    "source_file"
                ],
            )

            print(
                "CLASS:",
                match[
                    "class_name"
                ],
            )

            print(
                "MATCHING LINE:",
                match[
                    "matching_line"
                ],
            )

            print(
                "RELEVANT ASSIGNMENTS:"
            )


            if not match[
                "assignments"
            ]:

                print(
                    "  <none automatically resolved>"
                )


            for assignment in match[
                "assignments"
            ]:

                print(
                    "  "
                    f"{assignment['name']} = "
                    f"{assignment['literal_value']!r} "
                    f"(expression: "
                    f"{assignment['source_expression']})"
                )


            print()
            print("SOURCE SNIPPET:")
            print(
                match[
                    "snippet"
                ]
            )


    OUTPUT_PATH.write_text(
        json.dumps(
            results,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


    print()
    print("=" * 80)

    print(
        f"Inspection report: {OUTPUT_PATH}"
    )

    print()
    print(
        "Pair plan modified: no"
    )

    print(
        "Smoke pool modified: no"
    )

    print(
        "Review decisions modified: no"
    )


if __name__ == "__main__":
    main()

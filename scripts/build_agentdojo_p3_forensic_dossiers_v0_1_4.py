from __future__ import annotations

import ast
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


INVENTORY_PATH = Path(
    "data/interim/"
    "agentdojo_p3_revision_inventory_v0.1.4.jsonl"
)

PAIR_PLAN_PATH = Path(
    "data/interim/"
    "agentdojo_contextual_pair_plan_v0.1.4_"
    "p2_travel_repaired.jsonl"
)

OUTPUT_DIRECTORY = Path(
    "data/interim/"
    "agentdojo_p3_forensic_dossiers_v0.1.4"
)

COMBINED_TEXT_PATH = Path(
    "data/interim/"
    "agentdojo_p3_forensic_dossier_combined_v0.1.4.txt"
)

COMBINED_JSONL_PATH = Path(
    "data/interim/"
    "agentdojo_p3_forensic_dossier_combined_v0.1.4.jsonl"
)

REPORT_PATH = Path(
    "data/interim/"
    "agentdojo_p3_forensic_dossiers_v0.1.4_report.json"
)


EXPECTED_PAIR_COUNT = 17

EXPECTED_ISSUE_COUNTS = {
    "contextual_alignment_issue": 6,
    "document_content_not_retrieved": 3,
    "retrieval_path_not_guaranteed": 2,
    "retrieval_query_mismatch": 6,
}


ISSUE_OUTPUT_NAMES = {
    "retrieval_path_not_guaranteed": (
        "01_banking_retrieval_path"
    ),

    "contextual_alignment_issue": (
        "02_contextual_alignment"
    ),

    "document_content_not_retrieved": (
        "03_document_content_retrieval"
    ),

    "retrieval_query_mismatch": (
        "04_email_query_mismatch"
    ),
}


LOCATOR_PATTERN = re.compile(
    r"""
    (
        https?://[^\s"'<>]+
        |
        www\.[A-Za-z0-9._~:/?#\[\]@!$&()*+,;=%-]+
        |
        [A-Za-z0-9_.-]+\.
        (?:txt|docx|xlsx|pdf|csv|json|md|html)
        |
        [A-Za-z0-9._%+-]+@
        [A-Za-z0-9.-]+\.[A-Za-z]{2,}
    )
    """,
    re.VERBOSE | re.IGNORECASE,
)


INTERESTING_YAML_KEYS = {
    "name",
    "filename",
    "sender",
    "recipient",
    "recipients",
    "subject",
    "body",
    "url",
    "city",
    "query",
    "file_path",
    "content",
    "reviews",
    "email",
    "id_",
}


def load_jsonl(
    path: Path,
) -> list[dict[str, Any]]:

    if not path.exists():
        raise FileNotFoundError(
            f"Missing JSONL file: {path}"
        )

    records: list[dict[str, Any]] = []

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
                    f"Invalid JSONL in {path}, "
                    f"line {line_number}."
                ) from error

    return records


def write_jsonl(
    path: Path,
    records: list[dict[str, Any]],
) -> None:

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
    ) as file:

        for record in records:

            file.write(
                json.dumps(
                    record,
                    ensure_ascii=False,
                )
            )

            file.write("\n")


def canonical_json(
    value: Any,
) -> str:

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def pair_number(
    pair_id: str,
) -> int:

    match = re.search(
        r"(\d+)$",
        pair_id,
    )

    if match is None:
        raise ValueError(
            f"Invalid pair ID: {pair_id}"
        )

    return int(match.group(1))


def resolve_agentdojo_root() -> Path:

    candidates: list[Path] = []

    configured_root = os.environ.get(
        "AGENTDOJO_ROOT"
    )

    if configured_root:

        configured = Path(
            configured_root
        ).expanduser()

        candidates.extend(
            [
                configured,
                configured / "src" / "agentdojo",
            ]
        )

    candidates.extend(
        [
            Path(
                "data/raw/agentdojo_source/"
                "src/agentdojo"
            ),

            Path(
                "data/raw/agentdojo_source"
            ),

            Path.cwd().parent
            / "agentdojo/src/agentdojo",
        ]
    )

    for candidate in candidates:

        try:
            candidate = candidate.resolve()

        except OSError:
            continue

        if (
            candidate.is_dir()
            and
            (
                candidate
                / "default_suites"
            ).exists()
        ):
            return candidate

        nested = (
            candidate
            / "src"
            / "agentdojo"
        )

        if (
            nested.is_dir()
            and
            (
                nested
                / "default_suites"
            ).exists()
        ):
            return nested.resolve()

    raise FileNotFoundError(
        "Could not locate AgentDojo source root."
    )


def structure_id(
    context: dict[str, Any],
) -> str:

    return str(
        context.get("structure_id")
        or context.get("blueprint_id")
        or ""
    )


def action_name(
    action: dict[str, Any],
) -> str:

    return str(
        action.get(
            "normalized_function_name"
        )
        or action.get("function")
        or action.get("tool_name")
        or ""
    )


def action_args(
    action: dict[str, Any],
) -> Any:

    if action.get("args") is not None:
        return action["args"]

    return action.get(
        "args_expression"
    )


def class_specification(
    structure: str,
) -> tuple[str, str] | None:

    user_match = re.search(
        r"_user_task_(\d+)$",
        structure,
    )

    if user_match:

        return (
            "user_tasks.py",
            "UserTask"
            +
            str(
                int(
                    user_match.group(1)
                )
            ),
        )

    injection_match = re.search(
        r"_injection_task_(\d+)$",
        structure,
    )

    if injection_match:

        return (
            "injection_tasks.py",
            "InjectionTask"
            +
            str(
                int(
                    injection_match.group(1)
                )
            ),
        )

    return None


def literal_value(
    node: ast.AST,
) -> Any:

    try:
        return ast.literal_eval(node)

    except Exception:
        return None


def extract_function_calls(
    source: str | None,
) -> list[dict[str, Any]]:

    if not source:
        return []

    calls = []

    pattern = re.compile(
        r"""
        FunctionCall
        \s*\(
        [\s\S]*?
        function
        \s*=
        \s*
        ["']
        (?P<function>[^"']+)
        ["']
        [\s\S]*?
        args
        \s*=
        (?P<args>
            \{[\s\S]*?\}
        )
        [\s\S]*?
        \)
        """,
        re.VERBOSE,
    )

    for match in pattern.finditer(
        source
    ):

        calls.append(
            {
                "function": match.group(
                    "function"
                ),

                "args_expression": (
                    match.group("args")
                ),
            }
        )

    if calls:
        return calls

    function_names = re.findall(
        r"""
        FunctionCall
        \s*\(
        [\s\S]*?
        function
        \s*=
        \s*
        ["']
        ([^"']+)
        ["']
        """,
        source,
        re.VERBOSE,
    )

    return [
        {
            "function": function_name,
            "args_expression": None,
        }
        for function_name in function_names
    ]


def find_task_classes(
    package_root: Path,
    suite: str,
    structure: str,
) -> list[dict[str, Any]]:

    specification = class_specification(
        structure
    )

    if specification is None:
        return []

    target_filename, target_class = (
        specification
    )

    matches = []

    for path in package_root.rglob(
        target_filename
    ):

        if suite not in path.parts:
            continue

        try:
            source = path.read_text(
                encoding="utf-8"
            )

            tree = ast.parse(source)

        except (
            OSError,
            UnicodeDecodeError,
            SyntaxError,
        ):
            continue

        for node in tree.body:

            if not isinstance(
                node,
                ast.ClassDef,
            ):
                continue

            if node.name != target_class:
                continue

            assignments = []
            methods = []

            for child in node.body:

                target_name = None
                value_node = None

                if isinstance(
                    child,
                    ast.Assign,
                ):

                    if (
                        len(child.targets) == 1
                        and
                        isinstance(
                            child.targets[0],
                            ast.Name,
                        )
                    ):
                        target_name = (
                            child.targets[0].id
                        )

                        value_node = child.value

                elif isinstance(
                    child,
                    ast.AnnAssign,
                ):

                    if isinstance(
                        child.target,
                        ast.Name,
                    ):
                        target_name = (
                            child.target.id
                        )

                        value_node = child.value

                if (
                    target_name is not None
                    and
                    value_node is not None
                ):

                    assignments.append(
                        {
                            "name": target_name,

                            "literal_value": (
                                literal_value(
                                    value_node
                                )
                            ),

                            "source_expression": (
                                ast.get_source_segment(
                                    source,
                                    value_node,
                                )
                                or
                                ""
                            ),
                        }
                    )

                if isinstance(
                    child,
                    (
                        ast.FunctionDef,
                        ast.AsyncFunctionDef,
                    ),
                ):

                    method_source = (
                        ast.get_source_segment(
                            source,
                            child,
                        )
                    )

                    methods.append(
                        {
                            "name": child.name,

                            "source": (
                                method_source
                            ),

                            "function_calls": (
                                extract_function_calls(
                                    method_source
                                )
                            ),
                        }
                    )

            matches.append(
                {
                    "source_file": str(
                        path.resolve()
                    ),

                    "class_name": node.name,

                    "class_start_line": (
                        node.lineno
                    ),

                    "class_end_line": (
                        node.end_lineno
                    ),

                    "assignments": assignments,

                    "methods": methods,

                    "class_source": (
                        ast.get_source_segment(
                            source,
                            node,
                        )
                    ),
                }
            )

    return matches


def extract_locator_hints(
    context_lines: list[str],
) -> list[str]:

    hints = set()

    context = "\n".join(
        context_lines
    )

    for match in LOCATOR_PATTERN.finditer(
        context
    ):

        hints.add(
            match.group(1).rstrip(
                ".,);:"
            )
        )

    key_value_pattern = re.compile(
        r"""
        ^\s*
        (?P<key>
            name
            |filename
            |sender
            |recipient
            |recipients
            |subject
            |url
            |city
            |query
            |file_path
            |email
            |id_
        )
        \s*:
        \s*
        (?P<value>.+?)
        \s*$
        """,
        re.VERBOSE | re.IGNORECASE,
    )

    for line in context_lines:

        match = key_value_pattern.match(
            line
        )

        if match is None:
            continue

        value = match.group(
            "value"
        ).strip()

        if (
            value
            and
            value not in {
                "|",
                ">",
                "null",
                "None",
            }
        ):
            hints.add(
                f"{match.group('key')}={value}"
            )

    return sorted(hints)


def vector_occurrences(
    package_root: Path,
    suite: str,
    vector_id: str,
) -> list[dict[str, Any]]:

    suite_root = (
        package_root
        / "data"
        / "suites"
        / suite
    )

    search_root = (
        suite_root
        if suite_root.exists()
        else package_root
    )

    occurrences = []

    for path in search_root.rglob("*"):

        if (
            not path.is_file()
            or
            path.suffix.lower()
            not in {
                ".yaml",
                ".yml",
                ".json",
                ".py",
            }
        ):
            continue

        try:
            text = path.read_text(
                encoding="utf-8"
            )

        except (
            OSError,
            UnicodeDecodeError,
        ):
            continue

        if vector_id not in text:
            continue

        lines = text.splitlines()

        for line_number, line in enumerate(
            lines,
            start=1,
        ):

            if vector_id not in line:
                continue

            start = max(
                1,
                line_number - 24,
            )

            end = min(
                len(lines),
                line_number + 24,
            )

            context_lines = lines[
                start - 1:end
            ]

            occurrences.append(
                {
                    "source_file": str(
                        path.resolve()
                    ),

                    "line_number": (
                        line_number
                    ),

                    "line_text": line,

                    "context_start_line": (
                        start
                    ),

                    "context_end_line": (
                        end
                    ),

                    "context": "\n".join(
                        context_lines
                    ),

                    "locator_hints": (
                        extract_locator_hints(
                            context_lines
                        )
                    ),
                }
            )

    return occurrences


def parse_suite_vector_catalog(
    package_root: Path,
    suite: str,
) -> list[dict[str, Any]]:

    path = (
        package_root
        / "data"
        / "suites"
        / suite
        / "injection_vectors.yaml"
    )

    if not path.exists():
        return []

    text = path.read_text(
        encoding="utf-8"
    )

    lines = text.splitlines()

    vector_starts = []

    top_level_pattern = re.compile(
        r"""
        ^
        (?P<vector>
            [A-Za-z_]
            [A-Za-z0-9_]*
        )
        \s*:
        \s*
        $
        """,
        re.VERBOSE,
    )

    for index, line in enumerate(lines):

        match = top_level_pattern.match(
            line
        )

        if match:

            vector_starts.append(
                (
                    index,
                    match.group("vector"),
                )
            )

    catalog = []

    for position, (
        start_index,
        vector_id,
    ) in enumerate(vector_starts):

        if position + 1 < len(
            vector_starts
        ):

            end_index = (
                vector_starts[
                    position + 1
                ][0]
            )

        else:
            end_index = len(lines)

        block_lines = lines[
            start_index:end_index
        ]

        block = "\n".join(
            block_lines
        )

        description_match = re.search(
            r"""
            ^\s+
            description
            \s*:
            \s*
            (?P<value>.*)
            $
            """,
            block,
            re.VERBOSE | re.MULTILINE,
        )

        default_match = re.search(
            r"""
            ^\s+
            default
            \s*:
            \s*
            (?P<value>.*)
            $
            """,
            block,
            re.VERBOSE | re.MULTILINE,
        )

        occurrences = vector_occurrences(
            package_root,
            suite,
            vector_id,
        )

        locator_hints = sorted(
            {
                hint
                for occurrence in occurrences
                for hint in occurrence[
                    "locator_hints"
                ]
            }
        )

        catalog.append(
            {
                "vector_id": vector_id,

                "description_expression": (
                    description_match.group(
                        "value"
                    ).strip()
                    if description_match
                    else None
                ),

                "default_expression": (
                    default_match.group(
                        "value"
                    ).strip()
                    if default_match
                    else None
                ),

                "raw_block": block,

                "locator_hints": (
                    locator_hints
                ),

                "occurrence_count": len(
                    occurrences
                ),
            }
        )

    return catalog


def compact_pair(
    pair: dict[str, Any],
) -> dict[str, Any]:

    selected = pair[
        "selected_actions"
    ]

    surface = pair[
        "injection_surface"
    ]

    binding = pair.get(
        "context_bindings",
        {},
    )

    return {
        "pair_id": pair[
            "pair_id"
        ],

        "suite": pair[
            "suite"
        ],

        "legitimate_structure_id": (
            structure_id(
                pair[
                    "legitimate_context"
                ]
            )
        ),

        "attacker_structure_id": (
            structure_id(
                pair[
                    "attacker_context"
                ]
            )
        ),

        "vector_id": surface.get(
            "vector_id"
        ),

        "user_goal": (
            pair[
                "legitimate_context"
            ].get(
                "prompt_or_goal"
            )
        ),

        "attacker_goal": (
            pair[
                "attacker_context"
            ].get(
                "prompt_or_goal"
            )
        ),

        "safe_action": {
            "tool": action_name(
                selected[
                    "authorized_user_action"
                ]
            ),

            "args": action_args(
                selected[
                    "authorized_user_action"
                ]
            ),
        },

        "risky_action": {
            "tool": action_name(
                selected[
                    "attacker_target_action"
                ]
            ),

            "args": action_args(
                selected[
                    "attacker_target_action"
                ]
            ),
        },

        "surface": surface,

        "context_bindings": binding,
    }


def task_tool_summary(
    task_matches: list[dict[str, Any]],
) -> list[str]:

    tools = []

    for task_match in task_matches:

        for method in task_match[
            "methods"
        ]:

            if method[
                "name"
            ] != "ground_truth":
                continue

            for function_call in method[
                "function_calls"
            ]:

                tool_name = function_call[
                    "function"
                ]

                if tool_name not in tools:
                    tools.append(
                        tool_name
                    )

    return tools


def build_text_section(
    record: dict[str, Any],
) -> str:

    lines = [
        "=" * 120,

        f"PAIR: {record['pair_id']}",

        (
            "ISSUE: "
            f"{record['issue_category']}"
        ),

        (
            "SUITE: "
            f"{record['suite']}"
        ),

        (
            "REVIEW NOTE: "
            f"{record['review_note']}"
        ),

        "",

        (
            "LEGITIMATE STRUCTURE: "
            f"{record['legitimate_structure_id']}"
        ),

        (
            "ATTACKER STRUCTURE: "
            f"{record['attacker_structure_id']}"
        ),

        (
            "CURRENT VECTOR: "
            f"{record['current_vector_id']}"
        ),

        "",

        "USER GOAL:",

        str(record["user_goal"]),

        "",

        "ATTACKER GOAL:",

        str(record["attacker_goal"]),

        "",

        (
            "SAFE ACTION: "
            f"{canonical_json(record['safe_action'])}"
        ),

        (
            "RISKY ACTION: "
            f"{canonical_json(record['risky_action'])}"
        ),

        "",

        (
            "LEGITIMATE GROUND-TRUTH TOOLS: "
            f"{record['legitimate_ground_truth_tools']}"
        ),

        (
            "ATTACKER GROUND-TRUTH TOOLS: "
            f"{record['attacker_ground_truth_tools']}"
        ),

        "",

        "CURRENT BINDING:",

        json.dumps(
            record[
                "current_context_bindings"
            ],
            indent=2,
            ensure_ascii=False,
        ),

        "",

        "CURRENT SURFACE:",

        json.dumps(
            record[
                "current_surface"
            ],
            indent=2,
            ensure_ascii=False,
        ),

        "",

        "LEGITIMATE TASK SOURCE:",
    ]

    if not record[
        "legitimate_task_sources"
    ]:

        lines.append(
            "  <no matching class found>"
        )

    for match in record[
        "legitimate_task_sources"
    ]:

        lines.extend(
            [
                (
                    "  SOURCE: "
                    f"{match['source_file']} "
                    f"class={match['class_name']} "
                    f"lines="
                    f"{match['class_start_line']}-"
                    f"{match['class_end_line']}"
                ),

                "  ASSIGNMENTS:",
            ]
        )

        for assignment in match[
            "assignments"
        ]:

            lines.append(
                "    "
                f"{assignment['name']} = "
                f"{assignment['literal_value']!r} "
                f"(expr: "
                f"{assignment['source_expression']})"
            )

        for method in match[
            "methods"
        ]:

            if method["name"] not in {
                "ground_truth",
                "utility",
            }:
                continue

            lines.extend(
                [
                    "",
                    (
                        f"  METHOD: "
                        f"{method['name']}"
                    ),
                    str(method["source"]),
                ]
            )

    lines.extend(
        [
            "",
            "ATTACKER TASK SOURCE:",
        ]
    )

    if not record[
        "attacker_task_sources"
    ]:

        lines.append(
            "  <no matching class found>"
        )

    for match in record[
        "attacker_task_sources"
    ]:

        lines.extend(
            [
                (
                    "  SOURCE: "
                    f"{match['source_file']} "
                    f"class={match['class_name']} "
                    f"lines="
                    f"{match['class_start_line']}-"
                    f"{match['class_end_line']}"
                ),

                "  ASSIGNMENTS:",
            ]
        )

        for assignment in match[
            "assignments"
        ]:

            lines.append(
                "    "
                f"{assignment['name']} = "
                f"{assignment['literal_value']!r} "
                f"(expr: "
                f"{assignment['source_expression']})"
            )

        for method in match[
            "methods"
        ]:

            if method["name"] not in {
                "ground_truth",
                "utility",
            }:
                continue

            lines.extend(
                [
                    "",
                    (
                        f"  METHOD: "
                        f"{method['name']}"
                    ),
                    str(method["source"]),
                ]
            )

    lines.extend(
        [
            "",
            "CURRENT VECTOR OCCURRENCES:",
        ]
    )

    if not record[
        "current_vector_occurrences"
    ]:

        lines.append(
            "  <no occurrence found>"
        )

    for occurrence in record[
        "current_vector_occurrences"
    ]:

        lines.extend(
            [
                (
                    "  SOURCE: "
                    f"{occurrence['source_file']}:"
                    f"{occurrence['line_number']}"
                ),

                (
                    "  LOCATOR HINTS: "
                    f"{occurrence['locator_hints']}"
                ),

                occurrence[
                    "context"
                ],

                "",
            ]
        )

    lines.extend(
        [
            "SAME-SUITE VECTOR CATALOG:",
        ]
    )

    for candidate in record[
        "same_suite_vector_catalog"
    ]:

        lines.append(
            "  "
            f"vector={candidate['vector_id']} | "
            f"description="
            f"{candidate['description_expression']} | "
            f"default="
            f"{candidate['default_expression']} | "
            f"locator_hints="
            f"{candidate['locator_hints']}"
        )

    lines.extend(
        [
            "",
            "REPAIR DECISION: <pending>",
            "REPAIR NOTE: <pending>",
            "",
        ]
    )

    return "\n".join(lines)


def main() -> None:

    inventory = load_jsonl(
        INVENTORY_PATH
    )

    pairs = load_jsonl(
        PAIR_PLAN_PATH
    )

    if (
        len(inventory)
        !=
        EXPECTED_PAIR_COUNT
    ):
        raise ValueError(
            "Expected 17 P3 inventory records, "
            f"found {len(inventory)}."
        )

    issue_counts = Counter(
        str(
            row[
                "issue_category"
            ]
        )
        for row in inventory
    )

    if dict(issue_counts) != (
        EXPECTED_ISSUE_COUNTS
    ):
        raise ValueError(
            "Unexpected P3 issue distribution:\n"
            f"Expected: "
            f"{EXPECTED_ISSUE_COUNTS}\n"
            f"Found: {dict(issue_counts)}"
        )

    package_root = (
        resolve_agentdojo_root()
    )

    pair_by_id = {
        str(pair["pair_id"]): pair
        for pair in pairs
    }

    suite_catalogs = {
        suite: parse_suite_vector_catalog(
            package_root,
            suite,
        )
        for suite in {
            str(row["suite"])
            for row in inventory
        }
    }

    dossier_records = []

    for inventory_row in inventory:

        pair_id = str(
            inventory_row[
                "pair_id"
            ]
        )

        pair = pair_by_id.get(
            pair_id
        )

        if pair is None:
            raise ValueError(
                f"Pair missing from plan: "
                f"{pair_id}"
            )

        compact = compact_pair(
            pair
        )

        suite = str(
            compact[
                "suite"
            ]
        )

        legitimate_sources = (
            find_task_classes(
                package_root,
                suite,
                compact[
                    "legitimate_structure_id"
                ],
            )
        )

        attacker_sources = (
            find_task_classes(
                package_root,
                suite,
                compact[
                    "attacker_structure_id"
                ],
            )
        )

        occurrences = vector_occurrences(
            package_root,
            suite,
            str(
                compact[
                    "vector_id"
                ]
            ),
        )

        dossier_records.append(
            {
                "pair_id": pair_id,

                "issue_category": (
                    inventory_row[
                        "issue_category"
                    ]
                ),

                "review_note": (
                    inventory_row.get(
                        "review_note"
                    )
                ),

                "suite": suite,

                "legitimate_structure_id": (
                    compact[
                        "legitimate_structure_id"
                    ]
                ),

                "attacker_structure_id": (
                    compact[
                        "attacker_structure_id"
                    ]
                ),

                "current_vector_id": (
                    compact[
                        "vector_id"
                    ]
                ),

                "user_goal": compact[
                    "user_goal"
                ],

                "attacker_goal": compact[
                    "attacker_goal"
                ],

                "safe_action": compact[
                    "safe_action"
                ],

                "risky_action": compact[
                    "risky_action"
                ],

                "current_surface": compact[
                    "surface"
                ],

                "current_context_bindings": (
                    compact[
                        "context_bindings"
                    ]
                ),

                "legitimate_task_sources": (
                    legitimate_sources
                ),

                "attacker_task_sources": (
                    attacker_sources
                ),

                "legitimate_ground_truth_tools": (
                    task_tool_summary(
                        legitimate_sources
                    )
                ),

                "attacker_ground_truth_tools": (
                    task_tool_summary(
                        attacker_sources
                    )
                ),

                "current_vector_occurrences": (
                    occurrences
                ),

                "same_suite_vector_catalog": (
                    suite_catalogs[
                        suite
                    ]
                ),

                "repair_decision": None,

                "repair_note": None,
            }
        )

    dossier_records.sort(
        key=lambda row: pair_number(
            row["pair_id"]
        )
    )

    OUTPUT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    grouped_records: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)

    for record in dossier_records:

        grouped_records[
            record[
                "issue_category"
            ]
        ].append(record)

    output_files = {}

    for issue_category, records in (
        grouped_records.items()
    ):

        basename = ISSUE_OUTPUT_NAMES[
            issue_category
        ]

        jsonl_path = (
            OUTPUT_DIRECTORY
            /
            f"{basename}_v0.1.4.jsonl"
        )

        text_path = (
            OUTPUT_DIRECTORY
            /
            f"{basename}_v0.1.4.txt"
        )

        write_jsonl(
            jsonl_path,
            records,
        )

        text_lines = [
            "=" * 100,

            (
                "AGENTDOJO P3 FORENSIC DOSSIER "
                f"— {issue_category}"
            ),

            "=" * 100,

            "",

            f"Pair count: {len(records)}",

            (
                "AgentDojo source root: "
                f"{package_root}"
            ),

            "",

            (
                "No pair plans, labels, review "
                "decisions, or checkpoints were "
                "modified."
            ),

            "",
        ]

        for record in records:

            text_lines.append(
                build_text_section(
                    record
                )
            )

        text_path.write_text(
            "\n".join(
                text_lines
            ),
            encoding="utf-8",
        )

        output_files[
            issue_category
        ] = {
            "jsonl": str(jsonl_path),
            "text": str(text_path),
            "pair_count": len(records),
        }

    write_jsonl(
        COMBINED_JSONL_PATH,
        dossier_records,
    )

    combined_lines = [
        "=" * 100,

        (
            "AGENTDOJO P3 FORENSIC DOSSIER "
            "COMBINED v0.1.4"
        ),

        "=" * 100,

        "",

        f"Pair count: {len(dossier_records)}",

        (
            "AgentDojo source root: "
            f"{package_root}"
        ),

        "",
    ]

    for issue_category in [
        "retrieval_path_not_guaranteed",
        "contextual_alignment_issue",
        "document_content_not_retrieved",
        "retrieval_query_mismatch",
    ]:

        combined_lines.extend(
            [
                "",
                "#" * 120,
                (
                    f"ISSUE GROUP: "
                    f"{issue_category}"
                ),
                "#" * 120,
                "",
            ]
        )

        for record in grouped_records[
            issue_category
        ]:

            combined_lines.append(
                build_text_section(
                    record
                )
            )

    COMBINED_TEXT_PATH.write_text(
        "\n".join(combined_lines),
        encoding="utf-8",
    )

    suite_counts = Counter(
        record["suite"]
        for record in dossier_records
    )

    report = {
        "artifact_version": "0.1.4",

        "agentdojo_source_root": str(
            package_root
        ),

        "pair_count": len(
            dossier_records
        ),

        "suite_counts": dict(
            suite_counts
        ),

        "issue_counts": dict(
            issue_counts
        ),

        "pair_ids": [
            record["pair_id"]
            for record in dossier_records
        ],

        "group_outputs": output_files,

        "combined_jsonl": str(
            COMBINED_JSONL_PATH
        ),

        "combined_text": str(
            COMBINED_TEXT_PATH
        ),

        "pair_plan_modified": False,

        "labeled_pool_modified": False,

        "review_decisions_modified": False,

        "final_labels_modified": False,

        "checkpoint_modified": False,
    }

    REPORT_PATH.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("=" * 80)

    print(
        "AGENTDOJO P3 FORENSIC DOSSIERS "
        "v0.1.4 CREATED"
    )

    print("=" * 80)

    print()

    print(
        "AgentDojo root:",
        package_root,
    )

    print(
        "P3 pairs:",
        len(dossier_records),
    )

    print()

    print("Issue groups:")

    for issue_category in [
        "retrieval_path_not_guaranteed",
        "contextual_alignment_issue",
        "document_content_not_retrieved",
        "retrieval_query_mismatch",
    ]:

        output = output_files[
            issue_category
        ]

        print(
            "  "
            f"{issue_category}: "
            f"{output['pair_count']}"
        )

        print(
            "    "
            f"Text: {output['text']}"
        )

    print()

    print(
        "Combined dossier:",
        COMBINED_TEXT_PATH,
    )

    print(
        "Combined JSONL:",
        COMBINED_JSONL_PATH,
    )

    print(
        "Report:",
        REPORT_PATH,
    )

    print()

    print(
        "Pair plan modified: no"
    )

    print(
        "Labeled pool modified: no"
    )

    print(
        "Review decisions modified: no"
    )

    print(
        "Final labels modified: no"
    )

    print(
        "Checkpoint modified: no"
    )


if __name__ == "__main__":
    main()

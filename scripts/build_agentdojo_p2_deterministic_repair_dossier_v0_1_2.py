from __future__ import annotations

import ast
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any


INVENTORY_PATH = Path(
    "data/interim/"
    "agentdojo_p2_revision_inventory_v0.1.2.jsonl"
)

PAIR_PLAN_PATH = Path(
    "data/interim/"
    "agentdojo_contextual_pair_plan_v0.1.2_p1_repaired.jsonl"
)

OUTPUT_JSONL_PATH = Path(
    "data/interim/"
    "agentdojo_p2_deterministic_repair_dossier_v0.1.2.jsonl"
)

OUTPUT_TEXT_PATH = Path(
    "data/interim/"
    "agentdojo_p2_deterministic_repair_dossier_v0.1.2.txt"
)

OUTPUT_REPORT_PATH = Path(
    "data/interim/"
    "agentdojo_p2_deterministic_repair_dossier_v0.1.2_report.json"
)


TARGET_ISSUES = {
    "source_object_mismatch",
    "missing_concrete_source_binding",
}

EXPECTED_PAIR_COUNT = 9

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


def load_jsonl(
    path: Path,
) -> list[dict[str, Any]]:

    if not path.exists():
        raise FileNotFoundError(
            f"Missing JSONL file: {path}"
        )

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
        action.get("normalized_function_name")
        or action.get("function")
        or action.get("tool_name")
        or ""
    )


def action_args(
    action: dict[str, Any],
) -> Any:

    if action.get("args") is not None:
        return action["args"]

    return action.get("args_expression")


def resolve_agentdojo_root() -> Path:

    candidates = []

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
                "data/raw/agentdojo_source/src/agentdojo"
            ),

            Path(
                "data/raw/agentdojo_source"
            ),

            Path.cwd()
            / "data/raw/agentdojo_source/src/agentdojo",

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
                candidate / "default_suites"
            ).exists()
        ):
            return candidate


        package_candidate = (
            candidate
            / "src"
            / "agentdojo"
        )

        if (
            package_candidate.is_dir()
            and
            (
                package_candidate
                / "default_suites"
            ).exists()
        ):
            return package_candidate.resolve()


    raise FileNotFoundError(
        "Could not locate the AgentDojo source package."
    )


def source_file_path(
    package_root: Path,
    raw_path: str,
) -> Path | None:

    raw = Path(
        raw_path
    )

    candidates = [
        raw,
        Path.cwd() / raw,
    ]


    raw_parts = list(
        raw.parts
    )

    if (
        len(raw_parts) >= 3
        and
        raw_parts[0] == "src"
        and
        raw_parts[1] == "agentdojo"
    ):
        candidates.append(
            package_root.joinpath(
                *raw_parts[2:]
            )
        )


    candidates.append(
        package_root / raw
    )


    for candidate in candidates:

        try:
            candidate = candidate.resolve()
        except OSError:
            continue

        if candidate.is_file():
            return candidate

    return None


def class_name_from_structure(
    structure: str,
) -> str | None:

    match = re.search(
        r"_user_task_(\d+)$",
        structure,
    )

    if match is None:
        return None

    return (
        "UserTask"
        +
        str(
            int(
                match.group(1)
            )
        )
    )


def literal_value(
    node: ast.AST,
) -> Any:

    try:
        return ast.literal_eval(
            node
        )
    except Exception:
        return None


def task_source_matches(
    package_root: Path,
    suite: str,
    user_structure_id: str,
) -> list[dict[str, Any]]:

    target_class = class_name_from_structure(
        user_structure_id
    )

    if target_class is None:
        return []


    matches = []


    for path in package_root.rglob(
        "user_tasks.py"
    ):

        if suite not in path.parts:
            continue

        try:
            source = path.read_text(
                encoding="utf-8"
            )

            tree = ast.parse(
                source
            )

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
                    target_name is None
                    or
                    value_node is None
                ):
                    continue


                expression = (
                    ast.get_source_segment(
                        source,
                        value_node,
                    )
                    or
                    ""
                )


                assignments.append(
                    {
                        "name": target_name,

                        "literal_value": (
                            literal_value(
                                value_node
                            )
                        ),

                        "source_expression": (
                            expression
                        ),

                        "line_number": getattr(
                            child,
                            "lineno",
                            None,
                        ),
                    }
                )


            ground_truth_source = None

            for child in node.body:

                if (
                    isinstance(
                        child,
                        ast.FunctionDef,
                    )
                    and
                    child.name == "ground_truth"
                ):
                    ground_truth_source = (
                        ast.get_source_segment(
                            source,
                            child,
                        )
                    )

                    break


            class_source = ast.get_source_segment(
                source,
                node,
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

                    "assignments": (
                        assignments
                    ),

                    "ground_truth_source": (
                        ground_truth_source
                    ),

                    "class_source": (
                        class_source
                    ),
                }
            )


    return matches


def vector_occurrences(
    package_root: Path,
    vector_id: str,
) -> list[dict[str, Any]]:

    occurrences = []


    for path in package_root.rglob(
        "*"
    ):

        if (
            not path.is_file()
            or
            path.suffix.lower()
            not in {
                ".yaml",
                ".yml",
                ".py",
                ".json",
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
                line_number - 10,
            )

            end = min(
                len(lines),
                line_number + 10,
            )


            context_lines = lines[
                start - 1:end
            ]

            context = "\n".join(
                context_lines
            )


            locator_hints = sorted(
                {
                    match.group(1).rstrip(
                        ".,);"
                    )
                    for match in LOCATOR_PATTERN.finditer(
                        context
                    )
                }
            )


            yaml_key_hints = []

            for nearby_line in context_lines:

                key_match = re.match(
                    r"""
                    ^\s*
                    ["']?
                    ([^"'#:]+?)
                    ["']?
                    \s*:
                    """,
                    nearby_line,
                    re.VERBOSE,
                )

                if key_match:

                    key = key_match.group(1).strip()

                    if (
                        key
                        and
                        len(key) <= 120
                    ):
                        yaml_key_hints.append(
                            key
                        )


            occurrences.append(
                {
                    "source_file": str(
                        path.resolve()
                    ),

                    "line_number": line_number,

                    "line_text": line,

                    "context": context,

                    "locator_hints": (
                        locator_hints
                    ),

                    "yaml_key_hints": sorted(
                        set(
                            yaml_key_hints
                        )
                    ),
                }
            )


    return occurrences


def task_locator_literals(
    task_matches: list[dict[str, Any]],
    user_goal: str,
) -> list[str]:

    values = set()


    for match in LOCATOR_PATTERN.finditer(
        user_goal
    ):
        values.add(
            match.group(1).rstrip(
                ".,);"
            )
        )


    for task_match in task_matches:

        for assignment in task_match[
            "assignments"
        ]:

            value = assignment[
                "literal_value"
            ]


            if isinstance(
                value,
                str,
            ):

                if (
                    LOCATOR_PATTERN.fullmatch(
                        value
                    )
                    or
                    any(
                        token in assignment[
                            "name"
                        ].upper()
                        for token in [
                            "URL",
                            "FILE",
                            "FILENAME",
                            "EMAIL",
                            "SENDER",
                            "SUBJECT",
                            "QUERY",
                            "TOPIC",
                            "HOTEL",
                            "RESTAURANT",
                        ]
                    )
                ):
                    values.add(
                        value
                    )


    return sorted(
        values
    )


def vector_candidate_catalog(
    pairs: list[dict[str, Any]],
    current_pair: dict[str, Any],
    task_literals: list[str],
) -> list[dict[str, Any]]:

    suite = str(
        current_pair[
            "suite"
        ]
    )

    current_surface = current_pair[
        "injection_surface"
    ]

    current_vector = str(
        current_surface[
            "vector_id"
        ]
    )


    candidates_by_vector = {}


    for pair in pairs:

        if str(
            pair[
                "suite"
            ]
        ) != suite:
            continue


        surface = pair[
            "injection_surface"
        ]

        vector_id = str(
            surface[
                "vector_id"
            ]
        )

        if vector_id == current_vector:
            continue


        binding = pair.get(
            "context_bindings",
            {},
        )

        locator = (
            binding.get(
                "retrieved_object_locator"
            )
            or
            surface.get(
                "source_locator"
            )
        )


        location_text = canonical_json(
            surface.get(
                "environment_locations",
                [],
            )
        ).lower()


        score = 0
        reasons = []


        if (
            surface.get(
                "surface_type"
            )
            ==
            current_surface.get(
                "surface_type"
            )
        ):
            score += 3
            reasons.append(
                "same_surface_type"
            )


        if (
            surface.get(
                "source_type"
            )
            ==
            current_surface.get(
                "source_type"
            )
        ):
            score += 3
            reasons.append(
                "same_source_type"
            )


        if (
            surface.get(
                "retrieval_channel"
            )
            ==
            current_surface.get(
                "retrieval_channel"
            )
        ):
            score += 3
            reasons.append(
                "same_retrieval_channel"
            )


        if locator:
            score += 1
            reasons.append(
                "has_concrete_locator"
            )


        matching_literals = []

        for literal in task_literals:

            if (
                literal
                and
                literal.lower()
                in location_text
            ):
                score += 5

                matching_literals.append(
                    literal
                )


        if matching_literals:
            reasons.append(
                "task_literal_matches_environment"
            )


        candidate = {
            "vector_id": vector_id,

            "score": score,

            "reasons": reasons,

            "matching_task_literals": (
                matching_literals
            ),

            "source_locator": locator,

            "surface_type": surface.get(
                "surface_type"
            ),

            "source_type": surface.get(
                "source_type"
            ),

            "retrieval_channel": surface.get(
                "retrieval_channel"
            ),

            "environment_locations": surface.get(
                "environment_locations",
                [],
            ),

            "observed_in_pair_id": pair[
                "pair_id"
            ],
        }


        previous = candidates_by_vector.get(
            vector_id
        )

        if (
            previous is None
            or
            candidate[
                "score"
            ]
            >
            previous[
                "score"
            ]
        ):
            candidates_by_vector[
                vector_id
            ] = candidate


    candidates = list(
        candidates_by_vector.values()
    )

    candidates.sort(
        key=lambda candidate: (
            -candidate[
                "score"
            ],
            candidate[
                "vector_id"
            ],
        )
    )

    return candidates[:20]


def compact_task_match(
    match: dict[str, Any],
) -> dict[str, Any]:

    return {
        "source_file": match[
            "source_file"
        ],

        "class_name": match[
            "class_name"
        ],

        "class_start_line": match[
            "class_start_line"
        ],

        "class_end_line": match[
            "class_end_line"
        ],

        "assignments": match[
            "assignments"
        ],

        "ground_truth_source": match[
            "ground_truth_source"
        ],
    }


def main() -> None:

    inventory = load_jsonl(
        INVENTORY_PATH
    )

    pairs = load_jsonl(
        PAIR_PLAN_PATH
    )

    package_root = resolve_agentdojo_root()


    pair_by_id = {
        str(
            pair[
                "pair_id"
            ]
        ): pair
        for pair in pairs
    }


    target_inventory = [
        row
        for row in inventory
        if row.get(
            "issue_category"
        )
        in TARGET_ISSUES
    ]


    if (
        len(target_inventory)
        !=
        EXPECTED_PAIR_COUNT
    ):
        raise ValueError(
            "Expected 9 deterministic P2 pairs, "
            f"found {len(target_inventory)}."
        )


    dossiers = []


    for inventory_row in target_inventory:

        pair_id = str(
            inventory_row[
                "pair_id"
            ]
        )

        pair = pair_by_id[
            pair_id
        ]

        legitimate = pair[
            "legitimate_context"
        ]

        attacker = pair[
            "attacker_context"
        ]

        surface = pair[
            "injection_surface"
        ]

        selected = pair[
            "selected_actions"
        ]


        legitimate_id = structure_id(
            legitimate
        )


        task_matches = task_source_matches(
            package_root,
            str(
                pair[
                    "suite"
                ]
            ),
            legitimate_id,
        )


        task_literals = task_locator_literals(
            task_matches,
            str(
                legitimate.get(
                    "prompt_or_goal",
                    "",
                )
            ),
        )


        occurrences = vector_occurrences(
            package_root,
            str(
                surface[
                    "vector_id"
                ]
            ),
        )


        candidates = vector_candidate_catalog(
            pairs,
            pair,
            task_literals,
        )


        dossier = {
            "pair_id": pair_id,

            "priority": "P2",

            "issue_category": inventory_row.get(
                "issue_category"
            ),

            "review_note": inventory_row.get(
                "review_note"
            ),

            "suite": pair[
                "suite"
            ],

            "legitimate_structure_id": (
                legitimate_id
            ),

            "attacker_structure_id": (
                structure_id(
                    attacker
                )
            ),

            "vector_id": surface[
                "vector_id"
            ],

            "user_goal": legitimate.get(
                "prompt_or_goal"
            ),

            "attacker_goal": attacker.get(
                "prompt_or_goal"
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

            "current_context_bindings": pair.get(
                "context_bindings",
                {},
            ),

            "current_environment_locations": (
                surface.get(
                    "environment_locations",
                    [],
                )
            ),

            "task_locator_literals": (
                task_literals
            ),

            "task_source_matches": [
                compact_task_match(
                    match
                )
                for match in task_matches
            ],

            "current_vector_source_occurrences": (
                occurrences
            ),

            "candidate_replacement_vectors": (
                candidates
            ),

            "repair_decision": None,

            "repair_note": None,
        }


        dossiers.append(
            dossier
        )


    dossiers.sort(
        key=lambda dossier: dossier[
            "pair_id"
        ]
    )


    write_jsonl(
        OUTPUT_JSONL_PATH,
        dossiers,
    )


    lines = [
        "=" * 100,

        (
            "AGENTDOJO P2 DETERMINISTIC REPAIR "
            "DOSSIER v0.1.2"
        ),

        "=" * 100,

        "",

        f"AgentDojo source root: {package_root}",

        f"Pairs: {len(dossiers)}",

        "",
    ]


    for dossier in dossiers:

        lines.extend(
            [
                "=" * 120,

                f"PAIR: {dossier['pair_id']}",

                (
                    "ISSUE: "
                    f"{dossier['issue_category']}"
                ),

                (
                    "REVIEW NOTE: "
                    f"{dossier['review_note']}"
                ),

                (
                    "SUITE: "
                    f"{dossier['suite']}"
                ),

                "",

                (
                    "USER STRUCTURE: "
                    f"{dossier['legitimate_structure_id']}"
                ),

                (
                    "ATTACKER STRUCTURE: "
                    f"{dossier['attacker_structure_id']}"
                ),

                (
                    "CURRENT VECTOR: "
                    f"{dossier['vector_id']}"
                ),

                "",

                "USER GOAL:",

                str(
                    dossier[
                        "user_goal"
                    ]
                ),

                "",

                "ATTACKER GOAL:",

                str(
                    dossier[
                        "attacker_goal"
                    ]
                ),

                "",

                (
                    "SAFE ACTION: "
                    f"{canonical_json(dossier['safe_action'])}"
                ),

                (
                    "RISKY ACTION: "
                    f"{canonical_json(dossier['risky_action'])}"
                ),

                "",

                "TASK LOCATOR LITERALS:",

                canonical_json(
                    dossier[
                        "task_locator_literals"
                    ]
                ),

                "",

                "TASK CONSTANTS:",
            ]
        )


        if not dossier[
            "task_source_matches"
        ]:

            lines.append(
                "  <no task source match>"
            )


        for match in dossier[
            "task_source_matches"
        ]:

            lines.append(
                "  SOURCE: "
                f"{match['source_file']} "
                f"class={match['class_name']}"
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


            lines.append(
                "  GROUND TRUTH:"
            )

            lines.append(
                str(
                    match[
                        "ground_truth_source"
                    ]
                )
            )


        lines.extend(
            [
                "",

                "CURRENT VECTOR OCCURRENCES:",
            ]
        )


        if not dossier[
            "current_vector_source_occurrences"
        ]:

            lines.append(
                "  <no occurrence found>"
            )


        for occurrence in dossier[
            "current_vector_source_occurrences"
        ]:

            lines.append(
                "  "
                f"{occurrence['source_file']}:"
                f"{occurrence['line_number']}"
            )

            lines.append(
                "  LOCATOR HINTS: "
                f"{canonical_json(occurrence['locator_hints'])}"
            )

            lines.append(
                "  YAML KEY HINTS: "
                f"{canonical_json(occurrence['yaml_key_hints'])}"
            )

            lines.append(
                occurrence[
                    "context"
                ]
            )


        lines.extend(
            [
                "",

                "TOP REPLACEMENT VECTOR CANDIDATES:",
            ]
        )


        for candidate in dossier[
            "candidate_replacement_vectors"
        ][:10]:

            lines.append(
                "  "
                f"score={candidate['score']} "
                f"vector={candidate['vector_id']} "
                f"locator={candidate['source_locator']} "
                f"reasons={candidate['reasons']} "
                f"literal_matches="
                f"{candidate['matching_task_literals']}"
            )


        lines.append("")


    OUTPUT_TEXT_PATH.write_text(
        "\n".join(
            lines
        ),
        encoding="utf-8",
    )


    issue_counts = Counter(
        dossier[
            "issue_category"
        ]
        for dossier in dossiers
    )


    report = {
        "artifact_version": "0.1.2",

        "agentdojo_source_root": str(
            package_root
        ),

        "pair_count": len(
            dossiers
        ),

        "issue_counts": dict(
            issue_counts
        ),

        "pair_ids": [
            dossier[
                "pair_id"
            ]
            for dossier in dossiers
        ],

        "jsonl_dossier": str(
            OUTPUT_JSONL_PATH
        ),

        "text_dossier": str(
            OUTPUT_TEXT_PATH
        ),

        "pair_plan_modified": False,

        "labeled_pool_modified": False,

        "review_decisions_modified": False,
    }


    OUTPUT_REPORT_PATH.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


    print("=" * 80)
    print(
        "AGENTDOJO P2 DETERMINISTIC REPAIR "
        "DOSSIER v0.1.2 CREATED"
    )
    print("=" * 80)

    print()
    print(
        "AgentDojo root:",
        package_root,
    )

    print(
        "Pairs:",
        len(dossiers),
    )

    print()
    print("Issue counts:")

    for issue, count in sorted(
        issue_counts.items()
    ):
        print(
            f"  {issue}: {count}"
        )

    print()
    print("Pairs:")

    for dossier in dossiers:
        print(
            "  "
            f"{dossier['pair_id']} | "
            f"{dossier['suite']} | "
            f"{dossier['issue_category']} | "
            f"task literals="
            f"{dossier['task_locator_literals']}"
        )

    print()
    print(
        f"JSONL dossier: {OUTPUT_JSONL_PATH}"
    )

    print(
        f"Text dossier: {OUTPUT_TEXT_PATH}"
    )

    print(
        f"Report: {OUTPUT_REPORT_PATH}"
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


if __name__ == "__main__":
    main()

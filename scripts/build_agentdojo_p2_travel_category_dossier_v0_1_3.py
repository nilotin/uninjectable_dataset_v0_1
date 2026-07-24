from __future__ import annotations

import ast
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterator


INVENTORY_PATH = Path(
    "data/interim/"
    "agentdojo_p2_revision_inventory_v0.1.2.jsonl"
)

PAIR_PLAN_PATH = Path(
    "data/interim/"
    "agentdojo_contextual_pair_plan_v0.1.3_"
    "p2_deterministic_repaired.jsonl"
)

BLUEPRINT_POOL_PATH = Path(
    "data/processed/"
    "agentdojo_contextual_composition_blueprint_pool_v0.1.jsonl"
)

OUTPUT_JSONL_PATH = Path(
    "data/interim/"
    "agentdojo_p2_travel_category_dossier_v0.1.3.jsonl"
)

OUTPUT_TEXT_PATH = Path(
    "data/interim/"
    "agentdojo_p2_travel_category_dossier_v0.1.3.txt"
)

OUTPUT_REPORT_PATH = Path(
    "data/interim/"
    "agentdojo_p2_travel_category_dossier_v0.1.3_report.json"
)


EXPECTED_PAIR_COUNT = 14

CATEGORY_KEYWORDS = {
    "hotel": {
        "hotel",
        "hotels",
        "accommodation",
        "lodging",
        "room",
        "rooms",
    },

    "restaurant": {
        "restaurant",
        "restaurants",
        "dining",
        "cuisine",
        "food",
        "meal",
    },

    "flight": {
        "flight",
        "flights",
        "airline",
        "airport",
        "departure",
        "arrival",
    },

    "car_rental": {
        "car rental",
        "rental car",
        "vehicle rental",
        "rent a car",
        "car-rental",
        "car_rental",
    },
}


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

            Path.cwd().parent
            / "agentdojo/src/agentdojo",
        ]
    )

    for candidate in candidates:

        candidate = candidate.resolve()

        if (
            candidate.is_dir()
            and
            (
                candidate / "default_suites"
            ).exists()
        ):
            return candidate

        nested_candidate = (
            candidate
            / "src"
            / "agentdojo"
        )

        if (
            nested_candidate.is_dir()
            and
            (
                nested_candidate
                / "default_suites"
            ).exists()
        ):
            return nested_candidate.resolve()

    raise FileNotFoundError(
        "Could not locate the AgentDojo source root."
    )


def class_name_from_structure(
    value: str,
) -> str | None:

    match = re.search(
        r"_user_task_(\d+)$",
        value,
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


def extract_function_calls(
    function_source: str | None,
) -> list[str]:

    if not function_source:
        return []

    return re.findall(
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
        function_source,
        re.VERBOSE,
    )


def find_task_sources(
    package_root: Path,
    structure: str,
) -> list[dict[str, Any]]:

    target_class = class_name_from_structure(
        structure
    )

    if target_class is None:
        return []

    matches = []

    for path in package_root.rglob(
        "user_tasks.py"
    ):

        if "travel" not in path.parts:
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
            ground_truth_source = None

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

                            "literal_value": literal_value(
                                value_node
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

                    "ground_truth_source": (
                        ground_truth_source
                    ),

                    "ground_truth_tools": (
                        extract_function_calls(
                            ground_truth_source
                        )
                    ),
                }
            )

    return matches


def vector_occurrences(
    package_root: Path,
    vector_id: str,
) -> list[dict[str, Any]]:

    occurrences = []

    for path in package_root.rglob("*"):

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
                line_number - 18,
            )

            end = min(
                len(lines),
                line_number + 18,
            )

            context = "\n".join(
                lines[start - 1:end]
            )

            occurrences.append(
                {
                    "source_file": str(
                        path.resolve()
                    ),

                    "line_number": line_number,

                    "line_text": line,

                    "context": context,
                }
            )

    return occurrences


def detect_categories(
    value: Any,
) -> list[str]:

    text = canonical_json(
        value
    ).lower()

    detected = []

    for category, keywords in (
        CATEGORY_KEYWORDS.items()
    ):

        if any(
            keyword in text
            for keyword in keywords
        ):
            detected.append(
                category
            )

    return sorted(
        detected
    )


def walk_dicts(
    value: Any,
) -> Iterator[dict[str, Any]]:

    if isinstance(value, dict):

        yield value

        for child in value.values():
            yield from walk_dicts(
                child
            )

    elif isinstance(value, list):

        for child in value:
            yield from walk_dicts(
                child
            )


def surface_quality(
    surface: dict[str, Any],
) -> int:

    score = 0

    for key in [
        "surface_type",
        "source_type",
        "retrieval_channel",
        "trust_level",
    ]:

        if surface.get(key) is not None:
            score += 5

    if surface.get(
        "environment_locations"
    ):
        score += 10

    if "default_value" in surface:
        score += 3

    return score


def build_vector_catalog(
    pairs: list[dict[str, Any]],
    blueprints: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:

    catalog = {}
    quality_by_vector = {}
    observed_pairs: dict[
        str,
        set[str],
    ] = defaultdict(set)

    for pair in pairs:

        surface = pair.get(
            "injection_surface",
            {},
        )

        vector_id = surface.get(
            "vector_id"
        )

        if vector_id:

            observed_pairs[
                str(vector_id)
            ].add(
                str(pair["pair_id"])
            )

    for record in [
        *pairs,
        *blueprints,
    ]:

        for candidate in walk_dicts(
            record
        ):

            vector_id = candidate.get(
                "vector_id"
            )

            if not vector_id:
                continue

            if not any(
                key in candidate
                for key in [
                    "surface_type",
                    "source_type",
                    "retrieval_channel",
                    "environment_locations",
                ]
            ):
                continue

            vector_id = str(
                vector_id
            )

            quality = surface_quality(
                candidate
            )

            if (
                vector_id not in catalog
                or
                quality
                >
                quality_by_vector[
                    vector_id
                ]
            ):

                catalog[
                    vector_id
                ] = dict(
                    candidate
                )

                quality_by_vector[
                    vector_id
                ] = quality

    for vector_id, surface in (
        catalog.items()
    ):

        surface[
            "_observed_pair_ids"
        ] = sorted(
            observed_pairs.get(
                vector_id,
                set(),
            )
        )

    return catalog


def candidate_score(
    current_surface: dict[str, Any],
    candidate_surface: dict[str, Any],
    legitimate_categories: list[str],
) -> tuple[int, list[str]]:

    score = 0
    reasons = []

    candidate_categories = detect_categories(
        candidate_surface
    )

    category_overlap = sorted(
        set(
            legitimate_categories
        )
        &
        set(
            candidate_categories
        )
    )

    if category_overlap:

        score += (
            10
            *
            len(
                category_overlap
            )
        )

        reasons.append(
            "object_category_overlap="
            +
            ",".join(
                category_overlap
            )
        )

    for field in [
        "surface_type",
        "source_type",
        "retrieval_channel",
    ]:

        if (
            candidate_surface.get(field)
            ==
            current_surface.get(field)
        ):

            score += 3

            reasons.append(
                f"same_{field}"
            )

    if candidate_surface.get(
        "environment_locations"
    ):

        score += 1

        reasons.append(
            "has_environment_evidence"
        )

    return score, reasons


def main() -> None:

    inventory = load_jsonl(
        INVENTORY_PATH
    )

    pairs = load_jsonl(
        PAIR_PLAN_PATH
    )

    blueprints = (
        load_jsonl(
            BLUEPRINT_POOL_PATH
        )
        if BLUEPRINT_POOL_PATH.exists()
        else []
    )

    package_root = resolve_agentdojo_root()

    pair_by_id = {
        str(pair["pair_id"]): pair
        for pair in pairs
    }

    target_inventory = [
        row
        for row in inventory
        if (
            row.get(
                "suite"
            )
            ==
            "travel"
            and
            row.get(
                "issue_category"
            )
            ==
            "review_object_category_mismatch"
        )
    ]

    if (
        len(target_inventory)
        !=
        EXPECTED_PAIR_COUNT
    ):

        raise ValueError(
            "Expected 14 travel category-mismatch "
            f"pairs, found {len(target_inventory)}."
        )

    vector_catalog = build_vector_catalog(
        pairs,
        blueprints,
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

        task_sources = find_task_sources(
            package_root,
            legitimate_id,
        )

        legitimate_category_payload = {
            "user_goal": legitimate.get(
                "prompt_or_goal"
            ),

            "scenario_family": legitimate.get(
                "scenario_family"
            ),

            "safe_action": selected.get(
                "authorized_user_action"
            ),

            "task_sources": task_sources,
        }

        legitimate_categories = (
            detect_categories(
                legitimate_category_payload
            )
        )

        current_occurrences = (
            vector_occurrences(
                package_root,
                str(
                    surface[
                        "vector_id"
                    ]
                ),
            )
        )

        current_category_payload = {
            "surface": surface,
            "occurrences": current_occurrences,
        }

        current_categories = (
            detect_categories(
                current_category_payload
            )
        )

        candidates = []

        for vector_id, candidate_surface in (
            vector_catalog.items()
        ):

            if vector_id == surface[
                "vector_id"
            ]:
                continue

            candidate_suite_text = (
                canonical_json(
                    candidate_surface
                ).lower()
            )

            if "travel" not in candidate_suite_text:

                observed_pair_ids = (
                    candidate_surface.get(
                        "_observed_pair_ids",
                        [],
                    )
                )

                if not any(
                    pair_by_id.get(
                        observed_pair_id,
                        {},
                    ).get(
                        "suite"
                    )
                    ==
                    "travel"
                    for observed_pair_id
                    in observed_pair_ids
                ):
                    continue

            score, reasons = (
                candidate_score(
                    surface,
                    candidate_surface,
                    legitimate_categories,
                )
            )

            candidates.append(
                {
                    "vector_id": vector_id,

                    "score": score,

                    "reasons": reasons,

                    "detected_categories": (
                        detect_categories(
                            candidate_surface
                        )
                    ),

                    "surface_type": (
                        candidate_surface.get(
                            "surface_type"
                        )
                    ),

                    "source_type": (
                        candidate_surface.get(
                            "source_type"
                        )
                    ),

                    "retrieval_channel": (
                        candidate_surface.get(
                            "retrieval_channel"
                        )
                    ),

                    "environment_locations": (
                        candidate_surface.get(
                            "environment_locations",
                            [],
                        )
                    ),

                    "observed_pair_ids": (
                        candidate_surface.get(
                            "_observed_pair_ids",
                            [],
                        )
                    ),
                }
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

        dossiers.append(
            {
                "pair_id": pair_id,

                "issue_category": (
                    "review_object_category_mismatch"
                ),

                "review_note": (
                    inventory_row.get(
                        "review_note"
                    )
                ),

                "legitimate_structure_id": (
                    legitimate_id
                ),

                "attacker_structure_id": (
                    structure_id(
                        attacker
                    )
                ),

                "user_goal": legitimate.get(
                    "prompt_or_goal"
                ),

                "scenario_family": legitimate.get(
                    "scenario_family"
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

                "legitimate_object_categories": (
                    legitimate_categories
                ),

                "current_vector_id": surface[
                    "vector_id"
                ],

                "current_vector_object_categories": (
                    current_categories
                ),

                "current_surface": surface,

                "task_source_matches": (
                    task_sources
                ),

                "current_vector_occurrences": (
                    current_occurrences
                ),

                "top_replacement_candidates": (
                    candidates[:15]
                ),

                "repair_decision": None,

                "repair_note": None,
            }
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
            "AGENTDOJO P2 TRAVEL CATEGORY "
            "DOSSIER v0.1.3"
        ),

        "=" * 100,

        "",

        f"AgentDojo source root: {package_root}",

        f"Pairs: {len(dossiers)}",

        "",

        (
            "NOTE: Category detection and candidate "
            "scores are diagnostic heuristics only."
        ),

        "",
    ]

    for dossier in dossiers:

        lines.extend(
            [
                "=" * 120,

                f"PAIR: {dossier['pair_id']}",

                (
                    "REVIEW NOTE: "
                    f"{dossier['review_note']}"
                ),

                "",

                (
                    "LEGITIMATE STRUCTURE: "
                    f"{dossier['legitimate_structure_id']}"
                ),

                (
                    "ATTACKER STRUCTURE: "
                    f"{dossier['attacker_structure_id']}"
                ),

                "",

                "USER GOAL:",

                str(
                    dossier[
                        "user_goal"
                    ]
                ),

                "",

                (
                    "SCENARIO FAMILY: "
                    f"{dossier['scenario_family']}"
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

                (
                    "LEGITIMATE OBJECT CATEGORIES: "
                    f"{dossier['legitimate_object_categories']}"
                ),

                (
                    "CURRENT VECTOR: "
                    f"{dossier['current_vector_id']}"
                ),

                (
                    "CURRENT VECTOR OBJECT CATEGORIES: "
                    f"{dossier['current_vector_object_categories']}"
                ),

                "",

                "TASK SOURCE:",
            ]
        )

        for task_source in dossier[
            "task_source_matches"
        ]:

            lines.append(
                "  "
                f"{task_source['source_file']} "
                f"class={task_source['class_name']} "
                f"lines="
                f"{task_source['class_start_line']}-"
                f"{task_source['class_end_line']}"
            )

            lines.append(
                "  GROUND-TRUTH TOOLS: "
                f"{task_source['ground_truth_tools']}"
            )

            for assignment in task_source[
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
                    task_source[
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

        for occurrence in dossier[
            "current_vector_occurrences"
        ]:

            lines.append(
                "  "
                f"{occurrence['source_file']}:"
                f"{occurrence['line_number']}"
            )

            lines.append(
                occurrence[
                    "context"
                ]
            )

        lines.extend(
            [
                "",

                "TOP REPLACEMENT CANDIDATES:",
            ]
        )

        for candidate in dossier[
            "top_replacement_candidates"
        ]:

            lines.append(
                "  "
                f"score={candidate['score']} "
                f"vector={candidate['vector_id']} "
                f"categories="
                f"{candidate['detected_categories']} "
                f"reasons={candidate['reasons']} "
                f"observed_pairs="
                f"{candidate['observed_pair_ids']}"
            )

        lines.append("")

    OUTPUT_TEXT_PATH.write_text(
        "\n".join(
            lines
        ),
        encoding="utf-8",
    )

    legitimate_category_counts = Counter()

    current_category_counts = Counter()

    for dossier in dossiers:

        for category in dossier[
            "legitimate_object_categories"
        ]:

            legitimate_category_counts[
                category
            ] += 1

        for category in dossier[
            "current_vector_object_categories"
        ]:

            current_category_counts[
                category
            ] += 1

    report = {
        "artifact_version": "0.1.3",

        "agentdojo_source_root": str(
            package_root
        ),

        "pair_count": len(
            dossiers
        ),

        "pair_ids": [
            dossier[
                "pair_id"
            ]
            for dossier in dossiers
        ],

        "legitimate_category_counts": dict(
            legitimate_category_counts
        ),

        "current_vector_category_counts": dict(
            current_category_counts
        ),

        "jsonl_dossier": str(
            OUTPUT_JSONL_PATH
        ),

        "text_dossier": str(
            OUTPUT_TEXT_PATH
        ),

        "pair_plan_modified": False,

        "labeled_pool_modified": False,

        "review_decisions_modified": False,

        "final_labels_modified": False,
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
        "AGENTDOJO P2 TRAVEL CATEGORY "
        "DOSSIER v0.1.3 CREATED"
    )
    print("=" * 80)

    print()
    print(
        "AgentDojo root:",
        package_root,
    )

    print(
        "Travel mismatch pairs:",
        len(dossiers),
    )

    print()
    print(
        "Legitimate category counts:",
        dict(
            legitimate_category_counts
        ),
    )

    print(
        "Current vector category counts:",
        dict(
            current_category_counts
        ),
    )

    print()
    print("Pairs:")

    for dossier in dossiers:

        print(
            "  "
            f"{dossier['pair_id']} | "
            f"legitimate="
            f"{dossier['legitimate_object_categories']} | "
            f"current="
            f"{dossier['current_vector_object_categories']} | "
            f"vector="
            f"{dossier['current_vector_id']}"
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

    print(
        "Final labels modified: no"
    )


if __name__ == "__main__":
    main()

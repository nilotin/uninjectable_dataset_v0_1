from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as error:
    raise SystemExit(
        "PyYAML is required. Install with: pip install pyyaml"
    ) from error


PAIR_PATH = Path(
    "data/interim/"
    "agentdojo_contextual_pair_plan_v0.1.jsonl"
)

BLUEPRINT_PATH = Path(
    "data/processed/"
    "agentdojo_contextual_composition_blueprint_pool_v0.1.jsonl"
)

OUTPUT_PATH = Path(
    "data/interim/"
    "agentdojo_p1_concrete_object_resolution_v0.1.1.json"
)


P1_PAIR_IDS = [
    "agentdojo_pair_016",
    "agentdojo_pair_031",
    "agentdojo_pair_040",
    "agentdojo_pair_091",
    "agentdojo_pair_095",
]


SOURCE_SEARCH_PHRASES = {
    "agentdojo_pair_091": (
        "Please send a summary of the file"
    ),

    "agentdojo_pair_095": (
        "Please do the actions specified in the email"
    ),
}


VECTOR_BINDING_PROPOSALS = {
    "agentdojo_pair_031": {
        "binding_type": (
            "parameterized_web_url_binding"
        ),

        "retrieved_object_locator": (
            "www.eve-blog.com"
        ),

        "parameter_bindings": {
            "URL": "www.eve-blog.com",
        },
    },

    "agentdojo_pair_040": {
        "binding_type": (
            "slack_message_url_binding"
        ),

        "retrieved_object_locator": (
            "www.true-informations.com"
        ),

        "parameter_bindings": {
            "retrieved_article_url": (
                "www.true-informations.com"
            ),
        },
    },
}


def load_jsonl(
    path: Path,
) -> list[dict[str, Any]]:

    if not path.exists():
        raise FileNotFoundError(
            f"Missing input: {path}"
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


def function_name(
    action: dict[str, Any],
) -> str:

    return str(
        action.get(
            "normalized_function_name"
        )
        or
        action.get(
            "function"
        )
        or
        action.get(
            "tool_name"
        )
        or
        ""
    )


def action_args(
    action: dict[str, Any],
) -> Any:

    if action.get(
        "args"
    ) is not None:
        return action[
            "args"
        ]

    return action.get(
        "args_expression"
    )


def target_action(
    blueprint: dict[str, Any],
) -> dict[str, Any] | None:

    actions = (
        blueprint.get(
            "action_semantics",
            {},
        ).get(
            "reference_action_sequence",
            [],
        )
    )

    if not actions:
        return None

    impact_rank = {
        "low": 1,
        "medium": 2,
        "high": 3,
    }

    def score(
        action: dict[str, Any],
    ) -> tuple[int, int]:

        metadata = action.get(
            "tool_metadata",
            {},
        )

        impact = (
            metadata.get(
                "action_impact"
            )
            or
            action.get(
                "action_impact"
            )
            or
            ""
        )

        position = int(
            action.get(
                "sequence_position",
                0,
            )
            or 0
        )

        return (
            impact_rank.get(
                str(impact),
                0,
            ),
            position,
        )

    return max(
        actions,
        key=score,
    )


def contains_token(
    value: Any,
    token: str,
) -> bool:

    if isinstance(
        value,
        str,
    ):
        return token in value

    if isinstance(
        value,
        dict,
    ):
        return any(
            contains_token(
                child,
                token,
            )
            for child in value.values()
        )

    if isinstance(
        value,
        list,
    ):
        return any(
            contains_token(
                child,
                token,
            )
            for child in value
        )

    return False


def directly_contains_token(
    value: dict[str, Any],
    token: str,
) -> bool:

    for child in value.values():

        if isinstance(
            child,
            str,
        ) and token in child:
            return True

    return False


def find_token_objects(
    value: Any,
    token: str,
    path: str = "root",
) -> list[dict[str, Any]]:

    matches: list[
        dict[str, Any]
    ] = []

    if isinstance(
        value,
        dict,
    ):

        if directly_contains_token(
            value,
            token,
        ):
            matches.append(
                {
                    "yaml_path": path,
                    "object": value,
                }
            )

        for key, child in value.items():

            matches.extend(
                find_token_objects(
                    child,
                    token,
                    f"{path}.{key}",
                )
            )

    elif isinstance(
        value,
        list,
    ):

        for index, child in enumerate(
            value
        ):

            matches.extend(
                find_token_objects(
                    child,
                    token,
                    f"{path}[{index}]",
                )
            )

    return matches


def compact_object(
    value: dict[str, Any],
) -> dict[str, Any]:

    result = {}

    for key, child in value.items():

        if isinstance(
            child,
            str,
        ):

            if len(child) > 1200:
                result[key] = (
                    child[:1200]
                    +
                    "... [TRUNCATED]"
                )
            else:
                result[key] = child

        elif isinstance(
            child,
            (
                int,
                float,
                bool,
            ),
        ) or child is None:
            result[key] = child

        elif isinstance(
            child,
            list,
        ):

            if all(
                isinstance(
                    item,
                    (
                        str,
                        int,
                        float,
                        bool,
                    ),
                )
                or item is None
                for item in child
            ):
                result[key] = child

            else:
                result[key] = (
                    f"<complex list: "
                    f"{len(child)} items>"
                )

        elif isinstance(
            child,
            dict,
        ):
            result[key] = (
                f"<nested object: "
                f"{len(child)} keys>"
            )

    return result


def resolve_source_path(
    path_value: str,
) -> Path:

    import importlib.util
    import os

    requested = Path(
        path_value
    )

    requested_parts = tuple(
        part
        for part in requested.parts
        if part not in {
            "",
            ".",
        }
    )

    normalized = Path(
        *requested_parts
    )

    candidates: list[Path] = []


    def add_candidate(
        candidate: Path,
    ) -> None:

        candidate = candidate.expanduser()

        if candidate not in candidates:
            candidates.append(
                candidate
            )


    # Original and project-relative locations.
    if requested.is_absolute():
        add_candidate(
            requested
        )

    add_candidate(
        Path.cwd()
        /
        normalized
    )

    add_candidate(
        Path.cwd()
        /
        "agentdojo"
        /
        normalized
    )


    # Convert:
    # src/agentdojo/data/... -> data/...
    package_tail: Path | None = None

    parts = normalized.parts

    for index in range(
        max(
            0,
            len(parts) - 1,
        )
    ):

        if (
            parts[index] == "src"
            and
            parts[index + 1] == "agentdojo"
        ):

            package_tail = Path(
                *parts[
                    index + 2:
                ]
            )

            break


    if package_tail is not None:

        add_candidate(
            Path.cwd()
            /
            package_tail
        )

        add_candidate(
            Path.cwd()
            /
            "agentdojo"
            /
            package_tail
        )

        add_candidate(
            Path.cwd()
            /
            "src"
            /
            "agentdojo"
            /
            package_tail
        )


        # Resolve an installed AgentDojo package.
        spec = importlib.util.find_spec(
            "agentdojo"
        )

        if (
            spec is not None
            and
            spec.origin is not None
        ):

            package_dir = Path(
                spec.origin
            ).resolve().parent

            add_candidate(
                package_dir
                /
                package_tail
            )

            add_candidate(
                package_dir.parent
                /
                "src"
                /
                "agentdojo"
                /
                package_tail
            )


    # Optional manually configured AgentDojo root.
    configured_root = os.environ.get(
        "AGENTDOJO_ROOT"
    )

    if configured_root:

        root = Path(
            configured_root
        ).expanduser()

        add_candidate(
            root
            /
            normalized
        )

        if package_tail is not None:

            add_candidate(
                root
                /
                package_tail
            )

            add_candidate(
                root
                /
                "src"
                /
                "agentdojo"
                /
                package_tail
            )


    for candidate in candidates:

        if candidate.is_file():
            return candidate.resolve()


    # Search the dataset repository and nearby sibling repositories.
    suffixes = {
        normalized.as_posix(),
    }

    if package_tail is not None:

        suffixes.add(
            package_tail.as_posix()
        )

        suffixes.add(
            (
                Path("src")
                /
                "agentdojo"
                /
                package_tail
            ).as_posix()
        )


    search_roots = [
        Path.cwd(),
        Path.cwd().parent,
    ]

    filename = normalized.name

    for root in search_roots:

        if not root.exists():
            continue

        for candidate in root.rglob(
            filename
        ):

            if not candidate.is_file():
                continue

            candidate_text = (
                candidate
                .resolve()
                .as_posix()
            )

            if any(
                candidate_text.endswith(
                    suffix
                )
                for suffix in suffixes
            ):
                return candidate.resolve()


    attempted = "\n".join(
        f"  - {candidate}"
        for candidate in candidates
    )

    raise FileNotFoundError(
        "Could not resolve AgentDojo source file:\n"
        f"  requested: {path_value}\n"
        "Attempted locations:\n"
        f"{attempted}\n\n"
        "AgentDojo may not be installed or cloned locally. "
        "Set AGENTDOJO_ROOT to the AgentDojo repository root "
        "and run the script again."
    )


def parse_literal_assignments(
    source_text: str,
) -> dict[str, Any]:

    assignments: dict[
        str,
        Any,
    ] = {}

    try:
        tree = ast.parse(
            source_text
        )
    except SyntaxError:
        return assignments

    for node in ast.walk(
        tree
    ):

        if not isinstance(
            node,
            (
                ast.Assign,
                ast.AnnAssign,
            ),
        ):
            continue

        if isinstance(
            node,
            ast.Assign,
        ):
            targets = node.targets
            value_node = node.value

        else:
            targets = [
                node.target
            ]
            value_node = node.value

        if value_node is None:
            continue

        try:
            literal_value = ast.literal_eval(
                value_node
            )
        except Exception:
            continue

        for target in targets:

            if isinstance(
                target,
                ast.Name,
            ):
                assignments[
                    target.id
                ] = literal_value

            elif isinstance(
                target,
                ast.Attribute,
            ):
                assignments[
                    target.attr
                ] = literal_value

    return assignments


def find_python_prompt_context(
    phrase: str,
) -> list[dict[str, Any]]:

    roots = [
        Path(
            "src/agentdojo"
        ),
        Path(
            "agentdojo/src/agentdojo"
        ),
    ]

    existing_roots = [
        root
        for root in roots
        if root.exists()
    ]

    if not existing_roots:
        return [
            {
                "error": (
                    "No src/agentdojo source tree "
                    "was found."
                )
            }
        ]

    matches = []

    for root in existing_roots:

        for path in root.rglob(
            "*.py"
        ):

            try:
                text = path.read_text(
                    encoding="utf-8"
                )
            except UnicodeDecodeError:
                continue

            if phrase not in text:
                continue

            lines = text.splitlines()

            matching_indices = [
                index
                for index, line in enumerate(
                    lines
                )
                if phrase in line
            ]

            for index in matching_indices:

                start = max(
                    0,
                    index - 70,
                )

                end = min(
                    len(lines),
                    index + 90,
                )

                snippet = "\n".join(
                    lines[
                        start:end
                    ]
                )

                matches.append(
                    {
                        "source_file": str(
                            path
                        ),

                        "matching_line": (
                            index + 1
                        ),

                        "snippet_start_line": (
                            start + 1
                        ),

                        "snippet_end_line": end,

                        "snippet": snippet,

                        "literal_assignments": (
                            parse_literal_assignments(
                                snippet
                            )
                        ),
                    }
                )

    return matches


def extract_attachment_file_ids(
    action: dict[str, Any],
) -> list[str]:

    text = str(
        action_args(
            action
        )
    )

    patterns = [
        r"""file_id['"]?\s*:\s*['"]([^'"]+)['"]""",
        r"""['"]file_id['"]\s*:\s*['"]([^'"]+)['"]""",
    ]

    values = []

    for pattern in patterns:

        values.extend(
            re.findall(
                pattern,
                text,
            )
        )

    return sorted(
        set(values)
    )


def object_value(
    value: dict[str, Any],
    keys: list[str],
) -> Any:

    for key in keys:

        if key in value:
            return value[
                key
            ]

    return None


def main() -> None:

    pairs = load_jsonl(
        PAIR_PATH
    )

    blueprints = load_jsonl(
        BLUEPRINT_PATH
    )


    pair_by_id = {
        str(
            pair[
                "pair_id"
            ]
        ): pair
        for pair in pairs
    }

    blueprint_by_structure_id = {
        str(
            blueprint[
                "structure"
            ][
                "structure_id"
            ]
        ): blueprint
        for blueprint in blueprints
    }


    missing_pairs = [
        pair_id
        for pair_id in P1_PAIR_IDS
        if pair_id not in pair_by_id
    ]

    if missing_pairs:
        raise ValueError(
            f"Missing P1 pairs: {missing_pairs}"
        )


    existing_triples = {
        (
            pair[
                "legitimate_context"
            ][
                "blueprint_id"
            ],

            pair[
                "attacker_context"
            ][
                "blueprint_id"
            ],

            pair[
                "injection_surface"
            ][
                "vector_id"
            ],
        )
        for pair in pairs
        if pair[
            "pair_id"
        ] != "agentdojo_pair_016"
    }


    results: dict[str, Any] = {}


    # --------------------------------------------------------
    # Pair 016: enumerate unique bill-text same-tool options
    # --------------------------------------------------------

    pair_016 = pair_by_id[
        "agentdojo_pair_016"
    ]

    user_blueprint_id = (
        pair_016[
            "legitimate_context"
        ][
            "blueprint_id"
        ]
    )

    current_attacker_id = (
        pair_016[
            "attacker_context"
        ][
            "structure_id"
        ]
    )

    bill_candidates = []


    for structure_id, blueprint in (
        blueprint_by_structure_id.items()
    ):

        if (
            blueprint.get(
                "suite"
            )
            !=
            "banking"
        ):
            continue

        if "_injection_task_" not in structure_id:
            continue

        action = target_action(
            blueprint
        )

        if action is None:
            continue

        if function_name(
            action
        ) != "send_money":
            continue

        triple = (
            user_blueprint_id,
            blueprint[
                "blueprint_id"
            ],
            "injection_bill_text",
        )

        bill_candidates.append(
            {
                "structure_id": structure_id,

                "prompt_or_goal": (
                    blueprint[
                        "structure"
                    ][
                        "prompt_or_goal"
                    ]
                ),

                "target_action": {
                    "tool_name": (
                        function_name(
                            action
                        )
                    ),

                    "args": (
                        action_args(
                            action
                        )
                    ),
                },

                "triple_already_used": (
                    triple in existing_triples
                ),

                "is_current_attacker": (
                    structure_id
                    ==
                    current_attacker_id
                ),
            }
        )


    bill_candidates.sort(
        key=lambda candidate: (
            candidate[
                "triple_already_used"
            ],
            candidate[
                "is_current_attacker"
            ],
            candidate[
                "structure_id"
            ],
        )
    )


    results[
        "agentdojo_pair_016"
    ] = {
        "repair_type": (
            "replace_vector_and_attacker_structure"
        ),

        "replacement_vector_id": (
            "injection_bill_text"
        ),

        "replacement_source_locator": (
            "bill-december-2023.txt"
        ),

        "candidate_attacker_structures": (
            bill_candidates
        ),
    }


    # --------------------------------------------------------
    # Pairs 031 and 040: fixed URL bindings
    # --------------------------------------------------------

    for pair_id in [
        "agentdojo_pair_031",
        "agentdojo_pair_040",
    ]:

        results[
            pair_id
        ] = {
            "repair_type": (
                "binding_only"
            ),

            "proposed_binding": (
                VECTOR_BINDING_PROPOSALS[
                    pair_id
                ]
            ),
        }


    # --------------------------------------------------------
    # Pairs 091 and 095: resolve enclosing YAML objects
    # --------------------------------------------------------

    for pair_id in [
        "agentdojo_pair_091",
        "agentdojo_pair_095",
    ]:

        pair = pair_by_id[
            pair_id
        ]

        surface = pair[
            "injection_surface"
        ]

        vector_id = str(
            surface[
                "vector_id"
            ]
        )

        placeholder = (
            "{"
            +
            vector_id
            +
            "}"
        )

        environment_locations = (
            surface.get(
                "environment_locations",
                []
            )
        )

        if not environment_locations:
            raise ValueError(
                f"No environment location for {pair_id}."
            )

        source_path = resolve_source_path(
            str(
                environment_locations[
                    0
                ][
                    "source_file"
                ]
            )
        )

        yaml_data = yaml.safe_load(
            source_path.read_text(
                encoding="utf-8"
            )
        )

        matching_objects = (
            find_token_objects(
                yaml_data,
                placeholder,
            )
        )

        compact_matches = [
            {
                "yaml_path": match[
                    "yaml_path"
                ],

                "object": compact_object(
                    match[
                        "object"
                    ]
                ),
            }
            for match in matching_objects
        ]


        user_structure_id = (
            pair[
                "legitimate_context"
            ][
                "structure_id"
            ]
        )

        user_blueprint = (
            blueprint_by_structure_id[
                user_structure_id
            ]
        )

        safe_action = (
            pair[
                "selected_actions"
            ][
                "authorized_user_action"
            ]
        )


        task_source_context = (
            find_python_prompt_context(
                SOURCE_SEARCH_PHRASES[
                    pair_id
                ]
            )
        )


        resolution = {
            "repair_type": (
                "binding_only_pending_identity_check"
            ),

            "vector_id": vector_id,

            "placeholder": placeholder,

            "environment_source_file": str(
                source_path
            ),

            "matching_environment_objects": (
                compact_matches
            ),

            "legitimate_structure_id": (
                user_structure_id
            ),

            "legitimate_blueprint_source": (
                user_blueprint[
                    "structure"
                ].get(
                    "source",
                    {},
                )
            ),

            "safe_action": {
                "tool_name": (
                    function_name(
                        safe_action
                    )
                ),

                "args": (
                    action_args(
                        safe_action
                    )
                ),
            },

            "task_source_context": (
                task_source_context
            ),
        }


        if pair_id == "agentdojo_pair_091":

            resolution[
                "safe_attachment_file_ids"
            ] = extract_attachment_file_ids(
                safe_action
            )

            resolved_files = []

            for match in matching_objects:

                object_data = match[
                    "object"
                ]

                resolved_files.append(
                    {
                        "yaml_path": (
                            match[
                                "yaml_path"
                            ]
                        ),

                        "file_id": object_value(
                            object_data,
                            [
                                "id",
                                "file_id",
                            ],
                        ),

                        "filename": object_value(
                            object_data,
                            [
                                "filename",
                                "name",
                                "title",
                            ],
                        ),

                        "owner": object_value(
                            object_data,
                            [
                                "owner",
                            ],
                        ),
                    }
                )

            resolution[
                "resolved_file_identity"
            ] = resolved_files


        if pair_id == "agentdojo_pair_095":

            resolved_emails = []

            for match in matching_objects:

                object_data = match[
                    "object"
                ]

                resolved_emails.append(
                    {
                        "yaml_path": (
                            match[
                                "yaml_path"
                            ]
                        ),

                        "email_id": object_value(
                            object_data,
                            [
                                "id",
                                "email_id",
                            ],
                        ),

                        "sender": object_value(
                            object_data,
                            [
                                "sender",
                                "from",
                            ],
                        ),

                        "subject": object_value(
                            object_data,
                            [
                                "subject",
                            ],
                        ),

                        "recipients": object_value(
                            object_data,
                            [
                                "recipients",
                                "to",
                            ],
                        ),

                        "status": object_value(
                            object_data,
                            [
                                "status",
                            ],
                        ),

                        "read": object_value(
                            object_data,
                            [
                                "read",
                            ],
                        ),
                    }
                )

            resolution[
                "resolved_email_identity"
            ] = resolved_emails


        results[
            pair_id
        ] = resolution


    OUTPUT_PATH.write_text(
        json.dumps(
            results,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


    print("=" * 80)
    print(
        "AGENTDOJO P1 CONCRETE OBJECT "
        "RESOLUTION v0.1.1 COMPLETE"
    )
    print("=" * 80)


    pair_016_result = results[
        "agentdojo_pair_016"
    ]

    print()
    print(
        "PAIR: agentdojo_pair_016"
    )

    print(
        "PROPOSED VECTOR:",
        pair_016_result[
            "replacement_vector_id"
        ],
    )

    print(
        "PROPOSED LOCATOR:",
        pair_016_result[
            "replacement_source_locator"
        ],
    )

    print(
        "UNUSED SAME-TOOL ATTACKER OPTIONS:"
    )

    unused_options = [
        candidate
        for candidate in pair_016_result[
            "candidate_attacker_structures"
        ]
        if not candidate[
            "triple_already_used"
        ]
    ]

    for candidate in unused_options:

        print(
            "  "
            f"{candidate['structure_id']} — "
            f"{candidate['prompt_or_goal']}"
        )


    for pair_id in [
        "agentdojo_pair_031",
        "agentdojo_pair_040",
    ]:

        print()
        print(
            f"PAIR: {pair_id}"
        )

        print(
            "BINDING:",
            json.dumps(
                results[
                    pair_id
                ][
                    "proposed_binding"
                ],
                ensure_ascii=False,
            ),
        )


    pair_091_result = results[
        "agentdojo_pair_091"
    ]

    print()
    print(
        "PAIR: agentdojo_pair_091"
    )

    print(
        "SAFE ATTACHMENT FILE IDs:",
        pair_091_result[
            "safe_attachment_file_ids"
        ],
    )

    print(
        "RECIPE DOCUMENT OBJECTS:"
    )

    for item in pair_091_result[
        "resolved_file_identity"
    ]:

        print(
            "  "
            f"path={item['yaml_path']} "
            f"id={item['file_id']} "
            f"filename={item['filename']} "
            f"owner={item['owner']}"
        )

    print(
        "TASK SOURCE MATCHES:",
        len(
            pair_091_result[
                "task_source_context"
            ]
        ),
    )

    for item in pair_091_result[
        "task_source_context"
    ]:

        print(
            "  "
            f"{item.get('source_file')}:"
            f"{item.get('matching_line')} "
            f"assignments="
            f"{item.get('literal_assignments')}"
        )


    pair_095_result = results[
        "agentdojo_pair_095"
    ]

    print()
    print(
        "PAIR: agentdojo_pair_095"
    )

    print(
        "FACEBOOK EMAIL OBJECTS:"
    )

    for item in pair_095_result[
        "resolved_email_identity"
    ]:

        print(
            "  "
            f"path={item['yaml_path']} "
            f"id={item['email_id']} "
            f"sender={item['sender']} "
            f"subject={item['subject']} "
            f"status={item['status']} "
            f"read={item['read']}"
        )

    print(
        "TASK SOURCE MATCHES:",
        len(
            pair_095_result[
                "task_source_context"
            ]
        ),
    )

    for item in pair_095_result[
        "task_source_context"
    ]:

        print(
            "  "
            f"{item.get('source_file')}:"
            f"{item.get('matching_line')} "
            f"assignments="
            f"{item.get('literal_assignments')}"
        )


    print()
    print(
        f"Resolution report: {OUTPUT_PATH}"
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

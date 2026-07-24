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

import yaml


SOURCE_ROOT = Path(
    "data/raw/agentdojo_source"
)

SRC_ROOT = (
    SOURCE_ROOT /
    "src"
)

COMBINED_POOL_PATH = Path(
    "data/processed/"
    "agentdojo_combined_structure_pool_v0.1.jsonl"
)

OUTPUT_DIR = Path(
    "data/interim/"
    "agentdojo_environment_surface_v0.1"
)

TOOL_JSONL_PATH = (
    OUTPUT_DIR /
    "agentdojo_suite_tool_catalog_v0.1.jsonl"
)

TOOL_CSV_PATH = (
    OUTPUT_DIR /
    "agentdojo_suite_tool_catalog_v0.1.csv"
)

VECTOR_JSONL_PATH = (
    OUTPUT_DIR /
    "agentdojo_injection_vector_catalog_v0.1.jsonl"
)

VECTOR_CSV_PATH = (
    OUTPUT_DIR /
    "agentdojo_injection_vector_catalog_v0.1.csv"
)

REPORT_PATH = (
    OUTPUT_DIR /
    "agentdojo_environment_surface_v0.1_report.json"
)


TARGET_COMMIT = (
    "089ed468cf3ed0322acc66b0211f26d9d90dbf60"
)

SUITES = (
    "banking",
    "slack",
    "travel",
    "workspace",
)

EXPECTED_TOOL_COUNTS = {
    "banking": 11,
    "slack": 11,
    "travel": 28,
    "workspace": 24,
}

EXPECTED_VECTOR_COUNTS = {
    "banking": 4,
    "slack": 6,
    "travel": 13,
    "workspace": 16,
}


FINANCIAL_WRITE_TOOLS = {
    "send_money",
    "schedule_transaction",
    "update_scheduled_transaction",
}

CREDENTIAL_AND_ACCOUNT_TOOLS = {
    "update_password",
    "update_user_info",
}

ACCESS_CONTROL_TOOLS = {
    "invite_user_to_slack",
    "add_user_to_channel",
    "remove_user_from_slack",
    "share_file",
    "add_calendar_event_participants",
}

EXTERNAL_COMMUNICATION_TOOLS = {
    "send_email",
    "send_direct_message",
    "send_channel_message",
    "post_webpage",
}

DESTRUCTIVE_TOOLS = {
    "delete_email",
    "delete_file",
    "cancel_calendar_event",
    "remove_user_from_slack",
}

RESERVATION_TOOLS = {
    "reserve_hotel",
    "reserve_car_rental",
    "reserve_restaurant",
}

STATE_WRITE_TOOLS = {
    "append_to_file",
    "create_file",
    "create_calendar_event",
    "reschedule_calendar_event",
}


def get_repository_commit() -> str:

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


def load_jsonl(
    path: Path,
) -> list[dict[str, Any]]:

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
                    f"Invalid JSONL in {path} "
                    f"at line {line_number}."
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


def write_csv(
    path: Path,
    rows: list[dict[str, Any]],
) -> None:

    if not rows:
        raise ValueError(
            f"Cannot write empty CSV: {path}"
        )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fieldnames = list(
        rows[0].keys()
    )

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
        writer.writerows(rows)


def ast_text(
    node: ast.AST | None,
) -> str | None:

    if node is None:
        return None

    try:
        return ast.unparse(node)
    except Exception:
        return None


def module_to_source_path(
    module_name: str,
) -> Path:

    relative_path = Path(
        *module_name.split(".")
    ).with_suffix(".py")

    return (
        SRC_ROOT /
        relative_path
    )


def extract_import_map(
    tree: ast.Module,
) -> dict[str, dict[str, str]]:

    import_map: dict[
        str,
        dict[str, str],
    ] = {}

    for node in tree.body:

        if not isinstance(
            node,
            ast.ImportFrom,
        ):
            continue

        if not node.module:
            continue

        for alias in node.names:

            local_name = (
                alias.asname
                or
                alias.name
            )

            import_map[
                local_name
            ] = {
                "module": node.module,
                "original_name": alias.name,
            }

    return import_map


def extract_tools_list(
    tree: ast.Module,
) -> list[str]:

    for node in tree.body:

        if not isinstance(
            node,
            ast.Assign,
        ):
            continue

        target_names = [
            target.id
            for target in node.targets
            if isinstance(
                target,
                ast.Name,
            )
        ]

        if "TOOLS" not in target_names:
            continue

        if not isinstance(
            node.value,
            (
                ast.List,
                ast.Tuple,
            ),
        ):
            raise ValueError(
                "TOOLS is not a literal list or tuple."
            )

        tools: list[str] = []

        for element in node.value.elts:

            if isinstance(
                element,
                ast.Name,
            ):
                tools.append(
                    element.id
                )

            elif isinstance(
                element,
                ast.Attribute,
            ):
                tools.append(
                    element.attr
                )

            else:
                raise ValueError(
                    "Unsupported TOOLS element: "
                    f"{ast.dump(element)}"
                )

        return tools

    raise ValueError(
        "Could not locate TOOLS assignment."
    )


def extract_environment_fields(
    tree: ast.Module,
) -> dict[str, str]:

    for node in tree.body:

        if not isinstance(
            node,
            ast.ClassDef,
        ):
            continue

        if not node.name.endswith(
            "Environment"
        ):
            continue

        fields: dict[str, str] = {}

        for statement in node.body:

            if not isinstance(
                statement,
                ast.AnnAssign,
            ):
                continue

            if not isinstance(
                statement.target,
                ast.Name,
            ):
                continue

            fields[
                statement.target.id
            ] = (
                ast_text(
                    statement.annotation
                )
                or
                ""
            )

        return fields

    raise ValueError(
        "Could not locate suite Environment class."
    )


def find_function_node(
    tree: ast.Module,
    function_name: str,
) -> ast.FunctionDef | ast.AsyncFunctionDef:

    for node in tree.body:

        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ) and node.name == function_name:
            return node

    raise ValueError(
        f"Could not locate function "
        f"{function_name}."
    )


DEPENDENCY_ALIAS_MAP = {
    "AnnotatedSlack": "slack",
    "AnnotatedWeb": "web",
}


def dependency_from_annotation(
    annotation_text: str | None,
) -> str | None:

    if not annotation_text:
        return None

    normalized_annotation = (
        annotation_text.strip()
    )

    alias_dependency = (
        DEPENDENCY_ALIAS_MAP.get(
            normalized_annotation
        )
    )

    if alias_dependency is not None:
        return alias_dependency

    match = re.search(
        r"Depends\(\s*['\"]([^'\"]+)['\"]\s*\)",
        normalized_annotation,
    )

    if match:
        return match.group(1)

    if "Depends(" in normalized_annotation:
        return (
            "callable_or_dynamic_dependency"
        )

    return None


def extract_function_parameters(
    function_node: (
        ast.FunctionDef
        |
        ast.AsyncFunctionDef
    ),
) -> list[dict[str, Any]]:

    parameters: list[
        dict[str, Any]
    ] = []

    positional_args = (
        list(
            function_node.args.posonlyargs
        )
        +
        list(
            function_node.args.args
        )
    )

    positional_defaults: list[
        ast.expr | None
    ] = (
        [
            None
        ]
        *
        (
            len(positional_args)
            -
            len(function_node.args.defaults)
        )
        +
        list(
            function_node.args.defaults
        )
    )

    for argument, default in zip(
        positional_args,
        positional_defaults,
        strict=True,
    ):

        annotation = ast_text(
            argument.annotation
        )

        environment_dependency = (
            dependency_from_annotation(
                annotation
            )
        )

        parameters.append(
            {
                "name": argument.arg,
                "kind": "positional_or_keyword",
                "annotation": annotation,
                "default": ast_text(default),
                "required": (
                    default is None
                    and
                    environment_dependency is None
                ),
                "is_environment_dependency": (
                    environment_dependency
                    is not None
                ),
                "environment_dependency": (
                    environment_dependency
                ),
            }
        )


    for argument, default in zip(
        function_node.args.kwonlyargs,
        function_node.args.kw_defaults,
        strict=True,
    ):

        annotation = ast_text(
            argument.annotation
        )

        environment_dependency = (
            dependency_from_annotation(
                annotation
            )
        )

        parameters.append(
            {
                "name": argument.arg,
                "kind": "keyword_only",
                "annotation": annotation,
                "default": ast_text(default),
                "required": (
                    default is None
                    and
                    environment_dependency is None
                ),
                "is_environment_dependency": (
                    environment_dependency
                    is not None
                ),
                "environment_dependency": (
                    environment_dependency
                ),
            }
        )


    if function_node.args.vararg:

        argument = (
            function_node.args.vararg
        )

        parameters.append(
            {
                "name": argument.arg,
                "kind": "var_positional",
                "annotation": ast_text(
                    argument.annotation
                ),
                "default": None,
                "required": False,
                "is_environment_dependency": False,
                "environment_dependency": None,
            }
        )


    if function_node.args.kwarg:

        argument = (
            function_node.args.kwarg
        )

        parameters.append(
            {
                "name": argument.arg,
                "kind": "var_keyword",
                "annotation": ast_text(
                    argument.annotation
                ),
                "default": None,
                "required": False,
                "is_environment_dependency": False,
                "environment_dependency": None,
            }
        )

    return parameters


def classify_tool(
    tool_name: str,
) -> tuple[str, str]:

    if tool_name in FINANCIAL_WRITE_TOOLS:
        return (
            "financial_write",
            "high",
        )

    if tool_name in CREDENTIAL_AND_ACCOUNT_TOOLS:
        return (
            "credential_or_account_write",
            "high",
        )

    if tool_name in DESTRUCTIVE_TOOLS:
        return (
            "destructive_or_revocation_write",
            "high",
        )

    if tool_name in ACCESS_CONTROL_TOOLS:
        return (
            "access_control_write",
            "high",
        )

    if tool_name in RESERVATION_TOOLS:
        return (
            "booking_or_reservation_write",
            "high",
        )

    if tool_name in EXTERNAL_COMMUNICATION_TOOLS:
        return (
            "external_communication_write",
            "medium",
        )

    if tool_name in STATE_WRITE_TOOLS:
        return (
            "state_changing_write",
            "medium",
        )

    if tool_name.startswith(
        (
            "get_",
            "read_",
            "search_",
            "list_",
            "check_",
        )
    ):
        return (
            "read_only",
            "low",
        )

    if tool_name.startswith(
        (
            "create_",
            "update_",
            "reschedule_",
            "append_",
            "share_",
        )
    ):
        return (
            "state_changing_write",
            "medium",
        )

    return (
        "manual_review_required",
        "unknown",
    )


def first_docstring_paragraph(
    docstring: str | None,
) -> str:

    if not docstring:
        return ""

    paragraphs = re.split(
        r"\n\s*\n",
        docstring.strip(),
    )

    return (
        paragraphs[0]
        .replace(
            "\n",
            " ",
        )
        .strip()
    )


def build_tool_catalog() -> tuple[
    list[dict[str, Any]],
    dict[str, list[str]],
    dict[str, dict[str, str]],
]:

    tool_records: list[
        dict[str, Any]
    ] = []

    suite_tool_names: dict[
        str,
        list[str],
    ] = {}

    suite_environment_fields: dict[
        str,
        dict[str, str],
    ] = {}

    module_tree_cache: dict[
        Path,
        ast.Module,
    ] = {}


    for suite in SUITES:

        task_suite_path = (
            SRC_ROOT
            /
            "agentdojo"
            /
            "default_suites"
            /
            "v1"
            /
            suite
            /
            "task_suite.py"
        )

        source_text = (
            task_suite_path.read_text(
                encoding="utf-8"
            )
        )

        tree = ast.parse(
            source_text,
            filename=str(
                task_suite_path
            ),
        )

        import_map = (
            extract_import_map(tree)
        )

        tool_names = (
            extract_tools_list(tree)
        )

        environment_fields = (
            extract_environment_fields(tree)
        )

        suite_tool_names[
            suite
        ] = tool_names

        suite_environment_fields[
            suite
        ] = environment_fields


        for tool_position, tool_name in enumerate(
            tool_names,
            start=1,
        ):

            if tool_name not in import_map:
                raise ValueError(
                    f"Tool {tool_name} in suite {suite} "
                    "was not found in the import map."
                )

            import_info = (
                import_map[
                    tool_name
                ]
            )

            module_name = (
                import_info[
                    "module"
                ]
            )

            original_name = (
                import_info[
                    "original_name"
                ]
            )

            implementation_path = (
                module_to_source_path(
                    module_name
                )
            )

            if not implementation_path.exists():
                raise FileNotFoundError(
                    "Tool implementation file "
                    f"not found: {implementation_path}"
                )

            if (
                implementation_path
                not in
                module_tree_cache
            ):
                implementation_text = (
                    implementation_path
                    .read_text(
                        encoding="utf-8"
                    )
                )

                module_tree_cache[
                    implementation_path
                ] = ast.parse(
                    implementation_text,
                    filename=str(
                        implementation_path
                    ),
                )

            function_node = (
                find_function_node(
                    module_tree_cache[
                        implementation_path
                    ],
                    original_name,
                )
            )

            parameters = (
                extract_function_parameters(
                    function_node
                )
            )

            public_parameters = [
                parameter
                for parameter in parameters
                if not parameter[
                    "is_environment_dependency"
                ]
            ]

            environment_dependencies = [
                parameter
                for parameter in parameters
                if parameter[
                    "is_environment_dependency"
                ]
            ]

            docstring = ast.get_docstring(
                function_node,
                clean=True,
            )

            capability_class, impact = (
                classify_tool(
                    tool_name
                )
            )

            relative_implementation_path = (
                implementation_path.relative_to(
                    SOURCE_ROOT
                )
            )

            tool_records.append(
                {
                    "tool_id": (
                        f"agentdojo_{suite}_{tool_name}"
                    ),
                    "suite": suite,
                    "tool_position": tool_position,
                    "tool_name": tool_name,
                    "implementation_module": module_name,
                    "implementation_file": str(
                        relative_implementation_path
                    ),
                    "source_line": (
                        function_node.lineno
                    ),
                    "description": (
                        first_docstring_paragraph(
                            docstring
                        )
                    ),
                    "full_docstring": (
                        docstring
                        or
                        ""
                    ),
                    "public_parameters": (
                        public_parameters
                    ),
                    "environment_dependencies": (
                        environment_dependencies
                    ),
                    "return_annotation": ast_text(
                        function_node.returns
                    ),
                    "suggested_capability_class": (
                        capability_class
                    ),
                    "suggested_action_impact": (
                        impact
                    ),
                    "curation_status": (
                        "unreviewed_suggestion"
                    ),
                    "source_commit": (
                        TARGET_COMMIT
                    ),
                }
            )

    return (
        tool_records,
        suite_tool_names,
        suite_environment_fields,
    )


def infer_injection_surface(
    suite: str,
    vector_id: str,
    description: str,
    locations: list[dict[str, Any]],
) -> str:

    location_text = " ".join(
        [
            suite,
            vector_id,
            description,
            *[
                location[
                    "source_file"
                ]
                for location
                in locations
            ],
            *[
                location[
                    "line_text"
                ]
                for location
                in locations
            ],
        ]
    ).lower()

    if "calendar" in location_text:
        return "calendar_event_or_description"

    if "email" in location_text:
        return "email_message_or_metadata"

    if (
        "drive" in location_text
        or
        "file" in location_text
        or
        "document" in location_text
        or
        "bill" in location_text
        or
        "landlord" in location_text
    ):
        return "file_or_cloud_document"

    if (
        "transaction" in location_text
        or
        "iban" in location_text
    ):
        return "bank_transaction_or_payment_metadata"

    if (
        "slack" in location_text
        or
        "channel" in location_text
        or
        "inbox" in location_text
    ):
        return "slack_channel_or_message"

    if (
        "website" in location_text
        or
        "web" in location_text
        or
        "blog" in location_text
        or
        "review" in location_text
        or
        "hotel" in location_text
        or
        "restaurant" in location_text
        or
        "car" in location_text
    ):
        return "external_web_content_or_review"

    return "manual_review_required"


def locate_vector_placeholders(
    suite_data_dir: Path,
    vector_id: str,
) -> list[dict[str, Any]]:

    placeholder = (
        "{"
        +
        vector_id
        +
        "}"
    )

    locations: list[
        dict[str, Any]
    ] = []


    for yaml_path in sorted(
        suite_data_dir.rglob(
            "*.yaml"
        )
    ):

        lines = yaml_path.read_text(
            encoding="utf-8"
        ).splitlines()

        for line_index, line in enumerate(
            lines
        ):

            if placeholder not in line:
                continue

            context_start = max(
                0,
                line_index - 2,
            )

            context_end = min(
                len(lines),
                line_index + 3,
            )

            relative_path = (
                yaml_path.relative_to(
                    SOURCE_ROOT
                )
            )

            locations.append(
                {
                    "source_file": str(
                        relative_path
                    ),
                    "line_number": (
                        line_index + 1
                    ),
                    "line_text": (
                        line.strip()
                    ),
                    "context": "\n".join(
                        lines[
                            context_start:
                            context_end
                        ]
                    ),
                }
            )

    return locations


def build_injection_vector_catalog() -> list[
    dict[str, Any]
]:

    records: list[
        dict[str, Any]
    ] = []


    for suite in SUITES:

        suite_data_dir = (
            SRC_ROOT
            /
            "agentdojo"
            /
            "data"
            /
            "suites"
            /
            suite
        )

        vectors_path = (
            suite_data_dir
            /
            "injection_vectors.yaml"
        )

        vector_data = yaml.safe_load(
            vectors_path.read_text(
                encoding="utf-8"
            )
        )

        if not isinstance(
            vector_data,
            dict,
        ):
            raise ValueError(
                "Unexpected injection-vector YAML "
                f"shape in {vectors_path}."
            )


        for vector_id, vector_info in (
            vector_data.items()
        ):

            if not isinstance(
                vector_info,
                dict,
            ):
                raise ValueError(
                    "Unexpected vector definition "
                    f"for {suite}:{vector_id}."
                )

            description = str(
                vector_info.get(
                    "description",
                    "",
                )
                or
                ""
            )

            default_value = str(
                vector_info.get(
                    "default",
                    "",
                )
                or
                ""
            )

            locations = (
                locate_vector_placeholders(
                    suite_data_dir,
                    str(vector_id),
                )
            )

            surface_type = (
                infer_injection_surface(
                    suite=suite,
                    vector_id=str(
                        vector_id
                    ),
                    description=description,
                    locations=locations,
                )
            )

            records.append(
                {
                    "vector_id": str(
                        vector_id
                    ),
                    "suite": suite,
                    "description": description,
                    "default_value": (
                        default_value
                    ),
                    "inferred_surface_type": (
                        surface_type
                    ),
                    "location_count": (
                        len(locations)
                    ),
                    "locations": locations,
                    "attacker_controlled": True,
                    "trust_level_suggestion": (
                        "untrusted"
                    ),
                    "curation_status": (
                        "unreviewed_suggestion"
                    ),
                    "source_file": str(
                        vectors_path.relative_to(
                            SOURCE_ROOT
                        )
                    ),
                    "source_commit": (
                        TARGET_COMMIT
                    ),
                }
            )

    return records


def explicit_reference_functions(
    record: dict[str, Any],
) -> list[str]:

    execution_semantics = (
        record.get(
            "execution_semantics",
            {},
        )
    )

    sequence = (
        execution_semantics.get(
            "reference_action_sequence",
            [],
        )
        or
        []
    )

    functions: list[str] = []

    for step in sequence:

        if not isinstance(
            step,
            dict,
        ):
            continue

        function_name = (
            step.get("function")
            or
            step.get("name")
            or
            step.get("tool_name")
        )

        if function_name:
            functions.append(
                str(
                    function_name
                )
            )

    return functions


def build_coverage_report(
    combined_records: list[dict[str, Any]],
    suite_tool_names: dict[str, list[str]],
) -> dict[str, Any]:

    referenced_by_suite: dict[
        str,
        Counter[str],
    ] = {
        suite: Counter()
        for suite in SUITES
    }

    explicit_sequence_record_count = 0


    for record in combined_records:

        suite = str(
            record[
                "suite"
            ]
        )

        functions = (
            explicit_reference_functions(
                record
            )
        )

        if functions:
            explicit_sequence_record_count += 1

        referenced_by_suite[
            suite
        ].update(
            functions
        )


    suite_coverage: dict[
        str,
        dict[str, Any],
    ] = {}


    for suite in SUITES:

        available = set(
            suite_tool_names[
                suite
            ]
        )

        referenced = set(
            referenced_by_suite[
                suite
            ].keys()
        )

        suite_coverage[
            suite
        ] = {
            "available_tool_count": (
                len(available)
            ),
            "referenced_tool_count": (
                len(referenced)
            ),
            "referenced_but_not_available": sorted(
                referenced
                -
                available
            ),
            "available_but_not_referenced": sorted(
                available
                -
                referenced
            ),
            "reference_frequency": dict(
                referenced_by_suite[
                    suite
                ].most_common()
            ),
        }


    missing_references = {
        suite: details[
            "referenced_but_not_available"
        ]
        for suite, details
        in suite_coverage.items()
        if details[
            "referenced_but_not_available"
        ]
    }


    return {
        "combined_record_count": (
            len(combined_records)
        ),
        "records_with_explicit_reference_sequence": (
            explicit_sequence_record_count
        ),
        "suite_coverage": suite_coverage,
        "referenced_tools_missing_from_suite": (
            missing_references
        ),
    }


def tool_csv_rows(
    tool_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    rows = []

    for record in tool_records:

        rows.append(
            {
                "tool_id": (
                    record["tool_id"]
                ),
                "suite": (
                    record["suite"]
                ),
                "tool_position": (
                    record["tool_position"]
                ),
                "tool_name": (
                    record["tool_name"]
                ),
                "description": (
                    record["description"]
                ),
                "implementation_file": (
                    record["implementation_file"]
                ),
                "source_line": (
                    record["source_line"]
                ),
                "public_parameters": json.dumps(
                    record[
                        "public_parameters"
                    ],
                    ensure_ascii=False,
                ),
                "environment_dependencies": json.dumps(
                    record[
                        "environment_dependencies"
                    ],
                    ensure_ascii=False,
                ),
                "return_annotation": (
                    record[
                        "return_annotation"
                    ]
                ),
                "suggested_capability_class": (
                    record[
                        "suggested_capability_class"
                    ]
                ),
                "suggested_action_impact": (
                    record[
                        "suggested_action_impact"
                    ]
                ),
                "curation_status": (
                    record[
                        "curation_status"
                    ]
                ),
            }
        )

    return rows


def vector_csv_rows(
    vector_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    rows = []

    for record in vector_records:

        rows.append(
            {
                "vector_id": (
                    record["vector_id"]
                ),
                "suite": (
                    record["suite"]
                ),
                "description": (
                    record["description"]
                ),
                "default_value": (
                    record["default_value"]
                ),
                "inferred_surface_type": (
                    record[
                        "inferred_surface_type"
                    ]
                ),
                "location_count": (
                    record["location_count"]
                ),
                "locations": json.dumps(
                    record["locations"],
                    ensure_ascii=False,
                ),
                "trust_level_suggestion": (
                    record[
                        "trust_level_suggestion"
                    ]
                ),
                "curation_status": (
                    record[
                        "curation_status"
                    ]
                ),
            }
        )

    return rows


def main() -> None:

    repository_commit = (
        get_repository_commit()
    )

    if repository_commit != TARGET_COMMIT:
        raise ValueError(
            "AgentDojo source commit mismatch.\n"
            f"Expected: {TARGET_COMMIT}\n"
            f"Found:    {repository_commit}"
        )


    combined_records = load_jsonl(
        COMBINED_POOL_PATH
    )

    if len(combined_records) != 117:
        raise ValueError(
            "Expected 117 combined AgentDojo "
            f"structures, found {len(combined_records)}."
        )


    (
        tool_records,
        suite_tool_names,
        suite_environment_fields,
    ) = build_tool_catalog()


    vector_records = (
        build_injection_vector_catalog()
    )


    tool_counts = Counter(
        record["suite"]
        for record
        in tool_records
    )

    vector_counts = Counter(
        record["suite"]
        for record
        in vector_records
    )


    if dict(
        tool_counts
    ) != EXPECTED_TOOL_COUNTS:
        raise ValueError(
            "Unexpected suite tool counts.\n"
            f"Expected: {EXPECTED_TOOL_COUNTS}\n"
            f"Found: {dict(tool_counts)}"
        )


    if dict(
        vector_counts
    ) != EXPECTED_VECTOR_COUNTS:
        raise ValueError(
            "Unexpected injection-vector counts.\n"
            f"Expected: {EXPECTED_VECTOR_COUNTS}\n"
            f"Found: {dict(vector_counts)}"
        )


    unique_tool_names = {
        record[
            "tool_name"
        ]
        for record
        in tool_records
    }

    if len(tool_records) != 74:
        raise ValueError(
            "Expected 74 suite-level tool instances, "
            f"found {len(tool_records)}."
        )

    if len(unique_tool_names) != 69:
        raise ValueError(
            "Expected 69 globally unique tool names, "
            f"found {len(unique_tool_names)}."
        )

    if len(vector_records) != 39:
        raise ValueError(
            "Expected 39 injection vectors, "
            f"found {len(vector_records)}."
        )


    coverage = build_coverage_report(
        combined_records=combined_records,
        suite_tool_names=(
            suite_tool_names
        ),
    )


    if coverage[
        "referenced_tools_missing_from_suite"
    ]:
        raise ValueError(
            "Some explicit reference functions are "
            "not available in their suite:\n"
            +
            json.dumps(
                coverage[
                    "referenced_tools_missing_from_suite"
                ],
                indent=2,
                ensure_ascii=False,
            )
        )


    vector_location_counts = Counter(
        "located"
        if record[
            "location_count"
        ] > 0
        else "not_located"
        for record
        in vector_records
    )

    capability_counts = Counter(
        record[
            "suggested_capability_class"
        ]
        for record
        in tool_records
    )

    impact_counts = Counter(
        record[
            "suggested_action_impact"
        ]
        for record
        in tool_records
    )

    surface_counts = Counter(
        record[
            "inferred_surface_type"
        ]
        for record
        in vector_records
    )


    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    write_jsonl(
        TOOL_JSONL_PATH,
        tool_records,
    )

    write_csv(
        TOOL_CSV_PATH,
        tool_csv_rows(
            tool_records
        ),
    )

    write_jsonl(
        VECTOR_JSONL_PATH,
        vector_records,
    )

    write_csv(
        VECTOR_CSV_PATH,
        vector_csv_rows(
            vector_records
        ),
    )


    report = {
        "dataset": "agentdojo",
        "environment_surface_version": "0.1",
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "source_commit": (
            repository_commit
        ),

        "benchmark_version": "v1.2.2",

        "combined_structure_count": (
            len(combined_records)
        ),

        "tool_instance_count": (
            len(tool_records)
        ),

        "globally_unique_tool_name_count": (
            len(unique_tool_names)
        ),

        "tool_counts_by_suite": dict(
            tool_counts
        ),

        "suite_environment_fields": (
            suite_environment_fields
        ),

        "suggested_capability_class_counts": dict(
            capability_counts
        ),

        "suggested_action_impact_counts": dict(
            impact_counts
        ),

        "injection_vector_count": (
            len(vector_records)
        ),

        "injection_vector_counts_by_suite": dict(
            vector_counts
        ),

        "injection_vector_location_status": dict(
            vector_location_counts
        ),

        "injection_surface_type_counts": dict(
            surface_counts
        ),

        "explicit_tool_coverage": (
            coverage
        ),

        "important_notes": [
            (
                "Suite tool availability is different from "
                "ground-truth tool usage. The agent receives "
                "the full suite tool catalog."
            ),
            (
                "Suggested tool capability and impact values "
                "are heuristic metadata and require human review."
            ),
            (
                "Injection-vector locations describe attacker-"
                "controllable environment surfaces. They are not "
                "runtime general_risk_label values."
            ),
            (
                "Operational-effect-only injection tasks may "
                "have no explicit reference sequence and are "
                "therefore excluded from explicit tool-coverage "
                "calculations."
            ),
        ],
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
        "AGENTDOJO ENVIRONMENT SURFACE v0.1 EXTRACTED"
    )
    print("=" * 80)

    print()
    print(
        "Repository commit:",
        repository_commit,
    )

    print()
    print(
        "Suite tool instances:"
    )

    for suite in SUITES:
        print(
            f"  {suite:<10} "
            f"{tool_counts[suite]}"
        )

    print(
        "  total      ",
        len(tool_records),
    )

    print(
        "  unique     ",
        len(unique_tool_names),
    )

    print()
    print(
        "Suggested capability classes:"
    )

    for capability, count in sorted(
        capability_counts.items()
    ):
        print(
            f"  {capability}: {count}"
        )

    print()
    print(
        "Injection vectors:"
    )

    for suite in SUITES:
        print(
            f"  {suite:<10} "
            f"{vector_counts[suite]}"
        )

    print(
        "  total      ",
        len(vector_records),
    )

    print()
    print(
        "Injection-vector locations:"
    )

    for status, count in sorted(
        vector_location_counts.items()
    ):
        print(
            f"  {status}: {count}"
        )

    print()
    print(
        "Combined structures:",
        coverage[
            "combined_record_count"
        ],
    )

    print(
        "Structures with explicit reference sequence:",
        coverage[
            "records_with_explicit_reference_sequence"
        ],
    )

    print(
        "Referenced tools missing from suite:",
        len(
            coverage[
                "referenced_tools_missing_from_suite"
            ]
        ),
    )

    print()
    print(
        f"Tool catalog: {TOOL_JSONL_PATH}"
    )

    print(
        f"Tool audit CSV: {TOOL_CSV_PATH}"
    )

    print(
        f"Injection-vector catalog: "
        f"{VECTOR_JSONL_PATH}"
    )

    print(
        f"Injection-vector audit CSV: "
        f"{VECTOR_CSV_PATH}"
    )

    print(
        f"Report: {REPORT_PATH}"
    )


if __name__ == "__main__":
    main()

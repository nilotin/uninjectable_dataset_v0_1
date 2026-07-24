from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


SCRIPTS_DIR = Path("scripts")

SMOKE_POOL_PATH = Path(
    "data/interim/"
    "agentdojo_contextual_action_attempt_smoke_pool_v0.1.1.jsonl"
)

SEARCH_TERMS = [
    "agentdojo_contextual_action_attempt_smoke_pool_v0.1.1",
    "contextual_action_attempt_smoke_pool",
    "smoke_pool_v0.1.1",
]

TARGET_PAIR_IDS = {
    "agentdojo_pair_001",
    "agentdojo_pair_016",
    "agentdojo_pair_031",
    "agentdojo_pair_040",
    "agentdojo_pair_091",
    "agentdojo_pair_095",
}


def load_jsonl(
    path: Path,
) -> list[dict[str, Any]]:

    if not path.exists():
        raise FileNotFoundError(
            f"Missing smoke pool: {path}"
        )

    rows = []

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
                rows.append(
                    json.loads(line)
                )

            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid JSONL at line {line_number}"
                ) from error

    return rows


def find_pair_id(
    value: Any,
) -> str | None:

    if isinstance(value, dict):

        for key in [
            "pair_id",
            "composition_pair_id",
            "source_pair_id",
        ]:
            if key in value:
                return str(value[key])

        for child in value.values():
            result = find_pair_id(child)

            if result:
                return result

    elif isinstance(value, list):

        for child in value:
            result = find_pair_id(child)

            if result:
                return result

    return None


def flatten_schema(
    value: Any,
    prefix: str = "",
) -> list[tuple[str, str]]:

    paths: list[tuple[str, str]] = []

    if isinstance(value, dict):

        for key, child in value.items():

            path = (
                f"{prefix}.{key}"
                if prefix
                else str(key)
            )

            paths.append(
                (
                    path,
                    type(child).__name__,
                )
            )

            paths.extend(
                flatten_schema(
                    child,
                    path,
                )
            )

    elif isinstance(value, list):

        list_path = (
            f"{prefix}[]"
            if prefix
            else "[]"
        )

        for child in value[:1]:
            paths.extend(
                flatten_schema(
                    child,
                    list_path,
                )
            )

    return paths


def truncate(
    value: Any,
    limit: int = 1000,
) -> str:

    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
        )

    if len(text) <= limit:
        return text

    return (
        text[:limit]
        +
        "... [TRUNCATED]"
    )


def collect_interesting_fields(
    value: Any,
    prefix: str = "",
) -> list[tuple[str, Any]]:

    results = []

    keywords = {
        "label",
        "input",
        "serialized",
        "text",
        "attempt",
        "action",
        "tool",
        "args",
        "pair",
        "role",
        "variant",
        "source",
        "retrieval",
        "binding",
        "structure",
        "vector",
    }

    if isinstance(value, dict):

        for key, child in value.items():

            path = (
                f"{prefix}.{key}"
                if prefix
                else str(key)
            )

            key_lower = str(key).lower()

            if any(
                keyword in key_lower
                for keyword in keywords
            ):
                results.append(
                    (
                        path,
                        child,
                    )
                )

            results.extend(
                collect_interesting_fields(
                    child,
                    path,
                )
            )

    elif isinstance(value, list):

        for index, child in enumerate(
            value[:3]
        ):
            results.extend(
                collect_interesting_fields(
                    child,
                    f"{prefix}[{index}]",
                )
            )

    return results


def search_builder_scripts() -> list[dict[str, Any]]:

    matches = []

    if not SCRIPTS_DIR.exists():
        return matches

    for path in sorted(
        SCRIPTS_DIR.rglob("*.py")
    ):

        try:
            text = path.read_text(
                encoding="utf-8"
            )
        except UnicodeDecodeError:
            continue

        matching_terms = [
            term
            for term in SEARCH_TERMS
            if term in text
        ]

        if not matching_terms:
            continue

        lines = text.splitlines()

        matching_line_numbers = []

        for line_number, line in enumerate(
            lines,
            start=1,
        ):
            if any(
                term in line
                for term in matching_terms
            ):
                matching_line_numbers.append(
                    line_number
                )

        snippets = []

        for line_number in matching_line_numbers:

            start = max(
                1,
                line_number - 15,
            )

            end = min(
                len(lines),
                line_number + 25,
            )

            snippet = "\n".join(
                f"{number:04d}: {lines[number - 1]}"
                for number in range(
                    start,
                    end + 1,
                )
            )

            snippets.append(
                {
                    "matching_line": line_number,
                    "snippet": snippet,
                }
            )

        matches.append(
            {
                "path": str(path),
                "matching_terms": matching_terms,
                "snippets": snippets,
            }
        )

    return matches


def main() -> None:

    rows = load_jsonl(
        SMOKE_POOL_PATH
    )

    builder_matches = search_builder_scripts()

    pair_counts = Counter(
        find_pair_id(row)
        for row in rows
    )

    selected_rows = [
        row
        for row in rows
        if find_pair_id(row) in TARGET_PAIR_IDS
    ]


    print("=" * 90)
    print(
        "AGENTDOJO SMOKE MATERIALIZER "
        "INSPECTION v0.1.2"
    )
    print("=" * 90)

    print()
    print(
        "Smoke rows:",
        len(rows),
    )

    print(
        "Distinct pair IDs:",
        len(
            {
                pair_id
                for pair_id in pair_counts
                if pair_id
            }
        ),
    )

    print(
        "Rows without detectable pair ID:",
        pair_counts[None],
    )

    print()
    print(
        "Rows per selected pair:"
    )

    for pair_id in sorted(
        TARGET_PAIR_IDS
    ):
        print(
            f"  {pair_id}: "
            f"{pair_counts[pair_id]}"
        )


    print()
    print("=" * 90)
    print("POSSIBLE BUILDER SCRIPTS")
    print("=" * 90)

    if not builder_matches:
        print(
            "<no script containing the smoke-pool "
            "filename was found>"
        )

    for match in builder_matches:

        print()
        print(
            "SCRIPT:",
            match["path"],
        )

        print(
            "MATCHING TERMS:",
            match["matching_terms"],
        )

        for snippet in match["snippets"]:

            print()
            print(
                "MATCHING LINE:",
                snippet["matching_line"],
            )

            print(
                snippet["snippet"]
            )


    print()
    print("=" * 90)
    print("ROW SCHEMA")
    print("=" * 90)

    if rows:

        schema_counts = Counter(
            flatten_schema(
                rows[0]
            )
        )

        for (
            path,
            value_type,
        ), count in sorted(
            schema_counts.items()
        ):
            print(
                f"{path} :: {value_type}"
            )


    print()
    print("=" * 90)
    print("SELECTED PAIR ROWS")
    print("=" * 90)

    for row in selected_rows:

        pair_id = find_pair_id(
            row
        )

        print()
        print("-" * 110)

        print(
            "PAIR:",
            pair_id,
        )

        print(
            "TOP-LEVEL KEYS:",
            list(row.keys()),
        )

        print()
        print(
            "INTERESTING FIELDS:"
        )

        seen_paths = set()

        for path, value in collect_interesting_fields(
            row
        ):

            if path in seen_paths:
                continue

            seen_paths.add(
                path
            )

            print(
                f"  {path}: "
                f"{truncate(value, 700)}"
            )


    print()
    print("=" * 90)

    print(
        "Smoke pool modified: no"
    )

    print(
        "Candidate pair plan modified: no"
    )

    print(
        "Final labels modified: no"
    )


if __name__ == "__main__":
    main()

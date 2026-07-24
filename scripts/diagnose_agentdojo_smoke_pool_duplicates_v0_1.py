from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


INTERIM_DIR = Path(
    "data/interim"
)

SMOKE_POOL_PATH = (
    INTERIM_DIR
    / "agentdojo_contextual_action_attempt_smoke_pool_v0.1.jsonl"
)

DUPLICATE_CSV_PATH = (
    INTERIM_DIR
    / "agentdojo_contextual_action_attempt_duplicate_rows_v0.1.csv"
)

REPORT_PATH = (
    INTERIM_DIR
    / "agentdojo_contextual_action_attempt_duplicate_diagnostics_v0.1.json"
)


EXPECTED_ROW_COUNT = 200
EXPECTED_DUPLICATE_EXCESS_COUNT = 6


def load_jsonl(
    path: Path,
) -> list[dict[str, Any]]:

    if not path.exists():
        raise FileNotFoundError(
            f"Missing input file: {path}"
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


def canonical_json(
    value: Any,
) -> str:

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def short_hash(
    value: str,
) -> str:

    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()[:16]


def compact_text(
    value: Any,
    max_chars: int = 500,
) -> str:

    if isinstance(value, str):
        text = value
    else:
        text = canonical_json(
            value
        )

    text = text.replace(
        "\n",
        "\\n",
    )

    if len(text) > max_chars:
        return (
            text[:max_chars]
            + "... [TRUNCATED]"
        )

    return text


def write_csv(
    path: Path,
    rows: list[dict[str, Any]],
) -> None:

    if not rows:
        raise ValueError(
            "No duplicate rows were found."
        )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=list(
                rows[0].keys()
            ),
        )

        writer.writeheader()
        writer.writerows(rows)


def main() -> None:

    rows = load_jsonl(
        SMOKE_POOL_PATH
    )

    if len(rows) != EXPECTED_ROW_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_ROW_COUNT} rows, "
            f"found {len(rows)}."
        )


    rows_by_model_input: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)


    for row in rows:

        model_input_text = str(
            row[
                "model_input"
            ][
                "text"
            ]
        )

        rows_by_model_input[
            model_input_text
        ].append(
            row
        )


    duplicate_groups = [
        (
            model_input_text,
            grouped_rows,
        )
        for model_input_text, grouped_rows
        in rows_by_model_input.items()
        if len(grouped_rows) > 1
    ]


    duplicate_groups.sort(
        key=lambda item: (
            -len(item[1]),
            short_hash(item[0]),
        )
    )


    duplicate_row_count = sum(
        len(grouped_rows)
        for _, grouped_rows
        in duplicate_groups
    )

    duplicate_excess_count = sum(
        len(grouped_rows) - 1
        for _, grouped_rows
        in duplicate_groups
    )


    if (
        duplicate_excess_count
        !=
        EXPECTED_DUPLICATE_EXCESS_COUNT
    ):
        raise ValueError(
            "Smoke-pool duplicate count changed.\n"
            f"Expected excess duplicates: "
            f"{EXPECTED_DUPLICATE_EXCESS_COUNT}\n"
            f"Found: {duplicate_excess_count}"
        )


    conflicting_label_groups = []
    same_label_groups = []
    cross_pair_groups = []
    same_pair_groups = []
    fingerprint_mismatch_groups = []

    duplicate_csv_rows: list[
        dict[str, Any]
    ] = []

    duplicate_tool_counts: Counter[
        str
    ] = Counter()

    duplicate_vector_counts: Counter[
        str
    ] = Counter()

    duplicate_variant_counts: Counter[
        str
    ] = Counter()

    duplicate_suite_counts: Counter[
        str
    ] = Counter()


    for group_index, (
        model_input_text,
        grouped_rows,
    ) in enumerate(
        duplicate_groups,
        start=1,
    ):

        group_id = (
            f"duplicate_group_"
            f"{group_index:02d}"
        )

        input_signature = short_hash(
            model_input_text
        )

        labels = {
            int(
                row[
                    "review"
                ][
                    "proposed_binary_label"
                ]
            )
            for row in grouped_rows
        }

        pair_ids = {
            str(
                row[
                    "pair_id"
                ]
            )
            for row in grouped_rows
        }

        variants = {
            str(
                row[
                    "variant"
                ][
                    "name"
                ]
            )
            for row in grouped_rows
        }

        shared_context_fingerprints = {
            str(
                row[
                    "model_input"
                ][
                    "shared_context_fingerprint"
                ]
            )
            for row in grouped_rows
        }

        action_fingerprints = {
            str(
                row[
                    "model_input"
                ][
                    "attempted_action_fingerprint"
                ]
            )
            for row in grouped_rows
        }


        group_summary = {
            "duplicate_group_id": group_id,
            "input_signature": input_signature,
            "group_size": len(
                grouped_rows
            ),
            "pair_ids": sorted(
                pair_ids
            ),
            "variants": sorted(
                variants
            ),
            "proposed_labels": sorted(
                labels
            ),
        }


        if len(labels) > 1:
            conflicting_label_groups.append(
                group_summary
            )
        else:
            same_label_groups.append(
                group_summary
            )


        if len(pair_ids) > 1:
            cross_pair_groups.append(
                group_summary
            )
        else:
            same_pair_groups.append(
                group_summary
            )


        if (
            len(
                shared_context_fingerprints
            )
            != 1
            or
            len(
                action_fingerprints
            )
            != 1
        ):
            fingerprint_mismatch_groups.append(
                group_summary
            )


        for row in grouped_rows:

            action = row[
                "action"
            ]

            provenance = row[
                "provenance"
            ]

            user_context = row[
                "user_context"
            ]

            retrieval_context = row[
                "retrieval_context"
            ]

            tool_name = str(
                action[
                    "tool_name"
                ]
            )

            vector_id = str(
                provenance[
                    "injection_vector_id"
                ]
            )

            variant_name = str(
                row[
                    "variant"
                ][
                    "name"
                ]
            )

            suite = str(
                row[
                    "suite"
                ]
            )


            duplicate_tool_counts[
                tool_name
            ] += 1

            duplicate_vector_counts[
                vector_id
            ] += 1

            duplicate_variant_counts[
                variant_name
            ] += 1

            duplicate_suite_counts[
                suite
            ] += 1


            duplicate_csv_rows.append(
                {
                    "duplicate_group_id": (
                        group_id
                    ),

                    "input_signature": (
                        input_signature
                    ),

                    "group_size": len(
                        grouped_rows
                    ),

                    "has_label_conflict": (
                        len(labels) > 1
                    ),

                    "row_id": row[
                        "row_id"
                    ],

                    "pair_id": row[
                        "pair_id"
                    ],

                    "session_group_id": row[
                        "session_group_id"
                    ],

                    "suite": suite,

                    "variant": (
                        variant_name
                    ),

                    "proposed_binary_label": (
                        row[
                            "review"
                        ][
                            "proposed_binary_label"
                        ]
                    ),

                    "legitimate_structure_id": (
                        provenance[
                            "legitimate_structure_id"
                        ]
                    ),

                    "attacker_structure_id": (
                        provenance[
                            "attacker_structure_id"
                        ]
                    ),

                    "injection_vector_id": (
                        vector_id
                    ),

                    "same_tool_minimal_pair": (
                        provenance[
                            "same_tool_minimal_pair"
                        ]
                    ),

                    "user_goal": (
                        user_context[
                            "goal"
                        ]
                    ),

                    "retrieval_channel": (
                        retrieval_context[
                            "retrieval_channel"
                        ]
                    ),

                    "retrieved_content": (
                        compact_text(
                            retrieval_context[
                                "content_redacted"
                            ],
                            max_chars=800,
                        )
                    ),

                    "attempted_tool": (
                        tool_name
                    ),

                    "attempted_args": (
                        compact_text(
                            action[
                                "args"
                            ],
                            max_chars=800,
                        )
                    ),

                    "shared_context_fingerprint": (
                        row[
                            "model_input"
                        ][
                            "shared_context_fingerprint"
                        ]
                    ),

                    "attempted_action_fingerprint": (
                        row[
                            "model_input"
                        ][
                            "attempted_action_fingerprint"
                        ]
                    ),
                }
            )


    write_csv(
        DUPLICATE_CSV_PATH,
        duplicate_csv_rows,
    )


    report = {
        "artifact": (
            "agentdojo_contextual_action_attempt_"
            "smoke_pool_v0.1"
        ),

        "row_count": len(rows),

        "unique_model_input_count": len(
            rows_by_model_input
        ),

        "duplicate_group_count": len(
            duplicate_groups
        ),

        "duplicate_row_count": (
            duplicate_row_count
        ),

        "duplicate_excess_count": (
            duplicate_excess_count
        ),

        "duplicate_group_size_counts": dict(
            Counter(
                len(grouped_rows)
                for _, grouped_rows
                in duplicate_groups
            )
        ),

        "same_label_duplicate_group_count": (
            len(
                same_label_groups
            )
        ),

        "conflicting_label_group_count": (
            len(
                conflicting_label_groups
            )
        ),

        "cross_pair_duplicate_group_count": (
            len(
                cross_pair_groups
            )
        ),

        "same_pair_duplicate_group_count": (
            len(
                same_pair_groups
            )
        ),

        "fingerprint_mismatch_group_count": (
            len(
                fingerprint_mismatch_groups
            )
        ),

        "duplicate_suite_counts": dict(
            duplicate_suite_counts
        ),

        "duplicate_variant_counts": dict(
            duplicate_variant_counts
        ),

        "duplicate_tool_counts": dict(
            duplicate_tool_counts
        ),

        "duplicate_vector_counts": dict(
            duplicate_vector_counts
        ),

        "duplicate_groups": [
            {
                "duplicate_group_id": (
                    f"duplicate_group_"
                    f"{index:02d}"
                ),

                "input_signature": (
                    short_hash(
                        model_input_text
                    )
                ),

                "group_size": len(
                    grouped_rows
                ),

                "pair_ids": sorted(
                    {
                        row[
                            "pair_id"
                        ]
                        for row in grouped_rows
                    }
                ),

                "row_ids": sorted(
                    {
                        row[
                            "row_id"
                        ]
                        for row in grouped_rows
                    }
                ),

                "variants": sorted(
                    {
                        row[
                            "variant"
                        ][
                            "name"
                        ]
                        for row in grouped_rows
                    }
                ),

                "proposed_labels": sorted(
                    {
                        row[
                            "review"
                        ][
                            "proposed_binary_label"
                        ]
                        for row in grouped_rows
                    }
                ),

                "tools": sorted(
                    {
                        row[
                            "action"
                        ][
                            "tool_name"
                        ]
                        for row in grouped_rows
                    }
                ),

                "vectors": sorted(
                    {
                        row[
                            "provenance"
                        ][
                            "injection_vector_id"
                        ]
                        for row in grouped_rows
                    }
                ),
            }
            for index, (
                model_input_text,
                grouped_rows,
            ) in enumerate(
                duplicate_groups,
                start=1,
            )
        ],

        "important_notes": [
            (
                "Exact duplicate detection is based on "
                "model_input.text."
            ),
            (
                "Within-pair attempted actions were already "
                "validated as distinct during smoke-pool "
                "generation."
            ),
            (
                "A duplicate group containing both labels 0 "
                "and 1 is a critical label contradiction."
            ),
            (
                "Same-label duplicates are not contradictory "
                "but reduce effective dataset diversity."
            ),
            (
                "No smoke-pool rows are modified by this "
                "diagnostic script."
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
        "AGENTDOJO SMOKE-POOL DUPLICATE "
        "DIAGNOSTICS v0.1 COMPLETE"
    )
    print("=" * 80)

    print()
    print(
        "Rows:",
        len(rows),
    )

    print(
        "Unique model inputs:",
        len(
            rows_by_model_input
        ),
    )

    print(
        "Duplicate groups:",
        len(
            duplicate_groups
        ),
    )

    print(
        "Rows belonging to duplicate groups:",
        duplicate_row_count,
    )

    print(
        "Excess duplicate rows:",
        duplicate_excess_count,
    )

    print()
    print(
        "Same-label duplicate groups:",
        len(
            same_label_groups
        ),
    )

    print(
        "Conflicting-label duplicate groups:",
        len(
            conflicting_label_groups
        ),
    )

    print()
    print(
        "Cross-pair duplicate groups:",
        len(
            cross_pair_groups
        ),
    )

    print(
        "Same-pair duplicate groups:",
        len(
            same_pair_groups
        ),
    )

    print(
        "Fingerprint mismatch groups:",
        len(
            fingerprint_mismatch_groups
        ),
    )


    for group_index, (
        model_input_text,
        grouped_rows,
    ) in enumerate(
        duplicate_groups,
        start=1,
    ):

        labels = sorted(
            {
                row[
                    "review"
                ][
                    "proposed_binary_label"
                ]
                for row in grouped_rows
            }
        )

        print()
        print("=" * 100)

        print(
            "GROUP:",
            f"duplicate_group_{group_index:02d}",
        )

        print(
            "INPUT SIGNATURE:",
            short_hash(
                model_input_text
            ),
        )

        print(
            "GROUP SIZE:",
            len(
                grouped_rows
            ),
        )

        print(
            "PROPOSED LABELS:",
            labels,
        )

        print(
            "LABEL CONFLICT:",
            len(labels) > 1,
        )


        for row in grouped_rows:

            print("-" * 100)

            print(
                "ROW:",
                row[
                    "row_id"
                ],
            )

            print(
                "PAIR:",
                row[
                    "pair_id"
                ],
            )

            print(
                "VARIANT:",
                row[
                    "variant"
                ][
                    "name"
                ],
            )

            print(
                "LABEL:",
                row[
                    "review"
                ][
                    "proposed_binary_label"
                ],
            )

            print(
                "SUITE:",
                row[
                    "suite"
                ],
            )

            print(
                "LEGITIMATE STRUCTURE:",
                row[
                    "provenance"
                ][
                    "legitimate_structure_id"
                ],
            )

            print(
                "ATTACKER STRUCTURE:",
                row[
                    "provenance"
                ][
                    "attacker_structure_id"
                ],
            )

            print(
                "VECTOR:",
                row[
                    "provenance"
                ][
                    "injection_vector_id"
                ],
            )

            print(
                "TOOL:",
                row[
                    "action"
                ][
                    "tool_name"
                ],
            )

            print(
                "ARGS:",
                compact_text(
                    row[
                        "action"
                    ][
                        "args"
                    ],
                    max_chars=1200,
                ),
            )


    print()
    print("=" * 80)

    print(
        f"Duplicate CSV: "
        f"{DUPLICATE_CSV_PATH}"
    )

    print(
        f"Report: {REPORT_PATH}"
    )

    print()
    print(
        "Smoke pool modified: no"
    )


if __name__ == "__main__":
    main()

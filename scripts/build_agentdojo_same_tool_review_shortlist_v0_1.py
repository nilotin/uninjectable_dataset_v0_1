from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


INTERIM_DIR = Path("data/interim")

PAIR_PATH = (
    INTERIM_DIR
    / "agentdojo_contextual_pair_plan_v0.1.jsonl"
)

CANDIDATE_PATH = (
    INTERIM_DIR
    / "agentdojo_same_tool_conversion_candidates_v0.1.jsonl"
)

SHORTLIST_PATH = (
    INTERIM_DIR
    / "agentdojo_same_tool_review_shortlist_v0.1.jsonl"
)

SHORTLIST_CSV_PATH = (
    INTERIM_DIR
    / "agentdojo_same_tool_review_shortlist_v0.1.csv"
)

REPORT_PATH = (
    INTERIM_DIR
    / "agentdojo_same_tool_review_shortlist_v0.1_report.json"
)


EXPECTED_PAIR_COUNT = 100
EXPECTED_CURRENT_SAME_TOOL_COUNT = 4
TARGET_ADDITIONAL_SAME_TOOL_COUNT = 16
TARGET_FINAL_SAME_TOOL_COUNT = 20


# Scarce tools are processed first so that common tools do not
# consume all eligible pair slots.
TOOL_QUOTAS = {
    "update_password": 1,
    "update_scheduled_transaction": 1,
    "get_webpage": 1,
    "post_webpage": 1,
    "reserve_hotel": 2,
    "send_direct_message": 2,
    "send_money": 3,
    "send_email": 3,
    "create_calendar_event": 2,
}


IMPACT_RANK = {
    "low": 1,
    "medium": 2,
    "high": 3,
}


CHANGE_RANK = {
    "attacker_only": 3,
    "user_only": 2,
    "both_changed": 1,
    "unchanged": 0,
}


ALIGNMENT_RANK = {
    "exact_environment_object_match": 2,
    "retrieval_channel_match": 1,
}


def load_jsonl(
    path: Path,
) -> list[dict[str, Any]]:

    if not path.exists():
        raise FileNotFoundError(
            f"Missing file: {path}"
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


def write_csv(
    path: Path,
    rows: list[dict[str, Any]],
) -> None:

    if not rows:
        raise ValueError(
            "Shortlist CSV cannot be empty."
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


def stable_hash_number(
    *values: Any,
) -> int:

    text = "||".join(
        str(value)
        for value in values
    )

    digest = hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()

    return int(
        digest[:16],
        16,
    )


def json_text(
    value: Any,
) -> str:

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
    )


def candidate_priority(
    candidate: dict[str, Any],
    selected_user_usage: Counter[str],
    selected_attacker_usage: Counter[str],
) -> tuple[int, ...]:

    candidate_user_id = str(
        candidate[
            "candidate_user_blueprint_id"
        ]
    )

    candidate_attacker_id = str(
        candidate[
            "candidate_attacker_blueprint_id"
        ]
    )

    return (
        ALIGNMENT_RANK.get(
            str(
                candidate[
                    "alignment_type"
                ]
            ),
            0,
        ),

        CHANGE_RANK.get(
            str(
                candidate[
                    "change_type"
                ]
            ),
            0,
        ),

        -selected_user_usage[
            candidate_user_id
        ],

        -selected_attacker_usage[
            candidate_attacker_id
        ],

        IMPACT_RANK.get(
            str(
                candidate[
                    "attacker_action_impact"
                ]
            ),
            0,
        ),

        IMPACT_RANK.get(
            str(
                candidate[
                    "authorized_action_impact"
                ]
            ),
            0,
        ),

        -int(
            candidate.get(
                "candidate_rank",
                999,
            )
        ),

        stable_hash_number(
            candidate[
                "pair_id"
            ],
            candidate_user_id,
            candidate_attacker_id,
            candidate[
                "shared_tool_name"
            ],
        ),
    )


def main() -> None:

    pairs = load_jsonl(
        PAIR_PATH
    )

    candidates = load_jsonl(
        CANDIDATE_PATH
    )


    if len(pairs) != EXPECTED_PAIR_COUNT:
        raise ValueError(
            f"Expected 100 pairs, found {len(pairs)}."
        )


    pair_by_id = {
        str(
            pair[
                "pair_id"
            ]
        ): pair
        for pair in pairs
    }


    current_same_tool_count = sum(
        1
        for pair in pairs
        if pair[
            "pairing_diagnostics"
        ][
            "same_tool_name_across_variants"
        ]
    )

    if (
        current_same_tool_count
        !=
        EXPECTED_CURRENT_SAME_TOOL_COUNT
    ):
        raise ValueError(
            "Expected four current same-tool pairs, "
            f"found {current_same_tool_count}."
        )


    if (
        sum(
            TOOL_QUOTAS.values()
        )
        !=
        TARGET_ADDITIONAL_SAME_TOOL_COUNT
    ):
        raise ValueError(
            "Tool quotas do not sum to 16."
        )


    # --------------------------------------------------------
    # Current reuse and triple inventory
    # --------------------------------------------------------

    projected_user_usage: Counter[str] = Counter(
        str(
            pair[
                "legitimate_context"
            ][
                "blueprint_id"
            ]
        )
        for pair in pairs
    )

    projected_attacker_usage: Counter[str] = Counter(
        str(
            pair[
                "attacker_context"
            ][
                "blueprint_id"
            ]
        )
        for pair in pairs
    )


    baseline_max_user_reuse = max(
        projected_user_usage.values()
    )

    baseline_max_attacker_reuse = max(
        projected_attacker_usage.values()
    )


    # Allow at most one additional use beyond the current maximum.
    user_reuse_cap = (
        baseline_max_user_reuse
        +
        1
    )

    attacker_reuse_cap = (
        baseline_max_attacker_reuse
        +
        1
    )


    current_triples = {
        (
            str(
                pair[
                    "legitimate_context"
                ][
                    "blueprint_id"
                ]
            ),
            str(
                pair[
                    "attacker_context"
                ][
                    "blueprint_id"
                ]
            ),
            str(
                pair[
                    "injection_surface"
                ][
                    "vector_id"
                ]
            ),
        )
        for pair in pairs
    }


    candidates_by_tool: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)


    for candidate in candidates:

        tool_name = str(
            candidate[
                "shared_tool_name"
            ]
        )

        if tool_name in TOOL_QUOTAS:

            candidates_by_tool[
                tool_name
            ].append(
                candidate
            )


    # --------------------------------------------------------
    # Greedy balanced selection
    # --------------------------------------------------------

    selected: list[
        dict[str, Any]
    ] = []

    selected_pair_ids: set[str] = set()

    selected_triples: set[
        tuple[str, str, str]
    ] = set()

    selected_user_usage: Counter[str] = Counter()
    selected_attacker_usage: Counter[str] = Counter()

    selected_tool_counts: Counter[str] = Counter()


    for tool_name, quota in TOOL_QUOTAS.items():

        tool_candidates = list(
            candidates_by_tool[
                tool_name
            ]
        )


        for _ in range(quota):

            eligible: list[
                dict[str, Any]
            ] = []


            for candidate in tool_candidates:

                pair_id = str(
                    candidate[
                        "pair_id"
                    ]
                )

                if pair_id in selected_pair_ids:
                    continue


                pair = pair_by_id.get(
                    pair_id
                )

                if pair is None:
                    raise ValueError(
                        f"Candidate references missing pair: "
                        f"{pair_id}"
                    )


                current_user_id = str(
                    pair[
                        "legitimate_context"
                    ][
                        "blueprint_id"
                    ]
                )

                current_attacker_id = str(
                    pair[
                        "attacker_context"
                    ][
                        "blueprint_id"
                    ]
                )

                candidate_user_id = str(
                    candidate[
                        "candidate_user_blueprint_id"
                    ]
                )

                candidate_attacker_id = str(
                    candidate[
                        "candidate_attacker_blueprint_id"
                    ]
                )

                vector_id = str(
                    candidate[
                        "vector_id"
                    ]
                )


                prospective_triple = (
                    candidate_user_id,
                    candidate_attacker_id,
                    vector_id,
                )


                if (
                    prospective_triple
                    in
                    selected_triples
                ):
                    continue


                # Avoid reproducing a triple that already belongs
                # to another pair.
                if (
                    prospective_triple
                    in
                    current_triples
                ):
                    continue


                projected_candidate_user_count = (
                    projected_user_usage[
                        candidate_user_id
                    ]
                    +
                    1
                    -
                    (
                        1
                        if candidate_user_id
                        ==
                        current_user_id
                        else 0
                    )
                )

                projected_candidate_attacker_count = (
                    projected_attacker_usage[
                        candidate_attacker_id
                    ]
                    +
                    1
                    -
                    (
                        1
                        if candidate_attacker_id
                        ==
                        current_attacker_id
                        else 0
                    )
                )


                if (
                    projected_candidate_user_count
                    >
                    user_reuse_cap
                ):
                    continue

                if (
                    projected_candidate_attacker_count
                    >
                    attacker_reuse_cap
                ):
                    continue


                eligible.append(
                    candidate
                )


            if not eligible:
                raise ValueError(
                    "Unable to fill same-tool quota for "
                    f"{tool_name}. Already selected "
                    f"{selected_tool_counts[tool_name]} "
                    f"of {quota}."
                )


            chosen = max(
                eligible,
                key=lambda candidate: (
                    candidate_priority(
                        candidate,
                        selected_user_usage,
                        selected_attacker_usage,
                    )
                ),
            )


            pair_id = str(
                chosen[
                    "pair_id"
                ]
            )

            pair = pair_by_id[
                pair_id
            ]

            current_user_id = str(
                pair[
                    "legitimate_context"
                ][
                    "blueprint_id"
                ]
            )

            current_attacker_id = str(
                pair[
                    "attacker_context"
                ][
                    "blueprint_id"
                ]
            )

            candidate_user_id = str(
                chosen[
                    "candidate_user_blueprint_id"
                ]
            )

            candidate_attacker_id = str(
                chosen[
                    "candidate_attacker_blueprint_id"
                ]
            )

            vector_id = str(
                chosen[
                    "vector_id"
                ]
            )


            projected_user_usage[
                current_user_id
            ] -= 1

            projected_user_usage[
                candidate_user_id
            ] += 1

            projected_attacker_usage[
                current_attacker_id
            ] -= 1

            projected_attacker_usage[
                candidate_attacker_id
            ] += 1


            selected_pair_ids.add(
                pair_id
            )

            selected_triples.add(
                (
                    candidate_user_id,
                    candidate_attacker_id,
                    vector_id,
                )
            )

            selected_user_usage[
                candidate_user_id
            ] += 1

            selected_attacker_usage[
                candidate_attacker_id
            ] += 1

            selected_tool_counts[
                tool_name
            ] += 1

            selected.append(
                chosen
            )


    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    if len(selected) != (
        TARGET_ADDITIONAL_SAME_TOOL_COUNT
    ):
        raise ValueError(
            "Expected 16 selected conversions, "
            f"found {len(selected)}."
        )


    if dict(
        selected_tool_counts
    ) != TOOL_QUOTAS:
        raise ValueError(
            "Unexpected tool quota result.\n"
            f"Expected: {TOOL_QUOTAS}\n"
            f"Found: {dict(selected_tool_counts)}"
        )


    if len(selected_pair_ids) != len(
        selected
    ):
        raise ValueError(
            "A pair was selected more than once."
        )


    projected_final_same_tool_count = (
        current_same_tool_count
        +
        len(selected)
    )

    if (
        projected_final_same_tool_count
        !=
        TARGET_FINAL_SAME_TOOL_COUNT
    ):
        raise ValueError(
            "Expected projected final same-tool count "
            f"20, found "
            f"{projected_final_same_tool_count}."
        )


    projected_max_user_reuse = max(
        projected_user_usage.values()
    )

    projected_max_attacker_reuse = max(
        projected_attacker_usage.values()
    )


    # --------------------------------------------------------
    # Build review artifacts
    # --------------------------------------------------------

    selected.sort(
        key=lambda candidate: (
            candidate[
                "suite"
            ],
            candidate[
                "shared_tool_name"
            ],
            candidate[
                "pair_id"
            ],
        )
    )


    shortlist_records: list[
        dict[str, Any]
    ] = []

    csv_rows: list[
        dict[str, Any]
    ] = []


    for shortlist_index, candidate in enumerate(
        selected,
        start=1,
    ):

        pair = pair_by_id[
            candidate[
                "pair_id"
            ]
        ]

        record = {
            "shortlist_id": (
                f"same_tool_review_"
                f"{shortlist_index:02d}"
            ),

            "selection_version": "0.1",

            "pair_id": (
                candidate[
                    "pair_id"
                ]
            ),

            "suite": (
                candidate[
                    "suite"
                ]
            ),

            "vector_id": (
                candidate[
                    "vector_id"
                ]
            ),

            "surface_type": (
                pair[
                    "injection_surface"
                ][
                    "surface_type"
                ]
            ),

            "retrieval_channel": (
                candidate[
                    "retrieval_channel"
                ]
            ),

            "alignment_type": (
                candidate[
                    "alignment_type"
                ]
            ),

            "change_type": (
                candidate[
                    "change_type"
                ]
            ),

            "shared_tool_name": (
                candidate[
                    "shared_tool_name"
                ]
            ),

            "current_pair": {
                "user_blueprint_id": (
                    candidate[
                        "current_user_blueprint_id"
                    ]
                ),

                "user_structure_id": (
                    pair[
                        "legitimate_context"
                    ][
                        "structure_id"
                    ]
                ),

                "user_goal": (
                    pair[
                        "legitimate_context"
                    ][
                        "prompt_or_goal"
                    ]
                ),

                "attacker_blueprint_id": (
                    candidate[
                        "current_attacker_blueprint_id"
                    ]
                ),

                "attacker_structure_id": (
                    pair[
                        "attacker_context"
                    ][
                        "structure_id"
                    ]
                ),

                "attacker_goal": (
                    pair[
                        "attacker_context"
                    ][
                        "prompt_or_goal"
                    ]
                ),

                "authorized_action": (
                    pair[
                        "selected_actions"
                    ][
                        "authorized_user_action"
                    ]
                ),

                "attacker_action": (
                    pair[
                        "selected_actions"
                    ][
                        "attacker_target_action"
                    ]
                ),
            },

            "proposed_pair": {
                "user_blueprint_id": (
                    candidate[
                        "candidate_user_blueprint_id"
                    ]
                ),

                "user_structure_id": (
                    candidate[
                        "candidate_user_structure_id"
                    ]
                ),

                "user_goal": (
                    candidate[
                        "candidate_user_goal"
                    ]
                ),

                "attacker_blueprint_id": (
                    candidate[
                        "candidate_attacker_blueprint_id"
                    ]
                ),

                "attacker_structure_id": (
                    candidate[
                        "candidate_attacker_structure_id"
                    ]
                ),

                "attacker_goal": (
                    candidate[
                        "candidate_attacker_goal"
                    ]
                ),

                "authorized_action": {
                    "function": (
                        candidate[
                            "shared_tool_name"
                        ]
                    ),

                    "args": (
                        candidate[
                            "authorized_args"
                        ]
                    ),

                    "action_impact": (
                        candidate[
                            "authorized_action_impact"
                        ]
                    ),
                },

                "attacker_action": {
                    "function": (
                        candidate[
                            "shared_tool_name"
                        ]
                    ),

                    "args": (
                        candidate[
                            "attacker_args"
                        ]
                    ),

                    "action_impact": (
                        candidate[
                            "attacker_action_impact"
                        ]
                    ),
                },
            },

            "review": {
                "status": (
                    "pending_human_review"
                ),

                "decision": None,

                "review_note": None,
            },

            "important_note": (
                "Selection does not modify the pair plan. "
                "Approval must confirm contextual plausibility, "
                "authorization contrast, and argument-level "
                "difference."
            ),
        }

        shortlist_records.append(
            record
        )


        csv_rows.append(
            {
                "shortlist_id": (
                    record[
                        "shortlist_id"
                    ]
                ),

                "pair_id": (
                    record[
                        "pair_id"
                    ]
                ),

                "suite": (
                    record[
                        "suite"
                    ]
                ),

                "vector_id": (
                    record[
                        "vector_id"
                    ]
                ),

                "surface_type": (
                    record[
                        "surface_type"
                    ]
                ),

                "alignment_type": (
                    record[
                        "alignment_type"
                    ]
                ),

                "change_type": (
                    record[
                        "change_type"
                    ]
                ),

                "shared_tool_name": (
                    record[
                        "shared_tool_name"
                    ]
                ),

                "current_user_structure_id": (
                    record[
                        "current_pair"
                    ][
                        "user_structure_id"
                    ]
                ),

                "proposed_user_structure_id": (
                    record[
                        "proposed_pair"
                    ][
                        "user_structure_id"
                    ]
                ),

                "current_attacker_structure_id": (
                    record[
                        "current_pair"
                    ][
                        "attacker_structure_id"
                    ]
                ),

                "proposed_attacker_structure_id": (
                    record[
                        "proposed_pair"
                    ][
                        "attacker_structure_id"
                    ]
                ),

                "proposed_user_goal": (
                    record[
                        "proposed_pair"
                    ][
                        "user_goal"
                    ]
                ),

                "proposed_attacker_goal": (
                    record[
                        "proposed_pair"
                    ][
                        "attacker_goal"
                    ]
                ),

                "authorized_args": json_text(
                    record[
                        "proposed_pair"
                    ][
                        "authorized_action"
                    ][
                        "args"
                    ]
                ),

                "attacker_args": json_text(
                    record[
                        "proposed_pair"
                    ][
                        "attacker_action"
                    ][
                        "args"
                    ]
                ),

                "review_decision": "",

                "review_note": "",
            }
        )


    write_jsonl(
        SHORTLIST_PATH,
        shortlist_records,
    )

    write_csv(
        SHORTLIST_CSV_PATH,
        csv_rows,
    )


    suite_counts = Counter(
        record[
            "suite"
        ]
        for record in shortlist_records
    )

    alignment_counts = Counter(
        record[
            "alignment_type"
        ]
        for record in shortlist_records
    )

    change_counts = Counter(
        record[
            "change_type"
        ]
        for record in shortlist_records
    )


    report = {
        "selection_version": "0.1",

        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "current_same_tool_pair_count": (
            current_same_tool_count
        ),

        "selected_review_candidate_count": (
            len(shortlist_records)
        ),

        "projected_final_same_tool_pair_count": (
            projected_final_same_tool_count
        ),

        "tool_quotas": TOOL_QUOTAS,

        "selected_tool_counts": dict(
            selected_tool_counts
        ),

        "selected_suite_counts": dict(
            suite_counts
        ),

        "alignment_type_counts": dict(
            alignment_counts
        ),

        "change_type_counts": dict(
            change_counts
        ),

        "baseline_max_user_reuse": (
            baseline_max_user_reuse
        ),

        "projected_max_user_reuse": (
            projected_max_user_reuse
        ),

        "user_reuse_cap": (
            user_reuse_cap
        ),

        "baseline_max_attacker_reuse": (
            baseline_max_attacker_reuse
        ),

        "projected_max_attacker_reuse": (
            projected_max_attacker_reuse
        ),

        "attacker_reuse_cap": (
            attacker_reuse_cap
        ),

        "pair_plan_modified": False,

        "runtime_label_count": 0,

        "important_notes": [
            (
                "The shortlist contains sixteen proposed "
                "same-tool conversions."
            ),
            (
                "Each proposal affects exactly one existing "
                "pair and preserves its injection vector."
            ),
            (
                "Attacker-only changes are preferred over "
                "user-only changes; both-changed proposals "
                "have the lowest priority."
            ),
            (
                "Tool quotas prevent calendar and email "
                "candidates from dominating the shortlist."
            ),
            (
                "No proposal is applied before human review."
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
        "AGENTDOJO SAME-TOOL REVIEW SHORTLIST v0.1 CREATED"
    )
    print("=" * 80)

    print()
    print(
        "Current same-tool pairs:",
        current_same_tool_count,
    )

    print(
        "Selected review candidates:",
        len(shortlist_records),
    )

    print(
        "Projected same-tool pairs after approval:",
        projected_final_same_tool_count,
    )

    print()
    print(
        "Selected tools:"
    )

    for tool_name, count in (
        TOOL_QUOTAS.items()
    ):
        print(
            f"  {tool_name}: "
            f"{selected_tool_counts[tool_name]}"
        )

    print()
    print(
        "Selected suites:"
    )

    for suite, count in sorted(
        suite_counts.items()
    ):
        print(
            f"  {suite}: {count}"
        )

    print()
    print(
        "Change types:"
    )

    for change_type, count in sorted(
        change_counts.items()
    ):
        print(
            f"  {change_type}: {count}"
        )

    print()
    print(
        "Alignment types:"
    )

    for alignment, count in sorted(
        alignment_counts.items()
    ):
        print(
            f"  {alignment}: {count}"
        )

    print()
    print(
        "Reuse:"
    )

    print(
        "  user max:",
        baseline_max_user_reuse,
        "→",
        projected_max_user_reuse,
        f"(cap {user_reuse_cap})",
    )

    print(
        "  attacker max:",
        baseline_max_attacker_reuse,
        "→",
        projected_max_attacker_reuse,
        f"(cap {attacker_reuse_cap})",
    )

    print()
    print(
        f"Shortlist JSONL: {SHORTLIST_PATH}"
    )

    print(
        f"Shortlist CSV: {SHORTLIST_CSV_PATH}"
    )

    print(
        f"Report: {REPORT_PATH}"
    )

    print()
    print(
        "Pair plan modified: no"
    )

    print(
        "Runtime labels generated: 0"
    )


if __name__ == "__main__":
    main()

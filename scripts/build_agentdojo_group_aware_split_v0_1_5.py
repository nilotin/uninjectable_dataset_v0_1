from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


STRUCTURED_POOL_PATH = Path(
    "data/processed/"
    "agentdojo_contextual_action_attempt_labeled_pool_v0.1.5.jsonl"
)

TRAINING_VIEW_PATH = Path(
    "data/processed/"
    "agentdojo_bert_training_view_v0.1.5.jsonl"
)

REVIEW_LEDGER_PATH = Path(
    "data/interim/"
    "agentdojo_action_attempt_human_review_master_v0.1.5.csv"
)

CHECKPOINT_MANIFEST_PATH = Path(
    "data/processed/"
    "agentdojo_v0.1.5_sha256.txt"
)


OUTPUT_DIRECTORY = Path(
    "data/processed/"
    "agentdojo_group_aware_split_v0.1.5"
)

ASSIGNMENTS_PATH = (
    OUTPUT_DIRECTORY
    / "agentdojo_group_split_assignments_v0.1.5.jsonl"
)

REPORT_PATH = (
    OUTPUT_DIRECTORY
    / "agentdojo_group_split_v0.1.5_report.json"
)


SPLIT_NAMES = (
    "train",
    "validation",
    "test",
)

TARGET_GROUP_COUNTS = {
    "train": 68,
    "validation": 15,
    "test": 14,
}

EXPECTED_APPROVED_PAIR_COUNT = 97
EXPECTED_RUNTIME_ROW_COUNT = 194
EXPECTED_EXCLUDED_PAIR_COUNT = 3

SPLIT_SEED = (
    "agentdojo-v0.1.5-group-split-2026-07-21"
)


def load_jsonl(
    path: Path,
) -> list[dict[str, Any]]:

    if not path.exists():
        raise FileNotFoundError(
            f"Missing JSONL file: {path}"
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
                    f"Invalid JSONL in {path}, "
                    f"line {line_number}."
                ) from error

    return rows


def load_csv(
    path: Path,
) -> tuple[list[str], list[dict[str, str]]]:

    if not path.exists():
        raise FileNotFoundError(
            f"Missing CSV file: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:

        reader = csv.DictReader(file)

        if reader.fieldnames is None:
            raise ValueError(
                f"CSV has no header: {path}"
            )

        return (
            list(reader.fieldnames),
            list(reader),
        )


def write_jsonl(
    path: Path,
    rows: list[dict[str, Any]],
) -> None:

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
    ) as file:

        for row in rows:

            file.write(
                json.dumps(
                    row,
                    ensure_ascii=False,
                )
            )

            file.write("\n")


def sha256_file(
    path: Path,
) -> str:

    digest = hashlib.sha256()

    with path.open(
        "rb"
    ) as file:

        while True:

            chunk = file.read(
                1024 * 1024
            )

            if not chunk:
                break

            digest.update(chunk)

    return digest.hexdigest()


def verify_checkpoint() -> int:

    if not CHECKPOINT_MANIFEST_PATH.exists():
        raise FileNotFoundError(
            "Missing v0.1.5 SHA-256 manifest."
        )

    verified = 0

    for line in (
        CHECKPOINT_MANIFEST_PATH
        .read_text(
            encoding="utf-8"
        )
        .splitlines()
    ):

        line = line.strip()

        if not line:
            continue

        parts = line.split(
            None,
            1,
        )

        if len(parts) != 2:
            raise ValueError(
                f"Invalid manifest line: {line}"
            )

        expected_hash, raw_path = parts

        artifact_path = Path(
            raw_path.strip()
        )

        if not artifact_path.exists():
            raise FileNotFoundError(
                f"Checkpoint artifact missing: "
                f"{artifact_path}"
            )

        actual_hash = sha256_file(
            artifact_path
        )

        if actual_hash != expected_hash:
            raise ValueError(
                "v0.1.5 checkpoint integrity "
                "validation failed:\n"
                f"Artifact: {artifact_path}\n"
                f"Expected: {expected_hash}\n"
                f"Actual:   {actual_hash}"
            )

        verified += 1

    if verified != 4:
        raise ValueError(
            f"Expected four hashes, verified "
            f"{verified}."
        )

    return verified


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

    return int(
        match.group(1)
    )


def variant_name(
    row: dict[str, Any],
) -> str:

    value = row.get(
        "variant"
    )

    if isinstance(
        value,
        dict,
    ):
        value = value.get(
            "name"
        )

    return str(value)


def variant_order(
    row: dict[str, Any],
) -> int:

    order = {
        "safe": 0,
        "risky": 1,
    }

    name = variant_name(row)

    if name not in order:
        raise ValueError(
            f"Unexpected variant: {name}"
        )

    return order[name]


def stable_sort_key(
    group_id: str,
) -> str:

    value = (
        SPLIT_SEED
        +
        "|"
        +
        group_id
    )

    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def same_tool_flag(
    structured_row: dict[str, Any],
) -> bool:

    provenance = structured_row.get(
        "provenance",
        {},
    )

    return bool(
        provenance.get(
            "same_tool_minimal_pair",
            False,
        )
    )


def allocate_strata(
    stratum_counts: dict[str, int],
) -> dict[str, dict[str, int]]:

    total_groups = sum(
        stratum_counts.values()
    )

    if total_groups != (
        EXPECTED_APPROVED_PAIR_COUNT
    ):
        raise ValueError(
            f"Expected 97 groups, found "
            f"{total_groups}."
        )

    allocation: dict[
        str,
        dict[str, int],
    ] = {}

    ideal: dict[
        tuple[str, str],
        float,
    ] = {}

    for stratum, count in sorted(
        stratum_counts.items()
    ):

        allocation[stratum] = {}

        for split in SPLIT_NAMES:

            target_ratio = (
                TARGET_GROUP_COUNTS[split]
                /
                EXPECTED_APPROVED_PAIR_COUNT
            )

            ideal_value = (
                count
                *
                target_ratio
            )

            ideal[
                (
                    stratum,
                    split,
                )
            ] = ideal_value

            allocation[
                stratum
            ][
                split
            ] = math.floor(
                ideal_value
            )

    row_remaining = {
        stratum: (
            stratum_counts[stratum]
            -
            sum(
                allocation[
                    stratum
                ].values()
            )
        )
        for stratum in stratum_counts
    }

    column_remaining = {
        split: (
            TARGET_GROUP_COUNTS[split]
            -
            sum(
                allocation[stratum][split]
                for stratum in stratum_counts
            )
        )
        for split in SPLIT_NAMES
    }

    while any(
        remaining > 0
        for remaining in row_remaining.values()
    ):

        candidates = []

        for stratum in sorted(
            stratum_counts
        ):

            if (
                row_remaining[stratum]
                <=
                0
            ):
                continue

            for split_index, split in enumerate(
                SPLIT_NAMES
            ):

                if (
                    column_remaining[split]
                    <=
                    0
                ):
                    continue

                ideal_value = ideal[
                    (
                        stratum,
                        split,
                    )
                ]

                current_value = allocation[
                    stratum
                ][
                    split
                ]

                if (
                    current_value
                    >=
                    math.ceil(
                        ideal_value
                    )
                ):
                    continue

                fractional_remainder = (
                    ideal_value
                    -
                    math.floor(
                        ideal_value
                    )
                )

                candidates.append(
                    (
                        -fractional_remainder,
                        stratum,
                        split_index,
                        split,
                    )
                )

        if not candidates:
            raise ValueError(
                "Could not complete deterministic "
                "stratified allocation."
            )

        candidates.sort()

        _, stratum, _, split = (
            candidates[0]
        )

        allocation[
            stratum
        ][
            split
        ] += 1

        row_remaining[
            stratum
        ] -= 1

        column_remaining[
            split
        ] -= 1

    if any(
        value != 0
        for value in column_remaining.values()
    ):
        raise ValueError(
            "Split target allocation failed: "
            f"{column_remaining}"
        )

    return allocation


def main() -> None:

    hashes_verified_before = (
        verify_checkpoint()
    )


    structured_rows = load_jsonl(
        STRUCTURED_POOL_PATH
    )

    training_rows = load_jsonl(
        TRAINING_VIEW_PATH
    )

    _, ledger_rows = load_csv(
        REVIEW_LEDGER_PATH
    )


    if (
        len(structured_rows)
        !=
        EXPECTED_RUNTIME_ROW_COUNT
    ):
        raise ValueError(
            "Expected 194 structured rows, "
            f"found {len(structured_rows)}."
        )


    if (
        len(training_rows)
        !=
        EXPECTED_RUNTIME_ROW_COUNT
    ):
        raise ValueError(
            "Expected 194 training rows, "
            f"found {len(training_rows)}."
        )


    ledger_counts = Counter(
        row.get(
            "cumulative_review_decision",
            "",
        )
        for row in ledger_rows
    )


    expected_ledger_counts = {
        "approve_pair": (
            EXPECTED_APPROVED_PAIR_COUNT
        ),

        "exclude_pair": (
            EXPECTED_EXCLUDED_PAIR_COUNT
        ),
    }


    if (
        dict(ledger_counts)
        !=
        expected_ledger_counts
    ):
        raise ValueError(
            "Unexpected review-ledger counts:\n"
            f"Expected: {expected_ledger_counts}\n"
            f"Found: {dict(ledger_counts)}"
        )


    structured_by_row_id = {
        str(row["row_id"]): row
        for row in structured_rows
    }


    if (
        len(structured_by_row_id)
        !=
        EXPECTED_RUNTIME_ROW_COUNT
    ):
        raise ValueError(
            "Duplicate structured row IDs."
        )


    training_by_row_id = {
        str(row["row_id"]): row
        for row in training_rows
    }


    if (
        len(training_by_row_id)
        !=
        EXPECTED_RUNTIME_ROW_COUNT
    ):
        raise ValueError(
            "Duplicate training row IDs."
        )


    if (
        set(structured_by_row_id)
        !=
        set(training_by_row_id)
    ):
        raise ValueError(
            "Structured and training row IDs "
            "do not match."
        )


    groups: dict[
        str,
        dict[str, Any],
    ] = {}


    for row_id, training_row in (
        training_by_row_id.items()
    ):

        structured_row = (
            structured_by_row_id[
                row_id
            ]
        )

        pair_id = str(
            structured_row[
                "pair_id"
            ]
        )

        training_pair_id = str(
            training_row[
                "pair_id"
            ]
        )


        if training_pair_id != pair_id:
            raise ValueError(
                f"Pair mismatch for {row_id}."
            )


        session_group_id = str(
            structured_row.get(
                "session_group_id"
            )
            or
            training_row.get(
                "session_group_id"
            )
            or
            pair_id
        )


        suite = str(
            structured_row[
                "suite"
            ]
        )

        same_tool = same_tool_flag(
            structured_row
        )


        group = groups.setdefault(
            session_group_id,
            {
                "session_group_id": (
                    session_group_id
                ),

                "pair_ids": set(),

                "suite": suite,

                "same_tool": same_tool,

                "row_ids": [],

                "labels": [],

                "variants": [],
            },
        )


        if group["suite"] != suite:
            raise ValueError(
                "A session group spans multiple "
                f"suites: {session_group_id}"
            )


        if (
            group["same_tool"]
            !=
            same_tool
        ):
            raise ValueError(
                "Inconsistent same-tool flag for "
                f"{session_group_id}."
            )


        group[
            "pair_ids"
        ].add(
            pair_id
        )

        group[
            "row_ids"
        ].append(
            row_id
        )

        group[
            "labels"
        ].append(
            int(
                training_row[
                    "general_risk_label"
                ]
            )
        )

        group[
            "variants"
        ].append(
            variant_name(
                structured_row
            )
        )


    if (
        len(groups)
        !=
        EXPECTED_APPROVED_PAIR_COUNT
    ):
        raise ValueError(
            "Expected 97 session groups, "
            f"found {len(groups)}."
        )


    normalized_groups = []


    for group_id, group in groups.items():

        if len(
            group[
                "pair_ids"
            ]
        ) != 1:
            raise ValueError(
                f"{group_id} contains multiple "
                "pair IDs."
            )


        if len(
            group[
                "row_ids"
            ]
        ) != 2:
            raise ValueError(
                f"{group_id} has "
                f"{len(group['row_ids'])} rows."
            )


        if Counter(
            group[
                "labels"
            ]
        ) != {
            0: 1,
            1: 1,
        }:
            raise ValueError(
                f"{group_id} does not contain "
                "one safe and one risky row."
            )


        if set(
            group[
                "variants"
            ]
        ) != {
            "safe",
            "risky",
        }:
            raise ValueError(
                f"{group_id} has invalid variants."
            )


        pair_id = next(
            iter(
                group[
                    "pair_ids"
                ]
            )
        )


        stratum = (
            f"{group['suite']}"
            f"|same_tool="
            f"{str(group['same_tool']).lower()}"
        )


        normalized_groups.append(
            {
                "session_group_id": (
                    group_id
                ),

                "pair_id": pair_id,

                "suite": group[
                    "suite"
                ],

                "same_tool": group[
                    "same_tool"
                ],

                "stratum": stratum,

                "row_ids": sorted(
                    group[
                        "row_ids"
                    ]
                ),

                "labels": {
                    "0": 1,
                    "1": 1,
                },
            }
        )


    stratum_counts = Counter(
        group[
            "stratum"
        ]
        for group in normalized_groups
    )


    allocation = allocate_strata(
        dict(
            stratum_counts
        )
    )


    groups_by_stratum: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)


    for group in normalized_groups:

        groups_by_stratum[
            group[
                "stratum"
            ]
        ].append(group)


    assignment_by_group: dict[
        str,
        str,
    ] = {}


    for stratum in sorted(
        groups_by_stratum
    ):

        stratum_groups = sorted(
            groups_by_stratum[
                stratum
            ],
            key=lambda group: (
                stable_sort_key(
                    group[
                        "session_group_id"
                    ]
                )
            ),
        )


        cursor = 0


        for split in SPLIT_NAMES:

            count = allocation[
                stratum
            ][
                split
            ]

            selected = stratum_groups[
                cursor:
                cursor + count
            ]

            cursor += count


            for group in selected:

                group_id = group[
                    "session_group_id"
                ]

                if (
                    group_id
                    in
                    assignment_by_group
                ):
                    raise ValueError(
                        "Session group assigned "
                        f"twice: {group_id}"
                    )

                assignment_by_group[
                    group_id
                ] = split


        if cursor != len(
            stratum_groups
        ):
            raise ValueError(
                f"Not all groups assigned in "
                f"stratum {stratum}."
            )


    if (
        len(assignment_by_group)
        !=
        EXPECTED_APPROVED_PAIR_COUNT
    ):
        raise ValueError(
            "Not all session groups received "
            "a split assignment."
        )


    assignment_rows = []


    for group in normalized_groups:

        split = assignment_by_group[
            group[
                "session_group_id"
            ]
        ]

        assignment_rows.append(
            {
                **group,

                "split": split,

                "split_seed": (
                    SPLIT_SEED
                ),
            }
        )


    assignment_rows.sort(
        key=lambda row: pair_number(
            row[
                "pair_id"
            ]
        )
    )


    split_structured: dict[
        str,
        list[dict[str, Any]],
    ] = {
        split: []
        for split in SPLIT_NAMES
    }

    split_training: dict[
        str,
        list[dict[str, Any]],
    ] = {
        split: []
        for split in SPLIT_NAMES
    }


    for structured_row in structured_rows:

        group_id = str(
            structured_row.get(
                "session_group_id"
            )
            or
            structured_row[
                "pair_id"
            ]
        )

        split = assignment_by_group[
            group_id
        ]

        split_structured[
            split
        ].append(
            structured_row
        )


    for training_row in training_rows:

        row_id = str(
            training_row[
                "row_id"
            ]
        )

        structured_row = (
            structured_by_row_id[
                row_id
            ]
        )

        group_id = str(
            structured_row.get(
                "session_group_id"
            )
            or
            structured_row[
                "pair_id"
            ]
        )

        split = assignment_by_group[
            group_id
        ]

        split_training[
            split
        ].append(
            training_row
        )


    for split in SPLIT_NAMES:

        split_structured[
            split
        ].sort(
            key=lambda row: (
                pair_number(
                    str(
                        row[
                            "pair_id"
                        ]
                    )
                ),

                variant_order(row),
            )
        )

        split_training[
            split
        ].sort(
            key=lambda row: (
                pair_number(
                    str(
                        row[
                            "pair_id"
                        ]
                    )
                ),

                variant_order(row),
            )
        )


    split_group_sets = {
        split: {
            row[
                "session_group_id"
            ]
            for row in assignment_rows
            if row[
                "split"
            ]
            ==
            split
        }
        for split in SPLIT_NAMES
    }


    for first_index, first_split in enumerate(
        SPLIT_NAMES
    ):

        for second_split in SPLIT_NAMES[
            first_index + 1:
        ]:

            overlap = (
                split_group_sets[
                    first_split
                ]
                &
                split_group_sets[
                    second_split
                ]
            )

            if overlap:
                raise ValueError(
                    "Session-group leakage between "
                    f"{first_split} and "
                    f"{second_split}:\n"
                    f"{sorted(overlap)}"
                )


    split_statistics = {}


    for split in SPLIT_NAMES:

        group_count = len(
            split_group_sets[
                split
            ]
        )

        expected_group_count = (
            TARGET_GROUP_COUNTS[
                split
            ]
        )


        if (
            group_count
            !=
            expected_group_count
        ):
            raise ValueError(
                f"{split} expected "
                f"{expected_group_count} groups, "
                f"found {group_count}."
            )


        expected_row_count = (
            expected_group_count
            *
            2
        )


        if (
            len(
                split_structured[
                    split
                ]
            )
            !=
            expected_row_count
        ):
            raise ValueError(
                f"{split} structured row count "
                "is incorrect."
            )


        if (
            len(
                split_training[
                    split
                ]
            )
            !=
            expected_row_count
        ):
            raise ValueError(
                f"{split} training row count "
                "is incorrect."
            )


        label_counts = Counter(
            int(
                row[
                    "general_risk_label"
                ]
            )
            for row in (
                split_training[
                    split
                ]
            )
        )


        expected_label_counts = {
            0: expected_group_count,
            1: expected_group_count,
        }


        if (
            dict(label_counts)
            !=
            expected_label_counts
        ):
            raise ValueError(
                f"{split} label counts are "
                f"incorrect: {dict(label_counts)}"
            )


        suite_group_counts = Counter(
            row[
                "suite"
            ]
            for row in assignment_rows
            if row[
                "split"
            ]
            ==
            split
        )


        same_tool_group_count = sum(
            bool(
                row[
                    "same_tool"
                ]
            )
            for row in assignment_rows
            if row[
                "split"
            ]
            ==
            split
        )


        split_statistics[
            split
        ] = {
            "group_count": group_count,

            "runtime_row_count": (
                expected_row_count
            ),

            "label_counts": {
                str(label): count
                for label, count in sorted(
                    label_counts.items()
                )
            },

            "suite_group_counts": dict(
                sorted(
                    suite_group_counts.items()
                )
            ),

            "same_tool_group_count": (
                same_tool_group_count
            ),
        }


    OUTPUT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )


    output_files = {}


    for split in SPLIT_NAMES:

        structured_output = (
            OUTPUT_DIRECTORY
            /
            (
                "agentdojo_contextual_action_attempt_"
                f"labeled_pool_v0.1.5_{split}.jsonl"
            )
        )

        training_output = (
            OUTPUT_DIRECTORY
            /
            (
                "agentdojo_bert_training_view_"
                f"v0.1.5_{split}.jsonl"
            )
        )


        write_jsonl(
            structured_output,
            split_structured[
                split
            ],
        )

        write_jsonl(
            training_output,
            split_training[
                split
            ],
        )


        output_files[
            split
        ] = {
            "structured_pool": str(
                structured_output
            ),

            "training_view": str(
                training_output
            ),
        }


    write_jsonl(
        ASSIGNMENTS_PATH,
        assignment_rows,
    )


    hashes_verified_after = (
        verify_checkpoint()
    )


    report = {
        "dataset": "agentdojo",

        "artifact_version": "0.1.5",

        "split_version": "0.1.5",

        "split_strategy": (
            "deterministic_group_aware_"
            "stratified_by_suite_and_same_tool"
        ),

        "split_seed": SPLIT_SEED,

        "source_approved_pair_count": (
            EXPECTED_APPROVED_PAIR_COUNT
        ),

        "source_runtime_row_count": (
            EXPECTED_RUNTIME_ROW_COUNT
        ),

        "excluded_pair_count": (
            EXPECTED_EXCLUDED_PAIR_COUNT
        ),

        "target_group_counts": (
            TARGET_GROUP_COUNTS
        ),

        "split_statistics": (
            split_statistics
        ),

        "stratum_counts": dict(
            sorted(
                stratum_counts.items()
            )
        ),

        "stratum_allocation": (
            allocation
        ),

        "validation": {
            "checkpoint_hashes_verified_before": (
                hashes_verified_before
            ),

            "checkpoint_hashes_verified_after": (
                hashes_verified_after
            ),

            "session_group_overlap_count": 0,

            "pair_overlap_count": 0,

            "all_groups_have_safe_and_risky_rows": (
                True
            ),

            "all_splits_label_balanced": True,

            "source_checkpoint_modified": False,
        },

        "assignments": str(
            ASSIGNMENTS_PATH
        ),

        "outputs": output_files,

        "important_notes": [
            (
                "Safe and risky rows from the same "
                "session_group_id are always placed "
                "in the same split."
            ),

            (
                "Each split contains exactly one safe "
                "and one risky row per assigned pair."
            ),

            (
                "The three excluded pairs are absent "
                "from every split."
            ),

            (
                "The immutable v0.1.5 checkpoint "
                "artifacts were not modified."
            ),

            (
                "The test split should remain sealed "
                "until final model evaluation."
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
        "AGENTDOJO GROUP-AWARE SPLIT "
        "v0.1.5 CREATED"
    )

    print("=" * 80)

    print()

    print(
        "Checkpoint hashes verified before:",
        hashes_verified_before,
    )

    print(
        "Checkpoint hashes verified after:",
        hashes_verified_after,
    )

    print()

    for split in SPLIT_NAMES:

        statistics = split_statistics[
            split
        ]

        print(
            f"{split.upper()}:"
        )

        print(
            "  Groups:",
            statistics[
                "group_count"
            ],
        )

        print(
            "  Rows:",
            statistics[
                "runtime_row_count"
            ],
        )

        print(
            "  Labels:",
            statistics[
                "label_counts"
            ],
        )

        print(
            "  Suites:",
            statistics[
                "suite_group_counts"
            ],
        )

        print(
            "  Same-tool groups:",
            statistics[
                "same_tool_group_count"
            ],
        )

        print()

    print(
        "Session-group overlap:",
        0,
    )

    print(
        "Pair overlap:",
        0,
    )

    print()

    print(
        "Assignments:",
        ASSIGNMENTS_PATH,
    )

    print(
        "Report:",
        REPORT_PATH,
    )

    print()

    print(
        "v0.1.5 checkpoint modified: no"
    )


if __name__ == "__main__":
    main()

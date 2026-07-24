from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import re
import statistics
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


V013_EXTENSION_MODULE_PATH = Path(
    "scripts/"
    "extend_agentdojo_approved_labeled_pool_v0_1_3.py"
)

PAIR_PLAN_PATH = Path(
    "data/interim/"
    "agentdojo_contextual_pair_plan_v0.1.4_"
    "p2_travel_repaired.jsonl"
)

SOURCE_SMOKE_POOL_PATH = Path(
    "data/interim/"
    "agentdojo_contextual_action_attempt_smoke_pool_v0.1.1.jsonl"
)

SOURCE_STRUCTURED_POOL_PATH = Path(
    "data/processed/"
    "agentdojo_contextual_action_attempt_labeled_pool_v0.1.3.jsonl"
)

SOURCE_TRAINING_VIEW_PATH = Path(
    "data/processed/"
    "agentdojo_bert_training_view_v0.1.3.jsonl"
)

SOURCE_REVIEW_LEDGER_PATH = Path(
    "data/interim/"
    "agentdojo_action_attempt_human_review_master_v0.1.3.csv"
)

TRAVEL_SECOND_REVIEW_PATH = Path(
    "data/interim/"
    "agentdojo_p2_travel_second_review_queue_v0.1.4.csv"
)

V013_HASH_MANIFEST_PATH = Path(
    "data/processed/"
    "agentdojo_v0.1.3_sha256.txt"
)


OUTPUT_STRUCTURED_POOL_PATH = Path(
    "data/processed/"
    "agentdojo_contextual_action_attempt_labeled_pool_v0.1.4.jsonl"
)

OUTPUT_TRAINING_VIEW_PATH = Path(
    "data/processed/"
    "agentdojo_bert_training_view_v0.1.4.jsonl"
)

OUTPUT_REVIEW_LEDGER_PATH = Path(
    "data/interim/"
    "agentdojo_action_attempt_human_review_master_v0.1.4.csv"
)

REPORT_PATH = Path(
    "data/processed/"
    "agentdojo_contextual_action_attempt_labeled_pool_v0.1.4_report.json"
)


EXPECTED_SOURCE_PAIR_COUNT = 69
EXPECTED_SOURCE_ROW_COUNT = 138

EXPECTED_NEW_PAIR_COUNT = 14
EXPECTED_NEW_ROW_COUNT = 28

EXPECTED_FINAL_PAIR_COUNT = 83
EXPECTED_FINAL_ROW_COUNT = 166

EXPECTED_SAFE_COUNT = 83
EXPECTED_RISKY_COUNT = 83

EXPECTED_PENDING_PAIR_COUNT = 17
EXPECTED_SAME_TOOL_PAIR_COUNT = 17


EXPECTED_TRAVEL_PAIR_IDS = {
    "agentdojo_pair_041",
    "agentdojo_pair_042",
    "agentdojo_pair_043",
    "agentdojo_pair_044",
    "agentdojo_pair_045",
    "agentdojo_pair_048",
    "agentdojo_pair_053",
    "agentdojo_pair_054",
    "agentdojo_pair_055",
    "agentdojo_pair_057",
    "agentdojo_pair_059",
    "agentdojo_pair_061",
    "agentdojo_pair_063",
    "agentdojo_pair_064",
}


def load_module(
    path: Path,
    module_name: str,
) -> Any:

    if not path.exists():
        raise FileNotFoundError(
            f"Missing Python module: {path}"
        )

    specification = (
        importlib.util.spec_from_file_location(
            module_name,
            path,
        )
    )

    if (
        specification is None
        or specification.loader is None
    ):
        raise ImportError(
            f"Could not load module: {path}"
        )

    module = importlib.util.module_from_spec(
        specification
    )

    specification.loader.exec_module(
        module
    )

    return module


def sha256_file(
    path: Path,
) -> str:

    digest = hashlib.sha256()

    with path.open("rb") as file:

        while True:

            chunk = file.read(
                1024 * 1024
            )

            if not chunk:
                break

            digest.update(chunk)

    return digest.hexdigest()


def verify_checkpoint_manifest(
    manifest_path: Path,
) -> int:

    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Missing checkpoint manifest: "
            f"{manifest_path}"
        )

    verified = 0

    for line in manifest_path.read_text(
        encoding="utf-8"
    ).splitlines():

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
                "v0.1.3 checkpoint integrity "
                "validation failed:\n"
                f"Artifact: {artifact_path}\n"
                f"Expected: {expected_hash}\n"
                f"Actual:   {actual_hash}"
            )

        verified += 1

    if verified != 4:
        raise ValueError(
            "Expected four v0.1.3 checkpoint "
            f"hashes, verified {verified}."
        )

    return verified


def canonical_hash(
    value: Any,
) -> str:

    serialized = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()


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


def variant_order(
    variant: str,
) -> int:

    order = {
        "safe": 0,
        "risky": 1,
    }

    if variant not in order:
        raise ValueError(
            f"Unexpected variant: {variant}"
        )

    return order[variant]


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
    fieldnames: list[str],
    rows: list[dict[str, Any]],
) -> None:

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
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(rows)


def main() -> None:

    checkpoint_hashes_verified = (
        verify_checkpoint_manifest(
            V013_HASH_MANIFEST_PATH
        )
    )


    extension_v013 = load_module(
        V013_EXTENSION_MODULE_PATH,
        "agentdojo_extension_v013",
    )

    base = (
        extension_v013.load_base_module()
    )


    candidate_pairs = base.load_jsonl(
        PAIR_PLAN_PATH
    )

    source_smoke_rows = base.load_jsonl(
        SOURCE_SMOKE_POOL_PATH
    )

    source_structured_rows = base.load_jsonl(
        SOURCE_STRUCTURED_POOL_PATH
    )

    source_training_rows = base.load_jsonl(
        SOURCE_TRAINING_VIEW_PATH
    )

    (
        ledger_fieldnames,
        ledger_rows,
    ) = base.load_csv(
        SOURCE_REVIEW_LEDGER_PATH
    )

    (
        _,
        travel_review_rows,
    ) = base.load_csv(
        TRAVEL_SECOND_REVIEW_PATH
    )


    if len(candidate_pairs) != 100:
        raise ValueError(
            "Expected 100 candidate pairs, "
            f"found {len(candidate_pairs)}."
        )


    if (
        len(source_structured_rows)
        !=
        EXPECTED_SOURCE_ROW_COUNT
    ):
        raise ValueError(
            "Expected 138 v0.1.3 structured "
            f"rows, found "
            f"{len(source_structured_rows)}."
        )


    if (
        len(source_training_rows)
        !=
        EXPECTED_SOURCE_ROW_COUNT
    ):
        raise ValueError(
            "Expected 138 v0.1.3 training "
            f"rows, found "
            f"{len(source_training_rows)}."
        )


    source_pair_ids = {
        str(row["pair_id"])
        for row in source_structured_rows
    }


    if (
        len(source_pair_ids)
        !=
        EXPECTED_SOURCE_PAIR_COUNT
    ):
        raise ValueError(
            "Expected 69 v0.1.3 approved "
            f"pairs, found "
            f"{len(source_pair_ids)}."
        )


    travel_review_by_id = {
        str(row["pair_id"]): row
        for row in travel_review_rows
    }


    if (
        set(travel_review_by_id)
        !=
        EXPECTED_TRAVEL_PAIR_IDS
    ):
        raise ValueError(
            "Unexpected travel second-review "
            "inventory.\n"
            f"Expected: "
            f"{sorted(EXPECTED_TRAVEL_PAIR_IDS)}\n"
            f"Found: "
            f"{sorted(travel_review_by_id)}"
        )


    for pair_id, review_row in (
        travel_review_by_id.items()
    ):

        if (
            review_row.get(
                "second_review_decision"
            )
            !=
            "approve_pair"
        ):
            raise ValueError(
                "Travel pair has not been "
                f"approved: {pair_id}"
            )


        if (
            review_row.get(
                "label_eligible_after_second_review"
            ).lower()
            !=
            "true"
        ):
            raise ValueError(
                "Travel pair is not marked "
                f"label-eligible: {pair_id}"
            )


    overlap = (
        source_pair_ids
        &
        EXPECTED_TRAVEL_PAIR_IDS
    )

    if overlap:
        raise ValueError(
            "New travel pair already exists in "
            "the v0.1.3 labeled pool:\n"
            f"{sorted(overlap)}"
        )


    pair_by_id = {
        str(pair["pair_id"]): pair
        for pair in candidate_pairs
    }


    missing_pairs = (
        EXPECTED_TRAVEL_PAIR_IDS
        -
        set(pair_by_id)
    )

    if missing_pairs:
        raise ValueError(
            "Travel pairs missing from candidate "
            f"plan: {sorted(missing_pairs)}"
        )


    suite_template_by_name: dict[
        str,
        dict[str, Any],
    ] = {}


    for row in source_smoke_rows:

        suite = str(
            row["suite"]
        )

        suite_template_by_name.setdefault(
            suite,
            row,
        )


    if "travel" not in suite_template_by_name:
        raise ValueError(
            "Travel suite template was not found "
            "in the source smoke pool."
        )


    new_structured_rows: list[
        dict[str, Any]
    ] = []

    new_training_rows: list[
        dict[str, Any]
    ] = []


    for pair_id in sorted(
        EXPECTED_TRAVEL_PAIR_IDS,
        key=pair_number,
    ):

        pair = pair_by_id[
            pair_id
        ]

        review_row = travel_review_by_id[
            pair_id
        ]


        (
            structured_rows,
            training_rows,
        ) = extension_v013.materialize_new_pair(
            base=base,
            pair=pair,
            suite_template=(
                suite_template_by_name[
                    "travel"
                ]
            ),
            review_row=review_row,
        )


        for structured_row in (
            structured_rows
        ):

            structured_row[
                "review"
            ][
                "label_source"
            ] = (
                "human_review_p2_"
                "travel_second_round"
            )


            provenance = structured_row[
                "provenance"
            ]

            provenance[
                "active_pair_plan_artifact"
            ] = (
                "agentdojo_contextual_pair_plan_"
                "v0.1.4_p2_travel_repaired"
            )

            provenance[
                "human_review_round"
            ] = (
                "human_review_p2_"
                "travel_second_round"
            )

            provenance[
                "p2_deterministic_repaired_pair"
            ] = False

            provenance[
                "p2_travel_repaired_pair"
            ] = True

            provenance[
                "repair_metadata"
            ] = pair.get(
                "repair_metadata"
            )


            structured_row[
                "important_note"
            ] = (
                "This is a human-approved contextual "
                "action.attempt row added during the "
                "v0.1.4 travel extension. Final labels "
                "and review metadata remain excluded "
                "from model_input.text."
            )


        for training_row in (
            training_rows
        ):

            training_row[
                "label_source"
            ] = (
                "human_review_p2_"
                "travel_second_round"
            )


        new_structured_rows.extend(
            structured_rows
        )

        new_training_rows.extend(
            training_rows
        )


    if (
        len(new_structured_rows)
        !=
        EXPECTED_NEW_ROW_COUNT
    ):
        raise ValueError(
            "Expected 28 new structured rows, "
            f"found {len(new_structured_rows)}."
        )


    if (
        len(new_training_rows)
        !=
        EXPECTED_NEW_ROW_COUNT
    ):
        raise ValueError(
            "Expected 28 new training rows, "
            f"found {len(new_training_rows)}."
        )


    combined_structured_rows = [
        deepcopy(row)
        for row in source_structured_rows
    ] + new_structured_rows


    combined_training_rows = [
        deepcopy(row)
        for row in source_training_rows
    ] + new_training_rows


    combined_structured_rows.sort(
        key=lambda row: (
            pair_number(
                str(row["pair_id"])
            ),
            variant_order(
                str(
                    row[
                        "variant"
                    ][
                        "name"
                    ]
                )
            ),
        )
    )


    combined_training_rows.sort(
        key=lambda row: (
            pair_number(
                str(row["pair_id"])
            ),
            variant_order(
                str(row["variant"])
            ),
        )
    )


    # --------------------------------------------------------
    # Preserve every v0.1.3 row without modification
    # --------------------------------------------------------

    combined_structured_by_id = {
        str(row["row_id"]): row
        for row in combined_structured_rows
    }

    combined_training_by_id = {
        str(row["row_id"]): row
        for row in combined_training_rows
    }


    preserved_structured_count = 0
    preserved_training_count = 0


    for source_row in source_structured_rows:

        row_id = str(
            source_row["row_id"]
        )

        output_row = (
            combined_structured_by_id.get(
                row_id
            )
        )

        if output_row is None:
            raise ValueError(
                "Existing v0.1.3 structured "
                f"row disappeared: {row_id}"
            )

        if (
            canonical_hash(source_row)
            !=
            canonical_hash(output_row)
        ):
            raise ValueError(
                "Existing v0.1.3 structured "
                f"row changed: {row_id}"
            )

        preserved_structured_count += 1


    for source_row in source_training_rows:

        row_id = str(
            source_row["row_id"]
        )

        output_row = (
            combined_training_by_id.get(
                row_id
            )
        )

        if output_row is None:
            raise ValueError(
                "Existing v0.1.3 training "
                f"row disappeared: {row_id}"
            )

        if (
            canonical_hash(source_row)
            !=
            canonical_hash(output_row)
        ):
            raise ValueError(
                "Existing v0.1.3 training "
                f"row changed: {row_id}"
            )

        preserved_training_count += 1


    # --------------------------------------------------------
    # Final pool validations
    # --------------------------------------------------------

    if (
        len(combined_structured_rows)
        !=
        EXPECTED_FINAL_ROW_COUNT
    ):
        raise ValueError(
            "Expected 166 final structured rows, "
            f"found {len(combined_structured_rows)}."
        )


    if (
        len(combined_training_rows)
        !=
        EXPECTED_FINAL_ROW_COUNT
    ):
        raise ValueError(
            "Expected 166 final training rows, "
            f"found {len(combined_training_rows)}."
        )


    final_pair_ids = {
        str(row["pair_id"])
        for row in combined_structured_rows
    }


    if (
        len(final_pair_ids)
        !=
        EXPECTED_FINAL_PAIR_COUNT
    ):
        raise ValueError(
            "Expected 83 approved pairs, "
            f"found {len(final_pair_ids)}."
        )


    structured_row_ids = [
        str(row["row_id"])
        for row in combined_structured_rows
    ]

    training_row_ids = [
        str(row["row_id"])
        for row in combined_training_rows
    ]


    if (
        len(structured_row_ids)
        !=
        len(set(structured_row_ids))
    ):
        raise ValueError(
            "Duplicate structured row IDs "
            "detected."
        )


    if (
        len(training_row_ids)
        !=
        len(set(training_row_ids))
    ):
        raise ValueError(
            "Duplicate training row IDs "
            "detected."
        )


    if set(structured_row_ids) != set(
        training_row_ids
    ):
        raise ValueError(
            "Structured and training row IDs "
            "do not match."
        )


    rows_by_pair: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)


    for row in combined_structured_rows:

        rows_by_pair[
            str(row["pair_id"])
        ].append(row)


    final_label_counts: Counter[int] = (
        Counter()
    )

    variant_counts: Counter[str] = (
        Counter()
    )

    shared_context_passed = 0
    distinct_action_passed = 0
    session_group_passed = 0
    label_pair_passed = 0


    for pair_id, pair_rows in (
        rows_by_pair.items()
    ):

        if len(pair_rows) != 2:
            raise ValueError(
                f"{pair_id} has "
                f"{len(pair_rows)} rows."
            )


        shared_context_fingerprints = {
            str(
                row[
                    "model_input"
                ][
                    "shared_context_fingerprint"
                ]
            )
            for row in pair_rows
        }

        if (
            len(
                shared_context_fingerprints
            )
            !=
            1
        ):
            raise ValueError(
                "Shared context differs for "
                f"{pair_id}."
            )

        shared_context_passed += 1


        action_fingerprints = {
            str(
                row[
                    "model_input"
                ][
                    "attempted_action_fingerprint"
                ]
            )
            for row in pair_rows
        }

        if len(action_fingerprints) != 2:
            raise ValueError(
                "Attempted actions are identical "
                f"for {pair_id}."
            )

        distinct_action_passed += 1


        session_group_ids = {
            str(
                row[
                    "session_group_id"
                ]
            )
            for row in pair_rows
        }

        if len(session_group_ids) != 1:
            raise ValueError(
                "Session group differs for "
                f"{pair_id}."
            )

        session_group_passed += 1


        pair_labels = {
            int(
                row[
                    "review"
                ][
                    "final_binary_label"
                ]
            )
            for row in pair_rows
        }

        if pair_labels != {0, 1}:
            raise ValueError(
                "Invalid safe/risky label pair "
                f"for {pair_id}: {pair_labels}"
            )

        label_pair_passed += 1


        for row in pair_rows:

            label = int(
                row[
                    "review"
                ][
                    "final_binary_label"
                ]
            )

            variant = str(
                row[
                    "variant"
                ][
                    "name"
                ]
            )

            final_label_counts[
                label
            ] += 1

            variant_counts[
                variant
            ] += 1


    if final_label_counts != {
        0: EXPECTED_SAFE_COUNT,
        1: EXPECTED_RISKY_COUNT,
    }:
        raise ValueError(
            "Unexpected final label counts: "
            f"{dict(final_label_counts)}"
        )


    if variant_counts != {
        "safe": EXPECTED_SAFE_COUNT,
        "risky": EXPECTED_RISKY_COUNT,
    }:
        raise ValueError(
            "Unexpected variant counts: "
            f"{dict(variant_counts)}"
        )


    structured_by_id = {
        str(row["row_id"]): row
        for row in combined_structured_rows
    }


    for training_row in (
        combined_training_rows
    ):

        row_id = str(
            training_row["row_id"]
        )

        structured_row = (
            structured_by_id[row_id]
        )

        if (
            training_row["text"]
            !=
            structured_row[
                "model_input"
            ][
                "text"
            ]
        ):
            raise ValueError(
                "Training text mismatch for "
                f"{row_id}."
            )


        expected_label = int(
            structured_row[
                "review"
            ][
                "final_binary_label"
            ]
        )

        if (
            int(
                training_row[
                    "general_risk_label"
                ]
            )
            !=
            expected_label
        ):
            raise ValueError(
                "Training label mismatch for "
                f"{row_id}."
            )


    model_input_texts = [
        str(
            row[
                "model_input"
            ][
                "text"
            ]
        )
        for row in combined_structured_rows
    ]


    unique_model_input_count = len(
        set(model_input_texts)
    )

    duplicate_model_input_count = (
        len(model_input_texts)
        -
        unique_model_input_count
    )


    if duplicate_model_input_count != 0:
        raise ValueError(
            "Duplicate model inputs detected: "
            f"{duplicate_model_input_count}"
        )


    leakage_violations = []


    for row in combined_structured_rows:

        model_text = str(
            row[
                "model_input"
            ][
                "text"
            ]
        ).lower()


        leaked_markers = sorted(
            marker
            for marker in (
                base.FORBIDDEN_TEXT_MARKERS
            )
            if marker in model_text
        )


        if leaked_markers:

            leakage_violations.append(
                {
                    "row_id": row[
                        "row_id"
                    ],

                    "markers": (
                        leaked_markers
                    ),
                }
            )


    if leakage_violations:
        raise ValueError(
            "Label/review leakage detected:\n"
            f"{leakage_violations}"
        )


    same_tool_pair_count = sum(
        bool(
            pair_rows[0][
                "provenance"
            ][
                "same_tool_minimal_pair"
            ]
        )
        for pair_rows in (
            rows_by_pair.values()
        )
    )


    if (
        same_tool_pair_count
        !=
        EXPECTED_SAME_TOOL_PAIR_COUNT
    ):
        raise ValueError(
            "Expected 17 same-tool approved "
            f"pairs, found "
            f"{same_tool_pair_count}."
        )


    new_travel_same_tool_count = sum(
        bool(
            rows_by_pair[pair_id][0][
                "provenance"
            ][
                "same_tool_minimal_pair"
            ]
        )
        for pair_id in (
            EXPECTED_TRAVEL_PAIR_IDS
        )
    )


    if new_travel_same_tool_count != 0:
        raise ValueError(
            "A newly approved travel pair "
            "unexpectedly became same-tool."
        )


    # --------------------------------------------------------
    # Update cumulative review ledger
    # --------------------------------------------------------

    ledger_by_id = {
        str(row["pair_id"]): dict(row)
        for row in ledger_rows
    }


    ledger_columns_to_set = [
        "cumulative_review_decision",
        "cumulative_human_review_status",
        "cumulative_review_round",
        "cumulative_safe_label_final",
        "cumulative_risky_label_final",
        "label_eligible",
        "cumulative_review_note",
        "cumulative_reviewed_at",
        "active_legitimate_structure_id",
        "active_attacker_structure_id",
        "active_vector_id",
        "active_source_locator",
        "active_binding_type",
        "active_binding_status",
        "active_review_object_category",
        "active_review_object_name",
    ]


    output_ledger_fieldnames = list(
        ledger_fieldnames
    )

    for column in ledger_columns_to_set:

        if column not in (
            output_ledger_fieldnames
        ):
            output_ledger_fieldnames.append(
                column
            )


    for pair_id in (
        EXPECTED_TRAVEL_PAIR_IDS
    ):

        ledger_row = ledger_by_id.get(
            pair_id
        )

        if ledger_row is None:
            raise ValueError(
                f"Missing ledger row: {pair_id}"
            )


        if (
            ledger_row.get(
                "cumulative_review_decision"
            )
            !=
            "needs_revision"
        ):
            raise ValueError(
                f"{pair_id} was not pending "
                "inside the v0.1.3 ledger."
            )


        pair = pair_by_id[
            pair_id
        ]

        review_row = (
            travel_review_by_id[
                pair_id
            ]
        )

        binding = (
            base.resolve_context_binding(
                pair
            )
        )


        ledger_row[
            "cumulative_review_decision"
        ] = "approve_pair"

        ledger_row[
            "cumulative_human_review_status"
        ] = (
            "human_reviewed_approved_after_"
            "p2_travel_repair"
        )

        ledger_row[
            "cumulative_review_round"
        ] = (
            "p2_travel_second_human_review"
        )

        ledger_row[
            "cumulative_safe_label_final"
        ] = "0"

        ledger_row[
            "cumulative_risky_label_final"
        ] = "1"

        ledger_row[
            "label_eligible"
        ] = "true"

        ledger_row[
            "cumulative_review_note"
        ] = review_row.get(
            "second_review_note",
            "",
        )

        ledger_row[
            "cumulative_reviewed_at"
        ] = review_row.get(
            "second_reviewed_at",
            "",
        )

        ledger_row[
            "active_legitimate_structure_id"
        ] = base.structure_id(
            pair[
                "legitimate_context"
            ]
        )

        ledger_row[
            "active_attacker_structure_id"
        ] = base.structure_id(
            pair[
                "attacker_context"
            ]
        )

        ledger_row[
            "active_vector_id"
        ] = pair[
            "injection_surface"
        ][
            "vector_id"
        ]

        ledger_row[
            "active_source_locator"
        ] = (
            binding[
                "retrieved_object_locator"
            ]
            or
            ""
        )

        ledger_row[
            "active_binding_type"
        ] = binding[
            "binding_type"
        ]

        ledger_row[
            "active_binding_status"
        ] = binding[
            "binding_status"
        ]

        ledger_row[
            "active_review_object_category"
        ] = pair.get(
            "context_bindings",
            {},
        ).get(
            "review_object_category",
            "",
        )

        ledger_row[
            "active_review_object_name"
        ] = pair.get(
            "context_bindings",
            {},
        ).get(
            "review_object_name",
            "",
        )


    output_ledger_rows = sorted(
        ledger_by_id.values(),
        key=lambda row: pair_number(
            str(row["pair_id"])
        ),
    )


    ledger_decision_counts = Counter(
        str(
            row[
                "cumulative_review_decision"
            ]
        )
        for row in output_ledger_rows
    )


    if ledger_decision_counts != {
        "approve_pair": (
            EXPECTED_FINAL_PAIR_COUNT
        ),

        "needs_revision": (
            EXPECTED_PENDING_PAIR_COUNT
        ),
    }:
        raise ValueError(
            "Unexpected cumulative ledger "
            f"counts: "
            f"{dict(ledger_decision_counts)}"
        )


    # --------------------------------------------------------
    # Write versioned artifacts
    # --------------------------------------------------------

    write_jsonl(
        OUTPUT_STRUCTURED_POOL_PATH,
        combined_structured_rows,
    )

    write_jsonl(
        OUTPUT_TRAINING_VIEW_PATH,
        combined_training_rows,
    )

    write_csv(
        OUTPUT_REVIEW_LEDGER_PATH,
        output_ledger_fieldnames,
        output_ledger_rows,
    )


    generated_at = datetime.now(
        timezone.utc
    ).isoformat()


    model_input_lengths = [
        len(text)
        for text in model_input_texts
    ]


    report = {
        "dataset": "agentdojo",

        "artifact_version": "0.1.4",

        "generated_at": generated_at,

        "artifact_status": (
            "human_reviewed_approved_subset"
        ),

        "extension_strategy": (
            "preserve_v0.1.3_rows_and_append_"
            "p2_travel_approved_rows"
        ),

        "v0.1.3_checkpoint_hashes_verified": (
            checkpoint_hashes_verified
        ),

        "source_approved_pair_count": (
            EXPECTED_SOURCE_PAIR_COUNT
        ),

        "source_runtime_row_count": (
            EXPECTED_SOURCE_ROW_COUNT
        ),

        "newly_approved_pair_count": (
            EXPECTED_NEW_PAIR_COUNT
        ),

        "newly_materialized_runtime_row_count": (
            EXPECTED_NEW_ROW_COUNT
        ),

        "approved_pair_count": (
            EXPECTED_FINAL_PAIR_COUNT
        ),

        "remaining_needs_revision_pair_count": (
            EXPECTED_PENDING_PAIR_COUNT
        ),

        "runtime_row_count": (
            EXPECTED_FINAL_ROW_COUNT
        ),

        "variant_counts": dict(
            variant_counts
        ),

        "final_general_risk_label_counts": {
            str(label): count
            for label, count in sorted(
                final_label_counts.items()
            )
        },

        "same_tool_approved_pair_count": (
            same_tool_pair_count
        ),

        "new_travel_same_tool_pair_count": (
            new_travel_same_tool_count
        ),

        "unique_model_input_count": (
            unique_model_input_count
        ),

        "duplicate_model_input_count": (
            duplicate_model_input_count
        ),

        "label_or_review_leakage_count": (
            len(leakage_violations)
        ),

        "shared_context_pair_validation": {
            "passed": (
                shared_context_passed
            ),
            "failed": 0,
        },

        "distinct_attempted_action_validation": {
            "passed": (
                distinct_action_passed
            ),
            "failed": 0,
        },

        "session_group_integrity_validation": {
            "passed": (
                session_group_passed
            ),
            "failed": 0,
        },

        "safe_risky_label_pair_validation": {
            "passed": (
                label_pair_passed
            ),
            "failed": 0,
        },

        "preserved_v0.1.3_structured_rows": (
            preserved_structured_count
        ),

        "changed_v0.1.3_structured_rows": 0,

        "preserved_v0.1.3_training_rows": (
            preserved_training_count
        ),

        "changed_v0.1.3_training_rows": 0,

        "new_travel_pair_ids": sorted(
            EXPECTED_TRAVEL_PAIR_IDS,
            key=pair_number,
        ),

        "model_input_character_length": {
            "minimum": min(
                model_input_lengths
            ),

            "median": statistics.median(
                model_input_lengths
            ),

            "maximum": max(
                model_input_lengths
            ),

            "mean": (
                sum(model_input_lengths)
                /
                len(model_input_lengths)
            ),
        },

        "outputs": {
            "structured_labeled_pool": str(
                OUTPUT_STRUCTURED_POOL_PATH
            ),

            "bert_training_view": str(
                OUTPUT_TRAINING_VIEW_PATH
            ),

            "cumulative_review_ledger": str(
                OUTPUT_REVIEW_LEDGER_PATH
            ),
        },

        "important_notes": [
            (
                "All 138 v0.1.3 structured and "
                "training rows were preserved "
                "without modification."
            ),

            (
                "Only the 28 runtime rows belonging "
                "to the 14 newly approved travel "
                "pairs were materialized."
            ),

            (
                "The 17 pairs still awaiting repair "
                "remain excluded from labeled "
                "artifacts."
            ),

            (
                "Final labels and human-review "
                "metadata remain outside "
                "model_input.text."
            ),

            (
                "The v0.1.3 checkpoint artifacts "
                "were verified against their "
                "SHA-256 manifest before extension."
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
        "AGENTDOJO APPROVED LABELED POOL "
        "v0.1.4 EXTENDED"
    )
    print("=" * 80)

    print()

    print(
        "v0.1.3 checkpoint hashes verified:",
        checkpoint_hashes_verified,
    )

    print()

    print(
        "Preserved approved pairs:",
        EXPECTED_SOURCE_PAIR_COUNT,
    )

    print(
        "Newly approved travel pairs:",
        EXPECTED_NEW_PAIR_COUNT,
    )

    print(
        "Total approved pairs:",
        EXPECTED_FINAL_PAIR_COUNT,
    )

    print(
        "Remaining revision pairs:",
        EXPECTED_PENDING_PAIR_COUNT,
    )

    print()

    print(
        "Preserved runtime rows:",
        EXPECTED_SOURCE_ROW_COUNT,
    )

    print(
        "New runtime rows:",
        EXPECTED_NEW_ROW_COUNT,
    )

    print(
        "Total runtime rows:",
        EXPECTED_FINAL_ROW_COUNT,
    )

    print()

    print(
        "Safe / label 0:",
        final_label_counts[0],
    )

    print(
        "Risky / label 1:",
        final_label_counts[1],
    )

    print()

    print(
        "Same-tool approved pairs:",
        same_tool_pair_count,
    )

    print(
        "Same-tool new travel pairs:",
        new_travel_same_tool_count,
    )

    print()

    print(
        "Shared-context validation:",
        f"{shared_context_passed} / "
        f"{EXPECTED_FINAL_PAIR_COUNT} passed",
    )

    print(
        "Distinct-action validation:",
        f"{distinct_action_passed} / "
        f"{EXPECTED_FINAL_PAIR_COUNT} passed",
    )

    print(
        "Session-group validation:",
        f"{session_group_passed} / "
        f"{EXPECTED_FINAL_PAIR_COUNT} passed",
    )

    print(
        "Label-pair validation:",
        f"{label_pair_passed} / "
        f"{EXPECTED_FINAL_PAIR_COUNT} passed",
    )

    print()

    print(
        "Preserved v0.1.3 structured rows:",
        preserved_structured_count,
    )

    print(
        "Preserved v0.1.3 training rows:",
        preserved_training_count,
    )

    print()

    print(
        "Unique model inputs:",
        unique_model_input_count,
    )

    print(
        "Duplicate model inputs:",
        duplicate_model_input_count,
    )

    print(
        "Label/review leakage:",
        len(leakage_violations),
    )

    print()

    print(
        f"Structured labeled pool: "
        f"{OUTPUT_STRUCTURED_POOL_PATH}"
    )

    print(
        f"BERT training view: "
        f"{OUTPUT_TRAINING_VIEW_PATH}"
    )

    print(
        f"Cumulative review ledger: "
        f"{OUTPUT_REVIEW_LEDGER_PATH}"
    )

    print(
        f"Report: {REPORT_PATH}"
    )

    print()

    print(
        "v0.1.3 checkpoint modified: no"
    )

    print(
        "v0.1.4 candidate pair plan modified: no"
    )


if __name__ == "__main__":
    main()

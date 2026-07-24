from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


LEGITIMATE_SOURCE_PATH = Path(
    "data/interim/"
    "agentdojo_user_task_structure_pool_v0.1.jsonl"
)

LEGITIMATE_AUDIT_PATH = Path(
    "data/interim/"
    "agentdojo_legitimate_task_audit_pool_v0.1.csv"
)

INJECTION_CURATED_PATH = Path(
    "data/processed/"
    "agentdojo_curated_injection_structure_pool_v0.1.jsonl"
)

OUTPUT_DIR = Path(
    "data/processed"
)

LEGITIMATE_LEDGER_PATH = (
    OUTPUT_DIR
    / "agentdojo_curated_legitimate_structure_ledger_v0.1.jsonl"
)

LEGITIMATE_POOL_PATH = (
    OUTPUT_DIR
    / "agentdojo_curated_legitimate_structure_pool_v0.1.jsonl"
)

COMBINED_POOL_PATH = (
    OUTPUT_DIR
    / "agentdojo_combined_structure_pool_v0.1.jsonl"
)

LEGITIMATE_REPORT_PATH = (
    OUTPUT_DIR
    / "agentdojo_curated_legitimate_structure_pool_v0.1_report.json"
)

COMBINED_REPORT_PATH = (
    OUTPUT_DIR
    / "agentdojo_combined_structure_pool_v0.1_report.json"
)


ELIGIBLE_LEGITIMATE_DECISIONS = {
    "high_value_legitimate_structure",
    "usable_legitimate_structure",
}

EXPECTED_EXCLUDED_IDS = {
    "agentdojo_banking_user_task_010",
    "agentdojo_slack_user_task_009",
    "agentdojo_slack_user_task_010",
    "agentdojo_travel_user_task_016",
}


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


def task_number(
    record: dict[str, Any],
) -> int:

    task_id = str(
        record.get(
            "task_id",
            "",
        )
    )

    try:
        return int(
            task_id.rsplit(
                "_",
                maxsplit=1,
            )[-1]
        )
    except ValueError:
        return 999999


def combined_sort_key(
    record: dict[str, Any],
) -> tuple[str, str, int]:

    return (
        str(
            record.get(
                "structure_role",
                "",
            )
        ),
        str(
            record.get(
                "suite",
                "",
            )
        ),
        task_number(record),
    )


def main() -> None:

    legitimate_sources = load_jsonl(
        LEGITIMATE_SOURCE_PATH
    )

    injection_records = load_jsonl(
        INJECTION_CURATED_PATH
    )

    audit_df = pd.read_csv(
        LEGITIMATE_AUDIT_PATH,
        dtype="string",
    )

    required_audit_columns = {
        "structure_id",
        "review_decision",
        "scenario_family",
        "action_impact",
        "review_note",
    }

    missing_columns = (
        required_audit_columns
        -
        set(audit_df.columns)
    )

    if missing_columns:
        raise ValueError(
            "Legitimate audit is missing columns: "
            f"{sorted(missing_columns)}"
        )

    for column in required_audit_columns:
        audit_df[column] = (
            audit_df[column]
            .fillna("")
            .astype("string")
        )


    # --------------------------------------------------------
    # Input validation
    # --------------------------------------------------------

    if len(legitimate_sources) != 86:
        raise ValueError(
            "Expected 86 legitimate source structures, "
            f"found {len(legitimate_sources)}."
        )

    if len(audit_df) != 86:
        raise ValueError(
            "Expected 86 legitimate audit rows, "
            f"found {len(audit_df)}."
        )

    if len(injection_records) != 35:
        raise ValueError(
            "Expected 35 curated injection structures, "
            f"found {len(injection_records)}."
        )

    if (
        audit_df["review_decision"]
        ==
        ""
    ).any():
        unreviewed_ids = (
            audit_df.loc[
                audit_df["review_decision"]
                ==
                "",
                "structure_id",
            ]
            .tolist()
        )

        raise ValueError(
            "Legitimate audit is incomplete. "
            f"Unreviewed IDs: {unreviewed_ids}"
        )


    source_ids = [
        str(record["structure_id"])
        for record in legitimate_sources
    ]

    audit_ids = (
        audit_df[
            "structure_id"
        ]
        .astype(str)
        .tolist()
    )

    if len(source_ids) != len(set(source_ids)):
        raise ValueError(
            "Duplicate structure IDs found in "
            "legitimate source pool."
        )

    if len(audit_ids) != len(set(audit_ids)):
        raise ValueError(
            "Duplicate structure IDs found in "
            "legitimate audit pool."
        )

    if set(source_ids) != set(audit_ids):
        missing_from_audit = (
            set(source_ids)
            -
            set(audit_ids)
        )

        missing_from_source = (
            set(audit_ids)
            -
            set(source_ids)
        )

        raise ValueError(
            "Legitimate source/audit ID mismatch.\n"
            f"Missing from audit: "
            f"{sorted(missing_from_audit)}\n"
            f"Missing from source: "
            f"{sorted(missing_from_source)}"
        )


    audit_lookup = {
        str(row["structure_id"]): row
        for _, row in audit_df.iterrows()
    }


    # --------------------------------------------------------
    # Build legitimate ledger
    # --------------------------------------------------------

    legitimate_ledger: list[
        dict[str, Any]
    ] = []

    for source_record in legitimate_sources:

        structure_id = str(
            source_record[
                "structure_id"
            ]
        )

        audit_row = audit_lookup[
            structure_id
        ]

        review_decision = str(
            audit_row[
                "review_decision"
            ]
        )

        include_for_composition = (
            review_decision
            in
            ELIGIBLE_LEGITIMATE_DECISIONS
        )

        reference_sequence = (
            source_record.get(
                "expected_action_sequence",
                [],
            )
        )

        if not reference_sequence:
            raise ValueError(
                "Legitimate structure unexpectedly has "
                "an empty reference action sequence: "
                f"{structure_id}"
            )

        referenced_functions = (
            source_record.get(
                "referenced_function_names",
                [],
            )
        )

        record = dict(
            source_record
        )

        record[
            "execution_semantics"
        ] = {
            "evaluation_mode": (
                "explicit_ground_truth_function_calls"
            ),

            "reference_action_sequence_status": (
                "available"
            ),

            "reference_action_sequence": (
                reference_sequence
            ),

            "operational_effects": [],

            "semantic_action_candidates": (
                referenced_functions
            ),

            "operational_effect_source": None,

            "sequence_note": (
                "AgentDojo provides an explicit upstream "
                "FunctionCall reference sequence for this "
                "legitimate user task."
            ),
        }

        record[
            "curation"
        ] = {
            "status": "human_reviewed",

            "include_for_composition": (
                include_for_composition
            ),

            "review_decision": (
                review_decision
            ),

            "scenario_family": str(
                audit_row[
                    "scenario_family"
                ]
            ),

            "action_impact": str(
                audit_row[
                    "action_impact"
                ]
            ),

            "review_note": str(
                audit_row[
                    "review_note"
                ]
            ),

            "label_source": (
                "human_review"
            ),

            "quality_tier": "A",

            "exclusion_reason": (
                None
                if include_for_composition
                else (
                    "Prompt and reference-action "
                    "semantics require adjudication."
                )
            ),
        }

        record[
            "composition_role"
        ] = (
            "legitimate_context_structure"
        )

        record[
            "important_note"
        ] = (
            "This is a curated legitimate scenario "
            "structure, not a Phase-1 runtime-risk "
            "training row. A high action-impact value "
            "does not imply general_risk_label=1."
        )

        legitimate_ledger.append(
            record
        )


    legitimate_ledger.sort(
        key=combined_sort_key
    )

    legitimate_pool = [
        record
        for record in legitimate_ledger
        if record[
            "curation"
        ][
            "include_for_composition"
        ]
    ]

    excluded_records = [
        record
        for record in legitimate_ledger
        if not record[
            "curation"
        ][
            "include_for_composition"
        ]
    ]

    excluded_ids = {
        record[
            "structure_id"
        ]
        for record in excluded_records
    }


    # --------------------------------------------------------
    # Validate legitimate results
    # --------------------------------------------------------

    legitimate_decision_counts = Counter(
        record[
            "curation"
        ][
            "review_decision"
        ]
        for record
        in legitimate_ledger
    )

    legitimate_impact_counts = Counter(
        record[
            "curation"
        ][
            "action_impact"
        ]
        for record
        in legitimate_ledger
    )

    legitimate_suite_counts = Counter(
        record[
            "suite"
        ]
        for record
        in legitimate_pool
    )

    expected_decisions = {
        "high_value_legitimate_structure": 51,
        "usable_legitimate_structure": 31,
        "ambiguous_structure": 4,
    }

    expected_impacts = {
        "high": 30,
        "medium": 29,
        "low": 27,
    }

    expected_eligible_suite_counts = {
        "banking": 15,
        "slack": 15,
        "travel": 19,
        "workspace": 33,
    }

    if dict(
        legitimate_decision_counts
    ) != expected_decisions:
        raise ValueError(
            "Unexpected legitimate decision counts.\n"
            f"Expected: {expected_decisions}\n"
            f"Found: "
            f"{dict(legitimate_decision_counts)}"
        )

    if dict(
        legitimate_impact_counts
    ) != expected_impacts:
        raise ValueError(
            "Unexpected legitimate impact counts.\n"
            f"Expected: {expected_impacts}\n"
            f"Found: "
            f"{dict(legitimate_impact_counts)}"
        )

    if len(legitimate_pool) != 82:
        raise ValueError(
            "Expected 82 composition-eligible "
            "legitimate structures, "
            f"found {len(legitimate_pool)}."
        )

    if len(excluded_records) != 4:
        raise ValueError(
            "Expected 4 excluded legitimate "
            f"structures, found {len(excluded_records)}."
        )

    if excluded_ids != EXPECTED_EXCLUDED_IDS:
        raise ValueError(
            "Unexpected excluded legitimate IDs.\n"
            f"Expected: "
            f"{sorted(EXPECTED_EXCLUDED_IDS)}\n"
            f"Found: {sorted(excluded_ids)}"
        )

    if dict(
        legitimate_suite_counts
    ) != expected_eligible_suite_counts:
        raise ValueError(
            "Unexpected eligible legitimate "
            "suite counts.\n"
            f"Expected: "
            f"{expected_eligible_suite_counts}\n"
            f"Found: "
            f"{dict(legitimate_suite_counts)}"
        )


    # --------------------------------------------------------
    # Validate injection records
    # --------------------------------------------------------

    for record in injection_records:

        curation = record.get(
            "curation",
            {},
        )

        if not curation.get(
            "include_for_composition",
            False,
        ):
            raise ValueError(
                "Curated injection record is not "
                "composition eligible: "
                f"{record.get('structure_id')}"
            )

        record[
            "composition_role"
        ] = (
            "adversarial_context_structure"
        )


    injection_suite_counts = Counter(
        record[
            "suite"
        ]
        for record
        in injection_records
    )

    expected_injection_suite_counts = {
        "banking": 9,
        "slack": 5,
        "travel": 7,
        "workspace": 14,
    }

    if dict(
        injection_suite_counts
    ) != expected_injection_suite_counts:
        raise ValueError(
            "Unexpected injection suite counts.\n"
            f"Expected: "
            f"{expected_injection_suite_counts}\n"
            f"Found: "
            f"{dict(injection_suite_counts)}"
        )


    # --------------------------------------------------------
    # Build combined composition pool
    # --------------------------------------------------------

    combined_pool = (
        legitimate_pool
        +
        injection_records
    )

    combined_pool.sort(
        key=combined_sort_key
    )


    combined_ids = [
        record[
            "structure_id"
        ]
        for record in combined_pool
    ]

    if len(combined_ids) != len(
        set(combined_ids)
    ):
        raise ValueError(
            "Duplicate structure IDs found in "
            "combined AgentDojo pool."
        )


    role_counts = Counter(
        record[
            "structure_role"
        ]
        for record
        in combined_pool
    )

    composition_role_counts = Counter(
        record[
            "composition_role"
        ]
        for record
        in combined_pool
    )

    combined_suite_counts = Counter(
        record[
            "suite"
        ]
        for record
        in combined_pool
    )

    expected_role_counts = {
        "legitimate_user_goal": 82,
        "attacker_goal": 35,
    }

    expected_composition_roles = {
        "legitimate_context_structure": 82,
        "adversarial_context_structure": 35,
    }

    expected_combined_suite_counts = {
        "banking": 24,
        "slack": 20,
        "travel": 26,
        "workspace": 47,
    }

    if len(combined_pool) != 117:
        raise ValueError(
            "Expected 117 combined structures, "
            f"found {len(combined_pool)}."
        )

    if dict(
        role_counts
    ) != expected_role_counts:
        raise ValueError(
            "Unexpected structure-role counts.\n"
            f"Expected: {expected_role_counts}\n"
            f"Found: {dict(role_counts)}"
        )

    if dict(
        composition_role_counts
    ) != expected_composition_roles:
        raise ValueError(
            "Unexpected composition-role counts.\n"
            f"Expected: {expected_composition_roles}\n"
            f"Found: "
            f"{dict(composition_role_counts)}"
        )

    if dict(
        combined_suite_counts
    ) != expected_combined_suite_counts:
        raise ValueError(
            "Unexpected combined suite counts.\n"
            f"Expected: "
            f"{expected_combined_suite_counts}\n"
            f"Found: "
            f"{dict(combined_suite_counts)}"
        )


    # --------------------------------------------------------
    # Reports
    # --------------------------------------------------------

    legitimate_family_count = len(
        {
            record[
                "curation"
            ][
                "scenario_family"
            ]
            for record
            in legitimate_ledger
        }
    )

    eligible_legitimate_family_count = len(
        {
            record[
                "curation"
            ][
                "scenario_family"
            ]
            for record
            in legitimate_pool
        }
    )

    combined_family_count = len(
        {
            record[
                "curation"
            ][
                "scenario_family"
            ]
            for record
            in combined_pool
        }
    )

    evaluation_mode_counts = Counter(
        record[
            "execution_semantics"
        ][
            "evaluation_mode"
        ]
        for record
        in combined_pool
    )


    generated_at = datetime.now(
        timezone.utc
    ).isoformat()


    legitimate_report = {
        "dataset": "agentdojo",

        "curated_legitimate_structure_version": (
            "0.1"
        ),

        "generated_at": generated_at,

        "benchmark_version": "v1.2.2",

        "ledger_count": 86,

        "composition_eligible_count": 82,

        "excluded_count": 4,

        "review_decision_counts": dict(
            legitimate_decision_counts
        ),

        "action_impact_counts": dict(
            legitimate_impact_counts
        ),

        "eligible_suite_counts": dict(
            legitimate_suite_counts
        ),

        "unique_scenario_family_count": (
            legitimate_family_count
        ),

        "eligible_unique_scenario_family_count": (
            eligible_legitimate_family_count
        ),

        "excluded_structure_ids": sorted(
            excluded_ids
        ),

        "important_note": (
            "All 86 legitimate structures were "
            "human-reviewed. Four prompt/reference-"
            "sequence mismatch structures are retained "
            "in the ledger but excluded from composition."
        ),
    }


    combined_report = {
        "dataset": "agentdojo",

        "combined_structure_pool_version": (
            "0.1"
        ),

        "generated_at": generated_at,

        "benchmark_version": "v1.2.2",

        "source_structure_count": 121,

        "human_reviewed_structure_count": 121,

        "composition_eligible_count": 117,

        "excluded_count": 4,

        "structure_role_counts": dict(
            role_counts
        ),

        "composition_role_counts": dict(
            composition_role_counts
        ),

        "suite_counts": dict(
            combined_suite_counts
        ),

        "evaluation_mode_counts": dict(
            evaluation_mode_counts
        ),

        "legitimate_review_decision_counts": dict(
            legitimate_decision_counts
        ),

        "injection_review_decision_counts": dict(
            Counter(
                record[
                    "curation"
                ][
                    "review_decision"
                ]
                for record
                in injection_records
            )
        ),

        "legitimate_action_impact_counts": dict(
            legitimate_impact_counts
        ),

        "injection_target_action_risk_counts": dict(
            Counter(
                record[
                    "curation"
                ][
                    "target_action_risk"
                ]
                for record
                in injection_records
            )
        ),

        "unique_scenario_family_count": (
            combined_family_count
        ),

        "excluded_structure_ids": sorted(
            excluded_ids
        ),

        "composition_policy": {
            "legitimate_structures": (
                "Used as legitimate contextual goals and "
                "high-impact hard-negative material."
            ),

            "injection_structures": (
                "Used as adversarial scenario structures "
                "for contextual composition."
            ),

            "ambiguous_structures": (
                "Retained in the legitimate ledger but "
                "excluded until prompt/reference-action "
                "mismatches are adjudicated."
            ),
        },

        "important_note": (
            "These 117 records are scenario structures, "
            "not direct BERT training examples. Runtime "
            "general_risk_label values must be assigned "
            "only after contextual composition with source "
            "trust, authorization, policy, agent context, "
            "retrieval context, and attempted action."
        ),
    }


    # --------------------------------------------------------
    # Write files
    # --------------------------------------------------------

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    write_jsonl(
        LEGITIMATE_LEDGER_PATH,
        legitimate_ledger,
    )

    write_jsonl(
        LEGITIMATE_POOL_PATH,
        legitimate_pool,
    )

    write_jsonl(
        COMBINED_POOL_PATH,
        combined_pool,
    )

    LEGITIMATE_REPORT_PATH.write_text(
        json.dumps(
            legitimate_report,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    COMBINED_REPORT_PATH.write_text(
        json.dumps(
            combined_report,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


    # --------------------------------------------------------
    # Console summary
    # --------------------------------------------------------

    print("=" * 80)
    print(
        "AGENTDOJO CURATED LEGITIMATE AND COMBINED POOLS v0.1 FINALIZED"
    )
    print("=" * 80)

    print()
    print(
        "Legitimate ledger:",
        len(legitimate_ledger),
    )

    print(
        "Legitimate composition pool:",
        len(legitimate_pool),
    )

    print(
        "Legitimate excluded:",
        len(excluded_records),
    )

    print()
    print(
        "Legitimate decisions:"
    )

    for decision, count in (
        legitimate_decision_counts.items()
    ):
        print(
            f"  {decision}: {count}"
        )

    print()
    print(
        "Legitimate eligible suites:"
    )

    for suite, count in sorted(
        legitimate_suite_counts.items()
    ):
        print(
            f"  {suite}: {count}"
        )

    print()
    print(
        "Combined composition pool:",
        len(combined_pool),
    )

    print()
    print(
        "Combined roles:"
    )

    for role, count in (
        role_counts.items()
    ):
        print(
            f"  {role}: {count}"
        )

    print()
    print(
        "Combined suites:"
    )

    for suite, count in sorted(
        combined_suite_counts.items()
    ):
        print(
            f"  {suite}: {count}"
        )

    print()
    print(
        "Combined evaluation modes:"
    )

    for mode, count in (
        evaluation_mode_counts.items()
    ):
        print(
            f"  {mode}: {count}"
        )

    print()
    print(
        "Combined unique scenario families:",
        combined_family_count,
    )

    print()
    print(
        f"Legitimate ledger: "
        f"{LEGITIMATE_LEDGER_PATH}"
    )

    print(
        f"Legitimate pool: "
        f"{LEGITIMATE_POOL_PATH}"
    )

    print(
        f"Combined pool: "
        f"{COMBINED_POOL_PATH}"
    )

    print(
        f"Combined report: "
        f"{COMBINED_REPORT_PATH}"
    )


if __name__ == "__main__":
    main()

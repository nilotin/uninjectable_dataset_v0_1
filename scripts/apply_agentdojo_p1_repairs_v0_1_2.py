from __future__ import annotations

import copy
import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


INPUT_PAIR_PLAN = Path(
    "data/interim/"
    "agentdojo_contextual_pair_plan_v0.1.jsonl"
)

OUTPUT_PAIR_PLAN = Path(
    "data/interim/"
    "agentdojo_contextual_pair_plan_v0.1.2_p1_repaired.jsonl"
)

SECOND_REVIEW_QUEUE = Path(
    "data/interim/"
    "agentdojo_p1_second_review_queue_v0.1.2.csv"
)

MANIFEST_PATH = Path(
    "data/interim/"
    "agentdojo_p1_repair_manifest_v0.1.2.json"
)


TARGET_PAIR_IDS = {
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
            f"Missing pair plan: {path}"
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
            "Second-review queue is empty."
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


def canonical_json(
    value: Any,
) -> str:

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


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


def action_name(
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


def structure_id(
    context: dict[str, Any],
) -> str:

    return str(
        context.get(
            "structure_id"
        )
        or
        context.get(
            "blueprint_id"
        )
        or
        ""
    )


def blueprint_identity(
    context: dict[str, Any],
) -> str:

    return str(
        context.get(
            "blueprint_id"
        )
        or
        context.get(
            "structure_id"
        )
        or
        ""
    )


def pair_triple(
    pair: dict[str, Any],
) -> tuple[str, str, str]:

    return (
        blueprint_identity(
            pair[
                "legitimate_context"
            ]
        ),

        blueprint_identity(
            pair[
                "attacker_context"
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


def is_same_tool(
    pair: dict[str, Any],
) -> bool:

    selected = pair[
        "selected_actions"
    ]

    return (
        action_name(
            selected[
                "authorized_user_action"
            ]
        )
        ==
        action_name(
            selected[
                "attacker_target_action"
            ]
        )
    )


def args_are_distinct(
    pair: dict[str, Any],
) -> bool:

    selected = pair[
        "selected_actions"
    ]

    return (
        canonical_json(
            action_args(
                selected[
                    "authorized_user_action"
                ]
            )
        )
        !=
        canonical_json(
            action_args(
                selected[
                    "attacker_target_action"
                ]
            )
        )
    )


def find_pair(
    pairs: list[dict[str, Any]],
    *,
    suite: str,
    legitimate_structure_id: str | None = None,
    attacker_structure_id: str | None = None,
    vector_id: str | None = None,
    exclude_pair_id: str | None = None,
) -> dict[str, Any]:

    matches = []

    for pair in pairs:

        if str(
            pair.get(
                "suite"
            )
        ) != suite:
            continue

        if (
            exclude_pair_id is not None
            and
            pair[
                "pair_id"
            ] == exclude_pair_id
        ):
            continue

        if (
            legitimate_structure_id is not None
            and
            structure_id(
                pair[
                    "legitimate_context"
                ]
            )
            != legitimate_structure_id
        ):
            continue

        if (
            attacker_structure_id is not None
            and
            structure_id(
                pair[
                    "attacker_context"
                ]
            )
            != attacker_structure_id
        ):
            continue

        if (
            vector_id is not None
            and
            str(
                pair[
                    "injection_surface"
                ][
                    "vector_id"
                ]
            )
            != vector_id
        ):
            continue

        matches.append(
            pair
        )

    if not matches:
        raise ValueError(
            "No donor pair found for "
            f"suite={suite}, "
            f"legitimate={legitimate_structure_id}, "
            f"attacker={attacker_structure_id}, "
            f"vector={vector_id}."
        )

    matches.sort(
        key=lambda pair: pair_number(
            pair[
                "pair_id"
            ]
        )
    )

    return matches[0]


def set_binding(
    pair: dict[str, Any],
    *,
    binding_type: str,
    binding_status: str,
    source_locator: str | None,
    parameter_bindings: dict[str, Any],
    evidence: str,
) -> None:

    surface = pair[
        "injection_surface"
    ]

    surface[
        "source_locator"
    ] = source_locator

    surface[
        "binding_type"
    ] = binding_type

    surface[
        "binding_status"
    ] = binding_status


    bindings = copy.deepcopy(
        pair.get(
            "context_bindings",
            {}
        )
    )

    bindings.update(
        {
            "binding_type": binding_type,

            "binding_status": binding_status,

            "retrieved_object_locator": (
                source_locator
            ),

            "parameter_bindings": (
                parameter_bindings
            ),

            "binding_evidence": evidence,
        }
    )

    pair[
        "context_bindings"
    ] = bindings


def update_pair_diagnostics(
    pair: dict[str, Any],
) -> None:

    same_tool = is_same_tool(
        pair
    )

    distinct_args = args_are_distinct(
        pair
    )

    pair[
        "same_tool_minimal_pair"
    ] = same_tool


    diagnostics = copy.deepcopy(
        pair.get(
            "pairing_diagnostics",
            {}
        )
    )

    diagnostics[
        "same_tool_minimal_pair"
    ] = same_tool

    diagnostics[
        "action_args_distinct"
    ] = distinct_args

    diagnostics[
        "p1_repair_validation"
    ] = "passed"

    pair[
        "pairing_diagnostics"
    ] = diagnostics


def add_repair_metadata(
    pair: dict[str, Any],
    *,
    repair_type: str,
    repair_summary: str,
    donor_pair_ids: list[str],
    repaired_at: str,
) -> None:

    pair[
        "repair_metadata"
    ] = {
        "repair_round": (
            "p1_same_tool_repair_v0.1.2"
        ),

        "repair_type": repair_type,

        "repair_summary": repair_summary,

        "donor_pair_ids": donor_pair_ids,

        "repaired_at": repaired_at,

        "second_review_required": True,

        "final_labels_assigned": False,
    }


def compact_action(
    action: dict[str, Any],
) -> dict[str, Any]:

    return {
        "tool": action_name(
            action
        ),

        "args": action_args(
            action
        ),
    }


def main() -> None:

    original_pairs = load_jsonl(
        INPUT_PAIR_PLAN
    )

    if len(original_pairs) != 100:
        raise ValueError(
            f"Expected 100 pairs, found "
            f"{len(original_pairs)}."
        )


    pair_ids = {
        str(
            pair[
                "pair_id"
            ]
        )
        for pair in original_pairs
    }

    if not TARGET_PAIR_IDS.issubset(
        pair_ids
    ):
        raise ValueError(
            "Some P1 target pairs are missing: "
            f"{sorted(TARGET_PAIR_IDS - pair_ids)}"
        )


    candidate_pairs = copy.deepcopy(
        original_pairs
    )

    candidate_by_id = {
        str(
            pair[
                "pair_id"
            ]
        ): pair
        for pair in candidate_pairs
    }


    repaired_at = datetime.now(
        timezone.utc
    ).isoformat()

    change_records = []


    # ========================================================
    # PAIR 016
    # Bill task must use the bill-text injection object.
    # Change attacker task as well to avoid duplicate triple.
    # ========================================================

    pair_016 = candidate_by_id[
        "agentdojo_pair_016"
    ]

    old_016 = copy.deepcopy(
        pair_016
    )

    attacker_003_donor = find_pair(
        original_pairs,
        suite="banking",
        attacker_structure_id=(
            "agentdojo_banking_injection_task_003"
        ),
        exclude_pair_id="agentdojo_pair_016",
    )

    bill_vector_donor = find_pair(
        original_pairs,
        suite="banking",
        vector_id="injection_bill_text",
        exclude_pair_id="agentdojo_pair_016",
    )


    pair_016[
        "attacker_context"
    ] = copy.deepcopy(
        attacker_003_donor[
            "attacker_context"
        ]
    )

    pair_016[
        "selected_actions"
    ][
        "attacker_target_action"
    ] = copy.deepcopy(
        attacker_003_donor[
            "selected_actions"
        ][
            "attacker_target_action"
        ]
    )

    pair_016[
        "injection_surface"
    ] = copy.deepcopy(
        bill_vector_donor[
            "injection_surface"
        ]
    )

    set_binding(
        pair_016,
        binding_type=(
            "exact_cloud_document_filename_binding"
        ),
        binding_status="confirmed",
        source_locator="bill-december-2023.txt",
        parameter_bindings={
            "filename": "bill-december-2023.txt",
        },
        evidence=(
            "The legitimate task explicitly requests "
            "bill-december-2023.txt, and injection_bill_text "
            "is located in that document."
        ),
    )

    add_repair_metadata(
        pair_016,
        repair_type=(
            "replace_vector_and_attacker_structure"
        ),
        repair_summary=(
            "Replaced landlord-notice vector with bill-text "
            "vector and replaced attacker task 000 with "
            "attacker task 003 to preserve triple uniqueness."
        ),
        donor_pair_ids=[
            attacker_003_donor[
                "pair_id"
            ],
            bill_vector_donor[
                "pair_id"
            ],
        ],
        repaired_at=repaired_at,
    )

    update_pair_diagnostics(
        pair_016
    )


    # ========================================================
    # PAIR 031
    # Generic URL is concretely bound to Eve's blog.
    # ========================================================

    pair_031 = candidate_by_id[
        "agentdojo_pair_031"
    ]

    old_031 = copy.deepcopy(
        pair_031
    )

    set_binding(
        pair_031,
        binding_type=(
            "parameterized_web_url_binding"
        ),
        binding_status="confirmed",
        source_locator="www.eve-blog.com",
        parameter_bindings={
            "URL": "www.eve-blog.com",
        },
        evidence=(
            "The legitimate URL parameter is concretely set "
            "to the webpage containing "
            "prompt_injection_eve_blog."
        ),
    )

    add_repair_metadata(
        pair_031,
        repair_type="binding_only",
        repair_summary=(
            "Bound the legitimate URL parameter to "
            "www.eve-blog.com."
        ),
        donor_pair_ids=[],
        repaired_at=repaired_at,
    )

    update_pair_diagnostics(
        pair_031
    )


    # ========================================================
    # PAIR 040
    # Slack article URL is concretely bound to phishing page.
    # ========================================================

    pair_040 = candidate_by_id[
        "agentdojo_pair_040"
    ]

    old_040 = copy.deepcopy(
        pair_040
    )

    set_binding(
        pair_040,
        binding_type=(
            "slack_message_article_url_binding"
        ),
        binding_status="confirmed",
        source_locator="www.true-informations.com",
        parameter_bindings={
            "retrieved_article_url": (
                "www.true-informations.com"
            ),
        },
        evidence=(
            "The article URL retrieved from the Slack message "
            "is concretely bound to the webpage containing "
            "injection_phishing_1."
        ),
    )

    add_repair_metadata(
        pair_040,
        repair_type="binding_only",
        repair_summary=(
            "Bound the Slack article URL to "
            "www.true-informations.com."
        ),
        donor_pair_ids=[],
        repaired_at=repaired_at,
    )

    update_pair_diagnostics(
        pair_040
    )


    # ========================================================
    # PAIR 091
    # Recipe vector cannot bind to client-meeting-minutes.
    # Reuse approved keyword-search context from pair 090,
    # but retain attacker task 004 for a unique same-tool pair.
    # ========================================================

    pair_091 = candidate_by_id[
        "agentdojo_pair_091"
    ]

    old_091 = copy.deepcopy(
        pair_091
    )

    keyword_donor = find_pair(
        original_pairs,
        suite="workspace",
        legitimate_structure_id=(
            "agentdojo_workspace_user_task_025"
        ),
        vector_id=(
            "drive_keywords_stuffing_injection"
        ),
        exclude_pair_id="agentdojo_pair_091",
    )


    pair_091[
        "legitimate_context"
    ] = copy.deepcopy(
        keyword_donor[
            "legitimate_context"
        ]
    )

    pair_091[
        "selected_actions"
    ][
        "authorized_user_action"
    ] = copy.deepcopy(
        keyword_donor[
            "selected_actions"
        ][
            "authorized_user_action"
        ]
    )

    pair_091[
        "injection_surface"
    ] = copy.deepcopy(
        keyword_donor[
            "injection_surface"
        ]
    )

    pair_091[
        "context_bindings"
    ] = copy.deepcopy(
        keyword_donor.get(
            "context_bindings",
            {}
        )
    )

    set_binding(
        pair_091,
        binding_type=(
            "adversarial_keyword_search_binding"
        ),
        binding_status=(
            "confirmed_by_vector_semantics"
        ),
        source_locator=(
            pair_091[
                "injection_surface"
            ].get(
                "source_locator"
            )
        ),
        parameter_bindings={
            "search_topic": "team meeting minutes",
            "retrieval_mechanism": (
                "keyword-stuffed cloud document"
            ),
        },
        evidence=(
            "The legitimate task performs topic-based cloud "
            "search, and the replacement vector is explicitly "
            "designed to enter those search results through "
            "keyword stuffing."
        ),
    )

    add_repair_metadata(
        pair_091,
        repair_type=(
            "replace_legitimate_structure_and_vector"
        ),
        repair_summary=(
            "Replaced client-meeting-minutes task and recipe "
            "vector with user task 025 and the approved "
            "keyword-stuffing retrieval vector. Attacker task "
            "004 remains unchanged."
        ),
        donor_pair_ids=[
            keyword_donor[
                "pair_id"
            ],
        ],
        repaired_at=repaired_at,
    )

    update_pair_diagnostics(
        pair_091
    )


    # ========================================================
    # PAIR 095
    # UserTask13 explicitly reads feedback.xlsx.
    # Replace unrelated Facebook-email vector with the exact
    # feedback document vector. Keep both structures.
    # ========================================================

    pair_095 = candidate_by_id[
        "agentdojo_pair_095"
    ]

    old_095 = copy.deepcopy(
        pair_095
    )

    feedback_vector_donor = find_pair(
        original_pairs,
        suite="workspace",
        vector_id="drive_feedback_injection",
        exclude_pair_id="agentdojo_pair_095",
    )


    pair_095[
        "injection_surface"
    ] = copy.deepcopy(
        feedback_vector_donor[
            "injection_surface"
        ]
    )

    set_binding(
        pair_095,
        binding_type=(
            "exact_cloud_document_filename_binding"
        ),
        binding_status="confirmed",
        source_locator="feedback.xlsx",
        parameter_bindings={
            "filename": "feedback.xlsx",
            "task_parameter": "_FILENAME_2",
        },
        evidence=(
            "Workspace UserTask13 explicitly searches "
            "feedback.xlsx, and drive_feedback_injection is "
            "located in that document."
        ),
    )

    add_repair_metadata(
        pair_095,
        repair_type="replace_vector_only",
        repair_summary=(
            "Replaced the unrelated Facebook-email vector "
            "with drive_feedback_injection in feedback.xlsx. "
            "The legitimate and attacker structures remain "
            "unchanged."
        ),
        donor_pair_ids=[
            feedback_vector_donor[
                "pair_id"
            ],
        ],
        repaired_at=repaired_at,
    )

    update_pair_diagnostics(
        pair_095
    )


    old_by_id = {
        "agentdojo_pair_016": old_016,
        "agentdojo_pair_031": old_031,
        "agentdojo_pair_040": old_040,
        "agentdojo_pair_091": old_091,
        "agentdojo_pair_095": old_095,
    }


    # ========================================================
    # Global validation
    # ========================================================

    candidate_pairs.sort(
        key=lambda pair: pair_number(
            pair[
                "pair_id"
            ]
        )
    )


    candidate_ids = [
        pair[
            "pair_id"
        ]
        for pair in candidate_pairs
    ]

    if len(candidate_ids) != 100:
        raise ValueError(
            "Candidate pair plan does not contain 100 pairs."
        )

    if len(
        set(candidate_ids)
    ) != 100:
        raise ValueError(
            "Duplicate pair IDs detected."
        )


    triples = [
        pair_triple(
            pair
        )
        for pair in candidate_pairs
    ]

    duplicate_triples = {
        triple: count
        for triple, count in Counter(
            triples
        ).items()
        if count > 1
    }

    if duplicate_triples:
        raise ValueError(
            "Duplicate composition triples detected:\n"
            f"{duplicate_triples}"
        )


    for pair_id in sorted(
        TARGET_PAIR_IDS,
        key=pair_number,
    ):

        pair = candidate_by_id[
            pair_id
        ]

        if not is_same_tool(
            pair
        ):
            raise ValueError(
                f"P1 repair lost same-tool property: "
                f"{pair_id}"
            )

        if not args_are_distinct(
            pair
        ):
            raise ValueError(
                f"Safe and risky args are identical: "
                f"{pair_id}"
            )


    original_same_tool_count = sum(
        is_same_tool(
            pair
        )
        for pair in original_pairs
    )

    repaired_same_tool_count = sum(
        is_same_tool(
            pair
        )
        for pair in candidate_pairs
    )

    if (
        repaired_same_tool_count
        !=
        original_same_tool_count
    ):
        raise ValueError(
            "Same-tool pair count changed unexpectedly: "
            f"{original_same_tool_count} -> "
            f"{repaired_same_tool_count}"
        )


    # ========================================================
    # Build manifest and second-review queue
    # ========================================================

    second_review_rows = []


    for pair_id in sorted(
        TARGET_PAIR_IDS,
        key=pair_number,
    ):

        old_pair = old_by_id[
            pair_id
        ]

        new_pair = candidate_by_id[
            pair_id
        ]

        selected = new_pair[
            "selected_actions"
        ]

        surface = new_pair[
            "injection_surface"
        ]

        bindings = new_pair.get(
            "context_bindings",
            {}
        )

        repair = new_pair[
            "repair_metadata"
        ]


        change_records.append(
            {
                "pair_id": pair_id,

                "repair_type": repair[
                    "repair_type"
                ],

                "old_legitimate_structure_id": structure_id(
                    old_pair[
                        "legitimate_context"
                    ]
                ),

                "new_legitimate_structure_id": structure_id(
                    new_pair[
                        "legitimate_context"
                    ]
                ),

                "old_attacker_structure_id": structure_id(
                    old_pair[
                        "attacker_context"
                    ]
                ),

                "new_attacker_structure_id": structure_id(
                    new_pair[
                        "attacker_context"
                    ]
                ),

                "old_vector_id": (
                    old_pair[
                        "injection_surface"
                    ][
                        "vector_id"
                    ]
                ),

                "new_vector_id": (
                    surface[
                        "vector_id"
                    ]
                ),

                "source_locator": surface.get(
                    "source_locator"
                ),

                "binding_type": bindings.get(
                    "binding_type"
                ),

                "binding_status": bindings.get(
                    "binding_status"
                ),

                "same_tool_minimal_pair": (
                    is_same_tool(
                        new_pair
                    )
                ),

                "action_args_distinct": (
                    args_are_distinct(
                        new_pair
                    )
                ),
            }
        )


        second_review_rows.append(
            {
                "pair_id": pair_id,

                "suite": new_pair[
                    "suite"
                ],

                "repair_type": repair[
                    "repair_type"
                ],

                "repair_summary": repair[
                    "repair_summary"
                ],

                "legitimate_structure_id": structure_id(
                    new_pair[
                        "legitimate_context"
                    ]
                ),

                "attacker_structure_id": structure_id(
                    new_pair[
                        "attacker_context"
                    ]
                ),

                "vector_id": surface[
                    "vector_id"
                ],

                "source_locator": (
                    surface.get(
                        "source_locator"
                    )
                    or
                    ""
                ),

                "binding_type": (
                    bindings.get(
                        "binding_type"
                    )
                    or
                    ""
                ),

                "binding_status": (
                    bindings.get(
                        "binding_status"
                    )
                    or
                    ""
                ),

                "binding_evidence": (
                    bindings.get(
                        "binding_evidence"
                    )
                    or
                    ""
                ),

                "user_goal": new_pair[
                    "legitimate_context"
                ].get(
                    "prompt_or_goal",
                    ""
                ),

                "attacker_goal": new_pair[
                    "attacker_context"
                ].get(
                    "prompt_or_goal",
                    ""
                ),

                "safe_tool": action_name(
                    selected[
                        "authorized_user_action"
                    ]
                ),

                "safe_args": canonical_json(
                    action_args(
                        selected[
                            "authorized_user_action"
                        ]
                    )
                ),

                "risky_tool": action_name(
                    selected[
                        "attacker_target_action"
                    ]
                ),

                "risky_args": canonical_json(
                    action_args(
                        selected[
                            "attacker_target_action"
                        ]
                    )
                ),

                "same_tool_minimal_pair": (
                    str(
                        is_same_tool(
                            new_pair
                        )
                    )
                ),

                "action_args_distinct": (
                    str(
                        args_are_distinct(
                            new_pair
                        )
                    )
                ),

                "second_review_decision": "",

                "second_review_note": "",
            }
        )


    write_jsonl(
        OUTPUT_PAIR_PLAN,
        candidate_pairs,
    )

    write_csv(
        SECOND_REVIEW_QUEUE,
        second_review_rows,
    )


    manifest = {
        "artifact_version": "0.1.2",

        "generated_at": repaired_at,

        "source_pair_plan": str(
            INPUT_PAIR_PLAN
        ),

        "candidate_pair_plan": str(
            OUTPUT_PAIR_PLAN
        ),

        "second_review_queue": str(
            SECOND_REVIEW_QUEUE
        ),

        "target_pair_count": len(
            TARGET_PAIR_IDS
        ),

        "target_pair_ids": sorted(
            TARGET_PAIR_IDS,
            key=pair_number,
        ),

        "change_records": change_records,

        "validation": {
            "pair_count": len(
                candidate_pairs
            ),

            "duplicate_pair_ids": 0,

            "duplicate_composition_triples": 0,

            "original_same_tool_pair_count": (
                original_same_tool_count
            ),

            "repaired_same_tool_pair_count": (
                repaired_same_tool_count
            ),

            "p1_same_tool_repairs_preserved": True,

            "p1_distinct_action_args": True,
        },

        "important_notes": [
            (
                "The original v0.1 pair plan was not modified."
            ),
            (
                "No smoke-pool rows were modified."
            ),
            (
                "No human-review decisions or final labels "
                "were modified."
            ),
            (
                "All five repaired pairs require a second "
                "human-review decision before final labeling."
            ),
        ],
    }


    MANIFEST_PATH.write_text(
        json.dumps(
            manifest,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


    print("=" * 80)
    print(
        "AGENTDOJO P1 REPAIRS v0.1.2 "
        "APPLIED TO CANDIDATE PLAN"
    )
    print("=" * 80)

    print()
    print(
        "Repaired pairs:",
        len(
            TARGET_PAIR_IDS
        ),
    )

    print(
        "Pair count:",
        len(
            candidate_pairs
        ),
    )

    print(
        "Duplicate composition triples:",
        0,
    )

    print(
        "Same-tool count:",
        repaired_same_tool_count,
    )

    print(
        "Final labels modified:",
        "no",
    )

    print(
        "Smoke pool modified:",
        "no",
    )


    for row in second_review_rows:

        print()
        print("=" * 110)

        print(
            "PAIR:",
            row[
                "pair_id"
            ],
        )

        print(
            "REPAIR:",
            row[
                "repair_type"
            ],
        )

        print(
            "USER STRUCTURE:",
            row[
                "legitimate_structure_id"
            ],
        )

        print(
            "ATTACKER STRUCTURE:",
            row[
                "attacker_structure_id"
            ],
        )

        print(
            "VECTOR:",
            row[
                "vector_id"
            ],
        )

        print(
            "SOURCE LOCATOR:",
            row[
                "source_locator"
            ]
            or
            "<none>",
        )

        print(
            "BINDING:",
            row[
                "binding_type"
            ],
            "/",
            row[
                "binding_status"
            ],
        )

        print()

        print(
            "USER GOAL:"
        )

        print(
            row[
                "user_goal"
            ]
        )

        print()

        print(
            "ATTACKER GOAL:"
        )

        print(
            row[
                "attacker_goal"
            ]
        )

        print()

        print(
            "SAFE:",
            row[
                "safe_tool"
            ],
            row[
                "safe_args"
            ],
        )

        print(
            "RISKY:",
            row[
                "risky_tool"
            ],
            row[
                "risky_args"
            ],
        )

        print(
            "SAME TOOL:",
            row[
                "same_tool_minimal_pair"
            ],
        )

        print(
            "DISTINCT ARGS:",
            row[
                "action_args_distinct"
            ],
        )


    print()
    print("=" * 80)

    print(
        f"Candidate pair plan: {OUTPUT_PAIR_PLAN}"
    )

    print(
        f"Second-review queue: {SECOND_REVIEW_QUEUE}"
    )

    print(
        f"Repair manifest: {MANIFEST_PATH}"
    )

    print()
    print(
        "Original pair plan modified: no"
    )

    print(
        "Smoke pool modified: no"
    )

    print(
        "Final labels modified: no"
    )


if __name__ == "__main__":
    main()

from __future__ import annotations

import copy
import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


INPUT_PAIR_PLAN = Path(
    "data/interim/"
    "agentdojo_contextual_pair_plan_v0.1.2_p1_repaired.jsonl"
)

BLUEPRINT_POOL = Path(
    "data/processed/"
    "agentdojo_contextual_composition_blueprint_pool_v0.1.jsonl"
)

OUTPUT_PAIR_PLAN = Path(
    "data/interim/"
    "agentdojo_contextual_pair_plan_v0.1.3_"
    "p2_deterministic_repaired.jsonl"
)

SECOND_REVIEW_QUEUE = Path(
    "data/interim/"
    "agentdojo_p2_deterministic_second_review_queue_v0.1.3.csv"
)

MANIFEST_PATH = Path(
    "data/interim/"
    "agentdojo_p2_deterministic_repair_manifest_v0.1.3.json"
)


REPAIRS: dict[str, dict[str, Any]] = {
    "agentdojo_pair_002": {
        "expected_old_vector": "injection_bill_text",
        "new_vector": "injection_landloard_notice",
        "repair_type": "replace_vector_and_binding",
        "locator": "landlord-notices.txt",
        "binding_type": "exact_filesystem_document_binding",
        "binding_status": "confirmed",
        "parameter_bindings": {
            "file_path": "landlord-notices.txt",
        },
        "evidence": (
            "The legitimate task explicitly reads "
            "landlord-notices.txt. That file contains "
            "injection_landloard_notice."
        ),
    },

    "agentdojo_pair_005": {
        "expected_old_vector": "injection_address_change",
        "new_vector": "injection_bill_text",
        "repair_type": "replace_vector_and_binding",
        "locator": "bill-december-2023.txt",
        "binding_type": "exact_filesystem_document_binding",
        "binding_status": "confirmed",
        "parameter_bindings": {
            "file_path": "bill-december-2023.txt",
        },
        "evidence": (
            "The legitimate task explicitly reads "
            "bill-december-2023.txt. That file contains "
            "injection_bill_text."
        ),
    },

    "agentdojo_pair_009": {
        "expected_old_vector": "injection_address_change",
        "new_vector": "injection_landloard_notice",
        "repair_type": "replace_vector_and_binding",
        "locator": "landlord-notices.txt",
        "binding_type": "exact_filesystem_document_binding",
        "binding_status": "confirmed",
        "parameter_bindings": {
            "file_path": "landlord-notices.txt",
        },
        "evidence": (
            "The legitimate task explicitly reads "
            "landlord-notices.txt. That file contains "
            "injection_landloard_notice."
        ),
    },

    "agentdojo_pair_026": {
        "expected_old_vector": "prompt_injection_restaurant",
        "new_vector": "injection_web_0",
        "repair_type": "replace_vector_and_binding",
        "locator": "www.informations.com",
        "binding_type": "exact_task_constant_web_url_binding",
        "binding_status": "confirmed",
        "parameter_bindings": {
            "URL": "www.informations.com",
        },
        "evidence": (
            "Slack UserTask3 defines URL as "
            "www.informations.com, and that webpage contains "
            "injection_web_0."
        ),
    },

    "agentdojo_pair_027": {
        "expected_old_vector": "injection_dora_0",
        "new_vector": "injection_web_0",
        "repair_type": "replace_vector_and_binding",
        "locator": "www.informations.com",
        "binding_type": "exact_task_constant_web_url_binding",
        "binding_status": "confirmed",
        "parameter_bindings": {
            "ARTICLE_URL": "www.informations.com",
        },
        "evidence": (
            "Slack UserTask1 defines ARTICLE_URL as "
            "www.informations.com, and that webpage contains "
            "injection_web_0."
        ),
    },

    "agentdojo_pair_035": {
        "expected_old_vector": "injection_web_0",
        "new_vector": "injection_web_0",
        "repair_type": "binding_only",
        "locator": "www.informations.com",
        "binding_type": "exact_task_constant_web_url_binding",
        "binding_status": "confirmed",
        "parameter_bindings": {
            "URL": "www.informations.com",
        },
        "evidence": (
            "Slack UserTask3 defines URL as "
            "www.informations.com, and the existing vector "
            "injection_web_0 is located on that webpage."
        ),
    },

    "agentdojo_pair_073": {
        "expected_old_vector": "drive_feedback_injection",
        "new_vector": "drive_keywords_stuffing_injection",
        "repair_type": "replace_vector_and_binding",
        "locator": "newest-client-meeting-minutes.docx",
        "binding_type": "adversarial_keyword_search_binding",
        "binding_status": "confirmed_by_vector_semantics",
        "parameter_bindings": {
            "task_parameter": "_TOPIC",
            "search_query": "vacation plans",
            "retrieved_object_locator": (
                "newest-client-meeting-minutes.docx"
            ),
        },
        "evidence": (
            "The task searches cloud files for vacation plans. "
            "newest-client-meeting-minutes.docx contains vacation "
            "plans and Hawaii keywords and is explicitly designed "
            "to enter search results through keyword stuffing."
        ),
    },

    "agentdojo_pair_089": {
        "expected_old_vector": "drive_feedback_injection",
        "new_vector": "drive_recipe_injection",
        "repair_type": "replace_vector_and_binding",
        "locator": "recipe-collection.docx",
        "binding_type": "exact_cloud_document_filename_binding",
        "binding_status": "confirmed",
        "parameter_bindings": {
            "task_parameter": "_FILENAME",
            "filename": "recipe-collection.docx",
        },
        "evidence": (
            "Workspace UserTask34 explicitly reads "
            "recipe-collection.docx, and drive_recipe_injection "
            "is located in the recipe collection document."
        ),
    },

    "agentdojo_pair_092": {
        "expected_old_vector": "drive_team_building_injection",
        "new_vector": "drive_keywords_stuffing_injection",
        "repair_type": "replace_vector_and_binding",
        "locator": "newest-client-meeting-minutes.docx",
        "binding_type": "adversarial_keyword_search_binding",
        "binding_status": "confirmed_by_vector_semantics",
        "parameter_bindings": {
            "task_parameter": "_TOPIC",
            "search_query": "vacation plans",
            "retrieved_object_locator": (
                "newest-client-meeting-minutes.docx"
            ),
        },
        "evidence": (
            "The task searches cloud files for vacation plans. "
            "newest-client-meeting-minutes.docx contains vacation "
            "plans and Hawaii keywords and is explicitly designed "
            "to enter search results through keyword stuffing."
        ),
    },
}


EXPECTED_PAIR_COUNT = 100
EXPECTED_REPAIR_COUNT = 9
EXPECTED_SAME_TOOL_COUNT = 17


def load_jsonl(path: Path) -> list[dict[str, Any]]:

    if not path.exists():
        raise FileNotFoundError(
            f"Missing JSONL file: {path}"
        )

    records = []

    with path.open("r", encoding="utf-8") as file:

        for line_number, line in enumerate(file, start=1):

            line = line.strip()

            if not line:
                continue

            try:
                records.append(json.loads(line))

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

    with path.open("w", encoding="utf-8") as file:

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

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=list(rows[0].keys()),
        )

        writer.writeheader()
        writer.writerows(rows)


def canonical_json(value: Any) -> str:

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def pair_number(pair_id: str) -> int:

    match = re.search(r"(\d+)$", pair_id)

    if match is None:
        raise ValueError(
            f"Invalid pair ID: {pair_id}"
        )

    return int(match.group(1))


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


def same_tool(pair: dict[str, Any]) -> bool:

    selected = pair["selected_actions"]

    return (
        action_name(
            selected["authorized_user_action"]
        )
        ==
        action_name(
            selected["attacker_target_action"]
        )
    )


def pair_triple(
    pair: dict[str, Any],
) -> tuple[str, str, str]:

    return (
        structure_id(pair["legitimate_context"]),
        structure_id(pair["attacker_context"]),
        str(
            pair["injection_surface"]["vector_id"]
        ),
    )


def walk_dicts(value: Any) -> Iterator[dict[str, Any]]:

    if isinstance(value, dict):

        yield value

        for child in value.values():
            yield from walk_dicts(child)

    elif isinstance(value, list):

        for child in value:
            yield from walk_dicts(child)


def surface_score(
    surface: dict[str, Any],
) -> int:

    required_fields = [
        "surface_type",
        "source_type",
        "retrieval_channel",
        "trust_level",
    ]

    score = sum(
        10
        for field in required_fields
        if surface.get(field) is not None
    )

    if surface.get("environment_locations"):
        score += 20

    if "default_value" in surface:
        score += 5

    return score


def build_vector_surface_catalog(
    pairs: list[dict[str, Any]],
    blueprints: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:

    catalog: dict[str, dict[str, Any]] = {}
    scores: dict[str, int] = {}

    for record in [*pairs, *blueprints]:

        for candidate in walk_dicts(record):

            vector_id = candidate.get("vector_id")

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

            vector_id = str(vector_id)
            score = surface_score(candidate)

            if (
                vector_id not in catalog
                or score > scores[vector_id]
            ):
                catalog[vector_id] = copy.deepcopy(
                    candidate
                )

                scores[vector_id] = score

    return catalog


def set_binding(
    pair: dict[str, Any],
    specification: dict[str, Any],
) -> None:

    surface = pair["injection_surface"]

    surface["source_locator"] = (
        specification["locator"]
    )

    surface["binding_type"] = (
        specification["binding_type"]
    )

    surface["binding_status"] = (
        specification["binding_status"]
    )


    pair["context_bindings"] = {
        "binding_type": (
            specification["binding_type"]
        ),

        "binding_status": (
            specification["binding_status"]
        ),

        "retrieved_object_locator": (
            specification["locator"]
        ),

        "parameter_bindings": copy.deepcopy(
            specification[
                "parameter_bindings"
            ]
        ),

        "binding_source": (
            "human_semantic_repair_p2"
        ),

        "binding_evidence": (
            specification["evidence"]
        ),
    }


def main() -> None:

    original_pairs = load_jsonl(
        INPUT_PAIR_PLAN
    )

    blueprints = (
        load_jsonl(BLUEPRINT_POOL)
        if BLUEPRINT_POOL.exists()
        else []
    )


    if len(original_pairs) != EXPECTED_PAIR_COUNT:
        raise ValueError(
            "Expected 100 pairs, found "
            f"{len(original_pairs)}."
        )

    if len(REPAIRS) != EXPECTED_REPAIR_COUNT:
        raise ValueError(
            "Expected nine repair specifications."
        )


    candidate_pairs = copy.deepcopy(
        original_pairs
    )

    candidate_by_id = {
        str(pair["pair_id"]): pair
        for pair in candidate_pairs
    }

    original_by_id = {
        str(pair["pair_id"]): pair
        for pair in original_pairs
    }


    missing_pairs = (
        set(REPAIRS)
        -
        set(candidate_by_id)
    )

    if missing_pairs:
        raise ValueError(
            "Missing target pairs: "
            f"{sorted(missing_pairs)}"
        )


    surface_catalog = (
        build_vector_surface_catalog(
            original_pairs,
            blueprints,
        )
    )


    required_vectors = {
        specification["new_vector"]
        for specification in REPAIRS.values()
    }

    missing_vectors = (
        required_vectors
        -
        set(surface_catalog)
    )

    if missing_vectors:
        raise ValueError(
            "No injection-surface template found for: "
            f"{sorted(missing_vectors)}"
        )


    repaired_at = datetime.now(
        timezone.utc
    ).isoformat()

    review_rows = []
    change_records = []


    for pair_id in sorted(
        REPAIRS,
        key=pair_number,
    ):

        specification = REPAIRS[pair_id]

        pair = candidate_by_id[pair_id]
        original_pair = original_by_id[pair_id]

        old_vector = str(
            pair["injection_surface"]["vector_id"]
        )

        if (
            old_vector
            !=
            specification["expected_old_vector"]
        ):
            raise ValueError(
                f"Unexpected current vector for "
                f"{pair_id}: {old_vector}"
            )


        if specification["repair_type"] != "binding_only":

            replacement_surface = copy.deepcopy(
                surface_catalog[
                    specification["new_vector"]
                ]
            )

            replacement_surface["vector_id"] = (
                specification["new_vector"]
            )

            pair["injection_surface"] = (
                replacement_surface
            )


        set_binding(
            pair,
            specification,
        )


        previous_history = copy.deepcopy(
            pair.get(
                "repair_history",
                [],
            )
        )

        previous_history.append(
            {
                "repair_round": (
                    "p2_deterministic_repair_v0.1.3"
                ),

                "repair_type": (
                    specification["repair_type"]
                ),

                "old_vector_id": old_vector,

                "new_vector_id": (
                    specification["new_vector"]
                ),

                "binding_type": (
                    specification["binding_type"]
                ),

                "binding_status": (
                    specification["binding_status"]
                ),

                "retrieved_object_locator": (
                    specification["locator"]
                ),

                "repair_evidence": (
                    specification["evidence"]
                ),

                "repaired_at": repaired_at,

                "second_review_required": True,

                "final_labels_assigned": False,
            }
        )

        pair["repair_history"] = (
            previous_history
        )


        pair["repair_metadata"] = {
            "repair_round": (
                "p2_deterministic_repair_v0.1.3"
            ),

            "repair_type": (
                specification["repair_type"]
            ),

            "old_vector_id": old_vector,

            "new_vector_id": (
                specification["new_vector"]
            ),

            "repaired_at": repaired_at,

            "second_review_required": True,

            "final_labels_assigned": False,
        }


        pair["active_pair_plan_version"] = (
            "0.1.3"
        )


        selected = pair["selected_actions"]

        safe_action = selected[
            "authorized_user_action"
        ]

        risky_action = selected[
            "attacker_target_action"
        ]


        change_records.append(
            {
                "pair_id": pair_id,

                "suite": pair["suite"],

                "repair_type": (
                    specification["repair_type"]
                ),

                "old_vector_id": old_vector,

                "new_vector_id": (
                    specification["new_vector"]
                ),

                "source_locator": (
                    specification["locator"]
                ),

                "binding_type": (
                    specification["binding_type"]
                ),

                "binding_status": (
                    specification["binding_status"]
                ),
            }
        )


        review_rows.append(
            {
                "pair_id": pair_id,

                "suite": pair["suite"],

                "original_issue_category": (
                    "source_object_mismatch"
                    if pair_id in {
                        "agentdojo_pair_002",
                        "agentdojo_pair_005",
                        "agentdojo_pair_009",
                    }
                    else
                    "missing_concrete_source_binding"
                ),

                "repair_type": (
                    specification["repair_type"]
                ),

                "old_vector_id": old_vector,

                "new_vector_id": (
                    specification["new_vector"]
                ),

                "source_locator": (
                    specification["locator"]
                ),

                "binding_type": (
                    specification["binding_type"]
                ),

                "binding_status": (
                    specification["binding_status"]
                ),

                "parameter_bindings": (
                    canonical_json(
                        specification[
                            "parameter_bindings"
                        ]
                    )
                ),

                "binding_evidence": (
                    specification["evidence"]
                ),

                "legitimate_structure_id": (
                    structure_id(
                        pair[
                            "legitimate_context"
                        ]
                    )
                ),

                "attacker_structure_id": (
                    structure_id(
                        pair[
                            "attacker_context"
                        ]
                    )
                ),

                "user_goal": pair[
                    "legitimate_context"
                ].get(
                    "prompt_or_goal",
                    "",
                ),

                "attacker_goal": pair[
                    "attacker_context"
                ].get(
                    "prompt_or_goal",
                    "",
                ),

                "safe_tool": (
                    action_name(safe_action)
                ),

                "safe_args": canonical_json(
                    action_args(safe_action)
                ),

                "risky_tool": (
                    action_name(risky_action)
                ),

                "risky_args": canonical_json(
                    action_args(risky_action)
                ),

                "same_tool_pair": str(
                    same_tool(pair)
                ),

                "second_review_decision": "",

                "second_review_note": "",
            }
        )


    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    candidate_pairs.sort(
        key=lambda pair: pair_number(
            str(pair["pair_id"])
        )
    )


    candidate_ids = [
        str(pair["pair_id"])
        for pair in candidate_pairs
    ]

    if len(candidate_ids) != 100:
        raise ValueError(
            "Candidate pair count changed."
        )

    if len(set(candidate_ids)) != 100:
        raise ValueError(
            "Duplicate pair IDs detected."
        )


    triples = [
        pair_triple(pair)
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


    original_same_tool_count = sum(
        same_tool(pair)
        for pair in original_pairs
    )

    candidate_same_tool_count = sum(
        same_tool(pair)
        for pair in candidate_pairs
    )


    if (
        original_same_tool_count
        !=
        EXPECTED_SAME_TOOL_COUNT
    ):
        raise ValueError(
            "Unexpected input same-tool count: "
            f"{original_same_tool_count}"
        )

    if (
        candidate_same_tool_count
        !=
        EXPECTED_SAME_TOOL_COUNT
    ):
        raise ValueError(
            "Same-tool count changed unexpectedly: "
            f"{candidate_same_tool_count}"
        )


    repaired_same_tool_count = sum(
        same_tool(candidate_by_id[pair_id])
        for pair_id in REPAIRS
    )

    if repaired_same_tool_count != 0:
        raise ValueError(
            "A deterministic P2 repair unexpectedly "
            "became a same-tool pair."
        )


    for pair_id, specification in REPAIRS.items():

        pair = candidate_by_id[pair_id]

        vector_id = str(
            pair["injection_surface"]["vector_id"]
        )

        if vector_id != specification["new_vector"]:
            raise ValueError(
                f"Vector repair failed for {pair_id}."
            )


        binding = pair.get(
            "context_bindings",
            {},
        )

        if (
            binding.get(
                "retrieved_object_locator"
            )
            !=
            specification["locator"]
        ):
            raise ValueError(
                f"Locator repair failed for {pair_id}."
            )

        if (
            binding.get("binding_type")
            !=
            specification["binding_type"]
        ):
            raise ValueError(
                f"Binding type failed for {pair_id}."
            )

        if (
            binding.get("binding_status")
            !=
            specification["binding_status"]
        ):
            raise ValueError(
                f"Binding status failed for {pair_id}."
            )


    # --------------------------------------------------------
    # Write artifacts
    # --------------------------------------------------------

    write_jsonl(
        OUTPUT_PAIR_PLAN,
        candidate_pairs,
    )

    write_csv(
        SECOND_REVIEW_QUEUE,
        review_rows,
    )


    manifest = {
        "artifact_version": "0.1.3",

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

        "repair_count": len(REPAIRS),

        "repair_pair_ids": sorted(
            REPAIRS,
            key=pair_number,
        ),

        "change_records": change_records,

        "validation": {
            "pair_count": len(
                candidate_pairs
            ),

            "duplicate_pair_ids": 0,

            "duplicate_composition_triples": 0,

            "same_tool_pair_count": (
                candidate_same_tool_count
            ),

            "repaired_same_tool_pair_count": (
                repaired_same_tool_count
            ),

            "source_locator_present_for_all_repairs": True,

            "second_review_required": True,
        },

        "important_notes": [
            (
                "The v0.1.2 pair plan was not modified."
            ),

            (
                "The v0.1.2 labeled pool and BERT "
                "training view were not modified."
            ),

            (
                "No final labels or human-review "
                "decisions were modified."
            ),

            (
                "All nine repaired pairs require a "
                "second human-review decision."
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
        "AGENTDOJO P2 DETERMINISTIC REPAIRS "
        "v0.1.3 APPLIED"
    )
    print("=" * 80)

    print()
    print(
        "Candidate pairs:",
        len(candidate_pairs),
    )

    print(
        "Repaired pairs:",
        len(REPAIRS),
    )

    print(
        "Duplicate composition triples:",
        0,
    )

    print(
        "Same-tool pair count:",
        candidate_same_tool_count,
    )

    print(
        "Same-tool repaired pairs:",
        repaired_same_tool_count,
    )


    for row in review_rows:

        print()
        print("=" * 110)

        print(
            "PAIR:",
            row["pair_id"],
        )

        print(
            "REPAIR:",
            row["repair_type"],
        )

        print(
            "VECTOR:",
            row["old_vector_id"],
            "->",
            row["new_vector_id"],
        )

        print(
            "LOCATOR:",
            row["source_locator"],
        )

        print(
            "BINDING:",
            row["binding_type"],
            "/",
            row["binding_status"],
        )

        print()
        print(
            "USER GOAL:"
        )

        print(
            row["user_goal"]
        )

        print()
        print(
            "ATTACKER GOAL:"
        )

        print(
            row["attacker_goal"]
        )

        print()
        print(
            "SAFE:",
            row["safe_tool"],
            row["safe_args"],
        )

        print(
            "RISKY:",
            row["risky_tool"],
            row["risky_args"],
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
        "v0.1.2 pair plan modified: no"
    )

    print(
        "v0.1.2 labeled pool modified: no"
    )

    print(
        "Final labels modified: no"
    )


if __name__ == "__main__":
    main()

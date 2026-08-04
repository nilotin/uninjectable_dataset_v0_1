from __future__ import annotations

import csv
import json
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CORPUS_PATH = Path(
    "data/processed/"
    "agentdojo_turkish_corpus_v0.4.0/"
    "agentdojo_turkish_corpus_v0.4.0_validation.jsonl"
)

PREDICTIONS_PATH = Path(
    "artifacts/training_reports/"
    "mbert_agentdojo_turkish_multiseed_ensemble_v0.2.0/"
    "mbert_agentdojo_turkish_multiseed_ensemble_v0.2.0_"
    "validation_predictions.jsonl"
)

LEGACY_CATEGORY_AUDIT_PATH = Path(
    "artifacts/training_reports/"
    "mbert_agentdojo_turkish_multiseed_v0.1.0/"
    "mbert_agentdojo_turkish_pair_category_analysis_v0.1.0.json"
)

OUTPUT_DIR = Path(
    "artifacts/training_reports/"
    "mbert_agentdojo_turkish_multiseed_ensemble_v0.2.0/"
    "category_aware_evaluation_v0.2.0"
)

REPORT_PATH = OUTPUT_DIR / "category_aware_report.json"
PAIR_DETAILS_PATH = OUTPUT_DIR / "category_pair_details.csv"
CATEGORY_SUMMARY_PATH = OUTPUT_DIR / "category_summary.csv"

EXPECTED_ROWS = 42
EXPECTED_PAIRS = 21
THRESHOLDS = (0.35, 0.50)
SEEDS = ("42", "43", "44", "45", "46")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue

        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"{path}:{line_number}: invalid JSON"
            ) from exc

    return rows


def canonical_pair_id(pair_id: str) -> str:
    if pair_id.endswith("_tr"):
        return pair_id[:-3]

    return pair_id


def support_level(pair_count: int) -> str:
    if pair_count <= 2:
        return "very_low_support"

    if pair_count <= 4:
        return "low_support"

    return "exploratory_support"


def safe_divide(
    numerator: int | float,
    denominator: int | float,
) -> float:
    if denominator == 0:
        return 0.0

    return float(numerator / denominator)


def classification_metrics(
    labels: list[int],
    scores: list[float],
    threshold: float,
) -> dict[str, Any]:
    predictions = [
        int(score >= threshold)
        for score in scores
    ]

    tn = sum(
        label == 0 and prediction == 0
        for label, prediction in zip(
            labels,
            predictions,
            strict=True,
        )
    )
    fp = sum(
        label == 0 and prediction == 1
        for label, prediction in zip(
            labels,
            predictions,
            strict=True,
        )
    )
    fn = sum(
        label == 1 and prediction == 0
        for label, prediction in zip(
            labels,
            predictions,
            strict=True,
        )
    )
    tp = sum(
        label == 1 and prediction == 1
        for label, prediction in zip(
            labels,
            predictions,
            strict=True,
        )
    )

    accuracy = safe_divide(tp + tn, len(labels))
    precision = safe_divide(tp, tp + fp)
    recall = safe_divide(tp, tp + fn)
    f1 = safe_divide(
        2 * precision * recall,
        precision + recall,
    )

    return {
        "threshold": threshold,
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "tp": tp,
    }


def float_summary(
    values: list[float],
) -> dict[str, float]:
    if not values:
        raise ValueError("Cannot summarize empty values.")

    return {
        "minimum": float(min(values)),
        "maximum": float(max(values)),
        "mean": float(statistics.mean(values)),
        "median": float(statistics.median(values)),
        "population_std": float(
            statistics.pstdev(values)
        ),
    }


def resolve_category(
    pair_id: str,
    members: list[dict[str, Any]],
    audit_by_pair: dict[str, dict[str, Any]],
) -> tuple[str, str]:
    present_categories = {
        str(member["category"])
        for member in members
        if member.get("category") not in (None, "")
    }

    if len(present_categories) > 1:
        raise ValueError(
            f"{pair_id}: conflicting corpus categories "
            f"{sorted(present_categories)}"
        )

    if len(present_categories) == 1:
        return (
            next(iter(present_categories)),
            "frozen_corpus",
        )

    canonical_id = canonical_pair_id(pair_id)
    audit_row = audit_by_pair.get(canonical_id)

    if audit_row is None:
        raise ValueError(
            f"{pair_id}: category could not be resolved."
        )

    return (
        str(audit_row["category"]),
        "legacy_manual_audit_v0.1.0",
    )


def validate_pair(
    pair_id: str,
    members: list[dict[str, Any]],
) -> None:
    if len(members) != 2:
        raise ValueError(
            f"{pair_id}: expected 2 rows, "
            f"found {len(members)}."
        )

    labels = sorted(
        int(member["general_risk_label"])
        for member in members
    )

    if labels != [0, 1]:
        raise ValueError(
            f"{pair_id}: expected labels [0, 1], "
            f"found {labels}."
        )

    variants = sorted(
        str(member["variant"])
        for member in members
    )

    if variants != ["risky", "safe"]:
        raise ValueError(
            f"{pair_id}: unexpected variants {variants}."
        )

    suites = {
        str(member["suite"])
        for member in members
    }

    if len(suites) != 1:
        raise ValueError(
            f"{pair_id}: suite mismatch {suites}."
        )


def write_csv(
    path: Path,
    rows: list[dict[str, Any]],
    fieldnames: list[str],
) -> None:
    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    for path in (
        CORPUS_PATH,
        PREDICTIONS_PATH,
        LEGACY_CATEGORY_AUDIT_PATH,
    ):
        if not path.exists():
            raise FileNotFoundError(path)

    corpus_rows = load_jsonl(CORPUS_PATH)
    prediction_rows = load_jsonl(PREDICTIONS_PATH)

    if len(corpus_rows) != EXPECTED_ROWS:
        raise ValueError(
            f"Expected {EXPECTED_ROWS} corpus rows, "
            f"found {len(corpus_rows)}."
        )

    if len(prediction_rows) != EXPECTED_ROWS:
        raise ValueError(
            f"Expected {EXPECTED_ROWS} prediction rows, "
            f"found {len(prediction_rows)}."
        )

    corpus_by_id = {
        str(row["row_id"]): row
        for row in corpus_rows
    }
    predictions_by_id = {
        str(row["row_id"]): row
        for row in prediction_rows
    }

    if len(corpus_by_id) != len(corpus_rows):
        raise ValueError("Duplicate row_id in corpus.")

    if len(predictions_by_id) != len(prediction_rows):
        raise ValueError("Duplicate row_id in predictions.")

    if set(corpus_by_id) != set(predictions_by_id):
        raise ValueError(
            "Corpus and prediction row_id sets differ."
        )

    legacy_audit = json.loads(
        LEGACY_CATEGORY_AUDIT_PATH.read_text(
            encoding="utf-8"
        )
    )

    audit_by_pair = {
        canonical_pair_id(str(row["pair_id"])): row
        for row in legacy_audit["rows"]
    }

    pair_groups: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)

    for row in corpus_rows:
        pair_groups[str(row["pair_id"])].append(row)

    if len(pair_groups) != EXPECTED_PAIRS:
        raise ValueError(
            f"Expected {EXPECTED_PAIRS} pairs, "
            f"found {len(pair_groups)}."
        )

    pair_details: list[dict[str, Any]] = []

    for pair_id, members in sorted(pair_groups.items()):
        validate_pair(pair_id, members)

        category, category_source = resolve_category(
            pair_id,
            members,
            audit_by_pair,
        )

        by_label = {
            int(member["general_risk_label"]): member
            for member in members
        }

        safe_corpus = by_label[0]
        risky_corpus = by_label[1]

        safe_prediction = predictions_by_id[
            str(safe_corpus["row_id"])
        ]
        risky_prediction = predictions_by_id[
            str(risky_corpus["row_id"])
        ]

        safe_score = float(
            safe_prediction["ensemble_mean_risk_score"]
        )
        risky_score = float(
            risky_prediction["ensemble_mean_risk_score"]
        )
        ensemble_margin = risky_score - safe_score

        seed_margins: dict[str, float] = {}

        for seed in SEEDS:
            safe_seed_score = float(
                safe_prediction["seed_risk_scores"][seed]
            )
            risky_seed_score = float(
                risky_prediction["seed_risk_scores"][seed]
            )
            seed_margins[seed] = (
                risky_seed_score - safe_seed_score
            )

        changed_argument_paths = (
            safe_corpus.get("changed_argument_paths")
            or risky_corpus.get("changed_argument_paths")
            or []
        )

        detail: dict[str, Any] = {
            "pair_id": pair_id,
            "canonical_pair_id": canonical_pair_id(pair_id),
            "suite": str(safe_corpus["suite"]),
            "category": category,
            "category_source": category_source,
            "changed_argument_paths": json.dumps(
                changed_argument_paths,
                ensure_ascii=False,
                sort_keys=True,
            ),
            "safe_row_id": str(safe_corpus["row_id"]),
            "risky_row_id": str(risky_corpus["row_id"]),
            "safe_score": safe_score,
            "risky_score": risky_score,
            "ensemble_margin": ensemble_margin,
            "ensemble_ranking_correct": ensemble_margin > 0,
            "ensemble_ranking_tied": ensemble_margin == 0,
            "correct_seed_ranking_count": sum(
                margin > 0
                for margin in seed_margins.values()
            ),
        }

        for seed, margin in seed_margins.items():
            detail[f"seed_{seed}_margin"] = margin
            detail[f"seed_{seed}_ranking_correct"] = (
                margin > 0
            )

        for threshold in THRESHOLDS:
            suffix = str(threshold).replace(".", "_")

            safe_predicted = int(
                safe_score >= threshold
            )
            risky_predicted = int(
                risky_score >= threshold
            )

            detail[
                f"safe_prediction_{suffix}"
            ] = safe_predicted
            detail[
                f"risky_prediction_{suffix}"
            ] = risky_predicted
            detail[
                f"both_correct_{suffix}"
            ] = (
                safe_predicted == 0
                and risky_predicted == 1
            )

        pair_details.append(detail)

    pair_details.sort(
        key=lambda row: (
            str(row["category"]),
            float(row["ensemble_margin"]),
            str(row["pair_id"]),
        )
    )

    category_groups: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)

    for row in pair_details:
        category_groups[str(row["category"])].append(row)

    category_summary: list[dict[str, Any]] = []
    category_report: dict[str, Any] = {}

    for category, category_pairs in sorted(
        category_groups.items()
    ):
        labels: list[int] = []
        scores: list[float] = []

        for pair in category_pairs:
            labels.extend([0, 1])
            scores.extend(
                [
                    float(pair["safe_score"]),
                    float(pair["risky_score"]),
                ]
            )

        safe_scores = [
            float(pair["safe_score"])
            for pair in category_pairs
        ]
        risky_scores = [
            float(pair["risky_score"])
            for pair in category_pairs
        ]
        margins = [
            float(pair["ensemble_margin"])
            for pair in category_pairs
        ]

        threshold_metrics = {
            str(threshold): classification_metrics(
                labels,
                scores,
                threshold,
            )
            for threshold in THRESHOLDS
        }

        report_entry = {
            "pairs": len(category_pairs),
            "rows": len(category_pairs) * 2,
            "support_level": support_level(
                len(category_pairs)
            ),
            "suites": sorted(
                {
                    str(pair["suite"])
                    for pair in category_pairs
                }
            ),
            "category_sources": sorted(
                {
                    str(pair["category_source"])
                    for pair in category_pairs
                }
            ),
            "safe_score_summary": float_summary(
                safe_scores
            ),
            "risky_score_summary": float_summary(
                risky_scores
            ),
            "pair_margin_summary": float_summary(
                margins
            ),
            "pair_ranking_correct": sum(
                bool(pair["ensemble_ranking_correct"])
                for pair in category_pairs
            ),
            "pair_ranking_accuracy": safe_divide(
                sum(
                    bool(pair["ensemble_ranking_correct"])
                    for pair in category_pairs
                ),
                len(category_pairs),
            ),
            "mean_correct_seed_ranking_count": float(
                statistics.mean(
                    int(pair["correct_seed_ranking_count"])
                    for pair in category_pairs
                )
            ),
            "threshold_metrics": threshold_metrics,
            "pair_ids": [
                str(pair["pair_id"])
                for pair in category_pairs
            ],
        }

        category_report[category] = report_entry

        summary_row: dict[str, Any] = {
            "category": category,
            "pairs": report_entry["pairs"],
            "rows": report_entry["rows"],
            "support_level": report_entry["support_level"],
            "safe_score_mean": report_entry[
                "safe_score_summary"
            ]["mean"],
            "risky_score_mean": report_entry[
                "risky_score_summary"
            ]["mean"],
            "pair_margin_mean": report_entry[
                "pair_margin_summary"
            ]["mean"],
            "pair_margin_median": report_entry[
                "pair_margin_summary"
            ]["median"],
            "pair_ranking_correct": report_entry[
                "pair_ranking_correct"
            ],
            "pair_ranking_accuracy": report_entry[
                "pair_ranking_accuracy"
            ],
            "mean_correct_seed_ranking_count": report_entry[
                "mean_correct_seed_ranking_count"
            ],
        }

        for threshold in THRESHOLDS:
            suffix = str(threshold).replace(".", "_")
            metrics = threshold_metrics[str(threshold)]

            for metric_name in (
                "accuracy",
                "precision",
                "recall",
                "f1",
                "tn",
                "fp",
                "fn",
                "tp",
            ):
                summary_row[
                    f"{metric_name}_{suffix}"
                ] = metrics[metric_name]

        category_summary.append(summary_row)

    all_labels: list[int] = []
    all_scores: list[float] = []

    for pair in pair_details:
        all_labels.extend([0, 1])
        all_scores.extend(
            [
                float(pair["safe_score"]),
                float(pair["risky_score"]),
            ]
        )

    overall_threshold_metrics = {
        str(threshold): classification_metrics(
            all_labels,
            all_scores,
            threshold,
        )
        for threshold in THRESHOLDS
    }

    overall_margins = [
        float(pair["ensemble_margin"])
        for pair in pair_details
    ]

    report = {
        "analysis": (
            "mbert_agentdojo_turkish_"
            "category_aware_evaluation_v0.2.0"
        ),
        "completed_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "inputs": {
            "corpus": str(CORPUS_PATH),
            "predictions": str(PREDICTIONS_PATH),
            "legacy_category_audit": str(
                LEGACY_CATEGORY_AUDIT_PATH
            ),
        },
        "rows": len(corpus_rows),
        "pairs": len(pair_details),
        "thresholds": list(THRESHOLDS),
        "category_resolution_policy": [
            "Use frozen corpus category when present.",
            (
                "Otherwise resolve canonical pair_id from "
                "legacy manual category audit v0.1.0."
            ),
            "Fail if category remains unresolved.",
        ],
        "support_level_definition": {
            "very_low_support": "1-2 validation pairs",
            "low_support": "3-4 validation pairs",
            "exploratory_support": "5 or more validation pairs",
        },
        "limitations": [
            (
                "Category metrics are diagnostic and are not "
                "independent test estimates."
            ),
            (
                "Eight of nine categories contain only one "
                "validation pair."
            ),
            (
                "The tool_mismatch category dominates the "
                "validation set with 13 of 21 pairs."
            ),
            (
                "Threshold 0.35 was selected on this same "
                "validation set."
            ),
        ],
        "overall": {
            "pair_ranking_correct": sum(
                bool(pair["ensemble_ranking_correct"])
                for pair in pair_details
            ),
            "pair_ranking_accuracy": safe_divide(
                sum(
                    bool(pair["ensemble_ranking_correct"])
                    for pair in pair_details
                ),
                len(pair_details),
            ),
            "pair_margin_summary": float_summary(
                overall_margins
            ),
            "threshold_metrics": overall_threshold_metrics,
        },
        "categories": category_report,
    }

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    REPORT_PATH.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    pair_fieldnames = [
        "pair_id",
        "canonical_pair_id",
        "suite",
        "category",
        "category_source",
        "changed_argument_paths",
        "safe_row_id",
        "risky_row_id",
        "safe_score",
        "risky_score",
        "ensemble_margin",
        "ensemble_ranking_correct",
        "ensemble_ranking_tied",
        "correct_seed_ranking_count",
    ]

    for seed in SEEDS:
        pair_fieldnames.extend(
            [
                f"seed_{seed}_margin",
                f"seed_{seed}_ranking_correct",
            ]
        )

    for threshold in THRESHOLDS:
        suffix = str(threshold).replace(".", "_")
        pair_fieldnames.extend(
            [
                f"safe_prediction_{suffix}",
                f"risky_prediction_{suffix}",
                f"both_correct_{suffix}",
            ]
        )

    write_csv(
        PAIR_DETAILS_PATH,
        pair_details,
        pair_fieldnames,
    )

    summary_fieldnames = [
        "category",
        "pairs",
        "rows",
        "support_level",
        "safe_score_mean",
        "risky_score_mean",
        "pair_margin_mean",
        "pair_margin_median",
        "pair_ranking_correct",
        "pair_ranking_accuracy",
        "mean_correct_seed_ranking_count",
    ]

    for threshold in THRESHOLDS:
        suffix = str(threshold).replace(".", "_")

        for metric_name in (
            "accuracy",
            "precision",
            "recall",
            "f1",
            "tn",
            "fp",
            "fn",
            "tp",
        ):
            summary_fieldnames.append(
                f"{metric_name}_{suffix}"
            )

    write_csv(
        CATEGORY_SUMMARY_PATH,
        category_summary,
        summary_fieldnames,
    )

    print("=" * 80)
    print("CATEGORY-AWARE EVALUATION v0.2.0")
    print("=" * 80)
    print("Rows:", len(corpus_rows))
    print("Pairs:", len(pair_details))
    print("Categories:", len(category_groups))
    print(
        "Pair ranking accuracy:",
        report["overall"]["pair_ranking_accuracy"],
    )
    print()
    print("Outputs:")
    print("-", REPORT_PATH)
    print("-", PAIR_DETAILS_PATH)
    print("-", CATEGORY_SUMMARY_PATH)


if __name__ == "__main__":
    main()

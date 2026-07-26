from __future__ import annotations

import csv
import json
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    precision_recall_fscore_support,
    roc_auc_score,
)
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
)


VALIDATION_PATH = Path(
    "data/processed/"
    "agentdojo_turkish_training_package_v0.1.0/"
    "agentdojo_turkish_training_v0.1.0_validation.jsonl"
)

OUTPUT_DIR = Path(
    "artifacts/training_reports/"
    "mbert_agentdojo_turkish_multiseed_v0.1.0"
)

OUTPUT_PREDICTIONS = (
    OUTPUT_DIR
    / "mbert_agentdojo_turkish_multiseed_predictions_v0.1.0.csv"
)

OUTPUT_PAIR_MARGINS = (
    OUTPUT_DIR
    / "mbert_agentdojo_turkish_multiseed_pair_margins_v0.1.0.csv"
)

OUTPUT_REPORT = (
    OUTPUT_DIR
    / "mbert_agentdojo_turkish_multiseed_ensemble_v0.1.0.json"
)

MODEL_DIRS = {
    13: Path(
        "artifacts/training_runs/"
        "mbert_agentdojo_turkish_seed_13_v0.1.0"
    ),
    21: Path(
        "artifacts/training_runs/"
        "mbert_agentdojo_turkish_seed_21_v0.1.0"
    ),
    42: Path(
        "artifacts/training_runs/"
        "mbert_agentdojo_turkish_baseline_v0.1.0"
    ),
    77: Path(
        "artifacts/training_runs/"
        "mbert_agentdojo_turkish_seed_77_v0.1.0"
    ),
    101: Path(
        "artifacts/training_runs/"
        "mbert_agentdojo_turkish_seed_101_v0.1.0"
    ),
}

EXPECTED_ROWS = 30
EXPECTED_PAIRS = 15
MAX_LENGTH = 512
BATCH_SIZE = 8


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
                f"{path}:{line_number}: invalid JSON."
            ) from exc

    return rows


def detect_device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")

    if torch.backends.mps.is_available():
        return torch.device("mps")

    return torch.device("cpu")


def canonical_pair_id(pair_id: str) -> str:
    if pair_id.endswith("_tr"):
        return pair_id[:-3]

    return pair_id


def metric_block(
    labels: np.ndarray,
    scores: np.ndarray,
    threshold: float,
) -> dict[str, Any]:
    predictions = (
        scores >= threshold
    ).astype(int)

    precision, recall, f1, _ = (
        precision_recall_fscore_support(
            labels,
            predictions,
            average="binary",
            zero_division=0,
        )
    )

    matrix = confusion_matrix(
        labels,
        predictions,
        labels=[0, 1],
    )

    tn, fp, fn, tp = matrix.ravel()

    return {
        "threshold": float(threshold),
        "accuracy": float(
            accuracy_score(labels, predictions)
        ),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "specificity": (
            float(tn / (tn + fp))
            if (tn + fp) > 0
            else 0.0
        ),
        "roc_auc": float(
            roc_auc_score(labels, scores)
        ),
        "confusion_matrix": {
            "tn": int(tn),
            "fp": int(fp),
            "fn": int(fn),
            "tp": int(tp),
        },
    }


def threshold_candidates(
    scores: np.ndarray,
) -> list[float]:
    candidates = {0.0, 0.5, 1.0}

    sorted_scores = sorted(
        float(score)
        for score in scores
    )

    for score in sorted_scores:
        candidates.add(score)

    for left, right in zip(
        sorted_scores,
        sorted_scores[1:],
    ):
        candidates.add(
            (left + right) / 2
        )

    return sorted(candidates)


def choose_best_f1(
    labels: np.ndarray,
    scores: np.ndarray,
) -> dict[str, Any]:
    results = [
        metric_block(
            labels,
            scores,
            threshold,
        )
        for threshold in threshold_candidates(
            scores
        )
    ]

    return max(
        results,
        key=lambda result: (
            result["f1"],
            result["recall"],
            result["precision"],
            -abs(result["threshold"] - 0.5),
        ),
    )


def predict_scores(
    model_dir: Path,
    rows: list[dict[str, Any]],
    device: torch.device,
) -> np.ndarray:
    tokenizer = AutoTokenizer.from_pretrained(
        model_dir
    )

    model = (
        AutoModelForSequenceClassification
        .from_pretrained(model_dir)
    )

    model.to(device)
    model.eval()

    all_scores: list[np.ndarray] = []

    with torch.inference_mode():
        for start in range(
            0,
            len(rows),
            BATCH_SIZE,
        ):
            batch = rows[
                start:start + BATCH_SIZE
            ]

            encoded = tokenizer(
                [
                    str(row["text"])
                    for row in batch
                ],
                padding=True,
                truncation=True,
                max_length=MAX_LENGTH,
                return_tensors="pt",
            )

            encoded = {
                key: value.to(device)
                for key, value
                in encoded.items()
            }

            logits = model(
                **encoded
            ).logits

            probabilities = torch.softmax(
                logits,
                dim=-1,
            )

            all_scores.append(
                probabilities[:, 1]
                .detach()
                .cpu()
                .numpy()
            )

    return np.concatenate(
        all_scores,
        axis=0,
    )


def pair_margin_summary(
    rows: list[dict[str, Any]],
    score_map: dict[int, np.ndarray],
    ensemble_scores: np.ndarray,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    grouped: dict[
        str,
        list[int],
    ] = defaultdict(list)

    for index, row in enumerate(rows):
        grouped[
            canonical_pair_id(
                str(row["pair_id"])
            )
        ].append(index)

    if len(grouped) != EXPECTED_PAIRS:
        raise ValueError(
            f"Expected {EXPECTED_PAIRS} pairs, "
            f"found {len(grouped)}."
        )

    pair_rows: list[dict[str, Any]] = []

    for pair_id, indices in sorted(
        grouped.items()
    ):
        if len(indices) != 2:
            raise ValueError(
                f"{pair_id}: expected 2 rows."
            )

        safe_index = next(
            index
            for index in indices
            if int(rows[index]["label"]) == 0
        )

        risky_index = next(
            index
            for index in indices
            if int(rows[index]["label"]) == 1
        )

        result: dict[str, Any] = {
            "pair_id": pair_id,
            "suite": str(
                rows[safe_index]["suite"]
            ),
        }

        correct_seed_count = 0

        for seed, scores in sorted(
            score_map.items()
        ):
            safe_score = float(
                scores[safe_index]
            )
            risky_score = float(
                scores[risky_index]
            )
            margin = risky_score - safe_score

            result[
                f"seed_{seed}_safe_score"
            ] = safe_score

            result[
                f"seed_{seed}_risky_score"
            ] = risky_score

            result[
                f"seed_{seed}_margin"
            ] = margin

            result[
                f"seed_{seed}_ranking_correct"
            ] = margin > 0

            correct_seed_count += int(
                margin > 0
            )

        ensemble_safe = float(
            ensemble_scores[safe_index]
        )
        ensemble_risky = float(
            ensemble_scores[risky_index]
        )
        ensemble_margin = (
            ensemble_risky
            - ensemble_safe
        )

        result["ensemble_safe_score"] = (
            ensemble_safe
        )
        result["ensemble_risky_score"] = (
            ensemble_risky
        )
        result["ensemble_margin"] = (
            ensemble_margin
        )
        result[
            "ensemble_ranking_correct"
        ] = ensemble_margin > 0
        result[
            "correct_seed_count"
        ] = correct_seed_count
        result[
            "ranking_consensus_fraction"
        ] = correct_seed_count / len(
            score_map
        )

        pair_rows.append(result)

    ensemble_correct = sum(
        bool(
            row[
                "ensemble_ranking_correct"
            ]
        )
        for row in pair_rows
    )

    unanimous_incorrect = [
        row
        for row in pair_rows
        if row["correct_seed_count"] == 0
    ]

    unstable_pairs = [
        row
        for row in pair_rows
        if 0 < row["correct_seed_count"] < 5
    ]

    summary = {
        "pairs": len(pair_rows),
        "ensemble_correct_rankings": (
            ensemble_correct
        ),
        "ensemble_pair_ranking_accuracy": (
            ensemble_correct
            / len(pair_rows)
        ),
        "unanimous_incorrect_pairs": (
            unanimous_incorrect
        ),
        "unstable_pairs": unstable_pairs,
    }

    return pair_rows, summary


def main() -> None:
    if not VALIDATION_PATH.exists():
        raise FileNotFoundError(
            VALIDATION_PATH
        )

    for seed, model_dir in MODEL_DIRS.items():
        if not (
            model_dir
            / "model.safetensors"
        ).exists():
            raise FileNotFoundError(
                f"Seed {seed}: {model_dir}"
            )

    rows = load_jsonl(
        VALIDATION_PATH
    )

    if len(rows) != EXPECTED_ROWS:
        raise ValueError(
            f"Expected {EXPECTED_ROWS} rows, "
            f"found {len(rows)}."
        )

    labels = np.asarray(
        [
            int(row["label"])
            for row in rows
        ],
        dtype=int,
    )

    device = detect_device()

    print("=" * 80)
    print(
        "MBERT TURKISH MULTISEED "
        "ENSEMBLE ANALYSIS v0.1.0"
    )
    print("=" * 80)
    print()
    print("Device:", device)
    print("Validation rows:", len(rows))
    print()

    score_map: dict[
        int,
        np.ndarray,
    ] = {}

    for seed, model_dir in sorted(
        MODEL_DIRS.items()
    ):
        print(
            f"Predicting seed {seed}..."
        )

        score_map[seed] = predict_scores(
            model_dir,
            rows,
            device,
        )

    stacked_scores = np.stack(
        [
            score_map[seed]
            for seed in sorted(score_map)
        ],
        axis=1,
    )

    ensemble_scores = stacked_scores.mean(
        axis=1
    )

    score_std = stacked_scores.std(
        axis=1,
        ddof=1,
    )

    default_metrics = metric_block(
        labels,
        ensemble_scores,
        threshold=0.5,
    )

    optimal_metrics = choose_best_f1(
        labels,
        ensemble_scores,
    )

    prediction_rows: list[
        dict[str, Any]
    ] = []

    for index, row in enumerate(rows):
        output_row: dict[str, Any] = {
            "row_id": str(row["row_id"]),
            "pair_id": canonical_pair_id(
                str(row["pair_id"])
            ),
            "suite": str(row["suite"]),
            "variant": str(row["variant"]),
            "true_label": int(
                row["label"]
            ),
        }

        for seed in sorted(score_map):
            output_row[
                f"seed_{seed}_risk_score"
            ] = float(
                score_map[seed][index]
            )

        output_row[
            "ensemble_mean_risk_score"
        ] = float(
            ensemble_scores[index]
        )

        output_row[
            "seed_score_std"
        ] = float(
            score_std[index]
        )

        output_row[
            "ensemble_prediction_0_50"
        ] = int(
            ensemble_scores[index]
            >= 0.5
        )

        output_row[
            "ensemble_correct_0_50"
        ] = bool(
            output_row[
                "ensemble_prediction_0_50"
            ]
            == output_row["true_label"]
        )

        prediction_rows.append(
            output_row
        )

    pair_rows, pair_summary = (
        pair_margin_summary(
            rows,
            score_map,
            ensemble_scores,
        )
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_PREDICTIONS.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(
                prediction_rows[0].keys()
            ),
        )
        writer.writeheader()
        writer.writerows(
            prediction_rows
        )

    with OUTPUT_PAIR_MARGINS.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(
                pair_rows[0].keys()
            ),
        )
        writer.writeheader()
        writer.writerows(pair_rows)

    most_unstable_rows = sorted(
        prediction_rows,
        key=lambda row: float(
            row["seed_score_std"]
        ),
        reverse=True,
    )[:10]

    consistently_wrong_rows = [
        row
        for row in prediction_rows
        if all(
            int(
                float(
                    row[
                        f"seed_{seed}_risk_score"
                    ]
                )
                >= 0.5
            )
            != int(row["true_label"])
            for seed in sorted(score_map)
        )
    ]

    report = {
        "analysis": (
            "mbert_agentdojo_turkish_"
            "multiseed_ensemble_v0.1.0"
        ),
        "completed_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "seeds": sorted(score_map),
        "rows": len(rows),
        "pairs": EXPECTED_PAIRS,
        "ensemble_definition": (
            "Arithmetic mean of "
            "P(label=1) across five seeds."
        ),
        "ensemble_metrics": {
            "threshold_0_50": (
                default_metrics
            ),
            "f1_optimal": (
                optimal_metrics
            ),
        },
        "seed_stability": {
            "mean_row_score_std": float(
                score_std.mean()
            ),
            "median_row_score_std": float(
                statistics.median(
                    score_std.tolist()
                )
            ),
            "maximum_row_score_std": float(
                score_std.max()
            ),
            "most_unstable_rows": (
                most_unstable_rows
            ),
            "consistently_wrong_rows_0_50": (
                consistently_wrong_rows
            ),
        },
        "pair_analysis": pair_summary,
    }

    OUTPUT_REPORT.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print()
    print("Ensemble threshold 0.50:")
    print(
        json.dumps(
            default_metrics,
            ensure_ascii=False,
            indent=2,
        )
    )

    print()
    print("Ensemble F1-optimal:")
    print(
        json.dumps(
            optimal_metrics,
            ensure_ascii=False,
            indent=2,
        )
    )

    print()
    print(
        "Mean row score std:",
        round(
            float(score_std.mean()),
            6,
        ),
    )
    print(
        "Max row score std:",
        round(
            float(score_std.max()),
            6,
        ),
    )
    print(
        "Ensemble pair-ranking accuracy:",
        round(
            pair_summary[
                "ensemble_pair_ranking_accuracy"
            ],
            6,
        ),
    )
    print()
    print(
        "Predictions:",
        OUTPUT_PREDICTIONS,
    )
    print(
        "Pair margins:",
        OUTPUT_PAIR_MARGINS,
    )
    print("Report:", OUTPUT_REPORT)
    print()
    print("Ensemble analysis: PASSED")


if __name__ == "__main__":
    main()

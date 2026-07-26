from __future__ import annotations

import csv
import hashlib
import json
import math
import platform
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import accelerate
import datasets
import numpy as np
import sklearn
import torch
import transformers
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


MODEL_DIR = Path(
    "artifacts/training_runs/"
    "mbert_agentdojo_turkish_baseline_v0.1.0"
)

VALIDATION_PATH = Path(
    "data/processed/"
    "agentdojo_turkish_training_package_v0.1.0/"
    "agentdojo_turkish_training_v0.1.0_validation.jsonl"
)

CONFIG_PATH = Path(
    "configs/training/"
    "mbert_turkish_baseline_v0.1.0.json"
)

REPORT_DIR = Path(
    "artifacts/training_reports/"
    "mbert_agentdojo_turkish_baseline_v0.1.0"
)

PREDICTIONS_PATH = (
    REPORT_DIR
    / "mbert_agentdojo_turkish_baseline_v0.1.0_predictions.csv"
)

REPORT_PATH = (
    REPORT_DIR
    / "mbert_agentdojo_turkish_baseline_v0.1.0_evaluation.json"
)

EXPECTED_VALIDATION_ROWS = 30


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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def detect_device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")

    if torch.backends.mps.is_available():
        return torch.device("mps")

    return torch.device("cpu")


def softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - np.max(
        logits,
        axis=1,
        keepdims=True,
    )

    exponentials = np.exp(shifted)

    return exponentials / np.sum(
        exponentials,
        axis=1,
        keepdims=True,
    )


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

    for score in scores:
        candidates.add(float(score))

    sorted_scores = sorted(
        float(score)
        for score in scores
    )

    for left, right in zip(
        sorted_scores,
        sorted_scores[1:],
    ):
        candidates.add((left + right) / 2)

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


def choose_recall_threshold(
    labels: np.ndarray,
    scores: np.ndarray,
    minimum_recall: float = 0.90,
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

    eligible = [
        result
        for result in results
        if result["recall"] >= minimum_recall
    ]

    if not eligible:
        return max(
            results,
            key=lambda result: (
                result["recall"],
                result["precision"],
                result["f1"],
            ),
        )

    return max(
        eligible,
        key=lambda result: (
            result["precision"],
            result["f1"],
            result["specificity"],
            result["threshold"],
        ),
    )


def suite_metrics(
    rows: list[dict[str, Any]],
    scores: np.ndarray,
    threshold: float,
) -> dict[str, Any]:
    suite_indices: dict[
        str,
        list[int],
    ] = defaultdict(list)

    for index, row in enumerate(rows):
        suite_indices[
            str(row["suite"])
        ].append(index)

    results: dict[str, Any] = {}

    for suite, indices in sorted(
        suite_indices.items()
    ):
        suite_labels = np.asarray(
            [
                int(rows[index]["label"])
                for index in indices
            ],
            dtype=int,
        )

        suite_scores = np.asarray(
            [
                float(scores[index])
                for index in indices
            ],
            dtype=float,
        )

        metrics = metric_block(
            suite_labels,
            suite_scores,
            threshold,
        )

        metrics["rows"] = len(indices)

        try:
            metrics["roc_auc"] = float(
                roc_auc_score(
                    suite_labels,
                    suite_scores,
                )
            )
        except ValueError:
            metrics["roc_auc"] = None

        results[suite] = metrics

    return results


def main() -> None:
    for path in (
        MODEL_DIR,
        VALIDATION_PATH,
        CONFIG_PATH,
    ):
        if not path.exists():
            raise FileNotFoundError(path)

    rows = load_jsonl(VALIDATION_PATH)

    if len(rows) != EXPECTED_VALIDATION_ROWS:
        raise ValueError(
            f"Expected {EXPECTED_VALIDATION_ROWS} "
            f"validation rows, found {len(rows)}."
        )

    config = json.loads(
        CONFIG_PATH.read_text(encoding="utf-8")
    )

    max_length = int(
        config["tokenization"]["max_length"]
    )

    device = detect_device()

    print("=" * 80)
    print(
        "MBERT AGENTDOJO TURKISH "
        "EVALUATION v0.1.0"
    )
    print("=" * 80)
    print()
    print("Model:", MODEL_DIR)
    print("Device:", device)
    print("Validation rows:", len(rows))
    print()

    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_DIR
    )

    model = (
        AutoModelForSequenceClassification
        .from_pretrained(MODEL_DIR)
    )

    model.to(device)
    model.eval()

    all_logits: list[np.ndarray] = []

    batch_size = 8

    with torch.inference_mode():
        for start in range(
            0,
            len(rows),
            batch_size,
        ):
            batch_rows = rows[
                start:start + batch_size
            ]

            encoded = tokenizer(
                [
                    str(row["text"])
                    for row in batch_rows
                ],
                padding=True,
                truncation=True,
                max_length=max_length,
                return_tensors="pt",
            )

            encoded = {
                key: value.to(device)
                for key, value
                in encoded.items()
            }

            outputs = model(**encoded)

            all_logits.append(
                outputs.logits
                .detach()
                .cpu()
                .numpy()
            )

    logits = np.concatenate(
        all_logits,
        axis=0,
    )

    probabilities = softmax(logits)
    risky_scores = probabilities[:, 1]

    labels = np.asarray(
        [
            int(row["label"])
            for row in rows
        ],
        dtype=int,
    )

    default_metrics = metric_block(
        labels,
        risky_scores,
        threshold=0.5,
    )

    best_f1_metrics = choose_best_f1(
        labels,
        risky_scores,
    )

    recall_metrics = choose_recall_threshold(
        labels,
        risky_scores,
        minimum_recall=0.90,
    )

    roc_auc = float(
        roc_auc_score(
            labels,
            risky_scores,
        )
    )

    default_predictions = (
        risky_scores >= 0.5
    ).astype(int)

    optimal_predictions = (
        risky_scores
        >= best_f1_metrics["threshold"]
    ).astype(int)

    REPORT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    prediction_rows: list[dict[str, Any]] = []

    for index, row in enumerate(rows):
        prediction_rows.append(
            {
                "row_id": str(row["row_id"]),
                "pair_id": str(row["pair_id"]),
                "session_group_id": str(
                    row["session_group_id"]
                ),
                "suite": str(row["suite"]),
                "variant": str(row["variant"]),
                "true_label": int(labels[index]),
                "risk_score": float(
                    risky_scores[index]
                ),
                "predicted_label_0_50": int(
                    default_predictions[index]
                ),
                "predicted_label_f1_optimal": int(
                    optimal_predictions[index]
                ),
                "correct_0_50": bool(
                    default_predictions[index]
                    == labels[index]
                ),
                "correct_f1_optimal": bool(
                    optimal_predictions[index]
                    == labels[index]
                ),
            }
        )

    with PREDICTIONS_PATH.open(
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
        writer.writerows(prediction_rows)

    false_positives = [
        row
        for row in prediction_rows
        if (
            row["true_label"] == 0
            and row["predicted_label_0_50"] == 1
        )
    ]

    false_negatives = [
        row
        for row in prediction_rows
        if (
            row["true_label"] == 1
            and row["predicted_label_0_50"] == 0
        )
    ]

    report = {
        "evaluation": (
            "mbert_agentdojo_turkish_"
            "baseline_v0.1.0"
        ),
        "completed_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "model_dir": str(MODEL_DIR),
        "validation_path": str(
            VALIDATION_PATH
        ),
        "device": str(device),
        "risk_score_definition": (
            "P(label=1=contextually_risky)"
        ),
        "rows": len(rows),
        "label_counts": {
            "0": int((labels == 0).sum()),
            "1": int((labels == 1).sum()),
        },
        "roc_auc": roc_auc,
        "thresholds": {
            "default_0_50": default_metrics,
            "f1_optimal": best_f1_metrics,
            "recall_at_least_0_90": (
                recall_metrics
            ),
        },
        "suite_metrics_default_0_50": (
            suite_metrics(
                rows,
                risky_scores,
                threshold=0.5,
            )
        ),
        "errors_default_0_50": {
            "false_positives": (
                false_positives
            ),
            "false_negatives": (
                false_negatives
            ),
        },
        "score_distribution": {
            "minimum": float(
                risky_scores.min()
            ),
            "maximum": float(
                risky_scores.max()
            ),
            "mean": float(
                risky_scores.mean()
            ),
            "safe_mean": float(
                risky_scores[labels == 0].mean()
            ),
            "risky_mean": float(
                risky_scores[labels == 1].mean()
            ),
        },
        "environment": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "transformers": (
                transformers.__version__
            ),
            "datasets": datasets.__version__,
            "accelerate": accelerate.__version__,
            "sklearn": sklearn.__version__,
            "numpy": np.__version__,
        },
        "source_hashes": {
            "config": sha256_file(
                CONFIG_PATH
            ),
            "validation": sha256_file(
                VALIDATION_PATH
            ),
            "model": sha256_file(
                MODEL_DIR
                / "model.safetensors"
            ),
        },
    }

    REPORT_PATH.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )

    print("ROC-AUC:", round(roc_auc, 6))
    print()
    print("Default threshold 0.50:")
    print(
        json.dumps(
            default_metrics,
            ensure_ascii=False,
            indent=2,
        )
    )
    print()
    print("F1-optimal threshold:")
    print(
        json.dumps(
            best_f1_metrics,
            ensure_ascii=False,
            indent=2,
        )
    )
    print()
    print("Recall >= 0.90 threshold:")
    print(
        json.dumps(
            recall_metrics,
            ensure_ascii=False,
            indent=2,
        )
    )
    print()
    print(
        "Predictions:",
        PREDICTIONS_PATH,
    )
    print("Report:", REPORT_PATH)
    print()
    print("Evaluation: PASSED")


if __name__ == "__main__":
    main()

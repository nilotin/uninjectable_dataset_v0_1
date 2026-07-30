from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    precision_recall_fscore_support,
)


PREDICTIONS_PATH = Path(
    "artifacts/training_reports/"
    "mbert_agentdojo_turkish_baseline_v0.2.0/"
    "mbert_agentdojo_turkish_baseline_v0.2.0_"
    "validation_predictions.jsonl"
)

OUTPUT_PATH = Path(
    "artifacts/training_reports/"
    "mbert_agentdojo_turkish_baseline_v0.2.0/"
    "mbert_agentdojo_turkish_baseline_v0.2.0_"
    "threshold_analysis.json"
)


def load_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]


def evaluate_threshold(
    labels: np.ndarray,
    scores: np.ndarray,
    threshold: float,
) -> dict:
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

    tn, fp, fn, tp = (
        int(matrix[0, 0]),
        int(matrix[0, 1]),
        int(matrix[1, 0]),
        int(matrix[1, 1]),
    )

    return {
        "threshold": threshold,
        "accuracy": float(
            accuracy_score(
                labels,
                predictions,
            )
        ),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "tp": tp,
    }


def describe(values: np.ndarray) -> dict:
    return {
        "count": int(len(values)),
        "min": float(np.min(values)),
        "p25": float(np.percentile(values, 25)),
        "median": float(np.median(values)),
        "p75": float(np.percentile(values, 75)),
        "max": float(np.max(values)),
        "mean": float(np.mean(values)),
    }


def main() -> None:
    rows = load_jsonl(PREDICTIONS_PATH)

    labels = np.asarray(
        [
            int(row["label"])
            for row in rows
        ]
    )

    scores = np.asarray(
        [
            float(row["risk_score"])
            for row in rows
        ]
    )

    safe_scores = scores[labels == 0]
    risky_scores = scores[labels == 1]

    thresholds = [
        round(value, 2)
        for value in np.arange(
            0.05,
            0.96,
            0.05,
        )
    ]

    results = [
        evaluate_threshold(
            labels,
            scores,
            threshold,
        )
        for threshold in thresholds
    ]

    best_f1 = max(
        results,
        key=lambda row: (
            row["f1"],
            row["recall"],
            row["precision"],
            -row["threshold"],
        ),
    )

    highest_recall_no_fp = max(
        (
            row
            for row in results
            if row["fp"] == 0
        ),
        key=lambda row: (
            row["recall"],
            row["f1"],
            -row["threshold"],
        ),
    )

    report = {
        "rows": len(rows),
        "score_distribution": {
            "safe": describe(safe_scores),
            "risky": describe(risky_scores),
        },
        "threshold_results": results,
        "best_f1_threshold": best_f1,
        "highest_recall_with_zero_false_positives": (
            highest_recall_no_fp
        ),
    }

    OUTPUT_PATH.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print("=" * 80)
    print("MBERT V0.2.0 THRESHOLD ANALYSIS")
    print("=" * 80)
    print()

    print("Safe score distribution:")
    print(
        json.dumps(
            report["score_distribution"]["safe"],
            indent=2,
        )
    )

    print()
    print("Risky score distribution:")
    print(
        json.dumps(
            report["score_distribution"]["risky"],
            indent=2,
        )
    )

    print()
    print(
        "threshold  accuracy  precision  recall  "
        "f1      fp  fn"
    )

    for row in results:
        print(
            f"{row['threshold']:>8.2f}  "
            f"{row['accuracy']:>8.4f}  "
            f"{row['precision']:>9.4f}  "
            f"{row['recall']:>6.4f}  "
            f"{row['f1']:>6.4f}  "
            f"{row['fp']:>2}  "
            f"{row['fn']:>2}"
        )

    print()
    print(
        "Best F1 threshold:",
        best_f1,
    )

    print(
        "Highest recall with zero FP:",
        highest_recall_no_fp,
    )

    print()
    print("Report:", OUTPUT_PATH)


if __name__ == "__main__":
    main()

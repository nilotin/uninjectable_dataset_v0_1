from __future__ import annotations

import hashlib
import json
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
from torch.utils.data import DataLoader
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
)


RUN_DIR = Path(
    "artifacts/training_runs/"
    "mbert_agentdojo_turkish_baseline_v0.2.0"
)

PACKAGE_DIR = Path(
    "data/processed/"
    "agentdojo_turkish_training_package_v0.2.0"
)

VALIDATION_PATH = (
    PACKAGE_DIR
    / "agentdojo_turkish_training_v0.2.0_validation.jsonl"
)

REPORT_DIR = Path(
    "artifacts/training_reports/"
    "mbert_agentdojo_turkish_baseline_v0.2.0"
)

OUTPUT_PATH = (
    REPORT_DIR
    / "mbert_agentdojo_turkish_baseline_v0.2.0_"
      "evaluation.json"
)

PREDICTIONS_PATH = (
    REPORT_DIR
    / "mbert_agentdojo_turkish_baseline_v0.2.0_"
      "validation_predictions.jsonl"
)

MAX_LENGTH = 512
BATCH_SIZE = 8


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]


def write_jsonl(
    path: Path,
    rows: list[dict[str, Any]],
) -> None:
    path.write_text(
        "".join(
            json.dumps(
                row,
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


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

    if (
        hasattr(torch.backends, "mps")
        and torch.backends.mps.is_available()
    ):
        return torch.device("mps")

    return torch.device("cpu")


def main() -> None:
    rows = load_jsonl(VALIDATION_PATH)

    if len(rows) != 42:
        raise ValueError(
            f"Expected 42 validation rows, found {len(rows)}"
        )

    device = detect_device()

    tokenizer = AutoTokenizer.from_pretrained(
        RUN_DIR,
        use_fast=True,
    )

    model = (
        AutoModelForSequenceClassification
        .from_pretrained(RUN_DIR)
    )

    model.to(device)
    model.eval()

    encoded = tokenizer(
        [str(row["text"]) for row in rows],
        max_length=MAX_LENGTH,
        padding="max_length",
        truncation=True,
        return_tensors="pt",
    )

    dataset = torch.utils.data.TensorDataset(
        encoded["input_ids"],
        encoded["attention_mask"],
    )

    loader = DataLoader(
        dataset,
        batch_size=BATCH_SIZE,
        shuffle=False,
    )

    logits_batches = []

    with torch.no_grad():
        for input_ids, attention_mask in loader:
            outputs = model(
                input_ids=input_ids.to(device),
                attention_mask=attention_mask.to(device),
            )

            logits_batches.append(
                outputs.logits.detach().cpu()
            )

    logits = torch.cat(
        logits_batches,
        dim=0,
    ).numpy()

    shifted = (
        logits
        - logits.max(
            axis=1,
            keepdims=True,
        )
    )

    probabilities = np.exp(shifted)
    probabilities /= probabilities.sum(
        axis=1,
        keepdims=True,
    )

    risky_scores = probabilities[:, 1]
    predictions = np.argmax(
        probabilities,
        axis=1,
    )

    labels = np.asarray(
        [
            int(row["label"])
            for row in rows
        ]
    )

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

    metrics = {
        "accuracy": float(
            accuracy_score(
                labels,
                predictions,
            )
        ),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "roc_auc": float(
            roc_auc_score(
                labels,
                risky_scores,
            )
        ),
        "confusion_matrix": {
            "labels": [
                "contextually_safe",
                "contextually_risky",
            ],
            "matrix": matrix.tolist(),
            "tn": tn,
            "fp": fp,
            "fn": fn,
            "tp": tp,
        },
    }

    prediction_rows = []

    for row, prediction, score in zip(
        rows,
        predictions,
        risky_scores,
        strict=True,
    ):
        prediction_rows.append(
            {
                "row_id": row["row_id"],
                "pair_id": row["pair_id"],
                "suite": row["suite"],
                "variant": row["variant"],
                "label": int(row["label"]),
                "prediction": int(prediction),
                "risk_score": float(score),
                "correct": (
                    int(prediction)
                    == int(row["label"])
                ),
            }
        )

    false_negatives = [
        row
        for row in prediction_rows
        if (
            row["label"] == 1
            and row["prediction"] == 0
        )
    ]

    false_positives = [
        row
        for row in prediction_rows
        if (
            row["label"] == 0
            and row["prediction"] == 1
        )
    ]

    report = {
        "run_name": (
            "mbert_agentdojo_turkish_baseline_v0.2.0"
        ),
        "evaluated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "model_artifact": str(RUN_DIR),
        "validation_artifact": str(
            VALIDATION_PATH
        ),
        "validation_sha256": sha256_file(
            VALIDATION_PATH
        ),
        "device": str(device),
        "threshold": 0.5,
        "risk_score_definition": "P(label=1)",
        "rows": len(rows),
        "metrics": metrics,
        "error_counts": {
            "false_positives": len(
                false_positives
            ),
            "false_negatives": len(
                false_negatives
            ),
        },
        "false_positive_row_ids": [
            row["row_id"]
            for row in false_positives
        ],
        "false_negative_row_ids": [
            row["row_id"]
            for row in false_negatives
        ],
    }

    REPORT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    write_jsonl(
        PREDICTIONS_PATH,
        prediction_rows,
    )

    print("=" * 80)
    print(
        "MBERT AGENTDOJO TURKISH "
        "V0.2.0 EVALUATION"
    )
    print("=" * 80)
    print()
    print("Device:", device)
    print("Rows:", len(rows))
    print("Accuracy:", metrics["accuracy"])
    print("Precision:", metrics["precision"])
    print("Recall:", metrics["recall"])
    print("F1:", metrics["f1"])
    print("ROC-AUC:", metrics["roc_auc"])
    print(
        "Confusion matrix:",
        metrics["confusion_matrix"]["matrix"],
    )
    print("TN:", tn)
    print("FP:", fp)
    print("FN:", fn)
    print("TP:", tp)
    print(
        "False positive row IDs:",
        report["false_positive_row_ids"],
    )
    print(
        "False negative row IDs:",
        report["false_negative_row_ids"],
    )
    print()
    print("Report:", OUTPUT_PATH)
    print(
        "Predictions:",
        PREDICTIONS_PATH,
    )
    print()
    print("Evaluation: PASSED")


if __name__ == "__main__":
    main()

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
from torch.utils.data import DataLoader, TensorDataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
)


SEEDS = (42, 43, 44, 45, 46)

RUN_DIRS = {
    42: Path(
        "artifacts/training_runs/"
        "mbert_agentdojo_turkish_baseline_v0.2.0"
    ),
    43: Path(
        "artifacts/training_runs/"
        "mbert_agentdojo_turkish_baseline_v0.2.0_seed_43"
    ),
    44: Path(
        "artifacts/training_runs/"
        "mbert_agentdojo_turkish_baseline_v0.2.0_seed_44"
    ),
    45: Path(
        "artifacts/training_runs/"
        "mbert_agentdojo_turkish_baseline_v0.2.0_seed_45"
    ),
    46: Path(
        "artifacts/training_runs/"
        "mbert_agentdojo_turkish_baseline_v0.2.0_seed_46"
    ),
}

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
    "mbert_agentdojo_turkish_multiseed_ensemble_v0.2.0"
)

REPORT_PATH = (
    REPORT_DIR
    / "mbert_agentdojo_turkish_multiseed_ensemble_"
      "v0.2.0_report.json"
)

PREDICTIONS_PATH = (
    REPORT_DIR
    / "mbert_agentdojo_turkish_multiseed_ensemble_"
      "v0.2.0_validation_predictions.jsonl"
)

MAX_LENGTH = 512
BATCH_SIZE = 8
THRESHOLD = 0.5


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


def predict_scores(
    run_dir: Path,
    texts: list[str],
    device: torch.device,
) -> np.ndarray:
    tokenizer = AutoTokenizer.from_pretrained(
        run_dir,
        use_fast=True,
    )

    model = (
        AutoModelForSequenceClassification
        .from_pretrained(run_dir)
    )

    model.to(device)
    model.eval()

    encoded = tokenizer(
        texts,
        max_length=MAX_LENGTH,
        padding="max_length",
        truncation=True,
        return_tensors="pt",
    )

    dataset = TensorDataset(
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

    del model

    if device.type == "mps":
        torch.mps.empty_cache()

    return probabilities[:, 1]


def compute_metrics(
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
        "roc_auc": float(
            roc_auc_score(
                labels,
                scores,
            )
        ),
        "confusion_matrix": {
            "matrix": matrix.tolist(),
            "tn": tn,
            "fp": fp,
            "fn": fn,
            "tp": tp,
        },
    }


def main() -> None:
    for seed, run_dir in RUN_DIRS.items():
        if not run_dir.exists():
            raise FileNotFoundError(
                f"Seed {seed}: {run_dir}"
            )

    rows = load_jsonl(VALIDATION_PATH)

    if len(rows) != 42:
        raise ValueError(
            f"Expected 42 validation rows, "
            f"found {len(rows)}"
        )

    texts = [
        str(row["text"])
        for row in rows
    ]

    labels = np.asarray(
        [
            int(row["label"])
            for row in rows
        ]
    )

    device = detect_device()

    seed_scores: dict[int, np.ndarray] = {}

    for seed in SEEDS:
        print(
            f"Evaluating seed {seed}: "
            f"{RUN_DIRS[seed]}"
        )

        seed_scores[seed] = predict_scores(
            RUN_DIRS[seed],
            texts,
            device,
        )

    score_matrix = np.stack(
        [
            seed_scores[seed]
            for seed in SEEDS
        ],
        axis=1,
    )

    ensemble_scores = score_matrix.mean(
        axis=1
    )

    ensemble_predictions = (
        ensemble_scores >= THRESHOLD
    ).astype(int)

    metrics = compute_metrics(
        labels,
        ensemble_scores,
        THRESHOLD,
    )

    prediction_rows = []

    for index, row in enumerate(rows):
        per_seed = {
            str(seed): float(
                seed_scores[seed][index]
            )
            for seed in SEEDS
        }

        prediction_rows.append(
            {
                "row_id": row["row_id"],
                "pair_id": row["pair_id"],
                "suite": row["suite"],
                "variant": row["variant"],
                "label": int(row["label"]),
                "seed_risk_scores": per_seed,
                "ensemble_mean_risk_score": float(
                    ensemble_scores[index]
                ),
                "ensemble_prediction": int(
                    ensemble_predictions[index]
                ),
                "correct": (
                    int(
                        ensemble_predictions[index]
                    )
                    == int(row["label"])
                ),
            }
        )

    false_positives = [
        row
        for row in prediction_rows
        if (
            row["label"] == 0
            and row["ensemble_prediction"] == 1
        )
    ]

    false_negatives = [
        row
        for row in prediction_rows
        if (
            row["label"] == 1
            and row["ensemble_prediction"] == 0
        )
    ]

    disagreement_counts = []

    for index, row in enumerate(rows):
        binary_votes = [
            int(seed_scores[seed][index] >= 0.5)
            for seed in SEEDS
        ]

        disagreement_counts.append(
            {
                "row_id": row["row_id"],
                "risky_votes": int(
                    sum(binary_votes)
                ),
                "safe_votes": int(
                    len(binary_votes)
                    - sum(binary_votes)
                ),
                "score_std": float(
                    score_matrix[index].std(
                        ddof=0
                    )
                ),
            }
        )

    report = {
        "run_name": (
            "mbert_agentdojo_turkish_"
            "multiseed_ensemble_v0.2.0"
        ),
        "evaluated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "seeds": list(SEEDS),
        "ensemble_method": (
            "mean of P(label=1) across seeds"
        ),
        "threshold": THRESHOLD,
        "device": str(device),
        "validation_artifact": str(
            VALIDATION_PATH
        ),
        "validation_sha256": sha256_file(
            VALIDATION_PATH
        ),
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
        "highest_disagreement_rows": sorted(
            disagreement_counts,
            key=lambda row: (
                -row["score_std"],
                row["row_id"],
            ),
        )[:10],
    }

    REPORT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    REPORT_PATH.write_text(
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

    matrix = metrics["confusion_matrix"]

    print()
    print("=" * 80)
    print(
        "MBERT AGENTDOJO TURKISH "
        "MULTI-SEED ENSEMBLE v0.2.0"
    )
    print("=" * 80)
    print()
    print("Seeds:", list(SEEDS))
    print("Device:", device)
    print("Rows:", len(rows))
    print("Threshold:", THRESHOLD)
    print("Accuracy:", metrics["accuracy"])
    print("Precision:", metrics["precision"])
    print("Recall:", metrics["recall"])
    print("F1:", metrics["f1"])
    print("ROC-AUC:", metrics["roc_auc"])
    print(
        "Confusion matrix:",
        matrix["matrix"],
    )
    print("TN:", matrix["tn"])
    print("FP:", matrix["fp"])
    print("FN:", matrix["fn"])
    print("TP:", matrix["tp"])
    print(
        "False positive row IDs:",
        report["false_positive_row_ids"],
    )
    print(
        "False negative row IDs:",
        report["false_negative_row_ids"],
    )
    print()
    print("Report:", REPORT_PATH)
    print("Predictions:", PREDICTIONS_PATH)
    print()
    print("Ensemble evaluation: PASSED")


if __name__ == "__main__":
    main()

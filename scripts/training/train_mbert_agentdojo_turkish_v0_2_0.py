from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import accelerate
import datasets
import numpy as np
import sklearn
import torch
import transformers
from datasets import Dataset
from sklearn.metrics import (
    accuracy_score,
    precision_recall_fscore_support,
    roc_auc_score,
)
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
    set_seed,
)


CONFIG_PATH = Path(
    os.environ.get(
        "MBERT_CONFIG_PATH",
        (
            "configs/training/"
            "mbert_turkish_baseline_v0.2.0.json"
        ),
    )
)

PACKAGE_DIR = Path(
    "data/processed/"
    "agentdojo_turkish_training_package_v0.2.0"
)

TRAIN_PATH = (
    PACKAGE_DIR
    / "agentdojo_turkish_training_v0.2.0_train.jsonl"
)

VALIDATION_PATH = (
    PACKAGE_DIR
    / "agentdojo_turkish_training_v0.2.0_validation.jsonl"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help=(
            "Run one optimization step without producing "
            "the final baseline release."
        ),
    )

    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue

        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"{path}:{line_number}: invalid JSON."
            ) from exc

        rows.append(row)

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


def normalize_variant(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("name", "<missing>"))

    return str(value)


def prepare_dataset_rows(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []

    for row in rows:
        prepared.append(
            {
                "row_id": str(row["row_id"]),
                "pair_id": str(row["pair_id"]),
                "session_group_id": str(
                    row["session_group_id"]
                ),
                "suite": str(row["suite"]),
                "variant": normalize_variant(
                    row["variant"]
                ),
                "text": str(row["text"]),
                "labels": int(row["label"]),
            }
        )

    return prepared


def compute_metrics(
    eval_prediction: Any,
) -> dict[str, float]:
    logits, labels = eval_prediction

    logits = np.asarray(logits)
    labels = np.asarray(labels)

    predictions = np.argmax(logits, axis=-1)

    shifted = logits - logits.max(
        axis=-1,
        keepdims=True,
    )
    probabilities = np.exp(shifted)
    probabilities = probabilities / probabilities.sum(
        axis=-1,
        keepdims=True,
    )

    risky_scores = probabilities[:, 1]

    precision, recall, f1, _ = (
        precision_recall_fscore_support(
            labels,
            predictions,
            average="binary",
            zero_division=0,
        )
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
    }

    try:
        metrics["roc_auc"] = float(
            roc_auc_score(
                labels,
                risky_scores,
            )
        )
    except ValueError:
        metrics["roc_auc"] = float("nan")

    return metrics


def detect_device() -> str:
    if torch.cuda.is_available():
        return "cuda"

    if torch.backends.mps.is_available():
        return "mps"

    return "cpu"


def main() -> None:
    args = parse_args()

    for path in (
        CONFIG_PATH,
        TRAIN_PATH,
        VALIDATION_PATH,
    ):
        if not path.exists():
            raise FileNotFoundError(path)

    config = json.loads(
        CONFIG_PATH.read_text(encoding="utf-8")
    )

    training_config = config["training"]
    tokenization_config = config["tokenization"]

    seed = int(training_config["seed"])

    random.seed(seed)
    np.random.seed(seed)
    set_seed(seed)

    train_rows = load_jsonl(TRAIN_PATH)
    validation_rows = load_jsonl(
        VALIDATION_PATH
    )

    expected_train = int(
        config["data"]["train_rows"]
    )
    expected_validation = int(
        config["data"]["validation_rows"]
    )

    if len(train_rows) != expected_train:
        raise ValueError(
            f"Expected {expected_train} train rows, "
            f"found {len(train_rows)}."
        )

    if len(validation_rows) != expected_validation:
        raise ValueError(
            f"Expected {expected_validation} validation rows, "
            f"found {len(validation_rows)}."
        )

    model_name = str(config["model_name"])

    print("=" * 80)
    print(
        "MBERT AGENTDOJO TURKISH BASELINE "
        "v0.2.0"
    )
    print("=" * 80)
    print()
    print("Mode:", "smoke_test" if args.smoke_test else "training")
    print("Model:", model_name)
    print("Device:", detect_device())
    print("Train rows:", len(train_rows))
    print("Validation rows:", len(validation_rows))
    print()

    tokenizer = AutoTokenizer.from_pretrained(
        model_name,
        use_fast=True,
    )

    model = AutoModelForSequenceClassification.from_pretrained(
        model_name,
        num_labels=int(config["num_labels"]),
        id2label={
            0: "contextually_safe",
            1: "contextually_risky",
        },
        label2id={
            "contextually_safe": 0,
            "contextually_risky": 1,
        },
    )

    train_dataset = Dataset.from_list(
        prepare_dataset_rows(train_rows)
    )

    validation_dataset = Dataset.from_list(
        prepare_dataset_rows(validation_rows)
    )

    max_length = int(
        tokenization_config["max_length"]
    )

    def tokenize_batch(
        batch: dict[str, list[Any]],
    ) -> dict[str, Any]:
        return tokenizer(
            batch["text"],
            padding=str(
                tokenization_config["padding"]
            ),
            truncation=bool(
                tokenization_config["truncation"]
            ),
            max_length=max_length,
        )

    train_dataset = train_dataset.map(
        tokenize_batch,
        batched=True,
        desc="Tokenizing train split",
    )

    validation_dataset = validation_dataset.map(
        tokenize_batch,
        batched=True,
        desc="Tokenizing validation split",
    )

    removable_columns = [
        "text",
        "row_id",
        "pair_id",
        "session_group_id",
        "suite",
        "variant",
    ]

    train_dataset = train_dataset.remove_columns(
        removable_columns
    )

    validation_dataset = (
        validation_dataset.remove_columns(
            removable_columns
        )
    )

    base_run_dir = Path(
        config["output"]["run_dir"]
    )

    report_dir = Path(
        config["output"]["report_dir"]
    )

    if args.smoke_test:
        run_dir = Path(
            "artifacts/training_runs/"
            "mbert_agentdojo_turkish_smoke_test_v0.2.0"
        )
    else:
        run_dir = base_run_dir

    run_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    report_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    common_arguments: dict[str, Any] = {
        "output_dir": str(run_dir),
        "seed": seed,
        "data_seed": seed,
        "learning_rate": float(
            training_config["learning_rate"]
        ),
        "weight_decay": float(
            training_config["weight_decay"]
        ),
        "per_device_train_batch_size": int(
            training_config[
                "per_device_train_batch_size"
            ]
        ),
        "per_device_eval_batch_size": int(
            training_config[
                "per_device_eval_batch_size"
            ]
        ),
        "gradient_accumulation_steps": int(
            training_config[
                "gradient_accumulation_steps"
            ]
        ),
        "warmup_ratio": float(
            training_config["warmup_ratio"]
        ),
        "lr_scheduler_type": str(
            training_config[
                "lr_scheduler_type"
            ]
        ),
        "logging_strategy": str(
            training_config[
                "logging_strategy"
            ]
        ),
        "logging_steps": int(
            training_config["logging_steps"]
        ),
        "fp16": bool(
            training_config["fp16"]
        ),
        "bf16": bool(
            training_config["bf16"]
        ),
        "report_to": [],
        "remove_unused_columns": True,
        "dataloader_num_workers": 0,
    }

    if args.smoke_test:
        common_arguments.update(
            {
                "max_steps": 1,
                "num_train_epochs": 1,
                "eval_strategy": "no",
                "save_strategy": "no",
                "load_best_model_at_end": False,
                "logging_steps": 1,
            }
        )
    else:
        common_arguments.update(
            {
                "num_train_epochs": float(
                    training_config[
                        "num_train_epochs"
                    ]
                ),
                "eval_strategy": str(
                    training_config[
                        "eval_strategy"
                    ]
                ),
                "save_strategy": str(
                    training_config[
                        "save_strategy"
                    ]
                ),
                "save_total_limit": int(
                    training_config[
                        "save_total_limit"
                    ]
                ),
                "load_best_model_at_end": bool(
                    training_config[
                        "load_best_model_at_end"
                    ]
                ),
                "metric_for_best_model": str(
                    training_config[
                        "metric_for_best_model"
                    ]
                ),
                "greater_is_better": bool(
                    training_config[
                        "greater_is_better"
                    ]
                ),
            }
        )

    training_arguments = TrainingArguments(
        **common_arguments
    )

    trainer = Trainer(
        model=model,
        args=training_arguments,
        train_dataset=train_dataset,
        eval_dataset=validation_dataset,
        processing_class=tokenizer,
        compute_metrics=compute_metrics,
    )

    train_result = trainer.train()

    if args.smoke_test:
        smoke_report = {
            "run": (
                "mbert_agentdojo_turkish_"
                "smoke_test_v0.2.0"
            ),
            "completed_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "status": "passed",
            "device": detect_device(),
            "train_metrics": train_result.metrics,
            "environment": {
                "python": platform.python_version(),
                "torch": torch.__version__,
                "transformers": (
                    transformers.__version__
                ),
                "datasets": datasets.__version__,
                "accelerate": (
                    accelerate.__version__
                ),
                "sklearn": sklearn.__version__,
                "numpy": np.__version__,
            },
            "source_hashes": {
                "config": sha256_file(
                    CONFIG_PATH
                ),
                "train": sha256_file(
                    TRAIN_PATH
                ),
                "validation": sha256_file(
                    VALIDATION_PATH
                ),
            },
        }

        smoke_report_path = (
            report_dir
            / "mbert_agentdojo_turkish_"
            "smoke_test_v0.2.0_report.json"
        )

        smoke_report_path.write_text(
            json.dumps(
                smoke_report,
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        print()
        print("Smoke test: PASSED")
        print(
            "Report:",
            smoke_report_path,
        )
        return

    trainer.save_model(run_dir)
    tokenizer.save_pretrained(run_dir)

    train_metrics = {
        key: float(value)
        for key, value
        in train_result.metrics.items()
    }

    validation_metrics_raw = trainer.evaluate()

    validation_metrics = {
        key: float(value)
        for key, value
        in validation_metrics_raw.items()
    }

    trainer.save_metrics(
        "train",
        train_metrics,
    )

    trainer.save_metrics(
        "validation",
        validation_metrics,
    )

    trainer.save_state()

    report = {
        "run_name": config["run_name"],
        "completed_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "model_name": model_name,
        "device": detect_device(),
        "risk_score_definition": (
            config["evaluation"][
                "risk_score_definition"
            ]
        ),
        "train_metrics": train_metrics,
        "validation_metrics": validation_metrics,
        "environment": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "transformers": transformers.__version__,
            "datasets": datasets.__version__,
            "accelerate": accelerate.__version__,
            "sklearn": sklearn.__version__,
            "numpy": np.__version__,
        },
        "source_hashes": {
            "config": sha256_file(CONFIG_PATH),
            "train": sha256_file(TRAIN_PATH),
            "validation": sha256_file(
                VALIDATION_PATH
            ),
        },
    }

    report_path = (
        report_dir
        / "mbert_agentdojo_turkish_"
        "baseline_v0.2.0_report.json"
    )

    report_path.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print()
    print("Training: PASSED")
    print("Model artifact:", run_dir)
    print("Report:", report_path)


if __name__ == "__main__":
    main()

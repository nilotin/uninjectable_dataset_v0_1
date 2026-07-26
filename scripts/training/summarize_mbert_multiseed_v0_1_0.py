from __future__ import annotations

import csv
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BASELINE_REPORT = Path(
    "artifacts/training_reports/"
    "mbert_agentdojo_turkish_baseline_v0.1.0/"
    "mbert_agentdojo_turkish_baseline_v0.1.0_report.json"
)

MULTISEED_DIR = Path(
    "artifacts/training_reports/"
    "mbert_agentdojo_turkish_multiseed_v0.1.0"
)

OUTPUT_CSV = (
    MULTISEED_DIR
    / "mbert_agentdojo_turkish_multiseed_summary_v0.1.0.csv"
)

OUTPUT_JSON = (
    MULTISEED_DIR
    / "mbert_agentdojo_turkish_multiseed_summary_v0.1.0.json"
)

EXPECTED_SEEDS = [13, 21, 42, 77, 101]


def load_report(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)

    return json.loads(
        path.read_text(encoding="utf-8")
    )


def metric_summary(
    values: list[float],
) -> dict[str, float]:
    return {
        "minimum": float(min(values)),
        "maximum": float(max(values)),
        "mean": float(statistics.mean(values)),
        "median": float(statistics.median(values)),
        "sample_std": (
            float(statistics.stdev(values))
            if len(values) > 1
            else 0.0
        ),
    }


def main() -> None:
    runs: list[dict[str, Any]] = []

    baseline = load_report(BASELINE_REPORT)

    runs.append(
        {
            "seed": 42,
            "run_name": baseline["run_name"],
            "eval_loss": float(
                baseline["validation_metrics"]["eval_loss"]
            ),
            "accuracy": float(
                baseline["validation_metrics"]["eval_accuracy"]
            ),
            "precision": float(
                baseline["validation_metrics"]["eval_precision"]
            ),
            "recall": float(
                baseline["validation_metrics"]["eval_recall"]
            ),
            "f1": float(
                baseline["validation_metrics"]["eval_f1"]
            ),
            "roc_auc": float(
                baseline["validation_metrics"]["eval_roc_auc"]
            ),
            "train_loss": float(
                baseline["train_metrics"]["train_loss"]
            ),
        }
    )

    for seed in [13, 21, 77, 101]:
        report_path = (
            MULTISEED_DIR
            / f"seed_{seed}"
            / "mbert_agentdojo_turkish_"
            "baseline_v0.1.0_report.json"
        )

        report = load_report(report_path)

        runs.append(
            {
                "seed": seed,
                "run_name": report["run_name"],
                "eval_loss": float(
                    report["validation_metrics"]["eval_loss"]
                ),
                "accuracy": float(
                    report["validation_metrics"]["eval_accuracy"]
                ),
                "precision": float(
                    report["validation_metrics"]["eval_precision"]
                ),
                "recall": float(
                    report["validation_metrics"]["eval_recall"]
                ),
                "f1": float(
                    report["validation_metrics"]["eval_f1"]
                ),
                "roc_auc": float(
                    report["validation_metrics"]["eval_roc_auc"]
                ),
                "train_loss": float(
                    report["train_metrics"]["train_loss"]
                ),
            }
        )

    runs.sort(
        key=lambda row: int(row["seed"])
    )

    observed_seeds = [
        int(row["seed"])
        for row in runs
    ]

    if observed_seeds != EXPECTED_SEEDS:
        raise ValueError(
            f"Expected seeds {EXPECTED_SEEDS}, "
            f"found {observed_seeds}."
        )

    metric_names = [
        "eval_loss",
        "accuracy",
        "precision",
        "recall",
        "f1",
        "roc_auc",
        "train_loss",
    ]

    aggregate = {
        metric: metric_summary(
            [
                float(run[metric])
                for run in runs
            ]
        )
        for metric in metric_names
    }

    best_f1_run = max(
        runs,
        key=lambda row: (
            float(row["f1"]),
            float(row["roc_auc"]),
            -float(row["eval_loss"]),
        ),
    )

    best_auc_run = max(
        runs,
        key=lambda row: (
            float(row["roc_auc"]),
            float(row["f1"]),
        ),
    )

    OUTPUT_CSV.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_CSV.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(runs[0].keys()),
        )
        writer.writeheader()
        writer.writerows(runs)

    output = {
        "summary": (
            "mbert_agentdojo_turkish_"
            "multiseed_v0.1.0"
        ),
        "completed_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "seeds": EXPECTED_SEEDS,
        "runs": runs,
        "aggregate": aggregate,
        "best_runs": {
            "best_f1": best_f1_run,
            "best_roc_auc": best_auc_run,
        },
        "notes": [
            (
                "All metrics use the same frozen "
                "30-row validation split."
            ),
            (
                "The validation set is too small "
                "for production model selection."
            ),
            (
                "Seed sensitivity should be "
                "reported using mean and standard deviation."
            ),
        ],
    }

    OUTPUT_JSON.write_text(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print("=" * 80)
    print("MBERT TURKISH MULTISEED SUMMARY v0.1.0")
    print("=" * 80)
    print()

    for run in runs:
        print(
            f"Seed {run['seed']:>3} | "
            f"accuracy={run['accuracy']:.4f} | "
            f"precision={run['precision']:.4f} | "
            f"recall={run['recall']:.4f} | "
            f"f1={run['f1']:.4f} | "
            f"roc_auc={run['roc_auc']:.4f}"
        )

    print()
    print(
        "Mean F1:",
        round(aggregate["f1"]["mean"], 6),
    )
    print(
        "F1 sample std:",
        round(
            aggregate["f1"]["sample_std"],
            6,
        ),
    )
    print(
        "Mean ROC-AUC:",
        round(
            aggregate["roc_auc"]["mean"],
            6,
        ),
    )
    print(
        "ROC-AUC sample std:",
        round(
            aggregate["roc_auc"]["sample_std"],
            6,
        ),
    )
    print()
    print(
        "Best F1 seed:",
        best_f1_run["seed"],
        "| F1:",
        best_f1_run["f1"],
    )
    print(
        "Best ROC-AUC seed:",
        best_auc_run["seed"],
        "| ROC-AUC:",
        best_auc_run["roc_auc"],
    )
    print()
    print("CSV:", OUTPUT_CSV)
    print("JSON:", OUTPUT_JSON)
    print()
    print("Multiseed summary: PASSED")


if __name__ == "__main__":
    main()

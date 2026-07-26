from __future__ import annotations

import csv
import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PREDICTIONS_PATH = Path(
    "artifacts/training_reports/"
    "mbert_agentdojo_turkish_baseline_v0.1.0/"
    "mbert_agentdojo_turkish_baseline_v0.1.0_predictions.csv"
)

OUTPUT_CSV = Path(
    "artifacts/training_reports/"
    "mbert_agentdojo_turkish_baseline_v0.1.0/"
    "mbert_agentdojo_turkish_baseline_v0.1.0_pair_margins.csv"
)

OUTPUT_REPORT = Path(
    "artifacts/training_reports/"
    "mbert_agentdojo_turkish_baseline_v0.1.0/"
    "mbert_agentdojo_turkish_baseline_v0.1.0_pair_margin_report.json"
)

EXPECTED_ROWS = 30
EXPECTED_PAIRS = 15


def load_predictions(
    path: Path,
) -> list[dict[str, str]]:
    with path.open(
        encoding="utf-8",
        newline="",
    ) as handle:
        return list(csv.DictReader(handle))


def canonical_pair_id(pair_id: str) -> str:
    if pair_id.endswith("_tr"):
        return pair_id[:-3]

    return pair_id


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


def main() -> None:
    if not PREDICTIONS_PATH.exists():
        raise FileNotFoundError(PREDICTIONS_PATH)

    rows = load_predictions(PREDICTIONS_PATH)

    if len(rows) != EXPECTED_ROWS:
        raise ValueError(
            f"Expected {EXPECTED_ROWS} rows, "
            f"found {len(rows)}."
        )

    grouped: dict[
        str,
        list[dict[str, str]],
    ] = defaultdict(list)

    for row in rows:
        pair_id = canonical_pair_id(
            str(row["pair_id"])
        )
        grouped[pair_id].append(row)

    if len(grouped) != EXPECTED_PAIRS:
        raise ValueError(
            f"Expected {EXPECTED_PAIRS} pairs, "
            f"found {len(grouped)}."
        )

    pair_rows: list[dict[str, Any]] = []

    for pair_id, members in sorted(
        grouped.items()
    ):
        if len(members) != 2:
            raise ValueError(
                f"{pair_id}: expected 2 rows, "
                f"found {len(members)}."
            )

        by_label = {
            int(member["true_label"]): member
            for member in members
        }

        if set(by_label) != {0, 1}:
            raise ValueError(
                f"{pair_id}: expected labels 0 and 1."
            )

        safe = by_label[0]
        risky = by_label[1]

        if safe["suite"] != risky["suite"]:
            raise ValueError(
                f"{pair_id}: suite mismatch."
            )

        safe_score = float(
            safe["risk_score"]
        )
        risky_score = float(
            risky["risk_score"]
        )

        margin = risky_score - safe_score

        pair_rows.append(
            {
                "pair_id": pair_id,
                "suite": str(safe["suite"]),
                "safe_row_id": str(
                    safe["row_id"]
                ),
                "risky_row_id": str(
                    risky["row_id"]
                ),
                "safe_score": safe_score,
                "risky_score": risky_score,
                "pair_margin": margin,
                "ranking_correct": margin > 0,
                "ranking_tied": margin == 0,
                "safe_predicted_0_50": int(
                    safe[
                        "predicted_label_0_50"
                    ]
                ),
                "risky_predicted_0_50": int(
                    risky[
                        "predicted_label_0_50"
                    ]
                ),
                "both_correct_0_50": (
                    int(
                        safe[
                            "predicted_label_0_50"
                        ]
                    )
                    == 0
                    and int(
                        risky[
                            "predicted_label_0_50"
                        ]
                    )
                    == 1
                ),
            }
        )

    pair_rows.sort(
        key=lambda row: float(
            row["pair_margin"]
        )
    )

    margins = [
        float(row["pair_margin"])
        for row in pair_rows
    ]

    correct_rankings = [
        row
        for row in pair_rows
        if row["ranking_correct"]
    ]

    incorrect_rankings = [
        row
        for row in pair_rows
        if not row["ranking_correct"]
    ]

    both_correct = [
        row
        for row in pair_rows
        if row["both_correct_0_50"]
    ]

    suite_groups: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)

    for row in pair_rows:
        suite_groups[
            str(row["suite"])
        ].append(row)

    suite_summary: dict[str, Any] = {}

    for suite, suite_rows in sorted(
        suite_groups.items()
    ):
        suite_margins = [
            float(row["pair_margin"])
            for row in suite_rows
        ]

        suite_summary[suite] = {
            "pairs": len(suite_rows),
            "ranking_correct": sum(
                bool(row["ranking_correct"])
                for row in suite_rows
            ),
            "ranking_accuracy": (
                sum(
                    bool(
                        row["ranking_correct"]
                    )
                    for row in suite_rows
                )
                / len(suite_rows)
            ),
            "both_correct_0_50": sum(
                bool(row["both_correct_0_50"])
                for row in suite_rows
            ),
            "margin_summary": float_summary(
                suite_margins
            ),
        }

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
            fieldnames=list(
                pair_rows[0].keys()
            ),
        )

        writer.writeheader()
        writer.writerows(pair_rows)

    report = {
        "analysis": (
            "mbert_agentdojo_turkish_"
            "baseline_v0.1.0_pair_margins"
        ),
        "completed_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "source_predictions": str(
            PREDICTIONS_PATH
        ),
        "definition": {
            "pair_margin": (
                "risky_score - safe_score"
            ),
            "positive_margin": (
                "Risky variant receives a "
                "higher risk score than the "
                "safe variant."
            ),
        },
        "counts": {
            "rows": len(rows),
            "pairs": len(pair_rows),
            "ranking_correct": len(
                correct_rankings
            ),
            "ranking_incorrect_or_tied": len(
                incorrect_rankings
            ),
            "both_correct_at_threshold_0_50": (
                len(both_correct)
            ),
        },
        "metrics": {
            "pair_ranking_accuracy": (
                len(correct_rankings)
                / len(pair_rows)
            ),
            "both_correct_accuracy_0_50": (
                len(both_correct)
                / len(pair_rows)
            ),
            "margin_summary": float_summary(
                margins
            ),
        },
        "suite_summary": suite_summary,
        "incorrect_or_tied_rankings": (
            incorrect_rankings
        ),
        "lowest_margins": pair_rows[:5],
        "highest_margins": list(
            reversed(pair_rows[-5:])
        ),
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

    print("=" * 80)
    print(
        "MBERT AGENTDOJO TURKISH "
        "PAIR MARGIN ANALYSIS v0.1.0"
    )
    print("=" * 80)
    print()
    print("Pairs:", len(pair_rows))
    print(
        "Correct pair rankings:",
        len(correct_rankings),
    )
    print(
        "Pair ranking accuracy:",
        round(
            len(correct_rankings)
            / len(pair_rows),
            6,
        ),
    )
    print(
        "Both variants correct at 0.50:",
        len(both_correct),
    )
    print()
    print(
        "Mean margin:",
        round(
            statistics.mean(margins),
            8,
        ),
    )
    print(
        "Median margin:",
        round(
            statistics.median(margins),
            8,
        ),
    )
    print(
        "Minimum margin:",
        round(min(margins), 8),
    )
    print(
        "Maximum margin:",
        round(max(margins), 8),
    )
    print()

    print("Incorrect or tied pair rankings:")

    if not incorrect_rankings:
        print("  none")
    else:
        for row in incorrect_rankings:
            print(
                " ",
                row["pair_id"],
                "|",
                row["suite"],
                "| safe=",
                round(
                    float(row["safe_score"]),
                    6,
                ),
                "| risky=",
                round(
                    float(row["risky_score"]),
                    6,
                ),
                "| margin=",
                round(
                    float(row["pair_margin"]),
                    6,
                ),
            )

    print()
    print("Pair margins:", OUTPUT_CSV)
    print("Report:", OUTPUT_REPORT)
    print()
    print("Pair margin analysis: PASSED")


if __name__ == "__main__":
    main()

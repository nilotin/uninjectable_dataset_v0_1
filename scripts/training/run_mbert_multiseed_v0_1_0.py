from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CONFIG_DIR = Path(
    "configs/training/"
    "mbert_turkish_multiseed_v0.1.0"
)

TRAIN_SCRIPT = Path(
    "scripts/training/"
    "train_mbert_agentdojo_turkish_v0_1_0.py"
)

SUMMARY_DIR = Path(
    "artifacts/training_reports/"
    "mbert_agentdojo_turkish_"
    "multiseed_v0.1.0"
)

RUN_REPORT = (
    SUMMARY_DIR
    / "mbert_agentdojo_turkish_"
    "multiseed_training_run_v0.1.0.json"
)

EXPECTED_SEEDS = [13, 21, 77, 101]


def main() -> None:
    if not TRAIN_SCRIPT.exists():
        raise FileNotFoundError(
            TRAIN_SCRIPT
        )

    config_paths = sorted(
        CONFIG_DIR.glob("*.json")
    )

    if len(config_paths) != len(
        EXPECTED_SEEDS
    ):
        raise ValueError(
            "Expected "
            f"{len(EXPECTED_SEEDS)} configs, "
            f"found {len(config_paths)}."
        )

    SUMMARY_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    results: list[dict[str, Any]] = []

    print("=" * 80)
    print(
        "MBERT AGENTDOJO TURKISH "
        "MULTISEED TRAINING v0.1.0"
    )
    print("=" * 80)
    print()

    for index, config_path in enumerate(
        config_paths,
        start=1,
    ):
        config = json.loads(
            config_path.read_text(
                encoding="utf-8"
            )
        )

        seed = int(
            config["training"]["seed"]
        )

        run_dir = Path(
            config["output"]["run_dir"]
        )

        print(
            f"[{index}/{len(config_paths)}] "
            f"Starting seed {seed}"
        )
        print("Config:", config_path)
        print("Run dir:", run_dir)
        print()

        if (
            run_dir
            / "model.safetensors"
        ).exists():
            print(
                f"Seed {seed} already completed; "
                "skipping."
            )

            results.append(
                {
                    "seed": seed,
                    "config": str(
                        config_path
                    ),
                    "run_dir": str(run_dir),
                    "status": (
                        "already_completed"
                    ),
                    "return_code": 0,
                }
            )

            print()
            continue

        environment = os.environ.copy()

        environment[
            "MBERT_CONFIG_PATH"
        ] = str(config_path)

        environment[
            "PYTORCH_ENABLE_MPS_FALLBACK"
        ] = "1"

        completed = subprocess.run(
            [
                sys.executable,
                str(TRAIN_SCRIPT),
            ],
            env=environment,
            check=False,
        )

        status = (
            "passed"
            if completed.returncode == 0
            else "failed"
        )

        results.append(
            {
                "seed": seed,
                "config": str(
                    config_path
                ),
                "run_dir": str(run_dir),
                "status": status,
                "return_code": (
                    completed.returncode
                ),
            }
        )

        if completed.returncode != 0:
            RUN_REPORT.write_text(
                json.dumps(
                    {
                        "run": (
                            "mbert_agentdojo_"
                            "turkish_multiseed_"
                            "training_v0.1.0"
                        ),
                        "completed_at": (
                            datetime.now(
                                timezone.utc
                            ).isoformat()
                        ),
                        "status": "failed",
                        "results": results,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            raise RuntimeError(
                f"Seed {seed} training failed "
                f"with return code "
                f"{completed.returncode}."
            )

        print()
        print(
            f"Seed {seed}: PASSED"
        )
        print()

    report = {
        "run": (
            "mbert_agentdojo_turkish_"
            "multiseed_training_v0.1.0"
        ),
        "completed_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "status": "passed",
        "expected_seeds": EXPECTED_SEEDS,
        "results": results,
    }

    RUN_REPORT.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print("=" * 80)
    print("MULTISEED TRAINING COMPLETED")
    print("=" * 80)
    print()

    for result in results:
        print(
            "Seed",
            result["seed"],
            ":",
            result["status"],
        )

    print()
    print("Run report:", RUN_REPORT)
    print()
    print(
        "Multiseed training: PASSED"
    )


if __name__ == "__main__":
    main()

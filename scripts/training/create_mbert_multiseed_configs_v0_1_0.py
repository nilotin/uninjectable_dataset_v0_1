from __future__ import annotations

import json
from pathlib import Path
from typing import Any


BASE_CONFIG_PATH = Path(
    "configs/training/"
    "mbert_turkish_baseline_v0.1.0.json"
)

OUTPUT_DIR = Path(
    "configs/training/"
    "mbert_turkish_multiseed_v0.1.0"
)

SEEDS = [13, 21, 77, 101]


def main() -> None:
    if not BASE_CONFIG_PATH.exists():
        raise FileNotFoundError(
            BASE_CONFIG_PATH
        )

    base_config: dict[str, Any] = json.loads(
        BASE_CONFIG_PATH.read_text(
            encoding="utf-8"
        )
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    generated_paths: list[Path] = []

    for seed in SEEDS:
        config = json.loads(
            json.dumps(base_config)
        )

        run_name = (
            "mbert_agentdojo_turkish_"
            f"seed_{seed}_v0.1.0"
        )

        config["run_name"] = run_name
        config["training"]["seed"] = seed

        config["output"]["run_dir"] = (
            "artifacts/training_runs/"
            f"{run_name}"
        )

        config["output"]["report_dir"] = (
            "artifacts/training_reports/"
            "mbert_agentdojo_turkish_"
            "multiseed_v0.1.0/"
            f"seed_{seed}"
        )

        output_path = (
            OUTPUT_DIR
            / f"{run_name}.json"
        )

        output_path.write_text(
            json.dumps(
                config,
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        generated_paths.append(
            output_path
        )

    print("=" * 80)
    print(
        "MBERT MULTISEED CONFIG "
        "GENERATION v0.1.0"
    )
    print("=" * 80)
    print()

    for path in generated_paths:
        print(path)

    print()
    print(
        "Generated configs:",
        len(generated_paths),
    )
    print(
        "Seeds:",
        SEEDS,
    )
    print()
    print(
        "Multiseed config generation: "
        "PASSED"
    )


if __name__ == "__main__":
    main()

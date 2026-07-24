# Uninjectable Dataset v0.1

Goal: build a Phase-1 dataset for a BERT-based General Runtime Risk Scorer.

## Phase-1 task

Input:
- source
- agent
- context
- policy
- attempted action

Target:
- `general_risk_label`: 0 or 1

Inference output:
- `ml_risk_score`: continuous score in [0, 1]

The training label is binary for annotation consistency. The deployed model may use the sigmoid probability as a continuous score.

## Dataset unit

One row = one `action.attempt`.

## Folder layout

- `data/raw/`: untouched source datasets and source manifests
- `data/interim/`: normalized/composed examples before final split
- `data/processed/`: finalized train/validation/test JSONL files
- `schemas/`: canonical JSON schema
- `configs/`: scenario-family definitions
- `docs/`: annotation and provenance rules
- `scripts/`: validation and BERT serialization utilities

## Immediate workflow

1. Review `docs/annotation_guidelines_v0.1.md`.
2. Review `configs/scenario_families_v0.1.json`.
3. Inspect `data/interim/starter_examples_v0.1.jsonl`.
4. Run `python scripts/validate_dataset.py data/interim/starter_examples_v0.1.jsonl`.
5. Run `python scripts/serialize_for_bert.py data/interim/starter_examples_v0.1.jsonl data/processed/starter_bert_v0.1.jsonl`.

Do not put upstream datasets directly into training without normalization, provenance tracking, and relabeling for the Uninjectable task.

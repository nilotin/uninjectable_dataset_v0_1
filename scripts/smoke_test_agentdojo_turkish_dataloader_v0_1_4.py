from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import torch
from torch.utils.data import DataLoader, Dataset
from transformers import AutoTokenizer, DataCollatorWithPadding


MODEL_NAME = "google-bert/bert-base-multilingual-cased"
MAX_LENGTH = 512
BATCH_SIZE = 4

BASE_DIRECTORY = Path(
    "data/processed/"
    "agentdojo_turkish_pilot_v0.1.3"
)

TRAIN_PATH = (
    BASE_DIRECTORY
    / "agentdojo_turkish_bert_compact_view_v0.1.4_train.jsonl"
)

VALIDATION_PATH = (
    BASE_DIRECTORY
    / "agentdojo_turkish_bert_compact_view_v0.1.4_validation.jsonl"
)


def load_jsonl(
    path: Path,
) -> list[dict[str, Any]]:

    rows = []

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:

        for line_number, line in enumerate(
            file,
            start=1,
        ):
            line = line.strip()

            if not line:
                continue

            try:
                rows.append(json.loads(line))

            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid JSONL: {path}, "
                    f"line {line_number}"
                ) from error

    return rows


class RiskDataset(Dataset):

    def __init__(
        self,
        rows: list[dict[str, Any]],
        tokenizer,
    ) -> None:

        self.rows = rows
        self.tokenizer = tokenizer

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(
        self,
        index: int,
    ) -> dict[str, Any]:

        row = self.rows[index]

        encoding = self.tokenizer(
            row["text"],
            truncation=True,
            max_length=MAX_LENGTH,
            padding=False,
            return_attention_mask=True,
        )

        encoding["labels"] = int(
            row["general_risk_label"]
        )

        return encoding


def validate_rows(
    name: str,
    rows: list[dict[str, Any]],
    expected_count: int,
    expected_labels: dict[int, int],
) -> None:

    if len(rows) != expected_count:
        raise ValueError(
            f"{name}: expected {expected_count} "
            f"rows, found {len(rows)}."
        )

    labels = Counter(
        int(row["general_risk_label"])
        for row in rows
    )

    if dict(labels) != expected_labels:
        raise ValueError(
            f"{name}: unexpected label counts "
            f"{dict(labels)}"
        )

    if len({
        row["row_id"]
        for row in rows
    }) != len(rows):
        raise ValueError(
            f"{name}: duplicate row IDs."
        )

    print(
        f"{name} rows:",
        len(rows),
        "| labels:",
        dict(labels),
    )


def main() -> None:

    train_rows = load_jsonl(
        TRAIN_PATH
    )

    validation_rows = load_jsonl(
        VALIDATION_PATH
    )

    validate_rows(
        "Train",
        train_rows,
        expected_count=16,
        expected_labels={
            0: 8,
            1: 8,
        },
    )

    validate_rows(
        "Validation",
        validation_rows,
        expected_count=8,
        expected_labels={
            0: 4,
            1: 4,
        },
    )

    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_NAME
    )

    all_rows = (
        train_rows
        +
        validation_rows
    )

    lengths = [
        len(
            tokenizer(
                row["text"],
                add_special_tokens=True,
                truncation=False,
            )["input_ids"]
        )
        for row in all_rows
    ]

    if max(lengths) > MAX_LENGTH:
        raise ValueError(
            "Unexpected truncation requirement. "
            f"Maximum length: {max(lengths)}"
        )

    train_dataset = RiskDataset(
        train_rows,
        tokenizer,
    )

    validation_dataset = RiskDataset(
        validation_rows,
        tokenizer,
    )

    collator = DataCollatorWithPadding(
        tokenizer=tokenizer,
        padding=True,
        pad_to_multiple_of=8,
        return_tensors="pt",
    )

    train_loader = DataLoader(
        train_dataset,
        batch_size=BATCH_SIZE,
        shuffle=True,
        collate_fn=collator,
    )

    validation_loader = DataLoader(
        validation_dataset,
        batch_size=BATCH_SIZE,
        shuffle=False,
        collate_fn=collator,
    )

    train_batch = next(
        iter(train_loader)
    )

    validation_batch = next(
        iter(validation_loader)
    )

    print()
    print("Model:", MODEL_NAME)
    print("Maximum source length:", max(lengths))
    print("Minimum source length:", min(lengths))
    print("MPS available:", torch.backends.mps.is_available())

    print()
    print("Train batch:")
    print("  input_ids:", tuple(train_batch["input_ids"].shape))
    print("  attention_mask:", tuple(train_batch["attention_mask"].shape))
    print("  labels:", tuple(train_batch["labels"].shape))
    print("  label values:", train_batch["labels"].tolist())

    print()
    print("Validation batch:")
    print(
        "  input_ids:",
        tuple(validation_batch["input_ids"].shape),
    )
    print(
        "  attention_mask:",
        tuple(validation_batch["attention_mask"].shape),
    )
    print(
        "  labels:",
        tuple(validation_batch["labels"].shape),
    )

    print()
    print("Truncated rows: 0")
    print("DataLoader smoke test: PASSED")


if __name__ == "__main__":
    main()

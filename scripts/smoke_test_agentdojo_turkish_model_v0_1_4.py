from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Any

import torch
from torch import nn
from torch.optim import AdamW
from transformers import AutoModel, AutoTokenizer


MODEL_NAME = "google-bert/bert-base-multilingual-cased"
MAX_LENGTH = 512
LEARNING_RATE = 1e-3
SEED = 42

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

REPORT_PATH = (
    BASE_DIRECTORY
    / "agentdojo_turkish_model_smoke_test_v0.1.4.json"
)


def load_jsonl(
    path: Path,
) -> list[dict[str, Any]]:

    if not path.exists():
        raise FileNotFoundError(
            f"Missing file: {path}"
        )

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
                rows.append(
                    json.loads(line)
                )

            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid JSONL in {path}, "
                    f"line {line_number}."
                ) from error

    return rows


class RiskClassifier(nn.Module):

    def __init__(
        self,
        model_name: str,
    ) -> None:

        super().__init__()

        self.encoder = AutoModel.from_pretrained(
            model_name
        )

        hidden_size = int(
            self.encoder.config.hidden_size
        )

        self.dropout = nn.Dropout(
            p=0.1
        )

        self.classifier = nn.Linear(
            hidden_size,
            1,
        )

        # Bu aşama yalnızca model-head smoke testidir.
        # Encoder henüz fine-tune edilmiyor.
        for parameter in self.encoder.parameters():
            parameter.requires_grad = False

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor,
    ) -> torch.Tensor:

        # Encoder dondurulduğu için aktivasyon grafiği
        # tutmamıza gerek yok.
        with torch.no_grad():
            outputs = self.encoder(
                input_ids=input_ids,
                attention_mask=attention_mask,
            )

        cls_representation = (
            outputs.last_hidden_state[:, 0, :]
        )

        logits = self.classifier(
            self.dropout(
                cls_representation
            )
        )

        return logits.squeeze(-1)


def tensor_is_finite(
    tensor: torch.Tensor,
) -> bool:

    return bool(
        torch.isfinite(tensor).all().item()
    )


def main() -> None:

    random.seed(SEED)
    torch.manual_seed(SEED)

    train_rows = load_jsonl(
        TRAIN_PATH
    )

    validation_rows = load_jsonl(
        VALIDATION_PATH
    )

    if len(train_rows) != 16:
        raise ValueError(
            f"Expected 16 train rows, "
            f"found {len(train_rows)}."
        )

    if len(validation_rows) != 8:
        raise ValueError(
            f"Expected 8 validation rows, "
            f"found {len(validation_rows)}."
        )

    safe_row = next(
        row
        for row in train_rows
        if int(
            row["general_risk_label"]
        ) == 0
    )

    risky_row = next(
        row
        for row in train_rows
        if int(
            row["general_risk_label"]
        ) == 1
    )

    selected_rows = [
        safe_row,
        risky_row,
    ]

    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_NAME
    )

    original_lengths = [
        len(
            tokenizer(
                row["text"],
                add_special_tokens=True,
                truncation=False,
            )["input_ids"]
        )
        for row in selected_rows
    ]

    if max(original_lengths) > MAX_LENGTH:
        raise ValueError(
            "Selected smoke-test row exceeds "
            f"{MAX_LENGTH} tokens."
        )

    encoded = tokenizer(
        [
            row["text"]
            for row in selected_rows
        ],
        padding=True,
        truncation=True,
        max_length=MAX_LENGTH,
        return_tensors="pt",
    )

    labels = torch.tensor(
        [
            float(
                row[
                    "general_risk_label"
                ]
            )
            for row in selected_rows
        ],
        dtype=torch.float32,
    )

    if torch.backends.mps.is_available():
        device = torch.device(
            "mps"
        )
    else:
        device = torch.device(
            "cpu"
        )

    model = RiskClassifier(
        MODEL_NAME
    ).to(device)

    input_ids = encoded[
        "input_ids"
    ].to(device)

    attention_mask = encoded[
        "attention_mask"
    ].to(device)

    labels = labels.to(device)

    loss_function = (
        nn.BCEWithLogitsLoss()
    )

    optimizer = AdamW(
        model.classifier.parameters(),
        lr=LEARNING_RATE,
        weight_decay=0.01,
    )

    # Optimizer öncesi inference
    model.eval()

    with torch.no_grad():

        logits_before = model(
            input_ids=input_ids,
            attention_mask=attention_mask,
        )

        probabilities_before = (
            torch.sigmoid(
                logits_before
            )
        )

        evaluation_loss_before = (
            loss_function(
                logits_before,
                labels,
            )
        )

    classifier_weight_before = (
        model.classifier.weight
        .detach()
        .clone()
    )

    # Tek optimizer adımı
    model.train()

    # model.train() encoder'ı da train moduna alır.
    # Encoder dondurulduğu için tekrar eval moduna alıyoruz.
    model.encoder.eval()

    optimizer.zero_grad(
        set_to_none=True
    )

    training_logits = model(
        input_ids=input_ids,
        attention_mask=attention_mask,
    )

    training_loss = loss_function(
        training_logits,
        labels,
    )

    if not tensor_is_finite(
        training_loss
    ):
        raise ValueError(
            "Training loss is not finite."
        )

    training_loss.backward()

    classifier_gradient = (
        model.classifier.weight.grad
    )

    if classifier_gradient is None:
        raise ValueError(
            "Classifier gradient is missing."
        )

    if not tensor_is_finite(
        classifier_gradient
    ):
        raise ValueError(
            "Classifier gradient contains "
            "NaN or infinity."
        )

    gradient_norm = float(
        classifier_gradient
        .detach()
        .norm()
        .cpu()
        .item()
    )

    if gradient_norm <= 0:
        raise ValueError(
            "Classifier gradient norm is zero."
        )

    optimizer.step()

    classifier_weight_after = (
        model.classifier.weight
        .detach()
        .clone()
    )

    parameter_delta = float(
        (
            classifier_weight_after
            -
            classifier_weight_before
        )
        .abs()
        .max()
        .cpu()
        .item()
    )

    if parameter_delta <= 0:
        raise ValueError(
            "Optimizer did not update the "
            "classifier parameters."
        )

    # Optimizer sonrası inference
    model.eval()

    with torch.no_grad():

        logits_after = model(
            input_ids=input_ids,
            attention_mask=attention_mask,
        )

        probabilities_after = (
            torch.sigmoid(
                logits_after
            )
        )

        evaluation_loss_after = (
            loss_function(
                logits_after,
                labels,
            )
        )

    if not tensor_is_finite(
        logits_after
    ):
        raise ValueError(
            "Output logits contain NaN "
            "or infinity."
        )

    if not tensor_is_finite(
        probabilities_after
    ):
        raise ValueError(
            "Risk probabilities contain NaN "
            "or infinity."
        )

    probability_values = (
        probabilities_after
        .detach()
        .cpu()
        .tolist()
    )

    if not all(
        0.0 <= probability <= 1.0
        for probability in probability_values
    ):
        raise ValueError(
            "Risk probability is outside "
            "the [0, 1] interval."
        )

    report = {
        "artifact_version": "0.1.4",
        "test_type": (
            "single_optimizer_step_"
            "classifier_head_smoke_test"
        ),
        "model_name": MODEL_NAME,
        "device": str(device),
        "max_length": MAX_LENGTH,
        "encoder_frozen": True,
        "selected_rows": [
            {
                "row_id": row["row_id"],
                "pair_id": row["pair_id"],
                "variant": row["variant"],
                "label": int(
                    row[
                        "general_risk_label"
                    ]
                ),
                "original_token_length": (
                    original_length
                ),
            }
            for row, original_length in zip(
                selected_rows,
                original_lengths,
            )
        ],
        "batch_shape": {
            "input_ids": list(
                input_ids.shape
            ),
            "attention_mask": list(
                attention_mask.shape
            ),
            "labels": list(
                labels.shape
            ),
        },
        "loss": {
            "evaluation_before": float(
                evaluation_loss_before
                .detach()
                .cpu()
                .item()
            ),
            "training_step": float(
                training_loss
                .detach()
                .cpu()
                .item()
            ),
            "evaluation_after": float(
                evaluation_loss_after
                .detach()
                .cpu()
                .item()
            ),
        },
        "logits_before": (
            logits_before
            .detach()
            .cpu()
            .tolist()
        ),
        "probabilities_before": (
            probabilities_before
            .detach()
            .cpu()
            .tolist()
        ),
        "logits_after": (
            logits_after
            .detach()
            .cpu()
            .tolist()
        ),
        "probabilities_after": (
            probabilities_after
            .detach()
            .cpu()
            .tolist()
        ),
        "classifier_gradient_norm": (
            gradient_norm
        ),
        "classifier_parameter_max_delta": (
            parameter_delta
        ),
        "validation": {
            "finite_loss": True,
            "finite_logits": True,
            "finite_probabilities": True,
            "nonzero_gradient": True,
            "parameters_updated": True,
            "probabilities_in_zero_one": True,
            "truncated_rows": 0,
            "smoke_test_passed": True,
        },
        "important_note": (
            "This smoke test does not measure "
            "model quality. The encoder remained "
            "frozen and only one classifier-head "
            "optimizer step was performed."
        ),
    }

    REPORT_PATH.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("=" * 80)
    print(
        "AGENTDOJO TURKISH MODEL "
        "SMOKE TEST v0.1.4 PASSED"
    )
    print("=" * 80)
    print()

    print(
        "Model:",
        MODEL_NAME,
    )

    print(
        "Device:",
        device,
    )

    print(
        "Encoder frozen:",
        True,
    )

    print(
        "Batch shape:",
        tuple(
            input_ids.shape
        ),
    )

    print(
        "Original token lengths:",
        original_lengths,
    )

    print()

    print(
        "Labels:",
        labels.detach().cpu().tolist(),
    )

    print(
        "Scores before:",
        [
            round(value, 6)
            for value in (
                probabilities_before
                .detach()
                .cpu()
                .tolist()
            )
        ],
    )

    print(
        "Scores after:",
        [
            round(value, 6)
            for value in probability_values
        ],
    )

    print()

    print(
        "Training loss:",
        round(
            float(
                training_loss
                .detach()
                .cpu()
                .item()
            ),
            6,
        ),
    )

    print(
        "Classifier gradient norm:",
        round(
            gradient_norm,
            6,
        ),
    )

    print(
        "Classifier parameter max delta:",
        parameter_delta,
    )

    print()

    print(
        "Finite outputs: yes"
    )

    print(
        "Parameters updated: yes"
    )

    print(
        "Truncated rows: 0"
    )

    print(
        "Smoke test: PASSED"
    )

    print()

    print(
        "Report:",
        REPORT_PATH,
    )


if __name__ == "__main__":
    main()

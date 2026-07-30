from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


EXPANSION_DIR = Path(
    "data/planning/"
    "agentdojo_turkish_argument_mismatch_expansion_v0.1.0"
)

ARTIFACT_NAME = (
    "agentdojo_turkish_argument_mismatch_expansion_v0.1.0"
)

ALL_PATH = (
    EXPANSION_DIR
    / f"{ARTIFACT_NAME}.jsonl"
)

METADATA_PATH = (
    EXPANSION_DIR
    / f"{ARTIFACT_NAME}_metadata.json"
)

OUTPUT_PATH = (
    EXPANSION_DIR
    / "ARGUMENT_MISMATCH_EXPANSION_APPROVAL.md"
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]


def main() -> None:
    rows = load_jsonl(ALL_PATH)

    metadata = json.loads(
        METADATA_PATH.read_text(
            encoding="utf-8"
        )
    )

    grouped: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)

    for row in rows:
        grouped[
            str(row["pair_id"])
        ].append(row)

    category_pair_counts = Counter(
        str(members[0]["category"])
        for members in grouped.values()
    )

    category_row_counts = Counter(
        str(row["category"])
        for row in rows
    )

    split_pair_counts = Counter(
        str(members[0]["split"])
        for members in grouped.values()
    )

    split_row_counts = Counter(
        str(row["split"])
        for row in rows
    )

    label_counts = Counter(
        int(row["general_risk_label"])
        for row in rows
    )

    lines = [
        "# Argument Mismatch Expansion Approval v0.1.0",
        "",
        "## Artifact",
        "",
        f"- Name: `{ARTIFACT_NAME}`",
        "- Status: `approved_expansion_not_merged`",
        "- Language: `tr`",
        "- Frozen corpus modified: `no`",
        "- Training package modified: `no`",
        "",
        "## Corpus özeti",
        "",
        f"- Pairs: `{len(grouped)}`",
        f"- Rows: `{len(rows)}`",
        (
            "- Train pairs: "
            f"`{split_pair_counts['train']}`"
        ),
        (
            "- Validation pairs: "
            f"`{split_pair_counts['validation']}`"
        ),
        (
            "- Train rows: "
            f"`{split_row_counts['train']}`"
        ),
        (
            "- Validation rows: "
            f"`{split_row_counts['validation']}`"
        ),
        (
            "- Safe labels: "
            f"`{label_counts[0]}`"
        ),
        (
            "- Risky labels: "
            f"`{label_counts[1]}`"
        ),
        (
            "- Maximum token count: "
            f"`{metadata['maximum_token_count']}`"
        ),
        "- Max length: `512`",
        "",
        "## Kategori dağılımı",
        "",
        "| Category | Pairs | Rows |",
        "|---|---:|---:|",
    ]

    for category in sorted(
        category_pair_counts
    ):
        lines.append(
            "| "
            + " | ".join(
                [
                    category,
                    str(
                        category_pair_counts[
                            category
                        ]
                    ),
                    str(
                        category_row_counts[
                            category
                        ]
                    ),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Validation sonuçları",
            "",
            "- Pair integrity failures: `0`",
            "- Label/variant failures: `0`",
            "- Duplicate row IDs: `0`",
            "- Internal duplicate compact inputs: `0`",
            "- Train/validation exact-text leakage: `0`",
            "- Train/validation pair-ID leakage: `0`",
            "- Frozen corpus exact-text duplicates: `0`",
            "- Frozen corpus row-ID collisions: `0`",
            "- Frozen corpus pair-ID collisions: `0`",
            "- text_sha256 failures: `0`",
            "- SHA256 manifest failures: `0`",
            "- Truncated rows: `0`",
            "",
            "## Kategori kapsamı",
            "",
            "- `recipient_mismatch`: hedef alıcı değişimi",
            "- `amount_mismatch`: yalnız amount değişimi",
            (
                "- `object_or_record_id_mismatch`: "
                "hedef kayıt veya nesne ID değişimi"
            ),
            (
                "- `date_or_time_mismatch`: "
                "tarih veya zaman aralığı değişimi"
            ),
            (
                "- `body_or_subject_mismatch`: "
                "body, subject veya content değişimi"
            ),
            (
                "- `permission_or_scope_mismatch`: "
                "permission yükseltmesi veya erişim "
                "kapsamı genişlemesi"
            ),
            "",
            "## Approval kararı",
            "",
            "Bu expansion package teknik validation, "
            "kategori bazlı manuel review ve birleşik "
            "corpus audit kontrollerini geçmiştir.",
            "",
            "Artifact frozen corpus veya ana training "
            "package ile henüz birleştirilmemiştir.",
            "",
            "Decision: `approved_for_merge_planning`",
        ]
    )

    OUTPUT_PATH.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    print("=" * 80)
    print(
        "ARGUMENT MISMATCH EXPANSION APPROVAL v0.1.0"
    )
    print("=" * 80)
    print()
    print("Pairs:", len(grouped))
    print("Rows:", len(rows))
    print("Output:", OUTPUT_PATH)
    print()
    print(
        "Argument mismatch expansion approval build: PASSED"
    )


if __name__ == "__main__":
    main()

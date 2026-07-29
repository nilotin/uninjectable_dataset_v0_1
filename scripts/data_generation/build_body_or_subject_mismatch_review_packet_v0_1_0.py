from __future__ import annotations

import json
from pathlib import Path
from typing import Any


CANDIDATE_PATH = Path(
    "data/planning/"
    "agentdojo_turkish_argument_mismatch_batch_v0.1.0/"
    "body_or_subject_mismatch_candidates_v0.1.0.jsonl"
)

ROW_PATH = Path(
    "data/planning/"
    "agentdojo_turkish_argument_mismatch_batch_v0.1.0/"
    "body_or_subject_mismatch_rows_v0.1.0/"
    "body_or_subject_mismatch_rows_v0.1.0.jsonl"
)

OUTPUT_PATH = Path(
    "data/planning/"
    "agentdojo_turkish_argument_mismatch_batch_v0.1.0/"
    "BODY_OR_SUBJECT_MISMATCH_REVIEW.md"
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]


def format_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


def main() -> None:
    if not CANDIDATE_PATH.exists():
        raise FileNotFoundError(CANDIDATE_PATH)

    if not ROW_PATH.exists():
        raise FileNotFoundError(ROW_PATH)

    candidates = load_jsonl(CANDIDATE_PATH)
    rows = load_jsonl(ROW_PATH)

    row_lookup = {
        (
            str(row["pair_id"]),
            str(row["variant"]),
        ): row
        for row in rows
    }

    sections: list[str] = [
        "# Body or Subject Mismatch Manual Review v0.1.0",
        "",
        "## Review kapsamı",
        "",
        "- Pair sayısı: `4`",
        "- Row sayısı: `8`",
        "- Train pair: `3`",
        "- Validation pair: `1`",
        "- Kategori: `body_or_subject_mismatch`",
        "",
        "Her pair için safe ve risky varyant arasında yalnızca "
        "body, subject veya content alanlarının değişmesi "
        "beklenmektedir.",
        "",
    ]

    for candidate in candidates:
        pair_id = str(candidate["pair_id"])
        safe_row = row_lookup[(pair_id, "safe")]
        risky_row = row_lookup[(pair_id, "risky")]

        sections.extend(
            [
                "---",
                "",
                f"## {pair_id}",
                "",
                f"- Split: `{candidate['split']}`",
                f"- Suite: `{candidate['suite']}`",
                (
                    "- Source scenario: "
                    f"`{candidate['source_scenario_id']}`"
                ),
                (
                    "- Authorized tool: "
                    f"`{candidate['authorized_tool']}`"
                ),
                (
                    "- Changed paths: "
                    f"`{candidate['changed_argument_paths']}`"
                ),
                (
                    "- Safe token count: "
                    f"`{safe_row['tokenization']['token_count']}`"
                ),
                (
                    "- Risky token count: "
                    f"`{risky_row['tokenization']['token_count']}`"
                ),
                "",
                "### Authorized arguments",
                "",
                "```json",
                format_json(candidate["authorized_args"]),
                "```",
                "",
                "### Safe attempted arguments",
                "",
                "```json",
                format_json(
                    candidate["safe_attempted_args"]
                ),
                "```",
                "",
                "### Risky attempted arguments",
                "",
                "```json",
                format_json(
                    candidate["risky_attempted_args"]
                ),
                "```",
                "",
                "### Retrieved content",
                "",
                "```text",
                str(candidate["retrieved_content"]),
                "```",
                "",
                "### Safe serialized input",
                "",
                "```text",
                str(safe_row["text"]),
                "```",
                "",
                "### Risky serialized input",
                "",
                "```text",
                str(risky_row["text"]),
                "```",
                "",
                "### Review checklist",
                "",
                "- [ ] Tool safe/risky varyantlarda aynı.",
                "- [ ] Safe args authorization ile eşleşiyor.",
                "- [ ] Risky args authorization ile eşleşmiyor.",
                "- [ ] Yalnızca body/subject/content alanları değişiyor.",
                "- [ ] Recipient, channel veya file ID sabit.",
                "- [ ] Diğer action argümanları sabit.",
                "- [ ] Retrieved content risky içeriği destekliyor.",
                "- [ ] Safe varyant retrieved instruction'ı uygulamıyor.",
                "- [ ] Risky varyant retrieved instruction'ı uyguluyor.",
                "- [ ] İçerik değişikliği anlamlı ve yeterince belirgin.",
                "- [ ] Pair gerçekçi.",
                "- [ ] Label doğru.",
                "",
                "### Review kararı",
                "",
                "- [ ] `approved`",
                "- [ ] `needs_revision`",
                "- [ ] `rejected`",
                "",
                "Reviewer:",
                "",
                "Notes:",
                "",
            ]
        )

    OUTPUT_PATH.write_text(
        "\n".join(sections).rstrip()
        + "\n",
        encoding="utf-8",
    )

    print("=" * 80)
    print(
        "BODY OR SUBJECT MISMATCH REVIEW "
        "PACKET v0.1.0"
    )
    print("=" * 80)
    print()
    print("Pairs:", len(candidates))
    print("Rows:", len(rows))
    print("Output:", OUTPUT_PATH)
    print()
    print(
        "Body or subject review packet build: PASSED"
    )


if __name__ == "__main__":
    main()

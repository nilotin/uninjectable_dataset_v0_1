#!/usr/bin/env python3
import json
import sys
from pathlib import Path

REQUIRED_TOP = {"example_id", "scenario_family", "input", "target", "annotation", "metadata"}
REQUIRED_INPUT = {
    "source_type", "source_trust_level", "source_content_redacted",
    "agent_role", "action_type", "tool_name", "action_args_redacted"
}

def validate(path: Path) -> int:
    errors = []
    seen_ids = set()
    count = 0

    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            if not line.strip():
                continue
            count += 1
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"line {line_no}: invalid JSON: {exc}")
                continue

            missing_top = REQUIRED_TOP - set(row)
            if missing_top:
                errors.append(f"line {line_no}: missing top-level fields: {sorted(missing_top)}")
                continue

            example_id = row["example_id"]
            if example_id in seen_ids:
                errors.append(f"line {line_no}: duplicate example_id {example_id}")
            seen_ids.add(example_id)

            missing_input = REQUIRED_INPUT - set(row["input"])
            if missing_input:
                errors.append(f"line {line_no}: missing input fields: {sorted(missing_input)}")

            label = row["target"].get("general_risk_label")
            if label not in (0, 1):
                errors.append(f"line {line_no}: general_risk_label must be 0 or 1")

            status = row["annotation"].get("status")
            if status == "clear_safe" and label != 0:
                errors.append(f"line {line_no}: clear_safe must have label 0")
            if status == "clear_risky" and label != 1:
                errors.append(f"line {line_no}: clear_risky must have label 1")

    if errors:
        print(f"FAILED: {len(errors)} error(s) across {count} example(s)")
        for error in errors:
            print("-", error)
        return 1

    print(f"OK: {count} example(s) validated")
    return 0

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python validate_dataset.py <dataset.jsonl>")
        raise SystemExit(2)
    raise SystemExit(validate(Path(sys.argv[1])))

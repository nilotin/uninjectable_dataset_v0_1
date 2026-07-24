#!/usr/bin/env python3
import json
import sys
from pathlib import Path

def fmt_value(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)

def serialize(row):
    x = row["input"]
    parts = [
        "[EVENT=action.attempt]",
        f"[SOURCE_TYPE={x['source_type']}]",
        f"[SOURCE_TRUST={x['source_trust_level']}]",
        f"[AGENT_ROLE={x['agent_role']}]",
    ]

    if x.get("allowed_tools"):
        parts.append("[ALLOWED_TOOLS] " + ", ".join(x["allowed_tools"]))

    parts.append("[SOURCE] " + x["source_content_redacted"])

    if x.get("short_context_redacted"):
        parts.append("[CONTEXT] " + x["short_context_redacted"])

    if x.get("retrieved_policy_redacted"):
        parts.append("[POLICY] " + x["retrieved_policy_redacted"])

    if x.get("retrieved_doc_trust_level"):
        parts.append(f"[RETRIEVED_DOC_TRUST={x['retrieved_doc_trust_level']}]")

    parts.extend([
        f"[ACTION_TYPE={x['action_type']}]",
        f"[TOOL_NAME={x['tool_name']}]",
        "[ACTION_ARGS] " + fmt_value(x["action_args_redacted"])
    ])

    if x.get("authorization_context"):
        parts.append("[AUTH_CONTEXT] " + fmt_value(x["authorization_context"]))

    return "\n".join(parts)

def main(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with src.open("r", encoding="utf-8") as fin, dst.open("w", encoding="utf-8") as fout:
        for line in fin:
            if not line.strip():
                continue
            row = json.loads(line)
            if row["annotation"]["status"] == "ambiguous":
                continue
            out = {
                "example_id": row["example_id"],
                "input_text": serialize(row),
                "general_risk_label": row["target"]["general_risk_label"],
                "session_group_id": row["metadata"]["session_group_id"],
                "split": row["metadata"]["split"]
            }
            fout.write(json.dumps(out, ensure_ascii=False) + "\n")
            count += 1
    print(f"Wrote {count} serialized example(s) to {dst}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python serialize_for_bert.py <source.jsonl> <destination.jsonl>")
        raise SystemExit(2)
    main(Path(sys.argv[1]), Path(sys.argv[2]))

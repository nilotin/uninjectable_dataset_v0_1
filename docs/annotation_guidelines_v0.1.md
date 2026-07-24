# Annotation Guidelines v0.1

## What are we labeling?

One example represents one attempted action (`action.attempt`).

The label answers:

> Does the full source + agent + context + policy + attempted-action combination contain a meaningful runtime security or policy risk that warrants review or blocking?

## Labels

### `general_risk_label = 0`
Use only when the example is clearly acceptable under the supplied context and policy.

Typical reasons:
- action is within the agent's role;
- required authorization is present;
- scope is appropriate;
- no meaningful malicious instruction or policy conflict is present.

Annotation status: `clear_safe`.

### `general_risk_label = 1`
Use when the example contains a clear security or policy concern warranting review or blocking.

Typical reasons:
- explicit or indirect prompt injection;
- policy conflict;
- missing required authorization;
- role/tool mismatch;
- excessive scope;
- sensitive-data disclosure or exfiltration risk;
- destructive or privileged action without sufficient justification.

Annotation status: `clear_risky`.

### Ambiguous examples
If the available context is insufficient to decide reliably:
- set `annotation.status = "ambiguous"`;
- do not use the example for Phase-1 training until adjudicated.

The canonical schema currently still requires a binary target, so ambiguous examples should live in a separate review queue before final dataset export.

## Critical rules

1. Do not copy an upstream dataset's original label into `general_risk_label` without relabeling for the Uninjectable task.
2. Do not expose deterministic policy outputs such as final decision, matched rules, or existing risk score to BERT input.
3. Preserve provenance for every externally sourced seed.
4. Prefer minimal pairs: change one causal variable while keeping the rest of the example stable.
5. Avoid shortcuts:
   - `untrusted` must not always mean risky;
   - `refund.create` must not always mean risky;
   - large amounts must not always mean risky;
   - `email.send` must not always mean risky.
6. Redact real PII and secrets before examples reach the training dataset.
7. Split by `session_group_id` or source scenario group, not by individual near-duplicate row.

## Phase-1 label scope

The Phase-1 model is not trained to predict prompt-injection, policy-bypass, tool-abuse, or exfiltration labels separately.
Those may be stored as optional future labels only when genuinely known, and must not be used as BERT input.

## Seed-review taxonomy clarification

Seed-review categories describe the linguistic role of a source fragment.
They are not Phase-1 runtime-risk labels.

### `usable_attack_seed`

A source fragment that contains a sufficiently clear attempt to:

- override prior instructions or context;
- replace an existing task with a conflicting task;
- force behavior that bypasses supplied context or policy;
- extract prompt, system, or preceding instruction content.

A `usable_attack_seed` does not automatically become
`general_risk_label = 1`.

The final runtime label is assigned only after the seed is composed with:

- source trust;
- agent role;
- context;
- policy;
- attempted action;
- authorization state.

### `benign_instruction_seed`

This name means:

> No clear instruction-hierarchy override is present.

It does NOT mean:

> The instruction is guaranteed to be safe in every runtime context.

For example, a role-play instruction, SQL-generation request, code-generation
request, or politically sensitive instruction may be a non-override instruction
while still becoming risky when composed with a particular agent, policy,
tool, or action.

### `ambiguous_instruction`

Use when the fragment cannot be reliably classified as an operational
instruction override or a normal instruction without additional context.

### `irrelevant`

Use for malformed, unusable, or low-value fragments that should not enter
scenario composition.

## Critical distinction

Seed review:

    linguistic fragment classification

Final Phase-1 annotation:

    source + agent + context + policy + action
    -> general_risk_label

These two annotation stages must remain separate.

# AgentDojo Turkish Corpus v0.4.0 Freeze Approval

## Artifact

- Name: `agentdojo_turkish_corpus_v0.4.0`
- Version: `v0.4.0`
- Status: `frozen`
- Immutable: `yes`

## Final counts

- Pairs: `106`
- Rows: `212`
- Train pairs: `85`
- Train rows: `170`
- Validation pairs: `21`
- Validation rows: `42`
- Safe labels: `106`
- Risky labels: `106`
- Maximum token count: `506`
- Max length: `512`
- Truncated rows: `0`

## Validation results

- Duplicate row IDs: `0`
- Duplicate exact compact inputs: `0`
- Train/validation pair leakage: `0`
- Train/validation exact-text leakage: `0`
- Pair integrity failures: `0`
- Label/variant failures: `0`
- Base row preservation failures: `0`
- Expansion row preservation failures: `0`
- Synthetic legacy fields: `0`
- Synthetic expansion fields: `0`
- text_sha256 failures: `0`
- Base immutable checksum failures: `0`
- Artifact SHA manifest failures: `0`

## Source composition

- Base corpus: `agentdojo_turkish_corpus_v0.3.0`
- Expansion: `agentdojo_turkish_argument_mismatch_expansion_v0.1.0`

The base corpus was preserved without modification.

The approved argument mismatch expansion was merged without modifying source rows or split assignments.

Decision: `approved_and_frozen`

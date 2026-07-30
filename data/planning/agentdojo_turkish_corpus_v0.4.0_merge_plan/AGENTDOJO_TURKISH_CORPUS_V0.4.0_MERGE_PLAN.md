# AgentDojo Turkish Corpus v0.4.0 Merge Plan

## Status

- Decision: `approved_for_merge_execution`
- Target: `agentdojo_turkish_corpus_v0.4.0`
- Base: `agentdojo_turkish_corpus_v0.3.0`
- Expansion: `agentdojo_turkish_argument_mismatch_expansion_v0.1.0`
- Base corpus immutable: `yes`
- Existing split assignments preserved: `yes`

## Planned counts

| Artifact | Pairs | Rows | Train pairs | Train rows | Validation pairs | Validation rows |
|---|---:|---:|---:|---:|---:|---:|
| v0.3.0 | 82 | 164 | 67 | 134 | 15 | 30 |
| expansion | 24 | 48 | 18 | 36 | 6 | 12 |
| v0.4.0 target | 106 | 212 | 85 | 170 | 21 | 42 |

Target label balance: `106 safe / 106 risky`.

## Schema policy

The target uses a union schema.

Required common fields remain mandatory for every row:

- `row_id`
- `pair_id`
- `split`
- `suite`
- `language`
- `source_language`
- `session_group_id`
- `variant`
- `text`
- `text_sha256`
- `general_risk_label`
- `label_source`
- `schema_version`
- `tokenization`
- `merge_provenance`
- `crosslingual_group_id`

Legacy-only optional fields are preserved only where they already exist:

- `compact_serialization`
- `provenance`
- `source_row_id`
- `source_pair_id`

Expansion-only optional fields are preserved only for expansion rows:

- `category`
- `changed_argument_paths`

## crosslingual_group_id policy

- Frozen rows retain existing string values.
- Expansion rows retain `null`.
- Target type is `string | null`.
- Synthetic crosslingual IDs are forbidden.

## Provenance policy

- Existing provenance objects are never overwritten.
- Frozen legacy provenance remains unchanged.
- Expansion provenance remains unchanged.
- Missing legacy fields are not synthesized.
- Missing expansion metadata is not synthesized for frozen rows.

## Split policy

- Existing train/validation assignments are preserved.
- No re-splitting is allowed.
- Both rows of every pair remain in the same split.
- Train/validation pair leakage is forbidden.

## Content policy

- Serialized `text` is immutable.
- `text_sha256` must remain valid.
- Labels are immutable.
- Tokenization metadata is preserved.
- Maximum length remains `512`.
- Truncated rows are forbidden.

## Execution order

1. verify v0.3.0 immutable checksum snapshot
2. load frozen train and validation rows
3. load approved expansion train and validation rows
4. preserve all existing split assignments
5. merge train with train and validation with validation
6. sort rows deterministically by pair_id and variant
7. write new v0.4.0 directory only
8. validate counts, hashes, leakage and schema policy
9. write metadata and SHA256 manifest
10. freeze v0.4.0 only after validation passes

## Merge boundary

This plan does not itself create or freeze v0.4.0.
It authorizes a separate deterministic merge build and validation step.

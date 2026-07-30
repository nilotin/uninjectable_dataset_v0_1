# Argument Mismatch Expansion Approval v0.1.0

## Artifact

- Name: `agentdojo_turkish_argument_mismatch_expansion_v0.1.0`
- Status: `approved_expansion_not_merged`
- Language: `tr`
- Frozen corpus modified: `no`
- Training package modified: `no`

## Corpus özeti

- Pairs: `24`
- Rows: `48`
- Train pairs: `18`
- Validation pairs: `6`
- Train rows: `36`
- Validation rows: `12`
- Safe labels: `24`
- Risky labels: `24`
- Maximum token count: `463`
- Max length: `512`

## Kategori dağılımı

| Category | Pairs | Rows |
|---|---:|---:|
| amount_mismatch | 4 | 8 |
| body_or_subject_mismatch | 4 | 8 |
| date_or_time_mismatch | 4 | 8 |
| object_or_record_id_mismatch | 4 | 8 |
| permission_or_scope_mismatch | 4 | 8 |
| recipient_mismatch | 4 | 8 |

## Validation sonuçları

- Pair integrity failures: `0`
- Label/variant failures: `0`
- Duplicate row IDs: `0`
- Internal duplicate compact inputs: `0`
- Train/validation exact-text leakage: `0`
- Train/validation pair-ID leakage: `0`
- Frozen corpus exact-text duplicates: `0`
- Frozen corpus row-ID collisions: `0`
- Frozen corpus pair-ID collisions: `0`
- text_sha256 failures: `0`
- SHA256 manifest failures: `0`
- Truncated rows: `0`

## Kategori kapsamı

- `recipient_mismatch`: hedef alıcı değişimi
- `amount_mismatch`: yalnız amount değişimi
- `object_or_record_id_mismatch`: hedef kayıt veya nesne ID değişimi
- `date_or_time_mismatch`: tarih veya zaman aralığı değişimi
- `body_or_subject_mismatch`: body, subject veya content değişimi
- `permission_or_scope_mismatch`: permission yükseltmesi veya erişim kapsamı genişlemesi

## Approval kararı

Bu expansion package teknik validation, kategori bazlı manuel review ve birleşik corpus audit kontrollerini geçmiştir.

Artifact frozen corpus veya ana training package ile henüz birleştirilmemiştir.

Decision: `approved_for_merge_planning`

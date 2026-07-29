# AgentDojo Turkish Argument Mismatch Batch v0.1.0

## Amaç

Bu batch, mevcut Türkçe AgentDojo corpusundaki tool mismatch ağırlığını azaltmak için hazırlanmıştır.

Mevcut frozen corpus dağılımı:

| Kategori | Pair | Oran |
|---|---:|---:|
| Tool mismatch | 69 | 84.15% |
| Argument mismatch | 12 | 14.63% |
| Placeholder-only mismatch | 1 | 1.22% |

Yeni batch yalnızca aynı tool içinde gerçekleşen argument-level authorization ihlallerine odaklanacaktır.

## Batch kapsamı

| Kategori | Train pair | Validation pair | Toplam |
|---|---:|---:|---:|
| Recipient mismatch | 3 | 1 | 4 |
| Amount mismatch | 3 | 1 | 4 |
| Object/record ID mismatch | 3 | 1 | 4 |
| Resource/file ID mismatch | 3 | 1 | 4 |
| Date/time mismatch | 3 | 1 | 4 |
| Body/subject mismatch | 3 | 1 | 4 |
| **Toplam** | **18** | **6** | **24** |

Her pair bir safe ve bir risky row içerir.

- Train rows: `36`
- Validation rows: `12`
- Total rows: `48`

## Temel pair yapısı

### Safe

- `authorized_tool == attempted_tool`
- `authorized_args == attempted_args`
- Label: `0`

### Risky

- `authorized_tool == attempted_tool`
- `authorized_args != attempted_args`
- Label: `1`

Safe ve risky varyant arasında tool, retrieved content, source metadata ve agent facts değişmemelidir.

## ID formatı

Pair:

`agentdojo_argm_pair_001`

Safe row:

`agentdojo_argm_pair_001::safe::action_attempt::tr`

Risky row:

`agentdojo_argm_pair_001::risky::action_attempt::tr`

Session group:

`agentdojo_argm_pair_001::session`

## Split politikası

Her kategoride:

- Pair 1: train
- Pair 2: train
- Pair 3: train
- Pair 4: validation

Bu yapı kategori bazında dengeli validation coverage sağlar.

## Kategori örnekleri

### Recipient mismatch

Authorized:

`recipients=[AUTHORIZED_RECIPIENT]`

Risky:

`recipients=[UNAUTHORIZED_RECIPIENT]`

### Amount mismatch

Authorized:

`amount=500`

Risky:

`amount=5000`

### Object/record ID mismatch

Authorized:

`file_id=AUTHORIZED_CUSTOMER`

Risky:

`file_id=DIFFERENT_CUSTOMER`

### Resource/file ID mismatch

Authorized:

`file_id=AUTHORIZED_FILE`

Risky:

`file_id=UNAUTHORIZED_FILE`

### Date/time mismatch

Authorized:

`start_time=AUTHORIZED_TIME`

Risky:

`start_time=RETRIEVED_TIME`

### Body/subject mismatch

Authorized:

`subject=AUTHORIZED_SUBJECT`

Risky:

`subject=RETRIEVED_SUBJECT`

## Kabul kriterleri

Batch yalnızca şu koşullarda training package içine alınabilir:

- `24/24` pair review edilmiş olmalı.
- `48/48` row schema validation geçmeli.
- Pair integrity hatası bulunmamalı.
- Duplicate compact input bulunmamalı.
- Train/validation leakage bulunmamalı.
- Truncation bulunmamalı.
- Her kategoride tam olarak `3 train + 1 validation` pair bulunmalı.
- Safe ve risky tool adları bütün pairlerde aynı olmalı.
- Safe args authorization ile eşleşmeli.
- Risky args authorization ile eşleşmemeli.

# Argument Mismatch Batch Review Checklist v0.1.0

## Pair kimliği

- [ ] `pair_id` manifest ile eşleşiyor.
- [ ] Safe ve risky row ID'leri doğru formatta.
- [ ] İki varyant aynı `session_group_id` değerini kullanıyor.
- [ ] Pair doğru split içinde.
- [ ] Source scenario başka splitte tekrar kullanılmıyor.

## Tool invariants

- [ ] `authorized_tool` tanımlı.
- [ ] Safe attempted tool, authorized tool ile aynı.
- [ ] Risky attempted tool, authorized tool ile aynı.
- [ ] Safe ve risky attempted tool birbirleriyle aynı.
- [ ] Pair yanlışlıkla tool mismatch örneğine dönüşmemiş.

## Safe varyant

- [ ] Safe attempted args, authorized args ile semantik olarak eşleşiyor.
- [ ] Safe action kullanıcı talebini doğru uyguluyor.
- [ ] Safe varyant retrieved content içindeki yetkisiz talimatı uygulamıyor.
- [ ] Safe varyantın etiketi `0`.

## Risky varyant

- [ ] Risky attempted args, authorized args ile semantik olarak eşleşmiyor.
- [ ] Yalnızca hedeflenen kritik argüman veya argümanlar değişiyor.
- [ ] Risky argümanlar retrieved untrusted content ile ilişkilendirilebilir.
- [ ] Risky varyantın etiketi `1`.
- [ ] Risky varyant yalnızca yazım veya formatting farkından oluşmuyor.

## Contrastive kalite

- [ ] Safe ve risky metinler aynı retrieved content kullanıyor.
- [ ] Safe ve risky metinler aynı source metadata kullanıyor.
- [ ] Safe ve risky metinler aynı agent facts kullanıyor.
- [ ] Capability class iki varyantta aynı.
- [ ] Action impact iki varyantta aynı.
- [ ] Tool adı, source ve role gibi istem dışı sinyaller değişmiyor.
- [ ] Etiketi yalnızca argument authorization farkı belirliyor.
- [ ] Pair gerçekçi ve açıklanabilir.

## Serialization

- [ ] Bölüm sırası doğru:
  `USER_AUTHORIZATION → ATTEMPTED_ACTION → RETRIEVED_CONTENT → SOURCE → AGENT_FACTS`
- [ ] Label veya review bilgisi BERT input içine girmiyor.
- [ ] Metadata alanları input text içine sızmıyor.
- [ ] Türkçe metin doğal ve anlaşılır.
- [ ] Placeholder kullanımı iki varyantta tutarlı.
- [ ] `text_sha256` üretildi.

## Tokenization

- [ ] Frozen tokenizer kullanıldı:
  `google-bert/bert-base-multilingual-cased`
- [ ] Token sayısı `512` veya altında.
- [ ] Truncation oluşmadı.
- [ ] Kritik authorization ve action alanları tokenized input içinde kaldı.

## Split güvenliği

- [ ] Aynı pair iki splitte bulunmuyor.
- [ ] Aynı session group iki splitte bulunmuyor.
- [ ] Aynı source scenario iki splitte bulunmuyor.
- [ ] Near-duplicate pair başka splitte bulunmuyor.
- [ ] Validation pair, train pairin yalnızca isim değiştirilmiş kopyası değil.

## Review kararı

- [ ] `approved`
- [ ] `needs_revision`
- [ ] `rejected`

Reviewer:

Review date:

Notes:

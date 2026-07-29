# Body or Subject Mismatch Approval v0.1.0

| Pair | Split | Suite | Tool | Changed paths | Decision |
|---|---|---|---|---|---|
| agentdojo_argm_pair_017 | train | slack | send_direct_message | body | approved |
| agentdojo_argm_pair_018 | train | slack | send_channel_message | body | approved |
| agentdojo_argm_pair_019 | train | workspace | send_email | subject, body | approved |
| agentdojo_argm_pair_020 | validation | workspace | append_to_file | content | approved |

## Sonuç

- Approved pairs: `4/4`
- Approved rows: `8/8`
- Train pairs: `3`
- Validation pairs: `1`
- Tool invariant failures: `0`
- Body/subject isolation failures: `0`
- Non-content context differences: `0`
- Context drift: `0`
- Truncation: `0`
- Duplicate compact inputs: `0`

Pairlerde yalnızca `body`, `subject` veya `content` alanları değişmektedir.

Recipient, channel, recipients ve file ID gibi hedef alanları pair içinde sabit tutulmuştur.

Bu artifact henüz frozen corpus veya ana training package ile birleştirilmemiştir.

# Permission or Scope Mismatch Approval v0.1.0

| Pair | Split | Suite | Tool | Changed path | Decision |
|---|---|---|---|---|---|
| agentdojo_argm_pair_021 | train | workspace | share_file | permission | approved |
| agentdojo_argm_pair_022 | train | workspace | send_email | recipients | approved |
| agentdojo_argm_pair_023 | train | workspace | create_calendar_event | participants | approved |
| agentdojo_argm_pair_024 | validation | workspace | add_calendar_event_participants | participants | approved |

## Sonuç

- Approved pairs: `4/4`
- Approved rows: `8/8`
- Train pairs: `3`
- Validation pairs: `1`
- Tool invariant failures: `0`
- Permission/scope isolation failures: `0`
- Scope contraction cases: `0`
- Non-scope context differences: `0`
- Context drift: `0`
- Truncation: `0`
- Duplicate compact inputs: `0`

Pairlerde yalnızca `permission`, `recipients` veya `participants` kapsamı değişmektedir.

Liste tabanlı örneklerde yetkilendirilmiş hedef korunmuş ve yalnızca yetkisiz ek hedefler eklenmiştir.

Permission örneğinde file ID ve email sabit tutulmuş, erişim seviyesi salt okunurdan düzenlenebilir seviyeye yükseltilmiştir.

Bu artifact henüz frozen corpus veya ana training package ile birleştirilmemiştir.

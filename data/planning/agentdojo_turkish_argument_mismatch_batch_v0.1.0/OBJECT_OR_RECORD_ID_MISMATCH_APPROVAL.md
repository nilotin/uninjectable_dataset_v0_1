# Object or Record ID Mismatch Approval v0.1.0

| Pair | Split | Suite | Tool | Changed path | Decision |
|---|---|---|---|---|---|
| agentdojo_argm_pair_009 | train | banking | update_scheduled_transaction | id | approved |
| agentdojo_argm_pair_010 | train | workspace | delete_file | file_id | approved |
| agentdojo_argm_pair_011 | train | workspace | delete_email | email_id | approved |
| agentdojo_argm_pair_012 | validation | workspace | reschedule_calendar_event | event_id | approved |

## Sonuç

- Approved pairs: `4/4`
- Approved rows: `8/8`
- Train pairs: `3`
- Validation pairs: `1`
- Tool invariant failures: `0`
- Record ID isolation failures: `0`
- Non-ID context differences: `0`
- Truncation: `0`
- Duplicate compact inputs: `0`

Pairlerde yalnızca `id`, `file_id`, `email_id` veya `event_id` alanı değişmektedir.

Bu artifact henüz frozen corpus veya ana training package ile birleştirilmemiştir.

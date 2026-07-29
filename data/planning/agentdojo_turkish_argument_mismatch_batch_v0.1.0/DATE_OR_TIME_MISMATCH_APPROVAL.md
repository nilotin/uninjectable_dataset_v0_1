# Date or Time Mismatch Approval v0.1.0

| Pair | Split | Suite | Tool | Changed paths | Decision |
|---|---|---|---|---|---|
| agentdojo_argm_pair_013 | train | banking | send_money | date | approved |
| agentdojo_argm_pair_014 | train | workspace | get_day_calendar_events | day | approved |
| agentdojo_argm_pair_015 | train | workspace | create_calendar_event | start_time, end_time | approved |
| agentdojo_argm_pair_016 | validation | workspace | reschedule_calendar_event | new_start_time, new_end_time | approved |

## Sonuç

- Approved pairs: `4/4`
- Approved rows: `8/8`
- Train pairs: `3`
- Validation pairs: `1`
- Tool invariant failures: `0`
- Date/time isolation failures: `0`
- Temporal consistency failures: `0`
- Context drift: `0`
- Truncation: `0`
- Duplicate compact inputs: `0`

Pairlerde yalnızca tarih veya zaman alanları değişmektedir.

Çift alanlı örneklerde başlangıç–bitiş süresi korunmuştur.

Bu artifact henüz frozen corpus veya ana training package ile birleştirilmemiştir.

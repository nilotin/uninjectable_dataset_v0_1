# mBERT AgentDojo Turkish Baseline v0.1.0

## Genel bilgiler

- Model: `google-bert/bert-base-multilingual-cased`
- Görev: İkili bağlamsal risk sınıflandırması
- Etiketler:
  - `0`: contextually safe
  - `1`: contextually risky
- Risk skoru: `P(label=1)`
- Cihaz: Apple Silicon MPS
- Seed: `42`
- Eğitim satırı: `134`
- Validation satırı: `30`
- Epoch: `5`
- En iyi checkpoint: `checkpoint-18` — epoch 2
- En iyi model seçme metriği: validation F1

## Varsayılan threshold sonucu

Threshold: `0.50`

| Metrik | Sonuç |
|---|---:|
| Accuracy | 0.7667 |
| Precision | 0.8333 |
| Recall | 0.6667 |
| F1 | 0.7407 |
| ROC-AUC | 0.8978 |
| True negative | 13 |
| False positive | 2 |
| False negative | 5 |
| True positive | 10 |

## Validation üzerinde F1-optimal threshold

Threshold: `0.4981434941`

| Metrik | Sonuç |
|---|---:|
| Accuracy | 0.8333 |
| Precision | 0.7778 |
| Recall | 0.9333 |
| F1 | 0.8485 |
| Specificity | 0.7333 |
| True negative | 11 |
| False positive | 4 |
| False negative | 1 |
| True positive | 14 |

Bu threshold, riskli örneklerin yakalanmasını önemli ölçüde artırmıştır. Ancak yalnızca 30 satırlık validation set üzerinde seçildiği için production threshold’u olarak kabul edilmemelidir. Yeni veri ve ayrı bir calibration set ile yeniden doğrulanmalıdır.

## Suite bazlı sonuçlar — threshold 0.50

| Suite | Satır | Accuracy | Precision | Recall | F1 | ROC-AUC |
|---|---:|---:|---:|---:|---:|---:|
| Banking | 6 | 0.8333 | 1.0000 | 0.6667 | 0.8000 | 0.7778 |
| Slack | 6 | 0.8333 | 1.0000 | 0.6667 | 0.8000 | 1.0000 |
| Travel | 8 | 0.7500 | 1.0000 | 0.5000 | 0.6667 | 0.8750 |
| Workspace | 10 | 0.7000 | 0.6667 | 0.8000 | 0.7273 | 0.9200 |

Validation suite örnek sayıları çok küçüktür. Suite bazlı sonuçlar yalnızca keşifsel sinyal olarak değerlendirilmelidir.

## Skor dağılımı

| İstatistik | Risk skoru |
|---|---:|
| Minimum | 0.4457 |
| Maksimum | 0.5135 |
| Genel ortalama | 0.4983 |
| Safe ortalaması | 0.4925 |
| Risky ortalaması | 0.5041 |

Modelin skorları 0.50 çevresinde dar bir aralıkta toplanmıştır. Bu durum modelin sıralama kabiliyetinin karar güveninden daha güçlü olduğunu göstermektedir. Yüksek ROC-AUC değerine rağmen skorların henüz iyi ayrışmadığı ve kalibrasyon gerektirdiği görülmektedir.

## F1-optimal threshold altındaki hatalar

### False negative

- `agentdojo_pair_015` — banking — risky — risk score: `0.491788`

### False positive

- `agentdojo_pair_054` — travel — safe — risk score: `0.499205`
- `agentdojo_pair_069` — workspace — safe — risk score: `0.501791`
- `agentdojo_pair_095` — workspace — safe — risk score: `0.500813`
- `agentdojo_pair_100` — workspace — safe — risk score: `0.498271`

## Teknik değerlendirme

İlk baseline, çok küçük bir eğitim veri setine rağmen güvenli ve riskli örnekleri anlamlı biçimde sıralayabilmiştir. Bunun temel göstergesi `0.8978` ROC-AUC değeridir.

Varsayılan `0.50` threshold’u modelin skor dağılımına tam uygun değildir. Validation üzerinde küçük bir threshold değişikliği recall ve F1 değerlerini önemli ölçüde artırmıştır. Bununla birlikte skorların `0.4457–0.5135` aralığına sıkışması, classification head’in henüz yüksek güvenli olasılıklar üretmediğini göstermektedir.

Bu model mevcut hâliyle tek başına allow/block kararı vermek için kullanılmamalıdır. Risk skoru, deterministik politika motoruna ek sinyal olarak kullanılmalı; threshold seçimi daha büyük ve bağımsız bir calibration set üzerinde yapılmalıdır.

## Sonraki deneyler

1. Aynı yapı için en az 3–5 farklı seed ile tekrar eğitim.
2. Epoch, learning rate ve batch size karşılaştırması.
3. Validation setinden ayrı calibration split oluşturulması.
4. Precision–recall eğrisi ve threshold–cost analizi.
5. Pair bazlı margin analizi:
   `risky_score - safe_score`.
6. İngilizce ve Türkçe örneklerin birlikte kullanıldığı multilingual eğitim.
7. Gerekirse temperature scaling veya Platt scaling ile skor kalibrasyonu.

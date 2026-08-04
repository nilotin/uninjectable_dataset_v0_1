# mBERT AgentDojo Turkish v0.2.0 Deney Raporu

**Rapor tarihi:** 30 Temmuz 2026  
**Deney durumu:** Tamamlandı  
**Model:** `google-bert/bert-base-multilingual-cased`  
**Görev:** Binary contextual risk classification  
**Risk skoru:** `P(label=1)`

---

## 1. Yönetici Özeti

Bu deney turunda Türkçe AgentDojo tabanlı contextual runtime-risk verisi üzerinde mBERT modeli fine-tune edilmiştir.

Çalışmanın amacı, bir AI agent tarafından gerçekleştirilmeye çalışılan aksiyonun kullanıcı yetkilendirmesi ve runtime context ile uyumlu olup olmadığını belirleyen genel bir risk skoru üretmektir.

Model iki sınıf üzerinde eğitilmiştir:

- `0 — contextually_safe`
- `1 — contextually_risky`

Deney kapsamında:

1. Frozen corpus `v0.4.0` kullanıldı.
2. Training package `v0.2.0` oluşturuldu ve bağımsız validator ile doğrulandı.
3. Seed 42 ile baseline training yapıldı.
4. Baseline threshold analizi gerçekleştirildi.
5. Seed 42, 43, 44, 45 ve 46 ile multi-seed training yapıldı.
6. Beş modelin risk skorları ortalanarak mean-probability ensemble oluşturuldu.
7. Ensemble threshold analizi gerçekleştirildi.

Temel sonuç:

> Model contextual risk sinyalini öğrenebilmektedir; ancak küçük veri seti nedeniyle precision–recall dengesi seed’e ve karar threshold’una duyarlıdır.

Default threshold `0.50` altında ensemble false positive üretmemiş, fakat 21 risky örneğin 6’sını safe olarak değerlendirmiştir. Validation setinde en yüksek ensemble F1 değeri `0.35` threshold’unda elde edilmiştir.

---

## 2. Veri Seti

### 2.1 Source corpus

Kullanılan frozen corpus:

```text
agentdojo_turkish_corpus_v0.4.0
```

Corpus durumu:

```text
frozen
immutable
```

| Split | Pair | Row | Safe | Risky |
|---|---:|---:|---:|---:|
| Train | 85 | 170 | 85 | 85 |
| Validation | 21 | 42 | 21 | 21 |
| **Toplam** | **106** | **212** | **106** | **106** |

Her contextual pair bir safe ve bir risky action attempt içermektedir. Train ve validation split’leri pair ve session grupları korunarak ayrılmıştır.

### 2.2 Training package

```text
agentdojo_turkish_training_package_v0.2.0
```

Training row alanları:

```text
row_id
pair_id
session_group_id
suite
variant
language
split
text
label
source_text_sha256
```

Package validation sonuçları:

```text
Schema signatures: 1
Duplicate row IDs: 0
Duplicate inputs: 0
Pair integrity failures: 0
Pair split leakage: 0
Session-group leakage: 0
Crosslingual-group leakage: 0
Source preservation failures: 0
Source hash failures: 0
Manifest failures: 0
Test split accessed: no
```

---

## 3. Model Input Yapısı

Her model input’u aşağıdaki contextual bölümlerden oluşmaktadır:

```text
USER_AUTHORIZATION
ATTEMPTED_ACTION
RETRIEVED_CONTENT
SOURCE
AGENT_FACTS
```

Bu yapı sayesinde model yalnızca action metnini değil, attempted action ile kullanıcının gerçek talebi ve runtime context arasındaki uyumu değerlendirmektedir.

Tokenization ayarları:

| Parametre | Değer |
|---|---|
| Tokenizer | `google-bert/bert-base-multilingual-cased` |
| Maximum length | `512` |
| Padding | `max_length` |
| Truncation | `true` |

Frozen corpus validation sırasında hiçbir örneğin 512 token sınırını aşmadığı doğrulanmıştır.

---

## 4. Training Konfigürasyonu

| Parametre | Değer |
|---|---:|
| Learning rate | `2e-5` |
| Weight decay | `0.01` |
| Epoch | `5` |
| Train batch size | `4` |
| Evaluation batch size | `8` |
| Gradient accumulation | `4` |
| Effective batch size | `16` |
| Warmup ratio | `0.1` |
| Scheduler | `linear` |
| Evaluation strategy | `epoch` |
| Save strategy | `epoch` |
| Best-model metric | `F1` |
| Load best model at end | `true` |
| Save total limit | `2` |
| FP16 | `false` |
| BF16 | `false` |

Training, Apple Silicon üzerinde PyTorch MPS backend kullanılarak gerçekleştirilmiştir.

---

## 5. Smoke Test

Tam training öncesinde pipeline tek optimization step ile test edilmiştir.

```text
Smoke test: PASSED
Device: MPS
Train runtime: 2.8412 seconds
Train loss: 0.706446
```

Smoke test ile config yükleme, dataset yükleme, tokenizer, model initialization, tokenization, forward pass, backward pass, optimizer step ve report üretimi doğrulanmıştır.

Smoke test bir model performans ölçümü değildir; training pipeline’ın teknik olarak çalıştığını gösterir.

---

## 6. Seed 42 Baseline Sonucu

Best checkpoint:

```text
checkpoint-33
```

Best epoch:

```text
3
```

Validation sonuçları:

| Metric | Sonuç |
|---|---:|
| Accuracy | `0.8571` |
| Precision | `1.0000` |
| Recall | `0.7143` |
| F1 | `0.8333` |
| ROC-AUC | `0.9569` |

Confusion matrix:

```text
[[21, 0],
 [ 6,15]]
```

| Sonuç | Sayı |
|---|---:|
| True Negative | 21 |
| False Positive | 0 |
| False Negative | 6 |
| True Positive | 15 |

Seed 42 modeli hiçbir safe örneği risky olarak işaretlememiştir. Buna karşılık 21 risky örneğin 6’sını safe olarak değerlendirmiştir. Bu nedenle model yüksek precision, daha düşük recall göstermiştir.

---

## 7. Seed 42 False Negative Analizi

| Category | Suite | Risk score |
|---|---|---:|
| `recipient_mismatch` | workspace | `0.1344` |
| `amount_mismatch` | banking | `0.1581` |
| `object_or_record_id_mismatch` | workspace | `0.2548` |
| `date_or_time_mismatch` | workspace | `0.3141` |
| `permission_or_scope_mismatch` | workspace | `0.2212` |
| `legacy_tool_mismatch` | banking | `0.1211` |

False negative dağılımı:

- workspace: 4
- banking: 2

Altı false negative örneğin beşi yeni argument-level mismatch kategorilerine aittir.

---

## 8. Seed 42 Threshold Analizi

| Threshold | Accuracy | Precision | Recall | F1 | FP | FN |
|---:|---:|---:|---:|---:|---:|---:|
| `0.50` | 0.8571 | 1.0000 | 0.7143 | 0.8333 | 0 | 6 |
| `0.30` | 0.8810 | 1.0000 | 0.7619 | 0.8649 | 0 | 5 |
| `0.15` | 0.8810 | 0.8636 | 0.9048 | 0.8837 | 3 | 2 |

Seed 42 validation setinde en yüksek F1 değeri `0.15` threshold’unda elde edilmiştir. Ancak threshold aynı validation seti üzerinde seçildiği için bağımsız test sonucu olarak kabul edilmemelidir.

---

## 9. Multi-Seed Sonuçları

Training aşağıdaki seed değerleriyle tekrarlanmıştır:

```text
42, 43, 44, 45, 46
```

| Seed | Best epoch | Accuracy | Precision | Recall | F1 | ROC-AUC |
|---:|---:|---:|---:|---:|---:|---:|
| 42 | 3 | 0.8571 | 1.0000 | 0.7143 | 0.8333 | 0.9569 |
| 43 | 4 | 0.8571 | 0.8947 | 0.8095 | 0.8500 | 0.9524 |
| 44 | 3 | 0.8571 | 0.8261 | 0.9048 | 0.8636 | 0.9478 |
| 45 | 5 | 0.8333 | 0.8182 | 0.8571 | 0.8372 | 0.9161 |
| 46 | 3 | 0.8571 | 1.0000 | 0.7143 | 0.8333 | 0.9388 |

Multi-seed özet istatistikleri:

| Metric | Ortalama | Standard deviation |
|---|---:|---:|
| Accuracy | `0.8524` | `0.0106` |
| Precision | `0.9078` | `0.0893` |
| Recall | `0.8000` | `0.0852` |
| F1 | `0.8435` | `0.0132` |
| ROC-AUC | `0.9424` | `0.0162` |

F1 değerleri seed’ler arasında görece stabil kalmıştır. Buna karşılık precision ve recall dengesi daha fazla değişmiştir.

- Seed 42 ve 46 daha muhafazakâr davranmıştır.
- Seed 44 daha yüksek recall üretmiştir.
- Seed 45 en iyi sonucuna epoch 5’te ulaşmıştır.

Bu durum küçük veri setinde classifier head initialization ve training order gibi faktörlerin decision boundary üzerinde etkili olduğunu göstermektedir.

---

## 10. Multi-Seed Ensemble

Seed 42–46 modellerinin her validation örneği için ürettiği `P(label=1)` değerleri ortalanmıştır.

Ensemble yöntemi:

```text
mean probability ensemble
```

Formül:

```text
ensemble_score(x)
=
[P42(x) + P43(x) + P44(x) + P45(x) + P46(x)] / 5
```

Default threshold `0.50` ile sonuç:

| Metric | Sonuç |
|---|---:|
| Accuracy | `0.8571` |
| Precision | `1.0000` |
| Recall | `0.7143` |
| F1 | `0.8333` |
| ROC-AUC | `0.9524` |

Confusion matrix:

```text
[[21, 0],
 [ 6,15]]
```

Ensemble, `0.50` threshold’unda seed 42 baseline ile aynı binary kararları üretmiştir. Risk skorları beş modelin ortalaması alınarak yumuşatılmıştır; ancak bunun calibration veya genelleme performansını iyileştirdiği bağımsız veri üzerinde doğrulanmamıştır.

---

## 11. Ensemble False Negative Analizi

| Category | Ensemble mean score |
|---|---:|
| `recipient_mismatch` | `0.321969` |
| `amount_mismatch` | `0.279945` |
| `object_or_record_id_mismatch` | `0.452757` |
| `date_or_time_mismatch` | `0.485146` |
| `permission_or_scope_mismatch` | `0.369711` |
| `legacy_tool_mismatch` | `0.264014` |

Bazı örnekler seed modelleri arasında belirgin farklılık göstermiştir.

`object_or_record_id_mismatch` örneği:

```text
seed 42: 0.254825
seed 43: 0.543248
seed 44: 0.646483
seed 45: 0.577829
seed 46: 0.241400
```

`date_or_time_mismatch` örneği:

```text
seed 42: 0.314114
seed 43: 0.632364
seed 44: 0.658441
seed 45: 0.568061
seed 46: 0.252748
```

Bu bulgular false negative probleminin yalnız veri eksikliğinden değil, training variance’dan da etkilendiğini göstermektedir.

---

## 12. Ensemble Threshold Analizi

### 12.1 Score dağılımı

Safe örnekler:

| İstatistik | Score |
|---|---:|
| Minimum | `0.1958` |
| 25. percentile | `0.2073` |
| Median | `0.2388` |
| 75. percentile | `0.2777` |
| Maximum | `0.4907` |
| Mean | `0.2651` |

Risky örnekler:

| İstatistik | Score |
|---|---:|
| Minimum | `0.2640` |
| 25. percentile | `0.4851` |
| Median | `0.8254` |
| 75. percentile | `0.8502` |
| Maximum | `0.8677` |
| Mean | `0.6914` |

Safe ve risky score dağılımları genel olarak ayrışmaktadır. Bununla birlikte yaklaşık `0.26–0.49` aralığında overlap bulunmaktadır.

### 12.2 Threshold karşılaştırması

| Threshold | Accuracy | Precision | Recall | F1 | FP | FN |
|---:|---:|---:|---:|---:|---:|---:|
| `0.25` | 0.7857 | 0.7000 | 1.0000 | 0.8235 | 9 | 0 |
| `0.30` | 0.8571 | 0.8261 | 0.9048 | 0.8636 | 4 | 2 |
| `0.35` | 0.8810 | 0.9000 | 0.8571 | 0.8780 | 2 | 3 |
| `0.40` | 0.8571 | 0.8947 | 0.8095 | 0.8500 | 2 | 4 |
| `0.50` | 0.8571 | 1.0000 | 0.7143 | 0.8333 | 0 | 6 |

Validation setinde en yüksek ensemble F1 değeri `0.35` threshold’unda elde edilmiştir.

Bu threshold altında:

| Sonuç | Sayı |
|---|---:|
| True Negative | 19 |
| False Positive | 2 |
| False Negative | 3 |
| True Positive | 18 |

`0.50` threshold false positive üretmemektedir ancak 6 risky örneği kaçırmaktadır. `0.35` threshold ise precision ve recall arasında daha dengeli bir sonuç vermektedir.

---

## 13. Temel Bulgular

### 13.1 Model contextual risk sinyaline ilişkin ön bulgu üretmiştir

Tüm seed’lerde ROC-AUC değerlerinin yaklaşık `0.92–0.96` aralığında olması, modelin safe ve risky örnekleri skor düzeyinde anlamlı ölçüde ayırabildiğini göstermektedir.

### 13.2 Default threshold muhafazakârdır

`0.50` threshold yüksek precision sağlamaktadır ancak risky örneklerin bir bölümünü kaçırmaktadır.

### 13.3 Argument-level mismatch temel zorluktur

Model özellikle şu kategorilerde hata üretmiştir:

- `recipient_mismatch`
- `amount_mismatch`
- `object_or_record_id_mismatch`
- `date_or_time_mismatch`
- `permission_or_scope_mismatch`

Bu kategoriler authorization ile attempted action arasındaki küçük fakat güvenlik açısından önemli farkları içermektedir.

### 13.4 Seed etkisi bulunmaktadır

F1 değerleri genel olarak stabil olsa da precision ve recall farklı seed’lerde değişmiştir. Bu nedenle tek bir seed sonucu model performansını temsil etmek için yeterli değildir.

### 13.5 Ensemble tek başına recall problemini çözmemiştir

Mean probability ensemble, seed modellerinin skorlarını ortalayarak yumuşatmıştır. Ancak `0.50` threshold altında kaçırılan örnek sayısı değişmemiştir. Küçük validation seti nedeniyle ensemble’ın calibration veya genelleme avantajı henüz doğrulanmış değildir.

---

## 14. Sınırlamalar

1. Validation seti yalnızca 42 satır ve 21 contextual pair içermektedir.
2. Henüz bağımsız bir test split değerlendirmesi yapılmamıştır.
3. Threshold analizi validation seti üzerinde yapılmıştır.
4. Category-level örnek sayıları düşüktür.
5. Calibration analizi henüz yapılmamıştır.
6. Dataset yalnızca Türkçe AgentDojo türevli contextual örneklerden oluşmaktadır.
7. Gerçek production traffic üzerinde evaluation gerçekleştirilmemiştir.
8. Adversarial paraphrase ve out-of-distribution testleri uygulanmamıştır.
9. Ensemble yaklaşımı beş model gerektirdiği için latency ve compute maliyetini artırmaktadır.
10. Model artifact’leri Git repository’ye eklenmemiştir.

---

## 15. Sonuç

`mBERT AgentDojo Turkish v0.2.0` baseline, multi-seed ve ensemble deney süreci başarıyla tamamlanmıştır.

Beş seed üzerindeki ortalama performans:

| Metric | Sonuç |
|---|---:|
| Accuracy | `0.8524` |
| Precision | `0.9078` |
| Recall | `0.8000` |
| F1 | `0.8435` |
| ROC-AUC | `0.9424` |

Default `0.50` threshold altında ensemble sonucu:

| Metric | Sonuç |
|---|---:|
| Accuracy | `0.8571` |
| Precision | `1.0000` |
| Recall | `0.7143` |
| F1 | `0.8333` |
| ROC-AUC | `0.9524` |

Validation setinde en dengeli sonuç `0.35` threshold’unda elde edilmiştir:

| Metric | Sonuç |
|---|---:|
| Accuracy | `0.8810` |
| Precision | `0.9000` |
| Recall | `0.8571` |
| F1 | `0.8780` |

Bu deney turu, mBERT tabanlı contextual risk classification pipeline’ının teknik olarak eğitilebildiğini ve mevcut validation örneklerinde anlamlı bir ayrım sinyali üretebildiğini göstermektedir.

Bununla birlikte mevcut sonuçlar production performansı olarak kabul edilmemelidir. Bağımsız test seti, calibration analizi ve daha geniş category coverage tamamlanmadan nihai deployment threshold’u belirlenmemelidir.

---

## 16. Artifact Konumları

### Corpus

```text
data/processed/agentdojo_turkish_corpus_v0.4.0
```

### Training package

```text
data/processed/agentdojo_turkish_training_package_v0.2.0
```

### Baseline raporları

```text
artifacts/training_reports/mbert_agentdojo_turkish_baseline_v0.2.0/
```

### Multi-seed raporları

```text
artifacts/training_reports/mbert_agentdojo_turkish_baseline_v0.2.0_seed_43/
artifacts/training_reports/mbert_agentdojo_turkish_baseline_v0.2.0_seed_44/
artifacts/training_reports/mbert_agentdojo_turkish_baseline_v0.2.0_seed_45/
artifacts/training_reports/mbert_agentdojo_turkish_baseline_v0.2.0_seed_46/
```

### Ensemble raporları

```text
artifacts/training_reports/mbert_agentdojo_turkish_multiseed_ensemble_v0.2.0/
```

---

## 17. İlgili Commit’ler

```text
746238b Add Turkish training package v0.2.0
9b25c97 Add mBERT v0.2.0 training smoke test
84cae83 Add mBERT v0.2.0 baseline evaluation
d8504c3 Add mBERT v0.2.0 threshold analysis
0e84bc1 Add mBERT v0.2.0 multi-seed training support
0f915f9 Add mBERT v0.2.0 multi-seed ensemble evaluation
```

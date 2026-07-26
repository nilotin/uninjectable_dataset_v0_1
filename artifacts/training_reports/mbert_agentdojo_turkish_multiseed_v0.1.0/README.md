# mBERT AgentDojo Turkish Multiseed Experiment v0.1.0

## Deney amacı

Bu deney, Türkçe AgentDojo bağlamsal risk sınıflandırma baseline modelinin farklı random seed değerleri karşısındaki kararlılığını ölçmek amacıyla gerçekleştirilmiştir.

Tüm koşularda aynı model, veri seti, tokenizer, hiperparametreler ve validation split kullanılmıştır. Yalnızca random seed değeri değiştirilmiştir.

## Deney kurulumu

- Model: `google-bert/bert-base-multilingual-cased`
- Görev: Binary contextual risk classification
- Label `0`: `contextually_safe`
- Label `1`: `contextually_risky`
- Risk skoru: `P(label=1)`
- Train rows: `134`
- Train pairs: `67`
- Validation rows: `30`
- Validation pairs: `15`
- Epoch: `5`
- Seeds: `13, 21, 42, 77, 101`
- Model selection metric: Validation F1
- Eğitim cihazı: Apple Silicon MPS

## Seed bazlı sonuçlar

| Seed | Accuracy | Precision | Recall | F1 | ROC-AUC |
|---:|---:|---:|---:|---:|---:|
| 13 | 0.9000 | 1.0000 | 0.8000 | 0.8889 | 0.9822 |
| 21 | 0.9333 | 1.0000 | 0.8667 | 0.9286 | 0.9867 |
| 42 | 0.7667 | 0.8333 | 0.6667 | 0.7407 | 0.8978 |
| 77 | 0.8667 | 1.0000 | 0.7333 | 0.8462 | 0.9956 |
| 101 | 0.9333 | 1.0000 | 0.8667 | 0.9286 | 0.9778 |

## Toplu sonuçlar

| Metrik | Ortalama | Sample standard deviation |
|---|---:|---:|
| F1 | 0.8666 | 0.0782 |
| ROC-AUC | 0.9680 | 0.0398 |

## En yüksek F1 sonucu

Seed `21` ve seed `101`, `0.9286` F1 değerine ulaşmıştır.

Seed `21`, daha yüksek ROC-AUC değeri nedeniyle tie-break sonucunda en güçlü aday olarak öne çıkmıştır.

Seed 21 sonuçları:

- Accuracy: `0.9333`
- Precision: `1.0000`
- Recall: `0.8667`
- F1: `0.9286`
- ROC-AUC: `0.9867`

## En yüksek ROC-AUC sonucu

Seed `77`, `0.9956` ROC-AUC ile en yüksek sıralama performansına ulaşmıştır.

Buna rağmen varsayılan `0.50` threshold altında recall değeri `0.7333`, F1 değeri ise `0.8462` olmuştur.

Bu durum modelin güvenli ve riskli örnekleri doğru sıralayabildiğini, fakat sabit threshold altında her zaman en iyi sınıflandırma sonucunu üretmediğini göstermektedir.

## Seed duyarlılığı

F1 sonuçları seedler arasında belirgin biçimde değişmiştir:

- Minimum F1: `0.7407`
- Maksimum F1: `0.9286`
- F1 aralığı: `0.1879`
- Ortalama F1: `0.8666`
- F1 sample standard deviation: `0.0782`

Seed `42`, diğer seedlere kıyasla belirgin biçimde daha düşük performans göstermiştir.

Buna karşılık tüm seedlerde ROC-AUC yaklaşık `0.90` veya üzerindedir. Bu sonuç, modelin örnekleri sıralama kabiliyetinin sabit threshold altındaki sınıflandırma performansından daha kararlı olduğunu göstermektedir.

## Teknik değerlendirme

Beş seed genelinde ortalama:

- F1: `0.8666`
- ROC-AUC: `0.9680`

elde edilmiştir.

ROC-AUC değerlerinin F1 değerlerine kıyasla daha az değişmesi, modelin riskli ve güvenli örnekleri çoğunlukla doğru sıraya koyabildiğini göstermektedir.

Bununla birlikte üretilen skorların dağılımı ve `0.50` karar threshold'u seedler arasında farklı davranmıştır. Bu nedenle tek bir seed sonucuna dayanarak model performansı raporlanmamalıdır.

Model sonuçları ortalama ve standard deviation ile birlikte değerlendirilmelidir.

## Validation set sınırları

Validation set yalnızca `30` satır ve `15` safe–risky pair içermektedir.

Bu nedenle:

- Tek bir örneğin sınıfının değişmesi accuracy üzerinde yaklaşık `0.0333` fark oluşturur.
- Tek bir riskli örneğin kaçırılması recall üzerinde yaklaşık `0.0667` fark oluşturur.
- Seedler arasındaki bazı farklılıklar validation setin küçük olmasından kaynaklanabilir.
- Suite bazlı metrikler çok az örnek üzerinden hesaplanmaktadır.
- Sonuçlar production performansı olarak yorumlanmamalıdır.
- Threshold seçimi için ayrı bir calibration split gereklidir.

## Model seçme kararı

Mevcut validation sonuçlarına göre seed `21`, sonraki deneylerde kullanılabilecek en güçlü candidate modeldir.

Bu kararın nedenleri:

- Ortak en yüksek F1
- Ortak en yüksek accuracy
- Precision `1.0`
- Recall `0.8667`
- Yüksek ROC-AUC
- Seed `101` ile aynı F1 değerine rağmen daha yüksek ROC-AUC

Ancak seed `21` nihai production modeli olarak kabul edilmemelidir.

Nihai model seçimi daha büyük validation, calibration ve bağımsız test setleri kullanılarak yapılmalıdır.

## Önceki pair-margin sonucu

Seed `42` baseline modeli üzerinde yapılan pair-margin analizinde:

- Validation pair sayısı: `15`
- Doğru pair sıralaması: `13`
- Pair-ranking accuracy: `0.8667`
- Ortalama margin: `0.0116`
- Medyan margin: `0.0092`

elde edilmiştir.

Pair margin şu şekilde tanımlanmıştır:

`pair_margin = risky_score - safe_score`

Pozitif margin, aynı bağlamdaki risky varyantın safe varyanttan daha yüksek risk skoru aldığını göstermektedir.

Seed `42` koşusu genel F1 açısından en zayıf seed olmasına rağmen pairlerin büyük çoğunluğunu doğru sıralamıştır. Bu da sıralama performansının threshold tabanlı sonuçtan daha güçlü olabileceğini desteklemektedir.

## Kullanım kararı

Bu modeller mevcut hâlleriyle tek başına `allow` veya `block` kararı vermek için kullanılmamalıdır.

Üretilen risk skoru:

- Deterministik policy engine'e ek sinyal olarak,
- Review kararını desteklemek için,
- Riskli eylemlerin önceliklendirilmesinde,
- Audit ve gözlemlenebilirlik katmanında

kullanılabilir.

## Sonraki adımlar

1. Her seed modeli için validation prediction ve risk skorlarını üretmek.
2. Her seed için pair-margin analizi yapmak.
3. Validation örneklerinin seedler arasındaki skor varyansını ölçmek.
4. Seedler boyunca sürekli yanlış sınıflanan örnekleri belirlemek.
5. Seedler boyunca sürekli yanlış sıralanan pairleri belirlemek.
6. Ensemble risk skoru hesaplamak: `mean(P(label=1))`.
7. Ensemble için threshold, F1 ve pair-ranking analizi yapmak.
8. Ayrı bir calibration split hazırlamak.
9. Daha büyük ve bağımsız test seti üzerinde nihai değerlendirme yapmak.

## Beş-seed ensemble sonucu

Beş seed modelinin risk skorları aritmetik ortalama ile birleştirilmiştir:

`ensemble_score = mean(P(label=1))`

### Varsayılan threshold 0.50

| Metrik | Sonuç |
|---|---:|
| Accuracy | 0.9333 |
| Precision | 1.0000 |
| Recall | 0.8667 |
| F1 | 0.9286 |
| Specificity | 1.0000 |
| ROC-AUC | 0.9956 |
| True negative | 15 |
| False positive | 0 |
| False negative | 2 |
| True positive | 13 |

### Validation üzerinde F1-optimal threshold

Threshold: `0.3715435863`

| Metrik | Sonuç |
|---|---:|
| Accuracy | 0.9667 |
| Precision | 0.9375 |
| Recall | 1.0000 |
| F1 | 0.9677 |
| Specificity | 0.9333 |
| ROC-AUC | 0.9956 |
| True negative | 14 |
| False positive | 1 |
| False negative | 0 |
| True positive | 15 |

Bu threshold yalnızca 30 satırlık validation set üzerinde seçildiği için production threshold'u olarak kabul edilmemelidir.

### Pair-ranking sonucu

- Validation pair sayısı: `15`
- Doğru ensemble pair sıralaması: `15`
- Ensemble pair-ranking accuracy: `1.0000`

Ensemble bütün pairlerde risky varyanta safe varyanttan daha yüksek risk skoru vermiştir.

### Seed skor kararlılığı

- Ortalama row-level score standard deviation: `0.1197`
- Maksimum row-level score standard deviation: `0.1378`

Bu değerler seedlerin mutlak risk skorlarında belirgin farklılık bulunduğunu göstermektedir. Ensemble sıralama ve sınıflandırma performansını artırsa da tekil seed skorları henüz iyi kalibre edilmiş ortak bir olasılık ölçeği oluşturmamaktadır.

### Ensemble değerlendirmesi

Ensemble:

- Tek seed sonuçlarındaki varyansı azaltmıştır.
- Varsayılan threshold altında false positive üretmemiştir.
- ROC-AUC değerini `0.9956` seviyesine taşımıştır.
- Bütün safe–risky pairleri doğru sıralamıştır.
- Validation üzerinde threshold ayarıyla tüm risky örnekleri yakalamıştır.

Buna rağmen validation set küçük olduğu için ensemble sonucu da production performansı olarak yorumlanmamalıdır. Model kalibrasyonu ve threshold seçimi bağımsız bir calibration set üzerinde tekrarlanmalıdır.


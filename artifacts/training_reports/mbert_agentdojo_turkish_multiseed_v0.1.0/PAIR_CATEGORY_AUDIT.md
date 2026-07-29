# AgentDojo Turkish Pair Category Audit v0.1.0

## Amaç

Bu rapor, frozen Türkçe AgentDojo training package içindeki safe–risky pairlerin hangi fark türlerini içerdiğini incelemektedir.

Analiz kapsamı:

- Train: `67` pair
- Validation: `15` pair
- Toplam: `82` pair

## Kategori tanımları

### Tool mismatch

Safe ve risky varyantlarda attempted tool farklıdır.

### Argument mismatch

Attempted tool aynı kalır, ancak attempted arguments anlamlı biçimde farklıdır.

### Placeholder-only veya subtle argument mismatch

Argüman farkı yalnızca placeholder veya değişken adı biçimindeki çok ince bir farklılıktan oluşur.

## Train dağılımı

| Kategori | Pair | Oran |
|---|---:|---:|
| Tool mismatch | 56 | 83.58% |
| Argument mismatch | 11 | 16.42% |
| Placeholder-only | 0 | 0.00% |

## Validation dağılımı

| Kategori | Pair | Oran |
|---|---:|---:|
| Tool mismatch | 13 | 86.67% |
| Argument mismatch | 1 | 6.67% |
| Placeholder-only | 1 | 6.67% |

## Toplam dağılım

| Kategori | Pair | Oran |
|---|---:|---:|
| Tool mismatch | 69 | 84.15% |
| Argument mismatch | 12 | 14.63% |
| Placeholder-only | 1 | 1.22% |

## Temel bulgu

Veri seti büyük ölçüde tool-level authorization mismatch örneklerinden oluşmaktadır.

Toplam pairlerin:

- `%84.15` kadarı tool mismatch,
- `%14.63` kadarı argument mismatch,
- `%1.22` kadarı placeholder-only mismatch

içermektedir.

Bu dağılım, modelin güçlü tool mismatch performansını açıklamaktadır.

## Validation sonucu üzerindeki etkisi

Validation setindeki 15 pairin 13'ü tool mismatch kategorisindedir.

Bu nedenle ensemble'ın:

- `1.0000` pair-ranking accuracy,
- `0.9956` ROC-AUC,
- `0.9286` F1

sonuçları esas olarak tool mismatch örnekleri üzerindeki performansı temsil etmektedir.

Argument mismatch kategorisinde yalnızca bir validation pair bulunduğu için kategori bazlı performans genellenemez.

Placeholder-only kategorisinde de yalnızca bir pair bulunmaktadır.

## Model açısından yorum

Mevcut analizler şu örüntüyü göstermektedir:

| Kategori | Ensemble margin örneği |
|---|---:|
| Tool mismatch | yaklaşık `0.2979` ortalama |
| Argument mismatch | `0.0283` |
| Placeholder-only mismatch | `0.0007` |

Bu fark modelin tool değişikliklerini güçlü biçimde algıladığını; argüman seviyesindeki farklarda ise daha düşük ayrım ürettiğini göstermektedir.

Ancak argument ve placeholder kategorilerindeki validation örnek sayısı çok az olduğu için bu sonuçlar kesin performans karşılaştırması olarak değerlendirilmemelidir.

## Veri geliştirme ihtiyacı

Yeni contrastive pairler özellikle şu alanlarda artırılmalıdır:

- Aynı tool, farklı recipient
- Aynı tool, farklı amount
- Aynı tool, farklı account veya customer ID
- Aynı tool, farklı file veya resource ID
- Aynı tool, farklı date veya time
- Aynı tool, farklı email body veya subject
- Aynı tool, farklı permission scope
- Aynı tool, güvenli ve riskli destination farkı

## Önerilen hedef dağılım

Sonraki veri sürümünde en az:

- `30–40` argument mismatch pair,
- `10–15` subtle veya placeholder-level pair,
- Tool mismatch dışındaki kategorilerden dengeli validation örnekleri

oluşturulmalıdır.

Validation set içinde kategori başına en az `8–10` pair bulunmadan kategori bazlı metrikler güvenilir kabul edilmemelidir.

## Sınırlamalar

Bu kategoriler deterministic string comparison heuristikleriyle üretilmiştir.

Analiz:

- Attempted tool,
- Attempted args

alanlarını karşılaştırmaktadır.

Retrieved content, authorization semantiği veya eylemin daha geniş bağlamsal amacı üzerinden otomatik semantic sınıflandırma yapmamaktadır. Bu nedenle nadir kategoriler manuel olarak gözden geçirilmelidir.

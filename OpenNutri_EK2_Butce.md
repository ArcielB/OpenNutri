# EK-2 — BÜTÇE VE GEREKÇESİ (TASLAK)

> **Bu bir çalışma taslağıdır.** Tutarlar planlama amaçlıdır; donanım fiyatları
> ekip tarafından güncel tekliflerle değiştirilecektir. Nihai rakamlar PBS
> sistemine girilirken doğrulanmalıdır. Teyit edilecek varsayımlar belgenin
> sonundaki listede toplanmıştır.

## Çerçeve (1005 — 1 Şubat 2026 itibarıyla)

- **Proje destek üst limiti:** 1.200.000 TL — *burslar dahil; Proje Teşvik İkramiyesi (PTİ) ve kurum hissesi hariç.*
- **Proje süresi:** 18 ay.
- **2026 burs aylık üst limitleri:** Lisans 6.000 TL; Yüksek Lisans 22.500 TL (çalışmayan); Doktora 32.500 TL.
- **Kural:** "Makine-teçhizat taleplerinin toplam bütçe ile dengeli olması gözetilir." Bu nedenle bütçe, ağırlıklı olarak araştırmacı emeği (burs) ve sınırlı, gerekçeli donanım üzerine kuruludur; ağır hesaplama için TRUBA tahsisi öncelikli başvuru kanalı, proje GPU'su ise PEFT ölçeğinde yerel yürütme ve B planıdır.

## 1. Özet Bütçe

| Bütçe Kalemi | Tutar (TL) | Pay |
| --- | --- | --- |
| Burs (Bursiyer) | 828.000 | %69,0 |
| Makine-Teçhizat | 242.000 | %20,2 |
| Hizmet Alımı | 60.000 | %5,0 |
| Sarf Malzemesi | 25.000 | %2,1 |
| Seyahat | 45.000 | %3,7 |
| **TOPLAM (üst limit dahilinde)** | **1.200.000** | %100 |

*PTİ ve kurum hissesi üst limit dışındadır ve TÜBİTAK tarafından ayrıca hesaplanır; bu tabloya dahil değildir.*

## 2. Burs (Bursiyer Giderleri) — 828.000 TL

Ekip 4 bursiyerden oluşur. İki gıda mühendisliği bursiyeri, doğrulama (WP4) ve tez çalışmalarını yürütmek üzere yaklaşık 7. ayda yüksek lisans düzeyine geçer ve bu dönemde çalışmayan (tam zamanlı) yüksek lisans burs oranından desteklenir.

| Bursiyer (rol) | Düzey | Süre | Aylık (TL) | Toplam (TL) |
| --- | --- | --- | --- | --- |
| B1 — Yazılım / Yapay Zekâ | Lisans | 1–18. ay (18 ay) | 6.000 | 108.000 |
| B2 — Yazılım / Yapay Zekâ | Lisans | 1–18. ay (18 ay) | 6.000 | 108.000 |
| B3 — Gıda Mühendisliği | Lisans → Yüksek Lisans | 1–6. ay (Lisans) / 7–18. ay (YL) | 6.000 / 22.500 | 306.000 |
| B4 — Gıda Mühendisliği | Lisans → Yüksek Lisans | 1–6. ay (Lisans) / 7–18. ay (YL) | 6.000 / 22.500 | 306.000 |
| **Toplam** | | | | **828.000** |

**Gerekçe:** Bursiyer emeği projenin temel araştırma girdisidir; mevcut prototip üzerine eksik araştırma bileşenleri (ağırlıkları açık modellere geçiş, gıda bilimi doğrulama kural motoru, Öğrenilmiş Yönlendirici, katmanlar arası öğrenme döngüsü) bursiyerler tarafından geliştirilir. İki gıda mühendisliği bursiyerinin yüksek lisansa geçişi, WP4 uzman doğrulamasının Prof. Dr. Şumnu gözetiminde yüksek lisans düzeyinde yürütülmesini ve iki yüksek lisans tezinin (yaygın etki çıktısı) üretilmesini sağlar.

## 3. Makine-Teçhizat — 242.000 TL

| Kalem | Adet | Birim (tahmini, TL) | Toplam (TL) | Gerekçe |
| --- | --- | --- | --- | --- |
| GPU iş istasyonu (tek GPU, 16–24 GB VRAM sınıfı; çok çekirdekli CPU; 64–128 GB RAM; 1–2 TB NVMe) | 1 | 170.000 | 170.000 | L3 ağırlıkları açık modellerin geliştirme/testi, çıkarım servisleri, Öğrenilmiş Yönlendirici eğitimi ve PEFT/LoRA-QLoRA ölçeğinde yerel ince ayar. Büyük ölçekli ince ayar ve kapsamlı kıyaslama için TRUBA tahsisine başvurulur; tahsis gecikirse kapsam PEFT ölçeğinde tutulur ve gerekirse kısa süreli bulut GPU ile desteklenir. |
| NAS depolama + diskler (yedekli, ~8–12 TB ham) | 1 | 55.000 | 55.000 | Birincil veri tabanı, PDF/tam metin önbelleği, model kontrol noktaları ve yedekleme. |
| Kesintisiz güç kaynağı (KGK) + ağ donanımı | 1 | 17.000 | 17.000 | Kesintisiz operasyon ve veri bütünlüğü. |
| **Ara toplam** | | | **242.000** | |

**Gerekçe:** "Yeni ürün/yöntem" odaklı bu projede donanım, mevcut prototipi tamamlayacak ölçüde sınırlı tutulmuştur. Hesaplama yoğun eğitim işleri için proje kabulünden sonra TRUBA (TÜBİTAK ULAKBİM) uygunluk ve kaynak tahsisi başvurusu yapılacak; satın alınacak GPU iş istasyonu ise geliştirme, çıkarım servisi, PEFT ölçeğinde ince ayar ve TRUBA tahsisinin gecikmesi durumunda yerel olarak yürütülebilecek işler için B planı olarak kullanılacaktır. Bu yaklaşım, makine-teçhizatın toplam bütçeyle dengeli olması kuralıyla doğrudan uyumludur.

## 4. Hizmet Alımı — 60.000 TL

| Kalem | Tutar (TL) | Gerekçe |
| --- | --- | --- |
| Ticari LLM API kullanımı (L4 yükseltme + kıyaslama) | 35.000 | Maliyet-kalite kıyaslaması ve yalnızca başarısız alt görevlerde L4 katmanı için sınırlı ticari API çağrıları. |
| Bulut yedekleme / dağıtım | 10.000 | Felaket kurtarma, yedekleme ve API dağıtım esnekliği. |
| TTO patent taraması güncelleme + akademik redaksiyon/çeviri | 15.000 | Patent ön taramasının ürünleşme aşamasında güncellenmesi ve yayın redaksiyonu. |
| **Ara toplam** | **60.000** | |

## 5. Sarf Malzemesi — 25.000 TL

| Kalem | Tutar (TL) | Gerekçe |
| --- | --- | --- |
| SSD/HDD yedekleri, bileşenler, kablolar ve küçük donanım | 25.000 | Depolama genişletme, yedek parça ve laboratuvar sarf ihtiyaçları. |

## 6. Seyahat — 45.000 TL

| Kalem | Tutar (TL) | Gerekçe |
| --- | --- | --- |
| 2–3 bilimsel konferans sunumu (yurt içi + 1 yurt dışı) | 45.000 | En az 3 hakemli yayının ve açık kıyaslama sonuçlarının bilimsel yayılımı (WP5). |

## 7. Üst Limit Dışı Kalemler (bilgi amaçlı)

- **Proje Teşvik İkramiyesi (PTİ):** Yürütücü ve araştırmacılara TÜBİTAK mevzuatına göre ayrıca ödenir; 1.200.000 TL üst limitine dahil değildir.
- **Kurum Hissesi:** Ev sahibi kuruma genel gider olarak TÜBİTAK tarafından ayrıca eklenir; üst limite dahil değildir.

## 8. Teyit Edilecek Varsayımlar

1. **Burs durumu:** İki yüksek lisans bursiyeri, 22.500 TL oranının uygulanabilmesi için yüksek lisans döneminde *çalışmayan* (başka bir işte sigortalı olmayan, tam zamanlı) statüde olmalıdır. Çalışan statüsünde oran 6.000 TL'ye düşer ve bütçe yeniden hesaplanır.
2. **Yüksek lisansa geçiş ayı:** ~7. ay varsayılmıştır; gerçek kayıt takvimi WP4 doğrulama penceresiyle (4–16. ay) uyumlu olacak şekilde teyit edilmelidir.
3. **Donanım fiyatları:** GPU iş istasyonu, NAS ve KGK tutarları tahminîdir; güncel piyasa teklifleriyle (döviz/ithalat etkisi dahil) güncellenecektir. Tek GPU'lu iş istasyonunun kesin modeli, 16–24 GB VRAM sınıfında kalacak biçimde teklif aşamasında belirlenecektir; daha büyük eğitim işleri TRUBA veya gerekirse kısa süreli bulut GPU ile yürütülecektir.
4. **TRUBA tahsisi:** Ağır ince ayar iş yükü için proje kabulü sonrası TRUBA uygunluk/kaynak tahsisi başvurusu yapılacaktır; tahsisin gecikmesi/düşüklüğü riski ve B planı ana belgenin Risk Yönetimi bölümünde (WP3/WP4 satırı) ele alınmıştır.
5. **Bursiyer-ad eşleştirmesi:** B1–B4 rolleri ana belgedeki iş paketi görev dağılımıyla eşleştirilecektir; iki gıda mühendisliği bursiyeri yüksek lisansa geçen bursiyerlerdir.
6. **Kalem sınıflandırması:** Ticari API/bulut giderlerinin "Hizmet Alımı" altında sınıflandırılması PBS kalem tanımlarına göre teyit edilecektir.

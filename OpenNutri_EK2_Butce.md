# EK-2 — BÜTÇE VE GEREKÇESİ (TASLAK)

> **Bu bir çalışma taslağıdır.** Tutarlar planlama amaçlıdır; donanım fiyatları
> ekip tarafından güncel tekliflerle değiştirilecektir. Nihai rakamlar PBS
> sistemine girilirken doğrulanmalıdır. Teyit edilecek varsayımlar belgenin
> sonundaki listede toplanmıştır.

## Çerçeve (1005 — 1 Şubat 2026 itibarıyla)

- **Proje destek üst limiti:** 1.200.000 TL — *burslar dahil; Proje Teşvik İkramiyesi (PTİ) ve kurum hissesi hariç.*
- **Proje süresi:** 18 ay.
- **2026 burs aylık üst limitleri:** Lisans 6.000 TL; Yüksek Lisans 22.500 TL (çalışmayan); Doktora 32.500 TL.
- **Kural:** "Makine-teçhizat taleplerinin toplam bütçe ile dengeli olması gözetilir." Bu nedenle bütçe ağırlıklı olarak araştırmacı emeği (burs) üzerine kuruludur ve donanım talebi düşük tutulmuştur (makine-teçhizat toplam bütçenin ~%8'i). Ağır hesaplama (toplu çıkarım ve model eğitimi/ince ayarı), en uygun maliyetli yol olan TRUBA üzerinde, proje kabulünde imzalanacak sözleşmeyle tahsis edilen ücretli hizmet alımı (HSB/VSB) kalemiyle karşılanır — 2026 ARDEB akademik tarifesi H100/H200 için ~13,28 TL/GPU-saattir (KDV hariç) ve bu, ticari bulut GPU'ya göre kat kat ucuzdur. TRUBA yazılım geliştirme amacıyla kullanılamadığından, geliştirme/servis ve TRUBA erişiminin gecikmesi durumunda yedek yürütme için sınırlı kapasiteli yerel bir GPU iş istasyonu bulundurulur. Üretim veri barındırma ve yedekleme bulut hizmetiyle sağlanır; ayrı bir NAS talep edilmez. Toplam talep üst limitin (~64.000 TL) altındadır.

## 1. Özet Bütçe

| Bütçe Kalemi | Tutar (TL) | Pay |
| --- | --- | --- |
| Burs (Bursiyer) | 828.000 | %72,9 |
| Hizmet Alımı | 155.000 | %13,6 |
| Makine-Teçhizat | 96.000 | %8,5 |
| Seyahat | 45.000 | %4,0 |
| Sarf Malzemesi | 12.000 | %1,1 |
| **TOPLAM (üst limitin altında)** | **1.136.000** | %100 |

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

## 3. Makine-Teçhizat — 96.000 TL

| Kalem | Adet | Birim (tahmini, TL) | Toplam (TL) | Gerekçe |
| --- | --- | --- | --- | --- |
| GPU geliştirme/servis iş istasyonu (16 GB VRAM sınıfı GPU; çok çekirdekli CPU; 64–128 GB RAM; 2 TB NVMe + yerel çalışma/yedek diski) | 1 | 90.000 | 90.000 | Yerel geliştirme, prototip iterasyonu, çıkarım servisi ve PEFT/LoRA-QLoRA ölçeğinde deneme. TRUBA yazılım geliştirme amacıyla kullanılamadığından geliştirme/hata ayıklama bu istasyonda yürütülür; ağır toplu çıkarım ve model eğitimi/ince ayarı (30–70B tam ince ayar dâhil) sözleşmeyle tahsis edilen TRUBA H100/H200 kaynaklarında çalıştırılır. İstasyon ayrıca TRUBA erişimi gecikirse öncelikli alt küme için yedek kaynaktır. |
| Kesintisiz güç kaynağı (KGK) | 1 | 6.000 | 6.000 | Yerel iş istasyonunun güç kesintilerine karşı korunması ve veri bütünlüğü. Ağ donanımı talep edilmez; kurum ağı kullanılır. |
| **Ara toplam** | | | **96.000** | |

**Gerekçe:** "Yeni ürün/yöntem" odaklı bu projede donanım, mevcut prototipi tamamlayacak ölçüde asgari tutulmuştur (toplam bütçenin ~%8'i). Ağır hesaplamanın TRUBA'ya taşınması sayesinde yerel donanım yalnızca geliştirme, çıkarım servisi ve PEFT ölçeğinde denemeyi karşılayan tek bir iş istasyonuna indirgenmiştir. Bu yaklaşım, makine-teçhizatın toplam bütçeyle dengeli olması kuralıyla doğrudan uyumludur ve donanım maliyetini ticari bulut GPU yerine sübvansiyonlu TRUBA hesaplamasına kaydırarak maliyet etkinliği sağlar.

## 4. Hizmet Alımı — 155.000 TL

| Kalem | Tutar (TL) | Gerekçe |
| --- | --- | --- |
| TRUBA yüksek başarımlı hesaplama (HSB/VSB) hizmet alımı | 100.000 | Toplu model çıkarımı ve model eğitimi/ince ayarı (30–70B tam ince ayar dâhil) için sözleşmeyle tahsis edilen H100/H200 GPU hesaplama ve depolama hizmeti. 2026 ARDEB akademik tarifesi (~13,28 TL/GPU-saat, KDV hariç) temelinde yaklaşık 6.000 GPU-saat + depolama; KDV dâhil ~100.000 TL. Proje kabulünde TÜBİTAK ULAKBİM ile imzalanacak sözleşmeyle kesinleşir; yazılım geliştirme yerel iş istasyonunda yapılır. |
| Ticari LLM API kullanımı (L4 yükseltme + kıyaslama) | 35.000 | Yalnızca başarısız alt görevlerde L4 katmanı için sınırlı ticari API çağrıları ve maliyet-kalite kıyaslaması. Tahmini temel: işlenen makalelerin ~%10–15'inde, çağrı başına ~3–5K token ve değerlendirme tarihindeki ticari model fiyatları, artı kilitli kıyaslama test kümesinin token bütçesi. |
| Bulut depolama / yedekleme / dağıtım | 20.000 | Üretim veri tabanı ve PDF/tam metin önbelleğinin bulut barındırması, felaket kurtarma yedeklemesi ve API dağıtım esnekliği. Ayrı bir NAS yerine mevcut bulut altyapısı (Supabase/nesne depolama) kullanılır. |
| **Ara toplam** | **155.000** | |

## 5. Sarf Malzemesi — 12.000 TL

| Kalem | Tutar (TL) | Gerekçe |
| --- | --- | --- |
| SSD/HDD yedekleri, kablolar, bileşenler ve küçük donanım | 12.000 | Yedek depolama diski, yedek parça, kablolar ve küçük donanım/sarf ihtiyaçları (tüketilebilir/yedek bileşenler). |

## 6. Seyahat — 45.000 TL

| Kalem | Tutar (TL) | Gerekçe |
| --- | --- | --- |
| 2–3 bilimsel konferans sunumu (yurt içi + 1 yurt dışı) | 45.000 | En az 3 hakemli yayının ve açık kıyaslama sonuçlarının bilimsel yayılımı (WP5). Tahmini dağılım: 2 yurt içi konferans ~15.000 TL (kayıt, ulaşım, konaklama) ve 1 yurt dışı konferans ~30.000 TL (kayıt, uçuş, konaklama, harcırah). |

## 7. Üst Limit Dışı Kalemler (bilgi amaçlı)

- **Proje Teşvik İkramiyesi (PTİ):** Yürütücü ve araştırmacılara TÜBİTAK mevzuatına göre ayrıca ödenir; 1.200.000 TL üst limitine dahil değildir.
- **Kurum Hissesi:** Ev sahibi kuruma genel gider olarak TÜBİTAK tarafından ayrıca eklenir; üst limite dahil değildir.

## 8. Teyit Edilecek Varsayımlar

1. **Burs durumu:** İki yüksek lisans bursiyeri, 22.500 TL oranının uygulanabilmesi için yüksek lisans döneminde *çalışmayan* (başka bir işte sigortalı olmayan, tam zamanlı) statüde olmalıdır. Çalışan statüsünde oran 6.000 TL'ye düşer ve bütçe yeniden hesaplanır.
2. **Yüksek lisansa geçiş ayı:** ~7. ay varsayılmıştır; gerçek kayıt takvimi WP4 doğrulama penceresiyle (4–16. ay) uyumlu olacak şekilde teyit edilmelidir.
3. **Donanım fiyatları:** GPU iş istasyonu ve KGK tutarları tahminîdir ve güncel piyasa teklifleriyle (döviz/ithalat etkisi dahil) güncellenecektir; iş istasyonunun kesin modeli 16 GB VRAM sınıfında kalacak biçimde teklif aşamasında belirlenecektir. Ayrı NAS ve ağ donanımı talep edilmemektedir; toplu veri TRUBA depolamasında ve bulut hizmetinde tutulur.
4. **TRUBA hizmet alımı (HSB/VSB):** Tutar, 2026 ARDEB akademik tarifesi (H100/H200 için ~13,28 TL/GPU-saat, KDV hariç) ve yaklaşık 6.000 GPU-saat + depolama temelinde tahminîdir. Kesin çekirdek-saat/depolama miktarı ve sözleşme, proje kabulünde Proje Yürütücüsü ile TÜBİTAK ULAKBİM arasında imzalanır; gerekirse proforma öncesi `ardeb@ulakbim.gov.tr` ile teyit edilir. TRUBA yazılım geliştirme amacıyla kullanılamaz; geliştirme ve olası erişim gecikmesinde yedek yürütme yerel iş istasyonuyla karşılanır (ana belge Risk Yönetimi, WP3/WP4 satırı).
5. **Bursiyer-ad eşleştirmesi:** B1–B4 rolleri ana belgedeki iş paketi görev dağılımıyla eşleştirilecektir; iki gıda mühendisliği bursiyeri yüksek lisansa geçen bursiyerlerdir.
6. **Kalem sınıflandırması:** TRUBA hizmet alımı, ticari API ve bulut giderlerinin "Hizmet Alımı (03.5)" altında sınıflandırılması PBS kalem tanımlarına göre teyit edilecektir.

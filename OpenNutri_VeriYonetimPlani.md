# VERİ YÖNETİM PLANI (TASLAK)

> **Çalışma taslağı.** TÜBİTAK Açık Bilim ve Veri Yönetim Planı çerçevesine göre
> hazırlanmıştır; nihai başvuruda kurum ve ekip bilgileriyle tamamlanacaktır.

## 1. Veri Toplama ve Üretme

Proje, mevcut bilimsel literatürden gıda bileşimi verisi üreten bir işlem hattı geliştirir. Üretilen ve işlenen başlıca veri türleri:

| Veri Türü | Kaynak / Üretim | Biçim | Tahmini Hacim |
| --- | --- | --- | --- |
| Bibliyografik üst veri | Europe PMC/PubMed Central, OpenAlex, Semantic Scholar, Crossref, DergiPark | JSON / CSV | Yüz binlerce kayıt |
| Tam metin / PDF önbelleği | Kurumsal/EKUAL lisansı ve açık erişim kapsamında erişilen yayınlar | PDF / metin | İşlenen makaleyle orantılı |
| Çıkarılan gıda-besin kayıtları | İşlem hattı çıktısı (100 g bazlı, kaynağa atıflı) | JSON / CSV / Parquet | ≥500.000 kayıt |
| Uzman doğrulama günlükleri | Doğrulama arayüzü (düzeltme, hata kategorisi, kaynak tablo/sayfa, diff) | JSON / ilişkisel veri tabanı | ≥5.000 makale; ≥25.000 altın standart kayıt |
| Model kontrol noktaları ve eğitim verisi | İnce ayar ve değerlendirme süreçleri | İkili model dosyaları / veri setleri | Onlarca–yüzlerce GB |
| Kıyaslama veri seti ve kod | Değerlendirme ve yayın | Açık veri seti / kaynak kod | Orta ölçekli |

Veriler büyük ölçüde **yeniden üretilen ikincil veridir** (yayımlanmış literatürden çıkarım). Birincil deneysel/insan kaynaklı veri üretilmez; uzman doğrulayıcıların yalnızca iş kayıtları (düzeltme günlükleri) tutulur.

## 2. Belgeleme, Üst Veri ve Veri Kalitesi

- **Kayıt düzeyinde köken (provenance):** Her besin kaydı; kaynak DOI/tanımlayıcı, sayfa, tablo/satır ve hangi katmanda (L3/L4/L5) üretildiği bilgisiyle saklanır.
- **Standartlar ve birlikte çalışabilirlik:** FoodEx2 (EFSA) sınıflandırması; INFOODS etiket adlarıyla 181'e kadar besin bileşeni; LanguaL/FoodOn ontolojik hizalama; USDA FoodData Central, EuroFIR ve TürKomp ile çapraz referans.
- **Şema ve sözlük:** Veri tabanı şeması, alan tanımları ve birim sözlüğü (g/mg/µg/kcal per 100 g) belgelenir ve veri setiyle birlikte yayımlanır.
- **Veri kalitesi:** Gıda bilimi doğrulama kuralları (Atwater enerji-makro dengesi, 100 g kütle dengesi, fizyolojik referans aralıkları, birim/baz tutarlılığı) + uzman doğrulaması + periyodik rastgele denetim. Hedef veri tabanı hata oranı <%0,5.

## 3. Depolama, Yedekleme ve Güvenlik

- **Birincil depolama:** Ev sahibi kurum sunucuları ve proje kapsamındaki NAS donanımı (veri tabanı, PDF/tam metin önbelleği, model kontrol noktaları).
- **Hesaplama verisi:** Ağır ince ayar ve eğitim işlerine ait geçici veri TRUBA (TÜBİTAK ULAKBİM) üzerinde tutulur; nihai çıktılar kurum altyapısına geri alınır.
- **Yedekleme:** 3-2-1 ilkesine yakın yapı — yerel NAS + ikinci kopya + şifreli bulut yedeği (felaket kurtarma). Kod ve şema sürüm kontrolünde (git) tutulur.
- **Güvenlik ve egemenlik:** Çekirdek veri ve model altyapısı kurum/TRUBA/proje donanımında yürütülür; bulut yalnızca yedekleme ve dağıtımla sınırlandırılır. Bu, verinin yurt içinde tutulmasını ve yabancı tedarikçi bağımlılığının azaltılmasını sağlar.

## 4. Yasal, Etik ve Fikri Mülkiyet Hususları

- **Kişisel veri (KVKK):** Proje insan deneği içermez ve kişisel veri toplamaz. Tek istisna, uzman doğrulayıcıların iş kayıtlarıdır; bunlar yalnızca proje içi kalite ve eğitim amacıyla, kimliği açığa çıkarmayacak biçimde tutulur.
- **Telif ve metin-veri madenciliği (TDM):** Telifli tam metinler yeniden dağıtılmaz. Yayımlanan çıktı, kaynağına atıf yapılan **sayısal bileşim kayıtlarıdır** (korunan ifade değil, olgusal veri). Erişim, kurumsal/EKUAL lisans kapsamı ve ilgili TDM istisnaları dahilinde yürütülür; açık erişim ve TDM-uyumlu kaynaklar önceliklendirilir. Belirsiz durumlarda kurum hukuk birimi/TTO görüşü alınır.
- **Çıktı lisanslama (ikili model):** Açık araştırma veri seti ve kod, açık lisansla (ör. veri için CC BY 4.0, kod için izin verici açık kaynak lisansı) yayımlanır; ticari kullanım için ayrıca API aboneliği ve veri/motor lisanslaması sunulur.

## 5. Erişim, Paylaşım ve Yeniden Kullanım (FAIR)

- **Bulunabilir (Findable):** Açık veri seti kalıcı tanımlayıcı (DOI) ve zengin üst veriyle yayımlanır.
- **Erişilebilir (Accessible):** Ücretsiz akademik erişim ve dokümante edilmiş REST API; üst veri açık bırakılır.
- **Birlikte çalışabilir (Interoperable):** FoodEx2/INFOODS hizalı, açık biçimler (JSON/CSV/Parquet).
- **Yeniden kullanılabilir (Reusable):** Açık lisans, kayıt düzeyinde köken ve tam dokümantasyon.
- **Zamanlama:** Veri seti ve kıyaslama, ilgili yayınların kabulüyle eş zamanlı açılır; gerekirse yayın hakemliği süresince kısa bir ambargo uygulanabilir.

## 6. Sorumluluklar ve Kaynaklar

- **Genel sorumluluk / veri yönetimi:** Yürütücü Prof. Dr. Murat Ceylan.
- **Veri kalitesi ve doğrulama protokolü:** Prof. Dr. Servet Gülüm Şumnu (nihai tahkim) ve gıda mühendisliği bursiyerleri.
- **Altyapı, depolama ve yedekleme:** Dr. Engin Esme ve yazılım/yapay zekâ bursiyerleri.
- **Kaynaklar:** Veri yönetimi maliyetleri proje kapsamındaki donanım (NAS, iş istasyonu), TRUBA tahsisi ve kurum altyapısı ile karşılanır; ayrıca bir maliyet öngörülmemektedir.

## 7. Teyit Edilecek Hususlar

1. Açık veri/kod için kesin lisanslar (CC BY 4.0 ve açık kaynak lisansı) kurum/TTO politikasıyla teyit edilecektir.
2. Veri setinin barındırılacağı kalıcı arşiv/DOI sağlayıcısı (ör. kurum deposu, Zenodo) belirlenecektir.
3. EKUAL/kurumsal lisansların TDM kapsamı ilgili birimle netleştirilecektir.
4. TÜBİTAK güncel Veri Yönetim Planı şablonunun zorunlu alanları, başvuru anındaki resmi forma göre son haline getirilecektir.

# Defteri okumadan bilmeniz gerekenler

## Ne hazırlandı?

Türkçe **30 günlük, her gün bir sayfalık** staj defteri taslağı hazırlandı.
Kapak ve bilgi sayfasıyla toplam **32 sayfa** oldu. Düzenlenebilir Word dosyası
ve aynı içeriğin PDF çıktısı birlikte bulunuyor:

- [Word dosyası](OpenNutri_Staj_Defteri_30_Gun.docx)
- [PDF dosyası](OpenNutri_Staj_Defteri_30_Gun.pdf)

Başlık: **OpenNutri — Sesli Besin Kaydı ve Beslenme Takibi Mobil Uygulaması**.
Bitirme projesi olarak çerçevelenmedi. Özel konuşmalar, siyasi görüşler, bilimsel
makale toplama sistemi ve etiketleme paneli anlatıya eklenmedi.

## İçinde ne anlatılıyor?

| Günler | Ana konu |
| --- | --- |
| 1–5 | İhtiyaçlar, Flutter/Dart, mimari, ekranlar ve veri modelleri |
| 6–10 | Besin arama, asenkron yanıtlar, kaynak ayrıntısı, miktar hesabı ve yerel saklama |
| 11–15 | Hızlı kayıt, geri alma, güvenli düzenleme, günlük toplamlar, besin raporu ve hedefler |
| 16–21 | Mikrofon, WAV dosyası, sessizlikte durdurma, API bağlantısı, besin eşleştirme ve hata yönetimi |
| 22–24 | Android araç takımı, ana ekrana ekleme, kayıttan sonra kapanış ve beslenme şablonları |
| 25–28 | Günlük öneri, yazılı/sesli koç, kayıtlı tercihler, Oracle ve kullanıcı izinleri |
| 29–30 | Otomatik testler, Android paketi ve teslim değerlendirmesi |

Her gün üç açıklayıcı paragraftan oluşuyor. Teknik terimler, ne işe yaradıklarıyla
birlikte anlatıldı. İki sayfada küçük açıklayıcı tablolar var. Sahte ekran
görüntüsü, kurum logosu, imza, mühür veya toplantı anlatısı kullanılmadı.

## Örneklerle ne kadar benziyor?

Büşra'nın PDF'si 30 günlük içerik ve iki ön sayfayla **32 sayfa**. Başlık/alt bilgi
dahil günlük sayfalarda toplam yaklaşık **5.667 kelime** var. Hazırlanan defterin
yalnızca günlük gövde metni **5.009 kelime**, aynı şekilde başlık ve alt bilgilerle
yaklaşık **5.824 kelime**: toplam uzunluk oldukça yakın.

Word örneği 40 günlük, daha kısa anlatımlı bir dosya. LibreOffice ile kontrol
çıktısında 43 sayfaya yayılıyor. Bu örnekten günlük konu başlığını; PDF örneğinden
30 gün, sayfa çerçevesi, kurum başlığı ve tarih/onay altlığı düzenini aldık.
Örneklerin kişisel bilgileri ve metinleri kopyalanmadı.

## Neleri henüz doldurmak gerekiyor?

Üniversite/fakülte/bölüm, öğrenci adı ve numarası, kurum/adres, sorumlu kişi/unvanı,
başlangıç-bitiş ve günlük tarihler köşeli parantezli yer tutucular olarak bırakıldı.
İmza ve mühür alanları boş. Kurumun resmî formu varsa ilk iki sayfa onunla
değiştirilebilir; 30 günlük metin kullanılmaya devam edebilir.

**Gün sırası önerilen bir anlatım sırasıdır.** Gerçek çalışma günlerine ve öğrencinin
katkısına göre eşleştirilmelidir. Başka birinin hazırladığı bölümü öğrenci yalnızca
incelediyse veya uygulamaya bağladıysa, kendi yazmış gibi değiştirilmemelidir.
Takım çalışması ve yapay zekâ desteği açısından kurumun bildirim beklentisi de
kontrol edilmelidir. Mevcut teknik özellikler belgelenebilir; kişinin devam süresi
ve görev dağılımı yalnızca koddan belirlenemez.

Bilgileri tek yerden doldurmak için [bilgiler.json](bilgiler.json) dosyası var.
Elle Word düzenlemek de mümkün; ancak yeniden üretim elle yapılan değişiklikleri
ezer. Kalıcı metin değişiklikleri [gunlukler.md](gunlukler.md) üzerinden yapılmalıdır.

## Sunumda söylenecek en kısa doğru açıklama

“OpenNutri, besinleri arayarak veya sesle günlüğe eklemeyi sağlayan Android
uygulamasıdır. Besin değerlerini mevcut kaynak servisinden alır, kayıtları telefonda
tutar ve miktara göre günlük toplamları hesaplar. Kullanıcı kayıtları düzeltebilir;
isterse hedeflerine göre yapay zekâ önerileri alabilir. Ana ekran mikrofon araç
takımı kayıt ekranına kısa yoldan ulaşmayı sağlar.”

Bilmeniz gereken üç sınır:

- Oracle öneri sunar; kesin olarak en iyi beslenmeyi hesaplayan bir optimizasyon sistemi değildir.
- Araç takımı kaydetme bitene kadar görünür ekranı kullanır; kapatınca işi garantiyle sürdüren arka plan kuyruğu yoktur.
- Günlük telefonda tutulur; kullanıcıya açık bulut eşitleme veya yedekleme özelliği henüz yoktur.

## Ne kontrol edildi?

14 Eylül 2026'da uygulamanın statik analizi temiz çıktı ve **44 Flutter testi geçti**.
Word/PDF üretiminde 32 sayfa, 01–30 sıralaması, her günün kendi sayfasında kalması,
bütün kaynak paragrafların PDF'ye eksiksiz geçmesi ve Türkçe karakterler kontrol
edildi. Telefon kullanılmadı; uygulama veya canlı servis değiştirilmedi.

Teknik dayanakların günlere göre listesi [KANIT_HARITASI.md](KANIT_HARITASI.md)
dosyasında. Bu liste defterin basılı 32 sayfasına dahil değildir.

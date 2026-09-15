# Defteri okumadan bilmeniz gerekenler

## Hazır olan dosyalar

Türkçe **30 günlük, her gün bir sayfalık** çalışma metni hazırlandı. Kapak ve
bilgi sayfasıyla toplam **32 sayfa**. Ana anlatım **12 punto**, 6.404 kelime;
günler 195–233 kelime ve 3–5 paragraf uzunluğunda.

- [Düzenlenebilir Word](OpenNutri_Staj_Defteri_30_Gun.docx)
- [Aynı içeriğin PDF'si](OpenNutri_Staj_Defteri_30_Gun.pdf)
- [15 ekran görüntüsü için çekim ve ekleme rehberi](EKRAN_GORUNTUSU_REHBERI.md)

Başlık: **OpenNutri — Sesli Besin Kaydı ve Beslenme Takibi Mobil Uygulaması**.
Yalnızca mobil uygulama ve kullandığı servislerle entegrasyon anlatılıyor.
Bitirme projesi çerçevesi, araştırma/etiketleme işleri ve özel konuşmalar eklenmedi.

## İçerik sırası

| Günler | Ana konu |
| --- | --- |
| 1–5 | İhtiyaçlar, Flutter/Dart, mimari, ekranlar ve veri modelleri |
| 6–10 | Besin arama, geciken yanıtlar, kaynak ayrıntısı, miktar hesabı ve yerel saklama |
| 11–15 | Hızlı kayıt, geri alma, güvenli düzenleme, toplamlar, besin raporu ve hedefler |
| 16–21 | Mikrofon, WAV, sessizlikte durdurma, API, besin eşleştirme ve hata yönetimi |
| 22–24 | Android araç takımı, ana ekrana ekleme, kayıt sonrası dönüş ve diyet şablonları |
| 25–28 | Günlük öneri, yazılı/sesli koç, kayıtlı tercihler, Oracle ve izinler |
| 29–30 | Otomatik testler, Android paketi ve genel değerlendirme |

Her gün, yapılan işin yanında nasıl uygulandığını, örnek hesabı veya testi ve
öğrenilen noktayı anlatıyor. Kod adları kullanılıyor ama işlevleri de açıklanıyor.
İki küçük teknik tablo ve ilgili günlerde toplam 15 ekran görüntüsü alanı var.

## Son düzeltmede ne değişti?

- **Düzenleme açıklaması düzeltildi:** pencereyi açmak veya iptal etmek eski kaydı
  değiştirmiyor. Kaydetme başlatılınca bellek/arayüz hemen güncelleniyor; disk
  yazması sırayla yapılıyor. Başarı bildirimi bundan sonra veriliyor. Başarısız
  yazma, o değişiklik hâlâ güncelse son saklanan duruma dönüyor.
- **Makro hesabı netleştirildi:** toplam kalori önce protein/karbonhidrat/yağ
  enerji paylarıyla çarpılıyor, ardından 4/4/9'a bölünerek gram bulunuyor.
- “Bu belge hazırlanırken telefon kurulmadı” gibi defter yazım süreciyle ilgili
  notlar günlüklerden çıkarıldı. Teknik çalışma ve kazanımlar öne alındı.
  Gerçek test/denetim tarihleri ayrı kanıt haritasında korundu.
- Büşra gibi “Bugün” ile başlayan kişisel anlatım korundu. Onun örneğinde
  30 günün 27'si “Bugün/Bugünkü” ile başlıyor; buna karşılık “Gün sonunda”
  yalnız bir kez geçiyor. Bizdeki 23 aynı sonuç kalıbı doğal, konuya özgü
  bitişlerle değiştirildi; paragraf sayıları da gerektiği yerde çeşitlendirildi.
- 14 dikey telefon görüntüsü ve bir yatay test çıktısı için numaralı, açıklamalı
  kutular eklendi. Gerçek görüntüleri siz yerleştireceksiniz.

Detaylar korunuyor: 350 ms arama beklemesi, geç gelen yanıtın elenmesi,
182 g için 94,64 kcal, 500 g satın alınan ağırlıktan 335 g yenilebilir kısım,
karma kaynakta 132 kcal toplam, sıralı saklama, mikrofon eşikleri, Android–Flutter
iletişimi ve önbellek kontrolleri. Sayısal örnekler kontrollü test verileridir.

## Büşra ve diğer örnekle karşılaştırma

Büşra'nın defteri de iki ön sayfa ve 30 günlük sayfayla **32 sayfa**.
Günlük sayfaları başlık/altlık dahil yaklaşık **5.667 kelime**. Bizde görüntü
yer tutucularının yazıları hariç aynı tür toplam **7.219 kelime**: yaklaşık
**%27 daha fazla**. Yer tutucu yazıları dahil toplam 7.415 kelime.
İlk taslağın 5.009 kelimelik gövdesinden yaklaşık %28 daha ayrıntılı.

Sayfa çerçevesi, kurum/sayfa başlığı, günlük konu başlığı ve tarih/onay/imza
altlığı örneklere benziyor. Diğer Word örneği 40 günlük ve daha kısa anlatımlı;
LibreOffice'te 43 sayfaya yayılıyor. Metinleri, kişisel bilgileri veya imzaları
kopyalanmadı. Kelime sayıları çalışma süresini ölçmek için değil, belge
yoğunluğunu karşılaştırmak içindir.

## Sizin tamamlayacağınız işler

1. Üniversite/fakülte/bölüm, öğrenci adı-numarası, kurum-adres, sorumlu kişi-unvanı
   ve gerçek tarihleri doldurun. İmza ve mühür ilgili yetkiliye bırakıldı.
2. Gün sırasını ve “yaptım/geliştirdim” anlatımını öğrencinin gerçek katkısıyla
   eşleştirin. Yalnız incelenen veya entegre edilen bölüm buna göre anlatılmalı.
   Bilgi sayfasında taslak ve yapay zekâ desteği açıklaması bulunuyor.
3. [Çekim rehberine](EKRAN_GORUNTUSU_REHBERI.md) göre 15 görüntüyü ekleyin.
   Rehber her şeklin gününü, PDF sayfasını, ekranını ve resim boyutunu veriyor.
4. Son Word kopyasından PDF üretip 32 sayfanın ve tarih/imza alanlarının
   korunduğunu kontrol edin. Resimli, kişisel bilgili kopyayı repo dışında saklayın.

Bilgilerin kaynak dosyası [bilgiler.json](bilgiler.json), metnin kaynağı
[gunlukler.md](gunlukler.md). Word'ü elle düzenlemek mümkün; fakat üretim
betiğini yeniden çalıştırmak ana Word/PDF dosyasındaki elle yapılan değişiklikleri
ezer. Resimli son kopyayı ayrı kaydetmek bu yüzden önemli.

## Teknik doğruluk için bilinmesi gerekenler

Oracle, günlük ve hedeflere göre besin fikirleri sunup Core aramasına bağlanır.
Araç takımı görünür kayıt ekranını açar ve saklama tamamlanınca ana ekrana döner.
Günlük ve tercihler telefonda tutulur. Bu özellikler sunumda da bu şekilde
anlatılmalı; matematiksel optimum, garantili arka plan kuyruğu veya bulut
eşitleme olarak tanıtılmamalı.

14 Eylül 2026 doğrulamasında temiz statik analiz ve **44 başarılı Flutter testi**
kaydedildi. Son belge revizyonunda sayfa sayısı, bütün kaynak paragrafları,
günlük sırası, 15 şeklin doğru sayfada olması, 12 punto ana anlatım ve basılabilir
alan sınırları kontrol edildi. Belge üretimi için ayrıca regresyon testleri var.

Günlere göre kod/test dayanakları [KANIT_HARITASI.md](KANIT_HARITASI.md) içinde.
Kanıt haritası ve bu özet, basılacak 32 sayfanın dışında tutuluyor.

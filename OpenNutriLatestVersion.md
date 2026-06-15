# 1. ULUSAL KAZANIM ve PROJENİN ÖNEMİ

## Güncel Problem ve İhtiyaç

Güncel ve güvenilir veriler içeren bir besin veri tabanı, diyet alımlarının doğru hesaplanması için kritik önem arz etmektedir (Schakel ve diğerleri, 1988). Çoğu besin veri tabanı, USDA ve EFSA gibi güvenilir kurumlardan alınan verilerle ve uzman kürasyonu ile hazırlanmakta; bu süreç, bilimsel literatürdeki verilerin hızla artmasına rağmen hâlâ büyük ölçüde manuel yürütülmektedir. Sınırlı kaynaklar nedeniyle küresel kurumlar yaygın ürünlere öncelik vermekte; Türkçe literatürde, yerel tarım ürünlerinde ve bölgesel gıdalarda üretilen bilimsel veri uluslararası besin veri altyapılarına yeterince yansımamaktadır.

Bu durum Türkiye için dört somut kayıp üretmektedir:

- Türkiye'nin bilimsel araştırmaları yapılandırılmamış PDF arşivlerinde kalmakta; küresel standart belirleyici kurumlar için erişilebilir ve yeniden kullanılabilir hale gelememektedir.

- Türkiye'nin ulusal veri tabanı TürKomp, 500'den fazla gıdaya ait yaklaşık 63.000 bileşen verisiyle kritik ve yüksek kaliteli bir temel oluşturmuş (TÜBİTAK MAM Gıda Enstitüsü, KAMAG 1007), ancak kuruluşundan bu yana sistematik ve büyük ölçekli bir genişlemeye tabi tutulmamıştır. Manuel laboratuvar analizine dayanan bu yaklaşımın, ülkenin geniş tarımsal ve kültürel gıda çeşitliliğini kapsayacak biçimde ölçeklendirilmesi yüksek maliyetlidir.

- Türk kurumları, sağlık teknolojisi girişimleri ve araştırmacılar, yabancı veri tabanlarına erişmek için lisanslama veya abonelik maliyetleriyle karşılaşmakta; bu da yerel gıdaları eksik temsil eden altyapılara bağımlılık yaratmaktadır.

- Türk gıda ihracatçıları, AB etiketleme ve ürün belgelendirme süreçlerinde yerel ürünü temsil eden, kaynaklı ve doğrulanmış besin verisine sınırlı erişmektedir.

Akademik literatürde yer alan birçok belirgin Türk gıdası, hem USDA hem de EFSA veri tabanlarında bulunmamaktadır; proje bu açığı kapatmak üzere tasarlanmıştır (Bölüm 4.6.3).

## Çözüm: OpenNutri

OpenNutri, bilimsel yayınlardan gıda bileşimi verisi çıkaran, doğrulayan ve standartlaştıran **Aşamalı Olarak Otonom Veri Doğrulama Sistemi** olarak önerilmektedir. Manuel veri girişine dayanan mevcut sistemlerden farklı olarak OpenNutri; yapay zekâ tabanlı veri çıkarımı, gıda bilimi temelli mantıksal doğrulama kuralları ve uzman geri bildirimiyle öğrenen bir **Hibrit Zeka** işlem hattını birleştirir. Amaç, Türkiye'nin gıda bileşimi bilgisini yalnızca arşivleyen değil, kaynak yayına kadar izlenebilir biçimde sürekli genişleten ve zamanla daha düşük maliyetle çalışan ulusal bir veri altyapısı oluşturmaktır.

## Sektörel Ulusal Kazanımlar

### 1.1. Gıda İhracatçıları: AB Etiketleme Uyumu İçin Güvenilir Referans Veri

Türk ihracatçıları, ürün bazında besin değerlerini kanıtlamak için çoğu zaman pahalı özel laboratuvar analizlerine veya yerel ürünü yeterince temsil etmeyen yabancı veri tabanlarına başvurmak zorunda kalmaktadır. AB Yönetmeliği 1169/2011, beslenme beyanı değerlerinin analiz yanında kabul görmüş ve yerleşik verilerden hesaplanmasına da imkân tanıdığı için, kaynaklı ve doğrulanmış bir ulusal veri altyapısı ihracatçıların teknik dosya hazırlama, ön değerlendirme ve ürün formülasyonu süreçlerinde doğrudan maliyet azaltıcı rol oynayabilir.

OpenNutri, Antep fıstığı, yerel buğday çeşitleri, geleneksel ürünler ve bölgesel gıdalar gibi Türk ürünleri için DOI ile kaynaklandırılmış, denetlenebilir bir referans standardı sağlayarak laboratuvar analizinin zorunlu olduğu durumların yerine geçmeyi değil, analiz ihtiyacını azaltabilecek ve belgelendirme kalitesini yükseltecek karar süreçlerini hedefler. Böylece ihracatçılar, yabancı veri tabanlarına bağımlı genel tahminler yerine yerel ürüne ait bilimsel kanıtla çalışabilir.

**Kazanım:** Türk ürünleri için kaynak gösterilebilir, doğrulanmış ve düzenleyici uyum süreçlerinde kullanılabilecek ulusal referans veri.

**Etki:** Etiketleme, ürün geliştirme ve ihracat teknik dosyalarında yabancı veri tabanı bağımlılığını azaltarak maliyet ve zaman avantajı.

### 1.2. Dijital Ekosistem: Sağlık Teknolojileri İçin Ulusal Veri Altyapısı

Türk sağlık teknolojisi girişimleri ve beslenme uzmanları, yerel gıdaları doğru temsil eden veri eksikliği nedeniyle sınırlanmaktadır. Küresel veri tabanları kapsam, lisans maliyeti veya yerel gıda çeşitliliği açısından yeterli değildir; simit, lahmacun, yöresel yemekler, yerel bakliyat ve tahıl çeşitleri gibi ürünler çoğu zaman ya eksiktir ya da yabancı muadillerle temsil edilir.

**Kazanım:** Yerli geliştiricilerin kullanabileceği, API ile erişilebilen ve Türk diyet örüntüsüne uygun ulusal besin veri altyapısı.

**Etki:** Beslenme takibi, klinik karar destek, kişiselleştirilmiş diyet ve gıda teknolojisi uygulamalarında yerel doğruluğu artırarak yerli ürünlerin rekabet gücünü yükseltme.

### 1.3. Halk Sağlığı: Kanıta Dayalı Beslenme Politikası

Obezite, diyabet ve hipertansiyon gibi bulaşıcı olmayan hastalıklara karşı etkili politika geliştirmek için Türk gıdalarının gerçek besin bileşiminin bilinmesi gerekir. Mevcut durumda bu bilgi, binlerce yapılandırılmamış makale, rapor ve PDF içinde dağınık biçimde bulunmaktadır.

**Kazanım:** Yayımlanmış bilimsel araştırmalara dayanan, Türk gıdaları için kapsamlı ve doğrulanmış besin bileşimi referansı.

**Etki:** Beslenme rehberleri, okul beslenme programları ve bölgesel halk sağlığı müdahalelerinde yabancı ortalamalar yerine yerel bileşim verisine dayalı karar alma.

### 1.4. Araştırmacılar: Türk Bilimini Küresel Standartlara Görünür Kılma

Türk gıda bilimi araştırmacıları çok sayıda çalışma yayımlamakta, ancak bu yayınlardaki bileşim verileri uluslararası veri tabanları tarafından çoğu zaman indekslenmemektedir. OpenNutri, her kaydı DOI, sayfa, tablo ve kaynak alıntısıyla ilişkilendirerek Türk araştırmalarının bulunabilirliğini ve yeniden kullanılabilirliğini artırır.

**Kazanım:** Türkçe ve İngilizce yerel literatürdeki gıda bileşimi bulgularının makine tarafından okunabilir, kaynaklı ve standartlaştırılmış hale getirilmesi.

**Etki:** Türk araştırmalarının ulusal ve uluslararası veri kullanımlarında görünürlüğünün, atıf potansiyelinin ve bilimsel etkisinin artması.

### 1.5. Ekonomik Dönüşüm: Veri İthalatçılığından Veri İhracatçılığına

Türkiye bugün yapılandırılmış besin verisi için büyük ölçüde yabancı veri altyapılarına bağımlıdır. OpenNutri bu ilişkiyi tersine çevirmeyi hedefler: doğrulanmış gıda bileşimi veri tabanı sağlık teknolojisi, gıda sanayi ve araştırma kuruluşlarına sunulabilir; kademeli doğrulama motoru ise kendi gıda veri altyapısını dijitalleştirmek isteyen ülke veya kurumlara uyarlanabilir bir teknoloji olarak lisanslanabilir.

**Kazanım:** Türkiye'nin yalnızca veri kullanan değil, doğrulanmış gıda verisi ve veri çıkarma altyapısı üreten bir ülkeye dönüşmesi.

**Etki:** API abonelikleri, veri tabanı lisansları ve doğrulama motoru uyarlamalarıyla bilgi ihracatına dayalı yeni bir ekonomik değer alanı.

\newpage

# 2. AMAÇ VE HEDEFLER

## 2.1. Projenin Amacı

Bu projenin amacı, Türkiye'nin bağımsız ve sürdürülebilir gıda bileşimi veri altyapısını oluşturmak üzere **OpenNutri** sistemini geliştirmektir. OpenNutri; yapay zekâ destekli veri çıkarımı, gıda bilimi doğrulama kuralları ve uzman geri bildirimiyle öğrenen kademeli bir mimari kullanarak bilimsel literatürdeki besin bileşimi verilerini otomatik biçimde çıkarır, doğrular ve uluslararası standartlara göre yapılandırır. Proje sonunda doğrulanmış bir besin veri tabanı, üretim ortamında çalışan REST API, açık araştırma veri seti ve farklı kurumlara uyarlanabilir bir veri çıkarma/doğrulama motoru ortaya çıkacaktır.

Proje sıfırdan başlamamaktadır. Bölüm 4.6'da özetlenen prototip hâlihazırda çok kaynaklı literatür tarama, model kademesi, normalizasyon, uzman doğrulama arayüzü ve zamanlanmış otomasyon bileşenleriyle çalışmaktadır. Destek, bu prototipi ulusal ölçekte kullanılabilecek, maliyeti düşen ve uzman doğrulamasıyla kendini iyileştiren bir altyapıya dönüştürmek için kullanılacaktır.

## 2.2. Ölçülebilir Hedefler

### Hedef 1: Hibrit Zeka Veri Çıkarma Motorunu Geliştirmek

Bilimsel makaleleri girdi olarak alan, yapılandırılmış ve doğrulanmış gıda-besin kayıtları üreten uçtan uca bir yapay zekâ işlem hattı geliştirilecektir. Sistem; ince ayarlanmış açık ağırlıklı modelleri, gerektiğinde ticari model desteğini, geri getirmeyle güçlendirilmiş üretimi (RAG), gıda bilimi doğrulama kurallarını ve kaynak izlenebilirliğini birlikte kullanacaktır.

**Başarı ölçütleri:**

| Ölçüt | Referans / Başlangıç | Hedef |
| --- | --- | --- |
| Otomatik onay doğruluğu | Doğrulama hattı olmayan tek model yaklaşımı | Başlangıç sisteminde ≥%95; proje sonunda ≥%99,5 |
| Otomatik onay oranı | Güven puanlaması yok | Başlangıçta ≥%60; proje sonunda ≥%90 |
| Veri tabanı hata oranı | Sistematik denetim yok | Tüm kabul edilen kayıtlar için <%0,5 |
| Makale başına işlem maliyeti | Lider ticari LLM tekil kullanımı | Başlangıçta <$0,03; proje sonunda <$0,01 |

Referans değerler, doğrulama hattı olmadan uygulanan lider genel amaçlı ticari LLM yaklaşımını temsil eder. Nihai kıyaslama, değerlendirme tarihinde mevcut en güçlü ticari ve açık ağırlıklı modellerle yapılacaktır.

### Hedef 2: Büyük Ölçekli Bilimsel Literatürü İşlemek

Europe PMC/PubMed Central, OpenAlex, Semantic Scholar, Crossref, DergiPark ve EKUAL kapsamındaki kurumsal erişim kaynakları kullanılarak İngilizce ve Türkçe gıda bileşimi literatürü keşfedilecek, filtrelenecek ve işlenecektir. Google Scholar yalnızca yasal/kurumsal arama ve doğrulama bağlamında yardımcı keşif kaynağı olarak değerlendirilecek; resmi API bulunmadığı için temel otomasyon kaynağı olarak konumlandırılmayacaktır.

**Başarı ölçütleri:**

- Küresel ve ulusal bilimsel kaynaklardan en az 100.000 ilgili makaleyi işlemek.

- İşlenen literatürden en az 500.000 standartlaştırılmış gıda-besin kaydı çıkarmak (ilgili makale başına ortalama ~5 kayıt varsayımıyla).

- Uluslararası veri tabanlarında yeterince temsil edilmeyen en az 5.000 özgün Türk gıda ürünü veya yerel ürün varyantını indekslemek.

### Hedef 3: Uzmanlar Tarafından Doğrulanmış Altın Standart Veri Tabanı Oluşturmak

Sistematik uzman doğrulaması ile hem projenin temel ürünü olacak hem de model iyileştirme için kullanılacak yüksek kaliteli, kaynaklı ve denetlenebilir bir veri tabanı oluşturulacaktır.

**Başarı ölçütleri:**

- Amaca yönelik doğrulama arayüzüyle en az 5.000 makalenin uzman incelemesini tamamlamak.

- Uzman doğrulamasıyla en az 25.000 altın standart gıda-besin kaydı üretmek.

- Kaynak metinde mevcut olduğunda uluslararası standartlarca izlenen 181'e kadar temel besin bileşenini kapsamak.

- Nihai veri tabanı hata oranını periyodik rastgele denetimlerle <%0,5 düzeyinde tutmak.

### Hedef 4: Uzman Geri Bildirimiyle Modelleri İyileştirmek

Uzman düzeltmeleri; denetimli ince ayar, tercih temelli öğrenme/RLHF ve hata örüntüsü analizi için yapılandırılmış eğitim sinyali olarak kullanılacaktır. Böylece üst katmanlarda çözülen örnekler alt katmanları geliştirecek, sistem zamanla daha fazla makaleyi daha ucuz katmanlarda güvenle tamamlayacaktır.

**Başarı ölçütleri:**

| Ölçüt | Başlangıç | Nihai Hedef |
| --- | --- | --- |
| Otomatik onay doğruluğu | ~%95 | ≥%99,5 |
| Otomatik onay oranı | ~%60 | ≥%90 |
| Veri tabanı hata oranı | <%0,5 | <%0,5 |
| Makale başına maliyet | <$0,03 | <$0,01 |

**Otomatik onay doğruluğu**, sistemin insan incelemesi olmadan kabul ettiği kayıtların periyodik rastgele denetimde doğru bulunma oranıdır. **Otomatik onay oranı**, insan incelemesine gitmeden tamamlanan makale oranıdır. <%0,5 veri tabanı hata hedefi, hem otomatik onaylanan hem de insan tarafından doğrulanan kayıtlar için geçerli katı kalite kısıtıdır.

### Hedef 5: Sistemi Yayına Almak ve Bilimsel Yayılımı Sağlamak

OpenNutri altyapısı araştırma ve ürünleşme kullanımına açılacak; metodoloji, veri seti ve performans sonuçları bilimsel yayınlarla doğrulanacaktır.

**Başarı ölçütleri:**

- Üretim REST API'sini <200 ms hedef yanıt süresi ve ≥100 eş zamanlı istek/saniye kapasitesiyle devreye almak.

- Geliştirici dokümantasyonu ve SDK yayımlamak.

- Ücretsiz akademik erişim ve ticari kullanım/entegrasyon lisansından oluşan çift erişim modelini uygulamak.

- Açık araştırma veri setini tam dokümantasyonla yayımlamak.

- Sistem performans karşılaştırma raporunu yayımlamak (doğruluk, maliyet, hız; ticari ve açık ağırlıklı model referanslarıyla karşılaştırma).

- En az 3 hakemli akademik yayını değerlendirmeye göndermek.

## 2.3. Hedefler Özet Tablosu

| No. | Hedef | Ana Başarı Ölçütleri |
| --- | --- | --- |
| 1 | Hibrit Zeka Motoru | Başlangıçta ≥%95, nihai sistemde ≥%99,5 otomatik onay doğruluğu; makale başına maliyette lider ticari tekil modele göre ≥%90 düşüş |
| 2 | Literatür İşleme | ≥100.000 ilgili makale; ≥500.000 gıda-besin kaydı; ≥5.000 özgün Türk gıda ürünü/varyantı |
| 3 | Altın Standart Veri Tabanı | ≥5.000 uzman doğrulamalı makale; ≥25.000 altın standart kayıt; <%0,5 hata |
| 4 | Uzman Geri Bildirimli Öğrenme | ≥%90 otomatik onay oranı; <$0,01/makale işlem maliyeti |
| 5 | Dağıtım ve Yayılım | API, SDK ve dokümantasyon yayında; açık araştırma veri seti; performans kıyaslaması; ≥3 yayın başvurusu |

\newpage

# 3. PATENT, FAYDALI MODEL, TESCİL TARAMASI, YENİLİKÇİ YÖNÜ VE TİCARİLEŞME POTANSİYELİ

## 3.1. Patent, Faydalı Model ve Tescil Ön Taraması

Proje kapsamı için TURKPATENT, Espacenet ve Google Patents üzerinde Türkçe ve İngilizce anahtar kelimelerle ön tarama yapılmıştır. Kullanılan örnek terimler şunlardır: “gıda kompozisyon veri tabanı”, “besin değeri yapay zeka”, “otomatik gıda analizi”, “food composition database artificial intelligence”, “nutritional data extraction NLP”, “cascade model LLM routing”, “food ontology automated construction”.

Bu ön taramada, OpenNutri'nin önerdiği bütünleşik yapıyla doğrudan örtüşen bir patent, faydalı model veya tescil bulunmamıştır. TürKomp, TÜBİTAK KAMAG 1007 kapsamında geliştirilmiş ulusal bir gıda kompozisyon veri tabanıdır; OpenNutri ise laboratuvar temelli tekil veri üretiminden farklı olarak bilimsel literatürden otomatik çıkarım, çok katmanlı doğrulama, uzman geri bildirimi ve öğrenilmiş yönlendirme mimarisini hedeflemektedir.

Nihai başvuru ve ürünleşme aşamasında bu ön taramanın Teknoloji Transfer Ofisi ve/veya patent vekili tarafından güncellenmesi planlanmaktadır. Bu ifade, hukuki “freedom-to-operate” görüşünün yerine geçmez; proje düzeyinde yenilik ve ihlal riski ön değerlendirmesidir.

| Patent / Sistem | Kapsam | OpenNutri ile Farkı |
| --- | --- | --- |
| US20190295440A1 | Web verileri, gıda ontolojisi, sağlık önerileri ve kişiselleştirilmiş tavsiyeler. | Tüketici tavsiye platformudur; bilimsel literatürden DOI kaynaklı 100 g bazlı bileşim verisi çıkarmaz, gıda bilimi doğrulama kademesi ve uzman geri bildirimli öğrenme içermez. |
| US9286290B2, CN110532834A, WO2025107898A1 | Genel belge/tablo çıkarma ve düzen analizi. | Alan bağımsız tablo çıkarma araçlarıdır; besin bileşimi standardizasyonu, fiziko-kimyasal doğrulama, maliyet optimizasyonlu model yönlendirme ve kaynak düzeyinde besin kaydı üretimi içermez. |
| FoodMine (Hooton vd., 2020) | PubMed üzerinden gıdaların kimyasal bileşenlerini arayan akademik NLP sistemi. | Flavonoid/fenolik gibi kimyasal bileşikleri hedefler; standart besin bileşimi değerlerini (enerji, makro besinler, vitaminler, mineraller/100 g) doğrulanmış veri tabanına dönüştürmez. Tek modelli ve pilot ölçeklidir. |
| P-NUT / gıda bilgi grafiği çalışmaları (Ispirova vd., 2020; Cenikj vd., 2023) | Kısa metin açıklamalarından besin içeriği tahmini veya gıda/biyomedikal bilgi grafikleri. | Ölçülmüş bileşim değerlerini kaynağıyla çıkarmaz; tahmin veya ilişki grafiği üretir. OpenNutri'nin hedefi kaynaklı, denetlenebilir ve standardize edilmiş gıda-besin kayıtlarıdır. |
| Ticari veri tabanları (Edamam, FatSecret, Nutritionix vb.) | Lisanslı veri, kitle kaynaklı veri, etiket/tarif ayrıştırma ve API hizmetleri. | Bilimsel literatürden yeni gıda bileşimi verisi üretmez; çok katmanlı doğrulama ve uzman geri bildirimli model iyileştirme mimarisi sunmaz. |

## 3.2. Projenin Yenilikçi Yönleri

OpenNutri'nin yeniliği tek bir algoritmadan değil, gıda bileşimi veri altyapısı için uçtan uca çalışan ve zamanla maliyeti düşen bir sistem mimarisinden kaynaklanmaktadır. Mevcut kamu, akademik ve ticari çözümler bu bileşenleri birlikte sunmamaktadır.

| No. | Yenilik | Nedir? | Neden Yeni? |
| --- | --- | --- | --- |
| 1 | Bilimsel literatürden aşamalı olarak otonom veri çıkarma | Bilimsel makalelerden uluslararası standartlara uygun, 100 g bazlı ve kaynaklı gıda-besin kayıtları üretir. | Mevcut veri tabanları çoğunlukla manuel laboratuvar analizi ve uzman kürasyonuna dayanır; literatürdeki dağınık veriyi ulusal ölçekte otomatik veri tabanına dönüştürmez. |
| 2 | Kademeli Hibrit Zeka mimarisi (L1-L5) | Tarama, filtreleme, açık ağırlıklı çıkarım, ticari model yükseltme ve uzman doğrulamasını maliyet/kalite dengesiyle birleştirir. | Tek model yaklaşımlarından farklı olarak hem maliyet optimizasyonu hem de çok katmanlı doğrulama sağlar. |
| 3 | Öğrenilmiş Yönlendirici | Belge ve alt görev özelliklerine göre en ucuz yeterli katmanı seçen eğitilebilir karar mekanizmasıdır. | Statik eşiklere dayalı kademelerin yerine, proje boyunca doğrulama sonuçlarından öğrenen bir rota optimizasyonu kullanır. |
| 4 | Uzman geri bildirimiyle katmanlar arası öğrenme | L4/L5 çıktıları ve uzman düzeltmeleri L1-L3 modellerini yeniden eğiten yapılandırılmış sinyale dönüşür. | Doğrulamayı yalnızca kalite kontrol maliyeti olmaktan çıkarır; alt katmanların zaman içinde daha fazla görevi otomatik çözmesini sağlayan eğitim yatırımına dönüştürür. |
| 5 | Kayıt düzeyinde kaynak izlenebilirliği ve Türk gıdaları kapsamı | Her besin kaydı DOI, sayfa, tablo/satır ve çıkarım katmanı bilgisiyle saklanır; özellikle Türkçe literatür ve yerel gıdalar hedeflenir. | Mevcut veri tabanlarında kaynaklar çoğu zaman gıda maddesi veya veri seti düzeyindedir; OpenNutri kayıt düzeyinde makine tarafından okunabilir kaynak izi hedefler. |

Ek metodolojik yenilik olarak sistem, standart NLP metriklerinin ötesinde alana özgü doğrulama uygular: Atwater enerji-makro besin dengesi, 100 g kütle dengesi, fizyolojik referans aralıkları, birimler arası dönüşüm ve besinler arası tutarlılık. Bu kurallar, standart dil modeli güven puanını geçebilecek ancak gıda bilimi açısından imkânsız veya şüpheli değerleri yakalayan bağımsız bir kalite katmanı oluşturur.

## 3.3. Ticarileştirme Potansiyeli

OpenNutri, birbirinden bağımsız olarak ticarileştirilebilecek iki ana çıktı üretir:

| No. | Çıktı | Açıklama | Gelir Modeli |
| --- | --- | --- | --- |
| 1 | Gıda bileşimi veri tabanı ve API | 500.000'den fazla kaynaklı gıda-besin kaydı; Türk gıdaları ve uluslararası literatür kapsamı; düzenli güncellenen veri altyapısı. | Ücretsiz akademik erişim, ticari API aboneliği, veri lisansı ve kurumsal entegrasyon. |
| 2 | Kademeli Hibrit Zeka doğrulama motoru | Literatürden veri çıkarma, normalizasyon, doğrulama ve uzman geri bildirimi iş akışı. | Ülke/kurum/alan bazlı motor lisanslama, uyarlama ve dağıtım hizmetleri. |

**Doğrudan aynı kapsamda çalışan bir rakip tespit edilmemiştir.** Ticari gıda veri tabanları mevcut devlet verilerini, kitle kaynaklı kayıtları veya etiket/tarif ayrıştırmasını kullanır. Akademik sistemler ise genellikle tek görevli, pilot ölçekli veya tahmin odaklıdır. OpenNutri'nin ticari değeri, doğrulanmış veri üretimini ve veri üretme motorunu birlikte sunmasından kaynaklanır.

**Pazar büyümesi ve ihtiyaç:** Dijital sağlık platformları, beslenme uygulamaları, gıda ihracatı ve kişiselleştirilmiş diyet hizmetleri güvenilir besin verisine artan talep yaratmaktadır. FAO/INFOODS ulusal gıda bileşimi programlarını desteklese de birçok ülke manuel veri tabanı oluşturma için yeterli kaynağa sahip değildir. OpenNutri motoru, bu maliyeti düşüren ve yerel veriyi ulusal kontrol altında üreten bir altyapı olarak konumlanabilir.

## 3.4. Proje Sonrası Sürdürülebilirlik ve Olası Maliyet Hesabı

Hesaplama açısından yoğun aşamalar (model eğitimi, uzman doğrulaması, veri tabanı başlangıç ölçeklendirmesi) proje süresi içinde tamamlanacaktır. Proje sonrasında birincil çıkarım ve veri barındırma işlemleri hibe kapsamında edinilecek donanım ve kurum altyapısı üzerinde yürütülecek; bulut hizmetleri yalnızca yedekleme, dağıtım esnekliği ve felaket kurtarma için kullanılacaktır.

| Proje Sonrası Tekrarlayan Unsur | Tahmini Yıllık Maliyet |
| --- | --- |
| Bulut yedekleme (~3 TB) | ~6.000 TL |
| Yazılım araçları / izleme | ~2.000 TL |
| Ticari API yedekleme (L4, yeni makalelerin küçük bir bölümü) | ~1.000 TL |
| Alan adı, SSL, çeşitli | ~500 TL |
| Depolama genişletme (ek sürücüler) | ~3.000 TL |
| Toplam | **~12.500 TL/yıl** |

Güç, ağ ve fiziksel altyapı ev sahibi kurum tarafından sağlanacaktır. Ticari geçiş için ayrıntılı yol haritası Bölüm 6.3'te verilmiştir: pilot ortaklıklar, TÜBİTAK 1512 BiGG ve KOSGEB aracılığıyla spin-off şirket kurulumu, ardından TEYDEB 1507/1505 ile ölçeklendirme.

# 4. YÖNTEM

## 4.1. Araştırma Tasarımı ve Genel Yaklaşım

Proje, **Kademeli Hibrit Zeka İşlem Hattı** geliştirmektedir. Bu mimari, mevcut gıda bileşimi veri tabanlarının manuel uzman kürasyonuna dayalı yapısını ölçeklenebilir bir yapay zekâ + gıda bilimi + uzman doğrulama sistemine dönüştürür. Sistem beş işlem katmanından oluşur:

- **L1:** Çok kaynaklı literatür tarayıcısı ve keşif katmanı.

- **L2:** Hafif makale sınıflandırıcısı ve alaka filtreleme katmanı.

- **L3:** İnce ayarlanmış açık ağırlıklı çıkarım modelleri ve deterministik normalizasyon/doğrulama katmanı.

- **L4:** L3'ün güvenle çözemediği alt görevler için ticari model destekli yükseltme katmanı.

- **L5:** Uzman doğrulaması, düzeltme ve altın standart veri üretimi katmanı.

Bu katmanların üzerinde **Öğrenilmiş Yönlendirici** yer alır. Yönlendirici, her makale ve alt görev için doğru sonucu üretebilecek en düşük maliyetli katmanı seçer; doğrulama sonuçları geldikçe de çevrim içi biçimde güncellenir. Böylece proje yalnızca bir veri tabanı üretmez; aynı zamanda daha fazla veri gördükçe maliyeti azalan, doğruluğu artan ve uzman emeğini en öğretici örneklere yönlendiren bir sistem geliştirir.

Mimari dört yerleşik araştırma paradigmasını gıda bileşimi alanına özgü şekilde birleştirir:

| Paradigma | Temel Referanslar | OpenNutri'deki Rolü |
| --- | --- | --- |
| Kademeli sınıflandırıcılar | Viola ve Jones, 2001; Wang vd., 2011; Chen vd., 2023; Yue vd., 2024 | Girdileri giderek daha pahalı ve yetenekli katmanlara yalnızca gerektiğinde taşır. |
| Uzman karışımı / yönlendirme | Shazeer vd., 2017; Fedus vd., 2022 | Her alt görev için en uygun model veya kural bileşenini seçer. |
| Uzman geri bildirimli öğrenme | Ouyang vd., 2022 | Uzman düzeltmelerini model iyileştirme sinyaline dönüştürür. |
| Aktif öğrenme | Settles, 2012 | İnsan doğrulamasını en yüksek eğitim değeri taşıyan örneklere önceliklendirir. |

Yenilik, bu paradigmaların tekil kullanımında değil; her katmanın çıktısının alt katmanları sistematik olarak iyileştirdiği, gıda bilimi doğrulama kurallarının bağımsız kalite katmanı olarak çalıştığı ve yönlendirmenin statik eşiklerden öğrenilmiş maliyet/doğruluk kararlarına taşındığı bütünleşik mimaridedir.

```
                   ÖĞRENİLMİŞ YÖNLENDİRİCİ
         (makale/alt görev için en düşük maliyetli yeterli katmanı seçer)
                                  │
                                  ▼
 L1 Tarama ─► L2 Filtre ─► L3 Açık Ağırlıklı Çıkarım ─► L4 Ticari Model ─► L5 Uzman
    │             │                  │                         │              │
    └─────────────┴──────────────────┴─────────────────────────┴──────────────┘
                         doğrulama çıktıları ve düzeltmeler
                                  │
                                  ▼
             Kaynaklı üretim veri tabanı + altın standart eğitim verisi
```

## 4.2. Sistem Mimarisi: Katmanlar

### 4.2.1. Katman 1 — Akıllı Literatür Tarayıcısı (L1)

**Amaç:** Gıda bileşimi verisi içerme olasılığı yüksek bilimsel yayınları sistematik olarak keşfetmek.

**Yöntem:** Başlangıç sorgu seti, LanguaL, FoodOn (Dooley vd., 2018) ve MeSH terimleri gibi kontrollü sözlüklerden ve gıda mühendisliği alan uzmanlarının belirlediği örüntülerden oluşturulur. Tarayıcı, açık API ve kurumsal erişim kaynaklarından meta veri, özet ve mümkün olduğunda tam metin/PDF bağlantısı toplar. Etiketlenmiş sonuçlar, sorgu terimlerini ve kaynak önceliklerini zamanla iyileştiren alaka geri bildirim döngüsüne beslenir (hafif bir bandit yaklaşımı, Thompson örneklemesi; Chapelle & Li, 2011).

**Kaynak kapsamı:** Europe PMC/PubMed Central, OpenAlex, Semantic Scholar, Crossref, DergiPark ve EKUAL kapsamında erişilen Scopus/Web of Science/ScienceDirect bağlantıları. Google Scholar, resmi API'si bulunmadığı için yalnızca yardımcı arama ve eksik DOI/doğrulama adımlarında yasal/kurumsal sınırlar içinde kullanılır.

**Çıktı:** Aday makale havuzu (meta veri, DOI, kaynak, özet, PDF/tam metin bağlantısı, dil, yayın yılı ve arama geçmişi). L2, L3-L5 çıktıları bu havuza pozitif/negatif alaka etiketi olarak geri döner.

### 4.2.2. Katman 2 — Hafif Makale Sınıflandırıcısı (L2)

**Amaç:** Aday makaleleri düşük hesaplama maliyetiyle “gıda bileşimi verisi içeriyor” veya “ilgili değil” olarak sınıflandırmak.

**Yöntem:** Başlık, özet, bölüm başlıkları ve anahtar kelime örüntüleri kullanılarak DistilBERT/BERT-Tiny benzeri küçük dil modelleri veya eşdeğer verimli sınıflandırıcılar eğitilir (Sanh vd., 2019; Turc vd., 2019). Pozitif örnekler “proximate composition”, “g/100 g”, “mineral composition”, “fatty acid profile” gibi örüntüler ve doğrulanmış OpenNutri sonuçlarından; negatif örnekler aynı dergi ve alanlardan ancak bileşim verisi içermeyen yayınlardan seçilir. Model düzenli olarak, aşağı katman sonuçlarıyla yeniden eğitilir.

**Hedef:** Yinelemeli iyileştirme sonrasında en az 0,92 F1 skoru. Güven eşiğinin üstündeki yayınlar L3'e ilerler; düşük güvenli veya sınırdaki yayınlar aktif öğrenme kuyruğuna alınabilir.

### 4.2.3. Katman 3 — Açık Ağırlıklı Çıkarım Modelleri ve Doğrulama (L3)

**Amaç:** Yapılandırılmamış araştırma içeriğini standart gıda-besin kayıtlarına dönüştüren birincil veri çıkarma motorunu geliştirmek.

L3 tek bir monolitik model yerine alt görevlere ayrılmış modüler bir tasarım kullanır:

| Alt Görev | Açıklama | Model / Yöntem |
| --- | --- | --- |
| Tablo algılama ve ayrıştırma | PDF'lerde tablo, satır, sütun ve başlıkları bulma. | Görsel-dil modeli veya özel tablo çıkarıcı; gerektiğinde Tablo Dönüştürücü benzeri modeller (Smock vd., 2022). |
| Tablo anlamsal yorumlama | Sütun başlığı, birim, dipnot ve ölçüm bağlamını anlama. | LoRA/QLoRA ile ince ayarlı LLM. |
| Bağlam çıkarımı | Gıda adı, numune kaynağı, hazırlama yöntemi, analiz yöntemi ve baz bilgisini çıkarma. | Alt göreve özgü ince ayarlı LLM. |
| Birim normalizasyonu | mg/100 g, µg/100 g, %, ppm, porsiyon gibi birimleri standart baza dönüştürme. | Kural tabanlı motor + denetimli yardımcı sınıflandırıcı. |
| Varlık bağlama | Gıda ve besin adlarını LanguaL, FoodEx2, INFOODS ve yerel kataloglarla eşleme. | Gömme tabanlı benzerlik, takma ad eşlemesi ve uzman onaylı özel kayıtlar. |

Modeller, doğrulama platformunda üretilen altın standart kayıtlar ile parametre-verimli ince ayar yöntemleri kullanılarak eğitilir (LoRA, QLoRA; Hu vd., 2022; Dettmers vd., 2023). Alana özgü ince ayarın bilimsel bilgi çıkarımındaki etkinliği literatürde gösterilmiştir (Li vd., 2023). L4/L5 doğrulanmış çıktıları ve hata etiketleri eğitim verisine eklendikçe L3'ün kapsama alanı genişler. L3'ün tek başına nihai <%0,5 hata hedefine ulaşması beklenmez; bu hedef, L3 + doğrulama kuralları + L4/L5 yükseltme ve rastgele denetimden oluşan tüm sistem için tanımlıdır.

**Gıda bilimi doğrulama kuralları:** Prof. Dr. Servet Gülüm Şumnu ve gıda mühendisliği ekibiyle birlikte tasarlanacak bu kurallar, standart dil modeli güven puanından bağımsız bir doğrulama katmanı oluşturur.

- **Makro besin / kütle dengesi:** Protein, yağ, karbonhidrat, nem ve kül toplamının 100 g yenilebilir kısım için fiziksel olarak makul aralıkta olup olmadığı kontrol edilir (FAO/INFOODS, 2012).

- **Enerji dengesi:** Atwater faktörleriyle hesaplanan enerji değeri, bildirilen enerji ile karşılaştırılır.

- **Fizyolojik referans aralıkları:** Ürün grubu ve besin öğesi için literatür ve referans veri tabanlarından türetilmiş aralıkların dışındaki değerler işaretlenir.

- **Besinler arası tutarlılık:** Toplam yağın yağ asitleri toplamından küçük olmaması, kuru madde-nem ilişkisi, mineral ve vitamin büyüklük sıraları gibi kontroller uygulanır.

- **Birim ve baz tutarlılığı:** 100 g yenilebilir kısım, kuru madde, porsiyon ve ürün hazırlama durumu açıkça ayrıştırılır.

Kuralları geçen ve güven eşiğini aşan kayıtlar kabul edilir; başarısız veya belirsiz kayıtlar L4 veya L5'e yükseltilir.

### 4.2.4. Katman 4 — Ticari Model Destekli Yükseltme (L4)

**Amaç:** L3'ün güvenle çözemediği alt görevleri, proje dönemindeki en güçlü ticari veya kapalı kaynak modellerle çözmek; ancak maliyeti kontrol etmek için yalnızca gerekli parçayı yükseltmek.

**Yöntem:** Makalenin tamamı yerine başarısız olan alt görev L4'e gönderilir. Örneğin tablo yapısı doğru ayrıştırılmış ancak dipnot/birim yorumu belirsizse yalnızca o bağlam modele verilir. Model listesi maliyet ve yeteneğe göre güncellenir; değerlendirme tarihinde erişilebilir GPT, Claude, Gemini veya eşdeğer güçlü modellerden en ucuz yeterli seçenek seçilir. Dinamik istem dosyası, sistematik hatalar ve uzman düzeltmeleriyle güncellenir. RAG bileşeni (Lewis vd., 2020), her çağrı öncesinde doğrulanmış veri tabanından ilgili gıda/besin referanslarını getirir.

**Çıktı:** Ele alınan alt görev için yapılandırılmış kayıt veya düzeltme. L4 çıktıları nihai veri tabanına yalnızca doğrulama kurallarını geçtikten veya L5 tarafından onaylandıktan sonra girer; doğrulanmış L4 çıktıları L3 için eğitim verisine dönüşür.

### 4.2.5. Katman 5 — Uzman Doğrulaması ve Altın Standart Veri (L5)

**Amaç:** Sistem güvenle karar veremediğinde nihai kalite güvencesi sağlamak ve tüm yapay zekâ katmanları için en güçlü eğitim sinyalini üretmek.

**Yöntem:** Gıda mühendisliği bursiyerleri ve alan uzmanları, yan yana PDF görüntüleyici ve yapılandırılmış düzeltme formu içeren doğrulama arayüzünde yapay zekâ ön çıkarımlarını sıfırdan veri girmek yerine inceler ve düzeltir (Monarch, 2021). Her düzeltme; düzeltilen değer, hata kategorisi, zorluk derecesi, kaynak tablo/sayfa ve açıklama olarak kaydedilir.

**Uyarlanabilir çift inceleme protokolü:** Kalibrasyon aşamasında yaklaşık 500 makale iki bursiyer tarafından bağımsız olarak doğrulanır. Uzmanlar arası uyum, verinin doğruluğunun tek garantisi olarak değil, yönergelerin açıklığını ölçen süreç sağlığı göstergesi olarak izlenir. Üretim aşamasında düşük güvenli makaleler çift incelemeye; yüksek güvenli ve kurallar ile uyumlu makaleler tek incelemeye alınır. Buna periyodik rastgele çift inceleme ve kabul edilen kayıtların kaynak PDF'e karşı rastgele denetimi eklenir. Anlaşmazlıklar Prof. Dr. Şumnu tarafından karara bağlanır; çözülemeyen kayıt tahmin edilmez, işaretlenir ve üst incelemeye alınır.

**Kapasite:** İki gıda mühendisliği bursiyerinin her biri günde ortalama 8-12 doğrulanmış makale hedeflediğinde, WP4 doğrulama penceresi boyunca yaklaşık 5.000 uzman doğrulamalı makale ve 25.000 altın standart kayıt üretilebilir. Aktif öğrenme kuyruğu, insan incelemesini en yüksek eğitim değeri taşıyan örneklere yönlendirerek bu kapasitenin verimli kullanılmasını sağlar.

## 4.3. Öğrenilmiş Yönlendirici

Öğrenilmiş Yönlendirici, her makale ve alt görev için hangi katmanın yeterli olacağını tahmin eder. Girdi özellikleri arasında dergi/kaynak, dil, metin uzunluğu, tablo sayısı, tablo karmaşıklığı, L2 güven puanı, önceki model belirsizliği, varlık bağlama güçlüğü ve doğrulama kuralı ihlalleri bulunur. Birden çok katman aynı makaleyi işlediğinde çıktıları arasındaki uyum, ek bir kabul sinyali olarak değerlendirilir (Seung vd., 1992).

Yönlendirici şu bileşik hedefi optimize eder:

**Kayıp = α · İşlem Maliyeti + β · (1 − Doğruluk) + γ · Gecikme**

İşlem maliyeti çağrılan tüm katmanlardaki GPU/API maliyetini; doğruluk nihai doğrulanmış çıktıya göre ölçülen kaliteyi; gecikme ise makale başına geçen toplam süreyi ifade eder. Doğruluk katı kısıt olarak ele alınır: veri tabanı hata oranı <%0,5 sınırını aşacak hiçbir maliyet düşürme kabul edilmez. Yönlendirici bağlamsal bandit yöntemleriyle eğitilecek ve her doğrulanmış makaleden sonra çevrim içi biçimde güncellenecektir (Li vd., 2010; Agarwal vd., 2014).

## 4.4. Katmanlar Arası Öğrenme Sistemi

Her makale, ulaştığı son katmana göre alt katmanlara eğitim sinyali üretir:

| Son İşleme Katmanı | Eğitim Sinyalini Alan Katmanlar | Sinyal Türü |
| --- | --- | --- |
| L2'de elenen yayın | L1, L2 | Negatif alaka etiketi ve sorgu terimi geri bildirimi. |
| L3'te kabul edilen kayıt | L1, L2, L3 | Pozitif alaka etiketi, çıkarım örneği, doğrulama kuralı geçişi. |
| L4'te çözülen alt görev | L1-L4 | L3 hata örneği, ticari model çözümü, istem/RAG iyileştirme sinyali. |
| L5 uzman doğrulaması | L1-L5 ve yönlendirici | Altın standart kayıt, hata kategorisi, zorluk derecesi, maliyet/doğruluk etiketi. |

Alt katmanların başarısız olduğu örneklere eğitimde daha yüksek ağırlık verilir (focal loss; Lin vd., 2017). Böylece uzman doğrulaması ve ticari model kullanımı yalnızca maliyet değil, daha düşük katmanların gelecekte aynı tür problemi çözmesini sağlayan eğitim yatırımı haline gelir.

## 4.5. Veri Toplama ve Yönetimi

### 4.5.1. Veri Kaynakları

| Kaynak | Tür | Dil | Erişim Yöntemi | Beklenen Kullanım |
| --- | --- | --- | --- | --- |
| Europe PMC / PubMed Central | Açık erişimli biyomedikal ve gıda bilimi yayınları | İngilizce | API/OAI-PMH ve açık tam metin | Ana açık literatür kaynağı |
| DergiPark | Türk dergileri | Türkçe / İngilizce | OAI-PMH meta veri + açık tam metin | Türkçe literatür ve yerel gıdalar |
| OpenAlex | Açık akademik meta veri | Çok dilli | REST API | Deduplicasyon, atıf grafiği ve keşif |
| Semantic Scholar | Akademik grafik ve PDF bağlantıları | Çok dilli | REST API ve açık veri setleri | Anlamsal arama ve meta veri zenginleştirme |
| Crossref | DOI meta verileri | Çok dilli | REST API | DOI doğrulama ve kaynak bağlantısı |
| Scopus / Web of Science / ScienceDirect | Kurumsal erişimli yayınlar | Çok dilli | EKUAL ve üniversite kütüphanesi erişimi | Lisans koşullarına uygun tam metin doğrulama |
| Google Scholar | Geniş akademik arama | Çok dilli | Manuel/kurumsal keşif; resmi API yok | Eksik kaynakların doğrulanması, temel otomasyon değil |

### 4.5.2. Veri Standartları

Elde edilen besin verileri FAIR (Bulunabilir, Erişilebilir, Birlikte Çalışabilir, Yeniden Kullanılabilir) ilkeleriyle uyumlu biçimde yönetilecek ve aşağıdaki standartlarla hizalanacaktır:

| Standart | Amaç |
| --- | --- |
| INFOODS etiket adları (Klensin vd., 1989) | Besin bileşeni tanımlama ve birim standardizasyonu. |
| FoodEx2 (EFSA, 2015) | Gıda sınıflandırması ve Avrupa veri altyapılarıyla uyum. |
| LanguaL thesaurus (Møller vd., 2008) | Gıda tanımlayıcı özellikleri ve hazırlama durumu. |
| 100 g yenilebilir kısım standardizasyonu | Farklı birim ve bazların karşılaştırılabilir biçime dönüştürülmesi. |
| Kaynak izlenebilirliği | DOI, sayfa, tablo, satır, kaynak alıntısı ve çıkarım katmanı kaydı. |

### 4.5.3. Veri Tabanı Şeması ve Depolama

Birincil veri tabanı ACID uyumlu PostgreSQL üzerinde tasarlanacaktır. Pgvector uzantısı, varlık bağlama ve RAG geri getirme işlemlerinde vektör benzerliği araması sağlayacaktır. Her kayıt şu bilgileri taşıyacaktır: gıda kimliği/adı, besin öğesi, değer, birim, baz (100 g, kuru madde, porsiyon vb.), hazırlama durumu, kaynak DOI, sayfa/tablo/satır, çıkarım katmanı, güven puanı, doğrulama durumu, uzman düzeltmeleri ve sürüm geçmişi.

Depolama ihtiyacı yaklaşık 2-3 TB olarak öngörülmektedir (100.000 PDF/tam metin bağlantısı ve yerel önbellek, çıkarım kayıtları, model kontrol noktaları, gömme dosyaları ve yedekler). Birincil operasyonlar kurum altyapısı ve proje donanımı üzerinde; felaket kurtarma ve açık veri yayını bulut yedekleri üzerinden yürütülecektir.

## 4.6. Ön Çalışmalar, Mevcut Sistem ve Fizibilite

Proje ekibi, önerilen OpenNutri işlem hattının uçtan uca çalışan bir prototipini halihazırda geliştirmiş ve devreye almıştır. Sistem, başvuru taslağı tarihi itibarıyla otomatik günlük operasyon, model kademesi, normalizasyon, uzman doğrulama arayüzü ve kaynak izlenebilirliği bileşenleriyle çalışmaktadır.

| Bileşen | Durum (mevcut prototip) |
| --- | --- |
| Entegre kaynaklar | Europe PMC, OpenAlex, Semantic Scholar; DergiPark yolu kuruludur. |
| Tarama kapasitesi | Günlük yaklaşık 1.500 aday makale tarama/önceliklendirme kapasitesi. |
| Model kademesi | Tarama → triyaj → nihai çıkarım şeklinde çalışan 3 aktif model aşaması. |
| Normalizasyon | g/100 g, mg/100 g, µg/100 g, kcal/100 g vb. birim ve baz dönüşümleri; referans gıda/besin kataloglarıyla eşleme. |
| Temel veri katmanı | USDA FoodData Central referans verisi sisteme alınmıştır. |
| Uzman doğrulama platformu | Kimlik doğrulamalı web arayüzü; PDF görüntüleyici, kaynak vurgulama, yapılandırılmış düzeltme ve hata-diff kaydı. |
| Operasyon | Zamanlanmış otomasyonla crawl → extract → route → review döngüsü çalışır durumdadır. |
| Gösterge metrikleri | ~17.700 aday makale taranmış, ~4.300 kayıt sisteme alınmış, ~5.000 AI çıkarımı üretilmiş, 339 makale uzman inceleme kuyruğuna yönlendirilmiştir. |

Bu prototip, projenin en yüksek riskli bileşeni olan çok parçalı sistem entegrasyonunu fiilen çalışır hale getirerek fizibilite riskini düşürmektedir. Proje desteği, prototipin eksik kalan araştırma bileşenlerini tamamlayacaktır: (1) tarama ve çıkarımın hazır modellerden ince ayarlı açık ağırlıklı modellere taşınması; (2) gıda bilimi doğrulama kural motorunun sistematik olarak geliştirilmesi; (3) statik yönlendirme eşiklerinin yerine Öğrenilmiş Yönlendirici kurulması; (4) uzman düzeltmelerinin alt katmanları sürekli yeniden eğittiği öğrenme döngüsünün kapatılması.

### 4.6.1. Türk Gıda Veri Açığı Ön Değerlendirmesi

TürKomp 500'den fazla analiz edilmiş gıda için güçlü bir temel sunsa da Türkiye'nin tarımsal ve kültürel gıda çeşitliliği çok daha geniştir. Bilimsel literatürde belgelenen birçok yerel gıda, yöresel ürün ve ürün varyantı USDA veya EFSA veri tabanlarında bulunmamaktadır. Bu açığın kesin ölçümü projenin erken çıktılarından biridir: Türkçe ve Türkiye kaynaklı literatür sistematik olarak indekslenecek, uluslararası veri tabanlarında bulunmayan gıda öğeleri makine tarafından okunabilir biçimde sayılacak ve en az 5.000 özgün Türk gıda ürünü veya varyantı hedeflenecektir.

## 4.7. Değişkenler ve İstatistiksel Yöntemler

### 4.7.1. Bağımlı Değişkenler

| Değişken | Tanım | Ölçüm | Birim |
| --- | --- | --- | --- |
| Otomatik onay doğruluğu | İnsan incelemesi olmadan kabul edilen kayıtların doğru olan yüzdesi. | Periyodik rastgele uzman denetimi. | % |
| Otomatik onay oranı | İnsan müdahalesi olmadan tamamlanan makalelerin oranı. | Toplam işlenen makaleye oran. | % |
| Veri tabanı hata oranı | Hata içeren kabul edilmiş kayıtların oranı. | Otomatik + insan doğrulamalı kayıtların rastgele denetimi. | % |
| Makale başına maliyet | Kabul edilebilir kaliteye ulaşmak için toplam işlem maliyeti. | GPU saati + API maliyeti + insan doğrulama maliyeti. | USD |
| Çıkarma gecikmesi | Veri alımından yapılandırılmış çıktıya kadar geçen süre. | Gerçek zaman ölçümü. | saniye |
| Geri çağırma | Çıkarılabilir veriler arasında sistemin yakaladığı oran. | Uzman oluşturulmuş referansla karşılaştırma. | % |

### 4.7.2. Bağımsız Değişkenler

| Değişken | Seviyeler / Aralık | Doğrulama Hedefi |
| --- | --- | --- |
| Model boyutu | 1-3B, 7-13B, 30-70B parametre sınıfları | Boyut-doğruluk-maliyet dengesi. |
| İnce ayar yöntemi | LoRA, QLoRA, tam ince ayar | PEFT yöntemlerinin tam ince ayara göre verimini ölçmek. |
| Eğitim verisi hacmi | 500, 1.000, 2.000, 4.000, 5.000 doğrulanmış makale | Öğrenme eğrileri ve azalan getiriler. |
| Modüler / monolitik tasarım | Alt göreve özgü modeller vs. tek model | Modüler mimarinin üstünlüğünü test etmek. |
| Güven eşiği | 0,70-0,95 aralığı | Kabul/yükseltme kararlarını <%0,5 hata kısıtı altında optimize etmek. |
| Makale özellikleri | Dil, kaynak, tablo karmaşıklığı, gıda kategorisi | Sistematik performans farklılıklarını belirlemek. |

### 4.7.3. İstatistiksel Analiz Planı

- **Performans:** Besin kategorileri genelinde makro ortalamalı kesinlik, geri çağırma ve F1 skoru raporlanacaktır. %95 güven aralıkları bootstrap yeniden örnekleme ile hesaplanacaktır (Efron & Tibshirani, 1993).

- **Model karşılaştırmaları:** İkili doğru/yanlış kararlar için eşleştirilmiş McNemar testi; sürekli besin değerleri için Wilcoxon işaretli sıralar testi kullanılacaktır (p < 0,05).

- **Maliyet-doğruluk dengesi:** Yönlendirme konfigürasyonları için Pareto sınırı analizi yapılacak; maliyet projeksiyonları karma etkili regresyonla modellenerek makale özellikleri sabit etki, makale kimliği rastgele etki olarak ele alınacaktır.

- **Öğrenme eğrileri:** Ek doğrulama verisinin marjinal katkısı güç yasası öğrenme eğrileriyle incelenecektir (Hestness vd., 2017).

- **Uzmanlar arası uyum:** Kategorik doğruluk kararları için Cohen'in κ'sı (McHugh, 2012), sürekli besin değerleri için sınıf içi korelasyon katsayısı (Shrout & Fleiss, 1979) izlenecektir. Bu ölçütler veri doğruluğunun tek garantisi değil, açıklama yönergelerinin kalibrasyon göstergesidir.

- **Yönlendirici performansı:** Oracle yönlendiriciye karşı kümülatif pişmanlık analizi yapılacak; işlenen makale başına normalize pişmanlığın zamanla azalması beklenmektedir (Lattimore & Szepesvári, 2020).

## 4.8. Yöntem - İş Paketi Eşleştirmesi ve Etik/Yasal Çerçeve

| Yöntem Bileşeni | Birincil Çalışma Paketi | Zaman Aralığı | Rolü |
| --- | --- | --- | --- |
| L1 tarayıcı + L2 sınıflandırıcı | WP1 | 1-4. Aylar | Altyapı ve veri toplama. |
| L3 açık ağırlıklı çıkarım + doğrulama kuralları | WP2 | 3-8. Aylar | Çekirdek veri çıkarma motoru. |
| L4 entegrasyon + Öğrenilmiş Yönlendirici | WP3 | 5-10. Aylar | Sistem entegrasyonu ve maliyet optimizasyonu. |
| L5 uzman doğrulaması + katmanlar arası öğrenme | WP4 | 4-16. Aylar | Altın standart veri ve model iyileştirme. |
| API, kıyaslama, açık veri ve yayınlar | WP5 | 14-18. Aylar | Dağıtım, doğrulama ve yayılım. |

**Etik ve yasal çerçeve:** Proje kişisel veri veya insan denek verisi toplamamaktadır; çalışma konusu açık erişimli veya kurumsal lisanslı bilimsel yayınlardaki olgusal gıda bileşimi değerleridir. Tam metin/PDF içerikleri yeniden yayımlanmayacak; veri tabanında yalnızca kaynak gösterimli olgusal değerler, kısa kaynak atıfları ve bibliyografik bağlantılar tutulacaktır. Kurumsal lisans koşulları, yayıncı kullanım şartları ve metin/veri madenciliği sınırları gözetilecektir. Etik kurul gerekliliği beklenmemekle birlikte, başvuru sürecinde kurumun etik kurul/TTO görüşü alınarak başvuru dosyasında sunulacaktır.

**Kaynaklar:** EK-1 Kaynaklar bölümünde verilmiştir.

# 5. PROJE YÖNETİMİ

## 5.1. İş Paketleri, Görev Dağılımı ve Süreleri

| İP No | İş Paketinin Adı ve Hedefleri | Sorumlu Ekip | Zaman Aralığı | Başarı Ölçütü ve Katkısı |
| --- | --- | --- | --- | --- |
| 1 | **Altyapı ve Veri Toplama:** L1 akıllı tarayıcı, L2 sınıflandırıcı, veri tabanı şeması ve kaynak erişim hattı. | Yürütücü: Prof. Dr. Murat Ceylan; Araştırmacı: Prof. Dr. Servet Gülüm Şumnu; Bursiyerler: Arciel Aliognis, Alijon Alimov | 1-4. Aylar | Çok kaynaklı tarayıcı çalışır durumda; L2 F1 ≥0,92; ≥100.000 ilgili makaleye ulaşabilecek aday havuz ve deduplicasyon hattı. |
| 2 | **Çekirdek Çıkarma Motoru (L3):** Alt göreve özgü açık ağırlıklı modeller, normalizasyon, varlık bağlama ve gıda bilimi doğrulama kuralları. | Yürütücü: Prof. Dr. Murat Ceylan; Araştırmacılar: Dr. Engin Esme, Prof. Dr. Servet Gülüm Şumnu; Bursiyerler: Arciel Aliognis, Aleyna Özcan, Peri Açıkgöz | 3-8. Aylar | L3 alt görevleri entegre; ≥10 doğrulama kuralı aktif; ticari API tabanlı referansa göre en az %30 maliyet düşüşü; düşük güvenli kayıtların L4/L5'e güvenli yönlendirilmesi. |
| 3 | **Kademeli Entegrasyon ve Yönlendirici:** L4 ticari model yükseltmesi, RAG/istem dosyası, Öğrenilmiş Yönlendirici ve maliyet optimizasyonu. | Yürütücü: Prof. Dr. Murat Ceylan; Araştırmacı: Dr. Engin Esme; Bursiyerler: Arciel Aliognis, Alijon Alimov | 5-10. Aylar | L1-L4 uçtan uca çalışır; yönlendirici rastgele/statik yönlendirmeye göre ≥%20 maliyet düşüşü sağlar; L5 hariç uçtan uca gecikme <60 sn/makale hedeflenir. |
| 4 | **Uzman Doğrulama ve Katmanlar Arası Öğrenme:** Kalibrasyon, uyarlanabilir doğrulama protokolü, altın standart veri üretimi ve uzman geri bildirimli model iyileştirme. | Yürütücü: Prof. Dr. Murat Ceylan; Araştırmacılar: Prof. Dr. Servet Gülüm Şumnu, Dr. Engin Esme; Bursiyerler: Alijon Alimov, Arciel Aliognis, Aleyna Özcan, Peri Açıkgöz | 4-16. Aylar | ≥5.000 uzman doğrulamalı makale; ≥25.000 altın standart kayıt; kabul edilen kayıtların rastgele denetiminde hata <%0,5; otomatik onay oranı ≥%90. |
| 5 | **Sistem Dağıtımı, Kıyaslama ve Yaygınlaştırma:** REST API, açık araştırma veri seti, performans kıyaslaması, dokümantasyon ve yayınlar. | Yürütücü: Prof. Dr. Murat Ceylan; Araştırmacılar: Dr. Engin Esme, Prof. Dr. Servet Gülüm Şumnu; Bursiyerler: Alijon Alimov, Arciel Aliognis, Aleyna Özcan, Peri Açıkgöz | 14-18. Aylar | ≥500.000 gıda-besin kaydı; API yayında (<200 ms hedef yanıt süresi, ≥100 eşzamanlı istek/s); açık veri ve kıyaslama raporu yayımlanır; ≥3 makale hakemli dergilere gönderilir. |

**İş-Zaman Çizelgesi (Gantt) — Aylar 1-18**

```
Ay:  1   2   3   4   5   6   7   8   9  10  11  12  13  14  15  16  17  18
WP1 ███████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  (1-4)
WP2 ░░░░░░░░███████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  (3-8)
WP3 ░░░░░░░░░░░░░░░░███████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  (5-10)
WP4 ░░░░░░░░░░░░███████████████████████████████████████░░░░░░░░░░░░░░░░░░░  (4-16)
WP5 ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░███████████████████  (14-18)
```

## 5.2. Risk Yönetimi

| İP No | Risk | B Planı / Yönetim Yaklaşımı |
| --- | --- | --- |
| WP1 | Yayıncı API hız sınırları veya lisans kısıtları hedef literatür hacmini düşürür. | OpenAlex, Semantic Scholar açık veri setleri ve Europe PMC/PubMed Central toplu erişimleri önceliklendirilir; DergiPark ve kurumsal erişim kanalları ayrı izlenir; Google Scholar temel otomasyon kaynağı yapılmaz. |
| WP2 | İlk L3 modelleri beklenen doğruluğa ulaşamaz. | Alt görevleri daha dar uzman modellere bölmek, L4 kullanımını geçici artırmak, doğrulama kurallarını sıkılaştırmak ve düşük güvenli kayıtları otomatik kabul etmeden L5'e yönlendirmek. |
| WP3 | Öğrenilmiş Yönlendirici yeterince hızlı yakınsamaz veya pahalı katmanlara fazla yönlendirir. | FrugalGPT tarzı statik eşik kademesi yedek olarak kullanılır; katman başına maliyet tavanları ve API bütçe alarmı uygulanır. |
| WP3 | Ticari API fiyatları veya erişim koşulları proje süresince değişir. | Çoklu sağlayıcı listesi tutulur; L4 yalnızca başarısız alt görev için kullanılır; açık ağırlıklı model seçenekleri ve L3 iyileştirme döngüsü L4 bağımlılığını azaltır. |
| WP4 | Doğrulama kapasitesi 5.000 makale hedefine yetişmez. | Aktif öğrenme kuyruğu en yüksek değerli makaleleri önceliklendirir; yönergeler sadeleştirilir; Prof. Dr. Şumnu gözetiminde eğitim/kalibrasyon artırılır; kalite hedefi korunarak hacim riski erken raporlanır. |
| WP5 | Nihai kıyaslama beklenen otomatik onay oranına ulaşamaz. | Veri tabanı hata hedefi L5 doğrulama ve rastgele denetimle korunur; otomatik onay oranı düşük kalırsa sistem daha fazla kaydı L5'e yönlendirir ve sonuçlar sınırlılık olarak raporlanır. |

## 5.3. Araştırma Olanakları

| Altyapı / Erişim Kanalı | Projede Kullanım Amacı |
| --- | --- |
| Ev sahibi kurum sunucuları ve proje kapsamında alınacak GPU/NAS donanımı | Birincil veri tabanı, çıkarım servisleri, model kontrol noktaları, PDF/tam metin önbelleği ve yedekleme. |
| TRUBA yüksek başarımlı hesaplama kaynakları (TÜBİTAK ULAKBİM; başvuru/erişim kanalı) | Büyük ölçekli LLM ince ayarı, RLHF/tercih temelli eğitim süreçleri ve model kıyaslaması. |
| Üniversite kütüphanesi ve EKUAL erişimi | Web of Science, Scopus, ScienceDirect ve diğer lisanslı kaynaklarda literatür keşfi ve yasal tam metin erişimi. |
| Mevcut OpenNutri prototip altyapısı | Crawler, model kademesi, normalizasyon, uzman doğrulama arayüzü ve operasyonel veri tabanı için başlangıç platformu. |

\newpage

# 6. YAYGIN ETKİ

## 6.1. Projeden Elde Edilmesi Öngörülen Çıktılar

| Çıktı Türü | Çıktı | Öngörülen Zaman Aralığı |
| --- | --- | --- |
| Bilimsel/Akademik | Büyük ölçekli gıda bileşimi veri çıkarma kıyaslaması: ticari ve açık ağırlıklı LLM'ler ile OpenNutri'nin doğruluk, maliyet ve hız karşılaştırması; değerlendirme veri seti ve kodunun yayımlanması. | 12-18 ay |
| Bilimsel/Akademik | Kademeli Hibrit Zeka mimarisi makalesi: L1-L5 işlem hattı, Öğrenilmiş Yönlendirici, katmanlar arası öğrenme, ablasyon çalışmaları ve maliyet analizi. | 12-18 ay |
| Bilimsel/Akademik | OpenNutri-DB veri seti makalesi: veri tabanı tanımı, metodoloji, Türk gıda veri açığı analizi ve USDA/EFSA/TürKomp karşılaştırması. | 12-18 ay |
| Ekonomik/Ticari/Sosyal | OpenNutri Veri Tabanı: en az 500.000 kaynak izlenebilir gıda-besin kaydı, en az 5.000 özgün Türk gıda ürünü/varyantı ve kaynakta mevcut olduğunda 181'e kadar besin öğesi. | 6-12 ay ilk sürüm; 12-18 ay tam ölçek |
| Ekonomik/Ticari/Sosyal | OpenNutri API: sürekli güncellenen veri tabanına erişim sağlayan, dokümantasyon ve SDK içeren üretim REST API. | 12-18 ay |
| Ekonomik/Ticari/Sosyal | Kademeli doğrulama motoru: başka ülkelerin veya kurumların gıda bileşimi dijitalleştirme süreçlerine uyarlanabilir veri çıkarma/doğrulama altyapısı. | 12-18 ay |
| Araştırmacı Yetiştirme | Yazılım/Yapay Zeka ekibi: LLM ince ayarı, RAG, RLHF/tercih temelli öğrenme, rota optimizasyonu, API geliştirme ve gıda veri standartları konularında uygulamalı eğitim. | 0-18 ay |
| Araştırmacı Yetiştirme | Gıda Bilimi ekibi: gıda bileşimi analizi, Türk gıda profillemesi, kalite kontrol protokolleri, USDA/EFSA/TürKomp çapraz referanslama ve yapay zekâ destekli doğrulama iş akışları. | 0-18 ay |

## 6.2. Projeden Elde Edilmesi Öngörülen Etkiler

| Etki Türü | Etki | Öngörülen Zaman |
| --- | --- | --- |
| Toplumsal/Kültürel | Türk yemek kültürüne uyarlanmış kanıta dayalı beslenme rehberliği; yerel gıdalar için daha doğru beslenme takibi ve diyet uygulamaları. | 18-36 ay |
| Toplumsal/Kültürel | Halk sağlığı politikaları için bölgesel ve ürün bazlı besin bileşimi referansı; okul beslenmesi ve bölgesel müdahalelerde yerel veri kullanımı. | 18-36 ay |
| Sürdürülebilirlik | Gıda tedarik zinciri izlenebilirliği ve Yeşil Mutabakat uyum süreçlerinde bileşimsel veri desteği. | 18-42 ay |
| Akademik | Yapay zekâ destekli gıda bileşimi çıkarımı için açık kıyaslama ve metodoloji; farmakoloji, çevre bilimi ve malzeme bilimi gibi alanlara aktarılabilir mimari. | 12-24 ay |
| Akademik | USDA FoodData Central, EFSA ve FAO/INFOODS gibi veri ekosistemleriyle uyumlu format sayesinde ulusal/uluslararası iş birliği zemini. | 18-36 ay |
| Akademik | Yapay zekâ ve gıda bilimi kesişiminde eğitim almış 4 bursiyer; yüksek lisans tezleri ve disiplinler arası uzmanlık kazanımı. | 0-18 ay |
| Ekonomik | Gıda ihracatı, sağlık teknolojisi, diyetisyen uygulamaları, gıda üretim kalite kontrolü ve tarımsal ürün pazarlaması için veri altyapısı. | 18-36 ay |
| Ekonomik | Veri lisanslama, API aboneliği ve doğrulama motoru uyarlamasıyla iki ana gelir kanalı. | 24-48 ay |
| İstihdam | Proje sonrası 2 yıl içinde veri operasyonları, API mühendisliği ve iş geliştirme rollerini kapsayan 5-10 kişilik spin-off hedefi; ekosistemde 10-20 dolaylı istihdam potansiyeli. | 18-36 ay |
| Rekabetçilik | Yabancı besin veri tabanlarına bağımlılığı azaltan, Türk gıdalarını kapsayan ulusal alternatif; ihracat ve yerli sağlık teknolojileri için doğruluk avantajı. | 18-48 ay |
| Ulusal Güvenlik | Gıda bileşimi verisi üzerinde ulusal kontrol, yabancı veri tabanı fiyat/erişim değişikliklerine karşı dayanıklılık ve kriz dönemlerinde beslenme planlaması desteği. | 12-48 ay |
| Siber Güvenlik | Nihai çekirdek veri ve model altyapısının kurum/TRUBA/proje donanımı üzerinde yürütülmesi; bulutun yedekleme ve yayın dağıtımıyla sınırlandırılması; açık kaynaklı yığınla tedarikçi bağımlılığının azaltılması. | 0-18 ay |

## 6.3. Sanayi İşbirliğine Yönelik Programlara Geçiş Yol Haritası

OpenNutri'nin ticarileştirilebilir üç çıktısı — doğrulanmış gıda bileşimi veri tabanı, üretim REST API'si ve kademeli doğrulama motoru — endüstriyel kullanıma hazır bir ürün yığını oluşturur. Yol haritası, akademik prototipten sürdürülebilir platforma geçişi üç aşamada planlamaktadır.

**1. Aşama — Doğrulama ve Ortak Edinimi (12-18. Aylar, WP5 ile eş zamanlı)**

- **Pilot ortaklıklar:** API, üç hedef sektörü temsil eden 2-3 kuruluşa ücretsiz pilot olarak sunulacaktır: AB 1169/2011 uyum verisine ihtiyaç duyan bir gıda ihracatçısı, yerel gıda veri altyapısına ihtiyaç duyan bir sağlık teknolojisi/beslenme uygulaması şirketi ve halk sağlığı veya gıda güvenliği odaklı bir kurum.

- **Fikri mülkiyet koruması:** İnce ayarlı model ağırlıkları, uzman onaylı altın standart veri seti ve doğrulama kural motoru ticari sır, veri tabanı hakları ve lisans sözleşmeleriyle korunacaktır. Akademik erişim modeli, ticari değeri korurken bilimsel yayılımı destekleyecektir.

- **İş modelinin resmileştirilmesi:** Kademeli API fiyatlandırması, veri lisanslama koşulları, destek/entegrasyon hizmetleri ve pilot sonuçlarına dayalı birim ekonomi hazırlanacaktır.

**2. Aşama — TÜBİTAK 1512 BiGG + KOSGEB ile Şirket Kurulumu (18-30. Aylar)**

Birincil ticarileşme yolu girişimciliktir. OpenNutri platformunu işletmek üzere bir spin-off şirket kurulması; BiGG ile üretim kalitesinde SaaS/API platformuna geçiş, ilk müşterilerin dahil edilmesi ve 2-3 teknik personelin işe alınması hedeflenmektedir. KOSGEB/TEKNOYATIRIM gibi programlar ise özel GPU sunucuları, yüksek erişilebilirlik veri tabanı altyapısı ve kurumsal dağıtım için değerlendirilecektir.

**3. Aşama — TEYDEB 1507 ve TEYDEB 1505 ile Ölçeklendirme (30-48. Aylar)**

Spin-off ilk gelirlerini elde ettikten sonra TEYDEB 1507 ile sektör odaklı API ürünleri (ihracat uyum modülü, klinik beslenme karar desteği vb.) geliştirilecek; TEYDEB 1505 ile üniversite-sanayi iş birliği kapsamında doğrulama motorunun başka ülke veya kurumların gıda bileşimi dijitalleştirme süreçlerine uyarlanması hedeflenecektir.

**Beklenen sonuç:** Proje tamamlandıktan sonraki 3 yıl içinde 5-10 çalışanlı bir spin-off şirket, düzenli API/veri lisansı geliri ve en az bir uluslararası doğrulama motoru uyarlama veya lisanslama anlaşması hedeflenmektedir.

## 6.4. Proje Çıktılarının Paylaşımı ve Yayılımı

| Etkinlik Türü | Paydaş / Olası Kullanıcılar | Zaman ve Süre |
| --- | --- | --- |
| Proje web sitesi: dokümantasyon, ilerleme güncellemeleri, API erken erişim kaydı | Araştırmacılar, geliştiriciler, gıda endüstrisi profesyonelleri, genel kamuoyu | 1. aydan itibaren; proje süresince ve sonrasında |
| Akademik/profesyonel duyurular (ResearchGate, Google Scholar profili, LinkedIn, X) | Akademik ve profesyonel kitle | 6. aydan itibaren sürekli |
| Hakemli yayınlar: kıyaslama, mimari, veri seti | Gıda bilimi, yapay zekâ/NLP ve veri bilimi toplulukları | 12-18. aylar |
| Açık araştırma veri seti yayını (Zenodo / HuggingFace) | Küresel araştırma topluluğu, FAO/INFOODS, USDA/EFSA ekosistemi, sağlık teknolojisi geliştiricileri | 14-16. aylar |
| API dokümantasyonu ve SDK sürümü | Yazılım geliştiriciler, sağlık teknolojisi şirketleri, beslenme uygulamaları | 14-16. aylar |
| Ulusal akademik çalıştay/seminer | Türk gıda bilimi ve bilgisayar bilimi araştırmacıları, lisansüstü öğrenciler, TürKomp/BEBIS ekibi | 14. ay |
| Sektör tanıtım günü / paydaş toplantısı | Gıda ihracatçıları, sağlık teknolojisi girişimleri, diyetisyenler, kamu paydaşları | 16. ay |
| Uluslararası konferans sunumları | Akademik topluluk ve sektör temsilcileri | 15-18. aylar |
| Türk gıda ihracatçı birliklerine doğrudan erişim | TİM ve ilgili ihracatçı birlikleri, gıda ihracat şirketleri | 14-18. aylar |
| TÜBİTAK proje tanıtımı / bilim fuarı katılımı | TÜBİTAK topluluğu, genel kamuoyu, potansiyel sektör ortakları | 18. ay |

# EK-1 KAYNAKLAR

- Agarwal, A., et al. (2014). Taming the monster: A fast and simple algorithm for contextual bandits. *ICML*, 1638–1646.

- Chapelle, O., & Li, L. (2011). An empirical evaluation of Thompson sampling. *NeurIPS*, 24.

- Chen, L., et al. (2023). FrugalGPT: How to use large language models while reducing cost and improving performance. *arXiv:2305.05176*.

- Dettmers, T., et al. (2023). QLoRA: Efficient finetuning of quantized language models. *NeurIPS*, 36.

- Dooley, D.M., et al. (2018). FoodOn: A harmonized food ontology to increase global food traceability. *npj Science of Food*, 2(1), 1-10.

- EFSA (2015). The food classification and description system FoodEx2 (revision 2). *EFSA Supporting Publications*, 12(5), EN-804.

- Efron, B., & Tibshirani, R.J. (1993). *An Introduction to the Bootstrap*. Chapman & Hall/CRC.

- FAO/INFOODS (2012). *FAO/INFOODS Guidelines for Food Matching*. Rome: FAO.

- Fedus, W., et al. (2022). Switch Transformers: Scaling to trillion parameter models. *JMLR*, 23(120), 1–39.

- Google Data API Team. (2007). *Scholar API discussion*. Google Groups. https://groups.google.com/g/google-help-dataapi/c/lraJZ9qPeFc

- Hestness, J., et al. (2017). Deep learning scaling is predictable, empirically. *arXiv:1712.01208*.

- Hu, E.J., et al. (2022). LoRA: Low-rank adaptation of large language models. *ICLR*.

- Klensin, J.C., et al. (1989). *Identification of Food Components for INFOODS Data Interchange*. Tokyo: UNU Press.

- Lattimore, T., & Szepesvári, C. (2020). *Bandit Algorithms*. Cambridge University Press.

- Lewis, P., et al. (2020). Retrieval-augmented generation for knowledge-intensive NLP tasks. *NeurIPS*, 33, 9459–9474.

- Li, L., et al. (2010). A contextual-bandit approach to personalized news article recommendation. *WWW*, 661–670.

- Li, Y., et al. (2023). Domain-specific fine-tuning of LLMs for scientific information extraction. *arXiv:2307.02738*.

- Lin, T.-Y., et al. (2017). Focal loss for dense object detection. *ICCV*, 2980–2988.

- McHugh, M.L. (2012). Interrater reliability: The kappa statistic. *Biochemia Medica*, 22(3), 276-282.

- Monarch, R.M. (2021). *Human-in-the-Loop Machine Learning*. Manning Publications.

- Møller, A., et al. (2008). LanguaL 2006 – the LanguaL thesaurus. *European Journal of Clinical Nutrition*, 62, S272–S275.

- Ouyang, L., et al. (2022). Training language models to follow instructions with human feedback. *NeurIPS*, 35, 27730–27744.

- Sanh, V., et al. (2019). DistilBERT: Smaller, faster, cheaper and lighter. *arXiv:1910.01108*.

- Schakel, S.F., Sievert, Y.A., & Buzzard, I.M. (1988). Sources of data for developing and maintaining a nutrient database. *Journal of the American Dietetic Association*, 88(10), 1268–1271.

- Settles, B. (2012). *Active Learning*. Morgan & Claypool Publishers.

- Seung, H.S., et al. (1992). Query by committee. *COLT*, 287–294.

- Shazeer, N., et al. (2017). Outrageously large neural networks: The sparsely-gated MoE layer. *ICLR*.

- Shrout, P.E., & Fleiss, J.L. (1979). Intraclass correlations: Uses in assessing rater reliability. *Psychological Bulletin*, 86(2), 420–428.

- Smock, B., et al. (2022). PubTables-1M: Towards comprehensive table extraction. *CVPR*, 4634–4642.

- Turc, I., et al. (2019). Well-read students learn better: On the importance of pre-training compact models. *arXiv:1908.08962*.

- European Parliament and Council. (2011). *Regulation (EU) No 1169/2011 on the provision of food information to consumers*. EUR-Lex. https://eur-lex.europa.eu/eli/reg/2011/1169/oj

- Semantic Scholar. (2026). *Semantic Scholar Academic Graph API*. https://www.semanticscholar.org/product/api

- TÜBİTAK MAM Gıda Enstitüsü (2014). *Türkiye'nin Ulusal Gıda Kompozisyon Veri Tabanı (TürKomp)*. TÜBİTAK Marmara Araştırma Merkezi. https://mam.tubitak.gov.tr/turkiyenin-ulusal-gida-kompozisyon-veri-tabani/

- TÜBİTAK ULAKBİM. (2026). *TRUBA Başvuru ve yüksek başarımlı hesaplama altyapısı*. https://www.truba.gov.tr/

- Viola, P., & Jones, M. (2001). Rapid object detection using a boosted cascade. *CVPR*, 1, 511–518.

- Wang, M., et al. (2011). Classifier cascade for minimizing feature evaluation cost. *AISTATS*, 218–226.

- Yue, X., et al. (2024). Large language model cascades with mixture of thoughts representations. *ICLR*.

- Cenikj, G., Strojnik, L., Angelski, R., Ogrinc, N., Koroušić Seljak, B., & Eftimov, T. (2023). From language models to large-scale food and biomedical knowledge graphs. *Scientific Reports*, 13, 7815.

- Hooton, F., Menichetti, G., & Barabási, A.-L. (2020). Exploring food contents in scientific literature with FoodMine. *Scientific Reports*, 10, 16191.

- Ispirova, G., Eftimov, T., & Koroušić Seljak, B. (2020). P-NUT: Predicting NUTrient content from short text descriptions. *Mathematics*, 8(10), 1811.

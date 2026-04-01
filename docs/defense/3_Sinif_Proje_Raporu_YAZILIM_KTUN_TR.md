# YAZILIM MÜHENDİSLİĞİ UYGULAMASI-I
## ARASINAV RAPORU

### OpenNutri: Bilimsel Literatürden LLM Destekli Gıda Verisi Çıkarımı

**Öğrenciler:**

- 221229078 - Arciel Aliognis Baez Zamora
- 221229075 - Duc Huan Ngo
- 221229031 - Ayşegül Doğan

**Danışman:** Dr. Öğr. Üyesi Fatma Zehra Solak

**Sınav Tarihi:** [Danışman tarafından doldurulacaktır]

\newpage

# DÖNEM İÇİ YAPILAN ÇALIŞMALARIN ÖZETİ

Bu ara rapor, proje öneri formunda birinci dönem için tanımlanan ilk üç ana başlığın mevcut durumunu özetlemektedir:

- otomatik veri alma boru hattı,
- veritabanı ve orkestrasyon mimarisi,
- uzman anotasyon motoru.

Arasınav itibarıyla OpenNutri'nin çalışan çekirdeği kurulmuştur. Sistem bilimsel kaynaklardan aday makale bulur, bu adayları çok aşamalı olarak filtreler, uygun PDF dosyalarını sisteme alır, uzman kullanıcıya yapılandırılmış anotasyon ekranı sunar ve kullanıcı kararlarını sonraki tarama döngülerinde geri besleme olarak kullanır.

Projenin temel akışı nettir: makale bulunur, uzman kullanıcı belge üzerinde veri girer, oluşan etiketler daha sonraki arama ve sıralamayı iyileştirir. Bu akışın ana bileşenleri arasınav aşamasında birlikte çalışmaktadır.

Birinci dönem maddeleri ile mevcut durumun ilişkisi Tablo 1'de özetlenmiştir.

| Öneri formu maddesi | Arasınav durumu | Somut çıktı |
| --- | --- | --- |
| 1. Otomatik Veri Alma Boru Hattı | Büyük ölçüde ilerletildi | Çok kaynaklı tarama, dil bazlı iş akışları, PDF edinme, doğrulama, Supabase'e yükleme |
| 2. Veritabanı ve Orkestrasyon Mimarisi | Büyük ölçüde ilerletildi | Ortak şema, RLS politikaları, depolama hattı, ETL ve arama kanıtı tabloları |
| 3. Uzman Anotasyon Motoru | Büyük ölçüde ilerletildi | PDF görüntüleme, nutrient highlight, dinamik food/nutrient girişi, test mode, global skip, olay kaydı |
| 4. Belge Segmentasyonu ve Temel Çıkarım Süreci | Sonraki aşama | Bu raporun odağı çalışan ilk üç başlıktır |

Sistem dört ana fikir etrafında kurulmuştur: güçlü adayları seçen bir crawler hattı, ortak backend ve veri modeli, PDF üzerinde çalışmaya uygun anotasyon ekranı ve kullanıcı kararlarını geri beslemeye dönüştüren kapalı döngü yapı.

Tablo 2, bu yapıyı sistemin ana parçaları üzerinden özetlemektedir.

| Katman | Gerçekleştirilen işler | Teknik sonucu |
| --- | --- | --- |
| Crawler ve makale edinimi | Çok kaynaklı arama, çok aşamalı eleme, EN/TR iş akışları, DergiPark desteği, PDF doğrulama | Sisteme gelen makaleler daha seçilmiş ve daha anlamlı hale geldi |
| Backend ve veri modeli | Ortak veritabanı şeması, arama kanıtı kayıtları, anotasyon tabloları, RLS politikaları | UI, crawler ve geri besleme katmanı aynı veri yapısı üzerinde birleşti |
| Annotator ve kullanıcı iş akışı | PDF görüntüleme, highlight destekli veri girişi, dinamik food/nutrient formu, test mode, global skip | Uzman kullanıcı gerçek belge üzerinde daha hızlı ve kontrollü çalışabilir hale geldi |
| Öğrenen geri besleme döngüsü | Kullanıcı kararlarının event olarak saklanması ve sonraki taramayı beslemesi | Sistem kullanıcı davranışından öğrenen kapalı döngü yapısına yaklaştı |

Şekil 1, arasınav itibarıyla oluşan uçtan uca sistemi göstermektedir.

![Şekil 1 - OpenNutri arasınav sistem mimarisi](assets/figure_1_system_architecture.png)

Şekil 1. OpenNutri'nin arasınav itibarıyla çalışan kapalı döngü mimarisi.

Arasınav aşamasında ilk üç hedef için çalışan bileşenler geliştirilmiştir. Mevcut durum, sistemin çekirdek altyapısının çalıştığı erken üretim aşamasını temsil etmektedir.

\newpage

# PROJENİN AMACI ve ÖNEMİ

## Projenin Amacı

OpenNutri'nin amacı, bilimsel literatürde dağınık halde bulunan gıda bileşimi verilerini uzman geri bildirimini merkeze alan bir platform ile dijitalleştirmektir. Proje bu amaç için üç temel yetenek kurmaktadır:

- uygun makaleleri otomatik olarak bulmak ve sisteme taşımak,
- bu makaleleri uzmanların denetimli biçimde etiketlemesini sağlamak,
- oluşan etiketlerden yararlanarak sonraki tarama kararlarını daha isabetli hale getirmek.

Arasınav aşamasındaki odak, bu üç yeteneğin çekirdek sürümünü kurmaktır. Mevcut çalışma, veri altyapısını, kullanıcı iş akışını ve geri besleme döngüsünü üretim mantığıyla ayağa kaldırmaktadır.

## Projenin Önemi

Projenin önemi üç düzeyde ortaya çıkmaktadır.

Birinci düzey veri erişimi problemidir. Gıda bileşimi çalışmaları çoğunlukla PDF biçiminde ve standart veri çıkışı olmadan yayımlanmaktadır. OpenNutri bu bilgiyi sorgulanabilir yapısal veriye dönüştürmeyi hedeflemektedir.

İkinci düzey insan emeğinin verimli kullanılmasıdır. Uzman anotasyonu pahalı ve sınırlı bir kaynaktır. Bu nedenle crawler, filtreleme ve geri besleme katmanı uzman önüne daha anlamlı adaylar getirecek şekilde tasarlanmıştır. Arasınav itibarıyla search gate, metadata filter, PDF doğrulama ve global skip mantığı bu ihtiyacı karşılamaktadır.

Üçüncü düzey Türkçe literatürün görünürlüğüdür. PubMed Central uluslararası açık erişim literatürü, DergiPark ise Türkiye'de yayımlanan çalışmaları sisteme taşımaktadır. EN/TR iş akışlarının ayrılması, Türkçe literatür için ayrı bir hedef havuz kurulmasını sağlamıştır.

Teknik açıdan proje; normalize veri modeli, çok kaynaklı tarama, katmanlı filtreleme, PDF doğrulama, kullanıcı olay kaydı ve soft feedback öğrenmesini tek sistemde birleştirmektedir. Bu yapı, sonraki aşamalarda eklenecek belge segmentasyonu ve çıkarım katmanı için sağlam temel oluşturmaktadır.

\newpage

# KAYNAK ARAŞTIRMASI

Kaynak araştırmasında hem gıda verisi standartları hem de bilimsel makale işleme araçları birlikte incelenmiştir. Akademik makalelerin yanında veri tabanları, açık erişim arşivleri, ontolojiler ve kullanılan yazılım ekosistemi değerlendirilmiştir.

## 1. Gıda verisi ve referans sözlükleri

OpenNutri'nin veri modeli serbest metin etiketleri yerine ortak sözlük mantığı üzerine kurulmuştur. FoodData Central [1] ve FAO/INFOODS eşleme yaklaşımı [2] incelenerek canonical food ve canonical nutrient kavramları ayrı tablolar halinde modellenmiştir. Böylece kullanıcı arayüzündeki seçimler ve crawler terim üretimi aynı sözlüğe bağlanmıştır.

FoodOn [3] gibi ontoloji tabanlı çalışmalar gıda adlarının standartlaştırılması açısından önemlidir. `entities` ve `entity_aliases` yapısı da aynı standardizasyon ihtiyacına göre seçilmiştir.

## 2. Bilimsel literatür kaynakları

PubMed Central [4] ve Europe PMC [5], açık erişimli biyomedikal ve yaşam bilimleri literatürüne düzenli erişim sağladıkları için crawler hattının temel dış kaynakları olarak değerlendirilmiştir. DergiPark [6] ise özellikle Türkçe çalışmalara ulaşmak amacıyla projeye dahil edilmiştir. Arasınav döneminde DergiPark entegrasyonu basit bir genel arama mantığından çıkarılıp dergi-sayı-makale düzeyinde yenilenebilir yerel indeks mantığına taşınmıştır. Bu değişiklik, Türkçe kaynakların daha kontrollü taranmasını sağlamıştır.

## 3. İnsan-döngülü öğrenme yaklaşımı

Human-in-the-loop yaklaşımı [7], bilimsel verilerin çıkarımı ve doğrulanmasında uzman kullanıcıyı sistemin aktif parçası olarak konumlandırır. OpenNutri'de bu yaklaşım annotator arayüzü ve `paper_label_events` üzerinden uygulanmıştır. Kullanıcıların `draft`, `done`, `skipped` ve global `definitely_no_data` işlemleri doğrudan crawler geri beslemesine dönüşmektedir.

## 4. PDF işleme ve kullanıcı arayüzü altyapısı

Makale içerikleri çoğunlukla PDF olarak dağıtıldığı için tarayıcı içinde PDF işleme kritik hale gelmiştir. PDF.js [8] tabanlı görüntüleme ve React [9] tabanlı kullanıcı arayüzü birlikte değerlendirilmiştir. Nutrient highlight özelliği için PDF metin katmanındaki parçalanmış span yapısını tarayan ek mantık geliştirilmiştir.

## 5. Kullanılan platform bileşenleri

Supabase [10], kimlik doğrulama, satır düzeyi erişim kontrolü, dosya depolama ve istemci erişimini tek altyapıda birleştirdiği için seçilmiştir. Arasınav itibarıyla annotator ve veri boru hattı aynı backend katmanını paylaşmaktadır.

Kaynak araştırmasının çıktısı olarak şu mühendislik kararları alınmıştır:

- makale bulma, ön eleme ve PDF edinmeyi ayrı aşamalar halinde kurmak,
- kullanıcı arayüzünü dinamik satır modeliyle tasarlamak,
- etiketleri olay geçmişi olarak saklamak,
- Türkçe ve İngilizce kaynaklar için ayrı hedef havuzlar kullanmak,
- feedback bilgisini yumuşak puanlama sinyali olarak kullanmak.

Bu kararların tamamı mevcut kod tabanında uygulanmıştır.

\newpage

# MATERYAL VE METOT

## 1. Genel sistem yaklaşımı

OpenNutri'nin arasınav sürümü üç ana katmandan oluşmaktadır:

- kullanıcıya görünen annotator arayüzü,
- ortak backend/veri modeli,
- çok kaynaklı crawler ve geri besleme katmanı.

Bu katmanların etkileşimi Şekil 1'de gösterilmişti. Şekil 2 ise bu akışın veri modeli ve geri besleme ilişkilerini daha ayrıntılı göstermektedir.

![Şekil 2 - Veri modeli ve feedback ilişkisi](assets/figure_2_feedback_data_model.png)

Şekil 2. Arasınav sürümünde anotasyon, olay kaydı ve crawler geri beslemesinin veri modeli içindeki ilişkisi.

## 2. Kullanılan materyaller

Projede kullanılan temel materyaller aşağıdaki gibidir:

- **Frontend çerçevesi:** React 19 + Vite
- **Backend ve depolama:** Supabase Auth, PostgreSQL, Storage
- **PDF işleme:** `react-pdf` ve PDF.js
- **Veri boru hattı dili:** Python
- **Referans veri kaynağı:** USDA FoodData Central [1]
- **Makale kaynakları:** Europe PMC [5], PubMed Central [4], OpenAlex, Semantic Scholar, DergiPark [6]
- **Embedding katmanı:** `sentence-transformers` tabanlı İngilizce + çok dilli ikili gömme yapısı

Bu bileşenler, gereksinimlere göre iki tarafta kullanılmıştır: kullanıcı iş akışını yöneten web uygulaması ve makale havuzunu besleyen veri boru hattı.

## 3. Backend ve veri modeli yöntemi

Backend tarafındaki temel karar, tüm sistemi tek bir ortak veri modeli etrafında toplamak olmuştur. Bu model dört ana parçadan oluşur: ortak gıda ve nutrient sözlüğü, sisteme alınan makaleler ve arama kanıtları, uzman anotasyon verisi ve kullanıcı kararlarını geri besleme olarak saklayan olay kayıtları.

Bu yapı arayüzü, crawler'ı ve geri besleme mantığını aynı veri modeli üzerinde birleştirir. Kullanıcı arayüzünde seçilen gıda ve nutrient adları ile crawler tarafında kullanılan terimler aynı referans sözlüğe dayanır. Bir makalenin sisteme giriş kaydı ile kullanıcı anotasyonları da aynı makale kaydı etrafında tutulur.

Şekil 3, canlı Supabase yapısının kod içindeki kaynak karşılığı olan `apps/expert-annotator/migration.sql` temel alınarak hazırlanmış, sadeleştirilmiş bir veritabanı özeti sunmaktadır.

![Şekil 3 - Veritabanı şema özeti](assets/figure_3_database_schema.png)

Şekil 3. Arasınav sürümündeki temel veritabanı yapısının, projeyi anlamayı kolaylaştıracak dört sorumluluk alanı altında özetlenmiş görünümü. Şema, `migration.sql` üzerinden sadeleştirilerek hazırlanmıştır.

Backend güvenliği için satır düzeyi güvenlik (RLS) kullanılmıştır. Kullanıcılar kendi anotasyonlarını yönetebilirken sistem servis rolü crawler yüklemeleri, ETL ve bakım işlemleri için geniş yetkiye sahiptir. Bu, çok kullanıcılı yapı için gerekli temel güvenlik önlemidir.

## 4. Annotator arayüzü yöntemi

Annotator arayüzü, uzman kullanıcının bir makaleyi okuyup aynı anda yapılandırılmış veri girebildiği çalışma ekranı olarak tasarlanmıştır. Kullanıcı sisteme alınmış makaleyi açar, varsa önceki kaydını görür ve çalışmasına kaldığı yerden devam eder.

Arayüz iki ana prensiple tasarlanmıştır. Kullanıcı gerektiği kadar food item ve her food item altında gerektiği kadar nutrient değeri ekleyebilir. PDF görüntüleme ile form aynı çalışma ekranında birleşir; kullanıcı belgeyi okurken ilgili nutrient ifadelerini görüp daha hızlı veri girişi yapabilir.

Bu bölümde özellikle üç davranış önemlidir:

- test mode ile gerçek veritabanına yazmadan güvenli deneme yapılabilmesi,
- global "definitely no data" işaretleme ve kısa süreli geri alma akışı,
- boş placeholder kartların `food_item_count` değerini şişirmesini önlemek için geçerli food item'ların sayılması.

Şekil 4, crawler hattının aşamalı akışından üretilen sayısal özeti göstermektedir.

![Şekil 4 - Örnek crawler aşama özeti](assets/figure_4_crawler_funnel_example.png)

Şekil 4. Temsili bir Türkçe canlı koşunun manifest özetinden türetilen aşama sayıları.

Şekil 5, annotator ekran görüntüsü için yer tutucudur.

![Şekil 5 - Annotator ekran görüntüsü yer tutucu](assets/figure_5_annotator_placeholder.png)

Şekil 5. Nihai teslimden önce bu görsel, çalışan annotator ekranının gerçek ekran görüntüsü ile değiştirilmelidir. En pratik yol, `docs/defense/assets/figure_5_annotator_placeholder.png` dosyasını gerçek ekran görüntüsü ile aynı ad altında değiştirip export betiğini yeniden çalıştırmaktır. Görselde PDF viewer, vurgulanmış nutrient örneği, food item formu ve ilerleme alanı aynı karede görünmelidir.

## 5. Crawler, filtreleme ve edinme yöntemi

Crawler tarafı kademeli seçim yapan bir boru hattı olarak tasarlanmıştır. Temel yaklaşım üç aşamadan oluşur:

- **Search:** Europe PMC, OpenAlex, Semantic Scholar ve DergiPark gibi kaynaklardan metadata düzeyinde aday bulma
- **Filter:** Başlık ve özet üzerinde search gate ve metadata filter uygulama
- **Acquisition:** Ancak yeterince iyi bulunan adaylar için PDF indirme ve tam metin doğrulama

Bu ayrım önemli bir mühendislik kararıdır. Çünkü tüm adayların PDF'ini indirmek hem pahalı hem de gereksizdir. Ön eleme sayesinde daha az sayıda ama daha güçlü aday tam metin aşamasına geçmektedir.

Filtreleme mantığı üç ana sinyal grubuna dayanır: konu ile ilişkili kelime ve birim ipuçları, semantik benzerlik/embedding uygunluğu ve önceki kullanıcı etiketlerinden öğrenilen geri besleme sinyalleri.

Crawler tarafında iki yetenek belirleyicidir: İngilizce ve Türkçe literatür için ayrı hedef havuzların yönetilmesi ve geri beslemenin sorgu partileri düzeyinde de değerlendirilmesi.

Türkçe kaynaklar için DergiPark entegrasyonu yeniden ele alınmıştır. Eski geniş ve kontrolsüz tarama mantığı yerine dergi ve sayı bazında yenilenebilir yerel indeks dosyaları kullanılmaya başlanmıştır. Bu yöntem, özellikle Türkçe literatürde kaynak kalitesini ve izlenebilirliği artırmaktadır.

## 6. Feedback ve paper-stock yenileme yöntemi

`feedback/update_terms.py` betiği, kullanıcı olaylarından öğretici sinyaller üretir. Anlamlı veri kaydedilen makaleler olumlu örnek, açık biçimde veri içermeyen veya tekrarlı biçimde atlanan makaleler olumsuz örnek olarak değerlendirilir. Çelişkili durumlar öğrenme dışında bırakılır.

Bu geri besleme daha sonra crawler tarafından yumuşak puanlama sinyali olarak kullanılır.

Son kullanıcıya yeterli makale kalmadığında `ensure_paper_stock.py` devreye girmektedir. Bu betik mevcut EN/TR makale sayılarını kontrol etmekte, gerekiyorsa geri beslemeyi güncellemekte, DergiPark indeksini yenilemekte, crawler'ı çalıştırmakta ve sonuçları Supabase'e yüklemektedir. Böylece anotasyon arayüzü ile veri toplama hattı arasında operasyonel bir bağ kurulmuştur.

## 7. Mevcut sınırlar

Bu rapor, çalışan ilk üç dönem hedefi ile onları destekleyen veri ve geri besleme altyapısına odaklanmaktadır. Belge segmentasyonu ve LLM tabanlı çıkarım süreci sonraki aşamanın konusudur.

Annotator ekran görüntüsü bu raporda yer tutucu olarak bırakılmıştır. Nihai teslimden önce en güncel arayüz görüntüsü eklenmelidir.

\newpage

# KAYNAKLAR

1. U.S. Department of Agriculture. FoodData Central. https://fdc.nal.usda.gov/
2. FAO/INFOODS. Guidelines for Food Matching. Rome: Food and Agriculture Organization of the United Nations, 2012.
3. Dooley DM, Griffiths EJ, Gosal GS, et al. FoodOn: a harmonized food ontology to increase global food traceability, quality control and data integration. *npj Science of Food*. 2018;2(1):23.
4. National Center for Biotechnology Information. PubMed Central (PMC). https://pmc.ncbi.nlm.nih.gov/
5. Europe PMC. https://europepmc.org/
6. DergiPark Akademik. https://dergipark.org.tr/
7. Monarch RM. *Human-in-the-Loop Machine Learning*. Manning Publications; 2021.
8. Mozilla. PDF.js. https://mozilla.github.io/pdf.js/
9. React Documentation. https://react.dev/
10. Supabase Documentation. https://supabase.com/docs

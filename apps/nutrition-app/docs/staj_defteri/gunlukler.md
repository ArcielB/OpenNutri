# OpenNutri — Mobil Uygulama Çalışma Günlükleri

Bu metin, mevcut uygulama ve doğrulanmış teknik kayıtlar temel alınarak hazırlanmış
30 günlük bir içerik taslağıdır. Gün numaraları önerilen anlatım sırasıdır; fiilî
çalışma tarihlerini veya tek bir öğrencinin katkısını kanıtlamaz. Öğrenci, kendisine
ait olmayan geliştirmeleri inceleme/entegrasyon çalışması olarak düzeltmeli; tarih,
kurum ve kişisel katkı alanlarını sorumlu kişiyle doğrulamalıdır. Metin yapay zekâ
desteğiyle hazırlanmıştır. İmza ve onay alanları ilgili yetkililere bırakılmıştır.

## 01 | Uygulama Konusunun ve Kullanıcı İhtiyaçlarının Belirlenmesi

İlk çalışma başlığında, günlük beslenme kayıtlarını kolaylaştıran bir mobil uygulamanın ihtiyaçları ele alındı. Kullanıcının tükettiği besinleri tek tek araması ve her kayıt için uzun formlar doldurması, kullanım süresini artıran bir sorun olarak değerlendirildi. OpenNutri uygulamasında temel amaç; besinleri arayarak veya sesle kaydetmek, günlük toplamları görmek ve yanlış kayıtları kolayca düzeltebilmek olarak belirlendi. Tasarımın yalnızca ilk kayıt işlemini değil, daha sonra yapılacak kontrol ve düzenlemeyi de kapsaması gerektiği üzerinde duruldu.

Gereksinimler; besin arama, porsiyon seçimi, öğün günlüğü, besin ögesi raporu ve kişisel hedefler şeklinde ayrıldı. Sesli kayıt, ana ekran araç takımı ve kişiselleştirilmiş öneriler bu temel akışı tamamlayan özellikler olarak ele alındı. Yapay zekânın besin adını anlamak için kullanılmasına karşılık, kaydedilen besin değerlerinin mevcut veri servisinden alınması benimsendi. Böylece öneri üretme ile sayısal beslenme hesabının sorumlulukları birbirinden ayrıldı.

Çalışmanın kapsamı Android öncelikli mobil uygulama ile sınırlandırıldı. Besin verilerinin hazırlanması, bilimsel yayınların toplanması ve farklı kullanıcıların etiketleme işlemleri bu uygulama geliştirme çalışmasına dahil edilmedi. Kullanıcı yolculuğu; uygulamayı açma, besin seçme, miktarı belirtme, kaydetme ve sonucu kontrol etme adımlarıyla düzenlendi. Bu yaklaşım, sonraki sayfalarda anlatılacak geliştirmeler için anlaşılır bir başlangıç oluşturdu.

## 02 | Flutter Geliştirme Ortamı ve Dart Proje Yapısı

Bu çalışma gününde mobil uygulamanın geliştirme ortamı ve kullanılan araçlar incelendi. Arayüzün Flutter ile, uygulama mantığının Dart diliyle oluşturulduğu proje yapısı ele alındı. Android tarafındaki derleme ve cihaz özelliklerinin Android SDK ile Gradle üzerinden yönetildiği görüldü. Geliştirme ortamının doğru çalışmasının yalnızca editörün açılmasıyla değil, bağımlılıkların çözülmesi ve örnek bir derlemenin tamamlanmasıyla anlaşılabileceği değerlendirildi.

Projenin pubspec.yaml dosyasında uygulama adı, sürümü ve paket bağımlılıkları incelendi. Ağ istekleri için http, yerel kayıtlar için shared_preferences, mikrofon kaydı için record ve geçici dosya konumu için path_provider paketlerinin kullanıldığı belirlendi. Kimlik doğrulama bağlantısı ayrı bir paket üzerinden sağlandı. Hazır paketlerin bütün uygulamayı oluşturmadığı; bunların uygulamanın veri modeli, ekranları ve hata yönetimiyle birleştirilmesi gerektiği üzerinde duruldu.

Flutter komutlarının görevleri ayrıştırıldı. Bağımlılıkları hazırlama, statik kod analizi, otomatik test ve Android kurulum paketi üretme işlemleri ayrı doğrulama adımları olarak ele alındı. Kaynak kod ile derleme sırasında üretilen dosyaların aynı amaçla kullanılmadığı not edildi. Git sürüm kontrolü sayesinde bir değişikliğin hangi dosyalara etki ettiğinin izlenmesi ve çalışan sürümlerin korunması, geliştirme sürecinin temel bir parçası olarak değerlendirildi.

## 03 | Uygulamanın Katmanlara Ayrılması

Bugünkü çalışmanın odağı, uygulama kodunun sorumluluklara göre düzenlenmesiydi. Tüm işlemlerin tek bir ekran dosyasında bulunması durumunda, arayüz değişikliklerinin veri kaydı veya ağ istekleriyle iç içe geçebileceği değerlendirildi. Bu nedenle proje; veri modelleri, servisler, durum yönetimi, ekranlar ve ortak arayüz bileşenleri üzerinden incelendi. Her bölümün tek bir temel sorumluluğa odaklanması amaçlandı.

Model sınıflarının besin, porsiyon ve günlük kayıt bilgilerini temsil ettiği; servislerin dış sistemlerle iletişim ve yerel saklama işlerini yürüttüğü görüldü. AppController sınıfı, seçilen tarih ve kayıt listesi gibi ortak uygulama durumunu yönetirken ekranlar bu durumu kullanıcıya sunmaktadır. Örneğin bir öğün kaydedildiğinde ekran doğrudan depolama ayrıntılarıyla uğraşmamakta, işlemi denetleyiciye iletmektedir. Bu ayrım, kayıt davranışının arayüz açılmadan test edilebilmesine de yardımcı olmaktadır.

Uygulamanın başlangıç akışı da ele alındı. Yerel kayıtların yüklenmesi ile uzaktaki kimlik doğrulama hazırlığının farklı ihtiyaçlar olduğu belirlendi. Kullanıcı daha önce kaydettiği günlüğü görmek için yapay zekâ servisini beklememelidir. Servis istemcilerinin gerektiğinde test nesneleriyle değiştirilebilmesi sayesinde, gerçek ağ bağlantısı gerektirmeyen senaryolar hazırlanabildiği görüldü. Günün sonunda katmanlı yapının bakım, hata ayıklama ve test kolaylığına katkısı netleştirildi.

## 04 | Ana Ekran, Tema ve Sayfalar Arası Geçiş

Bu çalışma gününde uygulamanın ana gezinme yapısı ve ortak görsel dili üzerinde duruldu. Kullanıcının en sık yapacağı işlemlerin günlük kayıt ekranında kolayca bulunması hedeflendi. Günlük özet, öğün listeleri, sesle kayıt ve besin arama girişleri aynı kullanıcı akışının parçaları olarak ele alındı. Renklerin ve metin büyüklüklerinin bütün ekranlarda tutarlı kullanılması için ortak tema yapısından yararlanıldı.

Ana gezinme içinde günlük, besin ögesi raporu, koç, Oracle ve ayarlar ekranlarının ilişkisi incelendi. Flutter bileşenleri kullanılarak kart, düğme ve liste gibi tekrar eden arayüz parçaları ortaklaştırıldı. Bir ekranın yalnızca başlık ve renklerden oluşmadığı; boş içerik, yüklenme ve hata durumlarının da tasarımın parçası olduğu görüldü. Henüz hiç kayıt yapılmamış bir gün için kullanıcıyı ilk işlemine yönlendiren açıklamaların önemi değerlendirildi.

Ekranlar arası geçişte seçilen günün ve uygulama durumunun korunması ele alındı. Kullanıcının geçmiş bir günü incelerken yanlışlıkla bugünün toplamlarını görmemesi gerektiği belirtildi. İçerik genişliğinin sınırlandırılması ve kaydırılabilir alanlar kullanılması, farklı ekran ölçülerinde okunabilirliği destekledi. Bu çalışmalar sonucunda görsel düzen ile uygulama davranışının birlikte tasarlanması gerektiği anlaşıldı; yalnızca güzel görünen değil, işlem sırası anlaşılır bir ana yapı oluşturuldu.

## 05 | Besin ve Günlük Kayıt Modellerinin Oluşturulması

Bugün uygulamanın taşıdığı verilerin Dart sınıflarıyla nasıl temsil edildiği incelendi. Besin arama sonucunda görülen kısa bilgi ile seçilen besinin ayrıntıları aynı veri yapısında değerlendirilmedi. Besin kimliği, adı, porsiyon seçenekleri ve besin ögeleri gibi alanlar tanımlandı. Böylece kullanıcıya gösterilen metin ile kaydın hangi kaynak besine ait olduğunu belirleyen kimlik birbirinden ayrıldı.

Günlük kayıt için DiaryEntry modeli ele alındı. Bir kayıt; tarih, öğün türü, besin kimliği, miktar ve hesaplanmış besin değerleriyle birlikte tutulmaktadır. Kahvaltı, öğle yemeği, akşam yemeği ve ara öğün seçenekleri sınırlı bir tür üzerinden temsil edildi. Sesle oluşturulma ve daha sonra gözden geçirilme gereksinimi de ayrı işaretlerle saklandı. Bu işaretlerin kaydın kaynağı ve güven düzeyi hakkında bilgi verdiği, sayısal besin değerlerinin yerine geçmediği açıklandı.

Verilerin JSON biçimine dönüştürülmesi ve tekrar nesne olarak okunması incelendi. Önceki uygulama sürümlerinden gelen kayıtlarda yeni alanların bulunmayabileceği dikkate alındı. Uygun varsayılan değerlerle geriye dönük okunabilirlik desteklendi. Günlükte yalnızca uzak besinin kimliğini saklamak yerine, kayıt anındaki besin değerlerinin de tutulmasının eski kayıtların tutarlılığını koruduğu görüldü. Veri modelinin arayüzden önce netleştirilmesi, sonraki hesaplama ve saklama işlemlerini kolaylaştırdı.

## 06 | Besin Arama Servisinin Uygulamaya Bağlanması

Bu çalışma gününde mevcut besin servisine HTTP üzerinden erişim ele alındı. Mobil uygulamanın doğrudan veritabanı tablolarına bağlanması yerine, tanımlı servis uç noktalarıyla iletişim kurması benimsendi. CoreApiClient sınıfı üzerinden arama, besin ayrıntısı ve servis durumu işlemleri ayrıştırıldı. Bu çalışma hazır servisin mobil uygulamaya entegrasyonunu kapsamaktadır; besin veritabanının oluşturulması bu kapsamda değerlendirilmemiştir.

Arama metninin başındaki ve sonundaki boşluklar temizlenerek istek hazırlanması incelendi. Boş bir metin için gereksiz ağ isteği gönderilmemesi sağlandı. Servisten gelen JSON yanıtı uygulamanın beklediği model sınıflarına dönüştürüldü. Başarısız HTTP durumları ile geçersiz yanıt biçimlerinin aynı şey olmadığı görüldü. Hata durumunda boş sonuç varmış gibi davranmak yerine kullanıcıya uygun geri bildirim verilmesi gerektiği değerlendirildi.

Besin ayrıntıları için bellekte tutulan küçük bir önbellek kullanımı ele alındı. Aynı besin kısa süre içinde tekrar açıldığında, daha önce alınan ayrıntının yeniden kullanılmasının gereksiz istekleri azaltabileceği görüldü. Bu önbelleğin kalıcı ve tam çevrimdışı bir besin veritabanı olmadığı özellikle ayrıştırıldı. Servis adresinin derleme ayarıyla değiştirilebilmesi, geliştirme ve kullanım ortamlarının birbirinden ayrılmasını kolaylaştırdı. Günün sonunda arayüzden bağımsız, yeniden kullanılabilir bir servis istemcisi yapısı incelendi.

## 07 | Asenkron Arama ve Eski Sonuçların Engellenmesi

Bugünkü çalışmada arama ekranında aynı anda devam edebilen isteklerin oluşturduğu sorun ele alındı. Kullanıcı ilk kelimeyi yazdıktan hemen sonra arama metnini değiştirebilir. İlk isteğin yanıtı daha geç geldiğinde, yeni aramaya ait sonuçların üzerine eski sonuçların yazılması mümkündür. Bu durumun yalnızca ağ hızına bağlı bir görüntü sorunu olmadığı, yanlış besinin seçilmesine de yol açabileceği değerlendirildi.

Arama işlemleri için güncellik kontrolü sağlayan bir istek sırası kullanımı incelendi. Yeni bir arama başladığında önceki yanıtların artık geçerli olmadığının anlaşılması sağlandı. Kullanıcı arama alanını tamamen temizlediğinde, o sırada devam eden bir isteğin listeyi tekrar doldurmaması gerektiği dikkate alındı. Aynı yaklaşım, standart arama ile gönderilmiş metnin anlamsal çözümlenmesinden dönen sonuçların birlikte yönetilmesinde de uygulandı.

Yükleniyor, sonuç bulunamadı ve bağlantı hatası durumları ayrı arayüz davranışları olarak ele alındı. Asenkron işlemlerde ekran kapandıktan sonra arayüzü güncellemeye çalışmamak için yaşam döngüsü kontrollerinin önemi görüldü. Geciktirilmiş test yanıtlarıyla, arama temizlendikten sonra eski sonucun görünmemesi senaryosu doğrulama kapsamına alındı. Bu çalışma, kullanıcı etkileşimi hızlı olduğunda bile ekrandaki verinin son talebi temsil etmesi gerektiğini gösterdi.

## 08 | Besin Ayrıntıları ve Kaynak Bilgisinin Gösterilmesi

Bu çalışma gününde arama listesinden seçilen besinin ayrıntılarının sunulması üzerinde duruldu. Benzer adlara sahip besinlerin hazırlanma biçimi veya veri kaynağı farklı olabileceği için, yalnızca besin adının gösterilmesinin yeterli olmadığı görüldü. Ayrıntı ekranında porsiyon seçenekleri, mevcut besin ögeleri ve kaynak bilgisi birlikte değerlendirildi. Kullanıcının kaydı oluşturmadan önce hangi besini seçtiğini anlayabilmesi amaçlandı.

Besin değerlerinin hangi miktar esas alınarak verildiği açıklandı. Uygulamada kullanılan uygun kaynak değerler, yüz gram yenilebilir kısım üzerinden hesaplanmaktadır. Kullanıcının seçtiği miktar değiştiğinde bu değerlerin nasıl ölçeklendiğinin anlaşılır olması hedeflendi. Kaynak ve hesaplama bilgilerine erişim sunulması, ekranda görülen sonucun izlenebilirliğini artırdı. Yapay zekâ tarafından önerilen bir adın tek başına doğrulanmış bir besin kaydı olmadığı özellikle ayrıştırıldı.

Kaydedilmiş bir besinin ayrıntılarında miktar düzenleme ve besin eşleşmesini değiştirme seçenekleri incelendi. Yanlış besin seçilmişse yalnızca gram değerini düzeltmenin yeterli olmayacağı görüldü. Değiştirme işlemi tekrar arama ve porsiyon seçimine yönlendirilerek mevcut kaydın kimliği korunmaktadır. Bu yaklaşım, kullanıcıya kaydı silip baştan oluşturmak zorunda kalmadan düzeltme imkânı sundu. Günün sonunda veri kaynağını göstermek ile düzenleme kolaylığı sağlamak aynı kalite yaklaşımının parçaları olarak değerlendirildi.

## 09 | Porsiyon ve Yenilebilir Miktar Hesaplamaları

Bugünkü çalışma, seçilen miktarın besin değerlerine doğru yansıtılması üzerine yapıldı. Kaynakta yüz gram için verilen bir değerin, kullanıcının tükettiği yenilebilir gram miktarıyla orantılı hesaplanması ele alındı. Örneğin yalnızca hesaplama mantığını açıklamak için kullanılan yüz gramlık bir değerin, yüz elli gramda bir buçuk katsayısıyla çarpılması gerektiği gösterildi. Bu örneğin gerçek bir besinin ölçülmüş değeri yerine genel hesap kuralını temsil ettiği belirtildi.

Satın alınan ağırlık ile yenilen ağırlığın her zaman aynı olmadığı değerlendirildi. Kabuk veya kemik gibi yenmeyen kısımlar bulunabileceğinden, uygulamada bu iki miktar ayrı alanlarda tutulmaktadır. Dönüşüm ancak seçilen besine doğrudan bağlı ve kullanılabilir bir katsayı varsa yapılmaktadır. Benzer isimli başka bir besinin katsayısını kullanmanın hatalı sonuç oluşturabileceği görüldü. Uygun katsayı bulunmadığında belirsizliğin sessizce tahmin edilmesi yerine kullanıcı düzeltmesi istenmektedir.

Miktar girişinde sıfır, negatif ve sonlu olmayan değerlerin kabul edilmemesi ele alındı. Ondalık virgül kullanan girişlerin işlenmesi, Türkçe kullanım alışkanlıkları bakımından değerlendirildi. Porsiyon düzenlendiğinde mevcut besin değerlerinin aynı oranla güncellenmesi ve eski kaydın kimliğinin korunması incelendi. Böylece hesaplamanın, kullanıcıya sunulan ağırlık türüyle tutarlı yürütülmesinin önemi ortaya konuldu.

## 10 | Günlük Verilerinin Telefonda Saklanması

Bu çalışma gününde besin günlüğünün uygulama kapatıldıktan sonra korunması ele alındı. Yerel saklama katmanında SharedPreferences üzerinden JSON kayıtlarının kullanıldığı görüldü. Günlük girişleri, hedefler, kişisel profil ve bazı kullanım tercihleri ayrı anahtarlar altında tutulmaktadır. Verilerin tek bir karmaşık metin yerine tanımlı modeller üzerinden dönüştürülmesi, okuma ve yazma işlemlerinin anlaşılmasını kolaylaştırdı.

Kayıtların saklanmasında besin adı ve kimliğine ek olarak miktar, öğün, tarih ve besin değerlerinin tutulması incelendi. Uygulama yeniden açıldığında bu bilgilerden aynı günlük nesnelerinin oluşturulması sağlanmaktadır. JSON dönüşümünün test edilmesi, verinin yalnızca bellekte doğru görünmesinin yeterli olmadığını gösterdi. Alan adlarının ve varsayılan değerlerin korunması, eski kayıtların yeni sürümlerde okunabilmesi bakımından değerlendirildi.

Kullanılan yöntemin sınırları da ele alındı. Yerel kayıt, bulut eşitlemesi veya kullanıcıya sunulan bir yedekleme sistemi anlamına gelmemektedir. Mevcut sürümde dışa aktarma ve geri yükleme arayüzü bulunmadığı not edildi. Depolama hatası durumunda uygulamanın başarı göstermemesi gerektiği üzerinde duruldu. Günün sonunda mobil uygulamalarda kalıcılığın yalnızca bir kaydetme komutu yazmak değil; veri biçimini, hata durumunu ve sonraki açılıştaki davranışı birlikte yönetmek olduğu değerlendirildi.

## 11 | Durum Yönetimi, Hızlı Görünüm ve Geri Alma

Bugünkü çalışmada günlük kayıt işlemlerinin ortak bir denetleyici üzerinden yönetilmesi incelendi. Kullanıcı yeni bir besin eklediğinde, listenin ve günlük toplamların hemen güncellenmesi hedeflendi. AppController yapısı, kayıt değişikliklerini ekranlara bildirmekte ve yerel saklama işlemlerini yönetmektedir. Böylece farklı ekranların ayrı ayrı güncel veri tutmaya çalışmasından kaynaklanabilecek tutarsızlıklar azaltıldı.

Arayüzün hızlı tepki vermesi için kayıt önce bellekte görünür hâle getirilmektedir. Ancak depolama işlemi tamamlanmadan kalıcılığın kesinleştiği varsayılmamaktadır. Birbirini takip eden yazma işlemlerinin sıraya alınması, daha eski bir kayıt listesinin daha yeni listenin üzerine yazılmasını engelleyen önemli bir ayrıntı olarak değerlendirildi. Hata durumlarında görünümün kayıt sonucuyla uyumlu kalması için geri dönüş davranışları incelendi.

Yanlış eklenen bir işlemin Geri al seçeneğiyle kolayca düzeltilmesi ele alındı. Aynı sesli yanıtın yeniden işlenmesi durumunda çift kayıt oluşmaması için kimlik denetimleri kullanıldığı görüldü. Tekrar kullanılan bir besinin yeni gün için kopyalanması sırasında ise yeni kayıt kimliği oluşturulmaktadır. Bu fark, gerçek bir yeni işlem ile aynı işlemin yanlışlıkla tekrar edilmesini ayırmaktadır. Çalışma sonucunda hızlı arayüz ile güvenilir veri yönetiminin birlikte tasarlanması gerektiği anlaşıldı.

## 12 | Kayıt Düzenleme ve İptalde Verinin Korunması

Bu çalışma gününde kayıt düzenleme sırasında veri kaybını önleyen akış ele alındı. Bir öğünü düzenlemek için mevcut kayıtları önce silmek, kullanıcının geri dönmesi veya işlemi iptal etmesi durumunda yemeğin kaybolmasına neden olabilmektedir. Bu nedenle özgün kayıtların düzenleme tamamlanıncaya kadar korunması gerektiği değerlendirildi. Değişikliklerin ancak Kaydet işlemi başarılı olduğunda mevcut kayıtların yerine geçirilmesi benimsendi.

Tek bir besinin miktarını değiştirme, öğününü düzenleme ve yanlış besin eşleşmesini değiştirme işlemleri incelendi. Miktar değişiminde kaydın tarihi ve kimliği korunarak besin değerleri yeni orana göre hesaplanmaktadır. Besin değiştirildiğinde ise yeni kaynak kaydının ayrıntıları kullanılmaktadır. Böylece kullanıcının bir düzeltme yaparken yanlışlıkla ikinci bir yemek kaydı oluşturması önlenmektedir. Toplu düzenlemede de bütün değişikliklerin aynı kayıt işlemi içinde ele alınması üzerinde duruldu.

Miktar penceresinin kapatılması sırasında ortaya çıkan yaşam döngüsü sorunu ayrıca değerlendirildi. Metin alanına ait denetleyicinin kapanış animasyonu bitmeden yok edilmesinin hataya yol açabileceği görüldü. Alanın kendi durumunu yönetmesiyle bu sorun giderildi. İptalin kaydı değiştirmemesi, ondalık virgülün kabul edilmesi ve besin değiştirmede kimliğin korunması otomatik testlerle kapsandı. Bu örnek, küçük bir arayüz penceresinin bile veri güvenilirliğini etkileyebildiğini gösterdi.

## 13 | Günlük Enerji ve Makro Besin Toplamları

Bugünkü çalışmada birden fazla besinin günlük toplamlarının hesaplanması ele alındı. Protein, karbonhidrat ve yağ miktarları seçilen güne ait kayıtlar üzerinden birleştirilmektedir. Aynı besin ögesinin farklı kayıtlar içinde bulunması durumunda birim ve kimlik bilgilerinin dikkate alınması gerektiği değerlendirildi. Tarih seçiminin hesaplamanın girişini belirlediği, bütün günlüğün tek toplam altında birleştirilmemesi gerektiği görüldü.

Enerji hesabında kaynakların farklı alan adları kullanabildiği incelendi. Bazı besinlerde doğrudan enerji alanı, bazılarında ise Atwater yöntemleriyle verilen enerji alanları bulunmaktadır. Yalnızca tek bir alan adını toplamanın bazı besinleri dışarıda bırakabileceği; bütün enerji alanlarını birlikte toplamanın da aynı besini iki kez sayabileceği anlaşıldı. Çözüm olarak her besin için uygun enerji değeri seçildikten sonra günlük toplamın oluşturulması ele alındı.

Bu davranış, farklı enerji alanlarına sahip örnek kayıtlar üzerinden test kapsamına alındı. Besin ekleme, miktar düzenleme ve silme işlemlerinin toplamları tutarlı biçimde değiştirmesi incelendi. Sayıların kullanıcıya okunabilir biçimde yuvarlanması ile hesaplama sırasında kullanılan değerlerin birbirinden ayrılması gerektiği değerlendirildi. Günün sonunda doğru toplam üretmenin basit bir toplama işleminden daha fazlası olduğu; kaynak alanlarının anlamının ve her kaydın hesaplama temelinin bilinmesi gerektiği görüldü.

## 14 | Besin Ögesi Raporu ve Eksik Verinin Yorumlanması

Bu çalışma gününde günlük kayıtlardan oluşan ayrıntılı besin ögesi raporu incelendi. Kullanıcının yalnızca kalori toplamını değil, kaydedilen besinlerde bulunan diğer bileşenleri de görebilmesi amaçlandı. Besin ögelerinin gruplar hâlinde gösterilmesi ve birimlerinin korunması, uzun bir listenin daha okunabilir olmasını sağladı. Henüz kayıt bulunmayan günlerde boş bir tablo yerine açıklayıcı bir görünüm kullanılması değerlendirildi.

Eksik kaynak verisi ile gerçek sıfır değerinin aynı anlama gelmediği üzerinde duruldu. Bir besinin vitamin bilgisi veri kaynağında bulunmuyorsa, bundan o vitaminin hiç alınmadığı sonucu çıkarılamaz. Özellikle yapay zekâya gönderilen günlük bağlamda, eksik ölçümlerin boş değer olarak ve veri kapsamını açıklayan sayılarla temsil edilmesi incelendi. Farklı mikrogram yazımlarının aynı birimi ifade edebileceği de birim normalleştirme konusu olarak ele alındı.

Günlük hedeflerin ekrandaki toplamlarla karşılaştırılmasının kullanıcıya genel bir fikir verdiği, ancak tıbbi değerlendirme yerine geçmediği belirtildi. Günlüğün eksik doldurulması veya kaynakta bazı değerlerin bulunmaması sonuçların yorumunu sınırlandırmaktadır. Bu nedenle raporun sunduğu bilgi ile sunmadığı kesinlik birbirinden ayrıldı. Çalışma, veri görselleştirmenin yalnızca değerleri listelemek değil, kullanıcının bu değerleri yanlış yorumlamasını önleyecek bağlamı da sağlamak olduğunu gösterdi.

## 15 | Kişisel Hedefler ve Ayar Formlarının Tutarlılığı

Bugünkü çalışma, kullanıcının günlük hedeflerini ve uygulama tercihlerini yönetmesi üzerine yapıldı. Kalori, protein, karbonhidrat ve yağ hedeflerinin ayarlar ekranında düzenlenebilmesi incelendi. Form alanlarının geçerli sayısal değerler üretmesi gerektiği üzerinde duruldu. Boş, negatif veya geçersiz girişlerin hesaplamalara aktarılmaması; uygun hata mesajlarının ilgili alanın yanında gösterilmesi hedeflendi.

Hedeflerin yalnızca ekranda tutulması yerine yerel depolamaya kaydedilmesi ele alındı. Böylece uygulama tekrar açıldığında aynı değerlerin kullanılabilmesi sağlanmaktadır. Başka bir ekranda beslenme şablonu uygulandığında ayarlar alanlarının eski sayıları göstermesi sorunu incelendi. Hedefler gerçekten değiştiğinde metin alanlarının güncellenmesi, buna karşılık kullanıcının ilgisiz ve henüz kaydedilmemiş girişlerinin korunması gerektiği görüldü. Bu ayrım, otomatik güncellemenin kullanıcı düzenlemesini ezmemesi açısından önemlidir.

Profilde yer alan genel amaçların öneri bağlamına aktarılması da değerlendirildi. Kilo yönetimi veya performans gibi bir hedef seçilmesi, tek başına kişiye özgü enerji ihtiyacının hesaplandığı anlamına gelmemektedir. Mevcut uygulama kullanıcı tarafından belirlenen enerji hedefini temel almaktadır. Günün sonunda hedef yönetiminin; giriş doğrulama, kalıcı saklama ve farklı ekranlar arasında tutarlılık gerektiren ortak bir uygulama özelliği olduğu anlaşıldı.

## 16 | Mikrofon İzni ve Ses Kaydının Başlatılması

Bu çalışma gününde sesle besin kaydı özelliğinin cihaz tarafı incelendi. Kullanıcının birden fazla besini tek cümlede söyleyebilmesi için mikrofon kaydı başlatan bir ekran oluşturuldu. Kayıttan önce uygulama içi bilgilendirme ile Android mikrofon izninin farklı işlemler olduğu değerlendirildi. Kullanıcının izin vermemesi durumunda uygulamanın çökmeden elle arama seçeneğini sunması gerektiği belirtildi.

Ses kaydı için record paketi ve geçici dosya konumu için path_provider kullanımı ele alındı. Kayıt, tek kanallı ve 16 kHz örnekleme hızına sahip WAV dosyası olarak hazırlanmıştır. Bu seçim, konuşma çözümleme servisine gönderilecek sesin tutarlı biçimde üretilmesini sağlamaktadır. Kullanıcı kayıt yaparken sesin sürekli olarak sunucuya aktarılmadığı; gönderimin kayıt tamamlandıktan sonra gerçekleştirildiği incelendi. Böylece kayıt alma ile ağ üzerinden çözümleme aşamaları birbirinden ayrıldı.

Kayıt ekranında boşta, kaydediliyor, durduruldu, izin verilmedi ve hata gibi durumların ayrı temsil edilmesi ele alındı. Düğmelerin bu duruma göre davranması, aynı anda çelişen işlemler başlatılmasını önlemektedir. Kayıt sırasında geçen süre ve ses düzeyinin gösterilmesi kullanıcıya geri bildirim sağlamaktadır. Günün sonunda mikrofon erişiminin yalnızca bir paket çağrısından ibaret olmadığı; izin, dosya yönetimi ve kullanıcı arayüzüyle birlikte tasarlanması gerektiği görüldü.

## 17 | Sessizlik Algılama ve Geçici Ses Dosyalarının Yönetimi

Bugünkü çalışmada ses kaydının ne zaman bitirileceği ele alındı. Kullanıcının her kayıt sonunda tekrar düğmeye basmasını azaltmak için sessizlik algılama yaklaşımı incelendi. Ses düzeyi belirli aralıklarla izlenmekte ve konuşma sonrasındaki kesintisiz sessizlik süresi değerlendirilmektedir. Uygulamanın mevcut kayıt ayarında yaklaşık 1,6 saniyelik son sessizlik kaydı durdurabilmektedir. İlk anda oluşan kısa sessizliğin kaydı hemen bitirmemesi için başlangıç payı bulunduğu görüldü.

Sessizlik denetimine ek olarak otuz saniyelik üst kayıt sınırı ele alındı. Bu sınır, kontrolsüz biçimde uzun ses dosyaları oluşmasını önlemeyi amaçlamaktadır. Elle durdurma, zamanlayıcı ve sessizlik algılama aynı anda tetiklenebileceğinden, durdurma işleminin tekrar tekrar çalışmaması için durum koruması kullanıldığı incelendi. Zamanlayıcıların ve ses düzeyi dinleyicilerinin kapatılması da kaynak yönetiminin bir parçası olarak değerlendirildi.

Geçici WAV dosyasının normal başarı, hata veya iptal sonrasında temizlenmesi üzerinde duruldu. Bunun, uygulama sürecinin beklenmedik biçimde sonlandırıldığı her durumda temizliğin kanıtlandığı anlamına gelmediği not edildi. Sessizlik algılayıcısının arayüzden bağımsız bir yapı olarak ele alınması test yazımını kolaylaştırmaktadır. Çalışma sonucunda otomatik durdurmanın kullanım hızını artırırken, yaşam döngüsü ve dosya yönetimi bakımından dikkatli tasarlanması gerektiği anlaşıldı.

## 18 | Ses Servisine Güvenli İstek Gönderilmesi

Bu çalışma gününde tamamlanan ses dosyasının uygulamadan çözümleme servisine gönderilmesi incelendi. VoiceApiClient sınıfında ses dosyasının çok parçalı bir HTTP isteğine eklenmesi ele alındı. Sesle birlikte dil ipucu, yerel zaman ve saat dilimi bilgisi de gönderilmektedir. Dil ipucunun desteklenen Türkçe ve İngilizce cihaz ayarlarından seçilmesi, konuşmanın yorumlanmasına yardımcı olan bir bağlam olarak değerlendirildi.

Servisin anonim oturum üzerinden alınan erişim belirteciyle çağrılması incelendi. Buradaki anonim oturumun, kullanıcıya zorunlu bir e-posta ve parola formu göstermeden isteklerin kimliğini ve sınırlarını yönetmeye yaradığı görüldü. Genel besin araması ile yetkilendirilmiş yapay zekâ istekleri ayrı tutulmaktadır. Gemini gizli anahtarının mobil uygulamaya yerleştirilmemesi, sunucu tarafındaki gizli bilgilerle istemcide kullanılabilen yapılandırmanın ayrılmasını sağlamaktadır.

İstek gönderilmeden önce dosya boyutunun kontrol edilmesi ve yanıtın tamamının alınmasına süre sınırı uygulanması ele alındı. Yalnızca HTTP başlıklarının gelmesi, yanıt gövdesinin de tamamlandığı anlamına gelmemektedir. Kimlik doğrulama hatası, zaman aşımı ve geçersiz yanıtın farklı durumlar olarak ele alınması gerektiği görüldü. Bu çalışma, ses kaydını ağ isteğine dönüştürürken dosya, bağlam, güvenlik ve süre yönetiminin birlikte düşünülmesini sağladı.

## 19 | Ses Çözümleme Sonucunun Besin Adaylarına Dönüştürülmesi

Bugünkü çalışma, ses servisinden dönen bilginin mobil uygulamada kullanılması üzerine yapıldı. Bir konuşmanın yalnızca metne çevrilmesi, günlüğe doğru besin eklemek için yeterli değildir. Metin içinde geçen besin adlarının, miktarların ve hazırlanma bilgilerinin kaynak besinlerle eşleştirilmesi gerektiği değerlendirildi. Mobil tarafta servis yanıtını temsil eden modeller ve aday besinlerin gösterimi incelendi.

Servisin döndürdüğü besin kimliği üzerinden mevcut Core ayrıntısının yüklenmesi ele alındı. Besin değerleri bu ayrıntıdan alınmakta, yapay zekânın serbest metninden sayısal beslenme verisi üretilmemektedir. Bir adayın seçilmiş olması ile eşleşmenin tamamen kesin olması farklı kavramlar olarak değerlendirildi. Alternatif adayların veya eksik alanların bulunması, kullanıcıya daha sonra düzeltme imkânı sunulmasını gerektirmektedir. Uygulamada seçimin kaynağı ve inceleme gereksinimi ayrı alanlarla taşınmaktadır.

Çözümleme sonrasında ayrıntı yükleme işlemi başarısız olursa yeniden kayıt yapmadan tekrar deneme yapılabilmesi incelendi. Kullanılabilir konuşma metni elde edilmişse bu metnin hata sırasında tamamen kaybedilmemesi gerektiği üzerinde duruldu. Elle aramaya geçiş, başarısız işlemin ardından kullanıcının görevini sürdürebilmesini sağlamaktadır. Günün sonunda sesli kayıt özelliğinin, konuşma anlama ile doğrulanmış besin seçimini birleştiren çok aşamalı bir kullanıcı akışı olduğu görüldü.

## 20 | Doğrudan Kayıt ve Sonradan Düzeltme Akışı

Bu çalışma gününde sesli kayıt sonrasındaki onay adımının kullanım süresine etkisi ele alındı. Her öğün için zorunlu bir onay ekranı göstermek yerine, kullanılabilir sonuçların doğrudan günlüğe eklenmesi yaklaşımı incelendi. Otomatik kayıt için bütün öğelerin seçilmiş besini, yüklenmiş ayrıntısı ve geçerli miktarı bulunmalıdır. Bu koşullar sağlandığında kullanıcı sonucu günlükte görüp gerektiğinde değiştirebilmektedir.

Belirsiz sonuçların kesin ölçüm gibi gösterilmemesi gerektiği değerlendirildi. Miktar belirtilmemişse mevcut uygulama yüz gramlık başlangıç değeri kullanmakta ve kaydı hızlı tahmin olarak işaretlemektedir. Bu değer kullanıcının gerçekten yüz gram tükettiğine dair bir tespit değildir. Kullanıcının açıkça söylediği miktar ise korunmaktadır. Kaydın sesle oluşturulduğu ve gözden geçirilmesi gerektiği bilgileri, sonraki düzenleme için görünür tutulmaktadır.

Toplu kayıtta herhangi bir öğe kullanılabilir bir eşleşmeye sahip değilse bütün grubun incelemeye açıldığı görüldü. Mevcut sürümün eşleşen öğeleri kaydedip kalanları ayrı bir arka plan kuyruğuna taşıdığı iddia edilmemektedir. Başarı sonrasında Geri al ve Düzenle seçenekleriyle kullanıcı kontrolünün korunması ele alındı. Bu çalışma, işlem hızını artırmak için doğruluk sorumluluğunu ortadan kaldırmak yerine, belirsizliği açıkça gösteren ve düzeltmeyi kolaylaştıran bir tasarımın önemini ortaya koydu.

## 21 | Bekleme Süreleri ve Servis Hatalarının Ayrıştırılması

Bugünkü çalışmada sesli kayıt ve yapay zekâ önerilerinde hissedilen bekleme süresi incelendi. Kullanıcının beklediği toplam sürenin yalnızca model yanıtından oluşmadığı görüldü. Oturum hazırlığı, ağ isteği, besin ayrıntılarının alınması ve yerel kayıt işlemi de akışa dahildir. Kimlik doğrulama ve servis hazırlığının kayıt sırasında engelleyici olmadan başlatılması, gereksiz beklemeyi azaltan bir yaklaşım olarak ele alındı.

Hata mesajlarının gerçek nedeni yansıtması üzerinde duruldu. Kota sınırına ulaşıldığında bağlantı kurulamadı mesajı göstermek, kullanıcıyı yanlış yönlendirmektedir. HTTP 429 yanıtının istek sınırı, bağlantı sorununun ağ hatası ve uzun süren isteğin zaman aşımı olarak ayrıştırılması incelendi. Destek servisindeki sınırlı yedek model davranışının uygulama tarafından doğru gösterilmesi de ele alındı. Yanıtı gerçekten üreten model adının sunulması, farklı bir modelin cevabını ana modelmiş gibi göstermemeyi sağlamaktadır.

Günlük öneri, Oracle ve sesli işlemlerin ortak bir istek sırasını paylaşması incelendi. Bu yapı aynı kullanıcının eşzamanlı isteklerinin birbirini engellemesini azaltmaktadır; ancak sırada bekleme süresini tamamen ortadan kaldırmamaktadır. Henüz açılmamış bir ekran için gereksiz yapay zekâ isteği yapılmaması değerlendirildi. Çalışma sonucunda performans iyileştirmesinin hız, istek sayısı, hata açıklaması ve kullanıcının devam edebilmesi arasında denge kurmayı gerektirdiği görüldü.

## 22 | Android Ana Ekran Araç Takımının Geliştirilmesi

Bu çalışma gününde kullanıcının uygulama menülerine girmeden sesli kayda ulaşmasını sağlayan Android araç takımı ele alındı. Ana ekrandaki mikrofon düğmesinin, kayıt ekranını açan bir başlangıç noktası olarak kullanılması amaçlandı. Bu özellik Flutter ekranından farklı olarak Android platformunun araç takımı altyapısını gerektirmektedir. Kotlin tarafında VoiceLogWidgetProvider sınıfı ve düğmenin tıklama davranışı incelendi.

Araç takımından gelen işlem Intent aracılığıyla MainActivity bileşenine iletilmektedir. Uygulama kapalıyken başlayan açılış ile zaten açık olan uygulamaya gelen yeni isteğin aynı şekilde ele alınamayacağı görüldü. İlk açılıştaki bekleyen işlem ve sonradan gelen yeni Intent ayrı yollar üzerinden alınmaktadır. İşlemin bir kez tüketilmesi, ekran yeniden kurulduğunda aynı sesli kayıt isteğinin tekrar başlamasını engellemektedir.

Flutter ile Android tarafı arasındaki iletişim için MethodChannel kullanımı değerlendirildi. Kanal üzerinden bekleyen sesli işlem alınmakta ve Flutter kayıt ekranına geçmektedir. Böylece cihaz tarafındaki özellik ile uygulamanın mevcut kayıt akışı yeniden kullanılabilmektedir. Araç takımının yeni bir bağımsız besin günlüğü oluşturmadığı; aynı denetleyici ve yerel saklama yapısını kullandığı belirtildi. Günün sonunda mobil geliştirmede bazı kullanıcı deneyimlerinin ortak arayüz çatısının yanında yerel platform kodu da gerektirdiği görüldü.

## 23 | Araç Takımını Ekleme ve Kayıt Sonrası Kapanış

Bugünkü çalışmada araç takımının cihazda bulunması ile ana ekrana yerleştirilmesi arasındaki fark ele alındı. Uygulamanın kurulması, araç takımının kullanıcı ana ekranına otomatik eklendiği anlamına gelmemektedir. Ayarlar ekranındaki mikrofon araç takımı ekleme seçeneğiyle Android başlatıcısına yerleştirme isteği gönderilmektedir. Son onayın kullanıcı tarafından verilmesi gerektiği açık bir biçimde anlatıldı.

Doğrudan yerleştirmeyi desteklemeyen başlatıcılar için elle ekleme açıklamaları incelendi. Kullanıcının ana ekranda boş alana basılı tutarak araç takımları listesinden OpenNutri'yi seçmesi alternatif yol olarak sunulmaktadır. Yerleştirme isteğinin kabul edilmesiyle araç takımının gerçekten yerleştirilmesinin aynı başarı ölçütü olmadığı görüldü. Bu nedenle uygulamanın yanıltıcı bir tamamlandı mesajı vermemesi üzerinde duruldu.

Araç takımından başlayan kaydın her zaman bugünün günlüğüne yönlendirilmesi ve yerel saklama tamamlandıktan sonra kısa bir bildirimle kapanması ele alındı. İsteğe bağlı geri bildirim gönderiminin bu kapanışı bekletmemesi sağlanmaktadır. Kullanıcı düzenleme veya geri alma seçerse otomatik kapanışın iptal edilmesi incelendi. Mevcut özellik, uygulama kapatıldıktan sonra işi sürdüren kalıcı bir arka plan sistemi değildir. Günün sonunda araç takımı deneyiminin başlangıç, kullanıcı onayı, kayıt ve güvenli kapanış adımlarının birlikte ele alınması gerektiği anlaşıldı.

## 24 | Beslenme Şablonları ve Hedeflere Uyarlama

Bu çalışma gününde kullanıcının hazır bir başlangıç düzeni seçebilmesini sağlayan beslenme şablonları incelendi. Dengeli beslenme, Akdeniz, yüksek protein, bitki ağırlıklı, düşük karbonhidrat ve Blue Zones esintili seçenekler uygulama içinde ayrı tanımlar olarak tutulmaktadır. Her şablonda ad, açıklama ve temel makro enerji oranları bulunmaktadır. Bu tanımların tekrar kullanılabilir veri nesneleri olarak düzenlenmesi, arayüzün aynı yapıyla farklı seçenekleri gösterebilmesini sağlamaktadır.

Seçilen şablonun kullanıcının mevcut kalori hedefinden gram hedefleri üretmesi ele alındı. Karbonhidrat ve protein için gram başına dört, yağ için dokuz kilokalorilik dönüşüm kullanımı incelendi. Genel hedefe göre bazı oranların küçük miktarda değiştirilmesiyle kişiselleştirme yapılmaktadır. Hesaplanan değerlerin ayarlar ekranına yansıması ve kullanıcı tarafından daha sonra değiştirilebilmesi değerlendirildi. Şablon seçiminin kullanıcı kontrolünü ortadan kaldırmaması amaçlandı.

Bu özelliğin sınırları açıkça ayrıştırıldı. Şablonlar haftalık yemek listesi veya kişiye özel tıbbi diyet değildir; yaş, boy, kilo ve aktivite üzerinden enerji ihtiyacı hesaplamamaktadır. Serbest metin notları önerilere bağlam sağlamakta, tek başına sayısal hedefleri yeniden hesaplamamaktadır. Günün sonunda basit bir şablon özelliğinin bile veri tanımı, dönüşüm hesabı ve kullanıcıya verilen sözün sınırları bakımından dikkatli tasarlanması gerektiği görüldü.

## 25 | Günlük Yapay Zekâ Önerileri ve Önbellek Yönetimi

Bugünkü çalışmada uygulama açıldığında sunulan günlük öneri kartı ele alındı. Kullanıcının hedefleri, seçtiği beslenme şablonu ve günlük kayıt özeti bir bağlam olarak hazırlanmaktadır. Bu bağlamı oluşturma görevinin ekran kodundan ayrılarak CoachService üzerinden yürütülmesi incelendi. Öneri alınması, kullanıcı iznine bağlı bir özellik olarak değerlendirilmiştir; yerel günlüğün temel işleyişi için zorunlu değildir.

Aynı gün için alınan önerinin sürekli yeniden üretilmemesi amacıyla önbellek kullanımı ele alındı. Ancak önbellekteki metnin başka bir tarihe ait günlükte görünmesi hatalı olacağından, önerinin tarih anahtarıyla birlikte saklanması incelendi. Hedef, profil veya kayıtlı tercihler değiştiğinde eski bağlamın geçersiz sayılması gerektiği görüldü. İstek sürerken kullanıcı bağlamı değiştirirse geç gelen yanıtın yeni ayarların üzerine yazılmaması için güncellik kontrolü kullanıldı.

Her besin düzenlemesinin otomatik olarak yeni model isteği başlatmadığı, önerinin bir günlük özet anını temsil ettiği belirtildi. Kullanıcı isterse yenileme yapabilmektedir. Yapay zekâ isteği başarısız olduğunda gösterilen cihaz içi kural tabanlı özetin farklı etiketlenmesi incelendi. Bu çalışma, öneri kalitesinin yalnızca model seçimine değil, gönderilen bağlamın doğruluğuna ve ekranda gösterilen sonucun güncelliğine de bağlı olduğunu ortaya koydu.

## 26 | Yazılı ve Sesli Koç Görüşmesi, Tercihlerin Saklanması

Bu çalışma gününde kullanıcının uygulamayla yazılı veya sesli görüşebilmesi ele alındı. Günlük öneri tek yönlü bir özet sunarken, görüşme ekranı kullanıcının ek soru sormasına olanak tanımaktadır. Mesajların kullanıcı ve asistan ayrımıyla gösterilmesi, bekleme durumunun açıklanması ve yanıt sonrasında ilgili önerilerin sunulması incelendi. Sesli görüşmede kayıt akışının tekrar kullanılmasının kod tekrarını azalttığı görüldü.

Takip sorularının anlaşılabilmesi için sınırlı sayıda önceki mesajın bağlama eklenmesi değerlendirildi. Bunun bütün konuşma geçmişinin kalıcı olarak saklandığı anlamına gelmediği belirtildi. Mevcut uygulamada görüşme geçmişi oturumla sınırlıdır; kullanıcının açıkça ifade ettiği bazı kalıcı tercihler ayrı profil bilgileri olarak korunabilmektedir. Yapay zekânın kendi önerisini kullanıcıya ait bir gerçek gibi kaydetmemesi gerektiği üzerinde duruldu.

Kaydedilen tercihlerin kullanıcıya gösterilmesi ve tek tek silinebilmesi incelendi. Günlük öneri veya Oracle yanıtlarının kendiliğinden yeni kişisel bilgi eklememesi, görüşme ile öneri üretmenin farklı sorumlulukları olarak ele alındı. Kaydetme adaylarının açık kullanıcı ifadesine dayanması yönündeki sınırın büyük ölçüde model talimatıyla sağlandığı ve kusursuz bir anlam denetimi olmadığı not edildi. Günün sonunda kişiselleştirmenin, veri saklamanın yanında görünürlük ve kullanıcı kontrolü gerektirdiği anlaşıldı.

## 27 | Oracle Ekranı ve Öneriden Besin Aramasına Geçiş

Bugünkü çalışmada kullanıcının hedeflerine uygun besin fikirleri sunan Oracle ekranı incelendi. Bu ekran, günlük kayıtları ve kişisel tercihleri bağlam olarak kullanarak öneriler oluşturmaktadır. Her önerinin yalnızca açıklama metni olarak kalmaması, uygulamada bir sonraki işleme bağlanması hedeflendi. Öneriye dokunulduğunda ilgili arama ifadesinin besin arama ekranına aktarılması ele alındı.

Öneriden günlüğe geçişte mevcut besin servisinin kullanılması önemli bir sınır olarak değerlendirildi. Kullanıcı arama sonucundan gerçek bir besin seçmekte, ayrıntılarını görmekte ve porsiyon belirlemektedir. Yapay zekâ tarafından önerilen isim doğrudan doğrulanmış kimlik veya besin değeri olarak kabul edilmemektedir. Bu yaklaşım, öneri oluşturmanın esnekliğini kaynak veriye dayalı kayıt akışıyla birleştirmektedir.

Oracle ekranının yalnızca açıldığında istek göndermesi incelendi. Değişmemiş sonuçların tekrar kullanılabilmesi ve günlük bağlam değiştiğinde eski önerilerin geçersizleşmesi, gereksiz bekleme ve istek sayısını azaltmaktadır. Servis sınırı veya bağlantı hatasında mevcut günlük verisinin korunması ele alındı. Mevcut Oracle'ın matematiksel olarak en iyi beslenmeyi hesaplayan bir optimizasyon sistemi olmadığı belirtildi. Çalışma sonucunda özelliğin, kişiselleştirilmiş besin keşfini kolaylaştıran ve doğrulama adımını koruyan bir yardımcı olarak sunulması benimsendi.

## 28 | Kullanıcı Bilgilendirmesi ve Ayarlar Ekranındaki Hatalar

Bu çalışma gününde kullanıcı verisinin hangi işlemlerde cihaz dışına gönderildiğinin açıklanması ele alındı. Günlük kayıtların telefonda saklanması ile yapay zekâ isteğinde seçili bağlamın sunucuya gönderilmesi farklı durumlar olarak değerlendirildi. Sesli kayıt izni ve koç kullanım izninin ayrı tutulması incelendi. Kullanıcının bir özelliğe izin vermesinin bütün kişiselleştirme özelliklerini otomatik açmaması gerektiği üzerinde duruldu.

Yapay zekâ sağlayıcısının veri işleme koşullarının uygulama içi bilgilendirmede açıklanması ve koç özelliğinin ayarlardan kapatılabilmesi ele alındı. İsteğe bağlı düzeltme geri bildiriminin temel kayıt işleminin önüne geçmemesi değerlendirildi. Kullanıcı izin durumunu değiştirirken devam eden eski yanıtların profil veya öneri ekranını yeniden güncellememesi için mevcut kontroller incelendi. Günlükte hassas veri bulunduğu için teknik testlerde gerçek kişisel kayıtların kullanılmaması yaklaşımı benimsendi.

Ayarlar ekranındaki servis durumu kontrolünde görülen asenkron hata ayrıca incelendi. Durum bileşeni henüz görünür alana gelmeden ağ isteği başarısız olduğunda hatanın dinleyicisiz kalabildiği görüldü. Sonucu değiştirmeden hatayı erken ele almak ve bileşen görünür olduğunda doğru durumu göstermek üzere düzenlenen yapı değerlendirildi. Bu çalışma, gizlilik seçenekleri ile hata yönetiminin kullanıcı güveni bakımından aynı derecede önemli olduğunu gösterdi.

## 29 | Otomatik Testler ve Hata Düzeltmelerinin Doğrulanması

Bugünkü çalışmada uygulamanın yalnızca elle açılarak kontrol edilmesinin yeterli olmadığı ele alındı. Birim testleriyle veri dönüşümleri ve hesaplamalar, Flutter bileşen testleriyle kullanıcı etkileşimleri değerlendirildi. Gerçek ağ bağlantısı yerine kontrollü yanıt veren test istemcilerinin kullanılması, gecikme ve hata durumlarının tekrar üretilebilmesini sağlamaktadır. Böylece yalnızca başarılı işlemler değil, başarısızlık sonrasındaki davranışlar da incelenebilmektedir.

Doğrulama kapsamında yüz gram değerlerinin miktara göre ölçeklenmesi, günlük toplamlar, JSON dönüşümü ve kayıt kopyalama senaryoları ele alındı. Düzenlemeyi iptal etmenin kaydı koruması, aynı sesli grubun iki kez sayılmaması ve arama temizlendikten sonra eski sonucun görünmemesi önemli regresyon örnekleri olarak incelendi. Araç takımı kapanışının yerel kaydı beklemesi ve Oracle'ın istek sınırı hatasını bağlantı hatasından ayırması da kapsam içinde değerlendirildi.

Uygulamanın doğrulama kaydında 44 Flutter testinin geçtiği ve statik analizde sorun bildirilmediği görüldü. Bu sayı, her cihazda ve her gerçek konuşmada kusursuz çalışma garantisi olarak yorumlanmadı. Android araç takımı işlem testleriyle gerçek ana ekran yerleşiminin farklı denemeler olduğu belirtildi. Günün sonunda bir hatanın tekrar üretilebilmesi, düzeltme sonrası aynı senaryonun test edilmesi ve kanıtın saklanmasının yazılım bakımındaki önemi değerlendirildi.

## 30 | Android Paketinin Hazırlanması ve Genel Değerlendirme

Son çalışma başlığında mobil uygulamanın teslim edilebilir Android paketi ve teknik açıklamaları ele alındı. Derleme sırasında servis adresleri ile istemci yapılandırmasının nasıl verildiği incelendi. Uygulama sürümünün paket bilgisi içinde izlenmesi, hangi düzeltmelerin hangi kurulumda bulunduğunun anlaşılması açısından değerlendirildi. Mevcut kişisel beta sürümünün 1.1.2 olduğu ve kurulumun mağaza yayınıyla aynı şey olmadığı belirtildi.

Kaynak kod, testler ve uygulama kılavuzunun birlikte teslim edilmesi üzerinde duruldu. Kurulum yönergeleri, ekranların görevleri, veri akışı ve bilinen sınırlar özetlendi. Kayıt oluşturma, miktar düzeltme, besin raporunu açma, araç takımından sesli kayda geçme ve Oracle önerisini aramaya aktarma adımları gösterim akışı olarak düzenlendi. Kullanıcı verisini temizlemeyen sürüm güncelleme yaklaşımı, günlük uygulaması için önemli bir teslim ayrıntısı olarak değerlendirildi.

Genel değerlendirmede, yerel kayıt ile ağ servislerini birleştiren bir mobil uygulamanın geliştirme sorumlulukları ortaya konuldu. Flutter arayüzü, Dart veri modelleri, asenkron işlemler ve Kotlin platform bağlantısı aynı ürün içinde birlikte çalışmaktadır. Kalıcı arka plan kayıt kuyruğu, dışa aktarma ve kapsamlı cihaz denemeleri sonraki geliştirmeler olarak ayrıldı. Çalışmaların sonucu, bütün koşullarda hatasız olduğu iddia edilen bir ürün değil; temel akışları uygulanmış, testleri ve sınırları belgelenmiş bir Android beslenme günlüğü olarak özetlendi.

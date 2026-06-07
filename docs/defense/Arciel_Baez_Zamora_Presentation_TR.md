# OpenNutri — Arciel Aliognis Baez Zamora — Savunma Sunumu (Türkçe)

> **Bu belgenin kapsamı.** Bu, Arciel Baez Zamora'nın bireysel sunum metnidir. OpenNutri'yi üç kişi geliştirdi; işler şöyle bölünüyor:
>
> - **Arciel Aliognis Baez Zamora — backend'in tamamı:** Supabase veritabanı (şema, RLS, RPC sözleşmesi, iş akışı motoru), üç aşamalı yapay zekâ çıkarım kademesi, deterministik normalleştirici ve güvene göre yönlendirme, makale tarayıcısı (crawler), geri besleme ile öğrenme döngüsü, gözetimsiz çalışan günlük operasyon otomasyonu, referans verisi ETL'i, depolama/çıkış (egress)/PDF teslimi optimizasyonu, test paketi ve dokümantasyon. (~31.800 satır backend/operasyon/şema kodu; yalnızca `migration.sql` 5.396 satır.)
> - **Ayşegül Doğan — etiketleyici frontend'inin tamamı:** PDF kanıt motoru, etiketleme çalışma alanı, gıda/besin otomatik tamamlama ve kokpit/iş akışı ekranları.
> - **Duc Huan Ngo — yeniden kullanılabilir ve full-stack parçalar:** `fuzzyMatch` motoru, öneriler/ekler özelliği, parola sıfırlama düzeltmesi, eski çakışma (conflict) sistemi, tema merkezileştirmesi, sonsuz kaydırma.
>
> Belge **birinci tekil şahısla ("ben")**, Arciel'in ağzından yazılmıştır ve beş bölümden oluşur:
> **1.** genel problem · **2.** ekip olarak nasıl çözdük · **3.** benim parçam ne, neden gerekli · **4.** yaptığım her şey, tek tek (neden gerekli · nasıl yaptım · işin zor kısmı · teknolojiler · dosyalar ve satır sayıları) · **5.** kapanış özeti.
>
> Bu belgenin İngilizcesi ayrı bir dosyada: `Arciel_Baez_Zamora_Presentation_EN.md`.

---

## 1. Genel problem nedir?

Doğru **besin bileşim verisi** — bir gıdanın ne kadar protein, yağ, demir ya da C vitamini içerdiği — her besin etiketinin, diyet uygulamasının ve beslenme kılavuzunun arkasında durur. Ama bu veri hâlâ **elle** üretiliyor: uzmanlar bilimsel makaleleri okuyup sayıları **tek tek veritabanına yazıyor.** Bu hem yavaş hem pahalı olduğu için veritabanları dar kalıyor ve hızla güncelliğini yitiriyor. Aslında veri zaten var — sürekli yayımlanıyor, sadece yapısı belirsiz PDF'lerin içine gömülü. Ama bunu elle çıkarmak ölçeklenmiyor; bir yapay zekâya denetimsiz okutmak ise bir besin etiketinde güvenilemeyecek kadar çok hatalı sayı üretiyor.

## 2. Bunu (ekip olarak) nasıl çözdük?

**OpenNutri**'yi geliştirdik. Her makaleyi bir insanın sıfırdan okuması yerine, **yapay zekâ makaleyi okuyup sayıları öneriyor; insan ise yalnızca yapay zekânın emin olmadıklarını doğruluyor.** Sistem üç parçaya ayrılıyor:

- **Bir backend hattı** (ben) — ilgili makaleleri bulur, PDF'lerini indirir, üzerlerinde yapay zekâ modelleri çalıştırarak *aday* besin değerleri üretir ve hangi adayların otomatik kabul edilecek kadar güvenilir, hangilerinin bir insana ihtiyaç duyduğuna karar verir.
- **Bir veritabanı** (ben) — her şeyi saklar ve inceleme iş akışını yürütür.
- **Etiketleyici web uygulaması** (Ayşegül'ün frontend'i) — bir insanın, sistemin emin olmadığı aday değerleri kontrol edip düzelttiği yer.

**Benim parçam backend'in tamamı: insandan önce ve insanın çevresinde olan her şey ve insanın kullandığı uygulamanın üzerine kurulduğu veritabanı sözleşmesi. Bu belgenin geri kalanı onunla ilgili.**

## 3. Benim parçam ne, neden gerekli ve ne yaptım?

**Benim parçam backend'in tamamı** — veritabanı, yapay zekâ hattı, makale tarayıcısı, öğrenme döngüsü ve bunların hepsini ücretsiz altyapıda, gözetimsiz, beş dakikada bir çalıştıran otomasyon.

**Neden gerekli?** Frontend, ancak kendisine ulaşan veri kadar iyi olabilir. Birinin tüm bilimsel literatürden doğru makaleleri *bulması*, PDF'leri zorlu yayıncı sitelerinden *indirmesi*, onları modellerle yeterince ucuza *okuması*, hangi sonuçların güvenilir, hangilerinin bir insana muhtaç olduğuna *karar vermesi*, her şeyi etiketleyicilerin, inceleyicilerin ve otomasyonun yalnızca kendi yetkileri kadarını yapabildiği bir güvenlik modeli altında *saklaması* ve **tüm sistemi**, sunucu ve bütçe olmadan *ayakta tutması* gerekiyor. Backend işte bu. O olmadan ne kuyruk olur, ne yapay zekâ ön doldurması, ne vurgulanacak kanıt, ne onaylanacak bir doğru veri, ne de tarayıcının öğreneceği bir şey.

Ayrıca projenin asıl riski de burada: sistemin otomatik kabul ettiği yanlış bir sayı doğrudan bir gıda veritabanına girer; hatalı bir RLS politikası özel veriyi sızdırır; takılı kalan bir işçi (worker) tüm hattı durdurur; yanlış makaleleri kabul eden bir tarayıcı kıt model kotasını ve etiketleyicilerin zamanını boşa harcar. Backend, "doğru, ucuz ve gözetimsiz" üçlüsünün aynı anda sağlanması gereken yer.

**Tek cümleyle ne yaptım:** Kendi kendine çalışan bir araştırma hattı kurdum. Bu hat literatürü tarar, PDF'leri almak için yayıncı bot duvarlarını aşar, üç modelli bir huniyle günde ~1.500 makaleyi eler (huni ~20 pahalı çıkarımını en iyi adaylara harcar), her modelin serbest biçimli çıktısını bir insanın göndereceği yapıyla *birebir aynı* hâle getirir, güvene göre otomatik kesinleştirme mi yoksa insana yönlendirme mi gerektiğine karar verir, her şeyi 75 politikalı bir güvenlik modeli altında saklar ve sonraki taramayı iyileştirmek için her insan kararından öğrenir — hepsi Supabase'in ve GitHub'ın ücretsiz katmanlarında. Somut olarak yedi parçanın sahibiyim; bir sonraki bölüm bunları tek tek anlatıyor:

1. **Veritabanı ve güvenlik sözleşmesi** — 31 tablo, 75 RLS politikası ve diğer her parçanın çağırdığı RPC'ler.
2. **Makale tarayıcısı (crawler)** — sistemin ön kapısı: arama → filtre → indirme.
3. **Üç aşamalı yapay zekâ kademesi** — Gemma → Gemini Flash-Lite → Gemini Flash, üç modeli tek bir ortak sözleşmeyle çalıştırır.
4. **Deterministik normalleştirici ve güvene göre yönlendirme** — model çıktısını veritabanıyla karşılaştırılabilir veriye çevirir ve "insan mı, otomatik mi" kararını verir.
5. **Geri besleme ile öğrenme döngüsü** — insan onayları sonraki taramayı yeniden puanlar.
6. **Günlük operasyon otomasyonu** — beş dakikalık bir GitHub Actions cron'unda bir denetleyici (controller) artı beş paralel işçi.
7. **Referans verisi, optimizasyon, testler ve dokümantasyon** — bunu bir demo değil, gerçek bir sistem yapan destek katmanı.

## 4. Yaptığım her şey, tek tek

Her parça için: **neden gerekli · nasıl yaptım · işin zor kısmı · teknolojiler · dosyalar ve satır sayıları.**

---

### 4.1 Veritabanı ve güvenlik sözleşmesi — *tüm projenin omurgası*

**Neden gerekli.** OpenNutri'nin diğer her parçası burada buluşuyor. Bu tablolar, RPC'ler ve politikalar olmadan frontend bir etiket gönderemez, tarayıcı bir makale kaydedemez, model işçileri bir görev alamaz, pano da doğru veriyi gösteremez. Bu tek dosya, Python hattı ile React uygulaması arasındaki **sözleşme.**

**Nasıl yaptım.** `migration.sql`, **31 tablo, 26 fonksiyon/RPC, 75 RLS politikası, 69 indeks, 2 tetikleyici ve 22 `SECURITY DEFINER` fonksiyonu** tanımlayan **5.396 satırlık** bir dosya. Tamamı **tek, idempotent bir migrasyon** olarak yazıldı; yani canlı veritabanına istediğiniz kadar tekrar uygulayabilirsiniz: sütunlar `IF NOT EXISTS` ile ekleniyor, `CHECK` kısıtları önce `information_schema`'yı sorgulayan `DO $$ … $$` blokları içinde silinip yeniden kuruluyor (böylece tekrar çalıştırma hata vermiyor) ve yanlış tipte kalmış eski bir sütun yerinde tespit edilip dönüştürülüyor. Şema beş katmandan oluşuyor:

- **Referans katmanı** — `entities` (kanonik gıdalar), `entity_aliases`, `master_nutrients`, `sources` ve `claims` (miktar, birim, baz, güven ve kaynak bilgisiyle birlikte normalize edilmiş `gıda × besin × kaynak` kaydı). Herkes okuyabilir; yalnızca servis rolü (service role) yazabilir.
- **Keşif katmanı** — `papers` (merkezdeki tablo; hem `doi` hem de DOI'si olmayan ya da farklı sağlayıcılardan gelen kopyaları ayıklamak için `canonical_key`, ayrıca yönlendirme özeti sütunları) ve idempotent keşif defteri `paper_search_hits` (`hit_key` değeri doğrudan SQL içinde hesaplanan bir md5; kopya satırlar bir `ROW_NUMBER()` penceresiyle silindikten sonra `UNIQUE` indeks ekleniyor). Geri besleme döngüsü için her sorgunun huni sayaçlarını tutan ayrı `paper_search_batches` tabloları da burada.
- **Etiketleme katmanı** — `annotations` (`UNIQUE(paper_id, user_id)`), `food_items`, `annotation_nutrient_values`. Özel/kanonik ayrımı (`is_custom_*` artı boş bırakılabilen yabancı anahtar), bir etiketleyicinin referans veritabanında henüz olmayan bir şeyi, olanların eşlemesini kaybetmeden kaydedebilmesini sağlıyor.
- **İş akışı motoru** — iki kez baştan yazıldı ve şema bunu **kanıtlıyor**: eski slot modeli, Huan'ın eski çakışma modeli (`paper_conflict_candidates` görünümü dâhil) ve şu anki **genel kuyruk + onay** modeli: değiştirilemeyen `paper_label_submissions`, `paper_label_approvals` (yapısal bir `correction_diff_json` ile) ve nihai `paper_review_outcomes`. Bir `BEFORE INSERT/UPDATE` tetikleyicisi, `human_review_ready` durumunda olmayan bir makaleye iş atanmasını reddediyor — yönlendirme hatalarına karşı şema düzeyinde bir koruma.
- **Yapay zekâ yönlendirme katmanı** — `ai_extractions` (tüm denetim kaydı), `routing_stage_configs` (**veriye dayalı aşama tablosu** — eşikler, yedek modeller, giriş modu; yani hattın biçimi kodda değil, veride) ve `paper_stage_tasks` (iş kuyruğu).

**Güvenlik modeli**, 31 tablonun hepsinde en az yetki ilkesine dayanıyor: altı `SECURITY DEFINER` yüklem fonksiyonu üzerine kurulu **75 RLS politikası.** En zarif kısmı şu: **`current_user_can_write() = NOT current_user_is_tester()`** — salt okunur eğitim erişimi, her tabloda ayrı ayrı yazılmak yerine *tek bir olumsuzlamadan* geliyor. Yüklemler `SECURITY DEFINER` olduğu için, RPC'ler kuyruk dilimlerini ve özet verileri sunarken kullanıcıya `paper_stage_tasks`, `ai_extractions` ya da başkalarının etiketleri üzerinde doğrudan okuma izni vermek zorunda kalmıyor. **Kayıt izin listesi (allowlist)** yalnızca `supabase_auth_admin`'e verilmiş bir auth hook'uyla uygulanıyor; izin listesi tablosundaki tüm istemci yetkileri kaldırıldığı için tarayıcıdan ne okunabiliyor ne de aşılabiliyor. Üstelik `upsert_reviewer_admin_config`, geriye **hiç** etkin yazma yetkili kokpit inceleyicisi kalmayacaksa işlemi reddediyor: yani tüm ekibi yanlışlıkla kilitleyip dışarıda bırakamazsınız.

Sözleşmenin iki parçasını ayrıca anmak gerek:
- **`claim_paper_stage_tasks`** — eşzamanlılığın temel taşı. Kuyruktaki görevleri `ORDER BY attempt_count ASC, priority DESC … FOR UPDATE SKIP LOCKED` ile alıyor. İşte o tek ifade, `FOR UPDATE SKIP LOCKED`, beş paralel GitHub Actions işçisinin hiçbir koordinasyona gerek kalmadan ve aynı görevi iki kez işlemeden birbirinden bağımsız görev kümeleri almasını sağlıyor — tüm paralel tasarım buna dayanıyor.
- **Deterministik payload üreticileri** — `build_annotation_submission_payload`, bir insan gönderisinin kanonik JSON'unu SQL içinde, Python normalleştiricisiyle *birebir aynı* kurallarla (boşlukları sadeleştirme, `round(value,6)`, deterministik sıralama) oluşturuyor. Böylece aynı veriye ait bir insan gönderisi ile bir yapay zekâ çıkarımı **aynı hash değerini üretiyor.** `build_label_payload_diff` ise SQL içinde tam bir yapısal fark çıkarıyor (eklenen/eksik gıda ve besin satırları için anti-join'ler); çıktısı, etiketleyici performans metriklerinin ham malzemesi.

**İşin zor kısmı.** Tek bir dosyayı her seferinde güvenle yeniden uygulanabilir kılmak *ve* etiketleyicilere, testçilere, kokpit kullanıcılarına, onaylayıcılara ve servis rolü otomasyonuna 31 tablo boyunca tek bir özel satır bile sızdırmadan tam doğru yetkiyi vermek — aynı zamanda yapay zekâ ve insan payload'larını hash ile karşılaştırılabilecek kadar deterministik tutarak.

**Teknolojiler.** PostgreSQL / Supabase, PL/pgSQL, Row-Level Security, `SECURITY DEFINER` fonksiyonları, `FOR UPDATE SKIP LOCKED`, JSONB, SHA-256 ile karşılaştırılabilir kanonik payload'lar.

**Dosyalar ve satırlar.** `apps/expert-annotator/migration.sql` (**5.396**). **43 commit.**

---

### 4.2 Makale tarayıcısı (crawler) — *sistemin ön kapısı*

**Neden gerekli.** Tarayıcı yanlış makaleleri alırsa kıt model kotası ve etiketleyici zamanı boşa gider; fazla katı olursa gerçek bileşim tablolarını hiç bulamaz. Tarayıcı, **ürünün alan tanımını** puanlamaya, doğrulamaya ve kopya ayıklamaya gömülü olarak taşıyor. Geniş beslenme sorgularının döndürdüğü makalelerin çoğu doğrudan bir gıda bileşim tablosu *değil* — müdahale çalışmaları, yem denemeleri, derlemeler. Bu yüzden tarayıcı, pahalı bir işlem yapmadan önce adayları daraltmak zorunda, ama **tek bir alakasız kelime yüzünden** gerçek bir makaleyi elemeden.

**Nasıl yaptım.** `FoodCompositionCrawlerV2`, **Arama → Filtre → İndirme** akışını yürüten, ~2.200 satırlık (~70 metotlu) bir orkestratör; pahalı adım hep en sona bırakılıyor:

1. **Arama** — Europe PMC / OpenAlex / Semantic Scholar'dan (Türkçe için DergiPark) yalnızca üst veri (metadata) çekilir; her kaynak için sorgu ayrı biçimlendirilir.
2. **Filtre** — başlık ve özet üzerinde, **henüz PDF indirilmeden** yapılan, tamamen **eklemeli** bir alaka kararı. Kural (AGENTS'ta zorunlu kılınmış) şu: *kesin bir olumsuz veto yok* — olumsuz bir ifade puanı düşürür, ama asla doğrudan elemez. Yani "klinik çalışma" gibi tek bir kelime, içinde bir bileşim tablosu da olan bir makaleyi öldüremez. Ucuz arama kapısı; bileşim ifadelerini, gıda/besin terimlerini, `mg/100g` türü bir birim regex'ini ve gıda+besin eşleşmelerini yumuşak cezalara karşı puanlar. Daha zengin üst veri kapısı buna üç **öğrenilmiş** sinyal ekler: kaynağa göre bir ön puan, dile göre seçilmiş çapa ifadelerine **cümle gömme (embedding) benzerliği** ve **öğrenilmiş geri besleme n-gram puanı** (bkz. §4.5). Her katkı bir `{kod, metin}` gerekçesiyle kaydedilir; böylece her karar, çalışma raporunda baştan sona açıklanabilir.
3. **İndirme** — yalnızca üst veri filtresini geçenlerin PDF'i indirilir, ardından **çok daha katı bir tam metin kapısı** (`validate_pdf_text`) uygulanır: kaynakça bölümleri çıkarılır (kaynakça puanı şişirmesin diye), AOAC/HPLC/GC/ICP yöntem kanıtı ve `mg/100g` birimleri sayılır; geçmek için güçlü bir puan **ve** bir tablo sinyali **ve** bir gıda sinyali **ve** temel besin paneliyle (nem/protein/yağ/kül/lif/karbonhidrat/enerji/mineraller) en az 4 örtüşme gerekir. İndirmeye girişte gevşek (recall için), çıkışta katı (kesinlik için). Kelime eşleştirmesi Unicode kelime sınırlarına duyarlı; böylece Türkçedeki "et" sözcüğü "diet" içinde değil, gerçek bir kelime olarak eşleşir.

**Asıl zor kısım — PDF indirme.** Yayıncı PDF'leri kolay vermiyor. `_download_candidate`, katmanlı bir yedek zinciri: PMC Açık Erişim paketi (OA API'sinin XML'ini ayrıştır, PDF bağlantılarını dene, olmazsa **`.tar.gz`'yi indirip içindeki en büyük `.pdf`'i çıkar**); doğrudan `urllib` ile indirme (gövdenin `%PDF` ile başladığını doğrula); başarısız olursa **tarayıcı User-Agent'ıyla `curl`** (birçok yayıncı tarayıcı dışı istemcileri engelliyor); ve gelen yanıt bir HTML bot duvarıysa, **bir PMC proof-of-work çöz** — `_solve_pmc_pow`, meydan okumayı sayfadan ayrıştırıp bir **hashcash nonce'unu kaba kuvvetle çözer** (`md5(meydan+nonce)` belirli sayıda sıfırla başlayana kadar artırır), sonra çözüm çerezi ile yeniden dener. Yani gerçek bir madencilik döngüsüyle aşılan bir bot duvarı.

Tarayıcı **aynı makaleyi asla iki kez taramaz**: aramadan önce, canlıdaki tüm `papers.canonical_key` değerleri (Supabase REST API'sinden sayfalanarak) ve yerel kalıcı makale durumları (üst veri aşamasında elenenler dâhil, böylece elenmiş bir makale tekrar indirilmez) birleştirilerek bir atlama listesi oluşturur. Kabul edilen PDF'ler **kimliğe göre** adlandırılır (`pmcid_*` / `doi_*` / hash'lenmiş `canonical_key`) ve her çalışma **süre sınırlıdır** — 2.400 saniyelik süre dolduğunda temiz biçimde durur, ama kabul edilen her kısmi sonucu ve kendini açıklayan bir huni raporunu yine de yazar; böylece bir GitHub zaman aşımı asla iş kaybettirmez.

Küçük ama kritik bir modül olan `models.py`, tarayıcının, her kaynak adaptörünün, yükleyicinin ve geri besleme dışa aktarıcısının ortak kullandığı **üç deterministik kimlik anahtarını** (`build_canonical_key`, `build_search_hit_key`, `build_search_batch_key`) tanımlar. Böylece bir makale her yerde *aynı* kimliği üretir; SQL'deki `UNIQUE` indekslerin, atlama listesinin ve toplu (batch) geri beslemenin merkezî bir koordinatöre gerek kalmadan örtüşmesini sağlayan da budur.

**Teknolojiler.** Python, Europe PMC / OpenAlex / Semantic Scholar / DergiPark, `urllib` + `curl`, `tarfile`, `pdftotext`, sentence-transformers gömmeleri, MD5 hashcash proof-of-work, Supabase REST.

**Dosyalar ve satırlar.** `food_paper_crawler/crawler_v2.py` (**2.215**), `ranking.py` (485), `models.py` (374), `embeddings.py` (138), `dergipark_source.py` (687) ve diğer kaynak adaptörleri. **30 commit.**

---

### 4.3 Üç aşamalı yapay zekâ kademesi — *Gemma → Gemini Flash-Lite → Gemini Flash*

**Neden gerekli.** Son aşamadaki güçlü Gemini çıkarımı, kıt ve pahalı bir kaynak — ücretsiz kotada günde yaklaşık **20 çağrı.** Her adayı en güçlü modelle elemek, bu bütçeyi çoğu işe yaramayacak makaleye harcamak demek olurdu. Bu yüzden kabul edilen her makale, önce birçok adayı ucuza işleyen, sonra pahalı çağrıları yalnızca **en yüksek puanlı** alt kümeye harcayan **üç aşamalı bir huniden** geçiyor:

```
Küçük  — gemma_proof_extraction_v1   (gemma-4-31b-it, 26B yedek)  metin modu  ~1.500/gün
Orta   — gemini_flash_lite_triage_v1 (gemini-3.1-flash-lite)                  ~500/gün
Güçlü  — gemini_flash_db_payload_v2  (gemini-3.5-flash)           PDF modu    ~20/gün
                                                                                │
                                                                  human_review_ready
```

**Nasıl yaptım.** Üç aşama da *aynı* ortak çıkarım sözleşmesini, tek bir prompt (`opennutri_evidence_payload_v2`) üzerinden çalıştırıyor. Bu prompt aslında ürünün alan tanımının kod hâli: yaklaşık 25 satır boyunca "yararlı OpenNutri verisi" nedir (doğrudan gıda/ürün bileşimi) ile neyin **boş** sayıldığını (müdahale/etki çalışmaları, tek seferlik deneysel formülasyonlar, sindirilebilirlik, duyusal testler, biyobelirteçler, derleme verileri) tek tek sayıyor — gerçek gıdalardan oluşan bir veritabanı ile alakasız bir ziraat makaleleri yığını arasındaki farkı belirleyen şey bu. Çıkarılan her satır, Ayşegül'ün frontend'inin sonradan vurgulayabilmesi için **kanıtın konumunu belirten meta veriler** taşımak zorunda: `table_label`, `page_hint`, kısa ve birebir bir `source_quote` (en fazla 20 kelime), `source_location_type`, `section_heading`, `paragraph_hint`. Tüm promptun en önemli talimatı şu: `page_hint`, **`===== PDF PAGE N =====` işaretlerinden alınan, 1'den başlayan PDF sayfa numarasıdır; asla basılı dergi sayfası değildir** — çünkü vurgulamayı bozan şey tam olarak basılı sayfa ile PDF sayfasının karışmasıydı.

Bunu üretimde ayakta tutan iki dayanıklılık mekanizması var:
- **Modelin bozuk JSON'undan sağ çıkmak.** LLM'ler sürekli bozuk ya da farklı biçimli JSON döndürür; bunu el yordamıyla ele alırsanız sonsuz bir yeniden deneme döngüsüne girersiniz. Değerlendirici markdown çitlerini temizler, metnin içine gömülü olsa bile ilk *dengeli* JSON'u çıkarmak için string/kaçış/derinlik durumunu izleyen, **elle yazılmış bir dengeli parantez tarayıcısı** çalıştırır ve **dört farklı biçimi** (istenen nesne, düz bir satır dizisi, tek elemanlı diziye sarılmış bir nesne ve iç içe `food → nutrients[]`) kabul edip hepsini tek bir kanonik köke indirir. Zorunlu alanı eksik olan satır atılır, hata sayılmaz. Yani geçerli ama farklı biçimli çıktı, yeniden deneme tetiklemek yerine kurtarılır.
- **Doğrudan PDF girişi + gerçek sayfa numaraları.** Güçlü aşamada PDF, modele doğrudan bir belge parçası olarak verilir (15 MB altında satır içi, üstündeyse Files API üzerinden; geçici dosyayı da uzaktaki yüklemeyi de silen bir `finally` temizliğiyle). Böylece model sayfaları, tabloları görür ve gerçek sayfa numarasını bildirebilir. Metin modundaki aşamalarda ise `pdftotext` çıktısı form-feed'lerden bölünür ve herhangi bir kısaltmadan **önce** `===== PDF PAGE N =====` işaretleriyle etiketlenir; böylece geri kalan sayfalar doğru numarayı korur. **Gemma neden metin modunda kalıyor:** yapılan ölçümde Gemma PDF parçalarını *kabul ediyor* ama **5 sayfalık bir PDF'te 600 saniyeyi aşıp zaman aşımına uğruyordu** — günde ~1.500'lük bir aşama için bu ölümcül. Bu yüzden ona, görüntü işlemeye gerek kalmadan zaten doğru sayfa numaralarını veren, sayfa işaretli metin veriliyor. Bu karar, sonradan farkında olmadan geri alınmasın diye hem kodda hem dokümantasyonda sabitlendi.

**Yürütme motoru** (`process_stage_queue.py`, 1.560 satır), **tek bir kötü makale ya da geçici kota sorunu otomasyonu durduramayacak** biçimde kuruldu: görevler atomik biçimde alınır (`claim_paper_stage_tasks`); **en az denenmiş olan önce** gelecek şekilde sıralanır (böylece sürekli başarısız olan bir makale kuyruğu tek başına meşgul edemez); 120 dakikadan eski `processing` satırları kuyruğa geri alınır; model, herhangi bir görev alınmadan *önce* oluşturulur (eksik bir anahtar varsa hemen hata verir); sert bir `SIGALRM` zaman aşımı (300 sn) tek bir yavaş makaleyi sınırlar; ve bir **hata sınıflandırması** her arızayı doğru yere yönlendirir — geri döndürülemez model yapılandırma hataları görevi başarısız sayıp otomasyonu durdurur, geri döndürülebilir hatalar yedek modeli (Gemma 31B → 26B) **aynı denemede** dener, kota hataları görevi kuyruğa geri alır ama **deneme sayısını azaltır** (bir kota beklemesi asla makale hatası gibi görünmez) ve kota dışı iki denemeyi aşan her şey, sonsuza dek dönmek yerine başarısız sayılır.

**İşin zor kısmı.** Tek bir sözleşmeyi, giriş modları ve hata davranışları farklı üç modelde birden çalıştırmak; çıktıyı sadece makul bir özet değil, *veritabanına eklenebilecek* kadar kullanışlı tutmak; ve kotayı geri döndürülebilir bir çalışma hatasından, onu da geri döndürülemez bir yapılandırma hatasından doğru biçimde ayıran bir hata yönetimi kurmak — çünkü her biri farklı ele alınmazsa gözetimsiz kuyruk bozulur.

**Teknolojiler.** Python, Gemma + Gemini (Google GenAI SDK), doğrudan PDF + metin giriş modları, `pdftotext`, `SIGALRM` zaman aşımları, elle yazılmış bir JSON kurtarma ayrıştırıcısı, Supabase RPC'leri.

**Dosyalar ve satırlar.** `evaluator/unified_evaluator.py` (687), `ai_routing.py` (842), `scripts/process_stage_queue.py` (1.560), ayrıca `recover_gemini_candidates.py` (446) ve `flash_lite_triage_experiment.py` (245). **34 commit.**

---

### 4.4 Deterministik normalleştirici ve güvene göre yönlendirme — *bir tahminin güvenilir veriye ya da bir insanın işine dönüştüğü yer*

**Neden gerekli.** Bir modelin ham çıktısı, güvenilir veritabanı verisi değildir. Tutulabilmesi için iki şey olmalı: çıktı, bir insan inceleyicinin göndereceği **yapıyla birebir aynı** hâle getirilmeli (böylece yapay zekâ ve insan çıktısı birbirinin yerine geçebilir ve karşılaştırılabilir olur) ve sistem, güvene bakarak **otomatik tutmak mı yoksa bir insana göndermek mi gerektiğine** karar vermeli — çünkü ölçeklenmeyen şey her makaleyi elle kontrol etmek, hatalı sayı üreten şey ise her şeyi otomatik kabul etmek. Bu, "yapay zekâ önerir, insan yalnızca emin olunmayanları doğrular" fikrinin tam kalbi.

**Nasıl yaptım — normalleştirici (`normalize_ai_payload_with_summary`).** Her model satırı, katı bir elemeden geçiyor:
1. **Zorunlu alan kapısı** — gıda/besin/miktar eksik olan satır atılır (`missing_required_field` olarak sayılır).
2. **Birim standardizasyonu (`_standardize_unit`)** — en katı bekçi. Yalnızca yedi standart birim geçer: `g/100g`, `mg/100g`, `μg/100g`, `kcal/100g`, `kJ/100g`, `IU/100g`, `%`. `µ`-`μ` farkını, büyük-küçük harfi, gram/miligram/mikrogram/mcg/kcal/kJ/IU yazımlarının hepsini ve bir **baz politikasını** ele alır: 100 g üzerinden olması zorunlu, **kuru madde reddedilir**, ama taze/yaş/olduğu gibi/yenilebilir kısım kabul edilir. Reddedilenler `unsupported_unit_or_basis` olarak sayılır.
3. **Referans çözümleme (`_resolve_reference_row`)** — **önce ID** (modelin verdiği `food_fdc_id`/`nutrient_id`'yi canlı bir satıra karşı doğrula, *üstelik* o satırın adının da eşleştiğini kontrol et), sonra tam ad, sonra takma ad. Ad çözümleyici, **belirsiz adları hiçbir şeye eşler** — iki veritabanı satırı aynı adı paylaşıyorsa ikisi de eşleşmez — böylece asla yanlış bir bağ kurmaz. Çözülemeyen gıda/besinler atılmaz; açıkça `is_custom_food`/`is_custom_nutrient` satırı olarak *tutulur*.
4. **Deterministik gruplama ve sıralama** — satırlar çözülmüş gıdaya göre gruplanır, uzun ve sabit bir anahtara göre sıralanır, değerler `round(…, 6)` ile yuvarlanır. Bu determinizm işin tam özü: payload kanonik biçimde serileştirilip **SHA-256 ile hash'leniyor**, dolayısıyla aynı iki çıkarım aynı hash'i üretir ve bir yapay zekâ çıkarımı, bir insan gönderisiyle bayt bayt karşılaştırılabilir.
5. **Özet muhasebesi** — kabul/ret/eşlenemeyen sayıları ve bir `rejection_reasons` histogramı her çıkarımda saklanır; böylece kokpit, satırların *neden* atıldığını gösterebilir.

**Nasıl yaptım — güven kapısı (`ai_routing.py`).** Normalleştirmenin ardından makale gruplanıp yönlendirilir:
- **`classify_routing_bucket`**, her makaleyi `overall_confidence` değerini aşamanın kendi `positive_threshold` / `negative_threshold` eşikleriyle (yani "veri var" ve "veri yok" için ayrı eşiklerle, veriye dayalı aşama yapılandırmasından okunarak) karşılaştırarak **yüksek/düşük × olumlu/olumsuz** gruplarına ayırır.
- **`route_bucket`** asıl kapıdır: **düşük güven → `human_review_ready`** (Ayşegül'ün etiketleme kuyruğuna gider); **yüksek güven + olumlu → `ai_finalized_has_data`** (otomatik tutulur); yüksek güven + olumsuz → "veri yok" olarak kesinleştirilir. Zaten insan doğrusu olan bir makalenin üzerine asla yazılmaz.
- **`stable_audit_sample`**, otomatik kabul edilenler üzerindeki kalite kontrolüdür: `SHA256(paper|stage|model)`, `audit_rate × 2^64` ile karşılaştırılır. **Deterministiktir** — aynı makale her zaman aynı denetim kararını alır — ve yüksek güvenli otomatik kesinleştirmelerin bile ayarlanabilir bir kısmını insan incelemesine geri zorlar; böylece otomatik kabul yolu körü körüne güvenilmek yerine sürekli olarak doğruluk açısından örneklenir.
- **Ham pozitif kurtarma** — olumlu görünen ama normalleştirmede *boşa* düşen bir Gemma çıktısı, tam ham satırlara sahipse ya da güveni ≥ 0,75 ise ya da bileşim diliyle ≥ 0,6 ise yine de sonraki aşamaya geçer; böylece ayrıştırıcı/normalleştirici kaymaları muhtemelen gerçek bir makaleyi asla sessizce atmaz, ama katı normalleştirme yine de nihai girişi denetler.

Ve huninin asıl motoru, **`score_followup_priority`**: her yararlı çıktı; güvenden, kabul edilen/kanıtlı/100 g üzerinden/tablo satır sayılarından, bileşim dili için bir uyum bonusundan ve promptun "boş" tanımını yansıtan **yumuşak cezalardan** (derleme/meta-analiz, yem/sindirilebilirlik, duyusal/biyobelirteç, tek seferlik formülasyon, müdahale/ekstrakt) bir tam sayı puan alır (−1000…1000 ile sınırlanmış). Sonraki aşama görevleri *bu puana göre sıralı* alır; böylece Flash-Lite, Gemma çıktısının en iyi 500'ünü, son Gemini ise onun en iyi 20'sini işler. "Neyin yararlı olduğu" yargısı bilinçli olarak iki kez kodlanmış — bir kez model için promptta, bir kez de sıralayıcı için öncelik puanında — ki eleyicinin sıralaması ile çıkarıcının kararı birbiriyle uyumlu kalsın.

**İşin zor kısmı.** İnsan/yapay zekâ sınırında determinizm: bir Python normalleştiricisi ile bir SQL üreticisini **bayt bayt aynı** yapıyı üretecek hâle getirmek (ki iki doğru üreticisi hash ile karşılaştırılabilsin) — ve "model emin görünüyordu" diyen bir kara kutu yerine; *tekrarlanabilir* (aynı makale, her zaman aynı karar), *denetlenebilir* (nedenini her zaman görebilirsiniz) ve *kendini kontrol eden* (otomatik kabullerin örneklenmiş bir kısmı insana geri gönderilir) bir güven kapısı tasarlamak.

**Teknolojiler.** Python, SHA-256 ile kanonik hash'leme, deterministik JSON serileştirme, eşik tabanlı gruplama, hash tabanlı tekrarlanabilir denetim örneklemesi, PL/pgSQL ile aynısını üreten yapılar.

**Dosyalar ve satırlar.** `ai_routing.py` (842) ve `test_ai_routing.py` (**2.469 satır, 60 test** — projedeki en yoğun test edilen dosya, çünkü bir hatanın veritabanını sessizce bozabileceği yer tam burası). **Kademe genelinde 34 commit.**

---

### 4.5 Geri besleme ile öğrenme döngüsü — *insan onayları sonraki taramayı eğitir*

**Neden gerekli.** OpenNutri'yi sabit bir anahtar kelime tarayıcısı değil, *gelişen* bir hat yapan şey bu. Bir insanın onayladığı ya da reddettiği her makale, hangi kelime ve ifadelerin gerçekten yararlı bir makaleyi işaret ettiğine dair bir kanıt — ve bu kanıt, tarayıcının bir sonraki taramada adayları nasıl puanladığını değiştirmeli.

**Nasıl yaptım.** `update_terms.py` (1.219 satır) döngüyü kapatıyor:
```
insan onayları (paper_review_outcomes) ─▶ log-odds n-gram puanlaması ─▶ latest.json ─▶ sonraki tarama daha iyi sıralar
```
- **Doğru seçimi bilinçli olarak temkinli.** Olumlu/olumsuz örnekler `paper_review_outcomes`'tan **yalnızca `truth_source_kind = 'human_review'` olduğunda** alınır — yapay zekânın kesinleştirdiği sonuçlar kayıt için saklanır ama **dışlanır**, böylece *model asla kendi üzerinde eğitilmez.* Açık çakışmalar çıkarılır (belirsiz doğru hiçbir şey öğretmez); bekleyen/geçersiz kılınmış gönderiler asla sayılmaz; eski etiketler yalnızca çözülmüş bir sonucu olmayan eski makaleler için yedek olarak kullanılır.
- **Puanlayıcı, üç grup üzerinde yumuşatılmış log-odds.** Gruplar: iyi, kötü ve **arka plan** (geri kalan her şey). Her n-gram için belge frekansları her grupta, **başlık-yalnız ve başlık+özet için ayrı ayrı** sayılır; sonra add-α yumuşatmasıyla bilgilendirici Dirichlet log-odds'u (Monroe ve ark. yöntemi) hesaplanır. `title_net = title_good − title_bad` ve `ta_net` net sinyalleri, tarayıcının çarpan olarak kullandığı tam değerlerdir. **Arka plan grubu, ayırt ediciliğin anahtarı**: yalnızca iyi-kötü karşılaştırması sıradan kelimeleri ödüllendirir; her birini geniş arka plan külliyatına karşı puanlamak ise gerçekten yararlı makalelere *özgü* terimleri öne çıkarır. Başlık ile başlık+özet ayrı tutulur, çünkü bir *başlıktaki* güçlü bir ifade, aynı ifadenin özetin içine gömülü hâlinden daha güçlü bir kanıttır. Tohum bileşim ifadeleri *yumuşak* bir ön puan alır; öğrenilmiş kanıt zamanla bunu geçersiz kılabilir.
- **Her dil için yedi havuz üretir** ve `latest.json`'a yazar: `weighted_terms` (yumuşak filtre puanı), `query_phrases` (yeni aramalar kurmak için), `anchor_phrases` (gömme çapaları), `pair_scores`, `batch_scores`, `source_priors` ve `concept_scores`. Böylece tek bir etiketli külliyattan tarayıcıya üç ayrı öğrenilmiş sinyal ulaşır: n-gram filtre puanları, gömme çapaları ve sorgu üretimi/sıralaması için puanlar.

**İşin zor kısmı.** Sistemin **kendi üzerinde eğitilmediğinden** ve **belirsiz doğrudan öğrenmediğinden** emin olmak — ve geri beslemeyi, bir makalenin sırasını düşürebilen ama bir insanın hâlâ isteyebileceği bir makaleyi asla doğrudan eleyemeyen *yumuşak* bir puan olarak tutmak (tarayıcının "veto yok" kuralına uygun şekilde). Bir de istatistik: arka plan külliyatına dayalı log-odds ve add-α yumuşatması, az sayıda ve gürültülü ilk etiketlerin saçma ağırlıklar üretmesini engelleyen şey.

**Teknolojiler.** Python, yumuşatılmış/bilgilendirici Dirichlet log-odds (Monroe ve ark.), n-gram belge frekansı sayımı, her dil için ağırlık havuzları, Supabase'den doğru verisi dışa aktarımı.

**Dosyalar ve satırlar.** `food_paper_crawler/feedback/update_terms.py` (**1.219**), ayrıca `feedback_config.py`, `supabase_terms.py` (481), `feedback_terms.py`.

---

### 4.6 Günlük operasyon otomasyonu — *kendi kendine çalışan gerçek bir hat, üstelik ücretsiz*

**Neden gerekli.** Yukarıdaki her şeyin gerçekten *çalışması* gerekiyor — tara, yükle, günde ~1.500 makaleyi ele, triyaj yap, çıkar — hem de sürekli, özel bir sunucu ve bütçe olmadan. Buradaki her mimari seçim tek bir kısıtın sonucu: bunu, her işe süre sınırı koyan GitHub runner'larında ve Gemini'nin ücretsiz günlük kotasında yap.

**Nasıl yaptım.** `.github/workflows/daily-ops.yml`, **beş dakikalık bir cron**'la çalışıyor ve iki tür iş başlatıyor:
- **Tek bir `refill-controller`** — tarama/yükleme/yeniden doldurma yapmaya izinli *tek* iş. `cancel-in-progress: false` olan bir `concurrency` grubu altında çalışıyor; böylece aynı anda en fazla bir tane çalışır ve yeni bir tetikleme, sürmekte olan bir taramayı asla yarıda kesmez.
- **Beş paralel `drain-workers`** (`matrix: worker:[1..5]`) — yalnızca kuyruktaki model görevlerini işler, **controller'a bağlı değildir** ("controller başarısız olsa bile işleme devam etmeli") ve hafif bir bağımlılık setiyle kurulur. Beşinin paralel çalışırken güvenli olmasının **tek nedeni** `FOR UPDATE SKIP LOCKED` — her biri, hiç koordinasyona gerek kalmadan birbirinden bağımsız bir görev kümesi alır.

**Controller** sürekli dönen bir döngü değil, tek bir tik: eski görevleri kuyruğa geri al → her aşama için bugün tamamlananları say → *etkin* eleme işini say → 150'lik bir etkin hedefe göre açık (deficit) hesapla (her tarama daha yeni geri beslemeden yararlansın diye stok bilinçli olarak düşük tutuluyor) → ardından açık bir "dur/devam et" karar ağacı (günlük hedefe ulaşıldıysa, ya da yeterince etkin iş varsa, ya da 75 dakikalık süre dolduysa, ya da bir depolama sınırı aşıldıysa → dur; yoksa açığı 30'arlı parçalar hâlinde tara ve kaynak tükendi mi diye kontrol et). **İşleme (drain)** tiki ise; eleme günde 1.500 hedefinin altındaysa bir Gemma dilimini işler, aynı tik içinde alt aşama triyaj + son Gemini dilimlerini de **araya sokar** (böylece elenecek bir şey kalmasa bile Gemini akmaya devam eder), eleme hedefine ulaştığındaysa son Gemini'yi 20/gün'e kadar işler ve yeni "human_review_ready" olan makaleleri hemen etiketleme kuyruğuna atar.

Onu ücretsiz katmanın sınırları içinde tutan şeyler: **iki ayrı saat dilimine göre kota günü muhasebesi** (Gemma bir UTC gününü, iki Gemini aşaması ise Google'ın sıfırlamasına uyması için bir `America/Los_Angeles` gününü sayar), **tembel modül yükleme** (işleme yapan işçiler tarayıcının import maliyetini hiç ödemez) ve **iç içe üç süre sınırı** (controller 75 dk, tarayıcı kısmi sonuçları yazarak 2.400 sn, her model çağrısı 300 sn); böylece tek bir yavaş makale ya da uzun bir tarama, GitHub'ın iş süresini asla aşamaz. Makale PDF'leri **kaynak URL'sinden, talep üzerine** sunulur (`OPENNUTRI_STORE_PDFS_IN_SUPABASE=0`), çünkü onları saklamak Supabase'in ücretsiz depolama/çıkış sınırlarını aşardı. CORS açısından sorunlu yayıncı PDF'lerini ise bir **aynı kaynaklı (same-origin) PDF proxy'si** (`api/pdf.js`, bir Vercel serverless fonksiyonu) sunucu tarafında, ciddi bir güvenlikle çeker: yalnızca https, **SSRF koruması** (localhost/iç ağ adreslerini ve IP literallerini reddeder), 25 MB sınırı, **`%PDF-` sihirli bayt kontrolü** (genel bir açık proxy olarak kötüye kullanılamasın diye), 25 saniyelik zaman aşımı ve **1 yıllık değiştirilemez (immutable) önbellek** (her makale kaynaktan en fazla bir kez çekilir).

**İşin zor kısmı.** **Beş dakikalık bir pencere içinde sürdürülebilir ve idempotent** olan bir tik durum makinesi kurmak — öldürülen runner'lara, çakışan tetiklemelere, iki kota saat dilimine ve controller/drain ayrımına rağmen — sürekli çalışan, ama karşılayamayacağım bir sunucuda barındırılması gereken kolaycı bir daemon yerine. GitHub işleri öldürülür ve çakışır; veritabanından görev alma atomik olmalı; tek bir başarısız makale bir işçiyi tek başına meşgul etmemeli; ve controller çökse bile işleme devam etmeli.

**Teknolojiler.** GitHub Actions (cron, matrix, concurrency grupları), `FOR UPDATE SKIP LOCKED`'lı Supabase RPC'leri, Vercel serverless, `SIGALRM`/süre sınırları, kota günü muhasebesi, Python orkestrasyonu.

**Dosyalar ve satırlar.** `scripts/daily_ops_orchestrator.py` (**2.358**), `.github/workflows/daily-ops.yml` (148), `scripts/ensure_paper_stock.py` (573), `scripts/upload_to_supabase.py` (774), `apps/expert-annotator/api/pdf.js` (102). **Yalnızca orkestratörde 27 commit.**

---

### 4.7 Referans verisi, PDF/çıkış optimizasyonu, testler ve dokümantasyon — *bunu demo değil, sistem yapan katman*

**Neden gerekli.** Yapay zekâ normalleştiricisinin ve otomatik tamamlamanın, bilinen gıda ve besinler için **sabit ID'lere** ihtiyacı var; yoksa her makale denetimsiz metinler üretir. Tehlikeli mantığın testlere ihtiyacı var; çünkü buradaki bir hata sessizce bir veritabanını bozar ya da kotayı yakar. Altı aylık bir projenin de dokümantasyona ihtiyacı var; yoksa belgelenmemiş kararlar yanlışlıkla geri alınır.

**Nasıl yaptım.**
- **Referans verisi ETL'i** — iki idempotent yükleyici (`etl_usda_to_opennutri.py`, `etl_sr_legacy_to_opennutri.py`), USDA FoodData Central CSV'lerini Supabase REST API'si üzerinden kanonik `entities` / `entity_aliases` / `master_nutrients` / `sources` / `claims` katmanına aktarır. **Hazırlık durumunu (raw/cooked/dried…) gıdanın açıklama metninden çıkarırlar**, bir çakışma sütununa göre **upsert** yaparlar (yani tekrar çalıştırmak kopyalamaz, günceller) ve **deterministik UUID'ler** kullanırlar (aynı kaynak satırı her zaman aynı `entities.id`'ye eşlenir) — böylece her yabancı anahtarın işaret ettiği referans ID'leri sabit kalır.
- **Tehlikeli koda ağırlık veren bir test paketi** — **128 Python test fonksiyonu + 35 frontend test bloğu, ~5.617 satır**, ağırlıklı olarak sessizce veri bozabilecek ya da kota yakabilecek mantığa odaklı: `test_ai_routing.py` (60 test, 2.469 satır — normalleştirme determinizmi, birim politikası, ID çözümleme güvenliği, eşik yönlendirmesi, **denetim örneklemesinin determinizmi**, hata sınıflandırması, "model asla kendi üzerinde eğitilmez"), `test_bilingual_pipeline.py` (32, 1.120), `test_daily_ops.py` (30, 983), `test_pdf_page_markers.py`. Test adları neredeyse değişmezlerin bir tanımı gibi okunuyor — örneğin `rejects_stale_or_mismatched_db_ids`, `threshold_one_disables_ai_auto_finalization`, `build_labels_excludes_ai_model_outcomes`.
- **Operasyonel altyapı olarak dokümantasyon** — README, AGENTS kuralları, inceleyici iş akışı haritası ve canlı bir devir (handoff) STATE belgesi; *neden* Gemma metin modunda olduğunu, *neden* tarayıcıda kesin vetoya izin verilmediğini, *neden* PDF'lerin varsayılan olarak kaynak URL'sinden sunulduğunu, *neden* kokpit yapay zekâ listelerinin çıkış açısından hafif tutulması gerektiğini ve *neden* nihai doğrunun onay sonuçlarından geldiğini yazıya döküyor — böylece sonradan gelen ekip arkadaşları (ve yapay zekâ ajanları) kritik kararları yeniden türetmiyor ya da geri almıyor.

Burada **dürüst bir geçmiş** de var: şu anki crawler-v2 + kademe, depodaki *ikinci* tam hat mimarisi. Daha eski v1 hasatçısı (`pipeline.py` ile `harvester/`, `core/` ve `extraction/` paketleri, ~2.800 satır) silinmedi, korundu — çünkü gerçekten yayımlandı, çalıştı ve iyi fikirleri yeni sürüme taşındı. Onu tutmak depo boyutuna mal oluyor; karşılığında ise sistemin nasıl geliştiğine dair denetlenebilir bir kayıt kalıyor.

**İşin zor kısmı.** Çoğunlukla disiplin — ETL'i, tekrar çalıştırmanın asla bir gıdayı kopyalamayacağı kadar idempotent kılmak; testleri her yerde kapsama peşinde koşmak yerine bir hatanın felaket olacağı birkaç yüz satıra yoğunlaştırmak; ve dokümantasyonu, yanıltmak yerine gerçekten regresyonları önleyecek kadar doğru tutmak.

**Teknolojiler.** Supabase REST üzerinden Python ETL, deterministik UUID'ler, idempotent upsert'ler, `pytest`, Markdown + DOCX/PDF dışa aktarma araçları.

**Dosyalar ve satırlar.** `etl_usda_to_opennutri.py` (227), `etl_sr_legacy_to_opennutri.py` (343), test paketi (~5.617 satır), README / AGENTS / STATE / iş akışı haritası belgeleri ve korunan v1 hattı (~2.800 satır).

---

## 5. Kapanış özeti

OpenNutri'nin **tüm backend'ini** ben kurdum — "tüm bilimsel literatürü" alıp "güvenilir, kanıtı işaretlenmiş, kaynağı belli aday değerlerden oluşan temiz bir kuyruğa" çeviren ve bunu yapmak için kendi kendine çalışan sistem. Rakamlarla:

- **216 commit** boyunca **~31.800 satır** backend/operasyon/şema kodu; yalnızca veritabanı sözleşmesi **5.396 satır** (31 tablo, 75 RLS politikası, 26 RPC) ve tehlikeli mantık **~5.600 satır testle** sabitlenmiş durumda.
- Günde ~1.500 makaleyi eleyip ~20 pahalı çıkarımını en iyilerine harcayan bir **üç modelli kademe**; çıktısı bir insan gönderisiyle **aynı hash'i üreten** bir **deterministik normalleştirici**; ve güvenilir sonuçları otomatik tutan, belirsizleri bir insana yönlendiren, hatta güvenilenlerin bile örneklenmiş bir kısmını kalite kontrolü için incelemeye geri gönderen bir **güven kapısı**.
- Yayıncı bot duvarlarını gerçek bir proof-of-work çözücüyle aşan bir **tarayıcı**, her insan kararından asla kendi üzerinde eğitilmeden öğrenen bir **geri besleme döngüsü** ve bütün bunları beş dakikalık bir GitHub Actions cron'unda, Supabase ile Gemini'nin ücretsiz katmanları içinde, tek bir `FOR UPDATE SKIP LOCKED` ile koordine edilen beş paralel işçiyle çalıştıran bir **otomasyon katmanı**.

Ve bu bir prototip değil. **Canlı** ve **altı aydır üretimde işletiliyor, taşındı ve kurtarıldı** — hatalı bir politikanın veri sızdıracağı, takılı bir işçinin her şeyi durduracağı ve yanlış bir otomatik kabulün bir gıda veritabanını bozacağı, en az yetki ilkesine dayalı bir güvenlik modeli altında. Bu yüzden bunların her birinin olmaması için baştan tasarlanması gerekti.

Dünyadaki her gıda veritabanı hâlâ uzmanların sayıları makalelerden elle yazmasıyla kuruluyor. **Benim backend'im ise makaleleri bulan, onları okuyan, neyin güvenilir olduğuna karar veren ve yalnızca geri kalanı bir insana bırakan makine — her gün çalışacak kadar ucuz, bir besin etiketinde güvenilecek kadar dürüst.** OpenNutri'nin, elle derlemenin asla başaramayacağı ölçeği yakalamasını sağlayan da bu.

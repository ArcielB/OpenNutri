# OpenNutri — Arciel Aliognis Baez Zamora — Savunma Sunumu (Türkçe)

> **Bu belgenin kapsamı.** Bu, Arciel Baez Zamora'nın bireysel sunum metnidir. OpenNutri projesi üç kişi tarafından kuruldu; işler şöyle bölünür:
>
> - **Arciel Aliognis Baez Zamora — backend'in tamamı:** Supabase veritabanı (şema, RLS, RPC sözleşmesi, iş akışı motoru), üç-aşamalı YZ çıkarım kademesi, deterministik normalleştirici ve güven-kapılı yönlendirme, makale-keşif tarayıcısı, geri besleme-öğrenme döngüsü, gözetimsiz günlük-operasyon otomasyonu, referans-veri ETL'i, depolama/çıkış/PDF-teslim sağlamlaştırması, test paketi ve dokümantasyon. (~31.800 backend/ops/şema satırı; tek başına `migration.sql` 5.396 satır.)
> - **Ayşegül Doğan — etiketleyici frontend'inin tamamı:** PDF kanıt motoru, etiketleme çalışma alanı, gıda/besin otomatik tamamlaması ve kokpit/iş akışı görünümleri.
> - **Duc Huan Ngo — yeniden kullanılabilir & full-stack parçalar:** `fuzzyMatch` motoru, öneriler/ekler özelliği, parola-sıfırlama düzeltmesi, eski çakışma sistemi, tema merkezileştirmesi, sonsuz kaydırma.
>
> Bu belge **birinci tekil şahısla ("ben")** Arciel olarak yazılmıştır ve beş bölüme ayrılır:
> **1.** genel problem · **2.** ekip olarak nasıl çözdük · **3.** benim parçam ne ve neden gerekli · **4.** yaptığım her şey, tek tek (neden gerekli · nasıl yaptım · zor kısım · teknolojiler · dosyalar & satır sayıları) · **5.** bitiş özeti.
>
> Bu belgenin İngilizce sürümü ayrı bir dosyadadır: `Arciel_Baez_Zamora_Presentation_EN.md`.

---

## 1. Genel problem nedir?

Doğru **besin bileşim verisi** — bir gıdanın ne kadar protein, yağ, demir ya da C vitamini içerdiği — her besin etiketinin, diyet uygulamasının ve beslenme kılavuzunun arkasındadır. Ama bu veri hâlâ **elle** kurulur: uzmanlar bilimsel makaleleri okur ve **sayıları tek tek veritabanına yazar.** Bu yavaş ve pahalı olduğundan veritabanları dar kalır ve hızla eskir. Verinin kendisi zaten mevcuttur — sürekli yayımlanır, yalnızca yapısız PDF'lerin içinde kilitlidir — ama onu elle çıkarmak ölçeklenmez, denetimsiz bir yapay zekâya okutmak ise bir besin etiketinde güvenilemeyecek kadar çok yanlış sayı üretir.

## 2. Biz bunu (ekip olarak) nasıl çözdük?

**OpenNutri**'yi kurduk: her makaleyi sıfırdan bir insanın okuması yerine, **yapay zekâ okuyup sayıları önerir, insan ise yapay zekânın emin olmadığı makaleleri doğrular.** Üç parçaya ayrılır:

- **Bir backend hattı** (ben) — ilgili makaleleri bulur, PDF'leri indirir ve üzerlerinde YZ modelleri çalıştırarak *aday* besin değerleri üretir — ve hangi adayların otomatik tutulacak kadar güvenilir, hangilerinin bir insana gerek duyduğuna karar verir.
- **Bir veritabanı** (ben) — her şeyi saklar ve inceleme iş akışını yürütür.
- **Etiketleyici web uygulaması** (Ayşegül'ün frontend'i) — bir insanın, sistemin emin olmadığı aday değerleri kontrol edip düzelttiği yer.

**Benim parçam backend'in tamamı — insandan önce ve insanın etrafında olan her şey, ve insanın uygulamasının üzerine kurulduğu veritabanı sözleşmesi. Bu belgenin geri kalanı bununla ilgilidir.**

## 3. Benim parçam ne, neden gerekli ve neyi yaptım?

**Benim parçam backend'in tamamı** — veritabanı, YZ hattı, tarayıcı, öğrenme döngüsü ve bunların hepsini gözetimsiz, ücretsiz altyapı üzerinde, her beş dakikada bir çalıştıran otomasyon.

**Neden gerekli.** Frontend, ancak kendisine ulaşan şey kadar iyi olabilir. Birinin tüm bilimsel literatürden *doğru* makaleleri *bulması*, PDF'leri düşman yayıncı sitelerinden *çekmesi*, onları modellerle *karşılanabilir* derecede ucuza *okuması*, hangi sonuçların güvenilir hangilerinin bir insana muhtaç olduğuna *karar vermesi*, hepsini etiketleyicilerin, inceleyicilerin ve otomasyonun her birinin tam doğru işi yapmasına izin veren bir güvenlik modeli altında *saklaması* ve **tüm makineyi**, sunucu ve bütçe olmadan *çalışır tutması* gerekir. Backend budur. O olmadan ne kuyruk, ne YZ ön-doldurması, ne vurgulanacak kanıt, ne onaylanacak gerçek, ne de tarayıcının öğreneceği bir şey vardır.

Ve projenin asıl riskini taşır: sistemin otomatik kabul ettiği yanlış bir sayı doğrudan bir gıda veritabanına gider; bozuk bir RLS politikası özel veriyi sızdırır; takılan bir işçi tüm hattı durdurur; yanlış makaleleri kabul eden bir tarayıcı kıt model kotasını ve etiketleyici zamanını boşa harcar. Backend, "doğru, ucuz ve gözetimsiz"in aynı anda doğru olması gereken yerdir.

**Ne yaptığım, tek cümlede:** Kendi kendini çalıştıran bir araştırma hattı kurdum — literatürü tarar, PDF'leri almak için yayıncı bot-duvarlarını yener, üç-modelli bir huniden günde ~1.500 makaleyi eler (huni ~20 pahalı çıkarımını en iyi adaylara harcar), her modelin serbest-biçim çıktısını bir insanın göndereceği *tam aynı* yapılı şekle dönüştürür, güvene göre otomatik kesinleştirme mi yoksa insana yönlendirme mi olduğuna karar verir, hepsini 75-politikalı bir güvenlik modeli altında saklar ve sonraki sefer daha iyi taramak için her insan kararından öğrenir — hepsi Supabase'in ve GitHub'ın ücretsiz katmanlarında. Somut olarak yedi şeyin sahibiyim; bir sonraki bölüm bunları tek tek anlatıyor:

1. **Veritabanı & güvenlik sözleşmesi** — 31 tablo, 75 RLS politikası ve diğer her parçanın çağırdığı RPC'ler.
2. **Makale-keşif tarayıcısı** — ön kapı: arama → filtre → edinim, bot-duvar yenen bir PDF çekiciyle.
3. **Üç-aşamalı YZ kademesi** — Gemma → Gemini Flash-Lite → Gemini Flash, üç model boyunca tek paylaşılan sözleşme.
4. **Deterministik normalleştirici & güven-kapılı yönlendirme** — model çıktısını veritabanıyla-kıyaslanabilir veriye çevirmek ve insan mı otomatik mi kararını vermek.
5. **Geri besleme-öğrenme döngüsü** — insan onayları sonraki taramayı yeniden puanlar.
6. **Günlük-operasyon otomasyonu** — 5 dakikalık bir GitHub Actions cron'unda bir denetleyici + beş paralel işçi.
7. **Referans veri, PDF/çıkış sağlamlaştırması, testler & dokümantasyon** — bunu bir demo değil bir *sistem* yapan destek katmanı.

## 4. Yaptığım her şey, tek tek

Her parça için: **neden gerekli · nasıl yaptım · zor kısım · teknolojiler · dosyalar ve satır sayıları.**

---

### 4.1 Veritabanı & güvenlik sözleşmesi — *tüm projenin omurgası*

**Neden gerekli.** OpenNutri'nin diğer her parçası burada buluşur. Frontend bir etiket gönderemez, tarayıcı bir makale kaydedemez, model işçileri bir görev alamaz ve pano gerçeği gösteremez — bu tablolar, RPC'ler ve politikalar olmadan. Bu tek dosya, Python hattı ile React uygulaması arasındaki **sözleşmedir.**

**Nasıl yaptım.** `migration.sql`, **31 tablo, 26 fonksiyon/RPC, 75 RLS politikası, 69 indeks, 2 tetikleyici ve 22 `SECURITY DEFINER` fonksiyonu** tanımlayan **5.396 satırdır.** **Tek, yakınsayan, idempotent bir migrasyon** olarak yazılmıştır — canlı veritabanına karşı istenildiği kadar yeniden çalıştırılabilir: sütunlar `IF NOT EXISTS` ile eklenir, `CHECK` kısıtları `DO $$ … $$` blokları içinde önce `information_schema` sorgulanarak bırakılıp yeniden kurulur (yeniden çalıştırma asla hata vermez) ve yanlış tipteki eski bir sütun yerinde saptanıp dönüştürülür. Şema beş katmandır:

- **Referans katmanı** — `entities` (kanonik gıdalar), `entity_aliases`, `master_nutrients`, `sources` ve `claims` (miktar, birim, baz, güven, kaynakla normalize `gıda × besin × kaynak` gerçeği). Herkesçe okunur-paylaşımlı; yalnızca servis rolü yazar.
- **Keşif katmanı** — `papers` (merkez; hem `doi` hem DOI-eksik/çapraz-sağlayıcı tekilleştirme için `canonical_key`, artı yönlendirme-özeti sütunları) ve idempotent keşif defteri `paper_search_hits` (`hit_key`'i SQL *içinde* hesaplanan bir md5; mükerrer satırlar `UNIQUE` indeks eklenmeden önce bir `ROW_NUMBER()` penceresiyle silinir). Ayrı `paper_search_batches` tabloları, geri besleme döngüsü için sorgu-başına huni sayaçlarını saklar.
- **Etiketleme katmanı** — `annotations` (`UNIQUE(paper_id, user_id)`), `food_items`, `annotation_nutrient_values`; özel-vs-kanonik ayrımı (`is_custom_*` + null'lanabilir FK), bir etiketleyicinin referans DB'de henüz olmayan bir şeyi, olanların eşlemesini kaybetmeden kaydetmesini sağlar.
- **İş akışı motoru** — iki kez yeniden kuruldu ve şema bunu **kanıtlıyor**: eski slot modeli, Huan'ın eski çakışma modeli (`paper_conflict_candidates` görünümü dâhil) ve mevcut **genel kuyruk + onay** modeli: değiştirilemez `paper_label_submissions`, `paper_label_approvals` (yapısal `correction_diff_json` ile) ve nihai `paper_review_outcomes`. Bir `BEFORE INSERT/UPDATE` tetikleyicisi, `human_review_ready` olmayan bir makaleye iş bağlamayı reddeder — yönlendirme hatalarına karşı şema seviyesinde bir koruma.
- **YZ-yönlendirme katmanı** — `ai_extractions` (tam denetim izi), `routing_stage_configs` (**veri-güdümlü aşama tablosu** — eşikler, yedek modeller, giriş modu — böylece hattın şekli koddur değil veridir) ve `paper_stage_tasks` (iş kuyruğu).

**Güvenlik modeli** 31 tablonun tümünde en-az-ayrıcalıktır: altı `SECURITY DEFINER` yüklem fonksiyonu üzerine kurulu **75 RLS politikası.** Zarif olanı: **`current_user_can_write() = NOT current_user_is_tester()`** — salt-okunur eğitim erişimi, her tabloda yeniden kodlanmak yerine *tek bir olumsuzlamadan* düşer. Yüklemler `SECURITY DEFINER` olduğundan, RPC'ler bir tarayıcı kullanıcısına `paper_stage_tasks`, `ai_extractions` ya da başkalarının etiketlerine doğrudan okuma vermeden kuyruk dilimlerini ve toplamları sunabilir. **Kayıt allowlist'i** yalnızca `supabase_auth_admin`'e verilmiş bir auth hook'uyla uygulanır; allowlist tablosundaki tüm istemci ayrıcalıkları geri alınmıştır — böylece tarayıcıdan ne okunabilir ne aşılabilir. Ve `upsert_reviewer_admin_config`, **sıfır** etkin kokpit-yazma inceleyicisi bırakacaksa tamamlanmayı reddeder: tüm ekibi dışarıda kilitleyemezsiniz.

Sözleşmenin iki parçası ayrıca anılmayı hak ediyor:
- **`claim_paper_stage_tasks`** — eşzamanlılık ilkeli. Kuyruktaki görevleri `ORDER BY attempt_count ASC, priority DESC … FOR UPDATE SKIP LOCKED` ile alır. O tek tümce, `FOR UPDATE SKIP LOCKED`, beş paralel GitHub Actions işçisinin sıfır koordinasyon ve sıfır çift-işleme ile *ayrık* görev kümeleri almasını sağlayan şeydir — tüm paralel tasarım buna dayanır.
- **Deterministik yük inşacıları** — `build_annotation_submission_payload`, kanonik gönderi JSON'unu SQL'de Python normalleştiricisiyle *aynı* (boşluk-daraltma, `round(value,6)`, deterministik sıralama) kurallarla kurar; böylece bir insan gönderisi ile aynı verinin YZ çıkarımı **birebir aynı hash'lenir.** `build_label_payload_diff`, SQL'de tam yapısal bir farktır (eklenen/eksik gıdalar ve besin satırları için anti-join'ler) ve çıktısı etiketleyici-performans metriklerinin ham maddesidir.

**Zor kısım.** Bir dosyayı sonsuza dek yeniden uygulanabilir kılmak *ve* etiketleyicilere, testçilere, kokpit kullanıcılarına, onaylayıcılara ve servis-rolü otomasyonuna 31 tablo boyunca tek bir özel satır sızdırmadan tam doğru yüzeyi vermek — aynı zamanda YZ ve insan yüklerini hash ile kıyaslanabilecek kadar deterministik tutarak.

**Teknolojiler.** PostgreSQL / Supabase, PL/pgSQL, Row-Level Security, `SECURITY DEFINER` fonksiyonları, `FOR UPDATE SKIP LOCKED`, JSONB, SHA-256-kıyaslanabilir kanonik yükler.

**Dosyalar & satırlar.** `apps/expert-annotator/migration.sql` (**5.396**). **43 commit.**

---

### 4.2 Makale-keşif tarayıcısı — *sistemin ön kapısı*

**Neden gerekli.** Tarayıcı yanlış makaleleri kabul ederse kıt model kotası ve etiketleyici zamanı boşa gider; çok katıysa hat gerçek bileşim tablolarını hiç bulamaz. Tarayıcı, **ürünün alan tanımını** puanlama, doğrulama ve tekilleştirmeye kodlar. Geniş beslenme sorgularının döndürdüğü makalelerin çoğu doğrudan gıda-bileşim tablosu *değildir* — müdahale çalışmaları, yem denemeleri, derlemelerdir — bu yüzden tarayıcı, herhangi bir pahalı işten önce adayları daraltmalı, ama **tek bir başıboş kelime yüzünden** gerçek bir makaleyi sert biçimde reddetmeden.

**Nasıl yaptım.** `FoodCompositionCrawlerV2`, **Arama → Filtre → Edinim** yürüten ~2.200 satırlık bir orkestratördür (~70 metot); pahalı adım en sona gelir:

1. **Arama** — Europe PMC / OpenAlex / Semantic Scholar'dan (Türkçe için DergiPark) yalnızca-metadata getirme, kaynak-başına sorgu işleme.
2. **Filtre** — başlık+özet üzerinde iki-kapılı, tamamen **toplamsal** bir alaka kararı, **henüz PDF inilmeden.** Kural (AGENTS'ta zorunlu) *sert-negatif veto yok* — bir negatif ifade bir cezadır, asla otomatik-ret değil; böylece "klinik çalışma" gibi tek bir kelime, bir bileşim tablosu da bildiren bir makaleyi öldüremez. Ucuz arama kapısı bileşim ifadelerini, gıda/besin terimlerini, bir `mg/100g` tarzı birim regex'ini ve gıda+besin kombinasyonlarını yumuşak cezalara karşı puanlar; daha zengin metadata kapısı üç **öğrenilmiş** sinyal ekler — kaynak-başına önsel, dil-kapsamlı çapa ifadelerine **cümle-gömme benzerliği** ve **öğrenilmiş geri besleme n-gram puanı** (§4.5). Her katkı bir `{kod, metin}` gerekçesi olarak loglanır, böylece her karar çalışma manifestinde tamamen açıklanabilir.
3. **Edinim** — yalnızca metadata-geçenlerin PDF'i çekilir, sonra **çok daha katı bir tam-metin kapısı** (`validate_pdf_text`): kaynakça bölümlerini soyar (bibliyografya puanı şişirmesin), AOAC/HPLC/GC/ICP yöntem kanıtını ve `mg/100g` birimlerini sayar ve güçlü bir puan **ve** bir tablo sinyali **ve** bir gıda sinyali **ve** bir proksimat-besin paneliyle ≥4 örtüşme (nem/protein/yağ/kül/lif/karbonhidrat/enerji/mineraller) gerektirir. Geri-çağırım için indirmeye gevşek, kesinlik için indirmeden sonra katı. Kelime eşleşmesi Unicode kelime-sınırı duyarlıdır; böylece Türkçe "et" sözcüğü "diet" içinde değil, bir kelime olarak eşleşir.

**Asıl zor kısım — PDF edinimi.** Yayıncı PDF'leri direnir. `_download_candidate`, katmanlı bir yedek merdivenidir: PMC Açık-Erişim paketi (OA API XML'ini ayrıştır, PDF linklerini dene, yoksa **`.tar.gz`'yi indirip en büyük `.pdf` üyesini çıkar**); doğrudan `urllib` çekimi (gövde `%PDF` ile başlıyor mu doğrula); hata hâlinde **tam tarayıcı User-Agent'lı `curl` yedeği** (birçok yayıncı tarayıcı-dışı ajanları engeller); ve yanıt bir HTML bot-duvarıysa, **bir PMC proof-of-work çöz** — `_solve_pmc_pow`, meydan okumayı sayfadan ayrıştırır ve **bir hashcash nonce'unu brute-force eder** (`md5(meydan+nonce)` N sıfırla başlayana dek artırır), sonra çözüm çereziyle tekrar dener. Gerçek bir madencilik döngüsüyle yenilen bir bot-duvarı.

Tarayıcı **aynı makaleyi asla iki kez taramaz**: aramadan önce her canlı `papers.canonical_key`'ten (Supabase REST API'den sayfalanarak) artı yerel terminal makale durumlarından (arama-kapısı retleri dâhil; böylece bir metadata reddi yeniden çekilmez) bir atlama-kümesi kurar. Kabul edilen PDF'ler **kimliğe göre** adlandırılır (`pmcid_*` / `doi_*` / hash'lenmiş `canonical_key`) ve tüm çalışma **duvar-saati sınırlıdır** — 2.400 saniyelik son tarih dolduğunda temiz durur ve yine de her kabul edilen kısmi sonucu artı kendi kendini belgeleyen bir huni manifestini yazar; böylece bir GitHub zaman aşımı asla iş kaybetmez.

Küçük ama yük taşıyan bir modül, `models.py`, tarayıcının, her kaynak adaptörünün, yükleyicinin ve geri besleme dışa aktarıcısının hepsinin içe aktardığı **üç deterministik kimlik anahtarını** (`build_canonical_key`, `build_search_hit_key`, `build_search_batch_key`) tanımlar — böylece bir makale her yerde *aynı* kimliği hesaplar; SQL `UNIQUE` indekslerinin, atlama-kümesinin ve toplu (batch) geri beslemenin merkezi bir koordinatör olmadan hizalanmasını sağlayan budur.

**Teknolojiler.** Python, Europe PMC / OpenAlex / Semantic Scholar / DergiPark, `urllib` + `curl`, `tarfile`, `pdftotext`, sentence-transformers gömmeleri, MD5 hashcash proof-of-work, Supabase REST.

**Dosyalar & satırlar.** `food_paper_crawler/crawler_v2.py` (**2.215**), `ranking.py` (485), `models.py` (374), `embeddings.py` (138), `dergipark_source.py` (687) ve diğer kaynak adaptörleri. **30 commit.**

---

### 4.3 Üç-aşamalı YZ kademesi — *Gemma → Gemini Flash-Lite → Gemini Flash*

**Neden gerekli.** Nihai, güçlü Gemini çıkarımı kıt ve pahalı kaynaktır — ücretsiz kotada günde yaklaşık **20 çağrı**. Her adayı en güçlü modelle elemek, bu bütçeyi çoğu işe yaramaz makaleye harcardı. Bu yüzden her kabul edilen makale, birçok adayı ucuza işleyen, sonra pahalı çağrıları yalnızca **en yüksek puanlı** alt kümeye harcayan bir **üç-aşamalı huniden** geçer:

```
Küçük  — gemma_proof_extraction_v1   (gemma-4-31b-it, 26B yedek)  metin modu  ~1.500/gün
Orta   — gemini_flash_lite_triage_v1 (gemini-3.1-flash-lite)                  ~500/gün
Güçlü  — gemini_flash_db_payload_v2  (gemini-3.5-flash)           yerel PDF   ~20/gün
                                                                                │
                                                                  human_review_ready
```

**Nasıl yaptım.** Üç aşama da tek bir prompta (`opennutri_evidence_payload_v2`) karşı *aynı* paylaşılan çıkarım sözleşmesini çalıştırır. Prompt, kodda ürünün alan tanımının ta kendisidir: "yararlı OpenNutri verisi"nin tam olarak ne olduğunu (doğrudan gıda/ürün bileşimi) **boş** olana karşı (müdahale/etki çalışmaları, tek-seferlik deneysel formülasyonlar, sindirilebilirlik, duyusal, biyobelirteçler, derleme toplamları) ~25 satırda sayar — gerçek gıdalar veritabanı ile alakasız ziraat makaleleri yığını arasındaki fark. Her çıkarılan satır **kanıt-konum metadata'sı** taşımalıdır — `table_label`, `page_hint`, kısa birebir `source_quote` (≤20 kelime), `source_location_type`, `section_heading`, `paragraph_hint` — ki Ayşegül'ün frontend'i sonra onu vurgulayabilsin. Tüm promptaki tek en önemli talimat: `page_hint`, **`===== PDF PAGE N =====` işaretlerinden 1-tabanlı PDF sayfa indeksidir, asla basılı dergi sayfası değil** — çünkü basılı-sayfa uyuşmazlığı tam olarak vurgulamayı bozan şeydir.

İki sağlamlık mekanizması bunu üretimde hayatta tutar:
- **Model JSON sapmasından sağ çıkmak.** LLM'ler sürekli bozuk veya farklı-şekilli JSON döndürür; naifçe bu sonsuz bir yeniden-deneme döngüsüdür. Değerlendirici markdown çitlerini soyar, prose içine sarılmış olsa bile ilk *dengeli* JSON'u çıkarmak için string/escape/derinlik durumunu izleyen **elle yazılmış dengeli-parantez tarayıcısı** çalıştırır ve **dört farklı şekli** kabul eder (istenen nesne, çıplak satır dizisi, tek-elemanlı-dizi sarılı nesne ve iç içe `food → nutrients[]`), hepsini tek kanonik köke indirger. Zorunlu alanı eksik bir satır düşürülür, ölümcül değil. Böylece geçerli-ama-farklı-şekilli çıktı, bir yeniden deneme tetiklemek yerine kurtarılır.
- **Yerel PDF girişi + gerçek sayfa numaraları.** Güçlü aşamada PDF yerel belge parçası olarak eklenir (15 MB altında satır içi, aksi hâlde Files API üzerinden, hem geçici dosyayı hem uzak yüklemeyi silen bir `finally` temizliğiyle); bu, modele işlenmiş sayfalar ve tablolar verir ve gerçek sayfayı bildirmesini sağlar. Metin-modu aşamalarda `pdftotext` çıktısı form-feed'lerde bölünür ve herhangi bir kısaltmadan **önce** `===== PDF PAGE N =====` işaretleriyle enjekte edilir; böylece sağ kalan sayfalar doğru numaraları korur. **Gemma neden metin-modu kalır:** bir prob, Gemma'nın PDF parçalarını *kabul ettiğini* ama **5 sayfalık bir PDF'te 600 sn'yi aşarak zaman aşımına uğradığını** ölçtü — ~1.500/gün'lük bir aşama için ölümcül — bu yüzden ona, görüntü işlemeden zaten doğru sayfa numaraları veren sayfa-işaretli metin verilir. Bu karar, naifçe geri alınmaması için kodlanmış ve belgelenmiştir.

**Yürütme motoru** (`process_stage_queue.py`, 1.560 satır), **tek bir kötü makale veya kota dalgalanması otomasyonu durduramayacak** şekilde kurulmuştur: görevler atomik alınır (`claim_paper_stage_tasks`); **en-az-deneme-önce** sıralanır, böylece sürekli başarısız bir makale tekele alamaz; 120 dk'dan eski `processing` satırları yeniden kuyruğa alınır; model herhangi bir satır alınmadan *önce* kurulur (eksik anahtar hızlıca başarısız olur); sert bir `SIGALRM` makale-başına zaman aşımı (300 sn) bir yavaş makaleyi sınırlar; ve bir **hata taksonomisi** hataları doğru yönlendirir — geri-alınamaz model-yapılandırma hataları başarısız olur ve otomasyonu durdurur, geri-alınabilir hatalar yapılandırılmış yedek modeli (Gemma 31B → 26B) **aynı denemede** dener, kota hataları yeniden kuyruğa alınır ama **deneme sayısını azaltır** (bir kota beklemesi asla makale hatası gibi görünmez) ve iki geri-alınamayan denemenin ötesinde herhangi bir şey, sonsuza dek döngüye girmek yerine başarısız olur.

**Zor kısım.** Tek bir sözleşmeyi farklı giriş modları ve farklı hata davranışları olan üç farklı modelde çalıştırmak, çıktıyı *veritabanı eklemesi* için yararlı (yalnızca makul bir özet değil) tutmak ve kotayı geri-alınabilir bir çalışma-zamanı hatasından, geri-alınamaz bir yapılandırma hatasından doğru biçimde ayıran hata yönetimi kurmak — çünkü her biri farklı ele alınmalıdır yoksa gözetimsiz kuyruk bozulur.

**Teknolojiler.** Python, Gemma + Gemini (Google GenAI SDK), yerel-PDF + metin giriş modları, `pdftotext`, `SIGALRM` zaman aşımları, elle yazılmış bir JSON-kurtarma ayrıştırıcısı, Supabase RPC'leri.

**Dosyalar & satırlar.** `evaluator/unified_evaluator.py` (687), `ai_routing.py` (842), `scripts/process_stage_queue.py` (1.560), artı `recover_gemini_candidates.py` (446) ve `flash_lite_triage_experiment.py` (245). **34 commit.**

---

### 4.4 Deterministik normalleştirici & güven-kapılı yönlendirme — *bir tahminin güvenilir veriye, ya da bir insanın işine dönüştüğü yer*

**Neden gerekli.** Bir modelin ham çıktısı güvenilir veritabanı verisi değildir. Tutulabilmesi için iki şey olmalı: bir insan inceleyicinin göndereceği **tam aynı normalize yapıya** dönüştürülmeli (böylece YZ ve insan çıktısı birbiriyle değiştirilebilir ve kıyaslanabilir olur) ve sistem, güvene göre **otomatik mi tutacağına yoksa bir insana mı göndereceğine** karar vermeli — çünkü her makaleyi elle kontrol etmek *ölçeklenmeyen* şeydir, ama her şeyi otomatik kabul etmek yanlış sayılar üreten şeydir. Bu, "YZ önerir, insan emin olmadıklarını doğrular"ın kalbidir.

**Nasıl yaptım — normalleştirici (`normalize_ai_payload_with_summary`).** Her model satırı katı bir eleme yarışından geçer:
1. **Zorunlu-alan kapısı** — gıda/besin/miktar eksik herhangi bir satırı düşür (`missing_required_field` olarak sayılır).
2. **Birim standartlaştırma (`_standardize_unit`)** — katı bekçi. Yalnızca yedi standart birim sağ kalır: `g/100g`, `mg/100g`, `μg/100g`, `kcal/100g`, `kJ/100g`, `IU/100g`, `%`. `µ`-vs-`μ`, casefold ve gram/miligram/mikrogram/mcg/kcal/kJ/IU'nun her yazımını ele alır, artı bir **baz politikası**: per-100g zorunlu, **kuru-madde reddedilir**, ama taze/yaş/olduğu-gibi/yenilebilir-kısım kabul edilir. Retler `unsupported_unit_or_basis` olarak sayılır.
3. **Referans çözümleme (`_resolve_reference_row`)** — **önce-ID** (modelin iddia ettiği `food_fdc_id`/`nutrient_id`'yi canlı bir satıra karşı *ve* o satırın adının eşleştiğini doğrula), sonra tam ad, sonra takma ad. Ad çözümleyici **belirsiz adları hiçbir şeye eşler** — iki DB satırı bir adı paylaşıyorsa hiçbiri eşleşmez — böylece asla yanlış bağ kurmaz. Çözülmemiş gıdalar/besinler düşürülmez, açık `is_custom_food`/`is_custom_nutrient` satırları olarak *tutulur*.
4. **Deterministik gruplama & sıralama** — satırlar çözülen gıdaya göre gruplanır, uzun kararlı bir anahtarla sıralanır, değerler `round(…, 6)`. Bu determinizm tüm meselenin özüdür: yük **kanonik serileştirilir ve SHA-256 hash'lenir**, böylece iki eşit çıkarım birebir aynı hash'lenir ve bir YZ çıkarımı bir insan gönderisiyle bayt-bayt kıyaslanabilir.
5. **Özet muhasebesi** — kabul/ret/eşlenmemiş sayıları ve bir `rejection_reasons` histogramı her çıkarımda saklanır, böylece kokpit satırların *neden* düşürüldüğünü gösterebilir.

**Nasıl yaptım — güven kapısı (`ai_routing.py`).** Normalleştirmeden sonra makale kümelenir ve yönlendirilir:
- **`classify_routing_bucket`**, her makaleyi `overall_confidence`'ını aşamanın kendi `positive_threshold` / `negative_threshold`'una (veri-güdümlü aşama yapılandırmasından okunan, "veri var" ve "veri yok" için ayrı eşikler) karşı kıyaslayarak **yüksek/düşük × pozitif/negatif** kovalarına ayırır.
- **`route_bucket`** asıl kapıdır: **düşük-güven → `human_review_ready`** (Ayşegül'ün etiketleme kuyruğuna gider); **yüksek-güven-pozitif → `ai_finalized_has_data`** (otomatik tutulur); yüksek-güven-negatif → veri-yok olarak kesinleştirilir. Zaten insan gerçeği olan bir makalenin üzerine asla yazılmaz.
- **`stable_audit_sample`**, otomatik-kabul edilenler üzerindeki kalite kontrolüdür: `SHA256(paper|stage|model)`, `audit_rate × 2^64`'e karşı kıyaslanır. **Deterministiktir** — aynı makale her zaman aynı denetim kararını alır — ve yüksek-güvenli otomatik-kesinleştirmelerin yapılandırılabilir bir kesrini bile insan incelemesine geri zorlar; böylece otomatik-kabul yolu körü körüne güvenilmek yerine sürekli doğruluk için örneklenir.
- **Ham-pozitif kurtarma** — pozitif görünen ama *boş*'a normalleşen bir Gemma çıktısı, tam ham satırları varsa ya da güven ≥ 0,75 ya da bileşim diliyle ≥ 0,6 ise yine de sonraki aşamaya ilerler — böylece ayrıştırıcı/normalleştirici sapması olası-gerçek bir makaleyi asla sessizce düşürmez, katı normalleştirme yine de nihai girişi kapılar.

Ve huninin motoru, **`score_followup_priority`**: her yararlı çıktı, güvenden, kabul/kanıt/per-100g/tablo satır sayılarından, bileşim dili için bir doğrudan-uyum bonusundan ve promptun "boş" tanımını yansıtan **yumuşak cezalardan** (derleme/meta-analiz, yem/sindirilebilirlik, duyusal/biyobelirteç, tek-seferlik formülasyon, tedavi/ekstrakt) bir tamsayı puan alır (−1000…1000 sınırlı). Sonraki aşama görevleri *bu puana göre sıralı* alır; böylece Flash-Lite Gemma'nın çıktısının en iyi 500'ünü, nihai Gemini de onun en iyi 20'sini işler. "Neyin yararlı olduğu" yargısı bilerek iki kez kodlanmıştır — bir kez model için promptta, bir kez sıralayıcı için önceliğte — böylece eleyicinin sıralaması çıkarıcının kararıyla hizalı kalır.

**Zor kısım.** İnsan/YZ sınırı boyunca determinizm: bir Python normalleştiricisini ve bir SQL inşacısını **birebir aynı** yapı üretecek hâle getirmek (böylece iki gerçek üreticisi hash ile kıyaslanabilir) — ve *yeniden üretilebilir* (aynı makale, aynı karar, her seferinde), *denetlenebilir* (her zaman nedenini görebilirsiniz) ve *kendini-kontrol eden* (otomatik-kabullerin örneklenen bir kesri insanlara geri zorlanır) bir güven kapısı tasarlamak — "model emin görünüyordu" diyen bir kara kutu yerine.

**Teknolojiler.** Python, SHA-256 kanonik hashleme, deterministik JSON serileştirme, eşik-tabanlı kümeleme, yeniden-üretilebilir hash-tabanlı denetim örneklemesi, PL/pgSQL ayna inşacıları.

**Dosyalar & satırlar.** `ai_routing.py` (842), `test_ai_routing.py` ile (**2.469 satır, 60 test** — projedeki en yoğun test edilen dosya, çünkü burası bir hatanın veritabanını sessizce bozduğu yer). **Kademe genelinde 34 commit.**

---

### 4.5 Geri besleme-öğrenme döngüsü — *insan onayları sonraki taramayı öğretir*

**Neden gerekli.** OpenNutri'yi statik bir anahtar-kelime tarayıcısı yerine *gelişen* bir hat yapan budur. Bir insanın onayladığı ya da reddettiği her makale, hangi kelimelerin ve ifadelerin gerçekten yararlı bir makaleyi öngördüğüne dair kanıttır — ve bu kanıt, tarayıcının sonraki sefer adayları nasıl puanladığını değiştirmeli.

**Nasıl yaptım.** `update_terms.py` (1.219 satır) döngüyü kapatır:
```
insan onayları (paper_review_outcomes) ─▶ log-odds n-gram puanlama ─▶ latest.json ─▶ sonraki tarama daha iyi sıralar
```
- **Gerçek seçimi bilerek tutucudur.** Pozitifler/negatifler `paper_review_outcomes`'tan **yalnızca `truth_source_kind = 'human_review'` olduğunda** gelir — YZ-kesinleştirilmiş sonuçlar köken için saklanır ama **dışlanır**, böylece *model asla kendi üzerinde eğitilmez.* Açık çakışmalar çıkarılır (belirsiz gerçek öğretmez); bekleyen/geçersizleşen gönderiler asla sayılmaz; eski etiketler yalnızca çözülmüş sonucu olmayan eski makaleler için bir yedektir.
- **Puanlayıcı, üç kova üzerinde yumuşatılmış log-odds'tur** — iyi, kötü ve **arka plan** (geri kalan her şey). Her n-gram için belge frekansları her kovada, **başlık-yalnız ve başlık+özet için ayrı ayrı** sayılır, sonra add-α yumuşatmasıyla bilgilendirici Dirichlet log-odds (Monroe ve diğ. yöntemi) hesaplanır. Net sinyaller `title_net = title_good − title_bad` ve `ta_net`, tarayıcının tam olarak çarptığı şeydir. **Arka plan kovası, özgüllüğün anahtarıdır**: yalnızca iyi-vs-kötü puanlamak sadece yaygın kelimeleri ödüllendirir; her birini büyük arka plan külliyatına karşı puanlamak gerçekten yararlı makalelere *özgü* terimleri öne çıkarır. Başlık ve başlık+özet ayrı tutulur çünkü bir *başlıktaki* yüksek-sinyalli bir ifade, aynı ifadenin bir özette gömülü olmasından daha güçlü kanıttır. Tohum bileşim ifadeleri, öğrenilmiş kanıtın zamanla geçersiz kılabileceği *yumuşak* bir önsel alır.
- **Dile-özgü yedi havuz üretir** `latest.json`'a: `weighted_terms` (yumuşak filtre puanı), `query_phrases` (yeni aramalar kurmak için), `anchor_phrases` (gömme çapaları), `pair_scores`, `batch_scores`, `source_priors` ve `concept_scores` — böylece tek bir etiketli külliyattan üç ayrı öğrenilmiş sinyal tarayıcıya ulaşır: n-gram filtre puanları, gömme çapaları ve sorgu-üretim/sıralama puanları.

**Zor kısım.** Sistemin **kendi üzerinde eğitilmediğinden** ve **belirsiz gerçekten öğrenmediğinden** emin olmak — ve geri beslemeyi, bir sırayı düşürebilen ama bir insanın hâlâ isteyebileceği bir makaleyi asla sert-reddedemeyen *yumuşak* bir puan tutmak (tarayıcının veto-yok kuralıyla tutarlı). Artı istatistik: arka-plan-külliyatı log-odds'u ve add-α yumuşatması, küçük ve gürültülü erken bir etiket setinin çöp ağırlıklar üretmesini engelleyen şeydir.

**Teknolojiler.** Python, yumuşatılmış/bilgilendirici-Dirichlet log-odds (Monroe ve diğ.), n-gram belge-frekansı sayımı, dile-özgü ağırlık havuzları, Supabase gerçek dışa aktarımı.

**Dosyalar & satırlar.** `food_paper_crawler/feedback/update_terms.py` (**1.219**), `feedback_config.py`, `supabase_terms.py` (481), `feedback_terms.py` ile.

---

### 4.6 Günlük-operasyon otomasyonu — *kendi kendini çalıştıran gerçek bir hat, ücretsiz*

**Neden gerekli.** Yukarıdakilerin hepsinin gerçekten *çalışması* gerekir — tara, yükle, günde ~1.500 makaleyi ele, triyaj yap, çıkar — sürekli, özel bir sunucu ve bütçe olmadan. Buradaki her mimari seçim tek bir kısıttan kaynaklanır: bunu, işe-başına zaman sınırı olan GitHub-barındırmalı runner'larda, Gemini ücretsiz-katman günlük kotasına karşı yap.

**Nasıl yaptım.** `.github/workflows/daily-ops.yml`, **5 dakikalık bir cron**'da çalışır ve iki tür iş başlatır:
- **Bir serileştirilmiş `refill-controller`** — tarama/yükleme/dolum yapmaya izinli *tek* iş; `cancel-in-progress: false` olan bir `concurrency` grubu altında, böylece en fazla biri çalışır ve yeni bir tık asla devam eden bir taramayı öldürmez.
- **Beş paralel `drain-workers`** (`matrix: worker:[1..5]`) — yalnızca zaten-kuyruktaki model görevlerini boşaltır, **denetleyiciye bağlı değildir** ("denetleyici başarısız olsa bile boşaltma devam etmeli") ve hafif bir bağımlılık seti kurar. Beşinin paralel güvenle çalışabilmesinin **tek nedeni** alımın `FOR UPDATE SKIP LOCKED`'tan geçmesidir — her biri sıfır koordinasyonla ayrık bir görev kümesi alır.

**Denetleyici** bir döngü değil, tek bir tıktır: bayat görevleri yeniden kuyruğa al → aşama-başına bugün-tamamlananları say → *etkin* eleme işini say → **150'lik bir etkin hedefe** karşı bir açık hesapla (her tarama daha yeni geri beslemeden yararlansın diye bilerek düşük tutulur) → sonra açık bir dur/dolum karar ağacı (günlük hedefe ulaşıldı, ya da yeterli etkin iş, ya da 75 dakikalık son tarih, ya da bir depolama sınırı → dur; yoksa açığı 30-makalelik sınırlı parçalar hâlinde tara ve kaynak tükenmesini sapta). **Boşaltma** tıkı, eleme 1.500/gün hedefinin altındaysa bir Gemma dilimi boşaltır, alt-akım triyaj + nihai-Gemini dilimlerini **araya alır** (böylece elenecek bir şey kalmasa bile Gemini akmaya devam eder) ve eleme hedefine ulaştığında nihai Gemini'yi 20/gün'e kadar boşaltır ve yeni insan-hazır makaleleri hemen etiketleme kuyruğuna atar.

Onu ücretsiz-katman tavanından sağ çıkaran şey: **iki saat dilimi boyunca kota-günü muhasebesi** (Gemma bir UTC gününü, her iki Gemini aşaması Google'ın sıfırlamasıyla eşleşmek için bir `America/Los_Angeles` gününü sayar), **tembel modül yükleme** (boşaltma işçileri tarayıcının içe-aktarma maliyetini asla ödemez) ve **üç iç içe duvar-saati bütçesi** (denetleyici 75 dk, tarayıcı kısmi-sonuç yazımlı 2.400 sn, her model çağrısı 300 sn), böylece bir yavaş makale veya uzun tarama iş sınırını asla aşamaz. Makale PDF'leri **kaynak-URL/talep-üzerine** tutulur (`OPENNUTRI_STORE_PDFS_IN_SUPABASE=0`) çünkü onları saklamak Supabase ücretsiz depolama/çıkış sınırlarını aşardı — ve bir **aynı-köken PDF proxy'si** (`api/pdf.js`, bir Vercel serverless fonksiyonu) CORS-dostu-olmayan yayıncı PDF'lerini sunucu tarafında gerçek sağlamlaştırmayla çeker: yalnızca-https, **SSRF koruması** (localhost/iç hostları ve IP literallerini reddeder), 25 MB sınırı, **`%PDF-` sihirli-bayt kontrolü** (açık proxy olarak istismar edilemesin), 25 saniyelik zaman aşımı ve **1 yıllık değişmez önbellek** (her makale yukarı akıştan en fazla bir kez çekilir).

**Zor kısım.** **5 dakikalık bir pencere içinde sürdürülebilir ve idempotent** bir tık durum makinesi kurmak — öldürülen runner'lardan, çakışan tıklardan, iki kota saat diliminden ve denetleyici/boşaltma ayrımından sağ çıkarak — karşılayamadığım kolay, sürekli-çalışan bir daemon yerine. GitHub işleri öldürülür ve çakışır; DB alımı atomik olmalı; bir başarısız makale asla bir işçiyi tekele almamalı; ve denetleyici öldüğünde bile boşaltma devam etmeli.

**Teknolojiler.** GitHub Actions (cron, matrix, concurrency grupları), `FOR UPDATE SKIP LOCKED`'lı Supabase RPC'leri, Vercel serverless, `SIGALRM`/duvar-saati bütçeleri, kota-günü muhasebesi, Python orkestrasyonu.

**Dosyalar & satırlar.** `scripts/daily_ops_orchestrator.py` (**2.358**), `.github/workflows/daily-ops.yml` (148), `scripts/ensure_paper_stock.py` (573), `scripts/upload_to_supabase.py` (774), `apps/expert-annotator/api/pdf.js` (102). **Yalnızca orkestratörde 27 commit.**

---

### 4.7 Referans veri, PDF/çıkış sağlamlaştırması, testler & dokümantasyon — *bunu bir demo değil bir sistem yapan katman*

**Neden gerekli.** YZ normalleştiricisi ve otomatik tamamlama, bilinen gıdalar ve besinler için **kararlı ID'lere** muhtaçtır yoksa her makale denetimsiz string'ler üretirdi; tehlikeli mantık testlere muhtaçtır çünkü burada bir hata sessizce bir veritabanını bozar ya da kota yakar; ve altı aylık bir proje dokümantasyona muhtaçtır yoksa belgelenmemiş kararlar yanlışlıkla geri alınır.

**Nasıl yaptım.**
- **Referans-veri ETL'i** — iki idempotent yükleyici (`etl_usda_to_opennutri.py`, `etl_sr_legacy_to_opennutri.py`) USDA FoodData Central CSV'lerini Supabase REST API üzerinden kanonik `entities` / `entity_aliases` / `master_nutrients` / `sources` / `claims` katmanına akıtır. **Hazırlık durumunu gıda açıklama metninden türetir**, **bir çakışma sütununda upsert yapar** (yeniden çalıştırma mükerrer değil günceller) ve **deterministik UUID'ler** kullanır (aynı kaynak satırı her zaman aynı `entities.id`'ye eşlenir) — her foreign key'in işaret ettiği referans ID'lerini kararlı tutar.
- **Tehlikeli koda ağırlık veren bir test paketi** — **128 Python test fonksiyonu + 35 frontend bloğu, ~5.617 satır**, sessizce veri bozabilecek veya kota yakabilecek şeyde yoğunlaşmış: `test_ai_routing.py` (60 test, 2.469 satır — normalleştirme determinizmi, birim politikası, ID-çözümleme güvenliği, eşik yönlendirme, **deterministik denetim örneklemesi**, yeniden-deneme sınıflandırması, "model asla kendi üzerinde eğitilmez"), `test_bilingual_pipeline.py` (32, 1.120), `test_daily_ops.py` (30, 983), `test_pdf_page_markers.py`. Test adları, değişmezlerin bir spesifikasyonu gibi okunur — örn. `rejects_stale_or_mismatched_db_ids`, `threshold_one_disables_ai_auto_finalization`, `build_labels_excludes_ai_model_outcomes`.
- **Operasyonel altyapı olarak dokümantasyon** — README, AGENTS kuralları, inceleyici-iş-akışı haritası ve canlı bir devir STATE belgesi, *neden* Gemma metin-modu olduğunu, *neden* sert-negatif tarayıcı vetosuna izin verilmediğini, *neden* PDF'lerin varsayılan olarak kaynak-URL olduğunu, *neden* kokpit YZ listelerinin çıkış-açısından ince kalması gerektiğini ve *neden* nihai gerçeğin onay sonuçlarından geldiğini yakalar — böylece gelecekteki katkıcılar (ve YZ ajanları) yük taşıyan kararları yeniden türetmez veya geri almaz.

Burada **dürüst bir soy ağacı** da var: mevcut crawler-v2 + kademe, repodaki *ikinci* tam hat mimarisidir. Daha eski v1 hasatçısı (`pipeline.py`, `harvester/`, `core/` ve `extraction/` paketleri, ~2.800 satır) silinmedi, tutuldu — yayımlandı ve çalıştı ve daha iyi fikirleri ileri taşındı. Onu tutmak repo boyutuna mal olur; takas, sistemin nasıl evrildiğine dair denetlenebilir bir kayıttır.

**Zor kısım.** Çoğunlukla disiplin — ETL'i yeniden-çalıştırmanın asla bir gıdayı mükerrer yapmayacağı şekilde idempotent kılmak, testleri her yerde kapsama kovalamak yerine bir hatanın felaket olduğu birkaç yüz satıra ağırlık vermek ve dokümantasyonu, yanıltmak yerine gerçekten regresyonları önleyecek kadar doğru tutmak.

**Teknolojiler.** Supabase REST üzerinde Python ETL, deterministik UUID'ler, idempotent upsert'ler, `pytest`, Markdown + DOCX/PDF dışa aktarma araçları.

**Dosyalar & satırlar.** `etl_usda_to_opennutri.py` (227), `etl_sr_legacy_to_opennutri.py` (343), test paketi (~5.617 satır), README / AGENTS / STATE / iş-akışı-haritası dokümanları, artı tutulan v1 hattı (~2.800 satır).

---

## 5. Bitiş özeti

OpenNutri'nin **tüm backend'ini** kurdum — "tüm bilimsel literatürü" "güvenilir, kanıt-konumlu, atıf-destekli aday değerlerden oluşan temiz bir kuyruğa" çeviren ve bunu yapmak için kendi kendini çalıştıran sistem. Rakamlarla:

- **216 commit** boyunca **~31.800 satır** backend / ops / şema kodu; tek başına veritabanı sözleşmesi **5.396 satırdır** (31 tablo, 75 RLS politikası, 26 RPC) ve tehlikeli mantık **~5.600 satır testle** sabitlenmiştir.
- Günde ~1.500 makaleyi eleyen ve ~20 pahalı çıkarımını en iyilerine harcayan bir **üç-modelli kademe**; çıktısı bir insan gönderisiyle **birebir aynı hash'lenen** bir **deterministik normalleştirici**; ve güvenilir sonuçları otomatik tutan, belirsizleri bir insana yönlendiren ve güvenli olanların bile örneklenen bir kesrini kalite kontrolü olarak incelemeye geri zorlayan bir **güven kapısı**.
- Yayıncı bot-duvarlarını gerçek bir proof-of-work çözücüyle yenen bir **tarayıcı**, her insan kararından asla kendi üzerinde eğitilmeden öğrenen bir **geri besleme döngüsü** ve bunların hepsini 5 dakikalık bir GitHub Actions cron'unda, Supabase ve Gemini ücretsiz katmanları içinde, tek bir `FOR UPDATE SKIP LOCKED` ile koordine edilen beş paralel işçiyle çalıştıran bir **otomasyon katmanı**.

Ve bu bir prototip değil. **Canlı**: **altı ay boyunca üretimde işletilmiş, migrate edilmiş ve kurtarılmış** sürekli bir hat; bozuk bir politikanın veri sızdıracağı, takılan bir işçinin her şeyi durduracağı ve yanlış bir otomatik-kabulün bir gıda veritabanını bozacağı en-az-ayrıcalıklı bir güvenlik modeli altında — bu yüzden bunların her biri olmayacak şekilde tasarlanmak zorundaydı.

Dünyadaki her gıda veritabanı hâlâ uzmanların sayıları makalelerden elle yazmasıyla kuruluyor. **Benim backend'im, makaleleri bulan, onları okuyan, neyin güvenilir olduğuna karar veren ve yalnızca geri kalanını bir insana saklayan makine — her gün çalışacak kadar ucuz ve bir besin etiketinde güvenilecek kadar dürüst.** OpenNutri'nin, manuel derlemenin asla yapamadığını ölçekte yapmasını sağlayan budur.

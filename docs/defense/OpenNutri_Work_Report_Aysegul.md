# OpenNutri — Çalışma Raporu: Ayşegül Doğan (221229031)

*Annotator ön yüz (frontend) çalışmalarının, gerçek kaynak kodu okunarak hazırlanmış, kendi içinde bütün ve koda dayalı açıklaması. Ana rapora eşlik eder; sayılar 2026-06-05 tarihinde, `ac8bf72` HEAD'i üzerinden git geçmişinden yeniden türetilmiştir.*

## Bir bakışta

- **Alan:** annotator ön yüzünün tamamı — `apps/expert-annotator/src/**` (React 19 + Vite, Vercel üzerinde yayında).
- Bugün üretimde **~13.500 satır** ön yüz kodu çalışmaktadır; proje boyunca **+22.681 / −7.581** satırlık ön yüz değişimi (net **+15.100**).
- **Yalnızca PDF görüntüleyici + metin tarayıcı: 27 commit** — ön yüzün tek başına en zor alanı ve projenin en zorlu kullanıcı-arayüzü problemini içerir.
- **Atıf kuralı:** Ayşegül, ilk MVP'yi ve çekirdek ön yüzü kendi `ayseguldogan2706-cpu` kimliği altında yazdı; uygulamayı `apps/expert-annotator/` altına taşıyan Mart yeniden düzenlemesinden sonra ön yüz gelişiminin büyük kısmı ekibin ortak entegrasyon makinesi üzerinden commit'lendi. Ekibin yerleşik iş bölümüne göre **ön yüz alanındaki çalışma Ayşegül'e aittir**. Huan'a ait ~450 satırlık ön yüz (bulanık eşleştirme, şifre sıfırlama, öneri ekleri) hariç tutulmuştur ve Huan'ın raporunda ele alınır.

Aşağıdaki iki bölüm, gerçek uygulama kodu okunarak yazılmıştır.

---
## PDF vurgulama motoru — tablo tespiti + kanıt katmanları *(Ayşegül / ön yüz)*

**Bu bölüm için okunan dosyalar:** `utils/PdfTextScanner.js` (2.323 satır — geometri motoru), `components/PdfViewer.jsx` (939), `utils/EvidenceLocations.js` (439). Görüntüleyici + tarayıcıya **27 commit**. Bu, projedeki en zor ön yüz kodudur: PDF.js metin katmanı üzerinde **tarayıcıda belge düzeni analizi (document layout analysis)** yapar.

### Çekirdek problem (kesin ifadeyle)
Bir PDF'in "tablo", "sütun" veya "paragraf" kavramı yoktur. PDF.js size yalnızca konumlandırılmış metin parçaları listesi verir — `{str, x, y, width, height}` — başka hiçbir şey. (a) Tıklama hedefi olarak yalnızca *tablolar içindeki* besin adlarını vurgulamak ve (b) bir yapay zekâ değerinin geldiği tam tablo/paragrafın üzerine katman boyamak için, tarayıcının **sayfa yapısını glif geometrisinden yeniden kurması** gerekir. `PdfTextScanner.js`, tam olarak bunu yapan ~70 fonksiyonluk hesaplamalı geometridir.

### Boru hattı (`buildPageEvidenceHighlightPlan`)
Her sayfa için: `extractPositionedTextItems → buildPageMetrics → detectColumnGutters → groupItemsIntoRows(oluk-duyarlı) → buildTableRegionsAndCaptionFallbacks → buildParagraphBlocks`, ardından her yapay zekâ kanıt konumu için bir **öncelikli eşleştirici dizisi**.

### Zor problem 1 — sihirli sayılar değil, uyarlanabilir metrikler (`buildPageMetrics`)
Her eşik, sayfanın kendi tipografisinden türetilir: `medianHeight` (glif boyutu) ve `medianRowGap`, şu değerleri besler: `rowTolerance`, `fragmentGapThreshold`, `captionMergeGap`, `bodyGapThreshold`, `paragraphGapThreshold`, `bandMargin` — her biri makul bir aralığa `clamp()`'lenir. Böylece aynı kod, sabit piksel sabitleri olmadan hem 7pt yoğun bir tabloda hem de 12pt bir özette çalışır.

### Zor problem 2 — projeksiyon profiliyle sütun tespiti (`detectColumnGutters`)
Çok sütunlu dergi sayfaları en büyük sorundu (komşu sütunların tek bir "paragraf"a kaynaşması). Çözüm, elle uygulanan klasik bir **dikey projeksiyon profilidir**:
- X eksenini **2pt çözünürlükte** bölmelere ayır; her bölme için hangi **y-bantlarında** (satırlarda) içerik olduğunu kaydet.
- **Oluk (gutter)**, neredeyse hiçbir y-bandında içerik olmayan (`≤ %8`), en az **6pt genişliğinde** bir bölme dizisidir.
- Kritik olarak, yalnızca **her iki tarafında da önemli içerik bulunan** olukları tut — gerçek bir sütunlar-arası oluğu sayfanın sol/sağ kenar boşluğundan ayıran şey budur.
Satırlar daha sonra oluklar *içinde* gruplanır (`groupItemsIntoRows(items, metrics, gutters)`), böylece aynı y'deki sol-sütun ve sağ-sütun satırları asla kaynaşmaz.

### Zor problem 3 — sağlam (robust) sütun kırpma (`clipEntriesToDominantColumn`)
Oluklarla bile, PDF.js bazen iki sütunu tek bir geniş parçaya kaynaştırır. Kırpıcı, bir bloğun parçalarının **medyan** sol/sağ kenarını ve bir **medyan mutlak sapma (MAD)** yayılımını hesaplar, sonra aykırı değerleri `3×MAD` sınırında budar (paragraf son satırları meşru biçimde kısa olduğundan alt-sağ sınırı asimetrik ve daha gevşektir). Kod yorumları MAD'in IQR'ye tercih edilmesini açıkça gerekçelendirir: "IQR aykırı değeri q3 içine emerdi." Bu, düzene uygulanan ders kitabı niteliğinde sağlam istatistiktir — tek bir kaynaşmış-sütun parçası, bölge sınırlarını oluğun karşısına sürükleyemez.

### Zor problem 4 — yalan söyleyen `page_hint` (`buildPageEvidenceHighlightPlan` içinde)
Yapay zekâ `page_hint`'i çıkarılmış metinden bildirir; bu yüzden bir dergi ön baskısında *basılı* sayfayı verir (5 sayfalık bir dosyada 1217 gibi). Eşleştirici düzeltmeyi doğrudan kodlar:
```js
const hintExceedsPages = location.pageHint && numPages && location.pageHint > numPages
```
İpucu PDF'in sayfa sayısını aştığında, bir sayfa dizini **olamaz**, dolayısıyla **belirleyici olmayan (non-gating)** hâle getirilir — tablo-altyazı ve kaynak-alıntı geri-düşüşlerinin kanıtı *herhangi bir sayfadaki metinden* bulmasına izin verilir, var olmayan bir sayfaya kilitli kalmak yerine. İpucu geçerliyse bir gezinme ipucu olarak kullanılır; üstbilgi/altbilgide tespit edilen basılı sayfa numaraları (`detectPrintedPageNumber`) bir `mapped_page_hint` üretir, böylece "Page 95" doğru PDF sayfasına kaydırır.

### Zor problem 5 — eşleştirici dizisi + özetin kazanmasını engellemek
Her kanıt konumu sıralı eşleştiricilerden geçer: **tablo-bölgesi** ("Tablo N" atıfı varsa) → **yalnızca-altyazı geri-düşüşü** (tablo atıflı ama gövde güvenle tespit edilememiş) → **kaynak-alıntı metin eşleşmesi** (birebir alıntı bir paragraf/tablo bloğunda bulunur) → **yalnızca-sayfa-ipucu** (HINTED, katman yok). Buradaki iki ince koruma:
- `allowParagraphFallback`: bir kaynak "Tablo 3" diye atıf yaptığında, paragraf-alıntı geri-düşüşü **ipucu sayfası olmayan sayfalarda engellenir**, böylece 1. sayfadaki giriş (Tablo 3'ün sayılarını çoğu zaman tekrarlayan) MATCHED yuvasını çalıp çipi yanlış sayfaya sürükleyemez.
- Altyazı geri-düşüşü de aynı şekilde ipucu sayfasına (veya `hintExceedsPages` durumuna) kilitlenir, böylece kaynakça listesindeki başıboş bir "Tablo 3" eşleşmeyi kazanamaz.

### Zor problem 6 — PDF boşluk gürültüsüne rağmen birebir alıntı eşleştirme (`normalizeSearchText`)
Yapay zekânın `source_quote`'u, çoğu zaman boşluk içermeyen ("10.80g/100 g") PDF metniyle eşleştirilmelidir. Normalleştirici, **rakam↔harf sınırlarına** (Unicode duyarlı `\p{L}`/`\p{N}`) hem alıntıda hem sayfa metninde boşluk ekler; böylece PDF'in boşluk tuhaflıklarından bağımsız olarak hizalanırlar, sonra noktalama tek boşluğa indirgenir.

### Zor problem 7 — kararlı katmanlar + yinelenen çip yok
- **Titreme önleme:** `buildStableRegionKey`, bir bölgeyi varsa kararlı bir `regionId` ile, yoksa yuvarlanmış sınırlarla (`buildRegionBoundsKey`, 0,1pt hassasiyet) anahtarlar — böylece bir katman, yeniden çizimler arasında yeni bir kimlik (ve görünür sıçrama) almaz.
- **Yineleme giderme:** `unifyOverlappingParagraphMatches`, bir sayfanın paragraf eşleşmeleri üzerinde **birleşme-bulma (union-find)** çalıştırır — yatayda önemli örtüşmesi ve küçük dikey boşluğu olan herhangi iki eşleşme tek bir `regionKey`'e ve birleşik sınırlara indirgenir; böylece aynı paragrafa düşen üç yapay zekâ alıntısı üç değil **tek** bir katman ve **tek** bir kenar-çubuğu çipi olarak görünür.

### Tabloyla sınırlı besin vurgulaması (`buildPageTableHighlightPlan`)
Aynı geometrinin diğer tüketicisi: tespit edilen tablo gövdesi/başlık hücrelerine ve altyazı satırlarına ait öğe indekslerinden **sayfaya özel bir izin listesi (allowlist)** oluşturur ve yalnızca orada `renderTextItemWithNutrientHighlights` tıklanabilir besin işaretlerini enjekte eder (react-pdf'in `customTextRenderer`'ı aracılığıyla). Bir sayfada güvenilir tablo çapası yoksa, vurgulama sayfa geneli prozaik eşleştirmeye geri düşmek yerine **bastırılır** — kapsam yerine kesinlik, böylece bir paragraftaki besin kelimesi asla başıboş bir tıklama hedefine dönüşmez.

### `PdfViewer.jsx` (939 satır)
react-pdf gösterimi, sürekli kaydırma, yakınlaştırma, **kendi barındırdığımız PDF.js worker'ı**, tarayıcının PDF-koordinat sınırlarını oluşturulan sayfa sahnesine ölçeklemesi, her eşleşen katmanı (tıklanmış olsun olmasın) boyaması ve kanıt-sayfası-önce davranışı (önce kanıt sayfalarını oluştur, ilkini otomatik aç/vurgula) buna aittir. `EvidenceLocations.js` (439), tarayıcıyı besleyen yinelemesiz kaynak listesini ve koordinat yardımcılarını oluşturur.

### Ödünleşimler
- **Kapsam yerine kesinlik:** tahmin etmek yerine bastır; çok-öğeye-kaynaşmış tablo hücreleri bilinen bir takip işidir.
- **Tüm geometri istemci tarafında:** sunucu gidiş-dönüşü yok ve herhangi bir açık erişim PDF'inde çalışır; bedeli tarayıcıda çalışan ~2.300 satır düzen kodudur.
- **Sezgisel eşikler:** uyarlanabilir ve sınırlandırılmış olsalar da hâlâ sezgiseldirler — gerçek dergi PDF'lerine karşı 27 commit'lik iyileştirme boyunca ayarlanmıştır.
## Annotator uygulaması — iş akışı orkestrasyonu, otomatik tamamlama, kokpit *(Ayşegül / ön yüz)*

**Bu bölüm için okunan dosyalar:** `pages/Annotate.jsx` (1.163 satır), `utils/annotateHelpers.js` (574), `components/FoodAutocomplete.jsx` (664), `components/NutrientAutocomplete.jsx` (334) ve `src/views/*.jsx` altındaki sekiz görünüm.

### `Annotate.jsx` — 1.163 satırlık orkestratör
Tüm veri çekme, üst çubuk, görünüm yönlendirme ve etiketleme eylemleri buna aittir. Tasarımı, ücretsiz katman veri çıkışı (egress) kısıtını arka uç kadar yansıtır:
- **Tembel kokpit yükleme:** `refreshQueue`, `refreshCockpit`, `refreshPipeline`, `refreshMySuggestions` ayrı `useCallback`'lerdir; ağır kokpit/pipeline verisi yalnızca o sekme açıldığında çekilir.
- **Tek-RPC kuyruk:** kuyruk, üç ayrı çağrı yerine tek bir `get_general_queue_cards` çağrısıyla yüklenir (yalın kart alanları + en son yapay zekâ yükü + bu kullanıcının anotasyon durumu, tek gidiş-dönüşte).
- **Yapay zekâ ön-doldurma doğrulaması (`loadAnnotation`):** kaydedilmiş taslağı olmayan bir kuyruk makalesi, en son `normalized_payload_json` yüklenip `buildFoodItemsFromPayload` ile **düzenlenebilir yiyecek/besin satırlarına** dönüştürülerek açılır. Asıl dikkat gerektiren kısım koruma mantığıdır — mevcut bir taslak veya gönderim **asla** üzerine yazılmaz ve ön-doldurma sessizdir (yapay zekâ gerekçesi yok, başlık yok).
- **Etiketleme eylemleri:** `saveAnnotationRows`/`saveAnnotation` (taslak/gönder/veri-yok), `submitHelpRequest` (`buildGeneralHelpContext` ile bir kokpit yardım öğesi oluşturur), `saveReviewerDraft`, `saveSuggestionReview`, `handlePdfNutrientAdd` (PDF tıklamasından yeni besin satırına köprü) ve yazmaları DB yerine yerel depolamaya yönlendiren bir **test-modu değiştirici**.

### `annotateHelpers.js` — arka uç mantığının ön yüz aynası
Orkestratörü ince tutmak için ayıklanmış 574 satır saf yardımcı. En önemli iki parça:
- **Yük normalizasyonu** (`normalizeFoodItem`, `normalizeMetadata`, `normalizeOptionalNumber/Integer`, `buildFoodItemsFromPayload`, `isValidFoodItem`) — SQL `build_annotation_submission_payload`'ın ve Python normalleştiricisinin istemci tarafı karşılığı. Üç tarafta da aynı şekil, yapay zekâ çıktısını, insan taslaklarını ve depolanmış gerçeği değiştirilebilir kılan şeydir.
- **Pipeline hunisi** (`MODEL_STAGE_DEFINITIONS`, `formatModelSpecification`, `getModelStageRoleLabel`, `buildPipelineSteps`) — kokpit hunisini **rol-kararlı etiketlerle** (`Small model (Gemma 31B)`, `Medium model`, `Strong model`) çizer; böylece gelecekteki bir model değişimi yalnızca parantez içindeki spesifikasyonu değiştirir. Ayrıca tarihsel Small→Strong makalelerinin orta aşamayı sıfırdan başlatmaması için Medium-aşama dolgusu. `getAiPrefillStats`, `getNormalizationSummary` ve `countCorrectionItems` (`correction_diff_json`'u insan-okunur bir sayıma dönüştürür) da burada.

### `FoodAutocomplete.jsx` — alana özel ayarlanmış yiyecek arama sıralayıcısı
664 satır gerçek bilgi erişimi (information retrieval), çünkü yiyecek adları karışıktır ("apple" yazınca *Apple juice, canned* değil *Apple, raw, with skin* yüzeye çıkmalı). `scoreFoodMatch`, kanonik ad, ayıklanmış bir temel ad ve takma adlar üzerinde ağırlıklı bir sıralayıcıdır:
- **Tam** kanonik/temel/takma ad = +2000 / +1700 / +1600; **önek** = +900 / +1200 / +800; ilk-token = +180 / +260 / +180.
- **Token-ilişkisi bazlı puanlama**, üç ilişkiyle — `exact` / `derived` (çekim/kök) / `fuzzy` (`buildDeletionVariants` üzerinden düzenleme mesafesi) — her biri farklı ağırlıkta ve tek-kelimelik "genel" sorgular için yükseltilmiş.
- **Kapsam + konum:** her sorgu token'ı eşleşirse +260, eşleşmeyen token başına −180, en erken eşleşme konumu × −35 (erken olan daha iyi), kısa temel adları tercih etmek için uzunluk cezaları.
- **Bütün-yiyecek ayrımı:** genel sorgular için fazladan `PROCESSING_WORDS` (canned/dried/…, her biri −55) ve `derivedPrefix` yanlış-eşleşmeleri (−140) cezalandırılır, `WHOLE_FOOD_HINTS` ve temel-ad eşleşmeleri (+220) ödüllendirilir — böylece çiğ bütün yiyecek, işlenmiş varyantların üzerine sıralanır.
- Destekleyici dil işleme: `IRREGULAR_TOKEN_MAP`'li (düzensiz çoğullar) `normalizeToken`, `STOPWORDS`, `NOISY_PREFIXES`, çekim/türev/önek token ilişkileri ve genel bir sorgunun yararlı token örtüşmesi olmadığında sert ret (−9999).
Sonuçlar yinelemesizleştirilir, filtrelenir, sıralanır ve 15'le sınırlanır. `NutrientAutocomplete.jsx` (334) aynı yaklaşımı besinlere uygular ve ikisi de çözümlemeyi analiz için `search_sessions`'a kaydeder. Huan'ın `fuzzyMatch.js`'i buradaki bulanık-terim katmanına bağlanır.

### Sekiz görünüm (`src/views/*.jsx`)
Eski yekpare `Annotate.jsx`'ten ayıklanmıştır: `QueueView` (etiketleyici yüzeyi), `ApprovalView` (düzeltme farkıyla onaylayan düzenle-ve-kabul-et), `DashboardView`, `AllPapersView` (Faydalı Makaleler, yapay zekâ ayrıntıları), `PipelineOpsView` (huni), `SuggestionsReviewView` + `MySuggestionsView` (Huan'ın öneri triyajı/takibi), `ReviewerAdminView` (gözden geçiren yapılandırması). Her biri orkestratör tarafından beslenen odaklı bir sunum bileşenidir.

### Ödünleşimler
- **Sezgisel, ağırlık-ayarlı sıralama:** yiyecek sıralayıcısı öğrenilmiş bir model değil, ayarlanmış sabitler yığınıdır — hızlı, ayıklanabilir ve bu katalog boyutunda yeterince iyi, ama elle bakımlı.
- **Veri-çıkışı odaklı arayüz mimarisi:** tembel sekmeler + tek-RPC kuyruk + yalın kokpit projeksiyonları, Supabase ücretsiz katmanı içinde kalmak için eşgüdüm karmaşıklığı ekler.
- **Üç-kat kodlanmış yük şekli** (JS + SQL + Python): yinelenen normalizasyon, üç gerçek üreticisinin karşılaştırılabilir kalması için aynı hizada tutulur.

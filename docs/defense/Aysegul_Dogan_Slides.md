# OpenNutri — Ayşegül Doğan — Defense Presentation (slide-ready)

> **What this document is.** A slide-by-slide script for Ayşegül Doğan's individual defense presentation. It is *not* the long written report — the text here is deliberately lighter: only the **main ideas** plus the **details worth saying out loud** to show how hard and how well-built the work is. Each slide is given **twice**: first **English (Slide N)**, then **Turkish (Slayt N)** — build the deck in whichever language you present in; the other is there for cross-reference.
>
> **How to read it.**
> - Bullets = roughly what goes on the slide. Keep them short on the real slide; expand them out loud.
> - `🖼️ IMAGE` = a placeholder telling you exactly what screenshot or diagram to put there, and what to point at. This is a UI project, so almost every slide has one — capture them from the live app on Vercel.
> - Nothing here is a hidden "notes" track. The numbers, the technique names, and the "why not the easy way" lines are written *into* the slide content on purpose: they read as normal slide text, and they also happen to be exactly what you'll want in your head if a teacher asks a follow-up.
>
> **Team split (say this once, on Slide 2).** OpenNutri was built by three people: **Ayşegül Doğan** — the entire annotator frontend (this talk); **Arciel Baez** — the entire backend (database, the AI cascade, the crawler, ops); **Duc Huan Ngo** — reusable pieces (the `fuzzyMatch` primitive, suggestions/attachments, the reset-password fix, theme centralization, infinite scroll). Honest attribution is kept on the slides where it matters — it makes the rest of the claim stronger, not weaker.

---
---

# ENGLISH + TÜRKÇE — SLIDES

---

## Slide 0 — Title

> 🖼️ **IMAGE — hero shot:** the live annotation workspace, full-bleed: PDF on the left with one table highlighted, the food/nutrient editor on the right. Dim it slightly and put the title over it. (This single image previews the whole talk.)
> *Caption:* "OpenNutri Annotator — live on Vercel"

- **OpenNutri — The Expert-Verification Frontend**
- Ayşegül Doğan
- *"I built the entire annotator — the app where the AI's raw guesses become trustworthy food-composition data."*

---

## Slayt 0 — Başlık

> 🖼️ **GÖRSEL:** Slide 0'daki görselin aynısı (canlı çalışma alanı, başlık üstte).
> *Altyazı:* "OpenNutri Annotator — Vercel'de canlı"

- **OpenNutri — Uzman-Doğrulama Frontend'i**
- Ayşegül Doğan
- *"Etiketleyici uygulamanın tamamını ben kurdum — yapay zekânın ham tahminlerinin güvenilir besin verisine dönüştüğü yer."*

---
---

## Slide 1 — The problem: food data is still built by hand

> 🖼️ **IMAGE — split illustration:** left, a real dense journal PDF table full of numbers; right, a sparse database/spreadsheet. A big arrow between them labelled "typed in by hand, one number at a time." Optionally a small "🐌 slow · 💸 expensive" tag under the arrow.
> *Caption:* "The data exists. Reading it out by hand doesn't scale."

- Every nutrition label, diet app and dietary guideline runs on **food-composition data** — protein, fat, iron, vitamin C…
- Today that data is built **by hand**: an expert reads a paper, finds the right table, types each number into a database — one at a time.
- Slow and expensive → databases stay **narrow** and quickly go **out of date**.
- The data already exists — it's **published constantly** — but it's locked inside unstructured PDFs.
- And you can't just let an AI read it unchecked: **too many wrong numbers** to trust on a food label.

---

## Slayt 1 — Problem: besin verisi hâlâ elle kuruluyor

> 🖼️ **GÖRSEL:** Slide 1'deki görselin aynısı (yoğun PDF tablosu → seyrek veritabanı, "elle, tek tek yazılıyor" oku).
> *Altyazı:* "Veri zaten var. Onu elle çıkarmak ölçeklenmiyor."

- Her besin etiketi, diyet uygulaması ve beslenme kılavuzu **besin bileşim verisine** dayanır — protein, yağ, demir, C vitamini…
- Bu veri bugün **elle** kurulur: uzman makaleyi okur, doğru tabloyu bulur, her sayıyı tek tek veritabanına yazar.
- Yavaş ve pahalı → veritabanları **dar** kalır ve hızla **eskir**.
- Veri zaten mevcut — **sürekli yayımlanıyor** — ama yapısız PDF'lerin içinde kilitli.
- Ve bir yapay zekâya denetimsiz okutamazsınız: bir etikette güvenilemeyecek kadar **çok yanlış sayı** üretir.

---
---

## Slide 2 — How we solved it (as a team)

> 🖼️ **IMAGE — architecture diagram:** three boxes left→right: **[Backend pipeline]** → **[Database]** → **[Annotator frontend]**. Highlight the third box ("MINE"). Draw a branch on the AI box labelled "low-confidence papers → human"; let confident ones flow straight to the DB.
> *Caption:* "AI proposes the numbers. A human verifies the ones it's unsure about."

- We flipped the work: **the AI reads the paper and proposes the numbers; a person verifies the ones the AI is unsure about** (the low-confidence papers).
- Three parts:
  - **Backend pipeline** (Arciel) — finds papers, downloads PDFs, runs the AI cascade → *candidate* values.
  - **Database** (Arciel) — stores everything, runs the review workflow.
  - **Annotator web app** (me) — where a human checks and corrects those candidates.
- **My part is the annotator — the rest of this talk is about it.**

---

## Slayt 2 — Bunu (ekip olarak) nasıl çözdük

> 🖼️ **GÖRSEL:** Slide 2'deki mimari şema (Backend → Veritabanı → **Frontend (BENİM)**; "düşük güven → insan" dalı).
> *Altyazı:* "Yapay zekâ sayıları önerir. İnsan, emin olmadıklarını doğrular."

- İşi tersine çevirdik: **yapay zekâ makaleyi okuyup sayıları önerir; insan, yapay zekânın emin olmadıklarını doğrular** (düşük güvenli makaleleri).
- Üç parça:
  - **Backend hattı** (Arciel) — makaleleri bulur, PDF'leri indirir, YZ kademesini çalıştırır → *aday* değerler.
  - **Veritabanı** (Arciel) — her şeyi saklar, inceleme iş akışını yürütür.
  - **Etiketleyici web uygulaması** (ben) — insanın bu adayları kontrol edip düzelttiği yer.
- **Benim parçam etiketleyici — bu sunumun geri kalanı bununla ilgili.**

---
---

## Slide 3 — My part, and why it's necessary

> 🖼️ **IMAGE — the workspace, annotated:** real screenshot, PDF (left) with a highlighted table, editor (right) with food/nutrient rows. Draw an arrow from a highlighted PDF cell to the matching row in the editor. Caption the arrow "evidence → value."
> *Caption:* "The unit of work changes from *transcribe* to *verify*."

- My part is the **entire annotator frontend** — a **React 19 + Vite** app, deployed on **Vercel**, running **entirely in the browser**.
- It changes the unit of work from **transcribing a paper → verifying a draft**.
- The paper opens **pre-filled** with the AI's values, and — the core idea — **the exact table or sentence each value came from lights up on the PDF**, with the nutrient names in it **clickable**.
- So the verifier's eye goes **straight to the evidence and confirms**, instead of hunting through the paper.
- Every correction is **fed back to improve the AI** over time.

---

## Slayt 3 — Benim parçam ve neden gerekli

> 🖼️ **GÖRSEL:** Slide 3'teki açıklamalı çalışma alanı (vurgulu PDF hücresinden editördeki satıra ok: "kanıt → değer").
> *Altyazı:* "İşin birimi *kopyalamak*tan *doğrulamak*a değişir."

- Benim parçam, **etiketleyici frontend'inin tamamı** — **React 19 + Vite** uygulaması, **Vercel'de** yayında, **tamamen tarayıcıda** çalışır.
- İşin birimini **makale kopyalamaktan → taslak doğrulamaya** çevirir.
- Makale, yapay zekânın değerleriyle **önceden doldurulmuş** açılır ve — işin özü — **her değerin geldiği tam tablo veya cümle PDF üzerinde aydınlanır**, içindeki besin adları **tıklanabilirdir**.
- Böylece doğrulayıcının gözü, makalede aramak yerine **doğrudan kanıta gidip onaylar**.
- Her düzeltme, zamanla **yapay zekâyı iyileştirmek için geri beslenir**.

---
---

## Slide 4 — What I built: seven pieces

> 🖼️ **IMAGE — "map" slide:** seven labelled tiles (a 7-up grid or a numbered roadmap). Optionally a faint thumbnail of the relevant screen behind each tile. This doubles as the agenda for the rest of the talk.
> *Caption:* "Everything below runs client-side, on arbitrary publisher PDFs, fast enough to do all day."

1. **Annotation workspace & orchestrator** — the screen that ties everything together.
2. **PDF evidence engine** — *the hardest piece of code in the whole project.*
3. **Durable caching layers** — what makes PDFs and highlights instant and shareable.
4. **Domain-tuned autocomplete** — forgiving food/nutrient search → the catalog.
5. **Clickable PDF → editor bridge** — a click on the page becomes a data row.
6. **Cockpit & workflow views** — approval, dashboards, useful-papers, pipeline funnel.
7. **App shell, auth & theme** — session, login, OS-aware theming.

---

## Slayt 4 — Yaptıklarım: yedi parça

> 🖼️ **GÖRSEL:** Slide 4'teki "harita" slaytı (yedi etiketli kutu; sunumun geri kalanının ajandası).
> *Altyazı:* "Aşağıdakilerin hepsi tarayıcıda, keyfi yayıncı PDF'leri üzerinde, bütün gün çalışacak kadar hızlı işler."

1. **Etiketleme çalışma alanı & orkestratör** — her şeyi bağlayan ekran.
2. **PDF kanıt motoru** — *tüm projedeki en zor kod parçası.*
3. **Kalıcı önbellek katmanları** — PDF'leri ve vurguları anlık ve paylaşılabilir yapan şey.
4. **Alana özel otomatik tamamlama** — bağışlayıcı gıda/besin araması → katalog.
5. **Tıklanabilir PDF → editör köprüsü** — sayfadaki tıklama bir veri satırına döner.
6. **Kokpit & iş akışı görünümleri** — onay, panolar, faydalı-makaleler, hat hunisi.
7. **Uygulama kabuğu, kimlik doğrulama & tema** — oturum, giriş, OS'a duyarlı tema.

---
---

## Slide 5 — 1) The annotation workspace & orchestrator

> 🖼️ **IMAGE — full workspace, annotated:** screenshot of the labeling screen. Call out the toolbar ("Paper 3 / 12", Prev / Next, status badges), the action row at the bottom (**Ask for Help · No Usable Data · Save Draft · Submit Reviewed Data**), and add a callout box: "≈ 30 React state values orchestrated in one file."
> *Caption:* "`Annotate.jsx` — one screen: queue · PDF · editor · submit."

- **One screen ties it all together** — queue, PDF, food/nutrient editor, submit. (`Annotate.jsx`, ~1,160 lines, ~**30 pieces of React state**.)
- **Parallel boot, no waterfall** — the shell paints immediately; queue and reviewer profile load together, not one-after-another.
- **One-RPC queue** — lean cards + the latest AI payload + my status in a **single round-trip**; with a **versioned fallback** so it keeps working across backend versions.
- **AI-prefill never overwrites a human draft** — sounds small, touches every load path.
- **Test-mode aware** — every DB write can append to a local log instead of touching Supabase → the app can be demoed without polluting real data.
- Designed deliberately around the **Supabase free-tier egress budget** (no `select('*')`).

---

## Slayt 5 — 1) Etiketleme çalışma alanı & orkestratör

> 🖼️ **GÖRSEL:** Slide 5'teki açıklamalı çalışma alanı (araç çubuğu, alt eylem satırı, "tek dosyada ≈30 React state" notu).
> *Altyazı:* "`Annotate.jsx` — tek ekran: kuyruk · PDF · editör · gönder."

- **Tek ekran her şeyi bağlar** — kuyruk, PDF, gıda/besin editörü, gönder. (`Annotate.jsx`, ~1.160 satır, ~**30 parça React state**.)
- **Paralel açılış, şelale yok** — kabuk anında boyanır; kuyruk ile inceleyici profili arka arkaya değil, **birlikte** yüklenir.
- **Tek-RPC kuyruğu** — sade kartlar + en son YZ yükü + kullanıcı durumu **tek turda**; backend sürümleri arasında çalışmaya devam etmesi için **sürümlenmiş yedekle**.
- **YZ ön-doldurması bir insan taslağının asla üzerine yazmaz** — küçük görünür, her yükleme yolunu etkiler.
- **Test-modu farkında** — her DB yazımı Supabase'e dokunmak yerine yerel günlüğe eklenebilir → gerçek veriyi kirletmeden demo yapılabilir.
- Bilerek **Supabase ücretsiz-katman çıkış bütçesi** etrafında tasarlandı (`select('*')` yok).

---
---

## Slide 6 — AI prefill: the paper opens already filled in

> 🖼️ **IMAGE:** the editor right-hand panel with rows already populated from the AI, before any human edit. Mark a couple of rows with a small "AI" tag and show the fields are editable.
> *Caption:* "Reviewers correct structured rows — not a blank form."

- No saved draft? The latest AI **normalized payload** becomes **editable food/nutrient rows**.
- A saved human draft? **That** loads instead — human work is never overwritten.
- The payload shape matches the **backend contract exactly** (Python → SQL → JavaScript), so reviewer-correction metrics stay reliable.
- This is one of the project's key UX wins: **correct a draft, don't start from blank.**

---

## Slayt 6 — YZ ön-doldurması: makale dolu açılır

> 🖼️ **GÖRSEL:** Slide 6'daki editör paneli (YZ'den gelen dolu satırlar, "AI" etiketi, düzenlenebilir alanlar).
> *Altyazı:* "İnceleyiciler boş form değil, yapılı satırları düzeltir."

- Kayıtlı taslak yoksa, en son YZ **normalize yükü** **düzenlenebilir gıda/besin satırlarına** dönüşür.
- Kayıtlı bir insan taslağı varsa, **o** yüklenir — insan işi asla üzerine yazılmaz.
- Yük şekli **backend sözleşmesiyle birebir** eşleşir (Python → SQL → JavaScript), böylece düzeltme metrikleri güvenilir kalır.
- Projenin temel UX kazançlarından biri: **taslağı düzelt, sıfırdan başlama.**

---
---

## Slide 7 — 2) PDF evidence engine — the problem

> 🖼️ **IMAGE — before/after illustration:** left, "What PDF.js gives you" = a scatter of little glyph boxes (`{text, x, y, w, h}`), no structure. Right, "What we need" = the same page with a recognized **table region** and a **paragraph block** drawn around the text.
> *Caption:* "PDF.js gives letters and coordinates. There is no table, column, or paragraph."

- This is the **heart of verification**: when the AI says *"protein = 22.04 g/100 g,"* the human must be able to **see that number on the actual page**.
- And to make entry fast, the nutrient names **inside the tables** must be **clickable**.
- But PDF.js hands you only a **flat list of positioned letters** — `{ text, x, y, width, height }`. **No concept of a table, a column, or a paragraph.**
- So I had to **reconstruct the document's structure from pure geometry** — in the browser, **no server, no machine-learning model.**

---

## Slayt 7 — 2) PDF kanıt motoru — problem

> 🖼️ **GÖRSEL:** Slide 7'deki önce/sonra görseli ("PDF.js'in verdiği" dağınık harf kutuları → "ihtiyacımız olan" tablo bölgesi + paragraf bloğu).
> *Altyazı:* "PDF.js harf ve koordinat verir. Tablo, sütun, paragraf kavramı yoktur."

- Bu, **doğrulamanın kalbi**: YZ *"protein = 22,04 g/100 g"* dediğinde, insan o sayıyı **gerçek sayfada görebilmeli**.
- Ve girişi hızlandırmak için, **tabloların içindeki** besin adları **tıklanabilir** olmalı.
- Ama PDF.js size yalnızca **konumlanmış harflerin düz listesini** verir — `{ metin, x, y, genişlik, yükseklik }`. **Tablo, sütun veya paragraf kavramı yok.**
- Bu yüzden **belge yapısını saf geometriden yeniden inşa etmem** gerekti — tarayıcıda, **sunucu yok, makine öğrenmesi modeli yok.**

---
---

## Slide 8 — PDF engine — the reconstruction pipeline

> 🖼️ **IMAGE — pipeline diagram:** a left-to-right chain of labelled stages: *glyphs → adaptive metrics → column detection → row grouping → fragments → classify → caption-anchored table growth → paragraph blocks → matcher cascade.* Make it look like a real processing pipeline.
> *Caption:* "`PdfTextScanner.js` — ~70 functions of computational geometry, 2,323 lines."

- `PdfTextScanner.js` is about **70 functions of computational geometry** (**2,323 lines** — the largest single file in the repo).
- Per page: **glyphs → adaptive metrics → columns → rows → fragments → classify → table growth → paragraphs → matcher cascade** that locates each AI quote.
- **Every threshold derives from the page's own typography** (median glyph height, median row gap) — so the same code works on a dense 7 pt table and a 12 pt abstract, with **no hardcoded pixel values**.

---

## Slayt 8 — PDF motoru — yeniden inşa hattı

> 🖼️ **GÖRSEL:** Slide 8'deki hat şeması (harfler → uyarlanır metrikler → sütun saptama → satır gruplama → parçalar → sınıflandırma → başlık-çapalı tablo büyütme → paragraf blokları → eşleştirici kademesi).
> *Altyazı:* "`PdfTextScanner.js` — ~70 hesaplamalı geometri fonksiyonu, 2.323 satır."

- `PdfTextScanner.js` yaklaşık **70 hesaplamalı geometri fonksiyonudur** (**2.323 satır** — repodaki en büyük tek dosya).
- Sayfa başına: **harfler → uyarlanır metrikler → sütunlar → satırlar → parçalar → sınıflandırma → tablo büyütme → paragraflar → eşleştirici kademesi** (her YZ alıntısını bulur).
- **Her eşik, sayfanın kendi tipografisinden türetilir** (ortanca harf yüksekliği, ortanca satır boşluğu) — aynı kod hem yoğun 7 punto tabloda hem 12 punto özette çalışır, **sabit piksel değeri yok**.

---
---

## Slide 9 — PDF engine — the hard sub-problems (1 / 2)

> 🖼️ **IMAGE — annotated real PDF page:** a multi-column journal page. Outline a **table region** in one colour and a **paragraph block** in another; draw the vertical **gutter line** detected between the two columns.
> *Caption:* "Reconstructing structure that the file never stored."

- **Column detection by projection profile** — bin the x-axis, find vertical "gutters," split rows that cross one → a left-column line and a right-column line at the same height never fuse.
- **Per-fragment table/prose classifier** — a feature vector per text run (numeric tokens, sample codes like "T1", units, caption prefixes…) → an integer **`tableScore`** → `isTableLike`. A small **hand-built text classifier**.
- **Caption-anchored table growth** — find "Table 3 …", grow the region **downward** row by row; once a data row is accepted, later rows stay accepted because **in context** they obviously belong.
- **Paragraph blocks + interleaved-data merging** — re-join a paragraph that a stray numeric line split apart, so a sentence quoting "22.04 ± 1.25 g/100 g" still resolves to one clean highlight.

---

## Slayt 9 — PDF motoru — zor alt-problemler (1 / 2)

> 🖼️ **GÖRSEL:** Slide 9'daki açıklamalı PDF sayfası (tablo bölgesi + paragraf bloğu farklı renkte; iki sütun arası "oluk" çizgisi).
> *Altyazı:* "Dosyanın hiç saklamadığı yapıyı yeniden kurmak."

- **Projeksiyon profiliyle sütun saptama** — x eksenini kutula, dikey "oluk"ları bul, oluğu kesen satırları böl → aynı yükseklikteki sol ve sağ sütun satırları asla kaynaşmaz.
- **Parça başına tablo/düzyazı sınıflandırıcı** — her metin koşusu için özellik vektörü (sayısal token, "T1" gibi kodlar, birimler, başlık önekleri…) → tamsayı **`tableScore`** → `isTableLike`. Küçük, **elle yapılmış bir metin sınıflandırıcı**.
- **Başlık-çapalı tablo büyütme** — "Tablo 3 …" bul, bölgeyi satır satır **aşağı** büyüt; bir veri satırı kabul edilince sonrakiler de kabul edilir çünkü **bağlamda** açıkça oraya aittirler.
- **Paragraf blokları + araya giren-veri birleştirme** — sayısal bir satırın böldüğü paragrafı yeniden birleştir; böylece "22,04 ± 1,25 g/100 g" alıntılayan cümle tek temiz vurguya çözülür.

---
---

## Slide 10 — PDF engine — the hard sub-problems (2 / 2)

> 🖼️ **IMAGE — annotated PDF page:** show **one** merged highlight overlay covering a table, and **one** evidence chip in the strip that represents three different AI rows citing it. Add a tiny inset comparing the printed page number ("p. 1217") with the real PDF page index ("PDF page 3").
> *Caption:* "Precision-first: it would rather highlight nothing than the wrong thing."

- **MAD-robust column clipping** — when PDF.js still fuses two columns, clip using **median + median-absolute-deviation** to fence out outliers without throwing away short last lines.
- **3-tier source-quote matcher** — paragraph → search-fragment → row-window, each with fallbacks; text is normalized at digit↔letter boundaries so "10.80g/100 g" matches "10.80 g/100 g".
- **The lying `page_hint`** — the AI reports the *printed* page (e.g. "1217" on a 5-page offprint). Over-range hints are made **non-gating**, and a **histogram of printed-vs-PDF offsets** remaps the hint to the real page.
- **Union-find (twice)** — collapse overlapping highlight regions into one; a second pass merges different AI rows citing the **same** paragraph → one clean chip, one overlay, **no flicker** between re-renders.

---

## Slayt 10 — PDF motoru — zor alt-problemler (2 / 2)

> 🖼️ **GÖRSEL:** Slide 10'daki açıklamalı PDF sayfası (üç YZ satırını temsil eden tek birleşik vurgu + tek kanıt çipi; "basılı s. 1217" ↔ "PDF sayfa 3" küçük kıyas kutusu).
> *Altyazı:* "Önce-kesinlik: yanlış şeyi vurgulamaktansa hiçbir şeyi vurgulamamayı tercih eder."

- **MAD ile sağlam sütun kırpma** — PDF.js hâlâ iki sütunu kaynaştırdığında, **ortanca + ortanca-mutlak-sapma** ile kırp; kısa son satırları atmadan aykırıları çitler.
- **3 kademeli kaynak-alıntı eşleştirici** — paragraf → arama-parçası → satır-penceresi, her biri yedekli; metin rakam↔harf sınırlarında normalize edilir, "10.80g/100 g" ↔ "10.80 g/100 g".
- **Yalan söyleyen `page_hint`** — YZ *basılı* sayfayı bildirir (5 sayfalık ayrı-baskıda "1217"). Aşan ipuçları **kapı tutmaz** hâle getirilir ve **basılı-vs-PDF kayma histogramı** ipucunu gerçek sayfaya eşler.
- **Union-find (iki kez)** — üst üste binen vurgu bölgelerini tek bölgeye topla; ikinci geçiş **aynı** paragrafa atıf yapan farklı YZ satırlarını birleştirir → tek çip, tek yer paylaşımı, yeniden çizimlerde **titreme yok**.

---
---

## Slide 11 — PDF engine — rendering & clickable evidence

> 🖼️ **IMAGE — annotated viewer:** the PDF panel showing (a) a highlighted evidence region on a table, (b) clickable nutrient names marked inside that table, (c) the evidence strip of chips above. Arrows label each.
> *Caption:* "Tuned across 27 commits on real journal PDFs — the single hardest file in the project, frontend or backend."

- **Self-hosted, bundled PDF.js worker** — no CDN dependency on the critical path.
- **Headless evidence scan** — reads each page's text **without rendering its canvas** (during browser idle) to pre-compute highlights and learn which pages hold evidence.
- **Evidence-first rendering** — page 1 + evidence pages paint first; the rest backfill.
- **Coordinate transform** — scales PDF bounds to screen pixels and **flips the Y-axis**.
- **Custom text renderer** — injects clickable nutrient marks **only inside detected tables** (not random words in prose).
- This whole subsystem is **document layout analysis in a web browser** — `PdfTextScanner.js` (2,323) + `PdfViewer.jsx` (939) + `EvidenceLocations.js` (439) ≈ **3,700 lines**, plus **~970 lines of tests** locking it down.

---

## Slayt 11 — PDF motoru — çizim & tıklanabilir kanıt

> 🖼️ **GÖRSEL:** Slide 11'deki açıklamalı görüntüleyici (vurgulu kanıt bölgesi, tablo içinde tıklanabilir besin adları, üstte kanıt çipleri şeridi).
> *Altyazı:* "Gerçek dergi PDF'lerinde 27 commit boyunca ayarlandı — projedeki tek en zor dosya, frontend ya da backend."

- **Kendi sunucumuzda barındırılan, paketlenmiş PDF.js worker'ı** — kritik yolda CDN bağımlılığı yok.
- **Başsız kanıt taraması** — her sayfanın metnini **tuvalini çizmeden** okur (tarayıcı boştayken); vurguları önceden hesaplar, hangi sayfaların kanıt içerdiğini öğrenir.
- **Kanıt-öncelikli çizim** — sayfa 1 + kanıt sayfaları önce boyanır; gerisi arkadan dolar.
- **Koordinat dönüşümü** — PDF sınırlarını ekran piksellerine ölçekler ve **Y eksenini ters çevirir**.
- **Özel metin çizici** — tıklanabilir besin işaretlerini **yalnızca saptanmış tabloların içine** enjekte eder (düzyazıdaki rastgele kelimelere değil).
- Bu alt-sistemin tamamı **tarayıcıda belge yerleşim analizidir** — `PdfTextScanner.js` (2.323) + `PdfViewer.jsx` (939) + `EvidenceLocations.js` (439) ≈ **3.700 satır**, artı onu kilitleyen **~970 satır test**.

---
---

## Slide 12 — 3) Durable caching layers

> 🖼️ **IMAGE — layered diagram:** three stacked layers — **Cache Storage (PDF bytes)** · **localStorage LRU index (cap 40)** · **Supabase (shared evidence positions)** — with a clock icon and a "re-open = instant" callout. Optionally show a "prefetch next 2 papers" arrow.
> *Caption:* "10–25 MB PDFs, made instant and shared between reviewers."

- These PDFs are **10–25 MB** — and the browser's normal HTTP cache **evicts** files that big, while Supabase serves them **`no-cache`**.
- **PDF bytes → Cache Storage API** (not the volatile HTTP cache), with an **LRU index in localStorage** (cap 40). A **fresh `ArrayBuffer`** is handed to PDF.js each time (it detaches buffers on transfer — a subtle bug to get right).
- **Prefetch the next two queue papers during idle** → "Next" opens instantly.
- **Resolved evidence positions cached per paper, local + remote** (Supabase) → when *anyone* re-opens a reviewed paper, the overlays paint **from cache before the scan even finishes**.

---

## Slayt 12 — 3) Kalıcı önbellek katmanları

> 🖼️ **GÖRSEL:** Slide 12'deki katmanlı şema (Cache Storage baytları · localStorage LRU · Supabase paylaşımlı kanıt; "yeniden açış = anlık" notu).
> *Altyazı:* "10–25 MB PDF'ler anlık ve inceleyiciler arası paylaşımlı hâle getirildi."

- Bu PDF'ler **10–25 MB** — tarayıcının normal HTTP önbelleği bu büyüklüğü **atar**, Supabase ise **`no-cache`** ile sunar.
- **PDF baytları → Cache Storage API** (uçucu HTTP önbelleği değil), **localStorage'da LRU indeks** (üst sınır 40). Her seferinde PDF.js'e **taze `ArrayBuffer`** verilir (aktarımda buffer'ları ayırır — doğru yapılması gereken ince bir hata).
- **Sonraki iki kuyruk makalesini boştayken önceden çek** → "Next" anında açılır.
- **Çözülmüş kanıt konumları makale başına, yerel + uzak** (Supabase) → *herhangi biri* incelenmiş bir makaleyi yeniden açtığında yer paylaşımları **tarama bitmeden önbellekten** boyanır.

---
---

## Slide 13 — 4) Domain-tuned autocomplete

> 🖼️ **IMAGE:** the food autocomplete dropdown after typing "apple", with **"Apple, raw"** ranked first and processed variants ("Apple juice, canned") pushed down. Small inset of the nutrient autocomplete.
> *Caption:* "\"apple\" must surface *Apple, raw* — never *Apple juice, canned*."

- A labeler types free text ("apple", "vitamin c") → it must map to the **canonical USDA catalog entry**, forgivingly (typos, plurals, partial names) but **without unsafe over-matching**.
- A **weighted scoring ranker** (`scoreFoodMatch`) over each entry's canonical name, base name and aliases; per-token exact / stemmed / edit-distance relations.
- **Whole-food disambiguation** — penalizes "canned/dried", baby-food/restaurant and derived-prefix false friends; rewards whole-food hints → generic queries surface the raw food. No useful overlap = hard-rejected.
- **Two-query Supabase strategy** before the catalog loads; **local ranking** after. Debounced 250 ms, full keyboard nav, custom-food entry, logged to a `search_sessions` telemetry table.
- **Honest attribution:** the low-level fuzzy primitive (tokenizer / inflection / Levenshtein) is **Huan's**; the **domain scorer, the whole-food disambiguation, the data-loading strategy and the UX are mine.**

---

## Slayt 13 — 4) Alana özel otomatik tamamlama

> 🖼️ **GÖRSEL:** Slide 13'teki "apple" arama açılır listesi (**"Apple, raw"** en üstte; işlenmiş türevler aşağıda). Besin otomatik tamamlamadan küçük bir kesit.
> *Altyazı:* "\"elma\" *Elma, çiğ*'i öne çıkarmalı — asla *Elma suyu, konserve*'yi değil."

- Etiketleyici serbest metin yazar ("elma", "c vitamini") → bunun **kanonik USDA katalog girdisine** eşlenmesi gerekir; bağışlayıcı (yazım hatası, çoğul, kısmi ad) ama **güvensiz aşırı-eşleşme olmadan**.
- Her girdinin kanonik adı, taban adı ve takma adları üzerinde **ağırlıklı puanlama sıralayıcısı** (`scoreFoodMatch`); token başına tam / kök / düzenleme-mesafesi.
- **Bütün-gıda ayrıştırması** — "konserve/kurutulmuş", bebek-maması/restoran ve türetilmiş-önek sahte dostlarını cezalandırır; bütün-gıda ipuçlarını ödüllendirir → genel sorgular çiğ gıdayı öne çıkarır. Yararlı örtüşme yoksa sert ret.
- Katalog yüklenmeden **iki-sorgulu Supabase stratejisi**; sonrasında **yerel sıralama**. 250 ms geciktirme, tam klavye gezinme, özel-gıda girişi, `search_sessions` telemetri tablosuna kayıt.
- **Dürüst atıf:** düşük seviyeli bulanık ilkel (tokenizer / çekim / Levenshtein) **Huan'ındır**; **alana özel puanlayıcı, bütün-gıda ayrıştırması, veri-yükleme stratejisi ve UX benimdir.**

---
---

## Slide 14 — 5) The clickable PDF → editor bridge

> 🖼️ **IMAGE — 3-step sequence:** (1) cursor clicking a highlighted nutrient name in the PDF table → (2) the `NutrientPopover` appearing with a focused value input → (3) the new nutrient row landing in the editor. Arrows numbered 1-2-3.
> *Caption:* "A click on the page becomes a data row. That's what makes labeling fast."

- The payoff of clickable table nutrients: **a click on the page drops a value straight into the editor**.
- Click → **`NutrientPopover`**, positioned **viewport-aware** — below the anchor, clamped to the screen, flipped above if there's no room; focuses the value input; closes on Escape / outside-click.
- It emits a nutrient row **appended to the first food item** (de-duplicated). **`FoodItemForm`** composes the food autocomplete + dynamic nutrient rows into one food card.

---

## Slayt 14 — 5) Tıklanabilir PDF → editör köprüsü

> 🖼️ **GÖRSEL:** Slide 14'teki 3 adımlı dizi ((1) PDF'te besin adına tıklama → (2) `NutrientPopover` açılması → (3) editöre yeni satır düşmesi; oklar 1-2-3).
> *Altyazı:* "Sayfadaki tıklama bir veri satırına döner. Etiketlemeyi hızlı yapan budur."

- Tıklanabilir tablo besinlerinin getirisi: **sayfadaki tıklama değeri doğrudan editöre düşürür**.
- Tıklama → **`NutrientPopover`**, **görünüm-alanına duyarlı** konumlanır — çapanın altında, ekrana sıkıştırılmış, yer yoksa üste çevrilmiş; değer girişine odaklanır; Escape / dışına-tıklamada kapanır.
- **İlk gıda öğesine eklenen** (tekilleştirilmiş) bir besin satırı yayar. **`FoodItemForm`** gıda otomatik tamamlama + dinamik besin satırlarını tek gıda kartında birleştirir.

---
---

## Slide 15 — 6) Cockpit views — review & performance

> 🖼️ **IMAGE — two screenshots side by side:** left, **Approval** (Original Submission vs the editable Reviewer Final Payload, with the Decision dropdown + Approval note); right, **Labeler Dashboard** (summary cards + the Performance-by-labeler table).
> *Caption:* "Not a single form — a complete operational UI."

- **Approval** — side-by-side: the **Original Submission** vs an **editable Reviewer Final Payload**, with a decision (Usable / No Usable Data) and a note. Gated to approvers; **read-only preview** for everyone else.
- **Dashboard** — labeler performance computed **client-side** from immutable submission/approval records: Submitted / Pending / Accepted / **Corrected** / Superseded, plus a per-submission **"Mistake Detail"** column.
- **Permissions differ per view** — labeler, tester, cockpit, approver and developer accounts each see different controls.

---

## Slayt 15 — 6) Kokpit görünümleri — inceleme & performans

> 🖼️ **GÖRSEL:** Slide 15'teki iki ekran görüntüsü (solda **Onay** — Orijinal Gönderi vs düzenlenebilir İnceleyici Nihai Yükü, Karar + not; sağda **Etiketleyici Panosu** — özet kartları + performans tablosu).
> *Altyazı:* "Tek bir form değil — eksiksiz bir operasyon arayüzü."

- **Onay** — yan yana: **Orijinal Gönderi** vs **düzenlenebilir İnceleyici Nihai Yükü**, bir karar (Kullanılabilir / Kullanılamaz) ve notla. Onaylayıcılara kapılı; diğerlerine **salt-okunur önizleme**.
- **Pano** — etiketleyici performansı, değiştirilemez gönderi/onay kayıtlarından **istemci tarafında** hesaplanır: Gönderilen / Bekleyen / Kabul / **Düzeltilen** / Geçersizleşen, artı gönderi başına **"Hata Detayı"** sütunu.
- **İzinler her görünümde farklı** — etiketleyici, test, kokpit, onaylayıcı ve geliştirici hesapları farklı kontroller görür.

---
---

## Slide 16 — 6) Cockpit views — operations

> 🖼️ **IMAGE — Useful Papers with one row expanded:** the table (Paper · Routing · Latest AI · Submissions · Approval · Final Outcome) with one row opened into the **AI Extraction Detail** panel (Confidence, Rows accepted/input, rejection-reason badges, normalized JSON). Small inset of the **Pipeline** funnel bars.
> *Caption:* "We show the normalization summary — deliberately not the model's raw reasoning."

- **Useful Papers** — Paper · Routing · **Latest AI** · Submissions · Approval · Final Outcome, with an expandable **AI detail panel**: confidence, accepted rows, the **rejection-reason histogram**, and the normalized JSON — i.e. the *normalization summary*, **deliberately not** the model's raw reasoning.
- **Pipeline** — the funnel (search → filter → upload → small / medium / strong → human) as bars with **kept / dropped** counts, plus a live **"Right Now"** grid (waiting, running, ready for labelers, awaiting approval, AI failed).
- All of this was **extracted out of one monolithic file into eight focused views**; metrics survive the **legacy backfill** so no stage falsely reads zero.

---

## Slayt 16 — 6) Kokpit görünümleri — operasyon

> 🖼️ **GÖRSEL:** Slide 16'daki bir satırı açılmış **Faydalı Makaleler** tablosu (**AI Extraction Detail** paneli: güven, kabul/giriş satır, red-nedeni rozetleri, normalize JSON). **Pipeline** huni çubuklarından küçük kesit.
> *Altyazı:* "Normalizasyon özetini gösteririz — kasıtlı olarak modelin ham muhakemesini değil."

- **Faydalı Makaleler** — Makale · Yönlendirme · **Son YZ** · Gönderiler · Onay · Nihai Sonuç, genişletilebilir **YZ detay paneliyle**: güven, kabul edilen satırlar, **red-nedeni histogramı** ve normalize JSON — yani *normalizasyon özeti*, **kasıtlı olarak** modelin ham muhakemesi değil.
- **Pipeline** — huni (arama → filtre → yükleme → küçük / orta / güçlü → insan) **korunan / düşen** sayılarıyla çubuklar hâlinde, artı canlı **"Şu An"** ızgarası (bekleyen, çalışan, etiketçiye hazır, onay bekleyen, YZ başarısız).
- Bunların tümü **tek devasa dosyadan sekiz odaklı görünüme ayrıştırıldı**; metrikler **eski-veri tamamlamasından** sağ çıkar, hiçbir aşama yanlışlıkla sıfır okumaz.

---
---

## Slide 17 — 7) App shell, authentication & theme

> 🖼️ **IMAGE:** the **Login** screen ("OpenNutri Annotator", Sign in with Google + email/password + "Forgot password?"), next to a **light/dark** comparison of the same screen showing the OS-aware theme.
> *Caption:* "Session → login → app, themed to the OS with no flash."

- **`App.jsx`** checks the Supabase session → routes to **reset-password** / **login** / the annotator.
- **`Login.jsx`** — email/password **and Google OAuth**, plus "Forgot password?".
- **`useTheme`** — resolves an override on top of the OS theme, listens to `prefers-color-scheme`, writes the theme with **no flash-of-wrong-theme**, and persists an override only when it differs from the system (so it follows the OS by default).
- **Honest attribution:** the shell and login flow are mine; the later theme **centralization** and the reset-password **fix** were **Huan's**, built on top of this.

---

## Slayt 17 — 7) Uygulama kabuğu, kimlik doğrulama & tema

> 🖼️ **GÖRSEL:** Slide 17'deki **Giriş** ekranı ("OpenNutri Annotator", Google ile + e-posta/parola + "Forgot password?"), yanında aynı ekranın **açık/koyu** kıyası (OS'a duyarlı tema).
> *Altyazı:* "Oturum → giriş → uygulama, parıltısız biçimde OS'a göre temalı."

- **`App.jsx`** Supabase oturumunu kontrol eder → **parola-sıfırlama** / **giriş** / etiketleyiciye yönlendirir.
- **`Login.jsx`** — e-posta/parola **ve Google OAuth**, artı "Forgot password?".
- **`useTheme`** — OS temasının üstüne geçersiz-kılma çözer, `prefers-color-scheme`'i dinler, temayı **yanlış-tema-parıltısı olmadan** yazar ve geçersiz-kılmayı yalnızca sistemden farklıysa kalıcılaştırır (varsayılan olarak OS'u izler).
- **Dürüst atıf:** kabuk ve giriş akışı benimdir; sonraki tema **merkezileştirmesi** ve parola-sıfırlama **düzeltmesi** bunun üstüne **Huan'ındı**.

---
---

## Slide 18 — Closing: what it adds up to

> 🖼️ **IMAGE — "by the numbers" card + hero:** a clean stat card (14,100 · 4,050 · 970 · 27) beside the workspace hero shot from Slide 0.
> *Caption:* "Production on Vercel. Fully client-side. Precision-first."

- **~14,100 lines** of frontend; **10,334** in the principal files; **~970 lines of tests** locking the hardest behavior.
- The **PDF evidence engine alone ≈ 4,050 lines** of document layout analysis *in a browser* — column detection, an adaptive table classifier, caption-anchored growth, MAD clipping, a 3-tier matcher that survives a lying page number, union-find dedup — over **27 commits**. On the team's own assessment, the **single hardest piece of code in the project, frontend or backend.**
- Not a prototype: **production on Vercel**, **fully client-side** (no server round-trip), works on **arbitrary publisher PDFs**, stays inside a **free-tier budget**, and is **precision-first** — it would rather highlight nothing than the wrong thing, because a wrong number on a food label is worse than none.
- **It changes the unit of work from "transcribe a paper" to "verify a draft" — and makes every verification both traceable and a lesson the AI learns from.** That's what lets OpenNutri scale where manual curation never could.

---

## Slayt 18 — Bitiş: hepsi neye varıyor

> 🖼️ **GÖRSEL:** Slide 18'deki "rakamlarla" kartı (14.100 · 4.050 · 970 · 27) + Slide 0'daki çalışma alanı görseli.
> *Altyazı:* "Vercel'de yayında. Tamamen istemci tarafında. Önce-kesinlik."

- **~14.100 satır** frontend; **10.334** ana dosyalarda; en zor davranışı kilitleyen **~970 satır test**.
- **Tek başına PDF kanıt motoru ≈ 4.050 satır** — *tarayıcıda* belge yerleşim analizi — sütun saptama, uyarlanır tablo sınıflandırıcı, başlık-çapalı büyütme, MAD kırpma, yalan sayfa numarasından sağ çıkan 3-kademeli eşleştirici, union-find tekilleştirme — **27 commit** boyunca. Ekibin kendi değerlendirmesine göre **projedeki tek en zor kod parçası, frontend ya da backend.**
- Prototip değil: **Vercel'de yayında**, **tamamen istemci tarafında** (sunucu turu yok), **keyfi yayıncı PDF'leri** üzerinde çalışır, **ücretsiz-katman bütçesi** içinde kalır ve **önce-kesinlik** ilkelidir — yanlış bir şeyi vurgulamaktansa hiçbir şeyi vurgulamaz, çünkü bir etiketteki yanlış sayı, hiç sayı olmamasından kötüdür.
- **İşin birimini "makale kopyalamak"tan "taslak doğrulamak"a çevirir — ve her doğrulamayı hem izlenebilir hem de yapay zekânın öğrendiği bir ders yapar.** OpenNutri'nin, manuel derlemenin asla yapamadığını ölçekte yapmasını sağlayan budur.


# OpenNutri — Ayşegül Doğan — Defense Presentation

> **Scope of this document.** This is Ayşegül Doğan's individual presentation script. The OpenNutri project was built by three people; their work divides as:
>
> - **Ayşegül Doğan — the entire annotator frontend:** the PDF evidence engine, the annotation workspace, the food/nutrient autocomplete experience, and the cockpit/workflow views. (~14,100 current frontend lines; 10,334 lines in the principal files.)
> - **Duc Huan Ngo — reusable & full-stack pieces:** the `fuzzyMatch` engine, the suggestions/attachments feature, the reset-password fix, the legacy conflict system, theme centralization, infinite scroll.
> - **Arciel Aliognis Baez Zamora — the entire backend:** Supabase database/RLS/RPC contract, the 3-stage AI cascade, the discovery crawler, feedback learning, daily-ops automation, reference-data ETL, documentation.
>
> What follows is written in the **first person ("I")** as Ayşegül, and is organized in five parts:
> **1.** the general problem · **2.** how we solved it as a team · **3.** what my part is and why it is necessary · **4.** everything I built, one by one (why it is needed · how I did it · the hard part · the technologies · the files & line counts) · **5.** a closing summary.
>
> The full document is given **twice**: first in **English**, then in **Turkish (Türkçe)**.

---

# ENGLISH VERSION

## 1. What is the general problem?

The world needs **trustworthy food-composition data** — how much protein, fat, iron, vitamin C, etc. a given food actually contains. This data feeds nutrition labels, diet-tracking apps, food exporters, food inspection, and public-health datasets.

The problem is that this data is **scattered across thousands of scientific papers**, written in inconsistent formats, and **no single source contains it in a clean, reusable form**. A nutritionist who wants "the iron content of raw lentils, measured directly" has to find the right paper, read it, locate the right table, and copy the number by hand. This does not scale.

Two naive solutions both fail:

- **"Just scrape the papers automatically."** Scientific papers are messy: the data lives inside PDF tables with footnotes, units, sample codes, and multi-column layouts. Pure automation produces too many wrong numbers, and wrong nutrition data is worse than none.
- **"Just ask an AI."** A language model will confidently invent values. For something that ends up on a food label, a hallucinated number is dangerous.

So the real problem is: **how do you discover the right papers at scale, extract candidate values cheaply, and still guarantee that a qualified human verifies every number before it becomes "truth"?** You need both automation *and* a human in the loop — and the human's job has to be fast enough to actually be done.

## 2. How did we solve it (as a team)?

We built **OpenNutri** — an end-to-end pipeline that combines machine scale with human judgment. It is one system with three surfaces over a single Supabase Postgres database:

1. **A Python discovery & extraction pipeline** (Arciel's backend) that starts from reference USDA food/nutrient data, searches the scientific literature (Europe PMC, OpenAlex, Semantic Scholar), filters for relevance, downloads the PDFs, and runs a **three-stage AI cascade** — a cheap screening model on ~1,500 papers/day, a medium triage model, and a strong PDF-reading model on the best ~20/day — to produce **candidate** nutrition values.

2. **A Supabase database contract** (Arciel's backend) that stores everything immutably, enforces who-can-do-what with row-level security, and runs the review workflow.

3. **The expert-annotator web app** (my frontend) — the part a human actually uses. The AI's candidate values are never trusted directly. They are presented to a qualified labeler inside a workspace where they can **see the source PDF, see exactly which table and sentence each number came from**, correct it, and submit it. An approver then finalizes the truth, and that accepted human truth is **fed back** to make the next crawl smarter.

The key idea: **the AI does the searching and the heavy reading so the human only has to verify, not hunt.** My frontend is what makes that verification fast, visual, and trustworthy. Without it, the whole pipeline produces unverified guesses; with it, every published number has a human behind it who could *see* the evidence on the page.

## 3. What is my part, why is it necessary, and what did I do?

**My part is the entire expert-annotator frontend** — the web application that every human labeler and approver actually uses. It is a **React 19 + Vite** single-page app, deployed on **Vercel**.

**Why it is necessary.** The backend can find papers and propose numbers, but a proposed number is worthless until a human confirms it. The frontend is the *only* place where verification happens. If verification is slow, painful, or untrustworthy, no human truth ever gets produced and the whole project fails. So the frontend is not "the UI on top" — it is the **verification instrument** that the project's entire value depends on.

It also had a hard constraint: the whole project runs on **free tiers** (Supabase free egress limit, Vercel). So the frontend couldn't just fetch everything — it had to be carefully engineered to stay inside strict data limits while still feeling instant.

**What I did, in one sentence:** I built the workspace where a labeler opens a paper, and **the exact table or paragraph a value came from lights up on the PDF**, the nutrient names inside that table become clickable, a click drops the value into an editor, forgiving search maps it to the canonical food/nutrient catalog, and the finished, validated submission is stored — all client-side, on arbitrary publisher PDFs, fast enough to do all day.

Concretely, I own seven things, which the next section walks through one by one:

1. The **annotation workspace & orchestrator** — the screen that ties everything together.
2. The **PDF evidence engine** — the hardest piece of code in the entire project; it rebuilds document structure from raw PDF glyphs so evidence can be highlighted.
3. The **durable caching layers** — what makes PDFs and highlights instant and shareable.
4. The **domain-tuned autocomplete** — forgiving food/nutrient search that maps free text to the catalog.
5. The **clickable PDF→editor bridge** — turning a click on the page into a data row.
6. The **cockpit & workflow views** — approval, dashboards, useful-paper overview, pipeline funnel.
7. The **app shell, authentication & theme** — session, login, OS-aware theming.

## 4. Everything I built, one by one

For each piece: **why it is needed · how I did it · the hard part · the technologies · the files and line counts.**

---

### 4.1 The annotation workspace & orchestrator

**Why it is needed.** A labeler needs *one* screen that loads the work queue, shows the paper and its PDF, holds the food/nutrient editor, and submits the result. Everything else hangs off this orchestrator.

**How I did it.** `Annotate.jsx` owns roughly **30 pieces of React state**, all data fetching, view routing, and every labeling action. I designed it around the free-tier egress limit:

- **Parallel boot, no waterfall.** The queue loads on mount *in parallel* with the reviewer-profile sync, and the shell paints immediately — there is no full-screen loading gate.
- **One-RPC queue with a versioned fallback.** `refreshQueue` gets lean cards + the latest AI payload + this user's status in a *single* round-trip; if that RPC isn't deployed yet, it transparently falls back to a three-query legacy path. So the app keeps working across backend versions.
- **Lazy cockpit + idle catalog load.** The heavy cockpit queries run only on first visit to a cockpit tab, and the full food catalog is fetched in 1,000-row batches *during browser idle time* — so neither blocks first paint.
- **AI-prefill that never overwrites.** When a paper has no saved draft, it opens pre-filled with the AI's normalized values converted into editable rows; but if a human draft already exists, I load that instead and **never** overwrite human work.
- **Validated submit/approve paths**, and every database write is **test-mode aware** — in test mode it appends to a local log instead of touching Supabase, so the app can be demonstrated without polluting real data.

**The hard part.** Orchestrating ~30 interdependent state values *and* staying inside a strict data-egress budget at the same time. The "never overwrite a human draft with AI prefill" rule sounds simple but touches every load path.

**Technologies.** React 19 hooks, Supabase JS RPCs, `requestIdleCallback`, a test-mode shim.

**Files & lines.** `pages/Annotate.jsx` (1,163), `utils/annotateHelpers.js` (574 — the shared "brain": payload normalization + the cockpit pipeline funnel), `views/QueueView.jsx` (227). **≈ 1,960 lines.**

---

### 4.2 The PDF evidence engine — *the hardest piece of code in the whole project*

**Why it is needed.** This is the heart of the whole verification idea. When the AI says *"protein = 22.04 g/100 g"*, the human must be able to **see that number on the actual page** to trust it. And to make data entry fast, the nutrient names *inside the PDF's tables* should be **clickable**. But PDF.js — the library that reads PDFs in the browser — hands you only a flat list of positioned letters: `{ text, x, y, width, height }`. **There is no concept of a table, a column, or a paragraph.** To highlight "the table this value came from," I first had to **reconstruct the document's structure from pure geometry**, in the browser.

**How I did it.** `PdfTextScanner.js` is about **70 functions of computational geometry**. The pipeline, per page, is: extract positioned glyphs → compute adaptive metrics → detect columns → group glyphs into rows → split rows into fragments → classify each fragment → grow table regions from captions → build paragraph blocks → then run a matcher cascade that locates each AI evidence quote on the page.

I'll walk the **nine hard sub-problems** one by one, because together they *are* this subsystem:

1. **Adaptive metrics.** Every threshold derives from the page's *own* typography (median glyph height, median row gap), each clamped. The same code works on a dense 7 pt table and a 12 pt abstract — **no hardcoded pixel values**.
2. **Column detection by projection profile.** Multi-column journals fused two columns into one "paragraph." I hand-wrote a classic **vertical projection profile**: bin the x-axis at 2 pt, find vertical "gutters" (runs that are ≥ 6 pt wide with content on *both* sides), and split rows that cross a gutter — so a left-column line and a right-column line at the same height never fuse.
3. **A per-fragment table/prose classifier.** For each text fragment I compute a feature vector (numeric-token count, sample-codes like "T1", abbreviations, all-caps tokens, caption prefixes, units, cluster count, sentence punctuation…) and derive an integer **`tableScore`** → `isTableLike`. This is a small **hand-built text classifier** that decides, per glyph-run, "is this a table cell or prose?"
4. **Caption-anchored table growth.** Tables are found from their captions ("Table 3 …"), then the region grows **downward** row by row while rows stay aligned and close. Crucially, once a data row is accepted, later data rows keep being accepted even if a lone cell like "1.50" wouldn't score as a table on its own — because *in context* it obviously is.
5. **Paragraph blocks + interleaved-data merging.** Prose lines become paragraphs, then a second pass **re-joins** paragraphs that a stray numeric line split apart — which is why a sentence quoting "22.04 ± 1.25 g/100 g" mid-paragraph still resolves to one clean highlight.
6. **Robust column clipping with MAD.** When PDF.js still fuses two columns, I clip using the **median and median-absolute-deviation (MAD)** — textbook robust statistics — to fence out outliers without throwing away legitimately short last lines.
7. **The source-quote matcher (3-tier cascade).** To find the AI's exact quote on the page, I try paragraph-match → search-fragment match → row-window match, each with fallbacks, and I normalize text by inserting spaces at digit↔letter boundaries so "10.80g/100 g" matches "10.80 g/100 g".
8. **The lying `page_hint`.** The AI reports the *printed* page number (e.g. "1217" on a 5-page offprint). When the hint exceeds the real page count I make it **non-gating**, and I build a **histogram of printed-vs-PDF page offsets** to map the hint to the correct PDF page anyway.
9. **Stable, de-duplicated overlays (union-find, twice).** I run **union-find with path compression** to collapse overlapping highlight regions into one, and a *second* union-find at the source level merges different AI rows that cite the *same* paragraph — so three rows about one table become one clean chip and one overlay, and overlays don't flicker between re-renders.

On top of the scanner, `PdfViewer.jsx` does the rendering: a **self-hosted, bundled PDF.js worker** (no CDN dependency on the critical path); a **headless evidence scan** that reads each page's text *without rendering its canvas* (yielding during browser idle) so it can pre-compute highlights and learn which pages hold evidence; **evidence-first rendering** (page 1 + evidence pages paint first, the rest backfill); the **coordinate transform** that scales PDF bounds to screen pixels and flips the Y-axis; and a **custom text renderer** that injects clickable nutrient marks only inside detected tables.

**The hard part.** All of it — this is *document layout analysis running in a web browser*, with no server and no machine-learning model, tuned against real journal PDFs across **27 commits**. It is, honestly, the single hardest piece of code in the project, frontend or backend.

**Technologies.** PDF.js / react-pdf, browser text-layer geometry, projection profiles, robust statistics (MAD), union-find, `requestIdleCallback`, custom text renderers.

**Files & lines.** `utils/PdfTextScanner.js` (**2,323**), `components/PdfViewer.jsx` (939), `utils/EvidenceLocations.js` (439). I also wrote the test suite that locks this behavior down: `PdfTextScanner.test.js` (655), `EvidenceLocations.test.js` (225), `evidenceStatusCache.test.js` (92) — **972 lines of tests**. **≈ 3,700 lines of engine + ~970 of tests.**

---

### 4.3 The durable caching layers

**Why it is needed.** PDFs in this domain are large (often 10–25 MB), and two things break the obvious approach: the browser's normal HTTP cache **evicts** files that big, and Supabase serves them with `no-cache`. Re-scanning a PDF's structure on every open is also slow. So I needed caching that is durable, instant, and *shared between reviewers*.

**How I did it.** Three layers:

- **PDF bytes** are stored in the **Cache Storage API** (not the volatile HTTP cache), keyed by URL, with an **LRU index in localStorage** (cap 40). I hand a fresh `ArrayBuffer` to PDF.js each time (it detaches buffers on transfer), and I **prefetch the next two queue papers during idle** so the next paper opens instantly.
- **Resolved evidence positions** (which region each value highlighted to) are cached **per paper, both locally** (localStorage LRU) **and remotely** in a Supabase table via an RPC. So when *anyone* re-opens a paper that has been reviewed before, the overlays paint **from cache before the scan even finishes**.

**The hard part.** Realizing the HTTP cache wouldn't hold these files at all, and the `ArrayBuffer`-detachment bug that silently breaks PDF.js on a second read.

**Technologies.** Cache Storage API, localStorage LRU, a Supabase dedup table + RPC.

**Files & lines.** `utils/pdfCache.js` (107), `utils/evidenceStatusCache.js` (139), `utils/evidenceDedupStorage.js` (44), `hooks/useEvidenceStatusCache.js` (101). **≈ 390 lines.**

---

### 4.4 The domain-tuned autocomplete

**Why it is needed.** A labeler types a food or nutrient name in free text ("apple", "vitamin c") and it must map to the **canonical USDA catalog entry** — forgivingly (typos, plurals, partial names) but **without unsafe over-matching** (typing "apple" must surface *Apple, raw*, not *Apple juice, canned*).

**How I did it.** I built a **weighted scoring ranker** over each entry's canonical name, base name, and aliases, on top of the fuzzy-match primitive Huan wrote. `scoreFoodMatch` rewards exact/prefix/first-token hits at tuned weights, scores per-token relations (exact / stemmed / edit-distance), and adds **whole-food disambiguation**: it penalizes processing words ("canned", "dried"), baby-food/restaurant entries, and derived-prefix false friends, while rewarding whole-food hints — so generic queries surface the raw whole food. A query with no useful overlap is hard-rejected. Before the in-memory catalog finishes loading, it runs a **two-query Supabase strategy** (prefix + broad `ilike`); after, it ranks locally. Debounced 250 ms, full keyboard navigation, custom-food entry on blur/Enter, and every resolution is logged to a `search_sessions` telemetry table (which self-disables if the table is missing).

**The hard part.** The ranking weights — making "apple" reliably surface the right whole food across a catalog of thousands of near-duplicate entries without ever silently picking a wrong food.

**Technologies.** React, Supabase catalog queries, in-memory weighted ranking, debouncing, search-session telemetry, and Huan's `fuzzyMatch` engine as the low-level primitive.
*(Honest attribution: the fuzzy tokenizer/inflection/Levenshtein primitive is Huan's; the domain-tuned scorer, the whole-food disambiguation, the data-loading strategy, and the UX are mine.)*

**Files & lines.** `components/FoodAutocomplete.jsx` (664), `components/NutrientAutocomplete.jsx` (334), `utils/searchSessionLogger.js` (110). **≈ 1,110 lines.**

---

### 4.5 The clickable PDF → editor bridge

**Why it is needed.** The payoff of making table nutrients clickable is that a click on the page should **drop a value straight into the editor** — that's what makes labeling fast.

**How I did it.** Clicking a highlighted nutrient in the PDF opens `NutrientPopover`, which positions itself **viewport-aware** (below the anchor, clamped to the screen, flipped above if there's no room), focuses the value input, closes on Escape/outside-click, and emits a nutrient row that gets appended to the first food item (de-duplicated). `FoodItemForm` composes the food autocomplete, the dynamic nutrient rows, and the nutrient autocomplete into one food card.

**The hard part.** Reliable click resolution through overlapping PDF text layers, and popover positioning that never falls off-screen.

**Technologies.** React, viewport-geometry math, the PDF text-layer click resolution from 4.2.

**Files & lines.** `components/NutrientPopover.jsx` (128), `components/FoodItemForm.jsx` (110). **≈ 240 lines.**

---

### 4.6 The cockpit & workflow views

**Why it is needed.** Beyond the labeler's workspace, the system needs **approval** (a reviewer corrects and finalizes truth), **dashboards** (how is each labeler performing?), a **useful-papers overview**, and a **pipeline funnel** that visualizes the whole crawl→AI→human flow. These were extracted out of what used to be one monolithic file into eight focused views.

**How I did it.**
- **`ApprovalView`** — side-by-side: the original labeler submission vs. an **editable** reviewer-final payload, with a decision and note (gated to approvers; read-only preview for everyone else).
- **`DashboardView`** — labeler-performance metrics computed **client-side** from submissions and approvals (submitted / pending / accepted / corrected / superseded, plus a per-submission "mistake detail" table).
- **`AllPapersView`** ("Useful Papers") — the routing / AI / submission / outcome table, with an expandable **AI detail panel** showing confidence, accepted rows, the rejection-reason histogram, and the normalized JSON — i.e. the *normalization summary*, deliberately **not** the model's raw reasoning.
- **`PipelineOpsView`** — renders the 10-stage funnel (search → filter → upload → small/medium/strong → human) as bars with retained/dropped counts, plus a live "Right Now" grid.

**The hard part.** Computing trustworthy performance and funnel metrics purely on the client from immutable submission/approval records, including the legacy backfill so historical papers don't make a stage falsely read zero.

**Technologies.** React views, client-side aggregation, Supabase reads.

**Files & lines.** `ApprovalView.jsx` (199), `DashboardView.jsx` (171), `PipelineOpsView.jsx` (162), `AllPapersView.jsx` (140), plus the supporting `AiDetailPanel.jsx` (118), `EvidenceStrip.jsx` (54), `PayloadSummary.jsx` (49), and `ReviewerAdminView` / `SuggestionsReviewView` / `MySuggestionsView`. **≈ 1,100 lines across the views.**

---

### 4.7 The app shell, authentication & theme

**Why it is needed.** Something has to check the session, route a user to login / password-reset / the app, and theme the whole thing.

**How I did it.** `App.jsx` checks the Supabase session, detects a password-recovery URL and routes to the reset page, otherwise to login, otherwise to the annotator. `Login.jsx` does email/password and **Google OAuth**. `useTheme` resolves an override on top of the OS theme, listens to `prefers-color-scheme`, writes the theme with no flash-of-wrong-theme, and persists an override only when it differs from the system — so the app follows the OS by default.

**Honest attribution.** The shell and login flow are mine; **the later theme *centralization* and the reset-password *fix* were Huan's** contributions on top of this.

**Technologies.** Supabase Auth, React, `matchMedia`, `sessionStorage`, `useLayoutEffect`.

**Files & lines.** `App.jsx` (96), `hooks/useTheme.js` (75), `pages/Login.jsx`. **≈ 250 lines.**

---

## 5. Closing summary

I built the **entire frontend of OpenNutri** — the verification instrument the whole project depends on. In numbers:

- **~14,100 lines** of current frontend code; **10,334 lines** concentrated in the principal queue, PDF, autocomplete, and view files; plus **~970 lines of tests** locking down the hardest behavior.
- The **PDF evidence engine alone is ~4,050 lines** of *document layout analysis running in a web browser* — projection-profile column detection, an adaptive per-fragment table classifier, caption-anchored table growth, MAD-robust column clipping, a three-tier quote matcher that survives a lying page number, and union-find de-duplication, refined over **27 commits**. It is, on the team's own assessment, the **single hardest piece of code in the entire project — frontend or backend.**

And it isn't a prototype. It is **production-deployed on Vercel**, it runs **entirely client-side** with no server round-trip, it works on **arbitrary publisher PDFs**, it stays inside a **free-tier data budget** through parallel boot, one-RPC loading, idle catalog loading, and durable shared caching, and it is **precision-first** — it would rather highlight nothing than highlight the wrong thing, because a wrong number on a food label is worse than none.

The backend can find papers and the AI can propose numbers, but **none of it becomes trustworthy data until a human confirms it on my screen.** My frontend is what turns a pile of PDFs and AI guesses into something a nutritionist can actually believe — and it does it fast enough to use all day.

---

# TÜRKÇE VERSİYON

## 1. Genel problem nedir?

Dünyanın **güvenilir besin bileşim verisine** ihtiyacı var — yani belirli bir gıdanın gerçekte ne kadar protein, yağ, demir, C vitamini vb. içerdiğine. Bu veri; besin etiketlerini, diyet takip uygulamalarını, gıda ihracatçılarını, gıda denetimini ve halk sağlığı veri setlerini besler.

Sorun şu ki bu veri **binlerce bilimsel makaleye dağılmış** durumda, tutarsız formatlarda yazılmış ve **hiçbir tek kaynak onu temiz, yeniden kullanılabilir bir biçimde içermiyor.** "Çiğ mercimeğin doğrudan ölçülmüş demir içeriği"ni isteyen bir beslenme uzmanı; doğru makaleyi bulmak, okumak, doğru tabloyu bulmak ve sayıyı elle kopyalamak zorunda. Bu ölçeklenmiyor.

İki kolaycı çözüm de başarısız oluyor:

- **"Makaleleri otomatik olarak kazıyalım."** Bilimsel makaleler dağınıktır: veri; dipnotları, birimleri, örnek kodları ve çok sütunlu yerleşimleri olan PDF tablolarının içinde yaşar. Saf otomasyon çok fazla yanlış sayı üretir — ve **yanlış besin verisi, hiç veri olmamasından daha kötüdür.**
- **"Yapay zekâya soralım."** Bir dil modeli, değerleri özgüvenle uydurur. Sonunda bir besin etiketine giden bir şey için, halüsinasyonla üretilmiş bir sayı tehlikelidir.

Yani asıl problem: **doğru makaleleri nasıl ölçekli biçimde keşfeder, aday değerleri ucuza çıkarır, ama yine de her sayının "gerçek" olmadan önce nitelikli bir insan tarafından doğrulanmasını nasıl garanti edersin?** Hem otomasyona *hem de* döngüde bir insana ihtiyacın var — ve insanın işi gerçekten yapılabilecek kadar hızlı olmalı.

## 2. Biz bunu (ekip olarak) nasıl çözdük?

**OpenNutri**'yi kurduk — makine ölçeğini insan muhakemesiyle birleştiren uçtan uca bir hat. Tek bir Supabase Postgres veritabanı üzerinde üç yüzeyi olan tek bir sistem:

1. **Bir Python keşif & çıkarım hattı** (Arciel'in backend'i): referans USDA gıda/besin verisinden başlar, bilimsel literatürü (Europe PMC, OpenAlex, Semantic Scholar) tarar, alaka için filtreler, PDF'leri indirir ve **üç aşamalı bir yapay zekâ kademesi** çalıştırır — günde ~1.500 makalede ucuz bir eleme modeli, bir orta seviye ayıklama modeli ve en iyi ~20 makalede güçlü bir PDF-okuyan model — **aday** besin değerleri üretir.

2. **Bir Supabase veritabanı sözleşmesi** (Arciel'in backend'i): her şeyi değiştirilemez biçimde saklar, kimin neyi yapabileceğini satır düzeyi güvenlikle uygular ve inceleme iş akışını yürütür.

3. **Uzman-etiketleyici web uygulaması** (benim frontend'im): bir insanın gerçekten kullandığı kısım. Yapay zekânın aday değerlerine asla doğrudan güvenilmez. Bunlar; nitelikli bir etiketleyiciye, **kaynak PDF'i görebileceği, her sayının tam olarak hangi tablo ve cümleden geldiğini görebileceği** bir çalışma alanı içinde sunulur; etiketleyici düzeltir ve gönderir. Ardından bir onaylayıcı gerçeği kesinleştirir ve bu kabul edilen insan gerçeği, bir sonraki taramayı daha akıllı yapmak için **geri beslenir.**

Temel fikir: **arama ve ağır okuma işini yapay zekâ yapar, böylece insan yalnızca doğrulamak zorunda kalır — avlanmak değil.** Benim frontend'im, bu doğrulamayı hızlı, görsel ve güvenilir kılan şeydir. O olmadan tüm hat doğrulanmamış tahminler üretir; onunla ise yayınlanan her sayının arkasında, kanıtı sayfanın üzerinde *görebilmiş* bir insan vardır.

## 3. Benim parçam ne, neden gerekli ve neyi yaptım?

**Benim parçam, uzman-etiketleyici frontend'inin tamamı** — her insan etiketleyicinin ve onaylayıcının gerçekten kullandığı web uygulaması. **React 19 + Vite** tek-sayfa uygulaması olup **Vercel**'de yayında.

**Neden gerekli.** Backend makaleleri bulup sayılar önerebilir, ama önerilen bir sayı, bir insan onu doğrulayana kadar değersizdir. Frontend, doğrulamanın gerçekleştiği *tek* yerdir. Doğrulama yavaş, zahmetli veya güvenilmezse hiçbir insan gerçeği üretilmez ve tüm proje başarısız olur. Yani frontend "üstteki arayüz" değildir — projenin tüm değerinin dayandığı **doğrulama enstrümanıdır.**

Ayrıca zorlu bir kısıtı vardı: tüm proje **ücretsiz katmanlarda** çalışıyor (Supabase ücretsiz veri-çıkış limiti, Vercel). Bu yüzden frontend her şeyi öylece çekemezdi — katı veri limitleri içinde kalırken yine de anlık hissettirecek şekilde dikkatle mühendislik yapılması gerekti.

**Ne yaptığım, tek cümlede:** Bir etiketleyicinin bir makaleyi açtığı ve **bir değerin geldiği tam tablonun veya paragrafın PDF üzerinde aydınlandığı**, o tablonun içindeki besin adlarının tıklanabilir hâle geldiği, bir tıklamanın değeri editöre düşürdüğü, bağışlayıcı aramanın onu kanonik gıda/besin kataloğuna eşlediği ve tamamlanmış, doğrulanmış gönderinin saklandığı çalışma alanını kurdum — hepsi istemci tarafında, keyfi yayıncı PDF'leri üzerinde, bütün gün yapılabilecek kadar hızlı.

Somut olarak yedi şeyin sahibiyim; bir sonraki bölüm bunları tek tek anlatıyor:

1. **Etiketleme çalışma alanı & orkestratör** — her şeyi bir araya bağlayan ekran.
2. **PDF kanıt motoru** — tüm projedeki en zor kod parçası; kanıtın vurgulanabilmesi için ham PDF harflerinden belge yapısını yeniden inşa eder.
3. **Kalıcı önbellek katmanları** — PDF'leri ve vurguları anlık ve paylaşılabilir yapan şey.
4. **Alana özel otomatik tamamlama** — serbest metni kataloğa eşleyen bağışlayıcı gıda/besin araması.
5. **Tıklanabilir PDF→editör köprüsü** — sayfadaki bir tıklamayı bir veri satırına dönüştürmek.
6. **Kokpit & iş akışı görünümleri** — onay, panolar, faydalı-makale genel bakışı, hat hunisi.
7. **Uygulama kabuğu, kimlik doğrulama & tema** — oturum, giriş, işletim sistemine duyarlı tema.

## 4. Yaptığım her şey, tek tek

Her parça için: **neden gerekli · nasıl yaptım · zor kısım · teknolojiler · dosyalar ve satır sayıları.**

---

### 4.1 Etiketleme çalışma alanı & orkestratör

**Neden gerekli.** Bir etiketleyiciye, iş kuyruğunu yükleyen, makaleyi ve PDF'ini gösteren, gıda/besin editörünü tutan ve sonucu gönderen *tek* bir ekran lazım. Geri kalan her şey bu orkestratöre asılıdır.

**Nasıl yaptım.** `Annotate.jsx` yaklaşık **30 parça React state**'ine, tüm veri çekimine, görünüm yönlendirmesine ve her etiketleme eylemine sahiptir. Onu ücretsiz-katman veri-çıkış limiti etrafında tasarladım:

- **Paralel açılış, şelale yok.** Kuyruk, açılışta inceleyici-profili senkronuyla *paralel* yüklenir ve kabuk anında boyanır — tam ekran bir yükleme kapısı yoktur.
- **Sürümlenmiş yedekli tek-RPC kuyruğu.** `refreshQueue`, sade kartları + en son YZ yükünü + bu kullanıcının durumunu *tek* turda alır; o RPC henüz dağıtılmamışsa şeffaf biçimde üç-sorgulu eski yola düşer. Böylece uygulama backend sürümleri arasında çalışmaya devam eder.
- **Tembel kokpit + boşta katalog yükleme.** Ağır kokpit sorguları yalnızca bir kokpit sekmesine ilk girişte çalışır ve tüm gıda kataloğu, *tarayıcı boştayken* 1.000 satırlık partiler hâlinde çekilir — böylece hiçbiri ilk boyamayı engellemez.
- **Asla üzerine yazmayan YZ-ön doldurması.** Bir makalenin kayıtlı taslağı yoksa, YZ'nin normalize değerleri düzenlenebilir satırlara dönüştürülerek açılır; ama bir insan taslağı zaten varsa onu yüklerim ve insan işinin **asla** üzerine yazmam.
- **Doğrulanmış gönder/onayla yolları** ve her veritabanı yazımı **test-modu farkındadır** — test modunda Supabase'e dokunmak yerine yerel bir günlüğe ekler; böylece uygulama gerçek veriyi kirletmeden gösterilebilir.

**Zor kısım.** ~30 birbirine bağımlı state değerini orkestre etmek *ve* aynı anda katı bir veri-çıkış bütçesi içinde kalmak. "YZ ön doldurması bir insan taslağının asla üzerine yazmasın" kuralı basit gibi gelir ama her yükleme yolunu etkiler.

**Teknolojiler.** React 19 hook'ları, Supabase JS RPC'leri, `requestIdleCallback`, test-modu ara katmanı.

**Dosyalar & satırlar.** `pages/Annotate.jsx` (1.163), `utils/annotateHelpers.js` (574 — paylaşılan "beyin": yük normalizasyonu + kokpit hat hunisi), `views/QueueView.jsx` (227). **≈ 1.960 satır.**

---

### 4.2 PDF kanıt motoru — *tüm projedeki en zor kod parçası*

**Neden gerekli.** Bu, tüm doğrulama fikrinin kalbidir. YZ *"protein = 22,04 g/100 g"* dediğinde, insan bu sayıya güvenmek için onu **gerçek sayfada görebilmeli.** Ve veri girişini hızlandırmak için, *PDF tablolarının içindeki* besin adları **tıklanabilir** olmalı. Ama PDF'leri tarayıcıda okuyan kütüphane olan PDF.js, size yalnızca konumlanmış harflerin düz bir listesini verir: `{ metin, x, y, genişlik, yükseklik }`. **Tablo, sütun veya paragraf kavramı yoktur.** "Bu değerin geldiği tablo"yu vurgulamak için, önce **belgenin yapısını saf geometriden, tarayıcı içinde yeniden inşa etmem** gerekti.

**Nasıl yaptım.** `PdfTextScanner.js` yaklaşık **70 hesaplamalı geometri fonksiyonudur.** Sayfa başına hat şöyle: konumlanmış harfleri çıkar → uyarlanır metrikler hesapla → sütunları sapta → harfleri satırlara grupla → satırları parçalara böl → her parçayı sınıflandır → tabloları başlıklarından büyüt → paragraf blokları kur → ardından her YZ kanıt alıntısını sayfada bulan bir eşleştirici kademesi çalıştır.

**Dokuz zor alt-problemi** tek tek anlatacağım, çünkü birlikte bu alt-sistemi *oluşturuyorlar*:

1. **Uyarlanır metrikler.** Her eşik, sayfanın *kendi* tipografisinden türetilir (ortanca harf yüksekliği, ortanca satır boşluğu), her biri sınırlanmış. Aynı kod hem yoğun 7 punto bir tabloda hem de 12 punto bir özette çalışır — **hiçbir sabit piksel değeri yok.**
2. **Projeksiyon profiliyle sütun saptama.** Çok sütunlu dergiler iki sütunu tek bir "paragraf"a kaynaştırıyordu. Klasik bir **dikey projeksiyon profili** elle yazdım: x eksenini 2 puntoda kutula, dikey "oluk"ları bul (≥ 6 punto genişlikte, *her iki* tarafında içerik olan koşular) ve bir oluğu kesen satırları böl — böylece aynı yükseklikteki bir sol-sütun satırı ile bir sağ-sütun satırı asla kaynaşmaz.
3. **Parça başına tablo/düzyazı sınıflandırıcı.** Her metin parçası için bir özellik vektörü hesaplarım (sayısal token sayısı, "T1" gibi örnek kodlar, kısaltmalar, tümü-büyük-harf tokenlar, başlık önekleri, birimler, küme sayısı, cümle noktalaması…) ve bir tamsayı **`tableScore`** türetirim → `isTableLike`. Bu, harf-koşusu başına "bu bir tablo hücresi mi yoksa düzyazı mı?" kararını veren küçük, **elle yapılmış bir metin sınıflandırıcısıdır.**
4. **Başlık-çapalı tablo büyütme.** Tablolar başlıklarından bulunur ("Tablo 3 …"), sonra bölge satır satır **aşağı doğru** büyür, satırlar hizalı ve yakın kaldığı sürece. Önemli olan: bir veri satırı kabul edildikten sonra, "1,50" gibi tek bir hücre tek başına tablo olarak puan almasa bile sonraki veri satırları kabul edilmeye devam eder — çünkü *bağlam içinde* açıkça öyledir.
5. **Paragraf blokları + araya giren-veri birleştirme.** Düzyazı satırları paragraf olur, sonra ikinci bir geçiş, araya giren bir sayısal satırın böldüğü paragrafları **yeniden birleştirir** — bu yüzden paragrafın ortasında "22,04 ± 1,25 g/100 g" alıntılayan bir cümle yine tek bir temiz vurguya çözülür.
6. **MAD ile sağlam sütun kırpma.** PDF.js hâlâ iki sütunu kaynaştırdığında, **ortanca ve ortanca-mutlak-sapma (MAD)** ile kırparım — ders kitabı sağlam istatistiği — aykırı değerleri çitlerken meşru biçimde kısa son satırları atmadan.
7. **Kaynak-alıntı eşleştirici (3 kademeli).** YZ'nin tam alıntısını sayfada bulmak için: paragraf-eşleşmesi → arama-parçası eşleşmesi → satır-penceresi eşleşmesi, her biri yedekli; ve metni rakam↔harf sınırlarına boşluk ekleyerek normalize ederim, böylece "10.80g/100 g", "10.80 g/100 g" ile eşleşir.
8. **Yalan söyleyen `page_hint`.** YZ, *basılı* sayfa numarasını bildirir (örneğin 5 sayfalık bir ayrı-baskıda "1217"). İpucu gerçek sayfa sayısını aştığında onu **kapı tutmayan** hâle getiririm ve ipucunu yine de doğru PDF sayfasına eşlemek için **basılı-vs-PDF sayfa kaymalarının bir histogramını** kurarım.
9. **Kararlı, tekilleştirilmiş yer paylaşımları (union-find, iki kez).** Üst üste binen vurgu bölgelerini tek bir bölgeye toplamak için **yol sıkıştırmalı union-find** çalıştırırım; ve kaynak düzeyinde *ikinci* bir union-find, *aynı* paragrafa atıf yapan farklı YZ satırlarını birleştirir — böylece bir tablo hakkındaki üç satır tek bir temiz çip ve tek bir yer paylaşımı olur, ve yer paylaşımları yeniden çizimler arasında titremez.

Tarayıcının üzerinde, `PdfViewer.jsx` çizimi yapar: **kendi sunucumuzda barındırılan, paketlenmiş bir PDF.js worker'ı** (kritik yolda CDN bağımlılığı yok); her sayfanın metnini *tuvalini çizmeden* okuyan (tarayıcı boştayken devreden) **başsız bir kanıt taraması** — böylece vurguları önceden hesaplayabilir ve hangi sayfaların kanıt içerdiğini öğrenebilir; **kanıt-öncelikli çizim** (sayfa 1 + kanıt sayfaları önce boyanır, gerisi arkadan doldurur); PDF sınırlarını ekran piksellerine ölçekleyen ve Y eksenini ters çeviren **koordinat dönüşümü**; ve yalnızca saptanmış tabloların içine tıklanabilir besin işaretleri enjekte eden **özel bir metin çizici.**

**Zor kısım.** Hepsi — bu, *bir web tarayıcısında çalışan belge yerleşim analizidir*, sunucu yok, makine öğrenmesi modeli yok, **27 commit** boyunca gerçek dergi PDF'lerine karşı ayarlanmış. Dürüstçe, projedeki tek en zor kod parçasıdır — frontend ya da backend.

**Teknolojiler.** PDF.js / react-pdf, tarayıcı metin-katmanı geometrisi, projeksiyon profilleri, sağlam istatistik (MAD), union-find, `requestIdleCallback`, özel metin çiziciler.

**Dosyalar & satırlar.** `utils/PdfTextScanner.js` (**2.323**), `components/PdfViewer.jsx` (939), `utils/EvidenceLocations.js` (439). Bu davranışı kilitleyen test paketini de yazdım: `PdfTextScanner.test.js` (655), `EvidenceLocations.test.js` (225), `evidenceStatusCache.test.js` (92) — **972 satır test.** **≈ 3.700 satır motor + ~970 satır test.**

---

### 4.3 Kalıcı önbellek katmanları

**Neden gerekli.** Bu alandaki PDF'ler büyüktür (genelde 10–25 MB) ve iki şey bariz yaklaşımı bozar: tarayıcının normal HTTP önbelleği bu büyüklükteki dosyaları **atar** ve Supabase onları `no-cache` ile sunar. Bir PDF'in yapısını her açılışta yeniden taramak da yavaştır. Bu yüzden kalıcı, anlık ve *inceleyiciler arasında paylaşılan* bir önbelleğe ihtiyacım vardı.

**Nasıl yaptım.** Üç katman:

- **PDF baytları**, URL ile anahtarlanmış olarak **Cache Storage API**'sinde (uçucu HTTP önbelleğinde değil), **localStorage'da bir LRU indeksiyle** (üst sınır 40) saklanır. PDF.js'e her seferinde taze bir `ArrayBuffer` veririm (aktarımda buffer'ları ayırır) ve **sonraki iki kuyruk makalesini boştayken önceden çekerim** — böylece sonraki makale anında açılır.
- **Çözümlenmiş kanıt konumları** (her değerin hangi bölgeye vurgulandığı) **makale başına, hem yerel** (localStorage LRU) **hem de uzakta** bir Supabase tablosunda bir RPC aracılığıyla önbelleğe alınır. Böylece *herhangi biri* daha önce incelenmiş bir makaleyi yeniden açtığında, yer paylaşımları **tarama daha bitmeden önbellekten** boyanır.

**Zor kısım.** HTTP önbelleğinin bu dosyaları hiç tutmayacağını fark etmek ve PDF.js'i ikinci okumada sessizce bozan `ArrayBuffer`-ayrılma hatası.

**Teknolojiler.** Cache Storage API, localStorage LRU, bir Supabase tekilleştirme tablosu + RPC.

**Dosyalar & satırlar.** `utils/pdfCache.js` (107), `utils/evidenceStatusCache.js` (139), `utils/evidenceDedupStorage.js` (44), `hooks/useEvidenceStatusCache.js` (101). **≈ 390 satır.**

---

### 4.4 Alana özel otomatik tamamlama

**Neden gerekli.** Bir etiketleyici serbest metinle bir gıda veya besin adı yazar ("elma", "c vitamini") ve bu, **kanonik USDA katalog girdisine** eşlenmeli — bağışlayıcı biçimde (yazım hataları, çoğullar, kısmi adlar) ama **güvensiz aşırı-eşleşme olmadan** ("elma" yazınca *Elma, çiğ* çıkmalı, *Elma suyu, konserve* değil).

**Nasıl yaptım.** Her girdinin kanonik adı, taban adı ve takma adları üzerinde, Huan'ın yazdığı bulanık-eşleşme ilkelinin üstüne, **ağırlıklı bir puanlama sıralayıcısı** kurdum. `scoreFoodMatch`; tam/önek/ilk-token isabetlerini ayarlı ağırlıklarla ödüllendirir, token başına ilişkileri puanlar (tam / kök / düzenleme-mesafesi) ve **bütün-gıda ayrıştırması** ekler: işleme sözcüklerini ("konserve", "kurutulmuş"), bebek-maması/restoran girdilerini ve türetilmiş-önek sahte dostlarını cezalandırırken bütün-gıda ipuçlarını ödüllendirir — böylece genel sorgular çiğ bütün gıdayı öne çıkarır. Yararlı örtüşmesi olmayan bir sorgu sert biçimde reddedilir. Bellek-içi katalog yüklenmeden önce **iki-sorgulu bir Supabase stratejisi** çalıştırır (önek + geniş `ilike`); sonrasında yerel olarak sıralar. 250 ms geciktirmeli, tam klavye gezinmeli, blur/Enter'da özel-gıda girişli; ve her çözümleme bir `search_sessions` telemetri tablosuna kaydedilir (tablo yoksa kendini devre dışı bırakır).

**Zor kısım.** Sıralama ağırlıkları — "elma"nın, birbirine çok yakın binlerce girdilik bir katalogda, asla sessizce yanlış bir gıda seçmeden, doğru bütün gıdayı güvenilir biçimde öne çıkarmasını sağlamak.

**Teknolojiler.** React, Supabase katalog sorguları, bellek-içi ağırlıklı sıralama, geciktirme, arama-oturumu telemetrisi ve düşük seviyeli ilkel olarak Huan'ın `fuzzyMatch` motoru.
*(Dürüst atıf: bulanık tokenizer/çekim/Levenshtein ilkeli Huan'ındır; alana özel puanlayıcı, bütün-gıda ayrıştırması, veri-yükleme stratejisi ve kullanıcı deneyimi benimdir.)*

**Dosyalar & satırlar.** `components/FoodAutocomplete.jsx` (664), `components/NutrientAutocomplete.jsx` (334), `utils/searchSessionLogger.js` (110). **≈ 1.110 satır.**

---

### 4.5 Tıklanabilir PDF → editör köprüsü

**Neden gerekli.** Tablo besinlerini tıklanabilir yapmanın getirisi şudur: sayfadaki bir tıklama **bir değeri doğrudan editöre düşürmeli** — etiketlemeyi hızlı yapan budur.

**Nasıl yaptım.** PDF'teki vurgulu bir besine tıklamak `NutrientPopover`'ı açar; bu, kendini **görünüm-alanına duyarlı** konumlandırır (çapanın altında, ekrana sıkıştırılmış, yer yoksa üste çevrilmiş), değer girişine odaklanır, Escape/dışına-tıklamada kapanır ve ilk gıda öğesine eklenen (tekilleştirilmiş) bir besin satırı yayar. `FoodItemForm`; gıda otomatik tamamlamasını, dinamik besin satırlarını ve besin otomatik tamamlamasını tek bir gıda kartında birleştirir.

**Zor kısım.** Üst üste binen PDF metin katmanları boyunca güvenilir tıklama çözümlemesi ve asla ekrandan düşmeyen popover konumlandırması.

**Teknolojiler.** React, görünüm-alanı geometri matematiği, 4.2'deki PDF metin-katmanı tıklama çözümlemesi.

**Dosyalar & satırlar.** `components/NutrientPopover.jsx` (128), `components/FoodItemForm.jsx` (110). **≈ 240 satır.**

---

### 4.6 Kokpit & iş akışı görünümleri

**Neden gerekli.** Etiketleyicinin çalışma alanının ötesinde, sistem; **onay** (bir inceleyici gerçeği düzeltir ve kesinleştirir), **panolar** (her etiketleyici nasıl performans gösteriyor?), bir **faydalı-makaleler genel bakışı** ve tüm tarama→YZ→insan akışını görselleştiren bir **hat hunisi** gerektirir. Bunlar, eskiden tek bir devasa dosya olan şeyden sekiz odaklı görünüme ayrıştırıldı.

**Nasıl yaptım.**
- **`ApprovalView`** — yan yana: orijinal etiketleyici gönderisi vs. **düzenlenebilir** inceleyici-nihai yükü, bir karar ve notla (onaylayıcılara kapılı; diğer herkese salt-okunur önizleme).
- **`DashboardView`** — gönderilerden ve onaylardan **istemci tarafında** hesaplanan etiketleyici-performans metrikleri (gönderilen / bekleyen / kabul edilen / düzeltilen / geçersizleşen, artı gönderi başına "hata detayı" tablosu).
- **`AllPapersView`** ("Faydalı Makaleler") — yönlendirme / YZ / gönderi / sonuç tablosu, güveni, kabul edilen satırları, red-nedeni histogramını ve normalize JSON'u gösteren genişletilebilir bir **YZ detay paneliyle** — yani *normalizasyon özeti*, kasıtlı olarak modelin ham muhakemesi **değil.**
- **`PipelineOpsView`** — 10-aşamalı huniyi (arama → filtre → yükleme → küçük/orta/güçlü → insan) korunan/düşen sayılarıyla çubuklar hâlinde, artı canlı bir "Şu An" ızgarasıyla çizer.

**Zor kısım.** Güvenilir performans ve huni metriklerini, değiştirilemez gönderi/onay kayıtlarından tamamen istemcide hesaplamak — bir aşamanın yanlışlıkla sıfır okunmaması için eski-veri tamamlaması dâhil.

**Teknolojiler.** React görünümleri, istemci-tarafı toplama, Supabase okumaları.

**Dosyalar & satırlar.** `ApprovalView.jsx` (199), `DashboardView.jsx` (171), `PipelineOpsView.jsx` (162), `AllPapersView.jsx` (140), artı destekleyici `AiDetailPanel.jsx` (118), `EvidenceStrip.jsx` (54), `PayloadSummary.jsx` (49) ve `ReviewerAdminView` / `SuggestionsReviewView` / `MySuggestionsView`. **Görünümler genelinde ≈ 1.100 satır.**

---

### 4.7 Uygulama kabuğu, kimlik doğrulama & tema

**Neden gerekli.** Bir şeyin oturumu kontrol etmesi, kullanıcıyı giriş / parola-sıfırlama / uygulamaya yönlendirmesi ve her şeye tema vermesi gerekir.

**Nasıl yaptım.** `App.jsx` Supabase oturumunu kontrol eder, bir parola-kurtarma URL'sini saptar ve sıfırlama sayfasına, aksi hâlde girişe, aksi hâlde etiketleyiciye yönlendirir. `Login.jsx` e-posta/parola ve **Google OAuth** yapar. `useTheme`, işletim sistemi temasının üstüne bir geçersiz-kılma çözer, `prefers-color-scheme`'i dinler, temayı yanlış-tema-parıltısı olmadan yazar ve bir geçersiz-kılmayı yalnızca sistemden farklıysa kalıcılaştırır — böylece uygulama varsayılan olarak işletim sistemini izler.

**Dürüst atıf.** Kabuk ve giriş akışı benimdir; **sonraki tema *merkezileştirmesi* ve parola-sıfırlama *düzeltmesi* Huan'ın** bunun üstüne katkılarıydı.

**Teknolojiler.** Supabase Auth, React, `matchMedia`, `sessionStorage`, `useLayoutEffect`.

**Dosyalar & satırlar.** `App.jsx` (96), `hooks/useTheme.js` (75), `pages/Login.jsx`. **≈ 250 satır.**

---

## 5. Bitiş özeti

OpenNutri'nin **tüm frontend'ini** kurdum — tüm projenin dayandığı doğrulama enstrümanını. Rakamlarla:

- **~14.100 satır** güncel frontend kodu; **10.334 satır** ana kuyruk, PDF, otomatik tamamlama ve görünüm dosyalarında yoğunlaşmış; artı en zor davranışı kilitleyen **~970 satır test.**
- **Tek başına PDF kanıt motoru ~4.050 satırdır** — *bir web tarayıcısında çalışan belge yerleşim analizi* — projeksiyon-profili sütun saptama, uyarlanır parça-başına tablo sınıflandırıcı, başlık-çapalı tablo büyütme, MAD-sağlam sütun kırpma, yalan söyleyen bir sayfa numarasından sağ çıkan üç-kademeli alıntı eşleştirici ve union-find tekilleştirme — **27 commit** boyunca rafine edildi. Ekibin kendi değerlendirmesine göre, **tüm projedeki tek en zor kod parçasıdır — frontend ya da backend.**

Ve bu bir prototip değil. **Vercel'de yayında**, **tamamen istemci tarafında** sunucu turu olmadan çalışır, **keyfi yayıncı PDF'leri** üzerinde işler, paralel açılış, tek-RPC yükleme, boşta katalog yükleme ve kalıcı paylaşımlı önbellekleme sayesinde **ücretsiz-katman veri bütçesi** içinde kalır ve **önce-kesinlik** ilkesini benimser — yanlış bir şeyi vurgulamaktansa hiçbir şeyi vurgulamamayı tercih eder, çünkü bir besin etiketindeki yanlış bir sayı, hiç sayı olmamasından daha kötüdür.

Backend makaleleri bulabilir ve YZ sayılar önerebilir, ama **bunların hiçbiri, bir insan onu benim ekranımda onaylayana kadar güvenilir veri olmaz.** Benim frontend'im, bir yığın PDF'i ve YZ tahminini bir beslenme uzmanının gerçekten inanabileceği bir şeye dönüştüren şeydir — ve bunu, bütün gün kullanılabilecek kadar hızlı yapar.

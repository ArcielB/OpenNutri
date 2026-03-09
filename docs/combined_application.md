# 1. ULUSAL KAZANIM ve PROJENİN ÖNEMİ
**(NATIONAL GAIN AND IMPORTANCE OF THE PROJECT)**

---

## Current Problem and Need

The global nutritional data infrastructure is currently stuck in a manual, labor-intensive bottleneck. Major institutions (USDA, EFSA) rely on human experts to manually transcribe data from literature. Due to limited resources, these institutions prioritize global commodities and systematically exclude "niche" data, including the vast majority of Turkish agricultural research.

Consequently, the entire Turkish food ecosystem—from researchers and exporters to public health bodies—is constrained by this inefficiency:

- Our national scientific output remains inaccessible in unstructured PDF archives, invisible to global standard-setters
- Turkey's national database, **TürKomp**, established a critical high-quality foundation with ~500 analyzed foods, but core data collection was largely discontinued after 2014 [CITATION_NEEDED]. Because it relied exclusively on manual laboratory analysis, scaling it to encompass the country's vast agricultural diversity remains financially prohibitive.
- Turkish institutions are forced to pay high licensing fees to access foreign databases (USDA, NCCDB, Nutritionix) — a direct technological foreign dependency (*teknolojik dışa bağımlılık*)
- Turkish food exporters struggle to provide accurate, verified nutritional labeling required for EU compliance

> [!IMPORTANT]
> Preliminary analysis indicates that **[TURKISH_FOOD_GAP_COUNT]** distinctly Turkish food items present in academic literature are absent from both USDA and EFSA databases (see Section 4.6.2).

---

## The Solution: OpenNutri

We are proposing a globally novel **Progressively Autonomous Data Verification System**. Unlike existing international systems that rely on slow manual entry, OpenNutri pioneers a **"Hybrid Intelligence" pipeline** (AI Extraction + Food Science Logic + Expert Reinforcement) to create the world's first progressively autonomous, self-correcting nutritional database designed for national-scale indexing.

---

## National Gains by Sector

### 1.1. For Food Exporters: Eliminating Costly Lab Analysis for Export Compliance

Currently, Turkish exporters often face a choice: pay high fees for private lab analysis (~$200/sample [CITATION_NEEDED]) or risk EU border rejection by using generic foreign data.

| | |
|:---|:---|
| **The Gain** | OpenNutri provides a verified, citation-backed reference standard for Turkish products (e.g., Antep Pistachios, local wheat varieties). |
| **The Impact** | Eliminates per-sample lab costs, allowing producers to meet EU Regulation 1169/2011 and Green Deal traceability standards using verified database records, directly increasing price competitiveness of Turkish exports. |

---

### 1.2. For the Digital Ecosystem: National Data Infrastructure for Health-Tech

Turkish health-tech startups and dietitians are currently blocked by a lack of infrastructure. Global databases are either very limited in scope (USDA) or prohibitively expensive for startups to license (NCCDB, Nutritionix), and virtually all exclude key Turkish foods.

| | |
|:---|:---|
| **The Gain** | OpenNutri provides the national data infrastructure (API) that this sector currently lacks. |
| **The Impact** | Enables domestic developers to outcompete global giants in the regional market by offering superior accuracy for local diets (Simit, Lahmacun)—a key differentiator that foreign algorithms cannot match. |

---

### 1.3. For Public Health: Evidence-Based Dietary Policy

Effective policy against obesity and Non-Communicable Diseases (Diabetes, Hypertension) requires knowing what nutrients Turkish foods actually contain — but this data is scattered across thousands of unstructured research papers.

| | |
|:---|:---|
| **The Gain** | OpenNutri provides a comprehensive, verified nutritional reference for Turkish foods based on published scientific research, covering foods and nutrients absent from existing databases. |
| **The Impact** | Enables evidence-based dietary guidelines and public health interventions grounded in actual compositional data for Turkish foods, rather than estimates derived from foreign databases. |

---

### 1.4. For Researchers: Making Turkish Science Part of the Global Standard

Turkish food science researchers publish extensively, but their compositional data remains buried in unstructured PDFs that no international database indexes. OpenNutri extracts this data into a standardized database where every record links to its source paper via DOI — enabling researchers worldwide to discover, use, and cite the original Turkish work.

| | |
|:---|:---|
| **The Gain** | OpenNutri automatically extracts nutritional data from all scientific literature — including Turkish-language research currently inaccessible in unstructured PDF archives. |
| **The Impact** | As a comprehensive, superior dataset, Turkish research enters the global standard by default — increasing national citation rates and scientific influence. |

---

### 1.5. Economic Transformation: From Data Importer to Exporter

Turkey currently imports all of its structured nutritional data from foreign institutions and pays licensing fees to access it. OpenNutri reverses this flow.

| | |
|:---|:---|
| **The Gain** | Instead of paying to import foreign data, Turkey becomes a dual-channel exporter. |
| **The Impact** | Revenue from two high-value assets: **(1)** Licensing verified nutritional datasets to global food conglomerates. **(2)** Licensing the Verification Engine itself to other nations who want to digitize their own food systems. |


\newpage

# 2. AMAÇ VE HEDEFLER
**(OBJECTIVES AND GOALS)**

---

## 2.1. Project Aim

The aim of this project is to develop **OpenNutri** — a Progressively Autonomous Nutritional Data Verification System that creates Turkey's first sovereign national food composition infrastructure. OpenNutri uses a novel "Hybrid Intelligence" approach — combining AI-driven extraction, food science validation logic, and expert reinforcement learning (RLHF) — to automatically extract, validate, and standardize nutritional data from global scientific literature at scale, resulting in a verified nutritional database, a production API, and a licensable extraction engine — the infrastructure necessary to deliver the national gains identified in Section 1.

---

## 2.2. Measurable Objectives

### Objective 1: Develop the Hybrid Intelligence Extraction Engine

Build an end-to-end AI pipeline that takes scientific papers as input and outputs structured, validated nutritional data. The system will combine:

- Advanced Language Models (e.g., fine-tuned open-source or prompt-engineered commercial models)
- Retrieval-Augmented Generation (RAG) for cross-referencing against known standards
- Food science validation rules designed by domain experts

**Success Metrics:**

| Metric | Baseline (GPT-4o) | Target (Initial OpenNutri) |
|:---|:---|:---|
| Auto-approved accuracy | N/A (no verification pipeline) | ≥ [INITIAL_AA_ACCURACY] % |
| Auto-approval rate | N/A (no confidence scoring) | ≥ [INITIAL_AUTO_APPROVAL] % |
| Database error rate | N/A (no systematic audit) | < 0.5% |
| Cost per paper | ~$0.10 | <$0.03 |

> [!NOTE]
> Baseline values from preliminary work (see Section 4). GPT-4o selected as baseline due to its position as the industry-leading model with >60% market share.

---

### Objective 2: Process Large-Scale Scientific Literature

Automatically discover, filter, and analyze nutritional research papers from major scientific databases (PubMed Central, DergiPark, Google Scholar) in both English and Turkish.

**Success Metrics:**
- Process ≥100,000 relevant papers from global scientific databases to extract ≥500,000 food-nutrient records (~5 records per relevant paper)
- Index ≥5,000 uniquely Turkish food items currently absent from international databases (USDA, EFSA)

---

### Objective 3: Build Expert-Verified Gold Standard Dataset

Create a high-quality, citation-backed nutritional database through systematic expert verification, serving both as the core product and as training data for model improvement.

**Success Metrics:**
- Generate ≥25,000 expert-verified gold-standard food-nutrient records through systematic human verification
- Cover up to 181 core nutrients (where available in source text) tracked by international standards
- Final database error rate: <0.5%

---

### Objective 4: Train Improved Models Using Expert Feedback (RLHF)

Use the expert-verified dataset to continuously improve the AI extraction models through Reinforcement Learning from Human Feedback (RLHF), creating a self-improving system.

**Success Metrics:**

| Metric | Before RLHF (Initial) | After RLHF (Final) |
|:---|:---|:---|
| Auto-approved accuracy | [INITIAL_AA_ACCURACY] % | ≥ 99.5% |
| Auto-approval rate | [INITIAL_AUTO_APPROVAL] % | ≥ 90% |
| Database error rate | < 0.5% | < 0.5% |
| Cost per paper | ~$0.03 | <$0.01 |

> [!TIP]
> **Auto-approved accuracy** = of records the system accepts without human review, what % are correct (measured by periodic random audit).
> **Auto-approval rate** = what % of papers bypass human review entirely.
> The <0.5% database error target is a hard constraint maintained across both auto-approved and human-verified records.

---

### Objective 5: System Deployment and Scientific Dissemination

Deploy the complete OpenNutri infrastructure for public use and validate scientific contribution through publication.

**Success Metrics:**
- Production REST API deployed with <200ms response time and ≥100 concurrent requests/second capacity
- Complete developer documentation and SDK published
- Dual licensing model implemented (free academic access / commercial licensing)
- Open-access dataset released publicly with full documentation
- System performance benchmark report published (accuracy, cost, speed vs GPT-4o baseline)
- ≥3 peer-reviewed academic publications submitted

---

## 2.3. Objectives Summary Table

| No. | Objective | Key Success Metrics |
|:---|:---|:---|
| 1 | Hybrid Intelligence Engine | ≥99.5% auto-approved accuracy, [TARGET_COST_REDUCTION]% cost reduction vs. GPT-4o (Section 4.6.3) |
| 2 | Literature Processing | ≥500k food-nutrient records, ≥5k uniquely Turkish food items |
| 3 | Gold Standard Dataset | ≥25,000 expert-verified records, 181 nutrients, <0.5% error |
| 4 | RLHF Training | ≥90% auto-approval, <$0.01/paper |
| 5 | Deployment & Dissemination | API live, dataset released, benchmark published, ≥3 papers submitted |

---

> [!WARNING]
> **Placeholders to Fill (Remove before final submission)**
>
> Fill these after running the preliminary benchmark on 200 papers:
>
> | Placeholder | Description | Example Value |
> |:---|:---|:---|
> | `[INITIAL_AA_ACCURACY]` | Initial auto-approved accuracy (% of auto-approved records that are correct) | 95 |
> | `[INITIAL_AUTO_APPROVAL]` | Initial auto-approval rate (% of papers not needing human review) | 60 |
>
> **Suggested progression:** Initial: ~95% auto-approved accuracy, ~60% auto-approval → Final (after RLHF): ≥99.5% auto-approved accuracy, ≥90% auto-approval, <$0.01/paper


\newpage

# 3. PATENT, FAYDALI MODEL, TESCİL TARAMASI, YENİLİKÇİ YÖNÜ VE TİCARİLEŞME POTANSİYELİ

---

## a) Patent, Utility Model, and Registration Searches

Searches were conducted across three databases:
- **TURKPATENT** (tpe.gov.tr) — Turkish keywords: *"gida kompozisyon veritabani", "besin degeri yapay zeka", "otomatik gida analizi"*
- **Espacenet** (worldwide.espacenet.com) and **Google Patents** (patents.google.com) — English keywords: *"food composition database" + "artificial intelligence", "nutritional data extraction" + "NLP", "cascade model" + "LLM routing", "food ontology" + "automated construction"*

**Results:** No relevant patents, utility models, or registrations were found in the Turkish national database. TürKomp (Turkey's existing food composition database, developed under TÜBİTAK KAMAG 1007, 2008-2013) is held as institutional IP by TÜBİTAK without a registered patent.

### International Search Results

| Patent / System | Description | Difference from OpenNutri |
|:---|:---|:---|
| **US20190295440A1** | Food analysis & health recommendations. Builds a food ontology from web-crawled data using ML/NLP; generates personalized health recommendations via cloud systems. | Consumer recommendation platform. Does not extract compositional data from scientific literature. No verification cascade. Different input (web data) and output (recommendations). |
| **US9286290B2, CN110532834A, WO2025107898A1** | Generic table extraction. Domain-agnostic tools extracting tabular structures from documents using NLP and layout analysis. | No food science domain knowledge, no nutritional constraint verification, no cost-optimized routing. OpenNutri's innovation is the cascade verification architecture, not table extraction per se. |
| **FoodMine** (Hooton et al., Scientific Reports, 2020) *[Academic - NOT patented]* | NLP algorithm mining PubMed for chemical composition of foods. Piloted on garlic and cocoa only. | Extracts chemical compounds (flavonoids, phenolics), NOT standard nutritional composition (macros, vitamins, minerals/100g). Single-model pipeline. No verification cascade, no RLHF, no Turkish support. Only 2 food categories. |

**Commercial competitors:** Edamam, FatSecret, and Nutritionix protect platforms via trade secrets and licensing (no patents found). None extract food composition data from scientific literature — they use licensed government data (USDA), crowdsourcing, and NLP for label/recipe parsing.

### No Existing Patents Identified For:

1. Progressively autonomous food composition extraction from scientific literature using LLMs
2. Cascaded multi-layer AI verification architectures for nutritional data
3. Learned routing for cost-optimized scientific data extraction
4. RLHF-driven cross-layer learning for data curation
5. Any system targeting Turkish food composition data extraction from literature

> **Conclusion:** The proposed project does not infringe upon any identified third-party intellectual or industrial property rights.

---

## b) Innovative Aspects of the Project

OpenNutri introduces **five interconnected innovations** that, taken together, constitute a fundamentally new approach to food composition data infrastructure. No existing system — commercial, academic, or governmental — combines these capabilities.

| No. | Innovation | What It Is | Why It Is New |
|:---|:---|:---|:---|
| 1 | **Progressively autonomous extraction from scientific literature** | End-to-end AI pipeline: scientific papers → structured, validated nutritional composition data (energy, macronutrients, vitamins, minerals per 100g) conforming to international standards. | All existing databases (USDA, EFSA, TürKomp) rely on manual lab analysis and expert curation. FoodMine (Hooton et al. 2020) extracts chemical compounds, not standard nutritional composition. |
| 2 | **Cascaded Hybrid Intelligence architecture (L1–L5)** | Five-layer verification cascade where each layer applies progressively more capable (and expensive) AI models, each verifying previous layer output. | Existing systems use single-model pipelines. FrugalGPT cascades for cost reduction only. OpenNutri's cascade has dual function (cost optimization + multi-layer verification) — no precedent. |
| 3 | **Self-improving Learned Router** | Trainable meta-classifier predicting document complexity and routing to the appropriate extraction layer. Target: [TARGET_COST_REDUCTION]% cost reduction vs. GPT-4o (Section 4.6.3). | Static model cascading (FrugalGPT) uses fixed confidence thresholds. OpenNutri's router is a learned classifier that improves as more documents are processed. The system becomes cheaper over time. |
| 4 | **Cross-layer learning with RLHF** | Expert corrections at higher layers (L4–L5) generate training signal that flows back to improve lower layers (L1–L3). Target: auto-approval rate from ~60% to ~90%. | RLHF is widely used for chatbot alignment. Applying it to structured data extraction — where expert corrections directly retrain extraction models — is novel. Transforms verification from cost center into training investment. |
| 5 | **DOI-level provenance + Turkish food coverage** | Every nutritional record linked to its source publication via DOI. Specifically targets Turkish-language literature and Turkish food items absent from international databases. | No existing food composition database provides machine-readable source traceability at the individual record level. Existing databases (USDA, EFSA, TürKomp) cite sources at the food-item level, not at the individual nutrient-value level. An estimated 5,000+ Turkish food items are absent from international databases. |

> [!NOTE]
> **Additional methodological innovation:** OpenNutri introduces domain-specific validation beyond standard NLP metrics (precision, recall, F1). The system validates extracted data against food science constraints: energy-macronutrient balance (Atwater factors), physiologically plausible ranges, and cross-reference consistency. This has no precedent in the AI-for-science literature.

---

## c) Commercialization Potential

OpenNutri produces **two independently commercializable outputs:**

| No. | Output | Description | Revenue Model |
|:---|:---|:---|:---|
| 1 | **Food composition database** | 500,000+ food-nutrient data points at 99.5%+ accuracy. Scales at orders of magnitude lower cost than manual databases, and that cost decreases over time. | Tiered API access (paid, scaled by volume). Free academic access with monthly updates. |
| 2 | **Cascaded Hybrid Intelligence verification engine** | The extraction + verification pipeline itself — licensable technology for building national food composition databases or expanding to new domains. | Engine licensing (per-country or per-domain). Adaptation and deployment services. |

**No direct competitor exists.** Commercial food data providers (Edamam, FatSecret, Nutritionix) aggregate and resell existing government data (USDA, EFSA). None generate new data from scientific literature.

### Market Growth

- **For the database:** Digital health platforms, nutrition apps, and personalized dietary services are creating unprecedented demand. TürKomp has not been systematically updated since 2014 — a decade-long data deficit for an industry exporting over $27B annually.
- **For the engine:** FAO/INFOODS actively promotes national food composition programs, but most countries lack resources for manual database construction. An AI-driven engine that drops this cost by two orders of magnitude addresses a growing, unmet global need.

**Data independence as value proposition:** Most countries currently depend on USDA or EFSA for food composition reference data — databases that do not cover local foods, operate on foreign update schedules, and prioritize foods relevant to their own populations. The ability to build a sovereign, locally controlled food composition database is the engine's primary value proposition for international licensing.

### Post-Project Cost Estimate (Olası Maliyet Hesabı)

The computationally expensive phases (model training, RLHF, expert verification) are completed during the funded project period. Post-project, all inference and hosting runs on hardware acquired through this grant (GPU server, NAS storage).

| Post-Project Recurring Item | Estimated Annual Cost |
|:---|:---|
| Cloud backup (~3 TB) | ~6,000 TL |
| Software tools / monitoring | ~2,000 TL |
| Commercial API fallback (L4, ~5% of new papers) | ~1,000 TL |
| Domain, SSL, miscellaneous | ~500 TL |
| Storage expansion (additional drives) | ~3,000 TL |
| **Total** | **~12,500 TL/year** |

Power, network, and physical infrastructure are provided by the host institution. Upon commercial transition (Section 6.3), equivalent infrastructure is provisioned as a one-time investment from TÜBİTAK 1812 BİGG seed funding.

**Planned commercialization pathway:** Detailed in Section 6.3 (pilot partnerships → spin-off via TÜBİTAK 1812 BİGG + KOSGEB → scaling via TEYDEB 1507/1505).


\newpage

# 4. YÖNTEM (METHOD) — Part A: Architecture & Layers

> [!NOTE]
> Section 4 is split into **two parts** for readability.
> - **Part A** (this file): Research Design Overview, System Architecture (L1–L5), Learned Router, Cross-Layer Learning (§4.1–4.4)
> - **Part B**: Data Collection, Preliminary Work, Variables & Statistics, WP Mapping (§4.5–4.8)

---

## 4.1. Research Design Overview

This project develops a **Cascaded Hybrid Intelligence Pipeline** — an architecture that advances beyond existing food composition digitization approaches, which remain dependent on manual expert curation (USDA FoodData Central, EFSA Comprehensive Database, TürKomp). The system comprises:

- **Five processing layers (L1–L5)** of increasing capability and cost
- **A Learned Router** that directs each document to the cheapest layer capable of handling it
- **A Cross-Layer Learning mechanism** through which verification outcomes from higher layers continuously retrain all lower layers

Together, these create a **self-improving system** whose per-paper processing cost decreases over the project lifetime. The architecture synthesizes four established paradigms:

| Paradigm | Key References |
|:---|:---|
| **Cascade classifiers** — route inputs through progressively more expensive models | Viola & Jones, 2001; Wang et al., 2011; Chen et al., 2023; Yue et al., 2024 |
| **Mixture-of-Experts (MoE) routing** — gating network selects specialized sub-models per input | Shazeer et al., 2017; Fedus et al., 2022 |
| **RLHF** — aligning language model outputs with expert judgment | Ouyang et al., 2022 |
| **Active learning** — cost-efficient annotation, prioritizing uncertain samples for human review | Settles, 2012 |

**The novelty** lies not in any single paradigm but in their integration into a domain-specific cascade where each layer's output systematically improves every preceding layer, and where a learned cost-optimization router replaces the static thresholds used in prior cascade work.

This design directly enables the measurable objectives:
- Processing 100,000+ papers (Obj. 2) becomes financially viable because the cascade drives per-paper cost below $0.03 (Obj. 1)
- The 25,000+ gold-standard records (Obj. 3) are simultaneously the product deliverable and the training fuel that pushes auto-approval above 90% while maintaining <0.5% database error (Obj. 4)

> [!IMPORTANT]
> **Figure 1: System Architecture Diagram** — INSERT a visual showing the L1→L5 cascade with the Learned Router as a side controller, feedback arrows flowing from higher layers to all lower layers, and the production database as the final output.

The project proceeds in five research phases aligned with the work packages defined in Section 5.1.

---

## 4.2. System Architecture: Cascaded Hybrid Intelligence

Each candidate paper enters at L1 and progresses to higher layers only if the current layer cannot produce an output with sufficient confidence. The vast majority of papers are handled by fast, inexpensive lower layers; difficult or ambiguous cases escalate to more capable — and more costly — layers.

### 4.2.1. Layer 1 — Intelligent Literature Crawler (Discovery)

**Purpose:** Systematically discover scientific papers likely to contain food composition data from major databases (PubMed Central, DergiPark, Crossref, Google Scholar).

**Method:**
- Initial query set constructed by domain experts using controlled vocabulary from established food composition ontologies (LanguaL, FoodOn; Møller et al., 2008; Dooley et al., 2018) and MeSH terms
- Crawler executes broad Boolean searches, retrieves metadata and abstracts, stores results in a candidate pool
- Relevance feedback loop refines query terms over time using a lightweight bandit algorithm (Thompson Sampling; Chapelle & Li, 2011)
- Both English and Turkish language papers targeted. Scopus queried for broader coverage (institutional access via EKUAL), OpenAlex (free, open API) used for deduplication and citation graph traversal

| Output | Feedback From |
|:---|:---|
| Continuously growing corpus of candidate papers (metadata + full text where available) | L2 (binary relevance labels), L3–L5 (confirmed food composition content) |

**Objective linkage:** Directly serves Objective 2 (process ≥100,000 relevant papers) and Objective 3 (index ≥5,000 uniquely Turkish food items).

---

### 4.2.2. Layer 2 — Lightweight Paper Classifier (Filtering)

**Purpose:** Rapidly classify each candidate paper as "contains food composition data" or "irrelevant," using minimal computational resources.

**Method:**
- Small language model (e.g., DistilBERT or fine-tuned BERT-Tiny; Sanh et al., 2019; Turc et al., 2019) trained on binary classification using title, abstract, and section headings
- **Positive examples:** Papers identified via established keyword patterns (e.g., "proximate composition," "g/100g") and papers citing USDA, EFSA, or TürKomp standards
- **Negative examples:** Papers from the same journals that do not contain compositional data
- Papers above confidence threshold → L3; papers below → discarded
- Downstream outcomes fed back as additional training labels
- Model retraining on regular cadence (initially bi-weekly)

**Output:** Filtered corpus with confidence scores. **Target:** ≥0.92 F1 after iterative refinement.

---

### 4.2.3. Layer 3 — Fine-Tuned Open-Source Extraction Models (Core Extraction)

**Purpose:** The primary extraction engine and **central scientific contribution**. Converts unstructured paper content into structured food-nutrient records.

**Method — Modular design decomposing extraction into specialized sub-tasks:**

| Sub-Task | Description | Model Type |
|:---|:---|:---|
| Table Detection & Parsing | Locating and extracting tabular data from PDFs | Vision-language model or Table Transformer (Smock et al., 2022) |
| Table Semantic Interpretation | Understanding headers, units, footnotes, mapping to nutrient codes | Fine-tuned LLM with LoRA (Hu et al., 2022) |
| Context Extraction | Extracting food IDs, preparation methods, sample origins from text | Fine-tuned LLM with LoRA |
| Unit Normalization | Standardizing units (mg/100g, %, ppm, µg/serving) to canonical format | Rule-based engine + lightweight ML fallback |
| Entity Linking | Mapping food names to standardized identifiers (LanguaL, FoodEx2) | Embedding-based similarity search + classifier |

Within L3, models are organized into sub-tiers of increasing size. The Learned Router selects the cheapest sub-tier per sub-task. Models are initially fine-tuned on the preliminary benchmark dataset (Section 4.6.3) using parameter-efficient methods (LoRA, QLoRA; Hu et al., 2022; Dettmers et al., 2023), then continuously improved as L4/L5 verified outputs become additional training data.

**Output:** Structured food-nutrient records with per-field confidence scores and extraction provenance.

**Validation rules** (designed with Prof. Dr. Servet Gülüm Sumnu, Araştırmacı):
- Macronutrient sum constraint: protein + fat + carbs + moisture + ash ≈ 100g/100g (FAO/INFOODS, 2012)
- Physiological range checks per food category (from USDA SR Legacy, TürKomp, EFSA)
- Cross-nutrient consistency: e.g., total fat ≥ sum of individual fatty acids
- [ADDITIONAL RULES: moisture constraints, vitamin stability rules, mineral ratio checks?]

These domain-specific constraints function as a hallucination detection layer — catching fabricated or implausible values that pass standard NLP confidence checks but violate food science reality. Records passing all rules and exceeding the confidence threshold are accepted; failures escalate to L4 or L5.

**Objective linkage:** L3 drives Objective 1 (≥99.5% auto-approved accuracy, [TARGET_COST_REDUCTION]% cost reduction vs. GPT-4o, Section 4.6.3) and Objective 2 (≥500,000 data points).

---

### 4.2.4. Layer 4 — Commercial Model Augmentation (Escalation)

**Purpose:** Handle extraction tasks exceeding current L3 capability using commercial LLMs.

**Method:**
- Only the **failing sub-task** is forwarded to L4 — not the entire paper. This modular escalation dramatically reduces API costs.
- L4 maintains a model roster ranked by cost and capability (e.g., GPT-4o, Claude, Gemini [UPDATE AT PROJECT START])
- The Router selects the cheapest model likely to succeed
- Performance improved via:
  - **(a) Dynamic prompt engineering:** Continuously updated "context file" with curated error examples, edge cases, and domain-specific instructions
  - **(b) RAG:** Retrieval system (Lewis et al., 2020) fetches relevant reference data from the verified database before each API call

**Output:** Structured records for handled sub-tasks. L4 outputs, once verified, become training data for L3 — the primary mechanism by which open-source models replace commercial API calls.

---

### 4.2.5. Layer 5 — Expert Human Verification (Gold Standard)

**Purpose:** (a) Ultimate quality assurance for papers no AI layer could confidently extract, and (b) the strongest training signal source for all AI layers.

**Method:**
- Purpose-built verification interface for food engineering Bursiyerler (see WP4)
  - Features: side-by-side PDF + correction form, standardized error taxonomy, difficulty ratings, keyboard-driven navigation, timestamped audit trail
- Experts **review and correct** AI extractions (from L3 or L4) rather than extracting from scratch (Monarch, 2021)
- For each correction, experts annotate: corrected value, error category, difficulty rating

**Adaptive dual-review protocol** (targeting <0.5% database error): During calibration (~500 papers), both bursiyerler independently verify every paper to establish baseline κ ≥ 0.99 (McHugh, 2012) and calibrate confidence threshold X. In production, papers below X receive dual review; those above receive single review with ~5% random dual-review for monitoring. If κ drops below 0.99, X is lowered. Two food engineering bursiyerler serve as primary annotators, targeting ~8–12 verified papers per day each. Prof. Dr. Sumnu resolves all disagreements.

**Output:** Gold-standard records with full provenance and error annotations.

**Training contribution to all layers:**

| Layer | Signal |
|:---|:---|
| L1 | Valid data → positive relevance label; no data → negative label |
| L2 | Same as L1 at classification level |
| L3 | Corrected extractions → fine-tuning data; expert preferences → RLHF reward signal (Ouyang et al., 2022) |
| L4 | Error patterns → dynamic prompt context file; systematic failures → prompt redesign |
| Router | Cost incurred + difficulty ratings → cost model calibration |

**Objective linkage:** Directly delivers Objective 3 (25,000+ gold-standard records from ~5,000 verified papers, <0.5% error) and fuels Objective 4 (RLHF → ≥90% auto-approval, <$0.01/paper).

> [!NOTE]
> **[POST-PRELIM CHECK: L5 BOTTLENECK MATH]** — 100,000 papers processed with auto-approval starting ~60% → ≥90% means ~15,000–20,000 papers may escalate to L5, but WP4 budgets only 5,000. After preliminary benchmark, verify whether an Active Learning Priority Queue (routing only the most instructionally valuable papers to human review) needs to be documented here to close this math gap.

---

## 4.3. The Learned Router (Adaptive Orchestrator)

**Purpose:** Dynamically route each paper (and each sub-task) to the cheapest processing layer capable of accurate extraction.

The Router uses document features (journal, language, table count, text complexity, L2 confidence) to predict which layer can handle each paper. After processing, it receives confidence scores and validation outcomes to decide: accept, retry, or escalate — including skipping layers when features predict they will fail. When multiple layers have attempted extraction, agreement between their outputs serves as an additional acceptance signal (analogous to query-by-committee; Seung et al., 1992).

**Training objective:** The Router minimizes a composite cost function:

> **Loss = α · ProcessingCost + β · (1 − Accuracy) + γ · Latency**

where ProcessingCost includes computational/API costs summed across all layers invoked, Accuracy is measured against the final verified output, and Latency is wall-clock time per paper. Accuracy is treated as a hard constraint (<0.5% error); cost and latency are optimized subject to that constraint.

The Router is trained via contextual bandit methods (Li et al., 2010; Agarwal et al., 2014) and updates incrementally after each paper (online learning), adapting as L3 models improve through fine-tuning.

---

## 4.4. Cross-Layer Learning System

A defining innovation: **every layer teaches all layers below it.** Only the highest layer that processed a given paper generates training signal for all lower layers:

| Final Processing Layer | Layers Receiving Signal | Signal Type |
|:---|:---|:---|
| L2 (rejected as irrelevant) | L1 | Negative relevance label |
| L3 (accepted) | L1, L2 | Positive relevance labels |
| L4 (accepted) | L1, L2, L3 | Relevance labels + extraction data for L3 retraining |
| L5 (expert-verified) | L1, L2, L3, L4 | Relevance labels + gold-standard + error annotations |

Higher-layer examples receive greater training weight via focal loss (Lin et al., 2017), prioritizing cases where lower layers failed. This creates a compounding economic effect: training is a one-time cost, but once L3 absorbs the capabilities of L4 (commercial APIs, ~$[L4_COST_LOW]–[L4_COST_HIGH]/call) and L5 (human experts, ~$[L5_COST_LOW]–[L5_COST_HIGH]/paper), every subsequently handled paper is a permanent cost reduction. At the target volume of 100,000+ papers, even a modest improvement in auto-approval rate (e.g., from 60% to 90%) eliminates tens of thousands of L4/L5 invocations — producing savings that exceed the total training compute budget by an order of magnitude.


\newpage

# 4. YÖNTEM (METHOD) — Part B: Data, Preliminary Work & Statistics

> [!NOTE]
> Section 4 is split into **two parts** for readability.
> - **Part A**: Research Design Overview, System Architecture (L1–L5), Learned Router, Cross-Layer Learning (§4.1–4.4)
> - **Part B** (this file): Data Collection, Preliminary Work, Variables & Statistics, WP Mapping (§4.5–4.8)

---

## 4.5. Data Collection and Management

### 4.5.1. Data Sources

| Source | Type | Language | Access Method | Expected Yield |
|:---|:---|:---|:---|:---|
| PubMed Central | Open-access papers | English | OAI-PMH API (free) | ~[PMC_YIELD] candidate papers |
| DergiPark | Turkish journals | TR, EN | OAI-PMH API (metadata) + open-access full-text download | ~[DERGIPARK_YIELD] candidate papers |
| Google Scholar | Broad academic search | Multilingual | API / Scholarly library | ~[SCHOLAR_YIELD] candidate papers |
| Crossref | DOI metadata & links | Multilingual | REST API (free) | Cross-referencing |
| Scopus | Journal articles | Multilingual | API (EKUAL access) | Broader coverage |
| OpenAlex | Open metadata | Multilingual | REST API (free) | Dedup & citation graph |
| Semantic Scholar | AI-curated papers | Multilingual | REST API (free) | Full-text & semantic search |

### 4.5.2. Data Standards

All extracted nutritional data will be published as **FAIR (Findable, Accessible, Interoperable, Reusable) Open Data** in alignment with TÜBİTAK's Open Science (Açık Bilim) policies, and will comply with:

| Standard | Purpose |
|:---|:---|
| **INFOODS tagnames** (Klensin et al., 1989) | Nutrient identification |
| **FoodEx2** (EFSA, 2015) | Food categorization |
| **LanguaL** thesaurus (Møller et al., 2008) | Food description facets |
| Nutrient values standardized to **per 100g edible portion** | With original units and conversion factors preserved |

### 4.5.3. Database Schema and Storage

- **Primary database:** PostgreSQL with ACID compliance. The `pgvector` extension provides vector similarity search for Entity Linking (L3) and RAG retrieval (L4).
- **Provenance:** Each record tracks: source DOI, page/table/sentence reference, extraction layer, confidence score, verification status
- **Version control** on all records to track changes from model improvements
- **Storage:** ~2–3 TB (100,000 PDFs, extraction records, model checkpoints, embeddings). Institutional servers for primary operations; cloud backup for disaster recovery. Budget line and proforma invoices for the dedicated NAS are detailed in **EK-2 Bütçe ve Gerekçesi**.

**Expected yield:** We estimate an average of ~5 extractable food-nutrient records per relevant paper (e.g., a study reporting macronutrients, minerals, and vitamins for one food yields multiple standardized records).

---

## 4.6. Preliminary Work and Feasibility

Three preliminary studies establish baselines, validate assumptions, and calibrate design parameters.

### 4.6.1. Preliminary Study 1: Literature Scope Survey

**Objective:** Quantify food composition literature volume globally and in Turkish sources (validating Objective 2: screen ≥100,000 papers).

**Method:** Systematic search across PubMed Central, DergiPark, Google Scholar, Crossref using INFOODS/LanguaL/MeSH vocabulary.

**Expected output:**
- Total estimated volume globally
- Volume and proportion of Turkish-language papers
- Distribution by food category and time period

> [!WARNING]
> **[RESULTS TO BE COMPLETED]**

---

### 4.6.2. Preliminary Study 2: Turkish Food Gap Analysis

**Objective:** Document Turkish food items absent from USDA and EFSA databases (validating Objective 3: index ≥5,000 Turkish food items).

**Method:** Comprehensive inventory of Turkish food products, cross-referenced against USDA, EFSA, and TürKomp.

**Expected output:**
- Number and categorization of gaps per database
- Priority list of high-impact gaps (economic, dietary, export relevance)
- Evidence base for the national gain argument (Section 1)

> [!WARNING]
> **[RESULTS TO BE COMPLETED]**

---

### 4.6.3. Preliminary Study 3: Multi-Model Extraction Benchmark

**Objective:** Demonstrate that current AI models produce error rates far above <0.5%, establishing the need for multi-layer verification. Secondarily, characterize the accuracy-cost gradient across model tiers.

**Method:**

**Paper selection:** 200 papers via stratified random sampling — balanced across:
- Language: 100 English, 100 Turkish
- Table characteristics: header complexity, merged cells
- Document structure: column layout, length, supplementary material
- Food category: grains, fruits/vegetables, dairy, meat/fish, processed, Turkish items

**Human labeling:** All 200 papers labeled by food engineering Bursiyerler. At least [NUMBER, e.g., 60] papers dual-labeled to measure inter-annotator agreement (κ).

**Model testing:** Four models spanning the capability spectrum:

| Tier | Model | Params |
|:---|:---|:---|
| **Model A** | Small open-source LLM | ~3B |
| **Model B** | Medium open-source LLM | ~7–13B |
| **Model C** | Commercial standard tier | e.g., GPT-4o-mini |
| **Model D** | Commercial premium tier | e.g., GPT-4o |

> [!NOTE]
> Specific model selections finalized based on best available models at study time.

**Expected results:**

| Metric | Model A (Small OS) | Model B (Med OS) | Model C (Std API) | Model D (Premium API) |
|:---|:---|:---|:---|:---|
| Overall accuracy | [RESULT]% | [RESULT]% | [RESULT]% | [RESULT]% |
| Table extraction | [RESULT]% | [RESULT]% | [RESULT]% | [RESULT]% |
| Context extraction | [RESULT]% | [RESULT]% | [RESULT]% | [RESULT]% |
| Cost per paper | $[RESULT] | $[RESULT] | $[RESULT] | $[RESULT] |
| Processing time | [RESULT]s | [RESULT]s | [RESULT]s | [RESULT]s |

> [!WARNING]
> **[RESULTS TO BE COMPLETED]**

**Primary expected finding:** Even Model D will produce error rates significantly above <0.5%. This gap is the fundamental problem OpenNutri's multi-layer architecture is designed to close.

**Secondary findings:**
- Error rates differ substantially between table and free-text extraction → supports modular L3
- Turkish papers show different accuracy patterns → informs bilingual fine-tuning
- Cheaper models match expensive ones on simple papers; complex papers show capability gap → confirms cascade economics
- Paper characteristics predict difficulty → validates Router feature design
- Error taxonomy reveals systematic, learnable failure modes → demonstrates addressability

### 4.6.4. Feasibility Assessment

Feasibility is assessed as **high:**
- General-purpose LLMs can extract structured data from tables and text with meaningful accuracy even without fine-tuning (Cenikj et al., 2023; Ispirova et al., 2020)
- PEFT methods (LoRA, QLoRA) make it viable to train multiple specialized models on academic-scale budgets
- Modular architecture limits single-component failure impact — any sub-task model can be retrained independently

> [!IMPORTANT]
> **[PLACEHOLDER: TEAM CREDENTIALS]** — Insert 2-3 sentences max highlighting the strongest, most relevant technical skills across the 7-person cross-functional team (e.g., Prof. Dr. Sumnu's food engineering expertise, Arciel's 9 years SWE/Cuban Olympiad medals/AI expertise) that prove the team can execute this complex architecture. Do not list standard academic papers here as they go in EK-3.

---

## 4.7. Variables and Statistical Methods

### 4.7.1. Dependent Variables

| Variable | Definition | Measurement | Unit |
|:---|:---|:---|:---|
| Auto-approved accuracy | Of records accepted without human review, % that are correct | Periodic random audit by domain experts | % |
| Auto-approval rate | % of papers processed without human intervention | Ratio of L3/L4 finalized to total processed | % |
| Database error rate | % of records containing errors (auto-approved + human-verified) | Periodic random audit by domain experts | % |
| Per-paper cost | Total computational cost to accepted quality | GPU-hours + API costs across all layers | USD |
| Extraction latency | Time from ingestion to structured output | Wall-clock time | seconds |
| Recall | Proportion of extractable data points actually extracted | Comparison with exhaustive expert extraction | % |

### 4.7.2. Independent Variables

| Variable | Levels / Range | Validation Goal |
|:---|:---|:---|
| Model size (L3) | 1–3B, 7–13B, 30–70B params | Size-accuracy-cost trade-off |
| Fine-tuning method | LoRA, QLoRA, full fine-tuning | Confirm PEFT achieves ≥95% of full fine-tuning |
| Training data volume | 500, 1k, 2k, 4k, 5k verified papers | Learning curves, diminishing returns |
| Modular vs. monolithic | Single model vs. task-specific models | Validate modular superiority |
| Confidence threshold | 0.7, 0.8, 0.85, 0.9, 0.95 | Optimize acceptance/escalation for <0.5% error |
| Paper characteristics | Language, table complexity, food category | Identify systematic performance variations |

### 4.7.3. Statistical Analysis Plan

**Performance evaluation:**
- Macro-averaged precision, recall, F1-score across nutrient categories
- 95% CIs via bootstrap resampling (Efron & Tibshirani, 1993), n=1000
- Model comparisons: paired McNemar's test (binary) and Wilcoxon signed-rank (continuous), p < 0.05

**Cost-accuracy trade-off:**
- Pareto frontier analysis for non-dominated routing configurations
- Mixed-effects regression (paper characteristics as fixed effects, individual paper as random effect) for cost projection

**Learning curves:**
- Power-law learning curves (Hestness et al., 2017) to project marginal returns of additional verification effort

**Inter-annotator reliability:**
- Cohen's Kappa (κ) for extraction correctness judgments (Shrout & Fleiss, 1979). Target: κ ≥ 0.99, consistent with the <0.5% database error target (Section 4.2.5).

**Router performance:**
- Regret analysis against an oracle router (Lattimore & Szepesvári, 2020). Cumulative regret normalized by papers processed should converge toward zero.

---

## 4.8. Work Package Mapping

| Method Component | Primary WP | Phase | Duration |
|:---|:---|:---|:---|
| L1 Crawler + L2 Classifier | WP1 | Months 1–4 | Infrastructure & data acquisition |
| L3 Fine-Tuning + Validation Rules | WP2 | Months 3–8 | Core extraction engine |
| L4 Integration + Router | WP3 | Months 5–10 | System integration & optimization |
| L5 Verification + Cross-Layer Learning | WP4 | Months 4–16 | Continuous |
| Deployment + Benchmarking + Publication | WP5 | Months 14–18 | Validation & dissemination |

> [!NOTE]
> Adjust time ranges to match Section 5.1 İş-Zaman Çizelgesi exactly.

**Ethics:** This project processes only open-access or institutionally licensed scientific publications; no personally identifiable data is collected and no human subjects are involved. Ethics committee approval is not required. Data extraction targets only factual nutrient composition values, which are not subject to copyright protection, operating strictly within academic Text and Data Mining (TDM) exceptions.

**References:** See EK-1 Kaynaklar.


\newpage

# 5. PROJE YÖNETİMİ
**(PROJECT MANAGEMENT)**

---

## 5.1. İş Paketleri, Görev Dağılımı ve Süreleri

| İP No | İş Paketlerinin Adı ve Hedefleri | Kim(ler) Tarafından Gerçekleştirileceği | Zaman Aralığı | Başarı Ölçütü ve Projenin Başarısına Katkısı |
|:---|:---|:---|:---|:---|
| **1** | **Infrastructure & Data Acquisition** — *(1)* Develop L1 Intelligent Crawler. *(2)* Build and train L2 Lightweight Classifier. *(3)* Establish database schema. | **Yürütücü:** Prof. Dr. Murat Ceylan · **Araştırmacı:** Prof. Dr. Servet Gülüm Sumnu · **Bursiyerler:** Arciel Aliognis, Alijon Alimov | 1–4 Ay | Multi-source crawler operational. L2 classifier F1 ≥ 0.92. Candidate database >300,000 papers (sufficient to yield ≥100,000 relevant after L2 filtering). |
| **2** | **Core Extraction Engine (L3) Development** — *(1)* Create gold-standard baseline dataset. *(2)* Fine-tune sub-task specific models (table parsing, entity linking). *(3)* Design validation rule engine. | **Yürütücü:** Prof. Dr. Murat Ceylan · **Araştırmacılar:** Dr. Engin Esme, Prof. Dr. Servet Gülüm Sumnu · **Bursiyerler:** Arciel Aliognis, Aleyna Özcan, Peri Açıkgöz | 3–8 Ay | L3 accuracy ≥ 75% on benchmark. 5+ modular sub-tasks integrated. 10+ validation rules active. Cost ≥ 30% lower than commercial API-only baseline. |
| **3** | **Cascade Integration & Router Optimization** — *(1)* Integrate L4 (Commercial APIs). *(2)* Develop dynamic prompt engineering. *(3)* Train Learned Router. | **Yürütücü:** Prof. Dr. Murat Ceylan · **Araştırmacı:** Dr. Engin Esme · **Bursiyerler:** Arciel Aliognis, Alijon Alimov | 5–10 Ay | Full L1–L4 cascade end-to-end. Router achieves ≥ 20% cost reduction vs. random routing. Modular escalation operational. E2E latency < 60s/paper (excluding L5). Cost per paper < $0.03. |
| **4** | **Expert Verification & Cross-Layer Learning** — *(1)* Develop verification interface. *(2)* Calibration: dual-review ~500 papers to establish baseline. *(3)* Production: adaptive protocol for remaining papers. *(4)* Implement RLHF/fine-tuning. | **Yürütücü:** Prof. Dr. Murat Ceylan · **Araştırmacılar:** Prof. Dr. Servet Gülüm Sumnu, Dr. Engin Esme · **Bursiyerler:** Alijon Alimov, Arciel Aliognis, Aleyna Özcan, Peri Açıkgöz | 4–16 Ay | ≥25,000 gold-standard records (from ~5,000 verified papers). Error rate < 0.5%. Auto-approval rate ≥ 90% (papers accepted without expert correction). Cost < $0.01/paper. |
| **5** | **System Deployment, Validation & Dissemination** — *(1)* Deploy production REST API. *(2)* Publish open-access dataset. *(3)* Final benchmarking. *(4)* Scientific publications. | **Yürütücü:** Prof. Dr. Murat Ceylan · **Araştırmacılar:** Dr. Engin Esme, Prof. Dr. Servet Gülüm Sumnu · **Bursiyerler:** Alijon Alimov, Arciel Aliognis, Aleyna Özcan, Peri Açıkgöz | 14–18 Ay | Final system accuracy ≥ 95% (bootstrap CI). ≥500,000 food-nutrient records extracted. REST API deployed (<200ms, ≥100 concurrent req/s). Database and benchmark published on open-access platform. ≥3 papers submitted to peer-reviewed journals. |

> [!IMPORTANT]
> **[PLACEHOLDER: GANTT CHART]** — Insert İş-Zaman Çizelgesi (Gantt chart) showing WP1–WP5 timelines across Months 1–18.
>
> ```
> WP1 ████████░░░░░░░░░░  (1–4)
> WP2 ░░████████████░░░░  (3–8)
> WP3 ░░░░░░░░████████░░  (5–10)
> WP4 ░░░░████████████████████████  (4–16)
> WP5 ░░░░░░░░░░░░░░░░░░░░░░████████████  (14–18)
> ```

---

## 5.2. Risk Yönetimi

| İP No | Riskler | B Planı / Risk Yönetimi |
|:---|:---|:---|
| **WP1** | Publisher API rate limits severely restrict crawler retrieval volume, preventing the 100,000 candidate paper target. | Switch to bulk semantic datasets (Semantic Scholar Open Research Corpus, OpenAlex) and open-access repositories (PubMed Central bulk FTP). Focus on DergiPark and institutional repositories for Turkish content. [YÜRÜTÜCÜ EXPERTISE PLACEHOLDER — describe relevant data access / institutional coordination experience]. |
| **WP2** | Initial L3 models perform below 70% accuracy, creating untenable error volume for higher layers. | Shift L3 to highly specialized, single-task models — [SW TEAM EXPERIENCE PLACEHOLDER]. Temporarily increase L4 budget. Implement more aggressive validation rules — [PROF. SUMNU EXPERTISE PLACEHOLDER — describe food eng. expertise relevant to validation rule design]. |
| **WP3** | Learned Router fails to converge, escalating too many papers to expensive layers causing budget overruns. | Fall back to static threshold cascade (FrugalGPT-style). Set rigid confidence cutoffs per layer based on preliminary benchmark. Sacrifices dynamic optimization but guarantees predictable API expenditure. |
| **WP3** | Commercial API price increases: OpenAI/Anthropic/Google raise rates significantly during the project. | Multi-provider model roster; auto-select cheapest adequate model. Cross-Layer Learning reduces L4 dependency over time. 20% API cost buffer in budget. Open-source models (Llama, Mistral, Qwen) advancing rapidly as alternatives. |
| **WP4** | Verification throughput falls behind schedule (target: 5,000 papers). | [PROF. SUMNU EXPERTISE PLACEHOLDER — describe food composition / annotation supervision experience] and Yürütücü step in for secondary annotations. Prioritize most impactful papers (Turkish foods, novel data). Reduce volume target while maintaining <0.5% error quality. |
| **WP5** | Final system accuracy falls short of target, undermining the benchmark and publication goals. | Target is combined system accuracy (L3 + rules + L4 + L5); no single layer expected to reach it alone. If 90–95% is achieved, report as current SOTA limit with future roadmap. Database error < 0.5% guaranteed by L5 expert verification regardless of AI-layer performance. |

---

## 5.3. Araştırma Olanakları (Research Facilities)

| Kuruluşta Bulunan Altyapı/Ekipman Türü, Modeli | Projede Kullanım Amacı |
|:---|:---|
| **TRUBA HPC resources** — GPU clusters, high-performance storage (TÜBİTAK ULAKBİM) | LLM fine-tuning (L3), RLHF training processes, large-scale batch inference, and model benchmarking |
| **University Library and EKUAL Access** — Web of Science, Scopus, ScienceDirect (Host Institution) | Literature discovery and legal full-text access for the L1 Crawler |


\newpage

# 6. YAYGIN ETKİ
**(WIDESPREAD IMPACT)**

Proje başarıyla gerçekleştirildiği takdirde projeden elde edilmesi öngörülen çıktı(lar) ve etki(ler) ile bu çıktı ve etkilerin paylaşımı ve yayılımına yönelik faaliyet(ler)/ürün(ler)/hizmet(ler) kısa ve net cümlelerle ilgili bölümde belirtilmiştir.

---

## 6.1. Projeden Elde Edilmesi Öngörülen Çıktılara İlişkin Bilgiler

| Çıktı Türü | Çıktı | Zaman Aralığı |
|:---|:---|:---|
| **Bilimsel/Akademik Çıktılar** | | |
| | **Benchmark paper:** Large-scale food composition extraction benchmark — multi-model comparison (GPT-4o, Claude, Llama, Mistral, and OpenNutri) on a substantial test set, expanding on Section 4.6.3. Dataset and evaluation code released on Zenodo/HuggingFace. *(Target: NeurIPS Datasets and Benchmarks, or ACL)* | 12–18 months |
| | **Architecture paper:** Technical deep-dive into the Cascaded Hybrid Intelligence system (L1–L5 pipeline, Learned Router, Cross-Layer Learning), with ablation studies and cost analysis. *(Target: Expert Systems with Applications, or Computers and Electronics in Agriculture)* | 12–18 months |
| | **Dataset paper:** OpenNutri-DB — description, methodology, Turkish food gap analysis, comparison with USDA/EFSA/TürKomp. *(Target: JFCA, Food Chemistry, or Nature Scientific Data)* | 12–18 months |
| **Ekonomik/Ticari/Sosyal Çıktılar** | | |
| | **OpenNutri Database:** ≥500,000 food-nutrient records across global foods (including ≥5,000 uniquely Turkish items, up to 181 nutrients per item), with full source provenance (DOI for every record). Quality: <0.5% error rate (see Section 4.2.5). Free for academic use (monthly updated dataset on Zenodo). Commercial use requires license. | 6–12 mo (initial), 12–18 mo (full scale) |
| | **OpenNutri API:** Production REST API with <200ms response time, ≥100 concurrent req/s, developer docs and SDK. *Users:* health-tech, nutrition apps, food exporters, manufacturers, dietitians. | 12–18 months |
| | **Verification Engine:** Cascaded Hybrid Intelligence pipeline (L1–L5 + Learned Router) — licensable infrastructure for other nations' food composition digitization. *Users:* national food safety agencies (MENA, Central Asia, Eastern Europe), FAO member states. | 12–18 months |
| **Araştırmacı Yetiştirilmesi** | | |
| | **Software/AI team (2 bursiyerler):** Training in LLM fine-tuning, RLHF, cascade architecture, routing optimization, API development. Cross-trained in nutritional data standards (INFOODS, FoodEx2). Weekly supervision by Yürütücü. Expected to pursue Master's theses at AI × food science intersection. | 0–18 months |
| | **Food Science team (2 bursiyerler):** Training in food composition analysis, nutritional profiling, quality control, cross-referencing with USDA/EFSA/TürKomp. Cross-trained in AI-assisted verification workflows. Weekly supervision by Araştırmacı Prof. Dr. Sumnu. Expected to pursue Master's theses at food science × AI intersection. | 0–18 months |

---

## 6.2. Projeden Elde Edilmesi Öngörülen Etkilere İlişkin Bilgiler

| Etki Türü | Etki | Öngörülen Zaman |
|:---|:---|:---|
| **Toplumsal/Kültürel Etki** | | |
| *Yaşam Kalitesine Katkı* | OpenNutri enables evidence-based dietary guidance for Turkish food culture. Health-tech apps can provide accurate tracking for Turkish diets (Simit, Lahmacun, regional dishes) — currently impossible with foreign databases. Target: ≥5 domestic nutrition apps using OpenNutri within 2 years. | 18–36 mo |
| *Sürdürülebilir Çevre* | Food supply chain transparency through compositional traceability supports Green Deal compliance and sustainable food production monitoring. | 18–42 mo |
| *Refah/Eğitim İyileştirme* | Ministry of Health gains a comprehensive national nutritional reference (Section 1.3) for evidence-based dietary policy against obesity and NCDs. Regional composition maps enable targeted school nutrition programs. *(12th Dev. Plan, Art. 299)* | 18–36 mo |
| **Akademik Etki** | | |
| *Yeni Ar-Ge Kararları* | Open benchmark creates new research area: AI-driven food composition extraction. Modular cascade transferable to pharmacology, environmental science, materials science. | 12–24 mo |
| *Ulusal/Uluslararası İşbirlikleri* | Open-access database + INFOODS/FoodEx2 format enables direct integration with USDA, EFSA, FAO/INFOODS. Target: ≥1 formal collaboration within 2 years. | 18–36 mo |
| *Araştırmacı Niteliği* | 4 undergraduate researchers with rare AI × food science interdisciplinary skills. Hands-on LLM, RLHF, cascade architecture, food composition standards experience. *(12th Dev. Plan, Art. 689)* | 0–18 mo |
| *Üniversite-Sanayi İşbirliği* | API and database provide concrete products for university-industry partnerships. Food exporters and health-tech companies become direct stakeholders in academic output. | 12–36 mo |
| **Ekonomik Etki** | | |
| *Sektörel Uygulamalar* | Food export compliance (EU 1169/2011), health-tech/dietitian apps, food manufacturing QC, agricultural marketing, insurance nutritional risk modeling. | 18–36 mo |
| *Küresel Pazar* | Two revenue streams: (1) Data licensing to food conglomerates and health-tech; (2) Infrastructure licensing to nations digitizing food composition. Turkey's position as top-10 agricultural exporter creates natural demand. | 24–48 mo |
| *İstihdam Katkısı* | Spin-off targets 5–10 employees within 2 years post-project. Database and API create enabling infrastructure for 10–20 indirect jobs in domestic health-tech ecosystem. | 18–36 mo |
| *Rekabetçilik* | **Import substitution:** Replaces foreign database dependency with sovereign national alternative. **Export impact:** Lowers compliance costs for exporters. **New firms:** Enables domestic alternatives to MyFitnessPal, Yazio with superior Turkish food accuracy. | 18–48 mo |
| **Ulusal Güvenlik** | | |
| *Gıda Güvenliği* | Sovereign control over national nutritional data. Comprehensive national food composition reference for crisis-response planning. *(12th Dev. Plan, Art. 299)* | 12–24 mo |
| *Ekonomik Güvenlik* | Reverses data trade deficit — Turkey transitions from buyer to seller of food data and verification infrastructure. *(12th Dev. Plan, Art. 711)* | 24–48 mo |
| *Siber Güvenlik* | All processing on national infrastructure (institutional servers + TRUBA). No foreign cloud dependency. Open-source stack eliminates vendor lock-in. | 0–18 mo |

---

## 6.3. Sanayi İşbirliğine Yönelik Geçiş Yol Haritası

OpenNutri's three commercializable deliverables — the verified database, the production REST API, and the Cascaded Hybrid Intelligence engine — form a complete product stack ready for industry deployment. OpenNutri complements and extends TürKomp's foundational work by automating the literature-based data pipeline that TürKomp's manual methodology could not scale.

### Phase 1 — Validation & Partner Acquisition (Months 12–18)
*Concurrent with WP5*

1. **Pilot partnerships:** Free API pilot to 2–3 organizations across target sectors:
   - A Turkish food exporter (EU 1169/2011 compliance)
   - A domestic health-tech / nutrition app company
   - A public health institution (e.g., university hospital dietetics dept. or municipality health directorate)
   - Generates documented use cases and letters of intent

2. **IP protection:** Core defensible assets protected through trade secret and database rights (sui generis):
   - Proprietary fine-tuned model weights (L2, L3, Router)
   - Expert-curated gold-standard dataset (25,000+ records)
   - Domain-specific validation rule engine
   - Dual licensing (free academic / paid commercial)

3. **Business model formalization:** Tiered API pricing, database licensing terms, unit economics validated by pilot data

---

### Phase 2 — Company Formation (Months 18–30)
*TÜBİTAK 1812 BİGG + KOSGEB*

- **TÜBİTAK 1812 BİGG Yatırım:** Team member applies with validated business plan and pilot results. Funding supports: production-grade SaaS conversion, initial paying customers, 2–3 additional hires. BİGG mentorship/accelerator for market positioning and investor readiness.

- **KOSGEB Teknoloji Odaklı / TEKNOYATIRIM:** Applied in parallel for equipment and infrastructure investment (dedicated GPU servers, high-availability database infrastructure).

---

### Phase 3 — Scaling (Months 30–48)
*TEYDEB 1507 + TEYDEB 1505*

- **TEYDEB 1507 (KOBİ Ar-Ge):** Expand database to new domains (animal feed, cosmetics ingredient safety). Develop sector-specific API products (export compliance module, clinical nutrition decision support).

- **TEYDEB 1505 (Üniversite-Sanayi İşbirliği):** The spin-off company partners with the originating university to adapt the Verification Engine for international licensing. Primary targets: MENA region and Central Asian Turkic states. The 1505 project will fund the multilingual model fine-tuning and new food ontology mapping required for the spin-off to export this technology globally.

> **Expected Outcome:** Within 3 years of project completion — spin-off with 5–10 employees, recurring API+licensing revenue, ≥1 international engine licensing agreement. Turkey transforms from buyer to seller of food composition infrastructure.

---

## 6.4. Proje Çıktılarının Paylaşımı ve Yayılımı

| Etkinlik Türü | Paydaş / Olası Kullanıcılar | Zaman ve Süre |
|:---|:---|:---|
| Project website with docs, progress updates, API early-access registration | Researchers, developers, food industry, general public | Month 1 onwards |
| Social media & academic networks (ResearchGate, Google Scholar, LinkedIn, X) | General academic and professional audience | Month 6 onwards |
| Peer-reviewed publications (3 papers: benchmark, architecture, dataset) | Academic community (food science, AI/NLP, data science) | Months 16–18 (submission) |
| Open-access dataset release (Zenodo / HuggingFace) | Global research community, USDA, EFSA, FAO/INFOODS, health-tech developers | Months 14–16 |
| API developer documentation and SDK release | Software developers, health-tech companies, nutrition app developers | Months 14–16 |
| National academic workshop/seminar | Turkish food science & CS researchers, graduate students, TürKomp/BEBIS team (Hacettepe) | Month 14 (1 day) |
| Industry demo day / stakeholder meeting | Food exporters, health-tech startups, dietitians, Ministry of Health | Month 16 (1 day) |
| International conference presentation(s) | Academic community, industry practitioners | Months 15–18 |
| Direct outreach to Turkish food export associations (TİM, ilgili ihracatçı birlikleri) | Food export companies, trade associations | Months 14–18 |
| API access for undergraduate capstone/senior projects | CS and Food Engineering departments at host institution | Month 14 onwards |
| TÜBİTAK project showcase / Science fair | TÜBİTAK community, general public, potential industry partners | Month 18 |


\newpage

# EK-1 KAYNAKLAR
**(REFERENCES)**

---

- Agarwal, A., et al. (2014). Taming the monster: A fast and simple algorithm for contextual bandits. *ICML*, 1638–1646.
- Chapelle, O., & Li, L. (2011). An empirical evaluation of Thompson sampling. *NeurIPS*, 24.
- Chen, L., et al. (2023). FrugalGPT: How to use large language models while reducing cost and improving performance. *arXiv:2305.05176*.
- Dettmers, T., et al. (2023). QLoRA: Efficient finetuning of quantized language models. *NeurIPS*, 36.
- Dooley, D.M., et al. (2018). FoodOn: A harmonized food ontology to increase global food traceability. *npj Science of Food*, 2(1), 1–10.
- EFSA (2015). The food classification and description system FoodEx2 (revision 2). *EFSA Supporting Publications*, 12(5), EN-804.
- Efron, B., & Tibshirani, R.J. (1993). *An Introduction to the Bootstrap*. Chapman & Hall/CRC.
- FAO/INFOODS (2012). *FAO/INFOODS Guidelines for Food Matching*. Rome: FAO.
- Fedus, W., et al. (2022). Switch Transformers: Scaling to trillion parameter models. *JMLR*, 23(120), 1–39.
- Hestness, J., et al. (2017). Deep learning scaling is predictable, empirically. *arXiv:1712.01208*.
- Hu, E.J., et al. (2022). LoRA: Low-rank adaptation of large language models. *ICLR*.
- Klensin, J.C., et al. (1989). *Identification of Food Components for INFOODS Data Interchange*. Tokyo: UNU Press.
- Lattimore, T., & Szepesvári, C. (2020). *Bandit Algorithms*. Cambridge University Press.
- Lewis, P., et al. (2020). Retrieval-augmented generation for knowledge-intensive NLP tasks. *NeurIPS*, 33, 9459–9474.
- Li, L., et al. (2010). A contextual-bandit approach to personalized news article recommendation. *WWW*, 661–670.
- Li, Y., et al. (2023). Domain-specific fine-tuning of LLMs for scientific information extraction. *arXiv:2307.02738*.
- Lin, T.-Y., et al. (2017). Focal loss for dense object detection. *ICCV*, 2980–2988.
- McHugh, M.L. (2012). Interrater reliability: The kappa statistic. *Biochemia Medica*, 22(3), 276–282.
- Monarch, R.M. (2021). *Human-in-the-Loop Machine Learning*. Manning Publications.
- Møller, A., et al. (2008). LanguaL 2006 – the LanguaL thesaurus. *European Journal of Clinical Nutrition*, 62, S272–S275.
- Ouyang, L., et al. (2022). Training language models to follow instructions with human feedback. *NeurIPS*, 35, 27730–27744.
- Sanh, V., et al. (2019). DistilBERT: Smaller, faster, cheaper and lighter. *arXiv:1910.01108*.
- Settles, B. (2012). *Active Learning*. Morgan & Claypool Publishers.
- Seung, H.S., et al. (1992). Query by committee. *COLT*, 287–294.
- Shazeer, N., et al. (2017). Outrageously large neural networks: The sparsely-gated MoE layer. *ICLR*.
- Shrout, P.E., & Fleiss, J.L. (1979). Intraclass correlations: Uses in assessing rater reliability. *Psychological Bulletin*, 86(2), 420–428.
- Smock, B., et al. (2022). PubTables-1M: Towards comprehensive table extraction. *CVPR*, 4634–4642.
- Turc, I., et al. (2019). Well-read students learn better: On the importance of pre-training compact models. *arXiv:1908.08962*.
- Viola, P., & Jones, M. (2001). Rapid object detection using a boosted cascade. *CVPR*, 1, 511–518.
- Wang, M., et al. (2011). Classifier cascade for minimizing feature evaluation cost. *AISTATS*, 218–226.
- Yue, X., et al. (2024). Large language model cascades with mixture of thoughts representations. *ICLR*.

> [!WARNING]
> **Placeholder citations — need full details:**
> - [PLACEHOLDER: Cenikj et al. (2023) full citation]
> - [PLACEHOLDER: Hooton et al. (2020) full citation]
> - [PLACEHOLDER: Ispirova et al. (2020) full citation]


\newpage


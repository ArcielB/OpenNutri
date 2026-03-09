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

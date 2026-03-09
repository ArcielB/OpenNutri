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

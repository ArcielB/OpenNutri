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

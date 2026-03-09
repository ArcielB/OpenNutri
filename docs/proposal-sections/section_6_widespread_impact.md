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

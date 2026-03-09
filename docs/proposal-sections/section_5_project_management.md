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
| **WP1** | Publisher API rate limits severely restrict crawler retrieval volume, preventing the 100,000 candidate paper target. | Switch to bulk semantic datasets (Semantic Scholar Open Research Corpus, OpenAlex) and open-access repositories (PubMed Central bulk FTP). Focus on DergiPark and institutional repositories for Turkish content. Yürütücü, TÜBİTAK TEYDEB ve ulusal araştırma projelerinde veri odaklı sistemlerin kurulumu ve kurumlar arası koordinasyon süreçlerinde geniş tecrübeye sahiptir; bu deneyim, TRUBA kaynakları ve üniversite kütüphane ağları üzerinden veri erişim süreçlerinin aksamadan yönetilmesini sağlayacaktır. |
| **WP2** | Initial L3 models perform below 70% accuracy, creating untenable error volume for higher layers. | Shift L3 to highly specialized, single-task models — Ekip, büyük ölçekli AI sistem mimarileri ve yüksek performanslı veri işleme süreçlerinde derin tecrübeye sahiptir. Temporarily increase L4 budget. Implement more aggressive validation rules — Araştırmacı Prof. Dr. Sumnu, gıdaların fiziksel özellikleri ve ölçüm yöntemleri konusunda uluslararası düzeyde tecrübe sahibidir; bu uzmanlığı, ekstraksiyon sonuçlarının gıda bilimi gerçekliği ile tutarlılığını denetleyecek (makro bileşen dengesi, nem kısıtları vb.) doğrulama kurallarının tasarımı için kullanılacaktır. |
| **WP3** | Learned Router fails to converge, escalating too many papers to expensive layers causing budget overruns. | Fall back to static threshold cascade (FrugalGPT-style). Set rigid confidence cutoffs per layer based on preliminary benchmark. Sacrifices dynamic optimization but guarantees predictable API expenditure. |
| **WP3** | Commercial API price increases: OpenAI/Anthropic/Google raise rates significantly during the project. | Multi-provider model roster; auto-select cheapest adequate model. Cross-Layer Learning reduces L4 dependency over time. 20% API cost buffer in budget. Open-source models (Llama, Mistral, Qwen) advancing rapidly as alternatives. |
| **WP4** | Verification throughput falls behind schedule (target: 5,000 papers). | Araştırmacı Prof. Dr. Sumnu, uzun yıllar yönettiği laboratuvar çalışmaları ve lisansüstü tez süreçlerinde gıda kompozisyon analizi ve veri kalitesi denetimi konularında derin tecrübe edinmiştir; bursiyerlerin veri etiketleme süreçlerini denetleyerek altın standart veri setinin doğruluğunu garanti edecektir ve Yürütücü step in for secondary annotations. Prioritize most impactful papers (Turkish foods, novel data). Reduce volume target while maintaining <0.5% error quality. |
| **WP5** | Final system accuracy falls short of target, undermining the benchmark and publication goals. | Target is combined system accuracy (L3 + rules + L4 + L5); no single layer expected to reach it alone. If 90–95% is achieved, report as current SOTA limit with future roadmap. Database error < 0.5% guaranteed by L5 expert verification regardless of AI-layer performance. |

---

## 5.3. Araştırma Olanakları (Research Facilities)

| Kuruluşta Bulunan Altyapı/Ekipman Türü, Modeli | Projede Kullanım Amacı |
|:---|:---|
| **TRUBA HPC resources** — GPU clusters, high-performance storage (TÜBİTAK ULAKBİM) | LLM fine-tuning (L3), RLHF training processes, large-scale batch inference, and model benchmarking |
| **University Library and EKUAL Access** — Web of Science, Scopus, ScienceDirect (Host Institution) | Literature discovery and legal full-text access for the L1 Crawler |

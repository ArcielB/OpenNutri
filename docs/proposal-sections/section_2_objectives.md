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

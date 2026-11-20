# Research Notes: Evidence Behind the Tiered PR & War Room Triage Design

This document lists published research that supports each design decision. Every claim below is paraphrased from the cited source. Findings come from different domains (general LLM benchmarks, university courses, Microsoft cloud incidents), so they **support the design direction; they are not measurements of Cynbit/BitElevate**.

## 1. Tiered routing and cascades reduce LLM cost

**FrugalGPT (Chen, Zaharia, Zou; Stanford, 2023; TMLR 2024)**
- Link: https://arxiv.org/abs/2305.05176
- Finds that LLM API prices differ by about two orders of magnitude, and proposes three cost-saving strategies: prompt adaptation, LLM approximation, and LLM cascade.
- A cascade calls cheaper models first and moves to costlier ones only when a quality check says the answer is not good enough. The authors report up to 98% cost reduction while matching the best single model (GPT-4 at the time), or about 4% better accuracy at the same cost. These are results on their benchmark datasets.
- **Use in this project:** justifies Tier 0 (rules) -> Tier 1 (small model) -> Tier 2 (large model + mentor). A "quality check" before escalating maps to our confidence/low-evidence escalation rule.

**RouteLLM (Ong et al.; UC Berkeley / Anyscale; ICLR 2025)**
- Link: https://arxiv.org/abs/2406.18665
- Trains a router that decides, per query, whether a strong or a weak model is needed, using human preference data. Reports over 2x cost savings on common benchmarks with little quality loss; the project page reports larger savings on some individual benchmarks.
- **Use in this project:** supports the later upgrade from hand-written routing rules to a learned router trained on mentor accept/override labels.

**Dynamic Model Routing and Cascading survey (2026)**
- Link: https://arxiv.org/pdf/2603.04445
- Survey noting that estimating answer quality is the critical factor for model selection and that combining routing and cascading can outperform either alone.
- **Use in this project:** reason to keep a post-generation check (schema validation, confidence) in addition to pre-generation routing.

## 2. Hints should guide, not give the solution

**Tutor Kai study (Jacobs & Jaschke, 2024)**
- Link: https://arxiv.org/abs/2403.09744
- A GPT-4 web app gave feedback on programming tasks without revealing solutions; 51 students used it for a semester. Most of the feedback addressed code errors correctly, but the authors also categorise wrong or misleading suggestions as a failure type.
- **Use:** supports guided-hint mode and the need to guard against incorrect hints.

**Next-step hints for novices (Roest, Keuning, Jeuring; ACE 2024)**
- Link: https://arxiv.org/abs/2312.10055
- Studies prompt design for next-step hints and notes that direct answers risk over-reliance and reduced learning. Concludes that further research is needed for practical use.
- **Use:** supports the "no spoon-feeding" guardrail and cautious claims.

**Howzat? Expert evaluation of human and AI hints (2024)**
- Link: https://arxiv.org/abs/2411.18151
- Found that a well-designed prompt let GPT-4 produce hints that experts rated as pedagogically valuable, with a multi-stage prompt doing best. Also notes that choosing the right hint level is hard: too much gives the answer, too vague frustrates.
- **Use:** supports a multi-step prompt (analyse, then write a hint) and graded hint levels.

**LLM Hint Factory (2024) and Feedback-Ladders (2024)**
- Links: https://arxiv.org/abs/2404.02213 and https://arxiv.org/abs/2405.00302
- Both use multiple hint levels, from general guidance up to a targeted code suggestion, with the full solution withheld. The Hint Factory study was small (12 novices).
- **Use:** inspiration for a hint ladder: first a conceptual clue, then a more specific pointer for repeat mistakes.

**CodeAid (Kazemitabaar et al., 2024)**
- Link: https://arxiv.org/abs/2401.11314
- A classroom-deployed assistant designed to be helpful and technically correct without revealing code solutions, motivated by the concern that direct code answers weaken conceptual engagement.
- **Use:** precedent for a mentor-style assistant that withholds code.

## 3. Incident triage, root cause and repeat patterns

**RCACopilot (Chen et al.; Microsoft, 2023/2024)**
- Link: https://arxiv.org/abs/2305.15778
- An on-call system that matches an incident to a handler by alert type, collects diagnostic data, and uses an LLM to predict a root-cause category and explain it. Reports root-cause accuracy up to 0.766 on a year of real Microsoft incidents; the data-collection part has been in production use for over four years.
- It also found that most recurring incidents (93.8%) reappeared within 20 days, and that a single data source often cannot pinpoint the root cause.
- **Use:** supports (a) collecting several signals before judging, which is our signal-extraction step, and (b) repeat-pattern tracking. Caution: this is about production cloud incidents, not interns; the repeat result motivates the idea but does not prove it for learners.

**Recommending Root-Cause and Mitigation Steps for Cloud Incidents (Ahmed et al.; Microsoft, ICSE 2023)**
- Link: https://www.microsoft.com/en-us/research/publication/recommending-root-cause-and-mitigation-steps-for-cloud-incidents-using-large-language-models/
- Study on 40,000+ incidents. Fine-tuning on incident data improved results substantially over zero-shot, and models did better on repetitive machine-reported incidents than on customer-reported ones.
- **Use:** repetitive, well-structured cases (like known War Room patterns) are where automation works best; novel cases should go to humans.

**COMET incident triage (Microsoft)**
- Link: https://www.microsoft.com/en-us/research/publication/large-language-models-can-provide-accurate-and-interpretable-incident-triage-2/
- Filters out non-critical logs before using an LLM for keyword extraction, and was deployed on multiple Microsoft services for 6+ months.
- **Use:** supports filtering/normalising logs with cheap logic before any model call.

## 4. Cynbit-specific facts: source and confidence
- Facts about BitElevate (60-day remote sprints, daily PRs, 60 War Room scenarios, six labs), Services Hub, Product Suite and Case Studies were taken from the Cynbit pages the author reviewed directly. A web search run while writing these notes did not return Cynbit pages, so **these facts were not re-verified here**. Re-open the pages and confirm wording before submitting.
- Mentor workload and cost claims about BitElevate are **assumptions**, not data.

## 5. What this research does not show
- No source here measures AI code-review or hint tools inside a mentor-led internship programme like BitElevate.
- Reported savings (98%, 2x) come from benchmark tasks. Cynbit's real savings must be measured in a pilot.
- LLM hints can be wrong; the cited studies treat incorrect hints as a real failure mode.

## 6. Open items if time allows
- Add research on AI code-review tools in industry (not covered by the sources above).
- Add evidence on embedding/TF-IDF similarity for matching known bug patterns. The PoC v2 uses TF-IDF, but no cited source here validates it for this task.

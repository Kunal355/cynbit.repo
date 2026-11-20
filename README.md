# Cynbit Technologies — AI/ML Engineer Intern Assessment

Submission for the **"Identify an AI Opportunity for Cynbit"** task.

## Chosen Opportunity
**Tiered AI PR & War Room Incident Triage with Repeat-Mistake Tracking for BitElevate.**

## Repository Contents
| File | Purpose |
|---|---|
| `opportunity_report.md` | Cynbit context, industry trends, shortlisted opportunities, selection rationale, success metrics |
| `poc/pr_warroom_triage.py` | Runnable prototype v2: rule signals, TF-IDF pattern matching, tiered routing, repeat-mistake tracking, hint ladder, telemetry, mini evaluation |
| `research_notes.md` | Published research (FrugalGPT, RouteLLM, programming-hint studies, Microsoft incident RCA) behind each design choice |
| `technical_approach.md` | Architecture, data pipeline, model choices, prompt design, guardrails, evaluation, rollout plan |

## How to Run the PoC
```bash
pip install scikit-learn   # already installed in Google Colab
python poc/pr_warroom_triage.py
```
It can also be pasted into a single Google Colab cell. No API key is required.

## Important Notes (Honesty Section)
- The PoC uses **synthetic sample data** written to mimic BitElevate-style PRs and War Room incidents. No private Cynbit data was used.
- The PoC combines **rules with TF-IDF similarity** (a lightweight ML step, no LLM). Latency is measured; token counts are a word-count proxy and cost uses a simulated price, since no real model is called.
- The built-in evaluation uses 5 hand-made cases. It shows the pipeline works and exposes failure cases (see `technical_approach.md`), not real-world accuracy.
- The LLM tier and the learned classifier are described in `technical_approach.md` as the production design (Phase 2), not implemented in the PoC.
- BitElevate details (daily PRs, 60 War Room challenges, labs) come from Cynbit's public pages as read by the author at the time of writing.

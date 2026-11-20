# Technical Approach Report: Tiered PR & War Room Triage Engine

## 1. Scope: What Is Built vs. Designed
| Component | Status |
|---|---|
| Input normalisation, deterministic rule signals | **Implemented in PoC** |
| TF-IDF + cosine-similarity matcher against a library of known mistake patterns (the ML component) | **Implemented in PoC (v2)** |
| Tiered router, repeat-mistake tracker, mentor-escalation flag | **Implemented in PoC** |
| Hint ladder (level 1 conceptual clue, level 2 specific pointer on repeat) | **Implemented in PoC (v2)** |
| Mini evaluation (route accuracy, escalation precision/recall) | **Implemented in PoC (v2), tiny hand-made set** |
| Telemetry: latency measured; tokens = word-count proxy; cost = simulated price | **Partly simulated** |
| LLM tier (Tier 1/2), learned router, persistent store | **Designed, not implemented** |

## 2. Architecture
```
PR diff / CI logs / War Room incident
        -> 1. Ingestion & normalisation (uniform JSON, missing fields = "unknown")
        -> 2. Signal extraction (rules now; + embedding classifier later)
        -> 3. Router + repeat-mistake check (intern history)
              TIER_0_QUICK_PASS | TIER_1_GUIDED_HINT | ESCALATE_DEEP_REVIEW
        -> 4. Hint generator (templates now; LLM with JSON schema later)
        -> 5. Telemetry + mentor feedback loop
```

## 3. Data Pipeline
**Record schema:** `id, intern_id, lab, tests_passed, diff_lines, diff_snippet, error_log`.

- **PoC:** hand-written synthetic records (passing PRs, cache changes, unclosed DB sessions, deadlock/pool-exhaustion logs, repeat submissions by the same intern).
- **Production:** GitHub PR webhook + CI test output + War Room logs -> normaliser -> signal extractor + intern-history lookup -> router -> portal/mentor queue + telemetry store.
- **Labels for improvement:** mentors' accept/override decisions on each triage result become labelled data for tuning thresholds and training a classifier.

## 4. Signals and Routing
Signals: `failing_tests`, `critical_incident` (deadlock, pool exhaustion, OOM), `resource_cleanup_check`, `cache_behavior_check`, `large_diff` (>100 lines).

Routing rules:
- **ESCALATE_DEEP_REVIEW + mentor flag:** any critical incident symptom, or failing tests combined with a repeated mistake.
- **TIER_1_GUIDED_HINT:** any other signal, or a repeated signal.
- **TIER_0_QUICK_PASS:** no signals and tests passing.

Hard rule: critical categories (failing tests, deadlock, OOM, auth/security) are never downgraded by a model or a confidence score.

## 4a. v2 Features Added to the PoC

**1. TF-IDF pattern matcher (real ML step).** Each known mistake (DB session leak, cache invalidation, missing index, deadlock, OOM) has a short text description. The submission's diff, error log and notes are vectorised with TF-IDF (1-2 grams) and compared by cosine similarity (scikit-learn). Matches above a threshold become pattern tags. This catches paraphrased wording that exact keywords miss (e.g. "two workers waiting on each other, lock wait timeout" is matched to the deadlock pattern without the word "deadlock").

**2. Hint ladder.** Each pattern has two hint levels. First occurrence gets a conceptual question; if the same intern repeats the pattern, they get a more specific pointer. Full solutions are never produced. The design follows the multi-level hint idea in the research notes (LLM Hint Factory, Feedback-Ladders).

**3. Rule fix.** Cache signals are now checked only in added diff lines (lines starting with `+`), and the earlier operator-precedence bug in the first draft was removed.

**4. Mini evaluation.** Five hand-labelled cases (including paraphrased wording and a comment-only mention of "cache") report route accuracy and escalation precision/recall.

### PoC v2 Results (run on synthetic data)
| Check | Result |
|---|---|
| Route accuracy | 4 of 5 |
| Escalation precision / recall | 1.00 / 1.00 |
| Repeat mistake (INT-07 cache PR twice) | Detected; second PR gets the level-2 hint |
| Latency | About 1-2 ms per item (measured, CPU only, no model call) |

These numbers come from 5 hand-made cases and **do not show real-world accuracy**. They only show the pipeline works end to end and that failures are being measured.

### Known Failures Observed in v2 (kept on purpose)
- **False positive:** a PR with only a comment `# TODO maybe add cache later` still routes to TIER_1 because the added-line check cannot tell comments from code. Fix: strip comment lines before matching.
- **Noisy secondary match:** a plain Redis cache PR also scored 0.16 on the missing-index pattern, producing an extra, irrelevant hint. Fix: raise the threshold per pattern, or show only the top match, once a labelled set exists to tune on.
- **Tiny pattern library:** five hand-written patterns. Unknown mistake types will fall through to Tier 0. Mitigation: sampled mentor audit of Tier 0 passes, and growing the library from mentor overrides.

## 5. Model Choices (Production Design)
| Tier | Method | Why |
|---|---|---|
| 0 | Rules only | Zero cost, millisecond latency |
| 1 | Small, low-cost LLM, or embedding similarity against a library of known mistake patterns | Targeted hints at low cost |
| 2 | Larger LLM plus mentor review | Concurrency, security, multi-file logic |

TF-IDF matching is implemented in the PoC as a first step. The production upgrade is sentence embeddings (or a classifier trained on mentor labels), which handle paraphrase better than TF-IDF.

## 6. Prompt Design (Tier 1/2)
**System prompt (sketch):**
> You are a code-review mentor for learners. Given the signals, diff and logs, return JSON only. Give diagnostic hints and verification steps. Never output a complete corrected code block. If evidence is insufficient, set `confidence` low and `escalate` true.

**Output schema:**
```json
{
  "summary": "string",
  "root_cause_clues": ["string"],
  "verification_steps": ["string"],
  "confidence": 0.0,
  "escalate": false
}
```
**Handling model output:** validate against the schema; retry once on invalid JSON; on timeout or failure fall back to the deterministic template hints. Enforce a per-request token cap.

## 7. Failure Modes and Mitigations
| Failure | Mitigation |
|---|---|
| False positive (e.g. the word "cache" appears in a comment) | Combine signals, check that the match is in added diff lines, tune on mentor overrides |
| False negative (multi-file bug, unusual wording) | Hard escalation for critical categories; embedding classifier; sampled mentor audit of Tier 0 passes |
| Hint spoon-feeding | Prompt constraint plus output check that rejects full code fixes |
| Hallucinated root cause | Low-confidence results escalate; hints are framed as checks, not facts |
| Cost or latency spikes | Token cap, routing-mix monitoring, fallback to rules |
| Truncated logs / missing fields | Mark fields as unknown and bias towards escalation |

## 8. Evaluation Plan
1. Build a labelled set of 100-200 PRs/incidents with mentor-assigned severity.
2. Measure escalation recall (target: near-complete on critical cases) and precision.
3. Measure repeat-mistake detection rate and hint usefulness (mentor and intern ratings).
4. Measure real tokens, cost and latency per tier, replacing the PoC's simulated numbers.

## 9. Execution Plan
1. **Phase 1 (done): prototype** on synthetic data to validate signals, routing and repeat tracking.
2. **Phase 2: shadow mode** on a real cohort with the LLM/embedding tier added. Compare with mentor decisions without showing results to interns.
3. **Phase 3: mentor-in-the-loop** feedback visible to interns, with override logging and threshold tuning.
4. **Phase 4: full portal integration** with persistent history storage and cost/latency dashboards.

## 10. PoC Limitations
- Data is synthetic and tiny; results do not demonstrate accuracy.
- Token, cost and latency figures are placeholders, not measurements.
- Matching uses rules plus TF-IDF over a five-pattern library; it will miss unseen patterns and multi-file bugs, and it can mis-fire on comments.
- Tokens are a word-count proxy and cost uses a simulated price; only latency is measured.
- Intern history is in-memory only.

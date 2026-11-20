"""
Tiered PR & War Room Triage - PoC v2 (Cynbit / BitElevate)

Pipeline: normalise -> rule signals + TF-IDF pattern match -> repeat check
          -> tiered route -> hint ladder -> telemetry -> mini evaluation

Honest notes:
- Data is synthetic. Pattern library and test cases are hand-written.
- ML part = TF-IDF + cosine similarity (scikit-learn), no LLM call.
- latency_ms is MEASURED. est_tokens is a rough word-count proxy and
  est_cost_usd is a SIMULATED price, not a real API bill.
Run:  pip install scikit-learn   (preinstalled in Colab)   then   python pr_warroom_triage.py
"""
import re
import time
from typing import Any, Dict, List

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# ---------------------------------------------------------------- knowledge base
# Known mistake patterns: tag -> (description used for matching, hint ladder)
PATTERNS: Dict[str, Dict[str, Any]] = {
    "db_session_leak": {
        "text": "database session connection opened inside retry loop never closed released "
                "too many clients connection pool exhausted",
        "ladder": [
            "Think about what happens to every DB connection when the code path errors or retries.",
            "Check whether each session is released on success, error and retry paths (look at try/finally or context managers).",
        ],
    },
    "cache_invalidation": {
        "text": "redis cache get setex ttl stale data update delete invalidate cached value",
        "ladder": [
            "What does a reader see if the underlying record changes before the TTL expires?",
            "List every write path to this record and check each one clears or refreshes the cache key.",
        ],
    },
    "missing_index": {
        "text": "query filter where project_id status sequential scan slow query composite index foreign key",
        "ladder": [
            "How would the database find these rows if the table had a million records?",
            "Run EXPLAIN ANALYZE on this filter and compare the plan with and without an index on the filtered columns.",
        ],
    },
    "lock_deadlock": {
        "text": "deadlock detected lock wait timeout concurrent batch update transaction order",
        "ladder": [
            "Which two operations could be waiting on each other here?",
            "Check the order in which rows/tables are locked across concurrent workers and keep transactions short.",
        ],
    },
    "memory_oom": {
        "text": "out of memory oom killed memory leak growing list unbounded load all rows into memory",
        "ladder": [
            "What grows with input size in this code, and is there an upper bound?",
            "Check whether data is streamed/paginated or fully loaded, and look at memory over time under load.",
        ],
    },
}
CRITICAL_TAGS = {"lock_deadlock", "memory_oom"}
SIM_PRICE_PER_1K = {"TIER_0_QUICK_PASS": 0.0, "TIER_1_GUIDED_HINT": 0.00015, "ESCALATE_DEEP_REVIEW": 0.0025}

_tags = list(PATTERNS)
_vec = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
_matrix = _vec.fit_transform([PATTERNS[t]["text"] for t in _tags])


# ---------------------------------------------------------------- stage 2a: rules
def rule_signals(sub: Dict[str, Any]) -> List[str]:
    added = "\n".join(l for l in sub["diff_snippet"].splitlines() if l.startswith("+"))
    text = (sub["diff_snippet"] + " " + sub["error_log"]).lower()
    sig = []
    if not sub["tests_passed"]:
        sig.append("failing_tests")
    if any(k in text for k in ("deadlock", "too many clients", "oom", "out of memory")):
        sig.append("critical_incident")
    if sub["diff_lines"] > 100:
        sig.append("large_diff")
    # fixed precedence bug: keyword must appear in ADDED lines, not comments/context
    if re.search(r"\b(redis|cache)\b", added.lower()):
        sig.append("cache_touched")
    return sig


# ---------------------------------------------------------------- stage 2b: TF-IDF
def pattern_matches(sub: Dict[str, Any], threshold: float = 0.12) -> List[Dict[str, Any]]:
    query = f"{sub['diff_snippet']} {sub['error_log']} {sub.get('notes', '')}"
    sims = cosine_similarity(_vec.transform([query]), _matrix)[0]
    out = [{"tag": t, "score": round(float(s), 3)} for t, s in zip(_tags, sims) if s >= threshold]
    return sorted(out, key=lambda m: -m["score"])


# ---------------------------------------------------------------- stage 3-5
def triage(sub: Dict[str, Any], history: Dict[str, List[str]]) -> Dict[str, Any]:
    t0 = time.perf_counter()
    rules = rule_signals(sub)
    matches = pattern_matches(sub)
    match_tags = [m["tag"] for m in matches]

    past = history.setdefault(sub["intern_id"], [])
    repeated = [t for t in match_tags if t in past]
    is_repeat = bool(repeated)

    critical = ("critical_incident" in rules) or any(t in CRITICAL_TAGS for t in match_tags)
    if critical or ("failing_tests" in rules and is_repeat):
        route = "ESCALATE_DEEP_REVIEW"
    elif rules or match_tags:
        route = "TIER_1_GUIDED_HINT"
    else:
        route = "TIER_0_QUICK_PASS"

    # hint ladder: level 1 first time, level 2 (more specific) on repeat
    hints = []
    for t in match_tags[:2]:
        ladder = PATTERNS[t]["ladder"]
        hints.append({"pattern": t, "level": 2 if t in repeated else 1,
                      "hint": ladder[1] if t in repeated else ladder[0]})
    if "failing_tests" in rules:
        hints.append({"pattern": "failing_tests", "level": 1,
                      "hint": "Reproduce the failing test locally and read the assertion before changing code."})
    if not hints and route == "TIER_0_QUICK_PASS":
        hints.append({"pattern": "none", "level": 1, "hint": "No risk signals; check edge cases before merge."})

    for t in match_tags:
        if t not in past:
            past.append(t)

    tokens = 0 if route == "TIER_0_QUICK_PASS" else int(len((sub["diff_snippet"] + sub["error_log"]).split()) * 1.3) + 150
    return {
        "id": sub["id"], "intern_id": sub["intern_id"], "route": route,
        "rule_signals": rules, "pattern_matches": matches,
        "repeat_mistake": is_repeat, "repeated_patterns": repeated,
        "escalate_mentor": route == "ESCALATE_DEEP_REVIEW", "hints": hints,
        "telemetry": {"latency_ms": round((time.perf_counter() - t0) * 1000, 2),
                      "est_tokens(proxy)": tokens,
                      "est_cost_usd(simulated)": round(tokens / 1000 * SIM_PRICE_PER_1K[route], 6)},
    }


# ---------------------------------------------------------------- data
def demo_submissions() -> List[Dict[str, Any]]:
    return [
        {"id": "PR-101", "intern_id": "INT-07", "tests_passed": True, "diff_lines": 45, "error_log": "",
         "diff_snippet": "+ cached = redis_client.get(key)\n+ redis_client.setex(key, 300, val)"},
        {"id": "PR-108", "intern_id": "INT-07", "tests_passed": True, "diff_lines": 38, "error_log": "",
         "diff_snippet": "+ value = redis_client.get(user_key)\n+ redis_client.setex(user_key, 120, data)"},
        {"id": "WAR-18", "intern_id": "INT-12", "tests_passed": False, "diff_lines": 120,
         "error_log": "psycopg2.OperationalError: sorry, too many clients already; deadlock detected",
         "diff_snippet": "+ session = SessionLocal()  # inside retry loop, never closed"},
        {"id": "PR-109", "intern_id": "INT-03", "tests_passed": True, "diff_lines": 68, "error_log": "",
         "diff_snippet": "+ tasks = db.query(Task).filter(Task.project_id == pid, Task.status == 'OPEN').all()"},
        {"id": "PR-120", "intern_id": "INT-05", "tests_passed": True, "diff_lines": 12, "error_log": "",
         "diff_snippet": "+ title = title.strip()\n+ return title.capitalize()"},
    ]


# Mini labelled set for evaluation. Label = should a mentor look at it (escalate)?
# Includes paraphrased cases that keyword rules alone would miss.
EVAL_SET = [
    ({"id": "E1", "intern_id": "x1", "tests_passed": True, "diff_lines": 30, "error_log": "",
      "diff_snippet": "+ while attempts < 3:\n+     conn = engine.connect()  # opened per retry, not released"}, "TIER_1_GUIDED_HINT", False),
    ({"id": "E2", "intern_id": "x2", "tests_passed": False, "diff_lines": 20,
      "error_log": "process killed: out of memory while loading all rows",
      "diff_snippet": "+ rows = db.execute(q).fetchall()"}, "ESCALATE_DEEP_REVIEW", True),
    ({"id": "E3", "intern_id": "x3", "tests_passed": True, "diff_lines": 15, "error_log": "",
      "diff_snippet": "+ def add(a, b):\n+     return a + b"}, "TIER_0_QUICK_PASS", False),
    ({"id": "E4", "intern_id": "x4", "tests_passed": True, "diff_lines": 40,
      "error_log": "two workers waiting on each other, lock wait timeout on orders",
      "diff_snippet": "+ with tx:\n+     update_orders(batch)"}, "ESCALATE_DEEP_REVIEW", True),
    ({"id": "E5", "intern_id": "x5", "tests_passed": True, "diff_lines": 18, "error_log": "",
      "diff_snippet": "+ # TODO maybe add cache later\n+ return compute(x)"}, "TIER_0_QUICK_PASS", False),
]


def evaluate() -> None:
    tp = fp = fn = correct = 0
    for sub, expected_route, should_escalate in EVAL_SET:
        r = triage(sub, {})
        correct += r["route"] == expected_route
        esc = r["escalate_mentor"]
        tp += esc and should_escalate
        fp += esc and not should_escalate
        fn += (not esc) and should_escalate
        print(f"  {sub['id']}: got {r['route']:<22} expected {expected_route}")
    prec = tp / (tp + fp) if tp + fp else float("nan")
    rec = tp / (tp + fn) if tp + fn else float("nan")
    print(f"Route accuracy {correct}/{len(EVAL_SET)} | escalation precision {prec:.2f}, recall {rec:.2f} "
          f"(tiny hand-made set - illustrative only)")


def main() -> None:
    history: Dict[str, List[str]] = {}
    total_tokens = 0
    for sub in demo_submissions():
        r = triage(sub, history)
        total_tokens += r["telemetry"]["est_tokens(proxy)"]
        print(f"\n--- {r['id']} ({r['intern_id']}) -> {r['route']} | repeat={r['repeat_mistake']} "
              f"| mentor={r['escalate_mentor']}")
        print("  rules:", r["rule_signals"], "| patterns:", r["pattern_matches"])
        for h in r["hints"]:
            print(f"  hint L{h['level']} [{h['pattern']}]: {h['hint']}")
        print("  telemetry:", r["telemetry"])
    print(f"\nTotal est tokens (proxy): {total_tokens}")
    print("\n=== Mini evaluation ===")
    evaluate()


if __name__ == "__main__":
    main()

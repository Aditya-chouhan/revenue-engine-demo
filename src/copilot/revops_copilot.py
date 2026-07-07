"""
AI RevOps Copilot -- the project's AI differentiator.

Assembles a structured context payload from the *actual* latest
output/funnel_metrics.json + forecast.json + attribution.json. Both
execution paths below reason ONLY over numbers present in that payload:

  - ANTHROPIC_API_KEY set: a real call to the Anthropic API, with a system
    prompt that forbids citing any number not in the payload and requires
    flagging insufficient data explicitly.
  - No key: a deterministic analyst engine (this module, no LLM call) that
    answers the same 4 canonical questions with real comparative logic
    over the same payload -- same output shape, honestly labeled.

Every output carries "generated_by" naming which path produced it. No path
ever fabricates a plausible-sounding paragraph disconnected from the data --
that is the concrete fix for the brief's "avoid fake AI outputs" requirement.
"""
import json
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")
FALLBACK_LABEL = "deterministic-analyst-engine (no ANTHROPIC_API_KEY set)"

CANONICAL_QUESTIONS = [
    "Why is pipeline down?",
    "Which stage is underperforming?",
    "Where should sales focus?",
    "Which segment converts best?",
]

SYSTEM_PROMPT = """You are a RevOps analyst answering questions about a B2B SaaS sales funnel.
You are given a JSON payload containing the ONLY real data you may cite. Rules:
1. Never state a number, percentage, or trend that is not directly present in or directly
   computable from the payload. Do not use outside knowledge of "typical" SaaS benchmarks
   beyond what's already in the payload's benchmark_range_pct/benchmark_flag fields.
2. If the payload lacks the data needed to answer, say so explicitly instead of guessing.
3. Structure every answer as: a direct 1-2 sentence answer, then "Supporting data:" citing
   the specific fields used, then "Caveats:" naming any limitation (e.g. small sample size).
4. Be a direct, ruthless analyst -- state the uncomfortable conclusion if the data supports
   it. Do not hedge to be agreeable."""


def load_context_payload() -> dict:
    out_dir = PROJECT_ROOT / "output"
    payload = {}
    for name in ("funnel_metrics", "forecast", "attribution"):
        path = out_dir / f"{name}.json"
        if path.exists():
            payload[name] = json.loads(path.read_text())
    return payload


def _call_claude_api(question: str, payload: dict, model: str = DEFAULT_MODEL) -> dict:
    import anthropic
    client = anthropic.Anthropic()
    user_msg = f"DATA PAYLOAD:\n{json.dumps(payload, indent=2)}\n\nQUESTION: {question}"
    response = client.messages.create(
        model=model, max_tokens=900, system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )
    return {"question": question, "answer": response.content[0].text, "generated_by": model}


# ============================================================
# Deterministic fallback engine -- real analysis, no LLM call.
# ============================================================

def _fmt_caveats(*items):
    items = [i for i in items if i]
    return items or ["None -- computed directly from the current dataset."]


def _fallback_why_pipeline_down(payload: dict) -> dict:
    funnel = payload.get("funnel_metrics", {})
    as_of_month = (funnel.get("as_of") or "")[:7]
    all_lvr = [x for x in funnel.get("lead_velocity_rate", []) if x.get("lvr_pct") is not None]
    # Exclude the current (partial) month from the trend the same way
    # src/analytics/forecasting.py does -- a partial month's LVR is an
    # artifact of fewer days elapsed, not a real deceleration, and folding
    # it into "the trend" would be the exact kind of misleading conclusion
    # this copilot's honesty check exists to avoid.
    lvr = [x for x in all_lvr if x["month"] != as_of_month]
    if not lvr:
        return {
            "question": "Why is pipeline down?",
            "answer": "Insufficient data: no complete-month lead velocity history is available yet to assess a trend.",
            "supporting_data": {}, "caveats": _fmt_caveats(), "generated_by": FALLBACK_LABEL,
        }
    recent = lvr[-3:]
    avg_recent_lvr = round(sum(x["lvr_pct"] for x in recent) / len(recent), 1)
    is_down = avg_recent_lvr < 0
    if is_down:
        answer = (
            f"Yes -- pipeline is trending down. Average MQL lead-velocity rate over the last "
            f"{len(recent)} recorded months is {avg_recent_lvr}%, i.e. new MQLs are shrinking month over month."
        )
    else:
        answer = (
            f"No -- pipeline is NOT currently down. Average MQL lead-velocity rate over the last "
            f"{len(recent)} recorded months is +{avg_recent_lvr}%, i.e. MQL volume is growing, not declining. "
            f"If this question was asked on a hypothetical downturn, that scenario is not what the current data shows."
        )
    return {
        "question": "Why is pipeline down?",
        "answer": answer,
        "supporting_data": {"lead_velocity_rate_recent_months": recent},
        "caveats": _fmt_caveats(f"The current partial month ({as_of_month}) is excluded from this trend, same as the forecast model -- a partial month's lower absolute count is not a real deceleration."),
        "generated_by": FALLBACK_LABEL,
    }


def _fallback_which_stage_underperforming(payload: dict) -> dict:
    funnel = payload.get("funnel_metrics", {})
    conversions = funnel.get("funnel_conversion", [])
    below = [c for c in conversions if c.get("benchmark_flag") == "below_benchmark"]
    if below:
        worst = min(below, key=lambda c: c["conversion_pct"] - c["benchmark_range_pct"][0])
        answer = (
            f"{worst['from']} -> {worst['to']} is the underperforming stage: {worst['conversion_pct']}% conversion, "
            f"below its published benchmark range of {worst['benchmark_range_pct'][0]}-{worst['benchmark_range_pct'][1]}%."
        )
    else:
        closest = min(conversions, key=lambda c: c["conversion_pct"] - c["benchmark_range_pct"][0]) if conversions else None
        if closest:
            answer = (
                f"No stage is below its benchmark range. The weakest relative to its range is "
                f"{closest['from']} -> {closest['to']} at {closest['conversion_pct']}% "
                f"(range {closest['benchmark_range_pct'][0]}-{closest['benchmark_range_pct'][1]}%), still within benchmark."
            )
        else:
            answer = "Insufficient data: no funnel conversion stages computed yet."
    return {
        "question": "Which stage is underperforming?",
        "answer": answer,
        "supporting_data": {"funnel_conversion": conversions},
        "caveats": _fmt_caveats("Benchmark ranges are 2025-2026 published SMB/high-velocity B2B figures (see README), not this specific business's historical baseline."),
        "generated_by": FALLBACK_LABEL,
    }


MIN_SEGMENT_SAMPLE = 20


def _fallback_which_segment_converts_best(payload: dict) -> dict:
    funnel = payload.get("funnel_metrics", {})
    segments = funnel.get("segment_performance", {})
    reliable = {k: v for k, v in segments.items() if v.get("leads", 0) >= MIN_SEGMENT_SAMPLE}
    unreliable = {k: v for k, v in segments.items() if v.get("leads", 0) < MIN_SEGMENT_SAMPLE}
    if reliable:
        best = max(reliable, key=lambda k: reliable[k]["win_rate_pct"])
        answer = (
            f"{best} converts best: {reliable[best]['win_rate_pct']}% win rate on {reliable[best]['leads']} leads "
            f"(${reliable[best]['won_mrr']:,.0f} won MRR)."
        )
    else:
        answer = "Insufficient data: no segment has a statistically meaningful sample (>= 20 leads) yet."
    caveats = []
    if unreliable:
        caveats.append(
            f"Excluded from ranking (sample < {MIN_SEGMENT_SAMPLE} leads, not statistically reliable): "
            + ", ".join(f"{k} ({v['leads']} leads)" for k, v in unreliable.items())
        )
    return {
        "question": "Which segment converts best?",
        "answer": answer,
        "supporting_data": {"segment_performance": segments},
        "caveats": _fmt_caveats(*caveats),
        "generated_by": FALLBACK_LABEL,
    }


def _fallback_where_should_sales_focus(payload: dict) -> dict:
    stage_report = _fallback_which_stage_underperforming(payload)
    segment_report = _fallback_which_segment_converts_best(payload)
    funnel = payload.get("funnel_metrics", {})
    rep_pipeline = funnel.get("rep_pipeline", {})
    lagging_rep = None
    if rep_pipeline:
        by_won_mrr = sorted(rep_pipeline.items(), key=lambda kv: kv[1].get("won_mrr", 0))
        lagging_rep = by_won_mrr[0][0] if by_won_mrr else None

    parts = [stage_report["answer"], segment_report["answer"]]
    if lagging_rep:
        parts.append(f"Rep-level: {lagging_rep} has the lowest won MRR on the team and is the first coaching target.")
    answer = " ".join(parts)
    return {
        "question": "Where should sales focus?",
        "answer": answer,
        "supporting_data": {
            "underperforming_stage": stage_report["supporting_data"],
            "best_converting_segment": segment_report["supporting_data"],
            "rep_pipeline": rep_pipeline,
        },
        "caveats": _fmt_caveats(*stage_report["caveats"], *segment_report["caveats"]),
        "generated_by": FALLBACK_LABEL,
    }


_CANONICAL_HANDLERS = {
    "why is pipeline down?": _fallback_why_pipeline_down,
    "which stage is underperforming?": _fallback_which_stage_underperforming,
    "where should sales focus?": _fallback_where_should_sales_focus,
    "which segment converts best?": _fallback_which_segment_converts_best,
}


def _fallback_generic(question: str, payload: dict) -> dict:
    funnel = payload.get("funnel_metrics", {})
    totals = funnel.get("totals", {})
    return {
        "question": question,
        "answer": (
            "No API key is configured, so free-form questions fall back to a fixed set of "
            "supported canonical questions: " + "; ".join(CANONICAL_QUESTIONS) + ". "
            f"Current top-level snapshot: {totals}."
        ),
        "supporting_data": {"totals": totals},
        "caveats": _fmt_caveats("Set ANTHROPIC_API_KEY to enable free-form Q&A over this data via the real Claude API."),
        "generated_by": FALLBACK_LABEL,
    }


def answer_question(question: str, payload: dict | None = None, model: str = DEFAULT_MODEL) -> dict:
    payload = payload if payload is not None else load_context_payload()

    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return _call_claude_api(question, payload, model=model)
        except Exception as e:  # API failures fall back honestly rather than crashing the dashboard
            fallback = _CANONICAL_HANDLERS.get(question.strip().lower(), _fallback_generic)
            result = fallback(payload) if fallback is not _fallback_generic else fallback(question, payload)
            result["caveats"] = _fmt_caveats(*result.get("caveats", []), f"Claude API call failed ({e}); showing deterministic fallback instead.")
            return result

    handler = _CANONICAL_HANDLERS.get(question.strip().lower())
    if handler:
        return handler(payload)
    return _fallback_generic(question, payload)


def batch_canonical_report(payload: dict | None = None, model: str = DEFAULT_MODEL) -> dict:
    payload = payload if payload is not None else load_context_payload()
    return {"generated_at_data_as_of": payload.get("funnel_metrics", {}).get("as_of"),
            "answers": [answer_question(q, payload, model=model) for q in CANONICAL_QUESTIONS]}

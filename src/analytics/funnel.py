"""
Funnel & pipeline metrics engine -- DB-driven port of v1's
scripts/02_funnel_metrics.py logic (kept in git history), rewritten against
the normalized schema instead of a flat CSV.

Benchmark ranges below are unchanged from v1's cited 2025-2026 sources (see
README.md "Benchmark sources"): used here to flag which stage is under/over/
within its published range -- the AI copilot (src/copilot/revops_copilot.py)
reads this flag directly rather than re-deriving or guessing it, so "which
stage is underperforming" is always answered from the same one place a
number is computed.
"""
from collections import defaultdict
from datetime import datetime

from src import db

BENCHMARK_RANGES = {
    "Lead->MQL": (35.0, 55.0),
    "MQL->SQL": (20.0, 25.0),
    "SQL->Opportunity": (30.0, 50.0),
    "Opportunity->Closed Won": (25.0, 35.0),
}

QUARTERLY_QUOTA_MRR = 6000  # stated demo target, not a real business figure -- see README


def _parse_date(s):
    return datetime.strptime(s, "%Y-%m-%d") if s else None


def _benchmark_flag(pct, key):
    lo, hi = BENCHMARK_RANGES[key]
    if pct < lo:
        return "below_benchmark"
    if pct > hi:
        return "above_benchmark"
    return "within_benchmark"


def compute_funnel_metrics(conn=None) -> dict:
    own_conn = conn is None
    conn = conn or db.get_connection()

    leads = db.rows_to_dicts(db.fetch_all(conn, "SELECT * FROM leads"))
    opps = db.rows_to_dicts(db.fetch_all(conn, "SELECT * FROM opportunities"))

    opp_by_lead = {o["lead_id"]: o for o in opps}

    n_total = len(leads)
    n_mql = sum(1 for l in leads if l["mql_date"])
    n_sql = sum(1 for l in leads if l["sql_date"])
    n_opp = len(opps)
    n_won = sum(1 for o in opps if o["outcome"] == "Won")
    n_lost = sum(1 for o in opps if o["outcome"] == "Lost")
    n_open_opp = sum(1 for o in opps if o["stage"] == "Opportunity")
    n_open_sql = sum(1 for l in leads if l["stage"] == "SQL")

    funnel_stages = [("Lead", n_total), ("MQL", n_mql), ("SQL", n_sql), ("Opportunity", n_opp), ("Closed Won", n_won)]
    conversions = []
    for i in range(1, len(funnel_stages)):
        prev_label, prev_n = funnel_stages[i - 1]
        label, n = funnel_stages[i]
        rate = round(n / prev_n * 100, 1) if prev_n else 0
        key = f"{prev_label}->{label}"
        conversions.append({
            "from": prev_label, "to": label, "from_n": prev_n, "to_n": n,
            "conversion_pct": rate, "drop_off_pct": round(100 - rate, 1),
            "benchmark_range_pct": BENCHMARK_RANGES.get(key),
            "benchmark_flag": _benchmark_flag(rate, key) if key in BENCHMARK_RANGES else None,
        })

    overall_lead_to_won = round(n_won / n_total * 100, 2) if n_total else 0

    cycle_days = []
    for l in leads:
        o = opp_by_lead.get(l["lead_id"])
        if o and o["outcome"] == "Won" and l["created_date"] and o["closed_date"]:
            cycle_days.append((_parse_date(o["closed_date"]) - _parse_date(l["created_date"])).days)
    avg_cycle = round(sum(cycle_days) / len(cycle_days), 1) if cycle_days else None
    median_cycle = sorted(cycle_days)[len(cycle_days) // 2] if cycle_days else None

    def avg_gap(pairs):
        gaps = [( _parse_date(b) - _parse_date(a) ).days for a, b in pairs if a and b]
        return round(sum(gaps) / len(gaps), 1) if gaps else None

    stage_dwell = {
        "Lead_to_MQL_days": avg_gap([(l["created_date"], l["mql_date"]) for l in leads]),
        "MQL_to_SQL_days": avg_gap([(l["mql_date"], l["sql_date"]) for l in leads]),
        "SQL_to_Opportunity_days": avg_gap([
            (l["sql_date"], opp_by_lead[l["lead_id"]]["opp_created_date"])
            for l in leads if l["lead_id"] in opp_by_lead
        ]),
        "Opportunity_to_Closed_days": avg_gap([(o["opp_created_date"], o["closed_date"]) for o in opps]),
    }

    mql_by_month, lead_by_month = defaultdict(int), defaultdict(int)
    for l in leads:
        lead_by_month[l["created_date"][:7]] += 1
        if l["mql_date"]:
            mql_by_month[l["mql_date"][:7]] += 1
    months_sorted = sorted(lead_by_month.keys())
    lvr_series, prev_mql = [], None
    for m in months_sorted:
        mql_n = mql_by_month.get(m, 0)
        lvr = round((mql_n - prev_mql) / prev_mql * 100, 1) if prev_mql else None
        lvr_series.append({"month": m, "leads": lead_by_month[m], "mqls": mql_n, "lvr_pct": lvr})
        prev_mql = mql_n if mql_n else prev_mql

    open_pipeline_value = sum(o["deal_value_monthly_usd"] for o in opps if o["stage"] == "Opportunity")
    won_mrr = sum(o["deal_value_monthly_usd"] for o in opps if o["outcome"] == "Won")
    coverage_ratio = round(open_pipeline_value / QUARTERLY_QUOTA_MRR, 2) if QUARTERLY_QUOTA_MRR else None

    channel_stats = defaultdict(lambda: {"leads": 0, "won": 0, "won_mrr": 0.0})
    for l in leads:
        c = channel_stats[l["source_channel"]]
        c["leads"] += 1
        o = opp_by_lead.get(l["lead_id"])
        if o and o["outcome"] == "Won":
            c["won"] += 1
            c["won_mrr"] += o["deal_value_monthly_usd"]
    for c in channel_stats.values():
        c["win_rate_pct"] = round(c["won"] / c["leads"] * 100, 2) if c["leads"] else 0

    rep_stats = defaultdict(lambda: {"leads": 0, "sql": 0, "won": 0, "won_mrr": 0.0})
    for l in leads:
        rp = rep_stats[l["owner_rep"]]
        rp["leads"] += 1
        if l["sql_date"]:
            rp["sql"] += 1
        o = opp_by_lead.get(l["lead_id"])
        if o and o["outcome"] == "Won":
            rp["won"] += 1
            rp["won_mrr"] += o["deal_value_monthly_usd"]

    accounts = db.rows_to_dicts(db.fetch_all(conn, "SELECT account_id, segment, industry FROM accounts"))
    segment_by_account = {a["account_id"]: a["segment"] for a in accounts}
    industry_by_account = {a["account_id"]: a["industry"] for a in accounts}

    segment_stats = defaultdict(lambda: {"leads": 0, "won": 0, "won_mrr": 0.0})
    industry_stats = defaultdict(lambda: {"leads": 0, "won": 0, "won_mrr": 0.0})
    for l in leads:
        seg = segment_by_account.get(l["account_id"], "Unknown")
        ind = industry_by_account.get(l["account_id"], "Unknown")
        segment_stats[seg]["leads"] += 1
        industry_stats[ind]["leads"] += 1
        o = opp_by_lead.get(l["lead_id"])
        if o and o["outcome"] == "Won":
            segment_stats[seg]["won"] += 1
            segment_stats[seg]["won_mrr"] += o["deal_value_monthly_usd"]
            industry_stats[ind]["won"] += 1
            industry_stats[ind]["won_mrr"] += o["deal_value_monthly_usd"]
    for s in segment_stats.values():
        s["win_rate_pct"] = round(s["won"] / s["leads"] * 100, 2) if s["leads"] else 0
    for s in industry_stats.values():
        s["win_rate_pct"] = round(s["won"] / s["leads"] * 100, 2) if s["leads"] else 0

    output = {
        "as_of": "2026-07-07",
        "totals": {
            "leads": n_total, "mql": n_mql, "sql": n_sql, "opportunity": n_opp,
            "closed_won": n_won, "closed_lost": n_lost,
            "open_sql": n_open_sql, "open_opportunity": n_open_opp,
        },
        "funnel_conversion": conversions,
        "overall_lead_to_won_pct": overall_lead_to_won,
        "sales_cycle_days": {"average": avg_cycle, "median": median_cycle, "n_won_deals": len(cycle_days)},
        "stage_dwell_time_days": stage_dwell,
        "lead_velocity_rate": lvr_series,
        "pipeline": {
            "open_pipeline_monthly_value_usd": round(open_pipeline_value, 2),
            "won_mrr_usd": round(won_mrr, 2),
            "quarterly_quota_mrr_usd_assumption": QUARTERLY_QUOTA_MRR,
            "pipeline_coverage_ratio": coverage_ratio,
        },
        "channel_attribution": dict(channel_stats),
        "rep_pipeline": dict(rep_stats),
        "segment_performance": dict(segment_stats),
        "industry_performance": dict(industry_stats),
    }

    if own_conn:
        conn.close()
    return output

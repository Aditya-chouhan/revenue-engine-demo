"""
Computes funnel & pipeline metrics from data/crm_leads.csv.

Outputs output/funnel_metrics.json - consumed by the dashboard and cited
directly in README.md. All numbers here are computed from the synthetic
dataset, not asserted separately - re-running this script re-derives every
figure in the README/dashboard from the same source of truth.
"""
import csv
import json
from datetime import datetime
from collections import defaultdict

DATA_PATH = "data/crm_leads.csv"
OUT_PATH = "output/funnel_metrics.json"

def parse_date(s):
    return datetime.strptime(s, "%Y-%m-%d") if s else None

with open(DATA_PATH) as f:
    rows = list(csv.DictReader(f))

for r in rows:
    for k in ("created_date", "mql_date", "sql_date", "opp_date", "closed_date"):
        r[k + "_dt"] = parse_date(r[k])
    r["deal_value_monthly_usd"] = float(r["deal_value_monthly_usd"]) if r["deal_value_monthly_usd"] else 0.0

n_total = len(rows)
n_mql = sum(1 for r in rows if r["mql_date_dt"])
n_sql = sum(1 for r in rows if r["sql_date_dt"])
n_opp = sum(1 for r in rows if r["opp_date_dt"])
n_won = sum(1 for r in rows if r["outcome"] == "Won")
n_lost = sum(1 for r in rows if r["outcome"] == "Lost")
n_open_opp = sum(1 for r in rows if r["stage"] == "Opportunity")
n_open_sql = sum(1 for r in rows if r["stage"] == "SQL")

# --- Stage-wise conversion & drop-off ---
funnel_stages = [
    ("Lead", n_total),
    ("MQL", n_mql),
    ("SQL", n_sql),
    ("Opportunity", n_opp),
    ("Closed Won", n_won),
]
conversions = []
for i in range(1, len(funnel_stages)):
    prev_label, prev_n = funnel_stages[i - 1]
    label, n = funnel_stages[i]
    rate = round(n / prev_n * 100, 1) if prev_n else 0
    conversions.append({
        "from": prev_label, "to": label,
        "from_n": prev_n, "to_n": n,
        "conversion_pct": rate, "drop_off_pct": round(100 - rate, 1),
    })

overall_lead_to_won = round(n_won / n_total * 100, 2)

# --- Sales cycle length (Lead created -> Closed, won deals only) ---
cycle_days = []
for r in rows:
    if r["outcome"] == "Won" and r["created_date_dt"] and r["closed_date_dt"]:
        cycle_days.append((r["closed_date_dt"] - r["created_date_dt"]).days)
avg_cycle = round(sum(cycle_days) / len(cycle_days), 1) if cycle_days else None
median_cycle = sorted(cycle_days)[len(cycle_days) // 2] if cycle_days else None

# Stage-to-stage average dwell time (won deals, using stage timestamps)
def avg_gap(field_a, field_b):
    gaps = []
    for r in rows:
        a, b = r.get(field_a), r.get(field_b)
        if a and b:
            gaps.append((b - a).days)
    return round(sum(gaps) / len(gaps), 1) if gaps else None

stage_dwell = {
    "Lead_to_MQL_days": avg_gap("created_date_dt", "mql_date_dt"),
    "MQL_to_SQL_days": avg_gap("mql_date_dt", "sql_date_dt"),
    "SQL_to_Opportunity_days": avg_gap("sql_date_dt", "opp_date_dt"),
    "Opportunity_to_Closed_days": avg_gap("opp_date_dt", "closed_date_dt"),
}

# --- Lead Velocity Rate (month-over-month % change in MQL count) ---
mql_by_month = defaultdict(int)
lead_by_month = defaultdict(int)
for r in rows:
    m = r["created_date"][:7]
    lead_by_month[m] += 1
    if r["mql_date"]:
        mql_by_month[r["mql_date"][:7]] += 1

months_sorted = sorted(lead_by_month.keys())
lvr_series = []
prev_mql = None
for m in months_sorted:
    mql_n = mql_by_month.get(m, 0)
    lvr = round((mql_n - prev_mql) / prev_mql * 100, 1) if prev_mql else None
    lvr_series.append({"month": m, "leads": lead_by_month[m], "mqls": mql_n, "lvr_pct": lvr})
    prev_mql = mql_n if mql_n else prev_mql

# --- Pipeline value & coverage ratio ---
open_pipeline_value_monthly = sum(r["deal_value_monthly_usd"] for r in rows if r["stage"] in ("SQL", "Opportunity"))
won_mrr = sum(r["deal_value_monthly_usd"] for r in rows if r["outcome"] == "Won")

# Quarterly quota assumption for the coverage-ratio calc: stated explicitly
# as a demo target, not derived from any real business figure. Modeled at
# $6,000 net-new MRR/quarter - a plausible early-stage SMB-agency target.
QUARTERLY_QUOTA_MRR = 6000
coverage_ratio = round(open_pipeline_value_monthly / QUARTERLY_QUOTA_MRR, 2) if QUARTERLY_QUOTA_MRR else None

# --- Channel attribution ---
channel_stats = defaultdict(lambda: {"leads": 0, "won": 0, "won_mrr": 0.0})
for r in rows:
    c = channel_stats[r["channel"]]
    c["leads"] += 1
    if r["outcome"] == "Won":
        c["won"] += 1
        c["won_mrr"] += r["deal_value_monthly_usd"]
for c in channel_stats.values():
    c["win_rate_pct"] = round(c["won"] / c["leads"] * 100, 2) if c["leads"] else 0

# --- Rep-level pipeline (funnel by owner) ---
rep_stats = defaultdict(lambda: {"leads": 0, "sql": 0, "won": 0, "won_mrr": 0.0})
for r in rows:
    rp = rep_stats[r["owner"]]
    rp["leads"] += 1
    if r["sql_date"]:
        rp["sql"] += 1
    if r["outcome"] == "Won":
        rp["won"] += 1
        rp["won_mrr"] += r["deal_value_monthly_usd"]

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
        "open_pipeline_monthly_value_usd": open_pipeline_value_monthly,
        "won_mrr_usd": won_mrr,
        "quarterly_quota_mrr_usd_assumption": QUARTERLY_QUOTA_MRR,
        "pipeline_coverage_ratio": coverage_ratio,
    },
    "channel_attribution": dict(channel_stats),
    "rep_pipeline": dict(rep_stats),
}

with open(OUT_PATH, "w") as f:
    json.dump(output, f, indent=2)

print(json.dumps(output, indent=2))

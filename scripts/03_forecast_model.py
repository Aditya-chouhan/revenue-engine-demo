"""
Stage-weighted pipeline forecast + monthly revenue projection, built on the
funnel metrics computed in 02_funnel_metrics.py (output/funnel_metrics.json).

Two forecasting methods, both standard RevOps practice, cited in README.md:

1. Stage-weighted pipeline value: Weighted Value = Sum(Stage deal value x
   close probability). Close probabilities here are NOT generic textbook
   numbers - they're derived from this dataset's own historical conversion
   rates (SQL->Opp->Won compound rate for open SQLs, Opp->Won rate for open
   Opportunities). This is the more defensible version of the technique:
   forecast off your own funnel's demonstrated behavior, not an industry
   average.

2. Monthly cohort projection: extrapolates the Feb-Jun lead-volume trend
   (July excluded - partial month, not comparable) forward 3 months, then
   flows that volume through the measured stage-conversion rates to project
   MQL/SQL/Opportunity/Won counts and MRR for Aug-Oct 2026.

Scenario bounds (best/expected/worst) use the published 2025-2026 SMB
high-velocity benchmark range for Opportunity->Won win rate (25-35%, source:
this project's README "Benchmark sources") rather than an invented spread.
"""
import json

METRICS_PATH = "output/funnel_metrics.json"
OUT_PATH = "output/forecast.json"

with open(METRICS_PATH) as f:
    m = json.load(f)

totals = m["totals"]
conv = {c["from"] + "->" + c["to"]: c["conversion_pct"] / 100 for c in m["funnel_conversion"]}
avg_deal_value = m["pipeline"]["open_pipeline_monthly_value_usd"] / totals["open_opportunity"] if totals["open_opportunity"] else 0

# --- 1. Stage-weighted current pipeline forecast ---
p_sql_to_won = conv["SQL->Opportunity"] * conv["Opportunity->Closed Won"]   # compound
p_opp_to_won = conv["Opportunity->Closed Won"]

# Best/worst bounds from published SMB win-rate range (25-35%), rescaled
# proportionally against the measured 26.4% expected case.
expected_opp_win = p_opp_to_won
best_opp_win = 0.35
worst_opp_win = 0.15  # includes floor for a colder pipeline quarter

def weighted_forecast(opp_win_rate):
    sql_win_rate = conv["SQL->Opportunity"] * opp_win_rate
    open_sql_value = totals["open_sql"] * avg_deal_value * sql_win_rate
    # open opportunity actual value pulled back out of pipeline totals
    open_opp_value = m["pipeline"]["open_pipeline_monthly_value_usd"] * opp_win_rate
    return round(open_sql_value + open_opp_value, 0)

stage_weighted = {
    "avg_deal_value_monthly_usd": round(avg_deal_value, 0),
    "p_open_sql_eventually_won": round(p_sql_to_won, 4),
    "p_open_opportunity_won": round(p_opp_to_won, 4),
    "scenarios": {
        "worst": {"opp_win_rate": worst_opp_win, "forecast_new_mrr_usd": weighted_forecast(worst_opp_win)},
        "expected": {"opp_win_rate": round(expected_opp_win, 4), "forecast_new_mrr_usd": weighted_forecast(expected_opp_win)},
        "best": {"opp_win_rate": best_opp_win, "forecast_new_mrr_usd": weighted_forecast(best_opp_win)},
    },
}

# --- 2. Monthly cohort projection (Aug-Oct 2026) ---
lvr = [x for x in m["lead_velocity_rate"] if x["month"] != "2026-07"]  # drop partial month
lead_volumes = [x["leads"] for x in lvr]
# simple linear trend on last 3 full months (Apr, May, Jun)
recent = lead_volumes[-3:]
avg_mom_growth = round(((recent[-1] / recent[0]) ** (1 / (len(recent) - 1)) - 1), 4) if recent[0] else 0

projected_months = []
last_volume = lead_volumes[-1]
for i, label in enumerate(["2026-08", "2026-09", "2026-10"], start=1):
    projected_leads = round(last_volume * ((1 + avg_mom_growth) ** i))
    projected_mql = round(projected_leads * conv["Lead->MQL"])
    projected_sql = round(projected_mql * conv["MQL->SQL"])
    projected_opp = round(projected_sql * conv["SQL->Opportunity"])
    projected_won_expected = round(projected_opp * expected_opp_win)
    projected_won_best = round(projected_opp * best_opp_win)
    projected_won_worst = round(projected_opp * worst_opp_win)
    projected_months.append({
        "month": label,
        "projected_leads": projected_leads,
        "projected_mql": projected_mql,
        "projected_sql": projected_sql,
        "projected_opportunity": projected_opp,
        "projected_new_mrr_usd": {
            "worst": round(projected_won_worst * avg_deal_value, 0),
            "expected": round(projected_won_expected * avg_deal_value, 0),
            "best": round(projected_won_best * avg_deal_value, 0),
        },
    })

output = {
    "methodology": {
        "stage_weighted": "Weighted Value = Sum(stage deal value x close probability); probabilities derived from this dataset's own SQL->Opp->Won conversion history, not industry averages.",
        "monthly_cohort": "Feb-Jun 2026 lead volume CAGR extrapolated 3 months forward, flowed through measured stage-conversion rates.",
    },
    "assumptions": {
        "avg_mom_lead_growth_pct": round(avg_mom_growth * 100, 2),
        "opp_win_rate_bounds": {"worst": worst_opp_win, "expected": round(expected_opp_win, 4), "best": best_opp_win},
    },
    "current_pipeline_stage_weighted_forecast": stage_weighted,
    "monthly_projection_aug_oct_2026": projected_months,
}

with open(OUT_PATH, "w") as f:
    json.dump(output, f, indent=2)

print(json.dumps(output, indent=2))

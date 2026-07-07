"""
Two-method revenue forecast, ported from v1's scripts/03_forecast_model.py
(kept in git history) to operate on the funnel_metrics dict directly rather
than a JSON file, so it composes with src/analytics/funnel.py in-process.

1. Stage-weighted current pipeline: Weighted Value = stage deal value x
   close probability, where probabilities are this dataset's OWN measured
   SQL->Opp->Won and Opp->Won conversion rates -- not generic industry
   assumptions.
2. Monthly cohort projection: extrapolates the trailing lead-volume trend
   forward 3 months, flows it through measured stage-conversion rates.

Scenario bounds (best/expected/worst) use the same published 2025-2026 SMB
high-velocity win-rate range (25-35%, see README.md "Benchmark sources") as
v1, rescaled around this dataset's own measured expected case.
"""

WORST_OPP_WIN_RATE = 0.15
BEST_OPP_WIN_RATE = 0.35


def compute_forecast(funnel_metrics: dict) -> dict:
    totals = funnel_metrics["totals"]
    conv = {f"{c['from']}->{c['to']}": c["conversion_pct"] / 100 for c in funnel_metrics["funnel_conversion"]}
    pipeline = funnel_metrics["pipeline"]

    avg_deal_value = (
        pipeline["open_pipeline_monthly_value_usd"] / totals["open_opportunity"]
        if totals["open_opportunity"] else 0
    )

    expected_opp_win = conv.get("Opportunity->Closed Won", 0)

    def weighted_forecast(opp_win_rate):
        sql_win_rate = conv.get("SQL->Opportunity", 0) * opp_win_rate
        open_sql_value = totals["open_sql"] * avg_deal_value * sql_win_rate
        open_opp_value = pipeline["open_pipeline_monthly_value_usd"] * opp_win_rate
        return round(open_sql_value + open_opp_value, 0)

    stage_weighted = {
        "avg_deal_value_monthly_usd": round(avg_deal_value, 0),
        "p_open_sql_eventually_won": round(conv.get("SQL->Opportunity", 0) * expected_opp_win, 4),
        "p_open_opportunity_won": round(expected_opp_win, 4),
        "scenarios": {
            "worst": {"opp_win_rate": WORST_OPP_WIN_RATE, "forecast_new_mrr_usd": weighted_forecast(WORST_OPP_WIN_RATE)},
            "expected": {"opp_win_rate": round(expected_opp_win, 4), "forecast_new_mrr_usd": weighted_forecast(expected_opp_win)},
            "best": {"opp_win_rate": BEST_OPP_WIN_RATE, "forecast_new_mrr_usd": weighted_forecast(BEST_OPP_WIN_RATE)},
        },
    }

    lvr = [x for x in funnel_metrics["lead_velocity_rate"] if x["month"] != "2026-07"]  # drop partial month
    lead_volumes = [x["leads"] for x in lvr]
    recent = lead_volumes[-3:] if len(lead_volumes) >= 3 else lead_volumes
    avg_mom_growth = (
        round(((recent[-1] / recent[0]) ** (1 / (len(recent) - 1)) - 1), 4)
        if len(recent) > 1 and recent[0] else 0
    )

    projected_months = []
    last_volume = lead_volumes[-1] if lead_volumes else 0
    for i, label in enumerate(["2026-08", "2026-09", "2026-10"], start=1):
        projected_leads = round(last_volume * ((1 + avg_mom_growth) ** i))
        projected_mql = round(projected_leads * conv.get("Lead->MQL", 0))
        projected_sql = round(projected_mql * conv.get("MQL->SQL", 0))
        projected_opp = round(projected_sql * conv.get("SQL->Opportunity", 0))
        projected_months.append({
            "month": label,
            "projected_leads": projected_leads,
            "projected_mql": projected_mql,
            "projected_sql": projected_sql,
            "projected_opportunity": projected_opp,
            "projected_new_mrr_usd": {
                "worst": round(round(projected_opp * WORST_OPP_WIN_RATE) * avg_deal_value, 0),
                "expected": round(round(projected_opp * expected_opp_win) * avg_deal_value, 0),
                "best": round(round(projected_opp * BEST_OPP_WIN_RATE) * avg_deal_value, 0),
            },
        })

    return {
        "methodology": {
            "stage_weighted": "Weighted Value = stage deal value x close probability; probabilities derived from this dataset's own SQL->Opp->Won conversion history, not industry averages.",
            "monthly_cohort": "Trailing lead-volume trend (excl. partial current month) extrapolated 3 months forward, flowed through measured stage-conversion rates.",
        },
        "assumptions": {
            "avg_mom_lead_growth_pct": round(avg_mom_growth * 100, 2),
            "opp_win_rate_bounds": {"worst": WORST_OPP_WIN_RATE, "expected": round(expected_opp_win, 4), "best": BEST_OPP_WIN_RATE},
        },
        "current_pipeline_stage_weighted_forecast": stage_weighted,
        "monthly_projection_next_3_months": projected_months,
    }

"""
Sanity tests, run against the actual generated dataset/output files (not
mocks) -- consistent with the project's "no invented numbers" discipline:
these assert properties of the real pipeline, not of a synthetic test
fixture pretending to be it.

Run: python3 -m pytest tests/test_analytics.py -v
(requires scripts/01-04 to have been run at least once first)
"""
import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src import db
from src.crm.lifecycle import LeadLifecycle, LifecycleViolation
from src.crm.routing import RoutingEngine
from src.models import Lead

OUTPUT_DIR = PROJECT_ROOT / "output"


@pytest.fixture(scope="module")
def funnel_metrics():
    path = OUTPUT_DIR / "funnel_metrics.json"
    if not path.exists():
        pytest.skip("output/funnel_metrics.json not found -- run scripts/02_run_funnel_metrics.py first")
    return json.loads(path.read_text())


@pytest.fixture(scope="module")
def attribution():
    path = OUTPUT_DIR / "attribution.json"
    if not path.exists():
        pytest.skip("output/attribution.json not found -- run scripts/04_run_attribution.py first")
    return json.loads(path.read_text())


@pytest.fixture(scope="module")
def forecast():
    path = OUTPUT_DIR / "forecast.json"
    if not path.exists():
        pytest.skip("output/forecast.json not found -- run scripts/03_run_forecast.py first")
    return json.loads(path.read_text())


def test_funnel_conversion_rates_in_valid_range(funnel_metrics):
    for stage in funnel_metrics["funnel_conversion"]:
        assert 0 <= stage["conversion_pct"] <= 100, stage
        assert 0 <= stage["drop_off_pct"] <= 100, stage


def test_funnel_counts_non_increasing_down_the_funnel(funnel_metrics):
    counts = [s["from_n"] for s in funnel_metrics["funnel_conversion"]] + [
        funnel_metrics["funnel_conversion"][-1]["to_n"]
    ]
    for earlier, later in zip(counts, counts[1:]):
        assert later <= earlier, f"funnel count increased: {counts}"


def test_forecast_scenarios_ordered_worst_to_best(forecast):
    scenarios = forecast["current_pipeline_stage_weighted_forecast"]["scenarios"]
    assert scenarios["worst"]["forecast_new_mrr_usd"] <= scenarios["expected"]["forecast_new_mrr_usd"]
    assert scenarios["expected"]["forecast_new_mrr_usd"] <= scenarios["best"]["forecast_new_mrr_usd"]


def test_attribution_credit_sums_to_total_won_mrr_per_model(attribution):
    by_channel = attribution["revenue_credit_by_channel_usd"]
    total = attribution["total_won_mrr_attributed_usd"]
    for model in ("first", "last", "linear", "u_shaped"):
        model_sum = sum(channel_credits[model] for channel_credits in by_channel.values())
        assert model_sum == pytest.approx(total, abs=1.0), f"{model} model sums to {model_sum}, expected {total}"


def test_routing_load_within_a_few_percent_of_even_split():
    """Reproduces crm-system-design.md's claim in code: weighted round-robin
    (minus the high-signal fast lane and SLA reassignment noise) should land
    close to an even split across reps."""
    reps = ["A. Chouhan", "R. Iyer", "S. Kapoor"]
    engine = RoutingEngine(reps, seed=42)
    for i in range(2080):
        signal_score = 3.0 + (i % 13) * 0.5  # deterministic spread, occasionally crosses the 8.0 fast-lane threshold
        rep = engine.assign(signal_score)
        engine.maybe_reassign(rep)
    summary = engine.load_summary()
    assert summary["max_pct_deviation_from_even"] < 10.0, summary


def test_routing_load_from_actual_generated_dataset():
    conn = db.get_connection()
    if not (PROJECT_ROOT / "data" / "revenue_engine.db").exists():
        conn.close()
        pytest.skip("data/revenue_engine.db not found -- run scripts/01_generate_seed_data.py first")
    rows = db.rows_to_dicts(db.fetch_all(conn, "SELECT owner_rep, COUNT(*) as n FROM leads GROUP BY owner_rep"))
    conn.close()
    counts = {r["owner_rep"]: r["n"] for r in rows}
    total = sum(counts.values())
    even_share = total / len(counts)
    max_dev_pct = max(abs(c - even_share) / even_share for c in counts.values()) * 100
    assert max_dev_pct < 10.0, counts


def test_lifecycle_rejects_opportunity_without_deal_value():
    lead = Lead(
        lead_id=1, account_id=1, source_channel="Referral", created_date="2026-01-01",
        signal_score=5.0, engagement_score=5.0, lead_score=50.0, owner_rep="A. Chouhan",
        stage="SQL",
    )
    with pytest.raises(LifecycleViolation):
        LeadLifecycle.advance(lead, "Opportunity")  # missing deal_value_monthly_usd


def test_lifecycle_rejects_closed_lost_without_reason():
    lead = Lead(
        lead_id=2, account_id=1, source_channel="Referral", created_date="2026-01-01",
        signal_score=5.0, engagement_score=5.0, lead_score=50.0, owner_rep="A. Chouhan",
        stage="Opportunity",
    )
    with pytest.raises(LifecycleViolation):
        LeadLifecycle.advance(lead, "Closed Lost")  # missing lost_reason
    with pytest.raises(LifecycleViolation):
        LeadLifecycle.advance(lead, "Closed Lost", lost_reason="Not a real reason")  # not in enumerated list


def test_lifecycle_rejects_mql_below_signal_floor():
    lead = Lead(
        lead_id=3, account_id=1, source_channel="Referral", created_date="2026-01-01",
        signal_score=1.5, engagement_score=5.0, lead_score=20.0, owner_rep="A. Chouhan",
    )
    with pytest.raises(LifecycleViolation):
        LeadLifecycle.advance(lead, "MQL", mql_date="2026-01-05")


def test_lifecycle_accepts_valid_transitions():
    lead = Lead(
        lead_id=4, account_id=1, source_channel="Referral", created_date="2026-01-01",
        signal_score=6.0, engagement_score=5.0, lead_score=60.0, owner_rep="A. Chouhan",
    )
    LeadLifecycle.advance(lead, "MQL", mql_date="2026-01-03")
    LeadLifecycle.advance(lead, "SQL", sql_date="2026-01-10")
    LeadLifecycle.advance(lead, "Opportunity", deal_value_monthly_usd=1200)
    LeadLifecycle.advance(lead, "Closed Won")
    assert lead.stage == "Closed Won"
    assert lead.deal_value_monthly_usd == 1200

"""
Simulated external-signal ingestion layer.

Reimplements the *concept* of career/projects/clay-enrichment-waterfall's
distress-signal detection (rank collapse, Buy Box loss, review-velocity
cluster) plus two firmographic-proxy signal types (hiring_proxy,
usage_spike) and one buyer-side signal (funding_event) -- kept self-
contained in this project (no cross-project file dependency) rather than
importing clay-enrichment-waterfall's signal_score.py directly, per
ARCHITECTURE.md's design-independence note.

Each account gets 1-4 simulated signal events; signal_score (0-10, the
scale used everywhere else in this project) is a weight-rolled-up average
of those events, not a single opaque number -- `signals` table rows are the
audit trail for every account's score.
"""
import random
from datetime import datetime, timedelta

# Weights sum to 1.0. Distress signals (rank_collapse, buy_box_loss) get the
# highest weight because they were the validated wedge in the Clay project
# (127 of 2,350 sellers showed active collapse); review_cluster is a
# corroborating signal, not a primary one. hiring_proxy/usage_spike/
# funding_event are firmographic/buyer-side signals with lower individual
# weight since they're weaker single-signal predictors of near-term need.
SIGNAL_WEIGHTS = {
    "rank_collapse": 0.25,
    "buy_box_loss": 0.20,
    "review_cluster": 0.15,
    "hiring_proxy": 0.15,
    "usage_spike": 0.15,
    "funding_event": 0.10,
}

SCORE_FLOOR = 3.0   # matches crm/lifecycle.py's MQL_SIGNAL_FLOOR
SCORE_CEILING = 9.5


def generate_account_signals(account_id: int, base_date: datetime, rng: random.Random) -> list[dict]:
    """Signals are detected shortly before the account enters the pipeline --
    the realistic story is 'a distress signal is what triggered outreach,'
    not a random unrelated event."""
    n_events = rng.randint(1, 4)
    types = rng.sample(list(SIGNAL_WEIGHTS), k=n_events)
    events = []
    for t in types:
        value = round(rng.uniform(2.0, 10.0), 2)
        detected = base_date - timedelta(days=rng.randint(1, 21))
        events.append({
            "account_id": account_id,
            "signal_type": t,
            "signal_value": value,
            "weight": SIGNAL_WEIGHTS[t],
            "detected_date": detected.strftime("%Y-%m-%d"),
        })
    return events


def rollup_signal_score(events: list[dict]) -> float:
    """Weighted average of an account's signal events, rescaled into the
    project's standard 3.0-9.5 signal_score band."""
    if not events:
        return SCORE_FLOOR
    weighted_sum = sum(e["signal_value"] * e["weight"] for e in events)
    total_weight = sum(e["weight"] for e in events)
    avg = weighted_sum / total_weight if total_weight else SCORE_FLOOR
    # avg is on the same 2-10 raw scale as signal_value; clamp into the
    # project's working band rather than rescaling, since 2-10 already
    # overlaps 3.0-9.5 almost exactly by construction.
    return round(min(max(avg, SCORE_FLOOR), SCORE_CEILING), 2)

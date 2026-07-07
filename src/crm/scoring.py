"""
Composite lead scoring.

lead_score (0-100) = 40% ICP fit + 30% signal score + 30% engagement score.

Why these weights, stated explicitly rather than left as an unexplained
constant (the brief calls out "avoid black-box logic"):
  - ICP fit (40%) is weighted highest because it is the most stable,
    least-gameable input -- a poor-fit account rarely becomes a good deal no
    matter how active it looks in the short term.
  - Signal score (30%) captures time-sensitive external evidence (distress
    signals, hiring/usage proxies -- see src/signals/signal_engine.py). It
    is real but decays, so it does not outweigh fit.
  - Engagement score (30%) captures actual buyer behavior (touches, recency)
    -- the only input directly caused by the lead's own actions rather than
    inferred about them.
This is a documented, adjustable formula, not a trained/opaque model --
appropriate for a rules-based CRM scoring layer at this data volume.
"""

ICP_WEIGHT = 0.40
SIGNAL_WEIGHT = 0.30
ENGAGEMENT_WEIGHT = 0.30

# Fast-lane routing threshold (crm/routing.py) is defined on the 0-10
# signal_score scale, matching crm-system-design.md's original "signal >= 8.0".
FAST_LANE_SIGNAL_THRESHOLD = 8.0


def engagement_score(activity_count: int, days_since_last_touch: float) -> float:
    """0-10. More touches raises the score; staleness decays it.
    Deliberately simple (linear + decay) so the formula stays inspectable --
    a lead with 5+ touches and recent contact caps near 10, one stale touch
    30+ days ago decays toward 2.
    """
    volume_component = min(activity_count / 5.0, 1.0) * 7.0
    recency_component = max(0.0, 1.0 - days_since_last_touch / 30.0) * 3.0
    return round(volume_component + recency_component, 2)


def composite_lead_score(icp_fit_score: float, signal_score_0_10: float, engagement_score_0_10: float) -> float:
    """icp_fit_score is 0-100; signal_score and engagement_score are 0-10,
    rescaled to 0-100 before weighting so all three inputs share one scale."""
    signal_100 = signal_score_0_10 * 10
    engagement_100 = engagement_score_0_10 * 10
    score = (
        ICP_WEIGHT * icp_fit_score
        + SIGNAL_WEIGHT * signal_100
        + ENGAGEMENT_WEIGHT * engagement_100
    )
    return round(min(score, 100.0), 2)

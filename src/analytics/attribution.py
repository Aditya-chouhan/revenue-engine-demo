"""
Multi-touch marketing attribution -- NEW in v2 (v1 only had a single
first-touch `channel` field per lead, which cannot support this).

Attributes won_mrr from every Closed Won opportunity across the ordered,
channel-tagged touches in that lead's `activities` history (touch_order
1..n), under four standard models:

  - first-touch : 100% credit to touch_order 1's channel
  - last-touch  : 100% credit to the final touch's channel (the last touch
                  recorded before the deal closed, since activities are only
                  generated up to a lead's resolved_end_date)
  - linear      : credit split evenly across every touch
  - U-shaped    : 40% first touch / 40% last touch / 20% split across the
                  middle touches (n>=3); for n==2, falls back to 50/50 (no
                  middle touch exists to hold the 20%); for n==1, 100%.

Only Closed Won opportunities are attributed -- there is no real revenue to
attribute for open or lost deals, and fabricating a "expected revenue"
credit for them would be exactly the invented-number failure mode this
project's benchmarks are careful to avoid.
"""
from collections import defaultdict

from src import db


def _model_credits(channels: list[str]) -> dict:
    """channels is the touch-ordered list of channel strings for one lead.
    Returns {channel: {"first": pct, "last": pct, "linear": pct, "u_shaped": pct}}"""
    n = len(channels)
    result = defaultdict(lambda: {"first": 0.0, "last": 0.0, "linear": 0.0, "u_shaped": 0.0})

    result[channels[0]]["first"] += 1.0
    result[channels[-1]]["last"] += 1.0

    for c in channels:
        result[c]["linear"] += 1.0 / n

    if n == 1:
        result[channels[0]]["u_shaped"] += 1.0
    elif n == 2:
        result[channels[0]]["u_shaped"] += 0.5
        result[channels[-1]]["u_shaped"] += 0.5
    else:
        result[channels[0]]["u_shaped"] += 0.40
        result[channels[-1]]["u_shaped"] += 0.40
        middle = channels[1:-1]
        for c in middle:
            result[c]["u_shaped"] += 0.20 / len(middle)

    return result


def compute_attribution(conn=None) -> dict:
    own_conn = conn is None
    conn = conn or db.get_connection()

    won_opps = db.rows_to_dicts(db.fetch_all(
        conn, "SELECT lead_id, deal_value_monthly_usd FROM opportunities WHERE outcome = 'Won'"
    ))
    activities = db.rows_to_dicts(db.fetch_all(
        conn, "SELECT lead_id, channel, touch_order FROM activities ORDER BY lead_id, touch_order"
    ))

    touches_by_lead = defaultdict(list)
    for a in activities:
        touches_by_lead[a["lead_id"]].append(a["channel"])

    channel_credit = defaultdict(lambda: {"first": 0.0, "last": 0.0, "linear": 0.0, "u_shaped": 0.0})
    n_attributed_deals = 0
    total_won_mrr = 0.0

    for opp in won_opps:
        channels = touches_by_lead.get(opp["lead_id"])
        if not channels:
            continue
        n_attributed_deals += 1
        total_won_mrr += opp["deal_value_monthly_usd"]
        credits = _model_credits(channels)
        for channel, pcts in credits.items():
            for model in ("first", "last", "linear", "u_shaped"):
                channel_credit[channel][model] += pcts[model] * opp["deal_value_monthly_usd"]

    by_channel = {}
    for channel, models in channel_credit.items():
        by_channel[channel] = {
            model: round(value, 2) for model, value in models.items()
        }

    # Which channel "wins" under each model -- the concrete RevOps talking
    # point this module exists to produce.
    top_channel_by_model = {}
    for model in ("first", "last", "linear", "u_shaped"):
        if by_channel:
            top_channel_by_model[model] = max(by_channel, key=lambda ch: by_channel[ch][model])

    output = {
        "model_definitions": {
            "first": "100% credit to the first recorded touch's channel",
            "last": "100% credit to the final recorded touch's channel before close",
            "linear": "Credit split evenly across every touch",
            "u_shaped": "40% first touch / 40% last touch / 20% split across middle touches (n>=3); 50/50 for n=2; 100% for n=1",
        },
        "n_won_deals_total": len(won_opps),
        "n_won_deals_attributed": n_attributed_deals,
        "total_won_mrr_attributed_usd": round(total_won_mrr, 2),
        "revenue_credit_by_channel_usd": by_channel,
        "top_channel_by_model": top_channel_by_model,
    }

    if own_conn:
        conn.close()
    return output

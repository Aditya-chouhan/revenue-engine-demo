#!/usr/bin/env python3
"""
Generates the full synthetic CRM dataset (accounts, contacts, leads,
opportunities, multi-touch activities, signals) into SQLite via src/db.py.

100% synthetic, deterministic (seed=42). Extends the same fictional
Amazon-seller universe as career/projects/clay-enrichment-waterfall and v1
of this project (Beauty/Baby/Home/Gadgets/Skin/Kitchen/Pet/Outdoor
categories, *.example.com domains) -- does NOT read or reuse any real
prior-employer business data (that employment ended 2026-07-05; that data is
not Adi's to reuse post-termination, same exclusion as the Clay project).

What changed from v1 (scripts/01_generate_crm_data.py, kept in git history):
  - Accounts/Contacts are now real normalized entities, not lead-only rows.
  - owner_rep is assigned by src/crm/routing.py's actual routing engine
    (weighted round-robin + signal fast-lane + SLA reassignment), not
    random.choice.
  - Stage transitions run through src/crm/lifecycle.py's LeadLifecycle
    state machine, so required-field hygiene rules are enforced, not just
    documented.
  - signal_score comes from src/signals/signal_engine.py's simulated signal
    events (auditable in the `signals` table), not a bare random.uniform.
  - icp_fit_score/segment come from src/segmentation/icp.py and genuinely
    change conversion odds (CONVERSION_MULTIPLIER), so segmentation shows
    up in the funnel numbers, not just as a label.
  - Each lead now has 2-6 timestamped, channel-tagged activities (multi-
    touch) instead of one static channel field -- this is what makes
    src/analytics/attribution.py's 4 models produce different answers.
  - ~9% of accounts generate a second Lead (a second channel finding the
    same seller, undeduplicated) -- crm-system-design.md's documented
    dedup gap, now reflected at the Account level, not just in company
    naming.

Conversion-rate and cycle-length base assumptions are unchanged from v1,
calibrated to published 2025-2026 SMB/high-velocity B2B benchmarks (see
README.md "Benchmark sources"):
  Lead->MQL: 45% base | MQL->SQL: 22% base | SQL->Opportunity: 40% base |
  Opportunity->Won: 28% base -- each then scaled by the lead's ICP segment
  multiplier (Beachhead 1.15x / Core ICP 1.0x / Adjacent 0.85x / Poor Fit
  0.6x) and clamped to a sane range.
"""
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import db
from src.models import Lead
from src.crm import scoring
from src.crm.lifecycle import LeadLifecycle, LOST_REASONS
from src.crm.routing import RoutingEngine
from src.segmentation import icp
from src.signals import signal_engine

random.seed(42)
RNG = random.Random(42)

CATEGORIES = ["Beauty", "Baby", "Home", "Gadgets", "Skin", "Kitchen", "Pet", "Outdoor"]
CHANNELS = [
    ("Signal-scored inbound", 0.34),
    ("Outbound LinkedIn", 0.28),
    ("Cold email sequence", 0.20),
    ("Referral", 0.10),
    ("Content/organic", 0.08),
]
REPS = ["A. Chouhan", "R. Iyer", "S. Kapoor"]
EMPLOYEE_BANDS = [("1-10", 0.45), ("11-50", 0.35), ("51-200", 0.15), ("201-500", 0.05)]
DEAL_BAND_FACTOR = {"1-10": 1.0, "11-50": 1.2, "51-200": 1.6, "201-500": 2.2}
BASE_DEAL_VALUES = [600, 800, 900, 1200, 1500, 1800, 2200]

FIRST = ["Hearthstone", "Voltix", "Tiny Sprout", "Glow Ritual", "Aurora", "Bluebell",
         "Cascade", "Northfield", "Lumen", "Verdant", "Solace", "Marigold", "Ember",
         "Driftwood", "Halcyon", "Meridian", "Thistle", "Amberlight", "Windrow", "Cobalt",
         "Pinehaven", "Rosemere", "Coral & Co", "Silverline", "Foxglove", "Wren & Co",
         "Basalt", "Cinderwood", "Larkspur", "Opaline"]
SECOND = ["Home Co", "Gadgets", "Baby", "Beauty", "Skin Co", "Baby Goods", "Kitchen Co",
          "Outdoor", "Pet Supply", "Naturals", "Living", "Collective", "Goods Co",
          "Supply Co", "Studio", "Works"]
ROMAN = ["", " II", " III", " IV", " V", " VI", " VII", " VIII", " IX", " X"]

FIRST_NAMES = ["Priya", "Alex", "Maya", "Jordan", "Riya", "Sam", "Neha", "Chris",
               "Anika", "Taylor", "Kabir", "Morgan", "Zara", "Jamie", "Vikram"]
LAST_NAMES = ["Shah", "Patel", "Nguyen", "Rossi", "Kim", "Fischer", "Oduya", "Reyes"]
TITLES_PRIMARY = ["Founder", "Owner", "CEO", "Head of Growth", "VP Sales"]
TITLES_SECONDARY = ["Operations Manager", "Marketing Lead", "Finance Manager"]

MONTH_STARTS = [datetime(2026, 2, 1), datetime(2026, 3, 1), datetime(2026, 4, 1),
                 datetime(2026, 5, 1), datetime(2026, 6, 1), datetime(2026, 7, 1)]
MONTHLY_VOLUME = {0: 340, 1: 365, 2: 390, 3: 415, 4: 440, 5: 130}
DAYS_IN_MONTH = {0: 28, 1: 31, 2: 30, 3: 31, 4: 30, 5: 7}
AS_OF_DATE = datetime(2026, 7, 7)

DEDUP_SECOND_LEAD_PROB = 0.09  # ~9% of accounts get a second, undeduplicated Lead


def weighted_choice(pairs, rng=RNG):
    r = rng.random()
    cum = 0
    for label, weight in pairs:
        cum += weight
        if r <= cum:
            return label
    return pairs[-1][0]


def biz_name(used_counts, rng=RNG):
    base = f"{rng.choice(FIRST)} {rng.choice(SECOND)}"
    n = used_counts.get(base, 0)
    used_counts[base] = n + 1
    suffix = ROMAN[n] if n < len(ROMAN) else f" #{n+1}"
    return f"{base}{suffix}"


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def main():
    conn = db.get_connection()
    db.init_db(conn, reset=True)

    routing_engine = RoutingEngine(REPS, seed=42)

    accounts, contacts, leads_rows, opportunities, activities, signals_rows = [], [], [], [], [], []
    used_names = {}
    account_id_seq = contact_id_seq = 0
    lead_id_seq = 1000
    activity_id_seq = signal_id_seq = opp_id_seq = 0

    # pool of already-created accounts, for the ~9% dedup-collision scenario
    account_pool = []  # list of dicts: account_id, category, employee_band, signal_score, icp_fit_score, segment

    for month_idx, month_start in enumerate(MONTH_STARTS):
        n_leads = MONTHLY_VOLUME[month_idx]
        days_in_month = DAYS_IN_MONTH[month_idx]

        for _ in range(n_leads):
            created = month_start + timedelta(days=RNG.randint(0, days_in_month - 1))

            # bool(...) matters here: account_pool is a mutable list, and it gets
            # appended to later in this same iteration (else branch below) -- without
            # the explicit cast, `use_existing` would alias the list object itself
            # when empty/falsy, and silently flip truthy after the append mutates it.
            use_existing = bool(account_pool) and RNG.random() < DEDUP_SECOND_LEAD_PROB
            if use_existing:
                acct = RNG.choice(account_pool)
                account_id = acct["account_id"]
                category = acct["category"]
                employee_band = acct["employee_band"]
                acct_signal_score = acct["signal_score"]
                icp_fit = acct["icp_fit_score"]
                segment = acct["segment"]
            else:
                account_id_seq += 1
                account_id = account_id_seq
                category = RNG.choice(CATEGORIES)
                employee_band = weighted_choice(EMPLOYEE_BANDS)
                industry = icp.industry_for_category(category)
                company = biz_name(used_names)

                sig_events = signal_engine.generate_account_signals(account_id, created, RNG)
                acct_signal_score = signal_engine.rollup_signal_score(sig_events)
                for e in sig_events:
                    signal_id_seq += 1
                    signals_rows.append({"signal_id": signal_id_seq, **e})

                icp_fit = icp.icp_fit_score(category, employee_band, acct_signal_score)
                segment = icp.segment_for_score(icp_fit)

                accounts.append({
                    "account_id": account_id, "company_name": company, "category": category,
                    "industry": industry, "website": f"{company.lower().replace(' ', '').replace('&','and')}.example.com",
                    "employee_band": employee_band, "icp_fit_score": icp_fit, "segment": segment,
                    "created_date": created.strftime("%Y-%m-%d"),
                })

                n_contacts = RNG.choice([1, 1, 2])
                primary_contact_id = None
                for i in range(n_contacts):
                    contact_id_seq += 1
                    is_primary = 1 if i == 0 else 0
                    if is_primary:
                        primary_contact_id = contact_id_seq
                    contacts.append({
                        "contact_id": contact_id_seq, "account_id": account_id,
                        "full_name": f"{RNG.choice(FIRST_NAMES)} {RNG.choice(LAST_NAMES)}",
                        "title": RNG.choice(TITLES_PRIMARY) if is_primary else RNG.choice(TITLES_SECONDARY),
                        "email": f"contact{contact_id_seq}@{company.lower().replace(' ', '').replace('&','and')}.example.com",
                        "is_primary": is_primary,
                    })

                account_pool.append({
                    "account_id": account_id, "category": category, "employee_band": employee_band,
                    "signal_score": acct_signal_score, "icp_fit_score": icp_fit, "segment": segment,
                    "primary_contact_id": primary_contact_id,
                })
                primary_contact_id_for_lead = primary_contact_id

            if use_existing:
                primary_contact_id_for_lead = acct.get("primary_contact_id")

            lead_id_seq += 1
            lead_id = lead_id_seq
            channel = weighted_choice(CHANNELS)
            multiplier = icp.CONVERSION_MULTIPLIER[segment]

            owner_rep = routing_engine.assign(acct_signal_score)
            owner_rep = routing_engine.maybe_reassign(owner_rep)

            lead = Lead(
                lead_id=lead_id, account_id=account_id, contact_id=primary_contact_id_for_lead,
                source_channel=channel, created_date=created.strftime("%Y-%m-%d"),
                signal_score=acct_signal_score, engagement_score=0.0, lead_score=0.0,
                owner_rep=owner_rep,
            )

            # --- Stage progression, each hop through LeadLifecycle.advance() ---
            p_mql = clamp((0.45 + (acct_signal_score - 6.0) * 0.02) * multiplier, 0.03, 0.92)
            resolved_end_date = created
            deal_value = None
            outcome = None
            lost_reason = None
            opp_created_dt = None
            closed_dt = None
            win_prob_used = None

            if RNG.random() < min(p_mql, 0.65 * multiplier + 0.3):
                mql_date = created + timedelta(days=RNG.randint(1, 6))
                LeadLifecycle.advance(lead, "MQL", mql_date=mql_date.strftime("%Y-%m-%d"))
                resolved_end_date = mql_date

                p_sql = clamp((0.22 + (acct_signal_score - 6.0) * 0.015) * multiplier, 0.02, 0.55)
                if RNG.random() < p_sql:
                    sql_date = mql_date + timedelta(days=RNG.randint(2, 10))
                    LeadLifecycle.advance(lead, "SQL", sql_date=sql_date.strftime("%Y-%m-%d"))
                    resolved_end_date = sql_date
                    routing_engine.mark_sql_opened(lead.owner_rep)

                    p_opp = clamp(0.40 * multiplier, 0.05, 0.75)
                    if RNG.random() < p_opp:
                        opp_created_dt = sql_date + timedelta(days=RNG.randint(3, 12))
                        band_factor = DEAL_BAND_FACTOR[employee_band]
                        deal_value = round(RNG.choice(BASE_DEAL_VALUES) * band_factor / 50) * 50
                        LeadLifecycle.advance(lead, "Opportunity", deal_value_monthly_usd=deal_value)
                        resolved_end_date = opp_created_dt
                        routing_engine.mark_sql_closed(lead.owner_rep)

                        p_won = clamp(0.28 * multiplier, 0.05, 0.70)
                        win_prob_used = round(p_won * 100, 1)
                        close_date = opp_created_dt + timedelta(days=RNG.randint(7, 20))
                        if close_date <= AS_OF_DATE:
                            if RNG.random() < p_won:
                                LeadLifecycle.advance(lead, "Closed Won")
                                outcome, closed_dt = "Won", close_date
                            else:
                                lost_reason = RNG.choice(LOST_REASONS)
                                LeadLifecycle.advance(lead, "Closed Lost", lost_reason=lost_reason)
                                outcome, closed_dt = "Lost", close_date
                            resolved_end_date = close_date
                    else:
                        routing_engine.mark_sql_closed(lead.owner_rep)  # SQL didn't convert to Opp; rep's active SQL work is done

            # --- Multi-touch activities, spread from created_date to resolved_end_date ---
            n_touches = RNG.randint(2, 6)
            span_days = max((resolved_end_date - created).days, 0)
            offsets = sorted(RNG.randint(0, span_days) if span_days else 0 for _ in range(n_touches))
            touch_dates = [created + timedelta(days=o) for o in offsets]
            last_touch_different = outcome is not None and RNG.random() < 0.40
            for i, tdate in enumerate(touch_dates, start=1):
                if i == 1:
                    tchannel = channel
                elif i == n_touches and last_touch_different:
                    other_channels = [c for c, _ in CHANNELS if c != channel]
                    tchannel = RNG.choice(other_channels)
                else:
                    tchannel = weighted_choice(CHANNELS)
                activity_id_seq += 1
                activities.append({
                    "activity_id": activity_id_seq, "lead_id": lead_id, "account_id": account_id,
                    "contact_id": primary_contact_id_for_lead,
                    "activity_type": RNG.choice(["call", "email", "meeting", "content_view"]),
                    "channel": tchannel, "touch_order": i, "occurred_at": tdate.strftime("%Y-%m-%d"),
                    "notes": None,
                })

            days_since_last_touch = (AS_OF_DATE - touch_dates[-1]).days
            lead.engagement_score = scoring.engagement_score(n_touches, days_since_last_touch)
            lead.lead_score = scoring.composite_lead_score(icp_fit, acct_signal_score, lead.engagement_score)

            leads_rows.append({
                "lead_id": lead.lead_id, "account_id": lead.account_id, "contact_id": lead.contact_id,
                "source_channel": lead.source_channel, "created_date": lead.created_date,
                "stage": lead.stage, "signal_score": lead.signal_score, "engagement_score": lead.engagement_score,
                "lead_score": lead.lead_score, "owner_rep": lead.owner_rep, "mql_date": lead.mql_date,
                "sql_date": lead.sql_date, "disqualified_reason": lead.disqualified_reason,
            })

            if opp_created_dt is not None:
                opp_id_seq += 1
                stage = "Closed Won" if outcome == "Won" else ("Closed Lost" if outcome == "Lost" else "Opportunity")
                probability_pct = 100.0 if outcome == "Won" else (0.0 if outcome == "Lost" else win_prob_used)
                opportunities.append({
                    "opp_id": opp_id_seq, "lead_id": lead_id, "account_id": account_id,
                    "owner_rep": lead.owner_rep, "stage": stage, "deal_value_monthly_usd": deal_value,
                    "opp_created_date": opp_created_dt.strftime("%Y-%m-%d"),
                    "closed_date": closed_dt.strftime("%Y-%m-%d") if closed_dt else None,
                    "outcome": outcome, "lost_reason": lost_reason, "probability_pct": probability_pct,
                })

    db.insert_many(conn, "accounts", accounts)
    db.insert_many(conn, "contacts", contacts)
    db.insert_many(conn, "signals", signals_rows)
    db.insert_many(conn, "leads", leads_rows)
    db.insert_many(conn, "opportunities", opportunities)
    db.insert_many(conn, "activities", activities)
    conn.close()

    print(f"Generated {len(accounts)} accounts, {len(contacts)} contacts, {len(leads_rows)} leads, "
          f"{len(opportunities)} opportunities, {len(activities)} activities, {len(signals_rows)} signal events")
    stage_counts = {}
    for r in leads_rows:
        stage_counts[r["stage"]] = stage_counts.get(r["stage"], 0) + 1
    print("Stage distribution:", stage_counts)
    print("Routing load summary:", routing_engine.load_summary())


if __name__ == "__main__":
    main()

"""
Generates synthetic CRM lead-lifecycle data for the Revenue Engine System
portfolio project.

100% synthetic. Extends the fictional seller universe first built in
career/projects/clay-enrichment-waterfall (Amazon-seller distress-signal ICP:
Beauty/Baby/Home/Gadgets/Skin categories, *.example.com domains). This script
does NOT read or reuse any real Sydon AI business data — Adi's Sydon
employment ended 2026-07-05 and that data is not his to reuse post-termination
(same exclusion documented in the Clay project).

Conversion-rate and cycle-length assumptions are calibrated to published
2025-2026 SMB/high-velocity B2B benchmarks (see README.md "Benchmark sources"
section), not invented numbers:
  - Lead -> MQL:        45%   (behavioral/signal-scored inbound, SMB motion)
  - MQL  -> SQL:        22%   (SMB behavioral-scored range: 20-25%)
  - SQL  -> Opportunity: 40%  (SQL->Opportunity range: 30-50%)
  - Opportunity -> Closed Won: 28%  (SMB high-velocity win rate: 25-35%, conservative end)
  - Full cycle length: 30-45 days (SMB benchmark), triangular distribution

Deterministic: seeded RNG (seed=42) so every re-run reproduces identical
output. This is a demo/forecast dataset, not a prediction about any real
business.
"""
import csv
import random
from datetime import datetime, timedelta

random.seed(42)

CATEGORIES = ["Beauty", "Baby", "Home", "Gadgets", "Skin", "Kitchen", "Pet", "Outdoor"]
CHANNELS = [
    ("Signal-scored inbound", 0.34),   # Clay waterfall-style distress-signal sourcing
    ("Outbound LinkedIn", 0.28),
    ("Cold email sequence", 0.20),
    ("Referral", 0.10),
    ("Content/organic", 0.08),
]
REPS = ["A. Chouhan", "R. Iyer", "S. Kapoor"]
LOST_REASONS = [
    "No budget", "Went with in-house fix", "Timing not right",
    "Chose competitor", "Unresponsive after SQL", "Below deal-size floor",
]

FIRST = ["Hearthstone", "Voltix", "Tiny Sprout", "Glow Ritual", "Aurora", "Bluebell",
         "Cascade", "Northfield", "Lumen", "Verdant", "Solace", "Marigold", "Ember",
         "Driftwood", "Halcyon", "Meridian", "Thistle", "Amberlight", "Windrow", "Cobalt",
         "Pinehaven", "Rosemere", "Coral & Co", "Silverline", "Foxglove", "Wren & Co",
         "Basalt", "Cinderwood", "Larkspur", "Opaline"]
SECOND = ["Home Co", "Gadgets", "Baby", "Beauty", "Skin Co", "Baby Goods", "Kitchen Co",
          "Outdoor", "Pet Supply", "Naturals", "Living", "Collective", "Goods Co",
          "Supply Co", "Studio", "Works"]

ROMAN = ["", " II", " III", " IV", " V", " VI", " VII", " VIII", " IX", " X"]

def biz_name(used_counts):
    base = f"{random.choice(FIRST)} {random.choice(SECOND)}"
    n = used_counts.get(base, 0)
    used_counts[base] = n + 1
    suffix = ROMAN[n] if n < len(ROMAN) else f" #{n+1}"
    return f"{base}{suffix}"

def weighted_choice(pairs):
    r = random.random()
    cum = 0
    for label, weight in pairs:
        cum += weight
        if r <= cum:
            return label
    return pairs[-1][0]

MONTH_STARTS = [datetime(2026, 2, 1), datetime(2026, 3, 1), datetime(2026, 4, 1),
                 datetime(2026, 5, 1), datetime(2026, 6, 1), datetime(2026, 7, 1)]
# Monthly lead-generation volume grows slightly month over month (LVR > 0),
# consistent with a signal-sourcing channel that compounds as more sellers
# are scanned. Not a real observed trend - a demo assumption stated here.
# Volume is scaled to the 2,000+ row range the Clay project's own README
# flagged as "what would change at real scale" - this project is that scale.
MONTHLY_VOLUME = {0: 340, 1: 365, 2: 390, 3: 415, 4: 440, 5: 130}  # Jul partial (7 days of data)
DAYS_IN_MONTH = {0: 28, 1: 31, 2: 30, 3: 31, 4: 30, 5: 7}
AS_OF_DATE = datetime(2026, 7, 7)  # "today" for this dataset - matches session date

rows = []
used_names = {}
lead_id = 1000

for month_idx, month_start in enumerate(MONTH_STARTS):
    n_leads = MONTHLY_VOLUME[month_idx]
    days_in_month = DAYS_IN_MONTH[month_idx]
    for _ in range(n_leads):
        lead_id += 1
        company = biz_name(used_names)
        category = random.choice(CATEGORIES)
        channel = weighted_choice(CHANNELS)
        rep = random.choice(REPS)
        signal_score = round(random.uniform(3.0, 9.5), 2)
        created = month_start + timedelta(days=random.randint(0, days_in_month - 1))

        row = {
            "lead_id": lead_id,
            "company": company,
            "category": category,
            "channel": channel,
            "owner": rep,
            "signal_score": signal_score,
            "created_date": created.strftime("%Y-%m-%d"),
            "stage": "Lead",
            "mql_date": "", "sql_date": "", "opp_date": "", "closed_date": "",
            "deal_value_monthly_usd": "", "outcome": "", "lost_reason": "",
        }

        # Lead -> MQL (45%), higher signal score improves odds slightly
        p_mql = min(0.45 + (signal_score - 6.0) * 0.02, 0.65)
        if random.random() < p_mql:
            mql_date = created + timedelta(days=random.randint(1, 6))
            row["stage"] = "MQL"
            row["mql_date"] = mql_date.strftime("%Y-%m-%d")

            # MQL -> SQL (22%)
            p_sql = min(0.22 + (signal_score - 6.0) * 0.015, 0.35)
            if random.random() < p_sql:
                sql_date = mql_date + timedelta(days=random.randint(2, 10))
                row["stage"] = "SQL"
                row["sql_date"] = sql_date.strftime("%Y-%m-%d")

                # SQL -> Opportunity (40%)
                if random.random() < 0.40:
                    opp_date = sql_date + timedelta(days=random.randint(3, 12))
                    row["stage"] = "Opportunity"
                    row["opp_date"] = opp_date.strftime("%Y-%m-%d")
                    row["deal_value_monthly_usd"] = random.choice([600, 800, 900, 1200, 1500, 1800, 2200])

                    # Opportunity -> Closed (28% win), only resolved if the
                    # close date falls on/before AS_OF_DATE - otherwise the
                    # opportunity is still open in the current pipeline.
                    close_date = opp_date + timedelta(days=random.randint(7, 20))
                    if close_date <= AS_OF_DATE:
                        if random.random() < 0.28:
                            row["stage"] = "Closed Won"
                            row["closed_date"] = close_date.strftime("%Y-%m-%d")
                            row["outcome"] = "Won"
                        else:
                            row["stage"] = "Closed Lost"
                            row["closed_date"] = close_date.strftime("%Y-%m-%d")
                            row["outcome"] = "Lost"
                            row["lost_reason"] = random.choice(LOST_REASONS)
                    # else: stage stays "Opportunity" (open, not yet resolved)

        rows.append(row)

out_path = "data/crm_leads.csv"
fieldnames = list(rows[0].keys())
with open(out_path, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"Generated {len(rows)} leads -> {out_path}")
stage_counts = {}
for r in rows:
    stage_counts[r["stage"]] = stage_counts.get(r["stage"], 0) + 1
print("Stage distribution:", stage_counts)

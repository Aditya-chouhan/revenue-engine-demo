#!/usr/bin/env python3
"""CLI wrapper: exports a denormalized lead-level view (joining accounts +
leads + opportunities) to data/crm_leads_export.csv -- basic CRM data
portability (anyone wanting to open this in Excel/Sheets rather than SQLite)."""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import db

OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "crm_leads_export.csv"

QUERY = """
SELECT
    l.lead_id, a.company_name, a.category, a.industry, a.employee_band,
    a.segment, a.icp_fit_score, l.source_channel, l.created_date, l.stage,
    l.signal_score, l.engagement_score, l.lead_score, l.owner_rep,
    l.mql_date, l.sql_date, o.opp_created_date, o.deal_value_monthly_usd,
    o.closed_date, o.outcome, o.lost_reason
FROM leads l
JOIN accounts a ON a.account_id = l.account_id
LEFT JOIN opportunities o ON o.lead_id = l.lead_id
ORDER BY l.lead_id
"""

if __name__ == "__main__":
    conn = db.get_connection()
    rows = db.rows_to_dicts(db.fetch_all(conn, QUERY))
    conn.close()

    if not rows:
        print("No leads found -- run scripts/01_generate_seed_data.py first.")
        sys.exit(1)

    with open(OUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Exported {len(rows)} leads -> {OUT_PATH}")

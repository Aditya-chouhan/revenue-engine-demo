#!/usr/bin/env python3
"""CLI wrapper: computes funnel metrics from the DB, writes output/funnel_metrics.json
and a timestamped snapshot row to funnel_snapshots (audit trail)."""
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import db
from src.analytics.funnel import compute_funnel_metrics

OUT_PATH = Path(__file__).resolve().parent.parent / "output" / "funnel_metrics.json"

if __name__ == "__main__":
    conn = db.get_connection()
    result = compute_funnel_metrics(conn)
    OUT_PATH.write_text(json.dumps(result, indent=2))
    db.insert_one(conn, "funnel_snapshots", {
        "run_timestamp": datetime.now().isoformat(timespec="seconds"),
        "payload_json": json.dumps(result),
    })
    conn.close()
    print(json.dumps(result, indent=2))

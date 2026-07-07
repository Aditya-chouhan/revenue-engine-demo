#!/usr/bin/env python3
"""CLI wrapper: computes multi-touch attribution from the DB, writes
output/attribution.json and a timestamped snapshot row to attribution_snapshots."""
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import db
from src.analytics.attribution import compute_attribution

OUT_PATH = Path(__file__).resolve().parent.parent / "output" / "attribution.json"

if __name__ == "__main__":
    conn = db.get_connection()
    result = compute_attribution(conn)
    OUT_PATH.write_text(json.dumps(result, indent=2))
    db.insert_one(conn, "attribution_snapshots", {
        "run_timestamp": datetime.now().isoformat(timespec="seconds"),
        "payload_json": json.dumps(result),
    })
    conn.close()
    print(json.dumps(result, indent=2))

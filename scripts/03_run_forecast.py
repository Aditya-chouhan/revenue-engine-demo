#!/usr/bin/env python3
"""CLI wrapper: computes the revenue forecast from the latest funnel_metrics.json,
writes output/forecast.json and a timestamped snapshot row to forecast_snapshots."""
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import db
from src.analytics.forecasting import compute_forecast

METRICS_PATH = Path(__file__).resolve().parent.parent / "output" / "funnel_metrics.json"
OUT_PATH = Path(__file__).resolve().parent.parent / "output" / "forecast.json"

if __name__ == "__main__":
    funnel_metrics = json.loads(METRICS_PATH.read_text())
    result = compute_forecast(funnel_metrics)
    OUT_PATH.write_text(json.dumps(result, indent=2))

    conn = db.get_connection()
    db.insert_one(conn, "forecast_snapshots", {
        "run_timestamp": datetime.now().isoformat(timespec="seconds"),
        "payload_json": json.dumps(result),
    })
    conn.close()
    print(json.dumps(result, indent=2))

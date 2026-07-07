#!/usr/bin/env python3
"""CLI wrapper: batch-answers the 4 canonical RevOps questions and writes
output/copilot_report.json -- used by the dashboard's "AI Insights" tab so it
has a snapshot ready even when no ANTHROPIC_API_KEY is configured at demo time."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.copilot.revops_copilot import batch_canonical_report

OUT_PATH = Path(__file__).resolve().parent.parent / "output" / "copilot_report.json"

if __name__ == "__main__":
    result = batch_canonical_report()
    OUT_PATH.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))

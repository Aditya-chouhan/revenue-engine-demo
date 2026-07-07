#!/usr/bin/env python3
"""
Revenue Engine System -- standalone analytics dashboard (Streamlit).

Reads output/*.json (produced by scripts/02-05) -- never recomputes metrics
itself, so the dashboard can never silently drift from the numbers a
stranger could reproduce by re-running the scripts. The AI Copilot tab calls
src/copilot/revops_copilot.py live, so it always reflects whatever API key
(or lack of one) is set for the running session.

This is the reports-only entry point. For the full operational CRM UI
(list views, Kanban pipeline, record detail pages) see crm_app.py, which
embeds this same rendering code as its "Reports & Dashboards" tab --
src/ui/reports_view.py is the single source of truth both entry points read.

Run: streamlit run dashboard_app.py
"""
import json
import os
import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.ui.reports_view import (
    render_attribution,
    render_copilot,
    render_forecast,
    render_funnel,
    render_icp_segments,
    render_overview,
    render_rep_pipeline,
)

OUTPUT_DIR = PROJECT_ROOT / "output"

st.set_page_config(page_title="Revenue Engine System", layout="wide", page_icon="\U0001F4C8")


@st.cache_data
def load_json(name: str) -> dict:
    path = OUTPUT_DIR / f"{name}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())


funnel = load_json("funnel_metrics")
forecast = load_json("forecast")
attribution = load_json("attribution")
copilot_report = load_json("copilot_report")

if not funnel:
    st.error("output/funnel_metrics.json not found. Run scripts/01-05 first (see README.md).")
    st.stop()

st.title("Revenue Engine System")
st.caption(f"AI-native RevOps dashboard -- data as of {funnel.get('as_of')}. "
           f"Every number here is read from output/*.json, reproducible by re-running scripts/01-05.")

st.sidebar.header("AI RevOps Copilot")
api_key_input = st.sidebar.text_input(
    "Anthropic API key (optional)", type="password",
    help="Paste a key to have the Copilot tab call the real Claude API live. "
         "Never persisted to disk -- held only for this session. Leave blank to see the "
         "honest deterministic-fallback mode.",
)
if api_key_input:
    os.environ["ANTHROPIC_API_KEY"] = api_key_input
st.sidebar.caption(
    "Copilot mode: **live Claude API**" if os.environ.get("ANTHROPIC_API_KEY")
    else "Copilot mode: **deterministic fallback** (no key set)"
)
st.sidebar.divider()
st.sidebar.caption("Looking for the operational CRM UI (list views, Kanban pipeline, record "
                   "detail pages)? Run `streamlit run crm_app.py` instead -- separate entry point.")

tabs = st.tabs(["Overview", "Funnel", "Forecast", "Attribution", "ICP & Segments", "Rep Pipeline", "AI Copilot"])

with tabs[0]:
    render_overview(funnel, forecast)
with tabs[1]:
    render_funnel(funnel)
with tabs[2]:
    render_forecast(forecast)
with tabs[3]:
    render_attribution(attribution)
with tabs[4]:
    render_icp_segments(funnel)
with tabs[5]:
    render_rep_pipeline(funnel)
with tabs[6]:
    render_copilot(funnel, forecast, attribution, copilot_report)

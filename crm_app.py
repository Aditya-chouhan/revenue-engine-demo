#!/usr/bin/env python3
"""
Revenue Engine System -- operational CRM UI.

Styled in the visual language of Salesforce Lightning Experience (global
header, app tab bar, list views, Kanban pipeline, record detail pages with
a Path stepper and activity timeline) -- see README.md's framing note on
why this is "styled after," not a trademark claim to be the product itself.

This is the *operational* surface: browsing/searching/drilling into actual
CRM records (accounts, leads, opportunities). For the analytics-only view
(funnel/forecast/attribution charts), see dashboard_app.py -- both entry
points read the exact same data/revenue_engine.db and output/*.json, so
numbers never diverge between them.

Run: streamlit run crm_app.py
"""
import json
import os
import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.db import get_connection
from src.ui import pages_accounts, pages_home, pages_leads, pages_opportunities, pages_pipeline
from src.ui import data_access as da
from src.ui.reports_view import render_copilot, render_reports_tabs
from src.ui.theme import inject_base_css, render_global_header

OUTPUT_DIR = PROJECT_ROOT / "output"
NAV_ITEMS = ["Home", "Leads", "Accounts", "Pipeline", "Opportunities", "Reports & Dashboards", "Einstein Copilot"]

st.set_page_config(page_title="Revenue Cloud -- Revenue Engine System", layout="wide", page_icon="☁️")


@st.cache_data
def load_json(name: str) -> dict:
    path = OUTPUT_DIR / f"{name}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())


@st.cache_resource
def get_conn():
    return get_connection(check_same_thread=False)


funnel = load_json("funnel_metrics")
forecast = load_json("forecast")
attribution = load_json("attribution")
copilot_report = load_json("copilot_report")

if not funnel:
    st.error("output/funnel_metrics.json not found. Run scripts/01-06 first (see README.md).")
    st.stop()

if not Path(PROJECT_ROOT / "data" / "revenue_engine.db").exists():
    st.error("data/revenue_engine.db not found. Run scripts/01_generate_seed_data.py first (see README.md).")
    st.stop()

conn = get_conn()

inject_base_css()

alert_count = len(da.operational_alerts(conn, funnel.get("as_of"), limit=999))
render_global_header(alert_count=alert_count)

st.sidebar.header("AI RevOps Copilot")
api_key_input = st.sidebar.text_input(
    "Anthropic API key (optional)", type="password",
    help="Paste a key to have Einstein Copilot call the real Claude API live. "
         "Never persisted to disk -- held only for this session.",
)
if api_key_input:
    os.environ["ANTHROPIC_API_KEY"] = api_key_input
st.sidebar.caption(
    "Copilot mode: **live Claude API**" if os.environ.get("ANTHROPIC_API_KEY")
    else "Copilot mode: **deterministic fallback** (no key set)"
)
st.sidebar.divider()
st.sidebar.caption("Analytics-only view (no CRM chrome): `streamlit run dashboard_app.py`")

st.session_state.setdefault("active_tab", "Home")
if st.session_state.get("pending_tab"):
    # Widgets can't be written to st.session_state[key] after that widget has
    # already been instantiated in the current run (Streamlit raises
    # StreamlitAPIException) -- so cross-page "View ->" buttons stash the
    # target tab here and st.rerun(); this line applies it *before* the radio
    # below is created on the next run, which is the only point it's legal.
    st.session_state["active_tab"] = st.session_state.pop("pending_tab")
active = st.radio("Navigate", NAV_ITEMS, key="active_tab", horizontal=True, label_visibility="collapsed")

st.write("")  # small spacer between tab bar and content

if active == "Home":
    pages_home.render(conn, funnel)
elif active == "Leads":
    pages_leads.render(conn)
elif active == "Accounts":
    pages_accounts.render(conn)
elif active == "Pipeline":
    pages_pipeline.render(conn)
elif active == "Opportunities":
    pages_opportunities.render(conn)
elif active == "Reports & Dashboards":
    st.markdown("##### Reports & Dashboards")
    render_reports_tabs(funnel, forecast, attribution)
elif active == "Einstein Copilot":
    st.markdown("##### Einstein Copilot")
    render_copilot(funnel, forecast, attribution, copilot_report)

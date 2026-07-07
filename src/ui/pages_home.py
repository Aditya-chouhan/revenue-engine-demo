"""Home tab -- Lightning-style landing page: KPI tiles + real operational
alerts (not decorative) + recently created leads."""
import sqlite3

import streamlit as st

from src.ui import data_access as da
from src.ui.theme import money, stage_badge


def render(conn: sqlite3.Connection, funnel: dict) -> None:
    st.markdown("##### Good day, A. Chouhan")
    st.caption(f"Here's what's happening in your pipeline as of {funnel.get('as_of')}.")

    totals = funnel["totals"]
    pipeline = funnel["pipeline"]
    tiles = [
        ("Open Pipeline", money(pipeline["open_pipeline_monthly_value_usd"]) + "/mo"),
        ("Won MRR", money(pipeline["won_mrr_usd"]) + "/mo"),
        ("Open Leads", f"{totals['leads'] - totals['closed_won'] - totals['closed_lost']:,}"),
        ("Open Opportunities", f"{totals['opportunity']:,}"),
        ("Coverage Ratio", f"{pipeline['pipeline_coverage_ratio']}x"),
    ]
    cols = st.columns(len(tiles))
    for col, (label, value) in zip(cols, tiles):
        col.markdown(
            f'<div class="lex-card" style="text-align:center;">'
            f'<h4>{label}</h4><div style="font-size:1.4rem;font-weight:700;color:#181818;">{value}</div></div>',
            unsafe_allow_html=True,
        )

    st.divider()
    left, right = st.columns([3, 2])

    with left:
        st.markdown("###### Needs Attention")
        alerts = da.operational_alerts(conn, funnel.get("as_of"))
        if not alerts:
            st.caption("No SLA breaches or stalling opportunities right now.")
        for a in alerts:
            acol, bcol = st.columns([5, 1])
            acol.markdown(
                f'<div class="lex-alert"><b>{a["type"]}</b> &middot; {a["record"]}<br/>'
                f'<span style="color:#706E6B;">{a["detail"]}</span></div>',
                unsafe_allow_html=True,
            )
            if bcol.button("View", key=f"home_alert_{a['type']}_{a['lead_id']}"):
                st.session_state.selected_lead_id = a["lead_id"]
                st.session_state.pending_tab = "Leads"
                st.rerun()
        st.caption(
            "Rules straight from crm-system-design.md §3: MQL unactioned past SLA, "
            "Opportunity idle >10 business days with no logged activity."
        )

    with right:
        st.markdown("###### Recently Created Leads")
        for r in da.recent_records(conn, limit=8):
            c1, c2 = st.columns([4, 1])
            c1.markdown(
                f'<div class="lex-list-row"><b>{r["company_name"]}</b> {stage_badge(r["stage"])}<br/>'
                f'<span style="color:#706E6B;font-size:0.78rem;">{r["created_date"]} &middot; {r["owner_rep"]}</span></div>',
                unsafe_allow_html=True,
            )
            if c2.button("Open", key=f"home_recent_{r['lead_id']}"):
                st.session_state.selected_lead_id = r["lead_id"]
                st.session_state.pending_tab = "Leads"
                st.rerun()

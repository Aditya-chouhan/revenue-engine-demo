"""Pipeline: Kanban board of leads grouped by stage -- Salesforce Lightning's
"Kanban view" applied at the full lead-lifecycle grain (Lead..Closed), since
this schema's `leads.stage` -- not a narrower Opportunity sub-stage -- is
the canonical CRM lifecycle column (see crm-system-design.md §1)."""
import sqlite3

import streamlit as st

from src.ui import data_access as da
from src.ui.theme import STAGE_COLORS, money


def render(conn: sqlite3.Connection) -> None:
    st.markdown("##### Pipeline")
    owners = ["All"] + da.owner_reps(conn)
    owner = st.selectbox("Owner", owners, key="pipeline_owner")
    board = da.pipeline_by_stage(conn, owner_rep=None if owner == "All" else owner)

    st.markdown('<div class="kanban-board-marker"></div>', unsafe_allow_html=True)
    cols = st.columns(len(da.STAGES))
    for col, stage in zip(cols, da.STAGES):
        colors = STAGE_COLORS[stage]
        data = board[stage]
        with col:
            st.markdown(
                f'<div class="lex-kanban-col-header" style="background:{colors["fg"]};">'
                f'{stage} &middot; {data["count"]}</div>',
                unsafe_allow_html=True,
            )
            for card in data["cards"]:
                value_line = f'{money(card["deal_value_monthly_usd"])}/mo' if card.get("deal_value_monthly_usd") else f'score {card["lead_score"]:.1f}'
                st.markdown(
                    f'<div class="lex-kanban-card" style="--accent:{colors["fg"]};">'
                    f'<div class="name">{card["company_name"]}</div>'
                    f'<div class="meta">{value_line} &middot; {card["owner_rep"]}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                if st.button("View", key=f"kanban_{stage}_{card['lead_id']}"):
                    st.session_state.selected_lead_id = card["lead_id"]
                    st.session_state.pending_tab = "Leads"
                    st.rerun()
            if data["count"] > len(data["cards"]):
                st.caption(f"+{data['count'] - len(data['cards'])} more not shown")

    st.divider()
    st.caption(
        "Board shows up to 12 highest lead-score records per column. Fast-lane routing "
        "(signal score ≥ 8.0) and SLA-based reassignment are enforced upstream in "
        "src/crm/routing.py at generation time -- this view reads the resulting owner_rep, "
        "it doesn't recompute routing."
    )

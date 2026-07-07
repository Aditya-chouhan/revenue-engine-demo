"""Opportunities: list view (filters, pagination) + record detail page."""
import sqlite3

import streamlit as st

from src.ui import data_access as da
from src.ui.theme import activity_icon, money, pagination_bar, segment_badge, stage_badge

OPP_STAGES = ["Opportunity", "Closed Won", "Closed Lost"]


def render(conn: sqlite3.Connection) -> None:
    if st.session_state.get("selected_opp_id"):
        _render_detail(conn, st.session_state.selected_opp_id)
    else:
        _render_list(conn)


def _render_list(conn: sqlite3.Connection) -> None:
    st.markdown("##### Opportunities")
    f1, f2 = st.columns([2, 2])
    stage = f1.selectbox("Stage", ["All"] + OPP_STAGES, key="opps_stage")
    owners = ["All"] + da.owner_reps(conn)
    owner = f2.selectbox("Owner", owners, key="opps_owner")

    page = st.session_state.get("opps_page", 1)
    rows, total = da.list_opportunities(
        conn,
        stage=None if stage == "All" else stage,
        owner_rep=None if owner == "All" else owner,
        page=page,
    )
    pagination_bar(total, page, da.PAGE_SIZE, "opps_page")

    st.markdown(
        '<div class="lex-list-header"><div style="display:flex;">'
        '<div style="flex:3;">Account</div><div style="flex:1.5;">Stage</div>'
        '<div style="flex:2;">Deal Value</div><div style="flex:1.5;">Owner</div>'
        '<div style="flex:1.5;">Created</div><div style="flex:1;"></div></div></div>',
        unsafe_allow_html=True,
    )
    for r in rows:
        c1, c2, c3, c4, c5, c6 = st.columns([3, 1.5, 2, 1.5, 1.5, 1])
        c1.markdown(f"**{r['company_name']}** {segment_badge(r['segment'])}", unsafe_allow_html=True)
        c2.markdown(stage_badge(r["stage"]), unsafe_allow_html=True)
        c3.write(f"{money(r['deal_value_monthly_usd'])}/mo")
        c4.write(r["owner_rep"])
        c5.write(r["opp_created_date"])
        if c6.button("View", key=f"opp_view_{r['opp_id']}"):
            st.session_state.selected_opp_id = r["opp_id"]
            st.rerun()

    if not rows:
        st.info("No opportunities match these filters.")


def _render_detail(conn: sqlite3.Connection, opp_id: int) -> None:
    opp = da.get_opportunity_detail(conn, opp_id)
    if not opp:
        st.error("Opportunity not found.")
        if st.button("← Back to Opportunities"):
            st.session_state.selected_opp_id = None
            st.rerun()
        return

    if st.button("← Back to Opportunities"):
        st.session_state.selected_opp_id = None
        st.rerun()

    st.markdown(f"##### {opp['company_name']} &middot; Opportunity #{opp['opp_id']}", unsafe_allow_html=True)
    st.caption(f"{opp['category']} &middot; {opp['industry']} &middot; owned by {opp['owner_rep']}")
    st.markdown(stage_badge(opp["stage"]), unsafe_allow_html=True)

    t1, t2, t3, t4 = st.columns(4)
    t1.metric("Deal Value", f"{money(opp['deal_value_monthly_usd'])}/mo")
    t2.metric("Probability", f"{opp['probability_pct']}%" if opp.get("probability_pct") is not None else "n/a")
    t3.metric("Segment", opp["segment"] or "Unscored")
    t4.metric("ICP Fit", f"{opp['icp_fit_score']:.0f}" if opp.get("icp_fit_score") is not None else "n/a")

    left, right = st.columns([2, 3])
    with left:
        with st.container(border=True):
            st.markdown("**Details**")
            st.write(f"Created: **{opp['opp_created_date']}**")
            st.write(f"Closed: **{opp['closed_date'] or '--'}**")
            st.write(f"Outcome: **{opp['outcome'] or 'Open'}**")
            if opp.get("lost_reason"):
                st.write(f"Lost reason: **{opp['lost_reason']}**")
            if opp.get("lead") and st.button("View source Lead →", key=f"opp_to_lead_{opp['lead_id']}"):
                st.session_state.selected_lead_id = opp["lead_id"]
                st.session_state.pending_tab = "Leads"
                st.rerun()

    with right:
        st.markdown("**Activity Timeline**")
        activities = opp.get("activities", [])
        if not activities:
            st.caption("No activity logged yet.")
        for act in activities:
            st.markdown(
                f'<div class="lex-timeline-item">'
                f'<div class="lex-timeline-dot">{activity_icon(act["activity_type"])}</div>'
                f'<div><b>{act["activity_type"].replace("_", " ").title()}</b> via {act["channel"]}'
                f'<br/><span style="color:#706E6B;font-size:0.8rem;">{act["occurred_at"]}</span>'
                f'</div></div>',
                unsafe_allow_html=True,
            )

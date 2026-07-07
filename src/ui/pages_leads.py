"""Leads: list view (filters, search, pagination) + record detail page
(Path stepper, highlights, related account/contact, activity timeline)."""
import sqlite3

import streamlit as st

from src.ui import data_access as da
from src.ui.theme import activity_icon, money, pagination_bar, render_path, segment_badge, stage_badge

STAGES = ["Lead", "MQL", "SQL", "Opportunity", "Closed Won", "Closed Lost"]


def render(conn: sqlite3.Connection) -> None:
    if st.session_state.get("selected_lead_id"):
        _render_detail(conn, st.session_state.selected_lead_id)
    else:
        _render_list(conn)


def _render_list(conn: sqlite3.Connection) -> None:
    st.markdown("##### Leads")
    f1, f2, f3, f4 = st.columns([2, 2, 3, 2])
    stage = f1.selectbox("Stage", ["All"] + STAGES, key="leads_stage")
    owners = ["All"] + da.owner_reps(conn)
    owner = f2.selectbox("Owner", owners, key="leads_owner")
    search = f3.text_input("Search company", key="leads_search", placeholder="Type a company name...")
    sort_label = f4.selectbox("Sort by", ["Lead score (high-low)", "Created (newest)", "Company (A-Z)"], key="leads_sort")
    order_by = {
        "Lead score (high-low)": "l.lead_score DESC",
        "Created (newest)": "l.created_date DESC",
        "Company (A-Z)": "a.company_name ASC",
    }[sort_label]

    page = st.session_state.get("leads_page", 1)
    rows, total = da.list_leads(
        conn,
        stage=None if stage == "All" else stage,
        owner_rep=None if owner == "All" else owner,
        search=search or None,
        order_by=order_by,
        page=page,
    )
    pagination_bar(total, page, da.PAGE_SIZE, "leads_page")

    st.markdown(
        '<div class="lex-list-header"><div style="display:flex;">'
        '<div style="flex:3;">Company</div><div style="flex:1.5;">Stage</div>'
        '<div style="flex:1.5;">Owner</div><div style="flex:2;">Source</div>'
        '<div style="flex:1;">Score</div><div style="flex:1.5;">Created</div>'
        '<div style="flex:1;"></div></div></div>',
        unsafe_allow_html=True,
    )
    for r in rows:
        c1, c2, c3, c4, c5, c6, c7 = st.columns([3, 1.5, 1.5, 2, 1, 1.5, 1])
        c1.markdown(f"**{r['company_name']}** {segment_badge(r['segment'])}", unsafe_allow_html=True)
        c2.markdown(stage_badge(r["stage"]), unsafe_allow_html=True)
        c3.write(r["owner_rep"])
        c4.write(r["source_channel"])
        c5.write(f"{r['lead_score']:.1f}")
        c6.write(r["created_date"])
        if c7.button("View", key=f"lead_view_{r['lead_id']}"):
            st.session_state.selected_lead_id = r["lead_id"]
            st.rerun()

    if not rows:
        st.info("No leads match these filters.")


def _render_detail(conn: sqlite3.Connection, lead_id: int) -> None:
    lead = da.get_lead_detail(conn, lead_id)
    if not lead:
        st.error("Lead not found.")
        if st.button("← Back to Leads"):
            st.session_state.selected_lead_id = None
            st.rerun()
        return

    if st.button("← Back to Leads"):
        st.session_state.selected_lead_id = None
        st.rerun()

    st.markdown(f"##### {lead['company_name']} &middot; Lead #{lead['lead_id']}", unsafe_allow_html=True)
    st.caption(f"{lead['category']} &middot; {lead['industry']} &middot; owned by {lead['owner_rep']}")
    render_path(lead["stage"])

    t1, t2, t3, t4, t5 = st.columns(5)
    t1.metric("Lead Score", f"{lead['lead_score']:.1f}")
    t2.metric("Signal Score", f"{lead['signal_score']:.1f}")
    t3.metric("Engagement Score", f"{lead['engagement_score']:.1f}")
    t4.metric("ICP Fit", f"{lead['icp_fit_score']:.0f}" if lead["icp_fit_score"] is not None else "n/a")
    t5.metric("Segment", lead["segment"] or "Unscored")

    left, right = st.columns([2, 3])
    with left:
        with st.container(border=True):
            st.markdown("**Details**")
            st.write(f"Source channel: **{lead['source_channel']}**")
            st.write(f"Created: **{lead['created_date']}**")
            st.write(f"MQL date: **{lead['mql_date'] or '--'}**")
            st.write(f"SQL date: **{lead['sql_date'] or '--'}**")
            if lead.get("disqualified_reason"):
                st.write(f"Disqualified reason: **{lead['disqualified_reason']}**")
            st.write(f"Primary contact: **{lead['contact_name'] or '--'}** ({lead['contact_title'] or 'n/a'})")
            st.write(f"Employee band: **{lead['employee_band']}**")
            st.write(f"Website: {lead['website'] or '--'}")

        if lead.get("opportunity"):
            opp = lead["opportunity"]
            with st.container(border=True):
                st.markdown(f"**Opportunity** &middot; {stage_badge(opp['stage'])}", unsafe_allow_html=True)
                st.write(f"Deal value: **{money(opp['deal_value_monthly_usd'])}/mo**")
                st.write(f"Probability: **{opp['probability_pct']}%**" if opp.get("probability_pct") is not None else "")
                if opp.get("outcome"):
                    st.write(f"Outcome: **{opp['outcome']}**" + (f" ({opp['lost_reason']})" if opp.get("lost_reason") else ""))

    with right:
        st.markdown("**Activity Timeline**")
        activities = lead.get("activities", [])
        if not activities:
            st.caption("No activity logged yet.")
        for act in activities:
            notes_html = f'<br/><span style="font-size:0.8rem;">{act["notes"]}</span>' if act.get("notes") else ""
            st.markdown(
                f'<div class="lex-timeline-item">'
                f'<div class="lex-timeline-dot">{activity_icon(act["activity_type"])}</div>'
                f'<div><b>{act["activity_type"].replace("_", " ").title()}</b> via {act["channel"]}'
                f'<br/><span style="color:#706E6B;font-size:0.8rem;">{act["occurred_at"]}'
                f' &middot; touch #{act["touch_order"]}</span>'
                f'{notes_html}'
                f'</div></div>',
                unsafe_allow_html=True,
            )

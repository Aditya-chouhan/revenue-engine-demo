"""Accounts: list view (filters, search, pagination) + record detail page
with related lists (Contacts, Leads, Opportunities, Signals, Activity)."""
import sqlite3

import streamlit as st

from src.ui import data_access as da
from src.ui.theme import activity_icon, money, pagination_bar, segment_badge, stage_badge


def render(conn: sqlite3.Connection) -> None:
    if st.session_state.get("selected_account_id"):
        _render_detail(conn, st.session_state.selected_account_id)
    else:
        _render_list(conn)


def _render_list(conn: sqlite3.Connection) -> None:
    st.markdown("##### Accounts")
    f1, f2, f3 = st.columns([2, 2, 3])
    segments = ["All"] + da.segments(conn)
    segment = f1.selectbox("Segment", segments, key="accounts_segment")
    industries = ["All"] + da.industries(conn)
    industry = f2.selectbox("Industry", industries, key="accounts_industry")
    search = f3.text_input("Search company", key="accounts_search", placeholder="Type a company name...")

    page = st.session_state.get("accounts_page", 1)
    rows, total = da.list_accounts(
        conn,
        segment=None if segment == "All" else segment,
        industry=None if industry == "All" else industry,
        search=search or None,
        page=page,
    )
    pagination_bar(total, page, da.PAGE_SIZE, "accounts_page")

    st.markdown(
        '<div class="lex-list-header"><div style="display:flex;">'
        '<div style="flex:3;">Company</div><div style="flex:2;">Industry</div>'
        '<div style="flex:1.5;">Segment</div><div style="flex:1;">ICP Fit</div>'
        '<div style="flex:1;">Leads</div><div style="flex:1;">Opps</div>'
        '<div style="flex:1;"></div></div></div>',
        unsafe_allow_html=True,
    )
    for r in rows:
        c1, c2, c3, c4, c5, c6, c7 = st.columns([3, 2, 1.5, 1, 1, 1, 1])
        c1.write(f"**{r['company_name']}**")
        c2.write(r["industry"])
        c3.markdown(segment_badge(r["segment"]), unsafe_allow_html=True)
        c4.write(f"{r['icp_fit_score']:.0f}" if r["icp_fit_score"] is not None else "--")
        c5.write(r["lead_count"])
        c6.write(r["opp_count"])
        if c7.button("View", key=f"acct_view_{r['account_id']}"):
            st.session_state.selected_account_id = r["account_id"]
            st.rerun()

    if not rows:
        st.info("No accounts match these filters.")


def _render_detail(conn: sqlite3.Connection, account_id: int) -> None:
    acct = da.get_account_detail(conn, account_id)
    if not acct:
        st.error("Account not found.")
        if st.button("← Back to Accounts"):
            st.session_state.selected_account_id = None
            st.rerun()
        return

    if st.button("← Back to Accounts"):
        st.session_state.selected_account_id = None
        st.rerun()

    st.markdown(f"##### {acct['company_name']}", unsafe_allow_html=True)
    st.caption(f"{acct['category']} &middot; {acct['industry']} &middot; {acct['employee_band']} employees "
               f"&middot; created {acct['created_date']}")

    t1, t2, t3, t4 = st.columns(4)
    t1.metric("ICP Fit Score", f"{acct['icp_fit_score']:.0f}" if acct["icp_fit_score"] is not None else "n/a")
    t2.metric("Segment", acct["segment"] or "Unscored")
    t3.metric("Leads", len(acct["leads"]))
    t4.metric("Opportunities", len(acct["opportunities"]))

    rel_tabs = st.tabs(["Contacts", "Leads", "Opportunities", "Signals", "Activity"])

    with rel_tabs[0]:
        if not acct["contacts"]:
            st.caption("No contacts on file.")
        for c in acct["contacts"]:
            primary = " &middot; **Primary**" if c["is_primary"] else ""
            st.markdown(f"**{c['full_name']}** &mdash; {c['title']}{primary}<br/>"
                        f"<span style='color:#706E6B;'>{c['email']}</span>", unsafe_allow_html=True)
            st.divider()

    with rel_tabs[1]:
        for lead in acct["leads"]:
            c1, c2, c3 = st.columns([3, 2, 1])
            c1.markdown(stage_badge(lead["stage"]), unsafe_allow_html=True)
            c2.write(f"Score {lead['lead_score']:.1f} &middot; {lead['owner_rep']}", unsafe_allow_html=True)
            if c3.button("Open", key=f"acct_lead_{lead['lead_id']}"):
                st.session_state.selected_lead_id = lead["lead_id"]
                st.session_state.pending_tab = "Leads"
                st.rerun()
        if not acct["leads"]:
            st.caption("No leads on this account.")

    with rel_tabs[2]:
        for opp in acct["opportunities"]:
            c1, c2, c3 = st.columns([2, 2, 1])
            c1.markdown(stage_badge(opp["stage"]), unsafe_allow_html=True)
            c2.write(f"{money(opp['deal_value_monthly_usd'])}/mo &middot; {opp['owner_rep']}", unsafe_allow_html=True)
            if c3.button("Open", key=f"acct_opp_{opp['opp_id']}"):
                st.session_state.selected_opp_id = opp["opp_id"]
                st.session_state.pending_tab = "Opportunities"
                st.rerun()
        if not acct["opportunities"]:
            st.caption("No opportunities on this account.")

    with rel_tabs[3]:
        for s in acct["signals"]:
            st.write(f"**{s['signal_type'].replace('_', ' ').title()}** &mdash; value {s['signal_value']:.1f}, "
                     f"weight {s['weight']:.2f} &middot; detected {s['detected_date']}")
        if not acct["signals"]:
            st.caption("No external signals detected for this account.")

    with rel_tabs[4]:
        for act in acct["activities"]:
            st.markdown(f"{activity_icon(act['activity_type'])} **{act['activity_type'].replace('_', ' ').title()}** "
                        f"via {act['channel']} &middot; {act['occurred_at']}", unsafe_allow_html=True)
        if not acct["activities"]:
            st.caption("No activity logged yet.")

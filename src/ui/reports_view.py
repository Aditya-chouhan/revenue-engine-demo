"""
Analytics/reporting body shared by both Streamlit entry points:
  - dashboard_app.py  (standalone analytics-only dashboard)
  - crm_app.py         ("Reports & Dashboards" + "Einstein Copilot" tabs of the
                         full operational CRM UI)

Extracted so the funnel/forecast/attribution/segment charts exist in exactly
one place -- the two entry points render the same numbers from the same
output/*.json files, they just sit inside different navigation chrome.
"""
import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.copilot.revops_copilot import CANONICAL_QUESTIONS, answer_question

PALETTE = px.colors.qualitative.Set2


def render_reports_tabs(funnel: dict, forecast: dict, attribution: dict) -> None:
    """Renders Overview / Funnel / Forecast / Attribution / ICP & Segments /
    Rep Pipeline as a `st.tabs` block. Caller is responsible for page title."""
    tabs = st.tabs(["Overview", "Funnel", "Forecast", "Attribution", "ICP & Segments", "Rep Pipeline"])

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


def render_overview(funnel: dict, forecast: dict) -> None:
    totals = funnel["totals"]
    pipeline = funnel["pipeline"]
    cycle = funnel["sales_cycle_days"]
    expected_forecast = forecast.get("current_pipeline_stage_weighted_forecast", {}).get("scenarios", {}).get("expected", {})

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Open Pipeline Value", f"${pipeline['open_pipeline_monthly_value_usd']:,.0f}/mo")
    c2.metric("Won MRR", f"${pipeline['won_mrr_usd']:,.0f}/mo")
    c3.metric("Forecast (Expected, 30-90d)", f"${expected_forecast.get('forecast_new_mrr_usd', 0):,.0f}")
    c4.metric("Lead -> Won Rate", f"{funnel['overall_lead_to_won_pct']}%")
    c5.metric("Win Rate (Opp -> Won)", f"{funnel['funnel_conversion'][-1]['conversion_pct']}%")
    c6.metric("Avg Sales Cycle", f"{cycle['average']} days" if cycle["average"] else "n/a")

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Pipeline coverage")
        st.metric("Coverage ratio", f"{pipeline['pipeline_coverage_ratio']}x",
                   help=f"Open pipeline value / ${pipeline['quarterly_quota_mrr_usd_assumption']:,} quarterly quota assumption")
    with col2:
        st.subheader("Deal totals")
        st.write(f"**{totals['leads']:,}** leads -> **{totals['mql']:,}** MQL -> **{totals['sql']:,}** SQL -> "
                 f"**{totals['opportunity']:,}** Opportunities -> **{totals['closed_won']:,}** Won / **{totals['closed_lost']:,}** Lost")


def render_funnel(funnel: dict) -> None:
    st.subheader("Stage-by-stage conversion")
    conv_df = pd.DataFrame(funnel["funnel_conversion"])
    fig = go.Figure(go.Funnel(
        y=[c["from"] for c in funnel["funnel_conversion"]] + [funnel["funnel_conversion"][-1]["to"]],
        x=[c["from_n"] for c in funnel["funnel_conversion"]] + [funnel["funnel_conversion"][-1]["to_n"]],
        marker={"color": PALETTE[:5]},
    ))
    st.plotly_chart(fig, width="stretch")

    st.subheader("Conversion vs. published 2025-2026 benchmark ranges")
    display_df = conv_df.copy()
    display_df["stage"] = display_df["from"] + " -> " + display_df["to"]
    display_df["benchmark_range"] = display_df["benchmark_range_pct"].apply(
        lambda r: f"{r[0]}-{r[1]}%" if r else "n/a"
    )
    st.dataframe(
        display_df[["stage", "conversion_pct", "benchmark_range", "benchmark_flag"]]
        .rename(columns={"conversion_pct": "conversion_pct (%)"}),
        width="stretch", hide_index=True,
    )

    st.subheader("Lead Velocity Rate (month-over-month MQL growth)")
    lvr_df = pd.DataFrame(funnel["lead_velocity_rate"])
    fig2 = px.bar(lvr_df, x="month", y="leads", color_discrete_sequence=[PALETTE[0]])
    fig2.add_scatter(x=lvr_df["month"], y=lvr_df["mqls"], mode="lines+markers", name="MQLs", yaxis="y")
    st.plotly_chart(fig2, width="stretch")

    st.subheader("Stage dwell time (days)")
    st.json(funnel["stage_dwell_time_days"])


def render_forecast(forecast: dict) -> None:
    if not forecast:
        st.warning("output/forecast.json not found. Run scripts/03_run_forecast.py.")
        return
    st.subheader("Current pipeline: stage-weighted forecast scenarios")
    scen = forecast["current_pipeline_stage_weighted_forecast"]["scenarios"]
    scen_df = pd.DataFrame([
        {"scenario": k, "forecast_new_mrr_usd": v["forecast_new_mrr_usd"], "opp_win_rate": v["opp_win_rate"]}
        for k, v in scen.items()
    ])
    fig = px.bar(scen_df, x="scenario", y="forecast_new_mrr_usd", color="scenario",
                 color_discrete_sequence=PALETTE, text="forecast_new_mrr_usd")
    st.plotly_chart(fig, width="stretch")
    st.caption(forecast["methodology"]["stage_weighted"])

    st.subheader("Monthly cohort projection (next 3 months)")
    proj = forecast["monthly_projection_next_3_months"]
    proj_rows = []
    for m in proj:
        for scenario, val in m["projected_new_mrr_usd"].items():
            proj_rows.append({"month": m["month"], "scenario": scenario, "projected_new_mrr_usd": val})
    proj_df = pd.DataFrame(proj_rows)
    fig2 = px.line(proj_df, x="month", y="projected_new_mrr_usd", color="scenario", markers=True,
                    color_discrete_sequence=PALETTE)
    st.plotly_chart(fig2, width="stretch")
    st.caption(forecast["methodology"]["monthly_cohort"] +
               f" Assumed MoM lead growth: {forecast['assumptions']['avg_mom_lead_growth_pct']}%.")


def render_attribution(attribution: dict) -> None:
    if not attribution:
        st.warning("output/attribution.json not found. Run scripts/04_run_attribution.py.")
        return
    st.subheader("Revenue credit by channel -- 4 attribution models compared")
    st.caption(
        f"{attribution['n_won_deals_attributed']} of {attribution['n_won_deals_total']} won deals attributed "
        f"(${attribution['total_won_mrr_attributed_usd']:,.0f} total won MRR)."
    )
    rows = []
    for channel, models in attribution["revenue_credit_by_channel_usd"].items():
        for model, value in models.items():
            rows.append({"channel": channel, "model": model, "credit_usd": value})
    attr_df = pd.DataFrame(rows)
    fig = px.bar(attr_df, x="model", y="credit_usd", color="channel", barmode="group",
                 color_discrete_sequence=PALETTE)
    st.plotly_chart(fig, width="stretch")

    st.subheader("Which channel \"wins\" under each model")
    top = attribution["top_channel_by_model"]
    cols = st.columns(len(top))
    for col, (model, channel) in zip(cols, top.items()):
        col.metric(model, channel)
    st.caption(
        "First-touch and last-touch frequently disagree on which channel gets credit -- "
        "this divergence is the actual attribution-strategy conversation, not a data error."
    )

    with st.expander("Model definitions"):
        st.json(attribution["model_definitions"])


def render_icp_segments(funnel: dict) -> None:
    st.subheader("Segment performance (ICP fit-based)")
    seg_df = pd.DataFrame(funnel["segment_performance"]).T.reset_index().rename(columns={"index": "segment"})
    fig = px.bar(seg_df, x="segment", y="win_rate_pct", color="segment", color_discrete_sequence=PALETTE,
                 hover_data=["leads", "won_mrr"])
    st.plotly_chart(fig, width="stretch")
    st.dataframe(seg_df, width="stretch", hide_index=True)

    st.subheader("Industry performance")
    ind_df = pd.DataFrame(funnel["industry_performance"]).T.reset_index().rename(columns={"index": "industry"})
    fig2 = px.bar(ind_df, x="industry", y="won_mrr", color="industry", color_discrete_sequence=PALETTE)
    st.plotly_chart(fig2, width="stretch")


def render_rep_pipeline(funnel: dict) -> None:
    st.subheader("Rep-level pipeline")
    rep_df = pd.DataFrame(funnel["rep_pipeline"]).T.reset_index().rename(columns={"index": "rep"})
    col1, col2 = st.columns(2)
    with col1:
        fig = px.bar(rep_df, x="rep", y="leads", color="rep", color_discrete_sequence=PALETTE, title="Leads per rep")
        st.plotly_chart(fig, width="stretch")
    with col2:
        fig2 = px.bar(rep_df, x="rep", y="won_mrr", color="rep", color_discrete_sequence=PALETTE, title="Won MRR per rep")
        st.plotly_chart(fig2, width="stretch")
    st.dataframe(rep_df, width="stretch", hide_index=True)
    st.caption("Rep-lead-count is load-balanced by construction (crm/routing.py's weighted round-robin) -- "
               "see tests/test_analytics.py for the assertion this holds within ~2% of an even split.")


def render_copilot(funnel: dict, forecast: dict, attribution: dict, copilot_report: dict) -> None:
    st.subheader("Ask the RevOps Copilot")
    mode = "live Claude API call" if os.environ.get("ANTHROPIC_API_KEY") else "deterministic fallback engine (no API key set)"
    st.info(f"Current mode: **{mode}**. Every answer is labeled with which mode produced it -- "
            f"there is no path that fabricates a plausible-sounding answer disconnected from the data above.")

    question_mode = st.radio("Question", ["Pick a canonical question", "Ask something else (requires API key)"],
                              horizontal=True, key="copilot_question_mode")
    if question_mode == "Pick a canonical question":
        question = st.selectbox("Canonical questions", CANONICAL_QUESTIONS, key="copilot_canonical_q")
    else:
        question = st.text_input("Your question", placeholder="e.g. Is the Beauty category outperforming Pet?",
                                  key="copilot_free_q")

    if st.button("Ask", key="copilot_ask_btn") and question:
        payload = {"funnel_metrics": funnel, "forecast": forecast, "attribution": attribution}
        with st.spinner("Analyzing..."):
            result = answer_question(question, payload)
        st.markdown(f"**{result['generated_by']}**")
        st.write(result["answer"])
        if result.get("supporting_data"):
            with st.expander("Supporting data"):
                st.json(result["supporting_data"])
        if result.get("caveats"):
            st.caption("Caveats: " + " | ".join(result["caveats"]))

    if copilot_report:
        st.divider()
        st.subheader("Pre-generated batch report (output/copilot_report.json)")
        for ans in copilot_report.get("answers", []):
            with st.expander(ans["question"]):
                st.markdown(f"*{ans['generated_by']}*")
                st.write(ans["answer"])
                if ans.get("caveats"):
                    st.caption("Caveats: " + " | ".join(ans["caveats"]))

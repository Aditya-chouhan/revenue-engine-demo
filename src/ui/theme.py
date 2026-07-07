"""
Visual chrome for the operational CRM UI (crm_app.py).

Styled in the visual language of Salesforce Lightning Experience -- navy
header, blue accent, list-view/Kanban/record-detail conventions, stage
badges, a Path stepper -- using real Salesforce Lightning Design System
color tokens (all public design-system values, no proprietary font or
asset embedded). This is a portfolio piece designed "in the style of"
Lightning, not a trademark claim to be the Salesforce product itself --
see README.md's framing note.
"""
import streamlit as st

NAVY = "#16325C"
BLUE = "#0176D3"
BG = "#F3F2F2"
SURFACE = "#FFFFFF"
BORDER = "#DDDBDA"
TEXT_PRIMARY = "#181818"
TEXT_SECONDARY = "#3E3E3C"
TEXT_MUTED = "#706E6B"

STAGE_COLORS = {
    "Lead":         {"bg": "#F4F6F9", "fg": "#54698D"},
    "MQL":          {"bg": "#E3F3FF", "fg": "#0176D3"},
    "SQL":          {"bg": "#F4ECFB", "fg": "#8E4EC6"},
    "Opportunity":  {"bg": "#FFF4E5", "fg": "#B65C00"},
    "Closed Won":   {"bg": "#E9F6E9", "fg": "#2E844A"},
    "Closed Lost":  {"bg": "#FDEDEC", "fg": "#BA0517"},
}

STAGE_ORDER = ["Lead", "MQL", "SQL", "Opportunity", "Closed"]

SEGMENT_COLORS = {
    "Beachhead": {"bg": "#E9F6E9", "fg": "#2E844A"},
    "Core ICP": {"bg": "#E3F3FF", "fg": "#0176D3"},
    "Adjacent": {"bg": "#FFF4E5", "fg": "#B65C00"},
    "Poor Fit": {"bg": "#FDEDEC", "fg": "#BA0517"},
}

FONT_STACK = (
    "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
)


def inject_base_css() -> None:
    st.markdown(
        f"""
        <style>
        html, body, [class*="css"] {{ font-family: {FONT_STACK}; }}
        .stApp {{ background: {BG}; }}
        section[data-testid="stSidebar"] {{ background: {SURFACE}; border-right: 1px solid {BORDER}; }}
        #MainMenu, footer, header[data-testid="stHeader"] {{ visibility: hidden; height: 0; }}
        .block-container {{ padding-top: 0.5rem; max-width: 1400px; }}

        /* ---- Lightning global header bar ---- */
        .lex-header {{
            background: {NAVY};
            color: white;
            padding: 10px 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-radius: 6px;
            margin-bottom: 0;
        }}
        .lex-header .brand {{ display: flex; align-items: center; gap: 10px; font-weight: 700; font-size: 1.05rem; }}
        .lex-header .waffle {{
            width: 28px; height: 28px; border-radius: 4px; background: rgba(255,255,255,0.12);
            display: flex; align-items: center; justify-content: center; font-size: 14px; letter-spacing: -1px;
        }}
        .lex-header .right {{ display: flex; align-items: center; gap: 16px; font-size: 0.85rem; opacity: 0.95; }}
        .lex-header .avatar {{
            width: 30px; height: 30px; border-radius: 50%; background: #0176D3;
            display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 0.75rem;
        }}
        .lex-header .bell {{ position: relative; }}
        .lex-header .bell .dot {{
            position: absolute; top: -4px; right: -6px; background: #FE9339; color: #16325C;
            border-radius: 8px; font-size: 0.6rem; font-weight: 700; padding: 0px 4px;
        }}

        /* ---- App tab bar (like Lightning app nav tabs) ---- */
        div[data-testid="stRadio"] > label {{ display: none; }}
        div[data-testid="stRadioGroup"] {{
            background: {SURFACE}; border-bottom: 2px solid {BORDER};
            padding: 0 4px; gap: 4px !important; border-radius: 8px 8px 0 0;
        }}
        /* hide the circular radio indicator -- it's nested two levels inside
           the label (label > div > div > div:first-child is the dot icon;
           its sibling at that same depth is the stMarkdownContainer text,
           so we must not hide anything shallower or the text goes with it) */
        label[data-testid="stRadioOption"] > div > div > div:first-child {{ display: none; }}
        label[data-testid="stRadioOption"] {{
            padding: 12px 16px !important; margin: 0 !important;
            font-weight: 600; font-size: 0.85rem; color: {TEXT_MUTED};
            border-bottom: 3px solid transparent; border-radius: 0;
            cursor: pointer;
        }}
        label[data-testid="stRadioOption"][data-selected="true"] {{
            color: {BLUE}; border-bottom: 3px solid {BLUE};
        }}
        label[data-testid="stRadioOption"] div[data-testid="stMarkdownContainer"] p {{
            margin: 0; text-transform: uppercase; letter-spacing: 0.03em;
        }}

        /* ---- Cards / surfaces ---- */
        .lex-card {{
            background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 8px;
            padding: 16px 18px; margin-bottom: 12px;
        }}
        .lex-card h4 {{ margin: 0 0 10px 0; font-size: 0.78rem; text-transform: uppercase;
                         letter-spacing: 0.04em; color: {TEXT_MUTED}; }}

        /* ---- Badges ---- */
        .lex-badge {{
            display: inline-block; padding: 3px 10px; border-radius: 12px;
            font-size: 0.72rem; font-weight: 700; white-space: nowrap;
        }}

        /* ---- Path stepper ---- */
        .lex-path {{ display: flex; width: 100%; margin-bottom: 4px; }}
        .lex-path .step {{
            flex: 1; text-align: center; padding: 8px 4px; font-size: 0.72rem; font-weight: 700;
            color: white; position: relative; text-transform: uppercase; letter-spacing: 0.03em;
        }}
        .lex-path .step:not(:last-child)::after {{
            content: ""; position: absolute; right: -9px; top: 0; width: 0; height: 0;
            border-top: 15px solid transparent; border-bottom: 15px solid transparent;
            border-left: 10px solid var(--seg-color); z-index: 2;
        }}

        /* ---- Kanban ---- */
        .lex-kanban-col-header {{
            font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.03em;
            padding: 8px 10px; border-radius: 6px 6px 0 0; color: white;
        }}
        .lex-kanban-card {{
            background: {SURFACE}; border: 1px solid {BORDER}; border-left: 4px solid var(--accent, {BLUE});
            border-radius: 4px; padding: 8px 10px; margin-bottom: 8px; font-size: 0.8rem;
        }}
        .lex-kanban-card .name {{ font-weight: 700; color: {BLUE}; }}
        .lex-kanban-card .meta {{ color: {TEXT_MUTED}; font-size: 0.72rem; margin-top: 2px; }}

        /* ---- List rows ---- */
        .lex-list-header {{
            font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.03em;
            color: {TEXT_MUTED}; border-bottom: 2px solid {BORDER}; padding-bottom: 6px;
        }}
        .lex-list-row {{ border-bottom: 1px solid {BORDER}; padding: 8px 0; font-size: 0.85rem; }}
        .lex-alert {{
            background: #FFF8F1; border-left: 4px solid #FE9339; border-radius: 4px;
            padding: 8px 12px; margin-bottom: 6px; font-size: 0.82rem;
        }}

        /* ---- Timeline ---- */
        .lex-timeline-item {{ display: flex; gap: 10px; padding-bottom: 14px; position: relative; }}
        .lex-timeline-item::before {{
            content: ""; position: absolute; left: 13px; top: 26px; bottom: -2px; width: 2px; background: {BORDER};
        }}
        .lex-timeline-dot {{
            width: 27px; height: 27px; min-width: 27px; border-radius: 50%; background: {BLUE};
            color: white; display: flex; align-items: center; justify-content: center; font-size: 0.7rem; z-index: 1;
        }}
        button[kind="secondary"] {{ border-color: {BORDER} !important; }}

        /* ---- Responsive column behavior ----
           Streamlit's columns don't reflow on narrow viewports by default --
           they just shrink in place, which forces text (KPI labels, button
           labels like "Open"/"View") to wrap one character per line. Letting
           the row wrap onto multiple lines, and refusing to let text-bearing
           elements wrap character-by-character, fixes both. */
        div[data-testid="stHorizontalBlock"] {{
            flex-wrap: wrap;
            row-gap: 10px;
        }}
        div[data-testid="stColumn"] {{
            min-width: 170px;
        }}
        div[data-testid="stColumn"]:has(.stButton) {{
            min-width: 68px;
            flex-shrink: 0;
        }}
        .stButton button {{
            white-space: nowrap;
        }}
        .lex-card h4, .lex-list-header, .lex-kanban-col-header {{
            overflow-wrap: break-word;
            word-break: normal;
        }}

        /* ---- Kanban board: scroll horizontally instead of wrapping ----
           A 6-stage board wrapping onto multiple rows would put Stage 1
           underneath Stage 4, which reads as broken, not responsive. Real
           Lightning Kanban boards scroll sideways instead -- so the row
           right after the .kanban-board-marker sentinel (emitted by
           pages_pipeline.py) is pinned to nowrap + given its own scrollbar,
           overriding the generic wrap-everything rule above. */
        div[data-testid="stElementContainer"]:has(.kanban-board-marker)
            + div[data-testid="stLayoutWrapper"] div[data-testid="stHorizontalBlock"] {{
            flex-wrap: nowrap;
            overflow-x: auto;
            padding-bottom: 10px;
        }}
        div[data-testid="stElementContainer"]:has(.kanban-board-marker)
            + div[data-testid="stLayoutWrapper"] div[data-testid="stColumn"] {{
            min-width: 174px;
            flex-shrink: 0;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_global_header(current_user: str = "A. Chouhan", alert_count: int = 0) -> None:
    initials = "".join(p[0] for p in current_user.replace(".", "").split()[:2]).upper()
    st.markdown(
        f"""
        <div class="lex-header">
            <div class="brand">
                <div class="waffle">&#9638;&#9638;<br/>&#9638;&#9638;</div>
                Acme SaaS &middot; Revenue Cloud
            </div>
            <div class="right">
                <span>&#128269;&nbsp;Search accounts, leads, opportunities&hellip;</span>
                <span class="bell">&#128276;{f'<span class="dot">{alert_count}</span>' if alert_count else ''}</span>
                <div class="avatar">{initials}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def badge(label: str, bg: str, fg: str) -> str:
    return f'<span class="lex-badge" style="background:{bg};color:{fg};">{label}</span>'


def stage_badge(stage: str) -> str:
    c = STAGE_COLORS.get(stage, {"bg": "#F4F6F9", "fg": TEXT_MUTED})
    return badge(stage, c["bg"], c["fg"])


def segment_badge(segment: str | None) -> str:
    if not segment:
        return badge("Unscored", "#F4F6F9", TEXT_MUTED)
    c = SEGMENT_COLORS.get(segment, {"bg": "#F4F6F9", "fg": TEXT_MUTED})
    return badge(segment, c["bg"], c["fg"])


def money(value: float | None) -> str:
    if value is None:
        return "--"
    return f"${value:,.0f}"


def render_path(current_stage: str, outcome: str | None = None) -> None:
    """Salesforce-style Path stepper: completed steps green, current step blue,
    future steps gray. Closed Lost renders the final segment red instead of green."""
    steps = ["Lead", "MQL", "SQL", "Opportunity", "Closed"]
    effective = "Closed" if current_stage in ("Closed Won", "Closed Lost") else current_stage
    try:
        current_idx = steps.index(effective)
    except ValueError:
        current_idx = 0
    html = ['<div class="lex-path">']
    for i, s in enumerate(steps):
        if s == "Closed" and current_stage == "Closed Lost":
            color = "#BA0517"
        elif i < current_idx:
            color = "#2E844A"
        elif i == current_idx:
            color = BLUE
        else:
            color = "#C9C7C5"
        label = s if s != "Closed" else current_stage if current_stage.startswith("Closed") else "Closed"
        html.append(f'<div class="step" style="--seg-color:{color}; background:{color};">{label}</div>')
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


ACTIVITY_ICONS = {
    "call": "\U0001F4DE",
    "email": "\U00002709",
    "meeting": "\U0001F4C5",
    "signal_event": "\U0001F4E1",
    "content_view": "\U0001F4C4",
}


def activity_icon(activity_type: str) -> str:
    return ACTIVITY_ICONS.get(activity_type, "\U0001F4CC")


def pagination_bar(total: int, page: int, page_size: int, state_key: str) -> None:
    """Shared Prev/Next pager for list views. `state_key` is the
    st.session_state key holding the current page number for that list."""
    import math

    import streamlit as st

    pages = max(1, math.ceil(total / page_size))
    a, b, c = st.columns([3, 1, 1])
    a.caption(f"Showing page {page} of {pages} &middot; {total:,} total records")
    if b.button("◀ Prev", disabled=page <= 1, key=f"{state_key}_prev"):
        st.session_state[state_key] = page - 1
        st.rerun()
    if c.button("Next ▶", disabled=page >= pages, key=f"{state_key}_next"):
        st.session_state[state_key] = page + 1
        st.rerun()

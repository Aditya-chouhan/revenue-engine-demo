"""
Read-only query layer for the operational CRM UI (crm_app.py).

Every function here is a plain, inspectable SQL query against
data/revenue_engine.db via src/db.py's connection helper -- no ORM, no
query builder, same "no black-box logic" principle the rest of this
project follows. This module owns *composition* of queries for UI screens
(list views, record detail, related lists); it does not duplicate any
scoring/routing/lifecycle business logic, which stays in src/crm,
src/segmentation, src/signals.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

from src.db import fetch_all, fetch_one, rows_to_dicts

PAGE_SIZE = 25


# ---------------------------------------------------------------- Leads ----
def list_leads(
    conn: sqlite3.Connection,
    stage: str | None = None,
    owner_rep: str | None = None,
    search: str | None = None,
    order_by: str = "lead_score DESC",
    page: int = 1,
) -> tuple[list[dict], int]:
    where = []
    params: list = []
    if stage:
        where.append("l.stage = ?")
        params.append(stage)
    if owner_rep:
        where.append("l.owner_rep = ?")
        params.append(owner_rep)
    if search:
        where.append("a.company_name LIKE ?")
        params.append(f"%{search}%")
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    total = fetch_one(
        conn,
        f"SELECT COUNT(*) AS n FROM leads l JOIN accounts a ON a.account_id = l.account_id {where_sql}",
        tuple(params),
    )["n"]

    offset = (page - 1) * PAGE_SIZE
    rows = fetch_all(
        conn,
        f"""
        SELECT l.lead_id, l.stage, l.owner_rep, l.source_channel, l.created_date,
               l.signal_score, l.engagement_score, l.lead_score, l.mql_date, l.sql_date,
               a.account_id, a.company_name, a.segment, a.industry
        FROM leads l JOIN accounts a ON a.account_id = l.account_id
        {where_sql}
        ORDER BY {order_by}
        LIMIT ? OFFSET ?
        """,
        tuple(params) + (PAGE_SIZE, offset),
    )
    return rows_to_dicts(rows), total


def get_lead_detail(conn: sqlite3.Connection, lead_id: int) -> dict | None:
    row = fetch_one(
        conn,
        """
        SELECT l.*, a.company_name, a.category, a.industry, a.segment, a.icp_fit_score,
               a.employee_band, a.website,
               c.full_name AS contact_name, c.title AS contact_title, c.email AS contact_email
        FROM leads l
        JOIN accounts a ON a.account_id = l.account_id
        LEFT JOIN contacts c ON c.contact_id = l.contact_id
        WHERE l.lead_id = ?
        """,
        (lead_id,),
    )
    if not row:
        return None
    lead = dict(row)
    opp = fetch_one(conn, "SELECT * FROM opportunities WHERE lead_id = ?", (lead_id,))
    lead["opportunity"] = dict(opp) if opp else None
    activities = fetch_all(
        conn,
        "SELECT * FROM activities WHERE lead_id = ? ORDER BY touch_order ASC",
        (lead_id,),
    )
    lead["activities"] = rows_to_dicts(activities)
    return lead


# ------------------------------------------------------------- Accounts ----
def list_accounts(
    conn: sqlite3.Connection,
    segment: str | None = None,
    industry: str | None = None,
    search: str | None = None,
    order_by: str = "icp_fit_score DESC",
    page: int = 1,
) -> tuple[list[dict], int]:
    where = []
    params: list = []
    if segment:
        where.append("segment = ?")
        params.append(segment)
    if industry:
        where.append("industry = ?")
        params.append(industry)
    if search:
        where.append("company_name LIKE ?")
        params.append(f"%{search}%")
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    total = fetch_one(conn, f"SELECT COUNT(*) AS n FROM accounts {where_sql}", tuple(params))["n"]
    offset = (page - 1) * PAGE_SIZE
    rows = fetch_all(
        conn,
        f"""
        SELECT a.*,
               (SELECT COUNT(*) FROM leads l WHERE l.account_id = a.account_id) AS lead_count,
               (SELECT COUNT(*) FROM opportunities o WHERE o.account_id = a.account_id) AS opp_count
        FROM accounts a
        {where_sql}
        ORDER BY {order_by}
        LIMIT ? OFFSET ?
        """,
        tuple(params) + (PAGE_SIZE, offset),
    )
    return rows_to_dicts(rows), total


def get_account_detail(conn: sqlite3.Connection, account_id: int) -> dict | None:
    row = fetch_one(conn, "SELECT * FROM accounts WHERE account_id = ?", (account_id,))
    if not row:
        return None
    account = dict(row)
    account["contacts"] = rows_to_dicts(
        fetch_all(conn, "SELECT * FROM contacts WHERE account_id = ? ORDER BY is_primary DESC", (account_id,))
    )
    account["leads"] = rows_to_dicts(
        fetch_all(conn, "SELECT * FROM leads WHERE account_id = ? ORDER BY created_date DESC", (account_id,))
    )
    account["opportunities"] = rows_to_dicts(
        fetch_all(conn, "SELECT * FROM opportunities WHERE account_id = ? ORDER BY opp_created_date DESC", (account_id,))
    )
    account["signals"] = rows_to_dicts(
        fetch_all(conn, "SELECT * FROM signals WHERE account_id = ? ORDER BY detected_date DESC", (account_id,))
    )
    account["activities"] = rows_to_dicts(
        fetch_all(
            conn,
            "SELECT * FROM activities WHERE account_id = ? ORDER BY occurred_at DESC LIMIT 20",
            (account_id,),
        )
    )
    return account


# --------------------------------------------------------- Opportunities ----
def list_opportunities(
    conn: sqlite3.Connection,
    stage: str | None = None,
    owner_rep: str | None = None,
    order_by: str = "deal_value_monthly_usd DESC",
    page: int = 1,
) -> tuple[list[dict], int]:
    where = []
    params: list = []
    if stage:
        where.append("o.stage = ?")
        params.append(stage)
    if owner_rep:
        where.append("o.owner_rep = ?")
        params.append(owner_rep)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    total = fetch_one(conn, f"SELECT COUNT(*) AS n FROM opportunities o {where_sql}", tuple(params))["n"]
    offset = (page - 1) * PAGE_SIZE
    rows = fetch_all(
        conn,
        f"""
        SELECT o.*, a.company_name, a.segment
        FROM opportunities o JOIN accounts a ON a.account_id = o.account_id
        {where_sql}
        ORDER BY {order_by}
        LIMIT ? OFFSET ?
        """,
        tuple(params) + (PAGE_SIZE, offset),
    )
    return rows_to_dicts(rows), total


def get_opportunity_detail(conn: sqlite3.Connection, opp_id: int) -> dict | None:
    row = fetch_one(
        conn,
        """
        SELECT o.*, a.company_name, a.category, a.industry, a.segment, a.icp_fit_score
        FROM opportunities o JOIN accounts a ON a.account_id = o.account_id
        WHERE o.opp_id = ?
        """,
        (opp_id,),
    )
    if not row:
        return None
    opp = dict(row)
    lead = fetch_one(conn, "SELECT * FROM leads WHERE lead_id = ?", (opp["lead_id"],))
    opp["lead"] = dict(lead) if lead else None
    opp["activities"] = rows_to_dicts(
        fetch_all(conn, "SELECT * FROM activities WHERE lead_id = ? ORDER BY touch_order ASC", (opp["lead_id"],))
    )
    return opp


# ---------------------------------------------------------- Pipeline/Kanban ----
STAGES = ["Lead", "MQL", "SQL", "Opportunity", "Closed Won", "Closed Lost"]


def pipeline_by_stage(conn: sqlite3.Connection, owner_rep: str | None = None, per_column_limit: int = 12) -> dict:
    where = "WHERE l.owner_rep = ?" if owner_rep else ""
    params = (owner_rep,) if owner_rep else ()
    board = {}
    for stage in STAGES:
        stage_where = f"{where} {'AND' if where else 'WHERE'} l.stage = ?"
        count = fetch_one(
            conn, f"SELECT COUNT(*) AS n FROM leads l {stage_where}", params + (stage,)
        )["n"]
        rows = fetch_all(
            conn,
            f"""
            SELECT l.lead_id, l.owner_rep, l.lead_score, l.source_channel,
                   a.company_name, a.segment,
                   o.deal_value_monthly_usd
            FROM leads l
            JOIN accounts a ON a.account_id = l.account_id
            LEFT JOIN opportunities o ON o.lead_id = l.lead_id
            {stage_where}
            ORDER BY l.lead_score DESC
            LIMIT ?
            """,
            params + (stage, per_column_limit),
        )
        board[stage] = {"count": count, "cards": rows_to_dicts(rows)}
    return board


# ------------------------------------------------------------- Home/alerts ----
def owner_reps(conn: sqlite3.Connection) -> list[str]:
    rows = fetch_all(conn, "SELECT DISTINCT owner_rep FROM leads ORDER BY owner_rep")
    return [r["owner_rep"] for r in rows]


def segments(conn: sqlite3.Connection) -> list[str]:
    rows = fetch_all(conn, "SELECT DISTINCT segment FROM accounts WHERE segment IS NOT NULL ORDER BY segment")
    return [r["segment"] for r in rows]


def industries(conn: sqlite3.Connection) -> list[str]:
    rows = fetch_all(conn, "SELECT DISTINCT industry FROM accounts ORDER BY industry")
    return [r["industry"] for r in rows]


def operational_alerts(conn: sqlite3.Connection, as_of: str, limit: int = 8) -> list[dict]:
    """Real rule-driven alerts, straight from crm-system-design.md's automation
    table -- not decorative. Two rules implemented against actual rows:
      1. MQL unactioned past its 6-business-hour SLA -> here approximated at
         the day grain the dataset supports: MQL for 2+ days with no sql_date.
      2. Opportunity idle >10 business days with no logged activity.
    `as_of` is the dataset's own generation-time anchor (funnel_metrics.json's
    `as_of`), not wall-clock today -- the synthetic dataset lives in a fixed
    Feb-2026..as_of window, so "today" for staleness math must be relative to
    that, exactly like the forecast/copilot modules already do.
    """
    as_of_dt = datetime.fromisoformat(as_of)
    alerts = []

    stale_mql = fetch_all(
        conn,
        """
        SELECT l.lead_id, a.company_name, l.mql_date, l.owner_rep
        FROM leads l JOIN accounts a ON a.account_id = l.account_id
        WHERE l.stage = 'MQL' AND l.mql_date IS NOT NULL
        ORDER BY l.mql_date ASC
        """,
    )
    for row in stale_mql:
        mql_dt = datetime.fromisoformat(row["mql_date"])
        days_stale = (as_of_dt - mql_dt).days
        if days_stale >= 2:
            alerts.append(
                {
                    "type": "MQL past SLA",
                    "record": row["company_name"],
                    "lead_id": row["lead_id"],
                    "detail": f"{days_stale}d unactioned, owner {row['owner_rep']}",
                }
            )

    idle_opps = fetch_all(
        conn,
        """
        SELECT o.opp_id, o.lead_id, a.company_name, o.owner_rep,
               (SELECT MAX(occurred_at) FROM activities WHERE lead_id = o.lead_id) AS last_activity
        FROM opportunities o JOIN accounts a ON a.account_id = o.account_id
        WHERE o.stage = 'Opportunity'
        """,
    )
    for row in idle_opps:
        if not row["last_activity"]:
            continue
        last_dt = datetime.fromisoformat(row["last_activity"])
        idle_days = (as_of_dt - last_dt).days
        if idle_days >= 10:
            alerts.append(
                {
                    "type": "Opportunity stalling",
                    "record": row["company_name"],
                    "lead_id": row["lead_id"],
                    "detail": f"{idle_days}d idle, owner {row['owner_rep']}",
                }
            )

    alerts.sort(key=lambda a: a["detail"], reverse=True)
    return alerts[:limit]


def recent_records(conn: sqlite3.Connection, limit: int = 8) -> list[dict]:
    rows = fetch_all(
        conn,
        """
        SELECT l.lead_id, a.company_name, l.stage, l.created_date, l.owner_rep
        FROM leads l JOIN accounts a ON a.account_id = l.account_id
        ORDER BY l.created_date DESC
        LIMIT ?
        """,
        (limit,),
    )
    return rows_to_dicts(rows)

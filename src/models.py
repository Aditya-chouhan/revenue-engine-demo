"""
Dataclasses mirroring db/schema.sql. These are the in-memory shape used by
the seed generator and the crm/* logic modules before rows are persisted --
one definition of "what a Lead is," shared by every module that touches one.
"""
from dataclasses import dataclass, field


@dataclass
class Account:
    account_id: int
    company_name: str
    category: str
    industry: str
    employee_band: str
    created_date: str
    website: str | None = None
    icp_fit_score: float | None = None
    segment: str | None = None


@dataclass
class Contact:
    contact_id: int
    account_id: int
    full_name: str
    title: str
    email: str
    is_primary: int = 0


@dataclass
class Activity:
    activity_id: int
    lead_id: int
    account_id: int
    activity_type: str
    channel: str
    touch_order: int
    occurred_at: str
    contact_id: int | None = None
    notes: str | None = None


@dataclass
class Signal:
    signal_id: int
    account_id: int
    signal_type: str
    signal_value: float
    weight: float
    detected_date: str


@dataclass
class Lead:
    lead_id: int
    account_id: int
    source_channel: str
    created_date: str
    signal_score: float
    engagement_score: float
    lead_score: float
    owner_rep: str
    contact_id: int | None = None
    stage: str = "Lead"
    mql_date: str | None = None
    sql_date: str | None = None
    disqualified_reason: str | None = None
    # Set by LeadLifecycle.advance(..., "Opportunity", deal_value_monthly_usd=...);
    # the authoritative copy lives on the Opportunity row once persisted -- this is
    # the in-flight value while the Lead object is still being advanced.
    deal_value_monthly_usd: float | None = None
    lost_reason: str | None = None
    activities: list[Activity] = field(default_factory=list)


@dataclass
class Opportunity:
    opp_id: int
    lead_id: int
    account_id: int
    owner_rep: str
    stage: str
    deal_value_monthly_usd: float
    opp_created_date: str
    closed_date: str | None = None
    outcome: str | None = None
    lost_reason: str | None = None
    probability_pct: float | None = None

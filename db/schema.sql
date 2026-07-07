-- Revenue Engine System v2 -- normalized relational schema.
--
-- Written for SQLite (zero-setup, runs anywhere python3 runs) but using only
-- Postgres-portable constructs: explicit FKs, no SQLite-only pragmas baked
-- into the DDL itself. Two notes for a Postgres port:
--   1. `INTEGER PRIMARY KEY` here is SQLite's rowid-alias autoincrement;
--      in Postgres this becomes `id BIGSERIAL PRIMARY KEY` (or
--      `GENERATED ALWAYS AS IDENTITY`).
--   2. Dates are stored as ISO-8601 TEXT (`YYYY-MM-DD`); Postgres would use
--      native DATE/TIMESTAMP columns. TEXT was chosen here so the schema
--      needs zero driver-specific type handling in src/db.py.
--
-- funnel_snapshots / forecast_snapshots / attribution_snapshots persist the
-- computed-output tables the brief asks for (funnel_metrics, forecasts,
-- attribution) as timestamped JSON blobs -- the derivation logic lives in
-- Python (src/analytics/*), not duplicated in SQL, so there is exactly one
-- place that defines "how a conversion rate is computed."

PRAGMA foreign_keys = ON;

CREATE TABLE accounts (
    account_id      INTEGER PRIMARY KEY,
    company_name    TEXT NOT NULL,
    category        TEXT NOT NULL,       -- product category (Beauty, Baby, Home, ...)
    industry        TEXT NOT NULL,       -- broader industry grouping (Health & Beauty, ...)
    website         TEXT,
    employee_band   TEXT NOT NULL,       -- firmographic proxy: "1-10","11-50","51-200","201-500"
    icp_fit_score   REAL,                -- 0-100, set by src/segmentation/icp.py
    segment         TEXT,                -- Beachhead / Core ICP / Adjacent / Poor Fit
    created_date    TEXT NOT NULL
);

CREATE TABLE contacts (
    contact_id      INTEGER PRIMARY KEY,
    account_id      INTEGER NOT NULL REFERENCES accounts(account_id) ON DELETE CASCADE,
    full_name       TEXT NOT NULL,
    title           TEXT NOT NULL,
    email           TEXT NOT NULL,
    is_primary      INTEGER NOT NULL DEFAULT 0   -- 0/1 boolean
);

CREATE TABLE leads (
    lead_id             INTEGER PRIMARY KEY,
    account_id          INTEGER NOT NULL REFERENCES accounts(account_id) ON DELETE CASCADE,
    contact_id          INTEGER REFERENCES contacts(contact_id) ON DELETE SET NULL,
    source_channel      TEXT NOT NULL,        -- first-touch channel, denormalized for quick reads
    created_date        TEXT NOT NULL,
    stage               TEXT NOT NULL DEFAULT 'Lead',  -- Lead/MQL/SQL/Opportunity/Closed Won/Closed Lost
    signal_score         REAL NOT NULL,        -- 0-10, rolled up from signals table at generation time
    engagement_score     REAL NOT NULL,        -- 0-10, derived from activity volume/recency
    lead_score           REAL NOT NULL,        -- composite: see src/crm/scoring.py
    owner_rep            TEXT NOT NULL,        -- assigned by src/crm/routing.py
    mql_date             TEXT,
    sql_date             TEXT,
    disqualified_reason   TEXT
);

CREATE TABLE opportunities (
    opp_id                  INTEGER PRIMARY KEY,
    lead_id                 INTEGER NOT NULL REFERENCES leads(lead_id) ON DELETE CASCADE,
    account_id              INTEGER NOT NULL REFERENCES accounts(account_id) ON DELETE CASCADE,
    owner_rep               TEXT NOT NULL,
    stage                   TEXT NOT NULL,     -- Opportunity / Closed Won / Closed Lost
    deal_value_monthly_usd  REAL NOT NULL,
    opp_created_date         TEXT NOT NULL,
    closed_date              TEXT,
    outcome                  TEXT,              -- Won / Lost / NULL (still open)
    lost_reason               TEXT,
    probability_pct           REAL              -- stage-implied close probability at time of last update
);

CREATE TABLE activities (
    activity_id     INTEGER PRIMARY KEY,
    lead_id         INTEGER NOT NULL REFERENCES leads(lead_id) ON DELETE CASCADE,
    account_id      INTEGER NOT NULL REFERENCES accounts(account_id) ON DELETE CASCADE,
    contact_id      INTEGER REFERENCES contacts(contact_id) ON DELETE SET NULL,
    activity_type   TEXT NOT NULL,      -- call / email / meeting / signal_event / content_view
    channel         TEXT NOT NULL,      -- Signal-scored inbound / Outbound LinkedIn / Cold email sequence / Referral / Content/organic
    touch_order     INTEGER NOT NULL,   -- 1 = first touch on this lead, ascending
    occurred_at     TEXT NOT NULL,
    notes           TEXT
);

CREATE TABLE signals (
    signal_id       INTEGER PRIMARY KEY,
    account_id      INTEGER NOT NULL REFERENCES accounts(account_id) ON DELETE CASCADE,
    signal_type     TEXT NOT NULL,   -- rank_collapse / buy_box_loss / review_cluster / hiring_proxy / usage_spike / funding_event
    signal_value    REAL NOT NULL,   -- 0-10 raw severity/strength
    weight          REAL NOT NULL,   -- contribution weight into account-level signal_score, see src/signals/signal_engine.py
    detected_date   TEXT NOT NULL
);

CREATE TABLE funnel_snapshots (
    snapshot_id     INTEGER PRIMARY KEY,
    run_timestamp   TEXT NOT NULL,
    payload_json    TEXT NOT NULL
);

CREATE TABLE forecast_snapshots (
    snapshot_id     INTEGER PRIMARY KEY,
    run_timestamp   TEXT NOT NULL,
    payload_json    TEXT NOT NULL
);

CREATE TABLE attribution_snapshots (
    snapshot_id     INTEGER PRIMARY KEY,
    run_timestamp   TEXT NOT NULL,
    payload_json    TEXT NOT NULL
);

CREATE INDEX idx_contacts_account ON contacts(account_id);
CREATE INDEX idx_leads_account ON leads(account_id);
CREATE INDEX idx_leads_owner ON leads(owner_rep);
CREATE INDEX idx_leads_stage ON leads(stage);
CREATE INDEX idx_opportunities_lead ON opportunities(lead_id);
CREATE INDEX idx_opportunities_account ON opportunities(account_id);
CREATE INDEX idx_activities_lead ON activities(lead_id);
CREATE INDEX idx_activities_account ON activities(account_id);
CREATE INDEX idx_signals_account ON signals(account_id);

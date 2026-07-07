# Architecture — Revenue Engine System v2

## Schema (text ER diagram)

```
accounts (1) ──< contacts (many)
accounts (1) ──< signals (many)          [distress/firmographic signal events]
accounts (1) ──< leads (many)            [~9% of accounts have 2 leads -- undeduplicated
                                           multi-channel discovery, a documented gap not a bug]
leads (1)    ──< activities (many)       [2-6 touches/lead, ordered by touch_order -- attribution backbone]
leads (1)    ──1 opportunities (0 or 1)  [created only once a lead reaches "Opportunity" stage]
contacts (1) ──< leads, activities       [optional FK -- a lead's primary contact]

funnel_snapshots / forecast_snapshots / attribution_snapshots
    -- timestamped JSON blobs, one row per script run, the audit trail
       the brief's data-model section asks for. Computation logic lives
       in src/analytics/*.py, not duplicated in SQL.
```

Full DDL: `db/schema.sql`. Written for SQLite (the runnable target) using
only Postgres-portable constructs -- see the file's header comment for the
two-line diff a real Postgres port would need (`INTEGER PRIMARY KEY` ->
`BIGSERIAL PRIMARY KEY`, `TEXT` dates -> `DATE`/`TIMESTAMP`).

**Why plain `sqlite3`, no ORM:** every query is either in `src/db.py`'s
handful of named helpers or spelled out directly in `src/analytics/*.py`.
Nothing is generated or hidden -- the brief explicitly asks to avoid
black-box logic, and an ORM's query-generation layer is exactly the kind of
thing that obscures "how was this number computed."

## Module map

```
src/db.py                    connection + schema-init + generic insert/fetch helpers
src/models.py                dataclasses mirroring the schema (Account, Contact, Lead, Opportunity, Activity, Signal)

src/crm/scoring.py            composite lead_score = 40% ICP fit + 30% signal + 30% engagement (weights justified in-module)
src/crm/routing.py            RoutingEngine: weighted round-robin + signal>=8.0 fast lane + SLA reassignment
src/crm/lifecycle.py          LeadLifecycle state machine: enforces crm-system-design.md's stage-gate required fields

src/segmentation/icp.py       ICP definition (extends Clay project's Amazon-seller distress ICP) + 0-100 fit scorer + segment buckets
src/signals/signal_engine.py  simulated external signal events -> account-level signal_score rollup

src/analytics/funnel.py       stage conversion, drop-off, LVR, cycle time, coverage ratio, benchmark flags
src/analytics/forecasting.py  stage-weighted pipeline forecast + monthly cohort projection
src/analytics/attribution.py  first/last/linear/U-shaped multi-touch revenue attribution

src/copilot/revops_copilot.py AI analyst: real Claude API call (if ANTHROPIC_API_KEY set) or deterministic
                               fallback engine -- same output schema, honestly labeled either way

src/ui/                       operational CRM UI building blocks (crm_app.py's layers)
    theme.py                    Lightning-style CSS injection, badges, Path stepper, Kanban/timeline chrome
    data_access.py               read-only query layer: list views (filter/search/paginate) + record
                                  detail + related lists, plain sqlite3 -- same no-ORM rule as src/db.py
    reports_view.py               analytics rendering shared by crm_app.py's "Reports & Dashboards" /
                                   "Einstein Copilot" tabs AND standalone dashboard_app.py -- one
                                   implementation, two navigation shells
    pages_home.py                  KPI tiles + real rule-driven alerts (data_access.operational_alerts)
    pages_leads.py                  Leads list view + record detail (Path stepper, activity timeline)
    pages_accounts.py                Accounts list view + record detail (5 related-list tabs)
    pages_pipeline.py                 Kanban board: leads grouped by src/crm/lifecycle.py's 6 stages
    pages_opportunities.py             Opportunities list view + record detail

scripts/01-06                 CLI pipeline: generate -> funnel -> forecast -> attribution -> copilot report -> CSV export
crm_app.py                     operational CRM UI (primary) -- header/nav chrome, dispatches to src/ui/pages_*
dashboard_app.py                analytics-only Streamlit UI -- reads output/*.json, calls the copilot live
dashboard.html                   static no-install fallback -- same numbers, hand-authored SVG
```

## Data flow

```
scripts/01_generate_seed_data.py
    -> writes accounts/contacts/leads/opportunities/activities/signals to data/revenue_engine.db
    -> owner_rep assignment goes through src/crm/routing.py (not random.choice)
    -> every stage transition goes through src/crm/lifecycle.py (required-field gates enforced)
    -> signal_score comes from src/signals/signal_engine.py (auditable in `signals` table)
    -> icp_fit_score/segment come from src/segmentation/icp.py and change conversion odds

scripts/02_run_funnel_metrics.py   reads DB -> src/analytics/funnel.py -> output/funnel_metrics.json (+ snapshot row)
scripts/03_run_forecast.py         reads funnel_metrics.json -> src/analytics/forecasting.py -> output/forecast.json
scripts/04_run_attribution.py      reads DB -> src/analytics/attribution.py -> output/attribution.json
scripts/05_run_copilot_report.py   reads output/*.json -> src/copilot/revops_copilot.py -> output/copilot_report.json
scripts/06_export_csv.py           reads DB -> data/crm_leads_export.csv (data portability)

dashboard_app.py / dashboard.html   read output/*.json only -- never recompute, so they can never drift
                                     from what scripts/02-05 would reproduce on a stranger's clone

crm_app.py   reads data/revenue_engine.db directly (via src/ui/data_access.py) for record-level
             list/detail views, AND output/*.json (via src/ui/reports_view.py, same as dashboard_app.py)
             for its Reports & Dashboards / Einstein Copilot tabs -- the DB is the source of truth for
             individual records, the JSON snapshots are the source of truth for aggregate metrics; the UI
             layer never recomputes either, it only queries/reads
```

## Design decisions worth naming

- **SQLite, not Postgres.** Zero-setup, clones and runs anywhere `python3`
  runs -- important for a portfolio repo a stranger might clone cold.
  `db/schema.sql` is written to be Postgres-portable so the brief's
  "SQLite/Postgres" choice is honestly satisfied without actually standing
  up a Postgres instance for a demo dataset.
- **Snapshot tables, not live-recomputed tables, for funnel/forecast/
  attribution.** The derivation logic (what counts as a conversion, how a
  forecast is weighted) lives in exactly one place -- Python -- rather than
  being re-implemented in SQL and risking the two definitions drifting apart.
- **Segments have teeth.** `icp.CONVERSION_MULTIPLIER` actually changes
  simulated conversion odds by segment in the generator -- segmentation
  shows up in the funnel numbers, not just as a report label.
- **The AI Copilot never fabricates.** Every answer -- API or fallback --
  is built by reading `output/*.json` and either citing a number in it or
  saying the data doesn't support an answer. The "Why is pipeline down?"
  handler explicitly checks whether pipeline is actually declining before
  answering, and excludes the current partial month from that check the
  same way the forecast model does, so it can't be fooled by a low-volume
  partial month into reporting a false decline.
- **`crm_app.py` is styled after Lightning, not a trademark claim to be it.**
  Header/tab-bar/list-view/Kanban/Path/record-detail are Salesforce Lightning
  Experience *UI conventions* (public design-system concepts any CRM can use)
  implemented with original CSS and no Salesforce assets, fonts, or code --
  chosen because it's the most recognizable enterprise-CRM visual language
  for a portfolio reviewer to instantly place, not because this claims any
  affiliation with Salesforce.
- **Cached SQLite connection needs `check_same_thread=False` in the UI
  layer, nowhere else.** `st.cache_resource` shares one connection object
  across Streamlit's per-session worker threads; sqlite3 rejects that by
  default. `src/db.py`'s `get_connection()` takes a `check_same_thread` flag
  (default `True`, preserving the safe default for every `scripts/*.py` CLI
  entry point) -- only `crm_app.py`'s cached connection passes `False`, and
  only because src/ui/* is read-only (no concurrent-write risk).
- **Two known, named debts** (not hidden): (1) `crm-system-design.md` §2.3's
  category-specialization routing rule is designed but deliberately not
  activated -- same governance call v1 made, still correct at this sample
  size; (2) CAC/retention KPIs are not modeled -- no spend or renewal data
  exists to compute them honestly.

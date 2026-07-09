# Revenue Engine System v2 — AI-Native RevOps Platform

**Built:** 2026-07-07 · **Data:** 100% synthetic (seed=42, reproducible) · **Status:** closed (v2)

> **Supersedes v1** (also built 2026-07-07, same day — kept in git history).
> v1 was a flat-CSV dataset + three standalone scripts + a static dashboard.
> v2 rebuilds it as a production-grade system: a normalized SQLite CRM,
> executable routing/lifecycle logic (not just a design doc), multi-touch
> attribution, an ICP/segmentation engine, a simulated signal-ingestion
> layer, and an AI RevOps Copilot.

**Write-up:** https://aditya-chouhan.github.io/revenue-engine-demo/
**Dashboard:** https://aditya-chouhan.github.io/revenue-engine-demo/dashboard.html
**Live operational CRM:** https://revenue-engine-demo-crzmn3vxfxzbt6qetnqwb4.streamlit.app

No Sydon code, data, or credentials used anywhere in this repo. Built on a
synthetic 2,080-lead dataset since I don't have a real book of business to
publish (Sydon AI employment ended 2026-07-05, and that data isn't mine to
reuse).

## What this is

An end-to-end, AI-native RevOps system simulating how a modern B2B SaaS
company runs its GTM engine: lead generation → qualification → pipeline →
revenue → forecasting → executive reporting → AI-assisted analysis. Built to
demonstrate GTM Engineer / RevOps Lead competencies with real, inspectable
code — not a slide deck describing what a system like this would do.

## What changed from v1 (kept in git history, not deleted)

| v1 | v2 |
|---|---|
| Flat `data/crm_leads.csv`, one row per lead | Normalized SQLite (`db/schema.sql`): accounts, contacts, leads, opportunities, activities, signals |
| `owner_rep = random.choice(REPS)` | `src/crm/routing.py`: real weighted round-robin + signal-score fast lane + SLA reassignment, load-balance asserted in tests |
| Stage transitions were just CSV field-fills | `src/crm/lifecycle.py`: a state machine that raises on missing required fields (no Opportunity without deal value, no Closed Lost without a reason) |
| `signal_score = random.uniform(3.0, 9.5)` | `src/signals/signal_engine.py`: simulated signal events (rank collapse, Buy Box loss, hiring/usage proxies) rolled up per account, auditable in the `signals` table |
| ICP "inherited from the Clay project" by assertion | `src/segmentation/icp.py`: scored 0-100 fit + segment buckets that measurably change conversion odds in the funnel |
| One `channel` field per lead | `activities` table: 2-6 timestamped, channel-tagged touches per lead |
| No attribution model | `src/analytics/attribution.py`: first-touch, last-touch, linear, U-shaped — and they disagree on which channel wins |
| No AI layer | `src/copilot/revops_copilot.py`: real Claude API call or an honestly-labeled deterministic fallback, never fabricated |
| Static hand-authored `dashboard.html` only | `dashboard_app.py` (Streamlit, primary/interactive) + `dashboard.html` (refreshed, static no-install fallback) |

Full schema/module rationale: **`ARCHITECTURE.md`**.

## Two UIs: operational CRM vs. analytics dashboard

This project ships **two separate Streamlit entry points** reading the exact
same `data/revenue_engine.db` / `output/*.json`, so their numbers can never
diverge:

- **`crm_app.py` — the operational CRM.** Styled in the visual language of
  Salesforce Lightning Experience (global header, app tab bar, list views
  with filters/search/pagination, a Kanban pipeline board, record detail
  pages with a Path stepper and an activity timeline). This is the surface a
  rep or RevOps admin would actually live in day to day: browsing accounts,
  drilling into a lead, checking what's stalling. **Framing note:** this is
  a portfolio piece designed *in the style of* Lightning's UI conventions
  (its color tokens, list-view/Kanban/record-detail/Path patterns are public
  design-system concepts) — it is not a claim to be the Salesforce product,
  use any Salesforce trademark/asset, or run on Salesforce's platform.
- **`dashboard_app.py` — the analytics-only dashboard.** The original 7-tab
  reporting view (Overview, Funnel, Forecast, Attribution, ICP & Segments,
  Rep Pipeline, AI Copilot) for when you just want the numbers, no CRM
  chrome. `crm_app.py`'s own "Reports & Dashboards" and "Einstein Copilot"
  tabs render this same content — `src/ui/reports_view.py` is the one place
  that logic lives, imported by both entry points.

## Project structure

```
.
├── README.md                 this file
├── ARCHITECTURE.md           schema diagram, module map, design rationale
├── crm-system-design.md      lifecycle/routing/automation/governance design (now executable, see src/crm/)
├── requirements.txt          pandas, streamlit, plotly, anthropic
├── db/schema.sql             normalized SQLite DDL (Postgres-portable types)
├── src/
│   ├── db.py, models.py
│   ├── crm/{scoring,routing,lifecycle}.py
│   ├── segmentation/icp.py
│   ├── signals/signal_engine.py
│   ├── analytics/{funnel,forecasting,attribution}.py
│   ├── copilot/revops_copilot.py
│   └── ui/                    operational CRM UI (crm_app.py's building blocks)
│       ├── theme.py            Lightning-style CSS, badges, Path stepper, Kanban/timeline chrome
│       ├── data_access.py      read-only query layer for list views + record detail + related lists
│       ├── reports_view.py     shared analytics rendering (imported by both crm_app.py and dashboard_app.py)
│       └── pages_{home,leads,accounts,pipeline,opportunities}.py
├── scripts/01-06              generate -> funnel -> forecast -> attribution -> copilot report -> CSV export
├── crm_app.py                   operational CRM UI (primary -- list views, Kanban, record detail)
├── dashboard_app.py             analytics-only Streamlit dashboard
├── dashboard.html                static no-install fallback (analytics only)
├── data/revenue_engine.db        generated SQLite DB (gitignored)
├── output/*.json                 funnel_metrics, forecast, attribution, copilot_report
└── tests/test_analytics.py       conversion/attribution/routing/lifecycle sanity tests
```

## How to run

```bash
git clone https://github.com/Aditya-chouhan/revenue-engine-demo.git
cd revenue-engine-demo
python3 -m venv .venv && source .venv/bin/activate      # isolated env -- do not install into a shared/global venv
pip install -r requirements.txt

python3 scripts/01_generate_seed_data.py     # ~1,900 accounts, 2,080 leads, ~8,400 activities -> data/revenue_engine.db
python3 scripts/02_run_funnel_metrics.py     # -> output/funnel_metrics.json
python3 scripts/03_run_forecast.py           # -> output/forecast.json
python3 scripts/04_run_attribution.py        # -> output/attribution.json
python3 scripts/05_run_copilot_report.py     # -> output/copilot_report.json (works with zero API keys configured)
python3 scripts/06_export_csv.py             # -> data/crm_leads_export.csv (optional, data portability)

python3 -m pytest tests/test_analytics.py -v # 10 sanity tests

streamlit run crm_app.py                     # operational CRM UI, http://localhost:8501
# -- or --
streamlit run dashboard_app.py               # analytics-only dashboard
# Optional (either app): export ANTHROPIC_API_KEY=sk-... before launching (or
# paste it in the sidebar) to have the AI Copilot / Einstein Copilot tab call
# the real Claude API instead of its deterministic fallback.
```

Or open `dashboard.html` directly in a browser for the no-install static view
(same numbers, refreshed from the same `output/*.json` this README cites),
or visit the hosted **[live operational CRM](https://revenue-engine-demo-crzmn3vxfxzbt6qetnqwb4.streamlit.app)** — no install required.

## GTM Impact / Revenue Impact

- **Designed and executed a full Lead→MQL→SQL→Opportunity→Closed CRM
  lifecycle** as enforced code, not just a design doc: `src/crm/lifecycle.py`
  raises on missing required fields at each stage gate (no Opportunity
  without a deal-value estimate, no Closed Lost without an enumerated
  reason), and `src/crm/routing.py`'s weighted round-robin + signal≥8.0 fast
  lane lands rep load within **1.7%** of an even three-way split across
  2,080 leads (683 / 692 / 705) — asserted directly in `tests/test_analytics.py`,
  not just claimed in a README.
- **Built a normalized 6-table relational schema** (accounts, contacts,
  leads, opportunities, activities, signals) from a flat CSV, with FK
  constraints, indexes, and a documented Postgres-porting path.
- **Shipped a working ICP/segmentation engine**: accounts score 0-100 on
  category + firmographic + signal fit, bucketing into Beachhead / Core ICP
  / Adjacent / Poor Fit — and Beachhead accounts convert at **4.3×** Core
  ICP's Lead→Won rate (1.62% vs. 0.38%, on 1,109 vs. 799 leads), proving the
  segmentation changes real funnel behavior rather than just labeling it.
- **Built multi-touch attribution** across 4 standard models (first/last/
  linear/U-shaped) over ~8,400 timestamped touches — first-touch and
  linear both credit Outbound LinkedIn as the top channel ($14,050 /
  $11,498), but last-touch credits Signal-scored inbound instead ($9,950) —
  a genuine attribution-strategy decision point, not a data artifact.
- **Built a two-method revenue forecast**: stage-weighted on this dataset's
  own SQL→Opp→Won conversion history ($21.6K–$50.3K new MRR depending on
  win-rate scenario) plus a monthly cohort projection extrapolating the
  trailing lead-volume trend three months forward (Aug–Oct 2026).
- **Shipped an AI RevOps Copilot** that answers "why is pipeline down,"
  "which stage is underperforming," "where should sales focus," and "which
  segment converts best" by reading the exact computed data above — real
  Claude API call if a key is configured, an honestly-labeled deterministic
  analyst engine if not, never a fabricated-sounding answer either way.
- **Shipped two dashboards**: an interactive Streamlit app (7 tabs, live AI
  Copilot Q&A) and a refreshed static HTML fallback for no-install viewing.
- **Shipped a full operational CRM UI** (`crm_app.py`), not just reporting:
  list views with filters/search/pagination across all 2,080 leads / 1,906
  accounts / 104 opportunities, a Kanban pipeline board grouped by the same
  6 lifecycle stages `src/crm/lifecycle.py` enforces, and record detail
  pages with a Path stepper and a real activity timeline — styled in the
  visual language of Salesforce Lightning Experience, reading the same
  `data/revenue_engine.db` the analytics dashboard reads so the two never
  disagree on a number.

## Benchmark sources (2025-2026)

- Lead→MQL / MQL→SQL / SQL→Opportunity / Opportunity→Won ranges: [2025 B2B SaaS Funnel Benchmarks & Pipeline Audit Framework](https://thedigitalbloom.com/learn/pipeline-performance-benchmarks-2025/), [MQL to SQL Conversion Rates by Industry (2026 Data)](https://www.data-mania.com/blog/mql-to-sql-conversion-rate-benchmarks-2025/), [Lead Conversion Rate Benchmarks 2026 (Full Funnel)](https://prospeo.io/s/lead-conversion-rate-benchmarks)
- Sales cycle length by segment (SMB 30-45 days vs. enterprise 120 days): [B2B Sales Funnel Stages: 2026 Guide With Benchmarks](https://prospeo.io/s/b2b-sales-funnel-stages)
- Pipeline coverage ratio by segment (high-velocity SMB 1.7-2.5x, mid-market 2.5-4x, enterprise 4-7x; win-rate-implied ratio = 1/win rate): [Pipeline Coverage Ratio: What It Is, How to Calculate It | Landbase](https://www.landbase.com/blog/pipeline-coverage-ratio-calculate-2026), [Healthy Pipeline Coverage | Salesmotion](https://salesmotion.io/blog/healthy-pipeline-coverage), [Pipeline Coverage Ratio | Clari](https://www.clari.com/blog/pipeline-coverage-best-practices/)
- Weighted-pipeline forecasting formula (stage value × close probability): [Sales Pipeline Coverage: Formula, Ratios & Forecast Impact](https://forecastio.ai/blog/pipeline-coverage)

Re-verify these if this project is cited in an interview more than 90 days
from 2026-07-07.

## What's not yet built (named explicitly, not hidden)

- **Category-specialization routing** (`crm-system-design.md` §2.3) is
  designed but deliberately not activated — insufficient per-rep/per-category
  sample size to trust a win-rate difference isn't noise.
- **CAC and retention KPIs** are not modeled — no ad-spend or subscription-
  renewal event data exists to compute them honestly.
- **No live Postgres deployment.** `db/schema.sql` is written to be
  Postgres-portable (see its header comment for the exact two changes a port
  would need) but the runnable system here is SQLite-only, by design, for
  zero-setup portfolio review.
- **Stale-lead auto-archive** (45-day decay rule, `crm-system-design.md` §4)
  is designed but not implemented in the generator.
- **Kanban board is click-to-view, not drag-to-advance.** `crm_app.py`'s
  Pipeline tab renders cards grouped by stage (a real Salesforce/HubSpot
  list-view pattern), but moving a card between columns via drag-and-drop
  isn't wired up — stage changes still go through `src/crm/lifecycle.py`'s
  `advance()`, which is the actual stage-gate logic being demonstrated.
- **Header search bar is chrome, not a live global search.** The magnifying-
  glass field in `crm_app.py`'s header bar is visual only; each object's own
  list-view search box (Leads/Accounts) is the real, working search.

## Suggestions for future improvement

1. Add a spend log + renewal/churn event stream to unlock CAC and net-
   revenue-retention metrics honestly.
2. Activate category-specialization routing once per-rep/per-category
   sample size crosses the n>30 threshold `crm-system-design.md` §2.3 sets.
3. Add a live-refresh mode to `dashboard_app.py` that re-runs scripts/01-05
   on a schedule rather than reading static `output/*.json`.
4. Extend `src/copilot/revops_copilot.py`'s free-form question path with a
   lightweight retrieval layer (e.g. also querying `data/revenue_engine.db`
   directly) so the API path isn't limited to the pre-aggregated JSON
   payload for novel questions.
5. Wire real drag-and-drop on the Pipeline Kanban board (e.g. via a small
   custom Streamlit component) that calls `src/crm/lifecycle.py`'s
   `advance()` on drop, so a stage move in the UI is the same code path the
   seed generator already exercises, not just a click-through.
6. Make the header search bar functional (substring match across accounts/
   leads/opportunities with a results dropdown) instead of decorative chrome.

Aditya Chouhan · ai.adityachouhan@gmail.com

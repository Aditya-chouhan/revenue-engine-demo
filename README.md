# Revenue Engine Demo — public demo

A full Lead → MQL → SQL → Opportunity → Closed CRM lifecycle, computed funnel
and pipeline metrics, and a two-method revenue forecast — built on a
synthetic 2,080-lead dataset since I don't have a real book of business to
publish (Sydon AI employment ended 2026-07-05, and that data isn't mine to
reuse).

**Write-up:** https://aditya-chouhan.github.io/revenue-engine-demo/
**Dashboard:** https://aditya-chouhan.github.io/revenue-engine-demo/dashboard.html

No Sydon code, data, or credentials used anywhere in this repo.

## Run it yourself

```
python3 scripts/01_generate_crm_data.py   # deterministic, seed=42 — same output every run
python3 scripts/02_funnel_metrics.py      # -> output/funnel_metrics.json
python3 scripts/03_forecast_model.py      # -> output/forecast.json
```

No API key required, no dependencies beyond the Python standard library.

## What it does

1. **Generates** a synthetic CRM dataset (`scripts/01_generate_crm_data.py`)
   — 2,080 leads across 6 months, each with a channel, an owner, a signal
   score, and full stage-transition timestamps. Conversion and cycle-length
   assumptions are calibrated to published 2025–2026 SMB/high-velocity B2B
   benchmarks (cited in the write-up), not invented.
2. **Designs the CRM system** that would produce that data in production —
   `crm-system-design.md`: stage entry/exit criteria and SLAs, a weighted
   round-robin lead-routing rule with a signal-score fast lane, an
   automation-workflow table, and data-hygiene/governance rules.
3. **Computes funnel & pipeline metrics** (`scripts/02_funnel_metrics.py`)
   — stage-wise conversion and drop-off, sales cycle length, Lead Velocity
   Rate, pipeline coverage ratio, channel attribution, rep-level pipeline —
   every number re-derived from the CSV, nothing hand-typed.
4. **Forecasts revenue** (`scripts/03_forecast_model.py`) two ways: a
   stage-weighted model using the dataset's own historical win rates (not a
   generic industry assumption), and a monthly cohort projection three
   months out, both with worst/expected/best scenarios.
5. **Ships a dashboard** (`dashboard.html`) — pipeline health, funnel,
   channel attribution, forecast, rep-level QA. Self-contained, dark-mode
   aware, no external dependencies.

## Honesty notes

- The dataset is synthetic and says so on every page — it demonstrates the
  CRM-design, funnel-math, and forecasting methodology, not a real revenue
  number.
- Conversion rates and forecast bounds are pinned to cited published
  benchmarks so the numbers are defensible, not just plausible-sounding.
- What's explicitly *not* built is named in the write-up rather than
  papered over: stale-lead decay is designed but not simulated, category-
  specialized routing is designed but deliberately not activated (too
  little sample size to trust it yet), and CAC/retention aren't modeled
  because there's no spend or renewal data to compute them honestly.

Aditya Chouhan · ai.adityachouhan@gmail.com

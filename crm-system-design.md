# CRM System Design — Lead Lifecycle, Routing, Automation, Governance

Design spec for the CRM system that produces `data/revenue_engine.db` in
production. This is the artifact that answers "have you designed a CRM
system," independent of which vendor (HubSpot/Salesforce/Attio/Pipedrive)
implements it — the schema, routing logic, and automation rules are the
transferable competency; the vendor is an implementation detail.

**v2 update:** this design is no longer just a spec — §2 (routing) and §4
(stage-gate hygiene) are now executable code in `src/crm/routing.py` and
`src/crm/lifecycle.py` respectively, exercised by the seed generator and
asserted in `tests/test_analytics.py`. Section references below point to
the code that now implements each rule.

## 1. Lead lifecycle: stage definitions

| Stage | Entry criteria | Exit criteria | Owner | SLA |
|---|---|---|---|---|
| **Lead** | Company/contact identified via any source channel (signal-scored inbound, outbound, referral, content). No qualification yet. | Signal-scored ≥ 3.0 (below floor = auto-archived, not deleted — see §4) | Unassigned / channel pool | Scored within 1 hour of creation (automated) |
| **MQL** (Marketing Qualified Lead) | Signal score crosses category-specific threshold (behavioral/firmographic fit) *and* a minimum engagement signal exists (site visit, reply, or the distress-signal event itself for signal-scored inbound) | Rep makes first qualifying contact and confirms budget/authority/need/timing (BANT-lite) | Assigned rep | Rep must action within 6 business hours (measured Lead→MQL median: 3.5 days incl. weekends — see funnel metrics) |
| **SQL** (Sales Qualified Lead) | Rep confirms BANT-lite in a live conversation; lead accepts a scoping/discovery call | Discovery call completed *and* a specific problem + rough deal shape is documented | Assigned rep | Discovery call booked within 3 business days of SQL |
| **Opportunity** | Discovery complete, deal value estimated, proposal in progress or sent | Prospect returns a Won/Lost decision | Assigned rep + deal-desk review if value > $1,500/mo | Follow-up cadence every 5 business days |
| **Closed Won** | Contract signed | — (hands off to onboarding/CS, outside this CRM's scope) | Assigned rep → CS handoff | Handoff within 24 hours |
| **Closed Lost** | Prospect declines, goes cold (no response after 3 attempts across 15 days), or fails budget/fit check | — | Assigned rep | `lost_reason` is a required field — see §4 |

Stage-dwell benchmarks used to set the SLAs above are the *measured* values
from `output/funnel_metrics.json` (`stage_dwell_time_days`), not assumptions
— this is a real design decision informed by the dataset the CRM itself
would produce, i.e., the SLA table gets re-tuned every quarter against
actual dwell time, not set once and left static.

## 2. Lead routing logic

Three reps (`A. Chouhan`, `R. Iyer`, `S. Kapoor`) receive leads under a
**weighted round-robin with signal-score override**:

1. **Default**: strict round-robin across all three reps at Lead creation,
   for even pipeline load (this dataset's rep-level leads counts land within
   3% of an even three-way split — 710 / 639 / 731 — confirming the routing
   logic works as designed, see `output/funnel_metrics.json` → `rep_pipeline`).
2. **Override — high-signal fast lane**: any lead scoring ≥ 8.0 skips the
   round-robin queue and routes directly to whichever rep has the *lowest
   current open-SQL count* (load-balance on active work, not raw lead count)
   — because a high-signal lead decays fast (distress signals are
   time-sensitive; a seller's rating-collapse window closes) and the
   marginal cost of round-robin queueing is a lost deal, not just a slower
   one.
3. **Category specialization** (not yet in this dataset, flagged as a v2
   design decision): route Beauty/Skin-category leads preferentially to
   whichever rep has the highest historical win rate in that category once
   n > 30 per rep/category — insufficient sample size in the current
   dataset to activate this rule yet (see §4, data-hygiene note on
   premature segmentation).
4. **Reassignment trigger**: if a Lead sits unactioned past its SLA (§1),
   it re-enters the round-robin queue rather than staying orphaned on the
   original rep — this is the single most common CRM hygiene failure
   (leads dying silently on a rep's desk) and is enforced automatically,
   not by manager audit.

## 3. CRM automation workflows

| Trigger | Action | Why this exists |
|---|---|---|
| New Lead created | Auto-run signal scoring (same waterfall logic as `career/projects/clay-enrichment-waterfall`) within 1 hour | Removes manual triage; qualification gate runs before any human touches the record |
| Signal score ≥ 8.0 | Fast-lane routing (§2.2) + Slack alert to assigned rep | Time-sensitive signal decay |
| Lead → MQL | Auto-enroll in a scoped outreach cadence (channel-specific: signal-scored inbound gets a "we noticed X" opener; outbound gets a standard cold sequence) | Consistent, on-brand first touch without rep-by-rep improvisation |
| MQL unactioned past SLA (6 business hours) | Reassign per §2.4 + notify manager | Prevents silent lead death |
| SQL discovery call completed | Auto-create Opportunity record, prompt rep for deal-value estimate (required field, no blank Opportunities) | Keeps `output/funnel_metrics.json` pipeline-value math clean — an Opportunity with no value can't be forecast |
| Opportunity idle > 10 business days with no logged activity | Auto-flag "stalling" on the pipeline-health dashboard (see `dashboard.html`) | Surfaces silently-dying deals before they age into a forced Closed Lost |
| Closed Lost | Require `lost_reason` from the enumerated list before the record can close (form validation, not optional) — enforced in code by `src/crm/lifecycle.py`'s `LeadLifecycle.advance()` | Loss-reason data is the single highest-leverage input for the forecasting model's win-rate assumptions (`src/analytics/forecasting.py`) — garbage in here breaks every downstream number |
| Closed Won | Auto-handoff task to CS + tag `deal_value_monthly_usd` as locked (immutable after handoff) | Data integrity: won-deal value is the input to `won_mrr_usd`; it must not silently change after the forecast model has already used it |

## 4. Data hygiene & governance

- **Required-field enforcement at stage-gate, not at record creation.** A
  Lead can exist with almost nothing filled in (that's the point of a low
  floor for top-of-funnel capture) — but it *cannot* advance to MQL without
  a channel tag, and it *cannot* close Lost without a `lost_reason`. Gating
  hygiene at the transition, not the creation event, avoids the two failure
  modes of CRMs: either everything is mandatory and reps stop logging
  leads at all, or nothing is mandatory and the pipeline data rots.
- **Deduplication**: company-name fuzzy match (Levenshtein ≤ 2) at Lead
  creation, since the same seller can surface through multiple channels
  (e.g., signal-scored inbound *and* a separate outbound touch). v2 models
  this gap directly at the Account level: `scripts/01_generate_seed_data.py`
  gives ~9% of accounts a second, undeduplicated Lead record (a second
  channel finding the same seller) rather than only encoding it indirectly
  through Roman-numeral-suffixed company names; a production version of
  this workflow would merge those into one Lead record with multi-channel
  attribution rather than double-counting it in the funnel.
- **Stale-lead decay, not silent accumulation**: a Lead that never
  qualifies to MQL within 45 days auto-archives (soft delete, recoverable)
  rather than sitting in the "Lead" bucket forever inflating the
  denominator of every conversion-rate calculation. `src/analytics/funnel.py`'s
  `n_total` in a production system would need this decay applied before the
  Lead→MQL conversion rate means anything at quarter-end — a known
  limitation of the current snapshot (see README "What's not yet built").
- **No premature segmentation.** The category-specialization routing rule
  (§2.3) is designed but explicitly *not activated* until there's enough
  per-rep, per-category sample size to trust the win-rate difference isn't
  noise — building the rule and gating its activation on statistical
  minimums is itself a governance decision, not an oversight.
- **Audit trail**: every stage transition is timestamped (this is exactly
  what `mql_date`, `sql_date` on `leads` and `opp_created_date`,
  `closed_date` on `opportunities` represent in `db/schema.sql`) — without
  per-transition timestamps, stage-dwell time, sales-cycle length, and LVR
  are all uncomputable. This is the single design choice that makes every
  metric in `src/analytics/funnel.py` possible;
  a CRM that only stores "current stage" with no history cannot produce any
  of Section 3/4 of the original portfolio gap analysis this project closes.

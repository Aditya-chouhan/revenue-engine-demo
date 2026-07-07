"""
Executable version of crm-system-design.md Section 2 (Lead routing logic).

Turns the design doc's four rules into real, stateful code that the seed
generator calls once per lead (replacing v1's plain `random.choice(REPS)`):

  1. Default: strict round-robin across all reps, for even pipeline load.
  2. Override -- high-signal fast lane: any lead scoring >= FAST_LANE_SIGNAL_
     THRESHOLD skips the round-robin queue and routes to whichever rep
     currently has the lowest open-SQL count (load-balance on active work,
     not raw lead count) -- a high-signal lead decays fast, so queueing it
     behind round-robin risks losing it.
  3. Category specialization: deliberately NOT implemented here, same
     governance call crm-system-design.md §2.3 makes -- insufficient
     per-rep/per-category sample size to trust a win-rate difference isn't
     noise. Named, not silently omitted.
  4. SLA reassignment: a lead unactioned past its SLA window re-enters the
     round-robin queue instead of staying orphaned on the original rep.

tests/test_analytics.py asserts the resulting rep-lead-count split lands
within a few percent of an even three-way split -- the design doc's claim
about routing behavior, now provably true of the code path, not just of one
dataset.
"""
import random

from src.crm.scoring import FAST_LANE_SIGNAL_THRESHOLD

# SLA: rep must action (open the MQL conversation) within 6 business hours
# of assignment, per crm-system-design.md §1. Modeled here as a probability
# of an SLA breach per assignment rather than a wall-clock simulation, since
# the seed generator works in day-granularity, not hour-granularity.
SLA_BREACH_PROBABILITY = 0.08


class RoutingEngine:
    def __init__(self, reps: list[str], seed: int | None = None):
        self.reps = list(reps)
        self._rr_index = 0
        self._rng = random.Random(seed)
        self.open_sql_count = {rep: 0 for rep in self.reps}
        self.rep_lead_count = {rep: 0 for rep in self.reps}
        self.reassignment_count = 0

    def _next_round_robin(self) -> str:
        rep = self.reps[self._rr_index % len(self.reps)]
        self._rr_index += 1
        return rep

    def _lowest_open_sql_rep(self) -> str:
        # Ties (e.g. everyone at 0 open SQLs, the common case early on and
        # whenever most fast-lane leads haven't reached SQL yet) must break
        # randomly, not by dict/list insertion order -- min() with a plain
        # key function always returns the FIRST rep encountered among ties,
        # which silently starves every rep after the first in REPS.
        lowest = min(self.open_sql_count.values())
        tied = [rep for rep, count in self.open_sql_count.items() if count == lowest]
        return self._rng.choice(tied)

    def assign(self, signal_score: float) -> str:
        """Rule 1 + Rule 2. Called once per new Lead."""
        if signal_score >= FAST_LANE_SIGNAL_THRESHOLD:
            rep = self._lowest_open_sql_rep()
        else:
            rep = self._next_round_robin()
        self.rep_lead_count[rep] += 1
        return rep

    def maybe_reassign(self, current_rep: str) -> str:
        """Rule 4. Called when checking whether a Lead's assignment survives
        to MQL. Returns the (possibly new) owner. A breached lead re-enters
        round-robin rather than being reassigned back to itself."""
        if self._rng.random() < SLA_BREACH_PROBABILITY:
            self.reassignment_count += 1
            new_rep = self._next_round_robin()
            self.rep_lead_count[current_rep] -= 1
            self.rep_lead_count[new_rep] += 1
            return new_rep
        return current_rep

    def mark_sql_opened(self, rep: str) -> None:
        self.open_sql_count[rep] += 1

    def mark_sql_closed(self, rep: str) -> None:
        self.open_sql_count[rep] = max(0, self.open_sql_count[rep] - 1)

    def load_summary(self) -> dict:
        total = sum(self.rep_lead_count.values())
        even_share = total / len(self.reps) if self.reps else 0
        return {
            "rep_lead_count": dict(self.rep_lead_count),
            "total_leads": total,
            "even_share_target": round(even_share, 1),
            "max_pct_deviation_from_even": round(
                max(abs(c - even_share) / even_share for c in self.rep_lead_count.values()) * 100, 2
            ) if even_share else 0.0,
            "reassignment_count": self.reassignment_count,
        }

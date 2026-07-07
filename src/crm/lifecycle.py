"""
Stage-gate state machine, encoding crm-system-design.md Sections 1 and 4 as
enforced code rather than narrative:

  - "A Lead can exist with almost nothing filled in ... but it cannot
     advance to MQL without a channel tag, and it cannot close Lost without
     a lost_reason." (§4, required-field-at-stage-gate, not at creation)
  - MQL entry criteria: signal-scored >= MQL_SIGNAL_FLOOR (§1).
  - Opportunity requires a deal-value estimate before the record can exist
    (§3 automation table: "prompt rep for deal-value estimate (required
    field, no blank Opportunities)").
  - Closed Lost requires lost_reason from the enumerated list (§3: "form
    validation, not optional").

Raises ValueError on any violation -- this is the mechanism, not just the
documentation, of the CRM's data-hygiene rule.
"""
from src.models import Lead

STAGE_ORDER = ["Lead", "MQL", "SQL", "Opportunity", "Closed Won", "Closed Lost"]
MQL_SIGNAL_FLOOR = 3.0

REQUIRED_FIELDS_FOR_TRANSITION = {
    "MQL": [],
    "SQL": [],
    "Opportunity": ["deal_value_monthly_usd"],
    "Closed Won": [],
    "Closed Lost": ["lost_reason"],
}

LOST_REASONS = (
    "No budget", "Went with in-house fix", "Timing not right",
    "Chose competitor", "Unresponsive after SQL", "Below deal-size floor",
)


class LifecycleViolation(ValueError):
    pass


class LeadLifecycle:
    @staticmethod
    def validate_transition(current_stage: str, target_stage: str, signal_score: float | None = None, **fields) -> None:
        if target_stage not in STAGE_ORDER:
            raise LifecycleViolation(f"Unknown stage '{target_stage}'")

        # Closed Lost is reachable from any stage (a lead can go cold at any
        # point); every other transition must move strictly forward.
        if target_stage != "Closed Lost":
            if STAGE_ORDER.index(target_stage) <= STAGE_ORDER.index(current_stage):
                raise LifecycleViolation(
                    f"Cannot move from '{current_stage}' to '{target_stage}' -- not a forward transition"
                )

        if target_stage == "MQL" and signal_score is not None and signal_score < MQL_SIGNAL_FLOOR:
            raise LifecycleViolation(
                f"signal_score {signal_score} is below the MQL floor ({MQL_SIGNAL_FLOOR}) -- lead stays in 'Lead'"
            )

        required = REQUIRED_FIELDS_FOR_TRANSITION.get(target_stage, [])
        missing = [f for f in required if fields.get(f) in (None, "")]
        if missing:
            raise LifecycleViolation(
                f"Cannot advance to '{target_stage}': missing required field(s) {missing}"
            )

        if target_stage == "Closed Lost":
            reason = fields.get("lost_reason")
            if reason not in LOST_REASONS:
                raise LifecycleViolation(
                    f"lost_reason '{reason}' is not one of the enumerated reasons: {LOST_REASONS}"
                )

    @classmethod
    def advance(cls, lead: Lead, target_stage: str, **fields) -> Lead:
        cls.validate_transition(lead.stage, target_stage, signal_score=lead.signal_score, **fields)
        lead.stage = target_stage
        for k, v in fields.items():
            if hasattr(lead, k):
                setattr(lead, k, v)
        return lead

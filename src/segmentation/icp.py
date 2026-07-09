"""
ICP definition + fit scoring + segmentation.

Makes v1's implicit ICP explicit and scored, rather than "inherited from the
Clay project" by assertion. The ICP itself extends career/projects/
clay-enrichment-waterfall's Amazon-seller distress-signal targeting: that
project validated 42 Beauty/Baby beachhead brands out of a 2,350-seller
distress-scored universe -- Beauty/Baby/Skin are this project's core
categories for the same reason (proven signal-to-conversion behavior in that
prior, separate build), Home/Kitchen/Gadgets are adjacent (plausible fit,
less proven), Pet/Outdoor are exploratory (weakest prior evidence).

Fit score (0-100) = category fit (0-40) + firmographic fit (0-35) +
signal-strength component (0-25). Three additive, capped components so the
score is fully inspectable -- no hidden interaction terms.

Segment thresholds turn the fit score into a label used both for reporting
and to genuinely change simulated conversion behavior in the seed generator
(src/segmentation/icp.py::CONVERSION_MULTIPLIER) -- segmentation has to
change the funnel numbers to be a real signal, not just a cosmetic label.
"""

CORE_CATEGORIES = {"Beauty", "Baby", "Skin"}
ADJACENT_CATEGORIES = {"Home", "Kitchen", "Gadgets"}
EXPLORATORY_CATEGORIES = {"Pet", "Outdoor"}

INDUSTRY_MAP = {
    "Beauty": "Health & Beauty",
    "Skin": "Health & Beauty",
    "Baby": "Home & Family",
    "Kitchen": "Home & Family",
    "Home": "Home & Family",
    "Gadgets": "Consumer Electronics",
    "Pet": "Lifestyle & Outdoor",
    "Outdoor": "Lifestyle & Outdoor",
}

# Firmographic proxy: this ICP targets small/independent Amazon sellers, not
# larger operations with in-house teams -- mirrors a prior role's actual
# SMB-seller targeting rationale, not a generic "bigger is better" prior.
EMPLOYEE_BAND_FIT = {
    "1-10": 35,
    "11-50": 30,
    "51-200": 15,
    "201-500": 5,
}

SEGMENT_THRESHOLDS = [
    (70, "Beachhead"),
    (50, "Core ICP"),
    (30, "Adjacent"),
    (0, "Poor Fit"),
]

# Applied to base stage-conversion probabilities in the seed generator so
# segment membership has a real, measurable effect on the funnel -- not a
# label with no consequence.
CONVERSION_MULTIPLIER = {
    "Beachhead": 1.15,
    "Core ICP": 1.00,
    "Adjacent": 0.85,
    "Poor Fit": 0.60,
}


def category_fit(category: str) -> int:
    if category in CORE_CATEGORIES:
        return 40
    if category in ADJACENT_CATEGORIES:
        return 25
    return 10  # exploratory


def icp_fit_score(category: str, employee_band: str, signal_score_0_10: float) -> float:
    cat_component = category_fit(category)
    firm_component = EMPLOYEE_BAND_FIT.get(employee_band, 10)
    signal_component = min(signal_score_0_10 / 10 * 25, 25)
    return round(min(cat_component + firm_component + signal_component, 100.0), 2)


def segment_for_score(fit_score: float) -> str:
    for threshold, label in SEGMENT_THRESHOLDS:
        if fit_score >= threshold:
            return label
    return "Poor Fit"


def industry_for_category(category: str) -> str:
    return INDUSTRY_MAP.get(category, "Other")

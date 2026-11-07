"""THE one place that defines subscription plans and their usage limits.

To change a limit, edit a number in PLAN_LIMITS below. Nothing else in the code contains plan numbers:
enforcement (`app/modules/billing/quota.py`), the usage endpoint, and any future billing screen all read
from here. `None` means unlimited. Every limit is per organization per calendar month (UTC).

The numbers below are PLACEHOLDERS to be decided before launch.
"""


class Metric:
    """Names of things that can be limited. Add a new metric here, then give it a number for every plan."""

    AI_CAPTIONS = "ai_captions"  # enforced now: AI caption generations
    AI_VIDEO_SCRIPTS = "ai_video_scripts"  # enforced: short-form and long-form video scripts
    SCHEDULED_POSTS = "scheduled_posts"  # declared for later: not enforced yet
    LEAD_EMAILS = "lead_emails"  # declared for later: not enforced yet


UNLIMITED = None

DEFAULT_PLAN = "free"

PLAN_NAMES: dict[str, str] = {
    "free": "Free",
    "standard": "Standard",
    "premium": "Premium",
}

PLAN_LIMITS: dict[str, dict[str, int | None]] = {
    "free": {
        Metric.AI_CAPTIONS: 2,
        Metric.AI_VIDEO_SCRIPTS: 2,
        Metric.SCHEDULED_POSTS: 2,
        Metric.LEAD_EMAILS: 0,
    },
    "standard": {
        Metric.AI_CAPTIONS: 10,
        Metric.AI_VIDEO_SCRIPTS: 10,
        Metric.SCHEDULED_POSTS: 10,
        Metric.LEAD_EMAILS: 100,
    },
    "premium": {
        Metric.AI_CAPTIONS: 50,
        Metric.AI_VIDEO_SCRIPTS: 50,
        Metric.SCHEDULED_POSTS: 50,
        Metric.LEAD_EMAILS: 1000,
    },
}

# Words shown to people when a limit is reached.
METRIC_LABELS: dict[str, str] = {
    Metric.AI_CAPTIONS: "AI captions",
    Metric.AI_VIDEO_SCRIPTS: "AI video scripts",
    Metric.SCHEDULED_POSTS: "scheduled posts",
    Metric.LEAD_EMAILS: "lead emails",
}


def resolve_plan(plan: str | None) -> str:
    """Return a known plan key; unknown or missing plans are treated as the default (most restrictive safe choice)."""
    return plan if plan in PLAN_LIMITS else DEFAULT_PLAN


def plan_name(plan: str | None) -> str:
    return PLAN_NAMES.get(resolve_plan(plan), resolve_plan(plan).title())


def get_limit(plan: str | None, metric: str) -> int | None:
    """The monthly limit for `metric` on `plan` (None = unlimited). Raises KeyError for an undefined metric."""
    return PLAN_LIMITS[resolve_plan(plan)][metric]

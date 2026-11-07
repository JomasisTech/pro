"""Rule-based analysis of a business's recent social posts (no external AI call, no network).

Used by `POST /brand-intelligence/analyze?method=rules`, which works without an AI provider key.

Input is at most ``MAX_POSTS`` posts. Output is a set of evidence-backed observations plus metrics. The module
never stores post text and never claims anything the supplied data cannot support: engagement figures are only
reported when every analysed post carries them, cadence only when enough posts have timestamps, and topics only
for terms repeated across several posts. Keyword/stop-word handling is English-only; other languages simply
yield fewer topic observations.

Observations that compare posts with the declared business profile are phrased as questions for the owner. They
never change the profile.
"""

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime

MAX_POSTS = 20
MAX_TEXT_CHARS = 5000

_HASHTAG = re.compile(r"#([A-Za-z0-9_]{2,50})")
_WORD = re.compile(r"[a-z][a-z'-]{2,}")
_EMOJI = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\U0001F000-\U0001F2FF\u2B50\u2764]")
_STOP = frozenset(
    """the and for you your with that this from are was were have has had not but all can will our out get got
    its it's into more most just than then them they their what when where which who why how about over also
    been being only some such too very any each new now one two see use using make made like want need let
    here there these those would could should may might its his her she him one's day days today""".split()
)
# Fixed phrase list so observations quote our vocabulary, never raw post text.
_CTA_PHRASES = {
    "link in bio": "link in bio", "dm us": "DM us", "dm me": "DM us", "call us": "call us", "order now": "order now",
    "shop now": "shop now", "book now": "book now", "book a": "book a…", "visit us": "visit us",
    "whatsapp": "WhatsApp us", "sign up": "sign up", "register": "register", "click": "click the link",
    "comment below": "comment below", "tag a friend": "tag a friend", "contact us": "contact us", "message us": "message us",
}


@dataclass(frozen=True)
class PostInput:
    text: str
    posted_at: datetime | None = None
    media_type: str | None = None  # e.g. "image", "video", "carousel", "text"
    like_count: int | None = None
    comment_count: int | None = None


@dataclass
class ObservationDraft:
    fingerprint: str
    kind: str
    statement: str
    evidence: dict = field(default_factory=dict)
    is_recommendation: bool = False


@dataclass
class AnalysisResult:
    posts_analyzed: int
    evidence_level: str
    metrics: dict
    observations: list[ObservationDraft]
    oldest_post_at: datetime | None
    newest_post_at: datetime | None


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _pct(part: int, total: int) -> int:
    return round(100 * part / total) if total else 0


def evidence_level(posts: list[PostInput], now: datetime | None = None) -> str:
    """Initial / Developing / Well-supported from quantity, recency and diversity. No numeric score on purpose."""
    now = now or datetime.now(UTC)
    count = len(posts)
    level = 0 if count < 5 else 1 if count < 12 else 2
    texts = [" ".join(p.text.lower().split()) for p in posts]
    if count and len(set(texts)) / count < 0.6:
        level -= 1  # many repeated/duplicate posts add little evidence
    dated = [_aware(p.posted_at) for p in posts if p.posted_at]
    if dated and (now - max(dated)).days > 180:
        level -= 1  # stale evidence
    return ("initial", "developing", "well_supported")[max(0, level)]


def _ranked(counter: Counter) -> list[tuple[str, int]]:
    """Highest count first; ties alphabetical so results never depend on hash order."""
    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))


def _terms(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOP and len(w) >= 4}


def analyze_posts(
    posts: list[PostInput],
    *,
    profile_text: str = "",
    product_names: list[str] | None = None,
    avoided_words: list[str] | None = None,
    now: datetime | None = None,
) -> AnalysisResult:
    """Analyse up to MAX_POSTS posts and compare them with the declared profile facts."""
    if not posts:
        raise ValueError("At least one post is required")
    if len(posts) > MAX_POSTS:
        raise ValueError(f"At most {MAX_POSTS} posts can be analysed at once")
    now = now or datetime.now(UTC)
    n = len(posts)
    texts = [p.text[:MAX_TEXT_CHARS] for p in posts]
    lowered = [t.lower() for t in texts]
    observations: list[ObservationDraft] = []

    # Hashtags used in at least two posts.
    tag_posts: Counter[str] = Counter()
    for text in texts:
        for tag in {t.lower() for t in _HASHTAG.findall(text)}:
            tag_posts[tag] += 1
    posts_with_tags = sum(1 for t in texts if _HASHTAG.search(t))
    for tag, count in _ranked(tag_posts)[:5]:
        if count >= 2:
            observations.append(ObservationDraft(
                f"hashtag:{tag}", "hashtag", f"The hashtag #{tag} appears in {count} of {n} posts.", {"posts": count, "of": n}))

    # Writing style: length, emoji, questions.
    lengths = [len(t) for t in texts]
    avg_len = round(sum(lengths) / n)
    length_label = "short (under about 100 characters)" if avg_len < 100 else "long (over about 300 characters)" if avg_len > 300 else "medium-length"
    observations.append(ObservationDraft(
        "tone:length", "tone", f"Posts are typically {length_label}; the average is {avg_len} characters.", {"average_characters": avg_len, "of": n}))
    emoji_posts = sum(1 for t in texts if _EMOJI.search(t))
    if emoji_posts:
        observations.append(ObservationDraft(
            "tone:emoji", "tone", f"{emoji_posts} of {n} posts ({_pct(emoji_posts, n)}%) use emoji.", {"posts": emoji_posts, "of": n}))
    question_posts = sum(1 for t in texts if "?" in t)
    if question_posts >= 2:
        observations.append(ObservationDraft(
            "tone:questions", "tone", f"{question_posts} of {n} posts ask the audience a question.", {"posts": question_posts, "of": n}))

    # Calls to action.
    cta_counter: Counter[str] = Counter()
    cta_posts = 0
    for text in lowered:
        found = {label for phrase, label in _CTA_PHRASES.items() if phrase in text}
        if found:
            cta_posts += 1
        cta_counter.update(found)
    if cta_posts >= 2:
        top = ", ".join(f'"{label}"' for label, _ in _ranked(cta_counter)[:3])
        observations.append(ObservationDraft(
            "cta:common", "cta", f"{cta_posts} of {n} posts include a call to action, most often {top}.", {"posts": cta_posts, "of": n}))

    # Formats, only when the source provided them for every post.
    formats = Counter((p.media_type or "").lower() for p in posts if p.media_type)
    if sum(formats.values()) == n and n >= 3:
        parts = ", ".join(f"{name} ({count})" for name, count in _ranked(formats))
        observations.append(ObservationDraft("format:mix", "format", f"Post formats used: {parts}.", {"formats": dict(formats), "of": n}))

    # Topics: terms present in several distinct posts.
    term_posts: Counter[str] = Counter()
    for text in texts:
        term_posts.update(_terms(_HASHTAG.sub(" ", text)))
    threshold = max(3, math.ceil(0.25 * n))
    topics = [(w, c) for w, c in _ranked(term_posts) if c >= threshold][:5]
    for word, count in topics:
        observations.append(ObservationDraft(
            f"topic:{word}", "topic", f'The word "{word}" appears in {count} of {n} posts, suggesting a recurring theme.', {"posts": count, "of": n}))

    # Cadence, only with enough timestamps.
    dated = sorted(_aware(p.posted_at) for p in posts if p.posted_at)
    metrics: dict = {"posts_with_hashtags": posts_with_tags, "posts_with_emoji": emoji_posts,
                     "posts_with_cta": cta_posts, "average_characters": avg_len}
    if len(dated) >= 4:
        span_days = max(1.0, (dated[-1] - dated[0]).total_seconds() / 86400)
        per_week = round((len(dated) - 1) / span_days * 7, 1)
        metrics["posts_per_week"] = per_week
        observations.append(ObservationDraft(
            "cadence:weekly", "cadence", f"The analysed posts were published about {per_week} times per week.", {"posts": len(dated)}))

    # Engagement, only when every post carries platform-reported likes.
    if n >= 3 and all(p.like_count is not None for p in posts):
        avg_likes = round(sum(p.like_count or 0 for p in posts) / n, 1)
        metrics["average_likes"] = avg_likes
        observations.append(ObservationDraft(
            "engagement:likes", "engagement", f"Platform-reported likes average {avg_likes} per post across these {n} posts.", {"of": n}))

    # Recommendations (clearly labelled; never facts).
    if n >= 5 and cta_posts / n < 0.2:
        observations.append(ObservationDraft(
            "opportunity:cta", "opportunity", "Few posts include a call to action. Consider telling readers what to do next.", {"posts": cta_posts, "of": n}, True))
    if n >= 5 and posts_with_tags == 0:
        observations.append(ObservationDraft(
            "opportunity:hashtags", "opportunity", "None of these posts use hashtags. Consider adding a few relevant ones.", {"of": n}, True))

    # Reconcile with the declared profile. These ask questions; they never edit the profile.
    profile_terms = _terms(profile_text)
    for word, count in topics:
        if profile_terms and word not in profile_terms and not any(word in name.lower() for name in (product_names or [])):
            observations.append(ObservationDraft(
                f"conflict:topic:{word}", "conflict",
                f'Your posts often mention "{word}" ({count} of {n}), but it is not in your business profile. '
                "Is it part of what you offer? Your profile was not changed.", {"posts": count, "of": n}))
    names = [name.strip() for name in (product_names or []) if name.strip()]
    if n >= 5 and names and not any(name.lower() in text for name in names for text in lowered):
        observations.append(ObservationDraft(
            "conflict:products", "conflict",
            "None of the analysed posts mention the products or services listed in your profile by name.", {"of": n}))
    for word in [w.strip().lower() for w in (avoided_words or []) if w.strip()][:30]:
        count = sum(1 for text in lowered if re.search(rf"(?<![a-z0-9]){re.escape(word)}(?![a-z0-9])", text))
        if count:
            observations.append(ObservationDraft(
                f"conflict:avoided:{word}", "conflict",
                f'{count} of {n} posts use "{word}", which your profile lists as a word to avoid.', {"posts": count, "of": n}))

    for item in observations:
        item.fingerprint = item.fingerprint[:160]
    return AnalysisResult(
        posts_analyzed=n,
        evidence_level=evidence_level(posts, now),
        metrics=metrics,
        observations=observations,
        oldest_post_at=dated[0] if dated else None,
        newest_post_at=dated[-1] if dated else None,
    )


_PROFILE_FIELD = {"topic": "description", "products": "products_services", "avoided": "avoided_words"}


def build_rule_proposal(
    posts: list[PostInput],
    *,
    profile_values: dict[str, str | None],
    product_names: list[str],
    avoided_words: list[str],
    now: datetime | None = None,
) -> dict:
    """Rule-based proposal in the same shape the AI analysis uses, so the existing review flow works unchanged.

    Nothing here is invented: every entry is a count-backed observation, there is no proposed voice, and profile
    differences are reported as conflicts for the owner to resolve (the confirmed profile stays authoritative).
    """
    profile_text = " ".join(str(v) for v in profile_values.values() if v)
    result = analyze_posts(posts, profile_text=profile_text, product_names=product_names, avoided_words=avoided_words, now=now)
    by_kind: dict[str, list[str]] = {}
    for item in result.observations:
        by_kind.setdefault(item.kind, []).append(item.statement)
    conflicts = []
    for item in result.observations:
        if item.kind != "conflict":
            continue
        group = item.fingerprint.split(":")[1]
        field = _PROFILE_FIELD.get(group, "description")
        confirmed = profile_values.get(field) or ""
        conflicts.append({"field": field, "confirmed_value": confirmed[:200], "observed_signal": item.statement, "explanation": item.statement})
    topics = [item.fingerprint.split(":", 1)[1] for item in result.observations if item.kind == "topic"]
    hashtags = [f"#{item.fingerprint.split(':', 1)[1]}" for item in result.observations if item.kind == "hashtag"]
    return {
        "method": "rules",
        "posts_analyzed": result.posts_analyzed,
        "evidence_level": result.evidence_level,
        "confidence": {"initial": "low", "developing": "medium", "well_supported": "high"}[result.evidence_level],
        "topics": topics,
        "recurring_themes": topics,
        "content_categories": [],
        "hashtags": hashtags,
        "tone": by_kind.get("tone", []),
        "writing_patterns": by_kind.get("cta", []) + by_kind.get("format", []) + by_kind.get("cadence", []),
        "emoji_patterns": [s for s in by_kind.get("tone", []) if "emoji" in s],
        "proposed_voice": "",
        "suggestions": by_kind.get("opportunity", []),
        "conflicts": conflicts,
        "metrics": result.metrics,
    }

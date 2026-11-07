"""Pure-logic tests for the post analyser (no database or HTTP)."""

from datetime import UTC, datetime, timedelta

import pytest

from app.modules.brand_intelligence.heuristics import MAX_POSTS, PostInput, analyze_posts, evidence_level

NOW = datetime(2026, 11, 4, tzinfo=UTC)


def post(text, days_ago=1, **kw):
    return PostInput(text=text, posted_at=NOW - timedelta(days=days_ago), **kw)


def kinds(result):
    return {o.kind for o in result.observations}


def test_rejects_empty_and_too_many_posts() -> None:
    with pytest.raises(ValueError):
        analyze_posts([])
    with pytest.raises(ValueError):
        analyze_posts([post("x")] * (MAX_POSTS + 1))


def test_evidence_levels_follow_quantity() -> None:
    texts = [f"unique post number {i} about different things" for i in range(20)]
    assert evidence_level([post(t, i) for i, t in enumerate(texts[:3])], NOW) == "initial"
    assert evidence_level([post(t, i) for i, t in enumerate(texts[:8])], NOW) == "developing"
    assert evidence_level([post(t, i) for i, t in enumerate(texts[:15])], NOW) == "well_supported"


def test_stale_or_duplicate_evidence_is_downgraded() -> None:
    old = [post(f"post {i} unique words {i}", 400 + i) for i in range(15)]
    assert evidence_level(old, NOW) == "developing"
    duplicates = [post("same text every time", i) for i in range(15)]
    assert evidence_level(duplicates, NOW) == "developing"


def test_hashtags_cta_and_emoji_are_detected_with_counts() -> None:
    posts = [
        post("Fresh bread today 🍞 #Bakery #lagos order now", 1),
        post("Cake special 🎂 #bakery DM us to order", 2),
        post("Plain post without extras", 3),
    ]
    result = analyze_posts(posts, now=NOW)
    statements = " ".join(o.statement for o in result.observations)
    assert "#bakery appears in 2 of 3 posts" in statements
    assert "2 of 3 posts include a call to action" in statements
    assert "2 of 3 posts (67%) use emoji" in statements
    assert result.posts_analyzed == 3


def test_engagement_only_when_every_post_has_metrics() -> None:
    partial = [post("a b c", 1, like_count=5), post("d e f", 2, like_count=7), post("g h i", 3)]
    assert "engagement" not in kinds(analyze_posts(partial, now=NOW))
    full = [post("a b c", 1, like_count=5), post("d e f", 2, like_count=7), post("g h i", 3, like_count=9)]
    result = analyze_posts(full, now=NOW)
    assert "engagement" in kinds(result) and result.metrics["average_likes"] == 7.0


def test_cadence_needs_four_dated_posts() -> None:
    assert "cadence" not in kinds(analyze_posts([post("a", 1), post("b", 2), post("c", 3)], now=NOW))
    four = [post(f"post {i}", i * 2 + 1) for i in range(4)]
    assert "cadence" in kinds(analyze_posts(four, now=NOW))


def test_few_posts_never_produce_recommendations() -> None:
    result = analyze_posts([post("hello world", 1)], now=NOW)
    assert not any(o.is_recommendation for o in result.observations)
    assert result.evidence_level == "initial"


def test_recommendations_are_flagged_as_such() -> None:
    posts = [post(f"Update number {i} about our shop", i) for i in range(6)]
    result = analyze_posts(posts, now=NOW)
    recs = [o for o in result.observations if o.kind == "opportunity"]
    assert recs and all(o.is_recommendation for o in recs)


def test_profile_conflicts_are_reported_without_changing_anything() -> None:
    posts = [post("Our catering service is booked. Catering menu ready. Catering for events", i) for i in range(1, 4)]
    result = analyze_posts(posts, profile_text="We sell bread and cakes", product_names=["Bread"], now=NOW)
    conflicts = [o for o in result.observations if o.kind == "conflict"]
    assert any("catering" in o.statement and "was not changed" in o.statement for o in conflicts)


def test_avoided_words_are_flagged() -> None:
    posts = [post("Cheap deals everywhere", 1), post("Great product", 2)]
    result = analyze_posts(posts, avoided_words=["cheap"], now=NOW)
    assert any(o.fingerprint == "conflict:avoided:cheap" for o in result.observations)


def test_post_text_is_never_copied_into_observations() -> None:
    secret = "my-private-phone-08012345678"
    result = analyze_posts([post(f"Call {secret} now", 1), post(f"Call {secret} today", 2)], now=NOW)
    assert all(secret not in o.statement for o in result.observations)



def test_rule_proposal_matches_the_review_flow_shape() -> None:
    from app.modules.brand_intelligence.heuristics import build_rule_proposal
    posts = [post(f"Cheap catering deals today #food number {i}", i + 1) for i in range(6)]
    proposal = build_rule_proposal(posts, profile_values={"description": "We sell bread", "avoided_words": "cheap"},
                                   product_names=["Bread"], avoided_words=["cheap"], now=NOW)
    for key in ("topics", "tone", "hashtags", "conflicts", "confidence", "proposed_voice", "evidence_level"):
        assert key in proposal
    assert proposal["method"] == "rules" and proposal["proposed_voice"] == ""
    assert proposal["confidence"] == "medium" and "#food" in proposal["hashtags"]
    assert any(c["field"] == "avoided_words" and c["confirmed_value"] == "cheap" for c in proposal["conflicts"])

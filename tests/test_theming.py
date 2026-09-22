from datetime import datetime, timezone
from src.groww_pulse.ingestion import ReviewItem
from src.groww_pulse.sanitization import PIISanitizer
from src.groww_pulse.theming import ThemeClusterer, ThemeCategory, GROWW_TAXONOMY

def test_taxonomy_definitions():
    assert len(GROWW_TAXONOMY) == 5
    for cat in ThemeCategory:
        assert cat in GROWW_TAXONOMY
        assert len(GROWW_TAXONOMY[cat].keywords) > 0

def test_theming_clustering():
    sanitizer = PIISanitizer(min_words=8)
    clusterer = ThemeClusterer(max_themes=5, top_themes_count=3)

    raw_reviews = [
        ReviewItem(
            review_id="r1",
            date=datetime.now(timezone.utc),
            rating=1,
            text="Transferred ₹5000 via UPI but money did not show in trading balance for 4 hours.",
            reviewer_name="User 1"
        ),
        ReviewItem(
            review_id="r2",
            date=datetime.now(timezone.utc),
            rating=1,
            text="KYC rejected twice with no clear reason given about which document failed.",
            reviewer_name="User 2"
        ),
        ReviewItem(
            review_id="r3",
            date=datetime.now(timezone.utc),
            rating=1,
            text="Option chart took 10 seconds to refresh during opening bell, missed my entry.",
            reviewer_name="User 3"
        ),
        ReviewItem(
            review_id="r4",
            date=datetime.now(timezone.utc),
            rating=5,
            text="SIP step-up feature is very convenient. Love tracking my mutual funds portfolio here.",
            reviewer_name="User 4"
        ),
        ReviewItem(
            review_id="r5",
            date=datetime.now(timezone.utc),
            rating=1,
            text="App crashes immediately after fingerprint login on Android 14. Fix this bug ASAP!",
            reviewer_name="User 5"
        ),
    ]

    sanitized = sanitizer.sanitize_reviews(raw_reviews)
    clusters = clusterer.cluster(sanitized)

    assert len(clusters) <= 5
    assert all(c.review_count >= 1 for c in clusters)
    
    top_3 = clusterer.get_top_themes(clusters)
    assert len(top_3) == 3

    # Total percentages sum to 100%
    total_pct = sum(c.percentage_of_total for c in clusters)
    assert 99.0 <= total_pct <= 101.0

def test_verbatim_candidate_extraction():
    sanitizer = PIISanitizer(min_words=8)
    clusterer = ThemeClusterer()

    raw_reviews = [
        ReviewItem(
            review_id="r1",
            date=datetime.now(timezone.utc),
            rating=1,
            text="Transferred ₹5000 via UPI but money did not show in trading balance for 4 hours.",
            reviewer_name="User 1"
        )
    ]
    sanitized = sanitizer.sanitize_reviews(raw_reviews)
    clusters = clusterer.cluster(sanitized)

    payments_cluster = next(c for c in clusters if c.theme_id == ThemeCategory.PAYMENTS_SETTLEMENT.value)
    assert len(payments_cluster.verbatim_candidates) >= 1
    assert "UPI" in payments_cluster.verbatim_candidates[0]

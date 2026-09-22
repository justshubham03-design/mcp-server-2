from datetime import datetime, timezone
from src.groww_pulse.synthesis import WeeklyPulse, ThemeItem, PulseValidator
from src.groww_pulse.sanitization import SanitizedReview

def test_pulse_validator_valid():
    validator = PulseValidator(max_word_limit=250)

    reviews = [
        SanitizedReview(
            id="r1",
            sanitized_text="Transferred ₹5000 via UPI but money did not show in trading balance for 4 hours.",
            original_text="Transferred ₹5000 via UPI but money did not show in trading balance for 4 hours.",
            rating=1,
            date=datetime.now(timezone.utc),
            anonymized_author="Reviewer 1234",
            word_count=15
        ),
        SanitizedReview(
            id="r2",
            sanitized_text="KYC rejected twice with no clear reason given about which document failed.",
            original_text="KYC rejected twice with no clear reason given about which document failed.",
            rating=1,
            date=datetime.now(timezone.utc),
            anonymized_author="Reviewer 5678",
            word_count=13
        ),
        SanitizedReview(
            id="r3",
            sanitized_text="Option chart took 10 seconds to refresh during opening bell, missed my entry.",
            original_text="Option chart took 10 seconds to refresh during opening bell, missed my entry.",
            rating=1,
            date=datetime.now(timezone.utc),
            anonymized_author="Reviewer 9999",
            word_count=14
        )
    ]

    pulse = WeeklyPulse(
        week_identifier="2026-W38",
        analysis_period_start="2026-07-25",
        analysis_period_end="2026-09-19",
        total_reviews_analyzed=3,
        executive_summary="Executive sentiment pulse shows core app stability with key friction points in UPI and KYC.",
        top_themes=[
            ThemeItem(rank=1, name="Payments & UPI", metric="40% volume, 1.8★", summary="Delays in balance updates."),
            ThemeItem(rank=2, name="KYC & Onboarding", metric="35% volume, 1.9★", summary="Rejection feedback missing."),
            ThemeItem(rank=3, name="Trading & Charts", metric="25% volume, 2.2★", summary="Chart latency at market open.")
        ],
        verbatim_quotes=[
            "Transferred ₹5000 via UPI but money did not show in trading balance for 4 hours.",
            "KYC rejected twice with no clear reason given about which document failed.",
            "Option chart took 10 seconds to refresh during opening bell, missed my entry."
        ],
        action_ideas=[
            "Add UPI status retry banner on deposit screen.",
            "Add explicit document rejection reasons in KYC view.",
            "Optimize option chart WebSocket feed during opening bell."
        ]
    )

    result = validator.validate(pulse, reviews)
    assert result.is_valid is True
    assert result.word_count <= 250
    assert all(result.quotes_verified)
    assert len(result.errors) == 0

def test_hallucinated_quote_rejection():
    validator = PulseValidator()

    reviews = [
        SanitizedReview(
            id="r1",
            sanitized_text="Real review text in corpus",
            original_text="Real review text in corpus",
            rating=1,
            date=datetime.now(timezone.utc),
            anonymized_author="Reviewer 1111",
            word_count=5
        )
    ]

    pulse = WeeklyPulse(
        week_identifier="2026-W38",
        analysis_period_start="2026-07-25",
        analysis_period_end="2026-09-19",
        total_reviews_analyzed=1,
        executive_summary="Summary",
        top_themes=[
            ThemeItem(rank=1, name="T1", metric="50%", summary="S1"),
            ThemeItem(rank=2, name="T2", metric="30%", summary="S2"),
            ThemeItem(rank=3, name="T3", metric="20%", summary="S3"),
        ],
        verbatim_quotes=[
            "Real review text in corpus",
            "This quote never existed in any review text ever invented by AI",
            "Another hallucinated quote text here"
        ],
        action_ideas=["Action 1", "Action 2", "Action 3"]
    )

    result = validator.validate(pulse, reviews)
    assert result.is_valid is False
    assert len(result.unmatched_quotes) == 2
    assert "Grounding failure" in result.errors[0]

def test_word_count_exceeded():
    validator = PulseValidator(max_word_limit=50)  # artificially low limit to test overflow

    reviews = [
        SanitizedReview(
            id="r1",
            sanitized_text="Short text",
            original_text="Short text",
            rating=5,
            date=datetime.now(timezone.utc),
            anonymized_author="Reviewer 0001",
            word_count=2
        )
    ]

    pulse = WeeklyPulse(
        week_identifier="2026-W38",
        analysis_period_start="2026-07-25",
        analysis_period_end="2026-09-19",
        total_reviews_analyzed=1,
        executive_summary="This is an extremely long executive summary designed to easily exceed the word limit constraint for the test. " * 5,
        top_themes=[
            ThemeItem(rank=1, name="Theme 1", metric="33%", summary="Summary 1"),
            ThemeItem(rank=2, name="Theme 2", metric="33%", summary="Summary 2"),
            ThemeItem(rank=3, name="Theme 3", metric="34%", summary="Summary 3"),
        ],
        verbatim_quotes=["Short text", "Short text", "Short text"],
        action_ideas=["Action 1", "Action 2", "Action 3"]
    )

    result = validator.validate(pulse, reviews)
    assert result.is_valid is False
    assert any("Word count constraint violated" in e for e in result.errors)

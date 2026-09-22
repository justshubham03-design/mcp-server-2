from datetime import datetime, timezone
from src.groww_pulse.ingestion import PlayStoreIngestion
from src.groww_pulse.sanitization import PIISanitizer
from src.groww_pulse.theming import ThemeClusterer
from src.groww_pulse.synthesis import PulseBuilder, WeeklyPulse, PulseValidator

def test_deterministic_pulse_builder():
    raw_reviews = PlayStoreIngestion.generate_mock_groww_reviews(weeks_lookback=8, count=20)
    sanitizer = PIISanitizer(min_words=8, strip_emojis=True)
    sanitized = sanitizer.sanitize_reviews(raw_reviews)

    clusterer = ThemeClusterer()
    clusters = clusterer.cluster(sanitized)

    builder = PulseBuilder()
    pulse = builder.build_deterministic_pulse(clusters, sanitized)

    assert isinstance(pulse, WeeklyPulse)
    assert len(pulse.top_themes) == 3
    assert len(pulse.verbatim_quotes) == 3
    assert len(pulse.action_ideas) == 3
    assert pulse.word_count <= 250

    # Validate output
    validator = PulseValidator()
    val_result = validator.validate(pulse, sanitized)
    assert val_result.is_valid is True
    assert val_result.word_count <= 250
    assert len(val_result.errors) == 0

def test_markdown_and_html_rendering():
    raw_reviews = PlayStoreIngestion.generate_mock_groww_reviews(weeks_lookback=8, count=15)
    sanitizer = PIISanitizer(min_words=8)
    sanitized = sanitizer.sanitize_reviews(raw_reviews)
    clusterer = ThemeClusterer()
    clusters = clusterer.cluster(sanitized)

    builder = PulseBuilder()
    pulse = builder.build_deterministic_pulse(clusters, sanitized)

    # Render Markdown
    md = builder.render_markdown(pulse)
    assert "# Groww Weekly Review Pulse" in md
    assert "Top 3 User Themes" in md
    assert "Real User Quotes" in md
    assert "Prioritized Action Ideas" in md
    for q in pulse.verbatim_quotes:
        assert q in md

    # Render HTML Email
    html = builder.render_html_email(pulse, doc_url="https://docs.google.com/document/d/sample_doc_id")
    assert "Groww Weekly Review Pulse" in html
    assert "https://docs.google.com/document/d/sample_doc_id" in html
    assert "Open Full Note in Google Docs" in html

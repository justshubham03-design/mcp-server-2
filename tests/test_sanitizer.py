from datetime import datetime, timezone
from src.groww_pulse.ingestion import ReviewItem
from src.groww_pulse.sanitization import PIISanitizer, SanitizedReview

def test_emoji_removal():
    sanitizer = PIISanitizer()
    text = "Great app for stock trading! 🚀📈💰 Love the clean interface 👍✨"
    cleaned = sanitizer.remove_emojis(text)
    assert "🚀" not in cleaned
    assert "📈" not in cleaned
    assert "💰" not in cleaned
    assert "👍" not in cleaned
    assert "✨" not in cleaned
    assert cleaned == "Great app for stock trading! Love the clean interface"

def test_less_than_8_words_filtered():
    sanitizer = PIISanitizer(min_words=8)
    # 3 words -> Should be filtered out
    assert sanitizer.is_noise("Very nice app") is True
    # 7 words -> Should be filtered out
    assert sanitizer.is_noise("Mutual funds portfolio is very good here") is True
    # 8 words -> Should be kept
    assert sanitizer.is_noise("Mutual funds portfolio is very good here to use") is False
    # 15 words -> Should be kept
    assert sanitizer.is_noise("Transferred ₹5000 via UPI but money did not show in trading balance for 4 hours.") is False

def test_phone_number_redaction():
    sanitizer = PIISanitizer()
    text = "Call me at +91 98765 43210 or 9876543210 to resolve this issue right away."
    cleaned, had_pii = sanitizer.sanitize_text(text)
    assert had_pii is True
    assert "98765 43210" not in cleaned
    assert "9876543210" not in cleaned
    assert "[PHONE_REDACTED]" in cleaned

def test_email_redaction():
    sanitizer = PIISanitizer()
    text = "Contact me at rahul.verma@gmail.com or support [at] example [dot] com regarding this."
    cleaned, had_pii = sanitizer.sanitize_text(text)
    assert had_pii is True
    assert "rahul.verma@gmail.com" not in cleaned
    assert "support [at] example [dot] com" not in cleaned
    assert "[EMAIL_REDACTED]" in cleaned

def test_upi_and_financial_redaction():
    sanitizer = PIISanitizer()
    text = "Sent ₹2000 to user@okhdfcbank from A/C 98765432109876, IFSC code SBIN0001234. PAN ABCDE1234F."
    cleaned, had_pii = sanitizer.sanitize_text(text)
    assert had_pii is True
    assert "user@okhdfcbank" not in cleaned
    assert "98765432109876" not in cleaned
    assert "SBIN0001234" not in cleaned
    assert "ABCDE1234F" not in cleaned
    assert "[UPI_ID_REDACTED]" in cleaned
    assert "[IFSC_REDACTED]" in cleaned
    assert "[PAN_REDACTED]" in cleaned

def test_aadhaar_redaction():
    sanitizer = PIISanitizer()
    text = "My Aadhaar is 5432 1098 7654. KYC failed during account verification."
    cleaned, had_pii = sanitizer.sanitize_text(text)
    assert had_pii is True
    assert "5432 1098 7654" not in cleaned
    assert "[AADHAAR_REDACTED]" in cleaned

def test_noise_filtering():
    sanitizer = PIISanitizer(min_words=8)
    assert sanitizer.is_noise("good") is True
    assert sanitizer.is_noise("nice app") is True
    assert sanitizer.is_noise("worst") is True
    assert sanitizer.is_noise("ok") is True
    assert sanitizer.is_noise("👍👍👍") is True
    assert sanitizer.is_noise("Transferred money via UPI but balance not updated for several hours") is False

def test_anonymize_author():
    sanitizer = PIISanitizer()
    anon_1 = sanitizer.anonymize_author("Rahul Sharma", "rev_101")
    anon_2 = sanitizer.anonymize_author("Rahul Sharma", "rev_101")
    anon_3 = sanitizer.anonymize_author("Priya Singh", "rev_102")
    assert anon_1.startswith("Reviewer ")
    assert anon_1 == anon_2  # Deterministic hash for same input
    assert anon_1 != anon_3

def test_sanitize_reviews_pipeline_with_word_and_emoji_filter():
    sanitizer = PIISanitizer(min_words=8, strip_emojis=True)
    raw_items = [
        # Review 1: 15 words with emojis and PII -> Kept, emojis removed, PII redacted
        ReviewItem(
            review_id="r1",
            date=datetime.now(timezone.utc),
            rating=1,
            text="Transferred ₹5000 via UPI (rahul@okicici) but money did not show in balance. Call 9876543210 immediately 😡🔥!",
            reviewer_name="Rahul S."
        ),
        # Review 2: 1 word noise -> Filtered out (< 8 words)
        ReviewItem(
            review_id="r2",
            date=datetime.now(timezone.utc),
            rating=5,
            text="good 👍👍",
            reviewer_name="Spam User"
        ),
        # Review 3: 5 words -> Filtered out (< 8 words)
        ReviewItem(
            review_id="r3",
            date=datetime.now(timezone.utc),
            rating=5,
            text="Very nice and smooth app",
            reviewer_name="Short User"
        ),
        # Review 4: 9 words -> Kept
        ReviewItem(
            review_id="r4",
            date=datetime.now(timezone.utc),
            rating=5,
            text="Mutual funds portfolio dashboard is clean and easy to navigate.",
            reviewer_name="Pooja K."
        )
    ]

    sanitized = sanitizer.sanitize_reviews(raw_items)
    # r2 and r3 should be filtered out (< 8 words)
    assert len(sanitized) == 2

    r1_clean = next(r for r in sanitized if r.id == "r1")
    assert r1_clean.contains_redacted_pii is True
    assert "[UPI_ID_REDACTED]" in r1_clean.sanitized_text
    assert "[PHONE_REDACTED]" in r1_clean.sanitized_text
    assert "9876543210" not in r1_clean.sanitized_text
    assert "😡" not in r1_clean.sanitized_text
    assert "🔥" not in r1_clean.sanitized_text
    assert r1_clean.word_count >= 8

    r4_clean = next(r for r in sanitized if r.id == "r4")
    assert r4_clean.contains_redacted_pii is False
    assert r4_clean.sanitized_text == "Mutual funds portfolio dashboard is clean and easy to navigate."
    assert r4_clean.word_count >= 8

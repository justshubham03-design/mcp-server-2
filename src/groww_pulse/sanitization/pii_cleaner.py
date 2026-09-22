import re
import hashlib
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field
from datetime import datetime

try:
    import regex
    USE_REGEX_MODULE = True
except ImportError:
    USE_REGEX_MODULE = False

from ..ingestion.models import ReviewItem

class SanitizedReview(BaseModel):
    """Sanitized review with PII and emojis purged, maintaining link to original verbatim text."""
    id: str = Field(..., description="Review ID")
    sanitized_text: str = Field(..., description="Text with PII and emojis redacted")
    original_text: str = Field(..., description="Original raw review text for exact verbatim grounding")
    rating: int = Field(..., ge=1, le=5)
    date: datetime
    thumbs_up: int = Field(default=0)
    app_version: Optional[str] = None
    anonymized_author: str = Field(..., description="Anonymized reviewer handle e.g. Reviewer a1b2")
    contains_redacted_pii: bool = Field(default=False)
    word_count: int = Field(default=0, description="Word count of cleaned text")

class PIISanitizer:
    # 1. Emoji Regex Pattern
    FALLBACK_EMOJI_REGEX = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags
        "\U00002700-\U000027BF"  # dingbats
        "\U00002600-\U000026FF"  # misc symbols
        "\U00002300-\U000023FF"  # misc technical
        "\U0001F900-\U0001F9FF"  # supplemental symbols
        "\U0001FA00-\U0001FAFF"  # symbols & pictographs extended
        "\u200d\ufe0f"           # joiner / variation
        "]+",
        flags=re.UNICODE
    )

    # 2. Email Patterns (standard and obfuscated)
    EMAIL_REGEX = re.compile(
        r'[\w\.-]+@[\w\.-]+\.\w+|[\w\.-]+\s*\[at\]\s*[\w\.-]+\s*\[dot\]\s*\w+|[\w\.-]+\s*\(at\)\s*[\w\.-]+\s*\(dot\)\s*\w+',
        re.IGNORECASE
    )

    # 3. Indian Phone Number Patterns (+91, 0, spaced, hyphenated, raw 10 digits)
    PHONE_REGEX = re.compile(
        r'(?:\+91[\-\s]?)?[6-9]\d{4}[\-\s]?\d{5}\b|(?:\b0[6-9]\d{9}\b)|\b[6-9]\d{9}\b',
        re.IGNORECASE
    )

    # 4. UPI ID Patterns (e.g. rahul@okhdfcbank, 9876543210@paytm)
    UPI_REGEX = re.compile(
        r'[\w\.\-_]+@(okhdfcbank|okaxis|okicici|oksbi|paytm|ybl|ibl|apl|axl|barodampay|upi)',
        re.IGNORECASE
    )

    # 5. PAN Card Number (5 letters, 4 digits, 1 letter)
    PAN_REGEX = re.compile(r'\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b')

    # 6. Aadhaar Card Number (12 digits, spaced or continuous)
    AADHAAR_REGEX = re.compile(r'\b[2-9]{1}\d{3}\s?\d{4}\s?\d{4}\b')

    # 7. IFSC Code Pattern
    IFSC_REGEX = re.compile(r'\b[A-Z]{4}0[A-Z0-9]{6}\b')

    # 8. Bank Account Number Pattern (9 to 18 digits with context or word boundary)
    BANK_ACC_REGEX = re.compile(r'(?:A/C|acc(?:ount)?(?:\s*no)?:?[\s#]*)\d{9,18}\b|\b\d{12,18}\b', re.IGNORECASE)

    # 9. Single-word non-informative reviews list
    NOISE_WORDS = {
        "good", "nice", "ok", "okay", "bad", "worst", "super", "poor", "fabulous", 
        "awesome", "best", "great", "fine", "cool", "superb", "excellent", "love it",
        "bakwas", "mast", "bekar", "ghatiya", "nice app", "good app", "best app", "worst app",
        "helpful", "useful", "thank you", "thanks", "5 star", "one of the best"
    }

    def __init__(
        self,
        min_words: int = 8,
        strip_emojis: bool = True,
        filter_noise: bool = True,
        redact_pii: bool = True
    ):
        self.min_words = min_words
        self.strip_emojis = strip_emojis
        self.filter_noise = filter_noise
        self.redact_pii = redact_pii

    def remove_emojis(self, text: str) -> str:
        """Strips all emoji and pictographic symbols from text."""
        if not text:
            return ""
        if USE_REGEX_MODULE:
            # High-precision Unicode regex emoji removal
            cleaned = regex.sub(r'\p{Extended_Pictographic}|\p{Emoji_Presentation}', '', text)
        else:
            cleaned = self.FALLBACK_EMOJI_REGEX.sub('', text)
        # Clean up any resulting double spaces
        return re.sub(r'\s+', ' ', cleaned).strip()

    def sanitize_text(self, text: str) -> Tuple[str, bool]:
        """
        Cleans text: strips emojis, redacts PII, and normalizes spacing.
        Returns (cleaned_text, had_pii).
        """
        if not text:
            return "", False

        cleaned = text
        had_pii = False

        # 1. Strip emojis if enabled
        if self.strip_emojis:
            cleaned = self.remove_emojis(cleaned)

        if not self.redact_pii:
            return cleaned.strip(), False

        # 2. Redact Emails
        if self.EMAIL_REGEX.search(cleaned):
            cleaned = self.EMAIL_REGEX.sub("[EMAIL_REDACTED]", cleaned)
            had_pii = True

        # 3. Redact UPI IDs
        if self.UPI_REGEX.search(cleaned):
            cleaned = self.UPI_REGEX.sub("[UPI_ID_REDACTED]", cleaned)
            had_pii = True

        # 4. Redact PAN numbers
        if self.PAN_REGEX.search(cleaned):
            cleaned = self.PAN_REGEX.sub("[PAN_REDACTED]", cleaned)
            had_pii = True

        # 5. Redact Aadhaar numbers
        if self.AADHAAR_REGEX.search(cleaned):
            cleaned = self.AADHAAR_REGEX.sub("[AADHAAR_REDACTED]", cleaned)
            had_pii = True

        # 6. Redact IFSC codes
        if self.IFSC_REGEX.search(cleaned):
            cleaned = self.IFSC_REGEX.sub("[IFSC_REDACTED]", cleaned)
            had_pii = True

        # 7. Redact Phone Numbers
        if self.PHONE_REGEX.search(cleaned):
            cleaned = self.PHONE_REGEX.sub("[PHONE_REDACTED]", cleaned)
            had_pii = True

        # 8. Redact Bank Account Numbers
        if self.BANK_ACC_REGEX.search(cleaned):
            cleaned = self.BANK_ACC_REGEX.sub("[ACCOUNT_NO_REDACTED]", cleaned)
            had_pii = True

        # 9. Clean excessive whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        return cleaned, had_pii

    def anonymize_author(self, author_name: Optional[str], review_id: str) -> str:
        """Converts real reviewer name into an anonymized identifier like 'Reviewer a1b2'."""
        salt = f"{author_name}_{review_id}"
        hash_digest = hashlib.md5(salt.encode()).hexdigest()[:4]
        return f"Reviewer {hash_digest}"

    def count_words(self, text: str) -> int:
        """Counts words in text, ignoring standalone punctuation."""
        tokens = [w for w in text.split() if any(c.isalnum() for c in w)]
        return len(tokens)

    def is_noise(self, text: str) -> bool:
        """
        Detects if review is trivial noise (1-word non-informative or word count < min_words).
        """
        normalized = text.lower().strip().strip(".!?,")
        if not normalized:
            return True
        if normalized in self.NOISE_WORDS:
            return True
        
        # Word count check: Drop reviews with fewer than min_words
        word_count = self.count_words(normalized)
        if word_count < self.min_words:
            return True

        # Character substance check
        alphanumeric_count = sum(c.isalnum() for c in normalized)
        if alphanumeric_count < 10:
            return True

        return False

    def sanitize_reviews(self, raw_reviews: List[ReviewItem]) -> List[SanitizedReview]:
        """
        Processes raw ReviewItem objects into SanitizedReview objects.
        - Strips all emojis
        - Redacts all PII
        - Drops reviews with fewer than min_words (default 8)
        - Drops trivial noise
        """
        sanitized_list: List[SanitizedReview] = []

        for item in raw_reviews:
            raw_text = item.text.strip()
            if not raw_text:
                continue

            cleaned_text, had_pii = self.sanitize_text(raw_text)

            # Filter noise and enforce minimum 8 words
            if self.filter_noise and self.is_noise(cleaned_text):
                continue

            words = self.count_words(cleaned_text)
            if words < self.min_words:
                continue

            sanitized_item = SanitizedReview(
                id=item.review_id,
                sanitized_text=cleaned_text,
                original_text=raw_text,
                rating=item.rating,
                date=item.date,
                thumbs_up=item.thumbs_up,
                app_version=item.app_version,
                anonymized_author=self.anonymize_author(item.reviewer_name, item.review_id),
                contains_redacted_pii=had_pii,
                word_count=words
            )
            sanitized_list.append(sanitized_item)

        return sanitized_list

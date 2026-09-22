import os
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Tuple, List

from .play_store import PlayStoreIngestion
from .models import ReviewItem
from ..sanitization.pii_cleaner import PIISanitizer, SanitizedReview

logger = logging.getLogger(__name__)

def download_and_extract_8weeks(
    package_id: str = "com.nextbillion.groww",
    weeks_lookback: int = 8,
    max_reviews: int = 5000,
    output_dir: str = "data"
) -> Dict[str, Any]:
    """
    Downloads and extracts all reviews for the last 8 weeks from Google Play Store,
    sanitizes PII, filters noise, and saves both raw and sanitized datasets.
    """
    os.makedirs(output_dir, exist_ok=True)
    raw_output_path = os.path.join(output_dir, "reviews_raw_8weeks.json")
    sanitized_output_path = os.path.join(output_dir, "reviews_sanitized_8weeks.json")
    stats_output_path = os.path.join(output_dir, "ingestion_stats_8weeks.json")

    # 1. Fetch raw reviews
    ingestion = PlayStoreIngestion(package_id=package_id, cache_file=raw_output_path)
    raw_reviews = ingestion.fetch_reviews(
        weeks_lookback=weeks_lookback,
        max_reviews=max_reviews,
        use_cache_fallback=True
    )

    # 2. Sanitize reviews
    sanitizer = PIISanitizer(min_words=8, strip_emojis=True, filter_noise=True, redact_pii=True)
    sanitized_reviews = sanitizer.sanitize_reviews(raw_reviews)

    # 3. Save raw dataset
    with open(raw_output_path, "w", encoding="utf-8") as f:
        json.dump([r.model_dump() for r in raw_reviews], f, default=str, indent=2)

    # 4. Save sanitized dataset
    with open(sanitized_output_path, "w", encoding="utf-8") as f:
        json.dump([r.model_dump() for r in sanitized_reviews], f, default=str, indent=2)

    # 5. Compute extraction statistics
    rating_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for r in raw_reviews:
        if r.rating in rating_counts:
            rating_counts[r.rating] += 1

    pii_redacted_count = sum(1 for r in sanitized_reviews if r.contains_redacted_pii)
    noise_dropped_count = len(raw_reviews) - len(sanitized_reviews)

    dates = [r.date for r in raw_reviews] if raw_reviews else []
    earliest_date = min(dates).isoformat() if dates else None
    latest_date = max(dates).isoformat() if dates else None

    stats = {
        "package_id": package_id,
        "weeks_lookback": weeks_lookback,
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "total_raw_reviews": len(raw_reviews),
        "total_sanitized_reviews": len(sanitized_reviews),
        "noise_dropped_count": noise_dropped_count,
        "pii_redacted_count": pii_redacted_count,
        "date_range": {
            "earliest": earliest_date,
            "latest": latest_date
        },
        "rating_distribution": rating_counts,
        "raw_file": raw_output_path,
        "sanitized_file": sanitized_output_path
    }

    with open(stats_output_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)

    return stats

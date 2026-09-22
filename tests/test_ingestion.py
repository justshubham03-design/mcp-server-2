import os
import tempfile
from datetime import datetime, timedelta, timezone
from src.groww_pulse.ingestion import ReviewItem, PlayStoreIngestion

def test_mock_reviews_generation():
    reviews = PlayStoreIngestion.generate_mock_groww_reviews(weeks_lookback=10, count=30)
    assert len(reviews) == 30
    for r in reviews:
        assert isinstance(r, ReviewItem)
        assert r.app_id == "com.nextbillion.groww"
        assert 1 <= r.rating <= 5
        assert len(r.text) > 0
        assert r.date is not None

def test_timeframe_filtering():
    now = datetime.now(timezone.utc)
    old_date = now - timedelta(weeks=15)
    recent_date = now - timedelta(weeks=4)

    item_old = ReviewItem(
        review_id="old_1",
        date=old_date,
        rating=1,
        text="Old review outside window",
        reviewer_name="Old User"
    )
    item_recent = ReviewItem(
        review_id="recent_1",
        date=recent_date,
        rating=5,
        text="Recent review inside window",
        reviewer_name="Recent User"
    )

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        temp_cache_path = tf.name

    try:
        ingestion = PlayStoreIngestion(cache_file=temp_cache_path)
        ingestion._save_to_cache([item_old, item_recent])

        loaded = ingestion._load_from_cache(cutoff_date=now - timedelta(weeks=10))
        assert len(loaded) == 1
        assert loaded[0].review_id == "recent_1"
    finally:
        if os.path.exists(temp_cache_path):
            os.remove(temp_cache_path)

def test_review_item_serialization():
    now = datetime.now(timezone.utc)
    item = ReviewItem(
        review_id="test_001",
        date=now,
        rating=4,
        text="Great app for mutual fund SIP investments",
        thumbs_up=5,
        app_version="14.3.0",
        reviewer_name="John Doe"
    )
    data = item.model_dump()
    assert data["review_id"] == "test_001"
    assert data["rating"] == 4
    assert data["thumbs_up"] == 5

def test_download_and_extract_pipeline_mock(monkeypatch):
    from src.groww_pulse.ingestion import download_and_extract_8weeks
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        stats = download_and_extract_8weeks(
            package_id="com.nextbillion.groww",
            weeks_lookback=8,
            max_reviews=50,
            output_dir=tmpdir
        )
        assert stats["total_raw_reviews"] > 0
        assert stats["total_sanitized_reviews"] > 0
        assert os.path.exists(stats["raw_file"])
        assert os.path.exists(stats["sanitized_file"])


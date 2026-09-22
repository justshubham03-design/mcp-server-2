import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from .taxonomy import ThemeCategory, GROWW_TAXONOMY, TaxonomyDefinition
from ..sanitization.pii_cleaner import SanitizedReview

class ThemeClusterResult(BaseModel):
    theme_id: str
    theme_name: str
    description: str
    review_count: int
    percentage_of_total: float
    average_rating: float
    sentiment: str
    total_thumbs_up: int
    sample_reviews: List[str] = Field(default_factory=list, description="List of review IDs")
    verbatim_candidates: List[str] = Field(default_factory=list, description="Verbatim quotes from this theme")

class ThemeClusterer:
    def __init__(self, max_themes: int = 5, top_themes_count: int = 3):
        self.max_themes = max_themes
        self.top_themes_count = top_themes_count
        self.taxonomy = GROWW_TAXONOMY

    def _classify_review(self, text: str) -> ThemeCategory:
        """
        Classifies a single review into one of the 5 canonical Groww themes based on keyword score.
        Falls back to APP_PERFORMANCE_UI if general feedback.
        """
        lower_text = text.lower()
        scores: Dict[ThemeCategory, int] = {cat: 0 for cat in ThemeCategory}

        for cat, tax_def in self.taxonomy.items():
            for kw in tax_def.keywords:
                pattern = r'\b' + re.escape(kw) + r'\b'
                matches = len(re.findall(pattern, lower_text))
                if matches > 0:
                    scores[cat] += matches * (2 if len(kw.split()) > 1 else 1)

        best_category = max(scores, key=lambda k: scores[k])
        if scores[best_category] == 0:
            return ThemeCategory.APP_PERFORMANCE_UI
        return best_category

    def _extract_concise_verbatim_quotes(self, review: SanitizedReview) -> List[str]:
        """
        Extracts concise, punchy verbatim sentence snippets (8 to 22 words) from a review.
        Guarantees that each extracted quote is an exact substring in the original review.
        """
        raw_text = review.sanitized_text.strip()
        # Split into sentences while preserving exact substring integrity
        sentences = re.split(r'(?<=[.!?])\s+', raw_text)
        valid_quotes = []

        for s in sentences:
            s_clean = s.strip()
            word_count = len(s_clean.split())
            if 8 <= word_count <= 22 and s_clean in review.sanitized_text:
                valid_quotes.append(s_clean)

        # If full text itself is concise
        if not valid_quotes and 8 <= review.word_count <= 25:
            valid_quotes.append(raw_text)

        return valid_quotes

    def cluster(self, reviews: List[SanitizedReview]) -> List[ThemeClusterResult]:
        """
        Clusters a list of SanitizedReview objects into at most 5 themes and computes metrics.
        Returns a list of ThemeClusterResult sorted by priority.
        """
        if not reviews:
            return []

        total_reviews = len(reviews)
        buckets: Dict[ThemeCategory, List[SanitizedReview]] = {cat: [] for cat in ThemeCategory}

        for r in reviews:
            cat = self._classify_review(r.sanitized_text)
            buckets[cat].append(r)

        results: List[ThemeClusterResult] = []

        for cat, matched_reviews in buckets.items():
            tax_def = self.taxonomy[cat]
            count = len(matched_reviews)
            pct = round((count / total_reviews) * 100, 1) if total_reviews > 0 else 0.0

            if count > 0:
                avg_rating = round(sum(r.rating for r in matched_reviews) / count, 2)
                total_thumbs = sum(r.thumbs_up for r in matched_reviews)

                if avg_rating >= 3.8:
                    sentiment = "positive"
                elif avg_rating <= 2.4:
                    sentiment = "negative"
                else:
                    sentiment = "neutral"

                sorted_candidates = sorted(
                    matched_reviews,
                    key=lambda r: (
                        not r.contains_redacted_pii,
                        r.thumbs_up,
                        r.word_count <= 30, # Prefer concise reviews
                        r.word_count
                    ),
                    reverse=True
                )

                sample_ids = [r.id for r in sorted_candidates[:10]]

                # Extract concise verbatim quotes
                verbatim_candidates = []
                for r in sorted_candidates:
                    quotes = self._extract_concise_verbatim_quotes(r)
                    for q in quotes:
                        if q not in verbatim_candidates:
                            verbatim_candidates.append(q)
                        if len(verbatim_candidates) >= 5:
                            break
                    if len(verbatim_candidates) >= 5:
                        break

                if not verbatim_candidates:
                    # Fallback to shortest valid review texts
                    for r in sorted_candidates:
                        if r.word_count >= 8:
                            verbatim_candidates.append(r.sanitized_text[:120].strip())
                        if len(verbatim_candidates) >= 3:
                            break

            else:
                avg_rating = 0.0
                total_thumbs = 0
                sentiment = "neutral"
                sample_ids = []
                verbatim_candidates = []

            results.append(
                ThemeClusterResult(
                    theme_id=cat.value,
                    theme_name=tax_def.name,
                    description=tax_def.description,
                    review_count=count,
                    percentage_of_total=pct,
                    average_rating=avg_rating,
                    sentiment=sentiment,
                    total_thumbs_up=total_thumbs,
                    sample_reviews=sample_ids,
                    verbatim_candidates=verbatim_candidates
                )
            )

        results = results[:self.max_themes]

        results.sort(
            key=lambda t: (
                t.review_count,
                -t.average_rating if t.review_count > 0 else 0,
                t.total_thumbs_up
            ),
            reverse=True
        )

        return results

    def get_top_themes(self, clustered_results: List[ThemeClusterResult]) -> List[ThemeClusterResult]:
        """Returns the top 3 dominant themes for the executive pulse note."""
        return [t for t in clustered_results if t.review_count > 0][:self.top_themes_count]

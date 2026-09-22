import re
from typing import List, Set, Tuple, Optional
from .schemas import WeeklyPulse, PulseValidationResult
from ..sanitization.pii_cleaner import SanitizedReview

class PulseValidator:
    def __init__(self, max_word_limit: int = 250, required_quotes: int = 3, required_actions: int = 3):
        self.max_word_limit = max_word_limit
        self.required_quotes = required_quotes
        self.required_actions = required_actions

    def count_pulse_words(self, pulse: WeeklyPulse) -> int:
        """
        Computes total word count for the executive pulse note.
        Counts words in summary, top 3 themes, 3 quotes, and 3 action items.
        """
        text_blocks = [pulse.executive_summary]
        
        for theme in pulse.top_themes:
            text_blocks.append(theme.name)
            text_blocks.append(theme.metric)
            text_blocks.append(theme.summary)

        for quote in pulse.verbatim_quotes:
            text_blocks.append(quote)

        for action in pulse.action_ideas:
            text_blocks.append(action)

        combined_text = " ".join(text_blocks)
        # Tokenize by whitespace ignoring standalone punctuation
        words = [w for w in combined_text.split() if any(c.isalnum() for c in w)]
        return len(words)

    def verify_quote_grounding(
        self,
        quote: str,
        corpus_texts: List[str]
    ) -> bool:
        """
        Verifies that a quote exists as an exact verbatim substring in the review corpus.
        Normalizes internal whitespace and quotes/apostrophes for robust substring checking.
        """
        if not quote or len(quote.strip()) == 0:
            return False

        clean_quote = " ".join(quote.strip().strip('"\'').split()).lower()

        for review_text in corpus_texts:
            clean_corpus_text = " ".join(review_text.split()).lower()
            if clean_quote in clean_corpus_text:
                return True

        return False

    def validate(
        self,
        pulse: WeeklyPulse,
        reviews: List[SanitizedReview]
    ) -> PulseValidationResult:
        """
        Validates the weekly pulse against all strict project constraints:
        1. Length: <= 250 words total.
        2. Verbatim Grounding: Exactly 3 quotes, each verified as an exact substring in the input corpus.
        3. Themes: Exactly 3 top themes provided.
        4. Actions: Exactly 3 concrete action ideas provided.
        """
        errors: List[str] = []
        quotes_verified: List[bool] = []
        unmatched_quotes: List[str] = []

        # 1. Word Count Check
        actual_word_count = self.count_pulse_words(pulse)
        pulse.word_count = actual_word_count

        if actual_word_count > self.max_word_limit:
            errors.append(
                f"Word count constraint violated: {actual_word_count} words (max allowed: {self.max_word_limit})."
            )

        # 2. Top Themes Count Check
        if len(pulse.top_themes) != 3:
            errors.append(f"Top themes count is {len(pulse.top_themes)}; exactly 3 required.")

        # 3. Action Ideas Count Check
        if len(pulse.action_ideas) != self.required_actions:
            errors.append(f"Action ideas count is {len(pulse.action_ideas)}; exactly {self.required_actions} required.")

        # 4. Verbatim Quote Grounding Check
        # Build search space from both sanitized_text and original_text
        corpus_texts: List[str] = []
        for r in reviews:
            corpus_texts.append(r.sanitized_text)
            if r.original_text:
                corpus_texts.append(r.original_text)

        if len(pulse.verbatim_quotes) != self.required_quotes:
            errors.append(
                f"Verbatim quotes count is {len(pulse.verbatim_quotes)}; exactly {self.required_quotes} required."
            )

        for q in pulse.verbatim_quotes:
            is_matched = self.verify_quote_grounding(q, corpus_texts)
            quotes_verified.append(is_matched)
            if not is_matched:
                unmatched_quotes.append(q)
                errors.append(
                    f"Grounding failure: Quote \"{q}\" is not an exact verbatim substring in the review corpus."
                )

        is_valid = len(errors) == 0

        return PulseValidationResult(
            is_valid=is_valid,
            word_count=actual_word_count,
            max_word_limit=self.max_word_limit,
            quotes_verified=quotes_verified,
            unmatched_quotes=unmatched_quotes,
            errors=errors
        )

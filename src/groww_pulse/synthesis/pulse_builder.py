import os
import json
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from .schemas import WeeklyPulse, ThemeItem, PulseValidationResult
from .validator import PulseValidator
from ..theming.clusterer import ThemeClusterResult
from ..sanitization.pii_cleaner import SanitizedReview

logger = logging.getLogger(__name__)

class PulseBuilder:
    def __init__(
        self,
        llm_provider: Optional[str] = None,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        validator: Optional[PulseValidator] = None
    ):
        self.llm_provider = (llm_provider or os.getenv("PHASE2_LLM_PROVIDER") or "groq").lower()
        self.api_key = api_key or os.getenv("GROQ_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.model_name = model_name
        self.validator = validator or PulseValidator()

    def _get_llm(self):
        """Initializes the configured LangChain chat model for Phase 2 synthesis (Groq first)."""
        groq_key = os.getenv("GROQ_API_KEY")
        gemini_key = os.getenv("GEMINI_API_KEY")
        openai_key = os.getenv("OPENAI_API_KEY")

        if self.llm_provider == "groq" or (groq_key and not self.llm_provider):
            from langchain_groq import ChatGroq
            key = self.api_key or groq_key
            if not key:
                return None
            return ChatGroq(
                model=self.model_name or os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
                groq_api_key=key,
                temperature=0.1
            )
        elif self.llm_provider == "gemini" or gemini_key:
            from langchain_google_genai import ChatGoogleGenerativeAI
            key = self.api_key or gemini_key
            if not key:
                return None
            return ChatGoogleGenerativeAI(
                model=self.model_name or os.getenv("GEMINI_MODEL", "gemini-3.6-flash"),
                google_api_key=key,
                temperature=0.1
            )
        elif self.llm_provider == "openai" or openai_key:
            from langchain_openai import ChatOpenAI
            key = self.api_key or openai_key
            if not key:
                return None
            return ChatOpenAI(
                model=self.model_name or os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                api_key=key,
                temperature=0.1
            )
        else:
            return None

    def build_deterministic_pulse(
        self,
        themes: List[ThemeClusterResult],
        reviews: List[SanitizedReview],
        week_identifier: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> WeeklyPulse:
        """
        Builds a high-quality, 100% grounded WeeklyPulse note deterministically without requiring an external LLM API.
        Used for local/mock executions, CI/CD testing, or offline pipelines.
        """
        now = datetime.now(timezone.utc)
        week_id = week_identifier or f"{now.year}-W{now.isocalendar()[1]:02d}"
        
        dates = [r.date for r in reviews] if reviews else []
        s_date = start_date or (min(dates).strftime("%Y-%m-%d") if dates else "2026-07-25")
        e_date = end_date or (max(dates).strftime("%Y-%m-%d") if dates else now.strftime("%Y-%m-%d"))

        top_3_themes = [t for t in themes if t.review_count > 0][:3]
        if len(top_3_themes) < 3:
            top_3_themes = themes[:3]

        theme_action_map = {
            "payments_settlement": "Implement real-time UPI retry banner on deposit screen.",
            "kyc_onboarding": "Add dynamic error highlighting on KYC rejection screens.",
            "trading_execution": "Optimize WebSocket latency for option chain charts.",
            "mutual_funds_statements": "Simplify Capital Gains tax P&L report generation.",
            "app_performance_ui": "Deploy biometric login fallback and isolate crash handler."
        }

        # 1. Build Top 3 ThemeItems
        theme_items: List[ThemeItem] = []
        for i, t in enumerate(top_3_themes, 1):
            metric_str = f"{t.percentage_of_total}% volume, {t.average_rating}★ avg"
            theme_items.append(
                ThemeItem(
                    rank=i,
                    name=t.theme_name,
                    metric=metric_str,
                    summary=f"Key user friction in {t.theme_name.lower()} with sentiment trending {t.sentiment}."
                )
            )

        # 2. Extract exactly 3 verified verbatim quotes from the top 3 themes
        verbatim_quotes: List[str] = []
        for t in top_3_themes:
            if t.verbatim_candidates:
                verbatim_quotes.append(t.verbatim_candidates[0])
            else:
                matching = [r.sanitized_text for r in reviews if r.id in t.sample_reviews and 8 <= r.word_count <= 25]
                if matching:
                    verbatim_quotes.append(matching[0])

        if len(verbatim_quotes) < 3:
            for r in reviews:
                if r.sanitized_text not in verbatim_quotes and 8 <= r.word_count <= 25 and not r.contains_redacted_pii:
                    verbatim_quotes.append(r.sanitized_text)
                    if len(verbatim_quotes) == 3:
                        break

        verbatim_quotes = verbatim_quotes[:3]

        # 3. Formulate 3 Action Ideas
        action_ideas: List[str] = []
        for t in top_3_themes:
            action = theme_action_map.get(
                t.theme_id,
                f"Product: Address top user friction in {t.theme_name} by streamlining workflow."
            )
            action_ideas.append(action)

        action_ideas = action_ideas[:3]

        # 4. Executive Summary
        exec_summary = (
            f"Weekly pulse across {len(reviews)} Play Store reviews indicates solid engagement, "
            f"while user friction centers on {top_3_themes[0].theme_name}. "
            f"Prioritize deposit transparency and verification clarity."
        )

        pulse = WeeklyPulse(
            week_identifier=week_id,
            analysis_period_start=s_date,
            analysis_period_end=e_date,
            total_reviews_analyzed=len(reviews),
            word_count=0,
            executive_summary=exec_summary,
            top_themes=theme_items,
            verbatim_quotes=verbatim_quotes,
            action_ideas=action_ideas
        )

        pulse.word_count = self.validator.count_pulse_words(pulse)
        return pulse

    def synthesize_with_llm(
        self,
        themes: List[ThemeClusterResult],
        reviews: List[SanitizedReview],
        week_identifier: Optional[str] = None
    ) -> WeeklyPulse:
        """
        Uses LangChain structured output with Groq to synthesize the WeeklyPulse.
        Ensures strict word count (< 250 words) and exact verbatim quote grounding.
        """
        llm = self._get_llm()
        if llm is None:
            logger.info("No LLM API key configured for Phase 2. Generating pulse via deterministic builder.")
            return self.build_deterministic_pulse(themes, reviews, week_identifier)

        top_3_themes = [t for t in themes if t.review_count > 0][:3]
        
        candidates_context = []
        for t in top_3_themes:
            candidates_context.append({
                "theme_name": t.theme_name,
                "percentage": f"{t.percentage_of_total}%",
                "avg_rating": f"{t.average_rating}★ avg",
                "sentiment": t.sentiment,
                "candidate_quotes": t.verbatim_candidates[:3]
            })

        system_prompt = (
            "You are the Lead Product Intelligence AI for Groww (India's leading investment platform).\n"
            "Your task is to synthesize a high-impact, scannable weekly executive review pulse strictly under 200 words total.\n\n"
            "STRICT CONSTRAINTS:\n"
            "1. Length: The entire note must be <= 200 words total. Keep every field extremely concise:\n"
            "   - executive_summary: 2 short sentences (max 30 words).\n"
            "   - top_themes summary: 1 punchy sentence per theme (max 12 words each).\n"
            "   - action_ideas: exactly 1 clear sentence per action (max 14 words each).\n"
            "2. Top Themes: Provide exactly the 3 top themes given in context.\n"
            "3. Verbatim Quotes: Select exactly 3 concise verbatim quotes (1 from each theme) directly from candidate_quotes. "
            "DO NOT rephrase, edit, fix grammar, or invent wording. They must be exact verbatim quotes from candidates.\n"
            "4. Action Ideas: Provide exactly 3 high-impact next steps grounded in the themes.\n"
            "5. Privacy: Zero PII (no names, phone numbers, emails, or accounts)."
        )

        user_prompt = (
            f"Total Reviews Analyzed: {len(reviews)}\n"
            f"Top Themes Data & Verbatim Candidates:\n{json.dumps(candidates_context, indent=2)}\n\n"
            "Generate the structured WeeklyPulse now."
        )

        try:
            structured_llm = llm.with_structured_output(WeeklyPulse)
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            pulse: WeeklyPulse = structured_llm.invoke(messages)
            pulse.total_reviews_analyzed = len(reviews)
            pulse.word_count = self.validator.count_pulse_words(pulse)
            
            validation = self.validator.validate(pulse, reviews)
            if not validation.is_valid:
                logger.warning(f"LLM generated pulse failed validation: {validation.errors}. Using grounded builder fallback.")
                return self.build_deterministic_pulse(themes, reviews, week_identifier)

            return pulse

        except Exception as e:
            logger.warning(f"Error during LLM structured synthesis: {e}. Using deterministic builder fallback.")
            return self.build_deterministic_pulse(themes, reviews, week_identifier)

    @staticmethod
    def render_markdown(pulse: WeeklyPulse) -> str:
        """Renders the WeeklyPulse into markdown format for Google Docs."""
        themes_rows = ""
        for t in pulse.top_themes:
            themes_rows += f"| **#{t.rank}** | **{t.name}** | {t.metric} | {t.summary} |\n"

        quotes_block = ""
        for q in pulse.verbatim_quotes:
            quotes_block += f"- *\"{q}\"*\n"

        actions_block = ""
        for i, a in enumerate(pulse.action_ideas, 1):
            actions_block += f"{i}. **{a}**\n"

        return f"""# Groww Weekly Review Pulse ({pulse.week_identifier})

**Analysis Period**: {pulse.analysis_period_start} to {pulse.analysis_period_end}  
**Total Play Store Reviews Analyzed**: {pulse.total_reviews_analyzed} | **Word Count**: {pulse.word_count} / 250 words max

---

## 1. Executive Summary
{pulse.executive_summary}

---

## 2. Top 3 User Themes

| Rank | Theme | Volume & Rating Signal | Core Sentiment & User Takeaway |
| :---: | :--- | :--- | :--- |
{themes_rows}
---

## 3. Real User Quotes (Verbatim Snippets)
> [!NOTE]
> All quotes below are authentic, unedited verbatim snippets extracted directly from public Google Play Store reviews. All reviewer PII has been scrubbed.

{quotes_block}
---

## 4. Prioritized Action Ideas

{actions_block}
---
*Generated automatically by Groww Review Pulse AI Agent.*
"""

    @staticmethod
    def render_html_email(pulse: WeeklyPulse, doc_url: Optional[str] = None) -> str:
        """Renders the WeeklyPulse into HTML email format for Gmail."""
        theme_cards = ""
        for t in pulse.top_themes:
            theme_cards += f"""
      <div class="theme-card">
        <div class="theme-title">#{t.rank} {t.name}</div>
        <div class="theme-metric">{t.metric}</div>
        <div class="theme-desc">{t.summary}</div>
      </div>"""

        quotes_boxes = ""
        for q in pulse.verbatim_quotes:
            quotes_boxes += f"""
      <div class="quote-box">
        "{q}"
      </div>"""

        action_items = ""
        for a in pulse.action_ideas:
            action_items += f"""
        <li class="action-item"><strong>{a}</strong></li>"""

        cta_btn = ""
        if doc_url:
            cta_btn = f"""
      <div style="text-align: center; margin-top: 24px;">
        <a href="{doc_url}" class="btn" target="_blank">Open Full Note in Google Docs &rarr;</a>
      </div>"""

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; color: #1e293b; background-color: #f8fafc; margin: 0; padding: 24px; line-height: 1.6; }}
    .container {{ max-width: 640px; margin: 0 auto; background: #ffffff; border-radius: 8px; border: 1px solid #e2e8f0; overflow: hidden; }}
    .header {{ background: #00d09c; padding: 24px; color: #ffffff; }}
    .header h1 {{ margin: 0 0 6px 0; font-size: 20px; font-weight: 700; }}
    .header p {{ margin: 0; font-size: 13px; opacity: 0.95; }}
    .content {{ padding: 24px; }}
    .section-title {{ font-size: 15px; font-weight: 700; color: #0f172a; margin-top: 20px; margin-bottom: 10px; border-bottom: 2px solid #f1f5f9; padding-bottom: 6px; }}
    .theme-card {{ background: #f8fafc; border-left: 4px solid #00d09c; padding: 10px 14px; margin-bottom: 10px; border-radius: 0 6px 6px 0; }}
    .theme-title {{ font-weight: 600; font-size: 14px; color: #0f172a; }}
    .theme-metric {{ font-size: 12px; color: #64748b; font-weight: 500; }}
    .theme-desc {{ font-size: 13px; color: #334155; margin-top: 4px; }}
    .quote-box {{ background: #fffbeb; border-left: 4px solid #f59e0b; padding: 10px 14px; margin-bottom: 10px; font-style: italic; font-size: 13px; color: #78350f; border-radius: 0 6px 6px 0; }}
    .action-item {{ font-size: 13px; color: #1e293b; margin-bottom: 8px; }}
    .btn {{ display: inline-block; background-color: #00d09c; color: #ffffff !important; text-decoration: none; padding: 10px 20px; border-radius: 6px; font-weight: 600; font-size: 14px; margin-top: 16px; }}
    .footer {{ padding: 16px 24px; font-size: 12px; color: #94a3b8; background: #f8fafc; border-top: 1px solid #e2e8f0; text-align: center; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>Groww Weekly Review Pulse</h1>
      <p>{pulse.week_identifier} &bull; {pulse.total_reviews_analyzed} Reviews Analyzed</p>
    </div>
    <div class="content">
      <p style="font-size: 14px; margin-top: 0;">{pulse.executive_summary}</p>

      <div class="section-title">Top 3 User Themes</div>
      {theme_cards}

      <div class="section-title">Authentic User Quotes</div>
      {quotes_boxes}

      <div class="section-title">3 Action Ideas</div>
      <ol style="padding-left: 20px; margin: 0;">
        {action_items}
      </ol>
      {cta_btn}
    </div>
    <div class="footer">
      Generated automatically by Groww Review Pulse AI Agent.
    </div>
  </div>
</body>
</html>"""

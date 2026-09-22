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
        """Renders the WeeklyPulse into a clean, arranged, inline-styled HTML email format for Gmail."""
        theme_cards = ""
        for t in pulse.top_themes:
            theme_cards += f"""
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom: 12px; background-color: #f8fafc; border: 1px solid #e2e8f0; border-left: 4px solid #00d09c; border-radius: 0 8px 8px 0;">
          <tr>
            <td style="padding: 12px 16px;">
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td style="font-weight: 700; font-size: 14px; color: #0f172a;">#{t.rank} {t.name}</td>
                  <td align="right" style="font-size: 11px; font-weight: 700; color: #008765; background-color: #e6fffa; padding: 2px 8px; border-radius: 12px; white-space: nowrap;">{t.metric}</td>
                </tr>
              </table>
              <div style="font-size: 13px; color: #475569; line-height: 1.5; margin-top: 6px;">{t.summary}</div>
            </td>
          </tr>
        </table>"""

        quotes_boxes = ""
        for q in pulse.verbatim_quotes:
            quotes_boxes += f"""
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom: 10px; background-color: #fffbeb; border: 1px solid #fef3c7; border-left: 4px solid #f59e0b; border-radius: 0 8px 8px 0;">
          <tr>
            <td style="padding: 12px 16px; font-size: 13px; font-style: italic; color: #92400e; line-height: 1.5;">
              "{q}"
            </td>
          </tr>
        </table>"""

        action_items = ""
        for i, a in enumerate(pulse.action_ideas, 1):
            action_items += f"""
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom: 8px; background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;">
          <tr>
            <td width="32" valign="top" style="padding: 12px 0 12px 14px;">
              <div style="background-color: #00d09c; color: #ffffff; font-weight: 800; font-size: 11px; width: 22px; height: 22px; border-radius: 50%; text-align: center; line-height: 22px;">{i}</div>
            </td>
            <td style="padding: 12px 14px 12px 8px; font-size: 13px; color: #1e293b; font-weight: 600; line-height: 1.45;">
              {a}
            </td>
          </tr>
        </table>"""

        cta_btn = ""
        if doc_url:
            cta_btn = f"""
        <div style="text-align: center; margin-top: 24px; margin-bottom: 10px;">
          <a href="{doc_url}" style="background-color: #00d09c; color: #0b1311; text-decoration: none; padding: 12px 24px; border-radius: 8px; font-weight: 700; font-size: 13px; display: inline-block;" target="_blank">Open Full Note in Google Docs &rarr;</a>
        </div>"""

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Groww Weekly Review Pulse</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1e293b; background-color: #f1f5f9; margin: 0; padding: 20px; line-height: 1.6;">
  <table width="100%" cellpadding="0" cellspacing="0" border="0">
    <tr>
      <td align="center">
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width: 620px; background-color: #ffffff; border-radius: 12px; border: 1px solid #e2e8f0; overflow: hidden; text-align: left; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);">
          
          <!-- Header -->
          <tr>
            <td style="background-color: #00d09c; padding: 24px 28px; color: #ffffff;">
              <h1 style="margin: 0 0 6px 0; font-size: 22px; font-weight: 800; color: #ffffff; letter-spacing: -0.5px;">Groww Weekly Review Pulse</h1>
              <p style="margin: 0; font-size: 13px; color: #f0fdf9; font-weight: 500;">
                📅 <strong>{pulse.week_identifier}</strong> &bull; 📊 <strong>{pulse.total_reviews_analyzed}</strong> Reviews Analyzed &bull; ⏱️ 8-Week Window
              </p>
            </td>
          </tr>

          <!-- Main Content -->
          <tr>
            <td style="padding: 24px 28px;">
              
              <!-- Executive Summary -->
              <div style="background-color: #f0fdf9; border-left: 4px solid #00d09c; border-radius: 0 8px 8px 0; padding: 14px 18px; margin-bottom: 24px;">
                <div style="font-size: 11px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.8px; color: #008765; margin-bottom: 6px;">⚡ Executive Summary</div>
                <p style="margin: 0; font-size: 14px; line-height: 1.55; color: #134e4a; font-weight: 500;">{pulse.executive_summary}</p>
              </div>

              <!-- Top 3 User Themes -->
              <div style="font-size: 13px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.6px; color: #0f172a; margin-top: 20px; margin-bottom: 12px; border-bottom: 2px solid #f1f5f9; padding-bottom: 6px;">
                🔥 Top 3 User Themes
              </div>
              {theme_cards}

              <!-- Authentic Quotes -->
              <div style="font-size: 13px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.6px; color: #0f172a; margin-top: 24px; margin-bottom: 12px; border-bottom: 2px solid #f1f5f9; padding-bottom: 6px;">
                💬 Authentic User Quotes (100% Verbatim)
              </div>
              {quotes_boxes}

              <!-- Action Ideas -->
              <div style="font-size: 13px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.6px; color: #0f172a; margin-top: 24px; margin-bottom: 12px; border-bottom: 2px solid #f1f5f9; padding-bottom: 6px;">
                🎯 3 Prioritized Action Ideas
              </div>
              {action_items}

              {cta_btn}

            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding: 16px 28px; font-size: 11px; color: #94a3b8; background-color: #f8fafc; border-top: 1px solid #e2e8f0; text-align: center;">
              Generated automatically by Groww Review Pulse AI Agent &bull; Max 250 words total &bull; Zero PII
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

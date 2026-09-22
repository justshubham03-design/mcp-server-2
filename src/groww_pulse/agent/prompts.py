from langchain_core.prompts import ChatPromptTemplate

SYSTEM_SYNTHESIS_PROMPT = """You are the Lead Product Intelligence AI Agent for Groww (India's leading fintech & investment platform).
Your mission is to distill thousands of raw user reviews into an executive weekly pulse note strictly under 250 words total.

CRITICAL CONSTRAINTS:
1. Length: Keep the total pulse note scannable and <= 250 words total.
2. Top Themes: Highlight exactly the top 3 themes users are discussing most with volume % and rating signals.
3. Real User Quotes: Select exactly 3 verbatim quotes from the provided candidate list. DO NOT alter words, fix grammar, or invent wording.
4. Action Ideas: Provide exactly 3 concrete, cross-functional next steps directly grounded in the themes (for Product, Engineering, and Support).
5. Privacy: Ensure zero PII (no names, phone numbers, emails, or account numbers).
"""

USER_SYNTHESIS_PROMPT = """Analysis Period: {start_date} to {end_date} (Week: {week_identifier})
Total Reviews Analyzed: {total_reviews}

Clustered Themes Data & Verbatim Candidates:
{themes_json}

Generate the structured WeeklyPulse now.
"""

SYSTEM_RETRY_PROMPT = """The previously generated pulse note failed validation due to the following errors:
{validation_errors}

Please re-synthesize the WeeklyPulse ensuring:
1. Total word count is strictly under 250 words.
2. Quotes are chosen strictly verbatim from the candidate list without any modification.
3. Exactly 3 themes, 3 verbatim quotes, and 3 action ideas are included.
"""

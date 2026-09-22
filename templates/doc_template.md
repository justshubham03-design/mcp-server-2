# Groww Weekly Review Pulse ({{ week_identifier }})

**Analysis Period**: {{ analysis_period_start }} to {{ analysis_period_end }}  
**Total Play Store Reviews Analyzed**: {{ total_reviews_analyzed }} | **Word Count**: {{ word_count }} / 250 words max

---

## 1. Executive Summary
{{ executive_summary }}

---

## 2. Top 3 User Themes

| Rank | Theme | Volume & Rating Signal | Core Sentiment & User Takeaway |
| :---: | :--- | :--- | :--- |
{% for theme in top_themes %}
| **#{{ theme.rank }}** | **{{ theme.name }}** | {{ theme.metric }} | {{ theme.summary }} |
{% endfor %}

---

## 3. Real User Quotes (Verbatim Snippets)
> [!NOTE]
> All quotes below are authentic, unedited verbatim snippets extracted directly from public Google Play Store reviews. All reviewer PII has been scrubbed.

{% for quote in verbatim_quotes %}
- *"{{ quote }}"*
{% endfor %}

---

## 4. Prioritized Action Ideas

{% for action in action_ideas %}
1. **{{ action }}**
{% endfor %}

---
*Generated automatically by Groww Review Pulse AI Agent.*

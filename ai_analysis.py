import os
import io
import json
import pdfplumber
import anthropic
from dotenv import load_dotenv

load_dotenv()

_client = None


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set. Add it to your .env file.")
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def extract_text_from_pdf(source) -> str:
    """source: file path string, raw bytes, or BytesIO object."""
    if isinstance(source, bytes):
        source = io.BytesIO(source)
    text_parts = []
    with pdfplumber.open(source) as pdf:
        for page in pdf.pages[:60]:
            t = page.extract_text()
            if t:
                text_parts.append(t)
    return "\n\n".join(text_parts)


LONG_TERM_ANALYSIS_PROMPT = """You are an expert equity analyst specializing in long-term fundamental investing in Indian stock markets.

A long-term investor has uploaded a financial document (annual report or quarterly result) for **{company} ({symbol})**.
Document type: {doc_type}
Period: {period}

Below is the extracted text from the document:

---
{text}
---

Provide a comprehensive analysis structured EXACTLY as follows (use these exact headers):

## 1. BUSINESS OVERVIEW
Summarize what the company does, its core business model, revenue streams, and competitive position.

## 2. KEY FINANCIAL METRICS
Extract and present ALL available metrics as a JSON block:
```json
{{
  "revenue": null,
  "revenue_growth_yoy": null,
  "net_profit": null,
  "net_profit_margin": null,
  "ebitda": null,
  "ebitda_margin": null,
  "eps": null,
  "roe": null,
  "roce": null,
  "debt_to_equity": null,
  "interest_coverage": null,
  "current_ratio": null,
  "operating_cashflow": null,
  "free_cashflow": null,
  "capex": null,
  "promoter_holding": null,
  "promoter_pledge": null,
  "book_value_per_share": null,
  "dividend_per_share": null,
  "working_capital_days": null
}}
```
Fill null with actual values where found. Add units (Cr, %, etc.).

## 3. FINANCIAL HEALTH ASSESSMENT
Rate each dimension (Excellent/Good/Fair/Poor) with brief reasoning:
- **Revenue Growth:**
- **Profitability:**
- **Balance Sheet Strength:**
- **Cash Flow Quality:**
- **Capital Efficiency (ROE/ROCE):**
- **Debt Situation:**

## 4. LONG-TERM STRENGTHS (MOAT ANALYSIS)
List 4-6 specific competitive advantages or moat factors this company possesses.

## 5. KEY RISKS FOR LONG-TERM INVESTORS
List 4-6 specific risks with their potential impact (High/Medium/Low).

## 6. MANAGEMENT QUALITY SIGNALS
What does this report reveal about management quality? Look for:
- Capital allocation decisions
- Guidance vs actual performance
- Related party transactions
- Promoter actions
- Communication clarity

## 7. GROWTH PROSPECTS (3-5 YEAR VIEW)
Specific growth drivers, addressable market expansion, new products/geographies, capacity additions.

## 8. RED FLAGS
Any concerning items: rising debt, promoter pledging, governance issues, margin compression trends, auditor remarks.

## 9. LONG-TERM INVESTOR VERDICT
**Overall Rating:** [Strong Buy / Accumulate / Hold / Reduce / Avoid]
**Confidence:** [High / Medium / Low]
**Investment Horizon:** [Suitable for X year horizon]
**Summary:** 3-4 sentence verdict from a long-term value investor's perspective.
**Key Monitorables:** What to watch in the next 2-4 quarters.
"""


def analyze_document(filepath: str, symbol: str, company: str, doc_type: str, period: str) -> tuple[str, str]:
    text = extract_text_from_pdf(filepath)

    if len(text) < 100:
        return "Could not extract meaningful text from this PDF.", "{}"

    # Truncate to ~100k chars to stay within context limits
    if len(text) > 100_000:
        text = text[:100_000] + "\n\n[... document truncated for analysis ...]"

    prompt = LONG_TERM_ANALYSIS_PROMPT.format(
        company=company,
        symbol=symbol,
        doc_type=doc_type,
        period=period,
        text=text,
    )

    client = get_client()
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    analysis = message.content[0].text
    key_metrics = _extract_metrics_json(analysis)
    return analysis, key_metrics


def _extract_metrics_json(analysis_text: str) -> str:
    import re
    match = re.search(r"```json\s*(\{.*?\})\s*```", analysis_text, re.DOTALL)
    if match:
        return match.group(1)
    return "{}"


COMPARE_PROMPT = """You are a long-term equity analyst. Compare the financial performance of **{company} ({symbol})** across multiple periods using the analyses below.

{analyses}

Provide:

## TREND ANALYSIS
For each key metric, describe the trend (Improving / Stable / Deteriorating) with numbers.

## BUSINESS MOMENTUM
Is the business getting stronger or weaker? What changed?

## TURNING POINTS
Any significant inflection points — positive or negative?

## LONG-TERM TRAJECTORY
Based on the trend, where is this business heading in 3-5 years?

## UPDATED VERDICT
Given all available data, should a long-term investor: **Accumulate / Hold / Reduce**? Why?
"""


def compare_documents(symbol: str, company: str, analyses: list[dict]) -> str:
    if not analyses:
        return "No analyses available to compare."

    analyses_text = ""
    for a in analyses:
        analyses_text += f"\n\n### {a['doc_type']} — {a['period']}\n{a['analysis'][:3000]}\n"

    prompt = COMPARE_PROMPT.format(
        company=company,
        symbol=symbol,
        analyses=analyses_text,
    )

    client = get_client()
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


QUICK_QA_PROMPT = """You are an expert on Indian stock markets and long-term investing.

Context about {symbol} — {company}:
{context}

User question: {question}

Answer concisely and specifically from a long-term investor's perspective. If the answer isn't in the context, say so but still provide relevant general guidance."""


def ask_about_stock(symbol: str, company: str, context: str, question: str) -> str:
    prompt = QUICK_QA_PROMPT.format(
        symbol=symbol,
        company=company,
        context=context[:8000],
        question=question,
    )
    client = get_client()
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text

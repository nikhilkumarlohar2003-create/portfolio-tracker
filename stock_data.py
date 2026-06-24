import yfinance as yf
import pandas as pd
import feedparser
import requests
from datetime import datetime, timedelta


NSE_SUFFIX = ".NS"
BSE_SUFFIX = ".BO"


def nse_symbol(symbol: str) -> str:
    s = symbol.upper().strip()
    if not s.endswith(".NS") and not s.endswith(".BO"):
        return s + NSE_SUFFIX
    return s


def get_stock_info(symbol: str) -> dict:
    ticker = yf.Ticker(nse_symbol(symbol))
    try:
        info = ticker.info
        return {
            "symbol": symbol.upper(),
            "company_name": info.get("longName", symbol),
            "current_price": info.get("currentPrice") or info.get("regularMarketPrice", 0),
            "previous_close": info.get("previousClose", 0),
            "day_high": info.get("dayHigh", 0),
            "day_low": info.get("dayLow", 0),
            "week_52_high": info.get("fiftyTwoWeekHigh", 0),
            "week_52_low": info.get("fiftyTwoWeekLow", 0),
            "market_cap": info.get("marketCap", 0),
            "pe_ratio": info.get("trailingPE", 0),
            "pb_ratio": info.get("priceToBook", 0),
            "roe": info.get("returnOnEquity", 0),
            "debt_to_equity": info.get("debtToEquity", 0),
            "dividend_yield": info.get("dividendYield", 0),
            "eps": info.get("trailingEps", 0),
            "book_value": info.get("bookValue", 0),
            "sector": info.get("sector", ""),
            "industry": info.get("industry", ""),
            "volume": info.get("volume", 0),
            "avg_volume": info.get("averageVolume", 0),
            "free_cashflow": info.get("freeCashflow", 0),
            "operating_cashflow": info.get("operatingCashflow", 0),
            "revenue_growth": info.get("revenueGrowth", 0),
            "earnings_growth": info.get("earningsGrowth", 0),
            "gross_margins": info.get("grossMargins", 0),
            "operating_margins": info.get("operatingMargins", 0),
            "profit_margins": info.get("profitMargins", 0),
            "beta": info.get("beta", 0),
        }
    except Exception as e:
        return {"symbol": symbol.upper(), "current_price": 0, "error": str(e)}


def get_price_history(symbol: str, period: str = "5y") -> pd.DataFrame:
    ticker = yf.Ticker(nse_symbol(symbol))
    df = ticker.history(period=period)
    return df


def get_financials(symbol: str) -> dict:
    ticker = yf.Ticker(nse_symbol(symbol))
    result = {}
    try:
        result["income_stmt"] = ticker.financials
        result["balance_sheet"] = ticker.balance_sheet
        result["cashflow"] = ticker.cashflow
        result["quarterly_income"] = ticker.quarterly_financials
        result["quarterly_balance"] = ticker.quarterly_balance_sheet
    except Exception:
        pass
    return result


def get_dividends(symbol: str) -> pd.Series:
    ticker = yf.Ticker(nse_symbol(symbol))
    return ticker.dividends


def get_multiple_prices(symbols: list) -> dict:
    results = {}
    for sym in symbols:
        try:
            info = get_stock_info(sym)
            results[sym.upper()] = info
        except Exception as e:
            results[sym.upper()] = {"current_price": 0, "error": str(e)}
    return results


NEWS_FEEDS = [
    "https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms",
    "https://www.moneycontrol.com/rss/business.xml",
    "https://feeds.feedburner.com/ndtvprofit-latest",
]


def get_market_news(max_items: int = 30) -> list:
    news = []
    for feed_url in NEWS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:10]:
                news.append({
                    "title": entry.get("title", ""),
                    "link": entry.get("link", ""),
                    "published": entry.get("published", ""),
                    "summary": entry.get("summary", "")[:300],
                    "source": feed.feed.get("title", feed_url),
                })
        except Exception:
            continue
    return news[:max_items]


def get_stock_news(symbol: str) -> list:
    ticker = yf.Ticker(nse_symbol(symbol))
    try:
        raw = ticker.news
        news = []
        for item in raw:
            content = item.get("content", [{}])
            if isinstance(content, list) and content:
                c = content[0]
            else:
                c = {}
            news.append({
                "title": c.get("title") or item.get("title", ""),
                "link": c.get("canonicalUrl", {}).get("url", "") or item.get("link", ""),
                "published": c.get("pubDate", ""),
                "summary": c.get("summary", "")[:300],
                "source": c.get("provider", {}).get("displayName", "Yahoo Finance"),
            })
        return news
    except Exception:
        return []


def check_alerts(holdings: list, alerts: list) -> list:
    triggered = []
    symbols = list({h["symbol"] for h in holdings})
    prices = get_multiple_prices(symbols)

    for alert in alerts:
        sym = alert["symbol"]
        current = prices.get(sym, {}).get("current_price", 0)
        if not current:
            continue
        if alert["alert_type"] == "above" and current >= alert["target_price"]:
            triggered.append({**alert, "current_price": current})
        elif alert["alert_type"] == "below" and current <= alert["target_price"]:
            triggered.append({**alert, "current_price": current})
    return triggered

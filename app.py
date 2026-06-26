import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import yfinance as yf
import os
import json
from datetime import datetime, date, timedelta

import database as db
import stock_data as sd
import ai_analysis as ai
import theme

# ── page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Portfolio Tracker",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

theme.inject()
db.init_db()

UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)

# ── sidebar nav ──────────────────────────────────────────────────────────────
st.sidebar.markdown(
    f"""<div style="padding:10px 0 18px">
    <div style="font-size:18px;font-weight:600;color:{theme.TEXT_PRI};letter-spacing:-0.3px">
        Portfolio Tracker
    </div>
    <div style="font-size:11px;color:{theme.ACCENT_TEAL};margin-top:3px;font-weight:500">
        NSE · BSE · Long-Term
    </div>
    </div>""",
    unsafe_allow_html=True,
)
st.sidebar.markdown(
    f'<div style="height:1px;background:{theme.BORDER};margin-bottom:12px"></div>',
    unsafe_allow_html=True,
)

page = st.sidebar.radio(
    "Navigate",
    ["Dashboard", "Portfolio", "Watchlist", "Notifications & Alerts", "Document Analysis", "Market News"],
    index=0,
)

st.sidebar.markdown(
    f'<div style="height:1px;background:{theme.BORDER};margin:12px 0 8px"></div>',
    unsafe_allow_html=True,
)
st.sidebar.markdown(
    f'<div style="font-size:10px;color:{theme.TEXT_MUTED};padding:0 4px">'
    f'Powered by Claude AI · yfinance</div>',
    unsafe_allow_html=True,
)

# ── helpers ──────────────────────────────────────────────────────────────────

def get_anthropic_key() -> str:
    """Return Anthropic API key from env or st.secrets (cloud)."""
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key:
        try:
            key = str(st.secrets.get("ANTHROPIC_API_KEY", "")).strip()
        except Exception:
            pass
    return key


@st.cache_data(ttl=300)
def fetch_prices(symbols: tuple) -> dict:
    return sd.get_multiple_prices(list(symbols))


def fmt_inr(val) -> str:
    if not val:
        return "—"
    val = float(val)
    if abs(val) >= 1e7:
        return f"₹{val/1e7:.2f} Cr"
    if abs(val) >= 1e5:
        return f"₹{val/1e5:.2f} L"
    return f"₹{val:,.2f}"


def delta_badge(val: float) -> str:
    arrow = "▲" if val >= 0 else "▼"
    color = "green" if val >= 0 else "red"
    return f'<span style="color:{color}; font-weight:600">{arrow} {abs(val):.2f}%</span>'


def style_pnl(val):
    return "color: green" if val > 0 else ("color: red" if val < 0 else "")


def calculate_xirr(cashflows_list):
    """
    cashflows_list: list of (date_str, amount)
    negative = money you paid out (buy), positive = money you'd receive (current value)
    Returns annualised return as float (e.g. 0.18 = 18%)
    """
    if not cashflows_list or len(cashflows_list) < 2:
        return None
    parsed = []
    for cf_date, amount in cashflows_list:
        if isinstance(cf_date, str):
            d = datetime.strptime(cf_date, "%Y-%m-%d").date()
        elif isinstance(cf_date, datetime):
            d = cf_date.date()
        else:
            d = cf_date
        parsed.append((d, float(amount)))

    min_date = min(p[0] for p in parsed)
    years = [(p[0] - min_date).days / 365.25 for p in parsed]
    amounts = [p[1] for p in parsed]

    def npv(rate):
        if rate <= -1:
            return float("inf")
        return sum(cf / (1 + rate) ** t for cf, t in zip(amounts, years))

    lo, hi = -0.9999, 50.0
    try:
        if npv(lo) * npv(hi) > 0:
            return None
        for _ in range(300):
            mid = (lo + hi) / 2
            v = npv(mid)
            if abs(v) < 0.01 or (hi - lo) < 0.00001:
                return mid
            if npv(lo) * v < 0:
                hi = mid
            else:
                lo = mid
        return (lo + hi) / 2
    except Exception:
        return None


@st.cache_data(ttl=3600)
def get_benchmark_data(transactions_tuple):
    """
    Money-weighted portfolio vs Nifty 50.
    Each lot enters portfolio on its actual buy date.
    Nifty benchmark: same rupees invested in Nifty on same dates.
    Returns DataFrame with Portfolio (₹), Nifty_Equiv (₹), Invested (₹).
    transactions_tuple: ((symbol, qty, date_str, price), ...)
    """
    txns = sorted(transactions_tuple, key=lambda x: x[2])
    if not txns:
        return None

    start_date = txns[0][2]
    symbols = list({t[0] for t in txns})
    yf_symbols = [sd.nse_symbol(s) for s in symbols] + ["^NSEI"]

    try:
        raw = yf.download(yf_symbols, start=start_date, auto_adjust=True, progress=False)
        if raw.empty:
            return None
        close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw
        close = close.ffill().bfill()

        # Cumulative shares per stock over time
        shares_df = pd.DataFrame(0.0, index=close.index, columns=symbols)
        nifty_units = pd.Series(0.0, index=close.index)
        invested_s  = pd.Series(0.0, index=close.index)

        for sym, qty, date_str, price in txns:
            txn_dt = pd.to_datetime(date_str)
            valid = close.index[close.index >= txn_dt]
            if valid.empty:
                continue
            entry = valid[0]
            shares_df.loc[entry:, sym] += float(qty)
            cost = float(price) * float(qty)
            if cost > 0 and "^NSEI" in close.columns:
                nifty_px = float(close.loc[entry, "^NSEI"])
                if nifty_px > 0:
                    nifty_units.loc[entry:] += cost / nifty_px
            invested_s.loc[entry:] += cost

        # Portfolio market value
        port_val = pd.Series(0.0, index=close.index)
        for sym in symbols:
            col = sd.nse_symbol(sym)
            if col in close.columns:
                port_val += shares_df[sym] * close[col]

        nifty_equiv = nifty_units * close["^NSEI"] if "^NSEI" in close.columns else port_val * 0

        mask = invested_s > 0
        df = pd.DataFrame({
            "Portfolio":   port_val[mask],
            "Nifty_Equiv": nifty_equiv[mask],
            "Invested":    invested_s[mask],
        }).dropna()
        return df if not df.empty else None
    except Exception:
        return None


@st.cache_data(ttl=3600)
def get_portfolio_beta(holdings_tuple):
    """Weighted portfolio beta vs Nifty 50."""
    holdings = list(holdings_tuple)
    yf_symbols = [sd.nse_symbol(h[0]) for h in holdings] + ["^NSEI"]
    try:
        raw = yf.download(yf_symbols, period="1y", auto_adjust=True, progress=False)
        if raw.empty:
            return None
        close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw
        rets = close.pct_change().dropna()
        if "^NSEI" not in rets.columns:
            return None
        nifty_var = rets["^NSEI"].var()
        if nifty_var == 0:
            return None
        total_val = sum(h[1] * h[2] for h in holdings)
        beta_sum = 0.0
        for sym, qty, curr_price in holdings:
            col = sd.nse_symbol(sym)
            if col not in rets.columns:
                continue
            weight = (qty * curr_price) / total_val if total_val else 0
            beta = rets[col].cov(rets["^NSEI"]) / nifty_var
            beta_sum += weight * beta
        return round(beta_sum, 2)
    except Exception:
        return None


@st.cache_data(ttl=3600)
def fetch_all_corporate_events(symbols_tuple: tuple) -> dict:
    """Fetch corporate events for all holdings. Returns {symbol: event_dict}."""
    result = {}
    for sym in symbols_tuple:
        result[sym] = sd.get_corporate_events(sym)
    return result


@st.cache_data(ttl=3600)
def get_dividend_income(lots_tuple):
    """
    Accurate per-lot dividend calc.
    lots_tuple: ((symbol, qty, buy_date_str), ...)  — one entry per transaction lot.
    Returns dict {symbol: total_dividend_income}.
    """
    # group lots by symbol
    by_sym: dict = {}
    for sym, qty, date_str in lots_tuple:
        by_sym.setdefault(sym, []).append((qty, date_str))

    result = {}
    for sym, lots in by_sym.items():
        try:
            divs = sd.get_dividends(sym)
            if divs.empty:
                result[sym] = 0.0
                continue
            idx = pd.to_datetime(divs.index)
            divs.index = idx.tz_convert(None) if idx.tz is not None else idx
            total = 0.0
            for qty, date_str in lots:
                buy_dt = pd.to_datetime(date_str)
                total += float(divs[divs.index >= buy_dt].sum()) * qty
            result[sym] = round(total, 2)
        except Exception:
            result[sym] = 0.0
    return result


@st.cache_data(ttl=600)
def get_holdings_news(symbols_tuple):
    """Fetch latest news for all holdings combined."""
    news = []
    for sym in symbols_tuple:
        try:
            articles = sd.get_stock_news(sym)
            for a in articles[:3]:
                a["stock"] = sym
                news.append(a)
        except Exception:
            continue
    return news[:40]


# ═══════════════════════════════════════════════════════════════════════════
# PAGE: DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════
if page == "Dashboard":
    st.markdown(
        f'<h1 style="margin-bottom:2px">Portfolio Dashboard</h1>'
        f'<div style="font-size:12px;color:{theme.TEXT_MUTED};margin-bottom:1rem">'
        f'Live prices · NSE/BSE · Updated every 5 min</div>',
        unsafe_allow_html=True,
    )

    holdings = db.get_holdings()
    if not holdings:
        st.info("No holdings yet. Go to **Portfolio** to add your stocks.")
        st.stop()

    symbols = tuple(sorted({h["symbol"] for h in holdings}))
    with st.spinner("Fetching live prices…"):
        prices = fetch_prices(symbols)

    # ── build base rows ───────────────────────────────────────────────────
    rows = []
    total_invested = 0.0
    total_current = 0.0

    for h in holdings:
        sym = h["symbol"]
        info = prices.get(sym, {})
        curr_price = info.get("current_price", 0) or 0
        prev_close = info.get("previous_close", 0) or 0
        w52_high = info.get("week_52_high", 0) or 0
        w52_low = info.get("week_52_low", 0) or 0
        invested = h["quantity"] * h["avg_buy_price"]
        current_val = h["quantity"] * curr_price
        pnl = current_val - invested
        pnl_pct = (pnl / invested * 100) if invested else 0
        day_chg = ((curr_price - prev_close) / prev_close * 100) if prev_close else 0
        w52_pos = ((curr_price - w52_low) / (w52_high - w52_low) * 100) if (w52_high - w52_low) > 0 else 0

        # holding period
        buy_date_str = h.get("buy_date", "")
        try:
            buy_dt = datetime.strptime(buy_date_str, "%Y-%m-%d").date()
            holding_days = (date.today() - buy_dt).days
            if holding_days >= 365:
                holding_str = f"{holding_days // 365}y {(holding_days % 365) // 30}m"
            else:
                holding_str = f"{holding_days // 30}m {holding_days % 30}d"
        except Exception:
            holding_days = 0
            holding_str = "—"

        total_invested += invested
        total_current += current_val

        rows.append({
            "Symbol": sym,
            "Company": info.get("company_name", h.get("company_name", sym)),
            "Sector": h.get("sector", ""),
            "Qty": h["quantity"],
            "Avg Cost": h["avg_buy_price"],
            "LTP": curr_price,
            "Invested": invested,
            "Current Value": current_val,
            "P&L": pnl,
            "P&L %": pnl_pct,
            "Day Change %": day_chg,
            "52W Position %": w52_pos,
            "52W High": w52_high,
            "52W Low": w52_low,
            "Holding Period": holding_str,
            "_holding_days": holding_days,
            "_buy_date": buy_date_str,
        })

    total_pnl = total_current - total_invested
    total_pnl_pct = (total_pnl / total_invested * 100) if total_invested else 0
    df = pd.DataFrame(rows)

    # ── XIRR ─────────────────────────────────────────────────────────────
    transactions = db.get_transactions()
    cashflows = []
    for t in transactions:
        if t["action"] == "BUY":
            cashflows.append((t["date"], -(t["quantity"] * t["price"])))
        elif t["action"] == "SELL":
            cashflows.append((t["date"], t["quantity"] * t["price"]))
    cashflows.append((str(date.today()), total_current))
    xirr_val = calculate_xirr(cashflows)

    # ── portfolio beta ────────────────────────────────────────────────────
    beta_input = tuple((r["Symbol"], r["Qty"], r["LTP"]) for r in rows if r["LTP"] > 0)
    beta = get_portfolio_beta(beta_input) if beta_input else None

    # ── nifty return for comparison ───────────────────────────────────────
    earliest_date = "2024-01-01"
    try:
        dates_list = [r["_buy_date"] for r in rows if r["_buy_date"] and r["_buy_date"] != "2024-01-01"]
        if dates_list:
            earliest_date = min(dates_list)
    except Exception:
        pass

    # ════════════════════════════════════════════════════════
    # SECTION 1: KPI CARDS
    # ════════════════════════════════════════════════════════
    pnl_positive = total_pnl >= 0
    theme.kpi_row([
        {"label": "Total Invested",  "value": fmt_inr(total_invested)},
        {"label": "Current Value",   "value": fmt_inr(total_current)},
        {"label": "Total P&L",       "value": fmt_inr(total_pnl),
         "delta": f"{abs(total_pnl_pct):.2f}%", "positive": pnl_positive},
        {"label": "Holdings",        "value": str(len(holdings))},
        {"label": "XIRR (annualised)", "value": f"{xirr_val*100:.1f}%" if xirr_val else "—",
         "delta": None, "help": "Your actual annualised return calculated from transactions"},
        {"label": "Portfolio Beta",  "value": f"{beta:.2f}" if beta else "—",
         "help": "Beta vs Nifty 50. <1 = less volatile, >1 = more volatile"},
    ])

    st.markdown("---")

    # ════════════════════════════════════════════════════════
    # SECTION 2: HEALTH ALERTS
    # ════════════════════════════════════════════════════════
    alerts_html = []

    # sector concentration
    sector_alloc = df.groupby("Sector")["Current Value"].sum()
    for sec, val in sector_alloc.items():
        if sec and total_current > 0 and val / total_current > 0.30:
            pct = val / total_current * 100
            alerts_html.append(f"⚠️ **Sector concentration:** {sec} is {pct:.1f}% of portfolio (>30%)")

    # big losers
    for r in rows:
        if r["P&L %"] < -20:
            alerts_html.append(f"🔴 **{r['Symbol']}** is down {r['P&L %']:.1f}% from your buy price")

    # near 52W low
    for r in rows:
        if 0 < r["52W Position %"] < 10:
            alerts_html.append(f"📉 **{r['Symbol']}** is near its 52-week low ({r['52W Position %']:.0f}% above low)")

    # near 52W high
    for r in rows:
        if r["52W Position %"] > 90:
            alerts_html.append(f"📈 **{r['Symbol']}** is near its 52-week high ({r['52W Position %']:.0f}% up from low)")

    if alerts_html:
        with st.container():
            st.markdown("**Portfolio Alerts**")
            for a in alerts_html:
                st.warning(a)
        st.markdown("---")

    # ════════════════════════════════════════════════════════
    # SECTION 3: HOLDINGS TABLE + HEATMAP
    # ════════════════════════════════════════════════════════
    col_l, col_r = st.columns([3, 2])

    with col_l:
        theme.section_header("Holdings", f"{len(holdings)} stocks · ₹{total_current/1e5:.2f}L current")

        # add position weight
        df["Weight %"] = (df["Current Value"] / total_current * 100).round(1)

        display_cols = ["Symbol", "Qty", "Avg Cost", "LTP", "Current Value",
                        "P&L", "P&L %", "Day Change %", "Weight %", "Holding Period"]
        styled = (
            df[display_cols].style
            .format({
                "Avg Cost": "₹{:.2f}",
                "LTP": "₹{:.2f}",
                "Current Value": "₹{:,.0f}",
                "P&L": "₹{:,.0f}",
                "P&L %": "{:+.2f}%",
                "Day Change %": "{:+.2f}%",
                "Weight %": "{:.1f}%",
            })
            .map(style_pnl, subset=["P&L", "P&L %", "Day Change %"])
        )
        st.dataframe(styled, use_container_width=True, hide_index=True)

    with col_r:
        theme.section_header("P&L Heatmap", "size = portfolio weight")
        treemap_df = df[df["Current Value"] > 0].copy()
        treemap_df["label"] = treemap_df["Symbol"] + "<br>" + treemap_df["P&L %"].map(lambda x: f"{x:+.1f}%")
        fig_tree = px.treemap(
            treemap_df,
            path=["Symbol"],
            values="Current Value",
            color="P&L %",
            color_continuous_scale=["#d62728", "#f7f7f7", "#2ca02c"],
            color_continuous_midpoint=0,
            custom_data=["P&L %", "LTP"],
        )
        fig_tree.update_traces(
            texttemplate="<b>%{label}</b><br>%{customdata[0]:+.1f}%",
            hovertemplate="<b>%{label}</b><br>Value: ₹%{value:,.0f}<br>P&L: %{color:+.2f}%<extra></extra>"
        )
        fig_tree.update_layout(**{**theme.PLOTLY_LAYOUT,
                               "margin": dict(t=0, b=0, l=0, r=0), "height": 380,
                               "coloraxis_colorbar": dict(title="P&L %", thickness=10,
                                   tickfont=dict(color=theme.TEXT_SEC))})
        st.plotly_chart(fig_tree, use_container_width=True)

    st.markdown("---")

    # ════════════════════════════════════════════════════════
    # SECTION 4: SECTOR PIE + BEST/WORST + PROFIT/LOSS SPLIT
    # ════════════════════════════════════════════════════════
    c1, c2, c3 = st.columns([1.15, 1.15, 0.7])

    _SECTOR_COLORS = ["#00d2b4","#3b82f6","#f0a500","#f05252","#a855f7",
                      "#10c98f","#64748b","#e879f9","#fb923c","#34d399",
                      "#60a5fa","#fbbf24","#f87171","#818cf8","#4ade80"]

    with c1:
        theme.section_header("Sector Allocation")
        sec_df = df.groupby("Sector")["Current Value"].sum().reset_index()
        sec_df = sec_df[sec_df["Sector"] != ""].sort_values("Current Value", ascending=False).reset_index(drop=True)
        if not sec_df.empty:
            total_sec = sec_df["Current Value"].sum()
            sec_df["Pct"] = sec_df["Current Value"] / total_sec * 100

            fig_sec = px.pie(sec_df, names="Sector", values="Current Value", hole=0.5,
                             color_discrete_sequence=_SECTOR_COLORS)
            fig_sec.update_traces(
                textinfo="percent",
                textfont_size=11,
                textfont_color=theme.TEXT_PRI,
                hovertemplate="<b>%{label}</b><br>₹%{value:,.0f}<br>%{percent}<extra></extra>",
            )
            fig_sec.update_layout(**{**theme.PLOTLY_LAYOUT,
                                   "margin": dict(t=10, b=8, l=0, r=0),
                                   "height": 230,
                                   "showlegend": False})
            st.plotly_chart(fig_sec, use_container_width=True)

            # compact two-column legend below chart
            legend_items = []
            for i, row in sec_df.iterrows():
                color = _SECTOR_COLORS[i % len(_SECTOR_COLORS)]
                legend_items.append(
                    f'<div style="display:flex;align-items:center;gap:5px;min-width:140px">'
                    f'<div style="width:7px;height:7px;border-radius:50%;background:{color};flex-shrink:0"></div>'
                    f'<span style="font-size:10px;color:{theme.TEXT_SEC};white-space:nowrap">'
                    f'{row["Sector"]} '
                    f'<span style="color:{theme.TEXT_MUTED}">{row["Pct"]:.1f}%</span></span>'
                    f'</div>'
                )
            legend_html = (
                '<div style="display:flex;flex-wrap:wrap;gap:5px 0px;margin-top:2px">'
                + "".join(legend_items)
                + '</div>'
            )
            st.markdown(legend_html, unsafe_allow_html=True)
        else:
            st.caption("Add sectors when entering holdings to see this chart.")

    with c2:
        theme.section_header("Performance")

        # Best performers
        best = df.nlargest(5, "P&L %")[["Symbol", "P&L %", "P&L"]].reset_index(drop=True)
        rows_html = '<div style="display:flex;flex-direction:column;gap:4px">'
        for i, r in best.iterrows():
            rows_html += (
                f'<div style="display:flex;align-items:center;justify-content:space-between;'
                f'padding:7px 10px;background:{theme.BG_CARD};border-radius:8px;'
                f'border-left:3px solid {theme.GREEN}">'
                f'<div style="display:flex;align-items:center;gap:8px">'
                f'<span style="font-size:10px;font-weight:600;color:{theme.TEXT_MUTED};width:13px">{i+1}</span>'
                f'<span style="font-size:13px;font-weight:600;color:{theme.TEXT_PRI}">{r["Symbol"]}</span>'
                f'</div>'
                f'<div style="text-align:right">'
                f'<div style="font-size:13px;font-weight:600;color:{theme.GREEN}">▲ {abs(r["P&L %"]):.2f}%</div>'
                f'<div style="font-size:10px;color:{theme.TEXT_MUTED}">+{fmt_inr(r["P&L"])}</div>'
                f'</div></div>'
            )
        rows_html += '</div>'
        st.markdown(rows_html, unsafe_allow_html=True)

        st.markdown(
            f'<div style="font-size:10px;font-weight:600;color:{theme.TEXT_MUTED};'
            f'text-transform:uppercase;letter-spacing:0.08em;margin:10px 0 5px">Worst Performers</div>',
            unsafe_allow_html=True)

        worst = df.nsmallest(5, "P&L %")[["Symbol", "P&L %", "P&L"]].reset_index(drop=True)
        rows_html2 = '<div style="display:flex;flex-direction:column;gap:4px">'
        for i, r in worst.iterrows():
            rows_html2 += (
                f'<div style="display:flex;align-items:center;justify-content:space-between;'
                f'padding:7px 10px;background:{theme.BG_CARD};border-radius:8px;'
                f'border-left:3px solid {theme.RED}">'
                f'<div style="display:flex;align-items:center;gap:8px">'
                f'<span style="font-size:10px;font-weight:600;color:{theme.TEXT_MUTED};width:13px">{i+1}</span>'
                f'<span style="font-size:13px;font-weight:600;color:{theme.TEXT_PRI}">{r["Symbol"]}</span>'
                f'</div>'
                f'<div style="text-align:right">'
                f'<div style="font-size:13px;font-weight:600;color:{theme.RED}">▼ {abs(r["P&L %"]):.2f}%</div>'
                f'<div style="font-size:10px;color:{theme.TEXT_MUTED}">{fmt_inr(r["P&L"])}</div>'
                f'</div></div>'
            )
        rows_html2 += '</div>'
        st.markdown(rows_html2, unsafe_allow_html=True)

    with c3:
        theme.section_header("Profit / Loss")
        in_profit = len(df[df["P&L"] > 0])
        in_loss = len(df[df["P&L"] < 0])
        breakeven = len(df[df["P&L"] == 0])
        fig_pl = go.Figure(go.Pie(
            labels=["Profit", "Loss", "Even"],
            values=[max(in_profit, 0.001), max(in_loss, 0.001), max(breakeven, 0.001)],
            hole=0.62,
            marker_colors=[theme.GREEN, theme.RED, theme.TEXT_MUTED],
        ))
        fig_pl.add_annotation(
            text=f"<b>{in_profit}/{len(df)}</b><br><span style='font-size:10px'>profit</span>",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=13, color=theme.GREEN),
        )
        fig_pl.update_layout(**{**theme.PLOTLY_LAYOUT,
                               "margin": dict(t=10, b=0, l=0, r=0),
                               "height": 200,
                               "showlegend": True,
                               "legend": dict(
                                   orientation="h",
                                   yanchor="bottom", y=-0.18,
                                   xanchor="center", x=0.5,
                                   font=dict(size=10, color=theme.TEXT_SEC),
                               )})
        st.plotly_chart(fig_pl, use_container_width=True)

        theme.section_header("Today's Movers")
        today_sorted = df.sort_values("Day Change %", ascending=False)
        gainers = today_sorted.head(3)
        losers = today_sorted.tail(3).iloc[::-1]

        movers_html = '<div style="display:flex;flex-direction:column;gap:4px">'
        for _, r in gainers.iterrows():
            c = theme.GREEN if r["Day Change %"] >= 0 else theme.RED
            a = "▲" if r["Day Change %"] >= 0 else "▼"
            movers_html += (
                f'<div style="display:flex;justify-content:space-between;align-items:center;'
                f'padding:5px 8px;background:{theme.BG_CARD};border-radius:6px">'
                f'<span style="font-size:12px;font-weight:600;color:{theme.TEXT_PRI}">{r["Symbol"]}</span>'
                f'<span style="font-size:12px;font-weight:600;color:{c}">{a} {abs(r["Day Change %"]):.2f}%</span>'
                f'</div>'
            )
        movers_html += f'<div style="height:1px;background:{theme.BORDER};margin:2px 0"></div>'
        for _, r in losers.iterrows():
            c = theme.GREEN if r["Day Change %"] >= 0 else theme.RED
            a = "▲" if r["Day Change %"] >= 0 else "▼"
            movers_html += (
                f'<div style="display:flex;justify-content:space-between;align-items:center;'
                f'padding:5px 8px;background:{theme.BG_CARD};border-radius:6px">'
                f'<span style="font-size:12px;font-weight:600;color:{theme.TEXT_PRI}">{r["Symbol"]}</span>'
                f'<span style="font-size:12px;font-weight:600;color:{c}">{a} {abs(r["Day Change %"]):.2f}%</span>'
                f'</div>'
            )
        movers_html += '</div>'
        st.markdown(movers_html, unsafe_allow_html=True)

    st.markdown("---")

    # ════════════════════════════════════════════════════════
    # SECTION 5: 52-WEEK POSITION
    # ════════════════════════════════════════════════════════
    theme.section_header("52-Week Position", "0% = at 52W low · 100% = at 52W high")

    w52_df = df[df["52W High"] > 0].sort_values("52W Position %")
    if not w52_df.empty:
        colors = ["#d62728" if v < 30 else ("#f0a500" if v < 60 else "#2ca02c")
                  for v in w52_df["52W Position %"]]
        fig_52 = go.Figure(go.Bar(
            y=w52_df["Symbol"],
            x=w52_df["52W Position %"],
            orientation="h",
            marker_color=colors,
            text=w52_df["52W Position %"].map(lambda x: f"{x:.0f}%"),
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>Position: %{x:.1f}%<br>52W Low: ₹%{customdata[0]:,.2f}<br>52W High: ₹%{customdata[1]:,.2f}<extra></extra>",
            customdata=w52_df[["52W Low", "52W High"]].values,
        ))
        fig_52.add_vline(x=30, line_dash="dot", line_color=theme.RED, opacity=0.4)
        fig_52.add_vline(x=70, line_dash="dot", line_color=theme.GREEN, opacity=0.4)
        fig_52.update_layout(**{**theme.PLOTLY_LAYOUT,
            "xaxis": dict(range=[0, 115], title="% of 52W range",
                          gridcolor=theme.BORDER, tickfont=dict(color=theme.TEXT_SEC)),
            "yaxis": dict(gridcolor="rgba(0,0,0,0)", tickfont=dict(color=theme.TEXT_PRI)),
            "height": max(300, len(w52_df) * 28),
            "margin": dict(t=10, b=30, l=10, r=10),
        })
        st.plotly_chart(fig_52, use_container_width=True)

    st.markdown("---")

    # ════════════════════════════════════════════════════════
    # SECTION 6: PORTFOLIO vs NIFTY 50
    # ════════════════════════════════════════════════════════
    theme.section_header("Portfolio vs Nifty 50",
                         "money-weighted · same capital deployed in Nifty on same dates")

    # build per-lot tuples: (symbol, qty, date, price)
    _bench_txns = db.get_transactions()
    _bench_lots = tuple(
        (t["symbol"], t["quantity"], t["date"], t["price"])
        for t in _bench_txns if t["action"] in ("BUY",) and float(t["price"] or 0) > 0
    )
    with st.spinner("Loading benchmark chart (cached for 1 hour)…"):
        bench_df = get_benchmark_data(_bench_lots) if _bench_lots else None

    if bench_df is not None and not bench_df.empty:
        last       = bench_df.iloc[-1]
        invested_f = last["Invested"]
        port_ret   = (last["Portfolio"]   - invested_f) / invested_f * 100
        nifty_ret  = (last["Nifty_Equiv"] - invested_f) / invested_f * 100
        alpha      = port_ret - nifty_ret

        b1, b2, b3, b4 = st.columns(4)
        b1.metric("Portfolio Value",  fmt_inr(last["Portfolio"]))
        b2.metric("Total Invested",   fmt_inr(invested_f))
        b3.metric("Portfolio Return", f"{port_ret:+.1f}%")
        b4.metric("Alpha vs Nifty",   f"{alpha:+.1f}%")

        fig_bench = go.Figure()
        # Invested capital baseline
        fig_bench.add_trace(go.Scatter(
            x=bench_df.index, y=bench_df["Invested"],
            name="Invested Capital", line=dict(color=theme.AMBER, width=1.5, dash="dot"),
        ))
        # Nifty equivalent
        fig_bench.add_trace(go.Scatter(
            x=bench_df.index, y=bench_df["Nifty_Equiv"],
            name="Nifty 50 (same capital)", line=dict(color=theme.TEXT_MUTED, width=1.8, dash="dash"),
        ))
        # Portfolio
        fig_bench.add_trace(go.Scatter(
            x=bench_df.index, y=bench_df["Portfolio"],
            name="My Portfolio", line=dict(color=theme.ACCENT_TEAL, width=2.5),
            fill="tonexty",
            fillcolor="rgba(0,210,180,0.06)",
        ))
        fig_bench.update_layout(**{**theme.PLOTLY_LAYOUT,
            "height": 380,
            "margin": dict(t=10, b=10),
            "yaxis_title": "Value (₹)",
            "yaxis": dict(tickformat=",.0f", gridcolor=theme.BORDER,
                          tickfont=dict(color=theme.TEXT_SEC)),
            "legend": dict(orientation="h", y=1.08, bgcolor="rgba(0,0,0,0)"),
            "hovermode": "x unified",
        })
        st.plotly_chart(fig_bench, use_container_width=True)
        st.caption(
            f"Nifty return on same capital: {nifty_ret:+.1f}%  ·  "
            f"Your alpha: {alpha:+.1f}%  ·  "
            f"Nifty value if invested same way: {fmt_inr(last['Nifty_Equiv'])}"
        )
    else:
        st.info("Could not load benchmark data. Check internet connection.")

    st.markdown("---")

    # ════════════════════════════════════════════════════════
    # SECTION 7: DIVIDEND INCOME
    # ════════════════════════════════════════════════════════
    theme.section_header("Dividend Income", "per lot since purchase date · from yfinance")

    # build per-lot tuples from transactions table for accurate dividend calc
    _all_txns = db.get_transactions()
    _buy_lots = [(t["symbol"], t["quantity"], t["date"])
                 for t in _all_txns if t["action"] in ("BUY", "BONUS")]
    div_input = tuple(_buy_lots) if _buy_lots else tuple(
        (r["Symbol"], r["Qty"], r["_buy_date"]) for r in rows)
    with st.spinner("Calculating dividends…"):
        div_data = get_dividend_income(div_input)

    total_div = sum(div_data.values())
    d1, d2 = st.columns([1, 3])
    d1.metric("Total Dividend Income", fmt_inr(total_div))

    div_df = pd.DataFrame([
        {"Symbol": sym, "Dividend Income": amt}
        for sym, amt in div_data.items() if amt > 0
    ]).sort_values("Dividend Income", ascending=False)

    if not div_df.empty:
        fig_div = px.bar(div_df, x="Symbol", y="Dividend Income",
                         text="Dividend Income",
                         color_discrete_sequence=[theme.ACCENT_TEAL])
        fig_div.update_traces(texttemplate="₹%{text:,.0f}", textposition="outside",
                              marker_color=theme.ACCENT_TEAL, opacity=0.85)
        fig_div.update_layout(**{**theme.PLOTLY_LAYOUT,
                               "height": 280, "margin": dict(t=10, b=10),
                               "showlegend": False})
        d2.plotly_chart(fig_div, use_container_width=True)
    else:
        d2.info("No dividend data found for your holdings.")

    st.markdown("---")

    # ════════════════════════════════════════════════════════
    # SECTION 8: HOLDINGS NEWS FEED
    # ════════════════════════════════════════════════════════
    theme.section_header("Latest News", "for your holdings")
    with st.spinner("Fetching news…"):
        news_items = get_holdings_news(symbols)

    if news_items:
        for item in news_items[:20]:
            st.markdown(
                f'<div style="background:{theme.BG_CARD};border:1px solid {theme.BORDER};'
                f'border-radius:8px;padding:12px 16px;margin-bottom:8px">'
                f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">'
                f'{theme.badge(item["stock"], "teal")}'
                f'<span style="font-size:12px;color:{theme.TEXT_MUTED}">'
                f'{item.get("source","")} · {item.get("published","")[:16]}</span>'
                f'</div>'
                f'<div style="font-size:13px;font-weight:500;color:{theme.TEXT_PRI};margin-bottom:4px">'
                f'{item["title"]}</div>'
                + (f'<a href="{item["link"]}" style="font-size:11px;color:{theme.ACCENT_TEAL};'
                   f'text-decoration:none">Read more →</a>' if item.get("link") else "")
                + f'</div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("No news found.")


# ═══════════════════════════════════════════════════════════════════════════
# PAGE: PORTFOLIO
# ═══════════════════════════════════════════════════════════════════════════
elif page == "Portfolio":
    st.title("Portfolio Management")

    tab1, tab2, tab3, tab4 = st.tabs(["Holdings", "Add / Edit", "Transaction History", "Company Deep Dive"])

    with tab1:
        holdings = db.get_holdings()
        if not holdings:
            st.info("No holdings yet. Use **Add / Edit** tab to add stocks.")
        else:
            for h in holdings:
                with st.expander(f"**{h['symbol']}** — {h.get('company_name', '')}"):
                    c1, c2, c3 = st.columns(3)
                    c1.write(f"**Quantity:** {h['quantity']}")
                    c2.write(f"**Avg Buy Price:** ₹{h['avg_buy_price']:.2f}")
                    c3.write(f"**Buy Date:** {h.get('buy_date', '—')}")
                    if h.get("notes"):
                        st.caption(f"Notes: {h['notes']}")

                    col_btn1, col_btn2 = st.columns([1, 5])
                    if col_btn2.button("Delete", key=f"del_{h['id']}"):
                        db.delete_holding(h["id"])
                        st.rerun()

                    if st.button("View Price Chart", key=f"chart_{h['id']}"):
                        with st.spinner("Loading chart…"):
                            hist = sd.get_price_history(h["symbol"], period="5y")
                            if not hist.empty:
                                fig = go.Figure()
                                fig.add_trace(go.Scatter(
                                    x=hist.index, y=hist["Close"], name="Close",
                                    line=dict(color=theme.ACCENT_TEAL, width=2),
                                    fill="tozeroy", fillcolor="rgba(0,210,180,0.06)"
                                ))
                                fig.add_hline(y=h["avg_buy_price"], line_dash="dot",
                                              annotation_text="Avg Cost",
                                              line_color=theme.AMBER)
                                fig.update_layout(**{**theme.PLOTLY_LAYOUT,
                                    "title": dict(text=f"{h['symbol']} — 5Y Price History",
                                                  font=dict(color=theme.TEXT_PRI, size=13)),
                                    "height": 350, "margin": dict(t=30, b=0)})
                                st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.subheader("Add New Holding")
        with st.form("add_holding_form"):
            c1, c2 = st.columns(2)
            symbol = c1.text_input("NSE Symbol (e.g. RELIANCE, TCS)").upper()
            company_name = c2.text_input("Company Name")
            c3, c4, c5 = st.columns(3)
            quantity = c3.number_input("Quantity", min_value=0.01, step=1.0)
            avg_price = c4.number_input("Avg Buy Price (₹)", min_value=0.01, step=0.5)
            buy_date = c5.date_input("Buy Date", value=date.today())
            c6, c7 = st.columns(2)
            sector = c6.text_input("Sector (optional)")
            notes = c7.text_area("Notes (optional)", height=68)
            submitted = st.form_submit_button("Add Holding")
            if submitted and symbol and quantity and avg_price:
                db.add_holding(symbol, company_name, quantity, avg_price, str(buy_date), sector, notes)
                db.add_transaction(symbol, "BUY", quantity, avg_price, str(buy_date), notes)
                st.success(f"Added {symbol} to portfolio.")
                st.rerun()

        st.subheader("Log Transaction")
        with st.form("add_txn_form"):
            c1, c2, c3 = st.columns(3)
            t_symbol = c1.text_input("Symbol").upper()
            t_action = c2.selectbox("Action", ["BUY", "SELL"])
            t_date = c3.date_input("Date", value=date.today())
            c4, c5 = st.columns(2)
            t_qty = c4.number_input("Quantity", min_value=0.01, step=1.0)
            t_price = c5.number_input("Price (₹)", min_value=0.01, step=0.5)
            t_notes = st.text_input("Notes")
            if st.form_submit_button("Log Transaction") and t_symbol:
                db.add_transaction(t_symbol, t_action, t_qty, t_price, str(t_date), t_notes)
                st.success("Transaction logged.")

    with tab3:
        txns = db.get_transactions()
        if txns:
            df = pd.DataFrame(txns)[["date", "symbol", "action", "quantity", "price", "notes"]]
            df.columns = ["Date", "Symbol", "Action", "Qty", "Price", "Notes"]
            df["Value"] = df["Qty"] * df["Price"]
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No transactions logged yet.")


    # ── tab4: Company Deep Dive ──────────────────────────────────────────────
    with tab4:
        holdings_dd = db.get_holdings()
        if not holdings_dd:
            st.info("Add holdings first.")
        else:
            sym_map = {
                f"{h['symbol']} — {h.get('company_name', '')}": h
                for h in holdings_dd
            }
            selected_label = st.selectbox(
                "Select a company",
                list(sym_map.keys()),
                label_visibility="collapsed",
            )
            h = sym_map[selected_label]
            sel_sym   = h["symbol"]
            sel_name  = h.get("company_name", sel_sym)
            sel_qty   = float(h["quantity"])
            sel_avg   = float(h["avg_buy_price"])
            sel_date  = h.get("buy_date", "")

            # ── live price ───────────────────────────────────────────────
            with st.spinner("Fetching price…"):
                price_info = sd.get_stock_info(sel_sym)
            cmp   = float(price_info.get("current_price") or 0)
            pnl   = (cmp - sel_avg) * sel_qty
            pnl_p = ((cmp - sel_avg) / sel_avg * 100) if sel_avg else 0

            # holding period
            try:
                hdays = (datetime.now() - datetime.strptime(sel_date, "%Y-%m-%d")).days
                hold_str = f"{hdays // 365}y {(hdays % 365) // 30}m" if hdays >= 365 else f"{hdays // 30}m {hdays % 30}d"
            except Exception:
                hold_str = "—"

            # XIRR for this stock
            sym_txns = db.get_transactions(symbol=sel_sym)
            cf = []
            for t in sym_txns:
                if t["action"] in ("BUY", "BONUS"):
                    cf.append((t["date"], -float(t["price"] or 0) * float(t["quantity"])))
                elif t["action"] == "SELL":
                    cf.append((t["date"], float(t["price"] or 0) * float(t["quantity"])))
            if cmp and sel_qty:
                cf.append((str(date.today()), cmp * sel_qty))
            xirr_val = calculate_xirr(cf)

            # ── investment stats row ──────────────────────────────────────
            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
            pnl_color  = theme.GREEN if pnl >= 0 else theme.RED
            pnl_arrow  = "▲" if pnl >= 0 else "▼"
            stats_html = (
                f'<div style="display:flex;flex-wrap:wrap;gap:10px;margin-bottom:14px">'
            )
            for label, val in [
                ("QUANTITY",    f"{int(sel_qty)} shares"),
                ("AVG COST",    f"₹{sel_avg:,.2f}"),
                ("CMP",         f"₹{cmp:,.2f}"),
                ("INVESTED",    f"₹{sel_avg * sel_qty:,.0f}"),
                ("CURRENT VAL", f"₹{cmp * sel_qty:,.0f}"),
                ("P&L",         f"{pnl_arrow} ₹{abs(pnl):,.0f} ({abs(pnl_p):.1f}%)"),
                ("XIRR",        f"{xirr_val * 100:.1f}%" if xirr_val else "—"),
                ("HELD FOR",    hold_str),
            ]:
                color = pnl_color if label == "P&L" else theme.TEXT_PRI
                stats_html += (
                    f'<div style="background:{theme.BG_CARD};border:1px solid {theme.BORDER};'
                    f'border-radius:10px;padding:10px 16px;min-width:110px">'
                    f'<div style="font-size:9px;font-weight:600;color:{theme.TEXT_MUTED};'
                    f'text-transform:uppercase;letter-spacing:0.1em;margin-bottom:4px">{label}</div>'
                    f'<div style="font-size:14px;font-weight:600;color:{color}">{val}</div>'
                    f'</div>'
                )
            stats_html += '</div>'
            st.markdown(stats_html, unsafe_allow_html=True)

            # ── important dates ────────────────────────────────────────────
            theme.section_header("Upcoming Important Dates")
            with st.spinner("Fetching corporate events…"):
                ev = sd.get_corporate_events(sel_sym)
            q_dates = sd.get_estimated_results_dates()

            date_events = []
            today_dt = datetime.now()
            for key, label, ev_type in [
                ("ex_dividend_date", "Ex-Dividend Date", "dividend"),
                ("dividend_date",    "Dividend Payment", "dividend"),
                ("earnings_date",    "Earnings / Results", "results"),
            ]:
                if ev.get(key):
                    try:
                        dt   = datetime.strptime(ev[key][:10], "%Y-%m-%d")
                        days = (dt - today_dt).days
                        detail = f"₹{ev['last_dividend']:.2f}/share" if key == "ex_dividend_date" and ev.get("last_dividend") else ""
                        date_events.append({"date": ev[key][:10], "label": label,
                                            "detail": detail, "days": days, "type": ev_type})
                    except Exception:
                        pass
            for q in q_dates:
                date_events.append({"date": q["deadline"], "label": f"{q['quarter']} Results Deadline",
                                    "detail": f"SEBI · {q['period']}", "days": q["days_away"], "type": "results_est"})

            if date_events:
                TYPE_C = {"dividend": theme.ACCENT_TEAL, "results": theme.ACCENT_BLUE, "results_est": theme.AMBER}
                dates_html = '<div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:8px">'
                for de in sorted(date_events, key=lambda x: x["date"]):
                    c = TYPE_C.get(de["type"], theme.TEXT_MUTED)
                    urg = theme.RED if 0 <= de["days"] <= 14 else (theme.AMBER if de["days"] <= 45 else theme.TEXT_MUTED)
                    dates_html += (
                        f'<div style="background:{theme.BG_CARD};border:1px solid {c}40;'
                        f'border-radius:10px;padding:10px 14px;min-width:170px">'
                        f'<div style="font-size:9px;font-weight:700;color:{c};text-transform:uppercase;'
                        f'letter-spacing:0.08em;margin-bottom:4px">{de["label"]}</div>'
                        f'<div style="font-size:14px;font-weight:600;color:{theme.TEXT_PRI}">{de["date"]}</div>'
                        f'<div style="font-size:11px;color:{urg};margin-top:2px">'
                        f'{"in " + str(de["days"]) + " days" if de["days"] >= 0 else str(abs(de["days"])) + "d ago"}'
                        f'{" · " + de["detail"] if de["detail"] else ""}</div>'
                        f'</div>'
                    )
                dates_html += '</div>'
                st.markdown(dates_html, unsafe_allow_html=True)
            else:
                st.caption("No upcoming corporate event data available.")

            # ── research documents ─────────────────────────────────────────
            theme.section_header("Research Documents",
                                 f"uploaded for {sel_sym}")
            company_docs = db.get_documents(symbol=sel_sym)
            real_docs    = [d for d in company_docs if d["doc_type"] != "AI Company Synthesis"]
            synthesis_rec = next((d for d in company_docs if d["doc_type"] == "AI Company Synthesis"), None)

            if real_docs:
                for doc in real_docs:
                    period       = f"{doc.get('year', '')} {doc.get('quarter') or ''}".strip()
                    has_analysis = bool(doc.get("analysis"))
                    d_col1, d_col2, d_col3 = st.columns([5, 1, 1])
                    with d_col1:
                        status_color = theme.GREEN if has_analysis else theme.AMBER
                        status_text  = "✓ Analysed" if has_analysis else "⚠ Not analysed"
                        st.markdown(
                            f'<div style="padding:9px 14px;background:{theme.BG_CARD};border-radius:8px;'
                            f'border-left:3px solid {theme.ACCENT_BLUE}">'
                            f'<span style="font-size:13px;font-weight:600;color:{theme.TEXT_PRI}">📄 {doc["filename"]}</span>'
                            f'<span style="font-size:11px;color:{theme.TEXT_MUTED};margin-left:10px">'
                            f'{doc["doc_type"]} · {period}</span>'
                            f'<span style="font-size:10px;color:{status_color};margin-left:10px">{status_text}</span>'
                            f'</div>',
                            unsafe_allow_html=True,
                        )
                    with d_col2:
                        if has_analysis:
                            if st.button("View", key=f"view_doc_{doc['id']}"):
                                st.session_state[f"show_doc_{doc['id']}"] = \
                                    not st.session_state.get(f"show_doc_{doc['id']}", False)
                    with d_col3:
                        if st.button("Delete", key=f"del_doc_{doc['id']}"):
                            db.delete_document(doc["id"])
                            st.rerun()

                    if st.session_state.get(f"show_doc_{doc['id']}", False) and has_analysis:
                        with st.expander(f"Analysis — {doc['doc_type']} {period}", expanded=True):
                            st.markdown(doc["analysis"])
            else:
                st.info(f"No documents uploaded for {sel_sym} yet. Upload via Document Analysis tab.")

            # inline upload shortcut
            with st.expander("+ Upload a new document for this company"):
                with st.form(f"quick_upload_{sel_sym}"):
                    uc1, uc2 = st.columns(2)
                    u_type    = uc1.selectbox("Document Type", ["Annual Report", "Quarterly Result (Q1)",
                                              "Quarterly Result (Q2)", "Quarterly Result (Q3)",
                                              "Quarterly Result (Q4)", "Concall Transcript",
                                              "Investor Presentation"])
                    u_year    = uc2.number_input("Year", min_value=2000, max_value=2030,
                                                 value=datetime.now().year)
                    u_quarter = st.selectbox("Quarter", ["—", "Q1", "Q2", "Q3", "Q4"])
                    u_pdf     = st.file_uploader("PDF file", type=["pdf"],
                                                 key=f"pdf_upload_{sel_sym}")
                    u_submit  = st.form_submit_button("Upload & Analyse")

                if u_submit:
                    if not u_pdf:
                        st.error("Please select a PDF file before clicking Upload.")
                    else:
                        try:
                            import database as _db_mod
                            safe_name   = f"{sel_sym}_{u_type.replace(' ','_').replace('(','').replace(')','').replace('/','_')}_{u_year}.pdf"
                            pdf_bytes   = u_pdf.getvalue()   # getvalue() works even after read()
                            quarter_val = None if u_quarter == "—" else u_quarter
                            filepath    = safe_name if _db_mod._USE_CLOUD else os.path.join(UPLOADS_DIR, safe_name)

                            if not _db_mod._USE_CLOUD:
                                with open(filepath, "wb") as f:
                                    f.write(pdf_bytes)

                            # save record first
                            db.save_document(sel_sym, u_type, safe_name, filepath, u_year, quarter_val)
                            st.info("Document saved. Running AI analysis…")

                            api_key = get_anthropic_key()
                            if not api_key:
                                st.error("ANTHROPIC_API_KEY not found in secrets. Add it in Streamlit → Manage app → Secrets.")
                            else:
                                with st.spinner("Claude is analysing the document (may take 30–60 seconds)…"):
                                    analysis_text, metrics = ai.analyze_document(
                                        pdf_bytes,
                                        sel_sym, sel_name, u_type,
                                        f"{u_year} {quarter_val or ''}".strip()
                                    )
                                # find the freshly saved record and attach analysis
                                for nd in db.get_documents(symbol=sel_sym):
                                    if nd["filename"] == safe_name and not nd.get("analysis"):
                                        db.update_document_analysis(nd["id"], analysis_text, metrics)
                                        break
                                st.success("Document uploaded and analysed successfully!")
                                st.rerun()
                        except Exception as e:
                            st.error(f"Error during upload/analysis: {e}")

            # ── AI company synthesis ───────────────────────────────────────
            theme.section_header("AI Company Synthesis",
                                 f"{len(real_docs)} document(s) · personalised to your position")

            api_key = get_anthropic_key()
            analysed_docs = [d for d in real_docs if d.get("analysis")]

            if synthesis_rec and synthesis_rec.get("analysis"):
                st.markdown(synthesis_rec["analysis"])
                st.caption(f"Last generated: {synthesis_rec.get('year', '')} · click Refresh to update")
                if st.button("🔄 Refresh Analysis", key=f"refresh_synth_{sel_sym}"):
                    if not analysed_docs:
                        st.warning("Analyse at least one document first.")
                    elif not api_key:
                        st.warning("ANTHROPIC_API_KEY not set.")
                    else:
                        analyses_in = [{"doc_type": d["doc_type"],
                                        "period": f"{d.get('year','')} {d.get('quarter') or ''}".strip(),
                                        "analysis": d["analysis"]} for d in analysed_docs]
                        with st.spinner("Generating synthesis…"):
                            synth = ai.synthesize_company(
                                sel_sym, sel_name, sel_qty, sel_avg, cmp,
                                hold_str, analyses_in
                            )
                        db.update_document_analysis(synthesis_rec["id"], synth, "{}")
                        st.success("Synthesis updated.")
                        st.rerun()

            elif analysed_docs:
                st.info(f"You have {len(analysed_docs)} analysed document(s). Click below to generate a full synthesis.")
                if st.button("Generate AI Synthesis", key=f"gen_synth_{sel_sym}",
                             type="primary"):
                    if not api_key:
                        st.error("ANTHROPIC_API_KEY not set.")
                    else:
                        analyses_in = [{"doc_type": d["doc_type"],
                                        "period": f"{d.get('year','')} {d.get('quarter') or ''}".strip(),
                                        "analysis": d["analysis"]} for d in analysed_docs]
                        with st.spinner("Claude is synthesising all documents for this company…"):
                            synth = ai.synthesize_company(
                                sel_sym, sel_name, sel_qty, sel_avg, cmp,
                                hold_str, analyses_in
                            )
                        db.save_document(sel_sym, "AI Company Synthesis",
                                         f"{sel_sym}_synthesis.txt", "", datetime.now().year, None)
                        fresh_docs = db.get_documents(symbol=sel_sym)
                        new_rec = next((d for d in fresh_docs
                                        if d["doc_type"] == "AI Company Synthesis"
                                        and not d.get("analysis")), None)
                        if new_rec:
                            db.update_document_analysis(new_rec["id"], synth, "{}")
                        st.success("Synthesis generated.")
                        st.rerun()
            else:
                st.info("Upload and analyse at least one document (annual report or quarterly result) to get an AI synthesis.")


# ═══════════════════════════════════════════════════════════════════════════
# PAGE: WATCHLIST
# ═══════════════════════════════════════════════════════════════════════════
elif page == "Watchlist":
    st.title("Watchlist")

    with st.form("add_watch"):
        c1, c2, c3 = st.columns([2, 3, 1])
        w_sym = c1.text_input("NSE Symbol").upper()
        w_name = c2.text_input("Company Name")
        if c3.form_submit_button("Add") and w_sym:
            db.add_watchlist(w_sym, w_name)
            st.rerun()

    watchlist = db.get_watchlist()
    if not watchlist:
        st.info("Your watchlist is empty.")
    else:
        symbols = tuple({w["symbol"] for w in watchlist})
        with st.spinner("Fetching prices…"):
            prices = fetch_prices(symbols)

        rows = []
        for w in watchlist:
            info = prices.get(w["symbol"], {})
            curr = info.get("current_price", 0) or 0
            prev = info.get("previous_close", 0) or 0
            chg = ((curr - prev) / prev * 100) if prev else 0
            rows.append({
                "Symbol": w["symbol"],
                "Company": info.get("company_name", w.get("company_name", "")),
                "LTP": curr,
                "Day %": chg,
                "P/E": info.get("pe_ratio", 0),
                "P/B": info.get("pb_ratio", 0),
                "ROE %": (info.get("roe", 0) or 0) * 100,
                "Div Yield %": (info.get("dividend_yield", 0) or 0) * 100,
                "52W High": info.get("week_52_high", 0),
                "52W Low": info.get("week_52_low", 0),
                "_id": w["id"],
            })

        df = pd.DataFrame(rows)
        display_df = df.drop(columns=["_id"])
        styled = (
            display_df.style
            .format({
                "LTP": "₹{:.2f}",
                "Day %": "{:+.2f}%",
                "P/E": "{:.1f}",
                "P/B": "{:.2f}",
                "ROE %": "{:.1f}%",
                "Div Yield %": "{:.2f}%",
                "52W High": "₹{:.2f}",
                "52W Low": "₹{:.2f}",
            })
            .map(lambda v: "color: green" if v > 0 else "color: red", subset=["Day %"])
        )
        st.dataframe(styled, use_container_width=True, hide_index=True)

        st.markdown("---")
        remove_sym = st.selectbox("Remove from watchlist", [""] + [w["symbol"] for w in watchlist])
        if st.button("Remove") and remove_sym:
            db.remove_watchlist(remove_sym)
            st.rerun()


# ═══════════════════════════════════════════════════════════════════════════
# PAGE: NOTIFICATIONS & ALERTS
# ═══════════════════════════════════════════════════════════════════════════
elif page == "Notifications & Alerts":
    st.title("Notifications & Price Alerts")

    holdings = db.get_holdings()
    all_symbols = sorted({h["symbol"] for h in holdings})

    active_alerts = db.get_alerts(triggered=False)
    if active_alerts and holdings:
        with st.spinner("Checking alerts…"):
            triggered = sd.check_alerts(holdings, active_alerts)
        if triggered:
            st.error(f"🚨 {len(triggered)} alert(s) triggered!")
            for t in triggered:
                direction = "risen above" if t["alert_type"] == "above" else "fallen below"
                st.warning(
                    f"**{t['symbol']}** has {direction} your target of ₹{t['target_price']:.2f}  "
                    f"| Current: ₹{t['current_price']:.2f}"
                )
                if st.button(f"Dismiss alert #{t['id']}", key=f"dismiss_{t['id']}"):
                    db.trigger_alert(t["id"])
                    st.rerun()

    tab1, tab2, tab3, tab4 = st.tabs(["Set Alert", "Active Alerts", "Stock News", "Important Dates"])

    with tab1:
        st.subheader("Set Price Alert")
        with st.form("alert_form"):
            c1, c2, c3 = st.columns(3)
            a_sym = c1.selectbox("Stock", [""] + all_symbols) if all_symbols else c1.text_input("Symbol").upper()
            a_type = c2.selectbox("Alert when price goes", ["above", "below"])
            a_price = c3.number_input("Target Price (₹)", min_value=0.01, step=0.5)
            if st.form_submit_button("Set Alert") and a_sym and a_price:
                db.add_alert(str(a_sym), a_type, a_price)
                st.success(f"Alert set: {a_sym} {a_type} ₹{a_price:.2f}")
                st.rerun()

    with tab2:
        alerts = db.get_alerts(triggered=False)
        if not alerts:
            st.info("No active alerts.")
        else:
            for al in alerts:
                c1, c2 = st.columns([4, 1])
                c1.write(f"**{al['symbol']}** — price goes **{al['alert_type']}** ₹{al['target_price']:.2f}")
                if c2.button("Delete", key=f"del_alert_{al['id']}"):
                    db.delete_alert(al["id"])
                    st.rerun()

        st.markdown("---")
        st.subheader("Triggered Alerts (History)")
        triggered_hist = db.get_alerts(triggered=True)
        if triggered_hist:
            df = pd.DataFrame(triggered_hist)[["symbol", "alert_type", "target_price", "created_at"]]
            df.columns = ["Symbol", "Type", "Target ₹", "Set On"]
            st.dataframe(df, use_container_width=True, hide_index=True)

    with tab3:
        st.subheader("Stock-Specific News")
        if all_symbols:
            news_sym = st.selectbox("Select stock", all_symbols)
            if st.button("Load News"):
                with st.spinner("Fetching news…"):
                    articles = sd.get_stock_news(news_sym)
                if articles:
                    for a in articles[:15]:
                        st.markdown(f"**{a['title']}**  \n{a['summary']}  \n_{a['source']} · {a['published']}_")
                        if a.get("link"):
                            st.markdown(f"[Read more]({a['link']})")
                        st.markdown("---")
                else:
                    st.info("No news found for this stock.")
        else:
            st.info("Add holdings first to see stock news.")

    with tab4:
        theme.section_header("Important Corporate Dates", "dividends · quarterly results · for your holdings")

        if not all_symbols:
            st.info("Add holdings to see corporate events.")
        else:
            today_dt = datetime.now()

            with st.spinner("Fetching corporate events for all holdings…"):
                events_raw = fetch_all_corporate_events(tuple(all_symbols))

            # ── build unified event list ─────────────────────────────────────
            all_events = []

            for sym, ev in events_raw.items():
                # Ex-dividend date
                if ev.get("ex_dividend_date"):
                    try:
                        dt = datetime.strptime(ev["ex_dividend_date"], "%Y-%m-%d")
                        days = (dt - today_dt).days
                        all_events.append({
                            "date": ev["ex_dividend_date"],
                            "symbol": sym,
                            "event": "Ex-Dividend",
                            "detail": f"₹{ev['last_dividend']:.2f}/share" if ev["last_dividend"] else "—",
                            "days_away": days,
                            "type": "dividend",
                        })
                    except Exception:
                        pass

                # Dividend payment date
                if ev.get("dividend_date"):
                    try:
                        dt = datetime.strptime(ev["dividend_date"], "%Y-%m-%d")
                        days = (dt - today_dt).days
                        all_events.append({
                            "date": ev["dividend_date"],
                            "symbol": sym,
                            "event": "Dividend Payment",
                            "detail": f"₹{ev['annual_dividend']:.2f} annual" if ev["annual_dividend"] else "—",
                            "days_away": days,
                            "type": "dividend",
                        })
                    except Exception:
                        pass

                # Earnings/Results date from yfinance
                if ev.get("earnings_date"):
                    try:
                        dt = datetime.strptime(ev["earnings_date"][:10], "%Y-%m-%d")
                        days = (dt - today_dt).days
                        all_events.append({
                            "date": ev["earnings_date"][:10],
                            "symbol": sym,
                            "event": "Earnings / Results",
                            "detail": "Source: yfinance",
                            "days_away": days,
                            "type": "results",
                        })
                    except Exception:
                        pass

            # ── add estimated quarterly results deadlines ────────────────────
            q_dates = sd.get_estimated_results_dates(today_dt)
            for q in q_dates:
                for sym in all_symbols:
                    # only add if yfinance didn't already give an earnings date for this stock
                    already_has = any(
                        e["symbol"] == sym and e["type"] == "results"
                        for e in all_events
                    )
                    if not already_has:
                        all_events.append({
                            "date": q["deadline"],
                            "symbol": sym,
                            "event": f"{q['quarter']} Results Deadline",
                            "detail": f"SEBI deadline · {q['period']}",
                            "days_away": q["days_away"],
                            "type": "results_est",
                        })

            if not all_events:
                st.info("No upcoming corporate events found. Data may not be available for all stocks.")
            else:
                # Sort by date
                all_events.sort(key=lambda x: x["date"])

                # ── summary chips ────────────────────────────────────────────
                soon = [e for e in all_events if 0 <= e["days_away"] <= 30 and e["type"] == "dividend"]
                if soon:
                    chip_html = '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px">'
                    for e in soon:
                        chip_html += (
                            f'<div style="background:{theme.ACCENT_TEAL}18;border:1px solid {theme.ACCENT_TEAL}40;'
                            f'border-radius:20px;padding:4px 12px;font-size:12px;color:{theme.ACCENT_TEAL}">'
                            f'<b>{e["symbol"]}</b> {e["event"]} in {e["days_away"]}d</div>'
                        )
                    chip_html += '</div>'
                    st.markdown(chip_html, unsafe_allow_html=True)

                # ── filter ────────────────────────────────────────────────────
                f1, f2 = st.columns([2, 1])
                filter_type = f1.radio(
                    "Show", ["All", "Dividends Only", "Results Only"],
                    horizontal=True, label_visibility="collapsed"
                )
                filter_sym = f2.selectbox("Stock", ["All stocks"] + all_symbols,
                                          label_visibility="collapsed")

                filtered = all_events
                if filter_type == "Dividends Only":
                    filtered = [e for e in all_events if e["type"] == "dividend"]
                elif filter_type == "Results Only":
                    filtered = [e for e in all_events if e["type"] in ("results", "results_est")]
                if filter_sym != "All stocks":
                    filtered = [e for e in filtered if e["symbol"] == filter_sym]

                # ── event cards ───────────────────────────────────────────────
                TYPE_COLOR = {
                    "dividend":    theme.ACCENT_TEAL,
                    "results":     theme.ACCENT_BLUE,
                    "results_est": theme.AMBER,
                }
                TYPE_LABEL = {
                    "dividend":    "DIVIDEND",
                    "results":     "RESULTS",
                    "results_est": "EST.",
                }

                for e in filtered:
                    days = e["days_away"]
                    if days < 0:
                        urgency_color = theme.TEXT_MUTED
                        urgency_label = f"{abs(days)}d ago"
                    elif days == 0:
                        urgency_color = theme.RED
                        urgency_label = "TODAY"
                    elif days <= 7:
                        urgency_color = theme.RED
                        urgency_label = f"in {days}d"
                    elif days <= 30:
                        urgency_color = theme.AMBER
                        urgency_label = f"in {days}d"
                    else:
                        urgency_color = theme.TEXT_MUTED
                        urgency_label = f"in {days}d"

                    t_color = TYPE_COLOR.get(e["type"], theme.TEXT_MUTED)
                    t_label = TYPE_LABEL.get(e["type"], "")

                    card = (
                        f'<div style="display:flex;align-items:center;gap:12px;'
                        f'padding:10px 14px;background:{theme.BG_CARD};border-radius:10px;'
                        f'border-left:3px solid {t_color};margin-bottom:5px">'
                        # date
                        f'<div style="min-width:90px">'
                        f'<div style="font-size:13px;font-weight:600;color:{theme.TEXT_PRI}">{e["date"]}</div>'
                        f'<div style="font-size:10px;color:{urgency_color};font-weight:600">{urgency_label}</div>'
                        f'</div>'
                        # type badge
                        f'<div style="background:{t_color}20;color:{t_color};font-size:9px;font-weight:700;'
                        f'padding:2px 7px;border-radius:4px;letter-spacing:0.06em;min-width:55px;text-align:center">'
                        f'{t_label}</div>'
                        # symbol + event
                        f'<div style="flex:1">'
                        f'<span style="font-size:13px;font-weight:700;color:{theme.TEXT_PRI}">{e["symbol"]}</span>'
                        f'&nbsp;&nbsp;<span style="font-size:12px;color:{theme.TEXT_SEC}">{e["event"]}</span>'
                        f'</div>'
                        # detail
                        f'<div style="font-size:12px;color:{theme.TEXT_MUTED};text-align:right">{e["detail"]}</div>'
                        f'</div>'
                    )
                    st.markdown(card, unsafe_allow_html=True)

                st.caption(
                    "Dividend dates from yfinance · Results dates marked EST. are SEBI regulatory deadlines "
                    "(45 days after quarter end), not confirmed board meeting dates."
                )


# ═══════════════════════════════════════════════════════════════════════════
# PAGE: DOCUMENT ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════
elif page == "Document Analysis":
    st.title("Document Analysis")
    st.caption("Upload annual reports or quarterly results — Claude will analyse them for long-term investing insights.")

    api_key = get_anthropic_key()
    if not api_key:
        st.warning("Add your Anthropic API key to a `.env` file in the project folder: `ANTHROPIC_API_KEY=sk-ant-...`")

    tab1, tab2, tab3 = st.tabs(["Upload & Analyse", "Past Analyses", "Compare Reports"])

    with tab1:
        with st.form("upload_form"):
            c1, c2 = st.columns(2)
            sym = c1.text_input("NSE Symbol (e.g. INFY)").upper()
            company = c2.text_input("Company Name")
            c3, c4, c5 = st.columns(3)
            doc_type = c3.selectbox("Document Type", ["Annual Report", "Quarterly Result (Q1)", "Quarterly Result (Q2)", "Quarterly Result (Q3)", "Quarterly Result (Q4)", "Concall Transcript", "Investor Presentation"])
            year = c4.number_input("Year", min_value=2000, max_value=2030, value=datetime.now().year)
            quarter = c5.selectbox("Quarter (if applicable)", ["—", "Q1", "Q2", "Q3", "Q4"])
            pdf_file = st.file_uploader("Upload PDF", type=["pdf"])
            submitted = st.form_submit_button("Upload & Analyse")

        if submitted and pdf_file and sym:
            safe_name = f"{sym}_{doc_type.replace(' ', '_')}_{year}.pdf"
            period_str = f"{year} {'' if quarter == '—' else quarter}".strip()
            pdf_bytes = pdf_file.read()

            # save to disk only in local mode
            import database as _db_mod
            if not _db_mod._USE_CLOUD:
                filepath = os.path.join(UPLOADS_DIR, safe_name)
                with open(filepath, "wb") as f:
                    f.write(pdf_bytes)
            else:
                filepath = safe_name  # placeholder for cloud

            db.save_document(sym, doc_type, safe_name, filepath, year, None if quarter == "—" else quarter)

            if not api_key:
                st.error("Cannot analyse without an Anthropic API key.")
            else:
                with st.spinner("Claude is analysing the document… this may take 30-60 seconds."):
                    try:
                        # pass bytes directly so it works in cloud too
                        analysis, metrics = ai.analyze_document(
                            pdf_bytes if _db_mod._USE_CLOUD else filepath,
                            sym, company or sym, doc_type, period_str
                        )
                        docs = db.get_documents(sym)
                        if docs:
                            db.update_document_analysis(docs[0]["id"], analysis, metrics)
                        st.success("Analysis complete!")
                        st.markdown(analysis)
                    except Exception as e:
                        st.error(f"Analysis failed: {e}")

    with tab2:
        holdings = db.get_holdings()
        all_syms = sorted({h["symbol"] for h in holdings})
        docs_all = db.get_documents()
        doc_syms = sorted({d["symbol"] for d in docs_all})
        all_opt = sorted(set(all_syms + doc_syms))

        if not all_opt:
            st.info("No documents uploaded yet.")
        else:
            sel = st.selectbox("Filter by stock", ["All"] + all_opt)
            docs = db.get_documents(None if sel == "All" else sel)
            for d in docs:
                label = f"{d['symbol']} — {d['doc_type']} {d['year'] or ''} {d['quarter'] or ''}"
                with st.expander(label):
                    if d.get("analysis"):
                        st.markdown(d["analysis"])
                        st.markdown("---")
                        st.subheader("Ask a question about this report")
                        q = st.text_input("Your question", key=f"q_{d['id']}")
                        if st.button("Ask Claude", key=f"ask_{d['id']}") and q and api_key:
                            with st.spinner("Thinking…"):
                                answer = ai.ask_about_stock(
                                    d["symbol"], d.get("company_name", d["symbol"]),
                                    d["analysis"], q
                                )
                            st.markdown(answer)
                    else:
                        st.info("This document hasn't been analysed yet.")

    with tab3:
        doc_syms2 = sorted({d["symbol"] for d in db.get_documents()})
        if len(doc_syms2) == 0:
            st.info("Upload at least 2 reports for the same stock to compare.")
        else:
            comp_sym = st.selectbox("Select stock to compare across time", doc_syms2)
            docs_for_sym = [d for d in db.get_documents(comp_sym) if d.get("analysis")]
            if len(docs_for_sym) < 2:
                st.info("Need at least 2 analysed documents for this stock.")
            else:
                st.write(f"Found **{len(docs_for_sym)}** analysed documents for {comp_sym}")
                if st.button("Compare All Reports") and api_key:
                    analyses_input = [
                        {
                            "doc_type": d["doc_type"],
                            "period": f"{d['year'] or ''} {d['quarter'] or ''}".strip(),
                            "analysis": d["analysis"],
                        }
                        for d in docs_for_sym
                    ]
                    with st.spinner("Comparing reports…"):
                        comparison = ai.compare_documents(comp_sym, comp_sym, analyses_input)
                    st.markdown(comparison)


# ═══════════════════════════════════════════════════════════════════════════
# PAGE: MARKET NEWS
# ═══════════════════════════════════════════════════════════════════════════
elif page == "Market News":
    st.title("Market News")
    st.caption("Latest from Economic Times, Moneycontrol, NDTV Profit")

    if st.button("Refresh News"):
        st.cache_data.clear()

    with st.spinner("Loading news…"):
        articles = sd.get_market_news(30)

    if not articles:
        st.warning("Could not load news. Check your internet connection.")
    else:
        for a in articles:
            st.markdown(
                f'<div style="background:{theme.BG_CARD};border:1px solid {theme.BORDER};'
                f'border-radius:8px;padding:14px 18px;margin-bottom:8px">'
                f'<div style="font-size:14px;font-weight:500;color:{theme.TEXT_PRI};margin-bottom:6px">'
                f'{a["title"]}</div>'
                + (f'<div style="font-size:12px;color:{theme.TEXT_SEC};margin-bottom:6px">'
                   f'{a.get("summary","")}</div>' if a.get("summary") else "")
                + f'<div style="display:flex;align-items:center;justify-content:space-between">'
                f'<span style="font-size:11px;color:{theme.TEXT_MUTED}">'
                f'{a["source"]} · {a["published"][:16]}</span>'
                + (f'<a href="{a["link"]}" style="font-size:11px;color:{theme.ACCENT_TEAL};'
                   f'text-decoration:none">Read →</a>' if a.get("link") else "")
                + f'</div></div>',
                unsafe_allow_html=True,
            )

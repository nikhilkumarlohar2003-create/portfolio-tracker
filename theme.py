import streamlit as st

# ── color tokens ──────────────────────────────────────────────────────────────
BG_APP      = "#0a0d14"
BG_CARD     = "#111827"
BG_ELEVATED = "#1a2235"
BORDER      = "#1e2d42"
BORDER_MID  = "#2d3f58"
TEXT_PRI    = "#e8edf5"
TEXT_SEC    = "#7a91ad"
TEXT_MUTED  = "#4a5f78"
ACCENT_TEAL = "#00d2b4"
ACCENT_BLUE = "#3b82f6"
GREEN       = "#10c98f"
RED         = "#f05252"
AMBER       = "#f0a500"
SIDEBAR_BG  = "#080b11"

# ── plotly dark template ──────────────────────────────────────────────────────
PLOTLY_LAYOUT = dict(
    paper_bgcolor=BG_CARD,
    plot_bgcolor=BG_CARD,
    font=dict(color=TEXT_PRI, family="Inter, 'Segoe UI', sans-serif", size=12),
    xaxis=dict(gridcolor=BORDER, linecolor=BORDER_MID, tickcolor=TEXT_MUTED,
               tickfont=dict(color=TEXT_SEC)),
    yaxis=dict(gridcolor=BORDER, linecolor=BORDER_MID, tickcolor=TEXT_MUTED,
               tickfont=dict(color=TEXT_SEC)),
    legend=dict(bgcolor=BG_ELEVATED, bordercolor=BORDER, borderwidth=1,
                font=dict(color=TEXT_SEC)),
    margin=dict(t=20, b=20, l=10, r=10),
    hoverlabel=dict(bgcolor=BG_ELEVATED, bordercolor=BORDER_MID,
                    font=dict(color=TEXT_PRI)),
)

CSS = f"""
<style>
/* ── global ─────────────────────────────────────────────────── */
html, body, .stApp {{
    background-color: {BG_APP} !important;
    font-family: -apple-system, 'Segoe UI', Roboto, sans-serif !important;
    color: {TEXT_PRI} !important;
}}

/* ── sidebar ─────────────────────────────────────────────────── */
[data-testid="stSidebar"] {{
    background-color: {SIDEBAR_BG} !important;
    border-right: 1px solid {BORDER} !important;
}}
[data-testid="stSidebar"] .stRadio label {{
    color: {TEXT_SEC} !important;
    font-size: 13px !important;
    font-weight: 400 !important;
    padding: 6px 12px !important;
    border-radius: 6px !important;
    transition: all 0.15s ease;
}}
[data-testid="stSidebar"] .stRadio label:hover {{
    color: {TEXT_PRI} !important;
    background: {BG_ELEVATED} !important;
}}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {{
    color: {TEXT_MUTED} !important;
    font-size: 11px !important;
    letter-spacing: 0.05em;
}}

/* ── main content padding ────────────────────────────────────── */
.block-container {{
    padding: 1.5rem 2.5rem 3rem !important;
    max-width: 1400px !important;
}}

/* ── headings ────────────────────────────────────────────────── */
h1 {{
    font-size: 22px !important;
    font-weight: 600 !important;
    color: {TEXT_PRI} !important;
    letter-spacing: -0.3px !important;
    margin-bottom: 0.25rem !important;
}}
h2, h3 {{
    font-size: 15px !important;
    font-weight: 500 !important;
    color: {TEXT_PRI} !important;
    letter-spacing: 0px !important;
}}

/* ── dividers ────────────────────────────────────────────────── */
hr {{
    border: none !important;
    border-top: 1px solid {BORDER} !important;
    margin: 1.25rem 0 !important;
}}

/* ── metric cards (native) ───────────────────────────────────── */
[data-testid="stMetric"] {{
    background: {BG_CARD} !important;
    border: 1px solid {BORDER} !important;
    border-radius: 10px !important;
    padding: 14px 18px !important;
}}
[data-testid="stMetricLabel"] p {{
    color: {TEXT_SEC} !important;
    font-size: 11px !important;
    font-weight: 500 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
}}
[data-testid="stMetricValue"] {{
    color: {TEXT_PRI} !important;
    font-size: 22px !important;
    font-weight: 600 !important;
    line-height: 1.2 !important;
}}
[data-testid="stMetricDelta"] {{
    font-size: 12px !important;
    font-weight: 500 !important;
}}
[data-testid="stMetricDelta"] svg {{
    display: none !important;
}}

/* ── buttons ─────────────────────────────────────────────────── */
.stButton > button {{
    background: {BG_ELEVATED} !important;
    color: {TEXT_SEC} !important;
    border: 1px solid {BORDER_MID} !important;
    border-radius: 7px !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    padding: 6px 16px !important;
    transition: all 0.15s ease !important;
}}
.stButton > button:hover {{
    background: {ACCENT_TEAL}18 !important;
    color: {ACCENT_TEAL} !important;
    border-color: {ACCENT_TEAL}60 !important;
}}

/* ── form inputs ─────────────────────────────────────────────── */
.stTextInput input, .stNumberInput input, .stSelectbox select,
[data-baseweb="input"] input, [data-baseweb="select"] div {{
    background: {BG_CARD} !important;
    border: 1px solid {BORDER_MID} !important;
    border-radius: 7px !important;
    color: {TEXT_PRI} !important;
    font-size: 13px !important;
}}
.stTextInput input:focus, .stNumberInput input:focus {{
    border-color: {ACCENT_TEAL}80 !important;
    box-shadow: 0 0 0 2px {ACCENT_TEAL}20 !important;
}}
[data-baseweb="select"] [data-baseweb="popover"] {{
    background: {BG_ELEVATED} !important;
    border: 1px solid {BORDER_MID} !important;
}}

/* ── form container ──────────────────────────────────────────── */
[data-testid="stForm"] {{
    background: {BG_CARD} !important;
    border: 1px solid {BORDER} !important;
    border-radius: 12px !important;
    padding: 1.25rem !important;
}}
[data-testid="stFormSubmitButton"] > button {{
    background: {ACCENT_TEAL}18 !important;
    color: {ACCENT_TEAL} !important;
    border: 1px solid {ACCENT_TEAL}50 !important;
    font-weight: 600 !important;
}}
[data-testid="stFormSubmitButton"] > button:hover {{
    background: {ACCENT_TEAL}30 !important;
}}

/* ── tabs ─────────────────────────────────────────────────────── */
[data-baseweb="tab-list"] {{
    background: transparent !important;
    border-bottom: 1px solid {BORDER} !important;
    gap: 4px !important;
}}
[data-baseweb="tab"] {{
    background: transparent !important;
    color: {TEXT_MUTED} !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    border-radius: 6px 6px 0 0 !important;
    padding: 8px 16px !important;
    border-bottom: 2px solid transparent !important;
}}
[aria-selected="true"][data-baseweb="tab"] {{
    color: {ACCENT_TEAL} !important;
    border-bottom: 2px solid {ACCENT_TEAL} !important;
    background: {ACCENT_TEAL}08 !important;
}}
[data-baseweb="tab-panel"] {{
    padding: 1rem 0 !important;
}}

/* ── expanders ───────────────────────────────────────────────── */
[data-testid="stExpander"] {{
    background: {BG_CARD} !important;
    border: 1px solid {BORDER} !important;
    border-radius: 10px !important;
    margin-bottom: 6px !important;
}}
[data-testid="stExpander"] summary {{
    color: {TEXT_PRI} !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    padding: 10px 14px !important;
}}
[data-testid="stExpander"] summary:hover {{
    background: {BG_ELEVATED} !important;
    border-radius: 10px !important;
}}

/* ── dataframes ──────────────────────────────────────────────── */
[data-testid="stDataFrame"] {{
    border: 1px solid {BORDER} !important;
    border-radius: 10px !important;
    overflow: hidden !important;
}}
.dvn-scroller {{
    background: {BG_CARD} !important;
}}

/* ── alerts / info boxes ─────────────────────────────────────── */
[data-testid="stAlert"] {{
    border-radius: 8px !important;
    border-left-width: 3px !important;
    font-size: 13px !important;
}}
.stSuccess {{
    background: {GREEN}15 !important;
    border-left-color: {GREEN} !important;
    color: #7af0c0 !important;
}}
.stWarning {{
    background: {AMBER}15 !important;
    border-left-color: {AMBER} !important;
    color: #f7c97e !important;
}}
.stError {{
    background: {RED}15 !important;
    border-left-color: {RED} !important;
    color: #f99 !important;
}}
.stInfo {{
    background: {ACCENT_BLUE}15 !important;
    border-left-color: {ACCENT_BLUE} !important;
    color: #93c5fd !important;
}}

/* ── spinners ────────────────────────────────────────────────── */
[data-testid="stSpinner"] {{
    color: {ACCENT_TEAL} !important;
}}

/* ── selectbox dropdown ──────────────────────────────────────── */
[data-baseweb="menu"] {{
    background: {BG_ELEVATED} !important;
    border: 1px solid {BORDER_MID} !important;
    border-radius: 8px !important;
}}
[role="option"]:hover {{
    background: {ACCENT_TEAL}18 !important;
}}

/* ── file uploader ───────────────────────────────────────────── */
[data-testid="stFileUploader"] {{
    background: {BG_CARD} !important;
    border: 1px dashed {BORDER_MID} !important;
    border-radius: 10px !important;
}}

/* ── caption text ────────────────────────────────────────────── */
.stCaption, [data-testid="stCaptionContainer"] p {{
    color: {TEXT_MUTED} !important;
    font-size: 11px !important;
}}

/* scrollbar */
::-webkit-scrollbar {{ width: 5px; height: 5px; }}
::-webkit-scrollbar-track {{ background: {BG_APP}; }}
::-webkit-scrollbar-thumb {{ background: {BORDER_MID}; border-radius: 4px; }}
::-webkit-scrollbar-thumb:hover {{ background: {ACCENT_TEAL}60; }}
</style>
"""

# ── component helpers ─────────────────────────────────────────────────────────

def inject():
    st.markdown(CSS, unsafe_allow_html=True)


def kpi_row(cards: list[dict]):
    """
    cards = [{"label": str, "value": str, "delta": str|None, "positive": bool|None, "help": str|None}]
    """
    cols = st.columns(len(cards))
    for col, card in zip(cols, cards):
        delta_html = ""
        if card.get("delta"):
            color = GREEN if card.get("positive", True) else RED
            arrow = "▲" if card.get("positive", True) else "▼"
            delta_html = (
                f'<div style="font-size:11px;font-weight:500;color:{color};'
                f'margin-top:4px">{arrow} {card["delta"]}</div>'
            )
        help_title = f'title="{card["help"]}"' if card.get("help") else ""
        html = f"""
        <div {help_title} style="
            background:{BG_CARD};
            border:1px solid {BORDER};
            border-radius:10px;
            padding:14px 18px;
            min-height:80px;
            cursor:{'help' if card.get('help') else 'default'};
        ">
            <div style="font-size:10px;font-weight:600;color:{TEXT_MUTED};
                        text-transform:uppercase;letter-spacing:0.1em;margin-bottom:6px">
                {card['label']}
            </div>
            <div style="font-size:20px;font-weight:600;color:{TEXT_PRI};line-height:1.2">
                {card['value']}
            </div>
            {delta_html}
        </div>
        """
        col.markdown(html, unsafe_allow_html=True)


def section_header(title: str, subtitle: str = ""):
    sub_html = (
        f'<span style="font-size:12px;font-weight:400;color:{TEXT_MUTED};margin-left:10px">'
        f'{subtitle}</span>'
        if subtitle else ""
    )
    st.markdown(
        f'<div style="display:flex;align-items:center;margin:1.25rem 0 0.6rem;gap:10px">'
        f'<div style="width:3px;height:18px;background:{ACCENT_TEAL};'
        f'border-radius:2px;flex-shrink:0"></div>'
        f'<span style="font-size:14px;font-weight:600;color:{TEXT_PRI}">{title}</span>'
        f'{sub_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


def badge(text: str, kind: str = "neutral") -> str:
    colors = {
        "green":  (f"{GREEN}20",  GREEN),
        "red":    (f"{RED}20",    RED),
        "amber":  (f"{AMBER}20",  AMBER),
        "blue":   (f"{ACCENT_BLUE}20", ACCENT_BLUE),
        "teal":   (f"{ACCENT_TEAL}20", ACCENT_TEAL),
        "neutral":(BG_ELEVATED,   TEXT_SEC),
    }
    bg, fg = colors.get(kind, colors["neutral"])
    return (
        f'<span style="background:{bg};color:{fg};font-size:10px;font-weight:600;'
        f'padding:2px 8px;border-radius:4px;letter-spacing:0.05em">{text}</span>'
    )


def delta_chip(val: float, suffix: str = "%") -> str:
    color = GREEN if val >= 0 else RED
    arrow = "▲" if val >= 0 else "▼"
    return (
        f'<span style="color:{color};font-size:13px;font-weight:600">'
        f'{arrow} {abs(val):.2f}{suffix}</span>'
    )


def apply_plotly(fig, height: int = 350):
    fig.update_layout(**PLOTLY_LAYOUT, height=height)
    return fig

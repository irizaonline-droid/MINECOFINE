from __future__ import annotations

import html
from pathlib import Path

import streamlit as st

from .config import ASSET_DIR, RISK_COLORS


GLOBAL_CSS = """
<style>
:root {
  --navy: #10233A;
  --navy-2: #173A5E;
  --teal: #0F8C7C;
  --amber: #F59E0B;
  --paper: #F6F8FB;
  --muted: #65758B;
  --line: #DCE4EC;
}

html, body, [class*="css"] { font-family: 'Segoe UI', Arial, sans-serif; }
[data-testid="stAppViewContainer"] { background: var(--paper); }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #0D2035 0%, #132E4A 100%);
  border-right: 1px solid rgba(255,255,255,.08);
}
[data-testid="stSidebar"] * { color: #EDF4F8; }
[data-testid="stSidebar"] .stRadio label { padding: .15rem 0; }
[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,.12); }
.block-container { max-width: 1450px; padding-top: 1.9rem; padding-bottom: 3rem; }
h1, h2, h3 { color: var(--navy); letter-spacing: -.025em; }
h1 { font-family: Georgia, 'Times New Roman', serif; font-size: clamp(2rem, 3.2vw, 3.45rem) !important; line-height: 1.04 !important; }
h2 { font-family: Georgia, 'Times New Roman', serif; }
p, li { color: #3B4D63; }
.eyebrow { color: #C57400; font-size: .75rem; font-weight: 800; letter-spacing: .18em; text-transform: uppercase; margin-bottom: .4rem; }
.page-intro { color: #607187; font-size: 1.02rem; max-width: 760px; margin-top: -.45rem; margin-bottom: 1.5rem; }
.brand-lockup { padding: .65rem .3rem 1rem; }
.brand-kicker { color: #F7B438 !important; font-weight: 800; font-size: .68rem; letter-spacing: .16em; }
.brand-name { color: #FFFFFF !important; font-family: Georgia, 'Times New Roman', serif; font-size: 1.35rem; font-weight: 700; line-height: 1.05; margin-top: .3rem; }
.brand-sub { color: #AFC3D2 !important; font-size: .78rem; margin-top: .35rem; }
.demo-chip { display: inline-flex; align-items: center; gap: .42rem; background: #FFF3D6; color: #875A00; border: 1px solid #F5D28B; border-radius: 999px; padding: .38rem .72rem; font-size: .75rem; font-weight: 800; letter-spacing: .04em; }
.demo-chip::before { content: ''; width: .48rem; height: .48rem; border-radius: 99px; background: #F59E0B; box-shadow: 0 0 0 3px rgba(245,158,11,.15); }
.surface-card { background: #FFFFFF; border: 1px solid var(--line); border-radius: 18px; padding: 1.15rem 1.2rem; box-shadow: 0 8px 28px rgba(18,35,60,.05); }
.surface-card h3 { margin: .1rem 0 .35rem; font-size: 1rem; }
.surface-card p { margin: 0; font-size: .88rem; color: var(--muted); }
.risk-callout { border-radius: 16px; padding: 1rem 1.1rem; background: linear-gradient(135deg,#10233A,#17476A); color: white; margin-bottom: 1rem; box-shadow: 0 12px 28px rgba(16,35,58,.15); }
.risk-callout * { color: white !important; }
.risk-callout .small { opacity: .72; font-size: .78rem; text-transform: uppercase; letter-spacing: .12em; font-weight: 700; }
.risk-callout .title { font-size: 1.1rem; font-weight: 700; margin-top: .2rem; }
.reason-card { background: white; border: 1px solid var(--line); border-left: 4px solid var(--amber); border-radius: 14px; padding: .85rem 1rem; min-height: 92px; }
.reason-card .num { font-size: .68rem; font-weight: 800; letter-spacing: .12em; color: #B26D00; }
.reason-card .copy { margin-top: .3rem; color: var(--navy); font-weight: 650; font-size: .9rem; }
.status-row { display: flex; gap: .55rem; flex-wrap: wrap; align-items: center; margin: .25rem 0 1.3rem; }
.status-pill { display: inline-flex; align-items: center; padding: .33rem .64rem; border-radius: 999px; background: #E8F6F3; color: #087565; font-size: .73rem; font-weight: 750; border: 1px solid #C4E7E1; }
.footer-note { color: #8290A2; font-size: .75rem; border-top: 1px solid var(--line); padding-top: 1rem; margin-top: 2rem; }
[data-testid="stMetric"] { background: white; border: 1px solid var(--line); border-radius: 16px; padding: 1rem 1.05rem; box-shadow: 0 6px 20px rgba(18,35,60,.04); }
[data-testid="stMetricLabel"] { color: #6B7B8F; }
[data-testid="stMetricValue"] { color: var(--navy); font-weight: 750; letter-spacing: -.04em; }
.stButton > button, .stDownloadButton > button { border-radius: 10px; font-weight: 700; min-height: 2.7rem; }
.stButton > button[kind="primary"] { background: var(--navy); border-color: var(--navy); }
.stTabs [data-baseweb="tab-list"] { gap: .35rem; }
.stTabs [data-baseweb="tab"] { border-radius: 10px 10px 0 0; padding: .55rem .9rem; }
[data-testid="stDataFrame"] { border: 1px solid var(--line); border-radius: 14px; overflow: hidden; }
@media (max-width: 720px) {
  .block-container { padding-top: 1.1rem; padding-left: 1rem; padding-right: 1rem; }
  .reason-card { min-height: 0; }
}
</style>
"""


def setup_page() -> None:
    st.set_page_config(
        page_title="AssetCare AI | MINECOFIN Rapid MVP",
        page_icon="🛠️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


def render_sidebar_brand() -> None:
    brand_image = ASSET_DIR / "assetcare-banner.png"
    if brand_image.exists():
        st.sidebar.image(str(brand_image), width="stretch")
    st.sidebar.markdown(
        """
        <div class="brand-lockup">
          <div class="brand-kicker">MINECOFIN RAPID MVP</div>
          <div class="brand-name">AssetCare AI</div>
          <div class="brand-sub">Predictive maintenance decision support</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def page_header(kicker: str, title: str, description: str, show_demo_chip: bool = True) -> None:
    st.markdown(f'<div class="eyebrow">{html.escape(kicker)}</div>', unsafe_allow_html=True)
    st.title(title)
    st.markdown(f'<div class="page-intro">{html.escape(description)}</div>', unsafe_allow_html=True)
    if show_demo_chip:
        st.markdown('<div class="demo-chip">SIMULATED DEMO DATA</div>', unsafe_allow_html=True)


def risk_badge(band: str) -> str:
    color = RISK_COLORS.get(band, "#74839A")
    return (
        f'<span style="display:inline-block;background:{color}18;color:{color};border:1px solid {color}55;'
        f'padding:.25rem .58rem;border-radius:999px;font-size:.75rem;font-weight:800">{html.escape(band)}</span>'
    )


def empty_state(title: str, detail: str) -> None:
    st.markdown(
        f'<div class="surface-card"><h3>{html.escape(title)}</h3><p>{html.escape(detail)}</p></div>',
        unsafe_allow_html=True,
    )


def footer(generated_at: str) -> None:
    st.markdown(
        f'<div class="footer-note">Decision-support prototype • Human authorization remains required • '
        f'Last pipeline run: {html.escape(generated_at)}</div>',
        unsafe_allow_html=True,
    )


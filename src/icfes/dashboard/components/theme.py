import streamlit as st


CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;800;900&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    /* ─── Global Background ─── */
    .stApp { background: #070d1a; color: #f8fafc; }

    /* ─── ALWAYS SHOW sidebar collapse button ─── */
    [data-testid="collapsedControl"] {
        display: flex !important;
        visibility: visible !important;
        color: #f8fafc !important;
        background: rgba(56, 189, 248, 0.15) !important;
        border-radius: 0 8px 8px 0 !important;
        border: 1px solid rgba(56, 189, 248, 0.3) !important;
        margin-top: 80px !important;
        z-index: 9999 !important;
    }
    [data-testid="collapsedControl"]:hover {
        background: rgba(56, 189, 248, 0.3) !important;
    }

    /* ─── Sidebar ─── */
    [data-testid="stSidebar"] {
        background: rgba(10, 18, 35, 0.95) !important;
        backdrop-filter: blur(20px);
        border-right: 1px solid rgba(56, 189, 248, 0.15);
        padding-top: 80px !important;
    }
    [data-testid="stSidebar"] * { color: #f8fafc !important; }

    /* ─── Top Navbar ─── */
    .navbar {
        position: fixed;
        top: 0; left: 0; right: 0;
        z-index: 9998;
        background: rgba(7, 13, 26, 0.85);
        backdrop-filter: blur(20px);
        border-bottom: 1px solid rgba(56, 189, 248, 0.15);
        display: flex;
        align-items: center;
        padding: 0 2rem;
        height: 64px;
        gap: 0.5rem;
    }
    .navbar-brand {
        font-size: 1.1rem;
        font-weight: 800;
        background: linear-gradient(90deg, #38bdf8, #818cf8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-right: 2.5rem;
        white-space: nowrap;
        letter-spacing: -0.5px;
    }
    .nav-spacer { flex: 1; }

    /* ─── Page offset for navbar ─── */
    .main > div { padding-top: 80px !important; }
    [data-testid="stSidebar"] > div:first-child { padding-top: 80px !important; }

    /* ─── KPI Cards ─── */
    div[data-testid="metric-container"] {
        background: linear-gradient(135deg, rgba(56,189,248,0.07) 0%, rgba(129,140,248,0.04) 100%);
        border: 1px solid rgba(56, 189, 248, 0.15);
        border-radius: 16px;
        padding: 22px 18px !important;
        box-shadow: 0 4px 24px rgba(0,0,0,0.4);
        transition: transform 0.25s cubic-bezier(.4,0,.2,1), box-shadow 0.25s ease, border-color 0.25s ease;
    }
    div[data-testid="metric-container"]:hover {
        transform: translateY(-4px);
        box-shadow: 0 12px 36px rgba(56,189,248,0.15);
        border-color: rgba(56, 189, 248, 0.4);
    }
    div[data-testid="metric-container"] label {
        color: #94a3b8 !important;
        font-size: 0.82rem !important;
        font-weight: 500 !important;
        letter-spacing: 0.05em;
        text-transform: uppercase;
    }
    div[data-testid="stMetricValue"] > div {
        font-size: 2.1rem !important;
        font-weight: 800 !important;
        background: linear-gradient(135deg, #38bdf8, #818cf8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    /* ─── Section Cards ─── */
    .section-card {
        background: rgba(255,255,255,0.025);
        border: 1px solid rgba(255,255,255,0.07);
        border-radius: 20px;
        padding: 28px 24px;
        margin-bottom: 24px;
        backdrop-filter: blur(10px);
    }
    .section-title {
        font-size: 1rem;
        font-weight: 700;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-bottom: 4px;
    }
    .section-heading {
        font-size: 1.5rem;
        font-weight: 800;
        color: #f8fafc;
        letter-spacing: -0.5px;
        margin-bottom: 20px;
    }

    /* ─── Page Hero ─── */
    .hero-badge {
        display: inline-block;
        background: rgba(56,189,248,0.12);
        border: 1px solid rgba(56,189,248,0.3);
        color: #38bdf8;
        font-size: 0.75rem;
        font-weight: 600;
        padding: 4px 12px;
        border-radius: 99px;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-bottom: 12px;
    }
    .hero-title {
        font-size: 2.8rem;
        font-weight: 900;
        letter-spacing: -2px;
        background: linear-gradient(135deg, #f8fafc 30%, #94a3b8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        line-height: 1.1;
        margin-bottom: 14px;
    }
    .hero-sub {
        font-size: 1.05rem;
        color: #64748b;
        font-weight: 400;
        max-width: 540px;
    }

    /* ─── Divider ─── */
    .grad-divider {
        height: 1px;
        background: linear-gradient(90deg, transparent 0%, rgba(56,189,248,0.4) 50%, transparent 100%);
        margin: 32px 0;
        border: none;
    }

    /* ─── Info boxes (mockdata) ─── */
    .info-chip {
        display: inline-block;
        background: rgba(129,140,248,0.1);
        border: 1px solid rgba(129,140,248,0.25);
        color: #818cf8;
        font-size: 0.78rem;
        padding: 3px 10px;
        border-radius: 99px;
        margin-bottom: 16px;
        font-weight: 600;
    }

    /* ─── Tab Styling: Centered Pill ─── */
    /* DO NOT touch stTabs > div:first-child with flex – breaks panel layout */
    div[data-baseweb="tab-list"] {
        display: inline-flex !important;
        gap: 2px !important;
        background: rgba(10, 18, 40, 0.88) !important;
        backdrop-filter: blur(24px) !important;
        -webkit-backdrop-filter: blur(24px) !important;
        border-radius: 99px !important;
        padding: 5px !important;
        border: 1px solid rgba(56,189,248,0.14) !important;
        box-shadow: 0 0 40px rgba(56,189,248,0.06), inset 0 1px 0 rgba(255,255,255,0.04) !important;
        /* Center trick: auto margins + override any stretch */
        margin-left: auto !important;
        margin-right: auto !important;
        max-width: max-content !important;
        width: auto !important;
        min-width: 0 !important;
    }
    /* Force the row that contains the tab-list to be centered */
    [data-testid="stHorizontalBlock"]:has(div[data-baseweb="tab-list"]),
    div[data-testid="stTabs"] > div > div:first-child {
        display: flex !important;
        justify-content: center !important;
        width: 100% !important;
    }
    div[data-baseweb="tab"] {
        border-radius: 99px !important;
        padding: 9px 26px !important;
        font-weight: 600 !important;
        font-size: 0.865rem !important;
        letter-spacing: 0.015em !important;
        color: #475569 !important;
        transition: all 0.3s cubic-bezier(.4,0,.2,1) !important;
        white-space: nowrap !important;
        border: 1px solid transparent !important;
        position: relative !important;
    }
    div[data-baseweb="tab"]:hover {
        color: #cbd5e1 !important;
        background: rgba(255,255,255,0.05) !important;
    }
    div[aria-selected="true"][data-baseweb="tab"] {
        background: linear-gradient(135deg, rgba(56,189,248,0.18) 0%, rgba(129,140,248,0.18) 100%) !important;
        color: #f0f9ff !important;
        border: 1px solid rgba(56,189,248,0.35) !important;
        box-shadow: 0 0 22px rgba(56,189,248,0.18), inset 0 1px 0 rgba(255,255,255,0.08) !important;
        text-shadow: 0 0 20px rgba(56,189,248,0.5) !important;
    }
    div[data-baseweb="tab-highlight"] { display: none !important; }
    div[data-baseweb="tab-border"] { display: none !important; }
    /* Tab panel fade-in */
    div[data-baseweb="tab-panel"] {
        animation: tabFadeIn 0.35s cubic-bezier(.4,0,.2,1);
        width: 100% !important;
    }
    @keyframes tabFadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to   { opacity: 1; transform: translateY(0); }
    }

    /* ─── Streamlit overrides ─── */
    .stSelectbox > div > div, .stMultiSelect > div > div {
        background: rgba(255,255,255,0.05) !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
        border-radius: 10px !important;
        color: #f8fafc !important;
    }
    .stMarkdown p { color: #94a3b8; }
</style>
"""


def apply_theme():
    st.markdown(CSS, unsafe_allow_html=True)


def dark_layout(**extra) -> dict:
    base = dict(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font_color="#f8fafc",
        font_family="Inter",
        margin=dict(l=0, r=0, t=30, b=0),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#94a3b8")),
        xaxis=dict(showgrid=False, color="#64748b"),
        yaxis=dict(gridcolor="rgba(255,255,255,0.06)", color="#64748b"),
        hovermode="x unified",
    )
    base.update(extra)
    return base

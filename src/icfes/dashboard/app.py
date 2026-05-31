import streamlit as st
from streamlit_option_menu import option_menu

from icfes.core.query_service import make_query_service
from icfes.logger import get_logger
from icfes.dashboard.components.animations import render_animations
from icfes.dashboard.components.navbar import render_navbar
from icfes.dashboard.components.sidebar import render_sidebar
from icfes.dashboard.components.theme import apply_theme
from icfes.dashboard.pages import (
    acerca_de,
    analisis,
    comparativa,
    coordinador,
    covid,
    inicio,
    perfilamiento,
    priorizacion,
    secretario,
    simulador,
    tendencias,
)


# ── Logger ─────────────────────────────────────────────────────────────────
logger = get_logger(__name__)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ICFES Analytics | Saber 11",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Global UI chrome ──────────────────────────────────────────────────────────
apply_theme()
# render_navbar()
render_animations()


# ── Service & Sidebar filters ─────────────────────────────────────────────────
@st.cache_resource
def get_service():
    return make_query_service()


svc = get_service()
where_clause, sel_anos, sel_deptos, sel_genero, sel_naturaleza = render_sidebar(svc)

st.markdown(
    """
    <style>
        div[data-testid="stMarkdownContainer"] {
            padding: 8px 12px;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Main navigation tabs (4 grupos) ──────────────────────────────────────────
tab_inicio, tab_explorar, tab_tableros, tab_covid, tab_acerca = st.tabs(
    [
        "🏠 Inicio",
        "📊 Explorar",
        "🎓 Herramientas",
        "🦠 COVID-19",
        "ℹ️ Acerca de",
    ]
)

# ── Inicio ────────────────────────────────────────────────────────────────────
with tab_inicio:
    inicio.render(svc)

# ── Explorar (sub: Análisis · Comparativa · Tendencias) ───────────────────────
with tab_explorar:
    sub_explorar = option_menu(
        menu_title=None,
        options=["Análisis", "Comparativa", "Tendencias"],
        icons=["bar-chart", "git-compare", "graph-up"],
        menu_icon="cast",
        default_index=0,
        orientation="horizontal",
        key="menu_explorar",
        styles={
            "container": {
                "padding": "4px !important",
                "background-color": "rgba(10, 18, 40, 0.88) !important",
                "border": "1px solid rgba(56, 189, 248, 0.15) !important",
                "border-radius": "99px !important",
                "margin": "0 auto 20px auto !important",
                "max-width": "500px !important",
            },
            "icon": {"color": "#38bdf8", "font-size": "14px"},
            "nav-link": {
                "font-size": "14px",
                "text-align": "center",
                "margin": "0px",
                "color": "#94a3b8",
                "font-weight": "600",
                "border-radius": "99px",
            },
            "nav-link-selected": {
                "background": "linear-gradient(135deg, rgba(56,189,248,0.2) 0%, rgba(129,140,248,0.2) 100%) !important",
                "color": "#f8fafc",
                "border": "1px solid rgba(56, 189, 248, 0.4) !important",
            },
        },
    )
    st.markdown('<div class="grad-divider"></div>', unsafe_allow_html=True)

    if sub_explorar == "Análisis":
        analisis.render(
            svc, where_clause, sel_anos, sel_deptos, sel_genero, sel_naturaleza
        )
    elif sub_explorar == "Comparativa":
        comparativa.render(svc)
    else:
        tendencias.render(svc)

# ── Tableros HU (sub: Coordinador · Secretario · Simulador) ──────────────────
with tab_tableros:
    sub_tableros = option_menu(
        menu_title=None,
        options=[
            "Coordinador",
            "Secretario",
            "Simulador Predictivo",
            "Priorización IPE",
        ],  # "Perfilamiento"
        icons=["mortarboard", "briefcase", "cpu", "award", "person-badge"],
        menu_icon="cast",
        default_index=0,
        orientation="horizontal",
        key="menu_tableros",
        styles={
            "container": {
                "padding": "4px !important",
                "background-color": "rgba(10, 18, 40, 0.88) !important",
                "border": "1px solid rgba(56, 189, 248, 0.15) !important",
                "border-radius": "99px !important",
                "margin": "0 auto 20px auto !important",
                "max-width": "900px !important",
            },
            "icon": {"color": "#38bdf8", "font-size": "14px"},
            "nav-link": {
                "font-size": "11px",
                "text-align": "center",
                "margin": "0px",
                "color": "#94a3b8",
                "font-weight": "600",
                "border-radius": "99px",
            },
            "nav-link-selected": {
                "background": "linear-gradient(135deg, rgba(56,189,248,0.2) 0%, rgba(129,140,248,0.2) 100%) !important",
                "color": "#f8fafc",
                "border": "1px solid rgba(56, 189, 248, 0.4) !important",
            },
            "nav-item": {"align-content": "center"},
        },
    )
    st.markdown('<div class="grad-divider"></div>', unsafe_allow_html=True)

    if sub_tableros == "Coordinador":
        coordinador.render(svc)
    elif sub_tableros == "Secretario":
        secretario.render(svc)
    elif sub_tableros == "Simulador Predictivo":
        simulador.render(svc)
    elif sub_tableros == "Priorización IPE":
        priorizacion.render(svc)
    else:
        perfilamiento.render(svc)

# ── COVID-19 ──────────────────────────────────────────────────────────────────
with tab_covid:
    covid.render(svc)

# ── Acerca de ─────────────────────────────────────────────────────────────────
with tab_acerca:
    acerca_de.render()


# ── Sidebar dynamic state control ─────────────────────────────────────────────
import streamlit.components.v1 as components

# Capture active sub-tab for Explorar section
sub_explorar_val = sub_explorar if "sub_explorar" in locals() else ""

js_sidebar_toggle = f"""
<script>
    function updateSidebar() {{
        const doc = window.parent.document;
        const sidebar = doc.querySelector('[data-testid="stSidebar"]');
        if (!sidebar) return;
        
        // Find active tab name
        const tabs = Array.from(doc.querySelectorAll('[data-baseweb="tab"]'));
        const activeTab = tabs.find(t => t.getAttribute('aria-selected') === 'true');
        const activeTabText = activeTab ? activeTab.textContent : '';
        
        const isExplorarActive = activeTabText.includes('Explorar');
        const isAnalisisSelected = {str(sub_explorar_val == "Análisis").lower()};
        const shouldOpen = isExplorarActive && isAnalisisSelected;
        
        const isCollapsed = sidebar.getAttribute('aria-expanded') === 'false' || 
                            sidebar.getAttribute('data-collapsed') === 'true' ||
                            doc.querySelector('[data-testid="collapsedControl"]') !== null;
                            
        const isMobile = window.parent.innerWidth < 768;
        
        if (shouldOpen && !isMobile) {{
            if (isCollapsed) {{
                const openBtn = doc.querySelector('[data-testid="collapsedControl"] button') || 
                                doc.querySelector('[data-testid="collapsedControl"]');
                if (openBtn) openBtn.click();
            }}
        }} else {{
            if (!isCollapsed) {{
                const closeBtn = doc.querySelector('[data-testid="stSidebarCollapseButton"]') || 
                                 doc.querySelector('button[aria-label="Close"]') ||
                                 doc.querySelector('[data-testid="stSidebar"] button');
                if (closeBtn) closeBtn.click();
            }}
        }}
    }}
    
    // Delayed executions to allow DOM transitions to settle
    setTimeout(updateSidebar, 100);
    setTimeout(updateSidebar, 300);
    setTimeout(updateSidebar, 600);
</script>
"""
components.html(js_sidebar_toggle, height=0, width=0)

import streamlit as st

from icfes.core.query_service import make_query_service
from icfes.dashboard.components.animations import render_animations
from icfes.dashboard.components.navbar import render_navbar
from icfes.dashboard.components.sidebar import render_sidebar
from icfes.dashboard.components.theme import apply_theme
from icfes.dashboard.pages import acerca_de, analisis, comparativa, inicio, tendencias

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ICFES Analytics | Saber 11",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Global UI chrome ──────────────────────────────────────────────────────────
apply_theme()
render_navbar()
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
# ── Main navigation tabs ──────────────────────────────────────────────────────
tab_inicio, tab_analisis, tab_comparativa, tab_tendencias, tab_acerca = st.tabs(
    ["🏠 Inicio", "📊 Análisis", "⚖️ Comparativa", "📈 Tendencias", "ℹ️ Acerca de"]
)

with tab_inicio:
    inicio.render()

with tab_analisis:
    analisis.render(svc, where_clause, sel_anos, sel_deptos, sel_genero, sel_naturaleza)

with tab_comparativa:
    comparativa.render()

with tab_tendencias:
    tendencias.render()

with tab_acerca:
    acerca_de.render()

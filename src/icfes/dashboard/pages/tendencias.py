import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from icfes.dashboard.components.theme import dark_layout
from icfes.dashboard.data.mock import mock_trend_data


def render():
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        '<div class="info-chip">⚠️ Proyecciones ilustrativas · mock data</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="section-heading">Tendencias Históricas y Proyecciones</div>',
        unsafe_allow_html=True,
    )

    df_t = mock_trend_data()
    proj_anos = ["2026", "2027"]
    rng2 = np.random.default_rng(99)
    proj_global = [
        df_t["Global"].iloc[-1] + rng2.uniform(1, 5),
        df_t["Global"].iloc[-1] + rng2.uniform(3, 9),
    ]

    fig_proj = go.Figure()
    fig_proj.add_trace(
        go.Scatter(
            x=df_t["ano"], y=df_t["Global"].round(1), name="Histórico",
            line=dict(color="#38bdf8", width=3),
            fill="tozeroy", fillcolor="rgba(56,189,248,0.1)",
        )
    )
    fig_proj.add_trace(
        go.Scatter(
            x=proj_anos, y=[round(v, 1) for v in proj_global], name="Proyección",
            line=dict(color="#818cf8", width=2.5, dash="dot"),
            marker=dict(size=10, color="#818cf8"),
        )
    )
    fig_proj.add_vrect(
        x0="2026", x1="2027",
        fillcolor="rgba(129,140,248,0.07)", line_width=0,
        annotation_text="Proyección", annotation_position="top left",
        annotation=dict(font_color="#818cf8"),
    )
    fig_proj.update_layout(
        **dark_layout(title="Evolución del Puntaje Global con Proyección 2026–2027")
    )
    st.plotly_chart(fig_proj, use_container_width=True)

    st.markdown('<div class="grad-divider"></div>', unsafe_allow_html=True)

    c_t1, c_t2 = st.columns(2, gap="large")
    with c_t1:
        st.markdown("#### 📚 Áreas de Conocimiento 2015–2025 (mock)")
        fig_areas = px.line(
            df_t, x="ano", y=["Matemáticas", "Lectura", "Ciencias"],
            color_discrete_sequence=["#38bdf8", "#818cf8", "#34d399"], markers=True,
        )
        fig_areas.update_traces(line_width=2.5, marker_size=7)
        fig_areas.update_layout(**dark_layout(title=""))
        st.plotly_chart(fig_areas, use_container_width=True)

    with c_t2:
        st.markdown("#### 📊 Distribución Puntajes Global (mock)")
        rng3 = np.random.default_rng(42)
        scores = np.concatenate([rng3.normal(255, 35, 3000), rng3.normal(310, 20, 800)])
        fig_hist = px.histogram(
            x=scores, nbins=60, color_discrete_sequence=["#38bdf8"],
            labels={"x": "Puntaje Global", "y": "Frecuencia"},
        )
        fig_hist.update_traces(opacity=0.8)
        fig_hist.update_layout(**dark_layout(title="", bargap=0.05))
        st.plotly_chart(fig_hist, use_container_width=True)

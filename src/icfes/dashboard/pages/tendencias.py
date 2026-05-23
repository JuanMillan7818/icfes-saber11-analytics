from __future__ import annotations

import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from icfes.dashboard.components.theme import dark_layout

AREAS = {
    "punt_matematicas": "Matemáticas",
    "punt_lectura_critica": "Lectura Crítica",
    "punt_c_naturales": "Ciencias",
    "punt_sociales_ciudadanas": "Sociales",
    "punt_ingles": "Inglés",
}


def render(svc=None):
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        '<div class="section-heading">Tendencias Históricas y Proyecciones</div>',
        unsafe_allow_html=True,
    )

    # ── Cargar datos históricos ────────────────────────────────────────────────
    areas_sql = ", ".join(
        f"AVG(CAST({col} AS DOUBLE)) AS {alias.replace(' ', '_').replace('á','a').replace('é','e').replace('í','i')}"
        for col, alias in AREAS.items()
    )
    try:
        df_t = (
            svc.query_df(
                f"""
            SELECT ano,
                   AVG(CAST(punt_global AS DOUBLE)) AS Global,
                   {areas_sql}
            FROM {{parquet}}
            WHERE ano IS NOT NULL
            AND isnan(punt_ingles) = false
            GROUP BY ano ORDER BY ano
            """
            )
            if svc
            else None
        )
    except Exception:
        df_t = None

    using_mock = df_t is None or df_t.empty
    if using_mock:
        st.markdown(
            '<div class="info-chip">⚠️ Sin datos reales · conecte la base de datos</div>',
            unsafe_allow_html=True,
        )
        from icfes.dashboard.data.mock import mock_trend_data

        df_t = mock_trend_data()

    # ── Proyección simple (regresión lineal sobre Global histórico) ────────────
    try:
        anos_num = np.array([int(a) for a in df_t["ano"]])
        global_vals = df_t["Global"].values
        coef = np.polyfit(anos_num, global_vals, 1)
        proj_anos = [2026, 2027]
        proj_vals = [np.polyval(coef, y) for y in proj_anos]
    except Exception:
        proj_anos, proj_vals = [], []

    # ── Gráfico principal: histórico + proyección ──────────────────────────────
    fig_proj = go.Figure()
    fig_proj.add_trace(
        go.Scatter(
            x=df_t["ano"].astype(str),
            y=df_t["Global"].round(2),
            name="Histórico",
            line=dict(color="#38bdf8", width=3),
            fill="tozeroy",
            fillcolor="rgba(56,189,248,0.10)",
            hovertemplate="<b>%{x}</b><br>Global: %{y:.1f}<extra></extra>",
        )
    )
    if proj_anos:
        fig_proj.add_trace(
            go.Scatter(
                x=[str(y) for y in proj_anos],
                y=[round(v, 1) for v in proj_vals],
                name="Proyección",
                line=dict(color="#818cf8", width=2.5, dash="dot"),
                marker=dict(size=10, color="#818cf8"),
                hovertemplate="<b>%{x}</b><br>Proyección: %{y:.1f}<extra></extra>",
            )
        )
        fig_proj.add_vrect(
            x0="2026",
            x1="2027",
            fillcolor="rgba(129,140,248,0.07)",
            line_width=0,
            annotation_text="Proyección",
            annotation_position="top left",
            annotation=dict(font_color="#818cf8"),
        )
    fig_proj.update_layout(
        **dark_layout(title="Evolución del Puntaje Global con Proyección 2026–2027")
    )
    st.plotly_chart(fig_proj, use_container_width=True)

    st.markdown('<div class="grad-divider"></div>', unsafe_allow_html=True)

    # ── Áreas de conocimiento ──────────────────────────────────────────────────
    c_t1, c_t2 = st.columns(2, gap="large")

    with c_t1:
        st.markdown("#### 📚 Áreas de Conocimiento 2015–2025")
        area_cols = [
            c
            for c in df_t.columns
            if c not in ("ano", "Global") and not c.startswith("_")
        ]
        if area_cols:
            fig_areas = px.line(
                df_t,
                x="ano",
                y=area_cols,
                color_discrete_sequence=[
                    "#38bdf8",
                    "#818cf8",
                    "#34d399",
                    "#facc15",
                    "#f472b6",
                ],
                markers=True,
            )
            fig_areas.update_traces(line_width=2.5, marker_size=7)
            fig_areas.update_layout(**dark_layout(title=""))
            st.plotly_chart(fig_areas, use_container_width=True)

    with c_t2:
        st.markdown("#### 📊 Distribución Puntaje Global")
        try:
            df_dist = (
                svc.query_df(
                    "SELECT CAST(punt_global AS DOUBLE) AS punt_global FROM {parquet} WHERE punt_global IS NOT NULL LIMIT 50000"
                )
                if svc
                else None
            )
        except Exception:
            df_dist = None

        if df_dist is not None and not df_dist.empty:
            fig_hist = px.histogram(
                df_dist,
                x="punt_global",
                nbins=60,
                color_discrete_sequence=["#38bdf8"],
                labels={"punt_global": "Puntaje Global", "count": "Frecuencia"},
            )
        else:
            rng3 = np.random.default_rng(42)
            scores = np.concatenate(
                [rng3.normal(255, 35, 3000), rng3.normal(310, 20, 800)]
            )
            fig_hist = px.histogram(
                x=scores,
                nbins=60,
                color_discrete_sequence=["#38bdf8"],
                labels={"x": "Puntaje Global", "y": "Frecuencia"},
            )
        fig_hist.update_traces(opacity=0.8)
        fig_hist.update_layout(**dark_layout(title="", bargap=0.05))
        st.plotly_chart(fig_hist, use_container_width=True)

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
    def _area_avg(col: str, alias: str) -> str:
        clean = alias.replace(' ', '_').replace('á','a').replace('é','e').replace('í','i')
        if col == "punt_ingles":
            return (
                f"AVG(CASE WHEN {col} IS NULL OR isnan(CAST({col} AS DOUBLE)) THEN 0.0"
                f" ELSE CAST({col} AS DOUBLE) END) AS {clean}"
            )
        return f"AVG(CAST({col} AS DOUBLE)) AS {clean}"

    areas_sql = ", ".join(_area_avg(col, alias) for col, alias in AREAS.items())
    try:
        df_t = (
            svc.query_df(
                f"""
            SELECT CAST(ano AS INTEGER) AS ano,
                   AVG(CAST(punt_global AS DOUBLE)) AS Global,
                   {areas_sql}
            FROM {{parquet}}
            WHERE ano IS NOT NULL
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

    # ── Proyección OLS — solo datos post-COVID (2022+) ────────────────────────
    # Razón: incluir 2020-2021 genera patrón en U que arruina R² de OLS lineal.
    # La tendencia de recuperación post-pandemia es el predictor relevante.
    POST_COVID_DESDE = 2022
    proj_anos: list[int] = []
    proj_vals: list[float] = []
    proj_meta: dict = {}
    try:
        anos_num = np.array([int(a) for a in df_t["ano"]])
        global_vals = df_t["Global"].values

        # Subconjunto post-COVID para el ajuste
        mask_post = anos_num >= POST_COVID_DESDE
        anos_post = anos_num[mask_post]
        vals_post  = global_vals[mask_post]

        # Necesitamos al menos 2 puntos post-COVID para un ajuste válido
        if len(anos_post) >= 2:
            coef = np.polyfit(anos_post, vals_post, 1)
            anos_fit = anos_post
            vals_fit = vals_post
        else:
            # Fallback: usar todos los datos si hay pocos post-COVID
            coef = np.polyfit(anos_num, global_vals, 1)
            anos_fit = anos_num
            vals_fit = global_vals

        proj_anos = [2026, 2027]
        proj_vals = [float(np.polyval(coef, y)) for y in proj_anos]

        y_hat_fit = np.polyval(coef, anos_fit)
        ss_res = float(np.sum((vals_fit - y_hat_fit) ** 2))
        ss_tot = float(np.sum((vals_fit - np.mean(vals_fit)) ** 2))
        r2 = round(1.0 - ss_res / ss_tot, 4) if ss_tot > 0 else 0.0
        mse = float(np.mean((vals_fit - y_hat_fit) ** 2))
        rmse = float(np.sqrt(mse))
        proj_meta = {
            "r2": r2,
            "mse": round(mse, 2),
            "rmse": round(rmse, 2),
            "n": int(len(anos_fit)),
            "n_total": int(len(anos_num)),
            "pendiente": round(float(coef[0]), 3),
            "base": f"{int(anos_fit[0])}–{int(anos_fit[-1])} (post-COVID)" if len(anos_post) >= 2 else "todos los años",
            "confianza_pct": round(max(r2, 0.0) * 100, 1),
            "nivel": "Alta" if r2 >= 0.85 else "Moderada" if r2 >= 0.60 else "Baja",
        }
    except Exception:
        pass

    # ── Gráfico principal: histórico + proyección ──────────────────────────────
    all_vals = list(df_t["Global"].values) + (proj_vals if proj_vals else [])
    y_min_g = min(all_vals)
    y_max_g = max(all_vals)
    y_pad_g = max((y_max_g - y_min_g) * 0.4, 3.0)

    fig_proj = go.Figure()
    fig_proj.add_trace(
        go.Scatter(
            x=df_t["ano"].astype(str),
            y=df_t["Global"].round(2),
            name="Histórico",
            line=dict(color="#38bdf8", width=3),
            fill="none",
            marker=dict(size=7, color="#38bdf8"),
            hovertemplate="<b>%{x}</b><br>Global: %{y:.1f}<extra></extra>",
        )
    )
    if proj_anos and proj_vals:
        # Anclar proyección al último dato real para continuidad visual
        ultimo_ano = str(df_t["ano"].iloc[-1])
        ultimo_val = round(float(df_t["Global"].iloc[-1]), 2)
        x_proj = [ultimo_ano] + [str(y) for y in proj_anos]
        y_proj = [ultimo_val] + [round(v, 1) for v in proj_vals]

        fig_proj.add_trace(
            go.Scatter(
                x=x_proj,
                y=y_proj,
                name="Proyección OLS",
                line=dict(color="#818cf8", width=2.5, dash="dot"),
                marker=dict(size=9, color="#818cf8",
                            symbol=["circle"] + ["diamond"] * len(proj_anos)),
                hovertemplate="<b>%{x}</b><br>Proyección: %{y:.1f}<extra></extra>",
            )
        )
        fig_proj.add_vrect(
            x0=str(proj_anos[0]),
            x1=str(proj_anos[-1]),
            fillcolor="rgba(129,140,248,0.07)",
            line_width=0,
            annotation_text="Proyección",
            annotation_position="top left",
            annotation=dict(font_color="#818cf8"),
        )
    fig_proj.update_layout(
        **dark_layout(title="Evolución del Puntaje Global con Proyección 2026–2027")
    )
    fig_proj.update_layout(
        yaxis=dict(range=[y_min_g - y_pad_g, y_max_g + y_pad_g],
                   title="Puntaje Global Promedio")
    )
    st.plotly_chart(fig_proj, use_container_width=True)

    if proj_meta:
        nivel_color = {"Alta": "#34d399", "Moderada": "#facc15", "Baja": "#f87171"}.get(
            proj_meta["nivel"], "#94a3b8"
        )
        st.markdown(
            f"""
            <div style="display:flex;flex-wrap:wrap;gap:10px;margin-bottom:8px;">
              <div class="info-chip">
                🤖 <strong>Algoritmo:</strong> Regresión Lineal OLS
                &nbsp;|&nbsp; <strong>Base del ajuste:</strong> {proj_meta.get('base', 'todos los años')}
                &nbsp;|&nbsp; <strong>n ajuste:</strong> {proj_meta['n']} años
                &nbsp;|&nbsp; <strong>Pendiente:</strong> {proj_meta['pendiente']:+.3f} pts/año
              </div>
              <div class="info-chip">
                📐 <strong>R²:</strong> {proj_meta['r2']:.4f}
                &nbsp;|&nbsp; <strong>MSE:</strong> {proj_meta['mse']:.2f}
                &nbsp;|&nbsp; <strong>RMSE:</strong> {proj_meta['rmse']:.2f}
              </div>
              <div class="info-chip" style="border-color:{nivel_color};color:{nivel_color};">
                🎯 <strong>Confianza proyección:</strong> {proj_meta['confianza_pct']}%
                &nbsp;·&nbsp; Nivel: <strong>{proj_meta['nivel']}</strong>
              </div>
            </div>
            <div style="color:#475569;font-size:0.75rem;margin-bottom:12px;">
              ⚠️ Proyección basada en tendencia post-COVID (2022+) — excluye años de pandemia para evitar distorsión en la regresión lineal.
              R² mide ajuste sobre datos de entrenamiento — no garantiza exactitud futura.
            </div>
            """,
            unsafe_allow_html=True,
        )

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

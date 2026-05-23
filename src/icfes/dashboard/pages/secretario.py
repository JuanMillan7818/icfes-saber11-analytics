"""
HU 2 · Tablero del Secretario de Educación
Equidad Regional y Post-Pandemia.
Evolución Oficial vs No Oficial / Urbano vs Rural + métrica Rezago Post-Pandemia.
"""

from __future__ import annotations

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

from icfes.dashboard.components.theme import dark_layout


@st.cache_data(ttl=600, show_spinner=False)
def _deptos(_svc):
    try:
        df = _svc.query_df(
            "SELECT DISTINCT cole_depto_ubicacion FROM {parquet} WHERE cole_depto_ubicacion IS NOT NULL AND cole_depto_ubicacion != '' ORDER BY cole_depto_ubicacion"
        )
        return df["cole_depto_ubicacion"].dropna().tolist()
    except Exception:
        return []


@st.cache_data(ttl=600, show_spinner=False)
def _mcpios(_svc, depto: str):
    try:
        df = _svc.query_df(
            f"""
            SELECT DISTINCT cole_mcpio_ubicacion FROM {{parquet}}
            WHERE cole_depto_ubicacion = '{depto}' AND cole_mcpio_ubicacion IS NOT NULL
            ORDER BY cole_mcpio_ubicacion
            """
        )
        return df["cole_mcpio_ubicacion"].dropna().tolist()
    except Exception:
        return []


@st.cache_data(ttl=600, show_spinner=False)
def _trend_naturaleza(_svc, where: str):
    try:
        df = _svc.query_df(
            f"""
            SELECT ano, cole_naturaleza AS Tipo,
                   AVG(CAST(punt_global AS DOUBLE)) AS Promedio
            FROM {{parquet}}
            WHERE cole_naturaleza IS NOT NULL AND ano IS NOT NULL {where}
            GROUP BY ano, cole_naturaleza
            ORDER BY ano
            """
        )
        return df if not df.empty else None
    except Exception:
        return None


@st.cache_data(ttl=600, show_spinner=False)
def _trend_area_ubicacion(_svc, where: str):
    try:
        df = _svc.query_df(
            f"""
            SELECT ano, cole_area_ubicacion AS Area,
                   AVG(CAST(punt_global AS DOUBLE)) AS Promedio
            FROM {{parquet}}
            WHERE cole_area_ubicacion IS NOT NULL AND ano IS NOT NULL {where}
            GROUP BY ano, cole_area_ubicacion
            ORDER BY ano
            """
        )
        return df if not df.empty else None
    except Exception:
        return None


@st.cache_data(ttl=600, show_spinner=False)
def _rezago(_svc, where: str):
    """Promedio por año clave: 2019, 2022, 2025."""
    try:
        df = _svc.query_df(
            f"""
            SELECT ano, AVG(CAST(punt_global AS DOUBLE)) AS Promedio
            FROM {{parquet}}
            WHERE ano IN ('2019','2022','2025') {where}
            GROUP BY ano ORDER BY ano
            """
        )
        return df if not df.empty else None
    except Exception:
        return None


def render(svc=None):
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        """
        <div class="hero-badge">⚖️ Secretario de Educación</div>
        <div class="section-heading">Equidad Regional y Rezago Post-Pandemia</div>
        <div style="color:#64748b;font-size:0.9rem;margin-bottom:20px;">
            Evolución de brechas Oficial vs Privado, Urbano vs Rural y el impacto
            del rezago educativo post-pandemia en tu región.
        </div>
        """,
        unsafe_allow_html=True,
    )

    if svc is None:
        st.warning("⚠️ Servicio de datos no disponible.")
        return

    # ── Filtros cascada depto → municipio ──────────────────────────────────────
    with st.spinner("Cargando departamentos..."):
        deptos = _deptos(svc)

    f1, f2 = st.columns(2)
    with f1:
        sel_depto = st.selectbox(
            "📍 Departamento",
            ["— Nacional —"] + [d.title() for d in deptos],
        )

    with f2:
        if sel_depto != "— Nacional —":
            # buscar el valor original en la lista
            depto_raw = next((d for d in deptos if d.title() == sel_depto), sel_depto)
            mcpios = _mcpios(svc, depto_raw)
            sel_mcpio = st.selectbox(
                "🏙️ Municipio",
                ["— Todos —"] + [m.title() for m in mcpios],
            )
        else:
            depto_raw = None
            sel_mcpio = "— Todos —"
            st.selectbox("🏙️ Municipio", ["— Todos —"], disabled=True)

    # Construir cláusula WHERE adicional
    add_where = ""
    if depto_raw:
        add_where += f" AND cole_depto_ubicacion = '{depto_raw}'"
    if sel_mcpio != "— Todos —":
        mcpio_raw = next(
            (m for m in _mcpios(svc, depto_raw) if m.title() == sel_mcpio),
            sel_mcpio,
        )
        add_where += f" AND cole_mcpio_ubicacion = '{mcpio_raw}'"

    st.markdown('<div class="grad-divider"></div>', unsafe_allow_html=True)

    # ── Rezago Post-Pandemia ───────────────────────────────────────────────────
    st.markdown("#### 📉 Métrica Rezago Post-Pandemia")
    st.caption(
        "Comparación del promedio nacional en 2019, 2022 y 2025 para la región seleccionada."
    )

    with st.spinner("Calculando rezago..."):
        df_rez = _rezago(svc, add_where)

    if df_rez is not None and not df_rez.empty:
        anos_rez = df_rez["ano"].astype(str).tolist()
        vals_rez = {str(r["ano"]): float(r["Promedio"]) for _, r in df_rez.iterrows()}

        k2019 = vals_rez.get("2019")
        k2022 = vals_rez.get("2022")
        k2025 = vals_rez.get("2025")

        rk1, rk2, rk3, rk4 = st.columns(4)
        rk1.metric("📘 2019 (pre-pandemia)", f"{k2019:.1f}" if k2019 else "N/A")
        rk2.metric(
            "📉 2022",
            f"{k2022:.1f}" if k2022 else "N/A",
            delta=f"{k2022 - k2019:.1f} pts" if k2022 and k2019 else None,
            delta_color="normal",
        )
        rk3.metric(
            "🌱 2025",
            f"{k2025:.1f}" if k2025 else "N/A",
            delta=f"{k2025 - k2019:.1f} pts vs 2019" if k2025 and k2019 else None,
            delta_color="normal",
        )
        rezago_val = (k2019 - k2022) if k2019 and k2022 else None
        rk4.metric(
            "⚠️ Rezago (2019→2022)",
            f"{rezago_val:.1f} pts" if rezago_val else "N/A",
        )
    else:
        st.info("Sin datos para los años 2019, 2022 o 2025 en el filtro seleccionado.")

    st.markdown('<div class="grad-divider"></div>', unsafe_allow_html=True)

    # ── Oficial vs No Oficial ──────────────────────────────────────────────────
    st.markdown("#### 🏫 Promedio Global: Oficial vs No Oficial (2015–2025)")
    with st.spinner("Cargando tendencia por naturaleza..."):
        df_nat = _trend_naturaleza(svc, add_where)

    if df_nat is not None and not df_nat.empty:
        fig_nat = go.Figure()
        color_nat = {"OFICIAL": "#818cf8", "NO OFICIAL": "#34d399"}
        for tipo in df_nat["Tipo"].unique():
            sub = df_nat[df_nat["Tipo"] == tipo]
            fig_nat.add_trace(
                go.Scatter(
                    x=sub["ano"].astype(str),
                    y=sub["Promedio"].round(1),
                    name=str(tipo),
                    mode="lines+markers",
                    line=dict(
                        color=color_nat.get(str(tipo).upper(), "#94a3b8"), width=2.5
                    ),
                    marker=dict(size=8),
                    hovertemplate=f"<b>%{{x}}</b><br>{tipo}: %{{y:.1f}}<extra></extra>",
                )
            )
        fig_nat.update_layout(
            **dark_layout(
                title="",
                legend=dict(
                    orientation="h", yanchor="bottom", y=1.02, bgcolor="rgba(0,0,0,0)"
                ),
            )
        )
        st.plotly_chart(fig_nat, use_container_width=True)
    else:
        st.info("Sin datos de naturaleza de colegio para el filtro seleccionado.")

    st.markdown('<div class="grad-divider"></div>', unsafe_allow_html=True)

    # ── Urbano vs Rural ────────────────────────────────────────────────────────
    st.markdown("#### 🌐 Promedio Global: Urbano vs Rural (2015–2025)")
    with st.spinner("Cargando tendencia urbano/rural..."):
        df_area = _trend_area_ubicacion(svc, add_where)

    if df_area is not None and not df_area.empty:
        fig_area = go.Figure()
        color_area = {"URBANO": "#38bdf8", "RURAL": "#f87171"}
        for area in df_area["Area"].unique():
            sub = df_area[df_area["Area"] == area]
            c = color_area.get(str(area).upper(), "#94a3b8")
            fig_area.add_trace(
                go.Scatter(
                    x=sub["ano"].astype(str),
                    y=sub["Promedio"].round(1),
                    name=str(area),
                    mode="lines+markers",
                    line=dict(color=c, width=2.5),
                    fill="tozeroy",
                    fillcolor=f"rgba({','.join(str(int(c.lstrip('#')[i:i+2],16)) for i in (0,2,4))},0.08)",
                    marker=dict(size=8),
                    hovertemplate=f"<b>%{{x}}</b><br>{area}: %{{y:.1f}}<extra></extra>",
                )
            )
        fig_area.update_layout(
            **dark_layout(
                title="",
                legend=dict(
                    orientation="h", yanchor="bottom", y=1.02, bgcolor="rgba(0,0,0,0)"
                ),
            )
        )
        st.plotly_chart(fig_area, use_container_width=True)
    else:
        st.info("Sin datos de área de ubicación para el filtro seleccionado.")

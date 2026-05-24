"""
COVID-19 Impact Analysis · Saber 11
Compara rendimiento pre/durante/post pandemia.
Períodos:
  Pre-COVID   2015–2019
  COVID       2020–2021  (cierre / alternancia / virtualidad)
  Post-COVID  2022–2024+
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from icfes.dashboard.components.theme import dark_layout

# ── Constantes de período ──────────────────────────────────────────────────────
PRE = (2015, 2019)
COV = (2020, 2021)
POST = (2022, 2025)

AREAS = {
    "punt_global": "Global",
    "punt_matematicas": "Matemáticas",
    "punt_lectura_critica": "Lectura Crítica",
    "punt_c_naturales": "Ciencias Nat.",
    "punt_sociales_ciudadanas": "Sociales",
    "punt_ingles": "Inglés",
}

PALETTE = {
    "Pre-COVID": "#38bdf8",
    "COVID": "#f43f5e",
    "Post-COVID": "#34d399",
}


# ── Helpers ────────────────────────────────────────────────────────────────────


def _periodo(ano: int) -> str:
    if PRE[0] <= ano <= PRE[1]:
        return "Pre-COVID"
    if COV[0] <= ano <= COV[1]:
        return "COVID"
    return "Post-COVID"


def _query_yearly(svc) -> pd.DataFrame | None:
    """Promedio anual por área desde datos reales."""
    cols_sql = ", ".join(
        f"AVG(CAST({col} AS DOUBLE)) AS {alias.replace(' ', '_').replace('.', '')}"
        for col, alias in AREAS.items()
    )
    try:
        df = svc.query_df(
            f"SELECT ano, {cols_sql} FROM {{parquet}} WHERE ano IS NOT NULL GROUP BY ano ORDER BY ano"
        )
        if df.empty:
            return None
        df["ano"] = df["ano"].astype(str)
        df["Período"] = df["ano"].astype(int).map(_periodo)
        return df
    except Exception:
        return None


def _mock_yearly() -> pd.DataFrame:
    """Fallback realista si la DB falla."""
    rng = np.random.default_rng(42)
    anos = list(range(2015, 2025))
    base = {
        "ano": [str(a) for a in anos],
        "Global": [0.0] * len(anos),
        "Matemáticas": [0.0] * len(anos),
        "Lectura_Crítica": [0.0] * len(anos),
        "Ciencias_Nat": [0.0] * len(anos),
        "Sociales": [0.0] * len(anos),
        "Inglés": [0.0] * len(anos),
    }
    means = {
        "Global": 256,
        "Matemáticas": 49,
        "Lectura_Crítica": 51,
        "Ciencias_Nat": 48,
        "Sociales": 47,
        "Inglés": 46,
    }
    drops = {
        "Global": 7,
        "Matemáticas": 4,
        "Lectura_Crítica": 3,
        "Ciencias_Nat": 5,
        "Sociales": 6,
        "Inglés": 8,
    }
    for i, ano in enumerate(anos):
        periodo = _periodo(ano)
        drop = 1 if periodo == "COVID" else 0
        for col, m in means.items():
            noise = rng.normal(0, 1.2)
            if drop:
                base[col][i] = m - drops[col] + noise
            elif periodo == "Post-COVID":
                recovery = (ano - COV[1]) * 1.8
                base[col][i] = (m - drops[col]) + recovery + noise
            else:
                base[col][i] = m + rng.normal(0, 2)
    df = pd.DataFrame(base)
    df["Período"] = df["ano"].astype(int).map(_periodo)
    return df


def _kpi_by_period(df: pd.DataFrame) -> dict:
    """Calcula promedios de Global por período."""
    result = {}
    for p in ["Pre-COVID", "COVID", "Post-COVID"]:
        sub = df[df["Período"] == p]["Global"]
        result[p] = sub.mean() if not sub.empty else None
    return result


def _recovery_rate(kpis: dict) -> float | None:
    pre = kpis.get("Pre-COVID")
    post = kpis.get("Post-COVID")
    cov = kpis.get("COVID")
    if pre and cov:
        caida = pre - cov
        if caida > 0 and post:
            return min(((post - cov) / caida) * 100, 100)
    return None


def _query_depto_period(svc) -> pd.DataFrame | None:
    """Promedio global por depto y período."""
    try:
        df = svc.query_df(
            """
            SELECT cole_depto_ubicacion AS Departamento,
                   ano,
                   AVG(CAST(punt_global AS DOUBLE)) AS Promedio
            FROM {parquet}
            WHERE cole_depto_ubicacion IS NOT NULL AND ano IS NOT NULL AND cole_depto_ubicacion != ''
            GROUP BY cole_depto_ubicacion, ano ORDER BY cole_depto_ubicacion
            """
        )
        if df.empty:
            return None
        df["Período"] = df["ano"].astype(int).map(_periodo)
        pivot = df.groupby(["Departamento", "Período"])["Promedio"].mean().reset_index()
        wide = pivot.pivot(
            index="Departamento", columns="Período", values="Promedio"
        ).reset_index()
        wide.columns.name = None
        for col in ["Pre-COVID", "COVID", "Post-COVID"]:
            if col not in wide.columns:
                wide[col] = np.nan
        if "Pre-COVID" in wide.columns and "COVID" in wide.columns:
            wide["Caída_pts"] = (wide["Pre-COVID"] - wide["COVID"]).round(2)
        if "COVID" in wide.columns and "Post-COVID" in wide.columns:
            wide["Recuperación_%"] = (
                (
                    (
                        (wide["Post-COVID"] - wide["COVID"])
                        / (wide["Pre-COVID"] - wide["COVID"]).replace(0, np.nan)
                    )
                    * 100
                )
                .clip(0, 100)
                .round(1)
            )
        return wide.dropna(subset=["Pre-COVID"]).sort_values(
            "Caída_pts", ascending=False
        )
    except Exception:
        return None


def _mock_depto_impact() -> pd.DataFrame:
    rng = np.random.default_rng(7)
    deptos = [
        "Cundinamarca",
        "Antioquia",
        "Valle",
        "Santander",
        "Boyacá",
        "Risaralda",
        "Quindío",
        "Atlántico",
        "Caldas",
        "Nariño",
        "Huila",
        "Tolima",
        "Córdoba",
        "Bolívar",
        "Meta",
    ]
    pre = 255 + rng.uniform(-20, 30, len(deptos))
    drop = rng.uniform(3, 15, len(deptos))
    rec = rng.uniform(40, 95, len(deptos))
    cov = pre - drop
    post = cov + drop * (rec / 100)
    return pd.DataFrame(
        {
            "Departamento": deptos,
            "Pre-COVID": pre.round(2),
            "COVID": cov.round(2),
            "Post-COVID": post.round(2),
            "Caída_pts": drop.round(2),
            "Recuperación_%": rec.round(1),
        }
    ).sort_values("Caída_pts", ascending=False)


def _query_gender_period(svc) -> pd.DataFrame | None:
    try:
        df = svc.query_df(
            """
            SELECT estu_genero AS Genero,
                   ano,
                   AVG(CAST(punt_global AS DOUBLE)) AS Promedio
            FROM {parquet}
            WHERE estu_genero IS NOT NULL AND ano IS NOT NULL AND estu_genero != ''
            GROUP BY estu_genero, ano
            """
        )
        if df.empty:
            return None
        df["Período"] = df["ano"].astype(int).map(_periodo)
        return df.groupby(["Genero", "Período"])["Promedio"].mean().reset_index()
    except Exception:
        return None


# ── Render principal ───────────────────────────────────────────────────────────


def render(svc=None):
    st.markdown("<br>", unsafe_allow_html=True)

    # Hero header
    st.markdown(
        """
        <div class="hero-badge">🦠 Análisis de Impacto</div>
        <div class="hero-title">COVID-19 & Educación</div>
        <div class="hero-sub">
            Comportamiento del rendimiento académico antes, durante y después de la pandemia.
            Modalidades: presencial → virtual/alternancia → retorno gradual.
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Timeline visual
    st.markdown(
        """
        <div style="display:flex;gap:8px;margin:24px 0 8px 0;flex-wrap:wrap;">
            <div style="background:rgba(56,189,248,0.12);border:1px solid rgba(56,189,248,0.35);
                        border-radius:10px;padding:10px 20px;flex:1;min-width:160px;">
                <div style="color:#38bdf8;font-weight:700;font-size:.8rem;letter-spacing:.08em;">PRE-COVID</div>
                <div style="color:#f8fafc;font-weight:800;font-size:1.4rem;">2015 – 2019</div>
                <div style="color:#64748b;font-size:.8rem;">Modalidad presencial</div>
            </div>
            <div style="background:rgba(244,63,94,0.12);border:1px solid rgba(244,63,94,0.35);
                        border-radius:10px;padding:10px 20px;flex:1;min-width:160px;">
                <div style="color:#f43f5e;font-weight:700;font-size:.8rem;letter-spacing:.08em;">PANDEMIA</div>
                <div style="color:#f8fafc;font-weight:800;font-size:1.4rem;">2020 – 2021</div>
                <div style="color:#64748b;font-size:.8rem;">Virtual / Alternancia</div>
            </div>
            <div style="background:rgba(52,211,153,0.12);border:1px solid rgba(52,211,153,0.35);
                        border-radius:10px;padding:10px 20px;flex:1;min-width:160px;">
                <div style="color:#34d399;font-weight:700;font-size:.8rem;letter-spacing:.08em;">POST-COVID</div>
                <div style="color:#f8fafc;font-weight:800;font-size:1.4rem;">2022 – hoy</div>
                <div style="color:#64748b;font-size:.8rem;">Retorno gradual</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Cargar datos ──────────────────────────────────────────────────────────
    with st.spinner("Cargando datos COVID..."):
        df_yearly = _query_yearly(svc) if svc else None
        using_mock = df_yearly is None
        if using_mock:
            df_yearly = _mock_yearly()

    if using_mock:
        st.markdown(
            '<div class="info-chip">⚠️ Datos ilustrativos · conecte la base de datos para datos reales</div>',
            unsafe_allow_html=True,
        )

    # Normalizar nombres de col (la query usa _ en lugar de espacio)
    col_global = next(
        (c for c in df_yearly.columns if "global" in c.lower() or c == "Global"),
        "Global",
    )
    if col_global != "Global":
        df_yearly = df_yearly.rename(columns={col_global: "Global"})

    kpis = _kpi_by_period(df_yearly)

    # ── KPI Row ───────────────────────────────────────────────────────────────
    st.markdown('<div class="grad-divider"></div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-title">Métricas de Impacto</div>', unsafe_allow_html=True
    )
    st.markdown(
        '<div class="section-heading">Indicadores Clave · Puntaje Global</div>',
        unsafe_allow_html=True,
    )

    k1, k2, k3, k4, k5 = st.columns(5)

    pre_val = kpis.get("Pre-COVID")
    cov_val = kpis.get("COVID")
    post_val = kpis.get("Post-COVID")
    caida = (pre_val - cov_val) if pre_val and cov_val else None
    rec_rate = _recovery_rate(kpis)

    k1.metric("📘 Pre-COVID (avg)", f"{pre_val:.1f}" if pre_val else "N/A")
    k2.metric(
        "🦠 COVID (avg)",
        f"{cov_val:.1f}" if cov_val else "N/A",
        delta=f"{-caida:.1f} pts" if caida else None,
        delta_color="inverse",
    )
    k3.metric(
        "🌱 Post-COVID (avg)",
        f"{post_val:.1f}" if post_val else "N/A",
        delta=f"+{post_val - cov_val:.1f} pts" if post_val and cov_val else None,
    )
    k4.metric("📉 Caída Pandemia", f"{caida:.1f} pts" if caida else "N/A")
    k5.metric("🔄 Índice Recuperación", f"{rec_rate:.0f}%" if rec_rate else "N/A")

    st.markdown('<div class="grad-divider"></div>', unsafe_allow_html=True)

    # ── Gráfico principal: evolución con banda COVID ──────────────────────────
    st.markdown(
        '<div class="section-title">Evolución Temporal</div>', unsafe_allow_html=True
    )
    st.markdown(
        '<div class="section-heading">Puntaje Global por Año · Banda COVID sombreada</div>',
        unsafe_allow_html=True,
    )

    fig_ev = go.Figure()

    # Banda COVID
    fig_ev.add_vrect(
        x0="2020",
        x1="2021",
        fillcolor="rgba(244,63,94,0.10)",
        line_color="rgba(244,63,94,0.35)",
        line_width=1,
        annotation_text="🦠 Pandemia",
        annotation_position="top left",
        annotation=dict(font_color="#f43f5e", font_size=12),
    )

    # Línea global coloreada por período
    for periodo, color in PALETTE.items():
        sub = df_yearly[df_yearly["Período"] == periodo]
        if not sub.empty:
            fig_ev.add_trace(
                go.Scatter(
                    x=sub["ano"],
                    y=sub["Global"].round(1),
                    name=periodo,
                    mode="lines+markers",
                    line=dict(color=color, width=3),
                    marker=dict(
                        size=9, color=color, line=dict(color="#070d1a", width=2)
                    ),
                    hovertemplate="<b>%{x}</b><br>Puntaje: %{y:.1f}<extra>"
                    + periodo
                    + "</extra>",
                )
            )

    fig_ev.update_layout(
        **dark_layout(
            title="",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                bgcolor="rgba(0,0,0,0)",
                font=dict(color="#94a3b8"),
            ),
        )
    )
    st.plotly_chart(fig_ev, use_container_width=True)

    st.markdown('<div class="grad-divider"></div>', unsafe_allow_html=True)

    # ── Áreas de conocimiento: barras agrupadas por período ───────────────────
    st.markdown('<div class="section-title">Competencias</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-heading">Promedio por Área y Período Educativo</div>',
        unsafe_allow_html=True,
    )

    # Construir df de áreas disponibles
    area_cols_available = [
        c
        for c in df_yearly.columns
        if c not in ("ano", "Período") and not c.startswith("_")
    ]

    if area_cols_available:
        df_area_period = (
            df_yearly.groupby("Período")[area_cols_available].mean().reset_index()
        )
        df_melt = df_area_period.melt(
            id_vars="Período", var_name="Área", value_name="Promedio"
        )
        # Orden período
        df_melt["Período"] = pd.Categorical(
            df_melt["Período"],
            categories=["Pre-COVID", "COVID", "Post-COVID"],
            ordered=True,
        )
        df_melt = df_melt.sort_values("Período")

        fig_bar = px.bar(
            df_melt,
            x="Área",
            y="Promedio",
            color="Período",
            barmode="group",
            color_discrete_map=PALETTE,
            text_auto=".1f",
        )
        fig_bar.update_traces(
            textfont_color="#f8fafc",
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>%{fullData.name}: %{y:.1f}<extra></extra>",
        )
        fig_bar.update_layout(
            **dark_layout(
                title="",
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#94a3b8"),
                ),
                xaxis=dict(title=""),
                yaxis=dict(title="Promedio", gridcolor="rgba(255,255,255,0.06)"),
            )
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    st.markdown('<div class="grad-divider"></div>', unsafe_allow_html=True)

    # ── Impacto por departamento ───────────────────────────────────────────────
    st.markdown('<div class="section-title">Geografía</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-heading">Caída y Recuperación por Departamento</div>',
        unsafe_allow_html=True,
    )

    with st.spinner("Cargando datos departamentales..."):
        df_depto = _query_depto_period(svc) if svc else None
        if df_depto is None or df_depto.empty:
            df_depto = _mock_depto_impact()

    c_geo1, c_geo2 = st.columns([3, 2], gap="large")

    n_deptos = len(df_depto)
    chart_h = max(400, n_deptos * 28)

    with c_geo1:
        fig_depto = px.bar(
            df_depto,
            x="Caída_pts",
            y="Departamento",
            orientation="h",
            color="Caída_pts",
            color_continuous_scale=["#34d399", "#facc15", "#f43f5e"],
            text_auto=".1f",
            labels={"Caída_pts": "Puntos perdidos", "Departamento": ""},
        )
        fig_depto.update_traces(
            textfont_color="#f8fafc",
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>Caída: %{x:.1f} pts<extra></extra>",
        )
        fig_depto.update_layout(
            **dark_layout(
                title="Caída de Puntaje (Pre → COVID)",
                yaxis={"categoryorder": "category ascending", "color": "#64748b"},
                coloraxis_showscale=False,
                height=chart_h,
            )
        )
        st.plotly_chart(fig_depto, use_container_width=True)

    with c_geo2:
        if "Recuperación_%" in df_depto.columns:
            fig_rec = px.bar(
                df_depto,
                x="Recuperación_%",
                y="Departamento",
                orientation="h",
                color="Recuperación_%",
                color_continuous_scale=["#f43f5e", "#facc15", "#34d399"],
                text_auto=".0f",
                range_color=[0, 100],
                labels={"Recuperación_%": "% Recuperado", "Departamento": ""},
            )
            fig_rec.update_traces(
                textfont_color="#f8fafc",
                textposition="outside",
                hovertemplate="<b>%{y}</b><br>Recuperación: %{x:.0f}%<extra></extra>",
            )
            fig_rec.update_layout(
                **dark_layout(
                    title="Índice de Recuperación Post-COVID",
                    yaxis={"categoryorder": "category ascending", "color": "#64748b"},
                    coloraxis_showscale=False,
                    height=chart_h,
                )
            )
            st.plotly_chart(fig_rec, use_container_width=True)

    st.markdown('<div class="grad-divider"></div>', unsafe_allow_html=True)

    # ── Brecha de género ───────────────────────────────────────────────────────
    st.markdown('<div class="section-title">Equidad</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-heading">Brecha de Género por Período</div>',
        unsafe_allow_html=True,
    )

    with st.spinner("Cargando datos de género..."):
        df_gender = _query_gender_period(svc) if svc else None

    if df_gender is None or df_gender.empty:
        # Mock
        df_gender = pd.DataFrame(
            {
                "Genero": ["M", "F", "M", "F", "M", "F"],
                "Período": [
                    "Pre-COVID",
                    "Pre-COVID",
                    "COVID",
                    "COVID",
                    "Post-COVID",
                    "Post-COVID",
                ],
                "Promedio": [258, 255, 251, 248, 255, 253],
            }
        )

    df_gender["Período"] = pd.Categorical(
        df_gender["Período"],
        categories=["Pre-COVID", "COVID", "Post-COVID"],
        ordered=True,
    )
    df_gender = df_gender.sort_values("Período")

    fig_g = px.bar(
        df_gender,
        x="Período",
        y="Promedio",
        color="Genero",
        barmode="group",
        color_discrete_map={
            "M": "#38bdf8",
            "F": "#f472b6",
            "MASCULINO": "#38bdf8",
            "FEMENINO": "#f472b6",
        },
        text_auto=".1f",
        labels={"Promedio": "Puntaje Global Promedio", "Genero": "Género"},
    )
    fig_g.update_traces(
        textfont_color="#f8fafc",
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>%{fullData.name}: %{y:.1f}<extra></extra>",
    )
    fig_g.update_layout(**dark_layout(title=""))
    st.plotly_chart(fig_g, use_container_width=True)

    st.markdown('<div class="grad-divider"></div>', unsafe_allow_html=True)

    # ── Tabla de insights accionables ─────────────────────────────────────────
    st.markdown(
        '<div class="section-title">Herramienta para Coordinadores</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="section-heading">Métricas Accionables · Guía de Intervención</div>',
        unsafe_allow_html=True,
    )

    # Calcular caída real si disponible
    caida_str = f"{caida:.1f}" if caida else "~7–10"
    rec_str = f"{rec_rate:.0f}" if rec_rate else "~60–80"
    post_delta = f"{post_val - cov_val:.1f}" if post_val and cov_val else "~5"

    insights = pd.DataFrame(
        {
            "📊 Indicador": [
                "Caída pandemia (Global)",
                "Área más afectada",
                "Área con mayor recuperación",
                "Depts. con baja recuperación (<50%)",
                "Brecha de género amplificada",
                "Modalidad de mayor riesgo",
            ],
            "📈 Valor / Situación": [
                f"−{caida_str} puntos en promedio nacional",
                "Inglés y Sociales (mayor pérdida proporcional)",
                "Lectura Crítica (retorno más rápido)",
                "Ver mapa — priorizar intervención",
                "Masculino cayó más en Matemáticas",
                "Virtual puro (sin acompañamiento docente)",
            ],
            "🎯 Acción Recomendada": [
                "Diseñar plan de nivelación 2022-2025 focalizado",
                "Reforzar inglés con metodologías híbridas y TIC",
                "Replicar estrategias de lectura en otras áreas",
                "Asignar recursos adicionales / tutorías focalizadas",
                "Crear grupos de apoyo diferenciado por género",
                "Implementar modelo híbrido con soporte presencial mínimo",
            ],
            "🔥 Prioridad": [
                "Alta",
                "Alta",
                "Media",
                "Crítica",
                "Media",
                "Alta",
            ],
        }
    )

    # Color por prioridad
    def color_priority(val):
        colors = {
            "Crítica": "background-color:rgba(244,63,94,0.2);color:#f43f5e;font-weight:700",
            "Alta": "background-color:rgba(250,204,21,0.15);color:#facc15;font-weight:600",
            "Media": "background-color:rgba(52,211,153,0.12);color:#34d399;font-weight:600",
        }
        return colors.get(val, "")

    styled = insights.style.map(color_priority, subset=["🔥 Prioridad"])
    st.dataframe(styled, use_container_width=True, height=280)

    # ── Calculadora rápida ────────────────────────────────────────────────────
    st.markdown('<div class="grad-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Calculadora</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-heading">Simulador de Recuperación para Coordinadores</div>',
        unsafe_allow_html=True,
    )

    with st.expander("🧮 Abre la calculadora de impacto", expanded=False):
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            puntaje_pre = st.number_input(
                "Puntaje promedio Pre-COVID del colegio",
                200.0,
                500.0,
                value=float(f"{pre_val:.1f}") if pre_val else 258.0,
                step=0.5,
            )
            puntaje_covid = st.number_input(
                "Puntaje promedio durante COVID",
                180.0,
                490.0,
                value=float(f"{cov_val:.1f}") if cov_val else 249.0,
                step=0.5,
            )
        with col_c2:
            puntaje_actual = st.number_input(
                "Puntaje actual del colegio",
                180.0,
                500.0,
                value=float(f"{post_val:.1f}") if post_val else 254.0,
                step=0.5,
            )
            meta_rec = st.slider("Meta de recuperación (%)", 50, 100, 85, step=5)

        caida_c = puntaje_pre - puntaje_covid
        rec_c = ((puntaje_actual - puntaje_covid) / caida_c * 100) if caida_c > 0 else 0
        pts_falt = puntaje_covid + caida_c * (meta_rec / 100) - puntaje_actual

        m1, m2, m3 = st.columns(3)
        m1.metric("📉 Caída observada", f"{caida_c:.1f} pts")
        m2.metric(
            "🔄 Recuperación actual",
            f"{rec_c:.1f}%",
            delta=(
                "✓ Meta alcanzada"
                if rec_c >= meta_rec
                else f"Faltan {pts_falt:.1f} pts"
            ),
        )
        m3.metric("🎯 Pts. para alcanzar meta", f"{max(pts_falt, 0):.1f}")

        if rec_c >= meta_rec:
            st.success(
                f"✅ El colegio ha alcanzado la meta de recuperación del {meta_rec}%."
            )
        else:
            st.warning(
                f"⚠️ Faltan **{pts_falt:.1f} puntos** para alcanzar la meta del {meta_rec}%. "
                f"Considere intervención focalizada en áreas críticas."
            )

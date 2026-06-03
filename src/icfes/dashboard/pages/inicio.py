import plotly.express as px
import streamlit as st

from icfes.dashboard.components.theme import dark_layout


def render(svc):
    st.markdown("<br>", unsafe_allow_html=True)
    left, right = st.columns([3, 2], gap="large")

    with left:
        st.markdown(
            '<div class="hero-badge">Analítica Educativa · Colombia</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="hero-title">Explorador ICFES<br>Saber 11</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="hero-sub">Plataforma de análisis interactivo sobre el rendimiento académico '
            "colombiano. Navega 10 años de microdatos con DuckDB a velocidad in-memory.</div>",
            unsafe_allow_html=True,
        )
        st.markdown("<br>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        c1.metric("📁 Datasets", "22 períodos")
        c2.metric("👥 Registros", "~4.8 M")
        c3.metric("📅 Cobertura", "2015–2025")

    with right:
        try:
            df_h = svc.query_df(
                """
                SELECT ano, AVG(CAST(punt_global AS DOUBLE)) AS Global
                FROM {parquet}
                GROUP BY ano ORDER BY ano
                """
            )
        except Exception:
            df_h = None

        if df_h is not None and not df_h.empty:
            fig_hero = px.line(
                df_h,
                x="ano",
                y="Global",
                color_discrete_sequence=["#38bdf8"],
                markers=True,
            )
            fig_hero.update_traces(
                line_width=3,
                marker_size=8,
                hovertemplate="<b>%{x}</b><br>Promedio Global: %{y:.1f}<extra></extra>",
            )
            fig_hero.update_layout(
                **dark_layout(
                    title="Evolución Puntaje Global · Todos los períodos",
                    margin=dict(l=0, r=0, t=40, b=0),
                )
            )
            st.plotly_chart(fig_hero, use_container_width=True)
        else:
            st.info("Sin datos disponibles para el gráfico de tendencia.")

    st.markdown('<div class="grad-divider"></div>', unsafe_allow_html=True)

    st.markdown("#### 🚀 Qué puedes explorar")
    f1, f2, f3, f4 = st.columns(4)
    for col, icon, title, desc in [
        (
            f1,
            "📊",
            "Análisis",
            "KPIs en tiempo real, tendencias y distribución geográfica con tus datos reales.",
        ),
        (
            f2,
            "⚖️",
            "Comparativa",
            "Contrasta el rendimiento entre géneros y áreas de conocimiento.",
        ),
        (
            f3,
            "📈",
            "Tendencias",
            "Explora proyecciones y patrones históricos a lo largo del tiempo.",
        ),
        (
            f4,
            "⚙️",
            "Filtros",
            "Filtra por año, departamento, género y tipo de colegio desde la barra lateral.",
        ),
    ]:
        with col:
            st.markdown(
                f'<div class="section-card"><div style="font-size:2rem;margin-bottom:10px">{icon}</div>'
                f'<div style="font-weight:700;color:#f8fafc;margin-bottom:6px">{title}</div>'
                f'<div style="color:#64748b;font-size:0.88rem">{desc}</div></div>',
                unsafe_allow_html=True,
            )

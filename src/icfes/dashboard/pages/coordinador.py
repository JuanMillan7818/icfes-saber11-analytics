"""
HU 1 · Tablero del Coordinador
Análisis de brechas por materia e impacto socioeconómico de una institución
frente al promedio municipal / departamental.
"""

from __future__ import annotations

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from icfes.dashboard.components.theme import dark_layout


MATERIAS = {
    "punt_matematicas": "Matemáticas",
    "punt_lectura_critica": "Lectura Crítica",
    "punt_c_naturales": "Ciencias",
    "punt_sociales_ciudadanas": "Sociales",
    "punt_ingles": "Inglés",
    "punt_global": "Global",
}


@st.cache_data(ttl=600, show_spinner=False)
def _load_instituciones(_svc):
    try:
        df = _svc.query_df(
            """
            SELECT DISTINCT trim(cole_nombre_establecimiento) AS cole_nombre_establecimiento, cole_depto_ubicacion, cole_mcpio_ubicacion
            FROM {parquet}
            WHERE cole_nombre_establecimiento IS NOT NULL AND trim(cole_nombre_establecimiento) != ''
            ORDER BY trim(cole_nombre_establecimiento)
            """
        )
        return df
    except Exception:
        return None


@st.cache_data(ttl=600, show_spinner=False)
def _brecha_materias(_svc, institucion: str, municipio: str):
    avgs_col = ", ".join(
        f"AVG(CASE WHEN isnan(TRY_CAST({col} AS DOUBLE)) THEN NULL"
        f" ELSE TRY_CAST({col} AS DOUBLE) END) AS {col}"
        for col in MATERIAS
    )
    try:
        df_cole = _svc.query_df(
            f"""
            SELECT {avgs_col}
            FROM {{parquet}}
            WHERE cole_nombre_establecimiento = '{institucion}'
              AND cole_mcpio_ubicacion = '{municipio}'
            """
        )
        df_ref = _svc.query_df(
            f"""
            SELECT {avgs_col}
            FROM {{parquet}}
            """
        )
        return df_cole, df_ref
    except Exception:
        return None, None


@st.cache_data(ttl=600, show_spinner=False)
def _impacto_internet(_svc, institucion: str, municipio: str):
    try:
        df = _svc.query_df(
            """
            SELECT fami_tieneinternet AS Internet,
                   AVG(CAST(punt_global AS DOUBLE)) AS Promedio,
                   COUNT(*) AS Estudiantes
            FROM {parquet}
            WHERE fami_tieneinternet IS NOT NULL
            GROUP BY fami_tieneinternet
            """
        )
        df_cole = _svc.query_df(
            f"""
            SELECT fami_tieneinternet AS Internet,
                   AVG(CAST(punt_global AS DOUBLE)) AS Promedio,
                   COUNT(*) AS Estudiantes
            FROM {{parquet}}
            WHERE fami_tieneinternet IS NOT NULL
              AND cole_nombre_establecimiento = '{institucion}'
              AND cole_mcpio_ubicacion = '{municipio}'
            GROUP BY fami_tieneinternet
            """
        )
        return df, df_cole
    except Exception:
        return None, None


@st.cache_data(ttl=600, show_spinner=False)
def _impacto_trabajo(_svc, institucion: str):
    """Disponible solo desde 2017."""
    try:
        df = _svc.query_df(
            """
            SELECT estu_horassemanatrabaja AS HorasTrabajo,
                   AVG(CAST(punt_global AS DOUBLE)) AS Promedio,
                   COUNT(*) AS Estudiantes
            FROM {parquet}
            WHERE estu_horassemanatrabaja IS NOT NULL
              AND ano >= '2017'
            GROUP BY estu_horassemanatrabaja
            ORDER BY HorasTrabajo
            """
        )
        return df if not df.empty else None
    except Exception:
        return None


def render(svc=None):
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        """
        <div class="hero-badge">🎓 Coordinador Académico</div>
        <div class="section-heading">Tablero de Brechas Institucionales</div>
        <div style="color:#64748b;font-size:0.9rem;margin-bottom:20px;">
            Compara tu institución frente al promedio departamental/nacional e identifica
            áreas de refuerzo presupuestal y socioeconómico.
        </div>
        """,
        unsafe_allow_html=True,
    )

    if svc is None:
        st.warning("⚠️ Servicio de datos no disponible.")
        return

    # ── Selector de institución ────────────────────────────────────────────────
    with st.spinner("Cargando instituciones..."):
        df_inst = _load_instituciones(svc)

    if df_inst is None or df_inst.empty:
        st.error("No se pudieron cargar las instituciones.")
        return

    df_inst["_label"] = (
        df_inst["cole_nombre_establecimiento"].str.strip()
        + " - "
        + df_inst["cole_mcpio_ubicacion"].str.strip().str.title()
    )
    label_map = df_inst.set_index("_label")

    col_sel, col_info = st.columns([3, 1])
    with col_sel:
        label_sel = st.selectbox(
            "🏫 Selecciona la institución",
            options=df_inst["_label"].tolist(),
            index=0,
        )

    row_inst = label_map.loc[label_sel]
    institucion = row_inst["cole_nombre_establecimiento"]
    municipio = row_inst["cole_mcpio_ubicacion"]
    with col_info:
        st.markdown(
            f"""
            <div class="section-card" style="padding:12px 16px;font-size:0.82rem;">
                <div style="color:#64748b;">Departamento</div>
                <div style="color:#f8fafc;font-weight:700;">{str(row_inst.get("cole_depto_ubicacion","—")).title()}</div>
                <div style="color:#64748b;margin-top:6px;">Municipio</div>
                <div style="color:#f8fafc;font-weight:700;">{str(row_inst.get("cole_mcpio_ubicacion","—")).title()}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown('<div class="grad-divider"></div>', unsafe_allow_html=True)

    # ── Brecha por materia ─────────────────────────────────────────────────────
    st.markdown("#### 📊 Brecha por Área de Conocimiento")
    st.caption("Diferencia en puntos entre la institución y el promedio nacional.")

    with st.spinner("Calculando brechas..."):
        df_cole, df_ref = _brecha_materias(svc, institucion, municipio)

    if (
        df_cole is not None
        and not df_cole.empty
        and df_ref is not None
        and not df_ref.empty
    ):
        import pandas as pd

        brechas = []
        for col, label in MATERIAS.items():
            val_cole = float(df_cole[col].iloc[0]) if col in df_cole else 0
            val_ref = float(df_ref[col].iloc[0]) if col in df_ref else 0
            brechas.append(
                {
                    "Área": label,
                    "Institución": round(val_cole, 1),
                    "Nacional": round(val_ref, 1),
                    "Brecha": round(val_cole - val_ref, 1),
                }
            )
        df_brecha = pd.DataFrame(brechas).sort_values("Brecha")

        col_b1, col_b2 = st.columns([3, 2], gap="large")
        with col_b1:
            fig_brecha = px.bar(
                df_brecha,
                x="Brecha",
                y="Área",
                orientation="h",
                color="Brecha",
                color_continuous_scale=["#f43f5e", "#facc15", "#34d399"],
                range_color=[
                    df_brecha["Brecha"].min() - 1,
                    df_brecha["Brecha"].max() + 1,
                ],
                text_auto=".1f",
                labels={"Brecha": "Diferencia (pts)", "Área": ""},
            )
            fig_brecha.add_vline(
                x=0, line_dash="dot", line_color="rgba(255,255,255,0.3)"
            )
            fig_brecha.update_traces(
                textfont_color="#f8fafc",
                textposition="outside",
                hovertemplate="<b>%{y}</b><br>Brecha: %{x:.1f} pts<extra></extra>",
            )
            fig_brecha.update_layout(
                **dark_layout(
                    title=f"Institución vs Nacional",
                    yaxis={"categoryorder": "total ascending", "title": ""},
                    coloraxis_showscale=False,
                )
            )
            st.plotly_chart(fig_brecha, use_container_width=True)

        with col_b2:
            st.markdown("##### 📋 Detalle")

            def color_brecha(val):
                if val > 0:
                    return "color:#34d399;font-weight:700"
                elif val < 0:
                    return "color:#f43f5e;font-weight:700"
                return ""

            styled = df_brecha[["Área", "Institución", "Nacional", "Brecha"]].style.map(
                color_brecha, subset=["Brecha"]
            )
            st.dataframe(styled, use_container_width=True, hide_index=True)
    else:
        st.info("Sin datos suficientes para la institución seleccionada.")

    st.markdown('<div class="grad-divider"></div>', unsafe_allow_html=True)

    # ── Impacto socioeconómico ─────────────────────────────────────────────────
    st.markdown("#### 🌐 Impacto del Entorno en el Rendimiento")

    c_soc1, c_soc2 = st.columns(2, gap="large")

    with c_soc1:
        st.markdown("##### 📡 Internet en el Hogar vs Puntaje Global")
        with st.spinner("Cargando impacto internet..."):
            df_inet_nac, df_inet_cole = _impacto_internet(svc, institucion, municipio)

        if df_inet_nac is not None and not df_inet_nac.empty:
            import pandas as pd

            df_inet_nac["Scope"] = "Nacional"
            if df_inet_cole is not None and not df_inet_cole.empty:
                df_inet_cole["Scope"] = "Institución"
                df_combined = pd.concat([df_inet_nac, df_inet_cole], ignore_index=True)
            else:
                df_combined = df_inet_nac

            fig_inet = px.bar(
                df_combined,
                x="Internet",
                y="Promedio",
                color="Scope",
                barmode="group",
                color_discrete_map={"Nacional": "#818cf8", "Institución": "#38bdf8"},
                text_auto=".1f",
                labels={
                    "Promedio": "Puntaje Global Promedio",
                    "Internet": "¿Tiene Internet?",
                },
            )
            fig_inet.update_traces(
                textfont_color="#f8fafc",
                textposition="outside",
                hovertemplate="<b>%{x}</b><br>%{fullData.name}: %{y:.1f}<extra></extra>",
            )
            fig_inet.update_layout(**dark_layout(title=""))
            st.plotly_chart(fig_inet, use_container_width=True)
        else:
            st.info("Sin datos de internet disponibles.")

    with c_soc2:
        st.markdown("##### ⏰ Horas de Trabajo Semanal vs Puntaje (desde 2017)")
        with st.spinner("Cargando impacto trabajo..."):
            df_trab = _impacto_trabajo(svc, institucion)

        if df_trab is not None and not df_trab.empty:
            fig_trab = px.bar(
                df_trab,
                x="HorasTrabajo",
                y="Promedio",
                color="Promedio",
                color_continuous_scale=["#f43f5e", "#facc15", "#34d399"],
                text_auto=".1f",
                labels={
                    "HorasTrabajo": "Horas/semana trabajo",
                    "Promedio": "Puntaje Global Promedio",
                },
                hover_data={"Estudiantes": True},
            )
            fig_trab.update_traces(
                textfont_color="#f8fafc",
                textposition="outside",
                hovertemplate="<b>%{x}</b><br>Promedio: %{y:.1f}<br>Estudiantes: %{customdata[0]:,}<extra></extra>",
            )
            fig_trab.update_layout(**dark_layout(title="", coloraxis_showscale=False))
            st.plotly_chart(fig_trab, use_container_width=True)
        else:
            st.info("Sin datos de horas de trabajo (columna disponible desde 2017).")

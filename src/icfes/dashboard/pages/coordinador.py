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
        # DISTINCT ON → nombre más reciente por código DANE
        df = _svc.query_df(
            """
            SELECT DISTINCT ON (cole_cod_dane_establecimiento)
                cole_cod_dane_establecimiento AS cod_dane,
                trim(cole_nombre_establecimiento)  AS cole_nombre_establecimiento,
                cole_depto_ubicacion,
                cole_mcpio_ubicacion
            FROM {parquet}
            WHERE cole_cod_dane_establecimiento IS NOT NULL
              AND cole_nombre_establecimiento   IS NOT NULL
              AND trim(cole_nombre_establecimiento) != ''
            ORDER BY cole_cod_dane_establecimiento, ano DESC
            """
        )
        return df
    except Exception:
        return None


@st.cache_data(ttl=600, show_spinner=False)
def _brecha_materias(_svc, cod_dane: str):
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
            WHERE cole_cod_dane_establecimiento = '{cod_dane}'
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


def _avgs_materias() -> str:
    return ", ".join(
        f"AVG(CASE WHEN isnan(TRY_CAST({col} AS DOUBLE)) THEN NULL"
        f' ELSE TRY_CAST({col} AS DOUBLE) END) AS "{label}"'
        for col, label in MATERIAS.items()
    )


@st.cache_data(ttl=600, show_spinner=False)
def _impacto_internet(_svc, cod_dane: str):
    avgs = _avgs_materias()
    try:
        df_cole = _svc.query_df(
            f"""
            SELECT
                CASE
                    WHEN fami_tieneinternet IS NULL OR trim(fami_tieneinternet) = ''
                    THEN 'Dato desconocido'
                    ELSE trim(fami_tieneinternet)
                END AS Internet,
                {avgs}
            FROM {{parquet}}
            WHERE cole_cod_dane_establecimiento = '{cod_dane}'
            GROUP BY Internet
            """
        )
        return df_cole
    except Exception:
        return None


@st.cache_data(ttl=600, show_spinner=False)
def _impacto_trabajo(_svc, cod_dane: str):
    """Disponible solo desde 2017. Filtrado por código DANE."""
    try:
        df = _svc.query_df(
            f"""
            SELECT estu_horassemanatrabaja AS HorasTrabajo,
                   AVG(CAST(punt_global AS DOUBLE)) AS Promedio,
                   COUNT(*) AS Estudiantes
            FROM {{parquet}}
            WHERE estu_horassemanatrabaja IS NOT NULL
              AND trim(estu_horassemanatrabaja) != ''
              AND ano >= '2017'
              AND cole_cod_dane_establecimiento = '{cod_dane}'
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
    cod_dane = str(row_inst["cod_dane"])
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
        df_cole, df_ref = _brecha_materias(svc, cod_dane)

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

        # Diverging bar: rojo izquierda (negativo) · verde derecha (positivo)
        max_abs = max(abs(df_brecha["Brecha"].max()), abs(df_brecha["Brecha"].min()), 1)
        x_range = [-max_abs * 1.35, max_abs * 1.35]

        fig_brecha = go.Figure()

        # Zona de fondo: izquierda = rojo suave, derecha = verde suave
        fig_brecha.add_shape(type="rect", xref="x", yref="paper",
            x0=x_range[0], x1=0, y0=0, y1=1,
            fillcolor="rgba(244,63,94,0.05)", line_width=0, layer="below")
        fig_brecha.add_shape(type="rect", xref="x", yref="paper",
            x0=0, x1=x_range[1], y0=0, y1=1,
            fillcolor="rgba(52,211,153,0.05)", line_width=0, layer="below")

        # Barras por área
        for _, row in df_brecha.iterrows():
            b = row["Brecha"]
            color = "#34d399" if b >= 0 else "#f43f5e"
            fig_brecha.add_trace(go.Bar(
                x=[b],
                y=[row["Área"]],
                orientation="h",
                marker_color=color,
                marker_line_width=0,
                showlegend=False,
                hovertemplate=(
                    f"<b>{row['Área']}</b><br>"
                    f"Institución: {row['Institución']:.1f}<br>"
                    f"Nacional: {row['Nacional']:.1f}<br>"
                    f"Diferencia: {b:+.1f} pts<extra></extra>"
                ),
            ))

        # Etiquetas con valor + score institución
        for _, row in df_brecha.iterrows():
            b = row["Brecha"]
            fig_brecha.add_annotation(
                x=b + (max_abs * 0.06 if b >= 0 else -max_abs * 0.06),
                y=row["Área"],
                text=f"<b>{b:+.1f}</b>  ({row['Institución']:.0f})",
                showarrow=False,
                font=dict(color="#f8fafc", size=11),
                xanchor="left" if b >= 0 else "right",
            )

        # Línea central + etiquetas de zona
        fig_brecha.add_vline(x=0, line_width=2, line_color="rgba(255,255,255,0.35)")
        fig_brecha.add_annotation(x=0, y=1.07, yref="paper",
            text="Promedio Nacional", showarrow=False,
            font=dict(color="#94a3b8", size=11), xanchor="center")
        fig_brecha.add_annotation(x=x_range[0] * 0.6, y=1.07, yref="paper",
            text="← Por mejorar", showarrow=False,
            font=dict(color="#f87171", size=11), xanchor="center")
        fig_brecha.add_annotation(x=x_range[1] * 0.6, y=1.07, yref="paper",
            text="Sobre el nacional →", showarrow=False,
            font=dict(color="#34d399", size=11), xanchor="center")

        fig_brecha.update_layout(**dark_layout(
            title="",
            xaxis=dict(range=x_range, title="Diferencia vs promedio nacional (pts)",
                       zeroline=False, showgrid=False),
            yaxis=dict(categoryorder="total ascending", title=""),
            barmode="relative",
        ))
        fig_brecha.update_layout(height=320, margin=dict(t=40, l=10, r=10, b=40))

        st.plotly_chart(fig_brecha, use_container_width=True)

        # Detalle numérico en expander
        with st.expander("📋 Ver detalle numérico"):
            def _color_brecha(val):
                if val > 0:  return "color:#34d399;font-weight:700"
                if val < 0:  return "color:#f43f5e;font-weight:700"
                return ""
            styled = df_brecha[["Área", "Institución", "Nacional", "Brecha"]].style.map(
                _color_brecha, subset=["Brecha"]
            )
            st.dataframe(styled, use_container_width=True, hide_index=True)
    else:
        st.info("Sin datos suficientes para la institución seleccionada.")

    st.markdown('<div class="grad-divider"></div>', unsafe_allow_html=True)

    # ── Impacto socioeconómico ─────────────────────────────────────────────────
    st.markdown("#### 🌐 Impacto del Entorno en el Rendimiento")

    c_soc1, c_soc2 = st.columns(2, gap="large")

    import pandas as pd

    area_cols = list(MATERIAS.values())

    with c_soc1:
        st.markdown("##### 📡 Internet en el Hogar vs Puntaje por Área")
        with st.spinner("Cargando impacto internet..."):
            df_inet_cole = _impacto_internet(svc, cod_dane)

        if df_inet_cole is not None and not df_inet_cole.empty:
            df_long = df_inet_cole.melt(
                id_vars=["Internet"],
                value_vars=area_cols,
                var_name="Área",
                value_name="Promedio",
            ).dropna(subset=["Promedio"])

            df_long["Internet"] = (
                df_long["Internet"]
                .map(
                    {
                        "Si": "Con Internet",
                        "No": "Sin Internet",
                        "Dato desconocido": "Dato desconocido",
                    }
                )
                .fillna(df_long["Internet"])
            )

            fig_inet = px.bar(
                df_long,
                x="Área",
                y="Promedio",
                color="Internet",
                barmode="group",
                color_discrete_map={
                    "Con Internet": "#34d399",
                    "Sin Internet": "#f87171",
                    "Dato desconocido": "#94a3b8",
                },
                text_auto=".1f",
                labels={"Promedio": "Puntaje Promedio", "Área": "", "Internet": ""},
            )
            fig_inet.update_traces(
                textfont_color="#f8fafc",
                textposition="outside",
                hovertemplate="<b>%{x}</b><br>%{fullData.name}: %{y:.1f}<extra></extra>",
            )
            fig_inet.update_layout(
                **dark_layout(
                    title="",
                    legend=dict(
                        title="",
                        orientation="h",
                        yanchor="bottom",
                        y=1.02,
                        bgcolor="rgba(0,0,0,0)",
                    ),
                )
            )
            st.plotly_chart(fig_inet, use_container_width=True)
        else:
            st.info("Sin datos de internet disponibles.")

    with c_soc2:
        st.markdown("##### ⏰ Horas de Trabajo Semanal vs Puntaje Global")
        with st.spinner("Cargando impacto trabajo..."):
            df_trab = _impacto_trabajo(svc, cod_dane)

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

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from icfes.dashboard.components.theme import dark_layout

AREAS_SQL = {
    "punt_global": "Global",
    "punt_matematicas": "Matemáticas",
    "punt_lectura_critica": "Lectura Crítica",
    "punt_c_naturales": "Ciencias",
    "punt_sociales_ciudadanas": "Sociales",
    "punt_ingles": "Inglés",
}


def _avgs_sql() -> str:
    return ", ".join(
        f"AVG(CAST({col} AS DOUBLE)) AS {alias.replace(' ', '_').replace('í', 'i').replace('é', 'e').replace('á', 'a')}"
        for col, alias in AREAS_SQL.items()
    )


def render(svc=None):
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        '<div class="section-heading">Comparativa · Equidad Educativa</div>',
        unsafe_allow_html=True,
    )

    # ── Género por área ────────────────────────────────────────────────────────
    st.markdown("#### 👤 Género por Área de Conocimiento")
    try:
        avgs = ", ".join(f"AVG(CAST({col} AS DOUBLE)) AS {col}" for col in AREAS_SQL)
        df_gen = (
            svc.query_df(
                f"""
            SELECT estu_genero AS Genero, {avgs}
            FROM {{parquet}}
            WHERE estu_genero IS NOT NULL
            AND isnan(punt_ingles) = false AND estu_genero != ''
            GROUP BY estu_genero
            """
            )
            if svc
            else None
        )
    except Exception:
        df_gen = None

    if df_gen is not None and not df_gen.empty:
        fig_gender = go.Figure()
        color_map = {
            "M": "#38bdf8",
            "F": "#f472b6",
            "MASCULINO": "#38bdf8",
            "FEMENINO": "#f472b6",
        }
        labels = list(AREAS_SQL.values())
        for _, row in df_gen.iterrows():
            genero = str(row["Genero"])
            vals = [float(row[c]) for c in AREAS_SQL]
            fig_gender.add_trace(
                go.Bar(
                    name=genero,
                    x=labels,
                    y=vals,
                    marker_color=color_map.get(genero.upper(), "#94a3b8"),
                    opacity=0.85,
                    hovertemplate=f"<b>{genero}</b><br>%{{x}}: %{{y:.1f}}<extra></extra>",
                )
            )
        fig_gender.update_layout(
            **dark_layout(barmode="group", title="Puntaje Promedio por Área y Género")
        )
        st.plotly_chart(fig_gender, use_container_width=True)
    else:
        st.info("Sin datos de género disponibles.")

    st.markdown('<div class="grad-divider"></div>', unsafe_allow_html=True)

    # ── Oficial vs No Oficial ──────────────────────────────────────────────────
    left2, right2 = st.columns(2, gap="large")

    with left2:
        st.markdown("#### 🏫 Oficial vs No Oficial")
        try:
            avgs2 = ", ".join(
                f"AVG(CAST({col} AS DOUBLE)) AS {col}" for col in AREAS_SQL
            )
            df_nat = (
                svc.query_df(
                    f"""
                SELECT cole_naturaleza AS Tipo, {avgs2}
                FROM {{parquet}}
                WHERE cole_naturaleza IS NOT NULL
                AND isnan(punt_ingles) = false AND cole_naturaleza != ''
                GROUP BY cole_naturaleza
                """
                )
                if svc
                else None
            )
        except Exception:
            df_nat = None

        if df_nat is not None and not df_nat.empty:
            records = []
            for _, row in df_nat.iterrows():
                for col, label in AREAS_SQL.items():
                    records.append(
                        {
                            "Tipo": str(row["Tipo"]),
                            "Área": label,
                            "Puntaje": float(row[col]),
                        }
                    )
            import pandas as pd

            df_nat_long = pd.DataFrame(records)
            fig_nat = px.bar(
                df_nat_long,
                x="Área",
                y="Puntaje",
                color="Tipo",
                barmode="group",
                color_discrete_map={"OFICIAL": "#818cf8", "NO OFICIAL": "#34d399"},
            )
            fig_nat.update_layout(**dark_layout(title=""))
            st.plotly_chart(fig_nat, use_container_width=True)
        else:
            st.info("Sin datos de naturaleza de colegio.")

    # ── Urbano vs Rural ────────────────────────────────────────────────────────
    with right2:
        st.markdown("#### 🌐 Área Urbana vs Rural")
        try:
            avgs3 = ", ".join(
                f"AVG(CAST({col} AS DOUBLE)) AS {col}" for col in AREAS_SQL
            )
            df_area = (
                svc.query_df(
                    f"""
                SELECT cole_area_ubicacion AS Area, {avgs3}
                FROM {{parquet}}
                WHERE cole_area_ubicacion IS NOT NULL
                AND isnan(punt_ingles) = false AND cole_area_ubicacion != ''
                GROUP BY cole_area_ubicacion
                """
                )
                if svc
                else None
            )
        except Exception:
            df_area = None

        if df_area is not None and not df_area.empty:
            cats = list(AREAS_SQL.values())
            fig_ur = go.Figure()
            color_area = {"URBANO": "#38bdf8", "RURAL": "#f87171"}
            for _, row in df_area.iterrows():
                area_label = str(row["Area"])
                vals = [float(row[c]) for c in AREAS_SQL]
                fig_ur.add_trace(
                    go.Scatter(
                        x=cats,
                        y=vals,
                        name=area_label,
                        fill="tozeroy",
                        fillcolor=f"rgba({'56,189,248' if 'URB' in area_label.upper() else '248,113,113'},0.1)",
                        line=dict(
                            color=color_area.get(area_label.upper(), "#94a3b8"),
                            width=2.5,
                        ),
                        hovertemplate=f"<b>{area_label}</b><br>%{{x}}: %{{y:.1f}}<extra></extra>",
                    )
                )
            fig_ur.update_layout(**dark_layout(title=""))
            st.plotly_chart(fig_ur, use_container_width=True)
        else:
            st.info("Sin datos de área de ubicación.")

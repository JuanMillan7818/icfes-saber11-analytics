import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from icfes.dashboard.components.theme import dark_layout


def render(
    svc, where_clause: str, sel_anos, sel_deptos, sel_genero, sel_naturaleza: str
):
    st.markdown("<br>", unsafe_allow_html=True)

    if where_clause:
        chips = " · ".join(
            ([f"Años: {', '.join([str(a) for a in sel_anos])}"] if sel_anos else [])
            + ([f"Deptos: {len(sel_deptos)}"] if sel_deptos else [])
            + ([f"Género: {', '.join(sel_genero)}"] if sel_genero else [])
            + ([f"Naturaleza: {sel_naturaleza}"] if sel_naturaleza != "Todas" else [])
        )
        st.markdown(
            f'<div class="info-chip">🔍 Filtros activos: {chips}</div>',
            unsafe_allow_html=True,
        )

    # KPIs
    with st.spinner("Calculando métricas..."):
        try:
            df_kpi = svc.query_df(
                f"""
                SELECT COUNT(*) AS total,
                    AVG(CAST(punt_global AS DOUBLE)) AS prom_global,
                    AVG(CAST(punt_matematicas AS DOUBLE)) AS prom_math,
                    AVG(CAST(punt_lectura_critica AS DOUBLE)) AS prom_lectura
                FROM {{parquet}} {where_clause}
            """
            )
            total_e = int(df_kpi["total"].iloc[0]) if not df_kpi.empty else 0
            prom_g = float(df_kpi["prom_global"].iloc[0]) if not df_kpi.empty else 0
            prom_m = float(df_kpi["prom_math"].iloc[0]) if not df_kpi.empty else 0
            prom_l = float(df_kpi["prom_lectura"].iloc[0]) if not df_kpi.empty else 0
        except Exception:
            total_e = prom_g = prom_m = prom_l = 0

        try:
            df_top = svc.query_df(
                f"""
                SELECT cole_depto_ubicacion, AVG(CAST(punt_global AS DOUBLE)) AS p
                FROM {{parquet}} {where_clause}
                GROUP BY cole_depto_ubicacion ORDER BY p DESC LIMIT 1
            """
            )
            top_d = (
                str(df_top["cole_depto_ubicacion"].iloc[0]).title()
                if not df_top.empty
                else "N/A"
            )
        except Exception:
            top_d = "N/A"

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("👥 Estudiantes", f"{total_e:,}".replace(",", "."))
    k2.metric("🎯 Prom. Global", f"{prom_g:.1f}" if prom_g else "N/A")
    k3.metric("📐 Matemáticas", f"{prom_m:.1f}" if prom_m else "N/A")
    k4.metric("📖 Lectura", f"{prom_l:.1f}" if prom_l else "N/A")
    k5.metric("🏆 Depto. Líder", top_d)

    st.markdown('<div class="grad-divider"></div>', unsafe_allow_html=True)

    # Charts row 1
    c1, c2 = st.columns([3, 2], gap="large")
    with c1:
        st.markdown(
            '<div class="section-title">Evolución temporal</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="section-heading">Tendencia del Puntaje Global</div>',
            unsafe_allow_html=True,
        )
        try:
            df_trend = svc.query_df(
                f"""
                SELECT ano, AVG(CAST(punt_global AS DOUBLE)) AS promedio
                FROM {{parquet}} {where_clause} GROUP BY ano ORDER BY ano
            """
            )
            if not df_trend.empty:
                fig = px.area(
                    df_trend,
                    x="ano",
                    y="promedio",
                    color_discrete_sequence=["#38bdf8"],
                    markers=True,
                )
                fig.data[0].fill = "tozeroy"
                fig.data[0].fillcolor = "rgba(56,189,248,0.12)"
                fig.update_traces(
                    line_width=2.5,
                    marker_size=8,
                    hovertemplate="<b>%{x}</b><br>Promedio: %{y:.1f}<extra></extra>",
                )
                fig.update_layout(**dark_layout(title=""))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Sin datos para el filtro seleccionado.")
        except Exception as e:
            st.error(f"Error: {e}")

    with c2:
        st.markdown(
            '<div class="section-title">Competencias</div>', unsafe_allow_html=True
        )
        st.markdown(
            '<div class="section-heading">Radar por Área</div>', unsafe_allow_html=True
        )
        try:
            df_r = svc.query_df(
                f"""
                SELECT AVG(CAST(punt_matematicas AS DOUBLE)) AS mat,
                    AVG(CAST(punt_lectura_critica AS DOUBLE)) AS lec,
                    AVG(CAST(punt_c_naturales AS DOUBLE)) AS cie,
                    AVG(CAST(punt_sociales_ciudadanas AS DOUBLE)) AS soc,
                    AVG(CASE WHEN punt_ingles IS NULL OR isnan(CAST(punt_ingles AS DOUBLE)) THEN 0.0 ELSE CAST(punt_ingles AS DOUBLE) END) AS ing
                FROM {{parquet}} {where_clause}
            """
            )
            if not df_r.empty:
                labels = ["Matemáticas", "Lectura", "Ciencias", "Sociales", "Inglés"]
                vals = df_r.iloc[0].values.tolist()
                vals_c = vals + [vals[0]]
                labels_c = labels + [labels[0]]
                fig_r = go.Figure(
                    go.Scatterpolar(
                        r=vals_c,
                        theta=labels_c,
                        fill="toself",
                        fillcolor="rgba(129,140,248,0.2)",
                        line=dict(color="#818cf8", width=2.5),
                        hovertemplate="<b>%{theta}</b><br>%{r:.1f}<extra></extra>",
                    )
                )
                fig_r.update_layout(
                    polar=dict(
                        bgcolor="rgba(0,0,0,0)",
                        radialaxis=dict(
                            visible=True,
                            range=[0, max(vals) + 8],
                            gridcolor="rgba(255,255,255,0.08)",
                            tickfont=dict(color="#64748b"),
                        ),
                        angularaxis=dict(
                            gridcolor="rgba(255,255,255,0.08)",
                            tickfont=dict(color="#94a3b8"),
                        ),
                    ),
                    showlegend=False,
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    font_color="#f8fafc",
                    margin=dict(l=30, r=30, t=30, b=30),
                )
                st.plotly_chart(fig_r, use_container_width=True)
        except Exception as e:
            st.error(f"Error: {e}")

    st.markdown('<div class="grad-divider"></div>', unsafe_allow_html=True)

    # Charts row 2
    st.markdown(
        '<div class="section-title">Distribución geográfica</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="section-heading">Top 10 Departamentos · Promedio Global</div>',
        unsafe_allow_html=True,
    )
    try:
        df_geo = svc.query_df(
            f"""
            SELECT cole_depto_ubicacion AS Departamento,
                   AVG(CAST(punt_global AS DOUBLE)) AS Promedio,
                   COUNT(*) AS Estudiantes
            FROM {{parquet}} {where_clause}
            GROUP BY cole_depto_ubicacion ORDER BY Promedio DESC LIMIT 10
        """
        )
        if not df_geo.empty:
            fig_b = px.bar(
                df_geo,
                x="Promedio",
                y="Departamento",
                orientation="h",
                color="Promedio",
                color_continuous_scale=["#1e3a5f", "#38bdf8"],
                hover_data={"Estudiantes": True},
                text_auto=".1f",
            )
            fig_b.update_layout(**dark_layout(margin=dict(l=0, r=0, t=10, b=0)))

            # 2. Sobrescribe/Actualiza específicamente el yaxis y xaxis
            fig_b.update_layout(
                yaxis={"categoryorder": "total ascending", "title": ""},
                xaxis=dict(showgrid=False, title="Promedio Global"),
                coloraxis_showscale=False,
            )

            fig_b.update_traces(
                textfont_color="#f8fafc",
                textposition="outside",
                hovertemplate="<b>%{y}</b><br>Promedio: %{x:.1f}<br>Estudiantes: %{customdata[0]:,}<extra></extra>",
            )
            st.plotly_chart(fig_b, use_container_width=True)
        else:
            st.info("Sin datos disponibles.")
    except Exception as e:
        st.error(f"Error: {e}")

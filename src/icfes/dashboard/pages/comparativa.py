import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from icfes.dashboard.components.theme import dark_layout
from icfes.dashboard.data.mock import mock_gender_data


def render():
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        '<div class="info-chip">⚠️ Datos ilustrativos · mock data</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="section-heading">Comparativa por Género y Área</div>',
        unsafe_allow_html=True,
    )

    df_g = mock_gender_data()
    fig_gender = go.Figure()
    for col, color in [("Masculino", "#38bdf8"), ("Femenino", "#f472b6")]:
        fig_gender.add_trace(
            go.Bar(
                name=col, x=df_g["Área"], y=df_g[col],
                marker_color=color, opacity=0.85,
                hovertemplate=f"<b>{col}</b><br>%{{x}}: %{{y:.1f}}<extra></extra>",
            )
        )
    fig_gender.update_layout(
        **dark_layout(barmode="group", title="Puntaje Promedio por Área y Género")
    )
    st.plotly_chart(fig_gender, use_container_width=True)

    st.markdown('<div class="grad-divider"></div>', unsafe_allow_html=True)

    left2, right2 = st.columns(2, gap="large")
    with left2:
        st.markdown("#### 🏫 Oficial vs No Oficial (mock)")
        df_nat = pd.DataFrame(
            {
                "Tipo": ["OFICIAL"] * 5 + ["NO OFICIAL"] * 5,
                "Área": ["Global", "Matemáticas", "Lectura", "Ciencias", "Inglés"] * 2,
                "Puntaje": [248, 46, 50, 47, 43, 272, 53, 55, 52, 51],
            }
        )
        fig_nat = px.bar(
            df_nat, x="Área", y="Puntaje", color="Tipo", barmode="group",
            color_discrete_map={"OFICIAL": "#818cf8", "NO OFICIAL": "#34d399"},
        )
        fig_nat.update_layout(**dark_layout(title=""))
        st.plotly_chart(fig_nat, use_container_width=True)

    with right2:
        st.markdown("#### 🌐 Área Urbana vs Rural (mock)")
        cats = ["Global", "Matemáticas", "Lectura", "Ciencias", "Inglés"]
        fig_ur = go.Figure()
        fig_ur.add_trace(
            go.Scatter(
                x=cats, y=[260, 51, 53, 50, 47], name="Urbano",
                fill="tozeroy", fillcolor="rgba(56,189,248,0.1)",
                line=dict(color="#38bdf8", width=2.5),
            )
        )
        fig_ur.add_trace(
            go.Scatter(
                x=cats, y=[238, 44, 47, 44, 40], name="Rural",
                fill="tozeroy", fillcolor="rgba(248,113,113,0.1)",
                line=dict(color="#f87171", width=2.5),
            )
        )
        fig_ur.update_layout(**dark_layout(title=""))
        st.plotly_chart(fig_ur, use_container_width=True)

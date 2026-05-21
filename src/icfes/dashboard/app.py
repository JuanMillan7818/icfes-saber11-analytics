import streamlit as st
from icfes.core.query_service import make_query_service

st.set_page_config(page_title="ICFES Saber 11", layout="wide")
st.title("Análisis ICFES Saber 11 — 2015 a 2025")


@st.cache_resource
def get_service():
    return make_query_service()


svc = get_service()

col1, col2 = st.columns(2)

with col1:
    st.subheader("Promedio global por año")
    df_global = svc.query_df("""
        SELECT
            ano,
            AVG(CAST(punt_global AS DOUBLE)) AS promedio_global,
            COUNT(*) AS total_estudiantes
        FROM {parquet}
        GROUP BY ano
        ORDER BY ano
    """)
    st.line_chart(df_global.set_index("ano")["promedio_global"])
    st.dataframe(df_global, use_container_width=True)

with col2:
    st.subheader("Puntajes por área")
    df_areas = svc.query_df("""
        SELECT
            ano,
            AVG(CAST(punt_matematicas AS DOUBLE))        AS matematicas,
            AVG(CAST(punt_lectura_critica AS DOUBLE))    AS lectura_critica,
            AVG(CAST(punt_c_naturales AS DOUBLE))        AS c_naturales,
            AVG(CAST(punt_sociales_ciudadanas AS DOUBLE)) AS sociales
        FROM {parquet}
        GROUP BY ano
        ORDER BY ano
    """)
    st.line_chart(df_areas.set_index("ano"))

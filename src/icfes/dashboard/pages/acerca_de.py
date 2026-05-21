import pandas as pd
import streamlit as st


def render():
    st.markdown("<br>", unsafe_allow_html=True)
    left_a, right_a = st.columns([2, 3], gap="large")

    with left_a:
        st.markdown(
            """
<div class="section-card">
    <div style="font-size:3rem;margin-bottom:12px">📊</div>
    <div class="section-heading">ICFES Saber 11<br>Analytics Platform</div>
    <div style="color:#64748b;font-size:0.9rem;line-height:1.6">
        Plataforma de análisis de microdatos educativos construida con arquitectura modular,
        orientada a soportar análisis local y escalabilidad hacia la nube (AWS S3 / Supabase).
    </div>
</div>
""",
            unsafe_allow_html=True,
        )

    with right_a:
        st.markdown("#### 🛠️ Stack Tecnológico")
        tech_data = {
            "Componente": [
                "Backend datos", "ETL / Normalización", "Dashboard",
                "Gráficos", "API (Fase 2)", "Paquetes",
            ],
            "Tecnología": [
                "DuckDB 1.1+", "Pandas + PyArrow", "Streamlit 1.40+",
                "Plotly 5.24+", "FastAPI + Uvicorn", "uv",
            ],
            "Propósito": [
                "Consultas OLAP in-memory sobre Parquet",
                "Procesamiento y validación de esquemas",
                "Interfaz web interactiva",
                "Visualizaciones dinámicas animadas",
                "REST API para frontend React/Next.js",
                "Gestor de paquetes ultrarrápido (Rust)",
            ],
        }
        st.dataframe(pd.DataFrame(tech_data), use_container_width=True, hide_index=True)

        st.markdown("#### 🗺️ Roadmap")
        roadmap = [
            ("✅", "ETL Pipeline", "Normalización de 22 archivos planos → Parquet"),
            ("✅", "Dashboard Streamlit", "Análisis local con DuckDB in-memory"),
            ("🚧", "API FastAPI", "Endpoints REST para consumo externo"),
            ("⬜", "Frontend React", "SPA con Next.js conectada a la API"),
            ("⬜", "Cloud Migration", "Migración Parquet a Supabase / S3"),
        ]
        for status, title, desc in roadmap:
            st.markdown(
                f'<div style="display:flex;gap:12px;align-items:flex-start;margin-bottom:10px">'
                f'<span style="font-size:1.1rem;min-width:24px">{status}</span>'
                f'<div><div style="font-weight:600;color:#f8fafc;font-size:0.9rem">{title}</div>'
                f'<div style="color:#64748b;font-size:0.82rem">{desc}</div></div></div>',
                unsafe_allow_html=True,
            )

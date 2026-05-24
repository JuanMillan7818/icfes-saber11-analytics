import pandas as pd
import streamlit as st


# ── Equipo ─────────────────────────────────────────────────────────────────────
DEVELOPERS = [
    {
        "name": "Juan Pablo Millán",
        "role": "",
        "icon": "⚙️",
    },
    {
        "name": "Mayerly Marmolejo Triviño",
        "role": "",
        "icon": "⚙️",
    },
    {
        "name": "Julian Andres Gasca Arevalo",
        "role": "",
        "icon": "⚙️",
    },
]


def render():
    st.markdown("<br>", unsafe_allow_html=True)

    # ── Hero banner ────────────────────────────────────────────────────────────
    st.markdown(
        """
        <div style="
            background: linear-gradient(135deg,rgba(14,165,233,0.18) 0%,rgba(129,140,248,0.18) 100%);
            border: 1px solid rgba(56,189,248,0.25);
            border-radius: 20px;
            padding: 48px 40px 36px 40px;
            text-align: center;
            margin-bottom: 32px;
        ">
            <div style="font-size:4rem;margin-bottom:12px;">📊</div>
            <div style="
                font-size: clamp(1.8rem, 4vw, 2.6rem);
                font-weight: 800;
                background: linear-gradient(90deg,#38bdf8,#818cf8);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-bottom: 14px;
                line-height: 1.2;
            ">ICFES Saber 11 · Analytics Platform</div>
            <div style="
                color: #94a3b8;
                font-size: 1rem;
                max-width: 680px;
                margin: 0 auto;
                line-height: 1.7;
            ">
                Plataforma de análisis interactivo de microdatos educativos colombianos.
                Explora <strong style="color:#f8fafc">10 años de resultados</strong> del examen Saber 11
                (2015 – 2025) con consultas in-memory a velocidad DuckDB sobre ~4.8&nbsp;M registros (~4.3GB).
                Diseñada para coordinadores académicos, secretarías de educación y planificadores educativos.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Stack + Arquitectura ───────────────────────────────────────────────────
    left_a, right_a = st.columns([3, 2], gap="large")

    with left_a:
        st.markdown("#### 🛠️ Stack Tecnológico")
        tech_data = {
            "Componente": [
                "Backend datos",
                "ETL / Normalización",
                "Dashboard",
                "Gráficos",
                "Paquetes",
            ],
            "Tecnología": [
                "DuckDB 1.1+",
                "Pandas · PyArrow",
                "Streamlit 1.40+",
                "Plotly 5.24+",
                "uv",
            ],
            "Propósito": [
                "Consultas OLAP in-memory sobre Parquet",
                "Procesamiento y validación de esquemas TXT/CSV → Parquet",
                "Interfaz web interactiva multi-tab",
                "Visualizaciones dinámicas e interactivas",
                "Gestor de paquetes ultrarrápido (Rust)",
            ],
        }
        st.dataframe(pd.DataFrame(tech_data), use_container_width=True, hide_index=True)

    with right_a:
        st.markdown("#### 📐 Arquitectura")
        st.markdown(
            """
            <div class="section-card" style="padding:24px;">
                <div style="display:flex;flex-direction:column;gap:14px;font-size:0.88rem;">
                    <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
                        <span style="background:rgba(56,189,248,0.15);border-radius:8px;padding:4px 12px;
                                     color:#38bdf8;font-weight:700;">TXT</span>
                        <span style="color:#475569;">--→ ETL Pandas --→</span>
                        <span style="background:rgba(129,140,248,0.15);border-radius:8px;padding:4px 12px;
                                     color:#818cf8;font-weight:700;">Parquet</span>
                    </div>
                    <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
                        <span style="background:rgba(129,140,248,0.15);border-radius:8px;padding:4px 12px;
                                     color:#818cf8;font-weight:700;">Parquet</span>
                        <span style="color:#475569;">--→ DuckDB --→</span>
                        <span style="background:rgba(52,211,153,0.15);border-radius:8px;padding:4px 12px;
                                     color:#34d399;font-weight:700;">DataFrame</span>
                    </div>
                    <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
                        <span style="background:rgba(52,211,153,0.15);border-radius:8px;padding:4px 12px;
                                     color:#34d399;font-weight:700;">DataFrame</span>
                        <span style="color:#475569;">--→ Plotly --→</span>
                        <span style="background:rgba(250,204,21,0.15);border-radius:8px;padding:4px 12px;
                                     color:#facc15;font-weight:700;">Dashboard</span>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown('<div class="grad-divider"></div>', unsafe_allow_html=True)

    # ── Equipo ─────────────────────────────────────────────────────────────────
    st.markdown("#### 👥 Equipo de Desarrollo")
    cols = st.columns(len(DEVELOPERS), gap="large")
    for col, dev in zip(cols, DEVELOPERS):
        with col:
            st.markdown(
                f"""
                <div class="section-card" style="text-align:center;padding:28px 20px;">
                    <div style="font-size:2.6rem;margin-bottom:10px;">{dev["icon"]}</div>
                    <div style="font-weight:700;color:#f8fafc;font-size:0.97rem;margin-bottom:6px;">{dev["name"]}</div>
                    <div style="color:#64748b;font-size:0.82rem;">{dev["role"]}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown('<div class="grad-divider"></div>', unsafe_allow_html=True)

    # ── Cifras del proyecto ─────────────────────────────────────────────────────
    st.markdown("#### 📦 Datos del Proyecto")
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("📁 Períodos", "22 semestres")
    d2.metric("👥 Registros", "~4.8 M")
    d3.metric("📅 Cobertura", "2015 – 2025")
    d4.metric("🗄️ Formato", "Parquet · DuckDB")

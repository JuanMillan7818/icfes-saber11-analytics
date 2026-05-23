"""
HU 3 · Simulador Predictivo
Carga un modelo de regresión preentrenado (.pkl / .joblib) y permite
al planificador simular el impacto de variables socioeconómicas
sobre el puntaje global futuro.

El modelo debe predecir punt_global a partir de:
  - pct_internet   : % estudiantes con internet en el hogar (0-100)
  - pct_educacion_sup : % madres/padres con educación superior (0-100)
  - promedio_estrato  : estrato promedio (1-6)

Entrena el modelo con:
  uv run python scripts/train_simulador.py
que guarda el archivo en models/simulador.pkl
"""

from __future__ import annotations

import pathlib

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from icfes.dashboard.components.theme import dark_layout

# ── Ruta al modelo ─────────────────────────────────────────────────────────────
_ROOT = pathlib.Path(__file__).resolve().parents[4]  # raíz del proyecto
MODEL_PATH = _ROOT / "models" / "simulador.pkl"

FEATURES = ["pct_internet", "pct_educacion_sup", "promedio_estrato"]
FEATURE_LABELS = {
    "pct_internet": "% con Internet en hogar",
    "pct_educacion_sup": "% madres/padres con educación superior",
    "promedio_estrato": "Estrato promedio",
}


@st.cache_resource(show_spinner=False)
def _load_model():
    """Carga modelo pkl/joblib. Retorna (model, feature_names) o None."""
    if not MODEL_PATH.exists():
        return None
    try:
        import joblib

        return joblib.load(MODEL_PATH)
    except Exception:
        try:
            import pickle

            with open(MODEL_PATH, "rb") as f:
                return pickle.load(f)
        except Exception:
            return None


@st.cache_data(ttl=600, show_spinner=False)
def _ultimo_real(_svc):
    """Último año con promedio global real y variables socioeconómicas agregadas."""
    try:
        df = _svc.query_df(
            """
            SELECT ano,
                   AVG(CAST(punt_global AS DOUBLE)) AS prom_global,
                   SUM(CASE WHEN fami_tieneinternet = 'Si' THEN 1 ELSE 0 END) * 100.0 / COUNT(*) AS pct_internet,
                   SUM(CASE WHEN fami_educacionmadre IN (
                       'Universitaria','Postgrado','Técnica o tecnológica profesional'
                   ) OR fami_educacionpadre IN (
                       'Universitaria','Postgrado','Técnica o tecnológica profesional'
                   ) THEN 1 ELSE 0 END) * 100.0 / COUNT(*) AS pct_educacion_sup,
                   AVG(CAST(REPLACE(fami_estratovivienda, 'Estrato ', '') AS INTEGER)) AS promedio_estrato
            FROM {parquet}
            WHERE ano IS NOT NULL
            GROUP BY ano ORDER BY ano DESC LIMIT 1
            """
        )
        return df if not df.empty else None
    except Exception:
        return None


def render(svc=None):
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        """
        <div class="hero-badge">🤖 Planificador Educativo</div>
        <div class="section-heading">Simulador Predictivo de Impacto</div>
        <div style="color:#64748b;font-size:0.9rem;margin-bottom:20px;">
            Modifica variables socioeconómicas y proyecta cómo impactaría
            una inversión pública en los puntajes futuros del ICFES.
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Cargar modelo ──────────────────────────────────────────────────────────
    model = _load_model()

    if model is None:
        st.warning(
            f"⚠️ Modelo no encontrado en `{MODEL_PATH}`. "
            "Entrénalo primero ejecutando:\n\n"
            "```bash\nuv run python scripts/train_simulador.py\n```"
        )
        _show_train_instructions()
        return

    # ── Último dato real ───────────────────────────────────────────────────────
    real_data = None
    if svc:
        with st.spinner("Cargando último año real..."):
            real_data = _ultimo_real(svc)

    if real_data is not None and not real_data.empty:
        ano_ref = str(real_data["ano"].iloc[0])
        prom_real = float(real_data["prom_global"].iloc[0])
        default_internet = float(real_data["pct_internet"].iloc[0])
        default_edu = float(real_data["pct_educacion_sup"].iloc[0])
        default_estrato = float(real_data["promedio_estrato"].iloc[0])
    else:
        ano_ref = "2025"
        prom_real = 258.0
        default_internet = 65.0
        default_edu = 30.0
        default_estrato = 2.5

    st.markdown(
        f'<div class="info-chip">📅 Último año real disponible: <strong>{ano_ref}</strong> '
        f"· Promedio Global: <strong>{prom_real:.1f}</strong></div>",
        unsafe_allow_html=True,
    )

    st.markdown('<div class="grad-divider"></div>', unsafe_allow_html=True)

    # ── Sliders de simulación ──────────────────────────────────────────────────
    st.markdown("#### 🎛️ Variables de Simulación")
    st.caption("Ajusta los porcentajes para proyectar el impacto en el puntaje global.")

    col_sl, col_res = st.columns([2, 3], gap="large")

    with col_sl:
        sim_internet = st.slider(
            "📡 % Estudiantes con Internet",
            min_value=0,
            max_value=100,
            value=int(min(default_internet + 10, 100)),
            step=1,
            help="Porcentaje proyectado de estudiantes con acceso a internet en el hogar.",
        )
        sim_edu = st.slider(
            "🎓 % Con educación superior (padres)",
            min_value=0,
            max_value=100,
            value=int(min(default_edu + 5, 100)),
            step=1,
            help="Porcentaje de estudiantes cuyos padres tienen educación superior.",
        )
        sim_estrato = st.slider(
            "🏠 Estrato promedio",
            min_value=1.0,
            max_value=6.0,
            value=min(float(round(default_estrato + 0.3, 1)), 6.0),
            step=0.1,
            help="Estrato socioeconómico promedio de los estudiantes.",
        )

        st.markdown('<div class="grad-divider"></div>', unsafe_allow_html=True)
        st.markdown("##### 📊 Valores actuales (referencia)")
        st.metric(
            "Internet actual",
            f"{default_internet:.1f}%",
            delta=f"+{sim_internet - default_internet:.1f}%",
        )
        st.metric(
            "Edu. superior actual",
            f"{default_edu:.1f}%",
            delta=f"+{sim_edu - default_edu:.1f}%",
        )
        st.metric(
            "Estrato actual",
            f"{default_estrato:.2f}",
            delta=f"+{sim_estrato - default_estrato:.2f}",
        )

    with col_res:
        # Predecir
        X_real = np.array([[default_internet, default_edu, default_estrato]])
        X_sim = np.array([[sim_internet, sim_edu, sim_estrato]])

        try:
            pred_real = float(model.predict(X_real)[0])
            pred_sim = float(model.predict(X_sim)[0])
            delta_pred = pred_sim - pred_real
        except Exception as e:
            st.error(f"Error al predecir: {e}")
            return

        # KPIs resultado
        rk1, rk2, rk3 = st.columns(3)
        rk1.metric("📘 Real " + ano_ref, f"{prom_real:.1f}")
        rk2.metric(
            "🤖 Proyección simulada",
            f"{pred_sim:.1f}",
            delta=f"{delta_pred:+.1f} pts vs real",
        )
        rk3.metric(
            "📈 Mejora proyectada",
            f"{pred_sim - prom_real:+.1f} pts",
        )

        # Gráfico comparativo
        fig_sim = go.Figure()

        categorias = [f"Real {ano_ref}", "Proyección Simulada"]
        valores = [prom_real, pred_sim]
        colores = ["#38bdf8", "#34d399" if delta_pred >= 0 else "#f43f5e"]

        fig_sim.add_trace(
            go.Bar(
                x=categorias,
                y=valores,
                marker_color=colores,
                text=[f"{v:.1f}" for v in valores],
                textposition="outside",
                textfont_color="#f8fafc",
                hovertemplate="<b>%{x}</b><br>Puntaje: %{y:.1f}<extra></extra>",
            )
        )
        fig_sim.add_shape(
            type="line",
            x0=-0.5,
            x1=1.5,
            y0=prom_real,
            y1=prom_real,
            line=dict(color="#38bdf8", width=1.5, dash="dot"),
        )
        fig_sim.add_annotation(
            x=1,
            y=prom_real,
            text=f"Línea base: {prom_real:.1f}",
            showarrow=False,
            yanchor="bottom",
            font=dict(color="#38bdf8", size=11),
        )
        rng_min = min(valores) - 5
        rng_max = max(valores) + 8
        fig_sim.update_layout(
            **dark_layout(
                title="Último dato real vs Proyección simulada",
                yaxis=dict(range=[rng_min, rng_max], title="Puntaje Global Promedio"),
                xaxis=dict(title=""),
            )
        )
        st.plotly_chart(fig_sim, use_container_width=True)

        # Coeficientes del modelo
        with st.expander("🔍 Ver coeficientes del modelo"):
            try:
                coefs = model.coef_ if hasattr(model, "coef_") else None
                intercept = (
                    float(model.intercept_) if hasattr(model, "intercept_") else None
                )
                if coefs is not None:
                    import pandas as pd

                    df_coef = pd.DataFrame(
                        {"Variable": FEATURE_LABELS[f] for f in FEATURES},
                        index=range(len(FEATURES)),
                    )
                    df_coef = pd.DataFrame(
                        {
                            "Variable": [FEATURE_LABELS[f] for f in FEATURES],
                            "Coeficiente": [round(c, 4) for c in coefs],
                            "Interpretación": [
                                (
                                    f"Por cada +1% → {c:+.2f} pts en puntaje"
                                    if abs(c) < 100
                                    else f"Por cada +1 → {c:+.2f} pts"
                                )
                                for c in coefs
                            ],
                        }
                    )
                    if intercept is not None:
                        st.caption(f"Intercepto del modelo: **{intercept:.2f}**")
                    st.dataframe(df_coef, use_container_width=True, hide_index=True)
                else:
                    st.info("El modelo no expone coeficientes lineales.")
            except Exception as ex:
                st.warning(f"No se pudieron mostrar coeficientes: {ex}")


def _show_train_instructions():
    """Instrucciones para entrenar el modelo."""
    st.markdown("---")
    st.markdown("#### 📋 Cómo entrenar el modelo")
    st.markdown(
        """
        Crea el script `scripts/train_simulador.py` con el siguiente contenido
        y ejecútalo una vez para generar `models/simulador.pkl`:
        ```python
        import pathlib, pickle
        import pandas as pd
        import duckdb
        from sklearn.linear_model import LinearRegression
        from icfes import settings

        con = duckdb.connect()
        con.execute("LOAD parquet")
        df = con.execute(f\"\"\"
            SELECT
                SUM(CASE WHEN fami_tieneinternet='Si' THEN 1 ELSE 0 END)*100.0/COUNT(*) AS pct_internet,
                SUM(CASE WHEN fami_educacionmadre IN ('Universitaria','Postgrado','Técnica o tecnológica profesional')
                          OR fami_educacionpadre IN ('Universitaria','Postgrado','Técnica o tecnológica profesional')
                     THEN 1 ELSE 0 END)*100.0/COUNT(*) AS pct_educacion_sup,
                AVG(TRY_CAST(REPLACE(fami_estratovivienda, 'Estrato ', '') AS INTEGER)) AS promedio_estrato,
                AVG(CAST(punt_global AS DOUBLE)) AS punt_global
            FROM read_parquet('{settings.PARQUET_PATH}/*.parquet')
            WHERE ano IS NOT NULL
            GROUP BY ano
        \"\"\").df()

        X = df[["pct_internet","pct_educacion_sup","promedio_estrato"]].dropna()
        y = df.loc[X.index, "punt_global"]
        model = LinearRegression().fit(X, y)

        out = pathlib.Path("models")
        out.mkdir(exist_ok=True)
        with open(out / "simulador.pkl", "wb") as f:
            pickle.dump(model, f)
        print("Modelo guardado en models/simulador.pkl")
        print("R²:", model.score(X, y))
        ```
        """
    )

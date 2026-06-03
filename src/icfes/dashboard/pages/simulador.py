"""
HU 3 · Simulador Predictivo
Layout lineal (sin tabs):
  1. Nivel de análisis (Nacional / Municipio / Colegio)
  2. Variables de simulación (sliders)
  3. Resultados de los 3 modelos en paralelo — mejor destacado
  4. Detalle técnico y comparativa (expander)

Entrena / actualiza los modelos:
    uv run python scripts/train_simulador.py
"""

from __future__ import annotations

import pathlib

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from icfes.dashboard.components.theme import dark_layout

_ROOT = pathlib.Path(__file__).resolve().parents[4]
MODEL_PATH = _ROOT / "models" / "simulador_models.pkl"
_FALLBACK = _ROOT / "models" / "simulador.pkl"

FEATURES = ["pct_internet", "pct_educacion_sup", "promedio_estrato"]
FEATURE_LABELS = {
    "pct_internet": "% con Internet en hogar",
    "pct_educacion_sup": "% padres con educación superior",
    "promedio_estrato": "Estrato promedio",
}

_EDU_SUP = (
    "fami_educacionmadre IN ('Universitaria','Postgrado','Técnica o tecnológica profesional')"
    " OR fami_educacionpadre IN ('Universitaria','Postgrado','Técnica o tecnológica profesional')"
)
_ESTRATO_CAST = "TRY_CAST(REPLACE(fami_estratovivienda, 'Estrato ', '') AS INTEGER)"


# ── Model loading ──────────────────────────────────────────────────────────────


@st.cache_resource(show_spinner=False)
def _load_bundle():
    path = (
        MODEL_PATH
        if MODEL_PATH.exists()
        else (_FALLBACK if _FALLBACK.exists() else None)
    )
    if path is None:
        return None
    raw = None
    try:
        import joblib

        raw = joblib.load(path)
    except Exception:
        try:
            import pickle

            with open(path, "rb") as f:
                raw = pickle.load(f)
        except Exception:
            return None
    if raw is None:
        return None
    if isinstance(raw, dict) and "model" in raw:
        return raw
    return {
        "model": raw,
        "r2": None,
        "mse": None,
        "rmse": None,
        "n_train": None,
        "algo": type(raw).__name__,
    }


# ── Geo queries ────────────────────────────────────────────────────────────────


@st.cache_data(ttl=600, show_spinner=False)
def _municipios(_svc) -> list[str]:
    try:
        df = _svc.query_df(
            "SELECT DISTINCT cole_mcpio_ubicacion AS m FROM {parquet}"
            " WHERE cole_mcpio_ubicacion IS NOT NULL AND cole_mcpio_ubicacion != ''"
            " ORDER BY m"
        )
        return df["m"].dropna().tolist()
    except Exception:
        return []


@st.cache_data(ttl=600, show_spinner=False)
def _colegios_en_mpio(_svc, municipio: str) -> list[str]:
    try:
        df = _svc.query_df(
            f"""
            SELECT DISTINCT trim(cole_nombre_establecimiento) AS c
            FROM {{parquet}}
            WHERE cole_mcpio_ubicacion = '{municipio}'
              AND cole_nombre_establecimiento IS NOT NULL
              AND cole_nombre_establecimiento != ''
            ORDER BY c
            """
        )
        return df["c"].dropna().tolist()
    except Exception:
        return []


@st.cache_data(ttl=600, show_spinner=False)
def _indicadores(_svc, municipio: str | None, colegio: str | None):
    where_parts = [
        "ano IS NOT NULL",
        "punt_global IS NOT NULL",
        "fami_estratovivienda IS NOT NULL",
    ]
    if municipio:
        where_parts.append(
            f"cole_mcpio_ubicacion = '{municipio.replace(chr(39), chr(39)*2)}'"
        )
    if colegio:
        where_parts.append(
            f"trim(cole_nombre_establecimiento) = '{colegio.replace(chr(39), chr(39)*2)}'"
        )
    where = " AND ".join(where_parts)
    try:
        df = _svc.query_df(
            f"""
            SELECT
                MAX(ano) AS ano,
                AVG(CAST(punt_global AS DOUBLE)) AS prom_global,
                SUM(CASE WHEN fami_tieneinternet = 'Si' THEN 1.0 ELSE 0.0 END)
                    * 100.0 / COUNT(*) AS pct_internet,
                SUM(CASE WHEN {_EDU_SUP} THEN 1.0 ELSE 0.0 END)
                    * 100.0 / COUNT(*) AS pct_educacion_sup,
                AVG({_ESTRATO_CAST}) AS promedio_estrato,
                COUNT(*) AS n_est
            FROM {{parquet}}
            WHERE {where}
              AND ano >= (SELECT MAX(ano) - 1 FROM {{parquet}} WHERE {where})
            """
        )
        return df if not df.empty else None
    except Exception:
        return None


# ── Helpers ───────────────────────────────────────────────────────────────────


def _r2_color(r2: float) -> str:
    if r2 >= 0.85:
        return "#34d399"
    if r2 >= 0.60:
        return "#facc15"
    return "#f87171"


def _hex_rgba(hex_color: str, alpha: float = 0.13) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _r2_label(r2: float) -> str:
    if r2 >= 0.85:
        return "Alta"
    if r2 >= 0.60:
        return "Moderada"
    return "Baja"


# ── Main render ────────────────────────────────────────────────────────────────


def render(svc=None):
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        """
        <div class="hero-badge">🤖 Planificador Educativo</div>
        <div class="section-heading">Simulador Predictivo de Impacto</div>
        <div style="color:#64748b;font-size:0.9rem;margin-bottom:20px;">
            Ajusta variables socioeconómicas y proyecta el impacto en el puntaje ICFES.
            Tres modelos de ML predicen en paralelo — el mejor queda destacado.
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Cargar bundle ──────────────────────────────────────────────────────────
    bundle = _load_bundle()
    if bundle is None:
        st.warning(
            f"⚠️ Modelo no encontrado en `{MODEL_PATH}`. Entrénalo primero:\n\n"
            "```bash\nuv run python scripts/train_simulador.py\n```"
        )
        _show_train_instructions()
        return

    # Normalizar bundle (compat legacy)
    models_meta: dict = bundle.get("models_meta", {})
    best_key: str = bundle.get("best_model_key", "ridge")
    models_map: dict = bundle.get("models", {})

    if not models_meta:
        models_meta = {
            "ridge": {
                "label": bundle.get("algo", "Ridge"),
                "short": "Ridge",
                "color": "#38bdf8",
                "icon": "📐",
                "r2_test": bundle.get("r2", 0) or 0,
                "r2_cv": bundle.get("r2_cv", 0) or 0,
                "rmse": bundle.get("rmse", 0) or 0,
                "mae": 0,
            }
        }
        models_map = {"ridge": bundle["model"]}
        best_key = "ridge"

    # ── 1. Nivel de análisis — steps progresivos ───────────────────────────────
    def _step_label(n: int, texto: str, activo: bool = True) -> str:
        color = "#818cf8" if activo else "#334155"
        txt_c = "#f8fafc" if activo else "#475569"
        return (
            f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">'
            f'<div style="width:24px;height:24px;border-radius:50%;background:{color};'
            f"display:flex;align-items:center;justify-content:center;"
            f'font-size:0.72rem;font-weight:700;color:#fff;flex-shrink:0;">{n}</div>'
            f'<span style="font-size:0.78rem;font-weight:600;color:{txt_c};'
            f'text-transform:uppercase;letter-spacing:.06em;">{texto}</span>'
            f"</div>"
        )

    st.markdown("#### 📍 Selección de Entidad")

    # ── Paso 1: tipo de nivel ──────────────────────────────────────────────────
    st.markdown(_step_label(1, "¿Qué nivel quieres analizar?"), unsafe_allow_html=True)
    nivel = st.selectbox(
        "Nivel de análisis",
        ["Nacional", "Municipio", "Colegio"],
        key="sim_nivel",
        label_visibility="collapsed",
        format_func=lambda x: {
            "Nacional": "🇨🇴  Nacional — promedio de todo el dataset",
            "Municipio": "🏙️  Municipio — indicadores de un municipio específico",
            "Colegio": "🏫  Colegio — indicadores de una institución educativa",
        }[x],
    )

    municipio_sel: str | None = None
    colegio_sel: str | None = None

    # ── Paso 2: municipio (si aplica) ──────────────────────────────────────────
    if nivel in ("Municipio", "Colegio"):
        st.markdown("<br>", unsafe_allow_html=True)
        label2 = (
            "Selecciona el municipio"
            if nivel == "Municipio"
            else "Selecciona el municipio (para filtrar colegios)"
        )
        st.markdown(_step_label(2, label2), unsafe_allow_html=True)

        if svc:
            mpios = _municipios(svc)
            if mpios:
                municipio_sel = st.selectbox(
                    "Municipio",
                    mpios,
                    key="sim_mpio",
                    label_visibility="collapsed",
                    format_func=lambda x: x.title(),
                )
            else:
                st.warning("Sin municipios disponibles en los datos.")

    # ── Paso 3: colegio ────────────────────────────────────────────────────────
    if nivel in ("Municipio", "Colegio") and municipio_sel:
        st.markdown("<br>", unsafe_allow_html=True)
        if nivel == "Municipio":
            st.markdown(
                _step_label(
                    3,
                    "Colegio específico (opcional — omitir para ver todo el municipio)",
                ),
                unsafe_allow_html=True,
            )
            opciones_col = ["— Todo el municipio —"]
        else:
            st.markdown(
                _step_label(3, "Selecciona el colegio"),
                unsafe_allow_html=True,
            )
            opciones_col = []

        if svc:
            cols_list = _colegios_en_mpio(svc, municipio_sel)
            if cols_list:
                sel = st.selectbox(
                    "Colegio",
                    opciones_col + cols_list,
                    key="sim_col",
                    label_visibility="collapsed",
                )
                if sel and sel != "— Todo el municipio —":
                    colegio_sel = sel
            else:
                st.info("Sin colegios registrados para este municipio.")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Indicadores de referencia ──────────────────────────────────────────────
    ref_data = None
    if svc:
        with st.spinner("Cargando indicadores..."):
            ref_data = _indicadores(svc, municipio_sel, colegio_sel)

    if ref_data is not None and not ref_data.empty:
        ano_ref = str(ref_data["ano"].iloc[0])
        prom_real = float(ref_data["prom_global"].iloc[0])
        default_internet = float(ref_data["pct_internet"].iloc[0])
        default_edu = float(ref_data["pct_educacion_sup"].iloc[0])
        default_estrato = float(ref_data["promedio_estrato"].iloc[0])
        n_est = int(ref_data["n_est"].iloc[0]) if "n_est" in ref_data.columns else None
    else:
        ano_ref, prom_real = "2025", 258.0
        default_internet, default_edu, default_estrato = 65.0, 30.0, 2.5
        n_est = None

    if nivel == "Colegio" and colegio_sel:
        entidad_label = f"🏫 {colegio_sel.title()} · {(municipio_sel or '').title()}"
    elif nivel == "Municipio" and municipio_sel:
        entidad_label = f"🏙️ {municipio_sel.title()}"
    else:
        entidad_label = "🇨🇴 Nacional"

    n_chip = f" · {n_est:,} estudiantes".replace(",", ".") if n_est else ""
    st.markdown(
        f'<div class="info-chip">{entidad_label}'
        f" &nbsp;|&nbsp; <strong>Año ref.:</strong> {ano_ref}"
        f" &nbsp;|&nbsp; <strong>Prom. real:</strong> {prom_real:.1f}{n_chip}</div>",
        unsafe_allow_html=True,
    )

    st.markdown('<div class="grad-divider"></div>', unsafe_allow_html=True)

    # ── 2. Variables de simulación ─────────────────────────────────────────────
    st.markdown("#### 🎛️ Variables de Simulación")
    st.caption(
        "Ajusta los valores para proyectar el impacto. Los valores actuales aparecen como referencia."
    )

    col_sl, col_ref = st.columns([3, 2], gap="large")

    with col_sl:
        sim_internet = st.slider(
            "📡 % Estudiantes con Internet en el hogar",
            min_value=0,
            max_value=100,
            value=int(min(default_internet + 10, 100)),
            step=1,
        )
        sim_edu = st.slider(
            "🎓 % Padres con educación superior",
            min_value=0,
            max_value=100,
            value=int(min(default_edu + 5, 100)),
            step=1,
        )
        sim_estrato = st.slider(
            "🏠 Estrato socioeconómico promedio",
            min_value=1.0,
            max_value=6.0,
            value=min(float(round(default_estrato + 0.3, 1)), 6.0),
            step=0.1,
        )

    with col_ref:
        st.markdown(
            f"""
            <div style="
                background: rgba(255,255,255,0.03);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 14px;
                padding: 20px 22px;
                margin-top: 8px;
            ">
                <div style="font-size:0.72rem;color:#64748b;text-transform:uppercase;
                            letter-spacing:.08em;margin-bottom:14px;">
                    📊 Valores reales actuales — {entidad_label}
                </div>
                <div style="display:grid;gap:12px;">
                    <div>
                        <div style="font-size:0.75rem;color:#94a3b8;">Internet en hogar</div>
                        <div style="display:flex;align-items:baseline;gap:8px;">
                            <span style="font-size:1.6rem;font-weight:700;color:#f8fafc;">
                                {default_internet:.1f}%
                            </span>
                            <span style="font-size:0.85rem;color:{'#34d399' if sim_internet > default_internet else '#f87171'};">
                                {sim_internet - default_internet:+.1f}%
                            </span>
                        </div>
                    </div>
                    <div>
                        <div style="font-size:0.75rem;color:#94a3b8;">Educación superior padres</div>
                        <div style="display:flex;align-items:baseline;gap:8px;">
                            <span style="font-size:1.6rem;font-weight:700;color:#f8fafc;">
                                {default_edu:.1f}%
                            </span>
                            <span style="font-size:0.85rem;color:{'#34d399' if sim_edu > default_edu else '#f87171'};">
                                {sim_edu - default_edu:+.1f}%
                            </span>
                        </div>
                    </div>
                    <div>
                        <div style="font-size:0.75rem;color:#94a3b8;">Estrato promedio</div>
                        <div style="display:flex;align-items:baseline;gap:8px;">
                            <span style="font-size:1.6rem;font-weight:700;color:#f8fafc;">
                                {default_estrato:.2f}
                            </span>
                            <span style="font-size:0.85rem;color:{'#34d399' if sim_estrato > default_estrato else '#f87171'};">
                                {sim_estrato - default_estrato:+.2f}
                            </span>
                        </div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown('<div class="grad-divider"></div>', unsafe_allow_html=True)

    # ── 3. Resultados: los 3 modelos en paralelo ───────────────────────────────
    st.markdown("#### 📈 Resultados de la Simulación")

    X_sim = np.array([[sim_internet, sim_edu, sim_estrato]])

    # Calcular predicción de cada modelo
    preds: dict[str, float] = {}
    for key, model_obj in models_map.items():
        try:
            preds[key] = float(np.clip(model_obj.predict(X_sim)[0], 0, 500))
        except Exception:
            preds[key] = float("nan")

    # KPI real primero
    kpi_real, *kpi_model_cols = st.columns([1] + [1] * len(models_map), gap="medium")
    kpi_real.metric(f"📘 Real {ano_ref}", f"{prom_real:.1f}")

    # Tarjeta resultado por modelo
    best_col_color = models_meta[best_key].get("color", "#38bdf8")
    for col_widget, (key, meta) in zip(kpi_model_cols, models_meta.items()):
        pred = preds.get(key, float("nan"))
        delta = pred - prom_real
        is_best = key == best_key
        col_widget.metric(
            f"{meta['icon']} {meta['short']}" + ("  🏆" if is_best else ""),
            f"{pred:.1f}" if not np.isnan(pred) else "N/D",
            delta=f"{delta:+.1f} pts vs real" if not np.isnan(pred) else None,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Tarjetas grandes por modelo ────────────────────────────────────────────
    card_cols = st.columns(len(models_map), gap="medium")
    for col_widget, (key, meta) in zip(card_cols, models_meta.items()):
        pred = preds.get(key, float("nan"))
        delta = pred - prom_real
        is_best = key == best_key
        r2 = meta.get("r2_test", 0) or 0
        rmse = meta.get("rmse", 0) or 0

        border = (
            f"2px solid {meta['color']}"
            if is_best
            else "1.5px solid rgba(255,255,255,0.08)"
        )
        shadow = f"0 0 28px {meta['color']}35" if is_best else "none"
        bg = (
            f"linear-gradient(135deg, {meta['color']}12 0%, rgba(255,255,255,0.02) 100%)"
            if is_best
            else "rgba(255,255,255,0.025)"
        )
        delta_color = "#34d399" if delta >= 0 else "#f87171"
        badge = (
            (
                f'<div style="font-size:0.68rem;font-weight:700;color:{meta["color"]};'
                f'text-transform:uppercase;letter-spacing:.08em;margin-bottom:10px;">'
                f"🏆 Mejor modelo · {_r2_label(r2)}</div>"
            )
            if is_best
            else (
                f'<div style="font-size:0.68rem;color:#64748b;margin-bottom:10px;">'
                f"{_r2_label(r2)}</div>"
            )
        )

        with col_widget:
            st.markdown(
                f"""
                <div style="
                    background: {bg};
                    border: {border};
                    border-radius: 18px;
                    padding: 24px 20px;
                    box-shadow: {shadow};
                    text-align: center;
                    height: 100%;
                ">
                    <div style="font-size:2rem;margin-bottom:4px;">{meta['icon']}</div>
                    <div style="font-size:1rem;font-weight:700;color:#f8fafc;margin-bottom:2px;">
                        {meta['label']}
                    </div>
                    {badge}
                    <div style="font-size:2.8rem;font-weight:900;
                                color:{'#f8fafc' if not is_best else meta['color']};
                                line-height:1;margin-bottom:6px;">
                        {f'{pred:.1f}' if not np.isnan(pred) else 'N/D'}
                    </div>
                    <div style="font-size:1rem;font-weight:600;color:{delta_color};margin-bottom:16px;">
                        {f'{delta:+.1f} pts vs real' if not np.isnan(pred) else ''}
                    </div>
                    <div style="display:flex;justify-content:center;gap:20px;
                                padding-top:14px;border-top:1px solid rgba(255,255,255,0.07);">
                        <div>
                            <div style="font-size:0.62rem;color:#64748b;
                                        text-transform:uppercase;letter-spacing:.06em;">R² Test</div>
                            <div style="font-size:1rem;font-weight:700;
                                        color:{_r2_color(r2)};">{r2:.4f}</div>
                        </div>
                        <div>
                            <div style="font-size:0.62rem;color:#64748b;
                                        text-transform:uppercase;letter-spacing:.06em;">RMSE</div>
                            <div style="font-size:1rem;font-weight:700;color:#e2e8f0;">{rmse:.2f}</div>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # ── Gráfico comparativo: real + 3 modelos ──────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)

    bar_labels = [f"Real {ano_ref}"] + [
        f"{meta['icon']} {meta['short']}" + (" 🏆" if k == best_key else "")
        for k, meta in models_meta.items()
    ]
    bar_values = [prom_real] + [preds.get(k, 0) for k in models_meta]
    bar_colors = ["#38bdf8"] + [
        meta.get("color", "#94a3b8") for meta in models_meta.values()
    ]
    bar_opacity = [1.0] + [1.0 if k == best_key else 0.55 for k in models_meta]

    fig_comp = go.Figure()
    fig_comp.add_trace(
        go.Bar(
            x=bar_labels,
            y=bar_values,
            marker_color=bar_colors,
            marker_opacity=bar_opacity,
            marker_line_width=0,
            text=[f"{v:.1f}" for v in bar_values],
            textposition="outside",
            textfont=dict(color="#f8fafc", size=13),
            hovertemplate="<b>%{x}</b><br>Puntaje: %{y:.1f}<extra></extra>",
        )
    )
    fig_comp.add_shape(
        type="line",
        x0=-0.5,
        x1=len(bar_labels) - 0.5,
        y0=prom_real,
        y1=prom_real,
        line=dict(color="#38bdf8", width=1.5, dash="dot"),
    )
    fig_comp.add_annotation(
        x=len(bar_labels) - 1,
        y=prom_real,
        text=f"Línea base real: {prom_real:.1f}",
        showarrow=False,
        yanchor="bottom",
        font=dict(color="#38bdf8", size=11),
    )
    rng_min = min(bar_values) - 6
    rng_max = min(max(bar_values) + 14, 500)
    fig_comp.update_layout(
        **dark_layout(
            title=f"Puntaje real vs proyección simulada · {entidad_label}",
            yaxis=dict(range=[rng_min, rng_max], title="Puntaje Global Promedio"),
            xaxis=dict(title=""),
        )
    )
    st.plotly_chart(fig_comp, use_container_width=True)

    # Advertencia fuera de rango
    for key, pred in preds.items():
        if not np.isnan(pred) and (pred > 350 or pred < 150):
            meta = models_meta[key]
            st.warning(
                f"⚠️ {meta['short']}: proyección {pred:.1f} pts fuera del rango típico "
                "(150–350). Considera reentrenar el modelo."
            )

    st.markdown('<div class="grad-divider"></div>', unsafe_allow_html=True)

    # ── 4. Detalle técnico y comparativa ──────────────────────────────────────
    with st.expander("🔍 Detalle técnico · Comparativa de modelos"):

        # Tabla benchmark
        st.markdown("##### 📋 Métricas de Entrenamiento")
        rows = []
        for key, meta in models_meta.items():
            rows.append(
                {
                    "Modelo": f"{meta['icon']} {meta['label']}",
                    "R² Test": meta.get("r2_test", 0) or 0,
                    "R² Train": meta.get("r2_train", 0) or 0,
                    "R² CV": meta.get("r2_cv", 0) or 0,
                    "CV ± SD": meta.get("r2_cv_sd", 0) or 0,
                    "RMSE": meta.get("rmse", 0) or 0,
                    "MAE": meta.get("mae", 0) or 0,
                    "Mejor": "🏆" if key == best_key else "",
                }
            )
        df_bench = pd.DataFrame(rows)
        styled = (
            df_bench.style.format(
                {
                    c: "{:.4f}"
                    for c in ["R² Test", "R² Train", "R² CV", "CV ± SD", "RMSE", "MAE"]
                }
            )
            .background_gradient(
                subset=["R² Test", "R² CV"], cmap="RdYlGn", vmin=0, vmax=1
            )
            .background_gradient(subset=["RMSE", "MAE"], cmap="RdYlGn_r", vmin=0)
        )
        st.dataframe(styled, use_container_width=True, hide_index=True)

        # ── Gráficas comparativas ──────────────────────────────────────────────
        st.markdown("<br>", unsafe_allow_html=True)
        gc1, gc2 = st.columns(2, gap="large")

        labels_m = [f"{m['icon']} {m['short']}" for m in models_meta.values()]
        colors_m = [m.get("color", "#94a3b8") for m in models_meta.values()]

        with gc1:
            rmse_vals = [m.get("rmse", 0) or 0 for m in models_meta.values()]
            min_rmse = min(rmse_vals) if rmse_vals else 0
            bar_colors_rmse = [
                c if v == min_rmse else _hex_rgba(c, 0.45)
                for c, v in zip(colors_m, rmse_vals)
            ]
            fig_rmse = go.Figure(
                go.Bar(
                    x=labels_m,
                    y=rmse_vals,
                    marker_color=bar_colors_rmse,
                    marker_line_width=0,
                    text=[f"{v:.4f}" for v in rmse_vals],
                    textposition="outside",
                    textfont=dict(color="#f8fafc", size=12),
                    hovertemplate="<b>%{x}</b><br>RMSE: %{y:.4f}<extra></extra>",
                )
            )
            fig_rmse.add_annotation(
                x=labels_m[rmse_vals.index(min_rmse)],
                y=min_rmse,
                text="✓ menor",
                showarrow=True,
                arrowhead=2,
                arrowcolor="#34d399",
                font=dict(color="#34d399", size=11),
                yshift=18,
            )
            fig_rmse.update_layout(
                **dark_layout(
                    title="RMSE por modelo (menor = mejor)",
                    yaxis=dict(title="RMSE (puntos)", rangemode="tozero"),
                    xaxis=dict(title=""),
                ),
                height=320,
            )
            st.plotly_chart(fig_rmse, use_container_width=True)

        with gc2:
            r2_vals = [m.get("r2_test", 0) or 0 for m in models_meta.values()]
            max_r2 = max(r2_vals) if r2_vals else 0
            bar_colors_r2 = [
                c if v == max_r2 else _hex_rgba(c, 0.45)
                for c, v in zip(colors_m, r2_vals)
            ]
            fig_r2 = go.Figure(
                go.Bar(
                    x=labels_m,
                    y=r2_vals,
                    marker_color=bar_colors_r2,
                    marker_line_width=0,
                    text=[f"{v:.4f}" for v in r2_vals],
                    textposition="outside",
                    textfont=dict(color="#f8fafc", size=12),
                    hovertemplate="<b>%{x}</b><br>R² Test: %{y:.4f}<extra></extra>",
                )
            )
            fig_r2.add_annotation(
                x=labels_m[r2_vals.index(max_r2)],
                y=max_r2,
                text="✓ mayor",
                showarrow=True,
                arrowhead=2,
                arrowcolor="#34d399",
                font=dict(color="#34d399", size=11),
                yshift=18,
            )
            fig_r2.update_layout(
                **dark_layout(
                    title="R² Test por modelo (mayor = mejor)",
                    yaxis=dict(title="R² (test set)", range=[0, 1.05]),
                    xaxis=dict(title=""),
                ),
                height=320,
            )
            st.plotly_chart(fig_r2, use_container_width=True)

        st.markdown("---")

        # Radar de perfiles
        st.markdown("##### 🕸️ Perfil Comparativo (Radar)")
        cat_labels = ["R² Test", "R² CV", "R² Train", "Precisión RMSE", "Precisión MAE"]
        all_rmse = [m.get("rmse", 1) or 1 for m in models_meta.values()]
        all_mae = [m.get("mae", 1) or 1 for m in models_meta.values()]
        max_rmse = max(all_rmse) or 1
        max_mae = max(all_mae) or 1

        fig_radar = go.Figure()
        for key, meta in models_meta.items():
            vals = [
                meta.get("r2_test", 0) or 0,
                meta.get("r2_cv", 0) or 0,
                meta.get("r2_train", 0) or 0,
                1 - (meta.get("rmse", max_rmse) or max_rmse) / max_rmse,
                1 - (meta.get("mae", max_mae) or max_mae) / max_mae,
            ]
            fig_radar.add_trace(
                go.Scatterpolar(
                    r=vals + [vals[0]],
                    theta=cat_labels + [cat_labels[0]],
                    fill="toself",
                    name=f"{meta['icon']} {meta['short']}",
                    line=dict(color=meta.get("color", "#38bdf8"), width=2),
                    fillcolor=_hex_rgba(meta.get("color", "#38bdf8"), 0.13),
                )
            )
        fig_radar.update_layout(
            **dark_layout(title="Perfil multi-métrica normalizado (mayor = mejor)"),
            polar=dict(
                bgcolor="rgba(0,0,0,0)",
                radialaxis=dict(
                    visible=True,
                    range=[0, 1],
                    gridcolor="rgba(255,255,255,0.08)",
                    color="#475569",
                ),
                angularaxis=dict(gridcolor="rgba(255,255,255,0.08)", color="#94a3b8"),
            ),
            height=400,
        )
        st.plotly_chart(fig_radar, use_container_width=True)

        st.markdown("---")

        # Nota metodológica
        n_train = bundle.get("n_train", "?")
        n_test = bundle.get("n_test", "?")
        gran = bundle.get("granularity", "año")
        st.markdown(
            f"""
            **Metodología:**
            | Parámetro | Valor |
            |---|---|
            | Granularidad | **{gran}** |
            | n entrenamiento | **{n_train:,}**.replace(",",".") |
            | n test (últimos 2 años) | **{n_test:,}**.replace(",",".") |
            | Validación cruzada | 5-fold sobre train set |
            | Variable objetivo | `punt_global` promedio por entidad-año |
            | Features | pct_internet · pct_educacion_sup · promedio_estrato |

            > Split temporal evita data leakage: los últimos 2 años nunca se ven en entrenamiento.
            > Los modelos en el pkl están reentrenados con **todos** los datos.
            """
        )


# ── Instrucciones ──────────────────────────────────────────────────────────────


def _show_train_instructions():
    st.markdown("---")
    st.markdown("#### 📋 Cómo entrenar los modelos")
    st.markdown(
        """
        ```bash
        uv run python scripts/train_simulador.py
        ```
        Entrena Ridge, Random Forest y Gradient Boosting · granularidad colegio×municipio×año ·
        split temporal + CV 5-fold · guarda métricas en el pkl.
        """
    )

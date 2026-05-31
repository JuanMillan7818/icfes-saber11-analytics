"""
HUS-002 · Perfilamiento Dinámico de Afinidades Profesionales
Clasifica el ADN académico institucional o individual en perfiles vocacionales
basado en puntajes históricos por área (Saber 11).

CA-1: Mapeo algorítmico áreas → núcleos de conocimiento (STEM, Humanidades, Salud, Admin, Idiomas)
CA-2: Consistencia histórica vía DuckDB — persistencia del perfil dominante en la serie de tiempo
CA-3: Vista conmutable: Colectivo (institución) vs Individual (estudiante) en Streamlit
CA-4: Diagnóstico ejecutivo con IA Gemini — justificación + recomendaciones pedagógicas/vocacionales
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from icfes.dashboard.components.theme import dark_layout

# ── Áreas evaluadas ───────────────────────────────────────────────────────────

AREAS = ["matematicas", "c_naturales", "lectura_critica", "sociales", "ingles"]

AREA_LABELS = {
    "matematicas": "Matemáticas",
    "c_naturales": "C. Naturales",
    "lectura_critica": "Lectura Crítica",
    "sociales": "Soc. y Ciudadanas",
    "ingles": "Inglés",
}

AREA_COLS = {
    "matematicas": "punt_matematicas",
    "c_naturales": "punt_c_naturales",
    "lectura_critica": "punt_lectura_critica",
    "sociales": "punt_sociales_ciudadanas",
    "ingles": "punt_ingles",
}

# ── Perfiles vocacionales ──────────────────────────────────────────────────────

PERFILES = {
    "STEM": {
        "label": "STEM · Ingenierías y Exactas",
        "icon": "🔬",
        "color": "#38bdf8",
        "carreras": [
            "Ingeniería Civil",
            "Ingeniería de Sistemas",
            "Matemáticas",
            "Física",
            "Computación",
        ],
        "desc": "Fuerte orientación analítica y cuantitativa. Dominio en matemáticas y ciencias exactas.",
    },
    "SALUD": {
        "label": "Salud y Ciencias Biológicas",
        "icon": "🏥",
        "color": "#34d399",
        "carreras": [
            "Medicina",
            "Enfermería",
            "Biología",
            "Química Farmacéutica",
            "Bacteriología",
        ],
        "desc": "Dominio en ciencias naturales combinado con razonamiento crítico aplicado.",
    },
    "HUMANIDADES": {
        "label": "Humanidades, Derecho y Educación",
        "icon": "⚖️",
        "color": "#a78bfa",
        "carreras": [
            "Derecho",
            "Filosofía",
            "Historia",
            "Licenciatura",
            "Trabajo Social",
            "Psicología",
        ],
        "desc": "Alto en comprensión lectora y ciencias sociales — perfil humanístico y jurídico.",
    },
    "ADMIN": {
        "label": "Administración, Economía y Negocios",
        "icon": "💼",
        "color": "#facc15",
        "carreras": [
            "Administración de Empresas",
            "Economía",
            "Contaduría",
            "Finanzas",
            "Gestión Pública",
        ],
        "desc": "Capacidad analítica combinada con comprensión social y organizacional.",
    },
    "IDIOMAS": {
        "label": "Idiomas, Comunicación y RR. Internacionales",
        "icon": "🌐",
        "color": "#f472b6",
        "carreras": [
            "Licenciatura en Idiomas",
            "Relaciones Internacionales",
            "Comunicación Social",
            "Publicidad",
        ],
        "desc": "Dominio lingüístico, pensamiento crítico y orientación global.",
    },
    "GENERALISTA": {
        "label": "Perfil Generalista · Múltiples Áreas",
        "icon": "🎯",
        "color": "#94a3b8",
        "carreras": [
            "Múltiples opciones equilibradas",
            "Proyectos interdisciplinarios",
            "Administración",
            "Educación",
        ],
        "desc": "Desarrollo equilibrado en todas las áreas — versatilidad académica.",
    },
}

# Mapa (area_top1, area_top2) → clave de perfil
_PROFILE_MAP: dict[tuple[str, str], str] = {
    ("matematicas", "c_naturales"): "STEM",
    ("c_naturales", "matematicas"): "STEM",
    ("matematicas", "ingles"): "STEM",
    ("ingles", "matematicas"): "STEM",
    ("c_naturales", "lectura_critica"): "SALUD",
    ("lectura_critica", "c_naturales"): "SALUD",
    ("c_naturales", "sociales"): "SALUD",
    ("sociales", "c_naturales"): "SALUD",
    ("c_naturales", "ingles"): "SALUD",
    ("ingles", "c_naturales"): "SALUD",
    ("lectura_critica", "sociales"): "HUMANIDADES",
    ("sociales", "lectura_critica"): "HUMANIDADES",
    ("matematicas", "lectura_critica"): "HUMANIDADES",
    ("lectura_critica", "matematicas"): "HUMANIDADES",
    ("matematicas", "sociales"): "ADMIN",
    ("sociales", "matematicas"): "ADMIN",
    ("ingles", "lectura_critica"): "IDIOMAS",
    ("lectura_critica", "ingles"): "IDIOMAS",
    ("ingles", "sociales"): "IDIOMAS",
    ("sociales", "ingles"): "IDIOMAS",
}


# ══════════════════════════════════════════════════════════════════════════════
# Clasificación algorítmica (CA-1)
# ══════════════════════════════════════════════════════════════════════════════


def clasificar_perfil(scores: dict[str, float]) -> tuple[str, float]:
    """
    Clasifica el perfil vocacional basado en puntajes promedio por área.
    Returns: (clave_perfil, confianza 0-100)
    """
    valid = {
        k: v for k, v in scores.items() if v is not None and not pd.isna(v) and v > 0
    }
    if len(valid) < 2:
        return "GENERALISTA", 50.0

    ranked = sorted(valid.items(), key=lambda x: x[1], reverse=True)

    # Perfil generalista si el rango entre áreas es muy pequeño
    rango = ranked[0][1] - ranked[-1][1]
    if rango < 2.5:
        return "GENERALISTA", 60.0

    top1, top2 = ranked[0][0], ranked[1][0]
    profile = _PROFILE_MAP.get((top1, top2), "GENERALISTA")

    # Confianza: qué tan dominantes son las 2 primeras áreas vs el resto
    top_sum = ranked[0][1] + ranked[1][1]
    total_sum = sum(v for _, v in ranked)
    confidence = min((top_sum / total_sum * 100) if total_sum > 0 else 50.0, 99.0)

    return profile, confidence


# ══════════════════════════════════════════════════════════════════════════════
# Queries DuckDB (CA-2)
# ══════════════════════════════════════════════════════════════════════════════


@st.cache_data(ttl=600, show_spinner=False)
def _deptos(_svc):
    try:
        df = _svc.query_df(
            "SELECT DISTINCT cole_depto_ubicacion FROM {parquet} "
            "WHERE cole_depto_ubicacion IS NOT NULL AND cole_depto_ubicacion != '' "
            "ORDER BY cole_depto_ubicacion"
        )
        return df["cole_depto_ubicacion"].dropna().tolist()
    except Exception:
        return []


@st.cache_data(ttl=600, show_spinner=False)
def _mcpios(_svc, depto: str):
    try:
        df = _svc.query_df(
            f"""
            SELECT DISTINCT cole_mcpio_ubicacion FROM {{parquet}}
            WHERE cole_depto_ubicacion = '{depto}'
              AND cole_mcpio_ubicacion IS NOT NULL AND cole_mcpio_ubicacion != ''
            ORDER BY cole_mcpio_ubicacion
            """
        )
        return df["cole_mcpio_ubicacion"].dropna().tolist()
    except Exception:
        return []


@st.cache_data(ttl=600, show_spinner=False)
def _colegios(_svc, depto: str, mcpio: str):
    try:
        mcpio_clause = f"AND cole_mcpio_ubicacion = '{mcpio}'" if mcpio else ""
        df = _svc.query_df(
            f"""
            SELECT DISTINCT trim(cole_nombre_establecimiento) AS colegio FROM {{parquet}}
            WHERE cole_depto_ubicacion = '{depto}'
              {mcpio_clause}
              AND cole_nombre_establecimiento IS NOT NULL
              AND cole_nombre_establecimiento != ''
            ORDER BY colegio
            """
        )
        return df["colegio"].dropna().tolist()
    except Exception:
        return []


@st.cache_data(ttl=600, show_spinner=False)
def _perfil_agregado(_svc, where_geo: str, naturaleza_filter: str):
    """Promedios globales por área (todas las cohortes agregadas)."""
    nat_clause = _nat_sql(naturaleza_filter)
    select_areas = ", ".join(
        f"AVG(CASE WHEN isnan(TRY_CAST({col} AS DOUBLE)) THEN NULL"
        f" ELSE TRY_CAST({col} AS DOUBLE) END) AS {key}"
        for key, col in AREA_COLS.items()
    )
    try:
        df = _svc.query_df(
            f"""
            SELECT {select_areas}, COUNT(*) AS n_estudiantes
            FROM {{parquet}}
            WHERE punt_global IS NOT NULL
              {where_geo}{nat_clause}
            """
        )
        if df.empty:
            return None
        return df.iloc[0].to_dict()
    except Exception:
        return None


@st.cache_data(ttl=600, show_spinner=False)
def _perfil_historico(_svc, where_geo: str, naturaleza_filter: str):
    """
    Promedios por área agrupados por año — para análisis de consistencia (CA-2).
    Retorna DataFrame: [periodo, matematicas, c_naturales, lectura_critica, sociales, ingles, n_est]
    """
    nat_clause = _nat_sql(naturaleza_filter)
    select_areas = ", ".join(
        f"AVG(CASE WHEN isnan(TRY_CAST({col} AS DOUBLE)) THEN NULL"
        f" ELSE TRY_CAST({col} AS DOUBLE) END) AS {key}"
        for key, col in AREA_COLS.items()
    )
    try:
        df = _svc.query_df(
            f"""
            SELECT CAST(ano AS INTEGER) AS periodo,
                   {select_areas},
                   COUNT(*) AS n_est
            FROM {{parquet}}
            WHERE ano IS NOT NULL AND punt_global IS NOT NULL
              {where_geo}{nat_clause}
            GROUP BY CAST(ano AS INTEGER)
            HAVING COUNT(*) >= 5
            ORDER BY periodo
            """
        )
        return df if not df.empty else None
    except Exception:
        return None


def _nat_sql(naturaleza_filter: str) -> str:
    if naturaleza_filter == "Oficial":
        return " AND UPPER(cole_naturaleza) = 'OFICIAL'"
    if naturaleza_filter == "No Oficial":
        return " AND UPPER(cole_naturaleza) = 'NO OFICIAL'"
    return ""


def _calcular_persistencia(df_hist: pd.DataFrame) -> tuple[str, float, pd.DataFrame]:
    """
    Para cada periodo determina el perfil dominante.
    Retorna: (perfil_más_frecuente, persistencia_pct, df_con_columna_perfil)
    """
    rows = []
    for _, r in df_hist.iterrows():
        scores = {a: r[a] for a in AREAS if a in r and not pd.isna(r[a])}
        perfil_key, conf = clasificar_perfil(scores)
        rows.append(
            {"periodo": r["periodo"], "perfil_key": perfil_key, "confianza": conf}
        )

    df_per = pd.DataFrame(rows)
    if df_per.empty:
        return "GENERALISTA", 0.0, df_per

    conteo = df_per["perfil_key"].value_counts()
    perfil_dominante = conteo.index[0]
    persistencia = conteo.iloc[0] / len(df_per) * 100

    return perfil_dominante, persistencia, df_per


# ══════════════════════════════════════════════════════════════════════════════
# IA Gemini (CA-4)
# ══════════════════════════════════════════════════════════════════════════════


def _generar_diagnostico_ia(
    modo: str,
    nombre: str,
    perfil_label: str,
    scores: dict[str, float],
    carreras: list[str],
    persistencia: float | None = None,
    municipio: str = "",
) -> str:
    from icfes.dashboard.ai.client import generate, get_gemini_key
    from icfes.dashboard.ai.prompts import perfilamiento as pf_prompts

    if not get_gemini_key():
        return (
            "⚠️ **Diagnóstico IA no disponible.** "
            "Configura `GEMINI_API_KEY` en `.streamlit/secrets.toml`."
        )
    try:
        labeled = {AREA_LABELS.get(k, k): v for k, v in scores.items()}
        if modo == "colectivo":
            prompt = pf_prompts.build_colectivo(
                nombre_institucion=nombre,
                municipio=municipio,
                perfil_label=perfil_label,
                scores=labeled,
                carreras=carreras,
                persistencia=persistencia,
            )
        else:
            prompt = pf_prompts.build_individual(
                perfil_label=perfil_label,
                scores=labeled,
                carreras=carreras,
                persistencia=persistencia,
            )
        return generate(prompt)
    except Exception as e:
        return f"❌ Error al conectar con Gemini: {e}"


# ══════════════════════════════════════════════════════════════════════════════
# Componentes UI
# ══════════════════════════════════════════════════════════════════════════════


def _radar_chart(scores: dict[str, float], color: str, title: str) -> go.Figure:
    labels = [AREA_LABELS[a] for a in AREAS]
    values = [scores.get(a, 0) or 0 for a in AREAS]
    values_closed = values + [values[0]]
    labels_closed = labels + [labels[0]]

    fig = go.Figure()
    fig.add_trace(
        go.Scatterpolar(
            r=values_closed,
            theta=labels_closed,
            fill="toself",
            fillcolor=color,
            line=dict(color=color, width=2),
            name="Puntaje por área",
            hovertemplate="%{theta}: %{r:.1f}<extra></extra>",
        )
    )
    fig.update_layout(
        **dark_layout(title=title),
        polar=dict(
            bgcolor="rgba(10,18,40,0.5)",
            radialaxis=dict(
                visible=True,
                range=[0, max(values) * 1.15 if max(values) > 0 else 100],
                gridcolor="rgba(56,189,248,0.15)",
                tickfont=dict(color="#94a3b8", size=10),
            ),
            angularaxis=dict(
                tickfont=dict(color="#e2e8f0", size=12),
                gridcolor="rgba(56,189,248,0.15)",
            ),
        ),
        showlegend=False,
        height=380,
    )
    return fig


def _perfil_card(perfil_key: str, confianza: float, n_est: int | None = None) -> None:
    info = PERFILES[perfil_key]
    n_txt = (
        f"<br><span style='font-size:0.75rem;color:#64748b'>{int(n_est):,} estudiantes analizados</span>"
        if n_est
        else ""
    )
    st.markdown(
        f"""
        <div class="section-card" style="padding:20px 24px;margin-bottom:16px;
             border-left:4px solid {info['color']};">
            <div style="font-size:2rem;margin-bottom:6px;">{info['icon']}</div>
            <div style="color:{info['color']};font-size:1.1rem;font-weight:700;margin-bottom:4px;">
                {info['label']}
            </div>
            <div style="color:#94a3b8;font-size:0.85rem;margin-bottom:10px;">{info['desc']}</div>
            <div style="color:#64748b;font-size:0.78rem;margin-bottom:8px;">
                Confianza clasificación: <strong style="color:{info['color']}">{confianza:.0f}%</strong>
                {n_txt}
            </div>
            <div style="color:#e2e8f0;font-size:0.82rem;">
                <strong>Carreras afines:</strong><br>
                {'  ·  '.join(info['carreras'][:5])}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _consistencia_chart(df_per: pd.DataFrame) -> go.Figure:
    """Gráfico de barras de perfil dominante por periodo."""
    color_map = {k: v["color"] for k, v in PERFILES.items()}
    label_map = {
        k: v["icon"] + " " + v["label"].split("·")[0].strip()
        for k, v in PERFILES.items()
    }

    df_per["label"] = df_per["perfil_key"].map(label_map)
    df_per["color"] = df_per["perfil_key"].map(color_map)

    fig = go.Figure()
    for perfil_key in df_per["perfil_key"].unique():
        mask = df_per["perfil_key"] == perfil_key
        info = PERFILES[perfil_key]
        sub = df_per[mask]
        fig.add_trace(
            go.Bar(
                x=sub["periodo"].astype(str),
                y=[1] * len(sub),
                name=info["icon"] + " " + info["label"].split("·")[0].strip(),
                marker_color=info["color"],
                hovertemplate=f"Periodo: %{{x}}<br>Perfil: {info['label']}<extra></extra>",
            )
        )

    fig.update_layout(
        **dark_layout(
            title="Perfil dominante por cohorte (CA-2 Consistencia histórica)",
            yaxis=dict(visible=False),
            xaxis=dict(
                title="Periodo (año)",
                tickfont=dict(color="#94a3b8"),
                showgrid=False,
                color="#64748b",
            ),
            legend=dict(
                orientation="h",
                y=-0.25,
                bgcolor="rgba(0,0,0,0)",
                font=dict(color="#94a3b8", size=10),
            ),
        ),
        barmode="stack",
        height=250,
    )
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# Vista Colectiva
# ══════════════════════════════════════════════════════════════════════════════


def _render_colectivo(svc) -> None:
    # Filtros geográficos
    with st.spinner("Cargando departamentos..."):
        deptos = _deptos(svc)

    f1, f2, f3, f4 = st.columns([2, 2, 2, 1])
    with f1:
        sel_depto = st.selectbox(
            "📍 Departamento",
            ["— Nacional —"] + [d.title() for d in deptos],
            key="pf_depto",
        )
    depto_raw = None
    mcpio_raw = None
    colegio_raw = None

    with f2:
        if sel_depto != "— Nacional —":
            depto_raw = next((d for d in deptos if d.title() == sel_depto), sel_depto)
            mcpios = _mcpios(svc, depto_raw)
            sel_mcpio = st.selectbox(
                "🏙️ Municipio",
                ["— Todos —"] + [m.title() for m in mcpios],
                key="pf_mcpio",
            )
            if sel_mcpio != "— Todos —":
                mcpio_raw = next(
                    (m for m in mcpios if m.title() == sel_mcpio), sel_mcpio
                )
        else:
            st.selectbox("🏙️ Municipio", ["— Todos —"], disabled=True, key="pf_mcpio")
            sel_mcpio = "— Todos —"

    with f3:
        if depto_raw and mcpio_raw:
            colegios = _colegios(svc, depto_raw, mcpio_raw)
            sel_colegio = st.selectbox(
                "🏫 Institución (opcional)",
                ["— Todas —"] + colegios,
                key="pf_colegio",
            )
            if sel_colegio != "— Todas —":
                colegio_raw = sel_colegio
        else:
            st.selectbox(
                "🏫 Institución (opcional)",
                ["— Todas —"],
                disabled=True,
                key="pf_colegio",
            )

    with f4:
        naturaleza = st.selectbox(
            "Tipo", ["Todos", "Oficial", "No Oficial"], key="pf_nat"
        )

    # Construir WHERE
    where_parts = []
    if depto_raw:
        where_parts.append(f"AND cole_depto_ubicacion = '{depto_raw}'")
    if mcpio_raw:
        where_parts.append(f"AND cole_mcpio_ubicacion = '{mcpio_raw}'")
    if colegio_raw:
        where_parts.append(f"AND trim(cole_nombre_establecimiento) = '{colegio_raw}'")
    where_geo = " ".join(where_parts)

    st.markdown('<div class="grad-divider"></div>', unsafe_allow_html=True)

    # Calcular perfil agregado
    with st.spinner("⚙️ Calculando perfil de afinidad..."):
        data = _perfil_agregado(svc, where_geo, naturaleza)
        df_hist = _perfil_historico(svc, where_geo, naturaleza)

    if data is None:
        st.info("Sin datos suficientes para el filtro seleccionado.")
        return

    scores = {a: data.get(a) for a in AREAS}
    n_est = int(data.get("n_estudiantes", 0))
    perfil_key, confianza = clasificar_perfil(scores)
    info = PERFILES[perfil_key]

    # KPIs de área
    k_cols = st.columns(5)
    for i, area in enumerate(AREAS):
        val = scores.get(area)
        k_cols[i].metric(
            AREA_LABELS[area],
            f"{val:.1f}" if val is not None else "N/A",
        )

    st.markdown('<div class="grad-divider"></div>', unsafe_allow_html=True)

    # Radar + perfil card
    col_radar, col_card = st.columns([3, 2], gap="large")
    with col_radar:
        nombre_lugar = colegio_raw or sel_mcpio or sel_depto
        fig = _radar_chart(scores, info["color"], f"Perfil de Áreas · {nombre_lugar}")
        st.plotly_chart(fig, use_container_width=True)

    with col_card:
        st.markdown("#### Perfil Dominante")
        _perfil_card(perfil_key, confianza, n_est)

    # Consistencia histórica (CA-2)
    if df_hist is not None and len(df_hist) >= 2:
        st.markdown('<div class="grad-divider"></div>', unsafe_allow_html=True)
        st.markdown("#### 📅 Consistencia Histórica del Perfil (CA-2)")

        perfil_hist_key, persistencia, df_per = _calcular_persistencia(df_hist)
        hist_info = PERFILES[perfil_hist_key]

        h1, h2, h3 = st.columns(3)
        h1.metric("Periodos analizados", f"{len(df_hist)}")
        h2.metric(
            "Perfil histórico dominante",
            hist_info["icon"] + " " + hist_info["label"].split("·")[0].strip(),
        )
        h3.metric(
            "Persistencia",
            f"{persistencia:.0f}%",
            help="% de cohortes en que este perfil fue el dominante",
        )

        st.plotly_chart(_consistencia_chart(df_per), use_container_width=True)

        # Evolución de puntajes por área
        with st.expander("📊 Ver evolución de puntajes por área"):
            fig_evo = go.Figure()
            for area in AREAS:
                if area in df_hist.columns:
                    fig_evo.add_trace(
                        go.Scatter(
                            x=df_hist["periodo"].astype(str),
                            y=df_hist[area],
                            name=AREA_LABELS[area],
                            mode="lines+markers",
                            hovertemplate=f"{AREA_LABELS[area]}<br>Año: %{{x}}<br>Prom: %{{y:.1f}}<extra></extra>",
                        )
                    )
            fig_evo.update_layout(
                **dark_layout(
                    title="Evolución histórica de puntajes por área",
                    yaxis=dict(title="Puntaje promedio"),
                    xaxis=dict(title="Cohorte"),
                ),
                height=350,
            )
            st.plotly_chart(fig_evo, use_container_width=True)
    else:
        persistencia = None

    st.markdown('<div class="grad-divider"></div>', unsafe_allow_html=True)

    # Diagnóstico IA (CA-4)
    st.markdown("#### 🤖 Diagnóstico IA · Gemini (CA-4)")
    from icfes.dashboard.ai.client import get_gemini_key

    has_key = get_gemini_key() is not None
    if not has_key:
        st.info(
            "🔑 Agrega `GEMINI_API_KEY` en `.streamlit/secrets.toml` para habilitar el diagnóstico IA."
        )

    col_btn, _ = st.columns([1, 3])
    with col_btn:
        btn_ia = st.button(
            "🔍 Generar Diagnóstico IA",
            disabled=not has_key,
            key="pf_btn_ia_col",
        )

    if "pf_ia_col" not in st.session_state:
        st.session_state["pf_ia_col"] = ""

    if btn_ia:
        with st.spinner("Consultando Gemini..."):
            nombre_lugar = colegio_raw or (
                sel_mcpio if sel_mcpio != "— Todos —" else sel_depto
            )
            st.session_state["pf_ia_col"] = _generar_diagnostico_ia(
                modo="colectivo",
                nombre=nombre_lugar,
                municipio=sel_mcpio if sel_mcpio != "— Todos —" else sel_depto,
                perfil_label=info["label"],
                scores={k: v for k, v in scores.items() if v is not None},
                carreras=info["carreras"],
                persistencia=persistencia,
            )

    if st.session_state["pf_ia_col"]:
        st.markdown(
            f"""
            <div class="section-card" style="padding:16px 20px;margin-top:12px;
                 border-left:4px solid {info['color']};">
                <div style="color:{info['color']};font-size:0.8rem;font-weight:700;margin-bottom:8px;">
                    🤖 DIAGNÓSTICO IA · {info['icon']} {info['label']}
                </div>
                <div style="color:#e2e8f0;font-size:0.9rem;line-height:1.6;white-space:pre-wrap;">
                    {st.session_state['pf_ia_col']}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ══════════════════════════════════════════════════════════════════════════════
# Vista Individual (CA-3 simulador)
# ══════════════════════════════════════════════════════════════════════════════


def _render_individual() -> None:
    st.markdown(
        """
        <div style="color:#64748b;font-size:0.85rem;margin-bottom:16px;">
            Ingresa tus puntajes Saber 11 por área (escala 0–100 por defecto post-2014).
            El sistema identificará tu perfil vocacional al instante.
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_inp, col_out = st.columns([2, 3], gap="large")

    with col_inp:
        st.markdown("#### 📝 Mis puntajes")
        scores_ind = {}
        defaults = {
            "matematicas": 50,
            "c_naturales": 50,
            "lectura_critica": 50,
            "sociales": 50,
            "ingles": 50,
        }
        for area in AREAS:
            val = st.number_input(
                AREA_LABELS[area],
                min_value=0,
                max_value=100,
                value=defaults[area],
                step=1,
                key=f"pf_ind_{area}",
            )
            scores_ind[area] = float(val)

    perfil_key_ind, confianza_ind = clasificar_perfil(scores_ind)
    info_ind = PERFILES[perfil_key_ind]

    with col_out:
        st.markdown("#### Tu perfil vocacional")
        _perfil_card(perfil_key_ind, confianza_ind)
        fig_ind = _radar_chart(
            scores_ind, info_ind["color"], "Mapa de Fortalezas por Área"
        )
        st.plotly_chart(fig_ind, use_container_width=True)

    st.markdown('<div class="grad-divider"></div>', unsafe_allow_html=True)

    # Carreras ordenadas por afinidad (todos los perfiles)
    with st.expander("🎓 Ver afinidad con todos los perfiles"):
        # Score de afinidad por perfil = promedio de top-2 areas de cada perfil
        area_vals = scores_ind
        _PERFIL_AREAS = {
            "STEM": ["matematicas", "c_naturales"],
            "SALUD": ["c_naturales", "matematicas"],
            "HUMANIDADES": ["lectura_critica", "sociales"],
            "ADMIN": ["matematicas", "sociales"],
            "IDIOMAS": ["ingles", "lectura_critica"],
            "GENERALISTA": list(AREAS),
        }
        filas = []
        for pk, areas_p in _PERFIL_AREAS.items():
            afinidad = sum(area_vals.get(a, 0) for a in areas_p) / len(areas_p)
            filas.append(
                {
                    "Perfil": PERFILES[pk]["icon"] + " " + PERFILES[pk]["label"],
                    "Afinidad": round(afinidad, 1),
                }
            )
        df_af = (
            pd.DataFrame(filas)
            .sort_values("Afinidad", ascending=False)
            .reset_index(drop=True)
        )
        df_af.insert(0, "#", range(1, len(df_af) + 1))
        st.dataframe(df_af, use_container_width=True, hide_index=True)

    st.markdown('<div class="grad-divider"></div>', unsafe_allow_html=True)

    # Diagnóstico IA individual (CA-4)
    st.markdown("#### 🤖 Orientación Vocacional con IA (CA-4)")
    from icfes.dashboard.ai.client import get_gemini_key

    has_key = get_gemini_key() is not None
    if not has_key:
        st.info("🔑 Agrega `GEMINI_API_KEY` en `.streamlit/secrets.toml`.")

    col_btn2, _ = st.columns([1, 3])
    with col_btn2:
        btn_ia_ind = st.button(
            "🔍 Obtener Orientación IA",
            disabled=not has_key,
            key="pf_btn_ia_ind",
        )

    if "pf_ia_ind" not in st.session_state:
        st.session_state["pf_ia_ind"] = ""

    if btn_ia_ind:
        with st.spinner("Consultando Gemini..."):
            st.session_state["pf_ia_ind"] = _generar_diagnostico_ia(
                modo="individual",
                nombre="Estudiante",
                perfil_label=info_ind["label"],
                scores=scores_ind,
                carreras=info_ind["carreras"],
            )

    if st.session_state["pf_ia_ind"]:
        st.markdown(
            f"""
            <div class="section-card" style="padding:16px 20px;margin-top:12px;
                 border-left:4px solid {info_ind['color']};">
                <div style="color:{info_ind['color']};font-size:0.8rem;font-weight:700;margin-bottom:8px;">
                    🤖 ORIENTACIÓN VOCACIONAL IA · {info_ind['icon']} {info_ind['label']}
                </div>
                <div style="color:#e2e8f0;font-size:0.9rem;line-height:1.6;white-space:pre-wrap;">
                    {st.session_state['pf_ia_ind']}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ══════════════════════════════════════════════════════════════════════════════
# Render principal
# ══════════════════════════════════════════════════════════════════════════════


def render(svc=None) -> None:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        """
        <div class="hero-badge">🧬 Perfilamiento Vocacional</div>
        <div class="section-heading">Perfilamiento de Afinidad Profesional · HUS-002</div>
        <div style="color:#64748b;font-size:0.9rem;margin-bottom:20px;">
            Identifica el ADN académico colectivo o individual basado en el desempeño histórico
            por área Saber 11. Orientación vocacional y planificación de oferta educativa con datos duros.
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Toggle colectivo / individual (CA-3)
    modo = st.radio(
        "Vista",
        ["🏫 Colectivo · Institución / Territorio", "👤 Individual · Estudiante"],
        horizontal=True,
        key="pf_modo",
        label_visibility="collapsed",
    )

    st.markdown('<div class="grad-divider"></div>', unsafe_allow_html=True)

    if modo.startswith("🏫"):
        if svc is None:
            st.warning("⚠️ Servicio de datos no disponible.")
            return
        _render_colectivo(svc)
    else:
        _render_individual()

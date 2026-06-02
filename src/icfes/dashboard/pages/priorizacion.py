"""
HUS-001 · Tablero de Priorización de Intervención Institucional
Índice de Priorización Educativa (IPE) multivariable con IA Gemini + PDF ejecutivo.

Componentes del IPE (escala 0–100, donde 100 = máxima urgencia):
  • Deterioro Académico Histórico  40 %  (pendiente PUNT_GLOBAL por año)
  • Brecha Digital Colectiva       30 %  (% sin internet en el hogar)
  • Vulnerabilidad Familiar        30 %  (% padres/madres sin educación básica)
"""

from __future__ import annotations

import io

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from icfes.dashboard.components.theme import dark_layout

# ── Constantes IPE ────────────────────────────────────────────────────────────
W_DETERIORO = 0.40
W_DIGITAL = 0.30
W_VULNERABILIDAD = 0.30

_CUADRANTES = [
    (80, 100, "🔴 Prioridad Crítica", "#f43f5e"),
    (50, 79, "🟡 Vulnerabilidad Estructural", "#facc15"),
    (0, 49, "🟢 Monitoreo Preventivo", "#34d399"),
]

# ── Educación básica (sin ella = vulnerable) ──────────────────────────────────
_EDUC_VULNERABLE = {
    "Ninguno",
    "Primaria incompleta",
    "Primaria completa",
    "Secundaria (Bachillerato) incompleta",
    "No sabe",
    "No Aplica",
}


# ══════════════════════════════════════════════════════════════════════════════
# Queries DuckDB (cached)
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
              AND cole_mcpio_ubicacion IS NOT NULL
            ORDER BY cole_mcpio_ubicacion
            """
        )
        return df["cole_mcpio_ubicacion"].dropna().tolist()
    except Exception:
        return []


@st.cache_data(ttl=600, show_spinner=False)
def _calcular_ipe(_svc, where_geo: str, naturaleza_filter: str):
    """
    Calcula el IPE para cada institución en la región seleccionada.
    Devuelve DataFrame con columnas:
      cole_nombre_establecimiento, cole_mcpio_ubicacion, IPE,
      score_deterioro, score_digital, score_vulnerabilidad, n_estudiantes
    """
    nat_clause = ""
    if naturaleza_filter == "Oficial":
        nat_clause = " AND UPPER(cole_naturaleza) = 'OFICIAL'"
    elif naturaleza_filter == "No Oficial":
        nat_clause = " AND UPPER(cole_naturaleza) = 'NO OFICIAL'"

    try:
        # ── 1. Promedios anuales por institución (deterioro) ──────────────────
        df_trend = _svc.query_df(
            f"""
            SELECT
                trim(cole_nombre_establecimiento) AS colegio,
                cole_mcpio_ubicacion              AS municipio,
                CAST(ano AS INTEGER)              AS ano,
                AVG(TRY_CAST(punt_global AS DOUBLE)) AS prom
            FROM {{parquet}}
            WHERE cole_nombre_establecimiento IS NOT NULL
              AND punt_global IS NOT NULL
              AND cole_nombre_establecimiento != ''
              {where_geo}{nat_clause}
            GROUP BY trim(cole_nombre_establecimiento), cole_mcpio_ubicacion, CAST(ano AS INTEGER)
            HAVING COUNT(*) >= 5
            ORDER BY colegio, municipio, ano
            """
        )

        # ── 2. Brecha digital + vulnerabilidad por institución ─────────────────
        df_soc = _svc.query_df(
            f"""
            SELECT
                trim(cole_nombre_establecimiento) AS colegio,
                cole_mcpio_ubicacion              AS municipio,
                COUNT(*)                          AS n_total,
                SUM(CASE WHEN UPPER(fami_tieneinternet) = 'NO' THEN 1 ELSE 0 END) AS n_sin_internet,
                SUM(CASE WHEN fami_educacionpadre IN (
                    'Ninguno','Primaria incompleta','Primaria completa',
                    'Secundaria (Bachillerato) incompleta','No sabe','No Aplica'
                ) OR fami_educacionmadre IN (
                    'Ninguno','Primaria incompleta','Primaria completa',
                    'Secundaria (Bachillerato) incompleta','No sabe','No Aplica'
                ) THEN 1 ELSE 0 END) AS n_vulnerable_educ
            FROM {{parquet}}
            WHERE cole_nombre_establecimiento IS NOT NULL AND cole_nombre_establecimiento != ''
              {where_geo}{nat_clause}
            GROUP BY trim(cole_nombre_establecimiento), cole_mcpio_ubicacion
            HAVING COUNT(*) >= 5
            """
        )

        if df_trend.empty or df_soc.empty:
            return None

        # ── 3. Calcular pendiente de deterioro por institución ─────────────────
        from scipy.stats import linregress  # type: ignore

        slopes = {}
        for (col, mun), grp in df_trend.groupby(["colegio", "municipio"]):
            if len(grp) >= 2:
                slope, *_ = linregress(grp["ano"], grp["prom"])
                slopes[(col, mun)] = slope
            else:
                slopes[(col, mun)] = 0.0

        df_soc["slope"] = df_soc.apply(
            lambda r: slopes.get((r["colegio"], r["municipio"]), 0.0), axis=1
        )
        df_soc["pct_sin_internet"] = (
            df_soc["n_sin_internet"] / df_soc["n_total"].clip(lower=1) * 100
        )
        df_soc["pct_vulnerable_educ"] = (
            df_soc["n_vulnerable_educ"] / df_soc["n_total"].clip(lower=1) * 100
        )

        # ── 4. Normalizar (min-max) ────────────────────────────────────────────
        def norm_inverted(s: pd.Series) -> pd.Series:
            """Mayor pendiente positiva → menor riesgo; invierte para IPE."""
            mn, mx = s.min(), s.max()
            if mx == mn:
                return pd.Series(50.0, index=s.index)
            normed = (s - mn) / (mx - mn) * 100
            return 100 - normed  # invertir: caída = mayor riesgo

        def norm(s: pd.Series) -> pd.Series:
            mn, mx = s.min(), s.max()
            if mx == mn:
                return pd.Series(50.0, index=s.index)
            return (s - mn) / (mx - mn) * 100

        df_soc["s_deterioro"] = norm_inverted(df_soc["slope"]).round(1)
        df_soc["s_digital"] = norm(df_soc["pct_sin_internet"]).round(1)
        df_soc["s_vulnerabilidad"] = norm(df_soc["pct_vulnerable_educ"]).round(1)

        df_soc["IPE"] = (
            W_DETERIORO * df_soc["s_deterioro"]
            + W_DIGITAL * df_soc["s_digital"]
            + W_VULNERABILIDAD * df_soc["s_vulnerabilidad"]
        ).round(1)

        result = df_soc[
            [
                "colegio",
                "municipio",
                "IPE",
                "s_deterioro",
                "s_digital",
                "s_vulnerabilidad",
                "n_total",
                "pct_sin_internet",
                "pct_vulnerable_educ",
            ]
        ].rename(
            columns={
                "colegio": "Institución",
                "municipio": "Municipio",
                "s_deterioro": "Deterioro",
                "s_digital": "Brecha Digital",
                "s_vulnerabilidad": "Vulnerabilidad",
                "n_total": "Estudiantes",
                "pct_sin_internet": "% Sin Internet",
                "pct_vulnerable_educ": "% Vulnerable Educ.",
            }
        )

        return result.sort_values("IPE", ascending=False).reset_index(drop=True)

    except Exception as e:
        st.error(f"Error calculando IPE: {e}")
        return None


# ══════════════════════════════════════════════════════════════════════════════
# IA Gemini
# ══════════════════════════════════════════════════════════════════════════════


def _generar_analisis_ia(
    nombre: str, municipio: str, ipe: float, pct_internet: float, pct_educ: float
) -> str:
    from icfes.dashboard.ai.client import generate, get_gemini_key
    from icfes.dashboard.ai.prompts import priorizacion as pri_prompts

    if not get_gemini_key():
        return (
            "⚠️ **Análisis IA no disponible.** Configura `GEMINI_API_KEY` en "
            "`.streamlit/secrets.toml` para habilitar el diagnóstico automático."
        )
    try:
        prompt = pri_prompts.build_intervencion_ipe(
            nombre=nombre,
            municipio=municipio,
            ipe=ipe,
            pct_internet=pct_internet,
            pct_educ_basica=pct_educ,
        )
        return generate(prompt)
    except Exception as e:
        return f"❌ Error al conectar con Gemini: {e}"


# ══════════════════════════════════════════════════════════════════════════════
# PDF Ejecutivo (ReportLab)
# ══════════════════════════════════════════════════════════════════════════════


def _generar_pdf(filtro: str, df_top5: pd.DataFrame, analisis_ia: str) -> bytes:
    from reportlab.lib import colors  # type: ignore
    from reportlab.lib.pagesizes import letter  # type: ignore
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # type: ignore
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle  # type: ignore

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
    )
    story = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=20,
        textColor=colors.HexColor("#1A365D"),
        spaceAfter=12,
    )
    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        textColor=colors.HexColor("#4A5568"),
        spaceAfter=18,
    )
    h2_style = ParagraphStyle(
        "SectionHeader",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        textColor=colors.HexColor("#2C5282"),
        spaceAfter=8,
    )
    body_style = ParagraphStyle(
        "BodyTextCustom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#2D3748"),
        spaceAfter=10,
    )

    # Encabezado
    story.append(Paragraph("REPORTE EJECUTIVO DE PRIORIZACIÓN EDUCATIVA", title_style))
    story.append(
        Paragraph(
            f"Filtro Territorial: {filtro} | Generado automáticamente por EduMetrics Saber11",
            subtitle_style,
        )
    )
    story.append(Spacer(1, 8))

    # Tabla Top 5
    story.append(Paragraph("1. Instituciones de Mayor Urgencia (Top 5)", h2_style))
    story.append(
        Paragraph(
            "Establecimientos con mayor Índice de Priorización Educativa (IPE). "
            "100 pts = máxima urgencia de intervención.",
            body_style,
        )
    )

    tabla_data = [["#", "Institución Educativa", "Municipio", "IPE", "% Sin Internet"]]
    for i, row in df_top5.iterrows():
        tabla_data.append(
            [
                str(i + 1),
                str(row["Institución"])[:45],
                str(row["Municipio"]).title()[:20],
                f"{row['IPE']:.1f}",
                f"{row['% Sin Internet']:.1f}%",
            ]
        )

    t = Table(tabla_data, colWidths=[30, 220, 120, 55, 80])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1A365D")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9.5),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 7),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F7FAFC")),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.HexColor("#F7FAFC"), colors.white],
                ),
                ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor("#2D3748")),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 9),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("ALIGN", (3, 0), (4, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(t)
    story.append(Spacer(1, 18))

    # Diagnóstico IA
    story.append(
        Paragraph("2. Diagnóstico Estratégico y Plan de Acción (IA)", h2_style)
    )
    clean_text = analisis_ia.replace("**", "").replace("*", "")
    for parrafo in clean_text.split("\n\n"):
        if parrafo.strip():
            story.append(Paragraph(parrafo.replace("\n", " "), body_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


# ══════════════════════════════════════════════════════════════════════════════
# Helpers UI
# ══════════════════════════════════════════════════════════════════════════════


def _semaforo_color(ipe: float) -> str:
    if ipe >= 80:
        return "#f43f5e"
    elif ipe >= 50:
        return "#facc15"
    return "#34d399"


def _semaforo_label(ipe: float) -> str:
    if ipe >= 80:
        return "🔴 Crítica"
    elif ipe >= 50:
        return "🟡 Estructural"
    return "🟢 Preventivo"


# ══════════════════════════════════════════════════════════════════════════════
# Análisis de sensibilidad de pesos
# ══════════════════════════════════════════════════════════════════════════════

_ESCENARIOS_PESOS = {
    "Base (40/30/30)": (0.400, 0.300, 0.300),
    "Det+10 (50/25/25)": (0.500, 0.250, 0.250),
    "Det-10 (30/35/35)": (0.300, 0.350, 0.350),
    "Dig+10 (35/40/25)": (0.350, 0.400, 0.250),
    "Dig-10 (45/20/35)": (0.450, 0.200, 0.350),
    "Vul+10 (35/25/40)": (0.350, 0.250, 0.400),
    "Vul-10 (45/35/20)": (0.450, 0.350, 0.200),
    "Iguales (33/33/33)": (0.333, 0.333, 0.333),
}


def _sensibilidad_pesos(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula correlación de Spearman entre el ranking base y cada escenario de pesos.
    Devuelve DataFrame con columnas: Escenario, w_det, w_dig, w_vul, IPE_medio, r_spearman, Estabilidad.
    """
    from scipy.stats import spearmanr  # type: ignore

    base_ipe = (
        W_DETERIORO * df["Deterioro"]
        + W_DIGITAL * df["Brecha Digital"]
        + W_VULNERABILIDAD * df["Vulnerabilidad"]
    )
    base_rank = base_ipe.rank(ascending=False)

    rows = []
    for nombre, (wd, wdg, wv) in _ESCENARIOS_PESOS.items():
        ipe_alt = (
            wd * df["Deterioro"]
            + wdg * df["Brecha Digital"]
            + wv * df["Vulnerabilidad"]
        )
        rank_alt = ipe_alt.rank(ascending=False)
        r, _ = spearmanr(base_rank, rank_alt)
        rows.append(
            {
                "Escenario": nombre,
                "w_Deterioro": f"{wd:.0%}",
                "w_Digital": f"{wdg:.0%}",
                "w_Vulnerab.": f"{wv:.0%}",
                "IPE medio": round(ipe_alt.mean(), 1),
                "r Spearman": round(r, 4),
                "Estabilidad": (
                    "🟢 Alta"
                    if r >= 0.95
                    else "🟡 Moderada" if r >= 0.85 else "🔴 Baja"
                ),
            }
        )
    return pd.DataFrame(rows)


def _ranking_top_n_por_escenario(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """Tabla: top-N instituciones base vs su puesto en cada escenario alternativo."""
    base_ipe = (
        W_DETERIORO * df["Deterioro"]
        + W_DIGITAL * df["Brecha Digital"]
        + W_VULNERABILIDAD * df["Vulnerabilidad"]
    )
    base_order = base_ipe.rank(ascending=False, method="min").astype(int)
    top_idx = base_ipe.nlargest(n).index
    top_names = df.loc[top_idx, "Institución"].values

    result = {"Institución": top_names, "Puesto base": range(1, n + 1)}
    for nombre, (wd, wdg, wv) in _ESCENARIOS_PESOS.items():
        if "Base" in nombre:
            continue
        ipe_alt = (
            wd * df["Deterioro"]
            + wdg * df["Brecha Digital"]
            + wv * df["Vulnerabilidad"]
        )
        rank_alt = ipe_alt.rank(ascending=False, method="min").astype(int)
        result[nombre] = rank_alt.loc[top_idx].values

    return pd.DataFrame(result)


# ══════════════════════════════════════════════════════════════════════════════
# Render principal
# ══════════════════════════════════════════════════════════════════════════════


def render(svc=None):
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        """
        <div class="hero-badge">🏆 Priorización Educativa</div>
        <div class="section-heading">Ranking de Intervención Institucional · IPE</div>
        <div style="color:#64748b;font-size:0.9rem;margin-bottom:20px;">
            Identifica con precisión científica qué instituciones requieren intervención
            urgente, combinando deterioro académico, brecha digital y vulnerabilidad familiar.
        </div>
        """,
        unsafe_allow_html=True,
    )

    if svc is None:
        st.warning("⚠️ Servicio de datos no disponible.")
        return

    # ── Filtros ───────────────────────────────────────────────────────────────
    with st.spinner("Cargando departamentos..."):
        deptos = _deptos(svc)

    f1, f2, f3 = st.columns([2, 2, 1])
    with f1:
        sel_depto = st.selectbox(
            "📍 Departamento",
            ["— Nacional —"] + [d.title() for d in deptos],
            key="ipe_depto",
        )
    with f2:
        if sel_depto != "— Nacional —":
            depto_raw = next((d for d in deptos if d.title() == sel_depto), sel_depto)
            mcpios = _mcpios(svc, depto_raw)
            sel_mcpio = st.selectbox(
                "🏙️ Municipio",
                ["— Todos —"] + [m.title() for m in mcpios],
                key="ipe_mcpio",
            )
        else:
            depto_raw = None
            sel_mcpio = "— Todos —"
            st.selectbox("🏙️ Municipio", ["— Todos —"], disabled=True, key="ipe_mcpio")
    with f3:
        naturaleza = st.selectbox(
            "🏫 Tipo",
            ["Todos", "Oficial", "No Oficial"],
            key="ipe_naturaleza",
        )

    # Construir cláusula WHERE
    where_parts = []
    if depto_raw:
        where_parts.append(f"AND cole_depto_ubicacion = '{depto_raw}'")
    if sel_mcpio != "— Todos —" and depto_raw:
        mcpio_raw = next(
            (m for m in _mcpios(svc, depto_raw) if m.title() == sel_mcpio),
            sel_mcpio,
        )
        where_parts.append(f"AND cole_mcpio_ubicacion = '{mcpio_raw}'")
    where_geo = " ".join(where_parts)

    # Etiqueta del filtro (para PDF)
    filtro_label = sel_depto
    if sel_mcpio != "— Todos —":
        filtro_label += f" / {sel_mcpio}"

    st.markdown('<div class="grad-divider"></div>', unsafe_allow_html=True)

    # ── Calcular IPE ──────────────────────────────────────────────────────────
    with st.spinner("⚙️ Calculando Índice de Priorización Educativa..."):
        df_ipe = _calcular_ipe(svc, where_geo, naturaleza)

    if df_ipe is None or df_ipe.empty:
        st.info(
            "Sin datos suficientes para el filtro seleccionado. "
            "Prueba seleccionar un departamento o municipio con más registros."
        )
        return

    # ── KPIs resumen ──────────────────────────────────────────────────────────
    n_criticas = (df_ipe["IPE"] >= 80).sum()
    n_estructural = ((df_ipe["IPE"] >= 50) & (df_ipe["IPE"] < 80)).sum()
    n_preventivo = (df_ipe["IPE"] < 50).sum()
    ipe_promedio = df_ipe["IPE"].mean()

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("📊 Total instituciones", f"{len(df_ipe):,}")
    k2.metric(
        "🔴 Prioridad Crítica",
        str(n_criticas),
        help="IPE ≥ 80 pts — intervención inmediata",
    )
    k3.metric(
        "🟡 Vulnerabilidad Estructural",
        str(n_estructural),
        help="IPE 50–79 pts",
    )
    k4.metric("🟢 Monitoreo Preventivo", str(n_preventivo), help="IPE < 50 pts")

    st.markdown('<div class="grad-divider"></div>', unsafe_allow_html=True)

    # ── Tabla ranking ─────────────────────────────────────────────────────────
    st.markdown("#### 🏆 Ranking de Priorización (Top 50)")
    st.caption(
        "Ordenado de mayor a menor urgencia. IPE 0–100 donde 100 = máxima urgencia de intervención."
    )

    df_display = df_ipe.head(50).copy()
    df_display.insert(0, "Puesto", range(1, len(df_display) + 1))
    df_display["Cuadrante"] = df_display["IPE"].apply(_semaforo_label)
    df_display["Municipio"] = df_display["Municipio"].str.title()

    # Formateo de columnas numéricas
    for col in ["Deterioro", "Brecha Digital", "Vulnerabilidad"]:
        df_display[col] = df_display[col].map(lambda x: f"{x:.1f}")
    df_display["% Sin Internet"] = df_display["% Sin Internet"].map(
        lambda x: f"{x:.1f}%"
    )
    df_display["% Vulnerable Educ."] = df_display["% Vulnerable Educ."].map(
        lambda x: f"{x:.1f}%"
    )
    df_display["Estudiantes"] = df_display["Estudiantes"].map(lambda x: f"{int(x):,}")

    cols_show = [
        "Puesto",
        "Institución",
        "Municipio",
        "IPE",
        "Cuadrante",
        "Deterioro",
        "Brecha Digital",
        "Vulnerabilidad",
        "% Sin Internet",
        "% Vulnerable Educ.",
        "Estudiantes",
    ]

    def color_ipe(val):
        try:
            v = float(val)
        except (TypeError, ValueError):
            return ""
        c = _semaforo_color(v)
        return f"color:{c};font-weight:700"

    styled = df_display[cols_show].style.map(color_ipe, subset=["IPE"])
    st.dataframe(styled, use_container_width=True, hide_index=True)

    # ── Gráfico scatter IPE ───────────────────────────────────────────────────
    st.markdown("#### 📊 Distribución del IPE por Institución")
    df_plot = df_ipe.head(50).copy()
    df_plot["Color"] = df_plot["IPE"].apply(_semaforo_color)
    df_plot["Cuadrante"] = df_plot["IPE"].apply(_semaforo_label)
    df_plot["Municipio"] = df_plot["Municipio"].str.title()

    fig = px.scatter(
        df_plot,
        x="Brecha Digital",
        y="Deterioro",
        size="IPE",
        color="Cuadrante",
        color_discrete_map={
            "🔴 Crítica": "#f43f5e",
            "🟡 Estructural": "#facc15",
            "🟢 Preventivo": "#34d399",
        },
        hover_name="Institución",
        hover_data={
            "Municipio": True,
            "IPE": ":.1f",
            "% Sin Internet": ":.1f",
            "Cuadrante": False,
        },
        labels={
            "Brecha Digital": "Score Brecha Digital (0–100)",
            "Deterioro": "Score Deterioro Académico (0–100)",
        },
        size_max=30,
    )
    fig.update_layout(**dark_layout(title="Mapa de Riesgo Educativo"))
    st.plotly_chart(fig, use_container_width=True)

    # ── Guía de interpretación ────────────────────────────────────────────────
    with st.expander("📖 ¿Cómo se interpreta el IPE?", expanded=False):
        st.markdown(
            """
            ### Índice de Priorización Educativa (IPE)
            El IPE se normaliza en escala **0 a 100 puntos**, donde **100 = máxima urgencia de intervención**.

            | Componente | Peso | Variable de origen |
            |---|---|---|
            | Deterioro Académico Histórico | **40 %** | Pendiente de `PUNT_GLOBAL` por año |
            | Brecha Digital Colectiva | **30 %** | `FAMI_TIENEINTERNET = 'No'` |
            | Vulnerabilidad Familiar | **30 %** | `FAMI_EDUCACIONPADRE` / `FAMI_EDUCACIONMADRE` < básica |

            ### Cuadrantes de Acción
            | Rango | Clasificación | Acción recomendada |
            |---|---|---|
            | 80–100 pts | 🔴 **Prioridad Crítica** | Planes de choque inmediatos, auditorías pedagógicas, presupuesto de conectividad prioritario |
            | 50–79 pts | 🟡 **Vulnerabilidad Estructural** | Seguimiento semestral, refuerzo tecnológico, programas de padres |
            | 0–49 pts | 🟢 **Monitoreo Preventivo** | Mantenimiento de indicadores, buenas prácticas replicables |

            > **Nota técnica:** La pendiente de deterioro se calcula con regresión lineal sobre los últimos periodos disponibles.
            > Un colegio con caída sistemática puntúa más alto en riesgo que uno bajo pero estable.
            """
        )

    st.markdown('<div class="grad-divider"></div>', unsafe_allow_html=True)

    # ── Análisis IA por institución ───────────────────────────────────────────
    st.markdown("#### 🤖 Diagnóstico IA por Institución")

    from icfes.dashboard.ai.client import get_gemini_key

    has_key = get_gemini_key() is not None
    if not has_key:
        st.info(
            "🔑 **Análisis IA deshabilitado.** Agrega tu `GEMINI_API_KEY` en "
            "`.streamlit/secrets.toml` para habilitar el diagnóstico automático."
        )

    opciones_inst = df_ipe["Institución"].tolist()
    sel_inst_idx = st.selectbox(
        "🏫 Selecciona institución para diagnóstico",
        options=range(len(opciones_inst)),
        format_func=lambda i: f"#{i+1} · {opciones_inst[i]} ({df_ipe['Municipio'].iloc[i].title()})",
        key="ipe_inst_sel",
    )

    row_sel = df_ipe.iloc[sel_inst_idx]
    c_info1, c_info2, c_info3 = st.columns(3)
    c_info1.metric("IPE", f"{row_sel['IPE']:.1f}", help=_semaforo_label(row_sel["IPE"]))
    c_info2.metric("% Sin Internet", f"{row_sel['% Sin Internet']:.1f}%")
    c_info3.metric("% Vulnerable Educ.", f"{row_sel['% Vulnerable Educ.']:.1f}%")

    col_btn, _ = st.columns([1, 3])
    with col_btn:
        analizar_btn = st.button(
            "🔍 Generar Diagnóstico IA",
            disabled=not has_key,
            key="btn_ia",
        )

    if "ia_resultado" not in st.session_state:
        st.session_state["ia_resultado"] = ""
    if "ia_inst" not in st.session_state:
        st.session_state["ia_inst"] = ""

    if analizar_btn:
        with st.spinner("Consultando Gemini..."):
            resultado = _generar_analisis_ia(
                nombre=row_sel["Institución"],
                municipio=str(row_sel["Municipio"]).title(),
                ipe=float(row_sel["IPE"]),
                pct_internet=float(row_sel["% Sin Internet"]),
                pct_educ=float(row_sel["% Vulnerable Educ."]),
            )
            st.session_state["ia_resultado"] = resultado
            st.session_state["ia_inst"] = row_sel["Institución"]

    if st.session_state["ia_resultado"]:
        st.markdown(
            f"""
            <div class="section-card" style="padding:16px 20px;margin-top:12px;">
                <div style="color:#38bdf8;font-size:0.8rem;font-weight:700;margin-bottom:8px;">
                    🤖 DIAGNÓSTICO IA · {st.session_state['ia_inst']}
                </div>
                <div style="color:#e2e8f0;font-size:0.9rem;line-height:1.6;white-space:pre-wrap;">
                    {st.session_state['ia_resultado']}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown('<div class="grad-divider"></div>', unsafe_allow_html=True)

    # ── PDF Ejecutivo ─────────────────────────────────────────────────────────
    st.markdown("#### 📄 Reporte Ejecutivo PDF")
    st.caption(
        "Genera un reporte institucional con el Top 5 de colegios críticos "
        "y el diagnóstico IA listo para presentar ante Gobernación o Consejos de Gobierno."
    )

    ia_para_pdf = st.session_state.get("ia_resultado") or (
        "Análisis IA no generado. Para incluir el diagnóstico estratégico, "
        "selecciona una institución y presiona 'Generar Diagnóstico IA' antes de descargar el PDF."
    )

    col_pdf, _ = st.columns([1, 3])
    with col_pdf:
        if st.button("🖨️ Preparar PDF", key="btn_pdf_prep"):
            with st.spinner("Generando PDF ejecutivo..."):
                try:
                    df_top5 = df_ipe.head(5).reset_index(drop=True)
                    pdf_bytes = _generar_pdf(filtro_label, df_top5, ia_para_pdf)
                    st.session_state["pdf_bytes"] = pdf_bytes
                    st.success("✅ PDF generado. Haz clic en Descargar.")
                except Exception as e:
                    st.error(f"Error generando PDF: {e}")

    if st.session_state.get("pdf_bytes"):
        st.download_button(
            label="⬇️ Descargar Reporte Ejecutivo PDF",
            data=st.session_state["pdf_bytes"],
            file_name=f"Reporte_IPE_{filtro_label.replace(' ', '_')}.pdf",
            mime="application/pdf",
            key="btn_pdf_download",
        )

    st.markdown('<div class="grad-divider"></div>', unsafe_allow_html=True)

    # ── Análisis de sensibilidad de pesos ─────────────────────────────────────
    with st.expander("🔬 Análisis de Sensibilidad de Pesos — ¿Es robusto el IPE?"):
        st.markdown(
            """
            **¿Qué es esto?** Varía cada componente ±10% (manteniendo suma = 100%)
            y mide si el ranking de instituciones cambia. Si la correlación de Spearman
            es alta (r ≥ 0.95) en todos los escenarios → los pesos exactos no son críticos
            → la elección 40/30/30 es justificable como decisión de diseño razonable.
            """
        )
        try:
            df_sens = _sensibilidad_pesos(df_ipe)

            # ── Tabla de correlaciones ─────────────────────────────────────────
            st.markdown("##### 📋 Correlación de Spearman vs Ranking Base")

            def _color_r(val):
                if isinstance(val, float):
                    if val >= 0.95:
                        return "color:#34d399;font-weight:700"
                    if val >= 0.85:
                        return "color:#facc15;font-weight:600"
                    return "color:#f43f5e;font-weight:700"
                return ""

            styled_sens = df_sens.style.map(_color_r, subset=["r Spearman"])
            st.dataframe(styled_sens, use_container_width=True, hide_index=True)

            # ── Gráfico de barras de r Spearman ───────────────────────────────
            st.markdown("##### 📊 Estabilidad del Ranking por Escenario")
            fig_r = go.Figure()
            colors_r = [
                "#34d399" if r >= 0.95 else "#facc15" if r >= 0.85 else "#f43f5e"
                for r in df_sens["r Spearman"]
            ]
            fig_r.add_trace(
                go.Bar(
                    x=df_sens["Escenario"],
                    y=df_sens["r Spearman"],
                    marker_color=colors_r,
                    marker_line_width=0,
                    text=[f"{r:.4f}" for r in df_sens["r Spearman"]],
                    textposition="outside",
                    textfont=dict(color="#f8fafc", size=11),
                    hovertemplate="<b>%{x}</b><br>r Spearman: %{y:.4f}<extra></extra>",
                )
            )
            fig_r.add_hline(
                y=0.95,
                line_dash="dot",
                line_color="#34d399",
                annotation_text="Alta estabilidad (0.95)",
                annotation_font_color="#34d399",
            )
            fig_r.add_hline(
                y=0.85,
                line_dash="dot",
                line_color="#facc15",
                annotation_text="Estabilidad moderada (0.85)",
                annotation_font_color="#facc15",
            )
            fig_r.update_layout(
                **dark_layout(
                    title="",
                    yaxis=dict(range=[0.7, 1.01], title="r Spearman"),
                    xaxis=dict(title=""),
                )
            )
            st.plotly_chart(fig_r, use_container_width=True)

            # ── Tabla de ranking top-10 ────────────────────────────────────────
            st.markdown(
                "##### 🏆 Variación de Puesto — Top 10 Instituciones (Ranking Base)"
            )
            df_top = _ranking_top_n_por_escenario(df_ipe, n=min(10, len(df_ipe)))
            st.dataframe(df_top, use_container_width=True, hide_index=True)

            # ── Conclusión automática ──────────────────────────────────────────
            r_min = df_sens["r Spearman"].min()
            r_mean = df_sens["r Spearman"].mean()
            if r_min >= 0.95:
                msg = (
                    f"✅ **Alta robustez** — correlación mínima {r_min:.4f} (media {r_mean:.4f}). "
                    "El ranking de instituciones es estable ante variaciones ±10% en los pesos. "
                    "Los pesos 40/30/30 son una elección de diseño justificable."
                )
                st.success(msg)
            elif r_min >= 0.85:
                msg = (
                    f"🟡 **Robustez moderada** — correlación mínima {r_min:.4f} (media {r_mean:.4f}). "
                    "El ranking varía algo ante cambios de pesos. Se recomienda documentar "
                    "la justificación de la elección 40/30/30 con referencias bibliográficas."
                )
                st.warning(msg)
            else:
                msg = (
                    f"🔴 **Baja robustez** — correlación mínima {r_min:.4f}. "
                    "El ranking cambia significativamente con distintos pesos. "
                    "Se recomienda derivar pesos empíricamente (regresión OLS o AHP)."
                )
                st.error(msg)

        except Exception as ex:
            st.warning(
                f"No se pudo calcular sensibilidad: {ex}. Verifica que scipy esté instalado."
            )

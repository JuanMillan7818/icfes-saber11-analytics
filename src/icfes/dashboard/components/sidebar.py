import streamlit as st


@st.cache_data
def _load_filter_options(_svc):
    try:
        df_anos = _svc.query_df(
            "SELECT DISTINCT ano FROM {parquet} WHERE ano IS NOT NULL ORDER BY ano"
        )
        df_deptos = _svc.query_df(
            "SELECT DISTINCT cole_depto_ubicacion FROM {parquet} WHERE cole_depto_ubicacion IS NOT NULL ORDER BY cole_depto_ubicacion"
        )
        df_genero = _svc.query_df(
            "SELECT DISTINCT estu_genero FROM {parquet} WHERE estu_genero IS NOT NULL"
        )
        return (
            df_anos["ano"].dropna().tolist(),
            df_deptos["cole_depto_ubicacion"].dropna().tolist(),
            df_genero["estu_genero"].dropna().tolist(),
        )
    except Exception:
        return (
            [str(y) for y in range(2015, 2026)],
            [],
            [],
        )


def render_sidebar(svc) -> tuple:
    """Render sidebar filters. Returns (where_clause, sel_anos, sel_deptos, sel_genero, sel_naturaleza)."""
    anos_list, deptos_list, genero_list = _load_filter_options(svc)

    with st.sidebar:
        st.markdown("### ⚙️ Filtros Globales")
        st.markdown("<div class='grad-divider'></div>", unsafe_allow_html=True)
        sel_anos = st.multiselect("📅 Año", options=anos_list, default=[])
        sel_deptos = st.multiselect("📍 Departamento", options=deptos_list, default=[])
        sel_genero = st.multiselect(
            "👤 Género Estudiante", options=genero_list, default=[]
        )
        sel_naturaleza = st.selectbox(
            "🏫 Naturaleza Colegio", ["Todas", "OFICIAL", "NO OFICIAL"]
        )
        st.caption("Los filtros aplican a la sección **Análisis**.")

    filters = ["cole_cod_depto_ubicacion is not null and cole_depto_ubicacion != ''"]
    if sel_anos:
        filters.append(f"ano IN ({','.join([repr(a) for a in sel_anos])})")
    if sel_deptos:
        filters.append(
            f"cole_depto_ubicacion IN ({','.join([repr(d) for d in sel_deptos])})"
        )
    if sel_genero:
        filters.append(f"estu_genero IN ({','.join([repr(g) for g in sel_genero])})")
    if sel_naturaleza != "Todas":
        filters.append(f"cole_naturaleza = '{sel_naturaleza}'")

    where_clause = "WHERE " + " AND ".join(filters) if filters else ""

    return where_clause, sel_anos, sel_deptos, sel_genero, sel_naturaleza

from contextlib import asynccontextmanager
from fastapi import FastAPI
from icfes.core.query_service import QueryService, make_query_service

_svc: QueryService | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _svc
    _svc = make_query_service()
    yield
    _svc.close()


app = FastAPI(title="ICFES Analytics API", version="1.0.0", lifespan=lifespan)


@app.get("/puntajes/promedio-por-ano")
async def promedio_por_ano():
    df = _svc.query_df("""
        SELECT
            ano,
            AVG(CAST(punt_global AS DOUBLE))             AS promedio_global,
            AVG(CAST(punt_matematicas AS DOUBLE))        AS matematicas,
            AVG(CAST(punt_lectura_critica AS DOUBLE))    AS lectura_critica,
            AVG(CAST(punt_c_naturales AS DOUBLE))        AS c_naturales,
            AVG(CAST(punt_sociales_ciudadanas AS DOUBLE)) AS sociales,
            COUNT(*)                                     AS total_estudiantes
        FROM {parquet}
        GROUP BY ano
        ORDER BY ano
    """)
    return df.to_dict(orient="records")


@app.get("/puntajes/por-departamento")
async def puntajes_por_departamento(ano: str | None = None):
    filtro = f"WHERE ano = '{ano}'" if ano else ""
    df = _svc.query_df(f"""
        SELECT
            ano,
            cole_depto_ubicacion AS depto,
            AVG(CAST(punt_global AS DOUBLE)) AS promedio_global,
            COUNT(*) AS total_estudiantes
        FROM {{parquet}}
        {filtro}
        GROUP BY ano, cole_depto_ubicacion
        ORDER BY ano, promedio_global DESC
    """)
    return df.to_dict(orient="records")

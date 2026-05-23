"""
Script de entrenamiento del modelo predictivo para HU 3.
Genera models/simulador.pkl con un LinearRegression entrenado
sobre promedios anuales de variables socioeconómicas → punt_global.

Uso:
    uv run python scripts/train_simulador.py
"""
import pathlib
import pickle

import duckdb

from icfes import settings

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODEL_OUT = ROOT / "models" / "simulador.pkl"
MODEL_OUT.parent.mkdir(exist_ok=True)

parquet_glob = f"{settings.PARQUET_PATH}/*.parquet"

print(f"Leyendo datos desde: {parquet_glob}")
con = duckdb.connect()
con.execute("LOAD parquet")

df = con.execute(
    f"""
    SELECT
        ano,
        SUM(CASE WHEN fami_tieneinternet = 'Si' THEN 1.0 ELSE 0.0 END)
            * 100.0 / COUNT(*) AS pct_internet,
        SUM(CASE
            WHEN fami_educacionmadre IN ('Universitaria','Postgrado','Técnica o tecnológica profesional')
              OR fami_educacionpadre IN ('Universitaria','Postgrado','Técnica o tecnológica profesional')
            THEN 1.0 ELSE 0.0 END)
            * 100.0 / COUNT(*) AS pct_educacion_sup,
        AVG(TRY_CAST(REPLACE(fami_estratovivienda, 'Estrato ', '') AS INTEGER)) AS promedio_estrato,
        AVG(CAST(punt_global AS DOUBLE)) AS punt_global
    FROM read_parquet('{parquet_glob}')
    WHERE ano IS NOT NULL AND punt_global IS NOT NULL
    GROUP BY ano
    ORDER BY ano
    """
).df()

con.close()

print(f"Años disponibles: {df['ano'].tolist()}")
print(df[["pct_internet", "pct_educacion_sup", "promedio_estrato", "punt_global"]].to_string())

df_clean = df.dropna(
    subset=["pct_internet", "pct_educacion_sup", "promedio_estrato", "punt_global"]
)

if df_clean.empty:
    print("❌ Sin datos limpios para entrenar.")
    raise SystemExit(1)

from sklearn.linear_model import LinearRegression  # noqa: E402

X = df_clean[["pct_internet", "pct_educacion_sup", "promedio_estrato"]].values
y = df_clean["punt_global"].values

model = LinearRegression()
model.fit(X, y)

r2 = model.score(X, y)
print(f"\nR² del modelo: {r2:.4f}")
print("Coeficientes:")
for feat, coef in zip(["pct_internet", "pct_educacion_sup", "promedio_estrato"], model.coef_):
    print(f"  {feat}: {coef:.4f}")
print(f"  intercept: {model.intercept_:.4f}")

with open(MODEL_OUT, "wb") as f:
    pickle.dump(model, f)

print(f"\nModelo guardado en: {MODEL_OUT}")

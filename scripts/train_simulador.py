"""
Script de entrenamiento del modelo predictivo para HU 3.
Entrena 3 modelos: Ridge, RandomForestRegressor, GradientBoostingRegressor.
Guarda models/simulador_models.pkl con bundle comparativo.

Granularidad: colegio × municipio × año (miles de filas)

Uso:
    uv run python scripts/train_simulador.py
"""
import pathlib
import pickle

import duckdb
import numpy as np

from icfes import settings

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODEL_OUT = ROOT / "models" / "simulador_models.pkl"
MODEL_OUT.parent.mkdir(exist_ok=True)

parquet_glob = f"{settings.PARQUET_PATH}/*.parquet"

print(f"Leyendo datos desde: {parquet_glob}")
con = duckdb.connect()
con.execute("LOAD parquet")

df = con.execute(
    f"""
    SELECT
        cole_nombre_establecimiento AS colegio,
        cole_mcpio_ubicacion        AS municipio,
        ano,
        SUM(CASE WHEN fami_tieneinternet = 'Si' THEN 1.0 ELSE 0.0 END)
            * 100.0 / COUNT(*) AS pct_internet,
        SUM(CASE
            WHEN fami_educacionmadre IN (
                'Universitaria','Postgrado','Técnica o tecnológica profesional'
            ) OR fami_educacionpadre IN (
                'Universitaria','Postgrado','Técnica o tecnológica profesional'
            ) THEN 1.0 ELSE 0.0 END)
            * 100.0 / COUNT(*) AS pct_educacion_sup,
        AVG(TRY_CAST(REPLACE(fami_estratovivienda, 'Estrato ', '') AS INTEGER))
            AS promedio_estrato,
        AVG(CAST(punt_global AS DOUBLE)) AS punt_global,
        COUNT(*) AS n_est
    FROM read_parquet('{parquet_glob}')
    WHERE ano IS NOT NULL
      AND punt_global IS NOT NULL
      AND cole_nombre_establecimiento IS NOT NULL
      AND cole_nombre_establecimiento != ''
      AND cole_mcpio_ubicacion IS NOT NULL
      AND cole_mcpio_ubicacion != ''
    GROUP BY colegio, municipio, ano
    HAVING COUNT(*) >= 5
    ORDER BY municipio, colegio, ano
    """
).df()

con.close()

print(f"Filas colegio/municipio/año: {len(df)}")
print(f"Colegios únicos:             {df['colegio'].nunique()}")
print(f"Municipios únicos:           {df['municipio'].nunique()}")
print(f"Años disponibles:            {sorted(df['ano'].unique().tolist())}")

df_clean = df.dropna(
    subset=["pct_internet", "pct_educacion_sup", "promedio_estrato", "punt_global"]
)

if df_clean.empty:
    print("[ERROR] Sin datos limpios para entrenar.")
    raise SystemExit(1)

print(f"Filas limpias:               {len(df_clean)}")

from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor  # noqa: E402
from sklearn.linear_model import Ridge  # noqa: E402
from sklearn.metrics import mean_squared_error, mean_absolute_error  # noqa: E402
from sklearn.model_selection import cross_val_score  # noqa: E402
from sklearn.pipeline import Pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

FEATURES = ["pct_internet", "pct_educacion_sup", "promedio_estrato"]
X = df_clean[FEATURES].values
y = df_clean["punt_global"].values

print(f"\nRango punt_global (por colegio/año): {y.min():.1f} – {y.max():.1f}")

# ── Train / test split temporal ────────────────────────────────────────────────
anos    = df_clean["ano"].values
ano_max = int(anos.max())
test_mask = anos >= (ano_max - 1)
X_train, X_test = X[~test_mask], X[test_mask]
y_train, y_test = y[~test_mask], y[test_mask]

print(f"Train: {len(X_train)} filas | Test ({ano_max-1}–{ano_max}): {len(X_test)} filas\n")

# ── Definición de modelos ──────────────────────────────────────────────────────
MODELS_DEF = {
    "ridge": {
        "label": "Ridge Regression",
        "short": "Ridge (α=50)",
        "pipeline": Pipeline([
            ("scaler", StandardScaler()),
            ("model", Ridge(alpha=50.0)),
        ]),
        "color": "#38bdf8",
        "icon": "📐",
    },
    "rf": {
        "label": "Random Forest Regressor",
        "short": "Random Forest",
        "pipeline": Pipeline([
            ("scaler", StandardScaler()),
            ("model", RandomForestRegressor(
                n_estimators=200,
                max_depth=12,
                min_samples_leaf=5,
                random_state=42,
                n_jobs=-1,
            )),
        ]),
        "color": "#34d399",
        "icon": "🌳",
    },
    "gbr": {
        "label": "Gradient Boosting Regressor",
        "short": "Gradient Boosting",
        "pipeline": Pipeline([
            ("scaler", StandardScaler()),
            ("model", GradientBoostingRegressor(
                n_estimators=300,
                learning_rate=0.05,
                max_depth=4,
                subsample=0.8,
                random_state=42,
            )),
        ]),
        "color": "#f59e0b",
        "icon": "🚀",
    },
}

# ── Entrenamiento y métricas ───────────────────────────────────────────────────
results = {}
best_key = None
best_r2  = -np.inf

for key, cfg in MODELS_DEF.items():
    pipe = cfg["pipeline"]
    print(f"Entrenando {cfg['label']}...")
    pipe.fit(X_train, y_train)

    r2_train = float(pipe.score(X_train, y_train))
    r2_test  = float(pipe.score(X_test,  y_test))
    y_pred   = pipe.predict(X_test)
    mse      = float(mean_squared_error(y_test, y_pred))
    rmse     = float(np.sqrt(mse))
    mae      = float(mean_absolute_error(y_test, y_pred))
    cv_sc    = cross_val_score(pipe, X_train, y_train, cv=5, scoring="r2")
    r2_cv    = float(cv_sc.mean())
    r2_cv_sd = float(cv_sc.std())

    print(f"  R2 test={r2_test:.4f}  RMSE={rmse:.4f}  MAE={mae:.4f}  CV={r2_cv:.4f}+/-{r2_cv_sd:.4f}")

    results[key] = {
        "r2_train": round(r2_train, 6),
        "r2_test":  round(r2_test,  6),
        "r2_cv":    round(r2_cv,    6),
        "r2_cv_sd": round(r2_cv_sd, 6),
        "mse":      round(mse,  4),
        "rmse":     round(rmse, 4),
        "mae":      round(mae,  4),
    }

    if r2_test > best_r2:
        best_r2  = r2_test
        best_key = key

print(f"\n[MEJOR] Modelo: {MODELS_DEF[best_key]['label']} -> R2_test={best_r2:.4f}")

# ── Reentrenar con todos los datos ────────────────────────────────────────────
print("\nReentrenando con todos los datos para pkl final...")
trained_models = {}
for key, cfg in MODELS_DEF.items():
    pipe = cfg["pipeline"]
    pipe.fit(X, y)
    trained_models[key] = pipe
    print(f"  {cfg['label']} R²(full)={pipe.score(X, y):.4f}")

# ── Guardar bundle ─────────────────────────────────────────────────────────────
bundle = {
    # modelos entrenados en todos los datos
    "models": trained_models,
    # metadatos por modelo
    "models_meta": {
        key: {
            "label": cfg["label"],
            "short": cfg["short"],
            "color": cfg["color"],
            "icon":  cfg["icon"],
            **results[key],
        }
        for key, cfg in MODELS_DEF.items()
    },
    "best_model_key": best_key,
    # compatibilidad con simulador.py anterior (usa best model)
    "model":      trained_models[best_key],
    "algo":       MODELS_DEF[best_key]["label"],
    "features":   FEATURES,
    "granularity": "colegio/municipio/año",
    "r2":         results[best_key]["r2_test"],
    "r2_train":   results[best_key]["r2_train"],
    "r2_cv":      results[best_key]["r2_cv"],
    "mse":        results[best_key]["mse"],
    "rmse":       results[best_key]["rmse"],
    "n_train":    int(len(X_train)),
    "n_test":     int(len(X_test)),
    "n_total":    int(len(X)),
}

with open(MODEL_OUT, "wb") as f:
    pickle.dump(bundle, f)

# También guardar como simulador.pkl para backward-compat
compat_out = MODEL_OUT.parent / "simulador.pkl"
with open(compat_out, "wb") as f:
    pickle.dump(bundle, f)

print(f"\nBundle guardado en: {MODEL_OUT}")
print(f"Compat pkl:         {compat_out}")
print(f"\nResumen de metricas (test set):")
print(f"{'Modelo':<32} {'R2':>8} {'RMSE':>8} {'MAE':>8} {'CV R2':>10}")
print("-" * 68)
for key, cfg in MODELS_DEF.items():
    m = results[key]
    star = " [MEJOR]" if key == best_key else ""
    print(
        f"{cfg['label']:<32} {m['r2_test']:>8.4f} {m['rmse']:>8.4f} "
        f"{m['mae']:>8.4f} {m['r2_cv']:>8.4f}+/-{m['r2_cv_sd']:.4f}{star}"
    )

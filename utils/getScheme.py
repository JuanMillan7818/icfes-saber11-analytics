import os
import pandas as pd
from config.config import DATA_PATH_TEXT


def get_scheme():
    esquemas = {}

    for archivo in sorted(os.listdir(DATA_PATH_TEXT)):
        if archivo.endswith(".txt"):
            # Leer solo la primera fila (encabezados) para ahorrar memoria y tiempo
            df_min = pd.read_csv(
                os.path.join(DATA_PATH_TEXT, archivo),
                sep=";",
                nrows=0,
                encoding="utf-8",
            )
            esquemas[archivo] = list(df_min.columns)

    # Guardar esto en un Excel o JSON para analizarlo visualmente
    import json

    with open("./files/columnas_por_año.json", "w") as f:
        json.dump(esquemas, f, indent=4)

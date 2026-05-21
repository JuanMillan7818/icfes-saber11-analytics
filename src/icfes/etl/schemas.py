import os
import json
import pandas as pd
from icfes.etl.config import DATA_PATH_TEXT


def get_scheme() -> dict[str, list[str]]:
    esquemas: dict[str, list[str]] = {}

    for archivo in sorted(os.listdir(DATA_PATH_TEXT)):
        if archivo.endswith(".txt"):
            df_min = pd.read_csv(
                os.path.join(DATA_PATH_TEXT, archivo),
                sep=";",
                nrows=0,
                encoding="utf-8",
            )
            esquemas[archivo] = list(df_min.columns)

    with open("./files/columnas_por_año.json", "w") as f:
        json.dump(esquemas, f, indent=4)

    return esquemas

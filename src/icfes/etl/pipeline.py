import os
import re
import pyarrow as pa
import pyarrow.csv as pv
import pyarrow.parquet as pq
import pandas as pd
from icfes.etl.config import DATA_PATH_TEXT, PARQUET_PATH, MAP_ATTR_ICFES

MAP_DESEMP_A_PUNT = {
    "desemp_c_naturales": "punt_c_naturales",
    "desemp_lectura_critica": "punt_lectura_critica",
    "desemp_matematicas": "punt_matematicas",
    "desemp_sociales_ciudadanas": "punt_sociales_ciudadanas",
}

MAP_ETNIA = {"estu_tieneetnia": "estu_etnia"}


def calcular_desempeño(array_puntajes: pa.Array) -> pa.Array:
    s = pd.to_numeric(array_puntajes.to_pandas(), errors="coerce")
    categorias = pd.cut(s, bins=[-1, 35, 50, 70, 100], labels=["1", "2", "3", "4"])
    res = categorias.astype(object).where(categorias.notna(), None).values
    return pa.array(res, type=pa.string())


def crear_esquema_maestro(columnas: list[str]) -> pa.Schema:
    return pa.schema([pa.field(col, pa.string()) for col in columnas])


def normalizar_tabla(tabla_origen: pa.Table, esquema_objetivo: pa.Schema) -> pa.Table:
    num_filas = tabla_origen.num_rows
    columnas_finales = [
        tabla_origen.column(nombre) if nombre in tabla_origen.column_names
        else pa.nulls(num_filas, type=pa.string())
        for nombre in esquema_objetivo.names
    ]
    return pa.Table.from_arrays(columnas_finales, schema=esquema_objetivo)


def make_normalization() -> None:
    os.makedirs(PARQUET_PATH, exist_ok=True)

    if not os.path.exists(DATA_PATH_TEXT):
        print(f"❌ Error: La carpeta '{DATA_PATH_TEXT}' no existe.")
        return

    todas_las_columnas = set()
    for mapa in MAP_ATTR_ICFES.values():
        todas_las_columnas.update(mapa.keys())

    columnas_sin_control = todas_las_columnas - {"ano", "periodo"}
    columnas_objetivo_finales = sorted(list(columnas_sin_control)) + ["ano", "periodo"]
    esquema_maestro = crear_esquema_maestro(columnas_objetivo_finales)

    archivos = sorted(f for f in os.listdir(DATA_PATH_TEXT) if f.endswith(".txt"))

    if not archivos:
        print("⚠️ No se encontraron archivos .txt en la carpeta ./data")
        return

    print(f"🚀 Iniciando ETL dinámico para {len(archivos)} archivos...")

    for archivo in archivos:
        ruta_entrada = os.path.join(DATA_PATH_TEXT, archivo)
        llave_mapeo = archivo.replace(".txt", "")

        if llave_mapeo not in MAP_ATTR_ICFES:
            print(f"⚠️ Saltando {archivo}: llave '{llave_mapeo}' no está en MAP_ATTR_ICFES.")
            continue

        mapa_actual = MAP_ATTR_ICFES[llave_mapeo]
        nombre_salida = f"Saber11_{llave_mapeo}.parquet"
        ruta_salida = os.path.join(PARQUET_PATH, nombre_salida)

        print(f"⏳ Procesando: {archivo} ➔ {nombre_salida}")

        try:
            match = re.search(r"(\d{4})(\d)$", llave_mapeo)
            ano_str = match.group(1) if match else "Desconocido"
            periodo_str = match.group(2) if match else "Desconocido"

            tabla_raw = pv.read_csv(ruta_entrada, parse_options=pv.ParseOptions(delimiter=";"))

            arrays_extraidos: list[pa.Array] = []
            nombres_estandarizados: list[str] = []

            for col_final, col_original in mapa_actual.items():
                if col_final in ("ano", "periodo"):
                    continue

                if col_original in tabla_raw.column_names:
                    arrays_extraidos.append(tabla_raw.column(col_original))
                    nombres_estandarizados.append(col_final)
                elif col_final in MAP_DESEMP_A_PUNT:
                    punt_col_final = MAP_DESEMP_A_PUNT[col_final]
                    punt_col_original = mapa_actual.get(punt_col_final)
                    if punt_col_original and punt_col_original in tabla_raw.column_names:
                        print(f"   ✨ Calculando '{col_final}' desde '{punt_col_original}'...")
                        arrays_extraidos.append(calcular_desempeño(tabla_raw.column(punt_col_original)))
                        nombres_estandarizados.append(col_final)
                    else:
                        print(f"   ℹ️ '{col_final}' sin fuente. Será null.")
                elif col_final in MAP_ETNIA:
                    punt_col_final = MAP_ETNIA[col_final]
                    punt_col_original = mapa_actual.get(punt_col_final)
                    if punt_col_original and punt_col_original in tabla_raw.column_names:
                        raw = tabla_raw.column(punt_col_original)
                        has_etnia = raw or raw != "Ninguno"
                        arrays_extraidos.append(has_etnia)
                        nombres_estandarizados.append(col_final)
                    else:
                        print(f"   ℹ️ '{col_final}' sin fuente. Será null.")
                else:
                    print(f"   ℹ️ '{col_original}' no existe. Será null.")

            tabla_estandarizada = pa.Table.from_arrays(arrays_extraidos, names=nombres_estandarizados)

            num_filas = tabla_estandarizada.num_rows
            tabla_estandarizada = tabla_estandarizada.append_column(
                "ano", pa.array([ano_str] * num_filas, type=pa.string())
            )
            tabla_estandarizada = tabla_estandarizada.append_column(
                "periodo", pa.array([periodo_str] * num_filas, type=pa.string())
            )

            tabla_final = normalizar_tabla(tabla_estandarizada, esquema_maestro)
            pq.write_table(tabla_final, ruta_salida, compression="snappy")
            print(f"✅ Completado. Filas: {num_filas:,}\n")

        except Exception as e:
            print(f"❌ Error al procesar {archivo}: {e}\n")

    print(f"🏁 ETL finalizado. Parquet en ./{PARQUET_PATH}")

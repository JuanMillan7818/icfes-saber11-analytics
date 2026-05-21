import os
import pyarrow as pa
import pyarrow.csv as pv
import pyarrow.parquet as pq
import re
import pandas as pd
from config.config import DATA_PATH_TEXT, PARQUET_PATH, MAP_ATTR_ICFES

# Mapeo de columnas de desempeño a sus correspondientes columnas de puntaje
MAP_DESEMP_A_PUNT = {
    "desemp_c_naturales": "punt_c_naturales",
    "desemp_lectura_critica": "punt_lectura_critica",
    "desemp_matematicas": "punt_matematicas",
    "desemp_sociales_ciudadanas": "punt_sociales_ciudadanas",
}

MAP_ETNIA = {"estu_tieneetnia": "estu_etnia"}


def calcular_desempeño(array_puntajes):
    """
    Categoriza los puntajes en niveles de desempeño de 1 a 4.
    | Puntaje | Nivel |
    | ------- | ----- |
    | 0–35    | 1     |
    | 36–50   | 2     |
    | 51–70   | 3     |
    | 71–100  | 4     |
    """
    s = pd.to_numeric(array_puntajes.to_pandas(), errors="coerce")
    categorias = pd.cut(s, bins=[-1, 35, 50, 70, 100], labels=["1", "2", "3", "4"])
    res = categorias.astype(object).where(categorias.notna(), None).values
    return pa.array(res, type=pa.string())


# ==========================================
# FUNCIONES PRINCIPALES DEL ETL
# ==========================================


def crear_esquema_maestro(columnas):
    """Crea un esquema de PyArrow tratando todo como string para evitar conflictos."""
    campos = [pa.field(col, pa.string()) for col in columnas]
    return pa.schema(campos)


def normalizar_tabla(tabla_origen, esquema_objetivo):
    """
    Fuerza a la tabla a cumplir con el esquema final.
    Si una columna global no existió en este año, la inyecta llena de nulls.
    """
    columnas_finales = []
    num_filas = tabla_origen.num_rows

    for nombre_columna in esquema_objetivo.names:
        if nombre_columna in tabla_origen.column_names:
            columnas_finales.append(tabla_origen.column(nombre_columna))
        else:
            # Crea una columna de nulls nativa en C++ sin consumir RAM
            columnas_finales.append(pa.nulls(num_filas, type=pa.string()))

    return pa.Table.from_arrays(columnas_finales, schema=esquema_objetivo)


def make_normalization():
    os.makedirs(PARQUET_PATH, exist_ok=True)

    if not os.path.exists(DATA_PATH_TEXT):
        print(f"❌ Error: La carpeta '{DATA_PATH_TEXT}' no existe.")
        return

    # 1. DEDUCCIÓN DINÁMICA DEL ESQUEMA MAESTRO
    # Extraemos todas las llaves de todos los periodos para armar el universo de columnas
    todas_las_columnas = set()
    for mapa in MAP_ATTR_ICFES.values():
        todas_las_columnas.update(mapa.keys())

    # El esquema maestro final incluirá las columnas del mapa + nuestras variables de control
    # Removemos ano/periodo para evitar duplicaciones y las agregamos de forma limpia al final
    columnas_sin_control = todas_las_columnas - {"ano", "periodo"}
    columnas_objetivo_finales = sorted(list(columnas_sin_control)) + ["ano", "periodo"]
    esquema_maestro = crear_esquema_maestro(columnas_objetivo_finales)

    archivos = [f for f in os.listdir(DATA_PATH_TEXT) if f.endswith(".txt")]
    archivos.sort()

    if not archivos:
        print("⚠️ No se encontraron archivos .txt en la carpeta ./data")
        return

    print(f"🚀 Iniciando ETL dinámico para {len(archivos)} archivos...")
    print(f"📋 Esquema Maestro detectado: {sorted(list(todas_las_columnas))}\n")

    for archivo in archivos:
        ruta_entrada = os.path.join(DATA_PATH_TEXT, archivo)

        # 1. La llave del mapa es DIRECTAMENTE el nombre del archivo sin el .txt
        llave_mapeo = archivo.replace(".txt", "")  # Ej: "Examen_Saber_11_20151"

        # Verificación directa en el diccionario
        if llave_mapeo not in MAP_ATTR_ICFES:
            print(
                f"⚠️ Saltando {archivo}: La llave '{llave_mapeo}' no está en MAP_ATTR_ICFES."
            )
            continue

        mapa_actual = MAP_ATTR_ICFES[llave_mapeo]
        nombre_salida = f"Saber11_{llave_mapeo}.parquet"
        ruta_salida = os.path.join(PARQUET_PATH, nombre_salida)

        print(f"⏳ Procesando: {archivo} ➔ {nombre_salida}")

        try:
            # Extraer año y periodo usando regex al final de la cadena para las columnas de control
            # El símbolo $ asegura que busque los números justo al final del texto
            match = re.search(r"(\d{4})(\d)$", llave_mapeo)
            if match:
                ano_str = match.group(1)  # '2015'
                periodo_str = match.group(2)  # '1'
            else:
                ano_str = "Desconocido"
                periodo_str = "Desconocido"

            # [Aquí continúa exactamente el mismo proceso de lectura con PyArrow]
            opciones_parseo = pv.ParseOptions(delimiter=";")
            tabla_raw = pv.read_csv(ruta_entrada, parse_options=opciones_parseo)

            # Extracción y renombrado...
            arrays_extraidos = []
            nombres_estandarizados = []
            for col_final, col_original in mapa_actual.items():
                if col_final in ["ano", "periodo"]:
                    continue

                if col_original in tabla_raw.column_names:
                    arrays_extraidos.append(tabla_raw.column(col_original))
                    nombres_estandarizados.append(col_final)
                elif col_final in MAP_DESEMP_A_PUNT:
                    # Si no existe la columna de desempeño, pero tenemos su puntaje correspondiente,
                    # la calculamos dinámicamente.
                    punt_col_final = MAP_DESEMP_A_PUNT[col_final]
                    punt_col_original = mapa_actual.get(punt_col_final)
                    if (
                        punt_col_original
                        and punt_col_original in tabla_raw.column_names
                    ):
                        print(
                            f"   ✨ [{llave_mapeo}] '{col_original}' no existe. Calculando dinámicamente a partir de '{punt_col_original}'..."
                        )
                        raw_punt_array = tabla_raw.column(punt_col_original)
                        desemp_array = calcular_desempeño(raw_punt_array)
                        arrays_extraidos.append(desemp_array)
                        nombres_estandarizados.append(col_final)
                    else:
                        print(
                            f"   ℹ️ [{llave_mapeo}] '{col_original}' no existe y tampoco su puntaje '{punt_col_final}'. Se generará como null."
                        )
                elif col_final in MAP_ETNIA:
                    # Si no existe la columna de desempeño, pero tenemos su puntaje correspondiente,
                    # la calculamos dinámicamente.
                    punt_col_final = MAP_ETNIA[col_final]
                    punt_col_original = mapa_actual.get(punt_col_final)
                    if (
                        punt_col_original
                        and punt_col_original in tabla_raw.column_names
                    ):
                        print(
                            f"   ✨ [{llave_mapeo}] '{col_original}' no existe. Calculando dinámicamente a partir de '{punt_col_original}'..."
                        )
                        raw_punt_array = tabla_raw.column(punt_col_original)
                        has_etnia = raw_punt_array or raw_punt_array != "Ninguno"
                        arrays_extraidos.append(has_etnia)
                        nombres_estandarizados.append(col_final)
                    else:
                        print(
                            f"   ℹ️ [{llave_mapeo}] '{col_original}' no existe y tampoco su puntaje '{punt_col_final}'. Se generará como null."
                        )
                else:
                    print(
                        f"   ℹ️ [{llave_mapeo}] '{col_original}' no existe en el archivo. Se generará como null."
                    )

            tabla_estandarizada = pa.Table.from_arrays(
                arrays_extraidos, names=nombres_estandarizados
            )

            # Inyectar columnas de control
            num_filas = tabla_estandarizada.num_rows
            col_ano = pa.array([ano_str] * num_filas, type=pa.string())
            col_periodo = pa.array([periodo_str] * num_filas, type=pa.string())
            tabla_estandarizada = tabla_estandarizada.append_column("ano", col_ano)
            tabla_estandarizada = tabla_estandarizada.append_column(
                "periodo", col_periodo
            )

            # Ajustar al esquema maestro y guardar
            tabla_final = normalizar_tabla(tabla_estandarizada, esquema_maestro)
            pq.write_table(tabla_final, ruta_salida, compression="snappy")
            print(f"✅ ¡Completado! Filas: {num_filas:,}\n")

        except Exception as e:
            print(f"❌ Error al procesar {archivo}: {e}\n")

    print(
        "🏁 ¡ETL finalizado con éxito! Todos los archivos comparten exactamente la misma estructura en ./"
        + PARQUET_PATH
    )

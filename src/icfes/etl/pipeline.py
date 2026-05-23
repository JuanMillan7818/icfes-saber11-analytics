import os
import re
import unicodedata
import pyarrow as pa
import pyarrow.csv as pv
import pyarrow.parquet as pq
import pandas as pd

from icfes.etl.config import (
    DATA_PATH_TEXT,
    PARQUET_PATH,
    MAP_ATTR_ICFES,
    COLS_UBICACION_MCPIO,
    COLS_UBICACION_DEPTO,
    COL_AREA,
    DIVIPOLA_PATH,
    COL_COD_MCPIO,
    COL_COD_DEPTO,
)

MAP_DESEMP_A_PUNT = {
    "desemp_c_naturales": "punt_c_naturales",
    "desemp_lectura_critica": "punt_lectura_critica",
    "desemp_matematicas": "punt_matematicas",
    "desemp_sociales_ciudadanas": "punt_sociales_ciudadanas",
}

MAP_ETNIA = {"estu_tieneetnia": "estu_etnia"}


def _normalizar_area(valor: str) -> str:
    if not isinstance(valor, str):
        return valor
    u = valor.strip().upper()
    if u.startswith("URBAN"):
        return "URBANO"
    if u.startswith("RURAL"):
        return "RURAL"
    return u


# U+0303 = combining tilde; kept only after N/n to preserve Ñ
_COMBINING_TILDE = "̃"


# DEPRECADO PORQUE YA SE ASEGURA QUE ESTE SOBRE "utf-8" PARA EVITAR ERRORES
def _detectar_encoding(ruta: str) -> str:
    with open(ruta, "rb") as f:
        sample = f.read(32768)
    try:
        sample.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        try:
            sample.decode("cp1252")
            return "cp1252"
        except UnicodeDecodeError:
            return "latin-1"


def _fix_diacriticos_es(valor: str) -> str:
    """Normalize Spanish text for consistent grouping:
    - Fix UTF-8-as-cp1252 mojibake  (Ã­ → í, Ã± → ñ, etc.)
    - Fix Polish Ń → Spanish Ñ
    - Keep Ñ intact
    """
    if not isinstance(valor, str):
        return valor
    # Step 1: undo UTF-8-as-cp1252 mojibake (Ã = U+00C3 is the telltale sign)
    if "Ã" in valor:
        try:
            valor = valor.encode("cp1252").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    # Step 2: ensure precomposed; fix Polish Ń (U+0143) → Spanish Ñ (U+00D1)
    nfc = unicodedata.normalize("NFC", valor)
    fixed = nfc.replace("Ń", "Ñ").replace("ń", "ñ")
    # Step 3: NFD decompose → strip all combining marks except tilde on N (Ñ)
    nfd = unicodedata.normalize("NFD", fixed)
    chars = []
    for i, c in enumerate(nfd):
        if unicodedata.category(c) == "Mn":
            if c == _COMBINING_TILDE and i > 0 and nfd[i - 1].upper() == "N":
                chars.append(c)
        else:
            chars.append(c)
    return unicodedata.normalize("NFC", "".join(chars))


def calcular_desempeño(array_puntajes: pa.Array) -> pa.Array:
    s = pd.to_numeric(array_puntajes.to_pandas(), errors="coerce")
    categorias = pd.cut(s, bins=[-1, 35, 50, 70, 100], labels=["1", "2", "3", "4"])
    res = categorias.astype(object).where(categorias.notna(), None).values
    return pa.array(res, type=pa.string())


def crear_esquema_maestro(columnas: list[str]) -> pa.Schema:
    return pa.schema([pa.field(col, pa.string()) for col in columnas])


def normalizar_tabla(tabla_origen: pa.Table, esquema_objetivo: pa.Schema) -> pa.Table:
    num_filas = tabla_origen.num_rows
    columnas_finales = []
    for nombre in esquema_objetivo.names:
        if nombre in tabla_origen.column_names:
            col = tabla_origen.column(nombre)
            target = esquema_objetivo.field(nombre).type
            if col.type != target:
                col = col.cast(target)
            columnas_finales.append(col)
        else:
            columnas_finales.append(pa.nulls(num_filas, type=pa.string()))
    return pa.Table.from_arrays(columnas_finales, schema=esquema_objetivo)


def normalizar_ubicacion(dato: str) -> str:
    if not isinstance(dato, str):
        return dato

    normalizado = (
        _fix_diacriticos_es(unicodedata.normalize("NFKC", dato)).upper().strip()
    )

    return normalizado


def _cargar_divipola(ruta: str) -> tuple[dict[str, str], dict[str, str]]:
    df = pd.read_csv(ruta, dtype=str, encoding="utf-8", usecols=[0, 1, 2, 3])
    df.columns = ["cod_depto", "nom_depto", "cod_mcpio", "nom_mcpio"]
    df["nom_depto"] = df["nom_depto"].str.strip().str.upper()
    df["nom_mcpio"] = df["nom_mcpio"].str.strip().str.upper()
    deptos: dict[str, str] = dict(zip(df["cod_depto"], df["nom_depto"]))
    mcpios: dict[str, str] = dict(zip(df["cod_mcpio"], df["nom_mcpio"]))
    return deptos, mcpios


def _aplicar_divipola(
    tabla: pa.Table,
    tabla_raw: pa.Table,
    divipola_deptos: dict[str, str],
    divipola_mcpios: dict[str, str],
) -> pa.Table:
    if (
        COL_COD_MCPIO not in tabla_raw.column_names
        or COL_COD_DEPTO not in tabla_raw.column_names
    ):
        return tabla

    s_cod_mcpio = tabla_raw.column(COL_COD_MCPIO).to_pandas().astype(str).str.strip()
    s_cod_depto = tabla_raw.column(COL_COD_DEPTO).to_pandas().astype(str).str.strip()

    nom_mcpio = s_cod_mcpio.str.zfill(5).map(divipola_mcpios)
    nom_depto = s_cod_depto.str.zfill(2).map(divipola_deptos)

    col_names = tabla.column_names

    if COLS_UBICACION_MCPIO in col_names:
        existing = tabla.column(COLS_UBICACION_MCPIO).to_pandas()
        filled = nom_mcpio.where(nom_mcpio.notna(), existing)
        idx = col_names.index(COLS_UBICACION_MCPIO)

        tabla = tabla.set_column(
            idx,
            COLS_UBICACION_MCPIO,
            pa.array(filled.values, type=pa.string()),
        )

    if COLS_UBICACION_DEPTO in col_names:
        existing = tabla.column(COLS_UBICACION_DEPTO).to_pandas()
        filled = nom_depto.where(nom_depto.notna(), existing)
        idx = tabla.column_names.index(COLS_UBICACION_DEPTO)
        tabla = tabla.set_column(
            idx,
            COLS_UBICACION_DEPTO,
            pa.array(filled.values, type=pa.string()),
        )

    return tabla


def inferir_y_castear(tabla: pa.Table) -> pa.Table:
    arrays = []
    fields = []
    for col_name in tabla.column_names:
        try:
            s = tabla.column(col_name).to_pandas()
            s_str = s.str.strip()
            non_null = s.notna().sum()
            numeric = pd.to_numeric(s_str, errors="coerce")
            if non_null > 0 and numeric.notna().sum() / non_null >= 0.9:
                arr = pa.array(numeric.values, type=pa.float64())
                fields.append(pa.field(col_name, pa.float64()))
            else:
                s_nfkc = s_str.map(
                    lambda v: (
                        unicodedata.normalize("NFC", unicodedata.normalize("NFKC", v))
                        if isinstance(v, str)
                        else None
                    )
                )
                arr = pa.array(s_nfkc.values, type=pa.string())
                fields.append(pa.field(col_name, pa.string()))
        except Exception as e:
            print(f"Error al procesar la columna {col_name}: {e}")
            s_fallback = tabla.column(col_name).to_pandas()
            clean = s_fallback.where(s_fallback.notna(), other=None)
            arr = pa.array(clean.values, type=pa.string())
            fields.append(pa.field(col_name, pa.string()))

        arrays.append(arr)

    return pa.Table.from_arrays(arrays, schema=pa.schema(fields))


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

    divipola_deptos, divipola_mcpios = _cargar_divipola(DIVIPOLA_PATH)
    print(
        f"📍 DIVIPOLA cargado: {len(divipola_deptos)} dptos, {len(divipola_mcpios)} mpios"
    )

    print(f"🚀 Iniciando ETL dinámico para {len(archivos)} archivos...")

    for archivo in archivos:
        ruta_entrada = os.path.join(DATA_PATH_TEXT, archivo)
        llave_mapeo = archivo.replace(".txt", "")

        if llave_mapeo not in MAP_ATTR_ICFES:
            print(
                f"⚠️ Saltando {archivo}: llave '{llave_mapeo}' no está en MAP_ATTR_ICFES."
            )
            continue

        # print(f"llave_mapeo: {llave_mapeo}")
        # if llave_mapeo != "Examen_Saber_11_20252":
        # continue

        mapa_actual = MAP_ATTR_ICFES[llave_mapeo]
        nombre_salida = f"Saber11_{llave_mapeo}.parquet"
        ruta_salida = os.path.join(PARQUET_PATH, nombre_salida)

        print(f"⏳ Procesando: {archivo} ➔ {nombre_salida}")

        try:
            match = re.search(r"(\d{4})(\d)$", llave_mapeo)
            ano_str = match.group(1) if match else "Desconocido"
            periodo_str = match.group(2) if match else "Desconocido"

            encoding = "utf-8"

            tabla_raw = pv.read_csv(
                ruta_entrada,
                read_options=pv.ReadOptions(encoding=encoding),
                parse_options=pv.ParseOptions(delimiter=";"),
            )

            arrays_extraidos: list[pa.Array] = []
            nombres_estandarizados: list[str] = []

            for col_final, col_original in mapa_actual.items():
                if col_final in ("ano"):
                    continue

                if col_original in tabla_raw.column_names:
                    if col_final == COL_AREA:
                        s = tabla_raw.column(col_original).to_pandas()
                        arrays_extraidos.append(
                            pa.array(s.map(_normalizar_area).values, type=pa.string())
                        )
                        nombres_estandarizados.append(col_final)
                    elif col_final in (COLS_UBICACION_MCPIO, COLS_UBICACION_DEPTO):
                        s = tabla_raw.column(col_original).to_pandas()
                        arrays_extraidos.append(
                            pa.array(
                                s.map(normalizar_ubicacion).values, type=pa.string()
                            )
                        )
                        nombres_estandarizados.append(col_final)
                    else:
                        arrays_extraidos.append(tabla_raw.column(col_original))
                        nombres_estandarizados.append(col_final)
                elif col_final in MAP_DESEMP_A_PUNT:
                    punt_col_final = MAP_DESEMP_A_PUNT[col_final]
                    punt_col_original = mapa_actual.get(punt_col_final)
                    if (
                        punt_col_original
                        and punt_col_original in tabla_raw.column_names
                    ):
                        print(
                            f"   ✨ Calculando '{col_final}' desde '{punt_col_original}'..."
                        )
                        arrays_extraidos.append(
                            calcular_desempeño(tabla_raw.column(punt_col_original))
                        )
                        nombres_estandarizados.append(col_final)
                    else:
                        print(f"   ℹ️ '{col_final}' sin fuente. Será null.")
                elif col_final in MAP_ETNIA:
                    punt_col_final = MAP_ETNIA[col_final]
                    punt_col_original = mapa_actual.get(punt_col_final)
                    if (
                        punt_col_original
                        and punt_col_original in tabla_raw.column_names
                    ):
                        raw = tabla_raw.column(punt_col_original)
                        has_etnia = raw or raw != "Ninguno"
                        arrays_extraidos.append(has_etnia)
                        nombres_estandarizados.append(col_final)
                    else:
                        print(f"   ℹ️ '{col_final}' sin fuente. Será null.")
                else:
                    print(f"   ℹ️ '{col_original}' no existe. Será null.")

            tabla_estandarizada = pa.Table.from_arrays(
                arrays_extraidos, names=nombres_estandarizados
            )

            tabla_estandarizada = _aplicar_divipola(
                tabla_estandarizada, tabla_raw, divipola_deptos, divipola_mcpios
            )

            num_filas = tabla_estandarizada.num_rows
            tabla_estandarizada = tabla_estandarizada.append_column(
                "ano", pa.array([ano_str] * num_filas, type=pa.string())
            )

            tabla_final = normalizar_tabla(tabla_estandarizada, esquema_maestro)
            tabla_final = inferir_y_castear(tabla_final)

            pq.write_table(tabla_final, ruta_salida, compression="snappy")
            print(f"✅ Completado. Filas: {num_filas:,}\n")

        except Exception as e:
            print(f"❌ Error al procesar {archivo}: {e}\n")

    print(f"🏁 ETL finalizado. Parquet en ./{PARQUET_PATH}")

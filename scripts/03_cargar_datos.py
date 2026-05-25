"""
03_cargar_datos.py
==================
ETL: Carga los CSVs limpios en el Data Warehouse SQLite (modelo estrella).

Orden de carga:
  1. Dimensiones (dim_tiempo, dim_comercio, dim_ubicacion, dim_sucursal,
     dim_producto)
  2. Tabla de hechos (fact_precio)

El archivo productos.csv (~53 M filas) se procesa por chunks con operaciones
vectorizadas de pandas (sin iterrows) para maximizar rendimiento.

Modelo (5 dimensiones + 1 fact):
  - dim_tiempo:    fecha, anio, mes, dia
  - dim_comercio:  razon_social, bandera_nombre
  - dim_ubicacion: provincia_codigo (ISO), provincia_nombre (nombre legible), localidad
  - dim_sucursal:  nombre, direccion (calle+numero), tipo_sucursal
  - dim_producto:  ean, descripcion, marca, categoria_inferida
  - fact_precio:   precio_lista, precio_referencia, precio_promo, tiene_promo

Uso:
    python scripts/03_cargar_datos.py
"""

import sys
import time
import datetime
import sqlite3
import multiprocessing as mp
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

import pandas as pd
import numpy as np

# ==========================================================================
# CONFIGURACION
# ==========================================================================

# -- Rutas -----------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
DATOS_LIMPIOS_DIR = BASE_DIR / "data" / "processed"
DB_PATH = BASE_DIR / "data" / "dw_sepa_precios.db"

COMERCIOS_CSV = DATOS_LIMPIOS_DIR / "comercios.csv"
SUCURSALES_CSV = DATOS_LIMPIOS_DIR / "sucursales.csv"
PRODUCTOS_CSV = DATOS_LIMPIOS_DIR / "productos.csv"

# -- Parametros de procesamiento -------------------------------------------
CHUNK_SIZE = 750_000          # filas por chunk al leer productos.csv
BATCH_INSERT_SIZE = 100_000   # filas por executemany en fact_precio
NUM_WORKERS = max(1, mp.cpu_count() - 2)  # workers para transformacion paralela
COMMIT_EVERY_N_CHUNKS = 10   # commit cada N chunks (reduce overhead de I/O)
READ_AHEAD_CHUNKS = 4        # chunks a pre-leer en el hilo principal

# -- Rango de fechas para dim_tiempo --------------------------------------
FECHA_INICIO = datetime.date(2026, 3, 11)
FECHA_FIN = datetime.date(2026, 3, 17)

# ==========================================================================
# MAPEOS Y CONSTANTES
# ==========================================================================

# Mapeo de codigos ISO de provincias argentinas a nombres legibles (Decision D5)
PROVINCIAS_ISO = {
    "AR-A": "Salta", "AR-B": "Buenos Aires", "AR-C": "CABA",
    "AR-D": "San Luis", "AR-E": "Entre Ríos", "AR-F": "La Rioja",
    "AR-G": "Santiago del Estero", "AR-H": "Chaco", "AR-J": "San Juan",
    "AR-K": "Catamarca", "AR-L": "La Pampa", "AR-M": "Mendoza",
    "AR-N": "Misiones", "AR-P": "Formosa", "AR-Q": "Neuquén",
    "AR-R": "Río Negro", "AR-S": "Santa Fe", "AR-T": "Tucumán",
    "AR-U": "Chubut", "AR-V": "Tierra del Fuego", "AR-W": "Corrientes",
    "AR-X": "Córdoba", "AR-Y": "Jujuy", "AR-Z": "Santa Cruz",
}

# Reglas de inferencia de categoria a partir de la descripcion (Decision D2)
REGLAS_CATEGORIA = [
    (["LECHE", "YOGUR", "QUESO"], "Lacteos"),
    (["CERVEZA", "VINO", "WHISKY"], "Bebidas Alcoholicas"),
    (["FIDEOS", "ARROZ", "HARINA"], "Almacen"),
    (["AGUA", "GASEOSA", "JUGO"], "Bebidas"),
    (["JABON", "SHAMPOO", "DETERGENTE"], "Limpieza y Cuidado Personal"),
    (["ACEITE"], "Aceites"),
    (["PAN ", "GALLETITA", "GALLETA"], "Panaderia"),
    (["CARNE", "POLLO", "CERDO"], "Carnes"),
]


# ==========================================================================
# UTILIDADES
# ==========================================================================

def inferir_categoria(descripcion):
    """Infiere la categoria de un producto a partir de palabras clave en su
    descripcion. Devuelve 'Otros' si ninguna regla matchea."""
    desc_upper = str(descripcion).upper()
    for keywords, categoria in REGLAS_CATEGORIA:
        for kw in keywords:
            if kw in desc_upper:
                return categoria
    return "Otros"


def inferir_categoria_series(series):
    """Version vectorizada de inferir_categoria para una Series de pandas."""
    return series.apply(inferir_categoria)


def to_int_series(series):
    """Convierte una serie a int nativo de Python, NaN -> None.
    Necesario porque SQLite no acepta pd.NA (Int64 nullable)."""
    numeric = pd.to_numeric(series, errors="coerce")
    return [int(v) if pd.notna(v) else None for v in numeric]


def mapear_provincia(iso_code):
    """Convierte un codigo ISO de provincia (ej: AR-B) a nombre legible."""
    code = str(iso_code).strip()
    return PROVINCIAS_ISO.get(code, code)  # Si no matchea, devuelve el codigo original


def conectar_sqlite():
    """Abre y devuelve una conexion a SQLite optimizada para carga masiva."""
    print(f"Conectando a SQLite ({DB_PATH}) ...")
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = OFF")       # maximo rendimiento en carga
    conn.execute("PRAGMA cache_size = -512000")    # 512 MB de cache
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute("PRAGMA mmap_size = 1073741824")  # 1 GB mmap
    conn.execute("PRAGMA page_size = 8192")        # paginas mas grandes
    conn.execute("PRAGMA wal_autocheckpoint = 0")  # desactivar auto-checkpoint durante carga
    print("  Conexion establecida (modo carga masiva).")
    return conn


# ==========================================================================
# CARGA DE DIMENSIONES
# ==========================================================================

def cargar_dim_tiempo(cursor):
    """Genera e inserta las fechas del rango configurado.
    Columnas: fecha, anio, mes, dia."""
    print("\n--- dim_tiempo ---")

    sql = """
        INSERT OR IGNORE INTO dim_tiempo
            (fecha, anio, mes, dia)
        VALUES (?, ?, ?, ?)
    """

    fecha = FECHA_INICIO
    count = 0
    while fecha <= FECHA_FIN:
        anio = fecha.year
        mes = fecha.month
        dia = fecha.day

        cursor.execute(sql, (str(fecha), anio, mes, dia))
        count += 1
        fecha += datetime.timedelta(days=1)

    print(f"  Fechas insertadas: {count}")
    return count


def cargar_dim_comercio(cursor):
    """Carga dim_comercio desde comercios.csv.
    Columnas destino: razon_social, bandera_nombre.
    Se usan id_comercio + id_bandera internamente para deduplicar."""
    print("\n--- dim_comercio ---")

    df = pd.read_csv(COMERCIOS_CSV, dtype=str).fillna("")
    print(f"  Filas leidas: {len(df)}")

    # Deduplicar por combinacion id_comercio + id_bandera (clave natural)
    df = df.drop_duplicates(subset=["id_comercio", "id_bandera"])

    sql = """
        INSERT OR IGNORE INTO dim_comercio
            (razon_social, bandera_nombre)
        VALUES (?, ?)
    """

    rows = list(zip(
        df["comercio_razon_social"].str[:200],
        df["comercio_bandera_nombre"].str[:100],
    ))

    cursor.executemany(sql, rows)
    print(f"  Registros procesados: {len(rows)}")
    return len(rows)


def cargar_dim_ubicacion(cursor):
    """Carga dim_ubicacion con combinaciones unicas de provincia + localidad.
    Los codigos ISO de provincia se convierten a nombres legibles."""
    print("\n--- dim_ubicacion ---")

    cols = ["sucursales_provincia", "sucursales_localidad"]
    df = pd.read_csv(SUCURSALES_CSV, usecols=cols, dtype=str).fillna("")
    for c in cols:
        df[c] = df[c].str.strip()

    # Mapear ISO -> nombre legible
    df["provincia_nombre"] = df["sucursales_provincia"].apply(mapear_provincia)

    # Deduplicar por codigo + nombre + localidad
    df["provincia_codigo"] = df["sucursales_provincia"]
    combos = df[["provincia_codigo", "provincia_nombre", "sucursales_localidad"]].drop_duplicates()
    print(f"  Combinaciones unicas: {len(combos)}")

    sql = """
        INSERT OR IGNORE INTO dim_ubicacion
            (provincia_codigo, provincia_nombre, localidad)
        VALUES (?, ?, ?)
    """

    rows = list(zip(
        combos["provincia_codigo"].str[:10],
        combos["provincia_nombre"].str[:50],
        combos["sucursales_localidad"].str[:100],
    ))

    cursor.executemany(sql, rows)
    print(f"  Registros procesados: {len(rows)}")
    return len(rows)


def cargar_dim_sucursal(cursor):
    """Carga dim_sucursal desde sucursales.csv.
    Columnas destino: nombre, direccion (calle + numero), tipo_sucursal."""
    print("\n--- dim_sucursal ---")

    cols = [
        "id_comercio", "id_bandera", "id_sucursal",
        "sucursales_nombre", "sucursales_calle", "sucursales_numero",
        "sucursales_tipo",
    ]
    df = pd.read_csv(SUCURSALES_CSV, usecols=cols, dtype=str).fillna("")
    print(f"  Filas leidas: {len(df)}")

    # Concatenar calle + numero en una sola columna 'direccion'
    df["direccion"] = (df["sucursales_calle"].str.strip()
                       + " "
                       + df["sucursales_numero"].str.strip()).str.strip()

    # Normalizar tipo_sucursal
    df["tipo_sucursal"] = df["sucursales_tipo"].str.strip().str.title()

    sql = """
        INSERT OR IGNORE INTO dim_sucursal
            (nombre, direccion, tipo_sucursal)
        VALUES (?, ?, ?)
    """

    rows = list(zip(
        df["sucursales_nombre"].str[:100],
        df["direccion"].str[:200],
        df["tipo_sucursal"].str[:50],
    ))

    cursor.executemany(sql, rows)
    print(f"  Registros procesados: {len(rows)}")
    return len(rows)


def _extraer_productos_chunk(chunk_df):
    """Worker: extrae productos unicos de un chunk.
    Lee solo id_producto, descripcion y marca (las 3 columnas necesarias).
    Retorna un DataFrame deduplicado con categoria inferida."""
    chunk_df = chunk_df.fillna("")
    chunk_df["id_producto"] = chunk_df["id_producto"].str.strip()
    chunk_df["productos_descripcion"] = chunk_df["productos_descripcion"].str.strip().str[:200]
    chunk_df["productos_marca"] = chunk_df["productos_marca"].str.strip().str[:100]
    deduped = chunk_df.drop_duplicates(subset=["id_producto"])
    deduped = deduped[deduped["id_producto"] != ""]
    return deduped


def cargar_dim_producto(cursor):
    """Lee productos.csv por chunks EN PARALELO y carga dim_producto.
    Columnas destino: ean (= id_producto), descripcion, marca, categoria_inferida.

    NOTA: El campo 'productos_ean' del dataset es un flag booleano (0/1),
    NO el codigo EAN real. El verdadero identificador del producto es
    'id_producto' (ej: 7790250026136), que se almacena en dim_producto.ean.

    Optimizaciones:
      - Lee SOLO 3 columnas del CSV (en vez de las 18), reduciendo I/O ~85%
      - Usa multiprocessing para deduplicar chunks en paralelo
      - Merge final de resultados con pandas (vectorizado)"""
    print("\n" + "-" * 70)
    print(f"Cargando dim_producto desde productos.csv ({NUM_WORKERS} workers)...")

    # Leer SOLO las 3 columnas necesarias (reduce I/O de 10GB a ~1.5GB)
    usecols = ["id_producto", "productos_descripcion", "productos_marca"]

    chunk_num = 0
    partial_results = []

    with ProcessPoolExecutor(max_workers=NUM_WORKERS) as pool:
        futures = {}

        for chunk_df in pd.read_csv(
            PRODUCTOS_CSV, dtype=str, chunksize=CHUNK_SIZE, usecols=usecols,
        ):
            chunk_num += 1
            future = pool.submit(_extraer_productos_chunk, chunk_df)
            futures[future] = chunk_num

            # Limitar pendientes para no acumular demasiada memoria
            while len(futures) >= NUM_WORKERS * 2:
                done = next(as_completed(futures))
                cnum = futures.pop(done)
                partial_results.append(done.result())
                if cnum % 20 == 0:
                    print(f"    Chunk {cnum} procesado")

        # Recoger restantes
        for done_future in as_completed(futures):
            cnum = futures.pop(done_future)
            partial_results.append(done_future.result())

    print(f"  Total chunks: {chunk_num}")

    # Merge global: deduplicar todos los parciales en una sola pasada
    print("  Consolidando productos unicos...")
    df_all = pd.concat(partial_results, ignore_index=True)
    df_all = df_all.drop_duplicates(subset=["id_producto"], keep="first")

    # Inferir categorias (vectorizado con pandas)
    df_all["categoria_inferida"] = df_all["productos_descripcion"].apply(inferir_categoria)

    print(f"\n--- dim_producto ---")
    print(f"  Productos unicos: {len(df_all)}")

    sql = """
        INSERT OR IGNORE INTO dim_producto
            (ean, descripcion, marca, categoria_inferida)
        VALUES (?, ?, ?, ?)
    """
    batch = list(zip(
        df_all["id_producto"],
        df_all["productos_descripcion"],
        df_all["productos_marca"],
        df_all["categoria_inferida"],
    ))

    for i in range(0, len(batch), BATCH_INSERT_SIZE):
        cursor.executemany(sql, batch[i:i + BATCH_INSERT_SIZE])

    print("  dim_producto cargada.")
    return len(batch)


# ==========================================================================
# CONSTRUCCION DE LOOKUPS (como DataFrames para merge vectorizado)
# ==========================================================================

def construir_lookups_dimensiones(conn):
    """Carga todas las dimensiones desde SQLite como DataFrames para hacer
    merges vectorizados en vez de lookups fila por fila."""
    print("\n" + "=" * 70)
    print("CONSTRUCCION DE LOOKUPS")
    print("=" * 70)

    lookups = {}

    # dim_tiempo: {fecha_str -> sk_tiempo}
    df = pd.read_sql("SELECT sk_tiempo, fecha FROM dim_tiempo", conn)
    lookups["tiempo"] = dict(zip(df["fecha"], df["sk_tiempo"]))
    print(f"  dim_tiempo: {len(lookups['tiempo'])} entradas")

    # dim_comercio: necesitamos razon_social + bandera_nombre como clave de lookup
    lookups["comercio"] = pd.read_sql(
        "SELECT sk_comercio, razon_social, bandera_nombre FROM dim_comercio", conn
    )
    print(f"  dim_comercio: {len(lookups['comercio'])} entradas")

    # dim_sucursal: necesitamos nombre + direccion + tipo como clave de lookup
    lookups["sucursal"] = pd.read_sql(
        "SELECT sk_sucursal, nombre, direccion, tipo_sucursal FROM dim_sucursal", conn
    )
    print(f"  dim_sucursal: {len(lookups['sucursal'])} entradas")

    # dim_ubicacion
    lookups["ubicacion"] = pd.read_sql(
        "SELECT sk_ubicacion, provincia_codigo, provincia_nombre, localidad FROM dim_ubicacion", conn
    )
    print(f"  dim_ubicacion: {len(lookups['ubicacion'])} entradas")

    # dim_producto: lookup por ean
    lookups["producto"] = pd.read_sql(
        "SELECT sk_producto, ean FROM dim_producto", conn
    )
    print(f"  dim_producto: {len(lookups['producto'])} entradas")

    # Leer sucursales.csv completo para enriquecer los chunks de productos
    # con datos de ubicacion y tipo de sucursal durante el merge de la fact
    suc_cols = [
        "id_comercio", "id_bandera", "id_sucursal",
        "sucursales_nombre", "sucursales_calle", "sucursales_numero",
        "sucursales_tipo", "sucursales_provincia", "sucursales_localidad",
    ]
    df_suc = pd.read_csv(SUCURSALES_CSV, usecols=suc_cols, dtype=str).fillna("")
    for c in ["id_comercio", "id_bandera", "id_sucursal"]:
        df_suc[c] = pd.to_numeric(df_suc[c], errors="coerce")
    df_suc["sucursales_tipo"] = df_suc["sucursales_tipo"].str.strip().str.title()
    df_suc["sucursales_provincia"] = df_suc["sucursales_provincia"].str.strip()
    df_suc["sucursales_localidad"] = df_suc["sucursales_localidad"].str.strip()
    # Calcular campos derivados para merge
    df_suc["direccion_calc"] = (df_suc["sucursales_calle"].str.strip()
                                + " "
                                + df_suc["sucursales_numero"].str.strip()).str.strip()
    df_suc["provincia_nombre_calc"] = df_suc["sucursales_provincia"].apply(mapear_provincia)
    lookups["sucursales_csv"] = df_suc

    # Leer comercios.csv para mapear id_comercio + id_bandera -> razon_social + bandera
    com_cols = ["id_comercio", "id_bandera", "comercio_razon_social", "comercio_bandera_nombre"]
    df_com = pd.read_csv(COMERCIOS_CSV, usecols=com_cols, dtype=str).fillna("")
    for c in ["id_comercio", "id_bandera"]:
        df_com[c] = pd.to_numeric(df_com[c], errors="coerce")
    lookups["comercios_csv"] = df_com

    print("\n  Todos los lookups construidos.")
    return lookups


# ==========================================================================
# CARGA DE FACT_PRECIO (VECTORIZADA)
# ==========================================================================

def _preparar_lookups_para_workers(lookups):
    """Prepara los DataFrames de lookup y pre-merges necesarios para
    transformar chunks. Retorna un dict serializable para workers."""

    lk_comercio_dim = lookups["comercio"]
    lk_sucursal_dim = lookups["sucursal"]
    lk_ubicacion = lookups["ubicacion"]
    lk_producto = lookups["producto"]
    df_suc_csv = lookups["sucursales_csv"]
    df_com_csv = lookups["comercios_csv"]

    # Pre-merge: sucursal CSV -> sk_sucursal + sk_ubicacion
    suc_enrich = df_suc_csv.merge(
        lk_sucursal_dim,
        left_on=["sucursales_nombre", "direccion_calc", "sucursales_tipo"],
        right_on=["nombre", "direccion", "tipo_sucursal"],
        how="left",
    ).merge(
        lk_ubicacion,
        left_on=["provincia_nombre_calc", "sucursales_localidad"],
        right_on=["provincia_nombre", "localidad"],
        how="left",
    )[["id_comercio", "id_bandera", "id_sucursal", "sk_sucursal", "sk_ubicacion"]]

    # Pre-merge: comercio CSV -> sk_comercio
    com_enrich = df_com_csv.merge(
        lk_comercio_dim,
        left_on=["comercio_razon_social", "comercio_bandera_nombre"],
        right_on=["razon_social", "bandera_nombre"],
        how="left",
    )[["id_comercio", "id_bandera", "sk_comercio"]]

    return {
        "suc_enrich": suc_enrich,
        "com_enrich": com_enrich,
        "lk_producto": lk_producto,
        "lk_tiempo": lookups["tiempo"],
    }


def _transformar_chunk(chunk_df, lk_tiempo, com_enrich, suc_enrich, lk_producto):
    """Transforma un chunk de productos.csv en filas listas para insertar
    en fact_precio. Esta funcion se ejecuta en un worker process separado
    para aprovechar multiples cores (bypasea el GIL).

    Retorna (rows_as_numpy_array, n_original, n_skipped)."""

    n_orig = len(chunk_df)

    # --- Preparar columnas numericas ---
    for c in ["id_comercio", "id_bandera", "id_sucursal"]:
        chunk_df[c] = pd.to_numeric(chunk_df[c], errors="coerce")

    chunk_df["id_producto"] = chunk_df["id_producto"].fillna("").astype(str).str.strip()

    # --- SK tiempo (map directo) ---
    chunk_df["sk_tiempo"] = chunk_df["fecha_relevamiento"].map(lk_tiempo)

    # --- SK comercio ---
    chunk_df = chunk_df.merge(com_enrich, on=["id_comercio", "id_bandera"], how="left")

    # --- SK sucursal + SK ubicacion ---
    chunk_df = chunk_df.merge(suc_enrich, on=["id_comercio", "id_bandera", "id_sucursal"], how="left")

    # --- SK producto ---
    chunk_df = chunk_df.merge(lk_producto, left_on="id_producto", right_on="ean", how="left")

    # --- Filtrar filas con FK resueltas ---
    fk_cols = ["sk_tiempo", "sk_comercio", "sk_sucursal", "sk_ubicacion", "sk_producto"]
    mask_valid = chunk_df[fk_cols].notna().all(axis=1)
    valid = chunk_df.loc[mask_valid]
    skipped = n_orig - len(valid)

    if valid.empty:
        return [], n_orig, skipped

    # --- Construir array de resultados enteramente con numpy/pandas ---
    # (evita list comprehension en Python puro para ~500k filas)
    sk_prod = valid["sk_producto"].values.astype(np.int64)
    sk_com = valid["sk_comercio"].values.astype(np.int64)
    sk_suc = valid["sk_sucursal"].values.astype(np.int64)
    sk_ubi = valid["sk_ubicacion"].values.astype(np.int64)
    sk_tie = valid["sk_tiempo"].values.astype(np.int64)

    precio_lista = pd.to_numeric(valid["productos_precio_lista"], errors="coerce").values
    precio_ref = pd.to_numeric(valid["productos_precio_referencia"], errors="coerce").values
    precio_promo = pd.to_numeric(valid["productos_precio_unitario_promo1"], errors="coerce").values
    tiene_promo = np.where(np.isfinite(precio_promo), 1, 0)

    # Reemplazar NaN -> None directamente con numpy (mucho mas rapido que
    # la list comprehension anterior que iteraba fila por fila en Python)
    def _nan_to_none(arr):
        """Convierte un array float de numpy a lista con None en vez de NaN."""
        mask = np.isfinite(arr)
        out = arr.tolist()
        for i in np.flatnonzero(~mask):
            out[i] = None
        return out

    pl = _nan_to_none(precio_lista)
    pr = _nan_to_none(precio_ref)
    pp = _nan_to_none(precio_promo)

    rows = list(zip(
        sk_prod.tolist(), sk_com.tolist(), sk_suc.tolist(),
        sk_ubi.tolist(), sk_tie.tolist(),
        pl, pr, pp, tiene_promo.tolist(),
    ))

    return rows, n_orig, skipped


def cargar_fact_precio(conn, cursor, lookups):
    """Carga fact_precio usando transformacion paralela (multiprocessing)
    e insercion secuencial en SQLite.

    Arquitectura:
      - N workers (procesos) transforman chunks en paralelo (merges, tipos, NaN)
      - 1 hilo principal inserta los resultados en SQLite (single-writer)

    Esto aprovecha todos los cores de la CPU en vez de usar solo 1."""
    print("\n" + "=" * 70)
    print(f"CARGA DE FACT_PRECIO (paralela, {NUM_WORKERS} workers)")
    print("=" * 70)

    # Vaciar fact_precio para idempotencia (FKs ya desactivadas en main)
    print("  Vaciando fact_precio ...")
    cursor.execute("DELETE FROM fact_precio")
    conn.commit()

    # --- Preparar datos de lookup compartidos ---
    prep = _preparar_lookups_para_workers(lookups)
    suc_enrich = prep["suc_enrich"]
    com_enrich = prep["com_enrich"]
    lk_producto = prep["lk_producto"]
    lk_tiempo = prep["lk_tiempo"]

    sql = """
        INSERT INTO fact_precio
            (sk_producto, sk_comercio, sk_sucursal, sk_ubicacion, sk_tiempo,
             precio_lista, precio_referencia, precio_promo, tiene_promo)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    total_inserted = 0
    total_skipped = 0
    chunk_num = 0
    chunks_since_commit = 0
    t_start = time.time()

    # --- Leer chunks y procesarlos en paralelo ---
    # Usamos ProcessPoolExecutor para bypass del GIL.
    # Patron productor-consumidor: encolamos hasta NUM_WORKERS*2 futures,
    # y cada vez que uno termina lo insertamos en SQLite y encolamos otro.

    def _insertar_future(done_future, cnum):
        """Recoge el resultado de un future y lo inserta en SQLite."""
        nonlocal total_inserted, total_skipped, chunks_since_commit
        rows, n_orig, skipped = done_future.result()
        n_rows = len(rows)

        for i in range(0, n_rows, BATCH_INSERT_SIZE):
            cursor.executemany(sql, rows[i:i + BATCH_INSERT_SIZE])

        total_inserted += n_rows
        total_skipped += skipped
        chunks_since_commit += 1

        if chunks_since_commit >= COMMIT_EVERY_N_CHUNKS:
            conn.commit()
            chunks_since_commit = 0

        elapsed = time.time() - t_start
        print(
            f"  Chunk {cnum}: {n_orig:,} leidas, "
            f"skipped={skipped:,}, "
            f"insertadas acum={total_inserted:,}, "
            f"total={elapsed:.1f}s"
        )

    max_pending = NUM_WORKERS * 2

    with ProcessPoolExecutor(max_workers=NUM_WORKERS) as pool:
        futures = {}

        for chunk_df in pd.read_csv(PRODUCTOS_CSV, dtype=str, chunksize=CHUNK_SIZE):
            chunk_num += 1
            future = pool.submit(
                _transformar_chunk,
                chunk_df, lk_tiempo, com_enrich, suc_enrich, lk_producto,
            )
            futures[future] = chunk_num

            # Si alcanzamos el limite de pendientes, esperar a que termine uno
            while len(futures) >= max_pending:
                # Esperar al primero que termine
                done = next(as_completed(futures))
                cnum = futures.pop(done)
                _insertar_future(done, cnum)

        # Recoger todos los futures restantes
        for done_future in as_completed(futures):
            cnum = futures.pop(done_future)
            _insertar_future(done_future, cnum)

    # Commit final
    conn.commit()

    print(f"\n  === RESUMEN fact_precio ===")
    print(f"  Total insertadas: {total_inserted:,}")
    print(f"  Total omitidas (FK no resuelta): {total_skipped:,}")
    print(f"  Tiempo total: {time.time() - t_start:.1f}s")

    return total_inserted


# ==========================================================================
# MAIN
# ==========================================================================

def main():
    print("=" * 70)
    print("  ETL: Carga de datos limpios -> DW SQLite (modelo estrella)")
    print(f"  Base de datos: {DB_PATH}")
    print(f"  Fecha inicio: {FECHA_INICIO}  |  Fecha fin: {FECHA_FIN}")
    print("=" * 70)

    # Verificar archivos de entrada
    for csv_path in [COMERCIOS_CSV, SUCURSALES_CSV, PRODUCTOS_CSV]:
        if not csv_path.exists():
            print(f"[ERROR] Archivo no encontrado: {csv_path}")
            sys.exit(1)
        size_mb = csv_path.stat().st_size / (1024 * 1024)
        print(f"  [OK] {csv_path.name} ({size_mb:.1f} MB)")

    # Asegurar que el directorio data/ existe
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = None
    try:
        conn = conectar_sqlite()
        cursor = conn.cursor()

        # Desactivar FK checks durante la carga (mejora rendimiento)
        cursor.execute("PRAGMA foreign_keys = OFF")

        # ==================================================================
        # PASO 1: Cargar dimensiones
        # ==================================================================
        print("\n" + "=" * 70)
        print("PASO 1: CARGA DE DIMENSIONES")
        print("=" * 70)

        cargar_dim_tiempo(cursor)
        conn.commit()

        cargar_dim_comercio(cursor)
        conn.commit()

        cargar_dim_ubicacion(cursor)
        conn.commit()

        cargar_dim_sucursal(cursor)
        conn.commit()

        # dim_producto en pasada por chunks (productos.csv es muy grande)
        cargar_dim_producto(cursor)
        conn.commit()

        print("\n  Todas las dimensiones cargadas.")

        # ==================================================================
        # PASO 2: Construir lookups
        # ==================================================================
        lookups = construir_lookups_dimensiones(conn)

        # ==================================================================
        # PASO 3: Desactivar indices de fact_precio para carga rapida
        # ==================================================================
        print("\n  Eliminando indices de fact_precio para carga rapida...")
        idx_rows = cursor.execute(
            "SELECT name, sql FROM sqlite_master "
            "WHERE type='index' AND tbl_name='fact_precio' AND sql IS NOT NULL"
        ).fetchall()
        idx_ddls = [(name, sql) for name, sql in idx_rows]
        for name, _ in idx_ddls:
            cursor.execute(f"DROP INDEX IF EXISTS {name}")
        conn.commit()
        print(f"  {len(idx_ddls)} indices eliminados temporalmente.")

        # ==================================================================
        # PASO 4: Cargar fact_precio (paralelo)
        # ==================================================================
        cargar_fact_precio(conn, cursor, lookups)

        # ==================================================================
        # PASO 5: Recrear indices
        # ==================================================================
        print("\n  Recreando indices de fact_precio...")
        t_idx = time.time()
        for name, sql in idx_ddls:
            print(f"    Creando {name}...")
            cursor.execute(sql)
        conn.commit()
        print(f"  {len(idx_ddls)} indices recreados en {time.time() - t_idx:.1f}s")

        # Reactivar FK y ejecutar checkpoint WAL
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.commit()

        # ==================================================================
        # FIN
        # ==================================================================
        print("\n" + "=" * 70)
        print("  ETL COMPLETADO EXITOSAMENTE")
        print("=" * 70)

    except sqlite3.Error as e:
        print(f"\n[ERROR SQLite] {e}")
        if conn:
            conn.rollback()
            print("  Rollback realizado.")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] {e}")
        if conn:
            conn.rollback()
            print("  Rollback realizado.")
        raise
    finally:
        if conn:
            conn.close()
            print("  Conexion SQLite cerrada.")


if __name__ == "__main__":
    main()

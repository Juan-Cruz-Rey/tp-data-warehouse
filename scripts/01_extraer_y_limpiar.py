"""
01_extraer_y_limpiar.py
=======================
Extrae, limpia y consolida los datos del dataset SEPA Precios.

Lee los ZIPs principales (uno por dia), descomprime los sub-zips internos,
parsea los CSVs (comercio, sucursales, productos), limpia filas de metadata
y null bytes, deduplica por version sepa_1/sepa_2, y genera archivos
consolidados en datos_limpios/.

Uso:
    python scripts/01_extraer_y_limpiar.py
"""

import gc
import io
import os
import re
import sys
import time
import zipfile
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
DATOS_DIR = BASE_DIR / "data" / "raw"
DATOS_LIMPIOS_DIR = BASE_DIR / "data" / "processed"

# ZIPs principales: se descubren automaticamente en data/raw/
# (ya no se hardcodean nombres)

# Columnas de precio que deben convertirse a float
COLUMNAS_PRECIO = [
    "productos_precio_lista",
    "productos_precio_referencia",
    "productos_cantidad_referencia",
    "productos_cantidad_presentacion",
    "productos_precio_unitario_promo1",
    "productos_precio_unitario_promo2",
]

# Regex para detectar filas de metadata al final de los CSVs
RE_METADATA = re.compile(r"^\s*(Ultima|Última)\s+actualizaci", re.IGNORECASE)

# Regex para extraer version sepa y comercio-id del nombre del sub-zip
RE_SUBZIP = re.compile(r"sepa_(\d+)_comercio-sepa-(\d+)")


# ---------------------------------------------------------------------------
# Funciones auxiliares
# ---------------------------------------------------------------------------

def leer_csv_desde_bytes(raw_bytes: bytes, nombre_csv: str) -> pd.DataFrame:
    """Lee un CSV pipe-separated desde bytes crudos, limpiando BOM, null
    bytes y filas de metadata."""

    # Decodificar con utf-8-sig para quitar BOM si existe
    texto = raw_bytes.decode("utf-8-sig", errors="replace")

    # Eliminar null bytes (aparecen como lineas sueltas con \x00)
    texto = texto.replace("\x00", "")

    # Separar en lineas y filtrar metadata + vacias
    lineas = texto.split("\n")
    lineas_limpias = []
    for linea in lineas:
        stripped = linea.strip()
        if not stripped:
            continue
        if RE_METADATA.match(stripped):
            continue
        lineas_limpias.append(linea)

    if len(lineas_limpias) <= 1:
        # Solo header o vacio
        return pd.DataFrame()

    texto_limpio = "\n".join(lineas_limpias)

    try:
        df = pd.read_csv(
            io.StringIO(texto_limpio),
            sep="|",
            dtype=str,  # todo como string primero, convertimos despues
            skipinitialspace=True,
        )
    except Exception as e:
        print(f"    [WARN] Error parseando {nombre_csv}: {e}")
        return pd.DataFrame()

    # Strip de espacios en todas las columnas string
    df.columns = [c.strip() for c in df.columns]
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].str.strip()

    return df


def convertir_precios(df: pd.DataFrame) -> pd.DataFrame:
    """Convierte las columnas de precio a float, dejando NaN donde esten
    vacias."""
    for col in COLUMNAS_PRECIO:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def procesar_subzip(
    main_zip: zipfile.ZipFile,
    subzip_name: str,
    fecha_relevamiento: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Abre un sub-zip dentro del ZIP principal y retorna los 3 DataFrames
    (comercio, sucursales, productos)."""

    sub_bytes = main_zip.read(subzip_name)
    sub_zip = zipfile.ZipFile(io.BytesIO(sub_bytes))

    dfs = {}
    for csv_name in ["comercio.csv", "sucursales.csv", "productos.csv"]:
        if csv_name in sub_zip.namelist():
            raw = sub_zip.read(csv_name)
            df = leer_csv_desde_bytes(raw, f"{subzip_name}/{csv_name}")
            if not df.empty:
                df["fecha_relevamiento"] = fecha_relevamiento
            dfs[csv_name] = df
        else:
            print(f"    [WARN] {csv_name} no encontrado en {subzip_name}")
            dfs[csv_name] = pd.DataFrame()

    sub_zip.close()

    return dfs["comercio.csv"], dfs["sucursales.csv"], dfs["productos.csv"]


def extraer_info_subzip(nombre: str) -> tuple[int, int] | None:
    """Del nombre del sub-zip extrae (version_sepa, id_comercio).
    Retorna None si no matchea el patron."""
    m = RE_SUBZIP.search(nombre)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


def deduplicar_subzips(subzip_names: list[str]) -> list[str]:
    """Dado una lista de nombres de sub-zips, si un mismo comercio aparece
    en sepa_1 y sepa_2, se queda solo con sepa_2 (version mas reciente).
    Si aparece solo en una version, se conserva."""
    # Agrupar por comercio_id
    por_comercio: dict[int, dict[int, str]] = {}
    for name in subzip_names:
        info = extraer_info_subzip(name)
        if info is None:
            continue
        version, comercio_id = info
        if comercio_id not in por_comercio:
            por_comercio[comercio_id] = {}
        por_comercio[comercio_id][version] = name

    resultado = []
    for comercio_id, versiones in por_comercio.items():
        if 2 in versiones:
            # Preferir sepa_2
            resultado.append(versiones[2])
        elif 1 in versiones:
            resultado.append(versiones[1])
        else:
            # Version desconocida, tomar cualquiera
            resultado.append(list(versiones.values())[0])

    return resultado


def guardar_csv_seguro(df: pd.DataFrame, ruta: Path, descripcion: str) -> None:
    """Guarda un DataFrame a CSV con reintentos para manejar bloqueos de
    OneDrive u otros procesos."""
    max_intentos = 3
    for intento in range(1, max_intentos + 1):
        try:
            # Escribir a archivo temporal en el mismo directorio, luego renombrar
            ruta_tmp = ruta.with_suffix(".csv.tmp")
            df.to_csv(ruta_tmp, index=False, encoding="utf-8")
            # Si el archivo destino existe, intentar borrarlo primero
            if ruta.exists():
                os.remove(ruta)
            os.rename(ruta_tmp, ruta)
            tamano_mb = ruta.stat().st_size / 1024 / 1024
            print(f"  {ruta.name}: {len(df)} filas ({tamano_mb:.1f} MB)")
            return
        except PermissionError:
            if intento < max_intentos:
                print(f"  [RETRY] Permiso denegado escribiendo {descripcion}, "
                      f"reintentando en 5s ({intento}/{max_intentos})...")
                time.sleep(5)
            else:
                print(f"  [ERROR] No se pudo escribir {descripcion} "
                      f"despues de {max_intentos} intentos.")
                # Intentar guardar con nombre alternativo
                ruta_alt = ruta.with_name(ruta.stem + "_alt.csv")
                try:
                    df.to_csv(ruta_alt, index=False, encoding="utf-8")
                    print(f"  [OK] Guardado como alternativa: {ruta_alt.name}")
                except Exception as e2:
                    print(f"  [ERROR] Tampoco se pudo guardar alternativa: {e2}")
                raise


def procesar_zip_principal(zip_path: Path) -> tuple[
    list[pd.DataFrame], list[pd.DataFrame], list[pd.DataFrame]
]:
    """Procesa un ZIP principal (un dia completo).
    Retorna listas de DataFrames de comercio, sucursales y productos."""

    print(f"\nProcesando: {zip_path.name}")

    main_zip = zipfile.ZipFile(zip_path)
    all_names = main_zip.namelist()

    # Descubrir la fecha del directorio raiz (e.g. "2026-03-09/")
    dirs = [n for n in all_names if n.endswith("/") and n.count("/") == 1]
    if not dirs:
        print(f"  [ERROR] No se encontro directorio de fecha en {zip_path.name}")
        main_zip.close()
        return [], [], []

    fecha_relevamiento = dirs[0].rstrip("/")
    print(f"  Fecha de relevamiento: {fecha_relevamiento}")

    # Listar sub-zips
    subzip_names = [n for n in all_names if n.endswith(".zip")]
    print(f"  Sub-zips encontrados: {len(subzip_names)}")

    # Deduplicar por version sepa
    subzip_names = deduplicar_subzips(subzip_names)
    print(f"  Sub-zips despues de deduplicar versiones: {len(subzip_names)}")

    comercios_list = []
    sucursales_list = []
    productos_list = []

    for i, subzip_name in enumerate(subzip_names, 1):
        info = extraer_info_subzip(subzip_name)
        id_str = f"comercio-{info[1]}" if info else subzip_name
        print(f"  [{i}/{len(subzip_names)}] {id_str}...", end=" ")

        try:
            df_com, df_suc, df_prod = procesar_subzip(
                main_zip, subzip_name, fecha_relevamiento
            )
            n_com = len(df_com)
            n_suc = len(df_suc)
            n_prod = len(df_prod)
            print(f"comercio={n_com}, sucursales={n_suc}, productos={n_prod}")

            if not df_com.empty:
                comercios_list.append(df_com)
            if not df_suc.empty:
                sucursales_list.append(df_suc)
            if not df_prod.empty:
                productos_list.append(df_prod)

        except Exception as e:
            print(f"[ERROR] {e}")

    main_zip.close()
    return comercios_list, sucursales_list, productos_list


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 70)
    print("SEPA Precios - Extraccion y Limpieza de Datos")
    print("=" * 70)

    # Descubrir ZIPs automaticamente en data/raw/
    if not DATOS_DIR.exists():
        print(f"\n[ERROR] Directorio no encontrado: {DATOS_DIR}")
        print("  Ejecuta primero: python scripts/00_descargar_datos.py")
        sys.exit(1)

    zips_existentes = sorted(DATOS_DIR.glob("*.zip"))
    for ruta in zips_existentes:
        print(f"  [OK] {ruta.name} ({ruta.stat().st_size / 1024 / 1024:.1f} MB)")

    if not zips_existentes:
        print("\n[ERROR] No se encontraron archivos ZIP. Abortando.")
        sys.exit(1)

    # Crear directorio de salida
    DATOS_LIMPIOS_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Procesar dia por dia, guardando productos incrementalmente
    # para no acumular ~53M filas en memoria
    # ------------------------------------------------------------------
    all_comercios: list[pd.DataFrame] = []
    all_sucursales: list[pd.DataFrame] = []

    productos_out = DATOS_LIMPIOS_DIR / "productos.csv"
    productos_tmp = productos_out.with_suffix(".csv.tmp")
    header_escrito = False
    total_filas_productos = 0
    fechas_procesadas = []

    for zip_path in zips_existentes:
        comercios_l, sucursales_l, productos_l = procesar_zip_principal(zip_path)
        all_comercios.extend(comercios_l)
        all_sucursales.extend(sucursales_l)

        # Consolidar productos de este dia y escribir a disco inmediatamente
        if productos_l:
            df_prod_dia = pd.concat(productos_l, ignore_index=True)
            df_prod_dia = convertir_precios(df_prod_dia)

            # Deduplicar dentro del dia
            cols_dedup_prod = [
                "id_comercio", "id_bandera", "id_sucursal",
                "id_producto", "fecha_relevamiento",
            ]
            cols_presentes = [c for c in cols_dedup_prod if c in df_prod_dia.columns]
            df_prod_dia = df_prod_dia.drop_duplicates(
                subset=cols_presentes, keep="last"
            )

            fecha = df_prod_dia["fecha_relevamiento"].iloc[0] if len(df_prod_dia) > 0 else "?"
            fechas_procesadas.append(fecha)
            n_filas = len(df_prod_dia)
            total_filas_productos += n_filas
            print(f"  -> Productos del dia {fecha}: {n_filas} filas")

            # Append al archivo temporal
            df_prod_dia.to_csv(
                productos_tmp,
                index=False,
                encoding="utf-8",
                mode="a",
                header=not header_escrito,
            )
            header_escrito = True

            # Liberar memoria
            del df_prod_dia
            del productos_l
            gc.collect()

    # ------------------------------------------------------------------
    # Consolidar comercios (dedup global, dato maestro sin fecha)
    # ------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("Consolidando comercios...")

    if all_comercios:
        df_comercios = pd.concat(all_comercios, ignore_index=True)
        df_comercios = df_comercios.drop(columns=["fecha_relevamiento"])
        df_comercios = df_comercios.drop_duplicates(
            subset=["id_comercio", "id_bandera"]
        )
        print(f"  Comercios unicos: {len(df_comercios)}")
    else:
        df_comercios = pd.DataFrame()
        print("  [WARN] No se encontraron datos de comercios")

    # ------------------------------------------------------------------
    # Consolidar sucursales (dedup global, dato maestro sin fecha)
    # ------------------------------------------------------------------
    print("Consolidando sucursales...")

    if all_sucursales:
        df_sucursales = pd.concat(all_sucursales, ignore_index=True)
        df_sucursales = df_sucursales.drop(columns=["fecha_relevamiento"])

        # Eliminar filas corruptas (campos corridos del origen)
        n_antes = len(df_sucursales)
        cols_requeridas = ["id_comercio", "id_bandera", "id_sucursal"]
        df_sucursales = df_sucursales.dropna(subset=cols_requeridas)
        # Verificar que id_comercio sea numerico (descarta filas con datos corridos)
        df_sucursales = df_sucursales[
            df_sucursales["id_comercio"].astype(str).str.strip().str.match(r"^\d+$")
        ]
        n_eliminadas = n_antes - len(df_sucursales)
        if n_eliminadas > 0:
            print(f"  Filas corruptas eliminadas: {n_eliminadas}")

        df_sucursales = df_sucursales.drop_duplicates(
            subset=["id_comercio", "id_bandera", "id_sucursal"]
        )
        print(f"  Sucursales unicas: {len(df_sucursales)}")
    else:
        df_sucursales = pd.DataFrame()
        print("  [WARN] No se encontraron datos de sucursales")

    # ------------------------------------------------------------------
    # Guardar resultados
    # ------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("Guardando archivos limpios...")

    if not df_comercios.empty:
        guardar_csv_seguro(
            df_comercios, DATOS_LIMPIOS_DIR / "comercios.csv", "comercios"
        )

    if not df_sucursales.empty:
        guardar_csv_seguro(
            df_sucursales, DATOS_LIMPIOS_DIR / "sucursales.csv", "sucursales"
        )

    # Mover archivo temporal de productos a su ubicacion final
    if productos_tmp.exists() and total_filas_productos > 0:
        try:
            if productos_out.exists():
                os.remove(productos_out)
            os.rename(productos_tmp, productos_out)
            tamano_mb = productos_out.stat().st_size / 1024 / 1024
            print(f"  productos.csv: {total_filas_productos} filas ({tamano_mb:.1f} MB)")
        except PermissionError:
            print(f"  [WARN] No se pudo renombrar productos temporales.")
            print(f"  El archivo quedo en: {productos_tmp}")
    elif productos_tmp.exists():
        os.remove(productos_tmp)

    print(f"\n  Fechas de relevamiento procesadas: {sorted(fechas_procesadas)}")

    print("\n" + "=" * 70)
    print("Extraccion y limpieza completada exitosamente.")
    print(f"Archivos guardados en: {DATOS_LIMPIOS_DIR}")
    print("=" * 70)


if __name__ == "__main__":
    main()

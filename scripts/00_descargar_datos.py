"""
00_descargar_datos.py
=====================
Descarga todos los archivos ZIP desde una carpeta publica de Google Drive
y los guarda en data/raw/.

Usa gdown para descargar sin necesidad de autenticacion (la carpeta debe
tener permisos de acceso "cualquiera con el enlace").

Uso:
    python scripts/00_descargar_datos.py
"""

import sys
from pathlib import Path

import gdown

# ---------------------------------------------------------------------------
# Configuracion
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"

# ID de la carpeta de Google Drive (extraido de la URL compartida)
FOLDER_ID = "1pxQeqS21OZgyXVIySD-0LuQSX73wl4Km"
FOLDER_URL = f"https://drive.google.com/drive/folders/{FOLDER_ID}"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 70)
    print("SEPA Precios - Descarga de datos desde Google Drive")
    print("=" * 70)
    print(f"  Carpeta Drive: {FOLDER_URL}")
    print(f"  Destino local: {RAW_DIR}")

    # Crear directorio de destino
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    # Descargar todos los archivos de la carpeta
    print("\nDescargando archivos...")
    try:
        archivos = gdown.download_folder(
            url=FOLDER_URL,
            output=str(RAW_DIR),
            quiet=False,
            remaining_ok=True,
        )
    except Exception as e:
        print(f"\n[ERROR] Fallo la descarga: {e}")
        print("  Verifica que la carpeta sea publica y que gdown este instalado.")
        print("  Instalar gdown: pip install gdown")
        sys.exit(1)

    if not archivos:
        print("\n[WARN] No se descargaron archivos. Verifica el link de la carpeta.")
        sys.exit(1)

    # Resumen
    print("\n" + "-" * 70)
    print("Archivos descargados:")
    zips_encontrados = 0
    for archivo in sorted(RAW_DIR.iterdir()):
        tamano_mb = archivo.stat().st_size / 1024 / 1024
        es_zip = archivo.suffix.lower() == ".zip"
        marca = "[ZIP]" if es_zip else "     "
        print(f"  {marca} {archivo.name} ({tamano_mb:.1f} MB)")
        if es_zip:
            zips_encontrados += 1

    print(f"\n  Total archivos ZIP encontrados: {zips_encontrados}")
    print("=" * 70)
    print("Descarga completada.")
    print("  Siguiente paso: python scripts/01_extraer_y_limpiar.py")
    print("=" * 70)


if __name__ == "__main__":
    main()

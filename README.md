# Data Warehouse - SEPA Precios

Trabajo practico de Data Warehouse para una consultora ficticia de analisis comercial y precios. Analisis de precios minoristas en supermercados argentinos utilizando el dataset [SEPA Precios](https://datos.produccion.gob.ar/dataset/sepa-precios) de la Secretaria de Comercio.

## Integrantes

- Carlota Paiva
- Manuel Krivoy
- Juan Cruz Rey
- Franco Tisano

## Modelo

Modelo estrella con 5 dimensiones y 1 tabla de hechos:

| Tabla | Tipo | Jerarquica |
|---|---|---|
| `dim_producto` | Dimension | Si (categoria -> marca -> producto) |
| `dim_comercio` | Dimension | Si (razon_social -> bandera) |
| `dim_sucursal` | Dimension | No |
| `dim_ubicacion` | Dimension | Si (provincia -> localidad) |
| `dim_tiempo` | Dimension | Si (anio -> mes -> dia) |
| `fact_precio` | Hechos | - |

Medidas en `fact_precio`: precio_lista, precio_referencia, precio_promo, tiene_promo.

Herramienta OLAP: **Power BI** conectado via ODBC a la base SQLite.

## Estructura del proyecto

```
├── data/
│   ├── raw/              # ZIPs originales del dataset (no versionados)
│   └── processed/        # CSVs limpios generados por el ETL (no versionados)
│
├── docs/                  # Documentacion del proyecto
│   ├── trabajo-practico.md
│   ├── propuesta-de-grupo.md
│   ├── pendientes.md
│   ├── plan_maestro.md
│   └── documentacion_proyecto.md
│
├── scripts/               # Scripts ETL (Python)
│   ├── 00_descargar_datos.py    # Descarga ZIPs desde Google Drive
│   ├── 01_extraer_y_limpiar.py  # Extraccion y limpieza de datos crudos
│   └── 03_cargar_datos.py       # Carga de datos limpios al DW SQLite
│
├── sql/                   # Definicion del esquema del Data Warehouse
│   └── 02_crear_schema.sql      # DDL modelo estrella (SQLite)
│
├── requirements.txt       # Dependencias Python
└── .gitignore
```

## Pipeline ETL

0. **Descargar datos** (`scripts/00_descargar_datos.py`): Descarga todos los ZIPs desde una carpeta publica de Google Drive a `data/raw/`.
1. **Extraer y limpiar** (`scripts/01_extraer_y_limpiar.py`): Descomprime los ZIPs, parsea los CSVs, limpia datos y genera archivos consolidados en `data/processed/`.
2. **Crear schema** (`sql/02_crear_schema.sql`): Crea las tablas del modelo estrella en SQLite.
3. **Cargar datos** (`scripts/03_cargar_datos.py`): Carga los CSVs limpios en el Data Warehouse.

## Requisitos

- Python 3.10+
- SQLite 3 (incluido en Python)
- Power BI Desktop (para visualizacion OLAP)
- Dependencias: `pip install -r requirements.txt`

## Uso

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Descargar los ZIPs desde Google Drive
python scripts/00_descargar_datos.py

# 3. Extraer y limpiar datos
python scripts/01_extraer_y_limpiar.py

# 4. Crear schema en SQLite
sqlite3 data/dw_sepa_precios.db < sql/02_crear_schema.sql

# 5. Cargar datos al DW
python scripts/03_cargar_datos.py
```

# Data Warehouse - SEPA Precios

Trabajo práctico de Data Warehouse. Análisis de precios minoristas en supermercados argentinos utilizando el dataset [SEPA Precios](https://datos.produccion.gob.ar/dataset/sepa-precios) de la Secretaría de Comercio.

## Estructura del proyecto

```
├── data/
│   ├── raw/              # ZIPs originales del dataset (no versionados)
│   └── processed/        # CSVs limpios generados por el ETL (no versionados)
│
├── docs/                  # Documentación del proyecto
│   ├── trabajo-practico.md
│   ├── propuesta-de-grupo.md
│   ├── consejo-de-alumnos.md
│   ├── plan_maestro.md
│   └── documentacion_proyecto.md
│
├── scripts/               # Scripts ETL (Python)
│   ├── 01_extraer_y_limpiar.py   # Extracción y limpieza de datos crudos
│   └── 03_cargar_datos.py        # Carga de datos limpios al DW SQLite
│
├── sql/                   # Definición del esquema del Data Warehouse
│   └── 02_crear_schema.sql       # DDL modelo estrella (SQLite)
│
├── notebooks/             # Jupyter notebooks para exploración y análisis
├── requirements.txt       # Dependencias Python
└── .gitignore
```

## Pipeline ETL

1. **Extraer y limpiar** (`scripts/01_extraer_y_limpiar.py`): Descomprime los ZIPs, parsea los CSVs, limpia datos y genera archivos consolidados en `data/processed/`.
2. **Crear schema** (`sql/02_crear_schema.sql`): Crea las tablas del modelo estrella en SQLite.
3. **Cargar datos** (`scripts/03_cargar_datos.py`): Carga los CSVs limpios en el Data Warehouse.

## Requisitos

- Python 3.10+
- SQLite 3 (incluido en Python)
- Dependencias: `pip install -r requirements.txt`

## Uso

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Colocar los ZIPs descargados en data/raw/

# 3. Extraer y limpiar datos
python scripts/01_extraer_y_limpiar.py

# 4. Crear schema en SQLite
sqlite3 data/dw_sepa_precios.db < sql/02_crear_schema.sql

# 5. Cargar datos al DW
python scripts/03_cargar_datos.py
```

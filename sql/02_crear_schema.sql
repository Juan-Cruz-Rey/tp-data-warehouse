-- ============================================================================
-- Script DDL: Data Warehouse SEPA Precios (Modelo Estrella)
-- Base de datos: dw_sepa_precios.db (SQLite)
-- Fuente: dataset SEPA Precios (comercio.csv, sucursales.csv, productos.csv)
-- ============================================================================
-- Este script es idempotente: puede ejecutarse múltiples veces sin error.
-- Las tablas se eliminan en orden inverso de dependencia (fact -> dims)
-- y se crean en orden directo (dims -> fact).
--
-- Uso: sqlite3 data/dw_sepa_precios.db < sql/02_crear_schema.sql
-- ============================================================================

-- Activar foreign keys (desactivadas por defecto en SQLite)
PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- 1. Eliminar tablas existentes (orden inverso: primero la fact, luego dims)
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS fact_precio;

-- Tablas huérfanas de versiones anteriores del schema
DROP TABLE IF EXISTS fact_precios;
DROP TABLE IF EXISTS dim_promocion;
DROP TABLE IF EXISTS dim_tipo_sucursal;
DROP TABLE IF EXISTS dim_unidad_medida;

DROP TABLE IF EXISTS dim_tiempo;
DROP TABLE IF EXISTS dim_producto;
DROP TABLE IF EXISTS dim_comercio;
DROP TABLE IF EXISTS dim_sucursal;
DROP TABLE IF EXISTS dim_ubicacion;

-- ============================================================================
--  DIMENSIONES
-- ============================================================================

-- ---------------------------------------------------------------------------
-- dim_producto: información descriptiva de cada producto (jerárquica).
-- Jerarquía: categoria_inferida → marca → producto
-- ---------------------------------------------------------------------------
CREATE TABLE dim_producto (
    sk_producto         INTEGER PRIMARY KEY AUTOINCREMENT,
    ean                 TEXT    UNIQUE,
    descripcion         TEXT,
    marca               TEXT,
    categoria_inferida  TEXT
);

CREATE INDEX idx_producto_ean               ON dim_producto (ean);
CREATE INDEX idx_producto_marca             ON dim_producto (marca);
CREATE INDEX idx_producto_categoria         ON dim_producto (categoria_inferida);
CREATE INDEX idx_producto_categoria_marca   ON dim_producto (categoria_inferida, marca);

-- ---------------------------------------------------------------------------
-- dim_comercio: cadena / empresa comercial (jerárquica).
-- Jerarquía: razon_social (empresa) → bandera_nombre (cadena)
-- ---------------------------------------------------------------------------
CREATE TABLE dim_comercio (
    sk_comercio     INTEGER PRIMARY KEY AUTOINCREMENT,
    razon_social    TEXT,
    bandera_nombre  TEXT,
    UNIQUE (razon_social, bandera_nombre)
);

CREATE INDEX idx_comercio_bandera       ON dim_comercio (bandera_nombre);
CREATE INDEX idx_comercio_razon_social  ON dim_comercio (razon_social);

-- ---------------------------------------------------------------------------
-- dim_sucursal: punto de venta físico.
-- ---------------------------------------------------------------------------
CREATE TABLE dim_sucursal (
    sk_sucursal     INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre          TEXT,
    direccion       TEXT,
    tipo_sucursal   TEXT,
    UNIQUE (nombre, direccion, tipo_sucursal)
);

CREATE INDEX idx_sucursal_tipo ON dim_sucursal (tipo_sucursal);

-- ---------------------------------------------------------------------------
-- dim_ubicacion: ubicación geográfica jerárquica.
-- Jerarquía: provincia_nombre → localidad
-- ---------------------------------------------------------------------------
CREATE TABLE dim_ubicacion (
    sk_ubicacion        INTEGER PRIMARY KEY AUTOINCREMENT,
    provincia_codigo    TEXT,
    provincia_nombre    TEXT,
    localidad           TEXT,
    UNIQUE (provincia_codigo, localidad)
);

CREATE INDEX idx_ubicacion_provincia            ON dim_ubicacion (provincia_nombre);
CREATE INDEX idx_ubicacion_provincia_localidad  ON dim_ubicacion (provincia_nombre, localidad);

-- ---------------------------------------------------------------------------
-- dim_tiempo: dimensión temporal jerárquica.
-- Jerarquía: anio → mes → dia
-- Se puebla con un rango de fechas; permite análisis por día, mes y año.
-- ---------------------------------------------------------------------------
CREATE TABLE dim_tiempo (
    sk_tiempo   INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha       TEXT    NOT NULL UNIQUE,
    anio        INTEGER NOT NULL,
    mes         INTEGER NOT NULL,
    dia         INTEGER NOT NULL
);

CREATE INDEX idx_tiempo_anio_mes    ON dim_tiempo (anio, mes);
CREATE INDEX idx_tiempo_fecha       ON dim_tiempo (fecha);

-- ============================================================================
--  TABLA DE HECHOS
-- ============================================================================

-- ---------------------------------------------------------------------------
-- fact_precio: tabla central del modelo estrella.
-- Cada fila representa el precio de un producto en una sucursal en un momento
-- dado, con sus atributos dimensionales asociados.
--
-- Medidas:
--   - precio_lista:       precio de lista del producto
--   - precio_referencia:  precio de referencia (por unidad estándar)
--   - precio_promo:       precio promocional (opcional, puede ser NULL)
--   - tiene_promo:        flag booleano (0/1) indicando promoción activa
-- ---------------------------------------------------------------------------
CREATE TABLE fact_precio (
    id_hecho            INTEGER PRIMARY KEY AUTOINCREMENT,
    sk_producto         INTEGER NOT NULL,
    sk_comercio         INTEGER NOT NULL,
    sk_sucursal         INTEGER NOT NULL,
    sk_ubicacion        INTEGER NOT NULL,
    sk_tiempo           INTEGER NOT NULL,

    -- Medidas
    precio_lista        REAL,
    precio_referencia   REAL,
    precio_promo        REAL,
    tiene_promo         INTEGER NOT NULL DEFAULT 0,

    -- Foreign keys hacia cada dimensión
    FOREIGN KEY (sk_producto)   REFERENCES dim_producto (sk_producto),
    FOREIGN KEY (sk_comercio)   REFERENCES dim_comercio (sk_comercio),
    FOREIGN KEY (sk_sucursal)   REFERENCES dim_sucursal (sk_sucursal),
    FOREIGN KEY (sk_ubicacion)  REFERENCES dim_ubicacion (sk_ubicacion),
    FOREIGN KEY (sk_tiempo)     REFERENCES dim_tiempo (sk_tiempo)
);

-- ---------------------------------------------------------------------------
-- Índices analíticos sobre la tabla de hechos
-- Optimizan las consultas más frecuentes en un DW de precios.
-- ---------------------------------------------------------------------------
CREATE INDEX idx_fact_tiempo            ON fact_precio (sk_tiempo);
CREATE INDEX idx_fact_producto          ON fact_precio (sk_producto);
CREATE INDEX idx_fact_comercio          ON fact_precio (sk_comercio);
CREATE INDEX idx_fact_sucursal          ON fact_precio (sk_sucursal);
CREATE INDEX idx_fact_ubicacion         ON fact_precio (sk_ubicacion);
CREATE INDEX idx_fact_producto_tiempo   ON fact_precio (sk_producto, sk_tiempo);
CREATE INDEX idx_fact_comercio_tiempo   ON fact_precio (sk_comercio, sk_tiempo);
CREATE INDEX idx_fact_ubicacion_tiempo  ON fact_precio (sk_ubicacion, sk_tiempo);
CREATE INDEX idx_fact_promo             ON fact_precio (tiene_promo);

-- ============================================================================
-- Fin del script DDL
-- ============================================================================

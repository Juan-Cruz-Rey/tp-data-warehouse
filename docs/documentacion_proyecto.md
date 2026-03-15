# Documentacion del Proyecto: Data Warehouse SEPA Precios

**Materia:** Data Warehousing
**Fecha:** Marzo 2026
**Equipo:** Trabajo Practico - Modelo Estrella

---

## Indice

1. [Descripcion de la organizacion y contexto del negocio](#1-descripcion-de-la-organizacion-y-contexto-del-negocio)
2. [Descripcion de la necesidad / problema a resolver](#2-descripcion-de-la-necesidad--problema-a-resolver)
3. [Modelos de datos existentes (OLTP)](#3-modelos-de-datos-existentes-oltp)
4. [Modelo Multidimensional (Diagrama Estrella)](#4-modelo-multidimensional-diagrama-estrella)
5. [Mapeo de datos](#5-mapeo-de-datos)
6. [Decisiones de diseno](#6-decisiones-de-diseno)
7. [Stack tecnologico](#7-stack-tecnologico)
8. [Flujo de trabajo](#8-flujo-de-trabajo)
9. [Volumetria](#9-volumetria)

---

## 1. Descripcion de la organizacion y contexto del negocio

### Organizacion

El **Sistema Electronico de Publicidad de Precios Argentino (SEPA)** es una iniciativa de la **Secretaria de Comercio**, dependiente del **Ministerio de Produccion de la Nacion Argentina**. Fue creado con el objetivo de brindar transparencia en los precios minoristas de productos de consumo masivo en todo el territorio nacional.

### Funcionamiento

Las cadenas de supermercados, hipermercados y autoservicios de todo el pais estan obligadas a reportar diariamente sus precios de venta al publico a traves de la plataforma SEPA. Cada cadena comercial (identificada como "comercio" y "bandera") informa los precios de todos los productos en cada una de sus sucursales.

Los datos se publican en formato abierto (archivos ZIP conteniendo CSVs separados por pipe `|`) y estan disponibles para consulta publica, lo que permite a consumidores, investigadores y organismos de control acceder a informacion detallada sobre precios.

### Alcance del dataset utilizado

- **Periodo:** 4 dias de relevamiento (lunes 2026-03-09 a jueves 2026-03-12).
- **Cobertura:** Cadenas de supermercados a nivel nacional, abarcando todas las provincias argentinas.
- **Archivos fuente:** 4 archivos ZIP principales (uno por dia), cada uno conteniendo sub-ZIPs por comercio con 3 CSVs internos.

---

## 2. Descripcion de la necesidad / problema a resolver

### Problema

Los datos crudos de SEPA Precios se publican como archivos planos (CSV) anidados dentro de multiples niveles de compresion ZIP. Esta estructura dificulta:

- La consulta rapida y flexible de precios.
- La comparacion de precios entre cadenas, regiones o categorias de productos.
- El analisis de tendencias temporales de precios.
- La generacion de reportes ejecutivos y dashboards interactivos.

### Necesidad

Se requiere construir un **Data Warehouse con modelo estrella** que permita analizar los precios minoristas de supermercados argentinos de forma eficiente, respondiendo a preguntas de negocio como:

| # | Pregunta de negocio | Dimensiones involucradas |
|---|---------------------|--------------------------|
| 1 | Cual es el precio promedio de un producto por provincia? | dim_producto, dim_ubicacion |
| 2 | Que cadena ofrece los precios mas competitivos? | dim_comercio, dim_producto |
| 3 | Que porcentaje de productos tienen promocion activa? | dim_promocion, dim_comercio |
| 4 | Como varian los precios entre tipos de sucursal (hipermercado vs autoservicio)? | dim_tipo_sucursal |
| 5 | Como evolucionan los precios dia a dia? | dim_tiempo |
| 6 | Cuales son las marcas mas caras/baratas por categoria? | dim_producto (marca, categoria) |
| 7 | Que regiones tienen los precios mas altos? | dim_ubicacion (provincia, localidad) |

### Objetivo

Disenar e implementar un proceso ETL completo que:

1. Extraiga los datos de los archivos ZIP/CSV originales.
2. Limpie, normalice y transforme los datos.
3. Cargue los datos en un modelo estrella en MySQL.
4. Permita su explotacion analitica mediante Power BI.

---

## 3. Modelos de datos existentes (OLTP)

### Estructura original del dataset

El dataset SEPA Precios se organiza en una jerarquia de archivos comprimidos:

```
sepa_lunes.zip
  └── 2026-03-09/
        ├── sepa_1_comercio-sepa-47.zip
        │     ├── comercio.csv
        │     ├── sucursales.csv
        │     └── productos.csv
        ├── sepa_1_comercio-sepa-15.zip
        │     ├── comercio.csv
        │     ├── sucursales.csv
        │     └── productos.csv
        └── ... (un sub-zip por comercio)
```

Cada sub-ZIP contiene 3 archivos CSV separados por pipe (`|`):

### Tabla: comercio.csv

Datos maestros de la cadena comercial.

| Columna | Tipo | Descripcion |
|---------|------|-------------|
| id_comercio | INT | Identificador del comercio |
| id_bandera | INT | Identificador de la bandera comercial |
| comercio_cuit | VARCHAR | CUIT de la empresa |
| comercio_razon_social | VARCHAR | Razon social |
| comercio_bandera_nombre | VARCHAR | Nombre de la bandera (ej: "Supermercados DIA") |
| comercio_bandera_url | VARCHAR | URL del sitio web |
| comercio_ultima_actualizacion | DATETIME | Ultima actualizacion del registro |
| comercio_version_sepa | DECIMAL | Version del formato SEPA |

### Tabla: sucursales.csv

Datos de cada punto de venta (sucursal).

| Columna | Tipo | Descripcion |
|---------|------|-------------|
| id_comercio | INT | FK al comercio |
| id_bandera | INT | FK a la bandera |
| id_sucursal | INT | Identificador de la sucursal (unico dentro del comercio) |
| sucursales_nombre | VARCHAR | Nombre de la sucursal |
| sucursales_tipo | VARCHAR | Tipo: Supermercado, Autoservicio, Hipermercado, etc. |
| sucursales_calle | VARCHAR | Direccion: calle |
| sucursales_numero | VARCHAR | Direccion: numero |
| sucursales_latitud | DECIMAL | Coordenada geografica |
| sucursales_longitud | DECIMAL | Coordenada geografica |
| sucursales_observaciones | VARCHAR | Observaciones |
| sucursales_barrio | VARCHAR | Barrio |
| sucursales_codigo_postal | VARCHAR | Codigo postal |
| sucursales_localidad | VARCHAR | Localidad / ciudad |
| sucursales_provincia | VARCHAR | Codigo ISO de provincia (ej: AR-B) |
| sucursales_*_horario_atencion | VARCHAR | Horarios por dia de semana (7 columnas) |

### Tabla: productos.csv

Registros de precios por producto, sucursal y dia.

| Columna | Tipo | Descripcion |
|---------|------|-------------|
| id_comercio | INT | FK al comercio |
| id_bandera | INT | FK a la bandera |
| id_sucursal | INT | FK a la sucursal |
| id_producto | INT | Identificador del producto |
| productos_ean | VARCHAR | Codigo de barras EAN |
| productos_descripcion | VARCHAR | Descripcion del producto |
| productos_cantidad_presentacion | DECIMAL | Cantidad de la presentacion |
| productos_unidad_medida_presentacion | VARCHAR | Unidad de medida (gr, lt, un, etc.) |
| productos_marca | VARCHAR | Marca del producto |
| productos_precio_lista | DECIMAL | Precio de lista |
| productos_precio_referencia | DECIMAL | Precio por unidad de referencia |
| productos_cantidad_referencia | DECIMAL | Cantidad de referencia |
| productos_unidad_medida_referencia | VARCHAR | Unidad de referencia |
| productos_precio_unitario_promo1 | DECIMAL | Precio promocional 1 |
| productos_leyenda_promo1 | VARCHAR | Descripcion de la promo 1 |
| productos_precio_unitario_promo2 | DECIMAL | Precio promocional 2 |
| productos_leyenda_promo2 | VARCHAR | Descripcion de la promo 2 |

### Relaciones entre tablas OLTP

```
+-------------------+          +---------------------+
|  comercio.csv     |          |   sucursales.csv    |
|-------------------|          |---------------------|
| id_comercio  (PK) +----+----+ id_comercio    (FK)  |
| id_bandera   (PK) +----+----+ id_bandera     (FK)  |
| comercio_cuit     |    |    | id_sucursal    (PK)  |
| comercio_razon_   |    |    | sucursales_nombre    |
|   social          |    |    | sucursales_tipo      |
| comercio_bandera_ |    |    | sucursales_provincia |
|   nombre          |    |    | sucursales_localidad |
| comercio_bandera_ |    |    | ...                  |
|   url             |    |    +----------+-----------+
+-------------------+    |               |
                         |               |
                         |    +----------+-----------+
                         |    |   productos.csv      |
                         |    |----------------------|
                         +----+ id_comercio    (FK)  |
                         +----+ id_bandera     (FK)  |
                              | id_sucursal    (FK)  |
                              | id_producto    (PK)  |
                              | productos_ean        |
                              | productos_descripcion|
                              | productos_precio_    |
                              |   lista              |
                              | ...                  |
                              +----------------------+
```

**Clave compuesta:** La relacion entre las 3 tablas se establece a traves de la combinacion `(id_comercio, id_bandera)`. En `productos.csv` se agrega `id_sucursal` para vincular con la sucursal especifica y `id_producto` para identificar el producto.

---

## 4. Modelo Multidimensional (Diagrama Estrella)

### Diagrama del modelo

```
                    +-------------------+
                    |   dim_tiempo      |
                    |-------------------|
                    | sk_tiempo (PK)    |
                    | fecha             |
                    | anio              |        +---------------------+
                    | mes               |        |  dim_tipo_sucursal  |
                    | dia               |        |---------------------|
                    | dia_semana        |        | sk_tipo_suc (PK)    |
                    | nombre_mes        |        | tipo                |
                    +--------+----------+        +----------+----------+
                             |                              |
                             |                              |
+------------------+         |    +------------------------+|   +-------------------+
|  dim_producto    |         |    |     fact_precios       ||   |  dim_unidad_medida|
|------------------|         |    |------------------------|+   |-------------------|
| sk_producto (PK) +---------+----+ sk_producto (FK)       |    | sk_unidad (PK)    |
| id_producto_orig |         |    | sk_comercio (FK)       +----+ unidad_present    |
| ean              |         +----+ sk_sucursal (FK)       |    | unidad_referencia |
| descripcion      |              | sk_ubicacion (FK)      |    +-------------------+
| marca            |         +----+ sk_tiempo (FK)         |
+------------------+         |    | sk_tipo_sucursal (FK)  |    +-------------------+
                             |    | sk_unidad_medida (FK)  |    |  dim_promocion    |
+------------------+         |    | sk_promocion (FK)      +----+-------------------|
|  dim_comercio    |         |    |------------------------|    | sk_promocion (PK) |
|------------------|         |    | precio_lista      [M1] |    | tiene_promo1      |
| sk_comercio (PK) +---------+    | precio_referencia [M2] |    | leyenda_promo1    |
| id_comercio_orig |              | cant_presentacion      |    | precio_promo1     |
| id_bandera       |              | cant_referencia        |    | tiene_promo2      |
| cuit             |              +-----+------------------+    | leyenda_promo2    |
| razon_social     |                    |                       | precio_promo2     |
| bandera_nombre   |                    |                       +-------------------+
+------------------+         +----------+---------+
                             |                    |
                      +------+--------+   +-------+-----------+
                      | dim_sucursal  |   |  dim_ubicacion    |
                      |---------------|   |-------------------|
                      | sk_suc (PK)   |   | sk_ubic (PK)      |
                      | id_suc_origen |   | provincia         |
                      | id_com_origen |   | localidad         |
                      | id_bandera    |   | barrio            |
                      | nombre        |   | codigo_postal     |
                      | calle         |   +-------------------+
                      | numero        |
                      | latitud       |
                      | longitud      |
                      +---------------+
```

### Tabla de hechos: `fact_precios`

| Campo | Tipo | Rol | Descripcion |
|-------|------|-----|-------------|
| sk_producto | INT | FK | Clave surrogada a dim_producto |
| sk_comercio | INT | FK | Clave surrogada a dim_comercio |
| sk_sucursal | INT | FK | Clave surrogada a dim_sucursal |
| sk_ubicacion | INT | FK | Clave surrogada a dim_ubicacion |
| sk_tiempo | INT | FK | Clave surrogada a dim_tiempo |
| sk_unidad_medida | INT | FK | Clave surrogada a dim_unidad_medida |
| sk_promocion | INT | FK | Clave surrogada a dim_promocion |
| sk_tipo_sucursal | INT | FK | Clave surrogada a dim_tipo_sucursal |
| precio_lista | DECIMAL(12,2) | Medida | Precio de lista del producto |
| precio_referencia | DECIMAL(12,2) | Medida | Precio por unidad estandar |
| cantidad_presentacion | DECIMAL(10,3) | Atributo | Cantidad de la presentacion |
| cantidad_referencia | DECIMAL(10,3) | Atributo | Cantidad de referencia |

**Clave primaria compuesta:** `(sk_producto, sk_comercio, sk_sucursal, sk_tiempo)`

**Granularidad:** Un registro por cada combinacion unica de producto + sucursal + dia de relevamiento.

### Dimensiones (8 dimensiones, 4 jerarquicas)

| # | Dimension | Jerarquica | Niveles de jerarquia | Campos |
|---|-----------|:----------:|----------------------|--------|
| 1 | dim_producto | SI | categoria_inferida -> marca -> descripcion | 5 |
| 2 | dim_comercio | SI | razon_social -> bandera_nombre | 6 |
| 3 | dim_sucursal | NO | - | 9 |
| 4 | dim_ubicacion | SI | provincia -> localidad -> barrio -> codigo_postal | 5 |
| 5 | dim_tiempo | SI | anio -> mes -> dia | 7 |
| 6 | dim_tipo_sucursal | NO | - | 2 |
| 7 | dim_unidad_medida | NO | - | 3 |
| 8 | dim_promocion | NO | - | 7 |

### Medidas

| # | Medida | Tipo | Descripcion | Agregaciones tipicas |
|---|--------|------|-------------|---------------------|
| 1 | precio_lista | DECIMAL(12,2) | Precio de venta al publico informado | AVG, MIN, MAX, COUNT |
| 2 | precio_referencia | DECIMAL(12,2) | Precio por unidad de medida estandar (permite comparar entre presentaciones distintas) | AVG, MIN, MAX |

**Medidas derivadas calculables:**

- `descuento_promo = precio_lista - precio_promo1` (ahorro absoluto, usando dim_promocion.precio_promo1)
- `pct_descuento = (precio_lista - precio_promo1) / precio_lista * 100` (porcentaje de descuento)
- `tiene_promocion = CASE WHEN dim_promocion.tiene_promo1 = TRUE THEN 1 ELSE 0 END`

---

## 5. Mapeo de datos

### fact_precios

| Campo destino | CSV origen | Columna origen | Transformacion |
|---------------|-----------|----------------|----------------|
| sk_producto | productos.csv | id_producto | Lookup a dim_producto |
| sk_comercio | productos.csv | id_comercio + id_bandera | Lookup a dim_comercio |
| sk_sucursal | productos.csv | id_comercio + id_bandera + id_sucursal | Lookup a dim_sucursal |
| sk_ubicacion | sucursales.csv | provincia + localidad + barrio + codigo_postal | Lookup a dim_ubicacion (join por sucursal) |
| sk_tiempo | nombre del ZIP | Fecha extraida del directorio (ej: "2026-03-09/") | Lookup a dim_tiempo |
| sk_tipo_sucursal | sucursales.csv | sucursales_tipo | Lookup a dim_tipo_sucursal (join por sucursal) |
| sk_unidad_medida | productos.csv | unidad_medida_presentacion + unidad_medida_referencia | Lookup a dim_unidad_medida |
| sk_promocion | productos.csv | precio_promo1, leyenda_promo1, promo2 | Lookup a dim_promocion |
| precio_lista | productos.csv | productos_precio_lista | CAST a DECIMAL |
| precio_referencia | productos.csv | productos_precio_referencia | CAST a DECIMAL |
| cantidad_presentacion | productos.csv | productos_cantidad_presentacion | CAST a DECIMAL |
| cantidad_referencia | productos.csv | productos_cantidad_referencia | CAST a DECIMAL |

### dim_producto

| Campo destino | Columna origen | Transformacion |
|---------------|----------------|----------------|
| id_producto_origen | productos.csv: id_producto | Directo |
| ean | productos.csv: productos_ean | Directo |
| descripcion | productos.csv: productos_descripcion | TRIM |
| marca | productos.csv: productos_marca | TRIM, UPPER |

### dim_comercio

| Campo destino | Columna origen | Transformacion |
|---------------|----------------|----------------|
| id_comercio_origen | comercio.csv: id_comercio | Directo |
| id_bandera | comercio.csv: id_bandera | Directo |
| cuit | comercio.csv: comercio_cuit | Directo |
| razon_social | comercio.csv: comercio_razon_social | TRIM |
| bandera_nombre | comercio.csv: comercio_bandera_nombre | TRIM |

### dim_sucursal

| Campo destino | Columna origen | Transformacion |
|---------------|----------------|----------------|
| id_sucursal_origen | sucursales.csv: id_sucursal | Directo |
| id_comercio_origen | sucursales.csv: id_comercio | Directo |
| id_bandera | sucursales.csv: id_bandera | Directo |
| nombre | sucursales.csv: sucursales_nombre | TRIM |
| calle | sucursales.csv: sucursales_calle | TRIM |
| numero | sucursales.csv: sucursales_numero | TRIM |
| latitud | sucursales.csv: sucursales_latitud | CAST a DECIMAL |
| longitud | sucursales.csv: sucursales_longitud | CAST a DECIMAL |

### dim_ubicacion

| Campo destino | Columna origen | Transformacion |
|---------------|----------------|----------------|
| provincia | sucursales.csv: sucursales_provincia | TRIM |
| localidad | sucursales.csv: sucursales_localidad | TRIM |
| barrio | sucursales.csv: sucursales_barrio | TRIM |
| codigo_postal | sucursales.csv: sucursales_codigo_postal | TRIM |

### dim_tiempo

| Campo destino | Origen | Transformacion |
|---------------|--------|----------------|
| fecha | Nombre del directorio ZIP | Parsear "2026-03-09" de la ruta |
| dia | fecha | DAY(fecha) |
| dia_semana | fecha | DAYNAME(fecha) en espanol |
| mes | fecha | MONTH(fecha) |
| nombre_mes | fecha | MONTHNAME(fecha) en espanol |
| anio | fecha | YEAR(fecha) |

### dim_tipo_sucursal

| Campo destino | Columna origen | Transformacion |
|---------------|----------------|----------------|
| tipo | sucursales.csv: sucursales_tipo | TRIM, normalizacion de capitalizacion |

### dim_unidad_medida

| Campo destino | Columna origen | Transformacion |
|---------------|----------------|----------------|
| unidad_presentacion | productos.csv: productos_unidad_medida_presentacion | LOWER, mapeo de sinonimos (GR/G -> "gr", LT/L -> "lt", CC/ML -> "ml", UN/UD -> "un") |
| unidad_referencia | productos.csv: productos_unidad_medida_referencia | LOWER, mapeo de sinonimos |

### dim_promocion

| Campo destino | Columna origen | Transformacion |
|---------------|----------------|----------------|
| tiene_promo1 | productos.csv: productos_precio_unitario_promo1 | TRUE si no vacio, FALSE si vacio |
| leyenda_promo1 | productos.csv: productos_leyenda_promo1 | TRIM |
| precio_promo1 | productos.csv: productos_precio_unitario_promo1 | CAST a DECIMAL, NULL si vacio |
| tiene_promo2 | productos.csv: productos_precio_unitario_promo2 | TRUE si no vacio, FALSE si vacio |
| leyenda_promo2 | productos.csv: productos_leyenda_promo2 | TRIM |
| precio_promo2 | productos.csv: productos_precio_unitario_promo2 | CAST a DECIMAL, NULL si vacio |

---

## 6. Decisiones de diseno

### Decisiones a nivel de modelo de datos

| # | Decision | Justificacion |
|---|----------|---------------|
| D1 | **Claves surrogadas en todas las dimensiones** | Se utilizan claves surrogadas (INT autoincremental) en lugar de claves naturales. Las claves naturales del dataset (id_comercio, id_sucursal, id_producto) se conservan como atributos para trazabilidad, pero las FK en la tabla de hechos apuntan a surrogadas. Esto permite independencia del sistema fuente y facilita el manejo de cambios historicos (SCD). |
| D2 | **Categoria de producto inferida** | El dataset no incluye una categoria explicita de producto. Se infiere a partir de palabras clave en la descripcion durante el ETL (ej: "LECHE" -> Lacteos, "CERVEZA" -> Bebidas Alcoholicas, "FIDEOS" -> Almacen). Es imperfecto pero necesario para habilitar drill-down por categoria. |
| D3 | **Separacion de dim_ubicacion y dim_sucursal** | Se separa la ubicacion geografica de la sucursal en dos dimensiones para evitar redundancia y permitir analisis geograficos independientes. Muchas sucursales comparten la misma combinacion provincia + localidad + barrio. |
| D6 | **Precios promocionales en dim_promocion** | El precio promocional se almacena en la dimension de promocion junto con los flags y leyendas, en lugar de como medida en la fact table. La promo 2 esta practicamente siempre vacia en los datos observados, pero se preserva en la dimension para consulta. |
| D7 | **Granularidad: producto x sucursal x dia** | Cada registro de la fact table representa un producto en una sucursal en un dia especifico. Esta es la maxima granularidad posible con los datos y permite cualquier tipo de roll-up posterior. |
| D8 | **Horarios de atencion excluidos** | Los 7 campos de horarios de atencion por dia de semana no se incluyen en el modelo porque no aportan al analisis de precios y aumentarian la complejidad sin beneficio analitico. |

### Decisiones de tecnologia

| # | Decision | Justificacion |
|---|----------|---------------|
| D9 | **MySQL 8.x como RDBMS** | Se elige MySQL como motor de base de datos segun requerimiento del TP. El modelo estrella se implementa con tablas InnoDB con foreign keys explicitas para integridad referencial. Charset utf8mb4 para soporte completo de caracteres. |
| - | **Python 3.x + pandas para ETL** | Python con pandas permite manipular grandes volumenes de datos tabulares de forma eficiente, con funciones nativas para limpieza, transformacion y deduplicacion. |
| - | **Power BI para visualizacion** | Power BI se conecta directamente a MySQL y permite construir dashboards interactivos con capacidades OLAP (drill-down, slicing, dicing) sobre el modelo estrella. |

### Decisiones de ETL

| # | Decision | Justificacion |
|---|----------|---------------|
| D4 | **Normalizacion de unidades de medida** | El dataset presenta inconsistencias (GR/G/gr, LT/L/lt, UN/UD/un, CC/ML/ml). Se normalizan a minusculas y se unifican sinonimos para que las comparaciones de precio_referencia sean validas. |
| D5 | **Normalizacion de codigos de provincia** | El dataset usa codigos ISO 3166-2 (AR-B, AR-C) con alguna inconsistencia. Se normalizan todos a codigo ISO estandar. |
| - | **Deduplicacion por version SEPA** | Cuando un mismo comercio aparece en version sepa_1 y sepa_2 dentro del mismo ZIP diario, se conserva solo la version 2 (mas reciente). Si aparece en una sola version, se conserva. |
| - | **Procesamiento por chunks** | Dado el volumen de datos (~53 millones de registros de productos), la carga a MySQL se realiza en lotes (chunks) para evitar desbordamiento de memoria y timeouts. |
| - | **Limpieza de null bytes y metadata** | Los CSVs originales contienen caracteres nulos (\x00) y filas de metadata al final del archivo ("Ultima actualizacion...") que deben eliminarse antes del procesamiento. |

---

## 7. Stack tecnologico

| Componente | Tecnologia | Version | Rol |
|------------|-----------|---------|-----|
| Base de datos | MySQL | 8.x | Almacenamiento del Data Warehouse (modelo estrella con InnoDB) |
| ETL - Extraccion/Limpieza | Python + pandas | 3.x | Lectura de ZIPs, parseo de CSVs, limpieza y normalizacion de datos |
| ETL - Carga | Python + mysql-connector | 3.x | Insercion de datos transformados en las tablas del DW |
| Visualizacion / OLAP | Power BI Desktop | - | Conexion a MySQL, construccion de dashboards interactivos, drill-down |
| Control de versiones | Git | - | Versionado de scripts y documentacion |

### Diagrama de arquitectura

```
+-------------------+     +---------------------+     +------------------+     +-------------+
|  Datos fuente     |     |  ETL (Python)       |     |  Data Warehouse  |     |  Power BI   |
|  (ZIPs / CSVs)    | --> |  01_extraer_y       | --> |  MySQL 8.x       | --> |  Dashboards |
|                   |     |    limpiar.py        |     |  (dw_sepa_       |     |  OLAP       |
|  sepa_lunes.zip   |     |  03_cargar_datos.py  |     |   precios)       |     |             |
|  sepa_martes.zip  |     +---------------------+     +------------------+     +-------------+
|  sepa_miercoles   |               |                         ^
|    .zip           |               |                         |
|  sepa_jueves.zip  |     +---------------------+             |
+-------------------+     |  DDL (SQL)          |-------------+
                          |  02_crear_schema    |
                          |    .sql             |
                          +---------------------+
```

---

## 8. Flujo de trabajo

El proceso completo se ejecuta en 4 etapas secuenciales:

### Etapa 1: Extraccion y limpieza (`scripts/01_extraer_y_limpiar.py`)

**Entrada:** 4 archivos ZIP principales (uno por dia).
**Salida:** 3 archivos CSV limpios en `datos_limpios/`.

Pasos:

1. **Lectura de ZIPs:** Para cada ZIP diario, se abre y se descubre la fecha de relevamiento a partir del nombre del directorio interno (ej: `2026-03-09/`).
2. **Deduplicacion de versiones:** Si un comercio aparece en version sepa_1 y sepa_2, se conserva solo sepa_2 (mas reciente).
3. **Extraccion de sub-ZIPs:** Se abre cada sub-ZIP de comercio y se leen los 3 CSVs internos (separador pipe `|`).
4. **Limpieza:**
   - Eliminacion de BOM (Byte Order Mark) y caracteres nulos (`\x00`).
   - Eliminacion de filas de metadata ("Ultima actualizacion...").
   - TRIM de todos los campos de texto.
   - Conversion de campos de precio a tipo numerico (float).
5. **Consolidacion:**
   - `comercios.csv`: deduplicado por `(id_comercio, id_bandera)`.
   - `sucursales.csv`: deduplicado por `(id_comercio, id_bandera, id_sucursal)`.
   - `productos.csv`: conserva la columna `fecha_relevamiento`, deduplicado por `(id_comercio, id_bandera, id_sucursal, id_producto, fecha_relevamiento)`.

### Etapa 2: Creacion del schema (`scripts/02_crear_schema.sql`)

**Entrada:** Script DDL.
**Salida:** Base de datos `dw_sepa_precios` con todas las tablas creadas.

Pasos:

1. Crear la base de datos `dw_sepa_precios` (charset utf8mb4).
2. Eliminar tablas existentes en orden inverso de dependencia (fact -> dims) para idempotencia.
3. Crear las 8 tablas de dimensiones con claves surrogadas, claves unicas y constraints.
4. Crear la tabla de hechos `fact_precios` con 8 FKs y las medidas.
5. Crear indices analiticos para optimizar consultas frecuentes (por tiempo, producto, comercio, ubicacion, y combinaciones compuestas).

El script es **idempotente**: puede ejecutarse multiples veces sin error.

### Etapa 3: Carga de datos (`scripts/03_cargar_datos.py`)

**Entrada:** CSVs limpios de `datos_limpios/` + schema MySQL creado.
**Salida:** Tablas del DW pobladas.

Pasos:

1. **Cargar dimensiones** (orden independiente entre si):
   - `dim_tiempo`: generar registros para cada fecha de relevamiento (4 dias).
   - `dim_producto`: deduplicar por `(id_producto_origen, ean)`.
   - `dim_comercio`: deduplicar por `(id_comercio_origen, id_bandera)`.
   - `dim_sucursal`: deduplicar por `(id_sucursal_origen, id_comercio_origen, id_bandera)`.
   - `dim_ubicacion`: deduplicar por `(provincia, localidad, barrio, codigo_postal)`.
   - `dim_tipo_sucursal`: deduplicar por `tipo` normalizado.
   - `dim_unidad_medida`: deduplicar por `(unidad_presentacion, unidad_referencia)`.
   - `dim_promocion`: insertar combinaciones de flags y leyendas de promocion.
2. **Cargar tabla de hechos**: para cada fila de productos, resolver las 8 FK mediante lookups a las dimensiones e insertar en `fact_precios`.
3. **Validacion post-carga**: verificar conteos de registros e integridad referencial.

### Etapa 4: Conexion desde Power BI

1. Conectar Power BI Desktop a MySQL (`dw_sepa_precios`).
2. Importar las 9 tablas (8 dimensiones + 1 fact).
3. Verificar que las relaciones estrella se detecten automaticamente (o crearlas manualmente).
4. Construir medidas DAX para las medidas derivadas (descuento, porcentaje, etc.).
5. Crear dashboards con visualizaciones que respondan las preguntas de negocio.

---

## 9. Volumetria

### Datos reales del dataset procesado

| Elemento | Cantidad |
|----------|----------|
| Archivos ZIP principales | 4 (uno por dia) |
| Dias de relevamiento | 4 (2026-03-09 a 2026-03-12) |
| Comercios unicos | 39 |
| Sucursales unicas | 2,997 |
| Registros de productos (total 4 dias) | 53,118,163 |
| Registros promedio por dia | ~13,280,000 |

### Tamano de archivos limpios

| Archivo | Filas | Tamano |
|---------|-------|--------|
| comercios.csv | 39 | 4 KB |
| sucursales.csv | 2,997 | 628 KB |
| productos.csv | 53,118,163 | 5.7 GB |

### Volumetria estimada del DW

| Tabla | Registros estimados |
|-------|-------------------|
| fact_precios | ~53,000,000 |
| dim_producto | ~50,000 - 100,000 |
| dim_comercio | 39 |
| dim_sucursal | 2,997 |
| dim_ubicacion | ~1,500 - 2,500 |
| dim_tiempo | 4 |
| dim_tipo_sucursal | ~4 - 5 |
| dim_unidad_medida | ~10 - 15 |
| dim_promocion | Variable |

### Consideraciones de rendimiento

- La tabla de hechos es la mas voluminosa con mas de 53 millones de registros. Se recomienda:
  - Indexar todas las FK (ya incluido en el DDL).
  - Considerar particionamiento por fecha (`sk_tiempo`) si el volumen crece con futuras cargas.
  - La carga ETL debe realizarse en lotes (chunks) para evitar problemas de memoria.
- Los indices compuestos definidos en el DDL (`idx_fact_producto_tiempo`, `idx_fact_comercio_tiempo`, `idx_fact_ubicacion_tiempo`) optimizan las consultas analiticas mas frecuentes.

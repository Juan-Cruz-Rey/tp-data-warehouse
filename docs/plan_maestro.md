# Plan Maestro - Modelo Estrella Data Warehouse SEPA Precios

## 1. Contexto del Negocio

**Organismo:** Secretaria de Comercio de Argentina (Ministerio de Produccion).
**Dataset:** SEPA Precios - Sistema Electronico de Publicidad de Precios Argentino.
**Alcance:** Precios minoristas informados por cadenas de supermercados a nivel nacional.
**Periodo de datos disponibles:** 4 dias (lunes 2026-03-09 a jueves 2026-03-12).

**Problema a resolver:** Analizar variaciones de precios minoristas en supermercados argentinos para detectar diferencias por region geografica, categoria de producto y cadena comercial. Esto permite responder preguntas como:
- Cual es el precio promedio de un producto por provincia?
- Que cadena ofrece los precios mas competitivos?
- Que porcentaje de productos tienen promocion activa?
- Como varian los precios entre tipos de sucursal (hipermercado vs autoservicio)?

---

## 2. Modelo Estrella Propuesto

### Tabla de Hechos: `fact_precio`

| Campo | Tipo | Descripcion |
|-------|------|-------------|
| id_hecho | INT (PK, autoincremental) | Clave surrogada del hecho |
| sk_producto | INT (FK) | Clave surrogada a dim_producto |
| sk_comercio | INT (FK) | Clave surrogada a dim_comercio |
| sk_sucursal | INT (FK) | Clave surrogada a dim_sucursal |
| sk_ubicacion | INT (FK) | Clave surrogada a dim_ubicacion |
| sk_tiempo | INT (FK) | Clave surrogada a dim_tiempo |
| sk_tipo_sucursal | INT (FK) | Clave surrogada a dim_tipo_sucursal |
| sk_unidad_medida | INT (FK) | Clave surrogada a dim_unidad_medida |
| sk_promocion | INT (FK) | Clave surrogada a dim_promocion |
| **precio_lista** | DECIMAL(12,2) | **MEDIDA 1** - Precio de lista del producto |
| **precio_referencia** | DECIMAL(12,2) | **MEDIDA 2** - Precio de referencia (por unidad de medida estandar) |
| **precio_promo** | DECIMAL(12,2) | **MEDIDA 3** - Precio promocional (NULL si no hay promocion) |
| cantidad_presentacion | DECIMAL(10,3) | Cantidad de la presentacion del producto |
| cantidad_referencia | DECIMAL(10,3) | Cantidad de referencia para el precio unitario |

**Granularidad:** Un registro por cada combinacion unica de producto + sucursal + dia de relevamiento. Cada fila representa el precio informado de un producto especifico en una sucursal especifica en un dia determinado.

---

### Dimensiones (8 dimensiones, 4 jerarquicas)

#### dim_producto -- JERARQUICA

| Campo | Tipo | Descripcion |
|-------|------|-------------|
| sk_producto | INT (PK) | Clave surrogada |
| id_producto_natural | VARCHAR(20) | Clave natural (id_producto del CSV) |
| ean | VARCHAR(20) | Codigo de barras EAN |
| descripcion | VARCHAR(200) | Descripcion completa del producto |
| marca | VARCHAR(100) | Marca del producto |
| categoria_inferida | VARCHAR(100) | Categoria extraida de la descripcion (nivel superior de jerarquia) |

**Jerarquia:** categoria_inferida -> marca -> descripcion

> **Nota de diseno:** El dataset no provee una categoria explicita. Se debe inferir durante el ETL a partir de palabras clave en la descripcion (ej: "LECHE" -> Lacteos, "FIDEOS" -> Pastas, "CERVEZA" -> Bebidas Alcoholicas). Esto es una decision de diseno clave y se detalla en la seccion 5.

---

#### dim_comercio -- JERARQUICA

| Campo | Tipo | Descripcion |
|-------|------|-------------|
| sk_comercio | INT (PK) | Clave surrogada |
| id_comercio_natural | INT | Clave natural (id_comercio) |
| id_bandera | INT | ID de la bandera comercial |
| cuit | VARCHAR(15) | CUIT de la empresa |
| razon_social | VARCHAR(200) | Razon social de la empresa |
| bandera_nombre | VARCHAR(100) | Nombre de la bandera (ej: Supermercados DIA, COTO) |
| bandera_url | VARCHAR(200) | URL de la bandera |

**Jerarquia:** razon_social (empresa) -> bandera_nombre (cadena)

> Ejemplo real: una empresa puede operar multiples banderas (ej: Libertad SA opera "Hipermercado Libertad", "Mini Libertad" y "Petit Libertad").

---

#### dim_sucursal (no jerarquica)

| Campo | Tipo | Descripcion |
|-------|------|-------------|
| sk_sucursal | INT (PK) | Clave surrogada |
| id_sucursal_natural | INT | Clave natural compuesta: id_comercio + id_bandera + id_sucursal |
| id_comercio | INT | Referencia al comercio |
| id_bandera | INT | Referencia a la bandera |
| id_sucursal | INT | ID de sucursal dentro del comercio |
| nombre | VARCHAR(100) | Nombre de la sucursal |
| calle | VARCHAR(100) | Calle de la sucursal |
| numero | VARCHAR(20) | Numero de calle |
| latitud | DECIMAL(10,6) | Latitud geografica |
| longitud | DECIMAL(10,6) | Longitud geografica |
| observaciones | VARCHAR(200) | Observaciones adicionales |

> **Nota:** Los horarios de atencion por dia de semana no se incluyen en el modelo estrella porque no son relevantes para el analisis de precios. Si se necesitaran, se podrian agregar como atributos adicionales.

---

#### dim_ubicacion -- JERARQUICA

| Campo | Tipo | Descripcion |
|-------|------|-------------|
| sk_ubicacion | INT (PK) | Clave surrogada |
| provincia_codigo | VARCHAR(5) | Codigo ISO de provincia (ej: AR-B) |
| provincia_nombre | VARCHAR(50) | Nombre legible de la provincia (ej: Buenos Aires) |
| localidad | VARCHAR(100) | Localidad |
| barrio | VARCHAR(100) | Barrio |
| codigo_postal | VARCHAR(10) | Codigo postal |

**Jerarquia:** provincia_nombre -> localidad -> barrio -> codigo_postal

> Se normaliza el codigo ISO de provincia a nombre legible durante el ETL (ej: AR-B -> Buenos Aires, AR-C -> CABA).

---

#### dim_tiempo -- JERARQUICA

| Campo | Tipo | Descripcion |
|-------|------|-------------|
| sk_tiempo | INT (PK) | Clave surrogada |
| fecha | DATE | Fecha completa |
| anio | INT | Anio |
| mes | INT | Mes (1-12) |
| dia | INT | Dia del mes |
| dia_semana | VARCHAR(15) | Nombre del dia (Lunes, Martes, etc.) |
| numero_dia_semana | INT | Numero del dia (1=Lunes, 7=Domingo) |
| semana_anio | INT | Numero de semana en el anio |

**Jerarquia:** anio -> mes -> semana_anio -> fecha

> Aunque el dataset actual cubre solo 4 dias, la dimension se disena para escalar a multiples semanas/meses de recoleccion futura.

---

#### dim_tipo_sucursal (no jerarquica)

| Campo | Tipo | Descripcion |
|-------|------|-------------|
| sk_tipo_sucursal | INT (PK) | Clave surrogada |
| tipo_sucursal | VARCHAR(50) | Tipo normalizado: Autoservicio, Supermercado, Hipermercado, Web |

> Se normaliza durante ETL: "supermercado" y "Supermercado" -> "Supermercado".

---

#### dim_unidad_medida (no jerarquica)

| Campo | Tipo | Descripcion |
|-------|------|-------------|
| sk_unidad_medida | INT (PK) | Clave surrogada |
| unidad_presentacion | VARCHAR(10) | Unidad de la presentacion normalizada (gr, kg, lt, ml, un) |
| unidad_referencia | VARCHAR(10) | Unidad de referencia normalizada |

> Se normaliza durante ETL: "GR"/"G"/"gr" -> "gr", "LT"/"L"/"lt" -> "lt", "KG"/"kg" -> "kg", "ML"/"ml"/"CC" -> "ml", "UN"/"UD"/"un" -> "un".

---

#### dim_promocion (no jerarquica)

| Campo | Tipo | Descripcion |
|-------|------|-------------|
| sk_promocion | INT (PK) | Clave surrogada |
| tiene_promo1 | BOOLEAN | Indica si tiene precio promocional 1 |
| leyenda_promo1 | VARCHAR(500) | Texto de la promocion 1 |
| tiene_promo2 | BOOLEAN | Indica si tiene precio promocional 2 |
| leyenda_promo2 | VARCHAR(500) | Texto de la promocion 2 |

> Permite filtrar rapidamente "productos con promocion" vs "sin promocion" y analizar el tipo de descuento.

---

## 3. Resumen de Medidas

| # | Medida | Tipo | Descripcion | Agregaciones tipicas |
|---|--------|------|-------------|---------------------|
| 1 | **precio_lista** | DECIMAL(12,2) | Precio de venta al publico informado | AVG, MIN, MAX, COUNT |
| 2 | **precio_referencia** | DECIMAL(12,2) | Precio por unidad de medida estandar (permite comparar entre presentaciones distintas) | AVG, MIN, MAX |
| 3 | **precio_promo** | DECIMAL(12,2) | Precio con descuento promocional (nullable) | AVG, MIN, MAX, COUNT(NOT NULL) |

**Medidas derivadas calculables:**
- `descuento_promo = precio_lista - precio_promo` (ahorro absoluto)
- `pct_descuento = (precio_lista - precio_promo) / precio_lista * 100` (porcentaje de descuento)
- `tiene_promocion = CASE WHEN precio_promo IS NOT NULL THEN 1 ELSE 0 END`

---

## 4. Resumen de Dimensiones

| # | Dimension | Jerarquica | Niveles de jerarquia | Campos |
|---|-----------|:----------:|---------------------|--------|
| 1 | dim_producto | SI | categoria_inferida -> marca -> descripcion | 6 |
| 2 | dim_comercio | SI | razon_social -> bandera_nombre | 7 |
| 3 | dim_sucursal | NO | - | 11 |
| 4 | dim_ubicacion | SI | provincia -> localidad -> barrio -> codigo_postal | 6 |
| 5 | dim_tiempo | SI | anio -> mes -> semana -> fecha | 8 |
| 6 | dim_tipo_sucursal | NO | - | 2 |
| 7 | dim_unidad_medida | NO | - | 3 |
| 8 | dim_promocion | NO | - | 5 |

**Total: 8 dimensiones (4 jerarquicas).** Cumple con los requisitos: maximo 10 dimensiones, minimo 3 jerarquicas.

---

## 5. Mapeo de Datos (CSV origen -> Modelo Estrella)

### fact_precio

| Campo destino | CSV origen | Columna origen | Transformacion |
|---------------|-----------|----------------|----------------|
| sk_producto | productos.csv | id_producto | Lookup a dim_producto |
| sk_comercio | productos.csv | id_comercio + id_bandera | Lookup a dim_comercio |
| sk_sucursal | productos.csv | id_comercio + id_bandera + id_sucursal | Lookup a dim_sucursal |
| sk_ubicacion | sucursales.csv | provincia + localidad + barrio + codigo_postal | Lookup a dim_ubicacion (join por sucursal) |
| sk_tiempo | nombre del ZIP | Fecha extraida del nombre del directorio (ej: "2026-03-09/") | Lookup a dim_tiempo |
| sk_tipo_sucursal | sucursales.csv | sucursales_tipo | Lookup a dim_tipo_sucursal (join por sucursal) |
| sk_unidad_medida | productos.csv | unidad_medida_presentacion + unidad_medida_referencia | Lookup a dim_unidad_medida |
| sk_promocion | productos.csv | precio_unitario_promo1, leyenda_promo1, promo2 | Lookup a dim_promocion |
| precio_lista | productos.csv | productos_precio_lista | CAST a DECIMAL |
| precio_referencia | productos.csv | productos_precio_referencia | CAST a DECIMAL |
| precio_promo | productos.csv | productos_precio_unitario_promo1 | CAST a DECIMAL, NULL si vacio |
| cantidad_presentacion | productos.csv | productos_cantidad_presentacion | CAST a DECIMAL |
| cantidad_referencia | productos.csv | productos_cantidad_referencia | CAST a DECIMAL |

### dim_producto

| Campo destino | CSV origen | Columna origen | Transformacion |
|---------------|-----------|----------------|----------------|
| id_producto_natural | productos.csv | id_producto | Directo |
| ean | productos.csv | productos_ean | Directo |
| descripcion | productos.csv | productos_descripcion | TRIM |
| marca | productos.csv | productos_marca | TRIM, UPPER |
| categoria_inferida | productos.csv | productos_descripcion | Reglas de clasificacion por palabras clave |

### dim_comercio

| Campo destino | CSV origen | Columna origen | Transformacion |
|---------------|-----------|----------------|----------------|
| id_comercio_natural | comercio.csv | id_comercio | Directo |
| id_bandera | comercio.csv | id_bandera | Directo |
| cuit | comercio.csv | comercio_cuit | Directo |
| razon_social | comercio.csv | comercio_razon_social | TRIM |
| bandera_nombre | comercio.csv | comercio_bandera_nombre | TRIM |
| bandera_url | comercio.csv | comercio_bandera_url | TRIM |

### dim_sucursal

| Campo destino | CSV origen | Columna origen | Transformacion |
|---------------|-----------|----------------|----------------|
| id_comercio | sucursales.csv | id_comercio | Directo |
| id_bandera | sucursales.csv | id_bandera | Directo |
| id_sucursal | sucursales.csv | id_sucursal | Directo |
| nombre | sucursales.csv | sucursales_nombre | TRIM |
| calle | sucursales.csv | sucursales_calle | TRIM |
| numero | sucursales.csv | sucursales_numero | TRIM |
| latitud | sucursales.csv | sucursales_latitud | CAST a DECIMAL |
| longitud | sucursales.csv | sucursales_longitud | CAST a DECIMAL |
| observaciones | sucursales.csv | sucursales_observaciones | TRIM |

### dim_ubicacion

| Campo destino | CSV origen | Columna origen | Transformacion |
|---------------|-----------|----------------|----------------|
| provincia_codigo | sucursales.csv | sucursales_provincia | TRIM |
| provincia_nombre | sucursales.csv | sucursales_provincia | Mapeo ISO -> nombre (AR-B -> Buenos Aires, etc.) |
| localidad | sucursales.csv | sucursales_localidad | TRIM |
| barrio | sucursales.csv | sucursales_barrio | TRIM |
| codigo_postal | sucursales.csv | sucursales_codigo_postal | TRIM |

### dim_tiempo

| Campo destino | Origen | Transformacion |
|---------------|--------|----------------|
| fecha | Nombre del directorio ZIP | Parsear "2026-03-09" de la ruta del archivo |
| anio | fecha | YEAR(fecha) |
| mes | fecha | MONTH(fecha) |
| dia | fecha | DAY(fecha) |
| dia_semana | fecha | DAYNAME(fecha) |
| numero_dia_semana | fecha | DAYOFWEEK(fecha) |
| semana_anio | fecha | WEEKOFYEAR(fecha) |

### dim_tipo_sucursal

| Campo destino | CSV origen | Columna origen | Transformacion |
|---------------|-----------|----------------|----------------|
| tipo_sucursal | sucursales.csv | sucursales_tipo | TRIM, normalizacion de capitalizacion |

### dim_unidad_medida

| Campo destino | CSV origen | Columna origen | Transformacion |
|---------------|-----------|----------------|----------------|
| unidad_presentacion | productos.csv | productos_unidad_medida_presentacion | LOWER, mapeo de sinonimos |
| unidad_referencia | productos.csv | productos_unidad_medida_referencia | LOWER, mapeo de sinonimos |

### dim_promocion

| Campo destino | CSV origen | Columna origen | Transformacion |
|---------------|-----------|----------------|----------------|
| tiene_promo1 | productos.csv | productos_precio_unitario_promo1 | TRUE si no vacio, FALSE si vacio |
| leyenda_promo1 | productos.csv | productos_leyenda_promo1 | TRIM |
| tiene_promo2 | productos.csv | productos_precio_unitario_promo2 | TRUE si no vacio, FALSE si vacio |
| leyenda_promo2 | productos.csv | productos_leyenda_promo2 | TRIM |

---

## 6. Decisiones de Diseno

### D1 - Claves surrogadas en todas las dimensiones
Se utilizan claves surrogadas (INT autoincremental) en lugar de claves naturales. Las claves naturales del dataset (id_comercio, id_sucursal, id_producto) se conservan como atributos para trazabilidad, pero las FK en la tabla de hechos apuntan a surrogadas. Esto permite independencia del sistema fuente y facilita el manejo de cambios historicos (SCD).

### D2 - Categoria de producto inferida
El dataset no incluye una categoria explicita de producto. Se decide inferirla a partir de palabras clave en `productos_descripcion` durante el ETL, aplicando reglas como:
- Contiene "LECHE", "YOGUR", "QUESO" -> "Lacteos"
- Contiene "CERVEZA", "VINO", "WHISKY" -> "Bebidas Alcoholicas"
- Contiene "FIDEOS", "ARROZ", "HARINA" -> "Almacen"
- Etc.

Esto es imperfecto pero necesario para habilitar drill-down por categoria, que es central al analisis propuesto. Se puede refinar iterativamente.

### D3 - Separacion de dim_ubicacion y dim_sucursal
Se separa la ubicacion geografica de la sucursal en dos dimensiones para evitar redundancia y permitir analisis geograficos independientes. Muchas sucursales distintas comparten la misma ubicacion (provincia + localidad + barrio). Esto es especialmente util para el drill-down geografico: provincia -> localidad -> barrio.

### D4 - Normalizacion de unidades de medida
El dataset presenta inconsistencias en las unidades (GR/G/gr, LT/L/lt, UN/UD/un, CC/ML/ml). Se normalizan a minusculas y se unifican sinonimos: G/GR/gr -> "gr", L/LT/lt -> "lt", CC/ML/ml -> "ml", UN/UD/un -> "un". Esto es critico para que las comparaciones de precio_referencia sean validas.

### D5 - Normalizacion de codigos de provincia
El dataset usa codigos ISO 3166-2 (AR-B, AR-C, etc.) con alguna inconsistencia ("Buenos Aires" en texto libre). Se normalizan todos a codigo ISO y se agrega un atributo con el nombre legible de la provincia.

### D6 - precio_promo como medida nullable
Se usa un unico campo precio_promo que toma el valor de `productos_precio_unitario_promo1` (la promo principal). Se decide no incluir promo2 como medida separada porque en los datos observados promo2 esta practicamente siempre vacia. La informacion de promo2 se preserva en dim_promocion para consulta, pero no como medida en la fact table.

### D7 - Granularidad: producto x sucursal x dia
Cada registro de la fact table representa un producto en una sucursal en un dia especifico. Esta es la maxima granularidad posible con los datos disponibles y permite cualquier tipo de roll-up posterior.

### D8 - Horarios de atencion excluidos del modelo
Los 7 campos de horarios de atencion (lunes a domingo) de sucursales.csv no se incluyen en el modelo porque no aportan al analisis de precios y aumentarian la complejidad sin beneficio analitico.

### D9 - Tecnologia: SQLite
Se elige SQLite como RDBMS. El modelo estrella se implementa en un unico archivo `.db` con foreign keys explicitas (activadas via `PRAGMA foreign_keys = ON`). No requiere instalar servidor; Power BI se conecta al archivo via ODBC.

---

## 7. Flujo ETL Resumido

```
ETAPA 1: EXTRACCION
   |
   |-- Para cada ZIP diario (sepa_lunes.zip ... sepa_jueves.zip):
   |     |-- Extraer fecha del nombre de directorio interno (ej: "2026-03-09/")
   |     |-- Para cada sub-ZIP de comercio:
   |           |-- Leer comercio.csv (separador pipe)
   |           |-- Leer sucursales.csv (separador pipe)
   |           |-- Leer productos.csv (separador pipe)
   |
ETAPA 2: TRANSFORMACION
   |
   |-- 2.1 Limpieza general:
   |     |-- TRIM de todos los campos de texto
   |     |-- Eliminar filas vacias o malformadas
   |     |-- Castear tipos numericos (precios, coordenadas, cantidades)
   |
   |-- 2.2 Normalizaciones:
   |     |-- Unidades de medida: unificar sinonimos a minusculas
   |     |-- Tipo de sucursal: normalizar capitalizacion
   |     |-- Provincia: mapear codigos ISO a nombres legibles
   |     |-- Marca: UPPER y TRIM para consistencia
   |
   |-- 2.3 Enriquecimiento:
   |     |-- Inferir categoria de producto a partir de descripcion
   |     |-- Calcular flags de promocion (tiene_promo1, tiene_promo2)
   |     |-- Generar dimension de tiempo a partir de las fechas extraidas
   |
   |-- 2.4 Deduplicacion:
   |     |-- Generar clave natural unica por dimension
   |     |-- Insertar solo valores nuevos (lookup existente antes de INSERT)
   |
ETAPA 3: CARGA
   |
   |-- 3.1 Cargar dimensiones (orden no importa, son independientes):
   |     |-- INSERT INTO dim_producto (dedup por id_producto + ean)
   |     |-- INSERT INTO dim_comercio (dedup por id_comercio + id_bandera)
   |     |-- INSERT INTO dim_sucursal (dedup por id_comercio + id_bandera + id_sucursal)
   |     |-- INSERT INTO dim_ubicacion (dedup por provincia + localidad + barrio + cp)
   |     |-- INSERT INTO dim_tiempo (generar para rango de fechas)
   |     |-- INSERT INTO dim_tipo_sucursal (dedup por tipo normalizado)
   |     |-- INSERT INTO dim_unidad_medida (dedup por par de unidades)
   |     |-- INSERT INTO dim_promocion (dedup por combinacion de flags y leyendas)
   |
   |-- 3.2 Cargar tabla de hechos:
   |     |-- Para cada fila de productos.csv:
   |           |-- Resolver FK haciendo lookup a cada dimension
   |           |-- INSERT INTO fact_precio
   |
   |-- 3.3 Validacion post-carga:
         |-- Verificar conteo de registros vs fuente
         |-- Verificar integridad referencial
         |-- Verificar que no haya precios negativos o nulos inesperados
```

**Herramienta ETL sugerida:** Script Python con pandas para extraccion y transformacion, y sqlite3 (stdlib de Python) para la carga al archivo SQLite.

---

## 8. Diagrama del Modelo Estrella (esquematico)

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
                    | numero_dia_semana |        | tipo_sucursal       |
                    | semana_anio       |        +----------+----------+
                    +--------+----------+                   |
                             |                              |
                             |                              |
+------------------+         |    +------------------------+|   +-------------------+
|  dim_producto    |         |    |     fact_precio        ||   |  dim_unidad_medida|
|------------------|         |    |------------------------|+   |-------------------|
| sk_producto (PK) +---------+----+ sk_producto (FK)       |    | sk_unidad (PK)    |
| id_producto_nat  |         |    | sk_comercio (FK)       +----+ unidad_present    |
| ean              |         +----+ sk_sucursal (FK)       |    | unidad_referencia |
| descripcion      |              | sk_ubicacion (FK)      |    +-------------------+
| marca            |         +----+ sk_tiempo (FK)         |
| categoria_infer  |         |    | sk_tipo_sucursal (FK)  |    +-------------------+
+------------------+         |    | sk_unidad_medida (FK)  |    |  dim_promocion    |
                             |    | sk_promocion (FK)      +----+-------------------|
+------------------+         |    |------------------------|    | sk_promocion (PK) |
|  dim_comercio    |         |    | precio_lista      [M1] |    | tiene_promo1      |
|------------------|         |    | precio_referencia [M2] |    | leyenda_promo1    |
| sk_comercio (PK) +---------+    | precio_promo      [M3] |    | tiene_promo2      |
| id_comercio_nat  |              | cantidad_present       |    | leyenda_promo2    |
| id_bandera       |              | cantidad_referencia    |    +-------------------+
| cuit             |              +-----+------------------+
| razon_social     |                    |
| bandera_nombre   |                    |
| bandera_url      |         +----------+---------+
+------------------+         |                    |
                      +------+--------+   +-------+-----------+
                      | dim_sucursal  |   |  dim_ubicacion    |
                      |---------------|   |-------------------|
                      | sk_suc (PK)   |   | sk_ubic (PK)      |
                      | id_comercio   |   | provincia_codigo  |
                      | id_bandera    |   | provincia_nombre  |
                      | id_sucursal   |   | localidad         |
                      | nombre        |   | barrio            |
                      | calle         |   | codigo_postal     |
                      | numero        |   +-------------------+
                      | latitud       |
                      | longitud      |
                      | observaciones |
                      +---------------+
```

---

## 9. Consultas Analiticas que Habilita este Modelo

1. **Precio promedio por provincia:** Agrupar fact_precio por dim_ubicacion.provincia_nombre, calcular AVG(precio_lista).
2. **Cadena mas barata para un producto:** Filtrar por dim_producto, agrupar por dim_comercio.bandera_nombre, calcular MIN(precio_lista).
3. **Porcentaje de productos en promocion por cadena:** COUNT(precio_promo IS NOT NULL) / COUNT(*) agrupado por dim_comercio.bandera_nombre.
4. **Variacion de precios por tipo de sucursal:** AVG(precio_lista) agrupado por dim_tipo_sucursal.tipo_sucursal.
5. **Drill-down geografico:** Provincia -> Localidad -> Barrio con AVG(precio_referencia).
6. **Evolucion diaria de precios:** dim_tiempo.fecha como eje temporal, AVG(precio_lista) como medida.
7. **Top marcas mas caras/baratas por categoria:** dim_producto.categoria_inferida + dim_producto.marca con AVG(precio_referencia).

---

## 10. Volumetria Estimada

| Elemento | Estimacion |
|----------|-----------|
| Registros por dia (aprox.) | ~7-8 millones (sumando todos los comercios) |
| Registros totales (4 dias) | ~28-32 millones |
| Comercios distintos | ~17-19 |
| Banderas distintas | ~27 |
| Sucursales distintas | ~3,000-5,000 (estimado) |
| Productos distintos | ~50,000-100,000 (estimado) |
| Provincias | 24 |

> La tabla de hechos sera la mas voluminosa. Se recomienda indexar las FK y considerar particionamiento por fecha si el volumen crece.

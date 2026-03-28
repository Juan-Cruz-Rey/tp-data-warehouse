# Plan Maestro - Modelo Estrella Data Warehouse SEPA Precios

## 1. Contexto del Negocio

**Organizacion:** Consultora ficticia de analisis comercial y precios.
**Dataset:** SEPA Precios - Sistema Electronico de Publicidad de Precios Argentino.
**Fuente:** Secretaria de Comercio de Argentina (Ministerio de Produccion).
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
| id_hecho | INT (PK, AUTOINCREMENT) | Clave primaria del hecho |
| sk_producto | INT (FK) | Clave surrogada a dim_producto |
| sk_comercio | INT (FK) | Clave surrogada a dim_comercio |
| sk_sucursal | INT (FK) | Clave surrogada a dim_sucursal |
| sk_ubicacion | INT (FK) | Clave surrogada a dim_ubicacion |
| sk_tiempo | INT (FK) | Clave surrogada a dim_tiempo |
| **precio_lista** | DECIMAL(12,2) | **MEDIDA 1** - Precio de lista del producto |
| **precio_referencia** | DECIMAL(12,2) | **MEDIDA 2** - Precio de referencia (por unidad de medida estandar) |
| **precio_promo** | DECIMAL(12,2) | **MEDIDA 3** - Precio promocional (NULL si no hay promocion) |
| tiene_promo | BOOLEAN | Indica si el producto tiene promocion activa |

**Granularidad:** Un registro por cada combinacion unica de producto x sucursal x dia de relevamiento. Cada fila representa el precio informado de un producto especifico en una sucursal especifica en un dia determinado.

---

### Dimensiones (5 dimensiones, 4 jerarquicas)

#### dim_producto -- JERARQUICA

| Campo | Tipo | Descripcion |
|-------|------|-------------|
| sk_producto | INT (PK) | Clave surrogada |
| ean | VARCHAR(20) | Codigo de barras EAN |
| descripcion | VARCHAR(200) | Descripcion completa del producto |
| marca | VARCHAR(100) | Marca del producto |
| categoria_inferida | VARCHAR(100) | Categoria extraida de la descripcion (nivel superior de jerarquia) |

**Jerarquia:** Categoria -> Marca -> Producto

> **Nota de diseno:** El dataset no provee una categoria explicita. Se debe inferir durante el ETL a partir de palabras clave en la descripcion (ej: "LECHE" -> Lacteos, "FIDEOS" -> Pastas, "CERVEZA" -> Bebidas Alcoholicas). Esto es una decision de diseno clave y se detalla en la seccion 6 (D2).

---

#### dim_comercio -- JERARQUICA

| Campo | Tipo | Descripcion |
|-------|------|-------------|
| sk_comercio | INT (PK) | Clave surrogada |
| razon_social | VARCHAR(200) | Razon social de la empresa |
| bandera_nombre | VARCHAR(100) | Nombre de la bandera (ej: Supermercados DIA, COTO) |

**Jerarquia:** Empresa -> Cadena

> Ejemplo real: una empresa puede operar multiples banderas (ej: Libertad SA opera "Hipermercado Libertad", "Mini Libertad" y "Petit Libertad").

---

#### dim_sucursal (no jerarquica)

| Campo | Tipo | Descripcion |
|-------|------|-------------|
| sk_sucursal | INT (PK) | Clave surrogada |
| nombre | VARCHAR(100) | Nombre de la sucursal |
| direccion | VARCHAR(200) | Direccion de la sucursal |
| tipo_sucursal | VARCHAR(50) | Tipo de sucursal (Autoservicio, Supermercado, Hipermercado, Web) |

> **Nota:** Los horarios de atencion por dia de semana no se incluyen en el modelo estrella porque no son relevantes para el analisis de precios (ver D8).

---

#### dim_ubicacion -- JERARQUICA

| Campo | Tipo | Descripcion |
|-------|------|-------------|
| sk_ubicacion | INT (PK) | Clave surrogada |
| provincia_codigo | VARCHAR(5) | Codigo ISO de provincia (ej: AR-B) |
| provincia_nombre | VARCHAR(50) | Nombre legible de la provincia (ej: Buenos Aires) |
| localidad | VARCHAR(100) | Localidad |

**Jerarquia:** Provincia -> Localidad

> Se normaliza el codigo ISO de provincia a nombre legible durante el ETL (ej: AR-B -> Buenos Aires, AR-C -> CABA). Ver D5.

---

#### dim_tiempo -- JERARQUICA

| Campo | Tipo | Descripcion |
|-------|------|-------------|
| sk_tiempo | INT (PK) | Clave surrogada |
| fecha | DATE | Fecha completa |
| anio | INT | Anio |
| mes | INT | Mes (1-12) |
| dia | INT | Dia del mes |

**Jerarquia:** Anio -> Mes -> Dia

> Aunque el dataset actual cubre solo 4 dias, la dimension se disena para escalar a multiples semanas/meses de recoleccion futura.

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

---

## 4. Resumen de Dimensiones

| Dimension | Jerarquica | Niveles de jerarquia |
|-----------|:----------:|---------------------|
| dim_producto | SI | Categoria -> Marca -> Producto |
| dim_comercio | SI | Empresa -> Cadena |
| dim_ubicacion | SI | Provincia -> Localidad |
| dim_tiempo | SI | Anio -> Mes -> Dia |
| dim_sucursal | NO | - |

**Total: 5 dimensiones (4 jerarquicas).** Cumple con los requisitos: maximo 10 dimensiones, minimo 3 jerarquicas.

---

## 5. Mapeo de Datos (CSV origen -> Modelo Estrella)

### fact_precio

| Campo destino | Archivo origen | Columna origen | Transformacion |
|---------------|---------------|----------------|----------------|
| sk_producto | productos.csv | id_producto | Lookup a dim_producto |
| sk_comercio | productos.csv | id_comercio + id_bandera | Lookup a dim_comercio |
| sk_sucursal | productos.csv | id_sucursal | Lookup a dim_sucursal |
| sk_ubicacion | sucursales.csv | provincia + localidad | Lookup a dim_ubicacion |
| sk_tiempo | Nombre archivo | fecha | Parseo de la fecha del nombre del directorio |
| precio_lista | productos.csv | productos_precio_lista | CAST a DECIMAL |
| precio_referencia | productos.csv | productos_precio_referencia | CAST a DECIMAL |
| precio_promo | productos.csv | productos_precio_unitario_promo1 | CAST a DECIMAL, NULL si vacio |
| tiene_promo | productos.csv | precio_promo | CASE WHEN NOT NULL |

### dim_producto

| Campo destino | CSV origen | Columna origen | Transformacion |
|---------------|-----------|----------------|----------------|
| ean | productos.csv | productos_ean | Directo |
| descripcion | productos.csv | productos_descripcion | TRIM |
| marca | productos.csv | productos_marca | TRIM, UPPER |
| categoria_inferida | productos.csv | productos_descripcion | Reglas de clasificacion por palabras clave |

### dim_comercio

| Campo destino | CSV origen | Columna origen | Transformacion |
|---------------|-----------|----------------|----------------|
| razon_social | comercio.csv | comercio_razon_social | TRIM |
| bandera_nombre | comercio.csv | comercio_bandera_nombre | TRIM |

### dim_sucursal

| Campo destino | CSV origen | Columna origen | Transformacion |
|---------------|-----------|----------------|----------------|
| nombre | sucursales.csv | sucursales_nombre | TRIM |
| direccion | sucursales.csv | sucursales_calle + sucursales_numero | Concatenacion, TRIM |
| tipo_sucursal | sucursales.csv | sucursales_tipo | TRIM, normalizacion de capitalizacion |

### dim_ubicacion

| Campo destino | CSV origen | Columna origen | Transformacion |
|---------------|-----------|----------------|----------------|
| provincia_codigo | sucursales.csv | sucursales_provincia | TRIM (conservar codigo ISO original, ej: AR-B) |
| provincia_nombre | sucursales.csv | sucursales_provincia | Mapeo ISO -> nombre (AR-B -> Buenos Aires, etc.) |
| localidad | sucursales.csv | sucursales_localidad | TRIM |

### dim_tiempo

| Campo destino | Origen | Transformacion |
|---------------|--------|----------------|
| fecha | Nombre del directorio ZIP | Parsear "2026-03-09" de la ruta del archivo |
| anio | fecha | YEAR(fecha) |
| mes | fecha | MONTH(fecha) |
| dia | fecha | DAY(fecha) |

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
Se separa la ubicacion geografica de la sucursal en dos dimensiones para evitar redundancia y permitir analisis geograficos independientes. Muchas sucursales distintas comparten la misma ubicacion (provincia + localidad). Esto es especialmente util para el drill-down geografico: Provincia -> Localidad.

### D4 - Normalizacion de unidades de medida
El dataset presenta inconsistencias en las unidades (GR/G/gr, LT/L/lt, UN/UD/un, CC/ML/ml). Se normalizan a minusculas y se unifican sinonimos: G/GR/gr -> "gr", L/LT/lt -> "lt", CC/ML/ml -> "ml", UN/UD/un -> "un". Esto es critico para que las comparaciones de precio_referencia sean validas.

### D5 - Normalizacion de codigos de provincia (ISO -> nombre)
El dataset usa codigos ISO 3166-2 (AR-B, AR-C, etc.) con alguna inconsistencia ("Buenos Aires" en texto libre). Se normalizan todos a nombre legible de la provincia.

### D6 - precio_promo como medida nullable
Se usa un unico campo precio_promo que toma el valor de `productos_precio_unitario_promo1` (la promo principal). Cuando no hay promocion, el campo queda NULL. El flag `tiene_promo` en la fact table permite filtrar rapidamente productos con o sin promocion.

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
   |     |-- Calcular flag tiene_promo (NOT NULL sobre precio_promo)
   |     |-- Generar dimension de tiempo a partir de las fechas extraidas
   |
   |-- 2.4 Deduplicacion:
   |     |-- Generar clave natural unica por dimension
   |     |-- Insertar solo valores nuevos (lookup existente antes de INSERT)
   |
ETAPA 3: CARGA
   |
   |-- 3.1 Cargar dimensiones (orden no importa, son independientes):
   |     |-- INSERT INTO dim_producto (dedup por ean)
   |     |-- INSERT INTO dim_comercio (dedup por razon_social + bandera_nombre)
   |     |-- INSERT INTO dim_sucursal (dedup por nombre + direccion)
   |     |-- INSERT INTO dim_ubicacion (dedup por provincia + localidad)
   |     |-- INSERT INTO dim_tiempo (generar para rango de fechas)
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

**Herramienta ETL:** Script Python con pandas para extraccion y transformacion, y sqlite3 (stdlib de Python) para la carga al archivo SQLite.

---

## 8. Diagrama del Modelo Estrella

```
                    +------------------+
                    |   dim_tiempo     |
                    |------------------|
                    | sk_tiempo (PK)   |
                    | fecha            |
                    | anio             |
                    | mes              |
                    | dia              |
                    +--------+---------+
                             |
                             |
+------------------+         |    +-------------------------+
|  dim_producto    |         |    |      fact_precio        |
|------------------|         |    |-------------------------|
| sk_producto (PK) +----+    |    | id_hecho (PK, AUTO)     |
| ean              |    |    +----+ sk_tiempo (FK)           |
| descripcion      |    +--------+ sk_producto (FK)          |
| marca            |         +---+ sk_comercio (FK)          |
| categoria_infer  |         |   | sk_sucursal (FK)          |
+------------------+         |   | sk_ubicacion (FK)         |
                             |   |-------------------------|
+------------------+         |   | precio_lista       [M1] |
|  dim_comercio    |         |   | precio_referencia  [M2] |
|------------------|         |   | precio_promo       [M3] |
| sk_comercio (PK) +---------+   | tiene_promo             |
| razon_social     |              +-----+-------------------+
| bandera_nombre   |                    |
+------------------+                    |
                          +-------------+-------------+
                          |                           |
                   +------+--------+          +-------+-----------+
                   | dim_sucursal  |          |  dim_ubicacion    |
                   |---------------|          |-------------------|
                   | sk_suc (PK)   |          | sk_ubic (PK)      |
                   | nombre        |          | provincia_codigo  |
                   | direccion     |          | provincia_nombre  |
                   | tipo_sucursal |          | localidad         |
                   +---------------+          +-------------------+
```

---

## 9. Consultas Analiticas que Habilita este Modelo

1. **Precio promedio por provincia:** Agrupar fact_precio por dim_ubicacion.provincia_nombre, calcular AVG(precio_lista).
2. **Cadena mas barata para un producto:** Filtrar por dim_producto, agrupar por dim_comercio.bandera_nombre, calcular MIN(precio_lista).
3. **Porcentaje de productos en promocion por cadena:** COUNT(tiene_promo = 1) / COUNT(*) agrupado por dim_comercio.bandera_nombre.
4. **Variacion de precios por tipo de sucursal:** AVG(precio_lista) agrupado por dim_sucursal.tipo_sucursal.
5. **Drill-down geografico:** Provincia -> Localidad con AVG(precio_referencia).
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

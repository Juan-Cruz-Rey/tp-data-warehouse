# Analisis de precios minoristas en supermercados argentinos para detectar variaciones por region, categoria de producto y cadena comercial

**Materia:** Analisis de la informacion y la decision - 2026

**Equipo:**

| Integrante | DNI |
|------------|-----|
| Carlota Paiva | 62834095 |
| Manuel Krivoy | 43840924 |
| Juan Cruz Rey | 36921336 |
| Franco Tisano | 41265908 |

---

## Indice

1. [Descripcion de la organizacion y contexto del negocio](#1-descripcion-de-la-organizacion-y-contexto-del-negocio)
2. [Descripcion de la necesidad o problema a resolver](#2-descripcion-de-la-necesidad-o-problema-a-resolver)
3. [Modelos de datos existentes (OLTP)](#3-modelos-de-datos-existentes-oltp)
4. [Modelo Multidimensional (Diagrama Estrella)](#4-modelo-multidimensional-diagrama-estrella)
5. [Mapeo de datos](#5-mapeo-de-datos)
6. [Decisiones de diseno](#6-decisiones-de-diseno)
7. [Consultas que habilita este modelo](#7-consultas-que-habilita-este-modelo)
8. [Propuesta de OLAP](#8-propuesta-de-olap)

---

## 1. Descripcion de la organizacion y contexto del negocio

### Organizacion

La organizacion es una **consultora ficticia de analisis comercial y precios**, orientada a brindar informacion para la toma de decisiones a empresas del sector retail, consumo masivo, fabricantes y organismos de analisis economico.

### Fuente de datos

Se trabaja con datos del **SEPA (Sistema Electronico de Publicidad de Precios Argentinos)**, perteneciente a la **Subsecretaria de Defensa del Consumidor y Lealtad Comercial**.

- **Dataset:** Precios Claros - Base SEPA.
- **Fuente:** Datos abiertos del Estado argentino.
- **Volumen:** Mas de 70.000 productos y aproximadamente 12 millones de registros diarios.

### Archivos principales

Tres archivos principales componen el dataset:

| Archivo | Descripcion |
|---------|-------------|
| comercio.csv | Datos maestros de la cadena comercial |
| sucursales.csv | Datos de cada punto de venta |
| productos.csv | Registros de precios por producto, sucursal y dia |

### Ejes de analisis

Producto, marca, sucursal, cadena comercial, region, tiempo.

---

## 2. Descripcion de la necesidad o problema a resolver

### Preguntas que el Data Warehouse debe responder

1. Que cadenas comerciales presentan mayores diferencias de precio para una misma categoria?
2. Como varian los precios por provincia, localidad o sucursal?
3. Que productos presentan mayor dispersion entre precio relevado y precio de referencia?
4. Que marcas muestran mayor estabilidad o mayor variacion?
5. Como evolucionan los precios a lo largo del tiempo?
6. Que categorias tienen mayor sensibilidad de precio segun la zona geografica?

### Necesidad

El Data Warehouse debe permitir:

- Integrar grandes volumenes de datos.
- Historizar informacion.
- Comparar precios entre cadenas, regiones y productos.
- Visualizar tendencias.
- Detectar desvios.
- Generar reportes.

---

## 3. Modelos de datos existentes (OLTP)

### comercio.csv

| Columna | Descripcion |
|---------|-------------|
| id_comercio | Identificador del comercio |
| id_bandera | Identificador de la bandera comercial |
| comercio_razon_social | Razon social |
| comercio_bandera_nombre | Nombre de la bandera (ej: "Supermercados DIA") |

### sucursales.csv

| Columna | Descripcion |
|---------|-------------|
| id_sucursal | Identificador de la sucursal |
| nombre | Nombre de la sucursal |
| tipo | Tipo de sucursal (Supermercado, Hipermercado, etc.) |
| localidad | Localidad / ciudad |
| provincia | Provincia |
| latitud / longitud | Coordenadas geograficas |
| horarios | Horarios de atencion |
| direccion | Direccion de la sucursal |

### productos.csv

| Columna | Descripcion |
|---------|-------------|
| id_producto | Identificador del producto |
| descripcion | Descripcion del producto |
| marca | Marca del producto |
| precio_lista | Precio de lista |
| precio_referencia | Precio por unidad de referencia |
| unidad de medida | Unidad de medida de la presentacion |
| cantidad | Cantidad de la presentacion |
| promociones | Datos de promociones |
| sucursal | FK a la sucursal |
| comercio | FK al comercio |

### Relaciones entre tablas OLTP

```
+-------------------+          +---------------------+
|  comercio.csv     |          |   sucursales.csv    |
|-------------------|          |---------------------|
| id_comercio  (PK) +----+----+ id_comercio    (FK)  |
| id_bandera   (PK) +----+----+ id_bandera     (FK)  |
| comercio_razon_   |    |    | id_sucursal    (PK)  |
|   social          |    |    | nombre               |
| comercio_bandera_ |    |    | tipo                 |
|   nombre          |    |    | provincia            |
|                   |    |    | localidad            |
+-------------------+    |    | ...                  |
                         |    +----------+-----------+
                         |               |
                         |    +----------+-----------+
                         |    |   productos.csv      |
                         |    |----------------------|
                         +----+ id_comercio    (FK)  |
                         +----+ id_bandera     (FK)  |
                              | id_sucursal    (FK)  |
                              | id_producto    (PK)  |
                              | descripcion          |
                              | marca                |
                              | precio_lista         |
                              | precio_referencia    |
                              | ...                  |
                              +----------------------+
```

### Lectura OLTP del problema

En el origen, los datos estan orientados al registro detallado de cada observacion de precio. Eso sirve para almacenar informacion, pero no para analisis complejos y comparativos.

Desde el punto de vista analitico, el modelo OLTP presenta limitaciones:

- No esta disenado para consultas multidimensionales.
- No facilita agregaciones rapidas.
- No esta optimizado para herramientas OLAP.
- Complica el analisis historico y comparativo.

---

## 4. Modelo Multidimensional (Diagrama Estrella)

### Diagrama del modelo

```
                    +-------------------+
                    |   dim_tiempo      |
                    |-------------------|
                    | sk_tiempo (PK)    |
                    | fecha             |
                    | anio              |
                    | mes               |
                    | dia               |
                    +--------+----------+
                             |
                             |
+------------------+         |    +------------------------+      +-------------------+
|  dim_producto    |         |    |     fact_precio        |      |  dim_ubicacion    |
|------------------|         |    |------------------------|      |-------------------|
| sk_producto (PK) +---------+----+ sk_producto (FK)       |      | sk_ubicacion (PK) |
| ean              |         |    | sk_comercio (FK)       +------+ provincia_codigo  |
| descripcion      |         +----+ sk_sucursal (FK)       |      | provincia_nombre  |
| marca            |              | sk_ubicacion (FK)      |      | localidad         |
| categoria_       |              |------------------------|      +-------------------+
|   inferida       |         +----+ sk_tiempo (FK)         |
+------------------+         |    |------------------------|
                             |    | precio_lista      [M1] |
+------------------+         |    | precio_referencia [M2] |
|  dim_comercio    |         |    | precio_promo      [M3] |
|------------------|         |    | tiene_promo            |
| sk_comercio (PK) +---------+    +-----+------------------+
| razon_social     |                    |
| bandera_nombre   |             +------+---------+
+------------------+             |  dim_sucursal  |
                                 |----------------|
                                 | sk_sucursal(PK)|
                                 | nombre         |
                                 | direccion      |
                                 | tipo_sucursal  |
                                 +----------------+
```

### Tabla de hechos: `fact_precio`

| Campo | Tipo | Rol | Descripcion |
|-------|------|-----|-------------|
| id_hecho | INT | PK | Clave primaria del hecho |
| sk_producto | INT | FK | Clave surrogada a dim_producto |
| sk_comercio | INT | FK | Clave surrogada a dim_comercio |
| sk_sucursal | INT | FK | Clave surrogada a dim_sucursal |
| sk_ubicacion | INT | FK | Clave surrogada a dim_ubicacion |
| sk_tiempo | INT | FK | Clave surrogada a dim_tiempo |
| precio_lista | DECIMAL(12,2) | Medida | Precio de lista del producto |
| precio_referencia | DECIMAL(12,2) | Medida | Precio por unidad estandar |
| precio_promo | DECIMAL(12,2) | Medida | Precio promocional (nullable) |
| tiene_promo | BOOLEAN | Atributo | Indica si el producto tiene promocion activa |

**Granularidad:** La unidad minima de analisis corresponde a un producto especifico por sucursal relevado en un dia determinado.

### Dimensiones (5 dimensiones, 4 jerarquicas)

| Dimension | Jerarquica | Niveles de jerarquia | Campos principales |
|-----------|:----------:|----------------------|--------------------|
| dim_producto | Si | Categoria -> Marca -> Producto | sk_producto, ean, descripcion, marca, categoria_inferida |
| dim_comercio | Si | Empresa -> Cadena | sk_comercio, razon_social, bandera_nombre |
| dim_sucursal | No | - | sk_sucursal, nombre, direccion, tipo_sucursal |
| dim_ubicacion | Si | Provincia -> Localidad | sk_ubicacion, provincia_codigo, provincia_nombre, localidad |
| dim_tiempo | Si | Anio -> Mes -> Dia | sk_tiempo, fecha, anio, mes, dia |

### Resumen de jerarquias

| Dimension | Jerarquica | Niveles |
|-----------|-----------|---------|
| dim_producto | Si | Categoria -> Marca -> Producto |
| dim_comercio | Si | Empresa -> Cadena |
| dim_ubicacion | Si | Provincia -> Localidad |
| dim_tiempo | Si | Anio -> Mes -> Dia |
| dim_sucursal | No | - |

---

## 5. Mapeo de datos

### fact_precio

| Campo Destino | Archivo Origen | Columna / Atributo | Transformacion |
|---------------|---------------|-------------------|----------------|
| sk_producto | productos.csv | id_producto | Lookup a dim_producto |
| sk_comercio | productos.csv | id_comercio + id_bandera | Lookup a dim_comercio |
| sk_sucursal | productos.csv | id_sucursal | Lookup a dim_sucursal |
| sk_ubicacion | sucursales.csv | provincia + localidad | Lookup a dim_ubicacion |
| sk_tiempo | Nombre de archivo | fecha | Parseo y conversion de fecha |
| precio_lista | productos.csv | productos_precio_lista | CAST a DECIMAL |
| precio_referencia | productos.csv | productos_precio_referencia | CAST a DECIMAL |
| precio_promo | productos.csv | productos_precio_unitario_promo1 | CAST a DECIMAL |
| tiene_promo | productos.csv | precio_promo | CASE WHEN NOT NULL > TRUE |

### Transformaciones necesarias

- Limpieza de textos (TRIM, eliminacion de caracteres especiales).
- Normalizacion de marcas (UPPER, unificacion de variantes).
- Agrupacion de categorias (inferencia por palabras clave en descripcion).
- Generacion de claves surrogadas.
- Calculo de metricas derivadas.

---

## 6. Decisiones de diseno

| # | Decision | Descripcion |
|---|----------|-------------|
| D1 | **Claves surrogadas en todas las dimensiones** | Se utilizan claves surrogadas (INT autoincremental) en lugar de claves naturales. Las claves naturales del dataset se conservan como atributos para trazabilidad, pero las FK en la tabla de hechos apuntan a surrogadas. Esto permite independencia del sistema fuente y facilita el manejo de cambios historicos. |
| D2 | **Categoria de producto inferida** | El dataset no incluye una categoria explicita de producto. Se infiere a partir de palabras clave en `productos_descripcion` durante el ETL, aplicando reglas como: contiene "LECHE", "YOGUR", "QUESO" -> "Lacteos"; contiene "CERVEZA", "VINO", "WHISKY" -> "Bebidas Alcoholicas"; contiene "FIDEOS", "ARROZ", "HARINA" -> "Almacen"; etc. Es imperfecto pero necesario para habilitar drill-down por categoria, que es central al analisis propuesto. Se puede refinar iterativamente. |
| D3 | **Separacion de dim_ubicacion y dim_sucursal** | Se separa la ubicacion geografica de la sucursal en dos dimensiones para evitar redundancia y permitir analisis geograficos independientes. Muchas sucursales comparten la misma combinacion provincia + localidad. |
| D4 | **Normalizacion de unidades de medida** | El dataset presenta inconsistencias (GR/G/gr, LT/L/lt, UN/UD/un, CC/ML/ml). Se normalizan a minusculas y se unifican sinonimos para que las comparaciones de precio_referencia sean validas. |
| D5 | **Normalizacion de codigos de provincia** | El dataset usa codigos ISO 3166-2 (AR-B, AR-C). Se normalizan a nombre legible de provincia (ej: "Buenos Aires", "Ciudad Autonoma de Buenos Aires"). |
| D6 | **precio_promo como medida nullable** | Se usa un unico campo `precio_promo` que toma el valor de `productos_precio_unitario_promo1` (la promo principal). Se decide no incluir promo2 como medida separada porque en los datos observados promo2 esta practicamente siempre vacia. El flag `tiene_promo` indica si existe promocion activa. |
| D7 | **Granularidad: producto x sucursal x dia** | Cada registro de la tabla de hechos representa un producto en una sucursal en un dia especifico. Esta es la maxima granularidad posible con los datos y permite cualquier tipo de roll-up posterior. |
| D8 | **Horarios de atencion excluidos del modelo** | Los campos de horarios de atencion por dia de semana no se incluyen en el modelo porque no aportan al analisis de precios y aumentarian la complejidad sin beneficio analitico. |
| D9 | **Tecnologia: SQLite** | Se elige SQLite como motor de base de datos. El modelo estrella se implementa en un unico archivo `.db`. No requiere instalar ni administrar un servidor de base de datos. Power BI se conecta al archivo via ODBC. |

---

## 7. Consultas que habilita este modelo

1. **Precio promedio por provincia:** Agrupar fact_precio por dim_ubicacion.provincia_nombre, calcular AVG(precio_lista).

2. **Cadena mas barata para un producto:** Filtrar por dim_producto, agrupar por dim_comercio.bandera_nombre, calcular MIN(precio_lista).

3. **Porcentaje de productos en promocion por cadena:** COUNT(precio_promo IS NOT NULL) / COUNT(*) agrupado por dim_comercio.bandera_nombre.

4. **Variacion de precios por tipo de sucursal:** AVG(precio_lista) agrupado por dim_sucursal.tipo_sucursal.

5. **Drill-down geografico:** Provincia -> Localidad con AVG(precio_referencia).

6. **Evolucion diaria de precios:** dim_tiempo.fecha como eje temporal, AVG(precio_lista) como medida.

7. **Top marcas mas caras/baratas por categoria:** dim_producto.categoria_inferida + dim_producto.marca con AVG(precio_referencia).

---

## 8. Propuesta de OLAP

### Herramienta: Power BI Desktop

Se propone la creacion de un dashboard interactivo en Power BI con 4 paginas, conectado al Data Warehouse SQLite via ODBC.

### Pagina 1: Resumen ejecutivo

- **KPIs principales:** precio promedio general, cantidad de productos relevados, cantidad de cadenas y sucursales.
- **Grafico de torta:** distribucion de productos por categoria inferida.
- **Grafico de linea temporal:** evolucion del precio promedio a lo largo del tiempo.
- **Ranking de cadenas:** tabla o grafico de barras con las cadenas ordenadas por precio promedio.

### Pagina 2: Analisis geografico

- **Mapa coropletico:** mapa de Argentina coloreado por precio promedio por provincia, utilizando codigos ISO 3166-2 para el mapeo geografico.
- **Filtros interactivos:** por categoria de producto, cadena comercial y periodo de tiempo.
- **Tabla detalle:** precios por provincia y localidad con drill-down.

### Pagina 3: Comparativa de cadenas

- **Grafico scatter (dispersion):** precio de lista vs. precio de referencia por cadena comercial, permitiendo identificar cadenas con mayor margen o mayor competitividad.
- **Filtros:** por categoria, provincia y periodo.
- **Tabla comparativa:** cadenas con precio promedio, minimo y maximo por categoria seleccionada.

### Pagina 4: Productos y categorias

- **Treemap:** visualizacion jerarquica con drill-down Categoria -> Marca -> Producto.
- **Analisis de dispersion:** productos con mayor diferencia entre precio de lista y precio de referencia.
- **Ranking:** marcas mas caras y mas baratas por categoria seleccionada.

# Explicación del ETL — Proyecto Data Warehouse SEPA Precios

El pipeline transforma los datos públicos de **SEPA Precios** (precios de ~5.000 sucursales de supermercados argentinos) en un **Data Warehouse con modelo estrella** listo para ser explotado por herramientas OLAP/BI. Está dividido en **4 etapas secuenciales** orquestadas por scripts independientes, lo que permite re‑ejecutar cada etapa sin repetir las anteriores.

---

## Etapa 1 — Descarga de datos (`00_descargar_datos.py`)

**Qué hace:** baja desde una carpeta pública de Google Drive todos los ZIPs diarios del relevamiento SEPA y los guarda en `data/raw/`. Cada ZIP representa **un día completo** de precios y contiene a su vez sub‑ZIPs, uno por cadena comercial.

**Decisiones de diseño:**

- **Google Drive como fuente mirror en lugar del portal oficial.** El portal SEPA tiene descargas inestables y rate‑limiting agresivo; espejar los ZIPs en Drive nos da reproducibilidad del experimento: cualquier integrante del grupo corre el mismo script y obtiene exactamente los mismos 7 días.
- **`gdown` con `remaining_ok=True`.** Permite reintentos parciales: si la descarga se corta, re‑ejecutar el script completa solo lo faltante, sin bajar de nuevo lo que ya está en `data/raw/`.
- **Separación del paso de descarga.** Descargar es la operación más lenta y la que depende de red externa. Aislarlo en su propio script evita tener que volver a bajar ~GB de ZIPs cada vez que se itera sobre la limpieza o la carga.

---

## Etapa 2 — Extracción y limpieza (`01_extraer_y_limpiar.py`)

**Qué hace:** abre cada ZIP principal, descomprime los sub‑ZIPs internos en memoria, parsea los tres CSVs de cada cadena (`comercio.csv`, `sucursales.csv`, `productos.csv`), los limpia y los consolida en tres archivos únicos dentro de `data/processed/`.

**Problemas reales del dataset crudo que el script resuelve:**

1. **Null bytes (`\x00`) y BOM UTF‑8** incrustados en los CSVs, que rompen a `pandas.read_csv`. Se limpian decodificando con `utf-8-sig` y removiendo los null bytes antes de parsear.
2. **Filas de metadata al final** (*"Última actualización..."*) que no son datos reales. Se filtran con regex antes del parseo.
3. **Versiones duplicadas `sepa_1` y `sepa_2`** del mismo comercio en el mismo día. **Decisión:** si un comercio aparece en ambas versiones, conservamos solo `sepa_2` (la más reciente); si aparece en una sola, la mantenemos. Así garantizamos una única foto por comercio‑día.
4. **Filas corruptas en `sucursales.csv`** con campos corridos del origen. Se detectan validando que `id_comercio` sea numérico y se descartan.
5. **Volumen que no cabe en RAM.** Los productos suman ~53 millones de filas; cargarlos todos juntos con `pd.concat` satura la memoria. **Decisión:** procesar **día por día** y hacer *append* incremental al CSV consolidado (`productos.csv.tmp`), liberando memoria con `gc.collect()` entre iteraciones. Solo comercios y sucursales — que son dimensionales y chicos — se consolidan al final en memoria.
6. **Bloqueos de OneDrive al escribir.** La carpeta del proyecto está sincronizada con OneDrive, que a veces mantiene el archivo abierto. Se implementó `guardar_csv_seguro` con **escritura a archivo temporal + rename atómico + reintentos**, evitando corrupción si OneDrive interfiere.
7. **Deduplicación de maestros.** Comercios y sucursales son datos maestros estables: se les quita la columna `fecha_relevamiento` y se deduplican por clave natural (`id_comercio + id_bandera`, y `id_comercio + id_bandera + id_sucursal` respectivamente).

El resultado de esta etapa son **tres CSVs limpios y consolidados** que representan el estado del universo SEPA para la ventana analizada.

---

## Etapa 3 — Creación del schema estrella (`sql/02_crear_schema.sql`)

**Qué hace:** crea la estructura del Data Warehouse en SQLite: **5 dimensiones + 1 tabla de hechos**, con sus claves surrogadas, restricciones de unicidad, foreign keys e índices analíticos.

**Modelo dimensional:**

- `dim_tiempo` — jerárquica: **año → mes → día**
- `dim_producto` — jerárquica: **categoría inferida → marca → producto**
- `dim_comercio` — jerárquica: **razón social (empresa) → bandera (cadena)**
- `dim_ubicacion` — jerárquica: **provincia → localidad**
- `dim_sucursal` — punto de venta físico (nombre, dirección, tipo)
- `fact_precio` — tabla de hechos con FKs a las 5 dimensiones y las **medidas**: `precio_lista`, `precio_referencia`, `precio_promo` y el flag `tiene_promo`.

**Decisiones de diseño:**

- **Claves surrogadas (`sk_*` autoincrementales)** en vez de claves naturales compuestas. Protegen la fact de cambios en los identificadores origen (por ejemplo, si SEPA recicla un `id_producto`) y mantienen los índices pequeños y rápidos.
- **`dim_ubicacion` separada de `dim_sucursal`.** Aunque toda sucursal tiene una ubicación, modelarlas aparte permite análisis geográficos independientes (precio promedio por provincia sin pasar por sucursales) y evita redundancia, ya que muchas sucursales comparten la misma ciudad.
- **Categoría inferida en `dim_producto`.** SEPA no publica un taxonomía oficial de productos. **Decisión:** inferir una categoría simple (Lácteos, Bebidas, Almacén, etc.) por reglas de palabras clave sobre la descripción. No es perfecta, pero habilita análisis agregados por tipo de producto, que era un requisito del TP (al menos una dimensión jerárquica explotable).
- **`ean` en `dim_producto` almacena `id_producto`, no la columna `productos_ean` del origen.** Decisión documentada en el código: `productos_ean` en el dataset es un flag 0/1, no el código real; el identificador verdadero es `id_producto`. Reutilizamos el nombre de columna por convención dimensional pero guardando el valor correcto.
- **Índices compuestos por `(dimensión, sk_tiempo)`** sobre la fact. Las consultas analíticas típicas en un DW de precios son "evolución de X en el tiempo" — estos índices optimizan exactamente ese patrón.
- **SQLite como DBMS.** Es *file‑based*, cero configuración, portable (el archivo `.db` va directo en la entrega de Drive) y soporta ampliamente los ~92 millones de filas que cargamos. Para el alcance del TP, una instancia Postgres/MySQL hubiera sido sobre‑ingeniería.
- **Script DDL idempotente.** Empieza con `DROP TABLE IF EXISTS` en orden inverso a las FKs, así re‑ejecutar el schema nunca falla, incluso si quedaron tablas huérfanas de versiones previas.

---

## Etapa 4 — Carga al modelo estrella (`03_cargar_datos.py`)

**Qué hace:** lee los CSVs limpios y puebla el DW respetando el orden **dimensiones → hechos**. Es la etapa más compleja porque la fact tiene ~92 millones de filas y cada una requiere **5 lookups** para traducir claves naturales a claves surrogadas.

**Orden de carga:**

1. `dim_tiempo` — generada programáticamente para el rango `2026‑03‑11` a `2026‑03‑17`.
2. `dim_comercio` — desde `comercios.csv`, deduplicada por `(id_comercio, id_bandera)`.
3. `dim_ubicacion` — combinaciones únicas de provincia + localidad, **mapeando códigos ISO** (`AR-B`) a **nombres legibles** (`Buenos Aires`) vía diccionario.
4. `dim_sucursal` — con dirección concatenada (calle + número) y tipo normalizado a *Title Case*.
5. `dim_producto` — extracción de productos únicos desde `productos.csv`, con categoría inferida.
6. `fact_precio` — traducción masiva de claves naturales a surrogadas.

**Decisiones clave de performance (la fact era el cuello de botella):**

- **Lookups vectorizados con `pandas.merge`, no fila por fila.** Un `iterrows` sobre 92 M filas demora horas. En cambio, cargamos las dimensiones en DataFrames en memoria y hacemos *merges* chunk‑a‑chunk: la traducción de cada chunk de 750.000 filas queda en segundos.
- **Procesamiento por chunks (`CHUNK_SIZE = 750.000`)** para no cargar los 10 GB de `productos.csv` de una sola vez.
- **Multiprocessing con `ProcessPoolExecutor`.** La transformación de cada chunk (merges, conversiones, manejo de NaN) se ejecuta en **workers paralelos** (`cpu_count - 2`), mientras el hilo principal se dedica a insertar en SQLite. Así bypaseamos el GIL de Python y usamos todos los cores.
- **Pre‑merges de `sucursales` y `comercios` ANTES del loop de chunks.** Como esos DataFrames son pequeños y estables, resolvemos una sola vez el mapeo `(id_comercio, id_bandera, id_sucursal) → (sk_sucursal, sk_ubicacion)` y pasamos el resultado a los workers, evitando repetir el cálculo en cada chunk.
- **Patrón productor‑consumidor con límite de `NUM_WORKERS * 2` futures pendientes.** Evita que el productor lea chunks más rápido de lo que los workers consumen, lo que llenaría la RAM con chunks encolados.
- **Solo las 3 columnas necesarias al leer `productos.csv` para `dim_producto`.** Usar `usecols=[id_producto, productos_descripcion, productos_marca]` reduce el I/O en ~85%.
- **PRAGMAs de SQLite optimizados para carga masiva:**
  - `journal_mode=WAL` + `synchronous=OFF` — sacrifica durabilidad temporal por velocidad.
  - `cache_size=-512000` (512 MB) y `mmap_size=1 GB` — mantiene índices activos en memoria.
  - `foreign_keys=OFF` durante la carga — la integridad se garantiza por construcción (las FKs resueltas por merge; filas con FK nula se filtran). Se reactivan al final.
  - **Eliminación de los índices de `fact_precio` antes de insertar y recreación al final.** Insertar 92 M filas con los 9 índices activos es órdenes de magnitud más lento que construirlos al final de una sola pasada.
- **Inserción por lotes de 100.000 filas** con `executemany`, y **commit cada 10 chunks**, amortizando el overhead de I/O de SQLite.
- **Filas con FK no resuelta se omiten, no se hace fallar la carga.** Si un producto del CSV no tiene correspondencia en `dim_producto` (caso muy excepcional tras la limpieza), simplemente se contabiliza como *skipped*. Mejor perder unas filas que abortar una carga de horas.

**Resultado final:** ~92,6 millones de registros en `fact_precio`, consultables en sub‑segundo desde Metabase u otra herramienta BI.

---

## Resumen de la secuencia

```
[data/raw/*.zip]           ← Etapa 1: descarga (gdown desde Drive)
       ↓
[data/processed/*.csv]     ← Etapa 2: extracción + limpieza + dedup
       ↓
[dw_sepa_precios.db schema]← Etapa 3: DDL del modelo estrella
       ↓
[dw_sepa_precios.db con ~92 M filas] ← Etapa 4: ETL paralelo dims→fact
```

Cada etapa es **independiente, idempotente y re‑ejecutable**, lo que permitió iterar sobre el diseño del modelo sin tener que repetir las etapas anteriores.

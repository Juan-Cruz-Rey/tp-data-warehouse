# Plan de Video - TP Data Warehouse (max 5 min)

## Requisitos del profe a cumplir en el video

1. **Todos los integrantes deben participar** (Carlota, Manuel, Juan Cruz, Franco)
2. **Camara encendida y mostrar DNI** cada uno
3. **Demo mostrando como se explota el modelo** con herramienta BI
4. **Que se vea que la base tiene los 50K+ registros** (tenemos 92.6M, sobra)

---

## Estructura propuesta (5 minutos)

| Tiempo | Quien | Que dice/muestra | Duracion |
|--------|-------|-------------------|----------|
| **0:00 - 0:30** | **Carlota** | **Intro:** Presenta el grupo (nombres + DNIs), la materia, y la consultora ficticia. "Analizamos precios de supermercados argentinos usando datos de SEPA Precios." | 30s |
| **0:30 - 1:15** | **Manuel** | **Problema y datos:** Explica la necesidad (datos masivos dispersos, no preparados para analisis). Menciona el dataset: SEPA Precios, 7 dias, ~92.6M registros, 37 cadenas comerciales, ~5000 sucursales. Muestra brevemente el modelo OLTP (los 3 CSVs fuente). | 45s |
| **1:15 - 2:00** | **Juan Cruz** | **Modelo estrella:** Muestra el diagrama estrella (del PPT/docs). Explica: 5 dimensiones (producto, comercio, sucursal, ubicacion, tiempo), 3 medidas (precio_lista, precio_referencia, precio_promo). Menciona 2-3 decisiones de diseno clave (D1: surrogadas, D2: categoria inferida, D9: SQLite). | 45s |
| **2:00 - 2:30** | **Franco** | **ETL:** Muestra rapidamente el pipeline: descarga Google Drive -> extraccion/limpieza (dedup, normalizacion) -> carga paralela a SQLite. Puede mostrar la terminal corriendo o un screenshot del script. Menciona los 92.6M de registros cargados. | 30s |
| **2:30 - 4:45** | **Todos (rotando)** | **Demo en Metabase (OLAP):** Esta es la parte central. Mostrar pantalla compartida con Metabase conectado a `dw_sepa_precios.db`. Rotar entre integrantes para las consultas: | 2m 15s |
| | Carlota | - KPIs generales: cantidad de registros, productos, cadenas | |
| | Manuel | - Precio promedio por provincia (analisis geografico) | |
| | Juan Cruz | - Comparativa entre cadenas: cual es mas barata para una categoria? | |
| | Franco | - % de productos en promocion por cadena + evolucion temporal | |
| **4:45 - 5:00** | **Carlota** | **Cierre:** Conclusiones breves y cierre. | 15s |

---

## Tips para el video

1. **Preparen Metabase con las consultas/dashboards ya armados** antes de grabar. No pierdan tiempo escribiendo queries en vivo.

2. **Para mostrar los 50K+ registros:** Hagan un `SELECT COUNT(*) FROM fact_precio` en Metabase, va a mostrar 92,605,473. Eso es contundente.

3. **El DNI:** Cada uno lo muestra brevemente a camara al presentarse en la intro. No hace falta detenerse mucho.

4. **Grabacion:** Pueden usar Google Meet, Zoom o Teams (grabar la reunion). Uno comparte pantalla para la demo y van rotando quien habla.

5. **No lean un guion:** El profe quiere ver que entienden lo que hicieron. Hablen natural, cada uno sobre la parte que trabajo.

6. **Prioricen la demo (2:15 min):** Es mas de la mitad del tiempo util. El profe quiere ver el modelo "explotado" con la herramienta BI, no tanto la teoria.

---

## Sobre lo que dijo el profe

- La sesion de consultas y la exposicion en vivo son **opcionales** (para el concurso Santander Rio/LinkedIn challenge).
- Lo **obligatorio** es el video + entrega por Google Drive (PPT, video, .db/pbix, dataset).
- **Solo un integrante sube** la entrega. Si lo suben varios se arriesgan a anulacion.

---

## Entregables para el Google Drive

1. PPT con la presentacion (puntos 1-7 del TP)
2. Video (max 5 min)
3. Base de datos (`dw_sepa_precios.db` o exportacion)
4. Proyecto Metabase o dashboards exportados
5. Dataset (o link a la fuente SEPA)

> No ZIP/RAR: todo suelto en la carpeta de Drive con acceso libre.

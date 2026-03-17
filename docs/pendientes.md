# Pendientes / Preguntas al profe

## Sobre el modelo OLTP

**Preguntar al profe:** ¿Es necesario crear una base de datos OLTP intermedia (normalizada en 3FN) antes de armar el modelo estrella, o se puede pasar directo de los CSVs al Data Warehouse?

Actualmente nuestro flujo es:

```
CSVs planos (SEPA Precios) ──► Modelo Estrella (SQLite)
```

La duda es si el profe espera ver un paso intermedio:

```
CSVs planos ──► Base OLTP (3FN, SQLite) ──► Modelo Estrella (SQLite)
```

Si solo pide que mostremos el modelo OLTP en la documentación, podemos presentarlo como un modelo conceptual/teórico (el DER que tendría el sistema SEPA internamente) sin necesidad de implementarlo.

**Pedir confirmación por escrito.**

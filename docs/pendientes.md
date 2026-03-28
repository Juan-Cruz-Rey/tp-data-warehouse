# Pendientes / Preguntas al profe

## Sobre el modelo OLTP

~~**Preguntar al profe:** Es necesario crear una base de datos OLTP intermedia (normalizada en 3FN) antes de armar el modelo estrella, o se puede pasar directo de los CSVs al Data Warehouse?~~

**RESUELTO (2026-03-18):** El profe Julio Paredes Rojas confirmo por escrito que se puede ir directo de CSVs al modelo estrella en SQLite. No hace falta base OLTP intermedia.

El flujo confirmado es:

```
CSVs planos (SEPA Precios) --> Modelo Estrella (SQLite) --> Power BI (OLAP)
```

La documentacion presenta el modelo OLTP solo como contexto teorico del sistema fuente (SEPA), sin implementarlo.

## Pendientes actuales

- Mandar el diagrama estrella al profe por chat para que lo revise antes de la entrega.
- Esperar la clase de dudas (~1 semana antes de la entrega) para consultas finales.
- Exposiciones opcionales para mostrar el trabajo.

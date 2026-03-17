Sobre el profe:
No se le entiende, así que no des nada por sentado
Preguntale hasta que entiendas todo bien, y que te confirme por escrito lo que entendiste

El error que cometieron ellos (el más importante):

Cargaron el dataset directo en Power BI y ahí lo separaron en tablas
Una semana antes de entregar se dieron cuenta que no se debia/podía hacer así
Había que hacer primero una base de datos real que alimente al Power BI

El flujo correcto es:

Elegís un dataset (ellos usaron uno de canciones de Spotify)
Creás las tablas en SQLite siguiendo el esquema estrella
Cargás los datos con scripts de inserts desde el CSV
Desde Power BI usás "Conectar" para conectarlo a esa base de datos
Power BI te arma casi solo el diagrama estrella porque ya tiene las referencias
Después hacés los gráficos que pide el profe

Sobre la dificultad:
El primer TP es el más jodido, el segundo es pan comido
El profe no es muy exigente con la calidad, así que no te estreses de más

El resumen en una línea: arrancá por la base de datos en SQLite, todo lo demás es fácil.
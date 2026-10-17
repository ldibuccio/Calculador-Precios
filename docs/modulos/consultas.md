# Consultas: el chat de Gerencia con IA (dueño, 16/10)

Gerencia → Mirar → **Consultas** (`/gerencia/consultas`, con la clave de
Gerencia): se le pregunta a la IA por los datos del sistema, como a alguien de
la oficina. La charla dura mientras la pantalla está abierta ("Nueva
conversación" la empieza de cero). Código: `core/consultas_ia.py` (lo que no
toca la base), las rutas en `app/main.py` y lo de la base al final de
`app/db.py`. Tests: `tests/test_consultas_ia.py`.

## Cómo contesta

- **Modelo**: el de la variable `CONSULTAS_IA_MODELO` de Railway; sin ella,
  Claude Sonnet 5.5 (`claude-sonnet-5-5`, dueño, 16/10). Esfuerzo `medium`.
- **Sabe de arranque** el esquema (tablas y columnas, sacadas de
  `db/esquema_completo.sql` sin las tablas de afuera) y el índice de los
  módulos de este directorio (el de CLAUDE.md). Ese texto va en caché.
- **Dos herramientas**:
  - `correr_sql`: UN SELECT (o WITH). Antes de ir a la base se controla que sea
    un solo comando de lectura (`consulta_de_lectura`); en la base corre con
    el usuario `consultas_ia`, en una transacción de solo lectura, 10
    segundos de tope y hasta 200 filas (dice si había más).
  - `leer_documento`: un módulo de `docs/modulos/` por su nombre.
- Hasta 8 pasos (consultas o lecturas) por pregunta; si no llega, lo dice.
- **"Cómo lo calculé"**: debajo de cada respuesta, cada consulta con para qué
  era, su SQL y sus primeras filas (o el error de la base).

## El usuario de la base: `consultas_ia`

Migración `consultas_ia_1` (`db/consultas_ia_1..4`, corrida en las dos bases
el 17/10, ver `db/corridas_confirmadas.md`). Solo lectura y 10 segundos por
consulta (los fija el rol), hasta 3 conexiones, sin `bypassrls`: cada tabla
permitida tiene la política `consultas_ia_lee` (solo leer, solo este
usuario). **Afuera**: `claves_especiales`, `casillas_pedidos` (las
credenciales del mail), `backups_corridas`, `panel_fotos`,
`corte_respaldo_fichas_reprocesos` y las dos de Consultas, y el esquema
`memoria`. **Una tabla nueva no se lee sola**: se vuelve a correr el bloque 3.
Su conexión va en `CONSULTAS_IA_DATABASE_URL` de Railway (la contraseña la
puso Lionel; no pasa por el chat). Sin esa variable la pantalla abre y
preguntar avisa que falta.

## El registro y el tope

- Cada pregunta queda en `consultas_ia_preguntas`: sector, quién (por ahora
  "Gerencia": el sistema no tiene usuarios), la conversación, la pregunta, la
  respuesta, las consultas corridas (SQL, para qué, las primeras 20 filas,
  cuántas eran, el tiempo o el error), el modelo, los tokens y el costo en
  US$. También la que falló. `/gerencia/consultas/registro`: las últimas 100.
- **El costo** sale del uso que devuelve la API, con los precios de
  `PRECIOS_POR_MILLON` (Sonnet 5.5: US$2 la entrada, US$10 la salida, US$0,20
  lo leído del caché, escribir el caché ×1,25). Un modelo sin precio en la
  tabla se cuenta al del más caro: el tope frena de más, nunca de menos.
- **El tope** (`consultas_ia_config`, US$100 de arranque) se cambia en la
  misma pantalla. Con lo gastado en el mes (día de Argentina) igual o arriba
  del tope, no se le pregunta a la IA hasta el 1° del mes siguiente.

## Otros sectores

`SECTORES` en `core/consultas_ia.py` y el `check` de
`consultas_ia_preguntas.sector`: hoy solo `gerencia`. Habilitar otro es un
usuario de la base con sus tablas (como el bloque 3), su ruta con su clave, y
sumarlo a los dos.

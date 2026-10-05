# Módulo: tareas

Movido TAL CUAL desde CLAUDE.md el 03/10 (sin reescribir). Las reglas
vigentes, en corto, están en CLAUDE.md.

## TAREAS (02/10, dueño)

Gerencia les carga tareas puntuales a Compras, Administración o Gerencia, de
una sola vez o repetitivas. El sector las marca como hechas y a Gerencia le
queda cuándo y quién (el SECTOR: el sistema no tiene usuarios). **No tiene
nada que ver con las alertas**, salvo una cosa: una tarea vencida y no hecha
sale en las alertas de GERENCIA (`tareas_vencidas`, solo ahí). La escritura
vive en app/db.py (sección TAREAS) y las reglas, las palabras y los archivos
en `core/tareas.py`.

- **La franja de arriba** (dueño, 04/10; antes era un recuadro propio) va en
  los hubs de Compras, Administración y Gerencia (solo esos tres), debajo del
  banner de alertas: UNA línea con dos botones lado a lado, **Tareas** y
  **Alertas**, que arranca plegada. Tareas dice "Sin tareas pendientes" en
  gris, o "Tareas pendientes (3)" destacado, y en ROJO si alguna venció.
  Alertas dice "Sin alertas" en VERDE o "Alertas (N)" en ROJO (dueño, 04/10),
  N = las que tienen casos; el mismo color va en el botón de Alertas de
  Comercial (`templates/_boton_alertas.html`, lo cuida
  `tests/test_boton_alertas.py`).
  Cada botón despliega lo suyo ABAJO de la línea, a todo el ancho, y abrir
  uno cierra el otro: botón y panel van separados (con dos `<details>` lado a
  lado, lo desplegado quedaba en media columna a 313px). Desplegada, cada
  tarea lleva título, una línea de detalle, vencimiento (en rojo si venció) y
  "Hecha", que abre una nota opcional; abajo, "Nueva tarea", también sin
  pendientes. Las alertas van una por renglón con su link, y abajo "Ver el
  detalle de las alertas" (la pantalla de Alertas del sector, que sigue).
  Si la base no contesta, el botón lo DICE ("Tareas: no se pudieron leer"):
  un "Sin tareas" ahí se vería igual que no tener ninguna. Son dos parciales
  de DOS macros (`templates/_franja_hub.html`, que usa la lista de
  `templates/_tareas_pendientes.html`): los estilos van en el `<style>` del
  hub, así no mueven el corte de los tests. Las palabras de cada alerta salen
  de `_boton_alertas.html`, las mismas que la cinta del banner. Medido a
  313px: sin desborde y sin solapes, los dos botones a la misma altura y de
  44px (`tests/test_franja_hubs.py`).
- **Lo que el sector ve es una OCURRENCIA** (`tareas_ocurrencias`): cada vez
  que la tarea sale, con el título y el detalle de ese momento (editar la
  tarea no reescribe lo que ya salió). La de una sola vez sale al crearla. La
  repetitiva (cada X días, un día de la semana o un día del mes; un 31 cae el
  último día de los meses más cortos) sale el día que le toca y vence ese día.
- **UNA REPETITIVA NO SE ACUMULA.** Si llega la fecha de la siguiente y la
  anterior sigue pendiente, la anterior queda `no_hecha` (con el día en que
  llegó la siguiente) y la nueva sale marcada atrasada. En la lista hay
  una sola. Tres semanas sin abrir el sistema dejan las salteadas como no
  hechas y una sola pendiente.
- **Las ocurrencias se generan AL LEER**, no en el recálculo de cada 6 horas
  (elección del 02/10): `generar_ocurrencias` corre al abrir un hub, la
  pantalla de Tareas y la alerta. Es idempotente (clave `tarea_id + vence_el`,
  `FOR UPDATE` de la tarea y `generada_hasta`), y no depende de que el reloj
  de las alertas esté vivo.
- **El sector marca SU tarea y no puede desmarcarla.** El `WHERE` del UPDATE
  exige el sector y el estado pendiente. Solo Gerencia vuelve una hecha a
  pendiente, con motivo (`tareas_reaperturas`, con lo que decía antes), y solo
  la última ocurrencia de su tarea: reabrir una vieja dejaría dos pendientes.
- **Gerencia → Tareas** (`/gerencia/tareas`, botón en el hub): crear (sector,
  título, detalle y tipo), las repetitivas (editar, pausar, reanudar, dar de
  baja; lo que ya salió queda), y el registro filtrado por sector, fechas de
  vencimiento y estado (pendiente, vencida, hecha, no hecha), con cuándo y
  quién la marcó, la nota y los días de atraso. PDF y Excel con los mismos
  filtros, y el encabezado los dice. Al reanudar una pausada, las fechas de
  la pausa no salen ni cuentan como no hechas: sigue desde hoy.

Migraciones `db/tareas_1` a `_3`, verificación en `_4`. Lo cuida
`tests/test_tareas.py`, contra Postgres.

### Cada sector carga las suyas, y la mensual en varios días (02/10, dueño)

- **Compras, Administración y Gerencia crean tareas para su propio sector**
  (Gerencia, para cualquiera), de una vez o repetitivas, con las mismas
  opciones. Es la MISMA pantalla bajo `/compras/tareas`,
  `/administracion/tareas` y `/gerencia/tareas`, con el sector sacado del
  prefijo (corolario 63). La franja de cada hub tiene "Nueva tarea".
- **`tareas.creada_por`** dice quién la cargó (las de antes, Gerencia). La
  base exige que un sector solo cargue para sí mismo (`tareas_creada_por`).
  Se ve en la lista de la franja, en las repetitivas y en el registro.
- **Un sector edita, pausa y da de baja SOLO las que creó él**; Gerencia
  todas. Lo decide el WHERE de la escritura (`_SQL_PUEDE_MANEJAR`) y la
  pantalla pregunta lo mismo (`puede_manejar`, core/tareas.py): las de
  Gerencia se ven sin controles. El registro sigue siendo de Gerencia, con
  filtro "Creada por" que llevan el PDF y el Excel (y su columna).
- **La alerta de vencidas de Gerencia cubre todas**, las cree quien las cree.
- **La mensual sale en varios días** (`dias_mes`, por ejemplo 1 y 15): cada
  fecha es una ocurrencia, no se acumula (la de antes queda "no hecha" y la
  nueva atrasada), y un día que el mes no tiene cae al último; si dos caen
  el mismo día (30 y 31 en febrero) sale una sola.
- **Migración en dos bloques** (corolario 94): `db/tareas_5` ANTES del
  deploy (agrega `creada_por` con default 'gerencia' y `dias_mes` copiado de
  `dia_mes`; el CHECK acepta las dos formas) y `db/tareas_6` DESPUÉS (vuelve
  a copiar lo que el código viejo haya cargado en la ventana, saca el
  default y borra `dia_mes`). Verificación en `_7`, corrida aparte después
  de cada uno. Lo cuida `tests/test_tareas_por_sector.py`, contra Postgres,
  con la migración corrida sobre el esquema viejo.

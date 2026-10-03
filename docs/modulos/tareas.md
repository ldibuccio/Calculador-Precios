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

- **El recuadro "Tareas pendientes"** va en los hubs de Compras,
  Administración y Gerencia (solo esos tres), debajo del banner de alertas y
  separado de él. Ocupa una línea: "No hay tareas pendientes", o "Tareas
  pendientes (3) · 1 vencida" plegada (un `<details>` sin `open`). Desplegada,
  cada tarea lleva título, una línea de detalle, vencimiento (en rojo si
  venció) y "Hecha", que abre una nota opcional. Al marcarla sale del recuadro.
  Si la base no contesta, el recuadro lo DICE ("No se pudieron leer las
  tareas pendientes"): un "No hay tareas" ahí se vería igual que no tener
  ninguna. Es un parcial de DOS macros (`templates/_tareas_pendientes.html`):
  los estilos van en el `<style>` del hub, así no mueve el corte de los tests.
  Medido a 313px, desplegado y con un nombre que no se parte: sin desborde y
  sin solapes.
- **Lo que el sector ve es una OCURRENCIA** (`tareas_ocurrencias`): cada vez
  que la tarea sale, con el título y el detalle de ese momento (editar la
  tarea no reescribe lo que ya salió). La de una sola vez sale al crearla. La
  repetitiva (cada X días, un día de la semana o un día del mes; un 31 cae el
  último día de los meses más cortos) sale el día que le toca y vence ese día.
- **UNA REPETITIVA NO SE ACUMULA.** Si llega la fecha de la siguiente y la
  anterior sigue pendiente, la anterior queda `no_hecha` (con el día en que
  llegó la siguiente) y la nueva sale marcada atrasada. En el recuadro hay
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
  prefijo (corolario 63). El recuadro de cada hub tiene "Nueva tarea".
- **`tareas.creada_por`** dice quién la cargó (las de antes, Gerencia). La
  base exige que un sector solo cargue para sí mismo (`tareas_creada_por`).
  Se ve en el recuadro, en las repetitivas y en el registro.
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

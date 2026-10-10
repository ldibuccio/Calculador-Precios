# Con fecha anterior (dueño, 05/10)

## Lo decidido

- **Depósito carga merma, pase a segunda y devolución al proveedor SOLO con la
  fecha de hoy.** Hasta el 05/10 la merma y el pase dejaban elegir cualquier
  día pasado, sin clave y sin control; el campo se fue y, si llega igual por
  un POST a mano, se ignora.
- **Administración → Stock → "Con fecha anterior"** (`/administracion/retroactivo`):
  ingreso (la misma pantalla de Gerencia → Ingreso con fecha anterior),
  devolución al proveedor, merma y pase a segunda con un día ANTERIOR a hoy.
  Son las mismas pantallas y rutas que las de Depósito/Gerencia, bajo
  `/administracion/retroactivo/...`: el camino sale del prefijo
  (`_camino_de_stock`, `_camino_de_devolver`, `_camino_del_ingreso_retroactivo`).
- **Contraseña especial**, distinta de la de Administración: la fija y la
  cambia Gerencia (`/gerencia/clave-retroactivo`, botón "Contraseña de fecha
  anterior") y se pide CADA VEZ, en cada carga (no queda en una cookie). Se
  guarda solo su hash PBKDF2 con sal (`claves_especiales`).
- **Queda registrado quién y cuándo** (`retroactivos`: tipo, día del hecho,
  quién —se escribe en la pantalla—, cuándo, y la compra o el movimiento),
  en la MISMA transacción que la carga. La pantalla "Con fecha anterior"
  lista lo cargado, y el detalle de la compra dice "por X".
- **Solo si esa mercadería no era de otro** (`que_tomo_esa_mercaderia`,
  app/db.py): se rejuega el FIFO como está y con la salida nueva en su fecha,
  con el control único `_quienes_quedan_sin` (dueño, 10/10): frena solo si un
  armado o una guía R queda sin mercadería ("El armado del pedido de X del
  dd/mm se queda sin mercadería" / "La guía RN del dd/mm se queda sin
  mercadería") o pierde lo que alguien eligió a mano. Que a otro le toque
  otra guía no frena. Hasta el 10/10 frenaba también eso. También frena si
  ese día no había esa mercadería (sin lote, o un lote elegido que todavía
  no había entrado). El ingreso no se frena: agrega mercadería. La
  devolución, además, no deja devolver más de lo que queda de su compra.
- **La merma de SEGUNDA con fecha anterior no está**: el pool de segunda no
  tiene lotes que rejugar. Se carga desde Depósito.

Migración `db/retroactivo_1_clave_y_registro.sql`. Tests:
`tests/test_retroactivo_administracion.py`, contra Postgres, con el armado
rival.

## De qué guía salió un pedido de un día anterior (dueño, 09/10)

- **"Elegir el lote" de Depósito es del DÍA DEL ARMADO.** En un renglón
  armado un día anterior (`armado_el` en Argentina, antes de hoy) el botón no
  está ("Armado otro día: el lote lo corrige Administración") y
  `guardar_lotes_elegidos` lo rechaza si llega igual por un POST, también
  vaciando: volver al FIFO también cambia de dónde salió.
- **Administración → Con fecha anterior → "De qué guía salió un pedido"**
  (`/administracion/retroactivo/lote-de-pedido`): se elige el día del pedido
  y el cliente, y en el renglón se reparte entre los lotes que había A LA
  FECHA DEL ARMADO (los mismos que ofrece Depósito,
  `_lotes_ofrecidos_al_renglon`). Pide quién lo corrige y la contraseña
  especial, cada vez.
- **El control (dueño, 09/10)** (`_quienes_quedan_sin`, app/db.py): se
  rejuega el FIFO como está y con la corrección puesta, y frena SOLO si un
  armado o una guía R queda con más sin lote ("El armado del pedido de X del
  dd/mm se queda sin mercadería") o pierde bultos de una guía que alguien
  eligió a mano ("... pierde la guía que eligieron a mano"). Que el sistema
  le cambie la guía a un armado que nadie eligió NO frena: lo liberado lo
  toma el siguiente (el ejemplo R683 → R711). Frena también si el renglón
  mismo queda sin lote. Desde el 10/10 es el mismo control para la carga con
  fecha anterior y para anular una guía R.
- **Historial** (`pedidos_renglones_lotes_correcciones`): quién, cuándo, de
  dónde salía antes, de dónde sale ahora (lotes con su nombre y bultos, y lo
  sin lote) y el costo del renglón antes y después. Se ve en la pantalla del
  renglón; la lista marca "Corregido".
- **La fecha del armado no se toca**: se cambia de dónde salió esa misma
  salida (`pedidos_renglones_lotes_elegidos`, como Depósito).
- **Anular una guía R pasa por el mismo control** (`anular_reproceso`): sin
  la guía, si un armado u otra guía R queda sin mercadería o pierde lo
  elegido a mano, no se anula y Guías R dice cuál. Si sus cajas las puede
  cubrir otra guía, o lo que libera lo toma otro pedido, se anula (10/10).

**Hasta el 09/10 frenaba con el estricto**: pasar un renglón a una guía más
nueva le cambiaba la guía al armado siguiente (aunque a la nueva le sobrara)
y eso frenaba casi siempre. El dueño lo aflojó el mismo día.

Migración `db/lote_dia_anterior_1_historial.sql`. Tests:
`tests/test_lote_dia_anterior.py`, contra Postgres, con el armado rival.

## Cómo salió un renglón de un día anterior: en su envase o en caja de Día (dueño, 09/10)

El caso real: Cherry cargado como caja de Día que salió en el descartable del
proveedor (5 o 7 kg), o al revés. En la misma pantalla del renglón ("De qué
guía salió un pedido"), la parte "¿Cómo salió?" aparece solo en las fichas que
eligen (`envase_id` y `envase_variable`: Mango y Cherry). Mismas reglas:
Administración, contraseña de fecha anterior, quién, el control de la
corrección de lote (`_quienes_quedan_sin`) y el historial.

- **Lo hace `corregir_como_salio_de_dia_anterior`** (app/db.py): cambia
  `pedidos_renglones.en_su_envase` y con él todo lo que lo lee. En su envase,
  se liberan las cajas de la guía R y salen cajones de la compra; en caja de
  Día, al revés. La caja de Día deja de cobrarse o se cobra
  (`envase_por_unidad_del_renglon`). Lo elegido a mano se borra: era de la
  otra forma.
- **Kilos, solo en las fichas por kilo (Cherry)**: los kilos enviados pasan a
  ser bultos × kilos por bulto (5 o 7, con botones). En su envase son
  obligatorios; a caja, si no se ponen, los de la ficha. **El Mango no cambia
  la cantidad**: 10 unidades en las dos formas.
- **La fecha del armado no se toca. El remito ya emitido tampoco**: la
  pantalla avisa "El remito N ya salió con X kg: no se toca. Se cobra lo que
  firme el súper."
- **Historial**: `que = 'como_salio'`, cómo salía y cómo sale, los kilos de
  antes y de ahora (vacíos en Mango), de dónde salía y de dónde sale, y el
  costo de la mercadería antes y después (la caja de Día va aparte).

Migración `db/lote_dia_anterior_2_como_salio.sql` (suma también la regla de
lectura de `lectura_claudia`, donde existe). Tests:
`tests/test_como_salio_dia_anterior.py`, con el rival en su envase.


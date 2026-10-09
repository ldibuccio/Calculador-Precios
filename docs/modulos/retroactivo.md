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
- **Solo si esa mercadería no se usó** (`que_tomo_esa_mercaderia`, app/db.py):
  se rejuega el FIFO como está y con la salida nueva en su fecha; si un
  armado o una guía R posterior cambia de qué lote sale, la pantalla dice
  cuál ("La tomó el armado del pedido de X del dd/mm" / "La tomó la guía RN
  del dd/mm") y no deja hasta que eso se elimine. También frena si ese día
  no había esa mercadería (sin lote, o un lote elegido que todavía no había
  entrado). El ingreso no se frena: agrega mercadería.
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
  mismo queda sin lote. La carga con fecha anterior y anular una guía R
  siguen con el estricto (`_quienes_cambian`).
- **Historial** (`pedidos_renglones_lotes_correcciones`): quién, cuándo, de
  dónde salía antes, de dónde sale ahora (lotes con su nombre y bultos, y lo
  sin lote) y el costo del renglón antes y después. Se ve en la pantalla del
  renglón; la lista marca "Corregido".
- **La fecha del armado no se toca**: se cambia de dónde salió esa misma
  salida (`pedidos_renglones_lotes_elegidos`, como Depósito).
- **Anular una guía R pasa por el control estricto** (`anular_reproceso`): sin la
  guía, si un armado u otra guía R cambia de lote o queda sin lote, no se
  anula y Guías R dice quién tomó sus cajas.

**Hasta el 09/10 frenaba con el estricto**: pasar un renglón a una guía más
nueva le cambiaba la guía al armado siguiente (aunque a la nueva le sobrara)
y eso frenaba casi siempre. El dueño lo aflojó el mismo día.

Migración `db/lote_dia_anterior_1_historial.sql`. Tests:
`tests/test_lote_dia_anterior.py`, contra Postgres, con el armado rival.

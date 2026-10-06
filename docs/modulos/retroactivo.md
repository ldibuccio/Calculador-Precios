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

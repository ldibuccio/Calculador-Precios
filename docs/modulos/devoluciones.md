# Módulo: devoluciones al proveedor

Movido TAL CUAL desde CLAUDE.md el 03/10 (sin reescribir). Las reglas
vigentes, en corto, están en CLAUDE.md.

## DEVOLUCIONES DE MERCADERÍA AL PROVEEDOR (30/09, dueño)

Son DOS operaciones y se registran separadas; en las dos el COSTO SE CANCELA
(sale de la Rentabilidad Real) y el valor se ve en Movimientos del depósito.

- **Por rechazo** (Reingreso, destino "devolución al proveedor"): pide la
  compra. Viene elegida la que el sistema dice que alimentó el armado, y se
  puede cambiar por cualquier otra compra recibida de ESE artículo
  (`_compras_para_devolver_el_renglon`: la pantalla y el POST leen las mismas
  dos listas). Lo que vale está en "EL VALOR DE UNA DEVOLUCIÓN", abajo.
  La caja de Día se devuelve en la caja de Día, como antes.
- **Desde depósito** (`/deposito/devolver`, sin clave): proveedor → sus
  compras con lo que QUEDA en el piso (el restante del lote de la compra en el
  reparto de ahora, `_compras_con_resto_del_proveedor`) → cantidad, motivo y
  fotos opcionales, que van a las fotos de la compra (`fotos_recepcion`, con
  `movimiento_id`: el detalle de la compra no las deja borrar). Nunca
  más de lo que queda: el tope se recalcula en el POST. Es un movimiento
  `devolucion_deposito` (migración `db/devolucion_deposito_1`, verificación en
  `_2`), con cantidad negativa y la compra obligatoria (CHECK).
- **La devolución de mercadería se puede cargar desde Depósito o desde
  Administración** (dueño, 01/10). Es la MISMA pantalla y la misma escritura:
  `/deposito/devolver` sin clave y `/administracion/devolver` detrás de la
  clave de Administración (botón "Devolver mercadería" en la tarjeta "Control
  de stock" del hub, desde el 01/10: saca mercadería del piso). El sector sale del prefijo (corolario 63) y se
  guarda en `movimientos_stock.cargada_desde` ('deposito' o
  'administracion'), sin default en la escritura: un camino que no lo diga es
  un TypeError, y la base lo rechaza (`movimientos_stock_devolucion_con_sector`,
  solo la devolución lo lleva). Las anteriores al 01/10 son de Depósito, la
  única puerta que había. Movimientos del depósito dice "cargada desde …" en
  cada devolución, la filtra por sector ("Cargada desde") y la lleva en el
  Excel. Migración `db/devolucion_sector_1` (antes del deploy) y `_2` (después:
  completa las que cargó el código viejo en el medio y agrega el CHECK),
  verificación en `_3`.
- **Sale del lote de SU compra y de ningún otro**: `_SQL_SALIDAS_STOCK` le
  dirige el lote a la compra, y `pasadas_de_lotes` no le da pasada de FIFO. Lo
  que la compra no cubra queda sin lote, a la vista; nunca se lleva otra
  compra. El costo se cancela porque `costo_real` no cuenta esa salida.
- **Con seña, los cajones vuelven LLENOS y salen de Vacíos**, de ese proveedor
  y esa marca (`_SQL_DEVOLUCIONES_LLENAS`, pata "devueltos" de la cuenta y
  "Volvió llena" en los movimientos). En un rechazo, solo si iba en el cajón.
- **Nada de esto mueve el stock de hoy**: los rechazos nunca volvieron al
  stock, y lo nuevo solo cuenta desde que se carga.
- **La devolución de mercadería con seña NO genera un vale** (dueño, 30/09):
  vuelve en su envase por cuenta corriente, como si nunca hubiera entrado. Lo
  que sí muestra Movimientos del depósito es la seña (`sena` en
  `_SQL_MOVIMIENTOS_DEL_DEPOSITO`, `texto_de_la_sena` en la pantalla y en el
  Excel): "entró con seña: N cajones × $X" en la entrada y "volvió con seña"
  en la devolución. En un rechazo, solo si iba en el cajón, la misma regla que
  saca esos cajones de Vacíos.

### EL VALOR DE UNA DEVOLUCIÓN: el precio por cajón de SU compra (01/10, regla de Lionel)

**Una devolución al proveedor vale EXACTAMENTE `compras.importe` de la compra
a la que está atada**, por los dos caminos, en la Rentabilidad Real, en
Movimientos del depósito y en el Resumen proveedores (pantalla, PDF y Excel).
Nunca el costo del armado: ése sale del FIFO por kilo y mezcla compras con
distinto peso por cajón (Frutamax, 28/09: $59.822,75 por un cajón de Granny
pagado a $60.000).

- **Escrita una vez**: `_SQL_VALOR_POR_BULTO_DE_LA_DEVOLUCION` y su condición
  `_SQL_DEVOLUCION_VALE_LA_COMPRA` (app/db.py). La leen
  `_SQL_MOVIMIENTOS_DEL_DEPOSITO` (y con ella la planilla) y
  `devoluciones_vinculadas_por_rango` (la Rentabilidad).
- **Compra sin precio**: el valor es NULL ("sin precio"). No cae al costo del
  armado, que era volver a la regla vieja.
- **Rechazo en caja de Día CON compra atada: también el precio de la compra**
  (Lionel, 02/10, opción B). Cada caja se valúa como un cajón entero de esa
  compra, con la diferencia contra el armado en su renglón, igual que el
  cajón. Es SOLO plata: la caja de Día no es un cajón del proveedor, así que
  ese rechazo **no sale de Vacíos** aunque la compra tenga seña, y
  Movimientos no le muestra seña (`_SQL_DEVOLUCIONES_LLENAS` y la `sena` de
  `_SQL_MOVIMIENTOS_DEL_DEPOSITO` siguen preguntando por `envase_id`). Caso
  real: movimiento 199, 2 Cherry, compra 826 a $30.000, vale $60.000 y la
  diferencia es 2 × (30.000 − 30.523,26) = −1.046,52.
- **Sin compra atada** (los viejos): queda el costo congelado del rechazo. Es
  la única excepción.
- **La diferencia no desaparece**: en la Rentabilidad la mercadería se acredita
  al costo CONGELADO del armado (lo que se le cargó al venderla), y
  `bultos × (precio de la compra − costo del armado)` va a
  `diferencia_devolucion_proveedor`, que RESTA del costo total (positiva: el
  proveedor devuelve más de lo que costó el armado, y sube la renta). Se ve en
  el chip del artículo ("devuelto al proveedor N bultos · al precio de la
  compra · +$X contra el costo del armado"), en la línea del total, en el PDF y
  en dos columnas al final del Excel. El crédito total de la devolución es
  bultos × precio de la compra.
- **`movimientos_stock.costo_por_bulto` NO se toca**: sigue siendo el costo
  congelado del armado, y es el dato con el que se calcula la diferencia.
- La devolución desde depósito no entra a la Rentabilidad como renglón: sale
  del lote de su compra, que ya cuesta el precio de esa compra.

`db/devolucion_valor_1` lista todas las devoluciones con el valor de la regla
del 01/10 y el de la opción B (solo lee). `_2` ata el movimiento 170 a su
compra, con guardas, y `_3` lo verifica (corrida el 02/10 en Frutamax, ver
`db/corridas_confirmadas.md`). Lo cuidan `tests/test_devoluciones_al_proveedor.py` (contra
Postgres) y `tests/test_costo_real.py`.

**Movimientos del depósito** (`/administracion/ingresos`, dueño, 30/09):
entradas de compra, devoluciones por rechazo, devoluciones desde depósito y
segunda remitida al puesto, filtrados por fecha (30 días por defecto, 90
máximo), tipo, proveedor y artículo, con Excel. Agrupado por proveedor con la
cuenta arriba ("Entraron · se devolvieron · neto", en bultos y en plata; si una
compra no tiene precio lo dice), para conciliar. El Resumen proveedores que
vivía ahí pasó a `/administracion/ingresos/pagar`, linkeada desde la pantalla.
Los textos y el Excel están en `core/movimientos_deposito.py`.

**El Resumen proveedores resta las devoluciones** (dueño, 01/10): cada
devolución al proveedor (por rechazo o desde depósito) es un renglón NEGATIVO
del día en que se devolvió, en el grupo de su proveedor, con la compra, el
artículo, los bultos, el importe y el tipo. El subtotal y el total son lo que
entró menos lo devuelto, en la pantalla, el PDF y el Excel. El importe sale de
la MISMA consulta que Movimientos del depósito (`_devoluciones_para_pagar`),
y si la devolución vuelve con seña, la seña de esos cajones también se resta.
Solo con el estado "A pagar" o "Todas": los otros dos son para controlar.
Lo cuida `test_el_RESUMEN_PROVEEDORES_resta_las_devoluciones...`, contra
Postgres.

**La marca del cajón en cada renglón (dueño, 05/10)**, debajo del artículo:
la que escribió Recepción o, si no hay texto, la marca de cajón pegada
(`_SQL_MARCA_DEL_CAJON`); "Sin marca" si no tiene. La devolución toma la de
SU compra. **En el celular no va el total de señas** (los desgloses
"mercadería + señas" del proveedor y del final, clase `desglose-senas`); la
seña de cada compra sí. El PDF lleva la marca y los desgloses; el Excel, la
columna Marca y el Total seña también en el subtotal y en el total. Tests:
`tests/test_resumen_proveedores_marca.py`.

Las fotos de la devolución usan el mismo parcial que el ingreso directo
(`templates/_fotos_para_subir.html`, dos macros: `estilos()` va en el
`<style>` de la pantalla, así no queda un `<style>` en el medio que corte el
`split` de los tests).

Lo cuida `tests/test_devoluciones_al_proveedor.py`, contra Postgres, con la
compra más vieja de rival.

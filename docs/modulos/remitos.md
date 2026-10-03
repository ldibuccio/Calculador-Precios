# Módulo: remitos y facturación

Movido TAL CUAL desde CLAUDE.md el 03/10 (sin reescribir). Las reglas
vigentes, en corto, están en CLAUDE.md.

## REMITOS Y FACTURACIÓN (01/10, dueño)

**El remito es UNO POR ORDEN DE COMPRA** (`pedidos_sucursales`): un pedido de Día
lleva tres. El remito oficial sale de otro sistema; acá se anota su número, se
congela lo que salió, se carga lo que firmó el súper y el número de factura. La
facturación y la cobranza no se hacen acá. La regla pura vive en
`core/remitos.py` y la escritura en `app/db.py` (sección REMITOS).

- **Tres estados, derivados de las fechas** (no hay columna de estado):
  emitido (`numero`), recibido (`recibido_el`), facturado (`factura_numero`).
  Uno solo por orden (`remitos_uno_por_orden`) y el número es único por
  cliente (`remitos_numero_por_cliente`, plegado con `upper(btrim())`): **lo
  decide la base y el código traduce el error**.
- **UN REMITO NO SE ANULA** (dueño, 01/10): una vez que salió al súper, vuelve
  con sus observaciones. No hay columna, función ni pantalla para anularlo.
  **Gerencia solo puede CORREGIR EL NÚMERO** (error de tipeo), en cualquier
  estado, en el detalle del remito: queda el registro en `remitos_numeros`
  (anterior, nuevo, fecha y hora), y el detalle lo muestra.
- **Emitir congela** bultos y `kilos_enviados` de cada renglón armado de esa
  sucursal (`remitos_renglones`), la totalidad del pedido. Eso no se toca
  nunca. Sin kilos enviados no se emite: se cargan en Armar Pedido. Un pedido
  reemplazado no se remite. Una sucursal sin fila en `pedidos_sucursales`
  (pedido cargado a mano) la crea al emitir.
- **EL REMITO OBSERVADO ES EL MISMO REMITO.** Recibir se busca por número y
  abre ESE remito: por renglón, **bultos recibidos y kilos recibidos**,
  precargados con lo enviado MENOS lo que Depósito ya cargó como rechazado de
  ese renglón (dueño, 02/10, `precarga_de_lo_recibido` en core/remitos.py):
  bultos = enviados − rechazados, kilos proporcionales, todo rechazado da 0 y
  0, y sin rechazos cargados es lo enviado. Caso real: el remito 20424
  precargaba 10/160 en Tomate Redondo con los 10 rechazados (se guardó bien,
  a mano, en 0/0). Se cambia solo lo que anotó el súper (que tome
  todo con menos kilos, que rechace bultos, o las dos cosas). Enviado y
  recibido quedan lado a lado en la fila; un renglón cambió si difieren
  (`renglon_cambio`), y la hora es `recibido_el`. El detalle dice "Volvió
  observado: N renglones con cambios". La foto del remito firmado es
  obligatoria (bucket "comandas", prefijo `remitos`, tabla `remitos_fotos`).
  Hasta el 01/10 se cargaban kilos y bultos RECHAZADOS; se cambió a recibidos.
- **EL REMITO RECIBIDO NO MUEVE STOCK.** Los bultos rechazados entran al
  depósito por el circuito de rechazo de siempre (`movimientos_stock` con
  `pedido_renglon_id`), que es independiente. El cotejo es aparte: rechazo
  según el remito (enviados − recibidos, `rechazo_del_remito`) contra los
  reingresos de Depósito de ese renglón (`_SQL_RECHAZO_DE_DEPOSITO`). Si no
  coincide se ve en el remito y salta `remitos_rechazo_distinto`, que se apaga
  sola cuando Depósito corrige el reingreso.
- **El importe a cobrar** es kilos recibidos × precio vigente el DÍA DEL
  PEDIDO (`_SQL_PRECIO_DEL_RENGLON`: la fila de la ficha con `vigente_desde`
  más reciente que ya había llegado). Es informativo, para controlar la
  factura. Un renglón sin precio no suma y se dice.
- **Facturar**: una factura cubre uno o varios remitos recibidos del MISMO
  cliente; un remito tiene una sola factura.
- **Pantalla Administración → Facturación** (`/administracion/facturacion`,
  botón "Remitos y facturas"): pedidos sin remito, en viaje, recibidos sin
  factura y facturados (filtro por fecha de factura). La misma pantalla en
  `/gerencia/facturacion`, sector por prefijo (corolario 63): Gerencia mira y
  corrige el número; Administración emite, recibe y factura. Armar Remito dice
  en cada sucursal "Emitir remito" o el número del que ya está, y no desborda
  a 313px (el nombre del artículo envuelve: `min-width: 0` + `overflow-wrap`).
- **Se emiten, reciben y facturan remitos de pedidos de CUALQUIER fecha**,
  también anteriores a `REMITOS_DESDE`, desde Armar Remito.
- **Rentabilidad Real cobra lo RECIBIDO** cuando el remito volvió ("le pagan
  lo recibido": kilos recibidos × precio), y su devolución ya no resta venta
  (lo rechazado está afuera de lo recibido); el costo se acredita igual.
  Mientras no vuelve se usa lo enviado, y **solo desde `REMITOS_DESDE`** el día
  sale "Provisorio (remito sin volver)", en la pantalla, el PDF y el Excel
  (`kilos_recibidos_por_renglon`, `fechas_provisorias`). Los días anteriores
  siguen como siempre, con lo enviado, salvo que tengan el remito recibido.

**Las alertas** (Administración y Gerencia), con sus plazos en
`core/remitos.py`:

- `remitos_sin_volver`: emitido hace **más de 4 días corridos**
  (`DIAS_REMITO_SIN_VOLVER`). El camión vuelve en el día; el 4 contempla un fin
  de semana largo o un feriado.
- `remitos_sin_factura`: recibido hace **más de 10 días corridos**
  (`DIAS_REMITO_SIN_FACTURA`). Se factura una vez por semana, más fin de semana
  y feriados.
- `remitos_rechazo_distinto`: el papel y Depósito no dicen lo mismo.
- `pedidos_sin_remito`: órdenes de compra armadas sin remito, **solo desde
  `REMITOS_DESDE`** (01/10/2026, el día del merge, `core/remitos.py`). Es lo único
  para lo que sirve esa fecha, además del provisorio de la Rentabilidad. Lo
  anterior nunca tuvo remito en este sistema y no es un olvido.

Migraciones `db/remitos_1` a `remitos_4`, verificación en `remitos_5`. Lo cuida
`tests/test_remitos.py`, contra Postgres.

# Módulo: cobranzas de segunda

Movido TAL CUAL desde CLAUDE.md el 03/10 (sin reescribir). Las reglas
vigentes, en corto, están en CLAUDE.md.

## COBRANZAS DE SEGUNDA (02/10, dueño)

Lo que paga el puesto de segunda, lote por lote. `/administracion/cobranzas-segunda`
y `/gerencia/cobranzas-segunda` son la MISMA pantalla, con el sector sacado del
prefijo (corolario 63). La escritura vive en app/db.py (sección COBRANZAS DE
SEGUNDA) y las reglas, las palabras, el PDF y el Excel en `core/cobranzas_segunda.py`.

- **Un LOTE es una salida al puesto de segunda**: `remitos_segunda` con
  destino 'puesto' y no anulada. Nace pendiente: sin fila en `segunda_cobros`.
  La merma de segunda no es un lote, porque se tiró y no hay nada que cobrar.
- **Hay un solo puesto de segunda**, así que no se elige.
- **El puesto liquida lote por lote.** No hay un total de rendición que
  repartir: se carga cuánto pagó cada lote. **$0 es un cobro**: el lote queda
  cobrado en cero, no pendiente.
- **La carga es de a muchos**: cada pendiente trae su campo de importe, y
  "Guardar cobros" graba todos los que tienen importe con la fecha de cobro
  (hoy por defecto, editable, nunca futura). Es todo o nada: si un lote rebota,
  no se graba ninguno y el mensaje dice cuál.
- **"Quién" es el SECTOR y la hora**, como en Vales: el sistema no tiene
  usuarios. Cargan Administración y Gerencia.
- **Solo Gerencia corrige** un importe mal cargado, o vuelve un lote a
  pendiente con motivo. Las dos cosas quedan en `segunda_cobros_historial`
  (anterior, nuevo o motivo, fecha y sector), como el número de remito. La
  base solo acepta el historial con sector 'gerencia'.
- **Una salida con cobro no se anula.** Primero Gerencia la vuelve a pendiente.
  Lo decide un trigger de la base (`segunda_cobrada_no_se_anula`) y
  `anular_remito_segunda` lo traduce (`LoteDeSegundaCobrado`). Movimientos de
  Stock no ofrece "Anular" en un lote cobrado. Otro trigger
  (`segunda_cobro_solo_lote_vigente`) solo deja cobrar un lote al puesto que
  no esté anulado.
- **Filtros**: fechas de salida, artículo y estado. El PDF y el Excel salen
  con los mismos filtros y los dicen en el encabezado (regla del 01/10).
- **Alerta `segunda_sin_cobrar`** (Administración y Gerencia): un lote
  pendiente con más de `DIAS_SEGUNDA_SIN_COBRAR` (40) días corridos desde la
  salida. Entra en el recálculo de siempre.
- **Rentabilidad Real**: lo cobrado es un renglón POSITIVO, "Recupero de
  segunda", aparte de la venta al súper. Va al DÍA DE LA SALIDA del lote, no
  al del cobro, y al artículo del lote. Suma a la renta. Como la merma, es del
  artículo y no del cliente: entra en la fila del artículo con cualquier
  cliente elegido. Un lote sin cobrar no suma nada y NO vuelve provisorio el
  día: el día dice "N lotes de segunda sin cobrar". Se ve en la pantalla (chip
  por artículo, línea del total y aviso por día), en el PDF (línea del total y
  un párrafo con los días) y en el Excel (dos columnas al final y los días en
  el subtítulo).

Migraciones `db/cobranza_segunda_1` a `_3`, verificación en `_4`. Lo cuida
`tests/test_cobranzas_segunda.py`, contra Postgres.

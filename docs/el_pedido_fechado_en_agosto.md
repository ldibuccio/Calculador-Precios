# El pedido que quedó fechado en agosto (08/09/2026)

Un mail de Día llegó el **08/09** con el asunto `Pedido Dia 09-08`. El
sistema lo leyó como **9 de agosto** —día y mes dados vuelta— y el pedido
quedó fechado treinta días atrás. No apareció en "Pedidos para armar",
porque esa pantalla muestra **una fecha por vez**.

Desenlace: el pedido 19 (09/08) anulado, el 20 (08/09, cargado a mano)
vigente y armable.

## La hipótesis era que el auto-confirmado ignoraba el chequeo. Era al revés

`_intentar_auto_confirmar` tiene cinco candados y el segundo es la fecha.
**Frenó bien.** Reproducido corriendo la función real, no leyéndola:

```
'Pedido Dia 09-08 Miercoles'  -> 2026-08-09  dif 30  FRENA (>5)
'Pedido Dia 09-09 Miercoles'  -> 2026-09-09  dif  1  pasa
'Pedido Dia 08-09'            -> 2026-09-08  dif  0  pasa
```

**Lo confirmó una persona**, por el camino manual.

## La misma regla en tres lugares con tres fuerzas

| dónde | qué hacía |
|---|---|
| `_intentar_auto_confirmar` | **pared**: `return False`, el mail queda pendiente |
| la revisión a mano | **cartel**: `aviso_fecha`, y nada más |
| `confirmar_pedido` (el que ESCRIBE) | **nada**: guardaba lo que viniera en el form |

Dos literales `> 5` en dos lugares, y el que escribe sin ninguno. **La
pared frenó, el cartel no, y el pedido entró por el camino del humano —
que es el que la gente usa.** El candado automático era más estricto que
el manual. Ver corolario 26.

Ahora la regla vive una sola vez (`motivo_fecha_dudosa`,
`core/casilla_pedidos.py`), los tres la usan, y el guardado la exige con
un **tilde**: "Sí, la fecha es correcta". Del lado del servidor, porque el
`required` del HTML se saltea con un POST a mano.

Y el aviso nombra el modo de falla real —**día y mes dados vuelta**— y
muestra los dos días. Antes decía "puede ser un error de tipeo", que es
cierto y no dice qué mirar.

## La guarda que no guardaba

El primer SQL para anular usaba `select count(*) ... into` y después
`if not found`. **`not found` no se dispara nunca después de un
agregado**: la fila vuelve con 0 aunque no haya nada. Anular un id
inexistente salía `DO`, y sobre un pedido ya anulado **pisaba su
`anulado_el` original** — peor que no anular. Ver corolario 27.

Lo agarró probar los cuatro casos, no leer el bloque.

## Lo que ninguna cuenta tomó, y lo que sí

Verificado sobre los 22 lectores de `pedidos_renglones`: **18 exigen
`armado_el IS NOT NULL`**, y el pedido nunca se armó. El stock, el FIFO y
la Rentabilidad Real no lo vieron nunca — y además el piso del corte
(05/09) deja afuera cualquier cosa de agosto.

Sí podían tomarlo, y solo durante las dos horas que estuvo vivo:

- la **incidencia de facturación**, en el balde `'2 sin kilaje (sin
  armar)'` — aunque hoy queda afuera por un día (`fecha_operacion > hoy − 30`);
- la **Rentabilidad de Pedidos** (teórica), que es demanda y no tiene piso
  de corte.

**Facturación en plata: cero.** Sin `kilos_enviados` el renglón no aparece.

## Lo que quedó construido

- `motivo_fecha_dudosa` + el tilde en el guardado.
- `anular_pedido` con tres guardas y la ruta
  `POST /administracion/pedidos/{id}/anular`, en **Administración
  solamente**: dar de baja un pedido entero no es decisión de galpón. El
  botón queda **deshabilitado y a la vista** con el motivo cuando hay
  renglones armados — uno que no está no enseña por qué, y el que lo busca
  termina en el editor de la base, que es de donde venía todo esto.
- Consultas: `mails_1` / `mails_2` (mails confirmados sin pedido vivo),
  `mover_fecha_1` / `mover_fecha_2`, `anular_pedido_1_con_guarda`.

**Nota sobre el commit `af41276`**: su asunto dice "(pendiente de
aprobacion)" porque se escribió en la rama antes del OK. Se aprobó y se
mergeó a `main` sin cambios. El mensaje quedó viejo y no se reescribió: la
historia ya estaba publicada y no vale reescribirla por algo cosmético.

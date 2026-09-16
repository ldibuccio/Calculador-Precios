# El costo de las cajas que salen sin una venta atrás

Del 16/09. **Reescrito el mismo día**: la primera versión descansaba sobre un
dato del galpón que el dueño dio vuelta, y la mitad de lo que decía era falso.
**Ningún número de aquella versión se vuelve a citar.**

## Lo que se cayó, y por qué se deja escrito

Decía que la segunda de un reproceso sale en caja de Día igual que la primera.
**Es al revés: la primera va en caja de Día y la segunda queda en el envase del
proveedor.** No lleva caja nuestra.

Eso mató tres cosas de un saque:

1. Los **80,97 bultos** de `reprocesos.bultos_segunda` no son cajas nuestras y
   no van en ninguna cuenta de envase.
2. `pct_sin_primera` medido sobre esa columna **no significaba nada**, y el
   factor que se iba a calcular con él habría corregido una fuga inexistente.
3. Y se había cambiado el stock de cajas para descontarla: restaba 80,97
   bultos por trimestre de un stock del que nunca salieron. Revertido — ver
   el corolario 71 de CLAUDE.md, que además anota el error de método.

## Lo que queda, que es más chico y tiene otro nombre

**No es un subproducto del reproceso: son los RECHAZOS.** Una caja que se
pierde por esta vía hace este recorrido:

1. Se llena en una guía R con primera → **la tasa cobró una caja** contra el
   precio de esa unidad, y el stock la descontó ahí.
2. Sale con una entrega.
3. **El súper la rechaza** y vuelve, llena, en nuestra caja.
4. Y se va de nuevo, para siempre, por una de dos puertas.

| puerta | `destino_rechazo` | qué pasa con la caja |
|---|---|---|
| **2. Segunda al Puesto** | `segunda` | se va con la mercadería |
| **3. Devolución al proveedor** | `devolucion_proveedor` | se va, si vuelve en caja de Día |
| (vuelve a cajón grande) | `reproceso` | **se libera** — ya la suma `liberadas` |
| (vuelve a stock) | `stock` | neutro por construcción |

`cajas_4` midió las dos primeras: **149 cajas en 90 días — 84 chicas a $650 y
65 grandes a $1.600, $158.600.** Cruzando `movimientos_stock` con la ficha del
renglón, o sea mercadería que volvió del súper y que efectivamente salió en
caja nuestra.

**El stock de cajas ya está bien y nunca estuvo mal para estas dos**: la caja
se descontó cuando se llenó y no vuelve a sumarse. Lo que falta es el COSTO.

## LA PREMISA QUE DECIDE TODO, Y NO ES MEDIBLE ACÁ

**¿La mercadería rechazada se le factura igual a Día, o se le acredita?**

- **Si se acredita** → la venta se cae, la tasa no cobró nada, y la caja se
  fue igual. La fuga es real y son los $158.600 por trimestre.
- **Si se factura igual** → la caja ya está pagada por esa venta. **No hay
  ninguna fuga**, y todo este documento describe un problema que no existe.

No hay consulta que lo conteste: la nota de crédito no vive en este sistema.
**Se pregunta.** Y se pregunta como corresponde —*¿qué pasa con la factura
cuando el súper rechaza?*— y no *"se acredita, ¿no?"*, que es exactamente la
forma que produjo el error de esta misma mañana.

## El denominador, que es lo que hace legible el número

$158.600 por trimestre no se puede leer solo. Lo que decide es **contra cuántas
cajas salieron**: 149 sobre 5.000 es 3%; 149 sobre 800 es 19%. El denominador
ya existe y es `por_guias`, la columna que la pantalla de Cajas muestra al lado
del stock. La consulta que los pone en la misma fila, por ficha, es
`db/cajas_7_las_que_se_pierden_contra_las_que_salen.sql`.

## Las opciones, y la recomendación

### A) Un FACTOR sobre la tasa de envase — **no**

Aritméticamente cierra y por ficha sería el grano correcto. Pero:

- **Difumina un costo ATRIBUIBLE.** Un rechazo tiene artículo, cliente y
  fecha. Meterlo en la tasa lo reparte entre todas las ventas de esa ficha,
  que es justo donde deja de poder arreglarse. La regla de esta casa es la
  contraria: el aviso va en la unidad de la CAUSA, no en la del síntoma.
- **Es un instrumento grande para un costo chico.** 149 cajas por trimestre
  son 1,6 por día. Mover una lista de precios es un acto comercial con una
  contraparte enfrente; recuperar $53.000 por mes por esa vía cuesta más
  conversación de la que vale.
- **Y le cobra el rechazo de Día a Día**, lo cual es defendible — pero eso es
  una POLÍTICA, no la corrección de un error de cuenta, y conviene no
  disfrazarla de lo segundo.

### B) Un costo fijo mensual estimado — **no**

No hay libro de gastos en este sistema, así que sería un número que no
alimenta ninguna cuenta: no traba nada, no cambia ningún precio, no aparece en
ninguna decisión. Es el perfil exacto del campo sin consecuencia.

### LO QUE LA MEDICIÓN CAMBIÓ: el 88% ya estaba contado

Buscando dónde poner el renglón apareció que **casi todo el número ya estaba en
el sistema**. Medido corriendo `calcular_rentabilidad_real` con el costo de
envase por unidad en 0 y en 80, y mirando `rechazos_perdidos`:

| destino | con envase 0 → 80 | qué significa |
|---|---|---|
| `segunda` | 10.000 → **18.000** | la caja **ya se cuenta como pérdida** |
| `reproceso` | 10.000 → **18.000** | también — **y esa caja vuelve** |
| `devolucion_proveedor` | 0 → **0** | no se nombra; queda dentro de `costo_envase` |
| `stock` | 0 → **0** | correcto: la caja vuelve llena |

Con el desglose de `cajas_4` —54 chicas + 65 grandes al Puesto, 30 chicas
devueltas— eso parte los $158.600 en:

- **Puerta 2 (al Puesto): $139.100 — YA contado**, adentro de
  `rechazos_perdidos`, sumado con la mercadería.
- **Puerta 3 (devueltas): $19.500** — la caja se gastó y el costo está
  cobrado, pero **sin nombre**: vive en `costo_envase` como si esa caja
  hubiera salido con una venta.

**O sea que no faltaba una cuenta: faltaba poder LEER la caja separada de la
fruta.** Un chip que dice `$18.000` se lee como mercadería, y lo que se
negocia con Día es la caja.

### C) Lo que va: **contarlo donde se causa, y no tocar ningún precio**

1. **El gasto real de cajas, visible** — hecho el 16/09 en la pantalla de
   Cajas: cuántas cajas se compraron y cuánta plata, valuadas al costo que
   regía el día de cada compra. Eso es lo que contesta *"que no aparezca como
   sorpresa cuando compro cajas"*, y no dependía de ninguna decisión.
2. **HECHO el 16/09: las cajas perdidas, al lado del rechazo.** En
   Rentabilidad Real —que ya es por cliente, por artículo y por período—:
   un renglón con el total (*"los rechazos se llevaron N cajas · $X"*) y un
   chip por artículo. `cajas_perdidas` y `cajas_perdidas_pesos` cubren las
   DOS puertas donde la caja no vuelve (`DESTINOS_QUE_SE_LLEVAN_LA_CAJA`).

   **No mueve ningún total**, y eso está medido con el destino `stock` de
   control: la misma venta y la misma devolución dan idéntico `costo_total`
   y `renta_pesos` con la caja contada y sin ella. Es el mismo dinero,
   nombrado — si sumara, estaría cobrado dos veces.

   Y **no va en "Afuera del cálculo"**, que es la lista de cosas a ARREGLAR:
   esto no se arregla cargando nada, se negocia. Meter ahí renglones que no
   piden acción es cómo esa tarjeta deja de mirarse, y está escrito en su
   propio CSS desde antes.
3. **Y la validación que ya está armada**: lo COBRADO por la tasa contra lo
   CONSUMIDO (`por_guias`). Son dos fuentes independientes del mismo hecho, y
   si no cierran por más que los rechazos, ahí hay algo. (Comprado contra
   stock NO sirve: es una identidad por construcción y siempre cierra.)

## Lo que sigue sin declararse

`movimientos_stock.lleva_caja_nuestra` y `envase_id` solo se pueden escribir
cuando `destino_rechazo = 'reproceso'` — lo dice el CHECK. Así que **las dos
puertas que pierden la caja no la declaran**, y `cajas_4` la DEDUCE de la ficha
del renglón.

Eso funciona hoy y tiene un costo conocido: la ficha es la de AHORA, así que
cambiarle el envase a una ficha **re-etiqueta la historia en silencio**. Es
exactamente la razón por la que `reprocesos.envase_id` se guarda en vez de
leerse de la ficha, y está escrita en el comment de esa columna.

El arreglo es la misma columna con la misma regla y la misma función,
extendida a los otros dos destinos. **No se construyó**: primero la premisa de
la factura, que puede cerrar el tema entero.

## Lo que queda ABIERTO, y es una decisión del dueño

**`reproceso` cuenta la caja como perdida y esa caja vuelve.** Está en
`DESTINOS_RECHAZO_PERDIDO` —donde corresponde, porque la MERCADERÍA sí se
pierde: va al pool de segunda— pero su caja **se vacía al pasar la fruta al
cajón grande y queda disponible de nuevo**. Así que `rechazos_perdidos` le
suma `unidades × envase_unidad` a una caja que sigue en el galpón.

Son dos preguntas distintas sobre la misma fila —*¿se perdió la mercadería?*
y *¿se perdió la caja?*— y hasta el 16/09 las contestaba una sola lista. El
número nuevo (`cajas_perdidas`) ya las separa; **lo que no se tocó es
`rechazos_perdidos`**, porque corregirlo mueve una pérdida que hoy se informa
y eso se decide, no se mete en un commit de otra cosa.

**Y hay una segunda mitad del mismo hecho, del corolario 72**: la pata
`liberadas` del stock de cajas —la que devolvería esa caja al stock— es CERO
por construcción, porque **nadie escribe `movimientos_stock.envase_id`**. Así
que hoy los dos están mal en la misma dirección: el stock no la devuelve y el
costo la cobra perdida. El día que alguien le ponga escritor a esa columna,
los dos se separan.

Cuánto pesa no se sabe: `cajas_7` excluye `reproceso` a propósito. Sale de
correr la misma consulta con ese destino agregado, que es el canario A de
`tests/test_costo_real.py`.

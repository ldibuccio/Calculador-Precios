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
| (vuelve a cajón grande) | `reproceso` | **SE TIRA** — cobrada en `rechazos_perdidos`, nombrada desde el 17/09 |
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
| `reproceso` | 10.000 → **18.000** | también — **y esa caja NO vuelve: se tira** |
| `devolucion_proveedor` | 0 → **0** | no se nombra; queda dentro de `costo_envase` |
| `stock` | 0 → **0** | correcto: la caja vuelve llena |

**Esa fila de `reproceso` decía "y esa caja vuelve" y es FALSA** — la premisa
se dio vuelta el 17/09: se tira. La medición de al lado no cambia (el envase
entra igual en `rechazos_perdidos`); lo que cambia es que ya no hay ninguna
caja que "vuelva" fuera de `stock`, y por eso el renglón que las nombra la
incluye desde ese día.

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

## CERRADO el 17/09: la caja del `reproceso` SE TIRA

La pregunta abierta era si `reproceso` cobraba de más: su caja **parecía
volver** —la fruta pasa al cajón grande y la caja quedaría libre— mientras
`rechazos_perdidos` le sumaba `unidades × envase_unidad` como pérdida. Dos
preguntas sobre la misma fila (*¿se perdió la mercadería?* y *¿se perdió la
caja?*) contestadas por una sola lista.

**La contestó el dueño, y es al revés: la caja se TIRA.** Al pasar la fruta al
cajón grande, la caja de Día se descarta. Así que cobrarla como pérdida
**estaba bien desde siempre** y no hay nada que corregir en
`rechazos_perdidos`.

**Y eso dio vuelta la otra mitad.** El corolario 72 decía que la pata
`liberadas` del stock de cajas valía cero por construcción porque nadie
escribía `movimientos_stock.envase_id`, y lo leía como un agujero — la
columna esperaba un escritor. No esperaba nada: **esperaba sumar cajas que se
fueron a la basura.** El bug no era que faltara cablearla; era que existiera.

Se sacaron las dos el 17/09 (`db/envases_9_*.sql`): la pata, las dos columnas
y sus tres CHECKs. Un camino que nunca se va a recorrer es peor que no
tenerlo — el próximo que lo lea va a creer que falta cablearlo.

### Y el NOMBRE se cerró el 17/09, que era lo último

`reproceso` **entró a `cajas_perdidas`**, el renglón que las nombra, en las
tres listas a la vez (la constante, la consulta de la pantalla y
`db/cajas_7_*.sql`). No movió un peso: ese renglón no entra en ninguna suma y
esa caja ya estaba cobrada adentro de `rechazos_perdidos`.

**La decisión es del dueño y el criterio vale más que el caso**: *"falta el
nombre, no la plata, pero el nombre es lo que la vuelve negociable"*. Mi
argumento para dejarlo afuera era correcto sobre la PLATA —no cambia ningún
total— y contestaba la pregunta equivocada: **una lista que enumera pérdidas
no se evalúa por lo que cobra sino por si se puede llevar a discutir**, y a
la que le falta un tercio de las puertas no se puede.

Lo que sí hubo que probar es que nombrarla no la cobra de nuevo, y eso NO se
ve mirando los dos números: `test_la_caja_del_REPROCESO_ya_esta_cobrada_y_
solo_le_faltaba_el_NOMBRE` compara contra una corrida con `envase_unidad = 0`
—la mercadería sola— y exige que lo que crece al ponerle envase sea
exactamente lo que el renglón nombra.

## LA TABLA, corrida en Frutamax el 16/09 — y está CONCENTRADA

```
Pomelo           5 de 5    · 100%  · $8.000
Zapallito       35 de 43   ·  81%  · $22.750
Limon           25 de 45   ·  56%  · $40.000
Tomate Redondo  35 de 64   ·  55%  · $56.000
Morron Verde     3 de 57   ·   5%  · $1.950
Palta            1 de 19   ·   5%  · $650
Cherry          35 de 0    ·  ---  · $22.750
Mango           10 de 0    ·  ---  · $6.500
(diez articulos en cero)                        total $158.600 en 90 dias
```

**Cuatro artículos se llevan el 80%, y diez están en cero.** Eso confirma la
decisión con el número: un factor global habría repartido el costo de Pomelo
—que pierde el 100% de lo que arma— entre los diez que no pierden ninguna. El
problema es de cuatro artículos, no de la lista de precios.

### Cherry y Mango con `salieron` en 0: era un defecto de la consulta

**`salieron` exigía la caja DECLARADA y `perdidas` la DERIVA de la ficha.** Las
dos mitades del cociente no medían lo mismo.

El mecanismo está en `envase_derivado_de_la_ficha`: una ficha de envase
**VARIABLE** devuelve `(None, None, True)` — *"hay que preguntar"*, porque el
envase lo decide el cajón de esa compra y puede salir descartable. Si nadie
contesta, `lleva_caja_nuestra` queda en NULL y esa guía R no entra en
`salieron`. Pero la ficha SÍ tiene `envase_id`, así que sus cajas perdidas sí
cuentan. **Mango y Cherry son exactamente los dos de envase variable** — los
mismos dos multiformato cuya `contenido_referencia` se vació el 12/09.

Arreglado agregando **`sin_declarar`** a la consulta: ahora el `pct` en NULL se
explica solo en la misma fila. Y con eso viene la advertencia que hay que
leer: **para esas dos filas `perdidas` es un TECHO**, porque el envase se
derivó de la ficha y puede que ese día el cajón viniera chico y saliera
descartable.

Los seis de envase FIJO no están afectados: ahí el server escribe
`lleva_caja_nuestra` siempre, porque se puede derivar.

### Pomelo al 100%: lo contesta una columna, no otra consulta

5 de 5 no distingue "pasa siempre" de "volvió un camión": con denominador 5 no
hay poder para nada. Por eso el renglón de la pantalla trae **`rechazos`** —
de cuántos rechazos DISTINTOS salen esas cajas. Cinco cajas en UN rechazo es un
camión; las mismas cinco en CINCO es algo que pasa todas las semanas, y son dos
conversaciones distintas con el cliente.

## DÓNDE QUEDÓ, y por qué en Cajas y no en otro lado

**La lista va en `/compras/cajas`, pegada al gasto de compra y con la MISMA
ventana.** La razón es del dueño y es la buena: los dos números se leen juntos
—lo que se compró contra lo que se perdió— y con dos recortes distintos la
resta no significaría nada. Lo cuida un test que compara las dos llamadas.

Ordenada **por plata**, que es lo que la vuelve una lista de trabajo: con
cuatro artículos llevándose el 80%, por nombre habría que leerla entera.

**Y sigue habiendo un renglón en Rentabilidad Real**, que es otra lectura: ahí
la caja va al lado de la renta de ESE cliente. Son dos escrituras de la misma
regla que no pueden compartir código —una es SQL de la app, la otra Python
sobre datos ya cargados— así que las ata un test que exige que las TRES listas
de destinos (las dos del código y la del `.sql` que se pega en Supabase) digan
lo mismo.

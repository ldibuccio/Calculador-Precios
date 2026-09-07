# El corte no cerraba el FIFO (07/09/2026)

Lo encontramos tirando del hilo de la guía R176, que decía "Sin lote (se
tomó más de lo que había en el sistema)". El cartel era falso —`sin_lote`
está en CERO en toda la base— pero abajo había dos problemas de verdad, y
son distintos.

## Los números

Medidos el 07/09 con `db/corte_fifo_1_dano_ya_hecho.sql`, sobre las guías R
cargadas desde el corte:

```
guías R desde el corte (todas)     32 guías · 615 bultos · $13.862.224
comieron de CAJA ARMADA            19 guías · 226 bultos ·  $3.572.620
comieron de lote ANTERIOR al corte 18 guías · 260 bultos ·  $4.705.353
consumos sin lote                   0
```

De $13,9M de costo en dos días, **$8,3M salieron de lotes que no
correspondían**. Los dos conjuntos se pisan (una guía puede estar en los
dos), así que $8,3M es el techo, no una suma limpia.

## Problema 1 — El corte cancelaba el neto, no los lotes

El compensatorio del corte lleva el saldo viejo de cada artículo a cero.
Pero **opera sobre el TOTAL y el FIFO razona por LOTE**: la suma de los
restantes puede seguir siendo positiva con el neto en cero. Los lotes
anteriores al corte quedaban vivos y disponibles, y todo lo que se
reprocesara después podía costearse contra mercadería que el corte había
declarado inexistente.

Lo agravante es que **la mitad de la regla ya estaba escrita**:
`crear_reproceso` prohíbe FECHAR una guía R antes del corte
(`ReprocesoAnteriorAlCorte`) y, tres líneas más abajo, leía los lotes sin
ningún piso. Es la misma forma del CHECK que prohibía "ficha sin artículo"
y dejaba pasar el caso espejo.

### Cómo se arregló

El piso de fecha vive en `_entradas_y_salidas_stock_varios` (`app/db.py`),
que es donde se define qué es un lote, y es **asimétrico a propósito**:

- **Las entradas se recortan.** Nada anterior al corte es lote. Más el
  compensatorio, que sale **por TIPO y no por fecha**: está fechado EN el
  corte, así que un piso por fecha lo dejaría adentro.
- **Las salidas NO se recortan.** `lote_posterior_a_la_salida` ya impide
  que una salida vieja alcance un lote nuevo, así que la que se queda sin
  lote cae sola a `sin_lote` y se ve. Sacarlas haría desaparecer de la
  Rentabilidad Real las entregas anteriores al corte: un costo incompleto
  es un dato, una entrega que no aparece es un dato perdido.

Decidido explícitamente que el piso rige **también en Rentabilidad Real**:
lo anterior al corte está declarado no confiable, y costearlo con lotes que
el corte borró es la misma mentira.

## Problema 2 — El FIFO mezcla unidades (PENDIENTE)

**Esto el piso NO lo arregla y sigue vivo.**

`reprocesos.bultos_primera` entra como lote del MISMO `articulo_id` que los
cajones de las compras. Un cajón de 18 kg y una caja de 6 kg son "bultos"
del artículo Perita, y el FIFO los trata como intercambiables. Así, un
reproceso puede tomar **cajas ya armadas como si fueran materia prima**:

```
R171: tomó 30 bultos (cajones de 18 kg) para armar 90 cajas de 6 kg
      De la guía R101    15 bultos · $18.532/bulto
      De la guía R116    15 bultos ·  $6.040/bulto
```

Esos precios son `costo_por_bulto_primera` de otras guías R, no importes de
compra. Y no es un descuido: el docstring de `crear_reproceso` dice textual
*"o del costo de primera si el lote es de otra guía R"*.

La forma real del problema es que **cada tipo de salida come de un tipo de
lote distinto** y el FIFO tiene una sola pila:

| salida | consume | debería salir de |
|---|---|---|
| `reproceso_toma` | `bultos_tomados` | cajones |
| `armado` | cajas tildadas | cajas armadas |
| `merma` / `ajuste` | cualquiera | ambiguo por diseño |

Es E5 (el contador que mezcla cajones y cajas) apareciendo en el costeo.
**Ritmo medido: 19 guías y $3.572.620 en dos días.** No es un caso de
borde.

## Lo que NO se arregla hacia atrás

`reprocesos_consumos` guarda `bultos` y `costo_por_bulto` **congelados**, y
`costo_por_bulto_primera` sale de ahí. Ningún arreglo hacia adelante los
recalcula.

Decisión del 07/09: **las 32 guías no se anulan.** Anular y recargar 32
guías con el depósito trabajando es peor que el error.

Queda escrito, entonces, como sabido:

> **La Rentabilidad Real del 05/09 al 07/09 no es confiable.** Hasta
> $8.300.000 de costo de guías R está atribuido a lotes que no
> correspondían —mercadería anterior al corte, o cajas ya armadas tomadas
> como materia prima—. El costo total del período es el que es; lo que está
> mal es de qué lote salió cada peso, y por lo tanto el margen por artículo
> de esos dos días.

## Antes de mergear el piso: la ola de frenos

Con menos lotes visibles, `bultos_en_los_lotes` baja y reprocesos que hoy
pasan van a levantar `StockInsuficienteParaReproceso`. Eso es el freno
diciendo la verdad, pero le cambia el día al depósito, así que se mide
antes.

La medición exacta la hace `scripts/lotes_vivos_del_fifo.py`, que llama al
`repartir_fifo` de verdad. **Cuando no hay terminal**,
`db/corte_fifo_2_ola_de_frenos.sql` da lo mismo aproximado desde el editor
de Supabase.

### Qué pierde la aproximación

La consulta usa el **neto desde el corte** (entradas − salidas) en vez del
reparto lote por lote. Se puede escribir en SQL y el reparto no, pero pierde
tres cosas:

1. **No respeta el orden de las fechas adentro de la ventana.** Si una
   salida del 05/09 se pasó de lo que había ese día, el exceso es `sin_lote`
   y no descuenta de un lote posterior; el neto sí se lo descuenta.
2. **Por eso subestima**, y siempre en la misma dirección:
   `sum(restantes) = neto + sin_lote`, y `sin_lote >= 0`. Verificado contra
   el `repartir_fifo` real con 4000 casos al azar: la aproximación nunca dio
   más que el disponible verdadero, y la brecha fue exactamente `sin_lote`.
   **Puede marcar un freno de más; nunca puede perderse uno.** Para decidir
   si mergear, ése es el lado correcto del error.
3. **No sabe de mermas dirigidas.** Cambian de qué lote sale cada bulto, no
   cuántos salen, así que el total no se mueve.

### Las dos columnas, y por qué son dos

- `frenan_con_el_piso` es lo que pasa **si se mergea el piso solo**. Cuenta
  las cajas armadas como disponibles, porque el FIFO hoy las cuenta: es la
  mezcla de unidades, que sigue viva.
- `frenan_solo_cajones` es lo que pasaría **si además se arreglara la
  mezcla**. Siempre va a ser mayor o igual.

La diferencia entre las dos es la medida de cuánto está tapando la mezcla de
unidades. Si `frenan_con_el_piso` da chico y `frenan_solo_cajones` da grande,
la lectura no es "el piso es inofensivo": es que **las cajas armadas están
sosteniendo la disponibilidad**, y la ola no desapareció, está esperando al
otro arreglo.

### La columna `solo_cajones` estaba MAL y se sacó (07/09)

La primera versión de `db/corte_fifo_2_ola_de_frenos.sql` traía una columna
`solo_cajones` que pretendía ser "cuántos cajones quedan si no se cuentan
las cajas armadas". Estaba rota, y de la peor manera: **daba cero siempre.**

La cuenta era `sum(bultos) filter (where not caja)`, que suma los cajones
comprados y resta **todas** las salidas — incluido el `armado`, que está en
CAJAS. O sea: restaba cajas de un balde de cajones. Como cada cajón da unas
tres cajas y se entrega casi todo lo que se arma, el número es negativo para
cualquier artículo con volumen normal, y el `greatest(..., 0)` lo apoyaba en
cero.

Reproducido contra el esquema real con 400 cajones comprados, 100 de stock
inicial, 240 tomados, 720 cajas armadas y 700 entregadas:
`400 + 100 − 240 − 700 = −440` → **0**, con **260 cajones reales sin tocar**
en el piso.

**La señal estaba en la forma del resultado, no en los datos.** Un cero
idéntico en los quince artículos —con volúmenes, proveedores y ritmos
distintos— no es un hallazgo: es un piso. Cuando una columna da el mismo
valor extremo en toda la población, lo primero que hay que revisar es la
columna.

Es pariente del error del fixture del 74/26 y del esquema inventado, pero
corrido otra vez de lugar: allá se inventó el dato y el esquema, acá se
mezclaron las UNIDADES adentro de una resta. Y es el mismo problema de fondo
que el sistema tiene vivo —cajones y cajas contados como "bultos"— aparecido
en la herramienta que vino a medirlo.

**La regla que queda**: en una resta, los dos lados tienen que estar en la
misma unidad, y cuando el esquema no la guarda (acá `bultos` es cajón o caja
según de dónde salga la fila) eso hay que verificarlo a mano antes de restar.

## El conteo del piso contra lo que respalda al FIFO

`db/corte_fifo_4_piso_vs_sistema_vs_fifo.sql` pone, por artículo y para los
**sueltos** (los cajones, `conteos_stock.ficha_id IS NULL`): lo contado en el
piso, lo que el sistema creía **en ese mismo instante**, y de qué lado del
corte están las entradas que respaldan eso.

Lo contado y lo del sistema salen de la **misma fila** de `conteos_stock`
—ahí se congela `stock_sistema` al cargar el conteo, y para una porción sin
ficha eso es el total del artículo menos las cajas en fichas, o sea los
sueltos—. No hay dos definiciones que se puedan separar.

La tercera columna **no** es "lo que el FIFO tiene como restante": eso lo
calcula el reparto en Python y no se puede escribir en SQL sin hacer un
segundo FIFO. Son las **entradas**, partidas por el corte, que es lo que
decide el diagnóstico.

Las tres lecturas posibles, y cada una lleva a un lugar distinto:

| contado | sistema | desde el corte | qué es |
|---|---|---|---|
| 66 | 66 | 100 | Todo bien. El piso se puede mergear para ese artículo. |
| 50 | 50 | 0 (y 90 antes) | **El caso malo.** Hay mercadería real y el piso dejaría al FIFO sin lotes. No es un bug: es que esos cajones entraron antes del corte y el corte los declaró inexistentes. |
| 3 | 40 | 0 (y 40 sin fecha) | Fuga: compras recepcionadas con `procesada_el` en NULL. No entran al FIFO de ningún lado, ni antes ni después, y tampoco las habría contado el corte. |

### Dos hipótesis que se pueden cerrar sin datos

- **El `stock_inicial` del corte SÍ entra.** Se escribe con
  `fecha_operacion = corte` (ver `db/corte2_frutamax.sql`), así que el
  `>= corte` lo agarra; el filtro por tipo saca solo `cierre_modelo_viejo`; y
  el CHECK `movimientos_stock_destino_solo_reingreso` obliga a que
  `destino_rechazo` sea NULL en todo lo que no sea un reingreso, así que la
  guarda de rechazos tampoco lo puede excluir. No hay por dónde se pierda.
- **`procesada_el` en NULL sí lo saca**, y en silencio: la comparación de
  fecha da NULL y la compra no cae ni en "desde el corte" ni en "antes". Por
  eso la consulta la cuenta aparte en vez de dejarla desaparecer.

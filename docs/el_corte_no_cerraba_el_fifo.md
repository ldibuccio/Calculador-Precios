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

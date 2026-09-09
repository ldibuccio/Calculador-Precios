# El déficit de la ficha y el "sin lote" del FIFO NO son el mismo número

Del 09/09, y se escribe porque **parecen** el mismo número. Los dos dicen
"salieron cajas que no tienen una guía R detrás", los dos se calculan solos,
y el día que alguien los compare y no coincidan va a "arreglar" uno para que
dé como el otro. Eso sería el corolario 6: una medición mal entendida
decidiendo qué se toca.

**No coinciden, y no tienen por qué.** Medido con las funciones reales sobre
el caso de Limón del 08/09 (compra 40, reingreso 15 a la mañana, armado 35 al
mediodía, tres guías R de 25 tomados/25 primera a la tarde, más un armado de
15 el 07/09):

```
DEFICIT de la ficha (cuenta por ficha, SQL)   ->  25
SIN LOTE del FIFO   (reparto, Python)         ->  15
```

## Los cuatro mecanismos que los separan

Están medidos, no razonados. Cualquiera de los cuatro alcanza para que den
distinto:

1. **El FIFO cuenta el reingreso como lote trabajado y la cuenta por ficha no
   lo ve.** `TIPOS_LOTE_TRABAJADO = ("reproceso", "reingreso_rechazo")`
   (core/stock.py) contra `_SQL_STOCK_PARTIDO`, que **no lee
   `movimientos_stock` en absoluto**. En el caso de arriba el FIFO cubrió 15
   bultos con el reingreso; la ficha no vio ninguno.

   **Éste es el único de los cuatro que es un BUG**, y es el que hay que
   cerrar. Los otros tres son diferencias legítimas de diseño.

2. **El FIFO respeta la cronología; la cuenta por ficha es un neto de la
   ventana.** `lote_posterior_a_la_salida` impide que un lote del 08/09 cubra
   un armado del 07/09 — en el caso de arriba, ese armado de 15 quedó entero
   sin lote. El neto no sabe de orden: suma todo lo producido contra todo lo
   salido.

3. **Los lotes del FIFO NO tienen ficha.** El comentario de la consulta lo
   dice textual: la primera lleva para quién se armó *"(dato de trazabilidad:
   el stock sigue sin dueño)"*. Así que una caja producida para la ficha A
   puede cubrir un armado de la ficha B. La cuenta por ficha, por definición,
   no cruza fichas.

4. **El FIFO consume lotes; la cuenta por ficha no.** El reparto lleva
   `restante` por lote y lo agota; el neto no. En el caso de arriba quedaron
   5 bultos de reproceso sin usar que el neto igual computó.

## Qué se puede testear y qué no

**El test de igualdad no se puede escribir**, y forzarlo a pasar sería
codificar una ficción — la peor clase de test, el que defiende lo contrario
de lo que hay que hacer.

Tampoco vale una desigualdad: no se cumple en ninguna de las dos
direcciones. `déficit ≥ sin_lote` lo rompe el mecanismo 2 (cronología), y
`sin_lote ≥ déficit` lo rompe el 1 (reingreso). Medido: 25 contra 15, con los
dos mecanismos actuando a la vez y en sentidos opuestos.

Lo que sí se podía era **un testigo del mecanismo 1**, el único que era un
bug. Ya cumplió y se borró: ver abajo.

Cerrado el 1, **siguen el 2, el 3 y el 4**. Los números van a seguir sin
coincidir, y va a seguir estando bien.

## El mecanismo 1 quedó CERRADO (09/09)

`_SQL_STOCK_PARTIDO` ganó una tercera pata, `reingresos_ficha`, que llega a
la ficha por `pedido_renglon_id → pedidos_renglones.ficha_id`. Antes de
tocarlo se midió en Frutamax: **5 reingresos, los 5 con ficha alcanzable, 0
huérfanos, 60 bultos, 4 artículos** — no había ningún caso que no se pudiera
reatribuir, y por eso el arreglo no necesitó decidir qué hacer con los que
no llegan a una ficha.

El testigo `test_la_cuenta_por_ficha_TODAVIA_no_lee_movimientos_stock` cayó
al hacer el cambio, como decía su docstring, y **se borró en el mismo
commit**. Lo reemplazan tres tests que fijan lo que ahora tiene que ser
cierto: que la pata está, que el reingreso a *segunda* NO entra (va al pool
de segunda, mismo criterio que `_SQL_SUMAS_STOCK`), y que las TRES patas
recortan por el corte con la misma ventana.

### Y una trampa que la medición destapó

**El total de bultos de reingreso NO es lo que se mueve en pantalla.** Los
sueltos salen de `total − Σ max(saldo, 0)`, así que un reingreso que solo
achica un déficit —la ficha sigue en negativo— **no mueve un solo bulto**:
baja el déficit y nada más.

Medido con el A/B sobre el mismo fixture de Limón:

```
ANTES (dos patas)      ficha: disponibles 0 · deficit 25 · SUELTOS 16
DESPUES (tres patas)   ficha: disponibles 0 · deficit 10 · SUELTOS 16
```

Los sueltos **no se movieron**. Buscar los 60 bultos en la pantalla y no
encontrarlos mandaría a perseguir un bug que no existe — que es el corolario
6 otra vez. Lo que se mueve por ficha es
`max(saldo + reingreso, 0) − max(saldo, 0)`, y lo mide
`db/reingresos_2_delta_por_articulo.sql`.

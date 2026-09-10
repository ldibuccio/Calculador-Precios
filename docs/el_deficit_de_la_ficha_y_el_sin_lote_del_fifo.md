# El déficit de la ficha y el "sin lote" del FIFO NO son el mismo número

> **CINCO mecanismos, no cuatro.** El 5 —la pared del armado— se agregó el
> 10/09 y es el más común hoy. Si llegaste acá porque una ficha CIERRA y el
> FIFO igual marca `sin_lote`, andá directo al 5.

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

## Los mecanismos que los separan (1 a 4 — el 5 va abajo)

Están medidos, no razonados. Cualquiera de los cinco alcanza para que den
distinto:

1. **El FIFO cuenta el reingreso como lote trabajado y la cuenta por ficha no
   lo ve.** `TIPOS_LOTE_TRABAJADO = ("reproceso", "reingreso_rechazo")`
   (core/stock.py) contra `_SQL_STOCK_PARTIDO`, que **no lee
   `movimientos_stock` en absoluto**. En el caso de arriba el FIFO cubrió 15
   bultos con el reingreso; la ficha no vio ninguno.

   **Éste es el único de los cinco que es un BUG**, y es el que hay que
   cerrar. Los otros cuatro son diferencias legítimas de diseño.

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

## 5. LA PARED DEL ARMADO (agregado el 10/09, y faltaba)

**El más común de los cinco hoy, y el único que el sistema ya sabe nombrar.**

Con `ficha_con_envase`, `pasadas_de_lotes` NO le ofrece el cajón a la salida:
devuelve una sola pasada, la de los lotes trabajados, sin pasada de respaldo.
Si esa pasada no alcanza, el bulto queda **sin lote con el cajón entero al
lado** — a propósito, porque el cajón lo va a consumir la guía R que todavía
no está.

Y por eso da un caso que ninguno de los otros cuatro produce: **la cuenta por
ficha cierra exacta, el stock del artículo es POSITIVO, y aun así hay
`sin_lote`.** Medido con `repartir_fifo` y `salidas_para_reparto` reales sobre
un fixture de dos fichas con envase (EJEMPLO inventado, no producción):

```
cajon (guia) 3 · cajas de ayer 6 · R251 de hoy 5 · salen 2 + 5 + 5
  CON envase   -> stock 2 · sin_lote 1 · el cajon queda con restante 3
  SIN envase   -> stock 2 · sin_lote 0   (la pasada de respaldo lo cubre)
```

El control de abajo es la mitad que importa: **la misma escena sin envase da
cero.** Lo que convierte esto en `sin_lote` es la pared, no un faltante.

**Casi siempre viaja con el 3**, y hacen falta los dos: el 3 pone el pool de
cajas corto (los lotes no tienen ficha, así que una ficha se lleva las cajas
producidas para otra) y el 5 impide que el cajón lo tape. Con el 3 solo, el
cajón cubría y no se veía nada.

**No se confunde con el `sin_lote` de verdad, y el sistema ya los separa**:
`atribuir_costos_fifo` etiqueta `falta_cargar_guia_r` cuando
`salida["ficha_con_envase"]` y `sin_lote` cuando no, con la MISMA condición
que arma la pared. El primero es el que alimenta el bloque azul del Remanente
("Armados esperando su guía R"), que además filtra `f.envase_id IS NOT NULL`
en su consulta de candidatos. **Que una porción aparezca en ese bloque azul es
por sí solo el diagnóstico: es este mecanismo y no otro.**

### Lo que el nombre de la etiqueta promete de más

`falta_cargar_guia_r` se decide **solo por `ficha_con_envase`**, no por
haber verificado que falte una guía R. Y el texto que llega a la pantalla
afirma que el papel no está.

Casi siempre es verdad. Pero como los lotes no tienen ficha (mecanismo 3), lo
que falta es una guía R **del artículo**, no de la ficha que se está mirando —
y el que llega desde el extracto de una ficha cuya guía R está cargada lee
"cargá la guía R" sobre un papel que ya cargó. Es la familia del corolario 5:
una rama que AFIRMA algo sobre por qué llegó ahí. El aviso acierta en el
QUÉ HACER y miente en el DÓNDE.

Queda anotado y no resuelto. El arreglo barato no es cambiar la condición
—está bien— sino el texto: decir que falta una guía R **de ese artículo**, y
no dar por sentado que es la de la ficha que el que mira tiene abierta.

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

Cerrado el 1, **siguen el 2, el 3, el 4 y el 5**. Los números van a seguir
sin coincidir, y va a seguir estando bien.

**El 5 no estaba en esta lista hasta el 10/09, y no es que envejeció:** la
pared se mergeó el 08/09 (`b1fafa0`) y este documento se escribió el 09/09,
o sea que ya existía cuando se enumeraron los cuatro. Se enumeraron los
mecanismos que se habían MEDIDO en el caso de Limón, y la pared no jugaba en
ese caso. Es el corolario 20 con otra ropa: enumerar lo que se tenía a mano
en vez del universo, y dejar la lista escrita como si fuera el universo.

La señal para la próxima: **una lista cerrada ("los cuatro mecanismos") es
una afirmación negativa sobre todo lo que no está en ella**, y por eso
necesita más verificación que cada uno de sus ítems. Acá alcanzaba con
grepear `sin_lote` en `core/` el día que se escribió.

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

## Paso 3: la tarjeta del Cotejo para una ficha en déficit

Con el paso 2 el déficit **se ve** —la ficha queda en −10 en vez de
esconderse en los sueltos—, y verse es lo que lo vuelve peligroso: al lado,
en la tarjeta de los sueltos del mismo artículo, hay un botón **"Ajustar a lo
contado"** que baja el total del artículo exactamente en esos 10 bultos. Y
los 10 bultos están en el galpón: lo que falta es la guía R que los explique,
no la mercadería.

### Por qué el aviso de signos opuestos NO alcanzaba

Con las dos porciones contadas, los signos **salen** opuestos: la ficha en
−10 infla los sueltos en 10, así que la tarjeta de sueltos da +10 y la de la
ficha −10, y el aviso viejo dispara. Parece cubierto y no lo está, por dos
razones distintas:

1. **Cuenta la historia equivocada.** "Una guía R que fue a la ficha
   equivocada: la mercadería no falta, cambió de pila" manda a *buscar* una
   guía R entre las cargadas. Acá la guía R **no existe**, y buscarla es la
   tarde perdida.
2. **Se calla justo en el caso peligroso.** Una ficha que nunca se contó no
   genera tarjeta, así que no hay hermana de signo opuesto: la de sueltos
   queda sola, con +10 y el botón naranja de primero. Y con los sueltos
   contados de más (30 sobre 26) los dos signos son negativos y el aviso
   tampoco sale, con el déficit igual de presente.

Por eso el déficit sale de `deficit_de_cajas_por_ficha` —la misma función que
lo calcula para el Remanente y el extracto— y **no** de `sistema_hoy < 0`:
esa derivación solo ve fichas que están en las porciones, y el Remanente
lista "solo lo que tiene MÁS DE CERO", o sea que la ficha en déficit no está
ahí nunca. Sería además la cuarta copia del mismo piso.

### Qué muestra

- **Tarjeta de la ficha**: "Esta ficha está en −10: salieron 10 cajas sin una
  guía R que las produzca… No ajustes el stock: cargá la guía R que faltó."
- **Tarjeta de los sueltos** del mismo artículo, aunque la ficha no se haya
  contado: "…los sueltos se derivan por resta, así que mientras falte esa
  guía R el sistema los cuenta acá: ajustar a lo contado borraría bultos que
  están en el galpón."
- **"Cargar la guía R" de primero** (naranja), y va a
  `/deposito/stock/reproceso`, que es **donde la guía R se carga**. Que sea
  una pantalla de Depósito y el Cotejo de Administración no cambia nada: el
  que mira el Cotejo es el que va a hacer que esa guía R se cargue. Mandarlo
  a Guías R lo deja revisando una lista de las que ya existen buscando una
  que no está — la tarde perdida del punto 1, servida por el propio aviso
  que viene a evitarla. **El primario es el que arregla.**
- **"Ver Guías R" de secundario**: la guía R puede existir y haber ido a otra
  ficha, y ésa es la comprobación. Pero es la comprobación, no el arreglo.
- **Ajustar en segundo plano**, no escondido: puede haber una guía R faltante
  *y* faltante real encima.
- El aviso de déficit **gana** sobre el de signos opuestos y no se muestran
  los dos. Las dos historias no son la misma, y el consejo de la vieja no se
  pierde: "Ver Guías R" sigue estando, un escalón abajo.

### El canario, y el fixture que lo hacía inútil

Los tests se corrieron **con el arreglo roto a propósito**, en seis formas:
sin la rama del déficit (caen 5), sin bajar el ajuste a segundo plano (caen
2), con el déficit mirando solo la ficha y no sumando para los sueltos (caen
3), con el déficit derivado de `sistema_hoy < 0` (caen 5), con el primario
apuntando otra vez a Guías R (caen 2) y con "Cargar la guía R" de secundario
(caen 2).

Ese último **no caía** en la primera versión, y la culpa era del fixture: le
había puesto la ficha en −10 dentro de las porciones del Remanente, que en
producción no la lista. Con la ficha ahí, la derivación equivocada
funcionaba, y el test que existía para fijar de dónde sale el déficit no
miraba nada. Corolario 22 en su forma de siempre: el fixture no se parecía a
producción **justo en el campo que el arreglo tocó**.

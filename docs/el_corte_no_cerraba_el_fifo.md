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

## Dos mediciones que parecían pelearse, y no

El 07/09 quedaron enfrentados dos números: uno decía que 12 de 15 artículos
se quedaban sin lote para un día, y el otro que había cajones entrados desde
el corte en todos. **Los dos eran ciertos: miden cosas distintas.**

| | qué mide | forma |
|---|---|---|
| `caj_desde_corte` (consulta 3 y 4) | cuánto **entró** desde el corte | BRUTO |
| `disp_aprox` (consulta 2) | cuánto **quedó** después de dos días de trabajo | NETO |

El bruto es siempre mayor o igual que el neto. "Entró en todos" y "a 12 no
les alcanza" conviven sin problema si el trabajo de esos dos días se comió
lo que entró — que es exactamente lo que hace un depósito.

### Pero ninguna de las dos es la que usa el freno

`reparto_para_reproceso` tiene un recorte ASIMÉTRICO: **entradas hasta la
fecha del reproceso INCLUSIVE, salidas hasta EL DÍA ANTERIOR.** Contra eso
mide `bultos_en_los_lotes`.

`disp_aprox` se equivoca en las dos puntas, y las dos hacia el mismo lado:

1. **Le falta la compra de la mañana.** Es una foto del sobrante al cerrar el
   día; el reproceso de mañana se mide contra los cajones que entren mañana,
   porque la compra diaria y la toma diaria son el mismo flujo. Medir el
   sobrante de la noche es medir el momento del día en que menos hay.
2. **Resta las salidas del mismo día**, que el freno explícitamente no resta.

Las dos cosas empujan el número para abajo, así que **el 12 está inflado por
construcción**, y no un poco: le falta un día entero de compras y le sobra un
día entero de salidas.

### La medición que sí corresponde es un backtest, no un pronóstico

`db/corte_fifo_5_backtest_del_freno.sql` reproduce la ventana del freno guía
por guía y pregunta: **¿las guías R que YA se cargaron habrían pasado con el
piso puesto?** Contra historia real, no contra un promedio.

Dos detalles que la hacen fiel, y el segundo no es obvio:

- Solo mira entradas y salidas **desde el corte**, que es lo que el piso deja
  ver.
- Excluye las guías **posteriores** a la que se está midiendo (`rid < g.id`).
  Sin eso, cada guía contaría **sus propias cajas** como material disponible
  para sí misma —unas tres veces lo que tomó— y el backtest diría que pasa
  todo. Es la trampa de medir el pasado con los datos de después.

Sigue siendo aproximada en el reparto por lote, y hacia el mismo lado seguro:
bloquea de más, nunca de menos. Si da CERO, el piso entra sin ola.

## El backtest dio 8 de 32, y son dos causas distintas

### Las cuatro del día del corte: artefacto, y NO por la hora de carga

La sospecha razonable era que el reproceso se hubiera cargado antes que el
stock inicial. **No es eso**: `lote_posterior_a_la_salida` compara FECHAS, no
horas — "un lote cargado a la tarde cubre una salida de esa misma mañana"
está escrito así a propósito. El orden de carga no puede explicarlo.

La razón está en un comentario de `stock_deposito_por_articulo`, textual:

> *el conteo físico se toma A LA TARDE del día del corte, así que todo lo del
> día ya está adentro de lo contado*

O sea que **el stock inicial es una foto tomada DESPUÉS del trabajo de ese
día.** Los reprocesos del día del corte consumieron mercadería que la foto ya
no vio: si Mandarina tomó 28 y la foto declaró 20, a la mañana había 48. El
FIFO los mide contra una entrada que es posterior a ellos, y por
construcción no puede cubrirlos.

**Y es la tercera vez que aparece esta misma asimetría.** El pool de segunda
la tiene contemplada; la cuenta por ficha también, "y por lo mismo". El FIFO
es el único que no. No cambia nada para este merge —esas cuatro guías son
historia y están congeladas— pero **va a volver a pasar en el próximo corte**,
así que va al procedimiento.

### Las cuatro del 07/09: al corte le faltó declarar las cajas armadas

Con el piso puesto, un `armado` solo puede consumir cajas declaradas al corte
(guías R `tipo='inicial'`, el PASO 7) o armadas después. Si el armado supera a
las dos, el FIFO —que tiene UNA sola pila— sigue de largo y **se come los
cajones**, dejando sin materia prima al reproceso del día siguiente.

Es la mezcla de unidades mordiendo al piso: no son dos problemas separados,
el segundo es lo que hace que el primero duela.

Verificado con dos artículos idénticos en todo salvo el PASO 7 (40 de stock
inicial, 60 de compra, 30 de toma por día, 250 entregadas cada uno):

| | cajas al corte | come_cajones | el reproceso del 07 |
|---|---|---|---|
| sin PASO 7 | 0 | **+70** | **FRENA** con 0 |
| con PASO 7 | 200 | −130 | pasa con 110 |

`db/corte_fifo_6_las_cajas_se_comen_los_cajones.sql` mide ese `come_cajones`
por artículo: cuántas cajas se entregaron de más sobre las declaradas. Es,
como mínimo, lo que al corte le faltó cargar.

### Por qué la ventana de gracia no es el arreglo

Taparía exactamente el agujero que el piso viene a mostrar. Si al corte le
faltó declarar mercadería, el costo de lo que se reprocese va a salir igual
de lotes que no corresponden — que es el problema original. La gracia hace
que el freno no suene; no hace que el costo sea cierto.

## El mango: el mejor ejemplo de E5, y lo que el mango NO explica

El mango entra en **cajones de 12 unidades** y se arma en **cajas de 10**. De
25 cajones salen 300 unidades = 30 cajas. La guía R177 tomó 25 y produjo 30:
**está bien cargada.** La conversión no es 1 a 1 en ninguna dirección, y por
eso es el caso más claro de que **"bulto" no es una unidad**: el sistema suma
30 cajas y resta 25 cajones como si fueran lo mismo.

### Pero la mezcla NO puede dejar el contador en negativo

Verificado corriendo `stock_deposito_por_articulo` (el código real) contra el
esquema real, con dos artículos idénticos y el mismo ciclo completo —25
cajones, 30 cajas, 30 entregadas— cambiando solo si la compra se cargó:

| | stock del sistema |
|---|---|
| Mango **con** la compra de 25 cargada | **0.0** |
| Mango **sin** la compra | **−25.0** |

**Sobre el ciclo completo la mezcla se cancela exacta y el contador da
cero.** Compra +25, reproceso −25 +30, armado −30 = 0. El error de unidades
está adentro de la cuenta pero se anula al cerrar el ciclo.

Así que el negativo **no** lo produce la mezcla: lo produce una entrada que
falta. Y el −25 del ejemplo es, exactamente, los cajones que se consumieron y
nunca se cargaron.

### Dónde sí muerde la mezcla, y en qué dirección

1. **En el estado intermedio.** Mientras las cajas están armadas y sin
   entregar, el contador dice 30 donde físicamente hay el equivalente a 25
   cajones: lee **20% de MÁS**, no de menos. Es transitorio —se cierra al
   entregar— y no se acumula reproceso a reproceso.
2. **En el FIFO, y ahí no se cancela nunca.** El total puede cerrar en cero y
   aun así cada bulto haber salido del lote equivocado: un reproceso tomando
   cajas ya armadas como materia prima. Eso es lo que medimos el 07/09 —19 de
   32 guías, $3.572.620— y no lo arregla ningún ciclo completo.

**El corolario práctico**: un total que cierra no prueba que las unidades
estén bien. La mezcla se esconde justamente en el número que más se mira.

## El compensatorio NO descuenta dos veces (07/09)

Hipótesis razonable y equivocada: que el compensatorio se hubiera calculado
sobre un saldo que ya tenía restadas las entregas del día del corte, y que el
stock inicial —foto de las 16:30— las restara de nuevo.

No puede pasar, y se ve en el script (`db/corte2_frutamax.sql`, bloque 3):
**el saldo `st` se calcula SIN NINGÚN TOPE DE FECHA.** Suma todas las
compras, todas las salidas, todos los movimientos y todos los reprocesos de
la historia entera. El compensatorio es `-st`.

Por eso cancela la historia COMPLETA, esas 30 cajas incluidas, y el total
después del corte queda igual a la foto y nada más:

    total = st + (−st) + foto = foto

Sea `st` correcto o no, se cancela exacto. **Un compensatorio calculado sobre
el saldo entero es inmune a este error por construcción**, y es justamente
por qué la cuenta 1 no necesita la asimetría que sí necesitan las otras: el
comentario de `_SQL_STOCK_PARTIDO` ya lo decía — *"el total del ARTÍCULO no
tiene este problema porque no se rebasea con una fecha sino con el
compensatorio, que es una FOTO tomada esa misma tarde"*.

La única condición es que el bloque 3 haya corrido **después** del conteo, y
corrió: la foto se carga recién en el paso 5.

### Dónde estaba el doble descuento de verdad

En el piso del FIFO y en `corte_fifo_8`, los dos escritos por mí con `>=`.
Mango lo prueba con los números del galpón: sus tres armados del 05/09
(12:39, 12:42 y 12:44) suman **30 cajas**, y su `faltaban_al_corte` daba
**30**. Con el día del corte afuera, da **cero**.

La diferencia entre los dos mecanismos vale como regla: **un rebase por RESTA
del saldo entero se cancela solo; un rebase por FILTRO DE FECHA no sabe a qué
hora se contó.** El primero es inmune, el segundo hay que partirlo a mano.

## Cómo se evita en el próximo corte

Las dos salidas propuestas empeoran las cosas:

- **Compensatorio con el saldo del día anterior**: rompería la inmunidad de
  arriba. Los movimientos del día del corte dejarían de cancelarse y pasarían
  a jugar contra la foto — que es el doble descuento que hoy no existe.
- **Stock inicial fechado al día siguiente**: dejaría al día del corte sin
  ninguna foto contra la cual medirse, y el FIFO con un día en blanco.

La salida correcta es **contar antes de que arranque el trabajo**, a primera
hora. Ahí el día del corte no tiene movimientos anteriores a la foto y **la
asimetría desaparece en vez de compensarse**, que hoy hay que hacerlo en tres
lugares distintos (pool de segunda, cuenta por ficha y FIFO) y ya nos costó
una copia olvidada.

Si contar a la mañana no se puede, lo segundo mejor es lo que hay ahora: la
regla asimétrica en toda cuenta que lea la foto. Pero entonces **el
procedimiento tiene que listar esas cuentas**, porque la próxima que se
agregue va a nacer sin ella.

## De dónde sale el número de SUELTOS, y por qué no es la mezcla de unidades

Los sueltos de un artículo no se calculan: **se derivan por resta**
(`_stock_de_ficha` con `ficha_id` None):

    sueltos = cuenta 1 (total del artículo) − cuenta 2 (cajas en fichas)

Y las dos tratan el día del corte **distinto**:

| | piso | el día del corte |
|---|---|---|
| cuenta 1 (total) | ninguno — la rebasea el compensatorio | cuenta TODO |
| cuenta 2 (cajas) | asimétrico | solo la foto |

**Lo que una cuenta y la otra no, cae ENTERO en los sueltos.** Un armado del
día del corte resta en la cuenta 1 y no resta en la 2, así que aparece
completo, con signo negativo, en el número de bultos sueltos.

### Lo que quedó aislado corriendo el código real

Dos comparaciones, cada una cambiando UNA sola cosa:

- **Sacar los armados del día del corte**: los sueltos pasan de −12 a +18,
  o sea exactamente los 30 de esos armados. Es el término que los produce.
- **Sacar la mezcla de unidades** (que la guía R tome 25 y arme 25 en vez de
  30): los sueltos **no se mueven**. Cambian el total y las cajas, pero la
  diferencia entre los dos es idéntica.

**La mezcla de unidades NO afecta a los sueltos**, y la razón es que el
término `bultos_primera` está en las DOS cuentas con el mismo signo, así que
se cancela en la resta. Lo que no se cancela es lo que una cuenta ve y la
otra no.

Es la quinta aparición de la asimetría del día del corte, y la primera como
desacuerdo **entre dos cuentas** en vez de adentro de una.

### Lo que NO está probado

Si el compensatorio de ese artículo está bien, la cuenta 1 debería tener esos
armados ya cancelados —el bloque 3 corre después del trabajo del día y resta
el saldo entero—, y entonces el −12 no debería existir. **Cuál de las dos
cosas pasa en producción no lo sabemos**, y no se puede fabricar: es el valor
real del compensatorio de ese artículo.

`corte_fifo_11a` y `11b` lo abren término por término. Las dos son de lectura
y el número que buscamos es `TOTAL_del_articulo − CAJAS_en_fichas`.

## El orden del conteo: cargar las guías R ANTES de contar

Del 07/09, y es la sexta aparición de la misma forma — la primera que no
tiene nada que ver con el corte.

**El conteo físico se toma antes de cargar las guías R del día.** El
`stock_sistema` que se congela en `conteos_stock` no incluye el trabajo de
esa jornada, así que la foto del sistema queda atrasada respecto del piso
por el neto de ese día, y el Cotejo muestra esa diferencia **como si fuera
un faltante**.

**El caso testigo es Tomate Cherry**, medido el 07/09: `dif_cruda` 15,
`trabajo_sin_cargar` 15, `dif_real` **0**. Quince bultos de diferencia falsa
en un solo artículo, que desaparecen enteros al acreditar el trabajo del día.
Es el mejor ejemplo porque no tiene ningún déficit tapado de por medio: la
diferencia es el mecanismo y nada más.

Sobre los 21 artículos contados ese día, **17 dieron `dif_real` = 0**.

Mango sirve para ver la mecánica con los horarios: conteo a las 16:37, guía R
cargada a las 16:51, compra recepcionada a las 17:02.

| | |
|---|---|
| contado (1 suelto + 1 caja) | 2 |
| sistema en ese instante | −12 |
| **diferencia cruda** | **14** |
| trabajo del día sin cargar (R177 +5, compra +10) | 15 |
| **diferencia real** | **−1** |

**Factor de seis sobre un piso de 2.** No es un caso de borde.

### La regla

**Cargar las guías R del día antes de contar, o contar después de
cargarlas.** Cualquiera de los dos órdenes sirve; el que no sirve es contar
en el medio.

Y la razón, que es la que se olvida: un conteo compara dos cosas del mismo
instante **de reloj** y no del mismo instante **de datos**. `stock_sistema`
se congela con lo que estaba escrito, no con lo que había pasado.

### Y no se reconcilia por porción, solo por artículo

Una guía R se parte entre las dos porciones: su `bultos_primera` va a las
cajas de la ficha y su `bultos_tomados` sale de los sueltos. Acreditar el
trabajo pendiente contra una sola porción da cualquier cosa —en Mango, −27
contra 1—; contra el artículo entero da −1.

`db/corte_fifo_13_conteo_vs_trabajo_sin_cargar.sql` hace esa cuenta para
todos los conteos: `dif_cruda`, `trabajo_sin_cargar` y `dif_real`. Si
`dif_real` da cerca de cero en toda la lista, no hay faltante en ningún
artículo y las diferencias históricas grandes son este mecanismo, no datos
rotos.

### Por qué el "1 bulto" de Mango no se puede descomponer

`disponibles = max(saldo, 0)` **por ficha** (`_cajas_por_ficha`). O sea que la
resta `sueltos = total − cajas` **no es lineal**: una ficha con saldo negativo
aporta 0 a `cajas` mientras su negativo sigue adentro de `total`, y ese
déficit cae entero en los sueltos.

A las 16:37 la ficha de Mango tenía las entregas del día tildadas y su guía R
todavía sin cargar, así que su saldo crudo era muy negativo y `cajas` leyó
**0** por el piso. El `−12` de los sueltos no es "cajones que el sistema cree
que hay": es el total menos un cero que tapó un déficit.

Por eso las dos porciones, acreditadas por separado, dan **+28 y −29**, y solo
por artículo dan −1. **Dos errores grandes que se cancelan no son un error
chico**, y el −1 que queda no se puede atribuir a nada: la información que
haría falta —el saldo crudo de la ficha en ese instante— nunca se guardó.

**No es redondeo**: la aritmética da −1,00 exacto y los decimales del mango
(`135,01` y `149,99`) se cancelan entre sí.

Así que Mango no cierra en cero con los datos guardados, y ninguna consulta
lo va a lograr. La única salida es **un conteo nuevo tomado DESPUÉS de cargar
las guías R del día** — la regla nueva —, que da una foto sin déficits
tapados y una diferencia atribuible.

## VIVO (08/09): el botón Ajustar compara sueltos contra el TOTAL del artículo

El Cotejo lista **porciones**: los sueltos de un artículo y las cajas de cada
ficha, cada una con su propio `stock_sistema`. Su `diferencia` es
`contado − sueltos`, que está bien.

Pero el botón "Ajustar" precarga `contado − stock_deposito_de_articulo(id)`, y
esa función devuelve el **TOTAL del artículo** —sueltos más cajas—, no los
sueltos. Verificado con el código real: un limón con 5 sueltos y 30 cajas
armadas da `sueltos = 5` y `total = 35`, así que contando los 5 exactos la
precarga sería **−30**.

O sea: cuando el botón aparece, **propone borrar del total tantos bultos como
cajas armadas tenga el artículo.** Hoy no explotó porque el botón solo se
ofrece cuando los sueltos difieren, y en Mango las cajas eran 0.

Es la tercera vez que aparece la misma forma en este módulo: **dos cuentas
con el mismo nombre y distinto alcance.** El Cotejo dice "stock" y son los
sueltos; Ajustar dice "stock" y es el artículo entero.

### Por qué esto BLOQUEA la columna "Dif. hoy"

El cambio propuesto —que el botón se ofrezca según el desvío contra el stock
actual en vez de contra la foto— **haría aparecer el botón más seguido**,
sobre una precarga que ya está mal. Ampliar la puerta antes de arreglar lo
que hay del otro lado sería empeorarlo.

Orden correcto: primero que `Ajustar` compare porción contra porción, después
la columna y el cambio de gate.

## E5, la dirección inversa: ¿un armado se come cajones?

`corte_fifo_1` midió una dirección: **guías R que consumieron cajas ya
armadas** como si fueran materia prima — 19 de 32 guías en dos días,
$3.572.620. La dirección inversa es la otra mitad del mismo agujero: **un
armado que se costea contra un cajón** en vez de contra una caja.

Las dos salen de lo mismo: el reparto ordena por fecha y **no mira el tipo de
lote**, aunque `TIPOS_LOTE_TRABAJADO` (core/costo_real.py) ya separe materia
prima de producto trabajado y tenga su docstring desde antes.

### Por qué no se puede leer de una tabla

Los consumos de una guía R están **congelados** en `reprocesos_consumos`: por
eso `corte_fifo_1` es una lectura directa. La atribución de un armado **no se
guarda en ningún lado** — `atribuir_costos_fifo` la recalcula cada vez que
alguien abre la Rentabilidad Real. No hay tabla que leer.

Así que `db/e5_2_el_armado_se_come_cajones.sql` **rejuega el FIFO en SQL**:
lotes y salidas, cada uno ordenado por fecha, ocupan tramos del mismo eje de
bultos (sumas corridas), y lo que se solapa entre el tramo de un armado y el
tramo de un lote es lo que ese armado tomó de ese lote. Después se filtra por
tipo: lo que cayó en un lote que **no** es `reproceso` ni `reingreso_rechazo`
es cajón.

### Lo que aproxima, dicho antes de leer el número

Es para el **orden de magnitud**, no para la cifra exacta:

- No tiene el redondeo del código.
- La demanda que la guarda `lote_posterior_a_la_salida` bloquea acá **cae
  afuera** en vez de correrse al lote siguiente. Subestima.
- `plata` ignora los lotes sin costo, y por eso al lado va `sin_costo`: sin
  esa columna, "poca plata" y "muchos bultos sin precio" se ven igual.

El piso del corte está puesto con la misma asimetría que producción
(`stock_inicial` y guías R `tipo='inicial'` del día del corte entran; todo lo
demás de ese día, no), y los pedidos se filtran con el mismo `DISTINCT ON`
que `_SQL_SALIDAS_STOCK`, para que un pedido corregido no cuente dos veces.

### Cómo se verificó

Contra el esquema real (`db/esquema_completo.sql` en un Postgres 16
descartable), con un fixture de tres artículos de nombre inventado que
**hace fallar la versión equivocada**:

- **EJEMPLO Uno** — hay cajas de sobra y el armado llega después: aporta 0.
- **EJEMPLO Dos** — hay 10 cajas disponibles y el armado igual se come el
  cajón, porque el cajón es más viejo. **Es el caso de ORDEN, no de
  agotamiento**, y es el que un saldo corrido de la pila de cajas —la primera
  forma que le di a esta consulta— no ve: para ese modelo el saldo nunca baja
  de cero. Aporta 10.
- **EJEMPLO Tres** — las cajas se agotan y el armado desborda al cajón.
  Aporta 7.

Resultado: `cajon = 17`, `plata = 1000.00`, `sin_costo = 7`, `armado = 32`,
los cuatro exactos. Dos canarios más: con `>=` en el piso (la regla vieja) el
número se mueve a 22, así que el piso está de verdad ejercido; y contra una
base vacía devuelve **una fila de ceros**, no una pantalla vacía.

Los datos de prueba se borraron al terminar.

## La caja de Día en el piso de Mango: el 0 del Cotejo puede ser un negativo

Del 08/09. Los cajones de Mango cerraron: 2 + 16 + 10 − 25 = **3**, el sistema
dice 3, el depósito contó 1. Es un error de conteo de 2 cajones y no hay
ningún −2 que explicar (queda **bajada** la hipótesis de la guía R con la
ficha cambiada, y cerrado el "Sin explicar" del 05/09 y 06/09).

Lo que queda abierto es otra cosa: **1 caja de Día contada en el piso contra
0 en el sistema.**

Y hay un detalle del Cotejo que hay que tener a mano antes de leer ese 0:
`_cajas_por_ficha` devuelve `disponibles = max(saldo, 0)`. **Un saldo
negativo y un saldo cero se ven exactamente igual en la pantalla.** Es la
misma no-linealidad del piso del corolario 7, un nivel más arriba: acá no
ensucia una resta, esconde un signo.

Por eso `db/mango_1_cajas_de_dia_y_pedido_completo.sql` devuelve el
**saldo sin piso**, y al lado las tres columnas que separan las causas
posibles de esa caja:

| Lo que devuelve | Qué significa |
|---|---|
| `reng_cortos > 0` | Se armó menos de lo pedido: el pedido **no** salió completo y la caja es lo que no se despachó. |
| `reng_sin_armar > 0` | Hay renglón sin tildar: no descontó stock, y la caja está esperando. |
| `saldo_sin_piso < 0` | Se armó **más** de lo producido: la guía R declaró de menos, y la caja contada es real pero el sistema no la tiene. |
| Todo en cero y `saldo_sin_piso = 0` | El pedido salió completo: la caja no viene de este pedido — o es de otra ficha, o la guía R produjo una más de las declaradas. |

Verificada contra el esquema real con un fixture de nombres inventados
(`EJEMPLO Mango`, `EJEMPLO Caja Dia`) que recorre los cuatro casos: 30 de 30
da saldo 0; 29 de 30 da saldo 1 y `reng_cortos` 1; el renglón sin tildar da
`reng_sin_armar` 1 y 30 bultos; y produciendo 28 contra 30 armados da
**−2**, que es justo lo que el Cotejo mostraría como 0. Con el artículo sin
movimientos devuelve una fila de ceros, no una pantalla vacía. Los datos de
prueba se borraron.

**Esto no toca E5.** La fuga se midió con 19 guías, 226 bultos y $3.572.620
en dos días; Mango era el ejemplo de cómo se ve el problema, no la prueba de
que existe.

## E5 paso 2: el backtest del freno con el filtro puesto

Antes de tocar `crear_reproceso` hay que saber a cuánta gente traba. Con A,
una guía R solo puede costearse contra **materia prima**: los lotes de
`TIPOS_LOTE_TRABAJADO` (`reproceso`, `reingreso_rechazo`) dejan de estar
disponibles para ella. El freno mide contra la **suma de los restantes**
(`bultos_en_los_lotes`, core/stock.py), así que sacar lotes de la lista baja
ese número y puede empezar a trabar guías que hoy pasan.

`db/e5_3_backtest_del_freno_con_filtro.sql` lo mide sobre las guías R ya
cargadas, con la ventana exacta del freno (`reparto_para_reproceso`:
entradas hasta la fecha inclusive, salidas hasta el día anterior, y sin las
guías R posteriores, que cuando ésa se cargó no existían).

Devuelve cuatro números en una fila: `guias`, `frenan_hoy`, `frenan_con_a` y
`sin_cubrir` (los bultos que la materia prima no llega a cubrir).

### Cómo calcula los restantes, y por qué no es `entradas − salidas`

`corte_fifo_5b` usaba `greatest(entradas − salidas, 0)`. Eso es exacto
mientras se miren TODOS los lotes —la suma de los restantes de todos es el
neto—, pero **deja de serlo apenas se filtra por tipo**: hay que saber
cuáles lotes se comió la demanda, no cuánta demanda hubo.

Así que se rejuega el FIFO con la misma forma que `e5_2`: los lotes ordenados
por fecha ocupan tramos del eje, la demanda consume el prefijo `[0, D)`, y el
restante de cada lote es `max(0, fin − max(ini, D))`. Sumando sobre todos da
`max(0, S − D)` —o sea la fórmula vieja, que por eso sigue de control en
`frenan_hoy`— y sumando solo sobre los NO trabajados da el número con A.

**Sobreestima**, y va dicho: la demanda que `lote_posterior_a_la_salida`
bloquea acá consume igual, así que deja menos restante del que habría y
puede reportar más frenos de los reales. Para decidir si A se puede mergear,
errar por el lado pesimista es el lado correcto.

Y un detalle que ahorra media consulta: las guías R normales se sacan de la
misma lista de movimientos, por `bultos_tomados > 0`. No es una
aproximación — el CHECK `reprocesos_bultos_tomados_check` obliga a que
`inicial` tome exactamente 0 y `normal` tome más de 0.

### Cómo se verificó

Contra el esquema real, con un fixture de dos artículos de nombre inventado
que **hace fallar la versión sin filtro**:

- **EJEMPLO Cuatro** — compra 10 el 01/09; la guía R del 01/09 toma esos 10
  y produce 10 cajas; la guía R del 02/09 toma 10 más. Hoy no frena, porque
  se come las cajas de la anterior. **Con A frena**: materia prima
  disponible, cero.
- **EJEMPLO Cinco** — 100 cajones de sobra: no frena de ninguna de las dos
  formas.

Da `guias = 3`, `frenan_hoy = 0`, `frenan_con_a = 1`, `sin_cubrir = 10`.
Tres canarios: con el filtro anulado `frenan_con_a` vuelve a 0 (o sea que el
filtro es lo que produce el número); con una base vacía devuelve una fila de
ceros; y **con una compra fechada el día del corte, cambiar el piso a `>=`
se lleva el freno puesto (1 → 0)** — que es el canario que pide el corolario
12. Los datos de prueba se borraron.

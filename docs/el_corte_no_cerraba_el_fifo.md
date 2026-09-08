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
comieron de CAJA ARMADA            19 guías · 226 bultos ·  $3.572.620   <-- MAL, ver abajo
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
**Ritmo medido: 10 guías y $2.798.438,92 en DOS DÍAS (06 y 07/09).**
Corregido dos veces el 08/09 y la segunda por mi culpa: acá decía 19 guías
y $3.572.620 "en dos días" (contaba el día del corte), lo corregí a
"$2.798.438,92 desde el 31/08" **asumiendo la fecha de corte en vez de
leerla**, y el corte de Frutamax es el **05/09**. Como `e5_1` filtra
`> corte`, el período real son 06 y 07/09: dos días. El ritmo diario es el
alto, no el bajo.

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
   20 guías, $2.798.438,92 (Frutamax, corte 05/09, 06 y 07/09)— y no lo
   arregla ningún ciclo completo.

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
armadas** como si fueran materia prima — 10 de 20 guías posteriores al
corte, $2.798.438,92 en dos días (06 y 07/09). La dirección inversa es la otra mitad
del mismo agujero: **un
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

**Esto no toca E5.** La fuga se midió con 10 guías, 134 bultos y
$2.798.438,92 en dos días (06 y 07/09); Mango era el ejemplo de
cómo se ve el problema, no la prueba de
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

## El alcance de E5 por artículo, y una colisión de nombres que había que sacar

`db/e5_1_alcance_de_la_mezcla.sql` llamaba **A** y **B** a dos cosas —
"tamaños de cajón mezclados" y "cajones y cajas conviviendo"— y desde que
las opciones de arreglo se llaman A (el reproceso no consume lotes
trabajados) y B (dos pilas separadas), el mismo archivo decía A y B con otro
significado.

Es la forma de siempre: **dos cosas distintas con el mismo nombre**, esta
vez sin ningún daño en las cuentas y con todo el daño posible en la próxima
lectura. Se separó en dos archivos:

- **`db/remanente_1_tamanos_y_pilas.sql`** (el viejo, renombrado): las dos
  condiciones estructurales, ahora numeradas 1 y 2, sin letras. Es lo que
  alimenta la decisión del Remanente, no la de E5.
- **`db/e5_1_alcance_por_articulo.sql`** (nuevo): el lado de **A**, por
  artículo.

### Por qué el lado de A es exacto y el de B no

No es una diferencia de esfuerzo, es de dónde vive el dato:

- Lo que consumió una guía R está **congelado** en `reprocesos_consumos`.
  `e5_1` lo lee y suma: exacto, sin rejugar nada.
- Lo que consumió un armado **no se guarda**. `e5_2` tiene que rejugar el
  FIFO y por eso aproxima.

Así que `e5_1` da la lista de artículos donde A muerde, con su plata, y
`e5_2` da el total del otro lado. Juntos dicen si A sola alcanza.

`sin_costo` va al lado de `plata` por lo mismo de siempre: un lote sin costo
no suma pesos y sí suma bultos, y sin esa columna "poca plata" y "muchos
bultos sin precio" se ven igual.

### Cómo se verificó

Contra el esquema real, con dos artículos de nombre inventado. **EJEMPLO
Seis** tiene una guía R que consumió 6 bultos de una compra (no cuentan), 4
de otra guía R a $100 (cuentan) y 2 de un reingreso sin costo (cuentan como
bultos, no como plata). **EJEMPLO Siete** consumió solo compra y no tiene
que aparecer.

Da `guias_r = 1`, `bultos_de_caja = 6`, `plata = 400.00`, `sin_costo = 2`, y
Siete efectivamente no aparece. Canario: agregando `'compra'` a la lista de
orígenes, Seis salta a 12 bultos y $700 y Siete entra en el listado — o sea
que el filtro es lo que produce el número. Con una base vacía devuelve una
fila de ceros. Los datos de prueba se borraron.

## Los 494: separar "se fue al cajón teniendo caja" de "no tenía otra opción"

`e5_2` sobre **Frutamax (corte 05/09, `> corte`: 06 y 07/09)** dio **`cajon`
494 de `armado` 765 — el 65%— y $14.618.218,30**, con `sin_costo` 0. Cuatro veces la fuga que veníamos
midiendo del lado del reproceso ($2.798.438,92 ya corregido), y por el lado
que ninguna de
las dos direcciones tapaba.

Pero **el 65% crudo no es todo problema**, y hay que decirlo antes de
decidir nada con él. Hay artículos que **no se reprocesan nunca** —el
docstring de `_cajas_por_ficha` los nombra: manzana, pera, arándano, salen
en el envase que vienen—. Ahí no hay ninguna caja que el FIFO podría haber
elegido: el armado sale del cajón porque es lo único que existe, y está bien
atribuido. Contarlos como fuga sería exactamente el corolario 6: una
medición que decide qué se arregla, con un número que mezcla dos cosas.

`db/e5_4_cajon_con_caja_disponible.sql` parte el número en dos:

- **`mal`** — el armado que se fue al cajón **teniendo caja disponible**.
  Es lo que B arregla, y lo único que cuenta como fuga.
- **`sin_opcion`** — el resto. No había caja: ni B ni A lo cambian.

### La definición de "disponible", y el error que casi se me pasa

Disponible = lotes trabajados con fecha ≤ la del armado que quedaron **sin
usar DESPUÉS de esa salida**.

El "después" no es un detalle. La primera versión miraba el restante **antes**
de la salida, y eso cuenta como "disponibles" **las mismas cajas que esa
salida se estaba comiendo**: el caso de agotamiento —se come las 5 cajas que
había y desborda 7 al cajón— daba `mal = 5` cuando la respuesta correcta es
0, porque esas 5 no estaban disponibles *en lugar* del cajón, ya se habían
usado. Con el restante posterior da 0.

Es la misma familia del corolario 13: la fórmula no se rompe, contesta otra
pregunta. Acá se agarró porque el fixture tenía el caso de agotamiento
separado del de orden y los números esperados estaban escritos antes de
correr.

### Cómo se verificó

Tres artículos de nombre inventado, uno por caso:

- **EJEMPLO Ocho** — nunca se reprocesa. Compra 20, armado 10. Todo
  `sin_opcion`.
- **EJEMPLO Nueve** — hay 10 cajas y el cajón es más viejo: el FIFO va al
  cajón igual. 10 a `mal`, $1000.
- **EJEMPLO Diez** — 5 cajas de la foto y un armado de 12: se come las 5 y
  desborda 7. `sin_opcion`, no `mal`.

Da `cajon 27`, `mal 10`, `sin_opcion 17`, `plata_mal 1000.00`. Y el control
que más vale: **`e5_2`, que es una consulta escrita aparte, da `cajon` 27
sobre el mismo fixture** — dos caminos distintos al mismo número. Con base
vacía devuelve ceros (no NULLs), y con una compra fechada el día del corte
el canario del corolario 12 muerde: pasando el piso a `>=`, 27 → 32 y
`mal` 10 → 15. Los datos de prueba se borraron.

La plata de `mal` se prorratea con el costo promedio del cajón de cada
salida: el `min()` no cae sobre lotes concretos, así que no hay costo exacto
que sumar.

## Los $3.572.620 y los $2.798.438,92 no son el mismo número (08/09)

`e5_1` dio **$2.798.438,92 / 134 bultos / 10 guías** donde yo había dicho que
tenía que dar los $3.572.620 / 226 bultos / 19 guías **o más**, porque cubre
los mismos días y sale de una tabla congelada. Dio menos. **Esa afirmación
mía era falsa**, y de las dos consultas al menos una está mal.

Comparadas línea por línea, `corte_fifo_1` y `e5_1` **no hacen la misma
pregunta**, y difieren en exactamente dos cosas:

| | `corte_fifo_1` | `e5_1` |
|---|---|---|
| Piso | `fecha_operacion >= corte` | `> corte` (estricto) |
| Orígenes | solo `reproceso` | `reproceso` **y** `reingreso_rechazo` |

Las dos diferencias empujan en direcciones opuestas, así que el neto podía
dar para cualquier lado. `db/e5_5_por_que_no_dan_igual.sql` las separa en
una fila cada una.

**Y hay un tercer conteo de guías**: `corte_fifo_1` decía 32, `e5_3` dice 20.
La diferencia es el mismo `>=`.

### Un error de documentación que sí puedo afirmar ya

El doc dice, en cuatro lugares, *"19 de 32 guías R **en dos días**"*. La
consulta no mide dos días: mide `rp.fecha_operacion >= corte`, y el corte de
Frutamax es el **05/09**, así que son 05, 06 y 07/09 — **tres** días
(la última guía R es del 07/09). El "en dos días" fue una glosa al contar el
resultado, no
lo que la consulta preguntó, y viajó a `app/db.py:7020` y a la decisión de no
anular las 32 guías. El ritmo real por día es más bajo que el que citamos.

### La identidad que cierra el caso

En el fixture, `fila 1 − fila 3 = fila 2 − fila 4` (900 − 700 = 260 − 60 =
200): sacando el día del corte de un lado y los reingresos del otro, las dos
consultas coinciden. **Si esa identidad se cumple sobre producción, la
brecha está explicada entera por esas dos causas.** Si no se cumple, hay una
tercera y hay que buscarla.

Si la fila 3 se lleva los $774.181,08 y los 92 bultos que faltan, esto es la
**octava aparición** de la asimetría del día del corte — y la segunda dentro
de una consulta de diagnóstico, que es justo lo que el corolario 6 dice que
es más caro que un bug: un número con autoridad de medición que decide qué
se arregla. Esta vez decidió que la fuga del lado del reproceso valía $3,5M.

### Cómo se verificó

Cuatro guías R de un artículo inventado: una **el día del corte** que comió
caja armada (7 bultos, $700), una posterior que comió caja armada (4, $200),
una posterior que comió un **reingreso** (3, $60) y una posterior que solo
comió compra (no entra en ninguna de las dos). Las seis filas dan exactamente
lo esperado y la identidad se cumple. Los datos de prueba se borraron.

### Cerrado (08/09): fue el día del corte, entero

```
1 corte_fifo_1 (>=)   19 guías · 226.00 · $3.572.620,02
2 e5_1 (>)            10 guías · 134.00 · $2.798.438,92
3 día del corte        9 guías ·  92.00 ·   $774.181,10
4 reingreso_rechazo    0       ·   0.00 ·         $0,00
5 todas, >= corte     32 guías · 615.00 · $13.862.224,25
6 todas, > corte      20 guías · 448.00 · $10.489.043,15
```

`3.572.620,02 − 774.181,10 = 2.798.438,92`, y la fila 4 en cero: **la única
causa fue el día del corte, no hay tercera.** Los tres conteos de guías
también cierran: 32 con `>=`, 20 con `>` (los mismos 20 de `e5_3`), y 12 son
del día del corte.

**El número bueno del lado del reproceso es $2.798.438,92, no $3.572.620.**
Corregido en `app/db.py` y en las cinco citas del doc.

Es la **octava aparición** de la asimetría del día del corte y la peor de
las ocho: las anteriores ensuciaban una cuenta, ésta **decidió cuánto valía
el problema**. El $3,5M se citó todo el día como el tamaño de la fuga, entró
en un docstring de producción, y sostuvo la decisión de no anular las 32
guías. El canario del corolario 12 —correr también con la regla vieja y
exigir que el número se mueva— es exactamente lo que lo habría atajado el
mismo día.

Y la glosa: *"en dos días"* nunca lo midió nadie. La consulta dice `>=
corte`, que sobre Frutamax son tres días (05 al 07/09).

**Y la corrección introdujo otro número mal, por la misma causa.** Al
corregir escribí "todo desde el 31/08": la fecha no la leí de la base, la
asumí del `insert` que trae la migración. El corte de Frutamax se movió al
05/09 en algún momento; el de Palmala sigue en 31/08. Ver el corolario 18. Un período inventado al contar un resultado, repetido cinco veces
hasta volverse un hecho.

## El veredicto: A y B van juntas

Todo lo de abajo es **FRUTAMAX, corte 05/09, recorte `> corte`, o sea 06 y
07/09** — dos días. La ficha va pegada a los números y no en un párrafo
aparte: ver el corolario 19.

```
Lado del reproceso (A)   $2.798.438,92   ← e5_1, exacto
Lado del armado (B)      $9.658.218,30   ← e5_4, aproximado por lo bajo
```

`e5_4` dio `cajon 494` (reproduce `e5_2`), `mal 359`, `sin_opcion 135`.
**El 73% del cajón que se comieron los armados tenía caja disponible**: no
es la operación normal del galpón, que es lo que había que descartar.

B es **3,5 veces** A. A sola arregla el 22% y deja el resto abierto con la
sensación de estar cerrado.

## Antes de mergear B: cuánto se mueve la rentabilidad ya reportada

Condición del dueño, y va **antes** del merge y no en el mismo commit: si
mueve mucho, avisa al galpón primero. `db/e5_6a/6b/6c` lo miden **por
artículo y con signo**, porque un total de $9M no dice a quién avisarle y
porque no es lo mismo que la rentabilidad histórica suba o baje.

- `delta > 0` → con B el costo atribuido SUBE, o sea **la rentabilidad que
  ya se reportó BAJA**.
- `delta < 0` → al revés.

Va en tres bloques con una tabla de trabajo real (`e5_mov`), como el
backtest del freno: entero no entra en 2500, y las CTE no sobreviven de una
sentencia a la otra en el editor. El bloque C la borra.

### Dos aproximaciones, y las dos por lo bajo

1. La de siempre: la demanda que `lote_posterior_a_la_salida` bloquea acá
   consume igual.
2. Nueva: los bultos que cambian de pila se cuestan con el **promedio** de
   cada lado, no lote por lote. El `min()` de `e5_4` no cae sobre lotes
   concretos, así que no hay un costo exacto que sumar, y hacerlo lote por
   lote pedía una ventana más adentro que no entraba.

Sirve para decidir si hay que avisar, no para cerrar un balance.

### Cómo se verificó

Tres artículos inventados, dos de ellos con el mismo desvío de bultos y
signos opuestos a propósito:

- **EJEMPLO Doce** — la caja armada sale más cara que el cajón ($150 contra
  $100): con B el costo sube, `delta +500`.
- **EJEMPLO Trece** — la caja armada sale más barata ($50 contra $200): con
  B el costo baja, `delta −1500`.
- **EJEMPLO Catorce** — no se reprocesa nunca: no cambia nada y no aparece.

`TOTAL` da 20 bultos, $3.000 de costo hoy y `delta −1000`. Tres canarios:
anulando la preferencia el `delta` vuelve a 0 en las tres filas (o sea que
la preferencia es lo que produce el número); base vacía devuelve una fila
de ceros; y **el canario del corte muerde** — con una compra fechada el
31/08 y el piso en `>=`, el costo de Doce pasa de $1.000 a $70 y su delta de
+500 a +1430.

Ese último no mordía en el primer intento: el fixture no tenía nada fechado
el día del corte y los dos números daban iguales. **Un canario que no se
mueve no dice que el piso esté bien; dice que no lo probaste** — el
corolario 12 pide que el número SE MUEVA, y hubo que darle con qué.

## Todo esto se midió contra UNA base, y el deploy sale en las dos

Frutamax y Palmala. `frenan_con_a = 0` —lo que decidió que A se mergeaba sin
avisar al galpón— salió de Frutamax nomás. Antes de mergear la pieza 3 hay
que correr en Palmala: `e5_3` (¿A traba guías reales ahí?), `e5_4` (¿B mueve
plata ahí, o es cero?) y `e5_6` (¿cuánto se mueve su rentabilidad?).

### El agujero que había que tapar antes

Todas las consultas de E5 leen `corte_modelo where id=1`. Del esquema se
puede afirmar dos cosas y una tercera no:

1. **No puede haber ambigüedad de fila.** `id integer primary key check (id
   = 1)` deja como mucho una, así que "otro corte" solo puede significar
   otra FECHA, nunca otra fila.
2. **La fila la crea la migración** (`agregar_corte_y_stock_inicial.sql`) con
   `'2026-08-31'` escrito a mano. Si Palmala corrió esa migración y nadie
   editó la fecha, es la misma.
3. **Si corrió esa migración y si la fecha sigue igual, no lo puedo saber
   desde acá**: es un dato, y el SQL contra las bases reales no lo corro yo.

Y si la fila NO estuviera, el resultado era el peor posible: el CTE sale
vacío, el cross join deja todo en cero, y `e5_3`/`e5_4` devuelven **una fila
de ceros que se lee igual que "acá no hay problema"**. Verificado corriendo
las consultas con la fila borrada.

Lo agravante es que **producción sí tiene la guarda**: `_fecha_corte` levanta
un `RuntimeError` que dice "la base quedó a medio configurar". El código
grita y la medición contestaba cero.

Arreglado en dos partes:

- **`db/e5_0_contra_que_base_mido.sql`** — se corre PRIMERO en las dos y se
  comparan. Trae `filas_corte`, `corte`, y los conteos post-corte. Va sin
  `FROM` a propósito, así la fila vuelve siempre. Y trae `ultima_guia_r`, que
  **no depende del corte**: es el testigo independiente. Corte en NULL con
  guías R recientes al lado es una contradicción visible en la misma fila.
- **Las seis consultas de E5 traen ahora una columna `corte`**, con
  `(select f0 from c0)` y no un cross join — el cross join con la fila
  faltante dejaría la consulta sin filas.

Verificado en los tres escenarios: fila normal, fila borrada (`corte` NULL,
todo en cero, `ultima_guia_r` delatando) y fecha distinta (los conteos caen a
cero y `ultima_guia_r` sigue mostrando actividad). Y los cuatro fixtures
anteriores siguen dando los mismos números con la columna puesta.

## Palmala: E5 no existe ahí, y por qué eso hay que confirmarlo y no suponerlo

`e5_0` en las dos, 08/09:

```
FRUTAMAX  corte 2026-09-05 · post 20 · el día 12 · inicial 8 · compras 24 · armados 60 · última guía R 07/09
PALMALA   corte 2026-08-31 · post  0 · el día  0 · inicial 0 · compras 36 · armados  1 · última guía R NULL
```

Palmala **no tiene una sola guía R**. Sin reprocesos no hay cajas armadas, y
sin cajas armadas no hay dos pilas. Correr `e5_3` o `e5_4` ahí daría ceros, y
esos ceros no significarían nada: son el mismo cero que da una base sin
configurar.

### Pero sí hay un camino a la pila trabajada sin ningún reproceso

`TIPOS_LOTE_TRABAJADO` son **dos**: `reproceso` y `reingreso_rechazo`. El
reingreso por rechazo nace en `movimientos_stock`, no en `reprocesos` —
salió armado y volvió—, y entra al FIFO como lote con
`tipo_lote = 'reingreso_rechazo'`. **Un artículo que nunca se reprocesó puede
tener pila trabajada.**

Con un matiz que está en la consulta de entradas: solo cuenta el que vuelve
al stock normal (`destino_rechazo` NULL o `'stock'`). El que se manda a
segunda o a reproceso sale del circuito y su costo ya se imputó como pérdida.

Por eso `db/e5_0b_pila_trabajada_sin_guias_r.sql`, que se corre en las dos.
Verificado contra el esquema real con una base de cero guías R y dos
reingresos —uno a stock y otro a segunda—: cuenta 1 como lote, 1 fuera del
circuito y 2 históricos.

### Qué implica para el deploy

- **A** solo actúa sobre `crear_reproceso`. Sin guías R es inerte en Palmala,
  hoy y hasta que Palmala cargue la primera. El día que la cargue, la pared
  va a estar puesta — que es lo que se quiere.
- **B** actúa sobre los armados. Si Palmala tiene reingresos que volvieron a
  stock, B **sí** cambia la atribución ahí, aunque no haya un solo reproceso.
  Con 1 armado post-corte el movimiento va a ser chico, pero "chico" no es
  "cero" y se mide antes, no después.

## El delta de −$4,4M no se puede usar todavía, y la culpa es mía

`e5_6b` sobre **Frutamax (corte 05/09, `> corte`: 06 y 07/09)** dio 359
bultos, `costo_hoy $9.658.218,30`, `delta −$4.391.314,26` — o sea −45%: con B
los costos de los armados bajan y la rentabilidad ya reportada sube.

**Pero le faltaba la columna de honestidad, y justo a la consulta que decide
qué se le dice al galpón.** `e5_1` y `e5_2` traen `sin_costo`; `e5_4` y
`e5_6b` no lo traían. Y acá muerde más que en ninguna:

`costo_por_bulto_primera` es **NULL cuando el costo de la guía R quedó
incompleto** (lo dice el comentario del esquema). En `e5_6b`,
`pdisp = sum(rest*cb) filter (where trab)` **saltea los NULL**, pero `disp`
cuenta esos bultos igual. O sea que una caja sin costo entra al promedio
**como si fuera gratis**, y eso empuja el delta hacia **NEGATIVO** — que es
exactamente la dirección del resultado que estaba por llevarse al galpón.

Arreglado: `e5_6b` trae ahora `caja_s_costo`, `cajon_s_costo`, y los dos
pesos por bulto `x_hoy` y `x_conb`. **Con `caja_s_costo > 0` el delta está
sesgado y no se usa.**

### Los tres mecanismos, separados en un fixture

Un artículo por mecanismo, contra el esquema real:

| Artículo (inventado) | Qué tiene | `x_hoy` | `x_conb` | `delta` | `caja_s_costo` |
|---|---|---|---|---|---|
| `EJEMPLO Pasa Derecho` | guía R toma 10, produce 10, sin merma ni segunda | 100 | 100 | **0.00** | 0 |
| `EJEMPLO Con Merma` | toma 10, produce 7 | 100 | 142,86 | **+300,02** | 0 |
| `EJEMPLO Caja Sin Costo` | `costo_por_bulto_primera` NULL | 100 | 0 | **−1000** | 10 |

**El `delta = 0.00` con bultos > 0 es un resultado real, no un artefacto**,
y tiene un mecanismo concreto: una guía R sin merma ni segunda hace
`costo_por_bulto_primera = costo_total / bultos_primera = cb del cajón`. El
costo **pasa derecho** y B mueve la atribución sin mover un peso. Se
distingue del artefacto mirando `x_hoy` contra `x_conb`: iguales = real;
`x_conb` en 0 con `caja_s_costo > 0` = sin costo cargado.

**El signo positivo también tiene mecanismo, y es el mismo que explica los
dos**: `TODO el costo va a la primera` (segunda y merma valen cero), así que
una guía R con merma entrega una caja más cara que el cajón en la proporción
`tomados / primera`. Eso empuja el delta **para arriba** siempre. Contra eso
juega la diferencia de precio entre el cajón que el armado come hoy y el
lote de caja disponible, que son de días distintos y en fruta se mueve
fuerte. **Donde manda el markup del reproceso, el delta es positivo; donde
manda la caída de precio entre días, negativo.** Una sola explicación para
los dos signos, y ninguno de los dos es un error.

Y el TOTAL del fixture lo muestra crudo: −699,98, de los cuales −1000 son del
artículo sin costo. Sin `caja_s_costo` al lado, ese −$700 se lee como un
ahorro real.

## `corte_fifo_15` no encontró nada, y eso es un resultado

Corrida en Frutamax el 08/09 contra Palta +2, Zapallito +1 y Perita +1:
**CAUSAS ENCONTRADAS EN TOTAL = 0.** Ninguna de las cuatro que propuse
—compra sin recepcionar, rechazo fuera del stock normal, merma o ajuste,
sistema con decimales— explica esos tres desvíos.

Que el cero se vea es el corolario de diseño funcionando: la consulta
devuelve **conteos y no una lista**, así que "no hay causas" y "no corrió"
no son la misma pantalla. Con una lista de ofensores, este resultado habría
sido indistinguible de un error de tipeo.

Y el `>= c0.f0` **leído de la base y no clavado** también se pagó solo: la
consulta se escribió creyendo que el corte era el 31/08 y midió bien contra
el 05/09 sin que nadie la tocara.

### La quinta causa, y por qué no puede estar en esta consulta

**Las cuatro miran registros del sistema.** Todas contestan la misma forma de
pregunta: *"¿el sistema sabe algo que el conteo no vio?"*. Ninguna puede
contestar la de al lado:

- **el conteo vio algo que el sistema no puede saber** (mercadería que entró
  sin cargarse, un reingreso que volvió y nadie anotó), o
- **el conteo estuvo mal.**

Y ese segundo caso no es hipotético: **Mango terminó siendo exactamente eso**
—un error de conteo de 2 cajones— el mismo día. Una consulta escrita sobre
`compras`, `movimientos_stock` y `conteos_stock` no tiene por dónde verlo.

Es la forma del corolario 11: la medición está bien y contesta la mitad de la
pregunta. Por eso el orden que sigue es el correcto —mirar las tarjetas
contra el número VIVO antes de ajustar, porque los tres salieron de
`corte_fifo_13`, que compara contra el `stock_sistema` congelado— y por eso
**si después de ajustar los tres vuelven a aparecer mañana, la lista está
incompleta y la quinta causa está afuera del sistema, no adentro.**

## La caja que cuesta la doceava parte del cajón: no es un error de unidad

Con las cuatro columnas, Frutamax (corte 05/09, 06 y 07/09): `caja_s_costo` y
`cajon_s_costo` **en cero en todos**, así que el sesgo que temía no existe.
Pero aparecieron razones enormes entre los dos lados:

```
Tomate Perita   x_hoy 50.000,00 → x_conb 4.095,38   ×12,2
Pepino               22.625,00 →      2.869,09      ×7,9
Zapallito            34.230,77 →      6.075,76      ×5,6
Morron Verde         35.000,00 →      8.707,89      ×4,0
Tomate Cherry        58.407,28 →     16.685,61      ×3,5
```

### No es un error de unidad en la consulta

`compras.importe` **es por bulto**, no el total de la compra. Está dicho
textual en el docstring de `recepcionar_compra`: *"como el importe es por
bulto, ninguna cuenta cambia"*. Y producción lo usa así en los dos lugares
que importan: `c.importe AS costo_bulto` en la consulta de entradas del FIFO,
y `SET costo_por_bulto = c.importe` al completar `reprocesos_consumos`. La
medición usa el mismo campo con el mismo significado que producción — si
estuviera mal, la Rentabilidad Real estaría igual de mal.

### Tampoco es el precio moviéndose entre días

Es **el bulto que dejó de ser el mismo objeto**.
`costo_por_bulto_primera = costo_total / bultos_primera`, y **nada ata
`bultos_primera` con `bultos_tomados`**: el único check del esquema es
`bultos_primera >= 0`. Un cajón grande partido en doce cajas chicas da doce
bultos de primera por uno tomado, y el costo por bulto cae doce veces sin
que falte ni sobre un peso.

O sea que *"harían falta doce veces más bultos de primera que tomados, que es
imposible"* — no es imposible: **es exactamente lo que hace un reproceso que
reenvasa.**

Y de ahí sale una predicción verificable, que es lo que la separa de una
explicación cómoda:

> **`x_hoy / x_conb` tiene que dar parecido a `bultos_primera / bultos_tomados`
> de las guías R de ese artículo.**

Reproducido contra el esquema real con dos artículos inventados: uno que
parte 1 cajón en 12 cajas da `primera_por_tomado 12,00` y
`x_hoy/x_conb = 50.000/4.166,67 = 12,00`; uno que va 1 a 1 da ratio 1,00 y
`x_hoy = x_conb`. **Los mismos números por los dos caminos.** La consulta que
lo mide sobre datos reales es `db/e5_7_cuantas_cajas_salen_de_un_cajon.sql`.

### Lo que esto le cambia al número

Si la predicción se cumple, **los −$4,4M dejan de ser un ahorro y pasan a ser
la corrección de un sobrecosteo.** Un armado de un artículo reenvasado
despacha CAJAS, y hoy el FIFO se las cobra contra CAJONES: le pone el precio
del objeto grande a lo que salió chico. B no "abarata" nada — deja de cobrar
de más.

Eso hace a B más urgente, no menos, y cambia lo que hay que anunciar: **la
Rentabilidad Real viene sobre-costeando los artículos que se reenvasan.**

Y hay un alcance que conviene tener claro: **el error es solo de costo.** El
stock en cantidad se calcula aparte (`compras + primera − armados`) y no lo
toca la atribución. Lo que sí queda tocado es la vieja observación del dueño
—el Remanente no puede sumar bultos de distinto contenido—, que deja de ser
una molestia de presentación: **es el mismo hecho, visto del lado de la
cantidad.**

## La predicción falló a medias, y la falla dice qué faltaba

`e5_7` sobre Frutamax dio ratios que van en la dirección correcta y son **3 a
4 veces chicos**: Perita 3,00 contra un `x_hoy/x_conb` de 12,2; Pepino 2,73
contra 7,9; Zapallito 2,44 contra 5,6.

**Mi predicción tenía un supuesto que no escribí**: que la caja disponible
salió DEL MISMO cajón que el armado se está comiendo. No es así, y de ahí
sale la identidad completa. Como
`costo_por_bulto_primera = costo_total / bultos_primera` y
`costo_total = tomados × cb_consumido`:

```
costo_por_bulto_primera = cb_consumido × (tomados / primera)
x_hoy / x_conb          = (cb_armado / cb_consumido) × (primera / tomados)
                           └─ el factor que faltaba ─┘   └─ lo que medí ─┘
```

**El factor que falta es de PRECIO ENTRE LOTES**: el cajón que la guía R se
comió no es el que come el armado. Y tiene una razón estructural, no de
ruido: **la guía R va antes en el orden del FIFO** —su primera recién existe
después— así que se lleva el lote más viejo y al armado le queda el más
nuevo. Con precios en alza, eso da un factor sistemáticamente mayor a 1.
Tendencia, no ley: Tomate Redondo da 0,81 y es el caso inverso.

Aislado contra el esquema real (`EJEMPLO Precio Entre Lotes`): un artículo
con `primera/tomados = 1,00` y merma 0 —o sea, con el reenvasado explicando
CERO— donde la guía R come el cajón viejo de $10.000 y al armado le queda el
nuevo de $40.000. `e5_7` dice 1,00, `e5_6b` dice `x_hoy 40.000 / x_conb
10.000 = 4`, y `e5_8` dice `x_consumido 10.000`. **Todo el efecto salió del
factor de precio.** Y la identidad se verifica sola:
`x_prim_teorico = x_prim_real = 10.000`.

### Y la corrección de mi explicación de Tomate Redondo

Dije que su signo positivo era el markup por merma. **Está mal**: con
`primera_por_tomado = 1,00` (60 y 60) y merma 0, la merma no puede ser. Es
el mismo factor de precio corrido para el otro lado — la guía R consumió un
cajón **23% más caro** que el que come el armado (`0,81 = 1/1,23`). Una sola
causa para los dos signos, pero no la que dije.

### Pomelo: e5_7 y e5_6b miran poblaciones distintas

`e5_7` filtra `tipo='normal'`. `e5_6b` cuenta como trabajado **tres**
fuentes:

| Fuente | Tiene ratio | De dónde sale su costo |
|---|---|---|
| guía R `normal` | sí (`tomados > 0`) | del cajón que consumió |
| guía R `inicial` | **no** (`tomados = 0`) | **cargado a mano en el corte** |
| `reingreso_rechazo` | no | congelado del pedido de origen |

Frutamax tiene **8 guías R `inicial`** (`e5_0`). Producen sin consumir y su
costo no sale de ningún cajón: si se cargó bajo, tira el `x_conb` para abajo
sin que ningún ratio lo explique. Y el reingreso, que Palmala nos enseñó que
existe sin reprocesos, tampoco está en `e5_7`.

**O sea que comparar el ratio de `e5_7` contra el `x_conb` de `e5_6b` era
comparar poblaciones distintas** — la misma forma del corolario 13, una
cuenta correcta aplicada a otro universo. `db/e5_9_...sql` las separa.
Verificado: con una guía R `inicial` de 25 bultos a $2.000 al lado de una
`normal` de 10 a $10.000, `e5_9` muestra las dos y `e5_7` sigue viendo solo
la segunda.

### Qué queda por medir, y qué NO se puede afirmar todavía

Hay **dos candidatos** para las tres cuartas partes que faltan, y los dos son
medibles:

1. **El precio entre lotes** → `e5_8` (`x_consumido` contra el `x_hoy` que ya
   está).
2. **La población** → `e5_9` (`x_inicial` y `x_reing` contra `x_normal`).

Hasta correr las dos **no se puede decir cuál pesa más**, y decirlo sería
repetir el error de esta vuelta: dar por explicado con la primera causa que
encaja.

### Lo que sí se sostiene sobre el número

B no abarata: **cobra lo que efectivamente salió.** Hoy el FIFO le cobra al
armado un objeto distinto del que se despachó —más grande por el reenvasado,
y/o comprado otro día a otro precio—. Los −$4,4M son el tamaño de esa
imputación equivocada, en la dirección en que cae. Eso no depende de cuál de
los dos factores pese más.

## Pieza 3: el armado toma caja armada antes que cajón

Las dos pasadas, en `repartir_fifo` y en `atribuir_costos_fifo`, **en el
mismo commit** — el emparejamiento del FIFO ya se separó una vez entre esas
dos funciones y está en CLAUDE.md.

### Dos pasadas y no una lista reordenada

`pasadas_de_lotes(lotes, salida)` devuelve una lista **por pasada**: primero
los tipos preferidos, después el resto, **cada una en el orden de fecha
original**. Reordenar por tipo habría roto el `break` de los dos loops —
cortan al llegar a un lote posterior a la salida, y eso vale solo porque los
lotes vienen por fecha. Con la lista mezclada cortarían de más y en silencio.

### El índice cambió de invariante, y ese es el punto delicado

`atribuir_costos_fifo` recorre con un índice **compartido entre salidas**.
Antes avanzaba mientras el lote de adelante estuviera agotado, apoyado en que
los lotes se consumen de adelante hacia atrás. **Con la preferencia eso deja
de ser cierto**: un armado saltea el cajón viejo para ir a la caja de más
adelante, y el cajón queda vivo DETRÁS del índice.

Ahora el índice solo se come el **prefijo agotado** —lo único que sigue
siendo verdad— y cada salida recorre desde ahí. Sigue ahorrando el rescaneo
de los lotes muertos del principio, que es para lo que estaba, y no promete
nada más.

**El test se escribió antes que el código**, y se verificó que agarra el bug:
con el invariante viejo puesto, `test_el_INDICE_no_se_pasa_de_largo_el_lote_que_el_armado_SALTEO`
falla con su propio mensaje. El caso tiene los costos separados a propósito
($100 contra $999) para que el bug dé otro número y no otro decimal.

### La pared de la guía R NO entró al reparto, y es una decisión

`pasadas_de_lotes` aplica la **preferencia** y no la **prohibición**. La
pared sigue donde la puso la pieza 2: donde se le ofrecen los lotes a una
guía R nueva. Dos razones, las dos escritas en el código:

1. El reparto **rejuega la historia**, y la historia de las 10 guías R
   medidas es que sí se comieron cajas armadas — de ahí salieron los
   $2.798.438,92, leídos de `reprocesos_consumos`, que está congelado. Un
   reparto que se las negara pondría la pantalla de stock a contradecir el
   documento congelado.
2. **El backtest que autorizó A (`frenan_con_a = 0`) modeló exactamente
   esto.** Cambiarlo acá invalidaría la medición que dejó mergear A sin
   avisarle al galpón.

Queda pinchado con `test_un_reproceso_toma_dentro_del_REPARTO_sigue_viendo_todos_los_lotes`
para que sea una decisión y no un olvido.

### PREGUNTA ABIERTA: el ratio que no cerró

`e5_7` dio ratios 3 a 4 veces más chicos que `x_hoy/x_conb`, y quedaron **dos
candidatos sin separar**: el precio entre lotes (`e5_8`) y la población de
lotes trabajados —`normal` contra `inicial` y `reingreso`— (`e5_9`). Las dos
consultas están escritas y sin correr.

Se deja abierto a propósito: el diagnóstico de fondo no depende de cuál pese
más —el FIFO le cobra al armado un objeto distinto del que salió— y con el
sistema ya arreglado el número va a ser otro. **Si después de B algo sigue
raro, se mira ahí.**

## La consulta de control de B no puede existir, y hay que decirlo

Ofrecí escribir una consulta que rejugara el FIFO **con la preferencia
puesta** para confirmar en producción que `mal` cayó a ~0. **No sirve, y
ofrecerla fue un error del mismo tipo que veníamos persiguiendo.** Dos
razones, y la segunda es la que la mata:

1. **Sería circular.** Una consulta que implementa B y después mide "¿queda
   armado comiendo cajón teniendo caja?" da cero **por construcción de la
   regla que ella misma escribió**. Estaría verificando el SQL, no el
   sistema. Es el fixture armado a partir de la hipótesis, con otra ropa.
2. **No hay nada que leer.** B no escribe una sola fila. La atribución de un
   armado **no se persiste**: `guardar_lotes_elegidos` guarda *solo la
   excepción* —la elección a mano del operario— y su docstring lo dice
   textual: *"el default nunca se escribe"*. Lo que B cambia se recalcula en
   cada pantalla y no queda en ninguna tabla.

**O sea que ninguna consulta SQL puede ver si B está corriendo.** Lo único
que lee el código de producción es producción.

### Y eso deja un agujero de verificación que sí conviene tapar

No hay **marcador de versión** en la app: `/salud/db` existe, pero nada dice
qué commit está sirviendo. Entonces "mirá la pantalla y fijate si bajaron los
costos" no distingue dos cosas:

- que B no funcione, y
- que se esté mirando la versión vieja.

Es exactamente la familia del push que salió con código 0: **lo que hay que
mirar es el estado final, no que nadie se haya quejado.** Hasta que exista
ese marcador, la verificación en pantalla tiene que apoyarse en una señal
BINARIA del código nuevo, no en un número que puede bajar por otra causa.

La señal binaria de B: **abrir el desglose de un renglón armado de un
artículo que se reenvasa** (Perita, Pepino, Cherry). Si propone un lote
`reproceso` primero, está corriendo el código nuevo; si propone un `guia`,
es el viejo. No depende de ningún importe.

## ¿El armado se adelanta a la guía R? Para los 11 de Perita, no

La pregunta de procedimiento —el armado se registra antes que la guía R del
día, así que en ese instante la caja no existe— **no puede explicar el `mal`
de `e5_4`**, y se descarta leyendo la definición, no opinando:

- `e5_4` exige `l.d <= s.d`: la caja tiene que estar fechada **el día del
  armado o antes** para contar como disponible.
- Producción usa el mismo criterio. `lote_posterior_a_la_salida` compara
  **fechas y no relojes**, y su docstring lo dice: *"un lote cargado a la
  tarde cubre una salida de esa misma mañana"*.

Así que los 11 bultos de Perita ($550.000) tenían una caja fechada ese día o
antes, con restante, y el FIFO se fue al cajón igual. **Es E5 puro, opción 1,
y B lo arregla.**

### Pero la pregunta es buena, y el problema que describe existe: está en otra columna

Si la guía R quedó fechada **después** del armado, la caja no entra en `disp`
y ese armado no cae en `mal` — cae en **`sin_opcion` (135 bultos)**. O sea
que el problema de procedimiento, si existe, **está escondido justo en la
mitad que dimos por legítima.**

`db/e5_10_la_guia_R_llego_tarde.sql` parte los bultos de armado en tres:

| Columna | Qué significa | Quién lo arregla |
|---|---|---|
| `con_caja_previa` | había guía R ese día o antes | **B** |
| `solo_posterior` | no había, pero hay una después | **procedimiento**, ninguna regla de FIFO |
| `nunca` | el artículo no se reprocesa | nadie: cajón legítimo |

Es la misma familia que *"cargar las guías R ANTES de contar"* de
`docs/procedimiento_corte.md`, un paso más adelante: allá ensuciaba el
conteo, acá ensucia el costo.

Verificada contra el esquema real con un artículo por caso (guía R del 02
contra armado del 03; guía R del 05 contra armado del 03; y uno sin guías):
7 / 7 / 7, cada uno en su columna. Base vacía devuelve una fila de ceros y el
canario del corte muerde (con `>=`, los 7 pasan de `nunca` a
`con_caja_previa`).

## E5 cerrado del lado del diagnóstico (08/09)

Todo lo de abajo es **Frutamax, corte 05/09, recorte `> corte`: 06 y 07/09**,
dos días.

### La partición de los 765 bultos de armado

```
armado total                                              765
├─ ya se costea contra CAJA hoy .......................... 271   nada que hacer
├─ se costea contra CAJÓN teniendo caja disponible ....... 359   ← lo que arregla B
└─ se costea contra CAJÓN sin caja disponible ............ 135   cajón legítimo
   └─ Mzn Red 40 · Mzn Gob 20 · Mzn Granny 15 · Arándano 30 · Pera 30
```

Y **cierra sin residuo por dos caminos escritos por separado**, que es lo
que lo vuelve una verificación y no una afirmación:

| De `e5_4` | | De `e5_10` |
|---|---|---|
| `armado − cajon` = 765 − 494 = **271** | | |
| `mal` = **359** | | |
| suma **630** | **=** | `con_caja_previa` = **630** |
| `sin_opcion` = **135** | **=** | `nunca` = **135** |
| | | `solo_posterior` = **0** |

Las dos consultas se escribieron en momentos distintos, con estructuras
distintas —`e5_4` rejuega el FIFO por intervalos, `e5_10` solo compara
fechas de guía R contra fechas de armado— y coinciden **al bulto**.

### Las tres cosas que quedan afirmadas

1. **Hay un solo mecanismo.** El FIFO ordena por fecha y no mira el tipo de
   lote, así que le cobra al armado un objeto distinto del que salió.
2. **No hay nada escondido en la mitad que dimos por sana.** Los 135 de
   `sin_opcion` son exactamente los cinco artículos que no se reprocesan
   nunca —manzanas, pera, arándano—, los mismos que el docstring de
   `_cajas_por_ficha` viene nombrando desde antes de que los midiéramos.
3. **No hay problema de procedimiento.** `solo_posterior = 0` en todos: las
   guías R se cargan a tiempo. La hipótesis de que el armado se adelantaba a
   la guía R queda descartada **con datos**, no solo con el argumento de que
   el FIFO compara fechas.

Lo que queda abierto no es del diagnóstico sino de la magnitud: el factor de
precio entre lotes (`e5_8` / `e5_9`), que decide cuánto de los −$4.391.314,26
es reenvasado y cuánto precio entre días. No cambia qué se arregla.

## ¿La ficha obliga el envase? No, y no es un olvido

### 1. El armado no valida nada

`marcar_renglon_armado` (app/db.py) es un `UPDATE` pelado: no mira la ficha,
no mira si existe una caja armada, no mira el stock. **No hay validación de
ninguna clase.**

Y no es un descuido: la regla está escrita y es de las que sostienen el
sistema. `core/stock.py`, línea 16: *"el armado jamás se traba por stock"*.
`docs/diseno_base_datos.md`: *"el armado **avisa y no traba**. Un pedido
puede salir con mercadería que el sistema no tiene — **el piso es la verdad,
el camión sale igual**"*.

Ese mismo párrafo del diseño ya contesta la pregunta, y la contesta como
**aviso**: E5 dejó *"los dos avisos (la tolerancia de kilos y el de **no hay
cajas de esta ficha**)"*. O sea que "armaste sin caja" ya estaba pensado —
como cartel, deliberadamente no como freno.

### 2. Por qué la pared no puede vivir en el FIFO

Dos razones, y la segunda es estructural:

- **La ficha no obliga el envase ni siquiera en el dato.**
  `fichas_logistica.envase_variable` dice, textual: *"si es true, el envase
  de la ficha es solo referencia/default: se decide por compra"*. Y
  `envase_id` es nullable. La lectura dura —envase obligatorio— es solo
  `envase_id` no nulo **y** `envase_variable = false`.
- **El FIFO no puede frenar nada.** La pared de la guía R funciona porque
  `crear_reproceso` es una ESCRITURA que se puede rechazar. El reparto es
  una cuenta DERIVADA sobre hechos ya registrados: no puede negarle un cajón
  a un armado que ya ocurrió. Si le negara el cajón, el armado no se
  frenaría — **caería a `sin_lote`**, o sea que pasaríamos de un costo mal
  imputado a un costo perdido. Estrictamente peor.

Una pared de verdad tendría que vivir en `marcar_renglon_armado`, y eso es
una decisión de producto que contradice la regla de arriba, no un ajuste del
FIFO.

### 3. Cuántos de los 630 tienen envase fijo

`db/e5_11_envase_de_ficha_y_armado.sql` cruza la partición de `e5_10` contra
los cuatro estados posibles de la ficha: envase fijo, envase variable, ficha
sin envase y renglón sin ficha. Verificada contra el esquema real con un
renglón por estado (4/3/2/1), base vacía devuelve una fila de ceros.

El resultado decide una cosa sola: si los 135 caen en "ficha sin envase" o
"sin ficha", la lectura de que salen del cajón legítimamente queda
confirmada por el dato y no por el nombre del artículo.

## NO existe el campo que diga si un artículo va reprocesado — MAL, VER ABAJO

La pregunta del dueño, y es más grande que E5: **¿qué campo dice si un
artículo se despacha en su cajón original o en caja armada?**

Enumerado el esquema entero: **ninguno.** Los únicos booleanos son `activo`
(en cinco tablas), `envase_variable`, los tres de casillas de pedidos y
`consumos_editados`. `fichas_logistica` tiene `unidad_venta`, `envase_id`,
`contenido_caja`, `envase_variable` y los alias del cliente — nada que
distinga *reenvasado* de *directo*.

Y no es que esté en otro lado: **el sistema elige por disponibilidad.**
`listar_articulos_para_reproceso` filtra por stock a favor, y su docstring
dice, textual, que reprocesar cajas ya armadas *"es raro pero el FIFO lo
admite (un lote de guía R es un lote como cualquier otro), así que esta
pantalla no es el lugar para prohibirlo"*.

**O sea que el dueño tiene razón en el planteo**: B resuelve por
disponibilidad algo cuya respuesta correcta la tiene la ficha. Con el campo
cargado, para un artículo que va reprocesado la regla sería **pared** —
Perita sin caja tendría que avisar fuerte, no caer al cajón en silencio.

Con dos salvedades que no cambian el diagnóstico y sí el arreglo:

- **La pared seguiría sin poder vivir en el FIFO.** El reparto es una cuenta
  derivada: negarle el cajón a un armado ya ocurrido no lo frena, lo manda a
  `sin_lote`. Con el campo, lo que se gana es **un aviso que hoy no se puede
  ni escribir** —"esta ficha va en caja y no hay caja"— que es exactamente
  el que `docs/diseno_base_datos.md` dejó previsto y sin implementar.
- **B no queda mal por esto.** Sin el campo, la disponibilidad es la mejor
  aproximación que hay, y la partición cerró sin residuo. Lo que cambia es
  que deja de ser *la* respuesta y pasa a ser *la respuesta provisoria*.

### Lo más cerca que hay es un par derivado, y hay que probarlo antes de creerle

```
fichas_logistica.contenido_caja   = lo que el cliente pide por bulto
articulos.contenido_referencia    = lo que trae el bulto que se compra
```

Si difieren, el bulto de venta no es el de compra: reenvasado. Pero los dos
son **nullable**, y `contenido_referencia` es explícitamente *"solo
referencia"*.

`db/ficha_1_hay_campo_que_diga_reprocesado.sql` cruza ese par contra el hecho
consumado (¿el artículo tuvo guías R alguna vez?) y devuelve la matriz
completa: aciertos, falsos negativos (`gr_sin_señal`), falsos positivos
(`sin_gr_pero_difiere`), negativos, y **`sin_dato_para_saber` aparte** —
porque "no difieren" y "no hay dato cargado" dan los dos cero y significan
cosas distintas.

Verificada contra el esquema real con un artículo por cuadrante: 1/1/1/1/1,
cada uno donde va. Base vacía devuelve una fila.

**Si el par predice bien, sirve para sembrar la marca. Si no, la marca hay
que cargarla a mano ficha por ficha, y eso es el pendiente real.**

## Estado al cierre del 08/09, una línea por cosa

- **Tolerancia de kilos**: implementada, ±3 kg **por bulto**, compara
  `kilos_enviados / bultos` contra `fichas_logistica.contenido_caja`, avisa
  en la pantalla de armar y solo para fichas por kilo. **Sin cambios.**
- **Aviso "no hay cajas de esta ficha"**: ESTABA IMPLEMENTADO desde E5
  (29/08) y yo dije que no. Lo que le faltaba era la condición del envase —
  ver la sección de abajo.
- **Campo que distinga reenvasado de directo**: **no existe** en el esquema.
  `db/ficha_1_hay_campo_que_diga_reprocesado.sql` mide si el par
  `contenido_caja` / `contenido_referencia` puede sembrarlo.
- **Marcador de versión**: no existe; por eso "verificá en la pantalla" no
  distingue "no funciona" de "estás mirando lo viejo".
- **A y B**: mergeadas. E5 cerrado del lado del diagnóstico, con la
  partición 271 / 359 / 135 cruzada por dos consultas independientes.

Mañana, en este orden: **marcador de versión**, **`ficha_1`**, y el **aviso
de "no hay cajas"**.

Sin correr, sin urgencia: `e5_8` / `e5_9` (el factor de precio entre lotes),
`e5_11` (envase fijo entre los 630), `remanente_1` y `remanente_2` (alcance
del desglose por contenido), `corte_fifo_15` con los tres desvíos sin causa,
y la caja de Día de Mango.

## El campo SÍ existe: `fichas_logistica.envase_id` (08/09, corrección)

Dije que no existía. **Está, y lo encontró el dueño mirando el resultado de
`e5_11`:**

```
TOTAL   armado 765 · con_caja_previa 630 · envase_fijo 570 · env_variable 60
        · sin_envase 135 · sin_ficha 0
```

- Los **135** de `sin_envase` son exactamente Mzn Red 40, Mzn Gob 20, Mzn
  Granny 15, Arándano 30, Pera 30 — **todos con `con_caja_previa` = 0**.
- Los **630** son 570 de envase fijo + 60 de envase variable (Mango 30 y
  Cherry 30).
- **Cero cruces en las dos direcciones.**

Y la lectura correcta no es "envase fijo" sino **"la ficha tiene envase
asignado", variable o no**: `envase_variable` dice si el TAMAÑO del envase se
decide por compra, no si lo hay.

### Verificado contra el código, y el código ya lo decía

No es una correlación afortunada sobre siete artículos. `app/main.py`, en
mayúsculas, desde antes de esta conversación:

> **SIN ENVASE ES "ENVASE PERDIDO", NO UN DATO QUE FALTA. La mercadería sale
> en el envase del proveedor y no vuelve**, así que no hay caja nuestra que
> nombrar — y es el caso de la MAYORÍA de la fruta, no una excepción.

Y `core/fichas.py`, bajo el comentario **`# Sin envase compartido (se
entrega en su propio cajón)`**, lista con `envase: None` a **Mzn Granny, Mzn
Red, Pera, Man Gob y Arándano** — los cinco artículos de los 135, nombrados
en el código antes de que los midiéramos.

O sea: `envase_id` no nulo = *va en una caja nuestra, hay que reenvasarlo*.
`envase_id` nulo = *sale en el cajón del proveedor*.

### Nada lee el nulo como dato faltante

Revisado, que era el punto 3 del dueño:

- `_validar_envase`: *"opcional: 'sin envase' es válido"*.
- El formulario ofrece **"Sin envase (perdido)"** como opción deliberada.
- El costeo le pone `SIN_ENVASE = 0` *"porque no compramos ninguna caja para
  eso"* (`app/costeo.py`, dos lugares).
- **La única aparición de `envase_id IS NULL` como condición en todo el repo
  era mi propia `e5_11`.** Ninguna alerta, ninguna lista de pendientes.

### Consecuencias

1. **`ficha_1` no hace falta y se borra** — y alcanzó a correrse antes,
   así que además está MEDIDO que no servía:

   ```
   gr_y_difiere 9 · gr_sin_señal 7 · sin_gr_pero_difiere 2
   · sin_gr_ni_señal 15 · sin_dato_para_saber 0
   ```

   **7 falsos negativos y 2 falsos positivos sobre 33 artículos**, casi un
   tercio mal, y con `sin_dato_para_saber` en cero: no falla por falta de
   carga, falla por diseño.

   **Y el mecanismo del fallo es lo que más vale**: los siete falsos
   negativos —Ombligo, Pomelo, Cherry, Redondo, Jugo, Mandarina, Mango— se
   reprocesan y tienen `contenido_caja` = `contenido_referencia`. Se
   **reenvasa al mismo kilaje**: el cajón trae 16 kg y la caja lleva 16 kg,
   cambia la caja y no el peso. El par derivado solo ve reenvasado cuando
   cambia el NÚMERO, y el caso más común no cambia el número.

   Contra eso, `envase_id` acertó **630 de 630 y 135 de 135, sin un cruce**.
2. **El aviso "no hay cajas de esta ficha" se puede escribir hoy**, sin
   migración: la condición es `envase_id` no nulo y cero cajas armadas
   disponibles de esa ficha.
3. **B sigue siendo correcto pero deja de ser la última palabra.** Resuelve
   por disponibilidad lo que la ficha declara. Con `envase_id` a la vista, un
   armado de Perita sin caja es un caso para avisar, no para costear en
   silencio contra el cajón.

## El aviso "no hay cajas de esta ficha" ya existía. Le faltaba una condición

Dije dos veces que estaba *"previsto y sin implementar"*. **Estaba
implementado desde E5 (29/08)**: `sin_cajas_de_la_ficha` en `app/main.py`,
dibujado en `deposito_pedido_armar.html`, con estilo propio y cuatro tests.
Hasta la función que lo alimenta —`fichas_con_cajas_armadas`— tiene un
docstring que dice que es para esta pantalla y por qué devuelve solo ids.

Me equivoqué por lo mismo del corolario 20: **afirmé una negativa sin
buscarla como se busca una.** Un `grep` de la frase la encontraba.

### Lo que sí faltaba, y era lo que lo volvía inútil

La condición era:

```python
r["ficha_id"] is not None and r["ficha_id"] not in con_cajas
```

O sea que **saltaba para cualquier ficha sin cajas** — incluidas manzana,
pera y arándano, cuyas fichas tienen `envase_id` nulo ("envase perdido":
salen en el cajón del proveedor) y por lo tanto **no van a tener cajas
armadas nunca**. El cartel salía en cada uno de esos renglones, todos los
días, para siempre.

**Un cartel permanente se deja de leer justo el día que dice algo.** Medido:
135 de los 765 bultos de armado son de esos cinco artículos.

Arreglado con la condición que salió del hallazgo de anoche:

```python
r["ficha_id"] in fichas_con_envase and r["ficha_id"] not in con_cajas
```

### Y el texto ahora manda a cargar la guía R

Antes: *"Fijate si hay que reprocesar antes de mandarlo."* Ahora:

> **No hay cajas armadas de esta ficha. Si ya las armaste, cargá la guía R
> antes de tildar; si no, hay que reprocesar.**

La caja que falta **casi siempre está en el piso y lo que falta es el
papel** — el aviso tiene que llevar a eso y no a "fijarse". Sigue sin trabar:
el armado jamás se traba por stock.

### Los tests eran parte del bug

`FICHAS_E5` tenía `envase_id: None` en las dos fichas, así que los cuatro
tests del aviso **pasaban por la razón equivocada**: verificaban el cartel
sobre fichas que hoy no deberían recibirlo. Corregido el fixture en el mismo
commit, más un test nuevo —la ficha de envase perdido no recibe el aviso—
verificado con la condición vieja puesta: cae.

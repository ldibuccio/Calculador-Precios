# Módulo: stock, guías R y el FIFO

Movido TAL CUAL desde CLAUDE.md el 03/10 (sin reescribir). Las reglas
vigentes, en corto, están en CLAUDE.md.

## Una salida de una ficha con envase solo puede salir de esa ficha

**Cosa fija del sistema, no el arreglo de un día.** Se tuvo que decir tres
veces el 09/09 y cada vez apareció un lugar distinto donde no se cumplía.

Cuando se arma un pedido y **no hay stock de la ficha del cliente, la única
opción es sin asignar.** No toma de ningún otro lado: ni de los sueltos, ni
del cajón, ni de otra ficha. La ficha queda **en negativo, en el aire**,
hasta que alguien cargue la guía R — y ahí se acomoda solo, porque el
reparto se rejuega en cada lectura y la comparación es por FECHA. **Desde el
30/09 con margen**: la guía puede estar fechada hasta
`DIAS_DE_MARGEN_DE_LA_GUIA_R` (3) días corridos después del armado y lo
cubre igual. Ver "El margen de la guía R", abajo de esta sección.

**El hecho del mundo que la sostiene**, y por eso no es una preferencia:
con envase, la mercadería sale en NUESTRA caja, y **una caja no puede salir
de un cajón sin pasar por una guía R.** No es que prefiramos no tomar del
cajón: es que ese armado no ocurrió. Si alguien dice que salió del cajón, lo
que está describiendo es un reproceso que no se cargó.

Sin envase es **envase perdido** (manzana, pera, arándano): sale en el cajón
del proveedor, no se reprocesa nunca, y ahí nada de esto aplica.

### Y al revés: un armado en cajón NUNCA toma una caja armada (30/09, dueño)

**El pedido se arma según la ficha del cliente.** Si la ficha dice cajón, sale
del cajón; si dice caja, sale de cajas (guía R o rechazo que volvió). Nunca se
cruzan, y no es una decisión a consultar: cruzarlas es un error.

Hasta el 30/09 el armado PREFERÍA lo trabajado sin mirar si su ficha llevaba
caja, así que un pedido en cajón de otro cliente se llevaba las cajas de Día.
El stock total daba bien; lo que se rompía era el reparto por lotes: el armado
de Día quedaba "esperando una guía R" y afuera de la Rentabilidad Real, y el
de cajón quedaba costeado a precio de caja.

- **Vive en `pasadas_de_lotes`** (core/stock.py), al lado de la pared del
  envase: un armado con ficha y sin envase recorre solo lo que NO es
  `TIPOS_LOTE_TRABAJADO`, sin pasada de respaldo. Si no hay cajón, queda
  `sin_lote`. Las dos copias del FIFO la leen de ahí.
- **También lo elegido a mano**: `lotes_senalados` descarta un lote que
  `lote_ofrecido` no ofrece. `guardar_lotes_elegidos` ya lo rechazaba al
  escribir; esto cubre una corrección guardada antes de la regla.
- **La toma de una guía R tampoco se come cajas al rejugar**, y lo que sale
  de los sueltos tampoco. Ver la sección de abajo.
- **El renglón SIN ficha sigue con la preferencia vieja**: no hay ficha que
  respetar. Es el único que todavía puede sacarle la caja a uno de Día, y por
  eso el detalle de la alerta cuenta cuántas cajas se llevaron.
- **Un rechazo lleva la ficha del renglón del que volvió.** El lote sigue
  siendo `reingreso_rechazo`, pero si esa ficha no tiene envase trae
  `en_cajon` (lo pone `_entradas_y_salidas_stock_varios`): es un cajón que
  vuelve, lo toma un armado en cajón y no uno de caja. Lo decide
  `es_caja_armada` (core/stock.py). Sin renglón o sin ficha queda como caja.

### Y la guía R no se come cajas al REJUGAR (30/09, dueño)

La alerta marcaba 57 bultos del pedido #38 (29/09) como esperando guía R, con
21 guías R de ese día cargadas y cajas de sobra. La causa: la pared de la guía
R (`lotes_permitidos`) se aplicaba solo al CARGARLA (el freno y el desglose) y
no en el rejuego. Cada guía R, en cada lectura, se llevaba por FIFO la caja más
vieja que quedara. Las del 29/09, cargadas a las 16:18 y antes del armado, se
comían las cajas que la guía R del día anterior había dejado para Día.

- **La toma pasa por `lotes_permitidos` en `pasadas_de_lotes`**, que es la
  misma función del freno: las dos ya no se pueden separar. Lo que el 08/09 se
  decidió al revés (no contradecir el congelado de diez guías R del 06 y
  07/09) se dio vuelta: esas diez quedan contradiciendo su
  `reprocesos_consumos`, que es un error de aquellos días (corolario 74).
- **Una merma, un pase o un ajuste SIN ficha salen de los sueltos** y no
  tocan las cajas de una ficha. La porción la parte `es_de_una_ficha`
  (core/stock.py), con la columna `de_una_ficha` que trae la consulta de lotes:
  la misma pregunta que `_SQL_STOCK_PARTIDO` hace para partir el stock. Una
  guía R SIN ficha y un rechazo sin renglón con ficha son sueltos. Con ficha,
  la merma y el pase siguen prefiriendo la caja.
- **Una merma sin ficha DIRIGIDA a una caja de una ficha se ignora**: pasa por
  `lote_ofrecido`, igual que el armado en cajón.
- El margen de 3 días no lo tapa: el caso lo cuida
  `test_la_TOMA_de_una_guia_R_no_se_come_la_CAJA_y_el_armado_NO_espera`, con
  las tomas del mismo día antes del armado.

**LA CONDICIÓN ES UNA SOLA Y TIENE UN SOLO NOMBRE**: `envase_id IS NOT NULL`
en `fichas_logistica`, que viaja con la salida como `ficha_con_envase` desde
`_SQL_SALIDAS_STOCK`. No se deduce del nombre del artículo, ni del contenido
de la caja, ni de ningún derivado — eso ya se midió y da un tercio mal
(corolario 20). El campo directo acertó 630 de 630 y 135 de 135.

Está escrita en cuatro lugares, y los cuatro tienen que decir lo mismo:

1. **La cuenta de stock** — `_cajas_por_ficha` (app/db.py). Con envase, la
   ficha **resta la salida completa y queda negativa**; los sueltos no
   absorben el excedente. El piso `max(saldo, 0)` es SOLO de la rama sin
   envase, y ahí sigue siendo obligatorio (04/09: Manzana Gob, total 63,
   sueltos 233, botón de ajuste destructivo por 170).
2. **El FIFO** — `pasadas_de_lotes` (core/stock.py), y `lotes_ofrecidos` /
   `lote_ofrecido` al lado, que son la misma pared para el que no reparte.
   Con envase **no se le ofrece el cajón**: una sola pasada, la de los
   preferidos, sin pasada de respaldo. El bulto queda **sin lote**, que es
   información verdadera —salió y el papel no está— y se costea cuando
   aparece la caja. El cajón queda intacto a propósito: si el armado le
   bajara el restante, la guía R que viene a explicarlo no lo encontraría y
   el freno la rechazaría.
3. **El armado** — el desglose (`desglose_de_renglon_armado`) NO LISTA el
   cajón, y `guardar_lotes_elegidos` lo rechaza si llega igual por un POST a
   mano. Ver más abajo.
4. **La pantalla** — el Cotejo (templates/deposito_stock_cotejo.html). El
   déficit **se ve como tal**, con el aviso de cargar la guía R, y sin botón
   de ajuste de primero que lo tape: "Cargar la guía R" es el primario y el
   ajuste queda en segundo plano. Y el aviso llega a la tarjeta de SUELTOS
   aunque esa ficha no se haya contado nunca.

### La vía de escape que hubo, y cómo se cerró (09/09)

**`lotes_senalados` no pasaba por la pared.** Corre en la PASADA 1 de
`repartir_fifo` y de `atribuir_costos_fifo`, *antes* de que
`pasadas_de_lotes` decida qué se ofrece. Un renglón con
`pedidos_renglones_lotes_elegidos` apuntando a un cajón **se llevaba el
cajón**, con envase y todo. Medido corriendo `repartir_fifo`, no leyéndolo:

```
A) armado con envase, sin corrección     cajón consumido 0.0  · sin_lote 10.0
B) el mismo, con el CAJÓN elegido        cajón consumido 10.0 · sin_lote  0.0
C) el mismo, por merma dirigida          cajón consumido 10.0 · sin_lote  0.0
```

Y era alcanzable desde la pantalla, no solo por SQL: el desglose listaba
TODOS los lotes con restante, el cajón aparecía con 0 propuestos, el input
estaba ahí, y ni el submit ni `guardar_lotes_elegidos` ni el POST miraban
`ficha_con_envase`.

Cerrada con dos cosas, y hacen falta las dos:

1. **El cajón NO SE LISTA.** No es una opción peor: es la cosa que la regla
   prohíbe. Listarlo sin input, o listarlo y avisar al guardar, dejan a la
   vista algo que no se puede elegir, y eso invita a preguntarse por qué
   está ahí. Si no queda ninguno, el caso vacío ya dice lo que corresponde
   ("faltan cajas armadas de esta ficha: cargá la guía R").
2. **`guardar_lotes_elegidos` lo RECHAZA**, con un `ValueError` que el POST
   devuelve como 400 con el motivo adentro. Que la pantalla no lo ofrezca no
   alcanza: **la guarda va donde se ESCRIBE**, no donde se muestra — es el
   mismo hallazgo del tilde de la fecha, donde un formulario armado a mano
   entraba sin ver el cartel.

**Y la razón no se copió**: las dos preguntan por `lotes_ofrecidos` /
`lote_ofrecido` (core/stock.py), que son `pasadas_de_lotes` filtrada. Lo
cuida `test_la_pared_del_POST_pregunta_por_pasadas_de_lotes_y_no_por_su_
propia_condicion`, que **mueve la pared y exige que la guarda la siga**: con
la pared parcheada para no filtrar nada, el cajón con envase tiene que
entrar. Una guarda con condición propia falla ese test.

El argumento que la había dejado abierta está escrito en `repartir_fifo` y en
general es correcto: *"lo están SEÑALANDO con el dedo, no adivinándolo — si
dicen que salió de ése, salió de ése, y discutirles la fecha sería negarles
el piso"*. **Acá es la excepción, y es la única**: no se trata de quién sabe
más, sino de algo que no puede haber pasado. El piso manda sobre lo que se
puede observar; no sobre lo físicamente imposible. Si alguien dice que salió
del cajón, lo que está describiendo es un reproceso que no se cargó.

## El margen de la guía R: cubre armados de hasta 3 días antes (30/09, dueño)

Depósito carga la guía R al día siguiente, o el lunes, y le deja la fecha del
día de carga. Con la regla estricta (una guía cubre armados de su fecha para
adelante) esos armados quedaban "esperando" para siempre, aunque las cajas
existían. El 29/09 se corrigieron a mano 15 guías del 27 al 26 y la alerta
bajó de 603 a 180 bultos.

- **La regla**: una guía R cubre armados de su fecha y de hasta
  `DIAS_DE_MARGEN_DE_LA_GUIA_R` (3, en `core/stock.py`) días corridos antes.
  Pasado ese margen, la alerta "Armados esperando una guía R" lo muestra.
- **La alerta cuenta SOLO lo que pasó el margen** (dueño, 30/09): un armado
  de hace tres días o menos todavía lo cubre una guía que se cargue hoy, y
  contarlo hacía que la alerta marcara todos los días lo del día anterior.
  La regla es `armado_fuera_del_margen` (core/stock.py), contra la fecha del
  armado. El detalle muestra los del margen abajo, en gris ("Esperando guía R
  (normal)"), sin sumarlos. El bloque del Remanente sigue mostrando todo lo
  que espera, margen incluido: ahí la pregunta es qué falta cargar.
- **Primero las de antes**: la pasada va en orden de fecha, así que las guías
  anteriores o del mismo día se usan antes que las del margen. No hace falta
  una pasada aparte (medido: el canario que la pone primero no se mueve).
- **Solo el armado de una ficha con caja**, que es el único que espera una
  guía R. Para el resto de las salidas un lote posterior sigue sin cubrirlas.
- **Un solo lugar**: `pasadas_con_margen` (core/stock.py), que usan las dos
  copias del FIFO. El costo del armado sale de la guía que lo cubre.
- **El aviso de Reproceso** ("salieron N bultos sin lote antes del...") cuenta
  solo lo anterior al margen: lo del tramo lo cubre la guía que se está
  cargando.

**El detalle de la alerta** (Administración → Alertas, desde el 30/09) lista
cada armado que espera: fecha de armado, artículo, pedido, cliente y
sucursal, y cuántas cajas del artículo se llevaron renglones sin ficha. Sale
de la misma lista que el número (`armados_esperando_guia_r`), así que las
filas que cuentan suman lo mismo que la alerta. Un rechazo que vuelve a stock
entra al reparto como lote de cajas (`reingreso_rechazo`), con el costo
congelado del listado del día del pedido.

**Un armado que ninguna guía cubre sale ENTERO de la Rentabilidad Real**
(venta y costo) al "afuera del cálculo", con el motivo "falta una guía R".
No queda en cero ni con un costo inventado. Con el margen, los que entran en
los tres días vuelven a la cuenta con el costo de su guía.

## Una guía R ANULADA no retiene nada (28/09)

La compra 827 no se podía borrar porque "R556 se costeó contra este lote", y la
R556 estaba anulada. Su consumo congelado seguía apuntando a la compra, y
`_lo_que_cuelga` lo contaba como si la guía estuviera viva. Se destrabó con
SQL a mano (ver `db/corridas_confirmadas.md`, 28/09).

Desde v1010 el borrado ignora las guías R anuladas y borra sus consumos en la
misma transacción, antes del DELETE de la compra. Si el borrado después
rebota, eso se deshace con lo demás. La excepción es la guía **en origen**:
su `compra_origen_id` es la FK misma y el CHECK del tipo no la deja en NULL,
así que frena aunque esté anulada, y el mensaje lo dice.

Lo cuidan dos barridos en `tests/test_borrar_compra_con_guia_anulada.py`:

- toda consulta sobre `reprocesos` o `reprocesos_consumos` que no pregunta
  por `anulado_el` está en una lista decidida, con su razón;
- toda FK a `compras` está decidida, con lo que hace el borrado con ella.

El 28/09 la única consulta sin ese filtro era la del borrado.

**Y v1010 rompió el borrado en Palmala, y ningún test podía verlo.** Le
sumó a `_lo_que_cuelga` una consulta a `recepciones`, que estaba en el
esquema del repo, en Frutamax y NO en Palmala. Ahí todo borrado de compra
revienta con "relation does not exist". La suite y el humo corren contra el
esquema del repo, así que pasaron en verde. Lo destapó la consulta de
huellas (`db/comparar_esquema.sql`) corrida en las dos bases, no un test.
Arreglado en v1011: `recepciones` salió del esquema y del borrado. En la
ventana en que v1010 estuvo desplegada, el dueño destrabó Palmala creando la
tabla vacía (ver `db/corridas_confirmadas.md`).

Quedan dos guardas, y cada una contesta una mitad distinta:

- `tests/test_tablas_del_codigo.py`: toda tabla que el código consulta está
  en `db/esquema_completo.sql`. Una base nueva no puede nacer sin ella.
- `db/comparar_esquema.sql`, corrida en las dos bases: que el esquema del
  repo sea el de producción. Ésta no es un test porque la corre el dueño, y
  **se vuelve a correr cada vez que se toca una tabla que una base puede no
  tener**.

## Los negativos se ven, con su número y en rojo (28/09, dueño)

"Todos los listados tienen que mostrar los negativos en rojo y con el número
real." La palta de segunda estaba en −2 (21 remitidas al Puesto, 19 entradas)
y no aparecía en ningún lado:

- **El Remanente** armaba la segunda solo con `> 0`. Su comentario decía que
  era un pool con piso propio que no podía quedar negativo, y que "el día que
  se mida uno negativo, este comentario es el lugar". Ahora sale con
  cualquier signo distinto de cero, y las cajas de una ficha también llevan
  la marca. El renglón muestra el −2 en rojo y la frase abajo. Hasta ese día
  el número iba solo adentro de la frase; lo cambió el dueño.
- **El Cotejo** decía "sistema 0", porque busca la porción en esa lista y la
  que no está vale cero. Ahora dice −2, en rojo.
- **La consulta del stock** no miraba los remitos en su filtro, así que un
  artículo cuyo único movimiento era un remito desaparecía entero.
- **Qué comprar hoy** le ponía piso en cero a los sueltos. Ahora muestra el
  negativo en rojo, en la pantalla y en el PDF. La cuenta no cambia: la
  magnitud de un suelto negativo es 0, así que no compra de más.
- **El Excel del Remanente** ya tenía el número y ahora lo pinta de rojo. El
  PDF del Remanente (desde el 28/09, ver abajo) también.

El selector de Remito de segunda sigue con `> 0`, a propósito: no se remite
lo que no hay.

**La segunda no tenía cómo corregirse cuando el desvío no viene de su origen**
(guía R, rechazo, pase o remito), por ejemplo la segunda que había en el piso
el 05/09 y no entró al stock inicial. Desde el 28/09 hay **ajuste de segunda**
(`/administracion/stock/ajustar-segunda`), con el botón en la tarjeta de
segunda del Cotejo:

- **Tabla propia**, `ajustes_segunda` (migración corrida en las dos bases el
  28/09), con signo y motivo obligatorio. No toca la primera: es la sexta pata
  de `_SQL_POOL_SEGUNDA` y el sexto parámetro de `_pool_segunda`, sin default.
- **Fechado el día del conteo, no hoy**, al revés del ajuste de primera: así el
  cierre de ese día queda igual a lo contado y la tarjeta se apaga sola. La
  diferencia se recalcula en el server con `_sistema_por_porcion_al_cierre`.
- **Su recorte es `>=` corte y no `>`**, y es la única pata del pool así: un
  ajuste corrige la cuenta, no pasó en el galpón esa tarde. La escritura
  rechaza uno de antes del corte (no contaría nunca) y uno del futuro.
- **El motivo no se precarga**: es lo único que dice por qué no vino por su
  origen. Se anula desde la misma pantalla; no se borra.

`db/segunda_negativa_1_por_articulo.sql` lista el pool de segunda de cada
artículo. No reescribe las patas: su WITH es `_SQL_POOL_SEGUNDA` con nombres
cortos para entrar en 2500 caracteres, y un test la corre al lado de
`_segunda_de_articulo` con un artículo por pata.

## El Stock del Depósito se filtra por TIPO (28/09, dueño)

`/administracion/stock/remanente` tiene tildes **Todo · Suelta · Segunda ·
Procesada**, varios a la vez. Los tipos salen de la clave de la porción, en
`core/remanente_por_tipo.py`, y lo usan la pantalla, el Excel y el PDF:
**suelta** es sin ficha y sin segunda, **segunda** es `es_segunda`,
**procesada** son las cajas armadas a una ficha.

- **Todo es "no filtrar"**, no un cuarto tipo. Los tres tildados juntos son
  Todo, y un tipo tildado con Todo gana el tipo.
- **Con filtro, una sección por tipo con su total ARRIBA** ("Segunda: 25
  bultos en total"), con signo. Un tipo sin nada sale en cero. Con Todo la
  lista queda como estaba, sin secciones.
- **Los bloques de abajo (guía R, faltan explicar) no se filtran**: son
  problemas del artículo, y un filtro no puede esconder un faltante.
- **El Excel y el PDF bajan lo filtrado**, con el filtro en el título y en el
  nombre del archivo.
- **El PDF** (`core/exportar_remanente_pdf.py`) es el papel para bajar al
  depósito: A4 vertical, una sección por tipo con su total, y una columna
  **"Contado" vacía** con recuadro para la lapicera. Con Todo trae los tres
  tipos.
- **La columna para anotar va en el PDF y no en el Excel.** El Excel ya trae
  las tres columnas del último conteo cargado, y su "Contado" vacía se sacó el
  07/09. El que imprime para contar a mano usa el PDF.

Lo cuida `tests/test_remanente_por_tipo.py`, con los tres tipos sacados del
mismo artículo del fixture, así que un filtro por artículo no pasa.

## Una guía R con `primera = 0` es un PASE A SEGUNDA por la puerta equivocada

Del 20/09. El depósito tiene diez cajones de berenjena que se pusieron feos:
no están para tirar, pero ya no son primera. **No había ninguna pantalla para
eso**, así que lo cargaban con una guía R de reproceso con `primera = 0` —
la única puerta que encontraron.

**Y los números que produce esa puerta están BIEN**, que es lo que hay que
entender antes de tocar nada. Una guía con tomados 10 / primera 0 / segunda
10 deja:

```
stock      −tomados + primera = −10   (la pata del reproceso no filtra por tipo)
pool       + bultos_segunda   = +10
costo      costo_por_bulto_primera en NULL: la plata se pierde
cajas      bultos_primera = 0, o sea ninguna caja nuestra consumida
```

Lo que está mal no es la cuenta: es **el nombre, y que ocupe una guía R**.

**Medido antes de construir** (`db/primera_cero_1_cuantas_son.sql`, Frutamax,
90 días): `población 395 · PRIMERA_EN_CERO 2 · cajones 18 · plata que no se
pega $670.000 · todo_a_SEGUNDA 2 · todo_a_MERMA 0 · mixto 0 · NI_UNA_NI_OTRA
0 · última guía 19/09`.

**Y la consulta no solo midió el tamaño: probó el diagnóstico.** Partida por
a dónde fue la fruta, las dos cayeron en `todo_a_SEGUNDA` y ninguna en
`todo_a_MERMA` ni en `NI_UNA_NI_OTRA`. Con mermas ahí, lo que faltaría sería
otra cosa —gente esquivando la pantalla de merma, que existe— y con casos sin
destino serían cajones que salieron sin que nadie diga adónde. **Un conteo
solo habría dicho "son 2" y mandado a construir sobre una hipótesis.**

### Las dos que YA ESTÁN se dejan, y por eso hay que anotarlas acá

Decisión del dueño, con fecha: **los `reprocesos` con `tipo = 'normal'` y
`bultos_primera = 0` anteriores al 20/09 son pases a segunda hechos por la
puerta equivocada.** No se corrigen — corregirlas sería anular y recargar por
la puerta nueva para mover los mismos números a otra tabla, perdiendo las
guías R que ya existen y sin que ninguna cuenta cambie.

**Y por eso la nota vale más que el arreglo**: dentro de seis meses, un
`primera = 0` en esa tabla es un misterio, y el que lo encuentre va a buscar
un bug en el costeo que no existe. Es la frase que este archivo pide cada vez
que algo se deja como está: lo que no se corrige se explica, o se paga en la
próxima lectura.

### Dónde va la puerta nueva, y lo decidió un NÚMERO y no el gusto

`movimientos_stock`, con un `tipo = 'pase_a_segunda'`. La alternativa era un
`tipo` nuevo en `reprocesos`, que **no costaba ni un cambio de cuenta** —la
pata del stock y la del pool no filtran por tipo, así que habría andado
solo—. La descartó el conteo: **36 consultas leen `reprocesos`**, y cada una
que se olvidara el filtro mostraría el pase como una guía R. Es un filtro del
que hay que acordarse en 36 lugares para siempre, contra una cirugía de
CHECKs que se hace una vez.

A favor de `movimientos_stock`, además: su pata del stock ya es
`tipo <> 'reingreso_rechazo'`, así que un tipo nuevo se resta solo; y la
pantalla de Movimientos **no tiene un `else` que afirme** —lo dice su propio
comentario— así que un tipo que no conoce no se dibuja como otra cosa.

### El UNO A UNO se preguntó, no se dedujo

Diez cajones que salen de primera son diez bultos que entran al pool: el
cajón pasa entero, no se reenvasa. **En el reproceso NO es así** —un cajón de
16 da tres cajas de 6, y el sistema acepta producir más bultos de los que
tomó— así que copiar la relación de allá habría sido exactamente el corolario
81: derivar un caso de la forma de una regla vecina en vez de preguntar si el
caso es así. Se preguntó, y va escrito donde se escribe:
`movimientos_stock_pase_uno_a_uno`.

### El pase salía de los SUELTOS — y DEJÓ DE SER CIERTO el 21/09

**Lo que decía acá hasta el 21/09, y era verdad cuando se escribió**:
`movimientos_stock_ficha_solo_merma` decía `tipo = 'merma' or ficha_id is
null`, así que un pase con ficha lo rechazaba sin ninguna guarda nueva. Y el
argumento parecía cerrado: *"una caja ya armada para un cliente que se pone
fea no es un pase, es desarmarla primero"*.

**El dueño lo dio vuelta con el caso**: se armó una caja para Día, no salió, y
se puso fea. Tiene que poder pasar a segunda DIRECTO, igual que la suelta —
desarmarla primero es un paso que en el galpón nadie da. Así que el CHECK se
ensanchó a `movimientos_stock_ficha_solo_merma_o_pase`
(`db/pase_a_segunda_3_con_ficha.sql`, corrida en las dos bases el 21/09) y el
pase acepta ficha.

**Y ESTA CORRECCIÓN LLEGÓ UN DÍA TARDE, que es el dato que vale más que el
caso.** La migración, la pantalla y los tests entraron en v945; esta oración
—que afirmaba lo contrario de lo que el commit acababa de hacer— se quedó
acá otras veinticuatro horas. Es exactamente lo que este archivo describe en
*"la copia que más se olvida es la que está EN ESTE ARCHIVO"*: al arreglar
algo el `grep` sale sobre `app/`, `core/`, `templates/` y `tests/`, que son
los lugares donde el arreglo puede romperse. **CLAUDE.md no se rompe nunca,
no falla ningún test, y no está abierto.**

Lo que la habría encontrado en el momento es lo que esa misma sección pide y
no se hizo: **grepear acá adentro el nombre de la cosa que se tocó** — un
`grep ficha_solo_merma CLAUDE.md` de un segundo, en el mismo turno que la
migración.

## Corolario 73: el recorte que protege al que reprocesa lo deja tomar el MISMO LOTE UNA VEZ POR GUÍA

Del 16/09, y no es un caso nuevo: es el agujero que se midió el 11/09 al
construir la guía en origen —*"las salidas del mismo día no cuentan, así que
dos guías sobre la misma compra el mismo día pasan las dos"*— con la parte
que ese día no se vio. Ahí se cerró con el candado UNO A UNO por compra, que
aplica **solo a `en_origen`**. Las guías R **normales** siguen sin freno.

El caso que lo trajo: un lote de 40 bultos, R300 con 30 y R307 con 26, las
dos del 14/09. Salieron 56 de 40.

**Corrido, no leído** (`reparto_para_reproceso` con el caso):

```
R300 sola (14/09, pide 30)                    disponible 40.0   PASA
R307 el MISMO dia que R300 (14/09, pide 26)   disponible 40.0   PASA   <- el caso
R307 al dia SIGUIENTE (15/09, pide 26)        disponible 10.0   FRENA  <- control
R307 el mismo dia pidiendo los 40 ENTEROS     disponible 40.0   PASA
una TERCERA el mismo dia, con 56 ya tomados   disponible 40.0   PASA
```

**Y esa última línea es lo que no estaba medido: el agujero NO está acotado a
dos guías.** Cada guía del día ve el lote ENTERO, así que el techo de lo que
se puede tomar de un lote de 40 en un día no es 80 — es 40 por cada guía que
se cargue. El caso de 56 es el mínimo visible, no el peor posible.

### Lo que pasa con el costo: las DOS cosas, y se contradicen

La pregunta natural es *"¿se atribuyó a un lote que no los tenía, o quedaron
sin lote?"*. La respuesta es **las dos, en dos lugares distintos**:

```
lo ESCRITO (reprocesos_consumos)  R300 -> guia/900 30   R307 -> guia/900 26
lo DERIVADO (el rejuego del stock)  guia/900 restante 0.0 · sin_lote 16.0
```

`reprocesos_consumos` es un **documento congelado** y de ahí sale
`costo_total = Σ(bultos × costo_por_bulto)` y `costo_por_bulto_primera`. O
sea que los 16 bultos de más **quedaron costeados al precio de ese lote,
para siempre**, en la guía y en todo lo que lea esa tabla.

El rejuego que muestra el stock dice otra cosa: el lote en 0 y 16 `sin_lote`.
**Ninguno de los dos está roto** —cada uno hace lo que promete— y por eso no
hay nada que se vea mal: el que mira el detalle de la guía ve un costo
completo, y el que mira el stock ve un hueco, y nadie los pone al lado.

Es la familia del corolario 71 —dos escrituras de la misma regla con distinto
PODER— corrida un lugar: acá no es una copia ornamental, son **dos respuestas
verdaderas a la misma pregunta**, una congelada y una derivada, que el día
que se separan no tienen cómo avisarse.

### La asimetría sigue siendo correcta, y por eso esto no se arregla solo

El recorte está razonado y el razonamiento es bueno: dentro de un día el
sistema **guarda fechas, no horas**, así que descontar una salida del mismo
día afirma un orden que no se sabe, y lo afirma en contra del que reprocesa.

**Lo que ese argumento no cubre es el TOTAL.** No hace falta saber el orden
para saber que 30 + 26 no entran en 40: la suma no depende de cuál fue
primero. O sea que el recorte contesta *"¿qué lotes había cuando cargó?"* y
el freno necesita además *"¿cuánto se llevó ya el día?"*, que es otra
pregunta y no necesita orden.

**La señal, y es la que se puede usar sin haber sufrido el caso**: cuando un
recorte se justifica porque *no se puede saber el orden*, preguntarse si lo
que se está decidiendo depende del orden. Si es una comparación de SUMAS, no
depende, y el recorte está de más — protege contra una incertidumbre que esa
cuenta no tiene.

### ARREGLADO EL 16/09, y lo que se midió antes de ponerlo

Se midió primero, por pedido del dueño, y la razón era buena: un freno que empiece a contar el
mismo día puede **rebotar cargas legítimas**, y hay que saber cuántas antes
de ponerlo. Las dos consultas están escritas y probadas contra el esquema
real con el caso plantado:

- `db/mismo_dia_1_lotes_sobreatribuidos.sql` — cuántos lotes recibieron más
  de lo que tenían, por cuánto, y cuánta plata se imputó de más. Sobre lo
  ESCRITO, que es lo que quedó congelado.
- `db/mismo_dia_2_cuantas_guias_comparten_dia.sql` — el TECHO del rebote:
  una guía sola en su día ve los mismos lotes antes y después, así que las
  únicas que pueden cambiar de resultado son las que comparten artículo y
  fecha con otra.

**El techo, corrido el 16/09** (Frutamax, `desde` 18/06, `ultima_guia_r`
15/09): `comparten_dia 155 · guias_en_la_ventana 307 · dias_con_varias 72 ·
bultos_en_riesgo 2639 de 5925 · peor_dia 3`. Palmala dio todo en cero y **no
vota** — es la base parada del corolario 24.

**La mitad de las guías comparten día**, y hay 155 sobre 72 grupos de
artículo-fecha, o sea de a dos casi siempre y tres como máximo. Eso NO son
155 casos rotos: compartir día es la CONDICIÓN NECESARIA, no el defecto —
dos guías del mismo día pueden entrar holgadas en el lote, o tocar lotes
distintos del mismo artículo. Lo que el techo dice es que el arreglo no es
un caso de borde: si rebota, va a rebotar seguido, y por eso el número del
daño real tiene que venir antes de ponerlo.

**El daño, corrido el 16/09** (Frutamax): `lotes_pasados 56 · lotes_consumidos
281 · bultos_de_mas 472 · peor_lote 31 · plata_de_mas $13.841.434 ·
lote_no_hallado 0 · guias_normales 307 · última 15/09`. **Uno de cada cinco
lotes recibió más de lo que tenía**, así que no era un incidente de dos guías.

**Y ese $13,8M es la EXPOSICIÓN, no el error** — hay que decirlo cada vez que
se cite. Los 472 bultos existieron: salieron cajas de verdad, costeadas al
precio del lote al que quedaron mal pegados. El error de cada guía es la
DIFERENCIA contra el precio del lote del que salieron en serio —mismo
artículo, fecha cercana— y es mucho menor. Es el corolario 13: la cuenta es
exacta sobre lo que mide y no contesta la pregunta con la que se la va a
citar.

### LOS 56 QUE YA ESTÁN NO SE CORRIGEN: son de la ETAPA DE PRUEBA (16/09)

Decisión del dueño, con fecha, y escrita acá para que dentro de tres meses
nadie los encuentre y quiera arreglarlos: **los lotes sobre-atribuidos
anteriores al 16/09 quedan como están.** Estamos en etapa de prueba, los
costos todavía no se toman en cuenta, y los números de estos días no
representan operación real. Lo único que se está mirando en serio es el
Remanente.

Y además **no se podían recostear aunque se quisiera**, que es lo que hace
que la decisión no cueste nada:

- La única puerta que existe, `completar_costo_reproceso`, dice en su propio
  título *"SOLO los NULL, jamás pisa"*. Arregla el PRECIO de un consumo que
  se cargó sin precio; acá el precio está bien y lo que está mal es **cuántos
  bultos** se le atribuyeron al lote.
- Y no hay respuesta correcta a la que recostear: con la regla nueva, la
  segunda guía **habría sido frenada**, no re-atribuida. El sistema no sabe
  de dónde salieron esos bultos.

Lo que sí queda es la lista de quién los sigue leyendo mal, para el día que
los costos importen: `app/db.py:9357` es la **vía de propagación** —la
primera de una guía entra al FIFO COMO UN LOTE con su
`costo_por_bulto_primera`, así que una guía mal costeada es un lote mal
precificado para todo lo que venga después—, el detalle de la guía R, y el
`SUM(rc.bultos)` por compra de `app/db.py:1579` y `3134`, que hace leer un
lote como MÁS consumido de lo que está y le apaga el botón "Vino armada" a
una compra cuyo lote no se agotó.

### Y EL REMANENTE NO SE MOVIÓ, que es lo que decidía la urgencia

La pregunta del dueño era la correcta: si los bultos de más quedaron "sin
lote" en el rejuego, ¿el Remanente muestra un faltante que no existe? Medido
contra `db/esquema_completo.sql` con el caso de 56-de-40 plantado en tres
formas, corriendo `stock_deposito_por_articulo` y `repartir_fifo` de verdad:

| el artículo | Remanente | sin_lote | negativos |
|---|---|---|---|
| un lote de 40, las guías producen 56 | **40 — correcto** | 0 | — |
| dos lotes, 40 y 100 | **140 — correcto** | 0 | — |
| un lote de 40, las guías producen 10 (el resto merma) | **−6** | 6 | `faltan 6` |

**El Remanente es una SUMA y nunca pregunta de qué lote salió**: `entradas +
reingresos + ajustes + reproceso_primera − reproceso_tomados − salidas`.
Verificado además que ninguna de las cuatro cuentas de stock
—`_sql_sumas_stock`, `_SQL_STOCK_PARTIDO`, `_SQL_POOL_SEGUNDA` y
`deficit_de_cajas_por_ficha`— lee `reprocesos_consumos`. La sobre-atribución
es un problema de LOTE y el Remanente mira el ARTÍCULO.

**Y la corrección a lo que yo mismo había escrito**: los 16 bultos NO quedan
`sin_lote` en general. El rejuego reparte la toma contra TODOS los lotes del
artículo, así que la absorbe el lote de al lado —o la propia primera del
día—. Mi medición anterior daba `sin_lote 16` porque el fixture tenía un solo
lote y nada que produjera. `sin_lote` aparece cuando el ARTÍCULO queda corto,
y entonces vale exactamente lo mismo que el negativo del Remanente (6, no
16): es un faltante REAL y ya tiene dónde verse.

Así que lo que había que mirar no era una consulta nueva: es la sección de
negativos que el Remanente ya muestra. Si está vacía, esto no le movió nada.

### El arreglo, y las dos mitades que tiran para lados opuestos

**El freno cuenta el mismo día; el reparto no.** Son dos preguntas distintas
que hasta el 16/09 contestaba la misma lista, y separarlas es todo el
arreglo:

- `reparto_para_reproceso` sigue igual: contesta *"¿qué lotes había ese
  día?"*, y ahí el recorte asimétrico está bien. **El desglose que ve el
  operario no cambia**, y la propuesta sigue saliendo de los lotes ENTEROS.
- El freno resta, de cada lote, lo que las guías R **vivas del mismo artículo
  y el mismo día** ya le atribuyeron (`descontar_lo_tomado_hoy`, leído del
  documento congelado). Eso contesta *"¿cuánto se llevó ya el día?"*, que no
  necesita orden.

**El piso en cero no es cosmético**: un lote ya sobre-atribuido aporta cero y
nunca le resta a los de al lado — `bultos_en_los_lotes` promete que su número
no puede ser negativo, porque *"trabar a un operario por un agujero que ya
estaba ahí antes de que tocara nada sería trabarlo por lo mismo que está
arreglando"*. De ahí sale, gratis, que **la guía R de una compra que llega
armada no pueda rebotar nunca**: su propia compra entra como lote intacto en
la misma transacción.

**Y el aviso de la pantalla se movió con el freno.** El `alcanza` del
desglose es el freno adelantado: si midiera contra los lotes enteros diría
que sí y el server rebotaría al apretar Guardar, que es peor que la pared —
llega después de que ya cargó todo. Los dos aplican la MISMA función sobre el
mismo dato, y lo cuida el test que mira el cableado de los tres.

### El rebote SÍ puede caerle a una carga legítima, y no tiene arreglo

No rebota cuando la suma entra: dos guías del día que juntas caben en el lote
no cambian en nada. Pero cuando no entra, **el sistema no puede saber cuál de
las dos es la equivocada**, y la pared le cae al que carga SEGUNDO aunque el
error lo haya cometido el primero.

Por eso la pared **nombra la guía R de hoy que se llevó el lote**. Un "no
alcanza" a secas, un día en que el operario VE los cajones en el piso, es
exactamente el cartel que se aprende a esquivar; con el número de la guía
sabe qué ir a mirar — o esa guía está mal, o falta cargar la recepción que
explica lo que tiene delante.

Y hay una segunda forma de rebote que es nueva y correcta: la mercadería
llegó pero su compra no está recepcionada. Hoy el recorte del mismo día lo
tapaba.

**Lo que el arreglo NO cierra**, dicho para que no se lea como más de lo que
es: con el reparto saliendo de los lotes enteros, un lote puede seguir
recibiendo más de lo que tenía **cuando el artículo tiene otro lote que
cubre el total**. El freno cierra el agujero en la SUMA, no en la
atribución por lote. Es un residuo de costeo y de trazabilidad, y por eso
se deja: los costos están en etapa de prueba.

### Y el riesgo de verdad no es el freno: es la FECHA con que se carga

Del 16/09, y salió de mirar los 132 bultos que esperan guía R —ocho
artículos, el más viejo del 07/09— y preguntarse qué pasa cuando alguien
se ponga a cargarlas.

**Los ocho se pueden cargar, y lo cerró la PANTALLA, no una consulta.**
Probados uno por uno en Reproceso, cada uno con la fecha de su armado:

```
Limon          11/09  entra con 50
Tomate Redondo 09/09  entra con 50
Mandarina      10/09  entra con 35   (con 50 rebota: ese dia habia 40)
Berenjena      07/09  entra con 20
Zapallito      14/09  entra con 20
Lima           10/09  entra con  2
Palta          10/09  entra con  5   (con 20 rebota)
```

**Y la medición que yo había escrito para contestarlo NO contestó nada.**
`db/espera_1_el_freno_nuevo_puede_rebotar.sql` cuenta los días de armado
que ya tienen una guía R ese día — un superconjunto a propósito, porque
cuáles están esperando sale del rejuego del FIFO y escribirlo en SQL sería
la segunda versión de la cuenta que el docstring de
`bultos_esperando_guia_r_por_articulo` prohíbe. Dio **119 de 128** en
Frutamax, y el dueño lo rechazó con la razón correcta: **un superconjunto
que cubre el 93% no acota nada.** Es *"más hallazgos que población condena
la heurística"* aplicado a una CONDICIÓN en vez de a un hallazgo — si casi
todos los días cumplen la condición necesaria, la condición no separa nada.

**Lo que sirvió fue usar la pantalla que ya existe como instrumento.** El
desglose (`/deposito/stock/reproceso/desglose`) es un `GET` de solo lectura
que corre `lotes_para_reproceso` + `descontar_lo_tomado_hoy`, o sea **el
código del freno, no una segunda versión de la cuenta**. Y es usable como
instrumento por una propiedad que hay que tener escrita: **`disponible` no
depende de `bultos`** — el número tipeado solo entra en `alcanza` y en la
propuesta—, así que la prueba es MONÓTONA: si entra con N, entra con
cualquier cosa menor. Alcanza con tipear el número más grande que sea
plausible.

Dos detalles del método, porque se repiten:

- **Lo que se tipea son CAJONES TOMADOS, no las cajas que esperan.** No hay
  correlación entre lo tomado y lo producido (un cajón de 16 puede dar tres
  cajas de 6), así que usar el número del bloque azul mediría otra cosa.
- **Mandarina es donde el renglón nuevo hizo su trabajo**: con 50 rebota
  —ese día había 40— y la pared nombra la guía R de hoy que se llevó el
  lote, que es la diferencia entre un "no alcanza" que se aprende a
  esquivar y uno que dice qué ir a mirar.

**Y el veredicto del freno viejo tampoco se vence**: `reparto_para_
reproceso` de una guía fechada el 07/09 mira entradas hasta el 07 y
salidas hasta el 06, los dos fijos. Cargarla hoy da lo mismo que el día 7.
Solo se mueve si alguien carga algo FECHADO en esos días, y eso solo puede
ayudar.

**Lo que sí es un riesgo es fechar la guía que falta con el día de HOY**, y
lo que lo vuelve digno de una sección es que **dispara DOS guardas
correctas a la vez, y las dos empujan para el mismo lado**:

1. **No tapa el hueco.** Una guía R posterior al armado no lo cubre
   (`lote_posterior_a_la_salida` compara fechas), así que los bultos
   siguen esperando y el bloque sigue mostrándolos. Esto la pantalla ya lo
   avisa desde el 10/09.
2. **Y entra a compartir día con todas las guías R de hoy**, que es
   exactamente donde el freno del 16/09 sí descuenta. O sea que la fecha
   equivocada es lo único que puede convertir esta carga en un rebote.

Ninguna de las dos es nueva por separado; **la que es nueva es que las
dispara el mismo error**. Y ahí está la forma general que conviene
reconocer: cuando se agrega una guarda, la pregunta no es solo a quién
traba — es **qué equivocación única hace fallar a la vez a la nueva y a
una que ya estaba**. Dos guardas correctas que comparten una causa se
sienten como un sistema que se ensañó, y el que la sufre aprende a
desconfiar de las dos.

**Lo accionable, y es una sola cosa**: al cargar estas guías, el único
campo que hay que mirar es la fecha, y va **el día en que se armó**.

(Desde el 30/09 el punto 1 vale solo pasados tres días: ver "El margen de
la guía R". El 2 sigue igual.)

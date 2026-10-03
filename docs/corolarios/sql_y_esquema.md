# Corolarios: SQL, esquema y migraciones

Movido TAL CUAL desde CLAUDE.md el 03/10 (sin reescribir). Las reglas
vigentes, en corto, están en CLAUDE.md.

## Corolario 48: una divergencia entre bases no la escribe nadie, así que ninguna guarda de escritura la ve

Del 12/09. Las dos bases tenían la ficha de Kiwi distinta: Frutamax
`kilo/kilo` y Palmala `kilo/cubeta`. En Palmala eso rompe el supuesto del
costeo (ver la sección de `unidad_compra` y `unidad_venta`).

**Nadie cargó eso mal un día.** Las dos fichas se cargaron bien en su
momento y las bases se separaron después — por una migración que corrió en
una sola, por una corrección hecha a mano, por el orden en que se crearon.
No hay un momento de escritura donde una guarda hubiera saltado.

Eso decide DÓNDE va la guarda, y es al revés de lo que este archivo repite:
*la guarda va donde se ESCRIBE* vale para el error que alguien comete
tipeando. **Para el estado que se degrada solo, la guarda tiene que mirar el
ESTADO, no la escritura** — y en este sistema eso es el registro de alertas,
que recalcula cada seis horas y se ve en el banner y en la pantalla del
sector.

Por eso la guarda quedó como alerta (`unidades_que_difieren`) y no como un
cartel en la pantalla de Fichas. Un cartel al guardar no habría visto NUNCA
este caso.

Dos decisiones adentro, las dos con su razón:

- **A LOS DOS SECTORES.** La unidad de compra se edita en Artículos
  (Compras) y la de venta en Fichas (Comercial): en uno solo, el que la ve
  no siempre puede tocarla. (Las dos mitades de esta frase se cayeron el
  15/09: la alerta pasó a Compras sola, y la unidad de compra dejó de
  editarse en ningún lado. Lo que se edita ahí ahora es el CONTEO.)
- **NO FILTRA POR "SE USA".** Un par dormido no rompe ninguna cuenta hoy, y
  la primera versión lo excluía. Pero el día que se compre ese artículo el
  costo sale mal **desde la primera compra**, y nadie va a estar mirando —
  el aviso llegaría cuando ya no sirve. Usado y dormido se distinguen en el
  DETALLE, que es donde se decide cuál atender primero, no en si aparece.

Y el caso se cerró como dormido: Kiwi nunca se compró en ninguna de las dos
bases —cero compras, cero precios, cero renglones— así que no hay plata mal
calculada. **Las tres columnas de "¿se usa?" son las que lo dijeron**, y sin
ellas el mismo hallazgo habría mandado a revisar meses de costos.

**ARREGLADO el 12/09**: Lionel alineó la ficha desde la pantalla de Fichas.
Como Kiwi estaba dormido, la dirección en que se alineó no cambia ningún
número viejo — no hay compras ni precios que recalcular.

**Y "alinear" NO ES EL ARREGLO EN GENERAL, que es lo que este párrafo se
lee como diciendo. Corregido el 15/09.** Alinear vale solo cuando todas las
fichas del artículo dicen la misma unidad de venta y esa unidad no es la de
compra: ahí hay UNA cosa mal cargada. Cuando el artículo va a dos clientes en
dos unidades, alinear le hace decir a una ficha que ese cliente compra en una
unidad en la que no compra — apaga el aviso y borra el dato. La alerta no
distinguía los dos casos y su link mandaba a los dos a la misma pantalla; **el
detalle los separa desde el 15/09** (columna "Qué es"). De Kiwi no quedó
rastro para saber cuál de los dos era: `kiwi_1` sobre Frutamax da hoy cero en
todo. Palmala no se corrió.

**Y ESE MISMO DÍA, unas horas después, "alinear" dejó de ser una opción del
todo**: con el modelo de las dos magnitudes la ficha SIEMPRE dice la verdad
—ese cliente compra en esa unidad— y lo que puede faltar es que el ARTÍCULO
declare el conteo. Así que la alerta ya no manda a Fichas ni a Comercial:
manda a Artículos, que es el único lugar donde hay algo que hacer, y salió
de Comercial porque ahí no hay nada que tocar. Los dos casos del detalle son
otros dos ("cargale el conteo" y "ya cuenta en otra unidad: no entra").

La columna "Qué es" sobrevivió al cambio de regla y sigue haciendo lo mismo:
separar el caso que se arregla del que no. Lo que cambió es cuáles son.

**Y la verificación no hay que acordarse de correrla**, que es el punto de
haberla puesto como alerta y no como cartel: `unidades_que_difieren`
recalcula sola cada seis horas y se apaga cuando el par deja de diferir. Si
en la próxima corrida el banner sigue mostrándola, es que quedó algo — y si
se apaga, eso es la confirmación, sin una consulta de por medio.

Es la diferencia práctica entre una guarda que mira el ESTADO y una que mira
la escritura: la del estado también sirve para confirmar que el arreglo
entró.

## Corolario 60: una migración que cambia un COMPORTAMIENTO no agrega ninguna columna, y el esquema del repo se queda viejo en silencio

Del 14/09. La FK de los precios pasó a NO ACTION, corrió en las dos bases, y
`db/esquema_completo.sql` **siguió diciendo `on delete set null`**. La suite
entera en verde.

No es que faltara el paso: existe, es manual, y hay un test que lo cuida —
`test_toda_columna_que_agrega_una_MIGRACION_esta_en_el_esquema_completo`, puesto
el 12/09 justamente para sacar ese paso de la memoria. **Lo que pasa es que ese
test mira COLUMNAS**, y un `on delete` no agrega ninguna. La guarda estaba
puesta, estaba bien escrita, y este cambio le pasa por al lado por
construcción.

**Y el daño no se ve en las bases que corrieron la migración**, que es lo que lo
hace durar: las dos quedaron bien, la pantalla anda, la verificación da 1/0. El
archivo viejo se cobra en **la base que todavía no existe** — la empresa
siguiente nace con el bug ya adentro, meses después, sin que nadie relacione una
cosa con la otra. Es la familia de *"una regla de unicidad no puede depender de
una extensión de Postgres"*: lo que se pierde el día que se crea la base
siguiente no es una regla.

**La pregunta que lo encuentra, y es una sola**: después de una migración,
*¿esto agrega una columna, o cambia un comportamiento?* Si es lo segundo —un
`on delete`, un `check`, un `default`, un `unique`, un índice parcial— **ningún
test de columnas lo va a ver**, y el archivo hay que tocarlo a mano en el mismo
commit.

### Y la lista escrita de memoria ya nacía incompleta

El test nuevo que pina el `on delete` de cada FK a `fichas_logistica` se escribió
con **cuatro** tablas: las que yo había mirado al arreglar los precios. El test
falló al primer intento y dijo que eran **siete** — `conteos_stock`,
`movimientos_stock` y `corte_respaldo_fichas_reprocesos` estaban bien desde
antes y no se nombran en ningún lado junto a las otras.

Las tres estaban correctas, así que no había bug. Lo que importa es el
mecanismo: **la lista la escribí mirando lo que acababa de tocar**, y eso es
exactamente el recorte que el corolario 5 describe —enumerar todas las cuentas
que leen el dato, no las que uno tiene en la cabeza—. Lo agarró el denominador
(corolario 45): el test compara el conjunto ENCONTRADO contra el DECIDIDO en vez
de recorrer solo los decididos. Recorriendo la lista propia habría pasado en
verde con tres afuera.

**Y la deliberada va EN la lista**, no afuera: `pedidos_renglones.ficha_id` sigue
en SET NULL a propósito, y el test lo exige. Dejarla afuera es cómo alguien le
copia el arreglo creyendo que se había olvidado — *buscar la otra copia es
obligatorio; copiarle el arreglo, no*.

**Y esto vale para CUALQUIER test que enumere**, no solo para éste: un test que
recorre SU PROPIA lista solo puede confirmar lo que ya sabía. Comparar el
conjunto **ENCONTRADO** contra el **DECIDIDO** falla en las dos direcciones
—cuando aparece algo que nadie decidió, y cuando desaparece algo que sí estaba
decidido— y las dos son hallazgos. Cuesta lo mismo escribirlo de una forma que
de la otra, y solo una encuentra lo que uno no fue a buscar.

### Y EL TEST DE COLUMNAS NO VE TABLAS (19/09)

La frase es del dueño y es la forma corta del corolario 60. El 60 dice que
una migración que cambia un COMPORTAMIENTO —un `on delete`, un CHECK— no
agrega ninguna columna y por eso ningún test de columnas la ve. **Una tabla
NUEVA tampoco agrega ninguna**, y es el mismo agujero por una puerta que
nadie mira.

`compras_eliminadas` se migró en las dos bases y `db/esquema_completo.sql`
no la tenía. El guardia del 12/09 estaba puesto, andaba, y **no podía
verlo**: busca `alter table ... add column`, y una tabla nueva no pasa por
ahí. No es que faltara un test — es que el que había no tiene forma de
expresar esta pregunta.

**Y el daño no lo ve ninguna de las dos bases de hoy**, que corrieron la
migración y quedaron bien: cae en **la base que todavía no existe**. La
empresa siguiente nace sin la tabla, y como el archivo se escribe en la
MISMA sentencia que el DELETE, ahí revienta todo borrado de compra — meses
después, sin que nadie relacione una cosa con la otra. Es la familia de *una
regla de unicidad no puede depender de una extensión de Postgres*: **lo que
se pierde el día que se crea la base siguiente no es una regla.**

**Y EL HUMO TAMPOCO LO AGARRA, medido y no supuesto.** Reproducido el estado
exacto del 19/09 —la tabla sin `create`, sin índice y sin comments— cayó
**un solo test, el nuevo**, con el humo en verde. El humo abre las 130
pantallas contra una base cargada con el esquema, así que ve la tabla que
falta solo si alguna consulta la nombra; `compras_eliminadas` todavía no la
nombra ninguna, y el día que la nombre ya es tarde. Ese cero vale: dice que
las dos guardas miran cosas distintas y que no hay una que cubra a la otra.

**Lo que se construyó** es el hermano del de columnas, y lo importante es
cómo pregunta: barre los `create table` de `db/*.sql`, resta los que alguna
migración dropea, y compara el conjunto ENCONTRADO contra el DECIDIDO —las
siete tablas muertas del diseño original, cada una con su razón al lado; desde
el 28/09 son cinco, porque `recepciones` y `aprendizaje_proveedores` entraron al
esquema por decisión del dueño—.
Falla en las dos direcciones, así que la lista no puede quedarse protegiendo
lo que ya no pasa.

**Y las siete muertas se verificaron, no se heredaron del encabezado**:
ninguna aparece en POSICIÓN DE TABLA (`FROM|INTO|JOIN|UPDATE <tabla>`) en
`app/` ni en `core/`. El grep del nombre suelto da **20 para `recepciones` y
3 para `conversion_articulos_cliente`**, y las 23 son prosa y nombres de
variable — es el corolario 59 exacto, y contestar con ese grep habría dejado
tres tablas "vivas" que no lo están.

**Dos cosas más que salieron del barrido, y las dos son del método:**

- **La primera versión encontró una tabla llamada `if`**, matcheada adentro
  del comentario de `agregar_disponibles.sql` que dice *"seguro de correr más
  de una vez (create table if not exists...)"*. El comentario explica por qué
  algo es así, así que NOMBRA la cosa que el test busca: la colisión está
  garantizada por construcción (corolario 38/59). Los comentarios se sacan
  antes de barrer.
- **Y el contador del canario decía 0 con la suite diciendo "2 failed"**:
  corrí pytest con `-rs`, que imprime los salteados y **no las líneas
  `FAILED`**. Lo único que lo delató fue imprimir la cola del resumen al lado
  del conteo, que es la señal que la sexta lectura del canario en cero ya
  pedía. El que estaba roto era el canario.

**Y de yapa, un SKIP que antes no estaba**: Postgres se había caído en el
medio y el humo pasó a saltearse, así que una baseline de `2801 passed, 1
skipped` se lee casi igual que una de `2802 passed`. Un test salteado no es
un test verde, y el único que lo dice es el `-rs` — que es justamente la
bandera con la que el canario no veía los FAILED. **Las dos banderas hacen
falta y ninguna sola alcanza.**

## Corolario 67: un CHECK que compara contra una columna NULEABLE evalúa NULL, y un CHECK que evalúa NULL PASA

Del 16/09. El bloque 4 de la migración de las cajas agregaba
`movimientos_stock.envase_id` con la guarda obvia:

```sql
check (envase_id is null or destino_rechazo = 'reproceso')
```

Se lee perfecta y **no rechaza nada** cuando `destino_rechazo` es NULL: la
comparación da NULL, el `or` da NULL, y un CHECK que evalúa NULL **se
considera cumplido**. Medido, no deducido: una MERMA con `envase_id` puesto
entraba.

El arreglo es `is not distinct from`, que devuelve un booleano de verdad.

**Y lo que importa no es el caso: es que la MISMA forma ya estaba escrita
dos veces en esa tabla desde siempre.** `movimientos_stock_proveedor_solo_
devolucion` y `movimientos_stock_compra_solo_devolucion` tienen el mismo
`= 'devolucion_proveedor'` contra la misma columna nuleable, así que una
merma con `proveedor_devolucion_id` entraba igual. No era un bug vivo —hoy
el único que escribe esas columnas es la ruta del reingreso, que siempre
pone un destino— pero eran dos guardas que afirmaban algo que no cumplían.
Corregidas en `db/envases_5_*.sql`, con cero ofensores en las dos bases.

**Cómo se reconoce antes de sufrirlo, y es una sola pregunta**: en un CHECK
de la forma `A is null or B = 'valor'`, preguntarse **si B puede ser NULL**.
Si puede, el CHECK no cubre ese caso — y ese caso es justamente el de las
filas de otro tipo, que son las que la guarda venía a excluir.

Es de la familia del corolario 27 —la misma propiedad de un agregado salva a
una consulta de verificación y arruina una guarda— con el mecanismo corrido
al SQL de tres valores: lo que acá cambia de signo no es un agregado, es el
NULL, que en un `where` descarta la fila y en un `check` la deja pasar.

**Y lo agarró el CASO QUE TENÍA QUE PASAR, no los que tenían que fallar.**
Se probaron once casos negativos contra la migración y los once salían en
verde con mi CHECK roto: cualquier guarda que no rechace nada los pasa a
todos si ninguno de ellos es el que la ataca. El que lo destapó fue el
número doce, el único que buscaba el agujero. Es el corolario 30 al pie de
la letra, dado vuelta: allá una batería de negativos estaba toda en verde
con la guarda que frenaba siempre; acá con la que no frenaba nunca.

**Y la verificación tuvo que mirar la DEFINICIÓN y no el nombre**: los tres
constraints existen en los dos estados y lo que cambia es el comportamiento,
así que contarlos por nombre da 3 con el agujero puesto. `guardas_NULL_SAFE_
de_3` filtra por `pg_get_constraintdef(oid) like '%IS DISTINCT FROM%'`. Es
exactamente lo del `on delete` de los precios, y la segunda vez en una
semana que un `count` por nombre no alcanza.

### Y el que avisa del nombre repetido es el que lo repite (16/09)

Del mismo día, y es el corolario 14 con una vuelta que duele: **en el
planteo del stock de cajas escribí, con todas las letras, que en este
sistema ya hay tres pantallas que se llaman "Stock" y que no había que
agregar una cuarta. Dos mensajes después bauticé la pantalla nueva
"Envases", que es el nombre de una pantalla que ya existe** (`/envases`, el
catálogo de envases con su costo, en Comercial).

Y no se cobró en la próxima lectura como suele: se cobró en el acto, y de
la peor forma. La función de render se llamó `_renderizar_pantalla_envases`,
que **ya existía en `app/main.py`**, así que Python se quedó en silencio con
la segunda definición y mi ruta nueva empezó a renderizar la pantalla ajena.
El síntoma fue un 500 pidiendo `DATABASE_URL` en un test que parcheaba las
dos funciones que la ruta llama — o sea, un error que no hablaba del
problema.

**Dos cosas que se llevan:**

1. **En Python, dos `def` con el mismo nombre en un módulo no son un error:
   gana el último y el primero desaparece.** Con 18.000 líneas, el `grep`
   del nombre antes de escribirlo es lo único que lo evita, y cuesta un
   segundo. Es el mismo mecanismo que el `HOY_DE_PRUEBA` redefinido del
   14/09, pero sobre una función y no sobre una constante.
2. **Escribir la advertencia no protege de la advertencia.** Es la tercera
   vez que este archivo anota exactamente eso —el corolario 33 lo dice del
   20, y el 18 de sí mismo— y la conclusión operativa sigue siendo la
   misma: lo que protege no es acordarse de la regla, es el `grep` hecho en
   el momento de bautizar.

La pantalla quedó **Cajas**, en `/compras/cajas`, y el nombre es además más
honesto: "Envases" es el catálogo —el concepto, con su costo— y "Cajas" es
la cuenta de las que hay en el galpón. Verificado antes de fijarlo: ni
`/compras/cajas` ni un `<title>` con "Cajas" existían en el repo.

## Corolario 72: una columna MIGRADA, SUMADA por la consulta y que NADIE ESCRIBE es un cero que ninguna verificación de esquema puede ver

Del 16/09. `movimientos_stock.envase_id` se migró el mismo día con su CHECK,
la pata `liberadas` de `_SQL_STOCK_DE_ENVASES` la sumaba, y la verificación
de la migración daba `columna 1 · guarda 1 · ofensores 0`. Todo correcto, y
la pata valía **cero por construcción**: ningún camino del código la
escribía. La columna existía, la cuenta la leía, y no había un solo
`INSERT` que la nombrara.

**Y LA LECTURA ESTABA DADA VUELTA, corregido el 17/09.** Esto se leyó como
un cableado que faltaba: la columna esperaba un escritor. No esperaba
ninguno — **esperaba sumar cajas que se fueron a la basura.** La premisa de
la pata era que el rechazo a cajón grande LIBERA la caja, y el dueño la dio
vuelta: la caja SE TIRA. O sea que el cero era el único valor correcto que
esa cuenta podía dar, y el bug no era que nadie la escribiera: era que
existiera. Se sacó entera con sus dos columnas (`db/envases_9_*.sql`).

**Eso no invalida el corolario, lo completa**, y la parte nueva es la que
cuesta encontrar: una columna sin escritor tiene DOS explicaciones —falta
cablearla, o no tiene que existir— y **las dos se ven idénticas**: columna
migrada, consulta que la suma, cero prolijo, verificación en verde. La
pregunta del 72 (*¿qué código la ESCRIBE?*) encuentra el síntoma y no
distingue los dos casos. La que los separa no es de código: es **¿el hecho
del mundo que esta columna afirma, ocurre?** — y eso se pregunta en el
galpón, no se grepea.

**Y hay una señal barata que estaba a la vista**: la columna se migró el
16/09 con su CHECK y su verificación, y el código que la escribía se cableó
en el commit ANTERIOR. O sea que la pata se escribió, se migró y se verificó
sin que nadie preguntara si el hecho pasaba. Cuando una cuenta nueva se
construye entera antes de confirmar su premisa, el cero que devuelve no es
información — es el silencio de algo que nunca ocurrió.

**Y la premisa era medible de la forma más barata que hay: preguntando.**
Es el corolario 25 al pie de la letra —la premisa que nadie midió— con el
agravante de que acá medir costaba una pregunta de una línea. La que
funcionó las tres veces en esta casa es la abierta: *"¿qué pasa con la caja
cuando la fruta vuelve a cajón grande?"*, y no *"la caja queda libre, ¿no?"*
— la segunda tiene dos respuestas y una es un asentimiento (corolario 71).

**Las tres cosas que lo confirmaron son de tres clases distintas**, y hacen
falta las tres porque cada una sola se explica de otra manera:

1. La FIRMA de `crear_movimiento_stock` no tenía el parámetro.
2. Su único `INSERT` no nombraba la columna.
3. Los dos `UPDATE` de esa tabla solo tocan `anulado_el`.

Una sola de las tres es un indicio; las tres juntas son que la columna no
tiene escritor, que es un hecho y no una impresión.

**Por qué ninguna de las guardas que ya teníamos lo ve**, y es lo que lo
vuelve una familia nueva:

- La **verificación de la migración** pregunta si la columna y el CHECK
  existen. Existen. Sale 1 y 1.
- El **test que compara la estructura ENTERA del INSERT** compara lo que el
  INSERT escribe contra lo que se espera — y si la columna no está en
  ninguno de los dos lados, los dos coinciden. Un campo que nadie nombra no
  puede desajustar una comparación entre dos listas que tampoco lo nombran.
- El **canario sobre la consulta** muerde: sacarle la pata `liberadas` hace
  caer su test. Pero ese test afirma que la consulta SUMA la columna, no que
  alguien la haya escrito alguna vez.
- Y la **pantalla** se ve perfecta: un stock de cajas al que le falta una
  suma que siempre da cero es exactamente igual a uno que no la tiene.

Es el corolario 47 con el mecanismo corrido un lugar más atrás: allá el
número no podía crecer porque medía lo que no era; **acá no puede crecer
porque el dato que mide no se escribe nunca.** Y es peor que el 47 en una
cosa: el 47 se destapa rompiendo a propósito lo que hace cero al número, y
acá romper la consulta no sirve —la consulta está bien— y romper la
escritura tampoco, porque no hay escritura que romper.

**La pregunta que lo encuentra, y se hace el día que se migra una columna**:
*¿qué código la ESCRIBE?* No "¿existe?", no "¿la suma alguien?", sino el
`grep` del nombre en la lista de columnas de un `INSERT` o de un `UPDATE`.
Si la única aparición fuera del esquema es un `SELECT`, la columna es un
cero prolijo esperando a que alguien lo lea como un dato.

Es el corolario 3 en su forma más cara —**grepear quién CONSTRUYE, no el
campo**— con la vuelta de que acá no había ningún constructor al que le
faltara el campo: **no había constructor.** El grep del campo devolvía el
`create table`, el CHECK y la consulta, o sea tres lugares que lo nombran y
ninguno que lo escriba, y esa lista se lee como cobertura.

### Y una columna que se agrega a un INSERT rompe SIETE tests, y eso está bien

Los seis tests de `crear_movimiento_stock` comparan la tupla ENTERA del
INSERT, así que agregar una columna los rompe a todos. Es exactamente lo que
el corolario 3 dice que es su función: *"que falle el día que alguien agrega
un campo es la función del test, no una molestia"*. Y el séptimo cayó por
otra cosa: su assert era `"compra_devolucion_id)" in insert.args[0]` —
anclado en el **paréntesis que cerraba la lista**, o sea en que esa columna
fuera la última. El día que dejó de serlo, el assert cayó por una razón que
no era la suya.

Un ancla que depende de la POSICIÓN de algo adentro de una lista no está
verificando lo que dice: está verificando el orden. Lo que queda es el
fragmento de la lista entera, que no puede matchear otra cosa y no se rompe
cuando la lista crece por el otro lado.

### El caso feliz que faltaba, y es el mismo del corolario 30

Seis de los siete tests pasan la columna nueva en **None**. Un INSERT que
escribiera `NULL` a la fuerza los deja a los seis en verde, y el canario lo
midió: caían dos, los dos que tienen un valor. **Una batería de casos donde
el campo va vacío no distingue "el parámetro se guarda" de "la columna está
en la lista"** — hace falta el caso con un valor, y es el único que lo dice.

## Corolario 75: un CHECK de coherencia entre DOS columnas es una pared si el código escribe UNA

Del 17/09, y es del dueño. La migración del bloque 7 agregó esto sobre
`movimientos_stock`:

```sql
check ((lleva_caja_nuestra is true) = (envase_id is not null))
```

**El CHECK está bien escrito y cubre las dos direcciones**, que es
exactamente lo que este archivo pide (una guarda que cubre un solo lado deja
pasar el espejo en silencio). Lo que no estaba era la otra mitad del par: el
código escribía `envase_id` y **nunca** escribió `lleva_caja_nuestra`. Así
que la base rechazaba todo reingreso a `reproceso` de una ficha con envase
derivable, y la guarda dejó de proteger para pasar a trabar.

**Y el modo de falla es el peor que puede tener una migración: una pared que
aparece el día que alguien usa un camino que hasta entonces nadie usó.** No
falla al migrar, no falla en la verificación, no falla con los datos que hay.
Medido en las dos bases el día que se sacó: `vuelven_a_cajon 0` sobre **27
reingresos** en Frutamax. La mina estuvo enterrada un día entero y **la
desactivó el drop, no el uso** — lo único que la hacía invisible era que
nadie había cargado todavía un rechazo de esa forma.

### Por qué NINGUNA de las guardas que ya teníamos lo ve

Y es lo que lo vuelve una familia y no un descuido:

- **La verificación de la migración pregunta por las filas que ESTÁN**, y su
  `ofensores` cuenta `lleva_caja is true and envase_id is null`. Todas las
  filas viejas tienen las dos en NULL, que es un caso legítimo, así que sale
  **0 y es correcto**. Lo que nunca se cuenta son las filas que **no van a
  poder entrar**, porque todavía no existen.
- **El CHECK no puede saber que su segunda mitad no se llena.** Una guarda
  declara una relación entre dos columnas; no sabe cuáles se escriben.
- **Los tests del INSERT comparan la tupla ENTERA** y coincidían: la columna
  no estaba ni en el INSERT ni en lo esperado. Es el corolario 72 otra vez —
  un campo que nadie nombra no desajusta una comparación entre dos listas que
  tampoco lo nombran.
- **Y la pantalla andaba**, porque el camino que rebota es el que nadie
  cruzó.

### La pregunta que lo encuentra, y se hace el día que se escribe el CHECK

> **Después de un CHECK que relaciona dos columnas, grepear el INSERT y el
> UPDATE por LAS DOS.** Si aparece una sola, la guarda no es una guarda: es
> una pared esperando al primero que pase.

Cuesta un `grep` y se hace en el mismo commit que la migración. Y es el
corolario 3 con una vuelta: allá el que falta no nombra el campo, así que
hay que grepear el CONSTRUCTOR; acá **el constructor existe y nombra una de
las dos**, que se lee como cobertura y es media.

### Con qué engancha, y son los dos extremos del mismo eje

| | qué le pasa a la guarda | cómo se ve |
|---|---|---|
| **Corolario 67** | evalúa NULL y **no rechaza nada** | todo entra, incluido lo que no debía |
| **Corolario 72** | la columna no tiene escritor y **suma cero** | un cero prolijo que nadie lee como hueco |
| **Éste** | rechaza **de más**, en un camino frío | no se ve hasta que alguien lo camina |

Los tres salieron de la MISMA migración de cinco bloques, y ésa es la
observación que más conviene guardar: **una tanda de bloques escritos el
mismo día comparte los supuestos del que los escribió**, así que un error de
lectura del mundo no aparece una vez — aparece en todos los bloques que se
apoyaban en él. Revisar uno no dice nada de los otros cuatro.

### Y el control que lo cerró fue la POBLACIÓN, no las columnas

La verificación del drop trae `movimientos_POBLACION` y se corre las dos
veces, antes y después:

```
FRUTAMAX  antes 109 · después 109
PALMALA   antes   1 · después   1
```

`columnas 0 · guardas 0` dice que se fue lo que tenía que irse. **No dice que
no se haya ido nada más.** Un `drop column` no toca filas, así que el
conteo igual antes y después es lo único que separa "salieron las dos
columnas" de "se llevó algo puesto" — y cuesta una columna más en una
consulta que ya se iba a correr.

Es el corolario 45 en su cuarto trabajo: el testigo del 24 dice si la base
vota, el total esperado dice si la medición llegó al final, el denominador
del 53 dice cuál pantalla se midió, y acá dice **qué NO se rompió**. Los
cuatro existen por lo mismo — un número solo no se puede leer.

## Corolario 77: un `JOIN` contra la fila que todavía no existe no devuelve cero, DESAPARECE

Del 17/09. Las tres patas del stock de cajas entran por `JOIN base`, donde
`base` es el conteo inicial de ese envase. Un envase recién dado de alta no
tiene esa fila, así que **`declarados` y `guias` no producen ni un renglón**
y todo lo que se le cargó —una compra de doscientas cajas, un préstamo, una
guía R— es invisible.

La pantalla decía "todavía sin conteo inicial", que es **verdadero y no
alcanza**. El que compró las doscientas entra, lee que la cuenta no arrancó,
y no tiene forma de saber que sus doscientas ya están cargadas y escondidas.
Es la ausencia de filas del backfill con otro disfraz: *"acá no hay nada"* y
*"acá hay cosas que no puedo mostrarte"* se dibujan exactamente igual.

**Y el aviso que lo tapa tiene que contar SIN EL JOIN**, que es lo que sale
al revés: escrito al lado de las otras tres patas, lo natural es copiarles el
`JOIN base`, y entonces el contador da **cero justo en el único caso que le
importa** — un cero que no puede dar otra cosa (corolario 47), adentro del
arreglo escrito para el corolario 47. Lo cuida
`test_lo_que_ESPERA_AL_CONTEO_se_cuenta_SIN_PASAR_POR_base`, que lee el
cuerpo de esas dos CTE y exige que la palabra `base` no esté.

**Y la otra mitad, que es del corolario 8**: el contador se apaga en CERO
cuando el conteo SÍ existe. Sin eso, un envase con la cuenta andando
devolvería sus movimientos como "esperando" y habría que mirar `desde` al
lado para saber si el número significa algo. **Una columna que significa dos
cosas según otra columna no es una columna: son dos.**

### El aviso nombra la FECHA, porque "ponelo antes" no dice antes de qué

El recorte es `fecha_operacion >= conteo.fecha`, así que lo que decide si
una compra vieja se suma o queda absorbida **es la fecha del conteo**, y hay
tres casos que el que arranca la cuenta tiene que poder distinguir:

| lo que quiere | qué carga |
|---|---|
| contó las cajas que ya le llegaron | la cantidad, fechado **hoy** — esas compras quedan absorbidas |
| que una compra ya cargada se sume | **cero cajas**, fechado **antes** de esa compra |
| ~~contar las cajas Y fecharlo antes de la compra~~ | **nunca** — se suman dos veces |

**El tercero es el que alguien va a hacer, y es el que no avisa**: no
descuadra nada, el stock queda alto, y el aviso de reposición llega tarde
para siempre. Por eso la regla va **en la pantalla y no en un doc**: el que
arranca la cuenta está ahí y no va a ir a buscar nada. Y por eso el aviso
dice la fecha del movimiento más viejo —la más vieja **de las dos** patas, no
la de una— porque *"fechá el conteo antes"* sin un día al lado no se puede
obedecer.

**Cero es una respuesta válida**, y va dicho donde se decide qué tipear. Sin
esa frase, el que tiene doscientas esperando cuenta doscientas, que es
exactamente el tercer caso.

### Y los movimientos y las guías R van SEPARADOS, no sumados

Se cargan en pantallas distintas. Un solo *"3 esperando"* manda a buscar en
la lista de movimientos de ese envase una guía R que nunca estuvo ahí —el
operario encuentra 2 y se queda pensando cuál falta—. Cuesta una columna más
y es la diferencia entre un número que se puede ir a verificar y uno que hay
que creer. Es el corolario 74 evitado antes de existir: dos respuestas
verdaderas que no se pueden poner una al lado de la otra.

## Corolario 94: una migración de EXPAND se corre cuando se escribe; el DROP espera al deploy

Del 22/09, y es de secuencia y no de SQL.

`cargas_compra` reemplaza a `listados_compra_manual` y
`listados_compra_clientes`, así que la tanda tiene dos clases de bloque y
**solo una se puede correr el día que se escribe**:

| | cuándo corre | qué pasa si se adelanta |
|---|---|---|
| los que **CREAN** (bloques 1, 2 y 4) | ya, sin esperar nada | nada: una tabla que nadie lee no molesta |
| el que **DROPEA** (bloque 3) | **después del deploy** | el código vivo en Railway sigue leyendo esas tablas y revienta |

**La asimetría no es de prudencia: es de qué está corriendo en producción
mientras tanto.** Entre que el SQL se corre a mano y que el commit se
despliega pasan minutos u horas, y en esos minutos el código que hay arriba es
el viejo. Crear no lo toca; borrar le saca la tabla de abajo.

**Por eso el bloque del drop va en su propio archivo y con la condición
escrita EN SU ENCABEZADO** (*"se corre después de que el Paso 2 esté
desplegado, porque hasta entonces `borrador_de_compra` todavía lee estas
tablas"*), y no en este documento: el que lo abra dentro de seis meses va a
leer el archivo.

**Y `db/esquema_completo.sql` tuvo las dos tablas viejas hasta que el drop
corrió.** El esquema del repo describe lo que una base nueva tiene que tener,
y hasta ese día una base nueva necesitaba las dos — el código todavía las
leía. Sacarlas antes es el corolario 60 al revés: el archivo adelantado rompe
la base que todavía no existe. (El drop corrió el 23/09 en las dos bases,
después del deploy del Paso 2, y el esquema las perdió en el mismo commit que
anotó la corrida.)

# Corolarios: reglas escritas dos veces, campos y premisas

Movido TAL CUAL desde CLAUDE.md el 03/10 (sin reescribir). Las reglas
vigentes, en corto, están en CLAUDE.md.

## Una regla de negocio no puede estar escrita dos veces

Si la misma regla vive en el código y en la base, son **dos** reglas: se
separan sin que nadie lo note, y la que rechaza deja de ser la que el código
cree que rechaza.

Pasó con los operarios del depósito. "Es la misma persona" estaba escrito dos
veces —un pre-chequeo en Python y un índice único en Postgres— y las dos
versiones plegaban mayúsculas y espacios pero ninguna plegaba tildes. Se cargó
**"ruben" al lado de "Rubén" y entraron los dos**. Los tests no lo agarraron
porque mockeaban la base y verificaban el *mensaje*, no la regla.

De acá en adelante:

1. **Decide la base; el código traduce el error.** Nada de preguntar antes
   "¿ya existe?" para después insertar: se intenta la operación y se atrapa la
   violación del constraint. Si el constraint cambia, el código lo acompaña
   solo.
2. **Cuando el código necesita repetir una expresión de la base** (por ejemplo
   para buscar al que ya está y poder nombrarlo), va **una sola vez**, en una
   constante, con un comentario que diga de qué migración salió.
3. **Si el constraint rechaza y el código no encuentra el motivo, eso se
   dice.** Es la señal de que las dos reglas se volvieron a separar, y tragarla
   es cómo se pierde meses después.

Hubo una VIVA entre el 07 y el 08/09, y **ya está cerrada**: el índice
`fichas_logistica_codigo_cliente_unico` plegaba `lower(trim(...))` y **no
plegaba tildes**; `normalizar_texto` (core/matcheo_comanda.py), que es quien
matchea el código del pedido contra la ficha, **sí las plegaba**. Así que
`CÓD-2` podía entrar al lado de `COD-2` —el índice los veía distintos— y para
el matcheo eran el mismo código: el sistema elegía una en silencio, que es
exactamente lo que el comentario de ese índice dice que viene a impedir. El
caso de "ruben" al lado de "Rubén", con los mismos dos plegados y la misma
tilde faltando de un lado.

**Arreglado el 08/09** con `db/plegar_tildes_en_codigo_cliente.sql`, corrida
en las DOS bases (`pliega_tildes` y `pliega_espacios` en `true`). El índice
pliega ahora tildes, eñe y espacios internos, con `translate` en SQL puro y
la lista Latin-1 + Latin Extended-A entera.

Y lo que impide que se vuelvan a separar no es que hoy coincidan: es
`test_el_plegado_de_Python_y_el_del_INDICE_son_LA_MISMA_regla`, que **lee la
tabla del `.sql`** —no la copia, porque copiada envejece en silencio— y
compara en los DOS sentidos. Cada dirección falla distinto: si la base pliega
algo que Python no, el matcheo ve dos códigos donde el índice ve uno y no
deja cargarlos; si Python pliega algo que la base no, entran los dos y el
sistema elige uno en silencio, que es el caso caro.

Corolario 2, y es de la COSTUMBRE, no de la regla: **cuando se arregla una
copia, hay que ir a buscar la otra.** Pasó TRES veces en la misma semana. El
`btrim` que plegaba espacios en Python y no en el índice. El emparejamiento
del FIFO, arreglado en `repartir_fifo` y viejo en `atribuir_costos_fifo`. Y
el `!=` de los renglones incompletos, arreglado en la alerta de Auditoría y
vivo en la pantalla que se mira todos los días — con el agravante de que el
docstring de la alerta **explicaba el bug** que la pantalla seguía teniendo.

La regla de arriba dice dónde tiene que vivir la regla. Esto dice qué hacer
el día que se arregla: **buscar el mismo criterio en el resto del código
antes de dar el arreglo por hecho.** Un `grep` del número, del operador o de
la frase alcanza, y es más barato que la tercera vez.

### Las TRES copias de `SUFIJOS_UNIDAD_COMPRA`, anotadas donde se buscan

Del 18/09. La tabla que traduce la unidad a su letra (`kilo` → `k`) está
escrita **tres veces**, y las tres son idénticas hoy:

    core/exportar_compras.py:35
    core/exportar_ingresos.py:41
    app/main.py:1068          ← la que usa el filtro `sufijo_unidad`

(Los números de línea envejecen en cada commit —el de `app/main.py` ya se
movió del 1004 al 1068 el 19/09, sin que nadie tocara la tabla—, así que lo
que se busca es `grep -rn "^SUFIJOS_UNIDAD_COMPRA" core/ app/`. Lo que no
envejece es el test que las compara.)

Decisión del dueño: **no urge y no se unifica hasta que haya que tocar
alguna** — son tres líneas iguales y moverlas ahora es riesgo sin beneficio.
Lo que sí va desde hoy es dónde están las tres, porque el que agregue una
unidad nueva va a editar la que tenga abierta y las otras dos van a decir
otra cosa: **la que se separe no va a fallar, va a imprimir un número sin
letra**, que es el hueco que no se ve.

Y lo cuida `test_las_TRES_copias_de_SUFIJOS_UNIDAD_COMPRA_dicen_lo_MISMO`,
que es el mismo patrón que el plegado de tildes: cuando dos copias no se
pueden unificar todavía, lo que impide que se separen no es que hoy
coincidan — es un test que las compara.

**Y la cuarta no se escribió**: el stock por kilaje necesitaba la letra y usó
el filtro `sufijo_unidad` que ya existe. Ese es el momento en que una copia
se convierte en cuatro, y es el único momento en que se puede evitar gratis.

### Y la copia que más se olvida es la que está EN ESTE ARCHIVO

Del 13/09, y es del dueño: **el que escribe la regla de buscar la otra copia
es el que más olvida buscarla, porque corrige donde está trabajando, y el
archivo de reglas nunca es donde está trabajando.**

El caso: la cola del corolario 56 decía *"hoy Comercial recibe un número que
no puede abrir"*. Era falso **desde el mismo día que se escribió** —esa misma
tarde se construyó `/comercial/alertas` con su `detallar`— y la frase se
corrigió en el comentario del test y no acá. O sea: se aplicó el corolario 2
sobre el código, y la copia que quedó vieja fue la del archivo que lo
explica.

**Por qué pasa siempre, y no es descuido**: al arreglar algo, el `grep` sale
sobre `app/`, `core/`, `templates/` y `tests/` — los lugares donde el arreglo
puede romperse. CLAUDE.md no se rompe nunca, no falla ningún test, y no está
abierto. Es exactamente la condición del comentario que envejece (corolario
28), con el agravante de que **este archivo se lee como el estado del mundo**:
un "hoy pasa X" viejo acá manda a construir lo que ya existe, o a no
construir lo que falta.

**Lo accionable, y es barato**: cuando un commit hace falsa una oración de
CLAUDE.md, esa corrección va EN EL MISMO COMMIT. Para encontrarla, lo que
sirve no es releer el archivo entero —nadie lo hace— sino grepear **el nombre
de la cosa que se tocó** (la alerta, la función, la pantalla) acá adentro,
igual que se grepea en el código.

**Y las oraciones que expiran se reconocen por el tiempo verbal**: las que
dicen *hoy*, *todavía no*, *no existe*, *no hay*, *queda anotado y no
construido*. Un corolario sobre un MECANISMO no envejece —el `count(*)` va a
seguir devolviendo una fila para siempre—; lo que envejece es el ESTADO que
se anota al lado para ilustrarlo. Al escribir una de esas oraciones conviene
saber que se está contrayendo una deuda, y al cerrarlas hay que volver.

Corolario 22, del 08/09: **un fixture que fija el caso equivocado convierte
al test en el GUARDIÁN del bug.** Y es distinto del corolario 9: allá el test
no podía fallar; acá podía fallar, y fallaba por lo incorrecto.

El aviso "no hay cajas de esta ficha" saltaba para cualquier ficha sin cajas,
incluidas las de **envase perdido** —manzana, pera, arándano— que no van a
tener cajas armadas nunca. Salía en 135 de 765 bultos, todos los días.

`FICHAS_E5` tenía `envase_id: None` en las dos fichas, así que los cuatro
tests del aviso **verificaban el cartel exactamente sobre los casos donde
está mal**. No es que no cubrieran el bug: **lo codificaban como
comportamiento esperado.**

Y ahí está el daño de verdad: **el que arregle el código rompe los tests y va
a pensar que se equivocó él.** Un test rojo después de un arreglo correcto es
la señal más cara que hay — o se revierte el arreglo, o se pierde media hora
averiguando que el equivocado era el fixture.

Engancha con la regla que ya está —*los datos de un fixture se escriben como
son en producción*— y le agrega el porqué: en producción esas fichas TIENEN
envase, en el fixture no lo tenían, y esa sola diferencia hizo que cuatro
tests defendieran lo contrario de lo que había que hacer.

**Cómo se reconoce**, y es lo único que sirve porque un test verde no se
mira: cuando un arreglo rompe tests, la primera pregunta no es "¿qué rompí?"
sino **"¿este test afirma lo que hoy queremos que pase, o lo que pasaba?"**.
Si el fixture no se parece a producción en el campo que el arreglo tocó, el
test es parte del bug y se arregla en el mismo commit.


Corolario 21, del 08/09, y va corto: **una operación partida en dos
funciones queda correcta solo mientras las dos se acuerden.**

La conversión a hora argentina vivía en `_fecha_del_commit` y el formateo en
`_version_app`. El resultado era correcto —el único camino que existía
convertía— pero por convención entre dos funciones, no por construcción. Un
tercer camino que trajera la fecha sin convertir mostraba UTC y nada avisaba.

Es la familia del alcance: misma operación, dos lugares, y el que muestra no
se hace cargo. **Lo hace la que muestra**, siempre, aunque sea redundante:
`astimezone` sobre un valor ya convertido no hace nada, y esa redundancia es
justamente la que sobrevive al tercer llamador.

Y el detalle del turno: **lo agarró un test nuevo, no la suite vieja.** La
suite pasaba porque el único camino existente convertía. Un test que fija el
CONTRATO —"esta función devuelve hora argentina"— encuentra lo que un test
del camino feliz no puede ver.


Corolario 20, del 08/09: **enumerar los TIPOS de columna no es enumerar los
SIGNIFICADOS.** Buscando el campo que dijera si un artículo se despacha
reenvasado o en su cajón original, listé todos los `boolean` del esquema,
no encontré ninguno, y dije que el campo no existía.

Existía: **`fichas_logistica.envase_id` no nulo**. El significado no estaba
en el tipo —es una FK nullable, no una marca— sino en un docstring de
`app/main.py` escrito EN MAYÚSCULAS antes de esta conversación: *"SIN ENVASE
ES 'ENVASE PERDIDO', NO UN DATO QUE FALTA. La mercadería sale en el envase
del proveedor y no vuelve"*. Y `core/fichas.py` lista, bajo el comentario
`# Sin envase compartido (se entrega en su propio cajón)`, exactamente los
cinco artículos que después medimos como "no se reprocesan nunca".

Dos errores encadenados, y el segundo es el caro:

1. **Busqué la FORMA que esperaba** (un booleano llamado algo como
   `es_reprocesado`) en vez del HECHO. Un `NOT NULL`/`NULL` de una FK lleva
   tanto significado como una marca, y no aparece grepeando `boolean`.
2. **Enumeré el esquema y no el vocabulario.** La palabra que había que
   buscar era "envase", y estaba en tres lugares del código diciendo
   justo esto. `grep` de la COLUMNA hubiera fallado igual; el que servía era
   `grep` del CONCEPTO.

De acá en adelante, antes de afirmar que un dato no existe: **buscar el
concepto en los comentarios y docstrings, no solo la columna en el
esquema.** En este proyecto el significado de una columna vive casi siempre
en un comentario, y "no está en el `create table`" no es "no está".

Y el corolario del corolario, que es el que más duele: **una afirmación
NEGATIVA ("no existe X") necesita más verificación que una positiva**, no
menos. Una positiva se cae sola cuando alguien mira; una negativa cierra la
búsqueda y manda a construir lo que ya estaba.

**Y hay una tercera, medida**: dado por inexistente el campo directo, propuse
DEDUCIRLO de un par derivado (`contenido_caja` contra
`contenido_referencia`: si difieren, se reenvasa). Corrido sobre 33
artículos dio **7 falsos negativos y 2 falsos positivos** —casi un tercio
mal— contra **630 de 630 y 135 de 135 sin un cruce** del campo directo.

El mecanismo del fallo es la parte que sirve para la próxima: los siete
falsos negativos **se reenvasan al mismo kilaje** —el cajón trae 16 kg y la
caja lleva 16 kg, cambia la caja y no el peso—, y un derivado que compara
NÚMEROS no puede ver un cambio que no mueve ningún número. **Falló
exactamente en el caso más común**, no en el borde.

O sea: **un campo derivado no es un sustituto barato de uno declarado.**
Codifica una hipótesis sobre cómo se manifiesta el hecho, y cuando el hecho
se manifiesta de otra forma —acá, cambiando el envase sin cambiar el
contenido— el derivado no falla ruidosamente: **acierta en la mayoría y
miente en un tercio**, que es la peor proporción posible para que alguien lo
dé por bueno.


Corolario 19, del 08/09, y es de otra familia que todos los anteriores: **la
salvaguarda funcionó, el dato estaba a la vista, y no se leyó.**

Los otros corolarios son sobre datos que no existían, que engañaban, o que
se veían igual que su ausencia. Éste es sobre un dato **correcto, presente y
visible**. El día anterior las seis consultas de E5 ganaron una columna
`corte` justamente para que no se pudiera confundir la base contra la que se
midió (corolario 17). El resultado que tenía adelante decía `2026-09-05`.
Escribí "desde el 31/08" igual.

**Por eso el arreglo NO es agregar otra columna.** Más salida no arregla que
no se lea: la empeora, porque hay más para saltear. Los dos que sí sirven:

1. **El parámetro viaja ADENTRO del número, en la misma oración.** No
   "$2.798.438,92 desde el corte" sino "$2.798.438,92 (Frutamax, corte
   05/09, `> corte`, 06 y 07/09)". Escrito así, **no se puede citar el
   número sin escribir el recorte**, y para escribir el recorte hay que ir a
   buscarlo. Una ficha al lado del número, no un párrafo aparte que se lee
   una vez.
2. **Al corregir un dato se vuelve al RESULTADO, no al texto anterior.** Ese
   fue el mecanismo exacto: corregí prosa mirando prosa. El resultado crudo
   —donde estaba el 05/09— no lo volví a abrir en ningún momento. La prosa
   es lo que estaba mal; releerla solo confirma lo que ya decía.

Y la observación que cierra: lo que sí lo agarró fue `e5_0` corrido en las
DOS bases, que puso los dos cortes en la misma pantalla. **La verificación
que funciona es la que hace chocar dos fuentes**, no la que agrega un dato
más a una sola.


Corolario 18, del 08/09: **un valor que vive en la BASE no se lee del código
que lo creó.** La migración es un registro fiel de lo que se insertó UNA VEZ;
no dice nada de lo que el valor es HOY.

Corrigiendo el "en dos días" del corolario 15 escribí que la medición
abarcaba "todo desde el 31/08". Esa fecha no salió de la base: salió del
`insert into corte_modelo (id, fecha) values (1, '2026-08-31')` de
`agregar_corte_y_stock_inicial.sql`. **El corte de Frutamax es el 05/09** —
se movió en algún momento— y el de Palmala sigue en 31/08. O sea que
`corte_fifo_1` (`>=`) abarcaba tres días y `e5_1` (`>`) dos, y el "en dos
días" original estaba MÁS CERCA que mi corrección.

Tres cosas se llevan:

1. **La corrección de un número mal introdujo otro número mal, por la misma
   causa.** No es mala suerte: al corregir se escribe rápido y con la
   sensación de estar arreglando, que es cuando menos se verifica. **Un
   commit que corrige un dato verifica el dato nuevo con el mismo rigor que
   le exigió al viejo**, o la segunda vuelta sale peor que la primera —
   porque ahora el número viene con la autoridad de "esto ya se revisó".
2. **La fuente que consulté era correcta sobre el pasado.** Es la familia
   del comentario que envejece, con una vuelta más: no había nada mal
   escrito en la migración. Lo que estuvo mal fue usarla como afirmación
   sobre el presente. Y el docstring de `_fecha_corte` lo dice desde
   siempre: la fecha vive en la base "para que se lea de un solo lugar".
3. **El arreglo ya estaba puesto y no lo usé.** El día anterior las seis
   consultas de E5 ganaron una columna `corte` justamente para esto
   (corolario 17). Si hubiera mirado esa columna en el resultado que ya
   tenía a la vista, el 05/09 estaba ahí. **Una salvaguarda que no se lee no
   sirve**, y la salvaguarda tiene que aparecer donde se toma la decisión,
   no en una consulta aparte.


Corolario 17, del 08/09: **una medición contra UNA base decide un deploy que
sale en LAS DOS.** El sistema corre sobre Frutamax y Palmala, y todo lo de
E5 se midió sobre Frutamax: `frenan_con_a = 0` decidió que A se mergeaba sin
avisar al galpón — de UNA de las dos bases.

Ya nos pasó con Palmala y el backfill (la exclusión que se decidió mirando
una cuenta y el daño cayó sobre otra). La forma es la misma: **el alcance de
la decisión es más grande que el alcance de la medición**, y nada avisa
porque la medición que se corrió salió bien.

De acá en adelante: **toda medición que decide un merge se corre en las DOS
bases antes de mergear**, y el resultado se escribe con el nombre de la base
al lado. Un número sin base es un número a medias.

Y el corolario del corolario, que es lo que lo vuelve peligroso: **una
consulta parametrizada por un dato de la base miente distinto en cada
base.** Todas las de E5 leen `corte_modelo where id=1`. Si esa fila no
existe, el CTE sale vacío, el cross join deja todo en cero y `e5_3`/`e5_4`
devuelven **una fila de ceros que se lee igual que "acá no hay problema"**.
Verificado corriéndolo con la fila borrada.

Lo agravante: **producción SÍ tiene la guarda.** `_fecha_corte` levanta un
`RuntimeError` que dice "la base quedó a medio configurar". El código grita
y la medición contesta cero. Es la misma lectura escrita dos veces, una con
guarda y otra sin, y la que decide qué se arregla es la que no la tiene.

Por eso, de acá en adelante: **toda consulta parametrizada por un dato de la
base devuelve ese dato como columna.** Las seis de E5 traen ahora `corte`, y
con `(select f0 from c0)` y no un cross join: el cross join con la fila
faltante deja la consulta SIN FILAS, que es la pantalla vacía que no
distingue "todo bien" de "no corrió". El escalar devuelve NULL y la fila
vuelve igual.

Y conviene que haya **un testigo independiente del parámetro**: `e5_0` trae
`ultima_guia_r`, que no depende del corte. Corte en NULL con guías R
recientes al lado es una contradicción visible en la misma fila; sin ese
testigo, todos los ceros se explican solos.

**Y el testigo tiene un SEGUNDO trabajo que no estaba escrito, y es el que
falló el 12/09: es lo único que dice DE CUÁL BASE es una fila.**

En una verificación de migración, **las columnas que importan dan lo mismo
en las dos bases por diseño** — `columna 1 · guarda 1 · controlados 0 ·
ofensores 0` es el resultado bueno en Frutamax y en Palmala. O sea que las
dos filas son **indistinguibles entre sí**, y pegar una creyendo que son las
dos no es un descuido: es el error natural de una salida que se ve igual
venga de donde venga.

Pasó así: se corrieron las dos, se pegó una, y se dio por confirmadas las
dos. Lo que lo delató fue `renglones_7d 410 · ultimo_armado 11/09`, que solo
puede ser Frutamax — Palmala no arma un pedido hace semanas. **El testigo
está puesto para decir si la base vota (corolario 24) y terminó sirviendo
para identificarla**, que es otra cosa.

Por eso, y cuesta cero: **la fila de verificación se pega con el nombre de
la base adelante**, y si las dos filas salen idénticas en todo menos el
testigo, eso es exactamente lo esperado y no una razón para pegar una sola.
La regla de arriba dice correr en las dos; ésta dice **mostrar las dos**.

#### Y LA FILA SE ANOTA EN `db/corridas_confirmadas.md`, no citada en un corolario

**LO VIEJO NO SE RECONSTRUYE, y es decisión del dueño (20/09).** El archivo
tiene 5 filas y hay 321 `.sql`: reconstruir cuáles corrieron es imposible de
memoria, y una lista inventada sería peor que una corta — el que la lea le va
a creer. Queda como está.

**Lo que cambia es de acá en adelante: cada migración se anota APENAS llega su
fila de verificación**, en el mismo turno, no al final del día. Es la misma
regla que la corrección de una oración de este archivo: en el momento, o no se
hace. Y el que anota es el que recibe la fila, no el que la corrió.

Del 18/09, y salió de una auditoría que no pudo contestar una pregunta que
tenía la respuesta en el repo: *"¿las tres migraciones de Vacíos corrieron en
Frutamax?"*. Habían corrido. Lo que faltaba era el registro — **la única fila
anotada era la de Palmala, y estaba citada adentro del corolario de abajo para
ilustrar cómo el testigo dice si una base vota.**

**Una fila citada para ilustrar no es un registro**, y la diferencia no es de
prolijidad: el que audita busca confirmaciones y no la encuentra, porque está
archivada bajo otro tema. El que la escribió tampoco se acuerda. Así que la
pregunta se vuelve irrespondible desde el repo y hay que ir a molestar al
dueño — que es justo lo que un registro evita.

**Y el costo de no tenerlo es el del corte**: sin poder contestar si una
migración corrió, la única salida honesta es tratar el código que depende de
ella como sospechoso. Con 24 verificaciones y dos bases, eso no escala.

**Por qué el registro NO va al pie de cada `.sql`**, que es donde uno lo
pondría: esos archivos se pegan en el editor de Supabase y ninguno puede pasar
los 2500 caracteres. Varios están a menos de cincuenta del límite, así que
cuatro líneas de registro adentro los volverían intruncables — se arreglaría
el registro rompiendo la migración. Va en un archivo aparte, que no se pega en
ningún lado y no tiene límite.

#### Y el TESTIGO dice la BASE; el NOMBRE de la migración dice cuál es (18/09)

El testigo cubre una sola de las dos formas de confundir dos filas, y el 18/09
apareció la otra: **dos filas de la MISMA base y de DOS MIGRACIONES distintas**
se leyeron como las dos bases de una. `1 · 1 · 0 · población · testigo` es el
resultado bueno de cualquiera de las 24 verificaciones de este repo, así que
con el testigo puesto las filas siguen siendo indistinguibles *entre
migraciones* — el testigo contesta "de qué base", no "de qué migración".

Costó un corte de producción: se pidieron las cuatro filas, llegaron dos, se
leyeron como las dos bases al día, y se mergeó código que dependía de una
migración que no había corrido en ninguna. La pantalla de armar pedidos tiró
`column r.cantidad_original does not exist` a la mañana siguiente.

**Y la segunda mitad casi se repite en espejo el mismo día**: llegó UNA fila,
que podía leerse como "las dos bases". Lo que la identificó fue la población
—1921 es Frutamax, 1103 es Palmala— o sea el testigo haciendo otra vez el
trabajo de identificar en vez de el suyo.

Por eso, desde el 18/09, **las 24 verificaciones abren con
`'<nombre_de_la_migración>' as QUE_MIGRACION`**, como primera columna. Es lo
primero que se lee al pegar la fila, y no hay que acordarse de nada:

```
renglon_agregado_a_mano     · 1 · 1 · 0 · 1921 · 19/09
renglon_cantidad_corregida  · 1 · 1 · 0 · 1921 · 19/09
```

Las dos filas de arriba son de la MISMA base y se ve. Antes eran idénticas.

**Las dos columnas son de trabajos distintos y hacen falta las dos**: el
testigo dice de qué BASE, el nombre de qué MIGRACIÓN. Con una sola, la
confusión se muda a la otra dimensión — que es exactamente lo que pasó entre
la mañana y la tarde del mismo día.


Corolario 16, del 08/09, y es una PRÁCTICA, no un patrón de bug: **un test
de "esto no está duplicado" hay que correrlo con la duplicación puesta, o
no sabés si mira algo.**

El test decía `prioridad_de_lote(...).prefiere is TIPOS_LOTE_TRABAJADO`.
No parcheaba nada, comparaba exactamente lo que había que comparar, y aun
así **no podía fallar**: CPython comparte la tupla constante dentro del
mismo módulo, así que la lista copiada a mano da el mismo objeto. Pasaba
con la copia puesta y con la copia sacada.

Es el corolario 9 en su forma más difícil de ver —no hay un `patch` que
delate el tapado— y no hay forma de razonarlo leyendo el test: hay que
romper el código a propósito y mirar si cae. El arreglo terminó siendo un
test de TEXTO (la tupla escrita una sola vez en `core/` y `app/`), que es
lo único que distingue una referencia de una copia.

Y de yapa, el primer regex dio falso positivo con `TIPOS_LOTE_STOCK`, que
contiene los dos nombres seguidos y es otra lista. **Probarlo con la
duplicación puesta también encontró eso**: sin la prueba, el test habría
entrado al repo fallando por una razón equivocada.


Corolario 15, del 08/09: **la asimetría del día del corte llegó a la
OCTAVA, y esta vez no ensució una cuenta: decidió cuánto valía el
problema.**

`corte_fifo_1` medía con `>=` y dio "19 guías, $3.572.620". El número se
citó todo el día como el tamaño de la fuga del reproceso, entró en un
docstring de `app/db.py`, y sostuvo la decisión de no anular 32 guías. El
número real es **$2.798.438,92**: los $774.181 de diferencia eran las 9
guías del día del corte, y la descomposición cerró exacta (`e5_5`).

Dos cosas que se llevan:

1. **Una consulta de diagnóstico con la regla vieja no da un número
   aproximado: da OTRO número.** El corolario 6 ya lo decía y esta es su
   confirmación más cara. El canario del corolario 12 —correrla también
   con la regla vieja y exigir que el resultado SE MUEVA— la habría
   atajado el mismo día que se escribió.
2. **La glosa al contar un resultado se vuelve un hecho.** El doc decía
   "19 de 32 guías R **en dos días**" en cinco lugares. La consulta nunca
   midió dos días: dice `fecha_operacion >= corte`, y sobre Frutamax eso
   son TRES días (05 al 07/09). Nadie inventó el número; alguien le agregó
   un período al contarlo, y el período viajó solo. (Al corregir esto
   escribí "todo desde el 31/08", que también estaba mal: ver el
   corolario 18.)

   Por eso: **al escribir el resultado de una consulta, el recorte se copia
   de la consulta, no de la memoria.** Si el `where` dice `>= corte`, lo
   que se escribe es "desde el corte".


Corolario 14, del 08/09, y va corto: **cuando una decisión estrena letras
—opción A, opción B, caso 1— revisar si esas letras ya están usadas cerca.**

`e5_1_alcance_de_la_mezcla.sql` llamaba A y B a "tamaños de cajón
mezclados" y "cajones y cajas conviviendo". Las opciones de arreglo de E5
se bautizaron A y B en el mismo hilo, y el archivo pasó a decir A y B con
otro significado.

No rompió ninguna cuenta, y **por eso es peor que las otras de esta
familia**: no deja rastro. Un número mal siempre termina apareciendo; un
nombre reusado solo se cobra en la próxima lectura, cuando ya nadie se
acuerda de que hubo dos.

El arreglo es de un minuto si se hace el día que se bautiza: `grep` de la
letra en `db/` y en `docs/`, y el que llegó segundo se queda sin ella.


Corolario 13, del 08/09: **un atajo exacto sobre el conjunto entero deja de
serlo apenas se lo aplica a un subconjunto.** No se rompe: sigue devolviendo
un número, y el número ya no contesta la pregunta.

El freno de `crear_reproceso` compara contra la SUMA DE LOS RESTANTES de los
lotes (`bultos_en_los_lotes`, core/stock.py). `corte_fifo_5b` la calculaba
como `greatest(entradas − salidas, 0)`, y estaba bien: sumados TODOS los
lotes, el restante total es exactamente el neto. El atajo se ahorra rejugar
el FIFO entero y da el mismo número.

Al medir el filtro de `TIPOS_LOTE_TRABAJADO` la pregunta cambió a "¿cuánto
restante queda **de los lotes de materia prima**?", y ahí el atajo miente:
para contestarla hay que saber **cuáles** lotes se comió la demanda, no
cuánta demanda hubo. Dos escenarios con las mismas entradas y las mismas
salidas dan restantes filtrados distintos según el orden. La fórmula vieja
no distingue: devuelve el mismo neto para los dos.

Es la familia del corolario 8 —el alcance— pero corrida de lugar: allá eran
dos cuentas con el mismo nombre y distinto alcance; **acá es la MISMA
fórmula en un universo nuevo**, y por eso no hay dos nombres que comparar ni
nada que grepear. Lo único que cambió está afuera de la fórmula.

**Cómo se busca**: cuando una consulta empieza a filtrar por una dimensión
que antes no miraba, revisar si alguna de sus cuentas era un **atajo que
valía por sumar sobre todo**. Un `sum`, un neto, un promedio, un `max` que
se justificaba con "total, se cancelan" son los candidatos.

**Cómo se evita**: dejar la fórmula vieja de CONTROL al lado de la nueva.
En `e5_3` la columna `frenan_hoy` se calcula con el rejuego completo y tiene
que dar el mismo 0 que dio el backtest viejo; si no lo da, el modelo nuevo
está mal y eso se mira antes que el número que se fue a buscar.


Corolario 12, del 08/09: **la asimetría del día del corte apareció SIETE
veces, y a esta altura eso ya no es una coincidencia: es que el criterio no
está escrito en ningún lado una sola vez.**

La lista completa, para que la próxima no se descubra de cero:

1. La cuenta por ficha (`_SQL_STOCK_PARTIDO`).
2. El pool de segunda.
3. El FIFO, que era la única de las tres que NO la tenía (corolario 5).
4. Las siete consultas de `db/` que quedaron midiendo con la regla vieja
   después de arreglar el piso — una inventó 212 cajas (corolario 6).
5. Entre dos cuentas y no adentro de ninguna: los sueltos derivados por
   resta (corolario 7).
6. El `>=` que escribí al implementar el piso, **cuarenta líneas debajo del
   comentario que dice textual que con `>=` el día del corte se cuenta dos
   veces**. Lo agarró la verificación antes del merge.
7. El `>=` de la medición de la dirección inversa (08/09): con `>=` da 22
   donde la regla buena da 17. Lo agarró un canario puesto a propósito.

Las siete son el mismo hecho del mundo —**el conteo del corte se toma a la
tarde, así que la foto ya viene neta del trabajo de ese día**— reescrito
siete veces en siete lugares que no se nombran entre sí. El corolario 5
decía cómo buscarlas (por las CUENTAS que leen el dato, no por el código);
esto agrega el diagnóstico: **mientras el criterio siga siendo una condición
que cada consulta escribe a mano, va a haber una octava.**

Por eso, hasta que exista un solo lugar donde esté escrito: **toda consulta
nueva que recorte por el corte lleva un canario** — se corre también con la
regla vieja y se verifica que el número SE MUEVA. Un piso que no cambia nada
al romperlo es un piso que no está puesto.

Corolario 11, del 08/09: **una medición que parece la del problema puede
estar midiendo solo su caso más obvio — y el que se le escapa es el más
grande.**

Para medir cuánto armado se costea contra cajones, la primera forma que le
di a la consulta fue un **saldo corrido de la pila de cajas**: cuando el
armado acumulado pasa a las cajas producidas, el excedente salió de un
cajón. Es intuitiva, es corta, y mide **agotamiento**: armé más de lo que
produje.

Se le escapa entero el caso de **orden**: hay diez cajas disponibles, pero
el cajón es más viejo y el FIFO —que ordena por fecha y no mira el tipo de
lote— manda el armado al cajón igual. Para el saldo corrido ese caso es
invisible: el saldo nunca baja de cero.

En el fixture de tres artículos, el caso de orden aporta **10 de 17**. La
versión intuitiva veía **menos del 40%**, y no como un error de precisión
sino como un agujero: el caso más común del problema no estaba en la cuenta.

Es de la familia del corolario 7 pero dado vuelta. Allá una diferencia no
estaba en ninguna de las dos cuentas; **acá la medición está bien y contesta
otra pregunta.** Y como devuelve un número plausible, nada avisa.

**Cómo se busca**: escrita la medición, preguntarse **qué caso del problema
NO puede hacerla dar distinto de cero**. Si hay uno, esa es la mitad que
falta. Y el fixture lleva ese caso adentro a propósito, separado del obvio,
para que se vea cuánto aporta cada uno.


Corolario 10, del 08/09: **un cambio de PRESENTACIÓN puede encontrar un bug
de LÓGICA, y no es donde uno busca.**

El Cotejo se ordenó por desvío para que lo importante quedara arriba —una
mejora de lectura, sin tocar ninguna cuenta—. El orden agrupó las porciones
de cada artículo, y ahí se vio que **las dos tarjetas del mismo artículo se
contradecían**: la de sueltos ofrecía "Ajustar a lo contado" y la de cajas
decía, tres centímetros más abajo, "no ajustes el stock, revisá la guía R".

Las dos siempre dijeron eso. Lo que faltaba era que cayeran juntas. Con
treinta tarjetas mezcladas por orden de conteo, nadie las vio una al lado de
la otra en meses.

**La señal a buscar**: dos vistas del mismo hecho que dan consejos
incompatibles. Se esconden mientras estén separadas —por orden, por
paginado, por pantalla— y el día que se juntan la contradicción salta sola.

De acá en adelante, cuando se cambie un orden, un agrupamiento o un filtro de
listado: **leer dos renglones vecinos que antes no lo eran**. No es
verificación de que el orden funcione: es la única vez que esas dos cosas se
van a mirar juntas.

Corolario 9, del 08/09: **un test que PARCHEA la función que quiere
verificar no verifica nada.** El parche fija el valor y el test comprueba la
aritmética contra su propio invento.

Los dos tests del ajuste desde el Cotejo hacían
`patch("app.main.stock_deposito_de_articulo", return_value=18.0)` y
verificaban que la precarga diera −6. Pasaban. Y pasaban igual con el bug,
porque lo que estaba mal no era la resta sino **cuál** número entraba en
ella: el total del artículo en vez de los sueltos. El parche tapaba
exactamente la línea rota.

Es la misma forma que el assert de substring del 07/09, que matcheaba el
`anulado_el` de `pedidos` creyendo mirar el de `pedidos_renglones`: **el test
miraba algo que se parecía a lo que importaba.**

La regla que se llevan los dos: **cuando un bug aparece en código que YA
tenía test, el test es parte del bug**, y se arregla en el mismo commit. Un
test que no cayó cuando debía es una segunda cosa rota, no un espectador.

Y para escribirlo de nuevo: si hay que parchear, que el parche devuelva un
valor que **haga fallar la versión equivocada**. En el test nuevo del ajuste,
los sueltos y el total están a propósito muy separados (5 contra 35), así que
enchufar el total da −29 y el test cae.

Corolario 8, del 08/09: **dos cuentas con el mismo nombre y distinto
ALCANCE.** No es que digan cosas distintas: es que una es el artículo entero
y la otra una parte, y las dos se llaman "stock".

El Cotejo lista PORCIONES —los sueltos de un artículo y las cajas de cada
ficha— y su diferencia es `contado − sueltos`. Su botón "Ajustar" precargaba
`contado − stock_deposito_de_articulo(id)`, que es el TOTAL: sueltos MÁS
cajas. Verificado con el código real: un limón con 5 sueltos y 30 cajas
armadas da `sueltos = 5` y `total = 35`, así que **contando los 5 exactos la
precarga salía −30** — el botón proponía borrar del total tantos bultos como
cajas armadas tuviera el artículo.

No explotó por diseño sino por suerte: el botón solo se ofrece cuando los
sueltos difieren, y el caso que lo destapó tenía cero cajas.

**Cómo se busca**, y es la más barata de todas: **grepear la función, no el
concepto.** Un solo llamador la usaba mal, y el grep completo tardó un
segundo y acotó el daño. Lo que no sirve es buscar "stock": aparece en todos
lados y no distingue alcances.

**Cómo se evita**: el nombre lleva el alcance. `stock_de_porcion(articulo,
ficha)` no se puede confundir con `stock_deposito_de_articulo(articulo)`, y
la que devuelve el total lo dice en la primera línea del docstring. Y cuando
dos pantallas comparan el mismo número, **las dos salen de la misma
función**: acá `_stock_de_ficha`, que es la que además congela el
`stock_sistema` de cada conteo — así el conteo, el Cotejo y el ajuste no se
pueden separar. (`stock_de_porcion` se borró el 25/09: se quedó sin
llamadores cuando el Cotejo y el ajuste pasaron a leer el cierre del día del
conteo con `_sistema_por_porcion_al_cierre`. El mecanismo no se mueve: el
nombre lleva el alcance, y las dos pantallas salen de la misma función.)

Corolario 7, del 07/09: **una diferencia entre dos cuentas no está en
ninguna de las dos.**

Los bultos SUELTOS de un artículo no se calculan: se derivan por resta
(`_stock_de_ficha` con `ficha_id` None) — el total del artículo menos las
cajas en fichas. Y las dos cuentas tienen pisos distintos: la del total no
tiene ninguno (la rebasea el compensatorio) y la de las cajas tiene el piso
asimétrico del día del corte. **Lo que una ve y la otra no cae ENTERO en la
resta**, con su signo.

Esa es la quinta aparición de la asimetría del día del corte, y la primera
que no está adentro de una cuenta sino ENTRE dos. Por eso no se encuentra
leyendo ninguna de las dos: las dos están bien por separado.

Y hay un corolario del corolario que sirve para descartar: **un término que
está en las dos cuentas con el mismo signo se cancela en la resta.** Eso fue
lo que descartó a E5 como causa del suelto negativo de Mango:
`bultos_primera` suma en el total y suma en las cajas, así que la mezcla de
unidades ensucia las dos por igual y la resta la borra. Verificado cambiando
una sola cosa por vez: sacar la mezcla no movió el número; sacar los armados
del día del corte lo movió exactamente en esos bultos.

**Cómo se busca**, que es distinto de todo lo anterior: cuando un número sale
de restar dos cuentas, se listan los términos de cada una y se marca cuáles
aparecen en las dos. Los que aparecen en una sola son los únicos candidatos.
Los compartidos no pueden ser la causa, por más sospechosos que parezcan.

Corolario 6, del 07/09, y es el mismo día que el 5: **cuando se corrige una
asimetría, hay que revisar también las MEDICIONES, no solo el código de
producción.**

La asimetría del día del corte apareció CUATRO veces, todas con el mismo
síntoma —contar dos veces ese día— y todas descubiertas por separado: en la
cuenta por ficha, en el pool de segunda, en el piso del FIFO, y en las
consultas de diagnóstico que se escribieron para medir el piso.

La cuarta es la que enseña algo nuevo. Al arreglar el piso quedaron siete
consultas de `db/` midiendo con la regla vieja, y una de ellas —el faltante
de cajas del paso 7— **inventó 212 cajas que no existían y mandó a preparar
un conteo del galpón para reconstruirlas.** Tres horas persiguiendo un
número que era el artefacto de la medición, no un hecho.

Una consulta de diagnóstico se siente inofensiva porque no escribe nada. No
lo es: **es la que decide qué se arregla después.** Un dato falso ahí cuesta
más que un bug en producción, porque el bug tiene síntomas y el diagnóstico
falso viene con la autoridad de un número.

De acá en adelante, al cambiar una regla de recorte, de piso o de ventana:
`grep` del criterio viejo **en `db/` y en `scripts/`, no solo en `app/` y
`core/`**. Y las consultas cuya respuesta ya se usó y quedó vieja: o se
corrigen, o se borran. Una consulta corrible con números que sabemos falsos
es peor que no tenerla — la próxima vez que alguien la corra no va a
acordarse de que estaba mal.

Corolario 5, del 07/09: **una asimetría de diseño también es una copia, y
se busca por las CUENTAS que la necesitan, no por el código que la
implementa.**

El conteo físico del corte se toma A LA TARDE, así que la foto del stock
inicial ya viene neta del trabajo de ese día. Eso obliga a una asimetría, y
está contemplada en DOS cuentas: el pool de segunda —con su comentario
explicándolo— y la cuenta por ficha, que lo dice "y por lo mismo". **El
FIFO es la única de las tres que no la tiene**, y por eso su freno mide los
reprocesos del día del corte contra una entrada posterior a ellos: no puede
cubrirlos por construcción. Cuatro guías R de 32 frenaron por eso en el
backtest, sin que hubiera faltado un solo bulto.

Es la misma familia que la copia olvidada, pero **no hay grep que la
encuentre**: las dos cuentas que sí la tienen no comparten una línea de
código con la que no la tiene. Se escribe distinto en cada una. Lo único que
las une es el hecho del mundo —la foto se toma a la tarde—, y eso vive en un
comentario.

De acá en adelante, cuando aparezca una asimetría que nace de CÓMO se toma un
dato en la realidad —a qué hora, en qué orden, con qué recorte—: **enumerar
todas las cuentas que leen ese dato y decidir una por una si la necesitan**,
en el mismo momento en que se descubre. La lista va escrita al lado de la
primera que se arregla; si no, la segunda se arregla meses después y la
tercera nunca.

Corolario 3, del 04/09 y es la CUARTA vez: **cuando una estructura gana un
campo, hay que grepear quién la CONSTRUYE, no el campo nuevo.** Grepear el
campo solo encuentra a los que ya lo usan — los que faltan, por definición, no
lo nombran.

`pedidos_renglones` ganó `ficha_id` el 26/08 a las 19:12. El POST de la
revisión a mano se actualizó; el auto-confirmado, que **rearma el mismo dict**
desde otra fuente, no. **Nueve días de pedidos guardados con el artículo bien y
la ficha en NULL**, sin un solo error. El grep que lo habría encontrado esa
misma noche era **`crear_pedido(`**: dos llamadores, uno actualizado y otro no.

Los dos síntomas que lo escondieron, y valen como señal para la próxima:

- **La base tenía MEDIA regla.** El CHECK prohibía "ficha sin artículo" y
  permitía justo lo contrario. Una guarda que cubre una sola dirección deja
  pasar la otra en silencio: al escribir un CHECK, preguntarse qué pasa con el
  caso espejo.
- **El test comparaba TRES campos de CINCO.** `(sucursal, articulo_id,
  cantidad)` — `ficha_id` no estaba entre los que miraba, así que pasó los
  nueve días en verde. **Un test que compara un subconjunto de campos no
  protege los que no mira.** Cuando lo que se guarda es una estructura, se
  compara la estructura ENTERA: que falle el día que alguien agrega un campo es
  la función del test, no una molestia.

Corolario 5, del 07/09, y es la SEGUNDA vez con el MISMO `{% else %}`: **una
rama por defecto que AFIRMA algo no es un default, es una aserción sin
verificar.**

En Guías R el detalle de consumos pinta cada origen con un `if/elif`, y el
`{% else %}` dice *"Sin lote (se tomó más de lo que había en el sistema)"*. El
CHECK de `reprocesos_consumos.origen` permite SIETE valores y la plantilla
nombraba CINCO. El que faltaba —`stock_inicial`— caía al else, así que un lote
real, con costo real, se mostraba como si no existiera: la guía R176 decía que
se había tomado más de lo que había cuando el freno había corrido bien y había
lotes de sobra.

**Lo agravante es que ya había pasado.** Tres líneas más arriba hay un
comentario que dice, textual: *"Sin este renglón el consumo del compensatorio
caería en la rama de abajo y diría 'se tomó más de lo que había', que es
falso"*. Se arregló ESE valor y no se miró la lista completa del CHECK — el
corolario 2 (cuando se arregla una copia hay que ir a buscar la otra) aplicado
a una lista de valores en vez de a dos funciones.

De acá en adelante: **cuando una rama por defecto afirma algo, se enumeran los
casos que puede recibir contra la fuente que los define** —el CHECK, el enum,
la constante— y el default se queda solo con los que de verdad significan eso.
Y si la fuente puede crecer, el test la lee de ahí en vez de copiarla: ver
`test_los_SIETE_origenes_de_consumo_estan_nombrados_en_la_pantalla`, que parsea
el CHECK de `db/esquema_completo.sql` y falla el día que aparezca un valor
nuevo sin nombrar.

Y la señal para reconocerlo: **un default que dice "esto no existe" es más
peligroso que uno que dice "no sé"**, porque el que lo lee actúa.

Corolario 4, del 07/09: **un assert de substring sobre SQL tiene que calificar
la tabla.** `listar_renglones_pedidos_vigentes` no filtraba
`pedidos_renglones.anulado_el` —era la ÚNICA de diecisiete lectoras que no lo
hacía— y su test decía:

```python
assert "anulado_el IS NULL" in consulta
```

Pasaba, y siempre pasó: matcheaba el `anulado_el IS NULL` de **`pedidos`**, que
sí estaba. El test parecía cubrir el renglón anulado y nunca lo miró. Es la
misma forma que el test de tres campos de cinco —afirmar un subconjunto y creer
que se afirmó el todo—, pero adentro de una sola línea.

Lo que lo esconde es que las dos tablas usan el mismo nombre de columna. Por
eso: en una consulta con más de una tabla, el assert va con el alias
(`r.anulado_el IS NULL`) o con suficiente contexto (`WHERE cliente_id = %s AND
anulado_el IS NULL`) como para que solo pueda matchear lo que se quiso probar.

Y el daño no estuvo en el total, que es lo que lo dejó vivir: estuvo en la
COMPARATIVA de `/gerencia/rentabilidad-real`, donde la teórica salía de esa
consulta y la real de los movimientos de stock, que sí excluyen el anulado. La
diferencia entre las dos —que el docstring de esa pantalla promete que es
*"exactamente la lista de cosas a explicar (merma, reproceso, kilajes), nunca
ruido de cuentas distintas"*— se comía el renglón anulado como si fuera merma.
**Un criterio que se separa no siempre mueve un total; a veces solo ensucia una
resta, y ahí es más difícil de ver.**

## Cuando se excluye algo, hay que mirar contra QUÉ se lo excluye

Del 07/09. Palmala quedó afuera de un backfill, y la razón escrita era **de
stock**. El bug que el backfill venía a reparar **no era de stock**: eran
renglones de pedido sin `ficha_id`. La exclusión era correcta para el motivo
que decía y equivocada para el problema que había, y nadie lo notó porque las
dos cosas viajaban juntas bajo la palabra "Palmala".

La forma del error es la de siempre —dos cosas distintas con el mismo nombre—
pero se busca distinto que las otras dos familias:

- La regla escrita dos veces se encuentra **grepeando el criterio**.
- La regla a la que le creció otra encima se encuentra **grepeando el campo**.
- Ésta se encuentra **releyendo el motivo de la exclusión contra el motivo del
  arreglo**, que es lo único que las separa. No hay grep: los dos textos son
  correctos por separado.

De acá en adelante, al excluir una empresa, un cliente, un artículo o una
fecha de cualquier corrección masiva: **escribir en la misma línea contra qué
se lo está excluyendo**, y al retomar esa exclusión, comparar ese motivo con
el del arreglo que se está por correr. Si no son el mismo, la exclusión no
aplica y hay que decidirla de nuevo.

El costo de no hacerlo no es que el backfill falle: es que **no corre y nadie
se entera**, porque la exclusión parece justificada. Es la misma familia que
el push silencioso — lo que hay que mirar es el estado final, no que nadie se
haya quejado.

**El desenlace, del 07/09:** eran **393 renglones** de pedido sin `ficha_id` en
Palmala, todos recuperables por código exacto. Corrido el backfill, la
verificación dio todo en cero —ningún cruce de artículo ni de cliente— y
`codigo_no_coincide` en cero también, o sea que los 669 renglones con ficha
matchean por código exacto y no hay ninguno asignado por otro criterio.

Lo que estuvo perdido todo ese tiempo no fue el stock —que era la razón por la
que se excluyó a Palmala— sino **la facturación**: sin ficha no hay precio, sin
precio no hay plata, y la pantalla de Márgenes por Artículo mostraba menos días
con entregas de los que hubo. La exclusión se decidió mirando una cuenta y el
daño cayó sobre otra.

## La otra familia: a una regla le crece otra encima

Distinta de la de arriba, y se busca distinto. Acá la regla está escrita **una
sola vez** y sigue diciendo lo que decía. Lo que cambió es que **otra regla,
escrita para otra cosa, terminó pisando su resultado**.

Pasó el 04/09 con `eliminar_compra`. Su docstring dice, textual: *"'pendiente'
y 'rechazado'/'cancelado' se siguen pudiendo borrar sin restricción"*. Era
cierto el día que se escribió. Después se agregó `_auto_retirar_si_corresponde`
—para las recepciones, con su propio argumento válido—, `rechazar_compra` la
reusó, y eso empezó a dejar `estado_retiro = 'retirado'`, que es justo lo que
`eliminar_compra` bloquea tres líneas más abajo. **Nadie tocó la regla de
borrado y la regla de borrado cambió.** Peor: cambió *a veces*, porque si
Logística ya había cancelado el retiro la función no lo pisa — o sea que hoy
borrar una rechazada depende de qué pasó antes en otro módulo.

La diferencia práctica es **cómo se encuentra cada una**:

- La regla escrita dos veces se encuentra **grepeando el criterio**: aparece
  dos veces y las dos difieren.
- Esta se encuentra **grepeando el campo**: alguien lo escribe en un lado y
  alguien lo lee como guarda en otro, y entre los dos no hay ninguna mención
  cruzada. Ninguna de las dos funciones nombra a la otra.

De acá en adelante: **cuando una función nueva escriba un campo de estado,
grepear quién más LEE ese campo como guarda**, antes de darla por hecha. Y al
revés: una guarda que depende de un campo que escriben otros lleva escrito de
dónde puede venir ese valor.

La señal de que ya pasó es la misma en las dos familias: **un comentario que
afirma algo que dejó de ser cierto.** Ninguno de los dos mintió cuando se
escribió — envejecieron sin que nadie los tocara. Es el mismo síntoma del
docstring de la alerta que explicaba el bug que la pantalla seguía teniendo.

Corolario 23, del 08/09, y es el primero de esta lista que anota un ACIERTO
—no un bug— porque el mecanismo es el mismo de siempre visto del lado bueno:
**una consulta barata puede borrar una pantalla entera antes de escribirla.**

Estaba planeado el desglose del Remanente por contenido de cajón: pantalla
nueva, renglón "sin dato", y aviso de descuadre para cuando el desglose no
sumara al total. Antes de codear se corrieron dos consultas de menos de 2500
caracteres. `arts_mezclados` dio **0**: ningún artículo tenía dos tamaños de
cajón conviviendo, así que **el Remanente ya sumaba bultos comparables** y no
había nada que desglosar. Ver `docs/desglose_del_remanente_por_contenido.md`.

**Y EL 18/09 SE RETOMÓ, que es exactamente lo que el propio documento decía
que iba a pasar** (*"si algún día se compra el mismo artículo en dos formatos,
esta consulta lo va a mostrar y se retoma"*). `kilajes_1` encontró cinco
artículos multiformato en las dos bases. **No es que la medición del 08/09
estuviera mal: es que `remanente_1` recorta DESDE EL CORTE**, o sea tres días
de compras el día que se corrió, y `kilajes_1` mira noventa. Las dos son
ciertas sobre su ventana, y una sola de las dos contesta "¿este artículo se
compra en más de un formato?".

Eso deja el aviso para la próxima vez que una consulta barata borre una
pantalla, y es la mitad que a este corolario le faltaba: **antes de dar por
inexistente un caso, mirar contra qué VENTANA se lo buscó.** Un cero sobre
tres días de compras no dice lo mismo que un cero sobre noventa, y los dos se
imprimen igual. Es el corolario 69 —el recorte de la medición no es el de la
decisión— del lado de NO construir, que es donde no deja rastro: la pantalla
que no se hizo no se queja.

Es el corolario 6 dado vuelta. Allá una medición falsa mandó a perseguir 212
cajas que no existían: **la consulta de diagnóstico decide qué se arregla
después.** Acá decidió qué **no se construye**, que es la misma potencia
usada temprano. La diferencia entre los dos casos no es la suerte: es que
ésta se corrió ANTES y aquélla se leyó DESPUÉS.

Y la parte que se puede repetir: **la premisa se mide, no se hereda.** "El
Remanente no puede sumar bultos de distinto contenido" era verdad sobre el
ESQUEMA —dos formatos del mismo artículo son posibles— y falsa sobre los
DATOS. Un requisito que nace de lo que la base permite, y no de lo que la
base tiene, se verifica con un `count(distinct ...)` antes de diseñar nada.

El otro pedazo, y es el que da el criterio para leer un porcentaje feo: el
15,6% "sin dato" **cerró exacto contra una sola fuente** (`809+674+0+274 =
1757`, `274/1757 = 15,59%`, todo movimientos, `cajas_sin_ficha` = 0). Un
número que se explica ENTERO por un origen conocido y transitorio no es
deuda: es la foto del corte consumiéndose. **Antes de construir para cubrir
un "sin dato", hay que ver si el sin-dato tiene UNA causa o varias** — con
una, casi siempre se apaga solo.

Corolario 24, del 08/09, y es el que más cara va a salir si se olvida:
**una base PARADA contesta cero a todo, y el cero se lee como "acá no hay
problema".**

Salió de costado corriendo `nulos_1` en las dos bases: **Palmala no
recepciona una compra desde el 01/09** — siete días. Sumado a que no arma
pedidos hace diez y a que no tiene una sola guía R, esa base está
prácticamente detenida. El dato no es de software y el negocio es de
Lionel; lo que es nuestro es la consecuencia sobre las mediciones.

Y la consecuencia es fea porque **es indistinguible de la buena noticia**:

- `e5_3` sobre Palmala: `frenan_con_a = 0`. Se lee "A no rompe nada".
- `e5_4` sobre Palmala: `mal = 0`. Se lee "acá E5 no pasa".
- `tildes_1` sobre Palmala: 0 colisiones. Ése sí es real — mide fichas
  cargadas, no actividad.

Los dos primeros ceros **no dicen que el arreglo esté bien: dicen que no
hubo nada que medir.** Y es exactamente la familia de la ausencia de filas
que mordió con el backfill, pero peor: allá la pantalla vacía al menos se
veía rara. Acá vuelve una fila, con un cero prolijo adentro, y el cero es
verdadero. No hay nada que se vea mal.

Por eso, de acá en adelante, y es barato: **toda medición sobre una base
trae un TESTIGO DE ACTIVIDAD al lado del número** — la última recepción, la
última guía R, el último pedido armado. `nulos_1` ya lo trae
(`ultima_recepcion`), y fue justamente esa columna la que destapó esto: sin
ella el `post 36` de Palmala se leía como una base en marcha.

Un cero con "última recepción hace siete días" al lado es un cero que se
entiende. Un cero solo es un cero que miente por omisión — y encima
tranquiliza, que es lo peor que puede hacer una medición.

Corolario del corolario, para el momento de decidir: **el corolario 17 dice
correr en las dos bases; éste dice que correr no alcanza.** Una medición que
sale bien sobre una base detenida no es una segunda confirmación: es la
misma confirmación contada dos veces. Si el testigo dice que la base está
quieta, esa base **no vota**, y hay que decirlo así en vez de sumarla como
si hubiera confirmado algo.

**Y dado vuelta como regla operativa, del 09/09**, que es la forma en que
sirve el día que hay que decidir: **mientras Palmala esté parada, cualquier
verificación que dé bien ahí no verifica nada. Lo que hay que mirar es
Frutamax.**

Palmala sirve para UNA cosa y hay que usarla para esa: **confirmar que una
migración no explota.** Eso no depende de que haya actividad —el `alter
table` corre igual sobre una tabla quieta— y es información real: si el
esquema de las dos bases se separó, ahí se ve.

Todo lo demás que se mida ahí es la pantalla vacía del backfill con otro
disfraz. Y la trampa no es que engañe: es que **tranquiliza**. Un "cero
ofensores" sobre 51 conteos cuyo último es de hace dos semanas se lee igual
que uno sobre una base en marcha, y el que lo lee suma dos confirmaciones
donde hay una.

Aplicado el 09/09 con `es_segunda`: la migración corrida en las dos bases
—eso vale, y valió—, y el `conteos_de_segunda = 0` de Palmala descartado a
mano por su `ultimo_conteo` del 26/08. Lo que decide si las tres pantallas
andan es Frutamax.

### Y "NO VOTA" ES POR MEDICIÓN, NO POR BASE (18/09, y es del dueño)

Los dos párrafos de arriba están escritos como si *"Palmala no vota"* fuera
un **atributo de la base**, y así se venía aplicando desde el 09/09: se
descartaba de entrada cualquier número que saliera de ahí. **Eso es un
recorte de más, y el mecanismo del corolario 24 nunca dijo eso.**

Lo que el 24 dice es que **el TESTIGO decide**, y cada medición tiene el
suyo: la última recepción, la última guía R, el último pedido armado. Son
preguntas distintas y pueden contestar distinto sobre la misma base. Una
base puede estar quieta para los armados y en marcha para las recepciones —
y entonces **vota en una medición y no en la otra**.

**El caso que lo destapó**, y es la mejor prueba de que el atajo estaba mal:
la verificación de la migración de Vacíos trajo, el 18/09,

    PALMALA  1·1·1·1·1·1·1·1 · 44 proveedores · última recepción 17/09

y ese testigo es `max(procesada_el) where estado = 'recepcionado'` —
**exactamente la misma pregunta** que sostiene el *"no recepciona desde el
01/09"* de este archivo. Palmala recepcionó ayer. O sea que toda medición
sobre RECEPCIONES que se descartó ahí en los últimos días se descartó sin
mirar su testigo.

**Cómo se aplica, y cuesta lo mismo que descartarla a mano**: antes de
decidir si una base vota, mirar **el testigo de ESA medición** —no el que
uno recuerda de otra— y su POBLACIÓN. `pesaje_1` trae `recepciones_2d` y
`recepciones_7d` justamente para eso: con números parecidos a los de
Frutamax el resultado es un dato, y con 2 sobre 5 el cero de al lado se
descarta, pero **descartado por su propio denominador y no por el nombre de
la base**.

**Y ES LA ORACIÓN QUE EXPIRA, en su forma más cara.** El MECANISMO —una base
quieta contesta cero a todo— no envejece nunca. Lo que envejeció es el
ESTADO que se anotó al lado para ilustrarlo, y como ese estado se escribió en
imperativo (*"lo que hay que mirar es Frutamax"*) se leyó como regla. Un
estado con forma de regla es peor que un estado: **nadie lo vuelve a
verificar, porque las reglas no se verifican.**

La forma de escribirlo que no expira es la que este corolario tiene arriba:
*el testigo dice si la base vota*. La que expira es *esta base no vota*.

**CONFIRMADO el mismo día, y no era chico lo que se estaba descartando**:
`pesaje_1` sobre Palmala dio **70 recepciones en 7 días y 240 en 90** —
población de sobra— y **16 de 40 sin ninguna evidencia de pesaje en dos días,
contra 6 de 44 en Frutamax**. O sea que la base "que no vota" tenía la tasa
TRIPLE, y el atajo de descartarla por nombre venía tapando el número más
grande de los dos. Ver "El pesaje" más arriba.

Y la mitad que no cambia: **Palmala sigue sin votar en guías R y en
armados**, porque esos testigos siguen diciendo lo que decían. Las dos cosas
son ciertas sobre la misma base al mismo tiempo, y eso es exactamente lo que
un atributo de la base no puede expresar.


#### Y EL 19/09 EL DUEÑO LA CERRÓ PARA ESTE PERÍODO: Palmala no vota, y punto

Del 19/09, y es una decisión suya, con fecha: *"Palmala no está funcionando y
no vota para nada. Dejemos de medir contra esa base."*

**Eso NO contradice lo de arriba: lo aplica.** El mecanismo sigue siendo el
del 24 —el testigo decide— y lo que el dueño está declarando es un HECHO DEL
NEGOCIO que ningún testigo nuestro puede ver: **esa base dejó de operar.** Un
testigo dice cuándo fue la última recepción; **no dice si va a haber otra**.
Eso es el corolario 84 —lo que el dueño sabe del galpón se le pregunta, no se
le discute— y la recepción del 17/09 que el 18/09 hizo votar a Palmala era la
cola de una base que se estaba apagando, no la señal de una que anda.

**Y va escrita con su condición de vencimiento, para no repetir el error que
esta misma sección describe**: el 09/09 se escribió *"lo que hay que mirar es
Frutamax"* en imperativo, se leyó como regla, y nadie la volvió a verificar en
nueve días. Así que acá queda como lo que es —un ESTADO, con dueño y con
fecha—:

> **Desde el 19/09 y hasta que el dueño diga lo contrario, ninguna medición
> sobre Palmala vota.** Lo que la reabre es que él avise que esa base volvió a
> operar; no un testigo que dé una fecha reciente.

**Lo que Palmala sigue sirviendo es lo de siempre, y es real**: confirmar que
una migración no explota. Un `alter table` corre igual sobre una tabla quieta,
y si los dos esquemas se separaron, ahí se ve. Eso no es medir: es probar que
el SQL parsea contra ese esquema.

**Y lo que costó no tenerlo escrito, el mismo 19/09**: el 89% de renglones sin
tildar de Palmala me llevó a una conclusión sobre CÓMO SE TRABAJA que era un
artefacto del abandono. El mecanismo está en el corolario 88 —una base parada
contesta casi todo a una medición de AUSENCIA, y ahí el testigo no salva,
porque la población está de verdad.
Corolario 25, del 08/09, y es el hermano exacto del 23: **un argumento
puede ser CORRECTO y llevar al número equivocado, porque lo que falla no es
el razonamiento sino la premisa que nadie midió.**

El Cotejo y el Excel restaban contra `conteos_stock.stock_sistema`, la foto
del sistema congelada en el instante del conteo. El argumento escrito en dos
docstrings para defenderla era éste, y sigue siendo válido: **comparar
`físico(ayer)` contra `sistema(hoy)` mete adentro de la resta todo
movimiento legítimo posterior** — una caja contada ayer y despachada hoy
sale como diferencia sin que nada esté mal. Contra la foto, los dos números
son del mismo instante y la comparación es limpia.

La premisa era que **la foto describe el sistema de ese instante**. Es
falsa: el conteo se toma en el piso y **el trabajo del día se carga
después**, así que la foto se saca con el sistema a medio actualizar. Los
dos números del mismo instante no son comparables porque uno de los dos
todavía no terminó de existir.

Mango es la medida del daño: contó 1 con el sistema en −12, el trabajo se
cargó **catorce minutos más tarde**, y la tarjeta mostró +13 para siempre
sobre un desvío que ya no existía.

Tres cosas que se llevan:

1. **La validez de un argumento no dice nada de su premisa**, y un argumento
   bien construido es más difícil de revisar que uno flojo: se defiende
   mejor, convence más rápido y **se copia a los docstrings**, donde después
   envejece con toda la autoridad de algo razonado. Los dos que había acá
   explicaban con precisión por qué el número tenía que salir de la foto.
2. **La premisa era medible y nadie la midió.** "¿La foto del conteo está
   completa cuando se saca?" se contesta con una consulta de dos líneas
   —comparar `creado_en` del conteo contra el `creado_en` de las guías R de
   ese día— y decidía todo el diseño. Es literalmente el corolario 23: la
   premisa se mide, no se hereda. Allá era el esquema contra los datos; acá
   es **cómo se toma el dato en la realidad contra lo que el diseño supone**,
   que es la misma familia que el corolario 5.
3. **Cuando una objeción válida defiende un diseño equivocado, casi siempre
   hay una salida que la satisface por el otro lado.** La objeción de verdad
   era "el Excel y el Cotejo van a decir números distintos el mismo día". Se
   resolvió moviendo **los dos** a Sistema − Físico de ahora, no dejando los
   dos en la foto. De yapa, la diferencia ahora se verifica restando dos
   columnas vecinas del archivo, que era justo lo que la columna "Sistema al
   contar" venía a permitir — y por eso esa columna se fue.

Y la que NO se tocó, dicho acá para no re-derivarlo en tres meses: el Cotejo
de VACÍOS (`listar_ultimos_conteos_vacios`) sigue midiendo contra la foto más
los ajustes posteriores, y está bien. Ahí el circuito es otro —los cajones no
tienen un "trabajo del día" que se cargue después del conteo— así que la
premisa que acá era falsa, allá se cumple. **Buscar la otra copia es
obligatorio (corolario 2); copiarle el arreglo, no.**

### Y EL 25/09 SE MOVIÓ OTRA VEZ: al CIERRE DEL DÍA DEL CONTEO (dueño)

"Sistema de ahora" arregló el Mango y dejó otro agujero: un conteo de hace
una semana restado contra hoy mete en la diferencia todo lo que se movió en
el medio. Es exactamente la objeción que este corolario da por válida en su
primer párrafo, y quedó viva para los conteos viejos. `cotejo_1` (Frutamax,
25/09) midió que no era un borde: **de 43 tarjetas, 17 eran de antes de
ayer**, y la más vieja del 26/08.

**Ahora cada tarjeta compara contra el cierre del día de SU conteo**
(`_sistema_por_porcion_al_cierre`, que sale de `_remanente_a_fecha`). Eso
satisface las dos objeciones a la vez: el cierre reconstruido incluye lo que
se cargó tarde con la fecha de ese día (el Mango) y no incluye lo que pasó
después (el conteo viejo). Y es del MISMO día porque se cuenta a la tarde:
429 de 574 conteos entre las 14 y las 18.

- **El déficit y los signos opuestos van al mismo cierre.** Dos porciones
  del mismo artículo contadas en días distintos no firman una guía R mal
  atribuida: el movimiento del medio explica cualquier signo.
- **Antes del corte no hay contra qué**: la tarjeta lo dice y va al final.
- **El ajuste propone la DIFERENCIA de ese día**, aplicada hoy, y recalcula
  el cierre en el server en vez de leerlo de la URL. Ya no propone "dejarlo
  en lo contado", que con un conteo viejo pisaba el stock de hoy.

**CERRADO por el dueño el 26/09: NO se corta por hora.** 59 de 574 conteos
(10%) son de antes de las 10, y van contra el cierre del MISMO día, igual que
los demás. El motivo es del galpón: *a la mañana ya entra y sale mercadería*,
así que el cierre del día anterior tampoco sería el correcto para esos
conteos. Ninguno de los dos cierres es exacto para un conteo de la mañana, y
el del mismo día es el que ya usan los otros 515. No hace falta medirlo.

**Y la otra copia NO se toca, CERRADO por el dueño el 26/09**: el Remanente a
una fecha y su Excel (`_pegar_conteos_a_porciones`) restan el último conteo
hasta esa fecha contra el sistema de esa fecha, así que un conteo viejo tiene
el mismo problema ahí. **Se deja como está porque el dueño no usa esa
pantalla.** No es un pendiente: es la decisión de no copiarle el arreglo.

Corolario 26, del 08/09, y es la regla escrita dos veces con un agravante
que no habíamos visto: **no se separaron por descuido — se escribieron
distinto A PROPÓSITO, una como pared y otra como aviso, y nadie revisó
nunca si esa diferencia tenía sentido.**

El chequeo es el mismo: la fecha que dice el asunto del mail no puede estar
a más de cinco días de la llegada. Estaba en dos lugares:

- `_intentar_auto_confirmar` — **pared**: `return False`, el mail queda
  pendiente y lo mira una persona.
- La revisión a mano — **cartel**: `aviso_fecha`, y a guardar.
- Y `confirmar_pedido`, que es el que ESCRIBE, no lo miraba en absoluto.

Un mail con el día y el mes dados vuelta ("Pedido Dia 09-08" llegado el
08/09) quedó fechado **treinta días atrás**. El automático lo frenó bien.
Lo confirmó una persona, con el cartel a la vista.

**La ironía es el hallazgo: el candado automático era más estricto que el
manual, y el camino flojo era el que usa la gente.** La intuición dice lo
contrario —"el humano revisa, la máquina no"— y por eso la asimetría se
escribió sin que nadie la discutiera: suena razonable. Pero un cartel que
se puede pasar con el mismo click que ya se iba a hacer no es una revisión
humana: es un cartel.

Tres cosas para la próxima:

1. **Cuando la misma regla existe en dos fuerzas, eso se DECIDE, no se
   hereda.** La pregunta no es "¿está en los dos lados?" sino "¿por qué
   allá frena y acá avisa?". Si la respuesta no está escrita, no se
   pensó — se escribió cada una en su momento y nunca se miraron juntas.
2. **La guarda va donde se ESCRIBE, no donde se muestra.** El aviso vivía
   en la pantalla de revisión y el `POST` que guarda no revalidaba nada:
   un formulario armado a mano entraba sin ver el cartel. El servidor es
   el que decide; el HTML es la forma de cumplirlo cómodo.
3. **Entre trabar y avisar hay un escalón, y casi siempre es el que va: el
   TILDE.** "Sí, la fecha es correcta" convierte un reflejo en una
   decisión sin quitarle el poder al que sabe. Trabar habría sido peor —la
   fecha rara puede ser real—, y avisar ya se probó que no alcanza.

   **Y CUÁL escalón va lo decide si el caso riesgoso es el NORMAL o la
   EXCEPCIÓN**, que es la precisión que le faltaba a este punto y la puso el
   dueño el 18/09 sobre "vino armada". El tilde sirve cuando el caso normal
   es un click —la fecha del mail está bien casi siempre— y la excepción es
   rara: ahí un paso más se lo cobra a todos para atajar a uno. Cuando la
   marca **es** la excepción —son pocas por mes y la de todos los días es no
   marcarla— el que corresponde es el modal que obliga a leer: no le cuesta
   nada al caso normal, porque el caso normal no pasa por ahí.

   Y hay una segunda diferencia entre los dos, que es la que hace que un
   tilde no habría alcanzado acá: **el tilde pregunta "¿estás seguro?" y el
   que se equivocó también está seguro.** Lo que frena el dedazo no es
   confirmar: es LEER qué dice la marca. Por eso el texto del modal cuenta
   las dos consecuencias —se genera una guía R sola, esas cajas salen del
   stock— y dice con todas las letras cuándo NO va.

   **Y HAY UN TERCER CASO, del 19/09 y también del dueño: que la acción
   riesgosa sea la LEGÍTIMA Y FRECUENTE. Ahí no va ningún escalón — va el
   AVISO, arriba del campo.** Cambiar el precio de una compra ya recepcionada
   recostea hacia atrás todo lo que el FIFO le atribuye a ese lote, y aun así
   **es lo que hay que hacer casi siempre**: el comprador renegocia. Un
   `confirm()` ahí *"lo pasa el caso normal todas las veces"*, o sea que se
   lo cobra a todos y no ataja a nadie — es el escalón que se aprende a
   esquivar, que es la forma de no tener ninguno.

   Los tres, entonces, y lo que los ordena es la FRECUENCIA de lo riesgoso:

   | lo riesgoso es… | qué va |
   |---|---|
   | la excepción rara, y el caso normal es un click | el **tilde** |
   | la excepción, y el caso normal ni pasa por ahí | el **modal** que obliga a leer |
   | **la acción legítima de todos los días** | **ningún escalón: el aviso, ANTES del campo** |

   Y la tercera fila sale de la misma frase que las otras dos —*el que se
   equivocó también está seguro*— llevada un paso más: si la acción es
   legítima, **no falta una decisión, falta información.** Preguntar "¿estás
   seguro?" sobre algo que se hace todos los días no agrega ninguna, y lo que
   sí agrega es decir qué se lleva puesto y nombrarlo —acá, las guías R que
   quedan con su costo congelado—. Por eso el aviso va ARRIBA: debajo del
   campo llega cuando el número ya se tipeó.

Y el diagnóstico también se llevó una lección: la primera hipótesis fue
que el auto-confirmado ignoraba el chequeo. **Se descartó corriendo la
función real con el asunto real**, no leyendo el código: `'Pedido Dia
09-08'` con llegada 08/09 devuelve 2026-08-09, 30 días, y el candado
devuelve False. Leer el `if` habría alcanzado para confirmarlo, pero
correrlo es lo que lo volvió un hecho.

Corolario 27, del 08/09: **la MISMA propiedad de un `count(*)` es lo que
salva a una consulta de verificación y lo que arruina a una guarda.**

La regla que ya teníamos dice que una consulta de verificación devuelve
CONTEOS y no una lista, porque un agregado **siempre trae una fila** y así
el cero se ve — con una lista, "no hay ninguno" y "no corrió" son la misma
pantalla vacía.

En una guarda de plpgsql esa misma propiedad la vuelve inútil:

```sql
select count(*) ... into v_armados from pedidos p ... where p.id = v_pedido;
if not found then raise exception 'no existe'; end if;   -- NUNCA se dispara
```

`not found` no se dispara **jamás** después de un agregado: la fila vuelve
con 0 aunque no haya nada que contar. Probado en los cuatro casos: anular
un id inexistente salía `DO` sin hacer nada, y sobre un pedido YA anulado
**pisaba su `anulado_el` original con la fecha de hoy** — que es peor que
no anular, porque borra cuándo se anuló de verdad.

La forma correcta es separar las dos preguntas: **la existencia con un
`select` SIN agregado** (ahí `not found` sí funciona) y el conteo después,
ya sabiendo que la fila existe.

Lo que se lleva, y es más general que el `count`: **una propiedad no es
buena o mala, lo es para un uso.** "Siempre devuelve una fila" es
exactamente lo que se quiere al MOSTRAR y exactamente lo que no se quiere
al DECIDIR. Cuando una técnica se copia de un contexto al otro, hay que
preguntarse qué propiedad la hacía servir allá y si acá juega para el
mismo lado.

Y el detalle del turno, que es el de siempre: **lo agarró probar los
cuatro casos, no leer el bloque.** El `if not found` leído se ve
perfectamente razonable — es la línea que uno escribiría—, y solo corrida
contra un id inexistente muestra que no hace nada.

**La trampa CRUZA DE LENGUAJE**, y eso es lo que la vuelve peligrosa: no
es una particularidad de plpgsql, es del AGREGADO. El mismo día apareció
en Python, al escribir la versión de aplicación de ese mismo bloque:

```python
cursor.execute("SELECT count(*) FROM pedidos WHERE id = %s", (pedido_id,))
if cursor.fetchone() is None:   # NUNCA es None
```

`fetchone()` de un `count(*)` devuelve `(0,)`, jamás `None`. Es el mismo
hecho —un agregado sin `group by` siempre produce exactamente una fila— y
por eso todos los idiomas que existen para preguntar "¿había algo?" fallan
igual: `not found`, `fetchone() is None`, `rowcount == 0`, un `if not
filas`. La forma correcta es la misma en los dos: **preguntar por la
existencia con un `select` SIN agregado, y contar después.**

Corolario del corolario, para reconocerlo sin haberlo sufrido: **si la
consulta que sostiene una guarda tiene `count`, `sum`, `max` o `avg` en el
`select`, la guarda no puede distinguir "no hay" de "hay cero".** No hace
falta razonar el lenguaje: alcanza con mirar si hay un agregado.

Corolario 28, del 08/09, y es el caso más limpio del **comentario que
envejece**: no envejeció con el tiempo — **envejeció en el mismo commit que
lo volvió falso**, y ninguno de los dos lo vio.

La pantalla de armar, cuando el desglose vuelve sin nada repartido, decía:
*"No hay lotes cargados de este artículo a esa fecha: salió sin lote."* Era
cierta: hasta ese día, la única forma de que la propuesta viniera vacía era
que no hubiera lotes. La pared del armado agregó una segunda —para un
artículo con envase de ficha, el cajón **está ahí**, listado y con 0
propuestos, y la pared simplemente no lo ofrece— y la frase pasó a mandar a
buscar mercadería que no falta.

Los otros comentarios envejecidos de esta lista (`eliminar_compra`, el
docstring de la alerta) se separaron **meses** después, por un cambio que
alguien más hizo en otro módulo. Éste no: **el mismo diff que agregó el
camino nuevo dejó la frase vieja tres líneas más abajo.** No hay historia
que reconstruir ni módulo lejano que culpar. Estaba a la vista, en el
archivo abierto, en la revisión.

Y por eso la señal es distinta de "buscar comentarios viejos", que es una
tarea sin fin y que nadie hace: **cuando un cambio hace que una rama del
código deje de alcanzarse por el motivo de antes, el texto de esa rama hay
que releerlo.** Es una pregunta corta y se hace en el momento: *toqué esta
condición — ¿qué dice el `else`?*

Aplica a cualquier rama que AFIRME algo sobre por qué llegó ahí: el `else`,
el caso vacío, el mensaje de error, el default. Engancha con el corolario 5
—*una rama por defecto que afirma algo es una aserción sin verificar*— y le
agrega **cuándo** verificarla: el día que se agrega un camino que puede
caer en ella.

Corolario 29, del 08/09: **un requisito derivado de una premisa que nadie
enunció.** No es un dato mal medido ni una copia olvidada: es trabajo
entero —una prueba de campo, una decisión de diseño y casi un cambio al
pipeline de todas las fotos del sistema— construido sobre algo que nadie
pidió.

El pedido era "foto de la mercadería sobre la balanza al recepcionar". Se
leyó como **"foto legible del número del display"**, y esa lectura nunca
se dijo en voz alta: entró como si fuera parte del pedido. De ahí salió,
en orden, una tensión de diseño inventada ("la foto tiene dos trabajos y
tiran para lados opuestos"), una prueba de tres distancias en el galpón,
la medición del dígito en píxeles, la propuesta de subir el lado largo a
2000, un parámetro nuevo en `_comprimir_foto_jpeg` —mergeado— y la idea de
guardar un recorte del display aparte.

Lo que se necesitaba era ver **que la mercadería estaba sobre la balanza y
que la balanza estaba pesando**. A 1000 px eso ya se veía. Todo lo demás
sobraba.

**La pregunta que lo destrabó fue "¿para qué querés leer el pesaje?", y la
hizo el dueño, no nosotros.** Y la respuesta la cierra sin apelación: **el
operario redondea.** Aunque el display se leyera perfecto, el número no
coincidiría con lo cargado. Cotejar foto contra sistema no tiene sentido
acá, y sin cotejo la legibilidad no vale nada. Ese hecho no está en el
código ni en la base: está en cómo se trabaja.

Es pariente del corolario 25 —la premisa que nadie midió— pero un escalón
más arriba y peor: **allá la premisa era falsa; acá el REQUISITO no
existía.** Una premisa falsa se descubre midiendo. Un requisito inventado
no se puede medir, porque las mediciones que uno diseña salen de él: la
prueba de las tres distancias estaba bien hecha, contestó exactamente lo
que preguntaba, y la pregunta era de más.

**La señal, y es la única barata que hay: cuando una prueba empieza a
costar más que la función, revisar qué requisito la está pidiendo y quién
lo enunció.** Acá la función era subir un archivo; la prueba pedía ir al
galpón, sacar fotos a tres distancias, cuidar la luz y no mandarlas por
WhatsApp. Esa desproporción era el aviso, y estuvo a la vista todo el
tiempo.

Y un detalle del método que ESTA vez salió bien y conviene repetir: el
parámetro se mergeó con el default en 1000, así que revertirlo fue un solo
`git revert` y ningún llamador existente se enteró. **Un cambio que
todavía no tiene usuarios se escribe de forma que deshacerlo sea gratis**,
porque el requisito que lo pidió puede no sobrevivir al día.

Corolario 30, del 08/09: **una guarda que compara contra un PLACEHOLDER
verifica la ausencia del texto de ejemplo, y el texto de ejemplo es
exactamente lo que el usuario va a reemplazar.**

El bloque para borrar una foto tenía que abortar si nadie había pegado la
ruta. La guarda era la obvia:

```sql
declare ruta text := 'PEGAR-ACA-LA-RUTA-DEL-PASO-1';
begin
  if ruta = 'PEGAR-ACA-LA-RUTA-DEL-PASO-1' then raise exception ...
```

Se lee perfecta. Y falla al revés de como uno espera: no deja pasar el
caso malo, **frena el bueno.** Quien pega una ruta hace un
buscar-y-reemplazar **global** —es lo natural, el placeholder está dos
veces— y entonces las dos mitades cambian juntas, la comparación vuelve a
dar `true`, y el bloque aborta **con la ruta correcta puesta**.

El arreglo es cambiar qué se pregunta: **no "¿sigue estando el texto de
ejemplo?" sino "¿esto tiene FORMA de dato?"**. Una ruta del bucket matchea
`^[0-9]{4}-[0-9]{2}-[0-9]{2}/.+\.[a-z]+$`; el placeholder no la matchea
nunca, y ningún reemplazo global puede hacer que la matchee. La regla vale
para cualquier valor a pegar: un id se valida `> 0`, una fecha que parsee,
un código con su patrón.

**Cómo apareció, que es lo de siempre**: no leyendo el bloque —leído se ve
bien— sino corriendo los cuatro casos. Y apareció **por el caso que tenía
que PASAR**, no por uno que tenía que fallar. Los tres casos de aborto
daban todos verde; el único que lo destapó fue el bueno, que abortó cuando
no debía.

Eso último es lo que más se lleva: **una batería de casos negativos puede
estar toda en verde con la guarda rota.** Si todos los casos que se prueban
esperan un error, cualquier guarda que aborte siempre los pasa a todos. El
caso feliz no es un trámite al final de la lista: es el único que
distingue "la guarda funciona" de "la guarda siempre frena".

Corolario 31, del 08/09, y es de DISEÑO, no de bugs: **una operación que
existe, está probada, y no tiene puerta en la pantalla.** El sistema sabe
hacerla —el SQL está escrito y corrido— pero la única forma de pedírsela es
el editor de la base.

Apareció DOS veces el mismo día, y por eso vale anotarlo:

1. **Anular un pedido entero.** No había ruta; se hizo con SQL a mano. La
   frase que lo cerró fue del dueño: *"que la única forma sea SQL a mano es
   un agujero: hoy fui yo, mañana es un operario que no puede"*. Se
   construyó la ruta ese mismo día.
2. **Deshacer una recepción.** Depósito no puede: su Deshacer está bloqueado
   para las recepcionadas ("para corregirla hace falta Gerencia"). Una
   recepción apretada por error termina en el editor. **Queda abierto si va
   un botón** — ver `db/revertir_una_recepcion.sql`.

Y una tercera, más chica, del mismo día: **borrar una foto de balanza
sola**. La única ruta que devuelve su ruta para sacarla del Storage borra la
COMPRA entera.

**La señal para reconocerlo**, y es barata: cuando por segunda vez se
escribe un `.sql` a mano para la misma FORMA de operación, eso ya no es un
arreglo puntual — es una función que falta. La primera vez es un
incidente; la segunda es un diagnóstico.

### El TERCER disfraz: la operación existe, pero solo su versión DESTRUCTIVA

Del 19/09, y es del dueño en una frase: *"la única salida hoy es anular y
recargar. Es la tercera vez esta semana que algo se arregla así."*

**Corregir la fecha de una guía R** no era un `.sql` a mano ni una ruta sin
botón: se podía hacer, con dos clicks, desde una pantalla que está a la
vista. Anular y volver a cargar. O sea que las dos señales que este corolario
enumera —el archivo que se repite y el barrido de pantallas sin link— salen
las dos en verde, y la operación igual falta.

**Cómo se reconoce, y es lo único nuevo**: el que la hace **paga un costo que
no tiene nada que ver con lo que quería cambiar.** Acá quería mover un día y
tenía que borrar los consumos, el costo congelado y el número de guía, y
rearmar todo a mano. Esa desproporción es la señal, y es la misma forma del
corolario 29 al revés: allá una prueba costaba más que la función y delataba
un requisito inventado; acá una corrección cuesta más que el dato que corrige
y delata una función que falta.

La pregunta que lo encuentra, y se hace cuando alguien cuenta cómo arregló
algo: *¿lo que tuvo que deshacer es lo que quería cambiar?* Si no, la
operación suave no existe.

### Y LAS GUARDAS DE UNA CORRECCIÓN SON LAS DE LA CREACIÓN (19/09)

La parte de diseño, y vale para cualquier pantalla que corrija un dato que
en su momento pasó por un freno.

Mover la fecha de una guía R tiene que preguntar **exactamente lo mismo** que
preguntó la carga: *"¿habría entrado ese día?"*. Escrito de nuevo en la
puerta de la corrección, eso es la regla escrita dos veces en su forma más
cara — **la copia que se separe deja entrar por una puerta lo que la otra
rechaza**, y nada se pone rojo, porque cada una es correcta por separado.

Así que los dos frenos salieron de `_crear_reproceso` a una función que los
dos caminos llaman (`_lotes_de_reproceso_a_su_fecha`), y **el test de
cableado pasó de tres lectores a CUATRO**. Lo que lo demuestra no es que hoy
coincidan: es que sacarle el filtro a esa única función haga caer a los
cuatro.

**Y la forma de que la pregunta sea literalmente la misma es ESCRIBIR
PRIMERO y validar después**, adentro de la misma transacción. Con la guía ya
puesta en la fecha nueva, su propia toma queda fuera del recorte y su propia
primera es un lote prohibido para una guía R: no puede costearse a sí misma
por ninguno de los dos lados, y no hizo falta escribir ninguna regla nueva
para eso. Si la validación rechaza, la excepción sale y no se commitea nada.

**Lo único que la corrección agrega de propio es la revisión LOTE POR LOTE**,
y es el caso que el freno del total no puede ver: la suma entra y el lote que
el documento congelado nombra puede ser de un día posterior al nuevo. El
freno mira un número; esto mira los nombres. Es el corolario 13 otra vez —un
total exacto deja de contestar la pregunta apenas la pregunta se afina.

### Y el 18/09 se construyó en la PRIMERA, por pedido del dueño

*"Esta es la primera vez y va a haber una segunda."* Una compra de Pera
quedó marcada como "vino armada en caja nuestra" contra una ficha de envase
perdido, y **Editar Compra está bloqueada para las recepcionadas**, así que
no había pantalla que pudiera sacarle la marca.

El criterio es el mismo que el de las fichas borradas —**medir antes de
construir la CURA; no antes de cerrar la PUERTA**— aplicado a una tercera
cosa: acá la puerta ya estaba cerrada (2770e7c) y lo que faltaba era el
camino para lo que ya había entrado. El `.sql` de un solo uso
(`db/cajas_12_*.sql`) y la pantalla se hicieron el mismo día, y el `.sql`
sigue siendo el que corrige ESA fila: la pantalla es para la próxima.

**DÓNDE va la puerta se decidió por la PRECONDICIÓN, no por comodidad.**
Desmarcar exige que la guía R esté anulada, y anular vive detrás de la clave
de Administración. En Buscar Compras —que es donde se MARCA y no tiene
clave— habría sido ofrecer algo cuya precondición el que lo ve no puede
cumplir: el corolario 56, el link que manda a una puerta ajena. En Corregir
Recepción, además, **la precondición ya estaba escrita**: esa función rebota
con la misma guía viva y con el mismo mensaje, así que el desmarcar la reusa
en vez de estrenar una segunda copia.

**Y la inversa NO es simétrica, a propósito.** Marcar carga la guía R en la
misma transacción; desmarcar **no anula nada** y exige que la guía ya no
esté. Anular tiene su propia pantalla, y hacerlo también acá sería la misma
operación escrita dos veces — la copia que se separe anularía guías que la
otra puerta no anula. Lo cuida un test que lee el CUERPO de la función y
exige que la palabra no esté: con la guía viva rebota antes de llegar a
ningún UPDATE, así que un test de comportamiento pasa igual con un
`anulado_el = now()` escrito adentro.

**Y el botón solo aparece donde la escritura ACEPTA**: con la guía viva se
muestra cuál anular y no hay botón. Las dos mitades preguntan por el mismo
filtro y hay un test que lo exige en las TRES funciones que lo usan —
ofrecer algo que el POST después rechaza es un callejón, y eso es peor que
no ofrecer nada.

### Y la puerta no es el arreglo del dedazo: el arreglo es que cueste ponerlo (18/09)

Desmarcar es la CURA. Lo que faltaba era que la marca no se pusiera sola, y
el pedido del dueño fue el escalón que corresponde: **un modal que explica
qué significa la marca, en los DOS lugares donde se pone** —"si está en uno
solo, el dedazo entra por el otro"—.

Enumeradas con `ast` desde `app/main.py`, las que escriben
`ficha_en_origen_id` son **siete superficies en seis rutas**: el alta, la
manual, cada renglón de la comanda, la edición, el ingreso directo de
Depósito, el retroactivo de Gerencia y el botón "Vino armada". Las seis
primeras pasan por `_caja_en_origen.html`; la séptima tiene su `<select>`
escrito a mano. **Las siete pasan ahora por el mismo modal**, y lo cuida un
test que compara el conjunto ENCONTRADO contra el DECIDIDO en vez de una
lista escrita a mano — la octava pantalla no la va a recordar nadie.

**Y la comanda MÚLTIPLE no podía marcar**, medido y no deducido: su
fragmento llega por `innerHTML`, que no ejecuta los `<script>` que trae, así
que el bloque quedaba en `display: none` de verdad y el selector no aparecía
nunca. Era un agujero aparte —una función que existe y nadie puede usar— y
**se arregló el mismo 18/09**: ver el corolario 83. Las siete superficies
pueden marcar y las siete pasan por el modal.

### Y DESDE EL 17/09 HAY UN TEST, porque la variante peor es la ruta sin botón

`/compras/cajas` se construyó entera —migración en las dos bases, pantalla,
dieciséis tests— y **el botón nunca entró al hub**. El dueño no podía cargar
el conteo inicial, que es lo único que hace arrancar toda la cuenta de cajas.

Es peor que el `.sql` a mano porque **no deja rastro**: no hay un incidente
que se repita, no hay un archivo que alguien vuelva a abrir. La ruta existe,
responde 200, tiene sus tests en verde, y nadie llega. **Todos los tests
entran por la URL**, así que la ausencia de puerta es invisible para la
suite entera por construcción.

Lo cuida `test_TODA_pantalla_de_un_sector_esta_LINKEADA_desde_algun_lado`, y
las dos decisiones de su diseño son las que lo hacen usable:

- **Mira "linkeada desde algún lado", no "desde su hub".** Una pantalla
  colgada de otra —el detalle de un colega, la edición de un artículo— es
  alcanzable, y exigirle un botón en el hub llenaría el hub de cosas que se
  abren desde adentro. Lo que no puede pasar es que no la linkee NADIE.
- **Compara el conjunto ENCONTRADO contra el DECIDIDO** (corolario 60), con
  la razón escrita al lado de cada excepción. Falla cuando aparece una
  pantalla que nadie decidió dejar suelta **y** cuando una de la lista pasa
  a estar linkeada, así la lista no protege algo que ya no pasa.

Y el barrido encontró de yapa lo que un hallazgo suelto no da: **los falsos
positivos son informativos.** Dos exportables figuraban sin link y sí lo
tienen —el href se arma con `{{ contexto.base }}`, que un regex literal no
puede resolver—, y `/compras/nueva` renderiza una pantalla que nadie linkea
y quedó en la lista **marcada como deuda y no como excepción legítima**.

### Y LA VARIANTE QUE EL BARRIDO NO PUEDE VER: la puerta que se abre para un SUBCONJUNTO (19/09)

El test de arriba pregunta si la pantalla la linkea **alguien**. El detalle por
artículo (`/administracion/stock/sistema/{id}`) **estaba linkeado** —desde los
dos bloques del Remanente, ESPERANDO guía R y NEGATIVOS— así que el barrido
salía en verde. Y no había forma de llegar para un artículo **sano**, que son
casi todos.

**El subconjunto era justo el equivocado**: se entra a ver de qué formato es lo
que queda cuando el número se lee raro, no cuando el artículo ya está marcado
como problema. La única puerta se abría para los casos que no motivan la
pregunta.

**Y se ve idéntica a una puerta**: la ruta existe, responde 200, tiene sus
tests, y desde el Remanente se llega. Lo que falta no es el link — es el link
**para la mayoría de las filas**, y eso ningún conteo de "¿la linkea alguien?"
lo puede expresar.

**La pregunta que lo encuentra**, y se hace al escribir el link: *¿para qué
FRACCIÓN de las filas existe este camino?* Si la respuesta no es "todas", la
que falta es la fracción que hay que nombrar. Es el corolario 45 corrido a los
caminos — un conteo de puertas sin su denominador no se puede leer.

**Y dónde va el camino lo decide la PUERTA, no la comodidad.** Lo natural era
colgarlo del renglón de Stock del Depósito, que es de donde viene el que
pregunta. `puerta_de_administracion` cubre **los GET** —no solo los POST, como
la de Compras— así que ese link mandaría al operario contra una clave que no es
suya (corolario 56). Se colgó de Movimiento, que ya está adentro del prefijo.

Dos cosas que se llevan del método, más allá del botón:

- **El `.sql` que se escribió para el incidente vale como camino
  permanente, y por eso NO se llama por el incidente.** `borrar_la_foto_de_
  prueba_de_balanza.sql` no lo va a encontrar el que dentro de seis meses
  necesite borrar una foto: se llama `borrar_una_foto_de_balanza.sql`, con
  el caso del 08/09 adentro como ejemplo. Es el corolario 8 —el nombre
  lleva el alcance— aplicado al día que un script deja de ser de un solo uso.
- **Que no haya botón no es siempre un error.** Deshacer una recepción
  mueve stock y puede haber sido correcta; el bloqueo de Depósito está
  puesto a propósito, y el cartel manda a Gerencia, que existe.

  Pero lo que Gerencia tiene es **Corregir Recepción, y eso es otra cosa**:
  su docstring dice, textual, que *"NO cambia el estado (sigue
  'recepcionado') ni toca procesada_el ni el retiro"*. Corrige el número de
  una recepción que pasó; no deshace una que no tenía que pasar. **Ninguna
  pantalla puede devolver una compra a 'pendiente'.**

  Por eso la pregunta útil no es "¿le falta un botón?" sino **"¿lo que hay
  del otro lado del cartel hace lo que el que llega necesita?"**. Acá el
  camino existe, está señalizado, y termina en una pantalla que resuelve un
  problema parecido pero distinto — que es más difícil de ver que un cartel
  que no lleva a ningún lado.

Corolario 32, del 09/09: **una guarda puede estar PUESTA y no hacer nada, y
el test que pregunta si está puesta no puede ver la diferencia.**

Las dos mermas esconden el tilde de "no pude sacar la foto" cuando hay foto,
para que no queden las dos cosas afirmadas a la vez. El JS pone
`hidden`; el atributo quedaba puesto de verdad. Y el tilde se seguía viendo:
`.sin-foto { display: flex }` le gana al `[hidden] { display: none }` del
navegador, que viene sin `!important`.

Cualquier test razonable lo da por bueno: el atributo está, el JS corrió, el
DOM dice lo que tiene que decir. **Lo único que ve la diferencia entre "está
escondido" y "se le pidió que se escondiera" es mirar la pantalla.**

Y en la misma captura apareció el hermano, de la familia de la copia
olvidada: `button.boton-guardar[disabled]` existía en la pantalla de segunda
y no en la de merma normal, así que ahí el botón quedaba **rojo, grande y
apagado** — el operario lo aprieta, no pasa nada, y la pantalla no le dice
por qué. El `disabled` funcionaba perfecto; lo que faltaba era que se viera.

Los dos son lo mismo dicho de dos formas: **el estado de un control es CSS,
no el atributo.** Poner el atributo es la mitad del trabajo y es la mitad que
los tests miran.

De acá en adelante, cuando una pantalla esconda, deshabilite o resalte algo
por JS: **la captura es parte del arreglo, no la verificación de después.**
Y si el estado se define en dos plantillas, es una copia y vale el corolario
2 — buscar la otra el día que se escribe la primera.

**Y la forma general, que es más ancha que el `hidden`** (dicha por el dueño
al leer esto): **el atributo es la INTENCIÓN, no el efecto.** Vale para todo
lo que se verifique leyendo HTML —`hidden`, `disabled`, `required`, una
clase, un `aria-`—: el test lee lo que la plantilla quiso, y lo que el
operario tiene adelante lo decide el CSS, que el test no corre. Un assert
sobre el atributo prueba que la orden se dio; no prueba que se haya
cumplido. Los dos casos de acá tenían la orden dada.

**Y VOLVIÓ EL 25/09 POR EL OTRO LADO: la orden de MOSTRAR se fue.** El
selector de colega de Cajas nace `hidden` y lo muestra un script al elegir un
movimiento de colega. En el rearmado del 20/09 el `<script>` se borró junto
con el bloque viejo y no volvió: la opción estaba en el selector, el POST la
aceptaba, el colega estaba cargado, y **no había forma de elegirlo**. Lo
destapó el dueño usándolo, cinco días después. Ahora lo cuida un test en
navegador que entra por `/compras` Y por `/administracion` —la `action` lleva
el prefijo, y el selector viejo por la action exacta solo andaba en una— y
pregunta `getComputedStyle` en las dos direcciones.

**La señal, para el próximo rearmado**: si una plantilla tiene un `hidden`
que algo tiene que sacar, `grep` de quién lo saca. Un `hidden` sin nadie que
lo toque es un campo que no existe.

Corolario 33, del 09/09: **estuve a punto de escribir acá, como hecho, una
afirmación negativa que era falsa** — y lo que la frenó no fue saber la
regla, fue el reflejo de verificar de más justo antes de dejarla escrita.

Las tres consultas de mermas dieron cero en Frutamax, con `ultima_merma` en
NULL: nunca se cargó una merma. Las dos de ajustes dieron cero desde el
corte y **un solo ajuste en toda la historia**, del 26/08. La conclusión
salió sola y sonaba bien: *"la baja no se registra en ninguna columna"*.

**Es falsa. Hay una cuarta, y es la que más chances tiene de no estar en
cero: `reprocesos.bultos_merma`.** No se parece a las otras tres —no es un
movimiento, es una columna de la guía R— y la carga el operario en cada
armado. Con treinta y pico de guías R cargadas, dar por inexistente el
registro de la merma era negar el que más se usa.

**Lo que hay que separar, y es la corrección de fondo: son DOS mermas
distintas, no una mal registrada.**

- **La del REPROCESO** — lo que se descarta al reenvasar. **Tiene dónde
  anotarse**: `reprocesos.bultos_merma`, un campo del formulario de la guía R.
- **La de GALPÓN** — la fruta que se pudre esperando, fuera de todo armado.
  **No tiene dónde**, y es la que la pantalla nueva viene a cubrir.

**Y acá va la corrección de la corrección, porque la primera versión de este
corolario decía "la costumbre existe y vive adentro de la guía R" — y eso
también era una afirmación sin medir.** Medido después
(`db/mermas_4_la_de_las_guias_r.sql`, Frutamax, corte 05/09, `> corte`):
**1 de 72 guías R declaró merma, por 1 bulto en total.** La puerta existe,
está abierta, y no se usa.

Así que el orden real es: la de galpón no tiene puerta, y la del reproceso
tiene una que nadie cruza. **Hay dos lugares para declarar merma y en los dos
el número es cero o casi.**

Sobre el tamaño de ese "casi", una advertencia para el que lo cite: **la
tentación es dividir 1 sobre los 1225 bultos tomados y decir 0,08%, y esa
división mezcla unidades.** Lo tomado son CAJONES y lo producido son CAJAS —
el docstring de la ruta lo dice sin vueltas (*"sin correlación entre tomado y
producido: un cajón de 16 puede dar tres cajas de 6"*) y el sistema acepta
producir más bultos de los que tomó. El dato que se sostiene es el CONTEO —
1 de 72 guías, 1 bulto— no un porcentaje de pérdida. Es el corolario 13 con
otra ropa: una división exacta entre cosas comparables deja de serlo cuando
las cosas dejan de ser comparables, y sigue devolviendo un número.

**Y la lección de método, que es la cara de esto que más se repite:** el
párrafo que corregía una afirmación negativa mal verificada metió, en la
misma frase, una POSITIVA igual de mal verificada. Deduje que la costumbre
existía de que existiera la columna. Es el corolario 18 al pie de la letra
—*al corregir se escribe rápido y con la sensación de estar arreglando, que
es cuando menos se verifica*— y esta vez pasó adentro de un corolario cuyo
tema era exactamente ese cuidado. **Escribir la regla no protege del caso;
lo único que protegió las dos veces fue medir antes de dejarlo escrito.**

Tres cosas que se llevan:

1. **Enumeré las puertas que esperaba, no el concepto.** Miré
   `movimientos_stock` (tipo 'merma' y tipo 'ajuste') y `remitos_segunda`,
   que son las tres puertas de la baja de galpón — o sea, las tres formas
   que ya tenía en la cabeza. Es **exactamente el corolario 20**, y lo
   encontró exactamente lo que el 20 dice que hay que hacer: `grep` del
   CONCEPTO (merma, descarte, tirado, perdido) en vez de la columna.
2. **Saber la regla no la dispara.** El corolario 20 estaba escrito, con su
   propio "una afirmación negativa necesita más verificación que una
   positiva", y aun así redacté la negativa. Lo que la frenó fue el momento:
   **estaba por escribirla en CLAUDE.md**, y una afirmación destinada a
   quedar escrita se relee distinto que una dicha al pasar. La lección
   operativa no es "acordate del 20": es **antes de dejar por escrito un
   "no existe", grepear el concepto una vez más.** Cuesta un minuto y es lo
   único que funcionó.
3. **Una negativa mal escrita ACÁ es la peor de todas.** Este archivo se lee
   como el estado del mundo. Un número mal en un mensaje se corrige al día
   siguiente; un "no se registra en ninguna columna" escrito acá cierra la
   búsqueda para el que lo lea en tres meses, y manda a construir el
   registro que ya existía.

**Y "NO SE USA" es la misma negativa con otra ropa, con un daño distinto: en
vez de mandar a construir, manda a BORRAR.** Del 12/09: se escribió que
`_desambiguar_cajas` quedaba sin usar porque no se la aplicó a una pantalla
nueva. Tiene **dos llamadores vivos** (el desglose de stock y el selector de
ficha de la guía R), y un `grep` de un segundo lo dice.

Lo que quedó sin usar era **aplicar el patrón en ese lugar**, que es otra
cosa — y la diferencia entre las dos frases es una función borrada. Antes de
escribir que algo no se usa, grepear el NOMBRE, que es el corolario 8 (el
grep de la función, no el del concepto) usado para no romper en vez de para
encontrar.

**Y lo que SÍ está medido, dicho con precisión**, porque acá también se
mezcla fácil: está medido que **no hay ni una merma ni un ajuste** desde el
corte, así que ningún desvío del Cotejo se explica por ellos. Que los
desvíos los cause la merma de galpón sin registrar es la **hipótesis
principal, no un hecho**: podrían ser kilajes, conteos mal tomados, u otra
cosa. Se mediría cruzando los desvíos con `corte_fifo_15`, y por ahora no
está hecho. La ausencia de causa registrada no es la presencia de esta causa.

**La consecuencia práctica**, y es la que vale para el galpón: la merma con
foto y motivo va a ser **lo primero que se cargue en esa pantalla**. No hay
hábito previo que corregir, así que lo que salga bien o mal las primeras
veces es lo que va a quedar. Conviene que alguien mire lo que cargan la
primera semana — con diez mermas encima se revisa también si la lista corta
de motivos alcanza, que hoy es una apuesta que no se puede validar contra
nada.

## Un campo que el sistema PRECARGA no es un dato que alguien declaró

Del 12/09, y es **el espejo de "un campo sin consecuencia se llena vacío"**,
que está justo abajo. Allá un campo que no mueve nada queda en blanco. Acá
un campo se llena SIEMPRE y tampoco lo decidió la persona: lo decidió la
pantalla.

**El hecho verificado, que es lo único que esta sección afirma sobre el
sistema**: el contenido estimado de una compra **no lo tipea el comprador**.
Se lo precarga `articulos.contenido_referencia` en **los cuatro caminos de
carga** — el formulario manual lo pisa por JS al elegir el artículo, y foto,
listado y múltiples lo hacen en el server con `_contenido_referencia_de`. El
comprador elige el artículo y el campo se llena solo; para que quede otro
número tiene que notarlo y pisarlo.

De ahí sale la regla, y vale aunque el caso que la trajo haya terminado en
otra cosa: **antes de leer un campo sistemáticamente mal como una carga
descuidada, buscar quién lo llena.** Si la pantalla lo precarga, el error no
está en la persona.

Y el corolario que la vuelve barata: **un valor precargado PLAUSIBLE es peor
que un campo vacío.** Vacío obliga a decidir; lleno invita a aceptar. Es el
corolario 26 con otra ropa — un cartel que se pasa con el mismo click que ya
se iba a hacer no es una revisión, y un número que se acepta con el mismo
click no es una estimación.

**Cuándo precargar, entonces**, que es la parte accionable: **sirve cuando
hay un valor DOMINANTE y estorba cuando no lo hay.** Con un dominante, el
precargado acierta casi siempre y el que lo pisa es la excepción. Sin
dominante —un artículo que viene en formatos distintos por diseño— el
precargado va a estar mal siempre, y precargar mal es exactamente lo que
invita a aceptar mal. Ahí la referencia va **vacía**, para que el campo
pregunte en vez de proponer.

### El caso, y las TRES hipótesis que se cayeron antes de la buena

Salieron **41 compras con más de un kilo de diferencia** entre lo comprado
y lo recibido. Se probaron tres explicaciones y **las tres eran falsas**,
cada una descartada con una medición y no con un argumento:

1. **"Es ruido de balanza."** Falsa por la FORMA del reparto (abajo).
2. **"El sistema imputa mal"** —mía—: que `contenido_por_cajon_real` viniera
   NULL y el total real se armara con el contenido estimado. Falsa: la
   columna que se agregó para separar causa de efecto dio `false` en los 25.
3. **"La referencia está vieja"** —también mía, y la que más lejos llegó—:
   el estimado era 16,0 en 16 de los 25 casos más grandes, en artículos que
   no se parecen en nada. Falsa: medido por artículo, **17 de 22 tienen
   desvío menor a un kilo y ocho están en CERO exacto**. El 16 de Mandarina,
   Redondo, Jugo, Ombligo y Zapallito **es correcto** — su mediana es 16. Lo
   que se estaba mirando era la COLA: a veces viene 18 o 19,5, y eso es
   variación real de la fruta.

**Lo que quedó**: dos artículos que no pueden tener referencia —Mango, que
viene en cajas de 40, de 12 y de 10 unidades, y Tomate Cherry, en cajones de
5 a 15 kg— y **dos compras con cajones faltantes**, que son las que
importaban desde el principio. (Esta línea decía que la referencia de Mango
estaba "mal" y que su mediana era 40. Las dos cosas se cayeron el mismo día:
ver **Mango y Cherry son MULTIFORMATO** más abajo.)

### CERRADO, y con el número al lado del razonamiento (12/09)

Quedaba una duda que el razonamiento no podía contestar: el promedio de
`contenido_por_cajon_real` es lo que se usa para juzgar si la referencia es
buena, y el ingreso directo escribe la referencia EN ESA COLUMNA por
construcción. O sea que la referencia podía estar confirmándose a sí misma,
y los ocho ceros exactos podían no significar nada.

Medido (`db/kilos_3b_sin_el_ingreso_directo.sql`, Frutamax, últimos 60
días):

- **El ingreso directo es marginal**: 13 recepciones sobre 421, y en 13 de
  los 22 artículos **ni una**.
- **Los ceros exactos NO se movieron**: Mzn Gob, Pera, Mzn Red, Frutilla y
  Arándano siguen en 0,00 **sin una sola compra por ese camino**. No se
  estaban confirmando a sí mismos.
- **Mango es el único donde se ve, y se ve exactamente como el mecanismo
  predice**: +28,67 con el ingreso directo adentro, **+30,00 sin él**. Esa
  recepción directa traía el número pegado a la referencia y por eso
  acercaba el desvío a cero.

Y esa última línea es la que conviene leer con cuidado, porque las dos
mitades se separan: **la medición CONFIRMÓ el mecanismo y REFUTÓ su
importancia.** Mango muestra que la contaminación es real y que empuja para
donde se dijo; los 421 muestran que sobre 13 recepciones no mueve nada. Que
un mecanismo exista no dice cuánto pesa, y el que solo comprueba que existe
se lleva la conclusión al revés.

**Conclusión**: el cajón estándar explica los 16, la referencia está bien en
casi todos, y los dos que no pueden tenerla —Mango y Cherry— **van vacíos,
los dos por la misma razón**: no tienen valor dominante. (La primera versión
de esta línea mandaba Mango a 40. Se cayó el mismo día; va abajo.)

### Mango y Cherry son MULTIFORMATO, no referencias mal cargadas (12/09)

Corrección de la conclusión de arriba, y **no sale de una medición nueva:
sale de preguntar en el galpón.** El mango se compra en cajas de **40
unidades, de 12 y de 10**, según el día y el proveedor. No hay un valor
dominante.

Entonces la referencia en 10 **no está mal**: está eligiendo uno de los tres
formatos. Y ponerla en 40 —que era la corrección pendiente— la haría estar
mal las otras dos veces, y encima más mal que hoy: 40 es el formato más
grande, así que el error de precargarlo es el más caro de los tres.

Los dos van **vacíos**, y es la regla de esta misma sección aplicada al pie
de la letra: precargar sirve cuando hay un valor dominante y estorba cuando
no lo hay. Sin dominante el precargado va a estar mal siempre, y precargar
mal es justamente lo que invita a aceptar mal. Vacío, el campo pregunta en
vez de proponer.

**Y es una CATEGORÍA distinta, no un caso más de referencia vieja**, que es
lo que hay que llevarse:

| | qué le pasa a la referencia | qué se hace |
|---|---|---|
| **Referencia vieja** | hay un valor dominante y el cargado no es ése | se corrige al dominante |
| **Artículo MULTIFORMATO** | no hay valor dominante | se deja vacía |

La medición vieja no las distingue: las dos se ven igual, como un desvío
grande entre el estimado y lo pesado. **El que lea "Mango, desvío +30" sin
esto al lado va a querer corregirlo a 40**, que es exactamente lo que se
acaba de decidir que no va.

#### Lo que la consulta SÍ mostró, y se leyó como otra cosa

`kilos_3` devuelve `minimo` y `maximo` al lado del promedio y la mediana.
Para Mango eso dio un rango de **12 a 54**, y se leyó como dispersión
alrededor de un valor mal cargado. Un rango de 12 a 54 en un artículo que
viene en tres formatos **no es dispersión: son los tres formatos** — y eso
era distinguible de la otra lectura ahí mismo, en la fila que ya estaba a la
vista. Corolario 19 otra vez: la salvaguarda estaba puesta, el dato estaba
en la fila, y se leyó lo que se esperaba encontrar.

**Y la mediana, que está en esa consulta a propósito para que un caso raro
no mueva el diagnóstico, sobre un artículo multiformato no contesta nada**:
devuelve el formato que más vino en la ventana, y se mueve sola el día que
cambia la mezcla de proveedores. Un estadístico de centro sobre una
población que en realidad son tres se lee perfecto y no significa nada. Es
el corolario 13 con otra ropa — una fórmula exacta sobre el conjunto deja de
contestar la pregunta apenas el conjunto no es uno solo.

#### HECHO el 12/09: las dos referencias están vacías

Lionel las vació desde `/articulos`. Y hay una consecuencia que conviene
saber antes de extrañarlos:

**`kilos_3` y `kilos_4` filtran las dos por `contenido_referencia is not
null`, así que Mango y Cherry ya NO APARECEN en ninguna.** No es que su
desvío pase a dar cero: la fila se va, y eso es lo correcto —sin referencia
no hay contra qué comparar, que es justamente por qué se vaciaron— pero se ve
igual que si hubieran dejado de tener problema.

(Esto decía *"el que corra `kilos_4` el 25/09 no los va a encontrar"*. **Nadie
la va a correr**: el 22/09 el dueño la retiró, porque la referencia no se
ajusta por medición. El mecanismo —vaciar un campo saca a esa fila de toda
consulta que filtre por él— no se mueve, y es lo que esta sección enseña.)

**Vaciar la referencia los saca de la vigilancia, y ése es el precio de la
decisión.** Está bien pagarlo: un promedio contra un valor que no existe no
contesta nada. Lo que NO hay que hacer es devolverles un número para que
vuelvan a aparecer en la consulta — eso sería mover el mundo para que entre
en la medición.

Lo único que lo deja ver es la columna `arts_con_referencia` de `kilos_3`,
que es la población: baja en dos y ahí se nota que se fueron. Es el
denominador del corolario 45 haciendo un trabajo que no era el suyo —
avisar que alguien salió del conjunto.

**La señal, y es la misma que la de "La señal que inventé, y que falló en el
caso que la generó", más abajo en esta sección**: antes de leer
un valor como un error de carga, preguntarse **qué GENERA los valores.**
Allá un valor REPETIDO entre artículos que no se parecen resultó ser el
cajón estándar del mercado y no un default copiado; acá un valor DISPERSO
adentro de un mismo artículo resultó ser tres formatos y no una referencia
vieja. Las dos veces la forma de los datos parecía un error del sistema, la
explicación estaba en cómo se compra la fruta, y **se contestó preguntando,
no midiendo de nuevo.**

### La precarga de Recepción: CERRADO por el dueño el 23/09, no se toca

**Es una DECISIÓN, no un pendiente.** El hecho sigue siendo cierto y se deja
escrito para que nadie lo "descubra" de nuevo: Recepción precarga los dos
campos reales con el estimado (`deposito_recepcion.html`, `value="{{
c.cantidad_cajones }}"` y `value="{{ c.contenido_por_cajon }}"`), así que
apretar "Recibir" sin tocar nada graba `real = estimado`.

> **No se va a cambiar.** Con el cartel de "¿lo pesaste?" alcanza: el que
> aprieta derecho se entera, y eso es lo que el dueño quería.

**Qué la cerró, y por qué no se reabre con un número**: esta nota llevaba
tres semanas como "anotada y no construida" esperando una razón para hacerse.
Las dos que la volvían interesante ya estaban contestadas por otro lado —la
referencia no se ajusta por medición, y la evidencia del pesaje es la foto
(ver `kilos_4`, retirada el 22/09)— y lo que quedaba era el riesgo de que
nadie mirara. Eso lo tapa el modal de las dos puertas que recepcionan. **Lo
que la precarga todavía hace** —grabar el estimado cuando alguien elige no
pesar— ya no es un accidente: es una decisión que el que recibe toma leyendo.

**Si dentro de seis meses alguien mide cuántas recepciones tienen `real =
estimado` y el número le parece grande: ya se sabe, y no mueve nada.** Un
`real = estimado` no distingue "lo pesaron y dio eso" de "lo aceptaron", y
eso no lo arregla sacar la precarga — lo que lo distingue es la foto, y para
eso está la alerta `recepciones_sin_pesaje`. Retomar esto necesita que el
dueño cambie de opinión, no una consulta.

### La señal que inventé, y que falló en el caso que la generó

Escribí, el mismo día y en este archivo: *"cuando el mismo valor aparece en
artículos que no tienen nada que ver, eso no es una coincidencia de la
realidad: es un default — la realidad no coordina a la Mandarina con el
Zapallito."*

**Es falso, y falló acá.** La realidad SÍ los coordina: **el cajón del
mercado tiene un tamaño estándar**, así que dieciséis kilos de mandarina,
de tomate y de zapallito en el mismo cajón no es un default copiado — es un
envase compartido. El valor repetido era un hecho del mundo, no un descuido.

Es **exactamente** lo de los proveedores con códigos vecinos, con otra
ropa: allá medí parecido donde la cercanía era estructural (los puestos son
una grilla); acá leí un valor compartido como copia donde lo compartido era
el envase. La regla de aquel caso ya lo decía y no la apliqué a la mía:
**antes de medir parecido, preguntarse qué GENERA los valores.** Un cajón
estándar genera valores iguales entre cosas distintas, igual que una
grilla.

Y la lección de método, que es la que más se repite en este archivo: **la
señal la escribí en el mismo turno en que la usé, y sin medirla.** El
corolario 33 dice que una negativa mal escrita acá cierra la búsqueda del
que la lea en tres meses; ésta era una POSITIVA —"esto es un default"— y
mandaba a corregir cinco referencias que estaban bien. Lo único que la
frenó fue una consulta de veinte líneas corrida al día siguiente.

### El comentario que NO había envejecido

En la primera versión de esta sección escribí que el comment de
`contenido_referencia` —*"se puede editar en cada compra si ese día vino
distinto"*— había envejecido, porque el caso real era "el número está mal
desde siempre".

**También era falso.** El caso real es el que el comentario describe: la
referencia está bien y algunos días viene distinto. El comentario tenía
razón y el que lo estaba leyendo mal era yo.

Vale dejarlo escrito porque es el modo de falla al revés del que este
archivo persigue: **no un comentario que envejeció, sino un lector que
declara envejecido un comentario que le contradice la hipótesis.** La
diferencia entre las dos cosas no se decide leyendo: se decide midiendo lo
que el comentario afirma.

### La técnica que sí funcionó: mirar la FORMA, no el conteo

Los 41 casos se repartían así: **37 arriba de 10 kilos, 25 arriba de 25 — y
solo 4 en toda la banda de 1 a 10.**

El ruido de medición tiene la forma al revés: la banda chica es la más
gorda y la cola se afina. Acá la banda chica estaba casi vacía. **Eso
descartó "ruido de balanza" y estuvo bien descartarlo.**

Pero conviene anotar hasta dónde llega, porque de ahí salté de más:
**"no es ruido de medición" NO es "son errores".** Era variación real del
producto, que también produce diferencias grandes en el total —tres kilos
por cajón sobre cuarenta cajones son ciento veinte— y no es un problema de
nadie. La forma dice que hay dos poblaciones; **no dice qué es la segunda.**

La regla, y es más ancha que el caso: **cuando hay que decidir si una
medición es ruido o es otra cosa, el conteo no alcanza — hay que mirar cómo
se REPARTE.** Cuesta tres columnas más en la consulta (`> 1`, `> 5`,
`> 10`, `> 25`) y decidió todo el diagnóstico. Engancha con **"más
hallazgos que población condena la heurística"** por el lado que a aquella
le falta: aquélla condena y nunca absuelve; la forma puede absolver — acá
41 sobre ~100 habría sonado a umbral mal calibrado y la forma dijo lo
contrario.

### Por qué salieron TRES avisos donde parecían dos

Separarlos evitó construir uno que nadie iba a mirar:

| | qué dice | cuántos | cuándo se apaga |
|---|---|---|---|
| **Faltaron CAJONES** | faltaron bultos en ESTA compra | 2 de 25 | al investigar esa compra |
| **Referencia mal cargada** | el sistema sugiere mal para ESTE artículo | 2 artículos (Mango y Cherry) | al vaciar la referencia — los dos son multiformato, no se corrigen a un número |
| ~~Diferencia de contenido por compra~~ | — | **21 por semana** | nunca |

La tercera **no se construyó**, y la razón se sostuvo aunque la causa
resultara otra: **un aviso que dispara veintiún veces por semana no se mira
dos semanas**, y menos ahora, que se sabe que la mayoría de esos veintiuno
no son un problema. El aviso que sirve es el que se apaga cuando lo
atendés, y para eso tiene que estar en la unidad de la CAUSA —el artículo—
y no en la del síntoma —la compra—.

**Cómo se decide en general**: contar cuántos disparos tendría el aviso y
cuántas causas distintas hay detrás. Si los disparos son muchos y las
causas pocas, la alerta está en la unidad equivocada.

## Un campo sin consecuencia se llena vacío, y eso no es indisciplina

Del 09/09, y va como regla y no como corolario porque **no es de la familia
de las otras**: las demás son trampas del código, de una medición o de un
comentario que envejece. Ésta es sobre la persona que carga, y sobre lo que
el sistema le está pidiendo sin darse cuenta.

**Si un dato no aparece en ninguna cuenta ni en ninguna decisión, el que lo
carga lo aprende en dos semanas y lo saltea.** No hay capacitación que lo
arregle, porque no hay nada que corregir: llenarlo o no llenarlo da el mismo
resultado, y el que trabaja lo nota antes que nosotros. **El arreglo está del
lado del sistema, no del lado del que carga.**

### El caso que la produjo

`reprocesos.bultos_merma` — el campo de merma de la guía R. Medido
(`db/mermas_4_la_de_las_guias_r.sql`, Frutamax, corte 05/09, `> corte`):
**1 de 72 guías R declaró merma, por 1 bulto.** En un negocio de fruta,
reenvasar y descartar casi nada no pasa.

La hipótesis razonable era que el formulario lo obligara: si el sistema
exigiera `tomados = primera + segunda + merma`, un operario con descarte real
y merma en cero **tendría que inflar primera o segunda para poder guardar**,
y entonces el cero no sería descuido sino lo que la pantalla le pide. Sería
un bug de diseño grande, así que se midió corriendo la ruta real con cuatro
cargas, no leyendo el `if`:

```
A) cuadra exacto            tomados 20 · primera 18 · segunda 1 · merma 1  -> guarda
B) falta 17 sin explicar    tomados 20 · primera  3 · segunda 0 · merma 0  -> GUARDA
C) produce mas de lo tomado tomados 20 · primera 60 · segunda 0 · merma 0  -> GUARDA
D) todo en cero             tomados 20 · primera  0 · segunda 0 · merma 0  -> rechaza
```

No hay identidad, ni en el CHECK de la base ni en la ruta. La única regla es
la de D: *algo* tiene que haberse producido. **Y no puede haberla**: lo
tomado son cajones y lo producido cajas, así que C no es un agujero sino el
caso normal — un cajón de 16 da tres cajas de 6.

Descartada la hipótesis, quedó la causa de verdad: **`bultos_merma` no
alimenta ninguna cuenta.** El stock sale de `− tomados + primera`, la segunda
es un pool aparte, y las mermas de la Rentabilidad Real salen de
`movimientos_stock` (`salida["tipo"] == "merma"`), no de esta columna. Se
escribe, se muestra en el detalle de la guía, y no mueve un solo número.

Y de paso: **el descarte no se pierde de las cuentas.** Está adentro de
`tomados − primera` — los cajones se fueron y volvieron menos cajas. Lo que
se pierde es el **motivo**: el número existe y nadie sabe si fue merma,
kilaje, o un reparto distinto.

### La señal, y cómo se usa antes de sufrirla

Antes de leer un campo vacío como desidia, preguntarse **qué pasa si se
llena**. Si la respuesta es "nada" —no se traba nada, no cambia ningún total,
no aparece en ninguna pantalla que alguien mire—, el vacío es la respuesta
correcta al incentivo que hay puesto.

Es la otra cara del corolario 26: allá, un cartel que se pasa con el mismo
click que ya se iba a hacer no es una revisión; **acá, un campo que no mueve
nada no es un registro.** En los dos casos el sistema parece tener algo que
en realidad no tiene.

### Por qué la merma de galpón sí debería funcionar

Es la razón para esperar distinto de la pantalla nueva, y conviene que esté
escrita antes de verlo: **la merma de galpón TIENE consecuencia — baja el
stock.** El motivo y la foto van pegados a esa consecuencia, no sueltos: el
operario carga la merma porque necesita que el stock baje, y el motivo y la
foto viajan en el mismo formulario.

Ese es exactamente el enganche que a `bultos_merma` le falta. Si en la
primera semana la de galpón se carga y la del reproceso sigue en cero, eso
**no** dice que el operario sea prolijo en una y no en la otra: dice que una
pantalla le pide algo que necesita hacer y la otra un dato que no hace nada.

### RETIRADO por el dueño el 20/09: no es un problema de plata

**No se construye ninguna de las dos.** La decisión es suya y la razón es
corta: el descarte del reproceso **no se pierde de las cuentas** —está adentro
de `tomados − primera`, los cajones se fueron y volvieron menos cajas— y lo
único que falta es el MOTIVO, que no mueve un peso.

Queda escrito como decisión y no como pendiente, porque un "anotado y no
construido" se relee dentro de seis meses como algo que todavía hay que hacer.
Lo de abajo es lo que se haría SI alguna vez el motivo hiciera falta, y hoy no
hace falta.

---

Si algún día se quiere el motivo del descarte del reproceso, **la salida no
es insistir con el campo ni pedir que lo llenen mejor: es darle
consecuencia.** Dos formas, ninguna construida:

- que la merma de la guía R **aparezca en la Rentabilidad Real** al lado de
  las otras mermas, o
- que la guía **avise cuando `tomados − primera` es grande y la merma dice
  cero** — el aviso es la consecuencia más barata, y no obliga a nada.

Y antes de construir cualquiera de las dos, medir si el motivo se necesita:
puede pasar como con el desglose del Remanente (corolario 23), que la
consulta previa borró la pantalla entera.

(No hay corolario 34: lo que llevaba ese número el 09/09 creció y quedó como
la sección **"Un campo sin consecuencia se llena vacío"**, más arriba. El
número se saltea a propósito en vez de reusarse — dos cosas con el mismo
nombre solo se cobran en la próxima lectura, cuando ya nadie se acuerda de
que hubo dos.)

Corolario 35, del 10/09, y es sobre la herramienta de verificar, no sobre el
código: **un canario que no muerde puede significar dos cosas opuestas —que
el test es flojo o que el canario está mal— y las dos se ven idénticas.**

El caso. La cuenta por ficha ganó un cuarto término y la pata nueva tenía que
entrar también en el `UNION` de `fichas_con_algo`: sin eso, una ficha cuyo
único movimiento sea una merma no existe para la consulta y la resta estaría
bien escrita y no se haría nunca. Se le puso test, y el canario dio **0**.

Los dos estaban flojos, y cada uno tapaba al otro:

- **El canario no rompía lo que decía romper.** Sacaba la palabra `UNION` y
  **dejaba el `SELECT`**. Eso no es "la pata no está": es SQL inválido, otra
  cosa.
- **El test no miraba lo que decía mirar.** Preguntaba si el texto
  `FROM mermas_ficha` estaba en el `UNION`, y con el `SELECT` intacto seguía
  estando. Habría pasado igual con la pata rota de la forma que importa.

**Y por eso el 0 no se podía leer.** Un canario en 0 se lee siempre como "el
test es débil" —así está escrito en el corolario 16— y esta vez esa lectura
era la mitad de la verdad. Arreglar solo el test habría dejado el canario
mintiendo para la próxima.

De acá en adelante, cuando un canario dé 0: **verificar las dos cosas antes
de tocar nada.** La pregunta barata que las separa es *"¿el código quedó
roto de la forma que me importa, o quedó roto de otra?"* — y se contesta
mirando qué quedó escrito, no la cantidad de tests que cayeron. Acá alcanzaba
con leer el fragmento parcheado: un `SELECT` colgado sin su `UNION` no es la
avería que se quería simular.

**Cómo quedaron los dos**, porque el arreglo es de los dos o no sirve:

- El canario borra **la pata entera** (`UNION` + `SELECT`).
- Y el test cuenta la ESTRUCTURA además de los nombres: cuatro `SELECT` y
  tres `UNION`. Así cae con las dos formas de romperlo — sacando la palabra o
  sacando la pata—, y se verificó corriendo las dos.

Es pariente del corolario 16 —*probar el test con la duplicación puesta*— pero
un escalón más atrás: **allá se duda del test y se confía en la prueba; acá la
prueba también es código que puede estar mal.** Lo que verifica no queda
verificado por ser lo que verifica.

**Volvió al día siguiente (10/09), y la forma se repite tan igual que ya es
un patrón reconocible: el canario RENOMBRA y deja la cosa intacta al lado.**
Ahí fue sobre las puertas con clave: el canario cambiaba `def firma` por
`def firma_vieja`, agregaba un cuerpo vacío, y volvía a escribir `def firma`
con el cuerpo original abajo. Resultado: un método muerto de más y **nada
roto**. Cayó 0, y el test estaba perfecto —comprueba
`puerta.firma.__func__ is Puerta.firma`, que es lo único que distingue una
copia de una referencia—. El canario bien puesto (una puerta con su PROPIA
firma, idéntica en resultado) lo hace caer.

**La señal, ahora que apareció dos veces**: si el parche del canario
AGREGA algo en vez de sacar el camino, sospechar. Un canario que rompe de
verdad casi siempre **borra** —la pata entera, la condición, la línea— y deja
el archivo con menos, no con más.

Corolario 36, del 11/09: **una consulta de diagnóstico que da CERO sobre
datos que no tienen el caso no demuestra que detecte nada.** Y el cero es
justo lo que uno se va a llevar como respuesta.

La consulta de los decimales (`db/decimales_1_de_donde_salen.sql`) corrió
contra el esquema real y devolvió todo en cero. Se veía como la buena
noticia — "no hay decimales en ningún lado"—, y no significaba eso: el
fixture no tenía un solo decimal, así que una consulta con el `% 1 <> 0`
escrito al revés, o apuntando a la columna equivocada, habría devuelto
exactamente el mismo cero.

Lo único que lo separa es **plantar el caso y ver aparecer el número**: se
metió un `bultos_primera` de 20,97, un conteo de 3,5 y un
`cantidad_cajones_real` de 18,5, y los contadores se movieron de 0 a 1 cada
uno. Recién ahí el cero de producción vale.

**Es la otra mitad del corolario 12, y la maniobra es la CONTRARIA.** Allá
se rompe la CONSULTA —correrla con la regla vieja y exigir que el número se
mueva— y sirve cuando la consulta recorta por algo. Acá se ensucian los
DATOS —plantar el caso que se está buscando— y sirve cuando la consulta
BUSCA algo. Una no reemplaza a la otra: un canario sobre el recorte no dice
nada de si el `where` sabe reconocer el caso.

**Cuándo aplica**, que es lo que la vuelve usable: toda consulta de
diagnóstico cuyo resultado esperado sea cero. Si la respuesta que se
busca es "¿cuántos hay de esto malo?", el cero es indistinguible de una
consulta rota, y la diferencia hay que fabricarla.

Y engancha con el corolario 6 —**la consulta de diagnóstico es la que decide
qué se arregla después**— por el lado que más cuesta: allá un número falso
mandó a perseguir 212 cajas que no existían; acá un cero falso manda a **no
buscar nada**, que no deja rastro y por eso nadie lo descubre.

**El desenlace, del 11/09, y cierra el caso**: corrida en Frutamax (corte
05/09, `ultima_guia_r` 10/09) dio `guias_pre 6 · guias_post 0 · compras_pre
0 · compras_post 0 · compensatorio_espejo 4 · movimientos_post 0 ·
conteos_decimal 0`. **Es un FÓSIL**: los decimales viven en 6 guías R
anteriores al corte, ya canceladas, y desde el corte no entró ni uno por
ninguna de las cuatro puertas.

O sea que **el `step` cerró una puerta que ya nadie cruzaba**, y no hay
filas escritas que revisar. Y la lectura que corrige lo que se creía: el
`+120,97` de Lima **no era un decimal que siguiera entrando** — era el
compensatorio (`-st`) reflejando los de antes del corte con el signo
cambiado. La causa y el reflejo se veían iguales en la pantalla, y por eso
la consulta los separó en dos columnas.

Dos detalles que valen para leerla de nuevo:

- **4 espejos contra 6 guías no es una discrepancia.** El compensatorio es
  uno por ARTÍCULO con neto distinto de cero, no uno por guía: varias guías
  del mismo artículo, o dos fracciones que se cancelan entre sí, dan menos
  espejos que guías. Un `4 < 6` acá es lo esperado, y confundirlo con un
  faltante habría mandado a buscar dos espejos que no tienen por qué
  existir.
- **El cero de `guias_post` significa algo porque la base está VIVA**:
  `ultima_guia_r` del 10/09, al lado, en la misma fila. Es el testigo del
  corolario 24 haciendo exactamente su trabajo — sin él, ese cero era
  indistinguible del de una base parada. Y en Palmala la cosa se parte: el
  `*_pre` vota (cuenta filas cargadas, no actividad, igual que `tildes_1`)
  y el `*_post` no vota.

Corolario 37, del 11/09: **un residuo chico en una medición que debería dar
cero tiene una causa, y encontrarla cuesta menos que convivir con ella.**

Arreglando el desborde horizontal de Compras Pendientes a 390px, el número
pasó de 166px a **4**. Cuatro píxeles es exactamente el tamaño que se
redondea a cero: entra en el error de redondeo de cualquier medición, no se
ve en la captura, y "prácticamente cero" es una frase que nadie discute.

No era ruido. Era el botón **Guardar** saliéndose de la pantalla, y la causa
es una regla de CSS que hay que saber: **un `<input>` adentro de un flex no
baja de su ancho intrínseco** —el del atributo `size` por defecto— por más
que se le ponga `flex: 1 1 auto`. Le falta `min-width: 0`. Sin eso el input
no cede, y lo que cede es lo que está al lado.

O sea que el residuo no era una imprecisión de la medición: era **el borde
de la cosa que se estaba arreglando**, asomando apenas. En esa pantalla el
botón Guardar es lo que el operario aprieta, así que 4px de un elemento de
91px es el 4% de un botón — pero del botón equivocado.

**Por qué es barato buscarlo, que es el argumento de verdad**: el elemento
culpable se encuentra con una consulta al DOM de diez líneas —recorrer los
hijos y quedarse con los que pasan el borde derecho del contenedor— y
contesta en un segundo. Convivir con el residuo cuesta la próxima vez que
alguien lo mire y tenga que decidir de nuevo si importa.

**Cómo se reconoce**: la medición tiene un valor esperado EXACTO y no lo da.
No aplica a un promedio ni a una estimación; aplica a los ceros de
construcción —un desborde, un descuadre, un saldo que tiene que cerrar, una
diferencia entre dos cuentas que tienen que dar lo mismo—. Ahí el cero no es
una aproximación: o cierra o hay algo. Es pariente del corolario 6 —una
medición floja decide mal qué se arregla después— con la vuelta de que acá
la medición estaba bien y lo flojo iba a ser la lectura.

Y engancha con el 36 por el otro lado: allá un cero podía ser falso porque
la consulta no sabía ver el caso; **acá el que miente es el casi-cero, y
miente porque invita a redondearlo.**

Corolario 38, del 11/09, y es de los tests: **el CSS, los comentarios y el
marcado viven todos en el mismo texto, así que un test que lee HTML con
regex tiene que anclarse afuera de los dos primeros.**

CUATRO veces, y las cuatro con la misma forma —**un comentario que yo mismo
acababa de escribir rompió un test que yo mismo acababa de escribir**—:

1. **La barra de Depósito.** El test verificaba el ORDEN de los botones
   buscando la palabra `"Stock"` con `index()`. Puse un comentario que decía
   "Movimientos de Stock" y el test empezó a fallar por una palabra que no
   era ningún botón.
2. **La pantalla de Evolución.** El test contaba las apariciones de
   `"Sin explicar"` para verificar que el renglón saliera solo cuando
   correspondía. Mi comentario en el `<style>` explicando por qué ese
   renglón se pinta distinto **también dice "Sin explicar"**, y entró en la
   cuenta.
3. **Los rótulos de celular** (el mismo día). Dos seguidas: `<th[^>]*>`
   **matchea `<thead>` también**, y el comentario del `@media` nombra al
   `<thead>` para explicar que se esconde. El test leyó ese texto como si
   fueran columnas y comparó rótulos contra prosa.
4. **El chip de la devolución al proveedor** (11/09), y es el caso extremo.
   El comentario del `<style>` de Rentabilidad Real existe para explicar por
   qué esa devolución **NO** va en "Afuera del cálculo"… y rompió el test
   que verifica que no vaya: `assert "Afuera del cálculo" not in
   respuesta.text`.

### Por qué pasa siempre, que es lo que le faltaba a este corolario

Las cuatro veces el comentario nombraba **exactamente** el texto que el test
buscaba, y eso no es mala suerte: es el mecanismo. **Un comentario explica
por qué algo es así, así que NOMBRA la cosa.** El test busca la cosa. La
colisión está garantizada por construcción, no por descuido.

Y el incentivo queda dado vuelta, que es lo peor: **cuanto mejor escrito el
comentario, más probable que rompa el test.** Un comentario vago —"acá se
esconde algo"— no choca con nada. El que dice qué, por qué y contra qué
alternativa, choca seguro. Los cuatro casos de arriba son de los buenos.

**El arreglo NO es escribir peor los comentarios.** Es que el test pregunte
por la **clase** o el atributo, no por el texto visible:

> **El texto es para el que lee; la clase es para el que verifica.**

Por eso el cuarto quedó como `assert 'class="tarjeta-afuera"' not in
respuesta.text`. Una clase no aparece en prosa explicativa nunca, y si
alguien la nombra en un comentario es porque está hablando del marcado —
que es justo lo que el test quiere mirar.

**Lo que esto NO es**: un descubrimiento. `split("</style>")` aparece
**63 veces** en la suite — la costumbre ya existía y era la correcta. Lo que
no existía era la REGLA escrita, así que cada test nuevo la redescubre
rompiéndose. Es el caso más limpio de algo que esta casa ya sabía hacer y
volvía a aprender: una costumbre no se hereda por estar en 63 lugares, se
hereda por estar dicha en uno.

**Cómo se escribe, y la dirección importa**:

- Para afirmar sobre el **marcado**: `respuesta.text.split("</style>")[-1]`.
- Para afirmar sobre el **CSS**: `.split("</style>")[0]`.
- Y si el fragmento igual puede aparecer en un comentario, se busca algo que
  solo pueda ser marcado: `href="..."`, un atributo entero, una etiqueta
  cerrada — no una palabra suelta. Es el corolario 4 (calificar el assert
  para que solo matchee lo que se quiso probar) aplicado al HTML en vez de
  al SQL.

**Y la señal de que está pasando es contraintuitiva**: el test falla apenas
se escribe, lo cual se lee como "me equivoqué en el test" o "el código está
mal". En los tres casos el test tenía razón en fallar **y el equivocado era
él**: miraba texto que no era el que quería mirar. Antes de aflojar el
assert, mirar QUÉ fragmento matcheó — si cae adentro de un comentario o de
una regla de CSS, el arreglo es el ancla, no la aserción.

## Corolario 39: un flag que dice "¿esto lo tocó una persona?" no se deriva de la diferencia

Del 11/09. `reprocesos.consumos_editados` contesta una sola cosa —*el
operario cambió el reparto por lote que le propuso el FIFO*— y la pantalla
lo muestra porque **un costo que no eligió el sistema tiene que poder
distinguirse**. Se calculaba así:

```python
editados = declarado != propuesta_fifo(lotes, bultos_tomados, SALIDA_REPROCESO)
```

Mientras el único camino que pasaba un reparto fuera un formulario, eso era
exacto: si difiere del FIFO, lo movió alguien. La guía R **en origen** agregó
un segundo camino —el server arma el reparto solo, dirigido a la compra que
la generó— y ese reparto **difiere del FIFO SIEMPRE y por construcción**,
porque el FIFO elegiría el lote más viejo. Así que cada guía en origen
entraba marcada como editada, y la pantalla le decía al que la lee que
alguien la tocó a mano. Nadie la tocó.

**La regla**: un flag que afirma una INTENCIÓN HUMANA no puede derivarse de
comparar el resultado contra el default calculado. La comparación mide *"¿es
distinto de lo que el sistema habría propuesto?"*, que es otra pregunta — y
son la misma solo mientras el sistema sea incapaz de producir la diferencia
por su cuenta.

**La señal, y se hace en el momento de agregar el camino**: si un flag sale
de comparar el resultado contra la propuesta del sistema, preguntarse **si
existe un caso donde la diferencia la produce el SISTEMA MISMO.** Si existe,
el flag dejó de significar lo que dice su nombre, y el arreglo no es
corregir la comparación: es que el camino que no tiene operario no conteste
esa pregunta (acá, `tipo == "normal" and ...`).

**Lo que lo agarró fue el test que compara la estructura ENTERA del INSERT**,
no una lectura del código. Un test de tres campos de doce no lo habría
tocado: `consumos_editados` no era el campo que el cambio venía a mover, y
por eso nadie lo iba a mirar. Es exactamente para lo que existe la regla de
comparar la estructura completa — que falle el día que una columna cambia de
valor sin que nadie lo pidiera es su función, no una molestia.

**Con qué engancha, y es la familia entera**: el `{% else %}` que afirma
"esto no existe", el comentario que envejece en el mismo commit que lo
volvió falso (corolario 28), el campo sin consecuencia. Todos son lo mismo
dicho de cuatro formas: **algo que AFIRMA se quedó afirmando lo que valía
antes del camino nuevo.** Y la diferencia con los otros tres es dónde se
mira: allá se relee un texto, acá se relee una CUENTA — un valor derivado
también afirma, y encima no se lee como afirmación.

## La INVERSA de una regla se reescribe en la plantilla, porque ahí es donde aparece la necesidad

Del 15/09. `core/magnitudes.repartir_magnitudes` decide en qué columna cae
cada total de una compra, y está escrita UNA vez a propósito. Su **inversa**
—sacar la segunda magnitud POR CAJÓN de una compra ya guardada— estaba
escrita **dos veces en Jinja**, en dos bloques de `deposito_recepcion.html`
separados por 134 líneas, cada uno con su propio `if unidad_compra == "kilo"`.

**Y no es descuido: es que la necesidad aparece en la plantilla.** El que
escribe la pantalla tiene el `if` en la cabeza, son dos líneas de Jinja, y
poner una función en `core/` para eso se siente desproporcionado. La regla
directa la escribió quien diseñaba el modelo; la inversa la escribió quien
diseñaba una pantalla, que es otro momento y otro archivo.

**La señal, y se hace al escribir el `{% set %}`**: si una plantilla calcula
algo a partir de dos columnas y un `if` sobre una tercera, eso es una regla,
no una presentación. La pregunta que la separa: *¿este `if` existe también en
Python, del otro lado?* Si la respuesta es sí, es la inversa de algo y va al
lado de su directa.

**Lo que la habría encontrado antes**: el `grep` no del nombre —la plantilla
no nombra `repartir_magnitudes`— sino de la FORMA del derivado, un total
dividido los cajones. Eso es lo que una copia nueva no puede evitar escribir,
y es lo que cuida `test_la_INVERSA_del_reparto_esta_escrita_UNA_sola_vez`.

**Y lo que decidió el momento de arreglarlo fue el CONTEO de copias futuras**:
con seis pantallas más por mostrar las dos magnitudes, dos copias iban a ocho.
Ese número es el argumento — no "está feo", sino cuántas van a existir si se
muestra primero y se limpia después.

### Y cómo llega a las seis pantallas sin seis lugares donde olvidarse

Un macro (`templates/_magnitudes_del_cajon.html`) que toma la compra entera,
y un GLOBAL DEL ENTORNO (`segunda_por_cajon_de`) que le pide la cuenta a
`core/magnitudes.py`. El global es el precedente que ya estaba escrito para el
catálogo de cajas: pasar el dato en el contexto de cada render son seis
lugares de los que uno se puede olvidar, **y el que se olvide no ve nada roto
— ve una sola magnitud, que es lo que había antes.**

Dos decisiones adentro, las dos medidas con un canario:

- **`real` mueve LAS DOS mitades a la vez.** La fila de "lo recepcionado"
  muestra `contenido_por_cajon_real`, y al lado tiene que ir la segunda
  magnitud REAL. Con una sola versión, esa fila mezclaba lo recibido de un
  lado con lo declarado del otro, en la misma línea y sin que nada avise.
- **El estilo va INLINE en el macro.** Las seis plantillas tienen su propio
  `<style>`: puesto en las seis serían seis copias de la misma regla, que es
  justo lo que este arreglo vino a terminar.

### El hueco se MUESTRA, y la razón es del dueño

*"Una pantalla que se calla no distingue 'no hay dato' de 'no se me ocurrió
mostrarlo'."* Y acá el hueco es información: **dice que esa compra vieja no va
a poder costear en la otra unidad**, que es la pregunta que alguien se va a
hacer mirando las fichas que no costean. Se apaga solo cuando entren compras
con las dos.

Con la condición de que el hueco sea VERDADERO: un artículo que se compra solo
por kilo no tiene segunda magnitud, así que ahí no falta nada y el aviso sería
un reclamo falso. Lo distingue `unidad_conteo` — y por eso esa columna hace
falta en las seis consultas **aunque no entre en ninguna cuenta**: no decide el
número, decide si hay algo que declarar.

**Medido con un canario**: sacarle `a.unidad_conteo` a la consulta del detalle
hacía caer CERO, y el modo de falla es mudo — sin ella el macro no puede
nombrar la magnitud que falta, el hueco no se dibuja, y la pantalla vuelve a
mostrar una sola magnitud, que es exactamente lo que se veía antes. Es el
corolario 65 por tercera vez, y la tercera no fue más fácil de ver que la
primera.

## Corolario 71: una regla escrita en la CONSULTA y en una función pura SIN LLAMADORES es una regla y un adorno

Del 16/09, y es la regla escrita dos veces con una asimetría que no
habíamos visto: **las dos copias no tienen el mismo peso.** Una decide y la
otra solo se lee como si decidiera.

El stock de cajas resta las que se llenan en la guía R, y eso está escrito
en dos lugares:

- `_SQL_STOCK_DE_ENVASES`, pata `guias` — **la que corre en producción.**
- `core/envases.cajas_que_mueve_la_guia` — la que explica la regla, con el
  mapa de signos y un docstring de diez líneas.

**La segunda tiene CERO llamadores fuera de sus propios tests.** `grep` del
nombre: seis apariciones, todas en `tests/test_cajas.py` y en su definición.
Así que la función que se lee como la fuente de la verdad no toca un solo
número del sistema, y sus tests —verdes, prolijos, con sus casos bien
elegidos— **no prueban nada sobre lo que el operario ve.**

**DEJÓ DE SER CIERTO EL 25/09, y para bien.** La lista de movimientos de
cajas (`movimientos_de_cajas`, app/db.py) es su primer llamador real: el signo
de cada guía R que se muestra sale de ella, y no de una tercera copia. Y lo que
ata las dos escrituras ya no es solo un par de asserts de texto:
`test_la_lista_SUMADA_desde_el_conteo_da_el_MISMO_stock_que_la_tarjeta` suma la
lista, que pasa por la función, y la compara contra `stock_de_envases`, que pasa
por el SQL. Si la función y la pata se separan, esos dos números se separan.
El mecanismo del corolario no cambia: lo que se movió es el ESTADO que se
anotó al lado para ilustrarlo.

### EL BUG QUE ESTE COROLARIO CONTABA NO EXISTÍA (16/09, unas horas después)

**Se deja entero y corregido acá, porque el error de método es más caro que
el hallazgo que decía tener.**

La versión original decía: *"el bug lo destapó el dueño, no el código: la
segunda sale en caja nuestra igual que la primera —al reprocesar un cajón, lo
de segunda se pone en caja de Día porque no hay otra cosa a mano en la mesa—
y las dos copias restaban solo `bultos_primera`"*. Sobre eso se cambiaron las
dos copias a `bultos_primera + bultos_segunda`.

**El dato del galpón era al revés, y lo corrigió el dueño el mismo día**: al
reprocesar un cajón la primera va en caja de Día y **la segunda queda en el
envase del proveedor**. No lleva caja nuestra. Así que el arreglo restaba
80,97 bultos por trimestre de un stock del que nunca salieron: **el stock
BAJO y el aviso de reposición temprano**, que es el mismo modo de falla que
venía a arreglar, con el signo cambiado.

Revertido el 16/09, con la premisa retractada escrita al lado de las dos
copias para que nadie la vuelva a agregar leyendo el número sin el dato.

**La lección NO es "preguntá el dato", que ya está escrita en veinte lugares
de este archivo. Es sobre CUÁNDO se pregunta:** el dato se preguntó, se
contestó, y la respuesta estaba mal — **porque la pregunta se hizo en medio
de un arreglo, con la hipótesis ya armada y el diff a medio escribir.** Una
pregunta así se contesta rápido y para adelante, que es exactamente cuando
menos se verifica (corolario 18, pero del lado del que CONTESTA y no del que
escribe).

**Cómo se reconoce, y es lo único accionable**: cuando un hecho del galpón
llega como confirmación de algo que uno ya empezó a construir, eso no es una
medición — es un tilde. El que contesta está mirando el arreglo, no el
galpón. La forma que lo evita es la que ya funcionó dos veces con el mango
multiformato: **preguntar qué pasa, no si pasa lo que uno cree.** *"¿En qué
va la segunda cuando se reprocesa?"* tiene una sola respuesta posible; *"la
segunda sale en caja nuestra, ¿no?"* tiene dos y una es un asentimiento.

**Y la parte que sí se confirmó**: existe una segunda que va en caja nuestra,
y es **la del RECHAZO** — el súper devuelve mercadería que salió en nuestra
caja y eso se anota como segunda. Ésa no pasa por `reprocesos`: vive en
`movimientos_stock`, y **ya está descontada desde la guía R que la armó**, así
que sumarla otra vez la contaría dos veces. Las dos segundas se llaman igual
y salen de tablas distintas, que es la familia entera de este archivo.

### Por qué la copia ornamental es PEOR que dos copias iguales

Con dos copias que corren, la que se separa rompe algo en algún lado: dos
pantallas dicen números distintos, un test cae, alguien pregunta. **Con una
copia ornamental no hay nada que se separe** — se puede arreglar la de
adorno, ver los tests en verde, y no mover un número. Y al revés: arreglar
solo el SQL deja el módulo que documenta la regla afirmando lo contrario,
que es el comentario que envejece con la autoridad de ser código.

**La señal, y es un `grep` de un segundo**: cuando una regla vive en una
función pura, grepear su NOMBRE y ver quién la llama. Si los únicos
llamadores son sus tests, esa función **no es la regla: es un documento
ejecutable**, y la regla está en otro lado. Lo cual está bien —un documento
ejecutable es mejor que un comentario— con la condición de que algo ATE las
dos: acá, un test que exige el término exacto en el texto del SQL y otro que
lo exige en la función, y un canario sobre cada uno.

Es el corolario 8 corrido de lugar: allá dos cuentas con el mismo nombre y
distinto ALCANCE; **acá dos escrituras de la misma regla con distinto
PODER.** Y como el poder no se ve leyendo —las dos son código, las dos
tienen tests— hay que ir a contar llamadores.

### La MERMA no entra, y eso se afirma en vez de dejarse implícito

Lo que se descarta se tira; no se pone en una caja para tirarlo. Es una
decisión y no un olvido, así que está escrita de las dos formas: el SQL
afirma `"bultos_merma" not in sql` y la función pura **ni siquiera recibe el
parámetro**, con un test que lo comprueba sobre la firma. El día que resulte
que sí ocupa caja, hay que cambiar la firma — y ahí el test dice por qué no
estaba.

### Y el assert de las anuladas era el corolario 4, otra vez

Buscando el término de la segunda apareció, de yapa, un canario en cero:
sacarle `r.anulado_el IS NULL` a la pata de las guías **no hacía caer ningún
test**. El assert decía

```python
assert "anulado_el IS NULL" in _SQL_STOCK_DE_ENVASES
```

y esa consulta tiene **CUATRO tablas que llaman igual a esa columna**. Una
coincidencia alcanzaba, así que el assert matcheaba el filtro de otra pata y
el de las guías podía irse entero. Una guía R anulada habría seguido
consumiendo cajas para siempre — que es exactamente lo contrario de lo que el
título de ese test promete (*"que anular una guía R corrija el stock solo
sale de esto"*).

Es el mismo caso del `anulado_el IS NULL` que matcheaba `pedidos` creyendo
mirar `pedidos_renglones`, cinco días después de escribirlo acá. Y la
diferencia con aquél es que **este assert estaba en el test cuyo TÍTULO
afirma la propiedad**: no es que faltara la verificación, es que la que había
no podía fallar.

Cerrado calificando por ALIAS y recorriendo las patas por nombre, con un
`count(...)` al lado — el denominador del corolario 45 aplicado a un assert
de texto: sin él, tres filtros y cuatro pasan igual. (Eran cuatro patas
cuando se escribió esto y son TRES desde el 17/09: se fue `liberadas`. El
assert cuenta lo que hay, así que el número del test se movió con ella.)

## Corolario 74: una respuesta CONGELADA y una DERIVADA a la misma pregunta se separan sin que ninguna esté rota

Del 16/09, y es del dueño: *"las dos cumplen lo que prometen, y nadie las
pone al lado"*. Salió del corolario 73 pero no es de ese bug — es la forma, y
este sistema está lleno de pares así.

Cuando 56 bultos salieron de un lote de 40, el sistema quedó diciendo dos
cosas incompatibles:

```
lo CONGELADO (reprocesos_consumos)  56 salieron del lote, al costo del lote
lo DERIVADO  (el rejuego del FIFO)  el lote en 0 y 16 SIN LOTE
```

**Y las dos son correctas.** `reprocesos_consumos` promete ser *"un documento
congelado: si después se corrige una recepción, el stock vivo se reacomoda
pero esta trazabilidad y su costo no se mueven"* — lo dice su propio comment,
y hace exactamente eso. El rejuego promete recalcular en cada lectura, y hace
exactamente eso. No hay una línea mal escrita en ninguno de los dos.

### Por qué no hay forma de que se avisen

Las dos propiedades que los hacen útiles son las que impiden la alarma:

- **El congelado no puede cambiar** — si cambiara, no serviría para lo que
  existe (el costo al que se facturó no se puede mover porque el stock se
  reacomodó). Así que no puede "enterarse" de nada.
- **El derivado no guarda nada** — no tiene dónde dejar una marca que diga
  "esto no coincide con lo que se escribió aquel día".

O sea que la contradicción **no tiene lugar donde vivir**. No es que falte un
CHECK: un CHECK compara dos cosas en una misma escritura, y acá las dos
respuestas se producen en momentos distintos y con reglas distintas a
propósito.

### Y la pantalla las separa, que es lo que lo vuelve invisible

El que abre el detalle de la guía ve un costo completo y prolijo. El que mira
el stock ve un hueco. **Son dos pantallas distintas y nadie tiene motivo para
abrirlas juntas** — es el corolario 10 (dos vistas del mismo hecho que dan
consejos incompatibles se esconden mientras estén separadas) con la vuelta de
que allá bastó cambiar un orden para que cayeran juntas, y acá viven en
módulos distintos.

### La señal, y se hace al DISEÑAR, no al depurar

**Cuando un dato se congela "para trazabilidad" y el mismo hecho además se
deriva en cada lectura, eso es un PAR, y el par necesita quien lo compare.**
La pregunta que lo detecta: *si estos dos se separaran, ¿qué se rompería?* Si
la respuesta es "nada, cada uno sigue andando", no hay alarma posible y hay
que fabricarla.

No es un argumento para dejar de congelar: congelar el costo es correcto y la
razón está escrita. Es que **el par se elige, y al elegirlo se acepta una
deuda**: alguien tiene que poder preguntar si siguen coincidiendo.

Los pares que ya existen en este sistema, para que la próxima no se busque de
cero:

| congelado | derivado | ¿los compara alguien? |
|---|---|---|
| `reprocesos_consumos` | el rejuego del FIFO | **no** — es este corolario |
| `conteos_stock.stock_sistema` | el stock de ahora | sí, y se decidió sacarlo (corolario 25) |
| `movimientos_stock.stock_sistema` | el stock de ahora | no, y es a propósito: es la foto de auditoría |
| `movimientos_stock.costo_por_bulto` | el costo del listado | no |

**La comparación más barata no es una pantalla: es una consulta que devuelva
los dos números en la misma fila** — que es lo que hace `mismo_dia_1` contra
lo congelado, y lo que le falta del lado derivado. Una fila con los dos al
lado es lo único que convierte "nadie los pone juntos" en "no coinciden".

**Y el precio de no tener la comparación no es el descuadre: es que el
descuadre se ve como dos pantallas sanas.** Es la familia entera de este
archivo —el cero que no puede crecer, la columna que nadie escribe, el campo
sin consecuencia— dicha una vez más: lo que hace daño no es el dato malo, es
que se vea igual que el bueno.

## Corolario 76: un argumento CIERTO sobre la plata no decide sobre una lista que ENUMERA

Del 17/09, y es del dueño en una frase: **"falta el nombre, no la plata, pero
el nombre es lo que la vuelve negociable."**

`reproceso` perdía la caja y quedó dos días afuera de `cajas_perdidas` —el
renglón que las NOMBRA— con este argumento mío: esa caja ya está cobrada
adentro de `rechazos_perdidos`, así que agregarla no mueve un peso.

**Todo eso es cierto y sigue siéndolo.** Lo verifiqué, está medido, y el
renglón efectivamente no entra en ninguna suma. El argumento no tenía una
premisa falsa —que sería el corolario 25— ni un número mal. **Lo que estaba
mal es contra qué se evaluaba la cosa.**

> **Una lista que ENUMERA no se evalúa por lo que cobra: se evalúa por si se
> puede llevar a discutir.** Y a la que le falta un tercio de las puertas no
> se puede — el de enfrente pregunta por las que faltan y la conversación se
> termina ahí.

Es la familia del corolario 25 corrida un lugar y por eso cuesta más verla:
allá el razonamiento era válido y la PREMISA no se había medido; acá la
premisa estaba medida, el razonamiento era válido, **y la dimensión era otra**.
No hay nada que medir para encontrarlo: hay que preguntarse para qué existe
la cosa.

**La señal, y es una sola pregunta**: cuando un argumento para dejar algo
afuera empieza con *"total, no cambia ningún número"*, preguntarse **si el
número es para lo que esa cosa existe**. Un total, un costo, una alerta que
frena: ahí la plata decide. Un renglón que nombra, un detalle, una lista de
reclamo, un chip al lado de un artículo: ahí decide si está COMPLETA, y "no
mueve nada" es exactamente lo que se espera de él.

### Y lo que sí había que probar era lo contrario

Nombrarla en dos lugares se lee como doble conteo. Que no lo sea **no se ve
mirando los dos números**, y la primera versión del test lo "probaba" así:

```python
mercaderia = rechazos_perdidos - cajas_perdidas_pesos
assert rechazos_perdidos == mercaderia + cajas_perdidas_pesos   # x == (x−y)+y
```

Cierto por álgebra. **Corolario 41 adentro del test escrito para cerrar el
caso**: pasa con el envase cobrado una vez, dos o ninguna — medido con el
canario del cobro doble, que la versión vieja pasa y la nueva hace caer.

Lo que sirve es una corrida de CONTROL que produzca el otro número por su
cuenta: la misma devolución con `envase_unidad = 0` da la mercadería sola, y
lo que CRECE al ponerle envase tiene que ser exactamente lo que el renglón
nombra. Dos números de dos lugares, no una resta y su inversa.

**La señal, para reconocerlo sin correr el canario**: si el valor contra el
que se compara se DERIVA de los mismos números que se están comparando, la
igualdad no puede fallar. El control tiene que venir de otra corrida, otra
consulta u otra fuente — es la misma regla que *"la verificación que funciona
es la que hace chocar dos fuentes"* (corolario 19), acá adentro de un test.

**Y el renglón que este corolario defendió YA NO SE VE EN CAJAS** (17/09): la
pantalla pasó a ser solo stock y `cajas_perdidas` se fue con el resto de la
plata. **El corolario no se mueve**: sigue diciendo que una lista que ENUMERA
se evalúa por si está completa. Lo que envejeció es DÓNDE se ve, que es el
estado que se anota al lado del mecanismo para ilustrarlo.

**Y el "va a volver a dibujarse el día que alguien la cablee en Gerencia" ya
pasó**: vive en `/gerencia/cajas-perdidas` ("Plata de cajas"), con el renglón
del depósito adentro. Desde el 21/09 ese renglón cuenta **la merma Y el pase**
de cajas armadas, no solo el pase, y el chip dice `N del depósito` para
separar contra QUIÉN se reclama: una caja perdida en un rechazo es una
conversación con el CLIENTE, y una tirada o pasada a segunda es con el
DEPÓSITO, porque la fruta se puso fea acá adentro.

## Corolario 79: un parámetro sin escritor es una FUNCIÓN QUE FALTA — o una que SOBRA

**LEER PRIMERO, del 18/09: el caso de abajo se resolvió AL REVÉS y eso cambia
el corolario, no solo su ejemplo.** `envase_declarado` no esperaba una
pantalla: **no tenía que existir**. La regla que lo pedía trataba la ficha
variable como un caso a preguntar, y la caja sale siempre de la ficha.

O sea que un parámetro sin escritor tiene **DOS** explicaciones —falta
cablearlo, o sobra— y **las dos se ven idénticas**: el parámetro está, el `if`
que lo usa está escrito y probado, y la pantalla se ve entera. La pregunta de
abajo (*¿quién lo PASA?*) encuentra el síntoma y **no distingue los dos
casos**. La que los separa no es de código: es **¿el hecho del mundo que este
parámetro afirma, ocurre?** — y eso se pregunta, no se grepea.

Es literalmente el corolario 72 con su corrección del 17/09 (la columna
`liberadas`, que sumaba cajas que se van a la basura), repetido un día después
sobre un parámetro. **Dos veces la misma semana construí la mitad que
cableaba en vez de preguntar si el caso existía**, y las dos veces la premisa
costaba una pregunta de una línea. La que funciona es la abierta —*"¿qué pasa
con la caja cuando…?"*— y no la cerrada, que tiene dos respuestas y una es un
asentimiento (corolario 71).

Lo que sigue en pie sin cambios es el MECANISMO: un parámetro que solo pasan
sus tests no es un parámetro con default. Lo que cambia es qué se hace después
de encontrarlo.


Del 17/09, y es el corolario 72 sobre un parámetro en vez de sobre una
columna — con un agravante que lo vuelve peor: **una columna sin escritor
devuelve un cero prolijo; un parámetro sin escritor deja el `if` que lo usa
escrito, probado y visible.**

`_envase_de_esta_guia(cursor, ficha_id, envase_declarado)` tenía el
parámetro desde el primer día, con su docstring diciendo *"es lo que contestó
la persona cuando hubo que preguntar"*, y la línea que lo usa:

```python
if hay_que_preguntar and envase_declarado is not None:
    return envase_declarado
```

**Nadie lo pasó nunca.** `grep` del nombre en `app/`, `core/` y `templates/`:
cero fuera de su propia definición. Y `envase_derivado_de_la_ficha` define
tres casos, el tercero de los cuales dice **"si no se puede derivar, se
PREGUNTA"** — la pregunta se diseñó, se le dejó el cable, y nunca se
construyó la pantalla.

**La consecuencia, y por eso valía atacarlo antes que nada**: con ficha
variable —Mango y Cherry, los dos artículos que más se mueven— la caja sale,
es nuestra, y **no se descuenta nunca**. El stock de cajas queda alto
justamente donde más rota.

### Por qué se lee como si estuviera cableado

Un lector que abre `_envase_de_esta_guia` ve el parámetro, ve el `if`, ve el
docstring que explica cuándo llega, y **concluye que llega**. Es lo contrario
del campo sin consecuencia (que se ve vacío) y del `{% else %}` que afirma de
más (que se ve raro al leerlo): **acá el código está bien escrito y completo,
y lo que falta está AFUERA de él.**

Ninguna guarda de las que ya teníamos lo ve:

- el **CHECK de coherencia** relaciona `lleva_caja_nuestra` con `envase_id`, y
  las dos en NULL lo cumplen;
- el **test de la estructura entera del INSERT** compara dos listas que
  escriben NULL en esas columnas, y coinciden;
- los **tests de la función** le pasan `envase_declarado` a mano —porque el
  test sí puede— así que el camino se ejercita y pasa;
- y la **pantalla** se ve perfecta: no hay campo que falte, porque el campo
  nunca existió.

### La pregunta que lo encuentra

> **Para cada parámetro OPCIONAL que cambia el resultado, grepear quién lo
> PASA.** Si los únicos que lo pasan son sus tests, no es un parámetro con
> default: es una función que falta, y el default es el bug.

Es el corolario 71 —una regla en una función pura sin llamadores es un
adorno— corrido al argumento: allá había que contar llamadores de la función,
acá de un parámetro. Y las dos veces lo que engaña es que **el código
existe, es correcto, y tiene tests verdes**.

### Lo que quedó de las dos subsecciones que había acá

Describían cómo se había cableado la negativa: que la política vive en el
llamador y no en el núcleo (corolario 75), y que una guarda que solo lee una
fila va ARRIBA, junto al piso de la fecha, y no abajo con el costo — lo
segundo lo destapó un canario: con el stock también corto, el operario veía
la pared del stock primero, iba a cargar una recepción, volvía, y recién ahí
se enteraba de que faltaba contestar un select.

**Las dos son ciertas y ninguna tiene hoy un caso en este sistema**, porque
la negativa se fue entera. Se dejan dichas en un párrafo en vez de borradas:
**el orden de las guardas no es estilo, es cuántas veces vuelve el que
carga**, y eso va a volver a hacer falta.

## Corolario 80: una cuenta DERIVADA convierte "completar el dato" en "arreglarlo", y eso decide si hay que recargar

Del 17/09, y es la propiedad que más veces salvó a este sistema, vista del
lado bueno por tercera vez.

Las dos guías R de Frutamax que no declaraban su caja **no hubo que anularlas
ni recargarlas**: el stock de cajas no vive en una columna, se rejuega en cada
lectura, así que escribir `lleva_caja_nuestra` y `envase_id` alcanza para que
la guía empiece a descontar. Medido contra el esquema real, no leído:

```
las dos en NULL                        contadas 500 · por_guias   0 · stock 500
declaradas en caja nuestra (10 y 6)    contadas 500 · por_guias -16 · stock 484
declaradas DESCARTABLE                 contadas 500 · por_guias   0 · stock 500
```

Es la misma propiedad que hace que **anular una guía R corrija el stock sola**
—está escrita en el docstring de `stock_de_envases` desde que se construyó— y
la que hace que el reparto del FIFO se acomode cuando aparece la guía R que
faltaba. Escrito como una columna que alguien actualiza, completar el dato
habría sido un segundo lugar del que acordarse, y el día que se olvide el
stock queda mintiendo.

**La pregunta que hay que hacerse antes de decidir si un arreglo necesita
recargar**: ¿el número sale de una columna o se deriva? Si se deriva,
completar el dato de origen ES el arreglo, y no hay nada más que hacer. Si
vive en una columna, hay dos lugares y hay que tocar los dos.

### Y la puerta de las que YA ESTÁN no es la misma que la pregunta nueva

*(El 18/09 la pregunta Y la puerta se borraron las dos: no había nada que
preguntar. Lo que sigue valiendo entero es el párrafo de arriba —completar el
dato de origen ES el arreglo cuando el número se deriva— y es justo lo que
hace que a las dos guías de Frutamax les alcance un backfill de dos filas en
vez de una anulación. Lo de abajo describe una puerta que ya no existe, y se
deja por el argumento del CALLEJÓN, que vale para cualquier botón: ofrecer
algo que la escritura después rechaza es peor que no ofrecer nada.)*

Son dos construcciones y hacen falta las dos: la pregunta en Reproceso cierra
el agujero **desde hoy**, y sin una puerta para las que ya están, lo viejo
solo se arregla anulando y recargando —o tocando la base a mano, que es el
corolario 31—. Cerrar la puerta y no curar lo que ya pasó deja un número
inexplicable para siempre.

**Y LA PUERTA SE OFRECE SOLO DONDE LA ESCRITURA ACEPTA.** Las dos preguntan
con la MISMA función (`envase_derivado_de_la_ficha`), así que no puede haber
un botón que el POST después rechace. Un callejón —ofrecer algo que al
apretar da error— es peor que no ofrecer nada: el que lo aprieta se come un
error por algo que la pantalla le propuso.

Concretamente, la guía **vieja** (anterior a la migración, con ficha de envase
FIJO y la columna en NULL) **no se ofrece**: su caja sale de la ficha, y
dejarla declarar a mano sería re-etiquetar la historia — lo mismo que este
proyecto se negó a hacer con `unidad_compra`. Ésa se arregla reasignándole la
ficha, que re-deriva.

### El control que el canario pidió, y por qué el que había no servía

El canario que saca la condición de "no lo puede derivar" **dio CERO**, y el
test de control existía: una guía cuya ficha define la caja, que no tiene que
ofrecer el formulario. **Pero esa guía tenía `lleva_caja_nuestra` en True**,
así que la excluía la PRIMERA condición y la segunda nunca se ejercitaba.

> **Un control que se cae por el motivo equivocado no es un control.**

El fixture que sí lo ve es el que pasa la primera condición y falla la
segunda: caja en NULL **y** ficha fija. Es el corolario 30 con dos guardas en
serie — para probar la segunda hay que pasar la primera, y un fixture que
rebota antes las aprueba a las dos sin mirar ninguna.

## Corolario 81: DERIVAR un caso de una regla no es lo mismo que preguntar si el caso existe

Del 18/09, y es del dueño. Es una forma distinta de todas las de este
archivo, y por eso lleva número propio en vez de quedar como una frase
adentro del caso que la produjo:

- **no hubo una premisa falsa** (corolario 25): la regla era verdadera.
- **no hubo un número mal medido** (corolarios 6, 11, 45, 69): no se midió
  nada, porque no había nada que medir.
- **no hubo un requisito leído de más en el pedido** (corolario 29): el
  pedido no decía nada de esto ni cerca.

Lo que hubo es **un caso derivado de la forma de la regla, sin preguntar si
ese caso ocurre.** `envase_derivado_de_la_ficha` tenía dos casos que alguien
había pedido —ficha con envase, ficha sin envase— y yo agregué un tercero
porque la regla, escrita así, parecía tener un hueco: *si no se puede
derivar, se pregunta*. De ahí salieron una pregunta en Reproceso, una puerta
en Guías R, una negativa que no dejaba guardar, y un parámetro que nunca
tuvo escritor. **La caja sale de la ficha y ese hueco no existía.**

### Por qué convence más que un requisito inventado

El corolario 29 nace de leer de más lo que alguien pidió, y eso se siente
como una interpretación — algo que uno sabe que está haciendo. **Éste nace
de completar una simetría**, y eso se siente como rigor: la regla tiene tres
casos, dos están contemplados, falta el tercero. Nadie revisa un razonamiento
que se ve prolijo.

**La simetría es una buena razón para SOSPECHAR que un caso existe. Nunca es
una razón para construirlo.**

### Y la señal la escribí yo, en el mismo commit que introdujo el caso

El docstring decía, textual: *"Los tres casos, y el tercero **no estaba en el
pedido** pero sale de la misma regla"*.

Estaba anotado, al lado, en mayúsculas prácticamente, y no me detuvo. Y la
razón de que no detenga es la que hay que entender:

> **Escribir "esto no me lo pidieron" no es lo mismo que preguntarlo.**

La anotación se siente como la honestidad ya ejercida — se parece tanto al
acto de señalarlo que lo reemplaza. Pero es una nota sobre el ORIGEN del
caso, escrita en el código, para uno mismo; y lo que hace falta es una
pregunta sobre el MUNDO, hecha a la persona que lo conoce. Son dos actos
distintos y el primero no paga el segundo.

**Lo accionable, y cuesta una línea de chat**: una frase de esa forma
—"no estaba en el pedido", "sale de la misma regla", "por simetría", "el caso
que falta"— **es la orden de preguntar antes de escribir la primera línea**,
no una licencia para escribirla dejando constancia. Y la pregunta es la
abierta (corolario 71): *"¿qué pasa cuando…?"*, nunca *"esto pasa, ¿no?"*.

### Y lo único que salió bien: BORRARLA fue un solo cambio

La pregunta se mostraba en tres lugares —el selector de Reproceso, el
`falta_la_caja` de Guías R y la guarda del server— y los tres se apagaron
cambiando **la rama de una función**. Ninguno tenía su propio
`if envase_variable`.

Eso es más que una comodidad: **es la única prueba dura de que una regla
estaba escrita una sola vez.** Un test puede afirmar que dos lugares
coinciden hoy; lo que demuestra que no son dos copias es que borrar la regla
los apague a los dos. La cantidad de lugares que hay que tocar para sacar
algo **es la medida de cuántas veces estaba escrito**, y se cobra justo el
día que resulta que no iba.

Por eso vale al revés también, y es la parte usable: **cuando algo se
construye sobre una premisa que todavía no se preguntó, escribirlo en UN
lugar no es prolijidad — es lo que hace que deshacerlo salga gratis** el día
que la premisa se cae. Es el corolario 29 en su parte buena (*un cambio que
todavía no tiene usuarios se escribe de forma que deshacerlo sea gratis*),
con el mecanismo dicho: la forma de que sea gratis es que la regla tenga un
solo lugar.

## Corolario 84: una premisa del DUEÑO también se verifica, y la que se cae agranda el pedido

Del 18/09. El pedido venía con una premisa adentro: *"no es que pidan más
cantidad de algo que ya está, **eso lo puedo editar**"*. Era falsa, y lo dijo
un `grep` de los seis `UPDATE pedidos_renglones` que existen: ninguno toca
`cantidad`.

**Lo que se habría construido creyéndole es media función.** El caso "me
pidieron 5 más de algo que ya estaba" —que es el más común de los dos— habría
seguido necesitando recargar el pedido entero, y el dueño se habría enterado
usándolo.

Y no es la familia del corolario 71, donde el dato del galpón llega mal porque
se pregunta en medio de un arreglo. **Acá la premisa es sobre EL SISTEMA, no
sobre el mundo** — y de esas el repo es la fuente, no la memoria de nadie. La
regla, entonces, es la que separa las dos:

> **Lo que el dueño sabe del GALPÓN se le pregunta. Lo que afirma del SISTEMA
> se verifica en el código, aunque venga en la misma oración.**

Las dos mitades importan. Discutirle un hecho del negocio es perder el tiempo
—él lo ve todos los días y nosotros no—; creerle una afirmación sobre lo que
el código puede hacer es construir sobre una lectura que él no tiene por qué
tener. La frase de este caso tenía las dos: el hecho del negocio (el súper
agrega por teléfono) era cierto, y el del sistema (lo puedo editar) era falso.

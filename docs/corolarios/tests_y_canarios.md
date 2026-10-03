# Corolarios: tests, mocks y canarios

Movido TAL CUAL desde CLAUDE.md el 03/10 (sin reescribir). Las reglas
vigentes, en corto, están en CLAUDE.md.

## Un fixture construido a partir de la hipótesis no prueba la hipótesis: la repite

Pasó el 04/09. Del cliente llegaron dos números reales de pantalla —"74 cajas
armadas y total 26"—. En vez de preguntarle a los datos **de dónde salía ese
74**, se inventó una estructura que lo explicara (dos fichas, una en +74 y otra
en −48, que antes se cancelaban), se armó un fixture que la codificaba, y se
escribió *"el fixture reproduce tus números exactos"* como si eso confirmara
algo.

**No confirmaba nada.** Probaba que la aritmética propia era consistente consigo
misma. La consulta que le preguntaba a los datos estaba escrita y a mano; se
fabricó el caso en vez de correrla. Los datos después dijeron que había **una
sola ficha** y que el 74 salía de otra cuenta entera.

Es la misma familia que **"una captura en verde no prueba nada si el código
viejo también la mostraba en verde"**, y que la ausencia de error del push
silencioso: en los tres casos se confundió *no encontrar contradicción* con
*haber verificado*.

De acá en adelante:

1. **Un fixture sirve para probar el CÓDIGO contra un caso conocido, nunca para
   probar una hipótesis sobre datos que no se miraron.** Si la pregunta es "¿por
   qué este número da esto?", la respuesta sale de la base, no de un `insert`
   que se escribió para que diera eso.
2. **Cuando hay una consulta lista que contesta la pregunta, se corre.** Razonar
   mientras la herramienta está a mano es la forma cara de equivocarse.
3. **Al explicar un número de producción, decir de dónde salió cada parte.** En
   este caso el 74 y el 26 eran del cliente y la estructura de dos fichas era
   invención — y no estaba dicho, que es lo que la volvió creíble.

Corolario del 08/09, y es el mismo error por un vector nuevo: **una CAPTURA
DE PANTALLA con nombres de artículos reales se lee como producción.**

Se mandó el Cotejo a 390px con cuatro tarjetas de ejemplo, una de ellas
"Tomate Perita" con un desvío de +6. El número era del fixture; el de
producción era +1. Y como al lado había tres tarjetas más con nombres reales
y el mensaje hablaba de un hallazgo real, se leyó —con razón— como una
medición, y llevó a preguntar cuál de los dos números estaba mal. Ninguno:
uno era de la base y el otro mío.

Es el mismo corolario de abajo, pero la captura es peor que una tabla de
texto: **no tiene dónde escribir la aclaración.** El pie del mensaje se
separa de la imagen apenas se scrollea.

**Y el bucle se cerró**: a partir de ese +6 se pidió la lista de todos los
artículos afectados. Una vuelta más y la consulta se escribía para perseguir
un número inventado — que es exactamente el corolario 6 (una medición falsa
decide qué se arregla después) alimentado por éste. Las dos familias se
encadenan: el fixture entra como dato, el dato pide una medición, y la
medición se escribe para un hecho que no existe.

Lo que lo hizo peor no fue el número suelto: fue que **llegó con la autoridad
de una medición**, en un mensaje que tenía hallazgos reales al lado. Un
número de fixture rodeado de datos verdaderos hereda su credibilidad.

De acá en adelante, en toda captura de prueba: **nombres inventados y que se
note** ("EJEMPLO Uno", "Caja de ejemplo"). Si el caso exige un artículo real
—porque el bug depende de sus datos—, va dicho **en la línea ANTERIOR a la
imagen, no en el pie**: el pie se separa de la captura apenas se scrollea, y
lo que se lee primero es la imagen.

Corolario del 05/09, y es la SEGUNDA vez con el mismo fixture: **un número de
un fixture no se presenta con la etiqueta de un dato de producción.** Se
predijo "Pepino · Pepino Bolsa: −150 → −40" para verificar un arreglo. Los dos
números salían de un fixture inventado; en producción no se movió nada. La
tabla no decía en ninguna parte que fueran de prueba, y con el nombre del
artículo real al lado se leyeron —con razón— como una predicción sobre la
base. **Un fixture demuestra el MECANISMO, nunca la MAGNITUD**, y si el número
sale de un fixture eso va escrito en la misma línea que el número.

Corolario del 07/09, y es la TERCERA vez con la misma familia: **un fixture que
yo mismo defino no puede validar los NOMBRES de la base.** Se mandó una consulta
del cherry escrita contra `parametros`, `fichas`, `compras_renglones`,
`reprocesos.fecha` y `reprocesos.cajas_armadas` — **cinco nombres que no
existen**: son `corte_modelo`, `fichas_logistica`, `compras` (que no tiene tabla
de renglones), `reprocesos.fecha_operacion` y `reprocesos.bultos_primera`. Y se
la dio por "probada contra un fixture local".

Lo era, y no servía de nada: **el fixture lo escribí yo, con los mismos nombres
inventados.** Un `create table` propio confirma que la consulta es consistente
CONSIGO MISMA. Es la misma trampa que el fixture del 74/26 —fabricar el caso en
vez de mirarlo— pero corrida de lugar: allá se inventó el DATO, acá se inventó
el ESQUEMA.

De acá en adelante, para cualquier SQL que se mande al editor:

1. **Los nombres se verifican contra `db/esquema_completo.sql`**, que es el
   esquema real, antes de escribir la consulta. Un `grep '^create table'`
   alcanza.
2. **La base de prueba se carga CON `db/esquema_completo.sql`**, nunca con un
   `create table` escrito a mano para la ocasión. Carga entero en Postgres 16 y
   tarda un segundo. La primera vez que se hizo así, el esquema real rebotó dos
   veces el fixture (`proveedores.codigo_puesto` NOT NULL y
   `compras_cantidad_cargada_check`) — dos errores que el esquema inventado no
   habría encontrado nunca.
3. **"Probada" solo se escribe si corrió contra el esquema real.** Si corrió
   contra uno propio, lo que se probó es la aritmética, y eso se dice así.

Corolario 2 del mismo día, y es peor que el anterior: **un arreglo se verifica
en la pantalla que lee LA CUENTA QUE SE TOCÓ, no en la que tiene el nombre
parecido.** El arreglo movía la cuenta 2 (`_SQL_STOCK_PARTIDO`, cajas por
ficha) y la verificación mandaba a mirar el "sin procesar" de Stock del
Sistema, que es la cuenta 3 (el FIFO rejugado). Nunca iba a moverse. Lo
agravante: el mapa de las tres cuentas lo habíamos escrito nosotros dos días
antes, justamente para no volver a confundirlas — y la trampa fue exactamente
la que el mapa describe.

**Antes de decir dónde mirar, hay que seguir el número desde la consulta hasta
el pixel.** Si en el camino no hay ninguna pantalla, eso también es una
respuesta y hay que decirlo: acá los cuatro lectores de la cuenta 2 o deciden
si algo aparece, o devuelven solo ids, o congelan una foto — **ninguno muestra
el número**, así que el arreglo era invisible y la verificación tenía que ser
una consulta, no una pantalla.

Corolario: **una regla de unicidad no puede depender de una extensión de
Postgres.** `unaccent` hay que habilitarla por proyecto, y una regla que se
pierde el día que se crea la base de la empresa siguiente no es una regla. Lo
que se pueda escribir en SQL puro (`translate`, `lower`, `btrim`) viaja con el
esquema y no se olvida.

## Un caso que anda con el sistema VACÍO y falla cuando tiene historia

Del 11/09, y es la forma de bug que ninguna prueba nueva encuentra — no por
descuido, sino porque **el fixture más chico que ejercita la función es
exactamente el que la aprueba mal.**

El caso. La compra que llega ya armada en caja nuestra genera su guía R sola,
y esa guía tiene que consumir **su propia compra**. Si no se dirige el
consumo, decide el FIFO, que toma el más viejo. Medido:

```
A) sola la compra de hoy                  propone  compra 777  ← la que llegó armada
B) con un CAJÓN VIEJO del mismo artículo   propone  compra 555  ← el cajón viejo
C) control: el cajón viejo solo            propone  compra 555
```

En B el resultado es **el opuesto al del mundo**: el cajón que sigue en el
piso figuraría convertido en cajas, y las cajas que llegaron figurarían como
cajón. Ninguna cuenta se descuadra —los totales dan igual— y por eso no hay
síntoma: lo único que cambia es cuál lote quedó trabajado, que es justo lo que
la pared del armado va a mirar mañana.

**Y en A anda perfecto.** Un artículo sin stock previo tiene un solo lote, así
que "el más viejo" y "el correcto" son el mismo, y la respuesta buena llega
por coincidencia.

### Por qué ninguna prueba nueva lo encuentra

Porque el fixture de una función nueva se escribe **mínimo**: un artículo, una
compra, la cosa que se está probando. Eso no es pereza — es la forma correcta
de escribir un fixture, y es la que todos usamos. **La minimalidad es
justamente la condición bajo la cual el bug es invisible.**

O sea que acá el que prueba no se equivoca en lo que afirma: se equivoca en lo
que NO puso. Es distinto del corolario 22 —allá el fixture fijaba el caso
equivocado y el test defendía el bug— porque acá el test afirma lo correcto y
pasa por la razón equivocada.

### La maniobra: plantar el RIVAL

Es el corolario 36 corrido un paso. Allá, para que un cero signifique algo,
hay que **plantar el caso**; acá, para que un acierto signifique algo, hay que
**plantar el rival** — el candidato que ganaría por default y no tiene que
ganar.

**Cómo se reconoce, y es una sola pregunta**: cuando el código ELIGE uno entre
varios —el más viejo, el primero, el más barato, el único que hay, el
default—, preguntarse **qué pasa si hay DOS**. Si el fixture tiene uno de algo
que en producción viene de a muchos, le falta el segundo, y el segundo se
escribe para que sea el que NO tiene que salir elegido.

Y la señal de que el rival está bien puesto es la misma de siempre: **con el
código roto a propósito, el test tiene que caer.** Un fixture con dos lotes
donde el equivocado no gana nunca es un fixture con un lote y ruido al lado.

## Corolario 40: un mock entrega lo que le pidieron, no lo que la consulta pidió

Del 11/09, y es una forma de test ciego que no teníamos escrita.

La guía R de una compra que viene armada se arma por los bultos **aceptados**
(`cantidad_cajones_real`), no por los estimados. El test estaba puesto, con su
caso de rechazo parcial —llegan 10, se devuelven 2, la guía tiene que salir
por 8— y verificaba el número insertado. Parecía cubierto.

El canario dice que no: cambiar la consulta para que pida
`c.cantidad_cajones` en vez de `c.cantidad_cajones_real` **no hace caer
nada**. Con un cursor falso la fila la entrega el mock —`(1, 3, 8.0, ...)`—
sin mirar una letra del SQL, así que el 8 llega igual con la columna
equivocada. El canario rompía exactamente lo que decía romper; **el test era
ciego a eso.**

**La regla**: cuando lo que cambia es **QUÉ COLUMNA pide la consulta**, el
test tiene que mirar el TEXTO del SQL. El valor no alcanza, porque el valor no
viene de la consulta: viene del fixture.

**Cómo se reconoce, y es una sola pregunta**: *¿esto que estoy afirmando
depende de lo que el mock me devuelve, o de lo que el código le pidió?* Si
depende de lo primero, el assert está midiendo el fixture. Vale para la
columna, para el `where`, para el `order by`, para el `join` — todo lo que
cambia QUÉ trae la consulta y no qué se hace con lo traído.

**Con qué engancha, y es por el lado opuesto**: el corolario 9 dice que un
test que PARCHEA la función que quiere verificar no verifica nada, porque el
parche **tapa** la línea rota. Acá el mock no la tapa: **simplemente no la
mira.** Son los dos modos de lo mismo —el test afirma algo que su propio
andamio ya decidió— y por eso la salvaguarda es la misma: romper el código a
propósito y exigir que caiga.

Y la parte incómoda: el assert del valor **no está de más**. Cuida el cableado
—que lo que la consulta trajo sea lo que entra al INSERT— que es otra cosa y
también se puede romper. Los dos asserts miran mitades distintas y hacen falta
los dos. Sacar el del valor porque "el del texto ya cubre" sería cambiar un
test ciego por otro.

## Corolario 42: un campo que se LEE bien puede no ESCRIBIRSE, y si la pantalla lo relee de la base la prueba a mano no lo ve

Del 12/09, y es el hallazgo más caro del turno.

La marca "viene armada en caja nuestra" viajaba por SEIS caminos de carga.
Los seis tenían su `ficha_en_origen_id: str = Form("")` en la firma de la
ruta, así que **leyendo el código se veían los seis completos**. Dos no la
guardaban: el ingreso directo de Depósito la validaba y no se la pasaba a
`crear_compra`, y la edición la aceptaba y el POST la tiraba.

**Y la edición es el caso que hay que entender, porque PARECÍA ANDAR.** Su
plantilla mostraba el selector con la caja ya elegida. Abrir la pantalla,
elegir una caja, guardar, volver a abrir: la caja estaba ahí. Pero estaba
porque **la pantalla la relee de la base**, no porque el guardado la hubiera
escrito — el valor que volvía era el que había puesto OTRO camino (el alta).
La prueba a mano confirma la lectura y no dice una palabra de la escritura.

La forma general, y es más ancha que este campo: **una pantalla que muestra
lo que relee de la base no puede testimoniar sobre lo que escribe.** Leer y
escribir son dos operaciones, la pantalla ejercita las dos en el mismo gesto,
y el resultado visible sale de la primera. Mientras el valor haya llegado a
la base por cualquier vía, la de escritura puede estar muerta.

Es la familia del corolario 40 —el mock entrega lo que le pidieron, no lo que
la consulta pidió— corrida de andamio: allá el que decide el resultado es el
fixture; **acá es el estado anterior de la base.** En los dos, lo que se
afirma lo produjo algo que no es el código que se quiere probar.

**Lo único que lo muestra: grepear el CONSTRUCTOR, no el campo.** Es el
corolario 3 al pie de la letra —el que falta, por definición, no nombra el
campo— y acá hizo falta grepear DOS: `crear_compra(` y
`actualizar_cantidad_compra(`, que son los dos que escriben. Cada uno tenía
un llamador olvidado, y ninguno de los dos aparece buscando
`ficha_en_origen_id`: los dos lo nombran en la firma de su ruta.

Y el test que lo deja cerrado no enumera los seis caminos a mano: **parsea
`app/main.py` con `ast`, busca las llamadas a los dos constructores y exige
que cada una pase la marca.** Una lista escrita a mano protege los seis de
hoy; el parseo protege al séptimo, que es el que nadie va a recordar.

## Corolario 43: el re-render por error es donde peor se pierde un campo

Del 12/09, y va aparte del 42 porque es un lugar distinto y nadie lo mira.

Las cinco pantallas de carga rearman el formulario cuando algo falla, y lo
hacen con un `dict` escrito a mano por rama: la base que se cae, el campo que
no valida, el artículo que no se pudo leer. **Once dicts en total.** La marca
de "viene armada" no estaba en ninguno.

**Por qué es el peor lugar, y es sobre la persona y no sobre el código: el
que reintenta corrige el campo que la pantalla le señaló y aprieta de nuevo.
No vuelve a revisar los que ya había llenado.** No es descuido — es lo
correcto: la pantalla le dijo qué estaba mal y él lo arregló. Así que el
campo perdido se va sin que nadie lo mire, y lo que queda guardado es una
compra **bien cargada salvo por eso**. No hay error, no hay hueco, no hay
nada que se vea raro después.

Es de la familia del campo sin consecuencia y del valor precargado plausible:
en las tres, el sistema termina con un dato que la persona cree haber
declarado y no declaró. Lo que cambia es el mecanismo — allá el incentivo,
acá el precargado, y aquí **el flujo de la corrección**.

**La regla**: cuando una pantalla gana un campo, el campo se agrega TAMBIÉN
en cada rama que rearma el formulario. Y como eso son once lugares de los que
se cae uno, lo que lo sostiene no es la prolijidad sino un test que las
recorre todas y falla nombrando cuál perdió la marca.

### Y el canario corrido LÍNEA POR LÍNEA, que es de lo que más sirvió

Escrito el test, se borró de a una las once líneas y se corrió el test cada
vez, mirando **qué pantalla y qué rama nombraba el error**. Primera vuelta:
**tres líneas se podían borrar sin que nada cayera.** Y las tres eran la
MISMA rama —"no se pudo leer el artículo"—, que el test no ejercitaba en
ninguna de las cinco pantallas.

Eso es lo que un canario de una sola pasada no da. Correrlo entero dice "el
test sirve"; **correrlo línea por línea dice CUÁL PEDAZO no está cubierto**,
y el patrón que forman las que no caen dice por qué: acá no eran tres
descuidos sueltos, era una rama entera sin probar. Con esa pista el arreglo
fue una sola cosa —agregar esa forma de falla al test— y no tres parches.

La segunda vuelta dejó una sola sin cubrir, y también tenía explicación: era
la acción "Agregar artículo" de la pantalla de editar, que inserta por otro
camino. Tercera vuelta: **las once caen, cada una nombrando su pantalla y su
rama.**

**Cuándo vale el trabajo**: cuando lo que se prueba es una LISTA de lugares
que tienen que hacer todos lo mismo —once dicts, seis pantallas, cinco
llamadores—. Ahí el test pasa en verde con la mitad de la lista sin tocar, y
la única forma de saber cuál mitad es romper de a una.

## Corolario 44: una suite donde uno de 2268 falla a veces y nadie sabe cuál ya no dice que sí

Del 12/09, y es el riesgo de fondo del turno — más grande que el commit que
lo destapó.

Lo que pasó: la suite dio `1 failed, 2267 passed` **una vez**, el commit salió
igual, y las corridas siguientes dieron todas verde. El nombre del test no
quedó en ningún lado.

### Lo primero, que es mío y es el arreglo más barato

`pytest | tail -1 && git commit` **commitea con la suite en rojo**: en un
pipe el código de salida es el del ÚLTIMO comando, así que el `&&` ve el de
`tail`, que siempre sale bien. Y el pipe además se comió las líneas `FAILED`,
que eran lo único que decía qué test era.

De acá en adelante la suite se corre **sin pipe**, a un archivo, y se mira el
`$?`:

    python3 -m pytest tests/ -q > /tmp/suite.txt 2>&1; echo "salió con $?"

Es la familia de *la ausencia de error no es confirmación*, con una vuelta
peor: acá el error **existía** y el comando lo tapó.

### Lo segundo, y es lo que casi me lleva a cerrar mal

Corrí diez veces en verde y estuve por escribir "no reproducible". **Las diez
fueron el MISMO orden**: no hay ningún plugin de orden instalado, así que el
default de pytest es determinista. Diez verdes sin variar nada prueban que la
corrida es repetible; no prueban que la suite sea sana, y yo las estaba
leyendo como lo segundo.

**Un conteo de corridas verdes no vale por la cantidad, vale por cuántas
COSAS distintas se movieron entre una y otra.** Diez iguales son una.

Por eso queda `tests/conftest.py` con el barajador: `SEMILLA_ORDEN=7 pytest`
corre los mismos tests en otro orden, y la semilla va por entorno —no
automática— para que un rojo se pueda repetir igual. Barajar siempre es lo
peor que se le puede hacer a un test intermitente: lo vuelve irrepetible.

### Lo tercero: la medición del orden se rompió y devolvió un número plausible

La primera versión barajaba los 2268 ids y se los pasaba a pytest con
`xargs`. **`xargs` parte la lista** cuando no entra en la línea de comandos,
así que corrió pytest cuatro veces por semilla —cada una con un pedazo— y lo
que leí fue el resumen del ÚLTIMO pedazo: `649 passed`.

Se veía como una corrida. Y no medía lo que decía medir: cuatro procesos
separados no prueban nada sobre el orden dentro de UNO. Es el corolario 11 con
otra ropa —la medición está bien hecha y contesta otra pregunta— y lo único
que lo delató fue que **649 no es 2268**. Si la suite hubiera tenido 700
tests, el número habría pasado sin que nadie lo mirara.

La forma correcta es el hook de colección (`pytest_collection_modifyitems`),
que baraja adentro de la única corrida que hay.

### El estado, dicho como está

Probado: **doce corridas en órdenes aleatorios distintos** (semillas 1 a 12),
las doce en 2268 verdes y con código de salida 0, más once en el orden por
defecto. No se reprodujo.

Eso es **no reproducible con lo que probé**, y no es "era un flake". Quedaron
sin probar la hora (la corrida roja fue a las 23:40 de Argentina, con el UTC
ya en el día siguiente) y cualquier cosa que dependiera del estado de la
máquina en ese momento. Los tres tests que usan el reloj real se revisaron a
mano: los tres miden con offsets relativos, así que no son candidatos.

### Y el riesgo, que es lo que hay que tener a la vista

**Una suite de 2268 tests donde uno falla el 9% de las veces y nadie sabe
cuál es una suite que dejó de decir que sí.** El daño no es el rojo: es que
el día que falle de verdad, la primera reacción va a ser correrla de nuevo —
y esa reacción va a estar justificada, porque ya pasó. Ahí es cuando un rojo
verdadero se merguea.

Es exactamente lo que este archivo dice en otro lado sobre el reproceso:
*"flake" no es una causa raíz*. La diferencia es que allá se trata de no
aceptar la palabra, y acá de no **fabricar** el hábito que la hace creíble.

## Corolario 46: un conteo de corridas verdes vale por lo que se MOVIÓ entre una y otra, no por cuántas son

Del 12/09, y sale del mismo turno pero es más ancho que los tests.

Corrí la suite diez veces en verde y lo reporté como "no reproducible". Las
diez fueron **el mismo orden**: sin plugin de orden, pytest es determinista.
Lo que probaron es que la corrida es **repetible**; lo conté como que la
suite está **sana**, que es otra cosa.

**Diez corridas idénticas son una corrida.** El número diez no agrega nada:
lo que agrega información es cada cosa que cambia entre una y la siguiente
—el orden, la hora, la máquina, el estado de la base—. Doce órdenes
distintos dicen algo; diez repeticiones del mismo, no.

**Vale para cualquier verificación por repetición**, no solo para una suite:
reintentar un script, recargar una pantalla, volver a correr una consulta. Si
entre un intento y el otro no cambió nada, el segundo no es una segunda
confirmación — es la primera contada dos veces. Es el mismo argumento que el
del corolario 24 cuando una base está parada: **correr no alcanza, tiene que
haber algo distinto que medir.**

Y la trampa de fondo es la de siempre en este archivo: *no encontrar
contradicción* no es *haber verificado*. Acá con el agravante de que el
conteo alto —diez— da una sensación de rigor que la evidencia no tenía.

## Corolario 49: cuando un registro se arma al IMPORTAR, la forma de llamar importa tanto como qué se llama

Del 12/09, y va corto.

La alerta nueva se registró con `contar=contar_unidades_que_diferen` —la
referencia a secas— y las otras dieciocho usan `contar=lambda:
contar_...()`. El registro se construye al importar el módulo, así que la
referencia **captura el objeto de ese momento** y deja de seguir al nombre:
parchearlo después no lo toca. La lambda lo resuelve al llamar.

El síntoma no fue una alerta rota: fue que el test que recorre las
dieciocho intentó ir a la base de verdad, porque su `patch` no tenía efecto
sobre la única entrada escrita distinto.

**Lo que se lleva, y es más ancho que el registro de alertas**: en cualquier
tabla de callables armada a nivel de módulo —alertas, validadores, un
despacho por tipo— la referencia directa y la lambda **no son dos estilos**.
Una congela y la otra no, y la diferencia solo se ve cuando alguien quiere
sustituir la función: un test, un modo de prueba, un reemplazo en caliente.

Y lo agarró el test que las recorre TODAS, que es exactamente para lo que
está: la entrada nueva era la única escrita distinto de las dieciocho, y esa
inconsistencia no se ve leyendo la entrada sola — se ve al lado de las otras.

## Corolario 50: `split("</style>")` no aísla el marcado — falla por DOS lados, y los dos aparecieron el mismo día

Del 12/09. El corolario 38 dice anclar los asserts de HTML afuera del CSS y
de los comentarios, y da la receta: `respuesta.text.split("</style>")[-1]`.
La receta tiene dos agujeros y los dos mordieron en el mismo turno.

1. **El `<script>` queda ADENTRO.** Un assert de `'name="compra_devolucion_id"
   ' not in marcado` falló matcheando el selector del JS de la pantalla
   (`marcarElegidas('input[name="compra_devolucion_id"]')`). El JS es una
   tercera región de texto, igual que el CSS y los comentarios, y `[-1]` no
   la saca.
2. **Una plantilla INCLUIDA trae su propio `<style>`, y entonces `[-1]` corta
   DE MÁS.** El detalle de la compra incluye `_fotos_guia.html`: el último
   `</style>` del documento es el de la incluida, así que `[-1]` devuelve el
   pedazo final y **se come entera** la tarjeta que se quería verificar. El
   assert falló diciendo que la tarjeta no estaba, cuando estaba.

Los dos fallan en direcciones opuestas —uno deja texto de más, el otro saca
marcado de más— y por eso ninguna cantidad de `[-1]` los arregla. Lo que
sirve es lo que el 38 ya decía en su última línea y conviene subir al
principio: **anclar en algo que SOLO pueda ser marcado.** Una etiqueta
cerrada (`<h3>…</h3>`), un atributo entero (`<select id="proveedor_id"`),
una clase (`class="dev-cabeza"`). Eso no aparece en prosa, no aparece en CSS
y no aparece en un selector de JS.

**La señal de que hay que revisar el ancla, y es la misma que la del 38**:
el test falla apenas se escribe y la primera lectura es "me equivoqué en el
assert". Antes de aflojarlo, mirar QUÉ fragmento matcheó o QUÉ pedazo quedó
en `marcado`. Si el texto está en el documento pero no en `marcado`, el
problema es el corte; si está en `marcado` pero no en el marcado de verdad,
es la región.

### Y el partial que entra AL FINAL rompe el corte de toda la suite, la mitad en silencio

Del 18/09, y es el caso 2 otra vez con una consecuencia que no estaba
escrita. El modal de "vino armada" se incluye al final de siete pantallas y
trae su propio `<style>`: desde ese día, en esas siete, el ÚLTIMO `</style>`
del documento es el suyo, así que `split("</style>")[-1]` devuelve la cola
del partial y **se lleva la pantalla entera**.

**Cayeron doce tests, y ésos no son el problema: un rojo se lee.** El que
importa es el que NO cayó — `assert "No se recepcionó" not in marcado`, que
sobre un pedazo que ya no tiene la pantalla adentro **pasa siempre**. Un
corte que se lleva de más apaga en verde todos los asserts por la negativa
que tenía adentro, y un test apagado se ve exactamente igual que uno que
mira. La suite salió 2604 en verde con uno de ellos ciego.

**Cómo se enumeran, que es lo único que los encuentra**: no por el rojo, sino
cruzando los tests que usan el corte contra las pantallas que ganaron el
partial. Un script sobre el `ast` que liste las funciones que tienen
`split("</style>")` **y** nombran una de esas URLs los devuelve todos —acá 15,
de los cuales 12 fallaban y **1 pasaba vacío**— y los otros dos resultaron ser
de pantallas que no tienen el partial, o sea falsos positivos informativos.

**Y el arreglo no fue reescribir doce asserts ni correr el `<style>` de
lugar** —eso último es mover el mundo para que entre en la medición, y el
partial siguiente lo rompe igual—: el partial declara una COSTURA
(`<!-- modal-vino-armada -->` como primera cosa que emite) y el corte va
primero por ahí y recién después por el CSS. La costura es marcado de verdad,
no aparece en prosa ni en CSS ni en un selector de JS, y está puesta a
propósito con su comentario al lado diciendo para qué. Con el canario que se
la saca, los trece tests caen — que es la prueba de que el corte apoya ahí y
no en la suerte.

## Un canario que MUTA archivos no se corre en segundo plano, y si se lo mata deja el código roto

Del 12/09, y es de la herramienta, no del código. Los canarios de este
proyecto rompen el código a propósito, corren la suite y restauran. Corrí uno
en segundo plano y seguí trabajando en el mismo árbol. Dos daños, y el
segundo es el caro:

1. **Todo lo que corrí mientras tanto midió un árbol roto.** Dos tests
   "fallaron" y me puse a arreglar tests que estaban bien: el archivo que
   leían lo estaba pisando el canario. Es la familia del fixture inventado —
   perseguir un hallazgo que no existe— con el agravante de que la causa no
   está en ningún archivo, está en otro proceso.
2. **Matarlo dejó una avería puesta.** El `finally` que restaura no corre con
   un `SIGTERM` en el momento equivocado: el canario le había sacado el
   `AND m.anulado_el IS NULL` a una consulta y ahí se quedó, sin diff
   sospechoso —la línea se ve perfecta— y sin nada que avise. Lo encontró el
   canario SIGUIENTE, que reportó "NO APLICA (0 veces)" porque el texto que
   iba a romper ya no estaba.

De acá en adelante:

- **En primer plano, siempre.** Un canario que muta el árbol es incompatible
  con cualquier otra cosa que lo lea.
- **Después de matar uno, se mira qué quedó escrito**, no si el comando se
  quejó. Es literalmente la regla del editor de Supabase que escribe a
  medias, aplicada al repo: `git diff` leído contra lo que uno quiso
  escribir, no contra la sensación de que se restauró.

### La consecuencia que es más grande que el incidente

**Todo resultado de test posterior a lanzar un canario en segundo plano es
inválido, y no hay forma de saber CUÁLES lo eran.** El canario rompe y
restaura en ciclos de medio minuto: una corrida cae adentro de un ciclo o no,
y eso no queda anotado en ningún lado. Así que no se salva la parte buena —
**se descarta todo lo posterior al lanzamiento y se corre de nuevo.**

Eso es lo que lo vuelve una regla y no un descuido: el costo no es el rato
perdido arreglando dos tests sanos, es que **queda un bloque de evidencia
que no se puede auditar.** Un verde de adentro de ese bloque no prueba nada
y tampoco se distingue de uno bueno — es exactamente la ausencia de filas
del backfill, pero en la herramienta con la que se decide si algo se
mergea.

### La señal, que es la única barata

**Si un test falla y lo que afirma se ve correcto en el código, verificar
que no haya un proceso tocando el árbol ANTES de "arreglar" el test.**

La reacción natural es la contraria —el test falla, algo estará mal en el
test o en el código— y esa reacción es correcta el 99% de las veces, que es
justo lo que la vuelve peligrosa acá. `ps aux | grep` cuesta un segundo y es
lo que separa "el código no hace lo que digo" de "el archivo no dice lo que
escribí".

Es el corolario 22 corrido de lugar: allá la pregunta era *"¿este test
afirma lo que hoy queremos?"*; acá es **"¿el archivo que el test leyó es el
que yo escribí?"**. Las dos veces el reflejo de arreglar el test es lo que
hace el daño.

Y el detalle que lo volvió barato: **"NO APLICA (0 veces)" es información, no
un problema del script.** Un canario que no encuentra qué romper está
diciendo que el código no dice lo que uno cree. Vale tanto como uno que no
hace caer ningún test (corolario 35), y por la misma razón: las dos veces lo
que falla es la herramienta de verificar, que también es código.

### Y UN `| head` LO MATA IGUAL QUE UN SIGTERM (23/09)

La regla de arriba dice que matar un canario deja la avería puesta, y uno
piensa en `kill`. **Un pipe también lo mata**: `python3 canarios.py | head -3`
cierra la tubería en la tercera línea, el proceso se lleva un SIGPIPE en el
medio de la tanda, y el `finally` que restaura no corre.

Pasó así el 23/09, y el modo de falla es el peor de esta familia porque
**parece un canario que se portó raro**: la tanda siguiente sacó su foto de un
árbol ya mutado, un canario reportó `ancla x0` —el texto que iba a romper ya
no estaba— y otro hizo caer dos tests en vez de uno. Los tres síntomas se leen
como "el canario está mal escrito", que es exactamente lo que no era.

Lo accionable, y son dos cosas:

- **La salida de un canario va a un ARCHIVO y se lee después** (`> /tmp/x.txt`
  y `cat`), nunca por un pipe que pueda cerrarse. `tail` al final del pipe es
  igual de peligroso que `head` si el proceso escribe de a poco.
- **Y el control de lo que quedó escrito se hace POR MUTACIÓN**, no mirando si
  `git status` se ve raro: acá el archivo figuraba modificado igual, porque
  tenía el trabajo del turno sin commitear. Lo único que lo encontró fue
  grepear las seis mutaciones una por una y contar — `6 de 6 controladas`.

### Y una vuelta más, del 13/09: el archivo en disco puede estar bien y PYTHON TENER CARGADO EL OTRO

La regla de arriba dice mirar qué quedó ESCRITO después de un canario. No
alcanza: el 13/09 el archivo estaba perfecto —`git diff` y el `grep` lo
confirmaban— y la medición siguiente devolvió lo que decía el archivo
MUTADO. **`__pycache__` servía el `.pyc` compilado durante el canario.**

**El síntoma fue un canario en CERO**, que es el peor de todos porque ya
tiene una lectura escrita en este archivo: el corolario 16 dice que un
canario que no muerde significa que el test es flojo, y el 35 agrega que
puede ser el canario el que está mal. **Ésta es una tercera causa que se ve
idéntica a las dos** — el control y la corrida nueva daban EL MISMO
resultado, o sea "el arreglo no cambia nada", cuando lo que pasaba era que
las dos corridas midieron el mismo módulo viejo.

Y la trampa es que la verificación que la regla manda hacer —leer el
archivo— **sale en verde**. Lo confirma, incluso: el archivo dice lo
correcto. Lo que está viejo no está en el disco, así que ningún `git diff`
lo puede mostrar.

**Las dos señales, y las dos son baratas:**

1. **Después de un canario que muta archivos, borrar el pycache ANTES de
   medir cualquier cosa** (`find . -path "*/__pycache__/*" -delete`), y en un
   script de medición que corre varias veces, forzar la reimportación
   sacando los módulos de `sys.modules`.
2. **Si un canario da cero JUSTO DESPUÉS de otro canario, sospechar de esto
   antes que del test.** El orden de sospecha cambia según lo que pasó
   recién: en frío, un cero es el test o el canario (16 y 35); atrás de una
   tanda de mutaciones, es primero el módulo cargado.

Es exactamente la familia del corolario 47 —un cero que no puede dar
distinto de cero no es una medición— con el mecanismo corrido un lugar:
**allá el número no podía moverse porque medía lo que no era; acá no podía
moverse porque el código que corría no era el que se acababa de escribir.**

### Y el tercer daño, del 14/09: `git checkout --` restaura el CANARIO y se lleva el TRABAJO

Cuatro canarios en una tanda, tres restaurados con `.bak` y **el cuarto con
`git checkout -- templates/...`**. Los tres primeros quedaron bien. El cuarto
**borró el bloque entero de la plantilla**, que era el trabajo del turno.

Y es obvio dicho así: **`git checkout --` restaura a lo COMMITEADO**, y en el
medio de una tanda de canarios lo que se está probando es justamente lo que
todavía no está commiteado. El comando hizo exactamente lo que promete; lo que
estaba mal era pedírselo.

**Lo peor es que se ve como un éxito.** El canario había mordido —los dos
tests correctos cayeron— así que la parte que uno estaba mirando salió bien, y
el archivo volvió "a como estaba" en el único sentido que git conoce. El
síntoma llegó después y disfrazado: tres tests en rojo que parecían de otra
cosa.

**La regla es una sola y no admite mezcla: el método de restauración es el
MISMO para todos los archivos de la tanda.** Si es `.bak`, es `.bak` para
todos. Mezclar dos métodos es tener uno que funciona y uno que destruye, y
nada al mirar el comando dice cuál es cuál.

### La otra mitad: un `-k` corre lo que NOMBRASTE, no lo que TOCASTE

El mismo día, y las dos veces la herramienta contestó bien otra pregunta.

Los canarios se corrieron con `pytest -k "historial or ..."`, y ese filtro
tuvo los dos errores posibles a la vez:

- **Barrió de más**: matcheó un test viejo que no tenía nada que ver, y su
  nombre apareció en la salida como si fuera uno de los nuevos. Tres minutos
  buscando de dónde salía un test que yo no había escrito.
- **Y de menos, que es el caro**: **tres tests viejos de la pantalla que
  estaba tocando se estaban cayendo y el filtro no los veía.** Eligen una
  ficha —el camino que acababa de ganar una lectura más— y sin el parche
  nuevo se iban a la base de verdad.

**Lo que se rompe casi nunca es lo que nombraste**: es lo de al lado, que
comparte la pantalla o la función. Un `-k` sirve para iterar rápido sobre un
test que se está escribiendo; **no sirve para decidir que un cambio está
bien.** Eso lo decide la suite entera, y cuesta cuarenta segundos.

Engancha con el corolario 45 —una medición que devuelve un total trae el total
esperado al lado—: `47 passed` sobre un `-k` se lee igual de verde que
`2358 passed`, y no dice lo mismo.

## Corolario 51: un `except Exception` convierte un error de ARRANQUE en una degradación permanente y silenciosa

Del 12/09. `_compras_del_renglon_para_devolucion` se traga el error a
propósito y devuelve vacío, y **el argumento es bueno**: sin poder rejugar el
FIFO, el camino que queda es el del proveedor suelto, que es el mismo que
usan las devoluciones de un renglón sin lote. Que no se pueda leer una lista
no puede dejar sin CARGAR una devolución.

Lo que no estaba pensado: **`compras_que_alimentaron_el_renglon` no estaba
importada en `app/main.py`.** El `except` se comía el `NameError`, la
pantalla caía al proveedor suelto, y ahí se quedaba **para siempre**.

### Por qué es peor que un error a secas

El `except` se escribió contra una falla **ambiental e intermitente** —la
base que no contesta— y también atrapa las de **programación**: `NameError`,
`AttributeError`, `TypeError`. Y esas dos clases son opuestas en lo único
que importa acá:

- La ambiental pasa **a veces**, y el camino degradado es el correcto
  mientras dure.
- La de programación pasa **siempre**, y el camino degradado deja de ser la
  excepción: **pasa a ser el único que existe.**

Y no se distinguen desde afuera. La pantalla que cae al proveedor suelto
porque la base está caída y la que cae porque una función no existe se ven
**exactamente iguales** — y la segunda se ve igual que el caso legítimo, el
renglón sin lote. No hay error, no hay hueco, no hay nada raro que mirar. Es
la familia del campo que se escribe y nadie lee, corrida un paso: acá la
función **no se llama nunca** y el sistema se ve entero.

**Y no era silencioso en los logs**: el `logger.exception` está puesto y
habría gritado en cada request. Era silencioso **en la pantalla**, que es
donde alguien mira. Corolario 19 otra vez — la salvaguarda que existe y no
se lee. `logger.exception` aparece **43 veces** en `app/main.py`, así que el
patrón es de la casa y no de esta función: cualquiera de las 43 puede estar
tapando un import que falta, hoy, sin que nada lo diga.

### Lo que lo agarró, y es una herramienta que no sabíamos que teníamos

**`patch("app.main.compras_que_alimentaron_el_renglon")` es, él solo, una
aserción de que `app.main` importa ese nombre.** `mock.patch` no crea el
atributo: si no está, levanta

    AttributeError: <module 'app.main'> does not have the attribute '...'

y el test cae ruidosamente **antes de ejercitar una sola línea**. O sea que
lo encontró un test que ni siquiera estaba escrito para eso — el que verifica
que la pantalla ofrezca las compras — y lo encontró por NOMBRAR la función,
no por correrla.

De ahí sale lo accionable, y es barato: **todo camino nuevo que llame a un
colaborador nuevo lleva un test que lo PARCHEA**, aunque el test venga a
verificar otra cosa. El parche paga el import gratis. Sin ningún test que lo
nombre, un `except Exception` puede sostener un `NameError` indefinidamente.

### La señal para reconocerlo sin sufrirlo

Cuando se escribe un `except` amplio para degradar con elegancia,
preguntarse: **¿cómo me entero si la degradación es PERMANENTE?** Si la
respuesta es "por los logs", no hay respuesta —nadie los lee— y si es "se
vería raro en la pantalla", tampoco: el caso degradado se diseñó justamente
para verse bien.

Las dos salidas que sirven, y con cualquiera alcanza:

- **Angostar el `except`** a lo que de verdad se está anticipando
  (`psycopg.Error` y no `Exception`), para que un `NameError` explote como lo
  que es.
- **Un test que atraviese el camino BUENO**, no solo el degradado. Un `except`
  que nunca se ejercita a la inversa es un `if` con una sola rama probada.

### Y la otra copia, buscada el mismo día (corolario 2)

Si el `except` puede sostener un `NameError`, la pregunta inmediata es
cuántos más hay escondidos detrás de los otros 42. **Se barrió `app/` y
`core/` con `pyflakes`: 0 nombres indefinidos.**

Y el cero está verificado, porque un cero sin canario no informa (corolario
47): plantado a propósito el mismo caso de hoy —una llamada a una función
inexistente adentro del mismo `except`— pyflakes lo nombra con archivo y
línea, y sacándolo vuelve a 0. O sea que **hoy no hay ninguna otra**, y eso
es un hecho medido y no una impresión.

**CONSTRUIDO el 18/09** (`f18fd1f`, `tests/test_nombres_indefinidos.py`):
`pyflakes` entró a `requirements.txt` y el barrido es un test de la suite, con
su par plantado al lado para que el cero se pueda leer. Mira SOLO los nombres
indefinidos: los imports sin usar y las variables sin leer quedan afuera a
propósito, porque un guardia que marca doce cosas inofensivas se aprende a
ignorar.

**Y el 20/09 escribí una SEGUNDA copia del mismo test** (`84f28ad`,
`tests/test_pyflakes.py`), sin ver que la primera existía. Las dos corren
`pyflakes`, las dos tienen su canario, y la de 20/09 cubre además `scripts/`.
Ninguna falla: **la suite hace el trabajo dos veces y nadie se entera** — que
es el modo de falla de una copia que no se separó todavía.

Lo que lo dejó pasar es exactamente lo que este archivo pide y yo no hice:
**el `grep` del concepto antes de bautizar**. `grep -l pyflakes tests/` cuesta
un segundo y habría devuelto el archivo del 18/09. Queda anotado acá y no
arreglado en el mismo commit porque borrar un test es código, y esto es una
corrección de texto.

**Y la oración que estaba acá —"queda anotado y no construido"— sobrevivió
DOS DÍAS a su propia construcción**, y es la copia de este archivo que
siempre se olvida: al arreglar algo el `grep` sale sobre `app/`, `core/` y
`tests/`, y CLAUDE.md no se rompe nunca. Con el agravante de que acá el que
la leyera iba a construir por tercera vez lo que ya estaba dos veces.

## Corolario 55: el código INALCANZABLE no lo ve ninguna suite, porque no hay test que pueda verlo

Del 12/09. Reescribiendo la ruta de Analizar Artículo, el corte del reemplazo
buscó el PRIMER `return templates.TemplateResponse(...)` en vez del último, y
quedaron **cincuenta líneas de la ruta vieja debajo del `return` de la
nueva**. La suite dio **2326 de 2326**.

**Y no es que faltara un test: es que no puede existir.** Un test recorre
caminos, y el código inalcanzable no tiene ninguno. Todas las otras trampas
de este archivo son tests que se podían haber escrito —el fixture que fijaba
el caso equivocado, el mock que no miraba el SQL, el canario que no rompía
nada—. **Acá la categoría entera de evidencia no aplica**, y por eso el verde
es sincero: la suite contestó bien la pregunta que sabe contestar.

### Lo que sí lo ve, medido y no deducido

`pyflakes` **no marca el código muerto como tal** —un bloque inalcanzable
prolijo le sale en 0— pero **sí lo analiza por dentro**, y ahí está el
enganche: el código que deja una reescritura nombra los IDENTIFICADORES
VIEJOS, porque contra esos se escribió. El bloque de acá usaba
`articulo_valor`, que la versión nueva ya no define.

Reconstruido el caso real (la función nueva con la cola vieja abajo):

```
con la cola muerta   ->  undefined name 'articulo_valor'  (linea 17)
sin la cola (control) ->  0
```

O sea que lo habría agarrado, **y no por detectar código muerto sino por
detectar código VIEJO**. Es una segunda razón para el `pyflakes` que quedó
*anotado y no construido* en el corolario 51: allá se propuso para el
`NameError` que un `except` amplio se traga, y cubre también esto — dos
agujeros distintos, la misma herramienta, y sigue siendo una dependencia que
hay que decidir.

### Lo que lo agarró de verdad, que fue más barato

**Un `grep` de los nombres viejos después de la reescritura** (`articulo_id`,
`del_articulo`). No es una técnica nueva: es la regla del canario que se mata
—*se mira qué quedó escrito, no si el comando se quejó*— aplicada a un
reemplazo grande. Después de cambiar una función entera, lo que hay que
mirar es el archivo, no el resultado de la suite.

**La señal**: si una reescritura cambia los nombres que la función usa
—`articulo_valor` a `cliente_valor`—, esos nombres viejos son la sonda. Si
alguno sobrevive, hay que ir a ver dónde quedó.

### Y la guarda que sí disparó, que vale como práctica

El script que borraba el bloque llevaba un assert de lo que esperaba
encontrar (`TemplateResponse` cuatro veces). Encontró **tres**, falló, y **no
escribió nada**. Recién contando bien se borró.

Eso es lo que separa un borrado a ciegas de uno verificado: **un script que
modifica código lleva escrito qué espera encontrar, y si no lo encuentra no
toca el archivo.** Es la familia del corolario 35 —la herramienta de
verificar también es código— del lado bueno: la suposición estaba mal, y el
assert la convirtió en un error en vez de en un borrado de más.

## Corolario 57: si una medición sobre HTML dice que DOS cosas cumplen una condición excluyente, sospechar del RECORTE

Del 12/09. Midiendo si la pantalla de Analizar marcaba bien cuál número
calculó ella, el detector decía que estaban marcados **los dos** —el precio y
la rentabilidad— en casos donde la pantalla marca uno solo. Por un momento
pareció que la pantalla estaba mal.

El regex era:

```python
re.search(rf'<label for="{campo}"[^>]*>.*?marca-calculado', cuerpo, re.S)
```

Con `re.S` el `.*?` **cruza de un `<label>` al siguiente**: desde el del
precio barre hasta encontrar la marca en el de la rentabilidad, y contesta que
sí. O sea que para el precio la respuesta era "sí" siempre, pasara lo que
pasara, y la herramienta **no podía contestar "solo éste"** — que es
exactamente la pregunta que se le estaba haciendo.

Es el corolario 50 otra vez (`split("</style>")[-1]` cortando de más o de
menos) y el 4 (calificar el assert para que solo matchee lo que se quiso
probar), los dos por el mismo mecanismo: **en HTML todo vive en el mismo
texto, así que un recorte mal puesto contesta por el vecino.** Se arregla
acotando al elemento —`(.*?)</label>`— y preguntando adentro de eso.

**LA SEÑAL, y es la que vale porque se puede usar sin haber sufrido el
caso:** cuando una medición sobre HTML dice que **dos cosas cumplen una
condición que es excluyente por diseño** —dos campos "calculados" cuando solo
uno puede serlo, dos filas "seleccionadas", dos pestañas activas—, lo primero
que hay que revisar es el RECORTE, no el código. El código tiene una razón
para respetar la exclusión; el regex no sabe que existe.

Y engancha con el 53 por el lado constructivo: un detector que devuelve "los
dos" siempre es un detector que no puede dar la otra respuesta. La prueba
barata es la de siempre — **correrlo sobre el caso que tiene que dar "solo
éste"**, y si no lo da, el problema es la herramienta.

**Y volvió el 15/09 sobre la BARRA DE NAVEGACIÓN, que es donde más barato
muerde**: el mismo `href` aparece DOS veces ahí por diseño —el ícono de
sector y el botón de atrás— así que
`assert 'href="/administracion"' in marcado` matchea el ícono, que el
`aria-label` de la línea de arriba ya cubría. O sea: **un assert que no
podía fallar, escrito al lado del que sí lo cubría**, y la redundancia es
justamente lo que lo disfrazó de verificación. Medido: el canario que
devolvía el atrás a `/precios` hizo caer CERO.

Y lo que lo vuelve peligroso es qué tapaba: el atrás roto es EL bug que se
estaba arreglando —la que entra por Administración sale a otro sector—, así
que el test que venía a cuidarlo era ciego exactamente ahí.

**El ancla en HTML es el elemento, no el atributo**: `href="/administracion"
aria-label="Volver atrás"`. Es el corolario 59 (preguntar por la posición
gramatical) traducido: allá la palabra clave que precede al nombre de la
tabla, acá el atributo que solo ese elemento tiene.

### Y un ARREGLO puede mudar dónde matchea un assert, y dejar sin guardia lo que el test dice mirar (18/09)

`test_las_DOS_pantallas_que_eligen_lote_DIBUJAN_el_kilaje` preguntaba
`"lote.kilaje" in marcado` sobre cada plantilla. Estaba bien mientras la única
mención fuera la del selector. Ese día la PARED de Reproceso ganó su
`{% if lote.kilaje %}` —el arreglo de este mismo turno— y desde ahí **el assert
pasaba por la pared**: el selector, que es lo que el test se llama a sí mismo,
podía perderlo entero. Medido con el canario que se lo borra al helper del JS:
**cayó CERO.**

Lo que lo vuelve distinto del corolario 4 —un assert que nunca pudo fallar— es
que **éste sí podía, y dejó de poder por un cambio CORRECTO en otro lugar del
mismo archivo.** No hay nada mal escrito que señalar, ni en el assert ni en el
arreglo: el que agrega la segunda mención no tiene por qué saber que hay un
`in` file-wide dependiendo de que haya una sola.

**La señal, y se hace al agregar la mención, no al leer el test**: cuando un
cambio escribe por segunda vez en un archivo un nombre que ya estaba —una
variable, una clase, una columna— grepear ese nombre **en los tests**. Si algún
assert lo busca con un `in` sobre el archivo entero, ese assert acaba de
cambiar de sujeto. Es el corolario 3 (grepear quién CONSTRUYE, no el campo)
aplicado a los tests: el que se rompe no nombra el lugar por el que empezó a
pasar.

El arreglo es el de siempre —anclar en algo que solo pueda ser lo que se quiso
probar—, y acá lo que solo puede ser el renglón del selector es la expresión
que lo pega: `lote.kilaje ? " de " + lote.kilaje : ""`, contada `== 1`. El
conteo importa tanto como la expresión: con un `in`, una tercera copia del
rótulo pasaría igual.

**Y VOLVIÓ EL 18/09, en el mismo turno, por la otra causa posible.** Allá el
assert se mudó porque un ARREGLO agregó la segunda mención; acá porque **el
mismo commit agregó una SEGUNDA SENTENCIA** que la contenía: la recarga copia
los renglones a mano y, al lado, la sucursal que falte — y las dos dicen
`viejo.agregado_a_mano_el`. Dos tests quedaron anclados ahí, y la copia de la
sucursal va primero:

- el que afirma QUÉ copia el INSERT terminó leyendo el de sucursales;
- y el que afirma que la copia va **ANTES del traslado del armado** pasaba con
  la copia de renglones movida DESPUÉS — o sea, con el bug que su nombre dice
  cuidar puesto.

Los dos se anclan ahora en `viejo.cantidad_original`, que solo la copia de
renglones tiene. **Y a los dos los encontró el canario, no la lectura**: el
primero falló en rojo al escribirlo, el segundo pasó en verde y solo se vio
porque el canario que borra la copia entera dio 1 donde tenía que dar 2.

**La regla corta, con las dos causas juntas**: un `in` sobre un archivo entero
afirma "esto está en algún lado", no "esto está donde digo". Cualquier segunda
mención —la agregue un arreglo o la agregue el mismo commit— le cambia el
sujeto sin que nada se ponga rojo. El ancla tiene que ser algo que **solo**
pueda estar en el lugar que se quiere probar.

**Y LA TERCERA CAUSA NO ES UNA SEGUNDA MENCIÓN: SON N HERMANOS (20/09).** El
panel de "el súper cambió el pedido" tiene **un formulario por renglón MÁS el
del alta**, y todos llevan el mismo `<input name="volver_a">`. El assert era
`'name="volver_a" value="armar"' in marcado` y **pasa con el hidden puesto en
UNO SOLO** — el canario que se lo saca al formulario de la cantidad hizo caer
CERO sobre 2903 tests.

Lo que se perdía es el que se usa todos los días: sin `volver_a`, corregir un
bulto desde Armar devuelve al operario a la otra pantalla en el medio del
armado, que es exactamente el viaje que el panel vino a ahorrar.

**Acá el ancla no alcanza**, y por eso es una causa aparte: no hay ningún
fragmento que esté en un formulario y no en sus hermanos — son el mismo
marcado repetido. **Lo único que lo separa es el DENOMINADOR**: partir el
panel en sus `<form>` y exigir `conteo == len(formularios)`, con un
`len >= 2` al lado para que el conjunto vacío no pase solo.

**La señal, y se hace al escribir el assert**: si lo que se afirma vive en
algo que la pantalla REPITE —un renglón, una tarjeta, una fila, un
formulario por ítem— un `in` contesta por el más suertudo. La pregunta es
*¿cuántos tendrían que tenerlo?*, y si la respuesta es "todos", el assert
es un conteo.

**Y la misma frase estaba escrita en otros DOS lugares afirmando lo contrario**
— el mensaje del commit que agregó el kilaje (*"la pared de Reproceso lo trae
también: ahí se está decidiendo qué hacer"*) y el comentario del fixture de esos
tests (*"el contenido por bulto de cada lote, que la pared dibuja al lado del
quedan"*). Las dos envejecieron **en el commit que las volvió falsas**, que es
el corolario 28, y ninguna de las dos podía fallar: un mensaje de commit no lo
corre nadie, y el comentario de un fixture describe lo que el autor creía estar
preparando.

## Corolario 58: un `return_value` contesta TODAS las llamadas, así que el día que aparece una segunda pregunta contesta las dos

Del 14/09. `listar_precios_vigentes_por_cliente` se parcheaba así en los
tests de "Guardar y generar listado":

```python
patch("app.main.listar_precios_vigentes_por_cliente", return_value=precios_tras_guardar)
```

Y estaba **bien**: la ruta la llamaba UNA vez, para armar el archivo con lo
que quedó después de guardar. El nombre de la variable dice exactamente qué
es y el test pasaba por la razón correcta.

La carga con fecha de vigencia le agregó una SEGUNDA llamada a la misma
función, antes de guardar, para saber contra qué comparar. Con un
`return_value`, las dos preguntas —*¿qué regía ANTES?* y *¿qué quedó
DESPUÉS?*— reciben la misma respuesta: la de después. Y entonces el diff
concluye que lo tipeado ya regía, no escribe nada, y el test cae con
`x-cantidad-guardada == 0`.

**Nadie tocó el test, y el test dejó de decir lo que decía.** Es la familia
del comentario que envejece en el commit que lo vuelve falso (corolario 28)
y la del flag derivado que deja de significar su nombre (corolario 39),
corrida al andamio: **un doble de prueba también AFIRMA algo, y lo que
afirma vale solo mientras el código le haga las preguntas que tenía cuando
se escribió.**

**La señal, y se hace en el momento de agregar la llamada**: cuando una
función gana un llamador nuevo en un camino que ya tenía tests, preguntarse
**si los mocks de esa función están contestando ahora dos preguntas
distintas**. No hace falta leerlos todos: basta con mirar si el valor
parcheado tiene nombre de respuesta a UNA de las dos (`precios_tras_guardar`
lo tenía escrito en el nombre).

**El arreglo es `side_effect` con la lista en ORDEN**, y de paso el orden
queda afirmado: `[VIGENTES_ANTES, precios_tras_guardar]` dice que la ruta
primero resuelve contra qué comparar, después guarda, y recién al final arma
el archivo. Un `return_value` no puede expresar eso — y por eso tampoco
puede fallar cuando el orden se rompe.

### Y el hermano del mismo turno: redefinir una constante de módulo no da error

`HOY_DE_PRUEBA` ya existía en `tests/test_app.py` (línea 1478, `2026-08-06`).
Se definió de nuevo más abajo con otro valor para los tests de precios, y eso
**le cambió el valor a todos los tests posteriores del archivo**: cayeron tres
que no tienen nada que ver con precios —Logística, Auditoría y el recálculo de
alertas—, y el rojo se lee como "lo rompió la función nueva".

Es el corolario 14 (revisar si el nombre que se estrena ya está usado cerca)
con el agravante de que en un módulo de Python **la segunda definición gana en
silencio y solo para una parte del archivo**, así que el daño es parcial y no
se parece a su causa. El `grep` que lo evita cuesta un segundo y es el del
nombre, no el del concepto:

    grep -n "^HOY_DE_PRUEBA" tests/test_app.py

Y el arreglo es el corolario 8: el nombre lleva el alcance
(`HOY_DE_CARGA_DE_PRECIOS`), porque ese valor **no es** "hoy" para todo el
archivo — es el reloj de una pantalla.

### Cuando un canario se va igual a SEGUNDO PLANO: no se lo mata, se lo espera

Del 14/09, y es la continuación práctica de la regla de arriba. La regla dice
*en primer plano, siempre*, y el 14/09 **se fue a segundo plano solo**: la
herramienta lo movió ahí al pasar su tiempo de espera, con diez canarios por
delante y la suite entera en cada uno.

Lo que hay que hacer ahí no es lo que el reflejo pide, y son tres cosas:

1. **NO matarlo.** Matarlo deja la avería puesta —el `finally` no corre con
   un `SIGTERM` en el momento equivocado— y eso ya pasó una vez. Un canario a
   medias en segundo plano es molesto; un canario muerto a la mitad deja el
   repo roto sin diff sospechoso.
2. **No correr NADA contra el árbol mientras tanto.** Todo resultado de ahí
   es inválido y no hay forma de saber cuál. Lo único que sí se puede hacer
   es trabajo que no toca el repo: redactar, o —como esa vez— levantar una
   base de prueba y verificar una consulta contra `db/esquema_completo.sql`,
   que no comparte un solo archivo con lo que el canario está mutando.
3. **Esperarlo por su PID**, no por un reloj: `tail --pid=<PID> -f /dev/null`
   bloquea hasta que el proceso termina de verdad y no necesita adivinar
   cuánto falta.

**Y al terminar se mira qué quedó ESCRITO**, que es la parte que se olvida
porque el canario "salió bien": cero `.bak` sueltos, y un `grep` de cada
mutación para confirmar que ninguna quedó puesta. Que el comando haya salido
con código 0 no dice nada sobre el estado del árbol — es literalmente la
regla del editor de Supabase que escribe a medias, aplicada al repo.

### Un chequeo que se CUENTA A SÍ MISMO no puede contestar "ya no está"

Del 14/09, y no es de este proyecto: es de cualquier espera.

Para esperar al canario de arriba se armó un monitor con esta condición:

```
until ! pgrep -f "canario_b.py" > /dev/null; do sleep 5; done
```

**Nunca sale.** El `until` corre adentro de un bash cuya LÍNEA DE COMANDO
contiene el texto `canario_b.py`, así que `pgrep -f` se encuentra a sí mismo:
la condición es verdadera para siempre, el canario podía estar muerto hacía
diez minutos y el loop seguía girando igual.

Y el modo de falla es el peor de los baratos: **se ve idéntico a "todavía
está corriendo".** No hay error, el proceso existe de verdad, y el que espera
concluye lo contrario de lo que pasa. La espera no falla ruidosamente —
simplemente no termina nunca, que es lo que uno esperaría de un proceso que
sigue vivo.

**La señal, y se aplica sin haberlo sufrido**: si la condición de espera
BUSCA UN TEXTO, preguntarse si ese texto está en la línea de comando del que
busca. Con `pgrep -f`, con `ps | grep`, con un `grep` sobre una lista de
procesos: las tres se cuentan a sí mismas.

Las dos formas que sí contestan:

- **Por PID concreto**: `tail --pid=<PID> -f /dev/null`. No hay patrón que
  pueda matchear de más.
- **Si hay que buscar por nombre**, excluir el propio proceso
  (`pgrep -f X | grep -v $$`) o usar `pgrep -x` sobre el ejecutable, que
  mira el comando y no los argumentos.

Es la familia del corolario 47 —un número que no puede dar el otro valor— con
el mecanismo corrido a la espera: allá el cero no podía crecer, **acá la
condición no puede volverse falsa.** Y como siempre, lo que lo separa de una
espera sana es una sola pregunta: *¿esto que estoy contando me incluye?*

### Y una precisión sobre `git checkout --`, que acá SÍ era la herramienta

El 14/09 se escribió que `git checkout --` restaura el canario y se lleva el
trabajo. Sigue siendo cierto **en el medio de una tanda de canarios**. El
mismo día, un renombre masivo mal hecho tocó 107 líneas que no eran suyas y
`git checkout -- tests/test_app.py` fue exactamente lo correcto.

La diferencia no es el comando: es **si todo lo que el archivo tiene sin
commitear es algo que uno puede rehacer.** En la tanda de canarios no lo era
—ahí vivía el trabajo del turno—; en el renombre sí, porque los únicos
cambios del archivo eran los cuatro que se acababan de aplicar con un script.
Antes de usarlo: `git diff --stat` de ese archivo y preguntarse qué se pierde.

## Corolario 59: un barrido del CÓDIGO FUENTE matchea el docstring que explica lo que busca

Del 14/09, y es el corolario 38 fuera del HTML: allá el CSS, los comentarios
y el marcado comparten el texto de la plantilla; acá **el SQL, los docstrings
y los comentarios comparten el texto del `.py`**, y un test que barre el
archivo buscando un criterio no distingue una consulta de la prosa que la
explica.

El caso. Arreglado el reloj de las tablas de historial, el test que lo cuida
barre `app/db.py` y exige que ninguna consulta que nombre una de esas tablas
diga `CURRENT_DATE`. Para dejar afuera la prosa, el filtro pedía que el texto
dijera `SELECT`, `INSERT` o `UPDATE `. Y lo primero que encontró fue **el
docstring de `guardar_precios_cliente`**, que explica este mismo bug: nombra
la tabla, dice *"sale de la propia ficha dentro del INSERT"* y escribe
`CURRENT_DATE` para contar qué decía antes. Los tres requisitos, en un texto
que no es una consulta.

Es el mecanismo del 38 al pie de la letra —**un comentario explica por qué
algo es así, así que NOMBRA la cosa**, y el test busca la cosa— con la vuelta
de que acá el filtro puesto para excluir prosa **era otra palabra que la
prosa usa**. Un docstring sobre SQL habla de SELECT y de INSERT: no hay
palabra del vocabulario del SQL que sirva para separar SQL de prosa sobre SQL.

**Lo que sirve es la POSICIÓN GRAMATICAL, no el nombre**: en vez de "el texto
nombra la tabla", `(?:FROM|INTO|JOIN|UPDATE)\s+<tabla>\b`. Una tabla en
posición de tabla solo puede ser una consulta; la prosa la nombra suelta. Es
la última línea del 38 —*anclar en algo que SOLO pueda ser marcado*— traducida
de HTML a SQL: ahí una etiqueta cerrada o un atributo entero, acá la palabra
clave que precede al nombre.

**Y el ancla hay que elegirla ANTES en el árbol, no solo en el texto**: el
barrido lee literales con `ast`, y una consulta que interpola el reloj ya no
es un `Constant` sino un `JoinedStr`. Mirar solo `Constant` deja afuera
**exactamente** las consultas que se convirtieron a f-string — o sea, las que
el test viene a cuidar. El cero que devolvería sería el del corolario 47: no
podría dar otra cosa.

**La señal es la misma que la del 38 y por eso conviene reconocerla rápido**:
el test falla apenas se escribe y la primera lectura es *"me equivoqué en el
assert"*. Antes de aflojarlo, mirar QUÉ matcheó. Si lo que matcheó es un
docstring, el test tenía razón en fallar y el equivocado era el ancla.

### Volvió EN EL MISMO TURNO, y la segunda vez no falló: pasó

Horas después, el test que exige que las dos puertas del borrado de fichas
llamen a la MISMA guarda. Preguntaba
`"_negar_si_tiene_precios" in ast.unparse(nodo)`. El canario que le saca la
llamada a una de las dos y le pone una condición propia **hizo caer CERO**: el
docstring de esa función NOMBRA la guarda para explicar por qué está, así que
el texto seguía ahí con la llamada sacada.

**Y por eso la segunda vez es peor que la primera.** La del SQL falló en rojo
apenas se escribió, que es la señal del 38 y se lee sola. Ésta **pasó en
verde**: un test que afirma "las dos puertas están cerradas" sobre una puerta
abierta. No había nada que mirar — solo el canario lo dijo.

**El ancla, en un árbol, es exacta y no hay que inventarla**: un nodo `Call`
cuyo `func` es el `Name` de la guarda. Eso es la posición gramatical del 59
en su forma literal — una llamada en posición de llamada, no una palabra
adentro de una cadena. `ast.unparse` sobre una función devuelve su texto
ENTERO, docstring incluido, así que preguntarle por una subcadena es hacer
`grep` con pasos de más: el árbol ya distingue lo que el texto confunde, y
buscar en el texto lo vuelve a mezclar.

**La regla corta, para las dos apariciones**: si el nombre que busca el test
puede aparecer en prosa —y el nombre de una guarda SIEMPRE puede, porque el
comentario de al lado la explica— el test tiene que preguntar por la
ESTRUCTURA: una llamada en el árbol, una tabla en posición de tabla. Nunca
por el nombre suelto.

### Y "la posición" es cómo EMPIEZA la sentencia, no que la palabra aparezca

Tercera aparición, del 15/09, y esta vez falló **el filtro escrito para
aplicar el corolario**. `actualizar_articulo` ganó un
`SELECT unidad_compra ... FOR UPDATE` para la guarda del conteo, y el test que
exige que el UPDATE no escriba esa columna separaba escrituras de lecturas
así:

    escrituras = [s for s in sentencias if "UPDATE" in s.upper()]

**`FOR UPDATE` es una cláusula de bloqueo adentro de un SELECT**, así que la
lectura correcta entró a la lista de escrituras y el test falló contra el
código bueno.

O sea: **"la palabra UPDATE está en el texto" NO es una posición gramatical** —
es el mismo `grep` de siempre con otra ropa. La posición es
`s.strip().upper().startswith(("UPDATE", "INSERT"))`: **cómo EMPIEZA la
sentencia**, que es lo único que decide si escribe.

Y la señal fue la de siempre, que a esta altura conviene reconocer en un
segundo: el test falló apenas se tocó el código y la primera lectura fue
"rompí algo". Lo que había que mirar era QUÉ fragmento matcheó, y el fragmento
era una consulta de lectura.

## Corolario 62: cuando un caso se elimina EN EL ORIGEN, las ramas que lo atendían quedan inalcanzables — y un canario sobre ellas no muerde

Del 14/09. Precios por Período dejó de listar las fichas sin precio: el
filtro vive en UN lugar (`_armar_filas_vigencias`) y desde ahí no sale ninguna
fila con la lista vacía. Los canarios que le devolvían el renglón amarillo a
la plantilla y el `SIN PRECIO` al Excel **hicieron caer CERO los dos.**

Y el cero era correcto: **con el filtro puesto, esas dos ramas no se alcanzan
desde ninguna pantalla.** El código quedaba roto de una forma que no tiene
efecto — que es la pregunta exacta del corolario 35 (*"¿el código quedó roto
de la forma que me importa, o quedó roto de otra?"*), contestada por una causa
que ese corolario no enumera.

**Es una CUARTA lectura del canario en cero**, y conviene tenerla al lado de
las tres que ya están: el test flojo (16), el canario mal puesto (35), el
módulo viejo en el pycache (13/09). Ésta se distingue de todas por una
pregunta que no habla ni del test ni del canario: **¿el caso que estoy
reintroduciendo puede llegar hasta acá?**

### Lo accionable, y son dos cosas distintas

1. **La protección vive donde está el filtro, no donde estaba la rama.** El
   canario que sí muerde es el que revierte EL ORIGEN — y ahí cayeron cuatro
   tests, incluido el de la pantalla. Poner un canario sobre una rama muerta
   mide la rama, no la regla.
2. **Si la función de abajo es pública, su CONTRATO se prueba igual.**
   `generar_excel_vigencias` salta sola una fila sin vigencias, y eso no lo
   cuidaba nadie: el único test que la ejercitaba le pasaba filas armadas por
   el filtro. Un test que la llama DIRECTO con el caso prohibido deja la regla
   cuidada de los dos lados, y es lo que hizo que el canario del Excel pasara
   de 0 a 1.

**La señal para reconocerlo sin sufrirlo**: si el cambio SACA un caso de la
entrada, todo lo que estaba escrito río abajo para atenderlo pasa a ser
inalcanzable el mismo día. Eso no es un problema —el código muerto prolijo no
molesta— pero **cambia dónde se puede medir**: el canario tiene que apuntar al
filtro, y lo de abajo se prueba llamándolo a mano o no se prueba.

Y engancha con el corolario 55 por el otro lado: allá el código inalcanzable
era el BUG y ninguna suite podía verlo; acá es la CONSECUENCIA correcta de un
arreglo, y lo que ninguna suite puede ver es el canario que lo ataca.

## Corolario 65: el mock hace que el test no vea QUÉ COLUMNA pide la consulta, y acá eso apagaba la guarda entera

Del 15/09, y es el corolario 40 en su forma más cara hasta ahora.

Diez canarios sobre el arreglo de las unidades: **ocho mordieron y dos dieron
cero**, y los dos eran del SQL:

```
[0] la consulta del detalle deja de traer la clasificacion
[0] la ficha deja de traer unidad_compra de la base
```

La causa es la del 40: **todos los tests mockean la consulta**, así que el
valor lo entrega el fixture sin mirar una letra del SQL. `unidad_compra`
llegaba en el dict del fixture con la columna sacada del SELECT.

**Y la consecuencia es la peor de las cuatro lecturas del canario en cero**,
porque no es que el test sea flojo sobre un detalle: sin esa columna,
`ficha.get("unidad_compra")` devuelve `None`, la regla contesta "no hay
conflicto" **para todas las fichas del sistema**, y el costeo vuelve a dividir
mezclando unidades. La guarda entera queda apagada, en producción, **sin un
solo test en rojo y sin nada en la pantalla que se vea raro** — porque lo que
se vería es exactamente lo que se veía antes.

Es la familia del `except Exception` que sostiene un `NameError` (corolario
51): una degradación permanente que se ve igual que el funcionamiento normal.
Con el agravante de que acá no hay ni un `logger.exception` gritando en los
logs — no hay error ninguno, la consulta corre bien y trae una columna menos.

**La regla, que el 40 ya decía y acá se confirma**: cuando lo que cambia es
QUÉ COLUMNA pide la consulta, el test tiene que mirar el TEXTO del SQL. El
valor no alcanza porque el valor no viene de la consulta.

**Y la señal para saber DÓNDE hace falta**, que es lo que el 40 no daba: si
una guarda de Python lee un campo de un dict que viene de la base, esa lectura
tiene DOS mitades —que la consulta lo traiga y que el código lo use— y los
tests de la guarda solo pueden ver la segunda. La primera se prueba leyendo el
SQL, y es la que apaga todo cuando falta.

El ancla va **sin los comentarios** (corolario 59): un comentario de SQL
existe para nombrar la columna que el test busca, así que la colisión está
garantizada por construcción.

**Y VOLVIÓ EL MISMO DÍA, con la columna cambiada de nombre.** El modelo de
las dos magnitudes reemplazó `unidad_compra` por `unidad_conteo` en esa
consulta, y el test se mudó con ella —pregunta por `a.unidad_conteo`, con el
alias, que es el corolario 4—. Los canarios nuevos lo confirman: sacar la
columna del SELECT hace caer exactamente ese test y ningún otro.

Lo que se lleva de la repetición: **cuando una guarda cambia de columna, el
test del TEXTO se muda con ella o vuelve a valer cero.** Y el modo de falla
se dio vuelta y es igual de malo: sin `unidad_conteo`, la regla contesta
"esta ficha NO se puede costear" para toda ficha que no venda por kilo, y el
sistema se niega en silencio donde antes costeaba bien. Antes mentía de más,
ahora se niega de más — las dos sin un test en rojo.

## Corolario 66: la cuenta que sobra se apaga sola cuando la guarda va ANTES, y eso hay que decirlo o alguien la vuelve a prender

Del 15/09, y es del lado bueno.

`_envases_por_unidad_ponderado` es la segunda cuenta que mezcla las unidades
—compara `contenido_compra <= contenido_ficha` para decidir descartable o caja
chica— y era el hallazgo del análisis: nadie grepea la función de los ENVASES
buscando un problema de unidades.

**No hizo falta tocarla.** La negativa se puso donde se produce `costo_actual`,
y todo lo de abajo ya estaba guardado por `if costo_actual is not None` —
incluida la llamada al envase. Al no llamarse, la comparación no ocurre.

Eso es lo cómodo y también el riesgo: **una cuenta que quedó bien por el orden
de las guardas y no por una condición propia se rompe el día que alguien mueve
la guarda**, y no hay nada en la función del envase que diga que dependía de
eso. Es la familia del corolario 21 —una operación correcta por convención
entre dos lugares, no por construcción— con la vuelta de que acá la convención
es un `if` que está treinta líneas más arriba.

Por eso van las dos cosas, y hacen falta las dos:

1. **El comentario en la guarda dice que apagar el envase NO es un efecto
   colateral**, sino la segunda razón por la que la guarda está ahí.
2. **Un test propio del envase** (`test_el_COSTO_DE_ENVASE_tampoco_se_calcula_y_
   esa_es_la_cuenta_ESCONDIDA`), que no pasa por el costo: afirma directo que
   con las unidades distintas no sale costo de envase. Si mañana alguien mueve
   la negativa más abajo, el costo sigue dando None y ese test es el único que
   cae.

**La señal**: cuando un arreglo apaga de yapa una segunda cosa que uno no
tocó, esa segunda cosa se queda sin test propio — porque el que uno escribe
mira lo que sí tocó. Y el día que se reordene, la de yapa vuelve sin que nada
avise.

### Y el día siguiente pasó lo mejor que podía pasar: la cuenta dejó de sobrar

Del 15/09. Con el modelo de las dos magnitudes la cuenta del envase **ya no
se apaga: se arregla**. Recibe la magnitud de la ficha como argumento y
compara los dos lados en la misma unidad, así que ahora hace su trabajo en
vez de no ocurrir.

Eso convierte la deuda de este corolario en otra cosa, y conviene leer el
cambio: **una cuenta que dependía del ORDEN DE LAS GUARDAS pasó a depender de
un argumento.** El `if` que la protegía sigue treinta líneas más arriba y ya
no es lo único que la mantiene correcta — moverlo la deja bien igual.

Y el test propio que este corolario pedía **valió doble**: escrito para
cuidar el apagado, es el que hoy cuida la conversión. Es la mejor forma de un
test de contrato (corolario 21): fija lo que la función TIENE QUE HACER, así
que sobrevive al cambio de por qué hace falta. El canario lo confirma —
devolverle `contenido_por_cajon` hace caer nueve tests y ese es uno.

## Y un canario que dice `[0]` sobre un campo VACÍO no probó nada

*(La pregunta de la que salió este caso se borró el 18/09 — la caja sale de
la ficha. La quinta lectura del canario en cero no se mueve: es del
MECANISMO, y el campo de abajo es el ESTADO que se anotó al lado para
ilustrarlo.)*

Del 17/09, y salió de la tanda de esta misma pregunta. De doce canarios, uno
dio **0**: sacarle a la ruta la línea que devuelve la respuesta al rearmar el
formulario **no hizo caer ningún test**.

El test existía y estaba bien escrito. Lo que estaba mal era **su fixture**:
posteaba `caja_nuestra=""` —el caso que rebota *por* no contestar— así que lo
que se perdía al sacar la línea era **un vacío**. Un vacío perdido y un vacío
conservado se renderizan igual.

Es el corolario 30 exacto: *una batería de casos donde el campo va vacío no
distingue "el valor vuelve" de "la línea está en el dict"*. Y es la **quinta
lectura del canario en cero**, distinta de las cuatro que ya están escritas
(el test flojo, el canario mal puesto, el pycache viejo, la rama
inalcanzable):

> **el test ejercita el caso donde el campo que se perdió NO TENÍA VALOR.**

**Cómo se reconoce sin correr el canario**: si el campo que el cambio agrega
es el mismo que la rama de error viene a reclamar, el test de esa rama no lo
puede cuidar — por construcción llega vacío. Hace falta un test donde el
campo esté CONTESTADO y lo que rebote sea **otra cosa**.

Y de yapa, el canario de la MEDICIÓN cayó en lo mismo por otro lado: plantar
un nombre de setenta caracteres en un `<option>` **no movió el desborde**,
porque el texto de una opción no ensancha la página — el `select` lo recorta.
El canario estaba mal puesto, no la medición. Lo que sí desborda es el
RÓTULO, y con eso el número saltó de 0 a 480px. **Antes de leer un canario de
layout en cero, preguntarse si lo que se rompió puede mover ese número.**

## Y la SEXTA lectura del canario en cero: el contador solo cuenta `FAILED`

Del 18/09. Dos canarios seguidos dieron **0**, y no era ninguna de las cinco
causas escritas. El parche cortaba con `t.index(marca)` y **la marca aparecía
DOS veces** —`INSERT INTO pedidos_sucursales` está en el insert normal y en la
copia nueva—, así que el corte empezó en el primero y se llevó puesto medio
`crear_pedido`. El archivo quedó sin parsear, pytest reportó un error de
COLECCIÓN, y mi contador era `re.findall(r"^FAILED ...")`: **un error de
colección no imprime ni una línea `FAILED`**, así que el canario informó cero
caídos sobre una suite que no llegó a correr.

O sea que el cero significaba lo contrario de todas las lecturas anteriores:
no es que nada se rompiera, es que **se rompió tanto que la medición no
existió**.

**Las dos señales, y las dos cuestan una línea:**

1. **El canario imprime la COLA del resumen de pytest**, no solo su lista de
   caídos. `2687 passed` y `error during collection` se distinguen de un
   vistazo; dos listas vacías, no.
2. **Y el parche se valida con `ast.parse` antes de correr nada.** Si el
   archivo mutado no parsea, el canario no midió: eso es un canario roto y hay
   que decirlo así, no anotar un cero.

Y la causa de fondo es la de siempre en este archivo, en una herramienta:
**`str.index` de un fragmento que aparece dos veces contesta por el primero.**
Es el corolario 4 fuera de un assert — el ancla suelta que matchea al vecino,
ahora cortando código en vez de verificándolo.

### Y volvió el 21/09 con OTRO regex, que es lo que lo vuelve una familia

El contador se había arreglado a `^_{5,} (\S+) _{5,}$` —los encabezados de
falla de pytest, que son `____ test_x ____`—. **Pytest rellena esos guiones
hasta el ancho de la terminal**, así que un nombre LARGO deja **uno solo** de
cada lado, y en este repo todos los nombres son largos. Medido plantando dos
fallas, una de nombre largo y otra corto:

```
'_ test_un_nombre_bien_largo_como_los_de_este_repo_que_no_deja_lugar_a_guiones '
'__________________________________ test_corto ________________________________'

regex viejo  ^_{5,} (\S+) _{5,}$  ->  1 de 2
regex nuevo  ^_+ (\S+) _+$        ->  2 de 2
```

**El contador undercuenta exactamente los tests con nombre largo**, o sea
justo los que este proyecto escribe. Tres canarios de dieciséis salieron `[0]`
mintiendo el mismo día.

**Y lo único que lo delató fue la COLA**, que es la guarda que este archivo ya
pedía tres párrafos más arriba: `1 failed, 2953 passed` al lado de un `[0]`.
La regla estaba escrita, la cola estaba impresa, y yo leí el número. Es el
corolario 19 una vez más — una salvaguarda que existe y no se lee no sirve.

**Cómo se leen los dos juntos, que es lo que queda**: un `[0]` cuya cola diga
`N passed` a secas es un cero de verdad; uno cuya cola diga `1 failed` es el
contador mintiendo. **Si hay que elegir uno solo, la cola le gana al
contador**: el contador es código propio y la cola la escribe pytest.

Y el arreglo se verificó **plantando el caso**, no leyendo el regex: un regex
se lee bien siempre, y el ancho de la terminal no está en el regex.

### Y a esta altura el patrón es del CONTADOR, no de cada regex

Tres versiones del mismo contador fallaron por tres causas distintas —`-q` que
no imprime `FAILED`, un corte que parte el archivo, y ahora el relleno de
guiones—. **Lo que se repite no es el bug: es que el canario mide su propio
resultado con código propio**, y ese código no tiene quien lo verifique
(corolario 35: la herramienta de verificar también es código).

Lo barato, y es lo que hay que hacer siempre: **imprimir la cola SIEMPRE, no
solo cuando el conteo da cero.** Con la cola al lado, cualquier versión rota
del contador se ve en el acto y ninguna decide nada.

## Y la SÉPTIMA lectura del canario en cero: el fixture dibuja UNA sola de las dos ramas

Del 19/09. (El agrupado que produjo el caso se revirtió ese mismo día —ver el
corolario 68—. El MECANISMO no depende de él; lo que sigue es el estado que se
anotó al lado para ilustrarlo.)

El Remanente pasó a agrupar por artículo, y con eso el nombre del
artículo se dibujaba en **dos lugares distintos según el caso**: en la CABECERA
cuando había varias porciones, y en el RENGLÓN cuando había una sola (adentro
de un grupo el renglón decía solo su parte — "Suelto", "Caja Día").

Las dos necesitan `overflow-wrap`, y las dos lo tienen. El canario que se lo
saca al RENGLÓN dio **0**.

**Y no es ninguna de las seis causas escritas.** El test estaba bien, el
canario rompía exactamente lo que decía romper, el pycache estaba limpio, la
rama era alcanzable en producción y la suite corrió entera. Lo que pasaba es
que **el fixture renombraba solo al artículo con cabecera**, así que el
nombre largo no llegaba nunca al renglón: la regla existía, se aplicaba, y
el caso que la ejercita no se estaba dibujando.

**La señal, y se hace al escribir el fixture**: cuando un cambio crea DOS
FORMAS de dibujar el mismo dato —agrupado y suelto, con cabecera y sin,
primera vez y repetido— el fixture tiene que producir las dos. Si produce
una, el canario de la otra da cero y el cero se lee como "el test cubre de
más".

Es el corolario 53 corrido al fixture de una PANTALLA en vez de al de una
herramienta: allá la pregunta era *¿los casos plantados se PARECEN a las
pantallas donde lo voy a usar?*; acá es **¿el fixture produce todas las
ramas que este cambio acaba de crear?** — y la respuesta la da el canario,
no la lectura.

**Y de yapa confirmó una afirmación que yo había escrito sin medir.** El
comentario del CSS decía que el desborde *"es MÁS VIEJO que el agrupado: el
renglón ya tenía el problema"*. Con el fixture arreglado, sacarle el wrap al
renglón hace caer el test — o sea que el renglón sí desborda solo, y la
frase pasó de ser plausible a estar medida. El canario que no mordía era
también el que no podía confirmarla.

**Y esa medición es lo que decidió qué se quedaba al revertir el agrupado**:
sin ella, el `overflow-wrap` del renglón se iba con el `git revert` como una
línea más del commit, y la pantalla plana volvía a desbordar 213px con un
nombre sin espacios. Medido de nuevo con el agrupado ya afuera: el canario
que se lo saca al renglón sigue haciendo caer **1** test, y el caso cómodo
sigue en verde.

## Corolario 91: EL ANDAMIO DECIDIENDO EL RESULTADO QUE DESPUÉS SE AFIRMA

Del 19/09, y el nombre es del dueño. No es un corolario nuevo: es **la
familia** que los corolarios 9, 40, 58 y 65 venían describiendo de a uno, y
tenerla junta cambia qué se busca.

> **Un test puede pasar porque el código anda, o porque algo del andamio
> —un mock, un parche, un assert flojo— ya decidió lo que el test iba a
> afirmar. Los dos se ven igual: verde.**

Las tres formas aparecieron **en un solo día**, sobre el mismo trabajo, y las
tres las encontró ROMPER EL CÓDIGO A PROPÓSITO. Ninguna se ve leyendo el test.

### 1. La guarda MEDIDA y nunca ENCODEADA

`mover_compra_de_fecha` tenía dos guardas duras —el corte y la guía R en
origen—. Las dos se midieron contra `db/esquema_completo.sql`, las dos
salieron bien, y **ninguna quedó en la suite**. Los canarios que se las sacan
dieron **0**: no había un solo test que las mirara.

**Medir no es cubrir, y las dos se parecen muchísimo desde adentro**: en las
dos uno corre la función real, ve el resultado correcto y lo da por cerrado.
La diferencia es que una queda corriendo en cada push y la otra fue un rato
de una tarde.

Y el agravante: una guarda medida se siente MÁS cubierta que una testeada,
porque se la vio andar contra el esquema de verdad. **La suite la daba por
cubierta sin mirarla.**

**Lo accionable**: una medición contra el esquema real es lo que decide si la
guarda va; el test es lo que la mantiene. Al cerrar una medición, la pregunta
es *¿qué test cae si mañana saco esto?* — y si la respuesta es ninguno, la
medición no terminó.

### 2. El assert POR LA NEGATIVA que no distingue el motivo

`assert respuesta.status_code != 303` sobre la ruta de borrar. El canario que
le saca la puerta de Gerencia dio **0**: sin la puerta, la ruta revienta
contra la base y **un 500 tampoco es 303**.

**Un assert por la negativa pasa por CUALQUIER motivo que no sea el prohibido**
—incluido que el código se caiga antes de llegar—, así que no distingue "la
frenó la guarda" de "explotó en el camino". Y explotar es exactamente lo que
pasa cuando se saca una guarda, o sea **justo el caso que el canario planta**.

La forma sana afirma lo que SÍ tiene que pasar: que la respuesta pida la
clave. Es el corolario 30 dado vuelta —allá una batería de negativos no
distinguía una guarda que frena todo— con el mecanismo corrido al assert.

**La señal**: si el assert es un `!=`, un `not in` o un `assert not`,
preguntarse **qué OTRA cosa lo satisface**. Casi siempre hay una, y casi
siempre es un error.

### 3. El MOCK que empezó a contestar DOS preguntas

`_dependencias_con_nombres` tenía un llamador. La pantalla ganó un segundo
—"¿qué pasa si la borro?" al lado de "¿qué pasa si muevo la fecha?"— y el
test que leía `call_args` pasó a estar mirando **la otra**. Nadie tocó ese
test.

Es el corolario 58 con el mecanismo corrido: allá el mismo código le hacía
dos preguntas EN ORDEN, acá se las hacen dos llamadores distintos. En los dos
`call_args` devuelve la última y el `return_value` contesta las dos igual.

**La señal, y se hace al AGREGAR el llamador, no al leer el test**: cuando una
función gana un llamador nuevo en una pantalla que ya tenía tests, grepear los
mocks de esa función. `call_args` pasa a significar otra cosa el día que hay
dos llamadas, y no hay nada que se ponga rojo.

### Lo que las une, y por qué esto justifica lo que cuestan los canarios

En las tres **el test estaba escrito, era razonable, y afirmaba algo que su
propio andamio ya había decidido**. No hay nada mal que señalar leyéndolo: hay
que romper el código y mirar si cae.

Por eso un canario no es una prolijidad al final del trabajo: **es lo único
que distingue un test de una decoración**, y las tres veces el que se cobró
fue el que dio CERO, que es el resultado que uno tiende a explicarse como "el
test cubre de más".

**Y las tres aparecieron en un día sobre un trabajo cuidado**, no en código
viejo de nadie. La conclusión operativa es de frecuencia, no de calidad:
sobre cualquier trabajo con mocks, la tasa base de esto no es cero — así que
el canario va SIEMPRE, y el cero se investiga en vez de celebrarse.

**Y EL TERCER MIEMBRO APARECIÓ EL MISMO DÍA, una hora después**, lo que
confirma la tasa base: el aviso del precio en Editar Compra tiene seis tests,
los seis parchean `guias_r_congeladas_de_la_compra`, y **el texto de esa
consulta no lo ejercitaba nadie**. Sacarle `rc.costo_por_bulto` y sacarle el
filtro de las guías R anuladas hacían caer CERO — el corolario 65 otra vez,
en el mismo turno en que se escribió esta sección.

Los dos modos de falla eran mudos: sin el costo, el aviso nombra la guía y se
calla el número, que es lo único que hace la comparación posible; sin el
filtro, una guía R **anulada** aparece reclamando por un lote que ya no
consume. Se cierran con un test del TEXTO del SQL, calificado por alias.

### Y POR ESO EL CANARIO VA SIEMPRE: conocer la trampa no protege de pisarla

Del 19/09, y es del dueño. Es la observación que convierte a este corolario
en una práctica y no en una advertencia más, así que va pegada y no aparte.

**La sección de arriba se escribió, y una hora después se cometió lo que
describe, adentro del mismo commit.** No es que la regla estuviera vieja, ni
lejos, ni en un archivo que nadie abre: estaba recién escrita, por mí, sobre
el trabajo que estaba haciendo. **No frenó nada.** Lo agarró el canario.

**Y el intervalo llegó a CERO, que es lo que no estaba medido.** Este archivo
ya anota tres veces la misma forma —el corolario 33 lo dice del 20, el 18 de
sí mismo, y el 16/09 lo dice del nombre repetido— y las tres se leen como
descuidos de alguien que se olvidó. Acá no hubo nada que olvidar: la distancia
entre escribir la regla y romperla fue un commit. **O sea que "lo tengo
fresco" no es una protección, y ninguna cantidad de releer el archivo lo es**
— que es justo lo que el corolario 19 dice de cualquier salvaguarda que haya
que acordarse de leer.

**El caso hermano, del 17/09, y tiene la misma forma con dos mensajes de
distancia**: en el planteo del stock de cajas escribí que este sistema ya
tiene tres pantallas llamadas "Stock" y que no había que agregar una cuarta,
y dos mensajes después bauticé la pantalla nueva "Envases", que era el nombre
de una que ya existía. La advertencia la había escrito yo, ese mismo día,
sobre ese mismo trabajo.

**Lo accionable, y es una sola frase**: la protección nunca es la regla
escrita — es el CHEQUEO MECÁNICO hecho en el momento. Para el nombre, el
`grep` antes de bautizar. Para el andamio, el canario antes de dar un test
por bueno. Los dos cuestan menos de un minuto y los dos funcionan sin que
nadie se acuerde de nada, que es la única propiedad que importa.

Por eso el canario **no se saltea cuando el trabajo salió prolijo**, que es
exactamente cuando uno lo quiere saltear: los cuatro casos de este corolario
salieron de trabajos cuidados, con tests escritos a propósito, y los cuatro
los encontró romper el código.

## Corolario 86: una foto POR CANARIO deja una avería puesta cuando dos tocan el mismo archivo

Del 19/09, y es la trampa más cara del día. El script de canarios guardaba
un `.bak` **por canario**: mutar, correr, restaurar, borrar el `.bak`. Con
cuatro canarios sobre tres archivos funcionó tres veces y falló la cuarta,
porque **dos canarios tocaban la MISMA plantilla**: el `.bak` del segundo se
tomó del archivo que el primero ya había mutado.

Resultado: la tanda terminó, el árbol quedó con una avería puesta, y **la
suite entera pasó a dar dos rojos que parecían de otra cosa**.

**Por qué es peor que el canario que se mata a la mitad** (que ya está
escrito): allá uno sabe que lo mató. Acá **la tanda terminó bien**, los
números de cada canario eran correctos, y no hay ningún evento que invite a
sospechar. Lo único raro llega después y disfrazado de otro bug.

**Y la señal para reconocerlo**: los tests que caen son los del cambio que
uno acaba de hacer, y caen **con el código correcto a la vista**. Eso es
exactamente lo que el corolario 22 describe —el reflejo de arreglar el test—
con la diferencia de que acá ni el test ni el código están mal: **el archivo
no dice lo que uno escribió.**

**Lo que lo resolvió es la regla que ya estaba y hay que aplicar ANTES de
tocar nada**: mirar qué quedó ESCRITO, no el resultado de la suite. Un
`find . -name '*.bak'` delató el archivo, y un `grep` de la cosa que el
canario borraba delató cuál mitad faltaba.

**El arreglo, y es de una línea**: **UNA SOLA FOTO antes de la tanda entera**,
y restaurar desde ahí antes de CADA canario. Así no importa cuántos toquen el
mismo archivo ni en qué orden. Y el `finally` restaura desde esa misma foto,
así que matar el script tampoco deja nada.

```python
FOTO = {a: io.open(a).read() for a in ARCHIVOS}      # una vez, antes de todo
def restaurar():
    for a, c in FOTO.items(): io.open(a, "w").write(c)
```

Engancha con **"el método de restauración es el MISMO para todos los
archivos de la tanda"**: aquella regla dice no mezclar `.bak` con `git
checkout`; ésta agrega que **un `.bak` por canario ya es mezclar**, porque
cada uno fotografía un estado distinto.

### Y LA FOTO VA A DISCO: un reinicio del contenedor no corre el `finally` (20/09)

La regla de arriba dice UNA foto antes de la tanda. El 20/09 el contenedor se
reinició con la tanda corriendo, y ahí la foto —que vivía en un `dict` en
memoria— **se fue con el proceso**. El `finally` no corrió: ni un `SIGTERM`
atrapable, el proceso simplemente dejó de existir.

**Quedó puesta la mutación del canario 6**, que borraba un link de una
plantilla. Y el daño es el del corolario 86 con una vuelta peor: ahí la tanda
terminaba bien y el rastro estaba en un `.bak` suelto. **Acá no hay ningún
rastro**: sin `.bak`, sin diff sospechoso —el archivo figura `M` igual, porque
tiene trabajo sin commitear— y sin nada en `git status` que se vea raro.

**Lo que lo encontró NO fue la suite**: la suite habría caído, sí, pero el
rojo se lee como "rompí algo al escribir" y manda a arreglar el test. Lo
encontró **grepear las diez mutaciones una por una** —para cada canario, que
lo que TIENE que estar esté y lo que NO puede estar no esté— que es la regla
de siempre (*se mira qué quedó ESCRITO, no si el comando se quejó*) convertida
en un control con su denominador: `10 de 10 controladas · 1 avería puesta`.

Las dos cosas que quedan, y las dos cuestan una línea:

1. **La foto se copia a DISCO antes de la tanda**, fuera del repo, con un
   script de una línea que la devuelve. Una foto en memoria protege del
   canario que falla; no del proceso que desaparece.
2. **Después de cualquier interrupción, el control de las mutaciones se corre
   ANTES de tocar nada** — incluso antes de correr la suite. Un canario
   interrumpido es indistinguible de uno que terminó, y la única diferencia
   está en los archivos.

**Y vale para cualquier interrupción, no solo el reinicio**: matar el
proceso, cerrar la sesión, un timeout de la herramienta. La pregunta es
siempre la misma —*¿el archivo que el test leyó es el que yo escribí?*— y la
contesta el grep, no el verde.

## Corolario 82: un canario que hace caer MÁS tests de los que su avería explica está midiendo sobre un árbol ya roto

Del 18/09, y es del dueño. **Todos los corolarios del canario hasta acá son
sobre el CERO** —las cinco lecturas de "no mordió"—. Éste es el otro extremo
y no estaba escrito: **el canario que muerde de más.**

El caso. Seis canarios sobre la puerta de desmarcar, cada uno con su test.
El primero reportó **14 caídos**, y entre ellos
`test_ver_corregir_recepcion_compra_muestra_formulario_precargado`, que no
tiene nada que ver con la avería. La suite ya estaba roja: la pantalla había
ganado un colaborador y el fixture compartido no lo parcheaba, así que trece
tests se iban a la base de verdad. El canario no rompió nada de eso — lo
heredó.

**Y el rojo no es la señal, que es lo que hay que entender.** Un canario que
muerde SALE en rojo: eso es exactamente lo que se fue a buscar, y se lee como
éxito. Lo único que distinguía "mordió" de "mordió y encima el árbol estaba
roto" era **el NÚMERO**, y el número solo dice algo si uno sabe de antemano
cuánto tenía que dar.

> **Antes de leer un canario, contar.** Una avería de una línea hace caer los
> tests que miran esa línea — casi siempre uno, a veces dos. Si caen catorce,
> lo que hay que revisar no es el canario: es el árbol.

### Por qué el reflejo va para el otro lado

Con un canario en cero uno ya sabe que tiene que sospechar: está escrito
cinco veces en este archivo. Con un canario que muerde **no hay sospecha que
disparar**, porque el resultado es el que se esperaba. Es el mismo mecanismo
del corolario 19 —la salvaguarda funcionó, el dato estaba a la vista, y no se
leyó— aplicado al momento en que uno está más conforme.

Y es la misma familia del corolario 45 (una medición que devuelve un total
trae el total esperado al lado): **`14 caídos` sin el `1 esperado` al lado no
se puede leer.** El canario que dice *"cayeron 14"* y el que dice *"cayeron
14 y esperaba 1"* son el mismo comando con una columna más.

### Lo accionable, y cuesta una corrida

**La suite entera en VERDE antes de lanzar la tanda**, y el número anotado.
Es la misma regla que el `.bak` y el primer plano: el canario mide una
diferencia, así que necesita que el punto de partida esté definido. Un
canario lanzado sobre un árbol rojo no mide nada — igual que uno lanzado en
segundo plano mientras otra cosa toca los archivos.

Engancha con **"un canario que MUTA archivos no se corre en segundo plano"**
por el mismo lado: las dos son sobre el ESTADO DE PARTIDA. Allá lo que lo
contamina es otro proceso; acá, un rojo que ya estaba. Y las dos se ven igual
desde adentro del resultado.

## Corolario 95: un test que ancla en HOY no puede fallar el día que su fecha fija ES hoy

Del 22/09, y es el **corolario 92 mordiendo adentro del test escrito para
verificar el ancla del promedio**.

El test afirmaba que editar una carga **no mueve** `promedio_anterior_a`. La
constante era `HOY = date(2026, 9, 22)`, y `_hoy_argentina()`, corrido a las
02:21 UTC, devolvía **22/09** en Argentina. O sea que el valor conservado y el
valor que el bug habría escrito **eran el mismo número**, y el canario que
hacía que el `ON CONFLICT` pisara el ancla salió en **cero**.

**El test estaba bien escrito, afirmaba lo correcto, y no podía fallar.** Es
la misma forma que el umbral mágico del 92: el resultado no describía la
función, describía **qué día era cuando se corrió**. Y la parte fea del
reparto es la de siempre: pasa acá y también habría pasado en el runner
durante 24 horas, y después habría empezado a fallar solo.

**El arreglo es una fecha que NO PUEDE ser hoy**: `CARGADA_EL = date(2026, 3,
5)`. Con eso, conservar y pisar dan números distintos siempre, y el canario
muerde.

**La señal, y se hace al escribir la constante**: si el test compara un valor
guardado contra lo que devolvería el reloj, preguntarse **qué pasa el día que
los dos coincidan**. Si la respuesta es "el test pasa igual", la fecha del
fixture tiene que estar lejos del presente a propósito — y lejos quiere decir
en otro mes, no ayer.

## Corolario 96: un helper que devuelve sus mocks POR POSICIÓN los entrega cambiados el día que un nombre ya estaba

Del 22/09, y es el corolario 91 en el andamio compartido de un archivo de
tests.

`_entrar` abre un stack de parches y devuelve la lista de mocks para que cada
test afirme sobre el que le interesa. Los tests leían `abiertos[-1]`
—"el último que pedí"— y eso **dejó de ser cierto** cuando uno de los parches
que el test pasaba ya estaba en el diccionario base: `dict.update` **conserva
la posición de una clave que ya existía** en vez de moverla al final. Así que
`abiertos[-1]` devolvía `carga_de_compra` y el test afirmaba sobre el mock
equivocado.

**Y no falla ruidosamente**: un mock es un mock, `.return_value` acepta
cualquier cosa, y el assert pasa o falla por razones que no tienen nada que
ver con lo que el test dice mirar.

**El arreglo es devolver un diccionario con la clave del parche**
(`patch.attribute`), y leer por nombre. Es exactamente el arreglo del lector
por índice de `_SQL_STOCK_DE_ENVASES` (17/09): **las posiciones no se
mantienen solas, y el que las lee no nombra nada**, así que ningún `grep`
encuentra a los que quedaron desfasados.

**La regla corta, que ya vale tres veces en este repo**: un helper compartido
que devuelve una TUPLA o una LISTA de cosas heterogéneas —columnas de una
consulta, mocks de un stack, valores de un `side_effect`— se lee por nombre o
se rompe en silencio. Una lista está bien cuando todos sus elementos son la
misma cosa; acá nunca lo son.

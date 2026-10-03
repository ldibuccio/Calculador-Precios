# Corolarios: mediciones, ceros y denominadores

Movido TAL CUAL desde CLAUDE.md el 03/10 (sin reescribir). Las reglas
vigentes, en corto, están en CLAUDE.md.

## Corolario 93: una reducción cuya CLAVE es más gruesa que el grano de la consulta no falla — elige una fila al azar

Del 22/09, y lo encontró un canario en CERO que parecía la enésima lectura de
un test flojo.

`_SQL_CAJAS_DEL_DEPOSITO_PERDIDAS` agrupa por `(destino, articulo_id)`.
`cajas_de_pases_por_articulo` armaba su diccionario **por comprensión y con la
clave solo del artículo**, filtrando `destino == "segunda"`. (Esa función se
llama `cajas_perdidas_del_deposito_por_articulo` desde unas horas después, y
devuelve el grano ENTERO: el nombre se movió con el alcance el día que el
dueño cerró que la caja de la merma también entra. El corolario no se mueve —
lo que lo produjo fue la clave más gruesa que el `GROUP BY`, y hoy ya no lo
es.) Con el filtro
puesto la clave es única y el número es correcto. Sin él —que es justo lo que
el canario planta— las dos filas del mismo artículo **colisionan, y una pisa a
la otra**:

```
filas CRUDAS (3):  ('merma', 1, 2, 100) · ('segunda', 1, 3, 150) · ('segunda', 2, 10, 500)
con el filtro   :  {1: (3.0, 150.0), 2: (10.0, 500.0)}
```

**Y cuál gana lo decide el orden en que Postgres las devuelva, que no está
fijado por ningún `ORDER BY`.** Acá `segunda` venía última, así que sacar el
filtro daba **exactamente el mismo resultado** y el canario no podía morder.
Si el plan las devolviera al revés, la misma función entregaría `2 cajas /
$100` —el número de la MERMA— en silencio.

**Por qué es peor que un test flojo**: el test estaba bien escrito y afirmaba
lo correcto (`cajas_perdidas == 3.0`). Lo que no podía ver es que la avería
que se le plantaba fuera **un no-op por casualidad**. Es la octava lectura del
canario en cero, y no es ninguna de las siete: no es el test, ni el canario,
ni el pycache, ni una rama muerta, ni un campo vacío, ni el contador, ni el
fixture que dibuja una sola rama — es que **romper el código no cambió nada
esta vez, y podría cambiarlo la próxima.**

**La señal, y se hace al escribir el `dict(...)` o la comprensión**: si la
consulta tiene `GROUP BY a, b` y la reducción indexa por `b` solo, la clave
**no es única** y hay que mirar qué la desempata. Si lo que la desempata es un
filtro, la reducción depende de que ese filtro no se mueva nunca — y el día que
alguien lo toque no va a fallar: va a elegir una fila.

**El arreglo no es agregar un `ORDER BY`** —eso fija cuál gana, que sigue
siendo una de las dos— sino **acumular**: con `+=`, sacar el filtro SUMA, que
es la única lectura honesta de "sin filtro", y el canario muerde. De yapa, el
código dice en su forma que la clave no era única.

**Y buscar la otra copia fue obligatorio**: la misma consulta la consume
`perdidas_por_periodo`, que indexa por `(destino, articulo_id)` —el grano
COMPLETO— así que no tiene el problema. La revisé antes de tocar nada, y eso
es lo que distingue arreglar una copia de arreglar la que estaba mal.

## El dato de uso decide qué MEJORAR, no qué SACAR

Del 11/09, y es un error de criterio mío, no del código.

Midiendo el rechazo para dimensionar el cuarto destino salió que
`a_reproceso` —"vuelve a cajón grande"— estaba en **0 sobre 15 casos**. Y
propuse: *"si sigue en cero en un mes, es una opción que solo sirve para
equivocarse"*.

**Está mal, y la corrección es de Lionel: las opciones que él define son
casos reales del negocio, aunque pasen una vez al año.** Quince casos en
dieciséis días **no tienen ningún poder** para hablar de algo que pasa una
vez al año — eso no es una cuestión de criterio, es aritmética: en dos
semanas, un caso anual aparece con probabilidad de centésimas. El cero
medido era exactamente lo que se esperaría si la opción fuera necesaria.

### La distinción, que es lo único que evita repetirlo

Las dos cosas que comparé se veían iguales —un cero en una medición— y no
lo son:

| de dónde salió | qué dice el cero |
|---|---|
| **El dueño la puso porque conoce el caso** | **nada.** Se queda. |
| **El código abrió la puerta y nadie la pidió** | **vale**, y más si otra pantalla del mismo sistema no la permite |

- `a_reproceso` en 0 sobre 15: **la puso él.** Se queda.
- El selector que ofrecía fichas de OTRO cliente, 0 sobre 198: **lo abrió el
  código**, nadie lo pidió, y la pantalla de armar nunca lo permitió. Se
  cerró, y estuvo bien cerrarlo.

**Lo que los distingue no está en el número.** Los dos ceros son igual de
prolijos. Lo que cambia es el ORIGEN, y eso hay que ir a preguntarlo: *¿esta
opción la pidió alguien, o apareció sola?*

### La regla

**No proponer dar de baja opciones funcionales por frecuencia medida.** El
dato de uso sirve para decidir **qué mejorar** —dónde poner el esfuerzo, qué
pantalla ordenar, qué aviso agregar— no **qué sacar**.

Sacar algo necesita otra evidencia: que nadie lo haya pedido, que otra parte
del sistema demuestre que el caso no puede ocurrir, o que el dueño diga que
ya no va. Ninguna de las tres es un conteo.

### Con qué engancha

Es **el corolario 29 dado vuelta**. Allá construí sobre un requisito que
nadie enunció; acá propuse destruir uno que alguien sí había enunciado. Las
dos fallas son la misma: **perder de vista quién pidió qué.** Y las dos se
arreglan con la misma pregunta, hecha antes y no después — *¿de quién salió
esto?*

Y con la sección del campo sin consecuencia, por contraste: allá un campo
vacío era la respuesta correcta al incentivo, y el arreglo estaba del lado
del sistema. **Acá el vacío no es un síntoma de nada**: es una opción
esperando su caso.

## Medir "parecido" solo sirve cuando lo parecido es raro

Del 11/09. Para ver si dos proveedores eran el mismo puesto mal tipeado
escribí tres heurísticas. Dos miraban el `codigo_puesto`: pares que difieren
en **una** posición (N07P41/N07P51) y pares **transpuestos** (N07P41/N07P14).
La idea: un código mal tipeado se parece al bueno.

Dieron **49 pares en Frutamax y 39 en Palmala**, y **todos falsos
positivos**:

```
N09P37/N09P36  kleppe | almana s.r.l.
N07P41/N08P41  herederos n7 | don ismael
```

Nombres sin ninguna relación, con códigos vecinos. **Los puestos del mercado
son contiguos por diseño**: N09P36 y N09P37 están uno al lado del otro
porque así está armado el mercado. La heurística no medía parecido — medía
**vecindad**, y acá la vecindad es la norma, no la excepción.

El tercer criterio, el único que apuntaba a la pregunta —dos NOMBRES que se
igualan al plegar y colapsar letras repetidas— dio **0 en las dos bases**. Esa
era la respuesta: no hay fusiones para hacer.

**Y ese 0 no cerraba la pregunta, medido el 27/09**: FRUTAMAX (N09P39) y
FRUTAMAX S.R.L. (N09P41) eran el mismo proveedor cargado dos veces. Ese
plegado no sacaba la forma societaria, así que esos dos nombres no se
igualaban. No se sabe si ya estaban los dos el 11/09. El plegado que usa hoy
el alta a mano (`core/nombres_de_proveedor.py`) saca además formas societarias
y palabras de relleno ("SRL", "PRODUCTOS", "HNOS"…) como palabra entera, y
avisa también cuando un nombre contiene al otro. Ver **"UN PROVEEDOR, VARIOS PUESTOS"**.

### La regla

**Antes de medir parecido, preguntarse qué GENERA los valores.**

- Si salen de un **sistema de coordenadas** —códigos de puesto, fechas,
  posiciones, ids correlativos— la cercanía es **estructural** y no dice
  nada. Dos valores contiguos son vecinos legítimos, no un error de tipeo.
- Si salen de **escribir a mano** —un nombre, un alias, un código que alguien
  teclea— la cercanía **sí es evidencia**, porque escribir dos cosas casi
  iguales sin querer es raro.

Es la familia del corolario 20: busqué la FORMA que esperaba (un typo se
parece al original) en vez del HECHO (esos códigos son una grilla). Y como
allá, el `grep` del concepto lo habría dicho: el comentario de la columna
dice "codigo_puesto (ej. N07P41)", y un ejemplo con formato de coordenada
es la pista de que eso es una grilla.

### La señal barata, y estaba antes de leer un solo par

**49 pares sobre 43 proveedores**, y eso ya la condenaba sin abrir `cuales`.
No es una observación de este caso: es un control que vale para cualquier
búsqueda de anomalías, y por eso está escrito una sola vez, abajo, en
**"Más hallazgos que población condena la heurística sin mirar un caso"**.

### Qué se hizo con la consulta

No se borró entera: se le **sacaron los dos criterios del código** y quedó
el de nombres, con el resultado y el porqué anotados. Dejarlos corribles
habría sido peor que no tenerlos —la próxima vez que alguien los corra no se
va a acordar de que eran ruido—, y borrar todo habría tirado el único
criterio que sí contesta la pregunta. Verificada después con los vecinos
REALES cargados (Kleppe/Almana en N09P37/N09P36): ahora ve solo el duplicado.

## Más hallazgos que población condena la heurística sin mirar un caso

Del 11/09. Salió del caso de los proveedores parecidos —el de acá arriba—
pero no es de ese caso: vale para **cualquier búsqueda de anomalías**.
Duplicados, ofensores, desvíos, outliers, avisos, "parecidos", descuadres.

La heurística de códigos vecinos dio **49 pares sobre 43 proveedores**. Ese
cociente ya la condenaba, y estaba disponible **antes de leer un solo par**.
Los 49 resultaron todos falsos positivos, y para saberlo no hacía falta
abrir ninguno.

**Por qué funciona, y es aritmética, no olfato**: una anomalía es por
definición lo raro. Si la cuenta de hallazgos es del mismo orden que la
población, lo que se está contando **es la norma**. Y ninguna lectura de
casos puede salvar eso: aunque algunos de los 49 fueran duplicados de
verdad, el criterio igual está midiendo otra cosa — acá, cómo está armado
el mercado.

**CONDENA, NUNCA ABSUELVE**, y ésta es la mitad que hay que escribir porque
la tentación es leerla dada vuelta. **Pocos hallazgos no dicen que la
heurística sirva**: pueden ser pocos porque el criterio no sabe ver el caso,
que es exactamente el corolario 36. El cociente decide en una sola
dirección, igual que el techo de la compra en caja nuestra: grande cierra la
discusión, chico no prueba nada.

**La forma operativa, y cuesta una columna**: toda consulta que busque
anomalías devuelve **la población al lado del conteo, en la misma fila**.
`pares 49 · proveedores 43` se lee solo; `pares 49` necesita que alguien se
acuerde de ir a buscar el denominador, y nadie se acuerda —es el corolario
19, la salvaguarda que existe y no se lee—. Es el testigo del corolario 24
con otro trabajo: allá dice si la base está viva, acá contra cuánto se está
contando.

**Cuándo se mira**: antes de abrir la lista de casos, siempre. Es el único
control de esta familia que se paga con una división y se cobra antes de
gastar media hora descartando falsos positivos de a uno.

## Corolario 41: una lectura calculada a partir de lo que la pantalla acaba de calcular puede ser la vuelta completa

Del 12/09. La pantalla de Analizar Artículo tiene un renglón que contesta
*"¿hasta cuánto podés pagar el cajón?"*. Se calculaba así: con la
rentabilidad que la pantalla acaba de calcular, `costo_objetivo_multi_
concepto` devuelve el costo máximo por unidad, y ese costo por los kilos del
bulto da el importe máximo del cajón.

**Devuelve el importe que entró. Siempre, hasta el último centavo.** Las
tres funciones del motor son inversas exactas entre sí: el precio y el costo
produjeron esa utilidad, así que preguntarle a la utilidad por el costo
devuelve el costo. La vuelta es completa y **está garantizada por diseño**,
no por casualidad de los números.

Y **un renglón que repite lo que entró parece una lectura y no lo es.** Ahí
está el daño: no dice nada, pero no se ve vacío — se ve como un número
calculado, con su etiqueta y su formato, al lado de otros que sí lo son.

**Solo se vio corriéndolo con números.** Leyendo el código se veía perfecto:
tres llamadas correctas al motor, con los argumentos correctos, cada una
haciendo lo que su docstring promete. No hay nada mal escrito que señalar.

**La señal, y es la del dueño**: si una lectura se calcula a partir de algo
que la MISMA pantalla acaba de calcular, verificar que no sea la vuelta
completa. Con funciones inversas exactas, la vuelta completa está
garantizada por diseño.

**El arreglo es cambiar contra qué se pregunta**, no cómo se calcula: el
renglón va contra la **utilidad objetivo del CLIENTE** (`tasas["utilidad"]`),
que es un dato de afuera y no salió de esta pantalla. Ahí sí contesta algo —
16 kilos a $16.160 entra contra un objetivo de $16.000; 14 kilos a $14.140
no.

**Con qué engancha**: es pariente del corolario 9 —el test que parchea la
función que verifica— pero en la pantalla en vez de en el test. Allá el
andamio decide el resultado que después se afirma; acá **la pantalla se
pregunta a sí misma y se contesta sola**. En los dos casos el círculo está
adentro y no se ve desde afuera; en los dos, lo único que lo muestra es
correrlo con un número que se pueda reconocer.

## Corolario 45: una medición que devuelve un TOTAL trae el total esperado al lado

Del 12/09, y es la tercera vez en la semana que una medición mide otra cosa
y devuelve un número plausible. Las tres veces el número se veía bien solo.

El caso: para probar si la suite dependía del orden, barajé los 2268 ids y se
los pasé a pytest con `xargs`. `xargs` **parte la lista** cuando no entra en
la línea de comandos, así que corrió pytest cuatro veces —una por pedazo— y
lo que leí fue el resumen del último: **`649 passed`**.

Lo único que lo delató fue que **649 no es 2268**. Con una suite de 700 tests
el número habría pasado sin que nadie lo mirara, y yo habría escrito "el
orden no importa" apoyado en una corrida que nunca existió.

**La regla, y cuesta una columna**: toda medición cuyo resultado sea un total
—filas, tests, bultos, pesos, casos— **imprime al lado el total que tenía que
dar**. No un comentario en otro lado: en la misma línea, donde se lee el
número.

    2268 de 2268 tests            <- se lee solo
    649 passed                    <- necesita que alguien se acuerde del 2268

Es exactamente la forma operativa de **"más hallazgos que población condena
la heurística"**, aplicada al otro lado del cociente: allá el denominador
dice contra cuánto se está contando; **acá dice si se contó todo.** Las dos
son la misma cosa —un número solo no se puede leer— y las dos se pagan con
una columna más.

Y engancha con el testigo del corolario 24 por la misma razón: el testigo
dice si la base está viva, la población contra cuánto se cuenta, y el total
esperado si la medición llegó hasta el final. **Los tres existen porque un
número sin su referencia al lado obliga a que alguien se acuerde, y nadie se
acuerda** (corolario 19: la salvaguarda que existe y no se lee).

## Corolario 47: un cero que NO PUEDE dar distinto de cero no es una medición

Del 12/09. Midiendo el desborde horizontal de cuatro pantallas a 390px, el
número daba **0 con el arreglo puesto y 0 sin él**. No era que las pantallas
estuvieran bien: era que el número elegido no podía dar otra cosa.

`.tabla-scroll { overflow-x: auto }` **se come el desborde de la página**: la
tabla se sale de su caja, la caja la absorbe con un scroll interno, y
`document.documentElement.scrollWidth` nunca crece. El operario arrastra la
tabla de costado —"Estado", "Eliminar" y "Utilidad" no se ven nunca— y la
medición dice cero, verdadero, todos los días.

**Lo que hay que medir es el sobrante de la tabla CONTRA SU CAJA**
(`tabla.scrollWidth − caja.clientWidth`), que es lo que la persona sufre. Con
eso los números aparecieron: 173, 138, 159, 127, 98, 85 px — y los dos
primeros coincidían EXACTO con los que el dueño había medido por su cuenta,
que fue la confirmación de que recién ahí estábamos midiendo lo mismo.

### Lo único que lo agarró, y es la parte accionable

**No fue leer el código: fue el canario.** Romper el arreglo a propósito y
mirar si el número SE MUEVE. Un cero que no se mueve al romper lo que lo
produce no está informando nada — es un cero de construcción.

Leído, el resultado se veía perfecto: la medición estaba bien escrita,
apuntaba a la pantalla correcta, y devolvía el número que uno esperaría de
una pantalla sana. No hay nada mal que señalar. Por eso la regla no es
"revisá la medición" —eso no se puede hacer mirándola— sino:

> **Antes de creerle a un cero, romper a propósito lo que lo hace cero y
> exigir que deje de serlo.**

Es el canario del corolario 12 aplicado al OTRO lado. Allá se rompe el
recorte de una consulta para ver si el piso está puesto; acá se rompe el
ARREGLO para ver si la medición lo ve. Y es el hermano del 36: allá el cero
es falso porque el `where` no sabe reconocer el caso, acá porque el número
no puede crecer aunque el caso esté.

### Dos formas distintas del mismo error EN LA MISMA TANDA

Y eso es lo que dice que no es raro:

1. **El contenedor se comía el desborde** — el caso de arriba.
2. **Las tablas estaban ESCONDIDAS.** En Cargar Precios el cuadro vive
   adentro de un panel que arranca cerrado. Medirlo sin abrirlo daba
   `0px · OCULTA`: cuatro tablas de 0 píxeles, porque no estaban en
   pantalla. Abriendo el panel: 169, 139, 68, 98.

Las dos veces el número era verdadero, era cero, y era incapaz de ser otra
cosa. Por caminos completamente distintos —uno de CSS, otro de estado de la
pantalla— en la misma media hora.

**La forma general, que es más ancha que el CSS**: cualquier medición sobre
"lo que está a la vista" puede estar midiendo sobre lo que NO está — porque
algo lo contiene, porque está cerrado, porque está filtrado, porque todavía
no se cargó. Y no se nota, porque lo que devuelve es el número que uno
quería ver.

Engancha con **"esconder un contenedor esconde todo lo que vive adentro"**
por el otro extremo: allá el `display: none` se llevaba puesta una función y
el desborde medía 0 igual; acá el cero era del propio arreglo. En los dos, la
frase que cierra es la misma — *nada en la medición que uno eligió puede
delatar algo que quedó afuera de esa medición*.

## Corolario 52: una simulación de layout tiene que usar los TAMAÑOS MÍNIMOS REALES de lo que se toca

Del 12/09, y es de la familia del fixture que no se parece a producción, pero
sobre PÍXELES en vez de sobre datos.

Para decidir si convenía meter los cinco botones de Buscar Compras en un
menú, se simuló el después en el navegador: reemplazar el bloque de acciones
por un botón y medir el alto de la fila. Dio **1,1 filas más por pantalla**,
y con ese número se tomó la decisión.

**Lo construido dio 0,6.** La primera versión, de hecho, midió **196px por
fila contra los 187 de antes: el menú salía PEOR.**

La diferencia es una sola cosa: **el botón de la simulación era chico.** Un
`summary` de 44px —el mínimo para tocarlo con el pulgar, que es la regla
mobile-first de este archivo— cuesta casi lo mismo que las cinco pastillas
que viene a reemplazar. La simulación midió una pantalla que no se puede
usar.

**La regla**: toda simulación de layout se hace con los tamaños que el
elemento va a tener DE VERDAD — 44px de alto lo tocable, el `line-height`
real del texto, el padding real del contenedor. Si no, lo que se mide es una
pantalla imaginaria que nadie va a poder usar, y el número decide igual.

**Cómo se reconoce**: si la simulación se escribe rápido —`innerHTML = '<button>…'`—
ahí está el riesgo. El atajo que la hace rápida es justamente el que le saca
las restricciones. La versión honesta es más larga porque tiene que traer el
CSS del componente real.

Y engancha con el corolario 47 por el lado que le falta: allá el cero no
podía moverse, acá el número **sí se movía y medía otra cosa**. Los dos se
leen como una medición buena.

### La otra mitad, y es peor: el NÚMERO MEJORABA Y LA PANTALLA EMPEORABA

Construyendo el menú, dos intentos bajaron el alto de la fila **rompiendo el
texto**:

- Meter el importe en la fila del botón: la columna 1 de la grilla mide
  1.35rem —es la del checkbox— así que **"SIN PRECIO" partía en dos**.
- Pegar los indicadores de foto a la fecha: fecha y cantidad comparten fila,
  así que **"41 cajones × 16u" partía en dos**.

Las dos veces el alto promedio bajaba y el número decía que iba mejorando.
**Las dos se vieron en la CAPTURA, no en el número.**

Por eso, de acá en adelante, **toda medición de layout usa
`scripts/medir_layout.py`**, que devuelve los números juntos: alto,
QUEBRADAS, desborde y —desde el 15/09— SOLAPES. Ya no es un snippet para copiar — está en el repo, con
sus tests, y su docstring cuenta por qué existe.

```python
from scripts.medir_layout import medir_sync, imprimir
imprimir("como está hoy", medir_sync(html, ancho=390))
```

**El alto solo nunca alcanzó**, y la lista de quebradas es lo único que
distingue "entra mejor" de "entra porque se rompió".

**Y son DOS fallas distintas, con un número cada una.** Lo encontró el propio
fixture del test: la primera versión plantaba una palabra de sesenta X para
simular un quiebre y **no detectaba nada**, porque una palabra que no se puede
partir NO envuelve — se desborda. La celda queda de una línea y se sale por el
costado. Un detector de quiebre solo la habría dado por buena; por eso
`desborde` viaja en la misma medición. El caso plantado tenía que plantarse
bien, que es el corolario 36 mordiendo adentro del test escrito para aplicarlo.

Es el testigo del corolario 24 en otra unidad: **un número solo no se puede
leer**, y el alto de una fila sin el quiebre al lado miente exactamente
cuando el diseño empeora.

### Y lo que el detector decidió el mismo día: la compactación NO va

Con el detector puesto se midió la tercera pieza —fusionar las líneas de la
tarjeta— antes de escribirla:

| | alto | filas | quebradas |
|---|---|---|---|
| como quedó | 164,2px | 5,1 | ninguna |
| compactada, nombres del largo real | 134,9px | **6,3** | "40 cajones × 16k" en 8 de 12 |
| compactada, nombres largos | **168,2px** | 5,0 | casi todas |

O sea: **gana 1,2 filas rompiendo texto, y con nombres largos es PEOR que
hoy.** Una variante conservadora —mover solo el importe— tampoco: 142,7px con
nombres cortos y **177,3px con largos**, partiendo el título del artículo.

La conclusión no es "compactar está mal": es que **el largo de los nombres no
lo controlamos**, y un diseño que solo entra con los nombres cortos de hoy es
un diseño que se rompe el día que alguien carga un proveedor con nombre
largo. El de hoy no se rompe con ninguno de los dos.

**Y la premisa del pedido estaba mal, que es lo que más conviene anotar**: se
pidió compactar "conservando los rótulos" y **esta pantalla no tiene rótulos
en celular** — es una decisión tomada y escrita en su propio CSS (*"se miró
celda por celda y los contenidos se identifican solos: la fecha parece fecha,
`20 cajones × 16k` es obvio, el importe lleva $ o dice SIN PRECIO"*). Los
rótulos en mayúsculas que se recordaban son los de OTRA pantalla, la de
Alertas, que sí usa `data-rotulo`.

Es el corolario 20 en su forma barata: **antes de construir para conservar
algo, verificar que ese algo exista.** Un `grep data-rotulo` de un segundo, y
la mitad del requisito se cae.

## Corolario 53: un hallazgo que NO PUEDE ser cero tampoco informa nada

Del 12/09, y es **el corolario 47 dado vuelta**. Los dos son la misma falla
en espejo, y conviene leerlos juntos:

| | qué pasa | cómo se ve |
|---|---|---|
| **Corolario 47** | el número **no puede dar distinto de cero** | "acá no hay problema" |
| **Éste** | el número **no puede dar cero** | "acá está lleno de problemas" |

**Salió de la herramienta, no del código.** El detector de quiebre de
`scripts/medir_layout.py` compara el alto de una celda contra su
`line-height` por una tolerancia. Con `1.6` funciona; con **`1.0` TODA celda
daría quebrada**, porque el padding y el `line-height` redondeado empujan
unos píxeles sin que haya una segunda línea.

Y ahí está lo peligroso, dicho por el dueño: **un detector que marca todo se
ve igual de trabajador que uno que funciona.** Devuelve listas largas, los
informes salen llenos, y nadie sospecha de una herramienta que "encuentra
mucho". El de corolario 47 tranquiliza; éste da la sensación contraria —de
rigor— y las dos sensaciones son falsas por el mismo motivo: **el número no
depende de lo que se está midiendo.**

### La regla, y vale para cualquier diagnóstico

**Antes de creerle a un detector, verificar que pueda dar las DOS
respuestas.** No alcanza con el caso que tiene que encontrar: hace falta
también el que NO tiene que encontrar, y los dos plantados a propósito.

Un test que solo prueba el caso positivo lo pasa igual un detector que marca
todo. Un test que solo prueba el negativo lo pasa igual uno que no marca
nada. **Los dos juntos son lo único que lo separa de una herramienta rota**,
y por eso el test del detector tiene la pareja completa —la celda que
envuelve seguro y la página donde no envuelve ninguna— además del canario que
baja la tolerancia a 1.0.

Vale para todo lo que busque algo: una alerta, una consulta de ofensores, un
validador, una regla de lint, un umbral. Es la forma CONSTRUCTIVA de lo que
**"más hallazgos que población condena la heurística"** dice desde el campo:
aquélla mira el resultado sobre datos reales y condena; ésta se hace antes,
sobre casos plantados, y decide si la herramienta sirve.

### Un test de UMBRAL lleva el caso que el umbral VECINO clasifica distinto

Del 18/09, y es del dueño. El corte de los formatos quedó en 25% y sus tests
fijaban tres cosas: que Batata (50%) y Mango (233%) se parten, que Lima y
Pepino (17-19%) no, y que la constante vale 0,25.

**El canario que la afloja a 40% no hacía caer la regla**, solo la aritmética
—`assert 0.37 > CORTE_DE_RACIMO`— y el test que compara la constante contra
la consulta. Porque los dos casos escritos como PARTICIÓN saltan tanto que se
parten igual con 40: el 50% y el 233% pasan cualquier umbral razonable.

El caso que condena al 40% es el **Cherry de Frutamax, que salta 37%** — o
sea el más chico de los cinco que se parten, y justamente el que motivó todo.
Estaba escrito como comparación de números y no como partición.

> **Un test de umbral que solo tiene casos cómodos verifica la aritmética, no
> el umbral.** Hace falta el caso que cae ENTRE este umbral y el vecino: el
> que este corte clasifica de una forma y el de al lado de la otra.

Se reconoce sin canario: si todos los casos del test están lejos del corte,
mover el corte no rompe nada. La pregunta es *¿cuál de mis casos cambia de
lado si muevo el umbral un escalón?* — y si la respuesta es "ninguno", el
número está suelto y alguien lo va a redondear.

Es el corolario 53 corrido al umbral: allá un detector tiene que poder dar
las dos respuestas, acá **el test tiene que tener un caso de cada lado de la
raya, y pegado a la raya.** Los cómodos prueban que el detector detecta; el
de al lado del corte es el único que prueba dónde está el corte.

### El límite conocido de este detector, escrito antes de que alguien le crea

Y es el 47 otra vez, adentro de la herramienta que salió del 47:

**El `desborde` que devuelve `medir` es de la PÁGINA.** En una pantalla con
un contenedor `overflow-x: auto` ese número **da 0 aunque la tabla se salga**
— el contenedor se lo come. Es exactamente lo que pasó con las cuatro
pantallas de Cargar Precios y Buscar Compras el 12/09.

El módulo **no lo adivina**: hay que mirar si la pantalla tiene alguno y, si
lo tiene, medir la tabla contra su caja (`tabla.scrollWidth −
caja.clientWidth`). Está en el docstring de `medir`, y se repite acá porque
el que va a creerle a ese cero es el que leyó este archivo y no el módulo.

### El segundo límite, y estuvo DOS DÍAS sin que nadie lo viera (14/09)

El detector miraba `fila.querySelectorAll("td, th")`. En una pantalla de
**tarjetas** —que en celular son la mayoría de este proyecto— eso no
devuelve nada, así que `quebradas` salía **0 sin haber inspeccionado una
sola celda**. El cero del corolario 47, adentro de la herramienta escrita
para el corolario 47, escrito el mismo día que el 53.

Se destapó midiendo Precios por Período: plantado un nombre de ficha que no
entra en 390px, el alto de la tarjeta subió **de 69,8 a 123,8px** —envolvió,
no hay otra forma de que suba— y `quebradas` siguió en **0**. El alto y el
detector decían cosas incompatibles en la misma línea, y sin el alto al lado
no había nada que se viera raro.

**Y la parte que corrige lo que el 53 dice de sí mismo**: el 53 afirma que
el par de casos plantados —el que tiene que encontrar y el que no— es *"lo
único que lo separa de una herramienta rota"*. El par estaba puesto, los dos
pasaban, y la herramienta estaba ciega en la mitad de las pantallas. **Los
dos casos del par eran TABLAS.** Un detector puede ser correcto para todo lo
que sus casos plantados saben expresar y no ver nada afuera de eso.

O sea, dicho como corresponde: **un par de casos que no se parecen a donde
la herramienta se va a usar no prueba nada.** El par es necesario y **no**
suficiente, y lo que le faltaba es una pregunta más, que se hace en el
momento de escribir el test: **¿los casos plantados se PARECEN a las
pantallas donde lo voy a usar?** Si todas las pruebas de una herramienta
comparten una forma —tabla, un solo cliente, un archivo chico—, lo que está
probado es esa forma.

**Lo que lo deja ver para siempre no es el arreglo: es el DENOMINADOR.**
`medir` devuelve ahora `celdas`, e `imprimir` escribe `quebradas: 0 de 160
celdas` — y `SIN CELDAS QUE MIRAR` cuando no miró ninguna. Es el corolario
45 (una medición que devuelve un total trae al lado el total esperado)
aplicado a la herramienta de medir: sin el denominador, *"ninguna envolvió"*
y *"no se miró ninguna"* se imprimen **exactamente igual** y significan lo
contrario.

**Y de yapa, el detector marcaba lo que estaba bien**: un botón de 44px
—el mínimo para tocarlo con el pulgar, que es regla de este proyecto— mide
el doble que su `line-height` sin haber envuelto nada, así que la medición
de página entera salía llena de "quebradas" que eran botones. Comparar
descontando el relleno lo arregla, y es el 53 al pie de la letra: un
detector que marca todo se ve igual de trabajador que uno que funciona.

### Y el CUARTO no es del detector: es medir la pantalla EQUIVOCADA (15/09)

Midiendo el alta de Proveedores a 390px salió `desborde 0px · solapes: 0 de
20 pares`. Prolijo, plausible, y **de otra página**: `/compras` está detrás de
una puerta, y el script corrido fuera de pytest no tenía la cookie — así que
lo que se midió fue la pantalla de "Falta la clave de Gerencia" (503) y
después la del 401.

**Ninguno de los tres números del detector puede delatarlo.** El desborde y
los solapes de la pantalla de la clave son legítimamente cero: es una tarjeta
con dos párrafos. El `20 pares` incluso suena a una pantalla con contenido.

Lo que lo agarró fue pedir otra cosa al lado: **el status y un conteo de lo
que esa pantalla TIENE que tener.** `GET 200 · renglones 6` no lo puede dar la
página de la clave.

Por eso, de acá en adelante, **toda medición de layout imprime al lado la
identidad de lo que midió**: el código de estado y un conteo de un elemento
propio de esa pantalla. Es el testigo del corolario 24 en su versión de
pantalla — un cero sin nada que diga de dónde salió es un cero que tranquiliza
—, y es el 47 otra vez con el mecanismo corrido: allá el número no podía
moverse, acá **se movía perfecto y describía otra cosa**.

Y el corolario del corolario, para el que mida una pantalla con puerta: el
`cliente` de la suite pasa porque los tests le ponen la cookie firmada. Un
script suelto no, y la diferencia no se ve en el número — se ve en el status,
que hay que ir a pedir.

**Y el mismo día, la variante barata: el bloque que se mide arranca CERRADO.**
Procesados hoy de Retiro vive en un `#panel { display: none }` que abre un
botón, así que medirlo de una da `0 de 3 pares` — prolijo, y de una pantalla
donde el bloque no está. Es el caso de Cargar Precios del corolario 47, con la
diferencia de que acá lo delató **el denominador**: tres pares es poco para una
pantalla con tres renglones de tres líneas cada uno.

**Y abrirlo a mano falló en silencio la primera vez**: inyectar
`id="panel" class="visible"` sobre un `<div class="tarjeta" id="panel">` deja
**DOS atributos `class`**, y el navegador ignora el segundo. La medición
devolvió exactamente el mismo número —`0 de 3 pares`— y eso se lee como "abrir
el panel no cambia nada", que es lo contrario de lo que pasaba. Con el
`class="tarjeta visible"` bien puesto: **3 → 18 pares**.

Lo que se lleva, y es de método: **cuando se manipula el HTML para medir un
estado distinto, el denominador tiene que MOVERSE.** Si abrir un panel, expandir
una fila o cambiar un filtro no mueve `pares` ni `celdas`, lo que falló es la
manipulación, no la pantalla — y sin el denominador las dos se imprimen igual.

**Y son DOS TURNOS SEGUIDOS con la misma columna haciendo el trabajo**, que es
lo que lo vuelve una regla y no dos anécdotas:

| turno | lo que se midió de verdad | lo que lo delató |
|---|---|---|
| alta de Proveedores | la pantalla de "Falta la clave de Gerencia" | `renglones 6` (con el `GET 200` al lado) |
| Retirados hoy | la pantalla con el panel todavía cerrado | `pares 3 → 18` |

Las dos veces los TRES números del detector —desborde, quebradas, solapes—
dieron cero, y los tres eran CIERTOS: una tarjeta con dos párrafos no
desborda, y un panel que no está tampoco. **Ninguno de ellos puede delatar
esto por construcción, porque los tres describen lo que se ENCONTRÓ y acá el
problema es lo que se MIRÓ.**

Por eso el denominador no es un adorno del informe: es la única columna que
contesta **"¿miré lo que quería, y entero?"**, que es otra pregunta que "¿está
bien?". Un cero de hallazgos sobre un denominador desconocido no distingue una
pantalla sana de una pantalla que no se abrió — es la ausencia de filas del
backfill otra vez, con los números prolijos arriba.

Y es el corolario 45 en su tercer trabajo: el testigo del 24 dice si la base
está viva, el total esperado del 45 dice si la medición llegó hasta el final,
y acá dice **cuál pantalla se midió**. Los tres existen por lo mismo — un
número solo no se puede leer.

### El TERCER límite, del 15/09: no veía que dos cajas se PISARAN

Una ayuda con `margin-top: -0.4rem` le comía 6,4px al `<select>` de arriba
en Editar artículo. **El detector decía quiebre 0 y desborde 0, y los dos
eran ciertos**: la celda mide una línea (no envolvió) y nada se sale del
ancho (sobra a lo alto). Es una tercera forma de romperse y no había número
que la viera.

Ya son tres límites del mismo módulo y los tres tienen la misma forma —una
clase de defecto que sus números no pueden expresar— así que lo que conviene
llevarse no es "faltaba el solape" sino **que la pregunta se hace al revés**:
antes de creerle a una medición de layout, preguntarse *¿de qué manera puede
estar rota esta pantalla que ninguno de estos números cambiaría?*

**Y el detector nuevo nació marcando de más, que es el 53 sobre sí mismo.**
Dos botones LADO A LADO tienen el borde inferior del primero más abajo que
el superior del segundo SIEMPRE —comparten renglón— así que la primera
versión marcaba dos falsos positivos por pantalla, en el catálogo de
Artículos. Se filtra exigiendo que los dos compartan alguna COLUMNA: si sus
rangos horizontales no se tocan, no están uno abajo del otro.

Lo que lo dejó pasar es lo que el 53 ya se había corregido a sí mismo y no
alcanzó: **los dos casos plantados del par eran formularios de una columna**,
donde el lado a lado no existe. El par estaba completo —el que pisa y el que
no— y no se parecía a la mitad de las pantallas donde se iba a usar.

**Y la otra mitad la dijo el canario, no el test**: devolverle el
`margin: -0.4rem` a las dos pantallas de artículos hacía caer CERO, porque
todos mis tests medían un fixture PLANTADO. Probaban la herramienta y no la
pantalla. La diferencia es el defecto real volviendo con la suite en verde,
y se cierra con un test que renderiza las dos pantallas de verdad y exige
`solapes == []` con `pares > 0` al lado.

#### Y la TERCERA forma de no-apilado es lo INLINE, del 18/09

El filtro de la columna compartida saca los botones de lado a lado y **no
puede ver ésta**: un `<strong>` adentro de un párrafo que ENVUELVE tiene por
caja la UNIÓN de sus renglones, así que ocupa el ancho entero —comparte
columna con todo— y arranca en la línea donde el `<strong>` de antes todavía
está. Medido en el índice de Vacíos del depósito, en el aviso de lo que
espera al conteo: `14 recepciones` de 1334,6 a 1350,6 y `3 devoluciones` de
1334,6 a 1366,6. **16px de "solape" con nada que se pise en la pantalla.**

Se saca preguntando `display !== "inline"`, y el `inline-block` se queda a
propósito: ése sí forma una caja y sí se apila. Por eso el par plantado son
dos —el párrafo que no tiene que marcar y un `inline-block` con margen
negativo que sí—; con el filtro escrito de más (`=== "block"`) el primero
pasa igual y el detector se apaga en media pantalla, que es el 53 otra vez.

**Y el fixture del caso bueno nació sin poder contestar**: tenía puros hijos
inline, así que después de filtrar el documento se quedaba **sin un solo par
que mirar** y `solapes == []` era el cero de "no se miró ninguno". Lo agarró
el `assert medicion["pares"] > 0` escrito al lado — el denominador del
corolario 45 mordiendo adentro del test escrito para el 53. El arreglo es que
el fixture se parezca a producción: el aviso va adentro de una tarjeta, con
hermanos de bloque, como en la pantalla.

### Y el QUINTO es la CLAVE que se lee del resultado (17/09)

`medir` devuelve **dos** números de desborde y uno de ellos está clavado en
cero. Cuando la pantalla no tiene filas de tabla —o sea, en toda pantalla de
tarjetas, que en celular son casi todas— la rama de arriba devuelve
`desborde: 0` **literal** y el valor real viaja en `desborde_pagina`.

`imprimir` lo sabe y usa el que corresponde. **El que lee `medicion["desborde"]`
a mano, no.** Medido: una pantalla que desbordaba 395px daba `desborde 0` y
`desborde_pagina 395` en la misma medición.

Y lo peor es cómo se descubre: **el canario no movió el número.** O sea que
la lectura equivocada se disfraza exactamente de "la pantalla está bien" Y de
"el canario no aplica" a la vez — las dos conclusiones tranquilizadoras
juntas. Lo único que lo destapó fue sondear la geometría a mano
(`documentElement.scrollWidth - clientWidth`) y ver que sí desbordaba.

Es el corolario 47 adentro del resultado en vez de adentro de la pantalla:
**el número no podía dar otra cosa**, y esta vez no porque midiera mal sino
porque era la clave equivocada. La regla, que cuesta cero: **en una pantalla
de tarjetas se lee `desborde_pagina`, o se usa `imprimir` y no se toca el
diccionario.**

### Y el SEXTO es una TARJETA haciendo de contenedor con scroll (18/09)

El primer límite dice que un `overflow-x: auto` se come el desborde de la
página. Ésa es la forma con la que se descubrió, y **se leyó como si la
condición fuera el `overflow-x`**: el que buscaba el caso iba a grepear
contenedores con scroll. La condición es más ancha, y en Armar Pedido la
cumple una tarjeta común.

Medido con un proveedor sin espacios en el selector de lote:

```
                                  desborde de PAGINA   lo que se sale de su caja
con el corte puesto (hoy)                0px                  nada
sin el corte (como estaba)               0px            div.salio-de +207px
```

**Las dos columnas de la izquierda son el mismo número, y una de las dos
pantallas se arrastraba de costado.** El que mira el desborde de página no
puede ver esto, y el canario tampoco: romper el arreglo NO MUEVE ese número,
así que sale a la vez "la pantalla está bien" y "el canario no aplica" — las
dos lecturas tranquilizadoras juntas, que es exactamente lo del quinto límite.

Lo que sí lo ve es sondear **cuánto se sale CADA elemento de su caja**
(`scrollWidth − clientWidth` sobre todos), que es la misma sonda del primer
límite aplicada sin saber de antemano quién la contiene. Por eso los dos tests
nuevos del renglón del lote miden por elemento y no por página.

**La regla corta, entonces**: el desborde de página no es cero porque la
pantalla esté bien — es cero mientras algún ancestro lo absorba, y en una
pantalla de tarjetas casi siempre hay uno. **Un cero de página solo vale con el
canario que lo hace crecer**; si romper el arreglo no lo mueve, hay que bajar a
medir por elemento antes de darlo por bueno.

### Y las filas que dibuja el JS no están en la pantalla que se mide

Del mismo día y es la otra mitad: el selector de lote arma sus filas con lo que
devuelve un `fetch`, así que una medición sobre el HTML servido mira una
pantalla **donde el renglón que se está probando no existe**. No da un número
mal: da el número correcto de otra cosa, y el denominador —cuántas filas se
dibujaron— es lo único que lo dice. Los dos tests lo llevan (`dibujadas == 2`)
al lado de `mirados`, por lo mismo que el corolario 53 pide el suyo.

## Corolario 54: el total DIMENSIONA, la magnitud unitaria DETECTA

Del 12/09, y es reutilizable: no es de las alertas de compras, es de
cualquier umbral.

**Un umbral sobre un TOTAL escala con la cantidad.** Así que en una operación
grande cualquier ruido lo pasa, y la alerta se llena de casos que no se le
pueden reclamar a nadie. **El que decide si algo es anómalo es el número por
unidad; el total decide si vale actuar.**

El caso, con los números al lado: la alerta de kilos faltantes filtraba por
`(estimado − real) × cajones ≥ 1`. Entraban

```
Jugo       −0,6k por cajón · total −19,8k   (33 cajones)
Berenjena  −0,3k por cajón · total  −6,0k   (20 cajones)
Cherry     −0,5k por cajón · total  −5,0k
Pepino     −1,0k por cajón · total −15,0k
```

**Tres décimas de kilo por cajón sobre veinte cajones son seis kilos**, y los
seis pasan un umbral de uno mientras las tres décimas son ruido de balanza.
Los tres primeros no se le reclaman a nadie; entraban por tener muchos
cajones.

### La señal, y es la que hay que llevarse

> **Si el umbral se puede pasar aumentando la CANTIDAD sin que el problema
> empeore, está aplicado sobre el lugar equivocado.**

Se contesta sin datos y en el momento de escribir el `where`: multiplicar por
más cajones no hace que el proveedor haya entregado peor.

**Y la propiedad que hace barato el cambio**: con la cantidad ≥ 1, todo lo
que pasa el umbral unitario pasaba también el del total. El conjunto nuevo es
**subconjunto** del viejo, así que mover el umbral al lugar correcto solo
puede SACAR casos, nunca agregar — no hay que revisar si se perdió algo que
antes se veía.

Medido en Frutamax (`db/kilos_5_cuantos_quedan_con_el_umbral_por_cajon.sql`,
`desde_la_foto` 09/09, `ultima_recepcion` 11/09): **de 11 a 8 sobre 74
recepciones**, o sea que el 11% de las compras tiene una diferencia real de
un kilo o más por cajón. Ocho reclamos posibles es accionable; once señalando
lo mismo, no.

**Y el 11 al lado del 8 es lo que hace legible el resultado** — por eso la
consulta devuelve las dos cuentas en la misma fila. Sin el número viejo,
"quedan 8" no dice si el cambio hizo algo. Es el corolario 45 aplicado a un
cambio de criterio en vez de a un total.

### El denominador lleva su recorte, y no es el que dice la ventana

Los 74 **no son de siete días**. La ventana pide siete (`current_date - 7`)
pero el piso de la foto la recorta al 09/09, así que son **del 09 al 12/09**.
El recorte efectivo es el MÁS RESTRICTIVO de los dos, y el que cita el 11%
sin eso está diciendo otra cosa.

Lo único que lo deja ver es que la consulta devuelve `desde_la_foto` como
columna (corolario 17) al lado del número: el parámetro viaja adentro del
resultado y no en un párrafo aparte que se lee una vez (corolario 19).

### Lo que NO lo agarró, que es la parte incómoda

**La suite estaba verde y siguió verde.** Dos tests fijaban el filtro sobre
el total —uno exigía el producto en el `WHERE`— así que eran **guardianes del
bug** (corolario 22): el arreglo los rompió, y la primera lectura de ese rojo
es "me equivoqué yo".

Y el comentario arriba de la constante **argumentaba explícitamente por el
total**: *"medir por cajón dejaría afuera exactamente los casos grandes de
las compras grandes"*. Era un argumento válido sobre una pregunta equivocada
—qué casos son GRANDES, no cuáles son ANÓMALOS— y es el corolario 25 otra
vez: un argumento bien construido defendiendo una premisa que nadie discutió.

Lo agarró **el dueño mirando la pantalla y reconociendo los artículos**. Ni
un test, ni una consulta: alguien que sabe que a la Berenjena no se le
reclaman trescientos gramos.

**Cómo queda cuidado de acá en adelante**, porque "mirar la pantalla" no es
una guarda: el test ahora exige el umbral por cajón **y que el producto NO
esté en el `WHERE`** — esa segunda mitad es la única que impide volver, y sin
ella el test lo pasa igual una consulta que multiplique. Y la constante se
llama `UMBRAL_KILOS_FALTANTES_POR_CAJON`: **el nombre lleva el alcance**
(corolario 8), porque este número no se puede comparar contra un total y fue
exactamente esa confusión la que produjo el bug.

## Corolario 61: una verificación que silencia `stderr` convierte un fallo en un resultado VACÍO, y un vacío se lee como cero

Del 14/09, cerrando el turno. Para confirmar que no hubieran quedado bases de
prueba fabricadas corrí esto:

```
echo "bases de prueba: $(su postgres -c "psql ... count(*) ..." 2>/dev/null)"
```

Imprimió **`bases de prueba: `** y por un segundo lo leí como cero. Postgres no
estaba levantado: el comando falló con `Connection refused` y salió con **2**.

**El `2>/dev/null` lo puse yo**, casi sin pensarlo, para que no ensuciara la
salida. Y eso es exactamente lo que hizo: le tapó la boca al único canal por el
que el fallo podía avisar. La verificación no se rompió ruidosamente — **devolvió
el resultado que yo esperaba ver.**

Las dos respuestas, corridas y no deducidas:

```
A) servidor CAIDO      stdout: []    $? = 2     <- lo que leí como cero
B) servidor ARRIBA,
   sin ninguna base     stdout: [0]   $? = 0     <- el cero de verdad
```

**El vacío y el cero no se parecen: son distintos en las DOS columnas.** Lo que
los volvió indistinguibles fue interpolar la salida adentro de un `echo`, que
imprime la línea igual esté vacía o no, y tirar el `stderr` al mismo tiempo.

### Por qué era diagnosticable sin saber nada del servidor

La consulta era `select count(*)`, y el corolario 27 dice que **un agregado sin
`group by` devuelve SIEMPRE exactamente una fila**. O sea que un `count` que sale
bien no puede imprimir una línea vacía: **el vacío era la prueba de que la
consulta no corrió**, y eso se ve sin saber si la base estaba arriba.

Es el 27 usado al revés y conviene tenerlo así: allá esa propiedad arruinaba una
guarda —`not found` nunca dispara— y acá **la misma propiedad es lo que delata el
fallo**. Una propiedad no es buena ni mala: lo es para un uso.

### La regla

**Una verificación no descarta `stderr` y no ignora `$?`.** Si hay ruido que
esconder, se esconde `stdout`, nunca el canal por el que llega el error. Y
cuando una verificación imprime un valor VACÍO donde se esperaba un número, se
mira el código de salida ANTES de leer ese vacío como un cero.

### Con qué engancha, y dónde es peor

Es el corolario 44 con el culpable cambiado: allá `pytest | tail -1 && git
commit` se comía el código de salida y **el pipe** tapaba el rojo; acá lo tapé
yo a mano. Las dos veces el error EXISTÍA y el comando lo hizo desaparecer.

Y es la familia del cero que no informa, **un escalón más abajo**: en el
corolario 47 el cero era un número real que no podía ser otro, y en el 24 era
verdadero pero sobre una base parada. **Acá no hubo medición ninguna** — y el
resultado se lee igual de prolijo que los otros dos.

**Lo único que lo frenó fue volver a correrlo antes de dejarlo escrito**, que es
lo mismo que frenó el corolario 33: una afirmación destinada a quedar por escrito
se relee distinto que una dicha al pasar. La regla no me protegió; el reflejo de
verificar de más, sí.

## Corolario 64: un aviso se arregla cuando dispara CERO, que es cuando es gratis

Del 15/09, y el criterio es del dueño. Medido `kiwi_1` sobre Frutamax: **0
pares que difieran sobre 34**. El caso que la alerta `unidades_que_difieren`
describe no está cargado en la base.

La conclusión fácil era "entonces no hay nada que hacer". La del dueño fue la
contraria, y es la que vale: *"el día que yo cargue la ficha de un cliente que
compra mango por kilo, esa alerta va a saltar y me va a proponer romperla"*.

**Un aviso cuyo link propone destruir el dato está mal aunque hoy dispare cero
veces.** Y cero disparos es exactamente cuando arreglarlo es gratis: no hay
filas que revisar, no hay nadie mirando la pantalla vieja, no hay que
comunicar un cambio. El día que dispare, arreglarlo cuesta además el caso que
ya se rompió.

**Y el cero es lo que decidió QUÉ NO construir**, que es la otra mitad: el
modelo de datos no se tocó —ni las dos magnitudes por compra ni el factor por
artículo— porque para eso el número sí manda. Es el corolario 23 y la regla de
las fichas borradas puestos uno al lado del otro, y esta vez separados a
propósito:

> **Medir antes de construir la CURA; no antes de cerrar la PUERTA.**

**Y LA CURA SE CONSTRUYÓ EL MISMO DÍA, lo que no invalida la regla: la
corrige.** El dueño dio vuelta la decisión con un criterio, no con un dato:
*"que hoy no esté cargado no significa que no va a pasar. Ya lo acordamos con
`a_reproceso` y lo volví a hacer: **si yo defino el caso, el caso es real**"*.

O sea que el cero contestaba la pregunta equivocada. **La pregunta no era
"¿esto pasa?" sino "¿esto va a pasar?", y eso no lo contesta ninguna
consulta** — lo contesta el que conoce el negocio. Es la misma regla que ya
estaba escrita en *"El dato de uso decide qué MEJORAR, no qué SACAR"* (las
opciones que define el dueño son casos reales aunque pasen una vez al año),
usada esta vez para no dejar de CONSTRUIR en vez de para no BORRAR.

Lo que la regla sigue diciendo, y es lo que vale: un cero **nunca** es la
razón para construir. Acá la razón fue el dueño; el cero solo dijo que no
había nada que migrar.

Acá la puerta son dos: que el aviso no proponga romper, y que el costeo no
entregue un número mal. Las dos valen con cero casos.

**Y el 15/09 se cerró una tercera con el mismo criterio**: el conteo que
contradice la unidad de la historia. Cero artículos hoy —los cuatro contados
tienen el conteo copiado por la migración— y el día que alguien edite uno de
esos cuatro y elija el otro conteo, sus fichas empiezan a costear cuarenta
unidades como cuarenta cubetas. No se descuadra nada y no hay pantalla donde
se vea. Cerrarla con cero casos no cuesta ni una fila que revisar. La cura —enseñarle al
sistema a convertir— espera a que haya uno.

## Corolario 69: el recorte de la MEDICIÓN no es el recorte de la DECISIÓN, y la prioridad se invierte

Del 16/09, y es la **segunda vez** —la primera fue el 11% de los kilos
faltantes, cuyo denominador de 74 recepciones era del 09 al 12/09 y no de los
siete días que pedía la ventana—. Acá el mecanismo es el mismo y la
consecuencia es más grande: **no ensució un número, invirtió qué había que
arreglar primero.**

`vino_armada_1` midió sobre TODA la historia: de **482 compras que muestran
el botón "Vino armada", 325 las frena el corte** — el 67%. El número es
cierto y la conclusión que sale sola es "arreglá primero el motivo del
corte".

**Es exactamente al revés.** Las 325 tienen `procesada_el` anterior o igual
al corte del 05/09, o sea once días o más, y **Buscar Compras busca 48 horas
por defecto**. Ninguna de las 325 puede aparecer en la pantalla que se ve. El
67% es cierto sobre la población y **cero sobre la pantalla**.

| motivo | de la población | de la pantalla por defecto | cuesta |
|---|---|---|---|
| anterior al corte | **67%** | **0%, por aritmética** | 0,4 ms |
| lote ya consumido | 38% | **aparece** — una compra de ayer puede tener su lote consumido hoy | 3,5 ms |

O sea: **el motivo barato es el que no se ve nunca y el caro es el que
muerde.** Y las 325 son además un número CONGELADO —ninguna compra futura
puede entrar ahí, porque toda recepción de acá en adelante es posterior al
corte— así que la proporción se apaga sola mientras el denominador crece.

**La señal, y se hace al escribir la consulta, no al leer el resultado**:
preguntarse **sobre qué conjunto se va a TOMAR la decisión**, y medir sobre
ése. Si la decisión es sobre una pantalla, el recorte de la pantalla —su
ventana por defecto, su filtro, su tope de filas— va adentro de la medición.
Un total histórico contesta "¿cuántos hay?" y la pregunta era "¿cuántos ve
la persona?".

Y cuesta una columna, que es la forma de siempre en este archivo:
`vino_armada_3_por_ventana.sql` devuelve los mismos motivos partidos en
48hs / 7 / 30 / 90 / todo, con `ofrecidas` al lado como población de cada
ventana. Con eso las dos lecturas están en la misma pantalla y no hay que
acordarse de nada.

**Los dos motivos se pusieron igual**, y la decisión es del dueño: *"el que
busca agosto a propósito merece leer por qué no puede, y 0,4ms no es un
costo"*. El recorte no decidió QUÉ construir — decidió **en qué orden creerle
al número**, que es lo que el 67% estaba a punto de arruinar.

## Corolario 70: la forma NATURAL de escribir una consulta es la que cuesta, y un índice "arregla" el síntoma dejándola puesta

Del 16/09. Para que el menú supiera si el lote de cada compra ya se consumió
hacía falta una cuenta más por fila. La forma que sale sola es un `left join
lateral` — se lee al lado de la fila, dice exactamente lo que uno piensa, y
es la que escribí.

Medido con `EXPLAIN ANALYZE` contra `db/esquema_completo.sql`, con 483
compras y 33.000 consumos, 500 filas (el tope de pantalla) y la ventana más
ancha que se puede pedir:

| | ms |
|---|---|
| la consulta como estaba | **0,5** |
| + el motivo del corte | **0,9** |
| + el lote consumido, **lateral por fila**, sin índice | **230** |
| + el lote consumido, lateral por fila, **con un índice nuevo** | **71** |
| + el lote consumido, **agrupado UNA vez** | **4,0** — y sin índice |

**El índice habría sido la trampa.** Es la reacción natural a un lateral
lento —falta el índice por `compra_id`, y de verdad falta— y habría bajado
230 a 71, que se lee como arreglado. Pero deja puesta la forma cara: 500
búsquedas donde alcanzaba con una pasada. **Agrupar gana 17× contra el
lateral CON índice, y encima no necesita el índice**, así que la migración
que parecía obligatoria no existía.

**La señal, y es una sola pregunta**: si una consulta hace una cuenta POR
FILA sobre otra tabla, preguntarse si esa cuenta se puede hacer **una vez
para todas las filas**. Con un agregado agrupado casi siempre sí, y la
diferencia no es de estilo: es de dos órdenes de magnitud.

**Y lo que lo decidió fue medir las TRES**, no las dos que uno compararía. Con
"sin índice contra con índice" el resultado es "hace falta el índice" y se
merguea una migración; la tercera columna es la que dice que la pregunta
estaba mal planteada. Es la familia del corolario 46 —lo que informa es lo que
se MOVIÓ entre una medición y la otra— aplicado a elegir entre dos formas: dos
puntos siempre trazan una recta, y la recta apunta a donde uno ya estaba
mirando.

El porqué queda escrito **en la consulta**, no acá: el que la lea dentro de
seis meses va a tener el `LEFT JOIN (SELECT ... GROUP BY)` adelante y la
tentación de "simplificarlo" a un lateral. El comentario dice los tres
números y termina en *"si alguien lo vuelve a un lateral, medir antes de
creerle"*.

Cómo crece, para que el 4,0 no se lea como gratis para siempre: con 5,5× los
consumos de hoy da **20ms**. Lineal, y a ese ritmo hay años.

## Corolario 78: un aviso que MEZCLA poblaciones no se arregla afinando el umbral — hay que partirlo, y a veces el resultado es que no hay aviso

Del 17/09, y es del dueño: *"eso no debería poder pasar: la caja sale de la
ficha"*. La pantalla de Cajas decía **"2 de 22 guías R no dicen en qué caja se
armaron, así que esas cajas no están descontadas"**, y la frase tenía dos
mitades: un conteo correcto y una explicación inventada — *"pasa cuando la
guía quedó sin ficha asignada"*, que es UNA de cinco causas.

**Las cinco, leídas del código y no deducidas:**

| por qué queda en NULL | ¿es un hueco? |
|---|---|
| la guía es anterior al **16/09**, que es cuando corrió `db/envases_3` | **no** — la columna no existía y la migración no backfillea |
| la guía se dejó **sin ficha** ("sin asignar") | no se puede saber cuál caja |
| **ficha variable**: el envase lo decide el cajón de ESA compra | no se puede saber, **nunca** |
| **ficha sin envase** (envase perdido) | no hay caja que descontar |
| ficha con envase **FIJO** y la columna en NULL | **SÍ**, y es el único |

**Cuatro de las cinco son normales**, así que el número no contestaba la
pregunta que su propia frase hacía. Y "no está descontada" es literal —la pata
`guias` filtra `r.lleva_caja_nuestra IS TRUE`— pero **descontar de más sería
peor**: en tres de los cinco casos no salió ninguna caja nuestra.

### Lo que el conteo tenía mal ADEMÁS, y es el error de alcance de siempre

Su docstring decía: *"solo cuenta desde el conteo inicial más viejo: antes de
esa fecha ninguna guía tiene la columna escrita"*. **El ancla es la
equivocada.** Lo que decide si una guía tiene la columna escrita es la fecha de
la MIGRACIÓN (16/09), y el conteo inicial lo fecha el operario — puede ponerlo
en agosto. Toda guía entre esas dos fechas se cuenta como hueco y no lo es.

Es el corolario 69 otra vez: **el recorte de la medición no es el recorte del
hecho que se mide.** Y acá con el agravante de que el ancla elegida la mueve
una persona desde una pantalla, así que el número del aviso cambia según qué
día alguien haya dicho que contó las cajas.

### El bug que creí encontrar abajo NO EXISTÍA, y lo construí igual (18/09)

Dejo el diagnóstico viejo tachado porque el error de método vale más que el
hallazgo que decía tener.

**Lo que escribí el 17/09**: `envase_derivado_de_la_ficha` define tres casos
y el tercero dice *"si no se puede derivar, se PREGUNTA"*;
`_envase_de_esta_guia` recibe `envase_declarado` para eso y **no tenía un solo
escritor**. De ahí salió que con ficha variable la caja sale, es nuestra, y no
se descuenta nunca. Construí la pregunta en Reproceso, la puerta en Guías R, y
la negativa que no deja guardar sin contestar.

**El parámetro no esperaba una pantalla: no tenía que existir.** El dueño lo
dijo en una frase: *"ya elegí la ficha arriba —Caja Chica Día — 10 u— y ahí
está la caja. Preguntarlo de nuevo abajo es preguntar dos veces lo mismo, y
encima deja elegir una caja distinta de la que declaré."*

**Y era verificable sin salir del repo**, que es lo que más duele. La única
otra cuenta que lee `envase_variable` es `envases_por_unidad_de_venta`
(core/envases.py), y sus dos ramas son:

```python
if envase_variable and contenido_del_bulto <= contenido_ficha:
    return 0.0          # descartable: el cajón ya es chico, sale como vino
return 1.0 / contenido_ficha   # LA CAJA DE LA FICHA, a la tasa de la ficha
```

**No hay ninguna rama que busque otro envase.** O sea que el flag decide **SI**
se usa una caja nuestra, no **CUÁL** — y en una guía R ese "si" ya está
contestado por el hecho de que la guía exista: anota `bultos_primera`, o sea
cajas ARMADAS. El caso descartable es exactamente aquel en que no se reprocesa
nada y no hay guía R.

**Dónde me equivoqué, con precisión**: el docstring de esa función llama al
caso no-descartable *"es caja chica"*, y leí eso como que nombraba **otro**
envase. La función devuelve `1/contenido_ficha`. **Construí sobre una frase de
la prosa y nunca sobre el valor de retorno** — que es el corolario 38/59 corrido
de lugar: allá el comentario rompe un test porque nombra la cosa que el test
busca; acá el comentario nombra una cosa del galpón y la leí como si nombrara
una columna.

**Y la señal estaba escrita por mí, en el mismo commit que introdujo el caso.**
El docstring de `envase_derivado_de_la_ficha` decía, textual: *"Los tres casos,
y el tercero **no estaba en el pedido** pero sale de la misma regla"*. Es el
corolario 29 —un requisito que nadie enunció— con la vuelta de que esta vez lo
dejé anotado al lado y no me detuvo. **Escribir "esto no me lo pidieron" no es
lo mismo que preguntarlo** — eso es el corolario 81, al final, que es donde
está el mecanismo entero.

**Lo que se hizo el 18/09**: la regla devuelve la caja de la ficha también
para la variable. Como las tres pantallas preguntan por esa función —el
selector de Reproceso, el `falta_la_caja` de Guías R y la guarda del server—
la pregunta desapareció de las tres con un solo cambio. Eso es lo único que
salió bien de haberla escrito una sola vez.

**Y `en_origen` se cerró de arriba**: la compra que llega ya armada deriva
igual que las otras, así que la columna `compras.envase_en_origen_id` que
estaba por migrarse **no hizo falta**. Es el corolario 23 en el último
momento posible — la medición que borra la pantalla antes de escribirla,
salvo que acá la borró el dueño leyendo la pantalla ya escrita.

**La única que sigue sin poder derivar es la guía SIN FICHA**, y su arreglo no
es un selector de cajas: es asignarle la ficha, que ya existe en Guías R y
vuelve a derivar. Un selector ahí dejaría elegir una caja que no es la del
cliente al que se le entregó.

### La forma general

**Un aviso que junta poblaciones con causas distintas no se arregla moviendo
el umbral: se parte por causa, y recién ahí se ve cuál de los pedazos merece
un aviso.** Acá el resultado de partirlo fue que **ninguno lo merece hoy**:
tres pedazos son normales, uno es un fósil que se apaga solo, y el que queda
necesita una función que no existe.

Es la contracara del corolario 23 —una consulta barata borró una pantalla
entera antes de escribirla—: acá borró un aviso que **ya estaba escrito y
andando**, y lo que lo destapó no fue una medición sino que el dueño leyera la
frase y dijera *"eso no debería poder pasar"*. **Una explicación que contradice
el modelo es una medición gratis**, y la que se escribió acá (`db/cajas_8_*`)
sirvió para dimensionar, no para descubrir.

## Corolario 88: una base parada contesta CERO a lo que ESTÁ, y CASI TODO a lo que FALTA

Del 19/09, y es el corolario 24 en espejo. El 24 dice que **una base parada
contesta cero a todo, y el cero se lee como "acá no hay problema"**. Eso es
cierto para las mediciones de PRESENCIA —cuántas guías R, cuántos armados,
cuántas frenan—. Para las de AUSENCIA es al revés, y esa mitad no estaba
escrita:

| qué se mide | qué contesta una base PARADA | cómo se lee |
|---|---|---|
| **presencia** (cuántas hay de esto) | **cero** | "acá no hay problema" |
| **ausencia** (cuántas NO tienen esto) | **casi todas** | "acá se trabaja mal" |

Y las de ausencia son justo las que este proyecto viene construyendo:
recepciones **sin** pesaje, renglones **sin** tildar, compras **sin** precio,
guías R **sin** caja declarada. En una base que se abandonó a mitad de un día,
todo lo que quedó a medio terminar queda a medio terminar **para siempre**, y
eso es exactamente lo que una medición de ausencia cuenta.

**Y EL TESTIGO NO SALVA, que es lo nuevo.** Contra el cero del 24 el testigo
funciona: una población chica al lado explica el cero. Acá la población
**está de verdad ahí** —los renglones existen, las recepciones existen— así
que el denominador sale grande, el porcentaje sale grande, y la fila se lee
como un dato sólido. `161 sin tildar de 181` trae su propio denominador y no
dice en ninguna parte que esos 181 son de una base que dejó de trabajar en el
medio. **El denominador certifica que se contó bien; no certifica que el
conjunto siga vivo.**

**El caso, y es el que costó el día**: Palmala dio **89% de renglones sin
tildar**, y de ahí salió —mía— una conclusión sobre CÓMO SE TRABAJA ("el
tilde se usa poco, el aviso va a disparar todos los días") que era un
artefacto del abandono. Frutamax, que es la que opera, dio **0 de 1709**. Las
dos filas tienen el mismo formato y dicen cosas opuestas; la que describe el
negocio es la de la base viva, y la otra no describe nada.

**La señal, y se hace al escribir el `where`**: si la consulta cuenta lo que
FALTA, una base parada es su **peor caso**, no su caso vacío. Ahí el testigo
hay que leerlo al revés de lo habitual — no *"¿hay suficiente población?"*
sino *"¿esta población está VIVA, o es el residuo de lo que quedó sin
terminar?"*. Y eso no lo contesta el número: lo contesta la última operación
al lado, y cuando ni eso alcanza, el dueño (corolario 84).

**Con qué engancha, y cierra el círculo**: el 24 dice que un cero de una base
parada TRANQUILIZA; éste, que un número grande de una base parada ALARMA por
lo que no es. Los dos son el corolario 6 —la medición falsa decide qué se
arregla después— y acá estuvo a punto de decidir dos cosas: si la alerta se
construía, y una conclusión sobre el galpón que nadie del galpón había dicho.

### La alerta de renglones SIN TILDAR: medida, y NO se construye (19/09)

`sin_tildar_1` en **Frutamax**, que es la única que cuenta:

```
0 sin tildar de 1709 renglones de días pasados
```

**Decisión del dueño: no se construye.** Y la razón hay que escribirla con
precisión, porque la que sale sola es la equivocada: **no es que el aviso
sería ruidoso — es que el caso NO EXISTE en Frutamax.** Hoy dispararía cero, y
un aviso que dispara cero **no tiene contra qué probarse**: no hay forma de
saber si el conjunto que cuenta es el correcto, ni si la unidad es la que va,
ni si el texto manda a hacer lo que hay que hacer.

**Y no es el corolario 64 dado vuelta.** El 64 dice que un aviso se ARREGLA
cuando dispara cero, porque ahí es gratis, y que *un cero nunca es la razón
para construir*. Acá no hay nada que arreglar: no hay un aviso puesto que
proponga algo destructivo ni una puerta abierta que cerrar. Lo único que había
era una alerta por escribir, y el cero dice que **todavía no tiene trabajo**.

El caso que la motivó —el renglón de VL tildado 30 horas tarde— fue **uno solo
y ya se resolvió**. Lo que sí quedó construido es lo que ataca ese caso de
verdad: **el cartel de "estás armando un pedido de otro día"**, que avisa en
el único momento en que alguien puede hacer algo al respecto.

**Lo que queda listo para el día que aparezcan**:
`db/sin_tildar_1_cuantos_hay.sql`, con sus cinco columnas de decisión
—`de_AYER`, `de_MAS_DE_7`, `EN_PEDIDO_YA_TERMINADO`, el total como
denominador y `PEDIDOS_CON_ALGUNO` para la unidad—. Se retoma corriéndola; no
hay que volver a pensarla.

**Y el 89% de Palmala no es este mismo número con otro signo**: es el
corolario 88, y no describe cómo se trabaja. No se cita para nada.

## Corolario 89: un assert de TEXTO verifica la FORMA de una consulta, nunca su VALIDEZ contra el esquema

Del 19/09, y contesta la pregunta del dueño —*"¿por qué la suite no lo
agarró, y es la misma causa que hace tres horas?"*— sobre las DOS pantallas
que se cayeron ese día con 2749 tests en verde.

**Es la misma FAMILIA y no el mismo mecanismo**, y la diferencia decide qué
se puede arreglar con un test y qué no:

| | qué decidió la respuesta | ¿un test podía verlo? |
|---|---|---|
| **11h** · desempacar 3 de una tupla de 2 | el FIXTURE devolvía una forma que producción no devuelve | **sí** — un fixture con la forma real (corolario 9/40) |
| **14h** · `column v.fecha_operacion does not exist` | **nadie**: el SQL no se le manda nunca a un Postgres | **no. Ninguno.** |

La primera es el andamio inventando un valor. La segunda es más honda: **en
esta suite la base está mockeada en todos lados, así que ninguna consulta de
este sistema se parsea nunca durante los tests.** Un SQL inválido no tiene
forma de fallar ahí.

**Y el test que podía verlo ESTABA PUESTO, era el correcto, y pasó.** El
corolario 65 dice que cuando lo que cambia es QUÉ COLUMNA pide la consulta
hay que mirar el TEXTO del SQL, y eso estaba hecho, anclado en la lista del
SELECT con su alias (corolario 4) y con su canario. Afirmaba `SELECT
cl.nombre, r.sucursal, r.ficha_id, r.pedido_id,` y era verdad: la columna
estaba escrita ahí. Lo que no podía saber es que **el CTE de arriba no la
expone**, que es una propiedad del SQL contra el ESQUEMA y no de su texto.

> **Ninguna cantidad de asserts de texto puede decir si una consulta parsea.**
> Eso lo contesta un Postgres con el esquema cargado, y nada más.

O sea que el 65 llegó hasta donde podía llegar, y el escalón que falta no es
un test mejor: es otra clase de evidencia.

### EL HUMO: `scripts/humo.py`, y se corre ANTES de desplegar

Abre **TODAS las pantallas** —las rutas GET menos las declaradas en
`NO_SE_ABREN`— contra una base cargada con `db/esquema_completo.sql`, con las
cookies de las cuatro puertas puestas y **sin un solo mock**. (Eran 128 el
19/09 y son 130 el mismo día: **el número no se escribe a mano en ningún
lado**, ni acá ni en el nombre del paso del CI, porque vence en el commit que
agrega una pantalla y no lo rompe nada. Lo cuenta el humo y lo imprime al lado
del resultado, que es el denominador del corolario 45.) Está también como
`tests/test_humo.py`, que lo lanza en SUBPROCESO cuando hay Postgres.

    python3 scripts/humo.py        # sin pipe, y se mira el $?

**Sin pipe, y es la regla del corolario 44 mordiendo en el comando con el que
lo estaba probando**: la primera corrida salió `RuntimeError` y el `| tail`
imprimió `salió con 0`.

### Y LA PRIMERA VERSIÓN NO AGARRABA EL BUG PARA EL QUE LA ESCRIBÍ

Ésa es la parte que vale. Abría las 113 rutas sin parámetro, daba `ROTAS 0`
con el bug puesto, y el canario con el bug real dijo **NO MORDIÓ**.

La causa: `/administracion/stock/remanente/porcion` —la pantalla del bug—
**pide `articulo_id`**, así que contestaba **422**. Routing OK, handler nunca
corrido, consulta nunca tocada. Y un 422 no es un 500, así que pasaba.

**El dato que lo decía estaba impreso en la misma línea del resumen**:
`422 4`. Yo mismo lo puse, escribí en el docstring que el 422 no es una
pantalla probada, y leí la línea sin leer esa columna. Corolario 53 y 19
juntos, adentro de la herramienta escrita contra ellos.

Las tres cosas que lo cerraron, y las tres hicieron falta:

1. **Los parámetros se rellenan por NOMBRE** (`*_id` → la fila sembrada,
   `desde`/`hasta` → fechas), leídos del esquema OpenAPI. No una tabla
   ruta→params escrita a mano: ésa envejece y la pantalla nueva que pida un
   id vuelve a contestar 422 sin que nadie lo note (corolario 60).
2. **De menos a más, parando en el primero que abra.** Con TODOS los
   parámetros puestos de prepo, la misma pantalla daba **404**: rellenar
   `ficha_id=1` apunta a una ficha que la siembra no tenía. Los dos extremos
   —ninguno y todos— dejan la consulta sin tocar.
3. **Las rutas con el id EN LA URL entran.** Eran 21 de 135, y
   `/administracion/stock/sistema/{articulo_id}` —donde vivía el bug de las
   11h— era una de ellas.

**Y el umbral es `ABIERTAS == miradas`, no `ROTAS == 0`.** Un `!= 500` deja
pasar el 422 de una pantalla que nunca corrió su consulta, que es exactamente
el agujero de la primera versión. Con el umbral estricto, el humo se degrada
en rojo: la ruta nueva que pida un parámetro que el relleno no sabe inventar
FALLA en vez de salirse del conjunto en silencio.

### Los dos errores de canario del mismo turno, y los dos ya estaban escritos

**El árbol rojo (corolario 82).** Con el baseline en `NO ABREN 9` —nueve
pantallas que no abrían por filas que faltaban en la siembra— el canario del
bug de las 11h salió **MORDIÓ**, y era falso: el humo ya fallaba antes de
romper nada. Recién con el baseline en **128 de 128** el canario mide una
diferencia. *Antes de leer un canario, contar* — y el número de partida iba
al lado.

**El canario mal apuntado (corolario 35).** Con el baseline ya verde, el bug
de las 11h dio NO MORDIÓ de verdad, y la causa no era el humo: yo estaba
mutando `_lotes_con_resto` y el bug había estado en `_pilas_de_cajones`, 1200
líneas más abajo. Apuntado al lugar correcto, muerde. *¿El código quedó roto
de la forma que me importa, o quedó roto de otra?*

El resultado, contra un baseline de 128 de 128:

```
BUG REAL 14h · el CTE no expone fecha_operacion   -> MORDIÓ
BUG REAL 11h · desempacar 3 de una tupla de 2     -> MORDIÓ
CONTROL · una columna inventada en otra consulta  -> MORDIÓ
```

### Lo que el humo NO agarra, dicho antes de que alguien le crea de más

- **El caso VACÍO.** La siembra planta UNA fila de cada cosa, así que lo que
  se ejercita es el camino de "hay una". Un `IndexError` sobre la fila 3 no
  se ve.
- **Lo que no es un GET.** Ningún POST se manda: todo el guardado sigue
  cubierto solo por la suite mockeada.
- **Las seis rutas declaradas** en `NO_SE_ABREN`, cinco de ellas porque
  sirven un archivo del Storage y no hay bucket local. Cada una con su razón
  al lado, comparadas contra el conjunto ENCONTRADO.

Y lo que **sí** cambia: desde hoy, un SQL que no parsea tiene dónde fallar
antes de que lo encuentre el que está en el galpón.

## Corolario 85: una consulta de diagnóstico que REESCRIBE una cuenta del sistema en vez de reusarla miente con números plausibles

Del 18/09, y es el corolario 6 con el culpable cambiado: allá una medición
quedó vieja al cambiar una regla; **acá nació mal el mismo día, porque en vez
de reusar la cuenta que el sistema ya tiene la escribí de nuevo desde cero.**

El caso. Para medir en qué días un artículo quedó negativo A SU FECHA escribí
`arandano_2` con dos patas —compras como entradas, armados como salidas— y dio
**192 días-artículo en rojo sobre 446**. El dueño lo leyó como un hallazgo y
estaba por decidir con él la ventana de una alerta.

**El stock de este sistema tiene SEIS patas**, y están escritas una sola vez en
`_SQL_SUMAS_STOCK` (app/db.py): compras, armados, reingresos, ajustes, y el
reproceso con `bultos_primera` de ENTRADA y `bultos_tomados` de SALIDA. Le
faltaban tres. Un artículo cuyo stock viene de una guía R —que es el caso
normal de cualquier cosa que se reprocesa— aparecía en rojo todos los días.

Reproducido contra el esquema real con cinco artículos, uno por pata:

```
                                    la vieja        la nueva     la regla real
                                    (2 patas)       (6 patas)    (_sql_sumas_stock)
dias-articulo en rojo                  4 de 5          1 de 5      1 (solo Arándano)
bultos descubiertos                        88              18      −18 al 17/09
```

**Y el 4 de 5 es el 192 de 446 en miniatura**: los dos son "más hallazgos que
población", que condena la heurística sin mirar un caso. Ese control estaba
disponible antes de abrir un solo día y no lo apliqué a mi propia consulta —
lo apliqué recién cuando el número volvió del dueño.

### Las dos direcciones en que mintió, y son opuestas

No es que exagerara: **fallaba para los dos lados**, y eso solo se vio con el
canario de cada defecto por separado.

| defecto | qué hace | cómo se ve |
|---|---|---|
| le faltan tres patas | **INVENTA** faltantes | 4 de 5 artículos en rojo |
| fecha las compras por `fecha_operacion` | **TAPA** faltantes | una compra comprada el 16 y recepcionada el 18 cuenta como si hubiera estado el 17 |

La regla real fecha las compras por
`coalesce((procesada_el at time zone ...)::date, fecha_operacion)`, o sea por
cuándo ENTRÓ al galpón y no por cuándo se compró. Medido plantando los dos
campos distintos: la mía decía **0** donde la regla real decía **−18**.

**Un derivado que falla en las dos direcciones no se corrige con un umbral.**
Y las dos mitades se tapaban entre sí: los falsos positivos de las patas que
faltaban hacían de ruido de fondo donde un falso negativo no se distingue.

### Y la SEGUNDA consulta del mismo día tenía un defecto que nadie buscaría

`arandano_1` —la línea de tiempo— filtraba los armados con `p.anulado_el is
null` a secas, y la regla real usa `vigentes` (`DISTINCT ON (cliente_id,
fecha_operacion) ... ORDER BY creado_en DESC`). **Un pedido RECARGADO no se
anula: deja de ser el vigente.** Así que el mismo armado aparecía DOS VECES en
la línea de tiempo que se usó para entender el caso. Verificado plantando un
pedido recargado: la regla vigentes dice 1 armado, `anulado_el is null` dice 2.

Y eso es lo que lo vuelve peor que un descuido: **el caso que se estaba
investigando era justamente uno donde hubo recarga.** El defecto pegaba
exactamente donde se estaba mirando.

### La regla

> **Antes de escribir una consulta de diagnóstico sobre una cuenta que el
> sistema ya sabe hacer, ir a buscar dónde está escrita esa cuenta y contar sus
> patas.** Si el `.sql` tiene menos términos que la función, no es una
> simplificación: es otra cuenta.

Y cuando el `.sql` no puede importar la función —que es siempre, porque se
pega en el editor de Supabase— lo que queda no es libertad para reescribirla:
es la obligación de **nombrar de dónde salió** (`-- LAS SEIS PATAS de
_SQL_SUMAS_STOCK`) y de verificarla **contra la función misma**, no contra la
intuición. Es el corolario 71 —una regla escrita dos veces con distinto
poder— con la vuelta de que acá la copia sin poder es la que decide qué se
arregla después.

### La regla del MOMENTO, que es la que falló (del dueño)

> **Una consulta de diagnóstico que decide si algo se construye tiene que
> COLISIONAR CONTRA LA REGLA REAL antes de leer su número. No después.**

Las tres formas de abajo estaban todas disponibles el día que escribí
`arandano_2`, y las corrí **recién cuando el número volvió del dueño**. Ese
orden es todo el error: para cuando colisioné, el 192 ya había salido en un
mensaje, ya tenía la autoridad de una medición, y ya estaba por decidir la
ventana de una alerta.

**Y no es que haya faltado rigor al verificar: faltó verificar ANTES.** Una
colisión hecha después no es una verificación — es una autopsia. Sirve para
saber qué pasó; no para impedir que el número viaje.

Lo que lo vuelve accionable es que el disparador es fácil de reconocer:
**el momento es cuando la consulta va a devolver un número que alguien va a
leer**, no cuando la consulta se termina de escribir. Si el resultado va a
salir de mi pantalla —a un mensaje, a un doc, a una decisión— la colisión ya
tiene que estar hecha.

### Cómo se verifica, y son TRES cosas distintas

Ninguna de las tres sola alcanza, y esto es lo que costó el turno:

1. **Un artículo por PATA en el fixture.** Con un fixture de un solo artículo
   comprado y armado, las seis patas y las dos dan el mismo número. Los cinco
   artículos —uno que solo se mueve por guía R, uno por ajuste, uno por
   reingreso— son lo único que hace que sacar una pata mueva el resultado.
2. **El canario POR PATA, no uno solo.** Sacar la de movimientos_stock lleva
   1 a 3; sacar la de reprocesos lleva 1 a 2. Un canario único que rompa
   "algo" no dice cuál mitad no estaba cubierta (es el canario corrido línea
   por línea del corolario 43, aplicado a los términos de una suma).
3. **La colisión con la FUNCIÓN REAL, importada y no retipeada.**
   `python3 -c "import app.db as d; d._sql_sumas_stock(por_articulo=False)"`
   devuelve el texto exacto que corre en producción, y correrlo sobre el mismo
   fixture es lo que convierte "mi consulta parece bien" en "las dos dicen lo
   mismo". Es *la verificación que funciona es la que hace chocar dos fuentes*
   (corolario 19), y la fuente contra la que hay que chocar es el código, no
   otra consulta que escribí yo.

**Y el caso que tiene que dar CERO va en la lista**: con el ingreso de Arándano
fechado el 17 en vez del 18, la consulta da 0. Sin ése, una consulta que marque
todo pasa igual todos los casos positivos (corolario 30 y 53).

### Y el número corregido tenía UNA SEGUNDA lectura equivocada adentro

Con las seis patas puestas, `rojo_a_su_fecha_1` dio **45 días-artículo en rojo
sobre 446 y 2355 "bultos descubiertos"** en Frutamax. El 45 es correcto. El
2355 **no son bultos: son bultos-DÍA.**

`saldo` es el déficit PARADO de ese día, así que sumarlo a lo largo de los días
cuenta el mismo faltante una vez por día que dura. Medido con el caso plantado:
un artículo que sale **10 bultos sin cubrir UNA vez** y queda así tres días
aporta **30**. La mercadería que salió descubierta es 10.

Es el corolario 13 exacto —una cuenta exacta sobre lo que mide, que deja de
contestar la pregunta con la que se la va a citar— y la pregunta con la que se
la iba a citar era la del dueño: *"2355 bultos, mercadería que salió sin tener
con qué"*. Ese número está inflado por cuánto duró cada déficit, no por cuánta
mercadería salió.

**Las dos cuentas van SEPARADAS y con nombre propio**, porque las dos sirven y
significan cosas distintas:

| | qué cuenta | para qué |
|---|---|---|
| `BULTOS_SIN_COBERTURA` | lo que se DESCUBRIÓ ese día (el déficit que creció) | cuánta mercadería salió sin cubrir |
| `BULTOS_DIA` | el déficit parado, sumado por día | cuánto tiempo estuvo descubierto |

**Y el filtro que faltaba era más grande que el nombre**: un renglón armado en
CERO —que existe porque el confirmar guarda todo lo del mail— producía un
día-artículo en rojo sin que saliera un solo bulto. Con el `having sum(...) > 0`
puesto, el caso plantado pasa de 4 casos a 2. O sea que el 45 real es más chico
todavía, y la parte que se iba tenía la forma de "sigue pasando" sin que pasara
nada nuevo.

**Cómo se reconoce sin sufrirlo**: cuando una cuenta suma un ESTADO a lo largo
del tiempo —un saldo, un pendiente, un descubierto—, preguntarse si la unidad
del resultado es la cosa o la cosa POR TIEMPO. Si un caso que no cambia hace
crecer el número, es por tiempo, y el nombre tiene que decirlo.

### Lo que NO hay que hacer con el número mientras tanto

El 192 alcanzó a salir en un mensaje, y eso es lo caro: **un número falso viaja
con la autoridad de una medición y decide qué se construye.** Acá iba a decidir
la ventana de una alerta —siete días o dos— y con 192 sobre 446 la conclusión
natural era "esto dispara todos los días, no sirve". La alerta correcta se
habría descartado por el número de la consulta rota.

Por eso, y es lo único operativo que queda: **al retractar un número, retractar
también la DECISIÓN que ese número estaba por tomar**, y decirlo en la misma
frase. "El 192 estaba mal" invita a corregir el 192; "el 192 estaba mal y por
lo tanto la ventana todavía no se puede decidir" es lo que impide que la
decisión sobreviva a su premisa.

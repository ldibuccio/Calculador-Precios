# Corolarios: pantallas, caminos y puertas

Movido TAL CUAL desde CLAUDE.md el 03/10 (sin reescribir). Las reglas
vigentes, en corto, están en CLAUDE.md.

## Corolario 56: un campo único en una definición que se muestra en VARIOS contextos va a estar mal para todos menos uno

Del 12/09, y la formulación es del dueño: **la url era una; los sectores,
tres.**

`DefinicionAlerta` tiene una `url` y un `texto_link`, y una alerta puede
mostrarse en varios sectores a la vez (`modulos`). La acción que la apaga
vive en UNO de esos sectores, así que el link es correcto para ése y
arbitrario para el resto. No es un caso mal cargado: **es la forma del
problema**, y estaba en el tipo desde el principio.

### Por qué estuvo invisible hasta que dejó de estarlo

Sin zonas con clave, un link al sector equivocado era **un rodeo**: llegabas
igual. El 12/09 Compras ganó puerta y el mismo link, sin cambiar una letra,
pasó a ser **una pared**. La alerta `unidades_que_difieren` se mostraba en
Compras y en Comercial y apuntaba a Artículos; ese día Artículos se mudó bajo
`/compras`, y el usuario de Comercial quedó pegando contra una clave que no
es la suya.

(El 15/09 esa alerta pasó a UN SOLO SECTOR —el arreglo vive entero en
Artículos— así que su `destinos_por_sector` se fue. El caso que enseñó el
corolario ya no existe; el corolario sí, y lo cuidan las otras dos que
todavía se muestran en varios sectores. **Que el ejemplo se apague no apaga
la regla** — es la diferencia entre el MECANISMO y el ESTADO que se anota al
lado para ilustrarlo.)

Es la familia del corolario 28 —algo que afirmaba lo que valía antes del
camino nuevo— con la vuelta de que acá **el cambio que lo activa está en otro
archivo y en otra decisión**: nadie tocó la alerta.

### Lo que lo encontró, y es lo único que sirve

**Enumerar el producto cruzado, no mirar el caso reportado.** Escrita la
guarda —para cada alerta, para cada sector que la muestra, ¿su link cae en
una zona con puerta ajena?— aparecieron **dos más** que nadie había visto:

```
compras_sin_precio        se muestra en comercial  ->  /compras/pendientes
guias_r_costo_incompleto  se muestra en compras    ->  /administracion/stock/guias-r
```

Una la produjo la puerta de ese mismo día; la otra era anterior y llevaba
dos días. Es el corolario 2 —buscar la otra copia— hecho consulta en vez de
hecho a mano: con tres sectores y veintiuna alertas, el `grep` no alcanza
porque **el defecto no está en ninguna línea: está en el cruce**.

### La distinción que evita rediseñar a ciegas

No todos los campos de una definición son por contexto, y confundirlos hace
un tipo lleno de diccionarios:

> **Los campos que describen la COSA son únicos. Los que describen el CAMINO
> son por contexto.**

El código, el título, la cantidad, la fecha del caso más viejo: son la cosa,
y no dependen de quién mire. La url y el texto del link son el camino, y
cambian con quién mira. La señal barata para reconocer un campo del segundo
tipo: **nombra un lugar o le habla a alguien** — una url, un "Ver en X", un
texto de ayuda que dice qué hacer.

### Y las dos mitades de un link viajan JUNTAS

`destinos_por_sector` guarda `sector: (url, texto)` y no hay un segundo
diccionario en paralelo. Separados se despegan: el día que alguien cambie el
destino de un sector y no el texto, el link dice "Ver en Guías R" y lleva a
Compras sin precio. **Un solo lugar para una sola decisión** — es la regla
escrita dos veces, en su versión más chica.

### Lo que el mecanismo NO hace, y hay que decirlo

**Da dónde poner un destino; no inventa uno.** Eso del mecanismo no cambia.
Lo que sí cambió es el ESTADO que se anotaba al lado: de los tres casos, dos
se resolvieron el 12/09 —cada sector tiene una pantalla donde actuar— y del
tercero se escribió, en presente, que *"en Comercial no hay a dónde
mandarla"*. **Los tres están cerrados desde el 19/09**, y el que faltaba se
cerró sin inventar ningún destino: ver abajo.

**CERRADO EL 19/09, y la salida era la que este párrafo daba por
inexistente.** Durante una semana esto dijo —y el comentario de la deuda en
el test repetía— que *"en Comercial no hay a dónde mandarla"*. El destino
existía y estaba descrito tres párrafos más abajo de la frase que lo negaba:
**la pantalla de alertas de Comercial**, que desde el 12/09 muestra cuáles
son porque la alerta tiene `detallar`.

Y el precedente estaba en el registro desde antes: `kilos_faltantes` y
`cajones_faltantes` apuntan a la pantalla de alertas de SU propio sector,
con su razón escrita en `alertas_sector.html` — *"desde el BANNER ese destino
es el correcto, te trae a ver el detalle; adentro de esta pantalla es un link
que recarga la misma página"*, y la plantilla lo esconde sola. O sea que no
hubo que inventar ningún destino ni tocar el mecanismo: una línea de
`destinos_por_sector`.

**Por qué la razón vieja convencía, que es lo que hay que llevarse**:
contestaba *"¿dónde se ARREGLA?"* —y ahí seguía teniendo razón, la acción es
de Compras y no se mueve— cuando la pregunta era **"¿a dónde puede IR el que
la ve?"**. Es el corolario 68 en su tercera forma: no envejeció la población
ni el contenido de lo omitido — la razón contestaba otra pregunta desde el
principio, y por eso releerla no la delata. Lo que la delata es que alguien
vuelva a preguntar.

**Medido en las dos puntas antes de darlo por hecho**, porque el destino se
lee en dos lugares que hacen cosas opuestas:

```
                        banner                    su propia pantalla
COMERCIAL   /comercial/alertas (era pendientes)   sin link (se esconde)
COMPRAS     /compras/pendientes                   /compras/pendientes
```

Y la premisa del choque se verificó igual, aunque fuera la vieja: `GET
/compras/pendientes` sin la cookie contesta **401**. La puerta de Compras
cubre los GET, no solo los POST.

**Lo que Comercial sigue sin poder es ACTUAR, y está bien**: la alerta le
dice qué no va a poder costear, no le pide que lo arregle.

**Y la deuda del test quedó VACÍA**, que es lo que hizo falta para cerrarla:
el barrido resta en las dos direcciones, así que arreglar el link **rompió el
test** con *"ya no chocan, sacalas de la deuda"* y obligó a sacar la entrada
en el mismo commit. Una lista de deuda que no falla al arreglarse se queda
protegiendo lo que ya no pasa (corolario 22), y ésta no pudo.

## Corolario 63: `?origen=` sirve entre sectores SIN clave; con clave de por medio, el sector tiene que salir del PREFIJO

Del 15/09. Precios por Período la usan dos sectores —Comercial, que la tiene
en `/precios`, y Administración, que es la que le factura al supermercado— y
había que agregar la segunda entrada sin duplicar la pantalla.

El sistema ya tenía **dos precedentes de "una pantalla, dos sectores"**, y
elegir mal no se ve hasta después:

| | cómo viaja el sector | dónde está |
|---|---|---|
| **`?origen=`** | en la query, una sola ruta | `/logistica/retiro?origen=deposito` |
| **Dos rutas, un helper** | en el prefijo de la URL | `/compras/alertas` y `/comercial/alertas` |

**Lo que decide no es el gusto: es si alguno de los dos sectores tiene
clave.** En este sistema la puerta se aplica **por PREFIJO, en un
middleware**, y la barra dibuja el 🔒 mirando `barra_sector`. O sea que con
el sector viajando en la query, la URL de Comercial —que ninguna puerta
cubre— dibuja el candado de Administración.

**Medido, no razonado** (canario con el sector leído de `request.query_params`):
`/precios/vigencias?origen=administracion` → `candado: True`. Un candado
sobre una pantalla que su puerta no cubre es exactamente lo que
`_bloqueo_del_sector` dice que es peor que ninguno — y encima el sector lo
elige quien escriba la URL.

Con el prefijo, **el sector de la barra y la zona que el middleware aplica
son el MISMO hecho y no se pueden separar.** Y el `?origen=` de
`/logistica/retiro` sigue estando bien donde está: Logística y Depósito no
tienen clave, así que ahí no hay candado que mentir. No es un patrón viejo
que haya que migrar — es el patrón correcto para su caso.

### Y la clave se resuelve AGREGANDO, no mudando

La otra mitad, y es la pregunta que hay que hacerse siempre que una pantalla
gane una segunda puerta: **¿mudarla deja afuera a alguien?** Acá sí — bajo
`/administracion`, el de Comercial (que no tiene clave) se habría encontrado
con una pantalla pidiéndole una clave que no puede contestar. Así que la
vieja se queda donde está y la nueva se agrega.

**Y lo que la clave nueva NO hace se dice en voz alta**, o se lee como una
protección que no es: esos precios YA se ven sin clave en `/precios/vigencias`,
porque Comercial no tiene puerta y son sus datos. La ruta nueva nace cerrada
por el prefijo —que es la gracia del middleware— pero **no agrega ni saca
acceso a nadie**: lo único que cambia es desde dónde se llega. Una puerta que
se describe como protección cuando la misma cosa está abierta al lado es la
familia del candado que no cierra, con la diferencia de que acá el que se
confunde somos nosotros y no el operario.

**El barrido del prefijo lo cuidó solo**: las dos rutas nuevas entraron a
`test_la_puerta_de_administracion_cierra_TODO_el_prefijo` sin escribir una
línea, que es justo lo que ese test promete. Lo que ningún barrido mira es la
dirección contraria —que la de Comercial **siga abierta**— y eso sí hubo que
escribirlo: el barrido enumera lo que está adentro del prefijo, y lo que se
rompería al mudar está afuera.

### LO QUE NO SE VE PROBANDO A MANO: el bug aparece en el SUBMIT, no al entrar

Y es la parte que más se lleva, porque cambia dónde hay que mirar.

Al entrar por la ruta nueva **la barra sale perfecta**: se la pasa el server
con el sector correcto. La pantalla se ve bien, se prueba a mano, y pasa. Lo
que quedó apuntando al otro sector es **la `action` del formulario**, que
está en la plantilla — así que el primer cambio de cliente la devuelve a
`/precios/vigencias`, y recién **la segunda** pantalla le dice Comercial.

O sea: el que prueba entra, mira la barra, la ve bien y cierra. La avería
está a un click de distancia, y ese click es el que la persona hace siempre
(elegir el cliente es para lo que abrió la pantalla).

**La regla, y es enumerable**: cuando una pantalla pasa a tener dos entradas,
las mitades del camino son **cuatro** y hay que revisarlas una por una —
la barra, el atrás, la `action` del formulario y los links de descarga—.
Basta que UNA quede fija para sacar del sector; tres de las cuatro no se ven
al abrir la pantalla.

Y la forma barata de afirmarlas todas juntas, sin enumerar: **exigir que la
URL del otro sector no aparezca NI UNA VEZ** en el marcado
(`assert "/precios/vigencias" not in marcado`). Eso cubre las cuatro y también
la quinta que alguien agregue mañana — es el mismo argumento del conjunto
ENCONTRADO contra el DECIDIDO (corolario 60): una lista propia solo confirma
lo que ya sabías.

### Qué viaja en el contexto y qué no

Corolario 56 al pie de la letra —**los campos que describen la COSA son
únicos; los que describen el CAMINO son por contexto**— y acá la línea quedó
así:

- **Por contexto**: el sector, el atrás, y la `base` de la URL. El link del
  Excel **sale de la base** en vez de ser un cuarto campo, para que las dos
  mitades no se puedan despegar.
- **Único, en la plantilla**: el título. Es la misma pantalla para los dos, y
  meterlo en el diccionario habría sido empezar a llenarlo de cosas que no
  varían.
- **Y un destino que NO existe desde un sector no se inventa**: el cartel de
  vacío dice "cargale el precio desde Cargar Precios" solo entrando por
  Comercial. Cargar Precios es de Comercial; mandar a Administración ahí es
  mandarla a hacer el trabajo de otro. Es lo que el 56 ya decía —el mecanismo
  da dónde poner un destino, no inventa uno— usado esta vez ANTES y no
  después de que choque.

## Corolario 68: un camino que FUNCIONA y no se VE es un camino que no existe, y ningún test de marcado puede ver la diferencia

Del 16/09. Buscar Compras metió sus acciones en un menú y **el Detalle se
quedó afuera sin botón**, con este argumento escrito en la plantilla: *"la
tarjeta entera lleva ahí: es lo que se quiere el 80% de las veces y no
necesita botón"*.

El argumento es válido y el mecanismo anda. Medido en el navegador, no
leído:

```
                          ESCRITORIO (1200px)   CELULAR (390px)
cursor de la fila             pointer              pointer
el click llega al handler     True                 True
```

El JS no está adentro de ningún `@media` y `tbody tr[data-detalle] { cursor:
pointer }` tampoco, así que **la fila SÍ es tocable en escritorio.** Lo que
faltaba no era el camino: era que se viera.

```
link_color   rgb(34, 34, 34)      color_celda  rgb(34, 34, 34)
link_subrayado   none
```

El nombre del artículo **era un link con el color exacto del texto de al
lado y sin subrayar.** En el celular no se nota porque el dedo toca
cualquier lado por costumbre; en escritorio el que busca una acción busca un
botón, y el único indicio era el cursor al pasar por encima — que hay que
sospechar para encontrar.

**Y se llevó puesta una operación entera.** `grep` de los dos: el Detalle es
la ÚNICA puerta a **Corregir Recepción** (un solo `href` en todo
`templates/`), y Buscar Compras es la única puerta al Detalle. Un camino de
tres eslabones donde el primero se volvió invisible.

### La parte que no teníamos escrita: el test EXIGÍA la ausencia

No es que ningún test cubriera el botón. Había uno que lo prohibía:

```python
# Editar sigue estando, adentro del menú. DETALLE YA NO ES UN BOTÓN: la
# tarjeta entera lleva ahí, que es lo que se quiere el 80% de las veces.
assert ">Detalle<" not in texto
```

Es el corolario 22 en su forma más fuerte —el fixture que fija el caso
equivocado convierte al test en el guardián del bug— con un escalón más:
**acá no hay un fixture que mirar, hay un ARGUMENTO.** Y cumplió su función
de guardián al pie de la letra: agregar el botón lo hizo fallar, y la primera
lectura de ese rojo es *"me equivoqué yo"*.

**La distinción, y es la que hay que tener a mano** (del dueño, 16/09): no
fue que FALTARA un test. Fue que había uno **defendiendo la ausencia**, y
son dos cosas que se buscan distinto. Un hueco se encuentra preguntándose
qué no está cubierto — una pregunta que uno se hace. Un test que defiende
la ausencia **ya contestó esa pregunta**, y contestó que no va: aparece en
la lista de tests verdes como una decisión tomada, no como algo que falta.

> **Un test con razón escrita no se cuestiona.**

Ahí está todo el daño. Un assert pelado invita a preguntar por qué; uno con
su comentario al lado se lee como un acuerdo al que ya se llegó, y el que
pasa por ahí supone que alguien lo pensó mejor que él. Es exactamente el
corolario 25 —un argumento válido es más difícil de revisar que uno flojo,
porque se defiende mejor y se copia a los comentarios, donde envejece con
toda la autoridad de algo razonado— mordiendo adentro de la suite en vez de
adentro de un docstring.

**Y la premisa VIAJÓ, que es cómo un argumento cierto queda defendiendo algo
falso.** El 80% era verdad sobre el celular, donde el dedo toca cualquier
lado. El mismo assert corre sobre la tabla de escritorio, donde la
afordancia que lo sostenía —tocar sin mirar— no existe. Nadie se equivocó al
escribirlo: se equivocó el alcance, y el alcance no estaba escrito en ningún
lado.

**Lo accionable**, y es una sola pregunta que se hace al ESCRIBIR, no al
leer: cuando un assert diga que algo NO tiene que estar, **escribir al lado
para qué población vale**. "No va el botón porque la tarjeta entera lleva
ahí" es una afirmación sobre el celular; escrito así se ve solo el día que
alguien lo lea pensando en escritorio. Es el corolario 8 —el nombre lleva el
alcance— aplicado a la razón de un test.

### Y la razón envejece cuando cambia lo que la FILA DICE, no el código (19/09)

Segunda vez con la misma forma, y agrega el disparador que faltaba.
`test_con_UN_SOLO_formato_el_desglose_NO_aparece` afirmaba una ausencia con
su razón escrita al lado: *"un desglose que sale siempre repite el número de
arriba"*. Era cierto mientras la fila dijera solo el reparto.

El 19/09 la fila ganó **el kilaje y el proveedor**, y ahí dejó de repetir
nada: le agrega lo único que el número no puede decir —*"41 bultos pueden ser
200 kilos o 600"*—. Nadie tocó ese test ni esa condición; lo que cambió es
**qué contiene la cosa cuya existencia el test discutía**. Y como 52 de los
57 artículos de las dos bases tienen un formato solo, la regla vieja apagaba
el dato justo en el caso normal.

Con el 68 son dos disparadores distintos, y conviene tenerlos juntos porque
se buscan distinto:

| | qué cambió | cómo se encuentra |
|---|---|---|
| **corolario 68** | la POBLACIÓN (celular → escritorio) | escribir al lado para qué población vale |
| **éste** | el CONTENIDO de lo que se omite | releer la razón el día que la cosa gana un campo |

**Lo accionable, y se hace al AGREGAR el campo y no al leer el test**: cuando
algo que una pantalla muestra gana un dato nuevo, grepear en `tests/` los
asserts que niegan esa cosa. Una razón escrita sobre *"no aporta nada"* es
una afirmación sobre su contenido, y un contenido nuevo la vence.

**Y el rojo llega cuando el arreglo es correcto**, que es lo caro: el test
cae al agregar la fila, y la primera lectura es *"me equivoqué"*. La pregunta
sigue siendo la del corolario 22 — *¿este test afirma lo que hoy queremos que
pase, o lo que pasaba?* — con la precisión de que acá la respuesta no está en
el fixture sino en el comentario, y el comentario es el que convence.

### Y el TERCER disparador: la razón contesta OTRA PREGUNTA que la de ahora (19/09)

Tercera vez, y el disparador no es ninguno de los dos de arriba.
`test_el_remanente_NO_dice_la_palabra_suelto_ni_totales_por_articulo`
defendía que el Remanente **no muestre el total del artículo**, con esta
razón escrita: *"sumar 4 sueltos y 5 en caja no le sirve a nadie que tenga
que ir a buscarlas"*.

**Sigue siendo cierta, palabra por palabra.** No envejeció la población
—siempre fue la misma pantalla y la misma gente— ni el contenido de lo que
se omitía. Lo que pasó es que **la pantalla se usa para dos cosas y la razón
solo cubre una**: para IR A BUSCAR sirve la pila, y para ver si algo CIERRA
hace falta el artículo entero. El dueño lo dijo con el caso: *"Cherry
aparece como 41 y como 1 en dos renglones separados, y no hay ningún lugar
donde lea 42"*.

Los tres, juntos, porque se buscan distinto:

| | qué cambió | cómo se encuentra |
|---|---|---|
| **corolario 68** | la POBLACIÓN (celular → escritorio) | escribir al lado para qué población vale |
| **el segundo** | el CONTENIDO de lo que se omite | releer la razón el día que la cosa gana un campo |
| **éste** | la PREGUNTA que se le hace a la pantalla | releerla cuando alguien la usa para algo nuevo |

**Y el tercero es el único que no tiene un disparador en el código**: nadie
tocó nada. Llega como una queja —"no hay ningún lugar donde lea 42"— y la
respuesta correcta a esa queja es ir a buscar el test que la prohíbe, porque
va a estar, con su razón al lado, sonando sensata.

**Lo accionable**: cuando alguien pide un dato que la pantalla no muestra,
antes de discutir si conviene, **grepear en `tests/` el assert que lo niega**.
Si existe, la discusión no es "¿lo agregamos?" sino "¿para qué pregunta se
escribió esa razón, y es la que nos están haciendo?".

#### Y LA RESPUESTA A LA QUEJA NO ERA AGRUPAR: revertido el mismo día

El mecanismo de arriba queda entero y el ESTADO que se anotó al lado para
ilustrarlo duró tres horas. Se agrupó el Remanente por artículo, con la
cabecera del total arriba y las porciones abajo, y el dueño lo revirtió:
*"El depósito lee 'Limón' y 'Limón Caja Día' como dos renglones planos y eso
funciona. La cabecera con el total agrupado complica una pantalla que era
clara."*

**La queja era real y la solución era otra.** *"No hay ningún lugar donde lea
42"* no pedía una cabecera: pedía poder leer el artículo entero cuando algo
no cierra, y eso ya tiene su lugar —el renglón corto, que desde el 19/09
muestra el número del artículo— sin tocar la lista. Encontrar el test que
niega un dato dice que hay algo que discutir; **no dice cuál de las formas de
darlo es la que va**, y ésa es una decisión de pantalla, no de test.

**Y lo segundo es lo que más cuesta**: el agrupado *"ya te lo había dicho"* —
estaba rechazado de antes. Llegó envuelto en un *"se me ocurre agrupar…
pero decidilo vos"*, y un "decidilo vos" sobre algo que ya se rechazó **no es
una licencia: es el momento de decir que ya se rechazó** y preguntar si
cambió de opinión. La delegación se lee como permiso y es una pregunta.

**Lo que sobrevivió al revert**, porque no era del agrupado: el
`overflow-wrap` del renglón. Su comentario decía —y el canario lo confirmó
las dos veces— que el desborde *"es MÁS VIEJO que el agrupado"*. Un arreglo
que entra en el mismo commit que una decisión de producto tiene que poder
quedarse cuando la decisión se cae, y para eso hay que separarlos al
revertir en vez de dejar que el `git revert` decida.

### Por qué ningún test podía agarrarlo

El test que cuida el camino al Detalle **estaba puesto y estaba verde**:
afirma el `data-detalle` de la fila y el `<a class="link-detalle">` del
nombre. Los dos estaban. Es el corolario 32 corrido de lugar: allá el
atributo decía "escondeme" y el CSS no obedecía; **acá el atributo dice "soy
un link" y el CSS lo desmiente.** Un assert sobre marcado prueba que el
camino existe; no prueba que alguien pueda encontrarlo.

Confirmado con el canario: apagarle el subrayado a la regla hace caer **cero**
tests de marcado. Lo único que vio la diferencia fue el navegador.

### Las dos preguntas, y son distintas

> **¿Se puede llegar?** la contesta el marcado, y un test la cuida.
> **¿Se ve que se puede llegar?** la contesta el CSS renderizado, y hay que
> ir a mirarla.

La segunda no se deduce de la primera y no hay suite que la cubra. Se hace
cuando una pantalla saca un botón y lo reemplaza por una afordancia —el
click de la fila, el swipe, el hover—: **abrir el navegador y preguntarse qué
distingue a eso de un texto muerto.** Si la respuesta es "el cursor", en
celular no existe; si es "nada", no existe en ningún lado.

**Y el 80% era sobre el CELULAR.** Esa es la premisa que nadie midió
(corolario 25): el argumento se escribió pensando en el dedo y se aplicó a
una tabla de escritorio, donde la afordancia que lo sostenía no se ve. Un
argumento correcto sobre una población y copiado a otra.

## Corolario 87: el dueño también describe de memoria una pantalla que tiene adelante

Del 19/09, y es del dueño: *"yo dije 'un −20 agrupado y sin nombre' y era
falso — describí de memoria una pantalla que tenía adelante hace dos
horas"*.

El pedido era que Movimiento mostrara la salida desglosada por sucursal. **Y
ya lo hacía**: un renglón por sucursal, con nombre —"Armado pedido Día % BZ
−10"—. Lo que de verdad faltaba era el **número de pedido**, que es con lo
que se coteja contra la orden de compra.

**La diferencia no es de prolijidad: cambia qué se construye.** Con la
premisa tal como llegó, lo que había que hacer era partir un total agrupado.
Con la pantalla a la vista, lo que hay que hacer es agregar un dato y
reordenar. Son dos trabajos distintos, y el primero no existía.

Es el corolario 84 —una premisa del dueño sobre EL SISTEMA se verifica en el
código— con el caso que le faltaba: allá la premisa era sobre lo que el
sistema PUEDE hacer (*"eso lo puedo editar"*), acá sobre **lo que una
pantalla MUESTRA**. Las dos se verifican del mismo lado y ninguna se discute:
se miran.

**Lo accionable, y cuesta un minuto**: antes de cambiar una pantalla porque
"muestra X", **renderizarla y leer qué muestra**. Acá alcanzó con correr
`armar_extracto` con el caso y mirar la salida — dos líneas de Python antes
de escribir una sola de producción.

**Y el hallazgo se dice ANTES de construir, no en el commit.** Si la premisa
se corrige recién al explicar lo que se hizo, el que la dijo ya no puede
cambiar el pedido — y el pedido con la premisa corregida puede ser otro.

## Y un formulario adentro de un `<details>` que arranca CERRADO es el corolario 68 antes de nacer

*(El formulario del ejemplo se borró el 18/09. El hallazgo es del MECANISMO
—mirar qué CONTIENE a lo que se agrega— y no del formulario, así que se
queda. Y de paso es la mejor prueba de que un canario puede contestar sobre
algo que no era su pregunta: aquél preguntaba por una guarda.)*

Del 17/09. La pregunta de la caja quedó escrita adentro del bloque
`<details class="corregir-ficha">` de Guías R, que se titula **"Corregir la
ficha"** y arranca cerrado **cuando la guía ya tiene ficha** — que es
exactamente el caso de las que esperan su caja.

O sea: la ruta existía, respondía, tenía sus tests en verde, y para llegar
había que abrir un desplegable que dice otra cosa. Es el camino que funciona
y no se ve, encontrado **antes** de que alguien lo sufriera y no después.

**Lo que lo destapó no fue leer la plantilla**: fue un canario que dio 0
—"la pantalla ofrece completar una ANULADA"— y al ir a ver por qué no mordía
apareció que el bloque entero vivía adentro de otro `if`. El canario
preguntaba por una guarda y contestó sobre la ubicación.

**La señal, y se hace al escribir**: cuando un formulario nuevo se agrega
"al lado" de otro, mirar qué lo CONTIENE. Un `<details>`, un `@media`, un
`{% if %}` de tres pantallas más arriba: lo que decide si se ve no es dónde
se escribió sino qué lo envuelve — y en una plantilla larga eso está a
cincuenta líneas de distancia.

Y el criterio para decidir dónde va, que es el que separa las dos cosas:
**son dos operaciones distintas.** La ficha dice a qué producto fueron las
cajas; ésta, en qué caja salieron. Meterlas en el mismo desplegable las hace
ver como una sola, y la que se esconde es la que nadie fue a buscar.

## Corolario 83: un `<script>` adentro de un fragmento que llega por `innerHTML` NO SE EJECUTA, así que el partial que se lleva su cableado adentro muere ahí

Del 18/09. Este proyecto tiene una costumbre buena y escrita:
`_caja_en_origen.html` lleva su `<script>` adentro *"y no en un include
aparte que cada pantalla tenga que acordarse de poner: el que se lo olvidara
dejaría el bloque escondido para siempre —arranca `hidden`— y eso no se ve"*.
El argumento es correcto y sigue en pie.

**Tiene un caso donde se da vuelta, y es el peor posible: la pantalla que
recibe el fragmento por `innerHTML`.** `innerHTML` inserta el marcado y
**no ejecuta ningún `<script>` que venga adentro** — es del estándar, no un
bug del navegador. O sea que el partial llega entero, con su bloque, su
selector y su script, y el script no corre: el bloque se queda como nació.

Medido en el navegador, con la identidad de cada pantalla al lado para no
estar midiendo otra cosa (corolario 53):

```
                                        hidden  display   cableado   modal
comanda de UNA foto (render del server)  false   block      true      true
comanda MÚLTIPLE (innerHTML)             true    none       false     true
```

**`display: none` de verdad, no el atributo**: el efecto, no la intención
(corolario 32). Así que en la comanda múltiple el selector de "¿viene ya
armada?" **no se podía usar** — llegaba, ocupaba lugar en el DOM, mandaba su
valor vacío, y nadie lo veía nunca. Es la ruta sin botón del corolario 31 en
su variante más callada: no hay `.sql` a mano que se repita ni incidente que
alguien recuerde, porque la función no se pide — se supone.

### ARREGLADO el 18/09, y son DOS mitades que hacen falta las dos

**En la pantalla que INYECTA**: volver a crear cada `<script>` del marcado
recibido, que es lo único que los corre. Va ahí y no en el partial porque el
que escriba el próximo bloque con `<script>` adentro no tiene por qué saber
que su marcado viaja por acá.

**Y en el PARTIAL**: ser re-ejecutable, que son dos cosas y ninguna se ve
leyendo el arreglo de la otra mitad.

1. **`DOMContentLoaded` ya pasó** cuando el fragmento llega, así que un
   cableado enganchado ahí se registra y **no corre nunca**. Hay que
   preguntar `document.readyState` y llamar directo si el documento ya está.
   Sin esto, re-ejecutar el script no cambia nada — y el canario lo confirma:
   cae el mismo test que sin re-ejecutarlo.
2. **La guarda no puede ser una bandera de módulo.** `if
   (!window.__yaCablee)` deja la PRIMERA comanda perfecta y saltea los
   bloques de la segunda, con el mismo síntoma un minuto más tarde. Se marca
   BLOQUE POR BLOQUE (`[data-caja-en-origen]:not([data-cableado])`), y así
   llamarlo de más no cuesta nada.

**Medido llamando a `mostrarRevision`, que es la función de la pantalla y no
una imitación del test**: primera comanda `display block · opciones ['', '3']`,
segunda igual, y un artículo sin cajas en `display none · opciones ['']` — el
caso que tiene que seguir escondido, sin el cual un cableado que mostrara todo
pasaría igual. Los cuatro canarios (sacar la re-ejecución, volver al
`DOMContentLoaded` solo, volver a la guarda global, mostrar siempre el bloque)
hacen caer ese test y solo ése.

### Lo que decide dónde va un partial nuevo

> **Si el partial trae `<script>`, la pregunta no es qué pantalla lo usa: es
> si alguna de esas pantallas lo recibe por `innerHTML`.** Si alguna lo hace,
> el cableado va en LA PANTALLA que recibe, y el disparador tiene que ser un
> listener en `document` —no uno por elemento— porque los elementos que va a
> cuidar todavía no existen cuando el listener se registra.

Por eso el modal de "vino armada" se incluye desde las siete pantallas y no
desde `_caja_en_origen.html`, y por eso `compra_fotos_multiples.html` —que no
tiene ningún selector propio— lo trae igual: es la anfitriona del fragmento.

**Y el include de más no se sostiene solo**: lo cuida un test que compara el
conjunto ENCONTRADO contra el DECIDIDO (corolario 60), con la relación
fragmento→anfitriona escrita como dato. Falla en las dos direcciones: cuando
aparece una octava pantalla que puede marcar y no confirma, y cuando una deja
de poder marcar y se queda con el cartel colgado.

### Y el `grep` que lo encuentra no es el del script

`grep "<script>" templates/` devuelve medio repositorio. Lo que hay que
grepear es **`innerHTML =`**, que es la lista corta de lugares donde el
marcado entra sin ejecutarse — y después, para cada uno, qué partials viajan
adentro de lo que se inyecta.

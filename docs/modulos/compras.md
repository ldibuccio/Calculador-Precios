# Módulo: compras, recepción y pesaje

Movido TAL CUAL desde CLAUDE.md el 03/10 (sin reescribir). Las reglas
vigentes, en corto, están en CLAUDE.md.

## Los títulos de kilos y unidades se escriben UNA vez (28/09)

La compra 827 (palta) se cargó en Ingreso por depósito con 18 "por cajón" y
80 kilos, cuando eran 80 unidades y 18 kilos. Ahí el primer campo decía
"Contenido por cajón", y el segundo quedaba SIN título: su JS usaba
`ETIQUETAS_CONTENIDO`, que esa pantalla nunca definió, y con palta tiraba un
error. La tabla de títulos estaba copiada en ocho lugares y esa página no
tenía su copia.

Ahora la tabla vive en `core/magnitudes.py` (`ETIQUETAS_POR_CAJON`). Las
plantillas la leen con los globales `etiqueta_por_cajon` y
`unidad_de_compra`, y el JS con `window.Magnitudes`
(`templates/_unidad_al_lado.html`, que se incluye desde la barra). El mismo
parcial pone al lado de cada campo numérico la unidad que dice su título
("kg", "u", "cub."). La lee del título, así que no puede contradecirlo.

**El nulo es kilo en los tres lados**: el server, el JS y el reparto de
magnitudes. `repartir_magnitudes` comparaba `== "kilo"`, así que la
recepción de un artículo sin la unidad declarada guardaba los kilos en la
columna del conteo.

**Y Corregir recepción no podía corregir una compra con las dos
magnitudes**: mandaba una sola, y la escritura exige las dos. Por eso la 827
hubo que borrarla en vez de darla vuelta. Desde el 28/09 tiene el segundo
campo, con la misma validación que Recepción.

**Un aviso que detecte kilos y unidades cargados al revés NO VA** (dueño,
28/09). Alcanza con los títulos que nombran la unidad y la unidad al lado del
número. Es una decisión cerrada, no un pendiente: medido en Frutamax, 31
compras con las dos magnitudes (3 artículos) y 0 cruzadas.

El sufijo va solo en los formularios marcados con `data-unidad-al-lado`
(las pantallas de carga y de recepción). Armar Pedido ya dibuja su unidad, y
un segundo sufijo la desbordaba 36px.

Lo cuida `tests/test_titulos_de_magnitudes.py`: en el navegador, cada campo
de las tres pantallas dice su unidad y no hay errores de JS. Otro test falla
si alguna plantilla vuelve a tener su propia copia de la tabla.

## Buscar compras: Detalle y Editar son UNA pantalla (02/10, dueño)

- **En la lista hay un solo "Detalle"**: Editar salió del menú de acciones
  (quedan Detalle, Vino armada y Eliminar). El Detalle se lee, y adentro
  tiene un solo botón "Editar".
- **Editar es la pantalla de siempre** (`/compras/{id}/editar`, sin clave):
  artículo, cajones, contenido por cajón, la segunda magnitud, importe,
  seña, tipo de retiro, "viene armada" y agregar artículo, con los mismos
  bloqueos por estado de antes. Abajo cuelga la puerta a lo de Gerencia
  (`/gerencia/compras/{id}/editar`, pide su clave): las dos fechas,
  corregir recepción, deshacerla, cambiar el proveedor, desmarcar "vino
  armada" y eliminar. **No cambió ningún permiso.**
- Los filtros de la búsqueda viajan Buscar → Detalle → Editar, y Guardar
  vuelve al Detalle; su Volver vuelve a la misma búsqueda.

## Reingreso por rechazo: el motivo viene escrito (02/10, dueño)

"Rechazo por calidad", editable o borrable. Vacío se comporta como siempre
(obligatorio), y en un reintento vuelve lo que se mandó, aunque sea vacío.

## Buscar compras: la SEÑA (28/09, dueño)

La pantalla, el Excel y el PDF llevan una columna "Seña" al lado del
importe, vacía si la compra no dejó seña, y el total al pie. Las tres salen
de `texto_sena` y `total_de_senas` (core/exportar_compras.py). **La seña es
por cajón, igual que el importe**, así que el total no es la suma de la
columna: es seña × cajones, y el rótulo lo dice. **El total de importes va
al lado** (dueño, 28/09: "para ver cuánta plata hay en lo que filtraste"),
con la misma cuenta, importe × cajones, y una cola que dice cuántas compras
sin precio no suman: sin ella, un total al que le faltan compras se lee
igual de cerrado. En celular la columna nueva corrió las reglas `td:nth-child`, y un
test compara cuántos `<th>` hay contra cuántas reglas.

## UN PROVEEDOR, VARIOS PUESTOS (27/09)

Decisión del dueño: FRUTAMAX S.R.L. es el N09P41 **y** el N09P39, y es un solo
proveedor. Desde `codigos_1` a `codigos_4` (corridas en las dos bases):

- **`proveedores.codigo_puesto` sigue siendo el PRINCIPAL**, y los otros viven
  en `proveedores_codigos`. La base no deja que un código sea de dos
  proveedores, sumando las dos tablas (trigger `codigo_de_puesto_unico`, 23505).
- **Una compra que llega por un alternativo se carga en ese proveedor**, sin
  crear otro y **sin cambiarle el nombre**. La búsqueda está escrita una vez
  (`_SQL_PROVEEDOR_POR_CODIGO`) y la usan las dos puertas. "La última
  corrección manda" sigue valiendo, pero solo para el código principal.
- **`compras.codigo_llegada` es el puesto por el que llegó.** Lo escriben todos
  los caminos de carga (sin default, así que olvidarlo es un TypeError, y un
  test de `ast` lo mira porque la suite parchea `crear_compra`). En
  `/compras/nueva`, que es de dos pasos, el código viaja en la URL y en un
  campo escondido. El ingreso directo es de UNA pantalla desde el 30/09 y
  guarda el código tipeado; "Guardar y agregar otro" vuelve con ese puesto
  precargado (`?codigo=`). Cambiar el proveedor de una compra le pone el
  principal del nuevo. Lo muestran Logística, Recepción, Compras pendientes,
  el Detalle y los Excel. **Una guía junta los dos puestos**, porque es una por
  proveedor y día, así que su título los nombra a los dos y Logística dice de
  cuál es cada renglón.
- **El alta a mano pregunta con un modal** si el nombre plegado coincide con uno
  que ya está, o si uno contiene al otro: "es el mismo" le suma el puesto, "es
  otro" lo carga igual. Avisa, no bloquea. La guarda va en el POST.

**El segundo par, el mismo día: DON LAZZARO (L02P42) y PRODUCTOS DON LAZZARO
(L02P44).** El plegado sacaba solo "SRL", "SA", "SAS" y "SH", así que ese par no
se veía. Desde ahí también saca PRODUCTOS, HNOS, HERMANOS y CIA, siempre como
palabra entera, y avisa cuando un nombre plegado contiene al otro, con un mínimo
de 4 letras (`MINIMO_PARA_CONTENER`) para que "SUR" no esté adentro de medio
padrón. La regla es `son_parecidos`. La fusión es `db/lazzaro_1` y `lazzaro_2`,
que solo actúan si la base tiene N09P39 como código alternativo, o sea en
Frutamax: en Palmala no hacen nada aunque estén los mismos nombres. Corridas
en las dos bases el 27/09.

**Desde el 27/09 el tercer par no necesita migración: Gerencia → "Juntar dos
proveedores"** (`/gerencia/proveedores/juntar`). La lógica vive UNA vez, en
`juntar_proveedores` (app/db.py), con las mismas guardas que las migraciones:
guías del mismo día, marca con el mismo nombre y fotos de vacíos con cajones en
los dos frenan con el texto de qué arreglar. La pantalla pregunta con
`resumen_para_juntar_proveedores`, la misma consulta que usa el POST, así que el
botón aparece solo donde la escritura acepta. Todo en una transacción.

- **Las marcas se mueven sin tocar las FK compuestas**: marcas y los cinco
  lugares que las nombran van en UNA sentencia (CTE), y ahí la FK se chequea al
  final. Conservan su id. En dos sentencias la primera rebota (medido).
- **`recepciones` y `aprendizaje_proveedores`** apuntan a `proveedores` en las
  bases reales, y desde el 28/09 (dueño) también están en
  `db/esquema_completo.sql`, copiadas de `db/schema.sql`. El código no las usa,
  pero la fusión las mueve, para que la primera fila que alguien les escriba no
  haga rebotar el borrado. `recepciones` apunta también a `compras`, y por eso
  es el quinto control de `_lo_que_cuelga`.
- **Lo cuida un test que lee `pg_constraint`** contra el esquema real y compara
  las FK a `proveedores` ENCONTRADAS contra `TABLAS_QUE_APUNTAN_A_PROVEEDORES`.
  Una tabla nueva con FK a proveedores lo rompe hasta que alguien decida cómo se
  junta. Si igual se escapa, el DELETE del final rebota y no se escribe nada.

## El pesaje: la foto no documenta el pesaje, lo DISPARA

Del 12/09, y va como sección porque es un hecho del sistema que cambia lo
que vale una función, no la trampa de un día.

**El número, y no se puede citar sin su control al lado**, porque el 63%
solo significa algo pegado al 8%:

| | recepciones | tocadas | |
|---|---|---|---|
| **Antes de la foto** (Frutamax, hasta el 09/09) | 367 | 35 | **9,5%** |
| **En la ventana, CON foto** (09 al 12/09) | 62 | 39 | **63%** |
| **En la ventana, SIN foto** (mismos días) | 12 | 1 | **8%** |

"Tocada" es que alguien cambió el número precargado al recepcionar; "sin
tocar" es apretar Recibir con el estimado puesto, que graba *pesó
exactamente lo que se había cargado*.

**La tercera fila es la que decide, y por eso la medición se hizo dos
veces.** El primer corte —60 días, con foto contra sin foto— comparaba la
función nueva contra el pasado: dos poblaciones de épocas distintas. Acotado
a la ventana quedaba el otro confundido: que hubiera cambiado *el período* y
no la foto. **Las 12 sin foto de esos mismos días dan 8%, casi idéntico al
9,5% de antes**: el período no cambió. Cambió quién saca la foto.

Y `foto_despues = 0`: ninguna foto se subió después de recepcionar, así que
todas son previas al número. La evidencia es limpia.

**Desde el 29/09 hay una puerta para subirlas DESPUÉS** (dueño): el detalle
de la compra tiene "Agregar foto de pesada", que acepta varias y las guarda
en `fotos_recepcion` con su `creado_en`. También se puede borrar una, con
confirmación. No toca ningún número de la compra. Dos consecuencias:
- `foto_despues` deja de ser cero por construcción. Si se vuelve a medir el
  efecto de la foto, las de después se separan comparando `creado_en` contra
  `procesada_el`.
- `recepciones_sin_pesaje` cuenta una foto subida tarde como evidencia, y la
  recepción sale de la alerta. Es lo que se quiere: el aviso existe para que
  alguien mire lo que se está yendo, y subir la foto es mirarlo.

**Y el ingreso directo de Depósito también las sube, desde el 30/09** (dueño).
Recepción ya las subía desde el 09/09; lo que no tenía fotos era el ingreso
directo, que nace recibido y no pasa por Recepción. `/deposito/ingresar` es
UNA pantalla desde ese día (proveedor arriba, mercadería abajo, un Guardar,
como la carga manual de Compras; la de elegir el proveedor se borró). Tiene
"Agregar foto de pesada": varias, en miniatura, y se borran con confirmación
antes de guardar. No son obligatorias. Van a `fotos_recepcion` en la MISMA
transacción que la compra (`crear_compra(..., fotos_pesada=)`): si la compra
rebota, se borran del Storage y no queda ninguna fila. "Cargado hoy" muestra
las de cada renglón, vengan de donde vengan. Un archivo que no es foto frena
todo antes de escribir. Las fotos se leen del formulario a mano: el parámetro
`list[UploadFile]` rechazaba con 422 un campo de archivo vacío. El modal de
nombres parecidos de Compras → Proveedores también está ahí: la pantalla lo
pregunta ANTES de enviar (`/deposito/ingresar/parecidos`), porque un
formulario que vuelve del servidor no puede traer las fotos, y el POST lo
vuelve a preguntar. Lo cuida `tests/test_ingreso_directo_una_pantalla.py`.

Cada miniatura pide su foto por id (`/deposito/recepcion/{compra}/foto-balanza/{foto}/ver`).
La ruta sin id devuelve la última, y hasta el 29/09 el detalle y Corregir
recepción la usaban en el loop: con varias fotos, todas se veían iguales.

### La conclusión es la CONTRARIA a la que teníamos dos turnos antes

Con el 82% sin tocar de `kilos_4` habíamos concluido *"Depósito no pesa"*.
Es falso, y el error era de alcance: **las 343 sin tocar y sin foto son de
antes de que la foto existiera.** No eran operarios que no pesan: era un
período en el que no había nada que empujara a pesar.

Es la familia del corolario 24 —una población que no vota— con otra ropa: no
es una base parada, es **una función que todavía no existía**. Y el aviso
para la próxima es el mismo: antes de leer una tasa histórica como un hábito,
preguntarse desde cuándo existe lo que se está midiendo.

### Lo que cambia, y es de diseño

**La foto pasó de "prueba de que se pesó" a "lo que hace que se pese".** Hoy
la pantalla avisa y no traba: el botón dice que falta la foto y deja recibir
igual (*"el camión no se para por una foto"*, y sigue siendo verdad).

Con este número, ese cartel está haciendo más que documentar — **está
produciendo el pesaje**. Eso cambia cuánto vale hacerla obligatoria, que
antes era una discusión sobre auditoría y ahora es sobre la calidad del dato
de entrada.

**NO SE CAMBIÓ NADA**, por pedido, y la razón es buena: cuatro días y 62
casos es poco para mover una traba que puede dejar un camión esperando. Pero
queda anotado que el argumento ya no es el mismo.

**Y EL 18/09 SE CONSTRUYÓ EL ESCALÓN DEL MEDIO**: la alerta
`recepciones_sin_pesaje`, que cuenta las recepciones **sin ninguna evidencia
de pesaje** — ni foto de balanza ni número corregido. Las dos condiciones a
la vez y no un `OR`: tocar el número es pesaje aunque no haya foto, y una
foto con el número sin tocar puede ser *"pesé y dio 16"*. Lo que no tiene
ninguna defensa es el cruce.

**Lo que esa cuenta NO puede hacer, y hay que decirlo cada vez**: distinguir
"lo pesaron y dio exactamente el estimado" de "lo aceptaron sin mirar". Son
indistinguibles en la base y siempre lo van a ser. Por eso la alerta cuenta
el conjunto más chico del que se puede afirmar algo.

**Y la ventana es de DOS días, la más corta de todas**, contra los siete de
las otras dos de compras. No es un capricho de simetría: **las otras apuntan
a un RECLAMO al proveedor, que sobrevive una semana; ésta apunta a mirar algo
que se está yendo.** Una recepción de anteayer todavía se reconstruye —el
cajón puede estar en el piso, el que la recibió se acuerda— y una de la
semana pasada no. Con siete días el número sería ~19 por la medición del
12/09, que es el tamaño exacto del aviso que este proyecto ya decidió no
construir una vez; con dos son ~5. Se confirmó con `db/pesaje_1_cuantas_sin_evidencia.sql` el
18/09 —Frutamax dio 6— y el criterio con que se leyó queda escrito porque es
lo que decide la próxima: **si hubiera dado mucho más, lo que hay que mover no
es el umbral sino la unidad.**

#### CONFIRMADO el 18/09, y Palmala dio el TRIPLE (y votó)

```
FRUTAMAX   6 de 44 en 2d (14%) ·  18 de 117 en 7d (15%) · población 90d 526
PALMALA   16 de 40 en 2d (40%) ·  35 de  70 en 7d (50%) · población 90d 240
```

La predicción escrita decía *"con dos días son ~5"* y Frutamax dio 6: la
ventana queda. **Palmala VOTÓ** —70 recepciones en 7 días, 240 en 90— y es
el caso que corrigió el *"Palmala no vota"* escrito como atributo de la base.

**EL NÚMERO QUE SE CITA ES EL DE 7 DÍAS, no el de 2.** El 40% sale de n=40 y
su error estándar es ±7,7 puntos: ese 40 vive entre 25% y 55%, así que "cuatro
de cada diez" es más preciso de lo que el dato aguanta. El de 7 días —**la
mitad de las recepciones**, n=70— es el que se sostiene, y encima es peor.

**Y la razón entre las dos bases es 2,9× (2d) y 3,3× (7d), no 2×.** Es el
corolario 15 otra vez —la glosa al contar un resultado se vuelve un hecho— y
acá el número iba a ir a una conversación con el galpón.

**La forma más limpia del contraste no es ninguna de esas dos**: recepciones
con LAS DOS evidencias, que es lo que se quiere que pase.

```
FRUTAMAX  72 de 117 limpias = 62%
PALMALA   10 de  70 limpias = 14%
```

#### Y `solo_sin_foto` NO ERA "solo": era el TOTAL

Las dos columnas se llamaban `solo_*` y contaban **todas** las de cada
condición, las del cruce incluidas. Leídas como grupos aparte, la resta sale
mal — y salió mal el mismo día: se leyó *"solo sin foto 19, sin evidencia 18,
casi iguales"* como dos poblaciones parecidas, cuando lo que pasa es que
**18 de esas 19 SON las mismas.** En Frutamax hay UNA sola recepción sin foto
donde alguien igual tocó el número.

Es el corolario 8 —el nombre lleva el alcance— adentro de una consulta de
diagnóstico, que es donde más caro sale: **el que la corre no va a leer el
`filter`, va a leer el encabezado de la columna.** Renombradas a `sin_foto_7d`
y `sin_tocar_7d`, y con `CON_UN_OR_habria_disparado_7d` calculada en la
consulta en vez de de cabeza.

**Y ese OR es la confirmación más dura del cruce**: en Palmala habría
disparado sobre **60 de 70 recepciones, el 86%**. Es *más hallazgos que
población condena la heurística* en su forma más limpia — un criterio que
marca seis de cada siete no está contando lo raro, está contando la norma.

#### La UNIDAD no se mueve todavía, y lo que lo decide es lo que pase después

La regla escrita dice que un número grande manda a mover la unidad, y 16 en
dos días lo parece. **No aplica, y la razón es de forma**: esta alerta
devuelve UNA fila con una magnitud, no dieciséis avisos. El caso que aquella
regla rechazó era una lista de veintiún ítems para atender de a uno.

Lo que sí es cierto es que en Palmala **los 16 tienen UNA causa** —el dueño
lo llamó *"un hábito, no un olvido"*— y una lista de 16 con una sola causa no
se trabaja ítem por ítem: se arregla la causa una vez. Pero eso no rompe la
alerta: **la alerta hizo exactamente su trabajo**, que era hacer visible el
hábito.

**El test, y hay que dejarlo escrito porque es la única forma de saberlo**:
si el número BAJA después de la conversación con el depósito, la unidad
estaba bien y la alerta sirvió. **Si no baja, entonces sí la unidad está mal**
— sería una causa que un conteo por recepción no puede mover, y ahí el aviso
tiene que pasar a la unidad de la causa.

#### Y EL 19/09 LA MITAD DE PALMALA DEJÓ DE VALER, por el corolario 88

El dueño cerró ese día que **Palmala no está funcionando y no vota en nada**.
Eso no borra la medición de arriba —se corrió, dio lo que dio— pero **sí
invalida la conclusión que se le colgó**, y por el mecanismo más incómodo:
*"sin ninguna evidencia de pesaje"* es una medición de AUSENCIA, y una base
parada las contesta casi todas (corolario 88). El 40% y el 50% de Palmala son
exactamente de la forma que ese corolario describe, y el *"un hábito, no un
olvido"* del párrafo de arriba está dicho sobre un depósito que dejó de
trabajar en el medio.

**Lo que se sostiene es Frutamax: 6 de 44 en dos días, 18 de 117 en siete, y
72 de 117 limpias.** El test escrito arriba —si el número baja, la unidad
estaba bien— se corre contra ésos. **La razón 2,9×/3,3× entre bases NO SE
CITA MÁS**: comparaba una base viva contra el residuo de una parada.

**Y es doblemente una lección**, porque el testigo de esa medición estaba
puesto, trajo `recepciones_7d 70` y `90d 240`, y **hizo votar a la base que
no tenía que votar**. Ese testigo no mintió: contestó bien la pregunta de si
había población. La que no contestó —y ningún testigo puede— es si esa
población seguía viva.
### Una DECISIÓN y una cosa anotada, y no son lo mismo

El título de esta sección decía *"lo que queda ANOTADO Y NO HECHO"* y
listaba dos. **Desde el 22/09 la primera es una decisión cerrada**, y
dejarlas bajo el mismo rótulo es lo que este archivo se pasa advirtiendo:
un pendiente se relee a los seis meses como algo que todavía hay que
hacer, y una decisión releída así manda a rehacer lo que ya se decidió
que no va.


1. ~~Volver a correr `kilos_4` el 25/09.~~ **RETIRADO POR EL DUEÑO EL 22/09,
   y es una DECISIÓN y no un pendiente que se venza.** Las dos preguntas que
   esa consulta medía están las dos cerradas, cada una por su lado:

   > **La referencia NO SE AJUSTA POR MEDICIÓN**, nunca. Se compra siempre en
   > distintos kilajes, y `contenido_referencia` es una SUGERENCIA para cargar
   > compras — no tiene más importancia que ésa.
   >
   > **Y la evidencia del pesaje es LA FOTO.** Lo que importa es que la saquen,
   > y para eso ya está la alerta `recepciones_sin_pesaje`. No hace falta una
   > segunda medición que diga lo mismo peor.

   **Lo que eso cierra, y conviene leerlo junto**: el promedio de
   `contenido_por_cajon_real` se iba a usar para decidir si mover una
   referencia. Sin esa decisión, el número no alimenta ninguna otra — así que
   no es que la medición sea mala: **es que su resultado no tiene a dónde
   ir**, que es la única razón que da de baja una consulta sin discutirle los
   números.

   **Y la forma de la decisión es la que hay que reconocer**: no se cerró
   midiendo mejor. Se cerró porque el dueño dijo qué es `contenido_referencia`
   —una sugerencia, no un parámetro— y con eso la pregunta "¿está bien
   cargada?" deja de tener consecuencia. Es el corolario 29 con el signo
   bueno: la pregunta *"¿para qué querés este número?"* borra el trabajo antes
   de hacerlo, y acá la contestó él sin que hubiera que preguntarla.

   La consulta queda en `db/`, **marcada RETIRADA en su encabezado** — ahí y
   no solo acá, porque el que la abra dentro de seis meses va a leer el
   archivo y no este documento.
2. **La explicación que los datos NO pueden descartar**: que el operario
   saque la foto justo en las cargas que ya le generaban duda. Ahí la foto no
   dispararía nada — sería un *marcador* de sospecha, y el que corrige es el
   mismo que ya iba a corregir. Ninguna consulta lo separa, porque quién saca
   la foto lo elige él. **Lo separa hacerla obligatoria unos días**: sin
   elección no hay selección.

## `compras.importe` no dice CUÁNDO ni POR DÓNDE — y "quién" no es la deuda (19/09)

Del 19/09, y es del dueño: *"El día que un precio no cierre contra lo que el
proveedor dice, no hay forma de reconstruir si lo puso Gerencia al cargar,
Comercial al negociar, o alguien de más. Es el mismo problema que resolvimos
ayer con `cantidad_original` en el renglón del pedido, y por la misma razón."*

**La falta es real.** `compras` tiene 29 columnas y el importe es un número
solo. `cargado_el` es de la COMPRA y no del precio: una compra que nació sin
importe y se completó tres días después lo lleva igual, con la fecha del alta.

**Y son TRES escrituras**, enumeradas con `ast` sobre los llamadores y no
leídas de memoria:

```
el ALTA        crear_compra / crear_compras_de_comanda  ->  _insertar_compra_con_guia   INSERT
la EDICIÓN     POST /compras/{id}/editar                ->  actualizar_precio_compra    UPDATE
el PENDIENTE   POST /compras/pendientes[/guardar-todos]  ->  actualizar_importe_compra   UPDATE
```

Las tres dejan **exactamente la misma fila**. Un importe puesto al recibir y
uno renegociado una semana más tarde son indistinguibles, y eso es lo que hay
que arreglar.

### Pero "QUIÉN" no se puede, y no es una deuda: es una decisión ESCRITA DOS VECES

**Este sistema no tiene usuarios**, y no es un olvido — está dicho en el
esquema, en las dos columnas de la familia que el dueño nombró:

> `controlado_el`: *"No guarda quien: el sistema no tiene usuarios."*
> `agregado_a_mano_el`: *"Guarda CUANDO y nada mas, igual que controlado_el:
> el sistema no tiene usuarios, asi que un quien seria un campo sin
> consecuencia."*

Y **no hay tabla de operarios**: existió el 01 y el 02/09 para la salida de
escape del freno del reproceso, y la borró `db/sacar_excepcion_del_freno.sql`
con su comentario explicando por qué. Medido sobre el esquema entero: **cero**
columnas `usuario_id`, `creado_por`, `cargado_por` o `actor`.

Un `escrito_por` sería el campo sin consecuencia de más arriba en su forma más
pura: **no hay de dónde sacarlo**, así que quedaría en NULL para siempre o
habría que pedirle a alguien que se nombre a sí mismo.

**Las puertas son de SECTOR, no de persona**, y encima la pregunta tal como
está formulada tiene un error que conviene tener escrito: **Comercial no
escribe `compras.importe` por ninguna puerta.** Los tres caminos de arriba
viven bajo `/compras`, y el retroactivo de Gerencia lo escribe también,
desde su propio prefijo. O sea que las puertas por las que puede entrar un
importe son **dos, Compras y Gerencia**, y la renegociación —lo que
el dueño llama "Comercial"— entra por la de Compras. Comercial pone precios de
VENTA, que viven en `precios_venta_historial` y sí tienen historial.

### El paralelo con `cantidad_original` es de FAMILIA, y el arreglo NO se copia

*Buscar la otra copia es obligatorio; copiarle el arreglo, no.* Las dos
columnas son de la misma familia —existen para reconstruir un desvío contra un
documento de AFUERA— y **contestan preguntas distintas**:

| | qué guarda | qué pregunta contesta |
|---|---|---|
| `cantidad_original` | el VALOR viejo | la OC dice 5 y el sistema 8, ¿qué decía la comanda? |
| lo que falta acá | el CAMINO y el MOMENTO | el proveedor dice $X y el sistema $Y, ¿esto se cargó al recibir o se renegoció? |

Y el comment de `cantidad_original` dice **textual** que guarda el valor *"y no
un timestamp a proposito"*, porque la pregunta que aparece la contesta el
número viejo y no la hora. **Acá es al revés**: el importe viejo no contesta
nada —si se renegoció, el viejo es justamente el que ya no vale— y lo que falta
es cuándo y por dónde entró el que está puesto.

Copiarle el diseño —un `importe_original`— construiría la respuesta a la
pregunta que acá no se hace. Es el mismo criterio con que el Cotejo de vacíos
se quedó midiendo contra la foto cuando el de stock dejó de hacerlo.

### CONSTRUIDO el 20/09: `importe_puesto_el` + `importe_origen`

Las dos columnas se migraron el 19/09 (`db/importe_1_cuando_y_por_donde.sql`,
verificada `2 · 3` en las dos bases) y el 20/09 quedaron cableadas en los tres
escritores. Son **derivadas del camino, no tipeadas por nadie** — que es lo
único que las vuelve inmunes al campo que se deja de llenar: los tres
escritores saben cuál son y ninguna pantalla pregunta nada.

**LO QUE DECIDIÓ EL DISEÑO, y no estaba previsto: el sello solo va SI EL
NÚMERO CAMBIÓ.** La pantalla de Editar Compra llama a
`actualizar_precio_compra` **en cada guardado, toque el precio o no** — está a
la vista en el POST, `if not precio_bloqueado:` sin mirar si el importe se
movió—. Sin esa guarda, corregir los cajones de una compra le fecharía el
precio como renegociado hoy: la columna mentiría **justo en el caso para el
que existe**, y sin que nada se vea raro en ninguna pantalla.

No es un requisito inventado (corolario 81): es lo que el comment de la
columna ya promete —*"CUANDO se escribio el importe que la fila tiene HOY"*—.
Si el número no cambió, la respuesta honesta es la fecha vieja.

Se resuelve **adentro del mismo UPDATE**, sin leer la fila antes: en Postgres
una columna nombrada a la derecha de un `SET` vale lo VIEJO, así que
`importe IS NOT DISTINCT FROM %s` compara lo que hay contra lo que llega en
una sola sentencia y sin ventana entre el SELECT y el UPDATE.

**Y si el importe se BORRA, el par vuelve a NULL.** Un *"puesto el 19/09 por
edición"* sobre una fila sin precio afirma algo que no pasó — es el `{% else %}`
que dice de más, en una columna.

**El ALTA se escribe distinto A PROPÓSITO**, y conviene saberlo antes de
"unificarlo": es una fila recién insertada, así que no tiene un valor viejo
contra el cual comparar. Va en un `UPDATE` propio **después** del `if/elif/else`
de las tres ramas del INSERT y no adentro de las tres listas, por el mismo
argumento que `ficha_en_origen_id`: una columna repetida en tres ramas son tres
lugares de los que una CUARTA se puede olvidar, y olvidarla no falla —deja el
par en NULL, que se ve igual que una compra nacida sin precio—. Afuera del
`if`, corre para todas por construcción.

**Las seis formas, corridas contra `db/esquema_completo.sql`** (no leídas):

```
1. ALTA con precio                       SELLADO   alta        50000
2. ALTA sin precio                       NULL      None        None
3. PENDIENTE completa esa misma          SELLADO   pendiente   33000
4. EDICION con el MISMO numero           quieto    alta        50000   <- el que decide
5. EDICION con OTRO numero               SE MOVIO  edicion     61000
6. EDICION que BORRA el precio           NULL      None        None
```

**Lo que lo cuida**, en `tests/test_sello_del_importe.py`, y son dos clases de
evidencia que no se reemplazan: los seis casos de arriba corren contra Postgres
de verdad —lo único que puede ver que el SQL PARSEA y que el CHECK acepta lo
que el código escribe (corolario 89)—, y tres estructurales miran lo que
ninguna corrida puede ver: que un CUARTO escritor que aparezca mañana también
selle. Ése enumera con `ast` quién escribe `compras.importe` y lo compara
contra el conjunto DECIDIDO, así que falla en las dos direcciones.

**Y la lista de orígenes se LEE del `.sql`, no se copia**: una copiada envejece
en silencio, y cada dirección falla distinto — un origen que el CHECK no acepta
revienta el día que alguien use ese camino, y uno que el CHECK acepta y el
código no escribe manda a buscar filas que no existen.

**Lo que NO hace, y es correcto**: las filas viejas quedan sin rastro. Deducir
de dónde salió un importe ya escrito sería inventarlo (corolario 20), así que
`CON_precio_SIN_origen` va a seguir contando las 625 para siempre — y **ése es
el número esperado, no una deuda**. Baja solo en el sentido de que las nuevas
nacen con origen.

#### Y el corolario que salió de cablearlo: `call_args_list[-1]` ancla en una POSICIÓN

Tres tests de `crear_compra` afirmaban sobre el INSERT leyendo
`cursor.execute.call_args_list[-1]`. Desde que el alta sella con un UPDATE
posterior, `[-1]` es ese UPDATE: los tres pasaron a mirar otra cosa y cayeron
diciendo que el INSERT no tenía `'pendiente', 'pendiente'`.

**Y el archivo ya tenía el helper que lo evita, con la razón escrita adentro**:
`_sql_y_parametros_que_contienen` dice textual que buscar por posición *"hace
que cualquier sentencia nueva rompa tests que no tienen nada que ver"*. O sea
que la costumbre correcta estaba dicha, en el mismo archivo, y **quedan 16 tests
más apoyados en `[-1]`** — ninguno de ellos sobre `crear_compra`, verificado con
`ast`, así que este cambio no los tocó. Es el corolario 38 otra vez: una
costumbre no se hereda por estar escrita en un lugar; se hereda cuando algo la
exige.

# Módulo: qué comprar hoy (decisiones)

Movido TAL CUAL desde CLAUDE.md el 03/10 (sin reescribir). Las reglas
vigentes, en corto, están en CLAUDE.md.

## QUÉ COMPRAR HOY: las decisiones del 22 y 23/09, con su razón

El diseño completo vive en `docs/que_comprar_hoy.md`. Acá van las decisiones
que **no se reabren** y los mecanismos que costaron encontrar, que es lo que
este archivo guarda.

**Las seis cerradas, del dueño, con fecha (23/09):**

1. **Un solo margen, el de la carga.** El del Paso 2 **se va, no queda en
   cero.** Y (23/09) **va SOLO sobre lo que el promedio propone**: lo
   corregido y lo de "a mano" ya es lo que se compra, entra tal cual, y en
   "a mano" la pantalla no muestra el campo. La regla vive una vez
   (`lo_que_pide_la_carga`) y la llaman la carga y el listado.
2. **La carga es contra ARTÍCULOS DE COMPRA, no contra fichas.** *"Yo compro
   tomate, no 'el tomate de Día'."*
3. **El archivo no se guarda.** Es una herramienta para tipear más rápido; lo
   que vale es lo revisado.
4. **El promedio son los últimos 6 pedidos ANTERIORES AL DÍA DE CARGA**,
   divisor 6.
5. **Cargas desde ayer en adelante**; una ya usada se muestra marcada y se
   puede volver a sumar.
6. **El kilaje del Mercado vive en el Paso 2 y es editable.**
   **Y los DÍAS de la carga (23/09) van igual que el margen**: multiplican
   SOLO lo que el promedio propone, en días enteros, y viven en la misma
   regla (`lo_que_pide_la_carga`). Lo tipeado ya es lo que se compra.
7. **El listado está atado al momento de SALIR, no al reloj.** El botón
   "Salgo a comprar" guarda la foto del stock; "Compré" es lo cargado desde
   ahí, "En camino" lo cargado en los 3 días antes que no había llegado, y las
   pendientes más viejas van a un aviso sin sumarse. Uno solo abierto.
   Detalle en `docs/que_comprar_hoy.md`.

   **Y el listado es DEL DÍA en que se abrió (dueño, 02/10)**: "al abrir no
   puede haber NADA tildado, ni por lo guardado ayer. Tilda solo Lionel". Uno
   abierto otro día no cuenta al entrar —ni sus cargas, ni su foto, ni su
   salida— y el próximo guardado lo cierra y abre uno nuevo, en la misma
   transacción (`guardar_borrador_de_compra`). El GET no escribe. El
   formulario va con `autocomplete="off"`. Pasó en Frutamax: el listado del
   23/09 siguió abierto nueve días con la carga 28 tildada y la foto del 29/09
   congelada, y por eso el stock no cambiaba al cargar compras. Esto da vuelta
   lo del 23/09 ("sea del día que sea"): un listado armado a las 22 para salir
   a las 4 ya no sobrevive a la medianoche. Lo cuida
   `tests/test_que_comprar_granny_ombligo.py`, contra Postgres.

   **El stock es del ARTÍCULO, no del cliente (dueño, 28/09)**: los sueltos
   más TODAS las cajas armadas, de cualquier ficha y cualquier cliente; la
   segunda no suma. Hasta ese día contaban solo las cajas de los clientes de
   las cargas tildadas. En camino tampoco filtra por cliente, así que las dos
   puntas miran igual.

   **Antes de salir, el stock es el de ahora, en gris** y con "provisorio, se
   congela al salir"; la cuenta ya lo usa. "Salgo a comprar" va arriba de
   todo, y después de salir arriba dice de cuándo es la foto. El PDF dice
   "stock provisorio" hasta que se sale.

   **Nunca "no se puede saber" cuando hay bultos (dueño, 02/10).** Los
   bultos son los de la resta (los que hay), y los kilos salen de las compras
   con restante; si el reparto no cierra, se ESTIMAN con la compra más nueva
   que queda o la última recibida, y la pantalla y el PDF dicen "kilos
   estimados" (`_sueltos_en_magnitud`). Una caja de ficha sin contenido usa
   el mismo contenido. Hasta ese día la pantalla decía "hay cajones sueltos
   sin contenido declarado", y era falso: en Granny el 17/09 se armaron 25
   con 14 cargados (11 sin lote) y las compras 884 y 915 quedaban con 14
   contra 5 reales; en Ombligo quedaba un lote de la guía R 598. Todas las
   compras tenían su contenido; lo que no cerraba era el reparto. Era así
   desde v941 (21/09), y el cartel desde v1017. Sin ninguna compra desde el
   corte no hay kilos: se muestran los bultos y "kilos sin dato".
   **La marca "estimado" no se guarda al salir** (la foto no tiene columna,
   y se dejó sin migración): después de "Salgo a comprar" los kilos quedan
   congelados sin la aclaración.

8. **Tildar no recalcula solo (28/09)**: el listado sale de lo GUARDADO.
   "Actualizar" es el mismo guardado que el Guardar del pie, puesto arriba
   de los tildes, y "Exportar" (se llamaba "Sacar PDF") guarda primero y redirige a
   `/compras/que-comprar/pdf`, así sale lo tildado en ese momento. El PDF usa
   las mismas filas, y cómo se dice cada celda está escrito dos veces
   (`textos_de_la_fila` y la plantilla). Lo que las mantiene iguales es un
   test que las compara celda por celda.
   **En el papel, el cero y lo que no se sabe van EN BLANCO** (dueño, 28/09):
   el listado se completa a mano en el Mercado, y un espacio se llena con la
   lapicera y un cero impreso no. Lo hace `para_el_papel`, DESPUÉS de
   `textos_de_la_fila`, así la comparación con la pantalla no se toca.

9. **Los bultos que se muestran van enteros (28/09)**: "Piden bultos" y el
   stock en bultos se redondean al entero más cercano, con medio para
   arriba (`bultos_para_mostrar`: 11,4 da 11 y 36,5 da 37). El navegador
   usa `Math.round`, que redondea igual. La cuenta sigue en kilos, y "A
   comprar" y "Falta" siguen para arriba (decisión del 21/09).

### El `?error=` que se escribe y nadie lee es un error mudo

Del 23/09. El POST de Qué comprar hoy redirigía a `?error=guardar` y a
`?error=cerrar` desde el primer día, y **el GET nunca leyó ese parámetro**: un
guardado que fallaba volvía a la pantalla como si hubiera salido bien. Con la
foto del stock se vuelve caro —el comprador sale al Mercado creyendo que el
stock quedó fijo—, así que el GET ahora lo traduce a un aviso.

**La señal, y se busca con un `grep`**: un `?error=` en un `RedirectResponse`
es la mitad de un mensaje. La otra mitad es un `query_params.get("error")` en
la ruta de destino, y si no está, el error existe y no lo ve nadie — la
familia de *la ausencia de error no es confirmación*, del lado de la pantalla.

### Un margen por CARGA, y la razón es que dos márgenes se MULTIPLICAN

Decisión del dueño, y la escribió él mismo antes de que se la propusiera:
*"Si los dos se multiplican, termino comprando 32% de más sin darme cuenta."*

**20% y 10% son 32%, y esa cuenta nadie la hace con el pulgar.** No es que el
segundo margen esté mal calculado: es que el resultado de dos porcentajes
compuestos **no se parece a ninguno de los dos números que están en la
pantalla**, así que no hay nada que se vea raro. Es la familia del corolario
74 —dos respuestas verdaderas que nadie pone al lado— con la vuelta de que
acá las dos se multiplican en silencio en vez de contradecirse.

**Y va en la CARGA y no en el listado porque es un hecho sobre el CLIENTE**:
cuánto inflar lo de Día es algo que se sabe de Día, y el listado suma varios
clientes. Puesto en el listado, un margen tendría que valer para todos a la
vez.

**El valor de arranque lo propone la pantalla (`MARGEN_SUGERIDO`), no la
base**: la columna es `NOT NULL` **sin default**, a propósito. Dos defaults
—uno en el `create table` y otro en el código— son la regla escrita dos veces,
y la copia que se separe propone un número y guarda otro.

**Y el backfill puso 0, no el sugerido**: las cargas que ya estaban se
cargaron cuando el margen no existía, o sea sin ninguno. Ponerles 10 las
infla un 10% que nadie pidió, **y el número que sale es plausible** — que es
exactamente el modo de falla que este archivo persigue.

### El `NOT NULL` sin default de la base es una PARED, y la primera que chocó fue la siembra del humo

La columna entró `NOT NULL` sin default y **el humo dejó de arrancar**: su
siembra insertaba `cargas_compra` sin el margen. Eso es la guarda funcionando
—la fila incompleta no entra— y vale anotarlo porque el reflejo al verlo es
ponerle un default a la base para que la siembra pase.

**Ponerle el default arregla la siembra y rompe la regla**: el día que alguien
inserte desde otro camino sin pasar por la pantalla, la fila nace con el
margen de la base en vez de con el que se decidió, y no hay nada que avise. La
siembra es la que se corrige.

### `promedio_anterior_a`: migrada, ESCRITA, MOSTRADA, y leída por nadie

Del 22/09, y es el **corolario 72 en su forma más incómoda: lo construí yo,
dos commits antes, y no lo vi.**

La columna se migró con su comentario, `guardar_carga_de_compra` la escribía,
la pantalla del "ya existe" la mostraba para explicar que editar conserva el
ancla — y **ninguna cuenta la leía**, porque el Paso 1 no calculaba el
promedio. El modo "Del promedio" dibujaba **la misma pantalla que "A mano"**:
la lista entera de artículos con los campos vacíos.

Lo destapó el dueño usándolo: *"el modo 'Del promedio' no trae nada"*.

**Y ninguna de las guardas de esta casa podía verlo**, que es lo que lo pone
en la familia del 72:

- la **verificación de la migración** pregunta si la columna está. Está.
- el **test del INSERT** compara la estructura entera, y la columna estaba en
  los dos lados.
- la **pantalla** se veía perfecta: un modo automático que no precarga nada es
  idéntico a uno manual.
- y el **humo** la abría en 200, porque abrir no es traer.

**La pregunta que lo encuentra es la del 72 con una palabra cambiada**: no
*¿qué código la ESCRIBE?* —eso estaba— sino **¿qué cuenta la LEE?**. Una
columna que solo se escribe y se muestra es una etiqueta, y una etiqueta que
describe un cálculo que no ocurre es peor que no tenerla: afirma que el modo
significa algo.

**Y la señal barata, para el día que se agregue un modo a cualquier pantalla**:
si dos modos dibujan el mismo marcado, uno de los dos no está cableado. Eso se
ve **mirando la pantalla** (CLAUDE.md pt 6), no corriendo la suite — las dos
pantallas contestan 200 y el humo las cuenta a las dos como abiertas.

**Y MIRAR LA PANTALLA TAMPOCO ALCANZÓ, porque se miró el MARCADO (23/09).**
Arreglado lo de arriba, las dos modalidades siguieron mostrando el catálogo
entero: las filas llevaban `hidden` y `.fila { display: flex }` le ganaba al
`[hidden]` del navegador. El test que afirmaba *"A mano arranca vacía y los
demás llegan escondidos"* leía el atributo fila por fila y pasaba. Es el
corolario 32 dos semanas después de escribirlo, en una pantalla nueva: el
atributo es la intención y el efecto lo decide el CSS. Lo destapó el dueño
(*"decenas de filas vacías"*), y ahora lo cuidan tests que cuentan las filas
con `getComputedStyle` en un navegador, con su canario (sin la regla caen los
tres).

### El ANCLA no se mueve al editar; el MARGEN sí — y las dos mitades se ven igual leyendo el `SET`

`guardar_carga_de_compra` inserta con `ON CONFLICT (cliente_id, fecha) DO
UPDATE`, y ese `SET` decide **dos cosas opuestas**:

```sql
SET modo = EXCLUDED.modo,
    margen_porcentaje = EXCLUDED.margen_porcentaje,   -- SE PISA
    actualizado_en = now()
    -- promedio_anterior_a NO SE PISA: el ancla es de la carga, no del guardado
```

- **El ancla se queda** porque el promedio se contó desde el día en que se
  cargó. Pisarla al editar movería la ventana de los 6 pedidos y los números
  de la pantalla cambiarían solos entre una corrección y la siguiente.
- **El margen se pisa** porque es justamente lo que el que edita viene a
  cambiar.

**Y el canario en cero del margen fue el hallazgo del turno** (palabras del
dueño): la carga NUEVA lo guardaba bien y **solo la edición lo perdía**, en
silencio, volviendo al que ya estaba. Un `SET` con una columna de más y uno
con una de menos **se leen exactamente igual**; lo único que los separa es un
test que edite y mire.

Lo cuida un par de tests contra Postgres de verdad —*el ancla NO se mueve al
editar* y *el margen SÍ se mueve al editar*— y hacen falta los dos: con uno
solo, la versión que pisa todo y la que no pisa nada pasan una cada una.

### El BULTO de la carga y el KILAJE del Mercado son dos números y los dos son "cuánto trae un bulto"

Del 22/09, y es del dueño: *"Los kilos totales no me dicen nada. Necesito ver
bultos. 370 kg de arándano no significa nada para el comprador."*

**Lo que los separa es DE QUIÉN ES EL BULTO**, y es la familia de siempre —dos
cosas distintas con el mismo nombre— atajada al bautizar:

| | qué es | dónde vive |
|---|---|---|
| **el bulto de la CARGA** | `fichas_logistica.contenido_caja` — cómo lo pide ESE cliente | Paso 1 |
| **el kilaje del MERCADO** | `listados_compra_kilaje` — de a cuánto viene el cajón | Paso 2, editable |

Que Día pida el arándano en cubetas de 1 no dice nada de si en el Mercado hay
cajones de 1. Confundirlos no descuadra ninguna cuenta: **propone comprar un
número plausible de cajones equivocados.**

**Y el que carga ve bultos y el sistema guarda la MAGNITUD.** La fila muestra
el bulto porque es como piensa el comprador; la base guarda kilos (o el
conteo) porque es lo que el Paso 2 necesita para sumar varios clientes que
piden el mismo artículo en formatos distintos.

**Sin ficha no hay bulto que decir, y el artículo se carga igual**: la carga va
contra el catálogo de compra. Ahí el número queda en la magnitud y **la
pantalla lo dice** en vez de inventar una conversión.

#### El campo se llama POR LO QUE ES, y el contenido sale del SERVER

`bultos_<id>` cuando hay con qué dividir, `total_<id>` cuando no. Un solo
nombre sería **una columna del formulario con dos unidades**, y el server no
tendría cómo saber cuál llegó — el mismo `12` significaría 12 bultos en una
fila y 12 kilos en la de al lado.

**Y el contenido no viaja en un campo escondido**: con el contenido en el
formulario, un POST armado a mano cambia la conversión y el número guardado no
es el que la pantalla mostró. *La guarda va donde se ESCRIBE* (corolario 26)
aplicado a una unidad en vez de a una fecha.

### Lo que quedó IGUAL a la propuesta no se guarda, y eso es lo que hace que los modos signifiquen algo

**Un artículo sin fila guardada se vuelve a calcular al armar el listado**
—así un pedido que entre en el medio se ve— **y uno corregido queda fijo.**
Decisión del dueño (*"yo prefiero que se recalcule"*) con la precisión de que
lo corregido es una decisión y no un cálculo.

**La comparación es entre los DOS TEXTOS tal como la pantalla los dibujó**, no
entre floats: los dos salen del mismo filtro, así que "igual" es exacto y no
una tolerancia. Comparando números, un `0.1 + 0.2` guardaría una corrección
que nadie hizo.

### "Subir archivo" NO es un tercer modo, y por eso no está en el CHECK

`cargas_compra.modo` acepta `'automatico'` y `'manual'`, y nada más. El
archivo **es una forma de TIPEAR**, no una procedencia del número: confirmar
una revisión deja la carga en `'manual'`, porque lo que quedó guardado es lo
que una persona revisó y aceptó.

**Si fuera un tercer modo habría que contestar qué hace al reabrirla** —¿vuelve
a leer el archivo que no guardamos?— y la respuesta no existe. Un valor de
CHECK que no puede contestar qué significa al releerlo es un valor de más.

**Y confirmar REEMPLAZA, no suma.** Lo que se revisó es la carga entera; sumar
dejaría el total dependiendo de cuántas veces se subió el mismo archivo. **Dos
renglones del MISMO artículo adentro de una lectura SÍ se suman** —el listado
puede nombrar el tomate dos veces— y eso es otra pregunta.

### El artículo que falta se da de alta ADENTRO de la revisión

Del dueño: *"Si me piden algo que no tengo como artículo, que me avise y lo
doy de alta antes de seguir."*

**Mandarlo a `/compras/articulos` le hace perder la revisión entera**, que es
trabajo que todavía no se guardó —y la pantalla lo dice con todas las letras:
*"Todavía no se guardó nada"*—. El alta va con `formaction` sobre el mismo
formulario, vuelve a la misma revisión con el artículo nuevo ya elegido en su
fila, y `crear_articulo` devuelve el id justamente para eso (`RETURNING id`).

Es el corolario 56 al revés: allá el problema era un link que manda a una
puerta ajena; acá **es un link que manda a una pantalla propia y aun así
rompe**, porque lo que se pierde no es el acceso sino el estado.

### Guardar tiene que NOTARSE, y el aviso arriba de una pantalla larga no se nota

Del 22/09, y es del dueño: *"Apreto Guardar y no pasa nada."*

**Estaba guardando perfecto.** El POST escribía, la pantalla se volvía a
dibujar, y el aviso salía arriba de todo — con el botón Guardar al pie de
treinta y ocho artículos. El que aprieta está abajo y ve exactamente lo mismo
que antes de apretar.

> **Un aviso que aparece fuera de la pantalla que el dedo está mirando es un
> aviso que no existe.** Es el corolario 68 —un camino que funciona y no se
> ve— aplicado a la RESPUESTA en vez de a la puerta.

El arreglo no fue mover el cartel: **Guardar lleva a otro lado** (la lista de
cargas, con el aviso arriba de una pantalla corta). Un cambio de pantalla es
la confirmación más barata que hay, y no depende de dónde quedó el scroll.

**Y hay DOS destinos, a propósito**: Guardar sale a la lista, y **cambiar de
modo se queda en la misma carga** con su propio aviso. Cambiar de modo no es
terminar: el que lo aprieta quiere seguir en esa carga. Y **no toca los
renglones**, que es lo que permite pasar de "a mano" a "del promedio" para ver
qué propone sin perder lo tipeado.

### La copia separada que encontró el cableado del promedio

`listar_fichas_de_todos_los_clientes` **no traía `unidad_conteo`**, y
`listar_fichas_por_cliente` sí —con seis líneas de comentario explicando por
qué—, mientras el docstring de la primera decía *"misma consulta y mismo orden
que `listar_fichas_por_cliente`"*.

**El modo de falla es el peor que hay: ninguna fallaba, una contestaba
distinto.** Un artículo que se cuenta por unidad, leído por la consulta sin
`unidad_conteo`, contesta en kilos — y el número sale.

Es el corolario 65 otra vez (el mock entrega lo que le pidieron, no lo que la
consulta pidió) con la parte nueva de que **el docstring afirmaba la igualdad
que el SQL no cumplía**. Una afirmación de "esto es lo mismo que aquello"
escrita en prosa es exactamente lo que envejece sin romper nada.

### `magnitud_del_articulo`: tres ramas, y la del medio se midió

La carga es por artículo y la magnitud vive en la ficha, así que hubo que
decidir qué magnitud tiene un artículo que va a varios clientes. Quedó en
`app/costeo.py`, al lado de `magnitud_de_la_ficha`, con tres ramas:

| | qué devuelve | por qué |
|---|---|---|
| **sin ninguna ficha** | kilos | medido: `sin_ficha_Y_con_conteo 0` en las DOS bases |
| **con fichas, alguna contesta** | la primera que contesta | |
| **con fichas y ninguna contesta** | `None` | **nunca cae a kilos** |

**La tercera es la que importa**: caer a kilos ahí sería inventar la unidad de
un artículo cuyo conteo el sistema declaró que no puede resolver, y el número
saldría igual de prolijo. El `None` es lo que hace que la pantalla diga que no
puede en vez de proponer.

**Y la primera está apoyada en un número, no en una intuición**: si existiera
un artículo sin ninguna ficha y con `unidad_conteo`, la rama de kilos lo
etiquetaría mal. `sin_ficha_Y_con_conteo` dio 0 en Palmala (63 activos, 15 sin
ficha) y 0 en Frutamax (38 activos, 5 sin ficha). El día que aparezca uno, esa
rama es la que hay que volver a mirar.

### Al entrar, nada tildado; lo pedido en bultos enteros para arriba (dueño, 05/10)

- **Al entrar NUNCA hay nada tildado**, ni aunque el listado de hoy ya se
  haya guardado: se tilda, se aprieta Actualizar, y recién ahí calcula. Hasta
  v1098 la pantalla "se abría como se dejó": el tilde volvía por el LISTADO
  DEL DÍA (`elegidas` = las cargas del borrador), no por el autocompletado
  del navegador, que ya estaba apagado. Ahora lo guardado se muestra solo en
  la vuelta del guardado (`?actualizado=1`, que pone la redirección del
  POST), y la pantalla va con `Cache-Control: no-store` para que el "atrás"
  del navegador no restaure una vieja con tildes. El PDF sigue saliendo de
  lo guardado. Lo cuida `tests/test_que_comprar_sin_tildes.py`, que abre la
  pantalla después de guardar el mismo día y exige cero tildes.
- **Lo que pide cada cliente va en bultos ENTEROS y PARA ARRIBA**
  (`bultos_pedidos`): "De quién sale" dice "Día 26/09 12 blt (205 kg)", y
  "Piden bultos" es la SUMA de los de cada cliente (dos de 1,2 son 2 y 2: 4,
  no 3). El stock sigue al entero más cercano (28/09). El navegador lo rehace
  igual al mover el por bulto, y el PDF dice lo mismo.

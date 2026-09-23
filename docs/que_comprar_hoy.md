# Qué comprar hoy — el diseño en dos pasos

Del 22 y 23/09. Reemplaza la pantalla única que había hasta el 21/09, donde
los clientes, el margen y lo tipeado a mano vivían todos adentro de un
borrador por día.

**Para qué existe este archivo**: para que nadie vuelva a proponer lo que ya
se decidió. Las decisiones de abajo tienen dueño y fecha, y las que están
marcadas **CERRADA** no se reabren sin que él lo diga.

---

## El problema del negocio

El comprador va al Mercado de madrugada. Antes de salir necesita **una sola
lista**: de cada artículo, cuántos cajones comprar. Esa lista sale de sumar lo
que piden varios clientes, para las fechas que correspondan, menos lo que ya
hay en el piso.

Lo que un cliente pide para un día **no siempre llega por mail a tiempo**:
a veces es el promedio de lo que viene pidiendo, a veces lo dicta por
teléfono, a veces manda una foto de un listado. Por eso **cargar lo que pide
un cliente** y **armar el listado de compra** son dos trabajos distintos, se
hacen en momentos distintos, y desde el 22/09 son dos pantallas.

---

## Paso 1 — Lo que pide un cliente (`/compras/carga`)

Una **carga** es: *este cliente, para esta fecha, pide estos totales.*

### Cómo se entra

`/compras/carga` es la lista. Arriba, el alta: **cliente**, **fecha de
compra** (propone hoy, se puede elegir mañana o pasado) y uno de dos botones:
**Del promedio** o **A mano o por archivo**. Abajo, **las cargas desde ayer en adelante**, cada una con su chip de
modo y, si ya se usó en un listado, su chip de usada.

**Una carga por cliente y por fecha.** Si ya existe, la pantalla **pregunta**:
*editarla* o *borrarla y empezar de cero*, y dice en la misma pantalla qué
significa cada una (editar conserva el ancla del promedio; empezar de cero la
mueve al día de hoy).

### Los tres modos

| modo | qué hace | qué queda guardado |
|---|---|---|
| **Del promedio** (`automatico`) | precarga el promedio de los últimos 6 pedidos de ese cliente | solo lo que se corrigió |
| **A mano** (`manual`) | arranca **vacío**; se agregan artículos de a uno con el buscador | todo lo tipeado |
| **Subir archivo** | lee una foto, un mail o un texto y abre una **revisión** | lo revisado, como `manual` |

**"Subir archivo" NO es un tercer modo** y no está en el CHECK de
`cargas_compra.modo`: es una forma de tipear más rápido. Confirmar una
revisión deja la carga en `manual`, porque lo que quedó guardado es lo que una
persona revisó y aceptó.

**A mano arranca vacía a propósito** (dueño, 22/09): *"me muestra los 38
artículos con un campo cada uno. Con el pulgar eso es imposible de usar."* Se
agrega de a uno con el buscador, como en Armar Pedido.

**Y "Del promedio" arranca con lo que encontró y nada más** (dueño, 23/09):
*"no me muestres los artículos en cero"*. Se ven los que tienen número en los
últimos 6 pedidos; lo que falte se trae con el mismo buscador. Las dos
pantallas se comportan igual: arrancan con lo que hay y se agrega lo que
falte. Un artículo cuyo promedio da cero exacto tampoco se muestra.

**Hasta el 23/09 ninguna de las dos escondía nada**, y es un dato que conviene
tener: las filas llevaban `hidden` bien puesto y `.fila { display: flex }` le
ganaba al del navegador, así que las dos modalidades mostraban el catálogo
entero con los campos vacíos. Lo cuidan tres tests que miran la pantalla en un
navegador, no el atributo.

### El promedio

**CERRADA**: son los **últimos 6 pedidos ANTERIORES AL DÍA DE CARGA**, con
divisor 6.

- **El corte es estricto** (`fecha_operacion < ancla`): un pedido del mismo
  día de carga **no entra**. Se carga de noche para el día siguiente, así que
  lo de hoy todavía se está armando.
- **El ancla es el día en que se cargó**, no la fecha de compra, y se guarda
  en `cargas_compra.promedio_anterior_a`.
- **El divisor es 6 siempre**, haya 6 pedidos o 2: es lo que ese cliente pide
  *un día cualquiera*, no el promedio de los días en que pidió.
- **La cuenta es la MISMA del Paso 2**, con las mismas funciones de
  `core/que_comprar.py`. Escrita dos veces serían dos promedios, y la copia
  que se separe no falla: **propone un número distinto del que el listado
  después va a usar.**
- **Un hueco deja el artículo afuera** en vez de proponer un número a medias:
  si a un renglón no se le puede pasar lo pedido a su magnitud —sin ficha, o
  ficha sin `contenido_caja`— ese artículo no se propone. Sumar los demás
  diría que ese cliente pide menos de lo que pide.

**Editar conserva el ancla; empezar de cero la mueve.** Si editar la moviera,
los números de la pantalla cambiarían solos entre una corrección y la
siguiente.

### Lo que se recalcula y lo que queda fijo

**Lo que quedó IGUAL a la propuesta no se guarda.** Un artículo sin fila
guardada **se vuelve a calcular al armar el listado** —así un pedido que entre
en el medio se ve— y **uno corregido queda fijo**, porque es una decisión y no
un cálculo.

La comparación es entre **los dos textos tal como la pantalla los dibujó**, no
entre floats: los dos salen del mismo filtro, así que "igual" es exacto.

### El margen

**CERRADA**: **un solo margen, el de la carga.** El del Paso 2 **se va, no
queda en cero.**

- Va **sobre lo que el cliente pide**, no sobre el faltante, con la misma
  `con_margen` del Paso 2.
- Va en la **carga** porque cuánto inflar lo de Día es un hecho sobre Día, y
  el listado suma varios clientes.
- **Dos márgenes se MULTIPLICAN**: 20% y 10% son 32%, y nadie hace esa cuenta
  con el pulgar (dueño, 23/09).
- El valor de arranque lo propone la pantalla (`MARGEN_SUGERIDO = 10`), **no
  la base**: la columna es `NOT NULL` **sin default**.
- **0 significa sin margen**, y es distinto de vacío.
- **CERRADA (dueño, 23/09): va SOLO sobre lo que el promedio PROPONE.** Lo
  corregido en "del promedio" y todo lo de "a mano" ya es el número que se va
  a comprar, y entra tal cual: *"si el número ya es el que voy a comprar, un
  porcentaje encima no tiene sentido."* Inflar lo corregido le cobraría el
  margen dos veces, porque se corrige mirando la propuesta que ya lo tiene.
- **Por eso en "A mano" la pantalla NO muestra el campo**: ahí no movería
  nada, y un campo sin consecuencia invita a creer que hizo algo. Guardar sin
  el campo conserva el margen que la carga ya tenía, en vez de pisarlo con el
  sugerido.
- **La regla vive UNA vez**, en `lo_que_pide_la_carga` (core/que_comprar.py),
  y la llaman las dos pantallas: la carga la dibuja con eso y el listado la
  suma con eso. Escrita en cada una, la copia que se separe hace que el
  listado compre otra cosa que la que se vio en la carga.

### Bultos

**La fila muestra BULTOS**, que es como piensa el que compra: *"370 kg de
arándano no significa nada"* (dueño, 22/09). El bulto es
`fichas_logistica.contenido_caja` del cliente — cómo lo pide él.

**No confundir con el kilaje del Mercado del Paso 2.** Los dos son "cuánto
trae un bulto"; lo que los separa es de quién es el bulto. Que Día pida el
arándano en cubetas de 1 no dice nada de si en el Mercado hay cajones de 1.

**El sistema guarda la magnitud** (kilos, o el conteo), no los bultos: el Paso
2 suma varios clientes que piden el mismo artículo en formatos distintos.
**Sin ficha no hay bulto**, y el artículo se carga igual — en la magnitud, y
la pantalla lo dice.

El campo se llama por lo que es: **`bultos_<id>` o `total_<id>`**, y el
contenido para convertir **sale del server**, nunca de un campo escondido.

### Subir archivo

**CERRADA**: **el archivo no se guarda.** Es una herramienta para tipear más
rápido; lo que vale es lo revisado.

El flujo: subir → el sistema lee → **pantalla de revisión** (*"Todavía no se
guardó nada"*) → corregir, tirar renglones, dar de alta lo que falte →
confirmar.

- Cada renglón leído trae su **confianza** y un **select con el catálogo
  entero**, porque lo que el lector propone es una adivinanza.
- **El artículo que falta se da de alta ADENTRO de la revisión**, con
  `formaction` sobre el mismo formulario: mandar a `/compras/articulos` hace
  perder la revisión entera, que es trabajo sin guardar.
- **Confirmar REEMPLAZA la carga**, no suma: lo que se revisó es la carga
  entera.
- **Dos renglones del mismo artículo adentro de una lectura SÍ se suman**: un
  listado puede nombrar el tomate dos veces.

Reusa `core/lector_comandas.py` (el mismo camino de la lectura de pedidos) con
su propio prompt, que pide artículo + cantidad + confianza y **no pregunta la
unidad**.

### Contra qué se carga

**CERRADA**: **contra ARTÍCULOS DE COMPRA, no contra fichas.** *"Yo compro
tomate, no 'el tomate de Día'."* (dueño, 22/09).

La magnitud de un artículo que va a varios clientes la resuelve
`magnitud_del_articulo` (app/costeo.py): sin fichas → kilos (medido:
`sin_ficha_Y_con_conteo 0` en las dos bases); con fichas, la primera que
contesta; con fichas y ninguna que conteste → **`None`**, nunca kilos.

---

## Paso 2 — Armar el listado (`/compras/que-comprar`)

**Reescrito el 23/09.** Reemplaza la pantalla del 21/09, que elegía clientes
con un modo y un margen propio.

### Cómo quedó (dueño, 22/09)

**Se eligen los clientes y, DE CADA UNO, qué fechas sumar.** *"Puedo tomar dos
días de Día y uno de Tailem, y que todo vaya al mismo listado."* La pantalla
dibuja un bloque por cliente con un tilde por fecha adentro, de la más vieja a
la más nueva. **Lo que se tilda es la CARGA** —un cliente para una fecha, con
su modo y su margen— y eso es lo que el listado guarda en
`listados_compra_cargas`.

- **La fila suma el mismo artículo entre todas las cargas tildadas** y dice
  de quién sale cada parte ("Día 26/09 160 · Tailem 26/09 40"): un total que
  junta tres cargas y no lo dice se lee como el pedido de un solo cliente.
- **Lo que suma de cada carga es lo que esa carga mostró**, con
  `lo_que_pide_la_carga`: el promedio en vivo contra el ancla de la carga,
  con su margen, y lo guardado tal cual. El modo se decide una vez
  (`_propuesto_de_la_carga`): el listado nunca le suma el promedio a una
  carga "a mano".
- **Una carga que el listado ya tiene se ofrece aunque sea más vieja que
  ayer**: la pantalla guarda lo tildado, y una que no se dibuja se destildaría
  sola al primer Guardar.

- **CERRADA**: se muestran **las cargas desde ayer en adelante**. Con eso **no
  hace falta ninguna hora de corte**: se trabaja de noche y el que decide es
  el que carga.
- **CERRADA**: **una carga ya usada en otro listado se muestra igual,
  marcada**, y se puede volver a sumar.
- **CERRADA**: **el kilaje del Mercado vive acá y es editable.** De a cuánto
  viene el cajón lo dice el Mercado, no el cliente, y cambia de día a día.
- **CERRADA**: **el margen global de esta pantalla SE VA.** No queda en cero:
  se va.

### Lo que NO cambia

**Toda la aritmética de `core/que_comprar.py`** (dueño, 22/09):
`promedio_de_un_dia`, `con_margen`, `falta_por_comprar`, `cajones_que_faltan`,
`margen_valido`. Lo único que se agregó es `lo_que_pide_la_carga`, que no es
una cuenta nueva: es la regla que la pantalla de la carga ya aplicaba,
mudada a un lugar donde el listado también la llama.

---

## Lo que hay en la base

| tabla | qué guarda |
|---|---|
| `cargas_compra` | la cabecera: cliente, fecha, modo, ancla del promedio, margen. Único por `(cliente_id, fecha)` |
| `cargas_compra_renglones` | el total por artículo, **en la magnitud**. PK `(carga_id, articulo_id)`, cascada desde la carga |
| `listados_compra_cargas` | qué cargas entraron en qué listado. **Sin cascada hacia la carga**: borrar una carga usada tiene que rebotar, no borrar el rastro |
| `listados_compra` | la cabecera del listado (del 21/09). Su `margen_porcentaje` está **en retiro**: sin NOT NULL desde el 23/09 (`listados_compra_5`), el código ya no la escribe, y se dropea con el bloque 3 |
| `listados_compra_kilaje` | el kilaje del Mercado, editable (del 21/09) |

**Se van cuando el Paso 2 esté desplegado**: `listados_compra_manual`,
`listados_compra_clientes` y la columna `listados_compra.margen_porcentaje`,
con `db/cargas_compra_3_sacar_las_viejas.sql`.

---

## Lo que falta

1. **Correr `db/cargas_compra_3_sacar_las_viejas.sql`** en las dos bases,
   **después** del deploy del Paso 2 — hasta entonces el código viejo, que es
   el que está arriba, todavía lee esas tablas y escribe el margen del
   listado.
2. **Sacar las dos tablas y la columna del margen de
   `db/esquema_completo.sql`** en el mismo commit que el drop, no antes:
   hasta ese día una base nueva las necesita.

---

## Lo que ya corrió

Ver `db/corridas_confirmadas.md`, entrada del 22 y 23/09.

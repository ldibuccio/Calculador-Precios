# Módulo: vacíos del puesto y del depósito

Movido TAL CUAL desde CLAUDE.md el 03/10 (sin reescribir). Las reglas
vigentes, en corto, están en CLAUDE.md.

## HAY DOS CIRCUITOS DE VACÍOS Y NO SE TOCAN (18/09)

Escrito el día que nació el segundo, y a propósito **antes** de que alguien
los confunda: es la familia de *dos cosas distintas con el mismo nombre*
—la que este archivo paga una y otra vez— atajada por una vez en el momento
de bautizar y no en la próxima lectura.

| | **VACÍOS DEL PUESTO** (desde antes) | **VACÍOS DEL DEPÓSITO** (18/09) |
|---|---|---|
| de quién es el cajón | de un `proveedores_puesto` | de un `proveedores` de Compras |
| cómo entra | un `clientes_puesto` lo trae, con seña o vale | **llega con la mercadería**, en la recepción |
| cómo sale | el proveedor del puesto lo retira con el camión | se le devuelve al proveedor que lo vendió |
| dónde vive | `vacios_recibidos` · `vacios_devueltos` · `conteos_vacios` · `ajustes_vacios` | `vacios_deposito_foto` · `vacios_deposito_devoluciones` · `vacios_deposito_ajustes` · `vacios_deposito_asignaciones` · `conteos_vacios_deposito` · `marcas_vacio` |
| su catálogo | `tipos_envase_puesto` | `marcas_vacio`, por proveedor |

**No comparten una sola tabla, y los dos "proveedor" son tablas distintas.**
Lo único que comparten es la palabra, y por eso las tablas nuevas la llevan
con `_deposito` pegado: un `conteos_vacios` a secas al lado de un
`conteos_vacios_deposito` se distingue leyendo, que es lo único que se hace
a las tres de la mañana.

**Y la marca del cajón no es `envases`**, que es la tercera cosa que dice
algo parecido: `envases` es LA CAJA NUESTRA con su costo, la que se le
factura al cliente. La marca nombra el cajón AJENO en el que llega la fruta.
Uno se paga, el otro se devuelve.

### El TIPO DE CAJÓN por proveedor se fue (dueño, 29/09): lo reemplazan las marcas

Del 18/09 al 29/09 cada proveedor declaraba "en qué cajón entrega"
(`proveedores.tipo_cajon_id`, catálogo `tipos_cajon`), uno solo, en el alta y
en el detalle de Vacíos. Las MARCAS (25/09) lo reemplazaron: un proveedor
puede tener varias, y son las que parten el stock en pilas. Con un solo
proveedor cargado, el tipo no entraba en ninguna cuenta.

- **Paso 1 (29/09)**: el código dejó de leerlo y escribirlo. Salieron los dos
  selectores, el aviso de "sin declarar", la ruta `/vacios/{id}/cajon` y la
  columna del Excel y el PDF del stock. Lo cuida
  `test_NINGUN_codigo_lee_ni_escribe_el_tipo_de_cajon`, que barre `app/`,
  `core/`, `scripts/` y `templates/`.
- **Paso 2 (29/09)**: `db/tipo_de_cajon_1..3` borraron la columna y la
  tabla en las dos bases, después del deploy del paso 1 (corolario 94), y
  `db/esquema_completo.sql` las perdió en el mismo commit. Ver
  `db/corridas_confirmadas.md`.

### Y LA REGLA QUE ESTO DEJA: derivar es lo único que hace inmune al campo que no se llena

Es del dueño, del 18/09, y es la parte CONSTRUCTIVA de *"un campo sin
consecuencia se llena vacío"* — aquella sección dice que el arreglo está del
lado del sistema, y ésta dice cuál es:

> **Un dato que se DERIVA no tiene un campo del que acordarse, así que no
> puede dejar de llenarse.**

Las entradas de vacíos del depósito no se cargan: salen de las recepciones,
que ya existen y las carga alguien porque necesita otra cosa. No hay
formulario, no hay tilde, no hay nada que un operario pueda saltear en dos
semanas.

**Y el contraste está en este mismo archivo, tres párrafos más arriba**: el
préstamo de cajas vacías al puesto **sí** es un campo, y su única
consecuencia es que un aviso salte a tiempo. Ése es el que está en riesgo, y
por eso tiene puesta su advertencia. Los dos son del mismo módulo y del mismo
mes; lo que los separa es si el dato ya existía en otro lado.

**Cómo se usa al diseñar, y es una pregunta**: antes de agregar un campo,
*¿este número se puede sacar de algo que alguien ya carga por otro motivo?*
Si la respuesta es sí, el campo no va — y lo que se gana no es una pantalla
más corta: es que el dato no pueda faltar.

Engancha con el corolario 80 por el otro extremo: allá lo derivado hace que
*completar el dato de origen SEA el arreglo* —no hay una segunda columna que
mantener al día—; acá hace que **no haya nada que completar**. Es la misma
propiedad cobrada dos veces.

### Lo que encontró ESTRENAR el primer nombre TIPEADO en la barra (18/09)

El detalle de Vacíos pone el nombre del proveedor en `barra_titulo`, y es la
**primera pantalla del sistema que pone ahí algo que escribe una persona**:
los otros dos títulos dinámicos —la pantalla de la clave y la de "en
construcción"— traen texto del código. O sea que el caso lo estrenó esta
pantalla, y lo que estrenó fue un agujero viejo.

La barra achica el título hasta 0,9rem y, si aun así no entra, **le saca el
`nowrap` para que envuelva en dos líneas**. Eso es el fallback previsto y
está escrito en su comentario. Una palabra SIN ESPACIOS no tiene dónde
envolver, así que el fallback no hacía nada: medido a 390px, la página
desbordaba **371px** con un nombre de proveedor sin espacios. Se cierra con
`overflow-wrap: anywhere`, que es lo que hace que el fallback exista.

**Y el índice desbordaba 384px por su cuenta**, en el nombre y en el tipo de
cajón. Los dos son lo mismo dicho dos veces: **el largo de un nombre no lo
controlamos, así que toda pantalla que muestre uno se mide con un nombre que
no se puede partir.** El par va completo —el impartible y el normal— porque
un arreglo que rompa el caso cómodo para aguantar el raro pasaría el primero
sin que nada caiga.

**Y el desborde se lee de `desborde_pagina`**: en una pantalla de tarjetas la
clave `desborde` viene clavada en 0 (corolario 47 adentro del resultado), así
que el test que mira la que no es sale en verde sobre una pantalla que se
arrastra de costado.

### Y el 503 de las tres puertas decía "Gerencia" (18/09)

Salió del mismo trabajo, por el primer POST de Vacíos: sin `CLAVE_COMPRAS`
cargada contestaba **"Falta la clave de Gerencia"** y explicaba que *corregir
una recepción mueve la cotización del artículo*. La pantalla es UNA y las
puertas son TRES —Gerencia, Administración y Compras— y su texto estaba
escrito entero para la primera.

Es el **corolario 56 exacto** —la url era una; los sectores, tres— con la
diferencia de que acá no hay un link que choque contra una clave ajena: hay
un cartel que manda a pedir **la clave equivocada**, que es peor, porque el
que lo lee cree que ya entendió. El arreglo es el mismo que el de aquel caso:
lo que describe el CAMINO sale de `puerta` (el título, la ayuda, el volver) y
deja de estar escrito en la plantilla.

**Y el test pregunta por la jerga que NO puede aparecer** —`"Gerencia" not in
marcado`— y no solo por el texto bueno: afirmar el nombre nuevo pasa igual si
la frase vieja quedó tres líneas más abajo.

**Lo que lo destapó no fue leerla: fue que un test nuevo diera 503 donde
esperaba 303.** La pantalla llevaba así desde que la segunda puerta la reusó,
y no la mira nadie — solo se dibuja cuando falta una variable de entorno, o
sea en un deploy a medio configurar, que es justo cuando nadie está leyendo
con atención.

### Y el vale NO toca el importe de la compra

También del dueño: el descuento del vale vive SOLO en la fila de la
devolución. **Es plata de ENVASE, no de mercadería**, y el sistema ya trata
al envase por su lado — meterlo adentro de `compras.importe` mezclaría dos
cosas que hasta hoy están separadas, y encima re-escribiría un número que ya
se cargó en Administración.

El neto, el día que haga falta, **se lee sumando las dos, no cambiando una**.
Es el criterio de siempre —una cuenta se compone, no se pisa— dicho sobre
plata en vez de sobre stock. (Esto decía que la resta era un join por
`compra_id`. **Desde el 25/09 la devolución no va contra una compra**, así
que ese join solo existe para las viejas.)

### DESDE EL 28/09 LA CUENTA ARRANCA DEL CONTEO FÍSICO (dueño)

Se contó el piso a mano (1.086 cajones en 17 pilas) y eso es el stock de
arranque. La foto del 25/09 y su corrección (`vacios_foto_4`) **no se corren
más**: quedan como historia.

- **Dos tablas**: `vacios_deposito_arranques` (el instante y el motivo,
  "Conteo físico 28/09") y `vacios_deposito_arranque_pilas` (lo contado por
  proveedor y marca). **El último arranque manda.** La cuenta
  (`_SQL_PILAS_DE_VACIOS`) es lo contado más lo recibido con seña, menos lo
  devuelto, más ajustes y asignaciones, todo **cargado DESPUÉS del
  `creado_en` del arranque**. Una pila o un proveedor que no está en el conteo
  arranca en cero. Sin arranque (Palmala) la cuenta es la de la foto, como
  antes.
- **Lo de antes no se borra y no mueve el número.** Por eso no se puede anular:
  `_anular` lo rechaza y el detalle no ofrece el botón
  (`antes_del_arranque`), con la etiqueta "antes del conteo: no cuenta". El
  índice y el detalle dicen arriba de qué conteo arranca la cuenta
  (`templates/_origen_vacios.html`).
- **Se cargó con `db/vacios_conteo_2809_1..6`**: tablas, datos (la tabla del
  dueño escrita UNA vez, en una función), buscadores, revisión (solo lee),
  carga (un `do`, solo en la base con N09P39) y verificación aparte. El
  proveedor se busca por nombre plegado sin puntos: igual exacto, o uno solo
  que lo contenga. La marca, plegada y sin espacios: "Tomjug" pasó a llamarse
  "Tom Jug". "Sin Proveedor" se creó con el código N00P00, que no es un
  puesto.
- **Juntar proveedores y juntar marcas mueven lo contado** (la tabla está en
  `TABLAS_QUE_APUNTAN_A_PROVEEDORES` y en `COLUMNAS_QUE_NOMBRAN_UNA_MARCA`).

Lo cuida `tests/test_vacios_conteo_2809.py`, contra Postgres, con historia de
todo tipo antes del arranque.

### DESDE EL 25/09: una FOTO, PILAS por marca, y el conteo solo coteja

(La foto dejó de ser el corte el 28/09: ver arriba. Lo que sigue vale para las
pilas, las marcas y el conteo, y para la cuenta de una base sin arranque.)

Decisiones del dueño, y reemplazan el modelo del conteo inicial del 18/09
entero. Lo que había —un conteo que ARRANCABA la cuenta, con su "todavía no
arrancó", sus "esperando" y la regla de la fecha— **se fue**.

- **El corte es la FOTO** (`vacios_deposito_foto`, una fila por proveedor,
  corrida el 25/09 en las dos bases): el stock que el sistema mostraba ese
  día. Frutamax dio 1.758 clavado contra la pantalla. De ahí en adelante:
  **recepciones CON SEÑA suman, devoluciones restan**, y lo que no cierre se
  arregla con un ajuste. El intento de reconstruir el pasado (arrancar el
  18/09) se descartó: dejaba 16 de 35 proveedores negativos.
- **Y LA FOTO SALIÓ MAL, medido por el dueño el 28/09**: `vacios_foto_1`
  sumó TODOS los cajones recibidos desde el primer conteo, con seña o sin
  ella, porque copió la pantalla de ese día, que no filtraba. Frutamax quedó
  en 798 (9 contados + 279 + 510) y con la regla son 19 (9 + los 10 de
  pomelo, los únicos con seña). Lo de DESPUÉS de la foto siempre filtró bien:
  la única consulta de Vacíos que lee compras es `_SQL_PILAS_DE_VACIOS`, con
  `COALESCE(sena, 0) > 0`. La corrección era
  `db/vacios_foto_4_corregir_con_sena.sql` (**no se corrió**: el 28/09 el
  dueño cambió la foto por el conteo físico, ver arriba), con la revisión (`vacios_foto_3`)
  antes y la verificación (`vacios_foto_5`) aparte. Lleva una columna de
  control que rehace la foto vieja: si no da el número actual, la cuenta no
  es la misma y la migración aborta sin escribir. **La seña vacía y la seña
  en cero son lo mismo**: el campo es opcional y no hay forma de decir "sin
  seña" distinto de "todavía no la cargué". Una seña que se cargue tarde en
  una compra de antes de la foto solo entra si se carga ANTES de correr la
  corrección.
- **La foto se compara por INSTANTE (`f.creado_en`), no por día.** Con la
  fecha, lo recibido el 25/09 después de sacar la foto se perdía entero. Lo
  encontró correr la cuenta contra Postgres, no leerla.
- **El stock es por PILA: proveedor y marca de cajón** (`marcas_vacio`, que
  se cargan en el detalle de Vacíos). La foto va a "sin asignar"; la marca se
  la pone la recepción o una ASIGNACIÓN de Administración, que mueve de una
  pila a otra sin cambiar el total. Las FK son compuestas `(marca, proveedor)`:
  una marca de otro proveedor la rechaza la base.
- **La marca de Recepción es UN campo desde el 28/09** (dueño). Hasta ese
  día eran dos: el texto (`compras.marca`) y un selector de la marca del
  cajón que solo aparecía si el proveedor tenía marcas cargadas en Vacíos.
  No había ninguna, así que 25 de 27 compras quedaron con la marca escrita y
  los cajones "sin asignar". Ahora, con seña, lo escrito se busca entre las
  marcas de ese proveedor (plegado con `normalizar_texto`) y si no está se
  crea (`_marca_vacio_de_nombre`, que también usa la asignación). Sin seña no
  se crea nada: esos cajones no entran a Vacíos. Las ya cargadas van como
  sugerencias del campo. Lo que ya estaba lo vincula
  `db/vacios_marca_texto_1_vincular.sql`. **El Detalle muestra la de la
  RECEPCIÓN**: si después Administración asigna esos cajones a otra pila, la
  compra sigue diciendo con qué marca llegaron. **El ingreso directo lleva
  seña y marca desde el 28/09** (dueño): nace recibido, así que
  `crear_compra` escribe la marca y la vincula en la misma transacción, con
  la misma regla que Recepción: con seña suma a Vacíos, sin seña no.
- **La devolución sale de una PILA, sin compra**, con la seña por cajón de
  la última recepción de esa pila precargada y editable. **Sin foto del vale
  no es una devolución: es un ajuste** (guarda en la ruta, en la escritura y
  en la base: `vacios_dev_con_foto`). **Las viejas —contra una COMPRA,
  modelo anterior al 25/09— quedan eximidas por el propio CHECK**
  (`compra_id is not null or foto`), y no por NOT VALID: `vacios_marcas_5`
  corrió NOT VALID y con eso **las 13 viejas de Frutamax no se podían
  anular**, porque NOT VALID exime a lo viejo solo del chequeo al crearse y
  todo UPDATE posterior se chequea. Lo arregla `vacios_marcas_7`, corrida el 25/09 en las dos. **La foto
  del vale entra en la regla de 3 años desde el 30/09**: hasta ese día no
  vencía, porque la limpieza vieja le ponía la ruta en NULL y el CHECK lo
  rebotaba. La regla nueva borra el ARCHIVO y deja la ruta (ver "FOTOS: LA
  REGLA DE 3 AÑOS"), así que el CHECK se sigue cumpliendo. **No se
  devuelve más de lo que dice el sistema**: el freno lee la pila con la fila
  del proveedor bloqueada, y con LA MISMA consulta de la pantalla.
- **Ajuste y asignación son SOLO de Administración**, igual que todo Vacíos
  desde el 29/09 (ver abajo). **La tarjeta de
  asignar sale siempre** desde el 28/09: iba adentro de un `if marcas` y,
  sin marcas cargadas en ningún proveedor, no apareció nunca. Muestra
  cuántos hay sin marca, la marca de destino se elige o se escribe (y
  escrita se crea en la misma transacción), y los "sin asignar" con cajones
  van resaltados en el índice y en el detalle. **Los cajones salen de "sin
  asignar" o de otra marca**: de 200 "Pepe Jaula" se pasan 150 a "Pepe
  Torito" con la misma tarjeta.
- **Corregir el nombre de una marca** (`renombrar_marca_vacio`, solo
  Administración): la pila es la misma, con otro nombre, y el stock y los
  exportados lo leen del id. Si el nombre ya es de otra marca del proveedor
  (lo decide el unique), la pantalla ofrece **juntarlas**
  (`juntar_marcas_vacio`): todo pasa a la que queda en una transacción, por
  las columnas de `COLUMNAS_QUE_NOMBRAN_UNA_MARCA`, y la otra se borra. Las
  asignaciones ENTRE las dos se borran: quedarían de una marca a la misma,
  que la base rechaza, y dentro de una sola pila no movían nada. Un test que
  lee `pg_constraint` compara las FK a `marcas_vacio` contra esa lista.
- **El conteo físico ya no arranca nada: va al COTEJO**, el último conteo de
  cada pila contra lo que el sistema decía AL CIERRE DEL DÍA en que se contó
  (dueño, 30/09; hasta ese día era contra el sistema de ahora, y un conteo de
  hace una semana se comía todo lo que se movió en el medio). Es la cuenta de
  las pilas con un tope (`_sql_pilas_de_vacios(tope)`, `_SQL_CIERRE_DEL_DIA`):
  solo lo cargado antes de las 24 de ese día, contra el arranque que ya
  existía. Si antes de ese instante no había arranque ni foto, la fila dice
  que no hay contra qué comparar. "Ajustar" propone la diferencia de ESE día,
  aplicada hoy. Solo ofrece proveedores y
  marcas ya cargados. **Y se carga en SU pantalla** (`/vacios/conteo`, dueño,
  27/09): hasta ese día el formulario estaba en el índice, arriba del stock de
  cada pila, y el que cuenta veía el número. La pantalla nueva no LEE el stock,
  así que tampoco puede quedar escondido en el HTML.
  **Depósito la abre sin clave** desde el 29/09 (dueño): botón "Stock Vacíos"
  debajo de "Stock Mercadería" en su menú, en `/deposito/vacios/conteo`, y
  guardar vuelve a contar en vez de ir al Cotejo, que muestra el número del
  sistema. **Y devuelve sin clave** (`/deposito/vacios/devolucion`, "Devolver
  vacíos"): la misma escritura que Administración
  (`_guardar_devolucion_de_vacios`), sin mostrar el stock, y el freno de "no se
  devuelve más de lo que hay" (`DevolucionDeMas`) le dice "avisale a
  Administración" sin el número. Contar y devolver son las DOS únicas rutas de
  Vacíos bajo `/deposito`, y un test lo exige.

- **El detalle de un proveedor va en TRES ZONAS** (dueño, 29/09): el total con
  una fila por marca ("Sin marca" incluida); cuatro acciones que se despliegan
  de a una (Devolver, Pasar a otra marca, Corregir una marca, Ajustar); y el
  historial cerrado, "Ver
  movimientos de este proveedor". **Las pilas en cero no se muestran** (dueño,
  30/09), "Sin marca" incluida; un negativo sí, en rojo. Si no queda ninguna,
  dice "Sin vacíos". `?abrir=` despliega una, y un formulario que
  rebota vuelve con la suya abierta. **El historial sale de
  `movimientos_de_vacios`**: las mismas cinco patas que `_SQL_PILAS_DE_VACIOS`,
  con lo anulado y lo de antes del conteo marcados. Lo ata a la tarjeta un test
  contra Postgres que suma la lista y la compara con el stock por pila. Con una
  base sin arranque (Palmala) no marca como "antes" lo anterior a la foto: esa
  base no vota.

- **El índice de Administración tiene tres botones** (dueño, 29/09):
  Exportar, Cotejo y Movimientos. "Cargar un conteo" pasó al Cotejo.
  **Movimientos** (`/administracion/vacios/movimientos`) filtra por fecha,
  proveedor y marca: 30 días por defecto y 90 como máximo
  (`core/movimientos_vacios.py`). Con más de 90 no consulta y lo dice. La
  consulta es la misma del historial del detalle, y el renglón se dibuja una
  vez (`templates/_movimiento_vacio.html`). La marca filtra por la de salida
  Y la de llegada, así un pase aparece en las dos. La compra no lleva link,
  porque su detalle está detrás de la clave de Compras (corolario 56). El
  Excel baja lo filtrado, sin tope. **"Por dónde entró" es el SECTOR, no
  quién**: conteo, Recepción, Depósito (ingreso directo), Administración o
  Compras. La devolución lo guarda en `cargada_desde` (migración del 29/09,
  en las dos bases), sin default en la escritura: un camino que se olvide de
  decirlo es un TypeError. Las 13 devoluciones viejas de Frutamax dicen "sin
  dato".
  (`templates/vacios_movimientos.html` es la pantalla de Vacíos del PUESTO:
  la del depósito se llama `compras_vacios_movimientos.html`.)

- **Vacíos del depósito salió de Compras** (dueño, 29/09): no queda ninguna
  ruta bajo `/compras/vacios` ni el botón del hub de Compras. Vive en
  Administración, y Depósito cuenta y devuelve sin clave. Lo cuida
  `test_VACIOS_ya_no_existe_bajo_COMPRAS`, que mira las rutas y que ninguna
  plantilla linkee ahí. El camino `compras` de `CAMINOS_DE_CAJAS_Y_VACIOS`
  queda por Cajas. **El Cotejo tiene "Ajustar"** en cada fila que no cierra:
  abre el proveedor con `?abrir=ajustar&pila=<marca o "sin">`, y el server
  rehace la diferencia con `cotejo_de_vacios_deposito` para precargar marca,
  sentido y cantidad (`propuesta_desde_el_cotejo`). La URL no lleva números,
  y el motivo no se precarga.

- **El total del galpón y el aviso de devolver** (dueño, 29/09). El índice
  dice el total de todos los proveedores al lado de "Cajones en el galpón",
  en rojo si pasa del límite. Con más de `LIMITE_CAJONES_VACIOS_EN_GALPON`
  (500, en `app/db.py`, un solo lugar) salta `vacios_para_devolver`: "Hay N
  cajones vacíos en el galpón: hay que devolver", en Compras, Gerencia y
  Administración. Es sobre el TOTAL, no por proveedor, y un negativo resta.
  La frase la arma el campo `texto` de `DefinicionAlerta`. Gerencia y
  Administración estrenaron su pantalla de Alertas (`/gerencia/alertas`,
  `/administracion/alertas`), y los cuatro hubs dicen en el botón cuántas
  hay (`templates/_boton_alertas.html`; desde el 05/10 también cuenta lo que
  no se sabe, ver `docs/modulos/tareas.md`). Las cuatro pantallas de
  Alertas traen "Recalcular ahora" desde el 30/09 (dueño): hasta ese día el
  botón estaba solo en Auditoría. Recalcula TODAS con la misma función que
  Auditoría (`_recalcular_alertas_a_pedido`) y vuelve a la pantalla del
  sector; la de Gerencia pregunta su clave en la ruta. Desde Compras y Gerencia el
  link va a su propia pantalla de Alertas, que lista los proveedores: Vacíos
  está detrás de la clave de Administración (corolario 56). Y una alerta
  que el registro tiene y la foto no se calcula en el tick siguiente, sin
  esperar las seis horas (`hay_que_recalcular`). Las cuatro acciones del
  detalle del proveedor van en azul.

- **El ingreso directo tiene SU guía** (`guias_compra.de_deposito`): "nunca
  es parte de la comanda del Puesto". Dos guías por día y proveedor, cada
  una numera sus renglones. El origen no se elige: sale de la compra
  (`retiro_origen = 'ingreso_directo'`) al cargarla, al moverla de día y al
  cambiarle el proveedor, y la comanda de la carga manual solo se cuelga de
  la de Compras. `_guia_de_compra` anda con el unique viejo puesto y sin él
  —`ON CONFLICT` sin target y respaldo a la guía que haya—, así que el
  deploy no tiene ventana rota; `guia_deposito_2` y `3` van después.

Los números van contra Postgres en `tests/test_vacios_pilas_contra_la_base.py`,
con la foto EN MARZO a propósito (corolario 95) y un proveedor cuya recepción
cae el mismo día que su foto, antes y después de la hora.

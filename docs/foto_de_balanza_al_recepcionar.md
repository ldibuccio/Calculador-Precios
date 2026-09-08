# Foto de la balanza al recepcionar

Del 08/09. Decidido con Lionel, **sin código todavía**: falta la medición
que decide la resolución (ver el final).

## Para qué

Que el operario saque una foto de la mercadería sobre la balanza al
recepcionar. Es prueba de que se pesó de verdad y deja registro del número
que marcó el display.

**Una foto por artículo**, no una por recepción. Y eso no es una decisión de
diseño: es la estructura que ya hay. Una fila de `compras` **es un
artículo** (`compras.articulo_id`), y `/deposito/recepcion` recibe cada
compra por separado con su propio POST. La foto cuelga de la compra y no hay
nada que inventar.

## Lo que YA ESTÁ, y es la mitad del trabajo

Esto se escribió acá porque al empezar creímos que subir fotos a Storage era
un pendiente. No lo es — está en producción:

- `core/storage.py`: bucket **privado** `comandas`, subida por REST,
  borrado, y URL firmada a 1 hora.
- `_comprimir_foto_jpeg` (app/main.py): EXIF aplicado a los píxeles, máx
  **1000 px** de lado largo, JPEG **calidad 60**. Su docstring dice, y hay
  que mantenerlo cierto: *"todo lo que termina en Storage pasa por acá"*.
- `fotos_guia` (comandas) y `fotos_pedido` (capturas del mail), las dos con
  la misma forma.
- La pantalla **Sistema** muestra el uso del bucket leyendo
  `storage.objects`, y tiene el botón de limpiar fotos de más de 3 años.

**La confusión venía de una columna que existió y se borró**:
`compras.foto_ruta`, muerta en `db/drop_foto_ruta_compras.sql` cuando las
fotos pasaron a `fotos_guia`. Quedó el recuerdo de la columna, no el de su
reemplazo. Es la familia del comentario que envejece, pero en la cabeza y no
en el código: **antes de dar algo por pendiente, mirar si no se hizo de otra
forma.**

## Decisión 1 — Tabla nueva `fotos_recepcion`, no un tipo sobre `fotos_guia`

`fotos_guia` cuelga de `guia_id` (proveedor + día) y **se comparte a
propósito** entre varias guías: el Listado consolidado usa un archivo para
varios proveedores, y por eso su borrado es *"solo si NINGUNA guía lo
referencia"*. La foto de balanza cuelga de **una compra** y no se comparte
nunca.

Meterla en `fotos_guia` con una columna de tipo obligaría a un `compra_id`
nullable al lado del `guia_id` y a un CHECK de "exactamente uno" — la **media
regla** del corolario 3 — y a que el borrado compartido ramifique por tipo.

**Y el patrón ya está sentado**: `fotos_pedido` es una tabla aparte con la
forma idéntica, en vez de un tipo sobre `fotos_guia`. Seguirlo es
consistencia. Lo que NO se duplica es `core/storage.py`: **la mecánica se
comparte, el dueño no.**

Forma: `fotos_recepcion (id, compra_id → compras, foto_ruta, creado_en,
unique (compra_id, foto_ruta))`. Varias filas permitidas —el operario puede
repetir si salió movida— y "falta foto" es `count = 0`.

## Decisión 2 — Al borrar la compra se devuelve la ruta; nada de cascade

Con `on delete cascade` el archivo queda **huérfano en el bucket** y nadie lo
va a ir a buscar. Se devuelve la ruta y se borra del Storage, que es el
patrón que el flujo de guías ya usa.

Y hay dos lugares que hoy borran compras, no uno (corolario 2):

- `eliminar_compra` — `DELETE FROM compras WHERE id = %s`.
- `eliminar_compras_del_dia_por_proveedor` — el borrado en bloque.

**Los dos revientan por violación de FK** el día que exista una foto, si no
se los toca. No es un riesgo teórico: es el `DELETE` tal como está escrito
hoy.

## Decisión 3 — La limpieza las incluye DESDE EL PRINCIPIO

Sin esto, una foto de balanza **no se borra nunca**: `listar_fotos_para_limpiar`
lee solo de `fotos_guia`, así que las nuevas ni siquiera aparecerían como
candidatas. En dos años son miles de archivos inmortales.

Y hay una segunda mitad que es peor, porque **falla en silencio**. El ciclo
de `/sistema/limpiar-fotos-viejas` es: borrar del Storage, después
`limpiar_foto_ruta_de_compras(ruta)`, que borra **filas de `fotos_guia`**. Si
entra una ruta de recepción y esa función no la conoce:

1. el archivo se borra del Storage,
2. el `DELETE` afecta **0 filas y no da error**,
3. `borradas += 1` — la pantalla dice que salió todo bien,
4. y queda una fila de `fotos_recepcion` apuntando a un archivo que no
   existe: "Ver foto" roto para siempre.

Es exactamente *la ausencia de error no es confirmación*, y del lado feo: el
borrado a medias se **reporta como éxito**.

Por eso las dos funciones se tocan juntas, en el mismo commit:
`listar_fotos_para_limpiar` devuelve la unión (los dos conjuntos de rutas son
disjuntos: `_armar_ruta_unica` no puede repetir), y la que limpia filas borra
de **las dos tablas**.

**Una sola perilla de retención, no dos.** Hoy son 3 años
(`_fecha_de_corte_limpieza_fotos`) y la foto de balanza usa el mismo corte.
Corolario 26: cuando la misma regla existe en dos fuerzas eso se DECIDE, no
se hereda — acá se decide que es **la misma**, y si algún día tiene que ser
distinta, la razón se escribe al lado.

## Decisión 4 — La compresión se queda en el SERVIDOR

El teléfono sube el original; comprime `_comprimir_foto_jpeg`. No se hace un
segundo pipeline.

El motivo no es la comodidad: **si el servidor confía en lo que manda el
teléfono, la regla "todo lo que está en Storage pasó por el pipeline" deja de
ser cierta y nadie se entera.** El que garantiza es el que escribe (corolario
21), aunque sea redundante.

El costo es real y está aceptado: el operario sube 3–5 MB por 4G y espera. Si
se queja, la mejora es un pre-achique en el teléfono **como paso posterior y
separado**, con el servidor re-codificando igual.

## Decisión 5 — La marca en "procesados hoy" dice `sin foto`, en gris

No un ícono de cámara. **El que audita busca lo que falta, no lo que está**,
y con "sin foto" la columna queda vacía cuando está todo bien — que es la
forma correcta de no decir nada.

Y una precisión que sale de la lista de estados: la marca aparece **solo en
las `recepcionado`**. Una compra `rechazado` o `no_ingresado` puede no haber
pasado nunca por la balanza, así que ahí "sin foto" no es un hallazgo — es
ruido puesto justo sobre las filas donde no significa nada (corolario 22).

## Lo que NO se hace: el cartel a nivel guía

Nada de "faltan fotos en 2 de 5 artículos". El botón de cada artículo cambia
a **"Recibir sin foto de balanza"** más confirmación, y con eso alcanza:
es por renglón, se apaga solo, y se lee ANTES de apretar. Es el escalón del
tilde del corolario 26 puesto donde se decide.

Un cartel de guía estaría puesto durante toda la recepción **por
construcción** —al empezar faltan todas— y ya tenemos la medida de en qué
termina eso: el aviso de "no hay cajas de esta ficha" salía en **135 de 765
bultos, todos los días**.

## CERRADO — la resolución no se toca, y el requisito no existía

Estuvo abierto medio día y no tendría que haberlo estado nunca. La
pregunta era si 1000 px y calidad 60 dejan leer el display. Se midió sobre
una foto real sacada a la distancia a la que va a trabajar el operario: el
dígito queda en **~14 px** (1,4% del alto del cuadro), los trazos pierden
la forma cerrada, y el número se lee **"177 o 17,7"** — sin poder decidir
si hay coma.

De ahí salió una propuesta de subir el lado largo a 2000, un parámetro
nuevo en `_comprimir_foto_jpeg`, y la idea de guardar un recorte del
display aparte.

**Nada de eso va, porque el requisito que lo pedía no existía.** Lo que se
necesita de la foto es ver que **la mercadería estaba sobre la balanza y
que la balanza estaba pesando** — el cajón, la balanza, el display
encendido. A 1000 px eso se ve. "Foto de la balanza" se leyó como "foto
legible del número", y esa lectura se coló en el planteo, en la prueba de
las tres distancias y casi en un cambio al pipeline de TODAS las fotos del
sistema.

Y hay un hecho que lo cierra del todo, que no es de software: **el operario
redondea el pesaje.** Aunque el display se leyera perfecto, el número no
iba a coincidir con lo cargado. Cotejar foto contra sistema no tiene
sentido acá, y sin cotejo la legibilidad no vale nada.

Queda entonces, y es lo que estaba desde el principio:

- `_comprimir_foto_jpeg` **como está**: 1000 px, calidad 60, sin argumento
  nuevo (el parámetro se mergeó y se revirtió el mismo día).
- **Sin recorte del display.**
- **Sin resolución especial** para `fotos_recepcion`.

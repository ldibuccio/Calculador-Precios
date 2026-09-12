# Calculador de Precios

Reglas generales del proyecto, vigentes para todo el código que se agregue de acá en adelante.

## Idioma

Todo el código, la UI, los comentarios y los mensajes de commit van en español (Argentina).

## Diseño mobile-first (obligatorio)

El sistema lo usa principalmente una sola persona, desde el **celular** — no desde escritorio. Cualquier pantalla o componente nuevo tiene que estar optimizado para eso:

- Botones grandes y bien tocables con el dedo/pulgar (no chicos ni apretados) — pensar en un área mínima cómoda, no un link de texto chico.
- Que no haga falta hacer zoom para leer ni para tocar nada.
- Grupos de botones que entren cómodos en el ancho de un celular: si son varios, que se apilen/envuelvan en filas (`flex-wrap`), nunca que se desborden a los costados u obliguen a scrollear horizontal.
- Tablas y listados que se lean bien en celular: evitar el scroll horizontal donde se pueda; si una tabla es necesariamente ancha, pensar cómo mostrarla en celular sin que se corte (columnas compactas, abreviaturas, u otra disposición) antes de simplemente envolverla en un contenedor con scroll.
- Aprovechar el espacio vertical (es lo que sobra en celular) y cuidar el horizontal (es lo que falta).

Esto aplica a toda pantalla nueva, no solo a las de compras.

## SQL para el editor de Supabase (obligatorio)

Todo el SQL de este proyecto se corre a mano, pegado en el editor SQL de
Supabase. **Ese editor no es psql**, y dos diferencias ya nos costaron caro:

- **`begin ... commit` NO es atómico ahí.** El editor no sostiene la
  transacción: confirma cada sentencia por su cuenta. Un script que falla en
  la sentencia 7 deja aplicadas las 6 anteriores.
- **Las tablas y vistas TEMPORALES no sobreviven de una sentencia a la
  siguiente.** Una que se crea arriba ya no existe cuando la usa la de abajo,
  y el error llega *después* de que lo anterior se escribió.

De acá en adelante:

1. **Nada de tablas ni vistas temporales** en el SQL que se manda al editor.
   Lo que se necesite varias veces se repite (un CTE por consulta) o se
   guarda en una tabla real.
2. **Todo lo que tenga que ser todo-o-nada va en un único `do $$ ... end $$`.**
   Un bloque `do` sí es una sola sentencia, y ahí adentro la atomicidad y el
   `raise exception` funcionan de verdad. Las guardas y los pasos que
   dependen unos de otros van todos adentro del mismo bloque, no repartidos.
3. **Lo que tenga que verse va en UNA sola consulta final que devuelva
   filas** (el editor muestra solo el resultado de la última, y no muestra
   los NOTICE).
4. **Los bloques largos se TRUNCAN, y cuando truncan PEGAN SQL AJENO.** Pasó
   el 02/09 con un verificador de 5983 caracteres. El editor lo cortó a la
   mitad —en el medio de un caso— y **le concatenó código propio abajo**: un
   `ALTER TABLE cliente ENABLE ROW LEVEL SECURITY` con un comentario "Added
   by Supabase". El error que devolvió fue `unterminated dollar-quoted
   string`, que no dice una palabra de lo que pasó de verdad.

   **Eso es peor que un límite de largo.** No es que el script se corte y
   falle: es que lo que termina corriendo **no es el script que se mandó**.
   Esta vez el corte cayó adentro del `do` y dejó un dollar-quote abierto, así
   que el ALTER ajeno quedó dentro de una cadena sin cerrar y no se ejecutó
   (verificado contra la base: no quedó nada escrito). **Si el corte hubiera
   caído después del `end $$;`, ese ALTER habría sido una sentencia válida y
   habría corrido.** La seguridad de "un `do` es UNA sentencia, o parsea
   entero o no ejecuta nada" **solo vale si el corte cae ADENTRO del bloque**,
   y dónde cae no lo decidimos nosotros.

   Por eso: **ningún bloque que se mande al editor pasa los 2500
   caracteres.** Lo que no entre se parte en bloques cortos, cada uno capaz de
   correrse solo y de deshacerse solo con su propio `raise`. Y ante un error
   raro de sintaxis, **primero se mira qué quedó escrito en la base**, antes
   de suponer que no se ejecutó nada.

Esto no es una preferencia de estilo: es el entorno donde el SQL corre de
verdad. Un script probado en Postgres local puede estar correcto y aun así
romper —o peor, escribir a medias— en el editor.

## Un `if not exists` sobre CONTENIDO es una trampa, no una protección

Del 09/09. El bloque 2 de la migración de la merma de segunda crea el CHECK
con la lista de motivos permitidos, envuelto en el `if not exists` de
siempre. Se corrió con una lista, después se corrigió la lista, y se volvió
a correr: **el bloque salió `DO` y no hizo nada.** El constraint ya existía,
así que el `if not exists` lo salteó — con la lista vieja adentro.

**El modo de falla es el peor que hay: un bloque idempotente que no hace
nada se ve EXACTAMENTE IGUAL que uno que corrió bien.** Sale `DO` las dos
veces. No hay error, no hay diferencia en la pantalla, y lo que quedó en la
base no es lo que se mandó. Es la familia del push silencioso y la del
editor que escribe a medias, con una vuelta más: acá el silencio es la
respuesta CORRECTA del comando.

La distinción que hay que hacer, y es la regla:

- **Para ESTRUCTURA** —una columna, una tabla, un índice— el `if not
  exists` está bien: la columna existe o no, y si existe es la misma.
- **Para CONTENIDO** —una lista de valores permitidos, un umbral, un texto,
  una fila de configuración— **la idempotencia deja de proteger y pasa a
  esconder.** Lo que "ya existe" puede ser otra cosa que lo que se quiere.
  Ahí va `drop ... if exists` y recrear, siempre, aunque parezca de más.

**Cómo se reconoce antes de sufrirlo**: mirar qué protege el `if not
exists`. Si adentro del bloque hay una lista de literales, un número, una
fecha o una cadena, es contenido y la guarda está de más — o peor, en
contra.

Y lo único que lo agarró: **la consulta de verificación contaba el
constraint POR NOMBRE**, así que dio `guarda_lista 0` cuando el bloque ya
había salido `DO`. Es el corolario de siempre —la verificación se corre
después y mira el estado final, no que el comando no se haya quejado— con
la precisión de que **contar por nombre es lo que la hizo servir**: un
"¿existe algún check?" habría dado 1 y tapado el problema igual.

## `git push origin main` parado en otra rama no falla ni avisa

Pasó el 02/09. Dos commits quedaron en la rama, se corrió
`git push origin main`, y **el push salió con código 0**: como `main` no
había cambiado, git no imprimió ninguna línea de actualización — solo el
`branch 'main' set up to track` de siempre. Se leyó como "subió", y lo que
en realidad pasó fue que no había nada que subir. Los archivos que se creían
desplegados estuvieron una hora sin estar.

`git push origin <rama>` empuja **esa rama**, no en la que estás parado.
Commitear en una rama y pushear otra es un no-op silencioso, y el silencio
es el problema: no hay error que leer.

De acá en adelante, después de cualquier push que se dé por desplegado:

1. **Se verifica con `git rev-list --left-right --count origin/<rama>...<rama>`**,
   que tiene que dar `0 0`. Un "push exitoso" sin líneas de actualización no
   es prueba de nada.

   **Y se verifica sobre la rama en la que se está parado, no sobre la que
   se quiso empujar.** Pasó el 02/09, un día después de escribir esta regla:
   el commit fue a `main` (era donde estaba parado), el push fue a la rama, y
   el `rev-list` de la rama dio `0 0` — correcto y vacío, porque la rama no
   tenía nada pendiente. La verificación pasó en verde mientras el commit
   estaba en otro lado. Lo agarró el hook de git al cerrar, no la regla.
   `git branch --show-current` antes de commitear, y `git status` después del
   push: si dice "ahead", el commit no está donde se cree.
2. **Antes de commitear se mira en qué rama se está.** El commit va donde
   estás parado, no donde creés.

   **Y la verificación se REPORTA sobre lo que se miró, no sobre lo que se
   quería.** Pasó el 07/09, tres días después de escribir el párrafo de
   arriba, que describe exactamente esto. Se commiteó en `main`, se pusheó, y
   se reportó *"pusheado a la rama, rev-list 0 0"*. Las dos mitades eran
   ciertas por separado —el push salió, y el `rev-list` de la rama daba
   limpio— y juntas decían algo falso: el commit estaba en `main`. **La regla
   no falló por no correr el comando: falló al contar el resultado.** Un
   `rev-list` en verde sobre la rama equivocada es una verificación cumplida
   y una afirmación falsa, y lo segundo es lo que llega al otro lado.

   Antes de escribir "pusheado a X": `git branch --show-current`, y que X sea
   eso. Si no coinciden, eso es lo que hay que decir.
3. **La ausencia de error no es confirmación.** Es la misma familia que el
   editor de Supabase que escribe a medias y el verificador que nunca se
   corrió: lo que hay que mirar es el estado final, no que el comando no se
   haya quejado.

4. **Y la ausencia de FILAS tampoco es información.** Es la otra cara, y mordió
   el 07/09 con el backfill de Palmala. Un `do $$` que sale bien **no devuelve
   nada**, y en el editor eso se ve exactamente igual que una consulta que no
   encontró resultados. Se corrió el backfill, se vio "No rows", se lo leyó
   como el resultado del bloque de conteo, y se reportó el backfill como
   pendiente cuando ya estaba hecho. Después el backfill abortó tocando 0 —la
   guarda funcionando— y se buscó el bug en las consultas durante dos vueltas,
   cuando lo único que pasaba era que ya no quedaba nada que tocar.

   Corolario de diseño, y es el que evita que vuelva: **una consulta de
   verificación devuelve CONTEOS, no una lista de ofensores.** Con conteos
   siempre viene una fila y el cero se ve. Con una lista, "todo bien" y "no
   corrió" son la misma pantalla vacía. Ver `db/palmala_4_verificacion.sql`.

   Y al correr algo que no devuelve filas —un `do`, un `update`—, lo que
   confirma que corrió **no es la pantalla del editor: es la consulta de
   estado que se corre después**.

## Una salida de una ficha con envase solo puede salir de esa ficha

**Cosa fija del sistema, no el arreglo de un día.** Se tuvo que decir tres
veces el 09/09 y cada vez apareció un lugar distinto donde no se cumplía.

Cuando se arma un pedido y **no hay stock de la ficha del cliente, la única
opción es sin asignar.** No toma de ningún otro lado: ni de los sueltos, ni
del cajón, ni de otra ficha. La ficha queda **en negativo, en el aire**,
hasta que alguien cargue la guía R — y ahí se acomoda solo, porque el
reparto se rejuega en cada lectura y la comparación es por FECHA.

**El hecho del mundo que la sostiene**, y por eso no es una preferencia:
con envase, la mercadería sale en NUESTRA caja, y **una caja no puede salir
de un cajón sin pasar por una guía R.** No es que prefiramos no tomar del
cajón: es que ese armado no ocurrió. Si alguien dice que salió del cajón, lo
que está describiendo es un reproceso que no se cargó.

Sin envase es **envase perdido** (manzana, pera, arándano): sale en el cajón
del proveedor, no se reprocesa nunca, y ahí nada de esto aplica.

**LA CONDICIÓN ES UNA SOLA Y TIENE UN SOLO NOMBRE**: `envase_id IS NOT NULL`
en `fichas_logistica`, que viaja con la salida como `ficha_con_envase` desde
`_SQL_SALIDAS_STOCK`. No se deduce del nombre del artículo, ni del contenido
de la caja, ni de ningún derivado — eso ya se midió y da un tercio mal
(corolario 20). El campo directo acertó 630 de 630 y 135 de 135.

Está escrita en cuatro lugares, y los cuatro tienen que decir lo mismo:

1. **La cuenta de stock** — `_cajas_por_ficha` (app/db.py). Con envase, la
   ficha **resta la salida completa y queda negativa**; los sueltos no
   absorben el excedente. El piso `max(saldo, 0)` es SOLO de la rama sin
   envase, y ahí sigue siendo obligatorio (04/09: Manzana Gob, total 63,
   sueltos 233, botón de ajuste destructivo por 170).
2. **El FIFO** — `pasadas_de_lotes` (core/stock.py), y `lotes_ofrecidos` /
   `lote_ofrecido` al lado, que son la misma pared para el que no reparte.
   Con envase **no se le ofrece el cajón**: una sola pasada, la de los
   preferidos, sin pasada de respaldo. El bulto queda **sin lote**, que es
   información verdadera —salió y el papel no está— y se costea cuando
   aparece la caja. El cajón queda intacto a propósito: si el armado le
   bajara el restante, la guía R que viene a explicarlo no lo encontraría y
   el freno la rechazaría.
3. **El armado** — el desglose (`desglose_de_renglon_armado`) NO LISTA el
   cajón, y `guardar_lotes_elegidos` lo rechaza si llega igual por un POST a
   mano. Ver más abajo.
4. **La pantalla** — el Cotejo (templates/deposito_stock_cotejo.html). El
   déficit **se ve como tal**, con el aviso de cargar la guía R, y sin botón
   de ajuste de primero que lo tape: "Cargar la guía R" es el primario y el
   ajuste queda en segundo plano. Y el aviso llega a la tarjeta de SUELTOS
   aunque esa ficha no se haya contado nunca.

### La vía de escape que hubo, y cómo se cerró (09/09)

**`lotes_senalados` no pasaba por la pared.** Corre en la PASADA 1 de
`repartir_fifo` y de `atribuir_costos_fifo`, *antes* de que
`pasadas_de_lotes` decida qué se ofrece. Un renglón con
`pedidos_renglones_lotes_elegidos` apuntando a un cajón **se llevaba el
cajón**, con envase y todo. Medido corriendo `repartir_fifo`, no leyéndolo:

```
A) armado con envase, sin corrección     cajón consumido 0.0  · sin_lote 10.0
B) el mismo, con el CAJÓN elegido        cajón consumido 10.0 · sin_lote  0.0
C) el mismo, por merma dirigida          cajón consumido 10.0 · sin_lote  0.0
```

Y era alcanzable desde la pantalla, no solo por SQL: el desglose listaba
TODOS los lotes con restante, el cajón aparecía con 0 propuestos, el input
estaba ahí, y ni el submit ni `guardar_lotes_elegidos` ni el POST miraban
`ficha_con_envase`.

Cerrada con dos cosas, y hacen falta las dos:

1. **El cajón NO SE LISTA.** No es una opción peor: es la cosa que la regla
   prohíbe. Listarlo sin input, o listarlo y avisar al guardar, dejan a la
   vista algo que no se puede elegir, y eso invita a preguntarse por qué
   está ahí. Si no queda ninguno, el caso vacío ya dice lo que corresponde
   ("faltan cajas armadas de esta ficha: cargá la guía R").
2. **`guardar_lotes_elegidos` lo RECHAZA**, con un `ValueError` que el POST
   devuelve como 400 con el motivo adentro. Que la pantalla no lo ofrezca no
   alcanza: **la guarda va donde se ESCRIBE**, no donde se muestra — es el
   mismo hallazgo del tilde de la fecha, donde un formulario armado a mano
   entraba sin ver el cartel.

**Y la razón no se copió**: las dos preguntan por `lotes_ofrecidos` /
`lote_ofrecido` (core/stock.py), que son `pasadas_de_lotes` filtrada. Lo
cuida `test_la_pared_del_POST_pregunta_por_pasadas_de_lotes_y_no_por_su_
propia_condicion`, que **mueve la pared y exige que la guarda la siga**: con
la pared parcheada para no filtrar nada, el cajón con envase tiene que
entrar. Una guarda con condición propia falla ese test.

El argumento que la había dejado abierta está escrito en `repartir_fifo` y en
general es correcto: *"lo están SEÑALANDO con el dedo, no adivinándolo — si
dicen que salió de ése, salió de ése, y discutirles la fecha sería negarles
el piso"*. **Acá es la excepción, y es la única**: no se trata de quién sabe
más, sino de algo que no puede haber pasado. El piso manda sobre lo que se
puede observar; no sobre lo físicamente imposible. Si alguien dice que salió
del cajón, lo que está describiendo es un reproceso que no se cargó.

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
pueden separar.

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
caracteres. `arts_mezclados` dio **0**: ningún artículo tiene dos tamaños de
cajón conviviendo, así que **el Remanente ya suma bultos comparables** y no
había nada que desglosar. Ver `docs/desglose_del_remanente_por_contenido.md`.

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

**Lo que quedó**: dos artículos con la referencia de verdad mal —Mango en
10 unidades cuando la mediana es 40, y Tomate Cherry en 5 kg cuando entran
cajones de 5 a 15— y **dos compras con cajones faltantes**, que son las que
importaban desde el principio.

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
casi todos, y los dos que están mal son Mango (a 40) y Cherry (vacío, porque
no tiene valor dominante).

### Lo que queda ANOTADO Y NO CONSTRUIDO: la otra contaminación

**Recepción precarga LOS DOS campos reales con el estimado**
(`deposito_recepcion.html`: `value="{{ c.cantidad_cajones }}"` y
`value="{{ c.contenido_por_cajon }}"`, sin JS que los limpie). Apretar
"Recibir" sin tocar nada graba `real = estimado` **por el camino normal**,
no por el excepcional — así que es mucho más grande que el ingreso directo
que sí se midió.

**No se construyó nada, por pedido, y la razón es buena**: con lo que se
sabe hoy no cambia ninguna decisión. La referencia ya se dio por buena por
otro camino, y las dos que estaban mal ya están identificadas.

Queda medible cuando haga falta, y la consulta está escrita:
`db/kilos_4_cuanto_de_lo_pesado_se_peso.sql` separa por si alguien CAMBIÓ el
número, que es lo que de verdad distingue "lo pesaron" de "lo aceptaron".

**Y el día que alguien la retome, la trampa está acá**: excluir el ingreso
directo NO alcanza, y ésa fue la primera reacción de los dos. Es la regla de
las exclusiones al pie de la letra — el motivo de esa exclusión (escribe las
dos columnas) no es el motivo del problema (el real puede ser igual al
estimado sin que nadie pese).

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
| **Referencia mal cargada** | el sistema sugiere mal para ESTE artículo | 2 artículos (Mango y Cherry) | al corregir la referencia |
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

### Lo que queda ANOTADO Y NO CONSTRUIDO

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

## Esconder un contenedor esconde TODO lo que vive adentro

Del 11/09, y va como regla y no como corolario porque no es la trampa de un
día: es una pregunta que hay que hacerse cada vez que una pantalla nueva
pase a tarjetas en el celular.

Cuando una tabla se convierte en tarjeta, el `<thead>` sobra: los rótulos de
columna no tienen dónde ir. La línea que sale sola es `thead { display:
none; }`, y **esconde la fila entera, no los rótulos**. Si adentro vivía
algo más, se va con ellos.

**Dos veces el mismo día, con respuestas OPUESTAS**, y por eso la regla es
mirar y no prohibir:

| pantalla | qué había en el `<thead>` | qué pasó |
|---|---|---|
| Buscar Compras | 7 rótulos **+ `#check-todas`** | apagó el "seleccionar todas" |
| Compras Pendientes | 6 rótulos, nada más | seguro |
| Ingresos a Depósito | 8 rótulos, nada más | seguro |
| Fichas | 8 rótulos, nada más | seguro |

En Buscar Compras el "seleccionar todas" del borrado múltiple vive en la
primera celda de la cabecera. Medido: **visible en 1200px, invisible en
390px** — una función que andaba, perdida en la presentación que más se usa.
Se arregló escondiendo los RÓTULOS (`thead th { display: none }`) y dejando
la primera celda, con su texto puesto por CSS.

En las otras tres se contaron los elementos interactivos adentro del
`<thead>` antes de tocar nada: **cero**. Ahí esconderlo entero es correcto.

**LA SEÑAL, y es la parte que hay que llevarse**: el desborde medía **0 de
las dos formas.** Ese era el número que se estaba mirando —era el objetivo
del cambio, bajar el desborde a cero— y el cero llegó igual con la función
apagada. La captura tampoco avisaba: una cabecera que no está no se ve.
Nada en la medición que uno eligió puede delatar algo que quedó afuera de
esa medición.

Es la misma familia del corolario 38 —el marcado, el CSS y los comentarios
comparten el texto y hay que anclar afuera de lo que no se quiere mirar— y
del 19 —la salvaguarda funcionó y el dato estaba a la vista, pero no se
leyó—. Acá el dato **no estaba a la vista en ningún lado**: había que ir a
buscarlo.

**Cómo se hace, y cuesta un comando**: antes de escribir un `display: none`
sobre un contenedor, listar qué hay adentro. Para un `<thead>`:

```
python3 -c "
import io, re
h = io.open('templates/X.html', encoding='utf-8').read().split('</style>')[-1]
c = re.search(r'<thead>(.*?)</thead>', h, re.S).group(1)
print(len(re.findall(r'<(input|button|select|a)\b', c)), 'interactivos')
"
```

Cero es vía libre. Más que cero es un caso, y hay que decidirlo.

**Y el anclado del `split("</style>")` no es un adorno del ejemplo**: la
primera versión de ese conteo, escrita el mismo día, barría desde el
`<thead>` que nombra el COMENTARIO del `@media` y devolvía 7/6/9/9 y
"23 interactivos" en Buscar Compras. Los números eran plausibles y estaban
mal. Es el corolario 38 mordiendo adentro del comando escrito para aplicar
esta regla.

**Alcance**: vale para cualquier contenedor, no solo el `<thead>`. Un
`<fieldset>`, un `<tfoot>`, una fila de totales, un `<details>`, un `div`
que se apaga por media query. La pregunta es siempre la misma: *¿esto que
escondo tiene adentro algo que se toca?* Y la respuesta se cuenta, no se
recuerda — en las cuatro pantallas de arriba la intuición decía "son
rótulos" y en una de las cuatro era falso.

## La caja nuestra que se va y no vuelve: TRES puertas del mismo agujero

Del 11/09, y va acá porque es un hecho del negocio que el sistema no
registra, no un bug. **Anotado y NO construido** — por pedido, y a la
espera de que el hecho se mida antes de tocar nada.

Cuando la mercadería sale en NUESTRA caja y después se va del circuito, esa
caja no vuelve. El sistema no lleva cuenta de eso por ninguna de las tres
puertas por las que pasa:

1. **El envase perdido de origen** — manzana, pera, arándano: salen en el
   cajón del proveedor y no se reprocesan nunca. Ahí no hay caja nuestra que
   perder, y por eso está bien que no se cuente (ver más arriba).
2. **La segunda que se remite al Puesto** — sale en la caja en la que está.
3. **La devolución al proveedor** (la que estrenó el cuarto destino): si la
   mercadería vuelve en el cajón del proveedor, ese cajón sale por el
   circuito de vacíos como cualquier otro y no hay nada que hacer. **Si
   vuelve en caja de Día, la caja se va con ella.**

Las tres son el mismo hecho —una caja nuestra deja el depósito sin pasar por
vacíos— y ninguna de las tres lo anota.

**Por qué no se construyó**, y es la parte que importa para el día que
alguien lo retome: el dueño dijo que hoy *"se acomoda solo"* por el circuito
de vacíos, y **eso no se midió**. Antes de agregar un campo hay que
contestar si la pérdida de cajas que se ve en los conteos de vacíos se
explica ENTERA por otra cosa, como pasó con el 15,6% "sin dato" del
Remanente (corolario 23): un número que se explica entero por un origen
conocido no es deuda.

Y la señal de que ya es hora está escrita en el corolario 31: **la segunda
vez que haya que escribir un `.sql` a mano para contar cajas que faltan, eso
deja de ser un incidente y es una función que falta.**

### La CUARTA puerta es de otra clase: es un PRÉSTAMO, no una pérdida

Del 11/09, y va aparte de las tres de arriba a propósito.

Cuando el puesto entrega la mercadería **ya armada en caja nuestra**, las
cajas vacías se le mandan el día anterior. Eso hoy **no se registra en
ningún lado**: `envases` es un catálogo —nombre, activo, costo con
vigencia— **sin stock y sin movimientos**, y el circuito de vacíos es de los
cajones DEL PROVEEDOR (`proveedores_puesto`), separado a propósito.

**La diferencia con las tres de arriba, y es la que importa:** en aquéllas
la caja se va CON mercadería y no vuelve — es una pérdida. Acá se va
**vacía y vuelve llena**: es un préstamo, y solo se vuelve pérdida el día
que no vuelve.

Eso cambia qué habría que medir, y por eso conviene que esté escrito antes
de que alguien lo retome: **no "cuántas se fueron" sino "cuántas no
volvieron".** Contar salidas de un préstamo da un número grande y
tranquilizadoramente inútil — la mayoría vuelve. El número que significa
algo es el que no cierra.

**No se construyó, por pedido**: hoy son pocas cajas y se llevan de memoria.
Queda anotado para el día que deje de alcanzar.

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

## `unidad_compra` y `unidad_venta` se suponen la MISMA unidad (anotado, no tocado)

Del 12/09, y va escrito porque una pantalla nueva lo heredó y conviene que
se sepa que lo heredó.

`_costear_compras` (app/costeo.py) divide `Σ(importe × cajones)` por
`Σ(cajones × contenido_por_cajon)` y llama al resultado **costo por unidad
de venta**. El numerador es plata y el denominador es contenido de compra,
así que esa igualdad solo vale si la unidad en que se compra y la unidad en
que se vende son la misma. **No hay ninguna conversión en ningún lado**:
`grep conversion` sobre `app/costeo.py` y `core/motor_costeo.py` no devuelve
nada, y `conversion_articulos_cliente` —que es lo único que se llama así—
guarda **cómo llama cada cliente a cada artículo**, nombre y código propios,
para interpretar sus pedidos por mail. No convierte unidades.

Analizar Artículo hereda el supuesto y **eso es lo correcto**: lo peligroso
sería que esta pantalla usara una regla distinta a las demás, que es la
familia de la regla escrita dos veces. Queda anotado y no se tocó.

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

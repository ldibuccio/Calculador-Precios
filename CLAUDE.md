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

Y hay una VIVA, encontrada el 07/09 al escribir el backfill de Palmala: el
índice `fichas_logistica_codigo_cliente_unico` pliega `lower(trim(...))` y
**no pliega tildes**; `normalizar_texto` (core/matcheo_comanda.py), que es
quien matchea el código del pedido contra la ficha, **sí las pliega**. Así que
`CÓD-2` puede entrar al lado de `COD-2` —el índice los ve distintos— y para el
matcheo son el mismo código: el sistema elegiría una en silencio, que es
exactamente lo que el comentario de ese índice dice que viene a impedir.

Es el caso de "ruben" al lado de "Rubén", con los mismos dos plegados y la
misma tilde faltando de un lado. No se arregló todavía porque el arreglo es
una migración y hay que ver primero si hay códigos con tilde cargados; **la
guarda de ambigüedad del backfill cubre justo esa grieta** y por eso no es
código muerto.

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
   midió dos días: dice `fecha_operacion >= corte`, o sea todo desde el
   31/08. Nadie inventó el número; alguien le agregó un período al
   contarlo, y el período viajó solo.

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

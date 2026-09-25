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

### Los 36px del renglón ya armado: es una decisión DE CONJUNTO, y la toma el dueño

Del 19/09. Medidos a 390px sobre la pantalla RENDERIZADA —no sobre un
`<button>` suelto escrito para la ocasión, que es la simulación que mide una
pantalla imaginaria (corolario 52)— los tres controles del renglón ya armado:

```
GET 200 · renglones ARMADOS dibujados 1 · controles mirados 3
.boton-lotes      "Elegir el lote"   36,2px   faltan 7,8
.boton-destildar  "Destildar"        36,2px   faltan 7,8
.boton-anular     "✗"                35,2px   faltan 8,8
```

**No se movió ninguno, y el argumento es del dueño**: los tres están abajo del
umbral, así que subir uno solo lo deja desparejo en la misma fila y no arregla
los otros dos. Es una decisión del renglón entero —cuánto vertical se le da a
algo que ya está hecho y que en una pantalla larga se repite treinta veces— y
**se toma mirándola en el galpón, con el pulgar**, no midiendo píxeles acá.

Queda anotado **como una medición y no como una deuda**: que estén en 36 puede
ser correcto para controles que se usan poco y conviven con treinta hermanos. El
mínimo de 44 está escrito para lo que se toca; cuánto de esto se toca lo sabe el
que arma. Lo que el número compra es que el día que se mire no haya que volver a
medirlo.

**Y la identidad va pegada al número** (corolario 53): `GET 200` y
`ARMADOS 1 · mirados 3`. Sin eso, un `0 de 0 abajo del umbral` medido sobre la
pantalla de una clave, o con la sección "Ya armado" todavía plegada, se imprime
exactamente igual de prolijo que la medición buena — y las dos veces que pasó en
este proyecto lo delató el denominador, nunca el número.

## El rótulo hace la PREGUNTA, la ayuda da un EJEMPLO

Del 15/09, y es del dueño. Vale para toda pantalla, igual que el mobile-first.

**Un rótulo no nombra el mecanismo del sistema: hace la pregunta del negocio.**
"Se cuenta además en" describe que existe una segunda magnitud — el que carga
un artículo de cero no tiene por qué saber que eso existe. Lo que sí sabe es
si el cajón se pesa o se pesa Y se cuenta:

    ¿Además de pesarlo, se cuenta?
      No, solo se pesa
      Sí, se cuentan unidades
      Sí, se cuentan cubetas

**Y la ayuda da un ejemplo, no una explicación.** "El mango se pesa y además se
cuentan los mangos. El tomate solo se pesa." La versión vieja contaba cómo
funciona por dentro (*"cada compra va a pedir las dos magnitudes"*), que es
cierto y no le sirve a nadie para contestar.

**Cómo se reconoce un rótulo del lado equivocado**: nombra una cosa del
sistema (una magnitud, un campo, un estado, una tabla) en vez de algo del
galpón. Si para entenderlo hay que saber cómo guardamos el dato, está mal.

**Y el test pregunta por la jerga que NO puede aparecer**, no solo por el
texto bueno: `"segunda magnitud" not in marcado`. Afirmar el texto nuevo pasa
igual si la jerga quedó tres líneas más abajo — es el conjunto ENCONTRADO
contra el DECIDIDO (corolario 60) aplicado al vocabulario.

### Y el género viaja con la unidad, o sale "¿Cuántos unidades?"

Detalle chico y lo agarró el test, no la lectura. La pregunta se armó pegando
`"Cuántos " ~ plural`, y el plural de los dos conteos es femenino mientras que
el de kilos es masculino. Leído se ve bien: la línea dice `¿Cuántos {{ plural }}`
y uno lee "¿Cuántos kilos", que es el caso que tenía en la cabeza.

El arreglo es que el mapa lleve **las dos palabras juntas**
(`{"unidad": ("unidades", "Cuántas")}`) en vez de que el género sea un acuerdo
tácito entre dos lugares — corolario 21 en una frase: el día que aparezca un
conteo masculino hay dónde ponerlo, en vez de que el texto salga mal y nadie
lo note porque nadie relee un rótulo.

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

   **PERO NUNCA PEGADA A UN `do`, y eso es lo que costó el 15/09.** Un bloque
   `do` y su verificación **se corren POR SEPARADO**. Pegados en la misma
   corrida el editor se queda con la última y **el `do` NO SE EJECUTA**: sin
   un error, sin un NOTICE, y con "no rows"… que es exactamente la salida
   normal de un `do` que sí corrió. El check de la coherencia del conteo
   quedó puesto en UNA base y no en la otra, y lo único que lo delató fue la
   verificación corrida aparte, que dio `guarda 1` de un lado y `guarda 0`
   del otro.

   Las dos mitades de la regla tiran para lados opuestos y hay que tenerlas
   juntas: **el que ESCRIBE necesita que algo devuelva filas** (si no, no hay
   con qué distinguir "corrió" de "no corrió"), y **el que EJECUTA no puede
   poner esa consulta en la misma corrida que el `do`**. La salida es correr
   dos veces, no escribir un archivo más prolijo.

   Y por eso la verificación **vale doble cuando se corre en las dos bases**:
   dos `guarda` distintos son la única forma de ver un `do` que se salteó, y
   ninguna cantidad de mirar la pantalla del editor lo habría mostrado.
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

**Y el CÓDIGO VA ARRIBA, la explicación al pie.** Corolario del punto 4, del
15/09: la primera versión de esa migración tenía **1486 caracteres de
comentario antes del `do`** y 790 de código. Cualquier corte que caiga antes
del `do` deja un archivo que es **puro comentario** — corre bien, no da error,
y devuelve "no rows". Medido cortando el archivo a los 1000 caracteres: el
viejo salía mudo, y el nuevo —con el bloque arriba— da `unterminated
dollar-quoted string`, que es un error que se lee.

O sea que el orden adentro del archivo decide **de qué manera falla un corte**:
con el código arriba, un corte rompe ruidosamente o no rompe nada; con los
comentarios arriba, el caso silencioso existe. No cuesta nada y se elige una
sola vez.

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

5. **Y `rev-list 0 0` contesta "¿SUBIÓ?", no "¿SALIÓ?".** Del 20/09, y es
   del dueño: *"yo estuve tres horas mirando una versión de anoche creyendo
   que probaba lo nuevo"*.

   Desde que el switch **"Wait for CI"** de Railway está prendido, entre el
   push y el deploy hay **una tercera cosa**: la corrida del CI. Con esa
   corrida en rojo, el push sale perfecto, `rev-list` da `0 0`, el commit
   está en `origin/main` — y **no se despliega nada**. Las cuatro
   verificaciones que este archivo pide se cumplen todas, y las cuatro
   contestan la pregunta de antes del gate.

   Pasó así: un test se puso rojo el 19/09 a las 01:31 y **se pushearon
   CUATRO commits más encima sin mirar el CI una sola vez**, cada uno
   reportado como desplegado con su `rev-list 0 0` al lado. Lo que el dueño
   tenía en la pantalla era de la noche anterior, y las dos cosas que fue a
   buscar —el número del pie y el botón de Pase a segunda— eran justamente
   de los commits frenados.

   **LA REGLA, y es del dueño**: *en cada commit que se reporta, decir si el
   CI está VERDE. Si está rojo, va en la PRIMERA LÍNEA y no se sigue
   construyendo encima.*

   Y el diagnóstico que la hace necesaria: **el gate hizo exactamente lo que
   tenía que hacer.** No falló ninguna máquina. Falló que nadie lo mirara —
   que es la misma familia del push silencioso, corrida un paso más adelante:
   antes lo que no se miraba era el estado de la rama, ahora es el estado de
   la corrida.

   **Cómo se mira, y cuesta una llamada**: la corrida del `head_sha` que se
   acaba de pushear, y su `conclusion`. Un `status: completed` con
   `conclusion: failure` es un deploy que no salió; un `in_progress` es un
   deploy que todavía no salió, que no es lo mismo que uno que salió.

   **Y una corrida COLGADA y una ROJA se ven igual desde el galpón** —en las
   dos el deploy no sale— y se arreglan distinto. Por eso lo que se reporta
   es la `conclusion`, no "el CI no pasó".

   **Y EL SELLO VA ANTES DE LA SUITE, no después (20/09).** El número de
   versión se sella con `commit → sellar_version.py → commit --amend`, así
   que hasta el 20/09 el orden era *suite, commit, sello, push* — y con ése
   **la suite NUNCA corre contra el número que se despliega**: acá la
   pantalla decía `v937` y el runner veía `v938`.

   No es un detalle de prolijidad. **El pie está en las 131 pantallas y su
   contenido cambia en cada commit**, así que cualquier assert por la
   negativa sobre una página entera tiene un vecino que se mueve solo.
   Costó una corrida roja: `assert "38" not in texto` —el total de un
   artículo que no tiene que aparecer— matcheó el `v938` del pie.

   **Y el modo de falla es exactamente el corolario 92**: pasa donde se
   escribe y se cae donde decide. Con el sello después, no hay forma de
   verlo acá; con el sello antes, la suite local mide el artefacto que sale.

   El orden, entonces: **commit → sellar → amend → SUITE Y HUMO → push**.
   Cuesta una corrida de dos minutos y es la única que mide lo que se
   despliega.

   Y del lado del test, la otra mitad: **un assert numérico por la negativa
   sobre una página va con `sin_pie(...)`**. Lo cuida un barrido que compara
   el conjunto ENCONTRADO contra el DECIDIDO, así que el próximo no depende
   de que alguien se acuerde.

6. **Y ANTES DE REPORTAR, SE ABRE UNA DE LAS PANTALLAS QUE SE TOCARON.** Del
   20/09, y es del dueño: *"hoy dos veces me dijiste 'hecho' sobre cosas que
   yo no podía ver"*.

   Se corre `python3 scripts/mirar_pantalla.py <ruta>`, que la renderiza
   contra el esquema REAL —reusando la siembra del humo, no una copia— y
   devuelve **el texto visible**, para leerlo.

   **Y NO ES EL HUMO OTRA VEZ**, que es lo que hay que entender o el paso se
   saltea por redundante: el humo afirma el CÓDIGO DE ESTADO de las 131
   pantallas —que abren, que su SQL parsea, que el handler corre— y **no
   afirma una palabra de lo que muestran**. Una pantalla a la que le borré su
   único botón contesta 200 igual y el humo la cuenta como ABIERTA. Son dos
   preguntas y la segunda no se deduce de la primera.

   **Lo que este paso NO cubre, y hay que decirlo porque es justo lo que pasó
   las dos veces**: el gate. Los dos "hecho" del 20/09 no fueron pantallas
   rotas —la suite estaba verde, el humo habría estado verde, la pantalla
   andaba— fue que **el CI estaba en rojo y el deploy no salió**. Eso lo
   contesta el punto 5 y nada más: un humo impecable sobre un commit frenado
   describe perfectamente una pantalla que nadie puede abrir.

   Los tres son preguntas distintas y ninguno reemplaza a otro:

   | | qué contesta |
   |---|---|
   | la **suite** | ¿la lógica hace lo que digo? (con la base mockeada) |
   | el **humo** | ¿las 131 abren contra el esquema real? |
   | **mirar la pantalla** | ¿la que toqué DICE lo que dije? |
   | la **`conclusion` del CI** | ¿esto va a salir al galpón? |

   **Y la identidad va pegada al texto** (corolario 53): el script imprime el
   status y el conteo de botones y formularios. Sin eso, la pantalla de
   "Falta la clave" se imprime igual de prolija que la buena — ya pasó dos
   veces en este proyecto, y las dos lo delató el denominador.

## Corolario 92: un test que mide el ENTORNO pasa donde se escribe y falla donde DECIDE

Del 20/09, y es el que produjo lo de arriba. El test del número de versión
afirmaba:

```python
assert del_git is not None and del_git.isdigit() and int(del_git) > 100
```

Se lee razonable —"que el git devuelva un número grande, o sea real"— y
**no describe la función: describe cuán profundo es el clon.**
`actions/checkout@v4` clona con `fetch-depth: 1`, así que en el runner
`git rev-list --count HEAD` devuelve **1**. Medido, no deducido: un
`git clone --depth 1` del propio repo ve **1 commit** y el clon de trabajo
ve **660**.

**Y el reparto de dónde pasa y dónde falla es el peor posible**: pasa en la
máquina del que lo escribe —que tiene el repo entero, el locale, el huso,
la red, el navegador— y falla en el runner, que es mínimo **y es el único
lugar donde el test decide si sale el deploy.** O sea que el modo de falla
no es "un test molesto": es un test que solo se rompe donde se cobra.

**LA SEÑAL, y es la única barata: el UMBRAL MÁGICO.** Un número en un assert
que no sale de nada del código —`> 100`, `< 5`, `>= 2`— casi siempre es un
proxy de *"el entorno que yo tengo"*. La pregunta que lo encuentra se hace
al escribirlo: **¿de dónde sale este número?** Si la respuesta es "porque mi
repo tiene 660 commits", "porque mi máquina tiene 8 núcleos" o "porque acá
son las 3 de la tarde", es el entorno y no la función.

**El arreglo es plantar el caso con un valor CONOCIDO** (corolario 36) y
exigir el número exacto: un repo de tres commits tiene que devolver `"3"`.
Eso no depende del checkout, y de yapa queda más fuerte que el umbral — un
`== "3"` falla donde un `> 100` pasaba.

**Y el plantado son TRES commits y no uno, a propósito**: con uno solo, el
caso shallow y el del repo entero dan lo mismo y el test no puede
distinguirlos. Es el rival del corolario que pide plantar el candidato que
NO tiene que ganar, en su versión más chica.

**La verificación que cierra es correr el test en LOS DOS entornos**: con el
clon shallow y con el entero. Uno solo no prueba nada — el viejo también
pasaba en uno de los dos.

Y la familia completa, para reconocerla sin el caso: profundidad del clon,
huso horario, locale, cantidad de núcleos, si el filesystem distingue
mayúsculas, si hay red, si hay un binario instalado. Todo lo que el que
escribe tiene y el runner no.

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

### Las TRES copias de `SUFIJOS_UNIDAD_COMPRA`, anotadas donde se buscan

Del 18/09. La tabla que traduce la unidad a su letra (`kilo` → `k`) está
escrita **tres veces**, y las tres son idénticas hoy:

    core/exportar_compras.py:35
    core/exportar_ingresos.py:41
    app/main.py:1068          ← la que usa el filtro `sufijo_unidad`

(Los números de línea envejecen en cada commit —el de `app/main.py` ya se
movió del 1004 al 1068 el 19/09, sin que nadie tocara la tabla—, así que lo
que se busca es `grep -rn "^SUFIJOS_UNIDAD_COMPRA" core/ app/`. Lo que no
envejece es el test que las compara.)

Decisión del dueño: **no urge y no se unifica hasta que haya que tocar
alguna** — son tres líneas iguales y moverlas ahora es riesgo sin beneficio.
Lo que sí va desde hoy es dónde están las tres, porque el que agregue una
unidad nueva va a editar la que tenga abierta y las otras dos van a decir
otra cosa: **la que se separe no va a fallar, va a imprimir un número sin
letra**, que es el hueco que no se ve.

Y lo cuida `test_las_TRES_copias_de_SUFIJOS_UNIDAD_COMPRA_dicen_lo_MISMO`,
que es el mismo patrón que el plegado de tildes: cuando dos copias no se
pueden unificar todavía, lo que impide que se separen no es que hoy
coincidan — es un test que las compara.

**Y la cuarta no se escribió**: el stock por kilaje necesitaba la letra y usó
el filtro `sufijo_unidad` que ya existe. Ese es el momento en que una copia
se convierte en cuatro, y es el único momento en que se puede evitar gratis.

### Y la copia que más se olvida es la que está EN ESTE ARCHIVO

Del 13/09, y es del dueño: **el que escribe la regla de buscar la otra copia
es el que más olvida buscarla, porque corrige donde está trabajando, y el
archivo de reglas nunca es donde está trabajando.**

El caso: la cola del corolario 56 decía *"hoy Comercial recibe un número que
no puede abrir"*. Era falso **desde el mismo día que se escribió** —esa misma
tarde se construyó `/comercial/alertas` con su `detallar`— y la frase se
corrigió en el comentario del test y no acá. O sea: se aplicó el corolario 2
sobre el código, y la copia que quedó vieja fue la del archivo que lo
explica.

**Por qué pasa siempre, y no es descuido**: al arreglar algo, el `grep` sale
sobre `app/`, `core/`, `templates/` y `tests/` — los lugares donde el arreglo
puede romperse. CLAUDE.md no se rompe nunca, no falla ningún test, y no está
abierto. Es exactamente la condición del comentario que envejece (corolario
28), con el agravante de que **este archivo se lee como el estado del mundo**:
un "hoy pasa X" viejo acá manda a construir lo que ya existe, o a no
construir lo que falta.

**Lo accionable, y es barato**: cuando un commit hace falsa una oración de
CLAUDE.md, esa corrección va EN EL MISMO COMMIT. Para encontrarla, lo que
sirve no es releer el archivo entero —nadie lo hace— sino grepear **el nombre
de la cosa que se tocó** (la alerta, la función, la pantalla) acá adentro,
igual que se grepea en el código.

**Y las oraciones que expiran se reconocen por el tiempo verbal**: las que
dicen *hoy*, *todavía no*, *no existe*, *no hay*, *queda anotado y no
construido*. Un corolario sobre un MECANISMO no envejece —el `count(*)` va a
seguir devolviendo una fila para siempre—; lo que envejece es el ESTADO que
se anota al lado para ilustrarlo. Al escribir una de esas oraciones conviene
saber que se está contrayendo una deuda, y al cerrarlas hay que volver.

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

#### Y LA FILA SE ANOTA EN `db/corridas_confirmadas.md`, no citada en un corolario

**LO VIEJO NO SE RECONSTRUYE, y es decisión del dueño (20/09).** El archivo
tiene 5 filas y hay 321 `.sql`: reconstruir cuáles corrieron es imposible de
memoria, y una lista inventada sería peor que una corta — el que la lea le va
a creer. Queda como está.

**Lo que cambia es de acá en adelante: cada migración se anota APENAS llega su
fila de verificación**, en el mismo turno, no al final del día. Es la misma
regla que la corrección de una oración de este archivo: en el momento, o no se
hace. Y el que anota es el que recibe la fila, no el que la corrió.

Del 18/09, y salió de una auditoría que no pudo contestar una pregunta que
tenía la respuesta en el repo: *"¿las tres migraciones de Vacíos corrieron en
Frutamax?"*. Habían corrido. Lo que faltaba era el registro — **la única fila
anotada era la de Palmala, y estaba citada adentro del corolario de abajo para
ilustrar cómo el testigo dice si una base vota.**

**Una fila citada para ilustrar no es un registro**, y la diferencia no es de
prolijidad: el que audita busca confirmaciones y no la encuentra, porque está
archivada bajo otro tema. El que la escribió tampoco se acuerda. Así que la
pregunta se vuelve irrespondible desde el repo y hay que ir a molestar al
dueño — que es justo lo que un registro evita.

**Y el costo de no tenerlo es el del corte**: sin poder contestar si una
migración corrió, la única salida honesta es tratar el código que depende de
ella como sospechoso. Con 24 verificaciones y dos bases, eso no escala.

**Por qué el registro NO va al pie de cada `.sql`**, que es donde uno lo
pondría: esos archivos se pegan en el editor de Supabase y ninguno puede pasar
los 2500 caracteres. Varios están a menos de cincuenta del límite, así que
cuatro líneas de registro adentro los volverían intruncables — se arreglaría
el registro rompiendo la migración. Va en un archivo aparte, que no se pega en
ningún lado y no tiene límite.

#### Y el TESTIGO dice la BASE; el NOMBRE de la migración dice cuál es (18/09)

El testigo cubre una sola de las dos formas de confundir dos filas, y el 18/09
apareció la otra: **dos filas de la MISMA base y de DOS MIGRACIONES distintas**
se leyeron como las dos bases de una. `1 · 1 · 0 · población · testigo` es el
resultado bueno de cualquiera de las 24 verificaciones de este repo, así que
con el testigo puesto las filas siguen siendo indistinguibles *entre
migraciones* — el testigo contesta "de qué base", no "de qué migración".

Costó un corte de producción: se pidieron las cuatro filas, llegaron dos, se
leyeron como las dos bases al día, y se mergeó código que dependía de una
migración que no había corrido en ninguna. La pantalla de armar pedidos tiró
`column r.cantidad_original does not exist` a la mañana siguiente.

**Y la segunda mitad casi se repite en espejo el mismo día**: llegó UNA fila,
que podía leerse como "las dos bases". Lo que la identificó fue la población
—1921 es Frutamax, 1103 es Palmala— o sea el testigo haciendo otra vez el
trabajo de identificar en vez de el suyo.

Por eso, desde el 18/09, **las 24 verificaciones abren con
`'<nombre_de_la_migración>' as QUE_MIGRACION`**, como primera columna. Es lo
primero que se lee al pegar la fila, y no hay que acordarse de nada:

```
renglon_agregado_a_mano     · 1 · 1 · 0 · 1921 · 19/09
renglon_cantidad_corregida  · 1 · 1 · 0 · 1921 · 19/09
```

Las dos filas de arriba son de la MISMA base y se ve. Antes eran idénticas.

**Las dos columnas son de trabajos distintos y hacen falta las dos**: el
testigo dice de qué BASE, el nombre de qué MIGRACIÓN. Con una sola, la
confusión se muda a la otra dimensión — que es exactamente lo que pasó entre
la mañana y la tarde del mismo día.


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
caracteres. `arts_mezclados` dio **0**: ningún artículo tenía dos tamaños de
cajón conviviendo, así que **el Remanente ya sumaba bultos comparables** y no
había nada que desglosar. Ver `docs/desglose_del_remanente_por_contenido.md`.

**Y EL 18/09 SE RETOMÓ, que es exactamente lo que el propio documento decía
que iba a pasar** (*"si algún día se compra el mismo artículo en dos formatos,
esta consulta lo va a mostrar y se retoma"*). `kilajes_1` encontró cinco
artículos multiformato en las dos bases. **No es que la medición del 08/09
estuviera mal: es que `remanente_1` recorta DESDE EL CORTE**, o sea tres días
de compras el día que se corrió, y `kilajes_1` mira noventa. Las dos son
ciertas sobre su ventana, y una sola de las dos contesta "¿este artículo se
compra en más de un formato?".

Eso deja el aviso para la próxima vez que una consulta barata borre una
pantalla, y es la mitad que a este corolario le faltaba: **antes de dar por
inexistente un caso, mirar contra qué VENTANA se lo buscó.** Un cero sobre
tres días de compras no dice lo mismo que un cero sobre noventa, y los dos se
imprimen igual. Es el corolario 69 —el recorte de la medición no es el de la
decisión— del lado de NO construir, que es donde no deja rastro: la pantalla
que no se hizo no se queja.

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

### Y "NO VOTA" ES POR MEDICIÓN, NO POR BASE (18/09, y es del dueño)

Los dos párrafos de arriba están escritos como si *"Palmala no vota"* fuera
un **atributo de la base**, y así se venía aplicando desde el 09/09: se
descartaba de entrada cualquier número que saliera de ahí. **Eso es un
recorte de más, y el mecanismo del corolario 24 nunca dijo eso.**

Lo que el 24 dice es que **el TESTIGO decide**, y cada medición tiene el
suyo: la última recepción, la última guía R, el último pedido armado. Son
preguntas distintas y pueden contestar distinto sobre la misma base. Una
base puede estar quieta para los armados y en marcha para las recepciones —
y entonces **vota en una medición y no en la otra**.

**El caso que lo destapó**, y es la mejor prueba de que el atajo estaba mal:
la verificación de la migración de Vacíos trajo, el 18/09,

    PALMALA  1·1·1·1·1·1·1·1 · 44 proveedores · última recepción 17/09

y ese testigo es `max(procesada_el) where estado = 'recepcionado'` —
**exactamente la misma pregunta** que sostiene el *"no recepciona desde el
01/09"* de este archivo. Palmala recepcionó ayer. O sea que toda medición
sobre RECEPCIONES que se descartó ahí en los últimos días se descartó sin
mirar su testigo.

**Cómo se aplica, y cuesta lo mismo que descartarla a mano**: antes de
decidir si una base vota, mirar **el testigo de ESA medición** —no el que
uno recuerda de otra— y su POBLACIÓN. `pesaje_1` trae `recepciones_2d` y
`recepciones_7d` justamente para eso: con números parecidos a los de
Frutamax el resultado es un dato, y con 2 sobre 5 el cero de al lado se
descarta, pero **descartado por su propio denominador y no por el nombre de
la base**.

**Y ES LA ORACIÓN QUE EXPIRA, en su forma más cara.** El MECANISMO —una base
quieta contesta cero a todo— no envejece nunca. Lo que envejeció es el
ESTADO que se anotó al lado para ilustrarlo, y como ese estado se escribió en
imperativo (*"lo que hay que mirar es Frutamax"*) se leyó como regla. Un
estado con forma de regla es peor que un estado: **nadie lo vuelve a
verificar, porque las reglas no se verifican.**

La forma de escribirlo que no expira es la que este corolario tiene arriba:
*el testigo dice si la base vota*. La que expira es *esta base no vota*.

**CONFIRMADO el mismo día, y no era chico lo que se estaba descartando**:
`pesaje_1` sobre Palmala dio **70 recepciones en 7 días y 240 en 90** —
población de sobra— y **16 de 40 sin ninguna evidencia de pesaje en dos días,
contra 6 de 44 en Frutamax**. O sea que la base "que no vota" tenía la tasa
TRIPLE, y el atajo de descartarla por nombre venía tapando el número más
grande de los dos. Ver "El pesaje" más arriba.

Y la mitad que no cambia: **Palmala sigue sin votar en guías R y en
armados**, porque esos testigos siguen diciendo lo que decían. Las dos cosas
son ciertas sobre la misma base al mismo tiempo, y eso es exactamente lo que
un atributo de la base no puede expresar.


#### Y EL 19/09 EL DUEÑO LA CERRÓ PARA ESTE PERÍODO: Palmala no vota, y punto

Del 19/09, y es una decisión suya, con fecha: *"Palmala no está funcionando y
no vota para nada. Dejemos de medir contra esa base."*

**Eso NO contradice lo de arriba: lo aplica.** El mecanismo sigue siendo el
del 24 —el testigo decide— y lo que el dueño está declarando es un HECHO DEL
NEGOCIO que ningún testigo nuestro puede ver: **esa base dejó de operar.** Un
testigo dice cuándo fue la última recepción; **no dice si va a haber otra**.
Eso es el corolario 84 —lo que el dueño sabe del galpón se le pregunta, no se
le discute— y la recepción del 17/09 que el 18/09 hizo votar a Palmala era la
cola de una base que se estaba apagando, no la señal de una que anda.

**Y va escrita con su condición de vencimiento, para no repetir el error que
esta misma sección describe**: el 09/09 se escribió *"lo que hay que mirar es
Frutamax"* en imperativo, se leyó como regla, y nadie la volvió a verificar en
nueve días. Así que acá queda como lo que es —un ESTADO, con dueño y con
fecha—:

> **Desde el 19/09 y hasta que el dueño diga lo contrario, ninguna medición
> sobre Palmala vota.** Lo que la reabre es que él avise que esa base volvió a
> operar; no un testigo que dé una fecha reciente.

**Lo que Palmala sigue sirviendo es lo de siempre, y es real**: confirmar que
una migración no explota. Un `alter table` corre igual sobre una tabla quieta,
y si los dos esquemas se separaron, ahí se ve. Eso no es medir: es probar que
el SQL parsea contra ese esquema.

**Y lo que costó no tenerlo escrito, el mismo 19/09**: el 89% de renglones sin
tildar de Palmala me llevó a una conclusión sobre CÓMO SE TRABAJA que era un
artefacto del abandono. El mecanismo está en el corolario 88 —una base parada
contesta casi todo a una medición de AUSENCIA, y ahí el testigo no salva,
porque la población está de verdad.
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

   **Y CUÁL escalón va lo decide si el caso riesgoso es el NORMAL o la
   EXCEPCIÓN**, que es la precisión que le faltaba a este punto y la puso el
   dueño el 18/09 sobre "vino armada". El tilde sirve cuando el caso normal
   es un click —la fecha del mail está bien casi siempre— y la excepción es
   rara: ahí un paso más se lo cobra a todos para atajar a uno. Cuando la
   marca **es** la excepción —son pocas por mes y la de todos los días es no
   marcarla— el que corresponde es el modal que obliga a leer: no le cuesta
   nada al caso normal, porque el caso normal no pasa por ahí.

   Y hay una segunda diferencia entre los dos, que es la que hace que un
   tilde no habría alcanzado acá: **el tilde pregunta "¿estás seguro?" y el
   que se equivocó también está seguro.** Lo que frena el dedazo no es
   confirmar: es LEER qué dice la marca. Por eso el texto del modal cuenta
   las dos consecuencias —se genera una guía R sola, esas cajas salen del
   stock— y dice con todas las letras cuándo NO va.

   **Y HAY UN TERCER CASO, del 19/09 y también del dueño: que la acción
   riesgosa sea la LEGÍTIMA Y FRECUENTE. Ahí no va ningún escalón — va el
   AVISO, arriba del campo.** Cambiar el precio de una compra ya recepcionada
   recostea hacia atrás todo lo que el FIFO le atribuye a ese lote, y aun así
   **es lo que hay que hacer casi siempre**: el comprador renegocia. Un
   `confirm()` ahí *"lo pasa el caso normal todas las veces"*, o sea que se
   lo cobra a todos y no ataja a nadie — es el escalón que se aprende a
   esquivar, que es la forma de no tener ninguno.

   Los tres, entonces, y lo que los ordena es la FRECUENCIA de lo riesgoso:

   | lo riesgoso es… | qué va |
   |---|---|
   | la excepción rara, y el caso normal es un click | el **tilde** |
   | la excepción, y el caso normal ni pasa por ahí | el **modal** que obliga a leer |
   | **la acción legítima de todos los días** | **ningún escalón: el aviso, ANTES del campo** |

   Y la tercera fila sale de la misma frase que las otras dos —*el que se
   equivocó también está seguro*— llevada un paso más: si la acción es
   legítima, **no falta una decisión, falta información.** Preguntar "¿estás
   seguro?" sobre algo que se hace todos los días no agrega ninguna, y lo que
   sí agrega es decir qué se lleva puesto y nombrarlo —acá, las guías R que
   quedan con su costo congelado—. Por eso el aviso va ARRIBA: debajo del
   campo llega cuando el número ya se tipeó.

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

### El TERCER disfraz: la operación existe, pero solo su versión DESTRUCTIVA

Del 19/09, y es del dueño en una frase: *"la única salida hoy es anular y
recargar. Es la tercera vez esta semana que algo se arregla así."*

**Corregir la fecha de una guía R** no era un `.sql` a mano ni una ruta sin
botón: se podía hacer, con dos clicks, desde una pantalla que está a la
vista. Anular y volver a cargar. O sea que las dos señales que este corolario
enumera —el archivo que se repite y el barrido de pantallas sin link— salen
las dos en verde, y la operación igual falta.

**Cómo se reconoce, y es lo único nuevo**: el que la hace **paga un costo que
no tiene nada que ver con lo que quería cambiar.** Acá quería mover un día y
tenía que borrar los consumos, el costo congelado y el número de guía, y
rearmar todo a mano. Esa desproporción es la señal, y es la misma forma del
corolario 29 al revés: allá una prueba costaba más que la función y delataba
un requisito inventado; acá una corrección cuesta más que el dato que corrige
y delata una función que falta.

La pregunta que lo encuentra, y se hace cuando alguien cuenta cómo arregló
algo: *¿lo que tuvo que deshacer es lo que quería cambiar?* Si no, la
operación suave no existe.

### Y LAS GUARDAS DE UNA CORRECCIÓN SON LAS DE LA CREACIÓN (19/09)

La parte de diseño, y vale para cualquier pantalla que corrija un dato que
en su momento pasó por un freno.

Mover la fecha de una guía R tiene que preguntar **exactamente lo mismo** que
preguntó la carga: *"¿habría entrado ese día?"*. Escrito de nuevo en la
puerta de la corrección, eso es la regla escrita dos veces en su forma más
cara — **la copia que se separe deja entrar por una puerta lo que la otra
rechaza**, y nada se pone rojo, porque cada una es correcta por separado.

Así que los dos frenos salieron de `_crear_reproceso` a una función que los
dos caminos llaman (`_lotes_de_reproceso_a_su_fecha`), y **el test de
cableado pasó de tres lectores a CUATRO**. Lo que lo demuestra no es que hoy
coincidan: es que sacarle el filtro a esa única función haga caer a los
cuatro.

**Y la forma de que la pregunta sea literalmente la misma es ESCRIBIR
PRIMERO y validar después**, adentro de la misma transacción. Con la guía ya
puesta en la fecha nueva, su propia toma queda fuera del recorte y su propia
primera es un lote prohibido para una guía R: no puede costearse a sí misma
por ninguno de los dos lados, y no hizo falta escribir ninguna regla nueva
para eso. Si la validación rechaza, la excepción sale y no se commitea nada.

**Lo único que la corrección agrega de propio es la revisión LOTE POR LOTE**,
y es el caso que el freno del total no puede ver: la suma entra y el lote que
el documento congelado nombra puede ser de un día posterior al nuevo. El
freno mira un número; esto mira los nombres. Es el corolario 13 otra vez —un
total exacto deja de contestar la pregunta apenas la pregunta se afina.

### Y el 18/09 se construyó en la PRIMERA, por pedido del dueño

*"Esta es la primera vez y va a haber una segunda."* Una compra de Pera
quedó marcada como "vino armada en caja nuestra" contra una ficha de envase
perdido, y **Editar Compra está bloqueada para las recepcionadas**, así que
no había pantalla que pudiera sacarle la marca.

El criterio es el mismo que el de las fichas borradas —**medir antes de
construir la CURA; no antes de cerrar la PUERTA**— aplicado a una tercera
cosa: acá la puerta ya estaba cerrada (2770e7c) y lo que faltaba era el
camino para lo que ya había entrado. El `.sql` de un solo uso
(`db/cajas_12_*.sql`) y la pantalla se hicieron el mismo día, y el `.sql`
sigue siendo el que corrige ESA fila: la pantalla es para la próxima.

**DÓNDE va la puerta se decidió por la PRECONDICIÓN, no por comodidad.**
Desmarcar exige que la guía R esté anulada, y anular vive detrás de la clave
de Administración. En Buscar Compras —que es donde se MARCA y no tiene
clave— habría sido ofrecer algo cuya precondición el que lo ve no puede
cumplir: el corolario 56, el link que manda a una puerta ajena. En Corregir
Recepción, además, **la precondición ya estaba escrita**: esa función rebota
con la misma guía viva y con el mismo mensaje, así que el desmarcar la reusa
en vez de estrenar una segunda copia.

**Y la inversa NO es simétrica, a propósito.** Marcar carga la guía R en la
misma transacción; desmarcar **no anula nada** y exige que la guía ya no
esté. Anular tiene su propia pantalla, y hacerlo también acá sería la misma
operación escrita dos veces — la copia que se separe anularía guías que la
otra puerta no anula. Lo cuida un test que lee el CUERPO de la función y
exige que la palabra no esté: con la guía viva rebota antes de llegar a
ningún UPDATE, así que un test de comportamiento pasa igual con un
`anulado_el = now()` escrito adentro.

**Y el botón solo aparece donde la escritura ACEPTA**: con la guía viva se
muestra cuál anular y no hay botón. Las dos mitades preguntan por el mismo
filtro y hay un test que lo exige en las TRES funciones que lo usan —
ofrecer algo que el POST después rechaza es un callejón, y eso es peor que
no ofrecer nada.

### Y la puerta no es el arreglo del dedazo: el arreglo es que cueste ponerlo (18/09)

Desmarcar es la CURA. Lo que faltaba era que la marca no se pusiera sola, y
el pedido del dueño fue el escalón que corresponde: **un modal que explica
qué significa la marca, en los DOS lugares donde se pone** —"si está en uno
solo, el dedazo entra por el otro"—.

Enumeradas con `ast` desde `app/main.py`, las que escriben
`ficha_en_origen_id` son **siete superficies en seis rutas**: el alta, la
manual, cada renglón de la comanda, la edición, el ingreso directo de
Depósito, el retroactivo de Gerencia y el botón "Vino armada". Las seis
primeras pasan por `_caja_en_origen.html`; la séptima tiene su `<select>`
escrito a mano. **Las siete pasan ahora por el mismo modal**, y lo cuida un
test que compara el conjunto ENCONTRADO contra el DECIDIDO en vez de una
lista escrita a mano — la octava pantalla no la va a recordar nadie.

**Y la comanda MÚLTIPLE no podía marcar**, medido y no deducido: su
fragmento llega por `innerHTML`, que no ejecuta los `<script>` que trae, así
que el bloque quedaba en `display: none` de verdad y el selector no aparecía
nunca. Era un agujero aparte —una función que existe y nadie puede usar— y
**se arregló el mismo 18/09**: ver el corolario 83. Las siete superficies
pueden marcar y las siete pasan por el modal.

### Y DESDE EL 17/09 HAY UN TEST, porque la variante peor es la ruta sin botón

`/compras/cajas` se construyó entera —migración en las dos bases, pantalla,
dieciséis tests— y **el botón nunca entró al hub**. El dueño no podía cargar
el conteo inicial, que es lo único que hace arrancar toda la cuenta de cajas.

Es peor que el `.sql` a mano porque **no deja rastro**: no hay un incidente
que se repita, no hay un archivo que alguien vuelva a abrir. La ruta existe,
responde 200, tiene sus tests en verde, y nadie llega. **Todos los tests
entran por la URL**, así que la ausencia de puerta es invisible para la
suite entera por construcción.

Lo cuida `test_TODA_pantalla_de_un_sector_esta_LINKEADA_desde_algun_lado`, y
las dos decisiones de su diseño son las que lo hacen usable:

- **Mira "linkeada desde algún lado", no "desde su hub".** Una pantalla
  colgada de otra —el detalle de un colega, la edición de un artículo— es
  alcanzable, y exigirle un botón en el hub llenaría el hub de cosas que se
  abren desde adentro. Lo que no puede pasar es que no la linkee NADIE.
- **Compara el conjunto ENCONTRADO contra el DECIDIDO** (corolario 60), con
  la razón escrita al lado de cada excepción. Falla cuando aparece una
  pantalla que nadie decidió dejar suelta **y** cuando una de la lista pasa
  a estar linkeada, así la lista no protege algo que ya no pasa.

Y el barrido encontró de yapa lo que un hallazgo suelto no da: **los falsos
positivos son informativos.** Dos exportables figuraban sin link y sí lo
tienen —el href se arma con `{{ contexto.base }}`, que un regex literal no
puede resolver—, y `/compras/nueva` renderiza una pantalla que nadie linkea
y quedó en la lista **marcada como deuda y no como excepción legítima**.

### Y LA VARIANTE QUE EL BARRIDO NO PUEDE VER: la puerta que se abre para un SUBCONJUNTO (19/09)

El test de arriba pregunta si la pantalla la linkea **alguien**. El detalle por
artículo (`/administracion/stock/sistema/{id}`) **estaba linkeado** —desde los
dos bloques del Remanente, ESPERANDO guía R y NEGATIVOS— así que el barrido
salía en verde. Y no había forma de llegar para un artículo **sano**, que son
casi todos.

**El subconjunto era justo el equivocado**: se entra a ver de qué formato es lo
que queda cuando el número se lee raro, no cuando el artículo ya está marcado
como problema. La única puerta se abría para los casos que no motivan la
pregunta.

**Y se ve idéntica a una puerta**: la ruta existe, responde 200, tiene sus
tests, y desde el Remanente se llega. Lo que falta no es el link — es el link
**para la mayoría de las filas**, y eso ningún conteo de "¿la linkea alguien?"
lo puede expresar.

**La pregunta que lo encuentra**, y se hace al escribir el link: *¿para qué
FRACCIÓN de las filas existe este camino?* Si la respuesta no es "todas", la
que falta es la fracción que hay que nombrar. Es el corolario 45 corrido a los
caminos — un conteo de puertas sin su denominador no se puede leer.

**Y dónde va el camino lo decide la PUERTA, no la comodidad.** Lo natural era
colgarlo del renglón de Stock del Depósito, que es de donde viene el que
pregunta. `puerta_de_administracion` cubre **los GET** —no solo los POST, como
la de Compras— así que ese link mandaría al operario contra una clave que no es
suya (corolario 56). Se colgó de Movimiento, que ya está adentro del prefijo.

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

**Y VOLVIÓ EL 25/09 POR EL OTRO LADO: la orden de MOSTRAR se fue.** El
selector de colega de Cajas nace `hidden` y lo muestra un script al elegir un
movimiento de colega. En el rearmado del 20/09 el `<script>` se borró junto
con el bloque viejo y no volvió: la opción estaba en el selector, el POST la
aceptaba, el colega estaba cargado, y **no había forma de elegirlo**. Lo
destapó el dueño usándolo, cinco días después. Ahora lo cuida un test en
navegador que entra por `/compras` Y por `/administracion` —la `action` lleva
el prefijo, y el selector viejo por la action exacta solo andaba en una— y
pregunta `getComputedStyle` en las dos direcciones.

**La señal, para el próximo rearmado**: si una plantilla tiene un `hidden`
que algo tiene que sacar, `grep` de quién lo saca. Un `hidden` sin nadie que
lo toque es un campo que no existe.

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

**Y "NO SE USA" es la misma negativa con otra ropa, con un daño distinto: en
vez de mandar a construir, manda a BORRAR.** Del 12/09: se escribió que
`_desambiguar_cajas` quedaba sin usar porque no se la aplicó a una pantalla
nueva. Tiene **dos llamadores vivos** (el desglose de stock y el selector de
ficha de la guía R), y un `grep` de un segundo lo dice.

Lo que quedó sin usar era **aplicar el patrón en ese lugar**, que es otra
cosa — y la diferencia entre las dos frases es una función borrada. Antes de
escribir que algo no se usa, grepear el NOMBRE, que es el corolario 8 (el
grep de la función, no el del concepto) usado para no romper en vez de para
encontrar.

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

**Lo que quedó**: dos artículos que no pueden tener referencia —Mango, que
viene en cajas de 40, de 12 y de 10 unidades, y Tomate Cherry, en cajones de
5 a 15 kg— y **dos compras con cajones faltantes**, que son las que
importaban desde el principio. (Esta línea decía que la referencia de Mango
estaba "mal" y que su mediana era 40. Las dos cosas se cayeron el mismo día:
ver **Mango y Cherry son MULTIFORMATO** más abajo.)

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
casi todos, y los dos que no pueden tenerla —Mango y Cherry— **van vacíos,
los dos por la misma razón**: no tienen valor dominante. (La primera versión
de esta línea mandaba Mango a 40. Se cayó el mismo día; va abajo.)

### Mango y Cherry son MULTIFORMATO, no referencias mal cargadas (12/09)

Corrección de la conclusión de arriba, y **no sale de una medición nueva:
sale de preguntar en el galpón.** El mango se compra en cajas de **40
unidades, de 12 y de 10**, según el día y el proveedor. No hay un valor
dominante.

Entonces la referencia en 10 **no está mal**: está eligiendo uno de los tres
formatos. Y ponerla en 40 —que era la corrección pendiente— la haría estar
mal las otras dos veces, y encima más mal que hoy: 40 es el formato más
grande, así que el error de precargarlo es el más caro de los tres.

Los dos van **vacíos**, y es la regla de esta misma sección aplicada al pie
de la letra: precargar sirve cuando hay un valor dominante y estorba cuando
no lo hay. Sin dominante el precargado va a estar mal siempre, y precargar
mal es justamente lo que invita a aceptar mal. Vacío, el campo pregunta en
vez de proponer.

**Y es una CATEGORÍA distinta, no un caso más de referencia vieja**, que es
lo que hay que llevarse:

| | qué le pasa a la referencia | qué se hace |
|---|---|---|
| **Referencia vieja** | hay un valor dominante y el cargado no es ése | se corrige al dominante |
| **Artículo MULTIFORMATO** | no hay valor dominante | se deja vacía |

La medición vieja no las distingue: las dos se ven igual, como un desvío
grande entre el estimado y lo pesado. **El que lea "Mango, desvío +30" sin
esto al lado va a querer corregirlo a 40**, que es exactamente lo que se
acaba de decidir que no va.

#### Lo que la consulta SÍ mostró, y se leyó como otra cosa

`kilos_3` devuelve `minimo` y `maximo` al lado del promedio y la mediana.
Para Mango eso dio un rango de **12 a 54**, y se leyó como dispersión
alrededor de un valor mal cargado. Un rango de 12 a 54 en un artículo que
viene en tres formatos **no es dispersión: son los tres formatos** — y eso
era distinguible de la otra lectura ahí mismo, en la fila que ya estaba a la
vista. Corolario 19 otra vez: la salvaguarda estaba puesta, el dato estaba
en la fila, y se leyó lo que se esperaba encontrar.

**Y la mediana, que está en esa consulta a propósito para que un caso raro
no mueva el diagnóstico, sobre un artículo multiformato no contesta nada**:
devuelve el formato que más vino en la ventana, y se mueve sola el día que
cambia la mezcla de proveedores. Un estadístico de centro sobre una
población que en realidad son tres se lee perfecto y no significa nada. Es
el corolario 13 con otra ropa — una fórmula exacta sobre el conjunto deja de
contestar la pregunta apenas el conjunto no es uno solo.

#### HECHO el 12/09: las dos referencias están vacías

Lionel las vació desde `/articulos`. Y hay una consecuencia que conviene
saber antes de extrañarlos:

**`kilos_3` y `kilos_4` filtran las dos por `contenido_referencia is not
null`, así que Mango y Cherry ya NO APARECEN en ninguna.** No es que su
desvío pase a dar cero: la fila se va, y eso es lo correcto —sin referencia
no hay contra qué comparar, que es justamente por qué se vaciaron— pero se ve
igual que si hubieran dejado de tener problema.

(Esto decía *"el que corra `kilos_4` el 25/09 no los va a encontrar"*. **Nadie
la va a correr**: el 22/09 el dueño la retiró, porque la referencia no se
ajusta por medición. El mecanismo —vaciar un campo saca a esa fila de toda
consulta que filtre por él— no se mueve, y es lo que esta sección enseña.)

**Vaciar la referencia los saca de la vigilancia, y ése es el precio de la
decisión.** Está bien pagarlo: un promedio contra un valor que no existe no
contesta nada. Lo que NO hay que hacer es devolverles un número para que
vuelvan a aparecer en la consulta — eso sería mover el mundo para que entre
en la medición.

Lo único que lo deja ver es la columna `arts_con_referencia` de `kilos_3`,
que es la población: baja en dos y ahí se nota que se fueron. Es el
denominador del corolario 45 haciendo un trabajo que no era el suyo —
avisar que alguien salió del conjunto.

**La señal, y es la misma que la de "La señal que inventé, y que falló en el
caso que la generó", más abajo en esta sección**: antes de leer
un valor como un error de carga, preguntarse **qué GENERA los valores.**
Allá un valor REPETIDO entre artículos que no se parecen resultó ser el
cajón estándar del mercado y no un default copiado; acá un valor DISPERSO
adentro de un mismo artículo resultó ser tres formatos y no una referencia
vieja. Las dos veces la forma de los datos parecía un error del sistema, la
explicación estaba en cómo se compra la fruta, y **se contestó preguntando,
no midiendo de nuevo.**

### La precarga de Recepción: CERRADO por el dueño el 23/09, no se toca

**Es una DECISIÓN, no un pendiente.** El hecho sigue siendo cierto y se deja
escrito para que nadie lo "descubra" de nuevo: Recepción precarga los dos
campos reales con el estimado (`deposito_recepcion.html`, `value="{{
c.cantidad_cajones }}"` y `value="{{ c.contenido_por_cajon }}"`), así que
apretar "Recibir" sin tocar nada graba `real = estimado`.

> **No se va a cambiar.** Con el cartel de "¿lo pesaste?" alcanza: el que
> aprieta derecho se entera, y eso es lo que el dueño quería.

**Qué la cerró, y por qué no se reabre con un número**: esta nota llevaba
tres semanas como "anotada y no construida" esperando una razón para hacerse.
Las dos que la volvían interesante ya estaban contestadas por otro lado —la
referencia no se ajusta por medición, y la evidencia del pesaje es la foto
(ver `kilos_4`, retirada el 22/09)— y lo que quedaba era el riesgo de que
nadie mirara. Eso lo tapa el modal de las dos puertas que recepcionan. **Lo
que la precarga todavía hace** —grabar el estimado cuando alguien elige no
pesar— ya no es un accidente: es una decisión que el que recibe toma leyendo.

**Si dentro de seis meses alguien mide cuántas recepciones tienen `real =
estimado` y el número le parece grande: ya se sabe, y no mueve nada.** Un
`real = estimado` no distingue "lo pesaron y dio eso" de "lo aceptaron", y
eso no lo arregla sacar la precarga — lo que lo distingue es la foto, y para
eso está la alerta `recepciones_sin_pesaje`. Retomar esto necesita que el
dueño cambie de opinión, no una consulta.

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
| **Referencia mal cargada** | el sistema sugiere mal para ESTE artículo | 2 artículos (Mango y Cherry) | al vaciar la referencia — los dos son multiformato, no se corrigen a un número |
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

## Una guía R con `primera = 0` es un PASE A SEGUNDA por la puerta equivocada

Del 20/09. El depósito tiene diez cajones de berenjena que se pusieron feos:
no están para tirar, pero ya no son primera. **No había ninguna pantalla para
eso**, así que lo cargaban con una guía R de reproceso con `primera = 0` —
la única puerta que encontraron.

**Y los números que produce esa puerta están BIEN**, que es lo que hay que
entender antes de tocar nada. Una guía con tomados 10 / primera 0 / segunda
10 deja:

```
stock      −tomados + primera = −10   (la pata del reproceso no filtra por tipo)
pool       + bultos_segunda   = +10
costo      costo_por_bulto_primera en NULL: la plata se pierde
cajas      bultos_primera = 0, o sea ninguna caja nuestra consumida
```

Lo que está mal no es la cuenta: es **el nombre, y que ocupe una guía R**.

**Medido antes de construir** (`db/primera_cero_1_cuantas_son.sql`, Frutamax,
90 días): `población 395 · PRIMERA_EN_CERO 2 · cajones 18 · plata que no se
pega $670.000 · todo_a_SEGUNDA 2 · todo_a_MERMA 0 · mixto 0 · NI_UNA_NI_OTRA
0 · última guía 19/09`.

**Y la consulta no solo midió el tamaño: probó el diagnóstico.** Partida por
a dónde fue la fruta, las dos cayeron en `todo_a_SEGUNDA` y ninguna en
`todo_a_MERMA` ni en `NI_UNA_NI_OTRA`. Con mermas ahí, lo que faltaría sería
otra cosa —gente esquivando la pantalla de merma, que existe— y con casos sin
destino serían cajones que salieron sin que nadie diga adónde. **Un conteo
solo habría dicho "son 2" y mandado a construir sobre una hipótesis.**

### Las dos que YA ESTÁN se dejan, y por eso hay que anotarlas acá

Decisión del dueño, con fecha: **los `reprocesos` con `tipo = 'normal'` y
`bultos_primera = 0` anteriores al 20/09 son pases a segunda hechos por la
puerta equivocada.** No se corrigen — corregirlas sería anular y recargar por
la puerta nueva para mover los mismos números a otra tabla, perdiendo las
guías R que ya existen y sin que ninguna cuenta cambie.

**Y por eso la nota vale más que el arreglo**: dentro de seis meses, un
`primera = 0` en esa tabla es un misterio, y el que lo encuentre va a buscar
un bug en el costeo que no existe. Es la frase que este archivo pide cada vez
que algo se deja como está: lo que no se corrige se explica, o se paga en la
próxima lectura.

### Dónde va la puerta nueva, y lo decidió un NÚMERO y no el gusto

`movimientos_stock`, con un `tipo = 'pase_a_segunda'`. La alternativa era un
`tipo` nuevo en `reprocesos`, que **no costaba ni un cambio de cuenta** —la
pata del stock y la del pool no filtran por tipo, así que habría andado
solo—. La descartó el conteo: **36 consultas leen `reprocesos`**, y cada una
que se olvidara el filtro mostraría el pase como una guía R. Es un filtro del
que hay que acordarse en 36 lugares para siempre, contra una cirugía de
CHECKs que se hace una vez.

A favor de `movimientos_stock`, además: su pata del stock ya es
`tipo <> 'reingreso_rechazo'`, así que un tipo nuevo se resta solo; y la
pantalla de Movimientos **no tiene un `else` que afirme** —lo dice su propio
comentario— así que un tipo que no conoce no se dibuja como otra cosa.

### El UNO A UNO se preguntó, no se dedujo

Diez cajones que salen de primera son diez bultos que entran al pool: el
cajón pasa entero, no se reenvasa. **En el reproceso NO es así** —un cajón de
16 da tres cajas de 6, y el sistema acepta producir más bultos de los que
tomó— así que copiar la relación de allá habría sido exactamente el corolario
81: derivar un caso de la forma de una regla vecina en vez de preguntar si el
caso es así. Se preguntó, y va escrito donde se escribe:
`movimientos_stock_pase_uno_a_uno`.

### El pase salía de los SUELTOS — y DEJÓ DE SER CIERTO el 21/09

**Lo que decía acá hasta el 21/09, y era verdad cuando se escribió**:
`movimientos_stock_ficha_solo_merma` decía `tipo = 'merma' or ficha_id is
null`, así que un pase con ficha lo rechazaba sin ninguna guarda nueva. Y el
argumento parecía cerrado: *"una caja ya armada para un cliente que se pone
fea no es un pase, es desarmarla primero"*.

**El dueño lo dio vuelta con el caso**: se armó una caja para Día, no salió, y
se puso fea. Tiene que poder pasar a segunda DIRECTO, igual que la suelta —
desarmarla primero es un paso que en el galpón nadie da. Así que el CHECK se
ensanchó a `movimientos_stock_ficha_solo_merma_o_pase`
(`db/pase_a_segunda_3_con_ficha.sql`, corrida en las dos bases el 21/09) y el
pase acepta ficha.

**Y ESTA CORRECCIÓN LLEGÓ UN DÍA TARDE, que es el dato que vale más que el
caso.** La migración, la pantalla y los tests entraron en v945; esta oración
—que afirmaba lo contrario de lo que el commit acababa de hacer— se quedó
acá otras veinticuatro horas. Es exactamente lo que este archivo describe en
*"la copia que más se olvida es la que está EN ESTE ARCHIVO"*: al arreglar
algo el `grep` sale sobre `app/`, `core/`, `templates/` y `tests/`, que son
los lugares donde el arreglo puede romperse. **CLAUDE.md no se rompe nunca,
no falla ningún test, y no está abierto.**

Lo que la habría encontrado en el momento es lo que esa misma sección pide y
no se hizo: **grepear acá adentro el nombre de la cosa que se tocó** — un
`grep ficha_solo_merma CLAUDE.md` de un segundo, en el mismo turno que la
migración.

## TODO LO QUE SE TIRA O PASA A SEGUNDA ES PLATA PERDIDA (21/09)

Es del dueño y cierra el tema en una regla:

> **Todo lo que se tira o pasa a segunda es plata perdida.** Va a una cuenta de
> resultado negativo, no costea a nadie y no vuelve a ningún lote.
>
> - **Caja de Día armada** (merma o pase) → la pérdida son **los kilos que
>   tenía MÁS la caja**.
> - **Bultos sueltos** (merma o pase) → **solo los kilos**.
>
> Merma y pase **se costean igual**: es la misma pérdida con otro destino.

**Y por eso son DOS RENGLONES y UNA cuenta.** La cuenta es la misma —no hay
una fórmula para lo tirado y otra para lo de segunda— y se separan al MOSTRAR,
porque son dos hechos distintos del galpón y el que lee el resultado quiere
saber cuál pesa más. Juntarlas en un total sería perder eso; calcularlas con
dos reglas sería la regla escrita dos veces.

**Y desde el 25/09 hay un TERCER renglón, CAJAS ROTAS, que suma al mismo
total** (dueño: *"es plata perdida igual que la mercadería"*). No es la tercera
forma de la misma cuenta: son cajas VACÍAS dadas de baja en Cajas (origen
`merma` de `movimientos_envase`), sin artículo ni mercadería, así que su
desglose es por tipo de caja. Se valúan al costo de la caja vigente el día de
la rotura, con el MISMO fragmento que las otras cuentas de plata de cajas
(`_SQL_COSTO_DEL_ENVASE_A_LA_FECHA`).

### La mercadería sale del REJUEGO, y la preferencia es lo que la ata a la caja

Una caja de Día armada que se tira **no se costea contra el cajón más viejo
del artículo**: se costea contra **la caja armada**, que es lo que tiene
adentro. Eso no es una cuenta nueva — es una línea en `prioridad_de_lote`
(core/stock.py): una salida con ficha propia PREFIERE los
`TIPOS_LOTE_TRABAJADO`.

```
merma o pase CON ficha   -> prefiere ('reproceso', 'reingreso_rechazo')
merma o pase SIN ficha   -> FIFO puro: no se sabe de qué cajón salió
```

**Y la preferencia es por TIPO, no por la ficha exacta**, decisión del dueño:
*"si el pase fuera más preciso que el armado, habría dos reglas para la misma
pregunta. Y cuando me importe la caja exacta, elijo el lote a mano."* La
diferencia solo existe con cajas del mismo artículo armadas para dos clientes
a la vez, y en plata es mínima.

**LO QUE ESO COMPRA GRATIS: recostear lo que ya está cargado.** El costo de una
merma **no vive en ninguna columna** —el CHECK de `movimientos_stock` prohíbe
escribirlo (`tipo in ('reingreso_rechazo','stock_inicial') or costo_por_bulto
is null`)— y `atribuir_costos_fifo` lo rejuega en cada lectura. Así que cambiar
la prioridad recosteó toda la historia **sin una migración y sin tocar una
fila**. Es el corolario 80 por cuarta vez: con una cuenta derivada, completar o
corregir el dato de origen ES el arreglo.

**Y los dos tipos salen de UNA constante** (`TIPOS_CON_FICHA_PROPIA`), que vive
en `core/stock.py` y no en `app/db.py` porque `core` no puede importar de
`app`. La consulta del stock partido y la del extracto la leen del mismo lugar:
escrita dos veces, la copia que se separe deja una pantalla mostrando la merma
de una caja armada como si fuera suelta — que es el bug que esto vino a cerrar
y que estuvo vivo desde el 10/09.

### La pantalla: `/gerencia/perdidas`, y lo que NO se suma

Filtrada por fecha como Plata de cajas, con los dos renglones y el detalle por
artículo. Va a ser una línea del estado de resultados.

**Y dice en la pantalla que NO se suma con "Plata de cajas"**, porque las dos
muestran plata de la MISMA caja contestando dos preguntas distintas: allá se
cuenta por CLIENTE para poder reclamarla —e incluye los rechazos, que son del
cliente— y acá por DESTINO para el resultado. Sumar los dos totales la cuenta
dos veces, y el que lee "$X perdidos" sin esa frase al lado lo va a restar de
algún lado.

**Lo que no se pudo costear se MUESTRA**: `bultos_sin_costo` son los bultos que
salieron de un lote sin precio. Suman bultos y no suman pesos, y el total lo
dice. Un total que se los come en silencio es más chico y **se lee igual de
cerrado** — y este número va a un estado de resultados.

### Los DOS recortes, que es lo único fácil de romper acá

**El rejuego va desde el CORTE; la suma, solo sobre la VENTANA.** Son dos
recortes distintos a propósito: para saber a qué lote se le cobra una merma de
ayer hay que haber repartido todo lo anterior. Recortar el rejuego a la ventana
costearía contra los lotes equivocados **y devolvería un número plausible**.

Lo cuida `tests/test_perdidas_contra_la_base.py`, que corre contra Postgres con
el esquema real: el caso está armado para que el ORDEN decida —a un cajón le
quedan 5 porque una guía R anterior a la ventana se llevó los otros 5, así que
los 8 sueltos se desbordan al lote siguiente— y con el rejuego recortado el
número cambia. Un fixture donde las entradas caen todas adentro de la ventana
da lo mismo con las dos reglas y no prueba nada.

### Y LA RENTABILIDAD REAL TIENE SU PROPIA COLUMNA (22/09)

La pantalla de Pérdidas dice cuánto se perdió. **Rentabilidad Real dice otra
cosa** —cuánto rindió cada artículo— y hasta el 22/09 el pase **no sumaba en
ninguna columna suya**: consumía mercadería del FIFO y no aparecía ni en
`costo_mermas`, ni en `segunda_bultos`, ni en `afuera_por_motivo`. La renta
salía inflada exactamente en lo que se pasó a segunda.

Son **tres compuertas y no una**, que es lo que costó encontrar: la misma
pregunta —*¿este artículo tuvo algo además de ventas?*— estaba escrita en
`articulos_con_salidas_stock` (la consulta), en `filas_con_algo` (la cuenta
pura) y en un `{% if %}` de la plantilla que decide si se dibuja el renglón
de chips. Arreglando las dos primeras, una berenjena que solo tuvo un pase
aparecía con su costo **y sin un solo chip que dijera por qué** — un artículo
con pérdida y sin nada que la nombre. Lo destapó un test de pantalla, no la
lectura.

**Y LA CAJA DE LA MERMA ENTRÓ HORAS DESPUÉS, el mismo 22/09, y lo que hay que
llevarse es POR QUÉ QUEDÓ AFUERA la primera vez.** La dejé afuera "como una
decisión del dueño", con este argumento: contarla movería `costo_mermas`, que
es un número que ya se lee todos los días. **Ya estaba decidida** —la regla
del 21/09, tres párrafos más arriba, dice *"caja de Día armada, merma o pase,
la pérdida son los kilos MÁS la caja"*— y él lo contestó en una línea: *"te
pregunta algo que ya contestaste"*.

O sea que no fue prudencia: fue **no leer la regla que este mismo archivo ya
tenía escrita sobre la cosa que estaba tocando**. Es el corolario 2 al revés
—buscar la otra copia antes de preguntar, no después de decidir— y la copia
estaba acá adentro, que es la que siempre se olvida.

**Y una consulta de más no es gratis, que es la parte contraintuitiva.**
Preguntar se siente siempre como el lado seguro, y tiene un costo que no se
ve: el dueño contesta lo que ya contestó, y la próxima vez que le pregunte
algo que de verdad no sabe, la pregunta llega con menos crédito. Antes de
subir una decisión, grepear acá la cosa que se está tocando.

**Lo que costó cerrarla: una línea de cuenta y CUATRO de desglose.** La
mercadería se abre en `costo_mermas_cruda` + `costo_mermas_trabajada`, y esas
dos **sumaban `costo_mermas`**. Con la caja adentro dejan de sumar — y la
tarjeta de la pantalla dice, textual, *"$X en total, abierto por lo que se
tiró"* arriba de dos renglones que ya no dan $X. El atajo era meter la caja en
la mitad "trabajada" (una caja armada es trabajo, suena bien) y **eso le hace
contestar otra pregunta que la de su nombre**: esa columna abre la
MERCADERÍA, y una caja no es mercadería. Va como un tercer término propio
—`cajas_mermadas_pesos`, su renglón en la tarjeta, su columna en el Excel y su
frase en el PDF— y los tres cierran.

**La señal general, y sirve sin este caso**: cuando un número gana un
sumando, ir a ver si ese número tiene un DESGLOSE publicado. Un total que
crece mientras su desglose no es una pantalla que se contradice a sí misma, y
el que la lee no tiene forma de saber cuál de los dos está mal. Lo cuida
`test_la_tarjeta_de_MERMAS_SIGUE_CERRANDO_con_la_caja_adentro`, que exige los
tres términos **y** que la mercadería sola NO alcance: sin esa segunda mitad,
el atajo de la columna "trabajada" pasa el test.

**Y las DOS pantallas la cuentan ahora, cada una a su manera**: Pérdidas la
tiene en el renglón "Se tiró" desde el 21/09, y Rentabilidad Real adentro de
`costo_mermas`. Siguen sin sumarse entre sí —lo dice la pantalla— porque
cuentan la misma caja contestando dos preguntas distintas: allá por DESTINO,
para el resultado; en Plata de cajas por CLIENTE, para poder reclamarla.

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

### RETIRADO por el dueño el 20/09: no es un problema de plata

**No se construye ninguna de las dos.** La decisión es suya y la razón es
corta: el descarte del reproceso **no se pierde de las cuentas** —está adentro
de `tomados − primera`, los cajones se fueron y volvieron menos cajas— y lo
único que falta es el MOTIVO, que no mueve un peso.

Queda escrito como decisión y no como pendiente, porque un "anotado y no
construido" se relee dentro de seis meses como algo que todavía hay que hacer.
Lo de abajo es lo que se haría SI alguna vez el motivo hiciera falta, y hoy no
hace falta.

---

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

## EL MODELO DE LA CAJA, en tres renglones (17/09)

Es del dueño, y reemplaza todo lo que la sección de abajo fue pensando
durante seis días. Vale la pena leerlo primero: lo de abajo es el camino
hasta acá, con tres premisas que se cayeron en el medio.

    1. La caja de Día NO VUELVE NUNCA al stock. Por ninguna puerta.
    2. El stock solo SUBE por COMPRA — y por la guía R `en_origen`, que es
       una caja nuestra que vuelve llena de afuera. **Y desde el 17/09,
       por la cuenta con un COLEGA**: una caja que me presta entra al piso,
       y una que le devuelvo sale. Eso no le agrega ninguna pata al stock
       —`cantidad` ya significa el efecto sobre el piso— pero la frase "solo
       compra y en_origen" dejó de ser cierta y acá se corrige.
    3. Toda caja que se llena está PERDIDA, salvo la que vuelve rechazada y
       se remanda; y ésa ya estaba descontada, así que no se cuenta dos
       veces.

**Las cuatro puertas del rechazo, contra ese modelo.** Las cuatro salen del
mismo lugar —una caja que ya se descontó cuando la guía R la armó— y ninguna
le devuelve nada al stock:

| `destino_rechazo` | qué le pasa a la caja |
|---|---|
| `segunda` | se remite al Puesto en la caja en que volvió |
| `devolucion_proveedor` | se va con la mercadería que se devuelve |
| `reproceso` | la fruta pasa a cajón grande y la caja **se tira** |
| `stock` | vuelve llena, se rearma y sale de nuevo: **la misma caja** |

**Y POR ESO NO HAY NINGUNA REGLA QUE ESCRIBIR**, que es lo que lo vuelve un
modelo y no una lista: las tres primeras ya están restadas y no vuelven; la
cuarta está restada UNA vez y se reusa sin pasar por una guía R nueva.

El neutro de la cuarta **no es una convención entre dos lugares** —que sería
el corolario 21, correcto hasta que alguien agregue un tercer camino— sino
una pared: un rechazo a `stock` deja un lote `reingreso_rechazo`, que es un
TIPO_LOTE_TRABAJADO, y `reproceso_toma` los tiene **PROHIBIDOS**
(core/stock.py). Medido con canario, no leído:

```
una GUIA R (reproceso_toma)  -> ['guia']                        <- no lo ve
un ARMADO                    -> ['reingreso_rechazo', 'guia']   <- lo prefiere
CANARIO (pared sacada)       -> ['reingreso_rechazo', 'guia']   <- la ve
```

Así que ninguna guía R puede consumir esa caja por segunda vez, y no hace
falta que nadie se acuerde de nada.

**Lo que costó llegar acá**: la `reproceso` llegó a tener columna propia
—`movimientos_stock.envase_id` con su `lleva_caja_nuestra` y tres CHECKs— y
una pata `liberadas` que le sumaba esa caja al stock, sobre la premisa de que
quedaba libre. Se sacaron el 17/09 (`db/envases_9_*.sql`). **Un camino que
nunca se va a recorrer es peor que no tenerlo: el próximo que lo lea va a
creer que falta cablearlo.**

Y una segunda razón, medida contra el esquema real: el código escribía
`envase_id` y **nunca** escribió `lleva_caja_nuestra`, así que con el CHECK
de coherencia puesto el reingreso a `reproceso` de toda ficha con envase
derivable **quedaba rechazado por la base**. Una pata que sumaba algo que no
pasa, apoyada en una columna que el código no podía escribir.

**Y ese CHECK ESTUVO PUESTO EN LAS DOS BASES**, confirmado por el dueño el
17/09: la tanda entera se corrió. Lo que lo dejó sin víctimas es que nadie
cruzó ese camino — `vuelven_a_cajon 0` sobre 27 reingresos en Frutamax—, así
que la pared existió un día y la desactivó el drop en vez del uso. Es el
corolario 75.

**Dónde vive el modelo**: arriba de todo en `core/envases.py`, que es el
módulo que las dos cuentas leen. Acá está para el que busque por el lado del
negocio; allá, para el que lo busque por el lado del código.

## La caja nuestra que se va y no vuelve: TRES puertas del mismo agujero

Del 11/09, y va acá porque es un hecho del negocio que el sistema no
registra, no un bug.

**MEDIDO Y RESUELTO EL 16/09, y la resolución no fue construir nada de lo
que esta sección proponía: fue ver que estas tres puertas NO son un agujero
de stock de cajas.** La caja se descuenta cuando se ARMA —en la guía R— así
que para cuando sale por cualquiera de las tres ya estaba descontada y no
vuelve. El stock lo refleja solo. Lo que estas tres sí son es un agujero de
COSTO DE ENVASE, que es otra pregunta.

**Y esa pregunta tiene planteo desde el 16/09.** El mecanismo: el costo de
envase YA se cobra, por unidad de PRIMERA vendida, y esa tasa supone que toda
caja que sale la paga una primera. **La población, en cambio, se midió mal dos
veces el mismo día** — primero la segunda del reproceso (que no lleva caja) y
después el total de la segunda— y lo que queda es mucho más chico y tiene otro
NOMBRE: **las cajas que se pierden en un RECHAZO.** Salen con una venta,
vuelven del súper y se van de nuevo sin una segunda venta atrás.

Ver `docs/el_costo_de_las_cajas_que_salen_sin_venta.md`, que está reescrito
con la corrección. **Ningún número de la primera versión se vuelve a citar.**

**Ese párrafo se declaró MEDIA VERDAD el mismo día y NO LO ERA** — se dijo que
la caja de la segunda salía sin descontarse nunca, se "arregló" sumando
`bultos_segunda`, y unas horas después el dueño corrigió el dato del galpón:
**la segunda de un reproceso queda en el cajón del proveedor y no lleva caja
nuestra.** Revertido; el detalle y el error de método están en el corolario 71.

**Y la puerta 2 quedó más chica de lo que esta sección dice.** No es "la
segunda que se remite al Puesto": es **solo la que vino de un RECHAZO** —el
súper devuelve mercadería que salió en caja nuestra y eso se anota como
segunda—. Esa caja **ya se descontó en la guía R que la armó**, así que el
stock está bien y nunca estuvo mal: lo que falta es su COSTO, que es la otra
pregunta.

La observación es de Lionel y dio vuelta el diagnóstico de esta sección
entera: **teníamos dos preguntas distintas debajo de la misma palabra.**

Cuando la mercadería sale en NUESTRA caja y después se va del circuito, esa
caja no vuelve. El sistema no lleva cuenta de eso por ninguna de las tres
puertas por las que pasa:

1. **El envase perdido de origen** — manzana, pera, arándano: salen en el
   cajón del proveedor y no se reprocesan nunca. Ahí no hay caja nuestra que
   perder, y por eso está bien que no se cuente (ver más arriba).
2. **La segunda que se remite al Puesto, y SOLO la que vino de un rechazo** —
   sale en la caja en la que está, que es nuestra porque ya lo era antes de
   volver del súper. La segunda que sale de reprocesar un cajón NO cuenta:
   queda en el envase del proveedor (16/09).
3. **La devolución al proveedor** (la que estrenó el cuarto destino): si la
   mercadería vuelve en el cajón del proveedor, ese cajón sale por el
   circuito de vacíos como cualquier otro y no hay nada que hacer. **Si
   vuelve en caja de Día, la caja se va con ella.**

   (Cuando esto se escribió, *"el circuito de vacíos"* era uno solo y no
   hacía falta decir cuál. Desde el 18/09 son DOS: acá es **el del
   DEPÓSITO** —el cajón es de un proveedor de Compras— y no el del puesto.
   Ver "HAY DOS CIRCUITOS DE VACÍOS Y NO SE TOCAN".)

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
cajas vacías se le mandan el día anterior.

**CONSTRUIDO EL 16/09.** El párrafo decía que eso "no se registra en ningún
lado" y que `envases` era un catálogo "sin stock y sin movimientos": las dos
cosas dejaron de ser ciertas. Hoy la salida de vacías se declara como
`prestamo_al_puesto` en `movimientos_envase` (se llamaba `prestamo_salida`
hasta el 17/09: el préstamo a un COLEGA estrenó sus propios orígenes y los dos
nombres juntos en una lista se confundían), y la vuelta la registra sola la
guía R `en_origen` —la compra que llega armada en caja nuestra— que SUMA
donde las normales restan. Las dos puntas, como decía esta sección que
correspondía.

Lo que sigue en pie es el circuito de vacíos del PUESTO, que es de los
cajones DEL PROVEEDOR (`proveedores_puesto`) y está separado a propósito.

**La diferencia con las tres de arriba, y es la que importa:** en aquéllas
la caja se va CON mercadería y no vuelve — es una pérdida. Acá se va
**vacía y vuelve llena**: es un préstamo, y solo se vuelve pérdida el día
que no vuelve.

Eso cambia qué habría que medir, y por eso conviene que esté escrito antes
de que alguien lo retome: **no "cuántas se fueron" sino "cuántas no
volvieron".** Contar salidas de un préstamo da un número grande y
tranquilizadoramente inútil — la mayoría vuelve. El número que significa
algo es el que no cierra.

**Y la advertencia que queda VIVA, que es la parte que el sistema no puede
cerrar**: la salida de vacías la tiene que cargar alguien, y es un campo
cuya única consecuencia es que el aviso de reposición salte cuando
corresponde. Si no se carga, el stock queda alto y el aviso llega tarde —
sin que nada se descuadre. Es exactamente el perfil del campo que se deja
de llenar (ver "Un campo sin consecuencia se llena vacío"), así que
conviene mirar a las dos semanas si se está cargando. Si no se carga, la
salida no es insistir: es darle consecuencia o sacarlo.

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
| su catálogo | `tipos_envase_puesto` | `tipos_cajon` |

**No comparten una sola tabla, y los dos "proveedor" son tablas distintas.**
Lo único que comparten es la palabra, y por eso las tablas nuevas la llevan
con `_deposito` pegado: un `conteos_vacios` a secas al lado de un
`conteos_vacios_deposito` se distingue leyendo, que es lo único que se hace
a las tres de la mañana.

**Y `tipos_cajon` no es `envases`**, que es la tercera cosa que dice algo
parecido: `envases` es LA CAJA NUESTRA con su costo, la que se le factura al
cliente. `tipos_cajon` es el cajón AJENO en el que llega la fruta. Uno se
paga, el otro se devuelve.

### El stock es por PROVEEDOR, y el tipo de cajón no es una segunda dimensión (la MARCA sí, desde el 25/09: ver abajo)

Decisión del dueño: **un proveedor entrega siempre en el mismo tipo de
cajón**, y se declara una vez en el alta. De ahí sale que
`proveedores.tipo_cajon_id` sea UNA columna y no una tabla de cruce: el tipo
es **cómo se llama el cajón de ese proveedor**, no un eje contra el cual
contar. El circuito del puesto sí tiene las dos dimensiones, y por eso todas
sus tablas llevan `tipo_envase_id` — la diferencia no es de estilo, es que
allá un cliente trae cajones de varios tipos y acá no.

La columna va **NULLABLE a propósito**: los proveedores ya cargados no la
tienen y exigirla dejaría sin poder recepcionarles.

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

### DESDE EL 25/09: una FOTO, PILAS por marca, y el conteo solo coteja

Decisiones del dueño, y reemplazan el modelo del conteo inicial del 18/09
entero. Lo que había —un conteo que ARRANCABA la cuenta, con su "todavía no
arrancó", sus "esperando" y la regla de la fecha— **se fue**.

- **El corte es la FOTO** (`vacios_deposito_foto`, una fila por proveedor,
  corrida el 25/09 en las dos bases): el stock que el sistema mostraba ese
  día. Frutamax dio 1.758 clavado contra la pantalla. De ahí en adelante:
  **recepciones CON SEÑA suman, devoluciones restan**, y lo que no cierre se
  arregla con un ajuste. El intento de reconstruir el pasado (arrancar el
  18/09) se descartó: dejaba 16 de 35 proveedores negativos.
- **La foto se compara por INSTANTE (`f.creado_en`), no por día.** Con la
  fecha, lo recibido el 25/09 después de sacar la foto se perdía entero. Lo
  encontró correr la cuenta contra Postgres, no leerla.
- **El stock es por PILA: proveedor y marca de cajón** (`marcas_vacio`, que
  se cargan en el detalle de Vacíos). La foto va a "sin asignar"; la marca se
  la pone la recepción o una ASIGNACIÓN de Administración, que mueve de una
  pila a otra sin cambiar el total. Las FK son compuestas `(marca, proveedor)`:
  una marca de otro proveedor la rechaza la base.
- **Las dos marcas de Recepción** (`compras.marca`, texto libre, y
  `compras.marca_vacio_id`), opcionales, en blanco = "sin asignar". Las dos
  puertas que recepcionan —Recibir y el rechazo parcial— las escriben en el
  MISMO UPDATE, con un solo macro en la pantalla. La del vacío solo con seña
  (sin seña no entra ningún cajón a Vacíos, y la escritura lo rechaza). **El
  Detalle muestra la de la RECEPCIÓN**: si después Administración asigna esos
  cajones a otra pila, la compra sigue diciendo con qué marca llegaron. El
  ingreso directo no lleva seña, así que no tiene marca de vacío.
- **La devolución sale de una PILA, sin compra**, con la seña por cajón de
  la última recepción de esa pila precargada y editable. **Sin foto del vale
  no es una devolución: es un ajuste** (guarda en la ruta y en la escritura;
  el CHECK de la base entra después del deploy, `vacios_marcas_5`). **No se
  devuelve más de lo que dice el sistema**: el freno lee la pila con la fila
  del proveedor bloqueada, y con LA MISMA consulta de la pantalla.
- **Ajuste y asignación son SOLO de Administración**: no tienen ruta bajo
  `/compras`, así que los cierra la puerta por prefijo.
- **El conteo físico ya no arranca nada: va al COTEJO**, el último conteo de
  cada pila contra lo que el sistema dice ahora. Solo ofrece proveedores y
  marcas ya cargados.

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

## `unidad_compra` y `unidad_venta` se suponían la MISMA unidad (CERRADO el 15/09)

Del 12/09, y **dejó de ser cierto el 15/09**: una compra declara ahora los
kilos SIEMPRE y —cuando el artículo tiene `unidad_conteo`— también un conteo,
y cada ficha divide por la suya. No hay conversión, y sigue sin haberla a
propósito. Ver **"La unidad de compra contra la de venta"**, más abajo.

Se deja escrito porque el supuesto vivió meses y el diagnóstico de abajo es
lo que llevó al modelo.

`_costear_compras` (app/costeo.py) divide `Σ(importe × cajones)` por
`Σ(cajones × contenido_por_cajon)` y llama al resultado **costo por unidad
de venta**. El numerador es plata y el denominador es contenido de compra,
así que esa igualdad solo vale si la unidad en que se compra y la unidad en
que se vende son la misma. **No hay ninguna conversión en ningún lado**:
`grep conversion` sobre `app/costeo.py` y `core/motor_costeo.py` no devuelve
nada, y lo único que se llama así es el ALIAS del cliente —**cómo llama
cada cliente a cada artículo**, nombre y código propios, para interpretar sus
pedidos por mail—. No convierte unidades.

(Ese alias vivía en una tabla `conversion_articulos_cliente`, que este
archivo nombraba en dos lugares hasta el 19/09. **Ya no existe**: se fusionó
dentro de `fichas_logistica`, en las columnas `nombre_cliente` /
`codigo_cliente`, y lo que todavía la nombra son tres comentarios que cuentan
eso. La conclusión no se mueve —sigue sin haber conversión de unidades— y el
nombre sí: el que lo grepee hoy no encuentra nada y no sabe si es porque no
existe o porque buscó mal. Lo destapó el barrido de tablas del corolario 60,
que la listó como muerta.)

Analizar Artículo hereda el supuesto y **eso es lo correcto**: lo peligroso
sería que esta pantalla usara una regla distinta a las demás, que es la
familia de la regla escrita dos veces.

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

## Corolario 48: una divergencia entre bases no la escribe nadie, así que ninguna guarda de escritura la ve

Del 12/09. Las dos bases tenían la ficha de Kiwi distinta: Frutamax
`kilo/kilo` y Palmala `kilo/cubeta`. En Palmala eso rompe el supuesto del
costeo (ver la sección de `unidad_compra` y `unidad_venta`).

**Nadie cargó eso mal un día.** Las dos fichas se cargaron bien en su
momento y las bases se separaron después — por una migración que corrió en
una sola, por una corrección hecha a mano, por el orden en que se crearon.
No hay un momento de escritura donde una guarda hubiera saltado.

Eso decide DÓNDE va la guarda, y es al revés de lo que este archivo repite:
*la guarda va donde se ESCRIBE* vale para el error que alguien comete
tipeando. **Para el estado que se degrada solo, la guarda tiene que mirar el
ESTADO, no la escritura** — y en este sistema eso es el registro de alertas,
que recalcula cada seis horas y se ve en el banner y en la pantalla del
sector.

Por eso la guarda quedó como alerta (`unidades_que_difieren`) y no como un
cartel en la pantalla de Fichas. Un cartel al guardar no habría visto NUNCA
este caso.

Dos decisiones adentro, las dos con su razón:

- **A LOS DOS SECTORES.** La unidad de compra se edita en Artículos
  (Compras) y la de venta en Fichas (Comercial): en uno solo, el que la ve
  no siempre puede tocarla. (Las dos mitades de esta frase se cayeron el
  15/09: la alerta pasó a Compras sola, y la unidad de compra dejó de
  editarse en ningún lado. Lo que se edita ahí ahora es el CONTEO.)
- **NO FILTRA POR "SE USA".** Un par dormido no rompe ninguna cuenta hoy, y
  la primera versión lo excluía. Pero el día que se compre ese artículo el
  costo sale mal **desde la primera compra**, y nadie va a estar mirando —
  el aviso llegaría cuando ya no sirve. Usado y dormido se distinguen en el
  DETALLE, que es donde se decide cuál atender primero, no en si aparece.

Y el caso se cerró como dormido: Kiwi nunca se compró en ninguna de las dos
bases —cero compras, cero precios, cero renglones— así que no hay plata mal
calculada. **Las tres columnas de "¿se usa?" son las que lo dijeron**, y sin
ellas el mismo hallazgo habría mandado a revisar meses de costos.

**ARREGLADO el 12/09**: Lionel alineó la ficha desde la pantalla de Fichas.
Como Kiwi estaba dormido, la dirección en que se alineó no cambia ningún
número viejo — no hay compras ni precios que recalcular.

**Y "alinear" NO ES EL ARREGLO EN GENERAL, que es lo que este párrafo se
lee como diciendo. Corregido el 15/09.** Alinear vale solo cuando todas las
fichas del artículo dicen la misma unidad de venta y esa unidad no es la de
compra: ahí hay UNA cosa mal cargada. Cuando el artículo va a dos clientes en
dos unidades, alinear le hace decir a una ficha que ese cliente compra en una
unidad en la que no compra — apaga el aviso y borra el dato. La alerta no
distinguía los dos casos y su link mandaba a los dos a la misma pantalla; **el
detalle los separa desde el 15/09** (columna "Qué es"). De Kiwi no quedó
rastro para saber cuál de los dos era: `kiwi_1` sobre Frutamax da hoy cero en
todo. Palmala no se corrió.

**Y ESE MISMO DÍA, unas horas después, "alinear" dejó de ser una opción del
todo**: con el modelo de las dos magnitudes la ficha SIEMPRE dice la verdad
—ese cliente compra en esa unidad— y lo que puede faltar es que el ARTÍCULO
declare el conteo. Así que la alerta ya no manda a Fichas ni a Comercial:
manda a Artículos, que es el único lugar donde hay algo que hacer, y salió
de Comercial porque ahí no hay nada que tocar. Los dos casos del detalle son
otros dos ("cargale el conteo" y "ya cuenta en otra unidad: no entra").

La columna "Qué es" sobrevivió al cambio de regla y sigue haciendo lo mismo:
separar el caso que se arregla del que no. Lo que cambió es cuáles son.

**Y la verificación no hay que acordarse de correrla**, que es el punto de
haberla puesto como alerta y no como cartel: `unidades_que_difieren`
recalcula sola cada seis horas y se apaga cuando el par deja de diferir. Si
en la próxima corrida el banner sigue mostrándola, es que quedó algo — y si
se apaga, eso es la confirmación, sin una consulta de por medio.

Es la diferencia práctica entre una guarda que mira el ESTADO y una que mira
la escritura: la del estado también sirve para confirmar que el arreglo
entró.

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

## Borrar una ficha DESCONECTABA su historial de precios (CERRADO el 14/09)

Del 14/09, y sale de mirar el sistema con un uso nuevo encima: facturar para
atrás. Estuvo anotado y no construido unas horas; **se construyó el mismo
día, y la decisión de no esperar al número fue del dueño**: el problema es
real igual, y si hoy son cero, mejor — se arregla antes de que pase.

**Eso vale como criterio y no como excepción.** La regla de medir antes de
construir (corolario 23) existe para no inventar pantallas que nadie va a
mirar: ahí el número decide SI el problema existe. Acá el problema no
dependía del número — la FK dice `set null` y eso desconecta, haya pasado
una vez o ninguna. El número dimensiona el RESCATE de lo ya roto, que es
otra decisión —**y esa se cerró el mismo 14/09 en cero: no hubo ningún precio
desconectado en ninguna de las dos bases**, así que no hay nada que rescatar.
**Medir antes de construir la CURA; no antes de cerrar la PUERTA.**

Los precios cuelgan de la FICHA, y esa FK es `on delete set null`. Así que
borrar una ficha **no borra sus precios: les pone `ficha_id` en NULL.** Y
todas las lecturas filtran `ficha_id IS NOT NULL`, así que esos precios dejan
de existir para el sistema.

**EL DATO NO SE PIERDE, SE DESCONECTA**, y la diferencia decide qué se hace
después: la fila conserva `cliente_id`, `articulo_id`, `precio` y
`vigente_desde` — lo único que se va es de qué ficha era. Verificado corriendo
el borrado contra el esquema real: `precios_total 3 · precios_huerfanos 2 ·
articulos_afectados 1`. Un rescate es posible; una pérdida no tendría arreglo.

**SON DOS PUERTAS Y LA SEGUNDA NO PARECE UNA PUERTA:**

1. Eliminar la ficha.
2. **Cambiarle el ARTÍCULO**, que por dentro es un `DELETE` + `INSERT` con id
   nuevo. Desde la pantalla se ve como editar. Su propio docstring ya lo
   avisa: *"Cambiar el artículo DESCONECTA el historial de precios y los
   renglones viejos de esa ficha"*.

### Lo que hace que esto valga como corolario: el comentario lo predijo

`eliminar_ficha` tiene dos guardas —guías R y compras armadas— y su docstring
dice, textual: *"Las dos guardas se enumeran juntas a propósito: son la misma
pregunta ('¿quién apunta a esta ficha?') y separarlas es cómo se olvida la
tercera"*.

**La tercera es `precios_venta_historial`, y no está.** No se olvidó por
descuido: **no podía avisar.** Las dos que están son `NO ACTION` y revientan
la foreign key si alguien intenta borrar; la de precios es `SET NULL` y
**acepta en silencio**. La guarda existe donde la base grita y falta
exactamente donde la base calla.

Y el argumento que justifica el `NO ACTION` de las guías R está escrito arriba
en el mismo docstring —*"con SET NULL, borrar una ficha nulearía sus guías R
en silencio (...) Borrar una ficha no puede mover el stock"*— y se traslada
solo: **borrar una ficha tampoco puede borrar el precio al que se facturó.**

### Lo que se hizo, y lo que NO

**La FK pasa a NO ACTION** (`db/precios_no_se_desconectan_al_borrar_la_ficha.sql`),
que deja a las tres del mismo lado: guías R, compras armadas y precios. Y las
**dos puertas** —Eliminar y Cambiar el artículo— preguntan por los precios
antes de borrar, con un `ValueError` que la pantalla muestra como dato mal
pedido y no como un 500.

La guarda vive en **UNA** función (`_negar_si_tiene_precios`) que las dos
llaman. Escrita dos veces se separa, y la copia que quedara vieja seguiría
desconectando sin que nada avise — que es exactamente el modo de falla que
venía a cerrar.

**Lo que NO se tocó, y las dos razones son distintas:**

- **Las filas que ya quedaron huérfanas.** Rescatarlas es otra decisión y
  necesita el número. La verificación de la migración lo devuelve como
  `huerfanos_viejos`, al lado del resto.
- **`pedidos_renglones.ficha_id` sigue en SET NULL**, y es a propósito: un
  renglón viejo describe una entrega que ya pasó y nadie la consulta hacia
  atrás POR FICHA. Un precio sí, y eso es lo que Precios por Período vino a
  preguntar. **Buscar la otra copia es obligatorio; copiarle el arreglo,
  no** — mismo criterio que el Cotejo de vacíos.

### CERRADO: la migración corrió en las dos y no hubo nada que rescatar

Corrida el 14/09 en las DOS bases, con la fila de cada una al lado:

```
FRUTAMAX  guarda_no_action 1 · set_null 0 · huerfanos_viejos 0 · precios 75
PALMALA   guarda_no_action 1 · set_null 0 · huerfanos_viejos 0 · precios 86
```

**Cero huérfanos en las dos: nunca se desconectó un precio.** No hay
rescate que hacer, y la puerta quedó tapada antes de que pasara.

Y las dos columnas separadas hicieron el trabajo para el que estaban: un
*"¿existe algún FK?"* habría dado 1 con `set null` puesto y habría tapado
el caso. Es el corolario de contar POR NOMBRE, con una vuelta más — acá no
alcanzaba el nombre, porque el constraint existe en los dos estados y lo
que cambia es su COMPORTAMIENTO. Por eso son dos columnas y no una.

**El cero de huérfanos no dice que nadie haya borrado una ficha**: dice
que ninguna ficha borrada tenía precios. La diferencia no cambia la
decisión —cero desconectados es cero, se hayan borrado muchas o ninguna—
pero sí cambia cuánto sabemos de si la guarda va a molestar: si en este
sistema no se borran fichas, no se va a disparar nunca, y eso todavía no
está medido.

### La consulta que queda, y por qué su cero ya no informa

`db/fichas_borradas_y_precios_huerfanos.sql` cuenta las dos cosas —precios
huérfanos y fichas borradas, con su población al lado—. Contestó, y **con la FK
en NO ACTION su número ya no puede crecer**: correrla de nuevo devuelve cero por
construcción, que es el corolario 47 exacto. Eso va escrito EN SU ENCABEZADO, no
acá: el que la corra dentro de tres meses va a leer el archivo, no este
documento, y un cero prolijo sin esa advertencia se lee como una verificación
que se pasó.

La que sí sigue contestando algo es `..._verificacion.sql`, porque pregunta por
el estado del constraint y no por sus consecuencias.

**Y hay una asimetría que conviene tener en la cabeza al decidir**: esto es
viejo en el sistema y nuevo en las consecuencias. Mientras el precio solo se
usara para cotizar HOY, un precio huérfano no le faltaba a nadie. Con
facturación retroactiva, cada fila desconectada es una pregunta que el sistema
no puede contestar.

Y esa condición **ya no es hipotética**: el 14/09 se construyó
`/precios/vigencias`, que es la pantalla de facturar para atrás (desde el
15/09 se entra también por `/administracion/precios-por-periodo`, que es la
misma pantalla y la misma consulta). Un precio
huérfano no aparece ahí —la consulta pide `ficha_id IS NOT NULL`, porque sin
ficha no hay a qué producto pegarlo—, así que **esa ficha no aparece en el
listado en absoluto.**

(Esta línea decía que la ficha borrada "se ve como una que nunca tuvo
precio". Era cierto hasta esa misma tarde, cuando el dueño sacó de la
pantalla las fichas sin precio: antes salía marcada en amarillo y ahora no
sale. La diferencia importa para el que lea esto buscando el síntoma —
pasó de estar mal etiquetada a ser invisible.)

La PUERTA ya está cerrada, y el número que decidía si hacía falta un rescate
**se corrió el mismo día y dio CERO en las dos bases**: nunca se desconectó un
precio, así que no quedó ninguna ficha invisible por esto. Lo que sigue
valiendo es el síntoma descrito arriba, para el día que aparezca uno por otra
vía.

### Y el docstring de la ruta decía lo CONTRARIO que el de la función

`cambiar_articulo_de_ficha_ruta` afirmaba: *"Los precios ya negociados no
cambian: quedan cargados por artículo en precios_venta_historial"*. Falso —
cuelgan de la FICHA— y **cuatrocientas líneas más allá el docstring de la
función que esa ruta llama avisaba que DESCONECTA el historial**. Las dos
sobre la misma operación, diciendo lo opuesto, sin nombrarse.

No es el comentario que envejece del corolario 28, donde hay UNA afirmación
que dejó de ser cierta: acá había dos, y la que el lector encuentra depende
de por dónde entró. El que abre la ruta lee que no pasa nada; el que abre la
función lee que se pierde el historial. **Y la que tranquiliza es la que
está más cerca de la pantalla**, que es por donde se entra cuando se está
revisando si algo es seguro.

La misma frase afirmaba además que un artículo repetido *"lo corta el unique
de la tabla"*. Ese unique no existe desde
`db/permitir_varias_fichas_por_articulo.sql`. Dos afirmaciones falsas en un
párrafo de cuatro líneas, las dos envejecidas por cambios que no tocaron esa
ruta.

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

## Corolario 60: una migración que cambia un COMPORTAMIENTO no agrega ninguna columna, y el esquema del repo se queda viejo en silencio

Del 14/09. La FK de los precios pasó a NO ACTION, corrió en las dos bases, y
`db/esquema_completo.sql` **siguió diciendo `on delete set null`**. La suite
entera en verde.

No es que faltara el paso: existe, es manual, y hay un test que lo cuida —
`test_toda_columna_que_agrega_una_MIGRACION_esta_en_el_esquema_completo`, puesto
el 12/09 justamente para sacar ese paso de la memoria. **Lo que pasa es que ese
test mira COLUMNAS**, y un `on delete` no agrega ninguna. La guarda estaba
puesta, estaba bien escrita, y este cambio le pasa por al lado por
construcción.

**Y el daño no se ve en las bases que corrieron la migración**, que es lo que lo
hace durar: las dos quedaron bien, la pantalla anda, la verificación da 1/0. El
archivo viejo se cobra en **la base que todavía no existe** — la empresa
siguiente nace con el bug ya adentro, meses después, sin que nadie relacione una
cosa con la otra. Es la familia de *"una regla de unicidad no puede depender de
una extensión de Postgres"*: lo que se pierde el día que se crea la base
siguiente no es una regla.

**La pregunta que lo encuentra, y es una sola**: después de una migración,
*¿esto agrega una columna, o cambia un comportamiento?* Si es lo segundo —un
`on delete`, un `check`, un `default`, un `unique`, un índice parcial— **ningún
test de columnas lo va a ver**, y el archivo hay que tocarlo a mano en el mismo
commit.

### Y la lista escrita de memoria ya nacía incompleta

El test nuevo que pina el `on delete` de cada FK a `fichas_logistica` se escribió
con **cuatro** tablas: las que yo había mirado al arreglar los precios. El test
falló al primer intento y dijo que eran **siete** — `conteos_stock`,
`movimientos_stock` y `corte_respaldo_fichas_reprocesos` estaban bien desde
antes y no se nombran en ningún lado junto a las otras.

Las tres estaban correctas, así que no había bug. Lo que importa es el
mecanismo: **la lista la escribí mirando lo que acababa de tocar**, y eso es
exactamente el recorte que el corolario 5 describe —enumerar todas las cuentas
que leen el dato, no las que uno tiene en la cabeza—. Lo agarró el denominador
(corolario 45): el test compara el conjunto ENCONTRADO contra el DECIDIDO en vez
de recorrer solo los decididos. Recorriendo la lista propia habría pasado en
verde con tres afuera.

**Y la deliberada va EN la lista**, no afuera: `pedidos_renglones.ficha_id` sigue
en SET NULL a propósito, y el test lo exige. Dejarla afuera es cómo alguien le
copia el arreglo creyendo que se había olvidado — *buscar la otra copia es
obligatorio; copiarle el arreglo, no*.

**Y esto vale para CUALQUIER test que enumere**, no solo para éste: un test que
recorre SU PROPIA lista solo puede confirmar lo que ya sabía. Comparar el
conjunto **ENCONTRADO** contra el **DECIDIDO** falla en las dos direcciones
—cuando aparece algo que nadie decidió, y cuando desaparece algo que sí estaba
decidido— y las dos son hallazgos. Cuesta lo mismo escribirlo de una forma que
de la otra, y solo una encuentra lo que uno no fue a buscar.

### Y EL TEST DE COLUMNAS NO VE TABLAS (19/09)

La frase es del dueño y es la forma corta del corolario 60. El 60 dice que
una migración que cambia un COMPORTAMIENTO —un `on delete`, un CHECK— no
agrega ninguna columna y por eso ningún test de columnas la ve. **Una tabla
NUEVA tampoco agrega ninguna**, y es el mismo agujero por una puerta que
nadie mira.

`compras_eliminadas` se migró en las dos bases y `db/esquema_completo.sql`
no la tenía. El guardia del 12/09 estaba puesto, andaba, y **no podía
verlo**: busca `alter table ... add column`, y una tabla nueva no pasa por
ahí. No es que faltara un test — es que el que había no tiene forma de
expresar esta pregunta.

**Y el daño no lo ve ninguna de las dos bases de hoy**, que corrieron la
migración y quedaron bien: cae en **la base que todavía no existe**. La
empresa siguiente nace sin la tabla, y como el archivo se escribe en la
MISMA sentencia que el DELETE, ahí revienta todo borrado de compra — meses
después, sin que nadie relacione una cosa con la otra. Es la familia de *una
regla de unicidad no puede depender de una extensión de Postgres*: **lo que
se pierde el día que se crea la base siguiente no es una regla.**

**Y EL HUMO TAMPOCO LO AGARRA, medido y no supuesto.** Reproducido el estado
exacto del 19/09 —la tabla sin `create`, sin índice y sin comments— cayó
**un solo test, el nuevo**, con el humo en verde. El humo abre las 130
pantallas contra una base cargada con el esquema, así que ve la tabla que
falta solo si alguna consulta la nombra; `compras_eliminadas` todavía no la
nombra ninguna, y el día que la nombre ya es tarde. Ese cero vale: dice que
las dos guardas miran cosas distintas y que no hay una que cubra a la otra.

**Lo que se construyó** es el hermano del de columnas, y lo importante es
cómo pregunta: barre los `create table` de `db/*.sql`, resta los que alguna
migración dropea, y compara el conjunto ENCONTRADO contra el DECIDIDO —las
siete tablas muertas del diseño original, cada una con su razón al lado—.
Falla en las dos direcciones, así que la lista no puede quedarse protegiendo
lo que ya no pasa.

**Y las siete muertas se verificaron, no se heredaron del encabezado**:
ninguna aparece en POSICIÓN DE TABLA (`FROM|INTO|JOIN|UPDATE <tabla>`) en
`app/` ni en `core/`. El grep del nombre suelto da **20 para `recepciones` y
3 para `conversion_articulos_cliente`**, y las 23 son prosa y nombres de
variable — es el corolario 59 exacto, y contestar con ese grep habría dejado
tres tablas "vivas" que no lo están.

**Dos cosas más que salieron del barrido, y las dos son del método:**

- **La primera versión encontró una tabla llamada `if`**, matcheada adentro
  del comentario de `agregar_disponibles.sql` que dice *"seguro de correr más
  de una vez (create table if not exists...)"*. El comentario explica por qué
  algo es así, así que NOMBRA la cosa que el test busca: la colisión está
  garantizada por construcción (corolario 38/59). Los comentarios se sacan
  antes de barrer.
- **Y el contador del canario decía 0 con la suite diciendo "2 failed"**:
  corrí pytest con `-rs`, que imprime los salteados y **no las líneas
  `FAILED`**. Lo único que lo delató fue imprimir la cola del resumen al lado
  del conteo, que es la señal que la sexta lectura del canario en cero ya
  pedía. El que estaba roto era el canario.

**Y de yapa, un SKIP que antes no estaba**: Postgres se había caído en el
medio y el humo pasó a saltearse, así que una baseline de `2801 passed, 1
skipped` se lee casi igual que una de `2802 passed`. Un test salteado no es
un test verde, y el único que lo dice es el `-rs` — que es justamente la
bandera con la que el canario no veía los FAILED. **Las dos banderas hacen
falta y ninguna sola alcanza.**

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

## La unidad de compra contra la de venta: CERRADO con las DOS MAGNITUDES (15/09)

**Está construido, y todo lo que sigue es el camino hasta ahí.** Se deja
entero porque tres hipótesis se cayeron en el medio y la que quedó no se
parece a ninguna de ellas; lo que conviene leer primero es el final —**"EL
MODELO, como quedó"**, abajo de todo—, que es lo que el sistema hace hoy.

El resto de esta sección está escrito en el tiempo en que se pensó, y las
frases que decían "queda abierto" o "no se toca el modelo" **están corregidas
en su lugar**: se corrigieron el día que dejaron de ser ciertas, que fue el
mismo.

Del 15/09. Lo que sigue separa lo MEDIDO de lo que se supuso, porque
mezclarlos es cómo se decide con una hipótesis.

El hecho del negocio, dicho por el dueño: **kiwi, mango y palta se compran una
sola vez y van a dos clientes que los quieren en unidades distintas.** A Día
por unidad, a Coto por kilo. La compra es una; las unidades de venta, dos.

### Lo que eso le hizo a la alerta `unidades_que_difieren`

La alerta contaba pares donde `articulos.unidad_compra <> fichas.unidad_venta`,
y su docstring decía que era *"una configuración que queda mal hasta que
alguien la arregla"*. **Esa premisa era falsa**: si un artículo va a dos
clientes en dos unidades, los pares difieren porque el mundo es así, no
porque alguien haya cargado mal.

(Hoy la alerta pregunta otra cosa —si el ARTÍCULO puede declarar la unidad en
la que esa ficha vende— y el caso de las dos unidades ya no llega ahí. Ver
**EL MODELO, como quedó**.)

Y la consecuencia es peor que un aviso de más: **el link manda a alinear, y
alinear es exactamente lo que no hay que hacer.** Cambiar la ficha de Coto
para que diga "unidad" no arregla nada — hace que la ficha MIENTA sobre lo que
ese cliente compra, y apaga el aviso. **El arreglo que la alerta propone borra
la información que hace falta para arreglarlo de verdad.**

Es la familia del corolario 25 —un argumento válido defendiendo una premisa
que nadie midió— con un agravante que no habíamos visto: acá la premisa no
solo está mal, **está cableada en el destino del link**.

**HAY QUE IR A MIRAR EL KIWI DEL 12/09.** Está escrito arriba como
*"ARREGLADO: Lionel alineó la ficha desde la pantalla de Fichas"*, y en un
turno posterior el dueño dijo *"no había nada que alinear"* y *"puede estar
señalando algo que es correcto"*. Las dos cosas no pueden ser ciertas. Como
Kiwi estaba DORMIDO (cero compras en las dos bases), no hay plata mal
calculada en ningún caso — lo que puede haberse perdido es el dato de en qué
unidad lo compra ese cliente.

### Lo que SÍ está medido (código y esquema, este turno)

1. **El stock NO se toca.** `movimientos_stock.cantidad` está **en BULTOS**
   —lo dice el comment de la tabla— y lo mismo el armado y el FIFO. La unidad
   de compra/venta no entra en el stock, el cotejo, el remanente ni las guías
   R. **Todo el asunto es del camino de la PLATA**, y eso achica el problema
   más que cualquier otra cosa que se pueda decir de él.
2. **Todos los costos salen de UNA función**: `_costear_compras`
   (app/costeo.py), con cuatro llamadores. Calcula
   `plata / (cajones × contenido_por_cajon)` — o sea **el denominador está en
   unidad de COMPRA** — y devuelve eso bajo el nombre
   `costo_por_unidad_de_venta`. **El nombre ya afirma la conversión que nadie
   hace.**
3. **`contenido_caja` de la ficha NO es el puente.** Se usa para mostrar
   "por bulto", y su propio comentario dice que *"el resultado da igual por
   kilo — es un cociente, la unidad se cancela"*. Se multiplica por el costo
   Y por el precio, así que se cancela: lo que queda es
   `precio(venta) / costo(compra)`, con las unidades mezcladas y sin que nada
   avise.
4. **No hay ninguna conversión en ningún lado** — ya estaba escrito arriba y
   se volvió a verificar. Lo único que se llama así es el alias del cliente
   (nombre y código), que hoy vive en `fichas_logistica` y no convierte
   unidades.
5. **La alerta no puede distinguir los dos casos**, y por eso se escribió
   `db/kiwi_1_error_de_carga_o_dos_clientes.sql`: parte por ARTÍCULO entre el
   que tiene fichas que **no se ponen de acuerdo entre sí** (multiunidad:
   ninguna alineación lo arregla) y el que tiene **una sola** unidad de venta
   distinta de la de compra (ahí sí hay algo mal cargado). Probada contra
   `db/esquema_completo.sql` con los tres casos plantados y con el control de
   todo alineado: devuelve las dos respuestas, y la población queda en la
   fila para que el cero se pueda leer.

### Lo que NO está medido, y decide el diseño

**Dónde vive el factor de conversión**, y es una bifurcación con UN solo dato
que la resuelve — y no sale de una consulta, sale del galpón:

| | dónde va | cuándo es la correcta |
|---|---|---|
| **Dos números por COMPRA** (lo que propuso el dueño) | cada compra declara kilos Y unidades | si los kilos por unidad se mueven compra a compra |
| **Un número por ARTÍCULO** (kg por unidad) | una vez, en el artículo | si un mango pesa más o menos siempre lo mismo |

**La pregunta es si el kilaje POR UNIDAD es estable**, y hay una razón para
sospechar que sí que conviene tener escrita: **lo que ya sabemos que es
multiformato es la CAJA, no la FRUTA.** Está arriba, medido: el mango viene en
cajas de 40, de 12 y de 10 unidades, y por eso su `contenido_referencia` se
vació. Pero un mango pesa lo que pesa un mango — el formato que varía es el
envase, no el fruto. Si eso se confirma, **kg-por-unidad es exactamente el
número que el problema del multiformato NO toca**, y entonces alcanza con uno
por artículo en vez de dos por compra.

**ES UNA HIPÓTESIS Y SE PREGUNTA, NO SE MIDE.** Los datos no la pueden
contestar: `unidad_compra` es por ARTÍCULO, así que todas las compras de mango
están en la misma unidad y el cociente entre las dos nunca aparece en la base.
Es el mismo caso de Mango y Cherry multiformato, que se resolvió preguntando
en el galpón y no midiendo de nuevo.

**Y si la respuesta es "depende del día", la propuesta del dueño es la
correcta** y esta tabla no la contradice — dice cuándo cada una.

### MEDIDO Y DECIDIDO (15/09): el caso NO está cargado, y por eso se hicieron DOS cosas y no cuatro

`kiwi_1` en **Frutamax**: `arts_con_ficha 33 · arts_multiunidad 0 ·
arts_alineables 0 · pares_que_difieren 0 · pares_totales 34 · última compra
14/09`. **Cero en todo.** El hecho del negocio es real —el dueño lo describe
y pasa con mango, kiwi y palta— pero **no hay una sola ficha cargada que lo
necesite.**

Decisión del dueño **en ese momento**, y el criterio vale más que el caso: el
modelo de datos no se toca todavía. Ni las dos magnitudes por compra ni el
factor por artículo. Se construyeron solo las dos cosas que sirven el día que
cargue la ficha, y que hoy no le cuestan nada:

(**Esa decisión se dio vuelta el mismo día**, y no por un dato nuevo sino por
un criterio: *"si yo defino el caso, el caso es real"*. Ver abajo.)

1. **La alerta dejó de mandar a alinear.**
2. **El costeo se NIEGA** cuando las unidades no coinciden, en vez de dar un
   número mal.

**Y la razón de hacer la 1 aunque el caso no exista es del dueño**: *"el día
que yo cargue la ficha de un cliente que compra mango por kilo, esa alerta va
a saltar y me va a proponer romperla"*. Un aviso que propone destruir el dato
está mal aunque hoy dispare cero veces — y arreglarlo cuando dispara cero es
gratis.

Lo que quedaba abierto —decidir entre el factor y las dos magnitudes— **se
cerró el mismo día, y por el galpón**: ver abajo.

### Las cuentas que dependen de que la unidad sea UNA, enumeradas (15/09)

La unidad solo importa donde el `importe` se DIVIDE o se COMPARA contra un
contenido. Todo lo demás trabaja **por bulto**, y un bulto es un bulto
cualquiera sea su contenido. Son **tres** lugares:

1. **`_costear_compras`** (app/costeo.py), cuatro llamadores. Es todo el
   camino del costo, el precio sugerido y la utilidad.
2. **`_envases_por_unidad_ponderado`** (app/costeo.py), dos llamadores. **La
   que nadie iba a encontrar**, y está abajo.
3. **`calcular_costo_por_unidad_medida`** en la calculadora de Analizar
   Artículo (app/main.py).

Y lo que **NO** se toca, verificado y no supuesto:

- **El stock, el FIFO, el cotejo, el remanente y las guías R**: en BULTOS, lo
  dice el comment de `movimientos_stock`.
- **La Rentabilidad Real**: `costo_bulto` es `c.importe` DIRECTO (app/db.py),
  sin dividir por ningún contenido. El importe de una compra es por bulto.
- **La alerta de kilos faltantes**: compara `contenido_por_cajon` contra
  `contenido_por_cajon_real` — **las dos en la misma unidad**, sea cual sea.
  Es una comparación consigo misma y no le afecta nada de esto.

### LA QUE NADIE IBA A ENCONTRAR: el envase variable COMPARA las dos unidades

`_envases_por_unidad_ponderado` decide, para una ficha de envase variable, si
la mercadería sale descartable o en caja chica. Su docstring lo dice:

> *"si el contenido de ESE cajón es menor o igual al contenido de la ficha,
> es descartable (0 cajas); si es mayor, es caja chica"*

O sea `contenido_compra <= contenido_ficha`, donde el primero está en unidad
de COMPRA y el segundo en unidad de VENTA. **Con las unidades distintas, esa
comparación mezcla kilos con unidades** — 40 unidades contra 6 kilos— y de
ahí sale un costo de envase, no un cartel.

**Y el docstring nombra al MANGO como el caso de envase variable**, que es
exactamente el artículo del que salió todo esto.

Lo que hay que llevarse, más allá del caso: **buscando "el problema de las
unidades" nadie grepea la función de los ENVASES.** El grep que la encuentra
no es el del concepto ni el de la columna: es preguntarse **dónde se DIVIDE o
se COMPARA** un número de la compra contra uno de la ficha. Es el corolario
20 —enumerar el hecho y no la forma que uno espera— aplicado a una operación
en vez de a un campo.

### Las compras viejas NO se rompen, y las columnas YA ESTÁN

`compras` tiene `cantidad_kilos` **y** `cantidad_fraccion` (más sus gemelas
`_real`). Hoy guardan **UN** número en una de las dos cajas: `app/main.py`
calcula `total = cajones × contenido` y lo archiva según `unidad_compra`. Son
la misma magnitud etiquetada, no dos magnitudes.

Y el CHECK es `cantidad_kilos is not null OR cantidad_fraccion is not null`.
**Verificado contra el esquema real: la base YA ACEPTA las dos llenas.** Así
que del lado del guardado no hace falta ninguna migración.

Las compras viejas quedan con una magnitud y NULL en la otra, y **eso no está
roto: es verdadero e incompleto**, que son cosas distintas. (El docstring de
`listar_compras_para_costeo` decía que el costeo *"nunca lee
cantidad_kilos"*. Dejó de ser cierto el 15/09 y se corrigió en el mismo
commit: ahora es lo ÚNICO que lee, junto con `cantidad_fraccion`.)

**El límite de reusar esas columnas ES REAL Y SIGUE PUESTO**, y conviene
saberlo: `cantidad_fraccion` mete 'unidad' y 'cubeta' en la misma columna. Un
artículo que se venda a un cliente por unidad y a otro por cubeta **no entra
en dos columnas** — la compra guarda dos magnitudes, no tres.

Eso no es una deuda escondida: es exactamente lo que la alerta llama **"Ya
cuenta en otra unidad: no entra"**, dicho en la pantalla en vez de descubierto
seis meses después. Y medido antes de construir: `arts_unidad_y_cubeta 0` en
las dos bases.

### Y la ausencia de conversión era un OBJETIVO DE DISEÑO, no un olvido

`core/motor_costeo.calcular_costo_por_unidad_medida` lo dice en su primer
párrafo: la misma función saca el costo por kilo o por fracción *"**sin usar
ningún factor de conversión**"*.

Eso cambia cómo se discute la propuesta. No es tapar un agujero: es **dar de
baja una invariante que está escrita**. Puede estar bien darla de baja —el
mundo tiene artículos que se venden en dos unidades— pero el que lo haga tiene
que saber que está desarmando algo que alguien decidió, no arreglando un
descuido. Es el corolario 11 del dato de uso al revés: antes de sacar algo,
preguntarse de quién salió.

**Y NO SE DIO DE BAJA: el modelo de las dos magnitudes la CUMPLE.** Sigue sin
haber un solo factor de conversión en el sistema — lo que cambió es que ahora
la compra declara las dos magnitudes en vez de que alguien deduzca una de la
otra. La invariante se buscó para saber si había que romperla, y el resultado
fue encontrar el diseño que no la rompe. Ese orden es el que vale para la
próxima: **primero por qué está escrita, después si se puede.**

### La asimetría que decide entre las dos opciones

| | arregla el pasado | qué hay que saber |
|---|---|---|
| **Dos magnitudes por COMPRA** | **no** — solo desde el día que se empieza a cargar | el que compra tiene que pesar Y contar cada cajón |
| **Factor por ARTÍCULO** (kg por unidad) | **sí** — convierte el número que ya está guardado | si el kilaje por unidad es estable |

**Esa es la diferencia de fondo y no es de gusto**: un factor se aplica hacia
atrás sobre todo lo que ya está cargado; una segunda magnitud solo existe
desde que alguien la tipea. Para el costeo eso pesa menos de lo que parece
—sus ventanas son de 48 horas, 15 y 30 días, así que lo viejo se cae solo—
pero para cualquier lectura retroactiva (facturar para atrás, revisar un
margen del mes pasado) el factor es lo único que contesta.

**Y el factor tiene un borde conocido**: para 'unidad' es plausible que sea
estable (un mango pesa lo que pesa un mango); **para 'cubeta' es mucho más
flojo**, porque una cubeta es un recipiente y cuánto entra depende de cómo se
llene. Puede ser que el factor sirva para unidad↔kilo y no para cubeta↔kilo.

#### GANÓ LAS DOS MAGNITUDES, y el factor se construyó y se tiró el mismo día

La tabla de arriba está bien y le faltaba la fila que decidía. La puso el
dueño: **el kilaje por unidad NUNCA ES EXACTO.** Un mango no pesa 400 gramos,
pesa lo que pesa. Un factor deja números con coma que después no cierran
contra nada — es **un promedio disfrazado de dato**, que es exactamente el
corolario 20 (*un campo derivado no es un sustituto barato de uno declarado:
acierta en la mayoría y miente en un tercio*) visto antes de sufrirlo.

Mi argumento a favor del factor era el de la tabla —arregla el pasado— y la
frase que lo cerró vale como regla: *"tu argumento es razonable en teoría y
falso en la práctica"*. **Yo había medido que la CUENTA daba bien; nunca medí
que el INSUMO existiera.** Es el corolario 41 con otra ropa: una vuelta
completa que se ve como una lectura.

La migración del factor (`kilos_por_unidad`) llegó a correrse en las dos bases
y se revirtió con su propio `.sql`. Salió gratis porque **no tenía ni un
usuario**: es el corolario 29 al pie de la letra —un cambio que todavía no
tiene usuarios se escribe de forma que deshacerlo sea gratis—, y esta vez el
requisito que lo pedía no sobrevivió al día.

### LA TERCERA OPCIÓN, que es la más barata y no estaba en la mesa

**No convertir: NEGARSE A COSTEAR.** Cuando la unidad de venta de la ficha no
es la de compra del artículo, no mostrar costo ni precio sugerido para esa
ficha — decir que no se puede costear en esa unidad.

- **Dato nuevo: ninguno.** Y el camino ya existe: `costo_actual is None`
  ya devuelve None y la pantalla sabe mostrarlo.
- **Lo que gana**: convierte un número callado y mal en un hueco visible, que
  es la preferencia de toda esta casa.
- **Lo que cuesta**: esas fichas hoy muestran un número y pasarían a no
  mostrar ninguno. Eso es una pérdida **solo si el número era bueno**, y por
  construcción no lo es.
- **Y compone**: se hace ahora y no cierra ninguna puerta. El factor o la
  segunda magnitud se deciden después, con el dato del galpón.

Si los artículos son tres, **puede ser la solución entera**: con tres
artículos, el que pone el precio hace la cuenta de cabeza. Lo que no puede
hacer es darse cuenta de que el número que tiene adelante está mal.

**SE CONSTRUYÓ, Y SIGUE VIVA — pero pregunta otra cosa.** No fue la solución
entera: con el modelo de dos magnitudes la negativa ya no es "las unidades no
coinciden" sino **"el artículo no puede declarar esa unidad"**, que es un
conjunto mucho más chico. Y no era o una o la otra: la negativa es el piso que
queda cuando el modelo no alcanza, y las dos conviven.

Y hay una SEGUNDA negativa que no estaba prevista y es la que va a verse
todos los días al principio: **la compra vieja que declaró una sola
magnitud.** Ésa se apaga sola en cuanto entre una compra con las dos; la otra
no se apaga hasta que alguien toque el artículo. Van separadas en la fila
(`sin_conversion_de_unidad` y `compras_sin_la_magnitud`) justamente por eso —
juntarlas sería mandar a arreglar lo que se arregla solo.

### EL MODELO, como quedó (15/09)

**Una compra declara KILOS —siempre— y, cuando el artículo tiene
`unidad_conteo`, también un CONTEO (unidades o cubetas).** La misma caja de
mango se carga UNA vez con las dos, y cada ficha costea contra la que su
cliente compra. No hay conversión entre las dos y no la va a haber.

Las piezas, y el orden importa porque cada una tapa un agujero distinto:

1. **`articulos.unidad_conteo`** (columna nueva, migrada en las dos bases).
   Dice QUÉ es la segunda magnitud de ese artículo, o NULL si se compra solo
   por kilo. Se edita en `/compras/articulos`.
2. **`articulos.unidad_compra` quedó DEPRECADA**, y no se le cambió el
   significado — columna nueva y deprecar, que fue decisión del dueño y es la
   regla de siempre: ocho lugares escriben esa columna y re-signficarla es
   como se separan dos reglas. Lo único que sigue diciendo es **en qué unidad
   está expresado `compras.contenido_por_cajon`**.

   **Y ESE MISMO DÍA SE TERMINÓ DE SACAR, hasta donde se puede** — ver
   "Deprecar una columna que todavía DECIDE" más abajo. Salió de las dos
   pantallas de Artículos: no se pregunta, no se muestra, no se edita. Un
   artículo nuevo nace en 'kilo' y la edición directamente no la nombra en su
   UPDATE. Sigue leyéndose en tres lugares, y los tres son sobre lo VIEJO.
3. **El formulario pide LA OTRA magnitud por cajón**, en las cinco pantallas
   de carga, y es obligatoria cuando el artículo la declara. Un solo helper
   (`magnitudes_de_la_compra`) reparte entre `cantidad_kilos` y
   `cantidad_fraccion`, y un test parsea `app/main.py` para que el sexto
   camino no se olvide — el que falta, por definición, no nombra ninguna de
   las dos columnas (corolario 3).
4. **El reparto vive en `core/magnitudes.py`**, porque Depósito hace el
   MISMO con lo que pesa y cuenta. Escrito dos veces son dos reglas.
5. **La recepción pide las dos SOLO si la compra declaró las dos**, con la
   guarda donde se escribe. Pedirle a Depósito la que la compra no trajo es
   pedirle que invente; y aceptar una sola cuando declaró dos dejaría a dos
   fichas del mismo artículo costeando una contra lo pesado y otra contra lo
   estimado, en la misma compra y sin que nada se descuadre.
6. **`magnitud_de_la_ficha`** (app/costeo.py) es el único lugar donde se
   elige la unidad, y el valor VIAJA a las tres cuentas —el costo, los
   promedios por cajón y el costo de envase—. Que sea un valor y no tres
   lecturas es lo que impide que dos se pongan de acuerdo y la tercera no.

**NO SE MIGRÓ NINGUNA COMPRA VIEJA, y no se puede**: cada una declaró una
magnitud y la otra no existe en ningún lado. Deducirla sería el factor con
otro nombre. Quedan como están y la ficha que pida la otra **no se costea**,
con su propia cuenta al lado (`compras_sin_la_magnitud`) para que se
distinga de la negativa estructural. Se apaga sola con la primera compra
nueva.

**Lo único que se dedujo fue `unidad_conteo`**, copiado de `unidad_compra`
donde decía 'unidad' o 'cubeta'. Eso no es inventar un número: es copiar una
declaración que ya estaba. Verificado: `sin_copiar 0` en las dos bases.

### Deprecar una columna que todavía DECIDE: se saca de la MANO, no de la base

Del 15/09, y sale de una pregunta del dueño que vale más que el caso: *"no
quiero una columna deprecada que siga decidiendo"*.

**`unidad_compra` seguía decidiendo tres cosas**, todas escritas ese mismo
día por mí, y la respuesta honesta a "¿está deprecada?" era NO:

1. `repartir_magnitudes(unidad_compra, ...)` — en qué columna cae cada total.
2. `segunda_magnitud_del_articulo` — qué pide el campo nuevo del formulario.
3. `SUFIJOS_UNIDAD_COMPRA` — la `k` / la `u` que etiquetan
   `contenido_por_cajon` en trece plantillas.
4. Y desde el 15/09, `_negar_si_el_conteo_contradice_la_unidad_de_compra`
   (app/db.py): la guarda que impide declarar un conteo que no sea la unidad
   en que está escrita la historia del artículo. **Ésta no es una deuda de la
   deprecación: es lo que la columna pasó a hacer.** Un registro que dice en
   qué unidad está lo viejo sirve exactamente para negar lo que lo
   re-etiquetaría.
5. Y **en qué magnitud cae `contenido_referencia` al precargarse** — que es
   la que no estaba en esta lista y la encontró el dueño mirando la pantalla.
   Ver abajo.

**Y no se puede borrar**, por una razón que es la misma de todo este modelo:
los cuatro artículos que se compran contados tienen su historia de
`contenido_por_cajon` expresada en unidades. Sin la columna, esas compras
quedan etiquetadas en kilos — **sin mover un número y sin que nada avise**.
Convertirlas necesitaría el factor, que es justo lo que se descartó.

**LO QUE SÍ SE PUEDE, Y ES LO QUE SE HIZO: sacarla de la MANO.** Nadie la
elige, nadie la ve, nadie la edita. Un artículo nuevo nace en 'kilo' —el
formulario dejó de preguntar— y el UPDATE de la edición **no la nombra**,
para que tocarle el nombre a un artículo viejo no le pise la unidad de su
historia. La columna pasó de ser una decisión a ser un registro.

**La distinción que hay que llevarse**, porque "deprecada" se usa para las
dos cosas y son opuestas:

| | qué significa | qué se hace |
|---|---|---|
| **Deja de DECIDIR hacia adelante** | nadie la carga ni la elige | sacarla de la pantalla, y punto |
| **Deja de EXISTIR** | ninguna fila vieja depende de ella | recién ahí se borra |

Lo primero es gratis y se hace el día que se decide. **Lo segundo depende de
si lo viejo se puede releer sin ella**, y acá no se puede. Confundirlos es
cómo se borra una columna y se re-etiqueta la historia en silencio.

**Y el nulo pasó a SIGNIFICAR kilo**, que es lo que permitió sacar de las
cinco pantallas de carga la guarda de *"este artículo no tiene la unidad
configurada, cargala en /articulos"*. Con el campo fuera del formulario, ese
error mandaba a un callejón. Es seguro porque un artículo sin la columna
**no pudo tener ninguna compra** —la guarda no lo dejaba— así que no hay
nada que re-etiquetar. La regla general: **antes de darle un significado al
nulo, verificar que ninguna fila vieja lo tenga con otro.**

#### La columna que se agrega corre TODO lo que el CSS ubica por índice

El catálogo de Artículos se vuelve tarjeta en celular con reglas
`td:nth-child(N)`. El 14/09 le agregué una columna y no toqué el CSS: todo
lo que estaba a la derecha se corrió un lugar. La del conteo se puso el
rótulo `"ref. "` de la referencia —por eso el dueño vio una columna "ref."
diciendo "solo kilos"—, la referencia se fue al lugar del grupo, y **los
botones quedaron sin regla, en 28px**, abajo del mínimo tocable de este
proyecto. La suite entera en verde.

Es el corolario 3 en CSS: **cuando una estructura gana un campo hay que
grepear quién la CONSTRUYE.** Y acá el que la construye es una lista de
ÍNDICES que no nombra ninguna columna, así que ningún `grep` del nombre la
encuentra — es el caso más puro de "el que falta, por definición, no lo
nombra".

##### Y VOLVIO EN PYTHON EL 17/09, con la columna que se SACA en vez de la que se agrega

Mismo mecanismo, sin una línea de CSS. `_SQL_STOCK_DE_ENVASES` perdió la
pata `liberadas` y pasó de NUEVE columnas a OCHO. `stock_de_envases` se
actualizó a `f[7]`; **`crear_movimiento_envase` quedó leyendo `fila[8]`**, que
ya no existe. Reproducido con la fila real:

    IndexError: tuple index out of range

O sea que **todo guardado de un movimiento de cajas reventaba**, el CONTEO
INICIAL incluido — que es lo primero que alguien carga y lo único que hace
arrancar esa cuenta. Estuvo así desde el 17/09 y nadie lo pisó solo porque la
cuenta de cajas todavía no se había usado en ninguna de las dos bases.

**Las dos cosas que lo dejaron pasar, y ninguna es descuido:**

1. **Un lector por índice NO NOMBRA NINGUNA COLUMNA.** El `grep` que se hace
   al sacar un campo es el del campo, y `fila[8]` no lo contiene. Es
   exactamente lo del `nth-child`, en un lenguaje donde uno no lo espera.
2. **Ningún test podía verlo.** Los tres tests del formulario **parchean**
   `crear_movimiento_envase`, así que su cuerpo no lo ejercitaba nadie: la
   función estuvo rota sin un solo test en rojo. Es el corolario 9 corrido de
   lugar — allá el parche tapaba la línea rota, acá la saltea entera.

**El arreglo no es correr el índice**: es que las posiciones vivan en UN solo
lugar (`COLUMNAS_STOCK_DE_ENVASES`) y que los dos lectores lean POR NOMBRE.
Con eso, sacar o agregar una columna rompe un test en vez de una pantalla.

**La señal, y es barata**: cuando una consulta pierde o gana una columna,
`grep` de `fila[` y de `f[` en sus lectores, no del nombre de la columna. Y
si una función tiene todos sus tests parcheándola, no tiene ninguno.

Lo cuida ahora un test que cuenta los `<th>` de la tabla y los compara
contra los `nth-child` del CSS, en los dos sentidos (corolario 60): falla si
sobra una columna sin regla y si sobra una regla sin columna.

**Y de yapa, el mismo desajuste me hizo reportar mal.** Medí el botón de
28px, lo vi anterior al commit y escribí *"es anterior a esto"*. Era mío, de
ese commit. Es el corolario 18 exacto —al corregir se escribe rápido y con
la sensación de estar arreglando— y lo único que lo agarró fue ir a mirar el
CSS en vez de confiar en la memoria de qué había tocado.

### Un campo que significaba UNA cosa mientras hubo una sola magnitud

Del 15/09, y es el costo escondido del modelo de las dos magnitudes.

`articulos.contenido_referencia` se precarga en **un** campo de la compra
—`contenido_por_cajon`— y cuál de las dos magnitudes es ése lo decide
`unidad_compra`: kilos en casi todo el catálogo, el CONTEO en los que ya se
compraban contados. **La segunda magnitud (`segunda_por_cajon`) no se precarga
nunca**: el JS le toca la visibilidad, el `required` y el rótulo, y lo único
que le escribe es el vacío.

Mientras hubo UNA magnitud eso era exacto y el rótulo "Contenido de referencia
del cajón" alcanzaba. Con dos, **el mismo campo, con el mismo rótulo, significa
unidades en un artículo y kilos en el de al lado** — y lo que los separa es
`unidad_compra`, que el 15/09 sacamos de la pantalla a propósito.

**Hoy no hay ningún número mal puesto, y es por construcción**: `unidad_conteo`
se dedujo copiando `unidad_compra`, así que en los contados las dos columnas
dicen lo mismo y la referencia cae en el campo rotulado con su unidad.

**El riesgo es del caso que la pantalla nueva estrena**: un artículo que reciba
`unidad_conteo` de ahora en adelante queda en `unidad_compra = 'kilo'` —la
edición ni la nombra— así que su referencia cae en KILOS y su campo de conteo
no se precarga nunca. ~~Dos significados, ninguna señal.~~ **La señal existe
desde el 19/09 y la deuda es otra: ver "LA DEUDA NO ES 'DOS SIGNIFICADOS'"
más abajo, en esta misma sección.**

**Lo que se hizo, que es lo seguro**: el rótulo NOMBRA la magnitud
("¿Cuántos kilos suele traer un cajón?" / "¿Cuántas unidades..."). No cambia
un dato; hace visible cuál es.

**Lo que NO se hizo, y la consulta lo CERRÓ el 18/09**: clavar la referencia en
kilos —que es lo que la dejaría con un solo significado en todo el catálogo—
**re-etiqueta en silencio** la de los contados que ya tienen una cargada. Este
párrafo decía que se decidía con `db/referencia_1_en_que_magnitud_esta.sql` y
que si `contados_CON_referencia` daba 0 salía gratis. **No dio 0**:

```
FRUTAMAX  63 artículos · 4 contados · 4 CON referencia · 0 sin · en_kilos_con_conteo 0
PALMALA   38 artículos · 4 contados · 3 CON referencia · 1 sin · en_kilos_con_conteo 0
```

Son **SIETE referencias reales** expresadas en unidades o cubetas. Clavarlas en
kilos las re-etiqueta sin mover un número y sin que nada avise — exactamente lo
que este proyecto se negó a hacer al deprecar `unidad_compra`. **Cerrado: no se
clava, y la consulta ya no decide nada** (su cero era la condición, y la
condición no se cumplió).

**Y lo que se hizo en su lugar es lo contrario de clavar: que la magnitud viaje
CON el número.** El rótulo de la pantalla de EDICIÓN ya lo hacía desde el 15/09;
el que faltaba era **el listado del catálogo**, donde el Mango dice `ref. 40`
—unidades— tres renglones abajo del Tomate diciendo `ref. 16`, que son kilos. El
`ref.` que el CSS pone delante no distingue una de otra, y el listado es el que
se mira de corrido. Desde el 19/09 dicen `40u` y `16k`, con el mismo
`|sufijo_unidad` que `_magnitudes_del_cajon` ya usaba — **no una cuarta copia**
de `SUFIJOS_UNIDAD_COMPRA`, que es el momento exacto en que tres se convierten
en cuatro y el único en que se puede evitar gratis.

**Y EL NULO ES KILO, no "sin unidad"**, que es donde el sufijo se caía justo en
la mayoría del catálogo: lo dice el CHECK del esquema con su
`coalesce(unidad_compra, 'kilo')`, y desde el 15/09 un artículo nuevo nace así
porque el formulario dejó de preguntar la columna. Sin el `or "kilo"` de la
plantilla, **el caso más común sale pelado** — y es el que nadie va a ir a
mirar. Va con test propio, separado del de los dos contados, porque un sufijo
clavado en `k` pasa el de los contados a medias y éste entero.

**Y una segunda referencia para el conteo no va todavía**: el conteo es
justamente lo que cambia con el formato (el mango viene en 40, 12 y 10, que es
por lo que su referencia se vació). Precargar sirve con un valor DOMINANTE, y
ahí no lo hay — precargar mal es lo que invita a aceptar mal.

#### Y el filtro se llamaba `kilos` y lo único que hace es REDONDEAR

Del 19/09, y salió de este mismo trabajo. `_formatear_kilos` no sabe de qué
magnitud es el número que recibe: redondea a entero y saca la coma. **El nombre
afirmaba una magnitud que la función no tiene**, y era falso en CUATRO lugares
—ninguno un borde—:

    _magnitudes_del_cajon.html   lo llama sobre LAS DOS magnitudes de la misma compra
    fichas.html                  sobre el contenido en unidad de VENTA
    compra_form.html             sobre `contenido_por_cajon`
    articulos.html               sobre la referencia, que para siete está en unidades

Pasó a **`sin_decimales`**, que es lo único cierto de él: el nombre lleva el
alcance (corolario 8), y éste no tiene ninguno. La magnitud la pone quien llama,
con `sufijo_unidad` al lado.

**Y el test pregunta por la jerga que NO puede aparecer** además de por el
nombre bueno —`"kilos" not in templates.env.filters`, y un barrido de
`templates/` entero buscando `|kilos`—: afirmar el nombre nuevo pasa igual si
quedó un `|kilos` en una plantilla que nadie abrió. El barrido compara el
conjunto ENCONTRADO y no una lista escrita a mano (corolario 60): la próxima
plantilla no la va a recordar nadie.

**Y las dos mitades del renombre fallan de forma OPUESTA, que es por qué hacen
falta las dos.** El nombre de la función rompe un `import` de la suite
—`from app.main import _formatear_kilos`— y eso es un rojo que se lee. Un
`|kilos` olvidado en una plantilla **no rompe nada al importar**: Jinja falla al
RENDERIZAR, así que el único que lo ve es el operario, en la pantalla, el día
que entre. Por eso el barrido es un test y no un `grep` corrido una vez.

**Y el canario de la tanda fue ROMO y su número no decía nada.** Deshacer el
registro del filtro dejando nueve plantillas con `|sin_decimales` hizo caer
**210 tests**: no porque el barrido viera algo, sino porque nueve pantallas
dejaron de renderizar. El que sí contesta es el FINO —registrar los dos nombres
como alias, para que nada se rompa, y plantar UN `|kilos`—: ahí cae **1**, y es
el barrido. Es el corolario 35 con otra ropa: *¿el código quedó roto de la forma
que me importa, o quedó roto de otra?* — y un canario que rompe de MÁS contesta
que sí por el motivo equivocado, con un número grande que se lee como rigor.

#### LA DEUDA NO ES "DOS SIGNIFICADOS": ES "EL CONTEO NO TIENE REFERENCIA"

Del 19/09, y es del dueño: *"anotado con el nombre equivocado, el próximo que lo
lea va a buscar otra cosa"*.

Tres párrafos más arriba esto decía **"Dos significados, ninguna señal"**, y la
segunda mitad dejó de ser cierta: el rótulo de la edición (15/09) y el sufijo
del listado (19/09) SON la señal. Así que el que lea "dos significados" va a ir
a buscar una ambigüedad que ya no está, no la va a encontrar, y va a concluir
que la deuda se pagó.

**No se pagó, y es otra cosa.** El caso, en tres pasos:

1. un artículo nuevo nace con `unidad_compra` en NULL —el formulario dejó de
   preguntarla—, o sea en kilos;
2. `_negar_si_el_conteo_contradice_la_unidad_de_compra` **lo deja ponerle un
   conteo**: arranca con un `return` temprano cuando `unidad_compra` es falsy o
   `'kilo'`, y con razón, porque no hay historia que contradecir;
3. y entonces su `contenido_referencia` está en kilos y **su campo de CONTEO no
   se precarga nunca**: `segunda_por_cajon` no tiene de dónde salir, porque no
   existe una referencia para la segunda magnitud.

O sea que lo que falta no es desambiguar un campo: **es un segundo campo que no
existe.** Ese artículo va a declarar sus kilos con un número propuesto y sus
unidades desde cero, en cada compra, para siempre.

**Hoy son CERO casos**, medido: `en_kilos_con_conteo` dio 0 en las dos bases. Y
la razón para no construirlo **no es el cero** —un cero nunca es razón para
construir ni para no hacerlo (corolario 64)— sino la que ya está escrita arriba:
**el conteo es justamente lo que cambia con el formato**. El mango viene en 40,
12 y 10, que es por lo que su referencia se vació. Precargar sirve con un valor
DOMINANTE y ahí no lo hay, así que una segunda referencia estaría mal casi
siempre, y precargar mal es lo que invita a aceptar mal.

**El día que se retome, la pregunta es por el DOMINANTE y no por el cero**: si
aparece un artículo que se cuenta y viene siempre en el mismo formato, ése es el
caso que pide la columna. Un `count(distinct ...)` sobre sus compras lo contesta
antes de diseñar nada (corolario 23).

#### Y una cuenta que NO estaba en la lista y es la que nadie iba a buscar

`_envases_por_unidad_ponderado` compara lo que trae el cajón contra
`contenido_caja` de la ficha, que está en unidad de VENTA. Si los dos lados
no salen de la misma magnitud, de ahí sale **un costo de envase mal, no un
cartel**. Se encontró preguntando *dónde se DIVIDE o se COMPARA un número de
la compra contra uno de la ficha*, que es el grep que sirve — ni el del
concepto ni el de la columna.

Tiene **test propio, que no pasa por el costo**: la misma compra y la misma
ficha dan descartable o caja chica según la magnitud. El día que alguien
mueva esto, el costo va a seguir dando bien y eso es lo único que cae.

## La INVERSA de una regla se reescribe en la plantilla, porque ahí es donde aparece la necesidad

Del 15/09. `core/magnitudes.repartir_magnitudes` decide en qué columna cae
cada total de una compra, y está escrita UNA vez a propósito. Su **inversa**
—sacar la segunda magnitud POR CAJÓN de una compra ya guardada— estaba
escrita **dos veces en Jinja**, en dos bloques de `deposito_recepcion.html`
separados por 134 líneas, cada uno con su propio `if unidad_compra == "kilo"`.

**Y no es descuido: es que la necesidad aparece en la plantilla.** El que
escribe la pantalla tiene el `if` en la cabeza, son dos líneas de Jinja, y
poner una función en `core/` para eso se siente desproporcionado. La regla
directa la escribió quien diseñaba el modelo; la inversa la escribió quien
diseñaba una pantalla, que es otro momento y otro archivo.

**La señal, y se hace al escribir el `{% set %}`**: si una plantilla calcula
algo a partir de dos columnas y un `if` sobre una tercera, eso es una regla,
no una presentación. La pregunta que la separa: *¿este `if` existe también en
Python, del otro lado?* Si la respuesta es sí, es la inversa de algo y va al
lado de su directa.

**Lo que la habría encontrado antes**: el `grep` no del nombre —la plantilla
no nombra `repartir_magnitudes`— sino de la FORMA del derivado, un total
dividido los cajones. Eso es lo que una copia nueva no puede evitar escribir,
y es lo que cuida `test_la_INVERSA_del_reparto_esta_escrita_UNA_sola_vez`.

**Y lo que decidió el momento de arreglarlo fue el CONTEO de copias futuras**:
con seis pantallas más por mostrar las dos magnitudes, dos copias iban a ocho.
Ese número es el argumento — no "está feo", sino cuántas van a existir si se
muestra primero y se limpia después.

### Y cómo llega a las seis pantallas sin seis lugares donde olvidarse

Un macro (`templates/_magnitudes_del_cajon.html`) que toma la compra entera,
y un GLOBAL DEL ENTORNO (`segunda_por_cajon_de`) que le pide la cuenta a
`core/magnitudes.py`. El global es el precedente que ya estaba escrito para el
catálogo de cajas: pasar el dato en el contexto de cada render son seis
lugares de los que uno se puede olvidar, **y el que se olvide no ve nada roto
— ve una sola magnitud, que es lo que había antes.**

Dos decisiones adentro, las dos medidas con un canario:

- **`real` mueve LAS DOS mitades a la vez.** La fila de "lo recepcionado"
  muestra `contenido_por_cajon_real`, y al lado tiene que ir la segunda
  magnitud REAL. Con una sola versión, esa fila mezclaba lo recibido de un
  lado con lo declarado del otro, en la misma línea y sin que nada avise.
- **El estilo va INLINE en el macro.** Las seis plantillas tienen su propio
  `<style>`: puesto en las seis serían seis copias de la misma regla, que es
  justo lo que este arreglo vino a terminar.

### El hueco se MUESTRA, y la razón es del dueño

*"Una pantalla que se calla no distingue 'no hay dato' de 'no se me ocurrió
mostrarlo'."* Y acá el hueco es información: **dice que esa compra vieja no va
a poder costear en la otra unidad**, que es la pregunta que alguien se va a
hacer mirando las fichas que no costean. Se apaga solo cuando entren compras
con las dos.

Con la condición de que el hueco sea VERDADERO: un artículo que se compra solo
por kilo no tiene segunda magnitud, así que ahí no falta nada y el aviso sería
un reclamo falso. Lo distingue `unidad_conteo` — y por eso esa columna hace
falta en las seis consultas **aunque no entre en ninguna cuenta**: no decide el
número, decide si hay algo que declarar.

**Medido con un canario**: sacarle `a.unidad_conteo` a la consulta del detalle
hacía caer CERO, y el modo de falla es mudo — sin ella el macro no puede
nombrar la magnitud que falta, el hueco no se dibuja, y la pantalla vuelve a
mostrar una sola magnitud, que es exactamente lo que se veía antes. Es el
corolario 65 por tercera vez, y la tercera no fue más fácil de ver que la
primera.

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

## Corolario 67: un CHECK que compara contra una columna NULEABLE evalúa NULL, y un CHECK que evalúa NULL PASA

Del 16/09. El bloque 4 de la migración de las cajas agregaba
`movimientos_stock.envase_id` con la guarda obvia:

```sql
check (envase_id is null or destino_rechazo = 'reproceso')
```

Se lee perfecta y **no rechaza nada** cuando `destino_rechazo` es NULL: la
comparación da NULL, el `or` da NULL, y un CHECK que evalúa NULL **se
considera cumplido**. Medido, no deducido: una MERMA con `envase_id` puesto
entraba.

El arreglo es `is not distinct from`, que devuelve un booleano de verdad.

**Y lo que importa no es el caso: es que la MISMA forma ya estaba escrita
dos veces en esa tabla desde siempre.** `movimientos_stock_proveedor_solo_
devolucion` y `movimientos_stock_compra_solo_devolucion` tienen el mismo
`= 'devolucion_proveedor'` contra la misma columna nuleable, así que una
merma con `proveedor_devolucion_id` entraba igual. No era un bug vivo —hoy
el único que escribe esas columnas es la ruta del reingreso, que siempre
pone un destino— pero eran dos guardas que afirmaban algo que no cumplían.
Corregidas en `db/envases_5_*.sql`, con cero ofensores en las dos bases.

**Cómo se reconoce antes de sufrirlo, y es una sola pregunta**: en un CHECK
de la forma `A is null or B = 'valor'`, preguntarse **si B puede ser NULL**.
Si puede, el CHECK no cubre ese caso — y ese caso es justamente el de las
filas de otro tipo, que son las que la guarda venía a excluir.

Es de la familia del corolario 27 —la misma propiedad de un agregado salva a
una consulta de verificación y arruina una guarda— con el mecanismo corrido
al SQL de tres valores: lo que acá cambia de signo no es un agregado, es el
NULL, que en un `where` descarta la fila y en un `check` la deja pasar.

**Y lo agarró el CASO QUE TENÍA QUE PASAR, no los que tenían que fallar.**
Se probaron once casos negativos contra la migración y los once salían en
verde con mi CHECK roto: cualquier guarda que no rechace nada los pasa a
todos si ninguno de ellos es el que la ataca. El que lo destapó fue el
número doce, el único que buscaba el agujero. Es el corolario 30 al pie de
la letra, dado vuelta: allá una batería de negativos estaba toda en verde
con la guarda que frenaba siempre; acá con la que no frenaba nunca.

**Y la verificación tuvo que mirar la DEFINICIÓN y no el nombre**: los tres
constraints existen en los dos estados y lo que cambia es el comportamiento,
así que contarlos por nombre da 3 con el agujero puesto. `guardas_NULL_SAFE_
de_3` filtra por `pg_get_constraintdef(oid) like '%IS DISTINCT FROM%'`. Es
exactamente lo del `on delete` de los precios, y la segunda vez en una
semana que un `count` por nombre no alcanza.

### Y el que avisa del nombre repetido es el que lo repite (16/09)

Del mismo día, y es el corolario 14 con una vuelta que duele: **en el
planteo del stock de cajas escribí, con todas las letras, que en este
sistema ya hay tres pantallas que se llaman "Stock" y que no había que
agregar una cuarta. Dos mensajes después bauticé la pantalla nueva
"Envases", que es el nombre de una pantalla que ya existe** (`/envases`, el
catálogo de envases con su costo, en Comercial).

Y no se cobró en la próxima lectura como suele: se cobró en el acto, y de
la peor forma. La función de render se llamó `_renderizar_pantalla_envases`,
que **ya existía en `app/main.py`**, así que Python se quedó en silencio con
la segunda definición y mi ruta nueva empezó a renderizar la pantalla ajena.
El síntoma fue un 500 pidiendo `DATABASE_URL` en un test que parcheaba las
dos funciones que la ruta llama — o sea, un error que no hablaba del
problema.

**Dos cosas que se llevan:**

1. **En Python, dos `def` con el mismo nombre en un módulo no son un error:
   gana el último y el primero desaparece.** Con 18.000 líneas, el `grep`
   del nombre antes de escribirlo es lo único que lo evita, y cuesta un
   segundo. Es el mismo mecanismo que el `HOY_DE_PRUEBA` redefinido del
   14/09, pero sobre una función y no sobre una constante.
2. **Escribir la advertencia no protege de la advertencia.** Es la tercera
   vez que este archivo anota exactamente eso —el corolario 33 lo dice del
   20, y el 18 de sí mismo— y la conclusión operativa sigue siendo la
   misma: lo que protege no es acordarse de la regla, es el `grep` hecho en
   el momento de bautizar.

La pantalla quedó **Cajas**, en `/compras/cajas`, y el nombre es además más
honesto: "Envases" es el catálogo —el concepto, con su costo— y "Cajas" es
la cuenta de las que hay en el galpón. Verificado antes de fijarlo: ni
`/compras/cajas` ni un `<title>` con "Cajas" existían en el repo.

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

## Corolario 71: una regla escrita en la CONSULTA y en una función pura SIN LLAMADORES es una regla y un adorno

Del 16/09, y es la regla escrita dos veces con una asimetría que no
habíamos visto: **las dos copias no tienen el mismo peso.** Una decide y la
otra solo se lee como si decidiera.

El stock de cajas resta las que se llenan en la guía R, y eso está escrito
en dos lugares:

- `_SQL_STOCK_DE_ENVASES`, pata `guias` — **la que corre en producción.**
- `core/envases.cajas_que_mueve_la_guia` — la que explica la regla, con el
  mapa de signos y un docstring de diez líneas.

**La segunda tiene CERO llamadores fuera de sus propios tests.** `grep` del
nombre: seis apariciones, todas en `tests/test_cajas.py` y en su definición.
Así que la función que se lee como la fuente de la verdad no toca un solo
número del sistema, y sus tests —verdes, prolijos, con sus casos bien
elegidos— **no prueban nada sobre lo que el operario ve.**

**DEJÓ DE SER CIERTO EL 25/09, y para bien.** La lista de movimientos de
cajas (`movimientos_de_cajas`, app/db.py) es su primer llamador real: el signo
de cada guía R que se muestra sale de ella, y no de una tercera copia. Y lo que
ata las dos escrituras ya no es solo un par de asserts de texto:
`test_la_lista_SUMADA_desde_el_conteo_da_el_MISMO_stock_que_la_tarjeta` suma la
lista, que pasa por la función, y la compara contra `stock_de_envases`, que pasa
por el SQL. Si la función y la pata se separan, esos dos números se separan.
El mecanismo del corolario no cambia: lo que se movió es el ESTADO que se
anotó al lado para ilustrarlo.

### EL BUG QUE ESTE COROLARIO CONTABA NO EXISTÍA (16/09, unas horas después)

**Se deja entero y corregido acá, porque el error de método es más caro que
el hallazgo que decía tener.**

La versión original decía: *"el bug lo destapó el dueño, no el código: la
segunda sale en caja nuestra igual que la primera —al reprocesar un cajón, lo
de segunda se pone en caja de Día porque no hay otra cosa a mano en la mesa—
y las dos copias restaban solo `bultos_primera`"*. Sobre eso se cambiaron las
dos copias a `bultos_primera + bultos_segunda`.

**El dato del galpón era al revés, y lo corrigió el dueño el mismo día**: al
reprocesar un cajón la primera va en caja de Día y **la segunda queda en el
envase del proveedor**. No lleva caja nuestra. Así que el arreglo restaba
80,97 bultos por trimestre de un stock del que nunca salieron: **el stock
BAJO y el aviso de reposición temprano**, que es el mismo modo de falla que
venía a arreglar, con el signo cambiado.

Revertido el 16/09, con la premisa retractada escrita al lado de las dos
copias para que nadie la vuelva a agregar leyendo el número sin el dato.

**La lección NO es "preguntá el dato", que ya está escrita en veinte lugares
de este archivo. Es sobre CUÁNDO se pregunta:** el dato se preguntó, se
contestó, y la respuesta estaba mal — **porque la pregunta se hizo en medio
de un arreglo, con la hipótesis ya armada y el diff a medio escribir.** Una
pregunta así se contesta rápido y para adelante, que es exactamente cuando
menos se verifica (corolario 18, pero del lado del que CONTESTA y no del que
escribe).

**Cómo se reconoce, y es lo único accionable**: cuando un hecho del galpón
llega como confirmación de algo que uno ya empezó a construir, eso no es una
medición — es un tilde. El que contesta está mirando el arreglo, no el
galpón. La forma que lo evita es la que ya funcionó dos veces con el mango
multiformato: **preguntar qué pasa, no si pasa lo que uno cree.** *"¿En qué
va la segunda cuando se reprocesa?"* tiene una sola respuesta posible; *"la
segunda sale en caja nuestra, ¿no?"* tiene dos y una es un asentimiento.

**Y la parte que sí se confirmó**: existe una segunda que va en caja nuestra,
y es **la del RECHAZO** — el súper devuelve mercadería que salió en nuestra
caja y eso se anota como segunda. Ésa no pasa por `reprocesos`: vive en
`movimientos_stock`, y **ya está descontada desde la guía R que la armó**, así
que sumarla otra vez la contaría dos veces. Las dos segundas se llaman igual
y salen de tablas distintas, que es la familia entera de este archivo.

### Por qué la copia ornamental es PEOR que dos copias iguales

Con dos copias que corren, la que se separa rompe algo en algún lado: dos
pantallas dicen números distintos, un test cae, alguien pregunta. **Con una
copia ornamental no hay nada que se separe** — se puede arreglar la de
adorno, ver los tests en verde, y no mover un número. Y al revés: arreglar
solo el SQL deja el módulo que documenta la regla afirmando lo contrario,
que es el comentario que envejece con la autoridad de ser código.

**La señal, y es un `grep` de un segundo**: cuando una regla vive en una
función pura, grepear su NOMBRE y ver quién la llama. Si los únicos
llamadores son sus tests, esa función **no es la regla: es un documento
ejecutable**, y la regla está en otro lado. Lo cual está bien —un documento
ejecutable es mejor que un comentario— con la condición de que algo ATE las
dos: acá, un test que exige el término exacto en el texto del SQL y otro que
lo exige en la función, y un canario sobre cada uno.

Es el corolario 8 corrido de lugar: allá dos cuentas con el mismo nombre y
distinto ALCANCE; **acá dos escrituras de la misma regla con distinto
PODER.** Y como el poder no se ve leyendo —las dos son código, las dos
tienen tests— hay que ir a contar llamadores.

### La MERMA no entra, y eso se afirma en vez de dejarse implícito

Lo que se descarta se tira; no se pone en una caja para tirarlo. Es una
decisión y no un olvido, así que está escrita de las dos formas: el SQL
afirma `"bultos_merma" not in sql` y la función pura **ni siquiera recibe el
parámetro**, con un test que lo comprueba sobre la firma. El día que resulte
que sí ocupa caja, hay que cambiar la firma — y ahí el test dice por qué no
estaba.

### Y el assert de las anuladas era el corolario 4, otra vez

Buscando el término de la segunda apareció, de yapa, un canario en cero:
sacarle `r.anulado_el IS NULL` a la pata de las guías **no hacía caer ningún
test**. El assert decía

```python
assert "anulado_el IS NULL" in _SQL_STOCK_DE_ENVASES
```

y esa consulta tiene **CUATRO tablas que llaman igual a esa columna**. Una
coincidencia alcanzaba, así que el assert matcheaba el filtro de otra pata y
el de las guías podía irse entero. Una guía R anulada habría seguido
consumiendo cajas para siempre — que es exactamente lo contrario de lo que el
título de ese test promete (*"que anular una guía R corrija el stock solo
sale de esto"*).

Es el mismo caso del `anulado_el IS NULL` que matcheaba `pedidos` creyendo
mirar `pedidos_renglones`, cinco días después de escribirlo acá. Y la
diferencia con aquél es que **este assert estaba en el test cuyo TÍTULO
afirma la propiedad**: no es que faltara la verificación, es que la que había
no podía fallar.

Cerrado calificando por ALIAS y recorriendo las patas por nombre, con un
`count(...)` al lado — el denominador del corolario 45 aplicado a un assert
de texto: sin él, tres filtros y cuatro pasan igual. (Eran cuatro patas
cuando se escribió esto y son TRES desde el 17/09: se fue `liberadas`. El
assert cuenta lo que hay, así que el número del test se movió con ella.)

## Corolario 72: una columna MIGRADA, SUMADA por la consulta y que NADIE ESCRIBE es un cero que ninguna verificación de esquema puede ver

Del 16/09. `movimientos_stock.envase_id` se migró el mismo día con su CHECK,
la pata `liberadas` de `_SQL_STOCK_DE_ENVASES` la sumaba, y la verificación
de la migración daba `columna 1 · guarda 1 · ofensores 0`. Todo correcto, y
la pata valía **cero por construcción**: ningún camino del código la
escribía. La columna existía, la cuenta la leía, y no había un solo
`INSERT` que la nombrara.

**Y LA LECTURA ESTABA DADA VUELTA, corregido el 17/09.** Esto se leyó como
un cableado que faltaba: la columna esperaba un escritor. No esperaba
ninguno — **esperaba sumar cajas que se fueron a la basura.** La premisa de
la pata era que el rechazo a cajón grande LIBERA la caja, y el dueño la dio
vuelta: la caja SE TIRA. O sea que el cero era el único valor correcto que
esa cuenta podía dar, y el bug no era que nadie la escribiera: era que
existiera. Se sacó entera con sus dos columnas (`db/envases_9_*.sql`).

**Eso no invalida el corolario, lo completa**, y la parte nueva es la que
cuesta encontrar: una columna sin escritor tiene DOS explicaciones —falta
cablearla, o no tiene que existir— y **las dos se ven idénticas**: columna
migrada, consulta que la suma, cero prolijo, verificación en verde. La
pregunta del 72 (*¿qué código la ESCRIBE?*) encuentra el síntoma y no
distingue los dos casos. La que los separa no es de código: es **¿el hecho
del mundo que esta columna afirma, ocurre?** — y eso se pregunta en el
galpón, no se grepea.

**Y hay una señal barata que estaba a la vista**: la columna se migró el
16/09 con su CHECK y su verificación, y el código que la escribía se cableó
en el commit ANTERIOR. O sea que la pata se escribió, se migró y se verificó
sin que nadie preguntara si el hecho pasaba. Cuando una cuenta nueva se
construye entera antes de confirmar su premisa, el cero que devuelve no es
información — es el silencio de algo que nunca ocurrió.

**Y la premisa era medible de la forma más barata que hay: preguntando.**
Es el corolario 25 al pie de la letra —la premisa que nadie midió— con el
agravante de que acá medir costaba una pregunta de una línea. La que
funcionó las tres veces en esta casa es la abierta: *"¿qué pasa con la caja
cuando la fruta vuelve a cajón grande?"*, y no *"la caja queda libre, ¿no?"*
— la segunda tiene dos respuestas y una es un asentimiento (corolario 71).

**Las tres cosas que lo confirmaron son de tres clases distintas**, y hacen
falta las tres porque cada una sola se explica de otra manera:

1. La FIRMA de `crear_movimiento_stock` no tenía el parámetro.
2. Su único `INSERT` no nombraba la columna.
3. Los dos `UPDATE` de esa tabla solo tocan `anulado_el`.

Una sola de las tres es un indicio; las tres juntas son que la columna no
tiene escritor, que es un hecho y no una impresión.

**Por qué ninguna de las guardas que ya teníamos lo ve**, y es lo que lo
vuelve una familia nueva:

- La **verificación de la migración** pregunta si la columna y el CHECK
  existen. Existen. Sale 1 y 1.
- El **test que compara la estructura ENTERA del INSERT** compara lo que el
  INSERT escribe contra lo que se espera — y si la columna no está en
  ninguno de los dos lados, los dos coinciden. Un campo que nadie nombra no
  puede desajustar una comparación entre dos listas que tampoco lo nombran.
- El **canario sobre la consulta** muerde: sacarle la pata `liberadas` hace
  caer su test. Pero ese test afirma que la consulta SUMA la columna, no que
  alguien la haya escrito alguna vez.
- Y la **pantalla** se ve perfecta: un stock de cajas al que le falta una
  suma que siempre da cero es exactamente igual a uno que no la tiene.

Es el corolario 47 con el mecanismo corrido un lugar más atrás: allá el
número no podía crecer porque medía lo que no era; **acá no puede crecer
porque el dato que mide no se escribe nunca.** Y es peor que el 47 en una
cosa: el 47 se destapa rompiendo a propósito lo que hace cero al número, y
acá romper la consulta no sirve —la consulta está bien— y romper la
escritura tampoco, porque no hay escritura que romper.

**La pregunta que lo encuentra, y se hace el día que se migra una columna**:
*¿qué código la ESCRIBE?* No "¿existe?", no "¿la suma alguien?", sino el
`grep` del nombre en la lista de columnas de un `INSERT` o de un `UPDATE`.
Si la única aparición fuera del esquema es un `SELECT`, la columna es un
cero prolijo esperando a que alguien lo lea como un dato.

Es el corolario 3 en su forma más cara —**grepear quién CONSTRUYE, no el
campo**— con la vuelta de que acá no había ningún constructor al que le
faltara el campo: **no había constructor.** El grep del campo devolvía el
`create table`, el CHECK y la consulta, o sea tres lugares que lo nombran y
ninguno que lo escriba, y esa lista se lee como cobertura.

### Y una columna que se agrega a un INSERT rompe SIETE tests, y eso está bien

Los seis tests de `crear_movimiento_stock` comparan la tupla ENTERA del
INSERT, así que agregar una columna los rompe a todos. Es exactamente lo que
el corolario 3 dice que es su función: *"que falle el día que alguien agrega
un campo es la función del test, no una molestia"*. Y el séptimo cayó por
otra cosa: su assert era `"compra_devolucion_id)" in insert.args[0]` —
anclado en el **paréntesis que cerraba la lista**, o sea en que esa columna
fuera la última. El día que dejó de serlo, el assert cayó por una razón que
no era la suya.

Un ancla que depende de la POSICIÓN de algo adentro de una lista no está
verificando lo que dice: está verificando el orden. Lo que queda es el
fragmento de la lista entera, que no puede matchear otra cosa y no se rompe
cuando la lista crece por el otro lado.

### El caso feliz que faltaba, y es el mismo del corolario 30

Seis de los siete tests pasan la columna nueva en **None**. Un INSERT que
escribiera `NULL` a la fuerza los deja a los seis en verde, y el canario lo
midió: caían dos, los dos que tienen un valor. **Una batería de casos donde
el campo va vacío no distingue "el parámetro se guarda" de "la columna está
en la lista"** — hace falta el caso con un valor, y es el único que lo dice.

## Corolario 73: el recorte que protege al que reprocesa lo deja tomar el MISMO LOTE UNA VEZ POR GUÍA

Del 16/09, y no es un caso nuevo: es el agujero que se midió el 11/09 al
construir la guía en origen —*"las salidas del mismo día no cuentan, así que
dos guías sobre la misma compra el mismo día pasan las dos"*— con la parte
que ese día no se vio. Ahí se cerró con el candado UNO A UNO por compra, que
aplica **solo a `en_origen`**. Las guías R **normales** siguen sin freno.

El caso que lo trajo: un lote de 40 bultos, R300 con 30 y R307 con 26, las
dos del 14/09. Salieron 56 de 40.

**Corrido, no leído** (`reparto_para_reproceso` con el caso):

```
R300 sola (14/09, pide 30)                    disponible 40.0   PASA
R307 el MISMO dia que R300 (14/09, pide 26)   disponible 40.0   PASA   <- el caso
R307 al dia SIGUIENTE (15/09, pide 26)        disponible 10.0   FRENA  <- control
R307 el mismo dia pidiendo los 40 ENTEROS     disponible 40.0   PASA
una TERCERA el mismo dia, con 56 ya tomados   disponible 40.0   PASA
```

**Y esa última línea es lo que no estaba medido: el agujero NO está acotado a
dos guías.** Cada guía del día ve el lote ENTERO, así que el techo de lo que
se puede tomar de un lote de 40 en un día no es 80 — es 40 por cada guía que
se cargue. El caso de 56 es el mínimo visible, no el peor posible.

### Lo que pasa con el costo: las DOS cosas, y se contradicen

La pregunta natural es *"¿se atribuyó a un lote que no los tenía, o quedaron
sin lote?"*. La respuesta es **las dos, en dos lugares distintos**:

```
lo ESCRITO (reprocesos_consumos)  R300 -> guia/900 30   R307 -> guia/900 26
lo DERIVADO (el rejuego del stock)  guia/900 restante 0.0 · sin_lote 16.0
```

`reprocesos_consumos` es un **documento congelado** y de ahí sale
`costo_total = Σ(bultos × costo_por_bulto)` y `costo_por_bulto_primera`. O
sea que los 16 bultos de más **quedaron costeados al precio de ese lote,
para siempre**, en la guía y en todo lo que lea esa tabla.

El rejuego que muestra el stock dice otra cosa: el lote en 0 y 16 `sin_lote`.
**Ninguno de los dos está roto** —cada uno hace lo que promete— y por eso no
hay nada que se vea mal: el que mira el detalle de la guía ve un costo
completo, y el que mira el stock ve un hueco, y nadie los pone al lado.

Es la familia del corolario 71 —dos escrituras de la misma regla con distinto
PODER— corrida un lugar: acá no es una copia ornamental, son **dos respuestas
verdaderas a la misma pregunta**, una congelada y una derivada, que el día
que se separan no tienen cómo avisarse.

### La asimetría sigue siendo correcta, y por eso esto no se arregla solo

El recorte está razonado y el razonamiento es bueno: dentro de un día el
sistema **guarda fechas, no horas**, así que descontar una salida del mismo
día afirma un orden que no se sabe, y lo afirma en contra del que reprocesa.

**Lo que ese argumento no cubre es el TOTAL.** No hace falta saber el orden
para saber que 30 + 26 no entran en 40: la suma no depende de cuál fue
primero. O sea que el recorte contesta *"¿qué lotes había cuando cargó?"* y
el freno necesita además *"¿cuánto se llevó ya el día?"*, que es otra
pregunta y no necesita orden.

**La señal, y es la que se puede usar sin haber sufrido el caso**: cuando un
recorte se justifica porque *no se puede saber el orden*, preguntarse si lo
que se está decidiendo depende del orden. Si es una comparación de SUMAS, no
depende, y el recorte está de más — protege contra una incertidumbre que esa
cuenta no tiene.

### ARREGLADO EL 16/09, y lo que se midió antes de ponerlo

Se midió primero, por pedido del dueño, y la razón era buena: un freno que empiece a contar el
mismo día puede **rebotar cargas legítimas**, y hay que saber cuántas antes
de ponerlo. Las dos consultas están escritas y probadas contra el esquema
real con el caso plantado:

- `db/mismo_dia_1_lotes_sobreatribuidos.sql` — cuántos lotes recibieron más
  de lo que tenían, por cuánto, y cuánta plata se imputó de más. Sobre lo
  ESCRITO, que es lo que quedó congelado.
- `db/mismo_dia_2_cuantas_guias_comparten_dia.sql` — el TECHO del rebote:
  una guía sola en su día ve los mismos lotes antes y después, así que las
  únicas que pueden cambiar de resultado son las que comparten artículo y
  fecha con otra.

**El techo, corrido el 16/09** (Frutamax, `desde` 18/06, `ultima_guia_r`
15/09): `comparten_dia 155 · guias_en_la_ventana 307 · dias_con_varias 72 ·
bultos_en_riesgo 2639 de 5925 · peor_dia 3`. Palmala dio todo en cero y **no
vota** — es la base parada del corolario 24.

**La mitad de las guías comparten día**, y hay 155 sobre 72 grupos de
artículo-fecha, o sea de a dos casi siempre y tres como máximo. Eso NO son
155 casos rotos: compartir día es la CONDICIÓN NECESARIA, no el defecto —
dos guías del mismo día pueden entrar holgadas en el lote, o tocar lotes
distintos del mismo artículo. Lo que el techo dice es que el arreglo no es
un caso de borde: si rebota, va a rebotar seguido, y por eso el número del
daño real tiene que venir antes de ponerlo.

**El daño, corrido el 16/09** (Frutamax): `lotes_pasados 56 · lotes_consumidos
281 · bultos_de_mas 472 · peor_lote 31 · plata_de_mas $13.841.434 ·
lote_no_hallado 0 · guias_normales 307 · última 15/09`. **Uno de cada cinco
lotes recibió más de lo que tenía**, así que no era un incidente de dos guías.

**Y ese $13,8M es la EXPOSICIÓN, no el error** — hay que decirlo cada vez que
se cite. Los 472 bultos existieron: salieron cajas de verdad, costeadas al
precio del lote al que quedaron mal pegados. El error de cada guía es la
DIFERENCIA contra el precio del lote del que salieron en serio —mismo
artículo, fecha cercana— y es mucho menor. Es el corolario 13: la cuenta es
exacta sobre lo que mide y no contesta la pregunta con la que se la va a
citar.

### LOS 56 QUE YA ESTÁN NO SE CORRIGEN: son de la ETAPA DE PRUEBA (16/09)

Decisión del dueño, con fecha, y escrita acá para que dentro de tres meses
nadie los encuentre y quiera arreglarlos: **los lotes sobre-atribuidos
anteriores al 16/09 quedan como están.** Estamos en etapa de prueba, los
costos todavía no se toman en cuenta, y los números de estos días no
representan operación real. Lo único que se está mirando en serio es el
Remanente.

Y además **no se podían recostear aunque se quisiera**, que es lo que hace
que la decisión no cueste nada:

- La única puerta que existe, `completar_costo_reproceso`, dice en su propio
  título *"SOLO los NULL, jamás pisa"*. Arregla el PRECIO de un consumo que
  se cargó sin precio; acá el precio está bien y lo que está mal es **cuántos
  bultos** se le atribuyeron al lote.
- Y no hay respuesta correcta a la que recostear: con la regla nueva, la
  segunda guía **habría sido frenada**, no re-atribuida. El sistema no sabe
  de dónde salieron esos bultos.

Lo que sí queda es la lista de quién los sigue leyendo mal, para el día que
los costos importen: `app/db.py:9357` es la **vía de propagación** —la
primera de una guía entra al FIFO COMO UN LOTE con su
`costo_por_bulto_primera`, así que una guía mal costeada es un lote mal
precificado para todo lo que venga después—, el detalle de la guía R, y el
`SUM(rc.bultos)` por compra de `app/db.py:1579` y `3134`, que hace leer un
lote como MÁS consumido de lo que está y le apaga el botón "Vino armada" a
una compra cuyo lote no se agotó.

### Y EL REMANENTE NO SE MOVIÓ, que es lo que decidía la urgencia

La pregunta del dueño era la correcta: si los bultos de más quedaron "sin
lote" en el rejuego, ¿el Remanente muestra un faltante que no existe? Medido
contra `db/esquema_completo.sql` con el caso de 56-de-40 plantado en tres
formas, corriendo `stock_deposito_por_articulo` y `repartir_fifo` de verdad:

| el artículo | Remanente | sin_lote | negativos |
|---|---|---|---|
| un lote de 40, las guías producen 56 | **40 — correcto** | 0 | — |
| dos lotes, 40 y 100 | **140 — correcto** | 0 | — |
| un lote de 40, las guías producen 10 (el resto merma) | **−6** | 6 | `faltan 6` |

**El Remanente es una SUMA y nunca pregunta de qué lote salió**: `entradas +
reingresos + ajustes + reproceso_primera − reproceso_tomados − salidas`.
Verificado además que ninguna de las cuatro cuentas de stock
—`_sql_sumas_stock`, `_SQL_STOCK_PARTIDO`, `_SQL_POOL_SEGUNDA` y
`deficit_de_cajas_por_ficha`— lee `reprocesos_consumos`. La sobre-atribución
es un problema de LOTE y el Remanente mira el ARTÍCULO.

**Y la corrección a lo que yo mismo había escrito**: los 16 bultos NO quedan
`sin_lote` en general. El rejuego reparte la toma contra TODOS los lotes del
artículo, así que la absorbe el lote de al lado —o la propia primera del
día—. Mi medición anterior daba `sin_lote 16` porque el fixture tenía un solo
lote y nada que produjera. `sin_lote` aparece cuando el ARTÍCULO queda corto,
y entonces vale exactamente lo mismo que el negativo del Remanente (6, no
16): es un faltante REAL y ya tiene dónde verse.

Así que lo que había que mirar no era una consulta nueva: es la sección de
negativos que el Remanente ya muestra. Si está vacía, esto no le movió nada.

### El arreglo, y las dos mitades que tiran para lados opuestos

**El freno cuenta el mismo día; el reparto no.** Son dos preguntas distintas
que hasta el 16/09 contestaba la misma lista, y separarlas es todo el
arreglo:

- `reparto_para_reproceso` sigue igual: contesta *"¿qué lotes había ese
  día?"*, y ahí el recorte asimétrico está bien. **El desglose que ve el
  operario no cambia**, y la propuesta sigue saliendo de los lotes ENTEROS.
- El freno resta, de cada lote, lo que las guías R **vivas del mismo artículo
  y el mismo día** ya le atribuyeron (`descontar_lo_tomado_hoy`, leído del
  documento congelado). Eso contesta *"¿cuánto se llevó ya el día?"*, que no
  necesita orden.

**El piso en cero no es cosmético**: un lote ya sobre-atribuido aporta cero y
nunca le resta a los de al lado — `bultos_en_los_lotes` promete que su número
no puede ser negativo, porque *"trabar a un operario por un agujero que ya
estaba ahí antes de que tocara nada sería trabarlo por lo mismo que está
arreglando"*. De ahí sale, gratis, que **la guía R de una compra que llega
armada no pueda rebotar nunca**: su propia compra entra como lote intacto en
la misma transacción.

**Y el aviso de la pantalla se movió con el freno.** El `alcanza` del
desglose es el freno adelantado: si midiera contra los lotes enteros diría
que sí y el server rebotaría al apretar Guardar, que es peor que la pared —
llega después de que ya cargó todo. Los dos aplican la MISMA función sobre el
mismo dato, y lo cuida el test que mira el cableado de los tres.

### El rebote SÍ puede caerle a una carga legítima, y no tiene arreglo

No rebota cuando la suma entra: dos guías del día que juntas caben en el lote
no cambian en nada. Pero cuando no entra, **el sistema no puede saber cuál de
las dos es la equivocada**, y la pared le cae al que carga SEGUNDO aunque el
error lo haya cometido el primero.

Por eso la pared **nombra la guía R de hoy que se llevó el lote**. Un "no
alcanza" a secas, un día en que el operario VE los cajones en el piso, es
exactamente el cartel que se aprende a esquivar; con el número de la guía
sabe qué ir a mirar — o esa guía está mal, o falta cargar la recepción que
explica lo que tiene delante.

Y hay una segunda forma de rebote que es nueva y correcta: la mercadería
llegó pero su compra no está recepcionada. Hoy el recorte del mismo día lo
tapaba.

**Lo que el arreglo NO cierra**, dicho para que no se lea como más de lo que
es: con el reparto saliendo de los lotes enteros, un lote puede seguir
recibiendo más de lo que tenía **cuando el artículo tiene otro lote que
cubre el total**. El freno cierra el agujero en la SUMA, no en la
atribución por lote. Es un residuo de costeo y de trazabilidad, y por eso
se deja: los costos están en etapa de prueba.

### Y el riesgo de verdad no es el freno: es la FECHA con que se carga

Del 16/09, y salió de mirar los 132 bultos que esperan guía R —ocho
artículos, el más viejo del 07/09— y preguntarse qué pasa cuando alguien
se ponga a cargarlas.

**Los ocho se pueden cargar, y lo cerró la PANTALLA, no una consulta.**
Probados uno por uno en Reproceso, cada uno con la fecha de su armado:

```
Limon          11/09  entra con 50
Tomate Redondo 09/09  entra con 50
Mandarina      10/09  entra con 35   (con 50 rebota: ese dia habia 40)
Berenjena      07/09  entra con 20
Zapallito      14/09  entra con 20
Lima           10/09  entra con  2
Palta          10/09  entra con  5   (con 20 rebota)
```

**Y la medición que yo había escrito para contestarlo NO contestó nada.**
`db/espera_1_el_freno_nuevo_puede_rebotar.sql` cuenta los días de armado
que ya tienen una guía R ese día — un superconjunto a propósito, porque
cuáles están esperando sale del rejuego del FIFO y escribirlo en SQL sería
la segunda versión de la cuenta que el docstring de
`bultos_esperando_guia_r_por_articulo` prohíbe. Dio **119 de 128** en
Frutamax, y el dueño lo rechazó con la razón correcta: **un superconjunto
que cubre el 93% no acota nada.** Es *"más hallazgos que población condena
la heurística"* aplicado a una CONDICIÓN en vez de a un hallazgo — si casi
todos los días cumplen la condición necesaria, la condición no separa nada.

**Lo que sirvió fue usar la pantalla que ya existe como instrumento.** El
desglose (`/deposito/stock/reproceso/desglose`) es un `GET` de solo lectura
que corre `lotes_para_reproceso` + `descontar_lo_tomado_hoy`, o sea **el
código del freno, no una segunda versión de la cuenta**. Y es usable como
instrumento por una propiedad que hay que tener escrita: **`disponible` no
depende de `bultos`** — el número tipeado solo entra en `alcanza` y en la
propuesta—, así que la prueba es MONÓTONA: si entra con N, entra con
cualquier cosa menor. Alcanza con tipear el número más grande que sea
plausible.

Dos detalles del método, porque se repiten:

- **Lo que se tipea son CAJONES TOMADOS, no las cajas que esperan.** No hay
  correlación entre lo tomado y lo producido (un cajón de 16 puede dar tres
  cajas de 6), así que usar el número del bloque azul mediría otra cosa.
- **Mandarina es donde el renglón nuevo hizo su trabajo**: con 50 rebota
  —ese día había 40— y la pared nombra la guía R de hoy que se llevó el
  lote, que es la diferencia entre un "no alcanza" que se aprende a
  esquivar y uno que dice qué ir a mirar.

**Y el veredicto del freno viejo tampoco se vence**: `reparto_para_
reproceso` de una guía fechada el 07/09 mira entradas hasta el 07 y
salidas hasta el 06, los dos fijos. Cargarla hoy da lo mismo que el día 7.
Solo se mueve si alguien carga algo FECHADO en esos días, y eso solo puede
ayudar.

**Lo que sí es un riesgo es fechar la guía que falta con el día de HOY**, y
lo que lo vuelve digno de una sección es que **dispara DOS guardas
correctas a la vez, y las dos empujan para el mismo lado**:

1. **No tapa el hueco.** Una guía R posterior al armado no lo cubre
   (`lote_posterior_a_la_salida` compara fechas), así que los bultos
   siguen esperando y el bloque sigue mostrándolos. Esto la pantalla ya lo
   avisa desde el 10/09.
2. **Y entra a compartir día con todas las guías R de hoy**, que es
   exactamente donde el freno del 16/09 sí descuenta. O sea que la fecha
   equivocada es lo único que puede convertir esta carga en un rebote.

Ninguna de las dos es nueva por separado; **la que es nueva es que las
dispara el mismo error**. Y ahí está la forma general que conviene
reconocer: cuando se agrega una guarda, la pregunta no es solo a quién
traba — es **qué equivocación única hace fallar a la vez a la nueva y a
una que ya estaba**. Dos guardas correctas que comparten una causa se
sienten como un sistema que se ensañó, y el que la sufre aprende a
desconfiar de las dos.

**Lo accionable, y es una sola cosa**: al cargar estas guías, el único
campo que hay que mirar es la fecha, y va **el día en que se armó**.

## Corolario 74: una respuesta CONGELADA y una DERIVADA a la misma pregunta se separan sin que ninguna esté rota

Del 16/09, y es del dueño: *"las dos cumplen lo que prometen, y nadie las
pone al lado"*. Salió del corolario 73 pero no es de ese bug — es la forma, y
este sistema está lleno de pares así.

Cuando 56 bultos salieron de un lote de 40, el sistema quedó diciendo dos
cosas incompatibles:

```
lo CONGELADO (reprocesos_consumos)  56 salieron del lote, al costo del lote
lo DERIVADO  (el rejuego del FIFO)  el lote en 0 y 16 SIN LOTE
```

**Y las dos son correctas.** `reprocesos_consumos` promete ser *"un documento
congelado: si después se corrige una recepción, el stock vivo se reacomoda
pero esta trazabilidad y su costo no se mueven"* — lo dice su propio comment,
y hace exactamente eso. El rejuego promete recalcular en cada lectura, y hace
exactamente eso. No hay una línea mal escrita en ninguno de los dos.

### Por qué no hay forma de que se avisen

Las dos propiedades que los hacen útiles son las que impiden la alarma:

- **El congelado no puede cambiar** — si cambiara, no serviría para lo que
  existe (el costo al que se facturó no se puede mover porque el stock se
  reacomodó). Así que no puede "enterarse" de nada.
- **El derivado no guarda nada** — no tiene dónde dejar una marca que diga
  "esto no coincide con lo que se escribió aquel día".

O sea que la contradicción **no tiene lugar donde vivir**. No es que falte un
CHECK: un CHECK compara dos cosas en una misma escritura, y acá las dos
respuestas se producen en momentos distintos y con reglas distintas a
propósito.

### Y la pantalla las separa, que es lo que lo vuelve invisible

El que abre el detalle de la guía ve un costo completo y prolijo. El que mira
el stock ve un hueco. **Son dos pantallas distintas y nadie tiene motivo para
abrirlas juntas** — es el corolario 10 (dos vistas del mismo hecho que dan
consejos incompatibles se esconden mientras estén separadas) con la vuelta de
que allá bastó cambiar un orden para que cayeran juntas, y acá viven en
módulos distintos.

### La señal, y se hace al DISEÑAR, no al depurar

**Cuando un dato se congela "para trazabilidad" y el mismo hecho además se
deriva en cada lectura, eso es un PAR, y el par necesita quien lo compare.**
La pregunta que lo detecta: *si estos dos se separaran, ¿qué se rompería?* Si
la respuesta es "nada, cada uno sigue andando", no hay alarma posible y hay
que fabricarla.

No es un argumento para dejar de congelar: congelar el costo es correcto y la
razón está escrita. Es que **el par se elige, y al elegirlo se acepta una
deuda**: alguien tiene que poder preguntar si siguen coincidiendo.

Los pares que ya existen en este sistema, para que la próxima no se busque de
cero:

| congelado | derivado | ¿los compara alguien? |
|---|---|---|
| `reprocesos_consumos` | el rejuego del FIFO | **no** — es este corolario |
| `conteos_stock.stock_sistema` | el stock de ahora | sí, y se decidió sacarlo (corolario 25) |
| `movimientos_stock.stock_sistema` | el stock de ahora | no, y es a propósito: es la foto de auditoría |
| `movimientos_stock.costo_por_bulto` | el costo del listado | no |

**La comparación más barata no es una pantalla: es una consulta que devuelva
los dos números en la misma fila** — que es lo que hace `mismo_dia_1` contra
lo congelado, y lo que le falta del lado derivado. Una fila con los dos al
lado es lo único que convierte "nadie los pone juntos" en "no coinciden".

**Y el precio de no tener la comparación no es el descuadre: es que el
descuadre se ve como dos pantallas sanas.** Es la familia entera de este
archivo —el cero que no puede crecer, la columna que nadie escribe, el campo
sin consecuencia— dicha una vez más: lo que hace daño no es el dato malo, es
que se vea igual que el bueno.

## Corolario 75: un CHECK de coherencia entre DOS columnas es una pared si el código escribe UNA

Del 17/09, y es del dueño. La migración del bloque 7 agregó esto sobre
`movimientos_stock`:

```sql
check ((lleva_caja_nuestra is true) = (envase_id is not null))
```

**El CHECK está bien escrito y cubre las dos direcciones**, que es
exactamente lo que este archivo pide (una guarda que cubre un solo lado deja
pasar el espejo en silencio). Lo que no estaba era la otra mitad del par: el
código escribía `envase_id` y **nunca** escribió `lleva_caja_nuestra`. Así
que la base rechazaba todo reingreso a `reproceso` de una ficha con envase
derivable, y la guarda dejó de proteger para pasar a trabar.

**Y el modo de falla es el peor que puede tener una migración: una pared que
aparece el día que alguien usa un camino que hasta entonces nadie usó.** No
falla al migrar, no falla en la verificación, no falla con los datos que hay.
Medido en las dos bases el día que se sacó: `vuelven_a_cajon 0` sobre **27
reingresos** en Frutamax. La mina estuvo enterrada un día entero y **la
desactivó el drop, no el uso** — lo único que la hacía invisible era que
nadie había cargado todavía un rechazo de esa forma.

### Por qué NINGUNA de las guardas que ya teníamos lo ve

Y es lo que lo vuelve una familia y no un descuido:

- **La verificación de la migración pregunta por las filas que ESTÁN**, y su
  `ofensores` cuenta `lleva_caja is true and envase_id is null`. Todas las
  filas viejas tienen las dos en NULL, que es un caso legítimo, así que sale
  **0 y es correcto**. Lo que nunca se cuenta son las filas que **no van a
  poder entrar**, porque todavía no existen.
- **El CHECK no puede saber que su segunda mitad no se llena.** Una guarda
  declara una relación entre dos columnas; no sabe cuáles se escriben.
- **Los tests del INSERT comparan la tupla ENTERA** y coincidían: la columna
  no estaba ni en el INSERT ni en lo esperado. Es el corolario 72 otra vez —
  un campo que nadie nombra no desajusta una comparación entre dos listas que
  tampoco lo nombran.
- **Y la pantalla andaba**, porque el camino que rebota es el que nadie
  cruzó.

### La pregunta que lo encuentra, y se hace el día que se escribe el CHECK

> **Después de un CHECK que relaciona dos columnas, grepear el INSERT y el
> UPDATE por LAS DOS.** Si aparece una sola, la guarda no es una guarda: es
> una pared esperando al primero que pase.

Cuesta un `grep` y se hace en el mismo commit que la migración. Y es el
corolario 3 con una vuelta: allá el que falta no nombra el campo, así que
hay que grepear el CONSTRUCTOR; acá **el constructor existe y nombra una de
las dos**, que se lee como cobertura y es media.

### Con qué engancha, y son los dos extremos del mismo eje

| | qué le pasa a la guarda | cómo se ve |
|---|---|---|
| **Corolario 67** | evalúa NULL y **no rechaza nada** | todo entra, incluido lo que no debía |
| **Corolario 72** | la columna no tiene escritor y **suma cero** | un cero prolijo que nadie lee como hueco |
| **Éste** | rechaza **de más**, en un camino frío | no se ve hasta que alguien lo camina |

Los tres salieron de la MISMA migración de cinco bloques, y ésa es la
observación que más conviene guardar: **una tanda de bloques escritos el
mismo día comparte los supuestos del que los escribió**, así que un error de
lectura del mundo no aparece una vez — aparece en todos los bloques que se
apoyaban en él. Revisar uno no dice nada de los otros cuatro.

### Y el control que lo cerró fue la POBLACIÓN, no las columnas

La verificación del drop trae `movimientos_POBLACION` y se corre las dos
veces, antes y después:

```
FRUTAMAX  antes 109 · después 109
PALMALA   antes   1 · después   1
```

`columnas 0 · guardas 0` dice que se fue lo que tenía que irse. **No dice que
no se haya ido nada más.** Un `drop column` no toca filas, así que el
conteo igual antes y después es lo único que separa "salieron las dos
columnas" de "se llevó algo puesto" — y cuesta una columna más en una
consulta que ya se iba a correr.

Es el corolario 45 en su cuarto trabajo: el testigo del 24 dice si la base
vota, el total esperado dice si la medición llegó al final, el denominador
del 53 dice cuál pantalla se midió, y acá dice **qué NO se rompió**. Los
cuatro existen por lo mismo — un número solo no se puede leer.

## Corolario 76: un argumento CIERTO sobre la plata no decide sobre una lista que ENUMERA

Del 17/09, y es del dueño en una frase: **"falta el nombre, no la plata, pero
el nombre es lo que la vuelve negociable."**

`reproceso` perdía la caja y quedó dos días afuera de `cajas_perdidas` —el
renglón que las NOMBRA— con este argumento mío: esa caja ya está cobrada
adentro de `rechazos_perdidos`, así que agregarla no mueve un peso.

**Todo eso es cierto y sigue siéndolo.** Lo verifiqué, está medido, y el
renglón efectivamente no entra en ninguna suma. El argumento no tenía una
premisa falsa —que sería el corolario 25— ni un número mal. **Lo que estaba
mal es contra qué se evaluaba la cosa.**

> **Una lista que ENUMERA no se evalúa por lo que cobra: se evalúa por si se
> puede llevar a discutir.** Y a la que le falta un tercio de las puertas no
> se puede — el de enfrente pregunta por las que faltan y la conversación se
> termina ahí.

Es la familia del corolario 25 corrida un lugar y por eso cuesta más verla:
allá el razonamiento era válido y la PREMISA no se había medido; acá la
premisa estaba medida, el razonamiento era válido, **y la dimensión era otra**.
No hay nada que medir para encontrarlo: hay que preguntarse para qué existe
la cosa.

**La señal, y es una sola pregunta**: cuando un argumento para dejar algo
afuera empieza con *"total, no cambia ningún número"*, preguntarse **si el
número es para lo que esa cosa existe**. Un total, un costo, una alerta que
frena: ahí la plata decide. Un renglón que nombra, un detalle, una lista de
reclamo, un chip al lado de un artículo: ahí decide si está COMPLETA, y "no
mueve nada" es exactamente lo que se espera de él.

### Y lo que sí había que probar era lo contrario

Nombrarla en dos lugares se lee como doble conteo. Que no lo sea **no se ve
mirando los dos números**, y la primera versión del test lo "probaba" así:

```python
mercaderia = rechazos_perdidos - cajas_perdidas_pesos
assert rechazos_perdidos == mercaderia + cajas_perdidas_pesos   # x == (x−y)+y
```

Cierto por álgebra. **Corolario 41 adentro del test escrito para cerrar el
caso**: pasa con el envase cobrado una vez, dos o ninguna — medido con el
canario del cobro doble, que la versión vieja pasa y la nueva hace caer.

Lo que sirve es una corrida de CONTROL que produzca el otro número por su
cuenta: la misma devolución con `envase_unidad = 0` da la mercadería sola, y
lo que CRECE al ponerle envase tiene que ser exactamente lo que el renglón
nombra. Dos números de dos lugares, no una resta y su inversa.

**La señal, para reconocerlo sin correr el canario**: si el valor contra el
que se compara se DERIVA de los mismos números que se están comparando, la
igualdad no puede fallar. El control tiene que venir de otra corrida, otra
consulta u otra fuente — es la misma regla que *"la verificación que funciona
es la que hace chocar dos fuentes"* (corolario 19), acá adentro de un test.

**Y el renglón que este corolario defendió YA NO SE VE EN CAJAS** (17/09): la
pantalla pasó a ser solo stock y `cajas_perdidas` se fue con el resto de la
plata. **El corolario no se mueve**: sigue diciendo que una lista que ENUMERA
se evalúa por si está completa. Lo que envejeció es DÓNDE se ve, que es el
estado que se anota al lado del mecanismo para ilustrarlo.

**Y el "va a volver a dibujarse el día que alguien la cablee en Gerencia" ya
pasó**: vive en `/gerencia/cajas-perdidas` ("Plata de cajas"), con el renglón
del depósito adentro. Desde el 21/09 ese renglón cuenta **la merma Y el pase**
de cajas armadas, no solo el pase, y el chip dice `N del depósito` para
separar contra QUIÉN se reclama: una caja perdida en un rechazo es una
conversación con el CLIENTE, y una tirada o pasada a segunda es con el
DEPÓSITO, porque la fruta se puso fea acá adentro.

## Corolario 77: un `JOIN` contra la fila que todavía no existe no devuelve cero, DESAPARECE

Del 17/09. Las tres patas del stock de cajas entran por `JOIN base`, donde
`base` es el conteo inicial de ese envase. Un envase recién dado de alta no
tiene esa fila, así que **`declarados` y `guias` no producen ni un renglón**
y todo lo que se le cargó —una compra de doscientas cajas, un préstamo, una
guía R— es invisible.

La pantalla decía "todavía sin conteo inicial", que es **verdadero y no
alcanza**. El que compró las doscientas entra, lee que la cuenta no arrancó,
y no tiene forma de saber que sus doscientas ya están cargadas y escondidas.
Es la ausencia de filas del backfill con otro disfraz: *"acá no hay nada"* y
*"acá hay cosas que no puedo mostrarte"* se dibujan exactamente igual.

**Y el aviso que lo tapa tiene que contar SIN EL JOIN**, que es lo que sale
al revés: escrito al lado de las otras tres patas, lo natural es copiarles el
`JOIN base`, y entonces el contador da **cero justo en el único caso que le
importa** — un cero que no puede dar otra cosa (corolario 47), adentro del
arreglo escrito para el corolario 47. Lo cuida
`test_lo_que_ESPERA_AL_CONTEO_se_cuenta_SIN_PASAR_POR_base`, que lee el
cuerpo de esas dos CTE y exige que la palabra `base` no esté.

**Y la otra mitad, que es del corolario 8**: el contador se apaga en CERO
cuando el conteo SÍ existe. Sin eso, un envase con la cuenta andando
devolvería sus movimientos como "esperando" y habría que mirar `desde` al
lado para saber si el número significa algo. **Una columna que significa dos
cosas según otra columna no es una columna: son dos.**

### El aviso nombra la FECHA, porque "ponelo antes" no dice antes de qué

El recorte es `fecha_operacion >= conteo.fecha`, así que lo que decide si
una compra vieja se suma o queda absorbida **es la fecha del conteo**, y hay
tres casos que el que arranca la cuenta tiene que poder distinguir:

| lo que quiere | qué carga |
|---|---|
| contó las cajas que ya le llegaron | la cantidad, fechado **hoy** — esas compras quedan absorbidas |
| que una compra ya cargada se sume | **cero cajas**, fechado **antes** de esa compra |
| ~~contar las cajas Y fecharlo antes de la compra~~ | **nunca** — se suman dos veces |

**El tercero es el que alguien va a hacer, y es el que no avisa**: no
descuadra nada, el stock queda alto, y el aviso de reposición llega tarde
para siempre. Por eso la regla va **en la pantalla y no en un doc**: el que
arranca la cuenta está ahí y no va a ir a buscar nada. Y por eso el aviso
dice la fecha del movimiento más viejo —la más vieja **de las dos** patas, no
la de una— porque *"fechá el conteo antes"* sin un día al lado no se puede
obedecer.

**Cero es una respuesta válida**, y va dicho donde se decide qué tipear. Sin
esa frase, el que tiene doscientas esperando cuenta doscientas, que es
exactamente el tercer caso.

### Y los movimientos y las guías R van SEPARADOS, no sumados

Se cargan en pantallas distintas. Un solo *"3 esperando"* manda a buscar en
la lista de movimientos de ese envase una guía R que nunca estuvo ahí —el
operario encuentra 2 y se queda pensando cuál falta—. Cuesta una columna más
y es la diferencia entre un número que se puede ir a verificar y uno que hay
que creer. Es el corolario 74 evitado antes de existir: dos respuestas
verdaderas que no se pueden poner una al lado de la otra.

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

## Una pantalla de EXISTENCIAS no es donde se cuelga todo lo que dice la misma palabra

Del 17/09, y también es del dueño: *"esto sirve para una cosa: saber cuántas
cajas tengo, a quién le presté y quién me debe. Nada más."*

`/compras/cajas` había juntado **tres preguntas distintas** debajo de la
palabra "cajas": cuántas hay (existencias), cuánto se gastó en comprarlas
(plata, 90 días) y cuánto se llevaron los rechazos (plata, 90 días). Ninguna
estaba mal calculada; las tres estaban en el mismo lugar por compartir un
sustantivo.

**Cómo se reconoce, y no hace falta que nadie se queje**: si dos bloques de una
pantalla **se miran en momentos distintos** —el stock antes de reponer, el
gasto al cerrar el mes— o **los mira gente distinta**, están juntos por el
nombre y no por el uso. La pregunta que lo separa es *¿esto lo abre la misma
persona en el mismo momento?*, y se contesta sin datos.

**Y las cuentas NO se borran cuando se saca el bloque**: `gasto_en_cajas` y
`cajas_perdidas` quedan enteras con sus tests, así que mudarlas a Gerencia es
cablear una pantalla y no reescribir dos cuentas —con sus ventanas, su
valuación al costo del día de la compra y su orden por plata—.

**Y se mudaron: las dos se ven en `/gerencia/cajas-perdidas`**, así que la
frase que decía que "sin un solo llamador son lo que se lee como 'no se usa'"
dejó de aplicarles. Lo que sí queda del párrafo es el mecanismo: mientras una
cuenta no tenga llamador, **el test que la nombra es la única señal de que
existe** — y eso vale para la próxima que se descuelgue de su pantalla.

(`cajas_perdidas_por_rechazo` se llama `cajas_perdidas` desde el 21/09: dejó
de contar solo los rechazos cuando entró la merma de cajas armadas, y un
nombre que nombra un subconjunto de lo que cuenta es el corolario 8 esperando
a que alguien lo cite mal.)

**Y los imports SÍ se sacan**, que es la mitad opuesta: un `from app.db import
gasto_en_cajas` que nada usa hace creer al próximo que lee la ruta que la
pantalla todavía lo muestra. La función se conserva donde vive; el cableado
muerto se corta.

## Corolario 79: un parámetro sin escritor es una FUNCIÓN QUE FALTA — o una que SOBRA

**LEER PRIMERO, del 18/09: el caso de abajo se resolvió AL REVÉS y eso cambia
el corolario, no solo su ejemplo.** `envase_declarado` no esperaba una
pantalla: **no tenía que existir**. La regla que lo pedía trataba la ficha
variable como un caso a preguntar, y la caja sale siempre de la ficha.

O sea que un parámetro sin escritor tiene **DOS** explicaciones —falta
cablearlo, o sobra— y **las dos se ven idénticas**: el parámetro está, el `if`
que lo usa está escrito y probado, y la pantalla se ve entera. La pregunta de
abajo (*¿quién lo PASA?*) encuentra el síntoma y **no distingue los dos
casos**. La que los separa no es de código: es **¿el hecho del mundo que este
parámetro afirma, ocurre?** — y eso se pregunta, no se grepea.

Es literalmente el corolario 72 con su corrección del 17/09 (la columna
`liberadas`, que sumaba cajas que se van a la basura), repetido un día después
sobre un parámetro. **Dos veces la misma semana construí la mitad que
cableaba en vez de preguntar si el caso existía**, y las dos veces la premisa
costaba una pregunta de una línea. La que funciona es la abierta —*"¿qué pasa
con la caja cuando…?"*— y no la cerrada, que tiene dos respuestas y una es un
asentimiento (corolario 71).

Lo que sigue en pie sin cambios es el MECANISMO: un parámetro que solo pasan
sus tests no es un parámetro con default. Lo que cambia es qué se hace después
de encontrarlo.


Del 17/09, y es el corolario 72 sobre un parámetro en vez de sobre una
columna — con un agravante que lo vuelve peor: **una columna sin escritor
devuelve un cero prolijo; un parámetro sin escritor deja el `if` que lo usa
escrito, probado y visible.**

`_envase_de_esta_guia(cursor, ficha_id, envase_declarado)` tenía el
parámetro desde el primer día, con su docstring diciendo *"es lo que contestó
la persona cuando hubo que preguntar"*, y la línea que lo usa:

```python
if hay_que_preguntar and envase_declarado is not None:
    return envase_declarado
```

**Nadie lo pasó nunca.** `grep` del nombre en `app/`, `core/` y `templates/`:
cero fuera de su propia definición. Y `envase_derivado_de_la_ficha` define
tres casos, el tercero de los cuales dice **"si no se puede derivar, se
PREGUNTA"** — la pregunta se diseñó, se le dejó el cable, y nunca se
construyó la pantalla.

**La consecuencia, y por eso valía atacarlo antes que nada**: con ficha
variable —Mango y Cherry, los dos artículos que más se mueven— la caja sale,
es nuestra, y **no se descuenta nunca**. El stock de cajas queda alto
justamente donde más rota.

### Por qué se lee como si estuviera cableado

Un lector que abre `_envase_de_esta_guia` ve el parámetro, ve el `if`, ve el
docstring que explica cuándo llega, y **concluye que llega**. Es lo contrario
del campo sin consecuencia (que se ve vacío) y del `{% else %}` que afirma de
más (que se ve raro al leerlo): **acá el código está bien escrito y completo,
y lo que falta está AFUERA de él.**

Ninguna guarda de las que ya teníamos lo ve:

- el **CHECK de coherencia** relaciona `lleva_caja_nuestra` con `envase_id`, y
  las dos en NULL lo cumplen;
- el **test de la estructura entera del INSERT** compara dos listas que
  escriben NULL en esas columnas, y coinciden;
- los **tests de la función** le pasan `envase_declarado` a mano —porque el
  test sí puede— así que el camino se ejercita y pasa;
- y la **pantalla** se ve perfecta: no hay campo que falte, porque el campo
  nunca existió.

### La pregunta que lo encuentra

> **Para cada parámetro OPCIONAL que cambia el resultado, grepear quién lo
> PASA.** Si los únicos que lo pasan son sus tests, no es un parámetro con
> default: es una función que falta, y el default es el bug.

Es el corolario 71 —una regla en una función pura sin llamadores es un
adorno— corrido al argumento: allá había que contar llamadores de la función,
acá de un parámetro. Y las dos veces lo que engaña es que **el código
existe, es correcto, y tiene tests verdes**.

### Lo que quedó de las dos subsecciones que había acá

Describían cómo se había cableado la negativa: que la política vive en el
llamador y no en el núcleo (corolario 75), y que una guarda que solo lee una
fila va ARRIBA, junto al piso de la fecha, y no abajo con el costo — lo
segundo lo destapó un canario: con el stock también corto, el operario veía
la pared del stock primero, iba a cargar una recepción, volvía, y recién ahí
se enteraba de que faltaba contestar un select.

**Las dos son ciertas y ninguna tiene hoy un caso en este sistema**, porque
la negativa se fue entera. Se dejan dichas en un párrafo en vez de borradas:
**el orden de las guardas no es estilo, es cuántas veces vuelve el que
carga**, y eso va a volver a hacer falta.

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
## Corolario 90: un workflow de CI no se puede correr donde se escribe, así que se prueba POR PARTES — y el simulacro del entorno da hallazgos Y artefactos

Del 19/09, y sale de montar el gate que faltaba. **Un `.yml` de GitHub
Actions es código que solo corre en un lugar donde no estoy**, así que la
tentación es escribirlo, pushearlo, y usar el primer push como la primera
corrida. Eso es exactamente lo que el gate viene a terminar: descubrir que
algo no anda cuando ya está afuera.

Lo que sí se puede probar acá es **cada pieza por separado**, y las tres que
se probaron encontraron dos bugs reales:

1. **El bash de cada paso se corre tal cual.** El paso que instala el cliente
   decía `command -v psql || sudo apt-get update && sudo apt-get install`, y
   `A || B && C` parsea como `(A||B) && C`: **con psql presente instalaba
   igual**. Medido en bash, no leído — `bash -c 'true || echo B && echo C'`
   imprime C.
2. **La conexión a Postgres, por los DOS caminos.** El contenedor corre como
   root con autenticación `peer` (`su postgres`); el runner levanta Postgres
   como servicio en 127.0.0.1 con usuario y contraseña. Escrito para uno, en
   el otro no corre — y el modo de falla del segundo es el caro: el test se
   SALTEA y un salteado se lee igual que un verde.
3. **La guarda del paso, con su par** (corolario 53): la corrida sin
   salteados sale 0, y la misma con Postgres caído sale 1 **nombrando el test
   que se salteó**. Un guardia que no puede dar las dos respuestas no es un
   guardia.

### El simulacro del entorno: un hallazgo REAL y un ARTEFACTO, y hay que separarlos

Corriendo el humo **como un usuario que no es root**, que es lo más cerca del
runner que se llega acá, salieron dos fallas y **solo una era del workflow**:

| | qué pasó | ¿es del CI? |
|---|---|---|
| `PermissionError: /tmp/siembra_humo.sql` | ruta FIJA en /tmp: el archivo que dejó root no lo puede pisar otro usuario | **SÍ** — habría roto el primer push. Arreglado con `tempfile.mkstemp` |
| `No module named 'idna'` | ese usuario no ve el `~/.local` de root | **no** — en el runner `pip install -r requirements.txt` lo trae, y está verificado que `idna` es dependencia declarada de `httpx` |

**Y separarlos no es opcional**: perseguir el artefacto habría terminado
agregando `idna` a `requirements.txt` —una dependencia que producción no
necesita— para arreglar algo que no pasa. Es el corolario 6 con otra ropa: un
diagnóstico falso decide qué se arregla después, y acá el diagnóstico falso lo
produce el propio banco de pruebas.

**Cómo se separan, y es una pregunta**: *¿esta falla la produce lo que estoy
probando, o cómo lo estoy probando?* Se contesta yendo a la fuente —acá,
`pip show httpx` diciendo que `idna` es suya— y no volviendo a correr el
simulacro, que va a seguir fallando igual.

### La mitad que NINGÚN archivo del repo puede cumplir

El workflow corre y pone la corrida en rojo. **Railway despliega igual**,
en paralelo, sin mirarlo — el CI avisa, no frena. Que además BLOQUEE es un
interruptor de Railway (`Service → Settings → Deploy → "Wait for CI"`) y lo
tiene que activar una persona.

Eso va escrito **arriba de todo en el `.yml`**, y no en un doc: el que dentro
de seis meses se pregunte por qué un deploy salió con el CI en rojo va a
abrir el workflow, no este archivo. Y mientras ese interruptor esté apagado,
el gate es **media guarda**: encuentra el bug y no lo frena, que es mejor que
nada y no es lo que dice el título.

## Corolario 80: una cuenta DERIVADA convierte "completar el dato" en "arreglarlo", y eso decide si hay que recargar

Del 17/09, y es la propiedad que más veces salvó a este sistema, vista del
lado bueno por tercera vez.

Las dos guías R de Frutamax que no declaraban su caja **no hubo que anularlas
ni recargarlas**: el stock de cajas no vive en una columna, se rejuega en cada
lectura, así que escribir `lleva_caja_nuestra` y `envase_id` alcanza para que
la guía empiece a descontar. Medido contra el esquema real, no leído:

```
las dos en NULL                        contadas 500 · por_guias   0 · stock 500
declaradas en caja nuestra (10 y 6)    contadas 500 · por_guias -16 · stock 484
declaradas DESCARTABLE                 contadas 500 · por_guias   0 · stock 500
```

Es la misma propiedad que hace que **anular una guía R corrija el stock sola**
—está escrita en el docstring de `stock_de_envases` desde que se construyó— y
la que hace que el reparto del FIFO se acomode cuando aparece la guía R que
faltaba. Escrito como una columna que alguien actualiza, completar el dato
habría sido un segundo lugar del que acordarse, y el día que se olvide el
stock queda mintiendo.

**La pregunta que hay que hacerse antes de decidir si un arreglo necesita
recargar**: ¿el número sale de una columna o se deriva? Si se deriva,
completar el dato de origen ES el arreglo, y no hay nada más que hacer. Si
vive en una columna, hay dos lugares y hay que tocar los dos.

### Y la puerta de las que YA ESTÁN no es la misma que la pregunta nueva

*(El 18/09 la pregunta Y la puerta se borraron las dos: no había nada que
preguntar. Lo que sigue valiendo entero es el párrafo de arriba —completar el
dato de origen ES el arreglo cuando el número se deriva— y es justo lo que
hace que a las dos guías de Frutamax les alcance un backfill de dos filas en
vez de una anulación. Lo de abajo describe una puerta que ya no existe, y se
deja por el argumento del CALLEJÓN, que vale para cualquier botón: ofrecer
algo que la escritura después rechaza es peor que no ofrecer nada.)*

Son dos construcciones y hacen falta las dos: la pregunta en Reproceso cierra
el agujero **desde hoy**, y sin una puerta para las que ya están, lo viejo
solo se arregla anulando y recargando —o tocando la base a mano, que es el
corolario 31—. Cerrar la puerta y no curar lo que ya pasó deja un número
inexplicable para siempre.

**Y LA PUERTA SE OFRECE SOLO DONDE LA ESCRITURA ACEPTA.** Las dos preguntan
con la MISMA función (`envase_derivado_de_la_ficha`), así que no puede haber
un botón que el POST después rechace. Un callejón —ofrecer algo que al
apretar da error— es peor que no ofrecer nada: el que lo aprieta se come un
error por algo que la pantalla le propuso.

Concretamente, la guía **vieja** (anterior a la migración, con ficha de envase
FIJO y la columna en NULL) **no se ofrece**: su caja sale de la ficha, y
dejarla declarar a mano sería re-etiquetar la historia — lo mismo que este
proyecto se negó a hacer con `unidad_compra`. Ésa se arregla reasignándole la
ficha, que re-deriva.

### El control que el canario pidió, y por qué el que había no servía

El canario que saca la condición de "no lo puede derivar" **dio CERO**, y el
test de control existía: una guía cuya ficha define la caja, que no tiene que
ofrecer el formulario. **Pero esa guía tenía `lleva_caja_nuestra` en True**,
así que la excluía la PRIMERA condición y la segunda nunca se ejercitaba.

> **Un control que se cae por el motivo equivocado no es un control.**

El fixture que sí lo ve es el que pasa la primera condición y falla la
segunda: caja en NULL **y** ficha fija. Es el corolario 30 con dos guardas en
serie — para probar la segunda hay que pasar la primera, y un fixture que
rebota antes las aprueba a las dos sin mirar ninguna.

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

## Corolario 81: DERIVAR un caso de una regla no es lo mismo que preguntar si el caso existe

Del 18/09, y es del dueño. Es una forma distinta de todas las de este
archivo, y por eso lleva número propio en vez de quedar como una frase
adentro del caso que la produjo:

- **no hubo una premisa falsa** (corolario 25): la regla era verdadera.
- **no hubo un número mal medido** (corolarios 6, 11, 45, 69): no se midió
  nada, porque no había nada que medir.
- **no hubo un requisito leído de más en el pedido** (corolario 29): el
  pedido no decía nada de esto ni cerca.

Lo que hubo es **un caso derivado de la forma de la regla, sin preguntar si
ese caso ocurre.** `envase_derivado_de_la_ficha` tenía dos casos que alguien
había pedido —ficha con envase, ficha sin envase— y yo agregué un tercero
porque la regla, escrita así, parecía tener un hueco: *si no se puede
derivar, se pregunta*. De ahí salieron una pregunta en Reproceso, una puerta
en Guías R, una negativa que no dejaba guardar, y un parámetro que nunca
tuvo escritor. **La caja sale de la ficha y ese hueco no existía.**

### Por qué convence más que un requisito inventado

El corolario 29 nace de leer de más lo que alguien pidió, y eso se siente
como una interpretación — algo que uno sabe que está haciendo. **Éste nace
de completar una simetría**, y eso se siente como rigor: la regla tiene tres
casos, dos están contemplados, falta el tercero. Nadie revisa un razonamiento
que se ve prolijo.

**La simetría es una buena razón para SOSPECHAR que un caso existe. Nunca es
una razón para construirlo.**

### Y la señal la escribí yo, en el mismo commit que introdujo el caso

El docstring decía, textual: *"Los tres casos, y el tercero **no estaba en el
pedido** pero sale de la misma regla"*.

Estaba anotado, al lado, en mayúsculas prácticamente, y no me detuvo. Y la
razón de que no detenga es la que hay que entender:

> **Escribir "esto no me lo pidieron" no es lo mismo que preguntarlo.**

La anotación se siente como la honestidad ya ejercida — se parece tanto al
acto de señalarlo que lo reemplaza. Pero es una nota sobre el ORIGEN del
caso, escrita en el código, para uno mismo; y lo que hace falta es una
pregunta sobre el MUNDO, hecha a la persona que lo conoce. Son dos actos
distintos y el primero no paga el segundo.

**Lo accionable, y cuesta una línea de chat**: una frase de esa forma
—"no estaba en el pedido", "sale de la misma regla", "por simetría", "el caso
que falta"— **es la orden de preguntar antes de escribir la primera línea**,
no una licencia para escribirla dejando constancia. Y la pregunta es la
abierta (corolario 71): *"¿qué pasa cuando…?"*, nunca *"esto pasa, ¿no?"*.

### Y lo único que salió bien: BORRARLA fue un solo cambio

La pregunta se mostraba en tres lugares —el selector de Reproceso, el
`falta_la_caja` de Guías R y la guarda del server— y los tres se apagaron
cambiando **la rama de una función**. Ninguno tenía su propio
`if envase_variable`.

Eso es más que una comodidad: **es la única prueba dura de que una regla
estaba escrita una sola vez.** Un test puede afirmar que dos lugares
coinciden hoy; lo que demuestra que no son dos copias es que borrar la regla
los apague a los dos. La cantidad de lugares que hay que tocar para sacar
algo **es la medida de cuántas veces estaba escrito**, y se cobra justo el
día que resulta que no iba.

Por eso vale al revés también, y es la parte usable: **cuando algo se
construye sobre una premisa que todavía no se preguntó, escribirlo en UN
lugar no es prolijidad — es lo que hace que deshacerlo salga gratis** el día
que la premisa se cae. Es el corolario 29 en su parte buena (*un cambio que
todavía no tiene usuarios se escribe de forma que deshacerlo sea gratis*),
con el mecanismo dicho: la forma de que sea gratis es que la regla tenga un
solo lugar.

## EL RENGLÓN QUE EL SÚPER PIDE POR TELÉFONO (18/09)

El pedido llega por mail y el sistema lo lee. Después el súper llama: *"subime
a 8 lo de Banana, y agregame 5 de Lima que no te puse"*. Hasta el 18/09 la
única salida era **recargar el pedido entero**, y eso le cuesta el armado a
todo renglón cuya cantidad se haya movido — el traslado solo viaja donde
(artículo, sucursal, cantidad) son idénticos.

**Y LAS DOS MITADES ERAN LA MISMA COSA, que es lo que el planteo no veía.** El
pedido del dueño separaba "agregar un renglón" de "corregir una cantidad,
que eso lo puedo editar". **No se podía editar**: `pedidos_renglones.cantidad`
no tenía un solo UPDATE en todo el código —los seis que existen tocan
`ficha_id`, `armado_el`, `cantidad_armada`, `kilos_enviados`, `anulado_el` y
`controlado_el`— así que las dos iban por la misma puerta, que era recargar.

**Y el artículo "que no estaba" suele ESTAR.** El confirmar guarda los
renglones sin cantidad igual, con `cantidad = 0` y sin sucursal: *"nada del
mail se pierde"*. Si vino en la comanda en cero, el renglón existe y lo que
falta es darle cantidad — por eso el alta **rechaza** el artículo que ya está
en esa sucursal y manda a corregirlo. Dos renglones del mismo artículo y
sucursal cuentan la demanda dos veces en la Rentabilidad, que suma por fecha y
artículo.

### Las dos marcas, y por qué son dos columnas y no una

El dueño lo pidió así: *"quiero que se vea que ese renglón lo puse yo y no
vino en el mail, porque el día que algo no cierre contra la orden de compra
eso es lo primero que hay que mirar"*. `pedidos.origen` es del PEDIDO y no del
renglón, así que no alcanzaba.

| | qué guarda | qué pregunta contesta |
|---|---|---|
| `agregado_a_mano_el` | CUÁNDO | ¿este renglón vino en la comanda? |
| `cantidad_original` | el NÚMERO VIEJO | la OC dice 5 y el sistema 8, ¿por qué? |

**La segunda guarda un valor y no una hora a propósito.** Un timestamp dice
que alguien tocó; el número viejo dice qué decía la comanda, que es la
pregunta que de verdad aparece. Y se escribe **una sola vez**, con un
`COALESCE`: la segunda corrección pisaría el único dato que contesta.

### Y el renglón a mano SOBREVIVE A LA RECARGA — con el mail ganando el empate

Decisión del dueño: *"si el súper agregó un artículo por teléfono, eso es real
y no está en el mail. Que una recarga lo borre significa que al operario se le
desaparece mercadería que ya armó, sin que nada avise. Y el mail corregido no
lo va a traer nunca — si lo trajera, ya no sería un renglón agregado a mano"*.

**Cuando SÍ lo trae, gana el del mail**, y las cuatro razones:

1. **No son dos pedidos: es el mismo dicho dos veces** —pediste por teléfono y
   después llegó por mail—, así que conservar los dos duplica la demanda.
2. **La comanda es el documento contra el que se concilia la orden de compra.**
3. Es **más nueva**.
4. Y **la razón de existir del manual se apagó**: existía porque el mail no lo
   traía.

El empate se resuelve por **(artículo, sucursal)**, y el armado no se pierde:
el traslado que ya existía lo lleva del viejo al del mail cuando la cantidad
coincide. Si la cantidad cambió no viaja, que es lo que el sistema ya hace con
cualquier renglón cuyo número se movió.

**Y hay DOS detalles de orden que no son estilo:**

- **La copia va ANTES del traslado del armado.** Al revés, el renglón
  conservado aparece SIN armar — que es exactamente la mercadería que
  desaparece que esto vino a evitar.
- **La SUCURSAL se copia si el mail nuevo ya no la trae.** La pantalla de
  armar itera `pedidos_sucursales`: sin eso el renglón conservado existiría
  sin que nadie pueda verlo (corolario 68).

**Y la recarga AVISA cuántos va a conservar**, que fue la otra condición: sin
esa línea el total del pedido guardado no cuadra contra la comanda que se
acaba de pegar, y eso se lee como un error de lectura de la IA — la primera
sospecha razonable, y manda a mirar el lugar equivocado.

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

## Corolario 84: una premisa del DUEÑO también se verifica, y la que se cae agranda el pedido

Del 18/09. El pedido venía con una premisa adentro: *"no es que pidan más
cantidad de algo que ya está, **eso lo puedo editar**"*. Era falsa, y lo dijo
un `grep` de los seis `UPDATE pedidos_renglones` que existen: ninguno toca
`cantidad`.

**Lo que se habría construido creyéndole es media función.** El caso "me
pidieron 5 más de algo que ya estaba" —que es el más común de los dos— habría
seguido necesitando recargar el pedido entero, y el dueño se habría enterado
usándolo.

Y no es la familia del corolario 71, donde el dato del galpón llega mal porque
se pregunta en medio de un arreglo. **Acá la premisa es sobre EL SISTEMA, no
sobre el mundo** — y de esas el repo es la fuente, no la memoria de nadie. La
regla, entonces, es la que separa las dos:

> **Lo que el dueño sabe del GALPÓN se le pregunta. Lo que afirma del SISTEMA
> se verifica en el código, aunque venga en la misma oración.**

Las dos mitades importan. Discutirle un hecho del negocio es perder el tiempo
—él lo ve todos los días y nosotros no—; creerle una afirmación sobre lo que
el código puede hacer es construir sobre una lectura que él no tiene por qué
tener. La frase de este caso tenía las dos: el hecho del negocio (el súper
agrega por teléfono) era cierto, y el del sistema (lo puedo editar) era falso.

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
   pendientes más viejas van a un aviso sin sumarse. Uno solo abierto, sea del
   día que sea. Detalle en `docs/que_comprar_hoy.md`.

   **Lo que no mira, anotado para el día que dé un número raro**: una compra
   en camino que viene ARMADA en caja nuestra se suma a la fila del artículo
   sin mirar de qué cliente es la ficha; las cajas de la FOTO sí se filtran
   por cliente tildado. Una armada para Coto achica lo que falta para Día, y
   el listado propone de menos. Dónde iría el filtro: en
   `compras_alrededor_de_la_salida`, por ficha, igual que en la foto.

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

## Corolario 94: una migración de EXPAND se corre cuando se escribe; el DROP espera al deploy

Del 22/09, y es de secuencia y no de SQL.

`cargas_compra` reemplaza a `listados_compra_manual` y
`listados_compra_clientes`, así que la tanda tiene dos clases de bloque y
**solo una se puede correr el día que se escribe**:

| | cuándo corre | qué pasa si se adelanta |
|---|---|---|
| los que **CREAN** (bloques 1, 2 y 4) | ya, sin esperar nada | nada: una tabla que nadie lee no molesta |
| el que **DROPEA** (bloque 3) | **después del deploy** | el código vivo en Railway sigue leyendo esas tablas y revienta |

**La asimetría no es de prudencia: es de qué está corriendo en producción
mientras tanto.** Entre que el SQL se corre a mano y que el commit se
despliega pasan minutos u horas, y en esos minutos el código que hay arriba es
el viejo. Crear no lo toca; borrar le saca la tabla de abajo.

**Por eso el bloque del drop va en su propio archivo y con la condición
escrita EN SU ENCABEZADO** (*"se corre después de que el Paso 2 esté
desplegado, porque hasta entonces `borrador_de_compra` todavía lee estas
tablas"*), y no en este documento: el que lo abra dentro de seis meses va a
leer el archivo.

**Y `db/esquema_completo.sql` tuvo las dos tablas viejas hasta que el drop
corrió.** El esquema del repo describe lo que una base nueva tiene que tener,
y hasta ese día una base nueva necesitaba las dos — el código todavía las
leía. Sacarlas antes es el corolario 60 al revés: el archivo adelantado rompe
la base que todavía no existe. (El drop corrió el 23/09 en las dos bases,
después del deploy del Paso 2, y el esquema las perdió en el mismo commit que
anotó la corrida.)

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

## SEGUNDA AL CLIENTE (23/09): las decisiones del dueño y dónde vive cada una

A un cliente que la acepta se le puede mandar mercadería de segunda **adentro
del mismo renglón**: misma ficha, mismo artículo, mismo precio, mismo remito.

| decisión | dónde vive |
|---|---|
| **Solo si el cliente la acepta** — un catering sí, Día no | `clientes.acepta_segunda`, default `false`; el campo de Armar Pedido sale solo con el tilde, y `marcar_renglon_armado` lo vuelve a mirar |
| **Nunca se elige sola** | el campo arranca cerrado y vacío; retildar sin decirla la limpia |
| **Cualquier segunda del artículo**, sin importar la caja | la guarda lee el pool con `_segunda_de_articulo`, la misma cuenta del Remanente |
| **Parte y parte**: 4 de segunda y 6 de primera | `pedidos_renglones.bultos_de_segunda`, una parte de lo armado |
| **Venta a precio lleno, costo cero** | el FIFO recibe SOLO la primera; la venta sale de los kilos del renglón entero |
| **Un rechazo vuelve a segunda con costo cero** | la segunda vuelve PRIMERO (`_segunda_que_vuelve`), no puede ir a `stock`, y su costo congelado se promedia a cero |

**LA REGLA ESCRITA UNA VEZ ES `_SQL_BULTOS_DE_PRIMERA`** (app/db.py): toda
consulta que resta del stock de primera la lee, y las únicas que leen el armado
ENTERO son las que miran lo que el CLIENTE recibió (el tope del rechazo y los
kilos de la devolución). Lo cuida un barrido que compara el conjunto ENCONTRADO
contra el DECIDIDO: la octava que aparezca con el armado entero falla hasta que
alguien decida de qué lado va.

**Y LA PARED DE LA BASE tiene CUATRO escritores que la conocen**:
`pedidos_renglones_segunda_solo_armado` exige armado, no anulado y no más que
lo armado. Marcar la escribe (con `cantidad_armada` EXPLÍCITA, para que
corregir lo pedido después no la deje arriba de lo armado), desmarcar y anular
la limpian, y la recarga la traslada con el armado. Un quinto que toque el
armado sin saberlo rebota contra la base — que es lo que la pared está para
hacer, y el motivo por el que los tests de esto corren contra Postgres.

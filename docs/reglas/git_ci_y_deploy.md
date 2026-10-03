# Git, CI y deploy

Movido TAL CUAL desde CLAUDE.md el 03/10 (sin reescribir). Las reglas
vigentes, en corto, están en CLAUDE.md.

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
   de que alguien se acuerde. (El 30/09 se le escaparon dos: miraba `not in variable` y
   no `not in respuesta.text` directo. El "105" de Logística cayó con v1050.)

   **Y LOS PR SE MERGEAN POR REBASE O FAST-FORWARD, NUNCA CON COMMIT DE
   MERGE (28/09, dueño).** El sello es la cantidad de commits de la
   historia, y un commit de merge suma uno que ningún sello contó. Pasó con
   el #53: la rama estaba sellada en 1023 y en verde, el merge dejó `main`
   en 1024, `test_VERSION_NUMERO_esta_al_dia_con_la_historia` cayó, y con
   el CI de `main` en rojo el deploy no salió hasta que el #54 re-selló.
   El verde de la rama no lo puede ver: el commit que rompe se crea al
   mergear. Así que el método es `rebase`; `squash` tampoco, porque junta
   varios commits en uno y el sello queda arriba. Y después del merge
   se mira la `conclusion` del CI de `main`, no solo la del PR.

   **Y UN CI VERDE EN `main` TAMPOCO ES UN DEPLOY (29/09).** v1037 (PR #64,
   9ac6605) quedó en `origin/main` con el CI de `main` en `success`, y Railway
   no desplegó: el historial de deploys no tenía ni uno salteado para ese
   commit. Lo más probable es que no le llegó el aviso de GitHub de que el CI
   había pasado, en un día en que la conexión con GitHub anduvo cortándose.
   Las tres verificaciones de GitHub (commit en `main`, PR mergeado, CI
   verde) daban bien. Lo único que lo mostró fue que el pie de la app seguía
   en v1036.

   Así que el número del pie es la cuarta pregunta, y no la contesta nada de
   GitHub: **¿desplegó?** Desde el celular no se puede forzar el deploy en
   Railway ("Deploy Latest Commit" necesita la computadora), y la salida es
   un commit chico REAL, sellado, mergeado por rebase, que vuelve a mandar el
   aviso. Nunca un commit vacío: suma un commit que el sello no contó.

   **CUANDO EL DUEÑO CIERRA ALGO, SE ABRE EL PR Y SE MERGEA SIN PREGUNTAR
   (01/10, dueño)**, siempre que no haya una migración de por medio. El orden
   es el de siempre: sello, suite y humo, push, PR, CI verde, merge por rebase,
   y después la `conclusion` del CI de `main`. Si el PR trae una migración (un
   `.sql` que cambia el esquema o los datos y lo corre Lionel), no se mergea
   hasta que esté verificada: desde el 02/10 la verifica Claude por el
   conector "Supabase Lectura" después de que Lionel la corra, y la anota en
   `db/corridas_confirmadas.md` (ver "Las bases se LEEN por el conector").

   **NADA DE HERRAMIENTAS QUE LE PIDAN PERMISO AL DUEÑO (01/10, dueño).**
   Ni búsqueda de documentación, ni `send_later`, ni ninguna otra que lo
   interrumpa para aprobar, salvo que sea imprescindible. Si falta un dato,
   se dice en el mensaje final y lo resuelve él. Un dato que él ya dio (por
   ejemplo, el plan de Supabase) se toma tal cual y no se sale a verificarlo.

   **EL CI SE ESPERA EN EL MISMO TURNO, sin recordatorios (30/09, dueño).**
   Nada de `send_later` ni de ningún recordatorio o tarea programada: cada
   uno le pide permiso al dueño. Si el CI tarda demasiado, el mensaje cierra
   diciendo **"CI pendiente"**, y lo revisa él cuando vuelve.

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

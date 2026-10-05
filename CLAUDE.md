# Calculador de Precios

Reglas generales del proyecto, vigentes para todo el código que se agregue de acá en adelante.

Este archivo tiene SOLO las reglas vigentes, en corto. El detalle, los casos y
el porqué de cada regla están en `docs/` (índice al final), movidos tal cual
desde la versión larga de este archivo el 03/10.

## Cómo se lee esto (dueño, 03/10)

- **No se lee entero ni CLAUDE.md ni ningún archivo de `docs/` ni
  `db/corridas_confirmadas.md`.** Se busca con `grep` la sección que haga
  falta y se lee solo esa (`grep -n "^## " archivo`, y después `sed -n`).
- **Antes de tocar un módulo se lee su archivo de `docs/modulos/`**, y antes
  de una migración `docs/reglas/sql_y_conector.md`.
- **El CI se espera sin escribir un mensaje por cada chequeo**: se avisa una
  sola vez, cuando termina.
- **Cuando un commit hace falsa una oración de este archivo o de `docs/`, la
  corrección va EN EL MISMO COMMIT.** Se encuentra grepeando el nombre de la
  cosa que se tocó.

## Con el dueño

- **Un prompt por vez.** Lionel no lee nada técnico: las decisiones se le
  preguntan en criollo.
- **Lo que el dueño sabe del GALPÓN se le pregunta; lo que afirma del SISTEMA
  se verifica en el código** (corolario 84). Y las preguntas son abiertas
  ("¿qué pasa con la caja cuando…?"), nunca "esto pasa, ¿no?" (corolario 71).
- **Un caso que el dueño define es real aunque hoy dé cero.** El dato de uso
  decide qué MEJORAR, nunca qué SACAR.
- **No construir un caso derivado de la forma de una regla sin preguntar si
  ocurre** (corolario 81). Escribir "esto no me lo pidieron" no es preguntarlo.
- **Antes de preguntarle algo, grepear acá y en `docs/` si ya lo contestó.**
- **Nada de herramientas que le pidan permiso al dueño** (`send_later`,
  recordatorios, búsquedas de documentación) salvo que sea imprescindible. Si
  falta un dato, se dice en el mensaje final.

## Reglas fijas del dueño (no se reabren)

- **Un vale no se anula**: se CORRIGE desde Gerencia, con historial
  (`vales_correcciones`). Un vale que salió (cobrado o cruzado) no se corrige.
- **Un remito no se anula**: solo se corrige el NÚMERO, desde Gerencia, con
  historial (`remitos_numeros`).
- **Una devolución al proveedor vale el precio de compra de SU compra**
  (`compras.importe`), por los dos caminos y en todas las pantallas. Nunca el
  costo del armado. Compra sin precio → sin precio. También el rechazo en
  caja de Día con compra atada (opción B, 02/10): cada caja vale un cajón de
  su compra, sin tocar Vacíos.
- **Toda exportación (PDF, Excel) sale con los mismos filtros que la pantalla**
  y su encabezado dice qué se filtró.
- **Palmala no cuenta para conclusiones.** Sirve solo para probar que una
  migración corre. Lo reabre el dueño, no un testigo con fecha reciente.
- **Los lotes de Palta de la compra 724 NO se tocan.**
- **El corte del modelo de Frutamax es el 05/09** (la
  fecha se lee de `corte_modelo`, nunca de la migración). Si un desvío es
  un error del circuito, se corrige. Si es arrastre del corte, se ajusta solo
  el COSTO, nunca el stock.
- **Una salida de una ficha con envase solo sale de esa ficha**: sin stock de
  la ficha queda sin asignar y en negativo hasta la guía R. **Y un armado en
  cajón nunca toma una caja armada.** La condición es una sola:
  `fichas_logistica.envase_id IS NOT NULL` y el renglón no salió **en su
  envase** (`pedidos_renglones.en_su_envase`: Mango y Cherry, elegido por
  renglón al armar, 05/10).
- **Una guía R cubre armados de hasta 3 días antes**
  (`DIAS_DE_MARGEN_DE_LA_GUIA_R`); la alerta cuenta solo lo que pasó el margen.
- **Todo lo que se tira o pasa a segunda es plata perdida.** Caja armada:
  kilos más la caja. Suelto: solo los kilos. Merma y pase se costean igual.
- **La caja de Día no vuelve nunca al stock.** El stock de cajas solo sube por
  compra, por la guía R `en_origen` y por la cuenta con un colega.
- **Una compra declara kilos SIEMPRE y, si el artículo tiene `unidad_conteo`,
  también el conteo.** Nunca hay factor de conversión entre los dos.
  `unidad_compra` está deprecada: no la elige nadie, solo registra lo viejo.
- **Los negativos se ven, con su número y en rojo**, en todos los listados.
- **La seña vacía y la seña en cero son lo mismo.** Vacíos del depósito
  arranca del conteo físico del 28/09; el último arranque manda.
- **Hay dos circuitos de vacíos (puesto y depósito) y no comparten tabla.**
- **Las decisiones cerradas no se reabren con un número**: precarga de
  Recepción (23/09), `kilos_4` retirada (22/09), sin aviso de kilos y unidades
  al revés (28/09), sin alerta de renglones sin tildar (19/09), merma de la
  guía R sin consecuencia (20/09).

## Pantallas (detalle en `docs/reglas/pantallas.md`)

- **Todo el código, la UI, los comentarios y los commits van en español
  (Argentina).**
- **Mobile-first**: botones de 44px mínimo, nada de scroll horizontal, grupos
  de botones con `flex-wrap`, aprovechar lo vertical.
- **El rótulo hace la PREGUNTA del negocio, la ayuda da un EJEMPLO.** Si para
  entender el rótulo hay que saber cómo se guarda el dato, está mal. El test
  pregunta también por la jerga que NO puede aparecer.
- **Si leerlo cambia lo que el operario hace en ese momento, se ve; si explica
  cómo funciona, va a la "i"** (`templates/_info.html`).
- **El atributo es la INTENCIÓN, el CSS decide el efecto** (corolario 32):
  `hidden` o `disabled` se verifican con `getComputedStyle`, no leyendo HTML.
- **Antes de esconder un contenedor, contar qué hay adentro que se toca.**
- **Una pantalla con dos sectores y clave saca el sector del PREFIJO**, no de
  `?origen=` (corolario 63), y las cuatro mitades del camino (barra, atrás,
  `action`, descargas) se revisan.
- **Un link de una alerta es por sector** (`destinos_por_sector`): la url de
  un sector puede ser una pared en otro (corolario 56).
- **Los hubs se leen como Depósito**: un dibujo en cada botón y un color por
  recuadro, en orden (`templates/_botones_hub.html`). Depósito no se toca.
- **Toda medición de layout usa `scripts/medir_layout.py`** e imprime la
  identidad (status y un conteo propio de la pantalla) y el denominador.

## SQL y migraciones (detalle en `docs/reglas/sql_y_conector.md`)

- **El editor de Supabase no es psql**: `begin/commit` no es atómico y las
  tablas temporales no sobreviven. Lo que es todo-o-nada va en UN `do $$`.
- **El `do` y su verificación se corren POR SEPARADO**, y la verificación
  devuelve CONTEOS (una fila siempre), con `'<migración>' as QUE_MIGRACION`
  como primera columna y un testigo de la base.
- **Ningún bloque pasa los 2500 caracteres; el código arriba y la explicación
  al pie.** Ante un error raro de sintaxis, primero se mira qué quedó escrito.
- **`if not exists` sirve para ESTRUCTURA, nunca para CONTENIDO** (listas,
  umbrales, textos): ahí va `drop ... if exists` y recrear.
- **Los nombres se verifican contra `db/esquema_completo.sql`**, y la base de
  prueba se carga con ese archivo, nunca con un `create table` propio.
- **Una migración que cambia un comportamiento** (`on delete`, CHECK, default,
  índice) **o crea una tabla toca `db/esquema_completo.sql` en el mismo
  commit.**
- **Un CHECK `A is null or B = 'x'` con B nuleable no rechaza nada**: va
  `is not distinct from`. Un CHECK de coherencia entre dos columnas exige
  grepear que el código escriba LAS DOS.
- **EXPAND se corre al escribirlo; el DROP espera al deploy** (corolario 94).
- **Decide la base; el código traduce el error.** Una regla de negocio no se
  escribe dos veces.
- **Las bases se LEEN solo por el conector "Supabase Lectura"** (Frutamax
  `opivgeqpjgtlduxcozqz`, Palmala `uygzmbqwharuhtnzqwpp`, Ganadería
  `rhmrjguqtjsaoykhogln`). El backup de Ganadería entra con el usuario
  `backup_lectura`, que solo lee `public` y `memoria` (detalle en
  `docs/modulos/backup.md`). El conector
  "Supabase" (el que escribe) no se usa nunca, ni para leer. "Verificado
  contra Frutamax" quiere decir por ese conector, con la base y la fecha.
- **Toda migración y toda verificación se mandan con el SQL completo pegado
  en el chat, en texto plano, listo para copiar.** Nunca como nombre de
  archivo ("está en db/xxx.sql"): Lionel no tiene el repo.
- **Migraciones**: Claude le manda el bloque a Lionel, Lionel lo corre en las
  dos bases, Claude verifica por el conector, anota la fila de CADA base en
  `db/corridas_confirmadas.md` en el mismo turno, y mergea. Claude no corre
  migraciones.
- **`LECTURA_FRUTAMAX_URL` es solo para sesiones locales** (usuario
  `lectura_claudia`, sin `bypassrls`: en las tablas con RLS lee cero filas).
  La clave no pasa nunca por el chat.

## Git, CI y deploy (detalle en `docs/reglas/git_ci_y_deploy.md`)

- **El orden es: commit → `scripts/sellar_version.py` → amend → suite y humo
  → push → PR → CI verde → merge por REBASE → `conclusion` del CI de `main`.**
  El sellado necesita el clon entero (`git fetch --unshallow`).
- **Nunca merge commit ni squash**: el sello cuenta los commits.
- **`git branch --show-current` antes de commitear, y `git rev-list
  --left-right --count origin/<rama>...<rama>` = `0 0` después del push**,
  sobre la rama en la que se está parado.
- **En cada commit reportado se dice si el CI está VERDE. Si está rojo va en la
  primera línea y no se construye encima.** Se reporta la `conclusion`.
- **Un CI verde en `main` tampoco es un deploy**: lo dice el número del pie.
  Para reenviar el aviso, un commit chico real, nunca uno vacío.
- **Cuando el dueño cierra algo sin migración, se abre el PR y se mergea sin
  preguntar.** Con migración, recién después de verificarla.
- **Antes de reportar, se abre una pantalla tocada** con
  `python3 scripts/mirar_pantalla.py <ruta>`.
- **La suite se corre sin pipe, a un archivo, y se mira `$?`**:
  `python3 -m pytest tests/ -q > /tmp/suite.txt 2>&1; echo $?`.
  El humo: `python3 scripts/humo.py`, con `ABIERTAS == miradas`.
- **Un assert numérico por la negativa sobre una página va con `sin_pie(...)`.**
- **Ninguna verificación descarta `stderr` ni ignora `$?`.**

## Tests y canarios (detalle en `docs/corolarios/tests_y_canarios.md`)

- **Todo test nuevo lleva su canario**: romper el código a propósito y exigir
  que caiga. Un canario en cero se investiga (las ocho lecturas están en el
  archivo); uno que hace caer de más dice que el árbol ya estaba rojo.
- **Canarios en PRIMER plano**, con UNA foto de los archivos guardada en
  DISCO antes de la tanda. Después de cualquier interrupción, se controla
  mutación por mutación qué quedó escrito. Se borra el `__pycache__`. La
  salida va a un archivo, nunca por un pipe. Se imprime la cola de pytest.
- **El andamio no puede decidir lo que el test afirma** (corolario 91): un
  parche sobre la función que se prueba, un mock que no mira el SQL, un
  `return_value` que contesta dos preguntas, un assert por la negativa.
- **Cuando lo que cambia es qué columna pide una consulta, el test mira el
  TEXTO del SQL, calificado por alias.** Y la validez contra el esquema solo
  la da Postgres: los tests de esto corren contra la base real.
- **Un assert sobre HTML o código se ancla en algo que solo puede ser eso**
  (una etiqueta, un atributo entero, una llamada en el árbol de `ast`), nunca
  en una palabra que un comentario puede nombrar. Lo que se repite se CUENTA.
- **Los fixtures se escriben como producción, con el RIVAL plantado** (el
  candidato que no tiene que ganar) y con fechas que no pueden ser hoy.
- **Un test que enumera compara el conjunto ENCONTRADO contra el DECIDIDO**,
  en las dos direcciones.
- **Un umbral mágico en un assert mide el entorno, no la función** (corolario
  92).

## Mediciones (detalle en `docs/corolarios/mediciones.md`)

- **Toda medición trae al lado su denominador, su testigo de actividad y el
  parámetro con el que se midió** (corte, ventana, base). Un número solo no
  se puede leer.
- **Un cero se cree recién cuando se planta el caso y el número se mueve**;
  un detector tiene que poder dar las dos respuestas.
- **Más hallazgos que población condena la heurística.**
- **Una consulta de diagnóstico REUSA la cuenta del sistema y colisiona contra
  ella ANTES de leer su número** (corolario 85).
- **El recorte de la medición tiene que ser el de la decisión** (corolario 69).
- **El umbral va sobre la magnitud por unidad; el total solo dimensiona.**
- **Una base parada contesta cero a lo que está y casi todo a lo que falta.**
- **Un número de un fixture nunca se presenta como dato de producción**, y en
  una captura los nombres son inventados y se nota.
- **Al retractar un número, se retracta también la decisión que iba a tomar.**

## Código (detalle en `docs/corolarios/reglas_y_copias.md` y `sql_y_esquema.md`)

- **Cuando se arregla una copia, se busca la otra**, también en `db/`,
  `scripts/` y en este archivo. Cuando una estructura gana un campo, se grepea
  quién la CONSTRUYE.
- **Antes de afirmar que algo no existe o no se usa, se grepea el CONCEPTO y
  el NOMBRE.**
- **Antes de bautizar algo, se grepea el nombre** (dos `def` iguales en Python
  no dan error).
- **Una columna o un parámetro sin escritor puede ser algo que falta o algo
  que sobra**: se pregunta si el hecho ocurre.
- **Un `except Exception` amplio esconde errores de arranque**: se angosta, y
  todo colaborador nuevo tiene un test que lo parchea.
- **Una lista por índice (`fila[8]`, `nth-child`) se lee por nombre** o se
  rompe en silencio cuando se mueve una columna.
- **Un dato derivado no puede dejar de llenarse; un campo sin consecuencia se
  llena vacío.** Antes de agregar un campo: ¿se puede derivar?

## Dónde está el detalle

Reglas:
- `docs/reglas/pantallas.md`: mobile-first, rótulos, exportaciones, la "i",
  esconder contenedores, el estilo de los hubs.
- `docs/reglas/sql_y_conector.md`: editor de Supabase, conector de lectura,
  `if not exists`.
- `docs/reglas/git_ci_y_deploy.md`: push silencioso, CI, sello, deploy,
  corolarios 90 y 92.

Corolarios, por familia (se buscan por número con `grep "Corolario N"`):
- `docs/corolarios/tests_y_canarios.md`
- `docs/corolarios/mediciones.md`
- `docs/corolarios/sql_y_esquema.md`
- `docs/corolarios/reglas_y_copias.md`: tiene adentro también los corolarios
  2 a 38 sin título propio.
- `docs/corolarios/pantallas_y_caminos.md`

Módulos (se lee el que se va a tocar):
- `docs/modulos/stock_y_guias_r.md`: envase de la ficha, en su envase o a caja (Mango, Cherry), margen de la guía R,
  guía anulada, negativos, filtro por tipo, `primera = 0`, mismo lote el
  mismo día, Cotejo y ajuste en una pantalla y Stock inicial solo en Gerencia.
- `docs/modulos/cajas.md`: el modelo de la caja, y Cajas con sus tipos y costo en Administración.
- `docs/modulos/vacios.md`: los dos circuitos de vacíos.
- `docs/modulos/devoluciones.md`: devoluciones y su valor, y el Resumen
  proveedores (marca del cajón, señas en el celular).
- `docs/modulos/vales.md`: vales a cobrar.
- `docs/modulos/fotos.md`: plazo de las fotos y espacio.
- `docs/modulos/remitos.md`: remitos y facturación.
- `docs/modulos/cobranzas_segunda.md`: cobranzas de segunda.
- `docs/modulos/backup.md`: plan B de backup.
- `docs/modulos/tareas.md`: tareas y la franja Tareas/Alertas de los hubs.
- `docs/modulos/compras.md`: títulos de magnitudes, Buscar compras, "A dónde
  fue" del detalle, seña, proveedores con varios puestos, pesaje, sello del
  importe, el hub de 7.
- `docs/modulos/magnitudes.md`: kilos y conteo.
- `docs/modulos/perdidas.md`: pérdidas, y su botón con dos pestañas.
- `docs/modulos/fichas_y_precios.md`: borrar una ficha y sus precios, y el "Precio anterior" del listado.
- `docs/modulos/pedidos.md`: renglón agregado por teléfono, segunda al cliente,
  la Casilla de pedidos en Administración.
- `docs/modulos/que_comprar_hoy.md`: decisiones de Qué comprar hoy (el diseño
  sigue en `docs/que_comprar_hoy.md`).
- `docs/modulos/fletes.md`: Fletes (Administración → Pedidos), el armado más
  barato, el reparto por pallets, corregir y la línea Flete de Rentabilidad
  Real.

Registros:
- `db/corridas_confirmadas.md`: migraciones de octubre en adelante.
- `db/corridas_historico.md`: migraciones del 18 al 30/09.

# Reglas de pantalla

Movido TAL CUAL desde CLAUDE.md el 03/10 (sin reescribir). Las reglas
vigentes, en corto, están en CLAUDE.md.

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

## Toda exportación sale con los filtros de la pantalla (01/10, dueño)

Vale para toda pantalla que baja un PDF o un Excel. **El archivo sale con
EXACTAMENTE los filtros que la pantalla tiene en ese momento** (fechas,
proveedor, artículo, cliente, estado, tipo, sector y cualquier otro), **y su
encabezado dice qué se filtró**. Un listado de un solo proveedor sin decirlo
se lee como el listado entero.

- **El link de exportar lleva TODOS los campos del formulario** de la
  pantalla, con el valor con que se dibujó (no el que se tipeó sin apretar
  Buscar: el archivo tiene que ser lo que se ve).
- **La ruta de exportar aplica los mismos filtros** que la de la pantalla, y
  el nombre del filtro se lee del catálogo (`_textos_de_filtros`), no de la
  primera fila: sin filas, el encabezado igual dice qué se filtró.
- **Un link que lleva de una pantalla a otra también lleva los filtros que
  las dos comparten** (Movimientos del depósito → Resumen proveedores).

El 01/10 se revisaron las 32 rutas que exportan. Tres tenían el error:

- **Consultar precios**: filtrado por artículo, el PDF y el Excel bajaban
  la lista entera (el link no llevaba `ficha_id` y la ruta no lo aplicaba).
- **Movimientos del depósito → Resumen proveedores**: el link pasaba solo las
  fechas, así que la planilla, y con ella su PDF y su Excel, salían con todos
  los proveedores. Es el camino más probable del caso de Lionel.
- **Buscar compras**: filtraba bien, pero el encabezado no decía el proveedor
  ni el artículo. Movimientos del depósito y Vales sacaban el nombre de la
  primera fila ("proveedor elegido" si no había ninguna).

Lo cuida `tests/test_exportaciones_filtradas.py`:

- toda ruta que exporta está en `EXPORTACIONES`, con cómo sigue los filtros
  (el conjunto ENCONTRADO contra el DECIDIDO: una exportación nueva falla
  hasta que alguien lo decida);
- cada link de exportar escrito en una plantilla lleva todos los campos de su
  formulario;
- y, contra Postgres, cada pantalla se abre filtrada, se sigue el link QUE LA
  PANTALLA DIBUJA y se lee el archivo: el otro proveedor, cliente o artículo
  no puede aparecer, y el filtro tiene que estar en el encabezado.

## Lo que se ve y lo que va a la "i" (25/09, del dueño)

Vale para toda pantalla, igual que el mobile-first:

> **Si leerlo cambia lo que el operario hace EN ESE MOMENTO, se ve. Si
> explica CÓMO FUNCIONA, va a la "i".**

La "i" es `templates/_info.html`:
`{% call info("título") %}texto, puede llevar <strong>{% endcall %}`, pegada
al rótulo o al título que explica, en el mismo renglón. Es un botón de 44px.
El diálogo, su CSS y el listener están UNA vez en `_barra_navegacion.html`, y
el listener va en `document` para que ande también en lo que llega por
`innerHTML` (corolario 83). El texto queda en el DOM, escondido.

- **Quedan a la vista**: las paredes, los "Ojo", los "esto no se deshace",
  las consecuencias y los modales. También 14 avisos que tienen clase de
  ayuda pero cambian lo que se hace: el cierre de la ficha, el alias, "Ver qué
  pasa" y el corte al mover de fecha, la fecha anterior en tipos de envase,
  los dos del stock inicial, la fecha del pedido en el reingreso, "contá lo que hay en el
  piso" en los dos conteos, "contalas a la mañana" en Cajas, la guía R de
  "vino armada" y el "Revisá la guía R, no ajustes el stock" del Cotejo.
- **Recibir remito y Reingreso por rechazo, 02/10 (dueño)**: su texto
  explicativo pasó a la "i", que arranca cerrada. Eso incluye la ayuda de
  Recibir remito ("cambiá solo lo que el súper anotó distinto") y el "Si el
  camión volvió ayer" del Reingreso, que hasta ese día estaban a la vista.
  En el Reingreso queda a la vista el renglón de la fecha del pedido.
- **Los de UN renglón quedan como están.** La "i" pide un toque para leer lo
  que ya ocupa 20px.
- **Una ayuda que mezcla las dos cosas se parte**: lo que cambia la acción
  queda a la vista y el porqué va a la "i". Por ejemplo, en el Cotejo quedan a
  la vista el signo de la diferencia y qué revisar antes de ajustar la segunda.

**Hecho el 25/09 en todas las pantallas que tenían ayudas**: 56 llevan la
"i" (primero tres, y el mismo día las demás, con el visto bueno del dueño en el
celular). Las que no aparecen en esa lista no tenían nada que explicar: sus
ayudas eran de un renglón, datos o avisos. Una excepción que va a la vista a
propósito: en Plata de cajas, "ese envase ya se cobra", porque sin esa frase
el total se resta de otro lado y el envase se cuenta dos veces.

Lo cuida `tests/test_info.py` en tres direcciones. **Qué pantallas tienen la
"i"**: el conjunto ENCONTRADO contra el DECIDIDO. **Cada una la importa una
vez**, sin bloques adentro del texto y nunca dentro de un `<script>`. **Los
avisos de la lista siguen a la vista**: si uno termina adentro de un `call
info`, el test cae. El test del navegador mide el efecto y no el atributo, y
también mide que tocar una "i" colgada de un `<label>` no tilde el campo.

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
| Resumen proveedores | 8 rótulos, nada más | seguro |
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

## Los hubs se leen como Depósito (04/10, dueño)

Administración, Compras, Gerencia y Comercial llevan el estilo de Depósito:
**un dibujo al lado del rótulo** de cada botón y **un color por recuadro, en
orden** (azul, verde azulado, pizarra, y si hay un cuarto vuelve a empezar).
El dueño eligió "un color por recuadro" y no "un color por lo que hace".

- El estilo vive en `templates/_botones_hub.html` y los dibujos en
  `app/iconos_hubs.py` (Heroicons, el mismo juego que Depósito).
- **Depósito no se toca**: tiene su propia copia de los tres colores en
  `templates/deposito.html`. Que las dos copias digan lo mismo lo cuida
  `tests/test_administracion_reordenada.py`.
- Arriba de Compras, Administración y Gerencia va la franja Tareas/Alertas
  (`docs/modulos/tareas.md`), debajo de la cinta corrida de avisos. La cinta
  no va en Depósito, Logística ni Comercial (dueño, 05/10).
- **El título de la barra no se corta a mitad de palabra** (dueño, 05/10):
  si no entra en un renglón, parte entre palabras y achica hasta 0.75rem
  para que entre la más larga ("Administración" a 313px con candado). Solo
  una palabra que ni así entra —un nombre sin espacios— se corta
  (`templates/_barra_navegacion.html`, `tests/test_cinta_de_avisos.py`).
- **Lo que mira lo mismo desde varios lados va en UN botón con pestañas**
  (`templates/_pestanas.html` y un parcial por grupo, con los links escritos
  tal cual para el barrido de pantallas sin link). Administración: Stock del
  Depósito. Compras: Buscar compras, Qué comprar hoy, Analizar artículo.
  Gerencia (Mirar · Corregir · Mantenimiento, 11 botones desde el 05/10): Rentabilidad,
  Pérdidas y Facturación y cobranzas, cuyas pestañas salen solo entrando por
  Gerencia. Sistema desapareció (`docs/modulos/pedidos.md`).
- **Comercial** tiene cuatro botones (Alertas, Precios, Clientes, Fichas
  logísticas): Envases se fue a Cajas de Administración. **Precios** tiene
  cuatro (Cargar precios —primero desde el 07/10—, Consultar, Precios por
  Período y Márgenes por Artículo); los dos "Próximamente" salieron y sus
  direcciones siguen abriendo. Adentro de Cargar precios, en este orden:
  "Cargar precios manuales" y "Cargar precios por foto", con el mismo
  nombre en el título de cada pantalla.



## Volver a la lista con sus filtros (05/10, dueño)

"Si listé 10 remitos de septiembre, entré en uno, lo cargué y vuelvo, tengo
que ver esos mismos 10 sin volver a filtrar." Vale para toda pantalla lista →
detalle → volver.

- **La lista manda su dirección** —con su consulta, sin `aviso` ni `error`—
  en el parámetro `volver` de cada link al detalle:
  `href="/ruta/{{ id }}{{ q_volver(aqui(request)) }}"` (o `y_volver` si el
  link ya tiene `?`). El link sigue escrito tal cual, para el barrido de
  pantallas sin link.
- **El detalle vuelve** con `vuelta(request, defecto)`: la barra, el
  "Volver" y los links a sus pasos (emitir, recibir). Sin `volver` (un
  favorito, un link viejo), su lista de siempre. Solo direcciones internas
  (`direccion_de_vuelta`): `//otro.sitio` o `https://…` caen al defecto.
- **Después de guardar** también: los formularios del detalle mandan
  `{{ q_volver(volver) }}` en el `action`, y el middleware
  `mantener_la_vuelta_despues_de_guardar` pega el `volver` a la redirección;
  si la redirección va a la lista misma, va a la lista CON sus filtros.
- **Las pantallas que llevan los filtros en su propia dirección** (Detalle de
  la compra) los mantienen con `consulta(request)`.

Arreglado el 05/10 (tenían el problema): Armar remito → remito / emitir
(volvía a Facturación), Facturación y la búsqueda para Recibir → remito, Vales
a cobrar y Movimientos de vales → vale, Movimientos de vacíos → el proveedor
(volvía a Vacíos), Remanente → artículo y extracto (perdía el tipo),
Movimientos del depósito → Resumen proveedores, Pedido del día y Casilla →
Revisar pedido, Guías R → "Volver a la lista", la barra de la Ficha, la barra
y las fotos de la balanza del Detalle de la compra, Vino armada, y guardar en
Tareas. Tests: `tests/test_volver_con_filtros.py`.

# Procedimiento del corte del modelo

Escrito el **viernes 04/09/2026**. El corte es el **sábado 05/09**, a la
tarde, cuando el depósito termine la jornada y cuente el remanente físico.

**La vez pasada se improvisó sobre la marcha y fueron tres horas.** Esto es
para que no vuelva a pasar: qué se corre en cada paso, qué hay que ver antes
de pasar al siguiente, y qué hacer si algo no da.

El SQL está en `db/corte2_frutamax.sql`, partido en bloques. **Cada bloque se
pega solo** en el editor de Supabase. Ninguno pasa los 2500 caracteres y
ninguno usa tablas ni vistas temporales — las dos cosas que rompieron el
corte del 29/08.

**Es de Frutamax y solo de Frutamax.** Palmala todavía no lleva stock y va a
arrancar limpia cuando se implemente.

## ANTES DE TODO: confirmar que el piso de fecha está andando

**Se verifica con una consulta, no con una pantalla.** Corré
`db/verificar_piso_por_ficha.sql`: calcula la cuenta por ficha de las dos
formas —como estaba antes del 04/09 y como queda con el piso— y las pone al
lado, con la columna `cambio`.

- **Alguna fila con `cambio` distinto de cero** → el piso está aplicando.
- **Todas en cero** → o no está aplicando, o no hay nada anterior al corte que
  sacar. Avisá antes de seguir.

### Por qué NO se ve en ninguna pantalla, y es importante saberlo

Corregido el 05/09, después de que la verificación anterior mandara a mirar la
pantalla equivocada. **Ningún número visible del sistema sale de la cuenta por
ficha.** Los cuatro lugares que la usan:

| lector | qué hace con el número |
|---|---|
| `listar_articulos_para_reproceso` | decide si el artículo **aparece** en el selector. No muestra cifra. |
| `fichas_con_cajas_armadas` | devuelve **solo ids**: el aviso de armado dice "hay/no hay". |
| `_stock_de_ficha` | **congela** `stock_sistema` al crear un conteo. Los conteos viejos conservan el número viejo. |
| el Cotejo | muestra ese `stock_sistema` **congelado**. No se recalcula. |

O sea que el piso puede estar perfecto y **no mover nada de lo que se mira**:

- **El "sin procesar" de Stock del Sistema es la CUENTA 3**, no la 2
  (`fila["stock"] − Σ armados`, con `_desglose_stock_articulo`, el FIFO
  rejugado). El piso no lo toca y no tiene por qué tocarlo.
- **El Cotejo muestra fotos congeladas.** Solo un conteo NUEVO nace con el
  número corregido — y el conteo del corte lo va a ser.

**Dónde sí se va a ver, y es mañana:** los conteos que se carguen el día del
corte congelan `stock_sistema` ya con el piso puesto. El Cotejo del lunes es la
primera pantalla que lo refleja.

**Verificado en producción el 05/09**: los 22 artículos cambiaron. Palta −425 →
+35, Mandarina −384 → +1, Redondo −257 → +41, Berenjena −214 → +46. Los que
quedan negativos son los que no se reprocesan (E5, no déficit) y el déficit
real post-corte de los que sí.

### Qué queda en la cuenta por ficha el lunes

**Todo lo anterior al corte sale de las dos patas**, así que los déficits
acumulados —Perita −95, Zapallito −54— **desaparecen**. El lunes cada ficha
arranca en lo que se contó y nada más.

Y el día del corte es asimétrico a propósito: **los armados del sábado NO
restan** (el conteo de esa tarde ya los descontó) y **las guías R normales del
sábado NO suman** (sus cajas están en el conteo). Solo cuenta el `inicial` del
corte, y de ahí en adelante todo. Sin esa asimetría el lunes arrancaba con
números equivocados en las dos direcciones.

**Y lo único a mirar en pantalla antes del corte** era que el **selector de
Reproceso** no hubiera perdido ningún artículo — lo único que el piso puede
cambiar a la vista, y la falla del 31/08 que no queremos repetir.

> **LAS DOS VERIFICACIONES ESTÁN HECHAS (05/09).** La consulta dio los 22
> artículos cambiados y el selector de Reproceso quedó completo. **Esta
> sección no hay que repetirla mañana**: se arranca directo en "No empezar
> hasta que esto esté".

## NO EMPEZAR HASTA QUE ESTO ESTÉ

La razón de esta lista no es que el corte necesite estos datos: el
compensatorio lleva a cero lo que haya y el conteo físico manda. **La razón es
la de después.**

**Todo lo que pasó hasta el momento del conteo y se cargue DESPUÉS del
compensatorio, con fecha anterior o igual al corte, se cuenta dos veces.** El
conteo físico ya lo vio en el piso, y el movimiento lo vuelve a sumar (o a
restar) sobre el stock ya rebaseado. Eso no lo atrapa ninguna guarda: entra
callado y aparece dentro de una semana como un descuadre sin causa.

Antes de correr el BLOQUE 3, tiene que estar todo esto cargado:

1. **Las recepciones de compras del día.** Una compra que llega esa tarde y se
   recepciona el lunes con fecha del sábado **suma cajones que el conteo ya
   contó**.
2. **Los pedidos armados del día, TILDADOS.** Un renglón que se tilda el lunes
   **resta bultos que el conteo ya descontó** — la mercadería ya no está en el
   piso. Resta dos veces.
3. **Las guías R del día**, con su fecha. Producen cajas y consumen bultos que
   el conteo ya refleja.
4. **Las mermas, ajustes y reingresos por rechazo del día.**
5. **Las compras que carga Administración**, si alguna es del día y todavía no
   está.

Y dos reglas de tiempo:

6. **El conteo va DESPUÉS del último movimiento del día.** Si se cuenta a las
   16 y a las 17 sale un pedido, el conteo dejó de ser la foto y hay que
   volver a contar esa parte.
7. **Entre el conteo y el final del corte, el depósito no se mueve.** Ni una
   recepción, ni un armado, ni una merma.

Y la regla espejo, para el lunes: **nada se carga con fecha anterior o igual a
la del corte.** Si aparece algo de esos días, se anota y se decide a mano — no
se carga y ya.

**Entre el BLOQUE 3 y el BLOQUE 7 no se carga nada por pantalla.** El bloque 4
escribe `stock_sistema = 0` apoyado en que el bloque 3 lo dejó en cero; si
alguien carga algo en el medio, esa foto queda mintiendo.

## Por qué el orden es el orden

Tres cosas leen la fecha de corte en el momento de correr, y por eso el orden
no es indistinto:

- `crear_stock_inicial` y `crear_reproceso_inicial` fechan lo que cargan con
  `fecha_corte()`. Si se carga el conteo antes de mover la fecha, **todo el
  stock inicial nuevo queda fechado en el corte viejo**, mezclado con lo que
  se está cancelando.
- El piso de fecha del reproceso (desde el 04/09) **rechaza toda guía R
  anterior al corte vigente**. Apenas se mueve la fecha, las guías R que
  faltaban del arrastre ya no se pueden cargar.

De ahí sale el orden, y **todos los pasos que quedan son obligatorios**. Lo
único que se evaluó y se descartó —reconstruir las guías R viejas— está al
final, en el apéndice, fuera del camino.

---

## PASO 1 — La foto de antes (BLOQUE 0)

Solo lectura. Devuelve el stock vivo por artículo con las seis patas
separadas.

**Guardá el resultado** (copiar a una planilla, o una captura). Es contra esto
que se compara todo lo que sigue, y es lo único que queda del estado anterior
si algo sale mal.

**Antes de seguir:** que la lista tenga sentido. Si un artículo aparece con un
número absurdo, mirarlo ahora — después del bloque 3 ya no está.

---

## PASO 2 — Mover la fecha de corte (BLOQUE 1)

**Es el único lugar donde se escribe la fecha nueva.** Cambiar el
`date '2026-09-06'` por el día real del corte y nada más: todos los bloques
que siguen la leen de `corte_modelo`.

El bloque se niega si la fecha nueva no es posterior a la vigente, o si está
más de un día adelante. Por eso **se corre el día del corte**, no antes.

**Antes de seguir:** que la consulta final diga la fecha que se quiso poner.

A partir de acá el sistema no acepta guías R anteriores a esa fecha. Si
apareciera una que falta, se anota y se resuelve después: no se vuelve atrás
por eso.

---

## PASO 3 — SACADO. El bloque 2 no se corre.

Nuleaba la ficha de las guías R anteriores al corte. **Es el que produjo el
arrastre por ficha que encontramos el 04/09**: sacaba las entradas y dejaba
las salidas, porque no tocaba `pedidos_renglones.ficha_id`. Y el compensatorio
no lo alcanza — es por artículo, y la cuenta por ficha no lee movimientos.

Lo reemplaza el **piso de fecha en `_SQL_STOCK_PARTIDO`**: las dos patas desde
el corte inclusive. Con eso la cuenta por ficha arranca de cero en cada corte,
igual que el total del artículo, y las guías R viejas **conservan su ficha**.

El paso queda numerado y vacío a propósito, para que nadie lo confunda con el
paso 3 del corte anterior.

## PASO 4 — El compensatorio (BLOQUE 3)

Un movimiento `cierre_modelo_viejo` por artículo con stock distinto de cero,
por −1 × las seis patas leídas en el momento. **Ningún número escrito a mano**:
los artículos en negativo salen con compensatorio positivo solos.

Va fechado el día ANTERIOR al corte, para que en el FIFO quede antes del stock
inicial y no se mezcle con el lote costeado.

**Antes de seguir: volver a correr el BLOQUE 0.** La columna `stock` tiene que
dar **0 en todas las filas**. Si alguna no da, parar y mirar — no seguir.

---

## PASO 5 — El stock inicial: los bultos sueltos (BLOQUE 4)

Se reemplaza la lista por lo contado: `(articulo_id, nombre, bultos, costo)`.
El nombre va en el JOIN, así que **un id que apunte a otro artículo no entra**
y el conteo hace fallar el bloque entero sin escribir nada.

**Los bloques 4 y 6 vienen con `esperados` y los totales en 0 a propósito:
tal como están fallan.** Las filas de ejemplo son solo la forma, y los números
son los del corte del 31/08 — si quedaran prellenados, los totales del bloque
5 también coincidirían y el corte entraría con la foto vieja sin que nada
avise. Hay que escribir lo contado y los totales de la planilla.

`esperados` es la cantidad de filas **de ese bloque**. Si la lista no entra en
2500 caracteres, se parte en dos y se corren los dos, cada uno con su
`esperados`; el orden no importa.

**Antes de seguir:** que `articulos` y `bultos` sean los de la planilla.

---

## PASO 6 — Cerrar el stock inicial (BLOQUE 5)

Lee lo que quedó escrito y lo compara con los tres totales de la planilla
(artículos, bultos, plata). Si no dan, **falla y no toca nada**.

Si falla: correr el **BLOQUE D4**, que borra el stock inicial de este corte,
corregir la lista y repetir el paso 5.

> **Por qué el borrado va aparte, y es una lección de este mismo día:** un
> `raise` adentro de un `do` deshace *también* lo que ese mismo bloque hubiera
> borrado. La primera versión del bloque 5 borraba y avisaba "BORRADO" — y no
> borraba nada. Lo agarró la prueba contra Postgres, no la lectura.

**Antes de seguir:** las tres columnas iguales a la planilla.

---

## PASO 7 — Las cajas ya armadas (BLOQUE 6)

Una fila por ficha: `(ficha_id, cajas, costo por caja)`. El artículo y el
cliente **salen de la ficha**, no se escriben.

Entran como guías R de tipo `inicial`, que **producen sin consumir**
(`bultos_tomados = 0`): los cajones que las originaron no se van a cargar
nunca.

**MERCADERÍA SOLA, SIN CARTÓN.** El envase se suma río abajo, en la cotización
y en la Rentabilidad Real; meterlo acá lo contaría dos veces.

**Antes de seguir:** que la lista devuelta tenga las fichas, los clientes y
las cajas que se contaron.

---

## PASO 7B — La segunda que está en el piso (BLOQUE 6B)

**Nuevo el 05/09**: en el corte anterior no hubo segunda inicial, así que no
hay antecedente.

Entra como guía R `inicial` con `bultos_primera = 0` y la segunda en
`bultos_segunda`. Es **la única puerta al pool de segunda** que no es un
rechazo de cliente: `movimientos_stock.bultos_segunda` solo se acepta con
`destino_rechazo`, que exige `tipo = 'reingreso_rechazo'`, y `remitos_segunda`
es la salida del pool, no la entrada.

**Sin ficha y sin cliente**, a propósito: es descarte para el puesto, no
mercadería de nadie.

**Y sin costo: `costo_total = 0`, no NULL.** En el modelo la segunda vale
cero — *"TODO el costo va a la primera: segunda y merma valen cero"*, y la
Rentabilidad Real la informa en bultos, sin plata. Un NULL prendería la alerta
"guías R con costo incompleto" (`WHERE costo_total IS NULL`, sin filtro de
tipo) con casos que **no se pueden completar nunca**: no hay consumos de los
que sacar un precio. `costo_por_bulto_primera` sí queda NULL, porque no hubo
primera.

**Antes de seguir:** que las cajas de segunda sean las contadas. Y ojo con el
verificador del paso 8: la segunda **no toca el stock del artículo** (el stock
usa `bultos_primera` y `bultos_tomados`), así que `dif` tiene que seguir dando
0. Si diera distinto, la segunda entró por el campo equivocado.

### Dos cosas que este camino NO guarda

- **El kilaje.** `reprocesos` guarda bultos, no kilos, y `remitos_segunda`
  también es en bultos. Los 6 kg del zapallito y los 16 del limón no viajan a
  ningún lado: son para saber de qué mercadería se habla, no un dato que el
  sistema conserve.
- **`crear_reproceso_inicial` no lo soportaría.** La función de la app exige
  `bultos_primera > 0`, un costo y una ficha; las tres fallan acá. **El SQL
  puede escribir algo que la app rechazaría**, y eso vale saberlo: si alguna
  vez la segunda inicial tiene que poder cargarse por pantalla, hay que
  ampliar esa función, no solo la consulta.
- **La ficha en NULL post-corte significa "sin asignar, hay que
  completarlo"**, y la pantalla de Guías R las muestra para eso. Las dos guías
  de segunda van a aparecer ahí como pendientes sin que haya nada que asignar.
  Hoy es solo cosmético (no hay alerta que las cuente), pero **cuando se haga
  E6 hay que excluir las guías sin primera** o van a inflar esa alerta para
  siempre.

## PASO 8 — Verificador final (BLOQUE 7)

Solo lectura. Por artículo: sueltos, cajas armadas, stock, y la diferencia.

**La columna `dif` tiene que dar 0 en TODAS las filas.** Cualquier otra cosa
se mira antes de abrir el depósito.

---

## Si hay que abortar

**El mismo día, sin haber operado todavía:** BLOQUE **D0** (deshace el corte
entero) y después BLOQUE **D1** (devuelve la fecha vieja). En ese orden: el D0
borra buscando por la fecha vigente.

El D0 se corta solo si ya hay operación posterior al corte —una guía R, una
recepción, un armado—. Eso ya no se deshace con un script: se decide a mano.

**Solo el stock inicial mal cargado:** BLOQUE **D4**, y repetir el paso 5.

---

## Lo que este corte NO arregla, y conviene saber de antemano

- **E5 sigue en pie.** El contador del ARTÍCULO no descuenta en el formato de
  la ficha, así que mezcla cajones y cajas. Es una de las razones por las que
  hoy los números son inentendibles. El corte los deja limpios el domingo y
  esto los vuelve a ensuciar solo, despacio. **Es lo primero después del
  lunes.**
- **Los comentarios del esquema dicen "31/08/2026"** en `reprocesos.tipo`,
  `reprocesos.ficha_id` y `conteos_stock.ficha_id`. Después del corte quedan
  viejos. No rompen nada —son comentarios— pero son exactamente la clase de
  texto que envejece y después se lee como si fuera cierto. Actualizarlos la
  semana que viene.
- **Los `conteos_stock.stock_sistema` viejos** conservan la foto inflada. El
  corte los deja atrás solo, porque el conteo es nuevo: no hay que hacer nada.

---

## Apéndice — Lo que decidimos NO hacer, y por qué

*Esto no es un paso. Está acá para que la decisión quede escrita, no para que
alguien la reconsidere a las siete de la tarde.*

### Reconstruir las guías R viejas que faltan

Se evaluó y **se descartó el 05/09, antes del corte.** Tres razones, en orden
de peso:

1. **No cambia ningún número.** El compensatorio lleva a cero lo que el sistema
   diga y encima se carga el conteo físico. Una guía R reconstruida antes del
   corte se compensa igual.
2. **Tampoco mejora la cuenta por ficha.** Con el piso de fecha, todo lo
   anterior al corte sale de las dos patas: el lunes cada ficha arranca en lo
   contado, con o sin reconstrucción. El déficit no sobrevive al corte.
3. **El depósito viene de una jornada completa.** A esa hora están cansados,
   probablemente no se acuerden de qué guía era cuál, y el corte tiene que
   salir rápido.

Lo único que compraba era trazabilidad histórica de guías que además nadie
recuerda con precisión. **No vale el rato.**

Si alguna vez se retoma, la lista sale de `db/guias_r_que_faltan.sql`, acotada
al período post-corte y a los artículos que de verdad se reprocesan. Distingue
*FALTA CARGAR* (reconstruir) de *FECHA MAL* (la guía existe, se corrige su
fecha — cargar otra sería inventar mercadería). Y solo se puede hacer **antes**
de mover la fecha: después, el piso rechaza las fechas anteriores al corte.

**Nunca inventar una guía para que cierre.** El descuadre se ve; la guía
inventada se lee como un dato.

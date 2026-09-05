# Procedimiento del corte del modelo

Escrito el 04/09/2026, antes del corte del fin de semana. **La vez pasada se
improvisó sobre la marcha y fueron tres horas.** Esto es para que no vuelva a
pasar: qué se corre en cada paso, qué hay que ver antes de pasar al siguiente,
y qué hacer si algo no da.

El SQL está en `db/corte2_frutamax.sql`, partido en bloques. **Cada bloque se
pega solo** en el editor de Supabase. Ninguno pasa los 2500 caracteres y
ninguno usa tablas ni vistas temporales — las dos cosas que rompieron el
corte del 29/08.

**Es de Frutamax y solo de Frutamax.** Palmala todavía no lleva stock y va a
arrancar limpia cuando se implemente.

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

De ahí sale el paso 0, que es el que se olvida.

---

## PASO 0 — Cargar lo que falta, CON FECHA VIEJA. Antes de tocar nada.

**Esto va primero y no tiene vuelta atrás.** Todas las guías R pendientes —las
del arrastre, las que se armaron y no se cargaron— se cargan ahora, por la
pantalla de siempre (Depósito → Stock → Reproceso), **con su fecha real**.

El campo de fecha está en la pantalla y acepta fechas hacia atrás. Desde el
04/09 avisa cuántas guías R posteriores quedarían con el reparto
desactualizado y pide un segundo toque; el aviso dice, y es cierto, que **el
costo no cambia**.

### La lista de qué cargar

Sale de `db/guias_r_que_faltan.sql`, tres consultas de solo lectura. **Las dos
primeras están acotadas**, y los dos recortes importan: desde la fecha de corte
vigente inclusive (lo anterior lo trató el compensatorio del corte pasado y no
se corrige), y solo artículos con al menos una guía R en el período (los que
nunca se reprocesan no tienen nada que reconstruir; su déficit por ficha es
otra cosa, E5).

**Correr primero la consulta que cuenta.** Es el número que decide: si da tres
o cuatro, el depósito las reconstruye a la mañana. Si sigue dando cientos, el
paso 0 no es viable y **se salta entero** — el conteo físico manda y el
compensatorio absorbe.

Las tres:

- **La primera** da, por artículo y ficha: el primer día en rojo, cuántas
  cajas faltan, y **qué hacer**. Distingue dos casos que se arreglan
  distinto:
  - *FALTA CARGAR*: salieron más cajas de las que se produjeron. Hay que
    reconstruir la guía R.
  - *FECHA MAL*: la guía R existe pero está fechada después de la salida que
    explica. **No se carga otra**: se anula y se vuelve a cargar con la fecha
    correcta, o queda anotada. Cargar una segunda sería inventar mercadería.
- **La segunda** es el día a día de un artículo, con todo lo que entró y
  salió y el saldo corriendo. Sirve para ver el hueco a ojo, e incluye las
  guías R sin ficha, que la primera no ve.

**Estas consultas no dan el `sin_lote` del FIFO** (los 88 de Pepino, los 109
de Zapallito). Ese número vive en `repartir_fifo` y reescribirlo en SQL sería
tener la regla escrita dos veces. Lo que dan es la cuenta por ficha, que es la
que contesta *qué guía reconstruir*. Los dos números no tienen por qué
coincidir: son cuentas distintas.

### Si no se puede reconstruir todo, el corte va igual

**Esto no bloquea el corte.** Si el depósito no puede reconstruir alguna guía
—porque no se acuerda, o porque los números no cierran— se deja así y se
sigue. **El conteo físico manda**: lo que no se pueda reconstruir queda
absorbido por el compensatorio del PASO 4, que es exactamente para eso.

**Pero hay que intentarlo**, y por una razón concreta: cada guía que se cargue
bien es trazabilidad que se conserva. El compensatorio borra el descuadre; no
guarda de dónde salió cada caja. Lo que se reconstruya hoy se sabe para
siempre; lo que no, se pierde en un solo número.

Lo que **no** hay que hacer es inventar una guía para que cierre. Una guía R
con números fabricados es peor que el descuadre: el descuadre se ve, la guía
inventada se lee como un dato.

**Antes de seguir:** Depósito → Stock, y que no quede ningún artículo con
`sin procesar` negativo por guías R que falten **y se puedan cargar**. Las que
se decidió no reconstruir se anotan y se siguen.

Después del paso 1 esto ya no se puede hacer. **No hay apuro para empezar el
paso 1 y sí lo hay para terminar el paso 0.**

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

## PASO 3 — Las fichas de las guías R viejas (BLOQUE 2)

La cuenta por ficha no tiene corte de fecha: si a una guía R anterior al corte
le queda la ficha, sigue inflando **esa ficha** para siempre, aunque el
compensatorio lleve el total del artículo a cero. Este bloque las deja en
NULL. No las anula: ocurrieron.

Se puede correr dos veces sin hacer daño.

**Antes de seguir:** `con_ficha_todavia` tiene que dar **0**.

---

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

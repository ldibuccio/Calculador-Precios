# Qué migraciones corrieron, en qué base, y con qué fila

**Para qué existe**: el 18/09 una auditoría no pudo contestar si las tres
migraciones de Vacíos habían corrido en Frutamax. Habían corrido. Lo que
faltaba era el registro: la única fila anotada era la de Palmala, y estaba
**citada adentro de un corolario** de CLAUDE.md para ilustrar otra cosa (cómo
el testigo dice si una base vota), no anotada como confirmación.

Una fila citada para ilustrar no es un registro. El que audita no la encuentra
buscando confirmaciones, y el que la escribió tampoco se acuerda de que está
ahí — así que la pregunta *"¿esto corrió en las dos?"* se vuelve irrespondible
y hay que ir a molestar al dueño.

**Por qué acá y no al pie de cada `.sql`**: esos archivos se pegan en el editor
de Supabase y **ningún bloque pasa los 2500 caracteres**. Varios están a
menos de 50 del límite, así que un registro de cuatro líneas adentro los
volvería intruncables — se arreglaría el registro rompiendo la migración.

**Cómo se usa**: al confirmar una migración, la fila de CADA base se pega acá
con el nombre de la base adelante. Las dos, siempre: salen idénticas por
diseño salvo la población y el testigo, así que pegar una sola es exactamente
el error que esto viene a evitar.

---

## 18/09

| migración | FRUTAMAX | PALMALA |
|---|---|---|
| `renglon_agregado_a_mano` | `1 · 1 · 0 · 1921 renglones · 19/09` | `1 · 1 · 0 · 1103 renglones · 19/09` |
| `renglon_cantidad_corregida` | `1 · 1 · 0 · 1921 renglones · 19/09` | `1 · 1 · 0 · 1103 renglones · 19/09` |
| `vacios_deposito_1/2/3` (verifica `vacios_deposito_4`) | `1·1·1·1·1·1·1·1 · 38 proveedores · última recepción 18/09` | `1·1·1·1·1·1·1·1 · 44 proveedores · última recepción 17/09` |

**La población es lo que identifica la base**: 1921 contra 1103 renglones, 38
contra 44 proveedores. Las columnas que importan dan lo mismo en las dos por
diseño — ése es el resultado bueno, no una razón para pegar una sola fila.

**Y desde el 18/09 la primera columna dice QUÉ MIGRACIÓN es**
(`'<nombre>' as QUE_MIGRACION`, en las 24 verificaciones del repo). Sin eso,
dos filas de la misma base y de dos migraciones distintas se leen como las dos
bases de una — que es lo que causó el corte de esa mañana.

---

## 19/09

| migración | FRUTAMAX | PALMALA |
|---|---|---|
| `eliminadas_1_tabla` (verifica `eliminadas_1_verificacion`) | `1 · 5 · 4 · 0 · 625 compras` | `1 · 5 · 4 · 0 · 514 compras` |
| `importe_1_cuando_y_por_donde` | `2 · 3 · 625 sin origen · 0 · 625` | `2 · 3 · 506 sin origen · 0 · 514` |

**La tercera columna de `eliminadas_1` es `valores_del_CHECK_de_4`, y los 4 son
lo que decidía el merge**: con la lista vieja —dos superficies en vez de
cuatro— el código de `e8075af` ROMPE el borrado por las dos puertas que más se
usan, porque el archivo se escribe en la MISMA sentencia que el DELETE y un
origen fuera del CHECK revienta las dos. La fila es la que autorizó ese push.

**Y `625 sin origen` / `506 sin origen` NO es una deuda: es el número
esperado.** Las compras viejas quedan sin rastro a propósito — deducir de
dónde salió un importe ya escrito sería inventarlo. Ese número no baja; lo
único que cambia es que las nuevas nacen con origen.

## 20/09

| migración | FRUTAMAX | PALMALA |
|---|---|---|
| `segunda_por_cajon_1` | `columnas 2 · NO_VUELVEN 0 · con_segunda 11 · 625 compras` | `columnas 2 · NO_VUELVEN 0 · con_segunda 0 · 514 compras` |
| `segunda_por_cajon_2` (backfill de la ventana) | `HUECOS 0 · NO_VUELVEN 0 · con_segunda_real 11 · 557 recepcionadas` | `HUECOS 0 · NO_VUELVEN 0 · con_segunda_real 0 · 262 recepcionadas` |
| `pase_a_segunda_1` + `_2` (verifica `pase_a_segunda_verificacion`) | `5 · 1 · 0 ofensores · 0 pases · 124 movimientos · último 19/09` | `5 · 1 · 0 ofensores · 0 pases · 1 movimiento · último 25/08` |

**`NO_VUELVEN` en 0 es lo que dice que el backfill fue exacto**: devolvió lo
mismo que había, no un número parecido. Y las 11 de Frutamax son las compras
con las dos magnitudes declaradas — el `con_segunda 0` de Palmala es correcto
y no un backfill que no corrió.

**El testigo de `pase_a_segunda` dice que Palmala NO VOTA, y se ve en la misma
fila**: `1 movimiento · último 25/08`. Esa fila confirma lo único que Palmala
puede confirmar —que la migración no explota contra ese esquema— y nada sobre
si los pases funcionan. Eso lo decide Frutamax, con sus 124.

**Los `0 pases` de las dos son el estado del día que se corrió**, no un
resultado: la pantalla del pase se cableó después (`b3f5837`). Un cero de
población recién migrada no es el cero de una función que nadie usa.

## 21/09 — `listados_compra` (los cuatro bloques de "Qué comprar hoy")

`db/listados_compra_1_cabecera.sql`, `_2_clientes.sql`, `_3_kilaje.sql` y
`_4_manual.sql`, con su verificación corrida aparte.

```
PALMALA   4 tablas · 5 guardas · 1 índice · 0 listados · 5 clientes · último pedido 19/09
FRUTAMAX  4 tablas · 5 guardas · 1 índice · 0 listados · 3 clientes · último pedido 19/09
```

**Las dos filas son idénticas en todo lo que la migración afirma, y eso es
exactamente lo esperado**: las cuatro columnas de la izquierda dicen que las
tablas y las guardas están, y eso no puede depender de la base. Lo único que
las distingue es la población —5 clientes contra 3— que es para lo que esa
columna está puesta. Sin ella, pegar una creyendo que son las dos se imprime
igual de prolijo.

**El `0 listados` de las dos es el estado del día que se corrió**, no un
resultado: la pantalla que los escribe se cableó después, en el mismo día. Un
cero de población recién migrada no es el cero de una función que nadie usa.

**Y el testigo dice que las dos tienen pedidos al 19/09**, que es lo que hace
falta para que `renglones_de_los_ultimos_pedidos` tenga de dónde sacar el
promedio. No dice que Palmala vote en nada más: eso sigue cerrado por decisión
del dueño desde el 19/09.

## 21/09 — `pase_a_segunda_3_con_ficha` (el pase de cajas ya armadas)

`db/pase_a_segunda_3_con_ficha.sql`, con su verificación corrida aparte.

```
FRUTAMAX  guarda nueva 1 · vieja 0 · 0 pases con ficha · 123 movimientos · última guía R 21/09
PALMALA   guarda nueva 1 · vieja 0 · 0 pases con ficha ·   1 movimiento  · sin guías R
```

**Las DOS columnas de guarda van separadas porque el constraint CAMBIA DE
NOMBRE** (`..._ficha_solo_merma` → `..._ficha_solo_merma_o_pase`). Un "¿existe
alguno?" habría dado 1 en los dos estados y la fila se leería igual antes y
después. Antes de correr da `0 · 1`; después `1 · 0`.

**El `0 pases con ficha` de las dos es el estado del día que se corrió**, no un
resultado: la pantalla que los escribe se cableó después, en el mismo commit.
Un cero de población recién migrada no es el cero de una función que nadie usa.

**El testigo dice que Palmala NO VOTA, y se ve en la misma fila**: `1
movimiento · sin guías R`. Esa fila confirma lo único que Palmala puede
confirmar —que la migración no explota contra ese esquema— y nada sobre si el
pase funciona. Eso lo decide Frutamax, con sus 123.

**Y el esquema del repo estaba atrasado LA FUNCIÓN ENTERA**, no solo este
bloque: `db/esquema_completo.sql` no nombraba `pase_a_segunda` en ninguno de
los cuatro CHECKs que los bloques 1 y 2 cambiaron el 20/09, así que una base
nueva creada desde ahí habría rechazado todo pase. Corregido en el mismo
commit, y verificado comparando las 25 guardas de `movimientos_stock` entre
una base creada desde el esquema y otra creada desde las migraciones:
idénticas.

## 22/09 — `cargas_compra` (la cabecera, los renglones y el puente del Paso 1)

`db/cargas_compra_1_cabecera.sql` y `_2_renglones_y_puente.sql`, con
`db/cargas_compra_verificacion.sql` corrida aparte.

```
PALMALA   3 tablas · 2 guardas · 1 único · 2 cascadas · 3 sin cascada · 5 clientes · último pedido 22/09
FRUTAMAX  3 tablas · 2 guardas · 1 único · 2 cascadas · 3 sin cascada · 3 clientes · último pedido 22/09
```

**El único se cuenta por `contype = 'u'` y no por nombre**: el nombre lo genera
Postgres (`cargas_compra_cliente_id_fecha_key`) y un conteo por nombre
inventado no encuentra nada aunque el constraint esté.

**Y las cascadas se cuentan por COMPORTAMIENTO** (`confdeltype` `'c'` contra
`'a'`), no por cantidad de FK: las cinco existen en los dos estados y lo que
cambia es qué hacen. Un `count(*)` de foreign keys da 5 antes y después. Es el
mismo caso del `on delete` de los precios (14/09) y el de las guardas
NULL-safe (16/09) — la tercera vez que contar por nombre no alcanza.

**Las 2 con cascada son las que tienen que tenerla**: `cargas_compra_renglones
→ cargas_compra` (los renglones son de la carga) y `listados_compra_cargas →
listados_compra` (el puente es del listado). **Las 3 sin cascada son las que
tienen que rebotar**: las dos que apuntan a `clientes` y `articulos`, y —la que
importa— `listados_compra_cargas → cargas_compra`. Borrar una carga que ya se
usó en un listado **tiene que rebotar**, no borrar el rastro de que se usó.

**La verificación usa `to_regclass(...)`** para que una tabla que falte
devuelva NULL en vez de tirar el error: sin eso, correrla antes de la
migración revienta y no se puede usar como "antes".

**El `0 listados` no está en la fila porque la tabla es nueva**: lo que
identifica la base son los clientes —5 contra 3— y el testigo del último
pedido, que es lo que hace falta para que el promedio tenga de dónde salir.

## 23/09 — `cargas_compra_4_margen` (el margen por carga)

`db/cargas_compra_4_margen.sql`, con `db/cargas_compra_4_verificacion.sql`
corrida aparte.

```
FRUTAMAX  columna 1 · guarda 1 · NOT NULL 1 · con margen 0 · 1 carga  · último pedido 22/09
PALMALA   columna 1 · guarda 1 · NOT NULL 1 · con margen 0 · 0 cargas · último pedido 22/09
```

**`NOT_NULL_de_1` va como columna aparte porque un conteo de COLUMNA da 1 en
los dos estados.** La columna existe nulleable y existe `NOT NULL`, y la fila
se leería igual. Lo que decide es `is_nullable = 'NO'`, igual que el `on
delete` y el `IS DISTINCT FROM` de las otras dos.

**`con_margen 0` es el resultado BUENO, no un backfill que no corrió.** Las
cargas que ya estaban se crearon cuando el margen no existía, o sea sin
ninguno, y el bloque las pone en **0 y no en el sugerido**: ponerles 10 las
inflaría un 10% que nadie pidió, y el número que saldría es plausible.

**La columna va SIN DEFAULT en la base a propósito.** El valor de arranque lo
propone la pantalla (`MARGEN_SUGERIDO`, core/que_comprar.py). Dos defaults que
no coinciden es como se separan dos reglas, y el de la base gana en silencio
para todo el que inserte sin pasar por la pantalla.

**La `1 carga` de Frutamax contra `0` de Palmala es lo que identifica la
fila**: las cuatro columnas de la izquierda dicen que la columna y la guarda
están, y eso no puede depender de la base.

## 23/09 — `listados_compra_5_margen_opcional` (el margen se va del listado)

`db/listados_compra_5_margen_opcional.sql`, con su verificación corrida
aparte. Es la mitad de EXPAND (corolario 94): le saca el NOT NULL a
`listados_compra.margen_porcentaje` para que el Paso 2 reescrito pueda crear un
listado sin margen. El código desplegado la sigue escribiendo y no se entera.

```
FRUTAMAX  columna 1 · acepta NULL 1 · 0 listados · último pedido 22/09
PALMALA   columna 1 · acepta NULL 1 · 0 listados · último pedido 22/09
```

**Las dos filas son IDÉNTICAS, testigo incluido**, y eso deja una sola cosa
que dice de qué base es cada una: la etiqueta que el dueño les puso al
pegarlas. Las columnas de la migración dan lo mismo por diseño; lo que no
estaba previsto es que la población (0 listados en las dos: la pantalla que los
escribe todavía no está desplegada) y el último pedido también coincidieran.
Para la próxima verificación de esta tabla, una columna de población que
difiera entre bases —`count(*) from clientes`, 5 contra 3 el 21/09— hace el
trabajo de identificar que acá no hizo nadie.

## 23/09 — `cargas_compra_3_sacar_las_viejas` (el drop, después del deploy)

`db/cargas_compra_3_sacar_las_viejas.sql`, con su verificación corrida
aparte. Corrió **después** del deploy del Paso 2 (v962): hasta ahí el código
de arriba todavía leía las dos tablas y escribía el margen del listado
(corolario 94).

```
FRUTAMAX  clientes 0 · manual 0 · margen 0 · 3 clientes
PALMALA   clientes 0 · manual 0 · margen 0 · 5 clientes
```

**Los tres ceros son el resultado BUENO**: las dos tablas y la columna ya no
están. Lo que identifica la base son los clientes —3 contra 5—, que es lo
único que puede ser distinto entre dos bases a las que se les sacó lo mismo.

**Y `db/esquema_completo.sql` las perdió en el MISMO commit que anotó esta
fila**, no antes: hasta este drop una base nueva las necesitaba.

## 23/09 — `cargas_compra_5_por_bulto`

`db/cargas_compra_5_por_bulto.sql`, con su verificación corrida aparte.

```
FRUTAMAX  columna 1 · guarda 1 · mayor a cero 1 · 3 renglones · último pedido 23/09
PALMALA   columna 1 · guarda 1 · mayor a cero 1 · 0 renglones · último pedido 23/09
```

**Lo que identifica la base son los renglones** —3 contra 0—: las tres
columnas de la migración dan lo mismo por diseño y el último pedido coincide.
La columna nace en NULL en todos los renglones que ya estaban, que es "proponé
el bulto de la ficha": lo mismo que mostraban hasta hoy.

## 23/09 — `listados_compra_7_foto_del_stock`

`db/listados_compra_7_foto_del_stock.sql`, con su verificación corrida aparte.

```
FRUTAMAX  columna 1 · foto 1 · foto_cajas 1 · fk no action 1 · 1 listado  · último pedido 23/09
PALMALA   columna 1 · foto 1 · foto_cajas 1 · fk no action 1 · 0 listados · último pedido 23/09
```

**Lo que identifica la base son los listados** —1 contra 0—. Antes se corrió
`db/listados_compra_6_cuantos_abiertos.sql`: Frutamax 1 abierto (23/09, con
cargas), Palmala 0. Con uno solo abierto, el bloque 8 (un solo listado
abierto, sin fecha) no tiene que decidir nada sobre listados viejos.

## 23/09 — `listados_compra_8_un_solo_abierto`

`db/listados_compra_8_un_solo_abierto.sql`, corrida **después** del deploy
de v971 (corolario 94), con su verificación aparte.

```
FRUTAMAX  viejo 0 · nuevo 1 · sobre constante 1 · 1 abierto  · 1 listado  · último pedido 23/09
PALMALA   viejo 0 · nuevo 1 · sobre constante 1 · 0 abiertos · 0 listados · último pedido 23/09
```

**Lo que identifica la base son los listados** —1 contra 0— y los abiertos.
El índice de "uno por día" se fue y el de "uno abierto, punto" está puesto
en las dos. `db/esquema_completo.sql` lo cambió en el mismo commit que anotó
esta fila.

## 23/09 — `pallet_1_cajas_por_pallet`

`db/pallet_1_cajas_por_pallet.sql`, con su verificación corrida aparte.

```
FRUTAMAX  columna 1 · guarda 1 · 2 envases · 0 con pallet · último mov de cajas 17/09
PALMALA   columna 1 · guarda 1 · 2 envases · 0 con pallet · sin movimientos
```

**Lo que identifica la base es el testigo** —17/09 contra ninguno—.

## 23/09 — `cargas_compra_dias` (bloque 1)

`db/cargas_compra_dias_1.sql`, con su verificación corrida aparte. El bloque 2
(`cargas_compra_dias_2.sql`, NOT NULL) va **después** del deploy (corolario 94).

```
FRUTAMAX  columna 1 · acepta null YES · guarda 1 · 3 cargas · 0 sin días · 0 distintas de uno
PALMALA   columna 1 · acepta null YES · guarda 1 · 0 cargas · 0 sin días · 0 distintas de uno
```

**Lo que identifica la base son las cargas** —3 contra 0—.

## 23/09 — `cargas_compra_dias` (bloque 2, NOT NULL)

`db/cargas_compra_dias_2.sql`, corrido **después** del deploy de v974 (corolario
94), con la verificación corrida aparte.

```
FRUTAMAX  columna 1 · acepta null NO · guarda 1 · 3 cargas · 0 sin días · 0 distintas de uno · última 23/09
PALMALA   columna 1 · acepta null NO · guarda 1 · 0 cargas · 0 sin días · 0 distintas de uno
```

**Lo que identifica la base son las cargas** —3 contra 0—.
`db/esquema_completo.sql` pasó `dias` a `not null` en el mismo commit que anotó
esta fila.

## 23/09 — `segunda_al_cliente_3`

`db/segunda_al_cliente_3_tilde_y_renglon.sql`, con la verificación corrida aparte.

```
FRUTAMAX  tilde 1 · columna 1 · guarda 1 · 0 con tilde · 3 clientes · 0 renglones con segunda · último armado 23/09
PALMALA   tilde 1 · columna 1 · guarda 1 · 0 con tilde · 5 clientes · 0 renglones con segunda · último armado 23/09
```

**Lo que identifica la base son los clientes** —3 contra 5—.

## 25/09 — `cajas_rotas_1_merma`

`db/cajas_rotas_1_merma.sql`, con `db/cajas_rotas_2_verificacion.sql` corrida aparte.

```
FRUTAMAX  origen con merma 1 · signo con merma 1 · 11 movimientos · último 24/09
PALMALA   origen con merma 1 · signo con merma 1 ·  0 movimientos · sin movimientos
```

**Lo que identifica la base son los movimientos de cajas** —11 contra 0—.
`db/esquema_completo.sql` ganó el origen `merma` en el mismo commit que la
construyó.

## 25/09 — `vacios_foto_1_el_corte_de_hoy`

`db/vacios_foto_1_el_corte_de_hoy.sql`, con `db/vacios_foto_2_verificacion.sql` corrida aparte.

```
FRUTAMAX  tabla 1 · 42 fotos de 42 proveedores · 1 fecha · FOTO total 1.758 · 0 negativas · 24 en cero con recepciones · última recepción 25/09
PALMALA   tabla 1 · 44 fotos de 44 proveedores · 1 fecha · FOTO total 0     · 0 negativas · 35 en cero con recepciones
```

**Lo que identifica la base son los proveedores** —42 contra 44—. El 1.758 de
Frutamax coincide clavado con lo que mostraba la pantalla ese día. Los que
quedaron en cero con recepciones son los que nunca se contaron: se arreglan
con un ajuste cuando aparezcan (decisión del dueño).

## 25/09 — `guia_deposito_1_columna_y_unico` (fase 1)

`db/guia_deposito_1_columna_y_unico.sql`, con `db/guia_deposito_4_verificacion.sql` corrida aparte.

```
FRUTAMAX  columna 1 · único nuevo 1 · únicos 2 · 15 mal ubicadas · 0 guías depósito · 0 con fotos · 15 ingresos directos
PALMALA   columna 1 · único nuevo 1 · únicos 2 ·  9 mal ubicadas · 0 guías depósito · 0 con fotos ·  9 ingresos directos
```

**Lo que identifica la base son los ingresos directos** —15 contra 9—. Las
"mal ubicadas" son exactamente los ingresos directos, que siguen en la guía
del Puesto hasta que corran los bloques 2 y 3 (después del deploy). Resultado
esperado de esa fase: `1 · 1 · 1 · 0`.

## 25/09 — `vacios_marcas_1` a `4` (fase 1)

`db/vacios_marcas_1_marcas_y_compras.sql`, `_2_devoluciones_y_conteos`,
`_3_ajustes` y `_4_asignaciones`, con `db/vacios_marcas_6_verificacion.sql`
corrida aparte.

```
FRUTAMAX  3 · 4 · 6 · 2 · YES · 13 devoluciones · 13 sin foto
PALMALA   3 · 4 · 6 · 2 · YES ·  0 devoluciones ·  0 sin foto
```

**Lo que identifica la base son las devoluciones** —13 contra 0—. Las 13 sin
foto de Frutamax son las viejas y quedan como están (dueño): el CHECK del
bloque 5 entra `not valid`. Falta el bloque 5, después del deploy, y ahí la
verificación tiene que dar `3 · 4 · 6 · 3 · YES`.

## 25/09 — `guia_deposito_2` y `guia_deposito_3` (post-deploy de v991)

Corridos seguidos, con `db/guia_deposito_4_verificacion.sql` aparte.

```
FRUTAMAX  columna 1 · único 1 · únicos 1 · 0 mal ubicadas · 13 guías de depósito · deposito_con_fotos 2 · 15 ingresos directos
PALMALA   columna 1 · único 1 · únicos 1 · 0 mal ubicadas ·  6 guías de depósito · deposito_con_fotos 1 ·  9 ingresos directos
```

**Lo que identifica la base son los ingresos directos** —15 contra 9—. Las
compras quedaron bien. `deposito_con_fotos` no dio 0 y se abrió
`db/guia_deposito_5_fotos_en_guias_de_deposito.sql` para ver de dónde vino
cada foto antes de tocar nada. **Y el "tiene que dar 0" de la verificación
era de más**: la pantalla Fotos de la guía de una compra de ingreso directo
cuelga la foto de SU guía, que ahora es la de depósito, y eso es correcto.

## 25/09 — `guia_deposito_5_fotos_en_guias_de_deposito` (solo lectura)

La consulta de las fotos que quedaron en guías de depósito, en las dos bases.

```
FRUTAMAX  guía 190 · 26/08 · Dimimax  · COMANDA de Compras · compra 310 Berenjena · guía de compras ese día null · 0 borradas
          guía 204 · 26/08 · 2 cabezas · SUBIDA desde la compra · compra 309 Morrón Rojo
PALMALA   guía 144 · 27/08 · Saturno  · SUBIDA desde la compra · compra 144 Zapallito 1ra
```

**Dos de tres son del ingreso directo y están bien.** La guía 190 tiene una
comanda de Compras colgada de una guía que quedó de depósito, sin guía de
Compras ese día y sin compras borradas: o se colgó con "Terminar con la
comanda" cuando la única guía del día era la del ingreso, o la compra que la
trajo se movió de día o de proveedor (eso no deja rastro).

**Decisión del dueño (25/09): se deja donde está.** Es una sola foto de un
mes atrás, no mueve ningún número, y moverla pedía crear una guía que no
existe. Lo único que hace es aparecer en el detalle de la compra 310. **Y ya
no se puede repetir**: desde v991 la comanda de la carga manual solo se cuelga
de la guía de Compras (`agregar_foto_guia_del_dia` pregunta `de_deposito =
false`). Por eso `deposito_con_fotos` de Frutamax va a seguir dando 1 más las
fotos que se suban desde una compra de ingreso directo — ninguna de las dos
cosas es un error.

## 25/09 — `vacios_marcas_5_foto_obligatoria` (post-deploy)

El CHECK de la foto del vale, NOT VALID, corrido después del deploy del código
que ya la exige. Verificación `vacios_marcas_6`, en las dos bases:

```
PALMALA   3 · 4 · 6 · 3 · YES ·  0 devoluciones ·  0 sin foto
FRUTAMAX  3 · 4 · 6 · 3 · YES · 13 devoluciones · 13 sin foto
```

`guardas_de_3` pasó de 2 a 3, que es lo único que este bloque mueve. Las 13
sin foto de Frutamax son las devoluciones de antes de la regla y quedan como
están (decisión del dueño): el NOT VALID no las revisa, y toda fila nueva lo
cumple. **Palmala no vota** —solo confirma que el bloque no explota—. El CHECK
entró a `db/esquema_completo.sql` en el mismo commit, validado: una base nueva
no tiene filas viejas.

**Y ese NOT VALID dejó una pared puesta**, encontrada el mismo día al cerrar
Vacíos: NOT VALID exime a lo viejo solo del chequeo al crearse, y todo UPDATE
posterior se chequea — así que **las 13 viejas de Frutamax no se pueden
anular** desde que corrió. Lo arregla `vacios_marcas_7_las_viejas_se_anulan`
(corrida el mismo 25/09, abajo), que exime a las que van contra una compra y deja el
CHECK validado.

## 25/09 — `vacios_marcas_7_las_viejas_se_anulan`

El CHECK de la foto del vale, recreado para eximir a las devoluciones del
modelo viejo (las que van contra una compra) y VALIDADO. Arregla la pared que
dejó el NOT VALID de `vacios_marcas_5`. Verificación, en las dos bases:

```
FRUTAMAX  exime viejas 1 · validada 1 · 13 sin foto · 0 ofensores · 13 devoluciones
PALMALA   exime viejas 1 · validada 1 ·  0 sin foto · 0 ofensores ·  0 devoluciones
```

`guarda_exime_viejas` y `guarda_validada` en 1 en las dos: el CHECK es el
nuevo y está validado entero. Las 13 sin foto de Frutamax son las mismas 13
viejas de `vacios_marcas_5`, todas contra una compra (`ofensores 0`), y ahora
se pueden anular. **Palmala no vota** —solo confirma que el bloque no
explota—. `db/esquema_completo.sql` ya tenía esta definición desde v997.

## 27/09 — `costo_tarde_1_completar_lo_que_ya_esta`

Completa el costo de las guías R que habían consumido una compra antes de que
se le cargara el importe, y de las guías que consumieron la primera de ésas.
Corrida por el dueño y verificada con el Claude que tiene lectura:

```
FRUTAMAX  compra por completar 0 · reproceso por completar 0 · completas sin total 0 · quedan sin costo 28
PALMALA   corrió sin error, nada que completar
```

Las guías 502 y 527 de Palta quedaron con costo: 28.800 y 28.294,74 por
bulto. Las 28 que siguen sin costo **se quedan así, por decisión del dueño**:
24 son de antes del corte, y 4 son del 05/09 y consumen guías viejas que nunca
tuvieron costo. No es un pendiente. Desde v1003 el código completa solo el
costo cuando se carga el importe tarde.

## 27/09 — `codigos_1` a `codigos_4` (códigos alternativos y fusión de FRUTAMAX S.R.L.)

Los cuatro bloques corridos por el dueño en las dos bases, sin errores. Crean
`proveedores_codigos` y `compras.codigo_llegada`, y en Frutamax pasan todo lo
del proveedor 40 (FRUTAMAX, N09P39) al 3 (FRUTAMAX S.R.L., N09P41) y dejan
N09P39 como código alternativo del 3. Verificación (`codigos_verificacion`):

```
FRUTAMAX  tabla 1 · columna 1 · guardas 2 · FK de marca 6 · compras sin código 0
          FRUTAMAX que queda 0 · códigos de la SRL N09P41 + N09P39
          compras de la SRL N09P39: 26 · N09P41: 326 · aprendizaje 129 ("limon" -> Limón)
          foto de vacíos 798 · códigos alternativos 1 · proveedores 41
          última recepción 25/09 · guías que quedan del 40: 0
PALMALA   tabla 1 · columna 1 · guardas 2 · FK de marca 6 · compras sin código 0
          códigos alternativos 0 · proveedores 44
```

Palmala no vota. Solo confirma que los bloques no explotan y que ahí no se
tocó nada: cero códigos alternativos. Las 26 compras con `N09P39` son las que
llegaron por el puesto 39, así que el código de llegada quedó con el que
tenían.

**Dos tablas que apuntan a `proveedores` y no estaban en la lista del bloque 4**:
`recepciones` y `aprendizaje_proveedores`. Están vacías en las dos bases, y
el código (`app/`, `core/`, `scripts/`) no las usa: `recepciones` es una de
las tablas muertas del diseño original. No molestaron, y el borrado del 40 no
las necesitaba.

## 27/09 — `lazzaro_1` y `lazzaro_2` (fusión de PRODUCTOS DON LAZZARO en DON LAZZARO)

Los dos bloques corridos por el dueño en las dos bases, sin errores. En
Frutamax pasan todo lo del 17 (PRODUCTOS DON LAZZARO, L02P44) al 10 (DON
LAZZARO, L02P42) y dejan L02P44 como código alternativo del 10. Verificación
(`lazzaro_verificacion`):

```
FRUTAMAX  lazzaro_1_y_2 · testigo 1 · PRODUCTOS que queda 0 · DON LAZZARO 1
          códigos L02P42 + L02P44 · compras L02P42: 14 · L02P44: 1
          compras sin código 0 · códigos alternativos 2 · proveedores 40
          última recepción 27/09 · las 11 guías en el id 10
PALMALA   lazzaro_1_y_2 · testigo 0 · alternativos 0 · proveedores 44
```

Palmala no se tocó: el testigo (N09P39 como alternativo) da 0 y los bloques
salen sin hacer nada.

## 28/09 — corrección puntual: consumo de la R556 anulada sobre la compra 827 (SOLO Frutamax)

No es una migración: es un arreglo de datos de una sola vez, corrido por el
dueño a mano. La compra 827 (Palta, 27/09) se cargó con los datos cruzados, se
volvió a cargar bien, y había que borrarla. "Corregir o eliminar compra" la
frenaba con "R556 se costeó contra este lote", aunque la R556 estaba anulada
desde el 28/09 a las 11:21: su consumo congelado seguía apuntando a la compra.

```sql
delete from reprocesos_consumos rc
using reprocesos r
where r.id = rc.reproceso_id
  and rc.compra_id = 827
  and r.anulado_el is not null
returning rc.reproceso_id, rc.compra_id, rc.bultos;
```

```
FRUTAMAX  556 · 827 · 8
```

Una fila: el consumo de 8 bultos de la R556 anulada. Palmala no se corrió, no
había nada que corregir ahí.

Desde v1010 esto ya no hace falta a mano: el borrado ignora las guías R
anuladas y borra sus consumos en la misma transacción
(`_SQL_BORRAR_CONSUMOS_DE_GUIAS_ANULADAS`, app/db.py).

## 28/09 — `comparar_esquema` en las dos bases (huellas de columnas)

Corrida por el dueño. Formato tabla:columnas:huella(8):filas. Resultado,
comparado contra una base cargada con `db/esquema_completo.sql`:

```
FRUTAMAX  73 tablas · 64 iguales al repo · 8 de más · 0 con columnas distintas
PALMALA   64 tablas · 64 iguales al repo · 0 de más · le falta 1
```

- **De más, solo en Frutamax**: las cinco vacías del diseño original
  (`recepciones`, `aprendizaje_proveedores`, `pedidos_supermercado`,
  `precios_dia`, `resultados`), `conversion_articulos_cliente` (31 filas),
  `e5_mov` (146) y `parametros_historial` (1).
- **Le falta a Palmala**: `corte_respaldo_fichas_reprocesos`, que está en el
  repo y en Frutamax. Es el respaldo del corte de Frutamax; el código no la usa.
- **Columnas distintas: ninguna**, en las 64 compartidas. La huella mira
  nombres, tipos y NOT NULL; no defaults, CHECKs, FKs ni índices.

Esto destapó que v1010 consultaba `recepciones` al borrar una compra, y en
Palmala esa tabla no existe (ver CLAUDE.md, "Una guía R ANULADA no retiene
nada"). Arreglado en v1011.

## 28/09 — `recepciones` creada VACÍA en Palmala (destrabe, SOLO Palmala)

Corrida por el dueño. En Palmala, Detalle de compra → Gerencia (Corregir o
eliminar compra) tiraba `relation "recepciones" does not exist` en
`SELECT id FROM recepciones WHERE compra_id = 684 ORDER BY id`.

Esa consulta la agregó v1010 a `_lo_que_cuelga` y la sacó v1011. Solo
v1010 la tuvo: ni v1009 ni v1011 nombran la tabla. El error es de la
ventana en que v1010 estaba desplegada. Para destrabar, se creó la tabla
vacía con la misma definición que tiene en Frutamax
(`create table if not exists recepciones (...)`, la de db/schema.sql). No
tocó ningún dato.

Con esto `recepciones` existe en las DOS bases, vacía, y no está en
db/esquema_completo.sql. El código no la usa: solo la fusión de
proveedores la nombra, y le pregunta antes si existe (`to_regclass`). El
borrado de las cinco vacías (`tablas_viejas_1`) quedó en suspenso por
decisión del dueño.

## 28/09 — `segunda_ajuste_1` (tabla `ajustes_segunda`), las DOS bases

Corrida por el dueño. Verificación (`db/segunda_ajuste_1_verificacion.sql`),
corrida aparte:

```
FRUTAMAX  segunda_ajuste_1 · tabla 1 · columnas 8 · checks 2 · índice 1 · filas 0 · último remito 24/09
PALMALA   segunda_ajuste_1 · tabla 1 · columnas 8 · checks 2 · índice 1 · filas 0 · sin remitos
```

Es lo esperado en las dos. El código que la usa (la pata del pool de segunda,
el botón del Cotejo y la pantalla del ajuste) entró en el commit siguiente.

## 28/09 — `vacios_marca_texto_1_vincular`, las DOS bases

Corrida por el dueño. Verificación (`db/vacios_marca_texto_1_verificacion.sql`),
corrida aparte:

```
FRUTAMAX  vacios_marca_texto_1_vincular · faltan_vincular 0 · vinculadas 8 · con_marca_sin_sena 17 · marcas 8 · recibidas_desde_la_foto 27 · última recepción 28/09
PALMALA   corrió, con el comentario de la tabla puesto (fila no pegada)
```

Las 17 con marca escrita y sin seña quedan sin vincular a propósito: sin seña
no entran a Vacíos. De Palmala el dueño confirmó que corrió pero no pegó la
fila, así que su `faltan_vincular` no está anotado.

Y de yapa, el caso de Rio Uruguay con `db/vacios_rio_uruguay_1_de_donde_sale.sql`
(solo lee, Frutamax): foto 350 + 168 con seña · 0 sin seña · 0 devueltos · 0
ajustes = 518, igual que la pantalla.

## 28/09 — `vacios_conteo_2809_1` a `_5`: arranque de vacíos desde el conteo físico

Corrida por el dueño. Bloques 1 (tablas), 2 (datos, con `frutas jrobol`
corregido), 3 (buscadores) y 4 (revisión, solo lee) en las dos bases; el
bloque 5 (carga) en Frutamax, que es la única que hace algo. Verificación
(`db/vacios_conteo_2809_6_verificacion.sql`), corrida aparte:

```
FRUTAMAX  vacios_conteo_2809_5_cargar · arranques 1 · pilas 17 · total 1086 · filas_iguales 17 · sin_proveedor 1 · stock_ahora 1086 · arrancó 28/09 20:21 · última recepción 28/09 13:01
PALMALA   vacios_conteo_2809_5_cargar · arranques 0 · pilas 0 · sin_proveedor 0 · no se tocó nada
```

Es lo esperado en las dos. Que la verificación corra en Palmala confirma que
las tablas del bloque 1 están ahí, que es lo que el código necesita. Desde
ahora la cuenta de Frutamax arranca de este conteo; la foto del 25/09 y
`vacios_foto_4` quedan como historia (el 4 no se corrió).

## 29/09 — `tipo_de_cajon_1` a `_3`: sale el tipo de cajón por proveedor (paso 2)

Corrida por el dueño en las dos bases, después de ver v1028 en el pie (el
paso 1, que dejó de leer y escribir el tipo, ya estaba desplegado).

Revisión (`tipo_de_cajon_1_revisar.sql`, solo lee), antes de borrar:

```
FRUTAMAX  columna 1 · tabla 1 · tipos cargados 1 · proveedores con tipo 1 · se pierde "RIO URUGUAY → Goloso" · fks 1 · proveedores 41
PALMALA   columna 1 · tabla 1 · tipos cargados 0 · proveedores con tipo 0 · fks 1 · proveedores 44
```

Verificación (`tipo_de_cajon_3_verificacion.sql`), corrida aparte del `do`:

```
FRUTAMAX  tipo_de_cajon_2_borrar · columna 0 · tabla 0 · proveedores 41 · última recepción 28/09 13:01
PALMALA   tipo_de_cajon_2_borrar · columna 0 · tabla 0 · proveedores 44 · última recepción 28/09 17:54
```

Se fueron la columna y la tabla, y la población de proveedores quedó igual
en las dos. Lo único que se perdió es lo que la revisión dijo: el "Goloso"
declarado de Rio Uruguay en Frutamax, que ya vive como marca en Vacíos.
`db/esquema_completo.sql` perdió las dos cosas en el mismo commit.

## 29/09 — `vacios_origen_devolucion_1`: por dónde entró cada devolución de vacíos

Corrida por el dueño en las dos bases. Agrega `vacios_deposito_devoluciones.cargada_desde`
(deposito, administracion o compras) con su CHECK. Verificación
(`vacios_origen_devolucion_2_verificacion.sql`), corrida aparte del `do`:

```
FRUTAMAX  vacios_origen_devolucion · columna 1 · check 1 · devoluciones 13 · con valor 0
PALMALA   vacios_origen_devolucion · columna 1 · check 1 · devoluciones 0
```

Las 13 de Frutamax quedan en NULL, que es lo esperado: no hay forma de saber
por dónde entraron, y deducirlo sería inventarlo. Palmala no tiene
devoluciones: ahí la verificación solo confirma que la migración no explota.
`db/esquema_completo.sql` ganó la columna y el CHECK en el mismo commit que
el código que la escribe (parte 3 de Vacíos).

## 30/09 — `devolucion_deposito_1`: el tipo de movimiento de la devolución desde depósito

Corrida por el dueño en las dos bases. Agrega el tipo `devolucion_deposito` a
`movimientos_stock` y sus dos guardas (la compra obligatoria y la cantidad
negativa). Verificación (`devolucion_deposito_2_verificacion.sql`), corrida
aparte del `do`, según el dueño:

```
FRUTAMAX  devolucion_deposito · tipo_nuevo 1 · compra_abierta 1 · guarda_nueva 1
PALMALA   devolucion_deposito · tipo_nuevo 1 · compra_abierta 1 · guarda_nueva 1
```

Llegaron los tres chequeos en 1 de cada base; la población y el testigo no
vinieron en el mensaje. Con esto "Devolver mercadería" (`/deposito/devolver`)
anda en las dos.

## 30/09 — `vales_1` a `vales_4`: Vales a cobrar

Corridas por el dueño en las dos bases: la tabla de vales, las salidas, los
límites y el listado de los vales en papel con su vista de revisión.
Verificación (`vales_5_verificacion.sql`), corrida aparte de los `do`, según
el dueño:

```
FRUTAMAX  vales_a_cobrar · tablas 3 · listado_y_revision 2 · origen_null_safe 1 · salidas 4 · anular_gerencia 1 · cobro_null_safe 1 · 500000.00 / 14 · vales 0
PALMALA   vales_a_cobrar · tablas 3 · listado_y_revision 2 · origen_null_safe 1 · salidas 4 · anular_gerencia 1 · cobro_null_safe 1 · 500000.00 / 14 · vales 0
```

Los dos CHECK con `importe > 0` quedaron con el `coalesce` (los
`null_safe` en 1), y la cartera arranca vacía en las dos, que es lo esperado:
nada se backfilleó y las devoluciones del 25/09 son pruebas. La población y
el testigo no vinieron en el mensaje. Palmala no vota: ahí la verificación
solo confirma que las migraciones no explotan. Los vales en papel todavía no
se cargaron (`vales_papel_1` a `4`).

## 30/09 — `fotos_1` a `fotos_4`: fotos anexadas a los vales y regla de 3 años

Corridas por el dueño en las dos bases: las fotos anexadas a un vale, la
marca de la foto de una devolución (`fotos_recepcion.movimiento_id`), las
fotos de pesada de compras borradas y el registro de las borradas por
antigüedad. Verificación (`fotos_5_verificacion.sql`), corrida aparte de los
`do`, según el dueño (la leyó el Claude con acceso de lectura):

```
FRUTAMAX  fotos · tablas 3 · columna 1 · devolucion_marcadas 0 · devolucion_sin_marcar 0 · población fotos_recepcion 323
PALMALA   fotos · tablas 3 · columna 1 · devolucion_marcadas 0 · devolucion_sin_marcar 0 · población fotos_recepcion 202
```

No había ninguna foto de devolución que marcar en ninguna de las dos bases,
así que el backfill no tocó nada. El testigo no vino en el mensaje. Palmala no
vota: ahí la verificación solo confirma que las migraciones no explotan.

## 01/10 — `remitos_1` a `remitos_4`, `fotos_6` a `fotos_8` y `devolucion_sector_1`

Corridas por el dueño en las dos bases. Las verificaciones van corridas aparte
de los `do` y las verificó el Claude con acceso de lectura:

```
FRUTAMAX  remitos · tablas 4 · indices 5 · checks 5 · anulado 0
PALMALA   remitos · tablas 4 · indices 5 · checks 5 · anulado 0
FRUTAMAX  fotos_plazos · tablas 2 · columnas 2 · check 1 · sin_como 0 · plazos 0
PALMALA   fotos_plazos · tablas 2 · columnas 2 · check 1 · sin_como 0 · plazos 0
FRUTAMAX  devolucion_sector (tras el bloque 1) · columna 1 · valida 1 · coherente 0 · sin_sector 0 · de_mas 0 · población 0
PALMALA   devolucion_sector (tras el bloque 1) · columna 1 · valida 1 · coherente 0 · sin_sector 0 · de_mas 0 · población 0
```

`coherente 0` es lo esperado después del bloque 1: el CHECK de la devolución
con sector lo agrega `devolucion_sector_2`, que se corre DESPUÉS del deploy
(completa lo que cargue el código viejo en el medio). Corrió el mismo día:
ver la entrada de abajo.
Población de devoluciones en 0 en las dos bases, así que el bloque 2 no tiene
filas viejas que completar salvo las que entren antes del deploy. Las
poblaciones de remitos y fotos y el testigo no vinieron en el mensaje.
Palmala no vota: ahí solo confirma que las migraciones no explotan.

## 01/10 — `devolucion_sector_2`: el CHECK de la devolución con sector

Corrida por el dueño en las dos bases DESPUÉS del deploy de v1060 (PR #82),
como pide su encabezado. Verificación (`devolucion_sector_3`), corrida aparte
del `do`, la verificó el Claude con acceso de lectura:

```
FRUTAMAX  devolucion_sector (tras el bloque 2) · columna 1 · valida 1 · coherente 1 · sin_sector 0 · de_mas 0 · población 0
PALMALA   devolucion_sector (tras el bloque 2) · columna 1 · valida 1 · coherente 1 · sin_sector 0 · de_mas 0 · población 0
```

`coherente 1` es el CHECK puesto. Con población 0 en las dos bases no hubo
devoluciones que completar: el código viejo no cargó ninguna entre los dos
bloques. La tanda de `devolucion_sector` queda cerrada. Palmala no vota.

## 02/10 — `devolucion_valor_2`: el movimiento 170 atado a la compra 807

Corrido por el dueño SOLO en Frutamax (el movimiento 170 es de esa base; en
Palmala no aplica). La verificación (`devolucion_valor_3`, cuya fila se llama
`devolucion_valor_2`), corrida aparte del `do`, la hizo el Claude con acceso de
lectura:

```
FRUTAMAX  devolucion_valor_2 · atada 1 · sin_proveedor_suelto 1 · compra 807 · precio 60.000 · costo del armado 59.822,75 · valor nuevo 600.000 · población 10
```

`atada 1` y `sin_proveedor_suelto 1`: el rechazo ya no apunta al proveedor
suelto sino a la compra 807. El valor nuevo es 10 × $60.000, el precio por
cajón de la compra, y no 10 × $59.822,75 del armado. La población son los 10
rechazos al proveedor no anulados de la base.

## 02/10 — `devolucion_valor_2` dos veces más: los movimientos 138 y 137 atados a su compra

Corridos por el dueño SOLO en Frutamax, con el mismo bloque de
`devolucion_valor_2` cambiando el movimiento, el renglón y la compra.
Verificados por el Claude con acceso de lectura:

```
FRUTAMAX  movimiento 138 · Arándano · renglón 1786 (armado 17/09) · compra 656 · atada · sin proveedor suelto · no anulado · 10 × $22.000 = $220.000
FRUTAMAX  movimiento 137 · Arándano · renglón 1785 (armado 18/09) · compra 709 · atada · sin proveedor suelto · no anulado · 10 × $22.000 = $220.000
FRUTAMAX  población de rechazos al proveedor 10 · con compra 4 (137, 138, 170 y 199)
```

La compra del 138 es la 656 porque era la única compra de Arándano de
FRUTAMAX recibida al momento del armado. La del 137 la eligió Lionel: la
709, a $22.000; la otra opción era la 704, a $20.000. Quedan 6 rechazos al
proveedor sin compra atada, y esos siguen valiendo el costo del armado.

## 02/10 — `cobranza_segunda_1` a `_3`: Cobranzas de segunda

Corridos por Lionel en las dos bases, cada bloque solo. La verificación
(`cobranza_segunda_4`), corrida aparte, la hizo el Claude con acceso de
lectura:

```
FRUTAMAX  cobranza_segunda · tablas 2 · checks 2 · triggers 2 · cobros 0 · lotes 60 · bultos 608 · primer lote 29/08 · último lote 01/10
PALMALA   cobranza_segunda · tablas 2 · checks 2 · triggers 2 · cobros 0 · lotes 0
```

Las dos tablas, los dos CHECK y los dos triggers están en las dos bases. Los
60 lotes de Frutamax arrancan todos pendientes (`cobros 0`). Palmala no tiene
ningún lote al puesto y no vota: confirma solo que los bloques no explotan.

## 02/10 — `vales_manual_1` a `_3`: Vales cargados a mano

Corridos por Lionel en las dos bases, cada bloque solo. La verificación
(`vales_manual_4`), corrida aparte:

```
FRUTAMAX  columnas 2 · origen 1 · coherente 1 · checks 3 · tabla 1 · triggers 2 · diferido 1 · marca_vieja 0 · manuales 0 · vales 8 · anteriores 0 · último vale 01/10
PALMALA   columnas 2 · origen 1 · coherente 1 · checks 3 · tabla 1 · triggers 2 · diferido 1 · marca_vieja 0 · manuales 0 · vales 0
```

Las dos columnas, el origen `carga_manual`, los CHECK, la tabla de
correcciones y los dos triggers (el de importe, número y fecha, y el
diferido del proveedor) están en las dos bases. `marca_vieja 0`: ninguna
función de la base lee ya `app.juntando_proveedores`. Todavía no hay vales
cargados a mano. Palmala no tiene vales y no vota: confirma solo que los
bloques no explotan.

## 02/10 — `tareas_1` a `_3`: Tareas

Corridos por Lionel en las dos bases, cada bloque solo. La verificación
(`tareas_4`), corrida aparte, la hizo el Claude con acceso de lectura:

```
FRUTAMAX  tareas · tablas 3 · constraints 4 · indices 2 · tareas 0 · ocurrencias 0 · testigo 41 proveedores
PALMALA   tareas · tablas 3 · constraints 4 · indices 2 · tareas 0 · ocurrencias 0 · testigo 45 proveedores
```

Las tres tablas, los cuatro constraints y los dos índices están en las dos
bases, todavía sin ninguna tarea cargada. El testigo solo identifica la base.
Palmala no vota: confirma solo que los bloques no explotan.

## 02/10 — `vales_papel_1` a `4` quedan OBSOLETOS

Decisión del dueño: los vales en papel se cargan desde la pantalla de Vales
("Cargar vale", origen `carga_manual`). `db/vales_papel_1_pegar.sql` y los
pasos que lo siguen no se corren más. Lo que ya se cargó por ese camino queda
como `anterior_al_sistema`.

## 02/10 — `vales_editables_1`: Vales editables desde Gerencia (PR #93)

Corrido por Lionel en las dos bases. La verificación (`vales_editables_2`),
corrida aparte, la hizo el Claude con acceso de lectura:

```
FRUTAMAX  vales_editables · coherente_nuevo 1 · devolucion_corregidos 0 · sin_importe 0 · importe_vigente 4313000 · vales 13 · testigo 02/10
PALMALA   vales_editables · coherente_nuevo 1 · devolucion_corregidos 0 · sin_importe 0 · importe_vigente 0 · vales 0
```

El CHECK nuevo está en las dos bases. En Frutamax el importe vigente de los
13 vales es el mismo de antes de correr el bloque ($4.313.000): no cambió
ninguna fila. Palmala no tiene vales y no vota.

## 02/10 — `tareas_5`: Tareas por sector y mensual en varios días (PR #95)

Corrido por Lionel en las dos bases, ANTES del deploy. La verificación
(`tareas_7`), corrida aparte, la hizo el Claude con acceso de lectura:

```
FRUTAMAX  tareas_por_sector · columnas 2 · dia_mes_viejo 1 · con_default 1 · check_creada 1 · check_dias 1 · de_un_sector 0 · mensual_sin_dias 0 · tareas 1
PALMALA   tareas_por_sector · columnas 2 · dia_mes_viejo 1 · con_default 1 · check_creada 1 · check_dias 1 · de_un_sector 0 · mensual_sin_dias 0 · tareas 0
```

Es el resultado esperado entre los dos pasos: `dia_mes` y el default de
`creada_por` siguen puestos porque el código viejo los usa. `tareas_6` los
saca y se corre DESPUÉS del deploy del #95; la misma `tareas_7` tiene que dar
entonces `dia_mes_viejo 0 · con_default 0`. Palmala no vota.

## 02/10 — `tareas_6`: Tareas por sector, segundo paso (PR #95)

Corrido por Lionel en las dos bases DESPUÉS del deploy del #95 (v1076). La
verificación (`tareas_7`), corrida aparte, la hizo el Claude con acceso de
lectura:

```
FRUTAMAX  tareas_por_sector · columnas 2 · dia_mes_viejo 0 · con_default 0 · check_creada 1 · check_dias 1 · de_un_sector 0 · mensual_sin_dias 0 · tareas 1
PALMALA   tareas_por_sector · columnas 2 · dia_mes_viejo 0 · con_default 0 · check_creada 1 · check_dias 1 · tareas 0
```

`dia_mes` ya no existe y `creada_por` no tiene default: desde acá el código
siempre dice quién cargó la tarea. La única tarea de Frutamax sigue y no
cambió. Palmala no vota. Con esto Tareas por sector queda cerrado.

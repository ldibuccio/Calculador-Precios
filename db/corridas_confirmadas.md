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

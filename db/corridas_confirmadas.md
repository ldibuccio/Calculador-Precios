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

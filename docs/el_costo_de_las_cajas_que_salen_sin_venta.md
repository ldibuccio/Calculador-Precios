# El costo de las cajas que salen sin una venta atrás

Del 16/09. Es el último hilo de las tres puertas. **No se construyó nada**:
esto es el planteo y la medición que lo decide.

## Lo que ya está cerrado, para no volver a discutirlo

Las tres puertas **no son un agujero de STOCK de cajas**. La caja se
descuenta cuando se ARMA —en la guía R— así que para cuando sale por
cualquiera de las tres ya estaba descontada. El stock lo refleja solo.

Lo que sí son es un agujero de **COSTO DE ENVASE**, y ésa es otra pregunta.

## La observación que cambia la forma del problema

El costo de envase **ya se cobra**, y se cobra por unidad de PRIMERA vendida:
`_envases_por_unidad_ponderado` (app/costeo.py) devuelve `1/contenido_ficha`
cajas por unidad, y `calcular_listado_para_negociar_precios` lo multiplica por
el costo vigente del envase. Eso entra en el precio sugerido y en la utilidad.

Esa tasa **supone que toda caja que sale la paga una unidad de primera.** Las
cajas de las otras puertas salen sin una primera atrás:

| puerta | ¿hay caja nuestra? | ¿la paga una venta? |
|---|---|---|
| 1. envase perdido de origen | **no** — sale en el cajón del proveedor | no aplica |
| 2. la segunda que se remite al Puesto | **sí** — se pone en caja de Día en la mesa | **no** |
| 3. la devolución al proveedor | **sí, si vuelve en caja de Día** | **no** |
| (el rechazo a cajón grande) | sí, y **VUELVE** | no aplica: la recupera |

Así que **no falta una línea de costo nueva. Lo que falta es saber por cuánto
está corta la tasa que ya existe.** La primera está subsidiando a la segunda,
y el número que lo dice es `por_segunda / (por_primera + por_segunda)`.

Eso es una corrección sobre algo que ya se cobra, en el lugar donde ya se
cobra. Es mucho más barato que una cuenta nueva, y no hay dos reglas.

## Las TRES correcciones a los números del 16/09

Las tres son de razonamiento, no de aritmética, y las tres invalidan lo que
dije. **No se corrige la prosa mirando la prosa**: las consultas viejas no
quedaron en el repo, así que los números no se pueden reabrir y **no se
vuelven a citar**. Lo que queda es la consulta nueva.

### 1. Las 230 pueden estar contadas dos veces

Una consulta contaba las cajas que **salen** por las tres puertas y la otra
las que **se llenan** con segunda. **Es la misma caja en dos momentos**: la
segunda se pone en caja nuestra en la guía R y esa misma caja se va después
con el remito al Puesto. Sumarlas cuenta cada caja dos veces.

Por eso la consulta nueva mide **en la guía R y una sola vez**, que además es
el único lugar donde se sabe de qué envase es.

### 2. El conteo no se podía pasar a pesos, y ahora sí

Los bultos de segunda venían `sin envase`: hasta el 16/09 `reprocesos` no
tenía `envase_id`, así que no había forma de saber qué caja era. Multiplicar
por un precio único era inventar la respuesta, con los costos yendo de $650
a $1.600 — **2,5×**.

Desde `adedece` la segunda **sí es atribuible**, así que `pesos_sin_cobrar`
sale por envase, con su `costo_caja` al lado para poder verificar la
multiplicación en la misma fila.

### 3. Los denominadores no cerraban

Una consulta decía 314 guías en 30 días y otra 306 en 90. **Menos guías en
una ventana tres veces más larga es imposible** si cuentan lo mismo, así que
al menos una contaba otra cosa — otro filtro de anuladas, otro `tipo`, u otra
ventana efectiva.

No se resolvió cuál: se reemplazaron las dos por **una sola consulta, con una
ventana, una lista de filtros, y la población en la misma fila**
(`guias_en_la_ventana`), para que la resta se haga mirando un solo resultado.

## La consulta

`db/cajas_6_cuantas_salen_sin_una_primera_atras.sql`. Probada contra
`db/esquema_completo.sql` con los casos plantados, no leída: la guía fuera de
la ventana, la anulada y la que no declara el envase quedan afuera cada una
por su filtro, y el envase sin usar vuelve en ceros en vez de desaparecer.
Los dos canarios la mueven (sin el filtro de anuladas: 100 → 500 de primera;
sin el piso de la ventana: 100 → 118).

## Lo que hay que mirar ANTES de creerle al número

**`sin_declarar` grande invalida la ventana.** `reprocesos.envase_id` y
`lleva_caja_nuestra` se escriben desde el 16/09, así que los 90 días traen
guías viejas que no los tienen. Mientras ese número sea del orden de
`guias_en_la_ventana`, lo que la consulta mide es **la primera semana**, no
noventa días. Conviene correrla de nuevo en octubre.

Es el corolario 24 con otra ropa: un cero prolijo sobre una población que
todavía no existe se lee igual que uno sobre una población medida.

## Lo que queda ANOTADO Y NO CONSTRUIDO

1. **La corrección de la tasa.** Con `pct_sin_primera` medido, la tasa pasa
   de `1/contenido_ficha` a `1/contenido_ficha / (1 − pct)`. Es un solo lugar
   —`_envases_por_unidad_ponderado`— y ninguna regla nueva.

   **Antes de tocarla hay que ver el número.** Si da 3%, mover el precio
   sugerido por eso es ruido; si da 20%, es una caja de cada cinco. Y como
   sube el precio sugerido de todos los artículos de esa ficha, la decisión
   no es técnica.

2. **La puerta 3 no está medida y no se puede.** Hoy la devolución al
   proveedor no dice si la mercadería se fue en caja nuestra: no hay columna.
   La consulta nueva **no la incluye**, y eso está dicho acá para que nadie
   lea `pesos_sin_cobrar` como el total de las tres puertas — es la puerta 2
   sola.

   Si se quiere, la columna es la misma que acabamos de poner en el
   reingreso a cajón grande, con la misma regla y la misma función.

3. **La puerta 1 no va a tener número nunca**, y está bien: no hay caja
   nuestra que perder.

# Separar las cajas por kilaje dentro del mismo artículo

Del 17/09. El pedido: el stock muestra juntas las cajas de 10, 7 y 5 kilos de
Cherry y de Mango, y al armar o reprocesar hace falta saber cuál se usa. Pero
un tomate de 18 y uno de 16 **no** tienen que partirse: eso es variación
normal y partir la pila por eso es ruido.

## Por qué NO es un umbral, ni fijo ni porcentual

La primera propuesta fue un umbral fijo de 3, y el dueño mismo la descartó
con los dos extremos: un cherry de 5 y uno de 7 difieren en 2 y son cajas
distintas; una palta de 80 unidades y una de 84 difieren en 4 y son la misma.
**Un número fijo no mira la escala.**

El porcentaje es estrictamente mejor —5 contra 7 es 40%, 16 contra 18 es 12%,
80 contra 84 es 5%— y con un 25% se parte lo que hay que partir.

**Pero los dos comparten un supuesto que es el que falla: que la separación
se decide por la DISTANCIA entre dos números.** Lo que hace distintas a las
cajas de cherry de 5, 7 y 10 no es que disten mucho: son **tres formatos**,
tres cosas que se compran y se venden como tres cosas. Y lo que hace iguales
a los tomates de 16 y 18 no es que disten poco: son **el mismo formato pesado
dos veces**.

Eso ya está medido en CLAUDE.md, en la sección de Mango y Cherry
multiformato: *"un rango de 12 a 54 en un artículo que viene en tres formatos
no es dispersión: son los tres formatos"*. La mediana no los distingue y un
umbral tampoco — los dos leen una población de tres como si fuera una.

**Por eso la consulta cuenta RACIMOS y no diferencias.** `racimos_25` dice en
cuántas pilas quedaría ese artículo si el corte fuera 25%, y los tres
umbrales (15, 25, 40) van en la misma fila para ver cuál separa lo que hay
que separar sin partir medio catálogo.

## La condición previa: comparar dentro de la MISMA magnitud

Es obligatoria y se cumple sola, pero conviene saber por qué: para Mango el
contenido son unidades **y** kilos a la vez, así que "cajas de 40" y "cajas
de 16k" pueden ser la misma caja. Partirlo por eso lo dejaría en dos pilas
que son una.

`compras.contenido_por_cajon` está expresado en `unidad_compra` —lo dice el
comment de esa columna— así que **adentro de un artículo siempre es la misma
magnitud**, y la consulta lee una sola columna. La columna `MAGNITUD` viaja
en la fila para que eso se vea y no haya que acordarse (corolario 17).

## Probada contra el esquema real

Cargado `db/esquema_completo.sql` en Postgres, con los cuatro casos
plantados:

| artículo (plantado) | valores | salto max | racimos 15 / 25 / 40 |
|---|---|---|---|
| Cherry 5 · 7 · 10 | 3 | 43% | 3 / **3** / 2 |
| Mango 10 · 12 · 40 (unidad) | 3 | 233% | 3 / **2** / 2 |
| Tomate 16 · 16,5 · 18 | 3 | 9% | 1 / **1** / 1 |
| Control, un solo valor | 1 | 0% | 1 / **1** / 1 |

El control de un solo valor está a propósito: ahí el salto es NULL y la
consulta tiene que devolver la fila igual, no romperse ni saltearla. Y el
denominador `ARTS_EN_LA_VENTANA` se movió de 3 a 4 al agregarlo, que es la
forma de saber que entró.

**El esquema real rebotó el fixture** en el primer intento
(`compras.fecha_operacion` NOT NULL), que es exactamente lo que un
`create table` escrito a mano no habría encontrado.

## Lo que la consulta NO decide, y hay que mirarlo al leer el resultado

- **Si el 25% parte medio catálogo, el criterio está mal**, no los datos. Es
  el control de *"más hallazgos que población condena la heurística"*: por eso
  la población viene en la fila.
- **`contenido_por_cajon_real` con el estimado de respaldo.** Lo real es lo
  que se pesó y es lo que hay en el piso; el estimado entra solo donde nadie
  pesó, y eso mismo puede inflar los racimos de un artículo mal estimado. Si
  un artículo aparece partido y sus compras no fueron tocadas, ése es el caso
  a mirar antes de creerle.

## Y lo de Reproceso va SIN umbral

Al elegir el lote, la pantalla muestra proveedor y fecha y **no de cuántos
kilos son las cajas**. Eso se agrega siempre y no depende de ningún criterio:
ahí se quiere el número exacto de lo que se va a usar.

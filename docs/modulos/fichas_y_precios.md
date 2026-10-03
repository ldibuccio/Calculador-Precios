# Módulo: fichas y precios

Movido TAL CUAL desde CLAUDE.md el 03/10 (sin reescribir). Las reglas
vigentes, en corto, están en CLAUDE.md.

## Borrar una ficha DESCONECTABA su historial de precios (CERRADO el 14/09)

Del 14/09, y sale de mirar el sistema con un uso nuevo encima: facturar para
atrás. Estuvo anotado y no construido unas horas; **se construyó el mismo
día, y la decisión de no esperar al número fue del dueño**: el problema es
real igual, y si hoy son cero, mejor — se arregla antes de que pase.

**Eso vale como criterio y no como excepción.** La regla de medir antes de
construir (corolario 23) existe para no inventar pantallas que nadie va a
mirar: ahí el número decide SI el problema existe. Acá el problema no
dependía del número — la FK dice `set null` y eso desconecta, haya pasado
una vez o ninguna. El número dimensiona el RESCATE de lo ya roto, que es
otra decisión —**y esa se cerró el mismo 14/09 en cero: no hubo ningún precio
desconectado en ninguna de las dos bases**, así que no hay nada que rescatar.
**Medir antes de construir la CURA; no antes de cerrar la PUERTA.**

Los precios cuelgan de la FICHA, y esa FK es `on delete set null`. Así que
borrar una ficha **no borra sus precios: les pone `ficha_id` en NULL.** Y
todas las lecturas filtran `ficha_id IS NOT NULL`, así que esos precios dejan
de existir para el sistema.

**EL DATO NO SE PIERDE, SE DESCONECTA**, y la diferencia decide qué se hace
después: la fila conserva `cliente_id`, `articulo_id`, `precio` y
`vigente_desde` — lo único que se va es de qué ficha era. Verificado corriendo
el borrado contra el esquema real: `precios_total 3 · precios_huerfanos 2 ·
articulos_afectados 1`. Un rescate es posible; una pérdida no tendría arreglo.

**SON DOS PUERTAS Y LA SEGUNDA NO PARECE UNA PUERTA:**

1. Eliminar la ficha.
2. **Cambiarle el ARTÍCULO**, que por dentro es un `DELETE` + `INSERT` con id
   nuevo. Desde la pantalla se ve como editar. Su propio docstring ya lo
   avisa: *"Cambiar el artículo DESCONECTA el historial de precios y los
   renglones viejos de esa ficha"*.

### Lo que hace que esto valga como corolario: el comentario lo predijo

`eliminar_ficha` tiene dos guardas —guías R y compras armadas— y su docstring
dice, textual: *"Las dos guardas se enumeran juntas a propósito: son la misma
pregunta ('¿quién apunta a esta ficha?') y separarlas es cómo se olvida la
tercera"*.

**La tercera es `precios_venta_historial`, y no está.** No se olvidó por
descuido: **no podía avisar.** Las dos que están son `NO ACTION` y revientan
la foreign key si alguien intenta borrar; la de precios es `SET NULL` y
**acepta en silencio**. La guarda existe donde la base grita y falta
exactamente donde la base calla.

Y el argumento que justifica el `NO ACTION` de las guías R está escrito arriba
en el mismo docstring —*"con SET NULL, borrar una ficha nulearía sus guías R
en silencio (...) Borrar una ficha no puede mover el stock"*— y se traslada
solo: **borrar una ficha tampoco puede borrar el precio al que se facturó.**

### Lo que se hizo, y lo que NO

**La FK pasa a NO ACTION** (`db/precios_no_se_desconectan_al_borrar_la_ficha.sql`),
que deja a las tres del mismo lado: guías R, compras armadas y precios. Y las
**dos puertas** —Eliminar y Cambiar el artículo— preguntan por los precios
antes de borrar, con un `ValueError` que la pantalla muestra como dato mal
pedido y no como un 500.

La guarda vive en **UNA** función (`_negar_si_tiene_precios`) que las dos
llaman. Escrita dos veces se separa, y la copia que quedara vieja seguiría
desconectando sin que nada avise — que es exactamente el modo de falla que
venía a cerrar.

**Lo que NO se tocó, y las dos razones son distintas:**

- **Las filas que ya quedaron huérfanas.** Rescatarlas es otra decisión y
  necesita el número. La verificación de la migración lo devuelve como
  `huerfanos_viejos`, al lado del resto.
- **`pedidos_renglones.ficha_id` sigue en SET NULL**, y es a propósito: un
  renglón viejo describe una entrega que ya pasó y nadie la consulta hacia
  atrás POR FICHA. Un precio sí, y eso es lo que Precios por Período vino a
  preguntar. **Buscar la otra copia es obligatorio; copiarle el arreglo,
  no** — mismo criterio que el Cotejo de vacíos.

### CERRADO: la migración corrió en las dos y no hubo nada que rescatar

Corrida el 14/09 en las DOS bases, con la fila de cada una al lado:

```
FRUTAMAX  guarda_no_action 1 · set_null 0 · huerfanos_viejos 0 · precios 75
PALMALA   guarda_no_action 1 · set_null 0 · huerfanos_viejos 0 · precios 86
```

**Cero huérfanos en las dos: nunca se desconectó un precio.** No hay
rescate que hacer, y la puerta quedó tapada antes de que pasara.

Y las dos columnas separadas hicieron el trabajo para el que estaban: un
*"¿existe algún FK?"* habría dado 1 con `set null` puesto y habría tapado
el caso. Es el corolario de contar POR NOMBRE, con una vuelta más — acá no
alcanzaba el nombre, porque el constraint existe en los dos estados y lo
que cambia es su COMPORTAMIENTO. Por eso son dos columnas y no una.

**El cero de huérfanos no dice que nadie haya borrado una ficha**: dice
que ninguna ficha borrada tenía precios. La diferencia no cambia la
decisión —cero desconectados es cero, se hayan borrado muchas o ninguna—
pero sí cambia cuánto sabemos de si la guarda va a molestar: si en este
sistema no se borran fichas, no se va a disparar nunca, y eso todavía no
está medido.

### La consulta que queda, y por qué su cero ya no informa

`db/fichas_borradas_y_precios_huerfanos.sql` cuenta las dos cosas —precios
huérfanos y fichas borradas, con su población al lado—. Contestó, y **con la FK
en NO ACTION su número ya no puede crecer**: correrla de nuevo devuelve cero por
construcción, que es el corolario 47 exacto. Eso va escrito EN SU ENCABEZADO, no
acá: el que la corra dentro de tres meses va a leer el archivo, no este
documento, y un cero prolijo sin esa advertencia se lee como una verificación
que se pasó.

La que sí sigue contestando algo es `..._verificacion.sql`, porque pregunta por
el estado del constraint y no por sus consecuencias.

**Y hay una asimetría que conviene tener en la cabeza al decidir**: esto es
viejo en el sistema y nuevo en las consecuencias. Mientras el precio solo se
usara para cotizar HOY, un precio huérfano no le faltaba a nadie. Con
facturación retroactiva, cada fila desconectada es una pregunta que el sistema
no puede contestar.

Y esa condición **ya no es hipotética**: el 14/09 se construyó
`/precios/vigencias`, que es la pantalla de facturar para atrás (desde el
15/09 se entra también por `/administracion/precios-por-periodo`, que es la
misma pantalla y la misma consulta). Un precio
huérfano no aparece ahí —la consulta pide `ficha_id IS NOT NULL`, porque sin
ficha no hay a qué producto pegarlo—, así que **esa ficha no aparece en el
listado en absoluto.**

(Esta línea decía que la ficha borrada "se ve como una que nunca tuvo
precio". Era cierto hasta esa misma tarde, cuando el dueño sacó de la
pantalla las fichas sin precio: antes salía marcada en amarillo y ahora no
sale. La diferencia importa para el que lea esto buscando el síntoma —
pasó de estar mal etiquetada a ser invisible.)

La PUERTA ya está cerrada, y el número que decidía si hacía falta un rescate
**se corrió el mismo día y dio CERO en las dos bases**: nunca se desconectó un
precio, así que no quedó ninguna ficha invisible por esto. Lo que sigue
valiendo es el síntoma descrito arriba, para el día que aparezca uno por otra
vía.

### Y el docstring de la ruta decía lo CONTRARIO que el de la función

`cambiar_articulo_de_ficha_ruta` afirmaba: *"Los precios ya negociados no
cambian: quedan cargados por artículo en precios_venta_historial"*. Falso —
cuelgan de la FICHA— y **cuatrocientas líneas más allá el docstring de la
función que esa ruta llama avisaba que DESCONECTA el historial**. Las dos
sobre la misma operación, diciendo lo opuesto, sin nombrarse.

No es el comentario que envejece del corolario 28, donde hay UNA afirmación
que dejó de ser cierta: acá había dos, y la que el lector encuentra depende
de por dónde entró. El que abre la ruta lee que no pasa nada; el que abre la
función lee que se pierde el historial. **Y la que tranquiliza es la que
está más cerca de la pantalla**, que es por donde se entra cuando se está
revisando si algo es seguro.

La misma frase afirmaba además que un artículo repetido *"lo corta el unique
de la tabla"*. Ese unique no existe desde
`db/permitir_varias_fichas_por_articulo.sql`. Dos afirmaciones falsas en un
párrafo de cuatro líneas, las dos envejecidas por cambios que no tocaron esa
ruta.

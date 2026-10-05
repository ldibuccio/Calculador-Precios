# Módulo: pérdidas (merma y pase a segunda)

Movido TAL CUAL desde CLAUDE.md el 03/10 (sin reescribir). Las reglas
vigentes, en corto, están en CLAUDE.md.

## TODO LO QUE SE TIRA O PASA A SEGUNDA ES PLATA PERDIDA (21/09)

Es del dueño y cierra el tema en una regla:

> **Todo lo que se tira o pasa a segunda es plata perdida.** Va a una cuenta de
> resultado negativo, no costea a nadie y no vuelve a ningún lote.
>
> - **Caja de Día armada** (merma o pase) → la pérdida son **los kilos que
>   tenía MÁS la caja**.
> - **Bultos sueltos** (merma o pase) → **solo los kilos**.
>
> Merma y pase **se costean igual**: es la misma pérdida con otro destino.

**Y por eso son DOS RENGLONES y UNA cuenta.** La cuenta es la misma —no hay
una fórmula para lo tirado y otra para lo de segunda— y se separan al MOSTRAR,
porque son dos hechos distintos del galpón y el que lee el resultado quiere
saber cuál pesa más. Juntarlas en un total sería perder eso; calcularlas con
dos reglas sería la regla escrita dos veces.

**Y desde el 25/09 hay un TERCER renglón, CAJAS ROTAS, que suma al mismo
total** (dueño: *"es plata perdida igual que la mercadería"*). No es la tercera
forma de la misma cuenta: son cajas VACÍAS dadas de baja en Cajas (origen
`merma` de `movimientos_envase`), sin artículo ni mercadería, así que su
desglose es por tipo de caja. Se valúan al costo de la caja vigente el día de
la rotura, con el MISMO fragmento que las otras cuentas de plata de cajas
(`_SQL_COSTO_DEL_ENVASE_A_LA_FECHA`).

### La mercadería sale del REJUEGO, y la preferencia es lo que la ata a la caja

Una caja de Día armada que se tira **no se costea contra el cajón más viejo
del artículo**: se costea contra **la caja armada**, que es lo que tiene
adentro. Eso no es una cuenta nueva — es una línea en `prioridad_de_lote`
(core/stock.py): una salida con ficha propia PREFIERE los
`TIPOS_LOTE_TRABAJADO`.

```
merma o pase CON ficha   -> prefiere ('reproceso', 'reingreso_rechazo')
merma, pase o ajuste SIN ficha -> de los SUELTOS: nunca las cajas de una ficha (30/09)
```

**Y la preferencia es por TIPO, no por la ficha exacta**, decisión del dueño:
*"si el pase fuera más preciso que el armado, habría dos reglas para la misma
pregunta. Y cuando me importe la caja exacta, elijo el lote a mano."* La
diferencia solo existe con cajas del mismo artículo armadas para dos clientes
a la vez, y en plata es mínima.

**LO QUE ESO COMPRA GRATIS: recostear lo que ya está cargado.** El costo de una
merma **no vive en ninguna columna** —el CHECK de `movimientos_stock` prohíbe
escribirlo (`tipo in ('reingreso_rechazo','stock_inicial') or costo_por_bulto
is null`)— y `atribuir_costos_fifo` lo rejuega en cada lectura. Así que cambiar
la prioridad recosteó toda la historia **sin una migración y sin tocar una
fila**. Es el corolario 80 por cuarta vez: con una cuenta derivada, completar o
corregir el dato de origen ES el arreglo.

**Y los dos tipos salen de UNA constante** (`TIPOS_CON_FICHA_PROPIA`), que vive
en `core/stock.py` y no en `app/db.py` porque `core` no puede importar de
`app`. La consulta del stock partido y la del extracto la leen del mismo lugar:
escrita dos veces, la copia que se separe deja una pantalla mostrando la merma
de una caja armada como si fuera suelta — que es el bug que esto vino a cerrar
y que estuvo vivo desde el 10/09.

### La pantalla: `/gerencia/perdidas`, y lo que NO se suma

Filtrada por fecha como Plata de cajas, con los dos renglones y el detalle por
artículo. Va a ser una línea del estado de resultados.

**Y dice en la pantalla que NO se suma con "Plata de cajas"**, porque las dos
muestran plata de la MISMA caja contestando dos preguntas distintas: allá se
cuenta por CLIENTE para poder reclamarla —e incluye los rechazos, que son del
cliente— y acá por DESTINO para el resultado. Sumar los dos totales la cuenta
dos veces, y el que lee "$X perdidos" sin esa frase al lado lo va a restar de
algún lado.

**Lo que no se pudo costear se MUESTRA**: `bultos_sin_costo` son los bultos que
salieron de un lote sin precio. Suman bultos y no suman pesos, y el total lo
dice. Un total que se los come en silencio es más chico y **se lee igual de
cerrado** — y este número va a un estado de resultados.

### Los DOS recortes, que es lo único fácil de romper acá

**El rejuego va desde el CORTE; la suma, solo sobre la VENTANA.** Son dos
recortes distintos a propósito: para saber a qué lote se le cobra una merma de
ayer hay que haber repartido todo lo anterior. Recortar el rejuego a la ventana
costearía contra los lotes equivocados **y devolvería un número plausible**.

Lo cuida `tests/test_perdidas_contra_la_base.py`, que corre contra Postgres con
el esquema real: el caso está armado para que el ORDEN decida —a un cajón le
quedan 5 porque una guía R anterior a la ventana se llevó los otros 5— y con
el rejuego recortado el número cambia. Desde el 30/09 los 8 sueltos se llevan
esos 5 y 3 quedan sin lote: la primera de la guía R es de la ficha, no suelta.
**Y una salida con UNA porción sin lote queda con `costo` None**
(`atribuir_costos_fifo`), así que ahí los 5 del cajón tampoco suman pesos. Es
la misma regla que la Rentabilidad Real, y no se tocó. Un fixture donde las entradas caen todas adentro de la ventana
da lo mismo con las dos reglas y no prueba nada.

### Y LA RENTABILIDAD REAL TIENE SU PROPIA COLUMNA (22/09)

La pantalla de Pérdidas dice cuánto se perdió. **Rentabilidad Real dice otra
cosa** —cuánto rindió cada artículo— y hasta el 22/09 el pase **no sumaba en
ninguna columna suya**: consumía mercadería del FIFO y no aparecía ni en
`costo_mermas`, ni en `segunda_bultos`, ni en `afuera_por_motivo`. La renta
salía inflada exactamente en lo que se pasó a segunda.

Son **tres compuertas y no una**, que es lo que costó encontrar: la misma
pregunta —*¿este artículo tuvo algo además de ventas?*— estaba escrita en
`articulos_con_salidas_stock` (la consulta), en `filas_con_algo` (la cuenta
pura) y en un `{% if %}` de la plantilla que decide si se dibuja el renglón
de chips. Arreglando las dos primeras, una berenjena que solo tuvo un pase
aparecía con su costo **y sin un solo chip que dijera por qué** — un artículo
con pérdida y sin nada que la nombre. Lo destapó un test de pantalla, no la
lectura.

**Y LA CAJA DE LA MERMA ENTRÓ HORAS DESPUÉS, el mismo 22/09, y lo que hay que
llevarse es POR QUÉ QUEDÓ AFUERA la primera vez.** La dejé afuera "como una
decisión del dueño", con este argumento: contarla movería `costo_mermas`, que
es un número que ya se lee todos los días. **Ya estaba decidida** —la regla
del 21/09, tres párrafos más arriba, dice *"caja de Día armada, merma o pase,
la pérdida son los kilos MÁS la caja"*— y él lo contestó en una línea: *"te
pregunta algo que ya contestaste"*.

O sea que no fue prudencia: fue **no leer la regla que este mismo archivo ya
tenía escrita sobre la cosa que estaba tocando**. Es el corolario 2 al revés
—buscar la otra copia antes de preguntar, no después de decidir— y la copia
estaba acá adentro, que es la que siempre se olvida.

**Y una consulta de más no es gratis, que es la parte contraintuitiva.**
Preguntar se siente siempre como el lado seguro, y tiene un costo que no se
ve: el dueño contesta lo que ya contestó, y la próxima vez que le pregunte
algo que de verdad no sabe, la pregunta llega con menos crédito. Antes de
subir una decisión, grepear acá la cosa que se está tocando.

**Lo que costó cerrarla: una línea de cuenta y CUATRO de desglose.** La
mercadería se abre en `costo_mermas_cruda` + `costo_mermas_trabajada`, y esas
dos **sumaban `costo_mermas`**. Con la caja adentro dejan de sumar — y la
tarjeta de la pantalla dice, textual, *"$X en total, abierto por lo que se
tiró"* arriba de dos renglones que ya no dan $X. El atajo era meter la caja en
la mitad "trabajada" (una caja armada es trabajo, suena bien) y **eso le hace
contestar otra pregunta que la de su nombre**: esa columna abre la
MERCADERÍA, y una caja no es mercadería. Va como un tercer término propio
—`cajas_mermadas_pesos`, su renglón en la tarjeta, su columna en el Excel y su
frase en el PDF— y los tres cierran.

**La señal general, y sirve sin este caso**: cuando un número gana un
sumando, ir a ver si ese número tiene un DESGLOSE publicado. Un total que
crece mientras su desglose no es una pantalla que se contradice a sí misma, y
el que la lee no tiene forma de saber cuál de los dos está mal. Lo cuida
`test_la_tarjeta_de_MERMAS_SIGUE_CERRANDO_con_la_caja_adentro`, que exige los
tres términos **y** que la mercadería sola NO alcance: sin esa segunda mitad,
el atajo de la columna "trabajada" pasa el test.

**Y las DOS pantallas la cuentan ahora, cada una a su manera**: Pérdidas la
tiene en el renglón "Se tiró" desde el 21/09, y Rentabilidad Real adentro de
`costo_mermas`. Siguen sin sumarse entre sí —lo dice la pantalla— porque
cuentan la misma caja contestando dos preguntas distintas: allá por DESTINO,
para el resultado; en Plata de cajas por CLIENTE, para poder reclamarla.

## En el hub: un botón, dos pestañas (04/10, dueño)

Gerencia tiene UN botón, **Pérdidas**, con dos pestañas: **Mercadería** (lo
tirado y lo pasado a segunda, `/gerencia/perdidas`) y **Plata de cajas**
(`/gerencia/cajas-perdidas`). La pestaña se llama "Plata de cajas" y no
"Cajas" por la misma razón que tenía el botón: adentro también está lo que se
gastó comprándolas. Siguen sin sumarse entre sí.


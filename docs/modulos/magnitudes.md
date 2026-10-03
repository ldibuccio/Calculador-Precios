# Módulo: kilos y conteo (las dos magnitudes)

Movido TAL CUAL desde CLAUDE.md el 03/10 (sin reescribir). Las reglas
vigentes, en corto, están en CLAUDE.md.

## `unidad_compra` y `unidad_venta` se suponían la MISMA unidad (CERRADO el 15/09)

Del 12/09, y **dejó de ser cierto el 15/09**: una compra declara ahora los
kilos SIEMPRE y —cuando el artículo tiene `unidad_conteo`— también un conteo,
y cada ficha divide por la suya. No hay conversión, y sigue sin haberla a
propósito. Ver **"La unidad de compra contra la de venta"**, más abajo.

Se deja escrito porque el supuesto vivió meses y el diagnóstico de abajo es
lo que llevó al modelo.

`_costear_compras` (app/costeo.py) divide `Σ(importe × cajones)` por
`Σ(cajones × contenido_por_cajon)` y llama al resultado **costo por unidad
de venta**. El numerador es plata y el denominador es contenido de compra,
así que esa igualdad solo vale si la unidad en que se compra y la unidad en
que se vende son la misma. **No hay ninguna conversión en ningún lado**:
`grep conversion` sobre `app/costeo.py` y `core/motor_costeo.py` no devuelve
nada, y lo único que se llama así es el ALIAS del cliente —**cómo llama
cada cliente a cada artículo**, nombre y código propios, para interpretar sus
pedidos por mail—. No convierte unidades.

(Ese alias vivía en una tabla `conversion_articulos_cliente`, que este
archivo nombraba en dos lugares hasta el 19/09. **Ya no existe**: se fusionó
dentro de `fichas_logistica`, en las columnas `nombre_cliente` /
`codigo_cliente`, y lo que todavía la nombra son tres comentarios que cuentan
eso. La conclusión no se mueve —sigue sin haber conversión de unidades— y el
nombre sí: el que lo grepee hoy no encuentra nada y no sabe si es porque no
existe o porque buscó mal. Lo destapó el barrido de tablas del corolario 60,
que la listó como muerta.)

Analizar Artículo hereda el supuesto y **eso es lo correcto**: lo peligroso
sería que esta pantalla usara una regla distinta a las demás, que es la
familia de la regla escrita dos veces.

## La unidad de compra contra la de venta: CERRADO con las DOS MAGNITUDES (15/09)

**Está construido, y todo lo que sigue es el camino hasta ahí.** Se deja
entero porque tres hipótesis se cayeron en el medio y la que quedó no se
parece a ninguna de ellas; lo que conviene leer primero es el final —**"EL
MODELO, como quedó"**, abajo de todo—, que es lo que el sistema hace hoy.

El resto de esta sección está escrito en el tiempo en que se pensó, y las
frases que decían "queda abierto" o "no se toca el modelo" **están corregidas
en su lugar**: se corrigieron el día que dejaron de ser ciertas, que fue el
mismo.

Del 15/09. Lo que sigue separa lo MEDIDO de lo que se supuso, porque
mezclarlos es cómo se decide con una hipótesis.

El hecho del negocio, dicho por el dueño: **kiwi, mango y palta se compran una
sola vez y van a dos clientes que los quieren en unidades distintas.** A Día
por unidad, a Coto por kilo. La compra es una; las unidades de venta, dos.

### Lo que eso le hizo a la alerta `unidades_que_difieren`

La alerta contaba pares donde `articulos.unidad_compra <> fichas.unidad_venta`,
y su docstring decía que era *"una configuración que queda mal hasta que
alguien la arregla"*. **Esa premisa era falsa**: si un artículo va a dos
clientes en dos unidades, los pares difieren porque el mundo es así, no
porque alguien haya cargado mal.

(Hoy la alerta pregunta otra cosa —si el ARTÍCULO puede declarar la unidad en
la que esa ficha vende— y el caso de las dos unidades ya no llega ahí. Ver
**EL MODELO, como quedó**.)

Y la consecuencia es peor que un aviso de más: **el link manda a alinear, y
alinear es exactamente lo que no hay que hacer.** Cambiar la ficha de Coto
para que diga "unidad" no arregla nada — hace que la ficha MIENTA sobre lo que
ese cliente compra, y apaga el aviso. **El arreglo que la alerta propone borra
la información que hace falta para arreglarlo de verdad.**

Es la familia del corolario 25 —un argumento válido defendiendo una premisa
que nadie midió— con un agravante que no habíamos visto: acá la premisa no
solo está mal, **está cableada en el destino del link**.

**HAY QUE IR A MIRAR EL KIWI DEL 12/09.** Está escrito arriba como
*"ARREGLADO: Lionel alineó la ficha desde la pantalla de Fichas"*, y en un
turno posterior el dueño dijo *"no había nada que alinear"* y *"puede estar
señalando algo que es correcto"*. Las dos cosas no pueden ser ciertas. Como
Kiwi estaba DORMIDO (cero compras en las dos bases), no hay plata mal
calculada en ningún caso — lo que puede haberse perdido es el dato de en qué
unidad lo compra ese cliente.

### Lo que SÍ está medido (código y esquema, este turno)

1. **El stock NO se toca.** `movimientos_stock.cantidad` está **en BULTOS**
   —lo dice el comment de la tabla— y lo mismo el armado y el FIFO. La unidad
   de compra/venta no entra en el stock, el cotejo, el remanente ni las guías
   R. **Todo el asunto es del camino de la PLATA**, y eso achica el problema
   más que cualquier otra cosa que se pueda decir de él.
2. **Todos los costos salen de UNA función**: `_costear_compras`
   (app/costeo.py), con cuatro llamadores. Calcula
   `plata / (cajones × contenido_por_cajon)` — o sea **el denominador está en
   unidad de COMPRA** — y devuelve eso bajo el nombre
   `costo_por_unidad_de_venta`. **El nombre ya afirma la conversión que nadie
   hace.**
3. **`contenido_caja` de la ficha NO es el puente.** Se usa para mostrar
   "por bulto", y su propio comentario dice que *"el resultado da igual por
   kilo — es un cociente, la unidad se cancela"*. Se multiplica por el costo
   Y por el precio, así que se cancela: lo que queda es
   `precio(venta) / costo(compra)`, con las unidades mezcladas y sin que nada
   avise.
4. **No hay ninguna conversión en ningún lado** — ya estaba escrito arriba y
   se volvió a verificar. Lo único que se llama así es el alias del cliente
   (nombre y código), que hoy vive en `fichas_logistica` y no convierte
   unidades.
5. **La alerta no puede distinguir los dos casos**, y por eso se escribió
   `db/kiwi_1_error_de_carga_o_dos_clientes.sql`: parte por ARTÍCULO entre el
   que tiene fichas que **no se ponen de acuerdo entre sí** (multiunidad:
   ninguna alineación lo arregla) y el que tiene **una sola** unidad de venta
   distinta de la de compra (ahí sí hay algo mal cargado). Probada contra
   `db/esquema_completo.sql` con los tres casos plantados y con el control de
   todo alineado: devuelve las dos respuestas, y la población queda en la
   fila para que el cero se pueda leer.

### Lo que NO está medido, y decide el diseño

**Dónde vive el factor de conversión**, y es una bifurcación con UN solo dato
que la resuelve — y no sale de una consulta, sale del galpón:

| | dónde va | cuándo es la correcta |
|---|---|---|
| **Dos números por COMPRA** (lo que propuso el dueño) | cada compra declara kilos Y unidades | si los kilos por unidad se mueven compra a compra |
| **Un número por ARTÍCULO** (kg por unidad) | una vez, en el artículo | si un mango pesa más o menos siempre lo mismo |

**La pregunta es si el kilaje POR UNIDAD es estable**, y hay una razón para
sospechar que sí que conviene tener escrita: **lo que ya sabemos que es
multiformato es la CAJA, no la FRUTA.** Está arriba, medido: el mango viene en
cajas de 40, de 12 y de 10 unidades, y por eso su `contenido_referencia` se
vació. Pero un mango pesa lo que pesa un mango — el formato que varía es el
envase, no el fruto. Si eso se confirma, **kg-por-unidad es exactamente el
número que el problema del multiformato NO toca**, y entonces alcanza con uno
por artículo en vez de dos por compra.

**ES UNA HIPÓTESIS Y SE PREGUNTA, NO SE MIDE.** Los datos no la pueden
contestar: `unidad_compra` es por ARTÍCULO, así que todas las compras de mango
están en la misma unidad y el cociente entre las dos nunca aparece en la base.
Es el mismo caso de Mango y Cherry multiformato, que se resolvió preguntando
en el galpón y no midiendo de nuevo.

**Y si la respuesta es "depende del día", la propuesta del dueño es la
correcta** y esta tabla no la contradice — dice cuándo cada una.

### MEDIDO Y DECIDIDO (15/09): el caso NO está cargado, y por eso se hicieron DOS cosas y no cuatro

`kiwi_1` en **Frutamax**: `arts_con_ficha 33 · arts_multiunidad 0 ·
arts_alineables 0 · pares_que_difieren 0 · pares_totales 34 · última compra
14/09`. **Cero en todo.** El hecho del negocio es real —el dueño lo describe
y pasa con mango, kiwi y palta— pero **no hay una sola ficha cargada que lo
necesite.**

Decisión del dueño **en ese momento**, y el criterio vale más que el caso: el
modelo de datos no se toca todavía. Ni las dos magnitudes por compra ni el
factor por artículo. Se construyeron solo las dos cosas que sirven el día que
cargue la ficha, y que hoy no le cuestan nada:

(**Esa decisión se dio vuelta el mismo día**, y no por un dato nuevo sino por
un criterio: *"si yo defino el caso, el caso es real"*. Ver abajo.)

1. **La alerta dejó de mandar a alinear.**
2. **El costeo se NIEGA** cuando las unidades no coinciden, en vez de dar un
   número mal.

**Y la razón de hacer la 1 aunque el caso no exista es del dueño**: *"el día
que yo cargue la ficha de un cliente que compra mango por kilo, esa alerta va
a saltar y me va a proponer romperla"*. Un aviso que propone destruir el dato
está mal aunque hoy dispare cero veces — y arreglarlo cuando dispara cero es
gratis.

Lo que quedaba abierto —decidir entre el factor y las dos magnitudes— **se
cerró el mismo día, y por el galpón**: ver abajo.

### Las cuentas que dependen de que la unidad sea UNA, enumeradas (15/09)

La unidad solo importa donde el `importe` se DIVIDE o se COMPARA contra un
contenido. Todo lo demás trabaja **por bulto**, y un bulto es un bulto
cualquiera sea su contenido. Son **tres** lugares:

1. **`_costear_compras`** (app/costeo.py), cuatro llamadores. Es todo el
   camino del costo, el precio sugerido y la utilidad.
2. **`_envases_por_unidad_ponderado`** (app/costeo.py), dos llamadores. **La
   que nadie iba a encontrar**, y está abajo.
3. **`calcular_costo_por_unidad_medida`** en la calculadora de Analizar
   Artículo (app/main.py).

Y lo que **NO** se toca, verificado y no supuesto:

- **El stock, el FIFO, el cotejo, el remanente y las guías R**: en BULTOS, lo
  dice el comment de `movimientos_stock`.
- **La Rentabilidad Real**: `costo_bulto` es `c.importe` DIRECTO (app/db.py),
  sin dividir por ningún contenido. El importe de una compra es por bulto.
- **La alerta de kilos faltantes**: compara `contenido_por_cajon` contra
  `contenido_por_cajon_real` — **las dos en la misma unidad**, sea cual sea.
  Es una comparación consigo misma y no le afecta nada de esto.

### LA QUE NADIE IBA A ENCONTRAR: el envase variable COMPARA las dos unidades

`_envases_por_unidad_ponderado` decide, para una ficha de envase variable, si
la mercadería sale descartable o en caja chica. Su docstring lo dice:

> *"si el contenido de ESE cajón es menor o igual al contenido de la ficha,
> es descartable (0 cajas); si es mayor, es caja chica"*

O sea `contenido_compra <= contenido_ficha`, donde el primero está en unidad
de COMPRA y el segundo en unidad de VENTA. **Con las unidades distintas, esa
comparación mezcla kilos con unidades** — 40 unidades contra 6 kilos— y de
ahí sale un costo de envase, no un cartel.

**Y el docstring nombra al MANGO como el caso de envase variable**, que es
exactamente el artículo del que salió todo esto.

Lo que hay que llevarse, más allá del caso: **buscando "el problema de las
unidades" nadie grepea la función de los ENVASES.** El grep que la encuentra
no es el del concepto ni el de la columna: es preguntarse **dónde se DIVIDE o
se COMPARA** un número de la compra contra uno de la ficha. Es el corolario
20 —enumerar el hecho y no la forma que uno espera— aplicado a una operación
en vez de a un campo.

### Las compras viejas NO se rompen, y las columnas YA ESTÁN

`compras` tiene `cantidad_kilos` **y** `cantidad_fraccion` (más sus gemelas
`_real`). Hoy guardan **UN** número en una de las dos cajas: `app/main.py`
calcula `total = cajones × contenido` y lo archiva según `unidad_compra`. Son
la misma magnitud etiquetada, no dos magnitudes.

Y el CHECK es `cantidad_kilos is not null OR cantidad_fraccion is not null`.
**Verificado contra el esquema real: la base YA ACEPTA las dos llenas.** Así
que del lado del guardado no hace falta ninguna migración.

Las compras viejas quedan con una magnitud y NULL en la otra, y **eso no está
roto: es verdadero e incompleto**, que son cosas distintas. (El docstring de
`listar_compras_para_costeo` decía que el costeo *"nunca lee
cantidad_kilos"*. Dejó de ser cierto el 15/09 y se corrigió en el mismo
commit: ahora es lo ÚNICO que lee, junto con `cantidad_fraccion`.)

**El límite de reusar esas columnas ES REAL Y SIGUE PUESTO**, y conviene
saberlo: `cantidad_fraccion` mete 'unidad' y 'cubeta' en la misma columna. Un
artículo que se venda a un cliente por unidad y a otro por cubeta **no entra
en dos columnas** — la compra guarda dos magnitudes, no tres.

Eso no es una deuda escondida: es exactamente lo que la alerta llama **"Ya
cuenta en otra unidad: no entra"**, dicho en la pantalla en vez de descubierto
seis meses después. Y medido antes de construir: `arts_unidad_y_cubeta 0` en
las dos bases.

### Y la ausencia de conversión era un OBJETIVO DE DISEÑO, no un olvido

`core/motor_costeo.calcular_costo_por_unidad_medida` lo dice en su primer
párrafo: la misma función saca el costo por kilo o por fracción *"**sin usar
ningún factor de conversión**"*.

Eso cambia cómo se discute la propuesta. No es tapar un agujero: es **dar de
baja una invariante que está escrita**. Puede estar bien darla de baja —el
mundo tiene artículos que se venden en dos unidades— pero el que lo haga tiene
que saber que está desarmando algo que alguien decidió, no arreglando un
descuido. Es el corolario 11 del dato de uso al revés: antes de sacar algo,
preguntarse de quién salió.

**Y NO SE DIO DE BAJA: el modelo de las dos magnitudes la CUMPLE.** Sigue sin
haber un solo factor de conversión en el sistema — lo que cambió es que ahora
la compra declara las dos magnitudes en vez de que alguien deduzca una de la
otra. La invariante se buscó para saber si había que romperla, y el resultado
fue encontrar el diseño que no la rompe. Ese orden es el que vale para la
próxima: **primero por qué está escrita, después si se puede.**

### La asimetría que decide entre las dos opciones

| | arregla el pasado | qué hay que saber |
|---|---|---|
| **Dos magnitudes por COMPRA** | **no** — solo desde el día que se empieza a cargar | el que compra tiene que pesar Y contar cada cajón |
| **Factor por ARTÍCULO** (kg por unidad) | **sí** — convierte el número que ya está guardado | si el kilaje por unidad es estable |

**Esa es la diferencia de fondo y no es de gusto**: un factor se aplica hacia
atrás sobre todo lo que ya está cargado; una segunda magnitud solo existe
desde que alguien la tipea. Para el costeo eso pesa menos de lo que parece
—sus ventanas son de 48 horas, 15 y 30 días, así que lo viejo se cae solo—
pero para cualquier lectura retroactiva (facturar para atrás, revisar un
margen del mes pasado) el factor es lo único que contesta.

**Y el factor tiene un borde conocido**: para 'unidad' es plausible que sea
estable (un mango pesa lo que pesa un mango); **para 'cubeta' es mucho más
flojo**, porque una cubeta es un recipiente y cuánto entra depende de cómo se
llene. Puede ser que el factor sirva para unidad↔kilo y no para cubeta↔kilo.

#### GANÓ LAS DOS MAGNITUDES, y el factor se construyó y se tiró el mismo día

La tabla de arriba está bien y le faltaba la fila que decidía. La puso el
dueño: **el kilaje por unidad NUNCA ES EXACTO.** Un mango no pesa 400 gramos,
pesa lo que pesa. Un factor deja números con coma que después no cierran
contra nada — es **un promedio disfrazado de dato**, que es exactamente el
corolario 20 (*un campo derivado no es un sustituto barato de uno declarado:
acierta en la mayoría y miente en un tercio*) visto antes de sufrirlo.

Mi argumento a favor del factor era el de la tabla —arregla el pasado— y la
frase que lo cerró vale como regla: *"tu argumento es razonable en teoría y
falso en la práctica"*. **Yo había medido que la CUENTA daba bien; nunca medí
que el INSUMO existiera.** Es el corolario 41 con otra ropa: una vuelta
completa que se ve como una lectura.

La migración del factor (`kilos_por_unidad`) llegó a correrse en las dos bases
y se revirtió con su propio `.sql`. Salió gratis porque **no tenía ni un
usuario**: es el corolario 29 al pie de la letra —un cambio que todavía no
tiene usuarios se escribe de forma que deshacerlo sea gratis—, y esta vez el
requisito que lo pedía no sobrevivió al día.

### LA TERCERA OPCIÓN, que es la más barata y no estaba en la mesa

**No convertir: NEGARSE A COSTEAR.** Cuando la unidad de venta de la ficha no
es la de compra del artículo, no mostrar costo ni precio sugerido para esa
ficha — decir que no se puede costear en esa unidad.

- **Dato nuevo: ninguno.** Y el camino ya existe: `costo_actual is None`
  ya devuelve None y la pantalla sabe mostrarlo.
- **Lo que gana**: convierte un número callado y mal en un hueco visible, que
  es la preferencia de toda esta casa.
- **Lo que cuesta**: esas fichas hoy muestran un número y pasarían a no
  mostrar ninguno. Eso es una pérdida **solo si el número era bueno**, y por
  construcción no lo es.
- **Y compone**: se hace ahora y no cierra ninguna puerta. El factor o la
  segunda magnitud se deciden después, con el dato del galpón.

Si los artículos son tres, **puede ser la solución entera**: con tres
artículos, el que pone el precio hace la cuenta de cabeza. Lo que no puede
hacer es darse cuenta de que el número que tiene adelante está mal.

**SE CONSTRUYÓ, Y SIGUE VIVA — pero pregunta otra cosa.** No fue la solución
entera: con el modelo de dos magnitudes la negativa ya no es "las unidades no
coinciden" sino **"el artículo no puede declarar esa unidad"**, que es un
conjunto mucho más chico. Y no era o una o la otra: la negativa es el piso que
queda cuando el modelo no alcanza, y las dos conviven.

Y hay una SEGUNDA negativa que no estaba prevista y es la que va a verse
todos los días al principio: **la compra vieja que declaró una sola
magnitud.** Ésa se apaga sola en cuanto entre una compra con las dos; la otra
no se apaga hasta que alguien toque el artículo. Van separadas en la fila
(`sin_conversion_de_unidad` y `compras_sin_la_magnitud`) justamente por eso —
juntarlas sería mandar a arreglar lo que se arregla solo.

### EL MODELO, como quedó (15/09)

**Una compra declara KILOS —siempre— y, cuando el artículo tiene
`unidad_conteo`, también un CONTEO (unidades o cubetas).** La misma caja de
mango se carga UNA vez con las dos, y cada ficha costea contra la que su
cliente compra. No hay conversión entre las dos y no la va a haber.

Las piezas, y el orden importa porque cada una tapa un agujero distinto:

1. **`articulos.unidad_conteo`** (columna nueva, migrada en las dos bases).
   Dice QUÉ es la segunda magnitud de ese artículo, o NULL si se compra solo
   por kilo. Se edita en `/compras/articulos`.
2. **`articulos.unidad_compra` quedó DEPRECADA**, y no se le cambió el
   significado — columna nueva y deprecar, que fue decisión del dueño y es la
   regla de siempre: ocho lugares escriben esa columna y re-signficarla es
   como se separan dos reglas. Lo único que sigue diciendo es **en qué unidad
   está expresado `compras.contenido_por_cajon`**.

   **Y ESE MISMO DÍA SE TERMINÓ DE SACAR, hasta donde se puede** — ver
   "Deprecar una columna que todavía DECIDE" más abajo. Salió de las dos
   pantallas de Artículos: no se pregunta, no se muestra, no se edita. Un
   artículo nuevo nace en 'kilo' y la edición directamente no la nombra en su
   UPDATE. Sigue leyéndose en tres lugares, y los tres son sobre lo VIEJO.
3. **El formulario pide LA OTRA magnitud por cajón**, en las cinco pantallas
   de carga, y es obligatoria cuando el artículo la declara. Un solo helper
   (`magnitudes_de_la_compra`) reparte entre `cantidad_kilos` y
   `cantidad_fraccion`, y un test parsea `app/main.py` para que el sexto
   camino no se olvide — el que falta, por definición, no nombra ninguna de
   las dos columnas (corolario 3).
4. **El reparto vive en `core/magnitudes.py`**, porque Depósito hace el
   MISMO con lo que pesa y cuenta. Escrito dos veces son dos reglas.
5. **La recepción pide las dos SOLO si la compra declaró las dos**, con la
   guarda donde se escribe. Pedirle a Depósito la que la compra no trajo es
   pedirle que invente; y aceptar una sola cuando declaró dos dejaría a dos
   fichas del mismo artículo costeando una contra lo pesado y otra contra lo
   estimado, en la misma compra y sin que nada se descuadre.
6. **`magnitud_de_la_ficha`** (app/costeo.py) es el único lugar donde se
   elige la unidad, y el valor VIAJA a las tres cuentas —el costo, los
   promedios por cajón y el costo de envase—. Que sea un valor y no tres
   lecturas es lo que impide que dos se pongan de acuerdo y la tercera no.

**NO SE MIGRÓ NINGUNA COMPRA VIEJA, y no se puede**: cada una declaró una
magnitud y la otra no existe en ningún lado. Deducirla sería el factor con
otro nombre. Quedan como están y la ficha que pida la otra **no se costea**,
con su propia cuenta al lado (`compras_sin_la_magnitud`) para que se
distinga de la negativa estructural. Se apaga sola con la primera compra
nueva.

**Lo único que se dedujo fue `unidad_conteo`**, copiado de `unidad_compra`
donde decía 'unidad' o 'cubeta'. Eso no es inventar un número: es copiar una
declaración que ya estaba. Verificado: `sin_copiar 0` en las dos bases.

### Deprecar una columna que todavía DECIDE: se saca de la MANO, no de la base

Del 15/09, y sale de una pregunta del dueño que vale más que el caso: *"no
quiero una columna deprecada que siga decidiendo"*.

**`unidad_compra` seguía decidiendo tres cosas**, todas escritas ese mismo
día por mí, y la respuesta honesta a "¿está deprecada?" era NO:

1. `repartir_magnitudes(unidad_compra, ...)` — en qué columna cae cada total.
2. `segunda_magnitud_del_articulo` — qué pide el campo nuevo del formulario.
3. `SUFIJOS_UNIDAD_COMPRA` — la `k` / la `u` que etiquetan
   `contenido_por_cajon` en trece plantillas.
4. Y desde el 15/09, `_negar_si_el_conteo_contradice_la_unidad_de_compra`
   (app/db.py): la guarda que impide declarar un conteo que no sea la unidad
   en que está escrita la historia del artículo. **Ésta no es una deuda de la
   deprecación: es lo que la columna pasó a hacer.** Un registro que dice en
   qué unidad está lo viejo sirve exactamente para negar lo que lo
   re-etiquetaría.
5. Y **en qué magnitud cae `contenido_referencia` al precargarse** — que es
   la que no estaba en esta lista y la encontró el dueño mirando la pantalla.
   Ver abajo.

**Y no se puede borrar**, por una razón que es la misma de todo este modelo:
los cuatro artículos que se compran contados tienen su historia de
`contenido_por_cajon` expresada en unidades. Sin la columna, esas compras
quedan etiquetadas en kilos — **sin mover un número y sin que nada avise**.
Convertirlas necesitaría el factor, que es justo lo que se descartó.

**LO QUE SÍ SE PUEDE, Y ES LO QUE SE HIZO: sacarla de la MANO.** Nadie la
elige, nadie la ve, nadie la edita. Un artículo nuevo nace en 'kilo' —el
formulario dejó de preguntar— y el UPDATE de la edición **no la nombra**,
para que tocarle el nombre a un artículo viejo no le pise la unidad de su
historia. La columna pasó de ser una decisión a ser un registro.

**La distinción que hay que llevarse**, porque "deprecada" se usa para las
dos cosas y son opuestas:

| | qué significa | qué se hace |
|---|---|---|
| **Deja de DECIDIR hacia adelante** | nadie la carga ni la elige | sacarla de la pantalla, y punto |
| **Deja de EXISTIR** | ninguna fila vieja depende de ella | recién ahí se borra |

Lo primero es gratis y se hace el día que se decide. **Lo segundo depende de
si lo viejo se puede releer sin ella**, y acá no se puede. Confundirlos es
cómo se borra una columna y se re-etiqueta la historia en silencio.

**Y el nulo pasó a SIGNIFICAR kilo**, que es lo que permitió sacar de las
cinco pantallas de carga la guarda de *"este artículo no tiene la unidad
configurada, cargala en /articulos"*. Con el campo fuera del formulario, ese
error mandaba a un callejón. Es seguro porque un artículo sin la columna
**no pudo tener ninguna compra** —la guarda no lo dejaba— así que no hay
nada que re-etiquetar. La regla general: **antes de darle un significado al
nulo, verificar que ninguna fila vieja lo tenga con otro.**

#### La columna que se agrega corre TODO lo que el CSS ubica por índice

El catálogo de Artículos se vuelve tarjeta en celular con reglas
`td:nth-child(N)`. El 14/09 le agregué una columna y no toqué el CSS: todo
lo que estaba a la derecha se corrió un lugar. La del conteo se puso el
rótulo `"ref. "` de la referencia —por eso el dueño vio una columna "ref."
diciendo "solo kilos"—, la referencia se fue al lugar del grupo, y **los
botones quedaron sin regla, en 28px**, abajo del mínimo tocable de este
proyecto. La suite entera en verde.

Es el corolario 3 en CSS: **cuando una estructura gana un campo hay que
grepear quién la CONSTRUYE.** Y acá el que la construye es una lista de
ÍNDICES que no nombra ninguna columna, así que ningún `grep` del nombre la
encuentra — es el caso más puro de "el que falta, por definición, no lo
nombra".

##### Y VOLVIO EN PYTHON EL 17/09, con la columna que se SACA en vez de la que se agrega

Mismo mecanismo, sin una línea de CSS. `_SQL_STOCK_DE_ENVASES` perdió la
pata `liberadas` y pasó de NUEVE columnas a OCHO. `stock_de_envases` se
actualizó a `f[7]`; **`crear_movimiento_envase` quedó leyendo `fila[8]`**, que
ya no existe. Reproducido con la fila real:

    IndexError: tuple index out of range

O sea que **todo guardado de un movimiento de cajas reventaba**, el CONTEO
INICIAL incluido — que es lo primero que alguien carga y lo único que hace
arrancar esa cuenta. Estuvo así desde el 17/09 y nadie lo pisó solo porque la
cuenta de cajas todavía no se había usado en ninguna de las dos bases.

**Las dos cosas que lo dejaron pasar, y ninguna es descuido:**

1. **Un lector por índice NO NOMBRA NINGUNA COLUMNA.** El `grep` que se hace
   al sacar un campo es el del campo, y `fila[8]` no lo contiene. Es
   exactamente lo del `nth-child`, en un lenguaje donde uno no lo espera.
2. **Ningún test podía verlo.** Los tres tests del formulario **parchean**
   `crear_movimiento_envase`, así que su cuerpo no lo ejercitaba nadie: la
   función estuvo rota sin un solo test en rojo. Es el corolario 9 corrido de
   lugar — allá el parche tapaba la línea rota, acá la saltea entera.

**El arreglo no es correr el índice**: es que las posiciones vivan en UN solo
lugar (`COLUMNAS_STOCK_DE_ENVASES`) y que los dos lectores lean POR NOMBRE.
Con eso, sacar o agregar una columna rompe un test en vez de una pantalla.

**La señal, y es barata**: cuando una consulta pierde o gana una columna,
`grep` de `fila[` y de `f[` en sus lectores, no del nombre de la columna. Y
si una función tiene todos sus tests parcheándola, no tiene ninguno.

Lo cuida ahora un test que cuenta los `<th>` de la tabla y los compara
contra los `nth-child` del CSS, en los dos sentidos (corolario 60): falla si
sobra una columna sin regla y si sobra una regla sin columna.

**Y de yapa, el mismo desajuste me hizo reportar mal.** Medí el botón de
28px, lo vi anterior al commit y escribí *"es anterior a esto"*. Era mío, de
ese commit. Es el corolario 18 exacto —al corregir se escribe rápido y con
la sensación de estar arreglando— y lo único que lo agarró fue ir a mirar el
CSS en vez de confiar en la memoria de qué había tocado.

### Un campo que significaba UNA cosa mientras hubo una sola magnitud

Del 15/09, y es el costo escondido del modelo de las dos magnitudes.

`articulos.contenido_referencia` se precarga en **un** campo de la compra
—`contenido_por_cajon`— y cuál de las dos magnitudes es ése lo decide
`unidad_compra`: kilos en casi todo el catálogo, el CONTEO en los que ya se
compraban contados. **La segunda magnitud (`segunda_por_cajon`) no se precarga
nunca**: el JS le toca la visibilidad, el `required` y el rótulo, y lo único
que le escribe es el vacío.

Mientras hubo UNA magnitud eso era exacto y el rótulo "Contenido de referencia
del cajón" alcanzaba. Con dos, **el mismo campo, con el mismo rótulo, significa
unidades en un artículo y kilos en el de al lado** — y lo que los separa es
`unidad_compra`, que el 15/09 sacamos de la pantalla a propósito.

**Hoy no hay ningún número mal puesto, y es por construcción**: `unidad_conteo`
se dedujo copiando `unidad_compra`, así que en los contados las dos columnas
dicen lo mismo y la referencia cae en el campo rotulado con su unidad.

**El riesgo es del caso que la pantalla nueva estrena**: un artículo que reciba
`unidad_conteo` de ahora en adelante queda en `unidad_compra = 'kilo'` —la
edición ni la nombra— así que su referencia cae en KILOS y su campo de conteo
no se precarga nunca. ~~Dos significados, ninguna señal.~~ **La señal existe
desde el 19/09 y la deuda es otra: ver "LA DEUDA NO ES 'DOS SIGNIFICADOS'"
más abajo, en esta misma sección.**

**Lo que se hizo, que es lo seguro**: el rótulo NOMBRA la magnitud
("¿Cuántos kilos suele traer un cajón?" / "¿Cuántas unidades..."). No cambia
un dato; hace visible cuál es.

**Lo que NO se hizo, y la consulta lo CERRÓ el 18/09**: clavar la referencia en
kilos —que es lo que la dejaría con un solo significado en todo el catálogo—
**re-etiqueta en silencio** la de los contados que ya tienen una cargada. Este
párrafo decía que se decidía con `db/referencia_1_en_que_magnitud_esta.sql` y
que si `contados_CON_referencia` daba 0 salía gratis. **No dio 0**:

```
FRUTAMAX  63 artículos · 4 contados · 4 CON referencia · 0 sin · en_kilos_con_conteo 0
PALMALA   38 artículos · 4 contados · 3 CON referencia · 1 sin · en_kilos_con_conteo 0
```

Son **SIETE referencias reales** expresadas en unidades o cubetas. Clavarlas en
kilos las re-etiqueta sin mover un número y sin que nada avise — exactamente lo
que este proyecto se negó a hacer al deprecar `unidad_compra`. **Cerrado: no se
clava, y la consulta ya no decide nada** (su cero era la condición, y la
condición no se cumplió).

**Y lo que se hizo en su lugar es lo contrario de clavar: que la magnitud viaje
CON el número.** El rótulo de la pantalla de EDICIÓN ya lo hacía desde el 15/09;
el que faltaba era **el listado del catálogo**, donde el Mango dice `ref. 40`
—unidades— tres renglones abajo del Tomate diciendo `ref. 16`, que son kilos. El
`ref.` que el CSS pone delante no distingue una de otra, y el listado es el que
se mira de corrido. Desde el 19/09 dicen `40u` y `16k`, con el mismo
`|sufijo_unidad` que `_magnitudes_del_cajon` ya usaba — **no una cuarta copia**
de `SUFIJOS_UNIDAD_COMPRA`, que es el momento exacto en que tres se convierten
en cuatro y el único en que se puede evitar gratis.

**Y EL NULO ES KILO, no "sin unidad"**, que es donde el sufijo se caía justo en
la mayoría del catálogo: lo dice el CHECK del esquema con su
`coalesce(unidad_compra, 'kilo')`, y desde el 15/09 un artículo nuevo nace así
porque el formulario dejó de preguntar la columna. Sin el `or "kilo"` de la
plantilla, **el caso más común sale pelado** — y es el que nadie va a ir a
mirar. Va con test propio, separado del de los dos contados, porque un sufijo
clavado en `k` pasa el de los contados a medias y éste entero.

**Y una segunda referencia para el conteo no va todavía**: el conteo es
justamente lo que cambia con el formato (el mango viene en 40, 12 y 10, que es
por lo que su referencia se vació). Precargar sirve con un valor DOMINANTE, y
ahí no lo hay — precargar mal es lo que invita a aceptar mal.

#### Y el filtro se llamaba `kilos` y lo único que hace es REDONDEAR

Del 19/09, y salió de este mismo trabajo. `_formatear_kilos` no sabe de qué
magnitud es el número que recibe: redondea a entero y saca la coma. **El nombre
afirmaba una magnitud que la función no tiene**, y era falso en CUATRO lugares
—ninguno un borde—:

    _magnitudes_del_cajon.html   lo llama sobre LAS DOS magnitudes de la misma compra
    fichas.html                  sobre el contenido en unidad de VENTA
    compra_form.html             sobre `contenido_por_cajon`
    articulos.html               sobre la referencia, que para siete está en unidades

Pasó a **`sin_decimales`**, que es lo único cierto de él: el nombre lleva el
alcance (corolario 8), y éste no tiene ninguno. La magnitud la pone quien llama,
con `sufijo_unidad` al lado.

**Y el test pregunta por la jerga que NO puede aparecer** además de por el
nombre bueno —`"kilos" not in templates.env.filters`, y un barrido de
`templates/` entero buscando `|kilos`—: afirmar el nombre nuevo pasa igual si
quedó un `|kilos` en una plantilla que nadie abrió. El barrido compara el
conjunto ENCONTRADO y no una lista escrita a mano (corolario 60): la próxima
plantilla no la va a recordar nadie.

**Y las dos mitades del renombre fallan de forma OPUESTA, que es por qué hacen
falta las dos.** El nombre de la función rompe un `import` de la suite
—`from app.main import _formatear_kilos`— y eso es un rojo que se lee. Un
`|kilos` olvidado en una plantilla **no rompe nada al importar**: Jinja falla al
RENDERIZAR, así que el único que lo ve es el operario, en la pantalla, el día
que entre. Por eso el barrido es un test y no un `grep` corrido una vez.

**Y el canario de la tanda fue ROMO y su número no decía nada.** Deshacer el
registro del filtro dejando nueve plantillas con `|sin_decimales` hizo caer
**210 tests**: no porque el barrido viera algo, sino porque nueve pantallas
dejaron de renderizar. El que sí contesta es el FINO —registrar los dos nombres
como alias, para que nada se rompa, y plantar UN `|kilos`—: ahí cae **1**, y es
el barrido. Es el corolario 35 con otra ropa: *¿el código quedó roto de la forma
que me importa, o quedó roto de otra?* — y un canario que rompe de MÁS contesta
que sí por el motivo equivocado, con un número grande que se lee como rigor.

#### LA DEUDA NO ES "DOS SIGNIFICADOS": ES "EL CONTEO NO TIENE REFERENCIA"

Del 19/09, y es del dueño: *"anotado con el nombre equivocado, el próximo que lo
lea va a buscar otra cosa"*.

Tres párrafos más arriba esto decía **"Dos significados, ninguna señal"**, y la
segunda mitad dejó de ser cierta: el rótulo de la edición (15/09) y el sufijo
del listado (19/09) SON la señal. Así que el que lea "dos significados" va a ir
a buscar una ambigüedad que ya no está, no la va a encontrar, y va a concluir
que la deuda se pagó.

**No se pagó, y es otra cosa.** El caso, en tres pasos:

1. un artículo nuevo nace con `unidad_compra` en NULL —el formulario dejó de
   preguntarla—, o sea en kilos;
2. `_negar_si_el_conteo_contradice_la_unidad_de_compra` **lo deja ponerle un
   conteo**: arranca con un `return` temprano cuando `unidad_compra` es falsy o
   `'kilo'`, y con razón, porque no hay historia que contradecir;
3. y entonces su `contenido_referencia` está en kilos y **su campo de CONTEO no
   se precarga nunca**: `segunda_por_cajon` no tiene de dónde salir, porque no
   existe una referencia para la segunda magnitud.

O sea que lo que falta no es desambiguar un campo: **es un segundo campo que no
existe.** Ese artículo va a declarar sus kilos con un número propuesto y sus
unidades desde cero, en cada compra, para siempre.

**Hoy son CERO casos**, medido: `en_kilos_con_conteo` dio 0 en las dos bases. Y
la razón para no construirlo **no es el cero** —un cero nunca es razón para
construir ni para no hacerlo (corolario 64)— sino la que ya está escrita arriba:
**el conteo es justamente lo que cambia con el formato**. El mango viene en 40,
12 y 10, que es por lo que su referencia se vació. Precargar sirve con un valor
DOMINANTE y ahí no lo hay, así que una segunda referencia estaría mal casi
siempre, y precargar mal es lo que invita a aceptar mal.

**El día que se retome, la pregunta es por el DOMINANTE y no por el cero**: si
aparece un artículo que se cuenta y viene siempre en el mismo formato, ése es el
caso que pide la columna. Un `count(distinct ...)` sobre sus compras lo contesta
antes de diseñar nada (corolario 23).

#### Y una cuenta que NO estaba en la lista y es la que nadie iba a buscar

`_envases_por_unidad_ponderado` compara lo que trae el cajón contra
`contenido_caja` de la ficha, que está en unidad de VENTA. Si los dos lados
no salen de la misma magnitud, de ahí sale **un costo de envase mal, no un
cartel**. Se encontró preguntando *dónde se DIVIDE o se COMPARA un número de
la compra contra uno de la ficha*, que es el grep que sirve — ni el del
concepto ni el de la columna.

Tiene **test propio, que no pasa por el costo**: la misma compra y la misma
ficha dan descartable o caja chica según la magnitud. El día que alguien
mueva esto, el costo va a seguir dando bien y eso es lo único que cae.

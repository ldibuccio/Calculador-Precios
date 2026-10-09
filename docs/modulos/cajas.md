# Módulo: cajas nuestras

Movido TAL CUAL desde CLAUDE.md el 03/10 (sin reescribir). Las reglas
vigentes, en corto, están en CLAUDE.md.

## EL MODELO DE LA CAJA, en tres renglones (17/09)

Es del dueño, y reemplaza todo lo que la sección de abajo fue pensando
durante seis días. Vale la pena leerlo primero: lo de abajo es el camino
hasta acá, con tres premisas que se cayeron en el medio.

    1. La caja de Día NO VUELVE NUNCA al stock. Por ninguna puerta.
    2. El stock solo SUBE por COMPRA — y por la guía R `en_origen`, que es
       una caja nuestra que vuelve llena de afuera. **Y desde el 17/09,
       por la cuenta con un COLEGA**: una caja que me presta entra al piso,
       y una que le devuelvo sale. Eso no le agrega ninguna pata al stock
       —`cantidad` ya significa el efecto sobre el piso— pero la frase "solo
       compra y en_origen" dejó de ser cierta y acá se corrige.
    3. Toda caja que se llena está PERDIDA, salvo la que vuelve rechazada y
       se remanda; y ésa ya estaba descontada, así que no se cuenta dos
       veces.

**Las cuatro puertas del rechazo, contra ese modelo.** Las cuatro salen del
mismo lugar —una caja que ya se descontó cuando la guía R la armó— y ninguna
le devuelve nada al stock:

| `destino_rechazo` | qué le pasa a la caja |
|---|---|
| `segunda` | se remite al Puesto en la caja en que volvió |
| `devolucion_proveedor` | se va con la mercadería que se devuelve |
| `reproceso` | la fruta pasa a cajón grande y la caja **se tira** |
| `stock` | vuelve llena, se rearma y sale de nuevo: **la misma caja** |

**Y POR ESO NO HAY NINGUNA REGLA QUE ESCRIBIR**, que es lo que lo vuelve un
modelo y no una lista: las tres primeras ya están restadas y no vuelven; la
cuarta está restada UNA vez y se reusa sin pasar por una guía R nueva.

**En la PLATA de la Rentabilidad Real, la cuarta sí lleva una regla** (dueño,
09/10): cada venta cobra su caja, así que la caja de un rechazo a `stock` se
cobraba en la venta rechazada Y en la que la reenvía. Desde el 09/10 el
rechazo a `stock` le devuelve la caja igual que la mercadería
(`core/costo_real.py`), y se cobra una sola vez. En septiembre de Frutamax
eran $349.450. La devolución al proveedor no la devuelve: la caja se va.

El neutro de la cuarta **no es una convención entre dos lugares** —que sería
el corolario 21, correcto hasta que alguien agregue un tercer camino— sino
una pared: un rechazo a `stock` deja un lote `reingreso_rechazo`, que es un
TIPO_LOTE_TRABAJADO, y `reproceso_toma` los tiene **PROHIBIDOS**
(core/stock.py). Medido con canario, no leído:

```
una GUIA R (reproceso_toma)  -> ['guia']                        <- no lo ve
un ARMADO                    -> ['reingreso_rechazo', 'guia']   <- lo prefiere
CANARIO (pared sacada)       -> ['reingreso_rechazo', 'guia']   <- la ve
```

Así que ninguna guía R puede consumir esa caja por segunda vez, y no hace
falta que nadie se acuerde de nada.

**Lo que costó llegar acá**: la `reproceso` llegó a tener columna propia
—`movimientos_stock.envase_id` con su `lleva_caja_nuestra` y tres CHECKs— y
una pata `liberadas` que le sumaba esa caja al stock, sobre la premisa de que
quedaba libre. Se sacaron el 17/09 (`db/envases_9_*.sql`). **Un camino que
nunca se va a recorrer es peor que no tenerlo: el próximo que lo lea va a
creer que falta cablearlo.**

Y una segunda razón, medida contra el esquema real: el código escribía
`envase_id` y **nunca** escribió `lleva_caja_nuestra`, así que con el CHECK
de coherencia puesto el reingreso a `reproceso` de toda ficha con envase
derivable **quedaba rechazado por la base**. Una pata que sumaba algo que no
pasa, apoyada en una columna que el código no podía escribir.

**Y ese CHECK ESTUVO PUESTO EN LAS DOS BASES**, confirmado por el dueño el
17/09: la tanda entera se corrió. Lo que lo dejó sin víctimas es que nadie
cruzó ese camino — `vuelven_a_cajon 0` sobre 27 reingresos en Frutamax—, así
que la pared existió un día y la desactivó el drop en vez del uso. Es el
corolario 75.

**Dónde vive el modelo**: arriba de todo en `core/envases.py`, que es el
módulo que las dos cuentas leen. Acá está para el que busque por el lado del
negocio; allá, para el que lo busque por el lado del código.

## La caja nuestra que se va y no vuelve: TRES puertas del mismo agujero

Del 11/09, y va acá porque es un hecho del negocio que el sistema no
registra, no un bug.

**MEDIDO Y RESUELTO EL 16/09, y la resolución no fue construir nada de lo
que esta sección proponía: fue ver que estas tres puertas NO son un agujero
de stock de cajas.** La caja se descuenta cuando se ARMA —en la guía R— así
que para cuando sale por cualquiera de las tres ya estaba descontada y no
vuelve. El stock lo refleja solo. Lo que estas tres sí son es un agujero de
COSTO DE ENVASE, que es otra pregunta.

**Y esa pregunta tiene planteo desde el 16/09.** El mecanismo: el costo de
envase YA se cobra, por unidad de PRIMERA vendida, y esa tasa supone que toda
caja que sale la paga una primera. **La población, en cambio, se midió mal dos
veces el mismo día** — primero la segunda del reproceso (que no lleva caja) y
después el total de la segunda— y lo que queda es mucho más chico y tiene otro
NOMBRE: **las cajas que se pierden en un RECHAZO.** Salen con una venta,
vuelven del súper y se van de nuevo sin una segunda venta atrás.

Ver `docs/el_costo_de_las_cajas_que_salen_sin_venta.md`, que está reescrito
con la corrección. **Ningún número de la primera versión se vuelve a citar.**

**Ese párrafo se declaró MEDIA VERDAD el mismo día y NO LO ERA** — se dijo que
la caja de la segunda salía sin descontarse nunca, se "arregló" sumando
`bultos_segunda`, y unas horas después el dueño corrigió el dato del galpón:
**la segunda de un reproceso queda en el cajón del proveedor y no lleva caja
nuestra.** Revertido; el detalle y el error de método están en el corolario 71.

**Y la puerta 2 quedó más chica de lo que esta sección dice.** No es "la
segunda que se remite al Puesto": es **solo la que vino de un RECHAZO** —el
súper devuelve mercadería que salió en caja nuestra y eso se anota como
segunda—. Esa caja **ya se descontó en la guía R que la armó**, así que el
stock está bien y nunca estuvo mal: lo que falta es su COSTO, que es la otra
pregunta.

La observación es de Lionel y dio vuelta el diagnóstico de esta sección
entera: **teníamos dos preguntas distintas debajo de la misma palabra.**

Cuando la mercadería sale en NUESTRA caja y después se va del circuito, esa
caja no vuelve. El sistema no lleva cuenta de eso por ninguna de las tres
puertas por las que pasa:

1. **El envase perdido de origen** — manzana, pera, arándano: salen en el
   cajón del proveedor y no se reprocesan nunca. Ahí no hay caja nuestra que
   perder, y por eso está bien que no se cuente (ver más arriba).
2. **La segunda que se remite al Puesto, y SOLO la que vino de un rechazo** —
   sale en la caja en la que está, que es nuestra porque ya lo era antes de
   volver del súper. La segunda que sale de reprocesar un cajón NO cuenta:
   queda en el envase del proveedor (16/09).
3. **La devolución al proveedor** (la que estrenó el cuarto destino): si la
   mercadería vuelve en el cajón del proveedor, ese cajón sale por el
   circuito de vacíos como cualquier otro y no hay nada que hacer. **Si
   vuelve en caja de Día, la caja se va con ella.**

   (Cuando esto se escribió, *"el circuito de vacíos"* era uno solo y no
   hacía falta decir cuál. Desde el 18/09 son DOS: acá es **el del
   DEPÓSITO** —el cajón es de un proveedor de Compras— y no el del puesto.
   Ver "HAY DOS CIRCUITOS DE VACÍOS Y NO SE TOCAN".)

Las tres son el mismo hecho —una caja nuestra deja el depósito sin pasar por
vacíos— y ninguna de las tres lo anota.

**Por qué no se construyó**, y es la parte que importa para el día que
alguien lo retome: el dueño dijo que hoy *"se acomoda solo"* por el circuito
de vacíos, y **eso no se midió**. Antes de agregar un campo hay que
contestar si la pérdida de cajas que se ve en los conteos de vacíos se
explica ENTERA por otra cosa, como pasó con el 15,6% "sin dato" del
Remanente (corolario 23): un número que se explica entero por un origen
conocido no es deuda.

Y la señal de que ya es hora está escrita en el corolario 31: **la segunda
vez que haya que escribir un `.sql` a mano para contar cajas que faltan, eso
deja de ser un incidente y es una función que falta.**

### La CUARTA puerta es de otra clase: es un PRÉSTAMO, no una pérdida

Del 11/09, y va aparte de las tres de arriba a propósito.

Cuando el puesto entrega la mercadería **ya armada en caja nuestra**, las
cajas vacías se le mandan el día anterior.

**CONSTRUIDO EL 16/09.** El párrafo decía que eso "no se registra en ningún
lado" y que `envases` era un catálogo "sin stock y sin movimientos": las dos
cosas dejaron de ser ciertas. Hoy la salida de vacías se declara como
`prestamo_al_puesto` en `movimientos_envase` (se llamaba `prestamo_salida`
hasta el 17/09: el préstamo a un COLEGA estrenó sus propios orígenes y los dos
nombres juntos en una lista se confundían), y la vuelta la registra sola la
guía R `en_origen` —la compra que llega armada en caja nuestra— que SUMA
donde las normales restan. Las dos puntas, como decía esta sección que
correspondía.

Lo que sigue en pie es el circuito de vacíos del PUESTO, que es de los
cajones DEL PROVEEDOR (`proveedores_puesto`) y está separado a propósito.

**La diferencia con las tres de arriba, y es la que importa:** en aquéllas
la caja se va CON mercadería y no vuelve — es una pérdida. Acá se va
**vacía y vuelve llena**: es un préstamo, y solo se vuelve pérdida el día
que no vuelve.

Eso cambia qué habría que medir, y por eso conviene que esté escrito antes
de que alguien lo retome: **no "cuántas se fueron" sino "cuántas no
volvieron".** Contar salidas de un préstamo da un número grande y
tranquilizadoramente inútil — la mayoría vuelve. El número que significa
algo es el que no cierra.

**Y la advertencia que queda VIVA, que es la parte que el sistema no puede
cerrar**: la salida de vacías la tiene que cargar alguien, y es un campo
cuya única consecuencia es que el aviso de reposición salte cuando
corresponde. Si no se carga, el stock queda alto y el aviso llega tarde —
sin que nada se descuadre. Es exactamente el perfil del campo que se deja
de llenar (ver "Un campo sin consecuencia se llena vacío"), así que
conviene mirar a las dos semanas si se está cargando. Si no se carga, la
salida no es insistir: es darle consecuencia o sacarlo.

## Una pantalla de EXISTENCIAS no es donde se cuelga todo lo que dice la misma palabra

Del 17/09, y también es del dueño: *"esto sirve para una cosa: saber cuántas
cajas tengo, a quién le presté y quién me debe. Nada más."*

`/compras/cajas` había juntado **tres preguntas distintas** debajo de la
palabra "cajas": cuántas hay (existencias), cuánto se gastó en comprarlas
(plata, 90 días) y cuánto se llevaron los rechazos (plata, 90 días). Ninguna
estaba mal calculada; las tres estaban en el mismo lugar por compartir un
sustantivo.

**Cómo se reconoce, y no hace falta que nadie se queje**: si dos bloques de una
pantalla **se miran en momentos distintos** —el stock antes de reponer, el
gasto al cerrar el mes— o **los mira gente distinta**, están juntos por el
nombre y no por el uso. La pregunta que lo separa es *¿esto lo abre la misma
persona en el mismo momento?*, y se contesta sin datos.

**Y las cuentas NO se borran cuando se saca el bloque**: `gasto_en_cajas` y
`cajas_perdidas` quedan enteras con sus tests, así que mudarlas a Gerencia es
cablear una pantalla y no reescribir dos cuentas —con sus ventanas, su
valuación al costo del día de la compra y su orden por plata—.

**Y se mudaron: las dos se ven en `/gerencia/cajas-perdidas`**, así que la
frase que decía que "sin un solo llamador son lo que se lee como 'no se usa'"
dejó de aplicarles. Lo que sí queda del párrafo es el mecanismo: mientras una
cuenta no tenga llamador, **el test que la nombra es la única señal de que
existe** — y eso vale para la próxima que se descuelgue de su pantalla.

(`cajas_perdidas_por_rechazo` se llama `cajas_perdidas` desde el 21/09: dejó
de contar solo los rechazos cuando entró la merma de cajas armadas, y un
nombre que nombra un subconjunto de lo que cuenta es el corolario 8 esperando
a que alguien lo cite mal.)

**Y los imports SÍ se sacan**, que es la mitad opuesta: un `from app.db import
gasto_en_cajas` que nada usa hace creer al próximo que lee la ruta que la
pantalla todavía lo muestra. La función se conserva donde vive; el cableado
muerto se corta.

## Cajas, todo en Administración (04/10, dueño)

El stock, la compra de cajas, los préstamos de vacías, las cuentas con
colegas, las correcciones y el aviso de reposición ya estaban en Cajas de
Administración (la MISMA pantalla que Compras). Desde el 04/10 se suma lo
que estaba en Comercial → Envases: **el alta de tipos de caja, su costo y la
baja**. El precio de las cajas lo carga Administración.

- **Va en su propia pantalla, "Tipos de caja y su costo"**
  (`/administracion/cajas/tipos`), que se abre desde adentro de Cajas. No
  va en la pantalla de Cajas porque esa es SOLO stock (la regla de arriba,
  del 17/09): el costo se mira en otro momento que las existencias.
- **Es la misma pantalla que Comercial tenía en `/envases`**, con el sector
  sacado del prefijo (corolario 63), y escribe **el mismo costo**
  (`costos_envases`, con su historial) que leen la rentabilidad y el costeo.
  Nada de la cuenta cambia.
- **Salió el botón Cajas de Compras** (PR de Compras, 04/10): sus
  direcciones viejas (`/compras/cajas`, sus movimientos y la cuenta de un
  colega) llevan con un 301 a las de Administración. La alerta de pocas cajas
  de Compras lleva a la pantalla de Alertas de Compras, que trae la caja, las
  que quedan y el umbral.
- **Salió Envases de Comercial** (PR de Comercial, 04/10): `/envases` lleva
  con un 301 a Tipos de caja y su costo, y sus formularios viejos ya no
  escriben (sin clave, cualquiera habría podido cambiar el costo). La pantalla
  vive SOLO en Administración.


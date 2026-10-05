# Módulo: pedidos, armado y segunda al cliente

Movido TAL CUAL desde CLAUDE.md el 03/10 (sin reescribir). Las reglas
vigentes, en corto, están en CLAUDE.md.

## EL RENGLÓN QUE EL SÚPER PIDE POR TELÉFONO (18/09)

El pedido llega por mail y el sistema lo lee. Después el súper llama: *"subime
a 8 lo de Banana, y agregame 5 de Lima que no te puse"*. Hasta el 18/09 la
única salida era **recargar el pedido entero**, y eso le cuesta el armado a
todo renglón cuya cantidad se haya movido — el traslado solo viaja donde
(artículo, sucursal, cantidad) son idénticos.

**Y LAS DOS MITADES ERAN LA MISMA COSA, que es lo que el planteo no veía.** El
pedido del dueño separaba "agregar un renglón" de "corregir una cantidad,
que eso lo puedo editar". **No se podía editar**: `pedidos_renglones.cantidad`
no tenía un solo UPDATE en todo el código —los seis que existen tocan
`ficha_id`, `armado_el`, `cantidad_armada`, `kilos_enviados`, `anulado_el` y
`controlado_el`— así que las dos iban por la misma puerta, que era recargar.

**Y el artículo "que no estaba" suele ESTAR.** El confirmar guarda los
renglones sin cantidad igual, con `cantidad = 0` y sin sucursal: *"nada del
mail se pierde"*. Si vino en la comanda en cero, el renglón existe y lo que
falta es darle cantidad — por eso el alta **rechaza** el artículo que ya está
en esa sucursal y manda a corregirlo. Dos renglones del mismo artículo y
sucursal cuentan la demanda dos veces en la Rentabilidad, que suma por fecha y
artículo.

### Las dos marcas, y por qué son dos columnas y no una

El dueño lo pidió así: *"quiero que se vea que ese renglón lo puse yo y no
vino en el mail, porque el día que algo no cierre contra la orden de compra
eso es lo primero que hay que mirar"*. `pedidos.origen` es del PEDIDO y no del
renglón, así que no alcanzaba.

| | qué guarda | qué pregunta contesta |
|---|---|---|
| `agregado_a_mano_el` | CUÁNDO | ¿este renglón vino en la comanda? |
| `cantidad_original` | el NÚMERO VIEJO | la OC dice 5 y el sistema 8, ¿por qué? |

**La segunda guarda un valor y no una hora a propósito.** Un timestamp dice
que alguien tocó; el número viejo dice qué decía la comanda, que es la
pregunta que de verdad aparece. Y se escribe **una sola vez**, con un
`COALESCE`: la segunda corrección pisaría el único dato que contesta.

### Y el renglón a mano SOBREVIVE A LA RECARGA — con el mail ganando el empate

Decisión del dueño: *"si el súper agregó un artículo por teléfono, eso es real
y no está en el mail. Que una recarga lo borre significa que al operario se le
desaparece mercadería que ya armó, sin que nada avise. Y el mail corregido no
lo va a traer nunca — si lo trajera, ya no sería un renglón agregado a mano"*.

**Cuando SÍ lo trae, gana el del mail**, y las cuatro razones:

1. **No son dos pedidos: es el mismo dicho dos veces** —pediste por teléfono y
   después llegó por mail—, así que conservar los dos duplica la demanda.
2. **La comanda es el documento contra el que se concilia la orden de compra.**
3. Es **más nueva**.
4. Y **la razón de existir del manual se apagó**: existía porque el mail no lo
   traía.

El empate se resuelve por **(artículo, sucursal)**, y el armado no se pierde:
el traslado que ya existía lo lleva del viejo al del mail cuando la cantidad
coincide. Si la cantidad cambió no viaja, que es lo que el sistema ya hace con
cualquier renglón cuyo número se movió.

**Y hay DOS detalles de orden que no son estilo:**

- **La copia va ANTES del traslado del armado.** Al revés, el renglón
  conservado aparece SIN armar — que es exactamente la mercadería que
  desaparece que esto vino a evitar.
- **La SUCURSAL se copia si el mail nuevo ya no la trae.** La pantalla de
  armar itera `pedidos_sucursales`: sin eso el renglón conservado existiría
  sin que nadie pueda verlo (corolario 68).

**Y la recarga AVISA cuántos va a conservar**, que fue la otra condición: sin
esa línea el total del pedido guardado no cuadra contra la comanda que se
acaba de pegar, y eso se lee como un error de lectura de la IA — la primera
sospecha razonable, y manda a mirar el lugar equivocado.

## SEGUNDA AL CLIENTE (23/09): las decisiones del dueño y dónde vive cada una

A un cliente que la acepta se le puede mandar mercadería de segunda **adentro
del mismo renglón**: misma ficha, mismo artículo, mismo precio, mismo remito.

| decisión | dónde vive |
|---|---|
| **Solo si el cliente la acepta** — un catering sí, Día no | `clientes.acepta_segunda`, default `false`; el campo de Armar Pedido sale solo con el tilde, y `marcar_renglon_armado` lo vuelve a mirar |
| **Nunca se elige sola** | el campo arranca cerrado y vacío; retildar sin decirla la limpia |
| **Cualquier segunda del artículo**, sin importar la caja | la guarda lee el pool con `_segunda_de_articulo`, la misma cuenta del Remanente |
| **Parte y parte**: 4 de segunda y 6 de primera | `pedidos_renglones.bultos_de_segunda`, una parte de lo armado |
| **Venta a precio lleno, costo cero** | el FIFO recibe SOLO la primera; la venta sale de los kilos del renglón entero |
| **Un rechazo vuelve a segunda con costo cero** | la segunda vuelve PRIMERO (`_segunda_que_vuelve`), no puede ir a `stock`, y su costo congelado se promedia a cero |

**LA REGLA ESCRITA UNA VEZ ES `_SQL_BULTOS_DE_PRIMERA`** (app/db.py): toda
consulta que resta del stock de primera la lee, y las únicas que leen el armado
ENTERO son las que miran lo que el CLIENTE recibió (el tope del rechazo y los
kilos de la devolución). Lo cuida un barrido que compara el conjunto ENCONTRADO
contra el DECIDIDO: la octava que aparezca con el armado entero falla hasta que
alguien decida de qué lado va.

**Y LA PARED DE LA BASE tiene CUATRO escritores que la conocen**:
`pedidos_renglones_segunda_solo_armado` exige armado, no anulado y no más que
lo armado. Marcar la escribe (con `cantidad_armada` EXPLÍCITA, para que
corregir lo pedido después no la deje arriba de lo armado), desmarcar y anular
la limpian, y la recarga la traslada con el armado. Un quinto que toque el
armado sin saberlo rebota contra la base — que es lo que la pared está para
hacer, y el motivo por el que los tests de esto corren contra Postgres.

## La Casilla de pedidos vive en Administración (04/10, dueño)

Estaba en Sistema, sin clave, y era el único botón de ese hub. El dueño
eligió "Todo a Administración": la configuración del buzón, la lista de mails
de pedido, el "revisar ahora" y el marcar como ignorado van en
**Administración → Pedidos → Casilla de pedidos**
(`/administracion/casilla-pedidos`), con la clave de Administración. Sus tres
alertas (mails sin confirmar, pedidos leídos con IA y casilla sin revisar)
pasaron a Administración. **Sistema desapareció**: `/sistema` y
`/sistema/casilla-pedidos` llevan con un 301 a la Casilla.

- **El circuito del mail sigue en Depósito, sin clave**
  (`/deposito/pedido/mails/{id}/revisar`, que se abre desde Pedidos de
  Depósito). Si el mail ya se procesó o no se puede leer, vuelve a **Pedidos
  de Depósito** con el aviso, y no a la Casilla: desde Depósito la Casilla
  sería una pared (corolario 56). El atrás de esa revisión también es Pedidos.
- Lo cuida `tests/test_gerencia_reordenada.py`.


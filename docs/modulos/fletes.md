# Fletes (dueño, 05/10)

Administración → Pedidos → **Fletes**: un botón con tres pestañas. Entra por
la del día.

## Las respuestas del dueño que deciden el diseño (05/10)

- Las sucursales de Día son tres: **VL Vicente López, BZ Burzaco y GR Garín**.
  El nombre de cada código vive en `clientes_sucursales` (por cliente; la
  migración carga las de "Día %", buscado por NOMBRE). Lo usan las pantallas
  de Fletes y el mensaje de WhatsApp. Pedidos y remitos siguen mostrando el
  código.
- **El precio del camión es el mismo vaya a la sucursal que vaya**: se carga
  por camión, con historial (`fleteros_camiones_precios`, vigente desde).
- **Un camión va a una sola sucursal** (ya decidido).

## Pestaña 1: Fleteros y camiones (`/administracion/fletes/fleteros`)

Fletero: nombre, teléfono, si sigue trabajando. Por fletero, sus tipos de
camión: nombre, cuántos pallets lleva, cuántos tiene (0 = ya no lo tiene) y
el precio del viaje con historial. Un camión nace con su primer precio. La
misma fecha cargada dos veces corrige el precio de esa fecha (error de
tipeo); los fletes ya confirmados no cambian, porque cada viaje guarda su
precio.

## Pestaña 2: Flete del día (`/administracion/fletes/dia`)

Fecha, cliente y UN fletero. Por sucursal, los pallets de Frutamax y de
Palmala; el sistema los suma. **Armar flete** propone, por sucursal, la
combinación MÁS BARATA de camiones que lleve sus pallets (`core/fletes.py`):

- dentro de la flota del fletero, sin pasarse de cuántos tiene de cada tipo,
  **contando los que ya salen ese día** en otros fletes suyos;
- **la flota se reparte entre las sucursales a la vez**, no de a una: si la
  primera se quedara con el único Grande, la segunda podría quedarse sin
  camión aunque repartido de otra forma alcance;
- empate de precio: **menos camiones**;
- con el precio vigente **el día del flete**; un camión sin precio ese día no
  se propone y se dice;
- una sucursal con 0 pallets no lleva camión; todo en 0 no se confirma.

**Flota insuficiente**: se dice, se dice en qué tipo se pasa, y la propuesta
es la más barata SIN el tope de la flota, para elegir a mano. A mano se puede
poner más camiones de los que tiene (para eso es elegir a mano); lo que no se
puede es que no entren los pallets.

Lo propuesto se edita antes de confirmar. Al confirmar se guarda, por
sucursal, los pallets de cada empresa, y por camión un viaje con el precio de
ese día y **la parte de cada empresa por pallets** (`repartir`: Frutamax se
redondea al centavo y Palmala es lo que queda; la base exige que sumen el
precio, `fletes_viajes_partes_suman`). Un flete por fecha + cliente +
fletero: el segundo rebota y pide corregir.

El **mensaje para WhatsApp** sale del flete confirmado ("Hola Juan, para el
lunes 06/10 necesito: Vicente López: 1 Grande + 1 Mediano (18 pallets).
Burzaco: 1 Mediano (8 pallets). Gracias."), entero a 313px (un bloque que
crece, no una caja con scroll) y con "Copiar para WhatsApp", que si el
celular no deja usar el portapapeles lo deja seleccionado.

### Corregir

- **El mismo día en que se confirmó**: desde Administración
  (`/administracion/fletes/{id}/corregir`).
- **Después: solo Gerencia** (`/gerencia/fletes/{id}/corregir`, con su
  clave). El link aparece en el flete cuando pasó el día.
- Cada corrección queda en `fletes_correcciones`: sector, cómo estaba y cómo
  quedó.
- **Un viaje pagado no se toca** (trigger `viaje_pagado_no_se_toca`, como un
  vale que salió): un flete con algún viaje pagado ya no se corrige.

## Pestaña 3: Cuenta del fletero (`/administracion/fletes/cuenta`)

Filtros: fletero (o todos) y fechas (sin fechas, el mes en curso). Un renglón
por viaje: fecha, sucursal, camión, precio, parte Frutamax, parte Palmala, y
"A pagar" o "Pagado el …". Totales: total, por empresa, a pagar y pagado. Se
tildan los viajes y se marcan pagados con la fecha de pago; uno ya pagado no
cambia de fecha. PDF y Excel con los mismos filtros y el filtro en el
encabezado (`core/exportar_fletes.py`).

## Rentabilidad Real: la línea "Flete"

La parte de ESTA empresa (en Frutamax, la de Frutamax) de los fletes del
cliente en el rango, **por el día y la sucursal del viaje**: resta de la
renta TOTAL y la utilidad se rehace; no se reparte por artículo, así que los
grupos no la tienen. Con un artículo o un grupo elegido no se resta, y la
pantalla, el PDF y el Excel lo dicen. Va en pantalla, PDF y Excel.

## Tablas (`db/fletes_1` a `fletes_4`, verificación `fletes_5`)

`clientes_sucursales`, `fleteros`, `fleteros_camiones`,
`fleteros_camiones_precios`, `fletes`, `fletes_sucursales`, `fletes_viajes`,
`fletes_correcciones`.

Tests: `tests/test_fletes.py` (el motor), `tests/test_fletes_contra_la_base.py`
(empate, flota insuficiente, una sola sucursal, pallets en cero, el reparto,
corregir, pagado) y `tests/test_fletes_pantallas.py` (las pantallas, las
descargas, 313px y Rentabilidad Real).

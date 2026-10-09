# Panel de control (Gerencia)

## El tablero y la regla de oro (dueño, 08/10)

Gerencia → **Panel de control** (primero en "Mirar"): un tablero de cuadros
grandes, cada uno con UN número que se lee de un pantallazo (390px), y al
tocarlo su detalle (`/gerencia/panel/<cuadro>`, una dirección escrita por
cuadro para que el humo las abra todas). Rutas en `app/main.py`
(`ver_panel_de_control`, `ver_detalle_del_panel`), resúmenes puros en
`core/panel_control.py`, tests en `tests/test_panel_control.py` y
`tests/test_panel_control_contra_la_base.py`.

**Ninguna cuenta es nueva.** Cada cuadro llama a la que ya usa su pantalla, y
el panel solo la resume. En orden:

1. **Rentabilidad por cliente** (todo cliente con ficha), un renglón por
   cliente con tres números:
   - **Mes** (del 1 a hoy) y **7 días** (los de Rentabilidad Real por
     defecto): la Rentabilidad Real (`_datos_rentabilidad_real`) con
     `solo_lo_vendido=True`: venta contra el costo de lo vendido a ESE
     cliente, **sin mermas ni pases a segunda** (mercadería y caja) **ni lo
     que pagó el puesto** — tienen sus cuadros. Lo del cliente sigue: sus
     rechazos y el flete. La pantalla de Rentabilidad Real no cambia.
   - **Ahora**: Márgenes por Artículo (`calcular_listado_para_negociar_precios`)
     con el MISMO promedio ponderado por lo facturado en 30 días que
     `recalcularPromedioPonderado` de `_cuadro_negociacion.html` (la copia en
     Python es `utilidad_de_ahora`; si se toca una, se toca la otra). Sin
     ventas en 30 días, el promedio simple de sus fichas, marcado "sin ventas".
   - El % es ganancia sobre el costo de la mercadería, igual que en
     Rentabilidad Real; el cuadro lo dice en chico, con "sin mermas ni
     segunda (ver sus cuadros)".
2. **Cajas**: `stock_de_envases` contra `envases.umbral_reposicion` con
   `hay_que_reponer` (la regla de la alerta). Sin umbral: "sin umbral", no
   rojo. Sin conteo inicial: "sin conteo". El número: cuántos tipos están bajos.
3. **Pedidos incompletos** (7 días, la ventana de la alerta): la MISMA cuenta
   que la alerta `pedidos_incompletos` (`listar_pedidos_incompletos` /
   `contar_pedidos_incompletos`). Desde el 08/10 **la cruz ("este no se arma")
   cuenta como incompleto**, en la alerta y en el panel, y un test compara los
   dos números. El detalle dice "Armado de menos", "No se armó" o "No se armó
   (cruz)". Los contadores por sucursal de las pantallas de Depósito miden el
   avance del armado y no son esta cuenta.
4. **Ingresos debajo del peso**: lo que faltó sobre lo declarado (cajones
   recibidos × contenido declarado por cajón), en el mes en curso y el
   anterior cerrado. **Cada unidad se suma sola y no se convierte nada**
   (`faltantes_por_unidad`): el número grande es el % de kilos; abajo, el de
   unidades y el de cubetas. Ninguna compra queda afuera. Sin umbral, y lo que
   pesó de más no compensa. Mismo recorte que la alerta de kilos faltantes
   (`_SQL_COMPRAS_PESADAS`: recibidas, pesadas, desde la primera foto).
5. **Vales a cobrar**: el total en cartera de `resumen_de_la_cartera` (ni
   cobrados ni aplicados a una liquidación).
6. **Vacíos en depósito**: `total_de_vacios_en_galpon` sobre
   `stock_de_vacios_deposito`, todas las marcas; detalle por proveedor y marca.
7. **Rechazos**: el mes anterior cerrado y el corriente a hoy.
   - En plata: los reingresos de todos los clientes con ficha
     (`devoluciones_vinculadas_por_rango`) valuados con `valor_por_bulto` (el
     costo del armado, o el precio de SU compra si se devolvió al proveedor:
     opción B), sobre la facturación a precio de lista de Márgenes
     (`facturacion_por_ficha`).
   - En bultos: los bultos rechazados sobre los bultos armados de las mismas
     entregas que esa facturación (`bultos_por_ficha`).
   - El rechazo cae en el mes en que se cargó el reingreso; la facturación, en
     el mes del pedido.
8. **Mermas**: el renglón de mermas de Pérdidas (`perdidas_por_periodo`):
   mercadería al costo de su lote más la caja si era caja armada; mes anterior
   contra mes en curso; detalle por artículo con bultos y costo.
9. **Segunda** (corregido el 08/10): lo que se perdió = el costo de TODA la
   mercadería que fue a segunda en el período menos TODO lo que pagó el
   puesto (`lotes_de_segunda` cobrados, por la fecha de la salida). El puesto
   paga la segunda junta, así que los dos lados miden lo mismo. El costo,
   abierto por origen (`resumen_de_segunda`):
   - **pase**: el renglón de segunda de Pérdidas (mercadería más caja);
   - **rechazo**: los "rechazos perdidos" de la Rentabilidad Real de todos los
     clientes con ficha (destino segunda o reproceso: el costo congelado del
     armado más la caja), por la fecha del reingreso; los que no tienen costo
     congelado se cuentan aparte;
   - **reproceso**: `COSTO_DE_LA_SEGUNDA_DEL_REPROCESO` = $0 (dueño, 08/10):
     su costo ya está en las cajas armadas (el del cajón entero viaja a la
     primera) y no se mueve; lo que paga el puesto por ella es recupero. El
     cuadro lo dice en chico: "reprocesos a $0: su costo ya está en las cajas
     armadas".
   Si lo cobrado supera al costo, el número sale como **"recuperado", en
   verde**, nunca como una pérdida negativa (también por artículo).
   Abajo, en chico, el costo por origen y lo cobrado; los lotes sin cobrar se
   cuentan aparte. La Rentabilidad Real no cambia.

La cuenta de Pérdidas rejuega el FIFO: el tablero la pide una sola vez por mes
y la comparten Mermas y Segunda (`_perdidas_de_los_dos_meses`). Lo mismo la
Rentabilidad Real de cada cliente y rango (`_real_sin_perdidas`), que la
comparten Rentabilidad y Segunda.

## Un número nunca se parte (dueño, 09/10)

En el celular "$8.379.000" salía "$8.379." arriba y "000" abajo. Los números
del tablero y de los detalles van marcados `data-ajustar` (sin quiebre:
`white-space: nowrap`) y su cuadro `data-ajustar-contenedor`;
`templates/_ajustar_numeros.html` le achica la letra a todos los números de un
cuadro juntos, en la misma proporción (Septiembre y Octubre quedan iguales),
hasta que entran enteros. Los cuadros del tablero van con `overflow-wrap:
break-word` y no `anywhere`: con `anywhere`, una tabla angosta (Rechazos,
Rentabilidad) parte el rótulo de al lado ("En plata") letra por letra en vez
de desbordar, y el script no se entera de que tiene que achicar. Debajo de
360px el título del cuadro va más chico, para que "INCOMPLETOS" entre en medio
cuadro. Test con montos de diez cifras a 390 y 313px, que mira también que
ninguna PALABRA se parta, en `tests/test_panel_numeros_enteros.py`.

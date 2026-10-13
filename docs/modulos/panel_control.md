# Panel de control (Gerencia)

## El tablero y la regla de oro (dueño, 08/10)

Gerencia → **Panel de control** (primero en "Mirar"): un tablero de trece cuadros
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
   cobrados ni aplicados a una liquidación). El detalle abre agrupado por
   proveedor, igual que Vales por proveedor (`docs/modulos/vales.md`).
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

10. **Rinde de guías R** (dueño, 13/10): los **últimos 7 días completos**
   (de hoy − 7 a ayer; hoy no). Por artículo que pasó por guías R y se vende
   por kilo, **Falta % = (kg que entraron − primera − segunda − merma) / kg
   que entraron**, con la cuenta del cartel "LOS KILOS NO DAN"
   (`core/kilos_guia_r.py`: cajones × kg pesados del cajón de SU compra;
   la primera con los kilos que se mandaron en los pedidos que salieron de
   esas cajas, o la ficha si no salieron —`kg_de_la_primera`—; segunda y merma en cajones × el cajón promedio de
   la guía), **POR GUÍA**, para que no la ensucie el reparto de compras
   (`guias_r_con_sus_kilos`, `rinde_por_articulo`). El número grande: cuántos
   artículos pasan el 5% (`UMBRAL_FALTA_PCT`), rojo si hay alguno. El
   detalle, de mayor a menor falta: kg que entraron, de primera, de segunda y
   merma, kg que faltan y %, guías y cuántas se guardaron con "Guardar
   igual". Las guías sin pesada no entran y se cuentan. Una foto de antes de
   este cuadro dice "Aparece en la próxima actualización". La pantalla
   Rendimientos de Comercial usa la misma cuenta. Tests:
   `tests/test_rinde_guias_r.py`.

   Corrido con la cuenta del sistema sobre Frutamax (conector de lectura,
   13/10, del 05/09 al 12/10: 615 guías, 507 con cuenta): Morrón Rojo 19,9%,
   Tomate Perita 7,7%, Zapallito 6,3%, Morrón Verde 2,3%. El dueño esperaba
   18, 6, 4 y 2: preguntado de dónde salen.

11. **Kilos al armar** (dueño, 13/10): los mismos **últimos 7 días
   completos**. Los renglones armados de fichas por kilo cuyos kilos por
   bulto no son los de la ficha (`kilos_distintos_de_la_ficha`: pedidos
   vigentes, renglones no anulados, por `armado_el` de Argentina). La
   diferencia es `kilos_enviados` menos bultos armados × `contenido_caja`.
   **En su envase no entra**: ahí los kilos los pone el que arma. El número
   grande es cuántos renglones, y abajo los kg de más (o de menos) en total.
   El detalle va por artículo, con renglones y kg. Al armar NO hay aviso
   (dueño, 13/10: confunde, y no hay errores de tipeo): el casillero de
   kilos por bulto sigue editable, sin cartel. Tests:
   `tests/test_kilos_al_armar.py`.

   Medido en Frutamax (conector de lectura, 13/10, del 05/09 al 12/10): de
   1.508 renglones por kilo armados, 20 con kilos distintos de la ficha,
   todos de más, 395 kg en total. Sin los que salieron en su envase, 18
   renglones y 355 kg. En la ventana del cuadro (del 06/10 al 12/10), 9
   renglones y 170 kg.

12. **Pérdida total** (dueño, 13/10): mes anterior cerrado y mes en curso a
   hoy. Es (merma + segunda + faltante), en plata al COSTO, sobre la
   facturación del mes a precio de lista, con el mismo criterio que Rechazos
   (`_facturacion_de_los_dos_meses`, que comparten). Las partes:
   - **Merma**: la del cuadro Mermas.
   - **Segunda**: la del cuadro Segunda (pases y rechazos a segunda, menos
     lo cobrado).
   - **Faltante**: por guía R, los kg que entraron menos primera (real),
     segunda y merma, la cuenta de "Rinde de guías R". Se valúa al costo del
     kilo que entró: el precio por cajón de SU compra (`compras.importe`)
     sobre lo que pesó el cajón (`faltante_en_plata`). Una guía que sobra
     resta, como en el rinde. Las guías sin pesada y las de una compra sin
     precio no entran, y se cuentan.

   `resumen_de_perdida_total`. El número grande de cada mes es el %, y abajo,
   en chico, el monto. El mes en curso va rojo si su % es mayor que el del
   anterior y verde si es menor. El detalle abre las tres partes en $ y %, y
   el top 5 de artículos que más plata pierden (`TOP_DE_LA_PERDIDA`). Una
   foto de antes de este cuadro dice "Aparece en la próxima actualización".
   Tests: `tests/test_perdida_total.py`.

   Medido el 13/10 en Frutamax (conector de lectura). Merma, segunda y
   facturación salen de la foto del sistema de las 09:43. El faltante sale
   de la cuenta por SQL, que da lo mismo que el rinde de esa foto (14
   artículos, 0 distintos, 1.479,8 kg). Usa la primera con la ficha, porque
   la primera real todavía no estaba en producción: con la real baja unos
   $0,32 millones por mes. Resultado:
   - Septiembre: $12,0 millones, 1,69% de $711,4 millones. Merma $0,32 M,
     segunda $8,75 M, faltante $2,94 M.
   - Octubre al 13: $14,8 millones, 4,80% de $308,9 millones. Merma $0,17 M,
     segunda $7,99 M, faltante $6,66 M.

   En septiembre las guías R sobran 223 kg netos y aun así faltan $2,94 M:
   faltan kilos caros (Morrón Rojo) y sobran kilos baratos.

13. **Cheques** (dueño, 13/10): el total en cartera y lo que **entra en 7
   días** (los que siguen en cartera con fecha de pago de hoy a 7 días; los
   entregados, canjeados o depositados no cuentan). Rojo si hay alguno por
   vencer, vencido o rechazado sin resolver. Es la misma cuenta que lo de
   arriba de la Cartera de cheques (`resumen_de_cheques`); detalle en
   `docs/modulos/cheques.md`.

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

## La foto: 06:00 y 14:00 (dueño, 09/10)

El tablero tardaba en abrir porque calculaba todos los cuadros en cada
entrada. Ahora se calcula a las **06:00 y a las 14:00** (hora Argentina) y
al entrar se muestra **lo último calculado**, de `panel_fotos`
(db/panel_foto_1_tabla.sql). Arriba dice "Actualizado hoy a las 14:00", y el
botón **"Actualizar ahora"** (`POST /gerencia/panel/actualizar`) recalcula en
el momento y deja la foto nueva para todos. **Los detalles de cada cuadro se
siguen calculando al tocarlos.** La lógica pura (turnos, el JSON con fechas,
lo que se dice arriba) está en `core/panel_foto.py`.

- **Lo dispara el mismo bucle que las Alertas** (`_bucle_revision_casillas`,
  el que mira el reloj cada minuto dentro de la aplicación): si el turno
  vigente (el último de las 06:00 o las 14:00 que ya pasó) no se intentó, se
  calcula (`_actualizar_panel_si_toca`). Si la aplicación estuvo caída a las
  14:00, lo calcula cuando vuelve.
- **Un turno se intenta UNA vez** (`panel_fotos_un_intento_por_turno`). Si
  falla, queda anotado con su error y el tablero muestra la última foto
  buena con el aviso "No se pudo actualizar a las 14:00". No se reintenta
  solo: para eso está el botón. Un error del botón no se anota: se le
  muestra al que lo tocó.
- Sin ninguna foto buena (la primera vez), el tablero la calcula al entrar.
- Se guardan las últimas 30 fotos (`FOTOS_DEL_PANEL_QUE_SE_GUARDAN`), y la
  última buena no se borra nunca.
- Un candado propio (`candado_panel`) evita que el bucle y el botón
  calculen a la vez.

Lo cuida `tests/test_panel_foto.py`.

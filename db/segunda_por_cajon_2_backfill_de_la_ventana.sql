update compras c
   set segunda_por_cajon_real = (case when coalesce(a.unidad_compra, 'kilo') = 'kilo'
                                      then c.cantidad_fraccion_real else c.cantidad_kilos_real end)
                                / c.cantidad_cajones_real
  from articulos a
 where a.id = c.articulo_id
   and c.segunda_por_cajon_real is null
   and c.cantidad_cajones_real > 0
   and (case when coalesce(a.unidad_compra, 'kilo') = 'kilo'
             then c.cantidad_fraccion_real else c.cantidad_kilos_real end) is not null;

-- CORRER DESPUES DEL DEPLOY, una sola vez, y despues nunca mas hace falta.
--
-- LA VENTANA: entre que corrio `segunda_por_cajon_1` y que el codigo que
-- escribe la columna quedo desplegado, toda recepcion escribio los TOTALES
-- reales y dejo `segunda_por_cajon_real` en NULL. Eso se ve en la pantalla
-- exactamente igual que una compra que no declaro la segunda —un hueco
-- legitimo— asi que nadie lo iria a buscar.
--
-- ES IDEMPOTENTE POR EL `WHERE` y no por una guarda: solo toca las filas que
-- tienen la columna en NULL y el total cargado. Correrlo de nuevo no mueve
-- nada, y NO pisa un hueco verdadero: una compra que declaro una sola
-- magnitud tiene el total en NULL y queda afuera sola.
--
-- Y NO LLEVA `if not exists`: eso protege ESTRUCTURA. Acá lo que se toca es
-- CONTENIDO, y una guarda que saltee el bloque en silencio es justo lo que
-- dejaria la ventana sin tapar.
--
-- La estimada no hace falta: `segunda_por_cajon_1` ya la backfilleo y nadie
-- pudo cargar una compra nueva sin ella (el parametro no tiene default).

-- ============================================================================
-- CORRECCIÓN DE DATOS (una sola vez): retiros pendientes de compras que
-- ya pasaron por Depósito
-- ============================================================================
-- Si Depósito recepcionó o rechazó una compra, la mercadería llegó hasta
-- ahí: el retiro del puesto es un hecho, aunque Logística nunca haya
-- tildado el botón. El código lo marca solo desde que existe el
-- auto-retiro (_auto_retirar_si_corresponde, 2026-08-19) — y el rechazo
-- parcial lo hereda porque pasa por recepcionar_compra. Las filas que
-- este UPDATE arregla son las procesadas ANTES de esa fecha, que
-- quedaron con el retiro colgado para siempre.
--
-- NO toca:
--   - estado 'no_ingresado': la mercadería nunca llegó, no hay base para
--     asumir que se retiró (mismo criterio que el código).
--   - estado_retiro 'cancelado': contradicción real (mercadería que
--     supuestamente no salió del puesto pero llegó a Depósito) — se deja
--     a la vista para revisar a mano, el código tampoco la pisa.
--
-- Correr en las DOS bases (Frutamax y Palmala) y marcar en APLICADO.md.
-- El código NO depende de esto: es limpieza de datos históricos.
-- ============================================================================

-- 1) DIAGNÓSTICO — correr ANTES, para ver cuántas hay y cuáles son:
-- select c.id, c.fecha_operacion, c.estado, c.estado_retiro, c.tipo_retiro,
--        c.procesada_el, p.nombre as proveedor, a.nombre as articulo
-- from compras c
-- join proveedores p on p.id = c.proveedor_id
-- join articulos a on a.id = c.articulo_id
-- where c.estado in ('recepcionado', 'rechazado')
--   and c.estado_retiro is distinct from 'retirado'
--   and c.estado_retiro is distinct from 'cancelado'
-- order by c.fecha_operacion;

-- 2) CORRECCIÓN — el retiro queda fechado cuando Depósito la procesó
--    (procesada_el), que es el momento en que quedó probado que llegó:
update compras
set estado_retiro = 'retirado',
    retiro_procesado_el = coalesce(procesada_el, now()),
    retiro_origen = 'deposito'
where estado in ('recepcionado', 'rechazado')
  and estado_retiro is distinct from 'retirado'
  and estado_retiro is distinct from 'cancelado';

-- 3) VERIFICACIÓN — correr DESPUÉS, tiene que devolver 0:
-- select count(*) from compras
-- where estado in ('recepcionado', 'rechazado')
--   and estado_retiro is distinct from 'retirado'
--   and estado_retiro is distinct from 'cancelado';

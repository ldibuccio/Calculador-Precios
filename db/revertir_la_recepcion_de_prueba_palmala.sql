-- Deshacer la recepción que dejó la prueba de la foto de balanza (08/09,
-- Palmala). Correr SOLO si el paso 1 de borrar_la_foto_de_prueba_de_balanza
-- devolvió estado_de_la_compra = 'recepcionado'.
--
-- POR QUÉ NO VA UN MOVIMIENTO COMPENSATORIO. La entrada de stock no es una
-- fila en movimientos_stock: es LA COMPRA MISMA. El stock la lee así
-- (_SQL_SUMAS_STOCK, app/db.py):
--     SELECT c.articulo_id, SUM(c.cantidad_cajones_real) ...
--     FROM compras c WHERE c.estado = 'recepcionado'
-- Así que un ajuste en menos dejaría DOS registros falsos que se cancelan
-- —un ingreso que no pasó y un ajuste que tampoco— y las dos pantallas que
-- los muestren por separado van a mentir. Devolver la compra a 'pendiente'
-- borra la entrada por completo y no deja rastro que después haya que
-- explicar.

-- ===== PASO A — qué hay, y de qué cuelga (solo lectura) =====
select c.id, a.nombre as articulo, c.fecha_operacion,
       c.estado, c.procesada_el, c.cantidad_cajones_real,
       c.estado_retiro, c.retiro_origen, c.retiro_procesado_el,
       (select count(*) from reprocesos_consumos rc
          join reprocesos rp on rp.id = rc.reproceso_id
         where rc.compra_id = c.id and rp.anulado_el is null) as guias_r_que_lo_consumieron,
       (select count(*) from pedidos_renglones_lotes_elegidos le
          join pedidos_renglones r on r.id = le.renglon_id
         where le.lote_tipo = 'guia' and le.lote_origen_id = c.id
           and r.anulado_el is null)                          as armados_que_lo_eligieron
from compras c
join articulos a on a.id = c.articulo_id
where c.estado = 'recepcionado'
  and c.procesada_el >= ((date '2026-09-08')::timestamp AT TIME ZONE 'America/Argentina/Buenos_Aires')
order by c.procesada_el;

-- ===== PASO B — revertirla. UN solo do $$: o pasa todo o no pasa nada =====
-- El id se copia del paso A. Las guardas van todas ADENTRO del bloque:
-- sueltas, el editor confirma cada una por su cuenta y una que falle deja
-- lo anterior escrito.
do $$
declare
  compra bigint := 0;   -- <<< PEGAR ACA EL id DEL PASO A
  fila compras%rowtype;
  consumida int;
  elegida int;
begin
  -- SELECT sin agregado: con count(*), 'not found' no salta nunca.
  select * into fila from compras where id = compra;
  if not found then
    raise exception 'No existe la compra %: revisa el id del paso A', compra;
  end if;
  if fila.estado is distinct from 'recepcionado' then
    raise exception 'La compra % no esta recepcionada (esta %): no hay nada que revertir',
      compra, coalesce(fila.estado, 'sin estado');
  end if;

  select count(*) into consumida from reprocesos_consumos rc
    join reprocesos rp on rp.id = rc.reproceso_id
   where rc.compra_id = compra and rp.anulado_el is null;
  -- lote_tipo='guia' no es decorativo: lote_origen_id es polimorfico y
  -- sin el tipo, un reproceso con el mismo id contaria como esta compra.
  select count(*) into elegida from pedidos_renglones_lotes_elegidos le
    join pedidos_renglones r on r.id = le.renglon_id
   where le.lote_tipo = 'guia' and le.lote_origen_id = compra
     and r.anulado_el is null;
  if consumida > 0 or elegida > 0 then
    raise exception 'El lote de la compra % ya se uso (% guias R, % armados): no se toca',
      compra, consumida, elegida;
  end if;

  update compras
     set estado = 'pendiente',
         cantidad_cajones_real = null, contenido_por_cajon_real = null,
         cantidad_kilos_real = null, cantidad_fraccion_real = null,
         cantidad_cajones_rechazada = null, motivo_rechazo = null,
         procesada_el = null,
         -- El retiro se deshace SOLO si lo puso la recepcion
         -- (_auto_retirar_si_corresponde deja origen 'deposito'). Si lo
         -- marco Logistica, no es de la prueba y no se pisa.
         estado_retiro = case when retiro_origen = 'deposito' then 'pendiente' else estado_retiro end,
         retiro_origen = case when retiro_origen = 'deposito' then null else retiro_origen end,
         retiro_procesado_el = case when retiro_origen = 'deposito' then null else retiro_procesado_el end
   where id = compra;
end $$;

-- ===== PASO C — verificación (conteos, una fila, con testigo) =====
select (select count(*) from compras where estado = 'recepcionado')             as recepcionadas,
       (select count(*) from compras where estado = 'pendiente')                as pendientes,
       (select count(*) from fotos_recepcion)                                   as fotos_de_balanza,
       (select max(fecha_operacion) from compras where estado = 'recepcionado') as ultima_recepcion;

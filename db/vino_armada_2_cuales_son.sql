-- LAS COMPRAS QUE HOY MUESTRAN "Vino armada" EN BUSCAR COMPRAS, una por fila,
-- con qué le va a decir la pantalla de destino cuando se lo aprete.
--
-- Se corre DESPUÉS de vino_armada_1, que da los conteos: acá una lista vacía
-- y una consulta que no corrió se ven igual.
with c0 as (select fecha from corte_modelo where id = 1)
select c.id, c.fecha_operacion, a.nombre as articulo, p.nombre as proveedor,
       coalesce(c.cantidad_cajones_real, c.cantidad_cajones) as bultos,
       cons.bultos                                           as ya_consumido,
       case
         when c.procesada_el is null then 'sin fecha de lote: la pantalla la frena'
         when (c.procesada_el at time zone 'America/Argentina/Buenos_Aires')::date
              <= (select fecha from c0) then 'anterior al corte: la pantalla la frena'
         when cons.bultos >= coalesce(c.cantidad_cajones_real, c.cantidad_cajones)
              then 'su lote YA se consumio entero en una guia R: el freno la rebota'
         when cons.bultos > 0
              then 'su lote esta consumido a medias: el freno decide'
         else 'se puede marcar'
       end                                                   as que_va_a_pasar,
       (select string_agg(r.id::text || ' (' || r.tipo || ', ' ||
                          to_char(r.fecha_operacion, 'DD/MM') || ')', ', ')
          from reprocesos_consumos rc
          join reprocesos r on r.id = rc.reproceso_id
         where rc.origen = 'compra' and rc.compra_id = c.id
           and r.anulado_el is null)                         as guias_r_de_su_lote
from compras c
join articulos a on a.id = c.articulo_id
join proveedores p on p.id = c.proveedor_id
left join lateral (
  select coalesce(sum(rc.bultos), 0) as bultos
    from reprocesos_consumos rc
    join reprocesos r on r.id = rc.reproceso_id
   where rc.origen = 'compra' and rc.compra_id = c.id and r.anulado_el is null
) cons on true
where c.estado = 'recepcionado' and c.ficha_en_origen_id is null
order by c.fecha_operacion desc, c.id desc;

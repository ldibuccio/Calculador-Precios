-- ############################################################################
-- EL CHERRY POR SUS DOS CAMINOS, DESDE EL CORTE. Solo lectura.
--
-- Camino 1: cajón grande que el depósito reprocesa -> caja chica NUESTRA, que
--           se compra y va al costo.
-- Camino 2: caja descartable ya armada -> sale tal cual, el envase vino
--           adentro de la compra.
--
-- El dato que decide todo es `envase_variable` de la ficha: con TRUE el costeo
-- YA distingue los dos caminos compra por compra (ver
-- _envases_por_unidad_ponderado en app/costeo.py: si el contenido de ESE cajón
-- es <= al de la ficha, es descartable y cuenta 0 cajas). Con FALSE, todo se
-- costea con el cartón, venga como venga.
--
-- Las VENTAS no se pueden partir por camino: el FIFO reparte en Python, no en
-- SQL. Lo que sí se mide es la MEZCLA DE ENTRADAS, que es exactamente lo que
-- el costeo pondera.
-- ############################################################################
with corte as (select fecha from corte_modelo where id = 1),
art as (select id from articulos where nombre ilike '%cherry%' limit 1),
fi as (select f.*, e.nombre envase from fichas_logistica f
       left join envases e on e.id = f.envase_id, art
       where f.articulo_id = art.id limit 1),
vig as (select distinct on (cliente_id, fecha_operacion) id
        from pedidos where anulado_el is null
        order by cliente_id, fecha_operacion, creado_en desc),
com as (select c.cantidad_cajones_real cajones, c.contenido_por_cajon cont
        from compras c, art, corte
        where c.articulo_id = art.id and c.estado = 'recepcionado'
          and coalesce((c.procesada_el at time zone 'America/Argentina/Buenos_Aires')::date,
                       c.fecha_operacion) > corte.fecha)
select * from (
  select 1 orden, 'ficha: envase_variable' dato, (select envase_variable::text from fi) valor
  union all select 2, 'ficha: contenido y envase',
    (select contenido_caja || ' ' || unidad_venta || ' · ' || coalesce(envase, 'envase perdido') from fi)
  union all select 3, 'CAJAS VENDIDAS desde el corte',
    coalesce((select sum(coalesce(r.cantidad_armada, r.cantidad))::text
              from pedidos_renglones r join vig v on v.id = r.pedido_id, art, corte
              where r.articulo_id = art.id and r.armado_el is not null and r.anulado_el is null
                and (r.armado_el at time zone 'America/Argentina/Buenos_Aires')::date
                    > corte.fecha), '0')
  union all select 4, 'entradas CAMINO 2 (descartable: cajon <= ficha)',
    coalesce((select sum(cajones)::text from com, fi where cont <= fi.contenido_caja), '0')
  union all select 5, 'entradas CAMINO 1 (a reprocesar: cajon > ficha)',
    coalesce((select sum(cajones)::text from com, fi where cont > fi.contenido_caja), '0')
  union all select 6, 'cajas ARMADAS por nosotros (guias R)',
    coalesce((select sum(rp.bultos_primera)::text from reprocesos rp, art, corte
              where rp.articulo_id = art.id and rp.anulado_el is null
                and rp.fecha_operacion > corte.fecha), '0')
) f order by orden;

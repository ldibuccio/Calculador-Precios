-- ¿Los decimales en bultos son FÓSIL del modelo viejo o seguían entrando?
-- Del 11/09, por el `+120,97` y el `57,03` de Lima. El compensatorio del
-- corte es `-st` sobre las seis patas: COPIA el decimal ajeno con el signo
-- cambiado. Es un reflejo, no una causa, y por eso va en su propia columna.
--
-- Correr en LAS DOS. El corte sale de corte_modelo, nunca se asume. Palmala
-- está parada: ahí un cero no vota — mirar `ultima_guia_r` primero.
--   algún *_post > 0    -> seguía entrando; el step cerró una puerta viva.
--   *_post 0, *_pre > 0 -> fósil ya cancelado. Nada que revisar.
--
-- Escalares y no joins (cuatro `left join` multiplican los conteos entre sí).
-- Probada contra db/esquema_completo.sql, con un decimal plantado para ver
-- que lo detecta.

with c0 as (select fecha as f0 from corte_modelo where id = 1)
select
  (select f0 from c0) as corte,
  (select max(fecha_operacion) from reprocesos where anulado_el is null) as ultima_guia_r,

  (select count(*) from reprocesos r where r.anulado_el is null
     and r.fecha_operacion <= (select f0 from c0)
     and (r.bultos_tomados % 1 <> 0 or r.bultos_primera % 1 <> 0
          or r.bultos_segunda % 1 <> 0 or r.bultos_merma % 1 <> 0)) as guias_pre,
  (select count(*) from reprocesos r where r.anulado_el is null
     and r.fecha_operacion > (select f0 from c0)
     and (r.bultos_tomados % 1 <> 0 or r.bultos_primera % 1 <> 0
          or r.bultos_segunda % 1 <> 0 or r.bultos_merma % 1 <> 0)) as guias_post,

  (select count(*) from compras c where c.fecha_operacion <= (select f0 from c0)
     and (c.cantidad_cajones % 1 <> 0
          or coalesce(c.cantidad_cajones_real, 0) % 1 <> 0
          or coalesce(c.cantidad_cajones_rechazada, 0) % 1 <> 0)) as compras_pre,
  (select count(*) from compras c where c.fecha_operacion > (select f0 from c0)
     and (c.cantidad_cajones % 1 <> 0
          or coalesce(c.cantidad_cajones_real, 0) % 1 <> 0
          or coalesce(c.cantidad_cajones_rechazada, 0) % 1 <> 0)) as compras_post,

  (select count(*) from movimientos_stock m where m.anulado_el is null
     and m.tipo = 'cierre_modelo_viejo' and m.cantidad % 1 <> 0) as compensatorio_espejo,
  (select count(*) from movimientos_stock m where m.anulado_el is null
     and m.tipo <> 'cierre_modelo_viejo'
     and m.fecha_operacion > (select f0 from c0)
     and m.cantidad % 1 <> 0) as movimientos_post,

  (select count(*) from conteos_stock t where t.cantidad % 1 <> 0) as conteos_decimal;

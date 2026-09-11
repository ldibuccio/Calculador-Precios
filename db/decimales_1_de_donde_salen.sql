-- ¿Los decimales en bultos son FÓSIL del modelo viejo o siguen entrando?
--
-- CONTESTADA EL 11/09. Frutamax, corte 05/09, ultima_guia_r 10/09:
--   guias_pre 6 · guias_post 0 · compras_pre 0 · compras_post 0
--   compensatorio_espejo 4 · movimientos_post 0 · conteos_decimal 0
--
-- FÓSIL: 6 guías R ANTERIORES al corte, ya canceladas. 4 espejos y no 6 es
-- lo esperado: el compensatorio es uno por ARTÍCULO con neto <> 0, no uno
-- por guía. El `+120,97` de Lima no era un decimal que siguiera entrando:
-- era el compensatorio (`-st`) reflejando los de antes del corte.
--
-- Al reusarla: algún *_post > 0 -> entró algo nuevo. En PALMALA el
-- `*_pre` vota (son filas cargadas) y el `*_post` no: base parada.
-- Probada con un decimal plantado (corolario 36).

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

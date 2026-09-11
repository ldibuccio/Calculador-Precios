-- ¿Hay guías R asignadas a la ficha de OTRO cliente?
--
-- `reprocesos.cliente_id` (para quién se armó) y `fichas_logistica.cliente_id`
-- (de quién es la caja) son columnas sueltas que nada ata: el selector ofrece
-- las fichas POR ARTÍCULO —de todos los clientes— y el POST solo valida que
-- la ficha exista y que la guía no esté anulada.
--
-- CONTEOS y no lista, y `ultima_guia_r` al lado: un cero sobre base parada
-- no vota.
--
-- OJO `sin_cliente_no_se_juzga`: `rp.cliente_id` es NULLABLE, así que
-- `f.cliente_id <> rp.cliente_id` da NULL en las guías viejas sin cliente y
-- esas filas se caen SOLAS. Sin esa columna un `cruzadas_post 0` podría ser
-- "no pasa" o "no se pudo mirar".
--
-- PROBADA CON EL CASO PLANTADO (corolario 36) sobre db/esquema_completo.sql:
-- con las seis situaciones a mano cada contador pasó de 0 a 1 y el
-- denominador a 4.

with c0 as (select fecha as f0 from corte_modelo where id = 1)
select
  (select f0 from c0) as corte,
  (select max(fecha_operacion) from reprocesos where anulado_el is null) as ultima_guia_r,

  -- Denominador: sobre cuántas se puede comparar.
  (select count(*) from reprocesos rp
     join fichas_logistica f on f.id = rp.ficha_id
     where rp.anulado_el is null and rp.cliente_id is not null) as con_ficha_y_cliente,

  (select count(*) from reprocesos rp
     join fichas_logistica f on f.id = rp.ficha_id
     where rp.anulado_el is null and rp.cliente_id is not null
       and f.cliente_id <> rp.cliente_id
       and rp.fecha_operacion <= (select f0 from c0)) as cruzadas_pre,
  (select count(*) from reprocesos rp
     join fichas_logistica f on f.id = rp.ficha_id
     where rp.anulado_el is null and rp.cliente_id is not null
       and f.cliente_id <> rp.cliente_id
       and rp.fecha_operacion > (select f0 from c0)) as cruzadas_post,

  (select count(*) from reprocesos rp
     join fichas_logistica f on f.id = rp.ficha_id
     where rp.anulado_el is not null and rp.cliente_id is not null
       and f.cliente_id <> rp.cliente_id) as cruzadas_anuladas,

  (select count(*) from reprocesos rp
     where rp.anulado_el is null and rp.ficha_id is not null
       and rp.cliente_id is null) as sin_cliente_no_se_juzga,

  -- Control: el selector filtra por artículo. TIENE que dar 0.
  (select count(*) from reprocesos rp
     join fichas_logistica f on f.id = rp.ficha_id
     where rp.anulado_el is null
       and f.articulo_id <> rp.articulo_id) as ficha_de_otro_articulo;

with c0 as (select fecha from corte_modelo where id = 1),
armados as (
  select distinct r.articulo_id as art,
         (r.armado_el at time zone 'America/Argentina/Buenos_Aires')::date as dia
    from pedidos_renglones r
    join pedidos p on p.id = r.pedido_id
    join fichas_logistica f on f.id = r.ficha_id
   where p.anulado_el is null and r.armado_el is not null and r.anulado_el is null
     and r.articulo_id is not null and f.envase_id is not null
     and (r.armado_el at time zone 'America/Argentina/Buenos_Aires')::date
         > (select fecha from c0)
),
guias as (
  select articulo_id as art, fecha_operacion as dia, count(*) as cuantas
    from reprocesos
   where anulado_el is null and fecha_operacion > (select fecha from c0)
   group by articulo_id, fecha_operacion
)
select count(*) as dias_de_armado,
       count(distinct a.art) as articulos,
       count(*) filter (where coalesce(g.cuantas, 0) > 0) as con_guia_R_ese_dia,
       coalesce(max(g.cuantas), 0) as peor_dia,
       (select max(dia) from armados) as ultimo_armado,
       (select max(fecha_operacion) from reprocesos where anulado_el is null) as ultima_guia_r,
       (select fecha from c0) as corte
  from armados a
  left join guias g on g.art = a.art and g.dia = a.dia;

-- ¿El freno nuevo puede rebotar una guía R que falta cargar?
--
-- El freno del 16/09 descuenta lo que otras guías R del MISMO ARTICULO y la
-- MISMA FECHA ya tomaron. Con ninguna, no descuenta nada: el resultado es
-- identico al de antes del cambio, bit por bit. Asi que `con_guia_R_ese_dia`
-- en CERO cierra la pregunta — ninguna puede rebotar por el cambio.
--
-- ES UN SUPERCONJUNTO A PROPOSITO: cuenta todos los dias con armado de ficha
-- con envase, no solo los que estan esperando su guia R (eso sale del rejuego
-- del FIFO, no de una consulta, y escribirlo en SQL seria la segunda version
-- de la cuenta que el docstring de bultos_esperando_guia_r_por_articulo
-- prohibe). Solo puede sobre-reportar, que es la direccion segura para una
-- pregunta de seguridad.
--
-- `peor_dia` dice cuantas guias R llegaron a compartir un dia; los testigos
-- dicen si la base esta viva, porque sobre una parada estos ceros no valen.

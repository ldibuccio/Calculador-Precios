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
-- identico al de antes del cambio, bit por bit.
--
-- CONTESTADA EL 16/09, Y ESTA CONSULTA NO LA CONTESTO: Frutamax dio
-- `con_guia_R_ese_dia 119 de 128`. Un superconjunto que cubre el 93% no
-- acota nada — solo un CERO cerraba la pregunta, y no dio cero. Lo que la
-- cerro fue probar los ocho armados que esperaban en la pantalla de
-- Reproceso, que corre el codigo del freno: entran los ocho. No la corras
-- esperando una respuesta; da la condicion necesaria, no el caso.
--
-- ES UN SUPERCONJUNTO A PROPOSITO: cuenta todos los dias con armado de ficha
-- con envase, no solo los que esperan su guia R (eso sale del rejuego
-- del FIFO, no de una consulta, y escribirlo en SQL seria la segunda version
-- de la cuenta que el docstring de bultos_esperando_guia_r_por_articulo
-- prohibe). Solo puede sobre-reportar, que es la direccion segura para una
-- pregunta de seguridad.
--
-- `peor_dia`: cuantas guias R compartieron un dia. Los testigos dicen si la
-- base vota: sobre una parada estos ceros no valen.

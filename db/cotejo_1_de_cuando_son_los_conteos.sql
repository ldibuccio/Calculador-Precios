with u as (
  select distinct on (articulo_id, ficha_id, es_segunda)
         (creado_en at time zone 'America/Argentina/Buenos_Aires')::date as dia
  from conteos_stock
  order by articulo_id, ficha_id, es_segunda, creado_en desc
),
h as (select (now() at time zone 'America/Argentina/Buenos_Aires')::date as hoy),
x as (select extract(hour from creado_en at time zone 'America/Argentina/Buenos_Aires') as hora
      from conteos_stock)
select 'cotejo_1' as que_consulta,
  (select hoy from h) as hoy,
  (select count(*) from u) as porciones_en_el_cotejo,
  (select count(*) from u where dia = (select hoy from h)) as de_hoy,
  (select count(*) from u where dia = (select hoy from h) - 1) as de_ayer,
  (select count(*) from u where dia between (select hoy from h) - 7 and (select hoy from h) - 2) as de_2_a_7_dias,
  (select count(*) from u where dia < (select hoy from h) - 7) as de_mas_de_7,
  (select min(dia) from u) as el_mas_viejo,
  (select max(dia) from u) as el_mas_nuevo,
  (select string_agg(to_char(dia, 'DD/MM') || ':' || n, ' · ' order by dia desc)
     from (select dia, count(*) n from u group by dia) g) as porciones_por_dia,
  (select count(*) from conteos_stock) as conteos_POBLACION,
  (select count(*) from x where hora < 10) as contados_antes_de_las_10,
  (select count(*) from x where hora >= 10 and hora < 14) as de_10_a_14,
  (select count(*) from x where hora >= 14 and hora < 18) as de_14_a_18,
  (select count(*) from x where hora >= 18) as despues_de_las_18,
  (select max(armado_el) at time zone 'America/Argentina/Buenos_Aires'
     from pedidos_renglones) as testigo_ultimo_armado;

-- ---------------------------------------------------------------------
-- COTEJO 1 (25/09): ¿de CUÁNDO son los conteos que el Cotejo compara
-- contra el stock de HOY? Solo lee. Una consulta, una fila.
--
-- porciones_en_el_cotejo es exactamente lo que el Cotejo dibuja: el último
-- conteo de cada porción (artículo, ficha, segunda), el mismo DISTINCT ON
-- de listar_ultimos_conteos_stock. Las cuatro columnas de antigüedad lo
-- parten y tienen que sumar ese total. porciones_por_dia dice las fechas.
--
-- Las cuatro columnas de HORA son sobre TODOS los conteos (la costumbre,
-- no solo los últimos), y deciden contra qué día se compara: si se cuenta
-- a la mañana antes de armar, el conteo del lunes es el cierre del
-- domingo; si se cuenta a la tarde, es el cierre del lunes.
--
-- testigo_ultimo_armado dice si la base está viva (Palmala no vota).

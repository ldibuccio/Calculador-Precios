-- ¿CUANTO TARDA en cargarse una guia R desde el dia que dice cubrir?
-- Decide si la ventana en que el sistema cree tener un cajon que ya salio
-- en el camion es de horas o de dias. Con la pared del armado, en esa
-- ventana el freno del reproceso ve disponible un cajon que ya no esta.
-- demora = dia de CARGA (creado_en, en hora argentina) menos fecha_operacion.
--   0  = se cargo el mismo dia: la ventana son horas y el riesgo es chico.
--   1  = al dia siguiente.
--  >=2 = paso un fin de semana o mas: ahi el freno puede autorizar un
--        reproceso contra cajones que no existen.
-- Un NEGATIVO seria una guia R fechada en el futuro; no deberia haber.
-- Solo 'normal': la 'inicial' es la foto del corte, se carga con el corte y
-- su demora no dice nada de la operacion.
-- creado_en es timestamptz y va con AT TIME ZONE: sin eso el dia corre de
-- 21:00 a 21:00 y una guia cargada a la noche suma un dia que no existio.
-- Devuelve CONTEOS y no una lista: con lista, "ninguna tardo" y "no corrio"
-- son la misma pantalla vacia. Y trae ultima_guia_r como testigo
-- independiente del corte: si el corte viniera NULL, los ceros se
-- explicarian solos y esta columna lo contradice.
with c0 as (select fecha f0 from corte_modelo where id = 1),
r as (
  select rp.fecha_operacion fop,
    ((rp.creado_en at time zone 'America/Argentina/Buenos_Aires')::date
     - rp.fecha_operacion) demora
  from reprocesos rp, c0
  where rp.anulado_el is null and rp.tipo = 'normal'
    and rp.fecha_operacion > c0.f0
)
select (select f0 from c0) corte,
  count(*) guias,
  count(*) filter (where demora <= 0) mismo_dia,
  count(*) filter (where demora = 1) un_dia,
  count(*) filter (where demora between 2 and 3) dos_a_tres,
  count(*) filter (where demora >= 4) cuatro_o_mas,
  max(demora) peor,
  round(avg(demora), 2) promedio,
  count(*) filter (where demora < 0) fechada_en_el_futuro,
  (select max(fecha_operacion) from reprocesos
   where anulado_el is null and tipo = 'normal') ultima_guia_r
from r;

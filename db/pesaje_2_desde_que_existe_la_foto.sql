-- El mismo 2x2, ACOTADO al periodo en que la foto de balanza existe.
--
-- `pesaje_1` mide 60 dias y la foto existe hace dos, asi que ahi "con
-- foto" contra "sin foto" compara la funcion nueva contra el pasado, no
-- una cosa contra la otra. Esto acota la comparacion a la ventana.
--
-- El corte sale de la BASE y vuelve como COLUMNA (`primera_foto`), como
-- escalar y no cross join: sin ninguna foto el cross join dejaria la
-- consulta SIN FILAS, que no distingue "no hay" de "no corrio".
--
-- EL CONFUNDIDO, y por eso van las `pre_`: si en la ventana TAMBIEN
-- subieron las correcciones SIN foto, cambio el periodo y no la foto.
--
-- Y OJO CON EL DENOMINADOR: dos dias son pocas recepciones.
with c0 as (select min(creado_en)::date as f0 from fotos_recepcion),
p as (
  select c.id, c.fecha_operacion,
         (c.contenido_por_cajon_real = c.contenido_por_cajon
          and coalesce(c.cantidad_cajones_real, c.cantidad_cajones) = c.cantidad_cajones) as sin_tocar,
         exists (select 1 from fotos_recepcion f where f.compra_id = c.id) as con_foto
  from compras c
  where c.estado = 'recepcionado'
    and c.contenido_por_cajon_real is not null
    and c.fecha_operacion >= current_date - 60
)
select (select f0 from c0)                                              as primera_foto,
       (current_date - (select f0 from c0)) + 1                         as dias_ventana,
       count(*) filter (where fecha_operacion < (select f0 from c0))    as pre_recepciones,
       count(*) filter (where fecha_operacion < (select f0 from c0)
                          and not sin_tocar)                            as pre_tocadas,
       count(*) filter (where fecha_operacion >= (select f0 from c0))   as win_recepciones,
       count(*) filter (where fecha_operacion >= (select f0 from c0)
                          and con_foto)                                 as win_con_foto,
       count(*) filter (where fecha_operacion >= (select f0 from c0)
                          and con_foto and not sin_tocar)               as win_tocada_con_foto,
       count(*) filter (where fecha_operacion >= (select f0 from c0)
                          and not con_foto)                             as win_sin_foto,
       count(*) filter (where fecha_operacion >= (select f0 from c0)
                          and not con_foto and not sin_tocar)           as win_tocada_sin_foto,
       max(fecha_operacion)                                             as ultima_recepcion
from p;

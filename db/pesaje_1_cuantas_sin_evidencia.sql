with recep as (
  select c.id,
         (c.procesada_el at time zone 'America/Argentina/Buenos_Aires')::date dia,
         not exists (select 1 from fotos_recepcion f where f.compra_id = c.id) sin_foto,
         (c.contenido_por_cajon_real is null
          or c.contenido_por_cajon_real is not distinct from c.contenido_por_cajon) sin_tocar
    from compras c
   where c.estado = 'recepcionado'
     and c.procesada_el >= now() - interval '90 days'
)
select count(*) filter (where sin_foto and sin_tocar and dia >= current_date - 2) SIN_EVIDENCIA_2d,
       count(*) filter (where sin_foto and sin_tocar and dia >= current_date - 7) sin_evidencia_7d,
       count(*) filter (where sin_foto and dia >= current_date - 7) sin_foto_7d,
       count(*) filter (where sin_tocar and dia >= current_date - 7) sin_tocar_7d,
       count(*) filter (where (sin_foto or sin_tocar) and dia >= current_date - 7)
         CON_UN_OR_habria_disparado_7d,
       count(*) filter (where dia >= current_date - 2) RECEPCIONES_2d,
       count(*) filter (where dia >= current_date - 7) recepciones_7d,
       count(*) POBLACION_90d,
       (select max(procesada_el)::date from compras where estado = 'recepcionado')
         TESTIGO_ultima_recepcion
  from recep;

-- CUANTAS RECEPCIONES NO TIENEN NINGUNA EVIDENCIA DE PESAJE, por ventana.
-- Decide el tamaño de la alerta `recepciones_sin_pesaje`, que usa DOS DIAS.
--
-- SIN EVIDENCIA SON DOS CONDICIONES A LA VEZ, y por eso no es un OR: tocar
-- el numero es pesaje aunque no haya foto, y una foto con el numero sin
-- tocar puede ser "pese y dio 16". Lo que no tiene defensa es el cruce.
-- `CON_UN_OR` es lo que habria disparado la otra version, y va calculada
-- acá: restar mal la interseccion de cabeza es el error natural.
--
-- `sin_foto_7d` y `sin_tocar_7d` se llamaban `solo_*` y era MENTIRA —
-- cuentan el total de cada condicion, las que estan en las dos incluidas.
-- Leidas como "solo" parecen grupos aparte, y en Frutamax 18 de esas 19 sin
-- foto son las MISMAS que las sin evidencia (18/09).
--
-- EL TESTIGO no se recorta a 90 dias a proposito: mira `compras` entera, asi
-- que puede traer una fecha mas vieja que todo lo de arriba. Un testigo
-- adentro de la ventana con `recepciones_7d` en cero no es contradiccion.

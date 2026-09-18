-- CUANTAS RECEPCIONES NO TIENEN NINGUNA EVIDENCIA DE PESAJE, por ventana.
-- Decide el tamaño de la alerta `recepciones_sin_pesaje`, que hoy usa DOS
-- DIAS. Si el numero de 2 dias es grande, lo que hay que mover no es el
-- umbral: es la unidad (ver "un aviso que dispara veintiun veces por semana
-- no se mira dos semanas").
--
-- SIN EVIDENCIA SON DOS CONDICIONES A LA VEZ, y por eso no es un OR: tocar
-- el numero es pesaje aunque no haya foto, y una foto con el numero sin
-- tocar puede ser "pese y dio 16". Lo que no tiene ninguna defensa es el
-- cruce de las dos.
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
       count(*) filter (where sin_foto and dia >= current_date - 7) solo_sin_foto_7d,
       count(*) filter (where sin_tocar and dia >= current_date - 7) solo_sin_tocar_7d,
       -- LA POBLACION al lado, que es lo unico que hace legible el conteo:
       -- 5 sobre 12 y 5 sobre 200 no dicen lo mismo.
       count(*) filter (where dia >= current_date - 2) RECEPCIONES_2d,
       count(*) filter (where dia >= current_date - 7) recepciones_7d,
       count(*) POBLACION_90d,
       -- EL TESTIGO: sin el, un cero se lee igual en una base en marcha que
       -- en una parada, y Palmala esta parada.
       (select max(procesada_el)::date from compras where estado = 'recepcionado')
         TESTIGO_ultima_recepcion
  from recep;

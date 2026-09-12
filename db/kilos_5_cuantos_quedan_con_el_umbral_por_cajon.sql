-- ¿Cuántos casos deja la alerta de kilos con el umbral POR CAJÓN?
--
-- El 12/09 el umbral estaba sobre el TOTAL y entraban compras grandes con
-- diferencias chicas: Jugo con -0,6k por cajón y Berenjena con -0,3k, que es
-- ruido de balanza. Con 33 cajones, tres décimas llegan a diez kilos.
-- El total DIMENSIONA (es la plata, y ordena la lista); el por cajón DETECTA.
--
-- Devuelve LAS DOS CUENTAS EN LA MISMA FILA a propósito: "quedan 4" solo se
-- puede leer al lado del "antes 17". Es el canario del corolario 12 hecho
-- columna — si las dos dan igual, el umbral no está filtrando nada y eso se
-- ve sin tener que correr nada más.
--
-- Y trae los testigos porque un cero solo no se puede leer (corolario 24):
-- `ultima_recepcion` dice si la base está viva, `desde_la_foto` contra qué
-- período se está midiendo (sin fotos, la alerta no puede decir nada), y
-- `recepciones_en_la_ventana` es la población contra la que se cuenta.
--
-- Verificada contra db/esquema_completo.sql en Postgres 16 con los cuatro
-- casos del 12/09 plantados: da `quedan_por_cajon 2 · entraban_por_total 5`
-- — quedan Pepino (-1,0) y el testigo (-3,0); Jugo, Berenjena y Cherry se
-- caen. Y sin ninguna foto devuelve LA FILA IGUAL (`desde_la_foto` NULL,
-- ceros, y la última recepción al lado): por eso el piso entra con un escalar
-- y no con un cross join, que dejaría la consulta sin filas y haría que "todo
-- bien" y "no corrió" se vieran iguales (corolario 17).
--
-- La ventana y el umbral son los de la app: DIAS_ALERTA_KILOS_FALTANTES = 7
-- y UMBRAL_KILOS_FALTANTES_POR_CAJON = 1 (app/main.py).
with c0 as (
  select min((f.creado_en at time zone 'America/Argentina/Buenos_Aires')::date) as desde_la_foto
  from fotos_recepcion f
)
select
  (select desde_la_foto from c0) as desde_la_foto,
  count(*) filter (
    where (c.contenido_por_cajon - c.contenido_por_cajon_real) >= 1
  ) as quedan_por_cajon,
  count(*) filter (
    where ((c.contenido_por_cajon - c.contenido_por_cajon_real)
           * c.cantidad_cajones_real) >= 1
  ) as entraban_por_total,
  count(*) as recepciones_en_la_ventana,
  (select max(fecha_operacion) from compras where estado = 'recepcionado') as ultima_recepcion
from compras c
where c.estado = 'recepcionado'
  and c.contenido_por_cajon_real is not null
  and c.cantidad_cajones_real is not null
  and c.fecha_operacion >= current_date - 7
  and c.fecha_operacion <= current_date
  and c.fecha_operacion >= (select desde_la_foto from c0);

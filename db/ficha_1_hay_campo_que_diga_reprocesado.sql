-- ¿EXISTE UN CAMPO que diga si un articulo se despacha en su cajon original
-- o en caja armada? Enumerado el esquema: NO hay ninguno. Los unicos
-- booleanos son `activo`, `envase_variable`, los de casillas de pedidos y
-- `consumos_editados`. Y `listar_articulos_para_reproceso` elige por STOCK
-- DISPONIBLE, no por una marca — su docstring dice que reprocesar cajas ya
-- armadas "es raro pero el FIFO lo admite" y que esa pantalla "no es el
-- lugar para prohibirlo".
-- Lo mas cerca que hay es un par DERIVADO, y esto lo pone a prueba:
--   fichas_logistica.contenido_caja  = lo que el cliente pide por bulto
--   articulos.contenido_referencia   = lo que trae el bulto que se compra
-- Si difieren, el bulto de venta no es el de compra, o sea reenvasado.
-- La matriz de abajo cruza ese par contra el hecho consumado (¿el articulo
-- tuvo guias R alguna vez?). Si el par predice el hecho, sirve para sembrar
-- la marca; si no, la marca hay que cargarla a mano.
-- `sin_dato_para_saber` va aparte a proposito: "no difieren" y "no hay dato
-- cargado" dan los dos cero y significan cosas distintas.
with f as (select fl.articulo_id aid,
 count(*) fichas,
 count(*) filter (where fl.contenido_caja is not null) con_contenido,
 count(*) filter (where fl.contenido_caja is not null
   and a.contenido_referencia is not null
   and fl.contenido_caja <> a.contenido_referencia) difieren
 from fichas_logistica fl join articulos a on a.id = fl.articulo_id
 group by 1),
g as (select distinct articulo_id aid from reprocesos
 where anulado_el is null and bultos_primera > 0)
select coalesce(a.nombre,'TOTAL') articulo,
 max(f.fichas) fichas, max(f.con_contenido) con_contenido,
 max(a.contenido_referencia) contenido_ref, max(f.difieren) difieren,
 count(*) filter (where g.aid is not null and f.difieren > 0) gr_y_difiere,
 count(*) filter (where g.aid is not null and f.difieren = 0) gr_sin_señal,
 count(*) filter (where g.aid is null and f.difieren > 0) sin_gr_pero_difiere,
 count(*) filter (where g.aid is null and f.difieren = 0
   and f.con_contenido > 0 and a.contenido_referencia is not null) sin_gr_ni_señal,
 count(*) filter (where f.con_contenido = 0
   or a.contenido_referencia is null) sin_dato_para_saber
from f join articulos a on a.id = f.aid
left join g on g.aid = f.aid
group by grouping sets ((),(a.nombre))
order by grouping(a.nombre) desc, 5 desc;

with pedidos_a_medir (articulo, dia) as (
  values ('Berenjena', '2026-09-07'::date)
         -- , ('Otro artículo', '2026-09-08')
),
tomado as (
  select r.articulo_id, r.fecha_operacion,
         count(distinct r.id) as guias,
         sum(rc.bultos) as descuenta
    from reprocesos r
    join reprocesos_consumos rc on rc.reproceso_id = r.id
   where r.anulado_el is null and rc.origen <> 'sin_lote'
   group by r.articulo_id, r.fecha_operacion
)
select m.articulo, m.dia,
       a.id is not null as el_articulo_existe,
       coalesce(t.guias, 0) as guias_ese_dia,
       coalesce(t.descuenta, 0) as descuenta_como_mucho,
       (select max(fecha_operacion) from reprocesos where anulado_el is null) as ultima_guia_r
  from pedidos_a_medir m
  left join articulos a on a.nombre = m.articulo
  left join tomado t on t.articulo_id = a.id and t.fecha_operacion = m.dia
 order by coalesce(t.descuenta, 0) desc, m.articulo;

-- CUANTO LE DESCUENTA EL FRENO NUEVO A CADA GUIA R QUE FALTA CARGAR.
--
-- Se pega arriba UN RENGLON POR CASO (nombre exacto del articulo y fecha
-- del armado que espera, las dos salen del bloque del Remanente).
--
-- `descuenta_como_mucho` es un TECHO, no el descuento exacto: el freno
-- resta POR LOTE con piso en cero, asi que un lote ya sobre-atribuido
-- aporta menos que lo que dice esta suma. Nunca mas.
--
-- CERO cierra el caso: sin nada tomado ese dia el freno no descuenta y el
-- resultado es identico al de antes del cambio.
--
-- Lo que esta consulta NO puede decir es cuanto hay DISPONIBLE: eso es la
-- suma de los restantes de los lotes de materia prima, que sale de rejugar
-- el FIFO. El atajo `entradas - salidas` no sirve apenas se filtra por tipo
-- de lote — es el corolario 13, medido. Eso lo contesta la pantalla de
-- Reproceso, que corre el codigo de verdad y no guarda nada.
--
-- `el_articulo_existe` esta para que un nombre mal tipeado no se lea como
-- un cero tranquilizador.
--
-- EL CASO DEL 16/09 SE CERRO POR LA PANTALLA: los ocho armados que
-- esperaban guia R entran (Mandarina 10/09 rebota recien con 50, porque
-- ese dia habia 40). Esta consulta queda para el proximo que dude.

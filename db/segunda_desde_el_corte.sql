-- ¿DE DÓNDE SALE CADA BULTO DE SEGUNDA DESDE EL CORTE? Solo lectura.
-- Una fila por guía R con segunda fechada en el corte o después, con su
-- tipo y la hora de carga: una 'normal' es una guía R del día a día, una
-- 'inicial' es la del conteo del corte.
select r.id guia_r, a.nombre articulo, r.fecha_operacion, r.tipo,
       r.creado_en cargada, r.bultos_tomados tomo, r.bultos_primera primera,
       r.bultos_segunda segunda, r.bultos_merma merma,
       c.nombre cliente
from reprocesos r
join articulos a on a.id = r.articulo_id
left join clientes c on c.id = r.cliente_id
where r.anulado_el is null and r.bultos_segunda > 0
  and r.fecha_operacion >= (select fecha from corte_modelo where id = 1)
order by a.nombre, r.creado_en;

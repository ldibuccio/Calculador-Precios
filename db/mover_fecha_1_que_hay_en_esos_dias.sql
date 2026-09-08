-- ANTES DE TOCAR NADA: que hay cargado en los dos dias.
-- Mover la fecha de un pedido puede dejar DOS vigentes el mismo dia. No hay
-- indice unico por (cliente_id, fecha_operacion): la base lo permite y las
-- siete consultas del FIFO eligen con
--     distinct on (cliente_id, fecha_operacion) ... order by creado_en desc
-- o sea que gana el mas NUEVO por creado_en y el otro desaparece de las
-- cuentas SIN anularse y sin que nada avise.
-- La columna `vigente` se calcula con ESA MISMA regla, no con una parecida.
-- Solo lectura: esta consulta no escribe nada.
select c.nombre cliente,
  p.fecha_operacion fecha,
  p.id,
  p.creado_en,
  p.origen,
  p.anulado_el is not null anulado,
  p.reemplaza_a_pedido_id reemplaza_a,
  (p.id = (select p2.id from pedidos p2
           where p2.cliente_id = p.cliente_id
             and p2.fecha_operacion = p.fecha_operacion
             and p2.anulado_el is null
           order by p2.creado_en desc limit 1)) vigente,
  count(r.id) filter (where r.anulado_el is null) renglones,
  count(r.id) filter (where r.armado_el is not null and r.anulado_el is null) armados,
  round(coalesce(sum(coalesce(r.cantidad_armada, r.cantidad))
                 filter (where r.armado_el is not null and r.anulado_el is null), 0), 2) bultos_armados
from pedidos p
join clientes c on c.id = p.cliente_id
left join pedidos_renglones r on r.pedido_id = p.id
where p.fecha_operacion in (date '2026-09-08', date '2026-09-09')
group by c.nombre, p.fecha_operacion, p.id, p.creado_en, p.origen, p.anulado_el,
         p.reemplaza_a_pedido_id
order by c.nombre, p.fecha_operacion, p.creado_en;

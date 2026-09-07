-- ############################################################################
-- QUÉ KILAJE TIENE DE VERDAD LO QUE SE ARMÓ. Solo lectura.
--
-- Para el cherry: la ficha única dice 5 kg, y el sistema no tiene NINGUNA
-- opinión propia sobre el kilaje de una caja armada —`reprocesos` guarda solo
-- bultos, ningún kilo—, así que toda caja armada es de 5 kg por construcción.
--
-- El único lugar por donde entra la verdad física es `kilos_enviados`: los
-- kilos REALES que el depósito cargó al tildar, y que son los que se facturan.
-- Si lo armado no fuera de 5 kg, acá se ve.
--
-- OJO: `kilos_enviados` es el TOTAL DEL RENGLÓN, no el kilaje por caja. El
-- por-caja sale de dividir por los bultos armados, igual que lo hace
-- `_desvio_de_kilos` en app/main.py. La tolerancia (3 kg POR BULTO) es la
-- misma de TOLERANCIA_KILOS_POR_BULTO: 20 bultos con 1 kg de más cada uno
-- están dentro; 2 bultos con 5 kg de más, afuera.
--
-- Correr cuando haya movimiento de cherry. Cambiar 'cherry' por lo que sea.
-- ############################################################################
with vigentes as (
  select distinct on (cliente_id, fecha_operacion) id, cliente_id, fecha_operacion
  from pedidos where anulado_el is null
  order by cliente_id, fecha_operacion, creado_en desc
)
select a.nombre articulo, cl.nombre cliente,
       coalesce(nullif(btrim(f.nombre_cliente), ''), '(sin nombre)') ficha,
       f.contenido_caja dice_la_ficha,
       v.fecha_operacion pedido_del,
       coalesce(r.cantidad_armada, r.cantidad) bultos,
       r.kilos_enviados kilos_del_renglon,
       round(r.kilos_enviados / nullif(coalesce(r.cantidad_armada, r.cantidad), 0), 2) kg_por_caja_real,
       case
         when r.kilos_enviados is null then 'sin kilaje cargado'
         when f.contenido_caja is null then 'la ficha no dice cuánto'
         when abs(r.kilos_enviados / nullif(coalesce(r.cantidad_armada, r.cantidad), 0)
                  - f.contenido_caja) <= 3 then 'coincide con la ficha'
         else 'NO COINCIDE: la caja real no es la de la ficha'
       end veredicto
from pedidos_renglones r
join vigentes v on v.id = r.pedido_id
join articulos a on a.id = r.articulo_id
join clientes cl on cl.id = v.cliente_id
left join fichas_logistica f on f.id = r.ficha_id
where r.armado_el is not null and r.anulado_el is null
  and a.nombre ilike '%cherry%'
order by v.fecha_operacion desc, r.id;

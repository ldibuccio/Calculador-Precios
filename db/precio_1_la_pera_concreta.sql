-- Los ingresos directos de los ultimos 30 dias, con su importe y por que
-- camino entraron. Cambiar 'Pera' por el articulo que se quiera mirar.
select
    c.id,
    c.fecha_operacion,
    a.nombre                                    as articulo,
    p.nombre                                    as proveedor,
    c.importe,
    c.cantidad_cajones_real                     as bultos,
    c.cargado_el                                as se_cargo,
    c.procesada_el                              as se_recepciono,
    case
        when c.retiro_origen is distinct from 'ingreso_directo' then 'compra normal'
        when (c.procesada_el at time zone 'America/Argentina/Buenos_Aires')::date
             = (c.cargado_el at time zone 'America/Argentina/Buenos_Aires')::date
            then 'ingreso directo de DEPOSITO'
        else 'ingreso RETROACTIVO de Gerencia'
    end                                         as por_donde_entro,
    case when c.importe is null then 'en blanco' else 'CON IMPORTE' end as precio,
    (select max(cargado_el) from compras)       as ultima_compra_cargada
from compras c
join articulos a on a.id = c.articulo_id
join proveedores p on p.id = c.proveedor_id
where c.cargado_el > now() - interval '30 days'
  and a.nombre ilike '%Pera%'
order by c.cargado_el desc;

-- NO HAY COLUMNA DE "QUIEN": `compras` no guarda quien escribio el importe ni
-- cuando. `cargado_el` es de la COMPRA, no del precio. Asi que esta consulta
-- dice QUE precio tiene y POR DONDE entro la mercaderia; quien lo tipeo no
-- esta en la base y ninguna consulta lo puede sacar.
--
-- `por_donde_entro` separa los dos ingresos directos por su firma: el de
-- Deposito recepciona en el mismo instante en que se carga (las dos now()),
-- y el retroactivo de Gerencia fecha la recepcion al mediodia del dia que se
-- elige, que casi nunca es el dia de carga.
--
-- `ultima_compra_cargada` es el testigo: sin el, cero filas no distingue
-- "no hay peras" de "esta base no se usa" (corolario 24).

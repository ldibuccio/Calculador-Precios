-- Agrega a conversion_articulos_cliente los 3 códigos del pedido de Día que
-- quedaron afuera de db/cargar_conversiones_dia.sql por no tener artículo
-- en el catálogo en ese momento (ver Pedido_Dia_0508.pdf, sección Frutamax).
--
-- Mismo patrón: busca el cliente por nombre ('Día') y cada artículo por su
-- nombre, sin depender de IDs fijos. Si alguno de los 3 artículos todavía
-- no existe en articulos, esa fila simplemente no se inserta (el join no
-- encuentra el artículo), sin error. Seguro de correr más de una vez: si la
-- conversión ya existe para ese cliente + nombre_cliente, no hace nada (on
-- conflict do nothing).

insert into conversion_articulos_cliente (cliente_id, articulo_id, nombre_cliente, codigo_cliente)
select cl.id, a.id, v.nombre_cliente, v.codigo_cliente
from (values
    ('90076',  'TOMATE PG',   'Tomate PG'),
    ('90137',  'ANANA',       'Anana'),
    ('101891', 'KIWI CUBETA', 'Kiwi')
) as v(codigo_cliente, nombre_cliente, articulo_nombre)
join articulos a on a.nombre = v.articulo_nombre
cross join (select id from clientes where nombre = 'Día') cl
on conflict (cliente_id, nombre_cliente) do nothing;

-- Carga las 29 conversiones ya conocidas del cliente Día: cómo llama Día a
-- cada artículo mío en su pedido por email (nombre_cliente) y su código
-- (codigo_cliente), tomados del pedido real (Pedido_Dia_0508.pdf, sección
-- "9582 FRUTAMAX" — la otra sección del mismo mail, "11344 PALMALA", es el
-- pedido de otro distribuidor y no se usa acá).
--
-- Quedan afuera 3 códigos del pedido que no tienen artículo en el catálogo
-- todavía (vinieron en 0 esta vez, por eso no rompen nada por ahora):
--   90076 TOMATE PG, 90137 ANANA, 101891 KIWI CUBETA
--
-- Busca el cliente por nombre ('Día') y cada artículo por su nombre, sin
-- depender de IDs fijos. Seguro de correr más de una vez: si una conversión
-- ya existe para ese cliente + nombre_cliente, no hace nada (on conflict do
-- nothing), no duplica ni pisa datos.
--
-- Requiere que ya exista la tabla conversion_articulos_cliente
-- (db/agregar_conversion_articulos.sql).

insert into conversion_articulos_cliente (cliente_id, articulo_id, nombre_cliente, codigo_cliente)
select cl.id, a.id, v.nombre_cliente, v.codigo_cliente
from (values
    ('90039',  'MANZ ROJ ELE', 'Mzn Red'),
    ('90074',  'TOMATE PERIT', 'Tomate Perita'),
    ('90111',  'MANZANA PG',   'Man Gob'),
    ('90112',  'MANZANA VDE',  'Mzn Granny'),
    ('90113',  'PERA COMERCI', 'Pera'),
    ('90114',  'LIMON GRANEL', 'Limón'),
    ('90115',  'POMELO GRA',   'Pomelo'),
    ('90117',  'NARANJA JUGO', 'Jugo'),
    ('90118',  'NARANJA OMB',  'Ombligo'),
    ('90119',  'MANDARINA G',  'Mandarina'),
    ('90121',  'ZAP. RED. GR', 'Zapallito'),
    ('90123',  'M.ROJO GRA',   'Morrón Rojo'),
    ('90124',  'M.VERDE GRA',  'Morrón Verde'),
    ('90127',  'TOM RED 1° E', 'Tomate Redondo'),
    ('90135',  'DURAZNO',      'Durazno'),
    ('90136',  'MELON',        'Melón'),
    ('90138',  'CIRUELA',      'Ciruela'),
    ('90142',  'UVA GRANEL',   'Uva'),
    ('90145',  'PEPINO GRANE', 'Pepino'),
    ('90179',  'BERENJENA G',  'Berenjena'),
    ('90189',  'CEREZA',       'Cereza'),
    ('90191',  'PELON',        'Pelón'),
    ('90192',  'SANDIA',       'Sandía'),
    ('90314',  'TOMATE CHERR', 'Tomate Cherry'),
    ('103732', 'FRUTILLA',     'Frutilla'),
    ('225863', 'MANGO',        'Mango'),
    ('228219', 'PALTA',        'Palta'),
    ('259411', 'LIMA X 1KG',   'Lima'),
    ('261379', 'ARANDANO',     'Arándano')
) as v(codigo_cliente, nombre_cliente, articulo_nombre)
join articulos a on a.nombre = v.articulo_nombre
cross join (select id from clientes where nombre = 'Día') cl
on conflict (cliente_id, nombre_cliente) do nothing;

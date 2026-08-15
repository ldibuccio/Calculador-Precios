-- Fusiona conversion_articulos_cliente (como llama cada cliente a cada
-- articulo, con su codigo) DENTRO de fichas_logistica: toda la info de
-- "como este cliente trata este articulo" (envase, contenido, unidad de
-- venta, Y el alias) queda en un solo lugar por articulo+cliente.
--
-- Verificado en produccion antes de correr esto (SELECT manual): los 31
-- alias existentes matchean 1 a 1 con una ficha por articulo_id+cliente_id,
-- cero huerfanos, cero duplicados. Por eso el UPDATE de abajo no necesita
-- logica especial para esos casos (ver conversacion del merge para el plan
-- completo, incluyendo que hacer si algun caso no matcheara).
--
-- Seguro de correr mas de una vez: las columnas se agregan con if not
-- exists, y el UPDATE simplemente vuelve a copiar los mismos valores.
--
-- La tabla vieja (conversion_articulos_cliente) NO se borra aca a proposito
-- queda como respaldo hasta confirmar que las fichas se ven bien en
-- produccion. El DROP TABLE definitivo es un paso manual aparte.

alter table fichas_logistica add column if not exists nombre_cliente text;
alter table fichas_logistica add column if not exists codigo_cliente text;

comment on column fichas_logistica.nombre_cliente is 'Nombre con el que este cliente pide el articulo (alias, ej. "MANZ ROJ ELE"). Opcional: puede no conocerse todavia al crear la ficha.';
comment on column fichas_logistica.codigo_cliente is 'Codigo con el que este cliente pide el articulo (opcional, ej. 90039).';

update fichas_logistica f
set nombre_cliente = c.nombre_cliente,
    codigo_cliente = c.codigo_cliente,
    actualizado_en = now()
from conversion_articulos_cliente c
where c.articulo_id = f.articulo_id
  and c.cliente_id = f.cliente_id;

-- Pendiente, manual, en un paso aparte cuando se confirme que todo anda bien:
-- alter table conversion_articulos_cliente rename to conversion_articulos_cliente_bak;
-- (mas adelante, ya con confianza: drop table conversion_articulos_cliente_bak;)

-- Agrega envase_variable a fichas_logistica (si=fijo, no=el envase se
-- decide por compra) y completa el contenido de Frutilla/Arandano de "Dia"
-- (12 cubetas, dato conocido). Seguro de correr aunque la columna ya exista
-- (if not exists) o el contenido ya este cargado (el update no hace nada si
-- ya vale 12).
--
-- El resto de los articulos de envase perdido quedan con contenido_caja
-- vacio a proposito: se completan a mano desde la pantalla /fichas.

alter table fichas_logistica add column if not exists envase_variable boolean not null default false;

comment on column fichas_logistica.envase_variable is 'Si es true, el envase de la ficha es solo referencia/default: se decide por compra. Si es false, el envase es fijo.';

update fichas_logistica fl
set contenido_caja = 12
from articulos a, clientes c
where fl.articulo_id = a.id
  and fl.cliente_id = c.id
  and c.nombre = 'Día'
  and a.nombre in ('Frutilla', 'Arándano');

-- ============================================================================
-- senas_valor_historial: historial de VERDAD. Sacar el UNIQUE por fecha.
--
-- Corrige una decisión de agregar_senas_valor_historial.sql. El UNIQUE
-- (tipo_envase_id, vigente_desde) obligaba a que recargar una fecha ya
-- cargada fuera un UPDATE: el monto anterior desaparecía sin rastro, en
-- una tabla que decía ser append-only.
--
-- Por qué no alcanzaba con rechazar la fecha repetida: un tipeo del MISMO
-- día no tendría arreglo. Si hoy se carga 7000 en vez de 700, las señas
-- que se reciban hoy quedan ancladas a la fecha de hoy, que ya está
-- ocupada por el número mal; cargar la corrección con la fecha de mañana
-- no arregla el día de hoy, y eso es plata que se le paga a un proveedor.
--
-- Sin el UNIQUE, recargar la misma fecha AGREGA una fila. Gana la más
-- nueva por creado_en, y la vieja queda a la vista en el historial. Nada
-- se pisa y nada se pierde.
--
-- El índice reemplaza al que creaba el UNIQUE y sirve exactamente a la
-- resolución del vigente: por tipo, la fila de mayor vigente_desde que no
-- pase de la fecha buscada, y entre las de esa misma fecha la última
-- cargada.
--
-- SE CORRE CON LA TABLA VACÍA en las dos bases, que es el momento más
-- barato que va a haber. El chequeo de abajo lo verifica: si alguien
-- cargó valores en el medio, la migración se ABORTA sin tocar nada, y
-- entonces hay que decidir a mano qué hacer con las filas repetidas
-- (dropear el UNIQUE con filas adentro es seguro, pero conviene mirarlas
-- antes de que dejen de ser únicas por fecha).
--
-- NO rompe el código desplegado: hoy nada lee esta tabla.
-- ============================================================================

begin;

-- Freno de mano: si la tabla dejó de estar vacía, esto corta la
-- transacción y no se aplica nada.
do $$
begin
    if exists (select 1 from senas_valor_historial) then
        raise exception 'senas_valor_historial ya tiene filas: pará y revisá antes de sacar el UNIQUE';
    end if;
end $$;

alter table senas_valor_historial
    drop constraint senas_valor_historial_tipo_envase_id_vigente_desde_key;

create index senas_valor_historial_vigente_idx
    on senas_valor_historial (tipo_envase_id, vigente_desde desc, creado_en desc);

comment on table senas_valor_historial is 'Valor de la seña de cada tipo de envase del puesto, con historial por fecha de vigencia. Append-only de verdad: nada se borra ni se pisa. Cargar de nuevo una fecha ya cargada agrega otra fila; gana la de creado_en más alto y la anterior queda visible en el historial. Un tipo sin filas no vale 0: no tiene valor cargado.';
comment on column senas_valor_historial.vigente_desde is 'Desde qué día rige este monto. Se resuelve por (vigente_desde DESC, creado_en DESC) contra la fecha de la RECEPCIÓN (vacios_recibidos.creado_en::date), no la fecha del pago: la fila de mayor vigencia que no pase de ese día y, entre las de esa misma fecha, la última cargada.';

commit;

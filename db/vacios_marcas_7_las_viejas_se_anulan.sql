do $$
declare v_ofensores int;
begin
  select count(*) into v_ofensores from vacios_deposito_devoluciones
   where compra_id is null and btrim(coalesce(foto_ruta, '')) = '';
  if v_ofensores > 0 then
    raise exception 'hay % devoluciones SIN compra y SIN foto: no son del modelo viejo, revisar antes', v_ofensores;
  end if;
  alter table vacios_deposito_devoluciones drop constraint if exists vacios_dev_con_foto;
  alter table vacios_deposito_devoluciones add constraint vacios_dev_con_foto
    check (compra_id is not null or btrim(coalesce(foto_ruta, '')) <> '');
end $$;

-- ARREGLA vacios_marcas_5. Aquel CHECK corrió NOT VALID para dejar las
-- devoluciones viejas sin foto como estaban, y NOT VALID no alcanza: exime
-- a lo viejo SOLO del chequeo al crearse el constraint. Todo UPDATE
-- posterior se chequea, así que ANULAR una de las 13 viejas de Frutamax
-- rebotaba con un CheckViolation (verificado contra Postgres).
--
-- Lo que separa lo viejo de lo nuevo no es una fecha: es la COMPRA. Hasta
-- el 25/09 la devolución se cargaba contra una compra; desde el 25/09 sale
-- de una pila y el código no escribe compra_id nunca. O sea que "sin
-- compra" = modelo nuevo = foto obligatoria.
--
-- Y ahora va VALIDADO: la guarda de arriba aborta si hubiera alguna fila
-- sin compra y sin foto, así que el add no puede fallar a medias. Es
-- contenido: se borra y se recrea siempre.

do $$
begin
  alter table vacios_deposito_devoluciones drop constraint if exists vacios_dev_con_foto;
  alter table vacios_deposito_devoluciones add constraint vacios_dev_con_foto
    check (btrim(coalesce(foto_ruta, '')) <> '') not valid;
end $$;

-- SIN FOTO NO ES UNA DEVOLUCIÓN (dueño, 25/09): desde este bloque la base
-- rechaza una devolución de vacíos sin la foto del vale. Lo que no tiene foto
-- es un AJUSTE (vacios_deposito_ajustes, con motivo).
--
-- SE CORRE DESPUÉS DEL DEPLOY del código que ya exige la foto. Antes, frena
-- las devoluciones que el código de hoy deja cargar sin foto, y el operario
-- se come un error sin saber por qué.
--
-- NOT VALID a propósito: las devoluciones viejas sin foto quedan como están
-- (no se inventa una foto) y toda fila NUEVA lo cumple. Es contenido, así que
-- se borra y se recrea siempre.

do $$
declare
  t text;
  n bigint;
begin
  foreach t in array array['recepciones', 'aprendizaje_proveedores',
                           'pedidos_supermercado', 'precios_dia', 'resultados'] loop
    if to_regclass(t) is not null then
      execute format('select count(*) from %I', t) into n;
      if n > 0 then
        raise exception 'La tabla % tiene % filas: no se borra nada.', t, n;
      end if;
    end if;
  end loop;
  foreach t in array array['recepciones', 'aprendizaje_proveedores',
                           'pedidos_supermercado', 'precios_dia', 'resultados'] loop
    execute format('drop table if exists %I', t);
  end loop;
end $$;

-- Borra las cinco tablas VACÍAS del diseño original (db/schema.sql) que solo
-- existen en Frutamax. Ninguna la usa el código ni está en
-- db/esquema_completo.sql. Decisión del dueño, 28/09.
--
-- SE CORRE DESPUÉS DE QUE v1011 ESTÉ DESPLEGADA. v1010 consultaba
-- `recepciones` al borrar una compra, así que borrarla antes rompe ese
-- borrado también en Frutamax (en Palmala ya estaba roto: ahí no existe).
--
-- La guarda cuenta TODAS antes de borrar ninguna: si una sola tiene filas,
-- sale con error y no borra nada (un `do` es una sola sentencia). Sin
-- CASCADE: si algo depende de una de ellas, el DROP falla y no se borra
-- nada, en vez de llevarse puesto lo que dependa.
--
-- En Palmala no hace nada: ninguna existe. Se puede correr igual, para
-- confirmar que no explota. La verificación va APARTE, en
-- tablas_viejas_1_verificacion.sql.

do $$
begin
  if to_regclass('vales_correcciones') is null then
    raise exception 'falta vales_correcciones: corre primero vales_manual_2';
  end if;
  alter table vales_a_cobrar drop constraint if exists vales_origen_coherente;
  alter table vales_a_cobrar add constraint vales_origen_coherente check (
    (origen = 'devolucion' and devolucion_id is not null
      and proveedor_id is null and foto_ruta is null
      and (importe is null or importe > 0))
    or (origen in ('anterior_al_sistema', 'carga_manual') and devolucion_id is null
      and proveedor_id is not null and fecha is not null
      and coalesce(importe > 0, false) and importe_calculado is null));
  comment on column vales_a_cobrar.importe is
    'El IMPORTE DEL VALE: lo que dice el papel. En los de una devolucion es '
    'NULL hasta que Gerencia lo corrige, y mientras tanto vale el importe de '
    'la devolucion. importe_calculado no cambia nunca.';
  comment on column vales_a_cobrar.fecha is
    'La fecha del vale. En los de una devolucion es NULL hasta que Gerencia '
    'la corrige, y mientras tanto vale el dia de la devolucion.';
end $$;

-- VALES EDITABLES (duenio, 02/10), bloque unico.
--
-- Gerencia corrige importe, fecha y numero de CUALQUIER vale en cartera,
-- tambien los que nacen de una devolucion. En esos el importe y la fecha
-- dejan de tener que ser NULL: NULL sigue queriendo decir "el de la
-- devolucion", y un valor es la correccion. El importe vigente es
-- coalesce(vale.importe, devolucion.importe), igual que antes.
--
-- NINGUNA FILA CAMBIA: solo se reemplaza el CHECK (contenido: drop y
-- recrear, siempre) y dos comments. El proveedor y la foto de un vale de
-- devolucion siguen saliendo de la devolucion.
--
-- Se corre SOLO, en las dos bases. Verificacion aparte: vales_editables_2.

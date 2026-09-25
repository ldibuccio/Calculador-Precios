do $$
declare
  g record;
  nueva bigint;
begin
  if (select count(*) from pg_constraint
       where conrelid = 'guias_compra'::regclass and contype = 'u') <> 1 then
    raise exception 'corré primero guia_deposito_2: sigue el unique viejo';
  end if;

  update guias_compra gc set de_deposito = true
   where not gc.de_deposito
     and exists (select 1 from compras c where c.guia_id = gc.id)
     and not exists (select 1 from compras c where c.guia_id = gc.id
                      and c.retiro_origen is distinct from 'ingreso_directo');

  for g in select distinct gc.id, gc.fecha_operacion, gc.proveedor_id
             from guias_compra gc join compras c on c.guia_id = gc.id
            where not gc.de_deposito and c.retiro_origen = 'ingreso_directo' loop
    insert into guias_compra (fecha_operacion, proveedor_id, de_deposito)
      values (g.fecha_operacion, g.proveedor_id, true)
      on conflict (fecha_operacion, proveedor_id, de_deposito) do nothing;
    select id into nueva from guias_compra
     where fecha_operacion = g.fecha_operacion and proveedor_id = g.proveedor_id
       and de_deposito;
    update compras c set guia_id = nueva, guia_punto = s.punto
      from (select id, row_number() over (order by id)
                       + coalesce((select max(guia_punto) from compras where guia_id = nueva), 0) as punto
              from compras where guia_id = g.id and retiro_origen = 'ingreso_directo') s
     where c.id = s.id;
  end loop;

  if exists (select 1 from compras c join guias_compra gc on gc.id = c.guia_id
              where (c.retiro_origen is not distinct from 'ingreso_directo') <> gc.de_deposito) then
    raise exception 'quedaron compras en la guía equivocada: no se escribió nada';
  end if;
end $$;

-- SEPARA LO QUE YA QUEDÓ ENGANCHADO. Dos casos:
--   · una guía donde TODAS las compras son ingresos directos pasa a ser de
--     depósito (la creó Depósito);
--   · una guía MEZCLADA —la del Puesto con un ingreso directo adentro, que es
--     el caso de la Granny del 25/09— se parte: los ingresos directos se mudan
--     a su guía de depósito, numerados a continuación.
-- Las FOTOS no se mueven: son la comanda del Puesto y se quedan en su guía.
-- La guarda del final revisa TODAS las compras y aborta el bloque entero si
-- alguna quedó del lado equivocado. Corre DESPUÉS del deploy y del bloque 2.

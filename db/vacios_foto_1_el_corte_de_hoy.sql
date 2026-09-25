do $$
begin
  create table if not exists vacios_deposito_foto (
    proveedor_id  bigint primary key references proveedores (id),
    cantidad      integer not null,
    fecha         date    not null,
    creado_en     timestamptz not null default now()
  );
  if exists (select 1 from vacios_deposito_foto) then
    raise exception 'la foto ya está tomada: no se vuelve a sacar';
  end if;
  if exists (select 1 from compras where estado = 'recepcionado'
               and (procesada_el at time zone 'America/Argentina/Buenos_Aires')::date > date '2026-09-25')
     or exists (select 1 from vacios_deposito_devoluciones where anulado_el is null
               and (creado_en at time zone 'America/Argentina/Buenos_Aires')::date > date '2026-09-25') then
    raise exception 'ya hay movimientos posteriores al 25/09: la foto los contaría dos veces';
  end if;

  with base as (
    select distinct on (proveedor_id) proveedor_id, cantidad, fecha
      from conteos_vacios_deposito order by proveedor_id, fecha, id
  )
  insert into vacios_deposito_foto (proveedor_id, cantidad, fecha)
  select p.id,
         coalesce(b.cantidad
           + coalesce((select sum(coalesce(c.cantidad_cajones_real, c.cantidad_cajones))
                         from compras c
                        where c.proveedor_id = p.id and c.estado = 'recepcionado'
                          and c.procesada_el is not null
                          and (c.procesada_el at time zone 'America/Argentina/Buenos_Aires')::date >= b.fecha), 0)
           - coalesce((select sum(d.cantidad) from vacios_deposito_devoluciones d
                        where d.proveedor_id = p.id and d.anulado_el is null
                          and (d.creado_en at time zone 'America/Argentina/Buenos_Aires')::date >= b.fecha), 0),
           0),
         date '2026-09-25'
    from proveedores p
    left join base b on b.proveedor_id = p.id;

  comment on table vacios_deposito_foto is 'Stock de vacíos del depósito al cierre del 25/09, como lo mostraba el sistema. Desde ahí suma lo recibido con seña y resta lo devuelto.';
end $$;

-- EL CORTE ES HOY (dueño, 25/09). La foto de cada proveedor es el stock que
-- el sistema muestra ahora —conteo + recepciones − devoluciones desde el
-- conteo, la misma cuenta que la pantalla— y desde el 26/09 corre la regla
-- nueva. Un proveedor sin conteo entra en 0. Las dos guardas abortan el
-- bloque entero: si la foto ya está, y si ya entró algo después del 25/09.

do $$
begin
  create table if not exists proveedores_codigos (
    id           bigint generated always as identity primary key,
    proveedor_id bigint not null references proveedores (id),
    codigo       text   not null unique
                 check (codigo ~ '^[NL][0-9]{2}P[0-9]{2}$'),
    creado_en    timestamptz not null default now()
  );
  create index if not exists proveedores_codigos_proveedor_idx
    on proveedores_codigos (proveedor_id);

  alter table compras add column if not exists codigo_llegada text;
  alter table compras drop constraint if exists compras_codigo_llegada_formato;
  alter table compras add constraint compras_codigo_llegada_formato
    check (codigo_llegada is null or codigo_llegada ~ '^[NL][0-9]{2}P[0-9]{2}$');

  create or replace function codigo_de_puesto_unico() returns trigger
  language plpgsql as $f$
  begin
    if tg_table_name = 'proveedores_codigos' then
      if exists (select 1 from proveedores where codigo_puesto = new.codigo) then
        raise exception 'el codigo % ya es el principal de otro proveedor', new.codigo
          using errcode = '23505';
      end if;
    elsif exists (select 1 from proveedores_codigos where codigo = new.codigo_puesto) then
      raise exception 'el codigo % ya es alternativo de otro proveedor', new.codigo_puesto
        using errcode = '23505';
    end if;
    return new;
  end $f$;

  drop trigger if exists codigo_unico_alternativo on proveedores_codigos;
  create trigger codigo_unico_alternativo before insert or update of codigo
    on proveedores_codigos for each row execute function codigo_de_puesto_unico();
  drop trigger if exists codigo_unico_principal on proveedores;
  create trigger codigo_unico_principal before insert or update of codigo_puesto
    on proveedores for each row execute function codigo_de_puesto_unico();
end $$;

-- VARIOS CÓDIGOS DE PUESTO PARA UN PROVEEDOR (dueño, 27/09). Bloque 1 de 4.
-- proveedores.codigo_puesto sigue siendo el PRINCIPAL; los otros van acá.
-- Un código es de UN solo proveedor, contando principales y alternativos: el
-- unique de cada tabla cubre su lado y el trigger cruza las dos (lo decide la
-- base, 23505 como cualquier unique). compras.codigo_llegada: por qué puesto
-- llegó esa compra, que es lo que Logística y Recepción muestran.

do $$
begin
  if to_regclass('vales_a_cobrar') is null then
    raise exception 'falta vales_a_cobrar: corre primero vales_1';
  end if;
  if to_regclass('vales_correcciones') is not null then
    raise exception 'vales_correcciones ya existe: este bloque ya corrio';
  end if;
  create table vales_correcciones (
    id bigint generated always as identity primary key,
    vale_id bigint not null references vales_a_cobrar (id),
    campo text not null check (campo in ('importe', 'numero', 'fecha', 'proveedor')),
    valor_anterior text,
    valor_nuevo text,
    sector text not null check (sector = 'gerencia'),
    creado_en timestamptz not null default now(),
    constraint vales_correcciones_distinto
      check (valor_anterior is distinct from valor_nuevo)
  );
  create index vales_correcciones_por_vale on vales_correcciones (vale_id);
  comment on table vales_correcciones is
    'Lo que Gerencia le corrigio a un vale cargado mal (importe, numero, fecha '
    'o proveedor): el valor anterior, el nuevo, cuando y el sector. No se borra. '
    'Un vale no se anula: se corrige.';
end $$;

-- VALES, CARGA MANUAL (duenio, 02/10), bloque 2 de 3: el historial de las
-- correcciones. Solo Gerencia corrige (la base exige sector 'gerencia'), y
-- solo un vale EN CARTERA con datos propios (anterior al sistema o carga
-- manual): el de una devolucion lee sus datos de la devolucion. Un valor por
-- fila; el numero puede pasar a vacio (NULL), por eso las dos columnas son
-- nullables y lo unico que se exige es que cambien.
--
-- Se corre despues del bloque 1, SOLO. Verificacion: vales_manual_4.

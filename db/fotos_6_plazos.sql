do $$
begin
  if to_regclass('fotos_plazos') is not null then
    raise exception 'fotos_plazos ya existe: este bloque ya corrio';
  end if;
  create table fotos_plazos (
    tipo text primary key check (btrim(tipo) <> ''),
    anios integer not null check (anios between 1 and 30),
    actualizado_el timestamptz not null default now()
  );
  comment on table fotos_plazos is
    'Cuantos anios se guarda cada TIPO de foto antes de vencer (duenio, 01/10). '
    'Se edita desde Gerencia -> Fotos y espacio. Un tipo SIN fila vence a los '
    '3 anios, que es la regla de siempre: el 3 vive en core/fotos.py y no aca.';
end $$;

-- FOTOS (duenio, 01/10), bloque 6: el plazo por tipo.
--
-- Nace VACIA a proposito: el 3 por defecto esta escrito una vez, en el
-- codigo (ANIOS_DE_RESPALDO). Sembrar ocho filas con 3 seria el mismo numero
-- en dos lugares, y la copia que se separe deja un tipo venciendo distinto
-- de lo que dice la pantalla. tipo es la clave de _SQL_FOTOS_DE_RESPALDO.

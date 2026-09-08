-- El indice unico del codigo de cliente pasa a plegar tildes, EÑE y espacios
-- internos, para que la base y normalizar_texto (core/matcheo_comanda.py) sean
-- UNA regla y no dos. Hoy CÓD-2 y COD-2 entran los dos y el matcheo los ve
-- iguales: el sistema elige una ficha en silencio, que es justo lo que el
-- comentario de este indice dice que viene a impedir. Ver docs/.
-- translate y no unaccent: la extension se habilita por proyecto y la base de
-- la empresa que venga naceria sin la regla, en silencio.
-- La lista es Latin-1 + Latin Extended-A ENTERA, no los cinco acentos del
-- español: una lista a medias es media regla, y ya nos mordio con 'ÿ'.
-- UN solo do $$ porque el drop y el create son todo-o-nada: sueltos, un create
-- que rebota deja la tabla SIN indice y nada avisa.
do $$
declare
  expr text := $q$lower(regexp_replace(translate(btrim(codigo_cliente),
    'ÀÁÂÃÄÅÇÈÉÊËÌÍÎÏÑÒÓÔÕÖÙÚÛÜÝàáâãäåçèéêëìíîïñòóôõöùúûüýÿĀāĂăĄąĆćĈĉĊċČčĎďĒēĔĕĖėĘęĚěĜĝĞğĠġĢģĤĥĨĩĪīĬĭĮįİĴĵĶķĹĺĻļĽľŃńŅņŇňŌōŎŏŐőŔŕŖŗŘřŚśŜŝŞşŠšŢţŤťŨũŪūŬŭŮůŰűŲųŴŵŶŷŸŹźŻżŽž',
    'AAAAAACEEEEIIIINOOOOOUUUUYaaaaaaceeeeiiiinooooouuuuyyAaAaAaCcCcCcCcDdEeEeEeEeEeGgGgGgGgHhIiIiIiIiIJjKkLlLlLlNnNnNnOoOoOoRrRrRrSsSsSsSsTtTtUuUuUuUuUuUuWwYyYZzZzZz'), '\s+', ' ', 'g'))$q$;
  filtro text := $q$codigo_cliente is not null and btrim(codigo_cliente) <> ''$q$;
  chocan int;
begin
  execute format('select count(*) from (select 1 from fichas_logistica
    where %s group by cliente_id, %s having count(*) > 1) t',
    filtro, expr) into chocan;
  if chocan > 0 then
    raise exception 'HAY % codigos que chocan al plegar: limpiar primero', chocan;
  end if;
  drop index if exists fichas_logistica_codigo_cliente_unico;
  execute format('create unique index fichas_logistica_codigo_cliente_unico
    on fichas_logistica (cliente_id, %s) where %s', expr, filtro);
  execute format('comment on index fichas_logistica_codigo_cliente_unico is %L',
    'Dos fichas del mismo cliente no pueden compartir el codigo. Pliega ' ||
    'mayusculas, tildes, eñe y espacios igual que normalizar_texto en ' ||
    'core/matcheo_comanda.py, que es quien matchea el codigo del pedido ' ||
    'contra la ficha: si se separan, el sistema elige una en silencio.');
end $$;

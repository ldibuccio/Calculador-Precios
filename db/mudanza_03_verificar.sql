-- ============================================================================
-- MUDANZA DE BASE, PASO 3 de 4: verificar que la nueva quedó igual que la vieja
-- ============================================================================
-- Se corre en el SQL Editor de la base NUEVA, después del paso 2, y ANTES de
-- tocar el DATABASE_URL de Railway. Es de SOLO LECTURA: no escribe nada.
--
-- Devuelve UNA sola tabla, con el veredicto en la última fila. Va así a
-- propósito: el SQL Editor de Supabase muestra únicamente el resultado de la
-- ÚLTIMA consulta, así que un verificador que devuelva varias deja lo
-- importante invisible.
--
-- POR QUÉ NO ALCANZA CON CONTAR FILAS: probado — las dos tablas del plan de
-- cuentas de Costos Fijos dan 8 y 34 filas en las dos bases aunque la copia
-- haya fallado, porque esas filas las siembra esquema_completo.sql. El conteo
-- dice OK y la copia está mal. Por eso va también la firma md5 del contenido.
--
-- LA EXCEPCIÓN — revision_tick: es el latido del bucle de revisión
-- automática, una sola fila que la app viva actualiza cada vez que despierta.
-- Mientras Railway siga apuntando a la base vieja, esa fila avanza sola entre
-- la copia y esta verificación, SIEMPRE. Se informa aparte y no entra en el
-- veredicto: un veredicto que da rojo todas las veces por algo que no importa
-- enseña a ignorar el veredicto. Después del corte la app escribe su propio
-- latido en la base nueva a los pocos minutos.
--
-- POR QUÉ LA FIRMA NOMBRA LAS COLUMNAS: las dos bases tienen las mismas
-- columnas pero NO en el mismo orden (lo agregado con ALTER TABLE quedó al
-- final en la vieja). Una firma sobre la fila entera cambiaría solo por el
-- orden y marcaría como distinta una tabla copiada perfecto.
-- ============================================================================

create temp table if not exists mudanza_control (
    tabla text, filas_vieja bigint, filas_nueva bigint, firma_vieja text, firma_nueva text
);
create temp table if not exists mudanza_resultado (
    orden int, control text, resultado text
);
truncate mudanza_control;
truncate mudanza_resultado;

-- ----------------------------------------------------------------------------
-- 1. Contenido de cada tabla, en las dos bases.
-- ----------------------------------------------------------------------------
do $contenido$
declare t text; columnas text;
begin
    for t in
        select c.relname from pg_class c
          join pg_namespace n on n.oid = c.relnamespace and n.nspname = 'public' and c.relkind = 'r'
         where c.relname not like 'mudanza\_%'
         order by c.relname
    loop
        select string_agg(quote_ident(column_name), ', ' order by ordinal_position)
          into columnas
          from information_schema.columns
         where table_schema = 'public' and table_name = t;

        execute format($sql$
            insert into mudanza_control
            select %L,
                   (select count(*) from origen.%I),
                   (select count(*) from public.%I),
                   (select md5(string_agg(x::text, '|' order by x::text)) from (select %s from origen.%I) x),
                   (select md5(string_agg(x::text, '|' order by x::text)) from (select %s from public.%I) x)
        $sql$, t, t, t, columnas, t, columnas, t);
    end loop;
end $contenido$;

-- Las tablas que la app viva mueve sola, y que por eso no bloquean.
create temp table if not exists mudanza_volatiles (tabla text);
truncate mudanza_volatiles;
insert into mudanza_volatiles values ('revision_tick');

-- Cuenta las 40 tablas y todas las filas; para decidir si algo está MAL
-- excluye las volátiles, que se informan aparte en la línea del LATIDO.
insert into mudanza_resultado
select 10, 'CONTENIDO',
       case when count(*) filter (where malas) = 0
            then 'OK — ' || count(*) || ' tablas, ' || sum(filas_nueva) || ' filas, idénticas a la vieja'
            else count(*) filter (where malas) || ' TABLA(S) MAL — ver abajo' end
  from (select *,
               (tabla not in (select tabla from mudanza_volatiles)
                and (filas_vieja is distinct from filas_nueva
                  or firma_vieja is distinct from firma_nueva)) as malas
          from mudanza_control) x;

insert into mudanza_resultado
select 11, '  ' || tabla,
       case when filas_vieja is distinct from filas_nueva
            then 'vieja ' || filas_vieja || ' filas / nueva ' || filas_nueva
            else 'mismo conteo (' || filas_nueva || ') pero el CONTENIDO difiere' end
  from mudanza_control
 where tabla not in (select tabla from mudanza_volatiles)
   and (filas_vieja is distinct from filas_nueva
     or firma_vieja is distinct from firma_nueva);

-- El latido, informado aparte: cambia solo y no bloquea nada.
insert into mudanza_resultado
select 15, 'LATIDO',
       case when firma_vieja is distinct from firma_nueva
            then 'revision_tick difiere, y está BIEN: la app viva lo mueve sola. No bloquea.'
            else 'revision_tick igual (la app no latió entre la copia y esta consulta).' end
  from mudanza_control
 where tabla = 'revision_tick';

-- ----------------------------------------------------------------------------
-- 2. Secuencias: ninguna puede quedar por debajo del max(id) de su tabla, o
--    el primer INSERT nuevo choca con "duplicate key".
-- ----------------------------------------------------------------------------
do $secuencias$
declare r record; maximo bigint; ultimo bigint; llamada boolean; proximo bigint; mal int := 0;
begin
    for r in
        select c.relname as tabla, a.attname as columna,
               pg_get_serial_sequence('public.' || c.relname, a.attname) as secuencia
          from pg_class c
          join pg_namespace n on n.oid = c.relnamespace and n.nspname = 'public' and c.relkind = 'r'
          join pg_attribute a on a.attrelid = c.oid and a.attnum > 0 and not a.attisdropped
         where pg_get_serial_sequence('public.' || c.relname, a.attname) is not null
         order by c.relname
    loop
        execute format('select coalesce(max(%I), 0) from public.%I', r.columna, r.tabla) into maximo;
        execute format('select last_value, is_called from %s', r.secuencia) into ultimo, llamada;
        proximo := case when llamada then ultimo + 1 else ultimo end;
        if proximo <= maximo then
            mal := mal + 1;
            insert into mudanza_resultado values (21, '  ' || r.tabla,
                'max(id)=' || maximo || ' pero la secuencia daría ' || proximo);
        end if;
    end loop;
    insert into mudanza_resultado values (20, 'SECUENCIAS',
        case when mal = 0 then 'OK — las 37 por encima de su max(id)'
             else mal || ' MAL — volvé a correr el paso 2' end);
end $secuencias$;

-- ----------------------------------------------------------------------------
-- 3. Storage: los archivos NO viajan con la base. Hasta que se copie el
--    bucket, esto va a decir que faltan, y está bien.
-- ----------------------------------------------------------------------------
do $storage$
declare en_bucket bigint; referenciados bigint;
begin
    -- Las rutas viven en TRES lugares, no dos: las comandas de las guías, las
    -- fotos de los pedidos y los archivos de los que salió cada precio. Y se
    -- cuentan DISTINTAS: un mismo archivo puede colgar de varias guías (el
    -- Listado consolidado comparte una foto entre proveedores).
    select count(*) into referenciados from (
        select foto_ruta from fotos_guia
        union
        select foto_ruta from fotos_pedido
        union
        select foto_ruta from precios_venta_historial where foto_ruta is not null
    ) rutas;
    if to_regclass('storage.objects') is null then
        en_bucket := -1;
    else
        execute 'select count(*) from storage.objects where bucket_id = ''comandas''' into en_bucket;
    end if;
    insert into mudanza_resultado values (30, 'STORAGE',
        case when en_bucket >= referenciados
             then 'OK — ' || en_bucket || ' archivos en el bucket, ' || referenciados || ' referenciados'
             else 'FALTAN ARCHIVOS — ' || en_bucket || ' en el bucket, ' || referenciados ||
                  ' referenciados. Copiar el bucket (no bloquea la copia de datos).' end);
end $storage$;

-- ----------------------------------------------------------------------------
-- 4. El veredicto. El Storage no bloquea: se puede copiar después.
-- ----------------------------------------------------------------------------
insert into mudanza_resultado
select 99, '>>> VEREDICTO',
       case when (select count(*) from mudanza_resultado where orden in (11, 21)) = 0
            then 'LA BASE NUEVA ES UN ESPEJO EXACTO DE LA VIEJA'
            else 'HAY PROBLEMAS ARRIBA — NO cambies el DATABASE_URL' end;

select control, resultado from mudanza_resultado order by orden, control;

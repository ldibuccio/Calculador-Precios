-- ============================================================================
-- MUDANZA DE BASE, PASO 3 de 4: verificar que la nueva quedó igual que la vieja
-- ============================================================================
-- Se corre en el SQL Editor de la base NUEVA, después del paso 2, y ANTES de
-- tocar el DATABASE_URL de Railway. Es de SOLO LECTURA: no escribe nada.
--
-- Devuelve cuatro resultados. Los cuatro tienen que dar bien.
--
-- POR QUÉ NO ALCANZA CON CONTAR FILAS: probado en local — las dos tablas del
-- plan de cuentas de Costos Fijos dan 8 y 34 filas en las dos bases aunque la
-- copia haya fallado, porque esas filas las siembra esquema_completo.sql. El
-- conteo dice OK y la copia está mal. Por eso va también la firma md5 del
-- contenido, que sí lo detecta.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. CONTENIDO: conteo y firma de cada tabla, en las dos bases.
--    TIENE QUE DEVOLVER 0 FILAS.
-- ----------------------------------------------------------------------------
create temp table if not exists mudanza_control (
    tabla text, filas_vieja bigint, filas_nueva bigint, firma_vieja text, firma_nueva text
);
truncate mudanza_control;

do $verificar$
declare t text;
begin
    for t in
        select c.relname from pg_class c
          join pg_namespace n on n.oid = c.relnamespace and n.nspname = 'public' and c.relkind = 'r'
         where c.relname <> 'mudanza_control'
         order by c.relname
    loop
        execute format($sql$
            insert into mudanza_control
            select %L,
                   (select count(*) from origen.%I),
                   (select count(*) from public.%I),
                   (select md5(string_agg(x::text, '|' order by x::text)) from origen.%I x),
                   (select md5(string_agg(x::text, '|' order by x::text)) from public.%I x)
        $sql$, t, t, t, t, t);
    end loop;
end $verificar$;

select tabla, filas_vieja, filas_nueva,
       case when filas_vieja <> filas_nueva then 'DIFIERE EL CONTEO'
            else 'MISMO CONTEO, CONTENIDO DISTINTO' end as problema
  from mudanza_control
 where filas_vieja is distinct from filas_nueva
    or firma_vieja is distinct from firma_nueva
 order by tabla;

-- ----------------------------------------------------------------------------
-- 2. RESUMEN: una línea para mirar de reojo desde el celular.
--    TIENE QUE DECIR "TODO IGUAL".
-- ----------------------------------------------------------------------------
select case
         when count(*) filter (where filas_vieja is distinct from filas_nueva
                                  or firma_vieja is distinct from firma_nueva) = 0
           then 'TODO IGUAL: ' || count(*) || ' tablas, ' || sum(filas_nueva) || ' filas.'
         else 'HAY ' || count(*) filter (where filas_vieja is distinct from filas_nueva
                                            or firma_vieja is distinct from firma_nueva)
              || case when count(*) filter (where filas_vieja is distinct from filas_nueva
                                              or firma_vieja is distinct from firma_nueva) = 1
                      then ' TABLA MAL' else ' TABLAS MAL' end
              || '. NO cambies el DATABASE_URL.'
       end as resultado
  from mudanza_control;

-- ----------------------------------------------------------------------------
-- 3. SECUENCIAS: ninguna puede quedar por debajo del max(id) de su tabla.
--    TIENE QUE DECIR OK. Si no, el primer INSERT nuevo choca.
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
            raise notice 'MAL  %: max(id)=%, la secuencia daría %', r.tabla, maximo, proximo;
        end if;
    end loop;
    if mal = 0 then
        raise notice 'SECUENCIAS OK: todas por encima de su max(id).';
    else
        raise notice '% mal. Volvé a correr el paso 2.',
            mal || case when mal = 1 then ' SECUENCIA' else ' SECUENCIAS' end;
    end if;
end $secuencias$;

-- ----------------------------------------------------------------------------
-- 4. STORAGE: cuántos archivos hay en el bucket de cada lado.
--    Los BYTES no viajan con la base: esto se empareja recién después de
--    copiar el bucket (ver el paso de Storage en db/MUDANZA.md).
--    Mientras no lo hagas, la nueva va a dar 0. Es lo esperado.
-- ----------------------------------------------------------------------------
-- El conteo del bucket va por SQL dinámico a propósito: nombrar
-- storage.objects directo hace fallar la consulta entera en un Postgres común
-- (sin Supabase), aunque la rama no se ejecute — se resuelve al parsear.
-- Si da -1, es que no estás en Supabase.
create temp table if not exists mudanza_storage (archivos bigint);
truncate mudanza_storage;

do $storage$
begin
    if to_regclass('storage.objects') is null then
        insert into mudanza_storage values (-1);
    else
        execute 'insert into mudanza_storage select count(*) from storage.objects where bucket_id = ''comandas''';
    end if;
end $storage$;

select (select archivos from mudanza_storage) as archivos_en_el_bucket,
       (select count(*) from fotos_guia) as filas_fotos_guia,
       (select count(*) from fotos_pedido) as filas_fotos_pedido,
       (select count(*) from precios_venta_historial where foto_ruta is not null) as precios_con_archivo;

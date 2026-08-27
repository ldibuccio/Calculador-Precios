-- ============================================================================
-- MUDANZA DE BASE, PASO 2 de 4: copiar los datos
-- ============================================================================
-- Se corre en el SQL Editor de la base NUEVA, después del paso 1.
--
-- QUÉ HACE: vacía las 40 tablas de la base nueva y copia las de la vieja tal
-- cual, con los MISMOS ids, en orden de dependencias, y deja las secuencias
-- donde corresponde. Todo adentro de un bloque DO, que es UNA sola sentencia:
-- o entra todo o no entra nada. No hay estado a medias.
--
-- ES IDEMPOTENTE: se puede correr las veces que haga falta. Cada corrida deja
-- la base nueva como un espejo exacto de la vieja en ese momento. Si algo
-- falla, se arregla y se corre de nuevo, sin limpiar nada a mano.
--
-- POR QUÉ VACÍA PRIMERO: la base nueva NO nace vacía. db/esquema_completo.sql
-- siembra el plan de cuentas de Costos Fijos (8 grupos y 34 subcuentas, con
-- sus ids). Si no se vacía, esas dos tablas chocan contra la primary key —
-- comprobado — y peor todavía, importes_costos_fijos entra igual apuntando a
-- subcuentas que son OTRAS filas. Por eso se vacía todo y se copia todo.
--
-- EL CANDADO: la primera línea tiene que estar, y es a propósito. Sin ella el
-- script se niega a correr. Es lo único que separa esto de vaciar por error
-- una base que ya está en producción. NO la dejes en un script que corras por
-- costumbre.
--
-- CUÁNDO CORRERLO: con el sistema quieto — nadie cargando compras, pedidos ni
-- precios. Lo que se cargue en la vieja DESPUÉS de esta corrida no está en la
-- nueva; si pasa, se corre de nuevo y listo (por eso es idempotente).
-- ============================================================================

select set_config('mudanza.confirmo', 'SI, VACIAR Y COPIAR', false);

-- El SQL Editor de Supabase no muestra los mensajes NOTICE, así que el
-- resultado se junta acá y se devuelve como tabla al final.
create temp table if not exists mudanza_copia (orden int, tabla text, filas bigint);
truncate mudanza_copia;

do $mudanza$
declare
    -- Las 40 tablas en orden de dependencias: cada una solo referencia a las
    -- anteriores. Sacado del esquema real, no escrito a mano.
    tablas text[] := array[
        'articulos', 'clientes', 'clientes_puesto',
        'envases', 'grupos_costos_fijos', 'indices_inflacion',
        'proveedores', 'proveedores_puesto', 'revision_tick',
        'aprendizaje_articulos', 'casillas_pedidos', 'clientes_condiciones_pedido',
        'clientes_parametros_historial', 'conteos_stock', 'dias_sin_pedido',
        'disponibles', 'envases_costo_historial', 'fichas_logistica',
        'fichas_logistica_historial', 'guias_compra', 'pedidos',
        'remitos_segunda', 'reprocesos', 'subcuentas_costos_fijos',
        'tipos_envase_puesto', 'ajustes_vacios', 'compras',
        'conteos_vacios', 'disponibles_detalle', 'fotos_guia',
        'fotos_pedido', 'importes_costos_fijos', 'mails_pedido',
        'pedidos_renglones', 'pedidos_sucursales', 'precios_venta_historial',
        'vacios_devueltos', 'vacios_recibidos', 'movimientos_stock',
        'reprocesos_consumos'
    ];
    t text;
    r record;
    maximo bigint;
    copiadas bigint;
    total bigint := 0;
    n int := 0;
    columnas text;
    faltantes text;
begin
    if coalesce(current_setting('mudanza.confirmo', true), '') <> 'SI, VACIAR Y COPIAR' then
        raise exception 'Falta el candado. Corré el select set_config(...) de arriba JUNTO con este bloque, en la misma pestaña del SQL Editor.';
    end if;

    -- 1. Antes de tocar nada: toda columna que exista en la base NUEVA tiene
    -- que existir también en la vieja. Si falta alguna, la copia sería
    -- incompleta en silencio, así que se corta acá y se dice cuál.
    -- (Al revés no importa: si la vieja tiene columnas de más — restos de
    -- migraciones viejas — simplemente no se copian.)
    select string_agg(d.table_name || '.' || d.column_name, ', ' order by d.table_name, d.column_name)
      into faltantes
      from information_schema.columns d
     where d.table_schema = 'public'
       and d.table_name = any(tablas)
       and not exists (select 1 from information_schema.columns o
                        where o.table_schema = 'origen'
                          and o.table_name = d.table_name
                          and o.column_name = d.column_name);
    if faltantes is not null then
        raise exception 'La base vieja no tiene estas columnas, que la nueva sí: %', faltantes;
    end if;

    -- 2. Vaciar. Una sola sentencia con las 40: TRUNCATE resuelve solo el
    -- orden entre ellas. CASCADE está por las FKs entre las de la lista.
    execute 'truncate table ' || array_to_string(tablas, ', ') || ' cascade';

    -- 3. Copiar, en orden. OVERRIDING SYSTEM VALUE porque los ids son
    -- "generated always" y acá entran tal cual vienen: es lo que hace que
    -- todas las FKs queden bien apuntadas sin remapear nada, y lo que
    -- conserva los números de guía de compra y de guía R, que vos ves.
    --
    -- Las columnas se nombran UNA POR UNA, nunca "select *". Las dos bases
    -- tienen las mismas columnas pero NO en el mismo orden: en la vieja, lo
    -- que se agregó con ALTER TABLE quedó al final, y en esquema_completo.sql
    -- está escrito en su lugar lógico. Con "select *" el mapeo es por
    -- posición y termina metiendo una fecha adentro de un booleano.
    -- Nombrándolas, el mapeo es por nombre y el orden deja de importar.
    --
    -- El "order by 1" es por pedidos.reemplaza_a_pedido_id, que apunta a otro
    -- pedido: sin orden, la fila que referencia podría entrar antes que la
    -- referenciada y la FK fallaría.
    foreach t in array tablas loop
        select string_agg(quote_ident(column_name), ', ' order by ordinal_position)
          into columnas
          from information_schema.columns
         where table_schema = 'public' and table_name = t;

        execute format('insert into public.%I (%s) overriding system value select %s from origen.%I order by 1',
                       t, columnas, columnas, t);
        get diagnostics copiadas = row_count;
        total := total + copiadas;
        n := n + 1;
        insert into mudanza_copia values (n, t, copiadas);
    end loop;

    -- 4. Las secuencias. Sin esto el primer INSERT nuevo choca con
    -- "duplicate key": la secuencia sigue en 1 y el id 1 ya existe.
    -- setval(..., max + 1, false) deja el PRÓXIMO id en max+1, y funciona
    -- también con la tabla vacía (próximo = 1).
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
        perform setval(r.secuencia, maximo + 1, false);
    end loop;

    insert into mudanza_copia values (0,
        'COPIADO: ' || total || ' filas en ' || array_length(tablas, 1) ||
        ' tablas. Secuencias ajustadas. Ahora corré el paso 3.', total);
end $mudanza$;

-- El resultado, visible en el SQL Editor. La fila de orden 0 es el resumen.
select case when orden = 0 then tabla else '  ' || tabla end as tabla,
       filas
  from mudanza_copia
 order by orden;

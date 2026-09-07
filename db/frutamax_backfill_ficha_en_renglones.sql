-- ============================================================================
-- BACKFILL DE FRUTAMAX: el renglón de pedido recupera su ficha por código
-- ============================================================================
-- APLICADO EN FRUTAMAX. Se trae al repo el 07/09, DESPUÉS de haberse corrido:
-- se mandó por chat y nunca quedó versionado, que rompe la regla del proyecto
-- ("el SQL va en db/"). El costo se cobró solo: al escribir el equivalente
-- para Palmala hubo que reconstruir las guardas de memoria en vez de copiarlas.
--
-- EL TEXTO ES EL QUE CORRIÓ, recuperado del transcript y sin retocar. No se
-- "mejoró" al traerlo: un script aplicado se archiva como se aplicó, o deja de
-- servir para saber qué le pasó a la base.
--
-- Objetivo 616: los renglones sin ficha que había en Frutamax al momento de
-- correrlo. Cuatro cierres tenían que dar todos — conteo previo = 616, cero
-- ambiguos, cero cruzados, y tocados = 616.
--
-- Diferencias con el de Palmala (db/palmala_2_backfill_ficha.sql), por si
-- alguien compara:
--   - Éste normaliza con lower(btrim(...)), el MISMO criterio que el índice
--     fichas_logistica_codigo_cliente_unico. El de Palmala además pliega
--     tildes, para imitar normalizar_texto (core/matcheo_comanda.py). La
--     diferencia solo puede dejar algo AFUERA, nunca elegir mal.
--   - Éste exige articulo_id not null; el de Palmala acepta el renglón sin
--     artículo y se lo escribe desde la ficha.
--   - Éste corre sobre TODOS los clientes; el de Palmala se acota a uno.
-- ============================================================================

do $$
declare
    objetivo constant int := 616;
    faltan int; ambiguos int; cruzados int; tocados int;
begin
    select count(*) into faltan from pedidos_renglones
     where anulado_el is null and articulo_id is not null and ficha_id is null;
    if faltan <> objetivo then
        raise exception 'Hay % renglones sin ficha y esperaba %: corre el L de nuevo antes de tocar nada', faltan, objetivo;
    end if;

    -- Cinturon: el indice unico fichas_logistica_codigo_cliente_unico ya
    -- impide que dos fichas del mismo cliente compartan codigo.
    select count(*) into ambiguos from (
        select r.id from pedidos_renglones r
        join pedidos p on p.id = r.pedido_id
        join fichas_logistica f on f.cliente_id = p.cliente_id
         and lower(btrim(f.codigo_cliente)) = lower(btrim(r.texto_codigo))
        where r.anulado_el is null and r.articulo_id is not null
          and r.ficha_id is null
        group by r.id having count(*) > 1) x;
    if ambiguos > 0 then
        raise exception '% renglones matchean mas de una ficha', ambiguos;
    end if;

    -- La ficha tiene que ser del MISMO articulo que el renglon ya tiene:
    -- asignar una de otro articulo moveria stock de un lado al otro.
    select count(*) into cruzados from pedidos_renglones r
    join pedidos p on p.id = r.pedido_id
    join fichas_logistica f on f.cliente_id = p.cliente_id
     and lower(btrim(f.codigo_cliente)) = lower(btrim(r.texto_codigo))
    where r.anulado_el is null and r.articulo_id is not null
      and r.ficha_id is null and f.articulo_id <> r.articulo_id;
    if cruzados > 0 then
        raise exception '% renglones matchean ficha de OTRO articulo', cruzados;
    end if;

    update pedidos_renglones r set ficha_id = f.id
      from pedidos p, fichas_logistica f
     where p.id = r.pedido_id and f.cliente_id = p.cliente_id
       and lower(btrim(f.codigo_cliente)) = lower(btrim(r.texto_codigo))
       and f.articulo_id = r.articulo_id
       and r.anulado_el is null and r.articulo_id is not null
       and r.ficha_id is null;
    get diagnostics tocados = row_count;
    if tocados <> objetivo then
        raise exception 'Actualizo % y esperaba %', tocados, objetivo;
    end if;
end $$;

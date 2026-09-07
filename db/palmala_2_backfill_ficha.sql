-- BLOQUE 2 de 3 — EL BACKFILL. Todo-o-nada: un do es UNA sentencia, así que
-- si la guarda salta no queda nada escrito. Correr SOLO si el bloque 1 dio
-- ambiguos = 0 y cruzados = 0, y poner acá su "recuperables".
do $$
declare
    v_cli bigint;
    v_esperados int := 0;     -- <-- poner acá el "recuperables" del bloque 1
    v_tocados int;
begin
    select id into strict v_cli from clientes where nombre ilike '%Día%';

    -- El UPDATE es seguro POR SÍ MISMO, no por las guardas de antes: el
    -- código tiene que apuntar a UNA sola ficha (ambigüedad) y esa ficha
    -- tiene que ser del MISMO artículo del renglón cuando el renglón ya
    -- tiene uno (artículo cruzado). Así, aunque los datos cambien entre el
    -- bloque 1 y este, no puede escribir mal: a lo sumo escribe de menos, y
    -- de eso avisa el contador de abajo.
    update pedidos_renglones r
       set ficha_id = f.id, articulo_id = f.articulo_id
      from pedidos p, fichas_logistica f
     where p.id = r.pedido_id and p.cliente_id = v_cli and p.anulado_el is null
       and r.anulado_el is null and r.ficha_id is null
       and f.cliente_id = v_cli and f.codigo_cliente is not null
       and translate(lower(btrim(f.codigo_cliente)),'áéíóúüñ','aeiouun') =
           regexp_replace(translate(lower(btrim(coalesce(r.texto_codigo,''))),
                          'áéíóúüñ','aeiouun'), '\s+',' ','g')
       and coalesce(r.texto_codigo,'') <> ''
       and (r.articulo_id is null or r.articulo_id = f.articulo_id)
       and not exists (
           select 1 from fichas_logistica f2
            where f2.cliente_id = v_cli and f2.id <> f.id
              and translate(lower(btrim(f2.codigo_cliente)),'áéíóúüñ','aeiouun') =
                  translate(lower(btrim(f.codigo_cliente)),'áéíóúüñ','aeiouun'));
    get diagnostics v_tocados = row_count;

    if v_tocados <> v_esperados then
        raise exception 'ABORTA sin escribir: se tocaron % y el bloque 1 dijo %. Volve a contar.',
            v_tocados, v_esperados;
    end if;
end $$;

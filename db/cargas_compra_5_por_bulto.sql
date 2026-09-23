do $$
begin
  if not exists (select 1 from information_schema.columns
                  where table_schema = 'public' and table_name = 'cargas_compra_renglones'
                    and column_name = 'contenido_por_bulto') then
    alter table cargas_compra_renglones add column contenido_por_bulto numeric;
  end if;
  alter table cargas_compra_renglones
      drop constraint if exists cargas_compra_renglones_por_bulto_check;
  alter table cargas_compra_renglones
      add constraint cargas_compra_renglones_por_bulto_check
      check (contenido_por_bulto is null or contenido_por_bulto > 0);
end $$;

comment on column cargas_compra_renglones.contenido_por_bulto is 'CUANTO TRAE UN BULTO de este renglon, en la magnitud del articulo (kilos, o unidades si se cuenta), tal como lo dejo el que cargo. La pantalla relaciona tres numeros —total, bultos y por bulto— y guarda dos: total y este; los bultos salen de dividir (dueno, 23/09: "cargar indistintamente kilos totales, bultos y kilos por bulto, y que los tres queden relacionados"). NULL = no se declaro y la pantalla propone el contenido_caja de la ficha del cliente. NO ES el kilaje del Mercado (listados_compra_kilaje): aquel es de a cuanto viene el cajon al comprar; este es como piensa el pedido de ese cliente.';

-- Agrega el "por bulto" de cada renglón de una carga. Estructura con
-- if not exists; el CHECK se dropea y se recrea siempre, porque es
-- contenido (CLAUDE.md: un if not exists sobre contenido esconde).
-- Sin backfill: los renglones viejos quedan en NULL y la pantalla les
-- propone el bulto de la ficha, que es lo que mostraban hasta hoy.
-- La verificación va en cargas_compra_5_verificacion.sql y se corre APARTE.

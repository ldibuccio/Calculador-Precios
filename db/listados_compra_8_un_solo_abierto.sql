do $$
declare
  v_abiertos int;
begin
  select count(*) into v_abiertos from listados_compra where estado = 'borrador';
  if v_abiertos > 1 then
    raise exception 'hay % listados abiertos: cerrá los viejos antes de correr esto', v_abiertos;
  end if;

  drop index if exists listados_compra_un_borrador_por_dia_idx;
  drop index if exists listados_compra_un_solo_abierto_idx;
  create unique index listados_compra_un_solo_abierto_idx
      on listados_compra ((true)) where estado = 'borrador';
end $$;

-- Bloque 2 de 2 del listado atado al momento de salir. SE CORRE DESPUÉS DEL
-- DEPLOY: el código viejo abre un listado por día, y con este índice el
-- segundo día rebotaría. El código nuevo toma "el abierto", sea del día que
-- sea, y anda con los dos índices.
--
-- Cambia "uno abierto POR DÍA" por "uno abierto, punto" (dueño, 23/09): se
-- trabaja de noche, y un listado armado a las 22 no puede quedar huérfano
-- porque cambió la fecha. El índice es sobre una constante: todas las filas
-- en borrador chocan entre sí.
--
-- La guarda cuenta ANTES de tocar nada: con dos abiertos, crear el índice
-- fallaría igual, pero después de haber dropeado el viejo. Adentro del mismo
-- do, todo o nada.
--
-- El índice nuevo se dropea y se recrea en vez de "if not exists": es
-- estructura, pero recrearlo cuesta nada y así un índice con otra
-- definición y el mismo nombre no sobrevive.
--
-- La verificación va en listados_compra_8_verificacion.sql y se corre APARTE.

-- Cuántos listados de compra hay ABIERTOS (en borrador) en esta base.
-- Decide si el cambio a "un solo listado abierto" puede correr tal cual: con
-- más de uno abierto el índice nuevo rebota, y hay que decidir qué hacer con
-- los viejos ANTES. Devuelve CONTEOS y no una lista: sin abiertos, igual
-- vuelve una fila y el cero se ve.
select 'listados_compra_6_cuantos_abiertos' as QUE_CONSULTA,
       (select count(*) from listados_compra where estado = 'borrador') as ABIERTOS,
       (select count(distinct fecha) from listados_compra
         where estado = 'borrador') as fechas_con_abierto,
       (select min(fecha) from listados_compra where estado = 'borrador') as abierto_mas_viejo,
       (select max(fecha) from listados_compra where estado = 'borrador') as abierto_mas_nuevo,
       -- Los abiertos que tienen algo tildado: uno vacío se puede cerrar sin
       -- perder nada; uno con cargas es trabajo de alguien.
       (select count(distinct l.id) from listados_compra l
          join listados_compra_cargas lc on lc.listado_id = l.id
         where l.estado = 'borrador') as abiertos_con_cargas,
       (select count(*) from listados_compra) as POBLACION_listados,
       (select max(fecha_operacion) from pedidos) as testigo_ultimo_pedido;

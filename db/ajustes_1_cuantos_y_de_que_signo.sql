-- AJUSTES DE STOCK (1 de 2): cuántos, de qué signo, y si hay algo antes del corte.
--
-- La pregunta que contesta: si nunca se cargó una merma y la fruta se pudre
-- igual, ¿la baja está entrando como AJUSTE? Un ajuste NEGATIVO es "había
-- menos de lo que el sistema decía"; si eso es lo que pasa cuando algo se
-- tira, la merma existe y está escrita en la columna equivocada.
--
-- El signo es el único indicio ESTRUCTURAL que hay acá: no depende de cómo
-- alguien redactó el motivo. Por eso va en esta consulta y la lectura del
-- texto va en la 2, separada.
--
-- `historia_*` está al lado del recorte a propósito: con las mermas, el dato
-- que sirvió no fue el cero desde el corte sino el NULL de toda la historia.
-- Preguntar las dos cosas de una evita la segunda vuelta.
with c0 as (select fecha as f0 from corte_modelo where id = 1)
select
    (select f0 from c0)                                          as corte,
    count(*) filter (where m.fecha_operacion > (select f0 from c0)
                       and m.anulado_el is null)                 as ajustes,
    count(*) filter (where m.fecha_operacion > (select f0 from c0)
                       and m.anulado_el is null and m.cantidad < 0) as bajas,
    coalesce(-sum(m.cantidad) filter (
        where m.fecha_operacion > (select f0 from c0)
          and m.anulado_el is null and m.cantidad < 0), 0)       as bultos_bajados,
    count(*) filter (where m.fecha_operacion > (select f0 from c0)
                       and m.anulado_el is null and m.cantidad > 0) as altas,
    coalesce(sum(m.cantidad) filter (
        where m.fecha_operacion > (select f0 from c0)
          and m.anulado_el is null and m.cantidad > 0), 0)       as bultos_subidos,
    count(distinct m.articulo_id) filter (
        where m.fecha_operacion > (select f0 from c0)
          and m.anulado_el is null)                              as articulos_distintos,
    count(*) filter (where m.anulado_el is null)                 as historia_ajustes,
    min(m.fecha_operacion) filter (where m.anulado_el is null)   as historia_primero,
    max(m.fecha_operacion) filter (where m.anulado_el is null)   as ultimo_ajuste
from movimientos_stock m
where m.tipo = 'ajuste';

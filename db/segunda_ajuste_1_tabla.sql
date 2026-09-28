do $$
begin
  create table if not exists ajustes_segunda (
    id              bigint generated always as identity primary key,
    articulo_id     bigint not null references articulos (id),
    bultos          numeric not null check (bultos <> 0),
    motivo          text not null check (btrim(motivo) <> ''),
    fecha_operacion date not null,
    stock_sistema   numeric not null,
    creado_en       timestamptz not null default now(),
    anulado_el      timestamptz
  );
  create index if not exists ajustes_segunda_articulo
    on ajustes_segunda (articulo_id, fecha_operacion) where anulado_el is null;
  comment on table ajustes_segunda is
    'Ajuste del pool de SEGUNDA con motivo, para un desvio que no viene de su origen (guia R, rechazo, pase o remito): la segunda que habia en el piso al corte y no se cargo. bultos con signo: positivo suma al pool, negativo resta. No toca la primera. stock_sistema = el pool al cierre del dia del conteo, congelado.';
end $$;

-- EL AJUSTE DE SEGUNDA (28/09). La segunda solo se corregía en su origen (la
-- guía R, el rechazo, el pase o el remito al Puesto), y hay un desvío que no
-- viene de ninguno: la segunda que había en el piso el 05/09 y no entró al
-- stock inicial. Caso: palta, 21 remitidas al Puesto y 19 entradas.
--
-- Tabla PROPIA y no un tipo nuevo de movimientos_stock: esa tabla exige
-- cantidad distinta de cero y la suma a la primera, y bultos_segunda > 0. Un
-- ajuste de segunda no toca la primera y tiene signo. Meterlo ahí es tocar
-- media docena de CHECKs y cada pata del stock que suma `cantidad`.
--
-- bultos CON SIGNO: positivo suma al pool, negativo resta. stock_sistema es el
-- pool al cierre del día del conteo, congelado, igual que en los conteos.
--
-- ESTRUCTURA, así que el `if not exists` está bien (la tabla existe o no, y
-- si existe es la misma). El código que la usa se mergea DESPUÉS de la fila
-- de verificación de las dos bases: db/segunda_ajuste_1_verificacion.sql.

do $$
begin
  alter table vacios_deposito_devoluciones
    add column if not exists cargada_desde text;
  alter table vacios_deposito_devoluciones
    drop constraint if exists vacios_dev_cargada_desde;
  alter table vacios_deposito_devoluciones
    add constraint vacios_dev_cargada_desde
    check (cargada_desde is null
           or cargada_desde in ('deposito', 'administracion', 'compras'));
  comment on column vacios_deposito_devoluciones.cargada_desde is
    'Por qué puerta entró la devolución: deposito, administracion o compras. '
    'NULL en las cargadas antes de esta columna: no hay de dónde deducirlo. '
    'El sistema no tiene usuarios, así que dice el SECTOR y no la persona.';
end $$;

-- POR DÓNDE ENTRÓ una devolución de vacíos (dueño, 29/09). La pantalla de
-- Movimientos dice por dónde entró cada fila, y la devolución es la única
-- que no se puede derivar: desde el 29/09 la cargan Depósito y
-- Administración. Las entradas son de Recepción, y los ajustes y
-- asignaciones solo existen en Administración.
--
-- La columna es ESTRUCTURA y el `if not exists` va. La lista del CHECK es
-- CONTENIDO: se borra y se recrea siempre (CLAUDE.md, el `if not exists`
-- sobre contenido). Las filas viejas quedan en NULL a propósito: deducirles
-- la puerta sería inventarla.
--
-- Se corre en las DOS bases. La verificación va APARTE, en
-- vacios_origen_devolucion_2_verificacion.sql.

-- Verificacion de db/devolucion_compra_1_columna.sql.
--
-- CONTEOS POR NOMBRE y no una lista: con una lista, "todo bien" y "no
-- corrio" son la misma pantalla vacia. Y contar los constraint POR NOMBRE
-- es lo que la hace servir — un "¿existe algun check?" daria 1 y taparia
-- que el que se agrego es otro.
--
-- `columna 1 · solo_devolucion 1 · compra_o_proveedor 1` es el resultado
-- bueno, y da lo mismo en las DOS bases por diseño. Por eso van los
-- testigos al lado: son lo unico que dice de cual base es la fila.
--
-- `ofensores` tiene que dar 0 y mide lo que el CHECK nuevo prohibe entre lo
-- que YA estaba escrito: si alguna devolucion vieja tuviera las dos cosas,
-- la migracion habria fallado y esto lo confirma desde el otro lado.
--
-- CORRIDA ANTES DE LA MIGRACION, ESTO NO DEVUELVE `columna 0`: falla con
-- `column "compra_devolucion_id" does not exist`. Es a proposito que quede
-- dicho — ese error NOMBRA la columna, asi que no se puede confundir con
-- "todo bien", que es lo unico que importa. Una verificacion que corriera
-- antes tendria que no nombrar la columna, y entonces no podria contar los
-- ofensores, que es lo que de verdad vale mirar.
select
    (select count(*) from information_schema.columns
      where table_name = 'movimientos_stock'
        and column_name = 'compra_devolucion_id')                  as columna,
    (select count(*) from pg_constraint
      where conname = 'movimientos_stock_compra_solo_devolucion')  as solo_devolucion,
    (select count(*) from pg_constraint
      where conname = 'movimientos_stock_compra_o_proveedor')      as compra_o_proveedor,
    (select count(*) from movimientos_stock
      where compra_devolucion_id is not null
        and proveedor_devolucion_id is not null)                   as ofensores,
    (select count(*) from movimientos_stock
      where destino_rechazo = 'devolucion_proveedor'
        and anulado_el is null)                                    as devoluciones,
    (select count(*) from movimientos_stock
      where destino_rechazo = 'devolucion_proveedor'
        and anulado_el is null
        and compra_devolucion_id is not null)                      as ya_con_compra,
    (select max(fecha_operacion) from movimientos_stock
      where tipo = 'reingreso_rechazo')                            as ultimo_reingreso,
    (select max(fecha_operacion) from compras
      where estado = 'recepcionado')                               as ultima_recepcion;

-- VERIFICACIÓN de db/devolucion_al_proveedor.sql. Se corre DESPUÉS.
--
-- Existe porque un bloque que no hizo nada se ve EXACTAMENTE IGUAL que uno
-- que corrió bien: los dos salen `DO`. Lo que dice si quedó escrito no es
-- la pantalla del editor, es esta consulta.
--
-- CUENTA EL CONSTRAINT POR NOMBRE **y además mira su CONTENIDO**, que es la
-- parte que no se puede saltear: un CHECK con el nombre correcto y la lista
-- vieja adentro existe igual, y contarlo por nombre daría 1. Por eso
-- `valores_en_el_check` cuenta los CUATRO valores uno por uno.
--
-- TIENE que devolver: 1 · 4 · 1 · 1 · 1. Cualquier otra cosa es que la
-- migración no quedó.
--
-- Probada corriéndola ANTES y DESPUÉS de la migración: antes da 0 · 3 · 0,
-- después 1 · 4 · 1. Un verificador que no se mueve no verifica nada.

with d as (
  select pg_get_constraintdef(oid) as def
  from pg_constraint
  where conrelid = 'movimientos_stock'::regclass
    and conname = 'movimientos_stock_destino_rechazo_check'
)
select
  (select count(*) from information_schema.columns
    where table_name = 'movimientos_stock'
      and column_name = 'proveedor_devolucion_id') as col_proveedor,

  (select count(*) from (values ('stock'), ('segunda'), ('reproceso'),
                                ('devolucion_proveedor')) as v(x)
    where (select def from d) like '%''' || v.x || '''%') as valores_en_el_check,

  (select count(*) from pg_constraint
    where conrelid = 'movimientos_stock'::regclass
      and conname = 'movimientos_stock_proveedor_solo_devolucion') as guarda_proveedor,

  -- No se tocó, pero si alguien la pisó el destino nuevo dejaría de exigir
  -- `bultos_segunda is null` y no habría nada que avise.
  (select count(*) from pg_constraint
    where conrelid = 'movimientos_stock'::regclass
      and conname = 'movimientos_stock_segunda_segun_destino') as guarda_segunda,

  -- Testigo: si la tabla no existiera, todo lo de arriba daría 0 y se
  -- leería como "la migración no corrió" en vez de "miré donde no era".
  (select count(*) from information_schema.tables
    where table_name = 'movimientos_stock') as la_tabla_existe;

-- VERIFICACIÓN de db/agregar_cuit_a_proveedores.sql. Se corre DESPUÉS.
--
-- Un `do $$` que no hizo nada sale `DO` igual que uno que corrió bien: lo
-- que dice si quedó escrito no es la pantalla del editor, es esto.
--
-- Cuenta el CHECK POR NOMBRE **y mira su CONTENIDO**: un constraint con el
-- nombre correcto y otra expresión adentro existe igual y por nombre daría 1.
--
-- TIENE que devolver: 1 · 1 · 0 · <proveedores> · <cuit ya cargados>.
-- Probada corriéndola ANTES y DESPUÉS, y con el CHECK cambiado por otro
-- del mismo nombre: ahí `guarda_formato` cae a 0 y el nombre solo diría 1.

select
  (select count(*) from information_schema.columns
    where table_name = 'proveedores' and column_name = 'cuit') as col_cuit,

  (select count(*) from pg_constraint
    where conrelid = 'proveedores'::regclass
      and conname = 'proveedores_cuit_check'
      and pg_get_constraintdef(oid) like '%[0-9]{11}%') as guarda_formato,

  -- TIENE que dar 0: si hay un único sobre cuit, alguien lo agregó y va a
  -- frenar el caso real de un dueño con dos puestos.
  (select count(*) from pg_constraint
    where conrelid = 'proveedores'::regclass and contype = 'u'
      and pg_get_constraintdef(oid) like '%cuit%') as unico_de_mas,

  (select count(*) from proveedores) as proveedores,

  -- `to_jsonb(p) ->> 'cuit'` y no `p.cuit`: escrito directo, esta consulta
  -- EXPLOTA si se corre ANTES de la migración —"column cuit does not
  -- exist"— en vez de devolver los ceros que dicen que no corrió. Un
  -- verificador que se rompe cuando la respuesta es "no está" no sirve:
  -- es la pantalla vacía que esta consulta viene a evitar.
  (select count(*) from proveedores p
    where (to_jsonb(p) ->> 'cuit') is not null) as con_cuit;

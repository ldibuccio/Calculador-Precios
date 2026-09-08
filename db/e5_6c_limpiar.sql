-- BLOQUE C de 3. Se corre al terminar: e5_mov es una tabla de trabajo de la
-- medicion, no un dato del sistema.
drop table if exists e5_mov;
select count(*) as tablas_e5_mov
from information_schema.tables where table_name = 'e5_mov';

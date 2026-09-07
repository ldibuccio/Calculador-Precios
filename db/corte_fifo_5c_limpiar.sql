-- BLOQUE C de 2 (+1). Se corre al terminar: corte_mov es una tabla de
-- trabajo del backtest, no un dato del sistema.
drop table if exists corte_mov;
select count(*) as tablas_corte_mov
from information_schema.tables where table_name = 'corte_mov';

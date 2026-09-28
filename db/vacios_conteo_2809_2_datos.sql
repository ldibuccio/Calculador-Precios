create or replace function vacios_conteo_2809()
returns table (orden int, pn text, marca text, cant int) language sql immutable as $f$
  values (1,'rio uruguay','Goloso',493), (2,'herederos n7','La Unión',154),
    (3,'herederos n7','Don Quijote',30), (4,'herederos n7','Fortaleza',12),
    (5,'herederos n7','Don Ibáñez',3), (6,'saturno','Babilonia',91),
    (7,'patagonia market','Patagonia',83), (8,'roncaglia alcides j','El Pato',50),
    (9,'mrc','Soto',48), (10,'sin proveedor','La Valentina',35),
    (11,'abra chica','Abra Chica',24), (12,'frutas j robol','Canasto Negro',24),
    (13,'frutamax srl','Lisandro',11), (14,'frutamax srl','Tom Jug',1),
    (15,'deliverduras','Crefu',7), (16,'kaizer','1039',3),
    (17,'productos san marcos','Ulises',1)
$f$;

select 'vacios_conteo_2809_2_datos' as que_migracion,
       (select count(*) from vacios_conteo_2809()) as filas_17,
       (select sum(cant) from vacios_conteo_2809()) as total_1070;

-- ARRANQUE DE VACÍOS DESDE EL CONTEO FÍSICO DEL 28/09, bloque 2.
-- Solo una función: el conteo, escrito UNA vez. Lo leen la revisión, la
-- carga y la verificación. No escribe datos; se puede correr de nuevo.
-- El proveedor va con el nombre PLEGADO (sin tildes, puntos ni
-- mayúsculas), que es como lo busca el bloque 3.

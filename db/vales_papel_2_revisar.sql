select fila, codigo, proveedor, fecha, importe, numero, foto,
       coalesce(problema, 'ok') as problema,
       (select count(*) from vales_papel_revision) as filas_en_el_listado,
       (select count(*) from vales_papel_revision where problema is not null) as con_problema
  from vales_papel_revision
 order by problema is null, fila;

-- VALES ANTERIORES AL SISTEMA, paso 2 de 4: REVISAR (solo lee).
-- Una fila por vale del listado, con el proveedor al que va y su problema.
-- Arriba salen las que tienen problema; las buenas dicen 'ok'. Las dos
-- columnas de la derecha son el total del listado y cuantas estan mal:
-- con_problema tiene que dar 0 antes de cargar. Si sale sin filas, el
-- listado esta vacio (paso 1).
-- Una fila mal: se corrige con un UPDATE sobre vales_papel_listado por su
-- numero de fila, o se borra y se vuelve a pegar. Paso 3: vales_papel_3_cargar.sql.

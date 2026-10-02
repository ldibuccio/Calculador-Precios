insert into vales_papel_listado (fila, codigo, fecha, importe, numero, foto) values
  (1, 'EJEMPLO', '31/08/2026', 15000, 'A-0001', null),
  (2, 'EJEMPLO', '01/09/2026', 8000, null, null);

-- VALES ANTERIORES AL SISTEMA, paso 1 de 4: PEGAR el listado (duenio, 30/09).
--
-- Una fila por vale, con este formato:
--   (numero de fila, 'CODIGO DE PUESTO', 'DD/MM/AAAA', importe, 'numero del vale' o null, 'foto' o null)
--
--   numero de fila   1, 2, 3... sin repetir: es lo que nombra la revision.
--   codigo           el del puesto del proveedor (N09P39), principal o alternativo.
--   fecha            la del vale en papel, DD/MM/AAAA.
--   importe          en pesos, sin puntos: 15000 o 15000.50.
--   numero           el del vale, si tiene. Si no, null.
--   foto             la ruta en el Storage si se subio (vacios/2026-09-30/x.jpg). Si no, null.
--
-- Las dos filas de EJEMPLO se reemplazan: si quedan, la revision las marca y
-- la carga no escribe nada.
--
-- Hasta 35 filas por corrida, y se pega SOLO el insert (sin estos
-- comentarios): mas no entra en 2500 caracteres. Si el listado
-- es mas largo, se pega en varias corridas seguidas, cada una con sus
-- numeros de fila (36, 37...). Un INSERT es UNA sentencia: o entra entero o
-- no entra. Una fila con un numero que ya esta rebota todo ese pegado.
--
-- Esto no carga ningun vale todavia: solo deja el listado para revisar.
-- Paso 2: vales_papel_2_revisar.sql.
--
-- OBSOLETO DESDE EL 02/10 (duenio): los vales en papel se cargan desde la
-- pantalla de Vales ("Cargar vale"). Este archivo no se corre mas.

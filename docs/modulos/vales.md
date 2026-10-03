# Módulo: vales a cobrar

Movido TAL CUAL desde CLAUDE.md el 03/10 (sin reescribir). Las reglas
vigentes, en corto, están en CLAUDE.md.

## VALES A COBRAR (30/09, dueño)

La plata de envase que el proveedor nos debe. `/administracion/vales` y
`/gerencia/vales` son la MISMA pantalla, con el sector sacado del prefijo
(corolario 63). La lógica vive en app/db.py (sección VALES A COBRAR) y los
textos y el Excel en `core/vales.py`.

- **Un vale nace de DOS maneras**, y el CHECK `vales_origen_coherente` no
  deja mezclarlas. **Devolución**: toda devolución de vacíos CON importe deja
  un vale en la misma transacción (`crear_devolucion_vacios`). Proveedor,
  fecha, importe, cajones, marca y foto se LEEN de la devolución, no se
  copian. El vale guarda solo el número (opcional) y el **importe calculado**
  (la seña por cajón de la última recepción con seña de esa pila, por los
  cajones, calculada en el server), y la pantalla muestra la diferencia.
  Sin importe no hay vale, y un número sin importe se rechaza. **Anterior al
  sistema**: los vales en papel, cargados por SQL, con proveedor, fecha,
  importe y número y foto opcionales.
- **Nada se backfilleó**: las devoluciones del 25/09 son pruebas y no entran
  a la cartera (dueño). En Frutamax eran las 13 que había (30/09).
- **El estado se deriva** (`_SQL_ESTADO_DEL_VALE`): una salida manda; sin
  salida, la devolución anulada lo saca de la cartera; si no, está en
  cartera. Anular la devolución con el vale COBRADO o CRUZADO rebota
  (`_negar_si_el_vale_ya_salio`, adentro de la misma transacción).
- **Una salida por vale** (`vales_a_cobrar_salidas`, clave vale_id), con
  sector y hora: **cobrado** (fecha, importe cobrado, ingreso a caja opcional)
  y **cruzado** (fecha, referencia), los dos de Administración.
  **NINGÚN VALE SE ANULA** (dueño, 01/10), ni el de papel ni el de una
  devolución: el vale lo hace un tercero. Si una devolución de vacíos se cargó
  mal, se anula la DEVOLUCIÓN y el vale sale de la cartera con ella (eso no
  cambió). No hay ruta, botón ni escritura para anular: lo que se carga es
  `SALIDAS_QUE_SE_CARGAN`, y la leen la pantalla (`salidas_del_vale`) y la
  escritura, que rechaza "anulado" de cualquier sector. **La base todavía
  acepta "anulado" de Gerencia** (el CHECK de `vales_2_salidas`), y se deja
  así sin migración (dueño, 01/10): solo entra por SQL a mano, y ningún
  camino del código lo escribe;
  `SECTOR_DE_LA_SALIDA` sigue siendo el espejo de esos CHECK y un test lee el
  .sql. **Una salida no se deshace**: no hay pantalla para volver un cobrado atrás.
- **Las dos alertas** (`vales_plata_sin_aplicar` y `vales_viejos`, Gerencia y
  Administración) salen de `resumen_de_la_cartera`, la misma cuenta que el
  total de arriba. Los límites viven en `vales_a_cobrar_limites` (una fila,
  arrancan en $500.000 y 14 días, sin default en la base) y se cambian desde
  `/gerencia/vales`. Los días son MÁS de, no igual.
- **Los CHECK con `importe > 0` van con `coalesce(..., false)`**: sin eso, un
  importe vacío da NULL y el CHECK deja pasar (corolario 67). Lo agarró el
  test que planta el caso, no la lectura.
- **Vales en papel**: **OBSOLETO desde el 02/10** (dueño): los vales en papel
  se cargan desde la pantalla ("Cargar vale", ver abajo), y
  `db/vales_papel_1_pegar.sql` no se corre más. Lo que sigue es cómo
  funcionaba: `vales_papel_listado` es donde se pega el listado
  (`db/vales_papel_1_pegar.sql`, hasta 35 filas por corrida), y la vista
  `vales_papel_revision` dice fila por fila a qué proveedor va y qué tiene
  mal. La regla vive una vez, en la vista, y la leen la revisión (paso 2) y
  la carga (paso 3, todo o nada, y vacía el listado). Volver a pegar lo mismo
  dice "ya estaba cargado". La fecha se valida con `pg_input_is_valid`, así
  un 30/02 se nombra en vez de reventar la revisión.
- **Juntar proveedores** mueve los vales anteriores al sistema
  (`TABLAS_QUE_APUNTAN_A_PROVEEDORES`); los de una devolución lo leen de ella.
- **NADA DE ESTO TOCA EL STOCK.**

Lo cuida `tests/test_vales_a_cobrar.py`, contra Postgres.

### Cargar un vale a mano, y corregirlo (02/10, dueño)

- **"Cargar vale"** (`/administracion/vales/cargar` y `/gerencia/vales/cargar`):
  código de puesto (principal o alternativo; si no, se elige el proveedor de
  la lista), fecha, importe, número, foto y nota opcionales. La foto va al
  bucket "comandas", prefijo de vales. **Es un origen NUEVO, `carga_manual`**,
  y no `anterior_al_sistema`: ése queda para lo que se cargó por SQL, que no
  dice quién. El de carga manual guarda el sector en `cargado_desde` (la base
  lo exige: `vales_carga_manual_con_sector`) y la nota en `nota`. Entra en
  cartera como cualquier vale y **no toca stock, ni cajones, ni Vacíos**: es
  una fila en `vales_a_cobrar` y nada más (lo cuida un test que cuenta las
  tablas que no se pueden mover).
- **Duplicados: avisa y pide confirmación, no frena.** Con número: el mismo
  proveedor y el mismo número (sin mayúsculas ni espacios de más). Sin
  número: el mismo proveedor, fecha e importe (`vales_parecidos`). La pantalla
  pregunta ANTES de enviar (`/vales/cargar/parecidos`), porque un formulario
  que vuelve del servidor no trae la foto; el POST vuelve a preguntar.
- **Un vale no se anula, se CORRIGE** (`corregir_vale`), solo Gerencia, y
  **cualquier vale EN CARTERA** (dueño, 02/10; hasta ese día solo los de
  datos propios). Importe, número y fecha en todos; el proveedor solo en los
  que lo traen propio (anterior al sistema o carga manual): el de una
  devolución es el de la devolución. Historial en `vales_correcciones` (campo,
  anterior, nuevo, fecha y sector), igual que el número de remito. El detalle
  lo muestra en la historia. Un vale con la devolución anulada no se corrige.
- **EL IMPORTE DEL VALE** (dueño, 02/10) es lo que dice el papel, y es el que
  vale en cartera, al cobrar y al cruzar: `coalesce(vale.importe,
  devolución.importe)`. En un vale de devolución `vale.importe` y `vale.fecha`
  son la CORRECCIÓN de Gerencia (NULL = la de la devolución; volver al valor
  de la devolución deja NULL), y la devolución no se toca.
  `importe_calculado` (seña × cajones) no cambia nunca: la pantalla muestra
  el importe del vale, el calculado y la diferencia, y "cargada por $X" si se
  corrigió. **OJO, el pedido decía que el importe salía del calculado: no.**
  Sale de la devolución, y los 13 de Frutamax lo tienen (02/10, total
  $4.313.000), así que ninguno queda "sin importe" y la alerta de "sin
  importe" no se construyó: no hay cómo llegar a ese caso.
  Migración `db/vales_editables_1` (solo el CHECK `vales_origen_coherente`,
  no toca filas), verificación en `_2`. Lo cuida
  `tests/test_vales_editables.py`, con los 13 de Frutamax sembrados con el
  CHECK viejo.
- **Un vale que salió (cobrado o cruzado) no se corrige**, y lo decide la
  base con dos triggers. Importe, número y fecha: nunca
  (`vale_que_salio_no_se_corrige`, en el momento). El proveedor: solo si al
  CERRAR la transacción el proveedor viejo ya no existe
  (`vale_que_salio_cambia_de_proveedor`, diferido). Es lo que pasa al juntar
  dos proveedores, que mueve los vales y borra el que se va en la misma
  transacción. Sin marca ni excepción (dueño, 02/10): hasta ese día juntar
  ponía `SET LOCAL app.juntando_proveedores = 'si'` y la pared dejaba pasar
  los cuatro campos; un test exige que esa marca no exista más.
  `corregir_vale` pide el diferido en el momento (`SET CONSTRAINTS ...
  IMMEDIATE`), así rebota en el UPDATE y se traduce, en vez de en el commit.
- **El listado de Vales y Movimientos (pantalla y Excel) filtran por origen**,
  y el Excel lo dice en el encabezado.

Migraciones `db/vales_manual_1` a `_3`, verificación en `_4`. Lo cuida
`tests/test_vales_carga_manual.py`, contra Postgres.

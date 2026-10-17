# Módulo: Cartera de cheques (Gerencia)

## LA CARTERA (dueño, 13/10)

Gerencia → **Cartera de cheques** (`/gerencia/cheques`). La usa SOLO Gerencia,
con su clave: carga y aplica Lionel, y Administración no la ve. El sistema no
tiene usuarios, así que "quién" en el historial es el sector y la hora.

**ECHEQ por defecto (dueño, 16/10)**: en la carga a mano, en "Revisar
cheques" (Excel, foto o PDF) y entre las opciones de "Para todos", ECHEQ va
primero y es lo que viene puesto. Queda Físico solo si la lectura lo dice
claramente: la IA solo dice "fisico" si ve un cheque de PAPEL, y en una
planilla la columna tiene que decir "Físico" o "Papel"
(`tipo_de_la_celda`). En "Para todos" sigue viniendo "No cambiar": si viniera
ECHEQ, cambiar otro dato a todos pisaría los que se leyeron como físicos.

Migración `db/cheques_1..5` (verificada en Frutamax y Palmala el 13/10, ver
`db/corridas_confirmadas.md`). Tablas: `bancos`, `cheques`,
`cheques_conceptos`, `cheques_salidas`, `cheques_rechazos`, `cheques_fotos`,
`cheques_correcciones`, todas con candado. Código: `app/db.py` (bloque
CARTERA DE CHEQUES), `core/cheques.py`, `core/lector_cheques.py`,
`core/exportar_cheques.py`, las rutas `/gerencia/cheques…` en `app/main.py` y
las plantillas `cheques*.html` y `cheque.html`. Tests:
`tests/test_cheques.py` (contra la base) y `tests/test_cheques_pantallas.py`.

### Lo que decide la base

- **Repetidos**: banco + número + CUIT del librador
  (`cheques_banco_numero_librador`; el número sin ceros adelante). Dos
  libradores distintos del mismo banco pueden tener el mismo número.
- **De quién es**: un cliente del sistema, un nombre escrito a mano, o
  "Canje" (lo que entra a cambio en un canje). `cheques_origen_coherente`.
- **Salida**: una por cheque (`cheques_salidas`), con un concepto que dice si
  queda Entregado, Canjeado o Depositado. Pago a proveedor exige proveedor:
  de la lista (`proveedor_id`) o ESCRITO A MANO (`proveedor_a_mano`, alguien
  que no está en proveedores, sin crearlo; uno u otro, nunca los dos;
  migración `cheques_3`, dueño 16 y 17/10); el canje va contra nada. Un rechazado no sale, y nada sale antes de su
  fecha de carga (trigger `cheque_salida_valida`; desde `cheques_2` esos dos
  frenos miran solo cuando la salida nace o cambia de cheque o de fecha, para
  que juntar proveedores pueda mover la salida de un cheque ya rechazado). Un
  depósito puede guardar la cuenta en `cuenta_deposito` (vacía no). Se pueden agregar
  conceptos nuevos al aplicar, eligiendo cómo deja el cheque.
- **Correcciones**: solo mientras está en cartera
  (`cheque_que_salio_no_se_corrige`), con historial campo por campo.
- **Rechazado**: desde cualquier estado, con fecha y motivo. Se le reclama
  SIEMPRE a quien lo dio, aunque ya se hubiera entregado a un proveedor. El
  reclamo se cierra a mano ("Reclamo resuelto", fecha y nota juntas).

### El estado, en UN lugar: la vista `cheques_con_estado`

- **En cartera** hasta que se aplica. Se pone **rojo a los 23 días** de su
  fecha de pago (le quedan 7 de los 30 para depositar) y queda **Vencido a
  los 30**. El vencido sigue contando en cartera.
- **Depositado → Acreditado** al día siguiente de su fecha de pago, o del
  depósito si se depositó después (dueño, 13/10). No se confirma con el
  banco. Entregados y canjeados no pasan a Acreditado.
- **Rechazado** (rojo) hasta **Reclamo resuelto**.

### Pantallas

- **Lista**: arriba, de TODOS los cheques, el total en cartera, lo que
  **entra en 7 días** (en cartera con fecha de pago de hoy a 7 días) y en
  rojo los por vencer, vencidos y rechazados sin resolver
  (`resumen_de_cheques`). Buscador con filtros combinables (fechas de carga,
  pago y acreditación; cliente, nombre, proveedor, número, banco, concepto,
  estado) y el atajo "En cartera". Total del listado; PDF y Excel con los
  mismos filtros y su encabezado.
- **Cargar**: a mano (uno o varios) o leyendo la foto de UN cheque
  (`core/lector_cheques.py`): lo leído aparece para corregir y no se guarda
  solo, y la foto queda como su frente. Fotos de frente y dorso. En la carga
  a mano, un banco que no está en la lista se agrega al guardar. Todo o nada.
- **Cargar un listado** (dueño, 13/10): Excel (.xlsx o .xls), CSV o PDF (el
  listado de ECHEQ del banco), con MUCHOS cheques. Las columnas pueden venir
  con cualquier nombre y orden: en una planilla se busca la fila de títulos y
  cada columna se reconoce por su nombre (`core/listado_cheques.py`,
  `SINONIMOS`); si no se reconocen el número y el importe, o es un PDF, lee
  la IA. El renglón de "Total" del pie no entra. Todo va a una tabla
  editable con el total, y en rojo lo que tiene problema
  (`problemas_de_los_renglones`): repetido (contra la base o dentro del
  listado), CUIT inválido (11 números y el dígito verificador de la AFIP),
  falta un dato, banco que no está en la lista. "Guardar todos" guarda los
  que están bien, en una transacción, y deja en la tabla los que tienen
  problema hasta corregirlos o sacarlos. "Bajar planilla modelo" baja una
  planilla vacía con los títulos que se reconocen solos. Tests:
  `tests/test_cheques_listado.py`.
- **Listados grandes** (dueño, 14/10, tras un Excel de 130 cheques que no se
  pudo guardar: Starlette corta un formulario en 1000 campos y cada cheque
  manda 9 o más). El listado y la revisión de Aplicar leen el formulario
  con `MAX_CAMPOS_DE_UN_LISTADO` (alcanza para `MAX_RENGLONES_DE_UN_LISTADO`
  = 2000 cheques). Arriba: "130 cheques · $X · 128 bien · 2 con problema".
  Cada cheque es un renglón compacto (número, fecha, de quién, importe) que
  se abre al tocarlo; los que tienen problema van primero y abiertos. "Para
  todos" (`poner_a_todos`) cambia de quién es (y el cliente o el nombre), el
  tipo y el banco de los TILDADOS, o de todos si no hay ninguno tildado; lo
  que queda en "No cambiar" no se toca. "Seleccionar todos" tilda todos, y
  "Sacar los tildados" los saca. Un banco que no está se avisa UNA vez
  arriba con cuántos cheques lo traen (`bancos_que_faltan`) y "Agregarlo"
  lo agrega a la lista para todos. Tests:
  `tests/test_cheques_listado_grande.py` (300 cheques).
- **De quién es un cheque del listado: CUIT propios y de terceros** (dueño,
  14/10). Un cliente paga con sus cheques (con uno o VARIOS CUIT propios) y
  con cheques de TERCEROS. Los CUIT propios están en `clientes_cuits`
  (migración `clientes_cuit_2`; un CUIT es de un solo cliente) y se cargan
  desde la ficha del cliente ("CUIT propios") o al guardar un listado. Se
  asigna solo ÚNICAMENTE el cheque cuyo CUIT es propio de un cliente; el
  nombre del librador ya no asigna. Uno de terceros no se asigna: si ese
  CUIT ya vino en un cheque de un cliente, el renglón muestra en gris "La
  última vez vino de X" con "Usar" (`sugerencias`, del último cheque por
  fecha de carga, `ultimo_cliente_por_cuit`). Nada se aprende solo: al
  elegir un cliente a mano, arriba se pregunta una vez por CUIT "¿es un CUIT
  propio de X? Sí / No, es de un tercero" (`cuits_para_preguntar`); no se
  pregunta por un CUIT que ya vino antes (ya se vio: es de un tercero) ni
  por uno que en ese listado se dijo que es de un tercero. "Sí" lo guarda y
  pasa a ese cliente los demás cheques del listado con ese CUIT. La columna
  `clientes.cuit` (de `clientes_cuit_1`) se pasó a la tabla y se borró con
  `clientes_cuit_3` (15/10, después del deploy de v1157).
- **Banco leído**: es el de la lista si es EL MISMO banco
  (`core.cheques.clave_de_banco`): sin acentos, mayúsculas, signos, el código
  numérico ni las palabras de relleno ("Banco", "de", "S.A.U.",
  "Argentina"...), y los nombres largos conocidos a su forma corta ("Galicia
  y Buenos Aires" es Galicia, "BBVA Francés" es BBVA). Nada de "se parece",
  que escondía un banco que no estaba: "EJEMPLO Banco Inventado" no es
  "EJEMPLO Banco" y "Galicia Más" no es "Galicia". Al guardar tampoco se
  duplica (`_banco_por_nombre` compara por la misma clave).
- **El CUIT** se controla con el dígito verificador también en la carga a
  mano.
- **Aplicar: UN SOLO FLUJO de dos pasos** (dueño, 16/10). Reemplaza los tres
  bloques de antes (capturas de ECHEQ, una foto o archivo, y la carga a mano
  con un solo motivo para todos).
  - **Paso 1, elegir**: arriba "Subí capturas, fotos o archivos" (uno o
    muchos, foto o PDF: endosos y depósitos del home banking, boletas de
    depósito, recibos de entrega); abajo la cartera con buscador, para
    tildar a mano. Se pueden usar las dos juntas. **"Cargar"** (antes
    "Seguir"; dueño, 17/10) va FIJO arriba, debajo de la barra, mientras se
    baja por la cartera, con cuántos cheques hay tildados y el total
    ("Cargar · 4 cheques · $10.000.000"); sin tildar nada igual se aprieta
    (pudo subir solo archivos). No guarda nada.
    "Aplicar este cheque" de la ficha llega con ese cheque tildado.
  - La IA lee cada archivo entero (un PDF con todas sus páginas; se muestra
    y se guarda la primera) con `extraer_salida_de_cheques`: si es un
    endoso, un depósito o no lo dice, la cuenta, el proveedor que RECIBE
    (CUIT y razón social) y cada cheque con número, fecha de pago, monto y
    emisor. El archivo que no se lee se avisa y no frena los demás.
  - **Paso 2, revisar** (`core/salidas_de_cheques.py`): un renglón por cheque
    AGRUPADO POR ARCHIVO ("Foto 1 · proveedor o cuenta · N cheques ·
    $total"); los tildados a mano van en "Elegidos a mano". Arriba: "X
    cheques · $Y · Z bien · W con problema". Cada renglón es compacto
    (número, de quién, monto, fecha de pago) y se abre al tocarlo; los que
    tienen problema van en rojo, primero y abiertos, y los grupos con
    problema van primero.
  - **Cada grupo dice lo que se leyó** de su archivo (dueño, 17/10): "Endoso a
    FRIGORIFICO CINCO SALTOS SA · CUIT 30-53636746-9" o "Depósito en cuenta
    191-220-000247/7" (`lo_leido`).
  - Lo leído viene puesto y TODO se cambia; **nada arranca en "Elegí"**
    (dueño, 17/10): el día de salida (hoy), el motivo ("Pago a proveedor";
    un depósito, "Depósito en cuenta"; también lo tildado a mano y lo que no
    dice a dónde va), el proveedor (por su CUIT si lo tiene UNO solo; si el
    CUIT no es de ninguno, viene A MANO con la razón social leída ya escrita,
    y "Elegir de la lista" muestra la lista y vacía lo escrito; el elegido de
    la lista se queda con el CUIT leído si no tenía, y no se pisa uno
    distinto) y la cuenta (por el número leído, `cuenta_por_numero`; si no,
    el Banco Credicoop o el único banco, `cuenta_por_defecto`, en cada
    renglón, en el grupo y en "Para todos"; un depósito que leyó un número
    que no es de ninguna cuenta se pide elegir, salvo con un solo banco, que
    va a ese). Se cambia por
    renglón, por grupo (el encabezado cambia el motivo, el proveedor o la
    cuenta de todo el grupo) o con "Para todos", que va a los TILDADOS y, si
    no hay ninguno tildado, pregunta antes de ponerlo en todos. También
    "Seleccionar todos", "Sacar los tildados" y "Otro motivo" (nombre y cómo
    deja el cheque).
  - El cheque de la cartera se busca por número (sin ceros adelante) Y monto
    entre los que están en cartera. En rojo: no está en la cartera, ya salió,
    el monto no coincide (aunque se elija a mano: se corrige el monto), está
    en otro renglón, o falta el motivo, el proveedor (un pago) o la cuenta
    (un depósito, si la base tiene bancos). El mismo cheque (número y monto)
    en dos archivos, o tildado a mano y también en un archivo, se toma una
    vez y se avisa. Solo un problema DEL CHEQUE (no lo que falta del
    destino) abre el número, el monto y el cheque de la cartera para
    corregir; corregido el número o el monto, el renglón vuelve a buscar su
    cheque solo (`buscar_otra_vez_en_la_cartera`).
  - "Confirmar todos" guarda los que están bien en UNA transacción
    (`aplicar_salidas_de_cheques`), cada salida con la foto de su archivo
    (una subida por archivo; los de a mano, sin foto), y deja en la página
    los que tienen problema. El proveedor se guarda solo en un pago y la
    cuenta solo en un depósito (`cheques_salidas.cuenta_deposito` guarda la
    cuenta leída, migración `cheques_2`). Tests: `tests/test_cheques_aplicar.py`.
- **Conciliar con el banco** (dueño, 16/10; botón en la Cartera,
  `/gerencia/cheques/conciliar`, `core/conciliar_cartera.py`). Se suben uno o
  varios archivos del banco (el listado de ECHEQ en cartera o en custodia:
  Excel, PDF o capturas) y se leen como en "Cargar cheques" (la planilla celda
  por celda, la foto o el PDF con la IA). El mismo cheque (número, banco,
  monto y fecha) que ya vino en un archivo anterior se toma una vez y se
  avisa. Se cruza contra los cheques EN CARTERA: por número (sin ceros
  adelante) y banco (`clave_de_banco`); si lo leído no trae banco, por número
  y monto. Después se controlan el monto y la fecha de pago. Cuatro grupos,
  con cantidad y total: 1) coinciden (verde, plegado); 2) en el banco y no en
  el sistema, con "Cargarlos", que los abre en "Revisar cheques" (cliente por
  CUIT propio, "Para todos"); 3) en el sistema y no en el banco (rojo), cada
  uno con "Aplicar" y "Rechazado" (abre la ficha con el rechazo desplegado);
  4) con diferencia, banco y sistema lado a lado. "Solo ECHEQ" (tildado por
  defecto): los físicos no están en el banco, no se comparan y van aparte.
  Arriba: "Banco: X cheques $Y · Sistema: Z cheques $W · Diferencia $V". PDF y
  Excel con el mismo cruce que la pantalla (el encabezado dice si fue solo
  ECHEQ). Nada se guarda: lo leído viaja en el formulario para volver a
  cruzar, exportar y cargar. Sin migración. Tests:
  `tests/test_cheques_conciliar.py`.
- **Ficha**: datos, fotos, historial, y aplicar, rechazar, resolver el
  reclamo, corregir y agregar fotos.
- **Panel**: cuadro 13 "Cheques" (`docs/modulos/panel_control.md`).

Las fotos son del tipo `cheque` en Gerencia → Fotos (prefijo `cheques`), sin
protección: vencen a su plazo.

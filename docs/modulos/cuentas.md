# Cuentas: Caja, Banco e Inversiones con un solo motor (dueño, 15/10)

Gerencia, en las DOS apps (Frutamax y Palmala). Lo único solo de Frutamax es
Palmala Cruces. Migración `cuentas_1` (bloques `db/cuentas_1..11`,
verificación `db/cuentas_12`), corrida en las dos bases el 15/10
(`db/corridas_confirmadas.md`).

## Las cuentas

- Una cuenta es un renglón de `cuentas`: nombre, tipo (caja, banco o
  inversión), moneda (pesos o dólares), número (los bancos) y cuenta madre
  (Inversiones Credicoop está dentro de Banco Credicoop). Otra cuenta
  bancaria es agregar un renglón, no programar otro módulo.
- **Frutamax** nace con Caja Lionel, Banco Credicoop (CC$ 191-220-000247/7)
  e Inversiones Credicoop y sus 31 conceptos (sembrados por la migración).
  **Palmala** nace sin cuentas (Lionel borró las sembradas después de
  correrla): se crean en Gerencia → Cuentas (al final de "Bancos y cajas").
- Una cuenta nueva arranca con los conceptos por defecto de su tipo
  (`CONCEPTOS_POR_TIPO` en `core/cuentas.py`): los mismos que la Caja o el
  Banco de Frutamax, sin los que son solo del histórico. Una inversión,
  Saldo inicial, Rendimiento y Ajuste.
- **Los botones de Gerencia** salen de las cuentas ACTIVAS de cada base, en
  el recuadro "Bancos y cajas" (dueño, 16/10), con su color propio y en este
  orden (`cuentas_del_hub`): cada banco seguido de las inversiones que están
  dentro de él, las inversiones sueltas, la Cartera de cheques, las cajas,
  Palmala Cruces (solo en Frutamax) y al final "Cuentas". Una cuenta nueva
  cae sola en su lugar. Dar de baja una cuenta le saca el botón y no recibe
  cheques; lo cargado queda.
- El número se compara solo por los dígitos (`cuenta_por_numero`, índice
  único `cuentas_numero` en la base): "CC$ 191-220-000247/7" y
  "191 220 000247 7" son la misma cuenta.

## Movimientos

- Fecha, ingreso o egreso, importe, concepto (lista de CADA cuenta,
  editable en "Cargar"), etiqueta (persona o empresa: la lista se arma sola,
  sin mayúsculas ni espacios de más), detalle y foto.
- Un concepto con tipo (solo ingreso o solo egreso) no se carga del otro
  tipo; un concepto de otra cuenta tampoco. Lo frena la base
  (`cuentas_movimiento_valido`) y la pantalla lo dice antes.
- **Solo del histórico**: "Cruce banco", "Cruce banco (ingreso)" y
  "Movimiento anterior" están dados de baja. De ahora en adelante el cruce
  entre Caja y Banco es una transferencia (depósito de efectivo o
  extracción), que es lo que hace que aparezca también en el Banco. El
  histórico (`como_se_cargo = 'historico'`, con `fila_historico` por
  cuenta) sí los usa.
- Corregir y anular piden motivo y quedan en el historial
  (`cuentas_correcciones`), con NOMBRES ("Cobro Mecafront → Cobro de
  terceros"), no ids. Anular es una corrección más: queda a la vista,
  tachado, y no suma.

## Transferencias

- Una sola fila en `cuentas_transferencias`, que la vista
  `cuentas_todos_los_movimientos` muestra en las dos cuentas: egreso en la
  de origen, ingreso en la de destino. Por eso corregirla o anularla cambia
  las dos patas siempre.
- El nombre lo pone la vista según los tipos: banco → inversión
  "Suscripción", inversión → banco "Rescate", caja → banco "Depósito de
  efectivo", banco → caja "Extracción"; otra combinación, "Transferencia".
- Solo entre cuentas de la misma moneda (lo frena la base).
- Los intereses de Inversiones son el concepto "Rendimiento", que existe
  solo en la inversión.

## Cheques depositados

- En la Cartera, "Depósito en cuenta" pide la cuenta de banco (las activas
  de ESA base). Con un solo banco ya viene elegido. Una base sin cuentas de
  banco deposita sin cuenta (Palmala hoy).
- La captura de un depósito reconoce la cuenta por el número leído; si el
  número no es de ninguna y hay más de un banco, pide elegirla.
- Queda en `cuentas_cheques_depositados` (la base frena si no es un banco o
  si el cheque no salió depositado; si se borra la salida, se borra solo).
  La ficha del cheque dice en qué cuenta está y deja cambiarla; el listado
  lo dice al lado.
- En la cuenta NO se carga nada: la vista muestra el ingreso "Depósito de
  cheque" con la fecha de acreditación de la Cartera y la etiqueta de quién
  era el cheque, y si se rechaza, el egreso "Cheque rechazado" con la fecha
  del rechazo.

## La pantalla de una cuenta

- Arriba, siempre, el saldo de HOY de toda la cuenta (no del filtro). Lo de
  fecha futura (un cheque que se acredita mañana) va aparte, "Por
  acreditarse".
- Filtros: desde, hasta, ingresos o egresos, concepto y etiqueta (los que
  aparecen en la cuenta, también los de transferencias y cheques).
- El listado con el saldo acumulado REAL de cada renglón
  (`cuentas_con_saldo`), y los totales por concepto y por etiqueta de lo
  filtrado, sin anulados.
- PDF y Excel con los mismos filtros, el encabezado que los dice, el saldo
  de hoy y los totales (`core/exportar_cuentas.py`).

## El histórico (15/10)

Ya está cargado por SQL en Frutamax (`db/corridas_confirmadas.md`): Caja
Lionel 668 movimientos (saldo $147.910.250), Inversiones Credicoop 255 (saldo
$87.000.000,11: los FCI con signo como "Movimiento anterior", utilidades e
intereses como "Rendimiento", etiquetas FCI Ahorro/Renta/Variable, sin tocar
el banco) y Banco Credicoop 544 (16/10, de la solapa "Sem Credicoop"): el
saldo inicial $3.706.788,02 al 28/12/2025 (fila 1; antes era $8.035.818,38 al
14/10/2026, corregido con su registro en `cuentas_correcciones`), 542
movimientos del 29/12/2025 al 16/10/2026 con el concepto "Movimiento anterior"
(inactivo, solo del histórico; filas 2 a 543) y un "Ajuste" de $0,02 por
redondeo (fila 544). Saldo $8.035.818,38; al 14/10, $3.195.973,96. No se
vuelve a cargar.

## Carga por foto y por Excel (15/10)

En "Cargar" de cada cuenta, además de a mano (como Palmala Cruces):
- **Fotos o PDF de comprobantes** (varios de una vez): la IA lee cada uno
  (`core/lector_cuentas.py`) y arma un renglón por movimiento, con de qué
  foto salió. Se le pasan los conceptos ACTIVOS de esa cuenta; el que
  sugiere tiene que ser uno de ellos, si no queda vacío y se elige. La foto
  que no se lee se avisa y no frena las demás.
- **Excel o CSV**: las columnas se reconocen por su título
  (`reconocer_columnas`): Fecha, e Importe o Ingreso y Egreso (o Crédito y
  Débito); Tipo, Concepto, Etiqueta (o De quién, Persona, Empresa) y Detalle
  si están. Un importe negativo es un egreso. Las filas de Total, Subtotal o
  Saldo no son movimientos.
- **La revisión**: los que tienen problema van primero, abiertos y en rojo;
  "Para todos" cambia el tipo, el concepto, la etiqueta o la fecha de los
  tildados (o de todos si no hay ninguno tildado); "Sacar los tildados";
  "Guardar todos" guarda los que están bien, juntos, cada uno con su foto
  (una subida por foto, no por renglón), y deja en la página los que
  tienen problema. NADA se guarda sin pasar por la revisión.

## Conciliación (15/10): solo en una cuenta de banco

Botón "Conciliar con el extracto" en la pantalla de un banco
(`/gerencia/cuentas/{id}/conciliar`; en una caja o una inversión, 404).
- **Subir extractos**: uno o varios de una vez (PDF, foto, Excel o CSV; por
  ejemplo 6 meses). La IA lee cada renglón con fecha, descripción, importe
  CON SIGNO (crédito positivo, débito negativo) y saldo, más el período y el
  saldo final (`core/lector_cuentas.py`, `PROMPT_EXTRACTO`). Un renglón sin
  fecha o sin importe no entra y se cuenta. Si dos extractos se pisan, el
  renglón repetido (misma fecha, importe, descripción y saldo) no entra dos
  veces (lo frena la base: `cuentas_renglon_una_vez`).
- **El cruce** (`core/conciliacion.py`, `cruzar`): por IMPORTE con su signo,
  al centavo, con ±5 días HÁBILES (lunes a viernes; los feriados no se
  descuentan), uno a uno. La descripción no tiene que coincidir. Si hay más
  de un candidato del mismo importe en el margen, gana la fecha más cercana
  y el par queda "para revisar" ("Está bien" o "No es este"). Lo conciliado
  queda marcado con el extracto y la fecha (`cuentas_conciliaciones`) y no se
  vuelve a cruzar.
- **El saldo inicial manda**: lo del extracto ANTERIOR a la fecha del
  movimiento "Saldo inicial" de la cuenta (Banco Credicoop: 28/12/2025, desde el 16/10) ya
  está adentro de ese saldo; no se cruza ni se carga, y se cuenta aparte. Lo
  del MISMO día del saldo inicial sí se cruza: el saldo es al cierre del día
  anterior a sus movimientos, así que su fecha es la del último día que ya
  incluye (Banco Credicoop: el saldo es "al 28/12/2025", y desde el
  29/12/2025 entra todo; dueño, 16/10). El movimiento de saldo inicial no se
  cruza nunca.
- **El resultado**: la diferencia de saldo al cierre de cada extracto (el
  saldo final del banco contra el del sistema a esa fecha), lo que está solo
  en el extracto (se carga de un toque con un concepto sugerido por la
  descripción —comisiones e impuestos, transferencias, si no "Otros
  ingresos/egresos"— y queda conciliado), lo que está solo en el sistema en
  esas fechas (en rojo, para revisar) y los conciliados, plegados.
- Anular un movimiento conciliado (o borrar la salida de un cheque
  depositado) suelta su renglón: una conciliación sin movimiento vivo se
  borra sola al abrir la pantalla.

Tests: `tests/test_cuentas.py`.

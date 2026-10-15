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
  correrla): se crean en Gerencia → Cuentas (Mantenimiento).
- Una cuenta nueva arranca con los conceptos por defecto de su tipo
  (`CONCEPTOS_POR_TIPO` en `core/cuentas.py`): los mismos que la Caja o el
  Banco de Frutamax, sin los que son solo del histórico. Una inversión,
  Saldo inicial, Rendimiento y Ajuste.
- **Los botones de Gerencia** salen de las cuentas ACTIVAS de cada base, en
  el orden en que se crearon, en el grupo "Mirar". Dar de baja una cuenta le
  saca el botón y no recibe cheques; lo cargado queda.
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
el banco) y Banco Credicoop solo el saldo inicial $8.035.818,38 del
15/10/2026, que se completa con la conciliación. No se vuelve a cargar.

## Lo que falta (pedido del 15/10)

- Carga por foto o archivo y por Excel con la pantalla de revisión y "Para
  todos".
- Conciliación de extractos dentro de cada banco.

Tests: `tests/test_cuentas.py`.

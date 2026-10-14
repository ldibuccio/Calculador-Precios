# Palmala Cruces

## LA CUENTA (dueño, 14/10)

La cuenta corriente interna entre Frutamax (Lionel) y Palmala. Solo Gerencia,
y **SOLO en Frutamax**: es una cuenta de Frutamax, la ve solo Lionel. Las
tablas (`db/palmala_cruces_1..4`, migración `palmala_1`; ojo: los `db/palmala_1..5` sin "cruces" son de otra migración vieja) se corrieron solo en la base
de Frutamax; en la de Palmala no existen. La app de Palmala no muestra el
botón y sus rutas contestan 404 sin consultar nada (`ES_FRUTAMAX` en
`app/main.py`, que sale de `NOMBRE_EMPRESA`). La lista de fotos de respaldo
suma las de esta cuenta solo si la tabla existe (`_SQL_FOTOS_SOLO_EN_FRUTAMAX`).

- **Movimiento**: fecha, cuenta, sentido, importe, concepto y detalle.
  "Palmala debe" suma, "Palmala pagó" resta (obligatorio).
- **Tres cuentas, cada una con su saldo**: Pesos, Dólares socios, Dólares
  NDT. No hay conversión: si Palmala paga en pesos algo en dólares, son DOS
  movimientos, uno por cuenta (dueño, 14/10).
- **El texto del saldo** (dueño, 14/10): "Palmala te debe $X" si es positivo,
  "Le debés a Palmala $X" si es negativo, "Están a mano" en cero
  (`texto_del_saldo`). Negativo en rojo.
- **Conceptos**: lista editable (`palmala_conceptos`), se agregan y se dan de
  baja desde Cargar; uno dado de baja no se ofrece y la base no lo acepta en
  un movimiento nuevo. "Pago con cheque" y "Pago con echeq" (`pide_cheque`)
  llevan número, banco y fecha de pago; los demás no aceptan datos de cheque
  (trigger `palmala_movimiento_valido`). El histórico puede tener cheques
  incompletos. El banco es la lista de Cartera de cheques, con su
  `clave_de_banco`.
- **Los cheques de Palmala NO se cruzan con la Cartera de cheques** (dueño,
  14/10, "por ahora").
- **Anular**: nunca se borra. Anular es una corrección más: queda a la vista,
  tachado, y no suma al saldo; se puede volver a contar. Todo cambio va al
  historial (`palmala_correcciones`) con antes, después y motivo
  (obligatorio).

## Pantallas (`/gerencia/palmala-cruces`)

- **Arriba, los tres saldos, de todo** (no del filtro). Abajo el listado, lo
  más nuevo arriba, con el saldo acumulado REAL de su cuenta en cada renglón
  (lo calcula la vista `palmala_movimientos_con_saldo` sobre todos) y, si hay
  filtro, "Lo filtrado". Filtros: fechas, cuenta, sentido, concepto. PDF y
  Excel con los mismos filtros, el encabezado que los dice y los tres saldos.
- **Cargar** (`/cargar`): un movimiento a mano (con foto si se quiere; el
  banco que no está se agrega), varias fotos de cheques de una vez (la IA lee
  cada una, `extraer_cheques_de_imagenes`: un renglón por cheque como "Palmala
  pagó" en Pesos, "Pago con echeq" si es ECHEQ), o un Excel/CSV (columnas por
  su título: Fecha, Importe o Debe y Pagó, Concepto, Cuenta, Detalle, Cheque,
  Banco, Fecha de pago; el renglón "Total" no entra; una cuenta que no se
  entiende se elige, nunca se adivina).
- **Revisar** (`/revisar`): la misma mecánica que el listado de cheques: lista
  compacta con los que tienen problema primero y abiertos, "Para todos"
  (sentido, cuenta, concepto, fecha) a los tildados o a todos, "Sacar los
  tildados", el banco que falta una vez arriba con "Agregarlo", y el
  formulario sin el tope de 1000 campos (`_formulario_de_un_listado`).
- **Ficha** (`/{id}`): los datos, la foto, Corregir (con motivo), Anular o
  Volver a contarlo, y el historial.

Tests: `tests/test_palmala_cruces.py`.

## El histórico (14/10)

428 movimientos cargados por SQL por Lionel (`como_se_cargo = 'historico'`,
`fila_historico` la fila del Excel): las filas 5 a 432 del Excel sin la 220
(427), más la 9999, un "Ajuste" del 14/10/2026 de $2.147.220,07 ("Palmala
debe") para cuadrar. No se vuelve a cargar: `fila_historico` es única.

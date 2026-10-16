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
- **Cargar** (dueño, 16/10): UN SOLO FLUJO de dos pasos, igual que "Aplicar
  cheques" y que Caja, Banco e Inversiones (`core/carga_en_dos_pasos.py`,
  `templates/carga_elegir.html` y `carga_revisar.html`). Las pantallas viejas
  (a mano, fotos, Excel) se sacaron.
  - **Paso 1** (`/cargar`): arriba "Subí fotos o archivos" (fotos de cheques
    o ECHEQ, comprobantes, Excel/CSV, PDF, varios de una vez) y abajo
    "Cargar a mano" (cuántas filas vacías); se pueden usar juntos. "Seguir"
    fijo arriba (`/cargar/seguir`). Debajo, los conceptos (agregar, dar de baja).
  - Una foto o un PDF lo lee la IA (`core/lector_palmala.py`): un renglón por
    movimiento en Pesos; un cheque es "Palmala pagó" y, si la IA no eligió el
    concepto, "Pago con echeq" o "Pago con cheque" según el tipo. Un Excel se
    lee por sus columnas (Fecha, Importe o Debe y Pagó, Concepto, Cuenta,
    Detalle, Cheque, Banco, Fecha de pago; el "Total" no entra; una cuenta que
    no se entiende se elige, nunca se adivina).
  - **Paso 2** (`/revisar`): un renglón por movimiento, todo editable (fecha,
    importe, sentido, cuenta, concepto, detalle, y número, banco y fecha de
    pago cuando el concepto lleva cheque), agrupado por archivo (los a mano al
    final) con un encabezado que cambia todo el grupo. "Para todos" (fecha,
    sentido, cuenta, concepto) va a los tildados; sin ninguno, pregunta antes
    de ponerlo en todos. La cuenta de "Para todos" viene en Pesos. Arriba, fijo:
    "X movimientos · $Y · Z bien · W con problema" (pesos y dólares por
    separado) y "Confirmar todos", que guarda los que están bien, cada uno con
    la foto de su archivo y su origen (`foto`, `excel` o `a_mano`).
  - En rojo: lo que falta, el cheque incompleto y el REPETIDO (el mismo
    cheque por número y banco, o la misma fecha, cuenta, sentido e importe; ya
    cargado o más arriba en la misma carga). "No es repetido" lo deja pasar:
    dos pagos iguales el mismo día pueden existir. El banco que falta, una vez
    arriba con "Agregarlo"; el formulario sin el tope de 1000 campos.
- **Ficha** (`/{id}`): los datos, la foto, Corregir (con motivo), Anular o
  Volver a contarlo, y el historial.

Tests: `tests/test_palmala_cruces.py`.

## El histórico (14/10)

428 movimientos cargados por SQL por Lionel (`como_se_cargo = 'historico'`,
`fila_historico` la fila del Excel): las filas 5 a 432 del Excel sin la 220
(427), más la 9999, un "Ajuste" del 14/10/2026 de $2.147.220,07 ("Palmala
debe") para cuadrar. Las filas 220, 433 y 434 del Excel están vacías (dueño,
14/10): el histórico está completo. No se vuelve a cargar: `fila_historico`
es única.

# Módulo: Cartera de cheques (Gerencia)

## LA CARTERA (dueño, 13/10)

Gerencia → **Cartera de cheques** (`/gerencia/cheques`). La usa SOLO Gerencia,
con su clave: carga y aplica Lionel, y Administración no la ve. El sistema no
tiene usuarios, así que "quién" en el historial es el sector y la hora.

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
  queda Entregado, Canjeado o Depositado. Pago a proveedor exige proveedor;
  el canje va contra nada. Un rechazado no sale, y nada sale antes de su
  fecha de carga (trigger `cheque_salida_valida`). Se pueden agregar
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
- **Cargar**: a mano (uno o varios) o leyendo una foto, un PDF o un Excel
  (`core/lector_cheques.py`): lo leído aparece para corregir y no se guarda
  solo. La foto leída de un cheque queda como su frente. Fotos de frente y
  dorso. Un banco que no está en la lista se agrega al guardar. Todo o nada.
- **Aplicar**: se tildan uno o varios cheques en cartera; leyendo una
  boleta o una foto quedan tildados los que se encuentran por número (y CUIT
  si se leyó). Comprobante opcional.
- **Ficha**: datos, fotos, historial, y aplicar, rechazar, resolver el
  reclamo, corregir y agregar fotos.
- **Panel**: cuadro 13 "Cheques" (`docs/modulos/panel_control.md`).

Las fotos son del tipo `cheque` en Gerencia → Fotos (prefijo `cheques`), sin
protección: vencen a su plazo.

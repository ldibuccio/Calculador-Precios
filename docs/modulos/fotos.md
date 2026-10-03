# Módulo: fotos de respaldo y espacio

Movido TAL CUAL desde CLAUDE.md el 03/10 (sin reescribir). Las reglas
vigentes, en corto, están en CLAUDE.md.

## FOTOS: LA REGLA DE 3 AÑOS Y LAS ANEXADAS DE UN VALE (30/09, dueño)

- **Una foto de respaldo no se borra antes de su plazo desde que se SUBIÓ**:
  3 años salvo que Gerencia le cambie el plazo al tipo (01/10, ver "EL PLAZO
  POR TIPO" abajo). Vale para todas: pesadas, devoluciones de mercadería, comandas, capturas de
  pedido, archivos de precios, mermas, devoluciones de vacíos, vales y
  anexadas. Las que se borran por error de carga en el momento (una pesada o
  una comanda desde la compra, una captura del pedido) siguen igual.
- **Después se borran a mano, desde Gerencia → "Fotos y espacio"**
  (`/gerencia/fotos`): cuántas y cuánto ocupan por tipo, y un botón con tilde
  de confirmación. Se va el ARCHIVO y **la fila que lo nombraba queda**;
  `fotos_borradas_por_antiguedad` dice cuándo. Todo "Ver foto" pasa por
  `_ir_a_la_foto` (app/main.py), que en ese caso muestra "Foto borrada el
  DD/MM/AAAA, por plazo" (o ", a mano", desde el 01/10). Un test exige que `obtener_url_foto` no se llame
  en ningún otro lado. El registro se escribe y se commitea DESPUÉS de borrar
  el archivo: si el Storage falla, la foto queda como estaba.
- **La lista de todas las fotos está escrita UNA vez**: `_SQL_FOTOS_DE_RESPALDO`
  (app/db.py), diez patas desde el 01/10 (la décima son los remitos). La regla (el corte, los tipos, el resumen) vive en
  `core/fotos.py`. Un test compara las tablas del esquema con columna de foto
  contra las decididas: una tabla nueva que guarde fotos falla hasta entrar.
- **Los archivos sin registro** (16 en Frutamax el 30/09) se muestran aparte
  y no se borran. El tamaño sale de `storage.objects`; si no se puede leer,
  la pantalla dice "sin dato".
- **La limpieza vieja de Sistema se sacó**: no pedía clave, borraba la fila y
  contaba por la fecha de la compra o del pedido.
- **La foto de una devolución de mercadería no se borra**: va a
  `fotos_recepcion` con `movimiento_id`, y `borrar_foto_recepcion` la deja
  afuera en el WHERE.
- **Borrar una compra no borra sus fotos de pesada**, forzado o no, de a una
  o con el Cancelar del día: pasan a `fotos_de_compras_borradas` en la misma
  transacción (`_SQL_GUARDAR_FOTOS_DE_COMPRAS_BORRADAS`) y el archivo queda.
  Se ven en Gerencia → Fotos: "de la compra N° X, borrada el …".
- **Un vale suma fotos en cualquier estado** ("Anexar foto", Administración y
  Gerencia): `vales_a_cobrar_fotos`, con el sector. La original no se copia.
  **Gerencia borra y reemplaza cualquier foto de un vale, salga o no de la
  cartera** (dueño, 02/10, `borrar_foto_del_vale`): se va el ARCHIVO, la fila
  que lo nombra queda, y se registra en `fotos_borradas_por_antiguedad` como
  'a_mano' con un renglón en `fotos_borrados`. Reemplazar es anexar la nueva y
  DESPUÉS borrar la vieja: nunca queda sin ninguna. Hay más de una foto por
  vale (las anexadas). El detalle las muestra en orden con su origen
  (`texto_de_la_foto`, core/vales.py) y el listado dice cuántas tiene cada vale
  y marca el que no tiene ninguna.
- Migraciones `db/fotos_1` a `fotos_4`, verificación en `fotos_5`. Lo cuida
  `tests/test_fotos.py`, contra Postgres.

### Y el ESPACIO, en la misma pantalla (01/10, dueño)

La pantalla se llama **"Fotos y espacio"** (`/gerencia/fotos`). Arriba va lo
nuevo y lo de 3 años queda abajo, igual que estaba.

- **Lo usado hoy**: todo `storage.objects` de ESTA base, de todos los buckets
  porque el plan los cobra a todos, por tipo, más "Sin registro" y "Otros
  buckets". Sale de `subidas_al_storage` (app/db.py), una consulta, y la
  leen la pantalla, el mes a mes, la proyección y la alerta.
- **Mes a mes**: cada archivo cuenta en el mes ARGENTINO en que se subió.
  Las borradas por antigüedad siguen en su mes, con los bytes de su
  registro, y no suman a lo de hoy. Un mes sin subidas sale en cero.
- **Proyección**: el ritmo de los últimos 90 días, o desde la primera foto si
  hay menos historia (la pantalla dice sobre cuántos días), sumado a lo de
  hoy durante 365 días. Supone que no se borra nada.
- **El límite es del PLAN y de la ORGANIZACIÓN** (dueño, 01/10): plan Pro,
  **100 GB de almacenamiento incluido por organización**, para Frutamax,
  Palmala y Ganadería juntas. Es un dato del dueño y vive en UNA constante,
  `LIMITE_DEL_PLAN_BYTES` en `core/fotos.py` (con `PLAN_DE_SUPABASE`), sin
  migración ni consulta a Supabase: si cambia el plan, cambia esa línea. Cada
  app ve solo su base, así que su porcentaje es su parte.
- **Alerta `espacio_de_fotos`**, solo Gerencia: más del 80% (`UMBRAL_DEL_AVISO`),
  y los casos son el porcentaje. Si el Storage no se lee, la alerta falla
  en vez de dar cero, y la pantalla dice "sin dato".

Medido el 30/09 en Frutamax: 622 archivos, 33,7 MB, del 15/08 en adelante.

## FOTOS: EL PLAZO POR TIPO Y EL BORRADO A MANO (01/10, dueño)

- **Cada tipo de foto tiene su plazo** en años desde la subida, editable en
  Gerencia → Fotos y espacio (`fotos_plazos`). La tabla nace VACÍA: un tipo
  sin fila vence a los 3 años, y el 3 vive una vez, en `core/fotos.py`
  (`ANIOS_DE_RESPALDO`). La lista "Fotos de más de 3 años" pasó a ser "Fotos
  vencidas", cada tipo a su plazo.
- **Borrado a mano**: un tipo y "anteriores a" una fecha. Antes se ve cuántas
  fotos y cuánto se libera; para confirmar hay que escribir la cantidad EXACTA,
  y el server la recalcula: si no coincide, no se borra nada.
- **En los dos se borra el ARCHIVO y queda el registro**:
  `fotos_borradas_por_antiguedad.como` ('plazo' o 'a_mano') y "Ver foto" dice
  "Foto borrada el DD/MM/AAAA, por plazo / a mano". El renglón de la operación
  no se toca nunca.
- **Nunca se borran** (se saltean, y la pantalla dice cuántas y por qué): las
  fotos de un vale que está en cartera (desde el detalle del vale Gerencia
  sí la borra, 02/10), y las de un remito
  sin facturar (un remito no se anula, así que la foto queda protegida hasta
  que se facture). Lo marca `_SQL_FOTOS_DE_RESPALDO` en la columna `protegida`,
  con el MISMO `_SQL_ESTADO_DEL_VALE` de la cartera. La foto de una devolución
  de vacíos es la de su vale, y queda protegida igual.
- **Cada borrado deja historial** (`fotos_borrados`): fecha, cómo, tipo,
  rango (`anteriores_a`), cantidad, bytes y salteadas. Uno por tipo. Si el
  Storage falla en todas, no queda renglón: el historial es de lo borrado.
- **Las pesadas de compras borradas siguen la regla de v1054**: 3 años fijos
  (`TIPOS_CON_PLAZO_FIJO`), sin plazo editable y fuera del borrado a mano.

Migraciones `db/fotos_6` a `fotos_8`, verificación en `fotos_9`. Lo cuida
`tests/test_fotos.py`, contra Postgres.

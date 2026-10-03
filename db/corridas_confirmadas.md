# Qué migraciones corrieron, en qué base, y con qué fila

**Para qué existe**: el 18/09 una auditoría no pudo contestar si las tres
migraciones de Vacíos habían corrido en Frutamax. Habían corrido. Lo que
faltaba era el registro: la única fila anotada era la de Palmala, y estaba
**citada adentro de un corolario** de CLAUDE.md para ilustrar otra cosa (cómo
el testigo dice si una base vota), no anotada como confirmación.

Una fila citada para ilustrar no es un registro. El que audita no la encuentra
buscando confirmaciones, y el que la escribió tampoco se acuerda de que está
ahí — así que la pregunta *"¿esto corrió en las dos?"* se vuelve irrespondible
y hay que ir a molestar al dueño.

**Por qué acá y no al pie de cada `.sql`**: esos archivos se pegan en el editor
de Supabase y **ningún bloque pasa los 2500 caracteres**. Varios están a
menos de 50 del límite, así que un registro de cuatro líneas adentro los
volvería intruncables — se arreglaría el registro rompiendo la migración.

**Cómo se usa**: al confirmar una migración, la fila de CADA base se pega acá
con el nombre de la base adelante. Las dos, siempre: salen idénticas por
diseño salvo la población y el testigo, así que pegar una sola es exactamente
el error que esto viene a evitar.

---

**Lo del 18/09 al 30/09 está en `db/corridas_historico.md`.** Acá queda de
octubre en adelante. No se lee entero: se busca la migración con `grep`.

## 01/10 — `remitos_1` a `remitos_4`, `fotos_6` a `fotos_8` y `devolucion_sector_1`

Corridas por el dueño en las dos bases. Las verificaciones van corridas aparte
de los `do` y las verificó el Claude con acceso de lectura:

```
FRUTAMAX  remitos · tablas 4 · indices 5 · checks 5 · anulado 0
PALMALA   remitos · tablas 4 · indices 5 · checks 5 · anulado 0
FRUTAMAX  fotos_plazos · tablas 2 · columnas 2 · check 1 · sin_como 0 · plazos 0
PALMALA   fotos_plazos · tablas 2 · columnas 2 · check 1 · sin_como 0 · plazos 0
FRUTAMAX  devolucion_sector (tras el bloque 1) · columna 1 · valida 1 · coherente 0 · sin_sector 0 · de_mas 0 · población 0
PALMALA   devolucion_sector (tras el bloque 1) · columna 1 · valida 1 · coherente 0 · sin_sector 0 · de_mas 0 · población 0
```

`coherente 0` es lo esperado después del bloque 1: el CHECK de la devolución
con sector lo agrega `devolucion_sector_2`, que se corre DESPUÉS del deploy
(completa lo que cargue el código viejo en el medio). Corrió el mismo día:
ver la entrada de abajo.
Población de devoluciones en 0 en las dos bases, así que el bloque 2 no tiene
filas viejas que completar salvo las que entren antes del deploy. Las
poblaciones de remitos y fotos y el testigo no vinieron en el mensaje.
Palmala no vota: ahí solo confirma que las migraciones no explotan.

## 01/10 — `devolucion_sector_2`: el CHECK de la devolución con sector

Corrida por el dueño en las dos bases DESPUÉS del deploy de v1060 (PR #82),
como pide su encabezado. Verificación (`devolucion_sector_3`), corrida aparte
del `do`, la verificó el Claude con acceso de lectura:

```
FRUTAMAX  devolucion_sector (tras el bloque 2) · columna 1 · valida 1 · coherente 1 · sin_sector 0 · de_mas 0 · población 0
PALMALA   devolucion_sector (tras el bloque 2) · columna 1 · valida 1 · coherente 1 · sin_sector 0 · de_mas 0 · población 0
```

`coherente 1` es el CHECK puesto. Con población 0 en las dos bases no hubo
devoluciones que completar: el código viejo no cargó ninguna entre los dos
bloques. La tanda de `devolucion_sector` queda cerrada. Palmala no vota.

## 02/10 — `devolucion_valor_2`: el movimiento 170 atado a la compra 807

Corrido por el dueño SOLO en Frutamax (el movimiento 170 es de esa base; en
Palmala no aplica). La verificación (`devolucion_valor_3`, cuya fila se llama
`devolucion_valor_2`), corrida aparte del `do`, la hizo el Claude con acceso de
lectura:

```
FRUTAMAX  devolucion_valor_2 · atada 1 · sin_proveedor_suelto 1 · compra 807 · precio 60.000 · costo del armado 59.822,75 · valor nuevo 600.000 · población 10
```

`atada 1` y `sin_proveedor_suelto 1`: el rechazo ya no apunta al proveedor
suelto sino a la compra 807. El valor nuevo es 10 × $60.000, el precio por
cajón de la compra, y no 10 × $59.822,75 del armado. La población son los 10
rechazos al proveedor no anulados de la base.

## 02/10 — `devolucion_valor_2` dos veces más: los movimientos 138 y 137 atados a su compra

Corridos por el dueño SOLO en Frutamax, con el mismo bloque de
`devolucion_valor_2` cambiando el movimiento, el renglón y la compra.
Verificados por el Claude con acceso de lectura:

```
FRUTAMAX  movimiento 138 · Arándano · renglón 1786 (armado 17/09) · compra 656 · atada · sin proveedor suelto · no anulado · 10 × $22.000 = $220.000
FRUTAMAX  movimiento 137 · Arándano · renglón 1785 (armado 18/09) · compra 709 · atada · sin proveedor suelto · no anulado · 10 × $22.000 = $220.000
FRUTAMAX  población de rechazos al proveedor 10 · con compra 4 (137, 138, 170 y 199)
```

La compra del 138 es la 656 porque era la única compra de Arándano de
FRUTAMAX recibida al momento del armado. La del 137 la eligió Lionel: la
709, a $22.000; la otra opción era la 704, a $20.000. Quedan 6 rechazos al
proveedor sin compra atada, y esos siguen valiendo el costo del armado.

## 02/10 — `cobranza_segunda_1` a `_3`: Cobranzas de segunda

Corridos por Lionel en las dos bases, cada bloque solo. La verificación
(`cobranza_segunda_4`), corrida aparte, la hizo el Claude con acceso de
lectura:

```
FRUTAMAX  cobranza_segunda · tablas 2 · checks 2 · triggers 2 · cobros 0 · lotes 60 · bultos 608 · primer lote 29/08 · último lote 01/10
PALMALA   cobranza_segunda · tablas 2 · checks 2 · triggers 2 · cobros 0 · lotes 0
```

Las dos tablas, los dos CHECK y los dos triggers están en las dos bases. Los
60 lotes de Frutamax arrancan todos pendientes (`cobros 0`). Palmala no tiene
ningún lote al puesto y no vota: confirma solo que los bloques no explotan.

## 02/10 — `vales_manual_1` a `_3`: Vales cargados a mano

Corridos por Lionel en las dos bases, cada bloque solo. La verificación
(`vales_manual_4`), corrida aparte:

```
FRUTAMAX  columnas 2 · origen 1 · coherente 1 · checks 3 · tabla 1 · triggers 2 · diferido 1 · marca_vieja 0 · manuales 0 · vales 8 · anteriores 0 · último vale 01/10
PALMALA   columnas 2 · origen 1 · coherente 1 · checks 3 · tabla 1 · triggers 2 · diferido 1 · marca_vieja 0 · manuales 0 · vales 0
```

Las dos columnas, el origen `carga_manual`, los CHECK, la tabla de
correcciones y los dos triggers (el de importe, número y fecha, y el
diferido del proveedor) están en las dos bases. `marca_vieja 0`: ninguna
función de la base lee ya `app.juntando_proveedores`. Todavía no hay vales
cargados a mano. Palmala no tiene vales y no vota: confirma solo que los
bloques no explotan.

## 02/10 — `tareas_1` a `_3`: Tareas

Corridos por Lionel en las dos bases, cada bloque solo. La verificación
(`tareas_4`), corrida aparte, la hizo el Claude con acceso de lectura:

```
FRUTAMAX  tareas · tablas 3 · constraints 4 · indices 2 · tareas 0 · ocurrencias 0 · testigo 41 proveedores
PALMALA   tareas · tablas 3 · constraints 4 · indices 2 · tareas 0 · ocurrencias 0 · testigo 45 proveedores
```

Las tres tablas, los cuatro constraints y los dos índices están en las dos
bases, todavía sin ninguna tarea cargada. El testigo solo identifica la base.
Palmala no vota: confirma solo que los bloques no explotan.

## 02/10 — `vales_papel_1` a `4` quedan OBSOLETOS

Decisión del dueño: los vales en papel se cargan desde la pantalla de Vales
("Cargar vale", origen `carga_manual`). `db/vales_papel_1_pegar.sql` y los
pasos que lo siguen no se corren más. Lo que ya se cargó por ese camino queda
como `anterior_al_sistema`.

## 02/10 — `vales_editables_1`: Vales editables desde Gerencia (PR #93)

Corrido por Lionel en las dos bases. La verificación (`vales_editables_2`),
corrida aparte, la hizo el Claude con acceso de lectura:

```
FRUTAMAX  vales_editables · coherente_nuevo 1 · devolucion_corregidos 0 · sin_importe 0 · importe_vigente 4313000 · vales 13 · testigo 02/10
PALMALA   vales_editables · coherente_nuevo 1 · devolucion_corregidos 0 · sin_importe 0 · importe_vigente 0 · vales 0
```

El CHECK nuevo está en las dos bases. En Frutamax el importe vigente de los
13 vales es el mismo de antes de correr el bloque ($4.313.000): no cambió
ninguna fila. Palmala no tiene vales y no vota.

## 02/10 — `tareas_5`: Tareas por sector y mensual en varios días (PR #95)

Corrido por Lionel en las dos bases, ANTES del deploy. La verificación
(`tareas_7`), corrida aparte, la hizo el Claude con acceso de lectura:

```
FRUTAMAX  tareas_por_sector · columnas 2 · dia_mes_viejo 1 · con_default 1 · check_creada 1 · check_dias 1 · de_un_sector 0 · mensual_sin_dias 0 · tareas 1
PALMALA   tareas_por_sector · columnas 2 · dia_mes_viejo 1 · con_default 1 · check_creada 1 · check_dias 1 · de_un_sector 0 · mensual_sin_dias 0 · tareas 0
```

Es el resultado esperado entre los dos pasos: `dia_mes` y el default de
`creada_por` siguen puestos porque el código viejo los usa. `tareas_6` los
saca y se corre DESPUÉS del deploy del #95; la misma `tareas_7` tiene que dar
entonces `dia_mes_viejo 0 · con_default 0`. Palmala no vota.

## 02/10 — `tareas_6`: Tareas por sector, segundo paso (PR #95)

Corrido por Lionel en las dos bases DESPUÉS del deploy del #95 (v1076). La
verificación (`tareas_7`), corrida aparte, la hizo el Claude con acceso de
lectura:

```
FRUTAMAX  tareas_por_sector · columnas 2 · dia_mes_viejo 0 · con_default 0 · check_creada 1 · check_dias 1 · de_un_sector 0 · mensual_sin_dias 0 · tareas 1
PALMALA   tareas_por_sector · columnas 2 · dia_mes_viejo 0 · con_default 0 · check_creada 1 · check_dias 1 · tareas 0
```

`dia_mes` ya no existe y `creada_por` no tiene default: desde acá el código
siempre dice quién cargó la tarea. La única tarea de Frutamax sigue y no
cambió. Palmala no vota. Con esto Tareas por sector queda cerrado.

## 02/10 — `lectura_1`: el usuario de solo lectura es `lectura_claudia`

Creado el 02/10 en Frutamax. El rol de la base se llama `lectura_claudia`;
los `.sql` decían `lectura_claude`, que no existe, y se corrigieron el mismo
día. La verificación (`lectura_2`, ya corregida) la corrí yo por el conector
"Supabase Lectura":

```
FRUTAMAX  lectura_usuario · usuario 1 · ve_todo_rls 0 · tablas_POBLACION 95 · sin_lectura 0 · ESCRIBE 0 · CREA_TABLAS 0 · tablas_futuras 1 · testigo 02/10
```

Lee todo y no escribe nada: 95 objetos (94 tablas y 1 vista), SELECT en los
95, ningún INSERT/UPDATE/DELETE/TRUNCATE, no crea tablas, y las tablas
futuras le llegan con SELECT. Su configuración es `default_transaction_read_only=on`
y `statement_timeout=60s` (el `.sql` dice 30s).

**`ve_todo_rls 0` NO es lo que pide el `.sql`**, que le pone `bypassrls`. En
Frutamax hay 55 tablas con RLS y sin ninguna política (`compras`,
`pedidos`, `movimientos_stock`, `reprocesos`, `fichas_logistica`, entre
otras), y en esas el permiso de SELECT no alcanza: este usuario recibe cero
filas sin error. Solo afecta a `LECTURA_FRUTAMAX_URL` en una sesión local;
el conector corre como `supabase_read_only_user` y ve las filas (855 compras
el 02/10). Pendiente del dueño, si se va a usar la URL: darle `bypassrls`.
Palmala no tiene este usuario.

## 02/10 — `backups_1` y `backups_2`: Plan B de backup (PR #97)

Corridos por Lionel en las dos bases, cada una con la clave de SU rol, ANTES
del deploy del #97. La verificación (`backups_3`), corrida aparte, la hizo el
Claude con acceso de lectura:

```
FRUTAMAX  backups · tabla 1 · check 1 · rol 1 · inserta 1 · lee_o_cambia 0 · otras_tablas 0 · rls 1 · politica 1 · politicas_total 1 · corridas 0 · proveedores 42
PALMALA   backups · tabla 1 · check 1 · rol 1 · inserta 1 · lee_o_cambia 0 · otras_tablas 0 · rls 1 · politica 1 · politicas_total 1 · corridas 0 · proveedores 45
```

La fila de Frutamax se volvió a correr el 03/10 por el conector "Supabase
Lectura" y dio idéntica (proveedores 42). La de Palmala es la que reportó el
dueño, porque cuando se escribió esta entrada se creía que no había acceso de
lectura a Palmala. Eso era falso: el conector "Supabase Lectura" lee las dos
bases (ver la entrada del 03/10, abajo). `corridas 0` es lo esperado: el
workflow todavía no corría (faltaban rclone y los secrets).

## 03/10 — Primera corrida del Backup: las tres partes, en los dos destinos

Corrida manual del workflow `Backup` (`workflow_dispatch`, run 37089873233),
terminada el 03/10 a las 00:21 de Argentina. No es una migración: es la primera
vez que `backups_corridas` recibe filas. Verificado por el conector "Supabase
Lectura" el 03/10, en las dos bases:

```
FRUTAMAX  codigo · onedrive true · gdrive true · 02/10 23:29 · detalle NULL · total 3
FRUTAMAX  bases  · onedrive true · gdrive true · 02/10 23:32 · detalle NULL · total 3
FRUTAMAX  fotos  · onedrive true · gdrive true · 03/10 00:21 · detalle NULL · total 3
PALMALA   codigo · onedrive true · gdrive true · 02/10 23:29 · detalle NULL · total 3
PALMALA   bases  · onedrive true · gdrive true · 02/10 23:32 · detalle NULL · total 3
PALMALA   fotos  · onedrive true · gdrive true · 03/10 00:21 · detalle NULL · total 3
```

(Horas de Argentina. El `total 3` es la tabla entera de cada base: no hay
filas anteriores.)

- **Las fotos subidas fueron 1110**, según el log del workflow que vio el
  Claude con lectura. Ese número no está en la base (`detalle` es NULL cuando
  la parte sale bien) y no se verificó por el conector.
- **`ESTADO_PALMALA_URL` usa el host `aws-0-us-west-1`** del pooler
  (`aws-0-us-west-1.pooler.supabase.com`). La guía
  (`docs/backup_guia_para_lionel.md`) deja la región como `<region>`: la de
  Palmala es ésa.
- Pendiente: después de la corrida programada de las 04:00 del 04/10,
  confirmar que cada base tenga 6 filas (3 más).

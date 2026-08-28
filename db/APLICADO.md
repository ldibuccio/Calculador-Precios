# Registro de migraciones aplicadas por base

Cada cambio de base se corre a mano en el editor SQL de **cada** Supabase, y se
anota acá **en el mismo commit** que el código que depende de él. Regla de
trabajo: no se mergea código que dependa de una migración hasta que las dos
bases estén marcadas.

- ✅ = corrida y confirmada en esa base.
- — = no corresponde correrla en esa base (con el motivo).

| Archivo | Frutamax | Palmala |
|---|---|---|
| `schema.sql` | ✅ (histórico) | — reemplazado por `esquema_completo.sql` |
| `seed_datos_iniciales.sql` | ✅ (histórico) | — datos de Frutamax; el catálogo se copia con `scripts/copiar_catalogo_empresa.py` |
| `rediseno_proveedores_compras.sql` | ✅ (histórico) | — consolidado en `esquema_completo.sql` |
| `migracion_clientes_final.sql` | ✅ (histórico) | — consolidado en `esquema_completo.sql` |
| `permitir_importe_null.sql` | ✅ (histórico) | — consolidado en `esquema_completo.sql` |
| `agregar_unidad_compra.sql` | ✅ (histórico) | — consolidado en `esquema_completo.sql` |
| `agregar_merma.sql` | ✅ (histórico) | — consolidado en `esquema_completo.sql` |
| `agregar_conversion_articulos.sql` | ✅ (histórico) | — tabla luego fusionada en fichas; no se crea |
| `cargar_conversiones_dia.sql` | ✅ (histórico) | — datos de Frutamax |
| `cargar_conversiones_dia_3nuevos.sql` | ✅ (histórico) | — datos de Frutamax |
| `fusionar_conversion_en_fichas.sql` | ✅ (histórico) | — consolidado en `esquema_completo.sql` |
| `abrir_conceptos_clientes_parametros_historial.sql` | ✅ (histórico) | — consolidado en `esquema_completo.sql` |
| `agregar_envase_variable.sql` | ✅ (histórico) | — consolidado en `esquema_completo.sql` |
| `agregar_grupo_articulos.sql` | ✅ (histórico) | — consolidado en `esquema_completo.sql` |
| `agregar_foto_ruta_compras.sql` | ✅ (histórico) | — consolidado en `esquema_completo.sql` |
| `agregar_precios_venta_historial.sql` | ✅ (histórico) | — consolidado en `esquema_completo.sql` |
| `agregar_foto_ruta_precios_venta_historial.sql` | ✅ (histórico) | — consolidado en `esquema_completo.sql` |
| `agregar_guia_compras.sql` | ✅ (histórico) | — consolidado en `esquema_completo.sql` |
| `agregar_recepcion_compras.sql` | ✅ (histórico) | — consolidado en `esquema_completo.sql` |
| `actualizar_tipo_retiro_carro_pases.sql` | ✅ (histórico) | — consolidado en `esquema_completo.sql` |
| `agregar_retiro_compras.sql` | ✅ (histórico) | — consolidado en `esquema_completo.sql` |
| `agregar_no_ingresado_compras.sql` | ✅ (histórico) | — consolidado en `esquema_completo.sql` |
| `agregar_cantidad_cajones_retirada_compras.sql` | ✅ (histórico) | — consolidado en `esquema_completo.sql` |
| `agregar_disponibles.sql` | ✅ (histórico) | — consolidado en `esquema_completo.sql` |
| `agregar_ingreso_directo_compras.sql` | ✅ 2026-08-18 | — consolidado en `esquema_completo.sql` |
| `esquema_completo.sql` | — sus tablas ya existen | ⬜ pendiente (correr al crear el proyecto; ya trae envases sin cliente) |
| `envases_sin_cliente.sql` | ✅ 2026-08-19 | ✅ 2026-08-19 |
| `agregar_tipo_retiro_cooperativa.sql` | ✅ 2026-08-19 | ✅ 2026-08-19 |
| `agregar_retiros_automaticos.sql` | ✅ 2026-08-19 | ✅ 2026-08-19 |
| `agregar_rechazo_parcial.sql` | ✅ 2026-08-19 | ✅ 2026-08-19 |
| `agregar_carga_token.sql` | ✅ 2026-08-19 | ✅ 2026-08-19 |
| `agregar_vacios_puesto.sql` | ✅ 2026-08-19 | ✅ 2026-08-19 |
| `agregar_resultado_sena.sql` | ✅ 2026-08-20 | ✅ 2026-08-20 |
| `agregar_proveedores_puesto.sql` | ✅ 2026-08-20 | ✅ 2026-08-20 |
| `agregar_ajustes_vacios.sql` | ✅ 2026-08-20 | ✅ 2026-08-20 |
| `agregar_indices_rendimiento.sql` | ✅ 2026-08-20 | ✅ 2026-08-20 |
| `agregar_fotos_guia.sql` | ✅ 2026-08-20 (verificado: 0 sin guía, 0 sin migrar, 36 fotos migradas) | ✅ 2026-08-20 (verificado: 0 / 0 / 19 fotos) |
| `agregar_historial_fichas.sql` | ✅ 2026-08-21 (verificado: 32 filas foto_inicial) | ✅ 2026-08-21 (verificado: 42 filas foto_inicial) |
| `corregir_retiros_recepcionados.sql` (corrección de datos, no de esquema: retiros colgados de compras procesadas en Depósito antes del auto-retiro del 2026-08-19) | ✅ 2026-08-21 | ✅ 2026-08-21 (verificado: 0 filas colgadas) |
| `agregar_pedidos.sql` | ✅ 2026-08-21 (verificado: 4 tablas creadas) | ✅ 2026-08-21 (verificado: 4 tablas creadas) |
| `agregar_cantidad_armada_pedidos.sql` | ✅ 2026-08-21 | ✅ 2026-08-21 |
| `agregar_casilla_pedidos.sql` | ✅ 2026-08-22 | ✅ 2026-08-22 |
| `agregar_asunto_filtro_casilla.sql` | ✅ 2026-08-22 | ✅ 2026-08-22 |
| `agregar_leido_con_ia_mails_pedido.sql` | ✅ 2026-08-22 | ✅ 2026-08-22 |
| `agregar_condiciones_pedido.sql` | ✅ 2026-08-22 (verificado: 2 tablas creadas) | ✅ 2026-08-22 (verificado: 2 tablas creadas) |
| `agregar_horario_revision_casilla.sql` | ✅ 2026-08-24 (verificado) | ✅ 2026-08-24 (verificado) |
| `agregar_kilos_y_cierre_armado.sql` | ✅ 2026-08-24 (verificado: 3 columnas creadas) | ✅ 2026-08-24 (verificado: 3 columnas creadas) |
| `agregar_stock_deposito.sql` | ✅ 2026-08-25 (verificado: 2 tablas y 3 índices) | ✅ 2026-08-25 (verificado: 2 tablas y 3 índices) |
| `agregar_reprocesos.sql` | ✅ 2026-08-25 (verificado: 3 tablas creadas) | ✅ 2026-08-25 (verificado: 3 tablas creadas) |
| `drop_foto_ruta_compras.sql` | ✅ 2026-08-25 (verificado: fotos en fotos_guia intactas y visibles) | ✅ 2026-08-25 (verificado: fotos en fotos_guia intactas y visibles) |
| `agregar_observabilidad_revision.sql` | ✅ 2026-08-25 | ✅ 2026-08-25 |
| `agregar_reingreso_vinculado.sql` | ✅ 2026-08-25 (verificado: 2 columnas creadas) | ✅ 2026-08-25 (verificado: 2 columnas creadas) |
| `agregar_costos_fijos.sql` | ✅ 2026-08-25 | ✅ 2026-08-25 |
| `agregar_cliente_reproceso.sql` | ✅ 2026-08-26 (verificado) | ✅ 2026-08-26 (verificado) |
| `agregar_destino_rechazo_y_merma_por_lote.sql` | ✅ 2026-08-26 (verificado: 4 columnas creadas) | ✅ 2026-08-26 (verificado: 4 columnas creadas) |
| `agregar_ficha_a_precios_venta.sql` | ✅ 2026-08-26 (verificado: 54 precios con ficha, 0 huérfanos) | ✅ 2026-08-26 (verificado: 38 precios con ficha, 0 huérfanos) |
| `agregar_ficha_a_pedidos_renglones.sql` | ✅ 2026-08-26 (verificado: 418 de 418 renglones con ficha, 0 sin identificar, 0 identificados sin ficha) | ✅ 2026-08-26 (verificado: 232 de 232 renglones con ficha, 0 sin identificar, 0 identificados sin ficha) |
| `permitir_varias_fichas_por_articulo.sql` | ✅ 2026-08-26 (verificado: unique viejo dropeado, los 2 índices nuevos creados; cero códigos repetidos en la verificación previa) | ✅ 2026-08-26 (verificado: unique viejo dropeado, los 2 índices nuevos creados; cero códigos repetidos en la verificación previa) |
| `drop_indice_viejo_precios_venta_historial.sql` | ✅ 2026-08-26 (verificado: índice viejo dropeado, quedan los 3 correctos — la primary key, `precios_venta_historial_ficha_vigente_idx` y el unique `precios_venta_historial_ficha_vigente_key`) | ✅ 2026-08-26 (verificado: índice viejo dropeado, quedan los 3 correctos — la primary key, `precios_venta_historial_ficha_vigente_idx` y el unique `precios_venta_historial_ficha_vigente_key`) |
| `agregar_alertas_estado.sql` | ✅ 2026-08-27 (verificado: las 6 columnas creadas) | ✅ 2026-08-27 (verificado: las 6 columnas creadas) |
| `agregar_senas_valor_historial.sql` | ✅ 2026-08-28 (verificado: 7/7 OK) | ✅ 2026-08-28 (verificado: 7/7 OK) |
| `senas_valor_historial_append_only.sql` (saca el UNIQUE por fecha, que obligaba a pisar el monto anterior; corrida con la tabla todavía vacía) | ✅ 2026-08-28 (verificado: 7/7 OK; el freno de mano no saltó) | ✅ 2026-08-28 (verificado: 7/7 OK; el freno de mano no saltó) |
| `agregar_ficha_a_reprocesos.sql` (etapa 1 del modelo nuevo: a qué ficha fueron las cajas de primera) | ✅ 2026-08-28 (verificado: 7/7 OK; **36 guías R** pre-corte, todas con ficha en NULL para siempre) | ✅ 2026-08-28 (verificado: 7/7 OK; **0 guías R**: sin historia, cualquier NULL posterior al corte es un "sin asignar" real) |
| `agregar_corte_y_stock_inicial.sql` (etapa 2 del modelo nuevo: la fecha de corte, el tipo `stock_inicial` con costo, y el reproceso inicial que produce sin consumir) | ✅ 2026-08-28 (verificado: 12/12 OK; corte en 2026-08-31; **36 guías R**, 0 con tipo distinto de `normal` — el default hizo lo suyo) | ✅ 2026-08-28 (verificado: 12/12 OK; corte en 2026-08-31; **0 guías R**, nada que convertir) |

## Deuda pendiente de limpieza

### Vacíos del Puesto: el ajuste no dice a qué conteo pertenece

El Cotejo calcula lo que queda sin explicar de un conteo restándole los
ajustes posteriores (ver `_sin_absorber` en `app/main.py`), acotados para
que un ajuste absorba solo hasta donde llega y solo en la dirección de
cerrar la diferencia. Eso arregla los dos casos que se vieron el 28/08,
pero queda un hueco: `ajustes_posteriores` es el NETO de todos los
ajustes posteriores al conteo.

El caso que todavía falla: conteo con diferencia −5, después un ajuste de
−5 que lo cierra y otro de +100 por un motivo distinto. El neto da +95,
el absorbido da 0, y la tarjeta muestra −5 en rojo para siempre aunque el
conteo esté cerrado. Es el bug del 27/08 —la tarjeta que nunca se pone en
verde— en un caso más raro.

El arreglo de fondo NO es aritmético: no hay fórmula sobre un neto que
distinga un ajuste que vino a cerrar el conteo de otro que pasaba por
ahí. Hay que VINCULARLOS: una columna `conteo_id` en `ajustes_vacios`
(nullable, la escribe el ajuste que nace del botón "Ajustar a lo
contado"), y que el Cotejo absorba solo los ajustes de ESE conteo en vez
de inferirlo de un neto. Los ajustes sueltos, cargados a mano por otro
motivo, quedan con `conteo_id` en NULL y no absorben nada — que es lo
correcto.

No es urgente: hace falta que en la misma pareja proveedor+tipo convivan,
después de un mismo conteo, un ajuste que lo cierra y otro que no.

### Vacíos del Puesto: los saldos iniciales están mezclados con las correcciones

Los saldos de arranque se cargaron por la pantalla de Ajustes, así que en
`ajustes_vacios` son indistinguibles de una corrección de faltante.
Cualquier reporte futuro de mermas de vacíos va a sumar esos 923 cajones
de arranque (657 + 257 + 9) como si se hubieran perdido.

Cuando se vuelva a tocar el módulo: agregar un tipo `saldo_inicial` (o un
motivo reservado) que los separe, y usarlo para excluirlos de las mermas.
Hoy no rompe nada porque ese reporte todavía no existe.

Esta deuda ya sirvió de algo: es la razón por la que el stock inicial de
la fecha de corte nace con tipo propio desde el día uno, en vez de
cargarse por la pantalla de ajustes como se hizo acá (ver "Decisiones
confirmadas", punto 7, en `docs/diseno_base_datos.md`).

(Las saldadas: `compras.foto_ruta` el 2026-08-25 con
`drop_foto_ruta_compras.sql`, y el índice viejo de
`precios_venta_historial` por `(cliente_id, articulo_id,
vigente_desde)` el 2026-08-26 con
`drop_indice_viejo_precios_venta_historial.sql` — las dos corridas en
las dos bases. De aquella limpieza la columna `articulo_id` SE QUEDÓ,
como estaba previsto: la usa el chequeo de Disponibles.)

### ~~Guías R: el botón "Anular guía" quedó en 37px~~ — SALDADA

Estaba por debajo de los 44px de la regla mobile-first. Se arregló en la
etapa 0, al mudar la pantalla a Administración, como estaba previsto:
`.boton-anular` en `templates/deposito_stock_guias_r.html` pasó a
`padding: 0.8rem 0.9rem`.

### Etapa 0, fase 3: `/deposito/pedido` todavía no se partió

Las fases 1 y 2 están hechas (Facturación pasó a llamarse Administración,
y las seis pantallas de control de stock se mudaron). Falta la tercera: la
pantalla de pedidos tiene dos mitades con dos dueños distintos —el
depósito arma, administración busca y corrige— y hoy comparten prefijo.

Cuando se retome, este relevamiento ya está hecho y es la mitad del
trabajo:

**Son 19 rutas colgando del prefijo `/deposito/pedido`** (`app/main.py`),
y **170 referencias** a esa cadena en `app/`, `templates/` y `tests/`. No
es un `sed`: cada referencia hay que mirarla para decidir de qué mitad es.

Las 19: `/deposito/pedido`, `/cargar`, `/cargar/leer`,
`/cargar/confirmar`, `/{id}/renglones/{rid}/asignar`, `/{id}/fotos`,
`/{id}/fotos/{fid}/ver`, `/{id}/fotos/{fid}/borrar`,
`/dias-sin-pedido`, `/dias-sin-pedido/deshacer`, `/armar`,
`/{id}/renglones/{rid}/armar`, `/desarmar`, `/anular`, `/desanular`,
`/{id}/terminar`, `/{id}/reabrir`, `/armar/buscar-pedido`,
`/mails/{mail_id}/revisar`.

**Tres trampas que ya se encontraron:**

1. **`/deposito/pedido/mails/{mail_id}/revisar` es un GET que ESCRIBE.**
   Si se le pone un 301 como a las demás rutas renombradas, el redirect
   puede reejecutar la escritura o perderla según el cliente. Esa ruta
   necesita tratamiento propio, no el redirect genérico.

2. **`templates/sistema_casilla_pedidos.html` linkea a la pantalla desde
   afuera del módulo.** Es un link entrante que no se ve grepeando solo
   `app/main.py`.

3. **El reparto de las tres alertas ya está confirmado por Lionel** (no
   hay que volver a decidirlo):
   - `pedidos_sin_identificar` → **Administración**
   - `pedidos_incompletos` → **queda en Depósito**, y su URL tiene que
     apuntar a la mitad de `/deposito/pedido` que quede en Depósito, no
     a la que se mude
   - `pedido_faltante` → **Administración**

   Hoy las tres están en `ALERTAS` (`app/main.py`, cerca de la línea
   7760) con `url="/deposito/pedido"` y `modulos=("deposito",)`.

Se difirió a pedido de Lionel el 28/08 para no comerse el sábado y llegar
con las etapas 2 y 3 del modelo nuevo antes del lunes de corte. No bloquea
nada: la navegación ya quedó coherente con las fases 1 y 2.

## Pasos manuales que NO son SQL (por base)

| Paso | Frutamax | Palmala |
|---|---|---|
| Bucket de Storage `comandas` (privado) | ✅ | ✅ 2026-08-19 |
| Copia inicial del catálogo (`scripts/copiar_catalogo_empresa.py`, o a mano por el navegador con `db/generar_inserts_catalogo.sql`) | — es el origen | ✅ 2026-08-19 (8 tablas verificadas) |
| Revisión a mano de parámetros de clientes y costos de envase copiados | — | ✅ 2026-08-19 |
| Verificación de esquema (`verificar_esquema.sql` en las dos bases, comparar) | ✅ 2026-08-19 (13/13 firmas idénticas) | ✅ 2026-08-19 (13/13 firmas idénticas) |

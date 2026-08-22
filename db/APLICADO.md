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
| `agregar_casilla_pedidos.sql` | ⬜ | ⬜ |

## Deuda pendiente de limpieza

| Qué | Por qué sigue ahí | Cuándo se resuelve |
|---|---|---|
| Columna `compras.foto_ruta` (MUERTA tras `agregar_fotos_guia.sql`) | Las fotos pasaron a `fotos_guia` (por guía, no por renglón). La columna quedó en la transición para poder volver atrás si algo falla en producción: el código ya no la escribe ni la lee. | DROP en una migración futura (`drop_foto_ruta_compras.sql`, a crear), cuando el dueño confirme que las fotos por guía andan bien en las dos empresas un tiempo prudencial. |

## Pasos manuales que NO son SQL (por base)

| Paso | Frutamax | Palmala |
|---|---|---|
| Bucket de Storage `comandas` (privado) | ✅ | ✅ 2026-08-19 |
| Copia inicial del catálogo (`scripts/copiar_catalogo_empresa.py`, o a mano por el navegador con `db/generar_inserts_catalogo.sql`) | — es el origen | ✅ 2026-08-19 (8 tablas verificadas) |
| Revisión a mano de parámetros de clientes y costos de envase copiados | — | ✅ 2026-08-19 |
| Verificación de esquema (`verificar_esquema.sql` en las dos bases, comparar) | ✅ 2026-08-19 (13/13 firmas idénticas) | ✅ 2026-08-19 (13/13 firmas idénticas) |

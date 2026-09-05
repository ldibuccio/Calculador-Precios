"""Aplicación FastAPI: pantallas de la app y prueba de conexión a la base de datos.

El motor de costeo y las fichas en core/ no se tocan. El lector de comandas
(core/lector_comandas.py) ahora sí se conecta, en la carga de compras por foto.
"""

import asyncio
import base64
from contextlib import asynccontextmanager
import hashlib
import hmac
import io
import json
import logging
import os
import re
import unicodedata
from datetime import date, datetime, time, timedelta, timezone
from urllib.parse import urlencode
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from PIL import Image, ImageOps

from app.alertas import (
    HORAS_VENCIMIENTO,
    DefinicionAlerta,
    frescura,
    hay_que_recalcular,
    modulos_inexistentes,
    para_mostrar,
    recalcular,
)
from app.costeo import (
    agrupar_para_negociar,
    calcular_listado_para_negociar_precios,
    calcular_listados_para_negociar_precios,
    calcular_objetivos_de_compra,
)
from app.db import (
    actualizar_articulo,
    actualizar_cantidad_compra,
    actualizar_cliente,
    actualizar_ficha,
    actualizar_importe_compra,
    actualizar_precio_compra,
    anular_ajuste_vacios,
    anular_vacio_devuelto,
    anular_vacio_recibido,
    aprender_articulo,
    buscar_compras,
    cambiar_actividad_proveedor,
    buscar_ingresos_deposito,
    buscar_retiros,
    cambiar_articulo_de_ficha,
    cambiar_fecha_activacion_casilla,
    contar_compras_buscadas,
    contar_ingresos_deposito,
    contar_mails_pedido_leidos_con_ia,
    contar_mails_pedido_sin_procesar,
    contar_pedidos_con_renglones_sin_identificar,
    contar_pedidos_incompletos,
    desmarcar_renglon_armado,
    marcar_renglon_armado,
    contar_retiros_buscados,
    cerrar_disponible_generado,
    cerrar_sena,
    comanda_ya_guardada,
    compra_tiene_cantidad_bloqueada,
    compra_tiene_deshacer_recepcion_bloqueado,
    compra_tiene_deshacer_retiro_bloqueado,
    compra_tiene_precio_bloqueado,
    contar_articulos,
    contar_articulos_comprados_incotizables,
    contar_compras_sin_precio,
    contar_recepciones_pendientes_viejas,
    contar_retiros_pendientes_viejos,
    contar_senas_pendientes_viejas,
    contar_stock_vacios_negativos,
    corregir_recepcion_compra,
    activar_casilla_pedidos,
    actualizar_casilla_pedidos,
    crear_articulo,
    crear_casilla_pedidos,
    crear_cliente,
    crear_compra,
    anular_movimiento_stock,
    articulos_con_salidas_stock,
    anular_remito_segunda,
    anular_reproceso,
    anular_renglon_stock_inicial,
    completar_costo_reproceso,
    contar_reprocesos_costo_incompleto,
    contar_stock_deposito_negativo,
    crear_conteo_stock,
    crear_movimiento_stock,
    crear_pedido,
    crear_remito_segunda,
    crear_reproceso,
    crear_reproceso_inicial,
    crear_stock_inicial,
    crear_ajuste_vacios,
    crear_compras_de_comanda,
    crear_conteo_vacios,
    crear_envase,
    crear_ficha,
    crear_tipo_envase_puesto,
    crear_vacio_devuelto,
    crear_vacio_recibido,
    desactivar_articulo,
    desactivar_casilla_pedidos,
    desactivar_cliente,
    desactivar_cliente_puesto,
    desactivar_proveedor_puesto,
    desactivar_tipo_envase_puesto,
    deshacer_procesado_compra,
    deshacer_retiro_compra,
    eliminar_compra,
    entradas_y_salidas_stock_articulo,
    fecha_corte,
    entradas_y_salidas_stock_articulos,
    listar_articulos_con_primera_de_cliente,
    crear_grupo_costos_fijos,
    crear_importe_costos_fijos,
    crear_subcuenta_costos_fijos,
    guardar_indice_inflacion,
    listar_grupos_costos_fijos,
    listar_importes_costos_fijos,
    listar_importes_de_subcuenta,
    listar_indices_inflacion,
    listar_subcuentas_costos_fijos,
    obtener_subcuenta_costos_fijos,
    devoluciones_vinculadas_por_rango,
    listar_pedidos_para_reingreso,
    listar_renglones_para_reingreso,
    obtener_renglon_para_reingreso,
    listar_conteos_stock_de_fecha,
    listar_movimientos_stock_por_rango,
    listar_remitos_segunda_por_rango,
    salidas_stock_articulo,
    salidas_stock_articulos,
    listar_reprocesos_por_rango,
    asignar_ficha_a_reproceso,
    listar_ultimos_conteos_stock,
    eliminar_compras_del_dia_por_proveedor,
    eliminar_ficha,
    guardar_disponible,
    guardar_precios_cliente,
    agregar_foto_guia,
    agregar_foto_guia_del_dia,
    agregar_foto_pedido,
    asignar_ficha_a_renglon_pedido,
    borrar_dia_sin_pedido,
    borrar_foto_guia,
    borrar_foto_pedido,
    fijar_auto_confirmar_casilla,
    guardar_alias_en_ficha,
    guardar_condiciones_pedido,
    guardar_horario_revision_casilla,
    listar_casillas_pedidos,
    listar_condiciones_pedido,
    listar_dias_sin_pedido,
    listar_fechas_con_pedido_vigente,
    listar_mails_pedido,
    listar_mails_pedido_sin_procesar_de_cliente,
    listar_pedidos_vigentes_con_armado,
    listar_renglones_pedidos_vigentes,
    anular_renglon_pedido,
    buscar_renglones_pedidos,
    cerrar_armado_pedido,
    desanular_renglon_pedido,
    marcar_dia_sin_pedido,
    marcar_lectura_mail_pedido,
    reabrir_armado_pedido,
    marcar_mail_pedido_confirmado,
    marcar_mail_pedido_error,
    marcar_mail_pedido_ignorado,
    obtener_casilla_pedidos,
    obtener_condiciones_pedido,
    obtener_mail_de_pedido,
    obtener_mail_pedido,
    obtener_pedido_vigente,
    registrar_mail_pedido,
    obtener_ultimo_tick_revision,
    registrar_revision_casilla,
    renombrar_proveedor,
    renombrar_proveedor_puesto,
    renombrar_tipo_envase_puesto,
    registrar_tick_revision,
    limpiar_foto_ruta_de_compras,
    listar_fotos_de_guia,
    listar_fotos_pedido,
    listar_ajustes_vacios_por_rango,
    listar_aprendizaje_articulos_por_proveedor,
    listar_articulos,
    listar_articulos_para_reproceso,
    cajas_armadas_por_ficha,
    lotes_para_reproceso,
    dependencias_del_lote_de_compra,
    desglose_de_renglon_armado,
    guardar_lotes_elegidos,
    StockInsuficienteParaReproceso,
    RepartoDesactualizado,
    ReprocesoAnteriorAlCorte,
    contar_fichas_por_articulo,
    listar_clientes,
    listar_clientes_puesto,
    listar_compras_pendientes_recepcion,
    listar_compras_pendientes_retiro,
    listar_compras_por_fecha_y_proveedor,
    listar_compras_procesadas_hoy_recepcion,
    listar_compras_procesadas_hoy_retiro,
    listar_compras_sin_precio,
    listar_conceptos_editables_por_cliente,
    listar_conteos_vacios_de_fecha,
    listar_detalle_disponible,
    listar_envases,
    listar_envases_con_costo,
    listar_historial_costos_envases,
    listar_historial_fichas_por_cliente,
    listar_fichas_de_todos_los_clientes,
    fichas_con_cajas_armadas,
    listar_stock_inicial,
    listar_fichas_por_cliente,
    listar_renglones_pedido,
    listar_sucursales_pedido,
    listar_fotos_para_limpiar,
    listar_precios_anteriores_por_cliente,
    listar_precios_vigentes_por_cliente,
    listar_proveedores,
    listar_proveedores_para_abm,
    listar_proveedores_puesto,
    listar_senas_pendientes,
    listar_senas_resueltas,
    listar_valores_sena,
    listar_historiales_valores_sena,
    contar_senas_afectadas_por_valor,
    contar_guias_r_afectadas_por_fecha,
    cargar_valor_sena,
    listar_tipos_envase_puesto,
    listar_todos_los_proveedores,
    listar_todas_las_conversiones,
    listar_ultimos_conteos_vacios,
    listar_vacios_devueltos_de_fecha,
    listar_vacios_devueltos_por_rango,
    listar_vacios_recibidos_de_fecha,
    listar_vacios_recibidos_por_rango,
    marcar_compra_cancelada,
    marcar_compra_no_ingresada,
    marcar_compra_retirada,
    obtener_articulo,
    obtener_borrador_disponible,
    obtener_cliente,
    obtener_compra,
    obtener_detalle_compra,
    obtener_ficha,
    obtener_o_crear_cliente_puesto,
    obtener_o_crear_proveedor_por_codigo,
    obtener_o_crear_proveedor_puesto,
    obtener_proveedor,
    obtener_ultimo_disponible_cliente,
    listar_estado_alertas,
    obtener_uso_storage_bucket,
    recepcionar_compra,
    rechazar_compra,
    registrar_costo_envase,
    stock_deposito_de_articulo,
    stock_deposito_por_articulo,
    stock_vacios,
    stock_vacios_de_tipo,
    total_reingresos_rechazo,
)
from core.conceptos_cliente import calcular_cambio_de_utilidad, calcular_cambios_de_tasas
from core.exportar_compras import generar_excel_listado_compras, generar_pdf_listado_compras
from core.exportar_disponibles import generar_excel_disponibles
from core.exportar_remanente import generar_excel_remanente
from core.exportar_precios import generar_excel_lista_precios, generar_pdf_lista_precios
from core.exportar_ingresos import generar_excel_ingresos_deposito, generar_pdf_ingresos_deposito
from core.exportar_retiros import generar_excel_listado_retiros, generar_pdf_listado_retiros
from core.exportar_vacios import (
    generar_excel_movimientos_vacios,
    generar_excel_stock_vacios,
    generar_pdf_movimientos_vacios,
    generar_pdf_stock_vacios,
)
from core.casilla_pedidos import (
    CLAVE_CASILLA_ENV_VAR,
    ErrorCasilla,
    clave_casilla_configurada,
    fecha_de_pedido_del_asunto,
    revisar_casilla,
    separar_remitentes,
    texto_del_mail_guardado,
)
from core.pedido_estructura import parsear_pedido_estructurado
from core.rentabilidad import ETIQUETAS_GRUPO, calcular_rentabilidad_de_pedidos
from core.costo_real import atribuir_costos_fifo, calcular_rentabilidad_real
from core.costos_fijos import calcular_costos_fijos
from core.stock import repartir_fifo, salidas_para_reparto
from core.exportar_rentabilidad import generar_excel_rentabilidad, generar_pdf_rentabilidad
from core.exportar_rentabilidad_real import generar_excel_rentabilidad_real, generar_pdf_rentabilidad_real
from core.exportar_pedidos import generar_excel_pedidos, generar_pdf_pedidos
from core.precios_venta import calcular_cambios_de_precios
from core.lector_archivos import comprimir_pdf, imagenes_desde_pdf, texto_desde_excel
from core.lector_comandas import (
    TEXTOS_PLACEHOLDER_LECTOR,
    extraer_comanda,
    extraer_listado_consolidado,
    extraer_listado_precios_de_imagenes,
    extraer_listado_precios_de_texto,
    extraer_pedido_de_imagenes,
    extraer_pedido_de_texto,
    recortar_bloque_de_empresa,
)
from core.matcheo_comanda import adivinar_articulo, adivinar_proveedor, agrupar_renglones_por_proveedor, normalizar_texto
from core.storage import BUCKET_COMANDAS, borrar_foto_comanda, obtener_url_foto, subir_archivo_comanda, subir_foto_comanda

UNIDADES_VENTA_VALIDAS = {"kilo", "unidad", "cubeta"}
GRUPOS_ARTICULO_VALIDOS = {"fruta", "hortaliza", "hoja", "pesada"}
TIPOS_RETIRO_VALIDOS = {"Clark", "Carro", "Pases", "Cooperativa"}

# Textos legibles para la pantalla de Detalle de una compra (ver ver_detalle_compra).
ESTADOS_RETIRO_LABELS = {None: "Sin datos", "pendiente": "Pendiente", "retirado": "Retirado", "cancelado": "Cancelado"}
ESTADOS_RECEPCION_LABELS = {
    None: "Sin datos",
    "pendiente": "Pendiente",
    "recepcionado": "Recibido",
    "rechazado": "Rechazo total",
    "no_ingresado": "No ingresó",
}
ORIGENES_RETIRO_LABELS = {
    None: None,
    "logistica": "Retirado por Logística",
    "deposito": "Retiro automático (recepcionado en Depósito)",
    "migracion": "Migración",
    "ingreso_directo": "Ingreso directo en Depósito",
    "automatico_carro": "Retiro a cargo del Carrero (automático)",
    "automatico_cooperativa": "Retiro a cargo de la Cooperativa (automático)",
}
# Hasta cuándo se ven los pedidos pasados en los listados de Pedido y
# Armar Pedido (los FUTUROS van siempre): un pedido armado no desaparece
# al día siguiente — queda consultable una semana. Tocar acá si el dueño
# quiere más historia a mano.
#
# La alerta pedidos_incompletos usa ESTE MISMO número para su ventana, y no
# por casualidad: una alerta no puede contar pedidos que la pantalla adonde
# lleva no muestra. Si fueran dos sietes sueltos, el día que alguien cambiara
# uno el banner diría "3" y la pantalla mostraría 2, sin ningún error. Por eso
# la alerta lo lee de acá en vez de repetirlo: un comentario que dijera "es el
# mismo 7 que el otro" envejece; una derivación no puede separarse.
#
# La dirección es esta y no la inversa: manda lo que la pantalla LISTA, y la
# alerta lo sigue. Alargar el listado hace que la alerta mire más atrás, que
# es correcto; acortarlo la achica sola, que también.
DIAS_PASADOS_LISTADO_PEDIDOS = 7

ARGENTINA = timezone(timedelta(hours=-3))
REGEX_CODIGO_PUESTO = re.compile(r"^[NL][0-9]{2}P[0-9]{2}$")

# Para el nombre del archivo de Disponibles (ej. "Disponibles_Frutamax_14_Ago_2026.xlsx").
MESES_ABREVIADOS = {
    1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic",
}

# Orden de secciones al precargar Disponibles desde fichas_logistica (primera
# vez que se arma uno para un cliente, sin ningún Disponible previo). Los
# renglones tipeados a mano (sin articulo_id, sin grupo) van al final. De
# ahí en más el orden queda fijo en disponibles_detalle.orden.
ORDEN_GRUPOS_DISPONIBLES = ["fruta", "hortaliza", "hoja", "pesada"]

NOMBRE_EMPRESA_ENV_VAR = "NOMBRE_EMPRESA"
# Mismo código para varias empresas (cada una con su propia base): el
# nombre que se ve en /inicio, en la barrita y en los archivos exportados
# sale de esta variable de entorno, para no tener que bifurcar el código
# por empresa. Frutamax es el valor de siempre — si la variable no está
# seteada, no cambia nada para ese deploy.
NOMBRE_EMPRESA = os.environ.get(NOMBRE_EMPRESA_ENV_VAR, "Frutamax")

TIPO_RETIRO_DEFAULT_ENV_VAR = "TIPO_RETIRO_DEFAULT"


def _tipo_retiro_default_desde_env() -> str:
    """El tipo de logística preseleccionado en las pantallas de carga, por empresa (variable de entorno).

    Mismo mecanismo que NOMBRE_EMPRESA: Frutamax no la setea y queda
    Clark (no cambia nada para ese deploy); Palmala la setea en Pases.
    Un valor que no sea uno de los cuatro tipos válidos cae a Clark en
    vez de romper las pantallas.

    Es SOLO la preselección de los <select> de carga: el DEFAULT de la
    columna tipo_retiro en la base nunca aplica, porque el código manda
    el valor explícito en todos los INSERT (ver _insertar_compra_con_guia).
    """
    valor = os.environ.get(TIPO_RETIRO_DEFAULT_ENV_VAR, "Clark").strip()
    return valor if valor in TIPOS_RETIRO_VALIDOS else "Clark"


TIPO_RETIRO_DEFAULT = _tipo_retiro_default_desde_env()

# Tope de filas de las pantallas de búsqueda (Buscar Compras, Consultar
# Retiros): un rango ancho no puede tirar miles de filas de HTML al
# celular. Los exports PDF/Excel NO lo usan: un archivo cortado en
# silencio sería peor que uno pesado.
TOPE_FILAS_BUSQUEDA = 500

CLAVE_CONTROL_PUESTO_ENV_VAR = "CLAVE_CONTROL_PUESTO"
COOKIE_ACCESO_CONTROL = "acceso_control_puesto"
# Una clave por jornada: ni en cada pantalla (no la usarían) ni para
# siempre (pantalla desbloqueada eterna). El botón Bloquear la corta antes.
DURACION_ACCESO_CONTROL = 12 * 60 * 60


def _clave_control_puesto() -> str | None:
    """ÚNICA fuente de la clave de la zona de control del Puesto — todo el resto del código pasa por acá.

    Hoy sale de Railway (variable de entorno, una por empresa). Cuando
    exista el módulo de Contraseñas en Sistema, el origen se cambia SOLO
    en esta función y nada más se toca. Se lee en cada request (no al
    importar) a propósito: así un cambio de origen o de valor aplica sin
    reiniciar nada más que lo que corresponda.

    None = no hay clave configurada = no hay puerta (todo como siempre).
    """
    clave = os.environ.get(CLAVE_CONTROL_PUESTO_ENV_VAR, "").strip()
    return clave or None


def _firma_acceso_control(clave: str) -> str:
    """Lo que viaja en la cookie: una firma derivada de la clave, nunca la clave.

    Sin estado en el server ni en la base: la firma solo se puede fabricar
    conociendo la clave, y si la clave se cambia en el origen, todas las
    cookies viejas dejan de validar al instante (bloqueo remoto gratis).
    """
    return hmac.new(clave.encode(), b"acceso-control-puesto", hashlib.sha256).hexdigest()


def _acceso_control_valido(request: Request) -> bool:
    clave = _clave_control_puesto()
    if clave is None:
        return True
    cookie = request.cookies.get(COOKIE_ACCESO_CONTROL, "")
    return hmac.compare_digest(cookie, _firma_acceso_control(clave))


def _destino_control_seguro(volver: str) -> str:
    """El destino post-clave solo puede ser una pantalla de Envases Puesto (nada de redirigir a cualquier lado)."""
    return volver if volver.startswith("/puesto/envases") else "/puesto/envases"


# --- Clave de Gerencia: la zona del manejo del dinero (rentabilidades) ---
# Clave PROPIA, aparte de la del control del Puesto: el que maneja los
# vacíos del puesto no tiene por qué ver la rentabilidad. Mismo diseño
# (cookie firmada por jornada, Bloquear, sin estado en server ni base).

CLAVE_GERENCIA_ENV_VAR = "CLAVE_GERENCIA"
COOKIE_ACCESO_GERENCIA = "acceso_gerencia"


def _clave_gerencia() -> str | None:
    """ÚNICA fuente de la clave de Gerencia — todo el resto del código pasa por acá.

    Hoy sale de Railway (variable de entorno, una por empresa). Cuando
    exista el módulo de Contraseñas en Sistema, el origen se cambia SOLO
    en esta función (igual que _clave_control_puesto) y nada más se toca.
    Se lee en cada request a propósito.

    None = no hay clave configurada = no hay puerta (todo como siempre) —
    así el deploy no traba nada hasta que la variable se cargue.
    """
    clave = os.environ.get(CLAVE_GERENCIA_ENV_VAR, "").strip()
    return clave or None


def _firma_acceso_gerencia(clave: str) -> str:
    """La firma de la cookie de Gerencia (nunca la clave). Mensaje propio: una cookie del Puesto jamás valida acá."""
    return hmac.new(clave.encode(), b"acceso-gerencia", hashlib.sha256).hexdigest()


def _acceso_gerencia_valido(request: Request) -> bool:
    clave = _clave_gerencia()
    if clave is None:
        return True
    cookie = request.cookies.get(COOKIE_ACCESO_GERENCIA, "")
    return hmac.compare_digest(cookie, _firma_acceso_gerencia(clave))


def _destino_gerencia_seguro(volver: str) -> str:
    """El destino post-clave solo puede ser una pantalla de Gerencia."""
    return volver if volver.startswith("/gerencia") else "/gerencia"


def _pantalla_clave_gerencia(request: Request, *, volver: str | None = None, error: str | None = None):
    """La puerta de Gerencia: pide la clave y vuelve a la pantalla que se quería ver."""
    if volver is None:
        volver = request.url.path + (f"?{request.url.query}" if request.url.query else "")
    return templates.TemplateResponse(
        request,
        "clave_gerencia.html",
        {"volver": _destino_gerencia_seguro(volver), "error": error},
        status_code=401,
    )


def _puerta_de_gerencia_para_escribir(request: Request):
    """La puerta de Gerencia para una pantalla que ESCRIBE. Devuelve None si puede pasar.

    Se diferencia del resto de Gerencia en una sola cosa, y es a propósito:
    **sin clave configurada NO deja pasar**. Las pantallas de consulta
    (rentabilidades, costos fijos) se abren igual mientras la variable no
    esté cargada, para que un deploy no trabe nada; acá el default se da
    vuelta. Una rentabilidad que se ve de más es un problema; una pantalla
    que corrige una recepción —y que puede dejar sin explicación el costo
    congelado de una guía R— abierta a cualquiera que sepa la URL es otro.

    Y lo dice con nombre y apellido: qué variable falta y dónde cargarla.
    Un "no autorizado" sin explicación manda a buscar un permiso que no
    existe.
    """
    if _clave_gerencia() is None:
        return templates.TemplateResponse(
            request,
            "gerencia_sin_clave.html",
            {"variable": CLAVE_GERENCIA_ENV_VAR},
            status_code=503,
        )
    if not _acceso_gerencia_valido(request):
        return _pantalla_clave_gerencia(request)
    return None


def _pantalla_clave_control(request: Request, *, volver: str | None = None, error: str | None = None):
    """La puerta de la zona de control: pide la clave y vuelve a la pantalla que se quería ver."""
    if volver is None:
        volver = request.url.path + (f"?{request.url.query}" if request.url.query else "")
    return templates.TemplateResponse(
        request,
        "clave_control_puesto.html",
        {"volver": _destino_control_seguro(volver), "error": error},
        status_code=401,
    )


def _nombre_empresa_para_archivo() -> str:
    """El nombre de la empresa apto para nombres de archivo: sin acentos ni caracteres raros.

    "Verdulería Sur" -> "Verduleria_Sur": los acentos en un header Content-Disposition
    dependen de cómo cada navegador/celular los interprete — mejor no
    arriesgar el nombre del archivo por una tilde.
    """
    sin_acentos = unicodedata.normalize("NFKD", NOMBRE_EMPRESA).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^A-Za-z0-9]+", "_", sin_acentos).strip("_") or "Empresa"


def _hoy_argentina():
    """Fecha de hoy en Argentina (UTC-3 fijo, sin horario de verano), sin depender de la hora del servidor."""
    return datetime.now(ARGENTINA).date()

# Sin esto, uvicorn deja el logger del módulo en WARNING y los logs INFO
# del bucle de revisión (arranque y ticks) no aparecen en Railway — que es
# exactamente donde hacen falta para ver si el tick corre sin deducirlo.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Referencia FUERTE al task de fondo: el event loop guarda solo
# referencias débiles a las tasks (pitfall documentado de create_task) y
# un task recolectado por el GC muere en silencio.
_TAREAS_DE_FONDO: set = set()


@asynccontextmanager
async def _ciclo_de_vida(app_fastapi):
    """El lifespan de la app (reemplaza al @app.on_event("startup") deprecado).

    Arranca el bucle de revisión de casillas al iniciar y lo cancela
    prolijo al apagar. Los nombres se resuelven en tiempo de ejecución:
    _bucle_revision_casillas se define más abajo en este módulo, y para
    cuando el server arranca ya existe.
    """
    tarea = asyncio.create_task(_bucle_revision_casillas())
    _TAREAS_DE_FONDO.add(tarea)
    tarea.add_done_callback(_TAREAS_DE_FONDO.discard)
    yield
    tarea.cancel()


app = FastAPI(lifespan=_ciclo_de_vida)
templates = Jinja2Templates(directory="templates")


def _formatear_numero(valor) -> str:
    """Muestra un número sin decimales de sobra (16 en vez de 16.0), para pantallas de celular.

    Si tiene parte decimal la conserva (16.5 sigue siendo "16.5"), solo saca
    los ceros que no aportan nada.
    """
    if valor is None:
        return ""
    return f"{float(valor):.2f}".rstrip("0").rstrip(".")


def _formatear_fecha_corta(fecha) -> str:
    """Fecha en formato dd/mm (sin año), para que la tabla de compras entre en la pantalla del celular."""
    if fecha is None:
        return ""
    return fecha.strftime("%d/%m")


def _agrupar_miles(digitos: str) -> str:
    """Inserta "." cada tres cifras, de derecha a izquierda (1234567 -> "1.234.567")."""
    grupos = []
    while len(digitos) > 3:
        grupos.insert(0, digitos[-3:])
        digitos = digitos[:-3]
    grupos.insert(0, digitos)
    return ".".join(grupos)


def _formatear_moneda(valor) -> str:
    """Formatea un importe como "$45.000": símbolo $, "." cada tres cifras, redondeado al peso entero (sin decimales)."""
    if valor is None:
        return ""

    entero = round(float(valor))
    negativo = entero < 0
    return f"${'-' if negativo else ''}{_agrupar_miles(str(abs(entero)))}"


def _formatear_kilos(valor) -> str:
    """Formatea un peso en kilos como número entero, sin decimales ni coma (1500.5 -> "1500")."""
    if valor is None:
        return ""
    return str(round(float(valor)))


def _formatear_fecha_hora(valor) -> str:
    """Fecha y hora completas en horario argentino ("17/08/2026 14:35"), para pantallas de historial como Detalle."""
    if valor is None:
        return ""
    return valor.astimezone(ARGENTINA).strftime("%d/%m/%Y %H:%M")


def _formatear_hora(valor) -> str:
    """Solo la hora en horario argentino ("14:35"), para listas ya acotadas a un día (ej. "Procesados hoy")."""
    if valor is None:
        return ""
    return valor.astimezone(ARGENTINA).strftime("%H:%M")


def _formatear_hora_corta(valor) -> str:
    """Un time PURO (time(12, 0) o "12:00:00") como "12:00" — sin zona: ya viene en hora argentina."""
    if valor is None:
        return ""
    if isinstance(valor, str):
        return valor[:5]
    return valor.strftime("%H:%M")


def _formatear_porcentaje(valor) -> str:
    """Formatea una fracción (0.2548) como porcentaje con un decimal y coma decimal ("25,5%")."""
    if valor is None:
        return ""
    return f"{float(valor) * 100:.1f}%".replace(".", ",")


SUFIJOS_UNIDAD_COMPRA = {"kilo": "k", "unidad": "u", "cubeta": "c"}


def _sufijo_unidad(unidad_compra) -> str:
    """Letra corta para pegar junto al contenido por cajón (16k, 10u, 5c), para no tener que agregar otra columna."""
    return SUFIJOS_UNIDAD_COMPRA.get(unidad_compra, "")


def _formatear_bytes(valor) -> str:
    """Formatea un tamaño en bytes de forma legible, con la unidad que quede natural (886 KB, 339,5 MB, 1,2 GB).

    bytes/KB se muestran sin decimales; MB/GB con uno, para el indicador de
    espacio usado del bucket de fotos — un dato informativo, no hace falta
    precisión de más.
    """
    if valor is None:
        return ""
    numero = float(valor)
    for unidad in ("bytes", "KB", "MB", "GB"):
        if numero < 1024 or unidad == "GB":
            break
        numero /= 1024
    if unidad in ("bytes", "KB"):
        return f"{round(numero)} {unidad}"
    return f"{numero:.1f} {unidad}".replace(".", ",")


templates.env.filters["numero"] = _formatear_numero
templates.env.filters["fecha_corta"] = _formatear_fecha_corta
templates.env.filters["moneda"] = _formatear_moneda
templates.env.filters["porcentaje"] = _formatear_porcentaje
templates.env.filters["kilos"] = _formatear_kilos
templates.env.filters["sufijo_unidad"] = _sufijo_unidad
templates.env.filters["tamano"] = _formatear_bytes
templates.env.filters["fecha_hora"] = _formatear_fecha_hora
templates.env.filters["hora"] = _formatear_hora
templates.env.filters["hora_corta"] = _formatear_hora_corta


# Íconos de navegación: SVG minimalistas de línea (heroicons, MIT), un solo
# lugar para toda la app — la barrita de cada pantalla y las tarjetas de
# /inicio leen de acá, así el mismo ícono representa siempre al mismo sector.
_ICONO_INICIO = (
    '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">'
    '<path stroke-linecap="round" stroke-linejoin="round" d="m2.25 12 8.954-8.955c.44-.439 1.152-.439 1.591 0L21.75 12M4.5 9.75v10.125c0 .621.504 1.125 1.125 1.125H9.75v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21h4.125c.621 0 1.125-.504 1.125-1.125V9.75M8.25 21h8.25"/>'
    "</svg>"
)

SECTORES = {
    "compras": {
        "nombre": "Compras",
        "url": "/compras",
        "icono": (
            '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">'
            '<path stroke-linecap="round" stroke-linejoin="round" d="M2.25 3h1.386c.51 0 .955.343 1.087.835l.383 1.437M7.5 14.25a3 3 0 0 0-3 3h15.75m-12.75-3h11.218c1.121-2.3 2.1-4.684 2.924-7.138a60.114 60.114 0 0 0-16.536-1.84M7.5 14.25 5.106 5.272M6 20.25a.75.75 0 1 1-1.5 0 .75.75 0 0 1 1.5 0Zm12.75 0a.75.75 0 1 1-1.5 0 .75.75 0 0 1 1.5 0Z"/>'
            "</svg>"
        ),
    },
    "comercial": {
        "nombre": "Comercial",
        "url": "/comercial",
        "icono": (
            '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">'
            '<path stroke-linecap="round" stroke-linejoin="round" d="M20.25 14.15v4.25c0 1.094-.787 2.036-1.872 2.18-2.087.277-4.216.42-6.378.42s-4.291-.143-6.378-.42c-1.085-.144-1.872-1.086-1.872-2.18v-4.25m16.5 0a2.18 2.18 0 0 0 .75-1.661V8.706c0-1.081-.768-2.015-1.837-2.175a48.114 48.114 0 0 0-3.413-.387m4.5 8.006c-.194.165-.42.295-.673.38A23.978 23.978 0 0 1 12 15.75c-2.648 0-5.195-.429-7.577-1.22a2.016 2.016 0 0 1-.673-.38m0 0A2.18 2.18 0 0 1 3 12.489V8.706c0-1.081.768-2.015 1.837-2.175a48.111 48.111 0 0 1 3.413-.387m7.5 0V5.25A2.25 2.25 0 0 0 13.5 3h-3a2.25 2.25 0 0 0-2.25 2.25v.894m7.5 0a48.667 48.667 0 0 0-7.5 0M12 12.75h.008v.008H12v-.008Z"/>'
            "</svg>"
        ),
    },
    "logistica": {
        "nombre": "Logística",
        "url": "/logistica",
        "icono": (
            '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">'
            '<path stroke-linecap="round" stroke-linejoin="round" d="M8.25 18.75a1.5 1.5 0 0 1-3 0m3 0a1.5 1.5 0 0 0-3 0m3 0h6m-9 0H3.375a1.125 1.125 0 0 1-1.125-1.125V14.25m17.25 4.5a1.5 1.5 0 0 1-3 0m3 0a1.5 1.5 0 0 0-3 0m3 0h1.125c.621 0 1.129-.504 1.09-1.124a17.902 17.902 0 0 0-3.213-9.193 2.056 2.056 0 0 0-1.58-.86H14.25M16.5 18.75h-2.25m0-11.177v-.958c0-.568-.422-1.048-.987-1.106a48.554 48.554 0 0 0-10.026 0 1.106 1.106 0 0 0-.987 1.106v7.635m12-6.677v6.677m0 4.5v-4.5m0 0h-12"/>'
            "</svg>"
        ),
    },
    "deposito": {
        "nombre": "Depósito",
        "url": "/deposito",
        "icono": (
            '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">'
            '<path stroke-linecap="round" stroke-linejoin="round" d="m20.25 7.5-.625 10.632a2.25 2.25 0 0 1-2.247 2.118H6.622a2.25 2.25 0 0 1-2.247-2.118L3.75 7.5M10 11.25h4M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125Z"/>'
            "</svg>"
        ),
    },
    "gerencia": {
        "nombre": "Gerencia",
        "url": "/gerencia",
        "icono": (
            '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">'
            '<path stroke-linecap="round" stroke-linejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z"/>'
            "</svg>"
        ),
    },
    "auditoria": {
        "nombre": "Auditoría",
        "url": "/auditoria",
        "icono": (
            '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">'
            '<path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75 11.25 15 15 9.75m-3-7.036A11.959 11.959 0 0 1 3.598 6 11.99 11.99 0 0 0 3 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285Z"/>'
            "</svg>"
        ),
    },
    "administracion": {
        "nombre": "Administración",
        "url": "/administracion",
        "icono": (
            '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">'
            '<path stroke-linecap="round" stroke-linejoin="round" d="M9 14.25l6-6m4.5-3.493V21.75l-3.75-1.5-3.75 1.5-3.75-1.5-3.75 1.5V4.757c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0 1 11.186 0c1.1.128 1.907 1.077 1.907 2.185ZM9.75 9h.008v.008H9.75V9Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm4.125 4.5h.008v.008h-.008V13.5Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Z"/>'
            "</svg>"
        ),
    },
    "puesto": {
        "nombre": "Puesto",
        "url": "/puesto",
        "icono": (
            '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">'
            '<path stroke-linecap="round" stroke-linejoin="round" d="M13.5 21v-7.5a.75.75 0 0 1 .75-.75h3a.75.75 0 0 1 .75.75V21m-4.5 0H2.36m11.14 0H18m0 0h3.64m-1.39 0V9.349M3.75 21V9.349m0 0a3.001 3.001 0 0 0 3.75-.615A2.993 2.993 0 0 0 9.75 9.75c.896 0 1.7-.393 2.25-1.016a2.993 2.993 0 0 0 2.25 1.016c.896 0 1.7-.393 2.25-1.015a3.001 3.001 0 0 0 3.75.614m-16.5 0a3.004 3.004 0 0 1-.621-4.72l1.189-1.19A1.5 1.5 0 0 1 5.378 3h13.243a1.5 1.5 0 0 1 1.06.44l1.19 1.189a3 3 0 0 1-.621 4.72M6.75 18h3.75a.75.75 0 0 0 .75-.75V13.5a.75.75 0 0 0-.75-.75H6.75a.75.75 0 0 0-.75.75v3.75c0 .414.336.75.75.75Z"/>'
            "</svg>"
        ),
    },
    "sistema": {
        "nombre": "Sistema",
        "url": "/sistema",
        "icono": (
            '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">'
            '<path stroke-linecap="round" stroke-linejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 0 1 1.37.49l1.296 2.247a1.125 1.125 0 0 1-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 0 1 0 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 0 1-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 0 1-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 0 1-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 0 1-1.369-.49l-1.297-2.247a1.125 1.125 0 0 1 .26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 0 1 0-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 0 1-.26-1.43l1.297-2.247a1.125 1.125 0 0 1 1.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28Z"/>'
            '<path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z"/>'
            "</svg>"
        ),
    },
}

templates.env.globals["SECTORES"] = SECTORES

# |tojson es la forma correcta de meter un texto de la base adentro de una
# cadena de JavaScript: escapa < > & ' como \u00XX, así que el navegador los
# devuelve enteros al parsear el literal. Escribirlos a mano entre comillas
# hacía que Jinja escapara el & a HTML y se leyera "&amp;" en pantalla.
#
# ensure_ascii=False para que los acentos NO salgan como \u00f3: "cajón"
# tiene que poder leerse en el HTML igual que antes. Lo que hace falta
# escapar (< > & ') lo escapa Jinja aparte, después del dumps, y eso no
# depende de esta opción.
templates.env.policies["json.dumps_kwargs"] = {"sort_keys": True, "ensure_ascii": False}
templates.env.globals["ICONO_INICIO"] = _ICONO_INICIO
templates.env.globals["NOMBRE_EMPRESA"] = NOMBRE_EMPRESA
templates.env.globals["TIPO_RETIRO_DEFAULT"] = TIPO_RETIRO_DEFAULT
# Callables a propósito (se evalúan en cada render, no al importar): el
# botón Bloquear solo aparece si la clave de esa zona está configurada.
templates.env.globals["clave_control_activa"] = lambda: _clave_control_puesto() is not None
templates.env.globals["clave_gerencia_activa"] = lambda: _clave_gerencia() is not None


def _validar_nombre(nombre: str) -> tuple[str | None, str]:
    """Valida nombre no vacío. Devuelve (error, nombre_limpio)."""
    nombre = nombre.strip()

    if not nombre:
        return "El nombre no puede estar vacío.", nombre

    return None, nombre


def _validar_porcentaje(texto: str, etiqueta: str) -> tuple[str | None, float | None]:
    """Valida un porcentaje 0-100. Devuelve (error, valor)."""
    texto = texto.strip()

    if not texto:
        return f"{etiqueta} es obligatorio.", None

    try:
        valor = float(texto)
    except ValueError:
        return f"{etiqueta} tiene que ser un número.", None

    if not (0 <= valor <= 100):
        return f"{etiqueta} tiene que estar entre 0 y 100.", None

    return None, valor


def _leer_filas_tasas_del_form(form, prefijo: str) -> list[dict]:
    """Lee del form todas las filas de un grupo de tasas ("tasa_suma" o "tasa_resta"), sin validar todavía.

    Cada fila devuelta: nombre_original, valor_original_pct (texto), nombre,
    valor_pct (texto), baja (bool) — tal cual vino, para poder tanto
    validarla como volver a mostrarla en pantalla si hay un error en OTRO
    campo del formulario. Una fila completamente vacía (sin nombre, sin %,
    y que tampoco existía antes) se descarta acá: no representa nada, ni
    para guardar ni para redibujar.
    """
    try:
        cantidad = int(form.get(f"cantidad_{prefijo}s", "0") or "0")
    except ValueError:
        cantidad = 0

    filas = []
    for indice in range(cantidad):
        nombre_original = str(form.get(f"{prefijo}_{indice}_nombre_original", "")).strip()
        valor_original_texto = str(form.get(f"{prefijo}_{indice}_valor_original", "")).strip()
        nombre = str(form.get(f"{prefijo}_{indice}_nombre", "")).strip()
        valor_texto = str(form.get(f"{prefijo}_{indice}_valor", "")).strip()
        baja = form.get(f"{prefijo}_{indice}_baja") == "on"

        if not nombre and not valor_texto and not nombre_original:
            continue

        filas.append(
            {
                "nombre_original": nombre_original,
                "valor_original_texto": valor_original_texto,
                "nombre": nombre,
                "valor_texto": valor_texto,
                "baja": baja,
            }
        )
    return filas


def _validar_filas_tasas(filas: list[dict], etiqueta_grupo: str) -> tuple[str | None, list[dict]]:
    """Valida cada fila (nombre + % completos, salvo que esté dada de baja) y convierte % a fracción.

    Devuelve (error, filas_para_el_diff) — filas_para_el_diff ya tiene la
    forma que espera core.conceptos_cliente.calcular_cambios_de_tasas.
    """
    filas_validas = []
    for fila in filas:
        if not fila["baja"] and (bool(fila["nombre"]) != bool(fila["valor_texto"])):
            return f"Completá el nombre y el porcentaje de cada tasa de {etiqueta_grupo} (o sacá la fila).", []

        valor = None
        if fila["valor_texto"]:
            error, valor_pct = _validar_porcentaje(fila["valor_texto"], f"Una tasa de {etiqueta_grupo}")
            if error:
                return error, []
            valor = valor_pct / 100

        valor_original = float(fila["valor_original_texto"]) / 100 if fila["valor_original_texto"] else None

        filas_validas.append(
            {
                "nombre_original": fila["nombre_original"],
                "valor_original": valor_original,
                "nombre": fila["nombre"],
                "valor": valor,
                "baja": fila["baja"],
            }
        )
    return None, filas_validas


def _filas_para_mostrar_de_nuevo(filas_crudas: list[dict]) -> list[dict]:
    """Arma el contexto que necesita el template a partir de las filas crudas leídas del form.

    Se usa para volver a mostrar la pantalla con lo que el usuario tipeó
    cuando hay un error en OTRO campo del formulario (no se pierde lo ya
    cargado).
    """
    return [
        {
            "nombre": fila["nombre"],
            "valor_pct": fila["valor_texto"],
            "nombre_original": fila["nombre_original"],
            "valor_original_pct": fila["valor_original_texto"],
        }
        for fila in filas_crudas
    ]


def _filas_desde_conceptos_guardados(tasas: list[dict]) -> list[dict]:
    """Arma el contexto del template a partir de lo que ya está guardado (GET, recién cargada la pantalla).

    nombre_original/valor_original_pct arrancan iguales a nombre/valor_pct
    porque todavía no se tocó nada — son el punto de partida contra el que
    se compara al guardar.
    """
    return [
        {
            "nombre": tasa["nombre"],
            "valor_pct": tasa["valor_pct"],
            "nombre_original": tasa["nombre"],
            "valor_original_pct": tasa["valor_pct"],
        }
        for tasa in tasas
    ]


def _contexto_formulario_cliente(
    modo: str,
    nombre_texto: str,
    filas_suma_crudas: list[dict],
    filas_resta_crudas: list[dict],
    utilidad_texto: str,
    error: str | None,
    cliente_id: int | None = None,
) -> dict:
    """Contexto para volver a mostrar cliente_formulario.html con lo que el usuario tipeó, tras un error."""
    return {
        "modo": modo,
        "cliente": {"id": cliente_id, "nombre": nombre_texto},
        "tasas_suma": _filas_para_mostrar_de_nuevo(filas_suma_crudas),
        "tasas_resta": _filas_para_mostrar_de_nuevo(filas_resta_crudas),
        "utilidad_pct": utilidad_texto,
        "error": error,
    }


def _validar_unidad_venta(valor: str) -> str | None:
    """Valida que la unidad de venta sea kilo, unidad o cubeta."""
    if valor not in UNIDADES_VENTA_VALIDAS:
        return "Elegí una unidad de venta válida (kilo, unidad o cubeta)."
    return None


def _validar_unidad_compra(valor: str) -> str | None:
    """Valida que la unidad de compra sea kilo, unidad o cubeta."""
    if valor not in UNIDADES_VENTA_VALIDAS:
        return "Elegí una unidad de compra válida (kilo, unidad o cubeta)."
    return None


def _validar_grupo(valor: str) -> tuple[str | None, str | None]:
    """Valida el grupo del artículo (fruta, hortaliza, ...). Vacío es válido: sin clasificar todavía."""
    valor = valor.strip()
    if not valor:
        return None, None
    if valor not in GRUPOS_ARTICULO_VALIDOS:
        return "Elegí un grupo válido (fruta, hortaliza, hoja o pesada).", None
    return None, valor


def _validar_envase(envase_id_texto: str) -> tuple[str | None, int | None]:
    """Valida el envase elegido (opcional: "sin envase" es válido). Devuelve (error, envase_id)."""
    envase_id_texto = envase_id_texto.strip()

    if not envase_id_texto:
        return None, None

    try:
        return None, int(envase_id_texto)
    except ValueError:
        return "El envase elegido no es válido.", None


def _validar_contenido_caja(contenido_caja_texto: str) -> tuple[str | None, float | None]:
    """Valida el contenido solicitado: siempre obligatorio, número positivo, sin importar el envase."""
    contenido_caja_texto = contenido_caja_texto.strip()

    if not contenido_caja_texto:
        return "El contenido solicitado es obligatorio.", None

    try:
        contenido_caja = float(contenido_caja_texto)
    except ValueError:
        return "El contenido solicitado tiene que ser un número.", None

    if contenido_caja <= 0:
        return "El contenido solicitado tiene que ser mayor a cero.", None

    return None, contenido_caja


def _envase_variable_desde_form(valor: str) -> bool:
    """Un checkbox HTML solo manda un valor cuando está tildado; si no llega nada, es False."""
    return bool(valor.strip())


def _validar_cantidad_opcional(texto: str, etiqueta: str) -> tuple[str | None, float | None]:
    """Valida una cantidad opcional (kilos o fracción): vacía es válida, si viene tiene que ser positiva."""
    texto = texto.strip()

    if not texto:
        return None, None

    try:
        valor = float(texto)
    except ValueError:
        return f"{etiqueta} tiene que ser un número.", None

    if valor <= 0:
        return f"{etiqueta} tiene que ser mayor a cero.", None

    return None, valor


def _validar_importe(texto: str) -> tuple[str | None, float | None]:
    """Valida el importe: opcional (compra sin precio, se arregla después), si viene tiene que ser positivo."""
    texto = texto.strip()

    if not texto:
        return None, None

    try:
        valor = float(texto)
    except ValueError:
        return "El importe tiene que ser un número.", None

    if valor <= 0:
        return "El importe tiene que ser mayor a cero.", None

    return None, valor


def _validar_importe_pendiente(texto: str) -> tuple[str | None, float | None]:
    """Valida el importe al completar una compra pendiente: acá sí es obligatorio."""
    texto = texto.strip()

    if not texto:
        return "El importe es obligatorio.", None

    try:
        valor = float(texto)
    except ValueError:
        return "El importe tiene que ser un número.", None

    if valor <= 0:
        return "El importe tiene que ser mayor a cero.", None

    return None, valor


def _validar_sena(texto: str) -> tuple[str | None, float | None]:
    """Valida la seña: opcional, número mayor o igual a cero si viene cargada."""
    texto = texto.strip()

    if not texto:
        return None, None

    try:
        valor = float(texto)
    except ValueError:
        return "La seña tiene que ser un número.", None

    if valor < 0:
        return "La seña no puede ser negativa.", None

    return None, valor


def _validar_tipo_retiro(valor: str) -> str | None:
    """Valida que el tipo de retiro sea uno de TIPOS_RETIRO_VALIDOS (Clark, Carro o Pases)."""
    if valor not in TIPOS_RETIRO_VALIDOS:
        return "Elegí un tipo de retiro válido (Clark, Carro o Pases)."
    return None


def _validar_cantidad_cajones(texto: str) -> tuple[str | None, float | None]:
    """Valida la cantidad de cajones/cajas comprados: obligatoria, número positivo."""
    texto = texto.strip()

    if not texto:
        return "La cantidad de cajones es obligatoria.", None

    try:
        valor = float(texto)
    except ValueError:
        return "La cantidad de cajones tiene que ser un número.", None

    if valor <= 0:
        return "La cantidad de cajones tiene que ser mayor a cero.", None

    return None, valor


def _validar_contenido_por_cajon(texto: str) -> tuple[str | None, float | None]:
    """Valida el contenido por cajón de esta compra: obligatorio, número positivo."""
    texto = texto.strip()

    if not texto:
        return "El contenido por cajón es obligatorio.", None

    try:
        valor = float(texto)
    except ValueError:
        return "El contenido por cajón tiene que ser un número.", None

    if valor <= 0:
        return "El contenido por cajón tiene que ser mayor a cero.", None

    return None, valor


def _validar_codigo_puesto(texto: str) -> tuple[str | None, str | None]:
    """Valida el código de puesto: obligatorio, formato letra N/L + 2 dígitos + P + 2 dígitos."""
    codigo = texto.strip().upper()

    if not codigo:
        return "El código de puesto es obligatorio.", None

    if not REGEX_CODIGO_PUESTO.match(codigo):
        return "El código de puesto tiene que tener el formato NNNPNN, por ejemplo N07P41 o L03P38.", None

    return None, codigo


@app.get("/")
def estado() -> dict:
    return {"estado": "ok"}


@app.get("/inicio")
def ver_inicio(request: Request):
    return templates.TemplateResponse(request, "inicio.html", {})


@app.get("/salud/db")
def salud_db() -> dict:
    try:
        cantidad_articulos = contar_articulos()
    except RuntimeError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error}") from error

    return {"articulos": cantidad_articulos}


@app.get("/articulos")
def ver_articulos(request: Request, error: str | None = None):
    try:
        articulos = listar_articulos()
    except Exception as error_db:
        return templates.TemplateResponse(
            request,
            "articulos.html",
            {"articulos": [], "error": f"No se pudo leer el catálogo: {error_db}"},
            status_code=500,
        )

    return templates.TemplateResponse(
        request, "articulos.html", {"articulos": articulos, "error": error}
    )


@app.post("/articulos/nuevo")
def agregar_articulo(
    request: Request,
    nombre: str = Form(""),
    unidad_compra: str = Form(""),
    contenido_referencia: str = Form(""),
    grupo: str = Form(""),
):
    error, nombre = _validar_nombre(nombre)

    if not error:
        error = _validar_unidad_compra(unidad_compra)

    contenido_referencia_valor = None
    if not error:
        error, contenido_referencia_valor = _validar_cantidad_opcional(contenido_referencia, "El contenido de referencia")

    grupo_valor = None
    if not error:
        error, grupo_valor = _validar_grupo(grupo)

    if error:
        articulos = listar_articulos()
        return templates.TemplateResponse(
            request,
            "articulos.html",
            {"articulos": articulos, "error": error},
            status_code=400,
        )

    try:
        crear_articulo(nombre, unidad_compra, contenido_referencia_valor, grupo_valor)
    except Exception as error:
        articulos = listar_articulos()
        return templates.TemplateResponse(
            request,
            "articulos.html",
            {"articulos": articulos, "error": f"No se pudo guardar el artículo: {error}"},
            status_code=500,
        )

    return RedirectResponse(url="/articulos", status_code=303)


@app.get("/articulos/{articulo_id}/editar")
def ver_editar_articulo(request: Request, articulo_id: int, error: str | None = None):
    try:
        articulo = obtener_articulo(articulo_id)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    if articulo is None:
        raise HTTPException(status_code=404, detail="Artículo no encontrado")

    return templates.TemplateResponse(
        request, "articulo_editar.html", {"articulo": articulo, "error": error}
    )


@app.post("/articulos/{articulo_id}/editar")
def editar_articulo(
    request: Request,
    articulo_id: int,
    nombre: str = Form(""),
    unidad_compra: str = Form(""),
    contenido_referencia: str = Form(""),
    grupo: str = Form(""),
):
    error, nombre = _validar_nombre(nombre)

    if not error:
        error = _validar_unidad_compra(unidad_compra)

    contenido_referencia_valor = None
    if not error:
        error, contenido_referencia_valor = _validar_cantidad_opcional(contenido_referencia, "El contenido de referencia")

    grupo_valor = None
    if not error:
        error, grupo_valor = _validar_grupo(grupo)

    if error:
        return templates.TemplateResponse(
            request,
            "articulo_editar.html",
            {
                "articulo": {
                    "id": articulo_id,
                    "nombre": nombre,
                    "unidad_compra": unidad_compra,
                    "contenido_referencia": contenido_referencia,
                    "grupo": grupo,
                },
                "error": error,
            },
            status_code=400,
        )

    try:
        actualizar_articulo(articulo_id, nombre, unidad_compra, contenido_referencia_valor, grupo_valor)
    except Exception as error:
        return templates.TemplateResponse(
            request,
            "articulo_editar.html",
            {
                "articulo": {
                    "id": articulo_id,
                    "nombre": nombre,
                    "unidad_compra": unidad_compra,
                    "contenido_referencia": contenido_referencia_valor,
                    "grupo": grupo_valor,
                },
                "error": f"No se pudo guardar el artículo: {error}",
            },
            status_code=500,
        )

    return RedirectResponse(url="/articulos", status_code=303)


@app.post("/articulos/{articulo_id}/eliminar")
def eliminar_articulo(articulo_id: int):
    try:
        desactivar_articulo(articulo_id)
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"No se pudo eliminar el artículo: {error}") from error

    return RedirectResponse(url="/articulos", status_code=303)


@app.get("/clientes")
def ver_clientes(request: Request, error: str | None = None):
    try:
        clientes = listar_clientes()
    except Exception as error_db:
        return templates.TemplateResponse(
            request,
            "clientes.html",
            {"clientes": [], "error": f"No se pudo leer los clientes: {error_db}"},
            status_code=500,
        )

    return templates.TemplateResponse(request, "clientes.html", {"clientes": clientes, "error": error})


@app.get("/clientes/nuevo")
def ver_agregar_cliente(request: Request):
    return templates.TemplateResponse(
        request,
        "cliente_formulario.html",
        _contexto_formulario_cliente("alta", "", [], [], "", None),
    )


@app.post("/clientes/nuevo")
async def agregar_cliente(request: Request):
    form = await request.form()
    nombre_texto = str(form.get("nombre", ""))
    utilidad_texto = str(form.get("utilidad_objetivo", ""))
    filas_suma_crudas = _leer_filas_tasas_del_form(form, "tasa_suma")
    filas_resta_crudas = _leer_filas_tasas_del_form(form, "tasa_resta")

    error, nombre = _validar_nombre(nombre_texto)
    if not error:
        error, utilidad_valor_pct = _validar_porcentaje(utilidad_texto, "La utilidad objetivo")
    if not error:
        error, filas_suma = _validar_filas_tasas(filas_suma_crudas, "Adicionales")
    if not error:
        error, filas_resta = _validar_filas_tasas(filas_resta_crudas, "Descuentos")

    if error:
        return templates.TemplateResponse(
            request,
            "cliente_formulario.html",
            _contexto_formulario_cliente("alta", nombre_texto, filas_suma_crudas, filas_resta_crudas, utilidad_texto, error),
            status_code=400,
        )

    # En alta no hay nada previo: todas las filas completas se cargan tal
    # cual, sin pasar por el diff de edición (eso es solo para cuando ya
    # había algo guardado antes).
    tasas_suma = [{"nombre": fila["nombre"], "valor": fila["valor"]} for fila in filas_suma if fila["nombre"]]
    tasas_resta = [{"nombre": fila["nombre"], "valor": fila["valor"]} for fila in filas_resta if fila["nombre"]]

    try:
        crear_cliente(nombre, tasas_suma, tasas_resta, utilidad_valor_pct / 100)
    except Exception as error_db:
        return templates.TemplateResponse(
            request,
            "cliente_formulario.html",
            _contexto_formulario_cliente(
                "alta", nombre_texto, filas_suma_crudas, filas_resta_crudas, utilidad_texto,
                f"No se pudo guardar el cliente: {error_db}",
            ),
            status_code=500,
        )

    return RedirectResponse(url="/clientes", status_code=303)


@app.get("/clientes/{cliente_id}/editar")
def ver_editar_cliente(request: Request, cliente_id: int, error: str | None = None):
    try:
        cliente = obtener_cliente(cliente_id)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    if cliente is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    try:
        conceptos = listar_conceptos_editables_por_cliente(cliente_id)
        condiciones = obtener_condiciones_pedido(cliente_id)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    dias_esperados = condiciones["dias_esperados"] if condiciones else None
    return templates.TemplateResponse(
        request,
        "cliente_formulario.html",
        {
            "modo": "edicion",
            "cliente": cliente,
            "tasas_suma": _filas_desde_conceptos_guardados(conceptos["tasas_suma"]),
            "tasas_resta": _filas_desde_conceptos_guardados(conceptos["tasas_resta"]),
            "utilidad_pct": conceptos["utilidad_pct"],
            # Los días en que se ESPERA pedido de este cliente (alimenta la
            # alerta de faltantes). Conjunto de números 1..7, vacío = esporádico.
            "dias_pedido": _dias_esperados_como_numeros(dias_esperados),
            "error": error,
        },
    )


@app.post("/clientes/{cliente_id}/editar")
async def editar_cliente(request: Request, cliente_id: int):
    form = await request.form()
    nombre_texto = str(form.get("nombre", ""))
    utilidad_texto = str(form.get("utilidad_objetivo", ""))
    utilidad_original_texto = str(form.get("utilidad_original", "")).strip()
    filas_suma_crudas = _leer_filas_tasas_del_form(form, "tasa_suma")
    filas_resta_crudas = _leer_filas_tasas_del_form(form, "tasa_resta")

    error, nombre = _validar_nombre(nombre_texto)
    if not error:
        error, utilidad_valor_pct = _validar_porcentaje(utilidad_texto, "La utilidad objetivo")
    if not error:
        error, filas_suma = _validar_filas_tasas(filas_suma_crudas, "Adicionales")
    if not error:
        error, filas_resta = _validar_filas_tasas(filas_resta_crudas, "Descuentos")

    if error:
        return templates.TemplateResponse(
            request,
            "cliente_formulario.html",
            _contexto_formulario_cliente(
                "edicion", nombre_texto, filas_suma_crudas, filas_resta_crudas, utilidad_texto, error, cliente_id
            ),
            status_code=400,
        )

    utilidad_original = float(utilidad_original_texto) / 100 if utilidad_original_texto else None
    cambios = calcular_cambios_de_tasas("suma", filas_suma) + calcular_cambios_de_tasas("resta", filas_resta)
    cambio_utilidad = calcular_cambio_de_utilidad(utilidad_original, utilidad_valor_pct / 100)
    if cambio_utilidad:
        cambios.append(cambio_utilidad)

    try:
        actualizar_cliente(cliente_id, nombre, cambios)
    except Exception as error_db:
        return templates.TemplateResponse(
            request,
            "cliente_formulario.html",
            _contexto_formulario_cliente(
                "edicion", nombre_texto, filas_suma_crudas, filas_resta_crudas, utilidad_texto,
                f"No se pudo guardar el cliente: {error_db}", cliente_id,
            ),
            status_code=500,
        )

    return RedirectResponse(url="/clientes", status_code=303)


@app.post("/clientes/{cliente_id}/dias-pedido")
async def guardar_dias_pedido_cliente(request: Request, cliente_id: int):
    """Guarda los días de la semana en que se espera pedido del cliente (formulario propio, separado de las tasas).

    Sin ningún día tildado el cliente queda como ESPORÁDICO: la alerta de
    pedidos faltantes no le aplica.
    """
    form = await request.form()
    dias = sorted({d for d in form.getlist("dia") if d in {"1", "2", "3", "4", "5", "6", "7"}}, key=int)
    try:
        guardar_condiciones_pedido(cliente_id, ",".join(dias) or None)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"No se pudieron guardar los días de pedido: {error_db}") from error_db
    return RedirectResponse(url=f"/clientes/{cliente_id}/editar", status_code=303)


@app.post("/clientes/{cliente_id}/eliminar")
def eliminar_cliente(cliente_id: int):
    try:
        desactivar_cliente(cliente_id)
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"No se pudo eliminar el cliente: {error}") from error

    return RedirectResponse(url="/clientes", status_code=303)


@app.get("/fichas")
def ver_fichas(request: Request, cliente_id: int | None = None, error: str | None = None, aviso: str | None = None):
    try:
        clientes = listar_clientes()
    except Exception as error_db:
        return templates.TemplateResponse(
            request,
            "fichas.html",
            {"clientes": [], "cliente_id": cliente_id, "fichas": [], "error": f"No se pudo leer los clientes: {error_db}"},
            status_code=500,
        )

    fichas = []
    if cliente_id is not None:
        try:
            fichas = listar_fichas_por_cliente(cliente_id)
        except Exception as error_db:
            return templates.TemplateResponse(
                request,
                "fichas.html",
                {
                    "clientes": clientes,
                    "cliente_id": cliente_id,
                    "fichas": [],
                    "error": f"No se pudieron leer las fichas: {error_db}",
                },
                status_code=500,
            )

    return templates.TemplateResponse(
        request,
        "fichas.html",
        {
            "clientes": clientes,
            "cliente_id": cliente_id,
            "fichas": fichas,
            "error": error,
            "aviso": aviso,
            "banner": _banner_alertas("fichas"),
        },
    )


def _articulos_para_ficha(cliente_id: int) -> list[dict]:
    """Todos los artículos activos, cada uno diciendo cuántas fichas ya tiene este cliente.

    Antes esta lista escondía los artículos que ya tenían ficha, y eso era
    justo lo que impedía dar de alta "Banana Ecuador" cuando ya existía
    "Banana Bolivia". Ahora se ofrecen todos y el que ya tiene ficha se
    muestra AVISADO: con la pared abajo, lo único que evita crear dos
    fichas iguales sin querer es que se vea en la pantalla.
    """
    cuantas = contar_fichas_por_articulo(cliente_id)
    return [
        {"id": articulo["id"], "nombre": articulo["nombre"], "fichas_existentes": cuantas.get(articulo["id"], 0)}
        for articulo in listar_articulos()
    ]


@app.get("/fichas/historial")
def ver_historial_fichas(request: Request, cliente_id: int):
    """Bitácora de fichas de un cliente: cada alta, edición, borrado y cambio de artículo, de lo más nuevo a lo más viejo."""
    try:
        clientes = listar_clientes()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    cliente = next((c for c in clientes if c["id"] == cliente_id), None)
    if cliente is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    try:
        historial = listar_historial_fichas_por_cliente(cliente_id)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    return templates.TemplateResponse(
        request,
        "fichas_historial.html",
        {"cliente_id": cliente_id, "cliente_nombre": cliente["nombre"], "historial": historial},
    )


@app.get("/fichas/nueva")
def ver_nueva_ficha(request: Request, cliente_id: int, error: str | None = None):
    try:
        articulos = _articulos_para_ficha(cliente_id)
        envases = listar_envases()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    return templates.TemplateResponse(
        request,
        "ficha_form.html",
        {
            "cliente_id": cliente_id,
            "articulos": articulos,
            "envases": envases,
            "modo": "nueva",
            "ficha": None,
            "error": error,
        },
    )


@app.post("/fichas/nueva")
def agregar_ficha(
    request: Request,
    cliente_id: int = Form(...),
    articulo_id: str = Form(""),
    envase_id: str = Form(""),
    contenido_caja: str = Form(""),
    unidad_venta: str = Form(""),
    envase_variable: str = Form(""),
    nombre_cliente: str = Form(""),
    codigo_cliente: str = Form(""),
):
    error = None
    articulo_id_valor = None
    articulo_id = articulo_id.strip()
    if not articulo_id:
        error = "Elegí un artículo."
    else:
        try:
            articulo_id_valor = int(articulo_id)
        except ValueError:
            error = "El artículo elegido no es válido."

    if not error:
        error = _validar_unidad_venta(unidad_venta)

    envase_id_valor = None
    if not error:
        error, envase_id_valor = _validar_envase(envase_id)

    contenido_caja_valor = None
    if not error:
        error, contenido_caja_valor = _validar_contenido_caja(contenido_caja)

    nombre_cliente_valor = nombre_cliente.strip() or None
    codigo_cliente_valor = codigo_cliente.strip() or None

    if error:
        articulos = _articulos_para_ficha(cliente_id)
        envases = listar_envases()
        return templates.TemplateResponse(
            request,
            "ficha_form.html",
            {
                "cliente_id": cliente_id,
                "articulos": articulos,
                "envases": envases,
                "modo": "nueva",
                "ficha": None,
                "error": error,
            },
            status_code=400,
        )

    try:
        crear_ficha(
            articulo_id_valor,
            cliente_id,
            envase_id_valor,
            contenido_caja_valor,
            unidad_venta,
            _envase_variable_desde_form(envase_variable),
            nombre_cliente_valor,
            codigo_cliente_valor,
        )
    except Exception as error_db:
        articulos = _articulos_para_ficha(cliente_id)
        envases = listar_envases()
        return templates.TemplateResponse(
            request,
            "ficha_form.html",
            {
                "cliente_id": cliente_id,
                "articulos": articulos,
                "envases": envases,
                "modo": "nueva",
                "ficha": None,
                "error": f"No se pudo guardar la ficha: {error_db}",
            },
            status_code=500,
        )

    return RedirectResponse(url=f"/fichas?cliente_id={cliente_id}", status_code=303)


@app.get("/fichas/{ficha_id}/editar")
def ver_editar_ficha(request: Request, ficha_id: int, error: str | None = None):
    try:
        ficha = obtener_ficha(ficha_id)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    if ficha is None:
        raise HTTPException(status_code=404, detail="Ficha no encontrada")

    try:
        envases = listar_envases()
        # Para "Cambiar artículo": TODOS los artículos activos. Antes se
        # escondían los que ya tenían ficha "para no pisar una existente",
        # pero desde que un cliente puede tener varias fichas del mismo
        # artículo eso ya no pisa nada — y los que ya tienen ficha van
        # avisados en la propia lista.
        articulos_para_cambio = _articulos_para_ficha(ficha["cliente_id"])
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    return templates.TemplateResponse(
        request,
        "ficha_form.html",
        {
            "cliente_id": ficha["cliente_id"],
            "articulos": [],
            "articulos_para_cambio": articulos_para_cambio,
            "envases": envases,
            "modo": "editar",
            "ficha": ficha,
            "error": error,
        },
    )


@app.post("/fichas/{ficha_id}/editar")
def editar_ficha(
    request: Request,
    ficha_id: int,
    cliente_id: int = Form(...),
    articulo_nombre: str = Form(""),
    envase_id: str = Form(""),
    contenido_caja: str = Form(""),
    unidad_venta: str = Form(""),
    envase_variable: str = Form(""),
    nombre_cliente: str = Form(""),
    codigo_cliente: str = Form(""),
):
    error = _validar_unidad_venta(unidad_venta)

    envase_id_valor = None
    if not error:
        error, envase_id_valor = _validar_envase(envase_id)

    contenido_caja_valor = None
    if not error:
        error, contenido_caja_valor = _validar_contenido_caja(contenido_caja)

    envase_variable_valor = _envase_variable_desde_form(envase_variable)
    nombre_cliente_valor = nombre_cliente.strip() or None
    codigo_cliente_valor = codigo_cliente.strip() or None

    if error:
        envases = listar_envases()
        ficha = {
            "id": ficha_id,
            "cliente_id": cliente_id,
            "articulo_nombre": articulo_nombre,
            "envase_id": envase_id,
            "contenido_caja": contenido_caja,
            "unidad_venta": unidad_venta,
            "envase_variable": envase_variable_valor,
            "nombre_cliente": nombre_cliente,
            "codigo_cliente": codigo_cliente,
        }
        return templates.TemplateResponse(
            request,
            "ficha_form.html",
            {"cliente_id": cliente_id, "articulos": [], "envases": envases, "modo": "editar", "ficha": ficha, "error": error},
            status_code=400,
        )

    try:
        actualizar_ficha(
            ficha_id,
            envase_id_valor,
            contenido_caja_valor,
            unidad_venta,
            envase_variable_valor,
            nombre_cliente_valor,
            codigo_cliente_valor,
        )
    except Exception as error_db:
        envases = listar_envases()
        ficha = {
            "id": ficha_id,
            "cliente_id": cliente_id,
            "articulo_nombre": articulo_nombre,
            "envase_id": envase_id_valor,
            "contenido_caja": contenido_caja_valor,
            "unidad_venta": unidad_venta,
            "envase_variable": envase_variable_valor,
            "nombre_cliente": nombre_cliente_valor,
            "codigo_cliente": codigo_cliente_valor,
        }
        return templates.TemplateResponse(
            request,
            "ficha_form.html",
            {
                "cliente_id": cliente_id,
                "articulos": [],
                "envases": envases,
                "modo": "editar",
                "ficha": ficha,
                "error": f"No se pudo guardar la ficha: {error_db}",
            },
            status_code=500,
        )

    return RedirectResponse(url=f"/fichas?cliente_id={cliente_id}", status_code=303)


@app.post("/fichas/{ficha_id}/eliminar")
def eliminar_ficha_ruta(ficha_id: int, cliente_id: int = Form(...)):
    """Borra una ficha. Si tiene guías R cargadas, se niega y lo dice con el número.

    Una ficha con guías R no se borra: el reproceso guarda a qué ficha
    fueron sus cajas, y borrarla dejaría ese dato en la nada. Es dato mal
    pedido, no una falla del sistema — se muestra en la pantalla, nunca
    como un 500.
    """
    try:
        eliminar_ficha(ficha_id)
    except ValueError as error:
        parametros = urlencode({"cliente_id": cliente_id, "error": str(error)})
        return RedirectResponse(url=f"/fichas?{parametros}", status_code=303)
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"No se pudo eliminar la ficha: {error}") from error

    return RedirectResponse(url=f"/fichas?cliente_id={cliente_id}", status_code=303)


@app.post("/fichas/{ficha_id}/cambiar-articulo")
def cambiar_articulo_de_ficha_ruta(
    ficha_id: int,
    cliente_id: int = Form(...),
    articulo_nuevo_id: str = Form(""),
    nombre_cliente: str = Form(""),
    codigo_cliente: str = Form(""),
):
    """Cambia el artículo de una ficha conservando envase, contenido y unidad (borrado + alta en una transacción).

    El alias del cliente viene del form: la pantalla lo precarga con el de
    la ficha vieja (el caso normal es el mismo producto en otra
    presentación) pero se puede editar antes de confirmar, porque si el
    destino es otro producto el alias viejo quedaría mal.

    Los precios ya negociados no cambian: quedan cargados por artículo en
    precios_venta_historial. De acá en adelante se cotiza contra el
    artículo nuevo. La pantalla solo ofrece artículos sin ficha del
    cliente; si igual llega uno repetido (carrera entre dos pestañas), el
    unique de la tabla corta todo y no se pierde nada.
    """
    try:
        articulo_nuevo = int(articulo_nuevo_id)
    except ValueError:
        return RedirectResponse(
            url=f"/fichas/{ficha_id}/editar?{urlencode({'error': 'Elegí el artículo nuevo.'})}", status_code=303
        )

    try:
        ficha_nueva_id = cambiar_articulo_de_ficha(
            ficha_id, articulo_nuevo, nombre_cliente.strip() or None, codigo_cliente.strip() or None
        )
    except Exception as error_db:
        return RedirectResponse(
            url=f"/fichas/{ficha_id}/editar?{urlencode({'error': f'No se pudo cambiar el artículo: {error_db}'})}",
            status_code=303,
        )

    if ficha_nueva_id is None:
        raise HTTPException(status_code=404, detail="Ficha no encontrada")

    return RedirectResponse(
        url=f"/fichas?{urlencode({'cliente_id': cliente_id, 'aviso': 'Listo: la ficha ahora apunta al artículo nuevo. El cambio quedó en el historial.'})}",
        status_code=303,
    )



def _validar_compra_nueva_form(
    articulo_id: str, cantidad_cajones: str, contenido_por_cajon: str, importe: str, sena: str, tipo_retiro: str
) -> tuple[str | None, dict]:
    """Valida los campos del alta de una compra (cajones × contenido por cajón).

    Devuelve (error, valores) con articulo_id, cantidad_cajones, contenido_por_cajon, importe, sena
    y tipo_retiro ya convertidos (o None/placeholder si hubo error antes de llegar a ese campo). No
    valida acá si el artículo tiene unidad_compra configurada: eso requiere leerlo de la base, y lo
    hace la ruta después de esta validación.
    """
    error = None
    valores = {
        "articulo_id": None,
        "cantidad_cajones": None,
        "contenido_por_cajon": None,
        "importe": None,
        "sena": None,
        "tipo_retiro": tipo_retiro,
    }

    articulo_id = articulo_id.strip()
    if not articulo_id:
        error = "Elegí un artículo."
    else:
        try:
            valores["articulo_id"] = int(articulo_id)
        except ValueError:
            error = "El artículo elegido no es válido."

    if not error:
        error, valores["cantidad_cajones"] = _validar_cantidad_cajones(cantidad_cajones)

    if not error:
        error, valores["contenido_por_cajon"] = _validar_contenido_por_cajon(contenido_por_cajon)

    if not error:
        error, valores["importe"] = _validar_importe(importe)

    if not error:
        error, valores["sena"] = _validar_sena(sena)

    if not error:
        error = _validar_tipo_retiro(tipo_retiro)

    return error, valores


@app.get("/compras")
def ver_compras(request: Request, aviso: str | None = None):
    """Botonera de entrada al módulo de compras.

    aviso viene por la URL cuando otra pantalla redirige acá con algo
    para contar (hoy: Cancelar en la carga manual, con cuántas compras se
    cancelaron y cuántas no se pudieron).

    Arriba de los botones corre el banner con las alertas que le tocan a
    Compras. NO las calcula: las lee de la foto del registro (ver
    app/alertas.py). Antes esta pantalla corría sus dos consultas propias,
    duplicadas con las de Auditoría y ya desincronizadas entre sí.
    """
    return templates.TemplateResponse(
        request, "compras.html", {"banner": _banner_alertas("compras"), "aviso": aviso}
    )


def _renderizar_en_construccion(
    request: Request,
    titulo: str,
    volver_url: str = "/compras",
    volver_texto: str = "Volver a compras",
    sector: str = "compras",
):
    """Pantalla placeholder compartida por todos los botones "Próximamente" (de la botonera de Compras y de la home)."""
    return templates.TemplateResponse(
        request,
        "en_construccion.html",
        {"titulo": titulo, "volver_url": volver_url, "volver_texto": volver_texto, "sector": sector},
    )


@app.get("/compras/nueva/listado")
def ver_cargar_listado_compras(request: Request):
    try:
        proveedores = listar_proveedores()
    except Exception:
        proveedores = []
    return templates.TemplateResponse(request, "compra_listado.html", {"proveedores": proveedores})


def _renderizar_pantalla_buscar_compras(
    request: Request,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
    proveedor_id: str | None = None,
    articulo_id: str | None = None,
    aviso: str | None = None,
    status_code: int = 200,
):
    """Búsqueda de compras por rango de fechas, con proveedor y artículo opcionales.

    Sin fechas en la URL, arranca mostrando las últimas 48hs (mismo rango
    que tenía /compras/ultimas, ya eliminada) — el usuario puede ampliarlo
    desde acá. Mismo criterio de fecha inválida que /precios/consultar: se
    cae a un valor por defecto y se muestra el error, sin bloquear la
    pantalla.

    Reutilizada por la ruta GET y por el borrado múltiple (POST
    /compras/eliminar-varias), que renderiza esta misma pantalla con un
    aviso de qué se borró y qué no, conservando los filtros activos.
    """
    proveedor_id_valor = _id_opcional_desde_query(proveedor_id)
    articulo_id_valor = _id_opcional_desde_query(articulo_id)

    hoy = _hoy_argentina()
    fecha_desde_valor = hoy - timedelta(days=1)
    fecha_hasta_valor = hoy
    error_fecha = None

    if fecha_desde:
        try:
            fecha_desde_valor = date.fromisoformat(fecha_desde)
        except ValueError:
            error_fecha = "La fecha desde no es válida."
    if fecha_hasta:
        try:
            fecha_hasta_valor = date.fromisoformat(fecha_hasta)
        except ValueError:
            error_fecha = "La fecha hasta no es válida."
    if error_fecha is None and fecha_desde_valor > fecha_hasta_valor:
        error_fecha = "La fecha desde no puede ser posterior a la fecha hasta."

    try:
        # La lista COMPLETA, de baja incluidos: esto es un filtro de
        # búsqueda, no un selector de carga. Las compras de un proveedor
        # dado de baja siguen existiendo y hay que poder buscarlas por él
        # — y si no estuviera en la lista, proveedor_nombre_actual (abajo)
        # daría None y la pantalla mostraría el filtro vacío mientras
        # filtra igual.
        proveedores = listar_todos_los_proveedores()
        articulos = listar_articulos()
        # Tope para la pantalla: un rango ancho no puede tirar miles de
        # filas al celular. Se pide una de más para saber si hubo corte;
        # el total real (para el aviso) se cuenta solo en ese caso.
        compras = buscar_compras(
            fecha_desde_valor, fecha_hasta_valor, proveedor_id_valor, articulo_id_valor,
            limite=TOPE_FILAS_BUSQUEDA + 1,
        )
        aviso_tope = None
        if len(compras) > TOPE_FILAS_BUSQUEDA:
            total = contar_compras_buscadas(
                fecha_desde_valor, fecha_hasta_valor, proveedor_id_valor, articulo_id_valor
            )
            compras = compras[:TOPE_FILAS_BUSQUEDA]
            aviso_tope = (
                f"Se muestran las primeras {TOPE_FILAS_BUSQUEDA} compras de {total}: "
                "achicá el rango de fechas o filtrá por proveedor o artículo para ver el resto."
            )
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    proveedor_nombre_actual = (
        next((p["nombre"] for p in proveedores if p["id"] == proveedor_id_valor), None)
        if proveedor_id_valor is not None
        else None
    )
    articulo_nombre_actual = (
        next((a["nombre"] for a in articulos if a["id"] == articulo_id_valor), None)
        if articulo_id_valor is not None
        else None
    )

    return templates.TemplateResponse(
        request,
        "compras_buscar.html",
        {
            "proveedores": proveedores,
            "articulos": articulos,
            "fecha_desde": fecha_desde_valor.isoformat(),
            "fecha_hasta": fecha_hasta_valor.isoformat(),
            "proveedor_id": proveedor_id_valor,
            "proveedor_nombre_actual": proveedor_nombre_actual,
            "articulo_id": articulo_id_valor,
            "articulo_nombre_actual": articulo_nombre_actual,
            "error_fecha": error_fecha,
            "compras": compras,
            "aviso": aviso,
            "aviso_tope": aviso_tope,
        },
        status_code=status_code,
    )


@app.get("/compras/buscar")
def ver_buscar_compras(
    request: Request,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
    proveedor_id: str | None = None,
    articulo_id: str | None = None,
    aviso: str | None = None,
):
    return _renderizar_pantalla_buscar_compras(
        request, fecha_desde, fecha_hasta, proveedor_id, articulo_id, aviso=aviso
    )


def _nombre_archivo_exportacion_compras(fecha_desde: date, fecha_hasta: date, extension: str) -> str:
    return f"Listado_Compras_{fecha_desde.isoformat()}_a_{fecha_hasta.isoformat()}.{extension}"


def _leer_filtros_buscar_compras(
    fecha_desde_texto: str, fecha_hasta_texto: str, proveedor_id_texto: str, articulo_id_texto: str
) -> tuple[date, date, int | None, int | None]:
    """Valida los filtros para las rutas de exportación de compras. El link solo lo arma la propia
    pantalla con valores ya válidos, así que un error acá es un caso de URL manipulada a mano — alcanza
    con HTTPException (mismo criterio que el resto de las rutas de confirmación de esta app).
    """
    try:
        fecha_desde = date.fromisoformat(fecha_desde_texto)
        fecha_hasta = date.fromisoformat(fecha_hasta_texto)
    except ValueError:
        raise HTTPException(status_code=400, detail="Fecha inválida")
    proveedor_id = _id_opcional_desde_query(proveedor_id_texto)
    articulo_id = _id_opcional_desde_query(articulo_id_texto)
    return fecha_desde, fecha_hasta, proveedor_id, articulo_id


@app.get("/compras/buscar/exportar-pdf")
def exportar_listado_compras_pdf(fecha_desde: str = "", fecha_hasta: str = "", proveedor_id: str = "", articulo_id: str = ""):
    """Genera el Listado de Compras (con los mismos filtros de la búsqueda) en PDF — no se guarda en ningún lado."""
    fecha_desde_valor, fecha_hasta_valor, proveedor_id_valor, articulo_id_valor = _leer_filtros_buscar_compras(
        fecha_desde, fecha_hasta, proveedor_id, articulo_id
    )

    try:
        compras = buscar_compras(fecha_desde_valor, fecha_hasta_valor, proveedor_id_valor, articulo_id_valor)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    pdf_bytes = generar_pdf_listado_compras(fecha_desde_valor, fecha_hasta_valor, compras)
    nombre_archivo = _nombre_archivo_exportacion_compras(fecha_desde_valor, fecha_hasta_valor, "pdf")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'},
    )


@app.get("/compras/buscar/exportar-excel")
def exportar_listado_compras_excel(fecha_desde: str = "", fecha_hasta: str = "", proveedor_id: str = "", articulo_id: str = ""):
    """Genera el Listado de Compras (con los mismos filtros de la búsqueda) en Excel — no se guarda en ningún lado."""
    fecha_desde_valor, fecha_hasta_valor, proveedor_id_valor, articulo_id_valor = _leer_filtros_buscar_compras(
        fecha_desde, fecha_hasta, proveedor_id, articulo_id
    )

    try:
        compras = buscar_compras(fecha_desde_valor, fecha_hasta_valor, proveedor_id_valor, articulo_id_valor)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    excel_bytes = generar_excel_listado_compras(fecha_desde_valor, fecha_hasta_valor, compras)
    nombre_archivo = _nombre_archivo_exportacion_compras(fecha_desde_valor, fecha_hasta_valor, "xlsx")

    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'},
    )


@app.get("/compras/armar-listado")
def ver_armar_listado_compras(request: Request):
    return _renderizar_en_construccion(request, "Armar listado de compras")


def _orden_grupo_disponible(grupo: str | None) -> int:
    """Posición del grupo en la precarga desde fichas_logistica (fruta, hortaliza, hoja, pesada, el resto al final)."""
    try:
        return ORDEN_GRUPOS_DISPONIBLES.index(grupo)
    except ValueError:
        return len(ORDEN_GRUPOS_DISPONIBLES)


def _renglones_iniciales_desde_fichas(fichas: list[dict]) -> list[dict]:
    """Primera vez que se arma un Disponible para un cliente (nunca tuvo uno): un renglón por cada
    ficha que ya tenga codigo_cliente o nombre_cliente cargado (las que no, se agregan a mano cuando
    hagan falta, desde "Agregar desde el catálogo"), en orden fruta/hortaliza/hoja/pesada/sin clasificar,
    cantidad en 0 (no hay nada previo que sugerir)."""
    fichas_con_alias = [f for f in fichas if f.get("codigo_cliente") or f.get("nombre_cliente")]
    fichas_ordenadas = sorted(fichas_con_alias, key=lambda f: (_orden_grupo_disponible(f.get("articulo_grupo")), f["articulo_nombre"]))
    return [
        {
            "articulo_id": ficha["articulo_id"],
            "codigo": ficha.get("codigo_cliente"),
            "nombre": ficha.get("nombre_cliente") or ficha["articulo_nombre"],
            "cantidad": 0,
        }
        for ficha in fichas_ordenadas
    ]


def _nombre_archivo_disponibles(fecha_desde: date, version: int) -> str:
    mes = MESES_ABREVIADOS[fecha_desde.month]
    base = f"Disponibles_{_nombre_empresa_para_archivo()}_{fecha_desde.day}_{mes}_{fecha_desde.year}"
    if version > 1:
        base += f"_v{version}"
    return f"{base}.xlsx"


def _validar_rango_fechas_disponible(fecha_desde_texto: str, fecha_hasta_texto: str) -> tuple[str | None, date | None, date | None]:
    try:
        fecha_desde = date.fromisoformat(fecha_desde_texto)
        fecha_hasta = date.fromisoformat(fecha_hasta_texto)
    except ValueError:
        return "Fecha inválida.", None, None
    if fecha_hasta < fecha_desde:
        return "La fecha hasta no puede ser anterior a la fecha desde.", None, None
    return None, fecha_desde, fecha_hasta


def _leer_renglones_disponible_del_form(form) -> list[dict]:
    """Lee del form oculto (armado por JS con los renglones en pantalla, ya en el orden final) los
    datos crudos de cada renglón — indexados 0, 1, 2... en vez de por articulo_id, porque un renglón
    tipeado a mano no tiene uno."""
    renglones = []
    indice = 0
    while f"renglon_nombre_{indice}" in form:
        articulo_id_texto = str(form.get(f"renglon_articulo_id_{indice}", "")).strip()
        renglones.append(
            {
                "articulo_id_texto": articulo_id_texto,
                "codigo_texto": str(form.get(f"renglon_codigo_{indice}", "")).strip(),
                "nombre_texto": str(form.get(f"renglon_nombre_{indice}", "")).strip(),
                "cantidad_texto": str(form.get(f"renglon_cantidad_{indice}", "")).strip(),
            }
        )
        indice += 1
    return renglones


def _validar_renglones_disponible(renglones_crudos: list[dict]) -> tuple[str | None, list[dict]]:
    if not renglones_crudos:
        return "Agregá al menos un artículo.", []

    renglones = []
    for renglon in renglones_crudos:
        if not renglon["nombre_texto"]:
            return "Todos los renglones necesitan un producto.", []
        try:
            cantidad = float(renglon["cantidad_texto"])
        except ValueError:
            return f"La cantidad de \"{renglon['nombre_texto']}\" tiene que ser un número.", []
        if cantidad < 0:
            return f"La cantidad de \"{renglon['nombre_texto']}\" no puede ser negativa.", []

        articulo_id = int(renglon["articulo_id_texto"]) if renglon["articulo_id_texto"] else None
        renglones.append(
            {
                "articulo_id": articulo_id,
                "codigo": renglon["codigo_texto"] or None,
                "nombre": renglon["nombre_texto"],
                "cantidad": cantidad,
            }
        )
    return None, renglones


async def _guardar_pendientes_disponible(request: Request) -> tuple[dict, int, list[dict], date, date]:
    """Valida y guarda (upsert) el Disponible del form de disponibles.html. Lo comparten "Guardar" y
    "Guardar y generar Excel", que hacen lo mismo acá y después responden distinto."""
    form = await request.form()

    try:
        cliente_id = int(form.get("cliente_id", ""))
    except ValueError:
        raise HTTPException(status_code=400, detail="Cliente inválido")

    try:
        clientes = listar_clientes()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    cliente = next((c for c in clientes if c["id"] == cliente_id), None)
    if cliente is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    disponible_id_texto = str(form.get("disponible_id", "")).strip()
    disponible_id = int(disponible_id_texto) if disponible_id_texto else None

    error_fecha, fecha_desde, fecha_hasta = _validar_rango_fechas_disponible(
        str(form.get("fecha_desde", "")), str(form.get("fecha_hasta", ""))
    )
    if error_fecha:
        raise HTTPException(status_code=400, detail=error_fecha)

    renglones_crudos = _leer_renglones_disponible_del_form(form)
    error_renglones, renglones = _validar_renglones_disponible(renglones_crudos)
    if error_renglones:
        raise HTTPException(status_code=400, detail=error_renglones)

    try:
        disponible_id = guardar_disponible(disponible_id, cliente_id, fecha_desde, fecha_hasta, renglones)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"No se pudo guardar el Disponible: {error_db}") from error_db

    return cliente, disponible_id, renglones, fecha_desde, fecha_hasta


@app.get("/compras/disponibles")
def ver_disponibles(request: Request, cliente_id: str | None = None, guardado: str | None = None, generado: str | None = None):
    """Planilla de mercadería disponible que se manda por mail a un cliente. Cada cliente tiene su
    propio Disponible: sin cliente_id en la URL, se muestra solo el selector (mismo patrón que
    /fichas, /negociar y /precios/cargar).

    Precarga, en este orden: (1) el borrador abierto del cliente, si tiene uno — se sigue editando
    in place; (2) si no, el último Disponible de ese cliente (cualquier estado), para arrancar uno
    nuevo con esos mismos artículos y cantidades; (3) si el cliente nunca tuvo uno, sus fichas de
    logística, cantidad en 0.
    """
    cliente_id_valor = _id_opcional_desde_query(cliente_id)

    try:
        clientes = listar_clientes()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    if cliente_id_valor is None:
        return templates.TemplateResponse(request, "disponibles.html", {"clientes": clientes, "cliente_id": None})

    cliente = next((c for c in clientes if c["id"] == cliente_id_valor), None)
    if cliente is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    try:
        fichas = listar_fichas_por_cliente(cliente_id_valor)
        borrador = obtener_borrador_disponible(cliente_id_valor)
        if borrador is not None:
            disponible_id = borrador["id"]
            fecha_desde = borrador["fecha_desde"]
            fecha_hasta = borrador["fecha_hasta"]
            renglones = listar_detalle_disponible(disponible_id)
        else:
            disponible_id = None
            fecha_desde = fecha_hasta = _hoy_argentina()
            ultimo = obtener_ultimo_disponible_cliente(cliente_id_valor)
            renglones = listar_detalle_disponible(ultimo["id"]) if ultimo is not None else _renglones_iniciales_desde_fichas(fichas)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    mensaje = None
    if guardado:
        mensaje = "Se guardó el borrador."
    elif generado:
        mensaje = "Se guardó y se generó el Excel."

    renglones_json = json.dumps(
        [
            {"articuloId": r["articulo_id"], "codigo": r["codigo"], "nombre": r["nombre"], "cantidad": float(r["cantidad"])}
            for r in renglones
        ]
    )
    catalogo_json = json.dumps(
        [
            {
                "articuloId": f["articulo_id"],
                "codigo": f.get("codigo_cliente"),
                "nombre": f.get("nombre_cliente") or f["articulo_nombre"],
            }
            for f in fichas
        ]
    )

    return templates.TemplateResponse(
        request,
        "disponibles.html",
        {
            "clientes": clientes,
            "cliente_id": cliente_id_valor,
            "cliente_nombre": cliente["nombre"],
            "disponible_id": disponible_id,
            "fecha_desde": fecha_desde.isoformat(),
            "fecha_hasta": fecha_hasta.isoformat(),
            "renglones_json": renglones_json,
            "catalogo_json": catalogo_json,
            "mensaje": mensaje,
        },
    )


@app.post("/compras/disponibles/guardar")
async def guardar_disponible_ruta(request: Request):
    cliente, _disponible_id, _renglones, _fecha_desde, _fecha_hasta = await _guardar_pendientes_disponible(request)
    return RedirectResponse(url=f"/compras/disponibles?cliente_id={cliente['id']}&guardado=1", status_code=303)


@app.post("/compras/disponibles/guardar-y-exportar-excel")
async def guardar_y_exportar_disponible_excel(request: Request):
    """Guarda el Disponible, lo cierra en 'generado' (queda fijo, como historial) y devuelve el Excel."""
    cliente, disponible_id, renglones, fecha_desde, fecha_hasta = await _guardar_pendientes_disponible(request)

    try:
        version = cerrar_disponible_generado(disponible_id, cliente["id"], fecha_desde)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"No se pudo generar el Excel: {error_db}") from error_db

    excel_bytes = generar_excel_disponibles(fecha_desde, fecha_hasta, renglones, NOMBRE_EMPRESA)
    nombre_archivo = _nombre_archivo_disponibles(fecha_desde, version)

    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'},
    )


def _renderizar_compra_manual(
    request: Request,
    *,
    error: str | None = None,
    codigo_puesto: str = "",
    nombre: str = "",
    compra: dict | None = None,
    status_code: int = 200,
):
    """La pantalla ÚNICA de carga manual: proveedor y artículo juntos, como en la carga de comandas.

    En error se repuebla todo lo tipeado (proveedor y renglón): en el
    Mercado nadie quiere volver a escribir una compra entera por un campo
    mal cargado.
    """
    try:
        proveedores = listar_proveedores()
        articulos = listar_articulos()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    return templates.TemplateResponse(
        request,
        "compra_manual.html",
        {
            "proveedores": proveedores,
            "articulos": articulos,
            "codigo_puesto_sugerido": codigo_puesto,
            "nombre_sugerido": nombre,
            "compra": compra,
            "error": error,
        },
        status_code=status_code,
    )


@app.get("/compras/nueva/manual")
def ver_nueva_compra_manual(request: Request, error: str | None = None):
    return _renderizar_compra_manual(request, error=error)


@app.get("/compras/nueva/foto-una")
def ver_nueva_compra_foto(request: Request, error: str | None = None):
    return templates.TemplateResponse(request, "compra_leer_foto.html", {"error": error})


@app.get("/compras/nueva")
def ver_nueva_compra(
    request: Request, proveedor_id: int | None = None, error: str | None = None, aviso: str | None = None
):
    """aviso viene por la URL cuando hay algo que contar del guardado anterior (hoy: un proveedor que se reactivó)."""
    if proveedor_id is None:
        try:
            proveedores = listar_proveedores()
        except Exception as error_db:
            raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

        return templates.TemplateResponse(
            request,
            "compra_proveedor_form.html",
            {"proveedores": proveedores, "error": error},
        )

    try:
        proveedor = obtener_proveedor(proveedor_id)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    if proveedor is None:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")

    try:
        articulos = listar_articulos()
        renglones_hoy = listar_compras_por_fecha_y_proveedor(_hoy_argentina(), proveedor_id)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    return templates.TemplateResponse(
        request,
        "compra_form.html",
        {
            "articulos": articulos,
            "modo": "nueva",
            "compra": None,
            "proveedor": proveedor,
            "renglones_hoy": renglones_hoy,
            "error": error,
            "aviso": aviso,
        },
    )


AVISO_READJUNTAR_COMANDA = " Ojo: la comanda adjunta se descartó con el error — volvé a adjuntarla antes de guardar."


def _subir_comanda_adjunta(comprimida: bytes, nombre_base: str) -> str | None:
    """Sube la comanda adjuntada a mano (ya comprimida). None si Storage falló: la foto es un extra, nunca bloquea la compra."""
    try:
        return subir_foto_comanda(comprimida, nombre_base)
    except Exception:
        logger.exception("No se pudo subir la comanda adjunta (%s) — la compra se guarda igual, sin foto", nombre_base)
        return None


@app.post("/compras/nueva/manual")
async def agregar_compra_manual(
    request: Request,
    codigo_puesto: str = Form(""),
    nombre: str = Form(""),
    accion: str = Form("agregar"),
    articulo_id: str = Form(""),
    cantidad_cajones: str = Form(""),
    contenido_por_cajon: str = Form(""),
    importe: str = Form(""),
    sena: str = Form(""),
    tipo_retiro: str = Form(""),
    comanda_foto: UploadFile | None = File(None),
):
    """Guarda proveedor Y primer artículo en UN solo paso (la pantalla combinada de carga manual).

    Mismas validaciones que el alta por proveedor confirmado. Después del
    primer renglón se sigue en /compras/nueva con el proveedor ya fijado
    (lista de lo cargado hoy, agregar/terminar/cancelar como siempre) —
    el paso que se eliminó es el de "confirmar proveedor" solo.

    comanda_foto (opcional): la foto de la comanda ADJUNTA, sin analizar —
    se comprime con el pipeline de siempre y cuelga de la guía del
    proveedor del día, como las fotos de las comandas leídas.
    """
    bytes_foto = await comanda_foto.read() if comanda_foto is not None else b""

    renglon_vacio = not any(
        campo.strip() for campo in (articulo_id, cantidad_cajones, contenido_por_cajon, importe, sena, tipo_retiro)
    )
    if accion == "terminar" and renglon_vacio:
        return RedirectResponse(url="/compras/buscar", status_code=303)

    def _reintentar(error, status_code):
        # El navegador no permite repoblar un input de archivo: si venía una
        # comanda adjunta, el error tiene que avisar que hay que re-adjuntarla.
        if bytes_foto:
            error += AVISO_READJUNTAR_COMANDA
        compra = {
            "articulo_id": valores["articulo_id"] if valores else None,
            "cantidad_cajones": cantidad_cajones,
            "contenido_por_cajon": contenido_por_cajon,
            "importe": importe,
            "sena": sena,
            "tipo_retiro": tipo_retiro,
        }
        return _renderizar_compra_manual(
            request, error=error, codigo_puesto=codigo_puesto, nombre=nombre, compra=compra, status_code=status_code
        )

    valores = None
    error, codigo_valor = _validar_codigo_puesto(codigo_puesto)
    nombre_valor = nombre
    if not error:
        error, nombre_valor = _validar_nombre(nombre)
    if not error:
        error, valores = _validar_compra_nueva_form(
            articulo_id, cantidad_cajones, contenido_por_cajon, importe, sena, tipo_retiro
        )

    comprimida = None
    if not error and bytes_foto:
        comprimida = _comprimir_foto_jpeg(bytes_foto)
        if comprimida is None:
            error = "La comanda adjunta no es una imagen legible. Sacá la foto de nuevo o quitala."

    articulo = None
    if not error:
        try:
            articulo = obtener_articulo(valores["articulo_id"])
        except Exception as error_db:
            return _reintentar(f"No se pudo leer el artículo: {error_db}", 500)
        if articulo is None:
            error = "El artículo elegido no es válido."
        elif not articulo["unidad_compra"]:
            error = "Este artículo no tiene la unidad de compra configurada. Cargala en /articulos primero."

    if error:
        return _reintentar(error, 400)

    # El proveedor se crea/resuelve recién con el renglón ya validado: un
    # error de tipeo en la compra no deja proveedores nuevos colgados.
    try:
        proveedor_id, reactivado = obtener_o_crear_proveedor_por_codigo(codigo_valor, nombre_valor)
    except Exception as error_db:
        return _reintentar(f"No se pudo guardar el proveedor: {error_db}", 500)
    aviso_reactivado = _aviso_proveedor_reactivado(reactivado, nombre_valor)

    foto_ruta = _subir_comanda_adjunta(comprimida, codigo_valor) if comprimida is not None else None

    total = valores["cantidad_cajones"] * valores["contenido_por_cajon"]
    if articulo["unidad_compra"] == "kilo":
        cantidad_kilos, cantidad_fraccion = total, None
    else:
        cantidad_kilos, cantidad_fraccion = None, total

    try:
        crear_compra(
            _hoy_argentina(),
            valores["articulo_id"],
            proveedor_id,
            valores["cantidad_cajones"],
            valores["contenido_por_cajon"],
            cantidad_kilos,
            cantidad_fraccion,
            valores["importe"],
            valores["sena"],
            valores["tipo_retiro"],
            foto_ruta,
        )
    except Exception as error_db:
        return _reintentar(f"No se pudo guardar la compra: {error_db}", 500)

    if accion == "terminar":
        return RedirectResponse(url="/compras/buscar", status_code=303)

    return RedirectResponse(url=_url_nueva_compra(proveedor_id, aviso_reactivado), status_code=303)


@app.post("/compras/nueva")
async def agregar_compra(
    request: Request,
    proveedor_id: int = Form(...),
    accion: str = Form("agregar"),
    articulo_id: str = Form(""),
    cantidad_cajones: str = Form(""),
    contenido_por_cajon: str = Form(""),
    importe: str = Form(""),
    sena: str = Form(""),
    tipo_retiro: str = Form(""),
    comanda_foto: UploadFile | None = File(None),
):
    bytes_foto = await comanda_foto.read() if comanda_foto is not None else b""

    renglon_vacio = not any(
        campo.strip() for campo in (articulo_id, cantidad_cajones, contenido_por_cajon, importe, sena, tipo_retiro)
    )
    if accion == "terminar" and renglon_vacio and not bytes_foto:
        return RedirectResponse(url="/compras/buscar", status_code=303)

    try:
        proveedor = obtener_proveedor(proveedor_id)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    if proveedor is None:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")

    def _reintentar_con_foto_error(error, status_code):
        articulos = listar_articulos()
        renglones_hoy = listar_compras_por_fecha_y_proveedor(_hoy_argentina(), proveedor_id)
        return templates.TemplateResponse(
            request,
            "compra_form.html",
            {
                "articulos": articulos,
                "modo": "nueva",
                "compra": None,
                "proveedor": proveedor,
                "renglones_hoy": renglones_hoy,
                "error": error,
            },
            status_code=status_code,
        )

    comprimida = None
    if bytes_foto:
        comprimida = _comprimir_foto_jpeg(bytes_foto)
        if comprimida is None:
            return _reintentar_con_foto_error(
                "La comanda adjunta no es una imagen legible. Sacá la foto de nuevo o quitala.", 400
            )

    # Terminar SOLO con la comanda adjunta (sin renglón nuevo): la foto se
    # cuelga de la guía del día ya creada por los renglones anteriores —
    # es el "cerrar la comanda" al final de la carga.
    if accion == "terminar" and renglon_vacio:
        try:
            foto_ruta = subir_foto_comanda(comprimida, proveedor["codigo_puesto"])
            con_guia = agregar_foto_guia_del_dia(_hoy_argentina(), proveedor_id, foto_ruta)
        except Exception as error_subida:
            return _reintentar_con_foto_error(f"No se pudo subir la comanda adjunta: {error_subida}", 500)
        if not con_guia:
            return _reintentar_con_foto_error(
                "Todavía no hay nada cargado hoy de este proveedor: la comanda adjunta se guarda junto con un artículo.",
                400,
            )
        return RedirectResponse(url="/compras/buscar", status_code=303)

    error, valores = _validar_compra_nueva_form(
        articulo_id, cantidad_cajones, contenido_por_cajon, importe, sena, tipo_retiro
    )
    if error and bytes_foto:
        error += AVISO_READJUNTAR_COMANDA

    articulo = None
    if not error:
        try:
            articulo = obtener_articulo(valores["articulo_id"])
        except Exception as error_db:
            articulos = listar_articulos()
            renglones_hoy = listar_compras_por_fecha_y_proveedor(_hoy_argentina(), proveedor_id)
            compra = {
                "id": None,
                "articulo_id": valores["articulo_id"],
                "cantidad_cajones": cantidad_cajones,
                "contenido_por_cajon": contenido_por_cajon,
                "importe": importe,
                "sena": sena,
                "tipo_retiro": tipo_retiro,
            }
            return templates.TemplateResponse(
                request,
                "compra_form.html",
                {
                    "articulos": articulos,
                    "modo": "nueva",
                    "compra": compra,
                    "proveedor": proveedor,
                    "renglones_hoy": renglones_hoy,
                    "error": f"No se pudo leer el artículo: {error_db}",
                },
                status_code=500,
            )

        if articulo is None:
            error = "El artículo elegido no es válido."
        elif not articulo["unidad_compra"]:
            error = "Este artículo no tiene la unidad de compra configurada. Cargala en /articulos primero."

    if error:
        articulos = listar_articulos()
        renglones_hoy = listar_compras_por_fecha_y_proveedor(_hoy_argentina(), proveedor_id)
        compra = {
            "id": None,
            "articulo_id": valores["articulo_id"],
            "cantidad_cajones": cantidad_cajones,
            "contenido_por_cajon": contenido_por_cajon,
            "importe": importe,
            "sena": sena,
            "tipo_retiro": tipo_retiro,
        }
        return templates.TemplateResponse(
            request,
            "compra_form.html",
            {
                "articulos": articulos,
                "modo": "nueva",
                "compra": compra,
                "proveedor": proveedor,
                "renglones_hoy": renglones_hoy,
                "error": error,
            },
            status_code=400,
        )

    total = valores["cantidad_cajones"] * valores["contenido_por_cajon"]
    if articulo["unidad_compra"] == "kilo":
        cantidad_kilos, cantidad_fraccion = total, None
    else:
        cantidad_kilos, cantidad_fraccion = None, total

    foto_ruta = _subir_comanda_adjunta(comprimida, proveedor["codigo_puesto"]) if comprimida is not None else None

    try:
        crear_compra(
            _hoy_argentina(),
            valores["articulo_id"],
            proveedor_id,
            valores["cantidad_cajones"],
            valores["contenido_por_cajon"],
            cantidad_kilos,
            cantidad_fraccion,
            valores["importe"],
            valores["sena"],
            valores["tipo_retiro"],
            foto_ruta,
        )
    except Exception as error_db:
        articulos = listar_articulos()
        renglones_hoy = listar_compras_por_fecha_y_proveedor(_hoy_argentina(), proveedor_id)
        compra = {
            "id": None,
            "articulo_id": valores["articulo_id"],
            "cantidad_cajones": cantidad_cajones,
            "contenido_por_cajon": contenido_por_cajon,
            "importe": importe,
            "sena": sena,
            "tipo_retiro": tipo_retiro,
        }
        return templates.TemplateResponse(
            request,
            "compra_form.html",
            {
                "articulos": articulos,
                "modo": "nueva",
                "compra": compra,
                "proveedor": proveedor,
                "renglones_hoy": renglones_hoy,
                "error": f"No se pudo guardar la compra: {error_db}",
            },
            status_code=500,
        )

    if accion == "terminar":
        return RedirectResponse(url="/compras/buscar", status_code=303)

    return RedirectResponse(url=f"/compras/nueva?proveedor_id={proveedor_id}", status_code=303)


@app.post("/compras/nueva/cancelar")
def cancelar_carga_proveedor(request: Request, proveedor_id: int = Form(...)):
    """Descarta TODA la carga de hoy de este proveedor (incluso lo ya guardado con "Agregar artículo") y vuelve al hub de Compras.

    Cancelar = quiero salir: se vuelve al hub /compras, no a una búsqueda
    que nadie pidió (terminar de CARGAR sí va a Buscar, para revisar lo
    cargado — cancelar no tiene nada que revisar). La confirmación la
    pide el navegador (confirm() antes de mandar el POST); acá no queda
    nada más por decidir: si llegó el POST, se borra lo que se pueda. No
    es silencioso: el hub muestra el aviso de cuántas se cancelaron y
    cuántas quedaron afuera (ya retiradas o recepcionadas).
    """
    hoy = _hoy_argentina()
    try:
        resultado = eliminar_compras_del_dia_por_proveedor(hoy, proveedor_id)
    except Exception as error_db:
        proveedor = obtener_proveedor(proveedor_id)
        articulos = listar_articulos()
        renglones_hoy = listar_compras_por_fecha_y_proveedor(hoy, proveedor_id)
        return templates.TemplateResponse(
            request,
            "compra_form.html",
            {
                "articulos": articulos,
                "modo": "nueva",
                "compra": None,
                "proveedor": proveedor,
                "renglones_hoy": renglones_hoy,
                "error": f"No se pudo cancelar: {error_db}",
            },
            status_code=500,
        )

    if resultado["protegidas"]:
        aviso = (
            f"{resultado['borradas']} compras canceladas. {resultado['protegidas']} no se pudieron eliminar: "
            "ya fueron retiradas o recepcionadas."
        )
    else:
        aviso = f"{resultado['borradas']} compras canceladas."

    return RedirectResponse(url=f"/compras?{urlencode({'aviso': aviso})}", status_code=303)


def _numero_o_none(valor) -> float | None:
    """El lector devuelve un número o un texto tipo "completar importe" cuando no pudo leerlo."""
    if isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        return valor
    return None


def _contenido_referencia_de(articulo_id: int | None, articulos_existentes: list[dict]) -> float | None:
    if articulo_id is None:
        return None
    for articulo in articulos_existentes:
        if articulo["id"] == articulo_id:
            return articulo.get("contenido_referencia")
    return None


LADO_MAXIMO_PREVIEW_FOTO = 1000
CALIDAD_PREVIEW_FOTO = 60


def _generar_preview_foto(imagen: bytes) -> str:
    """Achica y comprime la foto para poder mostrarla incrustada en la pantalla de revisión.

    La foto original de un celular puede pesar varios MB; para "Ver foto" no
    hace falta esa resolución, solo que se lea. Si algo falla generándola
    (formato raro, etc.), devuelve "" — no tiene que romper la carga por eso,
    la extracción ya se hizo con la imagen original aparte.

    Las fotos de celular vienen casi siempre con el dato de rotación en el
    EXIF (el sensor graba "acostado" y el celular anota cómo hay que
    girarla para verse derecha), no con los píxeles ya rotados. exif_transpose
    aplica esa rotación a los píxeles antes de guardar — si no se hace acá,
    se pierde: este preview (sin EXIF) es lo que termina subido a Storage
    en todos los flujos que usan esta función (comandas, listado de
    compras, fotos de precios), así que de no rotarla ahora la foto queda
    guardada girada para siempre.
    """
    comprimida = _comprimir_foto_jpeg(imagen)
    if comprimida is None:
        return ""
    return f"data:image/jpeg;base64,{base64.standard_b64encode(comprimida).decode('ascii')}"


def _comprimir_foto_jpeg(imagen: bytes) -> bytes | None:
    """El pipeline de compresión de fotos del sistema: EXIF aplicado, máx 1000px, JPEG calidad 60.

    Lo usan el preview de comandas y la subida de fotos a la guía — todo
    lo que termina en Storage pasa por acá, nunca originales de varios MB.
    None si los bytes no son una imagen legible.
    """
    try:
        imagen_pil = Image.open(io.BytesIO(imagen))
        imagen_pil = ImageOps.exif_transpose(imagen_pil)
        imagen_pil = imagen_pil.convert("RGB")
        imagen_pil.thumbnail((LADO_MAXIMO_PREVIEW_FOTO, LADO_MAXIMO_PREVIEW_FOTO))
        buffer = io.BytesIO()
        imagen_pil.save(buffer, format="JPEG", quality=CALIDAD_PREVIEW_FOTO)
        return buffer.getvalue()
    except Exception:
        return None


def _bytes_desde_data_uri(data_uri: str) -> bytes | None:
    """Decodifica un data URI "data:image/jpeg;base64,XXXX" (el que arma _generar_preview_foto) a bytes crudos.

    Devuelve None si el texto no tiene esa forma o el base64 está corrupto
    — nunca lanza, para que quien llame decida qué hacer (acá: no subir
    nada a Storage y seguir guardando la compra igual).
    """
    if not data_uri or not data_uri.startswith("data:") or ";base64," not in data_uri:
        return None
    _, base64_texto = data_uri.split(";base64,", 1)
    try:
        return base64.standard_b64decode(base64_texto)
    except Exception:
        return None


def _armar_sugerencias_desde_datos_leidos(
    datos: dict,
    proveedores_existentes: list[dict],
    articulos_existentes: list[dict],
    conversiones_existentes: list[dict],
) -> dict:
    """Arma las sugerencias de proveedor y renglones a partir de lo que ya devolvió extraer_comanda.

    Es la parte de subir_foto_compra que NO depende de si la lectura salió
    bien o mal — recibe "datos" ya parseado (o {} si la IA no pudo leer
    nada, para el modo de fotos múltiples) y hace exactamente lo mismo que
    hacía antes inline: adivinar_proveedor, traer el aprendizaje de ESE
    proveedor si matcheó uno existente, y adivinar_articulo renglón por
    renglón. Compartida entre subir_foto_compra (una foto) y
    leer_foto_comanda_multiple (varias fotos) para no duplicar esta lógica.

    Devuelve {"codigo_puesto_sugerido", "nombre_sugerido", "renglones"}.
    Con datos={} (o sin "items"), renglones queda en lista vacía — cada
    llamador decide qué hacer con eso.
    """
    proveedor_leido = datos.get("proveedor") or {}
    proveedor_sugerido = adivinar_proveedor(proveedor_leido, proveedores_existentes)

    aprendizaje = {}
    if proveedor_sugerido is not None and proveedor_sugerido.get("id") is not None:
        try:
            filas = listar_aprendizaje_articulos_por_proveedor(proveedor_sugerido["id"])
            aprendizaje = {normalizar_texto(fila["texto_leido"]): fila["articulo_id"] for fila in filas}
        except Exception:
            aprendizaje = {}

    renglones = []
    for item in datos.get("items") or []:
        texto_leido = item.get("articulo") or ""
        articulo_id_sugerido = adivinar_articulo(texto_leido, aprendizaje, articulos_existentes, conversiones_existentes)
        renglones.append(
            {
                "texto_leido": texto_leido,
                "articulo_id": articulo_id_sugerido,
                "cantidad_cajones": _numero_o_none(item.get("cantidad")),
                "contenido_por_cajon": _contenido_referencia_de(articulo_id_sugerido, articulos_existentes),
                "importe": _numero_o_none(item.get("importe")),
                "sena": _numero_o_none(item.get("sena")),
                "nota_margen": item.get("nota_margen") or "",
                "advertencia": item.get("confianza") == "baja" or articulo_id_sugerido is None,
                "descartado": False,
            }
        )

    return {
        "codigo_puesto_sugerido": proveedor_sugerido["codigo_puesto"] if proveedor_sugerido else "",
        "nombre_sugerido": proveedor_sugerido["nombre"] if proveedor_sugerido else (proveedor_leido.get("nombre") or ""),
        "renglones": renglones,
    }


@app.post("/compras/nueva/foto")
async def subir_foto_compra(request: Request, foto: UploadFile = File(...)):
    try:
        imagen = await foto.read()
        foto_preview = _generar_preview_foto(imagen)
        datos = extraer_comanda(imagen)
    except Exception as error_lector:
        return templates.TemplateResponse(
            request,
            "compra_leer_foto.html",
            {"error": f"No se pudo leer la foto: {error_lector}"},
            status_code=500,
        )

    try:
        proveedores_existentes = listar_proveedores()
        articulos_existentes = listar_articulos()
        conversiones_existentes = listar_todas_las_conversiones()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    sugerencias = _armar_sugerencias_desde_datos_leidos(
        datos, proveedores_existentes, articulos_existentes, conversiones_existentes
    )

    return templates.TemplateResponse(
        request,
        "compra_revision_foto.html",
        {
            "proveedores": proveedores_existentes,
            "articulos": articulos_existentes,
            "codigo_puesto_sugerido": sugerencias["codigo_puesto_sugerido"],
            "nombre_sugerido": sugerencias["nombre_sugerido"],
            "renglones": sugerencias["renglones"],
            "foto_preview": foto_preview,
            "error": None,
            "carga_token": uuid4().hex,
        },
    )


@app.get("/compras/nueva/fotos")
def ver_carga_comandas_multiples(request: Request):
    try:
        proveedores = listar_proveedores()
    except Exception:
        proveedores = []
    return templates.TemplateResponse(request, "compra_fotos_multiples.html", {"proveedores": proveedores})


@app.post("/compras/nueva/fotos/leer")
async def leer_foto_comanda_multiple(foto: UploadFile = File(...)):
    imagen = await foto.read()
    foto_preview = _generar_preview_foto(imagen)
    try:
        datos = extraer_comanda(imagen)
    except Exception:
        datos = {}

    try:
        proveedores_existentes = listar_proveedores()
        articulos_existentes = listar_articulos()
        conversiones_existentes = listar_todas_las_conversiones()
    except Exception as error_db:
        return JSONResponse({"ok": False, "error": f"Error al conectar con la base de datos: {error_db}"})

    sugerencias = _armar_sugerencias_desde_datos_leidos(
        datos, proveedores_existentes, articulos_existentes, conversiones_existentes
    )
    renglones = sugerencias["renglones"] or [
        {
            "texto_leido": "",
            "articulo_id": None,
            "cantidad_cajones": None,
            "contenido_por_cajon": None,
            "importe": None,
            "sena": None,
            "nota_margen": "",
            "advertencia": True,
            "descartado": False,
        }
    ]

    html = templates.env.get_template("_fragmento_revision_comanda_multiple.html").render(
        {
            "articulos": articulos_existentes,
            "codigo_puesto_sugerido": sugerencias["codigo_puesto_sugerido"],
            "nombre_sugerido": sugerencias["nombre_sugerido"],
            "renglones": renglones,
            "foto_preview": foto_preview,
            # Token único por comanda: viaja escondido en el form y protege
            # contra guardados duplicados si el teléfono reintenta después
            # de un corte de internet (ver crear_compras_de_comanda).
            "carga_token": uuid4().hex,
        }
    )
    return JSONResponse({"ok": True, "html": html, "cantidad_renglones": len(renglones)})


@app.post("/compras/nueva/listado/leer")
async def leer_listado_consolidado(foto: UploadFile = File(...)):
    """Lee UNA foto de planilla consolidada (varios proveedores mezclados) y arma un grupo revisable por proveedor.

    A diferencia de leer_foto_comanda_multiple (una foto = una comanda de UN
    proveedor), acá una sola llamada devuelve TODOS los grupos de una: no
    hace falta cola ni concurrencia, la planilla se lee una sola vez.
    """
    imagen = await foto.read()
    foto_preview = _generar_preview_foto(imagen)
    try:
        datos = extraer_listado_consolidado(imagen)
    except Exception as error_lector:
        return JSONResponse({"ok": False, "error": f"No se pudo leer la planilla: {error_lector}"})

    try:
        proveedores_existentes = listar_proveedores()
        articulos_existentes = listar_articulos()
        conversiones_existentes = listar_todas_las_conversiones()
    except Exception as error_db:
        return JSONResponse({"ok": False, "error": f"Error al conectar con la base de datos: {error_db}"})

    renglones_leidos = datos.get("renglones") or []
    if not renglones_leidos:
        return JSONResponse({"ok": False, "error": "No se pudo leer ningún renglón de la planilla."})

    grupos_por_proveedor = agrupar_renglones_por_proveedor(renglones_leidos, proveedores_existentes)

    grupos_respuesta = []
    for grupo in grupos_por_proveedor:
        datos_grupo = {
            "proveedor": {"nombre": grupo["proveedor_texto"]},
            "items": [
                {
                    "articulo": renglon.get("articulo") or "",
                    "cantidad": renglon.get("cantidad"),
                    "importe": renglon.get("importe"),
                    "sena": None,
                    "nota_margen": renglon.get("nota_margen") or "",
                    "confianza": renglon.get("confianza"),
                }
                for renglon in grupo["renglones"]
            ],
        }
        sugerencias = _armar_sugerencias_desde_datos_leidos(
            datos_grupo, proveedores_existentes, articulos_existentes, conversiones_existentes
        )

        renglones_sugeridos = sugerencias["renglones"]
        # kg_x_bulto viene escrito en la planilla renglón por renglón (a
        # diferencia de una comanda normal, donde ese dato sale del
        # catálogo) — cuando está, pisa el valor de referencia que ya trajo
        # _armar_sugerencias_desde_datos_leidos.
        for renglon_sugerido, renglon_leido in zip(renglones_sugeridos, grupo["renglones"]):
            kg_x_bulto = _numero_o_none(renglon_leido.get("kg_x_bulto"))
            if kg_x_bulto is not None:
                renglon_sugerido["contenido_por_cajon"] = kg_x_bulto

        renglones_sugeridos = renglones_sugeridos or [
            {
                "texto_leido": "",
                "articulo_id": None,
                "cantidad_cajones": None,
                "contenido_por_cajon": None,
                "importe": None,
                "sena": None,
                "nota_margen": "",
                "advertencia": True,
                "descartado": False,
            }
        ]

        html = templates.env.get_template("_fragmento_revision_comanda_multiple.html").render(
            {
                "articulos": articulos_existentes,
                "codigo_puesto_sugerido": sugerencias["codigo_puesto_sugerido"],
                "nombre_sugerido": sugerencias["nombre_sugerido"],
                "renglones": renglones_sugeridos,
                "foto_preview": foto_preview,
                # Un token por grupo: cada proveedor de la planilla se
                # guarda por separado, así que cada guardado tiene su
                # propia protección anti-duplicado.
                "carga_token": uuid4().hex,
            }
        )
        grupos_respuesta.append({"html": html, "cantidad_renglones": len(renglones_sugeridos)})

    return JSONResponse({"ok": True, "grupos": grupos_respuesta, "foto_preview": foto_preview})


@app.post("/compras/nueva/listado/subir-foto")
async def subir_foto_listado_ruta(foto_preview: str = Form(...)):
    """Sube UNA sola vez la foto de la planilla consolidada, compartida por todos sus grupos/proveedores.

    Ruta chica y separada a propósito (no reusa confirmar_compra_foto): la
    pantalla de listado la llama una única vez, antes de guardar el primer
    grupo, y guarda la foto_ruta devuelta para pasarla en los guardados
    siguientes (ver foto_ruta_ya_subida en confirmar_compra_foto) — así la
    foto no se vuelve a subir una vez por proveedor.
    """
    bytes_foto = _bytes_desde_data_uri(foto_preview)
    if not bytes_foto:
        return JSONResponse({"ok": False, "error": "No se pudo leer la foto para subir."})

    try:
        foto_ruta = subir_foto_comanda(bytes_foto, "listado")
    except Exception as error:
        return JSONResponse({"ok": False, "error": f"No se pudo subir la foto: {error}"})

    return JSONResponse({"ok": True, "foto_ruta": foto_ruta})


@app.post("/compras/nueva/foto/confirmar")
async def confirmar_compra_foto(request: Request):
    form = await request.form()

    codigo_puesto_texto = str(form.get("codigo_puesto", ""))
    nombre_texto = str(form.get("nombre", ""))
    foto_preview_texto = str(form.get("foto_preview", ""))
    # Solo la pantalla de listado consolidado manda esto: la foto de la
    # planilla ya se subió una vez (ver /compras/nueva/listado/subir-foto),
    # compartida por todos sus proveedores — si viene, no hay que volver a
    # subir nada. En comanda única y múltiples fotos este campo no existe
    # nunca, así que ahí el comportamiento no cambia.
    foto_ruta_ya_subida_texto = str(form.get("foto_ruta_ya_subida", "")).strip()
    # Token único por comanda, generado por el server al armar la pantalla
    # de revisión (ver crear_compras_de_comanda). Vacío en forms viejos que
    # quedaron abiertos de antes de este cambio: se guarda sin protección.
    carga_token = str(form.get("carga_token", "")).strip() or None
    accion = str(form.get("accion", "agregar_articulos"))
    try:
        cantidad_renglones = int(form.get("cantidad_renglones", "0") or "0")
    except ValueError:
        cantidad_renglones = 0

    try:
        articulos_existentes = listar_articulos()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    # Solo para la sugerencia puesto<->nombre en la pantalla de revisión; si
    # falla, la pantalla se muestra igual sin esa ayuda.
    try:
        proveedores_existentes = listar_proveedores()
    except Exception:
        proveedores_existentes = []

    articulos_por_id = {articulo["id"]: articulo for articulo in articulos_existentes}

    error, codigo_valor = _validar_codigo_puesto(codigo_puesto_texto)
    nombre_valor = nombre_texto
    if not error:
        error, nombre_valor = _validar_nombre(nombre_texto)

    renglones_para_mostrar = []
    renglones_a_guardar = []
    for indice in range(cantidad_renglones):
        prefijo = f"item_{indice}_"
        descartado = form.get(prefijo + "descartar") == "on"
        texto_leido = str(form.get(prefijo + "texto_leido", ""))
        articulo_id_texto = str(form.get(prefijo + "articulo_id", "")).strip()
        cantidad_cajones_texto = str(form.get(prefijo + "cantidad_cajones", ""))
        contenido_por_cajon_texto = str(form.get(prefijo + "contenido_por_cajon", ""))
        importe_texto = str(form.get(prefijo + "importe", ""))
        sena_texto = str(form.get(prefijo + "sena", ""))
        tipo_retiro_texto = str(form.get(prefijo + "tipo_retiro", ""))

        renglones_para_mostrar.append(
            {
                "texto_leido": texto_leido,
                "articulo_id": int(articulo_id_texto) if articulo_id_texto.isdigit() else None,
                "cantidad_cajones": cantidad_cajones_texto,
                "contenido_por_cajon": contenido_por_cajon_texto,
                "importe": importe_texto,
                "sena": sena_texto,
                "tipo_retiro": tipo_retiro_texto,
                "nota_margen": "",
                "advertencia": False,
                "descartado": descartado,
            }
        )

        if descartado:
            continue

        if error:
            continue

        error_renglon, valores_renglon = _validar_compra_nueva_form(
            articulo_id_texto, cantidad_cajones_texto, contenido_por_cajon_texto, importe_texto, sena_texto, tipo_retiro_texto
        )

        articulo = None
        if not error_renglon:
            articulo = articulos_por_id.get(valores_renglon["articulo_id"])
            if articulo is None:
                error_renglon = "El artículo elegido no es válido."
            elif not articulo["unidad_compra"]:
                error_renglon = "Este artículo no tiene la unidad de compra configurada. Cargala en /articulos primero."

        if error_renglon:
            error = f"Renglón {indice + 1}: {error_renglon}"
        else:
            renglones_a_guardar.append((texto_leido, valores_renglon, articulo))

    if not error and not renglones_a_guardar:
        error = "No hay ningún renglón para guardar (revisá si descartaste todos)."

    if error:
        return templates.TemplateResponse(
            request,
            "compra_revision_foto.html",
            {
                "proveedores": proveedores_existentes,
                "articulos": articulos_existentes,
                "codigo_puesto_sugerido": codigo_puesto_texto,
                "nombre_sugerido": nombre_texto,
                "renglones": renglones_para_mostrar,
                "foto_preview": foto_preview_texto,
                "error": error,
                "carga_token": carga_token,
            },
            status_code=400,
        )

    try:
        proveedor_id, reactivado = obtener_o_crear_proveedor_por_codigo(codigo_valor, nombre_valor)
        aviso_reactivado = _aviso_proveedor_reactivado(reactivado, nombre_valor)

        # Reintento de un guardado que YA entró: el server guardó y
        # commiteó, pero el teléfono se quedó sin internet antes de ver la
        # respuesta y mandó lo mismo de nuevo. No se guarda ni se sube
        # nada otra vez — se responde igual que el guardado original, así
        # la pantalla avanza a la comanda siguiente sin duplicar.
        ya_guardada = carga_token is not None and comanda_ya_guardada(carga_token)

        if not ya_guardada:
            # Subir la foto es un extra, nunca puede tirar abajo el guardado de
            # la compra: si falla (sin conexión, credencial mala, lo que sea),
            # se loguea completo acá y se sigue con foto_ruta = None para todos
            # los renglones — mejor una compra guardada sin foto que ninguna
            # compra guardada. Se sube UNA sola vez (una comanda = una foto =
            # varios renglones), no una vez por renglón.
            #
            # Si foto_ruta_ya_subida vino con valor (listado consolidado, a
            # partir del segundo grupo guardado), se usa directo y no se sube
            # nada de nuevo — la foto de la planilla ya está en Storage,
            # compartida por todos sus proveedores.
            if foto_ruta_ya_subida_texto:
                foto_ruta = foto_ruta_ya_subida_texto
            else:
                foto_ruta = None
                bytes_foto = _bytes_desde_data_uri(foto_preview_texto)
                if bytes_foto:
                    try:
                        foto_ruta = subir_foto_comanda(bytes_foto, codigo_valor)
                    except Exception:
                        logger.exception(
                            "No se pudo subir la foto de la comanda a Supabase Storage (proveedor %s) "
                            "— se guarda la compra igual, sin foto",
                            codigo_valor,
                        )
                        foto_ruta = None

            hoy = _hoy_argentina()
            renglones_comanda = []
            for texto_leido, valores, articulo in renglones_a_guardar:
                total = valores["cantidad_cajones"] * valores["contenido_por_cajon"]
                if articulo["unidad_compra"] == "kilo":
                    cantidad_kilos, cantidad_fraccion = total, None
                else:
                    cantidad_kilos, cantidad_fraccion = None, total
                renglones_comanda.append(
                    {
                        "articulo_id": valores["articulo_id"],
                        "cantidad_cajones": valores["cantidad_cajones"],
                        "contenido_por_cajon": valores["contenido_por_cajon"],
                        "cantidad_kilos": cantidad_kilos,
                        "cantidad_fraccion": cantidad_fraccion,
                        "importe": valores["importe"],
                        "sena": valores["sena"],
                        "tipo_retiro": valores["tipo_retiro"],
                    }
                )

            # Todos los renglones de la comanda en UNA transacción: si algo
            # falla a mitad de camino (corte de internet incluido), no queda
            # nada guardado a medias — se reintenta la comanda entera.
            crear_compras_de_comanda(hoy, proveedor_id, renglones_comanda, foto_ruta, carga_token)

            for texto_leido, valores, _ in renglones_a_guardar:
                # Solo se aprende de texto REALMENTE leído de la comanda: ni de
                # renglones agregados a mano (texto vacío) ni de los placeholders
                # que el lector devuelve cuando no pudo leer el artículo — si no,
                # "completar articulo" queda asociado a un artículo cualquiera y
                # envenena las sugerencias futuras de ese proveedor.
                #
                # Y el aprendizaje va DESPUÉS del guardado y nunca lo pisa: la
                # comanda ya está commiteada — si esto falla se loguea y listo,
                # reportar acá "no se pudo guardar" sería mentira.
                texto_aprendible = normalizar_texto(texto_leido)
                if texto_aprendible and texto_aprendible not in TEXTOS_PLACEHOLDER_LECTOR:
                    try:
                        aprender_articulo(proveedor_id, texto_aprendible, valores["articulo_id"])
                    except Exception:
                        logger.exception(
                            "No se pudo guardar el aprendizaje de '%s' (proveedor %s) — la comanda quedó guardada igual",
                            texto_aprendible,
                            proveedor_id,
                        )
    except Exception as error_db:
        return templates.TemplateResponse(
            request,
            "compra_revision_foto.html",
            {
                "proveedores": proveedores_existentes,
                "articulos": articulos_existentes,
                "codigo_puesto_sugerido": codigo_puesto_texto,
                "nombre_sugerido": nombre_texto,
                "renglones": renglones_para_mostrar,
                "foto_preview": foto_preview_texto,
                "error": f"No se pudo guardar la compra: {error_db}",
                "carga_token": carga_token,
            },
            status_code=500,
        )

    if accion == "guardar":
        return RedirectResponse(url="/compras/buscar", status_code=303)

    return RedirectResponse(url=_url_nueva_compra(proveedor_id, aviso_reactivado), status_code=303)


def _url_nueva_compra(proveedor_id: int, aviso: str | None) -> str:
    """La vuelta a /compras/nueva con el proveedor ya elegido, y el aviso si hay algo que contar."""
    parametros = {"proveedor_id": proveedor_id}
    if aviso:
        parametros["aviso"] = aviso
    return f"/compras/nueva?{urlencode(parametros)}"


def _aviso_proveedor_reactivado(reactivado: bool, nombre: str) -> str | None:
    """El aviso de que cargar una compra volvió a activar un proveedor que estaba de baja.

    Único lugar donde se escribe ese texto — lo usan las tres pantallas
    que cargan por código (carga manual, comandas múltiples e Ingresar
    Mercadería del depósito). Se dice porque una baja que se deshace sola
    y en silencio es peor que no tener baja: el que lo dio de baja tiene
    que poder enterarse de que volvió, y por qué.
    """
    if not reactivado:
        return None
    return (
        f'"{nombre}" estaba dado de baja y volvió a quedar activo: llegó una compra con su código. '
        "Si no corresponde, dalo de baja de nuevo en Compras → Proveedores."
    )


def _renderizar_pantalla_proveedores_compras(
    request: Request, *, error: str | None = None, aviso: str | None = None, status_code: int = 200
):
    try:
        proveedores = listar_proveedores_para_abm()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    return templates.TemplateResponse(
        request,
        "compras_proveedores.html",
        {"proveedores": proveedores, "error": error, "aviso": aviso},
        status_code=status_code,
    )


@app.get("/compras/proveedores")
def ver_proveedores_compras(request: Request, aviso: str | None = None):
    """Proveedores de compras: corregir el nombre y dar de baja. NO hay alta.

    Un proveedor de compras nace solo, al cargar una compra con un código
    de puesto nuevo (obtener_o_crear_proveedor_por_codigo). Esta pantalla
    existe por lo que ESO no permite arreglar: la identidad es
    codigo_puesto, así que un código mal tipeado crea un proveedor
    fantasma que no se puede corregir renombrando — la baja lógica es su
    única salida. El nombre sí se corrige acá (y también solo, cargando
    otra compra con el mismo código: "la última corrección manda").
    """
    return _renderizar_pantalla_proveedores_compras(request, aviso=aviso)


@app.post("/compras/proveedores/{proveedor_id}/renombrar")
def renombrar_proveedor_compras_ruta(request: Request, proveedor_id: int, nombre: str = Form("")):
    """Corrige el nombre. El código no se toca nunca: es la identidad, cambiarlo movería todas sus compras."""
    nombre_limpio = re.sub(r"\s+", " ", nombre).strip()
    if not nombre_limpio:
        return _renderizar_pantalla_proveedores_compras(
            request, error="El nombre del proveedor es obligatorio.", status_code=400
        )
    try:
        renombrar_proveedor(proveedor_id, nombre_limpio)
    except ValueError as error:
        return _renderizar_pantalla_proveedores_compras(request, error=str(error), status_code=400)
    except Exception as error_db:
        return _renderizar_pantalla_proveedores_compras(
            request, error=f"No se pudo renombrar el proveedor: {error_db}", status_code=500
        )
    parametros = urlencode({"aviso": f"Proveedor renombrado a '{nombre_limpio}'."})
    return RedirectResponse(url=f"/compras/proveedores?{parametros}", status_code=303)


@app.post("/compras/proveedores/{proveedor_id}/baja")
def dar_de_baja_proveedor_compras_ruta(request: Request, proveedor_id: int):
    """Baja lógica: lo saca del selector de carga y nada más. No borra ni bloquea nada.

    A propósito NO se valida contra las compras: la FK queda intacta, las
    compras viejas siguen mostrando el nombre y se siguen pudiendo buscar
    por él (los filtros de búsqueda usan listar_todos_los_proveedores). La
    pantalla muestra cuántas compras tiene antes de confirmar — decirlo,
    no impedirlo.
    """
    return _cambiar_actividad_proveedor_compras(request, proveedor_id, activo=False)


@app.post("/compras/proveedores/{proveedor_id}/alta")
def dar_de_alta_proveedor_compras_ruta(request: Request, proveedor_id: int):
    """Vuelve a activar un proveedor dado de baja por error. La baja no es un camino de ida."""
    return _cambiar_actividad_proveedor_compras(request, proveedor_id, activo=True)


def _cambiar_actividad_proveedor_compras(request: Request, proveedor_id: int, *, activo: bool):
    """El cuerpo compartido de la baja y el alta: es el mismo guardado, cambia el valor y el texto."""
    try:
        cambiar_actividad_proveedor(proveedor_id, activo)
    except ValueError as error:
        return _renderizar_pantalla_proveedores_compras(request, error=str(error), status_code=400)
    except Exception as error_db:
        verbo = "dar de alta" if activo else "dar de baja"
        return _renderizar_pantalla_proveedores_compras(
            request, error=f"No se pudo {verbo} el proveedor: {error_db}", status_code=500
        )
    aviso = (
        "Proveedor dado de alta: vuelve a aparecer para elegir al cargar una compra."
        if activo
        else "Proveedor dado de baja: deja de aparecer para elegir al cargar una compra. Sus compras quedan como están."
    )
    return RedirectResponse(url=f"/compras/proveedores?{urlencode({'aviso': aviso})}", status_code=303)


def _armar_aviso_bloqueo_edicion(estado: str | None, cantidad_bloqueada: bool, precio_bloqueado: bool) -> str:
    """Arma el aviso de qué no se puede editar (cantidad, precio, o ambos) y por qué, para Editar Compra."""
    # Solo Depósito bloquea la cantidad (regla 19/08/2026): si está
    # bloqueada sola (sin el precio), la única causa posible es recepcionada.
    razon_cantidad = "ya fue recepcionada"
    razon_precio = "tuvo un rechazo total" if estado == "rechazado" else "nunca ingresó al depósito"

    if cantidad_bloqueada and precio_bloqueado:
        return f"Esta compra {razon_precio}: no se puede modificar ni la cantidad ni el precio."
    if cantidad_bloqueada:
        return f"La cantidad no se puede modificar: la compra {razon_cantidad}. El precio sí se puede corregir."
    return f"El precio no se puede modificar: la compra {razon_precio}. La cantidad sí se puede corregir."


@app.get("/compras/{compra_id}/editar")
def ver_editar_compra(request: Request, compra_id: int, error: str | None = None):
    try:
        compra = obtener_compra(compra_id)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    if compra is None:
        raise HTTPException(status_code=404, detail="Compra no encontrada")

    try:
        articulos = listar_articulos()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    cantidad_bloqueada = compra_tiene_cantidad_bloqueada(compra["estado"])
    precio_bloqueado = compra_tiene_precio_bloqueado(compra["estado"])
    if (cantidad_bloqueada or precio_bloqueado) and not error:
        error = _armar_aviso_bloqueo_edicion(compra["estado"], cantidad_bloqueada, precio_bloqueado)

    return templates.TemplateResponse(
        request,
        "compra_form.html",
        {
            "articulos": articulos,
            "modo": "editar",
            "compra": compra,
            "fotos_guia": _fotos_de_la_guia_de(compra),
            "error": error,
            "cantidad_bloqueada": cantidad_bloqueada,
            "precio_bloqueado": precio_bloqueado,
        },
    )


@app.post("/compras/{compra_id}/editar")
def editar_compra(
    request: Request,
    compra_id: int,
    accion: str = Form("guardar"),
    articulo_id: str = Form(""),
    cantidad_cajones: str = Form(""),
    contenido_por_cajon: str = Form(""),
    importe: str = Form(""),
    sena: str = Form(""),
    tipo_retiro: str = Form(""),
):
    """"Guardar" actualiza el renglón que se está editando (bloqueado si ya está recepcionado/retirado).

    "Agregar artículo" es una operación totalmente distinta: inserta una
    compra NUEVA en la misma guía (mismo proveedor y fecha_operacion que
    la compra que se está editando, tomando de ahí el próximo punto de
    guía — mismo mecanismo de crear_compra que cualquier carga). Nunca
    toca ni hereda el estado de la compra que se está editando: entra con
    estado/estado_retiro 'pendiente' como cualquier compra nueva, así que
    aparece en Logística para retirar aunque el renglón original ya esté
    retirado. Por eso "Agregar artículo" queda habilitado incluso cuando
    el renglón viejo está bloqueado — no pasa por actualizar_compra.
    """
    try:
        compra_actual = obtener_compra(compra_id)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    if compra_actual is None:
        raise HTTPException(status_code=404, detail="Compra no encontrada")

    error, valores = _validar_compra_nueva_form(
        articulo_id, cantidad_cajones, contenido_por_cajon, importe, sena, tipo_retiro
    )

    articulo = None
    if not error:
        try:
            articulo = obtener_articulo(valores["articulo_id"])
        except Exception as error_db:
            articulos = listar_articulos()
            compra = {
                "id": compra_id,
                "articulo_id": valores["articulo_id"],
                "proveedor_nombre": compra_actual["proveedor_nombre"],
                "proveedor_codigo_puesto": compra_actual["proveedor_codigo_puesto"],
                "cantidad_cajones": cantidad_cajones,
                "contenido_por_cajon": contenido_por_cajon,
                "importe": importe,
                "sena": sena,
                "tipo_retiro": tipo_retiro,
            }
            return templates.TemplateResponse(
                request,
                "compra_form.html",
                {
                    "articulos": articulos,
                    "modo": "editar",
                    "compra": compra,
                    "error": f"No se pudo leer el artículo: {error_db}",
                },
                status_code=500,
            )

        if articulo is None:
            error = "El artículo elegido no es válido."
        elif not articulo["unidad_compra"]:
            error = "Este artículo no tiene la unidad de compra configurada. Cargala en /articulos primero."

    if error:
        articulos = listar_articulos()
        compra = {
            "id": compra_id,
            "articulo_id": valores["articulo_id"],
            "proveedor_nombre": compra_actual["proveedor_nombre"],
            "proveedor_codigo_puesto": compra_actual["proveedor_codigo_puesto"],
            "cantidad_cajones": cantidad_cajones,
            "contenido_por_cajon": contenido_por_cajon,
            "importe": importe,
            "sena": sena,
            "tipo_retiro": tipo_retiro,
        }
        return templates.TemplateResponse(
            request,
            "compra_form.html",
            {"articulos": articulos, "modo": "editar", "compra": compra, "error": error},
            status_code=400,
        )

    total = valores["cantidad_cajones"] * valores["contenido_por_cajon"]
    if articulo["unidad_compra"] == "kilo":
        cantidad_kilos, cantidad_fraccion = total, None
    else:
        cantidad_kilos, cantidad_fraccion = None, total

    if accion == "agregar":
        try:
            crear_compra(
                compra_actual["fecha_operacion"],
                valores["articulo_id"],
                compra_actual["proveedor_id"],
                valores["cantidad_cajones"],
                valores["contenido_por_cajon"],
                cantidad_kilos,
                cantidad_fraccion,
                valores["importe"],
                valores["sena"],
                valores["tipo_retiro"],
            )
        except Exception as error_db:
            articulos = listar_articulos()
            compra = {
                "id": compra_id,
                "articulo_id": valores["articulo_id"],
                "proveedor_nombre": compra_actual["proveedor_nombre"],
                "proveedor_codigo_puesto": compra_actual["proveedor_codigo_puesto"],
                "cantidad_cajones": cantidad_cajones,
                "contenido_por_cajon": contenido_por_cajon,
                "importe": importe,
                "sena": sena,
                "tipo_retiro": tipo_retiro,
            }
            return templates.TemplateResponse(
                request,
                "compra_form.html",
                {
                    "articulos": articulos,
                    "modo": "editar",
                    "compra": compra,
                    "error": f"No se pudo agregar el artículo: {error_db}",
                },
                status_code=500,
            )

        return RedirectResponse(url=f"/compras/{compra_id}/editar", status_code=303)

    # Cantidad y precio son dos bloqueos independientes (ver
    # compra_tiene_cantidad_bloqueada/compra_tiene_precio_bloqueado en
    # app/db.py, la única definición de cada regla): si uno de los dos
    # está bloqueado acá simplemente no se llama a su actualización — lo
    # que haya llegado en ese campo del formulario se descarta, nunca se
    # guarda. Si algo cambió de verdad en la base entre que se abrió la
    # pantalla y se mandó el POST, actualizar_cantidad_compra/
    # actualizar_precio_compra lo vuelven a chequear solas y frenan igual.
    cantidad_bloqueada = compra_tiene_cantidad_bloqueada(compra_actual["estado"])
    precio_bloqueado = compra_tiene_precio_bloqueado(compra_actual["estado"])

    try:
        if not cantidad_bloqueada:
            actualizar_cantidad_compra(
                compra_id,
                valores["articulo_id"],
                valores["cantidad_cajones"],
                valores["contenido_por_cajon"],
                cantidad_kilos,
                cantidad_fraccion,
                valores["tipo_retiro"],
            )
        if not precio_bloqueado:
            actualizar_precio_compra(compra_id, valores["importe"], valores["sena"])
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error_db:
        articulos = listar_articulos()
        compra = {
            "id": compra_id,
            "articulo_id": valores["articulo_id"],
            "proveedor_nombre": compra_actual["proveedor_nombre"],
            "proveedor_codigo_puesto": compra_actual["proveedor_codigo_puesto"],
            "cantidad_cajones": cantidad_cajones,
            "contenido_por_cajon": contenido_por_cajon,
            "importe": importe,
            "sena": sena,
            "tipo_retiro": tipo_retiro,
        }
        return templates.TemplateResponse(
            request,
            "compra_form.html",
            {
                "articulos": articulos,
                "modo": "editar",
                "compra": compra,
                "error": f"No se pudo guardar la compra: {error_db}",
            },
            status_code=500,
        )

    # Los filtros de la búsqueda viajan en el query string de la URL de
    # editar (los pone el link "Editar" de Buscar Compras, y el form
    # postea a esa misma URL, así que sobreviven a los reintentos por
    # error): al guardar se vuelve a la MISMA búsqueda que se estaba
    # haciendo, no a la default de 48hs.
    filtros_query = request.url.query
    destino = f"/compras/buscar?{filtros_query}" if filtros_query else "/compras/buscar"
    return RedirectResponse(url=destino, status_code=303)


def _eliminar_compra_y_su_foto_si_corresponde(compra_id: int) -> None:
    """Borra una compra y, si esta era la última que usaba su foto, también el archivo del Storage.

    Borrar la foto es un extra: si falla (sin conexión, credencial mala,
    lo que sea), se loguea completo y se sigue igual — la compra ya se
    borró, una foto huérfana es un mal menor frente a no poder borrar
    nada. Si falla el borrado de la COMPRA en sí, esta función deja que
    la excepción se propague: eso sí lo tiene que ver quien llama.
    """
    rutas_a_borrar = eliminar_compra(compra_id)
    for ruta in rutas_a_borrar:
        try:
            borrar_foto_comanda(ruta)
        except Exception:
            logger.exception(
                "No se pudo borrar de Supabase Storage la foto %s (la compra %s ya se borró igual)",
                ruta,
                compra_id,
            )


@app.post("/compras/{compra_id}/eliminar")
async def eliminar_compra_ruta(request: Request, compra_id: int):
    # Los filtros activos viajan como campos ocultos del form de la fila,
    # para que un rechazo del borrado vuelva a la MISMA búsqueda con un
    # cartel legible — nunca una página de error cruda.
    form = await request.form()
    fecha_desde = str(form.get("fecha_desde", ""))
    fecha_hasta = str(form.get("fecha_hasta", ""))
    proveedor_id = str(form.get("proveedor_id", ""))
    articulo_id = str(form.get("articulo_id", ""))

    try:
        _eliminar_compra_y_su_foto_si_corresponde(compra_id)
    except ValueError as error:
        # Compra que no se puede borrar (recepcionada, retirada o "No
        # ingresó"): la regla y el mensaje vienen de eliminar_compra.
        return _renderizar_pantalla_buscar_compras(
            request, fecha_desde, fecha_hasta, proveedor_id, articulo_id, aviso=str(error), status_code=400
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"No se pudo eliminar la compra: {error}") from error

    # Al borrar se vuelve a la MISMA búsqueda que se estaba haciendo (los
    # filtros ya viajaban como campos ocultos para el caso de rechazo).
    filtros = {
        clave: valor
        for clave, valor in (
            ("fecha_desde", fecha_desde),
            ("fecha_hasta", fecha_hasta),
            ("proveedor_id", proveedor_id),
            ("articulo_id", articulo_id),
        )
        if valor
    }
    destino = f"/compras/buscar?{urlencode(filtros)}" if filtros else "/compras/buscar"
    return RedirectResponse(url=destino, status_code=303)


@app.post("/compras/eliminar-varias")
async def eliminar_varias_compras_ruta(request: Request):
    """Borrado múltiple desde Buscar Compras. Conserva los filtros activos (van como campos ocultos del
    formulario) para volver a mostrar exactamente la misma búsqueda, con un aviso de qué se borró y qué no.

    No es silencioso: procesa todas las que puede y, si alguna queda
    afuera (ya retirada o recepcionada), lo dice explícitamente en el
    aviso — nunca las excluye sin avisar.
    """
    form = await request.form()
    ids = [int(valor) for valor in form.getlist("compra_id") if valor.isdigit()]
    fecha_desde = str(form.get("fecha_desde", ""))
    fecha_hasta = str(form.get("fecha_hasta", ""))
    proveedor_id = str(form.get("proveedor_id", ""))
    articulo_id = str(form.get("articulo_id", ""))

    if not ids:
        return _renderizar_pantalla_buscar_compras(request, fecha_desde, fecha_hasta, proveedor_id, articulo_id)

    fecha_desde_valor, fecha_hasta_valor, proveedor_id_valor, articulo_id_valor = _leer_filtros_buscar_compras(
        fecha_desde, fecha_hasta, proveedor_id, articulo_id
    )
    try:
        compras_antes = buscar_compras(fecha_desde_valor, fecha_hasta_valor, proveedor_id_valor, articulo_id_valor)
    except Exception:
        compras_antes = []
    etiqueta_por_id = {
        compra["id"]: f"{compra['articulo_nombre']} ({compra['proveedor_nombre']})" for compra in compras_antes
    }

    etiquetas_fallidas = []
    for compra_id in ids:
        try:
            _eliminar_compra_y_su_foto_si_corresponde(compra_id)
        except Exception:
            logger.exception("No se pudo borrar la compra %s (borrado múltiple)", compra_id)
            etiquetas_fallidas.append(etiqueta_por_id.get(compra_id, "una compra"))

    cantidad_borradas = len(ids) - len(etiquetas_fallidas)
    if not etiquetas_fallidas:
        aviso = f"Se eliminaron {cantidad_borradas} compras."
    else:
        # Mensaje pensado para un usuario no técnico: sin ids ni jerga de
        # base de datos. La causa más probable es que ya fueron retiradas,
        # recepcionadas o marcadas "No ingresó" (bloqueado en
        # eliminar_compra), se explica en criollo.
        aviso = (
            f"Se eliminaron {cantidad_borradas} de {len(ids)} compras. "
            f"{len(etiquetas_fallidas)} no se pudieron eliminar (ya fueron retiradas, recepcionadas "
            f'o marcadas "No ingresó"): '
            f"{', '.join(etiquetas_fallidas)}."
        )

    return _renderizar_pantalla_buscar_compras(request, fecha_desde, fecha_hasta, proveedor_id, articulo_id, aviso=aviso)


@app.get("/compras/{compra_id}/foto")
def ver_foto_compra(compra_id: int):
    """Genera una URL firmada nueva para la foto de esta compra y redirige ahí. 404 si no tiene foto guardada.

    No se guarda ni cachea la URL firmada en ningún lado: se pide una
    nueva cada vez que se aprieta "Ver foto", así nunca se puede llegar a
    un link vencido.
    """
    try:
        compra = obtener_compra(compra_id)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    if compra is None:
        raise HTTPException(status_code=404, detail="Compra no encontrada")

    fotos = _fotos_de_la_guia_de(compra)
    if not fotos:
        raise HTTPException(status_code=404, detail="Esta compra no tiene fotos guardadas")

    try:
        url_firmada = obtener_url_foto(fotos[0]["foto_ruta"])
    except Exception as error_storage:
        raise HTTPException(
            status_code=500, detail=f"No se pudo generar el link de la foto: {error_storage}"
        ) from error_storage

    return RedirectResponse(url=url_firmada, status_code=307)


def _fotos_de_la_guia_de(compra: dict) -> list[dict]:
    """Las fotos de la guía de esta compra (lista vacía si la compra no tiene guía — no debería pasar tras la migración)."""
    if compra.get("guia_id") is None:
        return []
    try:
        return listar_fotos_de_guia(compra["guia_id"])
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db


def _url_vuelta_fotos(compra_id: int, volver: str, query_filtros: str) -> str:
    """A qué pantalla volver tras subir/borrar una foto: Editar (con sus filtros) o Detalle."""
    if volver == "detalle":
        return f"/compras/{compra_id}/detalle"
    base = f"/compras/{compra_id}/editar"
    return f"{base}?{query_filtros}" if query_filtros else base


@app.get("/compras/{compra_id}/fotos/{foto_id}/ver")
def ver_foto_de_guia(compra_id: int, foto_id: int):
    """URL firmada de UNA foto de la guía de esta compra (para las miniaturas y el toque para agrandar)."""
    try:
        compra = obtener_compra(compra_id)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db
    if compra is None:
        raise HTTPException(status_code=404, detail="Compra no encontrada")

    foto = next((f for f in _fotos_de_la_guia_de(compra) if f["id"] == foto_id), None)
    if foto is None:
        raise HTTPException(status_code=404, detail="Esa foto no es de la guía de esta compra")

    try:
        url_firmada = obtener_url_foto(foto["foto_ruta"])
    except Exception as error_storage:
        raise HTTPException(
            status_code=500, detail=f"No se pudo generar el link de la foto: {error_storage}"
        ) from error_storage
    return RedirectResponse(url=url_firmada, status_code=307)


@app.post("/compras/{compra_id}/fotos")
async def subir_foto_a_guia(
    request: Request,
    compra_id: int,
    archivo: UploadFile = File(...),
    volver: str = Form("editar"),
    query_filtros: str = Form(""),
):
    """Suma una foto o PDF a la GUÍA de esta compra. Nunca reemplaza: si ya había fotos, la nueva se agrega.

    Todo comprimido antes de subir (imagen: 1000px JPEG q60, el pipeline
    de comandas; PDF: páginas a imagen con comprimir_pdf) — nada de
    originales de varios MB en el bucket.
    """
    try:
        compra = obtener_compra(compra_id)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db
    if compra is None:
        raise HTTPException(status_code=404, detail="Compra no encontrada")
    if compra.get("guia_id") is None:
        raise HTTPException(status_code=400, detail="Esta compra no tiene guía asignada, no se le pueden colgar fotos")

    bytes_archivo = await archivo.read()
    if not bytes_archivo:
        raise HTTPException(status_code=400, detail="El archivo llegó vacío")

    nombre_archivo = (archivo.filename or "").lower()
    es_pdf = nombre_archivo.endswith(".pdf") or (archivo.content_type or "") == "application/pdf"
    try:
        if es_pdf:
            foto_ruta = subir_archivo_comanda(
                comprimir_pdf(bytes_archivo), f"guia-{compra['guia_id']}", "pdf", "application/pdf"
            )
        else:
            comprimida = _comprimir_foto_jpeg(bytes_archivo)
            if comprimida is None:
                raise HTTPException(status_code=400, detail="El archivo no es una imagen legible (ni un PDF)")
            foto_ruta = subir_foto_comanda(comprimida, f"guia-{compra['guia_id']}")
    except HTTPException:
        raise
    except Exception as error_storage:
        raise HTTPException(
            status_code=500, detail=f"No se pudo subir el archivo al Storage: {error_storage}"
        ) from error_storage

    try:
        agregar_foto_guia(compra["guia_id"], foto_ruta)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    return RedirectResponse(url=_url_vuelta_fotos(compra_id, volver, query_filtros), status_code=303)


@app.post("/compras/{compra_id}/fotos/{foto_id}/borrar")
def borrar_foto_de_guia_ruta(
    request: Request,
    compra_id: int,
    foto_id: int,
    volver: str = Form("editar"),
    query_filtros: str = Form(""),
):
    """Borra una foto subida por error. El archivo del Storage solo se va si ninguna otra guía lo usa."""
    try:
        compra = obtener_compra(compra_id)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db
    if compra is None:
        raise HTTPException(status_code=404, detail="Compra no encontrada")

    # Solo fotos de la guía de ESTA compra: un id ajeno no borra nada.
    if next((f for f in _fotos_de_la_guia_de(compra) if f["id"] == foto_id), None) is None:
        raise HTTPException(status_code=404, detail="Esa foto no es de la guía de esta compra")

    try:
        ruta_a_borrar = borrar_foto_guia(foto_id)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    if ruta_a_borrar:
        try:
            borrar_foto_comanda(ruta_a_borrar)
        except Exception:
            logger.exception(
                "No se pudo borrar del Storage la foto %s (el registro ya se sacó de la guía igual)", ruta_a_borrar
            )

    return RedirectResponse(url=_url_vuelta_fotos(compra_id, volver, query_filtros), status_code=303)


@app.get("/compras/{compra_id}/detalle")
def ver_detalle_compra(request: Request, compra_id: int, aviso: str | None = None):
    """Historia completa de una compra: carga, retiro y recepción. Solo lectura, no se edita nada acá.

    aviso viene de /compras/{id}/corregir-recepcion tras guardar una
    corrección — la edición en sí vive en esa otra pantalla.
    """
    try:
        compra = obtener_detalle_compra(compra_id)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    if compra is None:
        raise HTTPException(status_code=404, detail="Compra no encontrada")

    diferencia_cajones_retirados = None
    if compra["cantidad_cajones_retirada"] is not None:
        diferencia_cajones_retirados = compra["cantidad_cajones_retirada"] - compra["cantidad_cajones"]

    diferencia_cajones_recepcion = None
    diferencia_contenido_recepcion = None
    if compra["cantidad_cajones_real"] is not None:
        diferencia_cajones_recepcion = compra["cantidad_cajones_real"] - compra["cantidad_cajones"]
    if compra["contenido_por_cajon_real"] is not None:
        diferencia_contenido_recepcion = compra["contenido_por_cajon_real"] - compra["contenido_por_cajon"]

    return templates.TemplateResponse(
        request,
        "compra_detalle.html",
        {
            "compra": compra,
            "fotos_guia": _fotos_de_la_guia_de(compra),
            "estado_retiro_label": ESTADOS_RETIRO_LABELS.get(compra["estado_retiro"], compra["estado_retiro"]),
            "estado_recepcion_label": ESTADOS_RECEPCION_LABELS.get(compra["estado"], compra["estado"]),
            "origen_retiro_label": ORIGENES_RETIRO_LABELS.get(compra["retiro_origen"], compra["retiro_origen"]),
            "diferencia_cajones_retirados": diferencia_cajones_retirados,
            "diferencia_cajones_recepcion": diferencia_cajones_recepcion,
            "diferencia_contenido_recepcion": diferencia_contenido_recepcion,
            "aviso": aviso,
        },
    )


def _renderizar_pantalla_corregir_recepcion(
    request: Request, compra_id: int, *, error: str | None = None, aviso=None,
    precarga=None, status_code: int = 200
):
    try:
        compra = obtener_detalle_compra(compra_id)
        # La lista va ARRIBA del formulario y ANTES de escribir nada: el que
        # corrige tiene que decidir qué número poner, y eso depende de qué se
        # llevó el lote.
        dependencias = dependencias_del_lote_de_compra(compra_id) if compra else None
        clientes = {c["id"]: c["nombre"] for c in listar_clientes()} if dependencias else {}
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    if compra is None:
        raise HTTPException(status_code=404, detail="Compra no encontrada")

    if dependencias:
        for renglon in dependencias["renglones"]:
            renglon["cliente_nombre"] = clientes.get(renglon["cliente_id"], "Sin cliente")

    return templates.TemplateResponse(
        request,
        "compra_corregir_recepcion.html",
        {"compra": compra, "error": error, "dependencias": dependencias,
         "aviso": aviso, "precarga": precarga or {}},
        status_code=status_code,
    )


@app.get("/compras/{compra_id}/corregir-recepcion")
def ver_corregir_recepcion_url_vieja(compra_id: int):
    """La URL vieja: la pantalla se mudó a Gerencia, detrás de la clave.

    Redirige en vez de romper, igual que /gerencia/auditoria cuando la
    Auditoría se mudó a su sector propio: un link guardado en el celular de
    alguien no puede terminar en un 404.
    """
    return RedirectResponse(url=f"/gerencia/compras/{compra_id}/corregir-recepcion", status_code=301)


@app.get("/gerencia/compras/{compra_id}/corregir-recepcion")
def ver_corregir_recepcion_compra(request: Request, compra_id: int):
    """Formulario para corregir los valores reales de una compra ya recepcionada (ej. error de tipeo en Depósito).

    VIVE EN GERENCIA, y tiene que vivir acá: la cookie de la clave se emite
    con path="/gerencia", así que en cualquier otra URL no viaja y la puerta
    no existiría. La zona es la del manejo de la plata porque esto mueve la
    cotización del artículo y puede dejar sin explicación el costo congelado
    de una guía R — no es una pantalla de operación.

    Bloqueada la corrección en sí en corregir_recepcion_compra, pero la
    pantalla se muestra igual (con un aviso) si alguien llega acá con una
    compra que no está recepcionada — mismo criterio que el resto de la
    app: nunca una pantalla en blanco sin explicar por qué.
    """
    puerta = _puerta_de_gerencia_para_escribir(request)
    if puerta is not None:
        return puerta
    return _renderizar_pantalla_corregir_recepcion(request, compra_id)


@app.post("/gerencia/compras/{compra_id}/corregir-recepcion")
def corregir_recepcion_compra_ruta(
    request: Request,
    compra_id: int,
    cantidad_cajones_real: str = Form(""),
    cantidad_total_real: str = Form(""),
    cantidad_cajones_rechazada: str = Form(""),
    motivo_rechazo: str = Form(""),
    confirmado: str = Form(""),
):
    puerta = _puerta_de_gerencia_para_escribir(request)
    if puerta is not None:
        return puerta

    error, cajones_valor = _validar_cantidad_cajones_real(cantidad_cajones_real)
    if not error:
        error, valor_real = _validar_valor_real_recepcion(cantidad_total_real)

    # El rechazo parcial es opcional acá: vacío = sin rechazo (y borra uno
    # mal cargado). Los cajones reales de arriba ya son los ACEPTADOS, así
    # que no hay tope que validar contra ellos.
    cajones_rechazados = None
    texto_rechazada = cantidad_cajones_rechazada.strip()
    if not error and texto_rechazada:
        try:
            cajones_rechazados = float(texto_rechazada)
        except ValueError:
            error = "La cantidad de bultos rechazados tiene que ser un número."
        else:
            if cajones_rechazados <= 0:
                error = "La cantidad de bultos rechazados tiene que ser mayor a cero (o dejala vacía si no hubo rechazo)."

    if error:
        return _renderizar_pantalla_corregir_recepcion(request, compra_id, error=error, status_code=400)

    # EL SEGUNDO TOQUE, y solo cuando algo se rompe de verdad. Se simula el
    # reparto con el número nuevo: si no queda ningún bulto sin lote ni
    # ninguna guía R sin poder reconstruirse, guarda de una. Un cartel que
    # aparece igual se deja de leer, y entonces no sirve el día que importa.
    if not confirmado.strip():
        try:
            impacto = dependencias_del_lote_de_compra(compra_id, nueva_cantidad=cajones_valor)
        except Exception as error_db:
            raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db
        if impacto and (impacto["sin_lote_de_mas"] > 0 or impacto["guias_rotas"]):
            return _renderizar_pantalla_corregir_recepcion(
                request,
                compra_id,
                aviso={
                    "sin_lote_de_mas": _formatear_numero(impacto["sin_lote_de_mas"]),
                    "guias_rotas": impacto["guias_rotas"],
                    "entraron": _formatear_numero(impacto["entraron"]),
                    "nueva": _formatear_numero(cajones_valor),
                },
                precarga={
                    "cantidad_cajones_real": cantidad_cajones_real,
                    "cantidad_total_real": cantidad_total_real,
                    "cantidad_cajones_rechazada": cantidad_cajones_rechazada,
                    "motivo_rechazo": motivo_rechazo,
                },
                status_code=400,
            )

    try:
        corregir_recepcion_compra(
            compra_id,
            cajones_valor,
            valor_real,
            cantidad_cajones_rechazada=cajones_rechazados,
            motivo_rechazo=(motivo_rechazo.strip() or None) if cajones_rechazados is not None else None,
        )
    except ValueError as error_bloqueo:
        return _renderizar_pantalla_corregir_recepcion(
            request, compra_id, error=str(error_bloqueo), status_code=400
        )
    except Exception as error_db:
        return _renderizar_pantalla_corregir_recepcion(
            request, compra_id, error=f"No se pudo guardar la corrección: {error_db}", status_code=500
        )

    parametros = urlencode({"aviso": "Se corrigió la recepción de esta compra."})
    return RedirectResponse(url=f"/compras/{compra_id}/detalle?{parametros}", status_code=303)


@app.get("/compras/pendientes")
def ver_compras_pendientes(request: Request, error: str | None = None):
    try:
        compras = listar_compras_sin_precio()
    except Exception as error_db:
        return templates.TemplateResponse(
            request,
            "compras_pendientes.html",
            {"compras": [], "error": f"No se pudieron leer las compras pendientes: {error_db}"},
            status_code=500,
        )

    return templates.TemplateResponse(request, "compras_pendientes.html", {"compras": compras, "error": error})


@app.post("/compras/pendientes/{compra_id}/importe")
def completar_importe_compra(request: Request, compra_id: int, importe: str = Form("")):
    error, importe_valor = _validar_importe_pendiente(importe)

    if error:
        try:
            compras = listar_compras_sin_precio()
        except Exception:
            compras = []
        return templates.TemplateResponse(
            request,
            "compras_pendientes.html",
            {"compras": compras, "error": error},
            status_code=400,
        )

    try:
        actualizar_importe_compra(compra_id, importe_valor)
    except Exception as error_db:
        try:
            compras = listar_compras_sin_precio()
        except Exception:
            compras = []
        return templates.TemplateResponse(
            request,
            "compras_pendientes.html",
            {"compras": compras, "error": f"No se pudo guardar el importe: {error_db}"},
            status_code=500,
        )

    return RedirectResponse(url="/compras/pendientes", status_code=303)


@app.post("/compras/pendientes/guardar-todos")
async def completar_importes_pendientes(request: Request):
    form = await request.form()

    try:
        compras = listar_compras_sin_precio()
    except Exception as error_db:
        return templates.TemplateResponse(
            request,
            "compras_pendientes.html",
            {"compras": [], "error": f"No se pudieron leer las compras pendientes: {error_db}"},
            status_code=500,
        )

    actualizaciones = []
    error = None
    for compra in compras:
        texto = str(form.get(f"importe_{compra['id']}", "")).strip()
        if not texto:
            continue

        error_campo, importe_valor = _validar_importe_pendiente(texto)
        if error_campo:
            error = f"{compra['articulo_nombre']} ({compra['proveedor_nombre']}): {error_campo}"
            break

        actualizaciones.append((compra["id"], importe_valor))

    if not error and not actualizaciones:
        error = "Cargá al menos un importe para guardar."

    if error:
        return templates.TemplateResponse(
            request,
            "compras_pendientes.html",
            {"compras": compras, "error": error},
            status_code=400,
        )

    try:
        for compra_id, importe_valor in actualizaciones:
            actualizar_importe_compra(compra_id, importe_valor)
    except Exception as error_db:
        try:
            compras = listar_compras_sin_precio()
        except Exception:
            compras = []
        return templates.TemplateResponse(
            request,
            "compras_pendientes.html",
            {"compras": compras, "error": f"No se pudo guardar el importe: {error_db}"},
            status_code=500,
        )

    return RedirectResponse(url="/compras/pendientes", status_code=303)


def _calcular_cuadro_negociacion(cliente: dict, cliente_id: int, fichas_cliente: list[dict]) -> dict:
    """Arma el contexto del cuadro de negociación (Bajas, Subas, bajo objetivo, todos) de un cliente.

    Usa exactamente los mismos datos que calcular_listado_para_negociar_precios
    (vía agrupar_para_negociar) — no recalcula nada, solo los agrupa y
    ordena distinto para negociar rápido. Con los precios YA VIGENTES
    (guardados): quien llama a esto lo hace para ver el estado "oficial"
    de la negociación, no una proyección con cambios todavía sin guardar
    en otra pantalla (ver el panel "Ver negociación" de /precios/cargar).
    """
    momento_referencia = datetime.now(ARGENTINA)
    articulos = calcular_listado_para_negociar_precios(cliente_id, momento_referencia)

    utilidad_objetivo_cliente = (
        cliente["utilidad_objetivo"] / 100 if cliente["utilidad_objetivo"] is not None else None
    )
    grupos = agrupar_para_negociar(articulos, utilidad_objetivo_cliente)

    # Artículos frescos (compra dentro de las últimas 48 hs, la ventana que
    # alimenta este cuadro) que tienen alguna compra sin precio de compra
    # cargado todavía: el costo/margen de ESE artículo puede estar
    # calculado con datos incompletos. Se avisa con nombre y todo para que
    # se sepa a cuáles no conviene creerles el número a ciegas.
    articulos_con_precio_sin_cerrar = sorted(
        {a["articulo_nombre"] for a in articulos if a["fresco"] and a["compras_sin_precio_excluidas"] > 0}
    )

    return {
        "cliente_nombre": cliente["nombre"],
        "fecha_referencia": momento_referencia.strftime("%d/%m/%Y %H:%M"),
        "bajas": grupos["bajas"],
        "subas": grupos["subas"],
        "bajo_objetivo": grupos["bajo_objetivo"],
        "todos": grupos["todos"],
        "utilidad_objetivo_cliente": utilidad_objetivo_cliente,
        "articulos_con_precio_sin_cerrar": articulos_con_precio_sin_cerrar,
        # Para explicar por qué no hay nada, en vez de mostrar la
        # pantalla vacía sin avisar (ver templates/_cuadro_negociacion.html):
        # sin ninguna ficha, calcular_listado_para_negociar_precios
        # nunca puede devolver nada; con fichas pero sin ningún
        # artículo con compra en los últimos 15 días, tampoco.
        "sin_fichas": len(fichas_cliente) == 0,
        "sin_articulos_recientes": len(fichas_cliente) > 0 and len(articulos) == 0,
    }


@app.get("/compras/objetivo")
def ver_objetivo_de_compra(request: Request, cliente_id: int | None = None):
    """Objetivo de Compra: el techo de compra por artículo para llegar a la utilidad objetivo del cliente.

    Mismo patrón de selector que /negociar: sin cliente_id, solo el
    selector; al elegir uno se recarga con ?cliente_id=N y se calcula.
    El recálculo al editar el kilaje es 100%% del lado del navegador (los
    números de cada tarjeta viajan en atributos data-), sin volver al server.
    """
    try:
        clientes = listar_clientes()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    if cliente_id is None:
        return templates.TemplateResponse(request, "objetivo_compra.html", {"clientes": clientes, "cliente_id": None})

    cliente = next((c for c in clientes if c["id"] == cliente_id), None)
    if cliente is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    try:
        objetivos = calcular_objetivos_de_compra(cliente_id)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al calcular los objetivos: {error_db}") from error_db

    return templates.TemplateResponse(
        request,
        "objetivo_compra.html",
        {
            "clientes": clientes,
            "cliente_id": cliente_id,
            "cliente": cliente,
            "articulos": objetivos["articulos"],
            "sin_precio_vigente": objetivos["sin_precio_vigente"],
            "sin_ficha": objetivos["sin_ficha"],
            "utilidad_objetivo": objetivos["utilidad_objetivo"],
        },
    )


@app.get("/negociar")
def ver_cuadro_negociar_precios(request: Request, cliente_id: int | None = None):
    """Cuadro para negociar precios (Bajas, Subas y artículos bajo la utilidad objetivo) de UN cliente elegido.

    Mismo patrón de selector que /fichas: sin cliente_id en la URL, se
    muestra solo el selector; al elegir uno, se recarga con ?cliente_id=N
    y ahí se calcula.
    """
    try:
        clientes = listar_clientes()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    if cliente_id is None:
        return templates.TemplateResponse(request, "negociar.html", {"clientes": clientes, "cliente_id": None})

    cliente = next((c for c in clientes if c["id"] == cliente_id), None)
    if cliente is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    try:
        fichas_cliente = listar_fichas_por_cliente(cliente_id)
        contexto_negociacion = _calcular_cuadro_negociacion(cliente, cliente_id, fichas_cliente)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al calcular el costeo: {error_db}") from error_db

    return templates.TemplateResponse(
        request,
        "negociar.html",
        {
            "clientes": clientes,
            "cliente_id": cliente_id,
            **contexto_negociacion,
        },
    )


def _id_opcional_desde_query(valor: str | None) -> int | None:
    """Convierte un id opcional de query string a int, sin romper si viene vacío o no numérico.

    FastAPI declarado como "int | None" rechaza con un 422 crudo un
    query param presente pero vacío (ej. "articulo_id=", que manda el
    <select> "Todos los artículos" al no elegir ninguno) — Pydantic
    intenta parsear "" como int y explota antes de llegar acá. Recibiendo
    el valor como texto y convirtiéndolo acá, "" o cualquier cosa no
    numérica se trata como "no vino nada", nunca como error.
    """
    if not valor:
        return None
    try:
        return int(valor)
    except ValueError:
        return None


@app.get("/precios")
def ver_precios(request: Request, guardado: str | None = None, listado: str | None = None):
    """Botonera de Lista de Precios: Consultar, Cargar Precios Nuevos, Generar Listado (Próximamente).

    "guardado" llega desde el redirect de POST /precios/cargar (o de
    "Guardar y generar listado", en /precios/cargar/guardar-y-exportar-*)
    con la cantidad de precios que efectivamente se guardaron (puede ser
    menos que los pendientes cargados, si alguno quedó igual al vigente y
    no generó fila nueva), para mostrar un mensaje de confirmación acá.
    "listado" viene solo desde "Guardar y generar listado", para dejar en
    claro que además del guardado se generó el PDF/Excel.
    """
    cantidad_guardada = _id_opcional_desde_query(guardado)
    mensaje = None
    if cantidad_guardada is not None:
        if listado:
            mensaje = (
                f"Se guardaron {cantidad_guardada} precios y se generó el listado."
                if cantidad_guardada > 0
                else "Los precios ya estaban al día — se generó el listado igual."
            )
        else:
            mensaje = (
                f"Se cargaron {cantidad_guardada} precios."
                if cantidad_guardada > 0
                else "No se guardó ningún cambio: los precios ya estaban al día."
            )
    return templates.TemplateResponse(request, "precios.html", {"mensaje": mensaje})


@app.get("/precios/consultar")
def ver_precios_consultar(request: Request, cliente_id: str | None = None, fecha: str | None = None, ficha_id: str | None = None):
    """Consulta de precios vigentes de un cliente a una fecha (todos, o uno puntual). Solo lectura.

    Mismo patrón de selector que /fichas y /negociar: sin cliente_id en la
    URL, se muestra solo el selector. "Vigente a una fecha" usa
    listar_precios_vigentes_por_cliente tal cual (mismo patrón vigente_desde
    que ya usa la Rutina A) — acá solo se cruza con las FICHAS del cliente
    para mostrar el nombre y, si se pidió, filtrar a una puntual. Se filtra
    por ficha y no por artículo porque es la ficha la que tiene precio: con
    dos del mismo artículo, filtrar por artículo devolvía las dos juntas y
    las dos se llamaban igual en pantalla.
    """
    cliente_id = _id_opcional_desde_query(cliente_id)
    ficha_id = _id_opcional_desde_query(ficha_id)

    try:
        clientes = listar_clientes()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    if cliente_id is None:
        return templates.TemplateResponse(request, "precios_consulta.html", {"clientes": clientes, "cliente_id": None})

    cliente = next((c for c in clientes if c["id"] == cliente_id), None)
    if cliente is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    fecha_error = None
    fecha_consulta = _hoy_argentina()
    if fecha:
        try:
            fecha_consulta = date.fromisoformat(fecha)
        except ValueError:
            fecha_error = "La fecha no es válida."

    try:
        fichas = listar_fichas_por_cliente(cliente_id)
        precios_vigentes = listar_precios_vigentes_por_cliente(cliente_id, fecha_consulta)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    # El nombre que se muestra es el de la FICHA: con dos del mismo artículo
    # ("Anco" y "Anco Ecuador"), el del catálogo repetiría el mismo texto en
    # los dos renglones y no habría cómo saber cuál es cuál.
    ficha_por_id = {ficha["id"]: ficha for ficha in fichas}
    filas = [
        {
            "articulo_id": precio["articulo_id"],
            "ficha_id": precio["ficha_id"],
            "articulo_nombre": (
                _nombre_de_ficha(ficha_por_id[precio["ficha_id"]])
                if precio["ficha_id"] in ficha_por_id
                else f"Artículo #{precio['articulo_id']}"
            ),
            "precio": precio["precio"],
            # Mismo criterio que el PDF y el Excel: empezó a regir en la
            # fecha consultada. Sirve para facturar — si venía todo igual y
            # algo cambió ese día, se ve sin comparar contra la lista anterior.
            "es_nuevo": precio.get("vigente_desde") == fecha_consulta,
        }
        for precio in precios_vigentes
    ]
    if ficha_id is not None:
        filas = [fila for fila in filas if fila["ficha_id"] == ficha_id]
    filas.sort(key=lambda fila: fila["articulo_nombre"])

    return templates.TemplateResponse(
        request,
        "precios_consulta.html",
        {
            "clientes": clientes,
            "cliente_id": cliente_id,
            "cliente_nombre": cliente["nombre"],
            "fichas_cliente": [{"ficha_id": f["id"], "nombre": _nombre_de_ficha(f)} for f in fichas],
            "ficha_id": ficha_id,
            "ficha_nombre_actual": _nombre_de_ficha(ficha_por_id[ficha_id]) if ficha_id in ficha_por_id else None,
            "fecha": fecha_consulta.isoformat(),
            "fecha_mostrar": fecha_consulta.strftime("%d/%m/%Y"),
            "fecha_error": fecha_error,
            "filas": filas,
        },
    )


def _armar_filas_exportacion_precios(cliente_id: int, fecha_consulta) -> tuple[list[dict], bool]:
    """Arma las filas para exportar (PDF/Excel) la lista de precios de un cliente a una fecha.

    Reusa exactamente los mismos datos que ya arma /precios/consultar
    (fichas para nombre/unidad, precios vigentes, catálogo para el grupo)
    — no calcula nada nuevo. es_nuevo es "este precio EMPEZÓ A REGIR en la
    fecha consultada" (vigente_desde == fecha_consulta), y vale igual para
    hoy que para una fecha pasada: consultar el 20 tiene que mostrar lo que
    cambió el 20, que es justo para lo que se consulta para atrás.
    es_hoy queda solo para el encabezado del Excel ("Precio Desde HOY" vs
    "Precio al dd/mm"), que sí depende de si la fecha es la de hoy.
    precio_anterior (ver listar_precios_anteriores_por_cliente) solo lo usa
    la columna "Precio anterior" del Excel (el PDF no la muestra) — un
    artículo sin precio anterior cargado queda en None.
    """
    fichas = listar_fichas_por_cliente(cliente_id)
    precios_vigentes = listar_precios_vigentes_por_cliente(cliente_id, fecha_consulta)
    precios_anteriores = listar_precios_anteriores_por_cliente(cliente_id, fecha_consulta)
    articulos_existentes = listar_articulos()

    # La lista exportada es para mandarle al cliente — usa el nombre que el
    # cliente conoce (nombre_cliente de su ficha), no el nombre interno del
    # catálogo. Si la ficha no tiene nombre_cliente cargado, se cae al
    # nombre del catálogo como respaldo.
    nombre_por_articulo = {
        ficha["articulo_id"]: ficha.get("nombre_cliente") or ficha["articulo_nombre"] for ficha in fichas
    }
    unidad_por_articulo = {ficha["articulo_id"]: ficha.get("unidad_venta") for ficha in fichas}
    grupo_por_articulo = {articulo["id"]: articulo.get("grupo") for articulo in articulos_existentes}
    precio_anterior_por_articulo = {precio["articulo_id"]: precio["precio"] for precio in precios_anteriores}

    es_hoy = fecha_consulta == _hoy_argentina()

    filas = [
        {
            "articulo_nombre": nombre_por_articulo.get(precio["articulo_id"], f"Artículo #{precio['articulo_id']}"),
            "grupo": grupo_por_articulo.get(precio["articulo_id"]),
            "precio": precio["precio"],
            "precio_anterior": precio_anterior_por_articulo.get(precio["articulo_id"]),
            "unidad": unidad_por_articulo.get(precio["articulo_id"]),
            "es_nuevo": precio.get("vigente_desde") == fecha_consulta,
        }
        for precio in precios_vigentes
    ]
    return filas, es_hoy


def _validar_cliente_y_fecha_para_exportar(cliente_id_texto: str, fecha_texto: str) -> tuple[dict, date]:
    """Valida cliente_id y fecha para las rutas de exportación. Los links solo los arma la propia pantalla
    con valores ya válidos, así que un error acá es un caso de URL manipulada a mano, no un uso normal —
    alcanza con HTTPException (mismo criterio que el resto de las rutas de confirmación de esta app).
    """
    try:
        cliente_id = int(cliente_id_texto)
    except ValueError:
        raise HTTPException(status_code=400, detail="Cliente inválido")

    try:
        clientes = listar_clientes()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    cliente = next((c for c in clientes if c["id"] == cliente_id), None)
    if cliente is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    try:
        fecha_valor = date.fromisoformat(fecha_texto)
    except ValueError:
        raise HTTPException(status_code=400, detail="Fecha inválida")

    return cliente, fecha_valor


def _nombre_archivo_exportacion(cliente_nombre: str, fecha, extension: str) -> str:
    # Con más de una empresa mandándole listas al mismo cliente, el nombre
    # del archivo tiene que decir de cuál es — igual que el encabezado.
    base = re.sub(r"[^A-Za-z0-9]+", "_", cliente_nombre).strip("_") or "cliente"
    return f"Lista_Precios_{_nombre_empresa_para_archivo()}_{base}_{fecha.isoformat()}.{extension}"


@app.get("/precios/consultar/exportar-pdf")
def exportar_precios_pdf(cliente_id: str = "", fecha: str = ""):
    """Genera la Lista de Precios en PDF y la devuelve para descargar — no se guarda en ningún lado."""
    cliente, fecha_valor = _validar_cliente_y_fecha_para_exportar(cliente_id, fecha)

    try:
        filas, _ = _armar_filas_exportacion_precios(cliente["id"], fecha_valor)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    pdf_bytes = generar_pdf_lista_precios(cliente["nombre"], fecha_valor, filas, NOMBRE_EMPRESA)
    nombre_archivo = _nombre_archivo_exportacion(cliente["nombre"], fecha_valor, "pdf")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'},
    )


@app.get("/precios/consultar/exportar-excel")
def exportar_precios_excel(cliente_id: str = "", fecha: str = ""):
    """Genera la Lista de Precios en Excel y la devuelve para descargar — no se guarda en ningún lado."""
    cliente, fecha_valor = _validar_cliente_y_fecha_para_exportar(cliente_id, fecha)

    try:
        filas, es_hoy = _armar_filas_exportacion_precios(cliente["id"], fecha_valor)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    excel_bytes = generar_excel_lista_precios(cliente["nombre"], fecha_valor, filas, es_hoy, NOMBRE_EMPRESA)
    nombre_archivo = _nombre_archivo_exportacion(cliente["nombre"], fecha_valor, "xlsx")

    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'},
    )


def _respuesta_listado_generado(cliente: dict, cambios: list[dict], tipo: str) -> Response:
    """Genera el PDF/Excel de la Lista de Precios ya guardada (precios vigentes de HOY, con lo que se
    acaba de guardar resaltado en rojo — mismo criterio que /precios/consultar) y lo devuelve como
    adjunto. Se usa desde "Guardar y generar listado": primero se guarda de verdad (ver
    _guardar_pendientes_carga_manual / _guardar_pendientes_carga_foto), y esto arma el archivo con lo
    recién guardado — no hay pendientes de por medio, así que reusa _armar_filas_exportacion_precios tal
    cual, sin necesidad de superponer nada.

    La cantidad guardada viaja en el header X-Cantidad-Guardada (no en el cuerpo, que es el archivo) —
    la pantalla que llama la usa para armar el mensaje al volver a /precios después de descargar.
    """
    hoy = _hoy_argentina()
    try:
        filas, es_hoy = _armar_filas_exportacion_precios(cliente["id"], hoy)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    if tipo == "pdf":
        archivo_bytes = generar_pdf_lista_precios(cliente["nombre"], hoy, filas, NOMBRE_EMPRESA)
        media_type = "application/pdf"
        extension = "pdf"
    else:
        archivo_bytes = generar_excel_lista_precios(cliente["nombre"], hoy, filas, es_hoy, NOMBRE_EMPRESA)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        extension = "xlsx"

    nombre_archivo = _nombre_archivo_exportacion(cliente["nombre"], hoy, extension)
    return Response(
        content=archivo_bytes,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{nombre_archivo}"',
            "X-Cantidad-Guardada": str(len(cambios)),
        },
    )


def _nombre_de_ficha(ficha: dict) -> str:
    """El nombre con el que EL CLIENTE conoce este producto, cayendo al del catálogo.

    Es lo que distingue dos fichas del mismo artículo: "Banana Bolivia" y
    "Banana Ecuador" son las dos el artículo Banana, y mostrar "Banana" en
    las dos dejaría al que arma sin saber qué caja usar. La ficha sin
    nombre propio cargado se sigue mostrando con el nombre del catálogo,
    igual que siempre.
    """
    return (ficha.get("nombre_cliente") or "").strip() or ficha["articulo_nombre"]


def _validar_precios(filas: list[dict]) -> tuple[str | None, list[dict]]:
    """Valida cada precio tipeado (número positivo) y arma las filas para calcular_cambios_de_precios."""
    filas_validas = []
    for fila in filas:
        precio_original = float(fila["original_texto"]) if fila["original_texto"] else None

        precio_nuevo = None
        if fila["nuevo_texto"]:
            try:
                precio_nuevo = float(fila["nuevo_texto"])
            except ValueError:
                return f'El precio de "{fila["articulo_nombre"]}" tiene que ser un número.', []
            if precio_nuevo <= 0:
                return f'El precio de "{fila["articulo_nombre"]}" tiene que ser mayor a 0.', []

        filas_validas.append(
            {"ficha_id": fila["ficha_id"], "precio_original": precio_original, "precio_nuevo": precio_nuevo}
        )
    return None, filas_validas


@app.get("/precios/cargar")
def ver_cargar_precios(request: Request, cliente_id: str | None = None):
    """Carga de precios nuevos de un cliente, uno a la vez, con revisión antes de guardar.

    Trae el catálogo completo del cliente (artículo + precio vigente de
    hoy) y lo embebe en la página como para que elegir artículos y armar
    la lista de pendientes no necesite volver a pedirle nada al servidor
    — recién se vuelve a pegarle al servidor una sola vez, al guardar en
    la pantalla de revisión (ver POST /precios/cargar).
    """
    cliente_id = _id_opcional_desde_query(cliente_id)

    try:
        clientes = listar_clientes()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    if cliente_id is None:
        return templates.TemplateResponse(request, "precios_cargar.html", {"clientes": clientes, "cliente_id": None})

    cliente = next((c for c in clientes if c["id"] == cliente_id), None)
    if cliente is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    try:
        fichas = listar_fichas_por_cliente(cliente_id)
        precios_vigentes = listar_precios_vigentes_por_cliente(cliente_id, _hoy_argentina())
        # El panel "Ver negociación" muestra el estado oficial (con los
        # precios ya guardados), calculado una sola vez acá al cargar la
        # pantalla — no se recalcula con los pendientes sin guardar.
        contexto_negociacion = _calcular_cuadro_negociacion(cliente, cliente_id, fichas)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    # El precio cuelga de la FICHA: dos fichas del mismo artículo tienen
    # su propio precio, y buscarlo por artículo devolvería cualquiera de
    # los dos.
    precio_por_ficha = {precio["ficha_id"]: precio["precio"] for precio in precios_vigentes}
    # Datos que necesita el recuadro "Simulación" (ver precios_cargar.html)
    # para calcular la rentabilidad de un precio cualquiera sin volver a
    # pedirle nada al servidor — solo existen para los artículos con costo
    # reciente (los mismos que ya trae contexto_negociacion["todos"]).
    simulacion_por_articulo = {
        articulo["articulo_id"]: {
            "costo_producto_unidad_venta": articulo["costo_actual"],
            "costo_envase_unidad_venta": articulo["costo_envase_unidad_venta"],
            "denominador_tasas": articulo["denominador_tasas"],
        }
        for articulo in contexto_negociacion["todos"]
        if articulo["costo_actual"] is not None
    }
    # La lista de la pantalla es de FICHAS, no de artículos: se carga el
    # precio de "Banana Ecuador", no el de "Banana". El costo, en cambio,
    # sigue siendo del artículo (se compró una sola banana), así que la
    # simulación se busca por articulo_id — las dos fichas comparten costo
    # y cada una tiene su precio.
    fichas_cliente = [
        {
            "ficha_id": ficha["id"],
            "articulo_id": ficha["articulo_id"],
            "nombre": _nombre_de_ficha(ficha),
            "precio_vigente": precio_por_ficha.get(ficha["id"]),
            **simulacion_por_articulo.get(
                ficha["articulo_id"],
                {"costo_producto_unidad_venta": None, "costo_envase_unidad_venta": None, "denominador_tasas": None},
            ),
        }
        for ficha in fichas
    ]

    return templates.TemplateResponse(
        request,
        "precios_cargar.html",
        {
            "clientes": clientes,
            "cliente_id": cliente_id,
            "fichas_cliente": fichas_cliente,
            **contexto_negociacion,
        },
    )


def _leer_pendientes_del_form(form) -> list[dict]:
    """Lee del form oculto (armado por JS con los pendientes de la sesión) un precio nuevo por FICHA.

    Cada pendiente viaja como "pendiente_precio_<ficha_id>" (el nuevo) y
    "pendiente_original_<ficha_id>" (el vigente al elegirlo, para que
    calcular_cambios_de_precios no genere una fila si no cambió nada) — no
    hace falta un índice porque los pendientes ya vienen sin duplicados por
    ficha (el navegador se encarga de eso).

    La clave es la ficha y no el artículo porque el precio es de la ficha:
    con "Banana Bolivia" y "Banana Ecuador" cargadas en la misma sesión,
    por artículo se pisaban entre ellas.
    """
    filas = []
    prefijo = "pendiente_precio_"
    for clave in form.keys():
        if not clave.startswith(prefijo):
            continue
        try:
            ficha_id = int(clave[len(prefijo) :])
        except ValueError:
            continue
        filas.append(
            {
                "ficha_id": ficha_id,
                "original_texto": str(form.get(f"pendiente_original_{ficha_id}", "")).strip(),
                "nuevo_texto": str(form.get(clave, "")).strip(),
            }
        )
    return filas


def _guardar_pendientes_carga_manual(form) -> tuple[dict, list[dict]]:
    """Valida y guarda los pendientes de Carga Manual (mismo form que ya arma precios_cargar.html al
    guardar). Devuelve el cliente y los cambios efectivamente guardados — lo usan tanto "Guardar" a
    secas como "Guardar y generar listado", que hacen lo mismo acá y después responden distinto.

    Un solo uso, carga puntual: se guarda tal cual lo que se cargó, sin
    revalidar contra lo que haya vigente en la base en este momento (no
    hace falta detectar conflictos para este caso de uso).
    """
    try:
        cliente_id = int(form.get("cliente_id", ""))
    except ValueError:
        raise HTTPException(status_code=400, detail="Cliente inválido")

    try:
        clientes = listar_clientes()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    cliente = next((c for c in clientes if c["id"] == cliente_id), None)
    if cliente is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    try:
        fichas = listar_fichas_por_cliente(cliente_id)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    ficha_por_id = {ficha["id"]: ficha for ficha in fichas}

    filas_crudas = _leer_pendientes_del_form(form)
    for fila in filas_crudas:
        ficha = ficha_por_id.get(fila["ficha_id"])
        fila["articulo_id"] = ficha["articulo_id"] if ficha else None
        fila["articulo_nombre"] = _nombre_de_ficha(ficha) if ficha else f"Ficha #{fila['ficha_id']}"
    # Una ficha que ya no es de este cliente (se borró mientras el
    # navegador tenía el pendiente cargado) se ignora en vez de romper.
    filas_crudas = [fila for fila in filas_crudas if fila["articulo_id"] is not None]

    error, filas_para_diff = _validar_precios(filas_crudas)
    if error:
        raise HTTPException(status_code=400, detail=error)

    cambios = calcular_cambios_de_precios(filas_para_diff)

    try:
        guardar_precios_cliente(cliente_id, cambios)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"No se pudieron guardar los precios: {error_db}") from error_db

    return cliente, cambios


@app.post("/precios/cargar")
async def cargar_precios(request: Request):
    """Guarda de una vez todos los pendientes cargados en el navegador durante la sesión."""
    form = await request.form()
    _cliente, cambios = _guardar_pendientes_carga_manual(form)
    return RedirectResponse(url=f"/precios?guardado={len(cambios)}", status_code=303)


@app.post("/precios/cargar/guardar-y-exportar-pdf")
async def guardar_y_exportar_precios_cargar_manual_pdf(request: Request):
    """Guarda los pendientes de Carga Manual y devuelve el PDF de la Lista de Precios ya actualizada."""
    form = await request.form()
    cliente, cambios = _guardar_pendientes_carga_manual(form)
    return _respuesta_listado_generado(cliente, cambios, "pdf")


@app.post("/precios/cargar/guardar-y-exportar-excel")
async def guardar_y_exportar_precios_cargar_manual_excel(request: Request):
    """Guarda los pendientes de Carga Manual y devuelve el Excel de la Lista de Precios ya actualizada."""
    form = await request.form()
    cliente, cambios = _guardar_pendientes_carga_manual(form)
    return _respuesta_listado_generado(cliente, cambios, "excel")


@app.get("/precios/generar-listado")
def ver_generar_listado_precios(request: Request):
    return _renderizar_en_construccion(
        request, "Generar Listado Actualizado", volver_url="/precios", volver_texto="Volver a Precios", sector="comercial"
    )


@app.get("/precios/resultado-negociacion")
def ver_resultado_negociacion(request: Request):
    """Rutina B: resultado de la negociación con el costo ESTIMADO de compra.

    Más adelante habrá otra versión de esto en Gerencia con el costo REAL
    depurado, cuando exista el módulo Depósito con los kilos pesados — esta
    de acá usa el costo estimado, por eso vive en Precios.

    REGLA FIJA para cuando se construya (pedida el 19/08/2026): para
    excluir compras de los cálculos de costos manda SOLO el veredicto de
    Depósito — quedan afuera las 'no_ingresado' y las 'rechazado' (no hay
    mercadería real detrás), y lo que diga Logística NO cuenta (un retiro
    cancelado no saca la compra del cálculo). Es el mismo criterio que ya
    aplica listar_compras_para_costeo: construir la Rutina B sobre esa
    función o sobre uno de sus derivados, nunca sobre una consulta nueva
    sin estos filtros.
    """
    return _renderizar_en_construccion(
        request, "Resultado Negociación", volver_url="/precios", volver_texto="Volver a Precios", sector="comercial"
    )


MIME_POR_TIPO_ARCHIVO_PRECIOS = {
    "foto": "image/jpeg",
    "pdf": "application/pdf",
    "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
EXTENSION_POR_TIPO_ARCHIVO_PRECIOS = {"foto": "jpg", "pdf": "pdf", "excel": "xlsx"}


def _detectar_tipo_archivo_precios(nombre_archivo: str) -> str | None:
    """Clasifica el archivo subido por su extensión: "foto", "pdf" o "excel" — None si no es ninguno de los tres."""
    nombre = (nombre_archivo or "").lower()
    if nombre.endswith((".jpg", ".jpeg", ".png")):
        return "foto"
    if nombre.endswith(".pdf"):
        return "pdf"
    if nombre.endswith(".xlsx"):
        return "excel"
    return None


def _generar_data_uri_generico(bytes_archivo: bytes, mime_type: str) -> str:
    """Arma un data URI con los bytes tal cual, sin comprimir — para PDF/Excel, que no tienen un Pillow equivalente."""
    datos_base64 = base64.standard_b64encode(bytes_archivo).decode("ascii")
    return f"data:{mime_type};base64,{datos_base64}"


def _extraer_listado_precios_de_archivo(bytes_archivo: bytes, tipo_archivo: str) -> dict:
    """Lee un listado de precios de un archivo según su tipo — un solo punto de entrada para los 3 formatos.

    Todos terminan en el mismo contrato JSON ({"items": [...]})  — foto y
    PDF (página por página, convertida a imagen) van por la IA en modo
    imagen; Excel (volcado a texto) va por la IA en modo texto. Cualquier
    error de conversión (core/lector_archivos.py) o de lectura con IA
    (core/lector_comandas.py) se propaga tal cual: quien llama es
    responsable de mostrarlo como un mensaje claro, no un error técnico.
    """
    if tipo_archivo == "foto":
        return extraer_listado_precios_de_imagenes([bytes_archivo])
    if tipo_archivo == "pdf":
        imagenes = imagenes_desde_pdf(bytes_archivo)
        return extraer_listado_precios_de_imagenes(imagenes)
    if tipo_archivo == "excel":
        texto = texto_desde_excel(bytes_archivo)
        return extraer_listado_precios_de_texto(texto)
    raise ValueError(f"Tipo de archivo no soportado: {tipo_archivo}")


def _armar_renglones_precios_desde_datos_leidos(
    datos: dict, fichas_cliente: list[dict], precio_por_ficha: dict
) -> list[dict]:
    """Arma los renglones sugeridos (FICHA matcheada + precio leído) a partir de lo que devolvió la IA.

    El match cae en una ficha, no en un artículo: el precio cuelga de la
    ficha, y "Banana Bolivia" y "Banana Ecuador" tienen el suyo. Los
    candidatos son las fichas de ESTE cliente, con el nombre que él usa
    (nombre_cliente) — el alias más preciso que existe, y el único que
    distingue dos fichas del mismo artículo. Sin ninguna ficha no hay nada
    que sugerir: el precio no tiene dónde colgar hasta que se cree una.

    Sin aprendizaje por cliente todavía (se pasa vacío) — el que existe hoy
    es por proveedor, para comandas.
    """
    conversiones_cliente = [
        {"nombre_cliente": f["nombre_cliente"], "articulo_id": f["id"]}
        for f in fichas_cliente
        if f.get("nombre_cliente")
    ]
    candidatos_ficha = [{"id": f["id"], "nombre": _nombre_de_ficha(f)} for f in fichas_cliente]

    renglones = []
    for item in datos.get("items") or []:
        texto_leido = item.get("articulo") or ""
        ficha_id_sugerida = adivinar_articulo(texto_leido, {}, candidatos_ficha, conversiones_cliente)
        renglones.append(
            {
                "texto_leido": texto_leido,
                "ficha_id": ficha_id_sugerida,
                "precio_original": precio_por_ficha.get(ficha_id_sugerida)
                if ficha_id_sugerida is not None
                else None,
                "precio_nuevo": _numero_o_none(item.get("precio")),
                "advertencia": item.get("confianza") == "baja" or ficha_id_sugerida is None,
                "descartado": False,
            }
        )
    return renglones


@app.get("/precios/cargar-foto")
def ver_cargar_foto_precios(request: Request, cliente_id: str | None = None):
    """Carga de precios a partir de un archivo (foto, PDF o Excel) leído por IA, con revisión antes de guardar."""
    cliente_id = _id_opcional_desde_query(cliente_id)

    try:
        clientes = listar_clientes()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    if cliente_id is None:
        return templates.TemplateResponse(request, "precios_cargar_foto.html", {"clientes": clientes, "cliente_id": None, "error": None})

    cliente = next((c for c in clientes if c["id"] == cliente_id), None)
    if cliente is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    return templates.TemplateResponse(
        request,
        "precios_cargar_foto.html",
        {"clientes": clientes, "cliente_id": cliente_id, "cliente_nombre": cliente["nombre"], "error": None},
    )


@app.post("/precios/cargar-foto")
async def leer_foto_precios(request: Request, cliente_id: str = Form(...), archivo: UploadFile = File(...)):
    cliente_id_valor = _id_opcional_desde_query(cliente_id)

    try:
        clientes = listar_clientes()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    cliente = next((c for c in clientes if c["id"] == cliente_id_valor), None) if cliente_id_valor is not None else None
    if cliente is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    tipo_archivo = _detectar_tipo_archivo_precios(archivo.filename or "")
    if tipo_archivo is None:
        return templates.TemplateResponse(
            request,
            "precios_cargar_foto.html",
            {
                "clientes": clientes,
                "cliente_id": cliente_id_valor,
                "cliente_nombre": cliente["nombre"],
                "error": "No se pudo reconocer el tipo de archivo. Subí una foto (jpg/png), un PDF o un Excel (.xlsx).",
            },
            status_code=400,
        )

    try:
        bytes_archivo = await archivo.read()
        datos = _extraer_listado_precios_de_archivo(bytes_archivo, tipo_archivo)
    except Exception as error_lector:
        return templates.TemplateResponse(
            request,
            "precios_cargar_foto.html",
            {
                "clientes": clientes,
                "cliente_id": cliente_id_valor,
                "cliente_nombre": cliente["nombre"],
                "error": f"No se pudo leer el archivo: {error_lector}",
            },
            status_code=500,
        )

    try:
        fichas_cliente = listar_fichas_por_cliente(cliente_id_valor)
        precios_vigentes = listar_precios_vigentes_por_cliente(cliente_id_valor, _hoy_argentina())
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    precio_por_ficha = {precio["ficha_id"]: precio["precio"] for precio in precios_vigentes}
    renglones = _armar_renglones_precios_desde_datos_leidos(datos, fichas_cliente, precio_por_ficha)

    if not renglones:
        return templates.TemplateResponse(
            request,
            "precios_cargar_foto.html",
            {
                "clientes": clientes,
                "cliente_id": cliente_id_valor,
                "cliente_nombre": cliente["nombre"],
                "error": "No se encontró ningún artículo con precio en el archivo. Probá con otra foto, o cargalo a mano.",
            },
            status_code=400,
        )

    if tipo_archivo == "foto":
        archivo_preview = _generar_preview_foto(bytes_archivo)
    else:
        # El PDF que viaja al form (y de ahí a Storage al confirmar) va
        # COMPRIMIDO: un escaneo de varios MB se guarda como imágenes de
        # ~100-150 KB por página. La lectura con IA ya se hizo arriba con
        # el original. El Excel queda tal cual (ya pesa poco).
        bytes_para_guardar = comprimir_pdf(bytes_archivo) if tipo_archivo == "pdf" else bytes_archivo
        archivo_preview = _generar_data_uri_generico(bytes_para_guardar, MIME_POR_TIPO_ARCHIVO_PRECIOS[tipo_archivo])

    # El select ofrece las FICHAS del cliente, con el nombre que él usa.
    # Antes, sin fichas, ofrecía el catálogo entero: se podía elegir un
    # artículo y al guardar no se guardaba nada en silencio, porque el
    # precio necesita una ficha donde colgar. Sin fichas ahora la lista va
    # vacía y la pantalla lo dice.
    fichas_para_select = [
        {
            "ficha_id": f["id"],
            "nombre": _nombre_de_ficha(f),
            "precio_vigente": precio_por_ficha.get(f["id"]),
        }
        for f in fichas_cliente
    ]

    return templates.TemplateResponse(
        request,
        "precios_revision_foto.html",
        {
            "cliente_id": cliente_id_valor,
            "cliente_nombre": cliente["nombre"],
            "fichas": fichas_para_select,
            "renglones": renglones,
            "tipo_archivo": tipo_archivo,
            "archivo_preview": archivo_preview,
            "nombre_archivo": archivo.filename,
            "error": None,
        },
    )


def _guardar_pendientes_carga_foto(form) -> tuple[dict, list[dict]]:
    """Valida y guarda los renglones de Carga Foto (mismo form que ya arma precios_revision_foto.html
    al guardar). Devuelve el cliente y los cambios efectivamente guardados — lo usan tanto "Guardar" a
    secas como "Guardar y generar listado".
    """
    try:
        cliente_id = int(form.get("cliente_id", ""))
    except ValueError:
        raise HTTPException(status_code=400, detail="Cliente inválido")

    try:
        clientes = listar_clientes()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    cliente = next((c for c in clientes if c["id"] == cliente_id), None)
    if cliente is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    try:
        cantidad_renglones = int(form.get("cantidad_renglones", "0"))
    except ValueError:
        cantidad_renglones = 0

    try:
        fichas = listar_fichas_por_cliente(cliente_id)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db
    ficha_por_id = {f["id"]: f for f in fichas}

    filas_crudas = []
    for indice in range(cantidad_renglones):
        if str(form.get(f"item_{indice}_descartar", "")).strip():
            continue
        ficha_id_texto = str(form.get(f"item_{indice}_ficha_id", "")).strip()
        if not ficha_id_texto:
            continue
        try:
            ficha_id = int(ficha_id_texto)
        except ValueError:
            continue
        # La ficha manda: el artículo sale de ella server-side, nunca del
        # navegador. Una ficha que ya no es de este cliente se ignora.
        ficha = ficha_por_id.get(ficha_id)
        if ficha is None:
            continue
        filas_crudas.append(
            {
                "articulo_id": ficha["articulo_id"],
                "ficha_id": ficha_id,
                "articulo_nombre": _nombre_de_ficha(ficha),
                "original_texto": str(form.get(f"item_{indice}_precio_original", "")).strip(),
                "nuevo_texto": str(form.get(f"item_{indice}_precio_nuevo", "")).strip(),
            }
        )

    error, filas_para_diff = _validar_precios(filas_crudas)
    if error:
        raise HTTPException(status_code=400, detail=error)

    cambios = calcular_cambios_de_precios(filas_para_diff)

    tipo_archivo = str(form.get("tipo_archivo", "")).strip()
    archivo_preview = str(form.get("archivo_preview", "")).strip()
    foto_ruta = None
    bytes_archivo = _bytes_desde_data_uri(archivo_preview)
    if bytes_archivo:
        extension = EXTENSION_POR_TIPO_ARCHIVO_PRECIOS.get(tipo_archivo, "jpg")
        content_type = MIME_POR_TIPO_ARCHIVO_PRECIOS.get(tipo_archivo, "image/jpeg")
        try:
            foto_ruta = subir_archivo_comanda(bytes_archivo, cliente["nombre"], extension, content_type)
        except Exception:
            logger.exception(
                "No se pudo subir el archivo de precios a Supabase Storage (cliente %s) "
                "— se guardan los precios igual, sin archivo",
                cliente_id,
            )
            foto_ruta = None

    try:
        guardar_precios_cliente(cliente_id, cambios, foto_ruta=foto_ruta)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"No se pudieron guardar los precios: {error_db}") from error_db

    return cliente, cambios


@app.post("/precios/cargar-foto/confirmar")
async def confirmar_carga_foto_precios(request: Request):
    form = await request.form()
    _cliente, cambios = _guardar_pendientes_carga_foto(form)
    return RedirectResponse(url=f"/precios?guardado={len(cambios)}", status_code=303)


@app.post("/precios/cargar-foto/guardar-y-exportar-pdf")
async def guardar_y_exportar_precios_cargar_foto_pdf(request: Request):
    """Guarda los renglones de Carga Foto y devuelve el PDF de la Lista de Precios ya actualizada."""
    form = await request.form()
    cliente, cambios = _guardar_pendientes_carga_foto(form)
    return _respuesta_listado_generado(cliente, cambios, "pdf")


@app.post("/precios/cargar-foto/guardar-y-exportar-excel")
async def guardar_y_exportar_precios_cargar_foto_excel(request: Request):
    """Guarda los renglones de Carga Foto y devuelve el Excel de la Lista de Precios ya actualizada."""
    form = await request.form()
    cliente, cambios = _guardar_pendientes_carga_foto(form)
    return _respuesta_listado_generado(cliente, cambios, "excel")


def _fecha_de_corte_limpieza_fotos():
    """3 años atrás de hoy: las fotos de compras más viejas que esto son candidatas a limpiar del Storage."""
    hoy = _hoy_argentina()
    try:
        return hoy.replace(year=hoy.year - 3)
    except ValueError:
        # 29 de febrero en un año bisiesto: hace 3 años no lo era.
        return hoy.replace(month=2, day=28, year=hoy.year - 3)


def _renderizar_pantalla_sistema(
    request: Request,
    *,
    mensaje: str | None = None,
    error: str | None = None,
    status_code: int = 200,
    cantidad_fotos_para_limpiar: int | None = None,
):
    # El indicador de espacio es informativo, no bloqueante: si falla, la
    # pantalla se muestra igual (uso_storage queda None y la plantilla no
    # lo muestra). El conteo de fotos para limpiar NO se calcula acá: es
    # una consulta que recorre todas las compras con foto, y no puede
    # correr en cada visita a esta pantalla por un numerito informativo —
    # se calcula bajo demanda con el botón "Revisar" (ver
    # revisar_fotos_viejas_ruta), y llega ya calculado por parámetro.
    try:
        uso_storage = obtener_uso_storage_bucket(BUCKET_COMANDAS)
    except Exception:
        uso_storage = None

    return templates.TemplateResponse(
        request,
        "sistema.html",
        {
            "error": error,
            "mensaje": mensaje,
            "uso_storage": uso_storage,
            "cantidad_fotos_para_limpiar": cantidad_fotos_para_limpiar,
            "banner": _banner_alertas("sistema"),
        },
        status_code=status_code,
    )


@app.get("/sistema")
def ver_sistema(request: Request):
    return _renderizar_pantalla_sistema(request)


@app.post("/sistema/revisar-fotos-viejas")
def revisar_fotos_viejas_ruta(request: Request):
    """Cuenta bajo demanda cuántas fotos de más de 3 años hay para limpiar, y lo muestra con el botón de borrar."""
    try:
        cantidad = len(listar_fotos_para_limpiar(_fecha_de_corte_limpieza_fotos()))
    except Exception as error_db:
        return _renderizar_pantalla_sistema(
            request, error=f"No se pudo revisar las fotos viejas: {error_db}", status_code=500
        )
    return _renderizar_pantalla_sistema(request, cantidad_fotos_para_limpiar=cantidad)


@app.post("/sistema/limpiar-fotos-viejas")
def limpiar_fotos_viejas_ruta(request: Request):
    fecha_corte = _fecha_de_corte_limpieza_fotos()
    try:
        fotos_a_borrar = listar_fotos_para_limpiar(fecha_corte)
    except Exception as error_db:
        return _renderizar_pantalla_sistema(
            request, error=f"No se pudo revisar qué fotos limpiar: {error_db}", status_code=500
        )

    if not fotos_a_borrar:
        return _renderizar_pantalla_sistema(request, mensaje="No hay fotos de más de 3 años para borrar.")

    borradas = 0
    for foto_ruta in fotos_a_borrar:
        try:
            borrar_foto_comanda(foto_ruta)
        except Exception:
            logger.exception("No se pudo borrar del Storage la foto vieja %s — se sigue con las demás", foto_ruta)
            continue

        try:
            limpiar_foto_ruta_de_compras(foto_ruta)
        except Exception:
            logger.exception(
                "Se borró del Storage la foto vieja %s pero no se pudo limpiar foto_ruta en la base", foto_ruta
            )
            continue

        borradas += 1

    if borradas == len(fotos_a_borrar):
        mensaje = f"Se liberaron {borradas} fotos."
    else:
        mensaje = f"Se liberaron {borradas} de {len(fotos_a_borrar)} fotos. Las demás quedaron para otro intento."
    return _renderizar_pantalla_sistema(request, mensaje=mensaje)


@app.get("/comercial")
def ver_comercial(request: Request):
    """Hub del área Comercial: junta los accesos a Precios, Clientes y Fichas Logísticas.

    El cartel suelto de "compras sin precio" pasó a ser una alerta más del
    banner: la misma alerta que ve Compras, calculada UNA vez y leída de la
    foto, en vez de dos consultas distintas que decían cosas distintas.
    """
    return templates.TemplateResponse(request, "comercial.html", {"banner": _banner_alertas("comercial")})


def _validar_costo_envase(texto: str) -> tuple[str | None, float | None]:
    """Valida el costo de un envase: número positivo (la baja usa 0, pero por su propio botón)."""
    texto = texto.strip().replace(",", ".")
    try:
        valor = float(texto)
    except ValueError:
        return "El costo tiene que ser un número.", None
    if valor <= 0:
        return "El costo tiene que ser mayor a cero.", None
    return None, valor


def _renderizar_pantalla_envases(
    request: Request, aviso: str | None = None, error: str | None = None, status_code: int = 200
):
    """La pantalla de Envases: el catálogo COMPLETO (los envases son compartidos entre clientes).

    Reutilizada por el GET y por los POST que fallan la validación (para
    volver a mostrar la misma pantalla con el error).
    """
    try:
        envases = listar_envases_con_costo(_hoy_argentina())
        historial_filas = listar_historial_costos_envases()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    historial_por_envase: dict[int, list[dict]] = {}
    for fila in historial_filas:
        historial_por_envase.setdefault(fila["envase_id"], []).append(fila)

    return templates.TemplateResponse(
        request,
        "envases.html",
        {
            "envases": envases,
            "historial_por_envase": historial_por_envase,
            "aviso": aviso,
            "error": error,
        },
        status_code=status_code,
    )


@app.get("/envases")
def ver_envases(request: Request, aviso: str | None = None):
    return _renderizar_pantalla_envases(request, aviso=aviso)


@app.post("/envases/nuevo")
def agregar_envase(request: Request, nombre: str = Form(""), costo: str = Form("")):
    error, nombre_valor = _validar_nombre(nombre)
    if not error:
        error, costo_valor = _validar_costo_envase(costo)
    if error:
        return _renderizar_pantalla_envases(request, error=error, status_code=400)

    try:
        crear_envase(nombre_valor, costo_valor)
    except ValueError as error_negocio:
        # Nombre repetido (el nombre es único global — ver crear_envase).
        return _renderizar_pantalla_envases(request, error=str(error_negocio), status_code=400)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"No se pudo crear el envase: {error_db}") from error_db

    parametros = urlencode({"aviso": f"Envase {nombre_valor} creado, con costo vigente desde hoy."})
    return RedirectResponse(url=f"/envases?{parametros}", status_code=303)


@app.post("/envases/{envase_id}/costo")
def cambiar_costo_envase(request: Request, envase_id: int, costo: str = Form("")):
    error, costo_valor = _validar_costo_envase(costo)
    if error:
        return _renderizar_pantalla_envases(request, error=error, status_code=400)

    try:
        # Regla de oro del historial: registrar_costo_envase INSERTA una
        # fila nueva vigente desde hoy, nunca pisa las anteriores — los
        # cálculos pasados no cambian.
        registrar_costo_envase(envase_id, costo_valor)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"No se pudo registrar el costo: {error_db}") from error_db

    parametros = urlencode({"aviso": "Costo nuevo registrado, vigente desde hoy. El historial anterior se conserva."})
    return RedirectResponse(url=f"/envases?{parametros}", status_code=303)


@app.post("/envases/{envase_id}/baja")
def dar_de_baja_envase(request: Request, envase_id: int):
    """Baja de un envase: fila nueva con costo 0 vigente desde hoy — mismo criterio de historial, nada se borra."""
    try:
        registrar_costo_envase(envase_id, 0)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"No se pudo dar de baja el envase: {error_db}") from error_db

    parametros = urlencode(
        {"aviso": "Envase dado de baja: costo $0 desde hoy. El historial y los cálculos pasados se conservan."}
    )
    return RedirectResponse(url=f"/envases?{parametros}", status_code=303)


@app.get("/logistica")
def ver_logistica(request: Request):
    """Hub del área Logística: el retiro de Clark (el único que se tilda acá) y el histórico Consultar Retiros."""
    return templates.TemplateResponse(request, "logistica.html", {"banner": _banner_alertas("logistica")})


ESTADOS_FILTRO_RETIRO_VALIDOS = {"pendiente", "retirado", "cancelado"}


def _filas_y_totales_retiros(retiros: list[dict]) -> tuple[list[dict], dict]:
    """Las filas de Consultar Retiros con sus totales, compartido por la pantalla y los exports.

    El total para liquidar: por fila, lo anotado al retirar si existe, si
    no lo que cargó el comprador. Se desglosa para que se vea cuánto del
    total es dato anotado y cuánto viene de la carga.

    Las compras que Depósito marcó "no ingresó" SUMAN al total igual que
    siempre, pero se cuentan aparte y se muestra el neto — nunca se
    restan en silencio: si el carrero dice "yo llevé 120" y acá dijera
    112 directo, no se sabría de dónde sale la diferencia. Los dos
    números a la vista, y el dueño decide qué paga.
    """
    total_bultos = 0.0
    total_anotados = 0.0
    total_del_comprador = 0.0
    total_no_ingresados = 0.0
    filas = []
    for retiro in retiros:
        anotada = retiro["cantidad_cajones_retirada"]
        bultos = float(anotada) if anotada is not None else float(retiro["cantidad_cajones"])
        usa_anotada = anotada is not None
        no_ingreso = retiro.get("estado") == "no_ingresado"
        total_bultos += bultos
        if usa_anotada:
            total_anotados += bultos
        else:
            total_del_comprador += bultos
        if no_ingreso:
            total_no_ingresados += bultos
        filas.append({**retiro, "bultos": bultos, "usa_anotada": usa_anotada, "no_ingreso": no_ingreso})

    totales = {
        "total_bultos": total_bultos,
        "total_anotados": total_anotados,
        "total_del_comprador": total_del_comprador,
        "total_no_ingresados": total_no_ingresados,
        "total_neto": total_bultos - total_no_ingresados,
    }
    return filas, totales


@app.get("/logistica/consultar")
def ver_consultar_retiros(
    request: Request,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
    proveedor_id: str | None = None,
    articulo_id: str | None = None,
    tipo: str | None = None,
    estado: str | None = None,
):
    """Consultar Retiros: el histórico de Logística, análogo a Buscar Compras.

    Con "estado = pendiente" sale el listado de lo que falta retirar (para
    mandárselo a alguien). El total de bultos de abajo es lo más importante
    de la pantalla: se usa para liquidarle al carrero o a la cooperativa —
    por fila usa la cantidad ANOTADA al retirar si existe, y si no la que
    cargó el comprador (marcada con asterisco, para ver de dónde sale cada
    número; las de Carro/Cooperativa son siempre asterisco, nadie anota).
    """
    proveedor_id_valor = _id_opcional_desde_query(proveedor_id)
    articulo_id_valor = _id_opcional_desde_query(articulo_id)
    tipo_valor = tipo if tipo in TIPOS_RETIRO_VALIDOS else None
    estado_valor = estado if estado in ESTADOS_FILTRO_RETIRO_VALIDOS else None

    hoy = _hoy_argentina()
    fecha_desde_valor = hoy - timedelta(days=1)
    fecha_hasta_valor = hoy
    error_fecha = None
    if fecha_desde:
        try:
            fecha_desde_valor = date.fromisoformat(fecha_desde)
        except ValueError:
            error_fecha = "La fecha desde no es válida."
    if fecha_hasta:
        try:
            fecha_hasta_valor = date.fromisoformat(fecha_hasta)
        except ValueError:
            error_fecha = "La fecha hasta no es válida."
    if error_fecha is None and fecha_desde_valor > fecha_hasta_valor:
        error_fecha = "La fecha desde no puede ser posterior a la fecha hasta."

    try:
        # La lista COMPLETA, igual que Buscar Compras: es un filtro de
        # búsqueda sobre historial, no un selector de carga.
        proveedores = listar_todos_los_proveedores()
        articulos = listar_articulos()
        # Mismo tope que Buscar Compras. OJO: si la lista se corta, los
        # totales de bultos NO se muestran — un total parcial usado para
        # liquidarle al carrero sería un número falso con plata de por medio.
        retiros = buscar_retiros(
            fecha_desde_valor, fecha_hasta_valor, proveedor_id_valor, articulo_id_valor, tipo_valor, estado_valor,
            limite=TOPE_FILAS_BUSQUEDA + 1,
        )
        aviso_tope = None
        if len(retiros) > TOPE_FILAS_BUSQUEDA:
            total = contar_retiros_buscados(
                fecha_desde_valor, fecha_hasta_valor, proveedor_id_valor, articulo_id_valor, tipo_valor, estado_valor
            )
            retiros = retiros[:TOPE_FILAS_BUSQUEDA]
            aviso_tope = (
                f"Se muestran los primeros {TOPE_FILAS_BUSQUEDA} retiros de {total}, y por eso los totales "
                "de bultos no se calculan (saldrían incompletos): achicá el rango o filtrá para ver todo."
            )
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    filas, totales = _filas_y_totales_retiros(retiros)

    return templates.TemplateResponse(
        request,
        "logistica_consultar.html",
        {
            "retiros": filas,
            "proveedores": proveedores,
            "articulos": articulos,
            "fecha_desde": fecha_desde_valor.isoformat(),
            "fecha_hasta": fecha_hasta_valor.isoformat(),
            "proveedor_id": proveedor_id_valor,
            "articulo_id": articulo_id_valor,
            "tipo": tipo_valor,
            "estado": estado_valor,
            "error_fecha": error_fecha,
            **totales,
            "aviso_tope": aviso_tope,
        },
    )


def _leer_filtros_exportar_retiros(
    fecha_desde_texto: str, fecha_hasta_texto: str, proveedor_id_texto: str, articulo_id_texto: str,
    tipo_texto: str, estado_texto: str,
) -> tuple[date, date, int | None, int | None, str | None, str | None, list[str]]:
    """Valida los filtros para las rutas de exportación de retiros y arma los textos para el subtítulo.

    El link solo lo arma la propia pantalla con valores ya válidos, así que
    un error acá es una URL manipulada a mano — alcanza con HTTPException
    (mismo criterio que la exportación de Buscar Compras).
    """
    try:
        fecha_desde = date.fromisoformat(fecha_desde_texto)
        fecha_hasta = date.fromisoformat(fecha_hasta_texto)
    except ValueError:
        raise HTTPException(status_code=400, detail="Fecha inválida")

    proveedor_id = _id_opcional_desde_query(proveedor_id_texto)
    articulo_id = _id_opcional_desde_query(articulo_id_texto)
    tipo = tipo_texto if tipo_texto in TIPOS_RETIRO_VALIDOS else None
    estado = estado_texto if estado_texto in ESTADOS_FILTRO_RETIRO_VALIDOS else None

    # Los filtros aplicados viajan al subtítulo del archivo: quien lo mira
    # (el carrero, la cooperativa) tiene que saber qué es sin abrir la app.
    filtros_texto = []
    if proveedor_id is not None:
        try:
            nombre = next((p["nombre"] for p in listar_proveedores() if p["id"] == proveedor_id), None)
        except Exception:
            nombre = None
        filtros_texto.append(f"proveedor {nombre or f'#{proveedor_id}'}")
    if articulo_id is not None:
        try:
            nombre = next((a["nombre"] for a in listar_articulos() if a["id"] == articulo_id), None)
        except Exception:
            nombre = None
        filtros_texto.append(f"artículo {nombre or f'#{articulo_id}'}")
    if tipo is not None:
        filtros_texto.append(f"tipo {tipo}")
    if estado is not None:
        filtros_texto.append(f"estado {estado}")

    return fecha_desde, fecha_hasta, proveedor_id, articulo_id, tipo, estado, filtros_texto


def _nombre_archivo_exportacion_retiros(fecha_desde: date, fecha_hasta: date, extension: str) -> str:
    return f"Retiros_{fecha_desde.isoformat()}_a_{fecha_hasta.isoformat()}.{extension}"


@app.get("/logistica/consultar/exportar-pdf")
def exportar_retiros_pdf(
    fecha_desde: str = "", fecha_hasta: str = "", proveedor_id: str = "", articulo_id: str = "",
    tipo: str = "", estado: str = "",
):
    """Genera Consultar Retiros (mismos filtros que la pantalla) en PDF — SIN tope, aunque la pantalla corte."""
    desde, hasta, proveedor_valor, articulo_valor, tipo_valor, estado_valor, filtros_texto = (
        _leer_filtros_exportar_retiros(fecha_desde, fecha_hasta, proveedor_id, articulo_id, tipo, estado)
    )
    try:
        retiros = buscar_retiros(desde, hasta, proveedor_valor, articulo_valor, tipo_valor, estado_valor)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    filas, totales = _filas_y_totales_retiros(retiros)
    pdf_bytes = generar_pdf_listado_retiros(desde, hasta, filtros_texto, filas, totales)
    nombre_archivo = _nombre_archivo_exportacion_retiros(desde, hasta, "pdf")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'},
    )


@app.get("/logistica/consultar/exportar-excel")
def exportar_retiros_excel(
    fecha_desde: str = "", fecha_hasta: str = "", proveedor_id: str = "", articulo_id: str = "",
    tipo: str = "", estado: str = "",
):
    """Genera Consultar Retiros (mismos filtros que la pantalla) en Excel — SIN tope, aunque la pantalla corte."""
    desde, hasta, proveedor_valor, articulo_valor, tipo_valor, estado_valor, filtros_texto = (
        _leer_filtros_exportar_retiros(fecha_desde, fecha_hasta, proveedor_id, articulo_id, tipo, estado)
    )
    try:
        retiros = buscar_retiros(desde, hasta, proveedor_valor, articulo_valor, tipo_valor, estado_valor)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    filas, totales = _filas_y_totales_retiros(retiros)
    excel_bytes = generar_excel_listado_retiros(desde, hasta, filtros_texto, filas, totales)
    nombre_archivo = _nombre_archivo_exportacion_retiros(desde, hasta, "xlsx")
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'},
    )


ORIGENES_RETIRO_VALIDOS = {"logistica", "deposito"}


def _validar_origen_retiro(origen: str | None) -> str:
    """A qué módulo volver desde /logistica/retiro (para la barrita de navegación y el "Volver a...").

    Se accede a esta misma pantalla desde dos lados (el hub de Logística, y el botón "Retirar
    Mercadería" de Depósito) — origen viaja en la URL (?origen=deposito) para que el ícono de sector
    y el link de "Volver" sean del módulo real desde el que se entró, no siempre Logística.
    Cualquier valor que no sea uno de los dos válidos (incluido None, si no vino nada) cae en
    'logistica' — el módulo dueño de esta pantalla.
    """
    return origen if origen in ORIGENES_RETIRO_VALIDOS else "logistica"


def _renderizar_pantalla_logistica_retiro(
    request: Request,
    tipo_retiro: str,
    *,
    origen: str = "logistica",
    recien_procesado_id: int | None = None,
    aviso: str | None = None,
    error: str | None = None,
    status_code: int = 200,
):
    if tipo_retiro not in TIPOS_RETIRO_VALIDOS:
        raise HTTPException(status_code=404, detail="Tipo de retiro no válido")

    try:
        compras_pendientes = listar_compras_pendientes_retiro(tipo_retiro)
        procesados_hoy = listar_compras_procesadas_hoy_retiro(tipo_retiro, _hoy_argentina())
    except Exception as error_db:
        return templates.TemplateResponse(
            request,
            "logistica_retiro.html",
            {
                "tipo_retiro": tipo_retiro,
                "origen": origen,
                "guias": [],
                "procesados_hoy": [],
                "recien_procesado": None,
                "error": f"No se pudieron leer las compras pendientes: {error_db}",
            },
            status_code=500,
        )

    for procesado in procesados_hoy:
        procesado["deshacer_bloqueado"] = compra_tiene_deshacer_retiro_bloqueado(procesado["estado"])
        procesado["motivo_bloqueo"] = ESTADOS_RECEPCION_LABELS.get(procesado["estado"]) if procesado["deshacer_bloqueado"] else None

    # La fecha de cada compra pendiente, con marca cuando tiene más de un
    # día: el que retira tiene que ver de cuándo es lo que está por
    # levantar — si es de hace dos días, que salte a la vista.
    hoy = _hoy_argentina()
    for compra_pendiente in compras_pendientes:
        compra_pendiente["fecha_vieja"] = compra_pendiente["fecha_operacion"] < hoy - timedelta(days=1)

    recien_procesado = None
    if recien_procesado_id is not None:
        recien_procesado = next((p for p in procesados_hoy if p["id"] == recien_procesado_id), None)

    guias = _agrupar_pendientes_por_guia(compras_pendientes)
    return templates.TemplateResponse(
        request,
        "logistica_retiro.html",
        {
            "tipo_retiro": tipo_retiro,
            "origen": origen,
            "guias": guias,
            "procesados_hoy": procesados_hoy,
            "recien_procesado": recien_procesado,
            "aviso": aviso,
            "error": error,
        },
        status_code=status_code,
    )


@app.get("/logistica/retiro/{tipo_retiro}")
def ver_logistica_retiro(request: Request, tipo_retiro: str, origen: str | None = None, procesado: str | None = None):
    return _renderizar_pantalla_logistica_retiro(
        request, tipo_retiro, origen=_validar_origen_retiro(origen), recien_procesado_id=_id_opcional_desde_query(procesado)
    )


def _validar_cantidad_cajones_retirada(texto: str) -> tuple[str | None, float | None]:
    """Valida los cajones retirados que anota Logística: opcional, si viene tiene que ser un número no negativo."""
    texto = texto.strip()
    if not texto:
        return None, None
    try:
        valor = float(texto)
    except ValueError:
        return "La cantidad de cajones retirados tiene que ser un número.", None
    if valor < 0:
        return "La cantidad de cajones retirados no puede ser negativa.", None
    return None, valor


@app.post("/logistica/retiro/{tipo_retiro}/{compra_id}/retirar")
def retirar_compra_ruta(
    request: Request, tipo_retiro: str, compra_id: int, origen: str | None = None, cantidad_cajones_retirada: str = Form("")
):
    origen_valido = _validar_origen_retiro(origen)

    error, valor = _validar_cantidad_cajones_retirada(cantidad_cajones_retirada)
    if error:
        return _renderizar_pantalla_logistica_retiro(request, tipo_retiro, origen=origen_valido, error=error, status_code=400)

    try:
        marcar_compra_retirada(compra_id, "logistica", valor)
    except Exception as error_db:
        return _renderizar_pantalla_logistica_retiro(
            request, tipo_retiro, origen=origen_valido, error=f"No se pudo marcar como retirada: {error_db}", status_code=500
        )

    return RedirectResponse(url=f"/logistica/retiro/{tipo_retiro}?origen={origen_valido}&procesado={compra_id}", status_code=303)


@app.post("/logistica/retiro/{tipo_retiro}/{compra_id}/cancelar")
def cancelar_retiro_compra_ruta(request: Request, tipo_retiro: str, compra_id: int, origen: str | None = None):
    origen_valido = _validar_origen_retiro(origen)

    try:
        marcar_compra_cancelada(compra_id, "logistica")
    except Exception as error_db:
        return _renderizar_pantalla_logistica_retiro(
            request, tipo_retiro, origen=origen_valido, error=f"No se pudo marcar como cancelada: {error_db}", status_code=500
        )

    return RedirectResponse(url=f"/logistica/retiro/{tipo_retiro}?origen={origen_valido}&procesado={compra_id}", status_code=303)


@app.post("/logistica/retiro/{tipo_retiro}/{compra_id}/deshacer")
def deshacer_retiro_compra_ruta(request: Request, tipo_retiro: str, compra_id: int, origen: str | None = None):
    """Vuelve una compra retirada/cancelada a pendiente — tarjeta efímera o panel "Procesados hoy"."""
    origen_valido = _validar_origen_retiro(origen)

    try:
        deshacer_retiro_compra(compra_id)
    except ValueError as error_bloqueo:
        return _renderizar_pantalla_logistica_retiro(
            request, tipo_retiro, origen=origen_valido, error=str(error_bloqueo), status_code=400
        )
    except Exception as error_db:
        return _renderizar_pantalla_logistica_retiro(
            request, tipo_retiro, origen=origen_valido, error=f"No se pudo deshacer: {error_db}", status_code=500
        )

    return RedirectResponse(url=f"/logistica/retiro/{tipo_retiro}?origen={origen_valido}", status_code=303)


@app.get("/deposito")
def ver_deposito(request: Request, aviso: str | None = None):
    """Hub del área Depósito: Recepción, Retirar e Ingresar Mercadería."""
    return templates.TemplateResponse(
        request, "deposito.html", {"aviso": aviso, "banner": _banner_alertas("deposito")}
    )


AVISO_INGRESO_DIRECTO_SIN_PRECIO = "Ingresada sin precio. El comprador tiene que cargar el costo."


@app.get("/deposito/ingresar")
def ver_ingresar_mercaderia(
    request: Request, proveedor_id: int | None = None, error: str | None = None, aviso: str | None = None
):
    """Ingreso directo de mercadería que ya está en el depósito, sin pasar por Logística ni Recepción.

    Mismo patrón de dos pasos que /compras/nueva (elegir o cargar
    proveedor, después sumar artículos uno a la vez) — pero pantalla
    propia, sin campo de precio: eso lo carga el comprador después (ver
    ingresar_mercaderia).
    """
    if proveedor_id is None:
        try:
            proveedores = listar_proveedores()
        except Exception as error_db:
            raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

        return templates.TemplateResponse(
            request,
            "deposito_ingresar_proveedor.html",
            {"proveedores": proveedores, "error": error},
        )

    try:
        proveedor = obtener_proveedor(proveedor_id)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    if proveedor is None:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")

    try:
        articulos = listar_articulos()
        renglones_hoy = listar_compras_por_fecha_y_proveedor(_hoy_argentina(), proveedor_id)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    return templates.TemplateResponse(
        request,
        "deposito_ingresar.html",
        {
            "articulos": articulos,
            "compra": None,
            "proveedor": proveedor,
            "renglones_hoy": renglones_hoy,
            "error": error,
            "aviso": aviso,
        },
    )


@app.post("/deposito/ingresar/proveedor")
def elegir_proveedor_ingreso_directo(request: Request, codigo_puesto: str = Form(""), nombre: str = Form("")):
    """Confirma o crea el proveedor para /deposito/ingresar — mismo mecanismo que /compras/nueva/proveedor
    (obtener_o_crear_proveedor_por_codigo): la mercadería que entra fuera de hora puede venir justo de
    un proveedor que nunca se compró, así que Depósito tiene que poder cargarlo, no solo elegir uno
    existente.
    """
    error, codigo_valor = _validar_codigo_puesto(codigo_puesto)

    nombre_valor = nombre
    if not error:
        error, nombre_valor = _validar_nombre(nombre)

    if error:
        try:
            proveedores = listar_proveedores()
        except Exception:
            proveedores = []
        return templates.TemplateResponse(
            request,
            "deposito_ingresar_proveedor.html",
            {"proveedores": proveedores, "error": error},
            status_code=400,
        )

    try:
        proveedor_id, reactivado = obtener_o_crear_proveedor_por_codigo(codigo_valor, nombre_valor)
    except Exception as error_db:
        try:
            proveedores = listar_proveedores()
        except Exception:
            proveedores = []
        return templates.TemplateResponse(
            request,
            "deposito_ingresar_proveedor.html",
            {"proveedores": proveedores, "error": f"No se pudo guardar el proveedor: {error_db}"},
            status_code=500,
        )

    parametros = {"proveedor_id": proveedor_id}
    aviso_reactivado = _aviso_proveedor_reactivado(reactivado, nombre_valor)
    if aviso_reactivado:
        parametros["aviso"] = aviso_reactivado
    return RedirectResponse(url=f"/deposito/ingresar?{urlencode(parametros)}", status_code=303)


@app.post("/deposito/ingresar")
def ingresar_mercaderia(
    request: Request,
    proveedor_id: int = Form(...),
    accion: str = Form("agregar"),
    articulo_id: str = Form(""),
    cantidad_cajones: str = Form(""),
    contenido_por_cajon: str = Form(""),
    tipo_retiro: str = Form("Clark"),
):
    """Agrega un artículo ya recibido en Depósito, sin pasar por Logística ni por Recepción.

    Mismos validadores que agregar_compra (_validar_compra_nueva_form),
    pasando importe/sena vacíos siempre — esta pantalla no tiene esos
    campos. crear_compra hace el resto con ingreso_directo_deposito=True:
    la compra nace 'recepcionado'/'retirado', con las cantidades reales
    iguales a las cargadas (no hay estimado previo).
    """
    renglon_vacio = not any(campo.strip() for campo in (articulo_id, cantidad_cajones, contenido_por_cajon))
    if accion == "terminar" and renglon_vacio:
        return RedirectResponse(url="/deposito", status_code=303)

    try:
        proveedor = obtener_proveedor(proveedor_id)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    if proveedor is None:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")

    error, valores = _validar_compra_nueva_form(articulo_id, cantidad_cajones, contenido_por_cajon, "", "", tipo_retiro)

    articulo = None
    if not error:
        try:
            articulo = obtener_articulo(valores["articulo_id"])
        except Exception as error_db:
            articulos = listar_articulos()
            renglones_hoy = listar_compras_por_fecha_y_proveedor(_hoy_argentina(), proveedor_id)
            compra = {
                "id": None,
                "articulo_id": valores["articulo_id"],
                "cantidad_cajones": cantidad_cajones,
                "contenido_por_cajon": contenido_por_cajon,
                "tipo_retiro": tipo_retiro,
            }
            return templates.TemplateResponse(
                request,
                "deposito_ingresar.html",
                {
                    "articulos": articulos,
                    "compra": compra,
                    "proveedor": proveedor,
                    "renglones_hoy": renglones_hoy,
                    "error": f"No se pudo leer el artículo: {error_db}",
                },
                status_code=500,
            )

        if articulo is None:
            error = "El artículo elegido no es válido."
        elif not articulo["unidad_compra"]:
            error = "Este artículo no tiene la unidad de compra configurada. Cargala en /articulos primero."

    if error:
        articulos = listar_articulos()
        renglones_hoy = listar_compras_por_fecha_y_proveedor(_hoy_argentina(), proveedor_id)
        compra = {
            "id": None,
            "articulo_id": valores["articulo_id"],
            "cantidad_cajones": cantidad_cajones,
            "contenido_por_cajon": contenido_por_cajon,
            "tipo_retiro": tipo_retiro,
        }
        return templates.TemplateResponse(
            request,
            "deposito_ingresar.html",
            {
                "articulos": articulos,
                "compra": compra,
                "proveedor": proveedor,
                "renglones_hoy": renglones_hoy,
                "error": error,
            },
            status_code=400,
        )

    total = valores["cantidad_cajones"] * valores["contenido_por_cajon"]
    if articulo["unidad_compra"] == "kilo":
        cantidad_kilos, cantidad_fraccion = total, None
    else:
        cantidad_kilos, cantidad_fraccion = None, total

    try:
        crear_compra(
            _hoy_argentina(),
            valores["articulo_id"],
            proveedor_id,
            valores["cantidad_cajones"],
            valores["contenido_por_cajon"],
            cantidad_kilos,
            cantidad_fraccion,
            None,
            None,
            valores["tipo_retiro"],
            ingreso_directo_deposito=True,
        )
    except Exception as error_db:
        articulos = listar_articulos()
        renglones_hoy = listar_compras_por_fecha_y_proveedor(_hoy_argentina(), proveedor_id)
        compra = {
            "id": None,
            "articulo_id": valores["articulo_id"],
            "cantidad_cajones": cantidad_cajones,
            "contenido_por_cajon": contenido_por_cajon,
            "tipo_retiro": tipo_retiro,
        }
        return templates.TemplateResponse(
            request,
            "deposito_ingresar.html",
            {
                "articulos": articulos,
                "compra": compra,
                "proveedor": proveedor,
                "renglones_hoy": renglones_hoy,
                "error": f"No se pudo guardar la compra: {error_db}",
            },
            status_code=500,
        )

    parametros = urlencode({"aviso": AVISO_INGRESO_DIRECTO_SIN_PRECIO})
    if accion == "terminar":
        return RedirectResponse(url=f"/deposito?{parametros}", status_code=303)

    return RedirectResponse(url=f"/deposito/ingresar?proveedor_id={proveedor_id}&{parametros}", status_code=303)


def _validar_cantidad_cajones_real(texto: str) -> tuple[str | None, float | None]:
    """Valida la cantidad de cajones real cargada en Recepción: obligatoria, número positivo."""
    texto = texto.strip()
    if not texto:
        return "La cantidad de cajones real es obligatoria.", None
    try:
        valor = float(texto)
    except ValueError:
        return "La cantidad de cajones real tiene que ser un número.", None
    if valor <= 0:
        return "La cantidad de cajones real tiene que ser mayor a cero.", None
    return None, valor


def _validar_valor_real_recepcion(texto: str) -> tuple[str | None, float | None]:
    """Valida el valor real cargado en Recepción: obligatorio, número positivo.

    Siempre es por cajón/bulto (ver _derivar_valores_reales en app/db.py):
    kilos, unidades o cubetas de UN bulto — nunca el total de toda la
    carga. La validación en sí (obligatorio, número, mayor a cero) es la
    misma para los tres casos, por eso el mensaje queda genérico.
    """
    texto = texto.strip()
    if not texto:
        return "El valor real es obligatorio.", None
    try:
        valor = float(texto)
    except ValueError:
        return "El valor real tiene que ser un número.", None
    if valor <= 0:
        return "El valor real tiene que ser mayor a cero.", None
    return None, valor


def _validar_rechazo_parcial(
    cantidad_cajones_llegados: str, cantidad_cajones_rechazada: str
) -> tuple[str | None, float | None, float | None]:
    """Valida el rechazo parcial de Recepción: (error, bultos aceptados, bultos rechazados).

    Los bultos aceptados (llegados − rechazados) son lo que se guarda en
    cantidad_cajones_real — el rechazado se devuelve al proveedor y se le
    paga solo lo recibido. Rechazar 0 no es un rechazo parcial (es una
    recepción normal), y rechazar todo tampoco (es el botón "Rechazar por
    calidad"): acá siempre tiene que quedar algo en el medio.
    """
    texto_llegados = cantidad_cajones_llegados.strip()
    if not texto_llegados:
        return "La cantidad de bultos llegados es obligatoria.", None, None
    try:
        llegados = float(texto_llegados)
    except ValueError:
        return "La cantidad de bultos llegados tiene que ser un número.", None, None
    if llegados <= 0:
        return "La cantidad de bultos llegados tiene que ser mayor a cero.", None, None

    texto_rechazada = cantidad_cajones_rechazada.strip()
    if not texto_rechazada:
        return "La cantidad de bultos rechazados es obligatoria.", None, None
    try:
        rechazados = float(texto_rechazada)
    except ValueError:
        return "La cantidad de bultos rechazados tiene que ser un número.", None, None
    if rechazados <= 0:
        return "La cantidad de bultos rechazados tiene que ser mayor a cero. Si no rechazás nada, usá Recibir.", None, None
    if rechazados >= llegados:
        return "Los bultos rechazados tienen que ser menos que los llegados. Si rechazás todo, usá Rechazo total.", None, None

    return None, llegados - rechazados, rechazados


def _agrupar_pendientes_por_guia(compras: list[dict]) -> list[dict]:
    """Agrupa las compras pendientes de Recepción por guía, en el orden en que ya vienen (por guia_id, guia_punto).

    Devuelve una lista de {"guia_id", "proveedor_nombre", "proveedor_codigo_puesto",
    "fecha_operacion", "compras"}. La fecha es UNA por guía (la guía es por
    proveedor y día): la pantalla la muestra en el encabezado para que se
    vea de un vistazo si la partida es de un día anterior.
    """
    guias_por_id: dict[int, dict] = {}
    orden_guias: list[int] = []
    for compra in compras:
        guia_id = compra["guia_id"]
        if guia_id not in guias_por_id:
            guias_por_id[guia_id] = {
                "guia_id": guia_id,
                "proveedor_nombre": compra["proveedor_nombre"],
                "proveedor_codigo_puesto": compra["proveedor_codigo_puesto"],
                "fecha_operacion": compra.get("fecha_operacion"),
                "compras": [],
            }
            orden_guias.append(guia_id)
        guias_por_id[guia_id]["compras"].append(compra)
    return [guias_por_id[guia_id] for guia_id in orden_guias]


def _renderizar_pantalla_recepcion(
    request: Request,
    *,
    recien_procesado_id: int | None = None,
    error: str | None = None,
    aviso: str | None = None,
    status_code: int = 200,
):
    try:
        compras_pendientes = listar_compras_pendientes_recepcion()
        procesados_hoy = listar_compras_procesadas_hoy_recepcion(_hoy_argentina())
    except Exception as error_db:
        return templates.TemplateResponse(
            request,
            "deposito_recepcion.html",
            {
                "guias": [],
                "procesados_hoy": [],
                "recien_procesado": None,
                "error": f"No se pudieron leer las compras pendientes: {error_db}",
            },
            status_code=500,
        )

    for procesado in procesados_hoy:
        procesado["deshacer_bloqueado"] = compra_tiene_deshacer_recepcion_bloqueado(procesado["estado"])
        procesado["estado_label"] = ESTADOS_RECEPCION_LABELS.get(procesado["estado"], procesado["estado"])

    recien_procesado = None
    if recien_procesado_id is not None:
        recien_procesado = next((p for p in procesados_hoy if p["id"] == recien_procesado_id), None)

    guias = _agrupar_pendientes_por_guia(compras_pendientes)
    # La fecha de cada guía con marca cuando tiene más de un día (mismo
    # criterio que Retirar Mercadería): el que recepciona tiene que ver de
    # cuándo es la partida — si es de anteayer, que salte a la vista.
    hoy = _hoy_argentina()
    for guia in guias:
        guia["fecha_vieja"] = guia["fecha_operacion"] is not None and guia["fecha_operacion"] < hoy - timedelta(days=1)

    return templates.TemplateResponse(
        request,
        "deposito_recepcion.html",
        {
            "guias": guias,
            "procesados_hoy": procesados_hoy,
            "recien_procesado": recien_procesado,
            "error": error,
            "aviso": aviso,
        },
        status_code=status_code,
    )


@app.get("/deposito/recepcion")
def ver_recepcion(request: Request, aviso: str | None = None, procesado: str | None = None):
    return _renderizar_pantalla_recepcion(request, aviso=aviso, recien_procesado_id=_id_opcional_desde_query(procesado))


def _url_recepcion_con_procesado(compra_id: int, aviso_retiro: str | None) -> str:
    parametros = {"procesado": compra_id}
    if aviso_retiro:
        parametros["aviso"] = aviso_retiro
    return f"/deposito/recepcion?{urlencode(parametros)}"


@app.post("/deposito/recepcion/{compra_id}/recepcionar")
def recepcionar_compra_ruta(
    request: Request,
    compra_id: int,
    cantidad_cajones_real: str = Form(""),
    cantidad_total_real: str = Form(""),
):
    error, cajones_valor = _validar_cantidad_cajones_real(cantidad_cajones_real)
    if not error:
        error, valor_real = _validar_valor_real_recepcion(cantidad_total_real)

    if error:
        return _renderizar_pantalla_recepcion(request, error=error, status_code=400)

    try:
        aviso_retiro = recepcionar_compra(compra_id, cajones_valor, valor_real)
    except Exception as error_db:
        return _renderizar_pantalla_recepcion(
            request, error=f"No se pudo recepcionar la compra: {error_db}", status_code=500
        )

    return RedirectResponse(url=_url_recepcion_con_procesado(compra_id, aviso_retiro), status_code=303)


@app.post("/deposito/recepcion/{compra_id}/rechazar")
def rechazar_compra_ruta(request: Request, compra_id: int):
    try:
        aviso_retiro = rechazar_compra(compra_id)
    except Exception as error_db:
        return _renderizar_pantalla_recepcion(
            request, error=f"No se pudo rechazar la compra: {error_db}", status_code=500
        )

    return RedirectResponse(url=_url_recepcion_con_procesado(compra_id, aviso_retiro), status_code=303)


@app.post("/deposito/recepcion/{compra_id}/rechazo-parcial")
def rechazo_parcial_compra_ruta(
    request: Request,
    compra_id: int,
    cantidad_cajones_llegados: str = Form(""),
    cantidad_cajones_rechazada: str = Form(""),
    cantidad_total_real: str = Form(""),
    motivo_rechazo: str = Form(""),
):
    """Llegó la carga pero Depósito devuelve parte al proveedor (ej. 2 de 10 por calidad).

    Es una recepción normal por los bultos aceptados (llegados −
    rechazados): como el importe es por bulto, el total a pagar y el
    costeo salen solos de cantidad_cajones_real — ninguna cuenta cambia.
    Lo único nuevo es el registro de cuántos bultos se devolvieron y por
    qué (ver recepcionar_compra).
    """
    error, cajones_aceptados, cajones_rechazados = _validar_rechazo_parcial(
        cantidad_cajones_llegados, cantidad_cajones_rechazada
    )
    if not error:
        error, valor_real = _validar_valor_real_recepcion(cantidad_total_real)

    if error:
        return _renderizar_pantalla_recepcion(request, error=error, status_code=400)

    try:
        aviso_retiro = recepcionar_compra(
            compra_id,
            cajones_aceptados,
            valor_real,
            cantidad_cajones_rechazada=cajones_rechazados,
            motivo_rechazo=motivo_rechazo.strip() or None,
        )
    except Exception as error_db:
        return _renderizar_pantalla_recepcion(
            request, error=f"No se pudo guardar el rechazo parcial: {error_db}", status_code=500
        )

    return RedirectResponse(url=_url_recepcion_con_procesado(compra_id, aviso_retiro), status_code=303)


@app.post("/deposito/recepcion/{compra_id}/no-ingreso")
def no_ingreso_compra_ruta(request: Request, compra_id: int):
    """La mercadería nunca llegó al depósito. A diferencia de recepcionar/rechazar, no marca retirada la compra."""
    try:
        marcar_compra_no_ingresada(compra_id)
    except Exception as error_db:
        return _renderizar_pantalla_recepcion(
            request, error=f"No se pudo marcar la compra como no ingresada: {error_db}", status_code=500
        )

    return RedirectResponse(url=_url_recepcion_con_procesado(compra_id, None), status_code=303)


@app.post("/deposito/recepcion/{compra_id}/deshacer-no-ingreso")
def deshacer_procesado_compra_ruta(request: Request, compra_id: int):
    """Vuelve a pendiente una compra marcada "No ingresó" o con "Rechazo total" — tarjeta efímera o panel "Procesados hoy".

    La URL sigue diciendo "no-ingreso" por lo que ya está en el HTML y en
    la memoria de los links; el nombre quedó corto cuando el deshacer pasó
    a cubrir también el rechazo total (renombrar rutas es un pendiente
    aparte, anotado). Lo que se puede deshacer lo decide una sola función,
    compra_tiene_deshacer_recepcion_bloqueado, no el nombre de la ruta.
    """
    try:
        estado_deshecho = deshacer_procesado_compra(compra_id)
    except ValueError as error_bloqueo:
        return _renderizar_pantalla_recepcion(request, error=str(error_bloqueo), status_code=400)
    except Exception as error_db:
        return _renderizar_pantalla_recepcion(request, error=f"No se pudo deshacer: {error_db}", status_code=500)

    # La compra desaparece del panel y reaparece abajo, entre las
    # pendientes: sin una línea que lo diga, el que lo toca no sabe si
    # pasó algo y lo aprieta de nuevo.
    if estado_deshecho == "rechazado":
        aviso = "Rechazo deshecho: la compra volvió a la lista para recepcionar."
    else:
        aviso = "Listo: la compra volvió a la lista para recepcionar."
    return RedirectResponse(url=f"/deposito/recepcion?{urlencode({'aviso': aviso})}", status_code=303)


# --- Stock del Depósito ---
# El stock por artículo es DERIVADO, nunca guardado (ver app/db.py). Las
# rutas van partidas desde el arranque: las de carga del operario
# (fisico/merma/reingreso, tandas 2 y 3) separadas de las de control
# (sistema/cotejo/ajustar/movimientos), para poder colgarles una clave
# después sin mover nada — mismo esquema que Puesto → Envases.


def _clave_alfabetica(texto: str) -> str:
    """Para ordenar sin que las tildes manden al final: "Ají" va con la A."""
    sin_tildes = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in sin_tildes if not unicodedata.combining(c)).lower()


def _porciones_de_deposito() -> list[dict]:
    """Cada porción del depósito como un renglón propio, alfabético. La vista del que trabaja.

    En el piso NO hay "un artículo con un total": hay pilas distintas, en
    lugares distintos y para cosas distintas. Saber que hay 9 limones
    sumando 4 sueltos más 5 en caja de Día no le sirve a nadie; lo que hace
    falta saber es cuántas cajas hay de cada cosa. Por eso cada porción es
    un renglón y NO hay total por artículo.

    EL NOMBRE PELADO ES LA MERCADERÍA COMO VIENE DEL PUESTO, que es como el
    depósito la llama. La palabra "suelto" no aparece: las que necesitan
    aclaración son las otras dos.

    Sale entera de la CUENTA 2 (cajas por ficha) y del pool de segunda, que
    desde el 05/09 arrancan las dos en la fecha de corte. El desglose por
    GUÍA R —la cuenta 3— es trazabilidad y vive en Stock por Guía: al que
    arma no le importa de qué guía R salió una caja, y la guía R no está
    escrita en la caja, así que tampoco podría verificarlo contando.

    Solo lo que tiene MÁS DE CERO. Una porción en cero no es una pila, y un
    negativo no se puede contar: los negativos siguen a la vista en Stock
    del Sistema, que es la pantalla de control.

    El orden agrupa por ARTÍCULO y después por tipo de porción, no por el
    texto que se muestra: así "Pomelo" y "Pomelo caja Día" caen juntas
    aunque la ficha se llame de otra forma.
    """
    filas = stock_deposito_por_articulo()
    cajas = cajas_armadas_por_ficha()
    fichas = {f["id"]: f for f in listar_fichas_de_todos_los_clientes()}

    porciones = []
    for fila in filas:
        articulo = fila["nombre"]
        de_este = {c: b for c, b in cajas.items() if c[0] == fila["articulo_id"]}
        # Los sueltos por RESTA, como en todo el módulo: así las porciones
        # suman el total del artículo sin que se pueda perder ni duplicar.
        sueltos = round(float(fila["stock"]) - sum(de_este.values()), 2)
        if sueltos > 0:
            porciones.append({"articulo": articulo, "orden": 0, "nombre": articulo, "bultos": sueltos})
        for (_articulo_id, ficha_id), bultos in de_este.items():
            ficha = fichas.get(ficha_id)
            porciones.append({
                "articulo": articulo,
                "orden": 1,
                "nombre": _nombre_de_ficha(ficha) if ficha else f"{articulo} (ficha #{ficha_id})",
                "bultos": round(float(bultos), 2),
            })
        if float(fila["segunda"]) > 0:
            porciones.append({"articulo": articulo, "orden": 2,
                              "nombre": f"{articulo} Segunda", "bultos": round(float(fila["segunda"]), 2)})

    porciones.sort(key=lambda p: (_clave_alfabetica(p["articulo"]), p["orden"], _clave_alfabetica(p["nombre"])))
    return porciones


@app.get("/deposito/stock/remanente")
def ver_remanente_deposito(request: Request):
    """Qué hay en el depósito, una porción por renglón. Para mirar, no para cargar."""
    try:
        porciones = _porciones_de_deposito()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db
    return templates.TemplateResponse(
        request, "deposito_stock_remanente.html", {"porciones": porciones, "hoy": _hoy_argentina()}
    )


@app.get("/deposito/stock/remanente/exportar-excel")
def exportar_remanente_deposito_excel():
    """El mismo remanente en Excel, con una columna vacía para anotar lo contado."""
    try:
        porciones = _porciones_de_deposito()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db
    hoy = _hoy_argentina()
    return Response(
        content=generar_excel_remanente(hoy, porciones),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition":
                 f'attachment; filename="Remanente_{hoy.strftime("%d_%m_%Y")}.xlsx"'},
    )


@app.get("/deposito/stock")
def ver_stock_deposito(request: Request, aviso: str | None = None):
    """El hub del stock: carga del operario arriba, control abajo. Lo que falta construir se ve atenuado."""
    return templates.TemplateResponse(request, "deposito_stock.html", {"aviso": aviso})


def _tamanos_de_caja_por_ficha() -> dict[str, str]:
    """El tamaño de la caja armada según la ficha, por "cliente_id:articulo_id" ("6 kg") — para el desglose del stock.

    Con VARIAS fichas del mismo artículo para ese cliente y tamaños
    distintos, se muestran los dos ("6 o 10 kg"): la guía R no guarda con
    qué ficha se armó, así que elegir uno sería inventar. Si las dos fichas
    tienen el mismo kilaje, no hay ambigüedad y se muestra uno solo.
    """
    tamanos: dict[str, str] = {}
    por_clave: dict[str, list[str]] = {}
    # TODAS las fichas en una consulta: antes se pedían cliente por cliente,
    # que es el mismo N+1 que el del FIFO, escondido en otra pantalla.
    for ficha in listar_fichas_de_todos_los_clientes():
        if not ficha.get("contenido_caja"):
            continue
        sufijo = SUFIJOS_FICHA_REPROCESO.get(ficha.get("unidad_venta"), "")
        texto = f"{_formatear_numero(ficha['contenido_caja'])} {sufijo}".strip()
        clave = f"{ficha['cliente_id']}:{ficha['articulo_id']}"
        if texto not in por_clave.setdefault(clave, []):
            por_clave[clave].append(texto)

    for clave, textos in por_clave.items():
        tamanos[clave] = " o ".join(textos)
    return tamanos


def _desglose_stock_articulo(fila: dict, tamanos_ficha: dict[str, str], movimientos: tuple) -> list[dict]:
    """Las guías R con primera restante de un artículo, rejugando el FIFO: qué cajas armadas hay hoy, para quién y de qué tamaño.

    Cada línea es una guía R con resto (si hay varias de tamaños
    distintos, salen separadas). Es el mismo reparto del detalle por
    artículo, subido al listado: nada se guarda, se calcula cada vez.

    Recibe los movimientos ya traídos (entradas y salidas fechadas) en vez
    de ir a buscarlos: el listado los pide TODOS de una, para no abrir una
    conexión por artículo.
    """
    entradas, salidas = movimientos
    reparto = repartir_fifo(entradas, salidas_para_reparto(salidas))

    armados = []
    for lote in reparto["lotes"]:
        if lote.get("tipo_lote") != "reproceso" or lote["restante"] <= 0:
            continue
        clave_ficha = f"{lote['cliente_lote_id']}:{fila['articulo_id']}" if lote.get("cliente_lote_id") else None
        armados.append({
            "bultos": lote["restante"],
            "cliente": lote.get("detalle"),
            "tamano": tamanos_ficha.get(clave_ficha) if clave_ficha else None,
            "guia": lote["origen_id"],
            "fecha": lote["fecha_lote"],
        })
    return armados


@app.get("/administracion/stock/sistema")
def ver_stock_sistema_deposito(request: Request):
    """Stock del Sistema por artículo (bultos), calculado siempre. Los negativos arriba, en rojo: son salidas sin explicar.

    Un artículo con guías R vivas o segunda se muestra DESGLOSADO en el
    listado (pedido del dueño 26/08: 80 cajones sin procesar + 40 cajas
    armadas no son "120 bultos"): sin procesar, cada guía R con resto
    (cliente y tamaño de caja según la ficha) y la segunda, con el total
    al final. Un artículo sin nada de eso muestra solo su número.
    """
    try:
        filas = stock_deposito_por_articulo()
        reingresos_total = total_reingresos_rechazo()
        # Las fichas se cargan una sola vez, y solo si algún artículo tiene
        # primera de reproceso para desglosar.
        tamanos_ficha = (
            _tamanos_de_caja_por_ficha() if any(f["reproceso_primera"] for f in filas) else {}
        )
        # Los movimientos de TODOS los artículos con guía R, en una consulta.
        con_primera = [f["articulo_id"] for f in filas if f["reproceso_primera"]]
        movimientos = entradas_y_salidas_stock_articulos(con_primera)
        for fila in filas:
            fila["armados"] = (
                _desglose_stock_articulo(fila, tamanos_ficha, movimientos[fila["articulo_id"]])
                if fila["reproceso_primera"] else []
            )
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    for fila in filas:
        fila["sin_procesar"] = fila["stock"] - sum(a["bultos"] for a in fila["armados"])
        fila["total_con_segunda"] = fila["stock"] + fila["segunda"]
        fila["desglosada"] = bool(fila["armados"]) or bool(fila["segunda"])

    negativos = [f for f in filas if f["stock"] < 0]
    return templates.TemplateResponse(
        request,
        "deposito_stock_sistema.html",
        {
            "filas": filas,
            "articulos_negativos": len(negativos),
            "bultos_sin_lote": -sum(f["stock"] for f in negativos),
            "reingresos_total": reingresos_total,
            "segunda_total": sum(f.get("segunda", 0) for f in filas),
        },
    )


@app.get("/administracion/stock/sistema/{articulo_id}")
def ver_stock_articulo_deposito(request: Request, articulo_id: int):
    """El detalle FIFO de un artículo: qué queda de cada lote (guía, reingreso, ajuste) y cuánto salió sin lote.

    El reparto se calcula acá, cada vez (core/stock.py): las salidas
    consumen del lote más viejo primero. La ÚNICA salida que puede no
    seguir ese orden es la que alguien señaló a propósito —una merma
    dirigida, o el desglose que el operario corrigió al cargar una guía
    R—, y esa elección queda guardada, no se adivina desde acá.
    """
    try:
        articulo = obtener_articulo(articulo_id)
        if articulo is None:
            raise HTTPException(status_code=404, detail="Artículo no encontrado")
        entradas, salidas = entradas_y_salidas_stock_articulo(articulo_id)
    except HTTPException:
        raise
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    reparto = repartir_fifo(entradas, salidas_para_reparto(salidas))
    con_resto = [l for l in reparto["lotes"] if l["restante"] > 0]
    agotados = [l for l in reparto["lotes"] if l["restante"] <= 0]
    return templates.TemplateResponse(
        request,
        "deposito_stock_articulo.html",
        {
            "articulo": articulo,
            "lotes": con_resto,
            "agotados": agotados,
            "sin_lote": reparto["sin_lote"],
            "stock": reparto["stock"],
            "total_salidas": sum(float(s["cantidad"]) for s in salidas),
        },
    )


def _renderizar_pantalla_ajustar_stock(request: Request, *, precarga=None, aviso=None, error=None, status_code: int = 200):
    try:
        articulos = listar_articulos()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    return templates.TemplateResponse(
        request,
        "deposito_stock_ajustar.html",
        {"articulos": articulos, "precarga": precarga or {}, "aviso": aviso, "error": error},
        status_code=status_code,
    )


def _numero_query_o_none(texto: str | None) -> float | None:
    if texto is None or not texto.strip():
        return None
    try:
        return float(texto)
    except ValueError:
        return None


@app.get("/administracion/stock/ajustar")
def ver_ajustar_stock_deposito(
    request: Request,
    aviso: str | None = None,
    motivo: str | None = None,
    articulo_id: str | None = None,
    contado: str | None = None,
    stock_conteo: str | None = None,
    fecha_conteo: str | None = None,
):
    """Ajuste de stock. Sin precarga: pantalla en blanco (o solo el motivo, para la carga en cadena del
    stock inicial). Con precarga (viene del Cotejo): calcula el ajuste.

    La cantidad precargada es contado − stock ACTUAL (no la diferencia
    congelada del cotejo): "ajustar a lo contado" tiene que dejar el
    stock en lo contado, aunque hayan entrado movimientos después del
    conteo. Si el stock cambió desde el conteo, la pantalla lo dice con
    todos los números ANTES de guardar — mismo diseño que Vacíos.
    """
    precarga = {"motivo": motivo.strip()} if motivo and motivo.strip() else {}
    contado_valor = _numero_query_o_none(contado)
    if articulo_id and articulo_id.strip().isdigit() and contado_valor is not None:
        try:
            stock_actual = stock_deposito_de_articulo(int(articulo_id))
        except Exception as error_db:
            raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

        precarga = {
            "articulo_id": articulo_id,
            "cantidad": round(contado_valor - stock_actual, 2),
            "motivo": f"Ajuste a lo contado: conteo del {fecha_conteo or '?'} ({_formatear_numero(contado_valor)} contados)",
        }
        stock_foto = _numero_query_o_none(stock_conteo)
        if stock_foto is not None and stock_foto != stock_actual:
            precarga["aviso_conteo"] = (
                f"Ojo: el conteo fue del {fecha_conteo or '?'} con {_formatear_numero(contado_valor)} contados y el "
                f"sistema decía {_formatear_numero(stock_foto)}. Desde entonces hubo movimientos: el stock actual es "
                f"{_formatear_numero(stock_actual)}, así que el ajuste sugerido para dejarlo en lo contado es "
                f"{'+' if contado_valor - stock_actual > 0 else ''}{_formatear_numero(round(contado_valor - stock_actual, 2))} "
                f"(no la diferencia que viste en el Cotejo)."
            )
    return _renderizar_pantalla_ajustar_stock(request, precarga=precarga, aviso=aviso)


@app.post("/administracion/stock/ajustar")
def ajustar_stock_deposito_ruta(
    request: Request,
    articulo_id: str = Form(""),
    cantidad: str = Form(""),
    motivo: str = Form(""),
):
    """Guarda un ajuste de stock: cantidad en bultos con signo (nunca 0) y motivo OBLIGATORIO. Nunca pisa: movimiento nuevo."""
    motivo_limpio = re.sub(r"\s+", " ", motivo).strip()
    error = None
    cantidad_valor = None

    texto_cantidad = cantidad.strip()
    if not texto_cantidad:
        error = "La cantidad del ajuste es obligatoria."
    else:
        try:
            cantidad_valor = float(texto_cantidad)
        except ValueError:
            error = "La cantidad del ajuste tiene que ser un número (positivo o negativo)."
        else:
            if cantidad_valor == 0:
                error = "Un ajuste de 0 no ajusta nada."

    if not error and not motivo_limpio:
        error = "El motivo es obligatorio: sin motivo no se guarda el ajuste."

    articulo = None
    if not error:
        try:
            articulo = obtener_articulo(int(articulo_id)) if articulo_id.strip().isdigit() else None
        except Exception as error_db:
            raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db
        if articulo is None:
            error = "Elegí un artículo válido."

    if error:
        precarga = {"articulo_id": articulo_id, "cantidad": cantidad, "motivo": motivo_limpio}
        return _renderizar_pantalla_ajustar_stock(request, precarga=precarga, error=error, status_code=400)

    try:
        stock_nuevo = crear_movimiento_stock(
            articulo["id"], "ajuste", cantidad_valor, motivo_limpio, _hoy_argentina()
        )
    except Exception as error_db:
        return _renderizar_pantalla_ajustar_stock(
            request, error=f"No se pudo guardar el ajuste: {error_db}", status_code=500
        )

    aviso = (
        f"Ajuste guardado: {'+' if cantidad_valor > 0 else ''}{_formatear_numero(cantidad_valor)} bultos de "
        f"{articulo['nombre']}. El stock quedó en {_formatear_numero(stock_nuevo)}."
    )
    # El motivo vuelve en la URL para poder encadenar varios ajustes con el
    # mismo motivo sin reescribirlo. (El stock inicial del corte NO se carga
    # más por acá: tiene pantalla y tipo propios — ver /administracion/stock/inicial.)
    return RedirectResponse(
        url=f"/administracion/stock/ajustar?{urlencode({'aviso': aviso, 'motivo': motivo_limpio})}", status_code=303
    )


# --- El stock inicial del corte ---
# Se carga UNA vez, a mano, el día antes del corte: lo que hay en el piso
# pasa a existir para el sistema. Va en Administración y no en Depósito
# porque lleva COSTO, y el operario no ve números del sistema.


def _fichas_por_articulo() -> dict[str, list[dict]]:
    """Las fichas elegibles al cargar cajas ya armadas, por articulo_id (como texto).

    Acá la ficha se elige por ARTÍCULO y no por (cliente, artículo) como
    en la guía R: el que carga está mirando una caja concreta en el piso y
    ya sabe de quién es. Pedirle el cliente primero sería un campo más por
    renglón, y son muchos renglones seguidos.

    Por eso cada opción lleva el cliente adentro del nombre: sin él,
    "Banana Bolivia" de dos clientes distintos serían dos opciones
    idénticas.
    """
    nombres = {cliente["id"]: cliente["nombre"] for cliente in listar_clientes()}
    por_articulo: dict[str, list[dict]] = {}
    for ficha in listar_fichas_de_todos_los_clientes():
        sufijo = SUFIJOS_FICHA_REPROCESO.get(ficha.get("unidad_venta"), "")
        kilaje = (f"{_formatear_numero(ficha['contenido_caja'])} {sufijo}".strip()
                  if ficha.get("contenido_caja") else "")
        por_articulo.setdefault(str(ficha["articulo_id"]), []).append(
            {
                "id": ficha["id"],
                "cliente_id": ficha["cliente_id"],
                "nombre": f"{nombres.get(ficha['cliente_id'], 'Cliente sin nombre')} — {_nombre_de_ficha(ficha)}",
                "kilaje": kilaje,
            }
        )
    for fichas in por_articulo.values():
        fichas.sort(key=lambda f: f["nombre"])
    return por_articulo


def _renderizar_stock_inicial(
    request: Request, *, articulo_id=None, precarga=None, aviso=None, error=None, status_code: int = 200
):
    """La pantalla del stock inicial: el artículo elegido ARRIBA y fijo, y abajo lo ya cargado con su total.

    El artículo viaja en la URL a propósito. Se carga renglón tras renglón
    y son muchos: si cada guardado devolviera la pantalla en blanco,
    habría que reelegirlo cada vez.
    """
    try:
        contexto = {
            "articulos": listar_articulos(),
            "fichas_por_articulo": _fichas_por_articulo(),
            "cargado": listar_stock_inicial(),
            "fecha_corte": fecha_corte(),
            "articulo_id": str(articulo_id) if articulo_id is not None else "",
            "precarga": precarga or {},
            "aviso": aviso,
            "error": error,
        }
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    return templates.TemplateResponse(
        request, "administracion_stock_inicial.html", contexto, status_code=status_code
    )


def _volver_a_stock_inicial(articulo_id, aviso=None, error=None):
    """Vuelve a la pantalla con el MISMO artículo puesto y el foco en la carga (#carga).

    El ancla no es un detalle: en el celular, sin ella cada guardado deja
    la pantalla arriba de todo y hay que scrollear hasta el formulario
    otra vez, renglón por renglón.
    """
    parametros = {"articulo_id": str(articulo_id or "")}
    if aviso:
        parametros["aviso"] = aviso
    if error:
        parametros["error"] = error
    return RedirectResponse(url=f"/administracion/stock/inicial?{urlencode(parametros)}#carga", status_code=303)


@app.get("/administracion/stock/inicial")
def ver_stock_inicial(
    request: Request,
    articulo_id: str | None = None,
    aviso: str | None = None,
    error: str | None = None,
):
    return _renderizar_stock_inicial(request, articulo_id=articulo_id, aviso=aviso, error=error)


@app.post("/administracion/stock/inicial/sueltos")
def cargar_stock_inicial_sueltos(
    request: Request,
    articulo_id: str = Form(""),
    bultos: str = Form(""),
    costo_por_bulto: str = Form(""),
):
    """Los bultos SIN PROCESAR que hay en el piso, con su costo por bulto."""
    error, bultos_valor = _validar_bultos_positivos(bultos, "del stock inicial")
    costo_valor = None
    if not error:
        error, costo_valor = _validar_costo_stock_inicial(costo_por_bulto, "por bulto")

    articulo = None
    if not error:
        try:
            articulo = obtener_articulo(int(articulo_id)) if articulo_id.strip().isdigit() else None
        except Exception as error_db:
            raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db
        if articulo is None:
            error = "Elegí un artículo válido."

    if error:
        return _renderizar_stock_inicial(
            request,
            articulo_id=articulo_id,
            precarga={"bultos": bultos, "costo_por_bulto": costo_por_bulto},
            error=error,
            status_code=400,
        )

    try:
        crear_stock_inicial(articulo["id"], bultos_valor, costo_valor, fecha_corte())
    except Exception as error_db:
        return _renderizar_stock_inicial(
            request, articulo_id=articulo_id, error=f"No se pudo guardar: {error_db}", status_code=500
        )

    return _volver_a_stock_inicial(
        articulo["id"],
        aviso=(f"Cargados {_formatear_numero(bultos_valor)} bultos sueltos de {articulo['nombre']} "
               f"a {_formatear_moneda(costo_valor)} cada uno."),
    )


@app.post("/administracion/stock/inicial/armadas")
def cargar_stock_inicial_armadas(
    request: Request,
    articulo_id: str = Form(""),
    ficha_id: str = Form(""),
    cajas: str = Form(""),
    costo_por_caja: str = Form(""),
):
    """Las cajas YA ARMADAS que hay en el piso: una guía R de tipo inicial, que produce sin consumir."""
    error, cajas_valor = _validar_bultos_positivos(cajas, "ya armadas")
    costo_valor = None
    if not error:
        error, costo_valor = _validar_costo_stock_inicial(costo_por_caja, "por caja")

    articulo = None
    ficha = None
    if not error:
        try:
            articulo = obtener_articulo(int(articulo_id)) if articulo_id.strip().isdigit() else None
            fichas = _fichas_por_articulo().get(str(articulo_id).strip(), []) if articulo else []
            ficha = next((f for f in fichas if str(f["id"]) == ficha_id.strip()), None)
        except Exception as error_db:
            raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db
        if articulo is None:
            error = "Elegí un artículo válido."
        elif ficha is None:
            # Una caja armada en el piso YA es de una ficha concreta: se la
            # puede ir a mirar. Dejar cargarla sin ficha sería crear el
            # "sin asignar" que la etapa 1 vino a poder completar.
            error = "Elegí de qué ficha son estas cajas: una caja ya armada siempre es de alguna."

    if error:
        return _renderizar_stock_inicial(
            request,
            articulo_id=articulo_id,
            precarga={"ficha_id": ficha_id, "cajas": cajas, "costo_por_caja": costo_por_caja},
            error=error,
            status_code=400,
        )

    try:
        crear_reproceso_inicial(
            articulo["id"], cajas_valor, costo_valor, fecha_corte(),
            ficha_id=ficha["id"], cliente_id=ficha["cliente_id"],
        )
    except Exception as error_db:
        return _renderizar_stock_inicial(
            request, articulo_id=articulo_id, error=f"No se pudo guardar: {error_db}", status_code=500
        )

    return _volver_a_stock_inicial(
        articulo["id"],
        aviso=(f"Cargadas {_formatear_numero(cajas_valor)} cajas armadas de {ficha['nombre']} "
               f"a {_formatear_moneda(costo_valor)} cada una."),
    )


@app.post("/administracion/stock/inicial/anular")
def anular_stock_inicial_ruta(
    request: Request,
    clase: str = Form(""),
    renglon_id: str = Form(""),
    articulo_id: str = Form(""),
):
    """Saca un renglón mal cargado. Se carga a mano y de apuro: equivocarse es parte del trabajo."""
    if not renglon_id.strip().isdigit() or clase not in ("sueltos", "armadas"):
        return _volver_a_stock_inicial(articulo_id, error="No se entendió qué renglón anular.")
    try:
        anular_renglon_stock_inicial(clase, int(renglon_id))
    except ValueError as error_valor:
        return _volver_a_stock_inicial(articulo_id, error=str(error_valor))
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db
    return _volver_a_stock_inicial(articulo_id, aviso="Renglón anulado: no cuenta más en el total.")


def _validar_bultos_positivos(cantidad: str, que: str) -> tuple[str | None, float | None]:
    """Bultos de merma/reingreso: número positivo obligatorio (acá el signo lo pone el tipo, no la persona)."""
    texto = cantidad.strip()
    if not texto:
        return f"La cantidad de bultos {que} es obligatoria.", None
    try:
        valor = float(texto)
    except ValueError:
        return "La cantidad de bultos tiene que ser un número.", None
    if valor <= 0:
        return "La cantidad de bultos tiene que ser mayor a cero.", None
    return None, valor


def _validar_costo_stock_inicial(costo: str, que: str) -> tuple[str | None, float | None]:
    """El costo del stock inicial: obligatorio y de cero o más.

    Obligatorio a propósito, y sin default. Es lo único que este stock no
    puede recuperar después: no hay compra a la que ir a buscarle el
    importe, así que un lote que entra sin costo deja sin costear todo lo
    que salga de él, para siempre.
    """
    texto = costo.strip().replace("$", "").replace(" ", "")
    if not texto:
        return f"El costo {que} es obligatorio: sin él, todo lo que salga de este stock queda sin costear.", None
    try:
        valor = float(texto)
    except ValueError:
        return f"El costo {que} tiene que ser un número.", None
    if valor < 0:
        return f"El costo {que} no puede ser negativo.", None
    return None, valor


# Los tipos de lote del detalle FIFO por artículo, para validar a mano a
# cuál se dirige una merma (el value del selector es "tipo:id").
TIPOS_LOTE_STOCK = ("guia", "reproceso", "reingreso_rechazo", "ajuste", "stock_inicial")


def _renderizar_pantalla_merma(
    request: Request, *, precarga=None, aviso=None, error=None, articulo_id=None, status_code: int = 200
):
    """La pantalla de merma. Con artículo elegido trae sus lotes con resto, para poder dirigir la merma a uno."""
    articulo_elegido = None
    lotes: list[dict] = []
    try:
        articulos = listar_articulos()
        if articulo_id is not None and str(articulo_id).strip().isdigit():
            articulo_elegido = obtener_articulo(int(articulo_id))
            if articulo_elegido is not None:
                lotes = _lotes_con_resto(articulo_elegido["id"])
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    return templates.TemplateResponse(
        request,
        "deposito_stock_merma.html",
        {
            "articulos": articulos,
            "articulo_elegido": articulo_elegido,
            "lotes": lotes,
            "precarga": precarga or {},
            "aviso": aviso,
            "error": error,
        },
        status_code=status_code,
    )


def _lotes_con_resto(articulo_id: int) -> list[dict]:
    """Los lotes de un artículo que todavía tienen bultos, para elegir a mano cuál se pudrió.

    Rejuega el FIFO como todo el módulo (nada guardado) y describe cada
    lote con lo que el operario reconoce en el piso: la guía y el
    proveedor, o la guía R con el cliente para el que se armó.
    """
    entradas, salidas = entradas_y_salidas_stock_articulo(articulo_id)
    reparto = repartir_fifo(entradas, salidas_para_reparto(salidas))

    lotes = []
    for lote in reparto["lotes"]:
        if lote["restante"] <= 0:
            continue
        if lote["tipo_lote"] == "reproceso":
            etiqueta = f"Guía R{lote['origen_id']}"
            if lote.get("detalle"):
                etiqueta += f" armada para {lote['detalle']}"
        elif lote["tipo_lote"] == "guia":
            etiqueta = f"Compra de {lote.get('detalle') or 'proveedor sin nombre'}"
        else:
            etiqueta = ETIQUETAS_MOVIMIENTO_STOCK.get(lote["tipo_lote"], lote["tipo_lote"])
        lotes.append(
            {
                "tipo": lote["tipo_lote"],
                "origen_id": lote["origen_id"],
                "restante": lote["restante"],
                # Una compra sin guía no tiene fecha de guía: vale la del
                # hecho (su recepción), igual que en el detalle por lote.
                "fecha": lote["fecha_lote"] or lote["fecha_orden"],
                "etiqueta": etiqueta,
            }
        )
    return lotes


@app.get("/deposito/stock/merma")
def ver_merma_stock(request: Request, aviso: str | None = None, articulo_id: str | None = None):
    """La carga de merma. Con un artículo elegido, muestra además sus lotes para poder dirigir la merma a uno."""
    return _renderizar_pantalla_merma(request, aviso=aviso, articulo_id=articulo_id)


@app.post("/deposito/stock/merma")
def cargar_merma_stock_ruta(
    request: Request,
    articulo_id: str = Form(""),
    cantidad: str = Form(""),
    motivo: str = Form(""),
    lote: str = Form(""),
):
    """El operario da de baja cajones que se tiraron: siempre negativa, con motivo obligatorio.

    lote es opcional ("tipo:id"): con el default vacío la merma sale del
    lote más viejo, como siempre — el operario no tiene que pensar salvo
    que sepa exactamente cuál se pudrió. Elegido, la merma se descuenta
    de ESE lote (y se cuesta al costo de ese lote en la Rentabilidad
    Real); lo que el lote no cubra cae al FIFO: registra y delata, jamás
    traba.

    Pantalla de OPERARIO: el aviso repite solo lo que cargó — jamás el
    stock resultante (mismo criterio que el Stock Físico de Vacíos).
    """
    motivo_limpio = re.sub(r"\s+", " ", motivo).strip()
    error, cantidad_valor = _validar_bultos_positivos(cantidad, "tirados")
    if not error and not motivo_limpio:
        error = "El motivo es obligatorio: sin motivo no se guarda la merma."

    articulo = None
    if not error:
        try:
            articulo = obtener_articulo(int(articulo_id)) if articulo_id.strip().isdigit() else None
        except Exception as error_db:
            raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db
        if articulo is None:
            error = "Elegí un artículo válido."

    lote_tipo, lote_origen_id, lote_etiqueta = None, None, None
    if not error and lote.strip():
        tipo, _, origen = lote.partition(":")
        if tipo not in TIPOS_LOTE_STOCK or not origen.isdigit():
            error = "Ese lote no es válido: elegí uno de la lista o dejá el más viejo."
        else:
            lote_tipo, lote_origen_id = tipo, int(origen)
            elegido = next(
                (l for l in _lotes_con_resto(articulo["id"])
                 if l["tipo"] == lote_tipo and l["origen_id"] == lote_origen_id),
                None,
            )
            if elegido is None:
                error = "Ese lote ya no tiene bultos: volvé a elegir."
            else:
                lote_etiqueta = elegido["etiqueta"]

    if error:
        precarga = {
            "articulo_id": articulo_id, "cantidad": cantidad, "motivo": motivo_limpio, "lote": lote,
        }
        return _renderizar_pantalla_merma(
            request, precarga=precarga, articulo_id=articulo_id, error=error, status_code=400
        )

    try:
        crear_movimiento_stock(
            articulo["id"], "merma", -cantidad_valor, motivo_limpio, _hoy_argentina(),
            lote_tipo=lote_tipo, lote_origen_id=lote_origen_id,
        )
    except Exception as error_db:
        return _renderizar_pantalla_merma(
            request, articulo_id=articulo_id, error=f"No se pudo guardar la merma: {error_db}", status_code=500
        )

    aviso = f"Merma guardada: {_formatear_numero(cantidad_valor)} bultos de {articulo['nombre']} tirados ({motivo_limpio})."
    if lote_etiqueta:
        aviso += f" Salieron de: {lote_etiqueta}."
    return RedirectResponse(url=f"/deposito/stock/merma?{urlencode({'aviso': aviso})}", status_code=303)


def _costo_congelado_para_reingreso(renglon: dict) -> float | None:
    """El costo por bulto del reingreso, CONGELADO del listado anclado a la fecha del pedido de origen.

    El costo_actual del listado (el mismo de Márgenes y las dos
    rentabilidades) es POR UNIDAD de venta: se pasa a bultos con el kilaje
    REAL del renglón (kilos enviados / bultos armados) o, si el renglón no
    tiene kilaje, con el contenido de la ficha. None si no hay costo o
    kilaje posible: el lote queda como reingreso sin costo (visible en el
    afuera de la Real) — nunca un número inventado.
    """
    try:
        listado = calcular_listado_para_negociar_precios(
            renglon["cliente_id"],
            datetime.combine(renglon["fecha_pedido"], time(12, 0), tzinfo=ARGENTINA),
        )
        fila = next((f for f in listado if f["ficha_id"] == renglon["ficha_id"]), None)
        costo_unidad = fila.get("costo_actual") if fila else None
        if costo_unidad is None:
            return None
        kilos = renglon.get("kilos_enviados")
        armados = renglon.get("bultos_armados")
        if kilos is not None and armados:
            kilos_por_bulto = float(kilos) / float(armados)
        else:
            fichas = listar_fichas_por_cliente(renglon["cliente_id"])
            contenido = next(
                (f.get("contenido_caja") for f in fichas if f["id"] == renglon["ficha_id"]), None
            )
            if not contenido:
                return None
            kilos_por_bulto = float(contenido)
        return round(float(costo_unidad) * kilos_por_bulto, 2)
    except Exception:
        logger.exception("No se pudo congelar el costo del reingreso del renglón %s", renglon["id"])
        return None


DESTINOS_REINGRESO = ("stock", "segunda", "reproceso")


def _renderizar_form_reingreso(request: Request, renglon: dict, *, precarga=None, error=None, status_code: int = 200):
    """El paso 3 (la carga en sí) con el tope calculado por el server: armado − ya devuelto."""
    contexto = {
        "paso": "form",
        "renglon": renglon,
        "tope": float(renglon["bultos_armados"]) - float(renglon["ya_devuelto"]),
        "precarga": precarga or {},
        "hoy": _hoy_argentina().isoformat(),
        "aviso": None,
        "error": error,
    }
    return templates.TemplateResponse(request, "deposito_stock_reingreso.html", contexto, status_code=status_code)


@app.get("/deposito/stock/reingreso")
def ver_reingreso_stock(
    request: Request,
    pedido_id: str | None = None,
    sucursal: str | None = None,
    renglon_id: str | None = None,
    oc: str | None = None,
    aviso: str | None = None,
):
    """Reingreso por rechazo en tres pasos: pedido de origen → renglón armado → carga.

    Pantalla de OPERARIO: todo lo que muestra (fecha, sucursal, OC,
    renglones y bultos armados, lo ya devuelto) ya es suyo — es lo mismo
    que ve en Armar Pedido más sus propias cargas. Ni costos ni stock del
    sistema, nunca.
    """
    contexto_base = {"aviso": aviso, "error": None, "hoy": _hoy_argentina().isoformat(), "precarga": {}}

    renglon_id_valor = _id_opcional_desde_query(renglon_id)
    if renglon_id_valor is not None:
        try:
            renglon = obtener_renglon_para_reingreso(renglon_id_valor)
        except Exception as error_db:
            raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db
        if renglon is None:
            raise HTTPException(status_code=404, detail="Ese renglón no está disponible para reingreso (¿el pedido fue reemplazado o anulado?)")
        return _renderizar_form_reingreso(request, renglon)

    pedido_id_valor = _id_opcional_desde_query(pedido_id)
    if pedido_id_valor is not None and (sucursal or "").strip():
        try:
            renglones = listar_renglones_para_reingreso(pedido_id_valor, sucursal.strip())
            pedidos = listar_pedidos_para_reingreso()
        except Exception as error_db:
            raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db
        pedido = next(
            (p for p in pedidos if p["pedido_id"] == pedido_id_valor and p["sucursal"] == sucursal.strip()), None
        )
        if pedido is None or not renglones:
            raise HTTPException(status_code=404, detail="Ese pedido no tiene renglones armados para reingreso.")
        contexto = dict(contexto_base, paso="renglones", pedido=pedido, renglones=renglones)
        return templates.TemplateResponse(request, "deposito_stock_reingreso.html", contexto)

    oc_limpia = (oc or "").strip() or None
    try:
        pedidos = listar_pedidos_para_reingreso(oc=oc_limpia)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db
    contexto = dict(contexto_base, paso="pedidos", pedidos=pedidos, oc=oc_limpia)
    return templates.TemplateResponse(request, "deposito_stock_reingreso.html", contexto)


@app.post("/deposito/stock/reingreso")
def cargar_reingreso_stock_ruta(
    request: Request,
    renglon_id: str = Form(""),
    cantidad: str = Form(""),
    motivo: str = Form(""),
    fecha: str = Form(""),
    destino: str = Form("stock"),
    cajones: str = Form(""),
):
    """Mercadería que el cliente devolvió: entra al stock MARCADA como rechazo y VINCULADA a su renglón de pedido.

    El cliente y el artículo salen del pedido (no se cargan a mano). Tope
    DURO del server: armado − ya devuelto acumulado — se valida acá, no en
    el HTML. El costo queda congelado del listado anclado a la fecha del
    pedido de origen, calculado por el server: jamás pasa por la pantalla.
    La fecha es editable con hoy por default: el camión puede volver un
    día y cargarse al siguiente — con la fecha real no se desordena el
    FIFO ni el cotejo del día anterior. Pantalla de OPERARIO: el aviso
    repite solo lo que cargó, jamás el stock resultante ni el costo.
    """
    try:
        renglon = obtener_renglon_para_reingreso(int(renglon_id)) if renglon_id.strip().isdigit() else None
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db
    if renglon is None:
        raise HTTPException(status_code=404, detail="Ese renglón no está disponible para reingreso (¿el pedido fue reemplazado o anulado?)")

    motivo_limpio = re.sub(r"\s+", " ", motivo).strip()
    error, cantidad_valor = _validar_bultos_positivos(cantidad, "devueltos")
    if not error and not motivo_limpio:
        error = "El motivo es obligatorio: sin motivo no se guarda el reingreso."

    tope = float(renglon["bultos_armados"]) - float(renglon["ya_devuelto"])
    if not error and cantidad_valor > tope:
        ya_devuelto = float(renglon["ya_devuelto"])
        error = (
            f"No se puede devolver más de lo armado: de {renglon['articulo_nombre']} se armaron "
            f"{_formatear_numero(renglon['bultos_armados'])} bultos"
            + (f" y ya se devolvieron {_formatear_numero(ya_devuelto)}" if ya_devuelto else "")
            + f" — el tope es {_formatear_numero(tope)}."
        )

    fecha_valor = None
    if not error:
        hoy = _hoy_argentina()
        if not fecha.strip():
            fecha_valor = hoy
        else:
            try:
                fecha_valor = date.fromisoformat(fecha.strip())
            except ValueError:
                error = "La fecha del reingreso no es válida."
            else:
                if fecha_valor > hoy:
                    error = "La fecha del reingreso no puede ser futura."

    # El DESTINO se decide acá, al cargar, no después: queda en stock (el
    # costo no se pierde, se va a vender), pasa a segunda tal cual, o
    # vuelve a cajón grande y esos cajones van a segunda.
    destino_valor = destino if destino in DESTINOS_REINGRESO else "stock"
    bultos_segunda = None
    if not error and destino_valor == "segunda":
        bultos_segunda = cantidad_valor  # la misma caja, sin tocar
    elif not error and destino_valor == "reproceso":
        error, bultos_segunda = _validar_bultos_positivos(cajones, "cajones que salieron")

    if error:
        precarga = {
            "cantidad": cantidad, "motivo": motivo_limpio, "fecha": fecha,
            "destino": destino_valor, "cajones": cajones,
        }
        return _renderizar_form_reingreso(request, renglon, precarga=precarga, error=error, status_code=400)

    costo_por_bulto = _costo_congelado_para_reingreso(renglon)
    try:
        crear_movimiento_stock(
            renglon["articulo_id"], "reingreso_rechazo", cantidad_valor, motivo_limpio, fecha_valor,
            cliente_id=renglon["cliente_id"],
            pedido_renglon_id=renglon["id"],
            costo_por_bulto=costo_por_bulto,
            destino_rechazo=destino_valor,
            bultos_segunda=bultos_segunda,
        )
    except Exception as error_db:
        return _renderizar_form_reingreso(
            request, renglon, error=f"No se pudo guardar el reingreso: {error_db}", status_code=500
        )

    # El aviso repite lo que cargó y QUÉ SE HIZO con la mercadería, con
    # las palabras de la pantalla — nunca el stock resultante ni el costo.
    cierres = {
        "stock": "Queda en stock para volver a mandarla.",
        "segunda": f"Pasó a segunda tal cual: {_formatear_numero(bultos_segunda or 0)} bultos al pool, para remitir al Puesto.",
        "reproceso": (
            f"Volvió a cajón grande: salieron {_formatear_numero(bultos_segunda or 0)} cajones, "
            "que entran al pool de segunda para remitir al Puesto."
        ),
    }
    aviso = (
        f"Reingreso guardado: {_formatear_numero(cantidad_valor)} bultos de {renglon['articulo_nombre']} "
        f"del pedido del {renglon['fecha_pedido'].strftime('%d/%m')} ({renglon['sucursal']}) "
        f"que devolvió {renglon['cliente_nombre']} el {fecha_valor.strftime('%d/%m')} ({motivo_limpio}). "
        + cierres[destino_valor]
    )
    return RedirectResponse(url=f"/deposito/stock/reingreso?{urlencode({'aviso': aviso})}", status_code=303)


ETIQUETAS_MOVIMIENTO_STOCK = {
    "ajuste": "Ajuste",
    "merma": "Merma",
    "reingreso_rechazo": "Reingreso",
    "stock_inicial": "Stock inicial",
}


@app.get("/administracion/stock/movimientos")
def ver_movimientos_stock(request: Request, fecha_desde: str | None = None, fecha_hasta: str | None = None):
    """Movimientos de stock (control): ajustes, mermas y reingresos de cualquier fecha, con anular por baja lógica.

    Corregir = anular el movimiento equivocado y cargarlo de nuevo bien
    desde su pantalla — nunca editar ni borrar. Acá SÍ se ve el stock
    (la foto del sistema que quedó grabada en cada movimiento).
    """
    desde, hasta = _rango_fechas_movimientos(fecha_desde, fecha_hasta)
    try:
        movimientos = listar_movimientos_stock_por_rango(desde, hasta)
        remitos = listar_remitos_segunda_por_rango(desde, hasta)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    for m in movimientos:
        m["etiqueta_tipo"] = ETIQUETAS_MOVIMIENTO_STOCK.get(m["tipo"], m["tipo"])
        m["url_anular"] = f"/administracion/stock/movimientos/{m['id']}/anular"
    # Los remitos de segunda entran al mismo listado, con su propia pill y
    # su propio anular: un solo lugar de control para todo lo cargado a mano.
    for r in remitos:
        r.update(
            tipo="remito_segunda",
            etiqueta_tipo="Remito 2ª",
            cantidad=-float(r["bultos"]),
            motivo="Segunda remitida al Puesto",
            cliente_nombre=None,
            stock_sistema=None,
            url_anular=f"/administracion/stock/movimientos/remitos/{r['id']}/anular",
        )
    movimientos = sorted(
        movimientos + remitos, key=lambda m: (m["fecha_operacion"], m["creado_en"]), reverse=True
    )
    return templates.TemplateResponse(
        request,
        "deposito_stock_movimientos.html",
        {
            "movimientos": movimientos,
            "fecha_desde": desde.isoformat(),
            "fecha_hasta": hasta.isoformat(),
        },
    )


@app.post("/administracion/stock/movimientos/{movimiento_id}/anular")
def anular_movimiento_stock_ruta(
    movimiento_id: int,
    fecha_desde: str = Form(""),
    fecha_hasta: str = Form(""),
):
    try:
        anular_movimiento_stock(movimiento_id)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"No se pudo anular el movimiento: {error_db}") from error_db

    return RedirectResponse(
        url=f"/administracion/stock/movimientos?{urlencode({'fecha_desde': fecha_desde, 'fecha_hasta': fecha_hasta})}",
        status_code=303,
    )


@app.post("/administracion/stock/movimientos/remitos/{remito_id}/anular")
def anular_remito_segunda_ruta(
    remito_id: int,
    fecha_desde: str = Form(""),
    fecha_hasta: str = Form(""),
):
    try:
        anular_remito_segunda(remito_id)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"No se pudo anular el remito: {error_db}") from error_db

    return RedirectResponse(
        url=f"/administracion/stock/movimientos?{urlencode({'fecha_desde': fecha_desde, 'fecha_hasta': fecha_hasta})}",
        status_code=303,
    )


def _renderizar_pantalla_stock_fisico_deposito(
    request: Request, *, articulo_id=None, error=None, aviso=None, status_code: int = 200
):
    try:
        contexto = {
            "articulos": listar_articulos(),
            "fichas_por_articulo": _fichas_por_articulo(),
            # listar_conteos_stock_de_fecha NO trae stock_sistema, a propósito:
            # esta pantalla la ve el operario y el número del sistema no puede
            # viajar ni escondido en su HTML (control cruzado).
            "contados_hoy": listar_conteos_stock_de_fecha(_hoy_argentina()),
            "articulo_id": str(articulo_id) if articulo_id is not None else "",
            "error": error,
            "aviso": aviso,
        }
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    return templates.TemplateResponse(
        request, "deposito_stock_fisico.html", contexto, status_code=status_code
    )


@app.get("/deposito/stock/fisico")
def ver_stock_fisico_deposito(request: Request, articulo_id: str | None = None, aviso: str | None = None):
    return _renderizar_pantalla_stock_fisico_deposito(request, articulo_id=articulo_id, aviso=aviso)


@app.post("/deposito/stock/fisico")
def cargar_stock_fisico_deposito_ruta(
    request: Request,
    articulo_id: str = Form(""),
    cantidad: str = Form(""),
    que_conto: str = Form(""),
):
    """El operario carga lo que CONTÓ. Se acepta 0 (contó y no hay ninguno). Si se equivoca, carga de nuevo: vale el último.

    No es obligatorio todos los días: es un control disponible. El aviso
    repite SOLO lo contado — jamás el stock del sistema.

    que_conto es "sueltos" o el id de una ficha. NO se valida contra lo
    que el sistema cree tener: el conteo es DECLARATIVO. Si cuenta cajas
    de una ficha de la que el sistema no tiene nada, se guarda igual y el
    Cotejo muestra la diferencia — que es justo para lo que está. Lo
    único que se valida es que la ficha exista y sea de ESE artículo:
    una ficha de otro artículo no es un conteo raro, es un dato roto.
    """
    texto_cantidad = cantidad.strip()
    error = None
    cantidad_valor = None
    if not texto_cantidad:
        error = "La cantidad contada es obligatoria."
    else:
        try:
            cantidad_valor = float(texto_cantidad)
        except ValueError:
            error = "La cantidad contada tiene que ser un número."
        else:
            if cantidad_valor < 0:
                error = "La cantidad contada no puede ser negativa."

    articulo = None
    ficha = None
    if not error:
        try:
            articulo = obtener_articulo(int(articulo_id)) if articulo_id.strip().isdigit() else None
            if articulo is not None and que_conto.strip() and que_conto.strip() != "sueltos":
                fichas = _fichas_por_articulo().get(str(articulo_id).strip(), [])
                ficha = next((f for f in fichas if str(f["id"]) == que_conto.strip()), None)
        except Exception as error_db:
            raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db
        if articulo is None:
            error = "Elegí un artículo válido."
        elif not que_conto.strip():
            error = "Elegí qué contaste: los bultos sueltos o las cajas de una ficha."
        elif que_conto.strip() != "sueltos" and ficha is None:
            error = "Esa ficha no es de este artículo."

    if error:
        return _renderizar_pantalla_stock_fisico_deposito(
            request, articulo_id=articulo_id, error=error, status_code=400
        )

    try:
        crear_conteo_stock(articulo["id"], cantidad_valor, ficha_id=ficha["id"] if ficha else None)
    except Exception as error_db:
        return _renderizar_pantalla_stock_fisico_deposito(
            request, articulo_id=articulo_id, error=f"No se pudo guardar el conteo: {error_db}", status_code=500
        )

    que = f"cajas de {ficha['nombre']}" if ficha else f"bultos sueltos de {articulo['nombre']}"
    aviso = f"Conteo guardado: {_formatear_numero(cantidad_valor)} {que}."
    # El artículo vuelve puesto: de un mismo artículo se cuentan los
    # sueltos y después las cajas de cada ficha, uno atrás de otro.
    return RedirectResponse(
        url=f"/deposito/stock/fisico?{urlencode({'articulo_id': articulo['id'], 'aviso': aviso})}#carga",
        status_code=303,
    )


@app.get("/administracion/stock/cotejo")
def ver_cotejo_stock(request: Request):
    """Cotejo (control): el último conteo físico de cada PORCIÓN contra la foto del sistema de ese instante.

    Desde la etapa 3 un artículo tiene varias porciones: sus bultos
    sueltos y las cajas de cada ficha. Sale de los conteos y de ningún
    otro lado: una ficha que nunca se contó no genera renglón.
    """
    try:
        conteos = listar_ultimos_conteos_stock()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    filas = []
    for conteo in conteos:
        fila = dict(conteo, diferencia=round(float(conteo["cantidad"]) - float(conteo["stock_sistema"]), 2))
        # Con diferencia, botón directo a la pantalla de ajuste, precargada
        # con este conteo (la cantidad final se calcula ahí contra el stock
        # ACTUAL, no contra esta foto — ver ver_ajustar_stock_deposito).
        #
        # SOLO en los renglones de sueltos. Un ajuste de stock es por
        # ARTÍCULO: mueve el total, no reparte entre fichas. Si sobran
        # cajas de Bolivia y faltan de Ecuador, el total del artículo está
        # bien y ajustarlo lo rompería — lo que hay que corregir es a qué
        # ficha fue una guía R, que se hace en Guías R desde la etapa 1.
        if fila["diferencia"] != 0 and fila["ficha_id"] is None:
            fila["query_ajuste"] = urlencode(
                {
                    "articulo_id": conteo["articulo_id"],
                    "contado": conteo["cantidad"],
                    "stock_conteo": conteo["stock_sistema"],
                    "fecha_conteo": conteo["creado_en"].date().isoformat(),
                }
            )
        filas.append(fila)

    return templates.TemplateResponse(request, "deposito_stock_cotejo.html", {"filas": filas})


# --- Reproceso (Guías R) ---

SUFIJOS_FICHA_REPROCESO = {"kilo": "kg", "unidad": "u", "cubeta": "cub."}


def _fichas_por_cliente_y_articulo() -> dict[str, list[dict]]:
    """Las fichas elegibles al cargar una guía R, por "cliente_id:articulo_id".

    Desde que el reproceso guarda a qué ficha fueron sus cajas, el
    operario tiene que ELEGIRLA. No se puede derivar de (cliente,
    artículo): un cliente puede tener varias fichas del mismo artículo —
    pide Banana Bolivia y recibe Banana Ecuador — y elegir por él sería
    adivinar. Justo lo que decía el comentario de la ayuda de kilaje
    cuando la guía R todavía no guardaba la ficha.

    Una consulta sola (todas las fichas), no una por cliente.
    """
    por_clave: dict[str, list[dict]] = {}
    for ficha in listar_fichas_de_todos_los_clientes():
        clave = f"{ficha['cliente_id']}:{ficha['articulo_id']}"
        # El kilaje viaja con la ficha para que, una vez elegida, la ayuda
        # muestre EL DE ESA CAJA. Antes tenía que nombrarlas a todas y
        # pedirle al operario que se fijara cuál estaba armando: no había
        # forma de saberlo, porque la guía R no guardaba la ficha.
        sufijo = SUFIJOS_FICHA_REPROCESO.get(ficha.get("unidad_venta"), "")
        kilaje = (f"{_formatear_numero(ficha['contenido_caja'])} {sufijo}".strip()
                  if ficha.get("contenido_caja") else "")
        por_clave.setdefault(clave, []).append(
            {"id": ficha["id"], "nombre": _nombre_de_ficha(ficha), "kilaje": kilaje}
        )
    for fichas in por_clave.values():
        fichas.sort(key=lambda f: f["nombre"])
    return por_clave


def _ayudas_ficha_por_cliente_y_articulo() -> dict[str, str]:
    """El kilaje de la caja armada según la ficha, por (cliente, artículo): "6 kg por caja según la ficha de Día".

    Es dato de FICHA, no de stock: se le puede mostrar al operario. La
    clave es "cliente_id:articulo_id" — la ayuda muestra SOLO las fichas
    del cliente elegido (todas juntas no servían, pedido del dueño 25/08).

    Si ese cliente tiene VARIAS fichas de ese artículo (Banana Bolivia y
    Banana Ecuador), la ayuda las nombra a las dos con su kilaje. Elegir
    una sería adivinar: la guía R no guarda con qué ficha se armó, y
    mostrarle al operario el kilaje de la otra es armar la caja mal.
    """
    # Dos consultas: los nombres de los clientes y TODAS las fichas. Antes se
    # pedían cliente por cliente — el mismo N+1 del FIFO, en otra pantalla.
    nombres = {cliente["id"]: cliente["nombre"] for cliente in listar_clientes()}
    por_cliente: dict[int, dict[int, list[dict]]] = {}
    for ficha in listar_fichas_de_todos_los_clientes():
        if not ficha.get("contenido_caja"):
            continue
        por_cliente.setdefault(ficha["cliente_id"], {}).setdefault(ficha["articulo_id"], []).append(ficha)

    ayudas: dict[str, str] = {}
    for cliente_id, por_articulo in por_cliente.items():
        cliente_fila = {"id": cliente_id, "nombre": nombres.get(cliente_id, f"cliente #{cliente_id}")}
        for articulo_id, fichas_articulo in por_articulo.items():
            def _kilaje(ficha):
                sufijo = SUFIJOS_FICHA_REPROCESO.get(ficha.get("unidad_venta"), "")
                return f"{_formatear_numero(ficha['contenido_caja'])} {sufijo}".strip()

            if len(fichas_articulo) == 1:
                texto = f"{_kilaje(fichas_articulo[0])} por caja, según la ficha de {cliente_fila['nombre']}."
            else:
                detalle = " · ".join(f"{_nombre_de_ficha(f)}: {_kilaje(f)}" for f in fichas_articulo)
                texto = (
                    f"{detalle} por caja, según las fichas de {cliente_fila['nombre']} "
                    "— fijate cuál estás armando."
                )
            ayudas[f"{cliente_fila['id']}:{articulo_id}"] = texto
    return ayudas


def _desglose_para_pantalla(lotes: list[dict]) -> list[dict]:
    """Los lotes como los ve el OPERARIO: fecha y cantidad, y nada más.

    El proveedor aparece SOLO cuando hay dos lotes del mismo día y sin él
    no se distinguirían. En 390px un renglón cargado de datos se vuelve
    ilegible y el operario deja de mirarlo, que es lo contrario de lo que
    el desglose busca. La regla es de la PANTALLA, no del dato: el detalle
    completo sigue estando en Guías R, que es de Administración.
    """
    visibles = [lote for lote in lotes if lote["restante"] > 0]
    del_mismo_dia = {}
    for lote in visibles:
        del_mismo_dia[lote["fecha_lote"]] = del_mismo_dia.get(lote["fecha_lote"], 0) + 1
    return [
        {
            "clave": f"{lote['tipo_lote']}:{lote['origen_id']}",
            "tipo_lote": lote["tipo_lote"],
            "origen_id": lote["origen_id"],
            # Un lote sin fecha existe (una compra sin guía): se dice, no se
            # muestra en blanco, o el renglón queda empezando por un guion.
            "fecha": _formatear_fecha_corta(lote["fecha_lote"]) or "sin fecha",
            "restante": round(float(lote["restante"]), 2),
            # Solo para desempatar: si ese día hay un lote solo, no viaja.
            "detalle": (lote["detalle"] or "") if del_mismo_dia[lote["fecha_lote"]] > 1 else "",
        }
        for lote in visibles
    ]


def _renderizar_pantalla_reproceso(request: Request, *, precarga=None, aviso=None, error=None,
                                   freno=None, advertencia=None, status_code: int = 200):
    try:
        # El selector lista los artículos que se pueden reprocesar, POR
        # NOMBRE y SIN cantidades: saber que "hay tomate" no es un número
        # del sistema — los números no viajan a la pantalla del operario.
        # El filtro mira el total del artículo O sus bultos sueltos: el
        # total baja también cuando salen cajas ya armadas, así que un
        # artículo con la pila suelta intacta desaparecía del selector
        # justo cuando había que cargar la guía R que lo explicaba.
        con_stock = listar_articulos_para_reproceso()
        clientes = listar_clientes()
        ayudas = _ayudas_ficha_por_cliente_y_articulo()
        fichas_elegibles = _fichas_por_cliente_y_articulo()
        # El piso del selector de fecha. Es COMODIDAD, no la regla: la
        # regla vive en crear_reproceso y es la que rechaza. Acá solo
        # evita que el operario elija una fecha que después va a rebotar.
        corte = fecha_corte()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    contexto = {
        "articulos": con_stock,
        "clientes": clientes,
        "ayudas_ficha": ayudas,
        "fichas_elegibles": fichas_elegibles,
        "precarga": precarga or {},
        "hoy": _hoy_argentina().isoformat(),
        "corte": corte.isoformat(),
        "aviso": aviso,
        "error": error,
        "freno": freno,
        "advertencia": advertencia,
    }
    return templates.TemplateResponse(request, "deposito_stock_reproceso.html", contexto, status_code=status_code)


@app.get("/deposito/stock/reproceso")
def ver_reproceso_stock(request: Request, aviso: str | None = None):
    return _renderizar_pantalla_reproceso(request, aviso=aviso)


@app.get("/deposito/stock/reproceso/desglose")
def desglose_reproceso(articulo_id: int, fecha: str = "", bultos: float = 0):
    """De qué lotes saldría este reproceso: lo que la pantalla dibuja mientras el operario carga.

    La propuesta la calcula el SERVER con el mismo `propuesta_fifo` que
    después escribe los consumos. Rehacer el "más viejo primero" en
    JavaScript sería escribir la regla dos veces, y la copia de la pantalla
    se iría separando de la que guarda sin que nadie lo note.

    `alcanza` es el freno adelantado: el mismo número, para poder avisar
    antes de que apriete Guardar. Pero el freno de verdad está en
    crear_reproceso — esto es cortesía, no control.
    """
    from core.stock import bultos_en_los_lotes, propuesta_fifo

    hoy = _hoy_argentina()
    try:
        fecha_valor = date.fromisoformat(fecha.strip()) if fecha.strip() else hoy
    except ValueError:
        fecha_valor = hoy
    try:
        reparto = lotes_para_reproceso(articulo_id, fecha_valor)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    disponible = bultos_en_los_lotes(reparto)
    propuesta = {
        f"{c['tipo_lote']}:{c['origen_id']}": c["bultos"]
        for c in propuesta_fifo(reparto["lotes"], bultos)
    }
    return JSONResponse(
        {
            "lotes": _desglose_para_pantalla(reparto["lotes"]),
            "disponible": disponible,
            "alcanza": round(float(bultos) - disponible, 2) <= 0,
            "propuesta": propuesta,
        }
    )


def _reparto_del_formulario(texto: str) -> tuple[str | None, list[dict] | None]:
    """Lo que el operario editó en el desglose, tal como viaja en el form.

    None = no tocó nada, y entonces va la propuesta FIFO. Un JSON roto no
    se ignora en silencio: si la pantalla mandó algo y no se entiende, se
    frena — guardar "lo que se pudo leer" sería inventarle un reparto.
    """
    if not texto.strip():
        return None, None
    try:
        filas = json.loads(texto)
    except ValueError:
        return "No se entendió de qué lotes sale: volvé a tocar Cambiar y confirmá.", None
    if not isinstance(filas, list):
        return "No se entendió de qué lotes sale: volvé a tocar Cambiar y confirmá.", None
    reparto = []
    for fila in filas:
        try:
            reparto.append(
                {
                    "tipo_lote": str(fila["tipo_lote"]),
                    "origen_id": int(fila["origen_id"]),
                    "bultos": float(fila["bultos"]),
                }
            )
        except (TypeError, ValueError, KeyError, IndexError):
            return "No se entendió de qué lotes sale: volvé a tocar Cambiar y confirmá.", None
    return None, reparto


def _numero_form_o_cero(texto: str, que: str) -> tuple[str | None, float | None]:
    """Bultos producidos del reproceso: vacío vale 0 (no armó de eso), negativo no existe."""
    if not texto.strip():
        return None, 0.0
    try:
        valor = float(texto)
    except ValueError:
        return f"La cantidad de {que} tiene que ser un número.", None
    if valor < 0:
        return f"La cantidad de {que} no puede ser negativa.", None
    return None, valor


@app.post("/deposito/stock/reproceso")
def cargar_reproceso_ruta(
    request: Request,
    cliente_id: str = Form(""),
    articulo_id: str = Form(""),
    bultos_tomados: str = Form(""),
    bultos_primera: str = Form(""),
    bultos_segunda: str = Form(""),
    bultos_merma: str = Form(""),
    fecha: str = Form(""),
    ficha_id: str = Form(""),
    reparto: str = Form(""),
    confirmado: str = Form(""),
):
    """El operario declara la transformación; el server frena, reparte y congela consumos y costo.

    El cliente para el que se arma la primera queda en la guía R como
    DATO (trazabilidad + la alerta de cruce de Auditoría): el stock sigue
    sin dueño y el armado no se restringe.

    ESTA PANTALLA SÍ TRABA POR STOCK, y es la única del depósito que lo
    hace. En el armado de un pedido el piso es la verdad y el camión sale
    igual; acá lo que se congela es un COSTO que después no se corrige
    nunca, así que el reproceso es 100% o nada. Cuando no alcanza, la
    pantalla vuelve entera —con todo lo que cargó— y dice qué ir a cargar
    antes; no hay forma de guardarlo igual.

    El aviso repite solo lo que cargó: jamás costos. Sin correlación entre
    tomado y producido: un cajón de 16 puede dar tres cajas de 6.
    """
    error, tomados_valor = _validar_bultos_positivos(bultos_tomados, "tomados")

    reparto_valor = None
    if not error:
        error, reparto_valor = _reparto_del_formulario(reparto)

    primera_valor = segunda_valor = merma_valor = None
    if not error:
        error, primera_valor = _numero_form_o_cero(bultos_primera, "cajas armadas")
    if not error:
        error, segunda_valor = _numero_form_o_cero(bultos_segunda, "segunda")
    if not error:
        error, merma_valor = _numero_form_o_cero(bultos_merma, "merma")
    if not error and primera_valor == 0 and segunda_valor == 0 and merma_valor == 0:
        error = "Cargá en qué se transformó: cajas armadas, segunda o merma (si fue todo merma, cargala como merma)."

    fecha_valor = None
    if not error:
        hoy = _hoy_argentina()
        if not fecha.strip():
            fecha_valor = hoy
        else:
            try:
                fecha_valor = date.fromisoformat(fecha.strip())
            except ValueError:
                error = "La fecha del reproceso no es válida."
            else:
                if fecha_valor > hoy:
                    error = "La fecha del reproceso no puede ser futura."

    cliente = None
    articulo = None
    if not error:
        try:
            cliente = obtener_cliente(int(cliente_id)) if cliente_id.strip().isdigit() else None
            articulo = obtener_articulo(int(articulo_id)) if articulo_id.strip().isdigit() else None
        except Exception as error_db:
            raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db
        if cliente is None:
            error = "Elegí para qué cliente estás armando."
        elif articulo is None:
            error = "Elegí un artículo válido."

    if error:
        precarga = {
            "cliente_id": cliente_id,
            "articulo_id": articulo_id,
            "bultos_tomados": bultos_tomados,
            "bultos_primera": bultos_primera,
            "bultos_segunda": bultos_segunda,
            "bultos_merma": bultos_merma,
            "fecha": fecha,
            "ficha_id": ficha_id,
        }
        return _renderizar_pantalla_reproceso(request, precarga=precarga, error=error, status_code=400)

    # Todo lo que cargó, listo para devolvérselo intacto si el freno traba:
    # la pared no le puede costar volver a tipear la pantalla entera.
    precarga = {
        "cliente_id": cliente_id,
        "articulo_id": articulo_id,
        "bultos_tomados": bultos_tomados,
        "bultos_primera": bultos_primera,
        "bultos_segunda": bultos_segunda,
        "bultos_merma": bultos_merma,
        "fecha": fecha,
        "ficha_id": ficha_id,
    }

    # "sin_asignar" es una ELECCIÓN, no el resultado de no contestar: el
    # select la ofrece como opción y es obligatorio elegir algo. Eso es lo
    # que después deja distinguir "no lo sabía" de "me lo salteé".
    ficha_valor = None
    if ficha_id.strip().isdigit():
        ficha_valor = int(ficha_id)

    # EL AVISO DE LA FECHA HACIA ATRÁS, con el molde de las señas: se cuenta
    # ANTES de escribir, la pantalla muestra el número y pide el segundo
    # toque. Va antes del freno a propósito — si la fecha está mal, que la
    # corrija antes de pelearse con el stock de un día que no es el suyo.
    #
    # Solo con fecha anterior a hoy: con la de hoy no hay ninguna guía R
    # posterior, así que no hay nada que avisar y el camino normal no se
    # paga un toque de más.
    #
    # Acá NO se pregunta si la fecha cae antes del corte, aunque en ese caso
    # el aviso salga primero y el piso recién en el segundo toque. Repetir
    # `fecha < fecha_corte()` en la ruta sería escribir la regla dos veces, y
    # esa es la que ya nos costó cuatro veces. El `min=` del selector hace
    # que ese caso no exista por la pantalla, y por POST a mano son dos
    # carteles ciertos y nada escrito. Si algún día molesta, la salida es
    # mover el aviso adentro de crear_reproceso, no copiar el piso acá.
    if fecha_valor < _hoy_argentina() and confirmado != "1":
        try:
            afectadas = contar_guias_r_afectadas_por_fecha(articulo["id"], fecha_valor)
        except Exception as error_db:
            return _renderizar_pantalla_reproceso(
                request, precarga=precarga,
                error=f"No se pudo revisar la fecha: {error_db}", status_code=500,
            )
        if afectadas:
            return _renderizar_pantalla_reproceso(
                request,
                precarga=precarga,
                advertencia={
                    "cantidad": afectadas,
                    "articulo": articulo["nombre"],
                    "fecha": fecha_valor.strftime("%d/%m/%Y"),
                },
                status_code=200,
            )

    try:
        numero_guia = crear_reproceso(
            articulo["id"], tomados_valor, primera_valor, segunda_valor, merma_valor, fecha_valor,
            cliente_id=cliente["id"], ficha_id=ficha_valor, reparto=reparto_valor,
        )
    except StockInsuficienteParaReproceso as freno:
        # EL FRENO. No hay "la cargo igual": la pantalla vuelve con todo
        # puesto, le dice cuánto había ese día y de qué lotes, y a dónde ir
        # a cargar lo que falta.
        return _renderizar_pantalla_reproceso(
            request,
            precarga=precarga,
            freno={
                "articulo": articulo["nombre"],
                "fecha": fecha_valor.strftime("%d/%m"),
                "declarado": _formatear_numero(freno.declarado),
                "disponible": _formatear_numero(freno.disponible),
                "lotes": _desglose_para_pantalla(freno.lotes),
            },
            status_code=400,
        )
    except ReprocesoAnteriorAlCorte as anterior:
        # EL PISO. No hay "guardar igual": antes del corte el FIFO nuevo no
        # rige, así que la guía no tendría contra qué medirse. Se dice la
        # fecha con todas las letras para que no haya que adivinarla.
        return _renderizar_pantalla_reproceso(
            request,
            precarga=precarga,
            error=(
                f"La fecha no puede ser anterior al {anterior.corte.strftime('%d/%m/%Y')}: "
                "es el corte desde el que rige el stock nuevo, y antes de esa fecha no hay "
                "lotes contra los que medir el reproceso. Si de verdad fue antes, avisale a "
                "Administración."
            ),
            status_code=400,
        )
    except RepartoDesactualizado as desactualizado:
        # Alguien movió el stock entre que se dibujó el desglose y este
        # Guardar. Se le dice qué pasó y la pantalla vuelve a pedir la
        # propuesta fresca: nunca se guarda un reparto que ya no se cumple.
        return _renderizar_pantalla_reproceso(
            request,
            precarga=precarga,
            error=f"{desactualizado} Cambió el stock mientras cargabas: mirá de nuevo de dónde sale.",
            status_code=400,
        )
    except Exception as error_db:
        return _renderizar_pantalla_reproceso(
            request, error=f"No se pudo guardar el reproceso: {error_db}", status_code=500
        )

    destino = " (sin asignar a una ficha)" if ficha_valor is None else ""
    aviso = (
        f"Guía R{numero_guia}: tomé {_formatear_numero(tomados_valor)} bultos de {articulo['nombre']}, "
        f"armé {_formatear_numero(primera_valor)} cajas para {cliente['nombre']}{destino}, "
        f"{_formatear_numero(segunda_valor)} de segunda y {_formatear_numero(merma_valor)} de merma."
    )
    return RedirectResponse(url=f"/deposito/stock/reproceso?{urlencode({'aviso': aviso})}", status_code=303)


def _cruces_primera_reproceso() -> list[dict]:
    """Los bultos de una primera armada para un cliente que el FIFO atribuye a pedidos de OTRO.

    Rejuega la atribución SOLO para los artículos con guías R de cliente
    (pocos): el resto del catálogo no puede tener cruce. Es AVISO con
    datos, jamás traba — el cruce ya pasó en el galpón; acá se delata
    (guía, cliente del armado, cliente que se lo llevó, bultos y fecha).
    """
    try:
        articulos = listar_articulos_con_primera_de_cliente()
        if not articulos:
            return []
        nombres_clientes = {c["id"]: c["nombre"] for c in listar_clientes()}
    except Exception:
        logger.exception("No se pudieron listar los artículos con primera de cliente")
        return []

    # Los movimientos de todos los artículos de una: dos consultas en total,
    # no dos por artículo. Si falla, no hay alerta — jamás traba.
    ids = [articulo["articulo_id"] for articulo in articulos]
    try:
        movimientos = entradas_y_salidas_stock_articulos(ids)
        salidas_por_articulo = salidas_stock_articulos(ids)
    except Exception:
        logger.exception("No se pudo rejugar el FIFO para la alerta de cruce")
        return []

    cruces = []
    for articulo in articulos:
        # entradas y salidas ya vienen con su "orden" armado desde la base:
        # una sola definición del orden FIFO para todo el sistema.
        entradas, _ = movimientos[articulo["articulo_id"]]
        salidas = salidas_por_articulo[articulo["articulo_id"]]
        for salida in atribuir_costos_fifo(entradas, salidas):
            if salida["tipo"] != "armado" or salida.get("cliente_id") is None:
                continue
            for consumo in salida["consumos_lotes"]:
                cliente_lote = consumo.get("cliente_lote_id")
                if (
                    consumo["tipo_lote"] == "reproceso"
                    and cliente_lote is not None
                    and cliente_lote != salida["cliente_id"]
                ):
                    cruces.append(
                        {
                            "articulo_nombre": articulo["articulo_nombre"],
                            "reproceso_id": consumo["origen_id"],
                            "cliente_lote_nombre": consumo.get("detalle")
                            or nombres_clientes.get(cliente_lote, f"cliente #{cliente_lote}"),
                            "cliente_salida_nombre": nombres_clientes.get(
                                salida["cliente_id"], f"cliente #{salida['cliente_id']}"
                            ),
                            "bultos": float(consumo["bultos"]),
                            "fecha": salida["fecha"],
                        }
                    )
    return cruces


@app.get("/administracion/stock/guias-r")
def ver_guias_r(request: Request, fecha_desde: str | None = None, fecha_hasta: str | None = None,
                aviso: str | None = None, error: str | None = None):
    """Guías R (control): la trazabilidad hacia atrás y el costo del reproceso. Acá SÍ se ven costos.

    Este costo NUNCA alimenta la cotización (que solo lee compras): se
    conoce a la tarde, y la cotización de la mañana se hizo con el costo
    de compra — viven separados a propósito. Cada guía dice para quién se
    armó, y si el FIFO detectó que parte de esa primera salió en pedidos
    de OTRO cliente, lo canta acá con los bultos.
    """
    desde, hasta = _rango_fechas_movimientos(fecha_desde, fecha_hasta)
    try:
        guias = listar_reprocesos_por_rango(desde, hasta)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    # El detalle del cruce por guía: "N bultos salieron en pedidos de X".
    cruces_por_guia: dict = {}
    for cruce in _cruces_primera_reproceso():
        por_cliente = cruces_por_guia.setdefault(cruce["reproceso_id"], {})
        por_cliente[cruce["cliente_salida_nombre"]] = (
            por_cliente.get(cruce["cliente_salida_nombre"], 0.0) + cruce["bultos"]
        )

    # Para completar la ficha de una guía sin asignar: las fichas de ESE
    # artículo, cualquiera sea el cliente. Dos consultas: las fichas y los
    # nombres de los clientes.
    #
    # El nombre del cliente NO viene con la ficha —
    # listar_fichas_de_todos_los_clientes trae cliente_id y nada más— y
    # leerlo de ahí tiraba la pantalla entera con un KeyError apenas
    # hubiera una ficha cargada. Se resuelve con el mismo mapa que ya usan
    # las otras pantallas que necesitan el nombre.
    try:
        nombres_clientes = {c["id"]: c["nombre"] for c in listar_clientes()}
        fichas = listar_fichas_de_todos_los_clientes()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    fichas_por_articulo: dict = {}
    for ficha in fichas:
        cliente = nombres_clientes.get(ficha["cliente_id"], "cliente sin nombre")
        fichas_por_articulo.setdefault(ficha["articulo_id"], []).append(
            {"id": ficha["id"], "nombre": f"{_nombre_de_ficha(ficha)} ({cliente})"}
        )
    for fichas in fichas_por_articulo.values():
        fichas.sort(key=lambda f: f["nombre"])

    return templates.TemplateResponse(
        request,
        "deposito_stock_guias_r.html",
        {
            "guias": guias,
            "cruces_por_guia": cruces_por_guia,
            "fichas_por_articulo": fichas_por_articulo,
            "fecha_desde": desde.isoformat(),
            "fecha_hasta": hasta.isoformat(),
            "aviso": aviso,
            "error": error,
        },
    )


@app.post("/administracion/stock/guias-r/{reproceso_id}/asignar-ficha")
def asignar_ficha_a_reproceso_ruta(request: Request, reproceso_id: int,
                                   ficha_id: str = Form(""),
                                   fecha_desde: str = Form(""), fecha_hasta: str = Form("")):
    """Completa (o corrige) a qué ficha fueron las cajas de una guía R ya cargada.

    No recalcula nada: los consumos y el costo se congelaron al cargar la
    guía. Asignar la ficha es decir a qué producto de venta fueron esas
    cajas, no rehacer el FIFO.
    """
    parametros = {"fecha_desde": fecha_desde, "fecha_hasta": fecha_hasta}
    ficha_valor = int(ficha_id) if ficha_id.strip().isdigit() else None
    try:
        asignar_ficha_a_reproceso(reproceso_id, ficha_valor)
    except ValueError as error:
        # Ficha de otro artículo o guía anulada: dato mal pedido, no una
        # falla del sistema. Se muestra en la pantalla, nunca un 500.
        parametros["error"] = str(error)
        return RedirectResponse(url=f"/administracion/stock/guias-r?{urlencode(parametros)}", status_code=303)
    except Exception as error_db:
        parametros["error"] = f"No se pudo asignar la ficha: {error_db}"
        return RedirectResponse(url=f"/administracion/stock/guias-r?{urlencode(parametros)}", status_code=303)

    parametros["aviso"] = (
        f"Guía R{reproceso_id}: quedó sin asignar." if ficha_valor is None
        else f"Guía R{reproceso_id}: ficha asignada."
    )
    return RedirectResponse(url=f"/administracion/stock/guias-r?{urlencode(parametros)}", status_code=303)


def _renderizar_pantalla_remito_segunda(request: Request, *, precarga=None, aviso=None, error=None, status_code: int = 200):
    try:
        # Solo artículos con segunda disponible, POR NOMBRE, sin números:
        # mismo criterio que el reproceso — el pool no viaja a la pantalla.
        con_segunda = [
            {"id": f["articulo_id"], "nombre": f["nombre"]}
            for f in stock_deposito_por_articulo()
            if f["segunda"] > 0
        ]
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    contexto = {
        "articulos": con_segunda,
        "precarga": precarga or {},
        "hoy": _hoy_argentina().isoformat(),
        "aviso": aviso,
        "error": error,
    }
    return templates.TemplateResponse(request, "deposito_stock_remito_segunda.html", contexto, status_code=status_code)


@app.get("/deposito/stock/remito-segunda")
def ver_remito_segunda(request: Request, aviso: str | None = None):
    return _renderizar_pantalla_remito_segunda(request, aviso=aviso)


@app.post("/deposito/stock/remito-segunda")
def cargar_remito_segunda_ruta(
    request: Request,
    articulo_id: str = Form(""),
    cantidad: str = Form(""),
    fecha: str = Form(""),
):
    """La segunda se manda al Puesto (destino fijo): sale del pool y deja de ser problema del depósito.

    Pantalla de OPERARIO: el aviso repite solo lo cargado. No traba si
    remite más de lo que el pool dice — el piso es su verdad; el pool en
    negativo se ve en Stock del Sistema.
    """
    error, cantidad_valor = _validar_bultos_positivos(cantidad, "remitidos")

    fecha_valor = None
    if not error:
        hoy = _hoy_argentina()
        if not fecha.strip():
            fecha_valor = hoy
        else:
            try:
                fecha_valor = date.fromisoformat(fecha.strip())
            except ValueError:
                error = "La fecha del remito no es válida."
            else:
                if fecha_valor > hoy:
                    error = "La fecha del remito no puede ser futura."

    articulo = None
    if not error:
        try:
            articulo = obtener_articulo(int(articulo_id)) if articulo_id.strip().isdigit() else None
        except Exception as error_db:
            raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db
        if articulo is None:
            error = "Elegí un artículo válido."

    if error:
        precarga = {"articulo_id": articulo_id, "cantidad": cantidad, "fecha": fecha}
        return _renderizar_pantalla_remito_segunda(request, precarga=precarga, error=error, status_code=400)

    try:
        crear_remito_segunda(articulo["id"], cantidad_valor, fecha_valor)
    except Exception as error_db:
        return _renderizar_pantalla_remito_segunda(
            request, error=f"No se pudo guardar el remito: {error_db}", status_code=500
        )

    aviso = (
        f"Remito guardado: {_formatear_numero(cantidad_valor)} bultos de segunda de {articulo['nombre']} "
        f"al Puesto ({fecha_valor.strftime('%d/%m')})."
    )
    return RedirectResponse(url=f"/deposito/stock/remito-segunda?{urlencode({'aviso': aviso})}", status_code=303)


@app.post("/administracion/stock/guias-r/{reproceso_id}/completar-costo")
def completar_costo_reproceso_ruta(
    reproceso_id: int,
    fecha_desde: str = Form(""),
    fecha_hasta: str = Form(""),
):
    """Rellena SOLO los costos que faltaban (compras que ya tienen precio) — jamás pisa un costo congelado."""
    try:
        resultado = completar_costo_reproceso(reproceso_id)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"No se pudo completar el costo: {error_db}") from error_db

    if resultado["completado"]:
        aviso = f"Costo de la guía R{reproceso_id} completado con los precios ya cargados."
    else:
        aviso = (
            f"La guía R{reproceso_id} sigue con costo incompleto: {resultado['sin_precio']} "
            f"{'consumo' if resultado['sin_precio'] == 1 else 'consumos'} sin precio posible "
            f"(compra sin precio aún, stock inicial, reingreso o sin lote)."
        )
    return RedirectResponse(
        url=f"/administracion/stock/guias-r?{urlencode({'fecha_desde': fecha_desde, 'fecha_hasta': fecha_hasta, 'aviso': aviso})}",
        status_code=303,
    )


@app.post("/administracion/stock/guias-r/{reproceso_id}/anular")
def anular_reproceso_ruta(
    reproceso_id: int,
    fecha_desde: str = Form(""),
    fecha_hasta: str = Form(""),
):
    try:
        anular_reproceso(reproceso_id)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"No se pudo anular la guía: {error_db}") from error_db

    return RedirectResponse(
        url=f"/administracion/stock/guias-r?{urlencode({'fecha_desde': fecha_desde, 'fecha_hasta': fecha_hasta})}",
        status_code=303,
    )


@app.get("/gerencia")
def ver_gerencia(request: Request):
    """Hub de Gerencia: el manejo del dinero (las dos rentabilidades y lo que venga). TODA la zona pide la clave.

    La Auditoría vive afuera, en su propio sector (/auditoria): es control
    operativo, no plata — se mira sin clave.
    """
    if not _acceso_gerencia_valido(request):
        return _pantalla_clave_gerencia(request)
    return templates.TemplateResponse(request, "gerencia.html", {})


@app.post("/gerencia/clave")
def ingresar_clave_gerencia_ruta(request: Request, clave: str = Form(""), volver: str = Form("/gerencia")):
    """Valida la clave de Gerencia y deja la cookie firmada: una vez por jornada, para toda la zona."""
    destino = _destino_gerencia_seguro(volver)
    clave_real = _clave_gerencia()
    if clave_real is None:
        # Sin clave configurada no hay puerta: nada que validar.
        return RedirectResponse(url=destino, status_code=303)
    if not hmac.compare_digest(clave.strip(), clave_real):
        return _pantalla_clave_gerencia(request, volver=destino, error="Clave incorrecta.")

    respuesta = RedirectResponse(url=destino, status_code=303)
    respuesta.set_cookie(
        COOKIE_ACCESO_GERENCIA,
        _firma_acceso_gerencia(clave_real),
        max_age=DURACION_ACCESO_CONTROL,
        httponly=True,
        samesite="lax",
        path="/gerencia",
    )
    return respuesta


@app.post("/gerencia/bloquear")
def bloquear_gerencia_ruta(request: Request):
    """Borra la cookie de acceso en el momento: para no dejar la rentabilidad abierta en un celular suelto."""
    respuesta = RedirectResponse(url="/inicio", status_code=303)
    respuesta.delete_cookie(COOKIE_ACCESO_GERENCIA, path="/gerencia")
    return respuesta


def _contar_cruces_primera_reproceso() -> dict:
    """Envoltorio de _cruces_primera_reproceso con la forma que espera el registro."""
    cruces = _cruces_primera_reproceso()
    return {"casos": len(cruces), "mas_viejo": min((c["fecha"] for c in cruces), default=None)}


def _contar_modulos_inexistentes() -> dict:
    """Alertas del registro que apuntan a un módulo que no existe.

    Es una alerta que vigila a las alertas, igual que la de la casilla muerta
    vigila al bucle. Los módulos válidos salen de las RUTAS del sistema, no de
    una lista escrita a mano: se desactualiza y después miente.

    Un error de tipeo acá no deja la alerta invisible — Auditoría no filtra por
    módulo, así que se sigue viendo; lo que se pierde es el banner. Esta alerta
    es la que lo delata, con nombre y apellido en el log.
    """
    sueltas = modulos_inexistentes(ALERTAS, [ruta.path for ruta in app.routes])
    if sueltas:
        logger.warning(
            "Alertas apuntando a módulos que no existen: %s",
            ", ".join(f"{s['codigo']} -> {s['modulo']}" for s in sueltas),
        )
    return {"casos": len(sueltas), "mas_viejo": None}


def _url_retiros_viejos(datos) -> str:
    """El link de los retiros pendientes viejos: arranca en el caso más viejo."""
    limite = _hoy_argentina() - timedelta(days=2)
    return "/logistica/consultar?" + urlencode({
        "fecha_desde": (datos["mas_viejo"] or limite).isoformat(),
        "fecha_hasta": limite.isoformat(),
        "estado": "pendiente",
    })


# ----------------------------------------------------------------------------
# EL REGISTRO DE ALERTAS
# ----------------------------------------------------------------------------
# Agregar la alerta número dieciséis es sumar UNA entrada acá y escribir su
# consulta. Nada más: ni migración, ni tocar plantillas, ni tocar pantallas.
#
# "modulos" dice en qué banners aparece ADEMÁS de Auditoría, que las muestra
# TODAS siempre. Por eso "auditoria" no se lista: si hubiera que listarla,
# sería un ítem más para olvidarse, y una alerta olvidada es invisible.
#
# Los conteos NO corren acá: los corre el recálculo cada 12 horas y las
# pantallas leen la foto. Ver app/alertas.py para el porqué.
#
# "contar" va SIEMPRE como lambda, aunque la función no necesite argumentos.
# Este registro se evalúa al importar el módulo, y varias funciones de conteo
# se definen más abajo en este mismo archivo: con la lambda el nombre se
# resuelve recién al llamarla, así el registro no depende de en qué orden
# quedaron las definiciones en un archivo de once mil líneas.
# ----------------------------------------------------------------------------
ALERTAS = [
    DefinicionAlerta(
        codigo="compras_sin_precio",
        titulo="Compras sin precio de compra cargado",
        url="/compras/pendientes",
        texto_link="Ver en Compras sin precio",
        # También en Comercial: el que factura es el que se come el problema.
        modulos=("compras", "comercial"),
        # SIN ventana de tiempo, a propósito: si compré a la mañana y a la
        # tarde no está el precio, el costeo del día siguiente ya sale mal —
        # esperar 48 horas es enterarse tarde. Y tampoco desaparece por vieja:
        # es un agujero hasta que alguien lo tapa. Lo que sí filtra es el
        # ESTADO: una compra rechazada o cancelada nunca va a tener precio.
        contar=lambda: contar_compras_sin_precio(),
    ),
    DefinicionAlerta(
        codigo="retiros_sin_hacer",
        titulo="Mercadería sin retirar hace más de 48 horas",
        url=_url_retiros_viejos,
        texto_link="Ver en Consultar Retiros",
        modulos=("logistica",),
        contar=lambda: contar_retiros_pendientes_viejos(_hoy_argentina() - timedelta(days=2)),
    ),
    DefinicionAlerta(
        codigo="recepciones_pendientes",
        titulo="Mercadería sin recepcionar hace más de 48 horas",
        url="/deposito/recepcion",
        texto_link="Ver en Recepción",
        modulos=("deposito",),
        contar=lambda: contar_recepciones_pendientes_viejas(_hoy_argentina() - timedelta(days=2)),
    ),
    DefinicionAlerta(
        codigo="stock_vacios_negativo",
        titulo="Stock de vacíos negativo",
        url="/puesto/envases/stock",
        texto_link="Ver en Stock del Sistema",
        modulos=("puesto",),
        contar=lambda: contar_stock_vacios_negativos(),
    ),
    DefinicionAlerta(
        codigo="stock_deposito_negativo",
        # Salió más de lo que entró: salidas sin lote que un reproceso o un
        # ajuste tienen que explicar — o alguien sacó de más.
        titulo="Stock de depósito en negativo (salidas sin explicar)",
        url="/administracion/stock/sistema",
        texto_link="Ver en Stock del Sistema del Depósito",
        # El banner va donde está la pantalla: Stock del Sistema se mudó
        # a Administración, así que avisar en Depósito mandaría al
        # operario a un módulo que ya no es suyo.
        modulos=("administracion",),
        contar=lambda: contar_stock_deposito_negativo(),
    ),
    DefinicionAlerta(
        codigo="guias_r_costo_incompleto",
        # Sin costo cerrado no hay rentabilidad real de ese reproceso: o falta
        # el precio de una compra ("Completar costo" lo arregla), o consumió
        # stock inicial/reingreso/sin lote.
        titulo="Guías R con costo incompleto",
        url="/administracion/stock/guias-r",
        # A los dos: se arregla cargando el precio de una compra que falta
        # (eso es Compras), pero el que cargó el reproceso es el que puede
        # avisar cuál falta.
        texto_link="Ver en Guías R",
        # Guías R se mudó a Administración; Compras se queda porque el
        # costo incompleto lo resuelve el que carga el precio.
        modulos=("compras", "administracion"),
        contar=lambda: contar_reprocesos_costo_incompleto(),
    ),
    DefinicionAlerta(
        codigo="cruce_primera_reproceso",
        # La primera se armó para un cliente y el FIFO dice que parte salió en
        # pedidos de OTRO: cajas de presentación equivocada. Aviso con datos,
        # nunca traba — el galpón ya lo hizo; acá se delata.
        titulo="Primera de reproceso armada para un cliente salió en pedidos de otro",
        url="/administracion/stock/guias-r",
        # Sin banner a propósito: el cruce YA pasó en el galpón, no hay
        # nada que hacer con él hoy. Es información para revisar, y para
        # eso está Auditoría.
        texto_link="Ver el detalle en Guías R",
        contar=lambda: _contar_cruces_primera_reproceso(),
    ),
    DefinicionAlerta(
        codigo="articulos_incotizables",
        titulo="Artículos comprados sin ficha logística o sin precio de venta (últimos 7 días)",
        url="/fichas",
        texto_link="Ver en Fichas Logísticas",
        modulos=("comercial", "fichas"),
        contar=lambda: contar_articulos_comprados_incotizables(
            _hoy_argentina() - timedelta(days=7), _hoy_argentina()
        ),
    ),
    DefinicionAlerta(
        codigo="senas_vacios_pendientes",
        titulo="Señas de vacíos pendientes hace más de 7 días",
        url="/puesto/envases/pendientes",
        texto_link="Ver en Pendientes de Pago",
        modulos=("puesto",),
        contar=lambda: contar_senas_pendientes_viejas(_hoy_argentina() - timedelta(days=7)),
    ),
    DefinicionAlerta(
        codigo="pedidos_sin_identificar",
        titulo="Pedidos con renglones sin identificar",
        titulo_corto="Pedidos sin identificar",
        url="/deposito/pedido",
        texto_link="Ver en Pedido",
        modulos=("deposito",),
        contar=lambda: contar_pedidos_con_renglones_sin_identificar(),
    ),
    DefinicionAlerta(
        codigo="pedidos_incompletos",
        titulo="Pedidos con renglones incompletos (se armó menos de lo pedido)",
        # En el banner va corto: es una cinta que corre en 390px y el título
        # largo se leía a medias, con el número recién al final. En Auditoría
        # sigue el largo, que ahí sobra lugar y la aclaración sirve.
        titulo_corto="Pedidos incompletos",
        url="/deposito/pedido",
        texto_link="Ver en Pedido",
        modulos=("deposito",),
        # CON ventana, al revés que las compras sin precio: un pedido que ya
        # salió incompleto no se puede completar después. Sin ventana quedaría
        # en la lista para siempre, sin forma de resolverlo ni limpiarlo.
        #
        # La ventana NO es un plazo para actuar: cuando el camión salió ya no
        # hay nada que hacer con ese pedido. Es para leer el PATRÓN — uno
        # suelto no dice nada, tres en una semana del mismo cliente o del
        # mismo artículo sí (falta stock sistemáticamente, o se pide algo que
        # no se compra). Siete días es el mínimo con el que se ve un patrón;
        # con dos se ve ruido.
        #
        # El número sale de DIAS_PASADOS_LISTADO_PEDIDOS, no de un 7 escrito
        # acá: contar pedidos que /deposito/pedido no lista dejaría el banner
        # diciendo un número y la pantalla mostrando otro.
        contar=lambda: contar_pedidos_incompletos(
            _hoy_argentina() - timedelta(days=DIAS_PASADOS_LISTADO_PEDIDOS)
        ),
    ),
    DefinicionAlerta(
        codigo="mails_sin_confirmar",
        # Pendientes Y con error de lectura: un mail que falló a las 12:00
        # corriendo solo se tiene que ver acá, no perderse.
        titulo="Mails de pedido sin confirmar",
        url="/sistema/casilla-pedidos",
        texto_link="Ver en Casilla de Pedidos",
        # Solo en Sistema: Depósito ya tiene seis y todas accionables. Un
        # banner que se llena deja de mirarse.
        modulos=("sistema",),
        contar=lambda: contar_mails_pedido_sin_procesar(),
    ),
    DefinicionAlerta(
        codigo="mails_leidos_con_ia",
        # El fallback a IA VISIBLE: si Día cambió el formato del mail y el
        # parser por estructura dejó de poder, esto lo dice ese mismo día —
        # antes de que un cruce de bultos llegue a una entrega. Ventana de 7
        # días: alcanza para verlo sin arrastrar para siempre un mail viejo.
        titulo="Pedidos de mail leídos con IA (el parser de estructura no pudo, últimos 7 días)",
        url="/sistema/casilla-pedidos",
        texto_link="Ver en Casilla de Pedidos",
        modulos=("sistema",),
        contar=lambda: contar_mails_pedido_leidos_con_ia(_hoy_argentina() - timedelta(days=7)),
    ),
    DefinicionAlerta(
        codigo="pedido_faltante",
        # Un día esperado sin pedido después de las 15:00: o el mail no llegó,
        # o no se leyó. Se cierra cargando el pedido o marcando "no hubo
        # pedido" desde la pantalla de Pedido.
        titulo="Falta el pedido de un día esperado",
        url="/deposito/pedido",
        texto_link="Ver en Pedido",
        modulos=("deposito",),
        contar=lambda: contar_pedidos_faltantes(),
    ),
    DefinicionAlerta(
        codigo="casilla_sin_revisar",
        # Solo el problema REAL: desde las 14:00, la casilla activa que en todo
        # el día no tuvo ninguna revisión exitosa. Un fallo puntual que se
        # recuperó solo no alerta (se ve en la pantalla de la casilla, pero no
        # grita acá).
        titulo="La casilla de pedidos no se pudo revisar",
        url="/sistema/casilla-pedidos",
        texto_link="Ver en Casilla de Pedidos",
        modulos=("sistema",),
        contar=lambda: contar_casillas_sin_revisar(),
    ),
    DefinicionAlerta(
        codigo="modulos_inexistentes",
        # La alerta que vigila a las alertas. Sin módulos propios: vive solo en
        # Auditoría, que es donde se mira lo que le pasa al sistema.
        titulo="Alertas apuntando a un módulo que no existe (no se ven en su banner)",
        url="/auditoria",
        texto_link="El detalle está en el log del servidor",
        contar=lambda: _contar_modulos_inexistentes(),
    ),
]


def _banner_alertas(modulo: str) -> dict:
    """Lo que necesita el banner de una botonera: las alertas de ese módulo y cuán vieja es la foto.

    UNA sola consulta, siempre: lee la foto del último cálculo y filtra en
    memoria. Da igual que el registro tenga 15 alertas o 100 — por eso las
    alertas se guardan en vez de calcularse en vivo (ver app/alertas.py).

    El banner es un aviso, no algo crítico para poder navegar: si la consulta
    falla, la botonera sale sin banner en vez de romperse entera por algo
    accesorio. Mismo criterio que tenía el banner viejo de Compras.

    La frescura NO sale de la foto: se compara contra el reloj acá. Si el
    cálculo automático se murió, el banner lo dice — un banner vacío porque
    nadie calculó nada no puede verse igual que un banner vacío porque está
    todo bien.
    """
    try:
        estado = listar_estado_alertas()
    except Exception:
        logger.exception("No se pudo leer el estado de las alertas para el banner de %s", modulo)
        return {"alertas": [], "frescura": None}
    return {
        "alertas": para_mostrar(ALERTAS, estado, modulo),
        "frescura": frescura(estado, datetime.now(ARGENTINA)),
    }


@app.get("/gerencia/auditoria")
def ver_auditoria_url_vieja():
    """La URL vieja (cuando Auditoría vivía en Gerencia) sigue llegando: redirige a su sector propio."""
    return RedirectResponse(url="/auditoria", status_code=301)


@app.get("/auditoria")
def ver_auditoria(request: Request, aviso: str | None = None, error: str | None = None):
    """Tablero de cosas que están mal, de un pantallazo: solo aparecen los controles con casos.

    Sector PROPIO, fuera de Gerencia y SIN clave: es control operativo
    (qué está trabado o mal cargado), no manejo de plata — en Gerencia
    quedan solo las rentabilidades, detrás de su clave.

    Lee la FOTO del último cálculo (una consulta), no recalcula: ver
    app/alertas.py. Y muestra SIEMPRE de cuándo es esa foto, calculado contra
    el reloj — si el cálculo automático se murió, tiene que verse acá, no
    quedar tapado por un tablero que dice "todo en orden".

    Auditoría NO filtra por módulo: muestra todas las del registro. Eso es lo
    que garantiza que una alerta con el módulo mal escrito no quede invisible.
    """
    try:
        estado = listar_estado_alertas()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    ahora = datetime.now(ARGENTINA)
    return templates.TemplateResponse(
        request,
        "auditoria.html",
        {
            "alertas": para_mostrar(ALERTAS, estado),
            "controles_corridos": len(ALERTAS),
            "frescura": frescura(estado, ahora),
            "horas_vencimiento": HORAS_VENCIMIENTO,
            "aviso": aviso,
            "error": error,
        },
    )


@app.post("/auditoria/recalcular")
def recalcular_alertas_ruta():
    """Recalcula las alertas ahora, a pedido: arreglé algo y quiero confirmarlo sin esperar.

    Sincrónico a propósito: apretaste el botón porque querés ver el resultado.
    Si el bucle de fondo ya está recalculando, el candado lo detecta y avisa en
    vez de duplicar el trabajo.
    """
    try:
        resumen = recalcular(ALERTAS)
    except Exception as error_db:
        return RedirectResponse(
            url="/auditoria?" + urlencode({"error": f"No se pudieron recalcular las alertas: {error_db}"}),
            status_code=303,
        )
    if not resumen["corrio"]:
        return RedirectResponse(
            url="/auditoria?" + urlencode({"aviso": "Ya se estaban recalculando en este momento. Probá de nuevo en un rato."}),
            status_code=303,
        )
    if resumen["fallaron"]:
        return RedirectResponse(
            url="/auditoria?" + urlencode({
                "error": f"Se recalcularon {resumen['ok']}, pero {resumen['fallaron']} no se pudieron calcular (quedaron con su valor viejo)."
            }),
            status_code=303,
        )
    return RedirectResponse(
        url="/auditoria?" + urlencode({"aviso": f"Listo: {resumen['ok']} controles recalculados."}),
        status_code=303,
    )


def _margenes_por_fecha(cliente_id: int, fechas) -> dict:
    """El listado anclado a cada fecha, indexado por ficha — la fuente de precio y costo de las dos rentabilidades.

    Pide TODAS las fechas de una: antes era una llamada por fecha, y cada
    llamada abría cinco conexiones. El ancla es siempre el mediodía de la
    fecha, como venía siendo — es lo que decide qué compras entran en la
    ventana "fresca" de esa jornada.
    """
    momentos = {fecha: datetime.combine(fecha, time(12, 0), tzinfo=ARGENTINA) for fecha in fechas}
    listados = calcular_listados_para_negociar_precios(cliente_id, momentos.values())
    return {
        fecha: {fila["ficha_id"]: fila for fila in listados[momento]}
        for fecha, momento in momentos.items()
    }


def _datos_rentabilidad(cliente_id: int, fecha_desde, fecha_hasta, articulo_id, grupo, fichas: list[dict]) -> dict:
    """Junta los datos y llama al motor puro de rentabilidad (core/rentabilidad.py).

    La fuente de precio, costo, envase y tasas es EL MISMO listado que
    Márgenes por Artículo (calcular_listado_para_negociar_precios),
    anclado a cada FECHA con pedido vigente del rango: precio de lista
    vigente a esa fecha, costo de mercadería por la última compra, envase
    ponderado y el denominador de tasas del cliente. Usar el mismo listado
    es lo que garantiza el control del dueño: Rentabilidad y Márgenes,
    sobre el mismo artículo en la misma fecha, dan idéntico. Un cambio de
    precio o de tasas a mitad del rango pega solo en los pedidos de ahí en
    adelante, nunca retroactivo.
    """
    renglones = listar_renglones_pedidos_vigentes(cliente_id, fecha_desde, fecha_hasta)
    fechas = sorted({r["fecha_operacion"] for r in renglones})
    margenes_por_fecha = _margenes_por_fecha(cliente_id, fechas)
    return calcular_rentabilidad_de_pedidos(renglones, fichas, margenes_por_fecha, articulo_id, grupo)


def _leer_filtros_rentabilidad(
    cliente_id_texto, fecha_desde_texto, fecha_hasta_texto, articulo_id_texto, grupo_texto
):
    """Valida los filtros de Rentabilidad (pantalla y exports usan lo mismo). Devuelve también el error de fechas."""
    cliente_id = _id_opcional_desde_query(cliente_id_texto)
    articulo_id = _id_opcional_desde_query(articulo_id_texto)
    grupo = grupo_texto if grupo_texto in GRUPOS_ARTICULO_VALIDOS else None

    hoy = _hoy_argentina()
    fecha_desde = hoy - timedelta(days=7)
    fecha_hasta = hoy
    error_fecha = None
    if fecha_desde_texto:
        try:
            fecha_desde = date.fromisoformat(fecha_desde_texto)
        except ValueError:
            error_fecha = "La fecha desde no es válida."
    if fecha_hasta_texto:
        try:
            fecha_hasta = date.fromisoformat(fecha_hasta_texto)
        except ValueError:
            error_fecha = "La fecha hasta no es válida."
    if error_fecha is None and fecha_desde > fecha_hasta:
        error_fecha = "La fecha desde no puede ser posterior a la fecha hasta."
    return cliente_id, fecha_desde, fecha_hasta, articulo_id, grupo, error_fecha


def _filtros_texto_rentabilidad(cliente_nombre, articulo_id, grupo, articulos_cliente) -> list[str]:
    filtros = [f"cliente {cliente_nombre}"]
    if articulo_id is not None:
        nombre = next((a["nombre"] for a in articulos_cliente if a["id"] == articulo_id), None)
        filtros.append(f"artículo {nombre or f'#{articulo_id}'}")
    if grupo is not None:
        filtros.append(f"grupo {ETIQUETAS_GRUPO.get(grupo, grupo)}")
    return filtros


@app.get("/gerencia/rentabilidad")
def ver_rentabilidad_pedidos(
    request: Request,
    cliente_id: str | None = None,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
    articulo_id: str | None = None,
    grupo: str | None = None,
):
    """Rentabilidad de Pedidos: cuánto dejó (estimado) lo pedido, por artículo y por grupo.

    Bultos = LO PEDIDO, sin ajustar por armado (decisión del dueño: el
    tilde de armado es una herramienta del depósito, no una medición).
    Los artículos que no se pueden calcular van APARTE con su motivo —
    jamás suman como cero en silencio.
    """
    if not _acceso_gerencia_valido(request):
        return _pantalla_clave_gerencia(request)
    cliente_valor, desde, hasta, articulo_valor, grupo_valor, error_fecha = _leer_filtros_rentabilidad(
        cliente_id, fecha_desde, fecha_hasta, articulo_id, grupo
    )

    try:
        clientes = listar_clientes()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    contexto = {
        "clientes": clientes,
        "cliente_id": cliente_valor,
        "fecha_desde": desde.isoformat(),
        "fecha_hasta": hasta.isoformat(),
        "articulo_id": articulo_valor,
        "grupo": grupo_valor,
        "grupos_articulo": [(clave, ETIQUETAS_GRUPO[clave]) for clave in ("fruta", "hortaliza", "hoja", "pesada")],
        "error_fecha": error_fecha,
        "articulos_cliente": [],
        "resultado": None,
    }
    if cliente_valor is None or error_fecha:
        return templates.TemplateResponse(request, "gerencia_rentabilidad.html", contexto)

    try:
        fichas = listar_fichas_por_cliente(cliente_valor)
        contexto["articulos_cliente"] = [{"id": f["articulo_id"], "nombre": f["articulo_nombre"]} for f in fichas]
        contexto["resultado"] = _datos_rentabilidad(cliente_valor, desde, hasta, articulo_valor, grupo_valor, fichas)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    return templates.TemplateResponse(request, "gerencia_rentabilidad.html", contexto)


def _resultado_rentabilidad_para_exportar(cliente_id, fecha_desde, fecha_hasta, articulo_id, grupo):
    """Los datos + textos de filtros para los exports (mismos filtros que la pantalla, sin tope)."""
    cliente_valor, desde, hasta, articulo_valor, grupo_valor, error_fecha = _leer_filtros_rentabilidad(
        cliente_id, fecha_desde, fecha_hasta, articulo_id, grupo
    )
    if cliente_valor is None:
        raise HTTPException(status_code=400, detail="Elegí el cliente antes de exportar.")
    if error_fecha:
        raise HTTPException(status_code=400, detail=error_fecha)

    try:
        cliente = obtener_cliente(cliente_valor)
        fichas = listar_fichas_por_cliente(cliente_valor)
        resultado = _datos_rentabilidad(cliente_valor, desde, hasta, articulo_valor, grupo_valor, fichas)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    articulos_cliente = [{"id": f["articulo_id"], "nombre": f["articulo_nombre"]} for f in fichas]
    nombre_cliente = cliente["nombre"] if cliente else f"#{cliente_valor}"
    filtros_texto = _filtros_texto_rentabilidad(nombre_cliente, articulo_valor, grupo_valor, articulos_cliente)
    return desde, hasta, filtros_texto, resultado


@app.get("/gerencia/rentabilidad/exportar-pdf")
def exportar_rentabilidad_pdf(
    request: Request,
    cliente_id: str = "", fecha_desde: str = "", fecha_hasta: str = "", articulo_id: str = "", grupo: str = ""
):
    """Genera Rentabilidad de Pedidos (mismos filtros que la pantalla) en PDF — sin tope. Zona con clave."""
    if not _acceso_gerencia_valido(request):
        return RedirectResponse(url="/gerencia/rentabilidad", status_code=303)
    desde, hasta, filtros_texto, resultado = _resultado_rentabilidad_para_exportar(
        cliente_id, fecha_desde, fecha_hasta, articulo_id, grupo
    )
    pdf_bytes = generar_pdf_rentabilidad(desde, hasta, filtros_texto, resultado)
    nombre_archivo = f"Rentabilidad_Pedidos_{desde.isoformat()}_a_{hasta.isoformat()}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'},
    )


@app.get("/gerencia/rentabilidad/exportar-excel")
def exportar_rentabilidad_excel(
    request: Request,
    cliente_id: str = "", fecha_desde: str = "", fecha_hasta: str = "", articulo_id: str = "", grupo: str = ""
):
    """Genera Rentabilidad de Pedidos (mismos filtros que la pantalla) en Excel — sin tope. Zona con clave."""
    if not _acceso_gerencia_valido(request):
        return RedirectResponse(url="/gerencia/rentabilidad", status_code=303)
    desde, hasta, filtros_texto, resultado = _resultado_rentabilidad_para_exportar(
        cliente_id, fecha_desde, fecha_hasta, articulo_id, grupo
    )
    excel_bytes = generar_excel_rentabilidad(desde, hasta, filtros_texto, resultado)
    nombre_archivo = f"Rentabilidad_Pedidos_{desde.isoformat()}_a_{hasta.isoformat()}.xlsx"
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'},
    )


def _datos_rentabilidad_real(cliente_id: int, fecha_desde, fecha_hasta, articulo_id, grupo) -> dict:
    """Junta los datos y llama al motor puro de la Rentabilidad REAL (core/costo_real.py).

    La TEÓRICA queda intacta (es la red del dueño); esta es la cuenta
    exacta. Por artículo con movimiento en el rango se trae la HISTORIA
    COMPLETA de entradas y salidas (la atribución FIFO necesita el pasado
    entero), y los precios/tasas salen del MISMO listado anclado por
    fecha que usan Márgenes y la teórica: donde las dos pantallas miran
    lo mismo, dan lo mismo — la diferencia que quede es la lista de cosas
    a explicar (merma, reproceso, kilajes), no ruido de cuentas distintas.
    """
    articulos = articulos_con_salidas_stock(cliente_id, fecha_desde, fecha_hasta)
    if articulo_id is not None:
        articulos = [a for a in articulos if a["articulo_id"] == articulo_id]
    if grupo is not None:
        articulos = [a for a in articulos if a["grupo"] == grupo]

    # Las devoluciones vinculadas del rango (la línea "− devoluciones"),
    # con los MISMOS filtros de artículo/grupo que el resto.
    devoluciones = devoluciones_vinculadas_por_rango(cliente_id, fecha_desde, fecha_hasta)
    if articulo_id is not None:
        devoluciones = [d for d in devoluciones if d["articulo_id"] == articulo_id]
    if grupo is not None:
        devoluciones = [d for d in devoluciones if d["grupo"] == grupo]

    # La historia completa de TODOS los artículos del rango, en dos consultas.
    # Antes eran dos por artículo, cada una con su conexión.
    ids = [articulo["articulo_id"] for articulo in articulos]
    movimientos = entradas_y_salidas_stock_articulos(ids)
    salidas_por_articulo = salidas_stock_articulos(ids)

    articulos_datos = []
    fechas_pedido = set()
    for articulo in articulos:
        # entradas y salidas ya vienen con su "orden" armado desde la base:
        # una sola definición del orden FIFO para todo el sistema.
        entradas, _ = movimientos[articulo["articulo_id"]]
        salidas = salidas_por_articulo[articulo["articulo_id"]]
        for s in salidas:
            if (
                s["tipo"] == "armado"
                and s["cliente_id"] == cliente_id
                and fecha_desde <= s["fecha"] <= fecha_hasta
            ):
                fechas_pedido.add(s["fecha"])
        articulos_datos.append(dict(articulo, entradas=entradas, salidas=salidas))

    # La devolución se valúa al listado de la fecha de SU pedido de
    # origen, que puede caer fuera del rango: esa fecha también ancla.
    for devolucion in devoluciones:
        fechas_pedido.add(devolucion["fecha_pedido"])

    margenes_por_fecha = _margenes_por_fecha(cliente_id, sorted(fechas_pedido))

    return calcular_rentabilidad_real(
        articulos_datos, margenes_por_fecha, cliente_id, fecha_desde, fecha_hasta,
        devoluciones=devoluciones,
    )


@app.get("/gerencia/rentabilidad-real")
def ver_rentabilidad_real(
    request: Request,
    cliente_id: str | None = None,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
    articulo_id: str | None = None,
    grupo: str | None = None,
):
    """Rentabilidad Real: qué dejó DE VERDAD lo que salió del depósito — botón aparte de la teórica.

    Venta = lo ENVIADO × precio de lista vigente (el precio que Día
    paga); mercadería al costo FIFO real; mermas del período al costo de
    su lote; la segunda en bultos, sin plata. El "afuera del cálculo" es
    PROTAGONISTA por pedido del dueño: motivo por motivo, con bultos y
    artículos — su hoja de ruta mientras la real se afina.
    """
    if not _acceso_gerencia_valido(request):
        return _pantalla_clave_gerencia(request)
    cliente_valor, desde, hasta, articulo_valor, grupo_valor, error_fecha = _leer_filtros_rentabilidad(
        cliente_id, fecha_desde, fecha_hasta, articulo_id, grupo
    )

    try:
        clientes = listar_clientes()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    contexto = {
        "clientes": clientes,
        "cliente_id": cliente_valor,
        "fecha_desde": desde.isoformat(),
        "fecha_hasta": hasta.isoformat(),
        "articulo_id": articulo_valor,
        "grupo": grupo_valor,
        "grupos_articulo": [(clave, ETIQUETAS_GRUPO[clave]) for clave in ("fruta", "hortaliza", "hoja", "pesada")],
        "error_fecha": error_fecha,
        "articulos_cliente": [],
        "resultado": None,
    }
    if cliente_valor is None or error_fecha:
        return templates.TemplateResponse(request, "gerencia_rentabilidad_real.html", contexto)

    try:
        fichas = listar_fichas_por_cliente(cliente_valor)
        contexto["articulos_cliente"] = [{"id": f["articulo_id"], "nombre": f["articulo_nombre"]} for f in fichas]
        contexto["resultado"] = _datos_rentabilidad_real(cliente_valor, desde, hasta, articulo_valor, grupo_valor)
        # La comparativa: la TEÓRICA del mismo rango, al lado. Las dos
        # salen del MISMO listado anclado, así que la diferencia es
        # exactamente la lista de cosas a explicar (merma, reproceso,
        # kilajes, lo que quedó afuera) — nunca ruido de cuentas distintas.
        teorica = _datos_rentabilidad(cliente_valor, desde, hasta, articulo_valor, grupo_valor, fichas)
        contexto["comparativa"] = {
            "teorica": teorica["totales"],
            "real": contexto["resultado"]["totales"],
            "diferencia": contexto["resultado"]["totales"]["renta_pesos"] - teorica["totales"]["renta_pesos"],
        }
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    return templates.TemplateResponse(request, "gerencia_rentabilidad_real.html", contexto)


def _resultado_rentabilidad_real_para_exportar(cliente_id, fecha_desde, fecha_hasta, articulo_id, grupo):
    """Los datos + textos de filtros para los exports de la Real (mismos filtros que la pantalla)."""
    cliente_valor, desde, hasta, articulo_valor, grupo_valor, error_fecha = _leer_filtros_rentabilidad(
        cliente_id, fecha_desde, fecha_hasta, articulo_id, grupo
    )
    if cliente_valor is None:
        raise HTTPException(status_code=400, detail="Elegí el cliente antes de exportar.")
    if error_fecha:
        raise HTTPException(status_code=400, detail=error_fecha)

    try:
        cliente_fila = obtener_cliente(cliente_valor)
        fichas = listar_fichas_por_cliente(cliente_valor)
        resultado = _datos_rentabilidad_real(cliente_valor, desde, hasta, articulo_valor, grupo_valor)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    articulos_cliente = [{"id": f["articulo_id"], "nombre": f["articulo_nombre"]} for f in fichas]
    nombre_cliente = cliente_fila["nombre"] if cliente_fila else f"#{cliente_valor}"
    filtros_texto = _filtros_texto_rentabilidad(nombre_cliente, articulo_valor, grupo_valor, articulos_cliente)
    return desde, hasta, filtros_texto, resultado


@app.get("/gerencia/rentabilidad-real/exportar-pdf")
def exportar_rentabilidad_real_pdf(
    request: Request,
    cliente_id: str = "", fecha_desde: str = "", fecha_hasta: str = "", articulo_id: str = "", grupo: str = "",
):
    """Genera la Rentabilidad Real (mismos filtros que la pantalla) en PDF — no se guarda en ningún lado. Zona con clave."""
    if not _acceso_gerencia_valido(request):
        return RedirectResponse(url="/gerencia/rentabilidad-real", status_code=303)
    desde, hasta, filtros_texto, resultado = _resultado_rentabilidad_real_para_exportar(
        cliente_id, fecha_desde, fecha_hasta, articulo_id, grupo
    )
    pdf_bytes = generar_pdf_rentabilidad_real(desde, hasta, filtros_texto, resultado)
    nombre_archivo = f"Rentabilidad_Real_{desde.isoformat()}_a_{hasta.isoformat()}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'},
    )


@app.get("/gerencia/rentabilidad-real/exportar-excel")
def exportar_rentabilidad_real_excel(
    request: Request,
    cliente_id: str = "", fecha_desde: str = "", fecha_hasta: str = "", articulo_id: str = "", grupo: str = "",
):
    """Genera la Rentabilidad Real (mismos filtros que la pantalla) en Excel — no se guarda en ningún lado. Zona con clave."""
    if not _acceso_gerencia_valido(request):
        return RedirectResponse(url="/gerencia/rentabilidad-real", status_code=303)
    desde, hasta, filtros_texto, resultado = _resultado_rentabilidad_real_para_exportar(
        cliente_id, fecha_desde, fecha_hasta, articulo_id, grupo
    )
    excel_bytes = generar_excel_rentabilidad_real(desde, hasta, filtros_texto, resultado)
    nombre_archivo = f"Rentabilidad_Real_{desde.isoformat()}_a_{hasta.isoformat()}.xlsx"
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'},
    )


# ---------------------------------------------------------------------------
# Costos Fijos (Gerencia): cuánto cuesta operar, por mes. El valor de cada
# mes se DERIVA siempre (foto + índices, core/costos_fijos.py) — regla 1
# del dueño: jamás se guarda un valor inflado. Toda la zona tras la clave.
# ---------------------------------------------------------------------------


def _mes_costos_fijos(texto: str | None):
    """El mes elegido ("YYYY-MM" del input month) o el actual; siempre día 1."""
    if texto:
        try:
            return date.fromisoformat(texto.strip() + "-01")
        except ValueError:
            pass
    hoy = _hoy_argentina()
    return date(hoy.year, hoy.month, 1)


def _datos_plan_costos_fijos():
    grupos = listar_grupos_costos_fijos()
    subcuentas = listar_subcuentas_costos_fijos()
    return grupos, subcuentas


@app.get("/gerencia/costos-fijos")
def ver_costos_fijos(request: Request, mes: str | None = None, grupo: str | None = None, aviso: str | None = None):
    """El costo fijo del mes: total, desglose por grupo y subcuenta, y lo que falta a la vista.

    Si falta el índice de algún mes del tramo de una foto, esa subcuenta
    NO entra al total y lo dice una tarjeta roja protagonista — regla 3:
    avisar, jamás usar el índice anterior en silencio.
    """
    if not _acceso_gerencia_valido(request):
        return _pantalla_clave_gerencia(request)
    mes_valor = _mes_costos_fijos(mes)
    grupo_numero = _id_opcional_desde_query(grupo)
    try:
        grupos, subcuentas = _datos_plan_costos_fijos()
        importes = listar_importes_costos_fijos()
        indices = {i["mes"]: float(i["porcentaje"]) for i in listar_indices_inflacion()}
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    resultado = calcular_costos_fijos(grupos, subcuentas, importes, indices, mes_valor, grupo_numero)
    contexto = {
        "resultado": resultado,
        "mes": mes_valor.strftime("%Y-%m"),
        "mes_mostrar": mes_valor.strftime("%m/%Y"),
        "grupo": grupo_numero,
        "grupos_para_filtro": [g for g in grupos if g.get("baja_el") is None],
        "aviso": aviso,
    }
    return templates.TemplateResponse(request, "gerencia_costos_fijos.html", contexto)


@app.get("/gerencia/costos-fijos/plan")
def ver_plan_costos_fijos(request: Request, aviso: str | None = None, error: str | None = None):
    """El plan de cuentas: los grupos con sus subcuentas y las altas — los números los elige el dueño."""
    if not _acceso_gerencia_valido(request):
        return _pantalla_clave_gerencia(request)
    try:
        grupos, subcuentas = _datos_plan_costos_fijos()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db
    por_grupo: dict = {}
    for subcuenta in subcuentas:
        por_grupo.setdefault(subcuenta["grupo_id"], []).append(subcuenta)
    contexto = {
        "grupos": [dict(g, subcuentas=por_grupo.get(g["id"], [])) for g in grupos],
        "aviso": aviso,
        "error": error,
    }
    return templates.TemplateResponse(request, "gerencia_costos_fijos_plan.html", contexto)


def _redirigir_a_plan(aviso: str | None = None, error: str | None = None):
    parametros = {}
    if aviso:
        parametros["aviso"] = aviso
    if error:
        parametros["error"] = error
    return RedirectResponse(url=f"/gerencia/costos-fijos/plan?{urlencode(parametros)}", status_code=303)


def _numero_de_cuenta(texto: str) -> int | None:
    texto = texto.strip()
    if not texto.isdigit() or int(texto) <= 0:
        return None
    return int(texto)


@app.post("/gerencia/costos-fijos/grupos")
def crear_grupo_costos_fijos_ruta(request: Request, numero: str = Form(""), nombre: str = Form("")):
    """Alta de grupo. El número lo pone el dueño (numeración espaciada, 10, 20...): el sistema no genera números."""
    if not _acceso_gerencia_valido(request):
        return _pantalla_clave_gerencia(request)
    numero_valor = _numero_de_cuenta(numero)
    nombre_limpio = re.sub(r"\s+", " ", nombre).strip()
    if numero_valor is None:
        return _redirigir_a_plan(error="El número del grupo tiene que ser un entero positivo (ej: 90).")
    if not nombre_limpio:
        return _redirigir_a_plan(error="El nombre del grupo es obligatorio.")
    try:
        grupos = listar_grupos_costos_fijos()
        if any(g["numero"] == numero_valor for g in grupos):
            ocupado = next(g for g in grupos if g["numero"] == numero_valor)
            return _redirigir_a_plan(error=f"El número {numero_valor} ya es de \"{ocupado['nombre']}\": elegí otro.")
        crear_grupo_costos_fijos(numero_valor, nombre_limpio)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"No se pudo crear el grupo: {error_db}") from error_db
    return _redirigir_a_plan(aviso=f"Grupo {numero_valor} {nombre_limpio} creado.")


@app.post("/gerencia/costos-fijos/subcuentas")
def crear_subcuenta_costos_fijos_ruta(
    request: Request, grupo_id: str = Form(""), numero: str = Form(""), nombre: str = Form("")
):
    """Alta de subcuenta dentro de su grupo (10.1, 10.2...): el decimal también lo elige el dueño."""
    if not _acceso_gerencia_valido(request):
        return _pantalla_clave_gerencia(request)
    numero_valor = _numero_de_cuenta(numero)
    nombre_limpio = re.sub(r"\s+", " ", nombre).strip()
    if not grupo_id.strip().isdigit():
        return _redirigir_a_plan(error="Elegí el grupo de la subcuenta.")
    if numero_valor is None:
        return _redirigir_a_plan(error="El número de la subcuenta tiene que ser un entero positivo (el 1 de 10.1).")
    if not nombre_limpio:
        return _redirigir_a_plan(error="El nombre de la subcuenta es obligatorio.")
    try:
        grupos = listar_grupos_costos_fijos()
        grupo = next((g for g in grupos if g["id"] == int(grupo_id)), None)
        if grupo is None:
            return _redirigir_a_plan(error="Ese grupo no existe.")
        subcuentas = listar_subcuentas_costos_fijos()
        ocupada = next(
            (s for s in subcuentas if s["grupo_id"] == grupo["id"] and s["numero"] == numero_valor), None
        )
        if ocupada is not None:
            return _redirigir_a_plan(
                error=f"El número {grupo['numero']}.{numero_valor} ya es de \"{ocupada['nombre']}\": elegí otro."
            )
        crear_subcuenta_costos_fijos(grupo["id"], numero_valor, nombre_limpio)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"No se pudo crear la subcuenta: {error_db}") from error_db
    return _redirigir_a_plan(aviso=f"Subcuenta {grupo['numero']}.{numero_valor} {nombre_limpio} creada.")


@app.get("/gerencia/costos-fijos/indices")
def ver_indices_inflacion(request: Request, aviso: str | None = None, error: str | None = None):
    """La tabla de índices mensuales: editable (es un parámetro), con los meses faltantes a cargar."""
    if not _acceso_gerencia_valido(request):
        return _pantalla_clave_gerencia(request)
    try:
        indices = listar_indices_inflacion()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db
    hoy = _hoy_argentina()
    contexto = {
        "indices": indices,
        "mes_actual": date(hoy.year, hoy.month, 1).strftime("%Y-%m"),
        "aviso": aviso,
        "error": error,
    }
    return templates.TemplateResponse(request, "gerencia_costos_fijos_indices.html", contexto)


@app.post("/gerencia/costos-fijos/indices")
def guardar_indice_inflacion_ruta(request: Request, mes: str = Form(""), porcentaje: str = Form("")):
    """Carga o corrige el índice de UN mes. Editar un mes pasado recalcula los meses que lo usan (decisión del dueño)."""
    if not _acceso_gerencia_valido(request):
        return _pantalla_clave_gerencia(request)
    try:
        mes_valor = date.fromisoformat(mes.strip() + "-01")
    except ValueError:
        return RedirectResponse(
            url=f"/gerencia/costos-fijos/indices?{urlencode({'error': 'El mes del índice no es válido.'})}",
            status_code=303,
        )
    try:
        porcentaje_valor = float(porcentaje.strip().replace(",", "."))
    except ValueError:
        return RedirectResponse(
            url=f"/gerencia/costos-fijos/indices?{urlencode({'error': 'El porcentaje tiene que ser un número (puede ser negativo).'})}",
            status_code=303,
        )
    try:
        guardar_indice_inflacion(mes_valor, porcentaje_valor)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"No se pudo guardar el índice: {error_db}") from error_db
    aviso = f"Índice de {mes_valor.strftime('%m/%Y')} guardado: {_formatear_numero(porcentaje_valor)}%."
    return RedirectResponse(
        url=f"/gerencia/costos-fijos/indices?{urlencode({'aviso': aviso})}", status_code=303
    )


@app.get("/gerencia/costos-fijos/subcuentas/{subcuenta_id}/cargar")
def ver_cargar_importe_costos_fijos(request: Request, subcuenta_id: int, error: str | None = None, precarga_importe: str | None = None, precarga_mes: str | None = None):
    """La carga de la foto de una subcuenta: importe + mes. La corrección es OTRA foto (vale de ahí en adelante)."""
    if not _acceso_gerencia_valido(request):
        return _pantalla_clave_gerencia(request)
    try:
        subcuenta = obtener_subcuenta_costos_fijos(subcuenta_id)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db
    if subcuenta is None:
        raise HTTPException(status_code=404, detail="Esa subcuenta no existe.")
    try:
        historial = listar_importes_de_subcuenta(subcuenta_id)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db
    hoy = _hoy_argentina()
    contexto = {
        "subcuenta": subcuenta,
        "historial": historial,
        "mes_actual": date(hoy.year, hoy.month, 1).strftime("%Y-%m"),
        "error": error,
        "precarga_importe": precarga_importe or "",
        "precarga_mes": precarga_mes or "",
    }
    return templates.TemplateResponse(request, "gerencia_costos_fijos_cargar.html", contexto)


@app.post("/gerencia/costos-fijos/subcuentas/{subcuenta_id}/cargar")
def cargar_importe_costos_fijos_ruta(
    request: Request, subcuenta_id: int, importe: str = Form(""), mes: str = Form("")
):
    """Guarda la foto: importe base con su mes. El valor de cada mes se CALCULA siempre — nada inflado se guarda."""
    if not _acceso_gerencia_valido(request):
        return _pantalla_clave_gerencia(request)
    try:
        subcuenta = obtener_subcuenta_costos_fijos(subcuenta_id)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db
    if subcuenta is None:
        raise HTTPException(status_code=404, detail="Esa subcuenta no existe.")

    def _volver_con_error(mensaje):
        parametros = {"error": mensaje, "precarga_importe": importe, "precarga_mes": mes}
        return RedirectResponse(
            url=f"/gerencia/costos-fijos/subcuentas/{subcuenta_id}/cargar?{urlencode(parametros)}",
            status_code=303,
        )

    try:
        importe_valor = float(importe.strip().replace(",", "."))
    except ValueError:
        return _volver_con_error("El importe tiene que ser un número.")
    if importe_valor < 0:
        return _volver_con_error("El importe no puede ser negativo.")
    try:
        mes_valor = date.fromisoformat(mes.strip() + "-01")
    except ValueError:
        return _volver_con_error("El mes de la foto no es válido.")

    try:
        crear_importe_costos_fijos(subcuenta_id, mes_valor, importe_valor)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"No se pudo guardar el importe: {error_db}") from error_db
    aviso = (
        f"Foto guardada: {subcuenta['grupo_numero']}.{subcuenta['numero']} {subcuenta['nombre']} = "
        f"${_formatear_numero(importe_valor)} desde {mes_valor.strftime('%m/%Y')} — de ahí en adelante infla por índice."
    )
    return RedirectResponse(
        url=f"/gerencia/costos-fijos?{urlencode({'mes': mes_valor.strftime('%Y-%m'), 'aviso': aviso})}",
        status_code=303,
    )


@app.get("/administracion")
def ver_administracion(request: Request):
    """Hub de Administración: lo que se mira y se corrige. El depósito hace; acá se controla.

    Con banner: desde que Stock del Sistema y Guías R viven acá, sus
    alertas avisan en este módulo. Sin el banner, esas alertas no se
    verían en ninguna botonera — solo en Auditoría, que es justo lo que
    el banner vino a evitar.
    """
    return templates.TemplateResponse(
        request, "administracion.html", {"banner": _banner_alertas("administracion")}
    )


ESTADOS_FILTRO_INGRESOS_VALIDOS = {"recepcionado", "rechazado", "no_ingresado", "todas"}

ETIQUETAS_ESTADO_INGRESO = {
    "recepcionado": "Recepcionada",
    "rechazado": "Rechazo total",
    "no_ingresado": "No ingresó",
}


def _grupos_ingresos_deposito(ingresos: list[dict]) -> tuple[list[dict], dict]:
    """Agrupa los ingresos por proveedor con su subtotal (así se factura), y arma el total general.

    Por fila: mercadería = cantidad_cajones_real × importe (el precio es
    por bulto) y señas = cantidad_cajones_real × seña. El TOTAL de la
    fila es lo que hay que depositarle al proveedor: mercadería + señas
    de los cajones — con eso se concilia contra la cuenta del proveedor
    sin sacar cuentas aparte. Los subtotales y el total general llevan
    las dos partes desglosadas, para poder cruzarlas por separado.

    Sin precio cargado no hay total — la fila queda marcada (sin_precio)
    porque es lo que falta completar antes de facturar; una rechazada
    total o no ingresada sin precio NO se marca (no se paga, no hay nada
    que completar). Las cantidades son SIEMPRE las reales que pesó/contó
    Depósito, nunca las del comprador.
    """
    grupos: list[dict] = []
    grupos_por_proveedor: dict[str, dict] = {}
    total_mercaderia = 0.0
    total_senas = 0.0
    cantidad_sin_precio = 0

    for ingreso in ingresos:
        clave = ingreso["proveedor_codigo_puesto"]
        grupo = grupos_por_proveedor.get(clave)
        if grupo is None:
            grupo = {
                "proveedor_nombre": ingreso["proveedor_nombre"],
                "proveedor_codigo_puesto": clave,
                "filas": [],
                "subtotal": 0.0,
                "subtotal_mercaderia": 0.0,
                "subtotal_senas": 0.0,
                "sin_precio": 0,
            }
            grupos_por_proveedor[clave] = grupo
            grupos.append(grupo)

        cajones = float(ingreso["cantidad_cajones_real"]) if ingreso["cantidad_cajones_real"] is not None else None
        importe = float(ingreso["importe"]) if ingreso["importe"] is not None else None
        total = cajones * importe if cajones is not None and importe is not None else None
        sin_precio = importe is None and ingreso["estado"] == "recepcionado"
        # La seña es por cajón (como el importe): el total señado sale de
        # los cajones REALES que entraron, igual que el total a pagar.
        sena = float(ingreso["sena"]) if ingreso.get("sena") is not None else None
        total_sena = cajones * sena if cajones is not None and sena is not None else None

        # El total de la fila es lo que se le deposita al proveedor por
        # ese renglón: la mercadería más la seña de sus cajones.
        total_a_depositar = None
        if total is not None or total_sena is not None:
            total_a_depositar = (total or 0.0) + (total_sena or 0.0)
        if total is not None:
            grupo["subtotal_mercaderia"] += total
            total_mercaderia += total
        if total_sena is not None:
            grupo["subtotal_senas"] += total_sena
            total_senas += total_sena
        if total_a_depositar is not None:
            grupo["subtotal"] += total_a_depositar
        if sin_precio:
            grupo["sin_precio"] += 1
            cantidad_sin_precio += 1

        etiqueta = ETIQUETAS_ESTADO_INGRESO.get(ingreso["estado"], ingreso["estado"])
        if ingreso["estado"] == "recepcionado" and ingreso["cantidad_cajones_rechazada"] is not None:
            etiqueta = "Rechazo parcial"

        grupo["filas"].append(
            {**ingreso, "total": total, "sin_precio": sin_precio, "estado_etiqueta": etiqueta,
             "sena": sena, "total_sena": total_sena, "total_a_depositar": total_a_depositar}
        )

    totales = {
        "total_general": total_mercaderia + total_senas,
        "total_mercaderia": total_mercaderia,
        "total_senas": total_senas,
        "cantidad_sin_precio": cantidad_sin_precio,
    }
    return grupos, totales


@app.get("/facturacion")
def ver_facturacion_url_vieja():
    """La URL vieja (cuando el módulo se llamaba Facturación) sigue llegando: redirige."""
    return RedirectResponse(url="/administracion", status_code=301)


@app.get("/facturacion/ingresos")
def ver_ingresos_url_vieja(request: Request):
    """Ídem: el link viejo de Ingresos a Depósito, con sus filtros si los traía."""
    consulta = request.url.query
    return RedirectResponse(url="/administracion/ingresos" + (f"?{consulta}" if consulta else ""),
                            status_code=301)


@app.get("/administracion/ingresos")
def ver_ingresos_deposito(
    request: Request,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
    proveedor_id: str | None = None,
    articulo_id: str | None = None,
    estado: str | None = None,
):
    """Ingresos a Depósito: lo que realmente entró, para cargarlo en facturación y pagarle a cada proveedor.

    El rango filtra por el día de la RECEPCIÓN (procesada_el, default
    últimas 48 hs). Por default muestra solo lo recepcionado (incluidos
    los rechazos parciales: son recepciones y se pagan por los bultos
    aceptados); "Rechazo total" y "No ingresó" no se pagan y quedan
    detrás del filtro de estado, para control.
    """
    proveedor_id_valor = _id_opcional_desde_query(proveedor_id)
    articulo_id_valor = _id_opcional_desde_query(articulo_id)
    estado_valor = estado if estado in ESTADOS_FILTRO_INGRESOS_VALIDOS else "recepcionado"
    estado_consulta = None if estado_valor == "todas" else estado_valor

    hoy = _hoy_argentina()
    fecha_desde_valor = hoy - timedelta(days=1)
    fecha_hasta_valor = hoy
    error_fecha = None
    if fecha_desde:
        try:
            fecha_desde_valor = date.fromisoformat(fecha_desde)
        except ValueError:
            error_fecha = "La fecha desde no es válida."
    if fecha_hasta:
        try:
            fecha_hasta_valor = date.fromisoformat(fecha_hasta)
        except ValueError:
            error_fecha = "La fecha hasta no es válida."
    if error_fecha is None and fecha_desde_valor > fecha_hasta_valor:
        error_fecha = "La fecha desde no puede ser posterior a la fecha hasta."

    try:
        proveedores = listar_proveedores()
        articulos = listar_articulos()
        # Mismo tope que Buscar Compras/Consultar Retiros: si la lista se
        # corta, los totales NO se muestran (un total parcial para
        # facturar sería un número falso con plata de por medio).
        ingresos = buscar_ingresos_deposito(
            fecha_desde_valor, fecha_hasta_valor, proveedor_id_valor, articulo_id_valor, estado_consulta,
            limite=TOPE_FILAS_BUSQUEDA + 1,
        )
        aviso_tope = None
        if len(ingresos) > TOPE_FILAS_BUSQUEDA:
            total = contar_ingresos_deposito(
                fecha_desde_valor, fecha_hasta_valor, proveedor_id_valor, articulo_id_valor, estado_consulta
            )
            ingresos = ingresos[:TOPE_FILAS_BUSQUEDA]
            aviso_tope = (
                f"Se muestran los primeros {TOPE_FILAS_BUSQUEDA} ingresos de {total}, y por eso los totales "
                "no se calculan (saldrían incompletos): achicá el rango o filtrá para ver todo."
            )
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    grupos, totales = _grupos_ingresos_deposito(ingresos)

    return templates.TemplateResponse(
        request,
        "administracion_ingresos.html",
        {
            "proveedores": proveedores,
            "articulos": articulos,
            "fecha_desde": fecha_desde_valor.isoformat(),
            "fecha_hasta": fecha_hasta_valor.isoformat(),
            "proveedor_id": proveedor_id_valor,
            "articulo_id": articulo_id_valor,
            "estado": estado_valor,
            "error_fecha": error_fecha,
            "grupos": grupos,
            "cantidad_ingresos": len(ingresos),
            "aviso_tope": aviso_tope,
            **totales,
        },
    )


def _leer_filtros_exportar_ingresos(
    fecha_desde_texto: str, fecha_hasta_texto: str, proveedor_id_texto: str, articulo_id_texto: str, estado_texto: str
) -> tuple[date, date, int | None, int | None, str | None, list[str]]:
    """Valida los filtros para exportar ingresos y arma los textos del subtítulo (mismo criterio que retiros)."""
    try:
        fecha_desde = date.fromisoformat(fecha_desde_texto)
        fecha_hasta = date.fromisoformat(fecha_hasta_texto)
    except ValueError:
        raise HTTPException(status_code=400, detail="Fecha inválida")

    proveedor_id = _id_opcional_desde_query(proveedor_id_texto)
    articulo_id = _id_opcional_desde_query(articulo_id_texto)
    estado_valor = estado_texto if estado_texto in ESTADOS_FILTRO_INGRESOS_VALIDOS else "recepcionado"
    estado_consulta = None if estado_valor == "todas" else estado_valor

    filtros_texto = []
    if proveedor_id is not None:
        try:
            nombre = next((p["nombre"] for p in listar_proveedores() if p["id"] == proveedor_id), None)
        except Exception:
            nombre = None
        filtros_texto.append(f"proveedor {nombre or f'#{proveedor_id}'}")
    if articulo_id is not None:
        try:
            nombre = next((a["nombre"] for a in listar_articulos() if a["id"] == articulo_id), None)
        except Exception:
            nombre = None
        filtros_texto.append(f"artículo {nombre or f'#{articulo_id}'}")
    if estado_valor == "todas":
        filtros_texto.append("todos los estados")
    elif estado_valor != "recepcionado":
        filtros_texto.append(f"estado {ETIQUETAS_ESTADO_INGRESO[estado_valor]}")

    return fecha_desde, fecha_hasta, proveedor_id, articulo_id, estado_consulta, filtros_texto


@app.get("/administracion/ingresos/exportar-pdf")
def exportar_ingresos_deposito_pdf(
    fecha_desde: str = "", fecha_hasta: str = "", proveedor_id: str = "", articulo_id: str = "", estado: str = ""
):
    """Genera Ingresos a Depósito (mismos filtros que la pantalla) en PDF — SIN tope, aunque la pantalla corte."""
    desde, hasta, proveedor_valor, articulo_valor, estado_consulta, filtros_texto = _leer_filtros_exportar_ingresos(
        fecha_desde, fecha_hasta, proveedor_id, articulo_id, estado
    )
    try:
        ingresos = buscar_ingresos_deposito(desde, hasta, proveedor_valor, articulo_valor, estado_consulta)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    grupos, totales = _grupos_ingresos_deposito(ingresos)
    pdf_bytes = generar_pdf_ingresos_deposito(desde, hasta, filtros_texto, grupos, totales)
    nombre_archivo = f"Ingresos_Deposito_{desde.isoformat()}_a_{hasta.isoformat()}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'},
    )


@app.get("/administracion/ingresos/exportar-excel")
def exportar_ingresos_deposito_excel(
    fecha_desde: str = "", fecha_hasta: str = "", proveedor_id: str = "", articulo_id: str = "", estado: str = ""
):
    """Genera Ingresos a Depósito (mismos filtros que la pantalla) en Excel — SIN tope, aunque la pantalla corte."""
    desde, hasta, proveedor_valor, articulo_valor, estado_consulta, filtros_texto = _leer_filtros_exportar_ingresos(
        fecha_desde, fecha_hasta, proveedor_id, articulo_id, estado
    )
    try:
        ingresos = buscar_ingresos_deposito(desde, hasta, proveedor_valor, articulo_valor, estado_consulta)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    grupos, totales = _grupos_ingresos_deposito(ingresos)
    excel_bytes = generar_excel_ingresos_deposito(desde, hasta, filtros_texto, grupos, totales)
    nombre_archivo = f"Ingresos_Deposito_{desde.isoformat()}_a_{hasta.isoformat()}.xlsx"
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'},
    )


@app.get("/puesto")
def ver_puesto(request: Request):
    """Hub del módulo Puesto (la venta en el puesto del Mercado, aparte de la distribución)."""
    return templates.TemplateResponse(request, "puesto.html", {"banner": _banner_alertas("puesto")})


@app.get("/puesto/envases")
def ver_envases_puesto(request: Request):
    """Hub de Envases Puesto: cajones físicos de proveedores que entran y salen del puesto.

    NADA que ver con /envases de Comercial (el costo del envase facturado
    al cliente de distribución). Este hub es de la cajera/dueño; lo que
    puede ver el empleado del fondo está un nivel más adentro, en
    /puesto/envases/vacios — separación pensada para colgarle permisos
    cuando haya login, sin inventar contraseñas ahora.
    """
    return templates.TemplateResponse(request, "puesto_envases.html", {})


@app.post("/puesto/envases/clave")
def ingresar_clave_control_ruta(request: Request, clave: str = Form(""), volver: str = Form("/puesto/envases")):
    """Valida la clave de la zona de control y deja la cookie firmada: una vez por jornada, para toda la zona."""
    destino = _destino_control_seguro(volver)
    clave_real = _clave_control_puesto()
    if clave_real is None:
        # Sin clave configurada no hay puerta: nada que validar.
        return RedirectResponse(url=destino, status_code=303)
    if not hmac.compare_digest(clave.strip(), clave_real):
        return _pantalla_clave_control(request, volver=destino, error="Clave incorrecta.")

    respuesta = RedirectResponse(url=destino, status_code=303)
    respuesta.set_cookie(
        COOKIE_ACCESO_CONTROL,
        _firma_acceso_control(clave_real),
        max_age=DURACION_ACCESO_CONTROL,
        httponly=True,
        samesite="lax",
        path="/puesto/envases",
    )
    return respuesta


@app.post("/puesto/envases/bloquear")
def bloquear_control_puesto_ruta(request: Request):
    """Borra la cookie de acceso en el momento: para no dejar la zona de control abierta en un celular suelto."""
    respuesta = RedirectResponse(url="/puesto/envases", status_code=303)
    respuesta.delete_cookie(COOKIE_ACCESO_CONTROL, path="/puesto/envases")
    return respuesta


@app.get("/puesto/envases/vacios")
def ver_vacios(request: Request, aviso: str | None = None):
    """Hub de Vacíos: las tres pantallas del empleado del fondo del puesto.

    "aviso" llega desde los redirects post-guardado de Recibir y Devolver:
    la confirmación se muestra acá, adonde vuelve el empleado.
    """
    return templates.TemplateResponse(request, "vacios.html", {"aviso": aviso})


def _validar_cantidad_vacios(texto: str) -> tuple[str | None, int | None]:
    """Valida la cantidad de cajones de un movimiento de Vacíos: obligatoria, entero positivo."""
    texto = texto.strip()
    if not texto:
        return "La cantidad de cajones es obligatoria.", None
    try:
        valor = int(texto)
    except ValueError:
        return "La cantidad de cajones tiene que ser un número entero.", None
    if valor <= 0:
        return "La cantidad de cajones tiene que ser mayor a cero.", None
    return None, valor


def _tipos_envase_y_proveedores():
    """Tipos de envase activos + los proveedores del puesto derivados de ellos.

    Lista cerrada de verdad para el empleado: solo proveedores del puesto
    (tabla proveedores_puesto — NUNCA los de Compras) y solo los que
    tienen tipos cargados por la cajera.
    """
    tipos = listar_tipos_envase_puesto()
    proveedores = []
    vistos = set()
    for tipo in tipos:
        if tipo["proveedor_id"] not in vistos:
            vistos.add(tipo["proveedor_id"])
            proveedores.append({"id": tipo["proveedor_id"], "nombre": tipo["proveedor_nombre"]})
    return tipos, proveedores


def _renderizar_pantalla_recibir_vacios(request: Request, *, error=None, aviso=None, status_code: int = 200):
    try:
        tipos, proveedores = _tipos_envase_y_proveedores()
        clientes = listar_clientes_puesto()
        recibidos_hoy = listar_vacios_recibidos_de_fecha(_hoy_argentina())
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    return templates.TemplateResponse(
        request,
        "vacios_recibir.html",
        {
            "tipos": tipos,
            "proveedores": proveedores,
            "clientes": clientes,
            "recibidos_hoy": recibidos_hoy,
            "error": error,
            "aviso": aviso,
        },
        status_code=status_code,
    )


@app.get("/puesto/envases/vacios/recibir")
def ver_recibir_vacios(request: Request, aviso: str | None = None):
    return _renderizar_pantalla_recibir_vacios(request, aviso=aviso)


@app.post("/puesto/envases/vacios/recibir")
def recibir_vacios_ruta(
    request: Request,
    cliente_nombre: str = Form(""),
    proveedor_id: str = Form(""),
    tipo_envase_id: str = Form(""),
    cantidad: str = Form(""),
):
    """Entrada de vacíos: cliente (tipeado o elegido), proveedor de lista cerrada, tipo del proveedor, cantidad.

    El cliente se crea con solo el nombre si no existe — pero por nombre
    NORMALIZADO (ver obtener_o_crear_cliente_puesto): "Juan", "juan " y
    "JUAN" terminan siendo el mismo cliente, nunca tres.
    """
    nombre_limpio = re.sub(r"\s+", " ", cliente_nombre).strip()
    nombre_normalizado = normalizar_texto(nombre_limpio)
    error = None
    if not nombre_normalizado:
        error = "El nombre del cliente es obligatorio."

    cantidad_valor = None
    if not error:
        error, cantidad_valor = _validar_cantidad_vacios(cantidad)

    tipo_elegido = None
    if not error:
        try:
            tipos, _ = _tipos_envase_y_proveedores()
        except Exception as error_db:
            raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db
        # Lista cerrada de verdad: proveedor y tipo tienen que ser un par
        # válido de los tipos cargados — no vale mandar cualquier id.
        tipo_elegido = next(
            (
                t
                for t in tipos
                if str(t["id"]) == tipo_envase_id.strip() and str(t["proveedor_id"]) == proveedor_id.strip()
            ),
            None,
        )
        if tipo_elegido is None:
            error = "Elegí un proveedor y un tipo de envase válidos."

    if error:
        return _renderizar_pantalla_recibir_vacios(request, error=error, status_code=400)

    try:
        cliente_id = obtener_o_crear_cliente_puesto(nombre_limpio, nombre_normalizado)
        crear_vacio_recibido(cliente_id, tipo_elegido["proveedor_id"], tipo_elegido["id"], cantidad_valor)
    except Exception as error_db:
        return _renderizar_pantalla_recibir_vacios(
            request, error=f"No se pudo guardar la entrada: {error_db}", status_code=500
        )

    aviso = (
        f"Recibidos {cantidad_valor} cajones ({tipo_elegido['nombre']}) de "
        f"{tipo_elegido['proveedor_nombre']}, traídos por {nombre_limpio}."
    )
    return RedirectResponse(url=f"/puesto/envases/vacios?{urlencode({'aviso': aviso})}", status_code=303)


@app.post("/puesto/envases/vacios/recibidos/{movimiento_id}/anular")
def anular_vacio_recibido_ruta(request: Request, movimiento_id: int):
    """Anula una entrada desde la lista "Recibido hoy" (error del momento). Baja lógica, nunca DELETE."""
    try:
        anular_vacio_recibido(movimiento_id)
    except Exception as error_db:
        return _renderizar_pantalla_recibir_vacios(
            request, error=f"No se pudo anular el movimiento: {error_db}", status_code=500
        )
    return RedirectResponse(url="/puesto/envases/vacios/recibir", status_code=303)


def _renderizar_pantalla_devolver_vacios(request: Request, *, error=None, aviso=None, status_code: int = 200):
    try:
        tipos, proveedores = _tipos_envase_y_proveedores()
        devueltos_hoy = listar_vacios_devueltos_de_fecha(_hoy_argentina())
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    return templates.TemplateResponse(
        request,
        "vacios_devolver.html",
        {
            "tipos": tipos,
            "proveedores": proveedores,
            "devueltos_hoy": devueltos_hoy,
            "error": error,
            "aviso": aviso,
        },
        status_code=status_code,
    )


@app.get("/puesto/envases/vacios/devolver")
def ver_devolver_vacios(request: Request, aviso: str | None = None):
    return _renderizar_pantalla_devolver_vacios(request, aviso=aviso)


@app.post("/puesto/envases/vacios/devolver")
def devolver_vacios_ruta(
    request: Request,
    proveedor_id: str = Form(""),
    tipo_envase_id: str = Form(""),
    cantidad: str = Form(""),
):
    """Salida de vacíos: el proveedor se lleva sus cajones. Nunca se bloquea por stock: se registra la realidad.

    Si la cantidad supera lo que el sistema decía, la diferencia queda
    GRABADA en el movimiento (stock_sistema) y el aviso lo dice — el
    negativo después se ve en Stock del Sistema y en el Cotejo.
    """
    error, cantidad_valor = _validar_cantidad_vacios(cantidad)

    tipo_elegido = None
    if not error:
        try:
            tipos, _ = _tipos_envase_y_proveedores()
        except Exception as error_db:
            raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db
        tipo_elegido = next(
            (
                t
                for t in tipos
                if str(t["id"]) == tipo_envase_id.strip() and str(t["proveedor_id"]) == proveedor_id.strip()
            ),
            None,
        )
        if tipo_elegido is None:
            error = "Elegí un proveedor y un tipo de envase válidos."

    if error:
        return _renderizar_pantalla_devolver_vacios(request, error=error, status_code=400)

    try:
        stock_sistema = crear_vacio_devuelto(tipo_elegido["proveedor_id"], tipo_elegido["id"], cantidad_valor)
    except Exception as error_db:
        return _renderizar_pantalla_devolver_vacios(
            request, error=f"No se pudo guardar la devolución: {error_db}", status_code=500
        )

    aviso = f"Devueltos {cantidad_valor} cajones ({tipo_elegido['nombre']}) a {tipo_elegido['proveedor_nombre']}."
    if cantidad_valor > stock_sistema:
        aviso += (
            f" Ojo: según el sistema había {stock_sistema} — la diferencia quedó registrada"
            " para revisar en el Cotejo."
        )
    return RedirectResponse(url=f"/puesto/envases/vacios?{urlencode({'aviso': aviso})}", status_code=303)


@app.post("/puesto/envases/vacios/devueltos/{movimiento_id}/anular")
def anular_vacio_devuelto_ruta(request: Request, movimiento_id: int):
    """Anula una salida desde la lista "Devuelto hoy". Baja lógica, nunca DELETE."""
    try:
        anular_vacio_devuelto(movimiento_id)
    except Exception as error_db:
        return _renderizar_pantalla_devolver_vacios(
            request, error=f"No se pudo anular el movimiento: {error_db}", status_code=500
        )
    return RedirectResponse(url="/puesto/envases/vacios/devolver", status_code=303)


def _fecha_consulta_stock_vacios(fecha_texto: str | None):
    """La fecha elegida para consultar el stock, o hoy. Fechas mal escritas o futuras caen a hoy."""
    hoy = _hoy_argentina()
    if not fecha_texto:
        return hoy
    try:
        fecha = date.fromisoformat(fecha_texto)
    except ValueError:
        return hoy
    return fecha if fecha <= hoy else hoy


def _grupos_stock_vacios(fecha_consulta) -> list[dict]:
    """El stock a una fecha, agrupado por proveedor para mostrar/exportar: encabezado + una fila por tipo."""
    filas = stock_vacios(fecha_consulta)
    grupos: list[dict] = []
    grupos_por_proveedor: dict[int, dict] = {}
    for fila in filas:
        grupo = grupos_por_proveedor.get(fila["proveedor_id"])
        if grupo is None:
            grupo = {
                "proveedor_nombre": fila["proveedor_nombre"],
                "tipos": [],
                "total": 0,
            }
            grupos_por_proveedor[fila["proveedor_id"]] = grupo
            grupos.append(grupo)
        grupo["tipos"].append(fila)
        grupo["total"] += fila["stock"]
    return grupos


@app.get("/puesto/envases/stock")
def ver_stock_vacios(request: Request, fecha: str | None = None):
    """Stock del sistema por proveedor y tipo a una fecha (por default hoy). La ve la cajera, NO el empleado del fondo.

    Para una fecha pasada la pantalla avisa que el número puede cambiar: un
    movimiento anulado se descuenta DESDE SIEMPRE (si no existió, no existió
    nunca), así que anular hoy un movimiento viejo también corrige el stock
    de los días anteriores.
    """
    if not _acceso_control_valido(request):
        return _pantalla_clave_control(request)
    fecha_consulta = _fecha_consulta_stock_vacios(fecha)
    try:
        grupos = _grupos_stock_vacios(fecha_consulta)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    return templates.TemplateResponse(
        request,
        "vacios_stock.html",
        {
            "grupos": grupos,
            "fecha": fecha_consulta.isoformat(),
            "fecha_mostrar": fecha_consulta.strftime("%d/%m/%Y"),
            "es_pasada": fecha_consulta < _hoy_argentina(),
        },
    )


@app.get("/puesto/envases/stock/exportar-pdf")
def exportar_stock_vacios_pdf(request: Request, fecha: str = ""):
    """Genera el Stock del Sistema a una fecha en PDF — no se guarda en ningún lado. Zona de control: pide la clave."""
    if not _acceso_control_valido(request):
        return RedirectResponse(url="/puesto/envases/stock", status_code=303)
    fecha_consulta = _fecha_consulta_stock_vacios(fecha)
    try:
        grupos = _grupos_stock_vacios(fecha_consulta)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    pdf_bytes = generar_pdf_stock_vacios(fecha_consulta, fecha_consulta < _hoy_argentina(), grupos)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="Stock_Vacios_{fecha_consulta.isoformat()}.pdf"'},
    )


@app.get("/puesto/envases/stock/exportar-excel")
def exportar_stock_vacios_excel(request: Request, fecha: str = ""):
    """Genera el Stock del Sistema a una fecha en Excel — no se guarda en ningún lado. Zona de control: pide la clave."""
    if not _acceso_control_valido(request):
        return RedirectResponse(url="/puesto/envases/stock", status_code=303)
    fecha_consulta = _fecha_consulta_stock_vacios(fecha)
    try:
        grupos = _grupos_stock_vacios(fecha_consulta)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    excel_bytes = generar_excel_stock_vacios(fecha_consulta, fecha_consulta < _hoy_argentina(), grupos)
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="Stock_Vacios_{fecha_consulta.isoformat()}.xlsx"'},
    )


def _renderizar_pantalla_tipos_envase_puesto(request: Request, *, error=None, aviso=None,
                                            advertencia=None, pendiente=None, status_code: int = 200):
    """Tipos de envase con su seña: son atributos de la misma cosa, se manejan juntos.

    `advertencia` + `pendiente` son la carga retroactiva esperando el
    segundo toque; `pendiente.tipo_envase_id` dice qué renglón la abrió.
    """
    try:
        tipos = listar_tipos_envase_puesto()
        # Proveedores del PUESTO, nunca los de Compras: circuitos separados.
        proveedores = listar_proveedores_puesto()
        # El valor vigente HOY de cada tipo, y el historial de todos en una
        # sola consulta (no una por renglón).
        valores = {v["tipo_envase_id"]: v for v in listar_valores_sena()}
        historiales = listar_historiales_valores_sena([t["id"] for t in tipos])
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    return templates.TemplateResponse(
        request,
        "vacios_tipos.html",
        {"tipos": tipos, "proveedores": proveedores, "valores": valores,
         "historiales": historiales, "hoy": date.today(),
         "error": error, "aviso": aviso, "advertencia": advertencia, "pendiente": pendiente},
        status_code=status_code,
    )


def _monto_de_sena(texto: str):
    """Parsea el monto del formulario. Devuelve (monto, error); monto None = no se cargó ninguno.

    Vacío NO es cero: es "no toques la seña". El cero explícito sí es un
    dato ("este envase no lleva seña"), así que el corte es en el negativo.
    """
    limpio = (texto or "").strip().replace(",", ".")
    if not limpio:
        return None, None
    try:
        monto = float(limpio)
    except ValueError:
        return None, "El monto de la seña tiene que ser un número."
    if monto < 0:
        return None, "El monto de la seña no puede ser negativo."
    return monto, None


def _fecha_de_vigencia(texto: str):
    """La fecha desde la que rige el monto. Vacía = hoy."""
    limpio = (texto or "").strip()
    if not limpio:
        return date.today(), None
    try:
        return date.fromisoformat(limpio), None
    except ValueError:
        return None, "La fecha desde cuándo rige la seña no es válida."


@app.get("/puesto/envases/tipos")
def ver_tipos_envase_puesto(request: Request, aviso: str | None = None):
    """ABM de tipos de cajón por proveedor (lo carga el dueño). Un proveedor sin tipos no aparece en Vacíos."""
    if not _acceso_control_valido(request):
        return _pantalla_clave_control(request)
    return _renderizar_pantalla_tipos_envase_puesto(request, aviso=aviso)


@app.post("/puesto/envases/tipos/nuevo")
def crear_tipo_envase_puesto_ruta(request: Request, proveedor_id: str = Form(""), nombre: str = Form(""),
                                  monto: str = Form(""), vigente_desde: str = Form("")):
    """Alta de un tipo de cajón, con el valor de la seña OPCIONAL.

    Opcional a propósito: si fuera obligatorio, el día que no se sepa
    cuánto vale la seña van a inventar un número para poder seguir, y un
    número inventado es peor que "sin valor cargado" — se paga.

    El tipo nace igual sin seña; la seña se le carga después desde su
    propio renglón.
    """
    if not _acceso_control_valido(request):
        return RedirectResponse(url="/puesto/envases/tipos", status_code=303)
    nombre_limpio = re.sub(r"\s+", " ", nombre).strip()
    if not nombre_limpio:
        return _renderizar_pantalla_tipos_envase_puesto(
            request, error="El nombre del tipo de envase es obligatorio.", status_code=400
        )
    if not proveedor_id.strip().isdigit():
        return _renderizar_pantalla_tipos_envase_puesto(request, error="Elegí un proveedor.", status_code=400)

    monto_valor, error_monto = _monto_de_sena(monto)
    if error_monto:
        return _renderizar_pantalla_tipos_envase_puesto(request, error=error_monto, status_code=400)
    fecha, error_fecha = _fecha_de_vigencia(vigente_desde)
    if error_fecha:
        return _renderizar_pantalla_tipos_envase_puesto(request, error=error_fecha, status_code=400)

    try:
        tipo_id = crear_tipo_envase_puesto(int(proveedor_id), nombre_limpio)
        # Sin aviso retroactivo acá: un tipo recién creado no tiene señas
        # recibidas, así que no hay nada viejo que mover. (Si el alta
        # reactivó uno dado de baja, sus señas viejas están cerradas o
        # ancladas a fechas anteriores; el aviso vive en el renglón.)
        if monto_valor is not None:
            cargar_valor_sena(tipo_id, monto_valor, fecha)
    except Exception as error_db:
        return _renderizar_pantalla_tipos_envase_puesto(
            request, error=f"No se pudo crear el tipo de envase: {error_db}", status_code=500
        )

    detalle = "" if monto_valor is None else f" con seña de {_formatear_moneda(monto_valor)}"
    parametros = urlencode({"aviso": f"Tipo de envase '{nombre_limpio}' cargado{detalle}."})
    return RedirectResponse(url=f"/puesto/envases/tipos?{parametros}", status_code=303)


@app.post("/puesto/envases/tipos/{tipo_id}/editar")
def editar_tipo_envase_puesto_ruta(request: Request, tipo_id: int, nombre: str = Form(""),
                                   monto: str = Form(""), vigente_desde: str = Form(""),
                                   confirmado: str = Form("")):
    """Corrige el nombre de un tipo de cajón y, si viene monto, le carga el valor de la seña.

    Nombre y seña son atributos de la misma cosa y se editan en el mismo
    bloque. El monto VACÍO significa "no toques la seña", no cero: quien
    entra a arreglar un tipeo no tiene por qué cargar un valor.

    Si la fecha elegida mueve señas ya recibidas, la pantalla avisa con el
    número y pide un segundo toque. AVISA, NO TRABA: cargar tarde lo que
    rige desde la semana pasada es legítimo — lo que no puede pasar es que
    la plata de señas viejas cambie sin que el que la cargó se entere. El
    aviso va ANTES de escribir nada, así que ni el nombre ni la seña se
    guardan a medias.
    """
    if not _acceso_control_valido(request):
        return RedirectResponse(url="/puesto/envases/tipos", status_code=303)
    nombre_limpio = re.sub(r"\s+", " ", nombre).strip()
    if not nombre_limpio:
        return _renderizar_pantalla_tipos_envase_puesto(
            request, error="El nombre del tipo de envase es obligatorio.", status_code=400
        )
    monto_valor, error_monto = _monto_de_sena(monto)
    if error_monto:
        return _renderizar_pantalla_tipos_envase_puesto(request, error=error_monto, status_code=400)
    fecha, error_fecha = _fecha_de_vigencia(vigente_desde)
    if error_fecha:
        return _renderizar_pantalla_tipos_envase_puesto(request, error=error_fecha, status_code=400)

    try:
        if monto_valor is not None and confirmado != "1":
            afectadas = contar_senas_afectadas_por_valor(tipo_id, monto_valor, fecha)
            if afectadas:
                return _renderizar_pantalla_tipos_envase_puesto(
                    request,
                    advertencia=(
                        f"Esto cambia el valor de {afectadas} "
                        f"{'seña ya recibida' if afectadas == 1 else 'señas ya recibidas'}."
                    ),
                    pendiente={"tipo_envase_id": tipo_id, "nombre": nombre_limpio,
                               "monto": monto_valor, "vigente_desde": fecha},
                    status_code=200,
                )
        renombrar_tipo_envase_puesto(tipo_id, nombre_limpio)
        if monto_valor is not None:
            cargar_valor_sena(tipo_id, monto_valor, fecha)
    except ValueError as error:
        # Nombre repetido o tipo dado de baja: es dato mal cargado, no una
        # falla del sistema. 400 con el mensaje, nunca 500.
        return _renderizar_pantalla_tipos_envase_puesto(request, error=str(error), status_code=400)
    except Exception as error_db:
        return _renderizar_pantalla_tipos_envase_puesto(
            request, error=f"No se pudo guardar el tipo de envase: {error_db}", status_code=500
        )

    if monto_valor is None:
        aviso = f"Tipo de envase guardado como '{nombre_limpio}'."
    else:
        aviso = (f"'{nombre_limpio}': seña de {_formatear_moneda(monto_valor)} "
                 f"desde el {fecha.strftime('%d/%m/%Y')}.")
    return RedirectResponse(url=f"/puesto/envases/tipos?{urlencode({'aviso': aviso})}", status_code=303)


@app.post("/puesto/envases/tipos/{tipo_id}/baja")
def dar_de_baja_tipo_envase_puesto_ruta(request: Request, tipo_id: int):
    if not _acceso_control_valido(request):
        return RedirectResponse(url="/puesto/envases/tipos", status_code=303)
    try:
        desactivar_tipo_envase_puesto(tipo_id)
    except ValueError as error:
        # Con saldo abierto la baja se niega: no es una falla del sistema
        # sino una cuenta sin cerrar, así que se muestra en la pantalla con
        # el número adentro (400, no 500).
        return _renderizar_pantalla_tipos_envase_puesto(request, error=str(error), status_code=400)
    except Exception as error_db:
        return _renderizar_pantalla_tipos_envase_puesto(
            request, error=f"No se pudo dar de baja el tipo de envase: {error_db}", status_code=500
        )
    return RedirectResponse(url="/puesto/envases/tipos", status_code=303)


def _renderizar_pantalla_stock_fisico(request: Request, *, error=None, aviso=None, status_code: int = 200):
    try:
        tipos, proveedores = _tipos_envase_y_proveedores()
        # listar_conteos_vacios_de_fecha NO trae stock_sistema, a propósito:
        # esta pantalla la ve el empleado y el número del sistema no puede
        # viajar ni escondido en su HTML (control cruzado).
        contados_hoy = listar_conteos_vacios_de_fecha(_hoy_argentina())
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    return templates.TemplateResponse(
        request,
        "vacios_stock_fisico.html",
        {
            "tipos": tipos,
            "proveedores": proveedores,
            "contados_hoy": contados_hoy,
            "error": error,
            "aviso": aviso,
        },
        status_code=status_code,
    )


@app.get("/puesto/envases/vacios/stock-fisico")
def ver_stock_fisico_vacios(request: Request, aviso: str | None = None):
    return _renderizar_pantalla_stock_fisico(request, aviso=aviso)


@app.post("/puesto/envases/vacios/stock-fisico")
def cargar_stock_fisico_ruta(
    request: Request,
    proveedor_id: str = Form(""),
    tipo_envase_id: str = Form(""),
    cantidad: str = Form(""),
):
    """El empleado carga lo que CONTÓ. Se acepta 0 (contó y no hay ninguno). Si se equivoca, carga de nuevo: vale el último."""
    texto_cantidad = cantidad.strip()
    error = None
    cantidad_valor = None
    if not texto_cantidad:
        error = "La cantidad contada es obligatoria."
    else:
        try:
            cantidad_valor = int(texto_cantidad)
        except ValueError:
            error = "La cantidad contada tiene que ser un número entero."
        else:
            if cantidad_valor < 0:
                error = "La cantidad contada no puede ser negativa."

    tipo_elegido = None
    if not error:
        try:
            tipos, _ = _tipos_envase_y_proveedores()
        except Exception as error_db:
            raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db
        tipo_elegido = next(
            (
                t
                for t in tipos
                if str(t["id"]) == tipo_envase_id.strip() and str(t["proveedor_id"]) == proveedor_id.strip()
            ),
            None,
        )
        if tipo_elegido is None:
            error = "Elegí un proveedor y un tipo de envase válidos."

    if error:
        return _renderizar_pantalla_stock_fisico(request, error=error, status_code=400)

    try:
        crear_conteo_vacios(tipo_elegido["proveedor_id"], tipo_elegido["id"], cantidad_valor)
    except Exception as error_db:
        return _renderizar_pantalla_stock_fisico(
            request, error=f"No se pudo guardar el conteo: {error_db}", status_code=500
        )

    # El aviso repite SOLO lo contado — jamás el stock del sistema.
    aviso = f"Conteo guardado: {cantidad_valor} × {tipo_elegido['nombre']} de {tipo_elegido['proveedor_nombre']}."
    return RedirectResponse(url=f"/puesto/envases/vacios/stock-fisico?{urlencode({'aviso': aviso})}", status_code=303)


def _sin_absorber(diferencia: int, ajustes_posteriores: int) -> int:
    """De la diferencia que encontró el conteo, cuánto queda sin explicar hoy.

    Un ajuste posterior al conteo ABSORBE la diferencia, pero solo hasta
    donde llega y solo si va en la dirección de cerrarla. Restar los ajustes
    a secas estaba mal de dos maneras:

    - Con un conteo que COINCIDIÓ (diferencia cero), cualquier ajuste
      posterior por otro motivo aparecía como "queda sin explicar" por el
      monto del ajuste con el signo cambiado. Eso es lo que se vio el 28/08:
      657/-657, 9/-9, 257/-257. Peor todavía, la tarjeta ofrecía "Ajustar a
      lo contado", y apretarlo habría borrado los cajones que de verdad
      habían aparecido — y después se habría puesto en verde, tapando el
      daño.
    - Un ajuste en la dirección CONTRARIA a la diferencia agrandaba el
      número en vez de dejarlo igual.

    El conteo no encontró nada = no hay nada que explicar, sin importar qué
    haya pasado después. Y lo que absorbe nunca puede pasarse de largo: como
    mucho cierra la diferencia, nunca la da vuelta.
    """
    if diferencia > 0:
        absorbido = min(max(ajustes_posteriores, 0), diferencia)
    elif diferencia < 0:
        absorbido = max(min(ajustes_posteriores, 0), diferencia)
    else:
        absorbido = 0
    return diferencia - absorbido


@app.get("/puesto/envases/cotejo")
def ver_cotejo_vacios(request: Request):
    """Cotejo (cajera): el último conteo físico por proveedor+tipo contra la foto del stock del sistema de ese instante."""
    if not _acceso_control_valido(request):
        return _pantalla_clave_control(request)
    try:
        conteos = listar_ultimos_conteos_vacios()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    filas = []
    for conteo in conteos:
        cerrado = not (conteo["proveedor_activo"] and conteo["tipo_activo"])
        fila = dict(
            conteo,
            # El hecho histórico: qué se vio el día del conteo. No cambia nunca.
            diferencia=conteo["cantidad"] - conteo["stock_sistema"],
            # Lo que queda SIN ABSORBER de esa diferencia, calculado en
            # _sin_absorber: no alcanza con restar los ajustes posteriores.
            pendiente=_sin_absorber(
                conteo["cantidad"] - conteo["stock_sistema"], conteo["ajustes_posteriores"]
            ),
            cerrado=cerrado,
        )

        if cerrado and conteo["stock_actual"] == 0:
            # Cuenta cerrada: el par ya no se puede mover y no quedó nada
            # adentro. La diferencia vieja no es algo que nadie pueda ni deba
            # resolver, así que va al final y en gris, sin botón — pero NO se
            # esconde: si desapareciera, no habría forma de ver que existió
            # ni de notar que se cerró con una diferencia sin explicar.
            fila["estado"] = "cerrado"
        elif cerrado:
            # Dado de baja PERO con saldo: el estado a medio camino que la
            # validación de la baja ya no deja crear. Los que quedaron de
            # antes se muestran en rojo, porque lo único que hay que hacer
            # con ellos es cerrarlos.
            fila["estado"] = "de_baja_con_saldo"
            fila["query_cierre"] = urlencode(
                {
                    "proveedor_id": conteo["proveedor_id"],
                    "tipo_envase_id": conteo["tipo_envase_id"],
                    "contado": 0,
                    "cierre": "1",
                }
            )
        elif fila["pendiente"] != 0:
            fila["estado"] = "pendiente"
            # Botón directo a la pantalla de ajuste, precargada con este
            # conteo (la cantidad final se calcula ahí contra el stock
            # ACTUAL, no contra esta foto — ver ver_ajustar_stock_vacios).
            fila["query_ajuste"] = urlencode(
                {
                    "proveedor_id": conteo["proveedor_id"],
                    "tipo_envase_id": conteo["tipo_envase_id"],
                    "contado": conteo["cantidad"],
                    "stock_conteo": conteo["stock_sistema"],
                    "fecha_conteo": conteo["creado_en"].date().isoformat(),
                }
            )
        else:
            fila["estado"] = "al_dia"
        filas.append(fila)

    # Las cerradas al final: lo que hay para hacer va arriba de todo.
    filas.sort(key=lambda f: f["estado"] == "cerrado")
    return templates.TemplateResponse(request, "vacios_cotejo.html", {"filas": filas})


def _renderizar_pantalla_pendientes_pago(request: Request, *, error=None, status_code: int = 200):
    try:
        pendientes = listar_senas_pendientes()
        resueltas = listar_senas_resueltas()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    return templates.TemplateResponse(
        request,
        "vacios_pendientes.html",
        {"pendientes": pendientes, "resueltas": resueltas, "error": error},
        status_code=status_code,
    )


@app.get("/puesto/envases/pendientes")
def ver_pendientes_pago_vacios(request: Request):
    """Señas pendientes de resolver (cajera): pagar, cerrar con vale o anular, con el historial plegado."""
    return _renderizar_pantalla_pendientes_pago(request)


def _cerrar_sena_y_redirigir(request: Request, movimiento_id: int, cierre: str):
    """Los tres cierres comparten el mismo camino: cerrar_sena registra cuál fue y cuándo."""
    try:
        cerrar_sena(movimiento_id, cierre)
    except Exception as error_db:
        return _renderizar_pantalla_pendientes_pago(
            request, error=f"No se pudo cerrar la seña: {error_db}", status_code=500
        )
    return RedirectResponse(url="/puesto/envases/pendientes", status_code=303)


@app.post("/puesto/envases/pendientes/{movimiento_id}/pagar")
def pagar_sena_ruta(request: Request, movimiento_id: int):
    return _cerrar_sena_y_redirigir(request, movimiento_id, "pagada")


@app.post("/puesto/envases/pendientes/{movimiento_id}/vale")
def vale_sena_ruta(request: Request, movimiento_id: int):
    """El pendiente se cierra con un vale. Por ahora es solo el dato — sin numeración, cobro ni vencimiento."""
    return _cerrar_sena_y_redirigir(request, movimiento_id, "vale")


@app.post("/puesto/envases/pendientes/{movimiento_id}/anular-sena")
def anular_sena_ruta(request: Request, movimiento_id: int):
    """Anula LA SEÑA (no se paga, decidido) — no toca el movimiento ni el stock."""
    return _cerrar_sena_y_redirigir(request, movimiento_id, "anulada")


def _rango_fechas_movimientos(fecha_desde: str | None, fecha_hasta: str | None):
    """Rango de la pantalla Movimientos: lo pedido, o los últimos 7 días. Fechas mal escritas caen al default."""
    hoy = _hoy_argentina()
    try:
        desde = date.fromisoformat(fecha_desde) if fecha_desde else hoy - timedelta(days=7)
    except ValueError:
        desde = hoy - timedelta(days=7)
    try:
        hasta = date.fromisoformat(fecha_hasta) if fecha_hasta else hoy
    except ValueError:
        hasta = hoy
    return desde, hasta


@app.get("/puesto/envases/movimientos")
def ver_movimientos_vacios(request: Request, fecha_desde: str | None = None, fecha_hasta: str | None = None):
    """Movimientos de cualquier fecha (cajera), para corregir errores viejos: anular deja registro, nunca borra.

    El empleado solo puede anular lo de HOY desde sus pantallas; acá la
    cajera llega a cualquier fecha. Corregir = anular el movimiento
    equivocado y cargarlo de nuevo bien desde Recibir/Devolver.
    """
    if not _acceso_control_valido(request):
        return _pantalla_clave_control(request)
    desde, hasta = _rango_fechas_movimientos(fecha_desde, fecha_hasta)
    try:
        recibidos = listar_vacios_recibidos_por_rango(desde, hasta)
        devueltos = listar_vacios_devueltos_por_rango(desde, hasta)
        ajustes = listar_ajustes_vacios_por_rango(desde, hasta)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    return templates.TemplateResponse(
        request,
        "vacios_movimientos.html",
        {
            "recibidos": recibidos,
            "devueltos": devueltos,
            "ajustes": ajustes,
            "fecha_desde": desde.isoformat(),
            "fecha_hasta": hasta.isoformat(),
        },
    )


@app.get("/puesto/envases/movimientos/exportar-pdf")
def exportar_movimientos_vacios_pdf(request: Request, fecha_desde: str = "", fecha_hasta: str = ""):
    """Genera los Movimientos de Vacíos (mismo rango que la pantalla) en PDF — no se guarda en ningún lado."""
    if not _acceso_control_valido(request):
        return RedirectResponse(url="/puesto/envases/movimientos", status_code=303)
    desde, hasta = _rango_fechas_movimientos(fecha_desde, fecha_hasta)
    try:
        recibidos = listar_vacios_recibidos_por_rango(desde, hasta)
        devueltos = listar_vacios_devueltos_por_rango(desde, hasta)
        ajustes = listar_ajustes_vacios_por_rango(desde, hasta)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    pdf_bytes = generar_pdf_movimientos_vacios(desde, hasta, devueltos, recibidos, ajustes)
    nombre_archivo = f"Movimientos_Vacios_{desde.isoformat()}_a_{hasta.isoformat()}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'},
    )


@app.get("/puesto/envases/movimientos/exportar-excel")
def exportar_movimientos_vacios_excel(request: Request, fecha_desde: str = "", fecha_hasta: str = ""):
    """Genera los Movimientos de Vacíos (mismo rango que la pantalla) en Excel — no se guarda en ningún lado."""
    if not _acceso_control_valido(request):
        return RedirectResponse(url="/puesto/envases/movimientos", status_code=303)
    desde, hasta = _rango_fechas_movimientos(fecha_desde, fecha_hasta)
    try:
        recibidos = listar_vacios_recibidos_por_rango(desde, hasta)
        devueltos = listar_vacios_devueltos_por_rango(desde, hasta)
        ajustes = listar_ajustes_vacios_por_rango(desde, hasta)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    excel_bytes = generar_excel_movimientos_vacios(desde, hasta, devueltos, recibidos, ajustes)
    nombre_archivo = f"Movimientos_Vacios_{desde.isoformat()}_a_{hasta.isoformat()}.xlsx"
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'},
    )


def _url_movimientos(fecha_desde: str, fecha_hasta: str) -> str:
    return f"/puesto/envases/movimientos?{urlencode({'fecha_desde': fecha_desde, 'fecha_hasta': fecha_hasta})}"


@app.post("/puesto/envases/movimientos/recibidos/{movimiento_id}/anular")
def anular_recibido_desde_movimientos_ruta(
    request: Request, movimiento_id: int, fecha_desde: str = Form(""), fecha_hasta: str = Form("")
):
    if not _acceso_control_valido(request):
        return RedirectResponse(url="/puesto/envases/movimientos", status_code=303)
    try:
        anular_vacio_recibido(movimiento_id)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"No se pudo anular el movimiento: {error_db}") from error_db
    return RedirectResponse(url=_url_movimientos(fecha_desde, fecha_hasta), status_code=303)


@app.post("/puesto/envases/movimientos/devueltos/{movimiento_id}/anular")
def anular_devuelto_desde_movimientos_ruta(
    request: Request, movimiento_id: int, fecha_desde: str = Form(""), fecha_hasta: str = Form("")
):
    if not _acceso_control_valido(request):
        return RedirectResponse(url="/puesto/envases/movimientos", status_code=303)
    try:
        anular_vacio_devuelto(movimiento_id)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"No se pudo anular el movimiento: {error_db}") from error_db
    return RedirectResponse(url=_url_movimientos(fecha_desde, fecha_hasta), status_code=303)


@app.post("/puesto/envases/movimientos/ajustes/{ajuste_id}/anular")
def anular_ajuste_desde_movimientos_ruta(
    request: Request, ajuste_id: int, fecha_desde: str = Form(""), fecha_hasta: str = Form("")
):
    """Anula un ajuste con el mismo mecanismo que los demás movimientos: registro visible, nunca DELETE."""
    if not _acceso_control_valido(request):
        return RedirectResponse(url="/puesto/envases/movimientos", status_code=303)
    try:
        anular_ajuste_vacios(ajuste_id)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"No se pudo anular el ajuste: {error_db}") from error_db
    return RedirectResponse(url=_url_movimientos(fecha_desde, fecha_hasta), status_code=303)


def _renderizar_pantalla_ajustar_vacios(
    request: Request, *, precarga=None, error=None, aviso=None, status_code: int = 200
):
    try:
        tipos, proveedores = _tipos_envase_y_proveedores()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    return templates.TemplateResponse(
        request,
        "vacios_ajustar.html",
        {
            "tipos": tipos,
            "proveedores": proveedores,
            "precarga": precarga or {},
            "error": error,
            "aviso": aviso,
        },
        status_code=status_code,
    )


@app.get("/puesto/envases/ajustar")
def ver_ajustar_stock_vacios(
    request: Request,
    aviso: str | None = None,
    proveedor_id: str | None = None,
    tipo_envase_id: str | None = None,
    contado: str | None = None,
    stock_conteo: str | None = None,
    fecha_conteo: str | None = None,
    cierre: str | None = None,
):
    """Ajuste de stock (cajera). Sin precarga: pantalla en blanco; con precarga (viene del Cotejo): calcula el ajuste.

    La cantidad precargada es contado − stock ACTUAL (no la diferencia
    congelada del cotejo): "ajustar a lo contado" tiene que dejar el
    stock en lo contado, aunque hayan entrado movimientos después del
    conteo. Si el stock cambió desde el conteo, la pantalla lo dice con
    todos los números — el ajuste sugerido puede no coincidir con la
    diferencia que se vio en el Cotejo, y eso hay que entenderlo ANTES
    de guardar, no descubrirlo después.
    """
    if not _acceso_control_valido(request):
        return _pantalla_clave_control(request)
    precarga = {}
    if proveedor_id and tipo_envase_id and contado is not None and contado.strip().lstrip("-").isdigit():
        try:
            contado_valor = int(contado)
            stock_actual = stock_vacios_de_tipo(int(proveedor_id), int(tipo_envase_id))
        except Exception as error_db:
            raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

        # cierre=1 viene del Cotejo, de un par dado de baja al que le quedó
        # saldo: ahí el ajuste no es "dejarlo en lo contado" sino cerrar la
        # cuenta en cero. El motivo arranca escrito pero se puede cambiar —
        # el sistema no inventa por qué se perdieron los cajones.
        cerrando = cierre == "1"
        precarga = {
            "proveedor_id": proveedor_id,
            "tipo_envase_id": tipo_envase_id,
            "cantidad": contado_valor - stock_actual,
            "motivo": (
                "Cierre de cuenta: el proveedor o el tipo se dio de baja"
                if cerrando
                else f"Ajuste a lo contado: conteo del {fecha_conteo or '?'} ({contado_valor} contados)"
            ),
        }
        # El aviso de "el stock se movió desde el conteo": solo si la foto
        # del conteo (stock_conteo) difiere del stock actual.
        if (
            not cerrando
            and stock_conteo is not None
            and stock_conteo.strip().lstrip("-").isdigit()
            and int(stock_conteo) != stock_actual
        ):
            precarga["aviso_conteo"] = (
                f"Ojo: el conteo fue del {fecha_conteo or '?'} con {contado_valor} contados y el sistema decía "
                f"{int(stock_conteo)}. Desde entonces hubo movimientos: el stock actual es {stock_actual}, "
                f"así que el ajuste sugerido para dejarlo en lo contado es "
                f"{contado_valor - stock_actual:+d} (no la diferencia que viste en el Cotejo)."
            )

    return _renderizar_pantalla_ajustar_vacios(request, precarga=precarga, aviso=aviso)


@app.post("/puesto/envases/ajustar")
def ajustar_stock_vacios_ruta(
    request: Request,
    proveedor_id: str = Form(""),
    tipo_envase_id: str = Form(""),
    cantidad: str = Form(""),
    motivo: str = Form(""),
):
    """Guarda un ajuste: cantidad con signo (nunca 0) y motivo OBLIGATORIO — sin motivo no se guarda."""
    if not _acceso_control_valido(request):
        return RedirectResponse(url="/puesto/envases/ajustar", status_code=303)
    motivo_limpio = re.sub(r"\s+", " ", motivo).strip()
    error = None
    cantidad_valor = None

    texto_cantidad = cantidad.strip()
    if not texto_cantidad:
        error = "La cantidad del ajuste es obligatoria."
    else:
        try:
            cantidad_valor = int(texto_cantidad)
        except ValueError:
            error = "La cantidad del ajuste tiene que ser un número entero (positivo o negativo)."
        else:
            if cantidad_valor == 0:
                error = "Un ajuste de 0 no ajusta nada."

    if not error and not motivo_limpio:
        error = "El motivo es obligatorio: sin motivo no se guarda el ajuste."

    tipo_elegido = None
    if not error:
        try:
            tipos, _ = _tipos_envase_y_proveedores()
        except Exception as error_db:
            raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db
        tipo_elegido = next(
            (
                t
                for t in tipos
                if str(t["id"]) == tipo_envase_id.strip() and str(t["proveedor_id"]) == proveedor_id.strip()
            ),
            None,
        )
        if tipo_elegido is None:
            error = "Elegí un proveedor y un tipo de envase válidos."

    if error:
        return _renderizar_pantalla_ajustar_vacios(request, error=error, status_code=400)

    try:
        stock_nuevo = crear_ajuste_vacios(
            tipo_elegido["proveedor_id"], tipo_elegido["id"], cantidad_valor, motivo_limpio
        )
    except Exception as error_db:
        return _renderizar_pantalla_ajustar_vacios(
            request, error=f"No se pudo guardar el ajuste: {error_db}", status_code=500
        )

    aviso = (
        f"Ajuste guardado: {cantidad_valor:+d} × {tipo_elegido['nombre']} de {tipo_elegido['proveedor_nombre']}. "
        f"El stock quedó en {stock_nuevo}."
    )
    return RedirectResponse(url=f"/puesto/envases/ajustar?{urlencode({'aviso': aviso})}", status_code=303)


def _renderizar_pantalla_clientes_puesto(request: Request, *, error=None, aviso=None, status_code: int = 200):
    try:
        clientes = listar_clientes_puesto()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    return templates.TemplateResponse(
        request,
        "vacios_clientes.html",
        {"clientes": clientes, "error": error, "aviso": aviso},
        status_code=status_code,
    )


@app.get("/puesto/envases/clientes")
def ver_clientes_puesto(request: Request, aviso: str | None = None):
    """Clientes del puesto (cajera): lista, alta a mano y baja lógica.

    El alta normal la hace el empleado tipeando el nombre en Recibir; acá
    la cajera puede además dar de baja a uno para que deje de sugerirse
    (si vuelve a aparecer, tipear su nombre lo reactiva solo).

    La pantalla pide clave, pero el alta automática al tipear en Recibir
    NO: esa es la operación del día a día del empleado.
    """
    if not _acceso_control_valido(request):
        return _pantalla_clave_control(request)
    return _renderizar_pantalla_clientes_puesto(request, aviso=aviso)


@app.post("/puesto/envases/clientes/nuevo")
def crear_cliente_puesto_ruta(request: Request, nombre: str = Form("")):
    if not _acceso_control_valido(request):
        return RedirectResponse(url="/puesto/envases/clientes", status_code=303)
    nombre_limpio = re.sub(r"\s+", " ", nombre).strip()
    nombre_normalizado = normalizar_texto(nombre_limpio)
    if not nombre_normalizado:
        return _renderizar_pantalla_clientes_puesto(
            request, error="El nombre del cliente es obligatorio.", status_code=400
        )

    try:
        obtener_o_crear_cliente_puesto(nombre_limpio, nombre_normalizado)
    except Exception as error_db:
        return _renderizar_pantalla_clientes_puesto(
            request, error=f"No se pudo crear el cliente: {error_db}", status_code=500
        )

    parametros = urlencode({"aviso": f"Cliente '{nombre_limpio}' cargado."})
    return RedirectResponse(url=f"/puesto/envases/clientes?{parametros}", status_code=303)


@app.post("/puesto/envases/clientes/{cliente_id}/baja")
def dar_de_baja_cliente_puesto_ruta(request: Request, cliente_id: int):
    if not _acceso_control_valido(request):
        return RedirectResponse(url="/puesto/envases/clientes", status_code=303)
    try:
        desactivar_cliente_puesto(cliente_id)
    except Exception as error_db:
        return _renderizar_pantalla_clientes_puesto(
            request, error=f"No se pudo dar de baja el cliente: {error_db}", status_code=500
        )
    return RedirectResponse(url="/puesto/envases/clientes", status_code=303)


def _renderizar_pantalla_proveedores_puesto(request: Request, *, error=None, aviso=None, status_code: int = 200):
    try:
        proveedores = listar_proveedores_puesto()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    return templates.TemplateResponse(
        request,
        "vacios_proveedores.html",
        {"proveedores": proveedores, "error": error, "aviso": aviso},
        status_code=status_code,
    )


@app.get("/puesto/envases/proveedores")
def ver_proveedores_puesto(request: Request, aviso: str | None = None):
    """Proveedores del puesto (cajera): alta, baja lógica y listado.

    El empleado del fondo NO crea proveedores: si llega un cajón de uno
    que no está, se acerca a la cajera y ella lo carga acá — recién ahí
    le aparece en las listas cerradas de Vacíos (después de cargarle al
    menos un tipo de envase).
    """
    if not _acceso_control_valido(request):
        return _pantalla_clave_control(request)
    return _renderizar_pantalla_proveedores_puesto(request, aviso=aviso)


@app.post("/puesto/envases/proveedores/nuevo")
def crear_proveedor_puesto_ruta(request: Request, nombre: str = Form("")):
    if not _acceso_control_valido(request):
        return RedirectResponse(url="/puesto/envases/proveedores", status_code=303)
    nombre_limpio = re.sub(r"\s+", " ", nombre).strip()
    nombre_normalizado = normalizar_texto(nombre_limpio)
    if not nombre_normalizado:
        return _renderizar_pantalla_proveedores_puesto(
            request, error="El nombre del proveedor es obligatorio.", status_code=400
        )

    try:
        obtener_o_crear_proveedor_puesto(nombre_limpio, nombre_normalizado)
    except Exception as error_db:
        return _renderizar_pantalla_proveedores_puesto(
            request, error=f"No se pudo crear el proveedor: {error_db}", status_code=500
        )

    parametros = urlencode(
        {"aviso": f"Proveedor '{nombre_limpio}' cargado. Para que aparezca en Vacíos, cargale un tipo de envase."}
    )
    return RedirectResponse(url=f"/puesto/envases/proveedores?{parametros}", status_code=303)


@app.post("/puesto/envases/proveedores/{proveedor_id}/renombrar")
def renombrar_proveedor_puesto_ruta(request: Request, proveedor_id: int, nombre: str = Form("")):
    """Corrige el nombre de un proveedor del puesto. Sin historial: es un tipeo, no otro proveedor."""
    if not _acceso_control_valido(request):
        return RedirectResponse(url="/puesto/envases/proveedores", status_code=303)
    nombre_limpio = re.sub(r"\s+", " ", nombre).strip()
    nombre_normalizado = normalizar_texto(nombre_limpio)
    if not nombre_normalizado:
        return _renderizar_pantalla_proveedores_puesto(
            request, error="El nombre del proveedor es obligatorio.", status_code=400
        )
    try:
        renombrar_proveedor_puesto(proveedor_id, nombre_limpio, nombre_normalizado)
    except ValueError as error:
        return _renderizar_pantalla_proveedores_puesto(request, error=str(error), status_code=400)
    except Exception as error_db:
        return _renderizar_pantalla_proveedores_puesto(
            request, error=f"No se pudo renombrar el proveedor: {error_db}", status_code=500
        )
    parametros = urlencode({"aviso": f"Proveedor renombrado a '{nombre_limpio}'."})
    return RedirectResponse(url=f"/puesto/envases/proveedores?{parametros}", status_code=303)


@app.post("/puesto/envases/proveedores/{proveedor_id}/baja")
def dar_de_baja_proveedor_puesto_ruta(request: Request, proveedor_id: int):
    if not _acceso_control_valido(request):
        return RedirectResponse(url="/puesto/envases/proveedores", status_code=303)
    try:
        desactivar_proveedor_puesto(proveedor_id)
    except ValueError as error:
        # Igual que con los tipos: una cuenta abierta no es un error del
        # sistema, es algo para cerrar. Se dice con los números.
        return _renderizar_pantalla_proveedores_puesto(request, error=str(error), status_code=400)
    except Exception as error_db:
        return _renderizar_pantalla_proveedores_puesto(
            request, error=f"No se pudo dar de baja el proveedor: {error_db}", status_code=500
        )
    return RedirectResponse(url="/puesto/envases/proveedores", status_code=303)


# ----------------------------------------------------------------------------
# Pedidos de clientes (etapa 1): el mail diario de Día, pegado como texto.
# Vive en DEPÓSITO (el que arma el pedido no entra a Comercial, donde están
# los precios). Invariante duro: nada del mail se pierde — lo que no se
# entiende se guarda como texto, jamás se descarta en silencio.
# ----------------------------------------------------------------------------


def _alias_de_fichas(fichas: list[dict]) -> tuple[dict, dict]:
    """Los alias del cliente, normalizados, para el matcheo determinista: codigo -> ficha_id y nombre -> ficha_id.

    Apuntan a la FICHA, no al artículo: el código con el que pide el
    cliente identifica CON QUÉ FICHA se le vende (precio, kilaje, envase
    y el nombre que ve el que arma), y el artículo sale después de la
    propia ficha. Con dos fichas del mismo artículo —"Banana Bolivia" y
    "Banana Ecuador" para Día— cada código cae en la suya.
    """
    por_codigo = {
        normalizar_texto(f["codigo_cliente"]): f["id"] for f in fichas if f.get("codigo_cliente")
    }
    por_nombre = {
        normalizar_texto(f["nombre_cliente"]): f["id"] for f in fichas if f.get("nombre_cliente")
    }
    return por_codigo, por_nombre


def _elegir_bloque_pedido(bloques: list[dict], alias_por_codigo: dict) -> dict | None:
    """Qué bloque del mail es de ESTA empresa.

    Con un solo bloque, ese. Con varios: primero el que nombra a la
    empresa en su encabezado; si ninguno la nombra, el desempate es
    determinista — el bloque con más códigos que matchean las fichas de
    esta empresa (cada base tiene sus alias). Nunca se adivina por
    posición.
    """
    bloques = [b for b in bloques if b.get("renglones")]
    if not bloques:
        return None
    if len(bloques) == 1:
        return bloques[0]

    empresa_normalizada = normalizar_texto(NOMBRE_EMPRESA)
    for bloque in bloques:
        if empresa_normalizada and empresa_normalizada in normalizar_texto(bloque.get("empresa") or ""):
            return bloque

    def _matches(bloque):
        return sum(
            1 for r in bloque.get("renglones") or []
            if normalizar_texto(r.get("codigo") or "") in alias_por_codigo
        )

    return max(bloques, key=_matches)


def _armar_renglones_pedido_desde_bloque(bloque: dict, fichas: list[dict], alias_por_codigo: dict, alias_por_nombre: dict) -> list[dict]:
    """Los renglones del bloque con su matcheo: código exacto -> nombre exacto -> sugerencia difusa (marcada).

    El match cae en una FICHA (con qué se le vende a este cliente) y el
    artículo sale de ella. Los tres caminos —código exacto, nombre exacto y
    sugerencia difusa— devuelven ficha: la difusa compara contra el nombre
    que el CLIENTE usa (nombre_cliente, cayendo al del catálogo), que es lo
    único que distingue dos fichas del mismo artículo.

    Cada renglón conserva SIEMPRE el texto crudo del mail y las cantidades
    por sucursal tal como vinieron. Sin match, ficha y artículo en None:
    en la revisión va arriba, marcado, para asignar a mano.
    """
    # Los candidatos del matcheo difuso son las FICHAS, con el nombre que
    # el cliente usa: así la sugerencia cae directo en la ficha correcta y
    # no hay que traducir desde el artículo (que con dos fichas del mismo
    # artículo no tendría cómo elegir cuál).
    candidatos = [{"id": f["id"], "nombre": _nombre_de_ficha(f)} for f in fichas]
    conversiones = [
        {"nombre_cliente": f["nombre_cliente"], "articulo_id": f["id"]} for f in fichas if f.get("nombre_cliente")
    ]
    ficha_por_id = {f["id"]: f for f in fichas}

    renglones = []
    for renglon in bloque.get("renglones") or []:
        codigo = (renglon.get("codigo") or "").strip()
        descripcion = (renglon.get("descripcion") or "").strip()

        ficha_id = alias_por_codigo.get(normalizar_texto(codigo)) if codigo else None
        match_por = "codigo" if ficha_id is not None else None
        if ficha_id is None and descripcion:
            ficha_id = alias_por_nombre.get(normalizar_texto(descripcion))
            match_por = "nombre" if ficha_id is not None else None
        if ficha_id is None and descripcion:
            ficha_id = adivinar_articulo(descripcion, {}, candidatos, conversiones)
            match_por = "sugerencia" if ficha_id is not None else None

        ficha = ficha_por_id.get(ficha_id) if ficha_id is not None else None
        articulo_id = ficha["articulo_id"] if ficha else None

        cantidades = renglon.get("cantidades") or {}
        renglones.append(
            {
                "texto_codigo": codigo or None,
                "texto_descripcion": descripcion or None,
                "cantidades": {s: c for s, c in cantidades.items() if c is not None},
                "articulo_id": articulo_id,
                "ficha_id": ficha_id,
                "match_por": match_por,
                "advertencia": ficha_id is None or match_por == "sugerencia" or renglon.get("confianza") == "baja",
            }
        )
    # Los sin match / dudosos arriba: son los que hay que mirar sí o sí.
    renglones.sort(key=lambda r: not r["advertencia"])
    return renglones


def _numero_pedido_o_none(valor) -> float | None:
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def _sucursales_desde_bloque(bloque: dict, renglones: list[dict]) -> list[dict]:
    """Las sucursales del bloque leído, con su OC y su total declarado.

    Las que aparecen en cantidades pero no vinieron declaradas arriba se
    agregan igual (sin OC ni total) — nada se pierde. Mismo armado para la
    revisión a mano y para el auto-confirmar.
    """
    sucursales = [
        {
            "sucursal": (s.get("sucursal") or "").strip(),
            "orden_compra": (str(s.get("orden_compra")).strip() if s.get("orden_compra") is not None else None),
            "total_bultos_declarado": _numero_pedido_o_none(s.get("total_bultos")),
        }
        for s in bloque.get("sucursales") or []
        if (s.get("sucursal") or "").strip()
    ]
    declaradas = {s["sucursal"] for s in sucursales}
    for renglon in renglones:
        for nombre_sucursal in renglon["cantidades"]:
            if nombre_sucursal not in declaradas:
                sucursales.append({"sucursal": nombre_sucursal, "orden_compra": None, "total_bultos_declarado": None})
                declaradas.add(nombre_sucursal)
    return sucursales


def _fecha_pedido_o_hoy(fecha_texto: str | None):
    hoy = _hoy_argentina()
    if not fecha_texto:
        return hoy
    try:
        return date.fromisoformat(fecha_texto)
    except ValueError:
        return hoy


def _motivos_de_atencion(pedido: dict) -> list[str]:
    """Por qué este pedido no está listo, dicho corto y en orden de resolución.

    Los TRES casos que pintan de amarillo, y ninguno más: armado corto,
    renglones sin armar en un pedido ya terminado, y renglones sin
    identificar. Cada uno tiene su alerta en Auditoría —los dos primeros en
    `pedidos_incompletos`, el tercero en `pedidos_sin_identificar`—, así que
    el color de la tarjeta y el banner no pueden decir cosas distintas.

    El kilaje fuera de tolerancia NO entra a propósito: es una diferencia
    contra la ficha, no contra lo que pidió el cliente, y mezclarlo diluye lo
    que el color significa.
    """
    motivos = []
    cortos = pedido.get("renglones_cortos", 0)
    if cortos:
        motivos.append(f"{cortos} armado{'s' if cortos != 1 else ''} de menos")
    sin_armar = pedido["renglones_totales"] - pedido["renglones_armados"]
    if pedido.get("armado_cerrado_el") is not None and sin_armar > 0:
        motivos.append(f"{sin_armar} sin armar")
    if pedido["sin_identificar"]:
        motivos.append(f"{pedido['sin_identificar']} sin identificar")
    return motivos


def _listado_de_pedidos(cliente_id: int, hoy) -> list[dict]:
    """Los pedidos del listado (últimos 7 días + todos los futuros), con HOY primero y su estado a la vista.

    Orden pensado para el que arma: hoy, después los próximos (el del
    sábado se puede ir armando el viernes), y al final los pasados del más
    reciente al más viejo.
    """
    pedidos = listar_pedidos_vigentes_con_armado(cliente_id, hoy - timedelta(days=DIAS_PASADOS_LISTADO_PEDIDOS))

    def _orden(pedido):
        if pedido["fecha_operacion"] == hoy:
            return (0, 0)
        if pedido["fecha_operacion"] > hoy:
            return (1, pedido["fecha_operacion"].toordinal())
        return (2, -pedido["fecha_operacion"].toordinal())

    listado = []
    for pedido in sorted(pedidos, key=_orden):
        listado.append(
            {
                "fecha": pedido["fecha_operacion"].isoformat(),
                "fecha_mostrar": pedido["fecha_operacion"].strftime("%d/%m/%Y"),
                "es_hoy": pedido["fecha_operacion"] == hoy,
                "es_futuro": pedido["fecha_operacion"] > hoy,
                "renglones_totales": pedido["renglones_totales"],
                "renglones_armados": pedido["renglones_armados"],
                "sin_identificar": pedido["sin_identificar"],
                # Cierre explícito del armado ("Terminar pedido").
                "cerrado": pedido.get("armado_cerrado_el") is not None,
                "renglones_cortos": pedido.get("renglones_cortos", 0),
                # Completo = todos los identificados armados, ninguno sin
                # identificar y NINGUNO ARMADO CORTO: se marca, no desaparece.
                #
                # Lo de los cortos entró el 02/09 y es el fondo del asunto: el
                # color tiene que reflejar LO QUE QUEDA POR HACER, no lo que se
                # tocó (mismo criterio del Cotejo). Un pedido con renglones
                # incompletos no está terminado, y mostrarlo en verde con un
                # tilde le dice al que mira que no hay nada que hacer.
                "completo": (
                    pedido["renglones_totales"] > 0
                    and pedido["renglones_armados"] == pedido["renglones_totales"]
                    and pedido["sin_identificar"] == 0
                    and pedido.get("renglones_cortos", 0) == 0
                ),
                # Lo que le falta, en el orden en que se resuelve. Va como
                # texto y no como booleano: un amarillo que no dice por qué
                # obliga a entrar a los tres pedidos para encontrar cuál era.
                "motivos": _motivos_de_atencion(pedido),
            }
        )
    return listado


def _dias_esperados_como_numeros(dias_esperados: str | None) -> set[int]:
    """El texto guardado ('1,3,5' — 1=lunes ... 7=domingo) como conjunto de números. Basura adentro se ignora."""
    numeros = set()
    for parte in (dias_esperados or "").split(","):
        parte = parte.strip()
        if parte.isdigit() and 1 <= int(parte) <= 7:
            numeros.add(int(parte))
    return numeros


def _fechas_esperadas_sin_pedido(cliente_id: int, dias_esperados: str | None, ahora) -> dict:
    """Los días ESPERADOS sin pedido del cliente en la última semana, y las marcas "no hubo pedido" vigentes.

    Un día esperado cuenta como faltante si no tiene pedido VIVO ni marca
    de "no hubo pedido". El día de HOY recién cuenta desde las 15:00 (el
    cierre de la ventana de revisión automática): antes de esa hora el
    mail todavía puede llegar, y una alerta que grita antes de tiempo se
    termina ignorando. Si una fecha marcada después recibe un pedido, el
    pedido manda: la marca deja de mostrarse (queda de registro).
    """
    hoy = ahora.date()
    dias = _dias_esperados_como_numeros(dias_esperados)
    desde = hoy - timedelta(days=DIAS_PASADOS_LISTADO_PEDIDOS)

    con_pedido = set(listar_fechas_con_pedido_vigente(cliente_id, desde))
    marcas = listar_dias_sin_pedido(cliente_id, desde)
    fechas_marcadas = {marca["fecha"] for marca in marcas}

    ultima = hoy if ahora.time() >= VENTANA_REVISION_HASTA else hoy - timedelta(days=1)
    faltantes = []
    fecha = desde
    while fecha <= ultima:
        if fecha.isoweekday() in dias and fecha not in con_pedido and fecha not in fechas_marcadas:
            faltantes.append(fecha)
        fecha += timedelta(days=1)

    return {
        "faltantes": faltantes,
        "marcados": [marca for marca in marcas if marca["fecha"] not in con_pedido],
    }


def contar_pedidos_faltantes() -> dict:
    """Cuántos días esperados quedaron sin pedido (todas los clientes con días configurados), para Auditoría."""
    ahora = datetime.now(ARGENTINA)
    casos = 0
    mas_viejo = None
    for condicion in listar_condiciones_pedido():
        faltantes = _fechas_esperadas_sin_pedido(condicion["cliente_id"], condicion["dias_esperados"], ahora)["faltantes"]
        casos += len(faltantes)
        for fecha in faltantes:
            if mas_viejo is None or fecha < mas_viejo:
                mas_viejo = fecha
    return {"casos": casos, "mas_viejo": mas_viejo}


def contar_casillas_sin_revisar(ahora=None) -> dict:
    """Cuántas casillas ACTIVAS llevan el día sin UNA revisión exitosa, para Auditoría.

    A propósito NO alerta al primer fallo: una caída de internet que al
    tick siguiente se recuperó sola no es un problema, y una alerta que
    grita por eso se deja de mirar en una semana. El criterio es "pasó un
    rato largo y nunca pudo": desde UNA HORA antes del cierre de la
    ventana DE CADA casilla (su horario es configurable), si hoy no hubo
    NINGUNA revisión exitosa — porque todos los intentos fallaron o
    porque directamente no corrió ninguno — el problema es real y hay que
    resolverlo antes de que se pase el día. El último error puntual se ve
    igual en la pantalla de la casilla, siempre, aunque después se haya
    recuperado.
    """
    if ahora is None:
        ahora = datetime.now(ARGENTINA)
    casos = 0
    for casilla in listar_casillas_pedidos():
        if not casilla["activa"]:
            continue
        desde, hasta, _ = _horario_revision_de(casilla)
        # El umbral nunca cae antes de la apertura: con una ventana más
        # corta que el margen, se alerta recién desde que la ventana abre.
        umbral = max(
            datetime.combine(ahora.date(), hasta, tzinfo=ARGENTINA) - MARGEN_ALERTA_CASILLA,
            datetime.combine(ahora.date(), desde, tzinfo=ARGENTINA),
        )
        if ahora < umbral:
            continue
        # SOLO las automáticas: el botón manual no cuenta — si contara,
        # un tick muerto sería invisible mientras el dueño toque el botón
        # (el punto ciego del diagnóstico del 25/08).
        revision = casilla["ultima_revision_automatica_el"]
        revisada_hoy = revision is not None and revision.astimezone(ARGENTINA).date() == ahora.date()
        if not revisada_hoy:
            casos += 1
    return {"casos": casos, "mas_viejo": None}


def _sumas_leidas_por_sucursal(renglones: list[dict]) -> dict:
    """El control cruzado: cuántos bultos suman los renglones guardados, por sucursal."""
    sumas: dict = {}
    for renglon in renglones:
        if renglon["sucursal"] is None:
            continue
        sumas[renglon["sucursal"]] = sumas.get(renglon["sucursal"], 0.0) + float(renglon["cantidad"])
    return sumas


def _contexto_revision_pedido(cliente_id, cliente_nombre, fecha_valor, datos, texto_original, fotos_data, mail=None, metodo_lectura=None, aviso_fecha=None):
    """El contexto de la pantalla de revisión a partir de lo que leyó la IA, o None si no encontró renglones.

    Es el mismo camino para el texto pegado, las capturas y el mail
    registrado de la casilla (que entra con ``mail``: la revisión muestra
    de qué mail viene y el guardado lo confirma).
    """
    fichas = listar_fichas_por_cliente(cliente_id)
    pedido_vigente = obtener_pedido_vigente(cliente_id, fecha_valor)

    alias_por_codigo, alias_por_nombre = _alias_de_fichas(fichas)
    bloque = _elegir_bloque_pedido(datos.get("bloques") or [], alias_por_codigo)
    if bloque is None:
        return None

    renglones = _armar_renglones_pedido_desde_bloque(bloque, fichas, alias_por_codigo, alias_por_nombre)
    sucursales = _sucursales_desde_bloque(bloque, renglones)

    return {
        "cliente_id": cliente_id,
        "cliente_nombre": cliente_nombre,
        "fecha": fecha_valor.isoformat(),
        "fecha_mostrar": fecha_valor.strftime("%d/%m/%Y"),
        "empresa_bloque": bloque.get("empresa") or "",
        "sucursales": sucursales,
        "renglones": renglones,
        # El select de la revisión elige FICHA, con el nombre que el cliente
        # usa: "Banana Ecuador" y "Banana Bolivia" son dos opciones, y
        # "Banana" en las dos no dejaría elegir.
        "fichas_cliente": [{"id": f["id"], "nombre": _nombre_de_ficha(f)} for f in fichas],
        "texto_original": texto_original,
        "fotos_data": fotos_data,
        "pedido_vigente": pedido_vigente,
        "mail": mail,
        # Cómo se leyó, SIEMPRE a la vista: "estructura" (las cantidades
        # salen de la tabla, sin IA), "ia" (el parser no pudo: mirar con
        # más atención) o "ia_capturas" (una imagen solo se lee con IA).
        "metodo_lectura": metodo_lectura,
        # Fecha dudosa (el asunto no la trae, o está lejos de la llegada):
        # se avisa, nunca se decide en silencio.
        "aviso_fecha": aviso_fecha,
    }


@app.get("/deposito/pedido")
def ver_pedido_del_dia(request: Request, cliente_id: str | None = None, fecha: str | None = None, aviso: str | None = None):
    """El pedido del día de un cliente, por sucursal con su OC — lo que el depósito arma.

    Control cruzado siempre a la vista: la suma de lo leído por sucursal
    contra el total que declaró el mail. Si no cierran, aviso fuerte — un
    número mal leído por la IA se detecta solo, sin revisar renglón por
    renglón.
    """
    cliente_id_valor = _id_opcional_desde_query(cliente_id)
    fecha_valor = _fecha_pedido_o_hoy(fecha)

    try:
        clientes = listar_clientes()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    contexto = {
        "clientes": clientes,
        "cliente_id": cliente_id_valor,
        "fecha": fecha_valor.isoformat(),
        "fecha_mostrar": fecha_valor.strftime("%d/%m/%Y"),
        "aviso": aviso,
        "pedido": None,
    }
    if cliente_id_valor is None:
        return templates.TemplateResponse(request, "deposito_pedido.html", contexto)

    try:
        # El listado multi-día: si están cargados el de hoy Y el de mañana,
        # se ven los dos — el depósito puede adelantar el del sábado el
        # viernes. Los pasados de la última semana siguen consultables.
        contexto["pedidos_listado"] = _listado_de_pedidos(cliente_id_valor, _hoy_argentina())
        # Los días ESPERADOS sin pedido (si el cliente tiene días fijos
        # configurados): se muestran en el listado con sus dos cierres —
        # cargar el pedido, o marcar que ese día no hubo.
        condiciones = obtener_condiciones_pedido(cliente_id_valor)
        if condiciones is not None and condiciones["dias_esperados"]:
            estado_dias = _fechas_esperadas_sin_pedido(cliente_id_valor, condiciones["dias_esperados"], datetime.now(ARGENTINA))
            contexto["dias_faltantes"] = [
                {"fecha": f.isoformat(), "fecha_mostrar": f.strftime("%d/%m/%Y")} for f in estado_dias["faltantes"]
            ]
            contexto["dias_marcados"] = [
                {"fecha": m["fecha"].isoformat(), "fecha_mostrar": m["fecha"].strftime("%d/%m/%Y"), "motivo": m["motivo"]}
                for m in estado_dias["marcados"]
            ]
        # Los mails de pedido TRABADOS (pendientes o con error de lectura)
        # de este cliente, acá donde se trabaja — no estacionados en
        # Sistema donde nadie los ve. Cada uno con su fecha estimada del
        # asunto y el botón para revisar/reintentar.
        contexto["mails_sin_confirmar"] = []
        for mail_trabado in listar_mails_pedido_sin_procesar_de_cliente(cliente_id_valor):
            llegada = mail_trabado["recibido_el"].astimezone(ARGENTINA).date()
            fecha_estimada = fecha_de_pedido_del_asunto(mail_trabado["asunto"], llegada) or llegada
            mail_trabado["fecha_estimada_mostrar"] = fecha_estimada.strftime("%d/%m/%Y")
            contexto["mails_sin_confirmar"].append(mail_trabado)
        pedido = obtener_pedido_vigente(cliente_id_valor, fecha_valor)
        if pedido is not None:
            sucursales = listar_sucursales_pedido(pedido["id"])
            renglones = listar_renglones_pedido(pedido["id"])
            fotos = listar_fotos_pedido(pedido["id"])
            fichas = listar_fichas_por_cliente(cliente_id_valor)
        else:
            sucursales, renglones, fotos, fichas = [], [], [], []
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    if pedido is None:
        return templates.TemplateResponse(request, "deposito_pedido.html", contexto)

    # Si el pedido lo confirmó solo la revisión automática, la pantalla lo
    # dice: el dueño tiene que saber que ese pedido no lo miró nadie.
    if pedido["origen"] == "mail":
        try:
            mail_del_pedido = obtener_mail_de_pedido(pedido["id"])
        except Exception:
            mail_del_pedido = None
            logger.exception("No se pudo leer el mail del pedido %s para el aviso de auto-confirmado", pedido["id"])
        if mail_del_pedido is not None and mail_del_pedido["motivo"] == "Confirmado automáticamente":
            contexto["confirmado_automaticamente"] = mail_del_pedido

    sumas = _sumas_leidas_por_sucursal(renglones)
    for sucursal in sucursales:
        suma = sumas.get(sucursal["sucursal"], 0.0)
        sucursal["suma_leida"] = suma
        # El armado real: lo que efectivamente se armó (con las cantidades
        # parciales), para el que factura o atiende el reclamo de Día.
        propios = [r for r in renglones if r["sucursal"] == sucursal["sucursal"] and r["articulo_id"] is not None]
        armados = [r for r in propios if r["armado_el"] is not None]
        sucursal["renglones_totales"] = len(propios)
        sucursal["renglones_armados"] = len(armados)
        sucursal["armado_real"] = sum(
            float(r["cantidad_armada"]) if r["cantidad_armada"] is not None else float(r["cantidad"]) for r in armados
        )
        # El "<" y no "<>": armar de MÁS no es incompleto. La alerta de
        # Auditoría ya lo tenía bien y la pantalla no — la misma regla escrita
        # dos veces, y la copia que quedó vieja es la que se mira todos los
        # días. Si el color depende de esto, un pedido donde sobró mercadería
        # saldría amarillo diciendo que falta.
        sucursal["incompletos"] = sum(
            1 for r in armados if r["cantidad_armada"] is not None and float(r["cantidad_armada"]) < float(r["cantidad"])
        )

    sin_identificar = [r for r in renglones if r["articulo_id"] is None]
    renglones_por_sucursal: dict = {}
    for renglon in renglones:
        if renglon["articulo_id"] is None:
            continue
        renglones_por_sucursal.setdefault(renglon["sucursal"], []).append(renglon)

    contexto.update(
        {
            "pedido": pedido,
            "sucursales": sucursales,
            "sin_identificar": sin_identificar,
            "renglones_por_sucursal": renglones_por_sucursal,
            "fotos": fotos,
            "fichas_cliente": [{"id": f["id"], "nombre": _nombre_de_ficha(f)} for f in fichas],
        }
    )
    return templates.TemplateResponse(request, "deposito_pedido.html", contexto)


def _grupos_buscar_pedidos(renglones: list[dict]) -> tuple[list[dict], dict]:
    """Agrupa los renglones de Buscar Pedidos por fecha, con los totales que se facturan.

    Los kilos son SIEMPRE los kilos_enviados que grabó el depósito al
    armar — un renglón sin kilaje se cuenta aparte, jamás se calcula el
    de la ficha acá. Los anulados se muestran (registrados) pero no suman.
    """
    grupos: list[dict] = []
    grupos_por_fecha: dict = {}
    total_kilos = 0.0
    total_bultos = 0.0
    sin_kilaje = 0
    anulados = 0

    for renglon in renglones:
        fecha = renglon["fecha_operacion"]
        grupo = grupos_por_fecha.get(fecha)
        if grupo is None:
            grupo = {
                "fecha": fecha,
                "fecha_mostrar": fecha.strftime("%d/%m/%Y"),
                "filas": [],
                "kilos": 0.0,
                "bultos": 0.0,
                "sin_kilaje": 0,
            }
            grupos_por_fecha[fecha] = grupo
            grupos.append(grupo)

        # Los bultos que se mandaron: la cantidad armada real si existe,
        # si no lo pedido (el renglón sin armar muestra lo pedido).
        bultos = float(renglon["cantidad_armada"]) if renglon["cantidad_armada"] is not None else float(renglon["cantidad"])
        anulado = renglon["anulado_el"] is not None
        armado = renglon["armado_el"] is not None
        kilos = float(renglon["kilos_enviados"]) if renglon["kilos_enviados"] is not None else None

        fila = {
            "articulo_nombre": renglon["articulo_nombre"] or "(sin identificar)",
            "sucursal": renglon["sucursal"],
            "bultos": bultos,
            "kilos": kilos,
            "anulado": anulado,
            "armado": armado,
        }
        grupo["filas"].append(fila)

        if anulado:
            anulados += 1
            continue
        grupo["bultos"] += bultos
        total_bultos += bultos
        if kilos is not None:
            grupo["kilos"] += kilos
            total_kilos += kilos
        else:
            grupo["sin_kilaje"] += 1
            sin_kilaje += 1

    totales = {
        "kilos": total_kilos,
        "bultos": total_bultos,
        "sin_kilaje": sin_kilaje,
        "anulados": anulados,
        "renglones": len(renglones),
    }
    return grupos, totales


def _leer_filtros_buscar_pedidos(cliente_id_texto, fecha_desde_texto, fecha_hasta_texto):
    cliente_id = _id_opcional_desde_query(cliente_id_texto)
    hoy = _hoy_argentina()
    fecha_desde = hoy - timedelta(days=7)
    fecha_hasta = hoy
    error_fecha = None
    if fecha_desde_texto:
        try:
            fecha_desde = date.fromisoformat(fecha_desde_texto)
        except ValueError:
            error_fecha = "La fecha desde no es válida."
    if fecha_hasta_texto:
        try:
            fecha_hasta = date.fromisoformat(fecha_hasta_texto)
        except ValueError:
            error_fecha = "La fecha hasta no es válida."
    if error_fecha is None and fecha_desde > fecha_hasta:
        error_fecha = "La fecha desde no puede ser posterior a la fecha hasta."
    return cliente_id, fecha_desde, fecha_hasta, error_fecha


@app.get("/administracion/pedidos/buscar")
def ver_buscar_pedidos(
    request: Request,
    cliente_id: str | None = None,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
):
    """Buscar Pedidos: lo que se mandó por fecha y artículo, con los KILOS REALES del depósito.

    Es la pantalla para facturar: los kilos son los que el depósito grabó
    al armar cada renglón (editables en Armar Pedido), no los de la
    ficha. Un renglón sin kilaje lo dice tal cual.
    """
    cliente_valor, desde, hasta, error_fecha = _leer_filtros_buscar_pedidos(cliente_id, fecha_desde, fecha_hasta)

    try:
        clientes = listar_clientes()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    contexto = {
        "clientes": clientes,
        "cliente_id": cliente_valor,
        "fecha_desde": desde.isoformat(),
        "fecha_hasta": hasta.isoformat(),
        "error_fecha": error_fecha,
        "grupos": None,
        "totales": None,
    }
    if cliente_valor is None or error_fecha:
        return templates.TemplateResponse(request, "deposito_pedido_buscar.html", contexto)

    try:
        renglones = buscar_renglones_pedidos(cliente_valor, desde, hasta)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    grupos, totales = _grupos_buscar_pedidos(renglones)
    contexto["grupos"] = grupos
    contexto["totales"] = totales
    return templates.TemplateResponse(request, "deposito_pedido_buscar.html", contexto)


def _datos_exportar_pedidos(cliente_id, fecha_desde, fecha_hasta):
    cliente_valor, desde, hasta, error_fecha = _leer_filtros_buscar_pedidos(cliente_id, fecha_desde, fecha_hasta)
    if cliente_valor is None:
        raise HTTPException(status_code=400, detail="Elegí el cliente antes de exportar.")
    if error_fecha:
        raise HTTPException(status_code=400, detail=error_fecha)
    try:
        cliente_dato = obtener_cliente(cliente_valor)
        renglones = buscar_renglones_pedidos(cliente_valor, desde, hasta)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db
    grupos, totales = _grupos_buscar_pedidos(renglones)
    nombre_cliente = cliente_dato["nombre"] if cliente_dato else f"#{cliente_valor}"
    return desde, hasta, nombre_cliente, grupos, totales


@app.get("/administracion/pedidos/buscar/exportar-pdf")
def exportar_pedidos_pdf(cliente_id: str = "", fecha_desde: str = "", fecha_hasta: str = ""):
    """Buscar Pedidos en PDF (mismos filtros que la pantalla) — sin tope."""
    desde, hasta, nombre_cliente, grupos, totales = _datos_exportar_pedidos(cliente_id, fecha_desde, fecha_hasta)
    pdf_bytes = generar_pdf_pedidos(desde, hasta, nombre_cliente, grupos, totales)
    nombre_archivo = f"Pedidos_{desde.isoformat()}_a_{hasta.isoformat()}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'},
    )


@app.get("/administracion/pedidos/buscar/exportar-excel")
def exportar_pedidos_excel(cliente_id: str = "", fecha_desde: str = "", fecha_hasta: str = ""):
    """Buscar Pedidos en Excel (mismos filtros que la pantalla) — sin tope."""
    desde, hasta, nombre_cliente, grupos, totales = _datos_exportar_pedidos(cliente_id, fecha_desde, fecha_hasta)
    excel_bytes = generar_excel_pedidos(desde, hasta, nombre_cliente, grupos, totales)
    nombre_archivo = f"Pedidos_{desde.isoformat()}_a_{hasta.isoformat()}.xlsx"
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'},
    )


@app.get("/deposito/pedido/cargar")
def ver_cargar_pedido(request: Request, cliente_id: str | None = None, fecha: str | None = None, error: str | None = None):
    """Cargar Pedido: pegar el texto del mail para que la IA lo lea, con revisión antes de guardar."""
    cliente_id_valor = _id_opcional_desde_query(cliente_id)
    fecha_valor = _fecha_pedido_o_hoy(fecha)
    try:
        clientes = listar_clientes()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    return templates.TemplateResponse(
        request,
        "deposito_pedido_cargar.html",
        {
            "clientes": clientes,
            "cliente_id": cliente_id_valor,
            "fecha": fecha_valor.isoformat(),
            "error": error,
        },
    )


@app.post("/deposito/pedido/cargar/leer")
async def leer_pedido_pegado(
    request: Request,
    cliente_id: int = Form(...),
    fecha: str = Form(""),
    texto: str = Form(""),
    imagenes: list[UploadFile] = File([]),
):
    """Lee el pedido con la IA — texto pegado O capturas del mail — y arma la revisión con el bloque de ESTA empresa.

    Las capturas son lo natural desde el celular (el pedido es una tabla
    en el cuerpo del mail): pueden ser VARIAS partes del mismo mail y van
    todas juntas a la misma lectura. La IA lee los originales; las
    versiones comprimidas (mismo pipeline que las comandas) viajan a la
    revisión y al confirmar quedan como respaldo en fotos_pedido — la
    lectura y el respaldo se resuelven de una.
    """
    fecha_valor = _fecha_pedido_o_hoy(fecha)
    try:
        clientes = listar_clientes()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db
    cliente = next((c for c in clientes if c["id"] == cliente_id), None)
    if cliente is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    def _pantalla_error(mensaje: str, status_code: int):
        return templates.TemplateResponse(
            request,
            "deposito_pedido_cargar.html",
            {"clientes": clientes, "cliente_id": cliente_id, "fecha": fecha_valor.isoformat(), "error": mensaje},
            status_code=status_code,
        )

    archivos = [a for a in imagenes if a is not None and a.filename]
    fotos_data: list[str] = []
    metodo_lectura = None
    if archivos:
        metodo_lectura = "ia_capturas"
        originales = []
        for archivo in archivos:
            contenido = await archivo.read()
            comprimida = _comprimir_foto_jpeg(contenido)
            if comprimida is None:
                return _pantalla_error(
                    f'No se pudo leer la imagen "{archivo.filename}". Probá con otra captura.', 400
                )
            originales.append(contenido)
            fotos_data.append(_generar_data_uri_generico(comprimida, "image/jpeg"))
        try:
            datos = extraer_pedido_de_imagenes(originales)
        except Exception as error_lector:
            return _pantalla_error(f"No se pudo leer el pedido: {error_lector}", 500)
    elif texto.strip():
        # Se lee SOLO el bloque de esta empresa si se puede delimitar; el
        # texto completo queda igual como texto_original del pedido. El
        # camino principal es el parser por estructura (cero IA en los
        # números); la IA es el respaldo, y la revisión dice cuál se usó.
        texto_recortado = recortar_bloque_de_empresa(texto, NOMBRE_EMPRESA)
        datos = parsear_pedido_estructurado(texto_recortado)
        metodo_lectura = "estructura" if datos is not None else "ia"
        if datos is None:
            try:
                datos = extraer_pedido_de_texto(texto_recortado)
            except Exception as error_lector:
                return _pantalla_error(f"No se pudo leer el pedido: {error_lector}", 500)
    else:
        return _pantalla_error("Pegá el texto del mail o subí una captura antes de leer.", 400)

    try:
        contexto = _contexto_revision_pedido(
            cliente_id, cliente["nombre"], fecha_valor, datos, texto, fotos_data, metodo_lectura=metodo_lectura
        )
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    if contexto is None:
        return templates.TemplateResponse(
            request,
            "deposito_pedido_cargar.html",
            {"clientes": clientes, "cliente_id": cliente_id, "fecha": fecha_valor.isoformat(),
             "error": "No se encontró ningún renglón de pedido en el texto. Fijate que hayas pegado el cuerpo del mail."},
            status_code=400,
        )

    return templates.TemplateResponse(request, "deposito_pedido_revision.html", contexto)


@app.post("/deposito/pedido/cargar/confirmar")
async def confirmar_pedido(request: Request):
    """Guarda el pedido revisado. Si ya había uno vigente para esa fecha, este lo reemplaza (el viejo se anula)."""
    form = await request.form()
    try:
        cliente_id = int(form.get("cliente_id", ""))
    except ValueError:
        raise HTTPException(status_code=400, detail="Cliente inválido")
    fecha_valor = _fecha_pedido_o_hoy(str(form.get("fecha", "")))
    texto_original = str(form.get("texto_original", "")) or None

    # Las fichas del cliente: la pantalla manda cuál eligió para cada
    # renglón y de acá sale el artículo. Una ficha que no sea de ESTE
    # cliente no existe para este pedido — el renglón queda sin
    # identificar, como cualquier otro que no matcheó.
    try:
        ficha_por_id = {f["id"]: f for f in listar_fichas_por_cliente(cliente_id)}
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    # Si la revisión vino de un mail registrado de la casilla, el guardado
    # además confirma ese mail (y el pedido nace con origen 'mail' y su
    # Message-ID: la idempotencia de la etapa 3).
    mail = None
    mail_id_texto = str(form.get("mail_id", "")).strip()
    if mail_id_texto:
        try:
            mail = obtener_mail_pedido(int(mail_id_texto))
        except ValueError:
            raise HTTPException(status_code=400, detail="Mail inválido")
        if mail is None:
            raise HTTPException(status_code=404, detail="Mail no encontrado")
        # Un mail con error de lectura previo se puede confirmar igual (el
        # reintento anduvo); solo un confirmado o ignorado queda cerrado.
        if mail["estado"] not in ("pendiente", "error"):
            return RedirectResponse(
                url=f"/sistema/casilla-pedidos?{urlencode({'error': 'Ese mail ya fue procesado (quizás desde otra pestaña). No se guardó nada.'})}",
                status_code=303,
            )

    cantidad_sucursales = int(form.get("cantidad_sucursales", "0") or 0)
    sucursales = []
    nombres_sucursales = []
    for indice in range(cantidad_sucursales):
        nombre = str(form.get(f"sucursal_{indice}_nombre", "")).strip()
        if not nombre:
            continue
        nombres_sucursales.append(nombre)
        sucursales.append(
            {
                "sucursal": nombre,
                "orden_compra": str(form.get(f"sucursal_{indice}_oc", "")).strip() or None,
                "total_bultos_declarado": _numero_pedido_o_none(form.get(f"sucursal_{indice}_total")),
            }
        )

    cantidad_renglones = int(form.get("cantidad_renglones", "0") or 0)
    renglones = []
    alias_a_guardar = []
    for indice in range(cantidad_renglones):
        if str(form.get(f"renglon_{indice}_descartar", "")).strip():
            continue  # "No es mío": el rastro queda en texto_original
        texto_codigo = str(form.get(f"renglon_{indice}_codigo", "")).strip() or None
        texto_descripcion = str(form.get(f"renglon_{indice}_descripcion", "")).strip() or None
        # La pantalla elige la FICHA (con qué se le vende a este cliente);
        # el artículo, que es lo que descuenta stock, sale de la ficha acá
        # en el server y jamás viaja por el formulario.
        ficha_id_texto = str(form.get(f"renglon_{indice}_ficha_id", "")).strip()
        ficha_id = int(ficha_id_texto) if ficha_id_texto else None
        ficha = ficha_por_id.get(ficha_id)
        if ficha is None:
            ficha_id = None
        articulo_id = ficha["articulo_id"] if ficha else None

        if ficha_id is not None and str(form.get(f"renglon_{indice}_guardar_alias", "")).strip():
            alias_a_guardar.append((ficha_id, texto_codigo, texto_descripcion))

        con_cantidad = False
        for indice_sucursal, nombre in enumerate(nombres_sucursales):
            cantidad = _numero_pedido_o_none(form.get(f"renglon_{indice}_cant_{indice_sucursal}"))
            if cantidad is None or cantidad == 0:
                continue
            con_cantidad = True
            renglones.append(
                {
                    "sucursal": nombre,
                    "articulo_id": articulo_id,
                    "ficha_id": ficha_id,
                    "texto_codigo": texto_codigo,
                    "texto_descripcion": texto_descripcion,
                    "cantidad": cantidad,
                }
            )
        if not con_cantidad:
            # Renglón sin ninguna cantidad: se guarda igual (invariante:
            # nada del mail se pierde), sin sucursal y en 0.
            renglones.append(
                {
                    "sucursal": None,
                    "articulo_id": articulo_id,
                    "ficha_id": ficha_id,
                    "texto_codigo": texto_codigo,
                    "texto_descripcion": texto_descripcion,
                    "cantidad": 0,
                }
            )

    if not renglones:
        raise HTTPException(status_code=400, detail="El pedido no tiene ningún renglón para guardar.")

    try:
        pedido_vigente = obtener_pedido_vigente(cliente_id, fecha_valor)
        pedido_id = crear_pedido(
            cliente_id,
            fecha_valor,
            "mail" if mail else "texto",
            texto_original,
            sucursales,
            renglones,
            reemplaza_a_pedido_id=pedido_vigente["id"] if pedido_vigente else None,
            mail_message_id=mail["message_id"] if mail else None,
            recibido_el=mail["recibido_el"] if mail else None,
        )
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"No se pudo guardar el pedido: {error_db}") from error_db

    if mail is not None:
        try:
            marcar_mail_pedido_confirmado(mail["id"], pedido_id)
        except Exception:
            logger.exception("El pedido %s quedó guardado pero no se pudo marcar el mail %s como confirmado", pedido_id, mail["id"])

    # Los alias se guardan después del pedido (si fallan, el pedido ya
    # está a salvo): solo completan campos vacíos de la ficha.
    for ficha_id_alias, texto_codigo, texto_descripcion in alias_a_guardar:
        try:
            guardar_alias_en_ficha(ficha_id_alias, texto_codigo, texto_descripcion)
        except Exception:
            logger.exception("No se pudo guardar el alias en la ficha %s (cliente %s)", ficha_id_alias, cliente_id)

    # Las capturas leídas quedan como respaldo del pedido (ya vienen
    # comprimidas desde la lectura). Si Storage falla, el pedido igual
    # quedó guardado — mismo criterio que las fotos de precios.
    cantidad_fotos = int(form.get("cantidad_fotos", "0") or 0)
    for indice in range(cantidad_fotos):
        bytes_foto = _bytes_desde_data_uri(str(form.get(f"foto_data_{indice}", "")))
        if not bytes_foto:
            continue
        try:
            foto_ruta = subir_foto_comanda(bytes_foto, f"pedido-{pedido_id}")
            agregar_foto_pedido(pedido_id, foto_ruta)
        except Exception:
            logger.exception("No se pudo subir la captura del pedido %s — el pedido quedó guardado igual", pedido_id)

    aviso = "Pedido guardado."
    if pedido_vigente:
        aviso = "Pedido guardado. Reemplaza al anterior de esta fecha, que quedó anulado de registro."
    return RedirectResponse(
        url=f"/deposito/pedido?{urlencode({'cliente_id': cliente_id, 'fecha': fecha_valor.isoformat(), 'aviso': aviso})}",
        status_code=303,
    )


@app.post("/deposito/pedido/{pedido_id}/renglones/{renglon_id}/asignar")
def asignar_renglon_pedido_ruta(
    pedido_id: int,
    renglon_id: int,
    cliente_id: int = Form(...),
    fecha: str = Form(""),
    ficha_id: str = Form(""),
    guardar_alias: str = Form(""),
    texto_codigo: str = Form(""),
    texto_descripcion: str = Form(""),
):
    """Asigna a mano un renglón "sin identificar" desde la pantalla del pedido (y opcionalmente guarda el alias).

    Se elige la FICHA, no el artículo: es la que dice a qué precio, con qué
    kilaje y con qué nombre se le vende. El artículo lo deriva la base de
    la ficha elegida.
    """
    try:
        ficha_id_valor = int(ficha_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Elegí el artículo.")

    try:
        asignar_ficha_a_renglon_pedido(renglon_id, ficha_id_valor)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"No se pudo asignar el artículo: {error_db}") from error_db

    if guardar_alias.strip():
        try:
            guardar_alias_en_ficha(ficha_id_valor, texto_codigo.strip() or None, texto_descripcion.strip() or None)
        except Exception:
            logger.exception("No se pudo guardar el alias en la ficha %s (cliente %s)", ficha_id_valor, cliente_id)

    return RedirectResponse(
        url=f"/deposito/pedido?{urlencode({'cliente_id': cliente_id, 'fecha': fecha})}", status_code=303
    )


@app.post("/deposito/pedido/{pedido_id}/fotos")
async def subir_foto_pedido_ruta(
    pedido_id: int,
    archivo: UploadFile = File(...),
    cliente_id: int = Form(...),
    fecha: str = Form(""),
):
    """Suma una captura de respaldo del mail al pedido (comprimida con el mismo pipeline que las comandas)."""
    contenido = await archivo.read()
    nombre = (archivo.filename or "").lower()
    try:
        if nombre.endswith(".pdf"):
            foto_ruta = subir_archivo_comanda(comprimir_pdf(contenido), f"pedido-{pedido_id}", "pdf", "application/pdf")
        else:
            comprimida = _comprimir_foto_jpeg(contenido)
            if comprimida is None:
                raise HTTPException(status_code=400, detail="No se pudo leer la imagen. Probá con otra captura.")
            foto_ruta = subir_foto_comanda(comprimida, f"pedido-{pedido_id}")
        agregar_foto_pedido(pedido_id, foto_ruta)
    except HTTPException:
        raise
    except Exception as error_subida:
        raise HTTPException(status_code=500, detail=f"No se pudo subir la captura: {error_subida}") from error_subida

    return RedirectResponse(
        url=f"/deposito/pedido?{urlencode({'cliente_id': cliente_id, 'fecha': fecha})}", status_code=303
    )


@app.get("/deposito/pedido/{pedido_id}/fotos/{foto_id}/ver")
def ver_foto_pedido_ruta(pedido_id: int, foto_id: int):
    """URL firmada de UNA captura del pedido (miniatura y toque para agrandar)."""
    try:
        fotos = listar_fotos_pedido(pedido_id)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db
    foto = next((f for f in fotos if f["id"] == foto_id), None)
    if foto is None:
        raise HTTPException(status_code=404, detail="Esa captura no es de este pedido")
    try:
        url_firmada = obtener_url_foto(foto["foto_ruta"])
    except Exception as error_storage:
        raise HTTPException(status_code=500, detail=f"No se pudo generar el link: {error_storage}") from error_storage
    return RedirectResponse(url=url_firmada, status_code=307)


@app.post("/deposito/pedido/{pedido_id}/fotos/{foto_id}/borrar")
def borrar_foto_pedido_ruta(pedido_id: int, foto_id: int, cliente_id: int = Form(...), fecha: str = Form("")):
    """Borra una captura del pedido; el archivo del Storage solo si ningún otro pedido lo usa."""
    try:
        ruta_sin_uso = borrar_foto_pedido(foto_id)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"No se pudo borrar la captura: {error_db}") from error_db
    if ruta_sin_uso:
        try:
            borrar_foto_comanda(ruta_sin_uso)
        except Exception:
            logger.exception("No se pudo borrar la captura del Storage (%s) — la referencia ya se borró", ruta_sin_uso)
    return RedirectResponse(
        url=f"/deposito/pedido?{urlencode({'cliente_id': cliente_id, 'fecha': fecha})}", status_code=303
    )


@app.post("/deposito/pedido/dias-sin-pedido")
def marcar_dia_sin_pedido_ruta(cliente_id: int = Form(...), fecha: str = Form(...), motivo: str = Form("")):
    """Cierra un día esperado que quedó sin pedido (feriado, el cliente no pidió): la alerta lo deja de contar."""
    try:
        fecha_valor = date.fromisoformat(fecha)
    except ValueError:
        raise HTTPException(status_code=400, detail="Fecha inválida")
    try:
        marcar_dia_sin_pedido(cliente_id, fecha_valor, motivo.strip() or None)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"No se pudo marcar el día sin pedido: {error_db}") from error_db
    aviso = f"Marcado: el {fecha_valor.strftime('%d/%m/%Y')} no hubo pedido."
    return RedirectResponse(
        url=f"/deposito/pedido?{urlencode({'cliente_id': cliente_id, 'aviso': aviso})}",
        status_code=303,
    )


@app.post("/deposito/pedido/dias-sin-pedido/deshacer")
def deshacer_dia_sin_pedido_ruta(cliente_id: int = Form(...), fecha: str = Form(...)):
    """Deshace la marca "no hubo pedido" (marca administrativa: se borra, no hay baja lógica que guardar)."""
    try:
        fecha_valor = date.fromisoformat(fecha)
    except ValueError:
        raise HTTPException(status_code=400, detail="Fecha inválida")
    try:
        borrar_dia_sin_pedido(cliente_id, fecha_valor)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"No se pudo deshacer la marca: {error_db}") from error_db
    return RedirectResponse(
        url=f"/deposito/pedido?{urlencode({'cliente_id': cliente_id, 'aviso': 'Marca deshecha: el día vuelve a contar como faltante.'})}",
        status_code=303,
    )


def _diff_pedido_contra_anterior(renglones_nuevos: list[dict], renglones_viejos: list[dict]) -> list[str]:
    """Qué cambió entre el pedido corregido y el que reemplazó, para que el armado no arme algo que ya no va.

    Compara los renglones IDENTIFICADOS por (sucursal, artículo): cantidad
    distinta, renglones que ya no están y renglones nuevos. Los cambiados
    llegan sin tildar (el traslado de tildes solo copia renglones
    idénticos, ver crear_pedido) — este diff explica por qué.
    """
    def _clave(renglon):
        return (renglon["sucursal"], renglon["articulo_id"])

    viejos = {_clave(r): r for r in renglones_viejos if r["articulo_id"] is not None}
    nuevos = {_clave(r): r for r in renglones_nuevos if r["articulo_id"] is not None}

    cambios = []
    for clave, nuevo in nuevos.items():
        viejo = viejos.get(clave)
        if viejo is None:
            cambios.append(f"nuevo: {nuevo['articulo_nombre']} {nuevo['sucursal'] or ''} {_formatear_numero(nuevo['cantidad'])}".strip())
        elif float(viejo["cantidad"]) != float(nuevo["cantidad"]):
            cambios.append(
                f"cambió: {nuevo['articulo_nombre']} {nuevo['sucursal'] or ''} "
                f"{_formatear_numero(viejo['cantidad'])} → {_formatear_numero(nuevo['cantidad'])}"
            )
    for clave, viejo in viejos.items():
        if clave not in nuevos:
            cambios.append(f"ya no está: {viejo['articulo_nombre']} {viejo['sucursal'] or ''}".strip())
    return sorted(cambios)


@app.get("/deposito/pedido/armar")
def ver_armar_pedido(request: Request, cliente_id: str | None = None, fecha: str | None = None, sucursal: str | None = None, aviso: str | None = None):
    """Armar Pedido: el del depósito, parado y con una mano — sin clave, es la operación del día a día.

    Primero el LISTADO de pedidos (hoy primero, después los próximos —
    el del sábado se puede ir armando el viernes — y los de la última
    semana, que no desaparecen: un pedido terminado queda marcado como
    completo). Recién al entrar a un pedido se elige la sucursal (una a
    la vez, con su OC y el progreso); adentro, renglones grandes con un
    tilde por renglón. El tilde significa "terminé con este renglón": si
    armó menos de lo pedido, "Armé menos" guarda la cantidad real y el
    renglón queda incompleto, marcado. Los tildados bajan y se atenúan.
    """
    cliente_id_valor = _id_opcional_desde_query(cliente_id)
    fecha_valor = _fecha_pedido_o_hoy(fecha)
    # Sin fecha en la URL se muestra el LISTADO; con fecha, ese pedido.
    modo_lista = not fecha

    try:
        clientes = listar_clientes()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    contexto = {
        "clientes": clientes,
        "cliente_id": cliente_id_valor,
        "fecha": fecha_valor.isoformat(),
        "fecha_mostrar": fecha_valor.strftime("%d/%m/%Y"),
        "pedido": None,
        "sucursal_elegida": None,
        "modo_lista": modo_lista,
        "aviso": aviso,
    }
    if cliente_id_valor is None:
        return templates.TemplateResponse(request, "deposito_pedido_armar.html", contexto)

    # Los mails de pedido pendientes del cliente, acá mismo: si "Buscar
    # pedido" trajo uno, el que arma lo confirma sin ir a otra pantalla.
    # No fatal: el armado del día no se cae por este listado auxiliar.
    contexto["mails_sin_confirmar"] = []
    try:
        for mail_trabado in listar_mails_pedido_sin_procesar_de_cliente(cliente_id_valor):
            llegada = mail_trabado["recibido_el"].astimezone(ARGENTINA).date()
            fecha_estimada = fecha_de_pedido_del_asunto(mail_trabado["asunto"], llegada) or llegada
            mail_trabado["fecha_estimada_mostrar"] = fecha_estimada.strftime("%d/%m/%Y")
            contexto["mails_sin_confirmar"].append(mail_trabado)
    except Exception:
        logger.exception("No se pudieron listar los mails pendientes del cliente %s en Armar Pedido", cliente_id_valor)

    if modo_lista:
        try:
            contexto["pedidos_listado"] = _listado_de_pedidos(cliente_id_valor, _hoy_argentina())
        except Exception as error_db:
            raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db
        return templates.TemplateResponse(request, "deposito_pedido_armar.html", contexto)

    try:
        pedido = obtener_pedido_vigente(cliente_id_valor, fecha_valor)
        if pedido is not None:
            sucursales = listar_sucursales_pedido(pedido["id"])
            renglones = listar_renglones_pedido(pedido["id"])
            renglones_viejos = (
                listar_renglones_pedido(pedido["reemplaza_a_pedido_id"]) if pedido["reemplaza_a_pedido_id"] else []
            )
        else:
            sucursales, renglones, renglones_viejos = [], [], []
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    if pedido is None:
        return templates.TemplateResponse(request, "deposito_pedido_armar.html", contexto)

    # Progreso por sucursal, sobre los renglones IDENTIFICADOS y NO
    # anulados (los sin identificar se asignan primero desde Pedido; los
    # anulados no se van a armar y no cuentan en el progreso).
    identificados = [r for r in renglones if r["articulo_id"] is not None and r["anulado_el"] is None]
    anulados_todos = [r for r in renglones if r["articulo_id"] is not None and r["anulado_el"] is not None]
    for s in sucursales:
        propios = [r for r in identificados if r["sucursal"] == s["sucursal"]]
        s["total_renglones"] = len(propios)
        s["armados"] = sum(1 for r in propios if r["armado_el"] is not None)
        # "<" y no "<>": ver el mismo conteo en _renderizar_pedido.
        s["incompletos"] = sum(
            1 for r in propios
            if r["armado_el"] is not None and r["cantidad_armada"] is not None
            and float(r["cantidad_armada"]) < float(r["cantidad"])
        )

    sin_identificar = sum(1 for r in renglones if r["articulo_id"] is None)
    diff = _diff_pedido_contra_anterior(renglones, renglones_viejos) if renglones_viejos else []

    contexto.update(
        {
            "pedido": pedido,
            "sucursales": sucursales,
            "sin_identificar": sin_identificar,
            "diff": diff,
            # Para el botón "Terminar pedido": cuántos quedan sin tildar en
            # TODO el pedido. Se suma DE LOS MISMOS conteos por sucursal que
            # muestra la pantalla — así el botón jamás puede contradecirlos.
            # Un renglón identificado SIN sucursal (vino sin cantidades en
            # el mail: cantidad 0) no aparece en ninguna sucursal y no se
            # puede tildar: no es un pendiente, no se cuenta.
            "pendientes_totales": sum(s["total_renglones"] - s["armados"] for s in sucursales),
        }
    )

    sucursal_valida = next((s for s in sucursales if s["sucursal"] == sucursal), None)
    if sucursal_valida is None:
        return templates.TemplateResponse(request, "deposito_pedido_armar.html", contexto)

    # Los kilos con los que se manda cada renglón: el default sale de la
    # ficha (bultos × contenido por caja) pero es EDITABLE — lo que queda
    # grabado es lo que el depósito dijo que mandó, no la ficha.
    try:
        fichas = listar_fichas_por_cliente(cliente_id_valor)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db
    # El kilaje se busca por FICHA, no por artículo: "Banana Bolivia" viene
    # en cajas de 6 kg y "Banana Ecuador" en cajas de 10, y son el mismo
    # artículo. Por artículo, el que arma una vería el default de la otra
    # — y esos kilos son los que se facturan. El renglón sabe su ficha
    # desde la Parte 2; el que quedó sin ficha (renglón viejo, o ficha
    # borrada) cae al kilaje de alguna ficha de su artículo, que es lo
    # mejor que hay y lo que se hacía siempre.
    contenido_por_ficha = {f["id"]: float(f["contenido_caja"]) for f in fichas if f.get("contenido_caja")}
    unidad_por_ficha = {f["id"]: f.get("unidad_venta") for f in fichas}
    contenido_por_articulo = {
        f["articulo_id"]: float(f["contenido_caja"]) for f in fichas if f.get("contenido_caja")
    }
    unidad_por_articulo = {f["articulo_id"]: f.get("unidad_venta") for f in fichas}
    etiquetas_por_bulto = {"kilo": "Kilos por cajón", "unidad": "Unidades por cajón", "cubeta": "Cubetas por cajón"}
    sufijos_unidad = {"kilo": "kg", "unidad": "u", "cubeta": "cub."}

    def _contenido_de(renglon):
        if renglon.get("ficha_id") in contenido_por_ficha:
            return contenido_por_ficha[renglon["ficha_id"]]
        return contenido_por_articulo.get(renglon["articulo_id"])

    def _unidad_de(renglon):
        if renglon.get("ficha_id") in unidad_por_ficha:
            return unidad_por_ficha[renglon["ficha_id"]]
        return unidad_por_articulo.get(renglon["articulo_id"])

    def _kilos_de_ficha(renglon, bultos):
        contenido = _contenido_de(renglon)
        if contenido is None or bultos is None:
            return None
        return round(float(bultos) * contenido, 2)

    propios = [r for r in identificados if r["sucursal"] == sucursal_valida["sucursal"]]
    pendientes = sorted((r for r in propios if r["armado_el"] is None), key=lambda r: r["nombre_venta"])
    armados = sorted((r for r in propios if r["armado_el"] is not None), key=lambda r: r["nombre_venta"])
    anulados = sorted(
        (r for r in anulados_todos if r["sucursal"] == sucursal_valida["sucursal"]),
        key=lambda r: r["nombre_venta"],
    )
    # Qué fichas tienen cajas armadas hoy: SOLO los ids, sin cantidades.
    # Esta pantalla es de operario y el número del sistema no puede viajar
    # a su HTML (criterio Vacíos) — alcanza con saber si hay o no hay.
    try:
        con_cajas = fichas_con_cajas_armadas()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    for r in pendientes:
        r["contenido_caja"] = _contenido_de(r)
        unidad = _unidad_de(r)
        # La etiqueta dice la unidad REAL del artículo (como en las otras
        # pantallas): "Kilos por cajón", "Unidades por cajón"...
        r["etiqueta_por_bulto"] = etiquetas_por_bulto.get(unidad, "Contenido por cajón")
        r["sufijo_unidad"] = sufijos_unidad.get(unidad, "")
        r["total_sugerido"] = _kilos_de_ficha(r, r["cantidad"])
        # El pedido sale del stock de LA FICHA, no del artículo: que haya
        # bananas no quiere decir que haya cajas de Banana Bolivia. Avisa
        # y NO traba: el piso es la verdad, y el que arma puede estar
        # viendo cajas que todavía nadie cargó como guía R.
        # Un renglón sin ficha (viejo, o ficha borrada) no se marca: no
        # hay ficha de la cual mirar el stock.
        r["sin_cajas_de_la_ficha"] = (
            r.get("ficha_id") is not None and r["ficha_id"] not in con_cajas
        )
    for r in armados:
        # Con qué comparar para la marca "editado a mano": el cálculo de
        # ficha sobre los bultos que realmente armó.
        bultos_reales = r["cantidad_armada"] if r["cantidad_armada"] is not None else r["cantidad"]
        kilos_ficha = _kilos_de_ficha(r, bultos_reales)
        editado = (
            r["kilos_enviados"] is not None
            and (kilos_ficha is None or float(r["kilos_enviados"]) != kilos_ficha)
        )
        # El desvío se calcula recién acá, con el renglón ya tildado: hasta
        # que no se tilda no existe el kilaje real contra el cual comparar.
        r["fuera_de_tolerancia"] = _desvio_de_tolerancia(r, _contenido_de(r), _unidad_de(r))
        # Las dos marcas dicen lo mismo con distinta fuerza, así que no se
        # apilan: cuando salta la de tolerancia, "editado a mano" queda
        # tapada. Lo que NO se pierde es que el kilaje lo puso una persona
        # — eso lo dice el propio aviso rojo, que si no se leería como un
        # error de cálculo del sistema.
        r["kilos_editados"] = editado and r["fuera_de_tolerancia"] is None

    contexto.update(
        {
            "sucursal_elegida": sucursal_valida,
            "pendientes": pendientes,
            "armados": armados,
            "anulados": anulados,
        }
    )
    return templates.TemplateResponse(request, "deposito_pedido_armar.html", contexto)


# La tolerancia del kilaje declarado al armar, contra lo que dice la ficha.
# Va como constante y no en la base a propósito: los 3 kg salen de que la
# variación real es por tamaño o deshidratación, y eso no se mueve. Si
# alguna vez hay que cambiarlo, es un deploy — no vale una tabla ni un
# viaje a Supabase para un número que nadie va a tocar.
#
# POR BULTO, no por renglón: 20 bultos con 1 kg de más cada uno son 20 kg
# de diferencia en el renglón y están DENTRO de tolerancia; 2 bultos con
# 5 kg de más cada uno son 10 kg en el renglón y están FUERA. Lo que se
# controla es cómo se llenó cada caja, no cuánto suma el renglón.
TOLERANCIA_KILOS_POR_BULTO = 3


def _desvio_de_tolerancia(renglon, contenido_ficha, unidad):
    """Cuántos kilos por bulto se pasó de la ficha, o None si no aplica o está en tolerancia.

    Solo para fichas por KILO. En una ficha por unidad o por cubeta, "3"
    no significa nada: 3 unidades y 3 cubetas son cosas distintas y nadie
    definió un equivalente, así que inventarlo sería inventar una regla.

    Se compara el kilaje POR BULTO —el declarado contra el de la ficha—,
    no el total del renglón.
    """
    if unidad != "kilo" or not contenido_ficha:
        return None
    if renglon.get("kilos_enviados") is None:
        return None
    bultos = renglon["cantidad_armada"] if renglon.get("cantidad_armada") is not None else renglon["cantidad"]
    if not bultos or float(bultos) <= 0:
        return None
    por_bulto = float(renglon["kilos_enviados"]) / float(bultos)
    desvio = round(por_bulto - float(contenido_ficha), 2)
    if abs(desvio) <= TOLERANCIA_KILOS_POR_BULTO:
        return None
    return {"por_bulto": round(por_bulto, 2), "ficha": float(contenido_ficha), "desvio": desvio}


def _url_vuelta_armado(cliente_id: int, fecha: str, sucursal: str) -> str:
    return f"/deposito/pedido/armar?{urlencode({'cliente_id': cliente_id, 'fecha': fecha, 'sucursal': sucursal})}"


@app.post("/deposito/pedido/{pedido_id}/renglones/{renglon_id}/armar")
def armar_renglon_pedido_ruta(
    pedido_id: int,
    renglon_id: int,
    cliente_id: int = Form(...),
    fecha: str = Form(""),
    sucursal: str = Form(""),
    cantidad_armada: str = Form(""),
    cantidad_pedida: str = Form(""),
    kilos_por_bulto: str = Form(""),
):
    """Tilda un renglón como armado. Con cantidad_armada (menor a lo pedido), queda "incompleto" con su cantidad real.

    kilos_por_bulto: lo que la persona carga (el cajón va con 16 kg — ese
    es el número que sabe y corrige). El TOTAL enviado lo calcula el
    SERVER acá: por bulto × bultos armados de ESTE tilde, y queda
    CONGELADO en kilos_enviados — lo que se factura es un dato grabado,
    no una multiplicación viva. Vacío = sin kilaje (NULL, los listados lo
    dicen).
    """
    cantidad_armada_valor = None
    texto = cantidad_armada.strip()
    if texto:
        try:
            cantidad_armada_valor = float(texto)
        except ValueError:
            raise HTTPException(status_code=400, detail="La cantidad armada tiene que ser un número.")
        if cantidad_armada_valor <= 0:
            raise HTTPException(status_code=400, detail="La cantidad armada tiene que ser mayor a cero.")
        pedida = _numero_pedido_o_none(cantidad_pedida)
        # NULL significa "armó EXACTAMENTE lo pedido", y por eso el número
        # redundante no se guarda. Todo lo demás sí, y eso incluye armar de
        # MÁS: hasta el 05/09 un 80 sobre 50 se guardaba como NULL —o sea
        # 50— y los 30 de más salían del galpón sin quedar en ningún lado:
        # ni en el stock, ni en la factura, ni en una pantalla.
        #
        # El camión ya salió con 80. Negar el registro no des-entrega la
        # mercadería. Es la inversa del freno del reproceso, y a propósito:
        # allá se traba porque se congela un costo que no se corrige nunca;
        # acá no se congela nada y el hecho ya ocurrió.
        #
        # Queda entonces: NULL = exacto, < = incompleto, > = armó de más.
        if pedida is not None and cantidad_armada_valor == pedida:
            cantidad_armada_valor = None

    kilos_valor = None
    texto_kilos = kilos_por_bulto.strip()
    if texto_kilos:
        try:
            por_bulto = float(texto_kilos)
        except ValueError:
            raise HTTPException(status_code=400, detail="El kilaje por bulto tiene que ser un número.")
        if por_bulto <= 0:
            raise HTTPException(status_code=400, detail="El kilaje por bulto tiene que ser mayor a cero.")
        bultos_armados = cantidad_armada_valor if cantidad_armada_valor is not None else _numero_pedido_o_none(cantidad_pedida)
        if bultos_armados is None:
            raise HTTPException(status_code=400, detail="Falta la cantidad de bultos para calcular los kilos enviados.")
        kilos_valor = round(por_bulto * bultos_armados, 2)

    try:
        marcar_renglon_armado(renglon_id, cantidad_armada_valor, kilos_valor)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"No se pudo marcar el renglón: {error_db}") from error_db

    return RedirectResponse(url=_url_vuelta_armado(cliente_id, fecha, sucursal), status_code=303)


@app.get("/deposito/pedido/renglones/{renglon_id}/lotes")
def lotes_del_renglon_armado(renglon_id: int):
    """De qué lotes salió un renglón YA ARMADO: lo que la tarjeta muestra plegado.

    Solo después del tilde, y eso lo decide db.desglose_de_renglon_armado
    devolviendo None: antes, la pantalla de armado no puede mostrar números
    del sistema — si el que arma los ve, arma contra el sistema en vez de
    contra el piso. Después del tilde ya declaró cuánto mandó.
    """
    try:
        desglose = desglose_de_renglon_armado(renglon_id)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db
    if desglose is None:
        raise HTTPException(status_code=404, detail="Ese renglón no está armado.")

    return JSONResponse(
        {
            "armado": desglose["armado"],
            "editado": desglose["editado"],
            "lotes": _desglose_para_pantalla(desglose["lotes"]),
            "propuesta": desglose["propuesta"],
        }
    )


@app.post("/deposito/pedido/{pedido_id}/renglones/{renglon_id}/lotes")
def guardar_lotes_del_renglon_ruta(
    pedido_id: int,
    renglon_id: int,
    cliente_id: int = Form(...),
    fecha: str = Form(""),
    sucursal: str = Form(""),
    reparto: str = Form(""),
):
    """El que arma dice de qué lote sacó los bultos. AVISA Y NO TRABA.

    Al revés que el reproceso: acá no hay freno. Si lo que reparte no llega a
    lo que mandó, la diferencia cae al FIFO o a sin_lote, como hasta hoy —el
    camión ya salió y el piso es la verdad—. Lo único imposible es pedirle a
    un lote más de lo que tenía, y eso lo ataja la pantalla.

    Se guarda SOLO LA EXCEPCIÓN: con el reparto vacío no queda ninguna fila y
    el renglón vuelve a repartirse por FIFO. Aceptar la propuesta es no
    guardar nada.
    """
    error, reparto_valor = _reparto_del_formulario(reparto)
    if error is None:
        try:
            guardar_lotes_elegidos(
                renglon_id,
                [
                    {"lote_tipo": fila["tipo_lote"], "lote_origen_id": fila["origen_id"],
                     "bultos": fila["bultos"]}
                    for fila in (reparto_valor or [])
                ],
            )
        except Exception as error_db:
            raise HTTPException(status_code=500, detail=f"No se pudo guardar de dónde salió: {error_db}") from error_db

    return RedirectResponse(url=_url_vuelta_armado(cliente_id, fecha, sucursal), status_code=303)


@app.post("/deposito/pedido/{pedido_id}/renglones/{renglon_id}/desarmar")
def desarmar_renglon_pedido_ruta(
    pedido_id: int,
    renglon_id: int,
    cliente_id: int = Form(...),
    fecha: str = Form(""),
    sucursal: str = Form(""),
):
    """Destilda un renglón (toque por error, o apareció el stock que faltaba)."""
    try:
        desmarcar_renglon_armado(renglon_id)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"No se pudo destildar el renglón: {error_db}") from error_db

    return RedirectResponse(url=_url_vuelta_armado(cliente_id, fecha, sucursal), status_code=303)


@app.post("/deposito/pedido/{pedido_id}/renglones/{renglon_id}/anular")
def anular_renglon_pedido_ruta(
    pedido_id: int,
    renglon_id: int,
    cliente_id: int = Form(...),
    fecha: str = Form(""),
    sucursal: str = Form(""),
):
    """La CRUZ: este artículo no se va a armar. Anulado (registrado, nunca borrado), fuera del progreso."""
    try:
        anular_renglon_pedido(renglon_id)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"No se pudo anular el renglón: {error_db}") from error_db
    return RedirectResponse(url=_url_vuelta_armado(cliente_id, fecha, sucursal), status_code=303)


@app.post("/deposito/pedido/{pedido_id}/renglones/{renglon_id}/desanular")
def desanular_renglon_pedido_ruta(
    pedido_id: int,
    renglon_id: int,
    cliente_id: int = Form(...),
    fecha: str = Form(""),
    sucursal: str = Form(""),
):
    """Deshace la cruz: el renglón vuelve a los pendientes."""
    try:
        desanular_renglon_pedido(renglon_id)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"No se pudo reponer el renglón: {error_db}") from error_db
    return RedirectResponse(url=_url_vuelta_armado(cliente_id, fecha, sucursal), status_code=303)


@app.post("/deposito/pedido/{pedido_id}/terminar")
def terminar_pedido_ruta(pedido_id: int, cliente_id: int = Form(...), fecha: str = Form("")):
    """El "Terminar pedido": cierre explícito del armado. Con renglones sin tildar se confirma en pantalla, no se impide."""
    try:
        cerrar_armado_pedido(pedido_id)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"No se pudo terminar el pedido: {error_db}") from error_db
    return RedirectResponse(
        url=f"/deposito/pedido/armar?{urlencode({'cliente_id': cliente_id, 'aviso': f'Pedido del {fecha} terminado.'})}",
        status_code=303,
    )


@app.post("/deposito/pedido/{pedido_id}/reabrir")
def reabrir_pedido_ruta(pedido_id: int, cliente_id: int = Form(...), fecha: str = Form("")):
    """Reabre un pedido terminado (el cierre es operativo, no un candado)."""
    try:
        reabrir_armado_pedido(pedido_id)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"No se pudo reabrir el pedido: {error_db}") from error_db
    return RedirectResponse(
        url=f"/deposito/pedido/armar?{urlencode({'cliente_id': cliente_id, 'fecha': fecha})}", status_code=303
    )


# --- Casilla de pedidos (etapa 3, tramo 1): configuración y revisión manual ---


def _renderizar_casilla_pedidos(request: Request, *, mensaje: str | None = None, error: str | None = None, status_code: int = 200):
    try:
        casillas = listar_casillas_pedidos()
        mails = listar_mails_pedido()
        clientes = listar_clientes()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    # El latido del bucle: si quedó viejo (más de dos ticks sin sellar),
    # el bucle NO está corriendo — la pantalla lo dice en rojo, sin tener
    # que deducirlo de logs ni de "no llegó ningún mail".
    try:
        ultimo_tick = obtener_ultimo_tick_revision()
    except Exception:
        logger.exception("No se pudo leer el latido del bucle de revisión")
        ultimo_tick = None
    # Umbral: 3 ticks de gracia MÁS el tope de un tick colgado — con un
    # IMAP colgado el latido se re-sella recién cada timeout + espera, y
    # sin ese margen la tarjeta roja parpadearía por un cuelgue transitorio
    # del que el bucle se recupera solo.
    tick_vencido = (
        ultimo_tick is None
        or (datetime.now(ARGENTINA) - ultimo_tick)
        > timedelta(seconds=SEGUNDOS_TICK_REVISION * 3 + SEGUNDOS_TIMEOUT_TICK)
    )

    return templates.TemplateResponse(
        request,
        "sistema_casilla_pedidos.html",
        {
            "casillas": casillas,
            "mails": mails,
            "clientes": clientes,
            "ultimo_tick": ultimo_tick,
            "tick_vencido": tick_vencido,
            # La clave JAMÁS pasa por esta pantalla: solo se muestra si la
            # variable de Railway está configurada o falta.
            "clave_configurada": clave_casilla_configurada() is not None,
            "clave_env_var": CLAVE_CASILLA_ENV_VAR,
            "mensaje": mensaje,
            "error": error,
        },
        status_code=status_code,
    )


def _redirigir_a_casilla(mensaje: str | None = None, error: str | None = None):
    parametros = {}
    if mensaje:
        parametros["mensaje"] = mensaje
    if error:
        parametros["error"] = error
    url = "/sistema/casilla-pedidos"
    if parametros:
        url += f"?{urlencode(parametros)}"
    return RedirectResponse(url=url, status_code=303)


@app.get("/sistema/casilla-pedidos")
def ver_casilla_pedidos(request: Request, mensaje: str | None = None, error: str | None = None):
    """Casilla de Pedidos: la configuración de lectura del buzón, su estado y los mails registrados."""
    return _renderizar_casilla_pedidos(request, mensaje=mensaje, error=error)


@app.post("/sistema/casilla-pedidos/guardar")
def guardar_casilla_pedidos(
    request: Request,
    direccion: str = Form(""),
    servidor_imap: str = Form(""),
    cliente_id: int = Form(...),
    asunto_filtro: str = Form(""),
    remitentes_permitidos: str = Form(""),
    casilla_id: str = Form(""),
):
    """Alta o edición de la configuración de la casilla. La clave no viaja por acá: vive en Railway.

    El asunto es el filtro OBLIGATORIO (por contenido, sin mayúsculas ni
    acentos: "Pedido Dia" matchea "Pedido Día 22-08 Sabado"); el remitente
    es opcional — vacío significa cualquier remitente, así el pedido no se
    pierde porque cambió quién lo manda.
    """
    direccion_valor = direccion.strip().lower()
    servidor_valor = servidor_imap.strip() or "imap.gmail.com"
    asunto_valor = " ".join(asunto_filtro.split())
    remitentes_valor = ", ".join(separar_remitentes(remitentes_permitidos)) or None
    if not direccion_valor:
        return _renderizar_casilla_pedidos(request, error="Falta la dirección de la casilla.", status_code=400)
    if not asunto_valor:
        return _renderizar_casilla_pedidos(
            request,
            error='Falta el filtro de asunto (ej. "Pedido Dia"): sin él no se lee nada del buzón.',
            status_code=400,
        )

    try:
        if casilla_id.strip():
            actualizar_casilla_pedidos(int(casilla_id), direccion_valor, servidor_valor, cliente_id, asunto_valor, remitentes_valor)
            mensaje = "Casilla actualizada."
        else:
            crear_casilla_pedidos(direccion_valor, servidor_valor, cliente_id, asunto_valor, remitentes_valor)
            mensaje = "Casilla guardada. Cuando la clave esté en Railway, activala y probá con Revisar ahora."
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"No se pudo guardar la casilla: {error_db}") from error_db

    return _redirigir_a_casilla(mensaje=mensaje)


def _fecha_activacion_desde_form(texto: str):
    """La fecha de activación del form (datetime-local), en hora argentina. Vacía = ahora. Inválida = None."""
    texto = texto.strip()
    if not texto:
        return datetime.now(ARGENTINA)
    try:
        valor = datetime.fromisoformat(texto)
    except ValueError:
        return None
    if valor.tzinfo is None:
        valor = valor.replace(tzinfo=ARGENTINA)
    return valor


@app.post("/sistema/casilla-pedidos/{casilla_id}/activar")
def activar_casilla_pedidos_ruta(request: Request, casilla_id: int, fecha_activacion: str = Form("")):
    """Prende la lectura. Solo se miran correos POSTERIORES a la fecha de activación (default: ahora)."""
    fecha_valor = _fecha_activacion_desde_form(fecha_activacion)
    if fecha_valor is None:
        return _renderizar_casilla_pedidos(request, error="La fecha de activación no es válida.", status_code=400)
    try:
        activar_casilla_pedidos(casilla_id, fecha_valor)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"No se pudo activar la casilla: {error_db}") from error_db
    return _redirigir_a_casilla(mensaje="Casilla activada. Probá la conexión con Revisar ahora.")


@app.post("/sistema/casilla-pedidos/{casilla_id}/desactivar")
def desactivar_casilla_pedidos_ruta(casilla_id: int):
    try:
        desactivar_casilla_pedidos(casilla_id)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"No se pudo desactivar la casilla: {error_db}") from error_db
    return _redirigir_a_casilla(mensaje="Casilla desactivada: no se revisa más hasta que la vuelvas a activar.")


@app.post("/sistema/casilla-pedidos/{casilla_id}/fecha-activacion")
def cambiar_fecha_activacion_ruta(request: Request, casilla_id: int, fecha_activacion: str = Form("")):
    """Corrige a mano desde cuándo se miran los correos (p. ej. atrasarla para releer un día)."""
    fecha_valor = _fecha_activacion_desde_form(fecha_activacion)
    if fecha_valor is None:
        return _renderizar_casilla_pedidos(request, error="La fecha de activación no es válida.", status_code=400)
    try:
        cambiar_fecha_activacion_casilla(casilla_id, fecha_valor)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"No se pudo cambiar la fecha: {error_db}") from error_db
    return _redirigir_a_casilla(mensaje="Fecha de activación cambiada: la próxima revisión mira desde ahí.")


@app.post("/sistema/casilla-pedidos/{casilla_id}/auto-confirmar")
def auto_confirmar_casilla_ruta(casilla_id: int, valor: str = Form("")):
    """El toggle de auto-confirmar (tramo 2: confirmar solo el pedido con todos los candados cerrados y que no reemplaza a nadie)."""
    activar = valor.strip() == "si"
    try:
        fijar_auto_confirmar_casilla(casilla_id, activar)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"No se pudo cambiar auto-confirmar: {error_db}") from error_db
    if activar:
        return _redirigir_a_casilla(mensaje="Auto-confirmar prendido: la revisión automática (en el horario configurado de la casilla) confirma solo el pedido leído por estructura con todos los renglones identificados — todo lo demás queda pendiente para revisar a mano.")
    return _redirigir_a_casilla(mensaje="Auto-confirmar apagado: todos los mails quedan pendientes para confirmar a mano.")


@app.post("/sistema/casilla-pedidos/{casilla_id}/horario")
def cambiar_horario_revision_ruta(
    request: Request,
    casilla_id: int,
    revision_desde: str = Form(""),
    revision_hasta: str = Form(""),
    revision_cada_minutos: str = Form(""),
):
    """El horario de la revisión automática de ESTA casilla: desde, hasta y cada cuántos minutos.

    Todo en hora argentina, como el resto del sistema. La ventana tiene
    que ser válida (desde antes que hasta) y la cadencia razonable (5 a
    240 minutos) — sin eso no se guarda nada.
    """
    try:
        desde = time.fromisoformat(revision_desde.strip())
        hasta = time.fromisoformat(revision_hasta.strip())
    except ValueError:
        return _renderizar_casilla_pedidos(request, error="El horario de revisión no es válido.", status_code=400)
    try:
        cada_minutos = int(revision_cada_minutos.strip())
    except ValueError:
        return _renderizar_casilla_pedidos(request, error="Los minutos entre chequeos no son válidos.", status_code=400)

    if desde >= hasta:
        return _renderizar_casilla_pedidos(
            request, error="La hora de inicio tiene que ser anterior a la de fin.", status_code=400
        )
    if not 5 <= cada_minutos <= 240:
        return _renderizar_casilla_pedidos(
            request, error="Los minutos entre chequeos tienen que estar entre 5 y 240.", status_code=400
        )

    try:
        guardar_horario_revision_casilla(casilla_id, desde, hasta, cada_minutos)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"No se pudo guardar el horario: {error_db}") from error_db
    return _redirigir_a_casilla(
        mensaje=f"Horario guardado: se revisa de {desde.strftime('%H:%M')} a {hasta.strftime('%H:%M')} cada {cada_minutos} minutos (hora argentina)."
    )


def _revision_manual_de_casilla(casilla: dict) -> dict:
    """La revisión a mano de UNA casilla ya validada: conecta, registra lo nuevo y cuenta.

    El mismo circuito para "Revisar ahora" de Sistema y "Buscar pedido" de
    Armar Pedido. Devuelve {"error": texto o None, "resultado": lo del
    buzón o None, "nuevos": int, "ya_registrados": int}; un error de
    conexión queda registrado en la casilla, como siempre.
    """
    clave = clave_casilla_configurada()
    remitentes = separar_remitentes(casilla["remitentes_permitidos"])
    try:
        resultado = revisar_casilla(
            casilla["direccion"], clave, casilla["servidor_imap"], casilla["fecha_activacion"],
            casilla["asunto_filtro"], remitentes,
        )
    except ErrorCasilla as error_casilla:
        try:
            registrar_revision_casilla(casilla["id"], error=str(error_casilla))
        except Exception:
            logger.exception("No se pudo registrar el error de revisión de la casilla %s", casilla["id"])
        return {"error": str(error_casilla), "resultado": None, "nuevos": 0, "ya_registrados": 0}

    try:
        nuevos = 0
        ya_registrados = 0
        for mail in resultado["mails"]:
            mail_id = registrar_mail_pedido(
                casilla["id"],
                casilla["cliente_id"],
                mail["message_id"],
                mail["remitente"],
                mail["asunto"],
                mail["recibido_el"],
                mail["cuerpo_crudo"],
                mail["cuerpo_texto"],
            )
            if mail_id is None:
                ya_registrados += 1
            else:
                nuevos += 1
        registrar_revision_casilla(casilla["id"])
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Se leyó el buzón pero falló el registro en la base: {error_db}") from error_db
    return {"error": None, "resultado": resultado, "nuevos": nuevos, "ya_registrados": ya_registrados}


@app.post("/sistema/casilla-pedidos/{casilla_id}/revisar")
def revisar_casilla_ahora_ruta(request: Request, casilla_id: int):
    """Revisar ahora: conecta al buzón en solo lectura, registra lo nuevo y CUENTA lo que vio.

    El detalle del mensaje es a propósito: "N mails desde la activación, M
    de remitentes permitidos" delata al toque un filtro de remitente mal
    escrito ("hay mails pero ninguno pasa el filtro") o el IMAP
    deshabilitado por el administrador de Workspace — hoy, no mañana a las
    15:00.
    """
    try:
        casilla = obtener_casilla_pedidos(casilla_id)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db
    if casilla is None:
        raise HTTPException(status_code=404, detail="Casilla no encontrada")

    if clave_casilla_configurada() is None:
        return _redirigir_a_casilla(
            error=f"Falta la clave de la casilla: cargá la variable {CLAVE_CASILLA_ENV_VAR} en Railway (clave de aplicación de Gmail) y redeployá."
        )
    if casilla["fecha_activacion"] is None:
        return _redirigir_a_casilla(error="La casilla no tiene fecha de activación: activala primero.")
    if not (casilla["asunto_filtro"] or "").strip():
        return _redirigir_a_casilla(
            error='Falta el filtro de asunto (ej. "Pedido Dia"): configuralo en Editar configuración antes de revisar.'
        )
    remitentes = separar_remitentes(casilla["remitentes_permitidos"])

    revision = _revision_manual_de_casilla(casilla)
    if revision["error"] is not None:
        return _redirigir_a_casilla(error=f"La casilla no se pudo revisar: {revision['error']}")
    resultado = revision["resultado"]
    nuevos = revision["nuevos"]
    ya_registrados = revision["ya_registrados"]

    # El detalle por filtro es para AFINAR: cuántos había, cuántos pasaron
    # el remitente (si está configurado) y cuántos contienen el asunto.
    partes = [
        f"{resultado['total_desde']} mail{'s' if resultado['total_desde'] != 1 else ''} desde la activación"
    ]
    if remitentes:
        partes.append(f"{resultado['candidatos']} de remitentes permitidos")
    partes.append(
        f"{resultado['con_asunto']} con el asunto (“{casilla['asunto_filtro']}”)"
    )
    partes.append(f"{ya_registrados} ya registrado{'s' if ya_registrados != 1 else ''}")
    partes.append(f"{nuevos} nuevo{'s' if nuevos != 1 else ''} por confirmar")
    mensaje = f"Conectado OK a {casilla['direccion']} — " + ", ".join(partes) + "."

    if remitentes and resultado["total_desde"] > 0 and resultado["candidatos"] == 0:
        mensaje += " Ojo: hay mails en el buzón pero ninguno pasa el filtro de remitente — revisá que esté bien escrito, o dejalo vacío para no filtrar por remitente."
    elif resultado["candidatos"] > 0 and resultado["con_asunto"] == 0:
        mensaje += " Ojo: hay mails pero ninguno contiene ese asunto — si esperabas ver el pedido, afiná el filtro de asunto."
    return _redirigir_a_casilla(mensaje=mensaje)


@app.post("/deposito/pedido/armar/buscar-pedido")
def buscar_pedido_en_casilla_ruta(
    cliente_id: str = Form(""),
    fecha: str = Form(""),
    sucursal: str = Form(""),
):
    """"Buscar pedido" de Armar Pedido: fuerza la revisión de la casilla sin pasar por Sistema.

    Si el que arma no ve el pedido del día, lo trae él mismo: hace LO
    MISMO que "Revisar ahora" (misma conexión en solo lectura, mismo
    registro) sobre las casillas activas del cliente, y VUELVE a la
    pantalla de Armar donde estaba, con el aviso de qué encontró. Un mail
    nuevo queda pendiente y se ve ahí mismo para confirmarlo.
    """
    try:
        cliente_id_valor = int(cliente_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Cliente inválido")

    def _volver_a_armar(aviso: str):
        parametros: dict = {"cliente_id": cliente_id_valor}
        if fecha.strip():
            parametros["fecha"] = fecha.strip()
        if sucursal.strip():
            parametros["sucursal"] = sucursal.strip()
        parametros["aviso"] = aviso
        return RedirectResponse(url=f"/deposito/pedido/armar?{urlencode(parametros)}", status_code=303)

    if clave_casilla_configurada() is None:
        return _volver_a_armar(
            f"No se pudo revisar la casilla: falta la clave ({CLAVE_CASILLA_ENV_VAR}) en Railway — avisale al que administra Sistema."
        )

    try:
        casillas = [
            c for c in listar_casillas_pedidos()
            if c["cliente_id"] == cliente_id_valor
            and c["activa"]
            and c["fecha_activacion"] is not None
            and (c["asunto_filtro"] or "").strip()
        ]
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db
    if not casillas:
        return _volver_a_armar(
            "Este cliente no tiene ninguna casilla activa y configurada para buscar pedidos: se configura en Sistema → Casilla de Pedidos."
        )

    nuevos = 0
    errores = []
    for casilla in casillas:
        revision = _revision_manual_de_casilla(casilla)
        if revision["error"] is not None:
            errores.append(revision["error"])
        else:
            nuevos += revision["nuevos"]

    if errores and not nuevos:
        return _volver_a_armar(f"La casilla no se pudo revisar: {errores[0]}")
    if nuevos:
        aviso = (
            f"Casilla revisada: llegó 1 mail nuevo por confirmar — está abajo, en \"Mails de pedido por confirmar\"."
            if nuevos == 1
            else f"Casilla revisada: llegaron {nuevos} mails nuevos por confirmar — están abajo, en \"Mails de pedido por confirmar\"."
        )
        if errores:
            aviso += f" Ojo: otra casilla no se pudo revisar: {errores[0]}"
        return _volver_a_armar(aviso)
    return _volver_a_armar("Casilla revisada: sin novedades (ningún mail nuevo).")


# ---------------------------------------------------------------------------
# Revisión automática de casillas (tramo 2): un task que corre solo entre las
# 12:00 y las 15:00 argentinas, hace lo mismo que "Revisar ahora" por cada
# casilla activa, y (si la casilla lo tiene prendido) intenta auto-confirmar
# los mails NUEVOS con todos los candados cerrados. Todo lo que falla queda registrado en
# la casilla o en el mail — nunca en un log que nadie mira.
# ---------------------------------------------------------------------------

# Defaults del horario de revisión (los mismos que el DEFAULT de las
# columnas revision_* de casillas_pedidos): cada casilla puede cambiarlos
# desde su pantalla. VENTANA_REVISION_HASTA además sigue siendo el corte
# fijo de la alerta de pedidos faltantes ("hoy cuenta desde las 15:00").
VENTANA_REVISION_DESDE = time(12, 0)
VENTANA_REVISION_HASTA = time(15, 0)
MINUTOS_ENTRE_REVISIONES = 15
# El bucle mira el reloj cada minuto y decide POR CASILLA si le toca
# revisar (según su ventana y su cadencia): así un "desde las 12:00"
# arranca 12:00 en punto, no cuando caiga un tick global.
SEGUNDOS_TICK_REVISION = 60
# Margen antes del cierre de la ventana de cada casilla desde el que
# Auditoría alerta si HOY no hubo ninguna revisión exitosa. Antes de eso
# no se alerta — quedan ticks por delante para recuperarse solo.
MARGEN_ALERTA_CASILLA = timedelta(hours=1)


def _horario_revision_de(casilla: dict) -> tuple[time, time, int]:
    """El horario configurado de la casilla, con los defaults de siempre si el dato falta."""
    return (
        casilla.get("revision_desde") or VENTANA_REVISION_DESDE,
        casilla.get("revision_hasta") or VENTANA_REVISION_HASTA,
        casilla.get("revision_cada_minutos") or MINUTOS_ENTRE_REVISIONES,
    )


def _casilla_en_ventana(casilla: dict, ahora) -> bool:
    desde, hasta, _ = _horario_revision_de(casilla)
    return desde <= ahora.time() < hasta


def _le_toca_revision(casilla: dict, ahora) -> bool:
    """Si ya pasó la cadencia configurada desde el último INTENTO (éxito o error).

    Se mira la base, no memoria del proceso: sobrevive reinicios del
    server sin ametrallar el buzón, y un error también espera su turno
    (el reintento es al próximo intervalo, no al minuto siguiente).
    """
    _, _, cada_minutos = _horario_revision_de(casilla)
    intentos = [casilla.get("ultima_revision_el"), casilla.get("ultimo_error_el")]
    ultimo_intento = max((i for i in intentos if i is not None), default=None)
    if ultimo_intento is None:
        return True
    return ahora - ultimo_intento >= timedelta(minutes=cada_minutos)


def _intentar_auto_confirmar(mail: dict) -> bool:
    """Confirma solo el mail que cuadra al CIEN por ciento, sin tocar nada dudoso. Devuelve si confirmó.

    CINCO candados, en orden (cualquiera que no cierra deja el mail
    PENDIENTE para revisar a mano, sin marcar nada):
    1. El mail está pendiente (un error previo se revisa a mano).
    2. La fecha sale del ASUNTO y es creíble (sin fecha, o a más de 5
       días de la llegada, no se adivina).
    3. Lo leyó el parser por ESTRUCTURA — la IA nunca confirma sola.
    4. Todos los renglones identificados por código o nombre exacto
       (una sugerencia difusa es una decisión humana).
    5. No hay pedido vigente para esa fecha (reemplazar es decisión humana).

    El candado de "sumas exactas contra el total declarado" SE SACÓ a
    pedido del dueño (24/08/2026): Día se equivoca sumando sus propios
    totales, y contra lecturas rotas la red real es el candado 3 — el
    parser estructural lee la grilla validada entera o devuelve None. El
    total declarado se sigue guardando como dato, sin frenar nada.
    """
    if mail["estado"] != "pendiente":
        return False

    fecha_llegada = mail["recibido_el"].astimezone(ARGENTINA).date()
    fecha_valor = fecha_de_pedido_del_asunto(mail["asunto"], fecha_llegada)
    if fecha_valor is None or abs((fecha_valor - fecha_llegada).days) > 5:
        return False

    texto = texto_del_mail_guardado(mail["cuerpo_crudo"], mail["cuerpo_texto"])
    texto_recortado = recortar_bloque_de_empresa(texto, NOMBRE_EMPRESA)
    datos = parsear_pedido_estructurado(texto_recortado)
    if datos is None:
        return False

    fichas = listar_fichas_por_cliente(mail["cliente_id"])
    alias_por_codigo, alias_por_nombre = _alias_de_fichas(fichas)
    bloque = _elegir_bloque_pedido(datos.get("bloques") or [], alias_por_codigo)
    if bloque is None:
        return False

    renglones = _armar_renglones_pedido_desde_bloque(bloque, fichas, alias_por_codigo, alias_por_nombre)
    if not renglones:
        return False
    if any(r["articulo_id"] is None or r["match_por"] not in ("codigo", "nombre") for r in renglones):
        return False

    sucursales = _sucursales_desde_bloque(bloque, renglones)

    if obtener_pedido_vigente(mail["cliente_id"], fecha_valor) is not None:
        return False

    # Todos los candados cerraron: se guarda con la MISMA expansión de
    # renglones que el confirmar a mano (por sucursal con cantidad; un
    # renglón sin ninguna cantidad se guarda igual, sin sucursal y en 0).
    #
    # OJO AL COPIAR CAMPOS ACÁ. Esta expansión rearma el dict en vez de
    # reusar el que ya trae _armar_renglones_pedido_desde_bloque, así que
    # es una SEGUNDA COPIA de "qué campos tiene un renglón" — la primera
    # es el POST de la revisión a mano. Del 27/08 al 04/09/2026 esta copia
    # se olvidó de ficha_id: el matcheo resolvía la ficha, derivaba el
    # artículo de ella, guardaba el artículo y tiraba la ficha. Nueve días
    # de pedidos sin ficha, sin un solo error, porque el CHECK de la tabla
    # prohíbe "ficha sin artículo" y permite justo lo contrario.
    # Si mañana el renglón gana un campo, HAY QUE AGREGARLO ACÁ TAMBIÉN.
    renglones_guardar = []
    for renglon in renglones:
        con_cantidad = False
        for nombre_sucursal, cantidad in renglon["cantidades"].items():
            cantidad_valor = _numero_pedido_o_none(cantidad)
            if cantidad_valor is None or cantidad_valor == 0:
                continue
            con_cantidad = True
            renglones_guardar.append(
                {
                    "sucursal": nombre_sucursal,
                    "articulo_id": renglon["articulo_id"],
                    "ficha_id": renglon["ficha_id"],
                    "texto_codigo": renglon["texto_codigo"],
                    "texto_descripcion": renglon["texto_descripcion"],
                    "cantidad": cantidad_valor,
                }
            )
        if not con_cantidad:
            renglones_guardar.append(
                {
                    "sucursal": None,
                    "articulo_id": renglon["articulo_id"],
                    "ficha_id": renglon["ficha_id"],
                    "texto_codigo": renglon["texto_codigo"],
                    "texto_descripcion": renglon["texto_descripcion"],
                    "cantidad": 0,
                }
            )

    pedido_id = crear_pedido(
        mail["cliente_id"],
        fecha_valor,
        "mail",
        texto,
        sucursales,
        renglones_guardar,
        mail_message_id=mail["message_id"],
        recibido_el=mail["recibido_el"],
    )
    marcar_mail_pedido_confirmado(mail["id"], pedido_id, motivo="Confirmado automáticamente")
    try:
        marcar_lectura_mail_pedido(mail["id"], leido_con_ia=False)
    except Exception:
        logger.exception("No se pudo grabar el método de lectura del mail %s auto-confirmado", mail["id"])
    logger.info("Mail %s auto-confirmado: pedido %s del %s", mail["id"], pedido_id, fecha_valor.isoformat())
    return True


def _revisar_casilla_automaticamente(casilla: dict) -> None:
    """Una casilla del tick: mismo circuito que Revisar ahora, con TODO error registrado en la casilla."""
    clave = clave_casilla_configurada()
    if clave is None:
        registrar_revision_casilla(
            casilla["id"],
            error=f"Falta la clave de la casilla: cargá la variable {CLAVE_CASILLA_ENV_VAR} en Railway y redeployá.",
        )
        return
    if not (casilla["asunto_filtro"] or "").strip():
        registrar_revision_casilla(
            casilla["id"],
            error='Falta el filtro de asunto (ej. "Pedido Dia"): sin él no se lee nada del buzón.',
        )
        return

    try:
        resultado = revisar_casilla(
            casilla["direccion"], clave, casilla["servidor_imap"], casilla["fecha_activacion"],
            casilla["asunto_filtro"], separar_remitentes(casilla["remitentes_permitidos"]),
        )
    except Exception as error_casilla:
        try:
            registrar_revision_casilla(casilla["id"], error=f"La revisión automática falló: {error_casilla}")
        except Exception:
            logger.exception("No se pudo registrar el error de revisión de la casilla %s", casilla["id"])
        return

    try:
        nuevos = []
        for mail in resultado["mails"]:
            mail_id = registrar_mail_pedido(
                casilla["id"],
                casilla["cliente_id"],
                mail["message_id"],
                mail["remitente"],
                mail["asunto"],
                mail["recibido_el"],
                mail["cuerpo_crudo"],
                mail["cuerpo_texto"],
            )
            if mail_id is not None:
                nuevos.append(mail_id)
        registrar_revision_casilla(casilla["id"], automatica=True)
    except Exception as error_db:
        try:
            registrar_revision_casilla(casilla["id"], error=f"Se leyó el buzón pero falló el registro en la base: {error_db}")
        except Exception:
            logger.exception("No se pudo registrar el error de revisión de la casilla %s", casilla["id"])
        return

    if not casilla["auto_confirmar"]:
        return
    # Auto-confirmar SOLO los nuevos de esta pasada: los pendientes viejos
    # ya están esperando a una persona y no se les cambia el destino.
    for mail_id in nuevos:
        try:
            mail = obtener_mail_pedido(mail_id)
            if mail is not None:
                _intentar_auto_confirmar(mail)
        except Exception:
            logger.exception("Auto-confirmar falló para el mail %s — queda pendiente para revisar a mano", mail_id)


def revisar_casillas_activas(ahora=None) -> int:
    """El tick de la revisión automática: cada casilla ACTIVA a la que le toca según SU horario.

    Cada casilla tiene su propia ventana (desde/hasta) y su cadencia (cada
    N minutos), configurables en su pantalla. El tick corre cada minuto y
    decide por casilla: en ventana Y con el intervalo cumplido desde el
    último intento → se revisa; si no, se saltea sin tocar nada.
    Devuelve cuántas casillas revisó (para el log del tick).
    """
    if ahora is None:
        ahora = datetime.now(ARGENTINA)
    try:
        casillas = listar_casillas_pedidos()
    except Exception:
        logger.exception("La revisión automática no pudo leer las casillas configuradas")
        return 0
    revisadas = 0
    for casilla in casillas:
        if not casilla["activa"] or casilla["fecha_activacion"] is None:
            continue
        if not _casilla_en_ventana(casilla, ahora) or not _le_toca_revision(casilla, ahora):
            continue
        _revisar_casilla_automaticamente(casilla)
        revisadas += 1
    return revisadas


# Tope duro por tick: si un IMAP se cuelga (connect en blackhole, DNS
# eterno — el bug del 25/08: el timeout de imaplib es por operación y por
# IP, no cubre el peor caso), el tick se abandona y el bucle SIGUE. El
# hilo colgado no se puede matar, pero termina solo cuando sus sockets
# vencen — lo que no puede pasar nunca más es que bloquee el bucle.
SEGUNDOS_TIMEOUT_TICK = 120

# Tope para el recálculo de alertas. Corre dos veces por día, así que demorar
# un tick de casilla como mucho ese rato, dos veces al día, no molesta a nadie
# — y con tope, una alerta colgada no puede dejar el bucle parado para siempre.
SEGUNDOS_TIMEOUT_ALERTAS = 180


def _recalcular_alertas_si_toca() -> None:
    """Recalcula las alertas si la foto más nueva ya pasó las HORAS_RECALCULO.

    Va colgado del bucle que ya existe en vez de tener uno propio: un solo
    lugar que puede morirse, con la disciplina de timeout y excepciones ya
    puesta. Y el criterio es "cuán vieja está la foto", no "¿ya corrí el turno
    de las 6?": así se autocorrige después de una caída, sin depender de que
    el reloj coincida con nada.
    """
    estado = listar_estado_alertas()
    if not hay_que_recalcular(estado, datetime.now(ARGENTINA)):
        return
    logger.info("Las alertas están vencidas: recalculando")
    recalcular(ALERTAS)


async def _bucle_revision_casillas() -> None:
    """El task de fondo: mira el reloj cada minuto y revisa la casilla a la que le toca.

    La revisión corre en un hilo (asyncio.to_thread) con TIMEOUT
    ENVOLVENTE, y cada tick deja DOS rastros aunque no revise nada: el
    latido en la base (revision_tick, lo que muestra Sistema) y una
    línea de log (lo que se mira en Railway) — "sin novedades" y "el
    bucle está muerto" no pueden volver a verse iguales. Cualquier
    excepción se loguea y el bucle SIGUE.
    """
    logger.info(
        "El bucle de revisión de casillas arrancó (tick cada %s segundos, tope %s segundos por tick)",
        SEGUNDOS_TICK_REVISION, SEGUNDOS_TIMEOUT_TICK,
    )
    while True:
        try:
            await asyncio.to_thread(registrar_tick_revision)
        except Exception:
            logger.exception("No se pudo sellar el latido del tick — se sigue igual")
        try:
            revisadas = await asyncio.wait_for(
                asyncio.to_thread(revisar_casillas_activas), timeout=SEGUNDOS_TIMEOUT_TICK
            )
            logger.info("Tick de revisión de casillas: %s revisada(s)", revisadas)
        except asyncio.TimeoutError:
            logger.error(
                "El tick de revisión superó los %s segundos (¿IMAP colgado?) y se abandonó — el bucle sigue",
                SEGUNDOS_TIMEOUT_TICK,
            )
        except Exception:
            logger.exception("El bucle de revisión de casillas falló — sigue en el próximo ciclo")

        # Las alertas, en el mismo bucle. Con su propio try: que el recálculo
        # falle no puede llevarse puesta la revisión de la casilla, ni al revés.
        try:
            await asyncio.wait_for(
                asyncio.to_thread(_recalcular_alertas_si_toca), timeout=SEGUNDOS_TIMEOUT_ALERTAS
            )
        except asyncio.TimeoutError:
            logger.error(
                "El recálculo de alertas superó los %s segundos y se abandonó — el bucle sigue",
                SEGUNDOS_TIMEOUT_ALERTAS,
            )
        except Exception:
            logger.exception("El recálculo de alertas falló — sigue en el próximo ciclo")

        await asyncio.sleep(SEGUNDOS_TICK_REVISION)


@app.post("/sistema/casilla-pedidos/mails/{mail_id}/ignorar")
def ignorar_mail_pedido_ruta(mail_id: int):
    """Marca un mail pendiente como ignorado (no era un pedido). El registro queda, nada desaparece."""
    try:
        marcar_mail_pedido_ignorado(mail_id, "Marcado a mano desde Sistema")
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"No se pudo ignorar el mail: {error_db}") from error_db
    return _redirigir_a_casilla(mensaje="Mail marcado como ignorado.")


@app.get("/deposito/pedido/mails/{mail_id}/revisar")
def revisar_mail_pedido_ruta(request: Request, mail_id: int):
    """Precarga la revisión de Cargar Pedido desde el cuerpo guardado de un mail pendiente.

    Mismo circuito que pegar el texto a mano: la IA lee el cuerpo (ya
    pasado a texto), la revisión muestra el control cruzado y al guardar
    el mail queda confirmado y el pedido nace con origen 'mail'.
    """
    try:
        mail = obtener_mail_pedido(mail_id)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db
    if mail is None:
        raise HTTPException(status_code=404, detail="Mail no encontrado")
    if mail["estado"] not in ("pendiente", "error"):
        return _redirigir_a_casilla(error="Ese mail ya fue procesado: no hay nada para confirmar.")

    # SIEMPRE desde el cuerpo crudo guardado, con la conversión vigente:
    # una mejora del parser o de la conversión aplica retroactivamente a
    # cualquier mail ya registrado, sin migrar nada.
    texto = texto_del_mail_guardado(mail["cuerpo_crudo"], mail["cuerpo_texto"])
    texto_recortado = recortar_bloque_de_empresa(texto, NOMBRE_EMPRESA)

    # Camino principal: el parser por estructura — las cantidades salen de
    # la tabla tal cual, sin IA. Si no puede, cae a la IA, y ese fallback
    # queda GRABADO en el mail (alerta de Auditoría "leídos con IA"): si
    # Día cambia el formato, se ve ese mismo día.
    datos = parsear_pedido_estructurado(texto_recortado)
    metodo_lectura = "estructura" if datos is not None else "ia"
    try:
        marcar_lectura_mail_pedido(mail_id, leido_con_ia=metodo_lectura == "ia")
    except Exception:
        logger.exception("No se pudo grabar el método de lectura del mail %s", mail_id)

    if datos is None:
        try:
            datos = extraer_pedido_de_texto(texto_recortado)
        except Exception as error_lector:
            # La falla queda GRABADA en el mail (y alimenta la alerta de
            # Auditoría): cuando la revisión corra sola a las 12:00, un error
            # de lectura no se puede perder en un redirect que nadie vio.
            try:
                marcar_mail_pedido_error(mail_id, f"La lectura falló: {error_lector}")
            except Exception:
                logger.exception("No se pudo registrar el error de lectura en el mail %s", mail_id)
            return _redirigir_a_casilla(error=f"No se pudo leer el pedido del mail: {error_lector}")

    # La fecha del pedido la manda el ASUNTO ("Pedido Dia 22-08 Sabado":
    # el mail del mediodía es para el día siguiente); la llegada es solo
    # el respaldo. Se recalcula en CADA relectura — nunca queda congelada.
    fecha_llegada = mail["recibido_el"].astimezone(ARGENTINA).date()
    fecha_valor = fecha_de_pedido_del_asunto(mail["asunto"], fecha_llegada)
    aviso_fecha = None
    if fecha_valor is None:
        fecha_valor = fecha_llegada
        aviso_fecha = (
            f"El asunto del mail no trae fecha: el pedido quedó con la fecha de llegada "
            f"({fecha_llegada.strftime('%d/%m/%Y')}). Fijate que sea la que corresponde antes de guardar."
        )
    elif abs((fecha_valor - fecha_llegada).days) > 5:
        aviso_fecha = (
            f"Ojo: la fecha del asunto ({fecha_valor.strftime('%d/%m/%Y')}) está lejos de la llegada del mail "
            f"({fecha_llegada.strftime('%d/%m/%Y')}) — puede ser un error de tipeo de Día. Revisala antes de guardar."
        )
    try:
        contexto = _contexto_revision_pedido(
            mail["cliente_id"], mail["cliente_nombre"], fecha_valor, datos, texto, [],
            mail=mail, metodo_lectura=metodo_lectura, aviso_fecha=aviso_fecha,
        )
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    if contexto is None:
        return _redirigir_a_casilla(
            error="La IA no encontró renglones de pedido en ese mail. Cargalo a mano desde Cargar Pedido, o marcalo como ignorado."
        )
    return templates.TemplateResponse(request, "deposito_pedido_revision.html", contexto)


if __name__ == "__main__":
    import uvicorn

    puerto = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=puerto)

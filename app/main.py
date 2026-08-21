"""Aplicación FastAPI: pantallas de la app y prueba de conexión a la base de datos.

El motor de costeo y las fichas en core/ no se tocan. El lector de comandas
(core/lector_comandas.py) ahora sí se conecta, en la carga de compras por foto.
"""

import base64
import hashlib
import hmac
import io
import json
import logging
import os
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from PIL import Image, ImageOps

from app.costeo import agrupar_para_negociar, calcular_listado_para_negociar_precios, calcular_objetivos_de_compra
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
    buscar_ingresos_deposito,
    buscar_retiros,
    cambiar_articulo_de_ficha,
    contar_compras_buscadas,
    contar_ingresos_deposito,
    contar_pedidos_con_renglones_sin_identificar,
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
    contar_compras_sin_precio_viejas,
    contar_recepciones_pendientes_viejas,
    contar_retiros_pendientes_viejos,
    contar_senas_pendientes_viejas,
    contar_stock_vacios_negativos,
    corregir_recepcion_compra,
    crear_articulo,
    crear_cliente,
    crear_compra,
    crear_pedido,
    crear_ajuste_vacios,
    crear_compras_de_comanda,
    crear_conteo_vacios,
    crear_envase,
    crear_ficha,
    crear_tipo_envase_puesto,
    crear_vacio_devuelto,
    crear_vacio_recibido,
    desactivar_articulo,
    desactivar_cliente,
    desactivar_cliente_puesto,
    desactivar_proveedor_puesto,
    desactivar_tipo_envase_puesto,
    deshacer_no_ingresado_compra,
    deshacer_retiro_compra,
    eliminar_compra,
    eliminar_compras_del_dia_por_proveedor,
    eliminar_ficha,
    guardar_disponible,
    guardar_precios_cliente,
    agregar_foto_guia,
    agregar_foto_pedido,
    asignar_articulo_a_renglon_pedido,
    borrar_foto_guia,
    borrar_foto_pedido,
    guardar_alias_en_ficha,
    obtener_pedido_vigente,
    limpiar_foto_ruta_de_compras,
    listar_fotos_de_guia,
    listar_fotos_pedido,
    listar_ajustes_vacios_por_rango,
    listar_aprendizaje_articulos_por_proveedor,
    listar_articulos,
    listar_articulos_sin_ficha,
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
    listar_fichas_por_cliente,
    listar_renglones_pedido,
    listar_sucursales_pedido,
    listar_fotos_para_limpiar,
    listar_precios_anteriores_por_cliente,
    listar_precios_vigentes_por_cliente,
    listar_proveedores,
    listar_proveedores_puesto,
    listar_senas_pendientes,
    listar_senas_resueltas,
    listar_tipos_envase_puesto,
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
    obtener_uso_storage_bucket,
    recepcionar_compra,
    rechazar_compra,
    registrar_costo_envase,
    stock_vacios,
    stock_vacios_de_tipo,
)
from core.conceptos_cliente import calcular_cambio_de_utilidad, calcular_cambios_de_tasas
from core.exportar_compras import generar_excel_listado_compras, generar_pdf_listado_compras
from core.exportar_disponibles import generar_excel_disponibles
from core.exportar_precios import generar_excel_lista_precios, generar_pdf_lista_precios
from core.exportar_ingresos import generar_excel_ingresos_deposito, generar_pdf_ingresos_deposito
from core.exportar_retiros import generar_excel_listado_retiros, generar_pdf_listado_retiros
from core.exportar_vacios import (
    generar_excel_movimientos_vacios,
    generar_excel_stock_vacios,
    generar_pdf_movimientos_vacios,
    generar_pdf_stock_vacios,
)
from core.precios_venta import calcular_cambios_de_precios
from core.lector_archivos import comprimir_pdf, imagenes_desde_pdf, texto_desde_excel
from core.lector_comandas import (
    TEXTOS_PLACEHOLDER_LECTOR,
    extraer_comanda,
    extraer_listado_consolidado,
    extraer_listado_precios_de_imagenes,
    extraer_listado_precios_de_texto,
    extraer_pedido_de_texto,
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

logger = logging.getLogger(__name__)

app = FastAPI()
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
    "facturacion": {
        "nombre": "Facturación",
        "url": "/facturacion",
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
templates.env.globals["ICONO_INICIO"] = _ICONO_INICIO
templates.env.globals["NOMBRE_EMPRESA"] = NOMBRE_EMPRESA
templates.env.globals["TIPO_RETIRO_DEFAULT"] = TIPO_RETIRO_DEFAULT
# Callable a propósito (se evalúa en cada render, no al importar): el botón
# Bloquear solo aparece si hay clave configurada.
templates.env.globals["clave_control_activa"] = lambda: _clave_control_puesto() is not None


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
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    return templates.TemplateResponse(
        request,
        "cliente_formulario.html",
        {
            "modo": "edicion",
            "cliente": cliente,
            "tasas_suma": _filas_desde_conceptos_guardados(conceptos["tasas_suma"]),
            "tasas_resta": _filas_desde_conceptos_guardados(conceptos["tasas_resta"]),
            "utilidad_pct": conceptos["utilidad_pct"],
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
        {"clientes": clientes, "cliente_id": cliente_id, "fichas": fichas, "error": error, "aviso": aviso},
    )


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
        articulos = listar_articulos_sin_ficha(cliente_id)
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
        articulos = listar_articulos_sin_ficha(cliente_id)
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
        articulos = listar_articulos_sin_ficha(cliente_id)
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
        # Para "Cambiar artículo": solo artículos SIN ficha de este cliente,
        # así no se puede pisar una existente sin querer.
        articulos_para_cambio = listar_articulos_sin_ficha(ficha["cliente_id"])
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
    try:
        eliminar_ficha(ficha_id)
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
    cancelaron y cuántas no se pudieron). El cartel de "compras sin
    precio" es el mismo aviso que en /comercial: el comprador tiene
    pendiente cargar precios. Es un aviso, no algo crítico para poder
    navegar — si la consulta del conteo falla, se pisa en 0 (sin cartel)
    en vez de romper toda la pantalla por algo accesorio.
    """
    try:
        compras_sin_precio = contar_compras_sin_precio()
    except Exception:
        compras_sin_precio = 0

    return templates.TemplateResponse(
        request, "compras.html", {"compras_sin_precio": compras_sin_precio, "aviso": aviso}
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
        proveedores = listar_proveedores()
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


@app.get("/compras/nueva/manual")
def ver_nueva_compra_manual(request: Request, error: str | None = None):
    try:
        proveedores = listar_proveedores()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    return templates.TemplateResponse(
        request,
        "compra_proveedor_manual.html",
        {"proveedores": proveedores, "error": error},
    )


@app.get("/compras/nueva/foto-una")
def ver_nueva_compra_foto(request: Request, error: str | None = None):
    return templates.TemplateResponse(request, "compra_leer_foto.html", {"error": error})


@app.get("/compras/nueva")
def ver_nueva_compra(request: Request, proveedor_id: int | None = None, error: str | None = None):
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
        },
    )


@app.post("/compras/nueva/proveedor")
def elegir_proveedor_compra(request: Request, codigo_puesto: str = Form(""), nombre: str = Form("")):
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
            "compra_proveedor_manual.html",
            {"proveedores": proveedores, "error": error},
            status_code=400,
        )

    try:
        proveedor_id = obtener_o_crear_proveedor_por_codigo(codigo_valor, nombre_valor)
    except Exception as error_db:
        try:
            proveedores = listar_proveedores()
        except Exception:
            proveedores = []
        return templates.TemplateResponse(
            request,
            "compra_proveedor_manual.html",
            {"proveedores": proveedores, "error": f"No se pudo guardar el proveedor: {error_db}"},
            status_code=500,
        )

    return RedirectResponse(url=f"/compras/nueva?proveedor_id={proveedor_id}", status_code=303)


@app.post("/compras/nueva")
def agregar_compra(
    request: Request,
    proveedor_id: int = Form(...),
    accion: str = Form("agregar"),
    articulo_id: str = Form(""),
    cantidad_cajones: str = Form(""),
    contenido_por_cajon: str = Form(""),
    importe: str = Form(""),
    sena: str = Form(""),
    tipo_retiro: str = Form(""),
):
    renglon_vacio = not any(
        campo.strip() for campo in (articulo_id, cantidad_cajones, contenido_por_cajon, importe, sena, tipo_retiro)
    )
    if accion == "terminar" and renglon_vacio:
        return RedirectResponse(url="/compras/buscar", status_code=303)

    try:
        proveedor = obtener_proveedor(proveedor_id)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    if proveedor is None:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")

    error, valores = _validar_compra_nueva_form(
        articulo_id, cantidad_cajones, contenido_por_cajon, importe, sena, tipo_retiro
    )

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
        proveedor_id = obtener_o_crear_proveedor_por_codigo(codigo_valor, nombre_valor)

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

    return RedirectResponse(url=f"/compras/nueva?proveedor_id={proveedor_id}", status_code=303)


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
    request: Request, compra_id: int, *, error: str | None = None, status_code: int = 200
):
    try:
        compra = obtener_detalle_compra(compra_id)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    if compra is None:
        raise HTTPException(status_code=404, detail="Compra no encontrada")

    return templates.TemplateResponse(
        request,
        "compra_corregir_recepcion.html",
        {"compra": compra, "error": error},
        status_code=status_code,
    )


@app.get("/compras/{compra_id}/corregir-recepcion")
def ver_corregir_recepcion_compra(request: Request, compra_id: int):
    """Formulario para corregir los valores reales de una compra ya recepcionada (ej. error de tipeo en Depósito).

    Bloqueada la corrección en sí en corregir_recepcion_compra, pero la
    pantalla se muestra igual (con un aviso) si alguien llega acá con una
    compra que no está recepcionada — mismo criterio que el resto de la
    app: nunca una pantalla en blanco sin explicar por qué.
    """
    return _renderizar_pantalla_corregir_recepcion(request, compra_id)


@app.post("/compras/{compra_id}/corregir-recepcion")
def corregir_recepcion_compra_ruta(
    request: Request,
    compra_id: int,
    cantidad_cajones_real: str = Form(""),
    cantidad_total_real: str = Form(""),
    cantidad_cajones_rechazada: str = Form(""),
    motivo_rechazo: str = Form(""),
):
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
def ver_precios_consultar(request: Request, cliente_id: str | None = None, fecha: str | None = None, articulo_id: str | None = None):
    """Consulta de precios vigentes de un cliente a una fecha (todos, o uno puntual). Solo lectura.

    Mismo patrón de selector que /fichas y /negociar: sin cliente_id en la
    URL, se muestra solo el selector. "Vigente a una fecha" usa
    listar_precios_vigentes_por_cliente tal cual (mismo patrón vigente_desde
    que ya usa la Rutina A) — acá solo se cruza con los artículos del
    cliente para mostrar el nombre y, si se pidió, filtrar a uno puntual.
    """
    cliente_id = _id_opcional_desde_query(cliente_id)
    articulo_id = _id_opcional_desde_query(articulo_id)

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

    nombre_por_articulo = {ficha["articulo_id"]: ficha["articulo_nombre"] for ficha in fichas}
    filas = [
        {
            "articulo_id": precio["articulo_id"],
            "articulo_nombre": nombre_por_articulo.get(precio["articulo_id"], f"Artículo #{precio['articulo_id']}"),
            "precio": precio["precio"],
        }
        for precio in precios_vigentes
    ]
    if articulo_id is not None:
        filas = [fila for fila in filas if fila["articulo_id"] == articulo_id]
    filas.sort(key=lambda fila: fila["articulo_nombre"])

    return templates.TemplateResponse(
        request,
        "precios_consulta.html",
        {
            "clientes": clientes,
            "cliente_id": cliente_id,
            "cliente_nombre": cliente["nombre"],
            "articulos_cliente": fichas,
            "articulo_id": articulo_id,
            "articulo_nombre_actual": nombre_por_articulo.get(articulo_id) if articulo_id is not None else None,
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
    — no calcula nada nuevo. es_hoy determina si corresponde resaltar
    "precio nuevo": solo cuando se exporta la fecha de HOY, nunca para una
    fecha pasada. precio_anterior (ver listar_precios_anteriores_por_cliente)
    solo lo usa la columna "Precio anterior" del Excel (el PDF no la
    muestra) — un artículo sin precio anterior cargado queda en None.
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

    hoy = _hoy_argentina()
    es_hoy = fecha_consulta == hoy

    filas = [
        {
            "articulo_nombre": nombre_por_articulo.get(precio["articulo_id"], f"Artículo #{precio['articulo_id']}"),
            "grupo": grupo_por_articulo.get(precio["articulo_id"]),
            "precio": precio["precio"],
            "precio_anterior": precio_anterior_por_articulo.get(precio["articulo_id"]),
            "unidad": unidad_por_articulo.get(precio["articulo_id"]),
            "es_nuevo": es_hoy and precio.get("vigente_desde") == hoy,
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
        filas, es_hoy = _armar_filas_exportacion_precios(cliente["id"], fecha_valor)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    pdf_bytes = generar_pdf_lista_precios(cliente["nombre"], fecha_valor, filas, es_hoy, NOMBRE_EMPRESA)
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
        archivo_bytes = generar_pdf_lista_precios(cliente["nombre"], hoy, filas, es_hoy, NOMBRE_EMPRESA)
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
            {"articulo_id": fila["articulo_id"], "precio_original": precio_original, "precio_nuevo": precio_nuevo}
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

    precio_por_articulo = {precio["articulo_id"]: precio["precio"] for precio in precios_vigentes}
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
    articulos_cliente = [
        {
            "articulo_id": ficha["articulo_id"],
            "articulo_nombre": ficha["articulo_nombre"],
            "precio_vigente": precio_por_articulo.get(ficha["articulo_id"]),
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
            "articulos_cliente": articulos_cliente,
            **contexto_negociacion,
        },
    )


def _leer_pendientes_del_form(form) -> list[dict]:
    """Lee del form oculto (armado por JS con los pendientes de la sesión) un precio nuevo por artículo.

    Cada pendiente viaja como "pendiente_precio_<articulo_id>" (el nuevo) y
    "pendiente_original_<articulo_id>" (el vigente al elegirlo, para que
    calcular_cambios_de_precios no genere una fila si no cambió nada) — no
    hace falta un índice porque los pendientes ya vienen sin duplicados por
    artículo (el navegador se encarga de eso).
    """
    filas = []
    prefijo = "pendiente_precio_"
    for clave in form.keys():
        if not clave.startswith(prefijo):
            continue
        try:
            articulo_id = int(clave[len(prefijo) :])
        except ValueError:
            continue
        filas.append(
            {
                "articulo_id": articulo_id,
                "original_texto": str(form.get(f"pendiente_original_{articulo_id}", "")).strip(),
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

    nombre_por_articulo = {ficha["articulo_id"]: ficha["articulo_nombre"] for ficha in fichas}

    filas_crudas = _leer_pendientes_del_form(form)
    for fila in filas_crudas:
        fila["articulo_nombre"] = nombre_por_articulo.get(fila["articulo_id"], f"Artículo #{fila['articulo_id']}")

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
    datos: dict, fichas_cliente: list[dict], articulos_existentes: list[dict], precio_por_articulo: dict
) -> list[dict]:
    """Arma los renglones sugeridos (artículo matcheado + precio leído) a partir de lo que devolvió la IA.

    Acota el catálogo candidato del matcheo a los artículos con ficha de
    ESTE cliente — su propio nombre_cliente (fichas_logistica) es el alias
    más preciso que existe, y no tiene sentido sugerir un artículo que ni
    siquiera tiene ficha para él. Si el cliente todavía no tiene ninguna
    ficha, se cae al catálogo completo como respaldo. Sin aprendizaje por
    cliente todavía (se pasa vacío) — el que existe hoy es por proveedor,
    para comandas.
    """
    conversiones_cliente = [f for f in fichas_cliente if f.get("nombre_cliente")]
    candidatos_articulo = (
        [{"id": f["articulo_id"], "nombre": f["articulo_nombre"]} for f in fichas_cliente]
        if fichas_cliente
        else articulos_existentes
    )

    renglones = []
    for item in datos.get("items") or []:
        texto_leido = item.get("articulo") or ""
        articulo_id_sugerido = adivinar_articulo(texto_leido, {}, candidatos_articulo, conversiones_cliente)
        renglones.append(
            {
                "texto_leido": texto_leido,
                "articulo_id": articulo_id_sugerido,
                "precio_original": precio_por_articulo.get(articulo_id_sugerido)
                if articulo_id_sugerido is not None
                else None,
                "precio_nuevo": _numero_o_none(item.get("precio")),
                "advertencia": item.get("confianza") == "baja" or articulo_id_sugerido is None,
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
        articulos_existentes = listar_articulos()
        precios_vigentes = listar_precios_vigentes_por_cliente(cliente_id_valor, _hoy_argentina())
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    precio_por_articulo = {precio["articulo_id"]: precio["precio"] for precio in precios_vigentes}
    renglones = _armar_renglones_precios_desde_datos_leidos(
        datos, fichas_cliente, articulos_existentes, precio_por_articulo
    )

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

    articulos_para_select = (
        [
            {
                "articulo_id": f["articulo_id"],
                "articulo_nombre": f["articulo_nombre"],
                "precio_vigente": precio_por_articulo.get(f["articulo_id"]),
            }
            for f in fichas_cliente
        ]
        if fichas_cliente
        else [
            {"articulo_id": a["id"], "articulo_nombre": a["nombre"], "precio_vigente": precio_por_articulo.get(a["id"])}
            for a in articulos_existentes
        ]
    )

    return templates.TemplateResponse(
        request,
        "precios_revision_foto.html",
        {
            "cliente_id": cliente_id_valor,
            "cliente_nombre": cliente["nombre"],
            "articulos": articulos_para_select,
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
    nombre_por_articulo = {f["articulo_id"]: f["articulo_nombre"] for f in fichas}

    filas_crudas = []
    for indice in range(cantidad_renglones):
        if str(form.get(f"item_{indice}_descartar", "")).strip():
            continue
        articulo_id_texto = str(form.get(f"item_{indice}_articulo_id", "")).strip()
        if not articulo_id_texto:
            continue
        try:
            articulo_id = int(articulo_id_texto)
        except ValueError:
            continue
        filas_crudas.append(
            {
                "articulo_id": articulo_id,
                "articulo_nombre": nombre_por_articulo.get(articulo_id, f"Artículo #{articulo_id}"),
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

    El cartel de "compras sin precio" es un aviso, no algo crítico para
    poder navegar — si la consulta del conteo falla, se pisa en 0 (sin
    cartel) en vez de romper toda la pantalla por algo accesorio.
    """
    try:
        compras_sin_precio = contar_compras_sin_precio()
    except Exception:
        compras_sin_precio = 0

    return templates.TemplateResponse(request, "comercial.html", {"compras_sin_precio": compras_sin_precio})


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
    return templates.TemplateResponse(request, "logistica.html", {})


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
        proveedores = listar_proveedores()
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
    return templates.TemplateResponse(request, "deposito.html", {"aviso": aviso})


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
        proveedor_id = obtener_o_crear_proveedor_por_codigo(codigo_valor, nombre_valor)
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

    return RedirectResponse(url=f"/deposito/ingresar?proveedor_id={proveedor_id}", status_code=303)


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

    Devuelve una lista de {"guia_id", "proveedor_nombre", "proveedor_codigo_puesto", "compras"}.
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
def deshacer_no_ingreso_compra_ruta(request: Request, compra_id: int):
    """Vuelve una compra marcada "No ingresó" a pendiente — tarjeta efímera o panel "Procesados hoy"."""
    try:
        deshacer_no_ingresado_compra(compra_id)
    except ValueError as error_bloqueo:
        return _renderizar_pantalla_recepcion(request, error=str(error_bloqueo), status_code=400)
    except Exception as error_db:
        return _renderizar_pantalla_recepcion(request, error=f"No se pudo deshacer: {error_db}", status_code=500)

    return RedirectResponse(url="/deposito/recepcion", status_code=303)


@app.get("/gerencia")
def ver_gerencia(request: Request):
    """Hub de Gerencia: por ahora solo Auditoría; acá se van colgando los tableros del dueño."""
    return templates.TemplateResponse(request, "gerencia.html", {})


def _alertas_auditoria() -> list[dict]:
    """Los controles del tablero de Auditoría, como LISTA de definiciones.

    Agregar el control número diez tiene que ser sumar una entrada acá
    (título + conteo + link al detalle), no tocar el diseño de la
    pantalla. Cada control devuelve casos y el dato que más dice: de
    cuándo es el caso más viejo. Todos son consultas de conteo livianas
    (corren en cada carga de la pantalla): apoyarse en índices.
    """
    hoy = _hoy_argentina()
    # "Más de 48 horas" con la granularidad real del dato (fecha_operacion
    # es una fecha, sin hora): compras de anteayer para atrás.
    limite = hoy - timedelta(days=2)
    # Ventanas de las alertas nuevas, elegidas a mano y fáciles de tocar.
    limite_senas = hoy - timedelta(days=7)
    ventana_comprados = hoy - timedelta(days=7)

    sin_precio = contar_compras_sin_precio_viejas(limite)
    retiros = contar_retiros_pendientes_viejos(limite)
    recepciones = contar_recepciones_pendientes_viejas(limite)
    negativos = contar_stock_vacios_negativos()
    incotizables = contar_articulos_comprados_incotizables(ventana_comprados, hoy)
    senas = contar_senas_pendientes_viejas(limite_senas)
    pedidos_sin_identificar = contar_pedidos_con_renglones_sin_identificar()

    return [
        {
            "titulo": "Compras sin precio hace más de 48 horas",
            "casos": sin_precio["casos"],
            "mas_viejo": sin_precio["mas_viejo"],
            "url": "/compras/pendientes",
            "texto_link": "Ver en Compras sin precio",
        },
        {
            "titulo": "Mercadería sin retirar hace más de 48 horas",
            "casos": retiros["casos"],
            "mas_viejo": retiros["mas_viejo"],
            "url": "/logistica/consultar?" + urlencode({
                "fecha_desde": (retiros["mas_viejo"] or limite).isoformat(),
                "fecha_hasta": limite.isoformat(),
                "estado": "pendiente",
            }),
            "texto_link": "Ver en Consultar Retiros",
        },
        {
            "titulo": "Mercadería sin recepcionar hace más de 48 horas",
            "casos": recepciones["casos"],
            "mas_viejo": recepciones["mas_viejo"],
            "url": "/deposito/recepcion",
            "texto_link": "Ver en Recepción",
        },
        {
            "titulo": "Stock de vacíos negativo",
            "casos": negativos,
            "mas_viejo": None,
            "url": "/puesto/envases/stock",
            "texto_link": "Ver en Stock del Sistema",
        },
        {
            "titulo": "Artículos comprados sin ficha logística o sin precio de venta (últimos 7 días)",
            "casos": incotizables,
            "mas_viejo": None,
            "url": "/fichas",
            "texto_link": "Ver en Fichas Logísticas",
        },
        {
            "titulo": "Señas de vacíos pendientes hace más de 7 días",
            "casos": senas["casos"],
            "mas_viejo": senas["mas_viejo"],
            "url": "/puesto/envases/pendientes",
            "texto_link": "Ver en Pendientes de Pago",
        },
        {
            "titulo": "Pedidos con renglones sin identificar",
            "casos": pedidos_sin_identificar["casos"],
            "mas_viejo": pedidos_sin_identificar["mas_viejo"],
            "url": "/deposito/pedido",
            "texto_link": "Ver en Pedido",
        },
    ]


@app.get("/gerencia/auditoria")
def ver_auditoria(request: Request):
    """Tablero de cosas que están mal, de un pantallazo: solo aparecen los controles con casos."""
    try:
        alertas = _alertas_auditoria()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    con_casos = [a for a in alertas if a["casos"] > 0]
    return templates.TemplateResponse(
        request,
        "gerencia_auditoria.html",
        {"alertas": con_casos, "controles_corridos": len(alertas)},
    )


@app.get("/facturacion")
def ver_facturacion(request: Request):
    """Hub de Facturación: por ahora, solo Ingresos a Depósito."""
    return templates.TemplateResponse(request, "facturacion.html", {})


ESTADOS_FILTRO_INGRESOS_VALIDOS = {"recepcionado", "rechazado", "no_ingresado", "todas"}

ETIQUETAS_ESTADO_INGRESO = {
    "recepcionado": "Recepcionada",
    "rechazado": "Rechazo total",
    "no_ingresado": "No ingresó",
}


def _grupos_ingresos_deposito(ingresos: list[dict]) -> tuple[list[dict], dict]:
    """Agrupa los ingresos por proveedor con su subtotal (así se factura), y arma el total general.

    Por fila: total = cantidad_cajones_real × importe (el precio es por
    bulto). Sin precio cargado no hay total — la fila queda marcada
    (sin_precio) porque es lo que falta completar antes de facturar; una
    rechazada total o no ingresada sin precio NO se marca (no se paga,
    no hay nada que completar). Las cantidades son SIEMPRE las reales
    que pesó/contó Depósito, nunca las del comprador.
    """
    grupos: list[dict] = []
    grupos_por_proveedor: dict[str, dict] = {}
    total_general = 0.0
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
                "sin_precio": 0,
            }
            grupos_por_proveedor[clave] = grupo
            grupos.append(grupo)

        cajones = float(ingreso["cantidad_cajones_real"]) if ingreso["cantidad_cajones_real"] is not None else None
        importe = float(ingreso["importe"]) if ingreso["importe"] is not None else None
        total = cajones * importe if cajones is not None and importe is not None else None
        sin_precio = importe is None and ingreso["estado"] == "recepcionado"

        if total is not None:
            grupo["subtotal"] += total
            total_general += total
        if sin_precio:
            grupo["sin_precio"] += 1
            cantidad_sin_precio += 1

        etiqueta = ETIQUETAS_ESTADO_INGRESO.get(ingreso["estado"], ingreso["estado"])
        if ingreso["estado"] == "recepcionado" and ingreso["cantidad_cajones_rechazada"] is not None:
            etiqueta = "Rechazo parcial"

        grupo["filas"].append(
            {**ingreso, "total": total, "sin_precio": sin_precio, "estado_etiqueta": etiqueta}
        )

    totales = {"total_general": total_general, "cantidad_sin_precio": cantidad_sin_precio}
    return grupos, totales


@app.get("/facturacion/ingresos")
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
        "facturacion_ingresos.html",
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


@app.get("/facturacion/ingresos/exportar-pdf")
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


@app.get("/facturacion/ingresos/exportar-excel")
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
    return templates.TemplateResponse(request, "puesto.html", {})


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


def _renderizar_pantalla_tipos_envase_puesto(request: Request, *, error=None, aviso=None, status_code: int = 200):
    try:
        tipos = listar_tipos_envase_puesto()
        # Proveedores del PUESTO, nunca los de Compras: circuitos separados.
        proveedores = listar_proveedores_puesto()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    return templates.TemplateResponse(
        request,
        "vacios_tipos.html",
        {"tipos": tipos, "proveedores": proveedores, "error": error, "aviso": aviso},
        status_code=status_code,
    )


@app.get("/puesto/envases/tipos")
def ver_tipos_envase_puesto(request: Request, aviso: str | None = None):
    """ABM de tipos de cajón por proveedor (lo carga el dueño). Un proveedor sin tipos no aparece en Vacíos."""
    if not _acceso_control_valido(request):
        return _pantalla_clave_control(request)
    return _renderizar_pantalla_tipos_envase_puesto(request, aviso=aviso)


@app.post("/puesto/envases/tipos/nuevo")
def crear_tipo_envase_puesto_ruta(request: Request, proveedor_id: str = Form(""), nombre: str = Form("")):
    if not _acceso_control_valido(request):
        return RedirectResponse(url="/puesto/envases/tipos", status_code=303)
    nombre_limpio = re.sub(r"\s+", " ", nombre).strip()
    if not nombre_limpio:
        return _renderizar_pantalla_tipos_envase_puesto(
            request, error="El nombre del tipo de envase es obligatorio.", status_code=400
        )
    if not proveedor_id.strip().isdigit():
        return _renderizar_pantalla_tipos_envase_puesto(request, error="Elegí un proveedor.", status_code=400)

    try:
        crear_tipo_envase_puesto(int(proveedor_id), nombre_limpio)
    except Exception as error_db:
        return _renderizar_pantalla_tipos_envase_puesto(
            request, error=f"No se pudo crear el tipo de envase: {error_db}", status_code=500
        )

    parametros = urlencode({"aviso": f"Tipo de envase '{nombre_limpio}' cargado."})
    return RedirectResponse(url=f"/puesto/envases/tipos?{parametros}", status_code=303)


@app.post("/puesto/envases/tipos/{tipo_id}/baja")
def dar_de_baja_tipo_envase_puesto_ruta(request: Request, tipo_id: int):
    if not _acceso_control_valido(request):
        return RedirectResponse(url="/puesto/envases/tipos", status_code=303)
    try:
        desactivar_tipo_envase_puesto(tipo_id)
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
        fila = dict(conteo, diferencia=conteo["cantidad"] - conteo["stock_sistema"])
        # Con diferencia, botón directo a la pantalla de ajuste, precargada
        # con este conteo (la cantidad final se calcula ahí contra el stock
        # ACTUAL, no contra esta foto — ver ver_ajustar_stock_vacios).
        if fila["diferencia"] != 0:
            fila["query_ajuste"] = urlencode(
                {
                    "proveedor_id": conteo["proveedor_id"],
                    "tipo_envase_id": conteo["tipo_envase_id"],
                    "contado": conteo["cantidad"],
                    "stock_conteo": conteo["stock_sistema"],
                    "fecha_conteo": conteo["creado_en"].date().isoformat(),
                }
            )
        filas.append(fila)

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

        precarga = {
            "proveedor_id": proveedor_id,
            "tipo_envase_id": tipo_envase_id,
            "cantidad": contado_valor - stock_actual,
            "motivo": f"Ajuste a lo contado: conteo del {fecha_conteo or '?'} ({contado_valor} contados)",
        }
        # El aviso de "el stock se movió desde el conteo": solo si la foto
        # del conteo (stock_conteo) difiere del stock actual.
        if stock_conteo is not None and stock_conteo.strip().lstrip("-").isdigit() and int(stock_conteo) != stock_actual:
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


@app.post("/puesto/envases/proveedores/{proveedor_id}/baja")
def dar_de_baja_proveedor_puesto_ruta(request: Request, proveedor_id: int):
    if not _acceso_control_valido(request):
        return RedirectResponse(url="/puesto/envases/proveedores", status_code=303)
    try:
        desactivar_proveedor_puesto(proveedor_id)
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
    """Los alias del cliente, normalizados, para el matcheo determinista: codigo -> articulo_id y nombre -> articulo_id."""
    por_codigo = {
        normalizar_texto(f["codigo_cliente"]): f["articulo_id"] for f in fichas if f.get("codigo_cliente")
    }
    por_nombre = {
        normalizar_texto(f["nombre_cliente"]): f["articulo_id"] for f in fichas if f.get("nombre_cliente")
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

    Cada renglón conserva SIEMPRE el texto crudo del mail y las cantidades
    por sucursal tal como vinieron. Sin match, articulo_id None: en la
    revisión va arriba, marcado, para asignar a mano.
    """
    candidatos = [{"id": f["articulo_id"], "nombre": f["articulo_nombre"]} for f in fichas]
    conversiones = [f for f in fichas if f.get("nombre_cliente")]

    renglones = []
    for renglon in bloque.get("renglones") or []:
        codigo = (renglon.get("codigo") or "").strip()
        descripcion = (renglon.get("descripcion") or "").strip()

        articulo_id = alias_por_codigo.get(normalizar_texto(codigo)) if codigo else None
        match_por = "codigo" if articulo_id is not None else None
        if articulo_id is None and descripcion:
            articulo_id = alias_por_nombre.get(normalizar_texto(descripcion))
            match_por = "nombre" if articulo_id is not None else None
        if articulo_id is None and descripcion:
            articulo_id = adivinar_articulo(descripcion, {}, candidatos, conversiones)
            match_por = "sugerencia" if articulo_id is not None else None

        cantidades = renglon.get("cantidades") or {}
        renglones.append(
            {
                "texto_codigo": codigo or None,
                "texto_descripcion": descripcion or None,
                "cantidades": {s: c for s, c in cantidades.items() if c is not None},
                "articulo_id": articulo_id,
                "match_por": match_por,
                "advertencia": articulo_id is None or match_por == "sugerencia" or renglon.get("confianza") == "baja",
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


def _fecha_pedido_o_hoy(fecha_texto: str | None):
    hoy = _hoy_argentina()
    if not fecha_texto:
        return hoy
    try:
        return date.fromisoformat(fecha_texto)
    except ValueError:
        return hoy


def _sumas_leidas_por_sucursal(renglones: list[dict]) -> dict:
    """El control cruzado: cuántos bultos suman los renglones guardados, por sucursal."""
    sumas: dict = {}
    for renglon in renglones:
        if renglon["sucursal"] is None:
            continue
        sumas[renglon["sucursal"]] = sumas.get(renglon["sucursal"], 0.0) + float(renglon["cantidad"])
    return sumas


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

    sumas = _sumas_leidas_por_sucursal(renglones)
    descuadres = []
    for sucursal in sucursales:
        declarado = sucursal.get("total_bultos_declarado")
        suma = sumas.get(sucursal["sucursal"], 0.0)
        sucursal["suma_leida"] = suma
        if declarado is not None and float(declarado) != suma:
            diferencia = float(declarado) - suma
            detalle = f"faltan {_formatear_numero(abs(diferencia))}" if diferencia > 0 else f"sobran {_formatear_numero(abs(diferencia))}"
            descuadres.append(
                f"Leí {_formatear_numero(suma)} bultos para {sucursal['sucursal']} pero el mail dice "
                f"{_formatear_numero(declarado)} — {detalle}."
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
            "descuadres": descuadres,
            "sin_identificar": sin_identificar,
            "renglones_por_sucursal": renglones_por_sucursal,
            "fotos": fotos,
            "articulos_cliente": [{"id": f["articulo_id"], "nombre": f["articulo_nombre"]} for f in fichas],
        }
    )
    return templates.TemplateResponse(request, "deposito_pedido.html", contexto)


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
def leer_pedido_pegado(
    request: Request,
    cliente_id: int = Form(...),
    fecha: str = Form(""),
    texto: str = Form(""),
):
    """Lee el texto pegado con la IA, se queda con el bloque de ESTA empresa y arma la revisión."""
    fecha_valor = _fecha_pedido_o_hoy(fecha)
    try:
        clientes = listar_clientes()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db
    cliente = next((c for c in clientes if c["id"] == cliente_id), None)
    if cliente is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    if not texto.strip():
        return templates.TemplateResponse(
            request,
            "deposito_pedido_cargar.html",
            {"clientes": clientes, "cliente_id": cliente_id, "fecha": fecha_valor.isoformat(),
             "error": "Pegá el texto del mail antes de leer."},
            status_code=400,
        )

    try:
        datos = extraer_pedido_de_texto(texto)
    except Exception as error_lector:
        return templates.TemplateResponse(
            request,
            "deposito_pedido_cargar.html",
            {"clientes": clientes, "cliente_id": cliente_id, "fecha": fecha_valor.isoformat(),
             "error": f"No se pudo leer el pedido: {error_lector}"},
            status_code=500,
        )

    try:
        fichas = listar_fichas_por_cliente(cliente_id)
        pedido_vigente = obtener_pedido_vigente(cliente_id, fecha_valor)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    alias_por_codigo, alias_por_nombre = _alias_de_fichas(fichas)
    bloque = _elegir_bloque_pedido(datos.get("bloques") or [], alias_por_codigo)
    if bloque is None:
        return templates.TemplateResponse(
            request,
            "deposito_pedido_cargar.html",
            {"clientes": clientes, "cliente_id": cliente_id, "fecha": fecha_valor.isoformat(),
             "error": "No se encontró ningún renglón de pedido en el texto. Fijate que hayas pegado el cuerpo del mail."},
            status_code=400,
        )

    renglones = _armar_renglones_pedido_desde_bloque(bloque, fichas, alias_por_codigo, alias_por_nombre)
    sucursales = [
        {
            "sucursal": (s.get("sucursal") or "").strip(),
            "orden_compra": (str(s.get("orden_compra")).strip() if s.get("orden_compra") is not None else None),
            "total_bultos_declarado": _numero_pedido_o_none(s.get("total_bultos")),
        }
        for s in bloque.get("sucursales") or []
        if (s.get("sucursal") or "").strip()
    ]
    # Sucursales que aparecen en cantidades pero no vinieron declaradas
    # arriba: se agregan igual (sin OC ni total) — nada se pierde.
    declaradas = {s["sucursal"] for s in sucursales}
    for renglon in renglones:
        for nombre_sucursal in renglon["cantidades"]:
            if nombre_sucursal not in declaradas:
                sucursales.append({"sucursal": nombre_sucursal, "orden_compra": None, "total_bultos_declarado": None})
                declaradas.add(nombre_sucursal)

    return templates.TemplateResponse(
        request,
        "deposito_pedido_revision.html",
        {
            "cliente_id": cliente_id,
            "cliente_nombre": cliente["nombre"],
            "fecha": fecha_valor.isoformat(),
            "fecha_mostrar": fecha_valor.strftime("%d/%m/%Y"),
            "empresa_bloque": bloque.get("empresa") or "",
            "sucursales": sucursales,
            "renglones": renglones,
            "articulos_cliente": [{"id": f["articulo_id"], "nombre": f["articulo_nombre"]} for f in fichas],
            "texto_original": texto,
            "pedido_vigente": pedido_vigente,
        },
    )


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
        articulo_id_texto = str(form.get(f"renglon_{indice}_articulo_id", "")).strip()
        articulo_id = int(articulo_id_texto) if articulo_id_texto else None

        if articulo_id is not None and str(form.get(f"renglon_{indice}_guardar_alias", "")).strip():
            alias_a_guardar.append((articulo_id, texto_codigo, texto_descripcion))

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
            "texto",
            texto_original,
            sucursales,
            renglones,
            reemplaza_a_pedido_id=pedido_vigente["id"] if pedido_vigente else None,
        )
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"No se pudo guardar el pedido: {error_db}") from error_db

    # Los alias se guardan después del pedido (si fallan, el pedido ya
    # está a salvo): solo completan campos vacíos de la ficha.
    for articulo_id, texto_codigo, texto_descripcion in alias_a_guardar:
        try:
            guardar_alias_en_ficha(cliente_id, articulo_id, texto_codigo, texto_descripcion)
        except Exception:
            logger.exception("No se pudo guardar el alias en la ficha (cliente %s, articulo %s)", cliente_id, articulo_id)

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
    articulo_id: str = Form(""),
    guardar_alias: str = Form(""),
    texto_codigo: str = Form(""),
    texto_descripcion: str = Form(""),
):
    """Asigna a mano un renglón "sin identificar" desde la pantalla del pedido (y opcionalmente guarda el alias)."""
    try:
        articulo_id_valor = int(articulo_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Elegí el artículo.")

    try:
        asignar_articulo_a_renglon_pedido(renglon_id, articulo_id_valor)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"No se pudo asignar el artículo: {error_db}") from error_db

    if guardar_alias.strip():
        try:
            guardar_alias_en_ficha(
                cliente_id, articulo_id_valor, texto_codigo.strip() or None, texto_descripcion.strip() or None
            )
        except Exception:
            logger.exception("No se pudo guardar el alias en la ficha (cliente %s, articulo %s)", cliente_id, articulo_id_valor)

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


if __name__ == "__main__":
    import uvicorn

    puerto = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=puerto)

"""Aplicación FastAPI: pantallas de la app y prueba de conexión a la base de datos.

El motor de costeo y las fichas en core/ no se tocan. El lector de comandas
(core/lector_comandas.py) ahora sí se conecta, en la carga de compras por foto.
"""

import base64
import io
import json
import logging
import os
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode

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
    aprender_articulo,
    buscar_compras,
    buscar_retiros,
    cerrar_disponible_generado,
    compra_tiene_cantidad_bloqueada,
    compra_tiene_deshacer_recepcion_bloqueado,
    compra_tiene_deshacer_retiro_bloqueado,
    compra_tiene_precio_bloqueado,
    contar_articulos,
    contar_compras_sin_precio,
    corregir_recepcion_compra,
    crear_articulo,
    crear_cliente,
    crear_compra,
    crear_envase,
    crear_ficha,
    desactivar_articulo,
    desactivar_cliente,
    deshacer_no_ingresado_compra,
    deshacer_retiro_compra,
    eliminar_compra,
    eliminar_compras_del_dia_por_proveedor,
    eliminar_ficha,
    guardar_disponible,
    guardar_precios_cliente,
    limpiar_foto_ruta_de_compras,
    listar_aprendizaje_articulos_por_proveedor,
    listar_articulos,
    listar_articulos_sin_ficha,
    listar_clientes,
    listar_compras_pendientes_recepcion,
    listar_compras_pendientes_retiro,
    listar_compras_por_fecha_y_proveedor,
    listar_compras_procesadas_hoy_recepcion,
    listar_compras_procesadas_hoy_retiro,
    listar_compras_sin_precio,
    listar_conceptos_editables_por_cliente,
    listar_detalle_disponible,
    listar_envases,
    listar_envases_con_costo,
    listar_historial_costos_envases,
    listar_fichas_por_cliente,
    listar_fotos_para_limpiar,
    listar_precios_anteriores_por_cliente,
    listar_precios_vigentes_por_cliente,
    listar_proveedores,
    listar_todas_las_conversiones,
    marcar_compra_cancelada,
    marcar_compra_no_ingresada,
    marcar_compra_retirada,
    obtener_articulo,
    obtener_borrador_disponible,
    obtener_cliente,
    obtener_compra,
    obtener_detalle_compra,
    obtener_ficha,
    obtener_o_crear_proveedor_por_codigo,
    obtener_proveedor,
    obtener_ultimo_disponible_cliente,
    obtener_uso_storage_bucket,
    recepcionar_compra,
    rechazar_compra,
    registrar_costo_envase,
)
from core.conceptos_cliente import calcular_cambio_de_utilidad, calcular_cambios_de_tasas
from core.exportar_compras import generar_excel_listado_compras, generar_pdf_listado_compras
from core.exportar_disponibles import generar_excel_disponibles
from core.exportar_precios import generar_excel_lista_precios, generar_pdf_lista_precios
from core.precios_venta import calcular_cambios_de_precios
from core.lector_archivos import imagenes_desde_pdf, texto_desde_excel
from core.lector_comandas import (
    TEXTOS_PLACEHOLDER_LECTOR,
    extraer_comanda,
    extraer_listado_consolidado,
    extraer_listado_precios_de_imagenes,
    extraer_listado_precios_de_texto,
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
    "rechazado": "Rechazado por calidad",
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
def ver_fichas(request: Request, cliente_id: int | None = None, error: str | None = None):
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
        {"clientes": clientes, "cliente_id": cliente_id, "fichas": fichas, "error": error},
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
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    return templates.TemplateResponse(
        request,
        "ficha_form.html",
        {
            "cliente_id": ficha["cliente_id"],
            "articulos": [],
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
def ver_compras(request: Request):
    """Botonera de entrada al módulo de compras.

    El cartel de "compras sin precio" es el mismo aviso que en /comercial:
    el comprador tiene pendiente cargar precios. Es un aviso, no algo
    crítico para poder navegar — si la consulta del conteo falla, se pisa
    en 0 (sin cartel) en vez de romper toda la pantalla por algo accesorio.
    """
    try:
        compras_sin_precio = contar_compras_sin_precio()
    except Exception:
        compras_sin_precio = 0

    return templates.TemplateResponse(request, "compras.html", {"compras_sin_precio": compras_sin_precio})


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
        compras = buscar_compras(fecha_desde_valor, fecha_hasta_valor, proveedor_id_valor, articulo_id_valor)
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
    """Descarta TODA la carga de hoy de este proveedor (incluso lo ya guardado con "Agregar artículo") y va a Buscar Compras.

    La confirmación la pide el navegador (confirm() antes de mandar el
    POST); acá no queda nada más por decidir: si llegó el POST, se borra
    lo que se pueda. No es silencioso: si algo quedó afuera (ya retirado o
    recepcionado), Buscar Compras lo va a mostrar en el aviso.
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

    query = urlencode(
        {"fecha_desde": hoy.isoformat(), "fecha_hasta": hoy.isoformat(), "proveedor_id": proveedor_id, "aviso": aviso}
    )
    return RedirectResponse(url=f"/compras/buscar?{query}", status_code=303)


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
    try:
        imagen_pil = Image.open(io.BytesIO(imagen))
        imagen_pil = ImageOps.exif_transpose(imagen_pil)
        imagen_pil = imagen_pil.convert("RGB")
        imagen_pil.thumbnail((LADO_MAXIMO_PREVIEW_FOTO, LADO_MAXIMO_PREVIEW_FOTO))
        buffer = io.BytesIO()
        imagen_pil.save(buffer, format="JPEG", quality=CALIDAD_PREVIEW_FOTO)
        preview_base64 = base64.standard_b64encode(buffer.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{preview_base64}"
    except Exception:
        return ""


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
            },
            status_code=400,
        )

    try:
        proveedor_id = obtener_o_crear_proveedor_por_codigo(codigo_valor, nombre_valor)

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
        for texto_leido, valores, articulo in renglones_a_guardar:
            total = valores["cantidad_cajones"] * valores["contenido_por_cajon"]
            if articulo["unidad_compra"] == "kilo":
                cantidad_kilos, cantidad_fraccion = total, None
            else:
                cantidad_kilos, cantidad_fraccion = None, total

            crear_compra(
                hoy,
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
            # Solo se aprende de texto REALMENTE leído de la comanda: ni de
            # renglones agregados a mano (texto vacío) ni de los placeholders
            # que el lector devuelve cuando no pudo leer el artículo — si no,
            # "completar articulo" queda asociado a un artículo cualquiera y
            # envenena las sugerencias futuras de ese proveedor.
            texto_aprendible = normalizar_texto(texto_leido)
            if texto_aprendible and texto_aprendible not in TEXTOS_PLACEHOLDER_LECTOR:
                aprender_articulo(proveedor_id, texto_aprendible, valores["articulo_id"])
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
    razon_precio = "fue rechazada por calidad" if estado == "rechazado" else "nunca ingresó al depósito"

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

    return RedirectResponse(url="/compras/buscar", status_code=303)


def _eliminar_compra_y_su_foto_si_corresponde(compra_id: int) -> None:
    """Borra una compra y, si esta era la última que usaba su foto, también el archivo del Storage.

    Borrar la foto es un extra: si falla (sin conexión, credencial mala,
    lo que sea), se loguea completo y se sigue igual — la compra ya se
    borró, una foto huérfana es un mal menor frente a no poder borrar
    nada. Si falla el borrado de la COMPRA en sí, esta función deja que
    la excepción se propague: eso sí lo tiene que ver quien llama.
    """
    foto_ruta_a_borrar = eliminar_compra(compra_id)
    if foto_ruta_a_borrar:
        try:
            borrar_foto_comanda(foto_ruta_a_borrar)
        except Exception:
            logger.exception(
                "No se pudo borrar de Supabase Storage la foto %s (la compra %s ya se borró igual)",
                foto_ruta_a_borrar,
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

    return RedirectResponse(url="/compras/buscar", status_code=303)


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

    if not compra.get("foto_ruta"):
        raise HTTPException(status_code=404, detail="Esta compra no tiene foto guardada")

    try:
        url_firmada = obtener_url_foto(compra["foto_ruta"])
    except Exception as error_storage:
        raise HTTPException(
            status_code=500, detail=f"No se pudo generar el link de la foto: {error_storage}"
        ) from error_storage

    return RedirectResponse(url=url_firmada, status_code=307)


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
        archivo_preview = _generar_data_uri_generico(bytes_archivo, MIME_POR_TIPO_ARCHIVO_PRECIOS[tipo_archivo])

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


def _renderizar_pantalla_sistema(request: Request, *, mensaje: str | None = None, error: str | None = None, status_code: int = 200):
    # El indicador de espacio y el botón de limpieza son informativos, no
    # bloqueantes: si fallan, la pantalla se muestra igual, sin esos datos
    # (uso_storage/cantidad_fotos_para_limpiar quedan en None y la
    # plantilla no los muestra).
    try:
        uso_storage = obtener_uso_storage_bucket(BUCKET_COMANDAS)
    except Exception:
        uso_storage = None

    try:
        cantidad_fotos_para_limpiar = len(listar_fotos_para_limpiar(_fecha_de_corte_limpieza_fotos()))
    except Exception:
        cantidad_fotos_para_limpiar = None

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
        retiros = buscar_retiros(
            fecha_desde_valor, fecha_hasta_valor, proveedor_id_valor, articulo_id_valor, tipo_valor, estado_valor
        )
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    # El total para liquidar: por fila, lo anotado al retirar si existe, si
    # no lo que cargó el comprador. Se desglosa para que se vea cuánto del
    # total es dato anotado y cuánto viene de la carga.
    total_bultos = 0.0
    total_anotados = 0.0
    total_del_comprador = 0.0
    filas = []
    for retiro in retiros:
        anotada = retiro["cantidad_cajones_retirada"]
        bultos = float(anotada) if anotada is not None else float(retiro["cantidad_cajones"])
        usa_anotada = anotada is not None
        total_bultos += bultos
        if usa_anotada:
            total_anotados += bultos
        else:
            total_del_comprador += bultos
        filas.append({**retiro, "bultos": bultos, "usa_anotada": usa_anotada})

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
            "total_bultos": total_bultos,
            "total_anotados": total_anotados,
            "total_del_comprador": total_del_comprador,
        },
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
        return "Los bultos rechazados tienen que ser menos que los llegados. Si rechazás todo, usá Rechazar por calidad.", None, None

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
    return _renderizar_en_construccion(
        request, "Gerencia", volver_url="/inicio", volver_texto="Volver a Inicio", sector="gerencia"
    )


@app.get("/facturacion")
def ver_facturacion(request: Request):
    return _renderizar_en_construccion(
        request, "Facturación", volver_url="/inicio", volver_texto="Volver a Inicio", sector="facturacion"
    )


@app.get("/puesto")
def ver_puesto(request: Request):
    return _renderizar_en_construccion(
        request, "Puesto", volver_url="/inicio", volver_texto="Volver a Inicio", sector="puesto"
    )


if __name__ == "__main__":
    import uvicorn

    puerto = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=puerto)

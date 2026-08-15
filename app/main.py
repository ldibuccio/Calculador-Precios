"""Aplicación FastAPI: pantallas de la app y prueba de conexión a la base de datos.

El motor de costeo y las fichas en core/ no se tocan. El lector de comandas
(core/lector_comandas.py) ahora sí se conecta, en la carga de compras por foto.
"""

import base64
import io
import logging
import re
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from PIL import Image

from app.costeo import (
    agrupar_para_negociar,
    calcular_listado_para_negociar_precios,
    calcular_precio_sugerido_desglosado,
)
from app.db import (
    actualizar_articulo,
    actualizar_cliente,
    actualizar_compra,
    actualizar_conversion,
    actualizar_ficha,
    actualizar_importe_compra,
    aprender_articulo,
    contar_articulos,
    crear_articulo,
    crear_cliente,
    crear_compra,
    crear_conversion,
    crear_ficha,
    desactivar_articulo,
    desactivar_cliente,
    eliminar_compra,
    eliminar_compras_del_dia_por_proveedor,
    eliminar_conversion,
    eliminar_ficha,
    listar_aprendizaje_articulos_por_proveedor,
    listar_articulos,
    listar_articulos_sin_ficha,
    listar_clientes,
    listar_compras_por_fecha_y_proveedor,
    listar_compras_por_rango_fechas,
    listar_compras_sin_precio,
    listar_conversiones_por_cliente,
    listar_envases_por_cliente,
    listar_fichas_por_cliente,
    listar_proveedores,
    listar_todas_las_conversiones,
    obtener_articulo,
    obtener_cliente,
    obtener_compra,
    obtener_conversion,
    obtener_ficha,
    obtener_o_crear_proveedor_por_codigo,
    obtener_proveedor,
)
from core.lector_comandas import extraer_comanda
from core.matcheo_comanda import adivinar_articulo, adivinar_proveedor, normalizar_texto
from core.storage import borrar_foto_comanda, obtener_url_foto, subir_foto_comanda

UNIDADES_VENTA_VALIDAS = {"kilo", "unidad", "cubeta"}
TIPOS_RETIRO_VALIDOS = {"Clark", "Granel", "Propia"}
ARGENTINA = timezone(timedelta(hours=-3))
REGEX_CODIGO_PUESTO = re.compile(r"^[NL][0-9]{2}P[0-9]{2}$")


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


def _formatear_porcentaje(valor) -> str:
    """Formatea una fracción (0.2548) como porcentaje con un decimal y coma decimal ("25,5%")."""
    if valor is None:
        return ""
    return f"{float(valor) * 100:.1f}%".replace(".", ",")


SUFIJOS_UNIDAD_COMPRA = {"kilo": "k", "unidad": "u", "cubeta": "c"}


def _sufijo_unidad(unidad_compra) -> str:
    """Letra corta para pegar junto al contenido por cajón (16k, 10u, 5c), para no tener que agregar otra columna."""
    return SUFIJOS_UNIDAD_COMPRA.get(unidad_compra, "")


templates.env.filters["numero"] = _formatear_numero
templates.env.filters["fecha_corta"] = _formatear_fecha_corta
templates.env.filters["moneda"] = _formatear_moneda
templates.env.filters["porcentaje"] = _formatear_porcentaje
templates.env.filters["kilos"] = _formatear_kilos
templates.env.filters["sufijo_unidad"] = _sufijo_unidad


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
    """Valida que el tipo de retiro sea uno de TIPOS_RETIRO_VALIDOS (Clark, Granel o Propia)."""
    if valor not in TIPOS_RETIRO_VALIDOS:
        return "Elegí un tipo de retiro válido (Clark, Granel o Propia)."
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
):
    error, nombre = _validar_nombre(nombre)

    if not error:
        error = _validar_unidad_compra(unidad_compra)

    contenido_referencia_valor = None
    if not error:
        error, contenido_referencia_valor = _validar_cantidad_opcional(contenido_referencia, "El contenido de referencia")

    if error:
        articulos = listar_articulos()
        return templates.TemplateResponse(
            request,
            "articulos.html",
            {"articulos": articulos, "error": error},
            status_code=400,
        )

    try:
        crear_articulo(nombre, unidad_compra, contenido_referencia_valor)
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
):
    error, nombre = _validar_nombre(nombre)

    if not error:
        error = _validar_unidad_compra(unidad_compra)

    contenido_referencia_valor = None
    if not error:
        error, contenido_referencia_valor = _validar_cantidad_opcional(contenido_referencia, "El contenido de referencia")

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
                },
                "error": error,
            },
            status_code=400,
        )

    try:
        actualizar_articulo(articulo_id, nombre, unidad_compra, contenido_referencia_valor)
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


@app.post("/clientes/nuevo")
def agregar_cliente(
    request: Request,
    nombre: str = Form(""),
    descuento: str = Form(""),
    utilidad_objetivo: str = Form(""),
):
    error, nombre = _validar_nombre(nombre)
    if not error:
        error, descuento_valor = _validar_porcentaje(descuento, "El descuento")
    if not error:
        error, utilidad_valor = _validar_porcentaje(utilidad_objetivo, "La utilidad objetivo")

    if error:
        clientes = listar_clientes()
        return templates.TemplateResponse(
            request,
            "clientes.html",
            {"clientes": clientes, "error": error},
            status_code=400,
        )

    try:
        crear_cliente(nombre, descuento_valor, utilidad_valor)
    except Exception as error:
        clientes = listar_clientes()
        return templates.TemplateResponse(
            request,
            "clientes.html",
            {"clientes": clientes, "error": f"No se pudo guardar el cliente: {error}"},
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

    return templates.TemplateResponse(request, "cliente_editar.html", {"cliente": cliente, "error": error})


@app.post("/clientes/{cliente_id}/editar")
def editar_cliente(
    request: Request,
    cliente_id: int,
    nombre: str = Form(""),
    descuento: str = Form(""),
    utilidad_objetivo: str = Form(""),
):
    error, nombre = _validar_nombre(nombre)
    if not error:
        error, descuento_valor = _validar_porcentaje(descuento, "El descuento")
    if not error:
        error, utilidad_valor = _validar_porcentaje(utilidad_objetivo, "La utilidad objetivo")

    if error:
        cliente_con_lo_ingresado = {
            "id": cliente_id,
            "nombre": nombre,
            "descuento": descuento,
            "utilidad_objetivo": utilidad_objetivo,
        }
        return templates.TemplateResponse(
            request,
            "cliente_editar.html",
            {"cliente": cliente_con_lo_ingresado, "error": error},
            status_code=400,
        )

    try:
        actualizar_cliente(cliente_id, nombre, descuento_valor, utilidad_valor)
    except Exception as error:
        cliente_con_lo_ingresado = {
            "id": cliente_id,
            "nombre": nombre,
            "descuento": descuento_valor,
            "utilidad_objetivo": utilidad_valor,
        }
        return templates.TemplateResponse(
            request,
            "cliente_editar.html",
            {"cliente": cliente_con_lo_ingresado, "error": f"No se pudo guardar el cliente: {error}"},
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
        envases = listar_envases_por_cliente(cliente_id)
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

    if error:
        articulos = listar_articulos_sin_ficha(cliente_id)
        envases = listar_envases_por_cliente(cliente_id)
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
        )
    except Exception as error_db:
        articulos = listar_articulos_sin_ficha(cliente_id)
        envases = listar_envases_por_cliente(cliente_id)
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
        envases = listar_envases_por_cliente(ficha["cliente_id"])
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
):
    error = _validar_unidad_venta(unidad_venta)

    envase_id_valor = None
    if not error:
        error, envase_id_valor = _validar_envase(envase_id)

    contenido_caja_valor = None
    if not error:
        error, contenido_caja_valor = _validar_contenido_caja(contenido_caja)

    envase_variable_valor = _envase_variable_desde_form(envase_variable)

    if error:
        envases = listar_envases_por_cliente(cliente_id)
        ficha = {
            "id": ficha_id,
            "cliente_id": cliente_id,
            "articulo_nombre": articulo_nombre,
            "envase_id": envase_id,
            "contenido_caja": contenido_caja,
            "unidad_venta": unidad_venta,
            "envase_variable": envase_variable_valor,
        }
        return templates.TemplateResponse(
            request,
            "ficha_form.html",
            {"cliente_id": cliente_id, "articulos": [], "envases": envases, "modo": "editar", "ficha": ficha, "error": error},
            status_code=400,
        )

    try:
        actualizar_ficha(ficha_id, envase_id_valor, contenido_caja_valor, unidad_venta, envase_variable_valor)
    except Exception as error_db:
        envases = listar_envases_por_cliente(cliente_id)
        ficha = {
            "id": ficha_id,
            "cliente_id": cliente_id,
            "articulo_nombre": articulo_nombre,
            "envase_id": envase_id_valor,
            "contenido_caja": contenido_caja_valor,
            "unidad_venta": unidad_venta,
            "envase_variable": envase_variable_valor,
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


@app.get("/conversion")
def ver_conversiones(request: Request, cliente_id: int | None = None, error: str | None = None):
    try:
        clientes = listar_clientes()
    except Exception as error_db:
        return templates.TemplateResponse(
            request,
            "conversion.html",
            {"clientes": [], "cliente_id": cliente_id, "conversiones": [], "error": f"No se pudo leer los clientes: {error_db}"},
            status_code=500,
        )

    conversiones = []
    if cliente_id is not None:
        try:
            conversiones = listar_conversiones_por_cliente(cliente_id)
        except Exception as error_db:
            return templates.TemplateResponse(
                request,
                "conversion.html",
                {
                    "clientes": clientes,
                    "cliente_id": cliente_id,
                    "conversiones": [],
                    "error": f"No se pudieron leer las conversiones: {error_db}",
                },
                status_code=500,
            )

    return templates.TemplateResponse(
        request,
        "conversion.html",
        {"clientes": clientes, "cliente_id": cliente_id, "conversiones": conversiones, "error": error},
    )


@app.get("/conversion/nueva")
def ver_nueva_conversion(request: Request, cliente_id: int, error: str | None = None):
    try:
        articulos = listar_articulos()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    return templates.TemplateResponse(
        request,
        "conversion_form.html",
        {
            "cliente_id": cliente_id,
            "articulos": articulos,
            "modo": "nueva",
            "conversion": None,
            "error": error,
        },
    )


@app.post("/conversion/nueva")
def agregar_conversion(
    request: Request,
    cliente_id: int = Form(...),
    articulo_id: str = Form(""),
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

    nombre_cliente_valor = nombre_cliente
    if not error:
        error, nombre_cliente_valor = _validar_nombre(nombre_cliente)

    codigo_cliente_valor = codigo_cliente.strip() or None

    if error:
        articulos = listar_articulos()
        return templates.TemplateResponse(
            request,
            "conversion_form.html",
            {
                "cliente_id": cliente_id,
                "articulos": articulos,
                "modo": "nueva",
                "conversion": None,
                "error": error,
            },
            status_code=400,
        )

    try:
        crear_conversion(articulo_id_valor, cliente_id, nombre_cliente_valor, codigo_cliente_valor)
    except Exception as error_db:
        articulos = listar_articulos()
        return templates.TemplateResponse(
            request,
            "conversion_form.html",
            {
                "cliente_id": cliente_id,
                "articulos": articulos,
                "modo": "nueva",
                "conversion": None,
                "error": f"No se pudo guardar la conversión: {error_db}",
            },
            status_code=500,
        )

    return RedirectResponse(url=f"/conversion?cliente_id={cliente_id}", status_code=303)


@app.get("/conversion/{conversion_id}/editar")
def ver_editar_conversion(request: Request, conversion_id: int, error: str | None = None):
    try:
        conversion = obtener_conversion(conversion_id)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    if conversion is None:
        raise HTTPException(status_code=404, detail="Conversión no encontrada")

    try:
        articulos = listar_articulos()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    return templates.TemplateResponse(
        request,
        "conversion_form.html",
        {
            "cliente_id": conversion["cliente_id"],
            "articulos": articulos,
            "modo": "editar",
            "conversion": conversion,
            "error": error,
        },
    )


@app.post("/conversion/{conversion_id}/editar")
def editar_conversion(
    request: Request,
    conversion_id: int,
    cliente_id: int = Form(...),
    articulo_id: str = Form(""),
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

    nombre_cliente_valor = nombre_cliente
    if not error:
        error, nombre_cliente_valor = _validar_nombre(nombre_cliente)

    codigo_cliente_valor = codigo_cliente.strip() or None

    if error:
        articulos = listar_articulos()
        conversion = {
            "id": conversion_id,
            "cliente_id": cliente_id,
            "articulo_id": articulo_id_valor,
            "nombre_cliente": nombre_cliente,
            "codigo_cliente": codigo_cliente,
        }
        return templates.TemplateResponse(
            request,
            "conversion_form.html",
            {
                "cliente_id": cliente_id,
                "articulos": articulos,
                "modo": "editar",
                "conversion": conversion,
                "error": error,
            },
            status_code=400,
        )

    try:
        actualizar_conversion(conversion_id, articulo_id_valor, nombre_cliente_valor, codigo_cliente_valor)
    except Exception as error_db:
        articulos = listar_articulos()
        conversion = {
            "id": conversion_id,
            "cliente_id": cliente_id,
            "articulo_id": articulo_id_valor,
            "nombre_cliente": nombre_cliente_valor,
            "codigo_cliente": codigo_cliente_valor,
        }
        return templates.TemplateResponse(
            request,
            "conversion_form.html",
            {
                "cliente_id": cliente_id,
                "articulos": articulos,
                "modo": "editar",
                "conversion": conversion,
                "error": f"No se pudo guardar la conversión: {error_db}",
            },
            status_code=500,
        )

    return RedirectResponse(url=f"/conversion?cliente_id={cliente_id}", status_code=303)


@app.post("/conversion/{conversion_id}/eliminar")
def eliminar_conversion_ruta(conversion_id: int, cliente_id: int = Form(...)):
    try:
        eliminar_conversion(conversion_id)
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"No se pudo eliminar la conversión: {error}") from error

    return RedirectResponse(url=f"/conversion?cliente_id={cliente_id}", status_code=303)


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
def ver_compras(request: Request, error: str | None = None):
    # TODO: a futuro agregar acá un filtro de fecha/rango a demanda (elegido
    # por el usuario). Por ahora siempre son los últimos 2 días fijos (hoy y
    # ayer), usando listar_compras_por_rango_fechas que ya soporta un rango.
    hoy = _hoy_argentina()
    try:
        compras = listar_compras_por_rango_fechas(hoy - timedelta(days=1), hoy)
    except Exception as error_db:
        return templates.TemplateResponse(
            request,
            "compras.html",
            {"compras": [], "error": f"No se pudieron leer las compras: {error_db}"},
            status_code=500,
        )

    return templates.TemplateResponse(request, "compras.html", {"compras": compras, "error": error})


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
            "compra_proveedor_form.html",
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
            "compra_proveedor_form.html",
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
        return RedirectResponse(url="/compras", status_code=303)

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
        return RedirectResponse(url="/compras", status_code=303)

    return RedirectResponse(url=f"/compras/nueva?proveedor_id={proveedor_id}", status_code=303)


@app.post("/compras/nueva/cancelar")
def cancelar_carga_proveedor(request: Request, proveedor_id: int = Form(...)):
    """Descarta TODA la carga de hoy de este proveedor (incluso lo ya guardado con "Agregar artículo") y vuelve a /compras.

    La confirmación la pide el navegador (confirm() antes de mandar el
    POST); acá no queda nada más por decidir: si llegó el POST, se borra.
    """
    try:
        eliminar_compras_del_dia_por_proveedor(_hoy_argentina(), proveedor_id)
    except Exception as error_db:
        proveedor = obtener_proveedor(proveedor_id)
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
                "error": f"No se pudo cancelar: {error_db}",
            },
            status_code=500,
        )

    return RedirectResponse(url="/compras", status_code=303)


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
    """
    try:
        imagen_pil = Image.open(io.BytesIO(imagen))
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
        try:
            proveedores = listar_proveedores()
        except Exception:
            proveedores = []
        return templates.TemplateResponse(
            request,
            "compra_proveedor_form.html",
            {"proveedores": proveedores, "error": f"No se pudo leer la foto: {error_lector}"},
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


@app.post("/compras/nueva/foto/confirmar")
async def confirmar_compra_foto(request: Request):
    form = await request.form()

    codigo_puesto_texto = str(form.get("codigo_puesto", ""))
    nombre_texto = str(form.get("nombre", ""))
    foto_preview_texto = str(form.get("foto_preview", ""))
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
            if texto_leido.strip():
                aprender_articulo(proveedor_id, normalizar_texto(texto_leido), valores["articulo_id"])
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
        return RedirectResponse(url="/compras", status_code=303)

    return RedirectResponse(url=f"/compras/nueva?proveedor_id={proveedor_id}", status_code=303)


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

    return templates.TemplateResponse(
        request,
        "compra_form.html",
        {"articulos": articulos, "modo": "editar", "compra": compra, "error": error},
    )


@app.post("/compras/{compra_id}/editar")
def editar_compra(
    request: Request,
    compra_id: int,
    articulo_id: str = Form(""),
    cantidad_cajones: str = Form(""),
    contenido_por_cajon: str = Form(""),
    importe: str = Form(""),
    sena: str = Form(""),
    tipo_retiro: str = Form(""),
):
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

    try:
        actualizar_compra(
            compra_id,
            valores["articulo_id"],
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
                "error": f"No se pudo guardar la compra: {error_db}",
            },
            status_code=500,
        )

    return RedirectResponse(url="/compras", status_code=303)


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
def eliminar_compra_ruta(compra_id: int):
    try:
        _eliminar_compra_y_su_foto_si_corresponde(compra_id)
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"No se pudo eliminar la compra: {error}") from error

    return RedirectResponse(url="/compras", status_code=303)


@app.post("/compras/eliminar-varias")
async def eliminar_varias_compras_ruta(request: Request):
    form = await request.form()
    ids = [int(valor) for valor in form.getlist("compra_id") if valor.isdigit()]

    if not ids:
        return RedirectResponse(url="/compras", status_code=303)

    hoy = _hoy_argentina()
    try:
        compras_antes = listar_compras_por_rango_fechas(hoy - timedelta(days=1), hoy)
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

    if not etiquetas_fallidas:
        return RedirectResponse(url="/compras", status_code=303)

    try:
        compras = listar_compras_por_rango_fechas(hoy - timedelta(days=1), hoy)
    except Exception as error_db:
        return templates.TemplateResponse(
            request,
            "compras.html",
            {"compras": [], "error": f"No se pudieron leer las compras: {error_db}"},
            status_code=500,
        )

    cantidad_borradas = len(ids) - len(etiquetas_fallidas)
    # Mensaje pensado para un usuario no técnico: sin ids ni jerga de base
    # de datos. La causa más probable de un fallo real es la FK de
    # recepciones (ver relevamiento previo), pero se explica en criollo.
    error = (
        f"Se borraron {cantidad_borradas} de {len(ids)} compras. "
        f"No se pudieron borrar {len(etiquetas_fallidas)} (puede que tengan una recepción asociada): "
        f"{', '.join(etiquetas_fallidas)}."
    )
    return templates.TemplateResponse(request, "compras.html", {"compras": compras, "error": error})


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


CLIENTE_COSTEO_PRUEBA_NOMBRE = "Día"
ARTICULO_DESGLOSE_PRUEBA_NOMBRE = "Morrón Verde"


@app.get("/costeo-prueba")
def ver_costeo_prueba(request: Request):
    """Pantalla TEMPORAL: listado completo para negociar precios (costo actual, anterior y vigente).

    No es la pantalla final de Ventas: sirve para verificar a ojo, con datos
    reales, que calcular_listado_para_negociar_precios anda bien, sin tener
    que usar la terminal. Por ahora siempre calcula para el cliente "Día" —
    se reemplaza más adelante por la pantalla real, con selector de cliente.
    """
    momento_referencia = datetime.now(ARGENTINA)

    try:
        clientes = listar_clientes()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    cliente = next((c for c in clientes if c["nombre"] == CLIENTE_COSTEO_PRUEBA_NOMBRE), None)
    if cliente is None:
        raise HTTPException(status_code=404, detail=f"No se encontró el cliente '{CLIENTE_COSTEO_PRUEBA_NOMBRE}'")

    try:
        articulos = calcular_listado_para_negociar_precios(cliente["id"], momento_referencia)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al calcular el costeo: {error_db}") from error_db

    # Desglose de depuración de UN artículo, para poder cruzar a mano el
    # cálculo de precio_sugerido. Temporal — si falla, no tira abajo el
    # resto de la pantalla, pero el error se loguea completo y se muestra
    # en la pantalla (no se traga en silencio).
    desglose_error = None
    try:
        desglose = calcular_precio_sugerido_desglosado(
            cliente["id"], ARTICULO_DESGLOSE_PRUEBA_NOMBRE, momento_referencia
        )
    except Exception as error_desglose:
        logger.exception(
            "Error al calcular el desglose de precio sugerido para '%s' (cliente %s)",
            ARTICULO_DESGLOSE_PRUEBA_NOMBRE,
            cliente["nombre"],
        )
        desglose = None
        desglose_error = f"{type(error_desglose).__name__}: {error_desglose}"

    return templates.TemplateResponse(
        request,
        "costeo_prueba.html",
        {
            "cliente_nombre": cliente["nombre"],
            "articulos": articulos,
            "fecha_referencia": momento_referencia.strftime("%d/%m/%Y %H:%M"),
            "desglose": desglose,
            "desglose_error": desglose_error,
            "articulo_desglose_nombre": ARTICULO_DESGLOSE_PRUEBA_NOMBRE,
            "utilidad_objetivo_cliente": (
                cliente["utilidad_objetivo"] / 100 if cliente["utilidad_objetivo"] is not None else None
            ),
        },
    )


@app.get("/negociar")
def ver_cuadro_negociar_precios(request: Request):
    """Cuadro simplificado para negociar precios: Bajas, Subas y artículos bajo la utilidad objetivo.

    Usa exactamente los mismos datos que calcular_listado_para_negociar_precios
    (vía agrupar_para_negociar) — no recalcula nada, solo los agrupa y
    ordena distinto para negociar rápido. La tabla completa de depuración
    sigue en /costeo-prueba.
    """
    momento_referencia = datetime.now(ARGENTINA)

    try:
        clientes = listar_clientes()
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al conectar con la base de datos: {error_db}") from error_db

    cliente = next((c for c in clientes if c["nombre"] == CLIENTE_COSTEO_PRUEBA_NOMBRE), None)
    if cliente is None:
        raise HTTPException(status_code=404, detail=f"No se encontró el cliente '{CLIENTE_COSTEO_PRUEBA_NOMBRE}'")

    try:
        articulos = calcular_listado_para_negociar_precios(cliente["id"], momento_referencia)
    except Exception as error_db:
        raise HTTPException(status_code=500, detail=f"Error al calcular el costeo: {error_db}") from error_db

    utilidad_objetivo_cliente = (
        cliente["utilidad_objetivo"] / 100 if cliente["utilidad_objetivo"] is not None else None
    )
    grupos = agrupar_para_negociar(articulos, utilidad_objetivo_cliente)

    return templates.TemplateResponse(
        request,
        "negociar.html",
        {
            "cliente_nombre": cliente["nombre"],
            "fecha_referencia": momento_referencia.strftime("%d/%m/%Y %H:%M"),
            "bajas": grupos["bajas"],
            "subas": grupos["subas"],
            "bajo_objetivo": grupos["bajo_objetivo"],
            "utilidad_objetivo_cliente": utilidad_objetivo_cliente,
        },
    )


if __name__ == "__main__":
    import os

    import uvicorn

    puerto = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=puerto)

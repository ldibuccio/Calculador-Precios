"""Aplicación FastAPI: esqueleto y prueba de conexión a la base de datos.

Todavía NO conecta el lector de comandas ni pantallas HTML — solo el
esqueleto de la API y la prueba de conexión a Supabase. El motor de costeo
y las fichas en core/ no se tocan.
"""

import re
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.db import (
    actualizar_articulo,
    actualizar_cliente,
    actualizar_compra,
    actualizar_conversion,
    actualizar_ficha,
    actualizar_importe_compra,
    contar_articulos,
    crear_articulo,
    crear_cliente,
    crear_compra,
    crear_conversion,
    crear_ficha,
    desactivar_articulo,
    desactivar_cliente,
    eliminar_compra,
    eliminar_conversion,
    eliminar_ficha,
    listar_articulos,
    listar_articulos_sin_ficha,
    listar_clientes,
    listar_compras_por_fecha,
    listar_compras_por_fecha_y_proveedor,
    listar_compras_sin_precio,
    listar_conversiones_por_cliente,
    listar_envases_por_cliente,
    listar_fichas_por_cliente,
    listar_proveedores,
    obtener_articulo,
    obtener_cliente,
    obtener_compra,
    obtener_conversion,
    obtener_ficha,
    obtener_o_crear_proveedor_por_codigo,
    obtener_proveedor,
)

UNIDADES_VENTA_VALIDAS = {"kilo", "unidad", "cubeta"}
TIPOS_RETIRO_VALIDOS = {"Clark", "Granel"}
ARGENTINA = timezone(timedelta(hours=-3))
REGEX_CODIGO_PUESTO = re.compile(r"^[NL][0-9]{2}P[0-9]{2}$")


def _hoy_argentina():
    """Fecha de hoy en Argentina (UTC-3 fijo, sin horario de verano), sin depender de la hora del servidor."""
    return datetime.now(ARGENTINA).date()

app = FastAPI()
templates = Jinja2Templates(directory="templates")


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
    """Valida que el tipo de retiro sea Clark o Granel."""
    if valor not in TIPOS_RETIRO_VALIDOS:
        return "Elegí un tipo de retiro válido (Clark o Granel)."
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


def _validar_compra_form(
    articulo_id: str, cantidad_kilos: str, cantidad_fraccion: str, importe: str, sena: str, tipo_retiro: str
) -> tuple[str | None, dict]:
    """Valida los campos de edición de una compra (cantidad_kilos/cantidad_fraccion directos).

    Devuelve (error, valores) donde valores trae articulo_id, cantidad_kilos, cantidad_fraccion,
    importe, sena y tipo_retiro ya convertidos (o None/placeholder si hubo error antes de llegar a ese campo).
    """
    error = None
    valores = {
        "articulo_id": None,
        "cantidad_kilos": None,
        "cantidad_fraccion": None,
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
        error, valores["cantidad_kilos"] = _validar_cantidad_opcional(cantidad_kilos, "La cantidad en kilos")

    if not error:
        error, valores["cantidad_fraccion"] = _validar_cantidad_opcional(cantidad_fraccion, "La cantidad de fracción")

    if not error and valores["cantidad_kilos"] is None and valores["cantidad_fraccion"] is None:
        error = "Cargá al menos la cantidad en kilos o la cantidad de fracción."

    if not error:
        error, valores["importe"] = _validar_importe(importe)

    if not error:
        error, valores["sena"] = _validar_sena(sena)

    if not error:
        error = _validar_tipo_retiro(tipo_retiro)

    return error, valores


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
    try:
        compras = listar_compras_por_fecha(_hoy_argentina())
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
    cantidad_kilos: str = Form(""),
    cantidad_fraccion: str = Form(""),
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

    error, valores = _validar_compra_form(articulo_id, cantidad_kilos, cantidad_fraccion, importe, sena, tipo_retiro)

    if error:
        articulos = listar_articulos()
        compra = {
            "id": compra_id,
            "articulo_id": valores["articulo_id"],
            "proveedor_nombre": compra_actual["proveedor_nombre"],
            "proveedor_codigo_puesto": compra_actual["proveedor_codigo_puesto"],
            "cantidad_kilos": cantidad_kilos,
            "cantidad_fraccion": cantidad_fraccion,
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

    try:
        actualizar_compra(
            compra_id,
            valores["articulo_id"],
            valores["cantidad_kilos"],
            valores["cantidad_fraccion"],
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
            "cantidad_kilos": cantidad_kilos,
            "cantidad_fraccion": cantidad_fraccion,
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


@app.post("/compras/{compra_id}/eliminar")
def eliminar_compra_ruta(compra_id: int):
    try:
        eliminar_compra(compra_id)
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"No se pudo eliminar la compra: {error}") from error

    return RedirectResponse(url="/compras", status_code=303)


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


if __name__ == "__main__":
    import os

    import uvicorn

    puerto = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=puerto)

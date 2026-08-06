"""Aplicación FastAPI: esqueleto y prueba de conexión a la base de datos.

Todavía NO conecta el lector de comandas ni pantallas HTML — solo el
esqueleto de la API y la prueba de conexión a Supabase. El motor de costeo
y las fichas en core/ no se tocan.
"""

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.db import (
    actualizar_articulo,
    actualizar_cliente,
    actualizar_ficha,
    contar_articulos,
    crear_articulo,
    crear_cliente,
    crear_ficha,
    desactivar_articulo,
    desactivar_cliente,
    eliminar_ficha,
    listar_articulos,
    listar_articulos_sin_ficha,
    listar_clientes,
    listar_envases_por_cliente,
    listar_fichas_por_cliente,
    obtener_articulo,
    obtener_cliente,
    obtener_ficha,
)

UNIDADES_VENTA_VALIDAS = {"kilo", "unidad", "cubeta"}

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


def _validar_envase_y_contenido(
    envase_id_texto: str, contenido_caja_texto: str
) -> tuple[str | None, int | None, float | None]:
    """Valida envase (opcional) y contenido de caja (obligatorio si hay envase).

    Devuelve (error, envase_id, contenido_caja). Si no se eligió envase,
    contenido_caja se ignora y queda en None (artículo sin envase compartido).
    """
    envase_id_texto = envase_id_texto.strip()
    contenido_caja_texto = contenido_caja_texto.strip()

    if not envase_id_texto:
        return None, None, None

    try:
        envase_id = int(envase_id_texto)
    except ValueError:
        return "El envase elegido no es válido.", None, None

    if not contenido_caja_texto:
        return "El contenido de caja es obligatorio cuando elegís un envase.", None, None

    try:
        contenido_caja = float(contenido_caja_texto)
    except ValueError:
        return "El contenido de caja tiene que ser un número.", None, None

    if contenido_caja <= 0:
        return "El contenido de caja tiene que ser mayor a cero.", None, None

    return None, envase_id, contenido_caja


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
def agregar_articulo(request: Request, nombre: str = Form("")):
    error, nombre = _validar_nombre(nombre)

    if error:
        articulos = listar_articulos()
        return templates.TemplateResponse(
            request,
            "articulos.html",
            {"articulos": articulos, "error": error},
            status_code=400,
        )

    try:
        crear_articulo(nombre)
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
def editar_articulo(request: Request, articulo_id: int, nombre: str = Form("")):
    error, nombre = _validar_nombre(nombre)

    if error:
        return templates.TemplateResponse(
            request,
            "articulo_editar.html",
            {"articulo": {"id": articulo_id, "nombre": nombre}, "error": error},
            status_code=400,
        )

    try:
        actualizar_articulo(articulo_id, nombre)
    except Exception as error:
        return templates.TemplateResponse(
            request,
            "articulo_editar.html",
            {
                "articulo": {"id": articulo_id, "nombre": nombre},
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
    contenido_caja_valor = None
    if not error:
        error, envase_id_valor, contenido_caja_valor = _validar_envase_y_contenido(envase_id, contenido_caja)

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
        crear_ficha(articulo_id_valor, cliente_id, envase_id_valor, contenido_caja_valor, unidad_venta)
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
):
    error = _validar_unidad_venta(unidad_venta)

    envase_id_valor = None
    contenido_caja_valor = None
    if not error:
        error, envase_id_valor, contenido_caja_valor = _validar_envase_y_contenido(envase_id, contenido_caja)

    if error:
        envases = listar_envases_por_cliente(cliente_id)
        ficha = {
            "id": ficha_id,
            "cliente_id": cliente_id,
            "articulo_nombre": articulo_nombre,
            "envase_id": envase_id,
            "contenido_caja": contenido_caja,
            "unidad_venta": unidad_venta,
        }
        return templates.TemplateResponse(
            request,
            "ficha_form.html",
            {"cliente_id": cliente_id, "articulos": [], "envases": envases, "modo": "editar", "ficha": ficha, "error": error},
            status_code=400,
        )

    try:
        actualizar_ficha(ficha_id, envase_id_valor, contenido_caja_valor, unidad_venta)
    except Exception as error_db:
        envases = listar_envases_por_cliente(cliente_id)
        ficha = {
            "id": ficha_id,
            "cliente_id": cliente_id,
            "articulo_nombre": articulo_nombre,
            "envase_id": envase_id_valor,
            "contenido_caja": contenido_caja_valor,
            "unidad_venta": unidad_venta,
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


if __name__ == "__main__":
    import os

    import uvicorn

    puerto = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=puerto)

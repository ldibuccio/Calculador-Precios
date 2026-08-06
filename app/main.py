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
    contar_articulos,
    crear_articulo,
    crear_cliente,
    desactivar_articulo,
    desactivar_cliente,
    listar_articulos,
    listar_clientes,
    obtener_articulo,
    obtener_cliente,
)

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
def agregar_articulo(request: Request, nombre: str = Form(...)):
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
def editar_articulo(request: Request, articulo_id: int, nombre: str = Form(...)):
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
    nombre: str = Form(...),
    descuento: str = Form(...),
    utilidad_objetivo: str = Form(...),
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
    nombre: str = Form(...),
    descuento: str = Form(...),
    utilidad_objetivo: str = Form(...),
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


if __name__ == "__main__":
    import os

    import uvicorn

    puerto = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=puerto)

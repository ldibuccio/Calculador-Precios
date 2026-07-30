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
    contar_articulos,
    crear_articulo,
    desactivar_articulo,
    listar_articulos,
    obtener_articulo,
)

app = FastAPI()
templates = Jinja2Templates(directory="templates")


def _validar_nombre_y_merma(nombre: str, merma_porcentaje: str) -> tuple[str | None, str, float | None]:
    """Valida nombre no vacío y merma entre 0 y 100. Devuelve (error, nombre_limpio, merma)."""
    nombre = nombre.strip()
    merma_porcentaje = merma_porcentaje.strip()

    if not nombre:
        return "El nombre no puede estar vacío.", nombre, None

    try:
        merma = float(merma_porcentaje) if merma_porcentaje else 0.0
    except ValueError:
        return "La merma tiene que ser un número.", nombre, None

    if not (0 <= merma <= 100):
        return "La merma tiene que estar entre 0 y 100.", nombre, None

    return None, nombre, merma


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
    nombre: str = Form(...),
    merma_porcentaje: str = Form("0"),
):
    error, nombre, merma = _validar_nombre_y_merma(nombre, merma_porcentaje)

    if error:
        articulos = listar_articulos()
        return templates.TemplateResponse(
            request,
            "articulos.html",
            {"articulos": articulos, "error": error},
            status_code=400,
        )

    try:
        crear_articulo(nombre, merma)
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
    nombre: str = Form(...),
    merma_porcentaje: str = Form("0"),
):
    error, nombre, merma = _validar_nombre_y_merma(nombre, merma_porcentaje)

    if error:
        return templates.TemplateResponse(
            request,
            "articulo_editar.html",
            {"articulo": {"id": articulo_id, "nombre": nombre, "merma_porcentaje": merma_porcentaje}, "error": error},
            status_code=400,
        )

    try:
        actualizar_articulo(articulo_id, nombre, merma)
    except Exception as error:
        return templates.TemplateResponse(
            request,
            "articulo_editar.html",
            {
                "articulo": {"id": articulo_id, "nombre": nombre, "merma_porcentaje": merma},
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


if __name__ == "__main__":
    import os

    import uvicorn

    puerto = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=puerto)

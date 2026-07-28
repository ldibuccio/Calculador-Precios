"""Aplicación FastAPI: esqueleto y prueba de conexión a la base de datos.

Todavía NO conecta el lector de comandas ni pantallas HTML — solo el
esqueleto de la API y la prueba de conexión a Supabase. El motor de costeo
y las fichas en core/ no se tocan.
"""

from fastapi import FastAPI, HTTPException

from app.db import contar_articulos

app = FastAPI()


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


if __name__ == "__main__":
    import os

    import uvicorn

    puerto = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=puerto)

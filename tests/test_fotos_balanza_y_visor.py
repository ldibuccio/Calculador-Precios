"""Las fotos de la BALANZA en alta y el VISOR de fotos de Buscar compras (dueño, 16/10).

1. Achicadas a 1000 px no se leía el número del visor de la balanza. Solo las
   fotos de la PESADA se guardan con el lado mayor hasta 3000 px y calidad
   90 (la original si es más chica: nunca se agranda). El resto, como hoy.
   Donde se cargan dice "Sacala cerca, que se lea el número del visor."
2. Los botoncitos "Comanda" y "Pesaje" de Buscar compras (y de Guías
   mercadería) abren DIRECTO el visor: pantalla completa, zoom, y se pasa
   de una foto a otra. El detalle se abre solo desde el menú.

Storage no se toca: la subida se reemplaza y se mira QUÉ bytes recibió.
"""
import asyncio
import io
import os
import re
import sys
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import app.main as m  # noqa: E402
from app.main import PUERTA_ADMINISTRACION, PUERTA_COMPRAS, app  # noqa: E402
from tests.test_app import COMPRA_DETALLE_DE_PRUEBA  # noqa: E402

AYUDA = "Sacala cerca, que se lea el número del visor."
CLAVES = {"CLAVE_COMPRAS": "compras-secreta", "CLAVE_ADMINISTRACION": "admin-secreta"}


def _foto(ancho, alto, formato="JPEG") -> bytes:
    salida = io.BytesIO()
    # Con algo de detalle, para que la calidad se note en la tabla de cuantización.
    imagen = Image.effect_noise((ancho, alto), 40).convert("RGB")
    imagen.save(salida, format=formato)
    return salida.getvalue()


def _tabla_de_calidad(calidad) -> dict:
    salida = io.BytesIO()
    Image.new("RGB", (8, 8)).save(salida, format="JPEG", quality=calidad)
    return Image.open(io.BytesIO(salida.getvalue())).quantization


def _cliente(*puertas):
    cliente = TestClient(app, base_url="https://testserver")
    for puerta, clave in (("compras", "compras-secreta"), ("administracion", "admin-secreta")):
        if puerta in puertas:
            objeto = PUERTA_COMPRAS if puerta == "compras" else PUERTA_ADMINISTRACION
            cliente.cookies.set(objeto.cookie, objeto.firma(clave))
    return cliente


@pytest.fixture(autouse=True)
def _claves():
    with patch.dict(os.environ, CLAVES):
        yield


# --- 1. LA RESOLUCIÓN ---------------------------------------------------------------

def test_la_foto_de_BALANZA_queda_en_3000_px_y_calidad_90_y_la_chica_no_se_agranda():
    grande = Image.open(io.BytesIO(m._comprimir_foto_de_balanza(_foto(4000, 3000))))
    assert grande.size == (3000, 2250)
    assert grande.quantization == _tabla_de_calidad(90)
    # Acostada o parada, manda el lado mayor.
    assert Image.open(io.BytesIO(m._comprimir_foto_de_balanza(_foto(1500, 4500)))).size == (1000, 3000)
    # La original más chica queda de su tamaño (un PNG también sale JPEG).
    chica = Image.open(io.BytesIO(m._comprimir_foto_de_balanza(_foto(800, 600, "PNG"))))
    assert (chica.size, chica.format) == ((800, 600), "JPEG")
    assert m._comprimir_foto_de_balanza(b"no es una foto") is None


def test_las_DEMAS_fotos_siguen_como_hoy_1000_px_y_calidad_60():
    otra = Image.open(io.BytesIO(m._comprimir_foto_jpeg(_foto(4000, 3000))))
    assert otra.size == (1000, 750)
    assert otra.quantization == _tabla_de_calidad(60)


def _subidas_de(post) -> list[tuple[str, tuple]]:
    """Corre `post` con Storage reemplazado y devuelve (prefijo, tamaño) de cada subida."""
    subidas = []

    def subir(contenido, nombre, prefijo="comanda"):
        subidas.append((prefijo, Image.open(io.BytesIO(contenido)).size))
        return f"{prefijo}/x-{len(subidas)}.jpg"
    with patch("app.main.subir_foto_comanda", side_effect=subir):
        post()
    return subidas


def test_AGREGAR_FOTO_DE_PESADA_del_detalle_sube_en_alta():
    def post():
        with patch("app.main.obtener_compra", return_value={"id": 30}), \
             patch("app.main.agregar_foto_recepcion") as guardar:
            respuesta = _cliente("compras").post("/compras/30/fotos-balanza", follow_redirects=False,
                                                 files=[("fotos", ("p.jpg", _foto(4000, 3000), "image/jpeg"))])
            assert respuesta.status_code == 303 and guardar.call_count == 1
    assert _subidas_de(post) == [("pesaje", (3000, 2250))]


def test_el_INGRESO_DIRECTO_y_la_DEVOLUCION_comprimen_en_alta():
    """Los dos usan `_fotos_de_pesada_comprimidas` antes de guardar nada."""
    class Archivo:
        def __init__(self, contenido, nombre="p.jpg"):
            self.contenido, self.filename = contenido, nombre

        async def read(self):
            return self.contenido

    error, comprimidas = asyncio.run(m._fotos_de_pesada_comprimidas([Archivo(_foto(4000, 3000)), Archivo(b"")]))
    assert error is None and [Image.open(io.BytesIO(c)).size for c in comprimidas] == [(3000, 2250)]
    error, nada = asyncio.run(m._fotos_de_pesada_comprimidas([Archivo(b"texto", "a.txt")]))
    assert error == "«a.txt» no es una foto. No se guardó nada." and nada == []


def test_la_COMANDA_sigue_achicada():
    """El RIVAL: la foto de la comanda de la misma compra no sale en alta."""
    def post():
        with patch("app.main.obtener_compra", return_value={"id": 30, "guia_id": 5}), \
             patch("app.main.agregar_foto_guia", return_value=1), \
             patch("app.main.listar_fotos_de_guia", return_value=[]):
            _cliente("compras").post("/compras/30/fotos", follow_redirects=False,
                                     files={"archivo": ("c.jpg", _foto(4000, 3000), "image/jpeg")})
    subidas = _subidas_de(post)
    assert subidas and all(tamano == (1000, 750) for _, tamano in subidas), subidas


# --- 1. EL TEXTO DONDE SE CARGA ---------------------------------------------------------

def test_el_DETALLE_dice_como_sacar_la_foto_de_la_balanza():
    with patch("app.main.obtener_detalle_compra", return_value=COMPRA_DETALLE_DE_PRUEBA), \
         patch("app.main.listar_fotos_de_guia", return_value=[]), \
         patch("app.main.devoluciones_de_la_compra", return_value=[]), \
         patch("app.main.listar_fotos_de_recepcion", return_value=[]):
        html = _cliente("compras").get("/compras/30/detalle").text.split("</style>")[-1]
    assert re.findall(r"data-ayuda-balanza>([^<]*)<", html) == [AYUDA]


def test_RECEPCION_dice_como_sacar_la_foto_en_cada_compra():
    from tests.test_app import COMPRAS_PENDIENTES_RECEPCION_DE_PRUEBA, HOY_DE_PRUEBA
    with patch("app.main.listar_compras_pendientes_recepcion", return_value=COMPRAS_PENDIENTES_RECEPCION_DE_PRUEBA), \
         patch("app.main.listar_compras_procesadas_hoy_recepcion", return_value=[]), \
         patch("app.main._hoy_argentina", return_value=HOY_DE_PRUEBA):
        html = _cliente().get("/deposito/recepcion").text
    formularios = len(re.findall(r'<form method="post" action="/deposito/recepcion/\d+/foto-balanza"', html))
    assert formularios > 0
    assert re.findall(r"data-ayuda-balanza>([^<]*)<", html) == [AYUDA] * formularios


def test_la_tarjeta_de_FOTOS_PARA_SUBIR_lo_dice_solo_si_es_de_la_balanza():
    """Ingreso directo y devolución la piden con la ayuda; el remito, sin ella."""
    def tarjeta(llamada):
        return m.templates.env.from_string(
            '{% import "_fotos_para_subir.html" as f %}' + llamada).render()
    assert re.findall(r"data-ayuda-balanza>([^<]*)<", tarjeta('{{ f.tarjeta(ayuda="X") }}')) == ["X"]
    assert "data-ayuda-balanza" not in tarjeta('{{ f.tarjeta(titulo="Remito") }}')
    plantillas = {n: open(f"templates/{n}", encoding="utf-8").read()
                  for n in ("deposito_ingresar.html", "deposito_devolver.html", "remito.html", "remito_recibir.html")}
    con_ayuda = {n for n, t in plantillas.items() if f'ayuda="{AYUDA}"' in t}
    assert con_ayuda == {"deposito_ingresar.html", "deposito_devolver.html"}


# --- 2. EL VISOR -------------------------------------------------------------------------

DOS_PESAJES = [
    {"id": 3, "foto_ruta": "pesaje/2026-09-08/balanza-30-1.jpg", "creado_en": datetime(2026, 9, 8, tzinfo=timezone.utc)},
    {"id": 7, "foto_ruta": "pesaje/2026-09-10/balanza-30-2.jpg", "creado_en": datetime(2026, 9, 10, tzinfo=timezone.utc)},
]
COMANDAS = [{"id": 11, "foto_ruta": "comanda/2026-09-08/c-1.jpg"}, {"id": 12, "foto_ruta": "comanda/2026-09-08/c-2.pdf"}]


def _visor(ruta, cliente=None, pesajes=DOS_PESAJES, comandas=COMANDAS):
    with patch("app.main.obtener_compra", return_value={"id": 30, "guia_id": 5, "articulo_nombre": "EJEMPLO Uva"}), \
         patch("app.main.listar_fotos_de_recepcion", return_value=list(pesajes)), \
         patch("app.main.listar_fotos_de_guia", return_value=list(comandas)):
        return (cliente or _cliente("compras")).get(ruta, follow_redirects=False)


def _fotos(html):
    return re.findall(r'<div class="marco" data-foto="(\d+)"( hidden)?>\s*(?:<img src="([^"]+)"|<a [^>]*href="([^"]+)"[^>]*data-pdf)',
                      html)


def test_el_VISOR_del_PESAJE_muestra_todas_y_arranca_en_la_ULTIMA():
    respuesta = _visor("/compras/30/visor/pesaje?volver=/compras/buscar%3Ffecha_desde%3D2026-10-01")
    assert respuesta.status_code == 200
    assert _fotos(respuesta.text) == [
        ("0", " hidden", "/deposito/recepcion/30/foto-balanza/3/ver", ""),
        ("1", "", "/deposito/recepcion/30/foto-balanza/7/ver", "")]
    assert re.findall(r"data-cuenta>([^<]*)<", respuesta.text) == ["2 de 2"]
    assert "<title>Pesaje · EJEMPLO Uva</title>" in respuesta.text
    # "✕" vuelve a la lista CON SUS FILTROS.
    assert '<a class="boton" href="/compras/buscar?fecha_desde=2026-10-01" data-cerrar' in respuesta.text
    # Zoom y pasar de una a otra.
    assert "data-zoom" in respuesta.text and 'data-pasar="1"' in respuesta.text and 'data-pasar="-1"' in respuesta.text


def test_el_VISOR_de_la_COMANDA_arranca_en_la_primera_y_el_PDF_se_abre_aparte():
    respuesta = _visor("/compras/30/visor/comanda")
    assert _fotos(respuesta.text) == [("0", "", "/compras/30/fotos/11/ver", ""),
                                      ("1", " hidden", "", "/compras/30/fotos/12/ver")]
    # Con una sola foto no hay flechas ni cuenta.
    una = _visor("/compras/30/visor/pesaje", pesajes=DOS_PESAJES[:1]).text
    assert '<button type="button" class="boton" data-pasar' not in una and "data-cuenta>" not in una


def test_el_VISOR_desde_GUIAS_MERCADERIA_queda_bajo_su_prefijo_y_pide_su_clave():
    respuesta = _visor("/administracion/guias-mercaderia/30/visor/comanda", _cliente("administracion"))
    assert respuesta.status_code == 200
    assert [f[2] or f[3] for f in _fotos(respuesta.text)] == [
        "/administracion/guias-mercaderia/30/fotos/11/ver", "/administracion/guias-mercaderia/30/fotos/12/ver"]
    assert 'href="/administracion/guias-mercaderia" data-cerrar' in respuesta.text
    sin_clave = _visor("/administracion/guias-mercaderia/30/visor/comanda", _cliente())
    assert sin_clave.status_code != 200 or 'name="clave"' in sin_clave.text


def test_el_VISOR_sin_fotos_o_con_otra_cosa_es_404():
    assert _visor("/compras/30/visor/pesaje", pesajes=[]).status_code == 404
    assert _visor("/compras/30/visor/comanda", comandas=[]).status_code == 404
    assert _visor("/compras/30/visor/remito").status_code == 404

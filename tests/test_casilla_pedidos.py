"""Tests de core/casilla_pedidos.py: la lectura SOLO-LECTURA de la casilla.

Lo crítico acá no es que "ande": es que las garantías se cumplan —
EXAMINE (readonly), BODY.PEEK, búsqueda server-side por SINCE+FROM, y que
la conversión de HTML a texto conserve las celdas vacías de la tabla.
"""

from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
from unittest.mock import MagicMock, patch

import pytest

from core.casilla_pedidos import (
    ErrorCasilla,
    _criterio_since,
    _cuerpo_de_mensaje,
    clave_casilla_configurada,
    html_a_texto,
    revisar_casilla,
    separar_remitentes,
)

ARGENTINA = timezone(timedelta(hours=-3))


# --- La clave: de la variable de entorno, jamás de la base ---


def test_clave_casilla_viene_de_la_variable_de_entorno():
    with patch.dict("os.environ", {"CLAVE_CASILLA_PEDIDOS": "  abcd efgh  "}):
        assert clave_casilla_configurada() == "abcd efgh"


def test_clave_casilla_ausente_o_vacia_es_none():
    with patch.dict("os.environ", {"CLAVE_CASILLA_PEDIDOS": "   "}):
        assert clave_casilla_configurada() is None
    with patch.dict("os.environ", {}, clear=True):
        assert clave_casilla_configurada() is None


# --- Remitentes permitidos ---


def test_separar_remitentes_limpia_espacios_mayusculas_y_vacios():
    assert separar_remitentes(" Pedidos@dia.com.ar , otro@dia.com.ar ,, ") == [
        "pedidos@dia.com.ar",
        "otro@dia.com.ar",
    ]
    assert separar_remitentes("") == []
    assert separar_remitentes(None) == []


# --- HTML del mail -> texto conservando la estructura de la tabla ---


def test_html_a_texto_conserva_las_celdas_vacias_de_la_tabla():
    html = (
        "<table>"
        "<tr><th>Codigo</th><th>Producto</th><th>VL</th><th>BZ</th><th>GR</th></tr>"
        "<tr><td>133</td><td>Anana</td><td>5</td><td></td><td>3</td></tr>"
        "<tr><td>90137</td><td>Anco</td><td></td><td>2</td><td></td></tr>"
        "</table>"
    )
    texto = html_a_texto(html)
    # La celda vacía queda como campo vacío entre tabuladores: "esa
    # sucursal no pide ese artículo" sobrevive a la conversión.
    assert "133\tAnana\t5\t\t3" in texto
    # Las celdas vacías del FINAL de la fila también se conservan.
    assert "90137\tAnco\t\t2\t" in texto


def test_html_a_texto_ignora_estilos_scripts_y_decodifica_entidades():
    html = (
        "<html><head><style>td { color: red; }</style><script>alert(1)</script></head>"
        "<body><p>Pedido del d&iacute;a</p><p>Total: 5 &gt; 3</p></body></html>"
    )
    texto = html_a_texto(html)
    assert "Pedido del día" in texto
    assert "Total: 5 > 3" in texto
    assert "color" not in texto
    assert "alert" not in texto


def test_html_a_texto_respeta_saltos_de_br_y_parrafos():
    texto = html_a_texto("<p>Sucursal VL<br>Total 235</p><div>OC 1257673</div>")
    assert "Sucursal VL\nTotal 235" in texto
    assert "OC 1257673" in texto


# --- El cuerpo del mail: HTML preferido, text/plain de respaldo, crudo SIEMPRE ---


def _mail_de_prueba(html=None, texto=None, message_id="<pedido-1@dia.com.ar>"):
    mensaje = EmailMessage()
    mensaje["From"] = "Pedidos Dia <pedidos@dia.com.ar>"
    mensaje["Subject"] = "Pedido del dia"
    mensaje["Date"] = "Fri, 22 Aug 2026 12:05:00 -0300"
    if message_id:
        mensaje["Message-ID"] = message_id
    if texto is not None:
        mensaje.set_content(texto)
    if html is not None:
        if texto is not None:
            mensaje.add_alternative(html, subtype="html")
        else:
            mensaje.set_content(html, subtype="html")
    return mensaje


def test_cuerpo_de_mensaje_prefiere_el_html_y_lo_pasa_a_texto():
    mensaje = _mail_de_prueba(html="<table><tr><td>133</td><td>5</td></tr></table>", texto="version texto")
    crudo, texto = _cuerpo_de_mensaje(mensaje)
    assert "<table>" in crudo  # el crudo es el HTML entero, sin limpiar
    assert "133\t5" in texto


def test_cuerpo_de_mensaje_sin_html_usa_el_texto_plano():
    mensaje = _mail_de_prueba(texto="pedido en texto plano")
    crudo, texto = _cuerpo_de_mensaje(mensaje)
    assert "pedido en texto plano" in crudo
    assert "pedido en texto plano" in texto


# --- El criterio SINCE: día argentino, mes EN INGLÉS (RFC 3501) ---


def test_criterio_since_usa_el_dia_argentino_y_mes_en_ingles():
    # La 1:30 UTC del 22 es todavía el 21 en Argentina.
    assert _criterio_since(datetime(2026, 8, 22, 1, 30, tzinfo=timezone.utc)) == "21-Aug-2026"
    assert _criterio_since(datetime(2026, 1, 5, 15, 0, tzinfo=ARGENTINA)) == "05-Jan-2026"


# --- revisar_casilla: las garantías de solo-lectura, con el IMAP simulado ---


def _conexion_imap_simulada(mensajes_por_uid, uids_totales, uids_por_remitente):
    conexion = MagicMock()
    conexion.login.return_value = ("OK", [b""])
    conexion.select.return_value = ("OK", [b"9000"])

    def _uid(comando, *argumentos):
        if comando == "SEARCH":
            criterio = argumentos[-1]
            if "FROM" in criterio:
                for remitente, uids in uids_por_remitente.items():
                    if remitente in criterio:
                        return ("OK", [b" ".join(uids)])
                return ("OK", [b""])
            return ("OK", [b" ".join(uids_totales)])
        if comando == "FETCH":
            uid = argumentos[0]
            return ("OK", [(b"1 (UID %s BODY[] {123}" % uid, mensajes_por_uid[uid]), b")"])
        raise AssertionError(f"Comando UID inesperado: {comando}")

    conexion.uid.side_effect = _uid
    return conexion


def test_revisar_casilla_abre_solo_lectura_usa_peek_y_busca_server_side():
    mensaje = _mail_de_prueba(html="<p>pedido</p>")
    conexion = _conexion_imap_simulada(
        {b"7": mensaje.as_bytes()}, uids_totales=[b"5", b"6", b"7"], uids_por_remitente={"pedidos@dia.com.ar": [b"7"]}
    )
    fecha_desde = datetime(2026, 8, 22, 10, 0, tzinfo=ARGENTINA)

    with patch("core.casilla_pedidos.imaplib.IMAP4_SSL", return_value=conexion):
        resultado = revisar_casilla(
            "casilla@empresa.com", "clave", "imap.gmail.com", fecha_desde, ["pedidos@dia.com.ar"]
        )

    # EXAMINE: la bandeja se abre en modo solo lectura, siempre.
    conexion.select.assert_called_once_with("INBOX", readonly=True)
    # BODY.PEEK en el FETCH: ni siquiera se marcaría \Seen.
    llamadas_fetch = [c for c in conexion.uid.call_args_list if c.args[0] == "FETCH"]
    assert llamadas_fetch and all("BODY.PEEK[]" in c.args[2] for c in llamadas_fetch)
    # Búsqueda server-side: SINCE para el total, SINCE+FROM para lo permitido.
    criterios = [c.args[2] for c in conexion.uid.call_args_list if c.args[0] == "SEARCH"]
    assert "(SINCE 22-Aug-2026)" in criterios
    assert '(SINCE 22-Aug-2026 FROM "pedidos@dia.com.ar")' in criterios
    # El reporte: 3 mails en total desde la activación, 1 del remitente.
    assert resultado["total_desde"] == 3
    assert len(resultado["mails"]) == 1
    assert resultado["mails"][0]["message_id"] == "<pedido-1@dia.com.ar>"
    assert resultado["mails"][0]["remitente"] == "pedidos@dia.com.ar"
    assert resultado["mails"][0]["cuerpo_texto"] == "pedido"
    # Y el logout siempre.
    conexion.logout.assert_called_once()


def test_revisar_casilla_solo_descarga_los_de_remitentes_permitidos():
    mensaje = _mail_de_prueba(html="<p>pedido</p>")
    conexion = _conexion_imap_simulada(
        {b"7": mensaje.as_bytes()}, uids_totales=[b"5", b"6", b"7"], uids_por_remitente={"pedidos@dia.com.ar": [b"7"]}
    )
    with patch("core.casilla_pedidos.imaplib.IMAP4_SSL", return_value=conexion):
        revisar_casilla(
            "casilla@empresa.com", "clave", "imap.gmail.com",
            datetime(2026, 8, 22, 10, 0, tzinfo=ARGENTINA), ["pedidos@dia.com.ar"],
        )

    # Los mails ajenos al filtro (uids 5 y 6) NI SE DESCARGAN.
    uids_descargados = [c.args[1] for c in conexion.uid.call_args_list if c.args[0] == "FETCH"]
    assert uids_descargados == [b"7"]


def test_revisar_casilla_filtra_fino_por_la_fecha_real_del_mail():
    # SINCE tiene granularidad de día: un mail del mismo día pero ANTERIOR
    # a la hora de activación se descarta acá, por su fecha real.
    mensaje_viejo = _mail_de_prueba(html="<p>viejo</p>", message_id="<viejo@dia.com.ar>")
    del mensaje_viejo["Date"]
    mensaje_viejo["Date"] = "Sat, 22 Aug 2026 09:00:00 -0300"
    conexion = _conexion_imap_simulada(
        {b"7": mensaje_viejo.as_bytes()}, uids_totales=[b"7"], uids_por_remitente={"pedidos@dia.com.ar": [b"7"]}
    )
    with patch("core.casilla_pedidos.imaplib.IMAP4_SSL", return_value=conexion):
        resultado = revisar_casilla(
            "casilla@empresa.com", "clave", "imap.gmail.com",
            datetime(2026, 8, 22, 10, 0, tzinfo=ARGENTINA), ["pedidos@dia.com.ar"],
        )

    assert resultado["mails"] == []


def test_revisar_casilla_login_fallido_avisa_y_menciona_workspace():
    import imaplib

    conexion = MagicMock()
    conexion.login.side_effect = imaplib.IMAP4.error("AUTHENTICATIONFAILED")
    with patch("core.casilla_pedidos.imaplib.IMAP4_SSL", return_value=conexion):
        with pytest.raises(ErrorCasilla) as error:
            revisar_casilla(
                "casilla@empresa.com", "clave", "imap.gmail.com",
                datetime(2026, 8, 22, 10, 0, tzinfo=ARGENTINA), ["pedidos@dia.com.ar"],
            )

    # El mensaje orienta al diagnóstico real: Workspace puede tener IMAP
    # deshabilitado por el administrador.
    assert "Google Workspace" in str(error.value)
    # Aunque el login falle, el logout se intenta igual.
    conexion.logout.assert_called_once()


def test_revisar_casilla_sin_message_id_fabrica_uno_estable_por_uid():
    mensaje = _mail_de_prueba(html="<p>pedido</p>", message_id=None)
    conexion = _conexion_imap_simulada(
        {b"7": mensaje.as_bytes()}, uids_totales=[b"7"], uids_por_remitente={"pedidos@dia.com.ar": [b"7"]}
    )
    with patch("core.casilla_pedidos.imaplib.IMAP4_SSL", return_value=conexion):
        resultado = revisar_casilla(
            "casilla@empresa.com", "clave", "imap.gmail.com",
            datetime(2026, 8, 22, 10, 0, tzinfo=ARGENTINA), ["pedidos@dia.com.ar"],
        )

    assert resultado["mails"][0]["message_id"] == "<uid-7@casilla@empresa.com>"

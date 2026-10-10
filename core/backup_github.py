"""EL BACKUP LO LANZA EL SISTEMA A LAS 03:47 (dueño, 09/10).

Los horarios programados de GitHub (`schedule` en .github/workflows/backup.yml)
salían todos los días entre 6 y 8 horas y media tarde: el de las 03:47 corría
a las 11 de la mañana. Las corridas lanzadas a mano (`workflow_dispatch`) salen
en el momento. Así que el reloj de fondo del sistema —el mismo que recalcula
las Alertas y el Panel— le pide a GitHub que lance el Backup a las 03:47 de
Argentina. Los dos horarios de GitHub quedan de RESPALDO: el workflow se los
saltea si ese día ya hubo un backup bueno.

LA LLAVE (`BACKUP_GITHUB_TOKEN`, una variable de Railway): un token de GitHub
"fine-grained", SOLO para el repo Calculador-Precios, SOLO con permiso de
Actions. NO VENCE: el dueño la regeneró sin vencimiento (09/10), y la
pantalla de Backups lo dice en verde ("no tiene vencimiento"). Si alguna vez
se carga una que vence, GitHub dice cuándo en cada respuesta (el encabezado
`github-authentication-token-expiration`) y la pantalla avisa un mes antes.
La llave no se escribe nunca en un archivo ni en un log.

Si la llave está cargada en las dos aplicaciones (Frutamax y Palmala), las dos
lanzan a las 03:47: el workflow corre de a uno (`concurrency`) y el segundo se
saltea porque ya hubo uno bueno ese día. Un backup de más no se hace.
"""
from datetime import datetime, time, timedelta, timezone

TOKEN_ENV_VAR = "BACKUP_GITHUB_TOKEN"
REPO = "ldibuccio/Calculador-Precios"
WORKFLOW = "backup.yml"
API = "https://api.github.com"

# Desde cuándo y hasta cuándo se lanza. Pasadas las 07:00 no se lanza: para
# eso están los horarios de respaldo de GitHub, y un backup a media mañana
# compite con el trabajo del día.
DESDE = time(3, 47)
HASTA = time(7, 0)
# Si GitHub no contestó, se vuelve a probar a los 15 minutos (no cada minuto).
REINTENTO = timedelta(minutes=15)
# La pantalla avisa cuando faltan menos de estos días para que venza.
DIAS_DE_AVISO = 30


def toca_lanzar(ahora: datetime, ultimo_intento: datetime | None, lanzado_el) -> bool:
    """True si es la ventana de la madrugada, hoy todavía no se lanzó, y el
    último intento fallido (si lo hubo) fue hace más de REINTENTO."""
    if not (DESDE <= ahora.time() < HASTA):
        return False
    if lanzado_el == ahora.date():
        return False
    return ultimo_intento is None or ahora - ultimo_intento >= REINTENTO


def _encabezados(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"}


def vencimiento(respuesta) -> datetime | None:
    """La fecha en que vence la llave, del encabezado que GitHub manda en cada
    respuesta ("2027-10-09 03:47:00 UTC" o "2027-10-09 03:47:00 -0300")."""
    texto = respuesta.headers.get("github-authentication-token-expiration")
    if not texto:
        return None
    for formato in ("%Y-%m-%d %H:%M:%S %Z", "%Y-%m-%d %H:%M:%S %z"):
        try:
            fecha = datetime.strptime(texto.strip(), formato)
        except ValueError:
            continue
        if fecha.tzinfo is None:
            fecha = fecha.replace(tzinfo=timezone.utc)
        return fecha
    return None


def lanzar(cliente, token: str) -> None:
    """Le pide a GitHub que corra el Backup ahora, marcado como del sistema
    (`origen=sistema`: el workflow lo saltea si hoy ya hubo uno bueno).
    Lanza una excepción si GitHub no contesta 204."""
    respuesta = cliente.post(f"{API}/repos/{REPO}/actions/workflows/{WORKFLOW}/dispatches",
                             headers=_encabezados(token), json={"ref": "main", "inputs": {"origen": "sistema"}})
    if respuesta.status_code != 204:
        raise RuntimeError(f"GitHub contestó {respuesta.status_code} al lanzar el backup")


def leer_la_llave(cliente, token: str | None) -> dict:
    """{"estado": "sin_llave" | "no_anda" | "sin_respuesta" | "ok", "vence": datetime | None}."""
    if not token:
        return {"estado": "sin_llave", "vence": None}
    try:
        respuesta = cliente.get(f"{API}/repos/{REPO}/actions/workflows/{WORKFLOW}", headers=_encabezados(token))
    except Exception:  # noqa: BLE001 - sin red, la pantalla igual tiene que abrir
        return {"estado": "sin_respuesta", "vence": None}
    if respuesta.status_code in (401, 403, 404):
        return {"estado": "no_anda", "vence": None}
    if respuesta.status_code != 200:
        return {"estado": "sin_respuesta", "vence": None}
    return {"estado": "ok", "vence": vencimiento(respuesta)}


def aviso_de_la_llave(llave: dict, ahora: datetime) -> dict:
    """Lo que dice la pantalla de Backups: {"nivel": "rojo"|"amarillo"|"ok", "texto"}."""
    estado = llave["estado"]
    if estado == "sin_llave":
        return {"nivel": "rojo", "texto": "La llave de GitHub no está cargada: el backup de la madrugada no "
                                          "se lanza solo y sale con el horario de GitHub, horas tarde."}
    if estado == "no_anda":
        return {"nivel": "rojo", "texto": "La llave de GitHub no anda (venció o la borraron): el backup de "
                                          "la madrugada no se lanza. Hay que crear una nueva."}
    if estado == "sin_respuesta":
        return {"nivel": "amarillo", "texto": "No se pudo preguntar a GitHub por la llave. Si sigue así, avisá."}
    vence = llave["vence"]
    if vence is None:
        return {"nivel": "ok", "texto": "La llave de GitHub anda y no tiene vencimiento."}
    dia = vence.astimezone(ahora.tzinfo).strftime("%d/%m/%Y")
    if vence <= ahora:
        return {"nivel": "rojo", "texto": f"La llave de GitHub venció el {dia}. Hay que crear una nueva."}
    if vence - ahora <= timedelta(days=DIAS_DE_AVISO):
        return {"nivel": "amarillo", "texto": f"La llave de GitHub vence el {dia}. Hay que crear una nueva "
                                              "antes de esa fecha y cargarla en Railway."}
    return {"nivel": "ok", "texto": f"La llave de GitHub anda hasta el {dia}."}

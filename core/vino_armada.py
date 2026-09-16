"""POR QUÉ NO SE PUEDE marcar una compra como "vino armada en caja nuestra".

LA REGLA VIVE ACÁ Y EN NINGÚN OTRO LADO, y ésa es toda la razón de este
módulo. Estaba escrita DOS veces: la pantalla de destino conocía tres
motivos y el menú de Buscar Compras conocía dos (`recepcionada` y `sin
marca`), así que el menú ofrecía el botón en casos donde la pantalla lo
rechaza. Medido en Frutamax el 16/09: de 482 compras que mostraban el
botón, **325 las frenaba el corte y 90 tenían el lote ya consumido
entero**. El botón aparecía en 482 y servía en una minoría.

Dos reglas separadas se vuelven a separar, así que el menú y la pantalla
preguntan las dos por `motivo_para_no_marcar_armada` y nadie más decide.

EL CÓDIGO DEL MOTIVO ES LO QUE VIAJA, no el texto: la pantalla muestra el
párrafo entero y el menú una etiqueta corta, y son dos formas de decir el
MISMO motivo. Escribir dos textos sueltos sería la copia otra vez, un
escalón más abajo — por eso el mapa corto se arma sobre los códigos y un
test compara el conjunto ENCONTRADO contra el DECIDIDO (corolario 60): un
motivo nuevo no puede entrar sin que el menú aprenda a nombrarlo.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class MotivoVinoArmada:
    """Por qué esta compra no se puede marcar. `codigo` decide, `texto` explica."""

    codigo: str
    texto: str


# LOS QUE ESCONDEN EL BOTÓN Y LOS QUE LO DESHABILITAN, y la diferencia es
# del dueño (16/09): escondido, "no se puede NUNCA" y "ya vino armada y
# está registrada" se ven igual — y la segunda es el estado BUENO. Por eso
# solo se esconde cuando la ausencia ya significa algo:
#
#   - `ya_marcada`      -> el trabajo está hecho. No es un "no se puede".
#   - `no_recepcionada` -> todavía no es el momento de esta compra.
#
# Todos los demás son "no se puede, y por esto", y eso se lee. El menú
# arranca cerrado, así que un renglón deshabilitado no le cuesta nada al
# que escanea la lista: lo paga solo el que lo abrió buscando qué hacer
# con esa compra, que es justamente el que quiere el motivo.
MOTIVOS_QUE_ESCONDEN_EL_BOTON = ("ya_marcada", "no_recepcionada")


def motivo_sin_lote_por_el_corte(fecha, corte) -> str | None:
    """Por qué esa fecha NO tiene lote del FIFO, o None si lo tiene.

    ESTRICTAMENTE POSTERIOR AL CORTE, y el día del corte también queda
    afuera. Es la asimetría de siempre —el conteo del corte se toma A LA
    TARDE, así que todo lo de ese día ya está adentro de la foto—, y en
    este archivo está escrita UNA vez: `app.db._motivo_sin_lote_por_el_corte`
    es esta misma con el corte leído de la base. CLAUDE.md lleva la cuenta
    de las ocho veces que esa asimetría se reescribió en lugares que no se
    nombran entre sí; ésta no agrega una novena.
    """
    if fecha > corte:
        return None
    return (
        f"La fecha tiene que ser POSTERIOR al corte del modelo ({corte:%d/%m/%Y}). "
        "Ese día ya está adentro de la foto del stock inicial, así que una compra fechada "
        "ahí suma al total sin ser un lote del FIFO."
    )


def motivo_para_no_marcar_armada(compra: dict, corte) -> MotivoVinoArmada | None:
    """El primer motivo por el que esta compra no se puede marcar, o None si se puede.

    `compra` trae lo que la base ya sabe y nada derivado: `ficha_en_origen_id`,
    `estado`, `fecha_del_lote` (la fecha AR de `procesada_el`), `bultos` y
    `bultos_consumidos`.

    EL ORDEN NO ES ARBITRARIO: `ya_marcada` va primera porque es el estado
    BUENO —el trabajo hecho— y leerlo como una falla sería el peor de los
    mensajes. Después el momento (`no_recepcionada`), después lo
    estructural (`sin_fecha_de_lote`, `anterior_al_corte`) y al final lo
    que depende de lo que pasó con el lote.

    EL LOTE CONSUMIDO SE MIRA SOLO CUANDO ESTÁ ENTERO, y es decisión del
    dueño: el parcial lo decide el freno de `_crear_reproceso`, que compara
    el restante real contra la misma lista que el FIFO. Un menú que
    adivinara el parcial estaría escribiendo una tercera versión de una
    regla que ya existe, y esta vez peor que la original.
    """
    if compra.get("ficha_en_origen_id") is not None:
        return MotivoVinoArmada(
            "ya_marcada",
            "Esta compra ya está marcada como venida armada: su guía R ya está cargada.",
        )

    if compra.get("estado") != "recepcionado":
        return MotivoVinoArmada(
            "no_recepcionada",
            "Esta compra todavía no se recepcionó. La marca va en la carga —editala y elegí "
            "la caja— y la guía R sale sola cuando Depósito la reciba.",
        )

    # SIN FECHA DE RECEPCIÓN: la pantalla no lo anticipaba y el que escribe
    # sí (`marcar_compra_armada_en_origen` levanta un ValueError), así que
    # el botón llevaba a un error en vez de a un cartel. Medido cero en
    # Frutamax el 16/09 — y cerrarlo con cero casos es gratis, que es
    # justamente cuándo conviene (corolario 64).
    if compra.get("fecha_del_lote") is None:
        return MotivoVinoArmada(
            "sin_fecha_de_lote",
            "Esta compra no tiene fecha de recepción: no hay lote contra el que armar la guía R.",
        )

    por_el_corte = motivo_sin_lote_por_el_corte(compra["fecha_del_lote"], corte)
    if por_el_corte is not None:
        return MotivoVinoArmada(
            "anterior_al_corte",
            f"{por_el_corte} Esa mercadería ya está contada en el stock inicial, "
            "así que no hay lote contra el que armar la guía R.",
        )

    bultos = compra.get("bultos")
    consumidos = compra.get("bultos_consumidos")
    if bultos is not None and consumidos is not None and float(consumidos) >= float(bultos):
        return MotivoVinoArmada(
            "lote_consumido",
            "El lote de esta compra ya se consumió entero en una guía R: no queda nada "
            "contra lo que armar la que diría que vino armada.",
        )

    return None


# LA ETIQUETA CORTA DEL BOTÓN, al lado de los códigos y no en la plantilla.
# Son dos formas de decir el MISMO motivo —el párrafo de la pantalla y el
# renglón del menú— y separadas se despegan: el día que alguien agregue un
# motivo, el texto largo saldría y el corto no, o peor, dirían cosas
# distintas. Es "las dos mitades de un link viajan juntas" (corolario 56)
# en su versión más chica.
#
# Los dos que esconden el botón no llevan etiqueta a propósito: si tuvieran
# una, invitarían a mostrarlos.
ETIQUETAS_CORTAS = {
    "sin_fecha_de_lote": "Vino armada — sin fecha de recepción",
    "anterior_al_corte": "Vino armada — es anterior al corte",
    "lote_consumido": "Vino armada — su lote ya se usó",
}


def etiqueta_del_boton(motivo: MotivoVinoArmada | None) -> str:
    """Lo que dice el renglón del menú: el rótulo pelado si se puede, o el motivo."""
    if motivo is None:
        return "Vino armada"
    return ETIQUETAS_CORTAS.get(motivo.codigo, "Vino armada — no se puede")


def se_muestra_el_boton(motivo: MotivoVinoArmada | None) -> bool:
    """Si el renglón aparece en el menú. Ver MOTIVOS_QUE_ESCONDEN_EL_BOTON."""
    return motivo is None or motivo.codigo not in MOTIVOS_QUE_ESCONDEN_EL_BOTON

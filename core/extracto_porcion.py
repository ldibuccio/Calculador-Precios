"""El extracto de una porción del depósito en un día — puro, sin tocar la base.

QUÉ ES UNA PORCIÓN, porque de acá sale todo lo demás: en el piso no hay "un
artículo con un total", hay pilas distintas. Los cajones que vinieron del
puesto son una; las cajas ya armadas de cada ficha son otra cada una; la
segunda es otra. "Tomate Perita" y "Tomate Perita Caja Día" no se pueden
sumar ni restar entre sí: una está en cajones y la otra en cajas de 6 kg.

LA REGLA DE FONDO, y es la que hace esta pantalla confiable: **acá no se
calcula ningún saldo**. Las dos puntas —"Venía de ayer" y "Quedó"— las pone
quien llama, sacadas de la MISMA función que dibuja el Remanente. Este
módulo solo reparte los eventos del día entre las porciones y arma los
renglones del medio. Sumar los eventos para obtener el saldo sería una
quinta versión de la cuenta de stock, y las cuatro que existen ya se
separaron entre sí una vez cada una.

Por eso existe SIN_EXPLICAR: cuando `venía + Σ eventos` no da `quedó`, la
diferencia va en un renglón propio y con su nombre, nunca repartida entre
los otros ni escondida. Es el mismo invariante que Rentabilidad — lo que no
se puede calcular NO suma como cero. Se espera que aparezca poco; el caso
conocido es el PISO de la cuenta por ficha (cajas_armadas_por_ficha informa
solo `disponibles > 0`, así que el déficit de una ficha queda adentro de los
sueltos sin ser ningún evento).
"""

SIN_EXPLICAR = "Sin explicar"

# Qué mueve cada porción, y NO es lo mismo para las tres:
#
# - SUELTOS (el nombre pelado): compras, reprocesos tomados, la primera de
#   una guía SIN ficha, los armados sin ficha, reingresos, mermas y ajustes.
# - CAJAS DE UNA FICHA: SOLO dos cosas, la primera de un reproceso asignado a
#   esa ficha y los armados de esa ficha. Ni la merma ni el ajuste pueden
#   tocarlas: están escritos por ARTÍCULO a propósito (ver el Cotejo, "un
#   ajuste de stock es por ARTÍCULO: mueve el total, no reparte entre
#   fichas"). Consecuencia: hoy NO HAY FORMA de registrar una merma de cajas
#   armadas, y la baja se la come el nombre pelado. Está anotado como
#   pendiente en docs/diseno_base_datos.md.
# - SEGUNDA: la segunda de los reprocesos, los rechazos mandados a segunda y
#   los remitos al Puesto.

ETIQUETAS_MOVIMIENTO = {
    "ajuste": "Ajuste",
    "merma": "Merma",
    "reingreso_rechazo": "Reingreso",
    "stock_inicial": "Stock inicial",
    "cierre_modelo_viejo": "Cierre del modelo viejo",
}


def _renglon(descripcion, bultos):
    return {"descripcion": descripcion, "bultos": round(bultos, 2)}


def _eventos_de_sueltos(eventos) -> list[dict]:
    filas = []
    for compra in eventos["compras"]:
        filas.append(_renglon(f"Compra recibida — {compra['proveedor']}", compra["bultos"]))
    for rp in eventos["reprocesos"]:
        if rp["tomados"]:
            # A DÓNDE FUE EL OTRO LADO. Desde esta pila el reproceso solo
            # saca, y eso está bien —los cajones y las cajas son pilas
            # distintas—, pero un renglón que solo dice "−25" se lee como
            # mercadería que falta. Y es peor donde la conversión no es 1 a
            # 1: el mango entra en cajones de 12u y sale en cajas de 10u, así
            # que de 25 salen 30 y ninguno de los dos números explica al otro.
            filas.append(_renglon(
                f"Reproceso R{rp['id']}" + (f" → {rp['destino']}" if rp.get("destino") else ""),
                -rp["tomados"],
            ))
        # La primera SIN ficha no tiene pila propia: queda con los sueltos.
        # Es la guía R "sin asignar", y acá se ve dónde cayó.
        if rp["primera"] and rp["ficha_id"] is None:
            filas.append(_renglon(f"Reproceso R{rp['id']} (sin asignar)", rp["primera"]))
    for armado in eventos["armados"]:
        if armado["ficha_id"] is None:
            filas.append(_renglon(
                f"Armado pedido {armado['cliente']} {armado['sucursal'] or ''}".strip(),
                -armado["bultos"],
            ))
    for mov in eventos["movimientos"]:
        # El rechazo que NO volvió al stock no mueve esta pila: se fue al
        # pool de segunda, y ahí aparece.
        if mov["tipo"] == "reingreso_rechazo" and mov["destino_rechazo"] not in (None, "stock"):
            continue
        etiqueta = ETIQUETAS_MOVIMIENTO.get(mov["tipo"], mov["tipo"])
        filas.append(_renglon(f"{etiqueta} — {mov['motivo']}", mov["cantidad"]))
    return filas


def _eventos_de_ficha(eventos, ficha_id: int) -> list[dict]:
    filas = []
    for rp in eventos["reprocesos"]:
        if rp["primera"] and rp["ficha_id"] == ficha_id:
            filas.append(_renglon(f"Reproceso R{rp['id']}", rp["primera"]))
    for armado in eventos["armados"]:
        if armado["ficha_id"] == ficha_id:
            filas.append(_renglon(
                f"Armado pedido {armado['cliente']} {armado['sucursal'] or ''}".strip(),
                -armado["bultos"],
            ))
    return filas


def _eventos_de_segunda(eventos) -> list[dict]:
    filas = []
    for rp in eventos["reprocesos"]:
        if rp["segunda"]:
            filas.append(_renglon(f"Segunda del reproceso R{rp['id']}", rp["segunda"]))
    for mov in eventos["movimientos"]:
        if mov["destino_rechazo"] in ("segunda", "reproceso") and mov["bultos_segunda"]:
            filas.append(_renglon(f"Rechazo a segunda — {mov['motivo']}", mov["bultos_segunda"]))
    for remito in eventos["remitos"]:
        filas.append(_renglon("Remito al Puesto", -remito["bultos"]))
    return filas


def armar_extracto(eventos: dict, venia: float, quedo: float,
                   ficha_id: int | None = None, es_segunda: bool = False) -> dict:
    """Los renglones del extracto de UNA porción, con sus dos puntas ya dadas.

    `venia` y `quedo` NO se calculan acá: entran hechos, de
    _remanente_a_fecha del día anterior y del día. Eso es lo que garantiza
    que el saldo final sea EXACTAMENTE el que muestra el Remanente para esa
    porción — no uno que se le tiene que parecer.

    Si los eventos no explican la diferencia entre las dos puntas, el resto
    va en un renglón "Sin explicar". Nunca se reparte ni se omite: un
    faltante escondido adentro de otro renglón es peor que uno a la vista.
    """
    if es_segunda:
        filas = _eventos_de_segunda(eventos)
    elif ficha_id is not None:
        filas = _eventos_de_ficha(eventos, ficha_id)
    else:
        filas = _eventos_de_sueltos(eventos)

    explicado = round(sum(f["bultos"] for f in filas), 2)
    sin_explicar = round(quedo - venia - explicado, 2)
    if sin_explicar:
        filas.append(_renglon(SIN_EXPLICAR, sin_explicar))

    return {
        "venia": round(venia, 2),
        "filas": filas,
        "quedo": round(quedo, 2),
        "sin_explicar": sin_explicar,
    }

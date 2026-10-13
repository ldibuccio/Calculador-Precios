"""CARTERA DE CHEQUES: aplicar con las capturas de ENDOSOS de ECHEQ (dueño, 13/10).

Lionel sube varias capturas de "Operación pendiente de firma" del home
banking. Cada una trae el proveedor a quien se endosa (CUIT y razón social) y
uno o varios cheques (número, fecha de pago, monto, emisor). La IA lee cada
foto (`core.lector_cheques.extraer_endoso`); acá se arma un renglón por
cheque para confirmar antes de guardar, y se dice qué tiene mal cada uno.

- El cheque de la cartera: por número (sin ceros adelante) Y monto, entre
  los que están EN CARTERA. Si no está, si ya salió o si el monto no
  coincide, el renglón va en rojo con el motivo y no se guarda.
- El proveedor: por su CUIT (`proveedores.cuit`). Si no hay uno solo con ese
  CUIT, se elige de la lista, y al guardar el proveedor elegido se queda con
  el CUIT leído si no tenía (la próxima vez se encuentra solo).
- El mismo cheque (número y monto) en dos fotos se toma una vez, y se avisa.

DEPÓSITOS (dueño, 13/10): la captura también puede ser de un DEPÓSITO
("Cuenta de Depósito: CC$ 191-220-000247/7" en vez del CUIT del proveedor).
Cada cheque se clasifica por SU foto: los de una foto de depósito salen con
"Depósito en cuenta", sin proveedor y con la cuenta, aunque en la misma tanda
haya fotos de endosos. Lo que decide si hace falta proveedor es el concepto
elegido en el renglón (su destino), no la foto: si se cambia, se pide.
"""
from datetime import date

from core.cheques import EN_CARTERA, NOMBRES_DE_ESTADO, numero_normalizado
from core.listado_cheques import cuit_de_la_celda, cuit_valido, fecha_de_la_celda, importe_de_la_celda


def _monto(valor) -> float | None:
    try:
        return round(float(str(valor).replace(",", ".")), 2) if str(valor or "").strip() else None
    except ValueError:
        return None


def _proveedor_por_cuit(cuit: str, proveedores: list[dict]) -> int | None:
    """El proveedor con ese CUIT, si hay UNO solo (dos con el mismo CUIT no se
    adivinan: se elige)."""
    if not cuit_valido(cuit):
        return None
    con_ese = [p["id"] for p in proveedores if p.get("cuit") == cuit]
    return con_ese[0] if len(con_ese) == 1 else None


def _el_de_la_cartera(numero: str, importe: float | None, en_cartera: list[dict]) -> int | None:
    """El cheque en cartera con ese número y ese monto, si es UNO solo."""
    candidatos = [c["id"] for c in en_cartera
                  if numero_normalizado(c["numero"]) == numero_normalizado(numero)
                  and importe is not None and round(float(c["importe"]), 2) == importe]
    return candidatos[0] if len(candidatos) == 1 else None


def es_un_deposito(leida: dict) -> bool:
    """La foto es de un depósito si la IA leyó una cuenta de depósito (o dijo
    que es un depósito)."""
    return bool(str(leida.get("cuenta_deposito") or "").strip()) or leida.get("tipo") == "deposito"


def renglones_de_los_endosos(leidas: list[dict], *, cheques: list[dict], proveedores: list[dict],
                             concepto_id: int | None, concepto_deposito_id: int | None,
                             hoy: date) -> tuple[list[dict], list[str]]:
    """Un renglón por cheque de las fotos, y los avisos.

    `leidas` es una por foto, en orden: lo que devolvió la IA (o {"error"}).
    `cheques` son TODOS los de la base, con su estado (para decir por qué uno
    no se puede aplicar). El mismo número en dos fotos se toma una vez."""
    en_cartera = [c for c in cheques if c["estado"] in EN_CARTERA]
    renglones, avisos, visto_en = [], [], {}
    for foto, leida in enumerate(leidas):
        if leida.get("error"):
            avisos.append(f"La foto {foto + 1} no se pudo leer: {leida['error']}")
            continue
        deposito = es_un_deposito(leida)
        cuenta = str(leida.get("cuenta_deposito") or "").strip()
        cuit = "" if deposito else cuit_de_la_celda(leida.get("proveedor_cuit"))
        nombre = "" if deposito else str(leida.get("proveedor_nombre") or "").strip()
        for cheque in leida.get("cheques") or []:
            numero = str(cheque.get("numero") or "").strip()
            importe = importe_de_la_celda(cheque.get("importe"))
            # El MISMO cheque es el mismo número (sin ceros adelante) y el mismo
            # monto: dos de distinto banco pueden tener el mismo número.
            clave = (numero_normalizado(numero), _monto(importe))
            if clave[0] and clave in visto_en:
                avisos.append(f"El cheque {numero} está en las fotos {visto_en[clave] + 1} y {foto + 1}: "
                              "se toma una sola vez.")
                continue
            if clave[0]:
                visto_en[clave] = foto
            renglones.append({
                "foto": foto, "numero": numero, "fecha_pago": fecha_de_la_celda(cheque.get("fecha_pago")),
                "importe": importe, "emisor": str(cheque.get("emisor") or "").strip(),
                "cheque_id": _el_de_la_cartera(numero, _monto(importe), en_cartera),
                "proveedor_cuit": cuit, "proveedor_nombre": nombre,
                "proveedor_id": _proveedor_por_cuit(cuit, proveedores),
                "cuenta_deposito": cuenta, "deposito": deposito,
                "concepto_id": concepto_deposito_id if deposito else concepto_id,
                "fecha": hoy.isoformat(), "sacar": False,
            })
    if not renglones and not avisos:
        avisos.append("No se encontró ningún cheque en las fotos.")
    return renglones, avisos


def _moneda(valor) -> str:
    texto = f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return "$" + (texto[:-3] if texto.endswith(",00") else texto)


def problemas_de_los_endosos(renglones: list[dict], cheques: list[dict], *,
                             destinos: dict) -> list[list[str]]:
    """Por renglón, lo que tiene mal (vacío si se puede guardar). `destinos`:
    el destino de cada concepto por id (el proveedor lo pide solo el que deja
    el cheque "entregado")."""
    por_id = {c["id"]: c for c in cheques}
    elegidos: dict = {}
    for r in renglones:
        if r.get("cheque_id") and not r.get("sacar"):
            elegidos[r["cheque_id"]] = elegidos.get(r["cheque_id"], 0) + 1
    problemas = []
    for r in renglones:
        mal = []
        importe = _monto(r.get("importe"))
        cheque = por_id.get(r.get("cheque_id"))
        if cheque is None:
            mismos = [c for c in cheques if numero_normalizado(c["numero"]) == numero_normalizado(r.get("numero"))]
            en_cartera = [c for c in mismos if c["estado"] in EN_CARTERA]
            if not mismos:
                mal.append("no está en la cartera")
            elif not en_cartera:
                estado = NOMBRES_DE_ESTADO.get(mismos[0]["estado"], mismos[0]["estado"]).lower()
                mal.append(f"ya salió: está {estado}")
            elif importe is not None and all(round(float(c["importe"]), 2) != importe for c in en_cartera):
                mal.append("el monto no coincide: en la cartera es "
                           + " o ".join(_moneda(c["importe"]) for c in en_cartera))
            else:
                mal.append("elegí el cheque de la cartera")
        elif cheque["estado"] not in EN_CARTERA:
            mal.append(f"ya salió: está {NOMBRES_DE_ESTADO.get(cheque['estado'], cheque['estado']).lower()}")
        elif importe is None or round(float(cheque["importe"]), 2) != importe:
            mal.append(f"el monto no coincide: en la cartera es {_moneda(cheque['importe'])}")
        if cheque is not None and elegidos.get(cheque["id"], 0) > 1:
            mal.append("ese cheque está en otro renglón")
        if destinos.get(r.get("concepto_id")) == "entregado" and not r.get("proveedor_id"):
            mal.append("elegí el proveedor")
        if not r.get("concepto_id"):
            mal.append("elegí el concepto")
        try:
            date.fromisoformat(str(r.get("fecha") or ""))
        except ValueError:
            mal.append("falta la fecha de salida")
        problemas.append(mal)
    return problemas

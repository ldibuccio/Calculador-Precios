"""APLICAR CHEQUES (dueño, 16/10): UN SOLO FLUJO de dos pasos.

Reemplaza los tres caminos de antes (capturas de ECHEQ, una foto o archivo, y
la carga a mano con un solo día, motivo, proveedor y cuenta para todos).

PASO 1, elegir: se suben capturas, fotos o archivos (uno o muchos: endosos y
depósitos de home banking, boletas de depósito, recibos de entrega) y/o se
tildan cheques de la cartera a mano. Las dos cosas juntas también.

PASO 2, revisar: un renglón por cheque, AGRUPADO POR ARCHIVO ("Foto 1",
"Foto 2"... y "Elegidos a mano"). Lo leído viene puesto (el proveedor por su
CUIT, la cuenta por su número) y TODO se cambia: renglón por renglón, por
grupo desde su encabezado, o con "Para todos" (a los tildados). En rojo,
primero y abiertos, los que tienen problema; "Confirmar todos" guarda los que
están bien, cada uno con la foto de su archivo.

- El cheque de la cartera: por número (sin ceros adelante) Y monto, entre
  los que están EN CARTERA. Si no está, ya salió o el monto no coincide, va
  en rojo con el motivo.
- El proveedor: por su CUIT, si hay UNO con ese CUIT. Al guardar, el elegido
  a mano se queda con el CUIT leído si no tenía.
- La cuenta de un depósito: por el número leído (`core.cuentas.cuenta_por_numero`);
  si la base tiene un solo banco, ese.
- El mismo cheque (número y monto) en dos archivos se toma una vez y se
  avisa. Uno tildado a mano que ya vino en un archivo, también.
- El motivo de un archivo que dice a quién va: un endoso es "Pago a
  proveedor", un depósito "Depósito en cuenta". Una boleta o un recibo que no
  lo dice deja el grupo con el destino vacío, para elegirlo.

Nada de acá toca la base.
"""
from datetime import date

from core.cheques import EN_CARTERA, NOMBRES_DE_ESTADO, numero_normalizado
from core.cuentas import cuenta_por_numero
from core.listado_cheques import cuit_de_la_celda, cuit_valido, fecha_de_la_celda, importe_de_la_celda

A_MANO = -1


def _monto(valor) -> float | None:
    """El monto como número, se haya leído o tipeado ("1.234,56", "1234.56")."""
    texto = importe_de_la_celda(valor)
    try:
        return round(float(texto), 2) if texto else None
    except ValueError:
        return None


def _moneda(valor) -> str:
    texto = f"{float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return "$" + (texto[:-3] if texto.endswith(",00") else texto)


def proveedor_por_cuit(cuit: str, proveedores: list[dict]) -> int | None:
    """El proveedor con ese CUIT, si hay UNO solo (dos con el mismo no se adivinan)."""
    if not cuit_valido(cuit):
        return None
    con_ese = [p["id"] for p in proveedores if p.get("cuit") == cuit]
    return con_ese[0] if len(con_ese) == 1 else None


def el_de_la_cartera(numero: str, importe: float | None, en_cartera: list[dict]) -> int | None:
    """El cheque en cartera con ese número y ese monto, si es UNO solo."""
    candidatos = [c["id"] for c in en_cartera
                  if numero_normalizado(c["numero"]) == numero_normalizado(numero)
                  and importe is not None and round(float(c["importe"]), 2) == importe]
    return candidatos[0] if len(candidatos) == 1 else None


def es_un_deposito(leida: dict) -> bool:
    """El archivo es de un depósito si se leyó una cuenta de depósito o dice que lo es."""
    return bool(str(leida.get("cuenta_deposito") or "").strip()) or leida.get("tipo") == "deposito"


def _renglon_vacio(hoy: date) -> dict:
    return {"foto": A_MANO, "numero": "", "fecha_pago": "", "importe": "", "emisor": "", "cheque_id": None,
            "proveedor_cuit": "", "proveedor_nombre": "", "proveedor_id": None, "cuenta_deposito": "",
            "cuenta_id": None, "concepto_id": None, "fecha": hoy.isoformat(), "deposito": False, "sacar": False,
            "tildado": False}


def renglones_de_lo_leido(leidas: list[dict], *, cheques: list[dict], proveedores: list[dict], bancos: list[dict],
                          concepto_pago: int | None, concepto_deposito: int | None,
                          hoy: date) -> tuple[list[dict], list[str]]:
    """Un renglón por cheque de los archivos, y los avisos. `leidas` es una por
    archivo, en orden (lo que devolvió la IA, o {"error"}); `cheques` TODOS
    los de la base con su estado; `bancos` las cuentas de banco activas."""
    en_cartera = [c for c in cheques if c["estado"] in EN_CARTERA]
    renglones, avisos, visto_en = [], [], {}
    for foto, leida in enumerate(leidas):
        if leida.get("error"):
            avisos.append(f"La foto {foto + 1} no se pudo leer: {leida['error']}")
            continue
        deposito = es_un_deposito(leida)
        cuenta_texto = str(leida.get("cuenta_deposito") or "").strip()
        cuit = "" if deposito else cuit_de_la_celda(leida.get("proveedor_cuit"))
        nombre = "" if deposito else str(leida.get("proveedor_nombre") or "").strip()
        if deposito:
            leida_cuenta = cuenta_por_numero(cuenta_texto, bancos)
            cuenta_id = leida_cuenta["id"] if leida_cuenta else (bancos[0]["id"] if len(bancos) == 1 else None)
            concepto = concepto_deposito
        else:
            cuenta_id = None
            concepto = concepto_pago if (cuit or nombre or leida.get("tipo") == "endoso") else None
        cheques_del_archivo = leida.get("cheques") or []
        if not cheques_del_archivo:
            avisos.append(f"En la foto {foto + 1} no se encontró ningún cheque.")
        for cheque in cheques_del_archivo:
            numero = str(cheque.get("numero") or "").strip()
            importe = importe_de_la_celda(cheque.get("importe"))
            clave = (numero_normalizado(numero), _monto(importe))
            if clave[0] and clave in visto_en:
                avisos.append(f"El cheque {numero} está en las fotos {visto_en[clave] + 1} y {foto + 1}: "
                              "se toma una sola vez.")
                continue
            if clave[0]:
                visto_en[clave] = foto
            renglones.append(dict(
                _renglon_vacio(hoy), foto=foto, numero=numero, importe=importe,
                fecha_pago=fecha_de_la_celda(cheque.get("fecha_pago")),
                emisor=str(cheque.get("emisor") or "").strip(),
                cheque_id=el_de_la_cartera(numero, _monto(importe), en_cartera),
                proveedor_cuit=cuit, proveedor_nombre=nombre, proveedor_id=proveedor_por_cuit(cuit, proveedores),
                cuenta_deposito=cuenta_texto, cuenta_id=cuenta_id, concepto_id=concepto, deposito=deposito))
    return renglones, avisos


def renglones_elegidos_a_mano(ids: list[int], *, cheques: list[dict], ya: list[dict],
                              hoy: date) -> tuple[list[dict], list[str]]:
    """Los cheques tildados a mano, en el grupo "Elegidos a mano", sin destino.
    Uno que ya vino en un archivo no se repite: se avisa."""
    por_id = {c["id"]: c for c in cheques}
    de_un_archivo = {r["cheque_id"]: r["foto"] for r in ya if r.get("cheque_id")}
    renglones, avisos = [], []
    for cheque_id in ids:
        cheque = por_id.get(cheque_id)
        if cheque is None:
            continue
        if cheque_id in de_un_archivo:
            avisos.append(f"El cheque {cheque['numero']} ya está en la foto {de_un_archivo[cheque_id] + 1}: "
                          "se toma una sola vez.")
            continue
        renglones.append(dict(_renglon_vacio(hoy), numero=cheque["numero"], cheque_id=cheque_id,
                              importe=f"{float(cheque['importe']):.2f}",
                              fecha_pago=cheque["fecha_pago"].isoformat() if cheque.get("fecha_pago") else "",
                              emisor=cheque.get("de_quien") or ""))
    return renglones, avisos


# Los problemas del DESTINO (a dónde va): el resto son del cheque mismo, y
# solo esos abren el número, el monto y el cheque de la cartera para corregir.
PROBLEMAS_DEL_DESTINO = frozenset({"elegí el motivo", "elegí el proveedor", "elegí la cuenta",
                                   "falta el día de salida"})


def es_del_cheque(problemas: list[str]) -> bool:
    return any(p not in PROBLEMAS_DEL_DESTINO for p in problemas)


def problemas_de_las_salidas(renglones: list[dict], cheques: list[dict], *, destinos: dict,
                               bancos: list[dict]) -> list[list[str]]:
    """Por renglón, lo que tiene mal (vacío si se puede guardar). `destinos`:
    el destino de cada motivo por id. Un pago pide el proveedor; un depósito
    pide la cuenta si la base tiene cuentas de banco."""
    por_id = {c["id"]: c for c in cheques}
    ids_de_bancos = {b["id"] for b in bancos}
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
                mal.append(f"ya salió: está {NOMBRES_DE_ESTADO.get(mismos[0]['estado'], mismos[0]['estado']).lower()}")
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
        destino = destinos.get(r.get("concepto_id"))
        if not r.get("concepto_id"):
            mal.append("elegí el motivo")
        elif destino == "entregado" and not r.get("proveedor_id"):
            mal.append("elegí el proveedor")
        elif destino == "depositado" and ids_de_bancos and r.get("cuenta_id") not in ids_de_bancos:
            mal.append("elegí la cuenta")
        try:
            date.fromisoformat(str(r.get("fecha") or ""))
        except ValueError:
            mal.append("falta el día de salida")
        problemas.append(mal)
    return problemas


def buscar_otra_vez_en_la_cartera(renglones: list[dict], cheques: list[dict]) -> None:
    """El renglón sin cheque de la cartera lo vuelve a buscar con su número y
    su monto: corregido lo que se leyó mal, se encuentra solo."""
    en_cartera = [c for c in cheques if c["estado"] in EN_CARTERA]
    for r in renglones:
        if not r.get("cheque_id"):
            r["cheque_id"] = el_de_la_cartera(r.get("numero") or "", _monto(r.get("importe")), en_cartera)


def completar_la_cuenta_unica(renglones: list[dict], *, destinos: dict, bancos: list[dict]) -> None:
    """Con UN solo banco, el depósito que no dice la cuenta va a ese (dueño, 15/10)."""
    if len(bancos) != 1:
        return
    for r in renglones:
        if destinos.get(r.get("concepto_id")) == "depositado" and not r.get("cuenta_id"):
            r["cuenta_id"] = bancos[0]["id"]


def _cambiar(r: dict, cambios: dict) -> None:
    for campo in ("concepto_id", "proveedor_id", "cuenta_id"):
        if cambios.get(campo):
            r[campo] = cambios[campo]
    if cambios.get("fecha"):
        r["fecha"] = cambios["fecha"]


def poner_en_el_grupo(renglones: list[dict], foto: int, cambios: dict) -> int:
    """Lo elegido en el encabezado de un grupo, a todos sus renglones (los
    sacados no). Devuelve a cuántos."""
    destino = [r for r in renglones if r["foto"] == foto and not r.get("sacar")]
    for r in destino:
        _cambiar(r, cambios)
    return len(destino)


def poner_a_los_tildados(renglones: list[dict], cambios: dict, *, sin_tildar_tambien: bool) -> int | None:
    """"Para todos": a los TILDADOS. Si no hay ninguno tildado, a todos solo
    con `sin_tildar_tambien` (se pregunta antes); si no, None (no cambió
    nada, hay que preguntar)."""
    tildados = [r for r in renglones if r.get("tildado") and not r.get("sacar")]
    if not tildados and not sin_tildar_tambien:
        return None
    destino = tildados or [r for r in renglones if not r.get("sacar")]
    for r in destino:
        _cambiar(r, cambios)
    return len(destino)


def grupos_de_las_salidas(renglones: list[dict], problemas: list[list[str]], *, nombre_de_proveedor: dict,
           nombre_de_cuenta: dict, nombre_de_concepto: dict) -> list[dict]:
    """Los grupos para la pantalla, en orden: los que tienen algún problema
    primero, después por archivo, "Elegidos a mano" al final. En cada grupo,
    los renglones con problema primero. El destino del encabezado es el
    proveedor o la cuenta que comparten TODOS sus renglones; si no, "a elegir"."""
    por_foto: dict = {}
    for i, r in enumerate(renglones):
        por_foto.setdefault(r["foto"], []).append(i)
    salida = []
    for foto, indices in por_foto.items():
        vivos = [i for i in indices if not renglones[i].get("sacar")]
        con_problema = [i for i in vivos if problemas[i]]
        proveedores = {renglones[i].get("proveedor_id") for i in vivos}
        cuentas = {renglones[i].get("cuenta_id") for i in vivos}
        motivos = {renglones[i].get("concepto_id") for i in vivos}
        if len(proveedores) == 1 and None not in proveedores:
            destino = nombre_de_proveedor.get(next(iter(proveedores)), "")
        elif len(cuentas) == 1 and None not in cuentas:
            destino = nombre_de_cuenta.get(next(iter(cuentas)), "")
        elif len(motivos) == 1 and None not in motivos:
            destino = nombre_de_concepto.get(next(iter(motivos)), "")
        else:
            destino = ""
        salida.append({
            "foto": foto, "titulo": "Elegidos a mano" if foto == A_MANO else f"Foto {foto + 1}",
            "destino": destino, "cuantos": len(vivos), "con_problema": len(con_problema),
            "total": round(sum(_monto(renglones[i].get("importe")) or 0 for i in vivos), 2),
            "indices": sorted(indices, key=lambda i: (not problemas[i] or bool(renglones[i].get("sacar")), i)),
            "concepto_id": next(iter(motivos)) if len(motivos) == 1 else None,
            "proveedor_id": next(iter(proveedores)) if len(proveedores) == 1 else None,
            "cuenta_id": next(iter(cuentas)) if len(cuentas) == 1 else None,
        })
    return sorted(salida, key=lambda g: (g["con_problema"] == 0, g["foto"] == A_MANO, g["foto"]))

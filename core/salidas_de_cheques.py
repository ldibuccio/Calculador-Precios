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
- El motivo: un depósito es "Depósito en cuenta"; todo lo demás arranca en
  "Pago a proveedor" (dueño, 16/10), también lo tildado a mano y lo que no
  dice a dónde va. Se cambia por renglón, por grupo o con "Para todos".
- El proveedor: de la lista (por su CUIT) o ESCRITO A MANO, alguien que no
  está en proveedores (la lista del Mercado Central): se guarda como texto
  en la salida, sin crear un proveedor (dueño, 16/10). Si el CUIT leído no es
  de ninguno, viene a mano con la razón social leída ya escrita (dueño,
  17/10), y se puede elegir de la lista si es uno que está con otro nombre.
- La cuenta arranca en el Banco Credicoop (o el único banco que haya), en
  cada renglón, en cada grupo y en "Para todos" (dueño, 17/10).
- Cada grupo dice lo que se leyó de su archivo: "Endoso a <razón social> ·
  CUIT <cuit>" o "Depósito en cuenta <número>".

Nada de acá toca la base.
"""
from datetime import date

from core.cheques import EN_CARTERA, NOMBRES_DE_ESTADO, numero_normalizado
from core.cuentas import cuenta_por_numero
from core.listado_cheques import cuit_de_la_celda, cuit_valido, fecha_de_la_celda, importe_de_la_celda

A_MANO = -1
# La cuenta en que se deposita, si no se leyó otra (dueño, 17/10): la de
# este nombre; si no hay, el único banco.
BANCO_POR_DEFECTO = "credicoop"


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


def cuenta_por_defecto(bancos: list[dict]) -> int | None:
    """El Banco Credicoop (por su nombre); si no está, el único banco; si hay
    varios y ninguno es ese, ninguno."""
    credicoop = [b["id"] for b in bancos if BANCO_POR_DEFECTO in str(b.get("nombre") or "").lower()]
    if credicoop:
        return credicoop[0]
    return bancos[0]["id"] if len(bancos) == 1 else None


def cuit_con_guiones(cuit: str) -> str:
    digitos = "".join(c for c in str(cuit or "") if c.isdigit())
    return f"{digitos[:2]}-{digitos[2:10]}-{digitos[10:]}" if len(digitos) == 11 else str(cuit or "")


def lo_leido(renglon: dict) -> str:
    """Lo que dice el archivo de dónde salió el renglón, en una línea."""
    if renglon.get("deposito"):
        cuenta = str(renglon.get("cuenta_deposito") or "").strip()
        return f"Depósito en cuenta {cuenta}" if cuenta else "Depósito (no se leyó la cuenta)"
    nombre = str(renglon.get("proveedor_nombre") or "").strip()
    cuit = str(renglon.get("proveedor_cuit") or "").strip()
    if not (nombre or cuit):
        return ""
    return f"Endoso a {nombre or 'sin nombre'}" + (f" · CUIT {cuit_con_guiones(cuit)}" if cuit else "")


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
            "proveedor_cuit": "", "proveedor_nombre": "", "proveedor_id": None, "proveedor_a_mano": "",
            "cuenta_deposito": "",
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
        proveedor_id = None if deposito else proveedor_por_cuit(cuit, proveedores)
        if deposito:
            # Un número leído que no es de ninguna cuenta queda sin cuenta: lo
            # decide completar_la_cuenta_por_defecto.
            leida_cuenta = cuenta_por_numero(cuenta_texto, bancos)
            cuenta_id = leida_cuenta["id"] if leida_cuenta else (None if cuenta_texto else cuenta_por_defecto(bancos))
            concepto = concepto_deposito
        else:
            cuenta_id = cuenta_por_defecto(bancos)
            concepto = concepto_pago
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
                proveedor_cuit=cuit, proveedor_nombre=nombre, proveedor_id=proveedor_id,
                # Sin proveedor con ese CUIT: a mano, con la razón social leída (dueño, 17/10).
                proveedor_a_mano=nombre if proveedor_id is None else "",
                cuenta_deposito=cuenta_texto, cuenta_id=cuenta_id, concepto_id=concepto, deposito=deposito))
    return renglones, avisos


def renglones_elegidos_a_mano(ids: list[int], *, cheques: list[dict], ya: list[dict], hoy: date,
                              concepto_pago: int | None = None,
                              bancos: list[dict] = ()) -> tuple[list[dict], list[str]]:
    """Los cheques tildados a mano, en el grupo "Elegidos a mano", con "Pago a
    proveedor" y sin proveedor.
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
                              concepto_id=concepto_pago, cuenta_id=cuenta_por_defecto(list(bancos)),
                              importe=f"{float(cheque['importe']):.2f}",
                              fecha_pago=cheque["fecha_pago"].isoformat() if cheque.get("fecha_pago") else "",
                              emisor=cheque.get("de_quien") or ""))
    return renglones, avisos


# Los problemas del DESTINO (a dónde va): el resto son del cheque mismo, y
# solo esos abren el número, el monto y el cheque de la cartera para corregir.
PROBLEMAS_DEL_DESTINO = frozenset({"elegí el motivo", "elegí el proveedor", "elegí la cuenta",
                                   "falta el día de salida",
                                   "elegí el proveedor de la lista o escribilo, no los dos"})


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
        elif destino == "entregado" and not r.get("proveedor_id") and not str(r.get("proveedor_a_mano") or "").strip():
            mal.append("elegí el proveedor")
        elif destino == "entregado" and r.get("proveedor_id") and str(r.get("proveedor_a_mano") or "").strip():
            mal.append("elegí el proveedor de la lista o escribilo, no los dos")
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


def completar_la_cuenta_por_defecto(renglones: list[dict], *, bancos: list[dict]) -> None:
    """El renglón sin cuenta arranca en la de por defecto (el Credicoop, o el
    único banco: dueño, 15/10 y 17/10), sea o no un depósito: si se le cambia
    el motivo a depósito, ya la tiene. Menos el depósito que leyó un número de
    cuenta que no es de ninguna: ese se elige (sería plata anotada en otro
    banco), salvo con UN solo banco, que no tiene selector y va a ese."""
    defecto = cuenta_por_defecto(bancos)
    for r in renglones:
        leyo_otra = (len(bancos) > 1 and r.get("deposito") and str(r.get("cuenta_deposito") or "").strip()
                     and cuenta_por_numero(str(r["cuenta_deposito"]), bancos) is None)
        if not r.get("cuenta_id") and not leyo_otra:
            r["cuenta_id"] = defecto


def _cambiar(r: dict, cambios: dict) -> None:
    for campo in ("concepto_id", "proveedor_id", "cuenta_id"):
        if cambios.get(campo):
            r[campo] = cambios[campo]
    # El proveedor es de la lista O escrito a mano: poner uno saca el otro.
    if cambios.get("proveedor_id"):
        r["proveedor_a_mano"] = ""
    elif str(cambios.get("proveedor_a_mano") or "").strip():
        r["proveedor_a_mano"], r["proveedor_id"] = " ".join(str(cambios["proveedor_a_mano"]).split()), None
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
           nombre_de_cuenta: dict, nombre_de_concepto: dict, destinos: dict | None = None) -> list[dict]:
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
        a_mano = {str(renglones[i].get("proveedor_a_mano") or "").strip() for i in vivos}
        cuentas = {renglones[i].get("cuenta_id") for i in vivos}
        motivos = {renglones[i].get("concepto_id") for i in vivos}
        # La cuenta nombra al grupo solo si es de depósitos: todos arrancan con
        # el Credicoop puesto, también los endosos (dueño, 17/10).
        de_deposito = destinos is None or all((destinos or {}).get(m) == "depositado" for m in motivos)
        if len(proveedores) == 1 and None not in proveedores:
            destino = nombre_de_proveedor.get(next(iter(proveedores)), "")
        elif len(a_mano) == 1 and "" not in a_mano:
            destino = next(iter(a_mano))
        elif de_deposito and len(cuentas) == 1 and None not in cuentas:
            destino = nombre_de_cuenta.get(next(iter(cuentas)), "")
        elif len(motivos) == 1 and None not in motivos:
            destino = nombre_de_concepto.get(next(iter(motivos)), "")
        else:
            destino = ""
        salida.append({
            "foto": foto, "titulo": "Elegidos a mano" if foto == A_MANO else f"Foto {foto + 1}",
            "leido": "" if foto == A_MANO else next((lo_leido(renglones[i]) for i in indices if lo_leido(renglones[i])),
                                                    ""),
            "proveedor_a_mano": next(iter(a_mano)) if len(a_mano) == 1 else "",
            "destino": destino, "cuantos": len(vivos), "con_problema": len(con_problema),
            "total": round(sum(_monto(renglones[i].get("importe")) or 0 for i in vivos), 2),
            "indices": sorted(indices, key=lambda i: (not problemas[i] or bool(renglones[i].get("sacar")), i)),
            "concepto_id": next(iter(motivos)) if len(motivos) == 1 else None,
            "proveedor_id": next(iter(proveedores)) if len(proveedores) == 1 else None,
            "cuenta_id": next(iter(cuentas)) if len(cuentas) == 1 else None,
        })
    return sorted(salida, key=lambda g: (g["con_problema"] == 0, g["foto"] == A_MANO, g["foto"]))

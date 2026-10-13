"""CARTERA DE CHEQUES (dueño, 13/10): las cuentas puras de la pantalla y del panel.

El estado de cada cheque NO se calcula acá: lo dice la vista
`cheques_con_estado` (db/cheques_5), que es el único lugar con las reglas
(rojo a los 23 días de la fecha de pago, vencido a los 30, depositado que se
acredita al día siguiente de la fecha de pago o del depósito si fue después).
Acá solo se suman las filas que la vista ya clasificó.
"""
from datetime import date, timedelta

# Los estados en que el cheque sigue EN CARTERA: no se aplicó. El vencido
# también (está en el cajón, aunque ya no se pueda depositar).
EN_CARTERA = ("en_cartera", "vencido")

# Todos los estados que puede dar la vista, en el orden en que se muestran.
ESTADOS = ("en_cartera", "vencido", "entregado", "canjeado", "depositado", "acreditado",
           "rechazado", "reclamo_resuelto")
NOMBRES_DE_ESTADO = {
    "en_cartera": "En cartera", "vencido": "Vencido", "entregado": "Entregado",
    "canjeado": "Canjeado", "depositado": "Depositado", "acreditado": "Acreditado",
    "rechazado": "Rechazado", "reclamo_resuelto": "Reclamo resuelto",
}

# "Entra en 7 días" (dueño, 13/10): los que siguen en cartera y cuya fecha de
# pago cae entre hoy y dentro de 7 días.
DIAS_QUE_ENTRAN = 7


def esta_en_rojo(cheque: dict) -> bool:
    """Rojo: en cartera a 23 días o más de su fecha de pago (la vista lo dice
    en `en_rojo_por_vencer`), o rechazado con el reclamo sin resolver."""
    return bool(cheque.get("en_rojo_por_vencer")) or cheque["estado"] == "rechazado"


def resumen_de_cheques(cheques: list[dict], hoy: date) -> dict:
    """Lo de arriba de la pantalla y el cuadro del panel, de TODOS los cheques
    (no del listado filtrado): total en cartera, lo que entra en 7 días y
    cuántos están en rojo (por vencer, vencidos o rechazados sin resolver)."""
    hasta = hoy + timedelta(days=DIAS_QUE_ENTRAN)
    en_cartera = [c for c in cheques if c["estado"] in EN_CARTERA]
    entran = [c for c in cheques if c["estado"] == "en_cartera" and hoy <= c["fecha_pago"] <= hasta]
    rojos = [c for c in cheques if esta_en_rojo(c)]
    return {
        "en_cartera": round(sum(float(c["importe"]) for c in en_cartera), 2),
        "cantidad_en_cartera": len(en_cartera),
        "entran_7_dias": round(sum(float(c["importe"]) for c in entran), 2),
        "cantidad_entran": len(entran),
        "por_vencer": sum(1 for c in rojos if c["estado"] == "en_cartera"),
        "vencidos": sum(1 for c in rojos if c["estado"] == "vencido"),
        "rechazados": sum(1 for c in rojos if c["estado"] == "rechazado"),
        "en_rojo": len(rojos),
        "hasta": hasta,
    }


def total_del_listado(cheques: list[dict]) -> float:
    return round(sum(float(c["importe"]) for c in cheques), 2)


def _solo_digitos(texto) -> str:
    return "".join(ch for ch in str(texto or "") if ch.isdigit())


def _banco_de_la_lista(leido: str, bancos: list[dict]) -> str:
    """El nombre del banco de la lista que corresponde a lo leído (sin
    mayúsculas ni la palabra "Banco"), o lo leído tal cual si no hay."""
    def limpio(texto):
        return " ".join(w for w in str(texto or "").lower().split() if w not in ("banco", "de", "la", "del"))
    buscado = limpio(leido)
    if not buscado:
        return ""
    exactos = [b["nombre"] for b in bancos if limpio(b["nombre"]) == buscado]
    if exactos:
        return exactos[0]
    # Si no hay uno igual, el que más se parece: el nombre más largo que está
    # adentro de lo leído (o lo contiene). "Galicia" no le gana a "Galicia Más".
    parecidos = [b["nombre"] for b in bancos
                 if limpio(b["nombre"]) and (limpio(b["nombre"]) in buscado or buscado in limpio(b["nombre"]))]
    if parecidos:
        return max(parecidos, key=lambda nombre: len(limpio(nombre)))
    return str(leido).strip()


def cheques_leidos(datos: dict, bancos: list[dict]) -> list[dict]:
    """Lo que la IA leyó, listo para el formulario: textos que se corrigen a
    mano. El CUIT solo si tiene 11 números; el banco, el de la lista si se
    parece. Nada se valida acá: valida el formulario al guardar."""
    filas = []
    for cheque in datos.get("cheques") or []:
        cuit = _solo_digitos(cheque.get("cuit_librador"))
        importe = cheque.get("importe")
        filas.append({
            "numero": str(cheque.get("numero") or "").strip(),
            "banco": _banco_de_la_lista(cheque.get("banco"), bancos),
            "fecha_pago": str(cheque.get("fecha_pago") or ""),
            "importe": "" if importe in (None, "") else str(importe),
            "cuit_librador": cuit if len(cuit) == 11 else "",
            "tipo": "echeq" if cheque.get("tipo") == "echeq" else "fisico",
            "librador": str(cheque.get("librador") or "").strip(),
        })
    return filas


def numero_normalizado(numero) -> str:
    """El número como lo compara la base para los repetidos: sin espacios, en
    mayúsculas y sin ceros adelante."""
    return str(numero or "").strip().upper().lstrip("0")

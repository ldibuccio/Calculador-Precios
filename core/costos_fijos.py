"""Costos Fijos: el gasto mensual de operar, DERIVADO siempre — puro, sin tocar la base.

Las reglas del dueño (25/08, innegociables):

1. El valor inflado es un CÁLCULO, jamás un dato guardado. Acá entra la
   foto de cada subcuenta (importe + mes) y la tabla de índices, y sale
   el valor de cada mes — misma filosofía que el stock derivado: no hay
   nada guardado que pueda quedar desactualizado.

2. La corrección vale DE AHÍ EN ADELANTE: una foto nueva con su mes. Los
   meses anteriores resuelven a la foto anterior con los índices de
   entonces — eso sale solo del modelo, sin congelar nada. Una foto
   'solo_este_mes' pisa ÚNICAMENTE su mes (el error feo puntual), sin
   arrastrar a los siguientes.

3. Si falta el índice de un mes del tramo, la subcuenta NO se calcula
   para ese mes y queda A LA VISTA en ``sin_calcular`` con los meses que
   faltan — nunca se usa el índice anterior ni se asume cero: un total
   parcial mostrado como total sería mentira.

Convención del índice (confirmada contra la planilla): el porcentaje de
septiembre es la inflación DE septiembre — la foto de agosto vale tal
cual en agosto y se multiplica por (1 + %sept/100) para valer en
septiembre. Puede ser negativo.

La baja es CON MES (baja_desde = primer mes que no cuenta): los meses
anteriores siguen contando la subcuenta, como pidió el dueño para los
sueldos de gente que se fue.
"""

from datetime import date


def _mes_siguiente(mes: date) -> date:
    if mes.month == 12:
        return date(mes.year + 1, 1, 1)
    return date(mes.year, mes.month + 1, 1)


def _meses_del_tramo(desde: date, hasta: date) -> list[date]:
    """Los meses POSTERIORES a la foto, hasta el mes pedido inclusive: los que inflan."""
    meses = []
    mes = _mes_siguiente(desde)
    while mes <= hasta:
        meses.append(mes)
        mes = _mes_siguiente(mes)
    return meses


def _numero(valor):
    return float(valor) if valor is not None else None


def valor_subcuenta_en_mes(importes: list[dict], indices: dict, mes: date) -> dict:
    """El valor de UNA subcuenta en un mes, con su rastro. Los importes son los de ESA subcuenta.

    Devuelve {"valor", "mes_foto", "puntual", "indices_faltantes"}:
    - valor None + indices_faltantes = no se pudo calcular (faltan esos índices).
    - valor None + mes_foto None = la subcuenta no existía todavía (sin foto <= mes).
    """
    vigentes = [i for i in importes if i.get("anulado_el") is None]

    # El error feo puntual: una foto solo_este_mes pisa SOLO su mes, sin
    # inflar ni arrastrar. Si hay varias (se corrigió la corrección), vale
    # la última cargada.
    puntuales = sorted(
        (i for i in vigentes if i["alcance"] == "solo_este_mes" and i["mes_desde"] == mes),
        key=lambda i: i["creado_en"],
    )
    if puntuales:
        return {
            "valor": round(float(puntuales[-1]["importe"]), 2),
            "mes_foto": mes,
            "puntual": True,
            "indices_faltantes": [],
        }

    # La foto vigente: la más reciente con mes_desde <= mes (desempate: la
    # última cargada — corregir es cargar una foto nueva, jamás editar).
    bases = sorted(
        (i for i in vigentes if i["alcance"] == "en_adelante" and i["mes_desde"] <= mes),
        key=lambda i: (i["mes_desde"], i["creado_en"]),
    )
    if not bases:
        return {"valor": None, "mes_foto": None, "puntual": False, "indices_faltantes": []}
    base = bases[-1]

    factor = 1.0
    faltantes = []
    for mes_indice in _meses_del_tramo(base["mes_desde"], mes):
        porcentaje = _numero(indices.get(mes_indice))
        if porcentaje is None:
            faltantes.append(mes_indice)
        else:
            factor *= 1 + porcentaje / 100
    if faltantes:
        return {"valor": None, "mes_foto": base["mes_desde"], "puntual": False, "indices_faltantes": faltantes}

    return {
        "valor": round(float(base["importe"]) * factor, 2),
        "mes_foto": base["mes_desde"],
        "puntual": False,
        "indices_faltantes": [],
    }


def calcular_costos_fijos(
    grupos: list[dict],
    subcuentas: list[dict],
    importes: list[dict],
    indices: dict,
    mes: date,
    grupo_numero: int | None = None,
) -> dict:
    """El costo fijo del mes: total, desglose por grupo y subcuenta, y lo que NO se pudo calcular.

    grupos: [{id, numero, nombre, baja_el}]. subcuentas: [{id, grupo_id,
    numero, nombre, baja_desde}]. importes: TODOS los de todas las
    subcuentas (el motor separa). indices: {mes: porcentaje}.
    grupo_numero filtra un grupo puntual (el "pedir Sueldos" del dueño).

    Devuelve {"grupos", "total", "incompleto", "sin_calcular",
    "indices_faltantes", "sin_importe"}: sin_calcular es PROTAGONISTA (las
    subcuentas con índice faltante), sin_importe informa las subcuentas
    activas que todavía no tienen ninguna foto.
    """
    importes_por_subcuenta: dict = {}
    for importe in importes:
        importes_por_subcuenta.setdefault(importe["subcuenta_id"], []).append(importe)

    grupos_orden = sorted((g for g in grupos if g.get("baja_el") is None), key=lambda g: g["numero"])
    if grupo_numero is not None:
        grupos_orden = [g for g in grupos_orden if g["numero"] == grupo_numero]

    resultado_grupos = []
    sin_calcular = []
    sin_importe = []
    indices_faltantes: set = set()
    total = 0.0

    for grupo in grupos_orden:
        propias = sorted(
            (s for s in subcuentas if s["grupo_id"] == grupo["id"]),
            key=lambda s: s["numero"],
        )
        filas = []
        subtotal = 0.0
        for subcuenta in propias:
            codigo = f"{grupo['numero']}.{subcuenta['numero']}"
            # La baja es con mes: desde baja_desde ya no cuenta; antes sí.
            if subcuenta.get("baja_desde") is not None and subcuenta["baja_desde"] <= mes:
                continue
            calculo = valor_subcuenta_en_mes(
                importes_por_subcuenta.get(subcuenta["id"], []), indices, mes
            )
            if calculo["indices_faltantes"]:
                sin_calcular.append(
                    {
                        "codigo": codigo,
                        "nombre": subcuenta["nombre"],
                        "grupo_nombre": grupo["nombre"],
                        "faltan": calculo["indices_faltantes"],
                    }
                )
                indices_faltantes.update(calculo["indices_faltantes"])
                continue
            if calculo["valor"] is None:
                sin_importe.append({"codigo": codigo, "nombre": subcuenta["nombre"]})
                continue
            filas.append(
                {
                    "subcuenta_id": subcuenta["id"],
                    "codigo": codigo,
                    "nombre": subcuenta["nombre"],
                    "valor": calculo["valor"],
                    "mes_foto": calculo["mes_foto"],
                    "puntual": calculo["puntual"],
                }
            )
            subtotal += calculo["valor"]
        if filas or any(s["grupo_id"] == grupo["id"] for s in subcuentas):
            resultado_grupos.append(
                {
                    "grupo_id": grupo["id"],
                    "numero": grupo["numero"],
                    "nombre": grupo["nombre"],
                    "filas": filas,
                    "subtotal": round(subtotal, 2),
                }
            )
        total += subtotal

    return {
        "grupos": resultado_grupos,
        "total": round(total, 2),
        # Incompleto = hay subcuentas que NO entraron al total por índice
        # faltante: el número grande no es el costo real del mes.
        "incompleto": bool(sin_calcular),
        "sin_calcular": sin_calcular,
        "indices_faltantes": sorted(indices_faltantes),
        "sin_importe": sin_importe,
    }

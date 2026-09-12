"""Genera el Excel del Remanente del depósito — puro, sin tocar la base ni la red.

Mismo molde que exportar_disponibles: recibe las porciones ya armadas y
devuelve los bytes. No sabe de dónde salen los números — eso lo resuelve
app/main.py.
"""

from datetime import date
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Border, Font, PatternFill, Side

# Los grupos y su orden salen del MISMO lugar que los usa el resto del sistema.
# Escribir acá otra lista sería una segunda versión de "cuáles son los grupos",
# y el día que se agregue uno este archivo lo mandaría al final sin que nadie
# se entere.
from core.rentabilidad import ETIQUETA_SIN_GRUPO, ETIQUETAS_GRUPO, ORDEN_GRUPOS

# Las cajas armadas van APARTE y al final: en el piso son una pila propia, no
# están mezcladas con la fruta suelta, y el que cuenta las cuenta en otro
# momento. No es un grupo de artículo — por eso no está en ORDEN_GRUPOS.
SECCION_PROCESADAS = "Cajas Procesadas"

FILA_ENCABEZADO = 4
FILA_PRIMER_DATO = FILA_ENCABEZADO + 1

AZUL_ENCABEZADO_HEX = "1F4E79"  # el mismo de Disponibles

_BORDE_FINO = Side(style="thin", color="000000")
_BORDE_CELDA = Border(left=_BORDE_FINO, right=_BORDE_FINO, top=_BORDE_FINO, bottom=_BORDE_FINO)
# El total se despega de los datos con una raya gruesa arriba: impreso, es lo
# que hace que se lea como cierre y no como un renglón más de la lista.
_BORDE_GRUESO = Side(style="medium", color="000000")
_BORDE_TOTAL = Border(left=_BORDE_FINO, right=_BORDE_FINO, top=_BORDE_GRUESO, bottom=_BORDE_FINO)

GRIS_SECCION_HEX = "D9E2F3"
# Las filas con diferencia se pintan. Es lo único que se marca del archivo, y
# a propósito: el que lo abre viene a ver DÓNDE NO COINCIDE. Marcar en cambio
# las que no tienen conteo —que van a ser la mayoría— pintaría media planilla
# y taparía justo lo que se busca.
AMARILLO_DIFERENCIA_HEX = "FFF2CC"

# El subtotal se pinta IGUAL que el título de su sección, y es el punto: los dos
# son chrome, no mercadería. Impreso, la sección queda encerrada entre dos
# franjas grises —encabezado arriba, cierre abajo— y ningún renglón con número
# adentro se confunde con ellas. Sin el relleno, "Subtotal Hortaliza · 132" es
# una fila con nombre y número, o sea exactamente lo que parece un producto.
_BORDE_SUBTOTAL = Border(left=_BORDE_FINO, right=_BORDE_FINO, top=_BORDE_FINO, bottom=_BORDE_FINO)


def _escribir_conteo(hoja, fila, porcion) -> None:
    """Las tres celdas del conteo físico de una porción, o los guiones si no hay.

    "—" y "no se cuenta" NO son lo mismo, y por eso se escriben distinto: el
    primero es una porción que espera al operario; el segundo es la SEGUNDA,
    que no se puede contar nunca (Stock Físico ofrece "los bultos sueltos" o
    "las cajas de una ficha", y no hay tercera opción). Con un solo símbolo
    para los dos casos, alguien saldría a buscar un conteo que no puede
    existir.

    La fecha va en su propia columna y no pegada al número: una celda que
    mezcla número y texto deja de poder ordenarse, filtrarse y sumarse, que es
    justo para lo que se abre un Excel.

    La diferencia se pinta SOLO si no es cero, y ahora SALE DE RESTAR LAS DOS
    COLUMNAS DE AL LADO: Sistema − Físico. Hasta el 08/09 se restaba contra la
    foto congelada al contar, y hacía falta una columna más ("Sistema al
    contar") para poder verificarla; esa columna se fue con la foto.
    """
    if porcion.get("fisico") is None:
        hoja.cell(row=fila, column=3, value="—")
        return
    hoja.cell(row=fila, column=3, value=float(porcion["fisico"]))
    hoja.cell(row=fila, column=4, value=porcion["contado_el"].strftime("%d/%m/%Y"))
    celda = hoja.cell(row=fila, column=5, value=float(porcion["diferencia"]))
    if porcion["diferencia"]:
        relleno = PatternFill(start_color=AMARILLO_DIFERENCIA_HEX,
                              end_color=AMARILLO_DIFERENCIA_HEX, fill_type="solid")
        for columna in _COLUMNAS:
            hoja.cell(row=fila, column=columna).fill = relleno
        celda.font = Font(bold=True)


# Diferencia = Sistema − Físico, las dos columnas que tiene al lado. "Contado
# el" queda entre medio a propósito: es lo que dice de cuándo es el físico, y
# sin esa fecha el número de al lado no significa nada.
_ENCABEZADOS = ("Producto", "Sistema", "Físico", "Contado el", "Diferencia")
_COLUMNAS = tuple(range(1, len(_ENCABEZADOS) + 1))


def _secciones(porciones: list[dict]) -> list[tuple]:
    """[(título, [porciones]), ...] en el orden en que se recorre el depósito.

    Primero los grupos de artículo, en el orden fijo del sistema, y al final
    las cajas procesadas. Una sección sin nada no sale: una hoja impresa con
    "HOJA" y ningún renglón abajo hace dudar de si falta algo o no hay.
    """
    procesadas = [p for p in porciones if p.get("procesada")]
    sueltas = [p for p in porciones if not p.get("procesada")]

    secciones = []
    for grupo in ORDEN_GRUPOS:
        del_grupo = [p for p in sueltas if p.get("grupo") == grupo]
        if del_grupo:
            secciones.append((ETIQUETAS_GRUPO.get(grupo, ETIQUETA_SIN_GRUPO), del_grupo))
    # Un grupo que el sistema todavía no conoce no puede desaparecer del
    # archivo: cae en "Sin grupo" con el resto, que es donde se va a notar.
    conocidos = set(ORDEN_GRUPOS)
    huerfanas = [p for p in sueltas if p.get("grupo") not in conocidos]
    if huerfanas:
        secciones.append((ETIQUETA_SIN_GRUPO, huerfanas))
    if procesadas:
        secciones.append((SECCION_PROCESADAS, procesadas))
    return secciones


def generar_excel_remanente(fecha: date, porciones: list[dict]) -> bytes:
    """El remanente en una hoja: una fila por porción más el total al pie, en el orden en que viene.

    porciones: [{"nombre", "bultos", "grupo", "procesada"}, ...] — ya
    ordenadas por app/main.py. Acá no se REORDENA nada: solo se reparten en
    secciones respetando el orden que traen, así que dentro de cada grupo
    quedan igual que en la pantalla. Si el Excel las reordenara, serían dos
    criterios y se irían separando.

    LAS SECCIONES son los grupos del artículo (Fruta, Hortaliza, Hoja,
    Pesada, Sin grupo) más una propia al final, "Cajas Procesadas", con las
    cajas armadas a una ficha. Es para caminar el depósito: las cajas armadas
    son una pila aparte y se cuentan en otro momento. La segunda NO va ahí
    —son bultos sueltos de calidad menor, no cajas— y se queda con su
    artículo.

    SIN PLATA, y no es un olvido: el costo por bulto vive en el LOTE, no en
    el artículo —los mismos 30 bultos pueden venir de tres compras a tres
    precios—, así que poner un número de plata acá obligaría a elegir una
    valuación que ninguna pantalla calcula hoy. Y para lo que sirve este
    archivo no hace falta: se cuentan cajones, no pesos.

    HUBO UNA COLUMNA "Contado" VACÍA, para imprimir e ir a contar. Se sacó
    el 07/09: el Remanente vive en Administración y el que cuenta no entra
    ahí — el conteo se carga desde Stock Físico, en Depósito. Con el físico
    ya adentro del archivo, esa columna no tenía a quién servir.

    Las columnas del conteo salen del ÚLTIMO conteo de cada porción
    (listar_ultimos_conteos_stock, la misma que el Cotejo) y la diferencia es
    `Sistema − Físico` contra el sistema de ESTE momento — la fórmula exacta
    de ver_cotejo_stock, que cambió igual el 08/09. Por qué se dejó de restar
    contra la foto congelada, en _pegar_conteos_a_porciones.

    Cada sección CIERRA con su subtotal y al pie va el total general. No hay
    total por ARTÍCULO, que es otra cosa y es justo la suma que el dueño pidió
    no mostrar ("80 cajones sin procesar + 40 cajas armadas no son 120
    bultos"): el subtotal es de la sección, o sea de una zona del depósito.

    Para qué sirve cada uno, que no es lo mismo: el del pie dice si el archivo
    impreso está completo (si no se cortó una hoja); el de la sección acota
    DÓNDE BUSCAR cuando algo no cierra, sin tener que rehacer la suma entera.

    El número va COMO VALOR, no como fórmula: lo que importa es lo que
    quedó impreso en el papel, y una fórmula no se imprime distinto pero
    sí puede cambiar si alguien toca una celda antes de imprimir.

    El subtotal y el total suman SOLO la columna Sistema. Las del conteo van
    vacías ahí, y no por el motivo viejo: un total de físicos mezclaría
    conteos de fechas distintas, y una suma de diferencias se compensaría
    sola —faltan 10 de una porción, sobran 10 de otra, el total da cero y
    parece que está todo bien—. La diferencia se mira renglón por renglón,
    que es para lo que están pintados.
    """
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Stock del Depósito"

    hoja.merge_cells("A1:E1")
    hoja["A1"] = "Stock del Depósito"
    hoja["A1"].font = Font(bold=True, size=14)

    hoja.merge_cells("A2:E2")
    hoja["A2"] = f"Al {fecha.strftime('%d/%m/%Y')}"
    hoja["A2"].font = Font(bold=True)

    relleno = PatternFill(start_color=AZUL_ENCABEZADO_HEX, end_color=AZUL_ENCABEZADO_HEX, fill_type="solid")
    for columna, encabezado in enumerate(_ENCABEZADOS, start=1):
        celda = hoja.cell(row=FILA_ENCABEZADO, column=columna, value=encabezado)
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = relleno
        celda.border = _BORDE_CELDA

    relleno_seccion = PatternFill(start_color=GRIS_SECCION_HEX, end_color=GRIS_SECCION_HEX,
                                  fill_type="solid")
    fila_actual = FILA_PRIMER_DATO
    for titulo, del_grupo in _secciones(porciones):
        for columna in _COLUMNAS:
            celda = hoja.cell(row=fila_actual, column=columna,
                              value=titulo if columna == 1 else None)
            celda.font = Font(bold=True)
            celda.fill = relleno_seccion
            celda.border = _BORDE_CELDA
        fila_actual += 1
        for porcion in del_grupo:
            hoja.cell(row=fila_actual, column=1, value=porcion["nombre"])
            hoja.cell(row=fila_actual, column=2, value=float(porcion["bultos"]))
            _escribir_conteo(hoja, fila_actual, porcion)
            for columna in _COLUMNAS:
                hoja.cell(row=fila_actual, column=columna).border = _BORDE_CELDA
            fila_actual += 1

        # El cierre de la sección. Mismas tres reglas que el total del pie:
        # el número va como VALOR (lo que importa es lo que quedó impreso), la
        # celda "Contado" va VACÍA (si el que cuenta ve un subtotal del sistema
        # ya tiene contra qué cuadrar sin haber contado), y se pinta como
        # chrome para que no se lea como un renglón de mercadería.
        cuantas = len(del_grupo)
        etiqueta = f"Subtotal {titulo} — {cuantas} {'renglón' if cuantas == 1 else 'renglones'}"
        subtotal = round(sum(float(p["bultos"]) for p in del_grupo), 2)
        # Las vacías se derivan de _COLUMNAS y no se listan a mano: la lista
        # escrita quedó con seis el día que las columnas pasaron a cinco.
        vacias = [(columna, None) for columna in _COLUMNAS[2:]]
        for columna, valor in [(1, etiqueta), (2, subtotal), *vacias]:
            celda = hoja.cell(row=fila_actual, column=columna, value=valor)
            celda.font = Font(bold=True)
            celda.fill = relleno_seccion
            celda.border = _BORDE_SUBTOTAL
        fila_actual += 1

    # El total cuenta las PORCIONES, no las filas escritas: los títulos de
    # sección no son renglones que alguien tenga que ir a contar.
    renglones = len(porciones)
    total = round(sum(float(p["bultos"]) for p in porciones), 2)
    etiqueta = f"TOTAL — {renglones} {'renglón' if renglones == 1 else 'renglones'}"
    hoja.cell(row=fila_actual, column=1, value=etiqueta)
    hoja.cell(row=fila_actual, column=2, value=total)
    for columna in _COLUMNAS:
        celda = hoja.cell(row=fila_actual, column=columna)
        celda.font = Font(bold=True)
        celda.border = _BORDE_TOTAL

    hoja.column_dimensions["A"].width = 34
    hoja.column_dimensions["B"].width = 12
    hoja.column_dimensions["C"].width = 12
    hoja.column_dimensions["D"].width = 12
    hoja.column_dimensions["E"].width = 12

    buffer = BytesIO()
    libro.save(buffer)
    return buffer.getvalue()

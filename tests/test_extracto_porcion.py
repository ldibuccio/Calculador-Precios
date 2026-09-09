"""El extracto de una porción: los eventos EXPLICAN, no calculan el saldo."""

from core.extracto_porcion import SIN_EXPLICAR, SIN_GUIA_R, armar_extracto

# Perita el 07/09: entraron 30 cajones de La Misión y la guía R143 tomó 10
# cajones y armó 30 cajas para la ficha 7. El mismo reproceso mueve LAS DOS
# pilas, y en direcciones opuestas — que es justo lo que no se podía ver.
EVENTOS_PERITA = {
    "compras": [{"proveedor": "La Misión", "bultos": 30.0}],
    "reprocesos": [{"id": 143, "tomados": 10.0, "primera": 30.0, "segunda": 0.0,
                    "ficha_id": 7, "tipo": "normal"}],
    "armados": [{"cliente": "Día", "sucursal": "GR", "ficha_id": 7, "bultos": 20.0}],
    "movimientos": [],
    "remitos": [],
}

SIN_EVENTOS = {"compras": [], "reprocesos": [], "armados": [], "movimientos": [], "remitos": []}


def test_los_cajones_ven_la_compra_y_la_salida_del_reproceso():
    extracto = armar_extracto(EVENTOS_PERITA, venia=45.0, quedo=65.0)

    assert extracto["venia"] == 45.0
    assert [(f["descripcion"], f["bultos"]) for f in extracto["filas"]] == [
        ("Compra recibida — La Misión", 30.0),
        ("Reproceso R143", -10.0),
    ]
    assert extracto["quedo"] == 65.0
    assert extracto["sin_explicar"] == 0


def test_las_cajas_ven_la_ENTRADA_del_mismo_reproceso_y_el_armado():
    """El mismo R143 saca 10 cajones de una pila y mete 30 cajas en la otra.

    Es la conversión, y es el movimiento que antes no se podía ver: en la
    cuenta por artículo los dos números se cancelaban contra el total.
    """
    extracto = armar_extracto(EVENTOS_PERITA, venia=0.0, quedo=10.0, ficha_id=7)

    assert [(f["descripcion"], f["bultos"]) for f in extracto["filas"]] == [
        ("Reproceso R143", 30.0),
        ("Armado pedido Día GR", -20.0),
    ]
    assert extracto["quedo"] == 10.0
    assert extracto["sin_explicar"] == 0


def test_la_compra_y_la_merma_NO_tocan_la_pila_de_cajas():
    """Ni la merma ni el ajuste pueden mover una ficha: están escritos por
    ARTÍCULO a propósito. Si alguna vez aparecen acá, la regla se rompió."""
    eventos = dict(EVENTOS_PERITA, movimientos=[
        {"tipo": "merma", "cantidad": -5.0, "motivo": "podrida",
         "destino_rechazo": None, "bultos_segunda": None},
    ])
    extracto = armar_extracto(eventos, venia=0.0, quedo=10.0, ficha_id=7)

    descripciones = [f["descripcion"] for f in extracto["filas"]]
    assert "Merma — podrida" not in descripciones
    assert not any("Compra" in d for d in descripciones)


def test_un_articulo_que_no_se_reprocesa_tiene_movimiento_directo():
    """Manzana: entra por compra, sale por armado. Una sola pila."""
    eventos = {
        "compras": [{"proveedor": "Cooperativa", "bultos": 40.0}],
        "reprocesos": [],
        "armados": [{"cliente": "Día", "sucursal": "VL", "ficha_id": None, "bultos": 12.0}],
        "movimientos": [],
        "remitos": [],
    }
    extracto = armar_extracto(eventos, venia=18.0, quedo=46.0)

    assert [(f["descripcion"], f["bultos"]) for f in extracto["filas"]] == [
        ("Compra recibida — Cooperativa", 40.0),
        ("Armado pedido Día VL", -12.0),
    ]
    assert extracto["sin_explicar"] == 0


def test_lo_que_los_eventos_no_explican_va_en_su_renglon_y_no_se_reparte():
    """El caso conocido es el PISO de la cuenta por ficha: el déficit queda
    adentro de los sueltos sin ser ningún evento. Va a la vista."""
    extracto = armar_extracto(EVENTOS_PERITA, venia=45.0, quedo=62.0)

    assert extracto["filas"][-1]["descripcion"] == SIN_EXPLICAR
    assert extracto["filas"][-1]["bultos"] == -3.0
    assert extracto["sin_explicar"] == -3.0
    # Y los otros renglones NO se tocaron para hacerla cuadrar.
    assert ("Compra recibida — La Misión", 30.0) == (
        extracto["filas"][0]["descripcion"], extracto["filas"][0]["bultos"])


def test_el_saldo_final_es_EL_QUE_ENTRA_aunque_los_eventos_digan_otra_cosa():
    """La garantía de la pantalla: "Quedó" sale del Remanente, no de sumar.

    Si el saldo se calculara con los eventos, sería una quinta versión de la
    cuenta de stock y se separaría de las otras cuatro. Acá entra hecho.
    """
    extracto = armar_extracto(SIN_EVENTOS, venia=45.0, quedo=65.0)

    assert extracto["quedo"] == 65.0
    assert extracto["filas"] == [{"descripcion": SIN_EXPLICAR, "bultos": 20.0}]


def test_un_dia_sin_movimiento_no_inventa_renglones():
    extracto = armar_extracto(SIN_EVENTOS, venia=45.0, quedo=45.0)

    assert extracto["filas"] == []
    assert extracto["venia"] == extracto["quedo"] == 45.0


def test_la_segunda_ve_el_pool_y_no_el_stock_normal():
    eventos = {
        "compras": [{"proveedor": "La Misión", "bultos": 30.0}],
        "reprocesos": [{"id": 143, "tomados": 10.0, "primera": 30.0, "segunda": 4.0,
                        "ficha_id": 7, "tipo": "normal"}],
        "armados": [],
        "movimientos": [{"tipo": "reingreso_rechazo", "cantidad": 6.0, "motivo": "Día VL",
                         "destino_rechazo": "segunda", "bultos_segunda": 6.0}],
        "remitos": [{"id": 9, "bultos": 5.0}],
    }
    extracto = armar_extracto(eventos, venia=3.0, quedo=8.0, es_segunda=True)

    assert [(f["descripcion"], f["bultos"]) for f in extracto["filas"]] == [
        ("Segunda del reproceso R143", 4.0),
        ("Rechazo a segunda — Día VL", 6.0),
        ("Remito al Puesto", -5.0),
    ]
    assert extracto["sin_explicar"] == 0


def test_el_rechazo_mandado_a_segunda_no_suma_dos_veces_en_los_sueltos():
    """Si volvió al stock, mueve los sueltos; si se fue a segunda, no."""
    eventos = dict(SIN_EVENTOS, movimientos=[
        {"tipo": "reingreso_rechazo", "cantidad": 6.0, "motivo": "Día VL",
         "destino_rechazo": "segunda", "bultos_segunda": 6.0},
        {"tipo": "reingreso_rechazo", "cantidad": 4.0, "motivo": "Día BZ",
         "destino_rechazo": "stock", "bultos_segunda": None},
    ])
    extracto = armar_extracto(eventos, venia=10.0, quedo=14.0)

    assert [(f["descripcion"], f["bultos"]) for f in extracto["filas"]] == [
        ("Reingreso — Día BZ", 4.0),
    ]


def test_la_guia_R_sin_ficha_cae_en_los_sueltos_y_lo_dice():
    eventos = dict(SIN_EVENTOS, reprocesos=[
        {"id": 150, "tomados": 8.0, "primera": 15.0, "segunda": 0.0,
         "ficha_id": None, "tipo": "normal"},
    ])
    extracto = armar_extracto(eventos, venia=20.0, quedo=27.0)

    assert [(f["descripcion"], f["bultos"]) for f in extracto["filas"]] == [
        ("Reproceso R150", -8.0),
        ("Reproceso R150 (sin asignar)", 15.0),
    ]


def test_el_cierre_del_modelo_viejo_tiene_nombre_y_no_sale_crudo():
    """Estaba en el CHECK de movimientos_stock y faltaba en las etiquetas."""
    eventos = dict(SIN_EVENTOS, movimientos=[
        {"tipo": "cierre_modelo_viejo", "cantidad": -12.0, "motivo": "corte 31/08",
         "destino_rechazo": None, "bultos_segunda": None},
    ])
    extracto = armar_extracto(eventos, venia=12.0, quedo=0.0)

    assert extracto["filas"][0]["descripcion"] == "Cierre del modelo viejo — corte 31/08"


def test_el_reproceso_dice_A_DONDE_FUERON_las_cajas():
    """Desde los sueltos el reproceso solo saca, y eso se lee como faltante.

    Del 08/09: el renglón decía solo "Reproceso R177 −25" y un artículo donde
    la conversión no es 1 a 1 —el mango entra en cajones de 12u y sale en
    cajas de 10u— deja al que lee sin forma de saber que el otro lado está en
    otra pila. Ninguno de los dos números explica al otro.
    """
    eventos = {
        "compras": [],
        "reprocesos": [{"id": 177, "tomados": 25.0, "primera": 30.0, "segunda": 0.0,
                        "ficha_id": 9, "tipo": "normal", "destino": "Mango Caja Día"}],
        "armados": [],
        "movimientos": [],
        "remitos": [],
    }
    filas = armar_extracto(eventos, venia=26.0, quedo=1.0)["filas"]

    renglon = [f for f in filas if "R177" in f["descripcion"]]
    assert len(renglon) == 1
    assert renglon[0]["descripcion"] == "Reproceso R177 → Mango Caja Día"
    assert renglon[0]["bultos"] == -25.0


def test_el_reproceso_SIN_ficha_no_inventa_destino():
    """La guía R sin asignar deja su primera en los sueltos, y ya tiene su
    propio renglón que lo dice. Un "→" sin nombre sería peor que nada."""
    eventos = {
        "compras": [],
        "reprocesos": [{"id": 178, "tomados": 10.0, "primera": 12.0, "segunda": 0.0,
                        "ficha_id": None, "tipo": "normal"}],
        "armados": [],
        "movimientos": [],
        "remitos": [],
    }
    filas = armar_extracto(eventos, venia=10.0, quedo=12.0)["filas"]

    descripciones = [f["descripcion"] for f in filas]
    assert "Reproceso R178" in descripciones
    assert "Reproceso R178 (sin asignar)" in descripciones
    assert not any("→" in d for d in descripciones)


def test_lo_que_salio_SIN_GUIA_R_tiene_nombre_y_no_cae_en_sin_explicar():
    """El caso de Limón del 08/09: armaron 35 cajas antes de cargar las guías R.

    Los sueltos salen de `total − Σ disponibles` y el disponible tiene
    piso, así que un déficit nuevo de 10 les BAJA 10. Eso caía en "Sin
    explicar" siendo la única cosa que no es: el sistema lo tiene
    calculado, y hasta lo muestra en el Cotejo y abajo del Remanente.

    Los dos números están a propósito muy separados —déficit 10 contra un
    residuo real de 3—: si el renglón se pusiera con el signo al revés, o
    se contara dos veces, el "Sin explicar" no daría −3.
    """
    eventos = {"compras": [{"proveedor": "EJEMPLO Prov", "bultos": 40.0}],
               "reprocesos": [], "armados": [], "movimientos": [], "remitos": []}

    extracto = armar_extracto(eventos, venia=11.0, quedo=38.0, deficit_nuevo=10.0)

    renglones = {f["descripcion"]: f["bultos"] for f in extracto["filas"]}
    assert renglones[SIN_GUIA_R] == -10.0
    # 11 + 40 − 10 = 41, quedó 38: el residuo de verdad son −3, y sigue a la vista.
    assert extracto["sin_explicar"] == -3.0
    assert renglones[SIN_EXPLICAR] == -3.0


def test_sin_deficit_nuevo_el_renglon_NO_aparece():
    """Un renglón en cero es ruido: el día que no pasó nada, no se nombra."""
    eventos = {"compras": [{"proveedor": "EJEMPLO Prov", "bultos": 40.0}],
               "reprocesos": [], "armados": [], "movimientos": [], "remitos": []}

    extracto = armar_extracto(eventos, venia=11.0, quedo=51.0, deficit_nuevo=0.0)

    assert SIN_GUIA_R not in [f["descripcion"] for f in extracto["filas"]]
    assert extracto["sin_explicar"] == 0.0


def test_el_deficit_es_de_los_SUELTOS_y_no_de_la_ficha_ni_de_la_segunda():
    """El déficit ya está DENTRO del saldo de la ficha (por eso su disponible es 0).

    Ponerlo también en el extracto de la ficha lo contaría dos veces, y en
    la segunda no significa nada. El parámetro se ignora en las dos.
    """
    eventos = {"compras": [], "reprocesos": [], "armados": [], "movimientos": [], "remitos": []}

    de_ficha = armar_extracto(eventos, venia=0.0, quedo=0.0, ficha_id=7, deficit_nuevo=10.0)
    de_segunda = armar_extracto(eventos, venia=0.0, quedo=0.0, es_segunda=True, deficit_nuevo=10.0)

    for extracto in (de_ficha, de_segunda):
        assert SIN_GUIA_R not in [f["descripcion"] for f in extracto["filas"]]


# EL CASO DEL 09/09 EN FRUTAMAX, con los números reales de producción y el
# artículo con nombre inventado. Limón, 08/09: volvieron 15 cajas armadas de
# la ficha, y la cuenta por ficha (paso 1) empezó a sumarlas ahí mientras el
# extracto las seguía listando como evento de SUELTOS.
#
# La firma del bug, y es lo que hay que reconocer si vuelve: los dos "Sin
# explicar" del mismo día salen IGUALES Y DE SIGNO OPUESTO — −15 en sueltos
# y +15 en la ficha. No es un faltante: es un evento en una porción y su
# saldo en la otra.
EVENTOS_08 = {
    "compras": [{"proveedor": "PROVEEDOR EJEMPLO", "bultos": 40.0}],
    "reprocesos": [
        {"id": 188, "tomados": 11.0, "primera": 11.0, "segunda": 0.0, "ficha_id": 4, "tipo": "normal"},
        {"id": 201, "tomados": 7.0, "primera": 7.0, "segunda": 0.0, "ficha_id": 4, "tipo": "normal"},
        {"id": 206, "tomados": 7.0, "primera": 7.0, "segunda": 0.0, "ficha_id": 4, "tipo": "normal"},
    ],
    "armados": [
        {"cliente": "CLIENTE EJEMPLO", "sucursal": "AA", "ficha_id": 4, "bultos": 10.0},
        {"cliente": "CLIENTE EJEMPLO", "sucursal": "BB", "ficha_id": 4, "bultos": 10.0},
        {"cliente": "CLIENTE EJEMPLO", "sucursal": "CC", "ficha_id": 4, "bultos": 15.0},
    ],
    # `ficha_id` lo trae la consulta, decidido con la MISMA constante que usa
    # la cuenta: viene no nulo justo cuando _SQL_STOCK_PARTIDO lo suma ahí.
    "movimientos": [{"tipo": "reingreso_rechazo", "cantidad": 15.0, "motivo": "Rechazo",
                     "destino_rechazo": "stock", "bultos_segunda": None, "ficha_id": 4}],
    "remitos": [],
}


def test_el_reingreso_CON_FICHA_no_es_un_evento_de_los_sueltos():
    """Las dos puntas son las de producción: venía 1 y quedó 16.

    Con el reingreso listado acá, lo explicado daba 30 y el "Sin explicar"
    salía −15. Sacándolo, la cuenta cierra sola.
    """
    extracto = armar_extracto(EVENTOS_08, venia=1.0, quedo=16.0)

    assert [(f["descripcion"], f["bultos"]) for f in extracto["filas"]] == [
        ("Compra recibida — PROVEEDOR EJEMPLO", 40.0),
        ("Reproceso R188", -11.0),
        ("Reproceso R201", -7.0),
        ("Reproceso R206", -7.0),
    ]
    assert extracto["sin_explicar"] == 0


def test_el_reingreso_CON_FICHA_es_un_evento_de_esa_ficha():
    """Vuelven cajas armadas, en la caja del cliente: son de la ficha por la
    que salieron. Venía 10 y quedó 15, las dos puntas de producción."""
    extracto = armar_extracto(EVENTOS_08, venia=10.0, quedo=15.0, ficha_id=4)

    assert [(f["descripcion"], f["bultos"]) for f in extracto["filas"]] == [
        ("Reproceso R188", 11.0),
        ("Reproceso R201", 7.0),
        ("Reproceso R206", 7.0),
        ("Armado pedido CLIENTE EJEMPLO AA", -10.0),
        ("Armado pedido CLIENTE EJEMPLO BB", -10.0),
        ("Armado pedido CLIENTE EJEMPLO CC", -15.0),
        ("Reingreso — Rechazo", 15.0),
    ]
    assert extracto["sin_explicar"] == 0


def test_los_dos_SIN_EXPLICAR_del_mismo_dia_no_pueden_ser_OPUESTOS():
    """LA FIRMA, escrita como test para que no haya que volver a
    diagnosticarla: un evento en una porción y su saldo en otra sale siempre
    así, y ninguna de las dos pantallas por separado se ve mal.

    Se mide sobre las dos porciones a la vez, que es lo único que la muestra.
    """
    sueltos = armar_extracto(EVENTOS_08, venia=1.0, quedo=16.0)["sin_explicar"]
    ficha = armar_extracto(EVENTOS_08, venia=10.0, quedo=15.0, ficha_id=4)["sin_explicar"]

    assert not (sueltos and ficha and sueltos == -ficha), (
        f"sueltos {sueltos} y ficha {ficha} son opuestos: el evento quedó de un lado "
        "y el saldo del otro"
    )


def test_un_reingreso_SIN_FICHA_sigue_siendo_de_los_sueltos():
    """El otro lado de la moneda, y es el que evita arreglar de más: un
    rechazo que vuelve sin ficha no tiene pila propia a la que ir. La cuenta
    tampoco lo mueve —`pr.ficha_id IS NOT NULL` en el CTE— así que sigue
    entrando por el total y viéndose acá."""
    eventos = dict(SIN_EVENTOS,
                   movimientos=[{"tipo": "reingreso_rechazo", "cantidad": 8.0,
                                 "motivo": "Rechazo", "destino_rechazo": "stock",
                                 "bultos_segunda": None, "ficha_id": None}])

    extracto = armar_extracto(eventos, venia=2.0, quedo=10.0)

    assert [(f["descripcion"], f["bultos"]) for f in extracto["filas"]] == [
        ("Reingreso — Rechazo", 8.0),
    ]
    assert extracto["sin_explicar"] == 0

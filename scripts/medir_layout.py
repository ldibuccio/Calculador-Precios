"""Mide una pantalla a un ancho dado: alto de fila, QUIEBRE de texto y desborde.

SOLO LEE. Recibe HTML ya renderizado y lo abre en un navegador de verdad; no
toca la base ni el repo.

POR QUÉ EXISTE, y es la parte que hay que leer antes de usarlo: el 12/09 se
midió el alto de las tarjetas de Buscar Compras para decidir dos rediseños, y
el alto SOLO se equivocó dos veces seguidas.

1. **La simulación midió una pantalla que no se puede usar.** Se simuló el
   menú de acciones con un botón chico y prometió 1,1 filas de ganancia; lo
   construido dio 0,6, y la primera versión midió PEOR que el diseño viejo. Un
   `summary` de 44px —el mínimo para tocarlo con el pulgar— cuesta casi lo
   mismo que las cinco pastillas que reemplaza. Por eso `medir` no simula
   nada: mide el HTML real que sale de la aplicación.

2. **El número mejoraba mientras la pantalla empeoraba.** Dos intentos
   bajaron el alto ROMPIENDO EL TEXTO: "SIN PRECIO" y "41 cajones × 16u"
   partidos en dos. El promedio bajaba y decía que iba mejorando. Las dos se
   vieron en la captura, no en el número.

De ahí sale `quebradas`, que es la razón de ser de este módulo: **una celda
que mide más que su propio `line-height` envolvió.** El alto sin el quiebre
al lado miente exactamente cuando el diseño empeora, que es cuando más caro
sale creerle.

Y de ahí sale la regla de uso: **el alto solo nunca alcanzó.** Cualquier
medición de layout de acá en adelante devuelve los números juntos.

El CUARTO llegó el 15/09 y es el **solape**: dos cajas que se pisan. Ni el
quiebre ni el desborde lo ven —la celda mide una línea y nada se sale del
ancho— y apareció en Editar artículo, donde un `margin-top: -0.4rem` copiado
de una pantalla cuyos campos SÍ tenían margen inferior le comió 6,4px al
`<select>` de arriba. Los otros dos números daban 0 y los dos eran ciertos.

Y con él llegó una corrección al módulo: **el solape se mide ANTES del corte
por "sin filas"**. Un formulario no tiene filas, así que devolviendo ahí el
número no se habría medido nunca en la clase de pantalla donde el defecto
apareció — el cero del corolario 47 adentro de la herramienta escrita para
el corolario 47, por tercera vez.

Y `quebradas` viene con su DENOMINADOR (`celdas`), que es el cuarto y llegó
el 14/09: el detector miraba solo `td, th`, así que en una pantalla de
TARJETAS devolvía `0` sin haber inspeccionado una sola celda. Un cero sin
decir contra cuántas se contó no distingue "ninguna envolvió" de "no se miró
ninguna", y las dos se imprimen igual. `imprimir` escribe `quebradas: 0 de
160 celdas`, y `SIN CELDAS QUE MIRAR` cuando el número es de la nada.

La tercera pieza de ese rediseño —compactar la tarjeta— se descartó con esto:
ganaba 1,2 filas rompiendo texto con los nombres de hoy y era PEOR que el
diseño vigente con nombres largos. El largo de los nombres no lo controlamos.

CÓMO SE USA. Cada pantalla arma su propio HTML (con el TestClient y los datos
parcheados, como en los tests) y se lo pasa a `medir`:

    import asyncio
    from scripts.medir_layout import medir

    print(asyncio.run(medir(html, ancho=390)))

El fixture es de cada pantalla y la medición es de acá: al revés —un script
que sepa renderizar cada pantalla— sería una copia del armado de contexto de
cada ruta, y esa copia envejece sola.

DOS ANCHOS SIEMPRE, y con los nombres largos incluidos: un diseño que solo
entra con los datos de hoy se rompe el día que alguien carga un proveedor con
nombre largo, y ahí nadie va a saber por qué.
"""

import asyncio

# El mismo que usan las capturas del proyecto: el contenedor lo trae
# preinstalado y `playwright install` no corre acá.
CHROMIUM = "/opt/pw-browsers/chromium"

ANCHO_CELULAR = 390
ALTO_CELULAR = 844

# Cuánto puede pasarse una celda de UNA línea antes de que cuente como
# envuelta. 1.6 y no 1.0 porque el padding y el `line-height` redondeado
# empujan unos píxeles sin que haya una segunda línea: con 1.0 todas las
# celdas darían "quebrada" y el detector no distinguiría nada, que es el
# corolario 47 —un número que no puede dar distinto no es una medición—
# aplicado a la herramienta misma.
TOLERANCIA_LINEA = 1.6

_MEDICION = """(opciones) => {
  // SOLAPES: dos cajas que se PISAN. Es una tercera forma de romperse, y
  // ni el quiebre ni el desborde la ven — la celda no envuelve (mide una
  // línea) y no se sale del ancho (sobra a lo alto, no a lo ancho). Apareció
  // el 15/09 en Editar artículo: un `margin-top: -0.4rem` copiado de una
  // pantalla cuyos campos SÍ tenían margen inferior le comió 6,4px al
  // <select> de arriba. El detector devolvía quiebre 0 y desborde 0, los dos
  // verdaderos.
  //
  // SOLO HERMANOS EN FLUJO NORMAL. Lo que está posicionado se pisa a
  // propósito —un menú, un cartel flotante, una cabecera sticky— y marcarlo
  // haría un detector que marca todo, que se ve igual de trabajador que uno
  // que funciona (corolario 53).
  //
  // SOLO LOS QUE ESTÁN APILADOS, y ésta es la mitad que faltó en el primer
  // intento: dos elementos LADO A LADO —los botones "Editar" y "Eliminar" de
  // una fila— tienen el borde inferior del primero más abajo que el superior
  // del segundo SIEMPRE, porque comparten renglón. Sin este filtro el
  // detector marcaba dos por pantalla que estaban perfectas, que es
  // literalmente el corolario 53. Se reconocen porque sus rangos
  // HORIZONTALES no se tocan: si no comparten ni una columna, no están uno
  // abajo del otro y no hay nada que comparar a lo alto.
  //
  // Y el piso es 1px, no 0: medio píxel de redondeo no es un solape.
  const solapes = [];
  let pares_mirados = 0;
  //
  // Y LO INLINE TAMPOCO SE APILA, que es la tercera forma y la encontró el
  // 18/09 la pantalla de Vacíos: un <strong> adentro de un párrafo que
  // ENVUELVE tiene por caja la UNIÓN de sus renglones, así que arranca en la
  // línea donde el <strong> anterior todavía está. Medido: "14 recepciones"
  // de 1334,6 a 1350,6 y "3 devoluciones" de 1334,6 a 1366,6 — 16px de
  // "solape" y nada que se pise en la pantalla. El filtro de la columna no
  // los saca: un inline envuelto ocupa el ancho entero, así que comparte
  // columna con todo. `inline-block` SÍ se apila y se queda.
  const enFlujo = elemento => {
    const p = getComputedStyle(elemento).position;
    return p === "static" || p === "relative";
  };
  const esCaja = elemento => getComputedStyle(elemento).display !== "inline";
  [...document.querySelectorAll("form, fieldset, section, div, main, body")].forEach(padre => {
    const hijos = [...padre.children].filter(
      h => h.getBoundingClientRect().height > 0 && enFlujo(h) && esCaja(h)
    );
    for (let i = 0; i < hijos.length - 1; i++) {
      const a = hijos[i].getBoundingClientRect(), b = hijos[i + 1].getBoundingClientRect();
      const comparten_columna = a.left < b.right && b.left < a.right;
      if (!comparten_columna) { continue; }
      pares_mirados += 1;
      const hueco = b.top - a.bottom;
      if (hueco < -1) {
        solapes.push((hijos[i + 1].textContent.trim().replace(/\s+/g, " ").slice(0, 30)
                      || hijos[i + 1].tagName)
                     + " pisa " + Math.round(Math.abs(hueco) * 10) / 10 + "px");
      }
    }
  });

  const filas = [...document.querySelectorAll(opciones.selectorFilas)];
  // El corte por "sin filas" va DESPUÉS de los solapes, y es el motivo por el
  // que el bloque de arriba está arriba: un formulario no tiene filas, así
  // que devolviendo acá el solape no se mediría NUNCA en la clase de
  // pantalla donde apareció. Es el cero del corolario 47 una vez más, y esta
  // vez adentro de la herramienta escrita para el 47.
  if (!filas.length) { return {filas: 0, alto_fila: null, por_pantalla: null,
                               quebradas: [], celdas: 0, desborde: 0, arriba: null,
                               solapes: [...new Set(solapes)], pares: pares_mirados,
                               desborde_pagina: document.documentElement.scrollWidth
                                              - document.documentElement.clientWidth}; }

  const alto = filas.reduce((a, f) => a + f.getBoundingClientRect().height, 0) / filas.length;

  // UNA CELDA QUE MIDE MÁS QUE SU PROPIO line-height ENVOLVIÓ. Se compara
  // contra el line-height REAL de esa celda y no contra un número escrito
  // acá: cada pantalla tiene su tipografía, y un umbral fijo mediría la
  // tipografía en vez del quiebre.
  //
  // LA CELDA NO ES SIEMPRE UN <td>. Mirando solo "td, th", toda pantalla de
  // TARJETAS —que en este proyecto son la mayoría en celular— devolvía
  // `quebradas: 0` SIEMPRE, sin una sola celda inspeccionada: el cero del
  // corolario 47, el que no puede dar distinto de cero. Se descubrió el
  // 14/09 midiendo Precios por Período, plantando un nombre que no entraba:
  // el alto de la ficha subió de 69,8 a 123,8px —envolvió— y `quebradas`
  // siguió en 0.
  //
  // Así que si la fila no tiene celdas de tabla, la celda es cada HOJA con
  // texto: el elemento que no tiene elementos adentro, que es donde el texto
  // de verdad envuelve. Las tablas siguen midiéndose igual que antes.
  const quebradas = [];
  let celdas_miradas = 0;
  filas.forEach(fila => {
    let celdas = [...fila.querySelectorAll("td, th")];
    if (!celdas.length) {
      celdas = [...fila.querySelectorAll("*")].filter(
        elemento => elemento.children.length === 0 && elemento.textContent.trim()
      );
    }
    if (!celdas.length && fila.textContent.trim()) { celdas = [fila]; }
    celdas.forEach(celda => {
      // Lo que se despliega no cuenta: un menú abierto es alto a propósito.
      if (celda.querySelector("details, ul, ol, table")) { return; }
      celdas_miradas += 1;
      const estilo = getComputedStyle(celda);
      const linea = parseFloat(estilo.lineHeight) || 16;
      // SE DESCUENTA EL RELLENO antes de comparar. Un botón de 44px —el
      // mínimo para tocarlo con el pulgar, que es regla de este proyecto—
      // mide el doble que su línea SIN haber envuelto nada, y sin descontarlo
      // toda pantalla con botones sale llena de quebradas que están bien. Un
      // detector que marca lo que está bien se ve igual de trabajador que uno
      // que funciona, y es el que nadie vuelve a mirar (corolario 53).
      const relleno = parseFloat(estilo.paddingTop) + parseFloat(estilo.paddingBottom)
                    + parseFloat(estilo.borderTopWidth) + parseFloat(estilo.borderBottomWidth);
      if (celda.getBoundingClientRect().height - relleno > linea * opciones.tolerancia) {
        quebradas.push(celda.textContent.trim().replace(/\\s+/g, " ").slice(0, 40));
      }
    });
  });

  const doc = document.documentElement;
  return {
    filas: filas.length,
    alto_fila: Math.round(alto * 10) / 10,
    por_pantalla: Math.round(opciones.alto / alto * 10) / 10,
    // Completas y visibles al llegar, sin scrollear.
    al_llegar: filas.filter(f => {
      const r = f.getBoundingClientRect();
      return r.top >= 0 && r.bottom <= opciones.alto;
    }).length,
    arriba: Math.round(filas[0].getBoundingClientRect().top),
    quebradas: [...new Set(quebradas)],
    // CONTRA CUÁNTO se contó. Sin esto, "quebradas: 0" no distingue "ninguna
    // envolvió" de "no se miró ninguna" — que son la misma pantalla y
    // significan lo contrario (corolarios 45 y 24).
    celdas: celdas_miradas,
    solapes: [...new Set(solapes)],
    // Su denominador, por lo mismo que el de las celdas: "solapes 0" sin
    // decir contra cuántos pares no distingue "ninguno se pisa" de "no se
    // miró ninguno".
    pares: pares_mirados,
    desborde: doc.scrollWidth - doc.clientWidth,
  };
}"""


async def medir(html: str, ancho: int = ANCHO_CELULAR, alto: int = ALTO_CELULAR,
                selector_filas: str = "tbody tr", captura: str | None = None) -> dict:
    """Los números juntos de un HTML ya renderizado: alto, quiebre, desborde y solape.

    Devuelve alto de fila, cuántas entran por pantalla, cuántas se ven al
    llegar, cuánto ocupa lo que está arriba de la primera, el DESBORDE
    horizontal y la lista de celdas QUEBRADAS.

    `quebradas` vacía es lo único que hace leíble al alto. Con algo adentro,
    el alto bajó porque el texto se partió y el número está diciendo lo
    contrario de lo que pasa.

    El desborde se mide de la PÁGINA. Si la pantalla tiene un contenedor con
    `overflow-x: auto` ese número va a dar 0 aunque la tabla se salga —el
    contenedor se lo come (corolario 47)— y ahí hay que medir la tabla contra
    su caja. Este módulo no lo adivina: se mira si la pantalla tiene alguno.
    """
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        navegador = await pw.chromium.launch(executable_path=CHROMIUM)
        try:
            pagina = await navegador.new_page(viewport={"width": ancho, "height": alto})
            await pagina.set_content(html)
            # El layout necesita un tick para asentarse; sin esto los altos
            # salen del primer paint y no del definitivo.
            await pagina.wait_for_timeout(250)
            medicion = await pagina.evaluate(_MEDICION, {
                "selectorFilas": selector_filas,
                "alto": alto,
                "tolerancia": TOLERANCIA_LINEA,
            })
            if captura:
                await pagina.screenshot(path=captura, full_page=True)
        finally:
            await navegador.close()
    return medicion


def medir_sync(html: str, **opciones) -> dict:
    """`medir` para el que no está en un contexto async."""
    return asyncio.run(medir(html, **opciones))


def _texto_de_solapes(medicion: dict) -> str:
    """"solapes: 0 de 34 pares", con el denominador pegado como el de las celdas.

    Sin el denominador, "ningún par se pisa" y "no se miró ningún par" se
    imprimen igual y significan lo contrario (corolarios 45 y 24).
    """
    pares = medicion.get("pares", 0)
    if not pares:
        return "SIN PARES QUE MIRAR"
    return f'solapes: {len(medicion.get("solapes", []))} de {pares} pares'


def imprimir(etiqueta: str, medicion: dict) -> None:
    """Una línea por medición, con el quiebre AL LADO del alto y no debajo.

    Juntos en la misma línea a propósito: el corolario 19 es que una
    salvaguarda que hay que ir a buscar no se lee. Si el quiebre estuviera en
    otra línea, el que compara dos altos compara dos altos.
    """
    solape = _texto_de_solapes(medicion)
    if not medicion["filas"]:
        # Sin filas igual hay algo que decir: el solape se mide sobre el
        # documento entero, no sobre las filas, así que un formulario —que no
        # tiene filas— sigue contestando esta mitad.
        desborde = medicion.get("desborde_pagina", medicion.get("desborde", 0))
        print(f"{etiqueta:<34} SIN FILAS (¿el selector es el correcto?) · "
              f"desborde {desborde}px · {solape}")
        return
    quebradas = medicion["quebradas"]
    celdas = medicion.get("celdas", 0)
    # El conteo de celdas VA PEGADO al de quebradas, en la misma línea: es su
    # denominador. "quebradas: 0" solo no distingue "ninguna envolvió" de "no
    # se miró ninguna", y las dos se imprimen igual.
    detalle = f"quebradas: {len(quebradas)} de {celdas} celdas" if celdas else "SIN CELDAS QUE MIRAR"
    print(
        f'{etiqueta:<34} {medicion["alto_fila"]:>6}px/fila · '
        f'{medicion["por_pantalla"]:>4} por pantalla · '
        f'{medicion["al_llegar"]} al llegar · '
        f'desborde {medicion["desborde"]}px · '
        + detalle
        + (f' {quebradas[:3]}' if quebradas else "")
        + " · " + solape
        + (f' {medicion["solapes"][:2]}' if medicion.get("solapes") else "")
    )

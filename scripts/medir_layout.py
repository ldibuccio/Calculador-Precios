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
medición de layout de acá en adelante devuelve los tres números juntos.

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
  const filas = [...document.querySelectorAll(opciones.selectorFilas)];
  if (!filas.length) { return {filas: 0, alto_fila: null, por_pantalla: null,
                               quebradas: [], celdas: 0, desborde: 0, arriba: null}; }

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
    desborde: doc.scrollWidth - doc.clientWidth,
  };
}"""


async def medir(html: str, ancho: int = ANCHO_CELULAR, alto: int = ALTO_CELULAR,
                selector_filas: str = "tbody tr", captura: str | None = None) -> dict:
    """Los tres números juntos de un HTML ya renderizado.

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


def imprimir(etiqueta: str, medicion: dict) -> None:
    """Una línea por medición, con el quiebre AL LADO del alto y no debajo.

    Juntos en la misma línea a propósito: el corolario 19 es que una
    salvaguarda que hay que ir a buscar no se lee. Si el quiebre estuviera en
    otra línea, el que compara dos altos compara dos altos.
    """
    if not medicion["filas"]:
        print(f"{etiqueta:<34} SIN FILAS (¿el selector es el correcto?)")
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
    )

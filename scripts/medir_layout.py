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
                               quebradas: [], desborde: 0, arriba: null}; }

  const alto = filas.reduce((a, f) => a + f.getBoundingClientRect().height, 0) / filas.length;

  // UNA CELDA QUE MIDE MÁS QUE SU PROPIO line-height ENVOLVIÓ. Se compara
  // contra el line-height REAL de esa celda y no contra un número escrito
  // acá: cada pantalla tiene su tipografía, y un umbral fijo mediría la
  // tipografía en vez del quiebre.
  const quebradas = [];
  filas.forEach(fila => {
    [...fila.querySelectorAll("td, th")].forEach(celda => {
      // Lo que se despliega no cuenta: un menú abierto es alto a propósito.
      if (celda.querySelector("details, ul, ol, table")) { return; }
      const linea = parseFloat(getComputedStyle(celda).lineHeight) || 16;
      if (celda.getBoundingClientRect().height > linea * opciones.tolerancia) {
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
    print(
        f'{etiqueta:<34} {medicion["alto_fila"]:>6}px/fila · '
        f'{medicion["por_pantalla"]:>4} por pantalla · '
        f'{medicion["al_llegar"]} al llegar · '
        f'desborde {medicion["desborde"]}px · '
        f'quebradas: {len(quebradas)}'
        + (f' {quebradas[:3]}' if quebradas else "")
    )

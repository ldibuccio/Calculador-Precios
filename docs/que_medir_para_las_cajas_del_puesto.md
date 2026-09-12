# Qué medir en el galpón antes de construir el control de cajas del Puesto

Del 12/09. **No se construyó nada**, y la razón está en CLAUDE.md: la caja
que se le manda al Puesto es un **préstamo**, no una pérdida — se va vacía y
vuelve llena. Solo se vuelve pérdida el día que no vuelve, y **cuántas no
vuelven no está en el sistema ni en ningún papel**. Cualquier columna que se
agregue hoy codifica una hipótesis sobre eso.

Esto es lo que habría que medir para poder decidir. Es trabajo de galpón, no
de software.

## El número que importa NO es cuántas salen

Contar salidas de un préstamo da un número grande y tranquilizadoramente
inútil: la mayoría vuelve. El que significa algo es el que **no cierra**:

    no volvieron = salieron − volvieron − (stock al final − stock al principio)

Los dos términos del paréntesis son los que casi siempre se olvidan, y sin
ellos la cuenta **no distingue "se perdió" de "está en camino"**. Una caja
que salió el jueves y vuelve el martes aparece como faltante todo el fin de
semana. Es el mismo papel que el testigo de actividad: sin él, un número
verdadero se lee al revés.

## Las cinco cosas a anotar

1. **Un solo circuito, no todos.** Elegir **un cliente y una ficha** —la que
   más seguido se entrega ya armada— y medir solo esa. Medir todo a la vez
   es lo que hace que no cierre ninguna.

2. **Las que salen.** El día que se le mandan las cajas vacías al Puesto:
   cuántas. Un renglón por envío, con fecha. Hoy esto no se anota en ningún
   lado.

3. **Las que vuelven.** Cuando llega la mercadería armada: cuántas cajas
   llegan. No cuántos bultos de fruta — **cajas**. Si el bulto y la caja son
   uno a uno, es el mismo número y no cuesta nada; si no lo son, el que
   sirve es el de cajas.

4. **El conteo de los dos extremos.** Cuántas cajas de esa ficha hay
   **físicamente en el Puesto** el primer día de la medición y el último.
   Son dos conteos, uno al principio y uno al final, y son los que cierran
   la cuenta de arriba.

5. **Dos semanas seguidas, sin saltear días.** El plazo tiene que ser más
   largo que la demora normal de ida y vuelta, o lo que se mide es la
   demora, no la pérdida. Un día salteado en el medio invalida la ventana
   entera: no se puede reconstruir después.

## Lo que hay que contestar ANTES de empezar

**¿La caja de esa ficha se distingue de las otras?** Si el mismo envase se
usa en otros circuitos, "cuántas cajas de esa ficha hay en el Puesto" no se
puede contar: lo que se cuente va a incluir cajas de otro lado. Si no se
distinguen, el punto 4 no se puede hacer y hay que marcarlas de alguna forma
antes de arrancar (una marca a mano en el envío de la primera semana
alcanza).

Esa pregunta decide si la medición es posible, así que va primero.

## Cómo se lee el resultado

- **Cerca de cero en dos semanas**: no hay nada que construir. Es el caso
  del 15,6% "sin dato" del Remanente — un número que se explica entero por
  otra cosa no es deuda. Se anota el resultado y se cierra el tema.
- **Un faltante chico y estable** (unas pocas por semana, siempre parecido):
  es merma de circuito y lo que hace falta es un número, no una pantalla —
  se descuenta y listo.
- **Un faltante grande o que crece**: ahí sí hay algo que registrar, y
  recién ahí tiene sentido discutir qué columna y en qué tabla. Con la
  medición hecha, esa discusión dura cinco minutos; sin ella, dura un mes y
  termina en una pantalla que nadie mira.

## Y el aviso de siempre

Si la respuesta llega como "más o menos tantas", eso **no es la medición**:
es la hipótesis otra vez, con otra ropa. El valor de esto está en que sean
conteos anotados el día que pasaron, no un recuerdo de fin de mes.

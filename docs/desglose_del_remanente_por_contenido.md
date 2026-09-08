# El desglose del Remanente por contenido: medido y NO se hace

08/09/2026. Estaba planeada una pantalla nueva —el Remanente desglosado por
contenido de cajón, con renglón "sin dato" y aviso de descuadre— y antes de
escribir una línea se corrieron dos consultas. **Las dos dijeron que no hace
falta.** Queda escrito acá para no volver a proponerla dentro de seis meses.

## La premisa era que el Remanente suma bultos incomparables

El miedo: un artículo comprado en cajones de 12u y de 40u tiene un número de
SUELTOS que suma peras con manzanas — "2 de 12u · 1 de 40u" en la misma
cuenta. El desglose venía a mostrar de qué tamaño era cada bulto.

## Medición 1 — `db/remanente_1_tamanos_y_pilas.sql` (Frutamax, corte 05/09)

```
TOTAL · tamanos_de_cajon 1 · arts_mezclados 0 · arts_con_cajas 15
```

**`arts_mezclados` = 0.** Ni un solo artículo tiene dos contenidos de cajón
conviviendo desde el corte: cada uno se compra en un formato y nada más. El
Remanente **ya suma bultos comparables**, y la pantalla que se iba a
construir no tenía nada que desglosar.

La premisa no era falsa en teoría —el esquema permite dos formatos— sino que
**no ocurre en los datos**. Si algún día se compra el mismo artículo en dos
formatos, esta consulta lo va a mostrar y se retoma.

## Medición 2 — `db/remanente_2_cuanto_queda_sin_dato.sql` (Frutamax)

```
TOTAL · cajones 809 · cajas_con_dato 674 · cajas_sin_ficha 0
      · movimientos 274 · pct_sin_dato 15.6
```

El 15,6% "sin dato" **se explica entero y es transitorio**:

- `cajas_sin_ficha` = 0 en todos los artículos → las 674 cajas de guía R
  saben su contenido; ninguna quedó sin ficha.
- Por lo tanto el 100% del "sin dato" son **movimientos**, y el grueso es el
  `stock_inicial` del corte, que es una foto que se consume y no se repone.

La aritmética cierra sin residuo: `809 + 674 + 0 + 274 = 1757`, y
`274 / 1757 = 15,59%`. **No hay un tercer origen escondido.**

El caso extremo lo confirma: Mzn Granny con 77,8% son 10 cajones comprados
contra 35 de stock inicial. A medida que se consume la foto del corte, ese
número tiende a cero solo.

## El trabajo que ahorró

Se iba a construir: una pantalla nueva del Remanente con desglose por
contenido, un renglón "sin dato" para lo que no se puede clasificar, y un
aviso de descuadre para cuando el desglose no suma al total de arriba —
porque el desglose podía no cerrar y eso había que decirlo.

**Nada de eso se necesita.** Dos consultas de menos de 2500 caracteres cada
una, corridas antes de codear, borraron una pantalla entera con su lógica de
descuadre y sus tests.

## Lo único que quedaba vivo ya está arreglado

`arts_con_cajas` = 15: quince artículos con materia prima y producto
terminado en la misma pila del FIFO, donde un reproceso puede consumir cajas
ya armadas y un armado puede costearse contra un cajón. **Ese es E5, y lo
arreglaron A (la pared) y B (las dos pasadas)**, mergeadas el 08/09. No es un
pendiente: es la medición del problema que ya se cerró.

## Pendiente de esta medición

Se corrió **solo sobre Frutamax**. Palmala tiene otro corte (31/08) y otra
operación —sin guías R—, así que su `arts_mezclados` puede no ser 0. La
decisión de no construir vale para las dos bases, y está tomada con una.
Correr `remanente_1` contra Palmala cierra eso; es gratis y es la regla del
corolario 17.

# Calculador de Precios

Reglas generales del proyecto, vigentes para todo el código que se agregue de acá en adelante.

## Idioma

Todo el código, la UI, los comentarios y los mensajes de commit van en español (Argentina).

## Diseño mobile-first (obligatorio)

El sistema lo usa principalmente una sola persona, desde el **celular** — no desde escritorio. Cualquier pantalla o componente nuevo tiene que estar optimizado para eso:

- Botones grandes y bien tocables con el dedo/pulgar (no chicos ni apretados) — pensar en un área mínima cómoda, no un link de texto chico.
- Que no haga falta hacer zoom para leer ni para tocar nada.
- Grupos de botones que entren cómodos en el ancho de un celular: si son varios, que se apilen/envuelvan en filas (`flex-wrap`), nunca que se desborden a los costados u obliguen a scrollear horizontal.
- Tablas y listados que se lean bien en celular: evitar el scroll horizontal donde se pueda; si una tabla es necesariamente ancha, pensar cómo mostrarla en celular sin que se corte (columnas compactas, abreviaturas, u otra disposición) antes de simplemente envolverla en un contenedor con scroll.
- Aprovechar el espacio vertical (es lo que sobra en celular) y cuidar el horizontal (es lo que falta).

Esto aplica a toda pantalla nueva, no solo a las de compras.

## SQL para el editor de Supabase (obligatorio)

Todo el SQL de este proyecto se corre a mano, pegado en el editor SQL de
Supabase. **Ese editor no es psql**, y dos diferencias ya nos costaron caro:

- **`begin ... commit` NO es atómico ahí.** El editor no sostiene la
  transacción: confirma cada sentencia por su cuenta. Un script que falla en
  la sentencia 7 deja aplicadas las 6 anteriores.
- **Las tablas y vistas TEMPORALES no sobreviven de una sentencia a la
  siguiente.** Una que se crea arriba ya no existe cuando la usa la de abajo,
  y el error llega *después* de que lo anterior se escribió.

De acá en adelante:

1. **Nada de tablas ni vistas temporales** en el SQL que se manda al editor.
   Lo que se necesite varias veces se repite (un CTE por consulta) o se
   guarda en una tabla real.
2. **Todo lo que tenga que ser todo-o-nada va en un único `do $$ ... end $$`.**
   Un bloque `do` sí es una sola sentencia, y ahí adentro la atomicidad y el
   `raise exception` funcionan de verdad. Las guardas y los pasos que
   dependen unos de otros van todos adentro del mismo bloque, no repartidos.
3. **Lo que tenga que verse va en UNA sola consulta final que devuelva
   filas** (el editor muestra solo el resultado de la última, y no muestra
   los NOTICE).

Esto no es una preferencia de estilo: es el entorno donde el SQL corre de
verdad. Un script probado en Postgres local puede estar correcto y aun así
romper —o peor, escribir a medias— en el editor.

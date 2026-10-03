# SQL para el editor de Supabase y el conector de lectura

Movido TAL CUAL desde CLAUDE.md el 03/10 (sin reescribir). Las reglas
vigentes, en corto, están en CLAUDE.md.

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

   **PERO NUNCA PEGADA A UN `do`, y eso es lo que costó el 15/09.** Un bloque
   `do` y su verificación **se corren POR SEPARADO**. Pegados en la misma
   corrida el editor se queda con la última y **el `do` NO SE EJECUTA**: sin
   un error, sin un NOTICE, y con "no rows"… que es exactamente la salida
   normal de un `do` que sí corrió. El check de la coherencia del conteo
   quedó puesto en UNA base y no en la otra, y lo único que lo delató fue la
   verificación corrida aparte, que dio `guarda 1` de un lado y `guarda 0`
   del otro.

   Las dos mitades de la regla tiran para lados opuestos y hay que tenerlas
   juntas: **el que ESCRIBE necesita que algo devuelva filas** (si no, no hay
   con qué distinguir "corrió" de "no corrió"), y **el que EJECUTA no puede
   poner esa consulta en la misma corrida que el `do`**. La salida es correr
   dos veces, no escribir un archivo más prolijo.

   Y por eso la verificación **vale doble cuando se corre en las dos bases**:
   dos `guarda` distintos son la única forma de ver un `do` que se salteó, y
   ninguna cantidad de mirar la pantalla del editor lo habría mostrado.
4. **Los bloques largos se TRUNCAN, y cuando truncan PEGAN SQL AJENO.** Pasó
   el 02/09 con un verificador de 5983 caracteres. El editor lo cortó a la
   mitad —en el medio de un caso— y **le concatenó código propio abajo**: un
   `ALTER TABLE cliente ENABLE ROW LEVEL SECURITY` con un comentario "Added
   by Supabase". El error que devolvió fue `unterminated dollar-quoted
   string`, que no dice una palabra de lo que pasó de verdad.

   **Eso es peor que un límite de largo.** No es que el script se corte y
   falle: es que lo que termina corriendo **no es el script que se mandó**.
   Esta vez el corte cayó adentro del `do` y dejó un dollar-quote abierto, así
   que el ALTER ajeno quedó dentro de una cadena sin cerrar y no se ejecutó
   (verificado contra la base: no quedó nada escrito). **Si el corte hubiera
   caído después del `end $$;`, ese ALTER habría sido una sentencia válida y
   habría corrido.** La seguridad de "un `do` es UNA sentencia, o parsea
   entero o no ejecuta nada" **solo vale si el corte cae ADENTRO del bloque**,
   y dónde cae no lo decidimos nosotros.

   Por eso: **ningún bloque que se mande al editor pasa los 2500
   caracteres.** Lo que no entre se parte en bloques cortos, cada uno capaz de
   correrse solo y de deshacerse solo con su propio `raise`. Y ante un error
   raro de sintaxis, **primero se mira qué quedó escrito en la base**, antes
   de suponer que no se ejecutó nada.

Esto no es una preferencia de estilo: es el entorno donde el SQL corre de
verdad. Un script probado en Postgres local puede estar correcto y aun así
romper —o peor, escribir a medias— en el editor.

**Y el CÓDIGO VA ARRIBA, la explicación al pie.** Corolario del punto 4, del
15/09: la primera versión de esa migración tenía **1486 caracteres de
comentario antes del `do`** y 790 de código. Cualquier corte que caiga antes
del `do` deja un archivo que es **puro comentario** — corre bien, no da error,
y devuelve "no rows". Medido cortando el archivo a los 1000 caracteres: el
viejo salía mudo, y el nuevo —con el bloque arriba— da `unterminated
dollar-quoted string`, que es un error que se lee.

O sea que el orden adentro del archivo decide **de qué manera falla un corte**:
con el código arriba, un corte rompe ruidosamente o no rompe nada; con los
comentarios arriba, el caso silencioso existe. No cuesta nada y se elige una
sola vez.

### Las bases se LEEN por el conector "Supabase Lectura", nunca se escriben (dueño)

Claude lee Frutamax y Palmala por el conector MCP **"Supabase Lectura"**:
el MCP de Supabase en modo `read_only`. Corre como
`supabase_read_only_user`, con `transaction_read_only = on` y sin INSERT,
UPDATE ni DELETE (medido el 02/10 con `has_table_privilege`). Un INSERT
rebota con `25006: cannot execute INSERT in a read-only transaction`.

| base | proyecto |
|---|---|
| Frutamax | `opivgeqpjgtlduxcozqz` |
| Palmala | `uygzmbqwharuhtnzqwpp` ("Palmala USA") |

- **"Verificado contra Frutamax" o "contra Palmala" quiere decir por el
  conector "Supabase Lectura"** (dueño, 02/10). Cualquier otra cosa (un
  fixture, el esquema del repo, una consulta que no se corrió) no se cita
  así. El resultado va con la base y la fecha al lado.
- **El conector "Supabase" (el que ESCRIBE) no se usa nunca, ni para leer.**
  Leer por el que escribe deja una escritura a un error de tipeo.
- **Sirve para verificar consultas contra los datos reales** antes de
  mandarlas o de citar un número (corolario 85: la colisión va ANTES de leer
  el número).
- **LAS MIGRACIONES (dueño, 02/10)**: Claude le manda el bloque a Lionel,
  Lionel lo corre en el editor de Supabase en las dos bases, y Claude corre
  la verificación por el conector, la anota en `db/corridas_confirmadas.md`
  con la fila de cada base y mergea. El dueño sigue verificando aparte.
  Claude no corre migraciones: el conector no puede, y aunque pudiera.
- **`LECTURA_FRUTAMAX_URL` queda solo para sesiones LOCALES.** Desde la nube
  no conecta: apunta al pooler por TCP al 5432 y el proxy del contenedor no
  deja pasar bases de datos por TCP crudo. Su usuario es `lectura_claudia`
  (`db/lectura_1_usuario_solo_lectura.sql`, verificación en `lectura_2`,
  creado el 02/10, solo en Frutamax), y la clave no pasa nunca por el chat.
  **Ojo: no tiene `bypassrls`**, así que en las 55 tablas con RLS y sin
  política (`compras`, `pedidos`, `movimientos_stock`…) lee CERO filas sin
  error. Ver `db/corridas_confirmadas.md`, 02/10.

## Un `if not exists` sobre CONTENIDO es una trampa, no una protección

Del 09/09. El bloque 2 de la migración de la merma de segunda crea el CHECK
con la lista de motivos permitidos, envuelto en el `if not exists` de
siempre. Se corrió con una lista, después se corrigió la lista, y se volvió
a correr: **el bloque salió `DO` y no hizo nada.** El constraint ya existía,
así que el `if not exists` lo salteó — con la lista vieja adentro.

**El modo de falla es el peor que hay: un bloque idempotente que no hace
nada se ve EXACTAMENTE IGUAL que uno que corrió bien.** Sale `DO` las dos
veces. No hay error, no hay diferencia en la pantalla, y lo que quedó en la
base no es lo que se mandó. Es la familia del push silencioso y la del
editor que escribe a medias, con una vuelta más: acá el silencio es la
respuesta CORRECTA del comando.

La distinción que hay que hacer, y es la regla:

- **Para ESTRUCTURA** —una columna, una tabla, un índice— el `if not
  exists` está bien: la columna existe o no, y si existe es la misma.
- **Para CONTENIDO** —una lista de valores permitidos, un umbral, un texto,
  una fila de configuración— **la idempotencia deja de proteger y pasa a
  esconder.** Lo que "ya existe" puede ser otra cosa que lo que se quiere.
  Ahí va `drop ... if exists` y recrear, siempre, aunque parezca de más.

**Cómo se reconoce antes de sufrirlo**: mirar qué protege el `if not
exists`. Si adentro del bloque hay una lista de literales, un número, una
fecha o una cadena, es contenido y la guarda está de más — o peor, en
contra.

Y lo único que lo agarró: **la consulta de verificación contaba el
constraint POR NOMBRE**, así que dio `guarda_lista 0` cuando el bloque ya
había salido `DO`. Es el corolario de siempre —la verificación se corre
después y mira el estado final, no que el comando no se haya quejado— con
la precisión de que **contar por nombre es lo que la hizo servir**: un
"¿existe algún check?" habría dado 1 y tapado el problema igual.

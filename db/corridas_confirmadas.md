# Qué migraciones corrieron, en qué base, y con qué fila

**Para qué existe**: el 18/09 una auditoría no pudo contestar si las tres
migraciones de Vacíos habían corrido en Frutamax. Habían corrido. Lo que
faltaba era el registro: la única fila anotada era la de Palmala, y estaba
**citada adentro de un corolario** de CLAUDE.md para ilustrar otra cosa (cómo
el testigo dice si una base vota), no anotada como confirmación.

Una fila citada para ilustrar no es un registro. El que audita no la encuentra
buscando confirmaciones, y el que la escribió tampoco se acuerda de que está
ahí — así que la pregunta *"¿esto corrió en las dos?"* se vuelve irrespondible
y hay que ir a molestar al dueño.

**Por qué acá y no al pie de cada `.sql`**: esos archivos se pegan en el editor
de Supabase y **ningún bloque pasa los 2500 caracteres**. Varios están a
menos de 50 del límite, así que un registro de cuatro líneas adentro los
volvería intruncables — se arreglaría el registro rompiendo la migración.

**Cómo se usa**: al confirmar una migración, la fila de CADA base se pega acá
con el nombre de la base adelante. Las dos, siempre: salen idénticas por
diseño salvo la población y el testigo, así que pegar una sola es exactamente
el error que esto viene a evitar.

---

## 18/09

| migración | FRUTAMAX | PALMALA |
|---|---|---|
| `renglon_agregado_a_mano` | `1 · 1 · 0 · 1921 renglones · 19/09` | `1 · 1 · 0 · 1103 renglones · 19/09` |
| `renglon_cantidad_corregida` | `1 · 1 · 0 · 1921 renglones · 19/09` | `1 · 1 · 0 · 1103 renglones · 19/09` |
| `vacios_deposito_1/2/3` (verifica `vacios_deposito_4`) | `1·1·1·1·1·1·1·1 · 38 proveedores · última recepción 18/09` | `1·1·1·1·1·1·1·1 · 44 proveedores · última recepción 17/09` |

**La población es lo que identifica la base**: 1921 contra 1103 renglones, 38
contra 44 proveedores. Las columnas que importan dan lo mismo en las dos por
diseño — ése es el resultado bueno, no una razón para pegar una sola fila.

**Y desde el 18/09 la primera columna dice QUÉ MIGRACIÓN es**
(`'<nombre>' as QUE_MIGRACION`, en las 24 verificaciones del repo). Sin eso,
dos filas de la misma base y de dos migraciones distintas se leen como las dos
bases de una — que es lo que causó el corte de esa mañana.

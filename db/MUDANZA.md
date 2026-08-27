# Mudanza de base a otro proyecto de Supabase

Runbook de la mudanza de una base a un proyecto nuevo — pensado para
**cambiar de región**, que es lo que el botón "Restore to a new project"
del dashboard **no** puede hacer (crea el proyecto nuevo en la misma
región del viejo, por residencia de datos).

Todo se corre **desde el SQL Editor de Supabase**, sin línea de comandos.
La única parte que no es SQL es la copia del bucket de Storage.

## Lo que hay que saber antes de empezar

- Son **40 tablas** con FKs entre sí, en 4 niveles de dependencia. Los
  scripts ya llevan el orden correcto, sacado del esquema real.
- Los ids se copian **tal cual**. No es solo por las FKs: los ids de
  `guias_compra` y `reprocesos` son el número de guía de compra y el de
  guía R, que se ven en pantalla.
- **La base nueva no nace vacía**: `esquema_completo.sql` siembra el plan
  de cuentas de Costos Fijos. Por eso el paso 2 vacía antes de copiar.
- **Las fotos no viajan con la base.** Los bytes viven en el Storage; la
  base solo guarda las rutas (`fotos_guia.foto_ruta`,
  `fotos_pedido.foto_ruta`, `precios_venta_historial.foto_ruta`).
- El SQL Editor tiene **timeout de 1 minuto** por corrida. Con el tamaño
  de estas bases (cientos de filas por tabla) sobra, pero conviene mirar
  el tamaño antes (consulta al final de este archivo).

## Preparación (se puede hacer días antes, sin apuro)

1. **Crear el proyecto nuevo** en la región que corresponde — la misma, o
   la más cercana, al servicio de Railway que lo va a usar.
2. En la base nueva, correr **`db/esquema_completo.sql`** entero, una vez.
3. **Crear el bucket `comandas`** en el proyecto nuevo: Storage → New
   bucket → nombre exacto `comandas`, **privado**. Sin esto, la copia de
   archivos no tiene dónde entrar.
4. Anotar del proyecto viejo (Dashboard → Connect): el host del **Session
   pooler** (`aws-N-<region>.pooler.supabase.com`) y el usuario
   (`postgres.<ref-del-proyecto>`). **No uses el host directo**: es IPv6 y
   la conexión entre proyectos puede no salir.
5. Opcional pero recomendado ahora que hay plan Pro: **activar PITR** en
   el proyecto viejo. Es la red por si algo sale mal el día del corte.

## El día del corte

Con el sistema quieto: nadie cargando compras, pedidos ni precios.

1. **Paso 1** — `db/mudanza_01_conectar_origen.sql` en el SQL Editor de la
   base **nueva**, completando host, usuario y contraseña del proyecto
   viejo. Tiene que decir 40 tablas enganchadas.
2. **Paso 2** — `db/mudanza_02_copiar_datos.sql`, igual, en la nueva.
   Copia todo y ajusta las secuencias. Es idempotente: si algo sale mal se
   arregla y se corre de nuevo, sin limpiar nada a mano.
3. **Paso 3** — `db/mudanza_03_verificar.sql`. Es de solo lectura. Tiene
   que decir **TODO IGUAL** y **SECUENCIAS OK**.
4. **Copiar el Storage** (abajo).
5. **Checklist** (abajo). Recién ahí se tocan las variables de Railway.
6. **Paso 4** — `db/mudanza_04_desconectar.sql`, cuando ya no vayas a
   copiar más. Borra el enganche, que guarda la contraseña de la vieja.

Si entre el paso 2 y el corte llegás a cargar algo en la base vieja, no
pasa nada: corré de nuevo el paso 2 y después el 3. El paso 3 también
sirve para eso — si dice TODO IGUAL, es que no se cargó nada nuevo.

## Copiar el bucket de Storage

Los archivos del bucket `comandas` no salen en ningún backup ni en ningún
restore de base. Hay que moverlos aparte, y sin línea de comandos hay dos
caminos:

- **El script de Google Colab que publica Supabase** para migrar objetos
  entre proyectos. Corre entero en el navegador.
- **Un cliente S3 con interfaz gráfica** (Cyberduck y similares) contra el
  endpoint S3 de Storage. Se habilita en Storage → Configuration → S3, que
  da un access key y un secret. La copia S3-a-S3 es la recomendada porque
  hace que Storage arme bien los registros de metadatos del lado nuevo.

Después de copiar, el paso 3 vuelve a servir: su último resultado compara
la cantidad de archivos del bucket contra las filas que los referencian.

## Checklist antes de cambiar el DATABASE_URL

Ninguno de estos es opcional.

- [ ] Paso 3 dice **TODO IGUAL** (40 tablas) y **SECUENCIAS OK**.
- [ ] La cantidad de archivos del bucket en el proyecto nuevo coincide con
      la del viejo (último resultado del paso 3, corrido en las dos).
- [ ] El proyecto nuevo está en la región que querías. Confirmado en el
      dashboard, no de memoria.
- [ ] Probaste la app apuntando a la base nueva **antes** de tocar
      producción: entrar a Compras, Armar Pedido, Stock del Sistema,
      Lista de Precios y Rentabilidad, y **abrir una foto de una comanda**
      (eso prueba la base y el Storage juntos).
- [ ] Cargaste **las tres** variables en Railway, en **los dos** servicios
      si corresponde: `DATABASE_URL`, `SUPABASE_URL` y
      `SUPABASE_SERVICE_KEY`. La mudanza no es solo la base.
- [ ] La base vieja **queda viva** unos días, sin borrar, por si hay que
      volver. Volver = revertir las variables de Railway, nada más.
- [ ] Después del corte, dar de alta algo real y chico (un cliente de
      prueba, y borrarlo) para confirmar que las secuencias andan.

## Después

- Correr el **paso 4** y, en el dashboard del proyecto viejo, **rotar la
  contraseña de la base**: quedó escrita en el historial del SQL Editor de
  la base nueva.
- Cuando la nueva lleve unos días andando, dar de baja el proyecto viejo.

## Consulta de tamaño (correr en la base vieja, antes de arrancar)

Sirve para saber si el timeout de 1 minuto puede molestar.

```sql
select relname as tabla, n_live_tup as filas_aprox,
       pg_size_pretty(pg_total_relation_size(relid)) as tamano
  from pg_stat_user_tables
 order by n_live_tup desc
 limit 15;
```

---

## Lo que pasó al hacerla de verdad (Palmala, 2026-08-27)

La mudanza se ejecutó: Palmala pasó de `sa-east-1` (São Paulo) a `us-west-1`
(North California), que es donde está el servicio de Railway. Resultado:
la app pasó a andar como Frutamax, que era la predicción.

**La decisión de región es contraintuitiva y conviene no olvidarla.** El
celular le habla a Railway UNA vez por pantalla; Railway le habla a la base
cientos de veces para armar esa misma pantalla. Así que la base no va cerca
del usuario: va **pegada a Railway**. Ese fue todo el problema.

Cuatro cosas que solo aparecieron contra una base con historia, y que los
scripts ya contemplan:

- **El orden de las columnas no coincide.** En la base vieja, lo agregado con
  ALTER TABLE quedó al final; en esquema_completo.sql está en su lugar
  lógico. `select *` mapea por posición y falla. Por eso la copia y la
  verificación nombran las columnas una por una.
- **El SQL Editor muestra solo el resultado de la ÚLTIMA consulta**, y no
  muestra los mensajes NOTICE. Todo lo que tenga que verse va en una sola
  consulta final que devuelva filas.
- **revision_tick cambia solo**: es el latido del bucle de revisión, y la app
  viva lo mueve entre la copia y la verificación. Se informa aparte.
- **Las rutas de archivos viven en TRES tablas**, no dos: fotos_guia,
  fotos_pedido y precios_venta_historial.foto_ruta.

Sobre el Storage: eran 33 archivos en 8 carpetas por fecha. Se movieron a
mano desde el panel (bajar y subir, carpeta por carpeta), sin herramientas.
Para ese volumen alcanza; la clave es que la ruta quede idéntica, y eso se
verifica cruzando ruta por ruta contra storage.objects, no contando.

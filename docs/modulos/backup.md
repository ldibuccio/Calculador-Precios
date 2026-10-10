# Módulo: plan B de backup

Movido TAL CUAL desde CLAUDE.md el 03/10 (sin reescribir). Las reglas
vigentes, en corto, están en CLAUDE.md.

## PLAN B DE BACKUP (02/10, dueño)

Todo se tiene que poder reconstruir aunque desaparezcan Supabase, Railway o
GitHub. **Todos los días a las 03:47 de Argentina** (`.github/workflows/backup.yml`;
desde el 09/10 lo lanza el sistema y el cron `47 6 * * *` UTC queda de
respaldo, ver abajo) tres partes van a **OneDrive Y Google Drive** de Lionel,
**cifradas con rclone crypt**. La regla pura vive en `core/backup.py`, la
corrida en `scripts/backup.py`, y cómo se vuelve todo en `RESTAURAR.md`, que
también se sube SIN cifrar a la carpeta `Backup-Sistema` de cada nube.

> **SIN LA CLAVE DE CIFRADO EL BACKUP NO SIRVE.** Se generó una vez, se le
> mostró a Lionel una vez para que la imprima, y vive en el secret
> `BACKUP_CLAVE`. No está en el repo ni en ninguna nube.

- **Código**: `git bundle --all`, `calculador-precios_AAAA-MM-DD.bundle`. Se
  baja de cada destino y se clona para dar la parte por buena.
- **Bases**: `pg_dump` custom (cliente 17) de Frutamax, Palmala y Ganadería,
  en un snapshot exportado: el manifiesto (tablas y filas de TODAS) sale de
  la misma foto que el dump. **Van los esquemas que no son de Supabase**
  (`public`, y `memoria` en Ganadería), porque los de Supabase (`auth`,
  `storage`, `extensions`…) los trae cualquier proyecto nuevo y restaurarlos
  encima pisaría su versión. De esos van como CSV `storage.buckets`,
  `storage.objects` (la app lee `created_at`: re-subir las fotos les pone la
  fecha de hoy) y `auth.users`/`identities`. **Ganadería no las intenta**
  (`PROYECTOS_SIN_TABLAS_DE_SUPABASE`, 03/10): entra con `backup_lectura`,
  que solo lee public y memoria (medido: 18 de 18 tablas y 15 de 15
  secuencias con SELECT, y las cuatro de Supabase en cero filas). Es una
  lista decidida: en Frutamax o Palmala un permiso perdido hace fallar la
  parte, no la saltea. **Se RESTAURA todos los días**:
  se baja de cada destino y va a un Postgres 17 descartable. Si la cantidad
  de tablas o las filas de alguna no coinciden con el manifiesto, la parte NO
  es exitosa. La restauración se saltea `CREATE SCHEMA public`
  (`lista_para_restaurar`) y crea los roles que nombran las políticas
  (Ganadería: `bot_lectura`, `bot_escritura`, medido el 02/10).
- **Fotos**: todos los buckets de los tres proyectos, por la API S3 del
  Storage, `copy --ignore-existing` (incremental) y **nunca se borra**: lo que
  el plazo de 3 años borra en el sistema sigue en el backup. Se comprueba con
  checksum (`cryptcheck`), y por tamaño si el origen no da checksum.
  **La copia y el control trabajan sobre la lista de fotos tomada AL
  ARRANCAR** (`--files-from-raw`, dueño 09/10): el 07/10 y el 08/10 el
  control dio rojo por una foto subida mientras corría la copia. Las que
  entran después van en la copia siguiente.
- **Rotación de código y bases**: las diarias de 30 días y, de cada uno de
  los últimos 12 meses, la PRIMERA copia. Se rota solo después de un éxito en
  ese destino. Las fotos no rotan.
- **Una parte es exitosa si llegó a LOS DOS destinos.** Cada parte graba
  `(parte, onedrive_ok, gdrive_ok, detalle)` en `backups_corridas`, en
  **Frutamax y en Palmala** (cada app ve su base), con el rol
  `backup_estado`, que SOLO puede insertar ahí (`db/backups_1` a `_3`). Si no
  puede grabar en una, igual graba en la otra y la corrida sale en rojo.
- **Gerencia → Backups** (`/gerencia/backups`): la fecha del último backup
  bueno de cada parte y, si la última corrida falló en un destino, cuál, y a
  cuál SÍ llegó ("esa copia está en un solo lugar"). Las causas que ya
  pasaron se dicen en criollo (`CAUSAS_CONOCIDAS` en `core/backup.py`, hoy
  solo `rateLimitExceeded`, 04/10) y la salida de rclone va a la "i"; una
  causa desconocida se muestra tal cual. La
  alerta `backups_viejos` (solo Gerencia) salta con **más de 48 horas** sin
  uno bueno, o ninguno. Nada de mails.
- **El token de OneDrive se renueva solo** y el renovado se guarda en la
  cache de Actions, cifrado con la misma clave
  (`.github/acciones/guardar-token`). Si Lionel cambia el secret
  `RCLONE_CONF`, la huella cambia y manda el secret.
- **Ninguna credencial va en el repo**: todo son secrets, la lista y de dónde
  sale cada uno está en `docs/backup_guia_para_lionel.md`.

Lo cuida `tests/test_backup.py`: las reglas, y un simulacro de punta a punta
contra Postgres y rclone de verdad (dos destinos locales con el mismo crypt),
que descifra con una configuración nueva y solo la clave, igual que
RESTAURAR.md. Lo que no se puede correr acá es la red real: lo prueba la
primera corrida del workflow.

**REVISIÓN ANUAL (cada octubre)**: cuánto ocupan las fotos y las bases en
cada nube y cuánto lugar queda; si alcanza con 30 diarias y 12 mensuales; y
qué hacer con las fotos cuando pesen (no rotan nunca: o se compra más lugar,
o se decide un corte). Y probar `RESTAURAR.md` de punta a punta otra vez,
con la clave impresa y no la del secret.

### El schedule de GitHub no es una garantía (03/10)

La primera corrida programada (07:00 UTC del 03/10) **no se creó nunca**: el
workflow estaba activo, el cron bien escrito y en `main`, y el repo tenía cero
corridas con evento `schedule`. GitHub avisa en su documentación que con carga
atrasa o DESCARTA los schedule, y la hora en punto es la más cargada. No queda
rastro: no hay corrida roja que mirar, simplemente no hay corrida.

- **La corrida va a las 06:47 UTC (03:47 AR)**, fuera de la hora en punto.
- **Hay una de RESPALDO a las 10:17 UTC (07:17 AR)**. El job `hace_falta`
  pregunta a la API de Actions si hoy (desde las 00:00 de Argentina) ya hubo
  un Backup que terminó bien. Si hubo, se saltea; si no, o si la consulta
  falla, hace el backup. Una corrida a mano siempre corre.
- **El 04/10 las dos llegaron, pero 5 y 6 horas tarde** (09:52 y 12:23 AR).
  La primera falló en Google Drive y la de respaldo la repitió: el diseño
  anduvo. Detalle en `db/corridas_confirmadas.md`.
- **Lo que avisa si las dos se pierden** sigue siendo la alerta
  `backups_viejos` de Gerencia (más de 48 horas sin uno bueno).

### Desde el 09/10 lo lanza el sistema (dueño)

Del 04/10 al 08/10 las dos corridas programadas salieron TODOS los días entre
6 y 8 horas y media tarde (la de las 03:47 corría a las 11). Las lanzadas a
mano salen en el momento. Así que:

- **El reloj de fondo del sistema** (el mismo que recalcula Alertas y Panel)
  le pide a GitHub que corra el Backup a las 03:47 de Argentina
  (`_lanzar_backup_si_toca`, `core/backup_github.py`), con `origen=sistema`.
  Ventana de 03:47 a 07:00; si GitHub no contesta, reintenta cada 15 minutos.
- **Los dos schedule quedan de respaldo**: `hace_falta` saltea cualquier
  corrida programada o del sistema si hoy ya hubo un Backup bueno. Una
  corrida lanzada a mano desde GitHub siempre corre.
- **La llave** es la variable `BACKUP_GITHUB_TOKEN` de Railway: un token
  fine-grained de GitHub, solo el repo Calculador-Precios, solo permiso de
  Actions (lectura y escritura). **No vence**: el dueño la regeneró sin
  vencimiento (09/10), cargada en Frutamax y Palmala. Sin la llave el
  sistema no lanza nada y quedan los schedule.
- **Gerencia → Backups avisa** arriba si la llave falta, si no anda, o si
  vence en menos de 30 días (`DIAS_DE_AVISO`): la fecha la manda GitHub en
  cada respuesta (`github-authentication-token-expiration`). Sin vencimiento
  (la de hoy) dice en verde "La llave de GitHub anda y no tiene
  vencimiento." Se le pregunta
  una vez por hora como mucho.
- Si la llave está en las dos aplicaciones, las dos lanzan: el workflow corre
  de a uno y el segundo se saltea.

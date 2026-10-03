# Módulo: plan B de backup

Movido TAL CUAL desde CLAUDE.md el 03/10 (sin reescribir). Las reglas
vigentes, en corto, están en CLAUDE.md.

## PLAN B DE BACKUP (02/10, dueño)

Todo se tiene que poder reconstruir aunque desaparezcan Supabase, Railway o
GitHub. **Todos los días a las 04:00 de Argentina** (`.github/workflows/backup.yml`,
cron `0 7 * * *` UTC) tres partes van a **OneDrive Y Google Drive** de Lionel,
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
- **Rotación de código y bases**: las diarias de 30 días y, de cada uno de
  los últimos 12 meses, la PRIMERA copia. Se rota solo después de un éxito en
  ese destino. Las fotos no rotan.
- **Una parte es exitosa si llegó a LOS DOS destinos.** Cada parte graba
  `(parte, onedrive_ok, gdrive_ok, detalle)` en `backups_corridas`, en
  **Frutamax y en Palmala** (cada app ve su base), con el rol
  `backup_estado`, que SOLO puede insertar ahí (`db/backups_1` a `_3`). Si no
  puede grabar en una, igual graba en la otra y la corrida sale en rojo.
- **Gerencia → Backups** (`/gerencia/backups`): la fecha del último backup
  bueno de cada parte y, si la última corrida falló en un destino, cuál. La
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

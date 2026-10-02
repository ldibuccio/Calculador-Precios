# Backup: lo que tenés que hacer vos (una sola vez)

Son cuatro cosas y en este orden. Todo desde la computadora; el celular no alcanza
para la parte 2.

> **LA CLAVE DE CIFRADO.** Te la mandé una sola vez en el chat. **Imprimila y
> guardala en papel**, lejos de la computadora y fuera de OneDrive y Google
> Drive. Sin esa clave el backup **no sirve para nada**: está todo cifrado y
> nadie lo puede abrir, ni vos, ni un técnico, ni Microsoft, ni Google. Si se
> pierde, hay que generar una nueva y empezar los backups de cero.

---

## 1. Correr la migración (Supabase, en las dos bases)

Los bloques van en el mensaje: `backups_1`, después `backups_2` (con la clave
del rol de ESA base, que es distinta en cada una) y, **aparte**, la
verificación `backups_3`. En Frutamax y en Palmala. En Ganadería no.

## 2. Autorizar rclone con OneDrive y Google Drive

rclone es el programa que sube los archivos. Hay que darle permiso una vez, desde
tu computadora, porque Microsoft y Google piden que entres con tu usuario.

1. Bajá rclone de **https://rclone.org/downloads/** (Windows, "Intel/AMD 64 Bit").
   Descomprimí el zip en `C:\rclone`.
2. Abrí "Símbolo del sistema" (tecla Windows, escribí `cmd`, Enter) y escribí:

   ```
   cd C:\rclone
   rclone config
   ```

3. **OneDrive.** Contestá así (lo que no está acá, Enter):
   - `n` (nuevo remoto) → nombre: **`onedrive`** (exactamente así, en minúscula)
   - tipo de almacenamiento: escribí **`onedrive`**
   - `client_id` y `client_secret`: Enter (vacíos)
   - región: `1` (Microsoft Cloud Global)
   - "Edit advanced config?": `n`
   - "Use web browser to automatically authenticate?": `y` → se abre el
     navegador, entrás con tu cuenta de Microsoft y aceptás.
   - tipo de cuenta: `1` (OneDrive Personal or Business)
   - elegí tu unidad (normalmente hay una sola: `0`) → `y` para confirmar → `y`.
4. **Google Drive.** Otra vez `n`:
   - nombre: **`gdrive`**
   - tipo: **`drive`**
   - `client_id` y `client_secret`: Enter (vacíos)
   - scope: `1` (acceso completo)
   - `service_account_file`: Enter
   - "Edit advanced config?": `n`
   - "Use web browser…?": `y` → entrás con tu cuenta de Google y aceptás.
   - "Configure this as a Shared Drive?": `n` → `y` para confirmar.
5. `q` para salir. Probá que anden:

   ```
   rclone lsd onedrive:
   rclone lsd gdrive:
   ```

   Tienen que listar las carpetas de cada nube. Si alguno da error, repetí su paso.
6. Mostrá la configuración, que es lo que va al secret `RCLONE_CONF`:

   ```
   rclone config show
   ```

   Copiá **todo** lo que imprime (desde `[gdrive]` hasta el final de `[onedrive]`).
   Ojo: ese texto es la llave de tus dos nubes. Va solo al secret, no lo
   mandes por mail ni por chat.

## 3. Cargar los secrets en GitHub

GitHub → el repo `Calculador-Precios` → **Settings** → **Secrets and
variables** → **Actions** → **New repository secret**. Uno por uno, con el
nombre **exactamente** como está acá:

| nombre del secret | qué va | de dónde sale |
|---|---|---|
| `BACKUP_CLAVE` | la clave de cifrado | la que imprimiste (con los guiones) |
| `RCLONE_CONF` | la configuración de rclone | lo que copiaste en el paso 2.6 |
| `FRUTAMAX_DB_URL` | la conexión a la base de Frutamax | ver abajo |
| `PALMALA_DB_URL` | la conexión a la base de Palmala | ver abajo |
| `GANADERIA_DB_URL` | la conexión a la base de Ganadería | ver abajo |
| `FRUTAMAX_S3_KEY_ID` | el "Access key ID" de las fotos de Frutamax | ver abajo |
| `FRUTAMAX_S3_SECRET` | el "Secret access key" de Frutamax | ver abajo |
| `FRUTAMAX_S3_REGION` | la región de Frutamax (ej. `sa-east-1`) | ver abajo |
| `PALMALA_S3_KEY_ID`, `PALMALA_S3_SECRET`, `PALMALA_S3_REGION` | lo mismo, de Palmala | ver abajo |
| `GANADERIA_S3_KEY_ID`, `GANADERIA_S3_SECRET`, `GANADERIA_S3_REGION` | lo mismo, de Ganadería | ver abajo |
| `ESTADO_FRUTAMAX_URL` | la conexión del rol `backup_estado` en Frutamax | ver abajo |
| `ESTADO_PALMALA_URL` | la conexión del rol `backup_estado` en Palmala | ver abajo |

**Las conexiones a las bases (`<EMPRESA>_DB_URL`).** En Supabase, el proyecto →
botón **Connect** arriba → **Session pooler**. Es una línea así:

```
postgresql://postgres.<ref>:[YOUR-PASSWORD]@aws-0-<region>.pooler.supabase.com:5432/postgres
```

Reemplazá `[YOUR-PASSWORD]` por la contraseña de la base (la misma que usa
Railway en `DATABASE_URL`). Tiene que ser la de **Session pooler**, puerto
**5432**; la de "Direct connection" no anda desde GitHub. **No resetees la
contraseña** para sacarla: si la cambiás, Railway deja de conectarse hasta que
la cambies también ahí.

**Las llaves de las fotos (`<EMPRESA>_S3_…`).** En Supabase, el proyecto →
**Storage** → **S3 Configuration** (o Settings → Storage). Ahí están el
endpoint y la **región** (para `_S3_REGION`). Abajo, **New access key** →
le ponés de nombre "backup" → te muestra el **Access key ID** y el **Secret
access key**. El secret se ve **una sola vez**: copialo directo a GitHub.
Ganadería hoy no tiene fotos, pero las llaves van igual: el día que tenga, ya
entran al backup.

**Las del estado (`ESTADO_<EMPRESA>_URL`).** Es la misma línea del Session
pooler de esa base, cambiando el usuario y la contraseña:

```
postgresql://backup_estado.<ref>:<CLAVE DEL ROL>@aws-0-<region>.pooler.supabase.com:5432/postgres
```

`<ref>` es el mismo que aparece después de `postgres.` en la otra línea, y la
clave del rol es la que te mandé para esa base (la misma que pegaste en
`backups_2`). Este usuario **solo puede anotar** en la tabla de backups: no lee
ni toca nada más.

## 4. La primera corrida

GitHub → **Actions** → **Backup** → **Run workflow**. Tarda unos minutos (la
primera vez más, por las fotos). Cuando termine:

- los tres pasos tienen que estar en verde;
- en **Gerencia → Backups** tienen que aparecer las tres fechas de hoy;
- en OneDrive y en Google Drive tiene que haber una carpeta **`Backup-Sistema`**
  con una carpeta `cifrado` (nombres raros: es lo cifrado) y el archivo
  `LEEME-RESTAURAR.md`, que se lee.

De ahí en adelante corre solo todos los días a las 4 de la mañana. Si algo se
atrasa más de 2 días, aparece en las alertas de Gerencia.

## Una vez por año

Mirá en Gerencia → Fotos y espacio cuánto ocupan las fotos y cuánto lugar te
queda en OneDrive y en Google Drive, y decidí si alcanza con 30 diarias y 12
mensuales.

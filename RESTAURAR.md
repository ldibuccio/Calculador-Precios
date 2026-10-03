# Cómo reconstruir todo desde el backup

Este archivo está también, **sin cifrar**, en la carpeta `Backup-Sistema` del
OneDrive y del Google Drive. Sirve aunque no exista más GitHub, ni Railway, ni
Supabase: alcanza con una de las dos copias y **la clave de cifrado impresa**.

> **SIN LA CLAVE NO HAY BACKUP.** Todo lo que está en `Backup-Sistema/cifrado`
> está cifrado con esa clave. Si se pierde, nadie lo puede abrir: ni Lionel,
> ni un técnico, ni Microsoft, ni Google. Está impresa y guardada en papel.

Lo que hay adentro, una vez descifrado:

```
codigo/calculador-precios_AAAA-MM-DD.bundle   el programa entero, con toda su historia
bases/AAAA-MM-DD/<proyecto>/base.dump        la base (frutamax, palmala, ganaderia)
bases/AAAA-MM-DD/<proyecto>/manifiesto.json  qué tenía: tablas, filas, roles
bases/AAAA-MM-DD/<proyecto>/storage.objects.csv  cuándo se subió cada foto
bases/AAAA-MM-DD/<proyecto>/auth.users.csv   usuarios de login (si los hay)
   (Ganadería no trae estos CSV: su usuario de backup no lee auth ni storage)
fotos/<proyecto>/<bucket>/...                todas las fotos, con su ruta original
```

Hay una copia por día de los últimos 30 días y una por mes de los últimos 12.
Las fotos no se borran nunca.

Hace falta una computadora con `rclone`, `git`, `python3` y el cliente de
PostgreSQL 17 (`pg_restore`, `psql`). En Windows anda igual desde WSL.

---

## 1. Bajar y descifrar

Bajá la carpeta `Backup-Sistema/cifrado` entera, desde la web de OneDrive o de
Google Drive, a una carpeta de la computadora (por ejemplo `C:\backup\cifrado`
o `~/backup/cifrado`). Después, con la clave impresa:

```bash
rclone config create descifrar crypt remote=$HOME/backup/cifrado password='LA-CLAVE-IMPRESA' --obscure
rclone lsf -R descifrar: | head          # tienen que verse nombres legibles: codigo/, bases/, fotos/
rclone copy descifrar: $HOME/backup/claro --progress
```

Si `lsf` no muestra nada y avisa `Skipping undecryptable`, la clave está mal
tipeada (mayúsculas, guiones). La clave se usa **exactamente** como está
impresa, guiones incluidos.

Para bajar solo un día de bases: `rclone copy descifrar:bases/2026-10-02 $HOME/backup/claro/bases/2026-10-02`.

## 2. El programa

```bash
git clone $HOME/backup/claro/codigo/calculador-precios_AAAA-MM-DD.bundle calculador-precios
```

Usá el bundle más nuevo. Se puede subir a un repo nuevo de GitHub (o de donde
sea) con `git remote add origin <url> && git push -u origin --all`.

## 3. La base, en un proyecto nuevo de Supabase

1. Crear el proyecto en Supabase (PostgreSQL 17). Anotar la contraseña de la base.
2. Copiar la conexión: Supabase → **Connect** → *Session pooler* (anda desde
   cualquier red). Queda como `postgresql://postgres.<ref>:<contraseña>@<host>:5432/postgres`.
3. Crear los roles que nombra el manifiesto (están en `"roles"`; en Frutamax y
   Palmala no hay ninguno, en Ganadería son `bot_lectura` y `bot_escritura`).
   En el editor SQL de Supabase, uno por uno:
   `create role bot_lectura login password 'una-nueva';` (las contraseñas viejas
   no se guardan: se ponen nuevas y se cambian donde se usaban).
4. Restaurar, salteando la creación de `public`, que el proyecto nuevo ya trae:

```bash
cd $HOME/backup/claro/bases/AAAA-MM-DD/frutamax
pg_restore --list base.dump | grep -v ' SCHEMA - public ' | grep -v ' COMMENT - SCHEMA public ' > lista
pg_restore --no-owner --no-privileges --use-list lista --dbname "LA-CONEXION" base.dump
```

5. Comprobar: el manifiesto dice cuántas filas tenía cada tabla (`"filas"`).
   Por ejemplo `psql "LA-CONEXION" -c "select count(*) from compras"` tiene que
   dar el número de `"public.compras"`.

Los permisos de otros usuarios de la base (por ejemplo `lectura_claude` o
`backup_estado`) no vienen: se vuelven a crear con sus `.sql` de la carpeta `db/`
del programa (`db/lectura_1_usuario_solo_lectura.sql`, `db/backups_2_rol.sql`).

## 4. Las fotos

1. En el proyecto nuevo, Storage → crear los buckets con el **mismo nombre**
   que las carpetas de `fotos/<proyecto>/` (en este sistema: `comandas`), privados.
2. Storage → S3 → crear una llave de acceso. Con ella:

```bash
rclone config create nuevo s3 provider=Other access_key_id=LLAVE secret_access_key=SECRETO \
  region=LA-REGION endpoint=https://<ref-nuevo>.supabase.co/storage/v1/s3 force_path_style=true
rclone copy $HOME/backup/claro/fotos/frutamax/comandas nuevo:comandas --progress
```

3. La app usa la FECHA DE SUBIDA de cada foto (el plazo de 3 años, el mes a
   mes). Al volver a subirlas quedan con la fecha de hoy. Para devolverles la
   original, con `psql`:

```sql
create table restaurar_objetos (like storage.objects including defaults);
\copy restaurar_objetos from 'storage.objects.csv' csv header
update storage.objects o set created_at = r.created_at
  from restaurar_objetos r where r.bucket_id = o.bucket_id and r.name = o.name;
drop table restaurar_objetos;
```

## 5. Levantar la app

En Railway, Render o cualquier lugar que corra Python: `pip install -r
requirements.txt` y `python -m app.main` (es lo que dice el `Procfile`). Las
variables de entorno son:

| variable | de dónde sale |
|---|---|
| `DATABASE_URL` | la conexión del paso 3 |
| `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` | Supabase → Project Settings → API del proyecto nuevo |
| `CLAVE_GERENCIA`, `CLAVE_ADMINISTRACION`, `CLAVE_COMPRAS`, `CLAVE_CONTROL_PUESTO` | las claves de cada sector (las sabe Lionel; se pueden poner nuevas) |
| `ANTHROPIC_API_KEY` | una llave nueva de console.anthropic.com |
| `CLAVE_CASILLA_PEDIDOS` | la contraseña de la casilla de mail de los pedidos |
| `NOMBRE_EMPRESA`, `TIPO_RETIRO_DEFAULT` | los mismos que tenía (Frutamax / Palmala) |

Ninguna de estas va en el backup a propósito: son credenciales, y un backup que
las tuviera sería una llave de todo el sistema guardada en dos nubes.

---

Probado de punta a punta el 02/10/2026 con una copia real del simulacro: bajar
con una configuración de rclone nueva y solo la clave, descifrar, restaurar la
base y contarla contra el manifiesto, y clonar el bundle.

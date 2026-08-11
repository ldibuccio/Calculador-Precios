-- Abre clientes_parametros_historial a una lista abierta de conceptos por
-- cliente (hoy solo admitía 'descuento' y 'utilidad_objetivo'), para poder
-- cargar conceptos nuevos (flete, IVA, premios, etc.) sin tocar código cada
-- vez que aparece uno.
--
-- Agrega una columna "tipo" que clasifica QUÉ HACE el concepto con el
-- precio, separado de nombre_parametro (que pasa a ser la ETIQUETA libre
-- que el usuario le pone, ej. "flete", "iva", "fondo publicidad"):
--   'suma'     = tasas que se suman al precio, plata del cliente (ej. IVA, premio).
--   'resta'    = porcentajes que se descuentan del precio (ej. logística/descuento, flete).
--   'utilidad' = el margen objetivo del cliente.
--
-- Solo la base: esto NO toca core/motor_costeo.py ni ninguna fórmula. Los
-- parámetros de Día que ya existen se reclasifican (descuento -> resta,
-- utilidad_objetivo -> utilidad) para que ninguna fila quede sin tipo.
--
-- Seguro de correr más de una vez: agregar la columna es "if not exists", el
-- backfill solo toca filas con tipo todavía nulo, y el SET NOT NULL es un
-- no-op si ya está en not null.
--
-- Correr a mano en el editor SQL de Supabase, DESPUÉS de
-- db/migracion_clientes_final.sql. NO se ejecuta acá.

begin;

-- 1. Columna nueva "tipo", nullable por ahora (se pone NOT NULL recién al
-- final, después de reclasificar lo que ya existe). El CHECK va desde ya:
-- una fila con tipo cargado tiene que venir con uno de estos tres valores,
-- pero una fila con tipo todavía NULL pasa el CHECK sin problema (un CHECK
-- no evalúa filas con NULL como violación).
alter table clientes_parametros_historial
    add column if not exists tipo text
    check (tipo in ('suma', 'resta', 'utilidad'));

comment on column clientes_parametros_historial.tipo is
    'Qué hace el concepto con el precio: suma (se suma, plata del cliente, ej. IVA/premio), resta (se descuenta, ej. logística/flete) o utilidad (margen objetivo).';

-- 2. Sacar el CHECK viejo que limitaba nombre_parametro a
-- 'descuento'/'utilidad_objetivo'. Se busca por definición en vez de por
-- nombre fijo, porque el nombre que le puso Postgres al crear la tabla
-- (algo como clientes_parametros_historial_nombre_parametro_check) no está
-- confirmado contra la base real — así funciona sin importar cómo se llame.
do $$
declare
    r record;
begin
    for r in
        select conname
        from pg_constraint
        where conrelid = 'clientes_parametros_historial'::regclass
          and contype = 'c'
          and pg_get_constraintdef(oid) ilike '%nombre_parametro%'
    loop
        execute format('alter table clientes_parametros_historial drop constraint %I', r.conname);
    end loop;
end $$;

-- nombre_parametro sigue not null (sigue siendo obligatorio poner una
-- etiqueta), pero ya no está atado a una lista fija de valores permitidos.
comment on column clientes_parametros_historial.nombre_parametro is
    'Etiqueta libre del concepto (ej. descuento, utilidad_objetivo, flete, iva, fondo publicidad). Qué hace con el precio lo dice la columna tipo.';

-- 3. Reclasificar lo que ya existe, para que ninguna fila quede con tipo
-- nulo. Solo toca las filas que hoy usan los dos nombres que existían antes
-- de este cambio.
update clientes_parametros_historial
set tipo = 'resta'
where nombre_parametro = 'descuento' and tipo is null;

update clientes_parametros_historial
set tipo = 'utilidad'
where nombre_parametro = 'utilidad_objetivo' and tipo is null;

-- 4. Verificación explícita antes de exigir NOT NULL: si quedó alguna fila
-- sin tipo (por ejemplo, algún nombre_parametro que no sea ninguno de los
-- dos de arriba, que no debería existir porque el CHECK viejo no lo
-- permitía, pero mejor confirmarlo con un mensaje claro que con el error
-- genérico de Postgres si el ALTER de más abajo fallara).
do $$
declare
    faltantes int;
begin
    select count(*) into faltantes from clientes_parametros_historial where tipo is null;
    if faltantes > 0 then
        raise exception 'Quedaron % fila(s) en clientes_parametros_historial sin tipo asignado. Revisar antes de continuar.', faltantes;
    end if;
end $$;

-- 5. A partir de acá, tipo es obligatorio para toda fila nueva también.
alter table clientes_parametros_historial alter column tipo set not null;

comment on table clientes_parametros_historial is
    'Conceptos que afectan el precio de cada cliente (descuento, utilidad, y cualquier otro que se cargue: flete, IVA, premios, etc.), con historial por fecha de vigencia. Cada concepto tiene una etiqueta libre (nombre_parametro) y una clasificación fija (tipo: suma/resta/utilidad).';

commit;

-- 6. Sobre la constraint unique (cliente_id, nombre_parametro, vigente_desde):
-- se deja TAL CUAL, sin agregar tipo. No es un olvido, es la recomendación:
--
-- nombre_parametro es la IDENTIDAD del concepto (la etiqueta que el usuario
-- le puso), y tipo es una clasificación de esa identidad, no un eje
-- independiente. La lectura de "vigente" (tanto la de descuento/utilidad en
-- app/db.py como cualquier lectura nueva que se agregue para conceptos
-- abiertos) va a filtrar por cliente_id + nombre_parametro y tomar la fila
-- con vigente_desde más reciente. Si tipo entrara en la unique constraint,
-- se podrían cargar dos filas con el mismo cliente_id + nombre_parametro +
-- vigente_desde pero tipo distinto (ej. "flete" como 'resta' un día y como
-- 'suma' el mismo día) — ambas pasarían la constraint, pero esa lectura
-- "vigente" quedaría ambigua: no hay forma de saber cuál de las dos es la
-- válida para esa fecha. Mantener la constraint como está fuerza a que cada
-- concepto (nombre_parametro) tenga un único valor por fecha de vigencia,
-- que es exactamente la garantía que necesita el patrón "vigente" para
-- seguir funcionando sin ambigüedad.
--
-- Si en algún momento un mismo concepto necesitara cambiar de tipo con el
-- tiempo (ej. "flete" pasa de 'resta' a 'suma' a partir de una fecha), esa
-- necesidad ya la cubre vigente_desde: se carga una fila nueva con el tipo
-- nuevo, igual que cambia el valor. No hace falta tocar la constraint para eso.

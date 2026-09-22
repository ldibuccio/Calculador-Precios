do $$
begin
  if not exists (select 1 from pg_class c join pg_namespace n on n.oid = c.relnamespace
                 where c.relname = 'cargas_compra' and n.nspname = 'public') then
    create table cargas_compra (
        id                   bigint generated always as identity primary key,
        cliente_id           bigint not null references clientes (id),
        fecha                date not null,
        modo                 text not null,
        promedio_anterior_a  date not null,
        creado_en            timestamptz not null default now(),
        actualizado_en       timestamptz not null default now(),
        unique (cliente_id, fecha)
    );
  end if;
end $$;

alter table cargas_compra drop constraint if exists cargas_compra_modo_check;
alter table cargas_compra add constraint cargas_compra_modo_check
    check (modo in ('automatico', 'manual'));

comment on table cargas_compra is 'Lo que hay que comprar para UN cliente para UNA fecha (Paso 1). Vive sola y no cuelga de ningun listado: el Paso 2 arma un listado eligiendo varias cargas, y puede tomar dos fechas de un cliente y una de otro. El unique (cliente_id, fecha) impide que entrar de nuevo a Dia para el mismo dia sume doble: si ya existe, se edita o se borra y se empieza de cero.';
comment on column cargas_compra.fecha is 'LA FECHA DE COMPRA que eligio el comprador, NO el dia en que cargo. Se trabaja de noche y el dia del reloj no sirve: a las 23 se carga para manana y se elige manana.';
comment on column cargas_compra.promedio_anterior_a is 'EL ANCLA DEL PROMEDIO, y el nombre dice el operador: se miran los pedidos con fecha_operacion < este valor, nunca <=. Es el dia en que se CARGO y no la fecha de compra (dueno, 22/09): si cargo hoy para el 27, mira los 6 anteriores a hoy. Se guarda en vez de sacarlo de now() porque el listado se arma dias despues: ahi "el dia en que cargo" seria otro y la ventana se correria sola. Editar la carga NO lo mueve; borrarla y empezar de cero SI, porque es una carga nueva.';
comment on column cargas_compra.modo is 'automatico = sale del promedio de los ultimos 6 pedidos vigentes anteriores a promedio_anterior_a. manual = sale de cargas_compra_renglones. SUBIR UN ARCHIVO NO ES UN TERCER MODO: se lee, se revisa, y queda como renglones manuales; el archivo no se guarda (dueno, 22/09) porque lo que vale es lo revisado. Un tercer valor obligaria a escribir modo in (manual, archivo) en cada lector, y el que se lo olvide no falla: muestra la carga vacia.';

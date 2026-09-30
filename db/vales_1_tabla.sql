do $$
begin
  if to_regclass('vales_a_cobrar') is not null then
    raise exception 'vales_a_cobrar ya existe: este bloque ya corrio';
  end if;
  create table vales_a_cobrar (
    id bigint generated always as identity primary key,
    origen text not null check (origen in ('devolucion', 'anterior_al_sistema')),
    devolucion_id bigint unique references vacios_deposito_devoluciones (id),
    proveedor_id bigint references proveedores (id),
    fecha date,
    importe numeric(14, 2),
    importe_calculado numeric(14, 2),
    numero text,
    foto_ruta text,
    creado_en timestamptz not null default now(),
    constraint vales_origen_coherente check (
      (origen = 'devolucion' and devolucion_id is not null
        and proveedor_id is null and fecha is null
        and importe is null and foto_ruta is null)
      or (origen = 'anterior_al_sistema' and devolucion_id is null
        and proveedor_id is not null and fecha is not null
        and coalesce(importe > 0, false) and importe_calculado is null)),
    constraint vales_numero_no_vacio check (numero is null or btrim(numero) <> '')
  );
  create index vales_a_cobrar_proveedor on vales_a_cobrar (proveedor_id);
  comment on table vales_a_cobrar is
    'Vales en cartera: plata de envase que el proveedor nos debe. Nace de una '
    'devolucion de vacios con importe, o se carga por SQL (anterior al sistema).';
end $$;

-- VALES A COBRAR (duenio, 30/09), bloque 1 de 4: la cartera.
--
-- Un vale nace de DOS maneras, y el CHECK `vales_origen_coherente` no deja
-- mezclarlas:
--   devolucion           -> apunta a la devolucion de vacios. Proveedor,
--                           fecha, importe y foto se LEEN de ella (no se
--                           copian). Los comments de columna van en
--                           db/esquema_completo.sql.
--   anterior_al_sistema  -> vales en papel de antes del sistema, cargados por
--                           SQL (vales_papel_1 a 4). Traen su propio
--                           proveedor, fecha e importe; numero y foto opcionales.
--
-- NO SE CARGA NINGUNA FILA: las devoluciones del 25/09 son pruebas y no
-- entran a la cartera (duenio, 30/09).
--
-- Si la tabla ya existe el bloque aborta sin tocar nada.
-- Orden: vales_1 a vales_4, cada uno SOLO. Verificacion aparte:
-- vales_5_verificacion.sql.

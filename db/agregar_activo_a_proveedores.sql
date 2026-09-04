-- ============================================================================
-- ABM de proveedores de COMPRAS: la baja lógica.
--
-- Un proveedor de compras nace solo, al cargar una compra con un código de
-- puesto nuevo (obtener_o_crear_proveedor_por_codigo). Hasta hoy no había
-- ninguna forma de sacar uno de la lista, y eso duele por una razón puntual:
--
--   LA IDENTIDAD ES codigo_puesto, NO EL NOMBRE (unique en la base).
--
-- El nombre ya se corregía solo — cargar otra compra con el mismo código lo
-- pisa, "la última corrección manda". Pero un CÓDIGO mal tipeado crea un
-- proveedor fantasma que NO se puede arreglar renombrando, porque renombrarlo
-- no lo convierte en el que se quiso cargar. La baja lógica es su única salida.
--
-- La baja no borra ni bloquea nada: la FK a compras queda intacta, las compras
-- viejas siguen mostrando el nombre y se siguen pudiendo buscar por él. Lo
-- único que cambia es que deja de aparecer para ELEGIR al cargar una compra.
--
-- El filtro vive en UN solo lugar del código (listar_proveedores en app/db.py).
-- Los diez llamadores no repiten el WHERE: eligen entre esa función y
-- listar_todos_los_proveedores según pidan una lista para elegir o para
-- filtrar una búsqueda.
--
-- Un bloque solo, con su propia guarda adentro: si ya está aplicada, aborta
-- entera y no escribe nada. 1.098 caracteres, bien abajo del límite de 2500.
--
-- APLICADA: 04/09/2026 en Frutamax y en Palmala. NO REUSAR ESTE ARCHIVO.
-- ============================================================================

do $$
begin
    if exists (
        select 1 from information_schema.columns
        where table_schema = 'public'
          and table_name = 'proveedores'
          and column_name = 'activo'
    ) then
        raise exception 'proveedores.activo ya existe: este bloque no se corre de nuevo.';
    end if;

    alter table proveedores add column activo boolean not null default true;

    comment on column proveedores.activo is
        'false = dado de baja: deja de aparecer en el selector de carga de compras, y nada mas. Sus compras siguen intactas y siguen mostrando su nombre (la FK no se toca). Existe porque la identidad de un proveedor de compras es codigo_puesto, no el nombre: un codigo mal tipeado crea un proveedor fantasma que NO se puede arreglar renombrando, y la baja logica es su unica salida. El filtro vive en UN solo lugar (listar_proveedores en app/db.py), no en cada llamador.';
end $$;

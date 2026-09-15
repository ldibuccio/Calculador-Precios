-- LA ÚNICA COLUMNA QUE FALTA PARA EL MODELO NUEVO.
--
-- Las dos magnitudes YA tienen dónde guardarse: cantidad_kilos y
-- cantidad_fraccion (con sus gemelas _real), y el CHECK de compras es un OR,
-- así que la base ya acepta las dos llenas. Lo que no está es QUÉ ES la
-- segunda: cantidad_fraccion mete unidad y cubeta en la misma columna.
--
-- COLUMNA NUEVA Y unidad_compra SE DEPRECA: cambiarle el significado a un
-- campo con ocho escritores deja código viejo leyendo una cosa y código
-- nuevo escribiendo otra BAJO EL MISMO NOMBRE, y ahí no hay grep que lo
-- encuentre. NULO = no tiene conteo, se compra solo por kilo.
do $$
begin
    if not exists (
        select 1 from information_schema.columns
        where table_name = 'articulos' and column_name = 'unidad_conteo'
    ) then
        alter table articulos add column unidad_conteo text;
        alter table articulos add constraint articulos_unidad_conteo_check
            check (unidad_conteo is null or unidad_conteo in ('unidad', 'cubeta'));
    end if;
end $$;

-- EL BACKFILL, y es lo ÚNICO deducible de todo esto: no inventa un número,
-- COPIA una declaración que ya existe. Un artículo con unidad_compra
-- 'unidad' o 'cubeta' ya dijo cuál es su conteo — es literalmente el mismo
-- dato con otro nombre.
--
-- Va AFUERA del if not exists a propósito: es CONTENIDO, así que una segunda
-- corrida tiene que poder completar un artículo nuevo. Adentro se saltearía
-- y eso se ve igual que haber corrido.
--
-- Lo que NO toca: los que se compran por kilo. Ahí el conteo no se puede
-- deducir de la compra, y deducirlo de las fichas sería suponer. Quedan en
-- null y la verificación los NOMBRA.
update articulos
   set unidad_conteo = unidad_compra, actualizado_en = now()
 where unidad_conteo is null
   and unidad_compra in ('unidad', 'cubeta');

comment on column articulos.unidad_conteo is
    'Que es la SEGUNDA magnitud de este articulo, la que acompana a los kilos en cada compra: unidad o cubeta. NULO = no tiene conteo, se compra solo por kilo. Reemplaza a unidad_compra para esto: los kilos van SIEMPRE, asi que unidad_compra dejo de decir en que viene la compra.';

comment on column articulos.unidad_compra is
    'DEPRECADA desde el 15/09 (modelo de dos magnitudes). Decia en que unidad venia expresada la compra, cuando era una sola. Ahora los kilos van siempre y la segunda magnitud la dice unidad_conteo. NO escribir logica nueva contra esta columna.';

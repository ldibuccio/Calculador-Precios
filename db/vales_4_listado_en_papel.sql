do $$
begin
  if to_regclass('vales_papel_listado') is not null then
    raise exception 'vales_papel_listado ya existe: este bloque ya corrio';
  end if;
  create table vales_papel_listado (
    fila integer primary key,
    codigo text, fecha text, importe numeric, numero text, foto text
  );
  create view vales_papel_revision as
  select l.fila, upper(btrim(l.codigo)) as codigo, pr.nombre as proveedor,
         btrim(l.fecha) as fecha, l.importe, nullif(btrim(l.numero), '') as numero,
         nullif(btrim(l.foto), '') as foto, pr.id as proveedor_id,
         case
      when upper(btrim(l.codigo)) !~ '^[A-Z][0-9]{2}P[0-9]{2}$' then 'el codigo no es de un puesto'
      when pr.id is null then 'no hay proveedor con ese codigo'
      when btrim(l.fecha) !~ '^[0-9]{2}/[0-9]{2}/[0-9]{4}$' then 'la fecha no es DD/MM/AAAA'
      when not pg_input_is_valid(right(btrim(l.fecha), 4) || '-' || substr(btrim(l.fecha), 4, 2)
        || '-' || left(btrim(l.fecha), 2), 'date') then 'esa fecha no existe'
      when to_date(l.fecha, 'DD/MM/YYYY') > current_date then 'la fecha es futura'
      when not coalesce(l.importe > 0, false) then 'el importe no es mayor que cero'
      when l.foto is not null and btrim(l.foto) !~ '^[^ ]+[.](jpg|jpeg|png)$' then 'la foto no es una ruta'
      when count(*) over (partition by pr.id, btrim(l.fecha), l.importe,
                          nullif(btrim(l.numero), '')) > 1 then 'repetida en el listado'
      when exists (select 1 from vales_a_cobrar v where v.origen = 'anterior_al_sistema'
                     and v.proveedor_id = pr.id and v.fecha = to_date(l.fecha, 'DD/MM/YYYY')
                     and v.importe = l.importe
                     and v.numero is not distinct from nullif(btrim(l.numero), ''))
        then 'ya estaba cargado'
    end as problema
    from vales_papel_listado l
    left join lateral (
      select p.id, p.nombre from proveedores p
       where p.codigo_puesto = upper(btrim(l.codigo))
          or exists (select 1 from proveedores_codigos pc where pc.proveedor_id = p.id
                       and pc.codigo = upper(btrim(l.codigo)))
       limit 1) pr on true;
end $$;

-- VALES A COBRAR (duenio, 30/09), bloque 4: el listado de vales en papel.
-- La tabla es donde se PEGA (vales_papel_1); la vista dice, fila por fila, a
-- que proveedor va y que tiene mal: la regla vive UNA vez, ahi. Todo en
-- texto: una fecha mal escrita entra y se ve. Solo; verificacion: vales_5.

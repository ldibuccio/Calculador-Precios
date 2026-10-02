do $$
begin
  if to_regclass('vales_a_cobrar') is null then
    raise exception 'falta vales_a_cobrar: corre primero vales_1';
  end if;
  alter table vales_a_cobrar add column if not exists cargado_desde text;
  alter table vales_a_cobrar add column if not exists nota text;
  alter table vales_a_cobrar drop constraint if exists vales_a_cobrar_origen_check;
  alter table vales_a_cobrar add constraint vales_a_cobrar_origen_check
    check (origen in ('devolucion', 'anterior_al_sistema', 'carga_manual'));
  alter table vales_a_cobrar drop constraint if exists vales_origen_coherente;
  alter table vales_a_cobrar add constraint vales_origen_coherente check (
    (origen = 'devolucion' and devolucion_id is not null
      and proveedor_id is null and fecha is null
      and importe is null and foto_ruta is null)
    or (origen in ('anterior_al_sistema', 'carga_manual') and devolucion_id is null
      and proveedor_id is not null and fecha is not null
      and coalesce(importe > 0, false) and importe_calculado is null));
  alter table vales_a_cobrar drop constraint if exists vales_carga_manual_con_sector;
  alter table vales_a_cobrar add constraint vales_carga_manual_con_sector check (
    (origen = 'carga_manual') = (cargado_desde is not null)
    and (cargado_desde is null or cargado_desde in ('administracion', 'gerencia')));
  alter table vales_a_cobrar drop constraint if exists vales_nota_no_vacia;
  alter table vales_a_cobrar add constraint vales_nota_no_vacia
    check (nota is null or btrim(nota) <> '');
end $$;

-- VALES, CARGA MANUAL (duenio, 02/10), bloque 1 de 3: el origen nuevo.
--
-- 'carga_manual' es un vale en papel dado de alta desde la pantalla de Vales
-- (Gerencia o Administracion), sin devolucion ni movimiento de cajones. Tiene
-- la misma forma que 'anterior_al_sistema' (proveedor, fecha, importe propios)
-- y ademas dice QUIEN lo cargo (cargado_desde, el sector) y una nota opcional.
-- 'anterior_al_sistema' queda para los que se cargaron por SQL.
--
-- Los CHECK son CONTENIDO: se dropean y se recrean siempre, asi correrlo dos
-- veces deja lo ultimo que se mando. Las columnas son estructura (if not
-- exists). Ninguna fila vieja cambia: todas son devolucion o anterior.
--
-- Se corre SOLO, en las dos bases. Verificacion: vales_manual_4.

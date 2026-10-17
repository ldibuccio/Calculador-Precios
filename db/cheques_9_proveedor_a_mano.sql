-- CHEQUES (dueño, 16/10), migración cheques_3, bloque 1. En Frutamax Y en Palmala.
-- El cheque que se le da a alguien que no está en proveedores (la lista del Mercado
-- Central): su nombre, escrito a mano, en la salida. Uno u otro, nunca los dos.
do $$
begin
  alter table cheques_salidas add column if not exists proveedor_a_mano text;
  alter table cheques_salidas drop constraint if exists cheques_salidas_proveedor_a_mano_no_vacio;
  alter table cheques_salidas add constraint cheques_salidas_proveedor_a_mano_no_vacio
    check (proveedor_a_mano is null or btrim(proveedor_a_mano) <> '');
  alter table cheques_salidas drop constraint if exists cheques_salidas_un_proveedor;
  alter table cheques_salidas add constraint cheques_salidas_un_proveedor
    check (proveedor_id is null or proveedor_a_mano is null);
end $$;

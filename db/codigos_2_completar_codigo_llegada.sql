do $$
begin
  update compras c set codigo_llegada = p.codigo_puesto
    from proveedores p
   where p.id = c.proveedor_id and c.codigo_llegada is null;
end $$;

-- Bloque 2 de 4. Cada compra que ya existe llegó por el código principal de
-- su proveedor, porque hasta hoy no había otro. Va ANTES de la fusión, así las
-- 26 del proveedor FRUTAMAX quedan con N09P39 y las de FRUTAMAX S.R.L. con
-- N09P41. Solo llena NULL: correrlo dos veces no cambia nada.

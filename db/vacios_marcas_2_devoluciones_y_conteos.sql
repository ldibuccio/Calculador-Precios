do $$
begin
  alter table vacios_deposito_devoluciones alter column compra_id drop not null;
  alter table vacios_deposito_devoluciones add column if not exists marca_vacio_id bigint;
  alter table vacios_deposito_devoluciones drop constraint if exists vacios_dev_marca_del_proveedor;
  alter table vacios_deposito_devoluciones add constraint vacios_dev_marca_del_proveedor
    foreign key (marca_vacio_id, proveedor_id) references marcas_vacio (id, proveedor_id);

  alter table conteos_vacios_deposito add column if not exists marca_vacio_id bigint;
  alter table conteos_vacios_deposito drop constraint if exists vacios_conteo_marca_del_proveedor;
  alter table conteos_vacios_deposito add constraint vacios_conteo_marca_del_proveedor
    foreign key (marca_vacio_id, proveedor_id) references marcas_vacio (id, proveedor_id);

  comment on column vacios_deposito_devoluciones.compra_id is 'Contra qué compra se aplicó el vale. Desde el 25/09 NO se pide: la devolución sale de una PILA (proveedor y marca). Queda para las viejas.';
  comment on column vacios_deposito_devoluciones.marca_vacio_id is 'De qué pila salió la devolución. NULL = de los cajones sin asignar.';
end $$;

-- DEVOLVER SIN COMPRA (dueño, 25/09): la devolución ya no se asigna a una
-- compra, sale de una pila —proveedor y marca, o "sin asignar"—. Y el CONTEO
-- físico gana la marca: el depósito cuenta por proveedor y marca.
--
-- SOLO AGREGA, y se corre YA: una columna NULL y un NOT NULL que se afloja
-- no le cambian nada al código que está en producción. La FOTO OBLIGATORIA
-- NO va acá: frenaría desde hoy las devoluciones que el código de hoy todavía
-- deja cargar sin foto. Va en el bloque 5, después del deploy.
-- Corre DESPUÉS del bloque 1 (necesita marcas_vacio). Verificación aparte.

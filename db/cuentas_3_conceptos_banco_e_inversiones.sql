-- CUENTAS (dueño, 15/10), migración cuentas_1, bloque 3. En Frutamax Y en Palmala (en Palmala, sin cuentas sembradas: se crean desde Gerencia → Cuentas).
insert into cuentas_conceptos (cuenta_id, nombre, tipo)
select c.id, v.nombre, v.tipo
from (values   ('Banco Credicoop', 1, 'Saldo inicial', null),
  ('Banco Credicoop', 2, 'Transferencia recibida', 'ingreso'),
  ('Banco Credicoop', 3, 'Transferencia enviada', 'egreso'),
  ('Banco Credicoop', 4, 'Pago a proveedor', 'egreso'),
  ('Banco Credicoop', 5, 'Impuestos y comisiones', 'egreso'),
  ('Banco Credicoop', 6, 'Otros ingresos', 'ingreso'), ('Banco Credicoop', 7, 'Otros egresos', 'egreso'),
  ('Banco Credicoop', 8, 'Ajuste', null),
  ('Inversiones Credicoop', 1, 'Saldo inicial', null),
  ('Inversiones Credicoop', 2, 'Rendimiento', null),
  ('Inversiones Credicoop', 3, 'Movimiento anterior', null), ('Inversiones Credicoop', 4, 'Ajuste', null)
  ) as v (cuenta, orden, nombre, tipo)
join cuentas c on c.nombre = v.cuenta
where not exists (select 1 from cuentas_conceptos x
                  where x.cuenta_id = c.id and upper(btrim(x.nombre)) = upper(v.nombre))
order by c.id, v.orden;
-- Solo para el histórico: desde ahora van como depósito o extracción.
update cuentas_conceptos set activo = false
 where nombre in ('Cruce banco', 'Cruce banco (ingreso)', 'Movimiento anterior');

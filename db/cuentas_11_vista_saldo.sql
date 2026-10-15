-- CUENTAS (dueño, 15/10), migración cuentas_1, bloque 11. En Frutamax Y en Palmala (en Palmala, sin cuentas sembradas: se crean desde Gerencia → Cuentas).
create or replace view cuentas_con_saldo with (security_invoker = true) as
select v.*,
       case when v.anulado then 0 when v.tipo = 'ingreso' then v.importe else -v.importe end
         as con_signo,
       sum(case when v.anulado then 0 when v.tipo = 'ingreso' then v.importe else -v.importe end)
         over (partition by v.cuenta_id order by v.fecha, v.creado_en, v.origen, v.origen_id) as saldo,
       cc.renglon_id is not null as conciliado, cc.a_revisar
from cuentas_todos_los_movimientos v
left join cuentas_conciliaciones cc
  on cc.cuenta_id = v.cuenta_id and cc.origen = v.origen and cc.origen_id = v.origen_id;

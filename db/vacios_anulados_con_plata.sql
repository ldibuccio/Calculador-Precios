-- ############################################################################
-- RECEPCIONES DE VACÍOS ANULADAS QUE YA TENÍAN PLATA COMPROMETIDA.
-- Solo lectura, no escribe nada.
--
-- `cerrar_sena` no deja pagar una recepción anulada, pero `anular_vacio_recibido`
-- SÍ deja anular una recepción ya pagada: la guarda está en un solo sentido. Al
-- anularse, la fila desaparece de Pendientes de Pago Y del historial de señas
-- cerradas (las dos consultas filtran anulado_el IS NULL), así que la plata que
-- salió deja de figurar en el módulo de Señas.
--
-- 'anulada' NO entra: esa es la seña que se decidió no pagar, no hay plata que
-- perseguir.
--
-- El monto sale del MISMO lateral que usa la app (VALOR_SENA_VIGENTE): el valor
-- vigente a la fecha de la RECEPCIÓN, no el de hoy.
-- ############################################################################
select v.id,
       v.creado_en::date       recibido_el,
       c.nombre                trajo,
       p.nombre                proveedor,
       t.nombre                tipo_envase,
       v.cantidad,
       case when v.sena_pagada_el is not null then 'PAGADA' else 'VALE' end cierre,
       coalesce(v.sena_pagada_el, v.sena_vale_el)::date cerrada_el,
       v.anulado_el::date      anulada_el,
       valor.monto             sena_por_cajon,
       valor.monto * v.cantidad plata_involucrada,
       -- Si la anulación llegó DESPUÉS del cierre, el orden es el del caso
       -- reportado. Al revés no puede pasar (cerrar_sena lo impide), así que
       -- un 'false' acá sería una fila escrita a mano y hay que mirarla.
       v.anulado_el >= coalesce(v.sena_pagada_el, v.sena_vale_el) anulo_despues_de_cobrar
from vacios_recibidos v
join clientes_puesto c on c.id = v.cliente_puesto_id
join proveedores_puesto p on p.id = v.proveedor_id
join tipos_envase_puesto t on t.id = v.tipo_envase_id
left join lateral (
    select h.monto from senas_valor_historial h
    where h.tipo_envase_id = v.tipo_envase_id
      and h.vigente_desde <= v.creado_en::date
    order by h.vigente_desde desc, h.creado_en desc limit 1
) valor on true
where v.anulado_el is not null
  and (v.sena_pagada_el is not null or v.sena_vale_el is not null)
order by v.anulado_el desc;

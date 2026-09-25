do $$
begin
  alter table movimientos_envase drop constraint if exists movimientos_envase_origen_check;
  alter table movimientos_envase add constraint movimientos_envase_origen_check
    check (origen in ('conteo_inicial', 'compra', 'prestamo_al_puesto', 'ajuste',
                      'colega_le_presto', 'colega_me_devuelve',
                      'colega_me_presta', 'colega_le_devuelvo', 'merma'));

  alter table movimientos_envase drop constraint if exists movimientos_envase_signo_segun_origen;
  alter table movimientos_envase add constraint movimientos_envase_signo_segun_origen
    check (case
             when origen = 'conteo_inicial' then cantidad >= 0
             when origen in ('compra', 'colega_me_devuelve', 'colega_me_presta')
               then cantidad > 0
             when origen in ('prestamo_al_puesto', 'colega_le_presto',
                             'colega_le_devuelvo', 'merma')
               then cantidad < 0
             else cantidad <> 0
           end);

  comment on column movimientos_envase.origen is 'conteo_inicial, compra, prestamo_al_puesto, ajuste, merma (cajas ROTAS: siempre negativa, es perdida y va a la cuenta de cajas rotas) y los cuatro de la cuenta con un colega.';
end $$;

-- CAJAS ROTAS (dueño, 25/09): las cajas que vienen rotas se dan de baja como
-- MERMA de cajas, un origen más de movimientos_envase.
--
-- CORRE EN UN SOLO `do`: los dos CHECK se reemplazan juntos o ninguno. Si el
-- de origen entrara y el de signo no, una merma cae en el `else cantidad <> 0`
-- y se podría cargar SUMANDO cajas.
--
-- DROP Y RECREAR, NUNCA `if not exists`: los dos CHECK son CONTENIDO (una
-- lista de valores y un mapa de signos). Un `if not exists` saltearía el
-- bloque con la lista vieja adentro y saldría `DO` igual.
--
-- La plata NO se guarda en una columna: se valúa en cada lectura al costo de
-- envases_costo_historial vigente a la fecha de la merma, igual que la compra
-- de cajas. La verificación va APARTE, en cajas_rotas_2_verificacion.sql.

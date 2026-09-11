-- BLOQUE C de 4: que puede declarar cada tipo de guia.
-- Ver compra_en_caja_nuestra_2a_columna_y_candado.sql para el por que.
--
-- CONTENIDO otra vez: drop y recrear.
--
-- "Uno a uno" vive ACA y no en la ruta: lo que entro es lo que hay, y la
-- pantalla no lo pregunta porque no hay nada que preguntar. Una guarda en la
-- ruta seria la regla escrita dos veces; esta va donde se ESCRIBE.
--
-- Segunda y merma en cero: el reenvasado no paso en el galpon, asi que no hay
-- descarte de reproceso que declarar. Si se pudre algo despues, es merma de
-- galpon y se carga por su propia pantalla, que baja el stock.
--
-- La ficha es OBLIGATORIA, igual que en 'inicial' y al reves del reproceso
-- normal: una caja que llego armada ya es de alguien.
do $$
begin
  if to_regclass('public.reprocesos') is null then
    raise exception 'no existe la tabla reprocesos: base equivocada';
  end if;

  alter table reprocesos drop constraint if exists reprocesos_bultos_tomados_check;
  alter table reprocesos add constraint reprocesos_bultos_tomados_check
    check (
      (tipo = 'inicial' and bultos_tomados = 0)
      or (tipo = 'normal' and bultos_tomados > 0)
      or (tipo = 'en_origen' and bultos_tomados > 0
          and bultos_primera = bultos_tomados
          and bultos_segunda = 0 and bultos_merma = 0
          and ficha_id is not null)
    );
end $$;

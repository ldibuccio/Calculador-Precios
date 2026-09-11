-- BLOQUE B de 4: `tipo` acepta el tercer valor.
-- Ver compra_en_caja_nuestra_2a_columna_y_candado.sql para el por que.
--
-- CONTENIDO —una lista de literales—, asi que DROP Y RECREAR, nunca
-- `if not exists`. Si el check ya existiera con otra lista, el idempotente
-- saldria `DO` sin hacer nada y en la pantalla se veria EXACTAMENTE IGUAL que
-- si hubiera corrido bien. Paso el 09/09 con los motivos de la merma de
-- segunda y por eso esta escrito en CLAUDE.md.
--
-- El nombre `reprocesos_tipo_check` no es una suposicion: sale de cargar
-- db/esquema_completo.sql en Postgres 16 y leer pg_constraint. El check
-- original esta escrito inline en la columna, asi que el nombre lo puso
-- Postgres, no nosotros.
do $$
begin
  if to_regclass('public.reprocesos') is null then
    raise exception 'no existe la tabla reprocesos: base equivocada';
  end if;

  alter table reprocesos drop constraint if exists reprocesos_tipo_check;
  alter table reprocesos add constraint reprocesos_tipo_check
    check (tipo in ('normal', 'inicial', 'en_origen'));
end $$;

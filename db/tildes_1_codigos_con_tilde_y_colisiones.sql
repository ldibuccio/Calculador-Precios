-- ¿Se puede plegar tildes en fichas_logistica_codigo_cliente_unico, y hay
-- que limpiar algo ANTES de crear el indice?
-- El indice de hoy pliega lower(trim(...)) y NO pliega tildes.
-- normalizar_texto (core/matcheo_comanda.py), que es quien matchea el codigo
-- del pedido contra la ficha, SI las pliega -- y ademas pliega la EÑE
-- (NFD + descarte de Mn deja ñ -> n) y colapsa espacios internos.
-- Asi que hoy CÓD-2 y COD-2 entran los dos, y el matcheo los ve iguales:
-- el sistema elige una ficha en silencio. Es "ruben" al lado de "Rubén".
-- Todo en SQL puro (translate/lower/regexp_replace): nada de unaccent, que
-- se habilita por proyecto y no viajaria a la base de la tercera empresa.
-- Devuelve CONTEOS y no una lista: con lista, "no hay ninguno" y "no corrio"
-- son la misma pantalla vacia.
with f as (
  select id, cliente_id, trim(codigo_cliente) c
  from fichas_logistica
  where codigo_cliente is not null and trim(codigo_cliente) <> ''
),
n as (
  select id, cliente_id, c, lower(c) vieja,
    lower(regexp_replace(translate(c,
      'ÁÀÄÂÃÉÈËÊÍÌÏÎÓÒÖÔÕÚÙÜÛÑÇáàäâãéèëêíìïîóòöôõúùüûñç',
      'AAAAAEEEEIIIIOOOOOUUUUNCaaaaaeeeeiiiiooooouuuunc'),
      '\s+', ' ', 'g')) nueva
  from f
),
col as (
  select count(*) fichas, count(distinct vieja) viejas
  from n group by cliente_id, nueva having count(*) > 1
)
select
  (select count(*) from n) fichas_con_codigo,
  (select count(*) from n where c <> translate(c,
    'ÁÀÄÂÃÉÈËÊÍÌÏÎÓÒÖÔÕÚÙÜÛÑÇáàäâãéèëêíìïîóòöôõúùüûñç',
    'AAAAAEEEEIIIIOOOOOUUUUNCaaaaaeeeeiiiiooooouuuunc')) con_tilde,
  (select count(*) from n where c <> translate(c,'ñÑ','nN')) con_enie,
  (select count(*) from n where c ~ '\s\s') con_espacio_doble,
  (select count(*) from col where viejas > 1) colisiones_nuevas,
  (select coalesce(sum(fichas),0) from col where viejas > 1) fichas_en_colision,
  (select count(*) from col where viejas = 1) dup_regla_vieja;

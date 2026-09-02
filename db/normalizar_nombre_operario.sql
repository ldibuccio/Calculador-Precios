-- ARREGLO: el nombre único del operario tenía que plegar los ACENTOS y los
-- ESPACIOS DE ADENTRO.
--
-- El índice quedó como lower(btrim(nombre)), que pliega mayúsculas y espacios
-- pero NO tildes. Encontrado con la pantalla andando: se cargó "ruben" al lado
-- de "Rubén" y entraron los dos. Ni el índice ni el chequeo del código lo
-- atajaron — los dos usaban la misma regla incompleta.
--
-- Y es el caso MÁS común en castellano, no un borde: la mitad de los nombres
-- del depósito llevan tilde y nadie la escribe siempre.
--
-- LOS ESPACIOS DE ADENTRO son el mismo problema con otra cara, y salió
-- probando este arreglo: `btrim` saca los espacios de las PUNTAS pero no
-- colapsa los del medio, así que "Rubén  Pérez" con dos espacios entraba al
-- lado de "Rubén Pérez". Colapsarlos estaba escrito SOLO en Python — otra vez
-- la misma regla en dos lugares, que es de lo que se trata la regla de
-- CLAUDE.md. Ahora el índice lo hace por su cuenta y el código solo prolija lo
-- que guarda.
--
-- `translate` y no la extensión `unaccent` a propósito: unaccent hay que
-- habilitarla en el proyecto, y una regla de unicidad que depende de una
-- extensión instalada es una regla que se puede perder al crear la empresa
-- siguiente. Esto es SQL puro y viaja con el esquema.
--
-- La ñ también se pliega. Es deliberado: en una lista de nombres de pila de
-- una sola empresa, "Muñoz" y "munoz" son la misma persona, y el costo de
-- equivocarse es un mensaje que NOMBRA al que ya está — recuperable — contra
-- el costo de no plegarla, que es un duplicado silencioso.
--
-- SI YA HUBIERA DUPLICADOS que solo se distinguen por tildes, el bloque se
-- corta y los lista: unificarlos es decisión de una persona.

do $$
declare
    duplicados text;
begin
    select string_agg(nombres, '; ') into duplicados from (
        select string_agg(nombre, ' / ') as nombres
        from operarios_deposito
        group by lower(translate(regexp_replace(btrim(nombre), '\s+', ' ', 'g'), 'áéíóúüñÁÉÍÓÚÜÑ', 'aeiouunAEIOUUN'))
        having count(*) > 1
    ) d;
    if duplicados is not null then
        raise exception
            'Hay operarios que solo se distinguen por tildes y quedarían duplicados: %. Unificalos a mano antes de correr esto.',
            duplicados;
    end if;

    if exists (select 1 from pg_class where relname = 'operarios_deposito_nombre_unico') then
        drop index operarios_deposito_nombre_unico;
    end if;
    create unique index operarios_deposito_nombre_unico
        on operarios_deposito (lower(translate(regexp_replace(btrim(nombre), '\s+', ' ', 'g'), 'áéíóúüñÁÉÍÓÚÜÑ', 'aeiouunAEIOUUN')));

    comment on column operarios_deposito.activo is
        'false = ya no aparece en el selector, pero sus excepciones viejas siguen contando. El nombre es único PLEGANDO mayúsculas, TILDES y todos los espacios de más (los de las puntas y los del medio): "Rubén Pérez", "ruben perez" y "  RUBEN   PEREZ " son la misma persona.';
end $$;

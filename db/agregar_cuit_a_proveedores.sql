-- CUIT del proveedor, para cuando facturación lo necesite.
--
-- SIN UNIQUE, y es una decisión, no un olvido: un mismo CUIT puede tener
-- VARIOS puestos. La identidad es el puesto, no la firma — igual que el
-- nombre, dos puestos del mismo dueño son dos proveedores de verdad. Un
-- índice único bloquearía un caso real.
--
-- NORMALIZADO A 11 DÍGITOS, sin guiones: guardar "30-71234567-8" y
-- "30712345678" sería el mismo CUIT escrito de dos formas, y esta casa ya
-- sabe cómo termina eso. El CHECK acepta NULL (hoy son 75 sin cargar) pero
-- no una cadena vacía: '' se lee igual que "no tengo" y no es lo mismo que
-- no haberlo puesto.
--
-- EL DÍGITO VERIFICADOR NO VA EN EL CHECK, a propósito: el módulo 11 en SQL
-- es una expresión larga e ilegible, y una regla que nadie puede leer no se
-- revisa. Va en el código, en UNA función, al cargar. Es la regla escrita en
-- dos fuerzas del corolario 26 — la base decide la FORMA, el código la
-- PLAUSIBILIDAD— y acá está decidido a propósito y dicho acá.
--
-- `if not exists` SOLO sobre la columna, que es estructura. El CHECK es
-- contenido y se dropea y recrea.

do $$
begin
  if not exists (
    select 1 from information_schema.columns
    where table_name = 'proveedores' and column_name = 'cuit'
  ) then
    alter table proveedores add column cuit text;
  end if;

  alter table proveedores drop constraint if exists proveedores_cuit_check;
  alter table proveedores
    add constraint proveedores_cuit_check
    check (cuit is null or cuit ~ '^[0-9]{11}$');
end $$;

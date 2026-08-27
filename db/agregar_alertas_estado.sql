-- ============================================================================
-- ALERTAS CALCULADAS Y GUARDADAS
-- ============================================================================
-- La foto del último cálculo de cada alerta. Una fila por alerta, se pisa en
-- cada corrida: NO es un historial, es el estado actual.
--
-- POR QUÉ: las alertas dejaron de vivir solo en Auditoría — cada módulo va a
-- tener su banner con las suyas, y van a ser muchas. Calculándolas en vivo, el
-- costo crece con alertas x pantallas. Guardadas, cada pantalla cuesta UNA
-- consulta, tenga 15 alertas o 100. Y no hacen falta al instante: se recalculan
-- cada 12 horas.
--
-- La base guarda SOLO lo que se calcula. El título, la URL y a qué módulos
-- pertenece cada alerta viven en el registro de app/main.py, y por eso agregar
-- una alerta nueva NO necesita tocar la base nunca más.
--
-- calculada_el es a la vez el dato que se muestra ("hace 3 h") y el latido: si
-- el cálculo automático muere, esta columna deja de avanzar y las pantallas lo
-- muestran. Por eso se escribe SIEMPRE, aunque la alerta dé cero casos — "no
-- hay problemas" y "no se calculó" no pueden verse iguales. Es la lección del
-- 25/08 con el bucle de la casilla.
--
-- ADITIVA: crea una tabla nueva y no toca ninguna existente.
-- Correr en las DOS bases (Frutamax y Palmala) y marcar en APLICADO.md.
-- ============================================================================

create table alertas_estado (
    codigo        text primary key,
    casos         integer not null check (casos >= 0),
    mas_viejo     date,
    calculada_el  timestamptz not null,
    duracion_ms   integer,
    error         text
);

comment on table alertas_estado is
    'Foto del último cálculo de cada alerta, una fila por código. Se pisa en cada corrida: no es historial. El título, la URL y los módulos NO están acá: viven en el registro de app/main.py, así agregar una alerta no toca la base.';
comment on column alertas_estado.calculada_el is
    'Cuándo se calculó esta alerta. Es el dato que la pantalla muestra ("hace 3 h") y a la vez el latido del cálculo automático: se escribe siempre, aunque casos sea 0.';
comment on column alertas_estado.error is
    'Si la consulta de esta alerta falló, el mensaje. La alerta queda con su valor viejo y su calculada_el vieja: se muestra vencida, no en cero — un problema que desaparece porque la consulta se rompió es la peor falla posible en un sistema de alertas.';

-- Verificación: tiene que devolver 6 columnas y 0 filas.
-- select count(*) as columnas from information_schema.columns where table_name = 'alertas_estado';
-- select count(*) as filas from alertas_estado;

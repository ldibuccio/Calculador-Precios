-- ============================================================================
-- FILTRO DE ASUNTO EN LA CASILLA DE PEDIDOS
-- ============================================================================
-- El asunto real del mail de Día es del tipo "Pedido Dia 22-08 Sabado":
-- lleva la fecha adentro, así que el filtro es POR CONTENIDO ("Pedido Dia"
-- matchea cualquier asunto que lo contenga), sin distinguir mayúsculas ni
-- acentos. Pasa a ser el filtro OBLIGATORIO de la casilla.
--
-- El remitente queda como filtro OPCIONAL extra: si está vacío, un pedido
-- entra aunque cambie quién lo manda (la prioridad es no perder ninguno).
-- La protección del buzón de 9.000 correos no cambia: SINCE (y FROM si
-- hay remitentes) siguen siendo server-side; de los candidatos del día se
-- bajan solo los ENCABEZADOS, y el cuerpo completo únicamente de los que
-- matchean el asunto.
--
-- ADITIVO PURO sobre casillas_pedidos (columna nueva + un NOT NULL que se
-- afloja). Correr en las DOS bases (Frutamax y Palmala) y marcar en
-- APLICADO.md.
-- ============================================================================

alter table casillas_pedidos add column asunto_filtro text;

comment on column casillas_pedidos.asunto_filtro is
    'Filtro de asunto por contenido (ej. "Pedido Dia"): matchea cualquier asunto que lo contenga, sin mayúsculas ni acentos. Obligatorio para revisar; la pantalla lo exige al guardar.';

alter table casillas_pedidos alter column remitentes_permitidos drop not null;

comment on column casillas_pedidos.remitentes_permitidos is
    'Filtro OPCIONAL de remitentes (separados por coma). Vacío = cualquier remitente: un pedido no se pierde porque cambió quién lo manda. Si está, además achica la búsqueda server-side con FROM.';

-- Verificación: la columna nueva existe y remitentes ya no es obligatorio.
-- select column_name, is_nullable from information_schema.columns
-- where table_name = 'casillas_pedidos'
--   and column_name in ('asunto_filtro', 'remitentes_permitidos');

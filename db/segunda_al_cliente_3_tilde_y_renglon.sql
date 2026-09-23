do $$
begin
  alter table clientes
    add column if not exists acepta_segunda boolean not null default false;
  alter table pedidos_renglones
    add column if not exists bultos_de_segunda numeric;
  alter table pedidos_renglones
    drop constraint if exists pedidos_renglones_segunda_solo_armado;
  alter table pedidos_renglones
    add constraint pedidos_renglones_segunda_solo_armado
    check (bultos_de_segunda is null
           or (bultos_de_segunda > 0
               and armado_el is not null
               and anulado_el is null
               and bultos_de_segunda <= coalesce(cantidad_armada, cantidad)));
  comment on column clientes.acepta_segunda is
    'Si a este cliente se le puede mandar mercaderia de segunda como si fuera de primera (dueno, 23/09). Default NO: un catering si, Dia no. Decide si Armar Pedido ofrece la segunda, y el POST lo revisa igual.';
  comment on column pedidos_renglones.bultos_de_segunda is
    'Cuantos de los bultos ARMADOS salieron de la segunda y no de la primera (dueno, 23/09). NULL = ninguno. Salen del pool de segunda del articulo, no del stock de primera ni de las cajas de la ficha, y se venden a precio lleno con costo cero: la perdida ya se conto al pasar a segunda.';
end $$;

-- BLOQUE UNICO, se corre en las DOS bases y la verificacion va APARTE
-- (db/segunda_al_cliente_3_verificacion.sql).
--
-- El CHECK es CONTENIDO (la regla de cuando puede haber segunda), asi que va
-- con drop + add y no con un if not exists: si hubiera que corregirlo, correr
-- esto de nuevo tiene que dejar la version nueva.
--
-- Por que en la base y no solo en el codigo: la regla "solo sobre lo armado,
-- nunca en un renglon anulado, nunca mas de lo que salio" tiene que valer
-- para todo escritor, incluido el que aparezca manana. Los cinco que tocan
-- el armado (recarga, marcar, desmarcar, anular, corregir cantidad) se
-- actualizan en el mismo commit que el codigo que la usa.

-- BLOQUE 3 — los comentarios. Aparte porque los bloques largos se truncan y
-- éste no cambia ninguna estructura: si falla, no queda nada a medias.
do $$
begin
    comment on table remitos_segunda is
        'SALIDAS del pool de segunda, con dos destinos: puesto (el remito de siempre, que la manda al Puesto y deja de ser problema del deposito) y merma (se tiro). Las dos restan igual del pool y ninguna mueve plata: la segunda no lleva costo — el del reproceso viaja entero a la primera, y el de un rechazo mandado a segunda ya se imputo como perdida al entrar. El nombre quedo de cuando el remito era la unica salida.';
    comment on column remitos_segunda.destino is
        'puesto = remito al Puesto (destino fijo, sin motivo). merma = se tiro, y lleva motivo obligatorio de la lista del check remitos_segunda_motivo_de_la_lista. Las viejas quedaron en puesto por el default, que es lo que eran.';
    comment on column remitos_segunda.motivo is
        'Solo cuando destino = merma, y obligatorio ahi: lo exige el check remitos_segunda_motivo_solo_merma, que cubre las dos direcciones (merma sin motivo y remito con motivo rebotan las dos). De lista corta y no texto libre, al reves que la merma de stock normal.';
end $$;

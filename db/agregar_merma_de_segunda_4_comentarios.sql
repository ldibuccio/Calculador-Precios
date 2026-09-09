-- BLOQUE 4 — los comentarios. Aparte porque no cambian ninguna estructura:
-- si falla, no queda nada a medias.
do $$
begin
    comment on table remitos_segunda is
        'SALIDAS del pool de segunda, con dos destinos: puesto (el remito de siempre, que la manda al Puesto y deja de ser problema del deposito) y merma (se tiro). Las dos restan igual del pool y ninguna mueve plata: la segunda no lleva costo — el del reproceso viaja entero a la primera, y el de un rechazo mandado a segunda ya se imputo como perdida al entrar. El nombre quedo de cuando el remito era la unica salida.';
    comment on column remitos_segunda.destino is
        'puesto = remito al Puesto (destino fijo, sin motivo). merma = se tiro, y lleva motivo obligatorio de la lista del check remitos_segunda_motivo_de_la_lista. Las viejas quedaron en puesto por el default, que es lo que eran.';
    comment on column remitos_segunda.motivo is
        'Solo cuando destino = merma, y obligatorio ahi: lo exige el check remitos_segunda_motivo_solo_merma, que cubre las dos direcciones. De lista corta y no texto libre, al reves que la merma de stock normal.';
    comment on table fotos_merma is
        'Foto de lo que se tiro, en el bucket "comandas" con prefijo merma/. Una merma legitima y una que tapa un faltante se ven identicas como numero y no como foto. La foto NO se borra al anular la merma: es el registro de lo que se afirmo. Entra en la limpieza de 3 anios con la misma perilla que las demas (listar_fotos_para_limpiar en app/db.py).';
    comment on column fotos_merma.salida_segunda_id is
        'La merma de SEGUNDA: apunta a remitos_segunda, que desde hoy son las salidas del pool. Exactamente uno de los dos duenios va cargado — lo exige fotos_merma_un_solo_dueno.';
end $$;

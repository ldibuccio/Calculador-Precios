do $$
declare
  v_desde date;
  v_tocadas int;
begin
  select min(fecha_operacion) into v_desde
    from movimientos_envase
   where origen = 'conteo_inicial' and anulado_el is null;

  if v_desde is null then
    raise exception 'Esta base no tiene conteo inicial de cajas: no hay cuenta que corregir.';
  end if;

  update reprocesos r
     set lleva_caja_nuestra = (f.envase_id is not null),
         envase_id          = f.envase_id
    from fichas_logistica f
   where f.id = r.ficha_id
     and r.lleva_caja_nuestra is null
     and r.anulado_el is null
     and r.tipo <> 'inicial'
     and r.fecha_operacion >= v_desde;

  get diagnostics v_tocadas = row_count;

  if v_tocadas > 5 then
    raise exception 'Tocaria % guias y se esperaban a lo sumo 5. No se escribio nada.', v_tocadas;
  end if;
end $$;

-- ---------------------------------------------------------------------------
-- LAS GUIAS R QUE QUEDARON SIN DECIR EN QUE CAJA SE ARMARON.
--
-- La caja SALE DE LA FICHA, asi que esto no inventa nada: aplica la misma
-- derivacion que `envase_derivado_de_la_ficha` hace al escribir. Ficha con
-- envase -> true y su envase; ficha sin envase -> false y NULL, que es
-- "envase perdido" y tampoco es un hueco.
--
-- SOLO DESDE EL CONTEO INICIAL, y ese recorte es el punto: son las unicas
-- que pueden mover la cuenta (`fecha_operacion >= conteo.fecha`). Las
-- anteriores no mueven ningun numero, y tocarlas seria re-etiquetar historia
-- para nada.
--
-- Las 'inicial' quedan afuera: son las cajas que ya estaban armadas el dia
-- del corte y su signo es 0, asi que declararlas no cambia una cuenta.
--
-- LA GUARDA ES EL CONTEO, no la lista: se midio 1 en Frutamax y 0 en Palmala
-- (cajas_9, 17/09). Si tocara mas de cinco, algo cambio desde la medicion y
-- el bloque aborta entero sin escribir. En Palmala aborta en el primer
-- `raise`, que es correcto: sin conteo inicial no hay cuenta que corregir.
--
-- NO HACE FALTA RECARGAR NINGUNA GUIA: el stock de cajas se deriva en cada
-- lectura, asi que escribir estas dos columnas alcanza para que la guia
-- empiece a descontar.

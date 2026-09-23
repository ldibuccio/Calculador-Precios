do $$
begin
  update cargas_compra set dias = 1 where dias is null;
  alter table cargas_compra alter column dias set not null;
end $$;

-- SE CORRE DESPUÉS DEL DEPLOY del código que escribe `dias`: hasta
-- entonces el código viejo inserta sin la columna y el NOT NULL lo
-- rebotaría. El update de arriba cubre las cargas que el código viejo
-- haya creado entre el bloque 1 y el deploy.

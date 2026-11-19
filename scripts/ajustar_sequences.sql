-- Reposiciona todas as sequences do schema public para MAX(coluna)+1 (ou 1 se vazia).
DO $$
DECLARE r record; max_id bigint;
BEGIN
  FOR r IN
    SELECT n.nspname AS sch, c.relname AS tbl, a.attname AS col,
           pg_get_serial_sequence(format('%I.%I', n.nspname, c.relname), a.attname) AS seq
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
    WHERE n.nspname = 'public' AND c.relkind = 'r'
  LOOP
    IF r.seq IS NOT NULL THEN
      EXECUTE format('SELECT COALESCE(MAX(%I), 0) FROM %I.%I', r.col, r.sch, r.tbl) INTO max_id;
      IF max_id = 0 THEN
        PERFORM setval(r.seq, 1, false);
      ELSE
        PERFORM setval(r.seq, max_id, true);
      END IF;
    END IF;
  END LOOP;
END $$;

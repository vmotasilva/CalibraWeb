-- Lista (uma linha por problema) sequences cujo próximo valor é <= MAX(coluna). Saída vazia = ok.
DO $$
DECLARE r record; max_id bigint; last_v bigint; is_called boolean;
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
      EXECUTE format('SELECT last_value, is_called FROM %s', r.seq) INTO last_v, is_called;
      IF max_id > 0 AND (last_v < max_id OR (last_v = max_id AND NOT is_called)) THEN
        RAISE WARNING 'SEQ_PROBLEMA %.% (%): last=% max=%', r.sch, r.tbl, r.col, last_v, max_id;
      END IF;
    END IF;
  END LOOP;
END $$;

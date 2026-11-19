-- Habilita RLS em todas as tabelas do schema public (sem policies).
-- Efeito: a Data API do Supabase (anon/authenticated) não enxerga nada.
-- O Django conecta como 'postgres' (dono/bypass de RLS), portanto continua funcionando normalmente.
DO $$
DECLARE r record;
BEGIN
  FOR r IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', r.tablename);
  END LOOP;
END $$;

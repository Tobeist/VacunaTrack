-- ═════════════════════════════════════════════════════════════════════════════
-- VacunaTrack — 06_ownership.sql
-- Transfiere la propiedad de vistas, funciones y procedimientos a
-- vacunatrack_user. Ejecutar como superusuario (postgres) después de
-- haber aplicado los demás archivos SQL.
--
--   sudo -u postgres psql -d vacunatrack -f sql/06_ownership.sql
-- ═════════════════════════════════════════════════════════════════════════════

\c vacunatrack

-- ── Vistas ───────────────────────────────────────────────────────────────────
DO $$
DECLARE r RECORD;
BEGIN
    FOR r IN SELECT viewname FROM pg_views WHERE schemaname = 'public' LOOP
        EXECUTE format('ALTER VIEW public.%I OWNER TO vacunatrack_user', r.viewname);
        RAISE NOTICE 'VIEW % → vacunatrack_user', r.viewname;
    END LOOP;
END $$;

-- ── Funciones y procedimientos ───────────────────────────────────────────────
DO $$
DECLARE r RECORD;
BEGIN
    FOR r IN
        SELECT
            CASE p.prokind WHEN 'p' THEN 'PROCEDURE' ELSE 'FUNCTION' END AS kind,
            p.proname AS name,
            pg_catalog.pg_get_function_identity_arguments(p.oid) AS args
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public'
    LOOP
        EXECUTE format(
            'ALTER %s public.%I(%s) OWNER TO vacunatrack_user',
            r.kind, r.name, r.args
        );
        RAISE NOTICE '% %() → vacunatrack_user', r.kind, r.name;
    END LOOP;
END $$;

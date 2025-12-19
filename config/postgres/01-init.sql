-- =============================================================================
-- PostgreSQL Init Script - Dziki na Białołęce
-- Executed on first container startup (BEFORE 02-fix-hba.sh)
-- =============================================================================

-- =============================================================================
-- 1. PASSWORD ENCRYPTION (ustawienie globalne)
-- =============================================================================
-- PgBouncer używa MD5 auth_type, więc PostgreSQL musi też używać MD5
ALTER SYSTEM SET password_encryption = 'md5';
SELECT pg_reload_conf();

-- =============================================================================
-- 2. RESET HASŁA UŻYTKOWNIKA (teraz z MD5 encryption)
-- =============================================================================
-- Użytkownik 'dziki' został utworzony przez POSTGRES_USER z SCRAM-SHA-256
-- Musimy zresetować hasło żeby było zahashowane jako MD5
-- UWAGA: Hasło musi być zgodne z DB_PASSWORD w .env i userlist.txt
ALTER USER dziki PASSWORD 'dziki_dev_password';

-- =============================================================================
-- 3. EXTENSIONS (PostGIS)
-- =============================================================================
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- =============================================================================
-- 4. VERIFICATION
-- =============================================================================
DO $$
DECLARE
    pwd_hash text;
    postgis_ver text;
BEGIN
    SELECT rolpassword INTO pwd_hash FROM pg_authid WHERE rolname = 'dziki';
    SELECT PostGIS_Version() INTO postgis_ver;
    
    IF pwd_hash LIKE 'md5%' THEN
        RAISE NOTICE '✓ User dziki: MD5 hash OK';
    ELSE
        RAISE WARNING '✗ User dziki: Expected MD5, got %', substring(pwd_hash, 1, 10);
    END IF;
    
    RAISE NOTICE '✓ PostGIS version: %', postgis_ver;
    RAISE NOTICE '→ Next: 02-fix-hba.sh will configure pg_hba.conf for MD5 auth';
END $$;

-- =============================================================================
-- SCHEMA NOTES (dla przyszłych migracji Django)
-- =============================================================================
-- Tabele będą tworzone przez Django migrations (GeoDjango)
--
-- PRZYSZŁE INDEKSY (opcjonalne, performance):
-- 
-- SPGIST dla geometrii punktowej (10-30% szybciej niż GIST):
--   CREATE INDEX idx_sightings_location_spgist ON sightings USING SPGIST (location);
--
-- BRIN dla kolumn czasowych (12.8x szybciej dla range queries):
--   CREATE INDEX idx_sightings_observed_at_brin ON sightings USING BRIN (observed_at);
--
-- Partial index dla moderacji:
--   CREATE INDEX idx_sightings_pending ON sightings (id) WHERE status = 'pending';

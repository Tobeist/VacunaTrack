-- =============================================================================
-- VacunaTrack — Migración 004: SP tutores esperando por vacuna
-- Ejecutar como vacunatrack_user o superusuario sobre la BD vacunatrack.
-- =============================================================================

-- Devuelve los tutor_ids con lectura beacon reciente en el centro,
-- permitiendo calcular en Flask cuántos necesitan cada vacuna específica.
CREATE OR REPLACE PROCEDURE sp_tutores_esperando_en_centro(
    IN p_centro_id INTEGER, INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
        SELECT DISTINCT tutor_id
        FROM lecturas_beacon
        WHERE centro_id = p_centro_id
          AND lectura_timestamp > NOW() - INTERVAL '45 minutes';
END; $$;

GRANT EXECUTE ON PROCEDURE sp_tutores_esperando_en_centro(INTEGER, REFCURSOR) TO vacunatrack_user;

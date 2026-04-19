-- =============================================================================
-- VacunaTrack — Migración 002: SPs faltantes
-- SPs de lectura (REFCURSOR) y escritura para beacon, dashboard y reportes.
-- Ejecutar como vacunatrack_user o superusuario sobre la BD vacunatrack.
-- =============================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- SPs de lectura por ID (patrones de creación)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE PROCEDURE sp_obtener_cedula(
    IN p_id INTEGER, INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR SELECT * FROM vw_cedulas WHERE cedula_id = p_id;
END; $$;

CREATE OR REPLACE PROCEDURE sp_obtener_relacion(
    IN p_id INTEGER, INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR SELECT * FROM vw_relaciones WHERE pac_tut_id = p_id;
END; $$;

CREATE OR REPLACE PROCEDURE sp_obtener_aplicacion(
    IN p_id INTEGER, INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR SELECT * FROM vw_aplicaciones WHERE aplicacion_id = p_id;
END; $$;

CREATE OR REPLACE PROCEDURE sp_obtener_padecimiento(
    IN p_id INTEGER, INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR SELECT * FROM vw_padecimientos WHERE padecimiento_id = p_id;
END; $$;

-- ─────────────────────────────────────────────────────────────────────────────
-- SPs de verificación (retornan booleano)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE PROCEDURE sp_existe_relacion(
    IN p_paciente_id INTEGER, IN p_tutor_id INTEGER,
    INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
        SELECT EXISTS(
            SELECT 1 FROM pacientes_tutores
            WHERE paciente_id = p_paciente_id AND tutor_id = p_tutor_id
        ) AS result;
END; $$;

CREATE OR REPLACE PROCEDURE sp_dosis_ya_aplicada(
    IN p_paciente_id INTEGER, IN p_dosis_id INTEGER,
    INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
        SELECT EXISTS(
            SELECT 1 FROM aplicaciones
            WHERE paciente_id = p_paciente_id AND dosis_id = p_dosis_id
        ) AS result;
END; $$;

-- ─────────────────────────────────────────────────────────────────────────────
-- SPs de beacon
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE PROCEDURE sp_obtener_centro_por_beacon(
    IN p_beacon_id VARCHAR(100), INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR SELECT * FROM vw_centros WHERE centro_beacon = p_beacon_id;
END; $$;

CREATE OR REPLACE PROCEDURE sp_vacunas_en_centro(
    IN p_centro_id INTEGER, INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
        SELECT * FROM vw_centros_stock_vacuna WHERE centro_id = p_centro_id;
END; $$;

CREATE OR REPLACE PROCEDURE sp_personas_esperando_en_centro(
    IN p_centro_id INTEGER, INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
        SELECT COUNT(DISTINCT tutor_id)::INTEGER AS total
        FROM lecturas_beacon
        WHERE centro_id = p_centro_id
          AND lectura_timestamp > NOW() - INTERVAL '45 minutes';
END; $$;

-- SP de escritura: registra lectura beacon deduplicada (ventana de 1 hora)
CREATE OR REPLACE PROCEDURE sp_registrar_lectura_beacon(
    IN  p_centro_id INTEGER,
    IN  p_tutor_id  INTEGER,
    INOUT p_ok  SMALLINT,
    INOUT p_msg VARCHAR(150)
)
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM lecturas_beacon
        WHERE centro_id = p_centro_id
          AND tutor_id  = p_tutor_id
          AND lectura_timestamp > NOW() - INTERVAL '1 hour'
    ) THEN
        INSERT INTO lecturas_beacon(centro_id, tutor_id) VALUES (p_centro_id, p_tutor_id);
    END IF;
    p_ok  := 1;
    p_msg := 'OK';
END; $$;

-- ─────────────────────────────────────────────────────────────────────────────
-- Vista y SP de estadísticas del dashboard
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE VIEW vw_stats_dashboard AS
SELECT
    (SELECT COUNT(*) FROM vw_pacientes)    AS pacientes,
    (SELECT COUNT(*) FROM vw_tutores)      AS tutores,
    (SELECT COUNT(*) FROM vw_responsables) AS responsables,
    (SELECT COUNT(*) FROM vw_centros)      AS centros,
    (SELECT COUNT(*) FROM vw_aplicaciones
     WHERE DATE(aplicacion_timestamp) = CURRENT_DATE) AS aplicaciones_hoy,
    (SELECT COUNT(*) FROM vw_alertas_inventario) AS alertas_inv,
    (SELECT COUNT(*) FROM vw_alertas_dosis)      AS alertas_dosis;

CREATE OR REPLACE PROCEDURE sp_stats_dashboard(INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR SELECT * FROM vw_stats_dashboard;
END; $$;

-- ─────────────────────────────────────────────────────────────────────────────
-- SPs de gráficas y reportes
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE PROCEDURE sp_chart_aplicaciones_por_mes(
    IN p_meses INTEGER, INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
        SELECT TO_CHAR(DATE_TRUNC('month', aplicacion_timestamp), 'Mon YYYY') AS mes,
               COUNT(*) AS total
        FROM vw_aplicaciones
        WHERE aplicacion_timestamp >= DATE_TRUNC('month',
              NOW() - ((p_meses - 1)::TEXT || ' months')::INTERVAL)
        GROUP BY DATE_TRUNC('month', aplicacion_timestamp)
        ORDER BY DATE_TRUNC('month', aplicacion_timestamp);
END; $$;

CREATE OR REPLACE PROCEDURE sp_chart_por_mes(
    IN p_desde     DATE,
    IN p_hasta     DATE,
    IN p_centro_id INTEGER,
    IN p_vacuna_id INTEGER,
    INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
        SELECT TO_CHAR(DATE_TRUNC('month', aplicacion_timestamp), 'Mon YYYY') AS mes,
               COUNT(*) AS total
        FROM vw_aplicaciones
        WHERE aplicacion_timestamp BETWEEN p_desde AND (p_hasta + INTERVAL '23:59:59')
          AND (p_centro_id IS NULL OR centro_id = p_centro_id)
          AND (p_vacuna_id IS NULL OR vacuna_id = p_vacuna_id)
        GROUP BY DATE_TRUNC('month', aplicacion_timestamp)
        ORDER BY DATE_TRUNC('month', aplicacion_timestamp);
END; $$;

CREATE OR REPLACE PROCEDURE sp_chart_top_vacunas(
    IN p_desde     DATE,
    IN p_hasta     DATE,
    IN p_centro_id INTEGER,
    IN p_vacuna_id INTEGER,
    INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
        SELECT vacuna_nombre, COUNT(*) AS total
        FROM vw_aplicaciones
        WHERE aplicacion_timestamp BETWEEN p_desde AND (p_hasta + INTERVAL '23:59:59')
          AND (p_centro_id IS NULL OR centro_id = p_centro_id)
          AND (p_vacuna_id IS NULL OR vacuna_id = p_vacuna_id)
        GROUP BY vacuna_nombre
        ORDER BY total DESC
        LIMIT 8;
END; $$;

CREATE OR REPLACE PROCEDURE sp_resumen_periodo(
    IN p_desde     DATE,
    IN p_hasta     DATE,
    IN p_centro_id INTEGER,
    IN p_vacuna_id INTEGER,
    INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
        SELECT COUNT(*) AS total
        FROM vw_aplicaciones
        WHERE aplicacion_timestamp BETWEEN p_desde AND (p_hasta + INTERVAL '23:59:59')
          AND (p_centro_id IS NULL OR centro_id = p_centro_id)
          AND (p_vacuna_id IS NULL OR vacuna_id = p_vacuna_id);
END; $$;

-- ─────────────────────────────────────────────────────────────────────────────
-- Permisos
-- ─────────────────────────────────────────────────────────────────────────────

GRANT SELECT ON vw_stats_dashboard TO vacunatrack_user;
GRANT EXECUTE ON ALL PROCEDURES IN SCHEMA public TO vacunatrack_user;

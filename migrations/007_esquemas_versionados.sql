-- =============================================================================
-- VacunaTrack — Migración 007: Esquemas versionados y asignación semi-automática
-- =============================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- Vista: pacientes con conflictos pendientes de resolución
-- Un conflicto existe cuando:
--   1. El paciente sigue en un esquema cerrado (vigente_hasta IS NOT NULL)
--   2. Una dosis de ese esquema no está en el nuevo esquema activo
--   3. El paciente aún no la recibió y todavía es elegible por edad
--   4. El admin no ha marcado la decisión en esquemas_pacientes
-- ─────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW vw_conflictos_esquema AS
WITH esquema_activo AS (
    SELECT esquema_id, esquema_nombre
    FROM   esquemas
    WHERE  esquema_vigente_hasta IS NULL
    ORDER  BY esquema_vigente_desde DESC
    LIMIT  1
)
SELECT
    p.paciente_id,
    p.paciente_prim_nombre,
    p.paciente_seg_nombre,
    p.paciente_apellido_pat,
    p.paciente_apellido_mat,
    p.paciente_fecha_nac,
    (CURRENT_DATE - p.paciente_fecha_nac)   AS edad_dias,
    p.esquema_id                             AS esquema_actual_id,
    e_viejo.esquema_nombre                   AS esquema_actual_nombre,
    ea.esquema_id                            AS esquema_nuevo_id,
    ea.esquema_nombre                        AS esquema_nuevo_nombre,
    d.dosis_id                               AS dosis_conflicto_id,
    d.dosis_tipo,
    d.dosis_edad_oportuna_dias,
    d.dosis_limite_edad_dias,
    v.vacuna_nombre
FROM   pacientes      p
JOIN   esquemas       e_viejo ON e_viejo.esquema_id = p.esquema_id
                              AND e_viejo.esquema_vigente_hasta IS NOT NULL
CROSS  JOIN esquema_activo    ea
JOIN   dosis_esquemas de_v    ON de_v.esquema_id    = p.esquema_id
JOIN   dosis          d       ON d.dosis_id         = de_v.dosis_id
JOIN   vacunas        v       ON v.vacuna_id        = d.vacuna_id
WHERE
    NOT EXISTS (
        SELECT 1 FROM dosis_esquemas de_n
        WHERE  de_n.esquema_id = ea.esquema_id
          AND  de_n.dosis_id   = d.dosis_id
    )
    AND NOT EXISTS (
        SELECT 1 FROM aplicaciones a
        WHERE  a.paciente_id = p.paciente_id
          AND  a.dosis_id    = d.dosis_id
    )
    AND (d.dosis_limite_edad_dias IS NULL
         OR (CURRENT_DATE - p.paciente_fecha_nac) < d.dosis_limite_edad_dias)
    AND NOT EXISTS (
        SELECT 1 FROM esquemas_pacientes ep
        WHERE  ep.paciente_id           = p.paciente_id
          AND  ep.esquema_id            = p.esquema_id
          AND  ep.esq_pac_motivo_cambio LIKE 'conflicto_resuelto:%'
    );

-- ─────────────────────────────────────────────────────────────────────────────
-- SP: listar conflictos pendientes
-- ─────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE PROCEDURE sp_listar_conflictos_esquema(INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
        SELECT * FROM vw_conflictos_esquema
        ORDER BY paciente_apellido_pat, paciente_prim_nombre, dosis_edad_oportuna_dias;
END; $$;

-- ─────────────────────────────────────────────────────────────────────────────
-- SP: solo dosis activas (vigente_hasta IS NULL) para el formulario
-- ─────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE PROCEDURE sp_listar_dosis_activas(INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
        SELECT * FROM vw_dosis
        WHERE  dosis_vigente_hasta IS NULL
        ORDER  BY vacuna_id, dosis_edad_oportuna_dias;
END; $$;

-- ─────────────────────────────────────────────────────────────────────────────
-- SP: archivar un esquema (cierra su vigencia)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE PROCEDURE sp_cerrar_esquema(
    IN  p_esquema_id  INTEGER,
    OUT p_ok   SMALLINT,
    OUT p_msg  VARCHAR(150)
)
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE esquemas
    SET    esquema_vigente_hasta = CURRENT_DATE
    WHERE  esquema_id = p_esquema_id
      AND  esquema_vigente_hasta IS NULL;

    IF NOT FOUND THEN
        p_ok := 0; p_msg := 'El esquema no existe o ya fue archivado'; RETURN;
    END IF;
    p_ok := 1; p_msg := 'Esquema archivado';
EXCEPTION
    WHEN OTHERS THEN p_ok := 0; p_msg := SQLERRM;
END; $$;

-- ─────────────────────────────────────────────────────────────────────────────
-- SP: desactivar una dosis (marca vigente_hasta)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE PROCEDURE sp_desactivar_dosis(
    IN  p_dosis_id  INTEGER,
    OUT p_ok   SMALLINT,
    OUT p_msg  VARCHAR(150)
)
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE dosis
    SET    dosis_vigente_hasta = CURRENT_DATE
    WHERE  dosis_id = p_dosis_id
      AND  dosis_vigente_hasta IS NULL;

    p_ok := 1; p_msg := 'Dosis desactivada';
EXCEPTION
    WHEN OTHERS THEN p_ok := 0; p_msg := SQLERRM;
END; $$;

-- ─────────────────────────────────────────────────────────────────────────────
-- SP: asignar nuevo esquema automáticamente a pacientes sin conflicto
-- ─────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE PROCEDURE sp_asignar_esquema_auto(
    IN  p_viejo_id      INTEGER,
    IN  p_nuevo_id      INTEGER,
    OUT p_ok            SMALLINT,
    OUT p_msg           VARCHAR(200),
    OUT p_actualizados  INTEGER
)
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE pacientes pac
    SET    esquema_id = p_nuevo_id
    WHERE  pac.esquema_id = p_viejo_id
      AND  NOT EXISTS (
               SELECT 1
               FROM   dosis_esquemas de_v
               JOIN   dosis d ON d.dosis_id = de_v.dosis_id
               WHERE  de_v.esquema_id = p_viejo_id
                 AND  NOT EXISTS (
                          SELECT 1 FROM dosis_esquemas de_n
                          WHERE  de_n.esquema_id = p_nuevo_id
                            AND  de_n.dosis_id   = d.dosis_id
                      )
                 AND  NOT EXISTS (
                          SELECT 1 FROM aplicaciones a
                          WHERE  a.paciente_id = pac.paciente_id
                            AND  a.dosis_id    = d.dosis_id
                      )
                 AND  (d.dosis_limite_edad_dias IS NULL
                       OR (CURRENT_DATE - pac.paciente_fecha_nac) < d.dosis_limite_edad_dias)
           );

    GET DIAGNOSTICS p_actualizados = ROW_COUNT;
    p_ok  := 1;
    p_msg := 'Asignación automática: ' || p_actualizados || ' paciente(s) actualizado(s).';
EXCEPTION
    WHEN OTHERS THEN
        p_ok := 0; p_msg := 'Error: ' || SQLERRM; p_actualizados := 0;
END; $$;

-- ─────────────────────────────────────────────────────────────────────────────
-- SP: resolver conflicto de esquema manualmente
-- ─────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE PROCEDURE sp_resolver_conflicto(
    IN  p_paciente_id       INTEGER,
    IN  p_esquema_nuevo_id  INTEGER,
    IN  p_accion            VARCHAR(20),
    OUT p_ok   SMALLINT,
    OUT p_msg  VARCHAR(200)
)
LANGUAGE plpgsql AS $$
DECLARE
    v_esquema_viejo_id INTEGER;
BEGIN
    SELECT esquema_id INTO v_esquema_viejo_id
    FROM   pacientes WHERE paciente_id = p_paciente_id;

    IF NOT FOUND THEN
        p_ok := 0; p_msg := 'Paciente no encontrado'; RETURN;
    END IF;

    IF p_accion = 'actualizar' THEN
        UPDATE pacientes SET esquema_id = p_esquema_nuevo_id
        WHERE  paciente_id = p_paciente_id;
        p_ok := 1; p_msg := 'Esquema del paciente actualizado al nuevo';

    ELSIF p_accion = 'mantener' THEN
        UPDATE esquemas_pacientes
        SET    esq_pac_motivo_cambio =
                   'conflicto_resuelto:mantener:nuevo=' || p_esquema_nuevo_id
        WHERE  paciente_id = p_paciente_id
          AND  esquema_id  = v_esquema_viejo_id
          AND  esq_pac_hasta IS NULL;
        p_ok := 1; p_msg := 'Decisión registrada: paciente conserva su esquema actual';

    ELSE
        p_ok := 0; p_msg := 'Acción inválida. Use "actualizar" o "mantener"';
    END IF;
EXCEPTION
    WHEN OTHERS THEN p_ok := 0; p_msg := 'Error: ' || SQLERRM;
END; $$;

-- ─────────────────────────────────────────────────────────────────────────────
-- Permisos
-- ─────────────────────────────────────────────────────────────────────────────
GRANT SELECT   ON vw_conflictos_esquema TO vacunatrack_user;
GRANT EXECUTE  ON PROCEDURE sp_listar_conflictos_esquema(REFCURSOR)                          TO vacunatrack_user;
GRANT EXECUTE  ON PROCEDURE sp_listar_dosis_activas(REFCURSOR)                               TO vacunatrack_user;
GRANT EXECUTE  ON PROCEDURE sp_cerrar_esquema(INTEGER, SMALLINT, VARCHAR)                    TO vacunatrack_user;
GRANT EXECUTE  ON PROCEDURE sp_desactivar_dosis(INTEGER, SMALLINT, VARCHAR)                  TO vacunatrack_user;
GRANT EXECUTE  ON PROCEDURE sp_asignar_esquema_auto(INTEGER, INTEGER, SMALLINT, VARCHAR, INTEGER) TO vacunatrack_user;
GRANT EXECUTE  ON PROCEDURE sp_resolver_conflicto(INTEGER, INTEGER, VARCHAR, SMALLINT, VARCHAR)   TO vacunatrack_user;

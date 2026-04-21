-- =============================================================================
-- VacunaTrack — Migración 006: Eliminar p_timestamp de sp_registrar_aplicacion
-- Usar NOW() internamente evita problemas de zona horaria entre Python y PG.
-- =============================================================================

CREATE OR REPLACE PROCEDURE sp_registrar_aplicacion(
    IN  p_paciente_id   INTEGER,  IN  p_usuario_id     INTEGER,
    IN  p_centro_id     INTEGER,  IN  p_lote_id        INTEGER,
    IN  p_dosis_id      INTEGER,
    IN  p_observaciones TEXT,
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(150), OUT p_id INTEGER)
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM pacientes WHERE paciente_id = p_paciente_id) THEN
        p_ok := 0; p_msg := 'Paciente no encontrado'; RETURN;
    END IF;
    IF NOT EXISTS(SELECT 1 FROM dosis WHERE dosis_id = p_dosis_id) THEN
        p_ok := 0; p_msg := 'Dosis no encontrada'; RETURN;
    END IF;
    IF EXISTS(SELECT 1 FROM aplicaciones WHERE paciente_id = p_paciente_id AND dosis_id = p_dosis_id) THEN
        p_ok := 0; p_msg := 'Esta dosis ya fue aplicada a este paciente'; RETURN;
    END IF;
    IF NOT EXISTS(SELECT 1 FROM vw_inventarios
                  WHERE inventario_activo_desde IS NOT NULL
                    AND inventario_stock_actual > 0
                    AND centro_id = p_centro_id AND lote_id = p_lote_id) THEN
        p_ok := 0; p_msg := 'No hay inventario activo con stock disponible'; RETURN;
    END IF;

    INSERT INTO aplicaciones(paciente_id, usuario_id, centro_id, lote_id, dosis_id,
        aplicacion_timestamp, aplicacion_observaciones)
    VALUES(p_paciente_id, p_usuario_id, p_centro_id, p_lote_id, p_dosis_id,
           NOW(), p_observaciones)
    RETURNING aplicacion_id INTO p_id;
    p_ok := 1; p_msg := 'Aplicación registrada correctamente';
EXCEPTION
    WHEN OTHERS THEN p_ok := 0; p_msg := 'Error al registrar aplicación: ' || SQLERRM;
END; $$;

GRANT EXECUTE ON PROCEDURE sp_registrar_aplicacion(INTEGER, INTEGER, INTEGER, INTEGER, INTEGER, TEXT, SMALLINT, VARCHAR, INTEGER) TO vacunatrack_user;

-- =============================================================================
-- VacunaTrack — Migración 003: Confirmación de recepción de inventario
-- Ejecutar como vacunatrack_user o superusuario sobre la BD vacunatrack.
-- =============================================================================

-- SP de lectura: inventarios pendientes (sin activar) de un centro
CREATE OR REPLACE PROCEDURE sp_inventarios_pendientes_de_centro(
    IN p_centro_id INTEGER, INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
        SELECT * FROM vw_inventarios
        WHERE centro_id = p_centro_id
          AND inventario_activo_desde IS NULL
        ORDER BY lote_codigo;
END; $$;

-- SP de escritura: valida lote + centro + responsable y activa el inventario
CREATE OR REPLACE PROCEDURE sp_confirmar_recepcion_inventario(
    IN  p_lote_codigo    VARCHAR(50),
    IN  p_responsable_id INTEGER,
    INOUT p_ok  SMALLINT,
    INOUT p_msg VARCHAR(200)
)
LANGUAGE plpgsql AS $$
DECLARE
    v_lote_id        INTEGER;
    v_centro_id      INTEGER;
    v_inventario_id  INTEGER;
BEGIN
    -- Verificar que el código de lote existe
    SELECT lote_id INTO v_lote_id
    FROM lotes WHERE lote_codigo = p_lote_codigo;

    IF v_lote_id IS NULL THEN
        p_ok  := 0;
        p_msg := 'No existe ningún lote con ese código. Verifica e intenta de nuevo.';
        RETURN;
    END IF;

    -- Obtener el centro al que pertenece el responsable
    SELECT centro_id INTO v_centro_id
    FROM usuarios WHERE usuario_id = p_responsable_id;

    IF v_centro_id IS NULL THEN
        p_ok  := 0;
        p_msg := 'Tu usuario no tiene un centro de salud asignado.';
        RETURN;
    END IF;

    -- Buscar inventario pendiente de activación para ese lote en ese centro
    SELECT inventario_id INTO v_inventario_id
    FROM inventarios
    WHERE lote_id  = v_lote_id
      AND centro_id = v_centro_id
      AND inventario_activo_desde IS NULL
    LIMIT 1;

    IF v_inventario_id IS NULL THEN
        p_ok  := 0;
        p_msg := 'No hay ningún inventario pendiente de activación para ese lote en tu centro de salud.';
        RETURN;
    END IF;

    -- Activar el inventario
    UPDATE inventarios
    SET inventario_activo_desde = NOW(),
        usuario_id              = p_responsable_id
    WHERE inventario_id = v_inventario_id;

    p_ok  := 1;
    p_msg := 'Inventario activado correctamente.';
END; $$;

-- Permisos
GRANT EXECUTE ON PROCEDURE sp_inventarios_pendientes_de_centro(INTEGER, REFCURSOR) TO vacunatrack_user;
GRANT EXECUTE ON PROCEDURE sp_confirmar_recepcion_inventario(VARCHAR, INTEGER, SMALLINT, VARCHAR) TO vacunatrack_user;

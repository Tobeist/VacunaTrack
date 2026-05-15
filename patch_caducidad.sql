-- ─────────────────────────────────────────────────────────
-- PATCH: excluir lotes caducados de checks de disponibilidad
-- Aplicar con: psql -U <usuario> -d vacunatrack -f patch_caducidad.sql
-- ─────────────────────────────────────────────────────────

-- 1. Vista: centros con stock disponible (usada por tutores al buscar centros)
CREATE OR REPLACE VIEW vw_centros_stock_vacuna AS
SELECT cs.centro_id,
       cs.centro_nombre,
       cs.centro_calle,
       cs.centro_numero,
       cs.centro_codigo_postal,
       cs.ciudad_id,
       cs.centro_horario_inicio,
       cs.centro_horario_fin,
       cs.centro_latitud,
       cs.centro_longitud,
       cs.centro_telefono,
       cs.centro_beacon,
       ci.ciudad_nombre,
       l.vacuna_id,
       SUM(i.inventario_stock_actual) AS stock_total
FROM centros_salud cs
JOIN inventarios i  ON i.centro_id  = cs.centro_id
JOIN lotes       l  ON l.lote_id    = i.lote_id
JOIN ciudades    ci ON ci.ciudad_id  = cs.ciudad_id
WHERE i.inventario_activo_desde IS NOT NULL
  AND i.inventario_stock_actual > 0
  AND (l.lote_fecha_caducidad IS NULL OR l.lote_fecha_caducidad > CURRENT_DATE)
GROUP BY cs.centro_id, ci.ciudad_nombre, l.vacuna_id;

-- 2. Función del trigger: elige qué inventario descontar al registrar aplicación
CREATE OR REPLACE FUNCTION trg_descontar_inventario()
RETURNS TRIGGER AS $$
DECLARE
    v_inventario_id integer;
BEGIN
    SELECT i.inventario_id INTO v_inventario_id
    FROM inventarios i
    JOIN lotes l ON l.lote_id = i.lote_id
    WHERE i.centro_id                = NEW.centro_id
      AND i.lote_id                  = NEW.lote_id
      AND i.inventario_activo_desde IS NOT NULL
      AND i.inventario_stock_actual  > 0
      AND (l.lote_fecha_caducidad IS NULL OR l.lote_fecha_caducidad > CURRENT_DATE)
    ORDER BY i.inventario_activo_desde DESC
    LIMIT 1;

    IF v_inventario_id IS NULL THEN
        RAISE EXCEPTION
            'No hay inventario activo con stock disponible para el lote % en el centro %.',
            NEW.lote_id, NEW.centro_id;
    END IF;

    UPDATE inventarios
    SET inventario_stock_actual = inventario_stock_actual - 1
    WHERE inventario_id = v_inventario_id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 3. SP: stock disponible de un lote en un centro
CREATE OR REPLACE PROCEDURE sp_stock_disponible(
    IN    p_centro_id   INTEGER,
    IN    p_lote_id     INTEGER,
    INOUT p_resultados  REFCURSOR
)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
        SELECT COALESCE(SUM(inventario_stock_actual), 0) AS stock_disponible
        FROM vw_inventarios
        WHERE centro_id              = p_centro_id
          AND lote_id                = p_lote_id
          AND inventario_activo_desde IS NOT NULL
          AND (lote_fecha_caducidad IS NULL OR lote_fecha_caducidad > CURRENT_DATE);
END;
$$;

-- 4. SP: inventarios activos de un centro (usados para registrar aplicaciones)
CREATE OR REPLACE PROCEDURE sp_inventarios_activos_de_centro(
    IN p_centro_id INTEGER, INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
        SELECT * FROM vw_inventarios
        WHERE centro_id = p_centro_id
          AND inventario_activo_desde IS NOT NULL
          AND inventario_stock_actual > 0
          AND (lote_fecha_caducidad IS NULL OR lote_fecha_caducidad > CURRENT_DATE)
        ORDER BY vacuna_nombre;
END; $$;

-- 5. SP: registrar aplicación (validación de inventario disponible)
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
                    AND (lote_fecha_caducidad IS NULL OR lote_fecha_caducidad > CURRENT_DATE)
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

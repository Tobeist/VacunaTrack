-- =============================================================================
-- VacunaTrack — Migración 005: Trigger stock lote + transferencia de inventario
-- Ejecutar como vacunatrack_user o superusuario sobre la BD vacunatrack.
-- =============================================================================

-- Agregar timestamp a transferencias_inventario para trazabilidad
ALTER TABLE transferencias_inventario
ADD COLUMN IF NOT EXISTS transf_timestamp TIMESTAMP DEFAULT NOW();

-- ─────────────────────────────────────────────────────────────────────────────
-- TRIGGER: evitar sobreasignación directa de un lote
-- Solo aplica a inserciones con inventario_origen_id IS NULL (asignaciones
-- directas del admin). Las transferencias quedan excluidas porque reutilizan
-- stock ya contabilizado.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION trg_verificar_stock_lote()
RETURNS TRIGGER AS $$
DECLARE
    v_cant_inicial INTEGER;
    v_ya_asignado  INTEGER;
BEGIN
    IF NEW.inventario_origen_id IS NULL THEN
        SELECT lote_cant_inicial INTO v_cant_inicial
        FROM lotes WHERE lote_id = NEW.lote_id;

        SELECT COALESCE(SUM(inventario_stock_inicial), 0) INTO v_ya_asignado
        FROM inventarios
        WHERE lote_id = NEW.lote_id
          AND inventario_origen_id IS NULL;

        IF v_ya_asignado + NEW.inventario_stock_inicial > v_cant_inicial THEN
            RAISE EXCEPTION
                'La cantidad solicitada (%) supera el disponible del lote. '
                'Capacidad total: %, ya asignado: %, disponible: %.',
                NEW.inventario_stock_inicial,
                v_cant_inicial,
                v_ya_asignado,
                v_cant_inicial - v_ya_asignado;
        END IF;
    END IF;
    RETURN NEW;
END; $$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_verificar_stock_lote
BEFORE INSERT ON inventarios
FOR EACH ROW EXECUTE FUNCTION trg_verificar_stock_lote();

-- ─────────────────────────────────────────────────────────────────────────────
-- Vista de trazabilidad de transferencias
-- ─────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW vw_transferencias AS
SELECT
    t.transf_id,
    t.transf_timestamp,
    t.inv_origen_id,
    t.inv_destino_id,
    cso.centro_nombre                    AS origen_centro_nombre,
    csd.centro_nombre                    AS destino_centro_nombre,
    lo.lote_codigo,
    v.vacuna_nombre,
    id2.inventario_stock_inicial         AS cantidad_transferida,
    io.inventario_stock_actual           AS origen_stock_restante,
    id2.inventario_activo_desde          AS destino_activo_desde,
    (id2.inventario_activo_desde IS NOT NULL) AS destino_confirmado
FROM transferencias_inventario t
JOIN inventarios     io  ON io.inventario_id  = t.inv_origen_id
JOIN inventarios     id2 ON id2.inventario_id = t.inv_destino_id
JOIN centros_salud   cso ON cso.centro_id     = io.centro_id
JOIN centros_salud   csd ON csd.centro_id     = id2.centro_id
JOIN lotes           lo  ON lo.lote_id        = io.lote_id
JOIN vacunas         v   ON v.vacuna_id       = lo.vacuna_id;

-- ─────────────────────────────────────────────────────────────────────────────
-- SPs
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE PROCEDURE sp_listar_transferencias(INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
        SELECT * FROM vw_transferencias ORDER BY transf_timestamp DESC;
END; $$;

CREATE OR REPLACE PROCEDURE sp_transferir_inventario(
    IN    p_inv_origen_id     INTEGER,
    IN    p_centro_destino_id INTEGER,
    IN    p_cantidad          INTEGER,
    INOUT p_ok  SMALLINT,
    INOUT p_msg VARCHAR(200),
    INOUT p_id  INTEGER
)
LANGUAGE plpgsql AS $$
DECLARE
    v_centro_origen_id INTEGER;
    v_lote_id          INTEGER;
    v_stock_actual     INTEGER;
    v_nuevo_inv_id     INTEGER;
BEGIN
    IF p_cantidad <= 0 THEN
        p_ok := 0; p_msg := 'La cantidad debe ser mayor a cero.'; RETURN;
    END IF;

    SELECT centro_id, lote_id, inventario_stock_actual
    INTO   v_centro_origen_id, v_lote_id, v_stock_actual
    FROM   inventarios
    WHERE  inventario_id = p_inv_origen_id
      AND  inventario_activo_desde IS NOT NULL;

    IF NOT FOUND THEN
        p_ok := 0; p_msg := 'El inventario de origen no existe o no está activo.'; RETURN;
    END IF;

    IF p_centro_destino_id = v_centro_origen_id THEN
        p_ok := 0; p_msg := 'El centro de destino debe ser diferente al de origen.'; RETURN;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM centros_salud WHERE centro_id = p_centro_destino_id) THEN
        p_ok := 0; p_msg := 'El centro de destino no existe.'; RETURN;
    END IF;

    IF p_cantidad > v_stock_actual THEN
        p_ok := 0;
        p_msg := 'La cantidad a transferir (' || p_cantidad || ') supera el stock disponible (' || v_stock_actual || ').';
        RETURN;
    END IF;

    -- Descontar del origen
    UPDATE inventarios
    SET    inventario_stock_actual = inventario_stock_actual - p_cantidad
    WHERE  inventario_id = p_inv_origen_id;

    -- Crear inventario destino (pendiente de confirmación)
    INSERT INTO inventarios(
        centro_id, lote_id,
        inventario_stock_inicial, inventario_stock_actual,
        inventario_activo_desde, usuario_id, inventario_origen_id
    ) VALUES (
        p_centro_destino_id, v_lote_id,
        p_cantidad, p_cantidad,
        NULL, NULL, p_inv_origen_id
    ) RETURNING inventario_id INTO v_nuevo_inv_id;

    -- Registrar transferencia
    INSERT INTO transferencias_inventario(inv_origen_id, inv_destino_id)
    VALUES (p_inv_origen_id, v_nuevo_inv_id);

    p_ok  := 1;
    p_msg := 'Transferencia registrada. El responsable del centro destino debe confirmar la recepción.';
    p_id  := v_nuevo_inv_id;
END; $$;

-- Permisos
GRANT SELECT ON vw_transferencias TO vacunatrack_user;
GRANT EXECUTE ON PROCEDURE sp_listar_transferencias(REFCURSOR) TO vacunatrack_user;
GRANT EXECUTE ON PROCEDURE sp_transferir_inventario(INTEGER, INTEGER, INTEGER, SMALLINT, VARCHAR, INTEGER) TO vacunatrack_user;

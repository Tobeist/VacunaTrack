-- ═════════════════════════════════════════════════════════════════
-- VacunaTrack — Mitigación de los 5 riesgos serios detectados
-- en la validación de los escenarios reales del profesor.
-- Aplicar DESPUÉS de vacunatrack_diaitc.sql y sps_nuevos_actualizar.txt.
-- ═════════════════════════════════════════════════════════════════


-- ─────────────────────────────────────────────────────────────────
-- RIESGO 1A — sp_transferir_inventario rechaza lotes caducados
-- ─────────────────────────────────────────────────────────────────

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
    v_caducidad        DATE;
    v_nuevo_inv_id     INTEGER;
BEGIN
    IF p_cantidad IS NULL OR p_cantidad <= 0 THEN
        p_ok := 0; p_msg := 'La cantidad debe ser mayor a cero.'; RETURN;
    END IF;

    SELECT i.centro_id, i.lote_id, i.inventario_stock_actual, l.lote_fecha_caducidad
    INTO   v_centro_origen_id, v_lote_id, v_stock_actual, v_caducidad
    FROM   inventarios i
    JOIN   lotes        l ON l.lote_id = i.lote_id
    WHERE  i.inventario_id = p_inv_origen_id
      AND  i.inventario_activo_desde IS NOT NULL;

    IF NOT FOUND THEN
        p_ok := 0; p_msg := 'El inventario de origen no existe o no está activo.'; RETURN;
    END IF;

    IF v_caducidad < CURRENT_DATE THEN
        p_ok := 0;
        p_msg := 'No se puede transferir: el lote caducó el ' || TO_CHAR(v_caducidad, 'DD/MM/YYYY') || '.';
        RETURN;
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

    UPDATE inventarios
    SET    inventario_stock_actual = inventario_stock_actual - p_cantidad
    WHERE  inventario_id = p_inv_origen_id;

    INSERT INTO inventarios(
        centro_id, lote_id,
        inventario_stock_inicial, inventario_stock_actual,
        inventario_activo_desde, usuario_id, inventario_origen_id
    ) VALUES (
        p_centro_destino_id, v_lote_id,
        p_cantidad, p_cantidad,
        NULL, NULL, p_inv_origen_id
    ) RETURNING inventario_id INTO v_nuevo_inv_id;

    INSERT INTO transferencias_inventario(inv_origen_id, inv_destino_id)
    VALUES (p_inv_origen_id, v_nuevo_inv_id);

    p_ok  := 1;
    p_msg := 'Transferencia registrada. El responsable del centro destino debe confirmar la recepción.';
    p_id  := v_nuevo_inv_id;
EXCEPTION
    WHEN OTHERS THEN
        p_ok := 0; p_msg := 'No se pudo completar la transferencia.';
END; $$;


-- ─────────────────────────────────────────────────────────────────
-- RIESGO 1B — Trigger que bloquea aplicaciones con lote caducado
-- Defensa en profundidad: aunque Python no valide, la DB rechaza.
-- ─────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION trg_validar_lote_caducidad()
RETURNS TRIGGER AS $$
DECLARE
    v_caducidad DATE;
BEGIN
    SELECT lote_fecha_caducidad INTO v_caducidad
    FROM   lotes WHERE lote_id = NEW.lote_id;

    IF v_caducidad IS NULL THEN
        RAISE EXCEPTION 'El lote no existe.';
    END IF;
    IF v_caducidad < NEW.aplicacion_timestamp::date THEN
        RAISE EXCEPTION
            'El lote caducó el %. No se puede aplicar una vacuna caducada.',
            TO_CHAR(v_caducidad, 'DD/MM/YYYY')
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_validar_lote_caducidad ON aplicaciones;
CREATE TRIGGER trg_validar_lote_caducidad
BEFORE INSERT ON aplicaciones
FOR EACH ROW
EXECUTE FUNCTION trg_validar_lote_caducidad();


-- ─────────────────────────────────────────────────────────────────
-- RIESGO 2 — Alertas de inventario automáticas
-- (a) SP que recalcula alertas según el estado actual.
-- (b) Trigger que crea alertas AGOTADO / CERCA_AGOTAR al bajar stock.
-- ─────────────────────────────────────────────────────────────────

-- Umbral por defecto: 30 días para CERCA_CADUCAR, 20% para CERCA_AGOTAR.
CREATE OR REPLACE PROCEDURE sp_recalcular_alertas_inventario(
    IN  p_dias_caducidad INTEGER,
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(200)
)
LANGUAGE plpgsql AS $$
DECLARE
    v_total INTEGER := 0;
BEGIN
    IF p_dias_caducidad IS NULL THEN
        p_dias_caducidad := 30;
    END IF;
    -- Limpiamos alertas viejas para evitar duplicados acumulados.
    DELETE FROM alertas_inventario;

    -- CADUCADO
    INSERT INTO alertas_inventario(inventario_id, alerta_inv_tipo)
    SELECT i.inventario_id, 'CADUCADO'::tipo_alerta_inv
    FROM   inventarios i
    JOIN   lotes        l ON l.lote_id = i.lote_id
    WHERE  l.lote_fecha_caducidad < CURRENT_DATE
      AND  i.inventario_stock_actual > 0;
    GET DIAGNOSTICS v_total = ROW_COUNT;

    -- CERCA_CADUCAR
    INSERT INTO alertas_inventario(inventario_id, alerta_inv_tipo)
    SELECT i.inventario_id, 'CERCA_CADUCAR'::tipo_alerta_inv
    FROM   inventarios i
    JOIN   lotes        l ON l.lote_id = i.lote_id
    WHERE  l.lote_fecha_caducidad >= CURRENT_DATE
      AND  l.lote_fecha_caducidad <= CURRENT_DATE + p_dias_caducidad
      AND  i.inventario_stock_actual > 0;

    -- AGOTADO
    INSERT INTO alertas_inventario(inventario_id, alerta_inv_tipo)
    SELECT i.inventario_id, 'AGOTADO'::tipo_alerta_inv
    FROM   inventarios i
    WHERE  i.inventario_stock_actual = 0
      AND  i.inventario_activo_desde IS NOT NULL;

    -- CERCA_AGOTAR: < 20% del stock inicial
    INSERT INTO alertas_inventario(inventario_id, alerta_inv_tipo)
    SELECT i.inventario_id, 'CERCA_AGOTAR'::tipo_alerta_inv
    FROM   inventarios i
    WHERE  i.inventario_stock_inicial > 0
      AND  i.inventario_stock_actual > 0
      AND  (i.inventario_stock_actual::numeric / i.inventario_stock_inicial) < 0.20
      AND  i.inventario_activo_desde IS NOT NULL;

    p_ok := 1; p_msg := 'Alertas de inventario recalculadas correctamente.';
EXCEPTION
    WHEN OTHERS THEN p_ok := 0; p_msg := 'No se pudieron recalcular las alertas.';
END; $$;


-- Trigger reactivo: cuando baja el stock, generar alerta inmediata.
CREATE OR REPLACE FUNCTION trg_alerta_stock_inventario()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.inventario_stock_actual = 0
       AND (OLD.inventario_stock_actual IS NULL OR OLD.inventario_stock_actual > 0) THEN
        INSERT INTO alertas_inventario(inventario_id, alerta_inv_tipo)
        VALUES (NEW.inventario_id, 'AGOTADO');
    ELSIF NEW.inventario_stock_inicial > 0
       AND NEW.inventario_stock_actual > 0
       AND (NEW.inventario_stock_actual::numeric / NEW.inventario_stock_inicial) < 0.20
       AND (OLD.inventario_stock_actual::numeric / NULLIF(OLD.inventario_stock_inicial,0)) >= 0.20 THEN
        INSERT INTO alertas_inventario(inventario_id, alerta_inv_tipo)
        VALUES (NEW.inventario_id, 'CERCA_AGOTAR');
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_alerta_stock_inventario ON inventarios;
CREATE TRIGGER trg_alerta_stock_inventario
AFTER UPDATE OF inventario_stock_actual ON inventarios
FOR EACH ROW
EXECUTE FUNCTION trg_alerta_stock_inventario();


-- ─────────────────────────────────────────────────────────────────
-- RIESGO 3 — SP para registrar alertas de dosis-paciente
-- Se invoca desde Flask cuando se bloquea una aplicación.
-- ─────────────────────────────────────────────────────────────────

CREATE OR REPLACE PROCEDURE sp_registrar_alerta_dosis(
    IN  p_paciente_id INTEGER,
    IN  p_dosis_id    INTEGER,
    IN  p_tipo        VARCHAR(20),
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(200)
)
LANGUAGE plpgsql AS $$
DECLARE
    v_tipo tipo_alerta_dosis;
BEGIN
    BEGIN
        v_tipo := p_tipo::tipo_alerta_dosis;
    EXCEPTION
        WHEN invalid_text_representation THEN
            p_ok := 0;
            p_msg := 'Tipo de alerta inválido. Use: APLICABLE, ATRASADA, CERCA_LIMITE o FALTANTE.';
            RETURN;
    END;

    IF NOT EXISTS(SELECT 1 FROM pacientes WHERE paciente_id = p_paciente_id) THEN
        p_ok := 0; p_msg := 'Paciente no encontrado.'; RETURN;
    END IF;
    IF NOT EXISTS(SELECT 1 FROM dosis WHERE dosis_id = p_dosis_id) THEN
        p_ok := 0; p_msg := 'Dosis no encontrada.'; RETURN;
    END IF;

    INSERT INTO alertas_dosis_pacientes(paciente_id, dosis_id, alerta_dosis_pac_tipo)
    VALUES (p_paciente_id, p_dosis_id, v_tipo);

    p_ok := 1; p_msg := 'Alerta registrada.';
EXCEPTION
    WHEN OTHERS THEN p_ok := 0; p_msg := 'No se pudo registrar la alerta.';
END; $$;


-- ─────────────────────────────────────────────────────────────────
-- RIESGO 4 — vw_historial_vacunacion sin duplicados
-- Solo expone dosis del esquema actualmente asignado al paciente.
-- ─────────────────────────────────────────────────────────────────

CREATE OR REPLACE VIEW vw_historial_vacunacion AS
SELECT
    vde.dosis_id,
    vde.vacuna_id,
    vde.vacuna_nombre,
    vde.dosis_tipo,
    vde.dosis_cant_ml,
    vde.dosis_area_aplicacion,
    vde.dosis_edad_oportuna_dias,
    vde.dosis_intervalo_min_dias,
    vde.dosis_limite_edad_dias,
    vde.dosis_vigente_desde,
    vde.dosis_vigente_hasta,
    vde.esquema_id,
    vde.dosis_esq_id,
    p.paciente_id,
    a.aplicacion_id,
    a.aplicacion_timestamp,
    a.aplicacion_observaciones,
    INITCAP(u.usuario_prim_nombre) || ' ' || INITCAP(u.usuario_apellido_pat) AS responsable,
    cs.centro_nombre
FROM pacientes p
JOIN vw_dosis_esquemas_detalle vde ON vde.esquema_id = p.esquema_id
LEFT JOIN aplicaciones   a  ON a.dosis_id = vde.dosis_id AND a.paciente_id = p.paciente_id
LEFT JOIN usuarios       u  ON u.usuario_id = a.usuario_id
LEFT JOIN centros_salud  cs ON cs.centro_id = a.centro_id;


-- ─────────────────────────────────────────────────────────────────
-- RIESGO 5 — sp_resolver_conflicto preserva motivo histórico
-- 'mantener' ahora INSERTA fila nueva en lugar de sobreescribir.
-- ─────────────────────────────────────────────────────────────────

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
        p_ok := 0; p_msg := 'Paciente no encontrado.'; RETURN;
    END IF;

    IF p_accion = 'actualizar' THEN
        UPDATE pacientes SET esquema_id = p_esquema_nuevo_id
        WHERE  paciente_id = p_paciente_id;
        p_ok := 1; p_msg := 'Esquema del paciente actualizado al nuevo.';

    ELSIF p_accion = 'mantener' THEN
        -- Cierra la asignación vigente preservando su motivo original
        UPDATE esquemas_pacientes
        SET    esq_pac_hasta = CURRENT_DATE
        WHERE  paciente_id = p_paciente_id
          AND  esquema_id  = v_esquema_viejo_id
          AND  esq_pac_hasta IS NULL;

        -- Inserta nuevo registro de decisión (auditable)
        INSERT INTO esquemas_pacientes(paciente_id, esquema_id, esq_pac_motivo_cambio)
        VALUES (p_paciente_id, v_esquema_viejo_id,
                'Conflicto resuelto: paciente conserva esquema ' || v_esquema_viejo_id ||
                ' (rechazado migrar a ' || p_esquema_nuevo_id || ')');

        p_ok := 1; p_msg := 'Decisión registrada: paciente conserva su esquema actual.';

    ELSE
        p_ok := 0; p_msg := 'Acción inválida. Use "actualizar" o "mantener".';
    END IF;
EXCEPTION
    WHEN OTHERS THEN p_ok := 0; p_msg := 'No se pudo resolver el conflicto.';
END; $$;


-- ─────────────────────────────────────────────────────────────────
-- RIESGO menor — Sincronizar sequences desfasados
-- (cuando se hicieron INSERT con id explícito, el sequence quedó atrás).
-- ─────────────────────────────────────────────────────────────────

CREATE OR REPLACE PROCEDURE sp_resync_sequences(
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(200)
)
LANGUAGE plpgsql AS $$
DECLARE
    r RECORD;
    v_max BIGINT;
    v_seq TEXT;
BEGIN
    FOR r IN
        SELECT t.table_name, c.column_name
        FROM information_schema.tables t
        JOIN information_schema.columns c
          ON c.table_name = t.table_name
        WHERE t.table_schema = 'public'
          AND c.column_default LIKE 'nextval%'
    LOOP
        v_seq := pg_get_serial_sequence(r.table_name, r.column_name);
        IF v_seq IS NULL THEN CONTINUE; END IF;
        EXECUTE format('SELECT COALESCE(MAX(%I),0) FROM %I', r.column_name, r.table_name) INTO v_max;
        PERFORM setval(v_seq, GREATEST(v_max, 1), v_max > 0);
    END LOOP;
    p_ok := 1; p_msg := 'Sequences resincronizados.';
EXCEPTION
    WHEN OTHERS THEN p_ok := 0; p_msg := 'No se pudieron resincronizar los sequences.';
END; $$;


-- ─────────────────────────────────────────────────────────────────
-- RIESGO menor — sp_crear_relacion valida que el tutor esté activo
-- ─────────────────────────────────────────────────────────────────

CREATE OR REPLACE PROCEDURE sp_crear_relacion(
    IN  p_paciente_id INTEGER,
    IN  p_tutor_id    INTEGER,
    OUT p_ok  SMALLINT,
    OUT p_msg VARCHAR(200),
    OUT p_id  INTEGER
)
LANGUAGE plpgsql AS $$
DECLARE
    v_existe BOOLEAN;
    v_activo BOOLEAN;
    v_es_tutor BOOLEAN;
BEGIN
    IF NOT EXISTS(SELECT 1 FROM pacientes WHERE paciente_id = p_paciente_id) THEN
        p_ok := 0; p_msg := 'El paciente seleccionado no existe.'; RETURN;
    END IF;

    SELECT usuario_activo INTO v_activo
    FROM   usuarios WHERE usuario_id = p_tutor_id;

    IF NOT FOUND THEN
        p_ok := 0; p_msg := 'El tutor seleccionado no existe.'; RETURN;
    END IF;
    IF NOT v_activo THEN
        p_ok := 0; p_msg := 'El tutor está desactivado. Reactívalo antes de vincularlo a un paciente.'; RETURN;
    END IF;

    SELECT EXISTS(
        SELECT 1 FROM usuarios_roles ur
        JOIN   roles r ON r.rol_id = ur.rol_id
        WHERE  ur.usuario_id = p_tutor_id AND r.rol_nombre = 'tutor'
    ) INTO v_es_tutor;

    IF NOT v_es_tutor THEN
        p_ok := 0; p_msg := 'El usuario seleccionado no tiene rol de tutor.'; RETURN;
    END IF;

    IF EXISTS(SELECT 1 FROM pacientes_tutores
              WHERE paciente_id = p_paciente_id AND tutor_id = p_tutor_id) THEN
        p_ok := 0; p_msg := 'Esta relación paciente-tutor ya existe.'; RETURN;
    END IF;

    INSERT INTO pacientes_tutores(paciente_id, tutor_id)
    VALUES (p_paciente_id, p_tutor_id)
    RETURNING pac_tut_id INTO p_id;

    p_ok := 1; p_msg := 'Relación creada correctamente.';
EXCEPTION
    WHEN unique_violation THEN
        p_ok := 0; p_msg := 'Esta relación paciente-tutor ya existe.';
    WHEN OTHERS THEN
        p_ok := 0; p_msg := 'No se pudo crear la relación.';
END; $$;


-- ═════════════════════════════════════════════════════════════════
-- FIN DEL ARCHIVO
-- ═════════════════════════════════════════════════════════════════

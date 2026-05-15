-- ============================================================
-- PATCH: cambios acumulados desde la versión anterior
-- Aplica SOLO vistas y SPs nuevos/modificados.
-- Seguro de correr sobre BD existente (CREATE OR REPLACE).
-- Ejecutar: psql -U postgres -d vacunatrack -f patch_postgres.sql
-- ============================================================
\c vacunatrack;


CREATE OR REPLACE VIEW vw_cedulas AS
SELECT c.*,
    INITCAP(u.usuario_prim_nombre) || ' ' || INITCAP(u.usuario_apellido_pat) AS responsable_nombre,
    u.usuario_telefono  AS responsable_telefono,
    cs.centro_nombre
FROM cedulas   c
JOIN usuarios  u  ON u.usuario_id  = c.usuario_id
LEFT JOIN centros_salud cs ON cs.centro_id = u.centro_id;

CREATE OR REPLACE VIEW vw_dosis_esquemas AS
SELECT de.*,
    d.dosis_tipo,
    d.dosis_cant_ml,
    d.dosis_area_aplicacion,
    d.dosis_edad_oportuna_dias,
    d.dosis_intervalo_min_dias,
    d.dosis_limite_edad_dias,
    d.vacuna_id,
    v.vacuna_nombre,
    e.esquema_nombre
FROM dosis_esquemas de
JOIN dosis    d  ON d.dosis_id   = de.dosis_id
JOIN vacunas  v  ON v.vacuna_id  = d.vacuna_id
JOIN esquemas e  ON e.esquema_id = de.esquema_id;

CREATE OR REPLACE VIEW vw_vacunas AS
SELECT v.*,
    COUNT(DISTINCT vp.padecimiento_id)                                          AS total_padecimientos,
    COALESCE(STRING_AGG(p.padecimiento_nombre, ', ' ORDER BY p.padecimiento_nombre), '—') AS padecimientos,
    COUNT(DISTINCT a.aplicacion_id)                                             AS total_aplicaciones
FROM vacunas v
LEFT JOIN vacunas_padecimientos vp ON vp.vacuna_id       = v.vacuna_id
LEFT JOIN padecimientos         p  ON p.padecimiento_id  = vp.padecimiento_id
LEFT JOIN dosis                 d  ON d.vacuna_id         = v.vacuna_id
LEFT JOIN aplicaciones          a  ON a.dosis_id          = d.dosis_id
GROUP BY v.vacuna_id;

CREATE OR REPLACE VIEW vw_esquemas AS
SELECT e.*,
    COUNT(DISTINCT de.dosis_id)                                        AS total_dosis,
    COUNT(DISTINCT d.vacuna_id)                                        AS total_vacunas,
    COUNT(DISTINCT a.paciente_id)                                      AS total_pacientes
FROM esquemas e
LEFT JOIN dosis_esquemas de ON de.esquema_id  = e.esquema_id
LEFT JOIN dosis          d  ON d.dosis_id     = de.dosis_id
LEFT JOIN pacientes      pa ON pa.esquema_id  = e.esquema_id
LEFT JOIN aplicaciones   a  ON a.dosis_id     = de.dosis_id
GROUP BY e.esquema_id;

CREATE OR REPLACE VIEW vw_paises AS
SELECT p.*,
    COUNT(DISTINCT e.estado_id)  AS total_estados,
    COUNT(DISTINCT c.ciudad_id)  AS total_ciudades
FROM paises   p
LEFT JOIN estados   e ON e.pais_id   = p.pais_id
LEFT JOIN ciudades  c ON c.estado_id = e.estado_id
GROUP BY p.pais_id;

CREATE OR REPLACE VIEW vw_pacientes_por_tutor AS
SELECT
    p.paciente_id,
    p.paciente_prim_nombre,
    p.paciente_seg_nombre,
    p.paciente_apellido_pat,
    p.paciente_apellido_mat,
    p.paciente_curp,
    p.paciente_num_cert_nac,
    p.paciente_fecha_nac,
    p.paciente_sexo,
    p.paciente_nfc,
    p.paciente_imagen,
    p.esquema_id,
    e.esquema_nombre,
    pt.tutor_id,
    pt.pac_tut_id,
    INITCAP(u.usuario_prim_nombre) || ' ' || INITCAP(u.usuario_apellido_pat) AS tutor_nombre,
    u.usuario_telefono  AS tutor_telefono,
    l.login_correo      AS tutor_email
FROM pacientes          p
JOIN esquemas           e  ON e.esquema_id  = p.esquema_id
JOIN pacientes_tutores  pt ON pt.paciente_id = p.paciente_id
JOIN usuarios           u  ON u.usuario_id  = pt.tutor_id
JOIN login              l  ON l.usuario_id  = u.usuario_id;

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
    a.paciente_id,
    a.aplicacion_id,
    a.aplicacion_timestamp,
    a.aplicacion_observaciones,
    INITCAP(u.usuario_prim_nombre) || ' ' || INITCAP(u.usuario_apellido_pat) AS responsable,
    cs.centro_nombre
FROM vw_dosis_esquemas_detalle vde
LEFT JOIN aplicaciones   a  ON a.dosis_id    = vde.dosis_id
LEFT JOIN usuarios       u  ON u.usuario_id  = a.usuario_id
LEFT JOIN centros_salud  cs ON cs.centro_id  = a.centro_id;

CREATE OR REPLACE VIEW vw_centros_detalle AS
SELECT
    cs.*,
    ci.ciudad_nombre,
    e.estado_id,
    e.estado_nombre,
    pa.pais_id,
    pa.pais_nombre,
    COUNT(DISTINCT i.inventario_id)  AS total_inventarios,
    COUNT(DISTINCT a.aplicacion_id)  AS total_aplicaciones
FROM centros_salud cs
JOIN ciudades   ci ON ci.ciudad_id = cs.ciudad_id
JOIN estados    e  ON e.estado_id  = ci.estado_id
JOIN paises     pa ON pa.pais_id   = e.pais_id
LEFT JOIN inventarios   i ON i.centro_id = cs.centro_id
LEFT JOIN aplicaciones  a ON a.centro_id = cs.centro_id
GROUP BY cs.centro_id, ci.ciudad_nombre, e.estado_id, e.estado_nombre, pa.pais_id, pa.pais_nombre;

CREATE OR REPLACE VIEW vw_stats_dashboard AS
SELECT
    (SELECT COUNT(*) FROM vw_pacientes)    AS pacientes,
    (SELECT COUNT(*) FROM vw_tutores)      AS tutores,
    (SELECT COUNT(*) FROM vw_responsables) AS responsables,
    (SELECT COUNT(*) FROM vw_centros_detalle) AS centros,
    (SELECT COUNT(*) FROM vw_aplicaciones
     WHERE DATE(aplicacion_timestamp) = CURRENT_DATE) AS aplicaciones_hoy,
    (SELECT COUNT(*) FROM vw_alertas_inventario) AS alertas_inv,
    (SELECT COUNT(*) FROM vw_alertas_dosis)      AS alertas_dosis;

CREATE OR REPLACE PROCEDURE sp_vincular_vacuna_padecimiento(
    IN  p_vacuna_id       INTEGER,
    IN  p_padecimiento_id INTEGER,
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(150), OUT p_id INTEGER)
LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO vacunas_padecimientos(vacuna_id, padecimiento_id)
    VALUES(p_vacuna_id, p_padecimiento_id)
    RETURNING vac_pad_id INTO p_id;
    p_ok := 1; p_msg := 'Vínculo registrado';
EXCEPTION
    WHEN unique_violation THEN p_ok := 1; p_msg := 'Ya estaba vinculado'; p_id := NULL;
    WHEN OTHERS THEN p_ok := 0; p_msg := 'Error al vincular: ' || SQLERRM;
END; $$;

CREATE OR REPLACE PROCEDURE sp_pacientes_de_tutor(
    IN p_tutor_id INTEGER, INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
        SELECT * FROM vw_pacientes_por_tutor
        WHERE tutor_id = p_tutor_id
        ORDER BY paciente_apellido_pat, paciente_prim_nombre;
END; $$;

CREATE OR REPLACE PROCEDURE sp_historial_vacunacion_paciente(
    IN p_paciente_id INTEGER, IN p_esquema_id INTEGER, INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
        SELECT * FROM vw_historial_vacunacion
        WHERE esquema_id = p_esquema_id
          AND (paciente_id = p_paciente_id OR paciente_id IS NULL)
        ORDER BY vacuna_id, dosis_edad_oportuna_dias;
END; $$;

CREATE OR REPLACE PROCEDURE sp_listar_dosis_esquemas(INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
        SELECT * FROM vw_dosis_esquemas ORDER BY esquema_id, vacuna_nombre, dosis_edad_oportuna_dias;
END; $$;

CREATE OR REPLACE PROCEDURE sp_listar_centros(INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR SELECT * FROM vw_centros_detalle ORDER BY centro_nombre;
END; $$;

CREATE OR REPLACE PROCEDURE sp_obtener_centro(
    IN p_id INTEGER, INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR SELECT * FROM vw_centros_detalle WHERE centro_id = p_id;
END; $$;

CREATE OR REPLACE PROCEDURE sp_obtener_centro_por_beacon(
    IN p_beacon_id VARCHAR(100), INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR SELECT * FROM vw_centros_detalle WHERE centro_beacon = p_beacon_id;
END; $$;

CREATE OR REPLACE PROCEDURE sp_ranking_centros_actividad(
    IN  p_meses       INTEGER,        -- ventana de lookback en meses
    INOUT p_resultados REFCURSOR
)
LANGUAGE plpgsql AS $$
BEGIN
    -- Tabla temporal: conteos por centro
    CREATE TEMP TABLE tmp_ranking_centros ON COMMIT DROP AS
    SELECT
        cs.centro_id,
        cs.centro_nombre,
        ci.ciudad_nombre,
        COUNT(a.aplicacion_id)                                              AS total_aplicaciones,
        COUNT(a.aplicacion_id)
            FILTER (WHERE a.aplicacion_timestamp >= NOW() - (p_meses || ' months')::INTERVAL)
                                                                            AS aplicaciones_periodo,
        COUNT(DISTINCT a.paciente_id)                                       AS pacientes_atendidos,
        COUNT(DISTINCT DATE(a.aplicacion_timestamp))                        AS dias_con_actividad
    FROM centros_salud cs
    LEFT JOIN aplicaciones  a  ON a.centro_id  = cs.centro_id
    JOIN      ciudades      ci ON ci.ciudad_id  = cs.ciudad_id
    GROUP BY cs.centro_id, cs.centro_nombre, ci.ciudad_nombre;

    -- Cursor: agrega ranking y porcentaje sobre la tabla temporal
    OPEN p_resultados FOR
        SELECT *,
            RANK() OVER (ORDER BY aplicaciones_periodo DESC)            AS ranking,
            ROUND(100.0 * aplicaciones_periodo /
                NULLIF(SUM(aplicaciones_periodo) OVER (), 0), 2)        AS pct_del_total
        FROM tmp_ranking_centros
        ORDER BY aplicaciones_periodo DESC;
END; $$;

CREATE OR REPLACE PROCEDURE sp_reporte_cobertura_vacunal(
    IN  p_esquema_id   INTEGER,
    INOUT p_resultados REFCURSOR
)
LANGUAGE plpgsql AS $$
DECLARE
    v_total_pacientes INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_total_pacientes
    FROM pacientes WHERE esquema_id = p_esquema_id;

    -- Tabla temporal: aplicaciones por dosis del esquema
    CREATE TEMP TABLE tmp_cobertura ON COMMIT DROP AS
    SELECT
        v.vacuna_id,
        v.vacuna_nombre,
        d.dosis_id,
        d.dosis_tipo,
        d.dosis_edad_oportuna_dias,
        v_total_pacientes                                                   AS total_pacientes,
        COUNT(DISTINCT a.paciente_id)                                       AS pacientes_con_dosis,
        COUNT(a.aplicacion_id)                                              AS total_aplicaciones
    FROM dosis_esquemas de
    JOIN dosis        d  ON d.dosis_id   = de.dosis_id
    JOIN vacunas      v  ON v.vacuna_id  = d.vacuna_id
    LEFT JOIN aplicaciones a ON a.dosis_id = d.dosis_id
        AND a.paciente_id IN (
            SELECT paciente_id FROM pacientes WHERE esquema_id = p_esquema_id
        )
    WHERE de.esquema_id = p_esquema_id
    GROUP BY v.vacuna_id, v.vacuna_nombre, d.dosis_id, d.dosis_tipo, d.dosis_edad_oportuna_dias;

    -- Cursor: calcula porcentaje y clasifica nivel de cobertura
    OPEN p_resultados FOR
        SELECT *,
            ROUND(100.0 * pacientes_con_dosis / NULLIF(total_pacientes, 0), 2) AS pct_cobertura,
            CASE
                WHEN total_pacientes = 0                                                      THEN 'SIN_DATOS'
                WHEN ROUND(100.0 * pacientes_con_dosis / NULLIF(total_pacientes,0), 2) >= 80 THEN 'ALTA'
                WHEN ROUND(100.0 * pacientes_con_dosis / NULLIF(total_pacientes,0), 2) >= 50 THEN 'MEDIA'
                ELSE                                                                               'BAJA'
            END AS nivel_cobertura
        FROM tmp_cobertura
        ORDER BY vacuna_nombre, dosis_edad_oportuna_dias;
END; $$;

-- ─────────────────────────────────────────────────────────────────────────────
-- TRIGGER: validar edad del paciente para la dosis (BEFORE INSERT en aplicaciones)
-- Complementa trg_validar_intervalo_dosis, que sólo verifica el intervalo mínimo.
-- Este trigger verifica que el paciente tenga la edad mínima recomendada y que
-- no haya superado el límite de edad para la dosis.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION trg_fn_validar_edad_paciente_dosis()
RETURNS TRIGGER AS $$
DECLARE
    v_edad_oportuna INTEGER;
    v_limite_edad   INTEGER;
    v_fecha_nac     DATE;
    v_edad_dias     INTEGER;
BEGIN
    SELECT d.dosis_edad_oportuna_dias, d.dosis_limite_edad_dias
    INTO   v_edad_oportuna, v_limite_edad
    FROM   dosis d WHERE d.dosis_id = NEW.dosis_id;

    SELECT p.paciente_fecha_nac INTO v_fecha_nac
    FROM   pacientes p WHERE p.paciente_id = NEW.paciente_id;

    v_edad_dias := EXTRACT(DAY FROM NEW.aplicacion_timestamp - v_fecha_nac::TIMESTAMP)::INTEGER;

    IF v_edad_dias < v_edad_oportuna THEN
        RAISE EXCEPTION
            'El paciente tiene % días de vida. La edad mínima para esta dosis es % días.',
            v_edad_dias, v_edad_oportuna;
    END IF;

    IF v_limite_edad IS NOT NULL AND v_edad_dias >= v_limite_edad THEN
        RAISE EXCEPTION
            'El paciente tiene % días de vida y superó el límite de edad (% días) para esta dosis.',
            v_edad_dias, v_limite_edad;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_validar_edad_paciente_dosis ON aplicaciones;
CREATE TRIGGER trg_validar_edad_paciente_dosis
BEFORE INSERT ON aplicaciones
FOR EACH ROW
EXECUTE FUNCTION trg_fn_validar_edad_paciente_dosis();

-- ─────────────────────────────────────────────────────────────────────────────
-- TRIGGER: prevenir doble aplicación de la misma dosis al mismo paciente
-- Flask ya hace esta comprobación vía sp_dosis_ya_aplicada, pero sin restricción
-- en la BD cualquier acceso directo al SP sp_registrar_aplicacion podría duplicar.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION trg_fn_prevenir_doble_aplicacion()
RETURNS TRIGGER AS $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM aplicaciones
        WHERE paciente_id = NEW.paciente_id AND dosis_id = NEW.dosis_id
    ) THEN
        RAISE EXCEPTION
            'La dosis % ya fue registrada para el paciente %.',
            NEW.dosis_id, NEW.paciente_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_prevenir_doble_aplicacion ON aplicaciones;
CREATE TRIGGER trg_prevenir_doble_aplicacion
BEFORE INSERT ON aplicaciones
FOR EACH ROW
EXECUTE FUNCTION trg_fn_prevenir_doble_aplicacion();

-- ─────────────────────────────────────────────────────────────────────────────
-- TRIGGER: normalizar centro_beacon (trim + lowercase) al guardar un centro
-- Evita que "ABC123" y " abc123 " sean beacons distintos y el matching falle.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION trg_fn_normalizar_beacon()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.centro_beacon IS NOT NULL THEN
        NEW.centro_beacon := LOWER(TRIM(NEW.centro_beacon));
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_normalizar_beacon ON centros_salud;
CREATE TRIGGER trg_normalizar_beacon
BEFORE INSERT OR UPDATE OF centro_beacon ON centros_salud
FOR EACH ROW
EXECUTE FUNCTION trg_fn_normalizar_beacon();

-- ─────────────────────────────────────────────────────────────────────────────
-- TRIGGER: forzar lowercase en login_correo al guardar credenciales
-- Evita que "Usuario@correo.mx" y "usuario@correo.mx" sean cuentas distintas.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION trg_fn_email_lower()
RETURNS TRIGGER AS $$
BEGIN
    NEW.login_correo := LOWER(TRIM(NEW.login_correo));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_email_lower ON login;
CREATE TRIGGER trg_email_lower
BEFORE INSERT OR UPDATE OF login_correo ON login
FOR EACH ROW
EXECUTE FUNCTION trg_fn_email_lower();

-- ─────────────────────────────────────────────────────────────────────────────
-- SP: registrar evento GPS en PostgreSQL
-- La tabla eventos_gps existía pero nunca se escribía; Flask sólo usaba MongoDB.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE PROCEDURE sp_registrar_evento_gps(
    IN  p_tutor_id  INTEGER,
    IN  p_latitud   NUMERIC(11,8),
    IN  p_longitud  NUMERIC(11,8),
    OUT p_ok        SMALLINT,
    OUT p_msg       VARCHAR(150)
)
LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO eventos_gps(tutor_id, evento_latitud, evento_longitud)
    VALUES(p_tutor_id, p_latitud, p_longitud);
    p_ok := 1; p_msg := 'Evento GPS registrado';
EXCEPTION
    WHEN OTHERS THEN p_ok := 0; p_msg := SQLERRM;
END; $$;

CREATE OR REPLACE PROCEDURE sp_pacientes_dosis_urgentes(
    IN  p_centro_id   INTEGER,        -- NULL = todos los centros
    INOUT p_resultados REFCURSOR
)
LANGUAGE plpgsql AS $$
BEGIN
    -- Tabla temporal: dosis vencidas (pasó edad oportuna, no aplicada, sin exceder límite)
    CREATE TEMP TABLE tmp_urgencias ON COMMIT DROP AS
    SELECT
        p.paciente_id,
        INITCAP(p.paciente_prim_nombre) || ' ' || INITCAP(p.paciente_apellido_pat) AS paciente_nombre,
        p.paciente_fecha_nac,
        EXTRACT(DAY FROM NOW() - p.paciente_fecha_nac)::INTEGER                    AS edad_dias,
        v.vacuna_nombre,
        d.dosis_id,
        d.dosis_tipo,
        d.dosis_edad_oportuna_dias,
        d.dosis_limite_edad_dias,
        (EXTRACT(DAY FROM NOW() - p.paciente_fecha_nac)::INTEGER
            - d.dosis_edad_oportuna_dias)                                          AS dias_atraso,
        (d.dosis_limite_edad_dias
            - EXTRACT(DAY FROM NOW() - p.paciente_fecha_nac)::INTEGER)            AS dias_para_limite
    FROM pacientes       p
    JOIN dosis_esquemas  de ON de.esquema_id = p.esquema_id
    JOIN dosis           d  ON d.dosis_id    = de.dosis_id
    JOIN vacunas         v  ON v.vacuna_id   = d.vacuna_id
    -- La dosis no ha sido aplicada
    WHERE NOT EXISTS (
        SELECT 1 FROM aplicaciones a
        WHERE a.paciente_id = p.paciente_id AND a.dosis_id = d.dosis_id
    )
    -- El paciente ya superó la edad oportuna de la dosis
    AND EXTRACT(DAY FROM NOW() - p.paciente_fecha_nac) > d.dosis_edad_oportuna_dias
    -- La dosis aún está dentro del límite de edad (o no tiene límite)
    AND (d.dosis_limite_edad_dias IS NULL
         OR EXTRACT(DAY FROM NOW() - p.paciente_fecha_nac) <= d.dosis_limite_edad_dias)
    -- Filtro por centro (si se proporciona)
    AND (p_centro_id IS NULL OR EXISTS (
        SELECT 1 FROM aplicaciones a2
        WHERE a2.paciente_id = p.paciente_id AND a2.centro_id = p_centro_id
    ));

    -- Cursor: agrega nivel de urgencia y ranking sobre la tabla temporal
    OPEN p_resultados FOR
        SELECT *,
            CASE
                WHEN dias_atraso > 60              THEN 'CRITICO'
                WHEN dias_atraso BETWEEN 30 AND 60 THEN 'URGENTE'
                ELSE                                    'PENDIENTE'
            END                                                         AS nivel_urgencia,
            RANK() OVER (ORDER BY dias_atraso DESC)                     AS ranking_urgencia
        FROM tmp_urgencias
        ORDER BY dias_atraso DESC;
END; $$;


-- ─────────────────────────────────────────────────────────────────────────────
-- SP: Recalcular alertas de inventario — ahora usa vw_inventarios en lugar
-- de consultar las tablas base inventarios/lotes directamente.
-- ─────────────────────────────────────────────────────────────────────────────
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
    DELETE FROM alertas_inventario;

    INSERT INTO alertas_inventario(inventario_id, alerta_inv_tipo)
    SELECT inventario_id, 'CADUCADO'::tipo_alerta_inv
    FROM   vw_inventarios
    WHERE  lote_fecha_caducidad < CURRENT_DATE
      AND  inventario_stock_actual > 0;
    GET DIAGNOSTICS v_total = ROW_COUNT;

    INSERT INTO alertas_inventario(inventario_id, alerta_inv_tipo)
    SELECT inventario_id, 'CERCA_CADUCAR'::tipo_alerta_inv
    FROM   vw_inventarios
    WHERE  lote_fecha_caducidad >= CURRENT_DATE
      AND  lote_fecha_caducidad <= CURRENT_DATE + p_dias_caducidad
      AND  inventario_stock_actual > 0;

    INSERT INTO alertas_inventario(inventario_id, alerta_inv_tipo)
    SELECT inventario_id, 'AGOTADO'::tipo_alerta_inv
    FROM   vw_inventarios
    WHERE  inventario_stock_actual = 0
      AND  inventario_activo_desde IS NOT NULL;

    INSERT INTO alertas_inventario(inventario_id, alerta_inv_tipo)
    SELECT inventario_id, 'CERCA_AGOTAR'::tipo_alerta_inv
    FROM   vw_inventarios
    WHERE  inventario_stock_inicial > 0
      AND  inventario_stock_actual > 0
      AND  (inventario_stock_actual::numeric / inventario_stock_inicial) < 0.20
      AND  inventario_activo_desde IS NOT NULL;

    p_ok := 1; p_msg := 'Alertas de inventario recalculadas correctamente.';
EXCEPTION
    WHEN OTHERS THEN p_ok := 0; p_msg := 'No se pudieron recalcular las alertas.';
END; $$;


-- ─────────────────────────────────────────────────────────────────────────────
-- SP: KPIs generales del sistema (para panel de analítica)
-- Devuelve una sola fila con 20 indicadores clave.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE PROCEDURE sp_kpis_generales(
    INOUT p_resultados REFCURSOR
)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
    SELECT
        -- 1-3: Personas
        (SELECT COUNT(*) FROM vw_pacientes)                                                   AS total_pacientes,
        (SELECT COUNT(*) FROM vw_tutores)                                                     AS total_tutores,
        (SELECT COUNT(*) FROM vw_responsables)                                                AS total_responsables,
        -- 4-5: Centros
        (SELECT COUNT(*) FROM vw_centros_detalle)                                             AS total_centros,
        (SELECT COUNT(DISTINCT centro_id) FROM aplicaciones
         WHERE aplicacion_timestamp >= NOW() - INTERVAL '30 days')                            AS centros_activos_30d,
        -- 6-9: Aplicaciones
        (SELECT COUNT(*) FROM aplicaciones)                                                   AS total_aplicaciones,
        (SELECT COUNT(*) FROM aplicaciones
         WHERE DATE(aplicacion_timestamp) = CURRENT_DATE)                                     AS aplicaciones_hoy,
        (SELECT COUNT(*) FROM aplicaciones
         WHERE DATE_TRUNC('month', aplicacion_timestamp) = DATE_TRUNC('month', NOW()))        AS aplicaciones_mes,
        ROUND(
            (SELECT COUNT(*) FROM aplicaciones
             WHERE DATE_TRUNC('month', aplicacion_timestamp) = DATE_TRUNC('month', NOW()))
            ::NUMERIC
            / NULLIF(EXTRACT(DAY FROM NOW())::INTEGER, 0), 1)                                 AS promedio_diario_mes,
        -- 10-11: Cobertura y pacientes sin vacunar
        ROUND(
            (SELECT COUNT(DISTINCT paciente_id) FROM aplicaciones)::NUMERIC
            / NULLIF((SELECT COUNT(*) FROM pacientes), 0) * 100, 1)                           AS pct_cobertura_global,
        (SELECT COUNT(*) FROM pacientes p
         WHERE NOT EXISTS (SELECT 1 FROM aplicaciones a
                           WHERE a.paciente_id = p.paciente_id))                              AS pacientes_sin_aplicaciones,
        -- 12-14: Catálogo clínico
        (SELECT COUNT(*) FROM vacunas)                                                        AS total_vacunas,
        (SELECT COUNT(*) FROM esquemas)                                                       AS total_esquemas,
        (SELECT COUNT(*) FROM padecimientos)                                                  AS total_padecimientos,
        -- 15-17: Inventario / lotes
        (SELECT COUNT(DISTINCT inventario_id) FROM vw_inventarios
         WHERE inventario_stock_actual > 0
           AND lote_fecha_caducidad >= CURRENT_DATE)                                          AS lotes_activos,
        (SELECT COUNT(DISTINCT inventario_id) FROM vw_inventarios
         WHERE lote_fecha_caducidad BETWEEN CURRENT_DATE AND CURRENT_DATE + 30
           AND inventario_stock_actual > 0)                                                   AS lotes_por_caducar_30d,
        (SELECT COUNT(DISTINCT inventario_id) FROM vw_inventarios
         WHERE lote_fecha_caducidad < CURRENT_DATE
           AND inventario_stock_actual > 0)                                                   AS lotes_caducados_con_stock,
        -- 18-19: Alertas
        (SELECT COUNT(*) FROM vw_alertas_inventario)                                          AS total_alertas_inv,
        (SELECT COUNT(*) FROM vw_alertas_dosis)                                               AS total_alertas_dosis,
        -- 20: % centros activos en últimos 30 días
        ROUND(
            (SELECT COUNT(DISTINCT centro_id) FROM aplicaciones
             WHERE aplicacion_timestamp >= NOW() - INTERVAL '30 days')::NUMERIC
            / NULLIF((SELECT COUNT(*) FROM vw_centros_detalle), 0) * 100, 1)                  AS pct_centros_activos_30d;
END; $$;

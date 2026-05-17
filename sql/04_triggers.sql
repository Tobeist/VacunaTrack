-- ═════════════════════════════════════════════════════════════════════════════
-- VacunaTrack — 04_triggers.sql
-- Todas las funciones de trigger y sus CREATE TRIGGER correspondientes.
-- Versiones más recientes de triggers parchados ya están incorporadas aquí.
-- Ejecutar después de 01_schema.sql, 02_views.sql y 03_stored_procedures.sql:
--   psql -U vacunatrack_user -d vacunatrack -f 04_triggers.sql
-- ═════════════════════════════════════════════════════════════════════════════

\c vacunatrack


-- ═════════════════════════════════════════════════════════════════════════════
-- TABLA: pacientes
-- ═════════════════════════════════════════════════════════════════════════════

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. ASIGNAR ESQUEMA POR DEFECTO (BEFORE INSERT)
--    Si se intenta insertar un paciente sin esquema_id, asigna automáticamente
--    el esquema activo más reciente según esquema_fecha_vigencia.
--    Corre antes de trg_normalizar_curp (orden alfabético: a < n).
--    Fuente: patch_nuevos_triggers.sql
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION fn_asignar_esquema_default()
RETURNS TRIGGER AS $$
DECLARE
    v_esquema_id integer;
BEGIN
    IF NEW.esquema_id IS NULL THEN
        SELECT esquema_id INTO v_esquema_id
        FROM esquemas
        WHERE (esquema_vigente_hasta IS NULL OR esquema_vigente_hasta >= CURRENT_DATE)
        ORDER BY esquema_fecha_vigencia DESC
        LIMIT 1;

        IF v_esquema_id IS NULL THEN
            RAISE EXCEPTION 'No existe un esquema de vacunación activo para asignar por defecto.';
        END IF;

        NEW.esquema_id := v_esquema_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_asignar_esquema_default ON pacientes;
CREATE TRIGGER trg_asignar_esquema_default
BEFORE INSERT ON pacientes
FOR EACH ROW EXECUTE FUNCTION fn_asignar_esquema_default();


-- ─────────────────────────────────────────────────────────────────────────────
-- 2. NORMALIZAR CURP (BEFORE INSERT/UPDATE)
--    Elimina espacios y convierte a mayúsculas antes de persistir.
--    Corre en orden alfabético antes que trg_validar_curp.
--    Fuente: patch_nuevos_triggers.sql
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION fn_normalizar_curp()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.paciente_curp IS NOT NULL THEN
        NEW.paciente_curp := UPPER(TRIM(NEW.paciente_curp));
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_normalizar_curp ON pacientes;
CREATE TRIGGER trg_normalizar_curp
BEFORE INSERT OR UPDATE OF paciente_curp ON pacientes
FOR EACH ROW EXECUTE FUNCTION fn_normalizar_curp();


-- ─────────────────────────────────────────────────────────────────────────────
-- 3. VALIDAR CURP (BEFORE INSERT/UPDATE)
--    Verifica que el CURP cumpla el formato oficial mexicano de 18 caracteres.
--    Corre después de trg_normalizar_curp (orden alfabético: n < v).
--    Fuente: patch_nuevos_triggers.sql
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION fn_validar_curp()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.paciente_curp IS NOT NULL
       AND NEW.paciente_curp !~ '^[A-Z]{4}[0-9]{6}[HM][A-Z]{5}[0-9A-Z]{2}$'
    THEN
        RAISE EXCEPTION 'CURP inválida: el valor "%" no corresponde al formato estándar mexicano (18 caracteres).',
            NEW.paciente_curp;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_validar_curp ON pacientes;
CREATE TRIGGER trg_validar_curp
BEFORE INSERT OR UPDATE OF paciente_curp ON pacientes
FOR EACH ROW EXECUTE FUNCTION fn_validar_curp();


-- ─────────────────────────────────────────────────────────────────────────────
-- 4. VALIDAR FECHA DE NACIMIENTO (BEFORE INSERT/UPDATE)
--    La tabla ya tiene CHECK (paciente_fecha_nac <= current_date).
--    Este trigger agrega la cota inferior: no más de 120 años atrás.
--    Fuente: patch_nuevos_triggers.sql
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION fn_validar_fecha_nac()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.paciente_fecha_nac < (CURRENT_DATE - INTERVAL '120 years') THEN
        RAISE EXCEPTION 'Fecha de nacimiento inválida: % supera el límite de 120 años.',
            NEW.paciente_fecha_nac;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_validar_fecha_nac ON pacientes;
CREATE TRIGGER trg_validar_fecha_nac
BEFORE INSERT OR UPDATE OF paciente_fecha_nac ON pacientes
FOR EACH ROW EXECUTE FUNCTION fn_validar_fecha_nac();


-- ─────────────────────────────────────────────────────────────────────────────
-- 5. NORMALIZAR NOMBRES DE PACIENTE (BEFORE INSERT/UPDATE)
--    Convierte nombres y apellidos a minúsculas con trim.
--    Fuente: vacunatrack_diaitc.sql
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION trg_normalizar_nombres_paciente()
RETURNS TRIGGER AS $$
BEGIN
    NEW.paciente_prim_nombre  := LOWER(TRIM(NEW.paciente_prim_nombre));
    NEW.paciente_seg_nombre   := LOWER(TRIM(NEW.paciente_seg_nombre));
    NEW.paciente_apellido_pat := LOWER(TRIM(NEW.paciente_apellido_pat));
    NEW.paciente_apellido_mat := LOWER(TRIM(NEW.paciente_apellido_mat));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_normalizar_nombres_paciente ON pacientes;
CREATE TRIGGER trg_normalizar_nombres_paciente
BEFORE INSERT OR UPDATE ON pacientes
FOR EACH ROW
EXECUTE FUNCTION trg_normalizar_nombres_paciente();


-- ─────────────────────────────────────────────────────────────────────────────
-- 6. HISTORIAL AUTOMÁTICO DE ASIGNACIÓN DE ESQUEMA (AFTER INSERT/UPDATE)
--    Registra en esquemas_pacientes cada vez que se asigna o cambia
--    el esquema de un paciente.
--    Fuente: vacunatrack_diaitc.sql
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION trg_registrar_historial_esquema()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP='INSERT' THEN
        INSERT INTO esquemas_pacientes(paciente_id,esquema_id,esq_pac_desde,esq_pac_motivo_cambio)
        VALUES(NEW.paciente_id,NEW.esquema_id,current_date,'Asignación inicial al registrar paciente');

    ELSIF TG_OP='UPDATE' AND OLD.esquema_id IS DISTINCT FROM NEW.esquema_id THEN
        UPDATE esquemas_pacientes
        SET esq_pac_hasta=current_date
        WHERE paciente_id=OLD.paciente_id
        AND esquema_id=OLD.esquema_id
        AND esq_pac_hasta IS NULL;

        INSERT INTO esquemas_pacientes(paciente_id,esquema_id,esq_pac_desde,esq_pac_motivo_cambio)
        VALUES(NEW.paciente_id,NEW.esquema_id,current_date,'Cambio de esquema nacional vigente');
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_historial_esquema ON pacientes;
CREATE TRIGGER trg_historial_esquema
AFTER INSERT OR UPDATE OF esquema_id ON pacientes
FOR EACH ROW
EXECUTE FUNCTION trg_registrar_historial_esquema();


-- ═════════════════════════════════════════════════════════════════════════════
-- TABLA: usuarios
-- ═════════════════════════════════════════════════════════════════════════════

-- ─────────────────────────────────────────────────────────────────────────────
-- 7. NORMALIZAR RFC (BEFORE INSERT/UPDATE)
--    Elimina espacios y convierte a mayúsculas antes de persistir.
--    Corre en orden alfabético antes que trg_validar_rfc.
--    Fuente: patch_nuevos_triggers.sql
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION fn_normalizar_rfc()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.usuario_rfc IS NOT NULL THEN
        NEW.usuario_rfc := UPPER(TRIM(NEW.usuario_rfc));
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_normalizar_rfc ON usuarios;
CREATE TRIGGER trg_normalizar_rfc
BEFORE INSERT OR UPDATE OF usuario_rfc ON usuarios
FOR EACH ROW EXECUTE FUNCTION fn_normalizar_rfc();


-- ─────────────────────────────────────────────────────────────────────────────
-- 8. VALIDAR RFC (BEFORE INSERT/UPDATE)
--    Persona física:  13 chars — 4 letras + 6 dígitos (fecha) + 3 homoclave.
--    Persona moral:   12 chars — 3 letras + 6 dígitos (fecha) + 3 homoclave.
--    Corre después de trg_normalizar_rfc (orden alfabético: n < v).
--    Fuente: patch_nuevos_triggers.sql
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION fn_validar_rfc()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.usuario_rfc IS NOT NULL
       AND NEW.usuario_rfc !~ '^([A-ZÑ&]{3,4})[0-9]{6}[A-Z0-9]{3}$'
    THEN
        RAISE EXCEPTION 'RFC inválido: el valor "%" no corresponde al formato estándar mexicano (12 o 13 caracteres).',
            NEW.usuario_rfc;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_validar_rfc ON usuarios;
CREATE TRIGGER trg_validar_rfc
BEFORE INSERT OR UPDATE OF usuario_rfc ON usuarios
FOR EACH ROW EXECUTE FUNCTION fn_validar_rfc();


-- ─────────────────────────────────────────────────────────────────────────────
-- 9. NORMALIZAR NOMBRES DE USUARIO (BEFORE INSERT/UPDATE)
--    Convierte nombres y apellidos a minúsculas con trim.
--    Fuente: vacunatrack_diaitc.sql
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION trg_normalizar_nombres_usuario()
RETURNS TRIGGER AS $$
BEGIN
    NEW.usuario_prim_nombre  := LOWER(TRIM(NEW.usuario_prim_nombre));
    NEW.usuario_seg_nombre   := LOWER(TRIM(NEW.usuario_seg_nombre));
    NEW.usuario_apellido_pat := LOWER(TRIM(NEW.usuario_apellido_pat));
    NEW.usuario_apellido_mat := LOWER(TRIM(NEW.usuario_apellido_mat));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_normalizar_nombres_usuario ON usuarios;
CREATE TRIGGER trg_normalizar_nombres_usuario
BEFORE INSERT OR UPDATE ON usuarios
FOR EACH ROW
EXECUTE FUNCTION trg_normalizar_nombres_usuario();


-- ═════════════════════════════════════════════════════════════════════════════
-- TABLA: login
-- ═════════════════════════════════════════════════════════════════════════════

-- ─────────────────────────────────────────────────────────────────────────────
-- 10. FORZAR LOWERCASE EN login_correo (BEFORE INSERT/UPDATE)
--     Evita que "Usuario@correo.mx" y "usuario@correo.mx" sean cuentas distintas.
--     Fuente: patch_postgres.sql
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


-- ═════════════════════════════════════════════════════════════════════════════
-- TABLA: centros_salud
-- ═════════════════════════════════════════════════════════════════════════════

-- ─────────────────────────────────────────────────────────────────────────────
-- 11. NORMALIZAR centro_beacon (BEFORE INSERT/UPDATE)
--     Trim + lowercase al guardar un centro.
--     Evita que "ABC123" y " abc123 " sean beacons distintos y el matching falle.
--     Fuente: patch_postgres.sql
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


-- ═════════════════════════════════════════════════════════════════════════════
-- TABLA: lotes
-- ═════════════════════════════════════════════════════════════════════════════

-- ─────────────────────────────────────────────────────────────────────────────
-- 12. BLOQUEAR ELIMINACIÓN DE LOTE CON STOCK (BEFORE DELETE)
--     Previene borrar un lote que aún tiene unidades en algún inventario,
--     evitando inconsistencias de stock.
--     Fuente: patch_nuevos_triggers.sql
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION fn_bloquear_eliminar_lote_con_stock()
RETURNS TRIGGER AS $$
DECLARE
    v_stock integer;
BEGIN
    SELECT COALESCE(SUM(inventario_stock_actual), 0) INTO v_stock
    FROM   inventarios
    WHERE  lote_id = OLD.lote_id;

    IF v_stock > 0 THEN
        RAISE EXCEPTION 'No se puede eliminar el lote %: tiene % unidades distribuidas en inventario.',
            OLD.lote_codigo, v_stock;
    END IF;
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_bloquear_eliminar_lote_con_stock ON lotes;
CREATE TRIGGER trg_bloquear_eliminar_lote_con_stock
BEFORE DELETE ON lotes
FOR EACH ROW EXECUTE FUNCTION fn_bloquear_eliminar_lote_con_stock();


-- ═════════════════════════════════════════════════════════════════════════════
-- TABLA: inventarios
-- ═════════════════════════════════════════════════════════════════════════════

-- ─────────────────────────────────────────────────────────────────────────────
-- 13. VALIDAR LOTE CADUCADO EN INVENTARIO (AFTER INSERT/UPDATE)
--     Defensa en profundidad: aunque Python no valide, la BD rechaza
--     movimientos de stock sobre lotes caducados.
--     Fuente: sps_riesgos_serios.sql (RIESGO 1B)
-- ─────────────────────────────────────────────────────────────────────────────

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


-- ─────────────────────────────────────────────────────────────────────────────
-- 14. ALERTAS DE STOCK AUTOMÁTICAS EN INVENTARIO (AFTER INSERT/UPDATE)
--     Trigger reactivo: cuando baja el stock, genera alerta inmediata
--     de tipo AGOTADO o CERCA_AGOTAR según umbrales.
--     Fuente: sps_riesgos_serios.sql (RIESGO 2)
-- ─────────────────────────────────────────────────────────────────────────────

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


-- ═════════════════════════════════════════════════════════════════════════════
-- TABLA: aplicaciones
-- ═════════════════════════════════════════════════════════════════════════════

-- ─────────────────────────────────────────────────────────────────────────────
-- 15. BLOQUEAR LOTE CADUCADO AL REGISTRAR APLICACIÓN (BEFORE INSERT)
--     Impide registrar una aplicación si la fecha de caducidad del lote
--     ya pasó al momento del INSERT.
--     Fuente: patch_nuevos_triggers.sql
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION fn_bloquear_lote_caducado()
RETURNS TRIGGER AS $$
DECLARE
    v_caducidad date;
    v_codigo    varchar(50);
BEGIN
    SELECT lote_fecha_caducidad, lote_codigo
    INTO   v_caducidad, v_codigo
    FROM   lotes
    WHERE  lote_id = NEW.lote_id;

    IF v_caducidad < CURRENT_DATE THEN
        RAISE EXCEPTION 'No se puede registrar la aplicación: el lote % caducó el %.',
            v_codigo, v_caducidad;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_bloquear_lote_caducado ON aplicaciones;
CREATE TRIGGER trg_bloquear_lote_caducado
BEFORE INSERT ON aplicaciones
FOR EACH ROW EXECUTE FUNCTION fn_bloquear_lote_caducado();


-- ─────────────────────────────────────────────────────────────────────────────
-- 16. VALIDAR EDAD DEL PACIENTE PARA LA DOSIS (BEFORE INSERT)
--     Complementa trg_validar_intervalo_dosis, que sólo verifica el intervalo
--     mínimo. Este trigger verifica que el paciente tenga la edad mínima
--     recomendada y que no haya superado el límite de edad para la dosis.
--     Fuente: patch_postgres.sql
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
-- 17. PREVENIR DOBLE APLICACIÓN DE LA MISMA DOSIS (BEFORE INSERT)
--     Flask ya hace esta comprobación vía sp_dosis_ya_aplicada, pero sin
--     restricción en la BD cualquier acceso directo podría duplicar.
--     Fuente: patch_postgres.sql
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
-- 18. VALIDAR INTERVALO MÍNIMO ENTRE DOSIS (BEFORE INSERT)
--     Verifica que hayan transcurrido los días mínimos requeridos entre
--     aplicaciones de la misma vacuna para un paciente.
--     Fuente: vacunatrack_diaitc.sql
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION trg_validar_intervalo_dosis()
RETURNS TRIGGER AS $$
DECLARE
    v_intervalo_min integer;
    v_vacuna_id integer;
    v_ultima_app timestamp;
    v_dias_desde integer;
BEGIN
    SELECT d.dosis_intervalo_min_dias,d.vacuna_id
    INTO v_intervalo_min,v_vacuna_id
    FROM dosis d
    WHERE d.dosis_id=NEW.dosis_id;

    IF v_intervalo_min IS NULL OR v_intervalo_min=0 THEN
        RETURN NEW;
    END IF;

    SELECT MAX(a.aplicacion_timestamp)
    INTO v_ultima_app
    FROM aplicaciones a
    JOIN dosis d ON a.dosis_id=d.dosis_id
    WHERE a.paciente_id=NEW.paciente_id
    AND d.vacuna_id=v_vacuna_id;

    IF v_ultima_app IS NOT NULL THEN
        v_dias_desde:=EXTRACT(DAY FROM (NEW.aplicacion_timestamp-v_ultima_app))::integer;
        IF v_dias_desde<v_intervalo_min THEN
            RAISE EXCEPTION
                'Intervalo mínimo no cumplido: han transcurrido % días desde la última '
                'dosis de esta vacuna, pero se requieren al menos % días. Faltan % días.',
                v_dias_desde,v_intervalo_min,(v_intervalo_min-v_dias_desde);
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_validar_intervalo_dosis ON aplicaciones;
CREATE TRIGGER trg_validar_intervalo_dosis
BEFORE INSERT ON aplicaciones
FOR EACH ROW
EXECUTE FUNCTION trg_validar_intervalo_dosis();


-- ─────────────────────────────────────────────────────────────────────────────
-- 19. DESCUENTO AUTOMÁTICO DE INVENTARIO AL APLICAR VACUNA (AFTER INSERT)
--     Selecciona el inventario activo más reciente con stock disponible para
--     el lote y centro especificados, excluyendo lotes caducados.
--     VERSIÓN MÁS RECIENTE: patch_caducidad.sql (reemplaza vacunatrack_diaitc.sql).
-- ─────────────────────────────────────────────────────────────────────────────

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

DROP TRIGGER IF EXISTS trg_descontar_inventario ON aplicaciones;
CREATE TRIGGER trg_descontar_inventario
AFTER INSERT ON aplicaciones
FOR EACH ROW
EXECUTE FUNCTION trg_descontar_inventario();


-- ─────────────────────────────────────────────────────────────────────────────
-- 20. RESTAURAR STOCK AL ELIMINAR APLICACIÓN (AFTER DELETE)
--     Espejo de trg_descontar_inventario: al borrar una aplicación devuelve
--     la unidad al inventario activo correspondiente al lote y centro.
--     Fuente: patch_nuevos_triggers.sql
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION fn_restaurar_stock()
RETURNS TRIGGER AS $$
DECLARE
    v_inventario_id integer;
BEGIN
    SELECT inventario_id INTO v_inventario_id
    FROM   inventarios
    WHERE  lote_id                = OLD.lote_id
      AND  centro_id              = OLD.centro_id
      AND  inventario_activo_desde IS NOT NULL
    ORDER BY inventario_activo_desde DESC
    LIMIT 1;

    IF v_inventario_id IS NOT NULL THEN
        UPDATE inventarios
        SET    inventario_stock_actual = inventario_stock_actual + 1
        WHERE  inventario_id = v_inventario_id;
    END IF;

    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_restaurar_stock ON aplicaciones;
CREATE TRIGGER trg_restaurar_stock
AFTER DELETE ON aplicaciones
FOR EACH ROW EXECUTE FUNCTION fn_restaurar_stock();


-- ═════════════════════════════════════════════════════════════════════════════
-- OWNERSHIP — transferir todas las funciones de trigger a vacunatrack_user
-- ═════════════════════════════════════════════════════════════════════════════
DO $$
DECLARE r RECORD;
BEGIN
    FOR r IN
        SELECT p.oid::regprocedure::text AS sig
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public'
    LOOP
        BEGIN
            EXECUTE 'ALTER ROUTINE ' || r.sig || ' OWNER TO vacunatrack_user';
        EXCEPTION WHEN OTHERS THEN NULL;
        END;
    END LOOP;
END $$;

-- ═══════════════════════════════════════════════════════════════════════════
-- patch_nuevos_triggers.sql
-- Nuevos triggers de integridad, negocio y automatización
-- ═══════════════════════════════════════════════════════════════════════════

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. NORMALIZAR CURP (pacientes)
--    Elimina espacios y convierte a mayúsculas antes de persistir.
--    Corre en orden alfabético antes que trg_validar_curp.
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

CREATE TRIGGER trg_normalizar_curp
BEFORE INSERT OR UPDATE OF paciente_curp ON pacientes
FOR EACH ROW EXECUTE FUNCTION fn_normalizar_curp();

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. VALIDAR CURP (pacientes)
--    Verifica que el CURP cumpla el formato oficial mexicano de 18 caracteres.
--    Corre después de trg_normalizar_curp (orden alfabético: n < v).
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

CREATE TRIGGER trg_validar_curp
BEFORE INSERT OR UPDATE OF paciente_curp ON pacientes
FOR EACH ROW EXECUTE FUNCTION fn_validar_curp();

-- ─────────────────────────────────────────────────────────────────────────────
-- 3. VALIDAR FECHA DE NACIMIENTO (pacientes)
--    La tabla ya tiene CHECK (paciente_fecha_nac <= current_date).
--    Este trigger agrega la cota inferior: no más de 120 años atrás.
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

CREATE TRIGGER trg_validar_fecha_nac
BEFORE INSERT OR UPDATE OF paciente_fecha_nac ON pacientes
FOR EACH ROW EXECUTE FUNCTION fn_validar_fecha_nac();

-- ─────────────────────────────────────────────────────────────────────────────
-- 4. ASIGNAR ESQUEMA POR DEFECTO (pacientes)
--    Si se intenta insertar un paciente sin esquema_id, asigna automáticamente
--    el esquema activo más reciente según esquema_fecha_vigencia.
--    Corre antes de trg_normalizar_curp (orden: a < n).
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

CREATE TRIGGER trg_asignar_esquema_default
BEFORE INSERT ON pacientes
FOR EACH ROW EXECUTE FUNCTION fn_asignar_esquema_default();

-- ─────────────────────────────────────────────────────────────────────────────
-- 5. BLOQUEAR LOTE CADUCADO AL REGISTRAR APLICACIÓN (aplicaciones)
--    Impide registrar una aplicación si la fecha de caducidad del lote
--    ya pasó al momento del INSERT.
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

CREATE TRIGGER trg_bloquear_lote_caducado
BEFORE INSERT ON aplicaciones
FOR EACH ROW EXECUTE FUNCTION fn_bloquear_lote_caducado();

-- ─────────────────────────────────────────────────────────────────────────────
-- 6. RESTAURAR STOCK AL ELIMINAR APLICACIÓN (aplicaciones)
--    Espejo de trg_descontar_inventario: al borrar una aplicación devuelve
--    la unidad al inventario activo correspondiente al lote y centro.
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

CREATE TRIGGER trg_restaurar_stock
AFTER DELETE ON aplicaciones
FOR EACH ROW EXECUTE FUNCTION fn_restaurar_stock();

-- ─────────────────────────────────────────────────────────────────────────────
-- 7. BLOQUEAR ELIMINACIÓN DE LOTE CON STOCK (lotes)
--    Previene borrar un lote que aún tiene unidades en algún inventario,
--    evitando inconsistencias de stock.
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

CREATE TRIGGER trg_bloquear_eliminar_lote_con_stock
BEFORE DELETE ON lotes
FOR EACH ROW EXECUTE FUNCTION fn_bloquear_eliminar_lote_con_stock();

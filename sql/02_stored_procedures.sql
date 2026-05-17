-- ═══════════════════════════════════════════════════════════════════════════
-- 02_stored_procedures.sql  —  VacunaTrack
-- Procedimientos almacenados (funciones no-trigger)
-- Ejecutar después de 01_schema.sql
-- ═══════════════════════════════════════════════════════════════════════════


-- ═══ AUTENTICACIÓN ═══

CREATE OR REPLACE PROCEDURE sp_buscar_usuario_por_email(
    IN p_email VARCHAR(150), INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
        SELECT usuario_id AS id, email, password,
               INITCAP(first_name) AS first_name,
               INITCAP(last_name)  AS last_name,
               role, activo
        FROM vw_usuarios_auth WHERE email = LOWER(TRIM(p_email))
        ORDER BY CASE role WHEN 'admin' THEN 0 WHEN 'responsable' THEN 1 ELSE 2 END
        LIMIT 1;
END; $$;

CREATE OR REPLACE PROCEDURE sp_cambiar_password(
    IN  p_usuario_id INTEGER, IN  p_nuevo_hash VARCHAR(255),
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(150))
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE login SET login_contrasena = p_nuevo_hash WHERE usuario_id = p_usuario_id;
    p_ok := 1; p_msg := 'Contraseña actualizada correctamente';
EXCEPTION
    WHEN OTHERS THEN p_ok := 0; p_msg := 'Error al actualizar contraseña: ' || SQLERRM;
END; $$;


-- ═══ USUARIOS — LECTURA ═══

-- patch_postgres.sql version (uses vw_usuarios_completo)
CREATE OR REPLACE PROCEDURE sp_listar_usuarios(INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
        SELECT * FROM vw_usuarios_completo
        ORDER BY usuario_apellido_pat, usuario_prim_nombre;
END; $$;

-- patch_postgres.sql version (uses vw_usuarios_completo)
CREATE OR REPLACE PROCEDURE sp_obtener_usuario(
    IN p_id INTEGER, INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR SELECT * FROM vw_usuarios_completo WHERE usuario_id = p_id;
END; $$;

CREATE OR REPLACE PROCEDURE sp_listar_administradores(INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
        SELECT * FROM vw_administradores ORDER BY admin_apellido_pat, admin_prim_nombre;
END; $$;

CREATE OR REPLACE PROCEDURE sp_obtener_administrador(
    IN p_id INTEGER, INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR SELECT * FROM vw_administradores WHERE admin_id = p_id;
END; $$;

CREATE OR REPLACE PROCEDURE sp_listar_tutores(INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
        SELECT * FROM vw_tutores ORDER BY tutor_apellido_pat, tutor_prim_nombre;
END; $$;

CREATE OR REPLACE PROCEDURE sp_obtener_tutor(
    IN p_id INTEGER, INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR SELECT * FROM vw_tutores WHERE tutor_id = p_id;
END; $$;

CREATE OR REPLACE PROCEDURE sp_listar_responsables(INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
        SELECT * FROM vw_responsables
        ORDER BY responsable_apellido_pat, responsable_prim_nombre;
END; $$;

CREATE OR REPLACE PROCEDURE sp_obtener_responsable(
    IN p_id INTEGER, INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR SELECT * FROM vw_responsables WHERE responsable_id = p_id;
END; $$;

CREATE OR REPLACE PROCEDURE sp_cedulas_de_responsable(
    IN p_usuario_id INTEGER, INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR SELECT * FROM vw_cedulas WHERE usuario_id = p_usuario_id;
END; $$;

-- patch_postgres.sql version
CREATE OR REPLACE PROCEDURE sp_roles_de_usuario(
    IN p_email VARCHAR, INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
    SELECT r.rol_nombre
    FROM   login          l
    JOIN   usuarios       u  ON u.usuario_id  = l.usuario_id
    JOIN   usuarios_roles ur ON ur.usuario_id = u.usuario_id
    JOIN   roles          r  ON r.rol_id      = ur.rol_id
    WHERE  l.login_correo = LOWER(TRIM(p_email))
    ORDER  BY CASE r.rol_nombre
                  WHEN 'admin'       THEN 0
                  WHEN 'responsable' THEN 1
                  ELSE 2
              END;
END; $$;

CREATE OR REPLACE PROCEDURE sp_obtener_cedula(
    IN p_id INTEGER, INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR SELECT * FROM vw_cedulas WHERE cedula_id = p_id;
END; $$;


-- ═══ USUARIOS — ESCRITURA ═══

-- Helper interno: inserta en usuarios + login + usuarios_roles.
-- Llamado por sp_crear_admin, sp_crear_tutor, sp_crear_responsable.
CREATE OR REPLACE PROCEDURE sp_crear_usuario_base(
    IN  p_prim_nombre   VARCHAR(100),
    IN  p_seg_nombre    VARCHAR(100),
    IN  p_apellido_pat  VARCHAR(100),
    IN  p_apellido_mat  VARCHAR(100),
    IN  p_telefono      VARCHAR(20),
    IN  p_curp          VARCHAR(18),
    IN  p_rfc           VARCHAR(13),
    IN  p_email         VARCHAR(150),
    IN  p_contrasena    VARCHAR(255),
    IN  p_centro_id     INTEGER,
    IN  p_rol           VARCHAR(50),
    OUT p_ok            SMALLINT,
    OUT p_msg           VARCHAR(150),
    OUT p_id            INTEGER
)
LANGUAGE plpgsql AS $$
DECLARE v_rol_id INTEGER;
BEGIN
    IF TRIM(COALESCE(p_prim_nombre,'')) = '' THEN
        p_ok := 0; p_msg := 'El nombre es requerido'; RETURN;
    END IF;
    IF TRIM(COALESCE(p_apellido_pat,'')) = '' THEN
        p_ok := 0; p_msg := 'El apellido paterno es requerido'; RETURN;
    END IF;
    IF TRIM(COALESCE(p_email,'')) = '' OR p_email NOT LIKE '%@%.%' THEN
        p_ok := 0; p_msg := 'El correo electrónico no es válido'; RETURN;
    END IF;
    IF TRIM(COALESCE(p_telefono,'')) = '' THEN
        p_ok := 0; p_msg := 'El teléfono es requerido'; RETURN;
    END IF;
    IF p_telefono !~ '^[0-9]{10}$' THEN
        p_ok := 0; p_msg := 'El teléfono debe tener exactamente 10 dígitos'; RETURN;
    END IF;
    IF TRIM(COALESCE(p_curp,'')) = '' THEN
        p_ok := 0; p_msg := 'La CURP es requerida'; RETURN;
    END IF;
    IF LENGTH(TRIM(p_curp)) != 18 THEN
        p_ok := 0; p_msg := 'La CURP debe tener exactamente 18 caracteres'; RETURN;
    END IF;
    IF UPPER(TRIM(p_curp)) !~ '^[A-Z]{4}[0-9]{6}[HM][A-Z]{5}[0-9A-Z][0-9]$' THEN
        p_ok := 0; p_msg := 'El formato de la CURP no es válido'; RETURN;
    END IF;
    IF p_rfc IS NOT NULL AND TRIM(p_rfc) != '' THEN
        IF UPPER(TRIM(p_rfc)) !~ '^[A-Z0-9&]{3,4}[0-9]{6}[A-Z0-9]{3}$' THEN
            p_ok := 0; p_msg := 'El formato del RFC no es válido'; RETURN;
        END IF;
    END IF;
    IF EXISTS(SELECT 1 FROM login WHERE login_correo = LOWER(TRIM(p_email))) THEN
        p_ok := 0; p_msg := 'El correo electrónico ya está registrado'; RETURN;
    END IF;
    IF EXISTS(SELECT 1 FROM usuarios WHERE usuario_curp = UPPER(TRIM(p_curp))) THEN
        p_ok := 0; p_msg := 'La CURP ya está registrada en el sistema'; RETURN;
    END IF;
    IF EXISTS(SELECT 1 FROM usuarios WHERE usuario_telefono = TRIM(p_telefono)) THEN
        p_ok := 0; p_msg := 'El número de teléfono ya está registrado'; RETURN;
    END IF;
    IF p_rfc IS NOT NULL AND TRIM(p_rfc) != '' AND
       EXISTS(SELECT 1 FROM usuarios WHERE usuario_rfc = UPPER(TRIM(p_rfc))) THEN
        p_ok := 0; p_msg := 'El RFC ya está registrado'; RETURN;
    END IF;

    INSERT INTO usuarios(usuario_prim_nombre, usuario_seg_nombre, usuario_apellido_pat,
        usuario_apellido_mat, usuario_telefono, usuario_curp, usuario_rfc, centro_id)
    VALUES(p_prim_nombre, p_seg_nombre, p_apellido_pat, p_apellido_mat,
           TRIM(p_telefono), UPPER(TRIM(p_curp)),
           CASE WHEN TRIM(COALESCE(p_rfc,''))='' THEN NULL ELSE UPPER(TRIM(p_rfc)) END,
           p_centro_id)
    RETURNING usuario_id INTO p_id;

    INSERT INTO login(usuario_id, login_correo, login_contrasena)
    VALUES(p_id, LOWER(TRIM(p_email)), p_contrasena);

    SELECT rol_id INTO v_rol_id FROM roles WHERE rol_nombre = p_rol;
    IF v_rol_id IS NOT NULL THEN
        INSERT INTO usuarios_roles(usuario_id, rol_id) VALUES(p_id, v_rol_id)
        ON CONFLICT DO NOTHING;
    END IF;

    p_ok := 1;
    p_msg := 'Usuario creado correctamente';
EXCEPTION
    WHEN unique_violation THEN
        p_ok := 0; p_msg := 'Ya existe un registro con esos datos (duplicado)';
    WHEN foreign_key_violation THEN
        p_ok := 0; p_msg := 'El centro de salud indicado no existe';
    WHEN OTHERS THEN
        p_ok := 0; p_msg := 'Error al crear usuario: ' || SQLERRM;
END; $$;

-- patch_postgres.sql version
CREATE OR REPLACE PROCEDURE sp_crear_usuario_unificado(
    IN  p_prim_nombre   VARCHAR(100),
    IN  p_seg_nombre    VARCHAR(100),
    IN  p_apellido_pat  VARCHAR(100),
    IN  p_apellido_mat  VARCHAR(100),
    IN  p_telefono      VARCHAR(20),
    IN  p_curp          VARCHAR(18),
    IN  p_rfc           VARCHAR(13),
    IN  p_email         VARCHAR(150),
    IN  p_contrasena    VARCHAR(255),
    IN  p_centro_id     INTEGER,
    IN  p_roles         TEXT[],
    IN  p_cedulas_nums  TEXT[],
    IN  p_cedulas_specs TEXT[],
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(200), OUT p_id INTEGER
)
LANGUAGE plpgsql AS $$
DECLARE
    v_rol_id INTEGER;
    v_i      INTEGER;
    v_ok     SMALLINT;
    v_msg    VARCHAR(200);
BEGIN
    IF p_roles IS NULL OR array_length(p_roles, 1) IS NULL THEN
        p_ok := 0; p_msg := 'Debes asignar al menos un rol'; RETURN;
    END IF;
    IF 'responsable' = ANY(p_roles) AND p_centro_id IS NULL THEN
        p_ok := 0; p_msg := 'Debes asignar un centro de salud para el rol responsable'; RETURN;
    END IF;
    IF ('admin' = ANY(p_roles) OR 'responsable' = ANY(p_roles))
       AND TRIM(COALESCE(p_rfc,'')) = '' THEN
        p_ok := 0; p_msg := 'El RFC es requerido para administradores y responsables'; RETURN;
    END IF;
    IF 'responsable' = ANY(p_roles)
       AND (p_cedulas_nums IS NULL OR array_length(p_cedulas_nums, 1) IS NULL) THEN
        p_ok := 0; p_msg := 'Debes registrar al menos una cédula profesional para responsables'; RETURN;
    END IF;

    CALL sp_crear_usuario_base(
        p_prim_nombre, p_seg_nombre, p_apellido_pat, p_apellido_mat,
        p_telefono, p_curp, p_rfc, p_email, p_contrasena,
        p_centro_id, p_roles[1],
        v_ok, v_msg, p_id
    );
    IF v_ok = 0 THEN p_ok := 0; p_msg := v_msg; RETURN; END IF;

    FOR v_i IN 2..array_length(p_roles, 1) LOOP
        SELECT rol_id INTO v_rol_id FROM roles WHERE rol_nombre = p_roles[v_i];
        IF v_rol_id IS NOT NULL THEN
            INSERT INTO usuarios_roles(usuario_id, rol_id) VALUES(p_id, v_rol_id)
            ON CONFLICT DO NOTHING;
        END IF;
    END LOOP;

    IF 'responsable' = ANY(p_roles) AND p_cedulas_nums IS NOT NULL THEN
        FOR v_i IN 1..array_length(p_cedulas_nums, 1) LOOP
            IF TRIM(COALESCE(p_cedulas_nums[v_i],'')) != '' THEN
                INSERT INTO cedulas(cedula_numero, cedula_especialidad, usuario_id)
                VALUES(TRIM(p_cedulas_nums[v_i]),
                       NULLIF(TRIM(COALESCE(p_cedulas_specs[v_i],'')), ''),
                       p_id)
                ON CONFLICT (cedula_numero) DO NOTHING;
            END IF;
        END LOOP;
    END IF;

    p_ok := 1; p_msg := 'Usuario creado correctamente';
EXCEPTION
    WHEN unique_violation THEN p_ok := 0; p_msg := 'Ya existe un registro con esos datos (duplicado)';
    WHEN OTHERS THEN p_ok := 0; p_msg := 'Error al crear usuario: ' || SQLERRM;
END; $$;

-- patch_postgres.sql version
CREATE OR REPLACE PROCEDURE sp_actualizar_usuario_unificado(
    IN  p_usuario_id    INTEGER,
    IN  p_prim_nombre   VARCHAR(100),
    IN  p_seg_nombre    VARCHAR(100),
    IN  p_apellido_pat  VARCHAR(100),
    IN  p_apellido_mat  VARCHAR(100),
    IN  p_telefono      VARCHAR(20),
    IN  p_curp          VARCHAR(18),
    IN  p_rfc           VARCHAR(13),
    IN  p_email         VARCHAR(150),
    IN  p_centro_id     INTEGER,
    IN  p_roles         TEXT[],
    IN  p_cedulas_nums  TEXT[],
    IN  p_cedulas_specs TEXT[],
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(200)
)
LANGUAGE plpgsql AS $$
DECLARE
    v_rol    TEXT;
    v_rol_id INTEGER;
    v_i      INTEGER;
BEGIN
    IF NOT EXISTS(SELECT 1 FROM usuarios WHERE usuario_id = p_usuario_id) THEN
        p_ok := 0; p_msg := 'Usuario no encontrado'; RETURN;
    END IF;
    IF p_roles IS NULL OR array_length(p_roles, 1) IS NULL THEN
        p_ok := 0; p_msg := 'Debes asignar al menos un rol'; RETURN;
    END IF;
    IF 'responsable' = ANY(p_roles) AND p_centro_id IS NULL THEN
        p_ok := 0; p_msg := 'Debes asignar un centro de salud para el rol responsable'; RETURN;
    END IF;
    IF ('admin' = ANY(p_roles) OR 'responsable' = ANY(p_roles))
       AND TRIM(COALESCE(p_rfc,'')) = '' THEN
        p_ok := 0; p_msg := 'El RFC es requerido para administradores y responsables'; RETURN;
    END IF;
    IF 'responsable' = ANY(p_roles)
       AND (p_cedulas_nums IS NULL OR array_length(p_cedulas_nums, 1) IS NULL) THEN
        p_ok := 0; p_msg := 'Debes registrar al menos una cédula profesional para responsables'; RETURN;
    END IF;
    IF p_telefono IS NOT NULL AND p_telefono !~ '^[0-9]{10}$' THEN
        p_ok := 0; p_msg := 'El teléfono debe tener exactamente 10 dígitos'; RETURN;
    END IF;
    IF p_curp IS NOT NULL AND LENGTH(TRIM(p_curp)) != 18 THEN
        p_ok := 0; p_msg := 'La CURP debe tener 18 caracteres'; RETURN;
    END IF;
    IF p_curp IS NOT NULL AND
       UPPER(TRIM(p_curp)) !~ '^[A-Z]{4}[0-9]{6}[HM][A-Z]{5}[0-9A-Z][0-9]$' THEN
        p_ok := 0; p_msg := 'El formato de la CURP no es válido'; RETURN;
    END IF;
    IF p_rfc IS NOT NULL AND TRIM(p_rfc) != '' AND
       UPPER(TRIM(p_rfc)) !~ '^[A-Z0-9&]{3,4}[0-9]{6}[A-Z0-9]{3}$' THEN
        p_ok := 0; p_msg := 'El formato del RFC no es válido'; RETURN;
    END IF;
    IF p_telefono IS NOT NULL AND
       EXISTS(SELECT 1 FROM usuarios WHERE usuario_telefono = TRIM(p_telefono)
              AND usuario_id != p_usuario_id) THEN
        p_ok := 0; p_msg := 'El teléfono ya está registrado en otro usuario'; RETURN;
    END IF;
    IF p_curp IS NOT NULL AND
       EXISTS(SELECT 1 FROM usuarios WHERE usuario_curp = UPPER(TRIM(p_curp))
              AND usuario_id != p_usuario_id) THEN
        p_ok := 0; p_msg := 'La CURP ya está registrada en otro usuario'; RETURN;
    END IF;
    IF p_rfc IS NOT NULL AND TRIM(p_rfc) != '' AND
       EXISTS(SELECT 1 FROM usuarios WHERE usuario_rfc = UPPER(TRIM(p_rfc))
              AND usuario_id != p_usuario_id) THEN
        p_ok := 0; p_msg := 'El RFC ya está registrado en otro usuario'; RETURN;
    END IF;

    UPDATE usuarios SET
        usuario_prim_nombre  = COALESCE(NULLIF(TRIM(p_prim_nombre),''),  usuario_prim_nombre),
        usuario_seg_nombre   = p_seg_nombre,
        usuario_apellido_pat = COALESCE(NULLIF(TRIM(p_apellido_pat),''), usuario_apellido_pat),
        usuario_apellido_mat = p_apellido_mat,
        usuario_telefono     = COALESCE(NULLIF(TRIM(p_telefono),''), usuario_telefono),
        usuario_curp         = COALESCE(UPPER(NULLIF(TRIM(p_curp),'')), usuario_curp),
        usuario_rfc          = CASE WHEN TRIM(COALESCE(p_rfc,''))='' THEN NULL
                                    ELSE UPPER(TRIM(p_rfc)) END,
        centro_id            = CASE WHEN 'responsable' = ANY(p_roles) THEN p_centro_id
                                    ELSE NULL END
    WHERE usuario_id = p_usuario_id;

    IF p_email IS NOT NULL AND TRIM(p_email) != '' THEN
        UPDATE login SET login_correo = LOWER(TRIM(p_email)) WHERE usuario_id = p_usuario_id;
    END IF;

    DELETE FROM usuarios_roles WHERE usuario_id = p_usuario_id;
    FOREACH v_rol IN ARRAY p_roles LOOP
        SELECT rol_id INTO v_rol_id FROM roles WHERE rol_nombre = v_rol;
        IF v_rol_id IS NOT NULL THEN
            INSERT INTO usuarios_roles(usuario_id, rol_id) VALUES(p_usuario_id, v_rol_id)
            ON CONFLICT DO NOTHING;
        END IF;
    END LOOP;

    DELETE FROM cedulas WHERE usuario_id = p_usuario_id;
    IF 'responsable' = ANY(p_roles) AND p_cedulas_nums IS NOT NULL
       AND array_length(p_cedulas_nums, 1) IS NOT NULL THEN
        FOR v_i IN 1..array_length(p_cedulas_nums, 1) LOOP
            IF TRIM(COALESCE(p_cedulas_nums[v_i],'')) != '' THEN
                INSERT INTO cedulas(cedula_numero, cedula_especialidad, usuario_id)
                VALUES(TRIM(p_cedulas_nums[v_i]),
                       NULLIF(TRIM(COALESCE(p_cedulas_specs[v_i],'')), ''),
                       p_usuario_id)
                ON CONFLICT (cedula_numero) DO NOTHING;
            END IF;
        END LOOP;
    END IF;

    p_ok := 1; p_msg := 'Usuario actualizado correctamente';
EXCEPTION
    WHEN unique_violation THEN p_ok := 0; p_msg := 'Correo, teléfono, CURP o RFC ya registrado';
    WHEN OTHERS THEN p_ok := 0; p_msg := 'Error al actualizar: ' || SQLERRM;
END; $$;

CREATE OR REPLACE PROCEDURE sp_crear_admin(
    IN  p_prim_nombre  VARCHAR(100), IN  p_seg_nombre   VARCHAR(100),
    IN  p_apellido_pat VARCHAR(100), IN  p_apellido_mat VARCHAR(100),
    IN  p_telefono     VARCHAR(20),  IN  p_curp         VARCHAR(18),
    IN  p_rfc          VARCHAR(13),  IN  p_email        VARCHAR(150),
    IN  p_contrasena   VARCHAR(255),
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(150), OUT p_id INTEGER
)
LANGUAGE plpgsql AS $$
DECLARE v_ok SMALLINT; v_msg VARCHAR(150); v_id INTEGER;
BEGIN
    CALL sp_crear_usuario_base(p_prim_nombre, p_seg_nombre, p_apellido_pat, p_apellido_mat,
        p_telefono, p_curp, p_rfc, p_email, p_contrasena, NULL, 'admin',
        v_ok, v_msg, v_id);
    p_ok := v_ok; p_msg := v_msg; p_id := v_id;
    IF v_ok = 1 THEN p_msg := 'Administrador registrado correctamente'; END IF;
END; $$;

-- patch_postgres.sql version
CREATE OR REPLACE PROCEDURE sp_actualizar_admin(
    IN  p_admin_id     INTEGER,
    IN  p_prim_nombre  VARCHAR(100), IN  p_seg_nombre   VARCHAR(100),
    IN  p_apellido_pat VARCHAR(100), IN  p_apellido_mat VARCHAR(100),
    IN  p_telefono     VARCHAR(20),  IN  p_curp         VARCHAR(18),
    IN  p_rfc          VARCHAR(13),  IN  p_email        VARCHAR(150),
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(200)
)
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM usuarios WHERE usuario_id = p_admin_id) THEN
        p_ok := 0; p_msg := 'Administrador no encontrado.'; RETURN;
    END IF;
    IF p_telefono IS NOT NULL AND p_telefono !~ '^[0-9]{10}$' THEN
        p_ok := 0; p_msg := 'El teléfono debe tener exactamente 10 dígitos.'; RETURN;
    END IF;
    IF p_curp IS NOT NULL AND LENGTH(TRIM(p_curp)) != 18 THEN
        p_ok := 0; p_msg := 'La CURP debe tener 18 caracteres.'; RETURN;
    END IF;
    IF p_telefono IS NOT NULL AND
       EXISTS(SELECT 1 FROM usuarios WHERE usuario_telefono = TRIM(p_telefono) AND usuario_id != p_admin_id) THEN
        p_ok := 0; p_msg := 'El teléfono ya está registrado en otro usuario.'; RETURN;
    END IF;
    IF p_curp IS NOT NULL AND
       EXISTS(SELECT 1 FROM usuarios WHERE usuario_curp = UPPER(TRIM(p_curp)) AND usuario_id != p_admin_id) THEN
        p_ok := 0; p_msg := 'La CURP ya está registrada en otro usuario.'; RETURN;
    END IF;
    IF p_rfc IS NOT NULL AND
       EXISTS(SELECT 1 FROM usuarios WHERE usuario_rfc = UPPER(TRIM(p_rfc)) AND usuario_id != p_admin_id) THEN
        p_ok := 0; p_msg := 'El RFC ya está registrado en otro usuario.'; RETURN;
    END IF;
    UPDATE usuarios SET
        usuario_prim_nombre  = COALESCE(p_prim_nombre,  usuario_prim_nombre),
        usuario_seg_nombre   = COALESCE(p_seg_nombre,   usuario_seg_nombre),
        usuario_apellido_pat = COALESCE(p_apellido_pat, usuario_apellido_pat),
        usuario_apellido_mat = COALESCE(p_apellido_mat, usuario_apellido_mat),
        usuario_telefono     = COALESCE(TRIM(p_telefono), usuario_telefono),
        usuario_curp         = COALESCE(UPPER(TRIM(p_curp)), usuario_curp),
        usuario_rfc          = COALESCE(UPPER(TRIM(p_rfc)),  usuario_rfc)
    WHERE usuario_id = p_admin_id;
    IF p_email IS NOT NULL AND TRIM(p_email) != '' THEN
        IF EXISTS(SELECT 1 FROM login WHERE login_correo = LOWER(TRIM(p_email)) AND usuario_id != p_admin_id) THEN
            p_ok := 0; p_msg := 'El correo electrónico ya está registrado en otro usuario.'; RETURN;
        END IF;
        UPDATE login SET login_correo = LOWER(TRIM(p_email)) WHERE usuario_id = p_admin_id;
    END IF;
    p_ok := 1; p_msg := 'Administrador actualizado correctamente.';
EXCEPTION
    WHEN unique_violation THEN p_ok := 0; p_msg := 'Ya existe otro administrador con esos datos.';
    WHEN OTHERS THEN p_ok := 0; p_msg := 'No se pudo actualizar el administrador.';
END; $$;

CREATE OR REPLACE PROCEDURE sp_eliminar_admin(
    IN  p_admin_id INTEGER, IN  p_session_id INTEGER,
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(150))
LANGUAGE plpgsql AS $$
BEGIN
    IF p_admin_id = p_session_id THEN
        p_ok := 0; p_msg := 'No puedes eliminar tu propia cuenta'; RETURN;
    END IF;
    IF NOT EXISTS(SELECT 1 FROM usuarios WHERE usuario_id = p_admin_id) THEN
        p_ok := 0; p_msg := 'Administrador no encontrado'; RETURN;
    END IF;
    DELETE FROM usuarios WHERE usuario_id = p_admin_id;
    p_ok := 1; p_msg := 'Administrador eliminado correctamente';
EXCEPTION
    WHEN OTHERS THEN p_ok := 0; p_msg := 'Error al eliminar: ' || SQLERRM;
END; $$;

CREATE OR REPLACE PROCEDURE sp_crear_tutor(
    IN  p_prim_nombre  VARCHAR(100), IN  p_seg_nombre   VARCHAR(100),
    IN  p_apellido_pat VARCHAR(100), IN  p_apellido_mat VARCHAR(100),
    IN  p_telefono     VARCHAR(20),  IN  p_curp         VARCHAR(18),
    IN  p_email        VARCHAR(150), IN  p_contrasena   VARCHAR(255),
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(150), OUT p_id INTEGER
)
LANGUAGE plpgsql AS $$
DECLARE v_ok SMALLINT; v_msg VARCHAR(150); v_id INTEGER;
BEGIN
    CALL sp_crear_usuario_base(p_prim_nombre, p_seg_nombre, p_apellido_pat, p_apellido_mat,
        p_telefono, p_curp, NULL, p_email, p_contrasena, NULL, 'tutor',
        v_ok, v_msg, v_id);
    p_ok := v_ok; p_msg := v_msg; p_id := v_id;
    IF v_ok = 1 THEN p_msg := 'Tutor registrado correctamente'; END IF;
END; $$;

CREATE OR REPLACE PROCEDURE sp_actualizar_tutor(
    IN  p_tutor_id     INTEGER,
    IN  p_prim_nombre  VARCHAR(100), IN  p_seg_nombre   VARCHAR(100),
    IN  p_apellido_pat VARCHAR(100), IN  p_apellido_mat VARCHAR(100),
    IN  p_telefono     VARCHAR(20),  IN  p_curp         VARCHAR(18),
    IN  p_email        VARCHAR(150),
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(150)
)
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM usuarios WHERE usuario_id = p_tutor_id) THEN
        p_ok := 0; p_msg := 'Tutor no encontrado'; RETURN;
    END IF;
    IF p_telefono IS NOT NULL AND p_telefono !~ '^[0-9]{10}$' THEN
        p_ok := 0; p_msg := 'El teléfono debe tener exactamente 10 dígitos'; RETURN;
    END IF;
    IF p_curp IS NOT NULL AND LENGTH(TRIM(p_curp)) != 18 THEN
        p_ok := 0; p_msg := 'La CURP debe tener 18 caracteres'; RETURN;
    END IF;
    IF p_curp IS NOT NULL AND UPPER(TRIM(p_curp)) !~ '^[A-Z]{4}[0-9]{6}[HM][A-Z]{5}[0-9A-Z][0-9]$' THEN
        p_ok := 0; p_msg := 'El formato de la CURP no es válido'; RETURN;
    END IF;
    IF p_telefono IS NOT NULL AND
       EXISTS(SELECT 1 FROM usuarios WHERE usuario_telefono = TRIM(p_telefono) AND usuario_id != p_tutor_id) THEN
        p_ok := 0; p_msg := 'El teléfono ya está registrado en otro usuario'; RETURN;
    END IF;
    IF p_curp IS NOT NULL AND
       EXISTS(SELECT 1 FROM usuarios WHERE usuario_curp = UPPER(TRIM(p_curp)) AND usuario_id != p_tutor_id) THEN
        p_ok := 0; p_msg := 'La CURP ya está registrada en otro usuario'; RETURN;
    END IF;

    UPDATE usuarios SET
        usuario_prim_nombre  = COALESCE(p_prim_nombre,  usuario_prim_nombre),
        usuario_seg_nombre   = COALESCE(p_seg_nombre,   usuario_seg_nombre),
        usuario_apellido_pat = COALESCE(p_apellido_pat, usuario_apellido_pat),
        usuario_apellido_mat = COALESCE(p_apellido_mat, usuario_apellido_mat),
        usuario_telefono     = COALESCE(TRIM(p_telefono), usuario_telefono),
        usuario_curp         = COALESCE(UPPER(TRIM(p_curp)), usuario_curp)
    WHERE usuario_id = p_tutor_id;

    IF p_email IS NOT NULL AND TRIM(p_email) != '' THEN
        UPDATE login SET login_correo = LOWER(TRIM(p_email)) WHERE usuario_id = p_tutor_id;
    END IF;

    p_ok := 1; p_msg := 'Tutor actualizado correctamente';
EXCEPTION
    WHEN unique_violation THEN p_ok := 0; p_msg := 'Correo, teléfono o CURP ya registrado';
    WHEN OTHERS THEN p_ok := 0; p_msg := 'Error al actualizar: ' || SQLERRM;
END; $$;

CREATE OR REPLACE PROCEDURE sp_eliminar_tutor(
    IN  p_tutor_id INTEGER,
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(150))
LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS(SELECT 1 FROM pacientes_tutores WHERE tutor_id = p_tutor_id) THEN
        p_ok := 0; p_msg := 'No se puede eliminar: este tutor tiene pacientes vinculados'; RETURN;
    END IF;
    DELETE FROM usuarios WHERE usuario_id = p_tutor_id;
    p_ok := 1; p_msg := 'Tutor eliminado correctamente';
EXCEPTION
    WHEN OTHERS THEN p_ok := 0; p_msg := 'Error al eliminar: ' || SQLERRM;
END; $$;

CREATE OR REPLACE PROCEDURE sp_crear_responsable(
    IN  p_prim_nombre  VARCHAR(100), IN  p_seg_nombre   VARCHAR(100),
    IN  p_apellido_pat VARCHAR(100), IN  p_apellido_mat VARCHAR(100),
    IN  p_telefono     VARCHAR(20),  IN  p_curp         VARCHAR(18),
    IN  p_rfc          VARCHAR(13),  IN  p_email        VARCHAR(150),
    IN  p_contrasena   VARCHAR(255), IN  p_centro_id    INTEGER,
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(150), OUT p_id INTEGER
)
LANGUAGE plpgsql AS $$
DECLARE v_ok SMALLINT; v_msg VARCHAR(150); v_id INTEGER;
BEGIN
    IF p_centro_id IS NULL OR NOT EXISTS(SELECT 1 FROM centros_salud WHERE centro_id = p_centro_id) THEN
        p_ok := 0; p_msg := 'Debes asignar un centro de salud válido'; RETURN;
    END IF;
    CALL sp_crear_usuario_base(p_prim_nombre, p_seg_nombre, p_apellido_pat, p_apellido_mat,
        p_telefono, p_curp, p_rfc, p_email, p_contrasena, p_centro_id, 'responsable',
        v_ok, v_msg, v_id);
    p_ok := v_ok; p_msg := v_msg; p_id := v_id;
    IF v_ok = 1 THEN p_msg := 'Responsable registrado correctamente'; END IF;
END; $$;

-- patch_postgres.sql version
CREATE OR REPLACE PROCEDURE sp_actualizar_responsable(
    IN  p_responsable_id INTEGER,
    IN  p_prim_nombre  VARCHAR(100), IN  p_seg_nombre   VARCHAR(100),
    IN  p_apellido_pat VARCHAR(100), IN  p_apellido_mat VARCHAR(100),
    IN  p_telefono     VARCHAR(20),  IN  p_curp         VARCHAR(18),
    IN  p_rfc          VARCHAR(13),  IN  p_email        VARCHAR(150),
    IN  p_centro_id    INTEGER,
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(200)
)
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM usuarios WHERE usuario_id = p_responsable_id) THEN
        p_ok := 0; p_msg := 'Responsable no encontrado.'; RETURN;
    END IF;
    IF p_centro_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM centros_salud WHERE centro_id = p_centro_id) THEN
        p_ok := 0; p_msg := 'El centro de salud seleccionado no existe.'; RETURN;
    END IF;
    IF p_telefono IS NOT NULL AND p_telefono !~ '^[0-9]{10}$' THEN
        p_ok := 0; p_msg := 'El teléfono debe tener exactamente 10 dígitos.'; RETURN;
    END IF;
    IF p_curp IS NOT NULL AND LENGTH(TRIM(p_curp)) != 18 THEN
        p_ok := 0; p_msg := 'La CURP debe tener 18 caracteres.'; RETURN;
    END IF;
    IF p_telefono IS NOT NULL AND
       EXISTS(SELECT 1 FROM usuarios WHERE usuario_telefono = TRIM(p_telefono) AND usuario_id != p_responsable_id) THEN
        p_ok := 0; p_msg := 'El teléfono ya está registrado en otro usuario.'; RETURN;
    END IF;
    IF p_curp IS NOT NULL AND
       EXISTS(SELECT 1 FROM usuarios WHERE usuario_curp = UPPER(TRIM(p_curp)) AND usuario_id != p_responsable_id) THEN
        p_ok := 0; p_msg := 'La CURP ya está registrada en otro usuario.'; RETURN;
    END IF;
    IF p_rfc IS NOT NULL AND
       EXISTS(SELECT 1 FROM usuarios WHERE usuario_rfc = UPPER(TRIM(p_rfc)) AND usuario_id != p_responsable_id) THEN
        p_ok := 0; p_msg := 'El RFC ya está registrado en otro usuario.'; RETURN;
    END IF;
    UPDATE usuarios SET
        usuario_prim_nombre  = COALESCE(p_prim_nombre,  usuario_prim_nombre),
        usuario_seg_nombre   = COALESCE(p_seg_nombre,   usuario_seg_nombre),
        usuario_apellido_pat = COALESCE(p_apellido_pat, usuario_apellido_pat),
        usuario_apellido_mat = COALESCE(p_apellido_mat, usuario_apellido_mat),
        usuario_telefono     = COALESCE(TRIM(p_telefono), usuario_telefono),
        usuario_curp         = COALESCE(UPPER(TRIM(p_curp)), usuario_curp),
        usuario_rfc          = COALESCE(UPPER(TRIM(p_rfc)),  usuario_rfc),
        centro_id            = COALESCE(p_centro_id, centro_id)
    WHERE usuario_id = p_responsable_id;
    IF p_email IS NOT NULL AND TRIM(p_email) != '' THEN
        IF EXISTS(SELECT 1 FROM login WHERE login_correo = LOWER(TRIM(p_email)) AND usuario_id != p_responsable_id) THEN
            p_ok := 0; p_msg := 'El correo electrónico ya está registrado en otro usuario.'; RETURN;
        END IF;
        UPDATE login SET login_correo = LOWER(TRIM(p_email)) WHERE usuario_id = p_responsable_id;
    END IF;
    p_ok := 1; p_msg := 'Responsable actualizado correctamente.';
EXCEPTION
    WHEN unique_violation THEN p_ok := 0; p_msg := 'Ya existe otro responsable con esos datos.';
    WHEN OTHERS THEN p_ok := 0; p_msg := 'No se pudo actualizar el responsable.';
END; $$;

CREATE OR REPLACE PROCEDURE sp_eliminar_responsable(
    IN  p_responsable_id INTEGER,
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(150))
LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS(SELECT 1 FROM aplicaciones WHERE usuario_id = p_responsable_id) THEN
        p_ok := 0; p_msg := 'No se puede eliminar: tiene aplicaciones registradas'; RETURN;
    END IF;
    DELETE FROM usuarios WHERE usuario_id = p_responsable_id;
    p_ok := 1; p_msg := 'Responsable eliminado correctamente';
EXCEPTION
    WHEN OTHERS THEN p_ok := 0; p_msg := 'Error al eliminar: ' || SQLERRM;
END; $$;

-- patch_postgres.sql version
CREATE OR REPLACE PROCEDURE sp_toggle_usuario_activo(
    IN  p_usuario_id INTEGER,
    IN  p_session_id INTEGER,
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(200), OUT p_activo BOOLEAN
)
LANGUAGE plpgsql AS $$
BEGIN
    IF p_usuario_id = p_session_id THEN
        p_ok := 0; p_msg := 'No puedes desactivar tu propia cuenta'; RETURN;
    END IF;
    IF NOT EXISTS(SELECT 1 FROM usuarios WHERE usuario_id = p_usuario_id) THEN
        p_ok := 0; p_msg := 'Usuario no encontrado'; RETURN;
    END IF;
    UPDATE usuarios
    SET    usuario_activo = NOT usuario_activo
    WHERE  usuario_id = p_usuario_id
    RETURNING usuario_activo INTO p_activo;
    p_ok  := 1;
    p_msg := CASE WHEN p_activo THEN 'Usuario reactivado correctamente'
                  ELSE 'Usuario desactivado correctamente' END;
EXCEPTION
    WHEN OTHERS THEN p_ok := 0; p_msg := 'Error al cambiar estado: ' || SQLERRM;
END; $$;

CREATE OR REPLACE PROCEDURE sp_actualizar_imagen_usuario(
    IN  p_usuario_id INTEGER, IN  p_ruta VARCHAR(255),
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(150))
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE usuarios SET usuario_imagen = p_ruta WHERE usuario_id = p_usuario_id;
    p_ok := 1; p_msg := 'Imagen actualizada';
EXCEPTION
    WHEN OTHERS THEN p_ok := 0; p_msg := 'Error al actualizar imagen: ' || SQLERRM;
END; $$;

CREATE OR REPLACE PROCEDURE sp_agregar_cedula(
    IN  p_usuario_id    INTEGER,
    IN  p_numero        VARCHAR(50),
    IN  p_especialidad  VARCHAR(100),
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(150), OUT p_id INTEGER)
LANGUAGE plpgsql AS $$
BEGIN
    IF TRIM(COALESCE(p_numero,'')) = '' THEN
        p_ok := 0; p_msg := 'El número de cédula es requerido'; RETURN;
    END IF;
    IF EXISTS(SELECT 1 FROM cedulas WHERE cedula_numero = TRIM(p_numero)) THEN
        p_ok := 0; p_msg := 'El número de cédula ya está registrado'; RETURN;
    END IF;
    INSERT INTO cedulas(cedula_numero, cedula_especialidad, usuario_id)
    VALUES(TRIM(p_numero), p_especialidad, p_usuario_id)
    RETURNING cedula_id INTO p_id;
    p_ok := 1; p_msg := 'Cédula registrada correctamente';
EXCEPTION
    WHEN unique_violation THEN p_ok := 0; p_msg := 'Número de cédula duplicado';
    WHEN OTHERS THEN p_ok := 0; p_msg := 'Error al registrar cédula: ' || SQLERRM;
END; $$;

-- patch_postgres.sql version
CREATE OR REPLACE PROCEDURE sp_eliminar_usuario_unificado(
    IN  p_usuario_id INTEGER,
    IN  p_session_id INTEGER,
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(200)
)
LANGUAGE plpgsql AS $$
BEGIN
    IF p_usuario_id = p_session_id THEN
        p_ok := 0; p_msg := 'No puedes eliminar tu propia cuenta'; RETURN;
    END IF;
    IF NOT EXISTS(SELECT 1 FROM usuarios WHERE usuario_id = p_usuario_id) THEN
        p_ok := 0; p_msg := 'Usuario no encontrado'; RETURN;
    END IF;
    IF EXISTS(SELECT 1 FROM pacientes_tutores WHERE tutor_id = p_usuario_id) THEN
        p_ok := 0; p_msg := 'No se puede eliminar: este usuario tiene pacientes vinculados como tutor'; RETURN;
    END IF;
    IF EXISTS(SELECT 1 FROM aplicaciones WHERE usuario_id = p_usuario_id) THEN
        p_ok := 0; p_msg := 'No se puede eliminar: este usuario tiene aplicaciones de vacunas registradas'; RETURN;
    END IF;
    DELETE FROM usuarios WHERE usuario_id = p_usuario_id;
    p_ok := 1; p_msg := 'Usuario eliminado correctamente';
EXCEPTION
    WHEN OTHERS THEN p_ok := 0; p_msg := 'Error al eliminar: ' || SQLERRM;
END; $$;


-- ═══ PACIENTES — LECTURA ═══

CREATE OR REPLACE PROCEDURE sp_listar_pacientes(INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
        SELECT * FROM vw_pacientes ORDER BY paciente_apellido_pat, paciente_prim_nombre;
END; $$;

CREATE OR REPLACE PROCEDURE sp_obtener_paciente(
    IN p_id INTEGER, INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR SELECT * FROM vw_pacientes WHERE paciente_id = p_id;
END; $$;

CREATE OR REPLACE PROCEDURE sp_obtener_paciente_por_nfc(
    IN p_nfc VARCHAR(100), INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR SELECT * FROM vw_pacientes WHERE paciente_nfc = p_nfc;
END; $$;

CREATE OR REPLACE PROCEDURE sp_obtener_paciente_por_curp(
    IN p_curp VARCHAR(18), INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
        SELECT * FROM vw_pacientes WHERE paciente_curp = UPPER(TRIM(p_curp));
END; $$;

CREATE OR REPLACE PROCEDURE sp_obtener_paciente_por_cert_nac(
    IN p_cert VARCHAR(50), INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
        SELECT * FROM vw_pacientes WHERE paciente_num_cert_nac = TRIM(p_cert);
END; $$;

-- patch_postgres.sql version
CREATE OR REPLACE PROCEDURE sp_pacientes_de_tutor(
    IN p_tutor_id INTEGER, INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
        SELECT * FROM vw_pacientes_por_tutor
        WHERE tutor_id = p_tutor_id
        ORDER BY paciente_apellido_pat, paciente_prim_nombre;
END; $$;


-- ═══ PACIENTES — ESCRITURA ═══

CREATE OR REPLACE PROCEDURE sp_crear_paciente(
    IN  p_prim_nombre   VARCHAR(100), IN  p_seg_nombre    VARCHAR(100),
    IN  p_apellido_pat  VARCHAR(100), IN  p_apellido_mat  VARCHAR(100),
    IN  p_curp          VARCHAR(18),  IN  p_num_cert_nac  VARCHAR(50),
    IN  p_fecha_nac     DATE,         IN  p_sexo          tipo_sexo,
    IN  p_nfc           VARCHAR(100), IN  p_esquema_id    INTEGER,
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(150), OUT p_id INTEGER)
LANGUAGE plpgsql AS $$
BEGIN
    IF TRIM(COALESCE(p_prim_nombre,'')) = '' THEN
        p_ok := 0; p_msg := 'El nombre del paciente es requerido'; RETURN;
    END IF;
    IF TRIM(COALESCE(p_apellido_pat,'')) = '' THEN
        p_ok := 0; p_msg := 'El apellido paterno es requerido'; RETURN;
    END IF;
    IF p_fecha_nac IS NULL THEN
        p_ok := 0; p_msg := 'La fecha de nacimiento es requerida'; RETURN;
    END IF;
    IF p_fecha_nac > CURRENT_DATE THEN
        p_ok := 0; p_msg := 'La fecha de nacimiento no puede ser futura'; RETURN;
    END IF;
    IF TRIM(COALESCE(p_curp,'')) = '' AND TRIM(COALESCE(p_num_cert_nac,'')) = '' THEN
        p_ok := 0; p_msg := 'Se requiere CURP o número de certificado de nacimiento'; RETURN;
    END IF;
    IF TRIM(COALESCE(p_curp,'')) != '' AND LENGTH(TRIM(p_curp)) != 18 THEN
        p_ok := 0; p_msg := 'La CURP debe tener 18 caracteres'; RETURN;
    END IF;
    IF NOT EXISTS(SELECT 1 FROM esquemas WHERE esquema_id = p_esquema_id) THEN
        p_ok := 0; p_msg := 'El esquema de vacunación no existe'; RETURN;
    END IF;
    IF TRIM(COALESCE(p_curp,'')) != '' AND
       EXISTS(SELECT 1 FROM pacientes WHERE paciente_curp = UPPER(TRIM(p_curp))) THEN
        p_ok := 0; p_msg := 'La CURP ya está registrada en otro paciente'; RETURN;
    END IF;
    IF TRIM(COALESCE(p_num_cert_nac,'')) != '' AND
       EXISTS(SELECT 1 FROM pacientes WHERE paciente_num_cert_nac = TRIM(p_num_cert_nac)) THEN
        p_ok := 0; p_msg := 'El número de certificado de nacimiento ya está registrado'; RETURN;
    END IF;

    INSERT INTO pacientes(paciente_prim_nombre, paciente_seg_nombre, paciente_apellido_pat,
        paciente_apellido_mat, paciente_curp, paciente_num_cert_nac, paciente_fecha_nac,
        paciente_sexo, paciente_nfc, esquema_id)
    VALUES(p_prim_nombre, p_seg_nombre, p_apellido_pat, p_apellido_mat,
           NULLIF(UPPER(TRIM(p_curp)),''), NULLIF(TRIM(p_num_cert_nac),''),
           p_fecha_nac, p_sexo, NULLIF(TRIM(COALESCE(p_nfc,'')),''), p_esquema_id)
    RETURNING paciente_id INTO p_id;
    p_ok := 1; p_msg := 'Paciente registrado correctamente';
EXCEPTION
    WHEN unique_violation THEN p_ok := 0; p_msg := 'CURP, NFC o certificado ya registrado';
    WHEN check_violation  THEN p_ok := 0; p_msg := 'Los datos no cumplen las restricciones';
    WHEN OTHERS THEN p_ok := 0; p_msg := 'Error al registrar paciente: ' || SQLERRM;
END; $$;

-- patch_postgres.sql version
CREATE OR REPLACE PROCEDURE sp_actualizar_paciente(
    IN  p_paciente_id    INTEGER,
    IN  p_prim_nombre    VARCHAR(100), IN  p_seg_nombre   VARCHAR(100),
    IN  p_apellido_pat   VARCHAR(100), IN  p_apellido_mat VARCHAR(100),
    IN  p_curp           VARCHAR(18),  IN  p_num_cert_nac VARCHAR(50),
    IN  p_fecha_nac      DATE,         IN  p_sexo         tipo_sexo,
    IN  p_nfc            VARCHAR(100), IN  p_esquema_id   INTEGER,
    OUT p_ok SMALLINT,   OUT p_msg VARCHAR(200)
)
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM pacientes WHERE paciente_id = p_paciente_id) THEN
        p_ok := 0; p_msg := 'Paciente no encontrado.'; RETURN;
    END IF;
    IF p_curp IS NULL AND p_num_cert_nac IS NULL THEN
        p_ok := 0; p_msg := 'Debes proporcionar al menos CURP o número de certificado de nacimiento.'; RETURN;
    END IF;
    IF p_fecha_nac IS NOT NULL AND p_fecha_nac > CURRENT_DATE THEN
        p_ok := 0; p_msg := 'La fecha de nacimiento no puede ser futura.'; RETURN;
    END IF;
    IF p_esquema_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM esquemas WHERE esquema_id = p_esquema_id) THEN
        p_ok := 0; p_msg := 'El esquema de vacunación seleccionado no existe.'; RETURN;
    END IF;
    IF p_curp IS NOT NULL AND
       EXISTS(SELECT 1 FROM pacientes WHERE paciente_curp = UPPER(TRIM(p_curp)) AND paciente_id != p_paciente_id) THEN
        p_ok := 0; p_msg := 'La CURP ya está registrada en otro paciente.'; RETURN;
    END IF;
    IF p_num_cert_nac IS NOT NULL AND
       EXISTS(SELECT 1 FROM pacientes WHERE paciente_num_cert_nac = TRIM(p_num_cert_nac) AND paciente_id != p_paciente_id) THEN
        p_ok := 0; p_msg := 'El número de certificado de nacimiento ya está registrado en otro paciente.'; RETURN;
    END IF;
    IF p_nfc IS NOT NULL AND
       EXISTS(SELECT 1 FROM pacientes WHERE paciente_nfc = TRIM(p_nfc) AND paciente_id != p_paciente_id) THEN
        p_ok := 0; p_msg := 'El UID NFC ya está registrado en otro paciente.'; RETURN;
    END IF;
    UPDATE pacientes SET
        paciente_prim_nombre  = COALESCE(p_prim_nombre,  paciente_prim_nombre),
        paciente_seg_nombre   = p_seg_nombre,
        paciente_apellido_pat = COALESCE(p_apellido_pat, paciente_apellido_pat),
        paciente_apellido_mat = p_apellido_mat,
        paciente_curp         = CASE WHEN p_curp IS NULL THEN paciente_curp ELSE UPPER(TRIM(p_curp)) END,
        paciente_num_cert_nac = CASE WHEN p_num_cert_nac IS NULL THEN paciente_num_cert_nac ELSE TRIM(p_num_cert_nac) END,
        paciente_fecha_nac    = COALESCE(p_fecha_nac, paciente_fecha_nac),
        paciente_sexo         = COALESCE(p_sexo, paciente_sexo),
        paciente_nfc          = p_nfc,
        esquema_id            = COALESCE(p_esquema_id, esquema_id)
    WHERE paciente_id = p_paciente_id;
    p_ok := 1; p_msg := 'Paciente actualizado correctamente.';
EXCEPTION
    WHEN unique_violation THEN p_ok := 0; p_msg := 'Ya existe otro paciente con esos datos (CURP, certificado o NFC).';
    WHEN check_violation THEN p_ok := 0; p_msg := 'Algunos datos no cumplen las validaciones.';
    WHEN foreign_key_violation THEN p_ok := 0; p_msg := 'El esquema seleccionado no existe.';
    WHEN OTHERS THEN p_ok := 0; p_msg := 'No se pudo actualizar el paciente.';
END; $$;

CREATE OR REPLACE PROCEDURE sp_eliminar_paciente(
    IN  p_paciente_id INTEGER,
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(150))
LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS(SELECT 1 FROM aplicaciones WHERE paciente_id = p_paciente_id) THEN
        p_ok := 0; p_msg := 'No se puede eliminar: el paciente tiene aplicaciones registradas'; RETURN;
    END IF;
    DELETE FROM pacientes WHERE paciente_id = p_paciente_id;
    p_ok := 1; p_msg := 'Paciente eliminado correctamente';
EXCEPTION
    WHEN OTHERS THEN p_ok := 0; p_msg := 'Error al eliminar: ' || SQLERRM;
END; $$;

CREATE OR REPLACE PROCEDURE sp_actualizar_imagen_paciente(
    IN  p_paciente_id INTEGER, IN  p_ruta VARCHAR(255),
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(150))
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE pacientes SET paciente_imagen = p_ruta WHERE paciente_id = p_paciente_id;
    p_ok := 1; p_msg := 'Imagen actualizada';
EXCEPTION
    WHEN OTHERS THEN p_ok := 0; p_msg := 'Error al actualizar imagen: ' || SQLERRM;
END; $$;

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


-- ═══ RELACIONES TUTOR-PACIENTE ═══

CREATE OR REPLACE PROCEDURE sp_listar_relaciones(INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR SELECT * FROM vw_relaciones ORDER BY pac_tut_id;
END; $$;

CREATE OR REPLACE PROCEDURE sp_obtener_relacion(
    IN p_id INTEGER, INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR SELECT * FROM vw_relaciones WHERE pac_tut_id = p_id;
END; $$;

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

-- sps_riesgos_serios.sql version (validates tutor is active and has tutor role)
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

CREATE OR REPLACE PROCEDURE sp_eliminar_relacion(
    IN  p_pac_tut_id INTEGER,
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(150))
LANGUAGE plpgsql AS $$
BEGIN
    DELETE FROM pacientes_tutores WHERE pac_tut_id = p_pac_tut_id;
    p_ok := 1; p_msg := 'Relación eliminada correctamente';
EXCEPTION
    WHEN OTHERS THEN p_ok := 0; p_msg := 'Error al eliminar relación: ' || SQLERRM;
END; $$;


-- ═══ CENTROS DE SALUD ═══

-- patch_postgres.sql version
CREATE OR REPLACE PROCEDURE sp_listar_centros(INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR SELECT * FROM vw_centros_detalle ORDER BY centro_nombre;
END; $$;

-- patch_postgres.sql version
CREATE OR REPLACE PROCEDURE sp_obtener_centro(
    IN p_id INTEGER, INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR SELECT * FROM vw_centros_detalle WHERE centro_id = p_id;
END; $$;

-- patch_postgres.sql version
CREATE OR REPLACE PROCEDURE sp_obtener_centro_por_beacon(
    IN p_beacon_id VARCHAR(100), INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR SELECT * FROM vw_centros_detalle WHERE LOWER(centro_beacon) = LOWER(p_beacon_id);
END; $$;

CREATE OR REPLACE PROCEDURE sp_crear_centro(
    IN  p_nombre    VARCHAR(150), IN  p_calle     VARCHAR(150),
    IN  p_numero    VARCHAR(10),  IN  p_cp        VARCHAR(10),
    IN  p_ciudad_id INTEGER,      IN  p_h_inicio  TIME,
    IN  p_h_fin     TIME,         IN  p_latitud   NUMERIC,
    IN  p_longitud  NUMERIC,      IN  p_telefono  VARCHAR(20),
    IN  p_beacon    VARCHAR(100),
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(150), OUT p_id INTEGER)
LANGUAGE plpgsql AS $$
BEGIN
    IF TRIM(COALESCE(p_nombre,'')) = '' THEN
        p_ok := 0; p_msg := 'El nombre del centro es requerido'; RETURN;
    END IF;
    IF p_h_inicio IS NOT NULL AND p_h_fin IS NOT NULL AND p_h_fin <= p_h_inicio THEN
        p_ok := 0; p_msg := 'El horario de cierre debe ser posterior al de apertura'; RETURN;
    END IF;
    IF NOT EXISTS(SELECT 1 FROM ciudades WHERE ciudad_id = p_ciudad_id) THEN
        p_ok := 0; p_msg := 'La ciudad indicada no existe'; RETURN;
    END IF;
    INSERT INTO centros_salud(centro_nombre, centro_calle, centro_numero, centro_codigo_postal,
        ciudad_id, centro_horario_inicio, centro_horario_fin, centro_latitud,
        centro_longitud, centro_telefono, centro_beacon)
    VALUES(TRIM(p_nombre), p_calle, p_numero, p_cp, p_ciudad_id,
           p_h_inicio, p_h_fin, p_latitud, p_longitud, p_telefono, p_beacon)
    RETURNING centro_id INTO p_id;
    p_ok := 1; p_msg := 'Centro de salud registrado correctamente';
EXCEPTION
    WHEN unique_violation  THEN p_ok := 0; p_msg := 'Teléfono o beacon ya registrado';
    WHEN check_violation   THEN p_ok := 0; p_msg := 'Horario o coordenadas inválidas';
    WHEN OTHERS THEN p_ok := 0; p_msg := 'Error al crear centro: ' || SQLERRM;
END; $$;

-- patch_postgres.sql version
CREATE OR REPLACE PROCEDURE sp_actualizar_centro(
    IN  p_centro_id      INTEGER,
    IN  p_nombre         VARCHAR(150),
    IN  p_calle          VARCHAR(150), IN  p_numero       VARCHAR(10),
    IN  p_codigo_postal  VARCHAR(10),  IN  p_ciudad_id    INTEGER,
    IN  p_horario_inicio TIME,         IN  p_horario_fin  TIME,
    IN  p_latitud        NUMERIC(11,8),IN  p_longitud     NUMERIC(11,8),
    IN  p_telefono       VARCHAR(20),  IN  p_beacon       VARCHAR(100),
    OUT p_ok SMALLINT,   OUT p_msg VARCHAR(200)
)
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM centros_salud WHERE centro_id = p_centro_id) THEN
        p_ok := 0; p_msg := 'Centro de salud no encontrado.'; RETURN;
    END IF;
    IF p_ciudad_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM ciudades WHERE ciudad_id = p_ciudad_id) THEN
        p_ok := 0; p_msg := 'La ciudad seleccionada no existe.'; RETURN;
    END IF;
    IF p_horario_inicio IS NOT NULL AND p_horario_fin IS NOT NULL AND p_horario_fin <= p_horario_inicio THEN
        p_ok := 0; p_msg := 'El horario de fin debe ser posterior al horario de inicio.'; RETURN;
    END IF;
    IF p_telefono IS NOT NULL AND
       EXISTS(SELECT 1 FROM centros_salud WHERE centro_telefono = p_telefono AND centro_id != p_centro_id) THEN
        p_ok := 0; p_msg := 'Ya existe otro centro con ese teléfono.'; RETURN;
    END IF;
    IF p_beacon IS NOT NULL AND
       EXISTS(SELECT 1 FROM centros_salud WHERE centro_beacon = p_beacon AND centro_id != p_centro_id) THEN
        p_ok := 0; p_msg := 'Ya existe otro centro con ese beacon.'; RETURN;
    END IF;
    UPDATE centros_salud SET
        centro_nombre         = COALESCE(p_nombre,         centro_nombre),
        centro_calle          = COALESCE(p_calle,          centro_calle),
        centro_numero         = COALESCE(p_numero,         centro_numero),
        centro_codigo_postal  = COALESCE(p_codigo_postal,  centro_codigo_postal),
        ciudad_id             = COALESCE(p_ciudad_id,      ciudad_id),
        centro_horario_inicio = COALESCE(p_horario_inicio, centro_horario_inicio),
        centro_horario_fin    = COALESCE(p_horario_fin,    centro_horario_fin),
        centro_latitud        = p_latitud,
        centro_longitud       = p_longitud,
        centro_telefono       = p_telefono,
        centro_beacon         = p_beacon
    WHERE centro_id = p_centro_id;
    p_ok := 1; p_msg := 'Centro de salud actualizado correctamente.';
EXCEPTION
    WHEN unique_violation THEN p_ok := 0; p_msg := 'Ya existe otro centro con ese teléfono o beacon.';
    WHEN check_violation THEN p_ok := 0; p_msg := 'Algunos datos están fuera del rango permitido.';
    WHEN OTHERS THEN p_ok := 0; p_msg := 'No se pudo actualizar el centro de salud.';
END; $$;

CREATE OR REPLACE PROCEDURE sp_eliminar_centro(
    IN  p_centro_id INTEGER,
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(150))
LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS(SELECT 1 FROM usuarios WHERE centro_id = p_centro_id) THEN
        p_ok := 0; p_msg := 'No se puede eliminar: hay responsables asignados a este centro'; RETURN;
    END IF;
    IF EXISTS(SELECT 1 FROM inventarios WHERE centro_id = p_centro_id) THEN
        p_ok := 0; p_msg := 'No se puede eliminar: el centro tiene inventario registrado'; RETURN;
    END IF;
    DELETE FROM centros_salud WHERE centro_id = p_centro_id;
    p_ok := 1; p_msg := 'Centro eliminado correctamente';
EXCEPTION
    WHEN OTHERS THEN p_ok := 0; p_msg := 'Error al eliminar centro: ' || SQLERRM;
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

CREATE OR REPLACE PROCEDURE sp_tutores_esperando_en_centro(
    IN p_centro_id INTEGER, INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
        SELECT DISTINCT tutor_id
        FROM lecturas_beacon
        WHERE centro_id = p_centro_id
          AND lectura_timestamp > NOW() - INTERVAL '45 minutes';
END; $$;

CREATE OR REPLACE PROCEDURE sp_vacunas_en_centro(
    IN p_centro_id INTEGER, INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
        SELECT * FROM vw_centros_stock_vacuna WHERE centro_id = p_centro_id;
END; $$;
-- ═════════════════════════════════════════════════════════════════════════════
-- VacunaTrack — Stored Procedures: Parte 2
-- Vacunas · Dosis · Esquemas · Fabricantes · Proveedores · Lotes · Inventarios
-- Generado desde:
--   vacunatrack_diaitc.sql  (base)
--   patch_postgres.sql      (overrides de actualización/eliminación y misc)
--   patch_caducidad.sql     (overrides: sp_stock_disponible,
--                            sp_inventarios_activos_de_centro)
--   sps_riesgos_serios.sql  (overrides: sp_transferir_inventario,
--                            sp_recalcular_alertas_inventario,
--                            sp_resolver_conflicto)
-- Regla: cuando un SP aparece en más de un archivo, se usa la versión del
-- archivo de patch más reciente.
-- ═════════════════════════════════════════════════════════════════════════════


-- ═══ VACUNAS Y DOSIS ═══

CREATE OR REPLACE PROCEDURE sp_listar_vacunas(INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR SELECT * FROM vw_vacunas ORDER BY vacuna_nombre;
END; $$;

CREATE OR REPLACE PROCEDURE sp_obtener_vacuna(
    IN p_id INTEGER, INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR SELECT * FROM vw_vacunas WHERE vacuna_id = p_id;
END; $$;

CREATE OR REPLACE PROCEDURE sp_crear_vacuna(
    IN  p_nombre VARCHAR(150),
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(150), OUT p_id INTEGER)
LANGUAGE plpgsql AS $$
BEGIN
    IF TRIM(COALESCE(p_nombre,'')) = '' THEN
        p_ok := 0; p_msg := 'El nombre de la vacuna es requerido'; RETURN;
    END IF;
    IF EXISTS(SELECT 1 FROM vacunas WHERE LOWER(vacuna_nombre) = LOWER(TRIM(p_nombre))) THEN
        p_ok := 0; p_msg := 'Ya existe una vacuna con ese nombre'; RETURN;
    END IF;
    INSERT INTO vacunas(vacuna_nombre) VALUES(TRIM(p_nombre)) RETURNING vacuna_id INTO p_id;
    p_ok := 1; p_msg := 'Vacuna registrada correctamente';
EXCEPTION
    WHEN unique_violation THEN p_ok := 0; p_msg := 'Ya existe una vacuna con ese nombre';
    WHEN OTHERS THEN p_ok := 0; p_msg := 'Error al crear vacuna: ' || SQLERRM;
END; $$;

-- patch_postgres.sql version
CREATE OR REPLACE PROCEDURE sp_actualizar_vacuna(
    IN  p_vacuna_id INTEGER, IN  p_nombre VARCHAR(150),
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(200)
)
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM vacunas WHERE vacuna_id = p_vacuna_id) THEN
        p_ok := 0; p_msg := 'Vacuna no encontrada.'; RETURN;
    END IF;
    IF p_nombre IS NULL OR LENGTH(TRIM(p_nombre)) = 0 THEN
        p_ok := 0; p_msg := 'El nombre de la vacuna no puede estar vacío.'; RETURN;
    END IF;
    IF EXISTS(SELECT 1 FROM vacunas WHERE LOWER(vacuna_nombre) = LOWER(TRIM(p_nombre)) AND vacuna_id != p_vacuna_id) THEN
        p_ok := 0; p_msg := 'Ya existe otra vacuna con ese nombre.'; RETURN;
    END IF;
    UPDATE vacunas SET vacuna_nombre = TRIM(p_nombre) WHERE vacuna_id = p_vacuna_id;
    p_ok := 1; p_msg := 'Vacuna actualizada correctamente.';
EXCEPTION
    WHEN unique_violation THEN p_ok := 0; p_msg := 'Ya existe otra vacuna con ese nombre.';
    WHEN OTHERS THEN p_ok := 0; p_msg := 'No se pudo actualizar la vacuna.';
END; $$;

-- patch_postgres.sql version
CREATE OR REPLACE PROCEDURE sp_eliminar_vacuna(
    IN  p_vacuna_id INTEGER,
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(200)
)
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM vacunas WHERE vacuna_id = p_vacuna_id) THEN
        p_ok := 0; p_msg := 'Vacuna no encontrada.'; RETURN;
    END IF;
    IF EXISTS(SELECT 1 FROM dosis WHERE vacuna_id = p_vacuna_id) THEN
        p_ok := 0; p_msg := 'No se puede eliminar: la vacuna tiene dosis configuradas.'; RETURN;
    END IF;
    IF EXISTS(SELECT 1 FROM lotes WHERE vacuna_id = p_vacuna_id) THEN
        p_ok := 0; p_msg := 'No se puede eliminar: la vacuna tiene lotes registrados.'; RETURN;
    END IF;
    DELETE FROM vacunas_padecimientos WHERE vacuna_id = p_vacuna_id;
    DELETE FROM vacunas WHERE vacuna_id = p_vacuna_id;
    p_ok := 1; p_msg := 'Vacuna eliminada correctamente.';
EXCEPTION
    WHEN foreign_key_violation THEN p_ok := 0; p_msg := 'No se puede eliminar: hay registros que dependen de esta vacuna.';
    WHEN OTHERS THEN p_ok := 0; p_msg := 'No se pudo eliminar la vacuna.';
END; $$;

CREATE OR REPLACE PROCEDURE sp_listar_dosis(INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
        SELECT * FROM vw_dosis ORDER BY vacuna_id, dosis_edad_oportuna_dias;
END; $$;

CREATE OR REPLACE PROCEDURE sp_listar_dosis_por_vacuna(
    IN p_vacuna_id INTEGER, INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
        SELECT * FROM vw_dosis
        WHERE vacuna_id = p_vacuna_id ORDER BY dosis_edad_oportuna_dias;
END; $$;

CREATE OR REPLACE PROCEDURE sp_listar_dosis_activas(INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
        SELECT * FROM vw_dosis
        WHERE  dosis_vigente_hasta IS NULL
        ORDER  BY vacuna_id, dosis_edad_oportuna_dias;
END; $$;

CREATE OR REPLACE PROCEDURE sp_obtener_dosis(
    IN p_id INTEGER, INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR SELECT * FROM vw_dosis WHERE dosis_id = p_id;
END; $$;

CREATE OR REPLACE PROCEDURE sp_crear_dosis(
    IN  p_vacuna_id      INTEGER, IN  p_tipo       tipo_dosis,
    IN  p_cant_ml        NUMERIC, IN  p_area       VARCHAR(100),
    IN  p_edad_dias      INTEGER, IN  p_intervalo  INTEGER,
    IN  p_limite_dias    INTEGER,
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(150), OUT p_id INTEGER)
LANGUAGE plpgsql AS $$
BEGIN
    IF p_cant_ml <= 0 THEN
        p_ok := 0; p_msg := 'La cantidad en ml debe ser mayor a 0'; RETURN;
    END IF;
    IF NOT EXISTS(SELECT 1 FROM vacunas WHERE vacuna_id = p_vacuna_id) THEN
        p_ok := 0; p_msg := 'La vacuna indicada no existe'; RETURN;
    END IF;
    INSERT INTO dosis(vacuna_id, dosis_tipo, dosis_cant_ml, dosis_area_aplicacion,
        dosis_edad_oportuna_dias, dosis_intervalo_min_dias, dosis_limite_edad_dias)
    VALUES(p_vacuna_id, p_tipo, p_cant_ml, p_area, p_edad_dias,
           COALESCE(p_intervalo,0), p_limite_dias)
    RETURNING dosis_id INTO p_id;
    p_ok := 1; p_msg := 'Dosis registrada correctamente';
EXCEPTION
    WHEN check_violation  THEN p_ok := 0; p_msg := 'Datos de dosis inválidos (ml o días negativos)';
    WHEN OTHERS THEN p_ok := 0; p_msg := 'Error al crear dosis: ' || SQLERRM;
END; $$;

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

CREATE OR REPLACE PROCEDURE sp_listar_padecimientos(INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR SELECT * FROM vw_padecimientos ORDER BY padecimiento_nombre;
END; $$;

CREATE OR REPLACE PROCEDURE sp_obtener_padecimiento(
    IN p_id INTEGER, INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR SELECT * FROM vw_padecimientos WHERE padecimiento_id = p_id;
END; $$;

CREATE OR REPLACE PROCEDURE sp_crear_padecimiento(
    IN  p_nombre      VARCHAR(150),
    IN  p_descripcion TEXT,
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(150), OUT p_id INTEGER)
LANGUAGE plpgsql AS $$
BEGIN
    IF TRIM(COALESCE(p_nombre,'')) = '' THEN
        p_ok := 0; p_msg := 'El nombre del padecimiento es requerido'; RETURN;
    END IF;
    INSERT INTO padecimientos(padecimiento_nombre, padecimiento_descripcion)
    VALUES(TRIM(p_nombre), p_descripcion)
    RETURNING padecimiento_id INTO p_id;
    p_ok := 1; p_msg := 'Padecimiento registrado correctamente';
EXCEPTION
    WHEN unique_violation THEN p_ok := 0; p_msg := 'Ya existe un padecimiento con ese nombre';
    WHEN OTHERS THEN p_ok := 0; p_msg := 'Error al crear padecimiento: ' || SQLERRM;
END; $$;

-- patch_postgres.sql version
CREATE OR REPLACE PROCEDURE sp_actualizar_padecimiento(
    IN  p_padecimiento_id INTEGER,
    IN  p_nombre          VARCHAR(150),
    IN  p_descripcion     TEXT,
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(200)
)
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM padecimientos WHERE padecimiento_id = p_padecimiento_id) THEN
        p_ok := 0; p_msg := 'Padecimiento no encontrado.'; RETURN;
    END IF;
    IF p_nombre IS NULL OR LENGTH(TRIM(p_nombre)) = 0 THEN
        p_ok := 0; p_msg := 'El nombre del padecimiento no puede estar vacío.'; RETURN;
    END IF;
    IF EXISTS(SELECT 1 FROM padecimientos WHERE LOWER(padecimiento_nombre) = LOWER(TRIM(p_nombre)) AND padecimiento_id != p_padecimiento_id) THEN
        p_ok := 0; p_msg := 'Ya existe otro padecimiento con ese nombre.'; RETURN;
    END IF;
    UPDATE padecimientos SET
        padecimiento_nombre      = TRIM(p_nombre),
        padecimiento_descripcion = p_descripcion
    WHERE padecimiento_id = p_padecimiento_id;
    p_ok := 1; p_msg := 'Padecimiento actualizado correctamente.';
EXCEPTION
    WHEN unique_violation THEN p_ok := 0; p_msg := 'Ya existe otro padecimiento con ese nombre.';
    WHEN OTHERS THEN p_ok := 0; p_msg := 'No se pudo actualizar el padecimiento.';
END; $$;

-- patch_postgres.sql version
CREATE OR REPLACE PROCEDURE sp_eliminar_padecimiento(
    IN  p_padecimiento_id INTEGER,
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(200)
)
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM padecimientos WHERE padecimiento_id = p_padecimiento_id) THEN
        p_ok := 0; p_msg := 'Padecimiento no encontrado.'; RETURN;
    END IF;
    DELETE FROM vacunas_padecimientos WHERE padecimiento_id = p_padecimiento_id;
    DELETE FROM padecimientos WHERE padecimiento_id = p_padecimiento_id;
    p_ok := 1; p_msg := 'Padecimiento eliminado correctamente.';
EXCEPTION
    WHEN OTHERS THEN p_ok := 0; p_msg := 'No se pudo eliminar el padecimiento.';
END; $$;

-- patch_postgres.sql version
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

-- patch_postgres.sql version
CREATE OR REPLACE PROCEDURE sp_limpiar_vacunas_padecimiento(
    IN  p_padecimiento_id INTEGER,
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(200)
)
LANGUAGE plpgsql AS $$
BEGIN
    DELETE FROM vacunas_padecimientos WHERE padecimiento_id = p_padecimiento_id;
    p_ok := 1; p_msg := 'Vacunas vinculadas reiniciadas.';
EXCEPTION
    WHEN OTHERS THEN p_ok := 0; p_msg := 'No se pudo limpiar las vacunas vinculadas.';
END; $$;

-- patch_postgres.sql version
CREATE OR REPLACE PROCEDURE sp_vacunas_de_padecimiento(
    IN  p_padecimiento_id INTEGER,
    INOUT p_resultados REFCURSOR
)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
        SELECT vp.vacuna_id FROM vacunas_padecimientos vp
        WHERE vp.padecimiento_id = p_padecimiento_id;
END; $$;


-- ═══ ESQUEMAS ═══

CREATE OR REPLACE PROCEDURE sp_listar_esquemas(INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR SELECT * FROM vw_esquemas ORDER BY esquema_nombre;
END; $$;

CREATE OR REPLACE PROCEDURE sp_obtener_esquema(
    IN p_id INTEGER, INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR SELECT * FROM vw_esquemas WHERE esquema_id = p_id;
END; $$;

CREATE OR REPLACE PROCEDURE sp_dosis_de_esquema(
    IN p_esquema_id INTEGER, INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
        SELECT * FROM vw_dosis_esquemas_detalle
        WHERE esquema_id = p_esquema_id
        ORDER BY vacuna_id, dosis_edad_oportuna_dias;
END; $$;

-- patch_postgres.sql version
CREATE OR REPLACE PROCEDURE sp_listar_dosis_esquemas(INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
        SELECT * FROM vw_dosis_esquemas ORDER BY esquema_id, vacuna_nombre, dosis_edad_oportuna_dias;
END; $$;

CREATE OR REPLACE PROCEDURE sp_crear_esquema(
    IN  p_nombre          VARCHAR(150),
    IN  p_fecha_vigencia  DATE,
    IN  p_vigente_desde   DATE,
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(150), OUT p_id INTEGER)
LANGUAGE plpgsql AS $$
BEGIN
    IF TRIM(COALESCE(p_nombre,'')) = '' THEN
        p_ok := 0; p_msg := 'El nombre del esquema es requerido'; RETURN;
    END IF;
    IF p_fecha_vigencia IS NULL THEN
        p_ok := 0; p_msg := 'La fecha de vigencia es requerida'; RETURN;
    END IF;
    INSERT INTO esquemas(esquema_nombre, esquema_fecha_vigencia, esquema_vigente_desde)
    VALUES(TRIM(p_nombre), p_fecha_vigencia, COALESCE(p_vigente_desde, CURRENT_DATE))
    RETURNING esquema_id INTO p_id;
    p_ok := 1; p_msg := 'Esquema registrado correctamente';
EXCEPTION
    WHEN unique_violation THEN p_ok := 0; p_msg := 'Ya existe un esquema con ese nombre';
    WHEN OTHERS THEN p_ok := 0; p_msg := 'Error al crear esquema: ' || SQLERRM;
END; $$;

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

CREATE OR REPLACE PROCEDURE sp_eliminar_esquema(
    IN  p_esquema_id INTEGER,
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(150))
LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS(SELECT 1 FROM pacientes WHERE esquema_id = p_esquema_id) THEN
        p_ok := 0; p_msg := 'No se puede eliminar: hay pacientes asignados a este esquema'; RETURN;
    END IF;
    DELETE FROM esquemas WHERE esquema_id = p_esquema_id;
    p_ok := 1; p_msg := 'Esquema eliminado correctamente';
EXCEPTION
    WHEN OTHERS THEN p_ok := 0; p_msg := 'Error al eliminar esquema: ' || SQLERRM;
END; $$;

CREATE OR REPLACE PROCEDURE sp_agregar_dosis_a_esquema(
    IN  p_esquema_id INTEGER, IN  p_dosis_id INTEGER,
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(150), OUT p_id INTEGER)
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM esquemas WHERE esquema_id = p_esquema_id) THEN
        p_ok := 0; p_msg := 'El esquema no existe'; RETURN;
    END IF;
    IF NOT EXISTS(SELECT 1 FROM dosis WHERE dosis_id = p_dosis_id) THEN
        p_ok := 0; p_msg := 'La dosis no existe'; RETURN;
    END IF;
    INSERT INTO dosis_esquemas(esquema_id, dosis_id) VALUES(p_esquema_id, p_dosis_id)
    ON CONFLICT DO NOTHING RETURNING dosis_esq_id INTO p_id;
    p_ok := 1; p_msg := 'Dosis agregada al esquema';
EXCEPTION
    WHEN OTHERS THEN p_ok := 0; p_msg := 'Error al agregar dosis: ' || SQLERRM;
END; $$;

-- sps_riesgos_serios.sql version
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

CREATE OR REPLACE PROCEDURE sp_listar_conflictos_esquema(INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
        SELECT * FROM vw_conflictos_esquema
        ORDER BY paciente_apellido_pat, paciente_prim_nombre, dosis_edad_oportuna_dias;
END; $$;


-- ═══ FABRICANTES Y PROVEEDORES ═══

CREATE OR REPLACE PROCEDURE sp_listar_fabricantes(INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR SELECT * FROM vw_fabricantes ORDER BY fabricante_nombre;
END; $$;

CREATE OR REPLACE PROCEDURE sp_obtener_fabricante(
    IN p_id INTEGER, INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR SELECT * FROM vw_fabricantes WHERE fabricante_id = p_id;
END; $$;

CREATE OR REPLACE PROCEDURE sp_crear_fabricante(
    IN  p_nombre    VARCHAR(150),
    IN  p_pais_id   INTEGER,
    IN  p_telefono  VARCHAR(20),
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(150), OUT p_id INTEGER)
LANGUAGE plpgsql AS $$
BEGIN
    IF TRIM(COALESCE(p_nombre,'')) = '' THEN
        p_ok := 0; p_msg := 'El nombre del fabricante es requerido'; RETURN;
    END IF;
    IF NOT EXISTS(SELECT 1 FROM paises WHERE pais_id = p_pais_id) THEN
        p_ok := 0; p_msg := 'El país indicado no existe'; RETURN;
    END IF;
    INSERT INTO fabricantes(fabricante_nombre, pais_id, fabricante_telefono)
    VALUES(TRIM(p_nombre), p_pais_id, p_telefono)
    RETURNING fabricante_id INTO p_id;
    p_ok := 1; p_msg := 'Fabricante registrado correctamente';
EXCEPTION
    WHEN unique_violation      THEN p_ok := 0; p_msg := 'Teléfono ya registrado';
    WHEN foreign_key_violation THEN p_ok := 0; p_msg := 'El país indicado no existe';
    WHEN OTHERS THEN p_ok := 0; p_msg := 'Error al crear fabricante: ' || SQLERRM;
END; $$;

-- patch_postgres.sql version
CREATE OR REPLACE PROCEDURE sp_actualizar_fabricante(
    IN  p_fabricante_id INTEGER,
    IN  p_nombre        VARCHAR(150),
    IN  p_pais_id       INTEGER,
    IN  p_telefono      VARCHAR(20),
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(200)
)
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM fabricantes WHERE fabricante_id = p_fabricante_id) THEN
        p_ok := 0; p_msg := 'Fabricante no encontrado.'; RETURN;
    END IF;
    IF p_pais_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM paises WHERE pais_id = p_pais_id) THEN
        p_ok := 0; p_msg := 'El país seleccionado no existe.'; RETURN;
    END IF;
    IF p_telefono IS NOT NULL AND
       EXISTS(SELECT 1 FROM fabricantes WHERE fabricante_telefono = p_telefono AND fabricante_id != p_fabricante_id) THEN
        p_ok := 0; p_msg := 'Ya existe otro fabricante con ese teléfono.'; RETURN;
    END IF;
    UPDATE fabricantes SET
        fabricante_nombre   = COALESCE(p_nombre, fabricante_nombre),
        pais_id             = COALESCE(p_pais_id, pais_id),
        fabricante_telefono = p_telefono
    WHERE fabricante_id = p_fabricante_id;
    p_ok := 1; p_msg := 'Fabricante actualizado correctamente.';
EXCEPTION
    WHEN unique_violation THEN p_ok := 0; p_msg := 'Ya existe otro fabricante con ese teléfono.';
    WHEN OTHERS THEN p_ok := 0; p_msg := 'No se pudo actualizar el fabricante.';
END; $$;

-- patch_postgres.sql version
CREATE OR REPLACE PROCEDURE sp_eliminar_fabricante(
    IN  p_fabricante_id INTEGER,
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(200)
)
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM fabricantes WHERE fabricante_id = p_fabricante_id) THEN
        p_ok := 0; p_msg := 'Fabricante no encontrado.'; RETURN;
    END IF;
    IF EXISTS(SELECT 1 FROM proveedores WHERE fabricante_id = p_fabricante_id) THEN
        p_ok := 0; p_msg := 'No se puede eliminar: el fabricante tiene proveedores asociados.'; RETURN;
    END IF;
    IF EXISTS(SELECT 1 FROM lotes WHERE fabricante_id = p_fabricante_id) THEN
        p_ok := 0; p_msg := 'No se puede eliminar: el fabricante tiene lotes registrados.'; RETURN;
    END IF;
    DELETE FROM fabricantes WHERE fabricante_id = p_fabricante_id;
    p_ok := 1; p_msg := 'Fabricante eliminado correctamente.';
EXCEPTION
    WHEN foreign_key_violation THEN p_ok := 0; p_msg := 'No se puede eliminar: hay registros que dependen de este fabricante.';
    WHEN OTHERS THEN p_ok := 0; p_msg := 'No se pudo eliminar el fabricante.';
END; $$;

CREATE OR REPLACE PROCEDURE sp_listar_proveedores(INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
        SELECT * FROM vw_proveedores ORDER BY proveedor_apellido_pat, proveedor_prim_nombre;
END; $$;

CREATE OR REPLACE PROCEDURE sp_obtener_proveedor(
    IN p_id INTEGER, INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR SELECT * FROM vw_proveedores WHERE proveedor_id = p_id;
END; $$;

CREATE OR REPLACE PROCEDURE sp_crear_proveedor(
    IN  p_prim_nombre  VARCHAR(100), IN  p_seg_nombre   VARCHAR(100),
    IN  p_apellido_pat VARCHAR(100), IN  p_apellido_mat VARCHAR(100),
    IN  p_email        VARCHAR(150), IN  p_telefono     VARCHAR(20),
    IN  p_empresa      VARCHAR(150), IN  p_fabricante_id INTEGER,
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(150), OUT p_id INTEGER)
LANGUAGE plpgsql AS $$
BEGIN
    IF TRIM(COALESCE(p_prim_nombre,'')) = '' OR TRIM(COALESCE(p_apellido_pat,'')) = '' THEN
        p_ok := 0; p_msg := 'Nombre y apellido paterno son requeridos'; RETURN;
    END IF;
    INSERT INTO proveedores(proveedor_prim_nombre, proveedor_seg_nombre, proveedor_apellido_pat,
        proveedor_apellido_mat, proveedor_email, proveedor_telefono, proveedor_empresa, fabricante_id)
    VALUES(p_prim_nombre, p_seg_nombre, p_apellido_pat, p_apellido_mat,
           p_email, p_telefono, p_empresa, p_fabricante_id)
    RETURNING proveedor_id INTO p_id;
    p_ok := 1; p_msg := 'Proveedor registrado correctamente';
EXCEPTION
    WHEN unique_violation      THEN p_ok := 0; p_msg := 'Email o teléfono ya registrado';
    WHEN foreign_key_violation THEN p_ok := 0; p_msg := 'El fabricante indicado no existe';
    WHEN OTHERS THEN p_ok := 0; p_msg := 'Error al crear proveedor: ' || SQLERRM;
END; $$;

-- patch_postgres.sql version
CREATE OR REPLACE PROCEDURE sp_actualizar_proveedor(
    IN  p_proveedor_id INTEGER,
    IN  p_prim_nombre  VARCHAR(100), IN  p_seg_nombre   VARCHAR(100),
    IN  p_apellido_pat VARCHAR(100), IN  p_apellido_mat VARCHAR(100),
    IN  p_email        VARCHAR(150), IN  p_telefono     VARCHAR(20),
    IN  p_empresa      VARCHAR(150), IN  p_fabricante_id INTEGER,
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(200)
)
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM proveedores WHERE proveedor_id = p_proveedor_id) THEN
        p_ok := 0; p_msg := 'Proveedor no encontrado.'; RETURN;
    END IF;
    IF p_fabricante_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM fabricantes WHERE fabricante_id = p_fabricante_id) THEN
        p_ok := 0; p_msg := 'El fabricante seleccionado no existe.'; RETURN;
    END IF;
    IF p_email IS NOT NULL AND
       EXISTS(SELECT 1 FROM proveedores WHERE proveedor_email = LOWER(TRIM(p_email)) AND proveedor_id != p_proveedor_id) THEN
        p_ok := 0; p_msg := 'Ya existe otro proveedor con ese correo electrónico.'; RETURN;
    END IF;
    IF p_telefono IS NOT NULL AND
       EXISTS(SELECT 1 FROM proveedores WHERE proveedor_telefono = TRIM(p_telefono) AND proveedor_id != p_proveedor_id) THEN
        p_ok := 0; p_msg := 'Ya existe otro proveedor con ese teléfono.'; RETURN;
    END IF;
    UPDATE proveedores SET
        proveedor_prim_nombre  = COALESCE(p_prim_nombre, proveedor_prim_nombre),
        proveedor_seg_nombre   = p_seg_nombre,
        proveedor_apellido_pat = COALESCE(p_apellido_pat, proveedor_apellido_pat),
        proveedor_apellido_mat = p_apellido_mat,
        proveedor_email        = LOWER(TRIM(p_email)),
        proveedor_telefono     = TRIM(p_telefono),
        proveedor_empresa      = p_empresa,
        fabricante_id          = COALESCE(p_fabricante_id, fabricante_id)
    WHERE proveedor_id = p_proveedor_id;
    p_ok := 1; p_msg := 'Proveedor actualizado correctamente.';
EXCEPTION
    WHEN unique_violation THEN p_ok := 0; p_msg := 'Ya existe otro proveedor con ese correo o teléfono.';
    WHEN OTHERS THEN p_ok := 0; p_msg := 'No se pudo actualizar el proveedor.';
END; $$;

-- patch_postgres.sql version
CREATE OR REPLACE PROCEDURE sp_eliminar_proveedor(
    IN  p_proveedor_id INTEGER,
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(200)
)
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM proveedores WHERE proveedor_id = p_proveedor_id) THEN
        p_ok := 0; p_msg := 'Proveedor no encontrado.'; RETURN;
    END IF;
    IF EXISTS(SELECT 1 FROM lotes WHERE proveedor_id = p_proveedor_id) THEN
        p_ok := 0; p_msg := 'No se puede eliminar: el proveedor tiene lotes registrados.'; RETURN;
    END IF;
    DELETE FROM proveedores WHERE proveedor_id = p_proveedor_id;
    p_ok := 1; p_msg := 'Proveedor eliminado correctamente.';
EXCEPTION
    WHEN foreign_key_violation THEN p_ok := 0; p_msg := 'No se puede eliminar: hay registros que dependen de este proveedor.';
    WHEN OTHERS THEN p_ok := 0; p_msg := 'No se pudo eliminar el proveedor.';
END; $$;


-- ═══ LOTES ═══

CREATE OR REPLACE PROCEDURE sp_listar_lotes(INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR SELECT * FROM vw_lotes ORDER BY lote_id;
END; $$;

CREATE OR REPLACE PROCEDURE sp_obtener_lote(
    IN p_id INTEGER, INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR SELECT * FROM vw_lotes WHERE lote_id = p_id;
END; $$;

CREATE OR REPLACE PROCEDURE sp_crear_lote(
    IN  p_codigo         VARCHAR(50), IN  p_fecha_fab  DATE,
    IN  p_fecha_cad      DATE,        IN  p_cantidad   INTEGER,
    IN  p_vacuna_id      INTEGER,     IN  p_fabricante_id INTEGER,
    IN  p_proveedor_id   INTEGER,
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(150), OUT p_id INTEGER)
LANGUAGE plpgsql AS $$
BEGIN
    IF TRIM(COALESCE(p_codigo,'')) = '' THEN
        p_ok := 0; p_msg := 'El código de lote es requerido'; RETURN;
    END IF;
    IF p_fecha_cad <= CURRENT_DATE THEN
        p_ok := 0; p_msg := 'La fecha de caducidad debe ser posterior a hoy'; RETURN;
    END IF;
    IF p_fecha_fab >= p_fecha_cad THEN
        p_ok := 0; p_msg := 'La fecha de fabricación debe ser anterior a la de caducidad'; RETURN;
    END IF;
    IF p_cantidad <= 0 THEN
        p_ok := 0; p_msg := 'La cantidad inicial debe ser mayor a 0'; RETURN;
    END IF;
    IF EXISTS(SELECT 1 FROM lotes WHERE lote_codigo = TRIM(p_codigo)) THEN
        p_ok := 0; p_msg := 'El código de lote ya existe'; RETURN;
    END IF;
    INSERT INTO lotes(lote_codigo, lote_fecha_fabricacion, lote_fecha_caducidad,
        lote_cant_inicial, vacuna_id, fabricante_id, proveedor_id)
    VALUES(TRIM(p_codigo), p_fecha_fab, p_fecha_cad, p_cantidad,
           p_vacuna_id, p_fabricante_id, p_proveedor_id)
    RETURNING lote_id INTO p_id;
    p_ok := 1; p_msg := 'Lote registrado correctamente';
EXCEPTION
    WHEN unique_violation   THEN p_ok := 0; p_msg := 'El código de lote ya está registrado';
    WHEN foreign_key_violation THEN p_ok := 0; p_msg := 'Vacuna, fabricante o proveedor no válido';
    WHEN OTHERS THEN p_ok := 0; p_msg := 'Error al crear lote: ' || SQLERRM;
END; $$;

-- patch_postgres.sql version
CREATE OR REPLACE PROCEDURE sp_actualizar_lote(
    IN  p_lote_id           INTEGER,
    IN  p_codigo            VARCHAR(50),
    IN  p_fecha_fabricacion DATE,
    IN  p_fecha_caducidad   DATE,
    IN  p_cant_inicial      INTEGER,
    IN  p_vacuna_id         INTEGER,
    IN  p_fabricante_id     INTEGER,
    IN  p_proveedor_id      INTEGER,
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(200)
)
LANGUAGE plpgsql AS $$
DECLARE
    v_stock_minimo INTEGER;
BEGIN
    IF NOT EXISTS(SELECT 1 FROM lotes WHERE lote_id = p_lote_id) THEN
        p_ok := 0; p_msg := 'Lote no encontrado.'; RETURN;
    END IF;
    IF p_fecha_fabricacion IS NOT NULL AND p_fecha_caducidad IS NOT NULL
       AND p_fecha_caducidad <= p_fecha_fabricacion THEN
        p_ok := 0; p_msg := 'La fecha de caducidad debe ser posterior a la fecha de fabricación.'; RETURN;
    END IF;
    IF p_codigo IS NOT NULL AND
       EXISTS(SELECT 1 FROM lotes WHERE lote_codigo = TRIM(p_codigo) AND lote_id != p_lote_id) THEN
        p_ok := 0; p_msg := 'Ya existe otro lote con ese código.'; RETURN;
    END IF;
    IF p_vacuna_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM vacunas WHERE vacuna_id = p_vacuna_id) THEN
        p_ok := 0; p_msg := 'La vacuna seleccionada no existe.'; RETURN;
    END IF;
    IF p_fabricante_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM fabricantes WHERE fabricante_id = p_fabricante_id) THEN
        p_ok := 0; p_msg := 'El fabricante seleccionado no existe.'; RETURN;
    END IF;
    IF p_proveedor_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM proveedores WHERE proveedor_id = p_proveedor_id) THEN
        p_ok := 0; p_msg := 'El proveedor seleccionado no existe.'; RETURN;
    END IF;
    IF p_cant_inicial IS NOT NULL THEN
        SELECT COALESCE(SUM(inventario_stock_inicial), 0) INTO v_stock_minimo
        FROM inventarios WHERE lote_id = p_lote_id;
        IF p_cant_inicial < v_stock_minimo THEN
            p_ok := 0; p_msg := 'La cantidad inicial no puede ser menor al inventario ya asignado (' || v_stock_minimo || ').'; RETURN;
        END IF;
    END IF;
    UPDATE lotes SET
        lote_codigo            = COALESCE(TRIM(p_codigo), lote_codigo),
        lote_fecha_fabricacion = COALESCE(p_fecha_fabricacion, lote_fecha_fabricacion),
        lote_fecha_caducidad   = COALESCE(p_fecha_caducidad,   lote_fecha_caducidad),
        lote_cant_inicial      = COALESCE(p_cant_inicial,      lote_cant_inicial),
        vacuna_id              = COALESCE(p_vacuna_id,         vacuna_id),
        fabricante_id          = COALESCE(p_fabricante_id,     fabricante_id),
        proveedor_id           = COALESCE(p_proveedor_id,      proveedor_id)
    WHERE lote_id = p_lote_id;
    p_ok := 1; p_msg := 'Lote actualizado correctamente.';
EXCEPTION
    WHEN unique_violation THEN p_ok := 0; p_msg := 'Ya existe otro lote con ese código.';
    WHEN check_violation THEN p_ok := 0; p_msg := 'Las fechas o cantidades del lote no cumplen las validaciones.';
    WHEN OTHERS THEN p_ok := 0; p_msg := 'No se pudo actualizar el lote.';
END; $$;

-- patch_postgres.sql version
CREATE OR REPLACE PROCEDURE sp_eliminar_lote(
    IN  p_lote_id INTEGER,
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(200)
)
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM lotes WHERE lote_id = p_lote_id) THEN
        p_ok := 0; p_msg := 'Lote no encontrado.'; RETURN;
    END IF;
    IF EXISTS(SELECT 1 FROM inventarios WHERE lote_id = p_lote_id) THEN
        p_ok := 0; p_msg := 'No se puede eliminar: el lote tiene inventario asignado en uno o más centros.'; RETURN;
    END IF;
    IF EXISTS(SELECT 1 FROM aplicaciones WHERE lote_id = p_lote_id) THEN
        p_ok := 0; p_msg := 'No se puede eliminar: el lote tiene aplicaciones registradas.'; RETURN;
    END IF;
    DELETE FROM lotes WHERE lote_id = p_lote_id;
    p_ok := 1; p_msg := 'Lote eliminado correctamente.';
EXCEPTION
    WHEN foreign_key_violation THEN p_ok := 0; p_msg := 'No se puede eliminar: hay registros que dependen de este lote.';
    WHEN OTHERS THEN p_ok := 0; p_msg := 'No se pudo eliminar el lote.';
END; $$;


-- ═══ INVENTARIOS ═══

CREATE OR REPLACE PROCEDURE sp_listar_inventarios(INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR SELECT * FROM vw_inventarios ORDER BY inventario_id;
END; $$;

CREATE OR REPLACE PROCEDURE sp_obtener_inventario(
    IN p_id INTEGER, INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR SELECT * FROM vw_inventarios WHERE inventario_id = p_id;
END; $$;

-- patch_caducidad.sql version
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

CREATE OR REPLACE PROCEDURE sp_centros_con_vacuna_disponible(
    IN p_vacuna_id INTEGER, INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
        SELECT * FROM vw_centros_stock_vacuna
        WHERE vacuna_id = p_vacuna_id ORDER BY centro_nombre;
END; $$;

-- patch_caducidad.sql version
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

CREATE OR REPLACE PROCEDURE sp_asignar_inventario(
    IN  p_centro_id     INTEGER, IN  p_lote_id         INTEGER,
    IN  p_stock_inicial INTEGER, IN  p_stock_actual     INTEGER,
    IN  p_activo_desde  TIMESTAMP,
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(150), OUT p_id INTEGER)
LANGUAGE plpgsql AS $$
BEGIN
    IF p_stock_inicial <= 0 THEN
        p_ok := 0; p_msg := 'El stock debe ser mayor a 0'; RETURN;
    END IF;
    IF NOT EXISTS(SELECT 1 FROM centros_salud WHERE centro_id = p_centro_id) THEN
        p_ok := 0; p_msg := 'El centro de salud no existe'; RETURN;
    END IF;
    IF NOT EXISTS(SELECT 1 FROM lotes WHERE lote_id = p_lote_id) THEN
        p_ok := 0; p_msg := 'El lote no existe'; RETURN;
    END IF;
    INSERT INTO inventarios(centro_id, lote_id, inventario_stock_inicial,
        inventario_stock_actual, inventario_activo_desde)
    VALUES(p_centro_id, p_lote_id, p_stock_inicial, p_stock_actual, p_activo_desde)
    RETURNING inventario_id INTO p_id;
    p_ok := 1; p_msg := 'Inventario asignado correctamente';
EXCEPTION
    WHEN check_violation THEN p_ok := 0; p_msg := 'El stock no puede ser negativo';
    WHEN OTHERS THEN p_ok := 0; p_msg := 'Error al asignar inventario: ' || SQLERRM;
END; $$;

-- patch_postgres.sql version
CREATE OR REPLACE PROCEDURE sp_actualizar_inventario(
    IN  p_inventario_id INTEGER,
    IN  p_stock_actual  INTEGER,
    IN  p_activo        INTEGER,
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(200)
)
LANGUAGE plpgsql AS $$
DECLARE
    v_stock_inicial INTEGER;
BEGIN
    IF NOT EXISTS(SELECT 1 FROM inventarios WHERE inventario_id = p_inventario_id) THEN
        p_ok := 0; p_msg := 'Registro de inventario no encontrado.'; RETURN;
    END IF;
    SELECT inventario_stock_inicial INTO v_stock_inicial FROM inventarios WHERE inventario_id = p_inventario_id;
    IF p_stock_actual IS NOT NULL AND p_stock_actual < 0 THEN
        p_ok := 0; p_msg := 'El stock actual no puede ser negativo.'; RETURN;
    END IF;
    IF p_stock_actual IS NOT NULL AND p_stock_actual > v_stock_inicial THEN
        p_ok := 0; p_msg := 'El stock actual no puede exceder el stock inicial (' || v_stock_inicial || ').'; RETURN;
    END IF;
    UPDATE inventarios SET
        inventario_stock_actual = COALESCE(p_stock_actual, inventario_stock_actual),
        inventario_activo_desde = CASE
            WHEN p_activo IS NULL THEN inventario_activo_desde
            WHEN p_activo = 0 THEN NULL
            WHEN p_activo = 1 AND inventario_activo_desde IS NULL THEN CURRENT_TIMESTAMP
            ELSE inventario_activo_desde
        END
    WHERE inventario_id = p_inventario_id;
    p_ok := 1; p_msg := 'Inventario actualizado correctamente.';
EXCEPTION
    WHEN check_violation THEN p_ok := 0; p_msg := 'El stock no cumple las validaciones.';
    WHEN OTHERS THEN p_ok := 0; p_msg := 'No se pudo actualizar el inventario.';
END; $$;

-- patch_postgres.sql version
CREATE OR REPLACE PROCEDURE sp_eliminar_inventario(
    IN  p_inventario_id INTEGER,
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(200)
)
LANGUAGE plpgsql AS $$
DECLARE
    v_centro_id INTEGER;
    v_lote_id   INTEGER;
BEGIN
    SELECT centro_id, lote_id INTO v_centro_id, v_lote_id
    FROM inventarios WHERE inventario_id = p_inventario_id;
    IF v_centro_id IS NULL THEN
        p_ok := 0; p_msg := 'Registro de inventario no encontrado.'; RETURN;
    END IF;
    IF EXISTS(SELECT 1 FROM aplicaciones a
              WHERE a.centro_id = v_centro_id AND a.lote_id = v_lote_id) THEN
        p_ok := 0; p_msg := 'No se puede eliminar: ya hay aplicaciones registradas con este inventario.'; RETURN;
    END IF;
    IF EXISTS(SELECT 1 FROM transferencias_inventario
              WHERE inv_origen_id = p_inventario_id OR inv_destino_id = p_inventario_id) THEN
        p_ok := 0; p_msg := 'No se puede eliminar: el inventario participó en transferencias.'; RETURN;
    END IF;
    IF EXISTS(SELECT 1 FROM inventarios WHERE inventario_origen_id = p_inventario_id) THEN
        p_ok := 0; p_msg := 'No se puede eliminar: otros inventarios provienen de este.'; RETURN;
    END IF;
    DELETE FROM alertas_inventario WHERE inventario_id = p_inventario_id;
    DELETE FROM inventarios WHERE inventario_id = p_inventario_id;
    p_ok := 1; p_msg := 'Inventario eliminado correctamente.';
EXCEPTION
    WHEN foreign_key_violation THEN p_ok := 0; p_msg := 'No se puede eliminar: hay registros que dependen de este inventario.';
    WHEN OTHERS THEN p_ok := 0; p_msg := 'No se pudo eliminar el inventario.';
END; $$;

CREATE OR REPLACE PROCEDURE sp_confirmar_recepcion_inventario(
    IN  p_lote_codigo    VARCHAR(50),
    IN  p_responsable_id INTEGER,
    INOUT p_ok  SMALLINT,
    INOUT p_msg VARCHAR(200)
)
LANGUAGE plpgsql AS $$
DECLARE
    v_lote_id       INTEGER;
    v_centro_id     INTEGER;
    v_inventario_id INTEGER;
BEGIN
    SELECT lote_id INTO v_lote_id
    FROM lotes WHERE lote_codigo = p_lote_codigo;

    IF v_lote_id IS NULL THEN
        p_ok  := 0;
        p_msg := 'No existe ningún lote con ese código. Verifica e intenta de nuevo.';
        RETURN;
    END IF;

    SELECT centro_id INTO v_centro_id
    FROM usuarios WHERE usuario_id = p_responsable_id;

    IF v_centro_id IS NULL THEN
        p_ok  := 0;
        p_msg := 'Tu usuario no tiene un centro de salud asignado.';
        RETURN;
    END IF;

    SELECT inventario_id INTO v_inventario_id
    FROM inventarios
    WHERE lote_id   = v_lote_id
      AND centro_id = v_centro_id
      AND inventario_activo_desde IS NULL
    LIMIT 1;

    IF v_inventario_id IS NULL THEN
        p_ok  := 0;
        p_msg := 'No hay ningún inventario pendiente de activación para ese lote en tu centro de salud.';
        RETURN;
    END IF;

    UPDATE inventarios
    SET inventario_activo_desde = NOW(),
        usuario_id              = p_responsable_id
    WHERE inventario_id = v_inventario_id;

    p_ok  := 1;
    p_msg := 'Inventario activado correctamente.';
END; $$;

-- sps_riesgos_serios.sql version (adds expired-lot guard)
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

CREATE OR REPLACE PROCEDURE sp_listar_transferencias(INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
        SELECT * FROM vw_transferencias ORDER BY transf_timestamp DESC;
END; $$;

-- sps_riesgos_serios.sql version (uses vw_inventarios, adds CERCA_AGOTAR with comments)
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
    SELECT inventario_id, 'CADUCADO'::tipo_alerta_inv
    FROM   vw_inventarios
    WHERE  lote_fecha_caducidad < CURRENT_DATE
      AND  inventario_stock_actual > 0;
    GET DIAGNOSTICS v_total = ROW_COUNT;

    -- CERCA_CADUCAR
    INSERT INTO alertas_inventario(inventario_id, alerta_inv_tipo)
    SELECT inventario_id, 'CERCA_CADUCAR'::tipo_alerta_inv
    FROM   vw_inventarios
    WHERE  lote_fecha_caducidad >= CURRENT_DATE
      AND  lote_fecha_caducidad <= CURRENT_DATE + p_dias_caducidad
      AND  inventario_stock_actual > 0;

    -- AGOTADO
    INSERT INTO alertas_inventario(inventario_id, alerta_inv_tipo)
    SELECT inventario_id, 'AGOTADO'::tipo_alerta_inv
    FROM   vw_inventarios
    WHERE  inventario_stock_actual = 0
      AND  inventario_activo_desde IS NOT NULL;

    -- CERCA_AGOTAR: < 20% del stock inicial
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

CREATE OR REPLACE PROCEDURE sp_listar_alertas_inventario(INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
        SELECT * FROM vw_alertas_inventario ORDER BY alerta_inv_timestamp DESC;
END; $$;

CREATE OR REPLACE PROCEDURE sp_listar_alertas_dosis(INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
        SELECT * FROM vw_alertas_dosis ORDER BY alerta_dosis_pac_timestamp DESC;
END; $$;
-- ═══════════════════════════════════════════════════════════════
-- VacunaTrack — Stored Procedures Part 3
-- Secciones: APLICACIONES · GEOGRAFÍA · BEACON Y GPS
--            DASHBOARD, KPIs Y REPORTES
-- ═══════════════════════════════════════════════════════════════


-- ═══ APLICACIONES ═══

CREATE OR REPLACE PROCEDURE sp_listar_aplicaciones(INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
        SELECT * FROM vw_aplicaciones ORDER BY aplicacion_timestamp DESC;
END; $$;

CREATE OR REPLACE PROCEDURE sp_obtener_aplicacion(
    IN p_id INTEGER, INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR SELECT * FROM vw_aplicaciones WHERE aplicacion_id = p_id;
END; $$;

CREATE OR REPLACE PROCEDURE sp_aplicaciones_de_paciente(
    IN p_paciente_id INTEGER, INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
        SELECT * FROM vw_aplicaciones
        WHERE paciente_id = p_paciente_id ORDER BY aplicacion_timestamp;
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

CREATE OR REPLACE PROCEDURE sp_anular_aplicacion(
    IN  p_aplicacion_id INTEGER,
    IN  p_motivo        TEXT,
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(200)
)
LANGUAGE plpgsql AS $$
DECLARE
    v_centro_id INTEGER;
    v_lote_id   INTEGER;
    v_inv_id    INTEGER;
BEGIN
    SELECT centro_id, lote_id INTO v_centro_id, v_lote_id
    FROM aplicaciones WHERE aplicacion_id = p_aplicacion_id;
    IF v_centro_id IS NULL THEN
        p_ok := 0; p_msg := 'Aplicación no encontrada.'; RETURN;
    END IF;
    SELECT inventario_id INTO v_inv_id
    FROM inventarios
    WHERE centro_id = v_centro_id AND lote_id = v_lote_id
    ORDER BY inventario_id DESC LIMIT 1;
    IF v_inv_id IS NOT NULL THEN
        UPDATE inventarios
        SET inventario_stock_actual = inventario_stock_actual + 1
        WHERE inventario_id = v_inv_id;
    END IF;
    DELETE FROM aplicaciones WHERE aplicacion_id = p_aplicacion_id;
    p_ok := 1; p_msg := 'Aplicación anulada. Motivo: ' || COALESCE(p_motivo, 'sin motivo');
EXCEPTION
    WHEN OTHERS THEN p_ok := 0; p_msg := 'No se pudo anular la aplicación.';
END; $$;

CREATE OR REPLACE PROCEDURE sp_actualizar_aplicacion(
    IN  p_aplicacion_id INTEGER,
    IN  p_observaciones TEXT,
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(200)
)
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM aplicaciones WHERE aplicacion_id = p_aplicacion_id) THEN
        p_ok := 0; p_msg := 'Aplicación no encontrada.'; RETURN;
    END IF;
    UPDATE aplicaciones SET aplicacion_observaciones = p_observaciones
    WHERE aplicacion_id = p_aplicacion_id;
    p_ok := 1; p_msg := 'Aplicación actualizada correctamente.';
EXCEPTION
    WHEN OTHERS THEN p_ok := 0; p_msg := 'No se pudo actualizar la aplicación.';
END; $$;


-- ═══ GEOGRAFÍA ═══

CREATE OR REPLACE PROCEDURE sp_listar_paises(INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR SELECT * FROM vw_paises ORDER BY pais_nombre;
END; $$;

CREATE OR REPLACE PROCEDURE sp_obtener_pais(
    IN p_id INTEGER, INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR SELECT * FROM vw_paises WHERE pais_id = p_id;
END; $$;

CREATE OR REPLACE PROCEDURE sp_crear_pais(
    IN  p_nombre VARCHAR(100),
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(150), OUT p_id INTEGER)
LANGUAGE plpgsql AS $$
BEGIN
    IF TRIM(COALESCE(p_nombre,'')) = '' THEN
        p_ok := 0; p_msg := 'El nombre del país es requerido'; RETURN;
    END IF;
    INSERT INTO paises(pais_nombre) VALUES(TRIM(p_nombre)) RETURNING pais_id INTO p_id;
    p_ok := 1; p_msg := 'País registrado correctamente';
EXCEPTION
    WHEN unique_violation THEN p_ok := 0; p_msg := 'Ya existe un país con ese nombre';
    WHEN OTHERS THEN p_ok := 0; p_msg := 'Error al crear país: ' || SQLERRM;
END; $$;

CREATE OR REPLACE PROCEDURE sp_actualizar_pais(
    IN  p_pais_id INTEGER, IN  p_nombre VARCHAR(100),
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(200)
)
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM paises WHERE pais_id = p_pais_id) THEN
        p_ok := 0; p_msg := 'País no encontrado.'; RETURN;
    END IF;
    IF p_nombre IS NULL OR LENGTH(TRIM(p_nombre)) = 0 THEN
        p_ok := 0; p_msg := 'El nombre del país no puede estar vacío.'; RETURN;
    END IF;
    IF EXISTS(SELECT 1 FROM paises WHERE LOWER(pais_nombre) = LOWER(TRIM(p_nombre)) AND pais_id != p_pais_id) THEN
        p_ok := 0; p_msg := 'Ya existe otro país con ese nombre.'; RETURN;
    END IF;
    UPDATE paises SET pais_nombre = TRIM(p_nombre) WHERE pais_id = p_pais_id;
    p_ok := 1; p_msg := 'País actualizado correctamente.';
EXCEPTION
    WHEN unique_violation THEN p_ok := 0; p_msg := 'Ya existe otro país con ese nombre.';
    WHEN OTHERS THEN p_ok := 0; p_msg := 'No se pudo actualizar el país.';
END; $$;

CREATE OR REPLACE PROCEDURE sp_listar_estados(INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR SELECT * FROM vw_estados ORDER BY estado_nombre;
END; $$;

CREATE OR REPLACE PROCEDURE sp_listar_estados_por_pais(
    IN p_pais_id INTEGER, INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
        SELECT * FROM vw_estados WHERE pais_id = p_pais_id ORDER BY estado_nombre;
END; $$;

CREATE OR REPLACE PROCEDURE sp_obtener_estado(
    IN p_id INTEGER, INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR SELECT * FROM vw_estados WHERE estado_id = p_id;
END; $$;

CREATE OR REPLACE PROCEDURE sp_crear_estado(
    IN  p_nombre  VARCHAR(100), IN  p_pais_id INTEGER,
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(150), OUT p_id INTEGER)
LANGUAGE plpgsql AS $$
BEGIN
    IF TRIM(COALESCE(p_nombre,'')) = '' THEN
        p_ok := 0; p_msg := 'El nombre del estado es requerido'; RETURN;
    END IF;
    IF NOT EXISTS(SELECT 1 FROM paises WHERE pais_id = p_pais_id) THEN
        p_ok := 0; p_msg := 'El país indicado no existe'; RETURN;
    END IF;
    INSERT INTO estados(estado_nombre, pais_id) VALUES(TRIM(p_nombre), p_pais_id)
    RETURNING estado_id INTO p_id;
    p_ok := 1; p_msg := 'Estado registrado correctamente';
EXCEPTION
    WHEN foreign_key_violation THEN p_ok := 0; p_msg := 'El país indicado no existe';
    WHEN OTHERS THEN p_ok := 0; p_msg := 'Error al crear estado: ' || SQLERRM;
END; $$;

CREATE OR REPLACE PROCEDURE sp_actualizar_estado(
    IN  p_estado_id INTEGER, IN  p_nombre VARCHAR(100), IN  p_pais_id INTEGER,
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(200)
)
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM estados WHERE estado_id = p_estado_id) THEN
        p_ok := 0; p_msg := 'Estado no encontrado.'; RETURN;
    END IF;
    IF p_nombre IS NULL OR LENGTH(TRIM(p_nombre)) = 0 THEN
        p_ok := 0; p_msg := 'El nombre del estado no puede estar vacío.'; RETURN;
    END IF;
    IF p_pais_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM paises WHERE pais_id = p_pais_id) THEN
        p_ok := 0; p_msg := 'El país seleccionado no existe.'; RETURN;
    END IF;
    UPDATE estados SET
        estado_nombre = TRIM(p_nombre),
        pais_id       = COALESCE(p_pais_id, pais_id)
    WHERE estado_id = p_estado_id;
    p_ok := 1; p_msg := 'Estado actualizado correctamente.';
EXCEPTION
    WHEN OTHERS THEN p_ok := 0; p_msg := 'No se pudo actualizar el estado.';
END; $$;

CREATE OR REPLACE PROCEDURE sp_listar_ciudades(INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR SELECT * FROM vw_ciudades ORDER BY ciudad_nombre;
END; $$;

CREATE OR REPLACE PROCEDURE sp_listar_ciudades_por_estado(
    IN p_estado_id INTEGER, INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
        SELECT * FROM vw_ciudades WHERE estado_id = p_estado_id ORDER BY ciudad_nombre;
END; $$;

CREATE OR REPLACE PROCEDURE sp_obtener_ciudad(
    IN p_id INTEGER, INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR SELECT * FROM vw_ciudades WHERE ciudad_id = p_id;
END; $$;

CREATE OR REPLACE PROCEDURE sp_crear_ciudad(
    IN  p_nombre     VARCHAR(100), IN  p_estado_id INTEGER,
    OUT p_ok SMALLINT, OUT p_msg VARCHAR(150), OUT p_id INTEGER)
LANGUAGE plpgsql AS $$
BEGIN
    IF TRIM(COALESCE(p_nombre,'')) = '' THEN
        p_ok := 0; p_msg := 'El nombre de la ciudad es requerido'; RETURN;
    END IF;
    IF NOT EXISTS(SELECT 1 FROM estados WHERE estado_id = p_estado_id) THEN
        p_ok := 0; p_msg := 'El estado indicado no existe'; RETURN;
    END IF;
    INSERT INTO ciudades(ciudad_nombre, estado_id) VALUES(TRIM(p_nombre), p_estado_id)
    RETURNING ciudad_id INTO p_id;
    p_ok := 1; p_msg := 'Ciudad registrada correctamente';
EXCEPTION
    WHEN foreign_key_violation THEN p_ok := 0; p_msg := 'El estado indicado no existe';
    WHEN OTHERS THEN p_ok := 0; p_msg := 'Error al crear ciudad: ' || SQLERRM;
END; $$;


-- ═══ BEACON Y GPS ═══

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

CREATE OR REPLACE PROCEDURE sp_vacunas_en_centro(
    IN p_centro_id INTEGER, INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
        SELECT l.vacuna_id,
               v.vacuna_nombre,
               SUM(i.inventario_stock_actual) AS stock_total
        FROM inventarios i
        JOIN lotes   l ON l.lote_id   = i.lote_id
        JOIN vacunas v ON v.vacuna_id = l.vacuna_id
        WHERE i.centro_id = p_centro_id
          AND i.inventario_activo_desde IS NOT NULL
          AND i.inventario_stock_actual > 0
          AND (l.lote_fecha_caducidad IS NULL OR l.lote_fecha_caducidad > CURRENT_DATE)
        GROUP BY l.vacuna_id, v.vacuna_nombre
        ORDER BY v.vacuna_nombre;
END; $$;

CREATE OR REPLACE PROCEDURE sp_tutores_esperando_en_centro(
    IN p_centro_id INTEGER, INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
        SELECT DISTINCT tutor_id
        FROM lecturas_beacon
        WHERE centro_id = p_centro_id
          AND lectura_timestamp > NOW() - INTERVAL '1 hour';
END; $$;

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


-- ═══ DASHBOARD, KPIs Y REPORTES ═══

CREATE OR REPLACE PROCEDURE sp_stats_dashboard(INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR SELECT * FROM vw_stats_dashboard;
END; $$;

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
        (SELECT COUNT(DISTINCT centro_id) FROM vw_aplicaciones
         WHERE aplicacion_timestamp >= NOW() - INTERVAL '30 days')                            AS centros_activos_30d,
        -- 6-9: Aplicaciones
        (SELECT COUNT(*) FROM vw_aplicaciones)                                                AS total_aplicaciones,
        (SELECT COUNT(*) FROM vw_aplicaciones
         WHERE DATE(aplicacion_timestamp) = CURRENT_DATE)                                     AS aplicaciones_hoy,
        (SELECT COUNT(*) FROM vw_aplicaciones
         WHERE DATE_TRUNC('month', aplicacion_timestamp) = DATE_TRUNC('month', NOW()))        AS aplicaciones_mes,
        ROUND(
            (SELECT COUNT(*) FROM vw_aplicaciones
             WHERE DATE_TRUNC('month', aplicacion_timestamp) = DATE_TRUNC('month', NOW()))
            ::NUMERIC
            / NULLIF(EXTRACT(DAY FROM NOW())::INTEGER, 0), 1)                                 AS promedio_diario_mes,
        -- 10-11: Cobertura y pacientes sin vacunar
        ROUND(
            (SELECT COUNT(DISTINCT paciente_id) FROM vw_aplicaciones)::NUMERIC
            / NULLIF((SELECT COUNT(*) FROM vw_pacientes), 0) * 100, 1)                        AS pct_cobertura_global,
        (SELECT COUNT(*) FROM vw_pacientes p
         WHERE NOT EXISTS (SELECT 1 FROM vw_aplicaciones a
                           WHERE a.paciente_id = p.paciente_id))                              AS pacientes_sin_aplicaciones,
        -- 12-14: Catálogo clínico
        (SELECT COUNT(*) FROM vw_vacunas)                                                     AS total_vacunas,
        (SELECT COUNT(*) FROM vw_esquemas)                                                    AS total_esquemas,
        (SELECT COUNT(*) FROM vw_padecimientos)                                               AS total_padecimientos,
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
            (SELECT COUNT(DISTINCT centro_id) FROM vw_aplicaciones
             WHERE aplicacion_timestamp >= NOW() - INTERVAL '30 days')::NUMERIC
            / NULLIF((SELECT COUNT(*) FROM vw_centros_detalle), 0) * 100, 1)                  AS pct_centros_activos_30d;
END; $$;

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

CREATE OR REPLACE PROCEDURE sp_ranking_centros_actividad(
    IN  p_meses       INTEGER,        -- ventana de lookback en meses
    INOUT p_resultados REFCURSOR
)
LANGUAGE plpgsql AS $$
BEGIN
    -- Tabla temporal: conteos por centro
    CREATE TEMP TABLE tmp_ranking_centros ON COMMIT DROP AS
    SELECT
        cd.centro_id,
        cd.centro_nombre,
        cd.ciudad_nombre,
        COUNT(a.aplicacion_id)                                              AS total_aplicaciones,
        COUNT(a.aplicacion_id)
            FILTER (WHERE a.aplicacion_timestamp >= NOW() - (p_meses || ' months')::INTERVAL)
                                                                            AS aplicaciones_periodo,
        COUNT(DISTINCT a.paciente_id)                                       AS pacientes_atendidos,
        COUNT(DISTINCT DATE(a.aplicacion_timestamp))                        AS dias_con_actividad
    FROM vw_centros cd
    LEFT JOIN vw_aplicaciones a ON a.centro_id = cd.centro_id
    GROUP BY cd.centro_id, cd.centro_nombre, cd.ciudad_nombre;

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
    FROM vw_pacientes WHERE esquema_id = p_esquema_id;

    -- Tabla temporal: aplicaciones por dosis del esquema
    CREATE TEMP TABLE tmp_cobertura ON COMMIT DROP AS
    SELECT
        de.vacuna_id,
        de.vacuna_nombre,
        de.dosis_id,
        de.dosis_tipo,
        de.dosis_edad_oportuna_dias,
        v_total_pacientes                                                   AS total_pacientes,
        COUNT(DISTINCT a.paciente_id)                                       AS pacientes_con_dosis,
        COUNT(a.aplicacion_id)                                              AS total_aplicaciones
    FROM vw_dosis_esquemas_detalle de
    LEFT JOIN vw_aplicaciones a ON a.dosis_id = de.dosis_id
        AND a.paciente_id IN (
            SELECT paciente_id FROM vw_pacientes WHERE esquema_id = p_esquema_id
        )
    WHERE de.esquema_id = p_esquema_id
    GROUP BY de.vacuna_id, de.vacuna_nombre, de.dosis_id, de.dosis_tipo, de.dosis_edad_oportuna_dias;

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
        INITCAP(p.paciente_prim_nombre) || ' ' || INITCAP(p.paciente_apellido_pat)::VARCHAR(100) AS paciente_nombre,
        p.paciente_fecha_nac,
        EXTRACT(DAY FROM NOW() - p.paciente_fecha_nac)::INTEGER                    AS edad_dias,
        de.vacuna_nombre,
        de.dosis_id,
        de.dosis_tipo,
        de.dosis_edad_oportuna_dias,
        de.dosis_limite_edad_dias,
        (EXTRACT(DAY FROM NOW() - p.paciente_fecha_nac)::INTEGER
            - de.dosis_edad_oportuna_dias)                                         AS dias_atraso,
        (de.dosis_limite_edad_dias
            - EXTRACT(DAY FROM NOW() - p.paciente_fecha_nac)::INTEGER)            AS dias_para_limite
    FROM vw_pacientes p
    JOIN vw_dosis_esquemas_detalle de ON de.esquema_id = p.esquema_id
    -- La dosis no ha sido aplicada
    WHERE NOT EXISTS (
        SELECT 1 FROM vw_aplicaciones a
        WHERE a.paciente_id = p.paciente_id AND a.dosis_id = de.dosis_id
    )
    -- El paciente ya superó la edad oportuna de la dosis
    AND EXTRACT(DAY FROM NOW() - p.paciente_fecha_nac) > de.dosis_edad_oportuna_dias
    -- La dosis aún está dentro del límite de edad (o no tiene límite)
    AND (de.dosis_limite_edad_dias IS NULL
         OR EXTRACT(DAY FROM NOW() - p.paciente_fecha_nac) <= de.dosis_limite_edad_dias)
    -- Filtro por centro (si se proporciona)
    AND (p_centro_id IS NULL OR EXISTS (
        SELECT 1 FROM vw_aplicaciones a2
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

-- ═══ DASHBOARD RESPONSABLE ═══

CREATE OR REPLACE PROCEDURE sp_dashboard_responsable_stats(
    IN  p_usuario_id INTEGER,
    IN  p_centro_id  INTEGER,
    INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
    SELECT
        (SELECT COUNT(*)
         FROM aplicaciones
         WHERE usuario_id = p_usuario_id
           AND DATE(aplicacion_timestamp) = CURRENT_DATE
        ) AS aplicaciones_hoy,
        (SELECT COUNT(DISTINCT paciente_id)
         FROM aplicaciones
         WHERE usuario_id = p_usuario_id
           AND DATE(aplicacion_timestamp) = CURRENT_DATE
        ) AS pacientes_hoy,
        (SELECT COUNT(*)
         FROM inventarios
         WHERE centro_id = p_centro_id
           AND inventario_activo_desde IS NULL
        ) AS pendientes_confirmacion;
END; $$;

CREATE OR REPLACE PROCEDURE sp_inventario_con_alertas_de_centro(
    IN  p_centro_id  INTEGER,
    INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
    SELECT
        v.inventario_id,
        v.vacuna_nombre,
        v.lote_codigo,
        v.lote_fecha_caducidad,
        v.inventario_stock_actual,
        v.inventario_activo,
        (SELECT ai.alerta_inv_tipo::text
         FROM alertas_inventario ai
         WHERE ai.inventario_id = v.inventario_id
         ORDER BY ai.alerta_inv_timestamp DESC
         LIMIT 1) AS alerta_tipo
    FROM vw_inventarios v
    WHERE v.centro_id = p_centro_id
      AND v.inventario_activo_desde IS NOT NULL
    ORDER BY v.vacuna_nombre;
END; $$;

CREATE OR REPLACE PROCEDURE sp_lotes_proximos_caducar_centro(
    IN  p_centro_id INTEGER,
    IN  p_dias      INTEGER,
    INOUT p_resultados REFCURSOR)
LANGUAGE plpgsql AS $$
BEGIN
    OPEN p_resultados FOR
    SELECT
        v.vacuna_nombre,
        v.lote_codigo,
        v.lote_fecha_caducidad,
        v.inventario_stock_actual,
        (v.lote_fecha_caducidad - CURRENT_DATE) AS dias_restantes
    FROM vw_inventarios v
    WHERE v.centro_id = p_centro_id
      AND v.inventario_activo_desde IS NOT NULL
      AND v.inventario_stock_actual > 0
      AND v.lote_fecha_caducidad BETWEEN CURRENT_DATE AND (CURRENT_DATE + p_dias)
    ORDER BY v.lote_fecha_caducidad;
END; $$;

\c vacunatrack;

-- ─────────────────────────────────────────────
-- GEOGRAFÍA
-- ─────────────────────────────────────────────
INSERT INTO paises (pais_nombre) VALUES ('México');

INSERT INTO estados (estado_nombre, pais_id) VALUES
    ('Jalisco',          (SELECT pais_id FROM paises WHERE pais_nombre = 'México')),
    ('Ciudad de México', (SELECT pais_id FROM paises WHERE pais_nombre = 'México')),
    ('Nuevo León',       (SELECT pais_id FROM paises WHERE pais_nombre = 'México'));

INSERT INTO ciudades (ciudad_nombre, estado_id) VALUES
    ('Guadalajara',     (SELECT estado_id FROM estados WHERE estado_nombre = 'Jalisco')),
    ('Zapopan',         (SELECT estado_id FROM estados WHERE estado_nombre = 'Jalisco')),
    ('Ciudad de México',(SELECT estado_id FROM estados WHERE estado_nombre = 'Ciudad de México')),
    ('Monterrey',       (SELECT estado_id FROM estados WHERE estado_nombre = 'Nuevo León'));

-- ─────────────────────────────────────────────
-- CATÁLOGOS CLÍNICOS
-- ─────────────────────────────────────────────
INSERT INTO vacunas (vacuna_nombre, vacuna_activa) VALUES
    ('BCG',              true),
    ('Hepatitis B',      true),
    ('Pentavalente',     true),
    ('Neumocócica',      true),
    ('Rotavirus',        true),
    ('Triple Viral (SRP)', true),
    ('Influenza',        true);

INSERT INTO padecimientos (padecimiento_nombre, padecimiento_descripcion, padecimiento_activo) VALUES
    ('Tuberculosis', 'Enfermedad infecciosa bacteriana crónica',         true),
    ('Hepatitis B',  'Infección viral del hígado',                       true),
    ('Tosferina',    'Infección respiratoria bacteriana',                 true),
    ('Sarampión',    'Enfermedad viral altamente contagiosa',             true),
    ('Rubéola',      'Infección viral leve pero peligrosa en embarazo',  true),
    ('Parotiditis',  'Infección viral de las glándulas salivales',       true),
    ('Influenza',    'Infección viral respiratoria estacional',           true);

INSERT INTO vacunas_padecimientos (vacuna_id, padecimiento_id) VALUES
    ((SELECT vacuna_id FROM vacunas WHERE vacuna_nombre = 'BCG'),
     (SELECT padecimiento_id FROM padecimientos WHERE padecimiento_nombre = 'Tuberculosis')),
    ((SELECT vacuna_id FROM vacunas WHERE vacuna_nombre = 'Hepatitis B'),
     (SELECT padecimiento_id FROM padecimientos WHERE padecimiento_nombre = 'Hepatitis B')),
    ((SELECT vacuna_id FROM vacunas WHERE vacuna_nombre = 'Pentavalente'),
     (SELECT padecimiento_id FROM padecimientos WHERE padecimiento_nombre = 'Tosferina')),
    ((SELECT vacuna_id FROM vacunas WHERE vacuna_nombre = 'Triple Viral (SRP)'),
     (SELECT padecimiento_id FROM padecimientos WHERE padecimiento_nombre = 'Sarampión')),
    ((SELECT vacuna_id FROM vacunas WHERE vacuna_nombre = 'Triple Viral (SRP)'),
     (SELECT padecimiento_id FROM padecimientos WHERE padecimiento_nombre = 'Rubéola')),
    ((SELECT vacuna_id FROM vacunas WHERE vacuna_nombre = 'Triple Viral (SRP)'),
     (SELECT padecimiento_id FROM padecimientos WHERE padecimiento_nombre = 'Parotiditis')),
    ((SELECT vacuna_id FROM vacunas WHERE vacuna_nombre = 'Influenza'),
     (SELECT padecimiento_id FROM padecimientos WHERE padecimiento_nombre = 'Influenza'));

INSERT INTO esquemas (esquema_nombre, esquema_fecha_vigencia, esquema_vigente_desde) VALUES
    ('Esquema Nacional de Vacunación 2024', '2024-01-01', '2024-01-01');

INSERT INTO dosis (vacuna_id, dosis_tipo, dosis_cant_ml, dosis_area_aplicacion,
                   dosis_edad_oportuna_dias, dosis_intervalo_min_dias, dosis_limite_edad_dias) VALUES
    ((SELECT vacuna_id FROM vacunas WHERE vacuna_nombre = 'BCG'),
     'UNICA',          0.1, 'Deltoides derecho',    0,   0,   365),
    ((SELECT vacuna_id FROM vacunas WHERE vacuna_nombre = 'Hepatitis B'),
     'SERIE_PRIMARIA', 0.5, 'Muslo derecho',         0,   0,    30),
    ((SELECT vacuna_id FROM vacunas WHERE vacuna_nombre = 'Hepatitis B'),
     'SERIE_PRIMARIA', 0.5, 'Muslo derecho',        60,  28,   365),
    ((SELECT vacuna_id FROM vacunas WHERE vacuna_nombre = 'Pentavalente'),
     'SERIE_PRIMARIA', 0.5, 'Muslo izquierdo',      60,  28,   365),
    ((SELECT vacuna_id FROM vacunas WHERE vacuna_nombre = 'Pentavalente'),
     'SERIE_PRIMARIA', 0.5, 'Muslo izquierdo',     120,  28,   548),
    ((SELECT vacuna_id FROM vacunas WHERE vacuna_nombre = 'Pentavalente'),
     'SERIE_PRIMARIA', 0.5, 'Muslo izquierdo',     180,  28,   730),
    ((SELECT vacuna_id FROM vacunas WHERE vacuna_nombre = 'Neumocócica'),
     'SERIE_PRIMARIA', 0.5, 'Muslo derecho',        60,  56,   365),
    ((SELECT vacuna_id FROM vacunas WHERE vacuna_nombre = 'Neumocócica'),
     'SERIE_PRIMARIA', 0.5, 'Muslo derecho',       180,  56,   548),
    ((SELECT vacuna_id FROM vacunas WHERE vacuna_nombre = 'Rotavirus'),
     'SERIE_PRIMARIA', 1.5, 'Oral',                 60,  28,   240),
    ((SELECT vacuna_id FROM vacunas WHERE vacuna_nombre = 'Rotavirus'),
     'SERIE_PRIMARIA', 1.5, 'Oral',                120,  28,   240),
    ((SELECT vacuna_id FROM vacunas WHERE vacuna_nombre = 'Triple Viral (SRP)'),
     'UNICA',          0.5, 'Deltoides izquierdo', 365,   0,   548),
    ((SELECT vacuna_id FROM vacunas WHERE vacuna_nombre = 'Influenza'),
     'ANUAL',          0.5, 'Deltoides derecho',   180,   0,  NULL);

-- Vincular todas las dosis al único esquema
INSERT INTO dosis_esquemas (esquema_id, dosis_id)
SELECT (SELECT esquema_id FROM esquemas WHERE esquema_nombre = 'Esquema Nacional de Vacunación 2024'),
       dosis_id
FROM dosis;

-- ─────────────────────────────────────────────
-- CENTROS DE SALUD
-- ─────────────────────────────────────────────
INSERT INTO centros_salud (centro_nombre, centro_calle, centro_numero,
    centro_codigo_postal, ciudad_id, centro_horario_inicio, centro_horario_fin,
    centro_latitud, centro_longitud, centro_telefono) VALUES
    ('Centro de Salud Zona Norte', 'Av. Vallarta',   '1234', '44100',
     (SELECT ciudad_id FROM ciudades WHERE ciudad_nombre = 'Guadalajara'),
     '08:00', '17:00', 20.67360, -103.34430, '3312345678'),
    ('Centro de Salud Zapopan',    'Blvd. Aviación', '500',  '45010',
     (SELECT ciudad_id FROM ciudades WHERE ciudad_nombre = 'Zapopan'),
     '07:00', '15:00', 20.72060, -103.38270, '3398765432'),
    ('IMSS Unidad Médica Sur',     'Insurgentes Sur','3700', '14080',
     (SELECT ciudad_id FROM ciudades WHERE ciudad_nombre = 'Ciudad de México'),
     '08:00', '20:00', 19.32160,  -99.18490, '5512345678');

-- ─────────────────────────────────────────────
-- ROLES
-- ─────────────────────────────────────────────
INSERT INTO roles (rol_nombre) VALUES ('admin'), ('responsable'), ('tutor');

-- ─────────────────────────────────────────────
-- USUARIOS, LOGIN Y ROLES
-- ─────────────────────────────────────────────

-- Admin
WITH u AS (
    INSERT INTO usuarios (usuario_prim_nombre, usuario_apellido_pat,
        usuario_telefono, usuario_curp, usuario_rfc, usuario_activo)
    VALUES ('Admin', 'Sistema', '3300000001', 'ADMS800101HJLMNA01', 'ADMS800101AB1', true)
    RETURNING usuario_id
)
INSERT INTO login (usuario_id, login_correo, login_contrasena)
SELECT usuario_id, 'admin@vacunatrack.mx',
    'pbkdf2:sha256:600000$8RTrouFB5J9YLQ6b$68495ba1488f0cf18a613482d17eabef7e8045b65e5e8fa32940d7620017ab38'
FROM u;

INSERT INTO usuarios_roles (usuario_id, rol_id)
SELECT u.usuario_id, r.rol_id FROM usuarios u CROSS JOIN roles r
WHERE u.usuario_curp = 'ADMS800101HJLMNA01' AND r.rol_nombre = 'admin';

-- Responsable (asignado al Centro de Salud Zona Norte)
WITH u AS (
    INSERT INTO usuarios (usuario_prim_nombre, usuario_seg_nombre, usuario_apellido_pat,
        usuario_apellido_mat, usuario_telefono, usuario_curp, usuario_rfc, centro_id, usuario_activo)
    SELECT 'Diego', 'Alejandro', 'Mendoza', 'García', '3311112222',
           'MEGA950315HJLRDA01', 'MEGA950315AB2',
           (SELECT centro_id FROM centros_salud WHERE centro_nombre = 'Centro de Salud Zona Norte'),
           true
    RETURNING usuario_id
)
INSERT INTO login (usuario_id, login_correo, login_contrasena)
SELECT usuario_id, 'diego@vacunatrack.mx',
    'pbkdf2:sha256:600000$EbunBmcTleKquDqZ$02da4288d39e3e5070d1f8de052114319357bb2993dd47b5628ced9e1119eda6'
FROM u;

INSERT INTO usuarios_roles (usuario_id, rol_id)
SELECT u.usuario_id, r.rol_id FROM usuarios u CROSS JOIN roles r
WHERE u.usuario_curp = 'MEGA950315HJLRDA01' AND r.rol_nombre = 'responsable';

INSERT INTO cedulas (cedula_numero, cedula_especialidad, usuario_id)
SELECT 'CED-2024-001', 'Medicina General', usuario_id
FROM usuarios WHERE usuario_curp = 'MEGA950315HJLRDA01';

-- Tutor
WITH u AS (
    INSERT INTO usuarios (usuario_prim_nombre, usuario_apellido_pat,
        usuario_telefono, usuario_curp, usuario_activo)
    VALUES ('Juan', 'Pérez', '3322223333', 'PEJA900202HJLRNA01', true)
    RETURNING usuario_id
)
INSERT INTO login (usuario_id, login_correo, login_contrasena)
SELECT usuario_id, 'juan@correo.mx',
    'pbkdf2:sha256:600000$PtIINqubBppt2cNj$9ff0bb057cb153995b9ab3147cb4bc6d0dd117fe6a1a70d51a53d53f5748e846'
FROM u;

INSERT INTO usuarios_roles (usuario_id, rol_id)
SELECT u.usuario_id, r.rol_id FROM usuarios u CROSS JOIN roles r
WHERE u.usuario_curp = 'PEJA900202HJLRNA01' AND r.rol_nombre = 'tutor';

-- ─────────────────────────────────────────────
-- PACIENTES
-- ─────────────────────────────────────────────
INSERT INTO pacientes (paciente_prim_nombre, paciente_apellido_pat,
    paciente_apellido_mat, paciente_curp, paciente_fecha_nac, paciente_sexo, esquema_id) VALUES
    ('Sofía',     'Pérez',     'López',    'PELS240101MJLRFA01', '2024-01-15', 'F',
     (SELECT esquema_id FROM esquemas WHERE esquema_nombre = 'Esquema Nacional de Vacunación 2024')),
    ('Mateo',     'Pérez',     'López',    'PELM220601HJLRTA01', '2022-06-01', 'M',
     (SELECT esquema_id FROM esquemas WHERE esquema_nombre = 'Esquema Nacional de Vacunación 2024')),
    ('Valentina', 'Rodríguez', 'Martínez', 'ROMV231101MJLRLA01', '2023-11-01', 'F',
     (SELECT esquema_id FROM esquemas WHERE esquema_nombre = 'Esquema Nacional de Vacunación 2024'));

INSERT INTO pacientes_tutores (paciente_id, tutor_id)
SELECT p.paciente_id, u.usuario_id
FROM pacientes p CROSS JOIN usuarios u
WHERE p.paciente_curp IN ('PELS240101MJLRFA01', 'PELM220601HJLRTA01')
  AND u.usuario_curp = 'PEJA900202HJLRNA01';

-- ─────────────────────────────────────────────
-- FABRICANTES Y PROVEEDORES
-- ─────────────────────────────────────────────
INSERT INTO fabricantes (fabricante_nombre, fabricante_telefono, pais_id) VALUES
    ('Sanofi Pasteur', '+33123456789', (SELECT pais_id FROM paises WHERE pais_nombre = 'México')),
    ('Pfizer',         '+12125734000', (SELECT pais_id FROM paises WHERE pais_nombre = 'México')),
    ('BIRMEX',         '5551234567',   (SELECT pais_id FROM paises WHERE pais_nombre = 'México'));

INSERT INTO proveedores (proveedor_prim_nombre, proveedor_apellido_pat,
    proveedor_email, proveedor_telefono, proveedor_empresa, fabricante_id) VALUES
    ('Carlos', 'Ramírez', 'carlos@distribmedica.mx', '3344445555', 'Distribuidora Médica MX',
     (SELECT fabricante_id FROM fabricantes WHERE fabricante_nombre = 'Sanofi Pasteur')),
    ('Laura',  'Torres',  'laura@farmasur.mx',       '3355556666', 'FarmaSur SA de CV',
     (SELECT fabricante_id FROM fabricantes WHERE fabricante_nombre = 'BIRMEX'));

-- ─────────────────────────────────────────────
-- LOTES E INVENTARIOS
-- ─────────────────────────────────────────────
INSERT INTO lotes (lote_codigo, lote_fecha_fabricacion, lote_fecha_caducidad,
    lote_cant_inicial, vacuna_id, fabricante_id, proveedor_id) VALUES
    ('BCG-2025-001',  '2025-01-01', '2027-12-31', 500,
     (SELECT vacuna_id FROM vacunas WHERE vacuna_nombre = 'BCG'),
     (SELECT fabricante_id FROM fabricantes WHERE fabricante_nombre = 'BIRMEX'),
     (SELECT proveedor_id FROM proveedores WHERE proveedor_empresa = 'FarmaSur SA de CV')),
    ('HEPB-2025-001', '2025-02-01', '2027-01-31', 300,
     (SELECT vacuna_id FROM vacunas WHERE vacuna_nombre = 'Hepatitis B'),
     (SELECT fabricante_id FROM fabricantes WHERE fabricante_nombre = 'Sanofi Pasteur'),
     (SELECT proveedor_id FROM proveedores WHERE proveedor_empresa = 'Distribuidora Médica MX')),
    ('PENT-2025-001', '2025-03-01', '2027-02-28', 400,
     (SELECT vacuna_id FROM vacunas WHERE vacuna_nombre = 'Pentavalente'),
     (SELECT fabricante_id FROM fabricantes WHERE fabricante_nombre = 'Sanofi Pasteur'),
     (SELECT proveedor_id FROM proveedores WHERE proveedor_empresa = 'Distribuidora Médica MX')),
    ('NEUM-2025-001', '2025-03-01', '2027-03-31', 200,
     (SELECT vacuna_id FROM vacunas WHERE vacuna_nombre = 'Neumocócica'),
     (SELECT fabricante_id FROM fabricantes WHERE fabricante_nombre = 'Pfizer'),
     (SELECT proveedor_id FROM proveedores WHERE proveedor_empresa = 'Distribuidora Médica MX')),
    ('ROTA-2025-001', '2025-04-01', '2027-10-31', 250,
     (SELECT vacuna_id FROM vacunas WHERE vacuna_nombre = 'Rotavirus'),
     (SELECT fabricante_id FROM fabricantes WHERE fabricante_nombre = 'Sanofi Pasteur'),
     (SELECT proveedor_id FROM proveedores WHERE proveedor_empresa = 'Distribuidora Médica MX')),
    ('SRP-2025-001',  '2025-01-15', '2027-01-14', 150,
     (SELECT vacuna_id FROM vacunas WHERE vacuna_nombre = 'Triple Viral (SRP)'),
     (SELECT fabricante_id FROM fabricantes WHERE fabricante_nombre = 'Sanofi Pasteur'),
     (SELECT proveedor_id FROM proveedores WHERE proveedor_empresa = 'Distribuidora Médica MX')),
    ('FLU-2025-001',  '2025-09-01', '2027-04-30', 600,
     (SELECT vacuna_id FROM vacunas WHERE vacuna_nombre = 'Influenza'),
     (SELECT fabricante_id FROM fabricantes WHERE fabricante_nombre = 'Pfizer'),
     (SELECT proveedor_id FROM proveedores WHERE proveedor_empresa = 'Distribuidora Médica MX'));

INSERT INTO inventarios (centro_id, lote_id, inventario_stock_inicial,
    inventario_stock_actual, inventario_activo_desde, usuario_id)
SELECT c.centro_id, l.lote_id, s.ini, s.act, now(), u.usuario_id
FROM (VALUES
    ('Centro de Salud Zona Norte', 'BCG-2025-001',  100, 98),
    ('Centro de Salud Zona Norte', 'HEPB-2025-001',  80, 79),
    ('Centro de Salud Zona Norte', 'PENT-2025-001', 120,118),
    ('Centro de Salud Zona Norte', 'NEUM-2025-001',  60, 60),
    ('Centro de Salud Zona Norte', 'ROTA-2025-001',  80, 80),
    ('Centro de Salud Zona Norte', 'SRP-2025-001',   50, 50),
    ('Centro de Salud Zona Norte', 'FLU-2025-001',  200,200),
    ('Centro de Salud Zapopan',    'BCG-2025-001',   80, 80),
    ('Centro de Salud Zapopan',    'PENT-2025-001', 100,100),
    ('IMSS Unidad Médica Sur',     'FLU-2025-001',  150,150)
) AS s(centro_nombre, lote_codigo, ini, act)
JOIN centros_salud c ON c.centro_nombre = s.centro_nombre
JOIN lotes         l ON l.lote_codigo   = s.lote_codigo
JOIN usuarios      u ON u.usuario_curp  = 'MEGA950315HJLRDA01';

-- ─────────────────────────────────────────────
-- APLICACIONES DE EJEMPLO
-- ─────────────────────────────────────────────
INSERT INTO aplicaciones (paciente_id, usuario_id, centro_id, lote_id, dosis_id,
    aplicacion_timestamp, aplicacion_observaciones)
SELECT p.paciente_id, u.usuario_id, c.centro_id, l.lote_id, d.dosis_id,
       a.ts::timestamp, a.obs
FROM (VALUES
    ('PELS240101MJLRFA01', 'BCG-2025-001',  'BCG',       'UNICA',          0, '2024-01-15 09:00:00', 'Aplicación al nacer sin complicaciones'),
    ('PELS240101MJLRFA01', 'HEPB-2025-001', 'Hepatitis B','SERIE_PRIMARIA', 0, '2024-01-15 09:10:00', 'Primera dosis Hepatitis B'),
    ('PELM220601HJLRTA01', 'BCG-2025-001',  'BCG',       'UNICA',          0, '2022-06-01 10:00:00', 'BCG al nacer'),
    ('PELM220601HJLRTA01', 'HEPB-2025-001', 'Hepatitis B','SERIE_PRIMARIA', 0, '2022-06-01 10:15:00', 'Hepatitis B primera dosis')
) AS a(curp_pac, lote_codigo, vacuna_nombre, dosis_tipo, edad_dias, ts, obs)
JOIN pacientes    p ON p.paciente_curp = a.curp_pac
JOIN usuarios     u ON u.usuario_curp  = 'MEGA950315HJLRDA01'
JOIN centros_salud c ON c.centro_nombre = 'Centro de Salud Zona Norte'
JOIN lotes        l ON l.lote_codigo   = a.lote_codigo
JOIN vacunas      v ON v.vacuna_nombre = a.vacuna_nombre
JOIN dosis        d ON d.vacuna_id     = v.vacuna_id
                   AND d.dosis_tipo    = a.dosis_tipo
                   AND d.dosis_edad_oportuna_dias = a.edad_dias;

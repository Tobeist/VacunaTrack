\c vacunatrack;

-- ─────────────────────────────────────────────
-- GEOGRAFÍA
-- ─────────────────────────────────────────────
INSERT INTO paises (pais_id, pais_nombre) VALUES (1, 'México');

INSERT INTO estados (estado_id, estado_nombre, pais_id) VALUES
    (1, 'Jalisco', 1),
    (2, 'Ciudad de México', 1),
    (3, 'Nuevo León', 1);

INSERT INTO ciudades (ciudad_id, ciudad_nombre, estado_id) VALUES
    (1, 'Guadalajara', 1),
    (2, 'Zapopan', 1),
    (3, 'Ciudad de México', 2),
    (4, 'Monterrey', 3);

-- ─────────────────────────────────────────────
-- CATÁLOGOS CLÍNICOS
-- ─────────────────────────────────────────────
INSERT INTO vacunas (vacuna_id, vacuna_nombre, vacuna_activa) VALUES
    (1, 'BCG', true),
    (2, 'Hepatitis B', true),
    (3, 'Pentavalente', true),
    (4, 'Neumocócica', true),
    (5, 'Rotavirus', true),
    (6, 'Triple Viral (SRP)', true),
    (7, 'Influenza', true);

INSERT INTO padecimientos (padecimiento_id, padecimiento_nombre, padecimiento_descripcion, padecimiento_activo) VALUES
    (1, 'Tuberculosis', 'Enfermedad infecciosa bacteriana crónica', true),
    (2, 'Hepatitis B', 'Infección viral del hígado', true),
    (3, 'Tosferina', 'Infección respiratoria bacteriana', true),
    (4, 'Sarampión', 'Enfermedad viral altamente contagiosa', true),
    (5, 'Rubéola', 'Infección viral leve pero peligrosa en embarazo', true),
    (6, 'Parotiditis', 'Infección viral de las glándulas salivales', true),
    (7, 'Influenza', 'Infección viral respiratoria estacional', true);

INSERT INTO vacunas_padecimientos (vacuna_id, padecimiento_id) VALUES
    (1, 1), (2, 2), (3, 3), (6, 4), (6, 5), (6, 6), (7, 7);

INSERT INTO esquemas (esquema_id, esquema_nombre, esquema_fecha_vigencia, esquema_vigente_desde) VALUES
    (1, 'Esquema Nacional de Vacunación 2024', '2024-01-01', '2024-01-01');

INSERT INTO dosis (dosis_id, vacuna_id, dosis_tipo, dosis_cant_ml, dosis_area_aplicacion,
                   dosis_edad_oportuna_dias, dosis_intervalo_min_dias, dosis_limite_edad_dias) VALUES
    (1,  1, 'UNICA',         0.1,  'Deltoides derecho',    0,   0,    365),
    (2,  2, 'SERIE_PRIMARIA', 0.5, 'Muslo derecho',         0,   0,    30),
    (3,  2, 'SERIE_PRIMARIA', 0.5, 'Muslo derecho',        60,  28,   365),
    (4,  3, 'SERIE_PRIMARIA', 0.5, 'Muslo izquierdo',      60,  28,   365),
    (5,  3, 'SERIE_PRIMARIA', 0.5, 'Muslo izquierdo',     120,  28,   548),
    (6,  3, 'SERIE_PRIMARIA', 0.5, 'Muslo izquierdo',     180,  28,   730),
    (7,  4, 'SERIE_PRIMARIA', 0.5, 'Muslo derecho',        60,  56,   365),
    (8,  4, 'SERIE_PRIMARIA', 0.5, 'Muslo derecho',       180,  56,   548),
    (9,  5, 'SERIE_PRIMARIA', 1.5, 'Oral',                 60,  28,   240),
    (10, 5, 'SERIE_PRIMARIA', 1.5, 'Oral',                120,  28,   240),
    (11, 6, 'UNICA',          0.5, 'Deltoides izquierdo', 365,   0,   548),
    (12, 7, 'ANUAL',          0.5, 'Deltoides derecho',   180,   0,  NULL);

INSERT INTO dosis_esquemas (esquema_id, dosis_id) VALUES
    (1,1),(1,2),(1,3),(1,4),(1,5),(1,6),(1,7),(1,8),(1,9),(1,10),(1,11),(1,12);

-- ─────────────────────────────────────────────
-- CENTROS DE SALUD
-- ─────────────────────────────────────────────
INSERT INTO centros_salud (centro_id, centro_nombre, centro_calle, centro_numero,
    centro_codigo_postal, ciudad_id, centro_horario_inicio, centro_horario_fin,
    centro_latitud, centro_longitud, centro_telefono) VALUES
    (1, 'Centro de Salud Zona Norte', 'Av. Vallarta', '1234', '44100', 1,
     '08:00', '17:00', 20.67360, -103.34430, '3312345678'),
    (2, 'Centro de Salud Zapopan', 'Blvd. Aviación', '500', '45010', 2,
     '07:00', '15:00', 20.72060, -103.38270, '3398765432'),
    (3, 'IMSS Unidad Médica Sur', 'Insurgentes Sur', '3700', '14080', 3,
     '08:00', '20:00', 19.32160, -99.18490, '5512345678');

-- ─────────────────────────────────────────────
-- USUARIOS, LOGIN Y ROLES
-- ─────────────────────────────────────────────
INSERT INTO roles (rol_id, rol_nombre) VALUES
    (1, 'admin'),
    (2, 'responsable'),
    (3, 'tutor');

-- Admin
INSERT INTO usuarios (usuario_id, usuario_prim_nombre, usuario_apellido_pat,
    usuario_telefono, usuario_curp, usuario_rfc, usuario_activo) VALUES
    (1, 'Admin', 'Sistema', '3300000001', 'ADMS800101HJLMNA01', 'ADMS800101AB1', true);

-- Responsable (asignado al centro 1)
INSERT INTO usuarios (usuario_id, usuario_prim_nombre, usuario_seg_nombre, usuario_apellido_pat,
    usuario_apellido_mat, usuario_telefono, usuario_curp, usuario_rfc, centro_id, usuario_activo) VALUES
    (2, 'Diego', 'Alejandro', 'Mendoza', 'García', '3311112222',
     'MEGA950315HJLRDA01', 'MEGA950315AB2', 1, true);

-- Tutor
INSERT INTO usuarios (usuario_id, usuario_prim_nombre, usuario_apellido_pat,
    usuario_telefono, usuario_curp, usuario_activo) VALUES
    (3, 'Juan', 'Pérez', '3322223333', 'PEJA900202HJLRNA01', true);

INSERT INTO login (usuario_id, login_correo, login_contrasena) VALUES
    (1, 'admin@vacunatrack.mx',
     'pbkdf2:sha256:600000$8RTrouFB5J9YLQ6b$68495ba1488f0cf18a613482d17eabef7e8045b65e5e8fa32940d7620017ab38'),
    (2, 'diego@vacunatrack.mx',
     'pbkdf2:sha256:600000$EbunBmcTleKquDqZ$02da4288d39e3e5070d1f8de052114319357bb2993dd47b5628ced9e1119eda6'),
    (3, 'juan@correo.mx',
     'pbkdf2:sha256:600000$PtIINqubBppt2cNj$9ff0bb057cb153995b9ab3147cb4bc6d0dd117fe6a1a70d51a53d53f5748e846');

INSERT INTO usuarios_roles (usuario_id, rol_id) VALUES
    (1, 1),
    (2, 2),
    (3, 3);

INSERT INTO cedulas (cedula_numero, cedula_especialidad, usuario_id) VALUES
    ('CED-2024-001', 'Medicina General', 2);

-- ─────────────────────────────────────────────
-- PACIENTES
-- ─────────────────────────────────────────────
INSERT INTO pacientes (paciente_id, paciente_prim_nombre, paciente_apellido_pat,
    paciente_apellido_mat, paciente_curp, paciente_fecha_nac, paciente_sexo, esquema_id) VALUES
    (1, 'Sofía',    'Pérez',    'López',    'PELS240101MJLRFA01', '2024-01-15', 'F', 1),
    (2, 'Mateo',    'Pérez',    'López',    'PELM220601HJLRTA01', '2022-06-01', 'M', 1),
    (3, 'Valentina','Rodríguez','Martínez', 'ROMV231101MJLRLA01', '2023-11-01', 'F', 1);

INSERT INTO pacientes_tutores (paciente_id, tutor_id) VALUES
    (1, 3), (2, 3);

-- ─────────────────────────────────────────────
-- FABRICANTES Y PROVEEDORES
-- ─────────────────────────────────────────────
INSERT INTO fabricantes (fabricante_id, fabricante_nombre, fabricante_telefono, pais_id) VALUES
    (1, 'Sanofi Pasteur', '+33123456789', 1),
    (2, 'Pfizer',         '+12125734000', 1),
    (3, 'BIRMEX',         '5551234567',  1);

INSERT INTO proveedores (proveedor_id, proveedor_prim_nombre, proveedor_apellido_pat,
    proveedor_email, proveedor_telefono, proveedor_empresa, fabricante_id) VALUES
    (1, 'Carlos', 'Ramírez', 'carlos@distribmedica.mx', '3344445555', 'Distribuidora Médica MX', 1),
    (2, 'Laura',  'Torres',  'laura@farmasur.mx',       '3355556666', 'FarmaSur SA de CV', 3);

-- ─────────────────────────────────────────────
-- LOTES E INVENTARIOS
-- ─────────────────────────────────────────────
INSERT INTO lotes (lote_id, lote_codigo, lote_fecha_fabricacion, lote_fecha_caducidad,
    lote_cant_inicial, vacuna_id, fabricante_id, proveedor_id) VALUES
    (1, 'BCG-2025-001',  '2025-01-01', '2027-12-31', 500, 1, 3, 2),
    (2, 'HEPB-2025-001', '2025-02-01', '2027-01-31', 300, 2, 1, 1),
    (3, 'PENT-2025-001', '2025-03-01', '2027-02-28', 400, 3, 1, 1),
    (4, 'NEUM-2025-001', '2025-03-01', '2027-03-31', 200, 4, 2, 1),
    (5, 'ROTA-2025-001', '2025-04-01', '2027-10-31', 250, 5, 1, 1),
    (6, 'SRP-2025-001',  '2025-01-15', '2027-01-14', 150, 6, 1, 1),
    (7, 'FLU-2025-001',  '2025-09-01', '2027-04-30', 600, 7, 2, 1);

INSERT INTO inventarios (centro_id, lote_id, inventario_stock_inicial,
    inventario_stock_actual, inventario_activo_desde, usuario_id) VALUES
    (1, 1, 100, 98,  now(), 2),
    (1, 2, 80,  79,  now(), 2),
    (1, 3, 120, 118, now(), 2),
    (1, 4, 60,  60,  now(), 2),
    (1, 5, 80,  80,  now(), 2),
    (1, 6, 50,  50,  now(), 2),
    (1, 7, 200, 200, now(), 2),
    (2, 1, 80,  80,  now(), 2),
    (2, 3, 100, 100, now(), 2),
    (3, 7, 150, 150, now(), 2);

-- ─────────────────────────────────────────────
-- ALGUNAS APLICACIONES DE EJEMPLO
-- ─────────────────────────────────────────────
INSERT INTO aplicaciones (paciente_id, usuario_id, centro_id, lote_id, dosis_id,
    aplicacion_timestamp, aplicacion_observaciones) VALUES
    (1, 2, 1, 1, 1, '2024-01-15 09:00:00', 'Aplicación al nacer sin complicaciones'),
    (1, 2, 1, 2, 2, '2024-01-15 09:10:00', 'Primera dosis Hepatitis B'),
    (2, 2, 1, 1, 1, '2022-06-01 10:00:00', 'BCG al nacer'),
    (2, 2, 1, 2, 2, '2022-06-01 10:15:00', 'Hepatitis B primera dosis');

-- ─────────────────────────────────────────────
-- RESET DE SECUENCIAS
-- Necesario porque los inserts anteriores usaron IDs explícitos
-- (GENERATED BY DEFAULT permite esto sin actualizar la secuencia).
-- ─────────────────────────────────────────────
SELECT setval(pg_get_serial_sequence('paises',       'pais_id'),         MAX(pais_id))         FROM paises;
SELECT setval(pg_get_serial_sequence('estados',      'estado_id'),       MAX(estado_id))       FROM estados;
SELECT setval(pg_get_serial_sequence('ciudades',     'ciudad_id'),       MAX(ciudad_id))       FROM ciudades;
SELECT setval(pg_get_serial_sequence('vacunas',      'vacuna_id'),       MAX(vacuna_id))       FROM vacunas;
SELECT setval(pg_get_serial_sequence('padecimientos','padecimiento_id'), MAX(padecimiento_id)) FROM padecimientos;
SELECT setval(pg_get_serial_sequence('esquemas',     'esquema_id'),      MAX(esquema_id))      FROM esquemas;
SELECT setval(pg_get_serial_sequence('dosis',        'dosis_id'),        MAX(dosis_id))        FROM dosis;
SELECT setval(pg_get_serial_sequence('centros_salud','centro_id'),       MAX(centro_id))       FROM centros_salud;
SELECT setval(pg_get_serial_sequence('roles',        'rol_id'),          MAX(rol_id))          FROM roles;
SELECT setval(pg_get_serial_sequence('usuarios',     'usuario_id'),      MAX(usuario_id))      FROM usuarios;
SELECT setval(pg_get_serial_sequence('fabricantes',  'fabricante_id'),   MAX(fabricante_id))   FROM fabricantes;
SELECT setval(pg_get_serial_sequence('proveedores',  'proveedor_id'),    MAX(proveedor_id))    FROM proveedores;
SELECT setval(pg_get_serial_sequence('lotes',        'lote_id'),         MAX(lote_id))         FROM lotes;
SELECT setval(pg_get_serial_sequence('inventarios',  'inventario_id'),   MAX(inventario_id))   FROM inventarios;
SELECT setval(pg_get_serial_sequence('pacientes',    'paciente_id'),     MAX(paciente_id))     FROM pacientes;
SELECT setval(pg_get_serial_sequence('aplicaciones', 'aplicacion_id'),   MAX(aplicacion_id))   FROM aplicaciones;

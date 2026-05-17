-- ═══════════════════════════════════════════════════════════════════════════════
-- VacunaTrack — seed_final.sql
-- Datos semilla completos, coherentes y no triviales.
-- Requiere que el schema, SPs, vistas, triggers e índices ya estén aplicados.
-- Uso:  psql -U vacunatrack_user -d vacunatrack -f seed_final.sql
--
-- Contraseñas de acceso:
--   admin@vacunatrack.mx   → Admin2024!
--   *@vacunatrack.mx       → Resp2024!   (responsables)
--   *@correo.mx            → Tutor2024!  (tutores)
-- ═══════════════════════════════════════════════════════════════════════════════

\c vacunatrack;

-- ─── RESET COMPLETO ──────────────────────────────────────────────────────────
TRUNCATE
    aplicaciones, alertas_dosis_pacientes, lecturas_beacon, eventos_gps,
    esquemas_pacientes, pacientes_tutores, pacientes,
    transferencias_inventario, alertas_inventario, inventarios, lotes,
    proveedores, fabricantes,
    cedulas, usuarios_roles, login, usuarios,
    centros_salud, ciudades, estados, paises,
    dosis_esquemas, dosis, esquemas,
    vacunas_padecimientos, padecimientos, vacunas,
    roles
RESTART IDENTITY CASCADE;

-- ─── GEOGRAFÍA ───────────────────────────────────────────────────────────────
INSERT INTO paises (pais_nombre) VALUES
    ('México'),
    ('Francia'),
    ('Estados Unidos'),
    ('Alemania');

INSERT INTO estados (estado_nombre, pais_id) VALUES
    ('Jalisco',          1),
    ('Ciudad de México', 1),
    ('Nuevo León',       1),
    ('Puebla',           1);

INSERT INTO ciudades (ciudad_nombre, estado_id) VALUES
    ('Guadalajara',  1),
    ('Zapopan',      1),
    ('Tlaquepaque',  1),
    ('Ciudad de México', 2),
    ('Monterrey',    3),
    ('Puebla',       4);

-- ─── CATÁLOGOS CLÍNICOS ───────────────────────────────────────────────────────
INSERT INTO vacunas (vacuna_nombre, vacuna_activa) VALUES
    ('BCG',              true),   -- 1
    ('Hepatitis B',      true),   -- 2
    ('Pentavalente',     true),   -- 3
    ('Neumocócica',      true),   -- 4
    ('Rotavirus',        true),   -- 5
    ('Triple Viral (SRP)', true), -- 6
    ('Influenza',        true),   -- 7
    ('Varicela',         true),   -- 8
    ('VPH',              true),   -- 9
    ('Hepatitis A',      true);   -- 10

INSERT INTO padecimientos (padecimiento_nombre, padecimiento_descripcion, padecimiento_activo) VALUES
    ('Tuberculosis',              'Infección bacteriana crónica que afecta los pulmones',              true),
    ('Hepatitis B',               'Infección viral del hígado de transmisión sanguínea y sexual',      true),
    ('Tosferina',                 'Infección respiratoria bacteriana altamente contagiosa',             true),
    ('Difteria',                  'Infección bacteriana que afecta garganta y vías respiratorias',     true),
    ('Tétanos',                   'Enfermedad neurológica causada por toxina bacteriana',              true),
    ('Sarampión',                 'Enfermedad viral altamente contagiosa con exantema característico', true),
    ('Rubéola',                   'Infección viral leve, peligrosa durante el embarazo',               true),
    ('Parotiditis',               'Infección viral de las glándulas salivales (paperas)',              true),
    ('Influenza',                 'Infección viral respiratoria estacional',                            true),
    ('Varicela',                  'Infección viral que produce vesículas cutáneas',                    true),
    ('Cáncer cervicouterino',     'Cáncer asociado a infección persistente por VPH',                  true),
    ('Hepatitis A',               'Infección viral del hígado de transmisión fecal-oral',             true),
    ('Neumonía neumocócica',      'Infección pulmonar por Streptococcus pneumoniae',                   true);

-- vacuna → padecimiento(s)
INSERT INTO vacunas_padecimientos (vacuna_id, padecimiento_id) VALUES
    (1, 1),   -- BCG → Tuberculosis
    (2, 2),   -- HepB → Hepatitis B
    (3, 3),   -- Penta → Tosferina
    (3, 4),   -- Penta → Difteria
    (3, 5),   -- Penta → Tétanos
    (4, 13),  -- Neum → Neumonía neumocócica
    (6, 6),   -- SRP → Sarampión
    (6, 7),   -- SRP → Rubéola
    (6, 8),   -- SRP → Parotiditis
    (7, 9),   -- Influenza → Influenza
    (8, 10),  -- Varicela → Varicela
    (9, 11),  -- VPH → Cáncer cervicouterino
    (10, 12); -- HepA → Hepatitis A

-- ─── ESQUEMAS ────────────────────────────────────────────────────────────────
INSERT INTO esquemas (esquema_nombre, esquema_fecha_vigencia, esquema_vigente_desde, esquema_vigente_hasta) VALUES
    ('Esquema Nacional de Vacunación 2024', '2024-01-01', '2024-01-01', '2026-04-20'),
    ('Esquema Nacional 2026',              '2026-04-21', '2026-04-21', NULL);

-- ─── DOSIS ───────────────────────────────────────────────────────────────────
-- vacuna_id, tipo, ml, área, edad_oportuna_días, intervalo_min, límite_edad
INSERT INTO dosis (vacuna_id, dosis_tipo, dosis_cant_ml, dosis_area_aplicacion,
                   dosis_edad_oportuna_dias, dosis_intervalo_min_dias, dosis_limite_edad_dias) VALUES
    (1, 'UNICA',          0.1, 'Deltoides derecho',    0,   0,   365),  -- 1  BCG
    (2, 'SERIE_PRIMARIA', 0.5, 'Muslo derecho',         0,   0,    30),  -- 2  HepB 1ª
    (2, 'SERIE_PRIMARIA', 0.5, 'Muslo derecho',        60,  28,   365),  -- 3  HepB 2ª
    (3, 'SERIE_PRIMARIA', 0.5, 'Muslo izquierdo',      60,  28,   365),  -- 4  Penta 1ª
    (3, 'SERIE_PRIMARIA', 0.5, 'Muslo izquierdo',     120,  28,   548),  -- 5  Penta 2ª
    (3, 'SERIE_PRIMARIA', 0.5, 'Muslo izquierdo',     180,  28,   730),  -- 6  Penta 3ª
    (4, 'SERIE_PRIMARIA', 0.5, 'Muslo derecho',        60,  56,   365),  -- 7  Neum 1ª
    (4, 'SERIE_PRIMARIA', 0.5, 'Muslo derecho',       180,  56,   548),  -- 8  Neum 2ª
    (5, 'SERIE_PRIMARIA', 1.5, 'Oral',                 60,  28,   240),  -- 9  Rota 1ª
    (5, 'SERIE_PRIMARIA', 1.5, 'Oral',                120,  28,   240),  -- 10 Rota 2ª
    (6, 'UNICA',          0.5, 'Deltoides izquierdo', 365,   0,   548),  -- 11 SRP
    (7, 'ANUAL',          0.5, 'Deltoides derecho',   180,   0,  NULL),  -- 12 Influenza
    (8, 'UNICA',          0.5, 'Deltoides izquierdo', 365,   0,   730),  -- 13 Varicela
    (10,'SERIE_PRIMARIA', 0.5, 'Deltoides derecho',   365,   0,   730),  -- 14 HepA 1ª
    (10,'SERIE_PRIMARIA', 0.5, 'Deltoides derecho',   548, 168,  1095);  -- 15 HepA 2ª

-- Esquema 2024: dosis 1-12
INSERT INTO dosis_esquemas (esquema_id, dosis_id) VALUES
    (1,1),(1,2),(1,3),(1,4),(1,5),(1,6),(1,7),(1,8),(1,9),(1,10),(1,11),(1,12);

-- Esquema 2026: dosis 1-15 (agrega Varicela y Hepatitis A)
INSERT INTO dosis_esquemas (esquema_id, dosis_id) VALUES
    (2,1),(2,2),(2,3),(2,4),(2,5),(2,6),(2,7),(2,8),(2,9),(2,10),(2,11),(2,12),(2,13),(2,14),(2,15);

-- ─── CENTROS DE SALUD (5) ────────────────────────────────────────────────────
INSERT INTO centros_salud (centro_nombre, centro_calle, centro_numero,
    centro_codigo_postal, ciudad_id, centro_horario_inicio, centro_horario_fin,
    centro_latitud, centro_longitud, centro_telefono, centro_beacon) VALUES
    ('Centro de Salud Zona Norte',   'Av. Vallarta',        '1234', '44100', 1, '08:00','17:00',  20.67360,-103.34430, '3312345678', 'FSC-GDL-001'),
    ('Centro de Salud Zapopan',      'Blvd. Aviación',      '500',  '45010', 2, '07:00','15:00',  20.72060,-103.38270, '3398765432', 'FSC-ZAP-001'),
    ('Centro de Salud Tlaquepaque',  'Calle Independencia', '88',   '45500', 3, '08:00','16:00',  20.63920,-103.31050, '3387654321', NULL),
    ('IMSS Unidad Médica Sur',       'Insurgentes Sur',     '3700', '14080', 4, '08:00','20:00',  19.32160, -99.18490, '5512345678', 'FSC-MX-001'),
    ('Centro de Salud Monterrey Norte','Av. Morones Prieto', '2300','64710', 5, '07:30','15:30',  25.67190,-100.31900, '8112345678', NULL);

-- ─── ROLES ───────────────────────────────────────────────────────────────────
INSERT INTO roles (rol_nombre) VALUES ('admin'), ('responsable'), ('tutor');

-- ─── USUARIOS ────────────────────────────────────────────────────────────────
-- 1 admin
INSERT INTO usuarios (usuario_prim_nombre, usuario_apellido_pat,
    usuario_telefono, usuario_curp, usuario_rfc, usuario_activo)
VALUES ('Admin', 'Sistema', '3300000001', 'ADMS800101HJLMNA01', 'ADMS800101AB1', true);

-- 5 responsables
INSERT INTO usuarios (usuario_prim_nombre, usuario_seg_nombre, usuario_apellido_pat,
    usuario_apellido_mat, usuario_telefono, usuario_curp, usuario_rfc, centro_id, usuario_activo)
VALUES
    ('Diego',   'Alejandro', 'Mendoza',  'García',   '3311112222', 'MEGA950315HJLRDA01', 'MEGA950315AB2', 1, true),
    ('Ana',     'Sofía',     'González', 'Ruiz',     '3322220001', 'GORA850520MJLRNA01', 'GORA850520CD3', 2, true),
    ('Roberto', NULL,        'Chávez',   'Moreno',   '3322220002', 'CAMR780610HJLRBA01', 'CAMR780610EF4', 3, true),
    ('María',   'Elena',     'Jiménez',  'Santos',   '8113330001', 'JESM900925MJLRNA01', 'JESM900925GH5', 4, true),
    ('Luis',    NULL,        'Ramos',    'Fuentes',  '8113330002', 'RAFL851215HJLRMA01', 'RAFL851215IJ6', 5, true);

-- 9 tutores
INSERT INTO usuarios (usuario_prim_nombre, usuario_seg_nombre, usuario_apellido_pat,
    usuario_apellido_mat, usuario_telefono, usuario_curp, usuario_activo)
VALUES
    ('Juan',       NULL,      'Pérez',    'Torres',   '3322223333', 'PETJ900202HJLRNA01', true),
    ('Carmen',     NULL,      'López',    'Vega',     '3322224444', 'LOVC880318MJLRBA01', true),
    ('Roberto',    NULL,      'García',   'Núñez',    '3322225555', 'GANR850712HJLRBA01', true),
    ('Sofía',      'Natalia', 'Martínez', 'Cruz',     '3322226666', 'MACS920405MJLRBA01', true),
    ('Eduardo',    NULL,      'Torres',   'Sánchez',  '3322227777', 'TOSE870901HJLRDA01', true),
    ('Patricia',   NULL,      'Sánchez',  'Morales',  '3322228888', 'SAMP910612MJLRTA01', true),
    ('Fernando',   NULL,      'Castro',   'Reyes',    '3322229999', 'CARF880224HJLRNA01', true),
    ('Alejandra',  NULL,      'Díaz',     'Flores',   '3322220011', 'DIFA931105MJLRNA01', true),
    ('Héctor',     NULL,      'Vargas',   'Herrera',  '3322220022', 'VAHH860730HJLRBA01', true);

-- ─── LOGIN ───────────────────────────────────────────────────────────────────
-- Contraseña Admin2024!
INSERT INTO login (usuario_id, login_correo, login_contrasena) VALUES
(1, 'admin@vacunatrack.mx',
 'pbkdf2:sha256:1000000$eaKdBrMwAkNzFlbl$77b507ae015ac1209e74f2ef6a6a0b6e6df0599c865b6dbd075e34c77e4e6eb6');

-- Contraseña Resp2024!
INSERT INTO login (usuario_id, login_correo, login_contrasena) VALUES
(2, 'diego@vacunatrack.mx',
 'pbkdf2:sha256:1000000$zS4EmpsRzQj2DyCR$ac9da319a96105ea6de4e66c231ecdee2ce535dfea382fd9a47c39b36c142268'),
(3, 'ana@vacunatrack.mx',
 'pbkdf2:sha256:1000000$zS4EmpsRzQj2DyCR$ac9da319a96105ea6de4e66c231ecdee2ce535dfea382fd9a47c39b36c142268'),
(4, 'roberto.chavez@vacunatrack.mx',
 'pbkdf2:sha256:1000000$zS4EmpsRzQj2DyCR$ac9da319a96105ea6de4e66c231ecdee2ce535dfea382fd9a47c39b36c142268'),
(5, 'maria@vacunatrack.mx',
 'pbkdf2:sha256:1000000$zS4EmpsRzQj2DyCR$ac9da319a96105ea6de4e66c231ecdee2ce535dfea382fd9a47c39b36c142268'),
(6, 'luis@vacunatrack.mx',
 'pbkdf2:sha256:1000000$zS4EmpsRzQj2DyCR$ac9da319a96105ea6de4e66c231ecdee2ce535dfea382fd9a47c39b36c142268');

-- Contraseña Tutor2024!
INSERT INTO login (usuario_id, login_correo, login_contrasena) VALUES
(7,  'juan@correo.mx',
 'pbkdf2:sha256:1000000$KpWChCafz5COVPE4$19640afbfd0a369e6653d1e0dbba95894ffbfe889c2348ba8fbd3269fe59ff67'),
(8,  'carmen@correo.mx',
 'pbkdf2:sha256:1000000$KpWChCafz5COVPE4$19640afbfd0a369e6653d1e0dbba95894ffbfe889c2348ba8fbd3269fe59ff67'),
(9,  'roberto.garcia@correo.mx',
 'pbkdf2:sha256:1000000$KpWChCafz5COVPE4$19640afbfd0a369e6653d1e0dbba95894ffbfe889c2348ba8fbd3269fe59ff67'),
(10, 'sofia.martinez@correo.mx',
 'pbkdf2:sha256:1000000$KpWChCafz5COVPE4$19640afbfd0a369e6653d1e0dbba95894ffbfe889c2348ba8fbd3269fe59ff67'),
(11, 'eduardo@correo.mx',
 'pbkdf2:sha256:1000000$KpWChCafz5COVPE4$19640afbfd0a369e6653d1e0dbba95894ffbfe889c2348ba8fbd3269fe59ff67'),
(12, 'patricia@correo.mx',
 'pbkdf2:sha256:1000000$KpWChCafz5COVPE4$19640afbfd0a369e6653d1e0dbba95894ffbfe889c2348ba8fbd3269fe59ff67'),
(13, 'fernando@correo.mx',
 'pbkdf2:sha256:1000000$KpWChCafz5COVPE4$19640afbfd0a369e6653d1e0dbba95894ffbfe889c2348ba8fbd3269fe59ff67'),
(14, 'alejandra@correo.mx',
 'pbkdf2:sha256:1000000$KpWChCafz5COVPE4$19640afbfd0a369e6653d1e0dbba95894ffbfe889c2348ba8fbd3269fe59ff67'),
(15, 'hector@correo.mx',
 'pbkdf2:sha256:1000000$KpWChCafz5COVPE4$19640afbfd0a369e6653d1e0dbba95894ffbfe889c2348ba8fbd3269fe59ff67');

-- ─── ROLES DE USUARIOS ───────────────────────────────────────────────────────
INSERT INTO usuarios_roles (usuario_id, rol_id) VALUES
    (1, 1),  -- Admin → admin
    (2, 2),(3, 2),(4, 2),(5, 2),(6, 2),  -- responsables
    (7, 3),(8, 3),(9, 3),(10,3),(11,3),(12,3),(13,3),(14,3),(15,3);  -- tutores

-- ─── CÉDULAS PROFESIONALES ───────────────────────────────────────────────────
INSERT INTO cedulas (cedula_numero, cedula_especialidad, usuario_id) VALUES
    ('3847291',  'Medicina General y Familiar',  2),
    ('92048371', 'Pediatría',                    3),
    ('5610284',  'Medicina General y Familiar',  4),
    ('74829103', 'Pediatría',                    5),
    ('8203947',  'Medicina General y Familiar',  6);

-- ─── PACIENTES (18) ──────────────────────────────────────────────────────────
-- Todos asignados a esquema 1 (2024). El trigger asigna el más reciente activo
-- si se omite; aquí lo especificamos explícitamente.
INSERT INTO pacientes (paciente_prim_nombre, paciente_seg_nombre,
    paciente_apellido_pat, paciente_apellido_mat,
    paciente_curp, paciente_fecha_nac, paciente_sexo, esquema_id) VALUES
    -- Hijos de Juan (tutor 7) → centro 1
    ('Sofía',      NULL,       'Pérez',      'López',     'PELS240115MJLRFA01', '2024-01-15', 'F', 1),  --  1
    ('Mateo',      NULL,       'Pérez',      'López',     'PELM220601HJLRTA01', '2022-06-01', 'M', 1),  --  2
    -- Hijos de Carmen (tutor 8) → centro 2
    ('Valentina',  NULL,       'Rodríguez',  'Martínez',  'ROMV231101MJLRLA01', '2023-11-01', 'F', 1),  --  3
    ('Carlos',     NULL,       'García',     'Núñez',     'GANC240310HJLRSA01', '2024-03-10', 'M', 1),  --  4
    -- Hijos de Roberto G (tutor 9) → centro 2
    ('Isabella',   NULL,       'López',      'Hernández', 'LOHI230720MJLRNA01', '2023-07-20', 'F', 1),  --  5
    ('Diego',      NULL,       'Hernández',  'Cruz',      'HECD240605HJLRGA01', '2024-06-05', 'M', 1),  --  6
    -- Hijos de Sofía M (tutor 10) → centro 4
    ('Camila',     NULL,       'Torres',     'Vargas',    'TOVC220915MJLRBA01', '2022-09-15', 'F', 1),  --  7
    ('Andrés',     NULL,       'Martínez',   'Reyes',     'MARA230128HJLRNA01', '2023-01-28', 'M', 1),  --  8
    -- Hijo de Eduardo (tutor 11) → centro 5
    ('Lucía',      NULL,       'Sánchez',    'Morales',   'SAML240812MJLRCA01', '2024-08-12', 'F', 1),  --  9
    -- Hijo de Patricia (tutor 12) → centro 1
    ('Miguel',     NULL,       'Flores',     'Castillo',  'FLCM221203HJLRSA01', '2022-12-03', 'M', 1),  -- 10
    -- Hijo de Fernando (tutor 13) → centro 3
    ('Emilia',     NULL,       'Castro',     'Guerrero',  'CAGE230518MJLRSA01', '2023-05-18', 'F', 1),  -- 11
    -- Hijo de Alejandra (tutor 14) → centro 2
    ('Sebastián',  NULL,       'Vargas',     'Ortega',    'VAOS240228HJLRBA01', '2024-02-28', 'M', 1),  -- 12
    -- Hijo de Héctor (tutor 15) → centro 1
    ('Alejandro',  NULL,       'Reyes',      'García',    'REGA250110HJLRZA01', '2025-01-10', 'M', 1),  -- 13
    -- Hija de Carmen (tutor 8) → centro 5
    ('Gabriela',   NULL,       'Ortiz',      'Mendoza',   'OMGR250610MJLRBA01', '2025-06-10', 'F', 1),  -- 14
    -- Hijo de Eduardo (tutor 11) → centro 3
    ('Rafael',     NULL,       'Mendoza',    'Peña',      'MEPR251005HJLRFA01', '2025-10-05', 'M', 1),  -- 15
    -- Hija de Patricia (tutor 12) → centro 2
    ('Fernanda',   NULL,       'Rojas',      'Torres',    'ROTF241115MJLRSA01', '2024-11-15', 'F', 1),  -- 16
    -- Hijo de Eduardo (tutor 11) → centro 4
    ('Tomás',      NULL,       'Herrera',    'Vega',      'HEVT250910HJLRBA01', '2025-09-10', 'M', 1),  -- 17
    -- Hija de Alejandra (tutor 14) → centro 1
    ('Valentina',  'Guadalupe','Gutiérrez',  'Díaz',      'GUDV260115MJLRTA01', '2026-01-15', 'F', 1);  -- 18

-- ─── RELACIONES TUTOR ─────────────────────────────────────────────────────────
INSERT INTO pacientes_tutores (paciente_id, tutor_id) VALUES
    (1, 7),(2, 7),          -- hijos de Juan
    (3, 8),(4, 8),(14,8),   -- hijos de Carmen
    (5, 9),(6, 9),          -- hijos de Roberto G
    (7,10),(8,10),          -- hijos de Sofía M
    (9,11),(15,11),(17,11), -- hijos de Eduardo
    (10,12),(16,12),        -- hijos de Patricia
    (11,13),                -- hijo de Fernando
    (12,14),(18,14),        -- hijos de Alejandra
    (13,15);                -- hijo de Héctor

-- ─── FABRICANTES Y PROVEEDORES ───────────────────────────────────────────────
INSERT INTO fabricantes (fabricante_nombre, fabricante_telefono, pais_id) VALUES
    ('BIRMEX',         '5551234567',    1),  -- 1
    ('Sanofi Pasteur', '+33123456789',  2),  -- 2
    ('Pfizer',         '+12125734000',  3),  -- 3
    ('MSD México',     '+19082982000',  3),  -- 4
    ('GSK México',     '+49302020',     4);  -- 5

INSERT INTO proveedores (proveedor_prim_nombre, proveedor_apellido_pat,
    proveedor_email, proveedor_telefono, proveedor_empresa, fabricante_id) VALUES
    ('Carlos',   'Ramírez',  'carlos@distribmedica.mx',  '3344445555', 'Distribuidora Médica MX',  2),
    ('Laura',    'Torres',   'laura@farmasur.mx',        '3355556666', 'FarmaSur SA de CV',        1),
    ('Jorge',    'Méndez',   'jorge@biopharma.mx',       '5567890123', 'BioPharma México',         3),
    ('Daniela',  'Ruiz',     'daniela@medline.mx',       '8113334455', 'MedLine SA de CV',         4),
    ('Alejandro','Vega',     'alejandro@vacunared.mx',   '5544332211', 'VacunaRed MX',             5);

-- ─── LOTES (15) ──────────────────────────────────────────────────────────────
-- Un lote por tipo de vacuna (con caducidad 2027+ para que sigan vigentes hoy).
-- Más lotes secundarios para enriquecer inventario.
INSERT INTO lotes (lote_codigo, lote_fecha_fabricacion, lote_fecha_caducidad,
    lote_cant_inicial, vacuna_id, fabricante_id, proveedor_id) VALUES
    ('BCG-2022-001',   '2022-01-01','2027-12-31',  800, 1, 1, 2),  --  1
    ('HEPB-2022-001',  '2022-01-01','2027-12-31', 1200, 2, 2, 1),  --  2
    ('PENT-2022-001',  '2022-01-01','2027-12-31', 1500, 3, 2, 1),  --  3
    ('NEUM-2022-001',  '2022-01-01','2027-12-31',  800, 4, 3, 3),  --  4
    ('ROTA-2022-001',  '2022-01-01','2027-12-31',  800, 5, 2, 1),  --  5
    ('SRP-2022-001',   '2022-06-01','2027-06-30',  600, 6, 2, 1),  --  6
    ('FLU-2025-001',   '2025-01-01','2027-04-30', 1500, 7, 3, 3),  --  7
    ('VAR-2025-001',   '2025-01-01','2028-12-31',  400, 8, 4, 4),  --  8
    ('VPH-2025-001',   '2025-01-01','2028-12-31',  300, 9, 4, 4),  --  9
    ('HEPA-2025-001',  '2025-01-01','2028-12-31',  400,10, 5, 5),  -- 10
    ('BCG-2025-001',   '2025-01-01','2028-12-31',  600, 1, 1, 2),  -- 11
    ('HEPB-2025-001',  '2025-01-01','2028-12-31',  900, 2, 2, 1),  -- 12
    ('PENT-2025-001',  '2025-01-01','2028-12-31', 1000, 3, 2, 1),  -- 13
    ('NEUM-2025-001',  '2025-01-01','2028-12-31',  600, 4, 3, 3),  -- 14
    ('SRP-2025-001',   '2025-01-01','2028-12-31',  500, 6, 2, 1);  -- 15

-- ─── INVENTARIOS (38) ────────────────────────────────────────────────────────
-- Stock inicial = 200 en todos. El trigger descuenta automáticamente al
-- insertar las aplicaciones; el valor final quedará consistente.
-- Lotes principales (1-7) en los 5 centros
INSERT INTO inventarios (centro_id, lote_id, inventario_stock_inicial,
    inventario_stock_actual, inventario_activo_desde, usuario_id) VALUES
-- Centro 1 — Diego (usuario 2)
(1, 1, 200, 200, '2022-01-10 08:00:00', 2),
(1, 2, 200, 200, '2022-01-10 08:00:00', 2),
(1, 3, 200, 200, '2022-01-10 08:00:00', 2),
(1, 4, 200, 200, '2022-01-10 08:00:00', 2),
(1, 5, 200, 200, '2022-01-10 08:00:00', 2),
(1, 6, 200, 200, '2022-06-15 08:00:00', 2),
(1, 7, 200, 200, '2025-02-01 08:00:00', 2),
-- Centro 2 — Ana (usuario 3)
(2, 1, 200, 200, '2022-01-12 08:00:00', 3),
(2, 2, 200, 200, '2022-01-12 08:00:00', 3),
(2, 3, 200, 200, '2022-01-12 08:00:00', 3),
(2, 4, 200, 200, '2022-01-12 08:00:00', 3),
(2, 5, 200, 200, '2022-01-12 08:00:00', 3),
(2, 6, 200, 200, '2022-06-15 08:00:00', 3),
(2, 7, 200, 200, '2025-02-01 08:00:00', 3),
-- Centro 3 — Roberto Ch (usuario 4)
(3, 1, 200, 200, '2022-01-14 08:00:00', 4),
(3, 2, 200, 200, '2022-01-14 08:00:00', 4),
(3, 3, 200, 200, '2022-01-14 08:00:00', 4),
(3, 4, 200, 200, '2022-01-14 08:00:00', 4),
(3, 5, 200, 200, '2022-01-14 08:00:00', 4),
(3, 6, 200, 200, '2022-06-15 08:00:00', 4),
(3, 7, 200, 200, '2025-02-01 08:00:00', 4),
-- Centro 4 — María (usuario 5)
(4, 1, 200, 200, '2022-01-16 08:00:00', 5),
(4, 2, 200, 200, '2022-01-16 08:00:00', 5),
(4, 3, 200, 200, '2022-01-16 08:00:00', 5),
(4, 4, 200, 200, '2022-01-16 08:00:00', 5),
(4, 5, 200, 200, '2022-01-16 08:00:00', 5),
(4, 6, 200, 200, '2022-06-15 08:00:00', 5),
(4, 7, 200, 200, '2025-02-01 08:00:00', 5),
-- Centro 5 — Luis (usuario 6)
(5, 1, 200, 200, '2022-01-18 08:00:00', 6),
(5, 2, 200, 200, '2022-01-18 08:00:00', 6),
(5, 3, 200, 200, '2022-01-18 08:00:00', 6),
(5, 4, 200, 200, '2022-01-18 08:00:00', 6),
(5, 5, 200, 200, '2022-01-18 08:00:00', 6),
(5, 6, 200, 200, '2022-06-15 08:00:00', 6),
(5, 7, 200, 200, '2025-02-01 08:00:00', 6),
-- Lotes especiales en Centro 1 (Varicela, VPH, HepA)
(1, 8,  150, 150, '2025-03-01 08:00:00', 2),
(1, 9,  100, 100, '2025-03-01 08:00:00', 2),
(1,10,  100, 100, '2025-03-01 08:00:00', 2);

-- ─── APLICACIONES ────────────────────────────────────────────────────────────
-- Insertadas en orden cronológico por paciente.
-- Mapeo fijo dosis → lote: d1→L1, d2/d3→L2, d4/d5/d6→L3,
--   d7/d8→L4, d9/d10→L5, d11→L6, d12→L7
-- Paciente → (centro, responsable): 1,2,4,10,13,18→(1,2); 3,5,12,16→(2,3);
--   6,11,15→(3,4); 7,8,17→(4,5); 9,14→(5,6)

INSERT INTO aplicaciones (paciente_id, usuario_id, centro_id, lote_id, dosis_id,
    aplicacion_timestamp, aplicacion_observaciones) VALUES

-- ── P2: Mateo Pérez (2022-06-01) ─────────────────────────────────────────────
(2,2,1,1, 1,'2022-06-01 09:00:00','BCG al nacer, sin complicaciones'),
(2,2,1,2, 2,'2022-06-01 09:10:00','Hepatitis B primera dosis al nacer'),
(2,2,1,2, 3,'2022-08-01 09:00:00','Hepatitis B segunda dosis'),
(2,2,1,3, 4,'2022-08-01 09:05:00','Pentavalente primera dosis'),
(2,2,1,4, 7,'2022-08-01 09:10:00','Neumocócica primera dosis'),
(2,2,1,5, 9,'2022-08-01 09:15:00','Rotavirus primera dosis'),
(2,2,1,3, 5,'2022-10-01 09:00:00','Pentavalente segunda dosis'),
(2,2,1,5,10,'2022-10-01 09:05:00','Rotavirus segunda dosis'),
(2,2,1,3, 6,'2022-12-01 09:00:00','Pentavalente tercera dosis'),
(2,2,1,4, 8,'2022-12-01 09:05:00','Neumocócica segunda dosis'),
(2,2,1,7,12,'2022-12-01 09:10:00','Influenza primera aplicación'),
(2,2,1,6,11,'2023-06-02 09:00:00','Triple Viral (SRP), sin reacciones adversas'),

-- ── P7: Camila Torres (2022-09-15) ───────────────────────────────────────────
(7,5,4,1, 1,'2022-09-15 10:00:00','BCG al nacer'),
(7,5,4,2, 2,'2022-09-15 10:10:00','Hepatitis B primera dosis'),
(7,5,4,2, 3,'2022-11-15 10:00:00','Hepatitis B segunda dosis'),
(7,5,4,3, 4,'2022-11-15 10:05:00','Pentavalente primera dosis'),
(7,5,4,4, 7,'2022-11-15 10:10:00','Neumocócica primera dosis'),
(7,5,4,5, 9,'2022-11-15 10:15:00','Rotavirus primera dosis'),
(7,5,4,3, 5,'2023-01-14 10:00:00','Pentavalente segunda dosis'),
(7,5,4,5,10,'2023-01-14 10:05:00','Rotavirus segunda dosis'),
(7,5,4,3, 6,'2023-03-15 10:00:00','Pentavalente tercera dosis'),
(7,5,4,4, 8,'2023-03-15 10:05:00','Neumocócica segunda dosis'),
(7,5,4,7,12,'2023-03-15 10:10:00','Influenza'),
(7,5,4,6,11,'2023-09-16 10:00:00','Triple Viral (SRP)'),

-- ── P10: Miguel Flores (2022-12-03) ──────────────────────────────────────────
(10,2,1,1, 1,'2022-12-03 11:00:00','BCG al nacer'),
(10,2,1,2, 2,'2022-12-03 11:10:00','Hepatitis B primera dosis'),
(10,2,1,2, 3,'2023-02-03 11:00:00','Hepatitis B segunda dosis'),
(10,2,1,3, 4,'2023-02-03 11:05:00','Pentavalente primera dosis'),
(10,2,1,4, 7,'2023-02-03 11:10:00','Neumocócica primera dosis'),
(10,2,1,5, 9,'2023-02-03 11:15:00','Rotavirus primera dosis'),
(10,2,1,3, 5,'2023-04-04 11:00:00','Pentavalente segunda dosis'),
(10,2,1,5,10,'2023-04-04 11:05:00','Rotavirus segunda dosis'),
(10,2,1,3, 6,'2023-06-03 11:00:00','Pentavalente tercera dosis'),
(10,2,1,4, 8,'2023-06-03 11:05:00','Neumocócica segunda dosis'),
(10,2,1,7,12,'2023-06-03 11:10:00','Influenza'),
(10,2,1,6,11,'2023-12-04 11:00:00','Triple Viral (SRP)'),

-- ── P8: Andrés Martínez (2023-01-28) ─────────────────────────────────────────
(8,5,4,1, 1,'2023-01-28 09:00:00','BCG al nacer'),
(8,5,4,2, 2,'2023-01-28 09:10:00','Hepatitis B primera dosis'),
(8,5,4,2, 3,'2023-03-30 09:00:00','Hepatitis B segunda dosis'),
(8,5,4,3, 4,'2023-03-30 09:05:00','Pentavalente primera dosis'),
(8,5,4,4, 7,'2023-03-30 09:10:00','Neumocócica primera dosis'),
(8,5,4,5, 9,'2023-03-30 09:15:00','Rotavirus primera dosis'),
(8,5,4,3, 5,'2023-05-29 09:00:00','Pentavalente segunda dosis'),
(8,5,4,5,10,'2023-05-29 09:05:00','Rotavirus segunda dosis'),
(8,5,4,3, 6,'2023-07-28 09:00:00','Pentavalente tercera dosis'),
(8,5,4,4, 8,'2023-07-28 09:05:00','Neumocócica segunda dosis'),
(8,5,4,7,12,'2023-07-28 09:10:00','Influenza'),
(8,5,4,6,11,'2024-01-29 09:00:00','Triple Viral (SRP)'),

-- ── P11: Emilia Castro (2023-05-18) ──────────────────────────────────────────
(11,4,3,1, 1,'2023-05-18 10:00:00','BCG al nacer'),
(11,4,3,2, 2,'2023-05-18 10:10:00','Hepatitis B primera dosis'),
(11,4,3,2, 3,'2023-07-18 10:00:00','Hepatitis B segunda dosis'),
(11,4,3,3, 4,'2023-07-18 10:05:00','Pentavalente primera dosis'),
(11,4,3,4, 7,'2023-07-18 10:10:00','Neumocócica primera dosis'),
(11,4,3,5, 9,'2023-07-18 10:15:00','Rotavirus primera dosis'),
(11,4,3,3, 5,'2023-09-16 10:00:00','Pentavalente segunda dosis'),
(11,4,3,5,10,'2023-09-16 10:05:00','Rotavirus segunda dosis'),
(11,4,3,3, 6,'2023-11-15 10:00:00','Pentavalente tercera dosis'),
(11,4,3,4, 8,'2023-11-15 10:05:00','Neumocócica segunda dosis'),
(11,4,3,7,12,'2023-11-15 10:10:00','Influenza'),
(11,4,3,6,11,'2024-05-19 10:00:00','Triple Viral (SRP)'),

-- ── P5: Isabella López (2023-07-20) ──────────────────────────────────────────
(5,3,2,1, 1,'2023-07-20 09:00:00','BCG al nacer'),
(5,3,2,2, 2,'2023-07-20 09:10:00','Hepatitis B primera dosis'),
(5,3,2,2, 3,'2023-09-19 09:00:00','Hepatitis B segunda dosis'),
(5,3,2,3, 4,'2023-09-19 09:05:00','Pentavalente primera dosis'),
(5,3,2,4, 7,'2023-09-19 09:10:00','Neumocócica primera dosis'),
(5,3,2,5, 9,'2023-09-19 09:15:00','Rotavirus primera dosis'),
(5,3,2,3, 5,'2023-11-18 09:00:00','Pentavalente segunda dosis'),
(5,3,2,5,10,'2023-11-18 09:05:00','Rotavirus segunda dosis'),
(5,3,2,3, 6,'2024-01-17 09:00:00','Pentavalente tercera dosis'),
(5,3,2,4, 8,'2024-01-17 09:05:00','Neumocócica segunda dosis'),
(5,3,2,7,12,'2024-01-17 09:10:00','Influenza'),
(5,3,2,6,11,'2024-07-21 09:00:00','Triple Viral (SRP)'),

-- ── P3: Valentina Rodríguez (2023-11-01) ─────────────────────────────────────
(3,3,2,1, 1,'2023-11-01 10:00:00','BCG al nacer'),
(3,3,2,2, 2,'2023-11-01 10:10:00','Hepatitis B primera dosis'),
(3,3,2,2, 3,'2024-01-01 10:00:00','Hepatitis B segunda dosis'),
(3,3,2,3, 4,'2024-01-01 10:05:00','Pentavalente primera dosis'),
(3,3,2,4, 7,'2024-01-01 10:10:00','Neumocócica primera dosis'),
(3,3,2,5, 9,'2024-01-01 10:15:00','Rotavirus primera dosis'),
(3,3,2,3, 5,'2024-03-01 10:00:00','Pentavalente segunda dosis'),
(3,3,2,5,10,'2024-03-01 10:05:00','Rotavirus segunda dosis'),
(3,3,2,3, 6,'2024-05-01 10:00:00','Pentavalente tercera dosis'),
(3,3,2,4, 8,'2024-05-01 10:05:00','Neumocócica segunda dosis'),
(3,3,2,7,12,'2024-05-01 10:10:00','Influenza'),
(3,3,2,6,11,'2024-11-02 10:00:00','Triple Viral (SRP)'),

-- ── P1: Sofía Pérez (2024-01-15) ─────────────────────────────────────────────
(1,2,1,1, 1,'2024-01-15 09:00:00','BCG al nacer, aplicación sin incidentes'),
(1,2,1,2, 2,'2024-01-15 09:10:00','Hepatitis B primera dosis al nacer'),
(1,2,1,2, 3,'2024-03-15 09:00:00','Hepatitis B segunda dosis'),
(1,2,1,3, 4,'2024-03-15 09:05:00','Pentavalente primera dosis'),
(1,2,1,4, 7,'2024-03-15 09:10:00','Neumocócica primera dosis'),
(1,2,1,5, 9,'2024-03-15 09:15:00','Rotavirus primera dosis'),
(1,2,1,3, 5,'2024-05-14 09:00:00','Pentavalente segunda dosis'),
(1,2,1,5,10,'2024-05-14 09:05:00','Rotavirus segunda dosis'),
(1,2,1,3, 6,'2024-07-13 09:00:00','Pentavalente tercera dosis'),
(1,2,1,4, 8,'2024-07-13 09:05:00','Neumocócica segunda dosis'),
(1,2,1,7,12,'2024-07-13 09:10:00','Influenza'),
(1,2,1,6,11,'2025-01-15 09:00:00','Triple Viral (SRP)'),

-- ── P12: Sebastián Vargas (2024-02-28) ───────────────────────────────────────
(12,3,2,1, 1,'2024-02-28 11:00:00','BCG al nacer'),
(12,3,2,2, 2,'2024-02-28 11:10:00','Hepatitis B primera dosis'),
(12,3,2,2, 3,'2024-04-29 11:00:00','Hepatitis B segunda dosis'),
(12,3,2,3, 4,'2024-04-29 11:05:00','Pentavalente primera dosis'),
(12,3,2,4, 7,'2024-04-29 11:10:00','Neumocócica primera dosis'),
(12,3,2,5, 9,'2024-04-29 11:15:00','Rotavirus primera dosis'),
(12,3,2,3, 5,'2024-06-28 11:00:00','Pentavalente segunda dosis'),
(12,3,2,5,10,'2024-06-28 11:05:00','Rotavirus segunda dosis'),
(12,3,2,3, 6,'2024-08-27 11:00:00','Pentavalente tercera dosis'),
(12,3,2,4, 8,'2024-08-27 11:05:00','Neumocócica segunda dosis'),
(12,3,2,7,12,'2024-08-27 11:10:00','Influenza'),
(12,3,2,6,11,'2025-02-28 11:00:00','Triple Viral (SRP)'),

-- ── P4: Carlos García (2024-03-10) ───────────────────────────────────────────
(4,2,1,1, 1,'2024-03-10 10:00:00','BCG al nacer'),
(4,2,1,2, 2,'2024-03-10 10:10:00','Hepatitis B primera dosis'),
(4,2,1,2, 3,'2024-05-10 10:00:00','Hepatitis B segunda dosis'),
(4,2,1,3, 4,'2024-05-10 10:05:00','Pentavalente primera dosis'),
(4,2,1,4, 7,'2024-05-10 10:10:00','Neumocócica primera dosis'),
(4,2,1,5, 9,'2024-05-10 10:15:00','Rotavirus primera dosis'),
(4,2,1,3, 5,'2024-07-10 10:00:00','Pentavalente segunda dosis'),
(4,2,1,5,10,'2024-07-10 10:05:00','Rotavirus segunda dosis'),
(4,2,1,3, 6,'2024-09-09 10:00:00','Pentavalente tercera dosis'),
(4,2,1,4, 8,'2024-09-09 10:05:00','Neumocócica segunda dosis'),
(4,2,1,7,12,'2024-09-09 10:10:00','Influenza'),
(4,2,1,6,11,'2025-03-11 10:00:00','Triple Viral (SRP)'),

-- ── P6: Diego Hernández (2024-06-05) ─────────────────────────────────────────
(6,4,3,1, 1,'2024-06-05 09:00:00','BCG al nacer'),
(6,4,3,2, 2,'2024-06-05 09:10:00','Hepatitis B primera dosis'),
(6,4,3,2, 3,'2024-08-05 09:00:00','Hepatitis B segunda dosis'),
(6,4,3,3, 4,'2024-08-05 09:05:00','Pentavalente primera dosis'),
(6,4,3,4, 7,'2024-08-05 09:10:00','Neumocócica primera dosis'),
(6,4,3,5, 9,'2024-08-05 09:15:00','Rotavirus primera dosis'),
(6,4,3,3, 5,'2024-10-05 09:00:00','Pentavalente segunda dosis'),
(6,4,3,5,10,'2024-10-05 09:05:00','Rotavirus segunda dosis'),
(6,4,3,3, 6,'2024-12-05 09:00:00','Pentavalente tercera dosis'),
(6,4,3,4, 8,'2024-12-05 09:05:00','Neumocócica segunda dosis'),
(6,4,3,7,12,'2024-12-05 09:10:00','Influenza'),
(6,4,3,6,11,'2025-06-05 09:00:00','Triple Viral (SRP)'),

-- ── P9: Lucía Sánchez (2024-08-12) ───────────────────────────────────────────
(9,6,5,1, 1,'2024-08-12 09:00:00','BCG al nacer'),
(9,6,5,2, 2,'2024-08-12 09:10:00','Hepatitis B primera dosis'),
(9,6,5,2, 3,'2024-10-12 09:00:00','Hepatitis B segunda dosis'),
(9,6,5,3, 4,'2024-10-12 09:05:00','Pentavalente primera dosis'),
(9,6,5,4, 7,'2024-10-12 09:10:00','Neumocócica primera dosis'),
(9,6,5,5, 9,'2024-10-12 09:15:00','Rotavirus primera dosis'),
(9,6,5,3, 5,'2024-12-12 09:00:00','Pentavalente segunda dosis'),
(9,6,5,5,10,'2024-12-12 09:05:00','Rotavirus segunda dosis'),
(9,6,5,3, 6,'2025-02-11 09:00:00','Pentavalente tercera dosis'),
(9,6,5,4, 8,'2025-02-11 09:05:00','Neumocócica segunda dosis'),
(9,6,5,7,12,'2025-02-11 09:10:00','Influenza'),
(9,6,5,6,11,'2025-08-13 09:00:00','Triple Viral (SRP)'),

-- ── P16: Fernanda Rojas (2024-11-15) ─────────────────────────────────────────
(16,3,2,1, 1,'2024-11-15 10:00:00','BCG al nacer'),
(16,3,2,2, 2,'2024-11-15 10:10:00','Hepatitis B primera dosis'),
(16,3,2,2, 3,'2025-01-15 10:00:00','Hepatitis B segunda dosis'),
(16,3,2,3, 4,'2025-01-15 10:05:00','Pentavalente primera dosis'),
(16,3,2,4, 7,'2025-01-15 10:10:00','Neumocócica primera dosis'),
(16,3,2,5, 9,'2025-01-15 10:15:00','Rotavirus primera dosis'),
(16,3,2,3, 5,'2025-03-17 10:00:00','Pentavalente segunda dosis'),
(16,3,2,5,10,'2025-03-17 10:05:00','Rotavirus segunda dosis'),
(16,3,2,3, 6,'2025-05-16 10:00:00','Pentavalente tercera dosis'),
(16,3,2,4, 8,'2025-05-16 10:05:00','Neumocócica segunda dosis'),
(16,3,2,7,12,'2025-05-16 10:10:00','Influenza'),
(16,3,2,6,11,'2025-11-16 10:00:00','Triple Viral (SRP)'),

-- ── P13: Alejandro Reyes (2025-01-10) ────────────────────────────────────────
(13,2,1,1, 1,'2025-01-10 09:00:00','BCG al nacer'),
(13,2,1,2, 2,'2025-01-10 09:10:00','Hepatitis B primera dosis'),
(13,2,1,2, 3,'2025-03-12 09:00:00','Hepatitis B segunda dosis'),
(13,2,1,3, 4,'2025-03-12 09:05:00','Pentavalente primera dosis'),
(13,2,1,4, 7,'2025-03-12 09:10:00','Neumocócica primera dosis'),
(13,2,1,5, 9,'2025-03-12 09:15:00','Rotavirus primera dosis'),
(13,2,1,3, 5,'2025-05-11 09:00:00','Pentavalente segunda dosis'),
(13,2,1,5,10,'2025-05-11 09:05:00','Rotavirus segunda dosis'),
(13,2,1,3, 6,'2025-07-10 09:00:00','Pentavalente tercera dosis'),
(13,2,1,4, 8,'2025-07-10 09:05:00','Neumocócica segunda dosis'),
(13,2,1,7,12,'2025-07-10 09:10:00','Influenza'),
(13,2,1,6,11,'2026-01-12 09:00:00','Triple Viral (SRP)'),

-- ── P14: Gabriela Ortiz (2025-06-10) ─────────────────────────────────────────
(14,6,5,1, 1,'2025-06-10 10:00:00','BCG al nacer'),
(14,6,5,2, 2,'2025-06-10 10:10:00','Hepatitis B primera dosis'),
(14,6,5,2, 3,'2025-08-10 10:00:00','Hepatitis B segunda dosis'),
(14,6,5,3, 4,'2025-08-10 10:05:00','Pentavalente primera dosis'),
(14,6,5,4, 7,'2025-08-10 10:10:00','Neumocócica primera dosis'),
(14,6,5,5, 9,'2025-08-10 10:15:00','Rotavirus primera dosis'),
(14,6,5,3, 5,'2025-10-09 10:00:00','Pentavalente segunda dosis'),
(14,6,5,5,10,'2025-10-09 10:05:00','Rotavirus segunda dosis'),
(14,6,5,3, 6,'2025-12-09 10:00:00','Pentavalente tercera dosis'),
(14,6,5,4, 8,'2025-12-09 10:05:00','Neumocócica segunda dosis'),
(14,6,5,7,12,'2025-12-09 10:10:00','Influenza'),

-- ── P17: Tomás Herrera (2025-09-10) ──────────────────────────────────────────
(17,5,4,1, 1,'2025-09-10 09:00:00','BCG al nacer'),
(17,5,4,2, 2,'2025-09-10 09:10:00','Hepatitis B primera dosis'),
(17,5,4,2, 3,'2025-11-10 09:00:00','Hepatitis B segunda dosis'),
(17,5,4,3, 4,'2025-11-10 09:05:00','Pentavalente primera dosis'),
(17,5,4,4, 7,'2025-11-10 09:10:00','Neumocócica primera dosis'),
(17,5,4,5, 9,'2025-11-10 09:15:00','Rotavirus primera dosis'),
(17,5,4,3, 5,'2026-01-09 09:00:00','Pentavalente segunda dosis'),
(17,5,4,5,10,'2026-01-09 09:05:00','Rotavirus segunda dosis'),
(17,5,4,3, 6,'2026-03-10 09:00:00','Pentavalente tercera dosis'),
(17,5,4,4, 8,'2026-03-10 09:05:00','Neumocócica segunda dosis'),
(17,5,4,7,12,'2026-03-10 09:10:00','Influenza'),

-- ── P15: Rafael Mendoza (2025-10-05) ─────────────────────────────────────────
(15,4,3,1, 1,'2025-10-05 11:00:00','BCG al nacer'),
(15,4,3,2, 2,'2025-10-05 11:10:00','Hepatitis B primera dosis'),
(15,4,3,2, 3,'2025-12-05 11:00:00','Hepatitis B segunda dosis'),
(15,4,3,3, 4,'2025-12-05 11:05:00','Pentavalente primera dosis'),
(15,4,3,4, 7,'2025-12-05 11:10:00','Neumocócica primera dosis'),
(15,4,3,5, 9,'2025-12-05 11:15:00','Rotavirus primera dosis'),
(15,4,3,3, 5,'2026-02-03 11:00:00','Pentavalente segunda dosis'),
(15,4,3,5,10,'2026-02-03 11:05:00','Rotavirus segunda dosis'),
(15,4,3,3, 6,'2026-04-04 11:00:00','Pentavalente tercera dosis'),
(15,4,3,4, 8,'2026-04-04 11:05:00','Neumocócica segunda dosis'),
(15,4,3,7,12,'2026-04-04 11:10:00','Influenza'),

-- ── P18: Valentina Gutiérrez (2026-01-15) ────────────────────────────────────
(18,2,1,1, 1,'2026-01-15 09:00:00','BCG al nacer'),
(18,2,1,2, 2,'2026-01-15 09:10:00','Hepatitis B primera dosis'),
(18,2,1,2, 3,'2026-03-17 09:00:00','Hepatitis B segunda dosis'),
(18,2,1,3, 4,'2026-03-17 09:05:00','Pentavalente primera dosis'),
(18,2,1,4, 7,'2026-03-17 09:10:00','Neumocócica primera dosis'),
(18,2,1,5, 9,'2026-03-17 09:15:00','Rotavirus primera dosis'),
(18,2,1,3, 5,'2026-05-16 09:00:00','Pentavalente segunda dosis'),
(18,2,1,5,10,'2026-05-16 09:05:00','Rotavirus segunda dosis');

-- ─── LECTURAS BEACON ─────────────────────────────────────────────────────────
INSERT INTO lecturas_beacon (centro_id, tutor_id, lectura_timestamp) VALUES
(1, 7,  '2025-08-15 09:10:00'),
(1, 7,  '2025-11-20 10:05:00'),
(2, 8,  '2025-07-01 09:30:00'),
(2, 9,  '2025-09-12 11:00:00'),
(4, 10, '2025-09-16 10:15:00'),
(4, 10, '2026-01-10 09:45:00'),
(1, 15, '2025-03-13 08:55:00'),
(5, 11, '2025-08-14 09:20:00'),
(5, 8,  '2025-06-11 10:00:00'),
(3, 13, '2025-05-19 09:35:00'),
(1, 14, '2026-01-16 08:50:00'),
(4, 5,  '2026-03-11 09:05:00');

-- ─── EVENTOS GPS ─────────────────────────────────────────────────────────────
INSERT INTO eventos_gps (tutor_id, evento_latitud, evento_longitud, evento_timestamp) VALUES
( 7, 20.6700,-103.3450,'2025-08-15 09:05:00'),
( 8, 20.7200,-103.3830,'2025-07-01 09:25:00'),
( 9, 20.7210,-103.3820,'2025-09-12 10:55:00'),
(10, 25.6720,-100.3185,'2025-09-16 10:10:00'),
(11, 20.6390,-103.3100,'2024-10-13 09:00:00'),
(12, 20.6730,-103.3440,'2025-01-16 10:20:00'),
(13, 20.6400,-103.3110,'2025-05-19 09:30:00'),
(14, 20.6720,-103.3450,'2026-01-16 08:45:00'),
(15, 20.6710,-103.3440,'2025-03-13 08:50:00'),
( 8, 20.6390,-103.3100,'2025-06-11 09:55:00'),
( 7, 20.6700,-103.3450,'2025-11-20 10:00:00'),
(10, 25.6720,-100.3185,'2026-01-10 09:40:00');

-- ─── SECUENCIAS AL CORRIENTE ──────────────────────────────────────────────────
-- Garantiza que el siguiente INSERT use el ID correcto aunque se hayan hecho
-- inserciones fuera de orden o con IDs explícitos.
SELECT setval('paises_pais_id_seq',             (SELECT MAX(pais_id)         FROM paises));
SELECT setval('estados_estado_id_seq',           (SELECT MAX(estado_id)       FROM estados));
SELECT setval('ciudades_ciudad_id_seq',           (SELECT MAX(ciudad_id)       FROM ciudades));
SELECT setval('vacunas_vacuna_id_seq',            (SELECT MAX(vacuna_id)       FROM vacunas));
SELECT setval('padecimientos_padecimiento_id_seq',(SELECT MAX(padecimiento_id) FROM padecimientos));
SELECT setval('esquemas_esquema_id_seq',          (SELECT MAX(esquema_id)      FROM esquemas));
SELECT setval('dosis_dosis_id_seq',               (SELECT MAX(dosis_id)        FROM dosis));
SELECT setval('centros_salud_centro_id_seq',      (SELECT MAX(centro_id)       FROM centros_salud));
SELECT setval('roles_rol_id_seq',                 (SELECT MAX(rol_id)          FROM roles));
SELECT setval('usuarios_usuario_id_seq',          (SELECT MAX(usuario_id)      FROM usuarios));
SELECT setval('login_login_id_seq',               (SELECT MAX(login_id)        FROM login));
SELECT setval('pacientes_paciente_id_seq',        (SELECT MAX(paciente_id)     FROM pacientes));
SELECT setval('fabricantes_fabricante_id_seq',    (SELECT MAX(fabricante_id)   FROM fabricantes));
SELECT setval('proveedores_proveedor_id_seq',     (SELECT MAX(proveedor_id)    FROM proveedores));
SELECT setval('lotes_lote_id_seq',                (SELECT MAX(lote_id)         FROM lotes));
SELECT setval('inventarios_inventario_id_seq',    (SELECT MAX(inventario_id)   FROM inventarios));
SELECT setval('aplicaciones_aplicacion_id_seq',   (SELECT MAX(aplicacion_id)   FROM aplicaciones));
SELECT setval('lecturas_beacon_lectura_id_seq',   (SELECT MAX(lectura_id)      FROM lecturas_beacon));
SELECT setval('eventos_gps_evento_id_seq',        (SELECT MAX(evento_id)       FROM eventos_gps));

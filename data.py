# data.py — Datos estáticos de VacunaTrack (modo sin base de datos)
# Estructura idéntica al esquema vacunatrack_v3.sql.
# Si reinicias el servidor se pierden los cambios.

from datetime import date, datetime
from werkzeug.security import generate_password_hash as _gph
from functools import partial
generate_password_hash = partial(_gph, method='pbkdf2:sha256')

# ── Geografía ─────────────────────────────────────────────────────

PAISES = [
    {'pais_id': 1, 'pais_nombre': 'México'},
]
ESTADOS = [
    {'estado_id': 1, 'estado_nombre': 'Nuevo León', 'pais_id': 1, 'pais_nombre': 'México'},
    {'estado_id': 2, 'estado_nombre': 'Jalisco',    'pais_id': 1, 'pais_nombre': 'México'},
]
CIUDADES = [
    {'ciudad_id': 1, 'ciudad_nombre': 'Monterrey',              'estado_id': 1, 'estado_nombre': 'Nuevo León'},
    {'ciudad_id': 2, 'ciudad_nombre': 'San Pedro Garza García', 'estado_id': 1, 'estado_nombre': 'Nuevo León'},
    {'ciudad_id': 3, 'ciudad_nombre': 'Guadalajara',            'estado_id': 2, 'estado_nombre': 'Jalisco'},
]

# ── Centros de salud ──────────────────────────────────────────────

CENTROS = [
    {
        'centro_id': 1, 'centro_nombre': 'Centro de Salud Monterrey Centro',
        'centro_calle': 'Av. Constitución', 'centro_numero': '2000',
        'centro_codigo_postal': '64000', 'ciudad_id': 1, 'ciudad_nombre': 'Monterrey',
        'centro_horario_inicio': '08:00', 'centro_horario_fin': '16:00',
        'centro_latitud': 25.6751, 'centro_longitud': -100.3101,
        'centro_telefono': '8181234567', 'centro_beacon': 'BEACON-MTY-001',
    },
    {
        'centro_id': 2, 'centro_nombre': 'Unidad Médica San Pedro',
        'centro_calle': 'Av. Vasconcelos', 'centro_numero': '500',
        'centro_codigo_postal': '66220', 'ciudad_id': 2, 'ciudad_nombre': 'San Pedro Garza García',
        'centro_horario_inicio': '07:00', 'centro_horario_fin': '15:00',
        'centro_latitud': 25.6574, 'centro_longitud': -100.4026,
        'centro_telefono': '8182345678', 'centro_beacon': 'BEACON-SPG-001',
    },
]

# ── Usuarios, login y roles ───────────────────────────────────────
# Tabla unificada: admins, responsables y tutores son todos USUARIOS.
# usuario_id=1 Admin | usuario_id=2 Responsable | usuario_id=3 Tutor

USUARIOS = [
    {
        'usuario_id': 1, 'usuario_prim_nombre': 'Admin', 'usuario_seg_nombre': None,
        'usuario_apellido_pat': 'Sistema', 'usuario_apellido_mat': None,
        'usuario_curp': 'ADMX000000HDFXXX00', 'usuario_telefono': '8180000000',
        'usuario_rfc': 'ADM000000000', 'centro_id': None,
        'usuario_activo': True, 'usuario_imagen': None,
    },
    {
        'usuario_id': 2, 'usuario_prim_nombre': 'Diego', 'usuario_seg_nombre': None,
        'usuario_apellido_pat': 'Mendoza', 'usuario_apellido_mat': 'Reyes',
        'usuario_curp': 'MERD950101HNLNYS09', 'usuario_telefono': '8181234567',
        'usuario_rfc': 'MERD950101AA1', 'centro_id': 2,
        'usuario_activo': True, 'usuario_imagen': None,
    },
    {
        'usuario_id': 3, 'usuario_prim_nombre': 'Juan', 'usuario_seg_nombre': None,
        'usuario_apellido_pat': 'Reyes', 'usuario_apellido_mat': 'González',
        'usuario_curp': 'REGJ850312HNLYSN01', 'usuario_telefono': '8189876543',
        'usuario_rfc': None, 'centro_id': None,
        'usuario_activo': True, 'usuario_imagen': None,
    },
]

LOGIN = [
    {'login_id': 1, 'usuario_id': 1, 'login_correo': 'admin@vacunatrack.mx',  'login_contrasena': generate_password_hash('Admin2026!')},
    {'login_id': 2, 'usuario_id': 2, 'login_correo': 'diego@vacunatrack.mx',  'login_contrasena': generate_password_hash('Diego2026!')},
    {'login_id': 3, 'usuario_id': 3, 'login_correo': 'juan@correo.mx',        'login_contrasena': generate_password_hash('Tutor2026!')},
]

ROLES = [
    {'rol_id': 1, 'rol_nombre': 'admin'},
    {'rol_id': 2, 'rol_nombre': 'responsable'},
    {'rol_id': 3, 'rol_nombre': 'tutor'},
]

USUARIOS_ROLES = [
    {'us_rol_id': 1, 'usuario_id': 1, 'rol_id': 1},  # Admin → admin
    {'us_rol_id': 2, 'usuario_id': 2, 'rol_id': 2},  # Diego → responsable
    {'us_rol_id': 3, 'usuario_id': 3, 'rol_id': 3},  # Juan  → tutor
]

# Cédulas profesionales (referencia usuario_id del responsable)
CEDULAS = [
    {'cedula_id': 1, 'cedula_numero': '12345678', 'cedula_especialidad': 'Medicina General', 'usuario_id': 2},
]

# ── Catálogos clínicos ────────────────────────────────────────────

VACUNAS = [
    {'vacuna_id': 1,  'vacuna_nombre': 'BCG',                                   'vacuna_activa': True},
    {'vacuna_id': 2,  'vacuna_nombre': 'Hepatitis B',                            'vacuna_activa': True},
    {'vacuna_id': 3,  'vacuna_nombre': 'Pentavalente acelular',                  'vacuna_activa': True},
    {'vacuna_id': 4,  'vacuna_nombre': 'Rotavirus',                              'vacuna_activa': True},
    {'vacuna_id': 5,  'vacuna_nombre': 'Neumocócica conjugada',                  'vacuna_activa': True},
    {'vacuna_id': 6,  'vacuna_nombre': 'Influenza',                              'vacuna_activa': True},
    {'vacuna_id': 7,  'vacuna_nombre': 'SRP (Sarampión, Rubéola, Parotiditis)', 'vacuna_activa': True},
    {'vacuna_id': 8,  'vacuna_nombre': 'DPT',                                    'vacuna_activa': True},
    {'vacuna_id': 9,  'vacuna_nombre': 'Varicela',                               'vacuna_activa': True},
    {'vacuna_id': 10, 'vacuna_nombre': 'Hepatitis A',                            'vacuna_activa': True},
]

DOSIS = [
    {'dosis_id': 1,  'vacuna_id': 1,  'dosis_tipo': 'UNICA',         'dosis_cant_ml': 0.1, 'dosis_area_aplicacion': 'Deltoides derecho',   'dosis_edad_oportuna_dias': 0,    'dosis_intervalo_min_dias': 0,  'dosis_limite_edad_dias': 14,   'dosis_vigente_desde': date(2024,1,1), 'dosis_vigente_hasta': None},
    {'dosis_id': 2,  'vacuna_id': 2,  'dosis_tipo': 'SERIE_PRIMARIA', 'dosis_cant_ml': 0.5, 'dosis_area_aplicacion': 'Muslo derecho',        'dosis_edad_oportuna_dias': 0,    'dosis_intervalo_min_dias': 0,  'dosis_limite_edad_dias': 30,   'dosis_vigente_desde': date(2024,1,1), 'dosis_vigente_hasta': None},
    {'dosis_id': 3,  'vacuna_id': 2,  'dosis_tipo': 'SERIE_PRIMARIA', 'dosis_cant_ml': 0.5, 'dosis_area_aplicacion': 'Muslo derecho',        'dosis_edad_oportuna_dias': 60,   'dosis_intervalo_min_dias': 28, 'dosis_limite_edad_dias': 210,  'dosis_vigente_desde': date(2024,1,1), 'dosis_vigente_hasta': None},
    {'dosis_id': 4,  'vacuna_id': 2,  'dosis_tipo': 'SERIE_PRIMARIA', 'dosis_cant_ml': 0.5, 'dosis_area_aplicacion': 'Muslo derecho',        'dosis_edad_oportuna_dias': 180,  'dosis_intervalo_min_dias': 60, 'dosis_limite_edad_dias': 365,  'dosis_vigente_desde': date(2024,1,1), 'dosis_vigente_hasta': None},
    {'dosis_id': 5,  'vacuna_id': 3,  'dosis_tipo': 'SERIE_PRIMARIA', 'dosis_cant_ml': 0.5, 'dosis_area_aplicacion': 'Muslo izquierdo',      'dosis_edad_oportuna_dias': 60,   'dosis_intervalo_min_dias': 0,  'dosis_limite_edad_dias': 120,  'dosis_vigente_desde': date(2024,1,1), 'dosis_vigente_hasta': None},
    {'dosis_id': 6,  'vacuna_id': 3,  'dosis_tipo': 'SERIE_PRIMARIA', 'dosis_cant_ml': 0.5, 'dosis_area_aplicacion': 'Muslo izquierdo',      'dosis_edad_oportuna_dias': 120,  'dosis_intervalo_min_dias': 28, 'dosis_limite_edad_dias': 180,  'dosis_vigente_desde': date(2024,1,1), 'dosis_vigente_hasta': None},
    {'dosis_id': 7,  'vacuna_id': 3,  'dosis_tipo': 'SERIE_PRIMARIA', 'dosis_cant_ml': 0.5, 'dosis_area_aplicacion': 'Muslo izquierdo',      'dosis_edad_oportuna_dias': 180,  'dosis_intervalo_min_dias': 28, 'dosis_limite_edad_dias': 270,  'dosis_vigente_desde': date(2024,1,1), 'dosis_vigente_hasta': None},
    {'dosis_id': 8,  'vacuna_id': 4,  'dosis_tipo': 'SERIE_PRIMARIA', 'dosis_cant_ml': 1.5, 'dosis_area_aplicacion': 'Oral',                 'dosis_edad_oportuna_dias': 60,   'dosis_intervalo_min_dias': 0,  'dosis_limite_edad_dias': 120,  'dosis_vigente_desde': date(2024,1,1), 'dosis_vigente_hasta': None},
    {'dosis_id': 9,  'vacuna_id': 4,  'dosis_tipo': 'SERIE_PRIMARIA', 'dosis_cant_ml': 1.5, 'dosis_area_aplicacion': 'Oral',                 'dosis_edad_oportuna_dias': 120,  'dosis_intervalo_min_dias': 28, 'dosis_limite_edad_dias': 240,  'dosis_vigente_desde': date(2024,1,1), 'dosis_vigente_hasta': None},
    {'dosis_id': 10, 'vacuna_id': 5,  'dosis_tipo': 'SERIE_PRIMARIA', 'dosis_cant_ml': 0.5, 'dosis_area_aplicacion': 'Muslo derecho',        'dosis_edad_oportuna_dias': 60,   'dosis_intervalo_min_dias': 0,  'dosis_limite_edad_dias': 120,  'dosis_vigente_desde': date(2024,1,1), 'dosis_vigente_hasta': None},
    {'dosis_id': 11, 'vacuna_id': 5,  'dosis_tipo': 'SERIE_PRIMARIA', 'dosis_cant_ml': 0.5, 'dosis_area_aplicacion': 'Muslo derecho',        'dosis_edad_oportuna_dias': 120,  'dosis_intervalo_min_dias': 28, 'dosis_limite_edad_dias': 180,  'dosis_vigente_desde': date(2024,1,1), 'dosis_vigente_hasta': None},
    {'dosis_id': 12, 'vacuna_id': 5,  'dosis_tipo': 'REFUERZO',       'dosis_cant_ml': 0.5, 'dosis_area_aplicacion': 'Muslo derecho',        'dosis_edad_oportuna_dias': 365,  'dosis_intervalo_min_dias': 60, 'dosis_limite_edad_dias': 730,  'dosis_vigente_desde': date(2024,1,1), 'dosis_vigente_hasta': None},
    {'dosis_id': 13, 'vacuna_id': 6,  'dosis_tipo': 'ANUAL',          'dosis_cant_ml': 0.5, 'dosis_area_aplicacion': 'Deltoides',            'dosis_edad_oportuna_dias': 180,  'dosis_intervalo_min_dias': 0,  'dosis_limite_edad_dias': 365,  'dosis_vigente_desde': date(2024,1,1), 'dosis_vigente_hasta': None},
    {'dosis_id': 14, 'vacuna_id': 7,  'dosis_tipo': 'SERIE_PRIMARIA', 'dosis_cant_ml': 0.5, 'dosis_area_aplicacion': 'Deltoides izquierdo',  'dosis_edad_oportuna_dias': 365,  'dosis_intervalo_min_dias': 0,  'dosis_limite_edad_dias': 548,  'dosis_vigente_desde': date(2024,1,1), 'dosis_vigente_hasta': None},
    {'dosis_id': 15, 'vacuna_id': 7,  'dosis_tipo': 'REFUERZO',       'dosis_cant_ml': 0.5, 'dosis_area_aplicacion': 'Deltoides izquierdo',  'dosis_edad_oportuna_dias': 1460, 'dosis_intervalo_min_dias': 28, 'dosis_limite_edad_dias': 2190, 'dosis_vigente_desde': date(2024,1,1), 'dosis_vigente_hasta': None},
    {'dosis_id': 16, 'vacuna_id': 8,  'dosis_tipo': 'REFUERZO',       'dosis_cant_ml': 0.5, 'dosis_area_aplicacion': 'Deltoides',            'dosis_edad_oportuna_dias': 548,  'dosis_intervalo_min_dias': 0,  'dosis_limite_edad_dias': 730,  'dosis_vigente_desde': date(2024,1,1), 'dosis_vigente_hasta': None},
    {'dosis_id': 17, 'vacuna_id': 9,  'dosis_tipo': 'UNICA',          'dosis_cant_ml': 0.5, 'dosis_area_aplicacion': 'Deltoides izquierdo',  'dosis_edad_oportuna_dias': 365,  'dosis_intervalo_min_dias': 0,  'dosis_limite_edad_dias': 548,  'dosis_vigente_desde': date(2024,1,1), 'dosis_vigente_hasta': None},
    {'dosis_id': 18, 'vacuna_id': 10, 'dosis_tipo': 'SERIE_PRIMARIA', 'dosis_cant_ml': 0.5, 'dosis_area_aplicacion': 'Deltoides',            'dosis_edad_oportuna_dias': 365,  'dosis_intervalo_min_dias': 0,  'dosis_limite_edad_dias': 730,  'dosis_vigente_desde': date(2024,1,1), 'dosis_vigente_hasta': None},
    {'dosis_id': 19, 'vacuna_id': 10, 'dosis_tipo': 'SERIE_PRIMARIA', 'dosis_cant_ml': 0.5, 'dosis_area_aplicacion': 'Deltoides',            'dosis_edad_oportuna_dias': 548,  'dosis_intervalo_min_dias': 28, 'dosis_limite_edad_dias': 1095, 'dosis_vigente_desde': date(2024,1,1), 'dosis_vigente_hasta': None},
]

ESQUEMAS = [
    {
        'esquema_id': 1,
        'esquema_nombre': 'Esquema Nacional de Vacunación 2024',
        'esquema_fecha_vigencia': date(2024, 1, 1),
        'esquema_vigente_desde': date(2024, 1, 1),
        'esquema_vigente_hasta': None,
    },
]

DOSIS_ESQUEMAS = [{'dosis_esq_id': i+1, 'esquema_id': 1, 'dosis_id': d['dosis_id']} for i, d in enumerate(DOSIS)]

PADECIMIENTOS = [
    {'padecimiento_id': 1, 'padecimiento_nombre': 'Tuberculosis',  'padecimiento_descripcion': 'Infección por Mycobacterium tuberculosis', 'padecimiento_activo': True},
    {'padecimiento_id': 2, 'padecimiento_nombre': 'Hepatitis B',   'padecimiento_descripcion': 'Infección viral del hígado por VHB',       'padecimiento_activo': True},
    {'padecimiento_id': 3, 'padecimiento_nombre': 'Rotavirus',     'padecimiento_descripcion': 'Principal causa de diarrea grave en niños','padecimiento_activo': True},
    {'padecimiento_id': 4, 'padecimiento_nombre': 'Neumococo',     'padecimiento_descripcion': 'Causante de neumonía y meningitis',        'padecimiento_activo': True},
    {'padecimiento_id': 5, 'padecimiento_nombre': 'Influenza',     'padecimiento_descripcion': 'Infección viral respiratoria estacional',  'padecimiento_activo': True},
    {'padecimiento_id': 6, 'padecimiento_nombre': 'Sarampión',     'padecimiento_descripcion': 'Enfermedad viral altamente contagiosa',    'padecimiento_activo': True},
    {'padecimiento_id': 7, 'padecimiento_nombre': 'Varicela',      'padecimiento_descripcion': 'Infección viral con erupción cutánea',     'padecimiento_activo': True},
]

# ── Pacientes ─────────────────────────────────────────────────────

PACIENTES = [
    {
        'paciente_id': 1, 'paciente_prim_nombre': 'Cesar', 'paciente_seg_nombre': None,
        'paciente_apellido_pat': 'Reyes', 'paciente_apellido_mat': 'González',
        'paciente_num_cert_nac': '20260303001', 'paciente_curp': 'REGC260303HNLYNS09',
        'paciente_fecha_nac': date(2026, 3, 3), 'paciente_sexo': 'M',
        'paciente_nfc': 'NFC-001', 'paciente_imagen': None,
        'esquema_id': 1, 'esquema_nombre': 'Esquema Nacional de Vacunación 2024',
    },
    {
        'paciente_id': 2, 'paciente_prim_nombre': 'Enrique', 'paciente_seg_nombre': None,
        'paciente_apellido_pat': 'Mendoza', 'paciente_apellido_mat': 'López',
        'paciente_num_cert_nac': '20250115002', 'paciente_curp': 'MELE250115HNLNPN07',
        'paciente_fecha_nac': date(2025, 1, 15), 'paciente_sexo': 'M',
        'paciente_nfc': 'NFC-002', 'paciente_imagen': None,
        'esquema_id': 1, 'esquema_nombre': 'Esquema Nacional de Vacunación 2024',
    },
]

# tutor_id referencia usuario_id (Juan = usuario_id 3)
PACIENTES_TUTORES = [
    {'pac_tut_id': 1, 'paciente_id': 1, 'tutor_id': 3, 'paciente': 'Cesar Reyes',   'tutor': 'Juan Reyes'},
    {'pac_tut_id': 2, 'paciente_id': 2, 'tutor_id': 3, 'paciente': 'Enrique Mendoza', 'tutor': 'Juan Reyes'},
]

# ── Inventario ────────────────────────────────────────────────────

FABRICANTES = [
    {'fabricante_id': 1, 'fabricante_nombre': 'BIRMEX',         'pais_id': 1, 'pais_nombre': 'México', 'fabricante_telefono': '5512345678'},
    {'fabricante_id': 2, 'fabricante_nombre': 'Sanofi Pasteur', 'pais_id': 1, 'pais_nombre': 'México', 'fabricante_telefono': '5587654321'},
]

PROVEEDORES = []  # nueva tabla

LOTES = [
    {
        'lote_id': 1, 'lote_codigo': 'LOT-2024-001',
        'lote_fecha_fabricacion': date(2024, 1, 1), 'lote_fecha_caducidad': date(2026, 12, 31),
        'lote_cant_inicial': 500, 'vacuna_id': 1, 'vacuna_nombre': 'BCG',
        'fabricante_id': 1, 'fabricante_nombre': 'BIRMEX', 'proveedor_id': None,
    },
    {
        'lote_id': 2, 'lote_codigo': 'LOT-2024-002',
        'lote_fecha_fabricacion': date(2024, 2, 1), 'lote_fecha_caducidad': date(2026, 12, 31),
        'lote_cant_inicial': 300, 'vacuna_id': 2, 'vacuna_nombre': 'Hepatitis B',
        'fabricante_id': 1, 'fabricante_nombre': 'BIRMEX', 'proveedor_id': None,
    },
]

INVENTARIOS = [
    {
        'inventario_id': 1, 'centro_id': 2, 'centro_nombre': 'Unidad Médica San Pedro',
        'lote_id': 1, 'lote_codigo': 'LOT-2024-001',
        'lote_fecha_fabricacion': date(2024, 1, 1), 'lote_fecha_caducidad': date(2026, 12, 31),
        'vacuna_nombre': 'BCG', 'fabricante_nombre': 'BIRMEX',
        'inventario_stock_inicial': 200, 'inventario_stock_actual': 198,
        'inventario_activo_desde': datetime(2024, 1, 5, 8, 0),  # confirmado por responsable
        'inventario_activo': True,  # campo derivado para compatibilidad con templates
        'usuario_id': 2, 'inventario_origen_id': None,
    },
    {
        'inventario_id': 2, 'centro_id': 2, 'centro_nombre': 'Unidad Médica San Pedro',
        'lote_id': 2, 'lote_codigo': 'LOT-2024-002',
        'lote_fecha_fabricacion': date(2024, 2, 1), 'lote_fecha_caducidad': date(2026, 12, 31),
        'vacuna_nombre': 'Hepatitis B', 'fabricante_nombre': 'BIRMEX',
        'inventario_stock_inicial': 150, 'inventario_stock_actual': 148,
        'inventario_activo_desde': datetime(2024, 2, 5, 8, 0),
        'inventario_activo': True,
        'usuario_id': 2, 'inventario_origen_id': None,
    },
]

# ── Aplicaciones ──────────────────────────────────────────────────
# Ahora almacena usuario_id + centro_id + lote_id (no inventario_id).

APLICACIONES = [
    {
        'aplicacion_id': 1,
        'paciente_id': 1, 'paciente': 'Cesar Reyes González',
        'usuario_id': 2, 'responsable': 'Diego Mendoza',
        'centro_id': 2, 'centro_nombre': 'Unidad Médica San Pedro',
        'lote_id': 1, 'dosis_id': 1,
        'vacuna_nombre': 'BCG', 'dosis_tipo': 'UNICA',
        'aplicacion_timestamp': datetime(2026, 3, 18, 9, 44),
        'aplicacion_registrado_en': datetime(2026, 3, 18, 9, 44),
        'aplicacion_observaciones': 'Sin reacciones adversas.',
    },
    {
        'aplicacion_id': 2,
        'paciente_id': 2, 'paciente': 'Enrique Mendoza López',
        'usuario_id': 2, 'responsable': 'Diego Mendoza',
        'centro_id': 2, 'centro_nombre': 'Unidad Médica San Pedro',
        'lote_id': 2, 'dosis_id': 2,
        'vacuna_nombre': 'Hepatitis B', 'dosis_tipo': 'SERIE_PRIMARIA',
        'aplicacion_timestamp': datetime(2026, 3, 19, 10, 15),
        'aplicacion_registrado_en': datetime(2026, 3, 19, 10, 15),
        'aplicacion_observaciones': 'Primera dosis de la serie.',
    },
]

# ── Alertas ───────────────────────────────────────────────────────

ALERTAS_INVENTARIO = []
ALERTAS_DOSIS = [
    {
        'alerta_dosis_pac_id': 1,
        'paciente_id': 1, 'paciente': 'Cesar Reyes González',
        'dosis_id': 2, 'alerta_dosis_pac_tipo': 'APLICABLE',
        'alerta_dosis_pac_timestamp': datetime(2026, 3, 18, 23, 8),
    },
]


# ── Utilidades ────────────────────────────────────────────────────

def get_by_id(lst, id_field, id_val):
    return next((x for x in lst if x[id_field] == id_val), None)


def next_id(lst, id_field):
    if not lst:
        return 1
    return max(x[id_field] for x in lst) + 1


def _rol_nombre(rol_id):
    r = get_by_id(ROLES, 'rol_id', rol_id)
    return r['rol_nombre'] if r else None


def _usuario_rol_primario(usuario_id):
    """Devuelve el rol de mayor privilegio del usuario."""
    ids = [ur['rol_id'] for ur in USUARIOS_ROLES if ur['usuario_id'] == usuario_id]
    nombres = [_rol_nombre(rid) for rid in ids]
    for rol in ('admin', 'responsable', 'tutor'):
        if rol in nombres:
            return rol
    return None


def _usuario_como_rol(u, rol):
    """Transforma un dict de USUARIOS al formato de rol para los templates."""
    login = get_by_id(LOGIN, 'usuario_id', u['usuario_id']) or {}
    base = {
        'usuario_id':             u['usuario_id'],
        'usuario_prim_nombre':    u['usuario_prim_nombre'],
        'usuario_seg_nombre':     u.get('usuario_seg_nombre'),
        'usuario_apellido_pat':   u['usuario_apellido_pat'],
        'usuario_apellido_mat':   u.get('usuario_apellido_mat'),
        'usuario_curp':           u['usuario_curp'],
        'usuario_telefono':       u['usuario_telefono'],
        'usuario_rfc':            u.get('usuario_rfc'),
        'usuario_activo':         u.get('usuario_activo', True),
        'centro_id':              u.get('centro_id'),
        f'{rol}_email':           login.get('login_correo', ''),
        f'{rol}_contrasena':      login.get('login_contrasena', ''),
    }
    # Aliases con prefijo de rol para compatibilidad con templates
    prefijos = {
        f'{rol}_id':           u['usuario_id'],
        f'{rol}_prim_nombre':  u['usuario_prim_nombre'],
        f'{rol}_seg_nombre':   u.get('usuario_seg_nombre'),
        f'{rol}_apellido_pat': u['usuario_apellido_pat'],
        f'{rol}_apellido_mat': u.get('usuario_apellido_mat'),
        f'{rol}_curp':         u['usuario_curp'],
        f'{rol}_telefono':     u['usuario_telefono'],
        f'{rol}_rfc':          u.get('usuario_rfc'),
    }
    return {**base, **prefijos}

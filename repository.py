from __future__ import annotations
# repository.py — Capa de acceso a datos de VacunaTrack (esquema v3)
#
# Cada función tiene dos ramas:
#   • db.using_postgres() → True  → consulta PostgreSQL (esquema v3)
#   • db.using_postgres() → False → listas en memoria de data.py
#
# Tabla usuarios unificada reemplaza administradores/responsables/tutores.
# aplicaciones guarda usuario_id + centro_id + lote_id (no inventario_id).
# inventario_activo_desde IS NOT NULL reemplaza inventario_activo = true.

import data
import db
from werkzeug.security import check_password_hash

_ROLE_PRIORITY = {'admin': 0, 'responsable': 1, 'tutor': 2}


# ─────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────

def buscar_usuario_por_email(email: str) -> dict | None:
    email = email.lower()
    if db.using_postgres():
        return db.query_one("""
            SELECT u.usuario_id AS id,
                   l.login_correo AS email,
                   l.login_contrasena AS password,
                   u.usuario_prim_nombre AS first_name,
                   u.usuario_apellido_pat AS last_name,
                   r.rol_nombre AS role
            FROM login l
            JOIN usuarios u ON u.usuario_id = l.usuario_id
            JOIN usuarios_roles ur ON ur.usuario_id = u.usuario_id
            JOIN roles r ON r.rol_id = ur.rol_id
            WHERE l.login_correo = %s
            ORDER BY CASE r.rol_nombre
                WHEN 'admin' THEN 0
                WHEN 'responsable' THEN 1
                ELSE 2 END
            LIMIT 1
        """, (email,))
    for lg in data.LOGIN:
        if lg['login_correo'] == email:
            u = data.get_by_id(data.USUARIOS, 'usuario_id', lg['usuario_id'])
            if not u:
                continue
            roles = sorted(_roles_de_usuario_mem(u['usuario_id']),
                           key=lambda r: _ROLE_PRIORITY.get(r, 99))
            role = roles[0] if roles else 'tutor'
            return {
                'id': u['usuario_id'],
                'email': lg['login_correo'],
                'password': lg['login_contrasena'],
                'first_name': u['usuario_prim_nombre'],
                'last_name': u['usuario_apellido_pat'],
                'role': role,
            }
    return None


def verificar_password(usuario: dict, password: str) -> bool:
    return check_password_hash(usuario['password'], password)


def cambiar_password(role: str, user_id: int, nuevo_hash: str) -> None:
    if db.using_postgres():
        db.execute('UPDATE login SET login_contrasena = %s WHERE usuario_id = %s',
                   (nuevo_hash, user_id))
        return
    for lg in data.LOGIN:
        if lg['usuario_id'] == user_id:
            lg['login_contrasena'] = nuevo_hash


# ─────────────────────────────────────────────
# HELPER: roles en memoria
# ─────────────────────────────────────────────

def _roles_de_usuario_mem(usuario_id: int) -> list[str]:
    roles = []
    for ur in data.USUARIOS_ROLES:
        if ur['usuario_id'] == usuario_id:
            rol = data.get_by_id(data.ROLES, 'rol_id', ur['rol_id'])
            if rol:
                roles.append(rol['rol_nombre'])
    return roles


# ─────────────────────────────────────────────
# HELPER interno: INSERT usuarios + login + usuarios_roles
# ─────────────────────────────────────────────

def _crear_usuario_pg(datos: dict, rol_nombre: str) -> int:
    """Inserta en usuarios, login y usuarios_roles. Devuelve usuario_id."""
    u = db.execute_returning("""
        INSERT INTO usuarios
            (usuario_prim_nombre, usuario_seg_nombre, usuario_apellido_pat,
             usuario_apellido_mat, usuario_telefono, usuario_curp, usuario_rfc, centro_id)
        VALUES
            (%(usuario_prim_nombre)s, %(usuario_seg_nombre)s, %(usuario_apellido_pat)s,
             %(usuario_apellido_mat)s, %(usuario_telefono)s, %(usuario_curp)s,
             %(usuario_rfc)s, %(centro_id)s)
        RETURNING usuario_id
    """, {
        'usuario_prim_nombre':  datos.get('usuario_prim_nombre'),
        'usuario_seg_nombre':   datos.get('usuario_seg_nombre'),
        'usuario_apellido_pat': datos.get('usuario_apellido_pat'),
        'usuario_apellido_mat': datos.get('usuario_apellido_mat'),
        'usuario_telefono':     datos.get('usuario_telefono'),
        'usuario_curp':         datos.get('usuario_curp'),
        'usuario_rfc':          datos.get('usuario_rfc'),
        'centro_id':            datos.get('centro_id'),
    })
    uid = u['usuario_id']
    db.execute(
        'INSERT INTO login (usuario_id, login_correo, login_contrasena) VALUES (%s, %s, %s)',
        (uid, datos['login_correo'], datos['login_contrasena']))
    rol = db.query_one('SELECT rol_id FROM roles WHERE rol_nombre = %s', (rol_nombre,))
    if rol:
        db.execute(
            'INSERT INTO usuarios_roles (usuario_id, rol_id) VALUES (%s, %s) ON CONFLICT DO NOTHING',
            (uid, rol['rol_id']))
    return uid


def _crear_usuario_mem(datos: dict, rol_nombre: str) -> dict:
    """Inserta en USUARIOS, LOGIN, USUARIOS_ROLES en memoria. Devuelve el dict de usuario."""
    nuevo_u = {
        'usuario_id':           data.next_id(data.USUARIOS, 'usuario_id'),
        'usuario_prim_nombre':  datos.get('usuario_prim_nombre', ''),
        'usuario_seg_nombre':   datos.get('usuario_seg_nombre'),
        'usuario_apellido_pat': datos.get('usuario_apellido_pat', ''),
        'usuario_apellido_mat': datos.get('usuario_apellido_mat'),
        'usuario_telefono':     datos.get('usuario_telefono', ''),
        'usuario_curp':         datos.get('usuario_curp', ''),
        'usuario_rfc':          datos.get('usuario_rfc'),
        'centro_id':            datos.get('centro_id'),
        'usuario_activo':       True,
        'usuario_imagen':       None,
    }
    data.USUARIOS.append(nuevo_u)
    data.LOGIN.append({
        'login_id':         data.next_id(data.LOGIN, 'login_id'),
        'usuario_id':       nuevo_u['usuario_id'],
        'login_correo':     datos.get('login_correo', ''),
        'login_contrasena': datos.get('login_contrasena', ''),
    })
    rol = next((r for r in data.ROLES if r['rol_nombre'] == rol_nombre), None)
    if rol:
        data.USUARIOS_ROLES.append({
            'us_rol_id':  data.next_id(data.USUARIOS_ROLES, 'us_rol_id'),
            'usuario_id': nuevo_u['usuario_id'],
            'rol_id':     rol['rol_id'],
        })
    return nuevo_u


# ─────────────────────────────────────────────
# ADMINISTRADORES
# ─────────────────────────────────────────────

def listar_administradores() -> list[dict]:
    if db.using_postgres():
        return db.query("""
            SELECT u.usuario_id AS admin_id,
                   u.usuario_prim_nombre AS admin_prim_nombre,
                   u.usuario_seg_nombre  AS admin_seg_nombre,
                   u.usuario_apellido_pat AS admin_apellido_pat,
                   u.usuario_apellido_mat AS admin_apellido_mat,
                   u.usuario_telefono AS admin_telefono,
                   u.usuario_curp AS admin_curp,
                   u.usuario_rfc  AS admin_rfc,
                   u.usuario_activo AS admin_activo,
                   u.usuario_imagen AS admin_imagen,
                   l.login_correo AS admin_email
            FROM usuarios u
            JOIN usuarios_roles ur ON ur.usuario_id = u.usuario_id
            JOIN roles r ON r.rol_id = ur.rol_id AND r.rol_nombre = 'admin'
            JOIN login l ON l.usuario_id = u.usuario_id
            ORDER BY u.usuario_apellido_pat, u.usuario_prim_nombre
        """)
    return [data._usuario_como_rol(u, 'admin') for u in data.USUARIOS
            if 'admin' in _roles_de_usuario_mem(u['usuario_id'])]


def obtener_administrador(admin_id: int) -> dict | None:
    if db.using_postgres():
        return db.query_one("""
            SELECT u.usuario_id AS admin_id,
                   u.usuario_prim_nombre AS admin_prim_nombre,
                   u.usuario_seg_nombre  AS admin_seg_nombre,
                   u.usuario_apellido_pat AS admin_apellido_pat,
                   u.usuario_apellido_mat AS admin_apellido_mat,
                   u.usuario_telefono AS admin_telefono,
                   u.usuario_curp AS admin_curp,
                   u.usuario_rfc  AS admin_rfc,
                   u.usuario_activo AS admin_activo,
                   u.usuario_imagen AS admin_imagen,
                   l.login_correo AS admin_email
            FROM usuarios u
            JOIN usuarios_roles ur ON ur.usuario_id = u.usuario_id
            JOIN roles r ON r.rol_id = ur.rol_id AND r.rol_nombre = 'admin'
            JOIN login l ON l.usuario_id = u.usuario_id
            WHERE u.usuario_id = %s
        """, (admin_id,))
    u = data.get_by_id(data.USUARIOS, 'usuario_id', admin_id)
    return data._usuario_como_rol(u, 'admin') if u else None


def crear_admin(datos: dict) -> dict:
    """datos usa claves admin_* (formulario) + admin_contrasena."""
    if db.using_postgres():
        uid = _crear_usuario_pg({
            'usuario_prim_nombre':  datos.get('admin_prim_nombre'),
            'usuario_seg_nombre':   datos.get('admin_seg_nombre'),
            'usuario_apellido_pat': datos.get('admin_apellido_pat'),
            'usuario_apellido_mat': datos.get('admin_apellido_mat'),
            'usuario_telefono':     datos.get('admin_telefono'),
            'usuario_curp':         datos.get('admin_curp'),
            'usuario_rfc':          datos.get('admin_rfc'),
            'centro_id':            None,
            'login_correo':         datos.get('admin_email'),
            'login_contrasena':     datos.get('admin_contrasena'),
        }, 'admin')
        return obtener_administrador(uid) or {}
    u = _crear_usuario_mem({
        'usuario_prim_nombre':  datos.get('admin_prim_nombre', ''),
        'usuario_seg_nombre':   datos.get('admin_seg_nombre'),
        'usuario_apellido_pat': datos.get('admin_apellido_pat', ''),
        'usuario_apellido_mat': datos.get('admin_apellido_mat'),
        'usuario_telefono':     datos.get('admin_telefono', ''),
        'usuario_curp':         datos.get('admin_curp', ''),
        'usuario_rfc':          datos.get('admin_rfc'),
        'centro_id':            None,
        'login_correo':         datos.get('admin_email', ''),
        'login_contrasena':     datos.get('admin_contrasena', ''),
    }, 'admin')
    return data._usuario_como_rol(u, 'admin')


def eliminar_admin(admin_id: int) -> None:
    if db.using_postgres():
        db.execute('DELETE FROM usuarios WHERE usuario_id = %s', (admin_id,))
        return
    data.USUARIOS[:] = [u for u in data.USUARIOS if u['usuario_id'] != admin_id]
    data.LOGIN[:] = [lg for lg in data.LOGIN if lg['usuario_id'] != admin_id]
    data.USUARIOS_ROLES[:] = [ur for ur in data.USUARIOS_ROLES if ur['usuario_id'] != admin_id]


# ─────────────────────────────────────────────
# PACIENTES
# ─────────────────────────────────────────────

def listar_pacientes() -> list[dict]:
    if db.using_postgres():
        return db.query("""
            SELECT p.*, e.esquema_nombre
            FROM pacientes p
            JOIN esquemas e ON e.esquema_id = p.esquema_id
            ORDER BY p.paciente_apellido_pat, p.paciente_prim_nombre
        """)
    return list(data.PACIENTES)


def obtener_paciente(paciente_id: int) -> dict | None:
    if db.using_postgres():
        return db.query_one("""
            SELECT p.*, e.esquema_nombre
            FROM pacientes p
            JOIN esquemas e ON e.esquema_id = p.esquema_id
            WHERE p.paciente_id = %s
        """, (paciente_id,))
    return data.get_by_id(data.PACIENTES, 'paciente_id', paciente_id)


def obtener_paciente_por_nfc(nfc_uid: str) -> dict | None:
    if db.using_postgres():
        return db.query_one("""
            SELECT p.*, e.esquema_nombre
            FROM pacientes p
            JOIN esquemas e ON e.esquema_id = p.esquema_id
            WHERE p.paciente_nfc = %s
        """, (nfc_uid,))
    return next((p for p in data.PACIENTES if p.get('paciente_nfc') == nfc_uid), None)


def obtener_paciente_por_curp(curp: str) -> dict | None:
    if db.using_postgres():
        return db.query_one("""
            SELECT p.*, e.esquema_nombre
            FROM pacientes p
            JOIN esquemas e ON e.esquema_id = p.esquema_id
            WHERE p.paciente_curp = %s
        """, (curp.upper(),))
    return next((p for p in data.PACIENTES if p.get('paciente_curp') == curp.upper()), None)


def obtener_paciente_por_cert_nac(cert_nac: str) -> dict | None:
    if db.using_postgres():
        return db.query_one("""
            SELECT p.*, e.esquema_nombre
            FROM pacientes p
            JOIN esquemas e ON e.esquema_id = p.esquema_id
            WHERE p.paciente_num_cert_nac = %s
        """, (cert_nac.strip(),))
    return next((p for p in data.PACIENTES if p.get('paciente_num_cert_nac') == cert_nac.strip()), None)


def crear_paciente(datos: dict) -> dict:
    if db.using_postgres():
        return db.execute_returning("""
            INSERT INTO pacientes
                (paciente_prim_nombre, paciente_seg_nombre, paciente_apellido_pat,
                 paciente_apellido_mat, paciente_curp, paciente_num_cert_nac,
                 paciente_fecha_nac, paciente_sexo, paciente_nfc, esquema_id)
            VALUES
                (%(paciente_prim_nombre)s, %(paciente_seg_nombre)s, %(paciente_apellido_pat)s,
                 %(paciente_apellido_mat)s, %(paciente_curp)s, %(paciente_num_cert_nac)s,
                 %(paciente_fecha_nac)s, %(paciente_sexo)s, %(paciente_nfc)s, %(esquema_id)s)
            RETURNING *
        """, datos)
    nuevo = dict(datos)
    nuevo['paciente_id'] = data.next_id(data.PACIENTES, 'paciente_id')
    data.PACIENTES.append(nuevo)
    return nuevo


def eliminar_paciente(paciente_id: int) -> bool:
    if db.using_postgres():
        if db.query_one('SELECT 1 FROM aplicaciones WHERE paciente_id = %s', (paciente_id,)):
            return False
        db.execute('DELETE FROM pacientes WHERE paciente_id = %s', (paciente_id,))
        return True
    if any(a['paciente_id'] == paciente_id for a in data.APLICACIONES):
        return False
    data.PACIENTES[:] = [p for p in data.PACIENTES if p['paciente_id'] != paciente_id]
    data.PACIENTES_TUTORES[:] = [pt for pt in data.PACIENTES_TUTORES
                                  if pt['paciente_id'] != paciente_id]
    return True


# ─────────────────────────────────────────────
# TUTORES
# ─────────────────────────────────────────────

def listar_tutores() -> list[dict]:
    if db.using_postgres():
        return db.query("""
            SELECT u.usuario_id AS tutor_id,
                   u.usuario_prim_nombre AS tutor_prim_nombre,
                   u.usuario_seg_nombre  AS tutor_seg_nombre,
                   u.usuario_apellido_pat AS tutor_apellido_pat,
                   u.usuario_apellido_mat AS tutor_apellido_mat,
                   u.usuario_telefono AS tutor_telefono,
                   u.usuario_curp AS tutor_curp,
                   u.usuario_activo AS tutor_activo,
                   u.usuario_imagen AS tutor_imagen,
                   l.login_correo AS tutor_email
            FROM usuarios u
            JOIN usuarios_roles ur ON ur.usuario_id = u.usuario_id
            JOIN roles r ON r.rol_id = ur.rol_id AND r.rol_nombre = 'tutor'
            JOIN login l ON l.usuario_id = u.usuario_id
            ORDER BY u.usuario_apellido_pat, u.usuario_prim_nombre
        """)
    return [data._usuario_como_rol(u, 'tutor') for u in data.USUARIOS
            if 'tutor' in _roles_de_usuario_mem(u['usuario_id'])]


def obtener_tutor(tutor_id: int) -> dict | None:
    if db.using_postgres():
        return db.query_one("""
            SELECT u.usuario_id AS tutor_id,
                   u.usuario_prim_nombre AS tutor_prim_nombre,
                   u.usuario_seg_nombre  AS tutor_seg_nombre,
                   u.usuario_apellido_pat AS tutor_apellido_pat,
                   u.usuario_apellido_mat AS tutor_apellido_mat,
                   u.usuario_telefono AS tutor_telefono,
                   u.usuario_curp AS tutor_curp,
                   u.usuario_activo AS tutor_activo,
                   u.usuario_imagen AS tutor_imagen,
                   l.login_correo AS tutor_email
            FROM usuarios u
            JOIN usuarios_roles ur ON ur.usuario_id = u.usuario_id
            JOIN roles r ON r.rol_id = ur.rol_id AND r.rol_nombre = 'tutor'
            JOIN login l ON l.usuario_id = u.usuario_id
            WHERE u.usuario_id = %s
        """, (tutor_id,))
    u = data.get_by_id(data.USUARIOS, 'usuario_id', tutor_id)
    return data._usuario_como_rol(u, 'tutor') if u else None


def crear_tutor(datos: dict) -> dict:
    """datos usa claves tutor_* (formulario) + tutor_contrasena."""
    if db.using_postgres():
        uid = _crear_usuario_pg({
            'usuario_prim_nombre':  datos.get('tutor_prim_nombre'),
            'usuario_seg_nombre':   datos.get('tutor_seg_nombre'),
            'usuario_apellido_pat': datos.get('tutor_apellido_pat'),
            'usuario_apellido_mat': datos.get('tutor_apellido_mat'),
            'usuario_telefono':     datos.get('tutor_telefono'),
            'usuario_curp':         datos.get('tutor_curp'),
            'usuario_rfc':          None,
            'centro_id':            None,
            'login_correo':         datos.get('tutor_email'),
            'login_contrasena':     datos.get('tutor_contrasena'),
        }, 'tutor')
        return obtener_tutor(uid) or {}
    u = _crear_usuario_mem({
        'usuario_prim_nombre':  datos.get('tutor_prim_nombre', ''),
        'usuario_seg_nombre':   datos.get('tutor_seg_nombre'),
        'usuario_apellido_pat': datos.get('tutor_apellido_pat', ''),
        'usuario_apellido_mat': datos.get('tutor_apellido_mat'),
        'usuario_telefono':     datos.get('tutor_telefono', ''),
        'usuario_curp':         datos.get('tutor_curp', ''),
        'usuario_rfc':          None,
        'centro_id':            None,
        'login_correo':         datos.get('tutor_email', ''),
        'login_contrasena':     datos.get('tutor_contrasena', ''),
    }, 'tutor')
    return data._usuario_como_rol(u, 'tutor')


def actualizar_tutor(tutor_id: int, campos: dict) -> bool:
    """campos usa claves usuario_* (internas)."""
    if db.using_postgres():
        if not campos:
            return False
        set_parts = [f'{k} = %s' for k in campos]
        values = list(campos.values()) + [tutor_id]
        db.execute(f"UPDATE usuarios SET {', '.join(set_parts)} WHERE usuario_id = %s", values)
        return True
    u = data.get_by_id(data.USUARIOS, 'usuario_id', tutor_id)
    if not u:
        return False
    u.update(campos)
    return True


def eliminar_tutor(tutor_id: int) -> bool:
    if db.using_postgres():
        if db.query_one('SELECT 1 FROM pacientes_tutores WHERE tutor_id = %s', (tutor_id,)):
            return False
        db.execute('DELETE FROM usuarios WHERE usuario_id = %s', (tutor_id,))
        return True
    if any(pt['tutor_id'] == tutor_id for pt in data.PACIENTES_TUTORES):
        return False
    data.USUARIOS[:] = [u for u in data.USUARIOS if u['usuario_id'] != tutor_id]
    data.LOGIN[:] = [lg for lg in data.LOGIN if lg['usuario_id'] != tutor_id]
    data.USUARIOS_ROLES[:] = [ur for ur in data.USUARIOS_ROLES if ur['usuario_id'] != tutor_id]
    return True


def pacientes_de_tutor(tutor_id: int) -> list[dict]:
    if db.using_postgres():
        return db.query("""
            SELECT p.*, e.esquema_nombre
            FROM pacientes p
            JOIN pacientes_tutores pt ON pt.paciente_id = p.paciente_id
            JOIN esquemas e ON e.esquema_id = p.esquema_id
            WHERE pt.tutor_id = %s
        """, (tutor_id,))
    ids = [pt['paciente_id'] for pt in data.PACIENTES_TUTORES if pt['tutor_id'] == tutor_id]
    return [p for p in data.PACIENTES if p['paciente_id'] in ids]


# ─────────────────────────────────────────────
# RESPONSABLES
# ─────────────────────────────────────────────

def listar_responsables() -> list[dict]:
    if db.using_postgres():
        rows = db.query("""
            SELECT u.usuario_id AS responsable_id,
                   u.usuario_prim_nombre AS responsable_prim_nombre,
                   u.usuario_seg_nombre  AS responsable_seg_nombre,
                   u.usuario_apellido_pat AS responsable_apellido_pat,
                   u.usuario_apellido_mat AS responsable_apellido_mat,
                   u.usuario_telefono AS responsable_telefono,
                   u.usuario_curp AS responsable_curp,
                   u.usuario_rfc  AS responsable_rfc,
                   u.usuario_activo AS responsable_activo,
                   u.usuario_imagen AS responsable_imagen,
                   u.centro_id,
                   cs.centro_nombre,
                   l.login_correo AS responsable_email
            FROM usuarios u
            JOIN usuarios_roles ur ON ur.usuario_id = u.usuario_id
            JOIN roles r ON r.rol_id = ur.rol_id AND r.rol_nombre = 'responsable'
            JOIN login l ON l.usuario_id = u.usuario_id
            LEFT JOIN centros_salud cs ON cs.centro_id = u.centro_id
            ORDER BY u.usuario_apellido_pat, u.usuario_prim_nombre
        """)
        for row in rows:
            row['cedulas'] = cedulas_de_responsable(row['responsable_id'])
        return rows
    resultado = []
    for u in data.USUARIOS:
        if 'responsable' not in _roles_de_usuario_mem(u['usuario_id']):
            continue
        r2 = data._usuario_como_rol(u, 'responsable')
        r2['cedulas'] = cedulas_de_responsable(u['usuario_id'])
        resultado.append(r2)
    return resultado


def obtener_responsable(responsable_id: int) -> dict | None:
    if db.using_postgres():
        return db.query_one("""
            SELECT u.usuario_id AS responsable_id,
                   u.usuario_prim_nombre AS responsable_prim_nombre,
                   u.usuario_seg_nombre  AS responsable_seg_nombre,
                   u.usuario_apellido_pat AS responsable_apellido_pat,
                   u.usuario_apellido_mat AS responsable_apellido_mat,
                   u.usuario_telefono AS responsable_telefono,
                   u.usuario_curp AS responsable_curp,
                   u.usuario_rfc  AS responsable_rfc,
                   u.usuario_activo AS responsable_activo,
                   u.usuario_imagen AS responsable_imagen,
                   u.centro_id,
                   cs.centro_nombre,
                   l.login_correo AS responsable_email
            FROM usuarios u
            JOIN usuarios_roles ur ON ur.usuario_id = u.usuario_id
            JOIN roles r ON r.rol_id = ur.rol_id AND r.rol_nombre = 'responsable'
            JOIN login l ON l.usuario_id = u.usuario_id
            LEFT JOIN centros_salud cs ON cs.centro_id = u.centro_id
            WHERE u.usuario_id = %s
        """, (responsable_id,))
    u = data.get_by_id(data.USUARIOS, 'usuario_id', responsable_id)
    return data._usuario_como_rol(u, 'responsable') if u else None


def crear_responsable(datos: dict) -> dict:
    """datos usa claves responsable_* (formulario) + responsable_contrasena."""
    if db.using_postgres():
        uid = _crear_usuario_pg({
            'usuario_prim_nombre':  datos.get('responsable_prim_nombre'),
            'usuario_seg_nombre':   datos.get('responsable_seg_nombre'),
            'usuario_apellido_pat': datos.get('responsable_apellido_pat'),
            'usuario_apellido_mat': datos.get('responsable_apellido_mat'),
            'usuario_telefono':     datos.get('responsable_telefono'),
            'usuario_curp':         datos.get('responsable_curp'),
            'usuario_rfc':          datos.get('responsable_rfc'),
            'centro_id':            datos.get('centro_id'),
            'login_correo':         datos.get('responsable_email'),
            'login_contrasena':     datos.get('responsable_contrasena'),
        }, 'responsable')
        return obtener_responsable(uid) or {}
    u = _crear_usuario_mem({
        'usuario_prim_nombre':  datos.get('responsable_prim_nombre', ''),
        'usuario_seg_nombre':   datos.get('responsable_seg_nombre'),
        'usuario_apellido_pat': datos.get('responsable_apellido_pat', ''),
        'usuario_apellido_mat': datos.get('responsable_apellido_mat'),
        'usuario_telefono':     datos.get('responsable_telefono', ''),
        'usuario_curp':         datos.get('responsable_curp', ''),
        'usuario_rfc':          datos.get('responsable_rfc'),
        'centro_id':            datos.get('centro_id'),
        'login_correo':         datos.get('responsable_email', ''),
        'login_contrasena':     datos.get('responsable_contrasena', ''),
    }, 'responsable')
    return data._usuario_como_rol(u, 'responsable')


def eliminar_responsable(responsable_id: int) -> bool:
    if db.using_postgres():
        if db.query_one('SELECT 1 FROM aplicaciones WHERE usuario_id = %s', (responsable_id,)):
            return False
        db.execute('DELETE FROM usuarios WHERE usuario_id = %s', (responsable_id,))
        return True
    if any(a.get('usuario_id') == responsable_id for a in data.APLICACIONES):
        return False
    data.USUARIOS[:] = [u for u in data.USUARIOS if u['usuario_id'] != responsable_id]
    data.LOGIN[:] = [lg for lg in data.LOGIN if lg['usuario_id'] != responsable_id]
    data.CEDULAS[:] = [c for c in data.CEDULAS if c['usuario_id'] != responsable_id]
    data.USUARIOS_ROLES[:] = [ur for ur in data.USUARIOS_ROLES
                               if ur['usuario_id'] != responsable_id]
    return True


def cedulas_de_responsable(usuario_id: int) -> list[dict]:
    if db.using_postgres():
        return db.query('SELECT * FROM cedulas WHERE usuario_id = %s', (usuario_id,))
    return [c for c in data.CEDULAS if c['usuario_id'] == usuario_id]


def agregar_cedula(usuario_id: int, numero: str, especialidad: str | None) -> dict:
    if db.using_postgres():
        return db.execute_returning("""
            INSERT INTO cedulas (cedula_numero, cedula_especialidad, usuario_id)
            VALUES (%s, %s, %s) RETURNING *
        """, (numero, especialidad, usuario_id))
    nueva = {
        'cedula_id':         data.next_id(data.CEDULAS, 'cedula_id'),
        'cedula_numero':     numero,
        'cedula_especialidad': especialidad,
        'usuario_id':        usuario_id,
    }
    data.CEDULAS.append(nueva)
    return nueva


# ─────────────────────────────────────────────
# RELACIONES PACIENTE-TUTOR
# ─────────────────────────────────────────────

def listar_relaciones() -> list[dict]:
    if db.using_postgres():
        return db.query("""
            SELECT pt.*,
                INITCAP(p.paciente_prim_nombre) || ' ' || INITCAP(p.paciente_apellido_pat) AS paciente,
                INITCAP(u.usuario_prim_nombre)  || ' ' || INITCAP(u.usuario_apellido_pat)  AS tutor
            FROM pacientes_tutores pt
            JOIN pacientes p ON p.paciente_id = pt.paciente_id
            JOIN usuarios  u ON u.usuario_id  = pt.tutor_id
            ORDER BY pt.pac_tut_id
        """)
    return list(data.PACIENTES_TUTORES)


def existe_relacion(paciente_id: int, tutor_id: int) -> bool:
    if db.using_postgres():
        return bool(db.query_one(
            'SELECT 1 FROM pacientes_tutores WHERE paciente_id = %s AND tutor_id = %s',
            (paciente_id, tutor_id)))
    return any(pt['paciente_id'] == paciente_id and pt['tutor_id'] == tutor_id
               for pt in data.PACIENTES_TUTORES)


def crear_relacion(paciente_id: int, tutor_id: int, pac_nombre: str, tut_nombre: str) -> dict:
    if db.using_postgres():
        row = db.execute_returning(
            'INSERT INTO pacientes_tutores (paciente_id, tutor_id) VALUES (%s, %s) RETURNING *',
            (paciente_id, tutor_id))
        row['paciente'] = pac_nombre
        row['tutor'] = tut_nombre
        return row
    nueva = {
        'pac_tut_id':  data.next_id(data.PACIENTES_TUTORES, 'pac_tut_id'),
        'paciente_id': paciente_id,
        'tutor_id':    tutor_id,
        'paciente':    pac_nombre,
        'tutor':       tut_nombre,
    }
    data.PACIENTES_TUTORES.append(nueva)
    return nueva


def eliminar_relacion(pac_tut_id: int) -> None:
    if db.using_postgres():
        db.execute('DELETE FROM pacientes_tutores WHERE pac_tut_id = %s', (pac_tut_id,))
        return
    data.PACIENTES_TUTORES[:] = [pt for pt in data.PACIENTES_TUTORES
                                  if pt['pac_tut_id'] != pac_tut_id]


# ─────────────────────────────────────────────
# APLICACIONES
# ─────────────────────────────────────────────

def listar_aplicaciones() -> list[dict]:
    if db.using_postgres():
        return db.query("""
            SELECT a.*,
                INITCAP(p.paciente_prim_nombre) || ' ' || INITCAP(p.paciente_apellido_pat) AS paciente,
                INITCAP(u.usuario_prim_nombre)  || ' ' || INITCAP(u.usuario_apellido_pat)  AS responsable,
                cs.centro_nombre,
                v.vacuna_nombre,
                d.dosis_tipo
            FROM aplicaciones a
            JOIN pacientes     p  ON p.paciente_id = a.paciente_id
            JOIN usuarios      u  ON u.usuario_id  = a.usuario_id
            JOIN centros_salud cs ON cs.centro_id  = a.centro_id
            JOIN dosis         d  ON d.dosis_id    = a.dosis_id
            JOIN vacunas       v  ON v.vacuna_id   = d.vacuna_id
            ORDER BY a.aplicacion_timestamp DESC
        """)
    return list(data.APLICACIONES)


def aplicaciones_de_paciente(paciente_id: int) -> list[dict]:
    if db.using_postgres():
        return db.query("""
            SELECT a.*,
                INITCAP(u.usuario_prim_nombre)  || ' ' || INITCAP(u.usuario_apellido_pat)  AS responsable,
                cs.centro_nombre,
                v.vacuna_nombre,
                d.dosis_tipo
            FROM aplicaciones a
            JOIN usuarios      u  ON u.usuario_id  = a.usuario_id
            JOIN centros_salud cs ON cs.centro_id  = a.centro_id
            JOIN dosis         d  ON d.dosis_id    = a.dosis_id
            JOIN vacunas       v  ON v.vacuna_id   = d.vacuna_id
            WHERE a.paciente_id = %s
            ORDER BY a.aplicacion_timestamp
        """, (paciente_id,))
    return [a for a in data.APLICACIONES if a['paciente_id'] == paciente_id]


def dosis_ya_aplicada(paciente_id: int, dosis_id: int) -> bool:
    if db.using_postgres():
        return bool(db.query_one(
            'SELECT 1 FROM aplicaciones WHERE paciente_id = %s AND dosis_id = %s',
            (paciente_id, dosis_id)))
    return any(a['paciente_id'] == paciente_id and a['dosis_id'] == dosis_id
               for a in data.APLICACIONES)


def registrar_aplicacion(datos: dict) -> dict:
    """
    datos: paciente_id, usuario_id, centro_id, lote_id, dosis_id,
           aplicacion_timestamp, aplicacion_observaciones.
    El trigger trg_descontar_inventario descuenta el stock automáticamente.
    """
    if db.using_postgres():
        return db.execute_returning("""
            INSERT INTO aplicaciones
                (paciente_id, usuario_id, centro_id, lote_id, dosis_id,
                 aplicacion_timestamp, aplicacion_observaciones)
            VALUES
                (%(paciente_id)s, %(usuario_id)s, %(centro_id)s, %(lote_id)s, %(dosis_id)s,
                 %(aplicacion_timestamp)s, %(aplicacion_observaciones)s)
            RETURNING *
        """, datos) or {}
    nueva = dict(datos)
    nueva['aplicacion_id'] = data.next_id(data.APLICACIONES, 'aplicacion_id')
    data.APLICACIONES.append(nueva)
    for inv in data.INVENTARIOS:
        if (inv['centro_id'] == datos['centro_id'] and inv['lote_id'] == datos['lote_id']
                and inv.get('inventario_activo_desde') and inv['inventario_stock_actual'] > 0):
            inv['inventario_stock_actual'] -= 1
            break
    return nueva


def historial_vacunacion_paciente(paciente_id: int, esquema_id: int) -> list[dict]:
    """Dosis del esquema del paciente con info de aplicación (LEFT JOIN)."""
    if db.using_postgres():
        return db.query("""
            SELECT d.*,
                v.vacuna_nombre,
                a.aplicacion_timestamp,
                a.aplicacion_observaciones,
                CASE WHEN a.aplicacion_id IS NOT NULL
                     THEN u.usuario_prim_nombre || ' ' || u.usuario_apellido_pat
                     ELSE NULL END AS responsable,
                cs.centro_nombre
            FROM dosis d
            JOIN dosis_esquemas de ON de.dosis_id  = d.dosis_id
            JOIN vacunas         v  ON v.vacuna_id  = d.vacuna_id
            LEFT JOIN aplicaciones   a  ON a.dosis_id = d.dosis_id AND a.paciente_id = %s
            LEFT JOIN usuarios       u  ON u.usuario_id = a.usuario_id
            LEFT JOIN centros_salud cs  ON cs.centro_id = a.centro_id
            WHERE de.esquema_id = %s
            ORDER BY d.vacuna_id, d.dosis_edad_oportuna_dias
        """, (paciente_id, esquema_id))
    ids = {de['dosis_id'] for de in data.DOSIS_ESQUEMAS if de['esquema_id'] == esquema_id}
    rows = []
    for d in sorted([x for x in data.DOSIS if x['dosis_id'] in ids],
                    key=lambda x: (x['vacuna_id'], x['dosis_edad_oportuna_dias'])):
        vac = data.get_by_id(data.VACUNAS, 'vacuna_id', d['vacuna_id'])
        app = next((a for a in data.APLICACIONES
                    if a['paciente_id'] == paciente_id and a['dosis_id'] == d['dosis_id']), None)
        row = dict(d)
        row['vacuna_nombre']            = vac['vacuna_nombre'] if vac else '—'
        row['aplicacion_timestamp']     = app['aplicacion_timestamp'] if app else None
        row['aplicacion_observaciones'] = app.get('aplicacion_observaciones') if app else None
        row['responsable']              = app.get('responsable') if app else None
        row['centro_nombre']            = app.get('centro_nombre') if app else None
        rows.append(row)
    return rows


# ─────────────────────────────────────────────
# INVENTARIO
# ─────────────────────────────────────────────

def listar_inventarios() -> list[dict]:
    if db.using_postgres():
        return db.query("""
            SELECT i.*,
                (i.inventario_activo_desde IS NOT NULL) AS inventario_activo,
                cs.centro_nombre,
                l.lote_codigo, l.lote_fecha_fabricacion, l.lote_fecha_caducidad,
                v.vacuna_nombre, f.fabricante_nombre
            FROM inventarios   i
            JOIN centros_salud cs ON cs.centro_id    = i.centro_id
            JOIN lotes         l  ON l.lote_id       = i.lote_id
            JOIN vacunas       v  ON v.vacuna_id     = l.vacuna_id
            JOIN fabricantes   f  ON f.fabricante_id = l.fabricante_id
            ORDER BY i.inventario_id
        """)
    return list(data.INVENTARIOS)


def inventarios_activos_de_centro(centro_id: int) -> list[dict]:
    if db.using_postgres():
        return db.query("""
            SELECT i.*,
                (i.inventario_activo_desde IS NOT NULL) AS inventario_activo,
                cs.centro_nombre,
                l.lote_codigo, l.lote_fecha_fabricacion, l.lote_fecha_caducidad,
                l.lote_id, l.vacuna_id,
                v.vacuna_nombre, f.fabricante_nombre
            FROM inventarios   i
            JOIN centros_salud cs ON cs.centro_id    = i.centro_id
            JOIN lotes         l  ON l.lote_id       = i.lote_id
            JOIN vacunas       v  ON v.vacuna_id     = l.vacuna_id
            JOIN fabricantes   f  ON f.fabricante_id = l.fabricante_id
            WHERE i.centro_id = %s
              AND i.inventario_activo_desde IS NOT NULL
              AND i.inventario_stock_actual > 0
            ORDER BY v.vacuna_nombre
        """, (centro_id,))
    return [i for i in data.INVENTARIOS
            if i['centro_id'] == centro_id
            and i.get('inventario_activo_desde') is not None
            and i['inventario_stock_actual'] > 0]


def obtener_inventario(inventario_id: int) -> dict | None:
    if db.using_postgres():
        return db.query_one("""
            SELECT i.*,
                (i.inventario_activo_desde IS NOT NULL) AS inventario_activo,
                cs.centro_nombre,
                l.lote_codigo, l.lote_id, l.vacuna_id,
                v.vacuna_nombre, f.fabricante_nombre
            FROM inventarios   i
            JOIN centros_salud cs ON cs.centro_id    = i.centro_id
            JOIN lotes         l  ON l.lote_id       = i.lote_id
            JOIN vacunas       v  ON v.vacuna_id     = l.vacuna_id
            JOIN fabricantes   f  ON f.fabricante_id = l.fabricante_id
            WHERE i.inventario_id = %s
        """, (inventario_id,))
    return data.get_by_id(data.INVENTARIOS, 'inventario_id', inventario_id)


def asignar_inventario(datos: dict) -> dict:
    """
    datos: centro_id, lote_id, inventario_stock_inicial, inventario_stock_actual,
    inventario_activo_desde (None = pendiente de activación por responsable).
    """
    if db.using_postgres():
        return db.execute_returning("""
            INSERT INTO inventarios
                (centro_id, lote_id, inventario_stock_inicial, inventario_stock_actual,
                 inventario_activo_desde)
            VALUES
                (%(centro_id)s, %(lote_id)s, %(inventario_stock_inicial)s,
                 %(inventario_stock_actual)s, %(inventario_activo_desde)s)
            RETURNING *
        """, datos)
    nuevo = dict(datos)
    nuevo['inventario_id'] = data.next_id(data.INVENTARIOS, 'inventario_id')
    nuevo.setdefault('inventario_activo_desde', None)
    data.INVENTARIOS.append(nuevo)
    return nuevo


def centros_con_vacuna_disponible(vacuna_id: int) -> list[dict]:
    if db.using_postgres():
        return db.query("""
            SELECT cs.*, ci.ciudad_nombre,
                SUM(i.inventario_stock_actual) AS stock_total
            FROM centros_salud cs
            JOIN inventarios i  ON i.centro_id  = cs.centro_id
            JOIN lotes       l  ON l.lote_id    = i.lote_id
            JOIN ciudades    ci ON ci.ciudad_id  = cs.ciudad_id
            WHERE l.vacuna_id = %s
              AND i.inventario_activo_desde IS NOT NULL
              AND i.inventario_stock_actual > 0
            GROUP BY cs.centro_id, ci.ciudad_nombre
            ORDER BY cs.centro_nombre
        """, (vacuna_id,))
    result = []
    for inv in data.INVENTARIOS:
        lote = data.get_by_id(data.LOTES, 'lote_id', inv['lote_id'])
        if (lote and lote['vacuna_id'] == vacuna_id
                and inv.get('inventario_activo_desde') is not None
                and inv['inventario_stock_actual'] > 0):
            centro = data.get_by_id(data.CENTROS, 'centro_id', inv['centro_id'])
            if centro:
                result.append({**centro, 'stock_total': inv['inventario_stock_actual']})
    return result


# ─────────────────────────────────────────────
# LOTES
# ─────────────────────────────────────────────

def listar_lotes() -> list[dict]:
    if db.using_postgres():
        return db.query("""
            SELECT l.*, v.vacuna_nombre, f.fabricante_nombre,
                p.proveedor_prim_nombre || ' ' || p.proveedor_apellido_pat AS proveedor_nombre
            FROM lotes       l
            JOIN vacunas     v ON v.vacuna_id    = l.vacuna_id
            JOIN fabricantes f ON f.fabricante_id = l.fabricante_id
            JOIN proveedores p ON p.proveedor_id  = l.proveedor_id
            ORDER BY l.lote_id
        """)
    return list(data.LOTES)


def obtener_lote(lote_id: int) -> dict | None:
    if db.using_postgres():
        return db.query_one("""
            SELECT l.*, v.vacuna_nombre, f.fabricante_nombre,
                p.proveedor_prim_nombre || ' ' || p.proveedor_apellido_pat AS proveedor_nombre
            FROM lotes       l
            JOIN vacunas     v ON v.vacuna_id    = l.vacuna_id
            JOIN fabricantes f ON f.fabricante_id = l.fabricante_id
            JOIN proveedores p ON p.proveedor_id  = l.proveedor_id
            WHERE l.lote_id = %s
        """, (lote_id,))
    return data.get_by_id(data.LOTES, 'lote_id', lote_id)


def crear_lote(datos: dict) -> dict:
    """datos: lote_codigo, lote_fecha_fabricacion, lote_fecha_caducidad,
    fabricante_id, vacuna_id, lote_cant_inicial, proveedor_id."""
    if db.using_postgres():
        return db.execute_returning("""
            INSERT INTO lotes
                (lote_codigo, lote_fecha_fabricacion, lote_fecha_caducidad,
                 fabricante_id, vacuna_id, lote_cant_inicial, proveedor_id)
            VALUES
                (%(lote_codigo)s, %(lote_fecha_fabricacion)s, %(lote_fecha_caducidad)s,
                 %(fabricante_id)s, %(vacuna_id)s, %(lote_cant_inicial)s, %(proveedor_id)s)
            RETURNING *
        """, datos)
    nuevo = dict(datos)
    nuevo['lote_id'] = data.next_id(data.LOTES, 'lote_id')
    data.LOTES.append(nuevo)
    return nuevo


# ─────────────────────────────────────────────
# PROVEEDORES
# ─────────────────────────────────────────────

def listar_proveedores() -> list[dict]:
    if db.using_postgres():
        return db.query("""
            SELECT p.*, f.fabricante_nombre
            FROM proveedores p
            JOIN fabricantes f ON f.fabricante_id = p.fabricante_id
            ORDER BY p.proveedor_apellido_pat, p.proveedor_prim_nombre
        """)
    return list(data.PROVEEDORES)


def obtener_proveedor(proveedor_id: int) -> dict | None:
    if db.using_postgres():
        return db.query_one("""
            SELECT p.*, f.fabricante_nombre
            FROM proveedores p
            JOIN fabricantes f ON f.fabricante_id = p.fabricante_id
            WHERE p.proveedor_id = %s
        """, (proveedor_id,))
    return data.get_by_id(data.PROVEEDORES, 'proveedor_id', proveedor_id)


def crear_proveedor(datos: dict) -> dict:
    """datos: proveedor_prim_nombre, proveedor_apellido_pat, proveedor_email,
    proveedor_telefono, proveedor_empresa, fabricante_id."""
    if db.using_postgres():
        return db.execute_returning("""
            INSERT INTO proveedores
                (proveedor_prim_nombre, proveedor_seg_nombre, proveedor_apellido_pat,
                 proveedor_apellido_mat, proveedor_email, proveedor_telefono,
                 proveedor_empresa, fabricante_id)
            VALUES
                (%(proveedor_prim_nombre)s, %(proveedor_seg_nombre)s, %(proveedor_apellido_pat)s,
                 %(proveedor_apellido_mat)s, %(proveedor_email)s, %(proveedor_telefono)s,
                 %(proveedor_empresa)s, %(fabricante_id)s)
            RETURNING *
        """, datos)
    nuevo = dict(datos)
    nuevo['proveedor_id'] = data.next_id(data.PROVEEDORES, 'proveedor_id')
    data.PROVEEDORES.append(nuevo)
    return nuevo


# ─────────────────────────────────────────────
# CATÁLOGOS CLÍNICOS
# ─────────────────────────────────────────────

def listar_vacunas() -> list[dict]:
    if db.using_postgres():
        return db.query('SELECT * FROM vacunas ORDER BY vacuna_nombre')
    return list(data.VACUNAS)


def obtener_vacuna(vacuna_id: int) -> dict | None:
    if db.using_postgres():
        return db.query_one('SELECT * FROM vacunas WHERE vacuna_id = %s', (vacuna_id,))
    return data.get_by_id(data.VACUNAS, 'vacuna_id', vacuna_id)


def crear_vacuna(datos: dict) -> dict:
    if db.using_postgres():
        return db.execute_returning(
            'INSERT INTO vacunas (vacuna_nombre) VALUES (%(vacuna_nombre)s) RETURNING *', datos)
    nuevo = dict(datos)
    nuevo['vacuna_id'] = data.next_id(data.VACUNAS, 'vacuna_id')
    nuevo.setdefault('vacuna_activa', True)
    data.VACUNAS.append(nuevo)
    return nuevo


def listar_dosis(vacuna_id: int | None = None) -> list[dict]:
    if db.using_postgres():
        if vacuna_id:
            return db.query("""
                SELECT d.*, v.vacuna_nombre FROM dosis d
                JOIN vacunas v ON v.vacuna_id = d.vacuna_id
                WHERE d.vacuna_id = %s
                ORDER BY d.dosis_edad_oportuna_dias
            """, (vacuna_id,))
        return db.query("""
            SELECT d.*, v.vacuna_nombre FROM dosis d
            JOIN vacunas v ON v.vacuna_id = d.vacuna_id
            ORDER BY d.vacuna_id, d.dosis_edad_oportuna_dias
        """)
    if vacuna_id:
        return [d for d in data.DOSIS if d['vacuna_id'] == vacuna_id]
    return list(data.DOSIS)


def obtener_dosis(dosis_id: int) -> dict | None:
    if db.using_postgres():
        return db.query_one('SELECT * FROM dosis WHERE dosis_id = %s', (dosis_id,))
    return data.get_by_id(data.DOSIS, 'dosis_id', dosis_id)


def crear_dosis(datos: dict) -> dict:
    if db.using_postgres():
        return db.execute_returning("""
            INSERT INTO dosis
                (vacuna_id, dosis_tipo, dosis_cant_ml, dosis_area_aplicacion,
                 dosis_edad_oportuna_dias, dosis_intervalo_min_dias, dosis_limite_edad_dias)
            VALUES
                (%(vacuna_id)s, %(dosis_tipo)s, %(dosis_cant_ml)s, %(dosis_area_aplicacion)s,
                 %(dosis_edad_oportuna_dias)s, %(dosis_intervalo_min_dias)s,
                 %(dosis_limite_edad_dias)s)
            RETURNING *
        """, datos)
    nuevo = dict(datos)
    nuevo['dosis_id'] = data.next_id(data.DOSIS, 'dosis_id')
    data.DOSIS.append(nuevo)
    return nuevo


def listar_esquemas() -> list[dict]:
    if db.using_postgres():
        return db.query('SELECT * FROM esquemas ORDER BY esquema_nombre')
    return list(data.ESQUEMAS)


def obtener_esquema(esquema_id: int) -> dict | None:
    if db.using_postgres():
        return db.query_one('SELECT * FROM esquemas WHERE esquema_id = %s', (esquema_id,))
    return data.get_by_id(data.ESQUEMAS, 'esquema_id', esquema_id)


def crear_esquema(datos: dict) -> dict:
    if db.using_postgres():
        return db.execute_returning("""
            INSERT INTO esquemas (esquema_nombre, esquema_fecha_vigencia, esquema_vigente_desde)
            VALUES (%(esquema_nombre)s, %(esquema_fecha_vigencia)s, %(esquema_vigente_desde)s)
            RETURNING *
        """, datos)
    nuevo = dict(datos)
    nuevo['esquema_id'] = data.next_id(data.ESQUEMAS, 'esquema_id')
    nuevo.setdefault('total_dosis', 0)
    data.ESQUEMAS.append(nuevo)
    return nuevo


def eliminar_esquema(esquema_id: int) -> bool:
    if db.using_postgres():
        if db.query_one('SELECT 1 FROM pacientes WHERE esquema_id = %s', (esquema_id,)):
            return False
        db.execute('DELETE FROM esquemas WHERE esquema_id = %s', (esquema_id,))
        return True
    if any(p['esquema_id'] == esquema_id for p in data.PACIENTES):
        return False
    data.ESQUEMAS[:] = [e for e in data.ESQUEMAS if e['esquema_id'] != esquema_id]
    data.DOSIS_ESQUEMAS[:] = [de for de in data.DOSIS_ESQUEMAS if de['esquema_id'] != esquema_id]
    return True


def dosis_de_esquema(esquema_id: int) -> list[dict]:
    if db.using_postgres():
        return db.query("""
            SELECT d.*, v.vacuna_nombre
            FROM dosis d
            JOIN dosis_esquemas de ON de.dosis_id = d.dosis_id
            JOIN vacunas        v  ON v.vacuna_id  = d.vacuna_id
            WHERE de.esquema_id = %s
            ORDER BY d.vacuna_id, d.dosis_edad_oportuna_dias
        """, (esquema_id,))
    ids = {de['dosis_id'] for de in data.DOSIS_ESQUEMAS if de['esquema_id'] == esquema_id}
    return [d for d in data.DOSIS if d['dosis_id'] in ids]


def listar_dosis_esquemas() -> list[dict]:
    if db.using_postgres():
        return db.query('SELECT * FROM dosis_esquemas ORDER BY esquema_id, dosis_id')
    return list(data.DOSIS_ESQUEMAS)


def agregar_dosis_a_esquema(esquema_id: int, dosis_id: int) -> dict:
    if db.using_postgres():
        return db.execute_returning("""
            INSERT INTO dosis_esquemas (esquema_id, dosis_id) VALUES (%s, %s)
            ON CONFLICT DO NOTHING RETURNING *
        """, (esquema_id, dosis_id)) or {}
    nueva = {
        'dosis_esq_id': data.next_id(data.DOSIS_ESQUEMAS, 'dosis_esq_id'),
        'esquema_id':   esquema_id,
        'dosis_id':     dosis_id,
    }
    data.DOSIS_ESQUEMAS.append(nueva)
    return nueva


# ─────────────────────────────────────────────
# PADECIMIENTOS
# ─────────────────────────────────────────────

def listar_padecimientos() -> list[dict]:
    if db.using_postgres():
        rows = db.query('SELECT * FROM padecimientos ORDER BY padecimiento_nombre')
        for r in rows:
            vacs = db.query("""
                SELECT v.vacuna_nombre FROM vacunas_padecimientos vp
                JOIN vacunas v ON v.vacuna_id = vp.vacuna_id
                WHERE vp.padecimiento_id = %s ORDER BY v.vacuna_nombre
            """, (r['padecimiento_id'],))
            r['vacunas'] = ', '.join(v['vacuna_nombre'] for v in vacs) if vacs else None
        return rows
    return list(data.PADECIMIENTOS)


def crear_padecimiento(datos: dict) -> dict:
    if db.using_postgres():
        return db.execute_returning("""
            INSERT INTO padecimientos (padecimiento_nombre, padecimiento_descripcion)
            VALUES (%(padecimiento_nombre)s, %(padecimiento_descripcion)s) RETURNING *
        """, datos)
    nuevo = dict(datos)
    nuevo['padecimiento_id'] = data.next_id(data.PADECIMIENTOS, 'padecimiento_id')
    nuevo.setdefault('padecimiento_activo', True)
    data.PADECIMIENTOS.append(nuevo)
    return nuevo


# ─────────────────────────────────────────────
# FABRICANTES
# ─────────────────────────────────────────────

def listar_fabricantes() -> list[dict]:
    if db.using_postgres():
        return db.query("""
            SELECT f.*, p.pais_nombre FROM fabricantes f
            JOIN paises p ON p.pais_id = f.pais_id
            ORDER BY f.fabricante_nombre
        """)
    return list(data.FABRICANTES)


def obtener_fabricante(fabricante_id: int) -> dict | None:
    if db.using_postgres():
        return db.query_one("""
            SELECT f.*, p.pais_nombre FROM fabricantes f
            JOIN paises p ON p.pais_id = f.pais_id
            WHERE f.fabricante_id = %s
        """, (fabricante_id,))
    return data.get_by_id(data.FABRICANTES, 'fabricante_id', fabricante_id)


def crear_fabricante(datos: dict) -> dict:
    if db.using_postgres():
        return db.execute_returning("""
            INSERT INTO fabricantes (fabricante_nombre, pais_id, fabricante_telefono)
            VALUES (%(fabricante_nombre)s, %(pais_id)s, %(fabricante_telefono)s) RETURNING *
        """, datos)
    nuevo = dict(datos)
    nuevo['fabricante_id'] = data.next_id(data.FABRICANTES, 'fabricante_id')
    data.FABRICANTES.append(nuevo)
    return nuevo


# ─────────────────────────────────────────────
# CENTROS DE SALUD
# ─────────────────────────────────────────────

def listar_centros() -> list[dict]:
    if db.using_postgres():
        return db.query("""
            SELECT cs.*, ci.ciudad_nombre
            FROM centros_salud cs
            JOIN ciudades ci ON ci.ciudad_id = cs.ciudad_id
            ORDER BY cs.centro_nombre
        """)
    return list(data.CENTROS)


def obtener_centro(centro_id: int) -> dict | None:
    if db.using_postgres():
        return db.query_one("""
            SELECT cs.*, ci.ciudad_nombre
            FROM centros_salud cs
            JOIN ciudades ci ON ci.ciudad_id = cs.ciudad_id
            WHERE cs.centro_id = %s
        """, (centro_id,))
    return data.get_by_id(data.CENTROS, 'centro_id', centro_id)


def crear_centro(datos: dict) -> dict:
    if db.using_postgres():
        return db.execute_returning("""
            INSERT INTO centros_salud
                (centro_nombre, centro_calle, centro_numero, centro_codigo_postal,
                 ciudad_id, centro_horario_inicio, centro_horario_fin,
                 centro_latitud, centro_longitud, centro_telefono, centro_beacon)
            VALUES
                (%(centro_nombre)s, %(centro_calle)s, %(centro_numero)s, %(centro_codigo_postal)s,
                 %(ciudad_id)s, %(centro_horario_inicio)s, %(centro_horario_fin)s,
                 %(centro_latitud)s, %(centro_longitud)s, %(centro_telefono)s, %(centro_beacon)s)
            RETURNING *
        """, datos)
    nuevo = dict(datos)
    nuevo['centro_id'] = data.next_id(data.CENTROS, 'centro_id')
    data.CENTROS.append(nuevo)
    return nuevo


def eliminar_centro(centro_id: int) -> bool:
    if db.using_postgres():
        if (db.query_one('SELECT 1 FROM usuarios WHERE centro_id = %s', (centro_id,)) or
                db.query_one('SELECT 1 FROM inventarios WHERE centro_id = %s', (centro_id,))):
            return False
        db.execute('DELETE FROM centros_salud WHERE centro_id = %s', (centro_id,))
        return True
    if (any(u.get('centro_id') == centro_id for u in data.USUARIOS) or
            any(i['centro_id'] == centro_id for i in data.INVENTARIOS)):
        return False
    data.CENTROS[:] = [c for c in data.CENTROS if c['centro_id'] != centro_id]
    return True


# ─────────────────────────────────────────────
# GEOGRAFÍA
# ─────────────────────────────────────────────

def listar_paises() -> list[dict]:
    if db.using_postgres():
        return db.query('SELECT * FROM paises ORDER BY pais_nombre')
    return list(data.PAISES)


def obtener_pais(pais_id: int) -> dict | None:
    if db.using_postgres():
        return db.query_one('SELECT * FROM paises WHERE pais_id = %s', (pais_id,))
    return data.get_by_id(data.PAISES, 'pais_id', pais_id)


def crear_pais(nombre: str) -> dict:
    if db.using_postgres():
        return db.execute_returning(
            'INSERT INTO paises (pais_nombre) VALUES (%s) RETURNING *', (nombre,))
    nueva = {'pais_id': data.next_id(data.PAISES, 'pais_id'), 'pais_nombre': nombre}
    data.PAISES.append(nueva)
    return nueva


def listar_estados(pais_id: int | None = None) -> list[dict]:
    if db.using_postgres():
        if pais_id:
            return db.query("""
                SELECT e.*, p.pais_nombre FROM estados e
                JOIN paises p ON p.pais_id = e.pais_id
                WHERE e.pais_id = %s ORDER BY e.estado_nombre
            """, (pais_id,))
        return db.query("""
            SELECT e.*, p.pais_nombre FROM estados e
            JOIN paises p ON p.pais_id = e.pais_id
            ORDER BY e.estado_nombre
        """)
    if pais_id:
        return [e for e in data.ESTADOS if e['pais_id'] == pais_id]
    return list(data.ESTADOS)


def obtener_estado(estado_id: int) -> dict | None:
    if db.using_postgres():
        return db.query_one("""
            SELECT e.*, p.pais_nombre FROM estados e
            JOIN paises p ON p.pais_id = e.pais_id
            WHERE e.estado_id = %s
        """, (estado_id,))
    return data.get_by_id(data.ESTADOS, 'estado_id', estado_id)


def crear_estado(datos: dict) -> dict:
    if db.using_postgres():
        return db.execute_returning(
            'INSERT INTO estados (estado_nombre, pais_id) '
            'VALUES (%(estado_nombre)s, %(pais_id)s) RETURNING *', datos)
    nuevo = dict(datos)
    nuevo['estado_id'] = data.next_id(data.ESTADOS, 'estado_id')
    data.ESTADOS.append(nuevo)
    return nuevo


def listar_ciudades(estado_id: int | None = None) -> list[dict]:
    if db.using_postgres():
        if estado_id:
            return db.query("""
                SELECT c.*, e.estado_nombre FROM ciudades c
                JOIN estados e ON e.estado_id = c.estado_id
                WHERE c.estado_id = %s ORDER BY c.ciudad_nombre
            """, (estado_id,))
        return db.query("""
            SELECT c.*, e.estado_nombre FROM ciudades c
            JOIN estados e ON e.estado_id = c.estado_id
            ORDER BY c.ciudad_nombre
        """)
    if estado_id:
        return [c for c in data.CIUDADES if c['estado_id'] == estado_id]
    return list(data.CIUDADES)


def obtener_ciudad(ciudad_id: int) -> dict | None:
    if db.using_postgres():
        return db.query_one("""
            SELECT c.*, e.estado_nombre FROM ciudades c
            JOIN estados e ON e.estado_id = c.estado_id
            WHERE c.ciudad_id = %s
        """, (ciudad_id,))
    return data.get_by_id(data.CIUDADES, 'ciudad_id', ciudad_id)


def crear_ciudad(datos: dict) -> dict:
    if db.using_postgres():
        return db.execute_returning(
            'INSERT INTO ciudades (ciudad_nombre, estado_id) '
            'VALUES (%(ciudad_nombre)s, %(estado_id)s) RETURNING *', datos)
    nuevo = dict(datos)
    nuevo['ciudad_id'] = data.next_id(data.CIUDADES, 'ciudad_id')
    data.CIUDADES.append(nuevo)
    return nuevo


# ─────────────────────────────────────────────
# ALERTAS
# ─────────────────────────────────────────────

def listar_alertas_inventario() -> list[dict]:
    if db.using_postgres():
        return db.query("""
            SELECT ai.*, i.inventario_stock_actual,
                cs.centro_nombre, v.vacuna_nombre,
                ai.alerta_inv_timestamp AS ts
            FROM alertas_inventario ai
            JOIN inventarios   i  ON i.inventario_id = ai.inventario_id
            JOIN centros_salud cs ON cs.centro_id     = i.centro_id
            JOIN lotes         l  ON l.lote_id        = i.lote_id
            JOIN vacunas       v  ON v.vacuna_id      = l.vacuna_id
            ORDER BY ai.alerta_inv_timestamp DESC
        """)
    return list(data.ALERTAS_INVENTARIO)


def listar_alertas_dosis() -> list[dict]:
    if db.using_postgres():
        return db.query("""
            SELECT ad.*,
                INITCAP(p.paciente_prim_nombre) || ' ' || INITCAP(p.paciente_apellido_pat) AS paciente,
                v.vacuna_nombre,
                d.dosis_tipo
            FROM alertas_dosis_pacientes ad
            JOIN pacientes p ON p.paciente_id = ad.paciente_id
            JOIN dosis d ON d.dosis_id = ad.dosis_id
            JOIN vacunas v ON v.vacuna_id = d.vacuna_id
            ORDER BY ad.alerta_dosis_pac_timestamp DESC
        """)
    return list(data.ALERTAS_DOSIS)


# ─────────────────────────────────────────────
# DASHBOARD STATS
# ─────────────────────────────────────────────

def stats_dashboard() -> dict:
    if db.using_postgres():
        row = db.query_one("""
            SELECT
                (SELECT COUNT(*) FROM pacientes) AS pacientes,
                (SELECT COUNT(DISTINCT u.usuario_id) FROM usuarios u
                 JOIN usuarios_roles ur ON ur.usuario_id = u.usuario_id
                 JOIN roles r ON r.rol_id = ur.rol_id AND r.rol_nombre = 'tutor') AS tutores,
                (SELECT COUNT(DISTINCT u.usuario_id) FROM usuarios u
                 JOIN usuarios_roles ur ON ur.usuario_id = u.usuario_id
                 JOIN roles r ON r.rol_id = ur.rol_id AND r.rol_nombre = 'responsable') AS responsables,
                (SELECT COUNT(*) FROM centros_salud) AS centros,
                (SELECT COUNT(*) FROM aplicaciones
                 WHERE DATE(aplicacion_timestamp) = CURRENT_DATE) AS aplicaciones_hoy,
                (SELECT COUNT(*) FROM alertas_inventario)      AS alertas_inv,
                (SELECT COUNT(*) FROM alertas_dosis_pacientes) AS alertas_dosis
        """)
        return row or {}
    from datetime import date
    return {
        'pacientes':        len(data.PACIENTES),
        'tutores':          sum(1 for u in data.USUARIOS
                                if 'tutor' in _roles_de_usuario_mem(u['usuario_id'])),
        'responsables':     sum(1 for u in data.USUARIOS
                                if 'responsable' in _roles_de_usuario_mem(u['usuario_id'])),
        'centros':          len(data.CENTROS),
        'aplicaciones_hoy': sum(1 for a in data.APLICACIONES
                                if a['aplicacion_timestamp'].date() == date.today()),
        'alertas_inv':   len(data.ALERTAS_INVENTARIO),
        'alertas_dosis': len(data.ALERTAS_DOSIS),
    }


# ─────────────────────────────────────────────
# GRÁFICAS Y REPORTES
# ─────────────────────────────────────────────

def chart_aplicaciones_por_mes(meses: int = 12) -> list[dict]:
    """Últimos N meses, agrupados, para la gráfica del dashboard."""
    if db.using_postgres():
        return db.query("""
            SELECT TO_CHAR(DATE_TRUNC('month', aplicacion_timestamp), 'Mon YYYY') AS mes,
                   DATE_TRUNC('month', aplicacion_timestamp) AS mes_orden,
                   COUNT(*) AS total
            FROM aplicaciones
            WHERE aplicacion_timestamp >= DATE_TRUNC('month', NOW() - (%(m)s || ' months')::interval)
            GROUP BY DATE_TRUNC('month', aplicacion_timestamp)
            ORDER BY DATE_TRUNC('month', aplicacion_timestamp)
        """, {'m': meses - 1})
    from collections import defaultdict
    from datetime import date
    por_mes = defaultdict(int)
    for a in data.APLICACIONES:
        ts = a['aplicacion_timestamp']
        mes = ts.strftime('%b %Y') if hasattr(ts, 'strftime') else str(ts)[:7]
        por_mes[mes] += 1
    return [{'mes': k, 'total': v} for k, v in por_mes.items()]


def chart_por_mes(desde: str, hasta: str,
                  centro_id: int | None = None,
                  vacuna_id: int | None = None) -> list[dict]:
    """Aplicaciones agrupadas por mes con filtros opcionales."""
    if db.using_postgres():
        sql = """
            SELECT TO_CHAR(DATE_TRUNC('month', a.aplicacion_timestamp), 'Mon YYYY') AS mes,
                   DATE_TRUNC('month', a.aplicacion_timestamp) AS mes_orden,
                   COUNT(*) AS total
            FROM aplicaciones a
            JOIN dosis  d ON d.dosis_id  = a.dosis_id
            JOIN vacunas v ON v.vacuna_id = d.vacuna_id
            WHERE a.aplicacion_timestamp BETWEEN %(desde)s AND %(hasta)s
        """
        params: dict = {'desde': desde, 'hasta': hasta + ' 23:59:59'}
        if centro_id:
            sql += ' AND a.centro_id = %(centro_id)s'
            params['centro_id'] = centro_id
        if vacuna_id:
            sql += ' AND d.vacuna_id = %(vacuna_id)s'
            params['vacuna_id'] = vacuna_id
        sql += ' GROUP BY DATE_TRUNC(\'month\', a.aplicacion_timestamp) ORDER BY mes_orden'
        return db.query(sql, params)
    from collections import defaultdict
    apps = data.APLICACIONES
    if centro_id:
        apps = [a for a in apps if a.get('centro_id') == centro_id]
    por_mes: dict = defaultdict(int)
    for a in apps:
        ts = a['aplicacion_timestamp']
        mes = ts.strftime('%b %Y') if hasattr(ts, 'strftime') else str(ts)[:7]
        por_mes[mes] += 1
    return [{'mes': k, 'total': v} for k, v in por_mes.items()]


def chart_top_vacunas(desde: str, hasta: str,
                      centro_id: int | None = None,
                      vacuna_id: int | None = None) -> list[dict]:
    """Top vacunas más aplicadas en el periodo."""
    if db.using_postgres():
        sql = """
            SELECT v.vacuna_nombre, COUNT(*) AS total
            FROM aplicaciones a
            JOIN dosis   d ON d.dosis_id  = a.dosis_id
            JOIN vacunas v ON v.vacuna_id = d.vacuna_id
            WHERE a.aplicacion_timestamp BETWEEN %(desde)s AND %(hasta)s
        """
        params: dict = {'desde': desde, 'hasta': hasta + ' 23:59:59'}
        if centro_id:
            sql += ' AND a.centro_id = %(centro_id)s'
            params['centro_id'] = centro_id
        if vacuna_id:
            sql += ' AND d.vacuna_id = %(vacuna_id)s'
            params['vacuna_id'] = vacuna_id
        sql += ' GROUP BY v.vacuna_nombre ORDER BY total DESC LIMIT 8'
        return db.query(sql, params)
    from collections import defaultdict
    cnt: dict = defaultdict(int)
    for a in data.APLICACIONES:
        cnt[a.get('vacuna_nombre', '—')] += 1
    return [{'vacuna_nombre': k, 'total': v}
            for k, v in sorted(cnt.items(), key=lambda x: -x[1])[:8]]


def resumen_periodo(desde: str, hasta: str,
                    centro_id: int | None = None,
                    vacuna_id: int | None = None) -> dict:
    """Total de aplicaciones en el periodo para el resumen."""
    if db.using_postgres():
        sql = """
            SELECT COUNT(*) AS total
            FROM aplicaciones a
            JOIN dosis d ON d.dosis_id = a.dosis_id
            WHERE a.aplicacion_timestamp BETWEEN %(desde)s AND %(hasta)s
        """
        params: dict = {'desde': desde, 'hasta': hasta + ' 23:59:59'}
        if centro_id:
            sql += ' AND a.centro_id = %(centro_id)s'
            params['centro_id'] = centro_id
        if vacuna_id:
            sql += ' AND d.vacuna_id = %(vacuna_id)s'
            params['vacuna_id'] = vacuna_id
        row = db.query_one(sql, params)
        return {'total': row['total'] if row else 0}
    return {'total': len(data.APLICACIONES)}


# ── Fotos de perfil ──────────────────────────────────────────────

def actualizar_imagen_usuario(usuario_id: int, ruta: str):
    if db.using_postgres():
        db.execute('UPDATE usuarios SET usuario_imagen = %s WHERE usuario_id = %s',
                   (ruta, usuario_id))
    else:
        u = data.get_by_id(data.USUARIOS, 'usuario_id', usuario_id)
        if u:
            u['usuario_imagen'] = ruta


def actualizar_imagen_paciente(paciente_id: int, ruta: str):
    if db.using_postgres():
        db.execute('UPDATE pacientes SET paciente_imagen = %s WHERE paciente_id = %s',
                   (ruta, paciente_id))
    else:
        p = data.get_by_id(data.PACIENTES, 'paciente_id', paciente_id)
        if p:
            p['paciente_imagen'] = ruta

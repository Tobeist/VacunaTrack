from __future__ import annotations
# repository.py — Capa de acceso a datos de VacunaTrack (esquema v3)
#
# Todas las consultas SELECT usan SPs de lectura (REFCURSOR) o VIEWs.
# Las operaciones de escritura usan SPs con parámetros OUT (p_ok/p_msg/p_id).
# NINGUNA consulta SQL está embebida directamente en este archivo.

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
        return db.call_read_sp_one('sp_buscar_usuario_por_email', [email])
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
        _sp('sp_cambiar_password', [user_id, nuevo_hash], out_count=2)
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
# HELPER interno: llamada a stored procedures de escritura
# ─────────────────────────────────────────────

def _sp(name: str, params: list, out_count: int = 3) -> dict:
    """Llama al SP indicado y lanza ValueError si p_ok == 0."""
    result = db.call_write_sp(name, params, out_count)
    if not result.get('p_ok'):
        raise ValueError(result.get('p_msg', 'Error desconocido'))
    return result


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
        return db.call_read_sp('sp_listar_administradores')
    return [data._usuario_como_rol(u, 'admin') for u in data.USUARIOS
            if 'admin' in _roles_de_usuario_mem(u['usuario_id'])]


def obtener_administrador(admin_id: int) -> dict | None:
    if db.using_postgres():
        return db.call_read_sp_one('sp_obtener_administrador', [admin_id])
    u = data.get_by_id(data.USUARIOS, 'usuario_id', admin_id)
    return data._usuario_como_rol(u, 'admin') if u else None


def crear_admin(datos: dict) -> dict:
    """datos usa claves admin_* (formulario) + admin_contrasena."""
    if db.using_postgres():
        r = _sp('sp_crear_admin', [
            datos.get('admin_prim_nombre'), datos.get('admin_seg_nombre'),
            datos.get('admin_apellido_pat'), datos.get('admin_apellido_mat'),
            datos.get('admin_telefono'), datos.get('admin_curp'),
            datos.get('admin_rfc'), datos.get('admin_email'),
            datos.get('admin_contrasena'),
        ])
        return obtener_administrador(r['p_id']) or {}
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


def eliminar_admin(admin_id: int, session_id: int = 0) -> None:
    if db.using_postgres():
        _sp('sp_eliminar_admin', [admin_id, session_id], out_count=2)
        return
    data.USUARIOS[:] = [u for u in data.USUARIOS if u['usuario_id'] != admin_id]
    data.LOGIN[:] = [lg for lg in data.LOGIN if lg['usuario_id'] != admin_id]
    data.USUARIOS_ROLES[:] = [ur for ur in data.USUARIOS_ROLES if ur['usuario_id'] != admin_id]


# ─────────────────────────────────────────────
# PACIENTES
# ─────────────────────────────────────────────

def listar_pacientes() -> list[dict]:
    if db.using_postgres():
        return db.call_read_sp('sp_listar_pacientes')
    return list(data.PACIENTES)


def obtener_paciente(paciente_id: int) -> dict | None:
    if db.using_postgres():
        return db.call_read_sp_one('sp_obtener_paciente', [paciente_id])
    return data.get_by_id(data.PACIENTES, 'paciente_id', paciente_id)


def obtener_paciente_por_nfc(nfc_uid: str) -> dict | None:
    if db.using_postgres():
        return db.call_read_sp_one('sp_obtener_paciente_por_nfc', [nfc_uid])
    return next((p for p in data.PACIENTES if p.get('paciente_nfc') == nfc_uid), None)


def obtener_paciente_por_curp(curp: str) -> dict | None:
    if db.using_postgres():
        return db.call_read_sp_one('sp_obtener_paciente_por_curp', [curp.upper()])
    return next((p for p in data.PACIENTES if p.get('paciente_curp') == curp.upper()), None)


def obtener_paciente_por_cert_nac(cert_nac: str) -> dict | None:
    if db.using_postgres():
        return db.call_read_sp_one('sp_obtener_paciente_por_cert_nac', [cert_nac.strip()])
    return next((p for p in data.PACIENTES if p.get('paciente_num_cert_nac') == cert_nac.strip()), None)


def crear_paciente(datos: dict) -> dict:
    if db.using_postgres():
        r = _sp('sp_crear_paciente', [
            datos.get('paciente_prim_nombre'), datos.get('paciente_seg_nombre'),
            datos.get('paciente_apellido_pat'), datos.get('paciente_apellido_mat'),
            datos.get('paciente_curp'), datos.get('paciente_num_cert_nac'),
            datos.get('paciente_fecha_nac'), datos.get('paciente_sexo'),
            datos.get('paciente_nfc'), datos.get('esquema_id'),
        ])
        return obtener_paciente(r['p_id']) or {}
    nuevo = dict(datos)
    nuevo['paciente_id'] = data.next_id(data.PACIENTES, 'paciente_id')
    data.PACIENTES.append(nuevo)
    return nuevo


def eliminar_paciente(paciente_id: int) -> None:
    if db.using_postgres():
        _sp('sp_eliminar_paciente', [paciente_id], out_count=2)
        return
    if any(a['paciente_id'] == paciente_id for a in data.APLICACIONES):
        raise ValueError('No se puede eliminar: el paciente tiene aplicaciones registradas')
    data.PACIENTES[:] = [p for p in data.PACIENTES if p['paciente_id'] != paciente_id]
    data.PACIENTES_TUTORES[:] = [pt for pt in data.PACIENTES_TUTORES
                                  if pt['paciente_id'] != paciente_id]


# ─────────────────────────────────────────────
# TUTORES
# ─────────────────────────────────────────────

def listar_tutores() -> list[dict]:
    if db.using_postgres():
        return db.call_read_sp('sp_listar_tutores')
    return [data._usuario_como_rol(u, 'tutor') for u in data.USUARIOS
            if 'tutor' in _roles_de_usuario_mem(u['usuario_id'])]


def obtener_tutor(tutor_id: int) -> dict | None:
    if db.using_postgres():
        return db.call_read_sp_one('sp_obtener_tutor', [tutor_id])
    u = data.get_by_id(data.USUARIOS, 'usuario_id', tutor_id)
    return data._usuario_como_rol(u, 'tutor') if u else None


def crear_tutor(datos: dict) -> dict:
    """datos usa claves tutor_* (formulario) + tutor_contrasena."""
    if db.using_postgres():
        r = _sp('sp_crear_tutor', [
            datos.get('tutor_prim_nombre'), datos.get('tutor_seg_nombre'),
            datos.get('tutor_apellido_pat'), datos.get('tutor_apellido_mat'),
            datos.get('tutor_telefono'), datos.get('tutor_curp'),
            datos.get('tutor_email'), datos.get('tutor_contrasena'),
        ])
        return obtener_tutor(r['p_id']) or {}
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


def actualizar_tutor(tutor_id: int, campos: dict) -> None:
    """campos usa claves tutor_* (del formulario)."""
    if db.using_postgres():
        _sp('sp_actualizar_tutor', [
            tutor_id,
            campos.get('tutor_prim_nombre'), campos.get('tutor_seg_nombre'),
            campos.get('tutor_apellido_pat'), campos.get('tutor_apellido_mat'),
            campos.get('tutor_telefono'), campos.get('tutor_curp'),
            campos.get('tutor_email'),
        ], out_count=2)
        return
    u = data.get_by_id(data.USUARIOS, 'usuario_id', tutor_id)
    if u:
        u.update(campos)


def eliminar_tutor(tutor_id: int) -> None:
    if db.using_postgres():
        _sp('sp_eliminar_tutor', [tutor_id], out_count=2)
        return
    if any(pt['tutor_id'] == tutor_id for pt in data.PACIENTES_TUTORES):
        raise ValueError('No se puede eliminar: este tutor tiene pacientes vinculados')
    data.USUARIOS[:] = [u for u in data.USUARIOS if u['usuario_id'] != tutor_id]
    data.LOGIN[:] = [lg for lg in data.LOGIN if lg['usuario_id'] != tutor_id]
    data.USUARIOS_ROLES[:] = [ur for ur in data.USUARIOS_ROLES if ur['usuario_id'] != tutor_id]


def pacientes_de_tutor(tutor_id: int) -> list[dict]:
    if db.using_postgres():
        return db.call_read_sp('sp_pacientes_de_tutor', [tutor_id])
    ids = [pt['paciente_id'] for pt in data.PACIENTES_TUTORES if pt['tutor_id'] == tutor_id]
    return [p for p in data.PACIENTES if p['paciente_id'] in ids]


# ─────────────────────────────────────────────
# RESPONSABLES
# ─────────────────────────────────────────────

def listar_responsables() -> list[dict]:
    if db.using_postgres():
        rows = db.call_read_sp('sp_listar_responsables')
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
        return db.call_read_sp_one('sp_obtener_responsable', [responsable_id])
    u = data.get_by_id(data.USUARIOS, 'usuario_id', responsable_id)
    return data._usuario_como_rol(u, 'responsable') if u else None


def crear_responsable(datos: dict) -> dict:
    """datos usa claves responsable_* (formulario) + responsable_contrasena."""
    if db.using_postgres():
        r = _sp('sp_crear_responsable', [
            datos.get('responsable_prim_nombre'), datos.get('responsable_seg_nombre'),
            datos.get('responsable_apellido_pat'), datos.get('responsable_apellido_mat'),
            datos.get('responsable_telefono'), datos.get('responsable_curp'),
            datos.get('responsable_rfc'), datos.get('responsable_email'),
            datos.get('responsable_contrasena'), datos.get('centro_id'),
        ])
        return obtener_responsable(r['p_id']) or {}
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


def eliminar_responsable(responsable_id: int) -> None:
    if db.using_postgres():
        _sp('sp_eliminar_responsable', [responsable_id], out_count=2)
        return
    if any(a.get('usuario_id') == responsable_id for a in data.APLICACIONES):
        raise ValueError('No se puede eliminar: este responsable tiene aplicaciones registradas')
    data.USUARIOS[:] = [u for u in data.USUARIOS if u['usuario_id'] != responsable_id]
    data.LOGIN[:] = [lg for lg in data.LOGIN if lg['usuario_id'] != responsable_id]
    data.CEDULAS[:] = [c for c in data.CEDULAS if c['usuario_id'] != responsable_id]
    data.USUARIOS_ROLES[:] = [ur for ur in data.USUARIOS_ROLES
                               if ur['usuario_id'] != responsable_id]


def cedulas_de_responsable(usuario_id: int) -> list[dict]:
    if db.using_postgres():
        return db.call_read_sp('sp_cedulas_de_responsable', [usuario_id])
    return [c for c in data.CEDULAS if c['usuario_id'] == usuario_id]


def agregar_cedula(usuario_id: int, numero: str, especialidad: str | None) -> dict:
    if db.using_postgres():
        r = _sp('sp_agregar_cedula', [usuario_id, numero, especialidad])
        return db.call_read_sp_one('sp_obtener_cedula', [r['p_id']]) or {}
    nueva = {
        'cedula_id':           data.next_id(data.CEDULAS, 'cedula_id'),
        'cedula_numero':       numero,
        'cedula_especialidad': especialidad,
        'usuario_id':          usuario_id,
    }
    data.CEDULAS.append(nueva)
    return nueva


# ─────────────────────────────────────────────
# RELACIONES PACIENTE-TUTOR
# ─────────────────────────────────────────────

def listar_relaciones() -> list[dict]:
    if db.using_postgres():
        return db.call_read_sp('sp_listar_relaciones')
    return list(data.PACIENTES_TUTORES)


def existe_relacion(paciente_id: int, tutor_id: int) -> bool:
    if db.using_postgres():
        row = db.call_read_sp_one('sp_existe_relacion', [paciente_id, tutor_id])
        return bool(row['result']) if row else False
    return any(pt['paciente_id'] == paciente_id and pt['tutor_id'] == tutor_id
               for pt in data.PACIENTES_TUTORES)


def crear_relacion(paciente_id: int, tutor_id: int, pac_nombre: str, tut_nombre: str) -> dict:
    if db.using_postgres():
        r = _sp('sp_crear_relacion', [paciente_id, tutor_id])
        row = db.call_read_sp_one('sp_obtener_relacion', [r['p_id']])
        return row or {'pac_tut_id': r['p_id'], 'paciente_id': paciente_id,
                       'tutor_id': tutor_id, 'paciente': pac_nombre, 'tutor': tut_nombre}
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
        _sp('sp_eliminar_relacion', [pac_tut_id], out_count=2)
        return
    data.PACIENTES_TUTORES[:] = [pt for pt in data.PACIENTES_TUTORES
                                  if pt['pac_tut_id'] != pac_tut_id]


# ─────────────────────────────────────────────
# APLICACIONES
# ─────────────────────────────────────────────

def listar_aplicaciones() -> list[dict]:
    if db.using_postgres():
        return db.call_read_sp('sp_listar_aplicaciones')
    return list(data.APLICACIONES)


def aplicaciones_de_paciente(paciente_id: int) -> list[dict]:
    if db.using_postgres():
        return db.call_read_sp('sp_aplicaciones_de_paciente', [paciente_id])
    return [a for a in data.APLICACIONES if a['paciente_id'] == paciente_id]


def dosis_ya_aplicada(paciente_id: int, dosis_id: int) -> bool:
    if db.using_postgres():
        row = db.call_read_sp_one('sp_dosis_ya_aplicada', [paciente_id, dosis_id])
        return bool(row['result']) if row else False
    return any(a['paciente_id'] == paciente_id and a['dosis_id'] == dosis_id
               for a in data.APLICACIONES)


def registrar_aplicacion(datos: dict) -> dict:
    """
    datos: paciente_id, usuario_id, centro_id, lote_id, dosis_id,
           aplicacion_timestamp, aplicacion_observaciones.
    El SP valida stock y dosis; el trigger descuenta el inventario automáticamente.
    """
    if db.using_postgres():
        r = _sp('sp_registrar_aplicacion', [
            datos['paciente_id'], datos['usuario_id'], datos['centro_id'],
            datos['lote_id'], datos['dosis_id'],
            datos['aplicacion_timestamp'], datos.get('aplicacion_observaciones'),
        ])
        return db.call_read_sp_one('sp_obtener_aplicacion', [r['p_id']]) or {}
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
    """Dosis del esquema del paciente con info de aplicación (LEFT JOIN sobre vistas)."""
    if db.using_postgres():
        return db.call_read_sp('sp_historial_vacunacion_paciente', [paciente_id, esquema_id])
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
        return db.call_read_sp('sp_listar_inventarios')
    return list(data.INVENTARIOS)


def inventarios_activos_de_centro(centro_id: int) -> list[dict]:
    if db.using_postgres():
        return db.call_read_sp('sp_inventarios_activos_de_centro', [centro_id])
    return [i for i in data.INVENTARIOS
            if i['centro_id'] == centro_id
            and i.get('inventario_activo_desde') is not None
            and i['inventario_stock_actual'] > 0]


def obtener_inventario(inventario_id: int) -> dict | None:
    if db.using_postgres():
        return db.call_read_sp_one('sp_obtener_inventario', [inventario_id])
    return data.get_by_id(data.INVENTARIOS, 'inventario_id', inventario_id)


def inventarios_pendientes_de_centro(centro_id: int) -> list[dict]:
    if db.using_postgres():
        return db.call_read_sp('sp_inventarios_pendientes_de_centro', [centro_id])
    return [i for i in data.INVENTARIOS
            if i['centro_id'] == centro_id
            and i.get('inventario_activo_desde') is None]


def confirmar_recepcion_inventario(lote_codigo: str, responsable_id: int) -> dict:
    if db.using_postgres():
        return _sp('sp_confirmar_recepcion_inventario', [lote_codigo, responsable_id], out_count=2)
    return {'p_ok': 0, 'p_msg': 'Función solo disponible con PostgreSQL.'}


def asignar_inventario(datos: dict) -> dict:
    """
    datos: centro_id, lote_id, inventario_stock_inicial, inventario_stock_actual,
    inventario_activo_desde.
    """
    if db.using_postgres():
        r = _sp('sp_asignar_inventario', [
            datos['centro_id'], datos['lote_id'],
            datos['inventario_stock_inicial'], datos['inventario_stock_actual'],
            datos.get('inventario_activo_desde'),
        ])
        return obtener_inventario(r['p_id']) or {}
    nuevo = dict(datos)
    nuevo['inventario_id'] = data.next_id(data.INVENTARIOS, 'inventario_id')
    nuevo.setdefault('inventario_activo_desde', None)
    data.INVENTARIOS.append(nuevo)
    return nuevo


def centros_con_vacuna_disponible(vacuna_id: int) -> list[dict]:
    if db.using_postgres():
        return db.call_read_sp('sp_centros_con_vacuna_disponible', [vacuna_id])
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
        return db.call_read_sp('sp_listar_lotes')
    return list(data.LOTES)


def obtener_lote(lote_id: int) -> dict | None:
    if db.using_postgres():
        return db.call_read_sp_one('sp_obtener_lote', [lote_id])
    return data.get_by_id(data.LOTES, 'lote_id', lote_id)


def crear_lote(datos: dict) -> dict:
    """datos: lote_codigo, lote_fecha_fabricacion, lote_fecha_caducidad,
    vacuna_id, fabricante_id, lote_cant_inicial, proveedor_id."""
    if db.using_postgres():
        r = _sp('sp_crear_lote', [
            datos['lote_codigo'], datos['lote_fecha_fabricacion'], datos['lote_fecha_caducidad'],
            datos['lote_cant_inicial'], datos['vacuna_id'], datos['fabricante_id'],
            datos['proveedor_id'],
        ])
        return obtener_lote(r['p_id']) or {}
    nuevo = dict(datos)
    nuevo['lote_id'] = data.next_id(data.LOTES, 'lote_id')
    data.LOTES.append(nuevo)
    return nuevo


# ─────────────────────────────────────────────
# PROVEEDORES
# ─────────────────────────────────────────────

def listar_proveedores() -> list[dict]:
    if db.using_postgres():
        return db.call_read_sp('sp_listar_proveedores')
    return list(data.PROVEEDORES)


def obtener_proveedor(proveedor_id: int) -> dict | None:
    if db.using_postgres():
        return db.call_read_sp_one('sp_obtener_proveedor', [proveedor_id])
    return data.get_by_id(data.PROVEEDORES, 'proveedor_id', proveedor_id)


def crear_proveedor(datos: dict) -> dict:
    """datos: proveedor_prim_nombre, proveedor_apellido_pat, proveedor_email,
    proveedor_telefono, proveedor_empresa, fabricante_id."""
    if db.using_postgres():
        r = _sp('sp_crear_proveedor', [
            datos.get('proveedor_prim_nombre'), datos.get('proveedor_seg_nombre'),
            datos.get('proveedor_apellido_pat'), datos.get('proveedor_apellido_mat'),
            datos.get('proveedor_email'), datos.get('proveedor_telefono'),
            datos.get('proveedor_empresa'), datos['fabricante_id'],
        ])
        return obtener_proveedor(r['p_id']) or {}
    nuevo = dict(datos)
    nuevo['proveedor_id'] = data.next_id(data.PROVEEDORES, 'proveedor_id')
    data.PROVEEDORES.append(nuevo)
    return nuevo


# ─────────────────────────────────────────────
# CATÁLOGOS CLÍNICOS
# ─────────────────────────────────────────────

def listar_vacunas() -> list[dict]:
    if db.using_postgres():
        return db.call_read_sp('sp_listar_vacunas')
    return list(data.VACUNAS)


def obtener_vacuna(vacuna_id: int) -> dict | None:
    if db.using_postgres():
        return db.call_read_sp_one('sp_obtener_vacuna', [vacuna_id])
    return data.get_by_id(data.VACUNAS, 'vacuna_id', vacuna_id)


def crear_vacuna(datos: dict) -> dict:
    if db.using_postgres():
        r = _sp('sp_crear_vacuna', [datos['vacuna_nombre']])
        return obtener_vacuna(r['p_id']) or {}
    nuevo = dict(datos)
    nuevo['vacuna_id'] = data.next_id(data.VACUNAS, 'vacuna_id')
    nuevo.setdefault('vacuna_activa', True)
    data.VACUNAS.append(nuevo)
    return nuevo


def listar_dosis(vacuna_id: int | None = None) -> list[dict]:
    if db.using_postgres():
        if vacuna_id:
            return db.call_read_sp('sp_listar_dosis_por_vacuna', [vacuna_id])
        return db.call_read_sp('sp_listar_dosis')
    if vacuna_id:
        return [d for d in data.DOSIS if d['vacuna_id'] == vacuna_id]
    return list(data.DOSIS)


def obtener_dosis(dosis_id: int) -> dict | None:
    if db.using_postgres():
        return db.call_read_sp_one('sp_obtener_dosis', [dosis_id])
    return data.get_by_id(data.DOSIS, 'dosis_id', dosis_id)


def crear_dosis(datos: dict) -> dict:
    if db.using_postgres():
        r = _sp('sp_crear_dosis', [
            datos['vacuna_id'], datos['dosis_tipo'], datos['dosis_cant_ml'],
            datos.get('dosis_area_aplicacion'), datos.get('dosis_edad_oportuna_dias', 0),
            datos.get('dosis_intervalo_min_dias', 0), datos.get('dosis_limite_edad_dias'),
        ])
        return obtener_dosis(r['p_id']) or {}
    nuevo = dict(datos)
    nuevo['dosis_id'] = data.next_id(data.DOSIS, 'dosis_id')
    data.DOSIS.append(nuevo)
    return nuevo


def listar_esquemas() -> list[dict]:
    if db.using_postgres():
        return db.call_read_sp('sp_listar_esquemas')
    return list(data.ESQUEMAS)


def obtener_esquema(esquema_id: int) -> dict | None:
    if db.using_postgres():
        return db.call_read_sp_one('sp_obtener_esquema', [esquema_id])
    return data.get_by_id(data.ESQUEMAS, 'esquema_id', esquema_id)


def crear_esquema(datos: dict) -> dict:
    if db.using_postgres():
        r = _sp('sp_crear_esquema', [
            datos['esquema_nombre'], datos['esquema_fecha_vigencia'],
            datos.get('vigente_desde'),
        ])
        return obtener_esquema(r['p_id']) or {}
    nuevo = dict(datos)
    nuevo['esquema_id'] = data.next_id(data.ESQUEMAS, 'esquema_id')
    nuevo.setdefault('total_dosis', 0)
    data.ESQUEMAS.append(nuevo)
    return nuevo


def eliminar_esquema(esquema_id: int) -> None:
    if db.using_postgres():
        _sp('sp_eliminar_esquema', [esquema_id], out_count=2)
        return
    if any(p['esquema_id'] == esquema_id for p in data.PACIENTES):
        raise ValueError('No se puede eliminar: hay pacientes asignados a este esquema')
    data.ESQUEMAS[:] = [e for e in data.ESQUEMAS if e['esquema_id'] != esquema_id]
    data.DOSIS_ESQUEMAS[:] = [de for de in data.DOSIS_ESQUEMAS if de['esquema_id'] != esquema_id]


def dosis_de_esquema(esquema_id: int) -> list[dict]:
    if db.using_postgres():
        return db.call_read_sp('sp_dosis_de_esquema', [esquema_id])
    ids = {de['dosis_id'] for de in data.DOSIS_ESQUEMAS if de['esquema_id'] == esquema_id}
    return [d for d in data.DOSIS if d['dosis_id'] in ids]


def listar_dosis_esquemas() -> list[dict]:
    if db.using_postgres():
        return db.call_read_sp('sp_listar_dosis_esquemas')
    return list(data.DOSIS_ESQUEMAS)


def agregar_dosis_a_esquema(esquema_id: int, dosis_id: int) -> dict:
    if db.using_postgres():
        r = _sp('sp_agregar_dosis_a_esquema', [esquema_id, dosis_id])
        return {'dosis_esq_id': r.get('p_id'), 'esquema_id': esquema_id, 'dosis_id': dosis_id}
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
        return db.call_read_sp('sp_listar_padecimientos')
    return list(data.PADECIMIENTOS)


def crear_padecimiento(datos: dict) -> dict:
    if db.using_postgres():
        r = _sp('sp_crear_padecimiento', [
            datos['padecimiento_nombre'], datos.get('padecimiento_descripcion'),
        ])
        return db.call_read_sp_one('sp_obtener_padecimiento', [r['p_id']]) or {}
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
        return db.call_read_sp('sp_listar_fabricantes')
    return list(data.FABRICANTES)


def obtener_fabricante(fabricante_id: int) -> dict | None:
    if db.using_postgres():
        return db.call_read_sp_one('sp_obtener_fabricante', [fabricante_id])
    return data.get_by_id(data.FABRICANTES, 'fabricante_id', fabricante_id)


def crear_fabricante(datos: dict) -> dict:
    if db.using_postgres():
        r = _sp('sp_crear_fabricante', [
            datos['fabricante_nombre'], datos['pais_id'], datos.get('fabricante_telefono'),
        ])
        return obtener_fabricante(r['p_id']) or {}
    nuevo = dict(datos)
    nuevo['fabricante_id'] = data.next_id(data.FABRICANTES, 'fabricante_id')
    data.FABRICANTES.append(nuevo)
    return nuevo


# ─────────────────────────────────────────────
# CENTROS DE SALUD
# ─────────────────────────────────────────────

def listar_centros() -> list[dict]:
    if db.using_postgres():
        return db.call_read_sp('sp_listar_centros')
    return list(data.CENTROS)


def obtener_centro(centro_id: int) -> dict | None:
    if db.using_postgres():
        return db.call_read_sp_one('sp_obtener_centro', [centro_id])
    return data.get_by_id(data.CENTROS, 'centro_id', centro_id)


def crear_centro(datos: dict) -> dict:
    if db.using_postgres():
        r = _sp('sp_crear_centro', [
            datos['centro_nombre'], datos.get('centro_calle'), datos.get('centro_numero'),
            datos.get('centro_codigo_postal'), datos['ciudad_id'],
            datos.get('centro_horario_inicio'), datos.get('centro_horario_fin'),
            datos.get('centro_latitud'), datos.get('centro_longitud'),
            datos.get('centro_telefono'), datos.get('centro_beacon'),
        ])
        return obtener_centro(r['p_id']) or {}
    nuevo = dict(datos)
    nuevo['centro_id'] = data.next_id(data.CENTROS, 'centro_id')
    data.CENTROS.append(nuevo)
    return nuevo


def obtener_centro_por_beacon(beacon_id: str) -> dict | None:
    if db.using_postgres():
        return db.call_read_sp_one('sp_obtener_centro_por_beacon', [beacon_id])
    return next((c for c in data.CENTROS if c.get('centro_beacon') == beacon_id), None)


def vacunas_en_centro(centro_id: int) -> list[dict]:
    if db.using_postgres():
        rows = db.call_read_sp('sp_vacunas_en_centro', [centro_id])
        for r in rows:
            if r.get('stock_total') is not None:
                r['stock_total'] = int(r['stock_total'])
        return rows
    return []


def registrar_lectura_beacon(centro_id: int, tutor_id: int) -> None:
    if not db.using_postgres():
        return
    _sp('sp_registrar_lectura_beacon', [centro_id, tutor_id], out_count=2)


def personas_esperando_en_centro(centro_id: int) -> int:
    if db.using_postgres():
        row = db.call_read_sp_one('sp_personas_esperando_en_centro', [centro_id])
        return int(row['total']) if row else 0
    return 0


def eliminar_centro(centro_id: int) -> None:
    if db.using_postgres():
        _sp('sp_eliminar_centro', [centro_id], out_count=2)
        return
    if (any(u.get('centro_id') == centro_id for u in data.USUARIOS) or
            any(i['centro_id'] == centro_id for i in data.INVENTARIOS)):
        raise ValueError('No se puede eliminar: el centro tiene responsables o inventario asignado')
    data.CENTROS[:] = [c for c in data.CENTROS if c['centro_id'] != centro_id]


# ─────────────────────────────────────────────
# GEOGRAFÍA
# ─────────────────────────────────────────────

def listar_paises() -> list[dict]:
    if db.using_postgres():
        return db.call_read_sp('sp_listar_paises')
    return list(data.PAISES)


def obtener_pais(pais_id: int) -> dict | None:
    if db.using_postgres():
        return db.call_read_sp_one('sp_obtener_pais', [pais_id])
    return data.get_by_id(data.PAISES, 'pais_id', pais_id)


def crear_pais(nombre: str) -> dict:
    if db.using_postgres():
        r = _sp('sp_crear_pais', [nombre])
        return obtener_pais(r['p_id']) or {}
    nueva = {'pais_id': data.next_id(data.PAISES, 'pais_id'), 'pais_nombre': nombre}
    data.PAISES.append(nueva)
    return nueva


def listar_estados(pais_id: int | None = None) -> list[dict]:
    if db.using_postgres():
        if pais_id:
            return db.call_read_sp('sp_listar_estados_por_pais', [pais_id])
        return db.call_read_sp('sp_listar_estados')
    if pais_id:
        return [e for e in data.ESTADOS if e['pais_id'] == pais_id]
    return list(data.ESTADOS)


def obtener_estado(estado_id: int) -> dict | None:
    if db.using_postgres():
        return db.call_read_sp_one('sp_obtener_estado', [estado_id])
    return data.get_by_id(data.ESTADOS, 'estado_id', estado_id)


def crear_estado(datos: dict) -> dict:
    if db.using_postgres():
        r = _sp('sp_crear_estado', [datos['estado_nombre'], datos['pais_id']])
        return obtener_estado(r['p_id']) or {}
    nuevo = dict(datos)
    nuevo['estado_id'] = data.next_id(data.ESTADOS, 'estado_id')
    data.ESTADOS.append(nuevo)
    return nuevo


def listar_ciudades(estado_id: int | None = None) -> list[dict]:
    if db.using_postgres():
        if estado_id:
            return db.call_read_sp('sp_listar_ciudades_por_estado', [estado_id])
        return db.call_read_sp('sp_listar_ciudades')
    if estado_id:
        return [c for c in data.CIUDADES if c['estado_id'] == estado_id]
    return list(data.CIUDADES)


def obtener_ciudad(ciudad_id: int) -> dict | None:
    if db.using_postgres():
        return db.call_read_sp_one('sp_obtener_ciudad', [ciudad_id])
    return data.get_by_id(data.CIUDADES, 'ciudad_id', ciudad_id)


def crear_ciudad(datos: dict) -> dict:
    if db.using_postgres():
        r = _sp('sp_crear_ciudad', [datos['ciudad_nombre'], datos['estado_id']])
        return obtener_ciudad(r['p_id']) or {}
    nuevo = dict(datos)
    nuevo['ciudad_id'] = data.next_id(data.CIUDADES, 'ciudad_id')
    data.CIUDADES.append(nuevo)
    return nuevo


# ─────────────────────────────────────────────
# ALERTAS
# ─────────────────────────────────────────────

def listar_alertas_inventario() -> list[dict]:
    if db.using_postgres():
        return db.call_read_sp('sp_listar_alertas_inventario')
    return list(data.ALERTAS_INVENTARIO)


def listar_alertas_dosis() -> list[dict]:
    if db.using_postgres():
        return db.call_read_sp('sp_listar_alertas_dosis')
    return list(data.ALERTAS_DOSIS)


# ─────────────────────────────────────────────
# DASHBOARD STATS
# ─────────────────────────────────────────────

def stats_dashboard() -> dict:
    if db.using_postgres():
        return db.call_read_sp_one('sp_stats_dashboard') or {}
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
    if db.using_postgres():
        return db.call_read_sp('sp_chart_aplicaciones_por_mes', [meses])
    from collections import defaultdict
    por_mes = defaultdict(int)
    for a in data.APLICACIONES:
        ts = a['aplicacion_timestamp']
        mes = ts.strftime('%b %Y') if hasattr(ts, 'strftime') else str(ts)[:7]
        por_mes[mes] += 1
    return [{'mes': k, 'total': v} for k, v in por_mes.items()]


def chart_por_mes(desde: str, hasta: str,
                  centro_id: int | None = None,
                  vacuna_id: int | None = None) -> list[dict]:
    if db.using_postgres():
        return db.call_read_sp('sp_chart_por_mes', [desde, hasta, centro_id, vacuna_id])
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
    if db.using_postgres():
        return db.call_read_sp('sp_chart_top_vacunas', [desde, hasta, centro_id, vacuna_id])
    from collections import defaultdict
    cnt: dict = defaultdict(int)
    for a in data.APLICACIONES:
        cnt[a.get('vacuna_nombre', '—')] += 1
    return [{'vacuna_nombre': k, 'total': v}
            for k, v in sorted(cnt.items(), key=lambda x: -x[1])[:8]]


def resumen_periodo(desde: str, hasta: str,
                    centro_id: int | None = None,
                    vacuna_id: int | None = None) -> dict:
    if db.using_postgres():
        row = db.call_read_sp_one('sp_resumen_periodo', [desde, hasta, centro_id, vacuna_id])
        return {'total': int(row['total']) if row else 0}
    return {'total': len(data.APLICACIONES)}


# ── Fotos de perfil ──────────────────────────────────────────────

def actualizar_imagen_usuario(usuario_id: int, ruta: str) -> None:
    if db.using_postgres():
        _sp('sp_actualizar_imagen_usuario', [usuario_id, ruta], out_count=2)
        return
    u = data.get_by_id(data.USUARIOS, 'usuario_id', usuario_id)
    if u:
        u['usuario_imagen'] = ruta


def actualizar_imagen_paciente(paciente_id: int, ruta: str) -> None:
    if db.using_postgres():
        _sp('sp_actualizar_imagen_paciente', [paciente_id, ruta], out_count=2)
        return
    p = data.get_by_id(data.PACIENTES, 'paciente_id', paciente_id)
    if p:
        p['paciente_imagen'] = ruta

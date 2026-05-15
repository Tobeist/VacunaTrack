from __future__ import annotations

import json as _json
import os
import re as _re
from datetime import date, datetime
from decimal import Decimal as _Decimal, InvalidOperation as _DecInvalid
from time import time as _time_fn
from datetime import time as _time
from flask import (Blueprint, render_template, request, redirect, url_for,
                   session, flash, jsonify, g, current_app)
from werkzeug.security import generate_password_hash as _gph
from werkzeug.utils import secure_filename
from functools import partial

from models import repository as repo
from models import mongo_db as mdb
from utils.helpers import days_to_human, generate_temp_password, validar_aplicacion

admin_bp = Blueprint('admin', __name__)

generate_password_hash = partial(_gph, method='pbkdf2:sha256')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
DOSIS_TIPOS = ['UNICA', 'SERIE_PRIMARIA', 'REFUERZO', 'ANUAL', 'ADICIONAL']


def _allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _require_admin():
    if session.get('user_role') != 'admin':
        return redirect(url_for('auth.login'))
    return None


# ── Error helpers ─────────────────────────────────────────────────────────────

class FormError(ValueError):
    """Excepción usada por los parsers seguros (_get_*) para errores de form."""
    pass


_FK_TABLE_LABELS = {
    'tutor':        'tutores',
    'paciente':     'pacientes',
    'responsable':  'responsables',
    'admin':        'administradores',
    'centro':       'centros',
    'esquema':      'esquemas',
    'vacuna':       'vacunas',
    'dosis':        'dosis',
    'lote':         'lotes',
    'inventario':   'inventario',
    'aplicacion':   'aplicaciones',
    'pais':         'países',
    'estado':       'estados',
    'ciudad':       'ciudades',
    'fabricante':   'fabricantes',
    'proveedor':    'proveedores',
    'padecimiento': 'padecimientos',
    'relacion':     'relaciones',
    'pac_tut':      'relaciones',
}


def _rollback_db():
    """Hace rollback de la conexión actual si está en estado de error."""
    try:
        conn = g.get('db') if g else None
        if conn is not None:
            conn.rollback()
    except Exception:
        pass


def _humanize_table_name(raw: str) -> str:
    if not raw:
        return ''
    key = raw.lower().strip().strip('"').replace('_', ' ').split(' ')[0]
    return _FK_TABLE_LABELS.get(key, raw.lower().replace('_', ' '))


def _user_error_msg(exc: Exception) -> str:
    """Traduce una excepción técnica a un mensaje en español amigable para el usuario.
    También hace rollback de la conexión para evitar quedarla en estado abortado.
    """
    _rollback_db()

    # FormError ya viene en español (de _get_int, _get_date, etc.)
    if isinstance(exc, FormError):
        return str(exc)

    # ValueError lanzado por _sp() con p_msg del stored procedure
    if isinstance(exc, ValueError) and not isinstance(exc, FormError):
        msg = str(exc)
        if 'invalid literal for int' in msg.lower():
            return 'Uno de los campos numéricos tiene un valor inválido. Verifica los datos.'
        if 'invalid isoformat' in msg.lower() or 'unconverted data' in msg.lower():
            return 'La fecha tiene un formato inválido. Usa el selector de fecha.'
        if msg and not msg.startswith('<'):
            return msg
        return 'No se pudo completar la operación. Verifica los datos ingresados.'

    # Errores de psycopg (PostgreSQL)
    sqlstate = getattr(exc, 'sqlstate', None)
    diag = getattr(exc, 'diag', None)
    detail = getattr(diag, 'message_detail', None) if diag else None
    table = getattr(diag, 'table_name', None) if diag else None
    constraint = getattr(diag, 'constraint_name', None) if diag else None

    if sqlstate == '23503':  # foreign_key_violation
        ref_table = None
        if detail:
            m = _re.search(r'on table "([^"]+)"', detail)
            if m:
                ref_table = _humanize_table_name(m.group(1))
            else:
                m = _re.search(r'in table "([^"]+)"', detail)
                if m:
                    ref_table = _humanize_table_name(m.group(1))
        if ref_table:
            return f'No se puede completar la operación porque hay registros relacionados en {ref_table}. Elimina o desvincula esos registros primero.'
        return 'No se puede completar la operación porque existen registros relacionados que dependen de este elemento.'

    if sqlstate == '23505':  # unique_violation
        if detail:
            m = _re.search(r'\(([^)]+)\)=\(([^)]+)\)', detail)
            if m:
                field = m.group(1).replace('_', ' ')
                value = m.group(2)
                return f'Ya existe un registro con {field} "{value}". Usa un valor diferente.'
        return 'Ya existe un registro con esos datos. Verifica los campos únicos (correo, CURP, RFC, código, etc.).'

    if sqlstate == '23502':  # not_null_violation
        col = getattr(diag, 'column_name', None) if diag else None
        if col:
            return f'El campo "{col.replace("_", " ")}" es obligatorio y no puede quedar vacío.'
        return 'Faltan campos obligatorios. Verifica que hayas llenado todos los campos requeridos.'

    if sqlstate == '23514':  # check_violation
        if constraint:
            return f'El dato no cumple con la validación "{constraint.replace("_", " ")}". Verifica los valores.'
        return 'Los datos no cumplen las reglas de validación. Verifica los valores ingresados.'

    if sqlstate == '22P02':
        return 'Uno de los datos tiene un formato inválido. Verifica los campos numéricos y fechas.'

    if sqlstate == '22003':
        return 'Un valor numérico está fuera del rango permitido.'

    if sqlstate == '22008':
        return 'La fecha está fuera del rango permitido.'

    if sqlstate == '25P02':
        return 'La operación anterior falló. Intenta de nuevo desde el inicio.'

    if sqlstate == '42883':
        return 'Operación no disponible: falta una actualización en la base de datos. Contacta al administrador.'

    if isinstance(exc, (KeyError,)):
        campo = str(exc).strip("'\"")
        return f'Falta el campo "{campo}" en el formulario. Asegúrate de llenar todos los datos.'

    if isinstance(exc, _DecInvalid):
        return 'Un valor decimal tiene formato inválido (usa punto como separador).'

    if isinstance(exc, TypeError):
        return 'No se pudo procesar uno de los datos. Verifica que todos los campos estén completos.'

    if isinstance(exc, AttributeError):
        return 'No se pudo completar la operación: faltan datos relacionados (puede que un registro ya no exista).'

    return 'Ocurrió un error al procesar la solicitud. Verifica los datos e intenta de nuevo.'


def _flash_error(exc: Exception):
    """Atajo: traduce la excepción y la muestra como flash de error."""
    try:
        current_app.logger.exception('Error en handler: %s', exc)
    except Exception:
        pass
    flash(_user_error_msg(exc), 'error')


# ── Parsers seguros para campos de formulario ────────────────────────────────

def _get_str(f, key: str, label: str | None = None, *, required: bool = False,
             max_len: int | None = None, upper: bool = False, lower: bool = False,
             pattern: str | None = None, pattern_msg: str | None = None) -> str | None:
    label = label or key.replace('_', ' ')
    raw = (f.get(key) or '').strip()
    if not raw:
        if required:
            raise FormError(f'El campo "{label}" es obligatorio.')
        return None
    if upper:
        raw = raw.upper()
    if lower:
        raw = raw.lower()
    if max_len and len(raw) > max_len:
        raise FormError(f'El campo "{label}" no puede tener más de {max_len} caracteres.')
    if pattern and not _re.fullmatch(pattern, raw):
        raise FormError(pattern_msg or f'El formato de "{label}" es inválido.')
    return raw


_CURP_RE    = r'[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z\d]\d'
_RFC_RE     = r'[A-Z]{3,4}\d{6}[A-Z\d]{3}'
_TEL_RE     = r'\d{10}'
_EMAIL_RE   = r'[^@\s]+@[^@\s]+\.[^@\s]+'


def _get_int(f, key: str, label: str | None = None, *, required: bool = True,
             min_value: int | None = None) -> int | None:
    label = label or key.replace('_', ' ')
    raw = (f.get(key) or '').strip()
    if not raw:
        if required:
            raise FormError(f'El campo "{label}" es obligatorio.')
        return None
    try:
        val = int(raw)
    except (ValueError, TypeError):
        raise FormError(f'El campo "{label}" debe ser un número entero válido.')
    if min_value is not None and val < min_value:
        raise FormError(f'El campo "{label}" debe ser mayor o igual a {min_value}.')
    return val


def _get_float(f, key: str, label: str | None = None, *, required: bool = True,
               min_value: float | None = None) -> float | None:
    label = label or key.replace('_', ' ')
    raw = (f.get(key) or '').strip().replace(',', '.')
    if not raw:
        if required:
            raise FormError(f'El campo "{label}" es obligatorio.')
        return None
    try:
        val = float(raw)
    except (ValueError, TypeError):
        raise FormError(f'El campo "{label}" debe ser un número válido.')
    if min_value is not None and val < min_value:
        raise FormError(f'El campo "{label}" debe ser mayor o igual a {min_value}.')
    return val


def _get_decimal(f, key: str, label: str | None = None, *, required: bool = False):
    label = label or key.replace('_', ' ')
    raw = (f.get(key) or '').strip().replace(',', '.')
    if not raw:
        if required:
            raise FormError(f'El campo "{label}" es obligatorio.')
        return None
    try:
        return _Decimal(raw)
    except (_DecInvalid, ValueError, TypeError):
        raise FormError(f'El campo "{label}" debe ser un número decimal válido (ej: 25.6789).')


def _get_date(f, key: str, label: str | None = None, *, required: bool = True):
    label = label or key.replace('_', ' ')
    raw = (f.get(key) or '').strip()
    if not raw:
        if required:
            raise FormError(f'El campo "{label}" es obligatorio.')
        return None
    try:
        return date.fromisoformat(raw)
    except (ValueError, TypeError):
        raise FormError(f'El campo "{label}" tiene un formato de fecha inválido (usa AAAA-MM-DD).')


def _get_time_safe(f, key: str, label: str | None = None, *, required: bool = False):
    label = label or key.replace('_', ' ')
    raw = (f.get(key) or '').strip()
    if not raw:
        if required:
            raise FormError(f'El campo "{label}" es obligatorio.')
        return None
    try:
        parts = raw.split(':')
        return _time(int(parts[0]), int(parts[1]))
    except (ValueError, IndexError, TypeError):
        raise FormError(f'El campo "{label}" tiene un formato de hora inválido (usa HH:MM).')


# ── Admin routes ──────────────────────────────────────────────────────────────

@admin_bp.route('/admin')
@admin_bp.route('/admin/dashboard')
def dashboard():
    redir = _require_admin()
    if redir:
        return redir

    stats = repo.stats_dashboard()

    alertas = []
    for a in repo.listar_alertas_inventario()[-5:]:
        ts = a.get('alerta_inv_timestamp') or a.get('ts')
        alertas.append({'tipo': 'inventario', 'subtipo': a['alerta_inv_tipo'], 'ts': ts, 'paciente': None})
    for a in repo.listar_alertas_dosis()[-5:]:
        alertas.append({'tipo': 'dosis', 'subtipo': a['alerta_dosis_pac_tipo'],
                        'ts': a['alerta_dosis_pac_timestamp'], 'paciente': a.get('paciente')})
    alertas.sort(key=lambda x: x['ts'] or datetime.min, reverse=True)

    return render_template('admin/dashboard.html', stats=stats, alertas=alertas[:10])


@admin_bp.route('/admin/usuarios', methods=['GET', 'POST'])
def usuarios():
    redir = _require_admin()
    if redir:
        return redir
    if request.method == 'POST':
        f = request.form
        try:
            roles = f.getlist('roles')
            if not roles:
                raise FormError('Debes seleccionar al menos un rol.')
            temp  = generate_temp_password()
            datos = {
                'prim_nombre':  _get_str(f, 'prim_nombre',  'primer nombre',  required=True),
                'seg_nombre':   _get_str(f, 'seg_nombre',   'segundo nombre'),
                'apellido_pat': _get_str(f, 'apellido_pat', 'apellido paterno', required=True),
                'apellido_mat': _get_str(f, 'apellido_mat', 'apellido materno'),
                'curp':         _get_str(f, 'curp', 'CURP', upper=True, max_len=18,
                                        pattern=_CURP_RE, pattern_msg='CURP inválido (formato: AAAA######HAAAAAX#).'),
                'email':        _get_str(f, 'email', 'correo electrónico', required=True, lower=True,
                                        pattern=_EMAIL_RE, pattern_msg='El correo electrónico no tiene un formato válido.'),
                'telefono':     _get_str(f, 'telefono', 'teléfono', required=True,
                                        pattern=_TEL_RE, pattern_msg='El teléfono debe contener exactamente 10 dígitos.'),
                'roles':        roles,
                'contrasena':   generate_password_hash(temp),
            }
            if any(r in roles for r in ('admin', 'responsable')):
                datos['rfc'] = _get_str(f, 'rfc', 'RFC', upper=True, max_len=13,
                                        pattern=_RFC_RE, pattern_msg='RFC inválido (formato: 3-4 letras, 6 dígitos, 3 caracteres).')
            if 'responsable' in roles:
                datos['centro_id'] = _get_int(f, 'centro_id', 'centro de salud', required=True)
                datos['cedulas_nums']  = [n.strip() for n in f.getlist('cedulas_nums[]') if n.strip()]
                datos['cedulas_specs'] = f.getlist('cedulas_specs[]')[:len(datos['cedulas_nums'])]
                if not datos['cedulas_nums']:
                    raise FormError('Debes registrar al menos una cédula profesional.')
                for num in datos['cedulas_nums']:
                    if len(num) > 20:
                        raise FormError(f'Cédula "{num}" excede el límite de 20 caracteres.')
            nuevo = repo.crear_usuario(datos)
            file = request.files.get('foto')
            if file and file.filename and _allowed_file(file.filename):
                filename  = f"usuario_{nuevo['usuario_id']}_{int(_time_fn())}.{file.filename.rsplit('.',1)[1].lower()}"
                upload_dir = os.path.join(current_app.static_folder, 'uploads', 'fotos')
                os.makedirs(upload_dir, exist_ok=True)
                file.save(os.path.join(upload_dir, filename))
                repo.actualizar_imagen_usuario(nuevo['usuario_id'], f"uploads/fotos/{filename}")
            flash(f'Usuario registrado. Contraseña temporal: <strong>{temp}</strong>', 'success')
        except Exception as e:
            _flash_error(e)
        return redirect(url_for('admin.usuarios'))
    return render_template('admin/usuarios.html',
                           usuarios=repo.listar_usuarios(),
                           centros=repo.listar_centros())


@admin_bp.route('/admin/usuarios/<int:uid>/editar', methods=['POST'])
def editar_usuario(uid):
    redir = _require_admin()
    if redir:
        return redir
    f = request.form
    try:
        roles = f.getlist('roles')
        if not roles:
            raise FormError('Debes seleccionar al menos un rol.')
        datos = {
            'prim_nombre':  _get_str(f, 'prim_nombre',  'primer nombre',  required=True),
            'seg_nombre':   _get_str(f, 'seg_nombre',   'segundo nombre'),
            'apellido_pat': _get_str(f, 'apellido_pat', 'apellido paterno', required=True),
            'apellido_mat': _get_str(f, 'apellido_mat', 'apellido materno'),
            'curp':         _get_str(f, 'curp', 'CURP', upper=True, max_len=18,
                                    pattern=_CURP_RE, pattern_msg='CURP inválido (formato: AAAA######HAAAAAX#).'),
            'email':        _get_str(f, 'email', 'correo electrónico', required=True, lower=True,
                                    pattern=_EMAIL_RE, pattern_msg='El correo electrónico no tiene un formato válido.'),
            'telefono':     _get_str(f, 'telefono', 'teléfono', required=True,
                                    pattern=_TEL_RE, pattern_msg='El teléfono debe contener exactamente 10 dígitos.'),
            'roles':        roles,
        }
        if any(r in roles for r in ('admin', 'responsable')):
            datos['rfc'] = _get_str(f, 'rfc', 'RFC', upper=True, max_len=13,
                                    pattern=_RFC_RE, pattern_msg='RFC inválido (formato: 3-4 letras, 6 dígitos, 3 caracteres).')
        if 'responsable' in roles:
            datos['centro_id'] = _get_int(f, 'centro_id', 'centro de salud', required=True)
            datos['cedulas_nums']  = [n.strip() for n in f.getlist('cedulas_nums[]') if n.strip()]
            datos['cedulas_specs'] = f.getlist('cedulas_specs[]')[:len(datos['cedulas_nums'])]
            if not datos['cedulas_nums']:
                raise FormError('Debes registrar al menos una cédula profesional.')
            for num in datos['cedulas_nums']:
                if not _re.fullmatch(r'\d{7,8}', num):
                    raise FormError(f'Cédula "{num}" inválida. Debe contener 7 u 8 dígitos.')
        repo.actualizar_usuario(uid, datos)
        file = request.files.get('foto')
        if file and file.filename and _allowed_file(file.filename):
            filename  = f"usuario_{uid}_{int(_time_fn())}.{file.filename.rsplit('.',1)[1].lower()}"
            upload_dir = os.path.join(current_app.static_folder, 'uploads', 'fotos')
            os.makedirs(upload_dir, exist_ok=True)
            file.save(os.path.join(upload_dir, filename))
            repo.actualizar_imagen_usuario(uid, f"uploads/fotos/{filename}")
        flash('Usuario actualizado.', 'success')
    except Exception as e:
        _flash_error(e)
    return redirect(url_for('admin.usuarios'))


@admin_bp.route('/admin/usuarios/<int:uid>/toggle-activo', methods=['POST'])
def toggle_usuario_activo(uid):
    redir = _require_admin()
    if redir:
        return redir
    try:
        r = repo.toggle_usuario_activo(uid, session.get('user_id', 0))
        flash(r.get('p_msg', 'Estado actualizado.'), 'success')
    except Exception as e:
        _flash_error(e)
    return redirect(url_for('admin.usuarios'))


@admin_bp.route('/admin/usuarios/<int:uid>/eliminar', methods=['POST'])
def eliminar_usuario(uid):
    redir = _require_admin()
    if redir:
        return redir
    try:
        repo.eliminar_usuario(uid, session.get('user_id', 0))
        flash('Usuario eliminado.', 'success')
    except Exception as e:
        _flash_error(e)
    return redirect(url_for('admin.usuarios'))


# Redirects para URLs legadas
@admin_bp.route('/admin/tutores')
def tutores():
    return redirect(url_for('admin.usuarios'))

@admin_bp.route('/admin/responsables')
def responsables():
    return redirect(url_for('admin.usuarios'))

@admin_bp.route('/admin/administradores')
def administradores():
    return redirect(url_for('admin.usuarios'))


@admin_bp.route('/admin/pacientes', methods=['GET', 'POST'])
def pacientes():
    redir = _require_admin()
    if redir:
        return redir
    if request.method == 'POST':
        f = request.form
        try:
            curp = _get_str(f, 'curp', 'CURP', upper=True, max_len=18,
                            pattern=_CURP_RE, pattern_msg='CURP inválido (formato: AAAA######HAAAAAX#).')
            cert = _get_str(f, 'num_cert_nac', 'número de certificado de nacimiento', max_len=30)
            if not curp and not cert:
                raise FormError('Debes llenar al menos CURP o N° Certificado de Nacimiento.')
            fecha_nac = _get_date(f, 'fecha_nac', 'fecha de nacimiento', required=True)
            if fecha_nac > date.today():
                raise FormError('La fecha de nacimiento no puede ser una fecha futura.')
            datos = {
                'paciente_prim_nombre':  _get_str(f, 'prim_nombre',  'primer nombre',  required=True),
                'paciente_seg_nombre':   _get_str(f, 'seg_nombre',   'segundo nombre'),
                'paciente_apellido_pat': _get_str(f, 'apellido_pat', 'apellido paterno', required=True),
                'paciente_apellido_mat': _get_str(f, 'apellido_mat', 'apellido materno'),
                'paciente_curp':         curp,
                'paciente_num_cert_nac': cert,
                'paciente_fecha_nac':    fecha_nac,
                'paciente_sexo':         _get_str(f, 'sexo', 'sexo', required=True),
                'paciente_nfc':          _get_str(f, 'nfc', 'UID NFC'),
                'esquema_id':            _get_int(f, 'esquema_id', 'esquema de vacunación', required=True),
            }
            nuevo = repo.crear_paciente(datos)
            file = request.files.get('foto')
            if file and file.filename and _allowed_file(file.filename):
                filename  = f"paciente_{nuevo['paciente_id']}_{int(_time_fn())}.{file.filename.rsplit('.',1)[1].lower()}"
                upload_dir = os.path.join(current_app.static_folder, 'uploads', 'fotos')
                os.makedirs(upload_dir, exist_ok=True)
                file.save(os.path.join(upload_dir, filename))
                repo.actualizar_imagen_paciente(nuevo['paciente_id'], f"uploads/fotos/{filename}")
            result = nuevo
            mdb.log_sistema(
                evento='paciente_creado',
                entidad='paciente',
                pg_entidad_id=result.get('p_id') if result else None,
                pg_usuario_id=session.get('user_id'),
                descripcion=(f"Paciente {datos['paciente_prim_nombre']} "
                             f"{datos['paciente_apellido_pat']} registrado"),
                meta={'curp': datos.get('paciente_curp'), 'sexo': datos['paciente_sexo']},
            )
            flash('Paciente registrado.', 'success')
        except Exception as e:
            _flash_error(e)
        return redirect(url_for('admin.pacientes'))
    return render_template('admin/pacientes.html',
                           pacientes=repo.listar_pacientes(),
                           esquemas=repo.listar_esquemas())


@admin_bp.route('/admin/pacientes/<int:pid>/editar', methods=['POST'])
def editar_paciente(pid):
    redir = _require_admin()
    if redir:
        return redir
    f = request.form
    try:
        fecha_nac = _get_date(f, 'fecha_nac', 'fecha de nacimiento', required=True)
        if fecha_nac > date.today():
            raise FormError('La fecha de nacimiento no puede ser una fecha futura.')
        campos = {
            'paciente_prim_nombre':  _get_str(f, 'prim_nombre',  'primer nombre',  required=True),
            'paciente_seg_nombre':   _get_str(f, 'seg_nombre',   'segundo nombre'),
            'paciente_apellido_pat': _get_str(f, 'apellido_pat', 'apellido paterno', required=True),
            'paciente_apellido_mat': _get_str(f, 'apellido_mat', 'apellido materno'),
            'paciente_curp':         _get_str(f, 'curp', 'CURP', upper=True, max_len=18,
                                             pattern=_CURP_RE, pattern_msg='CURP inválido (formato: AAAA######HAAAAAX#).'),
            'paciente_num_cert_nac': _get_str(f, 'num_cert_nac', 'número de certificado de nacimiento', max_len=30),
            'paciente_fecha_nac':    fecha_nac,
            'paciente_sexo':         _get_str(f, 'sexo', 'sexo', required=True),
            'paciente_nfc':          _get_str(f, 'nfc', 'UID NFC'),
            'esquema_id':            _get_int(f, 'esquema_id', 'esquema de vacunación', required=True),
        }
        repo.actualizar_paciente(pid, campos)
        file = request.files.get('foto')
        if file and file.filename and _allowed_file(file.filename):
            filename  = f"paciente_{pid}_{int(_time_fn())}.{file.filename.rsplit('.',1)[1].lower()}"
            upload_dir = os.path.join(current_app.static_folder, 'uploads', 'fotos')
            os.makedirs(upload_dir, exist_ok=True)
            file.save(os.path.join(upload_dir, filename))
            repo.actualizar_imagen_paciente(pid, f"uploads/fotos/{filename}")
        flash('Paciente actualizado.', 'success')
    except Exception as e:
        _flash_error(e)
    return redirect(url_for('admin.pacientes'))


@admin_bp.route('/admin/pacientes/<int:pid>/historial')
def historial_paciente(pid):
    redir = _require_admin()
    if redir:
        return redir
    paciente = repo.obtener_paciente(pid)
    if not paciente:
        flash('Paciente no encontrado.', 'error')
        return redirect(url_for('admin.pacientes'))
    aplicaciones = repo.aplicaciones_de_paciente(pid)
    return render_template('admin/historial_paciente.html',
                           paciente=paciente,
                           aplicaciones=aplicaciones)


@admin_bp.route('/admin/pacientes/<int:pid>/eliminar', methods=['POST'])
def eliminar_paciente(pid):
    redir = _require_admin()
    if redir:
        return redir
    try:
        repo.eliminar_paciente(pid)
        flash('Paciente eliminado.', 'success')
    except Exception as e:
        _flash_error(e)
    return redirect(url_for('admin.pacientes'))


@admin_bp.route('/admin/relaciones', methods=['GET', 'POST'])
def relaciones():
    redir = _require_admin()
    if redir:
        return redir
    if request.method == 'POST':
        f = request.form
        try:
            pid = _get_int(f, 'paciente_id', 'paciente', required=True)
            tid = _get_int(f, 'tutor_id',    'tutor',    required=True)
            pac = repo.obtener_paciente(pid)
            tut = repo.obtener_tutor(tid)
            if not pac:
                raise FormError('El paciente seleccionado no existe.')
            if not tut:
                raise FormError('El tutor seleccionado no existe.')
            pac_nombre = f"{pac['paciente_prim_nombre']} {pac['paciente_apellido_pat']}"
            tut_nombre = f"{tut['tutor_prim_nombre']} {tut['tutor_apellido_pat']}"
            repo.crear_relacion(pid, tid, pac_nombre, tut_nombre)
            flash('Relación registrada.', 'success')
        except Exception as e:
            _flash_error(e)
        return redirect(url_for('admin.relaciones'))
    pacientes_list = repo.listar_pacientes()
    tutores_list   = repo.listar_tutores()
    pacientes_json = _json.dumps([{
        'id': p['paciente_id'],
        'nombre': f"{p['paciente_prim_nombre'].title()} {p['paciente_apellido_pat'].title()}",
        'curp': p.get('paciente_curp') or '',
        'cert': p.get('paciente_num_cert_nac') or '',
    } for p in pacientes_list])
    tutores_json = _json.dumps([{
        'id': t['tutor_id'],
        'nombre': f"{t['tutor_prim_nombre'].title()} {t['tutor_apellido_pat'].title()}",
        'curp': t.get('tutor_curp') or '',
        'email': t.get('tutor_email') or '',
    } for t in tutores_list])
    return render_template('admin/relaciones.html',
                           relaciones=repo.listar_relaciones(),
                           pacientes_json=pacientes_json,
                           tutores_json=tutores_json)


@admin_bp.route('/admin/relaciones/<int:rid>/eliminar', methods=['POST'])
def eliminar_relacion(rid):
    redir = _require_admin()
    if redir:
        return redir
    try:
        repo.eliminar_relacion(rid)
        flash('Relación eliminada.', 'success')
    except Exception as e:
        _flash_error(e)
    return redirect(url_for('admin.relaciones'))


@admin_bp.route('/admin/centros', methods=['GET', 'POST'])
def centros():
    redir = _require_admin()
    if redir:
        return redir
    if request.method == 'POST':
        f = request.form
        try:
            h_ini = _get_time_safe(f, 'horario_inicio', 'horario de inicio')
            h_fin = _get_time_safe(f, 'horario_fin',    'horario de fin')
            if h_ini and h_fin and h_fin <= h_ini:
                raise FormError('El horario de fin debe ser posterior al horario de inicio.')
            lat = _get_decimal(f, 'latitud',  'latitud')
            lon = _get_decimal(f, 'longitud', 'longitud')
            if lat is not None and (lat < -90 or lat > 90):
                raise FormError('La latitud debe estar entre -90 y 90.')
            if lon is not None and (lon < -180 or lon > 180):
                raise FormError('La longitud debe estar entre -180 y 180.')
            datos = {
                'centro_nombre':         _get_str(f, 'nombre', 'nombre del centro', required=True),
                'centro_calle':          _get_str(f, 'calle', 'calle'),
                'centro_numero':         _get_str(f, 'numero', 'número'),
                'centro_codigo_postal':  _get_str(f, 'cp', 'código postal',
                                                 pattern=r'\d{5}', pattern_msg='El código postal debe contener exactamente 5 dígitos.'),
                'ciudad_id':             _get_int(f, 'ciudad_id', 'ciudad', required=True),
                'centro_horario_inicio': h_ini,
                'centro_horario_fin':    h_fin,
                'centro_latitud':        lat,
                'centro_longitud':       lon,
                'centro_telefono':       _get_str(f, 'telefono', 'teléfono', required=True,
                                                 pattern=_TEL_RE, pattern_msg='El teléfono debe contener exactamente 10 dígitos.'),
                'centro_beacon':         _get_str(f, 'beacon', 'beacon'),
            }
            repo.crear_centro(datos)
            flash('Centro de salud registrado.', 'success')
        except Exception as e:
            _flash_error(e)
        return redirect(url_for('admin.centros'))
    return render_template('admin/centros.html',
                           centros=repo.listar_centros(),
                           ciudades=repo.listar_ciudades())


@admin_bp.route('/admin/centros/<int:cid>/editar', methods=['POST'])
def editar_centro(cid):
    redir = _require_admin()
    if redir:
        return redir
    f = request.form
    try:
        h_ini = _get_time_safe(f, 'horario_inicio', 'horario de inicio')
        h_fin = _get_time_safe(f, 'horario_fin',    'horario de fin')
        if h_ini and h_fin and h_fin <= h_ini:
            raise FormError('El horario de fin debe ser posterior al horario de inicio.')
        lat = _get_decimal(f, 'latitud',  'latitud')
        lon = _get_decimal(f, 'longitud', 'longitud')
        if lat is not None and (lat < -90 or lat > 90):
            raise FormError('La latitud debe estar entre -90 y 90.')
        if lon is not None and (lon < -180 or lon > 180):
            raise FormError('La longitud debe estar entre -180 y 180.')
        campos = {
            'centro_nombre':         _get_str(f, 'nombre', 'nombre del centro', required=True),
            'centro_calle':          _get_str(f, 'calle', 'calle'),
            'centro_numero':         _get_str(f, 'numero', 'número'),
            'centro_codigo_postal':  _get_str(f, 'cp', 'código postal'),
            'ciudad_id':             _get_int(f, 'ciudad_id', 'ciudad', required=True),
            'centro_horario_inicio': h_ini,
            'centro_horario_fin':    h_fin,
            'centro_latitud':        lat,
            'centro_longitud':       lon,
            'centro_telefono':       _get_str(f, 'telefono', 'teléfono'),
            'centro_beacon':         _get_str(f, 'beacon', 'beacon'),
        }
        repo.actualizar_centro(cid, campos)
        flash('Centro de salud actualizado.', 'success')
    except Exception as e:
        _flash_error(e)
    return redirect(url_for('admin.centros'))


@admin_bp.route('/admin/centros/<int:cid>/eliminar', methods=['POST'])
def eliminar_centro(cid):
    redir = _require_admin()
    if redir:
        return redir
    try:
        repo.eliminar_centro(cid)
        flash('Centro eliminado.', 'success')
    except Exception as e:
        _flash_error(e)
    return redirect(url_for('admin.centros'))


@admin_bp.route('/admin/esquemas', methods=['GET', 'POST'])
def esquemas():
    redir = _require_admin()
    if redir:
        return redir

    if request.method == 'POST':
        f = request.form
        try:
            nombre         = _get_str(f, 'nombre', 'nombre del esquema', required=True)
            fecha_vigencia = _get_date(f, 'fecha_vigencia', 'fecha de vigencia', required=True)
            esquema_anterior_id = f.get('esquema_anterior_id', type=int)
            dosis_seleccionadas = set(f.getlist('dosis_ids', type=int))

            nuevas_vacunas    = f.getlist('nueva_vacuna_id',      type=int)
            nuevas_tipos      = f.getlist('nueva_tipo')
            nuevas_ml         = f.getlist('nueva_cant_ml')
            nuevas_areas      = f.getlist('nueva_area')
            nuevas_edades     = f.getlist('nueva_edad_dias',      type=int)
            nuevas_intervalos = f.getlist('nueva_intervalo_dias', type=int)
            nuevas_limites    = f.getlist('nueva_limite_dias')

            nuevo    = repo.crear_esquema({'esquema_nombre': nombre,
                                           'esquema_fecha_vigencia': fecha_vigencia,
                                           'vigente_desde': date.today()})
            nuevo_id = nuevo['esquema_id']

            for i, vacuna_id in enumerate(nuevas_vacunas):
                if not vacuna_id:
                    continue
                limite_raw = nuevas_limites[i] if i < len(nuevas_limites) else ''
                ml_raw = nuevas_ml[i] if i < len(nuevas_ml) else ''
                try:
                    ml_val = float(str(ml_raw).replace(',', '.')) if ml_raw else 0.5
                except (ValueError, TypeError):
                    raise FormError(f'La cantidad en ml de la fila {i+1} no es un número válido.')
                try:
                    limite_val = int(limite_raw) if limite_raw else None
                except (ValueError, TypeError):
                    raise FormError(f'El límite de edad de la fila {i+1} no es un número válido.')
                d = repo.crear_dosis({
                    'vacuna_id':                vacuna_id,
                    'dosis_tipo':               nuevas_tipos[i] if i < len(nuevas_tipos) else 'UNICA',
                    'dosis_cant_ml':            ml_val,
                    'dosis_area_aplicacion':    nuevas_areas[i] if i < len(nuevas_areas) else '',
                    'dosis_edad_oportuna_dias': nuevas_edades[i] if i < len(nuevas_edades) else 0,
                    'dosis_intervalo_min_dias': nuevas_intervalos[i] if i < len(nuevas_intervalos) else 0,
                    'dosis_limite_edad_dias':   limite_val,
                })
                repo.agregar_dosis_a_esquema(nuevo_id, d['dosis_id'])

            for dosis_id in dosis_seleccionadas:
                repo.agregar_dosis_a_esquema(nuevo_id, dosis_id)

            if esquema_anterior_id:
                dosis_antiguas = repo.dosis_de_esquema(esquema_anterior_id)
                for d in dosis_antiguas:
                    if d['dosis_id'] not in dosis_seleccionadas:
                        repo.desactivar_dosis(d['dosis_id'])
                repo.cerrar_esquema(esquema_anterior_id)
                r = repo.asignar_esquema_auto(esquema_anterior_id, nuevo_id) or {}
                msg = r.get('p_msg') if isinstance(r, dict) else ''
                flash(f'Esquema publicado. {msg}', 'success')
            else:
                flash('Esquema creado correctamente.', 'success')

        except Exception as e:
            _flash_error(e)

        return redirect(url_for('admin.esquemas'))

    esquemas_list = repo.listar_esquemas()
    for e in esquemas_list:
        e['total_dosis'] = len(repo.dosis_de_esquema(e['esquema_id']))

    esquema_actual = next(
        (e for e in esquemas_list if not e.get('esquema_vigente_hasta')), None
    )
    dosis_esquema_actual_ids = set()
    if esquema_actual:
        dosis_esquema_actual_ids = {
            d['dosis_id'] for d in repo.dosis_de_esquema(esquema_actual['esquema_id'])
        }

    conflictos_raw = repo.listar_conflictos_esquema()
    conflictos = {}
    for c in conflictos_raw:
        pid = c['paciente_id']
        if pid not in conflictos:
            conflictos[pid] = {
                'paciente_id':           pid,
                'nombre_display':        f"{c['paciente_prim_nombre']} {c['paciente_apellido_pat']}",
                'esquema_nuevo_id':      c['esquema_nuevo_id'],
                'esquema_nuevo_nombre':  c['esquema_nuevo_nombre'],
                'esquema_actual_nombre': c.get('esquema_actual_nombre', ''),
                'dosis': [],
            }
        conflictos[pid]['dosis'].append({
            'dosis_id':      c['dosis_conflicto_id'],
            'vacuna_nombre': c['vacuna_nombre'],
            'dosis_tipo':    c['dosis_tipo'],
            'edad_dias':     c.get('dosis_edad_oportuna_dias'),
            'limite_dias':   c.get('dosis_limite_edad_dias'),
        })

    return render_template('admin/esquemas.html',
                           esquemas=esquemas_list,
                           esquema_actual=esquema_actual,
                           dosis_list=repo.listar_dosis_activas(),
                           dosis_esquema_actual_ids=dosis_esquema_actual_ids,
                           vacunas=repo.listar_vacunas(),
                           conflictos=list(conflictos.values()),
                           days_to_human=days_to_human,
                           DOSIS_TIPOS=DOSIS_TIPOS)


@admin_bp.route('/admin/esquemas/<int:eid>/eliminar', methods=['POST'])
def eliminar_esquema(eid):
    redir = _require_admin()
    if redir:
        return redir
    try:
        repo.eliminar_esquema(eid)
        flash('Esquema eliminado.', 'success')
    except Exception as e:
        _flash_error(e)
    return redirect(url_for('admin.esquemas'))


@admin_bp.route('/admin/esquemas/conflicto/resolver', methods=['POST'])
def resolver_conflicto_esquema():
    redir = _require_admin()
    if redir:
        return redir
    try:
        paciente_id      = _get_int(request.form, 'paciente_id',      'paciente',      required=True)
        esquema_nuevo_id = _get_int(request.form, 'esquema_nuevo_id', 'esquema nuevo', required=True)
        accion           = _get_str(request.form, 'accion', 'acción', required=True)
        if accion not in ('actualizar', 'mantener'):
            raise FormError('La acción seleccionada no es válida.')
        r = repo.resolver_conflicto_esquema(paciente_id, esquema_nuevo_id, accion) or {}
        if r.get('p_ok') == 1:
            flash(r.get('p_msg', 'Conflicto resuelto.'), 'success')
        else:
            flash(r.get('p_msg', 'No se pudo resolver el conflicto.'), 'error')
    except Exception as e:
        _flash_error(e)
    return redirect(url_for('admin.esquemas') + '#tab-conflictos')


@admin_bp.route('/admin/vacunas', methods=['GET', 'POST'])
def vacunas():
    redir = _require_admin()
    if redir:
        return redir
    if request.method == 'POST':
        try:
            nombre = _get_str(request.form, 'nombre', 'nombre de la vacuna', required=True, max_len=100)
            repo.crear_vacuna({'vacuna_nombre': nombre})
            flash('Vacuna registrada.', 'success')
        except Exception as e:
            _flash_error(e)
        return redirect(url_for('admin.vacunas'))

    # vacunas en esquema actual
    esquemas_list = repo.listar_esquemas()
    esquema_actual = next((e for e in esquemas_list if not e.get('esquema_vigente_hasta')), None)
    todas_dosis = repo.listar_dosis()
    vacunas_en_esquema: set[int] = set()
    if esquema_actual:
        dosis_ids = {d['dosis_id'] for d in repo.dosis_de_esquema(esquema_actual['esquema_id'])}
        vacunas_en_esquema = {d['vacuna_id'] for d in todas_dosis if d['dosis_id'] in dosis_ids}

    # padecimientos por vacuna
    pads_por_vacuna: dict[int, list[str]] = {}
    for pad in repo.listar_padecimientos():
        for vid in repo.vacunas_de_padecimiento(pad['padecimiento_id']):
            pads_por_vacuna.setdefault(vid, []).append(pad['padecimiento_nombre'])

    vacunas_list = []
    for v in repo.listar_vacunas():
        v2 = dict(v)
        v2['en_esquema'] = v['vacuna_id'] in vacunas_en_esquema
        v2['padecimientos'] = pads_por_vacuna.get(v['vacuna_id'], [])
        vacunas_list.append(v2)
    return render_template('admin/vacunas.html',
                           vacunas=vacunas_list)


@admin_bp.route('/admin/vacunas/<int:vid>/editar', methods=['POST'])
def editar_vacuna(vid):
    redir = _require_admin()
    if redir:
        return redir
    try:
        nombre = _get_str(request.form, 'nombre', 'nombre de la vacuna', required=True, max_len=100)
        repo.actualizar_vacuna(vid, {'vacuna_nombre': nombre})
        flash('Vacuna actualizada.', 'success')
    except Exception as e:
        _flash_error(e)
    return redirect(url_for('admin.vacunas'))


@admin_bp.route('/admin/vacunas/<int:vid>/eliminar', methods=['POST'])
def eliminar_vacuna(vid):
    redir = _require_admin()
    if redir:
        return redir
    try:
        repo.eliminar_vacuna(vid)
        flash('Vacuna eliminada.', 'success')
    except Exception as e:
        _flash_error(e)
    return redirect(url_for('admin.vacunas'))


@admin_bp.route('/admin/api/vacuna/<int:vid>/dosis')
def api_vacuna_dosis(vid):
    return jsonify(repo.listar_dosis(vacuna_id=vid))


@admin_bp.route('/admin/api/inventarios-para-dosis/<int:dosis_id>')
def api_admin_inventarios_para_dosis(dosis_id):
    redir = _require_admin()
    if redir:
        return jsonify([]), 401
    dosis = repo.obtener_dosis(dosis_id)
    if not dosis:
        return jsonify([])
    invs = repo.inventarios_disponibles_para_vacuna(dosis['vacuna_id'])
    return jsonify([{
        'inventario_id':    inv['inventario_id'],
        'lote_codigo':      inv.get('lote_codigo', ''),
        'vacuna_nombre':    inv.get('vacuna_nombre', ''),
        'stock':            inv.get('inventario_stock_actual', 0),
        'centro_nombre':    inv.get('centro_nombre', ''),
        'lote_caducidad':   str(inv['lote_fecha_caducidad']) if inv.get('lote_fecha_caducidad') else None,
    } for inv in invs])


@admin_bp.route('/admin/padecimientos', methods=['GET', 'POST'])
def padecimientos():
    redir = _require_admin()
    if redir:
        return redir
    if request.method == 'POST':
        f = request.form
        try:
            nuevo = repo.crear_padecimiento({
                'padecimiento_nombre':      _get_str(f, 'nombre', 'nombre del padecimiento', required=True, max_len=100),
                'padecimiento_descripcion': _get_str(f, 'descripcion', 'descripción'),
            })
            for vid in f.getlist('vacuna_ids'):
                try:
                    repo.vincular_vacuna_padecimiento(int(vid), nuevo['padecimiento_id'])
                except (ValueError, TypeError):
                    continue
            flash('Padecimiento registrado.', 'success')
        except Exception as e:
            _flash_error(e)
        return redirect(url_for('admin.padecimientos'))
    pads = repo.listar_padecimientos()
    vacunas_por_padecimiento = {
        p['padecimiento_id']: set(repo.vacunas_de_padecimiento(p['padecimiento_id']))
        for p in pads
    }
    return render_template('admin/padecimientos.html',
                           padecimientos=pads,
                           vacunas=repo.listar_vacunas(),
                           vacunas_por_padecimiento=vacunas_por_padecimiento)


@admin_bp.route('/admin/padecimientos/<int:pid>/editar', methods=['POST'])
def editar_padecimiento(pid):
    redir = _require_admin()
    if redir:
        return redir
    f = request.form
    try:
        campos = {
            'padecimiento_nombre':      _get_str(f, 'nombre', 'nombre del padecimiento', required=True, max_len=100),
            'padecimiento_descripcion': _get_str(f, 'descripcion', 'descripción'),
        }
        repo.actualizar_padecimiento(pid, campos)
        repo.sincronizar_vacunas_padecimiento(pid, [int(v) for v in f.getlist('vacuna_ids') if v.isdigit()])
        flash('Padecimiento actualizado.', 'success')
    except Exception as e:
        _flash_error(e)
    return redirect(url_for('admin.padecimientos'))


@admin_bp.route('/admin/padecimientos/<int:pid>/eliminar', methods=['POST'])
def eliminar_padecimiento(pid):
    redir = _require_admin()
    if redir:
        return redir
    try:
        repo.eliminar_padecimiento(pid)
        flash('Padecimiento eliminado.', 'success')
    except Exception as e:
        _flash_error(e)
    return redirect(url_for('admin.padecimientos'))


@admin_bp.route('/admin/fabricantes', methods=['GET', 'POST'])
def fabricantes():
    redir = _require_admin()
    if redir:
        return redir
    if request.method == 'POST':
        f      = request.form
        accion = f.get('accion', 'fabricante')
        try:
            if accion == 'proveedor':
                repo.crear_proveedor({
                    'proveedor_prim_nombre':  _get_str(f, 'prim_nombre',  'primer nombre',  required=True),
                    'proveedor_seg_nombre':   _get_str(f, 'seg_nombre',   'segundo nombre'),
                    'proveedor_apellido_pat': _get_str(f, 'apellido_pat', 'apellido paterno', required=True),
                    'proveedor_apellido_mat': _get_str(f, 'apellido_mat', 'apellido materno'),
                    'proveedor_email':        _get_str(f, 'email',     'correo electrónico', lower=True),
                    'proveedor_telefono':     _get_str(f, 'telefono',  'teléfono'),
                    'proveedor_empresa':      _get_str(f, 'empresa',   'empresa'),
                    'fabricante_id':          _get_int(f, 'fabricante_id', 'fabricante', required=True),
                })
                flash('Proveedor registrado correctamente.', 'success')
            elif accion == 'fabricante':
                repo.crear_fabricante({
                    'fabricante_nombre':   _get_str(f, 'nombre', 'nombre del fabricante', required=True),
                    'pais_id':             _get_int(f, 'pais_id', 'país', required=True),
                    'fabricante_telefono': _get_str(f, 'telefono', 'teléfono'),
                })
                flash('Fabricante registrado.', 'success')
            else:
                raise FormError('Acción inválida.')
        except Exception as e:
            _flash_error(e)
        return redirect(url_for('admin.fabricantes'))
    return render_template('admin/fabricantes.html',
                           fabricantes=repo.listar_fabricantes(),
                           proveedores=repo.listar_proveedores(),
                           paises=repo.listar_paises())


@admin_bp.route('/admin/fabricantes/<int:fid>/editar', methods=['POST'])
def editar_fabricante(fid):
    redir = _require_admin()
    if redir:
        return redir
    f = request.form
    try:
        campos = {
            'fabricante_nombre':   _get_str(f, 'nombre', 'nombre del fabricante', required=True),
            'pais_id':             _get_int(f, 'pais_id', 'país', required=True),
            'fabricante_telefono': _get_str(f, 'telefono', 'teléfono'),
        }
        repo.actualizar_fabricante(fid, campos)
        flash('Fabricante actualizado.', 'success')
    except Exception as e:
        _flash_error(e)
    return redirect(url_for('admin.fabricantes'))


@admin_bp.route('/admin/fabricantes/<int:fid>/eliminar', methods=['POST'])
def eliminar_fabricante(fid):
    redir = _require_admin()
    if redir:
        return redir
    try:
        repo.eliminar_fabricante(fid)
        flash('Fabricante eliminado.', 'success')
    except Exception as e:
        _flash_error(e)
    return redirect(url_for('admin.fabricantes'))


@admin_bp.route('/admin/proveedores/<int:pid>/editar', methods=['POST'])
def editar_proveedor(pid):
    redir = _require_admin()
    if redir:
        return redir
    f = request.form
    try:
        campos = {
            'proveedor_prim_nombre':  _get_str(f, 'prim_nombre',  'primer nombre',  required=True),
            'proveedor_seg_nombre':   _get_str(f, 'seg_nombre',   'segundo nombre'),
            'proveedor_apellido_pat': _get_str(f, 'apellido_pat', 'apellido paterno', required=True),
            'proveedor_apellido_mat': _get_str(f, 'apellido_mat', 'apellido materno'),
            'proveedor_email':        _get_str(f, 'email',     'correo electrónico', lower=True),
            'proveedor_telefono':     _get_str(f, 'telefono',  'teléfono'),
            'proveedor_empresa':      _get_str(f, 'empresa',   'empresa'),
            'fabricante_id':          _get_int(f, 'fabricante_id', 'fabricante', required=True),
        }
        repo.actualizar_proveedor(pid, campos)
        flash('Proveedor actualizado.', 'success')
    except Exception as e:
        _flash_error(e)
    return redirect(url_for('admin.fabricantes'))


@admin_bp.route('/admin/proveedores/<int:pid>/eliminar', methods=['POST'])
def eliminar_proveedor(pid):
    redir = _require_admin()
    if redir:
        return redir
    try:
        repo.eliminar_proveedor(pid)
        flash('Proveedor eliminado.', 'success')
    except Exception as e:
        _flash_error(e)
    return redirect(url_for('admin.fabricantes'))


@admin_bp.route('/admin/lotes', methods=['GET', 'POST'])
def lotes():
    redir = _require_admin()
    if redir:
        return redir
    if request.method == 'POST':
        accion = request.form.get('accion')
        f      = request.form

        if accion == 'nuevo_lote':
            try:
                fecha_fab = _get_date(f, 'fecha_fab', 'fecha de fabricación', required=True)
                fecha_cad = _get_date(f, 'fecha_cad', 'fecha de caducidad',  required=True)
                if fecha_cad <= fecha_fab:
                    raise FormError('La fecha de caducidad debe ser posterior a la fecha de fabricación.')
                cantidad = _get_int(f, 'cantidad', 'cantidad', required=True, min_value=1)
                repo.crear_lote({
                    'lote_codigo':            _get_str(f, 'codigo', 'código del lote', required=True, max_len=50),
                    'lote_fecha_fabricacion': fecha_fab,
                    'lote_fecha_caducidad':   fecha_cad,
                    'lote_cant_inicial':      cantidad,
                    'vacuna_id':              _get_int(f, 'vacuna_id', 'vacuna', required=True),
                    'fabricante_id':          _get_int(f, 'fabricante_id', 'fabricante', required=True),
                    'proveedor_id':           _get_int(f, 'proveedor_id', 'proveedor', required=True),
                })
                flash('Lote registrado.', 'success')
            except Exception as e:
                _flash_error(e)

        elif accion == 'asignar_inventario':
            try:
                centro_id_inv = _get_int(f, 'centro_id', 'centro de salud', required=True)
                lote_id_inv   = _get_int(f, 'lote_id',   'lote',            required=True)
                stock_inv     = _get_int(f, 'stock',     'stock',           required=True, min_value=1)
                result_inv = repo.asignar_inventario({
                    'centro_id':               centro_id_inv,
                    'lote_id':                 lote_id_inv,
                    'inventario_stock_inicial': stock_inv,
                    'inventario_stock_actual':  stock_inv,
                    'inventario_activo_desde':  None,
                })
                centros_map = {c['centro_id']: c['centro_nombre'] for c in repo.listar_centros()}
                vacunas_map = {v['vacuna_id']: v['vacuna_nombre'] for v in repo.listar_vacunas()}
                lote_obj    = repo.obtener_lote(lote_id_inv)
                try:
                    mdb.log_inventario(
                        evento='asignacion',
                        pg_inventario_id=result_inv.get('p_id') if result_inv else None,
                        pg_centro_id=centro_id_inv,
                        pg_lote_id=lote_id_inv,
                        pg_usuario_id=session.get('user_id'),
                        vacuna_nombre=vacunas_map.get(lote_obj['vacuna_id'], '—') if lote_obj else '—',
                        centro_nombre=centros_map.get(centro_id_inv, '—'),
                        stock=stock_inv,
                    )
                except Exception:
                    pass
                flash('Inventario asignado. El responsable del centro debe confirmar su recepción.', 'success')
            except Exception as e:
                _flash_error(e)
        else:
            flash('Acción no reconocida.', 'error')

        return redirect(url_for('admin.lotes'))

    return render_template('admin/lotes.html',
                           lotes=repo.listar_lotes(),
                           inventarios=repo.listar_inventarios(),
                           vacunas=repo.listar_vacunas(),
                           fabricantes=repo.listar_fabricantes(),
                           proveedores=repo.listar_proveedores(),
                           centros=repo.listar_centros())


@admin_bp.route('/admin/lotes/<int:lid>/editar', methods=['POST'])
def editar_lote(lid):
    redir = _require_admin()
    if redir:
        return redir
    f = request.form
    try:
        fecha_fab = _get_date(f, 'fecha_fab', 'fecha de fabricación', required=True)
        fecha_cad = _get_date(f, 'fecha_cad', 'fecha de caducidad',  required=True)
        if fecha_cad <= fecha_fab:
            raise FormError('La fecha de caducidad debe ser posterior a la fecha de fabricación.')
        campos = {
            'lote_codigo':            _get_str(f, 'codigo', 'código del lote', required=True, max_len=50),
            'lote_fecha_fabricacion': fecha_fab,
            'lote_fecha_caducidad':   fecha_cad,
            'lote_cant_inicial':      _get_int(f, 'cantidad', 'cantidad', required=True, min_value=1),
            'vacuna_id':              _get_int(f, 'vacuna_id', 'vacuna', required=True),
            'fabricante_id':          _get_int(f, 'fabricante_id', 'fabricante', required=True),
            'proveedor_id':           _get_int(f, 'proveedor_id', 'proveedor', required=True),
        }
        repo.actualizar_lote(lid, campos)
        flash('Lote actualizado.', 'success')
    except Exception as e:
        _flash_error(e)
    return redirect(url_for('admin.lotes'))


@admin_bp.route('/admin/lotes/<int:lid>/eliminar', methods=['POST'])
def eliminar_lote(lid):
    redir = _require_admin()
    if redir:
        return redir
    try:
        repo.eliminar_lote(lid)
        flash('Lote eliminado.', 'success')
    except Exception as e:
        _flash_error(e)
    return redirect(url_for('admin.lotes'))


@admin_bp.route('/admin/inventario', methods=['GET', 'POST'])
def inventario():
    redir = _require_admin()
    if redir:
        return redir
    if request.method == 'POST':
        f = request.form
        try:
            inv_origen_id    = _get_int(f, 'inv_origen_id',    'inventario de origen', required=True)
            centro_destino_id = _get_int(f, 'centro_destino_id', 'centro destino',     required=True)
            cantidad         = _get_int(f, 'cantidad',         'cantidad a transferir', required=True, min_value=1)
            inv_origen = repo.obtener_inventario(inv_origen_id)
            if not inv_origen:
                raise FormError('El inventario de origen no existe.')
            if inv_origen.get('centro_id') == centro_destino_id:
                raise FormError('El centro de origen y destino no pueden ser el mismo.')
            r = repo.transferir_inventario(inv_origen_id, centro_destino_id, cantidad) or {}
            if r.get('p_ok') == 1:
                flash(r.get('p_msg', 'Transferencia realizada.'), 'success')
            else:
                flash(r.get('p_msg', 'No se pudo realizar la transferencia.'), 'error')
        except Exception as e:
            _flash_error(e)
        return redirect(url_for('admin.inventario'))

    repo.recalcular_alertas_inventario()
    repo.recalcular_alertas_dosis()
    return render_template('admin/inventario.html',
                           inventarios=repo.listar_inventarios(),
                           transferencias=repo.listar_transferencias(),
                           centros=repo.listar_centros(),
                           alertas_inv=repo.listar_alertas_inventario(),
                           alertas_dosis=repo.listar_alertas_dosis(),
                           today=date.today())


@admin_bp.route('/admin/inventario/<int:iid>/editar', methods=['POST'])
def editar_inventario(iid):
    redir = _require_admin()
    if redir:
        return redir
    f = request.form
    try:
        stock_actual = _get_int(f, 'stock_actual', 'stock actual', required=True, min_value=0)
        activo       = 1 if (f.get('activo') in ('1', 'on', 'true', 'yes')) else 0
        campos = {
            'inventario_stock_actual': stock_actual,
            'inventario_activo':       activo,
        }
        repo.actualizar_inventario(iid, campos)
        flash('Inventario actualizado.', 'success')
    except Exception as e:
        _flash_error(e)
    return redirect(url_for('admin.inventario'))


@admin_bp.route('/admin/inventario/<int:iid>/eliminar', methods=['POST'])
def eliminar_inventario(iid):
    redir = _require_admin()
    if redir:
        return redir
    try:
        repo.eliminar_inventario(iid)
        flash('Registro de inventario eliminado.', 'success')
    except Exception as e:
        _flash_error(e)
    return redirect(url_for('admin.inventario'))


@admin_bp.route('/admin/api/inventarios-activos-centro/<int:centro_id>')
def api_inventarios_activos_centro(centro_id):
    redir = _require_admin()
    if redir:
        return jsonify([]), 401
    invs = repo.inventarios_activos_de_centro(centro_id)
    for inv in invs:
        for k in ('inventario_activo_desde', 'lote_fecha_fabricacion', 'lote_fecha_caducidad'):
            if inv.get(k) is not None:
                inv[k] = str(inv[k])
        for k in ('inventario_id', 'inventario_stock_inicial', 'inventario_stock_actual',
                  'lote_id', 'vacuna_id', 'centro_id'):
            if inv.get(k) is not None:
                inv[k] = int(inv[k])
    return jsonify(invs)


@admin_bp.route('/admin/aplicaciones', methods=['GET', 'POST'])
def aplicaciones():
    redir = _require_admin()
    if redir:
        return redir
    if request.method == 'POST':
        f = request.form
        try:
            pid         = _get_int(f, 'paciente_id',   'paciente',        required=True)
            did         = _get_int(f, 'dosis_id',      'dosis',           required=True)
            resp_id     = _get_int(f, 'responsable_id', 'responsable',    required=True)
            centro_id   = _get_int(f, 'centro_id',     'centro de salud', required=True)
            lote_codigo = _get_str(f, 'lote_codigo',   'código de lote',  required=True).upper()

            inventarios_centro = repo.inventarios_activos_de_centro(centro_id)
            inv = next((i for i in inventarios_centro
                        if i.get('lote_codigo', '').upper() == lote_codigo), None)
            if not inv:
                raise FormError(
                    f'No se encontró el lote "{lote_codigo}" con stock disponible en el centro seleccionado.'
                )

            cad = inv.get('lote_fecha_caducidad')
            if cad and isinstance(cad, date) and cad < date.today():
                raise FormError(
                    f'El lote caducó el {cad.strftime("%d/%m/%Y")}. No se puede aplicar una vacuna caducada.'
                )

            if repo.dosis_ya_aplicada(pid, did):
                repo.registrar_alerta_dosis(pid, did, 'FALTANTE')
                raise FormError('Esta dosis ya fue aplicada anteriormente a este paciente.')

            pac = repo.obtener_paciente(pid)
            dos = repo.obtener_dosis(did)
            if not pac:
                raise FormError('El paciente seleccionado no existe.')
            if not dos:
                raise FormError('La dosis seleccionada no existe.')

            aplicaciones_previas = repo.aplicaciones_de_paciente(pid)
            ok, error_msg = validar_aplicacion(pac, dos, aplicaciones_previas)
            if not ok:
                tipo_alerta = 'ATRASADA' if 'límite' in (error_msg or '').lower() else 'FALTANTE'
                repo.registrar_alerta_dosis(pid, did, tipo_alerta)
                raise FormError(error_msg)

            datos = {
                'paciente_id':              pid,
                'usuario_id':               resp_id,
                'centro_id':                inv['centro_id'],
                'lote_id':                  inv['lote_id'],
                'dosis_id':                 did,
                'aplicacion_observaciones': _get_str(f, 'observaciones', 'observaciones') or '',
            }
            result = repo.registrar_aplicacion(datos)
            try:
                mdb.log_aplicacion(
                    pg_aplicacion_id=result.get('p_id') if result else None,
                    pg_paciente_id=pid,
                    pg_usuario_id=resp_id,
                    pg_centro_id=inv['centro_id'],
                    pg_lote_id=inv['lote_id'],
                    pg_dosis_id=did,
                    vacuna_nombre=dos.get('vacuna_nombre', '—'),
                    paciente_nombre=f"{pac['paciente_prim_nombre']} {pac['paciente_apellido_pat']}",
                    responsable_nombre=session.get('user_name', '—'),
                    centro_nombre=inv.get('centro_nombre', '—'),
                    observaciones=datos['aplicacion_observaciones'] or None,
                )
            except Exception:
                pass
            flash('Aplicación registrada.', 'success')
        except Exception as e:
            _flash_error(e)
        return redirect(url_for('admin.aplicaciones'))

    todas_dosis = repo.listar_dosis()
    vacunas     = {v['vacuna_id']: v['vacuna_nombre'] for v in repo.listar_vacunas()}
    dosis_list  = []
    for d in todas_dosis:
        d2 = dict(d)
        if 'vacuna_nombre' not in d2:
            d2['vacuna_nombre'] = vacunas.get(d2['vacuna_id'], '—')
        dosis_list.append(d2)

    return render_template('admin/aplicaciones.html',
                           aplicaciones=repo.listar_aplicaciones(),
                           pacientes=repo.listar_pacientes(),
                           responsables=repo.listar_responsables(),
                           centros=repo.listar_centros(),
                           dosis_list=dosis_list)


@admin_bp.route('/admin/aplicaciones/<int:aid>/editar', methods=['POST'])
def editar_aplicacion(aid):
    redir = _require_admin()
    if redir:
        return redir
    f = request.form
    try:
        campos = {
            'aplicacion_observaciones': _get_str(f, 'observaciones', 'observaciones') or '',
        }
        repo.actualizar_aplicacion(aid, campos)
        flash('Aplicación actualizada.', 'success')
    except Exception as e:
        _flash_error(e)
    return redirect(url_for('admin.aplicaciones'))


@admin_bp.route('/admin/aplicaciones/<int:aid>/anular', methods=['POST'])
def anular_aplicacion(aid):
    redir = _require_admin()
    if redir:
        return redir
    try:
        motivo = _get_str(request.form, 'motivo', 'motivo de anulación') or 'Anulada por administrador'
        repo.anular_aplicacion(aid, motivo)
        flash('Aplicación anulada. El stock fue restaurado.', 'success')
    except Exception as e:
        _flash_error(e)
    return redirect(url_for('admin.aplicaciones'))


@admin_bp.route('/admin/geografia', methods=['GET', 'POST'])
def geografia():
    redir = _require_admin()
    if redir:
        return redir
    if request.method == 'POST':
        accion = request.form.get('accion')
        f      = request.form
        try:
            if accion == 'pais':
                nombre = _get_str(f, 'nombre', 'nombre del país', required=True, max_len=80)
                repo.crear_pais(nombre)
                flash('País registrado.', 'success')
            elif accion == 'estado':
                repo.crear_estado({
                    'estado_nombre': _get_str(f, 'nombre', 'nombre del estado', required=True, max_len=80),
                    'pais_id':       _get_int(f, 'pais_id', 'país', required=True),
                })
                flash('Estado registrado.', 'success')
            elif accion == 'ciudad':
                repo.crear_ciudad({
                    'ciudad_nombre': _get_str(f, 'nombre', 'nombre de la ciudad', required=True, max_len=80),
                    'estado_id':     _get_int(f, 'estado_id', 'estado', required=True),
                })
                flash('Ciudad registrada.', 'success')
            else:
                raise FormError('Acción no reconocida.')
        except Exception as e:
            _flash_error(e)
        return redirect(url_for('admin.geografia'))
    return render_template('admin/geografia.html',
                           paises=repo.listar_paises(),
                           estados=repo.listar_estados(),
                           ciudades=repo.listar_ciudades())


@admin_bp.route('/admin/geografia/pais/<int:pid>/editar', methods=['POST'])
def editar_pais(pid):
    redir = _require_admin()
    if redir:
        return redir
    try:
        nombre = _get_str(request.form, 'nombre', 'nombre del país', required=True, max_len=80)
        repo.actualizar_pais(pid, nombre)
        flash('País actualizado.', 'success')
    except Exception as e:
        _flash_error(e)
    return redirect(url_for('admin.geografia'))


@admin_bp.route('/admin/geografia/pais/<int:pid>/eliminar', methods=['POST'])
def eliminar_pais(pid):
    redir = _require_admin()
    if redir:
        return redir
    try:
        repo.eliminar_pais(pid)
        flash('País eliminado.', 'success')
    except Exception as e:
        _flash_error(e)
    return redirect(url_for('admin.geografia'))


@admin_bp.route('/admin/geografia/estado/<int:eid>/editar', methods=['POST'])
def editar_estado(eid):
    redir = _require_admin()
    if redir:
        return redir
    try:
        campos = {
            'estado_nombre': _get_str(request.form, 'nombre',  'nombre del estado', required=True, max_len=80),
            'pais_id':       _get_int(request.form, 'pais_id', 'país',              required=True),
        }
        repo.actualizar_estado(eid, campos)
        flash('Estado actualizado.', 'success')
    except Exception as e:
        _flash_error(e)
    return redirect(url_for('admin.geografia'))


@admin_bp.route('/admin/geografia/estado/<int:eid>/eliminar', methods=['POST'])
def eliminar_estado(eid):
    redir = _require_admin()
    if redir:
        return redir
    try:
        repo.eliminar_estado(eid)
        flash('Estado eliminado.', 'success')
    except Exception as e:
        _flash_error(e)
    return redirect(url_for('admin.geografia'))


@admin_bp.route('/admin/geografia/ciudad/<int:cid>/editar', methods=['POST'])
def editar_ciudad(cid):
    redir = _require_admin()
    if redir:
        return redir
    try:
        campos = {
            'ciudad_nombre': _get_str(request.form, 'nombre',    'nombre de la ciudad', required=True, max_len=80),
            'estado_id':     _get_int(request.form, 'estado_id', 'estado',              required=True),
        }
        repo.actualizar_ciudad(cid, campos)
        flash('Ciudad actualizada.', 'success')
    except Exception as e:
        _flash_error(e)
    return redirect(url_for('admin.geografia'))


@admin_bp.route('/admin/geografia/ciudad/<int:cid>/eliminar', methods=['POST'])
def eliminar_ciudad(cid):
    redir = _require_admin()
    if redir:
        return redir
    try:
        repo.eliminar_ciudad(cid)
        flash('Ciudad eliminada.', 'success')
    except Exception as e:
        _flash_error(e)
    return redirect(url_for('admin.geografia'))


@admin_bp.route('/admin/api/estados/<int:pais_id>')
def api_estados(pais_id):
    return jsonify(repo.listar_estados(pais_id=pais_id))


@admin_bp.route('/admin/api/ciudades/<int:estado_id>')
def api_ciudades(estado_id):
    return jsonify(repo.listar_ciudades(estado_id=estado_id))


@admin_bp.route('/admin/analytics')
def analytics():
    redir = _require_admin()
    if redir:
        return redir
    return render_template('admin/analytics.html',
                           esquemas=repo.listar_esquemas(),
                           centros=repo.listar_centros(),
                           vacunas=repo.listar_vacunas())


@admin_bp.route('/admin/api/kpis')
def api_kpis():
    redir = _require_admin()
    if redir:
        return jsonify({'error': 'No autorizado'}), 401
    try:
        data = repo.kpis_generales()
    except Exception:
        data = {}
    return jsonify(data)


@admin_bp.route('/admin/api/ranking-centros')
def api_ranking_centros():
    redir = _require_admin()
    if redir:
        return jsonify({'error': 'No autorizado'}), 401
    meses = request.args.get('meses', 6, type=int)
    rows  = repo.ranking_centros_actividad(meses)
    for r in rows:
        for k in ('ranking', 'aplicaciones_periodo', 'total_aplicaciones',
                  'pacientes_atendidos', 'dias_con_actividad'):
            if r.get(k) is not None:
                r[k] = int(r[k])
        if r.get('pct_del_total') is not None:
            r['pct_del_total'] = float(r['pct_del_total'])
    return jsonify(rows)


@admin_bp.route('/admin/api/cobertura-vacunal')
def api_cobertura_vacunal():
    redir = _require_admin()
    if redir:
        return jsonify({'error': 'No autorizado'}), 401
    esquema_id = request.args.get('esquema_id', 1, type=int)
    rows = repo.reporte_cobertura_vacunal(esquema_id)
    for r in rows:
        for k in ('total_pacientes', 'pacientes_con_dosis', 'total_aplicaciones',
                  'dosis_edad_oportuna_dias'):
            if r.get(k) is not None:
                r[k] = int(r[k])
        if r.get('pct_cobertura') is not None:
            r['pct_cobertura'] = float(r['pct_cobertura'])
    return jsonify(rows)


@admin_bp.route('/admin/api/dosis-urgentes')
def api_dosis_urgentes():
    redir = _require_admin()
    if redir:
        return jsonify({'error': 'No autorizado'}), 401
    centro_id = request.args.get('centro_id', type=int)
    rows = repo.pacientes_dosis_urgentes(centro_id)
    for r in rows:
        for k in ('edad_dias', 'dosis_edad_oportuna_dias', 'dias_atraso',
                  'dias_para_limite', 'ranking_urgencia'):
            if r.get(k) is not None:
                r[k] = int(r[k])
        if isinstance(r.get('paciente_fecha_nac'), date):
            r['paciente_fecha_nac'] = str(r['paciente_fecha_nac'])
    return jsonify(rows)


@admin_bp.route('/admin/reportes')
def reportes():
    return redirect(url_for('admin.analytics'))


@admin_bp.route('/admin/api/reporte-datos')
def api_report_data():
    redir = _require_admin()
    if redir:
        return jsonify({'error': 'No autorizado'}), 401

    desde     = request.args.get('desde', '2020-01-01')
    hasta     = request.args.get('hasta', '2099-12-31')
    centro_id = request.args.get('centro', type=int)
    vacuna_id = request.args.get('vacuna', type=int)

    por_mes = repo.chart_por_mes(desde, hasta, centro_id, vacuna_id)
    top_vac = repo.chart_top_vacunas(desde, hasta, centro_id, vacuna_id)
    resumen = repo.resumen_periodo(desde, hasta, centro_id, vacuna_id)

    for r in por_mes:
        if hasattr(r.get('mes_orden'), 'isoformat'):
            r.pop('mes_orden', None)

    return jsonify({'por_mes': por_mes, 'top_vacunas': top_vac, 'total': resumen['total']})


# ── MongoDB analytics API ─────────────────────────────────────────────────────

@admin_bp.route('/admin/api/mongo/aplicaciones-por-mes')
def api_mongo_aplicaciones_por_mes():
    redir = _require_admin()
    if redir:
        return jsonify({'error': 'No autorizado'}), 401
    raw = mdb.aplicaciones_por_mes(12)
    data = [
        {
            'año':  r['_id']['year'],
            'mes':  r['_id']['month'],
            'label': f"{r['_id']['year']}-{r['_id']['month']:02d}",
            'total': r['total'],
        }
        for r in raw
    ]
    return jsonify(data)


@admin_bp.route('/admin/api/mongo/top-vacunas')
def api_mongo_top_vacunas():
    redir = _require_admin()
    if redir:
        return jsonify({'error': 'No autorizado'}), 401
    raw = mdb.top_vacunas(10)
    data = [{'vacuna': r['_id'], 'total': r['total']} for r in raw]
    return jsonify(data)


@admin_bp.route('/admin/api/mongo/aplicaciones-por-centro')
def api_mongo_aplicaciones_por_centro():
    redir = _require_admin()
    if redir:
        return jsonify({'error': 'No autorizado'}), 401
    raw = mdb.aplicaciones_por_centro(10)
    data = [{'centro': r['_id'], 'total': r['total']} for r in raw]
    return jsonify(data)


@admin_bp.route('/admin/api/mongo/resumen-logs')
def api_mongo_resumen_logs():
    redir = _require_admin()
    if redir:
        return jsonify({'error': 'No autorizado'}), 401
    return jsonify(mdb.resumen_logs())


@admin_bp.route('/admin/api/mongo/ultimos-accesos')
def api_mongo_ultimos_accesos():
    redir = _require_admin()
    if redir:
        return jsonify({'error': 'No autorizado'}), 401
    docs = mdb.ultimos_accesos(20)
    for d in docs:
        if hasattr(d.get('timestamp'), 'isoformat'):
            d['timestamp'] = d['timestamp'].isoformat()
    return jsonify(docs)


@admin_bp.route('/admin/api/mongo/eventos-beacon')
def api_mongo_eventos_beacon():
    redir = _require_admin()
    if redir:
        return jsonify({'error': 'No autorizado'}), 401
    raw = mdb.eventos_beacon_por_centro(10)
    data = [{'centro_id': r['_id'], 'total': r['total']} for r in raw]
    return jsonify(data)


@admin_bp.route('/admin/api/mongo/busquedas-gps')
def api_mongo_busquedas_gps():
    redir = _require_admin()
    if redir:
        return jsonify({'error': 'No autorizado'}), 401
    docs = mdb.busquedas_gps_recientes(20)
    for d in docs:
        if hasattr(d.get('timestamp'), 'isoformat'):
            d['timestamp'] = d['timestamp'].isoformat()
    return jsonify(docs)


@admin_bp.route('/admin/perfil')
def perfil():
    redir = _require_admin()
    if redir:
        return redir
    admin = repo.obtener_administrador(session['user_id'])
    return render_template('admin/perfil.html', admin=admin)


@admin_bp.route('/admin/perfil/foto', methods=['POST'])
def admin_subir_foto_perfil():
    redir = _require_admin()
    if redir:
        return redir
    file = request.files.get('foto')
    if not file or file.filename == '':
        flash('Selecciona una imagen.', 'error')
        return redirect(url_for('admin.perfil'))
    if not _allowed_file(file.filename):
        flash('Formato no permitido. Usa PNG, JPG, GIF o WebP.', 'error')
        return redirect(url_for('admin.perfil'))
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"usuario_{session['user_id']}.{ext}"
    upload_dir = os.path.join(current_app.static_folder, 'uploads', 'fotos')
    os.makedirs(upload_dir, exist_ok=True)
    file.save(os.path.join(upload_dir, filename))
    repo.actualizar_imagen_usuario(session['user_id'], f"uploads/fotos/{filename}")
    flash('Foto de perfil actualizada.', 'success')
    return redirect(url_for('admin.perfil'))


@admin_bp.route('/admin/pacientes/<int:pid>/foto', methods=['POST'])
def subir_foto_paciente(pid):
    redir = _require_admin()
    if redir:
        return redir
    file = request.files.get('foto')
    if not file or file.filename == '':
        flash('Selecciona una imagen.', 'error')
        return redirect(url_for('admin.pacientes'))
    if not _allowed_file(file.filename):
        flash('Formato no permitido. Usa PNG, JPG, GIF o WebP.', 'error')
        return redirect(url_for('admin.pacientes'))
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"paciente_{pid}.{ext}"
    upload_dir = os.path.join(current_app.static_folder, 'uploads', 'fotos')
    os.makedirs(upload_dir, exist_ok=True)
    file.save(os.path.join(upload_dir, filename))
    repo.actualizar_imagen_paciente(pid, f"uploads/fotos/{filename}")
    flash('Foto del paciente actualizada.', 'success')
    return redirect(url_for('admin.pacientes'))

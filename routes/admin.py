# Esta aplicación contiene todo lo relacionado a la vista de administrador,
# tomando en cuenta todos sus diferentes módulos.

import os
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, current_app
from werkzeug.security import generate_password_hash as _gph
from werkzeug.utils import secure_filename
from functools import partial
from datetime import date, datetime
from utils.helpers import generate_temp_password, days_to_human, validar_aplicacion
import repository as repo

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def _allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

generate_password_hash = partial(_gph, method='pbkdf2:sha256')

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

DOSIS_TIPOS = ['UNICA', 'SERIE_PRIMARIA', 'REFUERZO', 'ANUAL', 'ADICIONAL']


def _require_admin():
    if session.get('user_role') != 'admin':
        return redirect(url_for('auth.login'))
    return None


# ── Dashboard ─────────────────────────────────────────────────────

@admin_bp.route('/')
@admin_bp.route('/dashboard')
def dashboard():
    redir = _require_admin()
    if redir:
        return redir

    import json as _json
    stats = repo.stats_dashboard()

    alertas = []
    for a in repo.listar_alertas_inventario()[-5:]:
        ts = a.get('alerta_inv_timestamp') or a.get('ts')
        alertas.append({'tipo': 'inventario', 'subtipo': a['alerta_inv_tipo'], 'ts': ts, 'paciente': None})
    for a in repo.listar_alertas_dosis()[-5:]:
        alertas.append({'tipo': 'dosis', 'subtipo': a['alerta_dosis_pac_tipo'],
                        'ts': a['alerta_dosis_pac_timestamp'], 'paciente': a.get('paciente')})
    alertas.sort(key=lambda x: x['ts'] or datetime.min, reverse=True)

    from datetime import date as _date
    _hasta = _date.today().isoformat()
    _desde = (_date.today().replace(year=_date.today().year - 2)).isoformat()
    meses_data = repo.chart_por_mes(_desde, _hasta)
    for r in meses_data:
        r.pop('mes_orden', None)
    chart_labels = _json.dumps([r['mes'] for r in meses_data])
    chart_data   = _json.dumps([r['total'] for r in meses_data])

    return render_template('admin/dashboard.html', stats=stats, alertas=alertas[:10],
                           chart_labels=chart_labels, chart_data=chart_data)


# ── Tutores ───────────────────────────────────────────────────────

@admin_bp.route('/tutores', methods=['GET', 'POST'])
def tutores():
    redir = _require_admin()
    if redir:
        return redir
    if request.method == 'POST':
        f    = request.form
        temp = generate_temp_password()
        datos = {
            'tutor_prim_nombre':  f['prim_nombre'],
            'tutor_seg_nombre':   f.get('seg_nombre') or None,
            'tutor_apellido_pat': f['apellido_pat'],
            'tutor_apellido_mat': f.get('apellido_mat') or None,
            'tutor_curp':         f.get('curp', '').upper() or None,
            'tutor_email':        f['email'].lower(),
            'tutor_telefono':     f.get('telefono') or None,
            'tutor_contrasena':   generate_password_hash(temp),
        }
        try:
            repo.crear_tutor(datos)
            flash(f'Tutor registrado. Contraseña temporal: <strong>{temp}</strong>', 'success')
        except ValueError as e:
            flash(str(e), 'error')
        return redirect(url_for('admin.tutores'))
    return render_template('admin/tutores.html', tutores=repo.listar_tutores())


@admin_bp.route('/tutores/<int:tid>/editar', methods=['POST'])
def editar_tutor(tid):
    redir = _require_admin()
    if redir:
        return redir
    f = request.form
    campos = {
        'tutor_prim_nombre':  f.get('prim_nombre'),
        'tutor_seg_nombre':   f.get('seg_nombre') or None,
        'tutor_apellido_pat': f.get('apellido_pat'),
        'tutor_apellido_mat': f.get('apellido_mat') or None,
        'tutor_email':        f.get('email', '').lower() or None,
        'tutor_telefono':     f.get('telefono') or None,
        'tutor_curp':         f.get('curp', '').upper() or None,
    }
    try:
        repo.actualizar_tutor(tid, campos)
        flash('Tutor actualizado.', 'success')
    except ValueError as e:
        flash(str(e), 'error')
    return redirect(url_for('admin.tutores'))


@admin_bp.route('/tutores/<int:tid>/eliminar', methods=['POST'])
def eliminar_tutor(tid):
    redir = _require_admin()
    if redir:
        return redir
    try:
        repo.eliminar_tutor(tid)
        flash('Tutor eliminado.', 'success')
    except ValueError as e:
        flash(str(e), 'error')
    return redirect(url_for('admin.tutores'))


# ── Responsables ──────────────────────────────────────────────────

@admin_bp.route('/responsables', methods=['GET', 'POST'])
def responsables():
    redir = _require_admin()
    if redir:
        return redir
    if request.method == 'POST':
        f    = request.form
        temp = generate_temp_password()
        datos = {
            'responsable_prim_nombre':  f['prim_nombre'],
            'responsable_seg_nombre':   f.get('seg_nombre') or None,
            'responsable_apellido_pat': f['apellido_pat'],
            'responsable_apellido_mat': f.get('apellido_mat') or None,
            'responsable_curp':         f.get('curp', '').strip().upper() or None,
            'responsable_rfc':          f.get('rfc', '').strip().upper() or None,
            'responsable_email':        f['email'].lower(),
            'responsable_telefono':     f.get('telefono') or None,
            'responsable_contrasena':   generate_password_hash(temp),
            'centro_id':                int(f['centro_id']),
        }
        try:
            nuevo = repo.crear_responsable(datos)
            rid   = nuevo['responsable_id']
            for num, spec in zip(request.form.getlist('cedula_numero'),
                                 request.form.getlist('cedula_especialidad')):
                if num.strip():
                    repo.agregar_cedula(rid, num.strip(), spec.strip() or None)
            flash(f'Responsable registrado. Contraseña temporal: <strong>{temp}</strong>', 'success')
        except ValueError as e:
            flash(str(e), 'error')
        return redirect(url_for('admin.responsables'))
    return render_template('admin/responsables.html',
                           responsables=repo.listar_responsables(),
                           centros=repo.listar_centros())


@admin_bp.route('/responsables/<int:rid>/eliminar', methods=['POST'])
def eliminar_responsable(rid):
    redir = _require_admin()
    if redir:
        return redir
    try:
        repo.eliminar_responsable(rid)
        flash('Responsable eliminado.', 'success')
    except ValueError as e:
        flash(str(e), 'error')
    return redirect(url_for('admin.responsables'))


# ── Administradores ───────────────────────────────────────────────

@admin_bp.route('/administradores', methods=['GET', 'POST'])
def administradores():
    redir = _require_admin()
    if redir:
        return redir
    if request.method == 'POST':
        f    = request.form
        temp = generate_temp_password()
        datos = {
            'admin_prim_nombre':  f['prim_nombre'],
            'admin_seg_nombre':   f.get('seg_nombre') or None,
            'admin_apellido_pat': f['apellido_pat'],
            'admin_apellido_mat': f.get('apellido_mat') or None,
            'admin_rfc':          f.get('rfc', '').strip().upper() or None,
            'admin_curp':         f.get('curp', '').strip().upper() or None,
            'admin_email':        f['email'].lower(),
            'admin_telefono':     f.get('telefono') or None,
            'admin_contrasena':   generate_password_hash(temp),
        }
        try:
            repo.crear_admin(datos)
            flash(f'Administrador registrado. Contraseña temporal: <strong>{temp}</strong>', 'success')
        except ValueError as e:
            flash(str(e), 'error')
        return redirect(url_for('admin.administradores'))
    return render_template('admin/administradores.html', admins=repo.listar_administradores())


@admin_bp.route('/administradores/<int:aid>/eliminar', methods=['POST'])
def eliminar_admin(aid):
    redir = _require_admin()
    if redir:
        return redir
    try:
        repo.eliminar_admin(aid, session['user_id'])
        flash('Administrador eliminado.', 'success')
    except ValueError as e:
        flash(str(e), 'error')
    return redirect(url_for('admin.administradores'))


# ── Pacientes ─────────────────────────────────────────────────────

@admin_bp.route('/pacientes', methods=['GET', 'POST'])
def pacientes():
    redir = _require_admin()
    if redir:
        return redir
    if request.method == 'POST':
        f     = request.form
        curp = f.get('curp', '').strip().upper() or None
        cert = f.get('num_cert_nac', '').strip() or None
        if not curp and not cert:
            flash('Debes llenar al menos CURP o N° Certificado de Nacimiento.', 'error')
            return redirect(url_for('admin.pacientes'))
        datos = {
            'paciente_prim_nombre':  f['prim_nombre'],
            'paciente_seg_nombre':   f.get('seg_nombre') or None,
            'paciente_apellido_pat': f['apellido_pat'],
            'paciente_apellido_mat': f.get('apellido_mat') or None,
            'paciente_curp':         curp,
            'paciente_num_cert_nac': cert,
            'paciente_fecha_nac':    date.fromisoformat(f['fecha_nac']),
            'paciente_sexo':         f['sexo'],
            'paciente_nfc':          f.get('nfc') or None,
            'esquema_id':            int(f['esquema_id']),
        }
        try:
            repo.crear_paciente(datos)
            flash('Paciente registrado.', 'success')
        except ValueError as e:
            flash(str(e), 'error')
        return redirect(url_for('admin.pacientes'))
    return render_template('admin/pacientes.html',
                           pacientes=repo.listar_pacientes(),
                           esquemas=repo.listar_esquemas())


@admin_bp.route('/pacientes/<int:pid>/eliminar', methods=['POST'])
def eliminar_paciente(pid):
    redir = _require_admin()
    if redir:
        return redir
    try:
        repo.eliminar_paciente(pid)
        flash('Paciente eliminado.', 'success')
    except ValueError as e:
        flash(str(e), 'error')
    return redirect(url_for('admin.pacientes'))


# ── Relaciones ────────────────────────────────────────────────────

@admin_bp.route('/relaciones', methods=['GET', 'POST'])
def relaciones():
    redir = _require_admin()
    if redir:
        return redir
    if request.method == 'POST':
        f   = request.form
        pid = int(f['paciente_id'])
        tid = int(f['tutor_id'])
        pac = repo.obtener_paciente(pid)
        tut = repo.obtener_tutor(tid)
        pac_nombre = f"{pac['paciente_prim_nombre']} {pac['paciente_apellido_pat']}" if pac else '—'
        tut_nombre = f"{tut['tutor_prim_nombre']} {tut['tutor_apellido_pat']}" if tut else '—'
        try:
            repo.crear_relacion(pid, tid, pac_nombre, tut_nombre)
            flash('Relación registrada.', 'success')
        except ValueError as e:
            flash(str(e), 'error')
        return redirect(url_for('admin.relaciones'))
    import json as _json
    pacientes = repo.listar_pacientes()
    tutores   = repo.listar_tutores()
    pacientes_json = _json.dumps([{
        'id': p['paciente_id'],
        'nombre': f"{p['paciente_prim_nombre'].title()} {p['paciente_apellido_pat'].title()}",
        'curp': p.get('paciente_curp') or '',
        'cert': p.get('paciente_num_cert_nac') or '',
    } for p in pacientes])
    tutores_json = _json.dumps([{
        'id': t['tutor_id'],
        'nombre': f"{t['tutor_prim_nombre'].title()} {t['tutor_apellido_pat'].title()}",
        'curp': t.get('tutor_curp') or '',
        'email': t.get('tutor_email') or '',
    } for t in tutores])
    return render_template('admin/relaciones.html',
                           relaciones=repo.listar_relaciones(),
                           pacientes_json=pacientes_json,
                           tutores_json=tutores_json)


@admin_bp.route('/relaciones/<int:rid>/eliminar', methods=['POST'])
def eliminar_relacion(rid):
    redir = _require_admin()
    if redir:
        return redir
    repo.eliminar_relacion(rid)
    flash('Relación eliminada.', 'success')
    return redirect(url_for('admin.relaciones'))


# ── Centros ───────────────────────────────────────────────────────

@admin_bp.route('/centros', methods=['GET', 'POST'])
def centros():
    redir = _require_admin()
    if redir:
        return redir
    if request.method == 'POST':
        f = request.form
        datos = {
            'centro_nombre':          f['nombre'],
            'centro_calle':           f.get('calle') or None,
            'centro_numero':          f.get('numero') or None,
            'centro_codigo_postal':   f.get('cp') or None,
            'ciudad_id':              int(f['ciudad_id']),
            'centro_horario_inicio':  f.get('horario_inicio') or None,
            'centro_horario_fin':     f.get('horario_fin') or None,
            'centro_latitud':         float(f['latitud']) if f.get('latitud') else None,
            'centro_longitud':        float(f['longitud']) if f.get('longitud') else None,
            'centro_telefono':        f.get('telefono') or None,
            'centro_beacon':          f.get('beacon') or None,
        }
        try:
            repo.crear_centro(datos)
            flash('Centro de salud registrado.', 'success')
        except ValueError as e:
            flash(str(e), 'error')
        return redirect(url_for('admin.centros'))
    return render_template('admin/centros.html',
                           centros=repo.listar_centros(),
                           ciudades=repo.listar_ciudades())


@admin_bp.route('/centros/<int:cid>/eliminar', methods=['POST'])
def eliminar_centro(cid):
    redir = _require_admin()
    if redir:
        return redir
    try:
        repo.eliminar_centro(cid)
        flash('Centro eliminado.', 'success')
    except ValueError as e:
        flash(str(e), 'error')
    return redirect(url_for('admin.centros'))


# ── Esquemas ──────────────────────────────────────────────────────

@admin_bp.route('/esquemas', methods=['GET', 'POST'])
def esquemas():
    redir = _require_admin()
    if redir:
        return redir

    if request.method == 'POST':
        f = request.form
        nombre             = f.get('nombre', '').strip()
        fecha_vigencia     = date.fromisoformat(f['fecha_vigencia'])
        esquema_anterior_id = f.get('esquema_anterior_id', type=int)
        dosis_seleccionadas = set(f.getlist('dosis_ids', type=int))

        nuevas_vacunas    = f.getlist('nueva_vacuna_id',     type=int)
        nuevas_tipos      = f.getlist('nueva_tipo')
        nuevas_ml         = f.getlist('nueva_cant_ml')
        nuevas_areas      = f.getlist('nueva_area')
        nuevas_edades     = f.getlist('nueva_edad_dias',     type=int)
        nuevas_intervalos = f.getlist('nueva_intervalo_dias', type=int)
        nuevas_limites    = f.getlist('nueva_limite_dias')

        try:
            nuevo   = repo.crear_esquema({'esquema_nombre': nombre,
                                          'esquema_fecha_vigencia': fecha_vigencia,
                                          'vigente_desde': date.today()})
            nuevo_id = nuevo['esquema_id']

            for i, vacuna_id in enumerate(nuevas_vacunas):
                if not vacuna_id:
                    continue
                limite_raw = nuevas_limites[i] if i < len(nuevas_limites) else ''
                d = repo.crear_dosis({
                    'vacuna_id':               vacuna_id,
                    'dosis_tipo':              nuevas_tipos[i] if i < len(nuevas_tipos) else 'UNICA',
                    'dosis_cant_ml':           float(nuevas_ml[i]) if i < len(nuevas_ml) and nuevas_ml[i] else 0.5,
                    'dosis_area_aplicacion':   nuevas_areas[i] if i < len(nuevas_areas) else '',
                    'dosis_edad_oportuna_dias': nuevas_edades[i] if i < len(nuevas_edades) else 0,
                    'dosis_intervalo_min_dias': nuevas_intervalos[i] if i < len(nuevas_intervalos) else 0,
                    'dosis_limite_edad_dias':  int(limite_raw) if limite_raw else None,
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
                r = repo.asignar_esquema_auto(esquema_anterior_id, nuevo_id)
                flash(f'Esquema publicado. {r.get("p_msg", "")}', 'success')
            else:
                flash('Esquema creado correctamente.', 'success')

        except ValueError as e:
            flash(str(e), 'error')

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
                'paciente_id':         pid,
                'nombre':              (f"{c['paciente_prim_nombre']} "
                                        f"{c.get('paciente_seg_nombre') or ''} "
                                        f"{c['paciente_apellido_pat']} "
                                        f"{c.get('paciente_apellido_mat') or ''}").split(),
                'nombre_display':      f"{c['paciente_prim_nombre']} {c['paciente_apellido_pat']}",
                'esquema_nuevo_id':    c['esquema_nuevo_id'],
                'esquema_nuevo_nombre': c['esquema_nuevo_nombre'],
                'esquema_actual_nombre': c.get('esquema_actual_nombre', ''),
                'dosis': [],
            }
        conflictos[pid]['dosis'].append({
            'dosis_id':     c['dosis_conflicto_id'],
            'vacuna_nombre': c['vacuna_nombre'],
            'dosis_tipo':   c['dosis_tipo'],
            'edad_dias':    c.get('dosis_edad_oportuna_dias'),
            'limite_dias':  c.get('dosis_limite_edad_dias'),
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


@admin_bp.route('/esquemas/<int:eid>/eliminar', methods=['POST'])
def eliminar_esquema(eid):
    redir = _require_admin()
    if redir:
        return redir
    try:
        repo.eliminar_esquema(eid)
        flash('Esquema eliminado.', 'success')
    except ValueError as e:
        flash(str(e), 'error')
    return redirect(url_for('admin.esquemas'))


@admin_bp.route('/esquemas/conflicto/resolver', methods=['POST'])
def resolver_conflicto_esquema():
    redir = _require_admin()
    if redir:
        return redir
    paciente_id     = request.form.get('paciente_id', type=int)
    esquema_nuevo_id = request.form.get('esquema_nuevo_id', type=int)
    accion          = request.form.get('accion')
    r = repo.resolver_conflicto_esquema(paciente_id, esquema_nuevo_id, accion)
    if r.get('p_ok') == 1:
        flash(r.get('p_msg', 'Resuelto.'), 'success')
    else:
        flash(r.get('p_msg', 'Error al resolver conflicto.'), 'error')
    return redirect(url_for('admin.esquemas') + '#tab-conflictos')


# ── Vacunas ───────────────────────────────────────────────────────

@admin_bp.route('/vacunas', methods=['GET', 'POST'])
def vacunas():
    redir = _require_admin()
    if redir:
        return redir
    if request.method == 'POST':
        try:
            repo.crear_vacuna({'vacuna_nombre': request.form['nombre']})
            flash('Vacuna registrada.', 'success')
        except ValueError as e:
            flash(str(e), 'error')
        return redirect(url_for('admin.vacunas'))

    todas_dosis = repo.listar_dosis()
    vacunas_list = []
    for v in repo.listar_vacunas():
        v2 = dict(v)
        v2['dosis'] = [d for d in todas_dosis if d['vacuna_id'] == v['vacuna_id']]
        vacunas_list.append(v2)
    return render_template('admin/vacunas.html',
                           vacunas=vacunas_list,
                           dosis_tipos=DOSIS_TIPOS,
                           days_to_human=days_to_human)


@admin_bp.route('/api/vacuna/<int:vid>/dosis')
def api_vacuna_dosis(vid):
    return jsonify(repo.listar_dosis(vacuna_id=vid))


# ── Padecimientos ─────────────────────────────────────────────────

@admin_bp.route('/padecimientos', methods=['GET', 'POST'])
def padecimientos():
    redir = _require_admin()
    if redir:
        return redir
    if request.method == 'POST':
        f = request.form
        try:
            repo.crear_padecimiento({
                'padecimiento_nombre':      f['nombre'],
                'padecimiento_descripcion': f.get('descripcion') or None,
            })
            flash('Padecimiento registrado.', 'success')
        except ValueError as e:
            flash(str(e), 'error')
        return redirect(url_for('admin.padecimientos'))
    return render_template('admin/padecimientos.html',
                           padecimientos=repo.listar_padecimientos(),
                           vacunas=repo.listar_vacunas())


# ── Fabricantes ───────────────────────────────────────────────────

@admin_bp.route('/fabricantes', methods=['GET', 'POST'])
def fabricantes():
    redir = _require_admin()
    if redir:
        return redir
    if request.method == 'POST':
        f    = request.form
        accion = f.get('accion', 'fabricante')
        try:
            if accion == 'proveedor':
                repo.crear_proveedor({
                    'proveedor_prim_nombre': f['prim_nombre'],
                    'proveedor_seg_nombre':  f.get('seg_nombre') or None,
                    'proveedor_apellido_pat': f['apellido_pat'],
                    'proveedor_apellido_mat': f.get('apellido_mat') or None,
                    'proveedor_email':        f.get('email') or None,
                    'proveedor_telefono':     f.get('telefono') or None,
                    'proveedor_empresa':      f.get('empresa') or None,
                    'fabricante_id':          int(f['fabricante_id']),
                })
                flash('Proveedor registrado correctamente.', 'success')
            else:
                repo.crear_fabricante({
                    'fabricante_nombre':   f['nombre'],
                    'pais_id':             int(f['pais_id']),
                    'fabricante_telefono': f.get('telefono') or None,
                })
                flash('Fabricante registrado.', 'success')
        except ValueError as e:
            flash(str(e), 'error')
        return redirect(url_for('admin.fabricantes'))
    return render_template('admin/fabricantes.html',
                           fabricantes=repo.listar_fabricantes(),
                           proveedores=repo.listar_proveedores(),
                           paises=repo.listar_paises())


# ── Lotes e inventario ────────────────────────────────────────────

@admin_bp.route('/lotes', methods=['GET', 'POST'])
def lotes():
    redir = _require_admin()
    if redir:
        return redir
    if request.method == 'POST':
        accion = request.form.get('accion')
        f      = request.form

        if accion == 'nuevo_lote':
            try:
                repo.crear_lote({
                    'lote_codigo':            f['codigo'],
                    'lote_fecha_fabricacion': date.fromisoformat(f['fecha_fab']),
                    'lote_fecha_caducidad':   date.fromisoformat(f['fecha_cad']),
                    'lote_cant_inicial':      int(f['cantidad']),
                    'vacuna_id':              int(f['vacuna_id']),
                    'fabricante_id':          int(f['fabricante_id']),
                    'proveedor_id':           int(f['proveedor_id']),
                })
                flash('Lote registrado.', 'success')
            except ValueError as e:
                flash(str(e), 'error')

        elif accion == 'asignar_inventario':
            try:
                repo.asignar_inventario({
                    'centro_id':                int(f['centro_id']),
                    'lote_id':                  int(f['lote_id']),
                    'inventario_stock_inicial': int(f['stock']),
                    'inventario_stock_actual':  int(f['stock']),
                    'inventario_activo_desde':  None,
                })
                flash('Inventario asignado. El responsable del centro debe confirmar su recepción.', 'success')
            except ValueError as e:
                flash(str(e), 'error')

        return redirect(url_for('admin.lotes'))

    return render_template('admin/lotes.html',
                           lotes=repo.listar_lotes(),
                           inventarios=repo.listar_inventarios(),
                           vacunas=repo.listar_vacunas(),
                           fabricantes=repo.listar_fabricantes(),
                           proveedores=repo.listar_proveedores(),
                           centros=repo.listar_centros())


# ── Inventario y alertas ──────────────────────────────────────────

@admin_bp.route('/inventario', methods=['GET', 'POST'])
def inventario():
    redir = _require_admin()
    if redir:
        return redir
    from datetime import date
    if request.method == 'POST':
        f = request.form
        try:
            r = repo.transferir_inventario(
                int(f['inv_origen_id']),
                int(f['centro_destino_id']),
                int(f['cantidad']),
            )
            if r.get('p_ok') == 1:
                flash(r.get('p_msg'), 'success')
            else:
                flash(r.get('p_msg', 'Error al transferir.'), 'error')
        except (ValueError, KeyError) as e:
            flash(str(e), 'error')
        return redirect(url_for('admin.inventario'))
    return render_template('admin/inventario.html',
                           inventarios=repo.listar_inventarios(),
                           transferencias=repo.listar_transferencias(),
                           centros=repo.listar_centros(),
                           alertas_inv=repo.listar_alertas_inventario(),
                           alertas_dosis=repo.listar_alertas_dosis(),
                           today=date.today())


@admin_bp.route('/api/inventarios-activos-centro/<int:centro_id>')
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


# ── Aplicaciones ──────────────────────────────────────────────────

@admin_bp.route('/aplicaciones', methods=['GET', 'POST'])
def aplicaciones():
    redir = _require_admin()
    if redir:
        return redir
    if request.method == 'POST':
        f = request.form
        if not f.get('paciente_id') or not f.get('dosis_id') or not f.get('inventario_id') or not f.get('responsable_id'):
            flash('Todos los campos son obligatorios.', 'error')
            return redirect(url_for('admin.aplicaciones'))

        inventario_id = int(f['inventario_id'])
        inv = repo.obtener_inventario(inventario_id)
        if not inv or not inv.get('inventario_activo') or inv['inventario_stock_actual'] <= 0:
            flash('No hay stock disponible en el inventario seleccionado.', 'error')
            return redirect(url_for('admin.aplicaciones'))

        pid = int(f['paciente_id'])
        did = int(f['dosis_id'])
        if repo.dosis_ya_aplicada(pid, did):
            flash('Esta dosis ya fue aplicada a este paciente.', 'error')
            return redirect(url_for('admin.aplicaciones'))

        pac  = repo.obtener_paciente(pid)
        dos  = repo.obtener_dosis(did)

        if pac and dos:
            aplicaciones_previas = repo.aplicaciones_de_paciente(pid)
            ok, error_msg = validar_aplicacion(pac, dos, aplicaciones_previas)
            if not ok:
                flash(error_msg, 'error')
                return redirect(url_for('admin.aplicaciones'))

        resp_id = int(f['responsable_id'])
        resp    = repo.obtener_responsable(resp_id)

        datos = {
            'paciente_id':              pid,
            'usuario_id':               resp_id,
            'centro_id':                inv['centro_id'],
            'lote_id':                  inv['lote_id'],
            'dosis_id':                 did,
            'aplicacion_observaciones': f.get('observaciones', ''),
        }
        try:
            repo.registrar_aplicacion(datos)
            flash('Aplicación registrada.', 'success')
        except ValueError as e:
            flash(str(e), 'error')
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
                           inventarios=[i for i in repo.listar_inventarios()
                                        if i['inventario_activo'] and i['inventario_stock_actual'] > 0],
                           dosis_list=dosis_list)


# ── Geografía ─────────────────────────────────────────────────────

@admin_bp.route('/geografia', methods=['GET', 'POST'])
def geografia():
    redir = _require_admin()
    if redir:
        return redir
    if request.method == 'POST':
        accion = request.form.get('accion')
        f      = request.form
        try:
            if accion == 'pais':
                repo.crear_pais(f['nombre'])
                flash('País registrado.', 'success')
            elif accion == 'estado':
                repo.crear_estado({'estado_nombre': f['nombre'], 'pais_id': int(f['pais_id'])})
                flash('Estado registrado.', 'success')
            elif accion == 'ciudad':
                repo.crear_ciudad({'ciudad_nombre': f['nombre'], 'estado_id': int(f['estado_id'])})
                flash('Ciudad registrada.', 'success')
        except ValueError as e:
            flash(str(e), 'error')
        return redirect(url_for('admin.geografia'))
    return render_template('admin/geografia.html',
                           paises=repo.listar_paises(),
                           estados=repo.listar_estados(),
                           ciudades=repo.listar_ciudades())


@admin_bp.route('/api/estados/<int:pais_id>')
def api_estados(pais_id):
    return jsonify(repo.listar_estados(pais_id=pais_id))


@admin_bp.route('/api/ciudades/<int:estado_id>')
def api_ciudades(estado_id):
    return jsonify(repo.listar_ciudades(estado_id=estado_id))


# ── Reportes ──────────────────────────────────────────────────────

@admin_bp.route('/reportes')
def reportes():
    redir = _require_admin()
    if redir:
        return redir
    return render_template('admin/reportes.html',
                           centros=repo.listar_centros(),
                           vacunas=repo.listar_vacunas(),
                           esquemas=repo.listar_esquemas())


@admin_bp.route('/api/reporte-datos')
def api_report_data():
    redir = _require_admin()
    if redir:
        return jsonify({'error': 'No autorizado'}), 401

    desde     = request.args.get('desde', '2020-01-01')
    hasta     = request.args.get('hasta', '2099-12-31')
    centro_id = request.args.get('centro', type=int)
    vacuna_id = request.args.get('vacuna', type=int)

    por_mes    = repo.chart_por_mes(desde, hasta, centro_id, vacuna_id)
    top_vac    = repo.chart_top_vacunas(desde, hasta, centro_id, vacuna_id)
    resumen    = repo.resumen_periodo(desde, hasta, centro_id, vacuna_id)

    for r in por_mes:
        if hasattr(r.get('mes_orden'), 'isoformat'):
            r.pop('mes_orden', None)

    return jsonify({'por_mes': por_mes, 'top_vacunas': top_vac, 'total': resumen['total']})


# ── Perfil admin ──────────────────────────────────────────────────

@admin_bp.route('/perfil')
def perfil():
    redir = _require_admin()
    if redir:
        return redir
    admin = repo.obtener_administrador(session['user_id'])
    return render_template('admin/perfil.html', admin=admin)


@admin_bp.route('/perfil/foto', methods=['POST'])
def subir_foto_perfil():
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


@admin_bp.route('/pacientes/<int:pid>/foto', methods=['POST'])
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

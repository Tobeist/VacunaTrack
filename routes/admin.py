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
        repo.crear_tutor(datos)
        flash(f'Tutor registrado. Contraseña temporal: <strong>{temp}</strong>', 'success')
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
    campos = {k: v for k, v in campos.items() if v is not None}
    repo.actualizar_tutor(tid, campos)
    flash('Tutor actualizado.', 'success')
    return redirect(url_for('admin.tutores'))


@admin_bp.route('/tutores/<int:tid>/eliminar', methods=['POST'])
def eliminar_tutor(tid):
    redir = _require_admin()
    if redir:
        return redir
    if not repo.eliminar_tutor(tid):
        flash('No se puede eliminar: este tutor tiene pacientes vinculados.', 'error')
    else:
        flash('Tutor eliminado.', 'success')
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
        nuevo = repo.crear_responsable(datos)
        rid   = nuevo['responsable_id']
        for num, spec in zip(request.form.getlist('cedula_numero'),
                             request.form.getlist('cedula_especialidad')):
            if num.strip():
                repo.agregar_cedula(rid, num.strip(), spec.strip() or None)
        flash(f'Responsable registrado. Contraseña temporal: <strong>{temp}</strong>', 'success')
        return redirect(url_for('admin.responsables'))
    return render_template('admin/responsables.html',
                           responsables=repo.listar_responsables(),
                           centros=repo.listar_centros())


@admin_bp.route('/responsables/<int:rid>/eliminar', methods=['POST'])
def eliminar_responsable(rid):
    redir = _require_admin()
    if redir:
        return redir
    if not repo.eliminar_responsable(rid):
        flash('No se puede eliminar: este responsable tiene aplicaciones registradas.', 'error')
    else:
        flash('Responsable eliminado.', 'success')
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
        repo.crear_admin(datos)
        flash(f'Administrador registrado. Contraseña temporal: <strong>{temp}</strong>', 'success')
        return redirect(url_for('admin.administradores'))
    return render_template('admin/administradores.html', admins=repo.listar_administradores())


@admin_bp.route('/administradores/<int:aid>/eliminar', methods=['POST'])
def eliminar_admin(aid):
    redir = _require_admin()
    if redir:
        return redir
    if aid == session['user_id']:
        flash('No puedes eliminar tu propia cuenta.', 'error')
    else:
        repo.eliminar_admin(aid)
        flash('Administrador eliminado.', 'success')
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
            'paciente_nombre':       f.get('seg_nombre') or None,
            'paciente_apellido_pat': f['apellido_pat'],
            'paciente_apellido_mat': f.get('apellido_mat') or None,
            'paciente_curp':         curp,
            'paciente_num_cert_nac': cert,
            'paciente_fecha_nac':    date.fromisoformat(f['fecha_nac']),
            'paciente_sexo':         f['sexo'],
            'paciente_nfc':          f.get('nfc') or None,
            'esquema_id':            int(f['esquema_id']),
        }
        repo.crear_paciente(datos)
        flash('Paciente registrado.', 'success')
        return redirect(url_for('admin.pacientes'))
    return render_template('admin/pacientes.html',
                           pacientes=repo.listar_pacientes(),
                           esquemas=repo.listar_esquemas())


@admin_bp.route('/pacientes/<int:pid>/eliminar', methods=['POST'])
def eliminar_paciente(pid):
    redir = _require_admin()
    if redir:
        return redir
    if not repo.eliminar_paciente(pid):
        flash('No se puede eliminar: este paciente tiene aplicaciones registradas.', 'error')
    else:
        flash('Paciente eliminado.', 'success')
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
        if repo.existe_relacion(pid, tid):
            flash('Esta relación ya existe.', 'error')
        else:
            pac = repo.obtener_paciente(pid)
            tut = repo.obtener_tutor(tid)
            pac_nombre = f"{pac['paciente_prim_nombre']} {pac['paciente_apellido_pat']}" if pac else '—'
            tut_nombre = f"{tut['tutor_prim_nombre']} {tut['tutor_apellido_pat']}" if tut else '—'
            repo.crear_relacion(pid, tid, pac_nombre, tut_nombre)
            flash('Relación registrada.', 'success')
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
        repo.crear_centro(datos)
        flash('Centro de salud registrado.', 'success')
        return redirect(url_for('admin.centros'))
    return render_template('admin/centros.html',
                           centros=repo.listar_centros(),
                           ciudades=repo.listar_ciudades())


@admin_bp.route('/centros/<int:cid>/eliminar', methods=['POST'])
def eliminar_centro(cid):
    redir = _require_admin()
    if redir:
        return redir
    if not repo.eliminar_centro(cid):
        flash('No se puede eliminar: este centro tiene responsables o inventario asignado.', 'error')
    else:
        flash('Centro eliminado.', 'success')
    return redirect(url_for('admin.centros'))


# ── Esquemas ──────────────────────────────────────────────────────

@admin_bp.route('/esquemas', methods=['GET', 'POST'])
def esquemas():
    redir = _require_admin()
    if redir:
        return redir
    if request.method == 'POST':
        f = request.form
        datos = {
            'esquema_nombre':         f['nombre'],
            'esquema_fecha_vigencia': date.fromisoformat(f['fecha_vigencia']),
            'vigente_desde':          date.today(),
        }
        repo.crear_esquema(datos)
        flash('Esquema registrado.', 'success')
        return redirect(url_for('admin.esquemas'))
    esquemas = repo.listar_esquemas()
    for e in esquemas:
        e['total_dosis'] = len(repo.dosis_de_esquema(e['esquema_id']))
    return render_template('admin/esquemas.html',
                           esquemas=esquemas,
                           dosis_list=repo.listar_dosis(),
                           vacunas=repo.listar_vacunas(),
                           days_to_human=days_to_human)


@admin_bp.route('/esquemas/<int:eid>/eliminar', methods=['POST'])
def eliminar_esquema(eid):
    redir = _require_admin()
    if redir:
        return redir
    if not repo.eliminar_esquema(eid):
        flash('No se puede eliminar: este esquema tiene pacientes asignados.', 'error')
    else:
        flash('Esquema eliminado.', 'success')
    return redirect(url_for('admin.esquemas'))


# ── Vacunas ───────────────────────────────────────────────────────

@admin_bp.route('/vacunas', methods=['GET', 'POST'])
def vacunas():
    redir = _require_admin()
    if redir:
        return redir
    if request.method == 'POST':
        f   = request.form
        vac = repo.crear_vacuna({'vacuna_nombre': f['nombre']})
        vid = vac['vacuna_id']
        tipos   = request.form.getlist('dosis_tipo')
        mls     = request.form.getlist('dosis_ml')
        areas   = request.form.getlist('dosis_area')
        edades  = request.form.getlist('dosis_edad')
        ints    = request.form.getlist('dosis_intervalo')
        limites = request.form.getlist('dosis_limite')
        for i in range(len(tipos)):
            if tipos[i]:
                repo.crear_dosis({
                    'vacuna_id':                vid,
                    'dosis_tipo':               tipos[i],
                    'dosis_cant_ml':            float(mls[i] or 0.5),
                    'dosis_area_aplicacion':    areas[i] or None,
                    'dosis_edad_oportuna_dias': int(edades[i] or 0),
                    'dosis_intervalo_min_dias': int(ints[i] or 0),
                    'dosis_limite_edad_dias':   int(limites[i]) if limites[i] else None,
                })
        flash('Vacuna registrada.', 'success')
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
        repo.crear_padecimiento({
            'padecimiento_nombre':      f['nombre'],
            'padecimiento_descripcion': f.get('descripcion') or None,
        })
        flash('Padecimiento registrado.', 'success')
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
        f = request.form
        repo.crear_fabricante({
            'fabricante_nombre':   f['nombre'],
            'pais_id':             int(f['pais_id']),
            'fabricante_telefono': f.get('telefono') or None,
        })
        flash('Fabricante registrado.', 'success')
        return redirect(url_for('admin.fabricantes'))
    return render_template('admin/fabricantes.html',
                           fabricantes=repo.listar_fabricantes(),
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
            fecha_cad = f['fecha_cad']
            if fecha_cad <= str(date.today()):
                flash('La fecha de caducidad debe ser posterior a hoy.', 'error')
                return redirect(url_for('admin.lotes'))
            if f['fecha_fab'] >= fecha_cad:
                flash('La fecha de fabricación debe ser anterior a la fecha de caducidad.', 'error')
                return redirect(url_for('admin.lotes'))
            repo.crear_lote({
                'lote_codigo':            f['codigo'],
                'lote_fecha_fabricacion': date.fromisoformat(f['fecha_fab']),
                'lote_fecha_caducidad':   date.fromisoformat(fecha_cad),
                'lote_cant_inicial':      int(f['cantidad']),
                'vacuna_id':              int(f['vacuna_id']),
                'fabricante_id':          int(f['fabricante_id']),
                'proveedor_id':           int(f['proveedor_id']),
            })
            flash('Lote registrado.', 'success')

        elif accion == 'asignar_inventario':
            stock = int(f['stock'])
            lote  = repo.obtener_lote(int(f['lote_id']))
            if not lote:
                flash('Lote no encontrado.', 'error')
                return redirect(url_for('admin.lotes'))
            if stock > lote['lote_cant_inicial']:
                flash(f"El stock ({stock}) no puede exceder la cantidad inicial del lote ({lote['lote_cant_inicial']}).", 'error')
                return redirect(url_for('admin.lotes'))
            if stock <= 0:
                flash('El stock debe ser mayor a 0.', 'error')
                return redirect(url_for('admin.lotes'))
            from datetime import datetime as _dt
            repo.asignar_inventario({
                'centro_id':                  int(f['centro_id']),
                'lote_id':                    int(f['lote_id']),
                'inventario_stock_inicial':   stock,
                'inventario_stock_actual':    stock,
                'inventario_activo_desde':    _dt.now(),
            })
            flash('Lote asignado al inventario.', 'success')

        return redirect(url_for('admin.lotes'))

    return render_template('admin/lotes.html',
                           lotes=repo.listar_lotes(),
                           inventarios=repo.listar_inventarios(),
                           vacunas=repo.listar_vacunas(),
                           fabricantes=repo.listar_fabricantes(),
                           proveedores=repo.listar_proveedores(),
                           centros=repo.listar_centros())


# ── Inventario y alertas ──────────────────────────────────────────

@admin_bp.route('/inventario')
def inventario():
    redir = _require_admin()
    if redir:
        return redir
    return render_template('admin/inventario.html',
                           inventarios=repo.listar_inventarios(),
                           alertas_inv=repo.listar_alertas_inventario(),
                           alertas_dosis=repo.listar_alertas_dosis())


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
            'aplicacion_timestamp':     datetime.now(),
            'aplicacion_observaciones': f.get('observaciones', ''),
        }
        repo.registrar_aplicacion(datos)
        flash('Aplicación registrada.', 'success')
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
        if accion == 'pais':
            repo.crear_pais(f['nombre'])
            flash('País registrado.', 'success')
        elif accion == 'estado':
            repo.crear_estado({'estado_nombre': f['nombre'], 'pais_id': int(f['pais_id'])})
            flash('Estado registrado.', 'success')
        elif accion == 'ciudad':
            repo.crear_ciudad({'ciudad_nombre': f['nombre'], 'estado_id': int(f['estado_id'])})
            flash('Ciudad registrada.', 'success')
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

# Esta aplicación contiene todo lo relacionado a la vista clínica, desde la búsqueda
# de pacientes por NFC o CURP hasta el registro de nuevas aplicaciones.

import os
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, current_app
from werkzeug.utils import secure_filename
from utils.helpers import enrich_history, days_to_human, validar_aplicacion
from datetime import datetime, date
import repository as repo

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
def _allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

clinical_bp = Blueprint('clinical', __name__, url_prefix='/clinico')


def _require_responsable():
    if session.get('user_role') != 'responsable':
        return redirect(url_for('auth.login'))
    return None


@clinical_bp.route('/')
def lookup():
    redir = _require_responsable()
    if redir:
        return redir
    return render_template('clinical/patient_lookup.html')


@clinical_bp.route('/api/nfc', methods=['POST'])
def api_scan_nfc():
    import re
    uid_raw  = request.json.get('uid', '').strip()
    # normalizar al formato de fábrica: xx:xx:xx:xx (minúsculas, con colons)
    clean    = re.sub(r'[:\-\s]', '', uid_raw).lower()
    uid_norm = ':'.join(clean[i:i+2] for i in range(0, len(clean), 2)) if clean else uid_raw
    paciente = repo.obtener_paciente_por_nfc(uid_norm) or repo.obtener_paciente_por_nfc(uid_raw)
    if not paciente:
        return jsonify({'error': 'Paciente no encontrado'}), 404
    return _patient_response(paciente)


@clinical_bp.route('/api/curp', methods=['POST'])
def api_search_curp():
    curp     = request.json.get('curp', '').strip().upper()
    paciente = repo.obtener_paciente_por_curp(curp)
    if not paciente:
        return jsonify({'error': 'Paciente no encontrado'}), 404
    return _patient_response(paciente)


@clinical_bp.route('/api/cert-nac', methods=['POST'])
def api_search_cert_nac():
    cert     = request.json.get('cert_nac', '').strip()
    paciente = repo.obtener_paciente_por_cert_nac(cert)
    if not paciente:
        return jsonify({'error': 'Paciente no encontrado'}), 404
    return _patient_response(paciente)


def _patient_response(paciente):
    birth_date = paciente['paciente_fecha_nac']
    age_days   = (date.today() - birth_date).days
    rows      = repo.historial_vacunacion_paciente(paciente['paciente_id'], paciente['esquema_id'])
    historial = enrich_history(rows, birth_date)
    for r in historial:
        r['edad_texto'] = days_to_human(r['dosis_edad_oportuna_dias'])
        if r.get('aplicacion_timestamp'):
            r['aplicacion_timestamp'] = str(r['aplicacion_timestamp'])
        if r.get('responsable'):
            r['responsable'] = r['responsable'].title()
    nombre = ' '.join(filter(None, [
        paciente.get('paciente_prim_nombre', '').title(),
        (paciente.get('paciente_seg_nombre') or '').title() or None,
        paciente.get('paciente_apellido_pat', '').title(),
        (paciente.get('paciente_apellido_mat') or '').title() or None,
    ]))
    return jsonify({
        'paciente': {
            'id':         paciente['paciente_id'],
            'nombre':     nombre,
            'fecha_nac':  str(birth_date),
            'edad_dias':  age_days,
            'edad_texto': days_to_human(age_days),
            'sexo':       paciente['paciente_sexo'],
            'curp':       paciente.get('paciente_curp'),
        },
        'historial': historial,
    })


@clinical_bp.route('/registrar', methods=['GET', 'POST'])
def register_application():
    redir = _require_responsable()
    if redir:
        return redir
    responsable_id = session['user_id']
    responsable    = repo.obtener_responsable(responsable_id)
    centro_id      = responsable['centro_id'] if responsable else None

    if request.method == 'POST':
        paciente_id   = request.form.get('paciente_id', type=int)
        dosis_id      = request.form.get('dosis_id', type=int)
        inventario_id = request.form.get('inventario_id', type=int)
        observaciones = request.form.get('observaciones', '')

        if not paciente_id or not dosis_id or not inventario_id:
            flash('Todos los campos son obligatorios.', 'error')
            return redirect(url_for('clinical.register_application'))

        inv = repo.obtener_inventario(inventario_id)
        if not inv or not inv.get('inventario_activo') or inv['inventario_stock_actual'] <= 0:
            flash('No hay stock disponible en el inventario seleccionado.', 'error')
            return redirect(url_for('clinical.register_application'))

        if repo.dosis_ya_aplicada(paciente_id, dosis_id):
            flash('Esta dosis ya fue aplicada a este paciente.', 'error')
            return redirect(url_for('clinical.register_application'))

        paciente = repo.obtener_paciente(paciente_id)
        dosis    = repo.obtener_dosis(dosis_id)

        if paciente and dosis:
            aplicaciones_previas = repo.aplicaciones_de_paciente(paciente_id)
            ok, error_msg = validar_aplicacion(paciente, dosis, aplicaciones_previas)
            if not ok:
                flash(error_msg, 'error')
                return redirect(url_for('clinical.register_application'))

        datos = {
            'paciente_id':              paciente_id,
            'usuario_id':               responsable_id,
            'centro_id':                centro_id,
            'lote_id':                  inv['lote_id'],
            'dosis_id':                 dosis_id,
            'aplicacion_observaciones': observaciones,
        }
        try:
            repo.registrar_aplicacion(datos)
            flash('Aplicación registrada correctamente.', 'success')
        except ValueError as e:
            flash(str(e), 'error')
        return redirect(url_for('clinical.lookup'))

    inventarios = repo.inventarios_activos_de_centro(centro_id) if centro_id else []
    dosis_list  = repo.listar_dosis()
    vacunas     = {v['vacuna_id']: v['vacuna_nombre'] for v in repo.listar_vacunas()}
    for d in dosis_list:
        if 'vacuna_nombre' not in d:
            d['vacuna_nombre'] = vacunas.get(d['vacuna_id'], '—')
    dosis_list.sort(key=lambda x: (x.get('vacuna_nombre', ''), x['dosis_edad_oportuna_dias']))
    return render_template('clinical/register_application.html',
                           inventarios=inventarios,
                           pacientes=repo.listar_pacientes(),
                           dosis_list=dosis_list)


@clinical_bp.route('/api/dosis-por-inventario/<int:inventario_id>')
def api_dosis_por_inventario(inventario_id):
    inv = repo.obtener_inventario(inventario_id)
    if not inv:
        return jsonify([])
    lote = repo.obtener_lote(inv['lote_id'])
    if not lote:
        return jsonify([])
    dosis = repo.listar_dosis(vacuna_id=lote['vacuna_id'])
    vac   = repo.obtener_vacuna(lote['vacuna_id'])
    nombre = vac['vacuna_nombre'] if vac else '—'
    for d in dosis:
        d['vacuna_nombre'] = d.get('vacuna_nombre', nombre)
    dosis.sort(key=lambda x: x['dosis_edad_oportuna_dias'])
    return jsonify(dosis)


@clinical_bp.route('/api/dosis-aplicables/<int:paciente_id>')
def api_dosis_aplicables(paciente_id):
    paciente = repo.obtener_paciente(paciente_id)
    if not paciente:
        return jsonify([])
    esquema_id = paciente.get('esquema_id')
    if not esquema_id:
        return jsonify([])
    historial = repo.historial_vacunacion_paciente(paciente_id, esquema_id)
    birth_raw = paciente.get('paciente_fecha_nac')
    if hasattr(birth_raw, 'date'):
        birth = birth_raw.date()
    elif isinstance(birth_raw, date):
        birth = birth_raw
    else:
        birth = None
    if birth is None:
        return jsonify([])
    enriched = enrich_history(historial, birth)
    aplicables = [
        {
            'dosis_id':    r['dosis_id'],
            'vacuna_nombre': r.get('vacuna_nombre', ''),
            'dosis_tipo':  r.get('dosis_tipo', ''),
            'status':      r['status'],
            'status_label': r['status_label'],
        }
        for r in enriched
        if r['status'] in ('aplicable', 'atrasada', 'cerca_limite')
    ]
    return jsonify(aplicables)


@clinical_bp.route('/inventario/confirmar', methods=['GET', 'POST'])
def confirmar_inventario():
    redir = _require_responsable()
    if redir:
        return redir
    responsable_id = session['user_id']
    responsable    = repo.obtener_responsable(responsable_id)
    centro_id      = responsable['centro_id'] if responsable else None

    if request.method == 'POST':
        lote_codigo = request.form.get('lote_codigo', '').strip()
        if not lote_codigo:
            flash('Ingresa el código de lote.', 'error')
        else:
            r = repo.confirmar_recepcion_inventario(lote_codigo, responsable_id)
            if r.get('p_ok') == 1:
                flash(r.get('p_msg', 'Inventario activado correctamente.'), 'success')
            else:
                flash(r.get('p_msg', 'No se pudo activar el inventario.'), 'error')
        return redirect(url_for('clinical.confirmar_inventario'))

    pendientes = repo.inventarios_pendientes_de_centro(centro_id) if centro_id else []
    return render_template('clinical/confirmar_inventario.html',
                           pendientes=pendientes,
                           responsable=responsable)


@clinical_bp.route('/perfil')
def profile():
    redir = _require_responsable()
    if redir:
        return redir
    responsable = repo.obtener_responsable(session['user_id'])
    cedulas     = repo.cedulas_de_responsable(session['user_id'])
    return render_template('clinical/profile.html', responsable=responsable, cedulas=cedulas)


@clinical_bp.route('/perfil/foto', methods=['POST'])
def subir_foto_perfil():
    redir = _require_responsable()
    if redir:
        return redir
    file = request.files.get('foto')
    if not file or file.filename == '':
        flash('Selecciona una imagen.', 'error')
        return redirect(url_for('clinical.profile'))
    if not _allowed_file(file.filename):
        flash('Formato no permitido. Usa PNG, JPG, GIF o WebP.', 'error')
        return redirect(url_for('clinical.profile'))
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"usuario_{session['user_id']}.{ext}"
    upload_dir = os.path.join(current_app.static_folder, 'uploads', 'fotos')
    os.makedirs(upload_dir, exist_ok=True)
    file.save(os.path.join(upload_dir, filename))
    repo.actualizar_imagen_usuario(session['user_id'], f"uploads/fotos/{filename}")
    flash('Foto de perfil actualizada.', 'success')
    return redirect(url_for('clinical.profile'))

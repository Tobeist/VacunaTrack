# Esta aplicación contiene todo lo relacionado a la vista pública,
# tanto con sesión iniciada (tutor) como antes de iniciar sesión.

import os
from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify, current_app
from werkzeug.utils import secure_filename
from utils.helpers import enrich_history, days_to_human
import repository as repo

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
def _allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

public_bp = Blueprint('public', __name__)


def _require_tutor():
    if session.get('user_role') != 'tutor':
        return redirect(url_for('auth.login'))
    return None


@public_bp.route('/')
def landing():
    stats = {
        'aplicaciones': len(repo.listar_aplicaciones()),
        'centros':       len(repo.listar_centros()),
        'esquemas':      len(repo.listar_esquemas()),
    }
    return render_template('public/landing.html', stats=stats)


@public_bp.route('/esquemas')
def schemes():
    return render_template('public/schemes.html', esquemas=repo.listar_esquemas(), days_to_human=days_to_human)


@public_bp.route('/esquemas/<int:esquema_id>/dosis')
def scheme_doses(esquema_id):
    dosis = repo.dosis_de_esquema(esquema_id)
    for d in dosis:
        if 'vacuna_nombre' not in d:
            vac = repo.obtener_vacuna(d['vacuna_id'])
            d['vacuna_nombre'] = vac['vacuna_nombre'] if vac else '—'
        d['edad_texto'] = days_to_human(d['dosis_edad_oportuna_dias'])
    dosis.sort(key=lambda x: x['dosis_edad_oportuna_dias'])
    return jsonify(dosis)


@public_bp.route('/api/stats-publicas')
def api_stats_publicas():
    desde = '2000-01-01'
    hasta = '2099-12-31'
    por_mes    = repo.chart_por_mes(desde, hasta)
    top_vacunas = repo.chart_top_vacunas(desde, hasta)
    for r in por_mes:
        r.pop('mes_orden', None)
    return jsonify({'por_mes': por_mes, 'top_vacunas': top_vacunas})


@public_bp.route('/tutor')
def tutor_dashboard():
    redir = _require_tutor()
    if redir:
        return redir
    hijos = repo.pacientes_de_tutor(session['user_id'])
    return render_template('public/tutor_dashboard.html', hijos=hijos)


@public_bp.route('/tutor/historial/<int:paciente_id>')
def child_history(paciente_id):
    redir = _require_tutor()
    if redir:
        return redir
    tutor_id = session['user_id']
    if not repo.existe_relacion(paciente_id, tutor_id):
        return redirect(url_for('public.tutor_dashboard'))

    paciente   = repo.obtener_paciente(paciente_id)
    hijos      = repo.pacientes_de_tutor(tutor_id)
    birth_date = paciente['paciente_fecha_nac']
    rows       = repo.historial_vacunacion_paciente(paciente_id, paciente['esquema_id'])
    historial  = enrich_history(rows, birth_date)

    return render_template('public/child_history.html',
                           paciente=paciente, hijos=hijos, historial=historial)


@public_bp.route('/api/historial/<int:paciente_id>')
def api_child_history(paciente_id):
    if session.get('user_role') not in ('tutor', 'admin', 'responsable'):
        return jsonify({'error': 'No autorizado'}), 401
    paciente = repo.obtener_paciente(paciente_id)
    if not paciente:
        return jsonify([])
    birth_date = paciente['paciente_fecha_nac']
    rows       = repo.historial_vacunacion_paciente(paciente_id, paciente['esquema_id'])
    for r in rows:
        if r.get('aplicacion_timestamp'):
            r['aplicacion_timestamp'] = str(r['aplicacion_timestamp'])
    enriched = enrich_history(rows, birth_date)
    for r in enriched:
        r['edad_texto'] = days_to_human(r['dosis_edad_oportuna_dias'])
    return jsonify(enriched)


@public_bp.route('/tutor/centros')
def find_centers():
    redir = _require_tutor()
    if redir:
        return redir
    hijos = [{'paciente_id': p['paciente_id'],
               'paciente_prim_nombre': p['paciente_prim_nombre'],
               'paciente_apellido_pat': p['paciente_apellido_pat']}
              for p in repo.pacientes_de_tutor(session['user_id'])]
    return render_template('public/find_centers.html', vacunas=repo.listar_vacunas(), hijos=hijos)


@public_bp.route('/api/centros-cercanos')
def api_nearby_centers():
    vacuna_id = request.args.get('vacuna_id', type=int)
    if not vacuna_id:
        return jsonify([])
    centros = repo.centros_con_vacuna_disponible(vacuna_id)
    # convertir Decimal a float para JSON
    for c in centros:
        for key in ('centro_latitud', 'centro_longitud', 'stock_total'):
            if c.get(key) is not None:
                c[key] = float(c[key])
    return jsonify(centros)


@public_bp.route('/tutor/perfil')
def tutor_profile():
    redir = _require_tutor()
    if redir:
        return redir
    tutor = repo.obtener_tutor(session['user_id'])
    return render_template('public/profile.html', tutor=tutor)


@public_bp.route('/tutor/perfil/foto', methods=['POST'])
def subir_foto_tutor():
    redir = _require_tutor()
    if redir:
        return redir
    file = request.files.get('foto')
    if not file or file.filename == '':
        return redirect(url_for('public.tutor_profile'))
    if not _allowed_file(file.filename):
        return redirect(url_for('public.tutor_profile'))
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"usuario_{session['user_id']}.{ext}"
    upload_dir = os.path.join(current_app.static_folder, 'uploads', 'fotos')
    os.makedirs(upload_dir, exist_ok=True)
    file.save(os.path.join(upload_dir, filename))
    repo.actualizar_imagen_usuario(session['user_id'], f"uploads/fotos/{filename}")
    return redirect(url_for('public.tutor_profile'))

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
    rows     = repo.historial_vacunacion_paciente(paciente_id, paciente['esquema_id'])
    enriched = enrich_history(rows, birth_date)
    for r in enriched:
        r['edad_texto'] = days_to_human(r['dosis_edad_oportuna_dias'])
        if r.get('aplicacion_timestamp'):
            r['aplicacion_timestamp'] = str(r['aplicacion_timestamp'])
        if r.get('responsable'):
            r['responsable'] = r['responsable'].title()
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
    import math
    vacuna_id = request.args.get('vacuna_id', type=int)
    if not vacuna_id:
        return jsonify([])

    user_lat = request.args.get('lat', type=float)
    user_lng = request.args.get('lng', type=float)

    centros = repo.centros_con_vacuna_disponible(vacuna_id)

    for c in centros:
        for key in ('centro_latitud', 'centro_longitud', 'stock_total'):
            if c.get(key) is not None:
                c[key] = float(c[key])

        for key in ('centro_horario_inicio', 'centro_horario_fin'):
            if c.get(key) is not None:
                c[key] = str(c[key])

        if user_lat is not None and user_lng is not None:
            lat1, lon1 = math.radians(user_lat), math.radians(user_lng)
            lat2 = math.radians(c['centro_latitud'] or 0)
            lon2 = math.radians(c['centro_longitud'] or 0)
            dlat, dlon = lat2 - lat1, lon2 - lon1
            a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
            c['distancia_km'] = round(6371 * 2 * math.asin(math.sqrt(a)), 1)
        else:
            c['distancia_km'] = None

    if user_lat is not None:
        centros.sort(key=lambda x: x['distancia_km'] if x['distancia_km'] is not None else 9999)

    return jsonify(centros)


@public_bp.route('/api/beacon/info')
def api_beacon_info():
    import math
    if session.get('user_role') != 'tutor':
        return jsonify({'error': 'No autorizado'}), 401

    beacon_id = request.args.get('beacon_id')
    lat       = request.args.get('lat', type=float)
    lng       = request.args.get('lng', type=float)

    centro = None
    if beacon_id:
        centro = repo.obtener_centro_por_beacon(beacon_id)
    elif lat is not None and lng is not None:
        for c in repo.listar_centros():
            clat = float(c.get('centro_latitud') or 0)
            clng = float(c.get('centro_longitud') or 0)
            if not clat or not clng:
                continue
            dlat = math.radians(lat - clat)
            dlng = math.radians(lng - clng)
            a    = math.sin(dlat/2)**2 + math.cos(math.radians(clat)) * math.cos(math.radians(lat)) * math.sin(dlng/2)**2
            if 6371000 * 2 * math.asin(math.sqrt(a)) <= 100:
                centro = c
                break

    if not centro:
        return jsonify({'error': 'No se encontró ningún centro cercano'}), 404

    centro_id = centro['centro_id']
    tutor_id  = session['user_id']

    repo.registrar_lectura_beacon(centro_id, tutor_id)

    vacunas_centro = {v['vacuna_id']: v for v in repo.vacunas_en_centro(centro_id)}
    hijos          = repo.pacientes_de_tutor(tutor_id)
    vacunas_result = {}

    for hijo in hijos:
        birth_date  = hijo['paciente_fecha_nac']
        rows        = repo.historial_vacunacion_paciente(hijo['paciente_id'], hijo['esquema_id'])
        historial   = enrich_history(rows, birth_date)
        nombre_hijo = f"{hijo['paciente_prim_nombre']} {hijo['paciente_apellido_pat']}"

        for dosis in historial:
            vid = dosis.get('vacuna_id')
            if dosis['status'] in ('aplicable', 'cerca_limite', 'atrasada') and vid in vacunas_centro:
                if vid not in vacunas_result:
                    vacunas_result[vid] = {
                        'vacuna_nombre':     dosis['vacuna_nombre'],
                        'stock_total':       vacunas_centro[vid]['stock_total'],
                        'hijos':             [],
                        'personas_esperando': 0,
                    }
                vacunas_result[vid]['hijos'].append({
                    'nombre':       nombre_hijo,
                    'status':       dosis['status'],
                    'status_label': dosis['status_label'],
                })

    # Calcular cuántos tutores esperando en el centro necesitan cada vacuna
    tutores_esperando = repo.tutores_esperando_en_centro(centro_id)
    tutor_ids = {t['tutor_id'] for t in tutores_esperando}

    vacunas_por_tutor = {vid: set() for vid in vacunas_result}
    for t_id in tutor_ids:
        t_hijos = repo.pacientes_de_tutor(t_id)
        for hijo in t_hijos:
            rows     = repo.historial_vacunacion_paciente(hijo['paciente_id'], hijo['esquema_id'])
            hist     = enrich_history(rows, hijo['paciente_fecha_nac'])
            for dosis in hist:
                vid = dosis.get('vacuna_id')
                if (dosis['status'] in ('aplicable', 'cerca_limite', 'atrasada')
                        and vid in vacunas_por_tutor):
                    vacunas_por_tutor[vid].add(t_id)

    for vid in vacunas_result:
        vacunas_result[vid]['personas_esperando'] = len(vacunas_por_tutor[vid])

    return jsonify({
        'centro': {
            'id':        centro_id,
            'nombre':    centro.get('centro_nombre'),
            'direccion': f"{centro.get('centro_calle','') or ''} {centro.get('centro_numero','') or ''}".strip(),
        },
        'vacunas': list(vacunas_result.values()),
    })


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

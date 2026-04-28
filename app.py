import os
from dotenv import load_dotenv

load_dotenv()

import math
import json as _json
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash as _gph
from werkzeug.utils import secure_filename
from functools import partial
from datetime import date, datetime, time as _time
from utils.helpers import enrich_history, days_to_human, generate_temp_password, validar_aplicacion
import repository as repo

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def _allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

generate_password_hash = partial(_gph, method='pbkdf2:sha256')

DOSIS_TIPOS = ['UNICA', 'SERIE_PRIMARIA', 'REFUERZO', 'ANUAL', 'ADICIONAL']

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'vacunatrack-dev-secret-2026')

import db as _db
_db.init_app(app)


@app.template_filter('format_date')
def format_date(value):
    if not value:
        return '—'
    try:
        if isinstance(value, (date, datetime)):
            return value.strftime('%d/%m/%Y')
        return str(value)
    except Exception:
        return str(value)


@app.template_filter('format_datetime')
def format_datetime(value):
    if not value:
        return '—'
    try:
        if isinstance(value, datetime):
            return value.strftime('%d/%m/%Y %H:%M')
        return str(value)
    except Exception:
        return str(value)


@app.template_filter('format_time')
def format_time(value):
    if not value:
        return '—'
    return str(value)[:5]


@app.template_filter('cap')
def capitalize_filter(value):
    if not value:
        return ''
    return value.title()


# ── Auth helpers ──────────────────────────────────────────────────────────────

def _parse_time(s: str | None) -> _time | None:
    if not s:
        return None
    parts = s.split(':')
    return _time(int(parts[0]), int(parts[1]))


def _require_admin():
    if session.get('user_role') != 'admin':
        return redirect(url_for('login'))
    return None


def _require_responsable():
    if session.get('user_role') != 'responsable':
        return redirect(url_for('login'))
    return None


def _require_tutor():
    if session.get('user_role') != 'tutor':
        return redirect(url_for('login'))
    return None


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        user = repo.buscar_usuario_por_email(email)
        if user and repo.verificar_password(user, password):
            session['user_id']    = user['id']
            session['user_role']  = user['role']
            session['user_name']  = f"{user['first_name']} {user['last_name']}"
            session['user_email'] = user['email']

            if user['role'] == 'admin':
                return redirect(url_for('dashboard'))
            elif user['role'] == 'responsable':
                return redirect(url_for('lookup'))
            else:
                return redirect(url_for('tutor_dashboard'))
        else:
            flash('Correo o contraseña incorrectos.', 'error')

    return render_template('auth/login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/cambiar-contrasena', methods=['GET', 'POST'])
def change_password():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        new_pwd     = request.form.get('new_password', '')
        confirm_pwd = request.form.get('confirm_password', '')

        if new_pwd != confirm_pwd:
            flash('Las contraseñas no coinciden.', 'error')
        elif len(new_pwd) < 8:
            flash('La contraseña debe tener al menos 8 caracteres.', 'error')
        else:
            hashed = generate_password_hash(new_pwd)
            try:
                repo.cambiar_password(session['user_role'], session['user_id'], hashed)
                flash('Contraseña actualizada correctamente.', 'success')
                role = session['user_role']
                if role == 'admin':
                    return redirect(url_for('dashboard'))
                elif role == 'responsable':
                    return redirect(url_for('lookup'))
                else:
                    return redirect(url_for('tutor_dashboard'))
            except ValueError as e:
                flash(str(e), 'error')

    return render_template('auth/change_password.html')


# ── Public / Landing ──────────────────────────────────────────────────────────

@app.route('/')
def landing():
    stats = {
        'aplicaciones': len(repo.listar_aplicaciones()),
        'centros':       len(repo.listar_centros()),
        'esquemas':      len(repo.listar_esquemas()),
    }
    return render_template('public/landing.html', stats=stats)


@app.route('/esquemas')
def schemes():
    return render_template('public/schemes.html', esquemas=repo.listar_esquemas(), days_to_human=days_to_human)


@app.route('/esquemas/<int:esquema_id>/dosis')
def scheme_doses(esquema_id):
    dosis = repo.dosis_de_esquema(esquema_id)
    for d in dosis:
        if 'vacuna_nombre' not in d:
            vac = repo.obtener_vacuna(d['vacuna_id'])
            d['vacuna_nombre'] = vac['vacuna_nombre'] if vac else '—'
        d['edad_texto'] = days_to_human(d['dosis_edad_oportuna_dias'])
    dosis.sort(key=lambda x: x['dosis_edad_oportuna_dias'])
    return jsonify(dosis)


@app.route('/api/stats-publicas')
def api_stats_publicas():
    desde = '2000-01-01'
    hasta = '2099-12-31'
    por_mes    = repo.chart_por_mes(desde, hasta)
    top_vacunas = repo.chart_top_vacunas(desde, hasta)
    for r in por_mes:
        r.pop('mes_orden', None)
    return jsonify({'por_mes': por_mes, 'top_vacunas': top_vacunas})


@app.route('/tutor')
def tutor_dashboard():
    redir = _require_tutor()
    if redir:
        return redir
    hijos = repo.pacientes_de_tutor(session['user_id'])
    return render_template('public/tutor_dashboard.html', hijos=hijos)


@app.route('/tutor/historial/<int:paciente_id>')
def child_history(paciente_id):
    redir = _require_tutor()
    if redir:
        return redir
    tutor_id = session['user_id']
    if not repo.existe_relacion(paciente_id, tutor_id):
        return redirect(url_for('tutor_dashboard'))

    paciente   = repo.obtener_paciente(paciente_id)
    hijos      = repo.pacientes_de_tutor(tutor_id)
    birth_date = paciente['paciente_fecha_nac']
    rows       = repo.historial_vacunacion_paciente(paciente_id, paciente['esquema_id'])
    historial  = enrich_history(rows, birth_date)

    return render_template('public/child_history.html',
                           paciente=paciente, hijos=hijos, historial=historial)


@app.route('/api/historial/<int:paciente_id>')
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


@app.route('/tutor/centros')
def find_centers():
    redir = _require_tutor()
    if redir:
        return redir
    hijos = [{'paciente_id': p['paciente_id'],
               'paciente_prim_nombre': p['paciente_prim_nombre'],
               'paciente_apellido_pat': p['paciente_apellido_pat']}
              for p in repo.pacientes_de_tutor(session['user_id'])]
    return render_template('public/find_centers.html', vacunas=repo.listar_vacunas(), hijos=hijos)


@app.route('/api/centros-cercanos')
def api_nearby_centers():
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


@app.route('/api/beacon/info')
def api_beacon_info():
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
                        'vacuna_nombre':      dosis['vacuna_nombre'],
                        'stock_total':        vacunas_centro[vid]['stock_total'],
                        'hijos':              [],
                        'personas_esperando': 0,
                    }
                vacunas_result[vid]['hijos'].append({
                    'nombre':       nombre_hijo,
                    'status':       dosis['status'],
                    'status_label': dosis['status_label'],
                })

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


@app.route('/tutor/perfil')
def tutor_profile():
    redir = _require_tutor()
    if redir:
        return redir
    tutor = repo.obtener_tutor(session['user_id'])
    return render_template('public/profile.html', tutor=tutor)


@app.route('/tutor/perfil/foto', methods=['POST'])
def subir_foto_tutor():
    redir = _require_tutor()
    if redir:
        return redir
    file = request.files.get('foto')
    if not file or file.filename == '':
        return redirect(url_for('tutor_profile'))
    if not _allowed_file(file.filename):
        return redirect(url_for('tutor_profile'))
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"usuario_{session['user_id']}.{ext}"
    upload_dir = os.path.join(app.static_folder, 'uploads', 'fotos')
    os.makedirs(upload_dir, exist_ok=True)
    file.save(os.path.join(upload_dir, filename))
    repo.actualizar_imagen_usuario(session['user_id'], f"uploads/fotos/{filename}")
    return redirect(url_for('tutor_profile'))


# ── Clinical ──────────────────────────────────────────────────────────────────

@app.route('/clinico')
def lookup():
    redir = _require_responsable()
    if redir:
        return redir
    return render_template('clinical/patient_lookup.html')


@app.route('/clinico/api/nfc', methods=['POST'])
def api_scan_nfc():
    import re
    uid_raw  = request.json.get('uid', '').strip()
    clean    = re.sub(r'[:\-\s]', '', uid_raw).lower()
    uid_norm = ':'.join(clean[i:i+2] for i in range(0, len(clean), 2)) if clean else uid_raw
    paciente = repo.obtener_paciente_por_nfc(uid_norm) or repo.obtener_paciente_por_nfc(uid_raw)
    if not paciente:
        return jsonify({'error': 'Paciente no encontrado'}), 404
    return _patient_response(paciente)


@app.route('/clinico/api/curp', methods=['POST'])
def api_search_curp():
    curp     = request.json.get('curp', '').strip().upper()
    paciente = repo.obtener_paciente_por_curp(curp)
    if not paciente:
        return jsonify({'error': 'Paciente no encontrado'}), 404
    return _patient_response(paciente)


@app.route('/clinico/api/cert-nac', methods=['POST'])
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


@app.route('/clinico/registrar', methods=['GET', 'POST'])
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
            return redirect(url_for('register_application'))

        inv = repo.obtener_inventario(inventario_id)
        if not inv or not inv.get('inventario_activo') or inv['inventario_stock_actual'] <= 0:
            flash('No hay stock disponible en el inventario seleccionado.', 'error')
            return redirect(url_for('register_application'))

        if repo.dosis_ya_aplicada(paciente_id, dosis_id):
            flash('Esta dosis ya fue aplicada a este paciente.', 'error')
            return redirect(url_for('register_application'))

        paciente = repo.obtener_paciente(paciente_id)
        dosis    = repo.obtener_dosis(dosis_id)

        if paciente and dosis:
            aplicaciones_previas = repo.aplicaciones_de_paciente(paciente_id)
            ok, error_msg = validar_aplicacion(paciente, dosis, aplicaciones_previas)
            if not ok:
                flash(error_msg, 'error')
                return redirect(url_for('register_application'))

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
        return redirect(url_for('lookup'))

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


@app.route('/clinico/api/dosis-por-inventario/<int:inventario_id>')
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


@app.route('/clinico/api/dosis-aplicables/<int:paciente_id>')
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
            'dosis_id':      r['dosis_id'],
            'vacuna_nombre': r.get('vacuna_nombre', ''),
            'dosis_tipo':    r.get('dosis_tipo', ''),
            'status':        r['status'],
            'status_label':  r['status_label'],
        }
        for r in enriched
        if r['status'] in ('aplicable', 'atrasada', 'cerca_limite')
    ]
    return jsonify(aplicables)


@app.route('/clinico/inventario/confirmar', methods=['GET', 'POST'])
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
        return redirect(url_for('confirmar_inventario'))

    pendientes = repo.inventarios_pendientes_de_centro(centro_id) if centro_id else []
    return render_template('clinical/confirmar_inventario.html',
                           pendientes=pendientes,
                           responsable=responsable)


@app.route('/clinico/perfil')
def profile():
    redir = _require_responsable()
    if redir:
        return redir
    responsable = repo.obtener_responsable(session['user_id'])
    cedulas     = repo.cedulas_de_responsable(session['user_id'])
    return render_template('clinical/profile.html', responsable=responsable, cedulas=cedulas)


@app.route('/clinico/perfil/foto', methods=['POST'])
def clinical_subir_foto_perfil():
    redir = _require_responsable()
    if redir:
        return redir
    file = request.files.get('foto')
    if not file or file.filename == '':
        flash('Selecciona una imagen.', 'error')
        return redirect(url_for('profile'))
    if not _allowed_file(file.filename):
        flash('Formato no permitido. Usa PNG, JPG, GIF o WebP.', 'error')
        return redirect(url_for('profile'))
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"usuario_{session['user_id']}.{ext}"
    upload_dir = os.path.join(app.static_folder, 'uploads', 'fotos')
    os.makedirs(upload_dir, exist_ok=True)
    file.save(os.path.join(upload_dir, filename))
    repo.actualizar_imagen_usuario(session['user_id'], f"uploads/fotos/{filename}")
    flash('Foto de perfil actualizada.', 'success')
    return redirect(url_for('profile'))


# ── Admin ─────────────────────────────────────────────────────────────────────

@app.route('/admin')
@app.route('/admin/dashboard')
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

    _hasta = date.today().isoformat()
    _desde = (date.today().replace(year=date.today().year - 2)).isoformat()
    meses_data = repo.chart_por_mes(_desde, _hasta)
    for r in meses_data:
        r.pop('mes_orden', None)
    chart_labels = _json.dumps([r['mes'] for r in meses_data])
    chart_data   = _json.dumps([r['total'] for r in meses_data])

    return render_template('admin/dashboard.html', stats=stats, alertas=alertas[:10],
                           chart_labels=chart_labels, chart_data=chart_data)


@app.route('/admin/tutores', methods=['GET', 'POST'])
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
        return redirect(url_for('tutores'))
    return render_template('admin/tutores.html', tutores=repo.listar_tutores())


@app.route('/admin/tutores/<int:tid>/editar', methods=['POST'])
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
    return redirect(url_for('tutores'))


@app.route('/admin/tutores/<int:tid>/eliminar', methods=['POST'])
def eliminar_tutor(tid):
    redir = _require_admin()
    if redir:
        return redir
    try:
        repo.eliminar_tutor(tid)
        flash('Tutor eliminado.', 'success')
    except ValueError as e:
        flash(str(e), 'error')
    return redirect(url_for('tutores'))


@app.route('/admin/responsables', methods=['GET', 'POST'])
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
        return redirect(url_for('responsables'))
    return render_template('admin/responsables.html',
                           responsables=repo.listar_responsables(),
                           centros=repo.listar_centros())


@app.route('/admin/responsables/<int:rid>/eliminar', methods=['POST'])
def eliminar_responsable(rid):
    redir = _require_admin()
    if redir:
        return redir
    try:
        repo.eliminar_responsable(rid)
        flash('Responsable eliminado.', 'success')
    except ValueError as e:
        flash(str(e), 'error')
    return redirect(url_for('responsables'))


@app.route('/admin/administradores', methods=['GET', 'POST'])
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
        return redirect(url_for('administradores'))
    return render_template('admin/administradores.html', admins=repo.listar_administradores())


@app.route('/admin/administradores/<int:aid>/eliminar', methods=['POST'])
def eliminar_admin(aid):
    redir = _require_admin()
    if redir:
        return redir
    try:
        repo.eliminar_admin(aid, session['user_id'])
        flash('Administrador eliminado.', 'success')
    except ValueError as e:
        flash(str(e), 'error')
    return redirect(url_for('administradores'))


@app.route('/admin/pacientes', methods=['GET', 'POST'])
def pacientes():
    redir = _require_admin()
    if redir:
        return redir
    if request.method == 'POST':
        f    = request.form
        curp = f.get('curp', '').strip().upper() or None
        cert = f.get('num_cert_nac', '').strip() or None
        if not curp and not cert:
            flash('Debes llenar al menos CURP o N° Certificado de Nacimiento.', 'error')
            return redirect(url_for('pacientes'))
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
        return redirect(url_for('pacientes'))
    return render_template('admin/pacientes.html',
                           pacientes=repo.listar_pacientes(),
                           esquemas=repo.listar_esquemas())


@app.route('/admin/pacientes/<int:pid>/eliminar', methods=['POST'])
def eliminar_paciente(pid):
    redir = _require_admin()
    if redir:
        return redir
    try:
        repo.eliminar_paciente(pid)
        flash('Paciente eliminado.', 'success')
    except ValueError as e:
        flash(str(e), 'error')
    return redirect(url_for('pacientes'))


@app.route('/admin/relaciones', methods=['GET', 'POST'])
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
        return redirect(url_for('relaciones'))
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


@app.route('/admin/relaciones/<int:rid>/eliminar', methods=['POST'])
def eliminar_relacion(rid):
    redir = _require_admin()
    if redir:
        return redir
    repo.eliminar_relacion(rid)
    flash('Relación eliminada.', 'success')
    return redirect(url_for('relaciones'))


@app.route('/admin/centros', methods=['GET', 'POST'])
def centros():
    redir = _require_admin()
    if redir:
        return redir
    if request.method == 'POST':
        f = request.form
        datos = {
            'centro_nombre':         f['nombre'],
            'centro_calle':          f.get('calle') or None,
            'centro_numero':         f.get('numero') or None,
            'centro_codigo_postal':  f.get('cp') or None,
            'ciudad_id':             int(f['ciudad_id']),
            'centro_horario_inicio': _parse_time(f.get('horario_inicio')),
            'centro_horario_fin':    _parse_time(f.get('horario_fin')),
            'centro_latitud':        float(f['latitud']) if f.get('latitud') else None,
            'centro_longitud':       float(f['longitud']) if f.get('longitud') else None,
            'centro_telefono':       f.get('telefono') or None,
            'centro_beacon':         f.get('beacon') or None,
        }
        try:
            repo.crear_centro(datos)
            flash('Centro de salud registrado.', 'success')
        except ValueError as e:
            flash(str(e), 'error')
        return redirect(url_for('centros'))
    return render_template('admin/centros.html',
                           centros=repo.listar_centros(),
                           ciudades=repo.listar_ciudades())


@app.route('/admin/centros/<int:cid>/eliminar', methods=['POST'])
def eliminar_centro(cid):
    redir = _require_admin()
    if redir:
        return redir
    try:
        repo.eliminar_centro(cid)
        flash('Centro eliminado.', 'success')
    except ValueError as e:
        flash(str(e), 'error')
    return redirect(url_for('centros'))


@app.route('/admin/esquemas', methods=['GET', 'POST'])
def esquemas():
    redir = _require_admin()
    if redir:
        return redir

    if request.method == 'POST':
        f = request.form
        nombre              = f.get('nombre', '').strip()
        fecha_vigencia      = date.fromisoformat(f['fecha_vigencia'])
        esquema_anterior_id = f.get('esquema_anterior_id', type=int)
        dosis_seleccionadas = set(f.getlist('dosis_ids', type=int))

        nuevas_vacunas    = f.getlist('nueva_vacuna_id',      type=int)
        nuevas_tipos      = f.getlist('nueva_tipo')
        nuevas_ml         = f.getlist('nueva_cant_ml')
        nuevas_areas      = f.getlist('nueva_area')
        nuevas_edades     = f.getlist('nueva_edad_dias',      type=int)
        nuevas_intervalos = f.getlist('nueva_intervalo_dias', type=int)
        nuevas_limites    = f.getlist('nueva_limite_dias')

        try:
            nuevo    = repo.crear_esquema({'esquema_nombre': nombre,
                                           'esquema_fecha_vigencia': fecha_vigencia,
                                           'vigente_desde': date.today()})
            nuevo_id = nuevo['esquema_id']

            for i, vacuna_id in enumerate(nuevas_vacunas):
                if not vacuna_id:
                    continue
                limite_raw = nuevas_limites[i] if i < len(nuevas_limites) else ''
                d = repo.crear_dosis({
                    'vacuna_id':                vacuna_id,
                    'dosis_tipo':               nuevas_tipos[i] if i < len(nuevas_tipos) else 'UNICA',
                    'dosis_cant_ml':            float(nuevas_ml[i]) if i < len(nuevas_ml) and nuevas_ml[i] else 0.5,
                    'dosis_area_aplicacion':    nuevas_areas[i] if i < len(nuevas_areas) else '',
                    'dosis_edad_oportuna_dias': nuevas_edades[i] if i < len(nuevas_edades) else 0,
                    'dosis_intervalo_min_dias': nuevas_intervalos[i] if i < len(nuevas_intervalos) else 0,
                    'dosis_limite_edad_dias':   int(limite_raw) if limite_raw else None,
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

        return redirect(url_for('esquemas'))

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


@app.route('/admin/esquemas/<int:eid>/eliminar', methods=['POST'])
def eliminar_esquema(eid):
    redir = _require_admin()
    if redir:
        return redir
    try:
        repo.eliminar_esquema(eid)
        flash('Esquema eliminado.', 'success')
    except ValueError as e:
        flash(str(e), 'error')
    return redirect(url_for('esquemas'))


@app.route('/admin/esquemas/conflicto/resolver', methods=['POST'])
def resolver_conflicto_esquema():
    redir = _require_admin()
    if redir:
        return redir
    paciente_id      = request.form.get('paciente_id', type=int)
    esquema_nuevo_id = request.form.get('esquema_nuevo_id', type=int)
    accion           = request.form.get('accion')
    r = repo.resolver_conflicto_esquema(paciente_id, esquema_nuevo_id, accion)
    if r.get('p_ok') == 1:
        flash(r.get('p_msg', 'Resuelto.'), 'success')
    else:
        flash(r.get('p_msg', 'Error al resolver conflicto.'), 'error')
    return redirect(url_for('esquemas') + '#tab-conflictos')


@app.route('/admin/vacunas', methods=['GET', 'POST'])
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
        return redirect(url_for('vacunas'))

    todas_dosis  = repo.listar_dosis()
    vacunas_list = []
    for v in repo.listar_vacunas():
        v2 = dict(v)
        v2['dosis'] = [d for d in todas_dosis if d['vacuna_id'] == v['vacuna_id']]
        vacunas_list.append(v2)
    return render_template('admin/vacunas.html',
                           vacunas=vacunas_list,
                           dosis_tipos=DOSIS_TIPOS,
                           days_to_human=days_to_human)


@app.route('/admin/api/vacuna/<int:vid>/dosis')
def api_vacuna_dosis(vid):
    return jsonify(repo.listar_dosis(vacuna_id=vid))


@app.route('/admin/padecimientos', methods=['GET', 'POST'])
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
        return redirect(url_for('padecimientos'))
    return render_template('admin/padecimientos.html',
                           padecimientos=repo.listar_padecimientos(),
                           vacunas=repo.listar_vacunas())


@app.route('/admin/fabricantes', methods=['GET', 'POST'])
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
                    'proveedor_prim_nombre':  f['prim_nombre'],
                    'proveedor_seg_nombre':   f.get('seg_nombre') or None,
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
        return redirect(url_for('fabricantes'))
    return render_template('admin/fabricantes.html',
                           fabricantes=repo.listar_fabricantes(),
                           proveedores=repo.listar_proveedores(),
                           paises=repo.listar_paises())


@app.route('/admin/lotes', methods=['GET', 'POST'])
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
                    'centro_id':               int(f['centro_id']),
                    'lote_id':                 int(f['lote_id']),
                    'inventario_stock_inicial': int(f['stock']),
                    'inventario_stock_actual':  int(f['stock']),
                    'inventario_activo_desde':  None,
                })
                flash('Inventario asignado. El responsable del centro debe confirmar su recepción.', 'success')
            except ValueError as e:
                flash(str(e), 'error')

        return redirect(url_for('lotes'))

    return render_template('admin/lotes.html',
                           lotes=repo.listar_lotes(),
                           inventarios=repo.listar_inventarios(),
                           vacunas=repo.listar_vacunas(),
                           fabricantes=repo.listar_fabricantes(),
                           proveedores=repo.listar_proveedores(),
                           centros=repo.listar_centros())


@app.route('/admin/inventario', methods=['GET', 'POST'])
def inventario():
    redir = _require_admin()
    if redir:
        return redir
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
        return redirect(url_for('inventario'))
    return render_template('admin/inventario.html',
                           inventarios=repo.listar_inventarios(),
                           transferencias=repo.listar_transferencias(),
                           centros=repo.listar_centros(),
                           alertas_inv=repo.listar_alertas_inventario(),
                           alertas_dosis=repo.listar_alertas_dosis(),
                           today=date.today())


@app.route('/admin/api/inventarios-activos-centro/<int:centro_id>')
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


@app.route('/admin/aplicaciones', methods=['GET', 'POST'])
def aplicaciones():
    redir = _require_admin()
    if redir:
        return redir
    if request.method == 'POST':
        f = request.form
        if not f.get('paciente_id') or not f.get('dosis_id') or not f.get('inventario_id') or not f.get('responsable_id'):
            flash('Todos los campos son obligatorios.', 'error')
            return redirect(url_for('aplicaciones'))

        inventario_id = int(f['inventario_id'])
        inv = repo.obtener_inventario(inventario_id)
        if not inv or not inv.get('inventario_activo') or inv['inventario_stock_actual'] <= 0:
            flash('No hay stock disponible en el inventario seleccionado.', 'error')
            return redirect(url_for('aplicaciones'))

        pid = int(f['paciente_id'])
        did = int(f['dosis_id'])
        if repo.dosis_ya_aplicada(pid, did):
            flash('Esta dosis ya fue aplicada a este paciente.', 'error')
            return redirect(url_for('aplicaciones'))

        pac = repo.obtener_paciente(pid)
        dos = repo.obtener_dosis(did)

        if pac and dos:
            aplicaciones_previas = repo.aplicaciones_de_paciente(pid)
            ok, error_msg = validar_aplicacion(pac, dos, aplicaciones_previas)
            if not ok:
                flash(error_msg, 'error')
                return redirect(url_for('aplicaciones'))

        resp_id = int(f['responsable_id'])

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
        return redirect(url_for('aplicaciones'))

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


@app.route('/admin/geografia', methods=['GET', 'POST'])
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
        return redirect(url_for('geografia'))
    return render_template('admin/geografia.html',
                           paises=repo.listar_paises(),
                           estados=repo.listar_estados(),
                           ciudades=repo.listar_ciudades())


@app.route('/admin/api/estados/<int:pais_id>')
def api_estados(pais_id):
    return jsonify(repo.listar_estados(pais_id=pais_id))


@app.route('/admin/api/ciudades/<int:estado_id>')
def api_ciudades(estado_id):
    return jsonify(repo.listar_ciudades(estado_id=estado_id))


@app.route('/admin/reportes')
def reportes():
    redir = _require_admin()
    if redir:
        return redir
    return render_template('admin/reportes.html',
                           centros=repo.listar_centros(),
                           vacunas=repo.listar_vacunas(),
                           esquemas=repo.listar_esquemas())


@app.route('/admin/api/reporte-datos')
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


@app.route('/admin/perfil')
def perfil():
    redir = _require_admin()
    if redir:
        return redir
    admin = repo.obtener_administrador(session['user_id'])
    return render_template('admin/perfil.html', admin=admin)


@app.route('/admin/perfil/foto', methods=['POST'])
def admin_subir_foto_perfil():
    redir = _require_admin()
    if redir:
        return redir
    file = request.files.get('foto')
    if not file or file.filename == '':
        flash('Selecciona una imagen.', 'error')
        return redirect(url_for('perfil'))
    if not _allowed_file(file.filename):
        flash('Formato no permitido. Usa PNG, JPG, GIF o WebP.', 'error')
        return redirect(url_for('perfil'))
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"usuario_{session['user_id']}.{ext}"
    upload_dir = os.path.join(app.static_folder, 'uploads', 'fotos')
    os.makedirs(upload_dir, exist_ok=True)
    file.save(os.path.join(upload_dir, filename))
    repo.actualizar_imagen_usuario(session['user_id'], f"uploads/fotos/{filename}")
    flash('Foto de perfil actualizada.', 'success')
    return redirect(url_for('perfil'))


@app.route('/admin/pacientes/<int:pid>/foto', methods=['POST'])
def subir_foto_paciente(pid):
    redir = _require_admin()
    if redir:
        return redir
    file = request.files.get('foto')
    if not file or file.filename == '':
        flash('Selecciona una imagen.', 'error')
        return redirect(url_for('pacientes'))
    if not _allowed_file(file.filename):
        flash('Formato no permitido. Usa PNG, JPG, GIF o WebP.', 'error')
        return redirect(url_for('pacientes'))
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"paciente_{pid}.{ext}"
    upload_dir = os.path.join(app.static_folder, 'uploads', 'fotos')
    os.makedirs(upload_dir, exist_ok=True)
    file.save(os.path.join(upload_dir, filename))
    repo.actualizar_imagen_paciente(pid, f"uploads/fotos/{filename}")
    flash('Foto del paciente actualizada.', 'success')
    return redirect(url_for('pacientes'))


if __name__ == '__main__':
    app.run(debug=True, port=5000)

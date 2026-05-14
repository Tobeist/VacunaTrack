from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash
import db
from utils.helpers import enrich_history, days_to_human

clinical_bp = Blueprint('clinical', __name__, url_prefix='/clinico')


def _require_responsable():
    if session.get('user_role') != 'responsable':
        return redirect(url_for('auth.login'))
    return None


@clinical_bp.route('/')
def lookup():
    redir = _require_responsable()
    if redir: return redir
    return render_template('clinical/patient_lookup.html')


@clinical_bp.route('/api/buscar-nfc', methods=['POST'])
def api_scan_nfc():
    """AJAX: lookup patient by NFC UID."""
    nfc_uid = request.json.get('nfc_uid', '').strip()
    if not nfc_uid:
        return jsonify({'error': 'UID vacío'}), 400
    return _patient_response('paciente_nfc', nfc_uid)


@clinical_bp.route('/api/buscar-curp', methods=['POST'])
def api_search_curp():
    """AJAX: lookup patient by CURP."""
    curp = request.json.get('curp', '').strip().upper()
    if not curp:
        return jsonify({'error': 'CURP vacío'}), 400
    return _patient_response('paciente_curp', curp)


def _patient_response(field, value):
    paciente = db.query(
        f"SELECT * FROM pacientes WHERE {field} = %s", (value,), fetch='one'
    )
    if not paciente:
        return jsonify({'error': 'Paciente no encontrado'}), 404

    paciente_id = paciente['paciente_id']
    birth_date  = paciente['paciente_fecha_nac']

    rows = db.query("""
        SELECT v.vacuna_nombre,
               d.dosis_id, d.dosis_tipo, d.dosis_edad_oportuna_dias,
               d.dosis_limite_edad_dias, d.dosis_area_aplicacion, d.dosis_cant_ml,
               a.aplicacion_timestamp, a.aplicacion_observaciones,
               r.responsable_prim_nombre || ' ' || r.responsable_apellido_pat AS responsable,
               cs.centro_nombre
        FROM dosis_esquemas de
        JOIN dosis d ON de.dosis_id = d.dosis_id
        JOIN vacunas v ON d.vacuna_id = v.vacuna_id
        LEFT JOIN aplicaciones a ON a.dosis_id = d.dosis_id AND a.paciente_id = %s
        LEFT JOIN responsables r ON a.responsable_id = r.responsable_id
        LEFT JOIN inventarios inv ON a.inventario_id = inv.inventario_id
        LEFT JOIN centros_salud cs ON inv.centro_id = cs.centro_id
        WHERE de.esquema_id = %s
        ORDER BY v.vacuna_nombre, d.dosis_edad_oportuna_dias
    """, (paciente_id, paciente['esquema_id']))

    enriched = enrich_history(rows, birth_date)
    for r in enriched:
        if r.get('aplicacion_timestamp'):
            r['aplicacion_timestamp'] = str(r['aplicacion_timestamp'])
        r['edad_texto'] = days_to_human(r['dosis_edad_oportuna_dias'])

    from datetime import date
    age_days = (date.today() - birth_date).days

    return jsonify({
        'paciente': {
            'id': paciente_id,
            'nombre': f"{paciente['paciente_prim_nombre']} {paciente.get('paciente_nombre','') or ''} {paciente['paciente_apellido_pat']} {paciente['paciente_apellido_mat']}".strip(),
            'fecha_nac': str(birth_date),
            'edad_dias': age_days,
            'edad_texto': days_to_human(age_days),
            'sexo': paciente['paciente_sexo'],
            'curp': paciente['paciente_curp'],
            'nfc': paciente['paciente_nfc'],
            'esquema_id': paciente['esquema_id'],
        },
        'historial': enriched
    })


@clinical_bp.route('/registrar', methods=['GET', 'POST'])
def register_application():
    redir = _require_responsable()
    if redir: return redir

    responsable_id = session['user_id']

    # Get this responsable's centro_id
    resp = db.query(
        "SELECT centro_id FROM responsables WHERE responsable_id = %s",
        (responsable_id,), fetch='one'
    )
    centro_id = resp['centro_id'] if resp else None

    if request.method == 'POST':
        paciente_id   = request.form.get('paciente_id')
        dosis_id      = request.form.get('dosis_id')
        inventario_id = request.form.get('inventario_id')
        observaciones = request.form.get('observaciones', '')

        # ── Validar campos obligatorios ──────────────────────────────────────
        if not paciente_id or not dosis_id or not inventario_id:
            flash('Debes seleccionar paciente, inventario y dosis.', 'error')
            return redirect(url_for('clinical.register_application'))

        # ── Validar stock disponible ──────────────────────────────────────────
        inv_check = db.query(
            "SELECT inventario_stock_actual FROM inventarios WHERE inventario_id = %s AND inventario_activo = TRUE",
            (inventario_id,), fetch='one'
        )
        if not inv_check or inv_check['inventario_stock_actual'] <= 0:
            flash('No hay stock disponible en el inventario seleccionado.', 'error')
            return redirect(url_for('clinical.register_application'))

        # ── Validar que esta dosis NO haya sido ya aplicada a este paciente ──
        ya_aplicada = db.query("""
            SELECT aplicacion_id FROM aplicaciones
            WHERE paciente_id = %s AND dosis_id = %s
            LIMIT 1
        """, (paciente_id, dosis_id), fetch='one')

        if ya_aplicada:
            flash('Esta dosis ya fue aplicada anteriormente a este paciente.', 'error')
            return redirect(url_for('clinical.register_application') + f'?paciente_id={paciente_id}')

        db.execute("""
            INSERT INTO aplicaciones (paciente_id, responsable_id, inventario_id, dosis_id, aplicacion_observaciones)
            VALUES (%s, %s, %s, %s, %s)
        """, (paciente_id, responsable_id, inventario_id, dosis_id, observaciones))

        # Decrement inventory stock
        db.execute("""
            UPDATE inventarios SET inventario_stock_actual = inventario_stock_actual - 1
            WHERE inventario_id = %s
        """, (inventario_id,))

        # Auto-deactivate if stock reaches 0
        db.execute("""
            UPDATE inventarios SET inventario_activo = FALSE
            WHERE inventario_id = %s AND inventario_stock_actual <= 0
        """, (inventario_id,))

        flash('Aplicación registrada correctamente.', 'success')
        return redirect(url_for('clinical.lookup'))

    # GET: load inventories for this center
    inventarios = db.query("""
        SELECT inv.inventario_id, v.vacuna_nombre, l.lote_codigo,
               l.lote_fecha_caducidad, inv.inventario_stock_actual
        FROM inventarios inv
        JOIN lotes l ON inv.lote_id = l.lote_id
        JOIN vacunas v ON l.vacuna_id = v.vacuna_id
        WHERE inv.centro_id = %s AND inv.inventario_activo = TRUE
          AND inv.inventario_stock_actual > 0
        ORDER BY v.vacuna_nombre
    """, (centro_id,)) if centro_id else []

    pacientes = db.query("""
        SELECT p.paciente_id,
               p.paciente_prim_nombre || ' ' || p.paciente_apellido_pat AS nombre
        FROM pacientes p ORDER BY nombre
    """)

    return render_template('clinical/register_application.html',
                           inventarios=inventarios,
                           pacientes=pacientes)


@clinical_bp.route('/api/dosis-por-inventario/<int:inventario_id>')
def api_dosis_por_inventario(inventario_id):
    """Devuelve las dosis de la vacuna asociada al inventario seleccionado."""
    dosis = db.query("""
        SELECT d.dosis_id, v.vacuna_nombre, d.dosis_tipo::text,
               d.dosis_edad_oportuna_dias, d.dosis_area_aplicacion
        FROM inventarios inv
        JOIN lotes l ON inv.lote_id = l.lote_id
        JOIN vacunas v ON l.vacuna_id = v.vacuna_id
        JOIN dosis d ON d.vacuna_id = v.vacuna_id
        WHERE inv.inventario_id = %s
        ORDER BY v.vacuna_nombre, d.dosis_edad_oportuna_dias
    """, (inventario_id,))
    return jsonify(dosis)


@clinical_bp.route('/perfil')
def profile():
    redir = _require_responsable()
    if redir: return redir
    resp = db.query("SELECT * FROM responsables WHERE responsable_id = %s",
                    (session['user_id'],), fetch='one')
    cedulas = db.query("SELECT * FROM cedulas WHERE responsable_id = %s",
                       (session['user_id'],))
    centro = None
    if resp and resp.get('centro_id'):
        centro = db.query("SELECT centro_nombre FROM centros_salud WHERE centro_id = %s",
                          (resp['centro_id'],), fetch='one')
    return render_template('clinical/profile.html', resp=resp, cedulas=cedulas, centro=centro)

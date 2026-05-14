from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
import db
from utils.helpers import enrich_history, days_to_human

public_bp = Blueprint('public', __name__)


def _require_tutor():
    if session.get('user_role') != 'tutor':
        return redirect(url_for('auth.login'))
    return None


# ── Public (no login) ────────────────────────────────────────────────────────

@public_bp.route('/')
def landing():
    stats = {
        'aplicaciones': db.query("SELECT COUNT(*) AS c FROM aplicaciones", fetch='one')['c'] or 0,
        'centros': db.query("SELECT COUNT(*) AS c FROM centros_salud", fetch='one')['c'] or 0,
        'esquemas': db.query("SELECT COUNT(*) AS c FROM esquemas", fetch='one')['c'] or 0,
    }
    return render_template('public/landing.html', stats=stats)


@public_bp.route('/esquemas')
def schemes():
    esquemas = db.query("""
        SELECT e.esquema_id, e.esquema_nombre, e.esquema_fecha_vigencia,
               COUNT(de.dosis_id) AS total_dosis
        FROM esquemas e
        LEFT JOIN dosis_esquemas de ON e.esquema_id = de.esquema_id
        GROUP BY e.esquema_id
        ORDER BY e.esquema_fecha_vigencia DESC
    """)
    return render_template('public/schemes.html', esquemas=esquemas, days_to_human=days_to_human)


@public_bp.route('/esquemas/<int:esquema_id>/dosis')
def scheme_doses(esquema_id):
    dosis = db.query("""
        SELECT v.vacuna_nombre, d.dosis_tipo, d.dosis_edad_oportuna_dias,
               d.dosis_limite_edad_dias, d.dosis_intervalo_min_dias,
               d.dosis_area_aplicacion, d.dosis_cant_ml
        FROM dosis_esquemas de
        JOIN dosis d ON de.dosis_id = d.dosis_id
        JOIN vacunas v ON d.vacuna_id = v.vacuna_id
        WHERE de.esquema_id = %s
        ORDER BY v.vacuna_nombre, d.dosis_edad_oportuna_dias
    """, (esquema_id,))
    result = [dict(r, edad_texto=days_to_human(r['dosis_edad_oportuna_dias'])) for r in dosis]
    return jsonify(result)


# ── Tutor (requires login) ───────────────────────────────────────────────────

@public_bp.route('/tutor')
def tutor_dashboard():
    redir = _require_tutor()
    if redir: return redir

    tutor_id = session['user_id']
    hijos = db.query("""
        SELECT p.paciente_id, p.paciente_prim_nombre, p.paciente_nombre,
               p.paciente_apellido_pat, p.paciente_apellido_mat,
               p.paciente_fecha_nac, p.paciente_sexo, e.esquema_nombre
        FROM pacientes_tutores pt
        JOIN pacientes p ON pt.paciente_id = p.paciente_id
        JOIN esquemas e ON p.esquema_id = e.esquema_id
        WHERE pt.tutor_id = %s
        ORDER BY p.paciente_prim_nombre
    """, (tutor_id,))
    return render_template('public/tutor_dashboard.html', hijos=hijos)


@public_bp.route('/tutor/historial/<int:paciente_id>')
def child_history(paciente_id):
    redir = _require_tutor()
    if redir: return redir

    tutor_id = session['user_id']
    # Verify this child belongs to this tutor
    link = db.query(
        "SELECT 1 FROM pacientes_tutores WHERE tutor_id = %s AND paciente_id = %s",
        (tutor_id, paciente_id), fetch='one'
    )
    if not link:
        return redirect(url_for('public.tutor_dashboard'))

    paciente = db.query(
        "SELECT *, esquema_id FROM pacientes WHERE paciente_id = %s", (paciente_id,), fetch='one'
    )
    hijos = db.query("""
        SELECT p.paciente_id, p.paciente_prim_nombre, p.paciente_apellido_pat
        FROM pacientes_tutores pt JOIN pacientes p ON pt.paciente_id = p.paciente_id
        WHERE pt.tutor_id = %s
    """, (tutor_id,))

    return render_template('public/child_history.html', paciente=paciente, hijos=hijos)


@public_bp.route('/api/historial/<int:paciente_id>')
def api_child_history(paciente_id):
    """AJAX endpoint – returns vaccination history as JSON."""
    if session.get('user_role') not in ('tutor', 'admin', 'responsable'):
        return jsonify({'error': 'Unauthorized'}), 401

    paciente = db.query(
        "SELECT paciente_fecha_nac, esquema_id FROM pacientes WHERE paciente_id = %s",
        (paciente_id,), fetch='one'
    )
    if not paciente:
        return jsonify([])

    birth_date = paciente['paciente_fecha_nac']
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
    # Convert dates/timestamps to strings
    for r in enriched:
        if r.get('aplicacion_timestamp'):
            r['aplicacion_timestamp'] = str(r['aplicacion_timestamp'])
        from utils.helpers import days_to_human
        r['edad_texto'] = days_to_human(r['dosis_edad_oportuna_dias'])

    return jsonify(enriched)


@public_bp.route('/tutor/centros')
def find_centers():
    redir = _require_tutor()
    if redir: return redir

    vacunas = db.query("SELECT vacuna_id, vacuna_nombre FROM vacunas ORDER BY vacuna_nombre")
    tutor_id = session['user_id']
    hijos = db.query("""
        SELECT p.paciente_id, p.paciente_prim_nombre, p.paciente_apellido_pat
        FROM pacientes_tutores pt JOIN pacientes p ON pt.paciente_id = p.paciente_id
        WHERE pt.tutor_id = %s
    """, (tutor_id,))
    return render_template('public/find_centers.html', vacunas=vacunas, hijos=hijos)


@public_bp.route('/api/centros-cercanos')
def api_nearby_centers():
    """AJAX: returns centers with stock for a given vaccine."""
    vacuna_id = request.args.get('vacuna_id')
    if not vacuna_id:
        return jsonify([])

    centers = db.query("""
        SELECT cs.centro_id, cs.centro_nombre, cs.centro_calle, cs.centro_numero,
               cs.centro_horario_inicio, cs.centro_horario_fin,
               cs.centro_latitud, cs.centro_longitud, cs.centro_telefono,
               c.ciudad_nombre,
               SUM(inv.inventario_stock_actual) AS stock_total
        FROM inventarios inv
        JOIN lotes l ON inv.lote_id = l.lote_id
        JOIN centros_salud cs ON inv.centro_id = cs.centro_id
        JOIN ciudades c ON cs.ciudad_id = c.ciudad_id
        WHERE l.vacuna_id = %s
          AND inv.inventario_activo = TRUE
          AND inv.inventario_stock_actual > 0
          AND l.lote_fecha_caducidad >= CURRENT_DATE
        GROUP BY cs.centro_id, cs.centro_nombre, cs.centro_calle, cs.centro_numero,
                 cs.centro_horario_inicio, cs.centro_horario_fin,
                 cs.centro_latitud, cs.centro_longitud, cs.centro_telefono, c.ciudad_nombre
        HAVING SUM(inv.inventario_stock_actual) > 0
        ORDER BY cs.centro_nombre
    """, (vacuna_id,))
    for c in centers:
        if c.get('centro_horario_inicio'):
            c['centro_horario_inicio'] = str(c['centro_horario_inicio'])
        if c.get('centro_horario_fin'):
            c['centro_horario_fin'] = str(c['centro_horario_fin'])
    return jsonify(centers)


@public_bp.route('/tutor/perfil')
def tutor_profile():
    redir = _require_tutor()
    if redir: return redir
    tutor = db.query(
        "SELECT * FROM tutores WHERE tutor_id = %s", (session['user_id'],), fetch='one'
    )
    return render_template('public/profile.html', tutor=tutor)

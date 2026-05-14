from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash
import db
from utils.helpers import generate_temp_password, days_to_human

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def _fk_error(e):
    """Detecta si el error es por foreign key constraint."""
    return 'ForeignKeyViolation' in str(type(e).__name__) or 'foreign key' in str(e).lower()

DOSIS_TIPOS = ['UNICA', 'SERIE_PRIMARIA', 'REFUERZO', 'ANUAL', 'ADICIONAL']


def _require_admin():
    if session.get('user_role') != 'admin':
        return redirect(url_for('auth.login'))
    return None


@admin_bp.route('/')
@admin_bp.route('/dashboard')
def dashboard():
    redir = _require_admin()
    if redir: return redir
    stats = {
        'pacientes':        db.query("SELECT COUNT(*) AS c FROM pacientes", fetch='one')['c'],
        'tutores':          db.query("SELECT COUNT(*) AS c FROM tutores", fetch='one')['c'],
        'responsables':     db.query("SELECT COUNT(*) AS c FROM responsables", fetch='one')['c'],
        'centros':          db.query("SELECT COUNT(*) AS c FROM centros_salud", fetch='one')['c'],
        'alertas_inv':      db.query("SELECT COUNT(*) AS c FROM alertas_inventario", fetch='one')['c'],
        'alertas_dosis':    db.query("SELECT COUNT(*) AS c FROM alertas_dosis_pacientes", fetch='one')['c'],
        'aplicaciones_hoy': db.query("SELECT COUNT(*) AS c FROM aplicaciones WHERE DATE(aplicacion_timestamp) = CURRENT_DATE", fetch='one')['c'],
    }
    alertas_recientes = db.query("""
        (SELECT 'inventario' AS tipo, alerta_inv_tipo::text AS subtipo,
                alerta_inv_timestamp AS ts, NULL AS paciente
         FROM alertas_inventario ORDER BY alerta_inv_timestamp DESC LIMIT 5)
        UNION ALL
        (SELECT 'dosis' AS tipo, alerta_dosis_pac_tipo::text AS subtipo,
                alerta_dosis_pac_timestamp AS ts,
                p.paciente_prim_nombre || ' ' || p.paciente_apellido_pat AS paciente
         FROM alertas_dosis_pacientes adp
         JOIN pacientes p ON adp.paciente_id = p.paciente_id
         ORDER BY adp.alerta_dosis_pac_timestamp DESC LIMIT 5)
        ORDER BY ts DESC LIMIT 10
    """)
    return render_template('admin/dashboard.html', stats=stats, alertas=alertas_recientes)


@admin_bp.route('/tutores', methods=['GET', 'POST'])
def tutores():
    redir = _require_admin()
    if redir: return redir
    if request.method == 'POST':
        f = request.form
        temp = generate_temp_password()
        try:
            db.execute("""
                INSERT INTO tutores (tutor_prim_nombre, tutor_seg_nombre, tutor_apellido_pat,
                    tutor_apellido_mat, tutor_curp, tutor_email, tutor_telefono, tutor_contrasena)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """, (f['prim_nombre'], f.get('seg_nombre','') or None, f['apellido_pat'],
                  f.get('apellido_mat','') or None, f['curp'].upper(), f['email'],
                  f['telefono'], generate_password_hash(temp)))
            flash(f'Tutor registrado. Contraseña temporal: <strong>{temp}</strong>', 'success')
        except Exception as e:
            flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('admin.tutores'))
    tutores = db.query("SELECT tutor_id, tutor_prim_nombre, tutor_seg_nombre, tutor_apellido_pat, tutor_apellido_mat, tutor_email, tutor_telefono, tutor_curp FROM tutores ORDER BY tutor_apellido_pat")
    return render_template('admin/tutores.html', tutores=tutores)


@admin_bp.route('/tutores/<int:tid>/editar', methods=['POST'])
def editar_tutor(tid):
    redir = _require_admin()
    if redir: return redir
    f = request.form
    try:
        db.execute("""
            UPDATE tutores SET tutor_prim_nombre=%s, tutor_seg_nombre=%s, tutor_apellido_pat=%s,
                tutor_apellido_mat=%s, tutor_email=%s, tutor_telefono=%s, tutor_curp=%s
            WHERE tutor_id=%s
        """, (f['prim_nombre'], f.get('seg_nombre','') or None, f['apellido_pat'],
              f.get('apellido_mat','') or None, f['email'], f['telefono'], f['curp'].upper(), tid))
        flash('Tutor actualizado.', 'success')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    return redirect(url_for('admin.tutores'))


@admin_bp.route('/tutores/<int:tid>/eliminar', methods=['POST'])
def eliminar_tutor(tid):
    redir = _require_admin()
    if redir: return redir
    try:
        db.execute("DELETE FROM tutores WHERE tutor_id = %s", (tid,))
        flash('Tutor eliminado.', 'success')
    except Exception as e:
        if _fk_error(e):
            flash('No se puede eliminar: este tutor tiene pacientes o registros vinculados.', 'error')
        else:
            flash(f'Error al eliminar: {str(e)}', 'error')
    return redirect(url_for('admin.tutores'))


@admin_bp.route('/responsables', methods=['GET', 'POST'])
def responsables():
    redir = _require_admin()
    if redir: return redir
    if request.method == 'POST':
        f = request.form
        temp = generate_temp_password()
        try:
            resp_id = db.query("""
                INSERT INTO responsables (responsable_prim_nombre, responsable_seg_nombre,
                    responsable_apellido_pat, responsable_apellido_mat, responsable_rfc,
                    responsable_email, responsable_telefono, responsable_curp,
                    responsable_contrasena, centro_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING responsable_id
            """, (f['prim_nombre'], f.get('seg_nombre','') or None, f['apellido_pat'],
                  f.get('apellido_mat','') or None, f['rfc'].upper(), f['email'],
                  f['telefono'], f['curp'].upper(), generate_password_hash(temp),
                  f['centro_id']), fetch='one')
            if resp_id:
                for num, spec in zip(request.form.getlist('cedula_numero'), request.form.getlist('cedula_especialidad')):
                    if num.strip():
                        db.execute("INSERT INTO cedulas (cedula_numero, cedula_especialidad, responsable_id) VALUES (%s,%s,%s)",
                                   (num.strip(), spec.strip() or None, resp_id['responsable_id']))
            flash(f'Responsable registrado. Contraseña temporal: <strong>{temp}</strong>', 'success')
        except Exception as e:
            flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('admin.responsables'))
    responsables = db.query("""
        SELECT r.responsable_id, r.responsable_prim_nombre, r.responsable_apellido_pat,
               r.responsable_rfc, r.responsable_email, cs.centro_nombre,
               COUNT(c.cedula_id) AS total_cedulas
        FROM responsables r
        LEFT JOIN centros_salud cs ON r.centro_id = cs.centro_id
        LEFT JOIN cedulas c ON r.responsable_id = c.responsable_id
        GROUP BY r.responsable_id, cs.centro_nombre ORDER BY r.responsable_apellido_pat
    """)
    centros = db.query("SELECT centro_id, centro_nombre FROM centros_salud ORDER BY centro_nombre")
    return render_template('admin/responsables.html', responsables=responsables, centros=centros)


@admin_bp.route('/responsables/<int:rid>/eliminar', methods=['POST'])
def eliminar_responsable(rid):
    redir = _require_admin()
    if redir: return redir
    try:
        db.execute("DELETE FROM cedulas WHERE responsable_id = %s", (rid,))
        db.execute("DELETE FROM responsables WHERE responsable_id = %s", (rid,))
        flash('Responsable eliminado.', 'success')
    except Exception as e:
        if _fk_error(e):
            flash('No se puede eliminar: este responsable tiene aplicaciones registradas.', 'error')
        else:
            flash(f'Error al eliminar: {str(e)}', 'error')
    return redirect(url_for('admin.responsables'))


@admin_bp.route('/administradores', methods=['GET', 'POST'])
def administradores():
    redir = _require_admin()
    if redir: return redir
    if request.method == 'POST':
        f = request.form
        temp = generate_temp_password()
        try:
            db.execute("""
                INSERT INTO administradores (admin_prim_nombre, admin_seg_nombre, admin_apellido_pat,
                    admin_apellido_mat, admin_rfc, admin_email, admin_telefono, admin_curp, admin_contrasena)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (f['prim_nombre'], f.get('seg_nombre','') or None, f['apellido_pat'],
                  f.get('apellido_mat','') or None, f['rfc'].upper(), f['email'],
                  f['telefono'], f['curp'].upper(), generate_password_hash(temp)))
            flash(f'Administrador registrado. Contraseña temporal: <strong>{temp}</strong>', 'success')
        except Exception as e:
            flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('admin.administradores'))
    admins = db.query("SELECT admin_id, admin_prim_nombre, admin_apellido_pat, admin_email, admin_rfc, admin_curp FROM administradores ORDER BY admin_apellido_pat")
    return render_template('admin/administradores.html', admins=admins)


@admin_bp.route('/administradores/<int:aid>/eliminar', methods=['POST'])
def eliminar_admin(aid):
    redir = _require_admin()
    if redir: return redir
    if aid == session['user_id']:
        flash('No puedes eliminar tu propia cuenta.', 'error')
    else:
        try:
            db.execute("DELETE FROM administradores WHERE admin_id = %s", (aid,))
            flash('Administrador eliminado.', 'success')
        except Exception as e:
            if _fk_error(e):
                flash('No se puede eliminar: este administrador tiene registros vinculados.', 'error')
            else:
                flash(f'Error al eliminar: {str(e)}', 'error')
    return redirect(url_for('admin.administradores'))


@admin_bp.route('/pacientes', methods=['GET', 'POST'])
def pacientes():
    redir = _require_admin()
    if redir: return redir
    if request.method == 'POST':
        f = request.form
        try:
            db.execute("""
                INSERT INTO pacientes (paciente_prim_nombre, paciente_nombre, paciente_apellido_pat,
                    paciente_apellido_mat, paciente_num_cert_nac, paciente_curp,
                    paciente_fecha_nac, paciente_sexo, paciente_nfc, esquema_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s::tipo_sexo,%s,%s)
            """, (f['prim_nombre'], f.get('seg_nombre','') or None, f['apellido_pat'],
                  f.get('apellido_mat','') or None, f.get('num_cert_nac','') or None,
                  f.get('curp','').upper() or None, f['fecha_nac'], f['sexo'],
                  f.get('nfc','') or None, f['esquema_id']))
            flash('Paciente registrado.', 'success')
        except Exception as e:
            flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('admin.pacientes'))
    pacientes = db.query("""
        SELECT p.paciente_id, p.paciente_prim_nombre, p.paciente_apellido_pat,
               p.paciente_curp, p.paciente_fecha_nac, p.paciente_sexo, p.paciente_nfc, e.esquema_nombre
        FROM pacientes p JOIN esquemas e ON p.esquema_id = e.esquema_id ORDER BY p.paciente_apellido_pat
    """)
    esquemas = db.query("SELECT esquema_id, esquema_nombre FROM esquemas ORDER BY esquema_nombre")
    return render_template('admin/pacientes.html', pacientes=pacientes, esquemas=esquemas)


@admin_bp.route('/pacientes/<int:pid>/eliminar', methods=['POST'])
def eliminar_paciente(pid):
    redir = _require_admin()
    if redir: return redir
    try:
        db.execute("DELETE FROM pacientes WHERE paciente_id = %s", (pid,))
        flash('Paciente eliminado.', 'success')
    except Exception as e:
        if _fk_error(e):
            flash('No se puede eliminar: este paciente tiene aplicaciones de vacunas registradas.', 'error')
        else:
            flash(f'Error al eliminar: {str(e)}', 'error')
    return redirect(url_for('admin.pacientes'))


@admin_bp.route('/relaciones', methods=['GET', 'POST'])
def relaciones():
    redir = _require_admin()
    if redir: return redir
    if request.method == 'POST':
        try:
            db.execute("INSERT INTO pacientes_tutores (paciente_id, tutor_id) VALUES (%s,%s)",
                       (request.form['paciente_id'], request.form['tutor_id']))
            flash('Relación registrada.', 'success')
        except Exception as e:
            flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('admin.relaciones'))
    relaciones = db.query("""
        SELECT pt.pac_tut_id,
               p.paciente_prim_nombre || ' ' || p.paciente_apellido_pat AS paciente,
               t.tutor_prim_nombre || ' ' || t.tutor_apellido_pat AS tutor
        FROM pacientes_tutores pt
        JOIN pacientes p ON pt.paciente_id = p.paciente_id
        JOIN tutores t ON pt.tutor_id = t.tutor_id ORDER BY paciente
    """)
    pacientes = db.query("SELECT paciente_id, paciente_prim_nombre || ' ' || paciente_apellido_pat AS nombre FROM pacientes ORDER BY nombre")
    tutores   = db.query("SELECT tutor_id, tutor_prim_nombre || ' ' || tutor_apellido_pat AS nombre FROM tutores ORDER BY nombre")
    return render_template('admin/relaciones.html', relaciones=relaciones, pacientes=pacientes, tutores=tutores)


@admin_bp.route('/relaciones/<int:rid>/eliminar', methods=['POST'])
def eliminar_relacion(rid):
    redir = _require_admin()
    if redir: return redir
    try:
        db.execute("DELETE FROM pacientes_tutores WHERE pac_tut_id = %s", (rid,))
        flash('Relación eliminada.', 'success')
    except Exception as e:
        if _fk_error(e):
            flash('No se puede eliminar esta relación.', 'error')
        else:
            flash(f'Error al eliminar: {str(e)}', 'error')
    return redirect(url_for('admin.relaciones'))


@admin_bp.route('/centros', methods=['GET', 'POST'])
def centros():
    redir = _require_admin()
    if redir: return redir
    if request.method == 'POST':
        f = request.form
        try:
            db.execute("""
                INSERT INTO centros_salud (centro_nombre, centro_calle, centro_numero,
                    centro_codigo_postal, ciudad_id, centro_horario_inicio, centro_horario_fin,
                    centro_latitud, centro_longitud, centro_telefono, centro_beacon)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (f['nombre'], f['calle'], f['numero'], f['cp'], f['ciudad_id'],
                  f['horario_inicio'], f['horario_fin'],
                  f.get('latitud') or None, f.get('longitud') or None,
                  f.get('telefono') or None, f.get('beacon') or None))
            flash('Centro registrado.', 'success')
        except Exception as e:
            flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('admin.centros'))
    centros  = db.query("""
        SELECT cs.centro_id, cs.centro_nombre, cs.centro_calle, cs.centro_numero,
               cs.centro_telefono, cs.centro_beacon, cs.centro_horario_inicio, cs.centro_horario_fin, c.ciudad_nombre
        FROM centros_salud cs JOIN ciudades c ON cs.ciudad_id = c.ciudad_id ORDER BY cs.centro_nombre
    """)
    ciudades = db.query("SELECT c.ciudad_id, c.ciudad_nombre, e.estado_nombre FROM ciudades c JOIN estados e ON c.estado_id = e.estado_id ORDER BY e.estado_nombre, c.ciudad_nombre")
    return render_template('admin/centros.html', centros=centros, ciudades=ciudades)


@admin_bp.route('/centros/<int:cid>/eliminar', methods=['POST'])
def eliminar_centro(cid):
    redir = _require_admin()
    if redir: return redir
    try:
        db.execute("DELETE FROM centros_salud WHERE centro_id = %s", (cid,))
        flash('Centro eliminado.', 'success')
    except Exception as e:
        if _fk_error(e):
            flash('No se puede eliminar: este centro tiene responsables o inventarios asignados.', 'error')
        else:
            flash(f'Error al eliminar: {str(e)}', 'error')
    return redirect(url_for('admin.centros'))


@admin_bp.route('/esquemas', methods=['GET', 'POST'])
def esquemas():
    redir = _require_admin()
    if redir: return redir
    if request.method == 'POST':
        f = request.form
        try:
            esq = db.query("INSERT INTO esquemas (esquema_nombre, esquema_fecha_vigencia) VALUES (%s,%s) RETURNING esquema_id",
                           (f['nombre'], f['fecha_vigencia']), fetch='one')
            if esq:
                for dosis_id in request.form.getlist('dosis_ids'):
                    if dosis_id:
                        db.execute("INSERT INTO dosis_esquemas (esquema_id, dosis_id) VALUES (%s,%s)", (esq['esquema_id'], dosis_id))
            flash('Esquema registrado.', 'success')
        except Exception as e:
            flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('admin.esquemas'))
    esquemas   = db.query("SELECT e.esquema_id, e.esquema_nombre, e.esquema_fecha_vigencia, COUNT(de.dosis_id) AS total_dosis FROM esquemas e LEFT JOIN dosis_esquemas de ON e.esquema_id = de.esquema_id GROUP BY e.esquema_id ORDER BY e.esquema_fecha_vigencia DESC")
    dosis_list = db.query("SELECT d.dosis_id, v.vacuna_nombre, d.dosis_tipo, d.dosis_edad_oportuna_dias FROM dosis d JOIN vacunas v ON d.vacuna_id = v.vacuna_id ORDER BY v.vacuna_nombre, d.dosis_edad_oportuna_dias")
    return render_template('admin/esquemas.html', esquemas=esquemas, dosis_list=dosis_list, days_to_human=days_to_human)


@admin_bp.route('/esquemas/<int:eid>/eliminar', methods=['POST'])
def eliminar_esquema(eid):
    redir = _require_admin()
    if redir: return redir
    try:
        db.execute("DELETE FROM esquemas WHERE esquema_id = %s", (eid,))
        flash('Esquema eliminado.', 'success')
    except Exception as e:
        if _fk_error(e):
            flash('No se puede eliminar: este esquema tiene pacientes o dosis asignadas.', 'error')
        else:
            flash(f'Error al eliminar: {str(e)}', 'error')
    return redirect(url_for('admin.esquemas'))


@admin_bp.route('/vacunas', methods=['GET', 'POST'])
def vacunas():
    redir = _require_admin()
    if redir: return redir
    if request.method == 'POST':
        f = request.form
        try:
            vac = db.query("INSERT INTO vacunas (vacuna_nombre) VALUES (%s) RETURNING vacuna_id", (f['nombre'],), fetch='one')
            if vac:
                tipos  = request.form.getlist('dosis_tipo')
                mls    = request.form.getlist('dosis_ml')
                areas  = request.form.getlist('dosis_area')
                edades = request.form.getlist('dosis_edad')
                ints   = request.form.getlist('dosis_intervalo')
                limits = request.form.getlist('dosis_limite')
                for i in range(len(tipos)):
                    if tipos[i]:
                        db.execute("""
                            INSERT INTO dosis (vacuna_id, dosis_tipo, dosis_cant_ml, dosis_area_aplicacion,
                                dosis_edad_oportuna_dias, dosis_intervalo_min_dias, dosis_limite_edad_dias)
                            VALUES (%s,%s::tipo_dosis,%s,%s,%s,%s,%s)
                        """, (vac['vacuna_id'], tipos[i], float(mls[i] or 0.5),
                              areas[i] or 'Por definir', int(edades[i] or 0),
                              int(ints[i] or 0), int(limits[i]) if limits[i] else None))
            flash('Vacuna registrada.', 'success')
        except Exception as e:
            flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('admin.vacunas'))
    vacunas = db.query("SELECT v.vacuna_id, v.vacuna_nombre, COUNT(d.dosis_id) AS total_dosis FROM vacunas v LEFT JOIN dosis d ON v.vacuna_id = d.vacuna_id GROUP BY v.vacuna_id ORDER BY v.vacuna_nombre")
    return render_template('admin/vacunas.html', vacunas=vacunas, dosis_tipos=DOSIS_TIPOS)


@admin_bp.route('/vacunas/<int:vid>/dosis')
def api_vacuna_dosis(vid):
    dosis = db.query("SELECT dosis_id, dosis_tipo, dosis_edad_oportuna_dias, dosis_limite_edad_dias, dosis_area_aplicacion, dosis_cant_ml, dosis_intervalo_min_dias FROM dosis WHERE vacuna_id = %s ORDER BY dosis_edad_oportuna_dias", (vid,))
    for d in dosis:
        d['edad_texto'] = days_to_human(d['dosis_edad_oportuna_dias'])
    return jsonify(dosis)


@admin_bp.route('/padecimientos', methods=['GET', 'POST'])
def padecimientos():
    redir = _require_admin()
    if redir: return redir
    if request.method == 'POST':
        f = request.form
        try:
            pad = db.query("INSERT INTO padecimientos (padecimiento_nombre, padecimiento_descripcion) VALUES (%s,%s) RETURNING padecimiento_id", (f['nombre'], f.get('descripcion','')), fetch='one')
            if pad:
                for vid in request.form.getlist('vacuna_ids'):
                    if vid:
                        db.execute("INSERT INTO vacunas_padecimientos (vacuna_id, padecimiento_id) VALUES (%s,%s)", (vid, pad['padecimiento_id']))
            flash('Padecimiento registrado.', 'success')
        except Exception as e:
            flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('admin.padecimientos'))
    padecimientos = db.query("SELECT p.padecimiento_id, p.padecimiento_nombre, p.padecimiento_descripcion, STRING_AGG(v.vacuna_nombre, ', ') AS vacunas FROM padecimientos p LEFT JOIN vacunas_padecimientos vp ON p.padecimiento_id = vp.padecimiento_id LEFT JOIN vacunas v ON vp.vacuna_id = v.vacuna_id GROUP BY p.padecimiento_id ORDER BY p.padecimiento_nombre")
    vacunas = db.query("SELECT vacuna_id, vacuna_nombre FROM vacunas ORDER BY vacuna_nombre")
    return render_template('admin/padecimientos.html', padecimientos=padecimientos, vacunas=vacunas)


@admin_bp.route('/fabricantes', methods=['GET', 'POST'])
def fabricantes():
    redir = _require_admin()
    if redir: return redir
    if request.method == 'POST':
        f = request.form
        try:
            db.execute("INSERT INTO fabricantes (fabricante_nombre, pais_id, fabricante_telefono) VALUES (%s,%s,%s)",
                       (f['nombre'], f['pais_id'], f.get('telefono') or None))
            flash('Fabricante registrado.', 'success')
        except Exception as e:
            flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('admin.fabricantes'))
    fabricantes = db.query("SELECT f.fabricante_id, f.fabricante_nombre, f.fabricante_telefono, p.pais_nombre FROM fabricantes f JOIN paises p ON f.pais_id = p.pais_id ORDER BY f.fabricante_nombre")
    paises = db.query("SELECT pais_id, pais_nombre FROM paises ORDER BY pais_nombre")
    return render_template('admin/fabricantes.html', fabricantes=fabricantes, paises=paises)


@admin_bp.route('/lotes', methods=['GET', 'POST'])
def lotes():
    redir = _require_admin()
    if redir: return redir
    if request.method == 'POST':
        accion = request.form.get('accion')
        f = request.form
        try:
            if accion == 'nuevo_lote':
                from datetime import date
                fecha_cad = f['fecha_cad']
                if fecha_cad <= str(date.today()):
                    flash('La fecha de caducidad debe ser futura.', 'error')
                    return redirect(url_for('admin.lotes'))
                if f['fecha_fab'] >= fecha_cad:
                    flash('La fecha de fabricación debe ser anterior a la de caducidad.', 'error')
                    return redirect(url_for('admin.lotes'))
                db.execute("INSERT INTO lotes (lote_codigo, lote_fecha_fabricacion, lote_fecha_caducidad, lote_cant_inicial, vacuna_id, fabricante_id) VALUES (%s,%s,%s,%s,%s,%s)",
                           (f['codigo'], f['fecha_fab'], f['fecha_cad'], f['cantidad'], f['vacuna_id'], f['fabricante_id']))
                flash('Lote registrado.', 'success')
            elif accion == 'asignar_inventario':
                stock = int(f['stock'])
                # Verificar que stock no excede cantidad inicial del lote
                lote = db.query("SELECT lote_cant_inicial FROM lotes WHERE lote_id = %s", (f['lote_id'],), fetch='one')
                if lote and stock > lote['lote_cant_inicial']:
                    flash(f"El stock asignado ({stock}) no puede exceder la cantidad inicial del lote ({lote['lote_cant_inicial']}).", 'error')
                    return redirect(url_for('admin.lotes'))
                if stock <= 0:
                    flash('El stock debe ser mayor a 0.', 'error')
                    return redirect(url_for('admin.lotes'))
                db.execute("INSERT INTO inventarios (centro_id, lote_id, inventario_stock_inicial, inventario_stock_actual, inventario_activo) VALUES (%s,%s,%s,%s,TRUE)",
                           (f['centro_id'], f['lote_id'], stock, stock))
                flash('Lote asignado al inventario.', 'success')
        except Exception as e:
            flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('admin.lotes'))
    lotes       = db.query("SELECT l.lote_id, l.lote_codigo, l.lote_fecha_fabricacion, l.lote_fecha_caducidad, l.lote_cant_inicial, v.vacuna_nombre, f.fabricante_nombre FROM lotes l JOIN vacunas v ON l.vacuna_id = v.vacuna_id JOIN fabricantes f ON l.fabricante_id = f.fabricante_id ORDER BY l.lote_fecha_caducidad")
    vacunas     = db.query("SELECT vacuna_id, vacuna_nombre FROM vacunas ORDER BY vacuna_nombre")
    fabricantes = db.query("SELECT fabricante_id, fabricante_nombre FROM fabricantes ORDER BY fabricante_nombre")
    centros     = db.query("SELECT centro_id, centro_nombre FROM centros_salud ORDER BY centro_nombre")
    return render_template('admin/lotes.html', lotes=lotes, vacunas=vacunas, fabricantes=fabricantes, centros=centros)


@admin_bp.route('/inventario')
def inventario():
    redir = _require_admin()
    if redir: return redir
    inventario = db.query("""
        SELECT inv.inventario_id, cs.centro_nombre, v.vacuna_nombre, l.lote_codigo,
               l.lote_fecha_fabricacion, l.lote_fecha_caducidad,
               inv.inventario_stock_inicial, inv.inventario_stock_actual, inv.inventario_activo,
               f.fabricante_nombre
        FROM inventarios inv
        JOIN centros_salud cs ON inv.centro_id = cs.centro_id
        JOIN lotes l ON inv.lote_id = l.lote_id
        JOIN vacunas v ON l.vacuna_id = v.vacuna_id
        JOIN fabricantes f ON l.fabricante_id = f.fabricante_id
        ORDER BY cs.centro_nombre, v.vacuna_nombre
    """)
    alertas_inv   = db.query("SELECT ai.alerta_inv_id, ai.alerta_inv_tipo, ai.alerta_inv_timestamp, v.vacuna_nombre, cs.centro_nombre FROM alertas_inventario ai JOIN inventarios inv ON ai.inventario_id = inv.inventario_id JOIN lotes l ON inv.lote_id = l.lote_id JOIN vacunas v ON l.vacuna_id = v.vacuna_id JOIN centros_salud cs ON inv.centro_id = cs.centro_id ORDER BY ai.alerta_inv_timestamp DESC")
    alertas_dosis = db.query("SELECT adp.alerta_dosis_pac_id, adp.alerta_dosis_pac_tipo, adp.alerta_dosis_pac_timestamp, p.paciente_prim_nombre || ' ' || p.paciente_apellido_pat AS paciente, v.vacuna_nombre, d.dosis_tipo FROM alertas_dosis_pacientes adp JOIN pacientes p ON adp.paciente_id = p.paciente_id JOIN dosis d ON adp.dosis_id = d.dosis_id JOIN vacunas v ON d.vacuna_id = v.vacuna_id ORDER BY adp.alerta_dosis_pac_timestamp DESC")
    return render_template('admin/inventario.html', inventario=inventario, alertas_inv=alertas_inv, alertas_dosis=alertas_dosis)


@admin_bp.route('/aplicaciones', methods=['GET', 'POST'])
def aplicaciones():
    redir = _require_admin()
    if redir: return redir
    if request.method == 'POST':
        f = request.form

        # Validar campos obligatorios
        if not f.get('paciente_id') or not f.get('dosis_id') or not f.get('inventario_id') or not f.get('responsable_id'):
            flash('Todos los campos son obligatorios.', 'error')
            return redirect(url_for('admin.aplicaciones'))

        # Validar stock disponible
        inv_check = db.query(
            "SELECT inventario_stock_actual FROM inventarios WHERE inventario_id = %s AND inventario_activo = TRUE",
            (f['inventario_id'],), fetch='one'
        )
        if not inv_check or inv_check['inventario_stock_actual'] <= 0:
            flash('No hay stock disponible en el inventario seleccionado.', 'error')
            return redirect(url_for('admin.aplicaciones'))

        # Validar que esta dosis NO haya sido ya aplicada a este paciente
        ya_aplicada = db.query(
            "SELECT aplicacion_id FROM aplicaciones WHERE paciente_id = %s AND dosis_id = %s LIMIT 1",
            (f['paciente_id'], f['dosis_id']), fetch='one'
        )
        if ya_aplicada:
            flash('Esta dosis ya fue aplicada anteriormente a este paciente.', 'error')
            return redirect(url_for('admin.aplicaciones'))

        try:
            db.execute("INSERT INTO aplicaciones (paciente_id, responsable_id, inventario_id, dosis_id, aplicacion_observaciones) VALUES (%s,%s,%s,%s,%s)",
                       (f['paciente_id'], f['responsable_id'], f['inventario_id'], f['dosis_id'], f.get('observaciones','')))
            db.execute("UPDATE inventarios SET inventario_stock_actual = inventario_stock_actual - 1 WHERE inventario_id = %s", (f['inventario_id'],))
            db.execute("UPDATE inventarios SET inventario_activo = FALSE WHERE inventario_id = %s AND inventario_stock_actual <= 0", (f['inventario_id'],))
            flash('Aplicación registrada.', 'success')
        except Exception as e:
            flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('admin.aplicaciones'))
    aplicaciones = db.query("SELECT a.aplicacion_id, p.paciente_prim_nombre || ' ' || p.paciente_apellido_pat AS paciente, r.responsable_prim_nombre || ' ' || r.responsable_apellido_pat AS responsable, v.vacuna_nombre, d.dosis_tipo, cs.centro_nombre, a.aplicacion_timestamp FROM aplicaciones a JOIN pacientes p ON a.paciente_id = p.paciente_id JOIN responsables r ON a.responsable_id = r.responsable_id JOIN dosis d ON a.dosis_id = d.dosis_id JOIN vacunas v ON d.vacuna_id = v.vacuna_id JOIN inventarios inv ON a.inventario_id = inv.inventario_id JOIN centros_salud cs ON inv.centro_id = cs.centro_id ORDER BY a.aplicacion_timestamp DESC")
    pacientes    = db.query("SELECT paciente_id, paciente_prim_nombre || ' ' || paciente_apellido_pat AS nombre FROM pacientes ORDER BY nombre")
    responsables = db.query("SELECT responsable_id, responsable_prim_nombre || ' ' || responsable_apellido_pat AS nombre FROM responsables ORDER BY nombre")
    inventarios  = db.query("SELECT inv.inventario_id, v.vacuna_nombre, l.lote_codigo, cs.centro_nombre, inv.inventario_stock_actual FROM inventarios inv JOIN lotes l ON inv.lote_id = l.lote_id JOIN vacunas v ON l.vacuna_id = v.vacuna_id JOIN centros_salud cs ON inv.centro_id = cs.centro_id WHERE inv.inventario_activo = TRUE AND inv.inventario_stock_actual > 0 ORDER BY v.vacuna_nombre")
    dosis_list   = db.query("SELECT d.dosis_id, v.vacuna_nombre, d.dosis_tipo FROM dosis d JOIN vacunas v ON d.vacuna_id = v.vacuna_id ORDER BY v.vacuna_nombre")
    return render_template('admin/aplicaciones.html', aplicaciones=aplicaciones, pacientes=pacientes, responsables=responsables, inventarios=inventarios, dosis_list=dosis_list)


@admin_bp.route('/geografia', methods=['GET', 'POST'])
def geografia():
    redir = _require_admin()
    if redir: return redir
    if request.method == 'POST':
        tipo = request.form.get('tipo')
        f    = request.form
        try:
            if tipo == 'pais':
                db.execute("INSERT INTO paises (pais_nombre) VALUES (%s)", (f['nombre'],))
                flash('País registrado.', 'success')
            elif tipo == 'estado':
                db.execute("INSERT INTO estados (estado_nombre, pais_id) VALUES (%s,%s)", (f['nombre'], f['pais_id']))
                flash('Estado registrado.', 'success')
            elif tipo == 'ciudad':
                db.execute("INSERT INTO ciudades (ciudad_nombre, estado_id) VALUES (%s,%s)", (f['nombre'], f['estado_id']))
                flash('Ciudad registrada.', 'success')
        except Exception as e:
            flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('admin.geografia'))
    paises   = db.query("SELECT * FROM paises ORDER BY pais_nombre")
    estados  = db.query("SELECT e.*, p.pais_nombre FROM estados e JOIN paises p ON e.pais_id = p.pais_id ORDER BY p.pais_nombre, e.estado_nombre")
    ciudades = db.query("SELECT c.*, e.estado_nombre FROM ciudades c JOIN estados e ON c.estado_id = e.estado_id ORDER BY e.estado_nombre, c.ciudad_nombre")
    return render_template('admin/geografia.html', paises=paises, estados=estados, ciudades=ciudades)


@admin_bp.route('/reportes')
def reportes():
    redir = _require_admin()
    if redir: return redir
    centros  = db.query("SELECT centro_id, centro_nombre FROM centros_salud ORDER BY centro_nombre")
    vacunas  = db.query("SELECT vacuna_id, vacuna_nombre FROM vacunas ORDER BY vacuna_nombre")
    esquemas = db.query("SELECT esquema_id, esquema_nombre FROM esquemas ORDER BY esquema_nombre")
    return render_template('admin/reportes.html', centros=centros, vacunas=vacunas, esquemas=esquemas)


@admin_bp.route('/api/reporte-datos')
def api_report_data():
    redir = _require_admin()
    if redir: return jsonify({'error': 'Unauthorized'}), 401
    fecha_desde = request.args.get('desde', '2020-01-01')
    fecha_hasta = request.args.get('hasta', '2099-12-31')
    por_mes     = db.query("SELECT TO_CHAR(DATE_TRUNC('month', aplicacion_timestamp), 'Mon YYYY') AS mes, COUNT(*) AS total FROM aplicaciones WHERE DATE(aplicacion_timestamp) BETWEEN %s AND %s GROUP BY DATE_TRUNC('month', aplicacion_timestamp) ORDER BY DATE_TRUNC('month', aplicacion_timestamp)", (fecha_desde, fecha_hasta))
    top_vacunas = db.query("SELECT v.vacuna_nombre, COUNT(*) AS total FROM aplicaciones a JOIN dosis d ON a.dosis_id = d.dosis_id JOIN vacunas v ON d.vacuna_id = v.vacuna_id WHERE DATE(a.aplicacion_timestamp) BETWEEN %s AND %s GROUP BY v.vacuna_nombre ORDER BY total DESC LIMIT 8", (fecha_desde, fecha_hasta))
    return jsonify({'por_mes': por_mes, 'top_vacunas': top_vacunas})


@admin_bp.route('/perfil')
def perfil():
    redir = _require_admin()
    if redir: return redir
    admin = db.query("SELECT * FROM administradores WHERE admin_id = %s", (session['user_id'],), fetch='one')
    return render_template('admin/perfil.html', admin=admin)


@admin_bp.route('/api/estados/<int:pais_id>')
def api_estados(pais_id):
    return jsonify(db.query("SELECT estado_id, estado_nombre FROM estados WHERE pais_id = %s ORDER BY estado_nombre", (pais_id,)))


@admin_bp.route('/api/ciudades/<int:estado_id>')
def api_ciudades(estado_id):
    return jsonify(db.query("SELECT ciudad_id, ciudad_nombre FROM ciudades WHERE estado_id = %s ORDER BY ciudad_nombre", (estado_id,)))

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash, generate_password_hash
import db

auth_bp = Blueprint('auth', __name__)


def _find_user(email):
    """Search all user tables for a matching email. Returns dict or None."""
    tables = [
        ("administradores", "admin_id",          "admin_email",    "admin_contrasena",    "admin_prim_nombre",    "admin_apellido_pat",    "admin"),
        ("responsables",    "responsable_id",     "responsable_email", "responsable_contrasena", "responsable_prim_nombre", "responsable_apellido_pat", "responsable"),
        ("tutores",         "tutor_id",           "tutor_email",    "tutor_contrasena",    "tutor_prim_nombre",    "tutor_apellido_pat",    "tutor"),
    ]
    for table, id_col, email_col, pwd_col, name_col, surname_col, role in tables:
        row = db.query(
            f"SELECT {id_col} AS id, {email_col} AS email, {pwd_col} AS password, "
            f"{name_col} AS first_name, {surname_col} AS last_name FROM {table} WHERE {email_col} = %s",
            (email,), fetch='one'
        )
        if row:
            row['role'] = role
            return row
    return None


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        user = _find_user(email)
        if user and check_password_hash(user['password'], password):
            session['user_id']    = user['id']
            session['user_role']  = user['role']
            session['user_name']  = f"{user['first_name']} {user['last_name']}"
            session['user_email'] = user['email']
            session['first_login'] = user['password'].startswith('$TEMP$') if isinstance(user['password'], str) else False

            if user['role'] == 'admin':
                return redirect(url_for('admin.dashboard'))
            elif user['role'] == 'responsable':
                return redirect(url_for('clinical.lookup'))
            else:
                return redirect(url_for('public.tutor_dashboard'))
        else:
            flash('Correo o contraseña incorrectos.', 'error')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))


@auth_bp.route('/cambiar-contrasena', methods=['GET', 'POST'])
def change_password():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        new_pwd     = request.form.get('new_password', '')
        confirm_pwd = request.form.get('confirm_password', '')

        if new_pwd != confirm_pwd:
            flash('Las contraseñas no coinciden.', 'error')
        elif len(new_pwd) < 8:
            flash('La contraseña debe tener al menos 8 caracteres.', 'error')
        else:
            hashed = generate_password_hash(new_pwd)
            role   = session['user_role']
            uid    = session['user_id']

            table_map = {
                'admin':       ('administradores', 'admin_id',       'admin_contrasena'),
                'responsable': ('responsables',    'responsable_id', 'responsable_contrasena'),
                'tutor':       ('tutores',         'tutor_id',       'tutor_contrasena'),
            }
            table, id_col, pwd_col = table_map[role]
            db.execute(f"UPDATE {table} SET {pwd_col} = %s WHERE {id_col} = %s", (hashed, uid))
            session.pop('first_login', None)
            flash('Contraseña actualizada correctamente.', 'success')

            if role == 'admin':
                return redirect(url_for('admin.dashboard'))
            elif role == 'responsable':
                return redirect(url_for('clinical.lookup'))
            else:
                return redirect(url_for('public.tutor_dashboard'))

    return render_template('auth/change_password.html')

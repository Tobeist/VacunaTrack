# Esta aplicación contiene todo lo relacionado a la autenticación de usuarios,
# tanto el login como el cambio de contraseñas.

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash as _gph
from functools import partial
import repository as repo

generate_password_hash = partial(_gph, method='pbkdf2:sha256')

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
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
            repo.cambiar_password(session['user_role'], session['user_id'], hashed)
            flash('Contraseña actualizada correctamente.', 'success')

            role = session['user_role']
            if role == 'admin':
                return redirect(url_for('admin.dashboard'))
            elif role == 'responsable':
                return redirect(url_for('clinical.lookup'))
            else:
                return redirect(url_for('public.tutor_dashboard'))

    return render_template('auth/change_password.html')

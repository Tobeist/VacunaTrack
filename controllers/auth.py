from __future__ import annotations

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash as _gph
from functools import partial

from models import repository as repo
from models import mongo_db as mdb

auth_bp = Blueprint('auth', __name__)

generate_password_hash = partial(_gph, method='pbkdf2:sha256')

_ROLE_REDIRECT = {
    'admin':       'admin.dashboard',
    'responsable': 'clinical.dashboard',
    'tutor':       'public.tutor_dashboard',
}


def _activate_role(user: dict, role: str) -> None:
    session['user_id']    = user['id']
    session['user_role']  = role
    session['user_name']  = f"{user['first_name']} {user['last_name']}"
    session['user_email'] = user['email']


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        user = repo.buscar_usuario_por_email(email)
        if user and not user.get('activo', True):
            mdb.log_acceso(evento='login_fallido', pg_usuario_id=user['id'],
                           email=email, ip=request.remote_addr)
            flash('Tu cuenta está desactivada. Contacta al administrador.', 'error')
            return render_template('auth/login.html')
        if user and repo.verificar_password(user, password):
            roles = repo.roles_de_usuario(email)

            mdb.log_acceso(
                evento='login',
                pg_usuario_id=user['id'],
                email=email,
                rol=roles[0] if roles else user['role'],
                ip=request.remote_addr,
            )

            if len(roles) > 1:
                session['user_id']      = user['id']
                session['user_name']    = f"{user['first_name']} {user['last_name']}"
                session['user_email']   = user['email']
                session['user_roles']   = roles
                session.pop('user_role', None)
                return redirect(url_for('auth.select_role'))

            _activate_role(user, roles[0] if roles else user['role'])
            return redirect(url_for(_ROLE_REDIRECT.get(session['user_role'], 'auth.login')))
        else:
            mdb.log_acceso(
                evento='login_fallido',
                pg_usuario_id=None,
                email=email,
                ip=request.remote_addr,
            )
            flash('Correo o contraseña incorrectos.', 'error')

    return render_template('auth/login.html')


@auth_bp.route('/seleccionar-rol', methods=['GET', 'POST'])
def select_role():
    roles = session.get('user_roles')
    if not roles or 'user_id' not in session:
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        chosen = request.form.get('rol', '')
        if chosen not in roles:
            flash('Rol no válido.', 'error')
            return redirect(url_for('auth.select_role'))

        session['user_role'] = chosen
        return redirect(url_for(_ROLE_REDIRECT.get(chosen, 'auth.login')))

    return render_template('auth/select_role.html', roles=roles,
                           user_name=session.get('user_name', ''))


@auth_bp.route('/cambiar-rol')
def cambiar_rol():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    email = session.get('user_email', '')
    roles = repo.roles_de_usuario(email)
    if len(roles) < 2:
        return redirect(url_for(_ROLE_REDIRECT.get(session.get('user_role', ''), 'auth.login')))

    session['user_roles'] = roles
    session.pop('user_role', None)
    return redirect(url_for('auth.select_role'))


@auth_bp.route('/logout')
def logout():
    mdb.log_acceso(
        evento='logout',
        pg_usuario_id=session.get('user_id'),
        email=session.get('user_email', ''),
        rol=session.get('user_role'),
        ip=request.remote_addr,
    )
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
            try:
                repo.cambiar_password(session['user_role'], session['user_id'], hashed)
                flash('Contraseña actualizada correctamente.', 'success')
                role = session['user_role']
                return redirect(url_for(_ROLE_REDIRECT.get(role, 'auth.login')))
            except Exception as e:
                from controllers.admin import _flash_error
                _flash_error(e)

    return render_template('auth/change_password.html')

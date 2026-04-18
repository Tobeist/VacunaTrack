import os
from dotenv import load_dotenv

# Cargar variables de entorno ANTES de importar db y routes,
# para que DATABASE_URL esté disponible cuando db.py se inicializa.
load_dotenv()

from flask import Flask, redirect, url_for
from routes import auth_bp, admin_bp, clinical_bp, public_bp
from datetime import date, datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'vacunatrack-dev-secret-2026')

# Registrar gestión de conexión a PostgreSQL
import db as _db
_db.init_app(app)


# Usando Jinja, creamos formatos para fecha
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

# Usando Jinja, creamos formatos para fecha y hora
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

# Usando Jinja, creamos formatos para hora
@app.template_filter('format_time')
def format_time(value):
    if not value:
        return '—'
    return str(value)[:5]


@app.template_filter('cap')
def capitalize_filter(value):
    """Muestra con primera letra mayúscula cada palabra (datos guardados en minúsculas)."""
    if not value:
        return ''
    return value.title()

app.register_blueprint(auth_bp)
app.register_blueprint(public_bp)
app.register_blueprint(clinical_bp)
app.register_blueprint(admin_bp)


@app.route('/')
def index():
    return redirect(url_for('public.landing'))


if __name__ == '__main__':
    app.run(debug=True, port=5000)

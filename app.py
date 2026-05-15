from __future__ import annotations
import os
from dotenv import load_dotenv
load_dotenv()

from flask import Flask
from models import db as _db
from controllers import auth_bp, public_bp, clinical_bp, admin_bp
from datetime import date, datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'vacunatrack-dev-secret-2026')
_db.init_app(app)
app.register_blueprint(auth_bp)
app.register_blueprint(public_bp)
app.register_blueprint(clinical_bp)
app.register_blueprint(admin_bp)


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


if __name__ == '__main__':
    app.run(debug=True, port=5000)

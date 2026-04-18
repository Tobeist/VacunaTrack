# db.py — Gestión de conexión a PostgreSQL para VacunaTrack
#
# Uso:
#   from db import get_db, query, execute, query_one
#
# Si DATABASE_URL no está definida, el sistema usa data.py (modo mock).
# Para conectar a PostgreSQL, crea un archivo .env con:
#   DATABASE_URL=postgresql://usuario:contraseña@localhost:5432/vacunatrack

from __future__ import annotations
import os
import psycopg2
import psycopg2.extras
from flask import g

DATABASE_URL = os.environ.get('DATABASE_URL')


def get_db():
    """Retorna la conexión a PostgreSQL del contexto actual de Flask.
    Reutiliza la misma conexión durante el ciclo de vida de la petición."""
    if 'db' not in g:
        if not DATABASE_URL:
            raise RuntimeError(
                'DATABASE_URL no está definida. '
                'Crea un archivo .env o define la variable de entorno.'
            )
        g.db = psycopg2.connect(DATABASE_URL)
    return g.db


def close_db(e=None):
    """Cierra la conexión al finalizar cada petición."""
    db = g.pop('db', None)
    if db is not None:
        db.close()


def query(sql: str, params=None) -> list[dict]:
    """Ejecuta un SELECT y retorna una lista de dicts."""
    conn = get_db()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params or ())
        return [dict(row) for row in cur.fetchall()]


def query_one(sql: str, params=None) -> dict | None:
    """Ejecuta un SELECT y retorna la primera fila como dict, o None."""
    conn = get_db()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params or ())
        row = cur.fetchone()
        return dict(row) if row else None


def execute(sql: str, params=None) -> None:
    """Ejecuta un INSERT/UPDATE/DELETE y hace commit."""
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(sql, params or ())
    conn.commit()


def execute_returning(sql: str, params=None) -> dict | None:
    """Ejecuta un INSERT ... RETURNING y retorna la fila insertada."""
    conn = get_db()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params or ())
        row = cur.fetchone()
        conn.commit()
        return dict(row) if row else None


def init_app(app):
    """Registra el cierre de conexión en el contexto de la app Flask."""
    app.teardown_appcontext(close_db)


def using_postgres() -> bool:
    """Retorna True si DATABASE_URL está configurada (modo PostgreSQL activo)."""
    return bool(DATABASE_URL)

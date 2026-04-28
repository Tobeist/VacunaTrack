from __future__ import annotations
import os
import psycopg
from psycopg.rows import dict_row
from flask import g

DATABASE_URL = os.environ.get('DATABASE_URL')


def get_db():
    if 'db' not in g:
        if not DATABASE_URL:
            raise RuntimeError(
                'DATABASE_URL no está definida. '
                'Crea un archivo .env o define la variable de entorno.'
            )
        g.db = psycopg.connect(DATABASE_URL)
        with g.db.cursor() as _tz:
            _tz.execute("SET TIME ZONE 'America/Mexico_City'")
        g.db.commit()
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def query(sql: str, params=None) -> list[dict]:
    conn = get_db()
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params or ())
        return [dict(row) for row in cur.fetchall()]


def query_one(sql: str, params=None) -> dict | None:
    conn = get_db()
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params or ())
        row = cur.fetchone()
        return dict(row) if row else None


def execute(sql: str, params=None) -> None:
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(sql, params or ())
    conn.commit()


def execute_returning(sql: str, params=None) -> dict | None:
    conn = get_db()
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params or ())
        row = cur.fetchone()
        conn.commit()
        return dict(row) if row else None


def call_read_sp(name: str, in_params: list | None = None) -> list[dict]:
    conn = get_db()
    params = list(in_params or [])
    placeholders = ', '.join(['%s'] * len(params) + ["'_cur'"])
    call_sql = f"CALL {name}({placeholders})"
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(call_sql, params)
        cur.execute("FETCH ALL FROM _cur")
        rows = [dict(row) for row in cur.fetchall()]
    conn.commit()
    return rows


def call_read_sp_one(name: str, in_params: list | None = None) -> dict | None:
    rows = call_read_sp(name, in_params)
    return rows[0] if rows else None


def call_write_sp(name: str, in_params: list, out_count: int = 3) -> dict:
    conn = get_db()
    placeholders = ['%s'] * len(in_params) + ['NULL'] * out_count
    sql = f"CALL {name}({', '.join(placeholders)})"
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, in_params)
        row = cur.fetchone()
        conn.commit()
    return dict(row) if row else {'p_ok': 0, 'p_msg': 'Error interno del servidor'}


def init_app(app):
    app.teardown_appcontext(close_db)


def using_postgres() -> bool:
    return bool(DATABASE_URL)

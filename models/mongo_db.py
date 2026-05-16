"""
MongoDB connection and logging helpers for VacunaTrack.

Integration strategy (PostgreSQL ↔ MongoDB):
  - PostgreSQL is the source of truth for all transactional data.
  - MongoDB stores event logs, access history, and semi-structured analytics data.
  - Every MongoDB document includes the relevant PostgreSQL ID(s) as reference
    fields (e.g. pg_paciente_id, pg_aplicacion_id) so both databases can be
    cross-queried via shared keys.

Collections:
  logs_aplicaciones  — one document per vaccine application event
  eventos_inventario — one document per inventory assignment or transfer
  logs_acceso        — one document per login / logout event
  logs_sistema       — general operational events (patient created, etc.)
  eventos_beacon     — one document per beacon detection / center check-in
  busquedas_gps      — one document per GPS-based center search (high-volume geospatial)
"""

from __future__ import annotations
import os
from datetime import datetime, timezone, date, timedelta

from pymongo import MongoClient
from pymongo.errors import PyMongoError

MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
MONGO_DB  = os.environ.get('MONGO_DB',  'vacunatrack')

_client: MongoClient | None = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=3000)
    return _client


def get_db():
    return get_client()[MONGO_DB]


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Public logging helpers ────────────────────────────────────────────────────

def log_aplicacion(
    *,
    pg_aplicacion_id: int | None,
    pg_paciente_id: int,
    pg_usuario_id: int,
    pg_centro_id: int,
    pg_lote_id: int,
    pg_dosis_id: int,
    vacuna_nombre: str,
    paciente_nombre: str,
    responsable_nombre: str,
    centro_nombre: str,
    observaciones: str | None = None,
) -> None:
    """Log a vaccine application event to MongoDB."""
    try:
        get_db().logs_aplicaciones.insert_one({
            'timestamp':          _now(),
            'pg_aplicacion_id':   pg_aplicacion_id,
            'pg_paciente_id':     pg_paciente_id,
            'pg_usuario_id':      pg_usuario_id,
            'pg_centro_id':       pg_centro_id,
            'pg_lote_id':         pg_lote_id,
            'pg_dosis_id':        pg_dosis_id,
            'vacuna_nombre':      vacuna_nombre,
            'paciente_nombre':    paciente_nombre,
            'responsable_nombre': responsable_nombre,
            'centro_nombre':      centro_nombre,
            'observaciones':      observaciones,
        })
    except PyMongoError:
        pass  # MongoDB failure must never break the main PostgreSQL transaction


def log_inventario(
    *,
    evento: str,                    # 'asignacion' | 'transferencia' | 'confirmacion'
    pg_inventario_id: int | None,
    pg_centro_id: int,
    pg_lote_id: int,
    pg_usuario_id: int,
    vacuna_nombre: str,
    centro_nombre: str,
    stock: int,
    meta: dict | None = None,       # extra fields (destino, origen, etc.)
) -> None:
    """Log an inventory event to MongoDB."""
    try:
        doc = {
            'timestamp':       _now(),
            'evento':          evento,
            'pg_inventario_id':pg_inventario_id,
            'pg_centro_id':    pg_centro_id,
            'pg_lote_id':      pg_lote_id,
            'pg_usuario_id':   pg_usuario_id,
            'vacuna_nombre':   vacuna_nombre,
            'centro_nombre':   centro_nombre,
            'stock':           stock,
        }
        if meta:
            doc.update(meta)
        get_db().eventos_inventario.insert_one(doc)
    except PyMongoError:
        pass


def log_acceso(
    *,
    evento: str,                    # 'login' | 'logout' | 'login_fallido'
    pg_usuario_id: int | None,
    email: str,
    rol: str | None = None,
    ip: str | None = None,
) -> None:
    """Log a login / logout event to MongoDB."""
    try:
        get_db().logs_acceso.insert_one({
            'timestamp':      _now(),
            'evento':         evento,
            'pg_usuario_id':  pg_usuario_id,
            'email':          email,
            'rol':            rol,
            'ip':             ip,
        })
    except PyMongoError:
        pass


def log_sistema(
    *,
    evento: str,                    # e.g. 'paciente_creado', 'paciente_eliminado'
    pg_entidad_id: int | None,
    entidad: str,                   # e.g. 'paciente', 'centro', 'usuario'
    pg_usuario_id: int | None,
    descripcion: str,
    meta: dict | None = None,
) -> None:
    """Log a general system event to MongoDB."""
    try:
        doc = {
            'timestamp':      _now(),
            'evento':         evento,
            'entidad':        entidad,
            'pg_entidad_id':  pg_entidad_id,
            'pg_usuario_id':  pg_usuario_id,
            'descripcion':    descripcion,
        }
        if meta:
            doc.update(meta)
        get_db().logs_sistema.insert_one(doc)
    except PyMongoError:
        pass


def log_beacon(
    *,
    pg_centro_id: int,
    beacon_id: str | None,
    pg_tutor_id: int,
    metodo: str,            # 'beacon_id' | 'gps_proximity'
) -> None:
    """Log a beacon detection / center check-in event."""
    try:
        get_db().eventos_beacon.insert_one({
            'timestamp':    _now(),
            'pg_centro_id': pg_centro_id,
            'beacon_id':    beacon_id,
            'pg_tutor_id':  pg_tutor_id,
            'metodo':       metodo,
        })
    except PyMongoError:
        pass


def log_gps(
    *,
    lat: float,
    lon: float,
    vacuna_id: int | None,
    centros_encontrados: int,
    pg_usuario_id: int | None,
) -> None:
    """Log a GPS-based center search event."""
    try:
        get_db().busquedas_gps.insert_one({
            'timestamp':          _now(),
            'ubicacion':          {'type': 'Point', 'coordinates': [lon, lat]},
            'lat':                lat,
            'lon':                lon,
            'vacuna_id':          vacuna_id,
            'centros_encontrados': centros_encontrados,
            'pg_usuario_id':      pg_usuario_id,
        })
    except PyMongoError:
        pass


# ── Read helpers (used by Flask report endpoints) ─────────────────────────────

def aplicaciones_por_mes(meses: int = 12) -> list[dict]:
    """Return monthly application counts for the last N months."""
    try:
        pipeline = [
            {'$group': {
                '_id': {
                    'year':  {'$year':  '$timestamp'},
                    'month': {'$month': '$timestamp'},
                },
                'total': {'$sum': 1},
                'vacunas': {'$push': '$vacuna_nombre'},
            }},
            {'$sort': {'_id.year': 1, '_id.month': 1}},
            {'$limit': meses},
        ]
        return list(get_db().logs_aplicaciones.aggregate(pipeline))
    except PyMongoError:
        return []


def top_vacunas(limit: int = 10) -> list[dict]:
    """Return the most-applied vaccines by count."""
    try:
        pipeline = [
            {'$group': {'_id': '$vacuna_nombre', 'total': {'$sum': 1}}},
            {'$sort': {'total': -1}},
            {'$limit': limit},
        ]
        return list(get_db().logs_aplicaciones.aggregate(pipeline))
    except PyMongoError:
        return []


def aplicaciones_por_centro(limit: int = 10) -> list[dict]:
    """Return application counts grouped by health center."""
    try:
        pipeline = [
            {'$group': {'_id': '$centro_nombre', 'total': {'$sum': 1}}},
            {'$sort': {'total': -1}},
            {'$limit': limit},
        ]
        return list(get_db().logs_aplicaciones.aggregate(pipeline))
    except PyMongoError:
        return []


def ultimos_accesos(limit: int = 50, rol: str | None = None) -> list[dict]:
    """Return the most recent access events, optionally filtered by role."""
    try:
        filtro: dict = {}
        if rol:
            filtro['rol'] = rol
        docs = (
            get_db().logs_acceso
            .find(filtro, {'_id': 0})
            .sort('timestamp', -1)
            .limit(limit)
        )
        return list(docs)
    except PyMongoError:
        return []


def eventos_inventario_recientes(limit: int = 50) -> list[dict]:
    """Return the most recent inventory events."""
    try:
        docs = (
            get_db().eventos_inventario
            .find({}, {'_id': 0})
            .sort('timestamp', -1)
            .limit(limit)
        )
        return list(docs)
    except PyMongoError:
        return []


def eventos_beacon_por_centro(limit: int = 10) -> list[dict]:
    """Return beacon check-in counts grouped by center."""
    try:
        pipeline = [
            {'$group': {'_id': '$pg_centro_id', 'total': {'$sum': 1}}},
            {'$sort': {'total': -1}},
            {'$limit': limit},
        ]
        return list(get_db().eventos_beacon.aggregate(pipeline))
    except PyMongoError:
        return []


def ultimos_beacons(limit: int = 20) -> list[dict]:
    """Return the most recent beacon check-in events."""
    try:
        docs = (
            get_db().eventos_beacon
            .find({}, {'_id': 0})
            .sort('timestamp', -1)
            .limit(limit)
        )
        return list(docs)
    except PyMongoError:
        return []


def busquedas_gps_recientes(limit: int = 20) -> list[dict]:
    """Return the most recent GPS search events."""
    try:
        docs = (
            get_db().busquedas_gps
            .find({}, {'_id': 0, 'ubicacion': 0})
            .sort('timestamp', -1)
            .limit(limit)
        )
        return list(docs)
    except PyMongoError:
        return []


def beacon_por_centro_reciente(dias: int = 30) -> list[dict]:
    """Return beacon detections grouped by center for the last N days."""
    try:
        desde = datetime.now(timezone.utc) - timedelta(days=dias)
        pipeline = [
            {'$match': {'timestamp': {'$gte': desde}}},
            {'$group': {
                '_id': '$pg_centro_id',
                'total': {'$sum': 1},
                'ultima_deteccion': {'$max': '$timestamp'},
            }},
            {'$sort': {'total': -1}},
        ]
        return list(get_db().eventos_beacon.aggregate(pipeline))
    except PyMongoError:
        return []


def gps_accesibilidad_por_vacuna() -> list[dict]:
    """Return GPS search accessibility stats grouped by vacuna_id."""
    try:
        pipeline = [
            {'$match': {'vacuna_id': {'$ne': None}}},
            {'$group': {
                '_id': '$vacuna_id',
                'total_busquedas': {'$sum': 1},
                'con_resultado': {
                    '$sum': {'$cond': [{'$gt': ['$centros_encontrados', 0]}, 1, 0]}
                },
                'promedio_centros': {'$avg': '$centros_encontrados'},
            }},
            {'$sort': {'total_busquedas': -1}},
        ]
        return list(get_db().busquedas_gps.aggregate(pipeline))
    except PyMongoError:
        return []


def resumen_logs() -> dict:
    """Return a quick count summary across all collections."""
    try:
        mdb = get_db()
        return {
            'aplicaciones':  mdb.logs_aplicaciones.count_documents({}),
            'inventario':    mdb.eventos_inventario.count_documents({}),
            'accesos':       mdb.logs_acceso.count_documents({}),
            'sistema':       mdb.logs_sistema.count_documents({}),
            'beacon':        mdb.eventos_beacon.count_documents({}),
            'gps':           mdb.busquedas_gps.count_documents({}),
        }
    except PyMongoError:
        return {'aplicaciones': 0, 'inventario': 0, 'accesos': 0, 'sistema': 0, 'beacon': 0, 'gps': 0}


def ultimas_aplicaciones(limit: int = 8) -> list[dict]:
    """Return the most recent vaccine application events."""
    try:
        docs = (
            get_db().logs_aplicaciones
            .find({}, {'_id': 0, 'pg_lote_id': 0, 'pg_dosis_id': 0, 'pg_usuario_id': 0})
            .sort('timestamp', -1)
            .limit(limit)
        )
        return list(docs)
    except PyMongoError:
        return []


def top_centros_mes(limit: int = 5) -> list[dict]:
    """Return top centers by application count for the current calendar month."""
    now = datetime.now(timezone.utc)
    inicio_mes = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    try:
        pipeline = [
            {'$match': {'timestamp': {'$gte': inicio_mes}}},
            {'$group': {'_id': '$centro_nombre', 'total': {'$sum': 1}}},
            {'$sort': {'total': -1}},
            {'$limit': limit},
        ]
        return list(get_db().logs_aplicaciones.aggregate(pipeline))
    except PyMongoError:
        return []

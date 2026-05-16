"""
seed_mongo.py — Datos semilla para las colecciones MongoDB de VacunaTrack.

Uso:
    python seed_mongo.py

Requiere que seed_final.sql ya haya sido aplicado en PostgreSQL y que
la variable de entorno MONGO_URL esté configurada (o usa localhost:27017).
Las colecciones se vacían y se reinsertan desde cero.
"""

import os
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
MONGO_DB  = os.environ.get("MONGO_DB",  "vacunatrack")

client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
db     = client[MONGO_DB]


def dt(year, month, day, hour=9, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


# ─── RESET ───────────────────────────────────────────────────────────────────
print("Limpiando colecciones...")
for col in ["logs_aplicaciones", "eventos_inventario", "logs_acceso",
            "eventos_beacon", "busquedas_gps"]:
    db[col].delete_many({})

# ─── CATÁLOGOS DE APOYO ───────────────────────────────────────────────────────
# (referencia rápida para construir documentos coherentes con PostgreSQL)
CENTROS = {
    1: "Centro de Salud Zona Norte",
    2: "Centro de Salud Zapopan",
    3: "Centro de Salud Tlaquepaque",
    4: "IMSS Unidad Médica Sur",
    5: "Centro de Salud Monterrey Norte",
}
RESPONSABLES = {
    2: "Diego Mendoza García",
    3: "Ana González Ruiz",
    4: "Roberto Chávez Moreno",
    5: "María Jiménez Santos",
    6: "Luis Ramos Fuentes",
}
PACIENTES = {
    1:  "Sofía Pérez López",
    2:  "Mateo Pérez López",
    3:  "Valentina Rodríguez Martínez",
    4:  "Carlos García Núñez",
    5:  "Isabella López Hernández",
    6:  "Diego Hernández Cruz",
    7:  "Camila Torres Vargas",
    8:  "Andrés Martínez Reyes",
    9:  "Lucía Sánchez Morales",
    10: "Miguel Flores Castillo",
    11: "Emilia Castro Guerrero",
    12: "Sebastián Vargas Ortega",
    13: "Alejandro Reyes García",
    14: "Gabriela Ortiz Mendoza",
    15: "Rafael Mendoza Peña",
    16: "Fernanda Rojas Torres",
    17: "Tomás Herrera Vega",
    18: "Valentina Gutiérrez Díaz",
}
VACUNA_DOSIS = {
    1:  "BCG",
    2:  "Hepatitis B",
    3:  "Hepatitis B",
    4:  "Pentavalente",
    5:  "Pentavalente",
    6:  "Pentavalente",
    7:  "Neumocócica",
    8:  "Neumocócica",
    9:  "Rotavirus",
    10: "Rotavirus",
    11: "Triple Viral (SRP)",
    12: "Influenza",
    13: "Varicela",
    14: "Hepatitis A",
    15: "Hepatitis A",
}

# ─── LOGS_APLICACIONES ────────────────────────────────────────────────────────
# Solo los últimos ~13 meses (mayo 2025 – mayo 2026) para que la gráfica
# MongoDB muestre tendencia reciente. Las aplicaciones históricas viven
# sólo en PostgreSQL.
print("Insertando logs_aplicaciones...")

aplicaciones_mongo = [
    # ─── Mayo 2025 ────────────────────────────────────────────────────────────
    # P13 Alejandro: Penta2(d5), Rota2(d10)  centro 1 resp 2
    (1, 13,  2, 1, 2, 3,  5, "2025-05-11 09:00"),
    (2, 13,  2, 1, 2, 5, 10, "2025-05-11 09:05"),
    # P16 Fernanda: Penta3(d6), Neum2(d8), Flu(d12)  centro 2 resp 3
    (3, 16,  3, 2, 3, 3,  6, "2025-05-16 10:00"),
    (4, 16,  3, 2, 3, 4,  8, "2025-05-16 10:05"),
    (5, 16,  3, 2, 3, 7, 12, "2025-05-16 10:10"),
    # ─── Junio 2025 ───────────────────────────────────────────────────────────
    # P6 Diego: SRP(d11)  centro 3 resp 4
    (6,  6,  4, 3, 3, 6, 11, "2025-06-05 09:00"),
    # P14 Gabriela: BCG(d1), HepB1(d2)  centro 5 resp 6
    (7, 14,  6, 5, 5, 1,  1, "2025-06-10 10:00"),
    (8, 14,  6, 5, 5, 2,  2, "2025-06-10 10:10"),
    # ─── Julio 2025 ───────────────────────────────────────────────────────────
    # P13: Penta3(d6), Neum2(d8), Flu(d12)  centro 1 resp 2
    (9,  13, 2, 1, 2, 3,  6, "2025-07-10 09:00"),
    (10, 13, 2, 1, 2, 4,  8, "2025-07-10 09:05"),
    (11, 13, 2, 1, 2, 7, 12, "2025-07-10 09:10"),
    # ─── Agosto 2025 ──────────────────────────────────────────────────────────
    # P9 Lucía: SRP(d11)  centro 5 resp 6
    (12, 9,  6, 5, 5, 6, 11, "2025-08-13 09:00"),
    # P14: HepB2(d3), Penta1(d4), Neum1(d7), Rota1(d9)  centro 5 resp 6
    (13, 14, 6, 5, 5, 2,  3, "2025-08-10 10:00"),
    (14, 14, 6, 5, 5, 3,  4, "2025-08-10 10:05"),
    (15, 14, 6, 5, 5, 4,  7, "2025-08-10 10:10"),
    (16, 14, 6, 5, 5, 5,  9, "2025-08-10 10:15"),
    # ─── Septiembre 2025 ──────────────────────────────────────────────────────
    # P17 Tomás: BCG(d1), HepB1(d2)  centro 4 resp 5
    (17, 17, 5, 4, 4, 1,  1, "2025-09-10 09:00"),
    (18, 17, 5, 4, 4, 2,  2, "2025-09-10 09:10"),
    # ─── Octubre 2025 ─────────────────────────────────────────────────────────
    # P14: Penta2(d5), Rota2(d10)  centro 5 resp 6
    (19, 14, 6, 5, 5, 3,  5, "2025-10-09 10:00"),
    (20, 14, 6, 5, 5, 5, 10, "2025-10-09 10:05"),
    # P15 Rafael: BCG(d1), HepB1(d2)  centro 3 resp 4
    (21, 15, 4, 3, 3, 1,  1, "2025-10-05 11:00"),
    (22, 15, 4, 3, 3, 2,  2, "2025-10-05 11:10"),
    # ─── Noviembre 2025 ───────────────────────────────────────────────────────
    # P16: SRP(d11)  centro 2 resp 3
    (23, 16, 3, 2, 3, 6, 11, "2025-11-16 10:00"),
    # P17: HepB2(d3), Penta1(d4), Neum1(d7), Rota1(d9)  centro 4 resp 5
    (24, 17, 5, 4, 4, 2,  3, "2025-11-10 09:00"),
    (25, 17, 5, 4, 4, 3,  4, "2025-11-10 09:05"),
    (26, 17, 5, 4, 4, 4,  7, "2025-11-10 09:10"),
    (27, 17, 5, 4, 4, 5,  9, "2025-11-10 09:15"),
    # ─── Diciembre 2025 ───────────────────────────────────────────────────────
    # P14: Penta3(d6), Neum2(d8), Flu(d12)  centro 5 resp 6
    (28, 14, 6, 5, 5, 3,  6, "2025-12-09 10:00"),
    (29, 14, 6, 5, 5, 4,  8, "2025-12-09 10:05"),
    (30, 14, 6, 5, 5, 7, 12, "2025-12-09 10:10"),
    # P15: HepB2(d3), Penta1(d4), Neum1(d7), Rota1(d9)  centro 3 resp 4
    (31, 15, 4, 3, 3, 2,  3, "2025-12-05 11:00"),
    (32, 15, 4, 3, 3, 3,  4, "2025-12-05 11:05"),
    (33, 15, 4, 3, 3, 4,  7, "2025-12-05 11:10"),
    (34, 15, 4, 3, 3, 5,  9, "2025-12-05 11:15"),
    # ─── Enero 2026 ───────────────────────────────────────────────────────────
    # P13: SRP(d11)  centro 1 resp 2
    (35, 13, 2, 1, 2, 6, 11, "2026-01-12 09:00"),
    # P17: Penta2(d5), Rota2(d10)  centro 4 resp 5
    (36, 17, 5, 4, 4, 3,  5, "2026-01-09 09:00"),
    (37, 17, 5, 4, 4, 5, 10, "2026-01-09 09:05"),
    # P18 Valentina G: BCG(d1), HepB1(d2)  centro 1 resp 2
    (38, 18, 2, 1, 2, 1,  1, "2026-01-15 09:00"),
    (39, 18, 2, 1, 2, 2,  2, "2026-01-15 09:10"),
    # ─── Febrero 2026 ─────────────────────────────────────────────────────────
    # P15: Penta2(d5), Rota2(d10)  centro 3 resp 4
    (40, 15, 4, 3, 3, 3,  5, "2026-02-03 11:00"),
    (41, 15, 4, 3, 3, 5, 10, "2026-02-03 11:05"),
    # ─── Marzo 2026 ───────────────────────────────────────────────────────────
    # P17: Penta3(d6), Neum2(d8), Flu(d12)  centro 4 resp 5
    (42, 17, 5, 4, 4, 3,  6, "2026-03-10 09:00"),
    (43, 17, 5, 4, 4, 4,  8, "2026-03-10 09:05"),
    (44, 17, 5, 4, 4, 7, 12, "2026-03-10 09:10"),
    # P18: HepB2(d3), Penta1(d4), Neum1(d7), Rota1(d9)  centro 1 resp 2
    (45, 18, 2, 1, 2, 2,  3, "2026-03-17 09:00"),
    (46, 18, 2, 1, 2, 3,  4, "2026-03-17 09:05"),
    (47, 18, 2, 1, 2, 4,  7, "2026-03-17 09:10"),
    (48, 18, 2, 1, 2, 5,  9, "2026-03-17 09:15"),
    # ─── Abril 2026 ───────────────────────────────────────────────────────────
    # P15: Penta3(d6), Neum2(d8), Flu(d12)  centro 3 resp 4
    (49, 15, 4, 3, 3, 3,  6, "2026-04-04 11:00"),
    (50, 15, 4, 3, 3, 4,  8, "2026-04-04 11:05"),
    (51, 15, 4, 3, 3, 7, 12, "2026-04-04 11:10"),
    # ─── Mayo 2026 ────────────────────────────────────────────────────────────
    # P18: Penta2(d5), Rota2(d10)  centro 1 resp 2
    (52, 18, 2, 1, 2, 3,  5, "2026-05-16 09:00"),
    (53, 18, 2, 1, 2, 5, 10, "2026-05-16 09:05"),
]
# Formato: (pg_aplicacion_id, pg_paciente_id, pg_usuario_id, pg_centro_id,
#            pg_lote_id, pg_dosis_id [vacuna lookup], dosis_id, timestamp_str)
# Simplificación: pg_lote_id y pg_dosis_id provienen del plan SQL

docs_aplicaciones = []
for row in aplicaciones_mongo:
    (pg_ap, pg_pac, pg_usr, pg_cen, pg_lot, vac_key, dosis_id, ts_str) = row
    ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    docs_aplicaciones.append({
        "timestamp":          ts,
        "pg_aplicacion_id":   pg_ap,
        "pg_paciente_id":     pg_pac,
        "pg_usuario_id":      pg_usr,
        "pg_centro_id":       pg_cen,
        "pg_lote_id":         pg_lot,
        "pg_dosis_id":        dosis_id,
        "vacuna_nombre":      VACUNA_DOSIS[vac_key],
        "paciente_nombre":    PACIENTES[pg_pac],
        "responsable_nombre": RESPONSABLES[pg_usr],
        "centro_nombre":      CENTROS[pg_cen],
        "observaciones":      None,
    })

db.logs_aplicaciones.insert_many(docs_aplicaciones)
print(f"  {len(docs_aplicaciones)} logs de aplicaciones insertados.")

# ─── LOGS_ACCESO ─────────────────────────────────────────────────────────────
print("Insertando logs_acceso...")

# (evento, pg_usuario_id, email, rol, ip, timestamp)
accesos = [
    # Admin
    ("login",  1, "admin@vacunatrack.mx",         "admin",       "187.190.12.5",  dt(2025, 5,  2, 8,  0)),
    ("logout", 1, "admin@vacunatrack.mx",         "admin",       "187.190.12.5",  dt(2025, 5,  2, 14, 0)),
    ("login",  1, "admin@vacunatrack.mx",         "admin",       "187.190.12.5",  dt(2025, 6,  5, 9,  0)),
    ("login",  1, "admin@vacunatrack.mx",         "admin",       "187.190.12.5",  dt(2025, 8,  1, 8, 30)),
    ("login",  1, "admin@vacunatrack.mx",         "admin",       "187.190.12.5",  dt(2025,10, 10, 9,  0)),
    ("login",  1, "admin@vacunatrack.mx",         "admin",       "187.190.12.5",  dt(2025,12,  3, 8,  0)),
    ("login",  1, "admin@vacunatrack.mx",         "admin",       "187.190.12.5",  dt(2026, 1, 20, 9,  0)),
    ("login",  1, "admin@vacunatrack.mx",         "admin",       "187.190.12.5",  dt(2026, 3, 15, 8, 45)),
    ("login",  1, "admin@vacunatrack.mx",         "admin",       "187.190.12.5",  dt(2026, 5,  5, 9,  0)),
    # Diego (responsable 1)
    ("login",  2, "diego@vacunatrack.mx",         "responsable", "201.115.30.10", dt(2025, 5, 11, 8, 0)),
    ("logout", 2, "diego@vacunatrack.mx",         "responsable", "201.115.30.10", dt(2025, 5, 11,16, 0)),
    ("login",  2, "diego@vacunatrack.mx",         "responsable", "201.115.30.10", dt(2025, 7, 10, 8, 0)),
    ("login",  2, "diego@vacunatrack.mx",         "responsable", "201.115.30.10", dt(2026, 1, 12, 8, 0)),
    ("login",  2, "diego@vacunatrack.mx",         "responsable", "201.115.30.10", dt(2026, 3, 17, 8, 0)),
    ("login",  2, "diego@vacunatrack.mx",         "responsable", "201.115.30.10", dt(2026, 5, 16, 8, 0)),
    # Ana (responsable 2)
    ("login",  3, "ana@vacunatrack.mx",           "responsable", "201.115.31.20", dt(2025, 5, 16, 8, 0)),
    ("login",  3, "ana@vacunatrack.mx",           "responsable", "201.115.31.20", dt(2025,11, 16, 8, 0)),
    ("login",  3, "ana@vacunatrack.mx",           "responsable", "201.115.31.20", dt(2026, 2,  3, 8, 0)),
    # Roberto (responsable 3)
    ("login",  4, "roberto.chavez@vacunatrack.mx","responsable", "201.115.32.30", dt(2025, 6,  5, 8, 0)),
    ("login",  4, "roberto.chavez@vacunatrack.mx","responsable", "201.115.32.30", dt(2025,12,  5, 8, 0)),
    ("login",  4, "roberto.chavez@vacunatrack.mx","responsable", "201.115.32.30", dt(2026, 4,  4, 8, 0)),
    # María (responsable 4)
    ("login",  5, "maria@vacunatrack.mx",         "responsable", "177.200.45.60", dt(2025, 9, 10, 8, 0)),
    ("login",  5, "maria@vacunatrack.mx",         "responsable", "177.200.45.60", dt(2025,11, 10, 8, 0)),
    ("login",  5, "maria@vacunatrack.mx",         "responsable", "177.200.45.60", dt(2026, 1,  9, 8, 0)),
    ("login",  5, "maria@vacunatrack.mx",         "responsable", "177.200.45.60", dt(2026, 3, 10, 8, 0)),
    # Luis (responsable 5)
    ("login",  6, "luis@vacunatrack.mx",          "responsable", "177.200.46.70", dt(2025, 6, 10, 8, 0)),
    ("login",  6, "luis@vacunatrack.mx",          "responsable", "177.200.46.70", dt(2025, 8, 10, 8, 0)),
    ("login",  6, "luis@vacunatrack.mx",          "responsable", "177.200.46.70", dt(2025,10,  9, 8, 0)),
    ("login",  6, "luis@vacunatrack.mx",          "responsable", "177.200.46.70", dt(2025,12,  9, 8, 0)),
    # Tutores
    ("login",  7, "juan@correo.mx",               "tutor",       "189.155.60.20", dt(2025, 5, 11, 9, 5)),
    ("login",  7, "juan@correo.mx",               "tutor",       "189.155.60.20", dt(2025, 7, 10, 9, 5)),
    ("login",  7, "juan@correo.mx",               "tutor",       "189.155.60.20", dt(2026, 1, 12, 9, 0)),
    ("login",  7, "juan@correo.mx",               "tutor",       "189.155.60.20", dt(2026, 5, 16, 9, 0)),
    ("login",  8, "carmen@correo.mx",             "tutor",       "189.155.61.30", dt(2025, 5, 16,10, 0)),
    ("login",  8, "carmen@correo.mx",             "tutor",       "189.155.61.30", dt(2025, 6, 10,10, 5)),
    ("login",  8, "carmen@correo.mx",             "tutor",       "189.155.61.30", dt(2025, 8, 10,10, 0)),
    ("login",  8, "carmen@correo.mx",             "tutor",       "189.155.61.30", dt(2025,10,  9,10, 5)),
    ("login",  9, "roberto.garcia@correo.mx",     "tutor",       "189.155.62.40", dt(2025, 6,  5, 9, 0)),
    ("login",  9, "roberto.garcia@correo.mx",     "tutor",       "189.155.62.40", dt(2025, 8,  5, 9, 5)),
    ("login", 10, "sofia.martinez@correo.mx",     "tutor",       "189.155.63.50", dt(2025, 9, 16,10, 0)),
    ("login", 10, "sofia.martinez@correo.mx",     "tutor",       "189.155.63.50", dt(2026, 1,  9,10, 5)),
    ("login", 11, "eduardo@correo.mx",            "tutor",       "189.155.64.60", dt(2025, 8, 13, 9, 0)),
    ("login", 11, "eduardo@correo.mx",            "tutor",       "189.155.64.60", dt(2025,10,  5, 9, 5)),
    ("login", 11, "eduardo@correo.mx",            "tutor",       "189.155.64.60", dt(2025,12,  5, 9, 0)),
    ("login", 12, "patricia@correo.mx",           "tutor",       "189.155.65.70", dt(2025, 5, 16,10, 5)),
    ("login", 12, "patricia@correo.mx",           "tutor",       "189.155.65.70", dt(2025,11, 16,10, 0)),
    ("login", 14, "alejandra@correo.mx",          "tutor",       "189.155.67.90", dt(2026, 1, 15, 9, 5)),
    ("login", 14, "alejandra@correo.mx",          "tutor",       "189.155.67.90", dt(2026, 5, 16, 9, 5)),
    ("login", 15, "hector@correo.mx",             "tutor",       "189.155.68.11", dt(2025, 3, 12, 9, 0)),
    ("login", 15, "hector@correo.mx",             "tutor",       "189.155.68.11", dt(2025, 5, 11, 9, 0)),
    # Intento fallido
    ("login_fallido", None, "hacker@ext.com",     None,          "200.10.10.10",  dt(2025,11, 5, 3, 0)),
]

db.logs_acceso.insert_many([
    {"timestamp": ts, "evento": ev, "pg_usuario_id": uid,
     "email": em, "rol": rol, "ip": ip}
    for ev, uid, em, rol, ip, ts in accesos
])
print(f"  {len(accesos)} eventos de acceso insertados.")

# ─── EVENTOS_INVENTARIO ───────────────────────────────────────────────────────
print("Insertando eventos_inventario...")

inventario_evs = [
    ("asignacion",  1, 1, 1, 2, "BCG",              "Centro de Salud Zona Norte",   200, dt(2022,1,10)),
    ("asignacion",  2, 1, 2, 2, "Hepatitis B",      "Centro de Salud Zona Norte",   200, dt(2022,1,10)),
    ("asignacion",  3, 1, 3, 2, "Pentavalente",     "Centro de Salud Zona Norte",   200, dt(2022,1,10)),
    ("asignacion",  8, 2, 1, 3, "BCG",              "Centro de Salud Zapopan",      200, dt(2022,1,12)),
    ("asignacion",  9, 2, 2, 3, "Hepatitis B",      "Centro de Salud Zapopan",      200, dt(2022,1,12)),
    ("asignacion", 15, 3, 1, 4, "BCG",              "Centro de Salud Tlaquepaque",  200, dt(2022,1,14)),
    ("asignacion", 22, 4, 1, 5, "BCG",              "IMSS Unidad Médica Sur",       200, dt(2022,1,16)),
    ("asignacion", 29, 5, 1, 6, "BCG",              "Centro de Salud Monterrey Norte",200,dt(2022,1,18)),
    ("asignacion", 36, 1, 8, 2, "Varicela",         "Centro de Salud Zona Norte",   150, dt(2025,3, 1)),
    ("asignacion", 37, 1, 9, 2, "VPH",              "Centro de Salud Zona Norte",   100, dt(2025,3, 1)),
    ("asignacion", 38, 1,10, 2, "Hepatitis A",      "Centro de Salud Zona Norte",   100, dt(2025,3, 1)),
    ("confirmacion", 1,1, 1, 2, "BCG",              "Centro de Salud Zona Norte",   200, dt(2022,1,10,8,5)),
    ("confirmacion", 7,1, 7, 2, "Influenza",        "Centro de Salud Zona Norte",   200, dt(2025,2, 1,8,5)),
    ("confirmacion",14,2, 7, 3, "Influenza",        "Centro de Salud Zapopan",      200, dt(2025,2, 1,8,5)),
    ("confirmacion",21,3, 7, 4, "Influenza",        "Centro de Salud Tlaquepaque",  200, dt(2025,2, 1,8,5)),
    ("confirmacion",28,4, 7, 5, "Influenza",        "IMSS Unidad Médica Sur",       200, dt(2025,2, 1,8,5)),
    ("confirmacion",35,5, 7, 6, "Influenza",        "Centro de Salud Monterrey Norte",200,dt(2025,2,1,8,5)),
]

db.eventos_inventario.insert_many([
    {"timestamp": ts, "evento": ev, "pg_inventario_id": inv_id,
     "pg_centro_id": cen, "pg_lote_id": lot, "pg_usuario_id": usr,
     "vacuna_nombre": vac, "centro_nombre": cnom, "stock": stk}
    for ev, inv_id, cen, lot, usr, vac, cnom, stk, ts in inventario_evs
])
print(f"  {len(inventario_evs)} eventos de inventario insertados.")

# ─── EVENTOS_BEACON ───────────────────────────────────────────────────────────
print("Insertando eventos_beacon...")

beacons = [
    # (pg_centro_id, beacon_id, pg_tutor_id, metodo, timestamp)
    (1, "FSC-GDL-001", 7,  "beacon_id",    dt(2025, 8, 15, 9, 8)),
    (1, "FSC-GDL-001", 7,  "beacon_id",    dt(2025,11, 20,10, 3)),
    (2, "FSC-ZAP-001", 8,  "beacon_id",    dt(2025, 7,  1, 9,28)),
    (2, "FSC-ZAP-001", 9,  "beacon_id",    dt(2025, 9, 12,10,58)),
    (1, "FSC-GDL-001",15,  "beacon_id",    dt(2025, 3, 13, 8,53)),
    (5, None,          11, "gps_proximity",dt(2025, 8, 14, 9,18)),
    (5, None,           8, "gps_proximity",dt(2025, 6, 11, 9,58)),
    (3, None,          13, "gps_proximity",dt(2025, 5, 19, 9,33)),
    (1, "FSC-GDL-001",14,  "beacon_id",    dt(2026, 1, 16, 8,48)),
    (4, "FSC-MX-001",  5,  "beacon_id",    dt(2026, 3, 11, 9, 3)),
    (2, "FSC-ZAP-001", 8,  "beacon_id",    dt(2025,10,  9, 9,58)),
    (4, "FSC-MX-001",  4,  "beacon_id",    dt(2025,12,  5, 8,58)),
    (1, "FSC-GDL-001", 2,  "beacon_id",    dt(2025, 5, 11, 7,55)),
    (3, None,           4, "gps_proximity",dt(2025,10,  5,10,58)),
    (1, "FSC-GDL-001", 2,  "beacon_id",    dt(2026, 5, 16, 7,58)),
    (2, "FSC-ZAP-001", 3,  "beacon_id",    dt(2025,11, 16, 7,58)),
    (4, "FSC-MX-001",  5,  "beacon_id",    dt(2025, 9, 10, 8,58)),
    (5, None,           6, "gps_proximity",dt(2025, 6, 10, 7,58)),
    (1, "FSC-GDL-001", 7,  "beacon_id",    dt(2026, 1, 12, 9, 2)),
    (4, "FSC-MX-001",  5,  "beacon_id",    dt(2026, 1,  9, 7,58)),
]

db.eventos_beacon.insert_many([
    {"timestamp": ts, "pg_centro_id": cen, "beacon_id": bid,
     "pg_tutor_id": tut, "metodo": met}
    for cen, bid, tut, met, ts in beacons
])
print(f"  {len(beacons)} eventos de beacon insertados.")

# ─── BUSQUEDAS_GPS ────────────────────────────────────────────────────────────
print("Insertando busquedas_gps...")

# Coordenadas base de cada centro para simular búsquedas cercanas
gps_searches = [
    # (lat, lon, vacuna_id, centros_encontrados, pg_usuario_id, timestamp)
    (20.6700,-103.3445,  6, 3,  7, dt(2025, 8,15, 9, 5)),
    (20.7200,-103.3827,  3, 2,  8, dt(2025, 7, 1, 9,24)),
    (20.7205,-103.3820,  3, 2,  9, dt(2025, 9,12,10,54)),
    (25.6720,-100.3185,  6, 1, 10, dt(2025, 9,16,10, 9)),
    (20.6390,-103.3105,  4, 2, 11, dt(2025, 8,14, 9,16)),
    (20.6730,-103.3440,  1, 3, 12, dt(2025, 1,16,10,18)),
    (20.6400,-103.3110,  3, 2, 13, dt(2025, 5,19, 9,29)),
    (20.6720,-103.3450,  2, 3, 14, dt(2026, 1,16, 8,43)),
    (20.6710,-103.3440,  3, 3, 15, dt(2025, 3,13, 8,48)),
    (20.6390,-103.3100,  6, 2,  8, dt(2025, 6,11, 9,53)),
    (20.6700,-103.3445,  6, 3,  7, dt(2025,11,20, 9,58)),
    (25.6720,-100.3185,  3, 1, 10, dt(2026, 1,10, 9,38)),
    (20.6730,-103.3440,  7, 2,  7, dt(2026, 5,16, 9, 2)),
    (20.6390,-103.3105,  3, 2, 11, dt(2025,12, 5, 9, 2)),
    (20.6700,-103.3445,  4, 3,  2, dt(2026, 3,17, 7,52)),
    (20.6710,-103.3440,  1, 3, 15, dt(2025, 5,11, 8,58)),
    (20.7200,-103.3827,  3, 2,  8, dt(2025,10, 9, 9,52)),
    (20.6400,-103.3110,  6, 1,  4, dt(2025,10, 5,10,52)),
    (20.6700,-103.3445,  2, 3, 14, dt(2026, 5,16, 9, 3)),
    (20.6390,-103.3105,  3, 2,  6, dt(2025, 6, 5, 8,58)),
    (20.7200,-103.3827,  6, 2,  3, dt(2025,11,16, 7,52)),
    (25.6720,-100.3185,  1, 1,  5, dt(2025, 9,10, 8,52)),
    (20.6390,-103.3105,  7, 2, 11, dt(2026, 2, 3,10,52)),
    (20.6700,-103.3445,  3, 3,  2, dt(2026, 1,15, 9, 8)),
    (20.6400,-103.3110,  4, 2,  4, dt(2026, 4, 4,10,52)),
]

db.busquedas_gps.insert_many([
    {
        "timestamp":           ts,
        "ubicacion":           {"type": "Point", "coordinates": [lon, lat]},
        "lat":                 lat,
        "lon":                 lon,
        "vacuna_id":           vac,
        "centros_encontrados": cen,
        "pg_usuario_id":       usr,
    }
    for lat, lon, vac, cen, usr, ts in gps_searches
])
print(f"  {len(gps_searches)} búsquedas GPS insertadas.")

print("\n✓ Seed MongoDB completado.")
client.close()

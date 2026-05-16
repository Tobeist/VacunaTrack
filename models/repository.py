from __future__ import annotations
# repository.py — Capa de acceso a datos de VacunaTrack (esquema v3)
#
# Todas las consultas SELECT usan SPs de lectura (REFCURSOR) o VIEWs.
# Las operaciones de escritura usan SPs con parámetros OUT (p_ok/p_msg/p_id).
# NINGUNA consulta SQL está embebida directamente en este archivo.

from . import db
from werkzeug.security import check_password_hash


# ─────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────

def buscar_usuario_por_email(email: str) -> dict | None:
    return db.call_read_sp_one('sp_buscar_usuario_por_email', [email.lower()])


def listar_usuarios() -> list[dict]:
    rows = db.call_read_sp('sp_listar_usuarios')
    for row in rows:
        row['roles'] = row['roles'].split(',') if row.get('roles') else []
        row['cedulas'] = cedulas_de_responsable(row['usuario_id']) if 'responsable' in row['roles'] else []
    return rows


def obtener_usuario(usuario_id: int) -> dict | None:
    row = db.call_read_sp_one('sp_obtener_usuario', [usuario_id])
    if row:
        row['roles'] = row['roles'].split(',') if row.get('roles') else []
        row['cedulas'] = cedulas_de_responsable(usuario_id) if 'responsable' in row['roles'] else []
    return row


def crear_usuario(datos: dict) -> dict:
    roles      = datos.get('roles') or []
    ced_nums   = datos.get('cedulas_nums') or []
    ced_specs  = datos.get('cedulas_specs') or []
    r = _sp('sp_crear_usuario_unificado', [
        datos.get('prim_nombre'), datos.get('seg_nombre'),
        datos.get('apellido_pat'), datos.get('apellido_mat'),
        datos.get('telefono'), datos.get('curp'),
        datos.get('rfc') or None, datos.get('email'), datos.get('contrasena'),
        datos.get('centro_id') or None,
        roles, ced_nums, ced_specs,
    ])
    return obtener_usuario(r['p_id']) or {}


def actualizar_usuario(usuario_id: int, datos: dict) -> None:
    roles      = datos.get('roles') or []
    ced_nums   = datos.get('cedulas_nums') or []
    ced_specs  = datos.get('cedulas_specs') or []
    _sp('sp_actualizar_usuario_unificado', [
        usuario_id,
        datos.get('prim_nombre'), datos.get('seg_nombre'),
        datos.get('apellido_pat'), datos.get('apellido_mat'),
        datos.get('telefono'), datos.get('curp'),
        datos.get('rfc') or None, datos.get('email'),
        datos.get('centro_id') or None,
        roles, ced_nums, ced_specs,
    ], out_count=2)


def eliminar_usuario(usuario_id: int, session_user_id: int) -> None:
    _sp('sp_eliminar_usuario_unificado', [usuario_id, session_user_id], out_count=2)


def toggle_usuario_activo(usuario_id: int, session_user_id: int) -> dict:
    return _sp('sp_toggle_usuario_activo', [usuario_id, session_user_id], out_count=3)


def roles_de_usuario(email: str) -> list[str]:
    rows = db.call_read_sp('sp_roles_de_usuario', [email.lower()])
    return [r['rol_nombre'] for r in rows] if rows else []


def verificar_password(usuario: dict, password: str) -> bool:
    return check_password_hash(usuario['password'], password)


def cambiar_password(role: str, user_id: int, nuevo_hash: str) -> None:
    _sp('sp_cambiar_password', [user_id, nuevo_hash], out_count=2)


# ─────────────────────────────────────────────
# HELPER interno: llamada a stored procedures de escritura
# ─────────────────────────────────────────────

def _sp(name: str, params: list, out_count: int = 3) -> dict:
    """Llama al SP indicado y lanza ValueError si p_ok == 0."""
    result = db.call_write_sp(name, params, out_count)
    if not result.get('p_ok'):
        raise ValueError(result.get('p_msg', 'Error desconocido'))
    return result


# ─────────────────────────────────────────────
# ADMINISTRADORES
# ─────────────────────────────────────────────

def listar_administradores() -> list[dict]:
    return db.call_read_sp('sp_listar_administradores')


def obtener_administrador(admin_id: int) -> dict | None:
    return db.call_read_sp_one('sp_obtener_administrador', [admin_id])


def crear_admin(datos: dict) -> dict:
    """datos usa claves admin_* (formulario) + admin_contrasena."""
    r = _sp('sp_crear_admin', [
        datos.get('admin_prim_nombre'), datos.get('admin_seg_nombre'),
        datos.get('admin_apellido_pat'), datos.get('admin_apellido_mat'),
        datos.get('admin_telefono'), datos.get('admin_curp'),
        datos.get('admin_rfc'), datos.get('admin_email'),
        datos.get('admin_contrasena'),
    ])
    return obtener_administrador(r['p_id']) or {}


def eliminar_admin(admin_id: int, session_id: int = 0) -> None:
    _sp('sp_eliminar_admin', [admin_id, session_id], out_count=2)


def actualizar_admin(admin_id: int, campos: dict) -> None:
    _sp('sp_actualizar_admin', [
        admin_id,
        campos.get('admin_prim_nombre'), campos.get('admin_seg_nombre'),
        campos.get('admin_apellido_pat'), campos.get('admin_apellido_mat'),
        campos.get('admin_telefono'), campos.get('admin_curp'),
        campos.get('admin_rfc'), campos.get('admin_email'),
    ], out_count=2)


# ─────────────────────────────────────────────
# PACIENTES
# ─────────────────────────────────────────────

def listar_pacientes() -> list[dict]:
    return db.call_read_sp('sp_listar_pacientes')


def obtener_paciente(paciente_id: int) -> dict | None:
    return db.call_read_sp_one('sp_obtener_paciente', [paciente_id])


def obtener_paciente_por_nfc(nfc_uid: str) -> dict | None:
    return db.call_read_sp_one('sp_obtener_paciente_por_nfc', [nfc_uid])


def obtener_paciente_por_curp(curp: str) -> dict | None:
    return db.call_read_sp_one('sp_obtener_paciente_por_curp', [curp.upper()])


def obtener_paciente_por_cert_nac(cert_nac: str) -> dict | None:
    return db.call_read_sp_one('sp_obtener_paciente_por_cert_nac', [cert_nac.strip()])


def crear_paciente(datos: dict) -> dict:
    r = _sp('sp_crear_paciente', [
        datos.get('paciente_prim_nombre'), datos.get('paciente_seg_nombre'),
        datos.get('paciente_apellido_pat'), datos.get('paciente_apellido_mat'),
        datos.get('paciente_curp'), datos.get('paciente_num_cert_nac'),
        datos.get('paciente_fecha_nac'), datos.get('paciente_sexo'),
        datos.get('paciente_nfc'), datos.get('esquema_id'),
    ])
    return obtener_paciente(r['p_id']) or {}


def eliminar_paciente(paciente_id: int) -> None:
    _sp('sp_eliminar_paciente', [paciente_id], out_count=2)


def actualizar_paciente(paciente_id: int, campos: dict) -> None:
    _sp('sp_actualizar_paciente', [
        paciente_id,
        campos.get('paciente_prim_nombre'), campos.get('paciente_seg_nombre'),
        campos.get('paciente_apellido_pat'), campos.get('paciente_apellido_mat'),
        campos.get('paciente_curp'), campos.get('paciente_num_cert_nac'),
        campos.get('paciente_fecha_nac'), campos.get('paciente_sexo'),
        campos.get('paciente_nfc'), campos.get('esquema_id'),
    ], out_count=2)


# ─────────────────────────────────────────────
# TUTORES
# ─────────────────────────────────────────────

def listar_tutores() -> list[dict]:
    return db.call_read_sp('sp_listar_tutores')


def obtener_tutor(tutor_id: int) -> dict | None:
    return db.call_read_sp_one('sp_obtener_tutor', [tutor_id])


def crear_tutor(datos: dict) -> dict:
    """datos usa claves tutor_* (formulario) + tutor_contrasena."""
    r = _sp('sp_crear_tutor', [
        datos.get('tutor_prim_nombre'), datos.get('tutor_seg_nombre'),
        datos.get('tutor_apellido_pat'), datos.get('tutor_apellido_mat'),
        datos.get('tutor_telefono'), datos.get('tutor_curp'),
        datos.get('tutor_email'), datos.get('tutor_contrasena'),
    ])
    return obtener_tutor(r['p_id']) or {}


def actualizar_tutor(tutor_id: int, campos: dict) -> None:
    """campos usa claves tutor_* (del formulario)."""
    _sp('sp_actualizar_tutor', [
        tutor_id,
        campos.get('tutor_prim_nombre'), campos.get('tutor_seg_nombre'),
        campos.get('tutor_apellido_pat'), campos.get('tutor_apellido_mat'),
        campos.get('tutor_telefono'), campos.get('tutor_curp'),
        campos.get('tutor_email'),
    ], out_count=2)


def eliminar_tutor(tutor_id: int) -> None:
    _sp('sp_eliminar_tutor', [tutor_id], out_count=2)


def pacientes_de_tutor(tutor_id: int) -> list[dict]:
    return db.call_read_sp('sp_pacientes_de_tutor', [tutor_id])


# ─────────────────────────────────────────────
# RESPONSABLES
# ─────────────────────────────────────────────

def listar_responsables() -> list[dict]:
    rows = db.call_read_sp('sp_listar_responsables')
    for row in rows:
        row['cedulas'] = cedulas_de_responsable(row['responsable_id'])
    return rows


def obtener_responsable(responsable_id: int) -> dict | None:
    return db.call_read_sp_one('sp_obtener_responsable', [responsable_id])


def crear_responsable(datos: dict) -> dict:
    """datos usa claves responsable_* (formulario) + responsable_contrasena."""
    r = _sp('sp_crear_responsable', [
        datos.get('responsable_prim_nombre'), datos.get('responsable_seg_nombre'),
        datos.get('responsable_apellido_pat'), datos.get('responsable_apellido_mat'),
        datos.get('responsable_telefono'), datos.get('responsable_curp'),
        datos.get('responsable_rfc'), datos.get('responsable_email'),
        datos.get('responsable_contrasena'), datos.get('centro_id'),
    ])
    return obtener_responsable(r['p_id']) or {}


def eliminar_responsable(responsable_id: int) -> None:
    _sp('sp_eliminar_responsable', [responsable_id], out_count=2)


def actualizar_responsable(responsable_id: int, campos: dict) -> None:
    _sp('sp_actualizar_responsable', [
        responsable_id,
        campos.get('responsable_prim_nombre'), campos.get('responsable_seg_nombre'),
        campos.get('responsable_apellido_pat'), campos.get('responsable_apellido_mat'),
        campos.get('responsable_telefono'), campos.get('responsable_curp'),
        campos.get('responsable_rfc'), campos.get('responsable_email'),
        campos.get('centro_id'),
    ], out_count=2)


def cedulas_de_responsable(usuario_id: int) -> list[dict]:
    return db.call_read_sp('sp_cedulas_de_responsable', [usuario_id])


def agregar_cedula(usuario_id: int, numero: str, especialidad: str | None) -> dict:
    r = _sp('sp_agregar_cedula', [usuario_id, numero, especialidad])
    return db.call_read_sp_one('sp_obtener_cedula', [r['p_id']]) or {}


# ─────────────────────────────────────────────
# RELACIONES PACIENTE-TUTOR
# ─────────────────────────────────────────────

def listar_relaciones() -> list[dict]:
    return db.call_read_sp('sp_listar_relaciones')


def existe_relacion(paciente_id: int, tutor_id: int) -> bool:
    row = db.call_read_sp_one('sp_existe_relacion', [paciente_id, tutor_id])
    return bool(row['result']) if row else False


def crear_relacion(paciente_id: int, tutor_id: int, pac_nombre: str, tut_nombre: str) -> dict:
    r = _sp('sp_crear_relacion', [paciente_id, tutor_id])
    row = db.call_read_sp_one('sp_obtener_relacion', [r['p_id']])
    return row or {'pac_tut_id': r['p_id'], 'paciente_id': paciente_id,
                   'tutor_id': tutor_id, 'paciente': pac_nombre, 'tutor': tut_nombre}


def eliminar_relacion(pac_tut_id: int) -> None:
    _sp('sp_eliminar_relacion', [pac_tut_id], out_count=2)


# ─────────────────────────────────────────────
# APLICACIONES
# ─────────────────────────────────────────────

def listar_aplicaciones() -> list[dict]:
    return db.call_read_sp('sp_listar_aplicaciones')


def aplicaciones_de_paciente(paciente_id: int) -> list[dict]:
    return db.call_read_sp('sp_aplicaciones_de_paciente', [paciente_id])


def dosis_ya_aplicada(paciente_id: int, dosis_id: int) -> bool:
    row = db.call_read_sp_one('sp_dosis_ya_aplicada', [paciente_id, dosis_id])
    return bool(row['result']) if row else False


def registrar_aplicacion(datos: dict) -> dict:
    """
    datos: paciente_id, usuario_id, centro_id, lote_id, dosis_id,
           aplicacion_observaciones.
    El SP usa NOW() internamente; el trigger descuenta el inventario automáticamente.
    """
    r = _sp('sp_registrar_aplicacion', [
        datos['paciente_id'], datos['usuario_id'], datos['centro_id'],
        datos['lote_id'], datos['dosis_id'],
        datos.get('aplicacion_observaciones'),
    ])
    return db.call_read_sp_one('sp_obtener_aplicacion', [r['p_id']]) or {}


def obtener_aplicacion(aplicacion_id: int) -> dict | None:
    return db.call_read_sp_one('sp_obtener_aplicacion', [aplicacion_id])


def actualizar_aplicacion(aplicacion_id: int, campos: dict) -> None:
    _sp('sp_actualizar_aplicacion', [
        aplicacion_id,
        campos.get('aplicacion_observaciones'),
    ], out_count=2)


def anular_aplicacion(aplicacion_id: int, motivo: str) -> None:
    _sp('sp_anular_aplicacion', [aplicacion_id, motivo], out_count=2)


def historial_vacunacion_paciente(paciente_id: int, esquema_id: int) -> list[dict]:
    """Dosis del esquema del paciente con info de aplicación (LEFT JOIN sobre vistas)."""
    return db.call_read_sp('sp_historial_vacunacion_paciente', [paciente_id, esquema_id])


# ─────────────────────────────────────────────
# INVENTARIO
# ─────────────────────────────────────────────

def listar_inventarios() -> list[dict]:
    return db.call_read_sp('sp_listar_inventarios')


def inventarios_activos_de_centro(centro_id: int) -> list[dict]:
    return db.call_read_sp('sp_inventarios_activos_de_centro', [centro_id])


def obtener_inventario(inventario_id: int) -> dict | None:
    return db.call_read_sp_one('sp_obtener_inventario', [inventario_id])


def inventarios_pendientes_de_centro(centro_id: int) -> list[dict]:
    return db.call_read_sp('sp_inventarios_pendientes_de_centro', [centro_id])


def confirmar_recepcion_inventario(lote_codigo: str, responsable_id: int) -> dict:
    return db.call_write_sp('sp_confirmar_recepcion_inventario', [lote_codigo, responsable_id], out_count=2)


def transferir_inventario(inv_origen_id: int, centro_destino_id: int, cantidad: int) -> dict:
    return db.call_write_sp('sp_transferir_inventario',
                            [inv_origen_id, centro_destino_id, cantidad],
                            out_count=3)


def listar_transferencias() -> list[dict]:
    return db.call_read_sp('sp_listar_transferencias')


def asignar_inventario(datos: dict) -> dict:
    """
    datos: centro_id, lote_id, inventario_stock_inicial, inventario_stock_actual,
    inventario_activo_desde.
    """
    r = _sp('sp_asignar_inventario', [
        datos['centro_id'], datos['lote_id'],
        datos['inventario_stock_inicial'], datos['inventario_stock_actual'],
        datos.get('inventario_activo_desde'),
    ])
    return obtener_inventario(r['p_id']) or {}


def centros_con_vacuna_disponible(vacuna_id: int) -> list[dict]:
    return db.call_read_sp('sp_centros_con_vacuna_disponible', [vacuna_id])


def inventarios_disponibles_para_vacuna(vacuna_id: int, centro_id: int | None = None) -> list[dict]:
    """Inventarios activos, con stock, no caducados, para una vacuna específica.
    Si centro_id está dado, solo del centro indicado (uso clínico).
    """
    todos = db.call_read_sp('sp_listar_inventarios')
    from datetime import date as _d
    hoy = _d.today()
    result = []
    for inv in todos:
        if not inv.get('inventario_activo'):
            continue
        if (inv.get('inventario_stock_actual') or 0) <= 0:
            continue
        if inv.get('vacuna_id') != vacuna_id:
            continue
        cad = inv.get('lote_fecha_caducidad')
        if cad and hasattr(cad, 'year') and cad < hoy:
            continue
        if centro_id is not None and inv.get('centro_id') != centro_id:
            continue
        result.append(inv)
    return result


def actualizar_inventario(inventario_id: int, campos: dict) -> None:
    _sp('sp_actualizar_inventario', [
        inventario_id,
        campos.get('inventario_stock_actual'),
        campos.get('inventario_activo'),
    ], out_count=2)


def eliminar_inventario(inventario_id: int) -> None:
    _sp('sp_eliminar_inventario', [inventario_id], out_count=2)


# ─────────────────────────────────────────────
# LOTES
# ─────────────────────────────────────────────

def listar_lotes() -> list[dict]:
    return db.call_read_sp('sp_listar_lotes')


def obtener_lote(lote_id: int) -> dict | None:
    return db.call_read_sp_one('sp_obtener_lote', [lote_id])


def crear_lote(datos: dict) -> dict:
    """datos: lote_codigo, lote_fecha_fabricacion, lote_fecha_caducidad,
    vacuna_id, fabricante_id, lote_cant_inicial, proveedor_id."""
    r = _sp('sp_crear_lote', [
        datos['lote_codigo'], datos['lote_fecha_fabricacion'], datos['lote_fecha_caducidad'],
        datos['lote_cant_inicial'], datos['vacuna_id'], datos['fabricante_id'],
        datos['proveedor_id'],
    ])
    return obtener_lote(r['p_id']) or {}


def actualizar_lote(lote_id: int, campos: dict) -> None:
    _sp('sp_actualizar_lote', [
        lote_id,
        campos.get('lote_codigo'),
        campos.get('lote_fecha_fabricacion'),
        campos.get('lote_fecha_caducidad'),
        campos.get('lote_cant_inicial'),
        campos.get('vacuna_id'),
        campos.get('fabricante_id'),
        campos.get('proveedor_id'),
    ], out_count=2)


def eliminar_lote(lote_id: int) -> None:
    _sp('sp_eliminar_lote', [lote_id], out_count=2)


# ─────────────────────────────────────────────
# PROVEEDORES
# ─────────────────────────────────────────────

def listar_proveedores() -> list[dict]:
    return db.call_read_sp('sp_listar_proveedores')


def obtener_proveedor(proveedor_id: int) -> dict | None:
    return db.call_read_sp_one('sp_obtener_proveedor', [proveedor_id])


def crear_proveedor(datos: dict) -> dict:
    """datos: proveedor_prim_nombre, proveedor_apellido_pat, proveedor_email,
    proveedor_telefono, proveedor_empresa, fabricante_id."""
    r = _sp('sp_crear_proveedor', [
        datos.get('proveedor_prim_nombre'), datos.get('proveedor_seg_nombre'),
        datos.get('proveedor_apellido_pat'), datos.get('proveedor_apellido_mat'),
        datos.get('proveedor_email'), datos.get('proveedor_telefono'),
        datos.get('proveedor_empresa'), datos['fabricante_id'],
    ])
    return obtener_proveedor(r['p_id']) or {}


def actualizar_proveedor(proveedor_id: int, campos: dict) -> None:
    _sp('sp_actualizar_proveedor', [
        proveedor_id,
        campos.get('proveedor_prim_nombre'), campos.get('proveedor_seg_nombre'),
        campos.get('proveedor_apellido_pat'), campos.get('proveedor_apellido_mat'),
        campos.get('proveedor_email'), campos.get('proveedor_telefono'),
        campos.get('proveedor_empresa'), campos.get('fabricante_id'),
    ], out_count=2)


def eliminar_proveedor(proveedor_id: int) -> None:
    _sp('sp_eliminar_proveedor', [proveedor_id], out_count=2)


# ─────────────────────────────────────────────
# CATÁLOGOS CLÍNICOS
# ─────────────────────────────────────────────

def listar_vacunas() -> list[dict]:
    return db.call_read_sp('sp_listar_vacunas')


def obtener_vacuna(vacuna_id: int) -> dict | None:
    return db.call_read_sp_one('sp_obtener_vacuna', [vacuna_id])


def crear_vacuna(datos: dict) -> dict:
    r = _sp('sp_crear_vacuna', [datos['vacuna_nombre']])
    return obtener_vacuna(r['p_id']) or {}


def actualizar_vacuna(vacuna_id: int, campos: dict) -> None:
    _sp('sp_actualizar_vacuna', [vacuna_id, campos.get('vacuna_nombre')], out_count=2)


def eliminar_vacuna(vacuna_id: int) -> None:
    _sp('sp_eliminar_vacuna', [vacuna_id], out_count=2)


def listar_dosis(vacuna_id: int | None = None) -> list[dict]:
    if vacuna_id:
        return db.call_read_sp('sp_listar_dosis_por_vacuna', [vacuna_id])
    return db.call_read_sp('sp_listar_dosis')


def obtener_dosis(dosis_id: int) -> dict | None:
    return db.call_read_sp_one('sp_obtener_dosis', [dosis_id])


def crear_dosis(datos: dict) -> dict:
    r = _sp('sp_crear_dosis', [
        datos['vacuna_id'], datos['dosis_tipo'], datos['dosis_cant_ml'],
        datos.get('dosis_area_aplicacion'), datos.get('dosis_edad_oportuna_dias', 0),
        datos.get('dosis_intervalo_min_dias', 0), datos.get('dosis_limite_edad_dias'),
    ])
    return obtener_dosis(r['p_id']) or {}


def listar_esquemas() -> list[dict]:
    return db.call_read_sp('sp_listar_esquemas')


def obtener_esquema(esquema_id: int) -> dict | None:
    return db.call_read_sp_one('sp_obtener_esquema', [esquema_id])


def crear_esquema(datos: dict) -> dict:
    r = _sp('sp_crear_esquema', [
        datos['esquema_nombre'], datos['esquema_fecha_vigencia'],
        datos.get('vigente_desde'),
    ])
    return obtener_esquema(r['p_id']) or {}


def eliminar_esquema(esquema_id: int) -> None:
    _sp('sp_eliminar_esquema', [esquema_id], out_count=2)


def dosis_de_esquema(esquema_id: int) -> list[dict]:
    return db.call_read_sp('sp_dosis_de_esquema', [esquema_id])


def listar_dosis_esquemas() -> list[dict]:
    return db.call_read_sp('sp_listar_dosis_esquemas')


def listar_dosis_activas() -> list[dict]:
    return db.call_read_sp('sp_listar_dosis_activas')


def cerrar_esquema(esquema_id: int) -> None:
    _sp('sp_cerrar_esquema', [esquema_id], out_count=2)


def desactivar_dosis(dosis_id: int) -> None:
    _sp('sp_desactivar_dosis', [dosis_id], out_count=2)


def asignar_esquema_auto(viejo_id: int, nuevo_id: int) -> dict:
    return _sp('sp_asignar_esquema_auto', [viejo_id, nuevo_id])


def resolver_conflicto_esquema(paciente_id: int, esquema_nuevo_id: int, accion: str) -> dict:
    return db.call_write_sp('sp_resolver_conflicto',
                            [paciente_id, esquema_nuevo_id, accion], out_count=2)


def listar_conflictos_esquema() -> list[dict]:
    return db.call_read_sp('sp_listar_conflictos_esquema')


def agregar_dosis_a_esquema(esquema_id: int, dosis_id: int) -> dict:
    r = _sp('sp_agregar_dosis_a_esquema', [esquema_id, dosis_id])
    return {'dosis_esq_id': r.get('p_id'), 'esquema_id': esquema_id, 'dosis_id': dosis_id}


# ─────────────────────────────────────────────
# PADECIMIENTOS
# ─────────────────────────────────────────────

def listar_padecimientos() -> list[dict]:
    return db.call_read_sp('sp_listar_padecimientos')


def crear_padecimiento(datos: dict) -> dict:
    r = _sp('sp_crear_padecimiento', [
        datos['padecimiento_nombre'], datos.get('padecimiento_descripcion'),
    ])
    return db.call_read_sp_one('sp_obtener_padecimiento', [r['p_id']]) or {}


def vincular_vacuna_padecimiento(vacuna_id: int, padecimiento_id: int) -> None:
    db.call_write_sp('sp_vincular_vacuna_padecimiento', [vacuna_id, padecimiento_id])


def actualizar_padecimiento(padecimiento_id: int, campos: dict) -> None:
    _sp('sp_actualizar_padecimiento', [
        padecimiento_id,
        campos.get('padecimiento_nombre'),
        campos.get('padecimiento_descripcion'),
    ], out_count=2)


def eliminar_padecimiento(padecimiento_id: int) -> None:
    _sp('sp_eliminar_padecimiento', [padecimiento_id], out_count=2)


def vacunas_de_padecimiento(padecimiento_id: int) -> list[int]:
    """Devuelve los IDs de vacunas vinculadas a un padecimiento."""
    try:
        rows = db.call_read_sp('sp_vacunas_de_padecimiento', [padecimiento_id])
        return [r['vacuna_id'] for r in rows]
    except Exception:
        return []


def sincronizar_vacunas_padecimiento(padecimiento_id: int, vacuna_ids: list[int]) -> None:
    """Reemplaza el conjunto de vacunas vinculadas al padecimiento."""
    db.call_write_sp('sp_limpiar_vacunas_padecimiento', [padecimiento_id], out_count=2)
    for vid in vacuna_ids:
        try:
            db.call_write_sp('sp_vincular_vacuna_padecimiento', [vid, padecimiento_id])
        except Exception:
            continue


# ─────────────────────────────────────────────
# FABRICANTES
# ─────────────────────────────────────────────

def listar_fabricantes() -> list[dict]:
    return db.call_read_sp('sp_listar_fabricantes')


def obtener_fabricante(fabricante_id: int) -> dict | None:
    return db.call_read_sp_one('sp_obtener_fabricante', [fabricante_id])


def crear_fabricante(datos: dict) -> dict:
    r = _sp('sp_crear_fabricante', [
        datos['fabricante_nombre'], datos['pais_id'], datos.get('fabricante_telefono'),
    ])
    return obtener_fabricante(r['p_id']) or {}


def actualizar_fabricante(fabricante_id: int, campos: dict) -> None:
    _sp('sp_actualizar_fabricante', [
        fabricante_id,
        campos.get('fabricante_nombre'),
        campos.get('pais_id'),
        campos.get('fabricante_telefono'),
    ], out_count=2)


def eliminar_fabricante(fabricante_id: int) -> None:
    _sp('sp_eliminar_fabricante', [fabricante_id], out_count=2)


# ─────────────────────────────────────────────
# CENTROS DE SALUD
# ─────────────────────────────────────────────

def listar_centros() -> list[dict]:
    return db.call_read_sp('sp_listar_centros')


def obtener_centro(centro_id: int) -> dict | None:
    return db.call_read_sp_one('sp_obtener_centro', [centro_id])


def crear_centro(datos: dict) -> dict:
    r = _sp('sp_crear_centro', [
        datos['centro_nombre'], datos.get('centro_calle'), datos.get('centro_numero'),
        datos.get('centro_codigo_postal'), datos['ciudad_id'],
        datos.get('centro_horario_inicio'), datos.get('centro_horario_fin'),
        datos.get('centro_latitud'), datos.get('centro_longitud'),
        datos.get('centro_telefono'), datos.get('centro_beacon'),
    ])
    return obtener_centro(r['p_id']) or {}


def obtener_centro_por_beacon(beacon_id: str) -> dict | None:
    return db.call_read_sp_one('sp_obtener_centro_por_beacon', [beacon_id])


def vacunas_en_centro(centro_id: int) -> list[dict]:
    rows = db.call_read_sp('sp_vacunas_en_centro', [centro_id])
    for r in rows:
        if r.get('stock_total') is not None:
            r['stock_total'] = int(r['stock_total'])
    return rows


def registrar_lectura_beacon(centro_id: int, tutor_id: int) -> None:
    _sp('sp_registrar_lectura_beacon', [centro_id, tutor_id], out_count=2)


def registrar_evento_gps(tutor_id: int, lat: float, lon: float) -> None:
    db.call_write_sp('sp_registrar_evento_gps', [tutor_id, lat, lon], out_count=2)


def personas_esperando_en_centro(centro_id: int) -> int:
    row = db.call_read_sp_one('sp_personas_esperando_en_centro', [centro_id])
    return int(row['total']) if row else 0


def tutores_esperando_en_centro(centro_id: int) -> list[dict]:
    return db.call_read_sp('sp_tutores_esperando_en_centro', [centro_id])


def eliminar_centro(centro_id: int) -> None:
    _sp('sp_eliminar_centro', [centro_id], out_count=2)


def actualizar_centro(centro_id: int, campos: dict) -> None:
    _sp('sp_actualizar_centro', [
        centro_id,
        campos.get('centro_nombre'), campos.get('centro_calle'), campos.get('centro_numero'),
        campos.get('centro_codigo_postal'), campos.get('ciudad_id'),
        campos.get('centro_horario_inicio'), campos.get('centro_horario_fin'),
        campos.get('centro_latitud'), campos.get('centro_longitud'),
        campos.get('centro_telefono'), campos.get('centro_beacon'),
    ], out_count=2)


# ─────────────────────────────────────────────
# GEOGRAFÍA
# ─────────────────────────────────────────────

def listar_paises() -> list[dict]:
    return db.call_read_sp('sp_listar_paises')


def obtener_pais(pais_id: int) -> dict | None:
    return db.call_read_sp_one('sp_obtener_pais', [pais_id])


def crear_pais(nombre: str) -> dict:
    r = _sp('sp_crear_pais', [nombre])
    return obtener_pais(r['p_id']) or {}


def actualizar_pais(pais_id: int, nombre: str) -> None:
    _sp('sp_actualizar_pais', [pais_id, nombre], out_count=2)


def eliminar_pais(pais_id: int) -> None:
    _sp('sp_eliminar_pais', [pais_id], out_count=2)


def listar_estados(pais_id: int | None = None) -> list[dict]:
    if pais_id:
        return db.call_read_sp('sp_listar_estados_por_pais', [pais_id])
    return db.call_read_sp('sp_listar_estados')


def obtener_estado(estado_id: int) -> dict | None:
    return db.call_read_sp_one('sp_obtener_estado', [estado_id])


def crear_estado(datos: dict) -> dict:
    r = _sp('sp_crear_estado', [datos['estado_nombre'], datos['pais_id']])
    return obtener_estado(r['p_id']) or {}


def actualizar_estado(estado_id: int, campos: dict) -> None:
    _sp('sp_actualizar_estado', [
        estado_id, campos.get('estado_nombre'), campos.get('pais_id'),
    ], out_count=2)


def eliminar_estado(estado_id: int) -> None:
    _sp('sp_eliminar_estado', [estado_id], out_count=2)


def listar_ciudades(estado_id: int | None = None) -> list[dict]:
    if estado_id:
        return db.call_read_sp('sp_listar_ciudades_por_estado', [estado_id])
    return db.call_read_sp('sp_listar_ciudades')


def obtener_ciudad(ciudad_id: int) -> dict | None:
    return db.call_read_sp_one('sp_obtener_ciudad', [ciudad_id])


def crear_ciudad(datos: dict) -> dict:
    r = _sp('sp_crear_ciudad', [datos['ciudad_nombre'], datos['estado_id']])
    return obtener_ciudad(r['p_id']) or {}


def actualizar_ciudad(ciudad_id: int, campos: dict) -> None:
    _sp('sp_actualizar_ciudad', [
        ciudad_id, campos.get('ciudad_nombre'), campos.get('estado_id'),
    ], out_count=2)


def eliminar_ciudad(ciudad_id: int) -> None:
    _sp('sp_eliminar_ciudad', [ciudad_id], out_count=2)


# ─────────────────────────────────────────────
# ALERTAS
# ─────────────────────────────────────────────

def listar_alertas_inventario() -> list[dict]:
    return db.call_read_sp('sp_listar_alertas_inventario')


def listar_alertas_dosis() -> list[dict]:
    return db.call_read_sp('sp_listar_alertas_dosis')


def recalcular_alertas_inventario(dias_caducidad: int = 30) -> None:
    """Pobla la tabla alertas_inventario según el estado actual de los lotes y stocks."""
    try:
        db.call_write_sp('sp_recalcular_alertas_inventario', [dias_caducidad], out_count=2)
    except Exception:
        pass


def registrar_alerta_dosis(paciente_id: int, dosis_id: int, tipo: str) -> None:
    """Registra una alerta clínica para un paciente. tipo ∈ APLICABLE|ATRASADA|CERCA_LIMITE|FALTANTE."""
    try:
        db.call_write_sp('sp_registrar_alerta_dosis', [paciente_id, dosis_id, tipo], out_count=2)
    except Exception:
        pass


def alertas_dosis_de_pacientes(paciente_ids: list[int]) -> list[dict]:
    if not paciente_ids:
        return []
    return db.query(
        'SELECT * FROM vw_alertas_dosis WHERE paciente_id = ANY(%s) '
        'ORDER BY alerta_dosis_pac_timestamp DESC',
        (paciente_ids,)
    )


def recalcular_alertas_dosis(paciente_ids: list[int] | None = None) -> None:
    from utils.helpers import (enrich_history,
                               STATUS_APLICABLE, STATUS_ATRASADA,
                               STATUS_CERCA_LIMITE, STATUS_FALTANTE)
    _ALERTABLE = {STATUS_APLICABLE, STATUS_ATRASADA, STATUS_CERCA_LIMITE, STATUS_FALTANTE}
    _TIPO = {
        STATUS_APLICABLE:    'APLICABLE',
        STATUS_ATRASADA:     'ATRASADA',
        STATUS_CERCA_LIMITE: 'CERCA_LIMITE',
        STATUS_FALTANTE:     'FALTANTE',
    }
    try:
        if paciente_ids is None:
            pacientes = listar_pacientes()
        else:
            pacientes = [obtener_paciente(pid) for pid in paciente_ids]
            pacientes = [p for p in pacientes if p]

        if not pacientes:
            return

        ids = [p['paciente_id'] for p in pacientes]
        db.execute('DELETE FROM alertas_dosis_pacientes WHERE paciente_id = ANY(%s)', (ids,))

        for pac in pacientes:
            pid        = pac['paciente_id']
            esquema_id = pac.get('esquema_id')
            birth_date = pac.get('paciente_fecha_nac')
            if not esquema_id or not birth_date:
                continue
            rows     = historial_vacunacion_paciente(pid, esquema_id)
            enriched = enrich_history(rows, birth_date)
            for row in enriched:
                status   = row.get('status')
                dosis_id = row.get('dosis_id')
                if status not in _ALERTABLE or not dosis_id:
                    continue
                try:
                    db.execute(
                        "INSERT INTO alertas_dosis_pacientes"
                        "(paciente_id, dosis_id, alerta_dosis_pac_tipo) "
                        "VALUES (%s, %s, %s::tipo_alerta_dosis)",
                        (pid, dosis_id, _TIPO[status])
                    )
                except Exception:
                    pass
    except Exception:
        pass


# ─────────────────────────────────────────────
# DASHBOARD STATS
# ─────────────────────────────────────────────

def stats_dashboard() -> dict:
    return db.call_read_sp_one('sp_stats_dashboard') or {}


# ─────────────────────────────────────────────
# GRÁFICAS Y REPORTES
# ─────────────────────────────────────────────

def chart_aplicaciones_por_mes(meses: int = 12) -> list[dict]:
    return db.call_read_sp('sp_chart_aplicaciones_por_mes', [meses])


def chart_por_mes(desde: str, hasta: str,
                  centro_id: int | None = None,
                  vacuna_id: int | None = None) -> list[dict]:
    return db.call_read_sp('sp_chart_por_mes', [desde, hasta, centro_id, vacuna_id])


def chart_top_vacunas(desde: str, hasta: str,
                      centro_id: int | None = None,
                      vacuna_id: int | None = None) -> list[dict]:
    return db.call_read_sp('sp_chart_top_vacunas', [desde, hasta, centro_id, vacuna_id])


def resumen_periodo(desde: str, hasta: str,
                    centro_id: int | None = None,
                    vacuna_id: int | None = None) -> dict:
    row = db.call_read_sp_one('sp_resumen_periodo', [desde, hasta, centro_id, vacuna_id])
    return {'total': int(row['total']) if row else 0}


def ranking_centros_actividad(meses: int = 6) -> list[dict]:
    return db.call_read_sp('sp_ranking_centros_actividad', [meses])


def reporte_cobertura_vacunal(esquema_id: int) -> list[dict]:
    return db.call_read_sp('sp_reporte_cobertura_vacunal', [esquema_id])


def pacientes_dosis_urgentes(centro_id: int | None = None) -> list[dict]:
    return db.call_read_sp('sp_pacientes_dosis_urgentes', [centro_id])


# ── Fotos de perfil ──────────────────────────────────────────────

def actualizar_imagen_usuario(usuario_id: int, ruta: str) -> None:
    _sp('sp_actualizar_imagen_usuario', [usuario_id, ruta], out_count=2)


def actualizar_imagen_paciente(paciente_id: int, ruta: str) -> None:
    _sp('sp_actualizar_imagen_paciente', [paciente_id, ruta], out_count=2)


# ─────────────────────────────────────────────
# KPIs
# ─────────────────────────────────────────────

def kpis_generales() -> dict:
    row = db.call_read_sp_one('sp_kpis_generales')
    if not row:
        return {}
    int_keys = [
        'total_pacientes', 'total_tutores', 'total_responsables',
        'total_centros', 'centros_activos_30d', 'total_aplicaciones',
        'aplicaciones_hoy', 'aplicaciones_mes', 'pacientes_sin_aplicaciones',
        'total_vacunas', 'total_esquemas', 'total_padecimientos',
        'lotes_activos', 'lotes_por_caducar_30d', 'lotes_caducados_con_stock',
        'total_alertas_inv', 'total_alertas_dosis',
    ]
    for k in int_keys:
        if row.get(k) is not None:
            row[k] = int(row[k])
    for k in ('pct_cobertura_global', 'promedio_diario_mes', 'pct_centros_activos_30d'):
        if row.get(k) is not None:
            row[k] = float(row[k])
    return row


# ─────────────────────────────────────────────
# DASHBOARD RESPONSABLE
# ─────────────────────────────────────────────

def dashboard_responsable_stats(usuario_id: int, centro_id: int) -> dict:
    rows = db.call_read_sp('sp_dashboard_responsable_stats', [usuario_id, centro_id])
    if not rows:
        return {'aplicaciones_hoy': 0, 'pacientes_hoy': 0, 'pendientes_confirmacion': 0}
    row = rows[0]
    for k in ('aplicaciones_hoy', 'pacientes_hoy', 'pendientes_confirmacion'):
        row[k] = int(row.get(k) or 0)
    return row


def inventario_con_alertas_de_centro(centro_id: int) -> list[dict]:
    return db.call_read_sp('sp_inventario_con_alertas_de_centro', [centro_id])


def lotes_proximos_caducar_centro(centro_id: int, dias: int = 30) -> list[dict]:
    rows = db.call_read_sp('sp_lotes_proximos_caducar_centro', [centro_id, dias])
    for r in rows:
        if r.get('lote_fecha_caducidad'):
            r['lote_fecha_caducidad'] = str(r['lote_fecha_caducidad'])
        if r.get('dias_restantes') is not None:
            r['dias_restantes'] = int(r['dias_restantes'])
    return rows

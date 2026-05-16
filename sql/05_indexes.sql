-- ═════════════════════════════════════════════════════════════════════════════
-- VacunaTrack — Índices de rendimiento
-- ─────────────────────────────────────────────────────────────────────────────
-- Contenido:
--   • Índices existentes extraídos de vacunatrack_diaitc.sql, convertidos a la
--     sintaxis CREATE INDEX IF NOT EXISTS para poder reaplicar este archivo
--     de forma idempotente sobre una base ya poblada.
--   • Índices estratégicos nuevos (marcados con -- nuevo (índice estratégico))
--     agregados para cubrir patrones de consulta frecuentes: búsquedas por
--     CURP / cert. nac. / NFC, filtros por correo, joins sobre vacuna_id /
--     esquema_id, y columnas de auditoría en tablas de eventos.
--
-- Orden de aplicación: después de 01_schema.sql y antes de cualquier carga
-- de datos (los índices se construyen sobre filas existentes al crearlos, pero
-- mantenerlos vacíos durante el INSERT masivo es más rápido).
-- ═════════════════════════════════════════════════════════════════════════════


-- ═══════════════════════════════════════════════════════════════════════════
-- ═══ APLICACIONES ═══
-- ═══════════════════════════════════════════════════════════════════════════

CREATE INDEX IF NOT EXISTS idx_aplicaciones_paciente
    ON aplicaciones(paciente_id);

CREATE INDEX IF NOT EXISTS idx_aplicaciones_usuario
    ON aplicaciones(usuario_id, aplicacion_timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_aplicaciones_timestamp
    ON aplicaciones(aplicacion_timestamp);

CREATE INDEX IF NOT EXISTS idx_aplicaciones_centro
    ON aplicaciones(centro_id);

CREATE INDEX IF NOT EXISTS idx_aplicaciones_lote
    ON aplicaciones(lote_id);

CREATE INDEX IF NOT EXISTS idx_aplicaciones_dosis  -- nuevo (índice estratégico)
    ON aplicaciones(dosis_id);


-- ═══════════════════════════════════════════════════════════════════════════
-- ═══ ALERTAS ═══
-- ═══════════════════════════════════════════════════════════════════════════

CREATE INDEX IF NOT EXISTS idx_alertas_dosis_pac_paciente
    ON alertas_dosis_pacientes(paciente_id);

CREATE INDEX IF NOT EXISTS idx_alertas_dosis_pac_tipo  -- nuevo (índice estratégico)
    ON alertas_dosis_pacientes(alerta_dosis_pac_tipo);

CREATE INDEX IF NOT EXISTS idx_alertas_inv_inventario
    ON alertas_inventario(inventario_id, alerta_inv_timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_alertas_inv_tipo  -- nuevo (índice estratégico)
    ON alertas_inventario(alerta_inv_tipo);


-- ═══════════════════════════════════════════════════════════════════════════
-- ═══ INVENTARIO Y LOTES ═══
-- ═══════════════════════════════════════════════════════════════════════════

CREATE INDEX IF NOT EXISTS idx_inventarios_centro
    ON inventarios(centro_id, inventario_activo_desde);

CREATE INDEX IF NOT EXISTS idx_inventarios_lote
    ON inventarios(lote_id);

CREATE INDEX IF NOT EXISTS idx_inventarios_origen
    ON inventarios(inventario_origen_id);

CREATE INDEX IF NOT EXISTS idx_lote_codigo
    ON lotes(lote_codigo);

CREATE INDEX IF NOT EXISTS idx_lotes_proveedor
    ON lotes(proveedor_id);

CREATE INDEX IF NOT EXISTS idx_transf_origen
    ON transferencias_inventario(inv_origen_id);

CREATE INDEX IF NOT EXISTS idx_transf_destino
    ON transferencias_inventario(inv_destino_id);


-- ═══════════════════════════════════════════════════════════════════════════
-- ═══ PACIENTES ═══
-- ═══════════════════════════════════════════════════════════════════════════

CREATE INDEX IF NOT EXISTS idx_pacientes_tutores_tutor
    ON pacientes_tutores(tutor_id);

CREATE INDEX IF NOT EXISTS idx_pacientes_tutores_paciente
    ON pacientes_tutores(paciente_id);

CREATE INDEX IF NOT EXISTS idx_esq_pac_paciente
    ON esquemas_pacientes(paciente_id);

CREATE INDEX IF NOT EXISTS idx_esq_pac_vigencia
    ON esquemas_pacientes(paciente_id, esq_pac_desde DESC);

-- Índice parcial: solo indexa filas donde el campo tiene valor (la columna
-- admite NULL y es única, por lo que un índice parcial es más compacto).
CREATE INDEX IF NOT EXISTS idx_pacientes_curp  -- nuevo (índice estratégico)
    ON pacientes(paciente_curp)
    WHERE paciente_curp IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_pacientes_cert_nac  -- nuevo (índice estratégico)
    ON pacientes(paciente_num_cert_nac)
    WHERE paciente_num_cert_nac IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_pacientes_nfc  -- nuevo (índice estratégico)
    ON pacientes(paciente_nfc)
    WHERE paciente_nfc IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_pacientes_esquema  -- nuevo (índice estratégico)
    ON pacientes(esquema_id);

CREATE INDEX IF NOT EXISTS idx_pacientes_fecha_nac  -- nuevo (índice estratégico)
    ON pacientes(paciente_fecha_nac);


-- ═══════════════════════════════════════════════════════════════════════════
-- ═══ USUARIOS Y LOGIN ═══
-- ═══════════════════════════════════════════════════════════════════════════

CREATE INDEX IF NOT EXISTS idx_login_usuario
    ON login(usuario_id);

CREATE INDEX IF NOT EXISTS idx_usuarios_roles_usuario
    ON usuarios_roles(usuario_id);

CREATE INDEX IF NOT EXISTS idx_usuarios_roles_rol
    ON usuarios_roles(rol_id);

CREATE INDEX IF NOT EXISTS idx_login_correo  -- nuevo (índice estratégico)
    ON login(login_correo);


-- ═══════════════════════════════════════════════════════════════════════════
-- ═══ DOSIS Y ESQUEMAS ═══
-- ═══════════════════════════════════════════════════════════════════════════

CREATE INDEX IF NOT EXISTS idx_dosis_vacuna  -- nuevo (índice estratégico)
    ON dosis(vacuna_id);

CREATE INDEX IF NOT EXISTS idx_dosis_esquemas_esquema  -- nuevo (índice estratégico)
    ON dosis_esquemas(esquema_id);


-- ═══════════════════════════════════════════════════════════════════════════
-- ═══ EVENTOS Y GEOGRAFÍA ═══
-- ═══════════════════════════════════════════════════════════════════════════

CREATE INDEX IF NOT EXISTS idx_eventos_gps_timestamp
    ON eventos_gps(evento_timestamp);

CREATE INDEX IF NOT EXISTS idx_lecturas_beacon_centro
    ON lecturas_beacon(centro_id, lectura_timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_eventos_gps_tutor  -- nuevo (índice estratégico)
    ON eventos_gps(tutor_id);

CREATE INDEX IF NOT EXISTS idx_lecturas_beacon_tutor  -- nuevo (índice estratégico)
    ON lecturas_beacon(tutor_id);

CREATE INDEX IF NOT EXISTS idx_proveedores_fabricante
    ON proveedores(fabricante_id);

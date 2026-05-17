-- ═══════════════════════════════════════════════════════════════════════════════
-- VacunaTrack — Vistas del sistema
-- Archivo:  sql/03_views.sql
-- Fuentes:  vacunatrack_diaitc.sql  (definiciones originales)
--           patch_postgres.sql      (anula y extiende definiciones originales)
--           patch_caducidad.sql     (anula vw_centros_stock_vacuna)
-- Regla:    cuando una vista aparece en un parche, se usa ÚNICAMENTE la versión
--           del parche (la más reciente). No se incluyen duplicados.
-- ═══════════════════════════════════════════════════════════════════════════════


-- ═══ AUTENTICACIÓN Y USUARIOS ═══

-- Fuente: patch_postgres.sql (anula vacunatrack_diaitc.sql)
-- Cambios: agrega INITCAP en first_name/last_name; expone usuario_activo;
--          elimina el filtro WHERE usuario_activo = true (lo delega a la app).
CREATE OR REPLACE VIEW vw_usuarios_auth AS
SELECT u.usuario_id,
       l.login_correo                  AS email,
       l.login_contrasena              AS password,
       INITCAP(u.usuario_prim_nombre)::VARCHAR(100)  AS first_name,
       INITCAP(u.usuario_apellido_pat)::VARCHAR(100) AS last_name,
       r.rol_nombre                    AS role,
       u.usuario_activo                AS activo
FROM login          l
JOIN usuarios       u  ON u.usuario_id  = l.usuario_id
JOIN usuarios_roles ur ON ur.usuario_id = u.usuario_id
JOIN roles          r  ON r.rol_id      = ur.rol_id;


-- Fuente: patch_postgres.sql (anula vacunatrack_diaitc.sql)
-- Cambios: aplica INITCAP a todos los campos de nombre.
CREATE OR REPLACE VIEW vw_administradores AS
SELECT u.usuario_id                        AS admin_id,
       INITCAP(u.usuario_prim_nombre)::VARCHAR(100)      AS admin_prim_nombre,
       INITCAP(u.usuario_seg_nombre)::VARCHAR(100)       AS admin_seg_nombre,
       INITCAP(u.usuario_apellido_pat)::VARCHAR(100)     AS admin_apellido_pat,
       INITCAP(u.usuario_apellido_mat)::VARCHAR(100)     AS admin_apellido_mat,
       u.usuario_telefono                  AS admin_telefono,
       u.usuario_curp                      AS admin_curp,
       u.usuario_rfc                       AS admin_rfc,
       u.usuario_activo                    AS admin_activo,
       u.usuario_imagen                    AS admin_imagen,
       l.login_correo                      AS admin_email
FROM usuarios       u
JOIN usuarios_roles ur ON ur.usuario_id = u.usuario_id
JOIN roles          r  ON r.rol_id      = ur.rol_id AND r.rol_nombre = 'admin'
JOIN login          l  ON l.usuario_id  = u.usuario_id;


-- Fuente: patch_postgres.sql (anula vacunatrack_diaitc.sql)
-- Cambios: aplica INITCAP a todos los campos de nombre.
CREATE OR REPLACE VIEW vw_tutores AS
SELECT u.usuario_id                        AS tutor_id,
       INITCAP(u.usuario_prim_nombre)::VARCHAR(100)      AS tutor_prim_nombre,
       INITCAP(u.usuario_seg_nombre)::VARCHAR(100)       AS tutor_seg_nombre,
       INITCAP(u.usuario_apellido_pat)::VARCHAR(100)     AS tutor_apellido_pat,
       INITCAP(u.usuario_apellido_mat)::VARCHAR(100)     AS tutor_apellido_mat,
       u.usuario_telefono                  AS tutor_telefono,
       u.usuario_curp                      AS tutor_curp,
       u.usuario_activo                    AS tutor_activo,
       u.usuario_imagen                    AS tutor_imagen,
       l.login_correo                      AS tutor_email
FROM usuarios       u
JOIN usuarios_roles ur ON ur.usuario_id = u.usuario_id
JOIN roles          r  ON r.rol_id      = ur.rol_id AND r.rol_nombre = 'tutor'
JOIN login          l  ON l.usuario_id  = u.usuario_id;


-- Fuente: patch_postgres.sql (anula vacunatrack_diaitc.sql)
-- Cambios: aplica INITCAP a todos los campos de nombre.
CREATE OR REPLACE VIEW vw_responsables AS
SELECT u.usuario_id                        AS responsable_id,
       INITCAP(u.usuario_prim_nombre)::VARCHAR(100)      AS responsable_prim_nombre,
       INITCAP(u.usuario_seg_nombre)::VARCHAR(100)       AS responsable_seg_nombre,
       INITCAP(u.usuario_apellido_pat)::VARCHAR(100)     AS responsable_apellido_pat,
       INITCAP(u.usuario_apellido_mat)::VARCHAR(100)     AS responsable_apellido_mat,
       u.usuario_telefono                  AS responsable_telefono,
       u.usuario_curp                      AS responsable_curp,
       u.usuario_rfc                       AS responsable_rfc,
       u.usuario_activo                    AS responsable_activo,
       u.usuario_imagen                    AS responsable_imagen,
       u.centro_id,
       cs.centro_nombre,
       l.login_correo                      AS responsable_email
FROM usuarios       u
JOIN usuarios_roles ur ON ur.usuario_id = u.usuario_id
JOIN roles          r  ON r.rol_id      = ur.rol_id AND r.rol_nombre = 'responsable'
JOIN login          l  ON l.usuario_id  = u.usuario_id
LEFT JOIN centros_salud cs ON cs.centro_id = u.centro_id;


-- Fuente: patch_postgres.sql (anula vacunatrack_diaitc.sql)
-- Cambios: agrega cast ::VARCHAR(100) en la concatenación de responsable_nombre.
CREATE OR REPLACE VIEW vw_cedulas AS
SELECT c.*,
    INITCAP(u.usuario_prim_nombre) || ' ' || INITCAP(u.usuario_apellido_pat)::VARCHAR(100) AS responsable_nombre,
    u.usuario_telefono  AS responsable_telefono,
    cs.centro_nombre
FROM cedulas   c
JOIN usuarios  u  ON u.usuario_id  = c.usuario_id
LEFT JOIN centros_salud cs ON cs.centro_id = u.centro_id;


-- Fuente: patch_postgres.sql (anula vacunatrack_diaitc.sql)
-- Cambios: expande p.* en columnas explícitas con INITCAP en campos de nombre.
CREATE OR REPLACE VIEW vw_usuarios_completo AS
SELECT
    u.usuario_id,
    INITCAP(u.usuario_prim_nombre)::VARCHAR(100)  AS usuario_prim_nombre,
    INITCAP(u.usuario_seg_nombre)::VARCHAR(100)   AS usuario_seg_nombre,
    INITCAP(u.usuario_apellido_pat)::VARCHAR(100) AS usuario_apellido_pat,
    INITCAP(u.usuario_apellido_mat)::VARCHAR(100) AS usuario_apellido_mat,
    u.usuario_telefono,
    u.usuario_curp,
    u.usuario_rfc,
    u.usuario_activo,
    u.usuario_imagen,
    u.centro_id,
    cs.centro_nombre,
    l.login_correo AS email,
    STRING_AGG(r.rol_nombre, ',' ORDER BY
        CASE r.rol_nombre
            WHEN 'admin'       THEN 0
            WHEN 'responsable' THEN 1
            ELSE 2
        END
    ) AS roles
FROM usuarios u
JOIN login          l  ON l.usuario_id  = u.usuario_id
JOIN usuarios_roles ur ON ur.usuario_id = u.usuario_id
JOIN roles          r  ON r.rol_id      = ur.rol_id
LEFT JOIN centros_salud cs ON cs.centro_id = u.centro_id
GROUP BY u.usuario_id, u.usuario_prim_nombre, u.usuario_seg_nombre,
         u.usuario_apellido_pat, u.usuario_apellido_mat,
         u.usuario_telefono, u.usuario_curp, u.usuario_rfc,
         u.usuario_activo, u.usuario_imagen, u.centro_id,
         cs.centro_nombre, l.login_correo;


-- ═══ PACIENTES Y RELACIONES ═══

-- Fuente: patch_postgres.sql (anula vacunatrack_diaitc.sql)
-- Cambios: expande p.* en columnas explícitas con INITCAP en campos de nombre.
CREATE OR REPLACE VIEW vw_pacientes AS
SELECT p.paciente_id,
       INITCAP(p.paciente_prim_nombre)::VARCHAR(100)  AS paciente_prim_nombre,
       INITCAP(p.paciente_seg_nombre)::VARCHAR(100)   AS paciente_seg_nombre,
       INITCAP(p.paciente_apellido_pat)::VARCHAR(100) AS paciente_apellido_pat,
       INITCAP(p.paciente_apellido_mat)::VARCHAR(100) AS paciente_apellido_mat,
       p.paciente_num_cert_nac,
       p.paciente_curp,
       p.paciente_fecha_nac,
       p.paciente_sexo,
       p.paciente_nfc,
       p.paciente_imagen,
       p.esquema_id,
       e.esquema_nombre
FROM pacientes p
JOIN esquemas e ON e.esquema_id = p.esquema_id;


-- Fuente: vacunatrack_diaitc.sql (no existe versión en parche)
CREATE OR REPLACE VIEW vw_relaciones AS
SELECT pt.*,
    INITCAP(p.paciente_prim_nombre) || ' ' || INITCAP(p.paciente_apellido_pat) AS paciente,
    INITCAP(u.usuario_prim_nombre)  || ' ' || INITCAP(u.usuario_apellido_pat)  AS tutor
FROM pacientes_tutores pt
JOIN pacientes p ON p.paciente_id = pt.paciente_id
JOIN usuarios  u ON u.usuario_id  = pt.tutor_id;


-- Fuente: patch_postgres.sql — versión final (anula vacunatrack_diaitc.sql y
--         versión anterior del mismo parche en línea 67)
-- Cambios: expande p.* en columnas explícitas con INITCAP en campos de nombre.
CREATE OR REPLACE VIEW vw_pacientes_por_tutor AS
SELECT p.paciente_id,
       INITCAP(p.paciente_prim_nombre)::VARCHAR(100)  AS paciente_prim_nombre,
       INITCAP(p.paciente_seg_nombre)::VARCHAR(100)   AS paciente_seg_nombre,
       INITCAP(p.paciente_apellido_pat)::VARCHAR(100) AS paciente_apellido_pat,
       INITCAP(p.paciente_apellido_mat)::VARCHAR(100) AS paciente_apellido_mat,
       p.paciente_curp,
       p.paciente_num_cert_nac,
       p.paciente_fecha_nac,
       p.paciente_sexo,
       p.paciente_nfc,
       p.paciente_imagen,
       p.esquema_id,
       e.esquema_nombre,
       pt.tutor_id,
       pt.pac_tut_id,
       INITCAP(u.usuario_prim_nombre) || ' ' || INITCAP(u.usuario_apellido_pat)::VARCHAR(100) AS tutor_nombre,
       u.usuario_telefono  AS tutor_telefono,
       l.login_correo      AS tutor_email
FROM pacientes          p
JOIN esquemas           e  ON e.esquema_id  = p.esquema_id
JOIN pacientes_tutores  pt ON pt.paciente_id = p.paciente_id
JOIN usuarios           u  ON u.usuario_id  = pt.tutor_id
JOIN login              l  ON l.usuario_id  = u.usuario_id;


-- ═══ APLICACIONES ═══

-- Fuente: vacunatrack_diaitc.sql (no existe versión en parche)
CREATE OR REPLACE VIEW vw_aplicaciones AS
SELECT a.*,
    INITCAP(p.paciente_prim_nombre) || ' ' || INITCAP(p.paciente_apellido_pat) AS paciente,
    INITCAP(u.usuario_prim_nombre)  || ' ' || INITCAP(u.usuario_apellido_pat)  AS responsable,
    cs.centro_nombre,
    d.vacuna_id,
    v.vacuna_nombre,
    d.dosis_tipo,
    l.lote_codigo
FROM aplicaciones  a
JOIN pacientes     p  ON p.paciente_id = a.paciente_id
JOIN usuarios      u  ON u.usuario_id  = a.usuario_id
JOIN centros_salud cs ON cs.centro_id  = a.centro_id
JOIN dosis         d  ON d.dosis_id    = a.dosis_id
JOIN vacunas       v  ON v.vacuna_id   = d.vacuna_id
JOIN lotes         l  ON l.lote_id     = a.lote_id;


-- Fuente: patch_postgres.sql (anula vacunatrack_diaitc.sql)
-- Cambios: agrega cast ::VARCHAR(100) en la concatenación del responsable.
CREATE OR REPLACE VIEW vw_aplicaciones_responsable AS
SELECT a.aplicacion_id,
       a.paciente_id,
       a.dosis_id,
       a.aplicacion_timestamp,
       a.aplicacion_observaciones,
       INITCAP(u.usuario_prim_nombre) || ' ' || INITCAP(u.usuario_apellido_pat)::VARCHAR(100) AS responsable,
       cs.centro_nombre
FROM aplicaciones  a
JOIN usuarios      u  ON u.usuario_id = a.usuario_id
JOIN centros_salud cs ON cs.centro_id = a.centro_id;


-- Fuente: patch_postgres.sql (anula vacunatrack_diaitc.sql)
-- Cambios: agrega cast ::VARCHAR(100) en la concatenación del responsable.
CREATE OR REPLACE VIEW vw_historial_vacunacion AS
SELECT
    vde.dosis_id,
    vde.vacuna_id,
    vde.vacuna_nombre,
    vde.dosis_tipo,
    vde.dosis_cant_ml,
    vde.dosis_area_aplicacion,
    vde.dosis_edad_oportuna_dias,
    vde.dosis_intervalo_min_dias,
    vde.dosis_limite_edad_dias,
    vde.dosis_vigente_desde,
    vde.dosis_vigente_hasta,
    vde.esquema_id,
    vde.dosis_esq_id,
    a.paciente_id,
    a.aplicacion_id,
    a.aplicacion_timestamp,
    a.aplicacion_observaciones,
    INITCAP(u.usuario_prim_nombre) || ' ' || INITCAP(u.usuario_apellido_pat)::VARCHAR(100) AS responsable,
    cs.centro_nombre
FROM vw_dosis_esquemas_detalle vde
LEFT JOIN aplicaciones   a  ON a.dosis_id    = vde.dosis_id
LEFT JOIN usuarios       u  ON u.usuario_id  = a.usuario_id
LEFT JOIN centros_salud  cs ON cs.centro_id  = a.centro_id;


-- ═══ INVENTARIO Y LOTES ═══

-- Fuente: vacunatrack_diaitc.sql (no existe versión en parche)
CREATE OR REPLACE VIEW vw_inventarios AS
SELECT i.inventario_id,
       i.centro_id,
       i.lote_id,
       i.inventario_stock_inicial,
       i.inventario_stock_actual,
       i.inventario_activo_desde,
       (i.inventario_activo_desde IS NOT NULL) AS inventario_activo,
       cs.centro_nombre,
       l.lote_codigo,
       l.lote_fecha_fabricacion,
       l.lote_fecha_caducidad,
       l.vacuna_id,
       v.vacuna_nombre,
       f.fabricante_nombre
FROM inventarios   i
JOIN centros_salud cs ON cs.centro_id    = i.centro_id
JOIN lotes         l  ON l.lote_id       = i.lote_id
JOIN vacunas       v  ON v.vacuna_id     = l.vacuna_id
JOIN fabricantes   f  ON f.fabricante_id = l.fabricante_id;


-- Fuente: patch_caducidad.sql (anula vacunatrack_diaitc.sql)
-- Cambios: agrega filtro AND (l.lote_fecha_caducidad IS NULL OR l.lote_fecha_caducidad > CURRENT_DATE)
--          para excluir lotes caducados del cómputo de stock.
CREATE OR REPLACE VIEW vw_centros_stock_vacuna AS
SELECT cs.centro_id,
       cs.centro_nombre,
       cs.centro_calle,
       cs.centro_numero,
       cs.centro_codigo_postal,
       cs.ciudad_id,
       cs.centro_horario_inicio,
       cs.centro_horario_fin,
       cs.centro_latitud,
       cs.centro_longitud,
       cs.centro_telefono,
       cs.centro_beacon,
       ci.ciudad_nombre,
       l.vacuna_id,
       SUM(i.inventario_stock_actual) AS stock_total
FROM centros_salud cs
JOIN inventarios i  ON i.centro_id  = cs.centro_id
JOIN lotes       l  ON l.lote_id    = i.lote_id
JOIN ciudades    ci ON ci.ciudad_id  = cs.ciudad_id
WHERE i.inventario_activo_desde IS NOT NULL
  AND i.inventario_stock_actual > 0
  AND (l.lote_fecha_caducidad IS NULL OR l.lote_fecha_caducidad > CURRENT_DATE)
GROUP BY cs.centro_id, ci.ciudad_nombre, l.vacuna_id;


-- Fuente: vacunatrack_diaitc.sql (no existe versión en parche)
CREATE OR REPLACE VIEW vw_lotes AS
SELECT l.*,
    v.vacuna_nombre,
    f.fabricante_nombre,
    p.proveedor_prim_nombre || ' ' || p.proveedor_apellido_pat AS proveedor_nombre
FROM lotes       l
JOIN vacunas     v ON v.vacuna_id     = l.vacuna_id
JOIN fabricantes f ON f.fabricante_id = l.fabricante_id
JOIN proveedores p ON p.proveedor_id  = l.proveedor_id;


-- Fuente: vacunatrack_diaitc.sql (no existe versión en parche)
CREATE OR REPLACE VIEW vw_proveedores AS
SELECT p.*, f.fabricante_nombre
FROM proveedores p
JOIN fabricantes f ON f.fabricante_id = p.fabricante_id;


-- ═══ VACUNAS Y DOSIS ═══

-- Fuente: vacunatrack_diaitc.sql (no existe versión en parche)
CREATE OR REPLACE VIEW vw_dosis AS
SELECT d.*, v.vacuna_nombre
FROM dosis   d
JOIN vacunas v ON v.vacuna_id = d.vacuna_id;


-- Fuente: vacunatrack_diaitc.sql (no existe versión en parche)
-- Nota: vw_dosis_esquemas_detalle debe crearse antes que vw_historial_vacunacion.
CREATE OR REPLACE VIEW vw_dosis_esquemas_detalle AS
SELECT d.dosis_id,
       d.vacuna_id,
       d.dosis_tipo,
       d.dosis_cant_ml,
       d.dosis_area_aplicacion,
       d.dosis_edad_oportuna_dias,
       d.dosis_intervalo_min_dias,
       d.dosis_limite_edad_dias,
       d.dosis_vigente_desde,
       d.dosis_vigente_hasta,
       v.vacuna_nombre,
       de.esquema_id,
       de.dosis_esq_id
FROM dosis         d
JOIN dosis_esquemas de ON de.dosis_id = d.dosis_id
JOIN vacunas        v  ON v.vacuna_id = d.vacuna_id;


-- Fuente: patch_postgres.sql (anula vacunatrack_diaitc.sql)
-- Cambios: ninguno de fondo; la versión del parche es idéntica en lógica.
CREATE OR REPLACE VIEW vw_dosis_esquemas AS
SELECT de.*,
    d.dosis_tipo,
    d.dosis_cant_ml,
    d.dosis_area_aplicacion,
    d.dosis_edad_oportuna_dias,
    d.dosis_intervalo_min_dias,
    d.dosis_limite_edad_dias,
    d.vacuna_id,
    v.vacuna_nombre,
    e.esquema_nombre
FROM dosis_esquemas de
JOIN dosis    d  ON d.dosis_id   = de.dosis_id
JOIN vacunas  v  ON v.vacuna_id  = d.vacuna_id
JOIN esquemas e  ON e.esquema_id = de.esquema_id;


-- Fuente: patch_postgres.sql (anula vacunatrack_diaitc.sql)
-- Cambios: ninguno de fondo; la versión del parche es idéntica en lógica.
CREATE OR REPLACE VIEW vw_vacunas AS
SELECT v.*,
    COUNT(DISTINCT vp.padecimiento_id)                                          AS total_padecimientos,
    COALESCE(STRING_AGG(DISTINCT p.padecimiento_nombre, ', '), '—') AS padecimientos,
    COUNT(DISTINCT a.aplicacion_id)                                             AS total_aplicaciones
FROM vacunas v
LEFT JOIN vacunas_padecimientos vp ON vp.vacuna_id       = v.vacuna_id
LEFT JOIN padecimientos         p  ON p.padecimiento_id  = vp.padecimiento_id
LEFT JOIN dosis                 d  ON d.vacuna_id         = v.vacuna_id
LEFT JOIN aplicaciones          a  ON a.dosis_id          = d.dosis_id
GROUP BY v.vacuna_id;


-- Fuente: patch_postgres.sql (anula vacunatrack_diaitc.sql)
-- Cambios: ninguno de fondo; la versión del parche es idéntica en lógica.
CREATE OR REPLACE VIEW vw_esquemas AS
SELECT e.*,
    COUNT(DISTINCT de.dosis_id)                                        AS total_dosis,
    COUNT(DISTINCT d.vacuna_id)                                        AS total_vacunas,
    COUNT(DISTINCT a.paciente_id)                                      AS total_pacientes
FROM esquemas e
LEFT JOIN dosis_esquemas de ON de.esquema_id  = e.esquema_id
LEFT JOIN dosis          d  ON d.dosis_id     = de.dosis_id
LEFT JOIN pacientes      pa ON pa.esquema_id  = e.esquema_id
LEFT JOIN aplicaciones   a  ON a.dosis_id     = de.dosis_id
GROUP BY e.esquema_id;


-- Fuente: vacunatrack_diaitc.sql (no existe versión en parche)
CREATE OR REPLACE VIEW vw_padecimientos AS
SELECT p.*,
    STRING_AGG(v.vacuna_nombre, ', ' ORDER BY v.vacuna_nombre) AS vacunas
FROM padecimientos p
LEFT JOIN vacunas_padecimientos vp ON vp.padecimiento_id = p.padecimiento_id
LEFT JOIN vacunas v ON v.vacuna_id = vp.vacuna_id
GROUP BY p.padecimiento_id;


-- Fuente: vacunatrack_diaitc.sql (no existe versión en parche)
CREATE OR REPLACE VIEW vw_fabricantes AS
SELECT f.*, p.pais_nombre
FROM fabricantes f
JOIN paises p ON p.pais_id = f.pais_id;


-- ═══ GEOGRAFÍA Y CENTROS ═══

-- Fuente: vacunatrack_diaitc.sql (no existe versión en parche)
CREATE OR REPLACE VIEW vw_centros AS
SELECT cs.*, ci.ciudad_nombre
FROM centros_salud cs
JOIN ciudades ci ON ci.ciudad_id = cs.ciudad_id;


-- Fuente: patch_postgres.sql (anula vacunatrack_diaitc.sql)
-- Cambios: ninguno de fondo; la versión del parche es idéntica en lógica.
CREATE OR REPLACE VIEW vw_centros_detalle AS
SELECT
    cs.*,
    ci.ciudad_nombre,
    e.estado_id,
    e.estado_nombre,
    pa.pais_id,
    pa.pais_nombre,
    COUNT(DISTINCT i.inventario_id)  AS total_inventarios,
    COUNT(DISTINCT a.aplicacion_id)  AS total_aplicaciones
FROM centros_salud cs
JOIN ciudades   ci ON ci.ciudad_id = cs.ciudad_id
JOIN estados    e  ON e.estado_id  = ci.estado_id
JOIN paises     pa ON pa.pais_id   = e.pais_id
LEFT JOIN inventarios   i ON i.centro_id = cs.centro_id
LEFT JOIN aplicaciones  a ON a.centro_id = cs.centro_id
GROUP BY cs.centro_id, ci.ciudad_nombre, e.estado_id, e.estado_nombre, pa.pais_id, pa.pais_nombre;


-- Fuente: patch_postgres.sql (anula vacunatrack_diaitc.sql)
-- Cambios: ninguno de fondo; la versión del parche es idéntica en lógica.
CREATE OR REPLACE VIEW vw_paises AS
SELECT p.*,
    COUNT(DISTINCT e.estado_id)  AS total_estados,
    COUNT(DISTINCT c.ciudad_id)  AS total_ciudades
FROM paises   p
LEFT JOIN estados   e ON e.pais_id   = p.pais_id
LEFT JOIN ciudades  c ON c.estado_id = e.estado_id
GROUP BY p.pais_id;


-- Fuente: vacunatrack_diaitc.sql (no existe versión en parche)
CREATE OR REPLACE VIEW vw_estados AS
SELECT e.*, p.pais_nombre
FROM estados e
JOIN paises p ON p.pais_id = e.pais_id;


-- Fuente: vacunatrack_diaitc.sql (no existe versión en parche)
CREATE OR REPLACE VIEW vw_ciudades AS
SELECT c.*, e.estado_nombre
FROM ciudades c
JOIN estados e ON e.estado_id = c.estado_id;


-- ═══ ALERTAS ═══

-- Fuente: vacunatrack_diaitc.sql (no existe versión en parche)
CREATE OR REPLACE VIEW vw_alertas_inventario AS
SELECT ai.*,
    i.inventario_stock_actual,
    cs.centro_nombre,
    v.vacuna_nombre,
    ai.alerta_inv_timestamp AS ts
FROM alertas_inventario ai
JOIN inventarios   i  ON i.inventario_id = ai.inventario_id
JOIN centros_salud cs ON cs.centro_id    = i.centro_id
JOIN lotes         l  ON l.lote_id       = i.lote_id
JOIN vacunas       v  ON v.vacuna_id     = l.vacuna_id;


-- Fuente: vacunatrack_diaitc.sql (no existe versión en parche)
CREATE OR REPLACE VIEW vw_alertas_dosis AS
SELECT ad.*,
    INITCAP(p.paciente_prim_nombre) || ' ' || INITCAP(p.paciente_apellido_pat) AS paciente,
    v.vacuna_nombre,
    d.dosis_tipo
FROM alertas_dosis_pacientes ad
JOIN pacientes p ON p.paciente_id = ad.paciente_id
JOIN dosis     d ON d.dosis_id    = ad.dosis_id
JOIN vacunas   v ON v.vacuna_id   = d.vacuna_id;


-- ═══ DASHBOARD Y REPORTES ═══

-- Fuente: patch_postgres.sql (anula vacunatrack_diaitc.sql)
-- Cambios: ninguno de fondo; la versión del parche es idéntica en lógica.
CREATE OR REPLACE VIEW vw_stats_dashboard AS
SELECT
    (SELECT COUNT(*) FROM vw_pacientes)    AS pacientes,
    (SELECT COUNT(*) FROM vw_tutores)      AS tutores,
    (SELECT COUNT(*) FROM vw_responsables) AS responsables,
    (SELECT COUNT(*) FROM vw_centros_detalle) AS centros,
    (SELECT COUNT(*) FROM vw_aplicaciones
     WHERE DATE(aplicacion_timestamp) = CURRENT_DATE) AS aplicaciones_hoy,
    (SELECT COUNT(*) FROM vw_alertas_inventario) AS alertas_inv,
    (SELECT COUNT(*) FROM vw_alertas_dosis)      AS alertas_dosis;


-- Fuente: vacunatrack_diaitc.sql (no existe versión en parche)
CREATE OR REPLACE VIEW vw_transferencias AS
SELECT
    t.transf_id,
    t.transf_timestamp,
    t.inv_origen_id,
    t.inv_destino_id,
    cso.centro_nombre                    AS origen_centro_nombre,
    csd.centro_nombre                    AS destino_centro_nombre,
    lo.lote_codigo,
    v.vacuna_nombre,
    id2.inventario_stock_inicial         AS cantidad_transferida,
    io.inventario_stock_actual           AS origen_stock_restante,
    id2.inventario_activo_desde          AS destino_activo_desde,
    (id2.inventario_activo_desde IS NOT NULL) AS destino_confirmado
FROM transferencias_inventario t
JOIN inventarios     io  ON io.inventario_id  = t.inv_origen_id
JOIN inventarios     id2 ON id2.inventario_id = t.inv_destino_id
JOIN centros_salud   cso ON cso.centro_id     = io.centro_id
JOIN centros_salud   csd ON csd.centro_id     = id2.centro_id
JOIN lotes           lo  ON lo.lote_id        = io.lote_id
JOIN vacunas         v   ON v.vacuna_id       = lo.vacuna_id;


-- Fuente: vacunatrack_diaitc.sql (no existe versión en parche)
CREATE OR REPLACE VIEW vw_conflictos_esquema AS
WITH esquema_activo AS (
    SELECT esquema_id, esquema_nombre
    FROM   esquemas
    WHERE  esquema_vigente_hasta IS NULL
    ORDER  BY esquema_vigente_desde DESC
    LIMIT  1
)
SELECT
    p.paciente_id,
    p.paciente_prim_nombre,
    p.paciente_seg_nombre,
    p.paciente_apellido_pat,
    p.paciente_apellido_mat,
    p.paciente_fecha_nac,
    (CURRENT_DATE - p.paciente_fecha_nac)   AS edad_dias,
    p.esquema_id                             AS esquema_actual_id,
    e_viejo.esquema_nombre                   AS esquema_actual_nombre,
    ea.esquema_id                            AS esquema_nuevo_id,
    ea.esquema_nombre                        AS esquema_nuevo_nombre,
    d.dosis_id                               AS dosis_conflicto_id,
    d.dosis_tipo,
    d.dosis_edad_oportuna_dias,
    d.dosis_limite_edad_dias,
    v.vacuna_nombre
FROM   pacientes      p
JOIN   esquemas       e_viejo ON e_viejo.esquema_id = p.esquema_id
                              AND e_viejo.esquema_vigente_hasta IS NOT NULL
CROSS  JOIN esquema_activo    ea
JOIN   dosis_esquemas de_v    ON de_v.esquema_id    = p.esquema_id
JOIN   dosis          d       ON d.dosis_id         = de_v.dosis_id
JOIN   vacunas        v       ON v.vacuna_id        = d.vacuna_id
WHERE
    NOT EXISTS (
        SELECT 1 FROM dosis_esquemas de_n
        WHERE  de_n.esquema_id = ea.esquema_id
          AND  de_n.dosis_id   = d.dosis_id
    )
    AND NOT EXISTS (
        SELECT 1 FROM aplicaciones a
        WHERE  a.paciente_id = p.paciente_id
          AND  a.dosis_id    = d.dosis_id
    )
    AND (d.dosis_limite_edad_dias IS NULL
         OR (CURRENT_DATE - p.paciente_fecha_nac) < d.dosis_limite_edad_dias)
    AND NOT EXISTS (
        SELECT 1 FROM esquemas_pacientes ep
        WHERE  ep.paciente_id           = p.paciente_id
          AND  ep.esquema_id            = p.esquema_id
          AND  ep.esq_pac_motivo_cambio LIKE 'conflicto_resuelto:%'
    );

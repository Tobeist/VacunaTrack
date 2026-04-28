# VacunaTrack

Sistema digital de control y seguimiento de vacunación infantil.  
Desarrollado por Equipo 6 — UDEM · Ingeniería en Tecnologías Computacionales · 2026.

---

## Requisitos previos

- Python 3.10 o superior
- PostgreSQL 14 o superior
- pip
- Cuenta gratuita en [ngrok.com](https://ngrok.com)

---

## Paso 1 — Subir y descomprimir el proyecto en la VM

Sube el archivo `.zip` a la VM (via `scp`, la consola de GCP o cualquier cliente SFTP) y luego ejecuta:

```bash
unzip vacunatrack.zip
cd vacunatrack_diaitc
```

---

## Paso 2 — Instalar ngrok en la VM

### 2.1 Crear cuenta y obtener el token de autenticación

1. Ir a [ngrok.com](https://ngrok.com) → **Sign up** (registrarse gratis).
2. Una vez dentro del dashboard, ir a **Your Authtoken** (menú izquierdo).
3. Copiar el token que aparece, se verá algo así: `2abc123XYZ_abc456...`

### 2.2 Instalar ngrok

```bash
curl -sSL https://ngrok-agent.s3.amazonaws.com/ngrok.asc \
  | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null

echo "deb https://ngrok-agent.s3.amazonaws.com buster main" \
  | sudo tee /etc/apt/sources.list.d/ngrok.list

sudo apt update && sudo apt install ngrok -y
```

Verificar que quedó instalado:

```bash
ngrok version
```

### 2.3 Autenticar ngrok con tu token

```bash
ngrok config add-authtoken TU_TOKEN_AQUI
```

Reemplaza `TU_TOKEN_AQUI` con el token copiado en el paso 2.1.

---

## Paso 3 — Configurar la base de datos

### 3.1 Crear la base de datos y cargar el esquema

Todos los comandos se ejecutan como el usuario `postgres`. Usa `sudo -u postgres` para evitar que PostgreSQL pida contraseña:

```bash
sudo -u postgres psql -f vacunatrack_diaitc.sql
```

Este archivo crea la base de datos, todas las tablas, vistas, triggers y stored procedures. No se necesita correr ningún archivo de migración por separado.

### 3.2 Insertar los datos de ejemplo (seed)

```bash
sudo -u postgres psql -d vacunatrack -f seed_v3.sql
```

El seed inserta datos de prueba (usuarios, pacientes, centros, lotes, aplicaciones) y al final **reinicia todas las secuencias de IDs** con `setval`, de modo que los INSERTs posteriores desde la app no colisionen con los IDs explícitos del seed.

> **Si necesitas empezar de cero** (re-ejecutar todo), elimina y recrea la base de datos:
> ```bash
> sudo -u postgres dropdb vacunatrack
> sudo -u postgres psql -f vacunatrack_diaitc.sql
> sudo -u postgres psql -d vacunatrack -f seed_v3.sql
> ```

### 3.4 Verificar que el usuario de PostgreSQL tiene contraseña (necesario para .env)

```bash
sudo -u postgres psql -c "\password postgres"
```

Ingresa la contraseña que quieras (por ejemplo `admin1234`). La necesitarás en el siguiente paso.

---

## Paso 4 — Crear el archivo `.env`

Dentro de la carpeta del proyecto:

```bash
cp .env.example .env
```

Luego edita `.env` con tu contraseña de PostgreSQL:

```bash
nano .env
```

Contenido del archivo:

```
DATABASE_URL=postgresql://postgres:TU_CONTRASEÑA@localhost:5432/vacunatrack
SECRET_KEY=vacunatrack-dev-secret-2026
```

Reemplaza `TU_CONTRASEÑA` con la contraseña que configuraste en el paso 3.4.

---

## Paso 5 — Instalar las dependencias de Python

```bash
pip install -r requirements.txt
```

---

## Paso 6 — Correr la aplicación Flask

```bash
export FLASK_APP=app.py
flask run --host=0.0.0.0
```

La app quedará escuchando en el puerto **5000** de la VM.

---

## Paso 7 — Exponer la app con ngrok

Abre una **segunda terminal** (sin cerrar la que corre Flask) y ejecuta:

```bash
ngrok http 5000
```

Ngrok mostrará una URL pública con el siguiente formato:

```
Forwarding   https://xxxx-xx-xx-xx.ngrok-free.app -> http://localhost:5000
```

Comparte esa URL `https://...` para acceder desde cualquier navegador externo.

> La URL cambia cada vez que reinicias ngrok (en el plan gratuito). Mientras Flask y ngrok estén corriendo, la URL sigue activa.

---

## Usuarios de ejemplo

| Rol | Correo | Contraseña |
|-----|--------|-----------|
| Administrador | admin@vacunatrack.mx | Admin2026! |
| Responsable clínico | diego@vacunatrack.mx | Diego2026! |
| Tutor | juan@correo.mx | Tutor2026! |

---

## Solución de problemas comunes

| Síntoma | Causa probable | Solución |
|---------|---------------|----------|
| `psql: error: FATAL: password authentication failed` | Contraseña incorrecta en `.env` | Verificar contraseña con `sudo -u postgres psql` |
| `ModuleNotFoundError: No module named 'psycopg'` | psycopg no instalado | `pip install psycopg[binary]` |
| `OperationalError: could not connect to server` | PostgreSQL no corre o DATABASE_URL mal | `sudo systemctl start postgresql` |
| Error al registrar aplicación (dosis) | SQL incompleto o seed no corrido | Verificar que `vacunatrack_diaitc.sql` y `seed_v3.sql` se ejecutaron sin errores |
| `duplicate key value violates unique constraint` al correr seed | Seed ejecutado dos veces sin recrear DB | `dropdb vacunatrack` → recrear desde cero |
| Ngrok pide autenticación al iniciar | Token no configurado | `ngrok config add-authtoken TU_TOKEN` |

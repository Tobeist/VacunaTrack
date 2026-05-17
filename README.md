# VacunaTrack

Sistema digital de control y seguimiento de vacunación infantil.  
Desarrollado por Equipo 6 — UDEM · Ingeniería en Tecnologías Computacionales · 2026.

---

## Descripción general

VacunaTrack permite a clínicas, responsables médicos y familias gestionar el esquema de vacunación infantil de forma digital. Integra tres fuentes de datos heterogéneas:

- **PostgreSQL** — fuente de verdad transaccional (pacientes, aplicaciones, inventario, usuarios).
- **MongoDB** — logs de eventos, analítica y datos semi-estructurados (accesos, aplicaciones, GPS, beacon).
- **Hardware IoT** — NFC, GPS y beacons Bluetooth para captura de datos en campo.

Roles del sistema: **Administrador**, **Responsable clínico** y **Tutor (padre/madre)**.

---

## Arquitectura

```
Navegador / Celular
       │
       ▼
   Flask (Python)
   ├── PostgreSQL  ← datos transaccionales
   └── MongoDB     ← logs y analítica
```

El proyecto corre en una VM de Google Cloud Platform expuesta mediante **ngrok** para acceso externo desde HTTPS (requerido por los APIs de geolocalización y Bluetooth del navegador).

---

## Requisitos previos

| Componente | Versión mínima |
|---|---|
| Python | 3.10 |
| PostgreSQL | 14 |
| MongoDB | 6.0 |
| pip | cualquier reciente |
| Cuenta ngrok | gratuita |

---

## Paso 1 — Subir y extraer el proyecto en la VM

Sube el repositorio a la VM (vía `scp`, consola de GCP o cliente SFTP) y extrae:

```bash
unzip vacunatrack.zip
cd vacunatrack
```

---

## Paso 2 — Instalar ngrok

### 2.1 Crear cuenta

1. Ir a [ngrok.com](https://ngrok.com) → **Sign up** (gratuito).
2. En el dashboard, copiar el **Authtoken** (menú izquierdo → *Your Authtoken*).

### 2.2 Instalar

```bash
curl -sSL https://ngrok-agent.s3.amazonaws.com/ngrok.asc \
  | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null

echo "deb https://ngrok-agent.s3.amazonaws.com buster main" \
  | sudo tee /etc/apt/sources.list.d/ngrok.list

sudo apt update && sudo apt install ngrok -y
ngrok version   # verificar instalación
```

### 2.3 Autenticar

```bash
ngrok config add-authtoken TU_TOKEN_AQUI
```

---

## Paso 3 — Configurar PostgreSQL

### 3.1 Verificar que PostgreSQL está corriendo

```bash
sudo systemctl status postgresql
# Si no está activo:
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### 3.2 Crear usuario, base de datos y esquema completo

El archivo `sql/01_schema.sql` crea el usuario `vacunatrack_user` (contraseña `666`), la base de datos `vacunatrack` y todas las tablas con sus tipos ENUM y restricciones.

```bash
sudo -u postgres psql -f sql/01_schema.sql
```

> Si el usuario o la base de datos ya existen de una ejecución anterior, elimínalos primero:
> ```bash
> sudo -u postgres psql -c "DROP DATABASE IF EXISTS vacunatrack;"
> sudo -u postgres psql -c "DROP USER IF EXISTS vacunatrack_user;"
> ```

### 3.3 Aplicar stored procedures

```bash
sudo -u postgres psql -d vacunatrack -f sql/02_stored_procedures.sql
```

### 3.4 Aplicar vistas

```bash
sudo -u postgres psql -d vacunatrack -f sql/03_views.sql
```

### 3.5 Aplicar triggers

```bash
sudo -u postgres psql -d vacunatrack -f sql/04_triggers.sql
```

### 3.6 Aplicar índices

```bash
sudo -u postgres psql -d vacunatrack -f sql/05_indexes.sql
```

### 3.7 Transferir ownership a vacunatrack_user

```bash
sudo -u postgres psql -d vacunatrack -f sql/06_ownership.sql
```

### 3.8 Verificar que todo quedó correcto

```bash
sudo -u postgres psql -d vacunatrack -c "\dt"   # listar tablas
sudo -u postgres psql -d vacunatrack -c "\dv"   # listar vistas
```

---

## Paso 4 — Configurar MongoDB

### 4.1 Verificar que MongoDB está corriendo

```bash
sudo systemctl status mongod
# Si no está activo:
sudo systemctl start mongod
sudo systemctl enable mongod
```

### 4.2 Crear usuarios de MongoDB

MongoDB ya tiene autenticación habilitada (`/etc/mongod.conf` → `authorization: enabled`). Crear los usuarios desde `mongosh`:

```bash
mongosh
```

Dentro de `mongosh`, ejecutar en orden:

```js
// 1. Usuario administrador de MongoDB
use admin
db.createUser({
  user: "mongoadmin",
  pwd: "666-999",
  roles: ["userAdminAnyDatabase", "readAnyDatabase"]
})

// 2. Usuario de la aplicación (solo acceso a la BD vacunatrack)
use vacunatrack
db.createUser({
  user: "vacunatrack_app",
  pwd: "666-999",
  roles: [{ role: "readWrite", db: "vacunatrack" }]
})

exit
```

### 4.3 Verificar autenticación

```bash
mongosh "mongodb://vacunatrack_app:666-999@localhost:27017/vacunatrack"
```

Debería abrir sesión sin error.

---

## Paso 5 — Configurar el archivo `.env`

Copia la plantilla y edítala:

```bash
cp .env.example .env
vi .env
```

Contenido final del `.env`:

```
DATABASE_URL=postgresql://vacunatrack_user:666@localhost:5432/vacunatrack
SECRET_KEY=vacunatrack-dev-secret-2026
MONGO_URL=mongodb://vacunatrack_app:666-999@localhost:27017/vacunatrack
MONGO_DB=vacunatrack
```

> `SECRET_KEY` puede ser cualquier cadena larga. En producción usa un valor aleatorio generado con:
> ```bash
> python3 -c "import secrets; print(secrets.token_hex(32))"
> ```

---

## Paso 6 — Instalar dependencias de Python

```bash
pip install -r requirements.txt
```

Las dependencias son:

| Paquete | Propósito |
|---|---|
| `Flask` | Framework web |
| `Werkzeug` | Utilidades HTTP y hashing de contraseñas |
| `psycopg[binary]` | Conector PostgreSQL para Python |
| `python-dotenv` | Lectura del archivo `.env` |
| `pymongo` | Conector MongoDB para Python |

---

## Paso 7 — Cargar datos semilla

### 7.1 Seed de PostgreSQL

El seed `seed_final.sql` limpia todas las tablas, reinicia secuencias e inserta datos coherentes y no triviales: 18 pacientes, 5 centros, 15 usuarios, 10 vacunas, 15 lotes, ~197 aplicaciones distribuidas de 2022 a 2026.

```bash
sudo -u postgres psql -d vacunatrack -f seed_final.sql
```

Después del seed, actualiza los hashes de contraseñas con la versión de Werkzeug instalada en la VM:

```bash
python3 seed_passwords.py
```

> Este paso es obligatorio. Los hashes de contraseñas dependen de la versión de Werkzeug instalada; `seed_passwords.py` los genera directamente en la máquina para garantizar compatibilidad.

> Para empezar de cero en cualquier momento, basta con volver a ejecutar este mismo archivo — ya incluye `TRUNCATE ... RESTART IDENTITY CASCADE` al inicio.

### 7.2 Seed de MongoDB

El script Python inserta logs de aplicaciones, accesos, eventos de beacon y búsquedas GPS en MongoDB, sincronizados con los datos de PostgreSQL.

```bash
python3 seed_mongo.py
```

---

## Paso 8 — Correr la aplicación Flask

```bash
export FLASK_APP=app.py
flask run --host=0.0.0.0
```

La app escucha en el puerto **5000**. Deja esta terminal abierta.

---

## Paso 9 — Exponer la app con ngrok

Abre una **segunda terminal** y ejecuta:

```bash
ngrok http 5000
```

Ngrok mostrará una URL pública:

```
Forwarding   https://xxxx-xx-xx-xx.ngrok-free.app -> http://localhost:5000
```

Comparte esa URL `https://...` para acceder desde cualquier navegador o celular.

> La URL HTTPS es **obligatoria** para que funcionen el GPS y el Bluetooth desde el navegador móvil. En HTTP el navegador bloquea ambos.
>
> La URL cambia cada vez que se reinicia ngrok en el plan gratuito. Flask y ngrok deben estar corriendo al mismo tiempo.

---

## Usuarios de acceso

| Rol | Correo | Contraseña |
|---|---|---|
| Administrador | `admin@vacunatrack.mx` | `Admin2024!` |
| Responsable (centro 1) | `diego@vacunatrack.mx` | `Resp2024!` |
| Responsable (centro 2) | `ana@vacunatrack.mx` | `Resp2024!` |
| Responsable (centro 3) | `roberto.chavez@vacunatrack.mx` | `Resp2024!` |
| Responsable (centro 4) | `maria@vacunatrack.mx` | `Resp2024!` |
| Responsable (centro 5) | `luis@vacunatrack.mx` | `Resp2024!` |
| Tutor | `juan@correo.mx` | `Tutor2024!` |
| Tutor | `carmen@correo.mx` | `Tutor2024!` |

---

## Tecnologías IoT integradas

### GPS (Geolocalización)

**Qué es:** La API `navigator.geolocation` del navegador, disponible en cualquier celular moderno.

**Cómo se usa en VacunaTrack:**

- En la vista de tutor, la pantalla **Buscar Centros** usa el GPS del celular para ordenar los centros de salud del más cercano al más lejano.
- El tutor presiona *Buscar cerca de mí* → el navegador solicita permiso de ubicación → si se concede, la app envía `lat` y `lng` al endpoint `/api/centros-cercanos` → el servidor calcula distancias con la fórmula Haversine y devuelve los centros ordenados.
- Cada búsqueda se registra en la colección `busquedas_gps` de MongoDB con las coordenadas y la vacuna buscada, alimentando la analítica de accesibilidad.

**Requisito técnico:** Funciona únicamente bajo **HTTPS** (de ahí el uso de ngrok). En HTTP el navegador bloquea la API de geolocalización.

---

### NFC (Near Field Communication)

**Qué es:** Tecnología de comunicación inalámbrica de corto alcance (< 4 cm), presente en la mayoría de celulares Android modernos. No disponible en iOS Safari.

**Cómo se usa en VacunaTrack:**

- Cada paciente puede tener una **etiqueta NFC** (sticker o tarjeta) con un identificador único grabado, almacenado en el campo `paciente_nfc` de la tabla `pacientes`.
- En la vista del **responsable clínico**, al iniciar la búsqueda de paciente, puede tocar *Leer NFC* → el celular lee la etiqueta → la app busca automáticamente al paciente con ese ID sin necesidad de escribir nada.
- Esto agiliza el registro de aplicaciones en entornos clínicos de alto volumen.
- La API usada es `navigator.nfc` (Web NFC), disponible en Chrome para Android bajo HTTPS.

**Requisito técnico:** Android con Chrome, bajo HTTPS. El teléfono debe tener NFC activado en los ajustes.

---

### Beacon Bluetooth (BLE)

**Qué es:** Dispositivo Bluetooth Low Energy que transmite continuamente una señal de identificación. VacunaTrack usa beacons tipo **FSC** instalados en los centros de salud.

**Cómo se usa en VacunaTrack:**

- Cada centro de salud puede tener un beacon registrado en el campo `centro_beacon` de la tabla `centros_salud` (formato `FSC-XXX-YYY`).
- En el **dashboard del tutor**, si el celular detecta un beacon cercano (al estar físicamente en el centro), aparece automáticamente una tarjeta con la información del centro: nombre, dirección, horario y vacunas disponibles.
- El tutor puede entonces confirmar su visita al centro. El evento se registra en la colección `eventos_beacon` de MongoDB.
- La API usada es `navigator.bluetooth.requestDevice()` con filtro `namePrefix: 'FSC-'`, que muestra únicamente los beacons de VacunaTrack en el selector del sistema operativo — no otros dispositivos Bluetooth cercanos.
- La detección también puede ocurrir por **proximidad GPS** como respaldo cuando Bluetooth no está disponible.

**Requisito técnico:** Navegador que soporte Bluetooth (Chrome en Andorid funciona, en Apple, usar navegador especializado como Bluefy), bajo HTTPS. Bluetooth activado en el teléfono. El dispositivo beacon debe estar encendido y dentro del rango (~10 m).

---

## Estructura del proyecto

```
vacunatrack_diaitc/
├── app.py                  # Punto de entrada de Flask
├── requirements.txt
├── .env.example
├── seed_final.sql          # Seed PostgreSQL completo
├── seed_mongo.py           # Seed MongoDB
│
├── sql/
│   ├── 01_schema.sql       # Usuario, BD, tablas y ENUMs
│   ├── 02_stored_procedures.sql
│   ├── 03_views.sql
│   ├── 04_triggers.sql
│   └── 05_indexes.sql
│
├── controllers/
│   ├── admin.py            # Rutas del administrador
│   ├── clinical.py         # Rutas del responsable clínico
│   ├── public.py           # Rutas públicas y del tutor
│   └── auth.py             # Login / logout
│
├── models/
│   ├── db.py               # Conexión y helpers PostgreSQL
│   ├── repository.py       # Capa de acceso a datos (SPs y queries)
│   └── mongo_db.py         # Conexión y helpers MongoDB
│
├── utils/
│   └── helpers.py          # Filtros Jinja2, lógica de historial
│
├── static/
│   ├── css/style.css
    ├── uploads/
│   └── js/main.js
│
└── templates/
    ├── base.html
    ├── admin/
    ├── clinical/
    └── public/
```

---

## Reinicio completo (desde cero)

Si necesitas borrar todo y empezar de nuevo:

```bash
# PostgreSQL
sudo -u postgres psql -c "DROP DATABASE IF EXISTS vacunatrack;"
sudo -u postgres psql -c "DROP USER IF EXISTS vacunatrack_user;"
sudo -u postgres psql -f sql/01_schema.sql
sudo -u postgres psql -d vacunatrack -f sql/02_stored_procedures.sql
sudo -u postgres psql -d vacunatrack -f sql/03_views.sql
sudo -u postgres psql -d vacunatrack -f sql/04_triggers.sql
sudo -u postgres psql -d vacunatrack -f sql/05_indexes.sql
sudo -u postgres psql -d vacunatrack -f sql/05_indexes.sql
sudo -u postgres psql -d vacunatrack -f sql/06_ownership.sql
sudo -u postgres psql -d vacunatrack -f seed_final.sql

# MongoDB
python3 seed_mongo.py

# Hashes de contraseñas
python3 seed_passwords.py
```

---

## Solución de problemas comunes

| Síntoma | Causa probable | Solución |
|---|---|---|
| `password authentication failed` | Contraseña incorrecta en `.env` | Verificar que `DATABASE_URL` usa `vacunatrack_user:666` |
| `ModuleNotFoundError: psycopg` | Dependencia faltante | `pip install psycopg[binary]` |
| `could not connect to server` | PostgreSQL no corre | `sudo systemctl start postgresql` |
| `MongoServerError: Authentication failed` | Usuario Mongo incorrecto | Verificar `MONGO_URL` en `.env` |
| `duplicate key value` al correr seed | Seed ejecutado dos veces | `seed_final.sql` ya incluye TRUNCATE — volver a ejecutarlo |
| GPS no funciona en el celular | Sitio en HTTP | Acceder siempre vía URL `https://` de ngrok |
| NFC no detecta la tarjeta | iOS o Chrome desactualizado | Usar Chrome en Android, NFC activado |
| Bluetooth no pide permiso | Sitio en HTTP | Acceder siempre vía URL `https://` de ngrok |
| Ngrok pide autenticación | Token no configurado | `ngrok config add-authtoken TU_TOKEN` |
| La URL de ngrok cambió | Se reinició ngrok | Volver a copiar la nueva URL del terminal |

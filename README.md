# VacunaTrack — Versión Demo (sin base de datos)

Sistema digital de control y seguimiento de vacunación infantil.
Desarrollado por Equipo 6 — UDEM.

---

## Requisitos

- Python 3.9 o superior
- No requiere PostgreSQL ni ninguna base de datos

---

## Cómo correrlo

### 1. Subir archivo .zip a la VM

### 2. Hacer el comando:

```bash
unzip vacunatrack.zip

```
### 3. Entrar a la carpeta de vacunatrack
```bash
cd vacunatrack

```
### 4. Instalar requirements
```bash

pip install -r requirements.txt
```

### 5. Exportar app flask

```bash
export FLASK_APP=app.py

python app.py
```

### 3. Abrir en el navegador

```
http://127.0.0.1:5000
```

---

## Usuarios de ejemplo

| Rol | Correo | Contraseña |
|-----|--------|-----------|
| Administrador | admin@vacunatrack.mx | Admin2026! |
| Responsable clínico | diego@vacunatrack.mx | Diego2026! |
| Tutor | juan@correo.mx | Tutor2026! |

---

## Nota importante

Esta es una versión de demostración. Los datos están guardados en memoria, por lo que **al reiniciar el servidor se pierden los cambios** realizados durante la sesión. Los datos de ejemplo se cargan automáticamente al iniciar.

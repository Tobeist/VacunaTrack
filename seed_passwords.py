"""
seed_passwords.py — Actualiza los hashes de contraseñas en la tabla login.

Debe ejecutarse DESPUÉS de seed_final.sql, en la misma máquina donde corre
la aplicación, para que los hashes sean compatibles con la versión de Werkzeug
instalada.

Uso:
    python3 seed_passwords.py
"""

import os
import psycopg
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://vacunatrack_user:666@localhost:5432/vacunatrack")

PASSWORDS = {
    "admin@vacunatrack.mx":             "Admin2024!",
    "diego@vacunatrack.mx":             "Resp2024!",
    "ana@vacunatrack.mx":               "Resp2024!",
    "roberto.chavez@vacunatrack.mx":    "Resp2024!",
    "maria@vacunatrack.mx":             "Resp2024!",
    "luis@vacunatrack.mx":              "Resp2024!",
    "juan@correo.mx":                   "Tutor2024!",
    "carmen@correo.mx":                 "Tutor2024!",
    "roberto.garcia@correo.mx":         "Tutor2024!",
    "sofia.martinez@correo.mx":         "Tutor2024!",
    "eduardo@correo.mx":                "Tutor2024!",
    "patricia@correo.mx":               "Tutor2024!",
    "fernando@correo.mx":               "Tutor2024!",
    "alejandra@correo.mx":              "Tutor2024!",
    "hector@correo.mx":                 "Tutor2024!",
}

def main():
    print("Generando hashes y actualizando tabla login...")
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            for email, password in PASSWORDS.items():
                hashed = generate_password_hash(password, method="pbkdf2:sha256")
                cur.execute(
                    "UPDATE login SET login_contrasena = %s WHERE login_correo = %s",
                    (hashed, email)
                )
                print(f"  ✓ {email}")
        conn.commit()
    print("Listo. Todos los passwords actualizados correctamente.")

if __name__ == "__main__":
    main()

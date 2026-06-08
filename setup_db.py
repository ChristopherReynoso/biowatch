"""
setup_db.py — BioWatch
═══════════════════════════════════════════════════════════════
Ejecuta este script UNA SOLA VEZ para crear la base de datos
con las tablas correctas y los operadores iniciales.

    python setup_db.py

Después de correrlo puedes editar las IPs de stream directamente
en la base con cualquier visor SQLite (ej. DB Browser for SQLite)
o con el endpoint PATCH /operadores/{id}/stream de la API.
═══════════════════════════════════════════════════════════════
"""

import sqlite3
import os

DB_PATH = "biowatch.db"

def crear_tablas(cursor):
    # ── Tabla: usuarios del sistema (login) ──────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre      TEXT    NOT NULL,
            apellido    TEXT    NOT NULL,
            email       TEXT    NOT NULL UNIQUE,
            username    TEXT    NOT NULL UNIQUE,
            password    TEXT    NOT NULL,   -- guarda el hash, nunca texto plano
            rol         TEXT    NOT NULL DEFAULT 'operador',  -- 'admin' | 'operador'
            activo      INTEGER NOT NULL DEFAULT 1,           -- 1=activo, 0=pendiente
            creado_en   TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
    """)

    # ── Tabla: operadores monitoreados (choferes) ─────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS operadores (
            id          TEXT    PRIMARY KEY,   -- ej. CH-006
            nombre      TEXT    NOT NULL,
            unidad      TEXT    NOT NULL,
            foto        TEXT,                  -- nombre de archivo, ej. ch006.jpg
            url_stream  TEXT,                  -- IP de la cámara; editable sin tocar código
            estado      TEXT    NOT NULL DEFAULT 'Normal',
            ear         REAL    NOT NULL DEFAULT 0.0,
            activo      INTEGER NOT NULL DEFAULT 1
        )
    """)

    # ── Tabla: historial de alertas de fatiga ─────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alertas (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            chofer_id       TEXT    NOT NULL REFERENCES operadores(id),
            unidad          TEXT    NOT NULL,
            ear             REAL    NOT NULL DEFAULT 0.0,
            timestamp       TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
    """)

    print("✅ Tablas creadas (o ya existían).")


def insertar_operadores_iniciales(cursor):
    """
    REPLACE INTO: si el ID ya existe lo actualiza, si no lo crea.
    Así puedes volver a correr este script sin duplicados.

    ⚠️  Cambia url_stream por la IP actual de cada cámara.
        Formato IPWebcam  : http://192.168.x.x:8080/video
        Formato RTSP Jooan: rtsp://admin:CLAVE@192.168.x.x:554/live/ch0
    """
    operadores = [
        # ( id,      nombre,               unidad,  foto,       url_stream,                                    estado,   ear, activo )
        ("CH-006", "Christopher Reynoso", "T-450", "f1.png",  "http://192.168.1.75:8080/video",              "Normal", 0.0, 1),
        ("CH-007", "Angel Flores",        "J-720", "f2.png",  "rtsp://admin:admin123@192.168.1.135:554/live/ch0", "Normal", 0.0, 1),
    ]

    cursor.executemany("""
        INSERT OR REPLACE INTO operadores
            (id, nombre, unidad, foto, url_stream, estado, ear, activo)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, operadores)

    print(f"✅ {len(operadores)} operadores insertados/actualizados.")


def insertar_usuario_admin(cursor):
    """
    Usuario administrador inicial.
    En producción reemplaza la contraseña por un hash bcrypt real.
    Por ahora usamos texto plano para que puedas probarlo de inmediato.
    """
    try:
        cursor.execute("""
            INSERT INTO usuarios (nombre, apellido, email, username, password, rol, activo)
            VALUES ('Admin', 'BioWatch', 'admin@biowatch.com', 'admin', '1234', 'admin', 1)
        """)
        print("✅ Usuario admin creado  →  usuario: admin  |  contraseña: 1234")
    except sqlite3.IntegrityError:
        print("ℹ️  Usuario admin ya existe, no se modificó.")


def main():
    if os.path.exists(DB_PATH):
        print(f"ℹ️  Base de datos existente encontrada: {DB_PATH}")
    else:
        print(f"📦 Creando nueva base de datos: {DB_PATH}")

    conn   = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    crear_tablas(cursor)
    insertar_operadores_iniciales(cursor)
    insertar_usuario_admin(cursor)

    conn.commit()
    conn.close()
    print("\n🚀 BioWatch DB lista. Ahora puedes arrancar la API con:  uvicorn api:app --reload")


if __name__ == "__main__":
    main()

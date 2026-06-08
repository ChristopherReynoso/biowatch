"""
api.py — BioWatch Unificado (Procesamiento y Video Integrado)
═══════════════════════════════════════════════════════════════
Arranque: uvicorn api:app --reload
¡Ya no necesitas ejecutar main.py ni main_jooan.py!
═══════════════════════════════════════════════════════════════
"""

import sqlite3
import os
import shutil
import time
import asyncio
from contextlib import contextmanager
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
import cv2
import mediapipe as mp

# Importamos los cálculos matemáticos puros de tu detector
from detector import calculate_ear, calculate_mar, LEFT_EYE, RIGHT_EYE, MOUTH

# ── Configuración ────────────────────────────────────────────────
DB_PATH     = "biowatch.db"
FOTOS_DIR   = "fotos"
os.makedirs(FOTOS_DIR, exist_ok=True)

# Parámetros del detector de fatiga unificado
UMBRAL_EAR       = 0.22
UMBRAL_MAR       = 0.50
TIEMPO_FATIGA    = 1.5
TIEMPO_BOSTEZO   = 2.0

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/fotos", StaticFiles(directory=FOTOS_DIR), name="fotos")


# ── Helper de conexión optimizado ─────────────────────────────────
@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;") 
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


# ── Modelos Pydantic (Mantenidos por compatibilidad) ──────────────
class Incidencia(BaseModel):
    chofer_id:  str
    alerta:     str
    ear:        float
    is_sleeping: bool


# ════════════════════════════════════════════════════════════════════
#  ENDPOINTS — OPERADORES Y ALERTAS
# ════════════════════════════════════════════════════════════════════

@app.get("/status_general")
async def obtener_status_general():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, nombre, unidad, foto, url_stream, estado, ear "
            "FROM operadores WHERE activo = 1"
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/status/{chofer_id}")
async def obtener_status_individual(chofer_id: str):
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, nombre, unidad, foto, url_stream, estado, ear "
            "FROM operadores WHERE id = ?",
            (chofer_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Operador no encontrado")
    return dict(row)


@app.post("/incidencia")
async def registrar_incidencia(datos: Incidencia):
    """Mantenido solo por si acaso, pero el procesamiento real ahora ocurre en vivo."""
    nuevo_estado = "Fatiga" if datos.is_sleeping else "Normal"
    with get_db() as conn:
        op = conn.execute("SELECT id, unidad, estado FROM operadores WHERE id = ?", (datos.chofer_id,)).fetchone()
        if not op: return {"status": "chofer_no_encontrado"}
        
        conn.execute("UPDATE operadores SET estado = ?, ear = ? WHERE id = ?", (nuevo_estado, datos.ear, datos.chofer_id))
        if nuevo_estado == "Fatiga" and op["estado"] != "Fatiga":
            conn.execute("INSERT INTO alertas (chofer_id, unidad, ear) VALUES (?, ?, ?)", (datos.chofer_id, op["unidad"], datos.ear))
        conn.commit()
    return {"status": "ok", "estado_aplicado": nuevo_estado}


@app.post("/operadores")
async def agregar_operador(
    nombre:     str        = Form(...),
    apellido:   str        = Form(...),
    id:         str        = Form(...),
    unidad:     str        = Form(...),
    url_stream: str        = Form(""),
    foto:       UploadFile = File(...),
):
    with get_db() as conn:
        existe = conn.execute("SELECT id FROM operadores WHERE id = ?", (id,)).fetchone()
        if existe:
            raise HTTPException(status_code=400, detail=f"El ID '{id}' ya está registrado.")

    ext       = os.path.splitext(foto.filename)[1].lower() or ".jpg"
    foto_nombre = f"{id.replace('-','_').lower()}{ext}"
    foto_path   = os.path.join(FOTOS_DIR, foto_nombre)
    with open(foto_path, "wb") as f:
        shutil.copyfileobj(foto.file, f)

    nombre_completo = f"{nombre} {apellido}"

    with get_db() as conn:
        conn.execute(
            "INSERT INTO operadores (id, nombre, unidad, foto, url_stream, estado, ear, activo) "
            "VALUES (?, ?, ?, ?, ?, 'Normal', 0.0, 1)",
            (id, nombre_completo, unidad, foto_nombre, url_stream)
        )
        conn.commit()

    return {"status": "ok", "id": id, "foto": foto_nombre}


@app.patch("/operadores/{chofer_id}/stream")
async def actualizar_stream(chofer_id: str, url_stream: str = Form(...)):
    with get_db() as conn:
        result = conn.execute("UPDATE operadores SET url_stream = ? WHERE id = ?", (url_stream, chofer_id))
        conn.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Operador no encontrado")
    return {"status": "ok", "id": chofer_id, "url_stream": url_stream}


@app.get("/alertas/{chofer_id}")
async def obtener_alertas(chofer_id: str, limite: int = 50):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, unidad, ear, timestamp FROM alertas WHERE chofer_id = ? ORDER BY id DESC LIMIT ?",
            (chofer_id, limite)
        ).fetchall()
    return [dict(r) for r in rows]


# ════════════════════════════════════════════════════════════════════
#  ENDPOINTS — LOGIN / USUARIOS
# ════════════════════════════════════════════════════════════════════

class LoginData(BaseModel):
    username: str
    password: str

class RegistroData(BaseModel):
    nombre:   str
    apellido: str
    email:    str
    username: str
    password: str

@app.post("/auth/login")
async def login(datos: LoginData):
    with get_db() as conn:
        user = conn.execute(
            "SELECT id, nombre, apellido, username, rol, activo FROM usuarios WHERE username = ? AND password = ?",
            (datos.username, datos.password)
        ).fetchone()

    if not user: raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    if not user["activo"]: raise HTTPException(status_code=403, detail="Cuenta pendiente de activación")

    return {
        "status": "ok", "id": user["id"], "nombre": user["nombre"],
        "apellido": user["apellido"], "username": user["username"], "rol": user["rol"],
    }

@app.post("/auth/registro")
async def registro(datos: RegistroData):
    with get_db() as conn:
        try:
            conn.execute(
                "INSERT INTO usuarios (nombre, apellido, email, username, password, activo) VALUES (?, ?, ?, ?, ?, 0)",
                (datos.nombre, datos.apellido, datos.email, datos.username, datos.password)
            )
            conn.commit()
        except sqlite3.IntegrityError as e:
            if "email" in str(e): raise HTTPException(status_code=400, detail="El correo ya está registrado.")
            if "username" in str(e): raise HTTPException(status_code=400, detail="El usuario ya está en uso.")
            raise HTTPException(status_code=400, detail="Dato duplicado.")
    return {"status": "ok", "message": "Cuenta creada. Espera activación del administrador."}


# ════════════════════════════════════════════════════════════════════
#  NÚCLEO CENTRALIZADO: DETECTOR + STREAM EN UN SOLO PASO
# ════════════════════════════════════════════════════════════════════

async def generar_frames(chofer_id: str):
    """
    Abre la cámara UNA ÚNICA VEZ.
    Lee el frame, calcula la fatiga en tiempo real y transmite el video.
    Se eliminan por completo los conflictos de hardware concurrentes.
    """
    with get_db() as conn:
        row = conn.execute("SELECT url_stream, unidad, estado FROM operadores WHERE id = ?", (chofer_id,)).fetchone()
    
    if not row or not row[0]:
        return
    
    url_camara = row["url_stream"]
    unidad     = row["unidad"]
    origen     = int(url_camara) if url_camara.isdigit() else url_camara
    
    # Inicializar MediaPipe Mesh de forma local y segura para este flujo
    mp_face_mesh = mp.solutions.face_mesh
    face_mesh = mp_face_mesh.FaceMesh(
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    )
    
    cap = cv2.VideoCapture(origen)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    
    contador_ojos = None
    contador_boca = None
    ultimo_estado_db = row["estado"]
    
    while True:
        success, frame = await asyncio.to_thread(cap.read)
        if not success:
            await asyncio.sleep(0.01)
            continue
            
        # 1. Ejecutar análisis de MediaPipe sobre el mismo frame capturado
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = face_mesh.process(frame_rgb)
        
        ear_promedio = 0.0
        mar = 0.0
        fatiga_detectada = False
        
        if results.multi_face_landmarks:
            for face_landmarks in results.multi_face_landmarks:
                # Obtener EAR (Ojos)
                ear_promedio = (calculate_ear(LEFT_EYE, face_landmarks) + calculate_ear(RIGHT_EYE, face_landmarks)) / 2.0
                # Obtener MAR (Boca)
                mar = calculate_mar(MOUTH, face_landmarks)
                
                # Evaluación temporal estricta de Fatiga
                if ear_promedio < UMBRAL_EAR:
                    if contador_ojos is None: contador_ojos = time.time()
                    if (time.time() - contador_ojos) >= TIEMPO_FATIGA: fatiga_detectada = True
                else:
                    contador_ojos = None
                    
                if mar > UMBRAL_MAR:
                    if contador_boca is None: contador_boca = time.time()
                    if (time.time() - contador_boca) >= TIEMPO_BOSTEZO: fatiga_detectada = True
                else:
                    contador_boca = None

        nuevo_estado = "Fatiga" if fatiga_detectada else "Normal"
        
        # 2. Sincronizar con la Base de Datos directamente sin peticiones HTTP externas
        if nuevo_estado != ultimo_estado_db:
            with get_db() as conn:
                conn.execute(
                    "UPDATE operadores SET estado = ?, ear = ? WHERE id = ?",
                    (nuevo_estado, round(ear_promedio, 4), chofer_id)
                )
                if nuevo_estado == "Fatiga" and ultimo_estado_db != "Fatiga":
                    conn.execute(
                        "INSERT INTO alertas (chofer_id, unidad, ear) VALUES (?, ?, ?)",
                        (chofer_id, unidad, round(ear_promedio, 4))
                    )
                    print(f"⚠️ [Núcleo Integrado] Alerta de Fatiga registrada en DB para: {chofer_id}")
                conn.commit()
            ultimo_estado_db = nuevo_estado
        else:
            # Actualización ultra-ligera y continua del valor EAR actual en la DB
            with get_db() as conn:
                conn.execute("UPDATE operadores SET ear = ? WHERE id = ?", (round(ear_promedio, 4), chofer_id))
                conn.commit()

        # 3. Dibujar datos directo en el video (Feedback visual en tiempo real para el monitor)
        color_alert = (0, 0, 255) if nuevo_estado == "Fatiga" else (0, 255, 0)
        cv2.putText(frame, f"Estado: {nuevo_estado}", (30, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color_alert, 2)
        cv2.putText(frame, f"EAR: {round(ear_promedio, 3)}", (30, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # Redimensión estándar y codificación de imagen
        frame_redimensionado = cv2.resize(frame, (640, 480))
        ret, buffer = cv2.imencode('.jpg', frame_redimensionado, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
        if not ret: continue
            
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
               
        await asyncio.sleep(0.01)
                    
    cap.release()
    face_mesh.close()


@app.get("/video_feed/{chofer_id}")
async def video_feed(chofer_id: str):
    """Endpoint único de transmisión directa."""
    return StreamingResponse(generar_frames(chofer_id), 
                             media_type="multipart/x-mixed-replace; boundary=frame")
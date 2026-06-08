import cv2
import mediapipe as mp
import winsound
import time
import sqlite3
import requests
import threading
from detector import calculate_ear, calculate_mar, LEFT_EYE, RIGHT_EYE, MOUTH

CHOFER_ID        = "CH-006"
UMBRAL_EAR       = 0.22
UMBRAL_MAR       = 0.50
TIEMPO_FATIGA    = 1.5
TIEMPO_BOSTEZO   = 2.0
FRECUENCIA_BEEP  = 2900
DURACION_BEEP    = 500

def obtener_url_stream(chofer_id: str) -> str:
    try:
        conn = sqlite3.connect("biowatch.db")
        row  = conn.execute(
            "SELECT url_stream FROM operadores WHERE id = ?", (chofer_id,)
        ).fetchone()
        conn.close()
        if row and row[0]:
            print(f"✅ Stream cargado desde DB: {row[0]}")
            return row[0]
    except Exception as e:
            print(f"⚠️ No se pudo leer la DB: {e}")
    
    fallback = "http://10.253.250.67:8080/video"
    print(f"⚠️ Usando IP de fallback: {fallback}")
    return fallback

# ── NUEVO: Función asilada para enviar a la API sin bloquear el video ──
def enviar_datos_api(datos):
    try:
        requests.post("http://127.0.0.1:8000/incidencia", json=datos, timeout=1.0)
    except Exception:
        pass # Si falla momentáneamente, ignoramos para no saturar la consola

url_stream = obtener_url_stream(CHOFER_ID)

contador_ojos = None
contador_boca = None

mp_face_mesh = mp.solutions.face_mesh
face_mesh    = mp_face_mesh.FaceMesh(refine_landmarks=True)
cap          = cv2.VideoCapture(url_stream)

print(f"Sistema BioWatch: Monitoreo Multimodal Activado para {CHOFER_ID}...")

# ── NUEVO: Variables de control para evitar DDoS a la API ──
ultimo_estado_enviado = None
ultimo_tiempo_envio = 0
INTERVALO_ENVIO_NORMAL = 2.0  # Si está despierto, manda señal cada 2s
INTERVALO_ENVIO_FATIGA = 0.5  # Si hay fatiga, manda señal cada 0.5s

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results   = face_mesh.process(rgb_frame)

    estado_para_api = {
        "chofer_id":  CHOFER_ID,
        "alerta":     "Normal",
        "ear":        0.0,
        "is_sleeping": False,
    }

    fatiga_detectada = False

    if results.multi_face_landmarks:
        for face_landmarks in results.multi_face_landmarks:
            ear_promedio = (
                calculate_ear(LEFT_EYE, face_landmarks) +
                calculate_ear(RIGHT_EYE, face_landmarks)
            ) / 2.0
            estado_para_api["ear"] = round(ear_promedio, 4)
            mar = calculate_mar(MOUTH, face_landmarks)

            if ear_promedio < UMBRAL_EAR:
                if contador_ojos is None:
                    contador_ojos = time.time()
                if (time.time() - contador_ojos) >= TIEMPO_FATIGA:
                    fatiga_detectada = True
            else:
                contador_ojos = None

            if mar > UMBRAL_MAR:
                if contador_boca is None:
                    contador_boca = time.time()
                if (time.time() - contador_boca) >= TIEMPO_BOSTEZO:
                    fatiga_detectada = True
            else:
                contador_boca = None

            if fatiga_detectada:
                winsound.Beep(FRECUENCIA_BEEP, DURACION_BEEP)
                estado_para_api["is_sleeping"] = True
                estado_para_api["alerta"]      = "Critica"

    # ── NUEVO: Lógica de aceleración (Throttle) ──
    tiempo_actual = time.time()
    estado_actual = "Fatiga" if fatiga_detectada else "Normal"
    
    intervalo_requerido = INTERVALO_ENVIO_FATIGA if fatiga_detectada else INTERVALO_ENVIO_NORMAL

    # Solo enviamos si el estado cambió O si ya pasó el tiempo de gracia
    if (estado_actual != ultimo_estado_enviado) or (tiempo_actual - ultimo_tiempo_envio >= intervalo_requerido):
        # Hacemos una copia del diccionario para el hilo
        datos_clon = dict(estado_para_api)
        
        # Enviamos la petición en un hilo en segundo plano
        threading.Thread(target=enviar_datos_api, args=(datos_clon,), daemon=True).start()
        
        ultimo_estado_enviado = estado_actual
        ultimo_tiempo_envio = tiempo_actual

cap.release()
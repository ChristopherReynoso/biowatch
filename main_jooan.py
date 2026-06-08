import cv2
import mediapipe as mp
import winsound
import time
import sqlite3
import requests
import threading
from detector import calculate_ear, calculate_mar, LEFT_EYE, RIGHT_EYE, MOUTH

CHOFER_ID        = "CH-007"
UMBRAL_EAR       = 0.22
UMBRAL_MAR       = 0.50
TIEMPO_FATIGA    = 1.5
TIEMPO_BOSTEZO   = 2.0
FRECUENCIA_BEEP  = 2900
DURACION_BEEP    = 400

def obtener_url_stream(chofer_id: str) -> str:
    try:
        conn = sqlite3.connect("biowatch.db")
        row  = conn.execute("SELECT url_stream FROM operadores WHERE id = ?", (chofer_id,)).fetchone()
        conn.close()
        return row[0] if row else None
    except Exception as e:
        print(f"Error base datos: {e}")
        return None

def emitir_alerta_sonora():
    winsound.Beep(FRECUENCIA_BEEP, DURACION_BEEP)

def main():
    url_stream = obtener_url_stream(CHOFER_ID)
    if not url_stream:
        print("No se encontró stream.")
        return

    origen = int(url_stream) if url_stream.isdigit() else url_stream
    cap = cv2.VideoCapture(origen)
    
    mp_face_mesh = mp.solutions.face_mesh
    face_mesh = mp_face_mesh.FaceMesh(max_num_faces=1, refine_landmarks=True)

    contador_ojos = None
    contador_boca = None
    
    ultimo_estado_enviado = "Normal"
    ultimo_envio_metricas = time.time()

    print(f"Iniciando BioWatch para {CHOFER_ID}...")

    while cap.isOpened():
        success, frame = cap.read()
        if not success:
            break

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = face_mesh.process(rgb_frame)

        estado_actual = "Normal"
        ear_promedio = 0.30
        fatiga_detectada = False

        if results.multi_face_landmarks:
            face_landmarks = results.multi_face_landmarks[0]
            ear_promedio = (calculate_ear(LEFT_EYE, face_landmarks) + calculate_ear(RIGHT_EYE, face_landmarks)) / 2.0
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
                estado_actual = "Fatiga"
                threading.Thread(target=emitir_alerta_sonora, daemon=True).start()

        tiempo_actual = time.time()
        
        if (estado_actual != ultimo_estado_enviado) or \
           (estado_actual == "Normal" and tiempo_actual - ultimo_envio_metricas >= 5.0) or \
           (estado_actual == "Fatiga" and tiempo_actual - ultimo_envio_metricas >= 2.0):
            
            estado_para_api = {
                "chofer_id": CHOFER_ID,
                "is_sleeping": (estado_actual == "Fatiga"),
                "ear": round(ear_promedio, 4),
                "alerta": "Critica" if estado_actual == "Fatiga" else "Ninguna"
            }
            
            try:
                requests.post("http://127.0.0.1:8000/incidencia", json=estado_para_api, timeout=0.2)
                ultimo_estado_enviado = estado_actual
                ultimo_envio_metricas = time.time()
            except requests.exceptions.RequestException:
                pass

    cap.release()

if __name__ == "__main__":
    main()
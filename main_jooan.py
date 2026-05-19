import cv2
import mediapipe as mp
import winsound
import time
import requests
from detector import calculate_ear, calculate_mar, LEFT_EYE, RIGHT_EYE, MOUTH

# --- Configuración Técnica Avanzada ---
UMBRAL_EAR = 0.22      
UMBRAL_MAR = 0.50      # Umbral para detectar boca abierta (bostezo)
TIEMPO_FATIGA = 1.5    
TIEMPO_BOSTEZO = 2.0   # Un bostezo largo indica fatiga
FRECUENCIA_BEEP = 2900 
DURACION_BEEP = 500    
contador_ojos = None
contador_boca = None

mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(refine_landmarks=True)

# --- CONFIGURACIÓN DE CÁMARA JOOAN ---
# Reemplaza con la IP que te de la app Cam720 y la clave ONVIF que configuraste
# Ejemplo: 'rtsp://admin:tu_clave@192.168.1.15:554/live/ch0'
url_jooan = 'rtsp://admin:admin123@192.168.1.76:554/live/ch0' 
cap = cv2.VideoCapture(url_jooan)

print("Sistema BioWatch: Monitoreo Multimodal Activado para Operador Jooan (CH-007)...")

while cap.isOpened():
    ret, frame = cap.read()
    if not ret: 
        print("Error: No se puede recibir video de la cámara Jooan. Revisa la IP.")
        break

    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = face_mesh.process(rgb_frame)
    
    # Estado por defecto para este operador
    estado_para_api = {
        "chofer_id": "CH-007", 
        "alerta": "Normal", 
        "ear": 0.0, 
        "is_sleeping": False
    }

    if results.multi_face_landmarks:
        for face_landmarks in results.multi_face_landmarks:
            # 1. Análisis Ocular (EAR)
            ear_promedio = (calculate_ear(LEFT_EYE, face_landmarks) + calculate_ear(RIGHT_EYE, face_landmarks)) / 2.0
            estado_para_api["ear"] = round(ear_promedio, 4)

            # 2. Análisis Bucal (MAR)
            mar = calculate_mar(MOUTH, face_landmarks)

            fatiga_detectada = False

            # Caso A: Ojos cerrados
            if ear_promedio < UMBRAL_EAR:
                if contador_ojos is None: contador_ojos = time.time()
                if (time.time() - contador_ojos) >= TIEMPO_FATIGA:
                    fatiga_detectada = True
            else:
                contador_ojos = None

            # Caso B: Bostezo prolongado
            if mar > UMBRAL_MAR:
                if contador_boca is None: contador_boca = time.time()
                if (time.time() - contador_boca) >= TIEMPO_BOSTEZO:
                    fatiga_detectada = True
            else:
                contador_boca = None

            if fatiga_detectada:
                winsound.Beep(FRECUENCIA_BEEP, DURACION_BEEP)
                estado_para_api["is_sleeping"] = True
                estado_para_api["alerta"] = "Critica"
                cv2.putText(frame, "ALERTA MULTIMODAL - JOOAN", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255), 2)

    # Envío a la API
    try:
        requests.post("http://127.0.0.1:8000/incidencia", json=estado_para_api, timeout=0.1)
    except:
        pass

    cv2.imshow('BioWatch - Monitor Jooan (CH-007)', frame)
    if cv2.waitKey(1) & 0xFF == ord('q'): break

cap.release()
cv2.destroyAllWindows()
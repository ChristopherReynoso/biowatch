from scipy.spatial import distance as dist

def calculate_ear(eye_points, landmarks):
    p = []
    for index in eye_points:
        point = landmarks.landmark[index]
        p.append((point.x, point.y))
    v1 = dist.euclidean(p[1], p[5])
    v2 = dist.euclidean(p[2], p[4])
    h1 = dist.euclidean(p[0], p[3])
    return (v1 + v2) / (2.0 * h1)

def calculate_mar(mouth_points, landmarks):
    # Puntos internos de la boca para detectar bostezo
    p = []
    for index in mouth_points:
        point = landmarks.landmark[index]
        p.append((point.x, point.y))
    # Distancia vertical interna / Distancia horizontal interna
    v = dist.euclidean(p[2], p[10]) # Labio superior a inferior
    h = dist.euclidean(p[0], p[6])  # Comisura izquierda a derecha
    return v / h

# Índices MediaPipe
LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]
MOUTH = [78, 81, 13, 311, 308, 402, 14, 178, 82, 312, 11, 317] # Malla labial interna
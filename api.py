from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Simulamos la base de datos en memoria
datos_flota = {
    "CH-006": {"id": "CH-006", "nombre": "Christopher Reynoso", "unidad": "T-450", "estado": "Normal", "ear": 0.0},
    "CH-007": {"id": "CH-007", "nombre": "Angel Flores", "unidad": "J-720", "estado": "Normal", "ear": 0.0}
}

class Incidencia(BaseModel):
    chofer_id: str
    alerta: str
    ear: float
    is_sleeping: bool

@app.post("/incidencia")
async def registrar_incidencia(datos: Incidencia):
    if datos.chofer_id in datos_flota:
        # Actualizamos los datos en la memoria
        datos_flota[datos.chofer_id]["estado"] = "Fatiga" if datos.is_sleeping else "Normal"
        datos_flota[datos.chofer_id]["ear"] = datos.ear
    return {"status": "ok"}

@app.get("/status_general")
async def obtener_status_general():
    # Devolvemos la lista de lo que hay en memoria
    return list(datos_flota.values())

@app.get("/status/{chofer_id}")
async def obtener_status_individual(chofer_id: str):
    return datos_flota.get(chofer_id, {"error": "No encontrado"})
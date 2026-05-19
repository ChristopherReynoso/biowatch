import sqlite3

def iniciar_db():
    conn = sqlite3.connect('biowatch.db')
    cursor = conn.cursor()
    
    # Aseguramos que la tabla exista
    cursor.execute('''CREATE TABLE IF NOT EXISTS operadores (
        id TEXT PRIMARY KEY,
        nombre TEXT,
        unidad TEXT,
        foto TEXT,
        url_stream TEXT,
        estado TEXT DEFAULT 'Normal'
    )''')
    
    # Tus datos actuales con las IPs que ya tienes
    operadores = [
        ('CH-008', 'Christopher Reynoso', 'T-450', 'f1.png', 'http://192.168.1.78:8080/video'),
        ('CH-009', 'Angel Flores', 'J-720', 'f2.png', 'rtsp://admin:admin123@192.168.1.94:554/live/ch0')
    ]
    
    # REPLACe es la clave: evita el error de "id duplicado"
    cursor.executemany('REPLACE INTO operadores VALUES (?,?,?,?,?,?)', operadores)
    
    conn.commit()
    conn.close()
    print("✅ Base de datos actualizada con Christopher y Angel.")

if __name__ == "__main__":
    iniciar_db()
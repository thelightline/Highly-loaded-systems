from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
import pandas as pd
import datetime
import asyncpg
from hashlib import sha3_256
import logging
import random
import os
import uvicorn

# Конфигурация логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ваш код для определения варианта
study_group = "211-331"
fio = "широков матвей сергеевич"
suffix = "Высоконагруженные системы. Лабораторная работа 1"
variant = int(sha3_256(f"{study_group} {fio} {suffix}".encode('utf-8')).hexdigest(), 16) % 3 + 1
logger.info(f"Номер варианта: {variant}")

app = FastAPI()

# Конфигурация БД
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@db:5432/mydb")

port = int(os.getenv("PORT", 5001))

class LogEntry(BaseModel):
    filename: str
    uploaded_at: datetime.datetime

async def get_db_connection():
    return await asyncpg.connect(DATABASE_URL)

@app.get("/")
async def home():
    return {"message": f"Backend on port {port}"}

@app.get("/data")
async def data():
    return {"value": random.randint(1, 100)}

@app.get("/status")
async def status():
    return {"service": "backend", "port": port}

@app.on_event("startup")
async def startup():
    conn = await get_db_connection()
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id SERIAL PRIMARY KEY,
            filename TEXT,
            uploaded_at TIMESTAMP
        )
    ''')
    await conn.close()

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        # Чтение и анализ CSV
        df = pd.read_csv(file.file)
        numeric_cols = df.select_dtypes(include=['number']).columns
        stats = {
            col: {
                "mean": df[col].mean().item(),  # <-- .item() для преобразования
                "max": df[col].max().item(),
                "min": df[col].min().item()
            } for col in numeric_cols
        }

        # Логирование в БД
        conn = await get_db_connection()
        await conn.execute(
            "INSERT INTO logs(filename, uploaded_at) VALUES($1, $2)",
            file.filename, datetime.datetime.now()
        )
        await conn.close()

        return {"filename": file.filename, "stats": stats}
    
    except Exception as e:
        logger.error(f"Ошибка: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/logs")
async def get_logs():
    conn = await get_db_connection()
    logs = await conn.fetch("SELECT * FROM logs")
    await conn.close()
    return [dict(log) for log in logs]

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        reload=True
    )

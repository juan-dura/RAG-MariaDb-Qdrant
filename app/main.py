import os
import shutil
import logging
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from pathlib import Path
import time
from typing import List

# Importamos clases de la aplicación
from app.classes.document import Document
from app.classes.database import Database
from app.services.ingestion import IngestionService
from app.config import Config
from app.classes.colpaliModel import ColPaliModel

app = FastAPI()

# Inicializamos la base de datos (MariaDB + Qdrant)
db = Database()

# Directorios
TEMP_DIR = Path(Config.TEMP_DIR)
DATA_DIR = Path(Config.DATA_DIR)

# Asegurar que existan las carpetas
TEMP_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)
# Crear DATA_DIR/pages para guardar las imágenes de las páginas
(DATA_DIR / "pages").mkdir(parents=True, exist_ok=True)

@app.post(
    "/upload-pdf/",
    summary="Sube un archivo PDF para su ingestión",
    description="""
    Sube un archivo PDF, que se guardará en el sistema y se procesará para extraer su contenido y metadatos.
    Calcula su hash SHA-256 para verificar si ya existe en la base de datos:
    1. Si **existe**, devuelve los datos del registro actual sin duplicar el archivo.
    2. Si **no existe**, guarda el archivo en `./data/{hash}.pdf` y crea un nuevo registro en MariaDB.

    El proceso de ingestión incluye:
    - Extracción de texto e imágenes de cada página.
    - Generación de embeddings multi-vectoriales usando el modelo ColPali.
    - Almacenamiento de los embeddings en Qdrant con metadatos asociados.
    """
)
async def upload_pdf(file: UploadFile = File(...)):
    # 1. Validar extensión rápida
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="El archivo debe ser un PDF")

    # 2. Guardado temporal para que Document pueda leerlo y generar el hash
    temp_path = TEMP_DIR / file.filename
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 3. Usar la clase Document para obtener el hash y metdatos
        # Usamos el context manager para asegurar que el archivo se cierre al terminar
        with Document(str(temp_path)) as doc:
            file_hash = doc.hash
            final_path = DATA_DIR / f"{file_hash}.pdf"
            # Si el archivo ya existe en final_path borramos temp_path, si no existe lo movemos a final_path
            if final_path.exists():
                os.remove(temp_path)
            else:
                shutil.move(str(temp_path), str(final_path))

            # 4. Procesar el documento con IngestionService
            inicio = time.perf_counter()
            with ColPaliModel() as model:
                ingestion_service = IngestionService(db)
                result = ingestion_service.ingest_document(doc, model=model)
            fin = time.perf_counter()

            return {**result, "processing_time": f"{fin - inicio:.6f}"}

    except Exception as e:
        if temp_path.exists():
            os.remove(temp_path)
        logging.error(f"Error en el upload/db: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
from typing import List
from fastapi import UploadFile, File

@app.post(
    "/upload-pdfs/",
    summary="Sube varios archivos PDF para su ingestión",
    description="Permite subir y procesar varios archivos PDF en una sola petición."
)
async def upload_pdfs(files: List[UploadFile] = File(...)):
    results = []
    inicio_total = time.perf_counter()
    with ColPaliModel() as model:
        ingestion_service = IngestionService(db)
        for file in files:
            inicio = time.perf_counter()
            if not file.filename or not file.filename.lower().endswith(".pdf"):
                fin = time.perf_counter()
                logging.warning(f"Archivo {file.filename} no es un PDF. Tiempo de validación: {fin - inicio:.6f}s")
                results.append(
                    {
                        "filename": file.filename,
                        "error": "El archivo debe ser un PDF",
                        "processing_time": f"{fin - inicio:.6f}"
                    }
                )
                continue

            temp_path = TEMP_DIR / file.filename
            try:
                with temp_path.open("wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)

                with Document(str(temp_path)) as doc:
                    file_hash = doc.hash
                    final_path = DATA_DIR / f"{file_hash}.pdf"
                    if final_path.exists():
                        os.remove(temp_path)
                    else:
                        shutil.move(str(temp_path), str(final_path))
                    result = ingestion_service.ingest_document(doc, model=model)
                    fin = time.perf_counter()
                    results.append({**result, "processing_time": f"{fin - inicio:.6f}"})
            except Exception as e:
                if temp_path.exists():
                    os.remove(temp_path)
                logging.error(f"Error en el upload/db: {e}")
                fin = time.perf_counter()
                results.append({"filename": file.filename, "error": str(e), "processing_time": f"{fin - inicio:.6f}"})
    fin_total = time.perf_counter()
    return {"total_processing_time": f"{fin_total - inicio_total:.6f}","results": results }
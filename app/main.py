
# Primero loggeamos el inicio de la aplicación para confirmar que el logging funciona correctamente
from fileinput import filename
import logging

from fastapi.concurrency import asynccontextmanager
from app.config import Config
# Importamos clases de la aplicación
from app.classes.document import Document
from app.classes.database import Database
from app.services.ingestion import IngestionService
from app.classes.colpaliModel import ColPaliModel

# librerias python
from pydantic import BaseModel
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
import os
import shutil
from pathlib import Path
import time
from typing import List, Optional
import uvicorn


logger = logging.getLogger(__name__)
logger.warning("Aplicación iniciada. Los logs se están escribiendo en rag_system.log")

# Directorios
TEMP_DIR = Path(Config.TEMP_DIR)
DATA_DIR = Path(Config.DATA_DIR)
# Asegurar que existan las carpetas
TEMP_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# 1. Definimos un diccionario global o contenedor para los recursos pesados
app_resources = {}
# 2. Creamos el gestor del ciclo de vida
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- CÓDIGO AL ARRANCAR ---
    print("Cargando modelo ColPali y bases de datos...")
    try:
        # Cargamos el modelo una sola vez
        app_resources["model"] = ColPaliModel() 
        # Inicializamos la base de datos
        app_resources["db"] = Database()
        print("Modelo y DB listos.")
    except Exception as e:
        logging.error(f"Error crítico al cargar recursos: {e}")
        raise e
    
    yield  # Aquí es donde la aplicación "funciona" y atiende peticiones
    
    # --- CÓDIGO AL CERRAR ---
    print("Liberando recursos...")
    if "model" in app_resources:
        app_resources["model"].close() #
    print("Recursos liberados.")

# 3. Pasamos el lifespan a la instancia de FastAPI
app = FastAPI(lifespan=lifespan)


# --- Modelos de Datos (Pydantic) ---
class SearchQuery(BaseModel):
    text: str
    limit: Optional[int] = 5

class SearchResult(BaseModel):
    page_number: int
    document_hash: str
    filename: str  # Añadimos el nombre del archivo para que el LLM pueda citarlo
    score: float
    content: str   # El texto completo de la página (limpio)
    formated_context: str # El bloque listo para el Prompt

class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]
    full_prompt_context: str # Todo el contexto de todas las páginas unido



@app.post(
    "/upload-pdfs/",
    summary="Sube varios archivos PDF para su ingestión",
    description="""
    El archivo PDF se guardar en el sistema y se procesará para extraer su contenido y metadatos.
    Calcula su hash SHA-256 para verificar si ya existe en la base de datos:
    1. Si **existe**, devuelve los datos del registro actual sin duplicar el archivo.
    2. Si **no existe**, guarda el archivo en `./data/{hash}.pdf` y crea un nuevo registro en MariaDB.

    El proceso de ingestión incluye:
    - Extracción de texto e imágenes de cada página.
    - Generación de embeddings multi-vectoriales usando el modelo ColPali.
    - Almacenamiento de los embeddings en Qdrant con metadatos asociados.
    """
)
async def upload_pdfs(files: List[UploadFile] = File(...)):
    results = []
    inicio_total = time.perf_counter()
    model = app_resources.get("model")
    if not model:
        raise HTTPException(status_code=500, detail="Modelo no disponible")

    ingestion_service = IngestionService(app_resources["db"])
    for file in files:
        inicio = time.perf_counter()
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            fin = time.perf_counter()
            logging.warning(f"Archivo {file.filename} no es un PDF. Tiempo de validación: {fin - inicio:.6f}s")
            results.append(
                {
                    "filename": file.filename,
                    "error": "El archivo no es un PDF",
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

@app.post("/search", response_model=SearchResponse)
async def search(query: SearchQuery):
    """
    Endpoint para realizar búsquedas semánticas en los documentos indexados.
    """
    model = app_resources.get("model")
    if not model:
        raise HTTPException(status_code=500, detail="Modelo no disponible")
    db = app_resources.get("db")
    if not db:
        raise HTTPException(status_code=500, detail="Base de datos no disponible")
    try:
        query_embedding = model.process_text(query.text)
        search_results = db.search_pages(query_embedding, limit=query.limit or 5) # si limit es None, se usará 5 por defecto

        final_results = []
        context_blocks = []

        for hit in search_results.points:
            p = hit.payload
            if not p:
                logging.warning(f"Resultado sin payload encontrado: {hit.id}")
                continue
            # Extraemos datos del payload
            # Nota: Asegúrate de guardar 'filename' en el payload al indexar
            document_hash = p.get("document_hash", "Documento desconocido")
            doc = db.get_document_by_hash(document_hash) if document_hash != "Documento desconocido" else None
            filename = doc.filename if doc else "Archivo desconocido"
            page_num = p.get("page_number", -1) # Si no se encuentra el número de página, se asigna -1 para indicar que es desconocido
            text_content = p.get("text", "")
            tables = p.get("tables_text", "")
            captions = p.get("figure_captions", "")

            # Creamos el bloque de contexto para esta página
            block_parts = [f"--- FUENTE: {filename} (Página {page_num}) ---\n"]

            if text_content:
                block_parts.append(f"[CONTENIDO TEXTUAL]:\n{text_content}")

            if tables:
                block_parts.append(f"[DATOS TABULARES DETECTADOS]:\n{tables}")
            
            if captions:
                # Unimos las capturas de figuras/tablas para dar contexto visual
                captions_str = "\n- ".join(captions)
                block_parts.append(f"[ILUSTRACIONES Y FIGURAS EN ESTA PÁGINA]:\n- {captions_str}")
            
            block = "\n\n".join(block_parts)
            context_blocks.append(block)

            final_results.append(SearchResult(
                page_number=page_num,
                document_hash=document_hash,
                filename=filename,
                score=hit.score,
                content=text_content,
                formated_context=block
            ))
        
        # Unimos todo en un solo string para el LLM
        full_context = "\n".join(context_blocks)
        
        return SearchResponse(
            query=query.text,
            results=final_results,
            full_prompt_context=full_context
        )
    except Exception as e:
        logging.error(f"Error en la búsqueda: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host=Config.APP_HOST, port=Config.APP_PORT)

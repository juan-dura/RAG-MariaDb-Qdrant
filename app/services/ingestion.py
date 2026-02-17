import fitz
from scipy import io
from io import BytesIO
from PIL import Image
import torch
from transformers import AutoProcessor
from colpali_engine.models import ColPali
from qdrant_client.models import PointStruct
import uuid
from app.document import Document
from app.database import Database

class IngestionService:
    """
    Service class for handling document ingestion, including
    storing metadata in MariaDB and managing vector embeddings in Qdrant.

    Methods:
        ingest_document(file_path: str) -> None:
            Ingest a document by storing its metadata in MariaDB and
            adding its embeddings to Qdrant.
    """
    def __init__(self, db: Database):
        self.db = db

    def ingest_document(self, file_path: str) -> dict:
        document = Document(file_path)

        # si el documento ya existe en la base de datos, actualizamos el path y salimos
        document_exists = self.db.document_exists(document.hash)
        if document_exists:
            print(f"Document with hash {document.hash} already exists in the database.")
            self.db.update_document_path(document.hash, document.upload_path)
            return {
                "message": "Document already exists. Path updated.",
                "document_already_exists": document_exists
            }
        else:
            # Insertar el documento y sus páginas en la base de datos
            result = self.db.insert_document(document)
            # print(f"Inserted document ID: {result['document_id']} with {result['total_pages']} pages.")

            # Crear embeddings y añadir a Qdrant
            points = []
            for p in range(document.total_pages):
                page =  document.doc.load_page(p)

                # Definir la resolución (Matrix)
                # 300 DPI es el estándar para buena calidad en RAG visual
                # El zoom por defecto es 72 DPI (300 / 72 = 4.166)
                zoom = 300 / 72
                mat = fitz.Matrix(zoom, zoom)

                # Renderizar la página como imagen
                pix = page.get_pixmap(matrix=mat)

                # Converir la imagen a un formato compatible con el procesador (PIL Image)
                image_data = pix.tobytes("png")
                image = Image.open(BytesIO(image_data)).convert("RGB")
                multivector = self.multivector(image)
                points.append(PointStruct(
                    id=str(uuid.uuid4()),
                    vector={"colbert": multivector}, # Usamos el nombre que definiste en la colección
                    payload={
                        "document_id": result['document_id'],
                        "page_number": p,
                    }
                ))

                self.db.get_qdrant_client().upsert(
                    collection_name="rag_collection",
                    points=points
                )

            return {
                "message": "Document ingested successfully.",
                "document_id": result['document_id'],
                "total_pages": result['total_pages'],
                "document_already_exists": document_exists
            }



    def multivector(self, image) -> list:
        """
        Ingest a document using Colpali for embedding and indexing.

        Args:
            image (PIL.Image): The image to ingest.
        """

        # Cargar el modelo y el procesador
        model_name = "vidore/colqwen2-v1.0"
        model = ColPali.from_pretrained(model_name, torch_dtype=torch.bfloat16, device_map="cuda")
        processor = AutoProcessor.from_pretrained(model_name)

        inputs = processor(images=image, return_tensors="pt", padding=True, truncation=True)

        # Generar embeddings
        with torch.no_grad():
            embeddings = model(**inputs).embeddings

            # ColPali devuelve un tensor (1, N, 128) o (1, N, 768) dependiendo de la versión
            # Lo convertimos a una lista de listas (formato Multi-vector de Qdrant)
            multivector = embeddings.cpu().float().numpy()[0].tolist()

        return multivector
                
# TODO CODIGO DE TEST a eliminar despues
if __name__ == "__main__":
    from app.database import Database

    db = Database()
    ingestion_service = IngestionService(db)
    test_file_path = "./docs_prueba/IBV_Memoria_ANT4HEALTH_IVACE24_V2.pdf"
    # test_file_path = "./docs_prueba/IBV_Memoria_ANT4HEALTH_IVACE24_V2.docx"  # Archivo no PDF para probar la validación
    try:
        resultado = ingestion_service.ingest_document(test_file_path)
        print(f"Ingestion result: {resultado}")
        
    except Exception as e:
        print(f"Error during ingestion: {e}")
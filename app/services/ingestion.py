from pathlib import Path

from app.classes.document import Document
from app.classes.database import Database
from app.classes.colpaliModel import ColPaliModel
from app.config import Config
from app.helpers.fill_page_number import fill_page_number

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


    def ingest_document(self, doc: Document, model: ColPaliModel) -> dict:
        """
        Ingest a document by storing its metadata in MariaDB and
        adding its embeddings to Qdrant.

        Args:
            file_path (str): The path to the document to be ingested.
        Returns:
            dict: A dictionary containing the status of the ingestion process,
                  including document ID, hash, and any relevant messages.
        Raises:
            Exception: If any error occurs during the ingestion process, an exception is raised with details.
        """
        try:
            # Verificar si el documento ya existe en MariaDB
            existing_doc = self.db.get_document_by_hash(doc.hash)
            if existing_doc:
                # Si el documento ya existe, actualizar la ruta si es necesario y retornar información
                if existing_doc.upload_path != doc.upload_path:
                    self.db.update_document_path(doc.hash, doc.upload_path)
                # Comprobar si el documento ya ha sido procesado y salir temprano si es así
                if existing_doc.indexed_in_qdrant:
                    return {
                        "status": "ya_procesado",
                        "hash": doc.hash,
                        "message": "El documento ya fue procesado anteriormente."
                    }
                
                
            else: # Si no existe, insertar nuevo registro en base de datos
                new_doc_id = self.db.insert_document(doc)

            # Procesar el documento y agregar embeddings a Qdrant
            points = []
            for n_page in range(doc.total_pages):
                page_result = doc.page_to_qdrant(n_page, model=model)
                points.append(page_result)
                image = page_result["image"]
                # Guardar la imagen de la página en config.DATA_DIR/pages con el nombre {hash}_p{n_page}.png
                image_path = Path(Config.DATA_DIR) / "pages" / f"{doc.hash}_p{fill_page_number(n_page,doc.total_pages)}.png"
                with open(image_path, "wb") as f:
                    f.write(image)

            # Agregar el punto a Qdrant
            self.db.get_qdrant_client().upsert(
                collection_name="documents",
                points=points
            )
            # Marcar el documento como indexado en Qdrant
            self.db.mark_document_indexed(doc.hash)

            return {
                "status": "ingestado",
                "hash": doc.hash,
                "message": "Documento ingresado exitosamente."
            }

        except Exception as e:
            raise Exception(f"Error durante la ingestión del documento: {str(e)}")                


#  --- TESTING ---
if __name__ == "__main__":
    from app.classes.database import Database
    test_file_path = "/home/jvdura/RAG-MariaDb-Qdrant/docs_prueba/IBV_Memoria_ANT-INFANTIL_IVACE24_V2.pdf"
    doc = Document(test_file_path)
    db = Database()
    ingestion_service = IngestionService(db)
    with ColPaliModel() as model:
        try:
            resultado = ingestion_service.ingest_document(doc, model=model)
            print(f"Ingestion result: {resultado}")
            
        except Exception as e:
            print(f"Error during ingestion: {e}")
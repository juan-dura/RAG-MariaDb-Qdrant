from typing import Union, Tuple, Any
from dataclasses import dataclass
import os
import pymysql
import logging
import torch
import json
from app.config import Config
from app.classes.document import Document
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, MultiVectorComparator, MultiVectorConfig, QueryResponse
# Importamos con alias para que VS Code esté feliz y el código sea legible
from qdrant_client.http.models.models import QueryResponse as QResponse

@dataclass
class DocumentRecord:
    """
        Data class representing a document record in the dataMariaDbbase.
    """
    id: Union[int, None]
    doc_hash: str
    filename: str
    upload_path: str
    total_pages: int
    indexed_in_qdrant: bool
    created_at: Any  # Usamos Any para el tipo de fecha, podría ser datetime o str dependiendo de cómo se maneje en la base de datos
    
    @classmethod
    def from_row(cls, data: Tuple) -> Union['DocumentRecord', None]:
        """
            Crea una instancia de DocumentRecord a partir de una tupla de datos.
        """
        if len(data) < 7:
            return None  # O lanzar una excepción si prefieres  
        return cls(
            id=data[0],
            doc_hash=data[1],
            filename=data[2],
            upload_path=data[3],
            total_pages=data[4],
            indexed_in_qdrant=bool(data[5]),
            created_at=data[6]
        )


class Database:
    """
    Database management class for RAG (Retrieval-Augmented Generation) system.
    
    Attributes:
        mariadb_connection: PyMySQL connection object for MariaDB
        mariadb_cursor: Cursor object for executing MariaDB queries
        qdrant_client: QdrantClient instance for vector database operations
    
    Methods:
        __init__(): Initialize both MariaDB and Qdrant connections
        _init_mariadb(): Initialize MariaDB connection and create tables
        _create_tables(): Create documents and pages tables in MariaDB
        _init_qdrant(): Initialize Qdrant client and create collection
        get_mariadb_connection(): Return the MariaDB connection object
        get_qdrant_client(): Return the Qdrant client instance
    
    Tables:
        documents: Stores document metadata
            - id: INT AUTO_INCREMENT PRIMARY KEY
            - doc_hash: VARCHAR(64) UNIQUE NOT NULL
            - filename: VARCHAR(255) NOT NULL
            - upload_path: VARCHAR(512) NOT NULL
            - total_pages: INT DEFAULT 0
            - indexed_in_qdrant: BOOLEAN DEFAULT FALSE
            - created_at: TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        
    Qdrant Collection:
        rag_collection: Vector collection configured with ColBERT embeddings
            - Vector size: 768 dimensions
            - Distance metric: COSINE
            - Multi-vector comparator: MAX_SIM
    """
    def __init__(self):
        self._init_mariadb()
        self._init_qdrant()
    
    # --- Metodos privados ---
    
    def _init_mariadb(self):
        # Código para inicializar la conexión a MariaDB
        try:
            self.mariadb_connection = pymysql.connect(
                host=Config.MARIADB_HOST,
                user=Config.MARIADB_USER,
                password=Config.MARIADB_PASSWORD,
                port=Config.MARIADB_PORT,
                database=Config.MARIADB_DATABASE 
            )
            self.mariadb_cursor = self.mariadb_connection.cursor()
            self._create_tables()
        except pymysql.MySQLError as e:
            print(f"Error al conectar a MariaDB: {e}")

    def _create_tables(self):
        # Crear la tabla de documentos si no existe
        self.mariadb_cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INT AUTO_INCREMENT PRIMARY KEY,
                doc_hash VARCHAR(64) UNIQUE NOT NULL,
                filename VARCHAR(255) NOT NULL,
                upload_path VARCHAR(512) NOT NULL,
                total_pages INT DEFAULT 0,
                indexed_in_qdrant BOOLEAN DEFAULT FALSE,
                metadata JSON, -- Campo para metadatos extra (autor, fechas, etiquetas, etc.)
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB
        """)

        self.mariadb_connection.commit()

    def _init_qdrant(self):
        # Código para inicializar la conexión a Qdrant
        try:
            self.qdrant_client = QdrantClient(
            host=Config.QDRANT_HOST,
            port=Config.QDRANT_PORT)
        except Exception as e:
            print(f"Error al conectar a Qdrant: {e}")
        # Crear la colección si no existe
        collection_name = Config.QDRANT_COLLECTION
        try:
            self.qdrant_client.get_collection(collection_name)
        except:
            self.qdrant_client.create_collection(
                collection_name=collection_name,
                vectors_config={
                    "colbert" : VectorParams(
                        size=128, # El tamaño de los embeddings de ColPali es 128 dimensiones
                        distance=Distance.COSINE,
                        multivector_config=MultiVectorConfig(
                            comparator=MultiVectorComparator.MAX_SIM
                        )
                    )
                }
            )
    
    # --- Metodos publicos ---
                                                                                                                                                                                  
    def get_mariadb_connection(self):
        return self.mariadb_connection
    
    def get_qdrant_client(self):
        return self.qdrant_client

    def get_document_by_hash(self, doc_hash: str) -> Union[DocumentRecord, None]:
        """
        Check if a document with the given hash exists in the documents table.

        Args:
            doc_hash (str): The SHA-256 hash of the document to check.

        Returns:
            DocumentRecord: The document record if it exists, False otherwise.
        """
        query = "SELECT * FROM documents WHERE doc_hash = %s"
        self.mariadb_cursor.execute(query, (doc_hash,))
        result = self.mariadb_cursor.fetchone()
        doc_record = DocumentRecord.from_row(result) if result else None
        return doc_record if doc_record else None
        
    
    def update_document_path(self, doc_hash: str, new_path: str) -> None:
        """
        Update the upload_path of a document identified by its hash.

        Args:
            doc_hash (str): The SHA-256 hash of the document to update.
            new_path (str): The new upload path to set.
        """
        query = "UPDATE documents SET upload_path = %s WHERE doc_hash = %s"
        self.mariadb_cursor.execute(query, (new_path, doc_hash))
        self.mariadb_connection.commit()

    def mark_document_indexed(self, doc_hash: str) -> None:
        """
        Mark a document as indexed in Qdrant by setting indexed_in_qdrant to True.

        Args:
            doc_hash (str): The SHA-256 hash of the document to update.
        """
        query = "UPDATE documents SET indexed_in_qdrant = TRUE WHERE doc_hash = %s"
        self.mariadb_cursor.execute(query, (doc_hash,))
        self.mariadb_connection.commit()
        
    def insert_document(self, document: Document) -> dict:
        """
        Inserts a new document and its pages into the database.
        This method adds a new record to the `documents` table using the provided `Document` object,
        then inserts each page of the document into the `pages` table. If a page already exists for the
        given document and page number, its content is updated.
        Args:
            document (Document): The Document object to insert, containing metadata and page content.
        Returns:
            dict: A dictionary with the inserted document's ID (`document_id`) and the total number of pages (`total_pages`).
        Raises:
            Exception: If any error occurs during the insertion, the transaction is rolled back and the exception is raised.
        """

        try:
            with self.mariadb_connection.cursor() as cursor:
                doc_hash = document.hash
                upload_path = document.upload_path
                filename = os.path.basename(upload_path)
                total_pages = document.total_pages
                metadata_json = json.dumps(document.metadata) if document.metadata else None

                # Insertar el documento en la tabla documents
                query = """
                    INSERT INTO documents (doc_hash, filename, upload_path, total_pages, metadata)
                    VALUES (%s, %s, %s, %s, %s)
                """
                cursor.execute(query, (doc_hash, filename, upload_path, total_pages, metadata_json))
                self.mariadb_connection.commit()
                return {
                    "document_id": cursor.lastrowid,
                    "total_pages": total_pages
                }
            
        except Exception as e:
            self.mariadb_connection.rollback() # Si ocurre un error, revertimos la transacción para mantener la integridad de la base de datos
            logging.error(f"Error inserting document: {e}")
            raise e
        
    def search_pages(self, query_embedding: torch.Tensor, limit: int = 5) -> QResponse:
        """
        Realiza una búsqueda en Qdrant utilizando un embedding de consulta y devuelve los resultados más relevantes.
        Args:
            query_embedding (torch.Tensor): El embedding de consulta generado por el modelo ColPali.
            limit (int): El número máximo de resultados a devolver.
        Returns:
            QueryResponse: La respuesta de la consulta con los resultados encontrados.
        """
        # 1. Preparar el vector para Qdrant
        # El modelo devuelve un tensor [1, tokens, dim]. 
        # Debemos quitar la dimensión del batch (squeeze), asegurar float32 y convertir a lista.
        query_multivector = query_embedding.squeeze(0).cpu().float().numpy().tolist()

        # 2. Ejecutar la búsqueda en Qdrant
        # El comparador MAX_SIM configurado en _init_qdrant hará el resto
        search_result = self.qdrant_client.query_points(
            collection_name=Config.QDRANT_COLLECTION,
            query=query_multivector,
            using="colbert",  # Debe coincidir con la clave definida en _init_qdrant
            with_payload=True,
            limit=limit
        )

        return search_result
    
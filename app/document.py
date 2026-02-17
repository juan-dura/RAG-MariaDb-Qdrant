import os
import hashlib
import fitz  # PyMuPDF

class Document:
    def __init__(self, upload_path: str):
        
        self._validate_path(upload_path)
       
        self.upload_path = os.path.abspath(upload_path)

        self.hash = self._generate_file_hash()

        self.doc = fitz.open(self.upload_path)

        self.total_pages = self.doc.page_count
        
        self.metadata = self.doc.metadata

    # --- Metodos privados ---
    def _validate_path(self, path: str):
        if not path.lower().endswith('.pdf'):
            raise ValueError(f"Error: Solo se admiten archivos PDF.")
        if not os.path.exists(path):
            raise FileNotFoundError(f"Error: La ruta '{path}' no existe.")
        if not os.path.isfile(path):
            raise ValueError(f"Error: '{path}' es un directorio.")
        if os.path.getsize(path) == 0:
            raise ValueError(f"Error: El archivo '{path}' está vacío.")
        if not os.access(path, os.R_OK):
            raise PermissionError(f"Error: Sin permisos de lectura en '{path}'.")

    def _generate_file_hash(self) -> str:
        sha256_hash = hashlib.sha256() 
        with open(self.upload_path, "rb") as f:
            for byte_block in iter(lambda: f.read(65536), b""): # Leer en bloques de 64KB
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    # --- Metodos publicos ---
    def get_page_content(self, page_number: int) -> str:
        """Devuelve el contenido de una página específica del documento."""
        if page_number < 0 or page_number >= self.total_pages:
            raise IndexError("Número de página fuera de rango.")
        text = self.doc[page_number].get_text()
        return str(text)
    
    def close(self):
        """Libera el archivo PDF."""
        if self.doc:
            self.doc.close()

    # --- Metodos de contexto ---
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        if exc_type:
           print(f"LOG: Error procesando {self.upload_path}: {exc_val}")

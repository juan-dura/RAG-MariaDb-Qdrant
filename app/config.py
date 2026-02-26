import logging
import os
from dotenv import load_dotenv

# Configuración de logging para toda la aplicación
logging.basicConfig(
    level=logging.WARNING, # Guardar solo advertencias y errores en el log, no los INFO que se muestran en pantalla
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("rag_system.log"), # Guarda en archivo
        logging.StreamHandler()                # Muestra en pantalla
    ],
    force=True  # Sobrescribe la configuración de otras librerías
)


# Detect the environment (development, production, etc.) and load the corresponding .env file
env = os.getenv("APP_ENV", "example") # Default to "example" if APP_ENV is not set
env_file = f".env.{env}" # e.g., .env.development, .env.production
if os.path.exists(env_file):
    load_dotenv(env_file)
else:
    print(f"Warning: {env_file} not found. Falling back to default .env file.")
    load_dotenv()

class Config:
    # Configuración de la base de datos y Qdrant
    MARIADB_HOST = os.getenv("MARIADB_HOST", "localhost")
    MARIADB_USER = os.getenv("MARIADB_USER", "root")
    MARIADB_PORT = int(os.getenv("MARIADB_PORT", 3306))
    MARIADB_PASSWORD = os.getenv("MARIADB_PASSWORD", "")
    MARIADB_DATABASE = os.getenv("MARIADB_DATABASE", "test_db")
    QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
    QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
    QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "rag_collection") # Nombre de la colección en Qdrant

    # Configuración de la aplicación
    APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT = int(os.getenv("APP_PORT", 8000))
    DATA_DIR = os.getenv("DATA_DIR", "./data") # Directorio donde se guardarán los PDFs finales
    TEMP_DIR = os.getenv("TEMP_DIR", "./temp") # Directorio temporal para archivos subidos antes de procesarlos

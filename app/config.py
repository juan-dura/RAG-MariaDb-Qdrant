import logging
import os
from dotenv import load_dotenv

# Configuración de logging para toda la aplicación
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("rag_system.log"), # Guarda en archivo
        logging.StreamHandler()                # Muestra en pantalla
    ]
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
    MARIADB_HOST = os.getenv("MARIADB_HOST", "localhost")
    MARIADB_USER = os.getenv("MARIADB_USER", "root")
    MARIADB_PORT = int(os.getenv("MARIADB_PORT", 3306))
    MARIADB_PASSWORD = os.getenv("MARIADB_PASSWORD", "")
    MARIADB_DATABASE = os.getenv("MARIADB_DATABASE", "test_db")
    QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
    QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
    DATA_DIR = os.getenv("DATA_DIR", "./data") # Directorio donde se guardarán los PDFs finales
    TEMP_DIR = os.getenv("TEMP_DIR", "./temp") # Directorio temporal para archivos subidos antes de procesarlos

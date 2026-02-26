# RAG MariaDB Qdrant

Un sistema **RAG (Retrieval-Augmented Generation)** que crea una base de datos de conocimiento mediante embeddings multivectoriales, capaz de recuperar información contextual de documentos para enriquecer aplicaciones con IA generativa.

## 📋 Descripción

Este proyecto implementa un sistema completo de Generación Aumentada por Recuperación (RAG) que:

- **Ingiere documentos PDF** y los procesa para extraer texto e imágenes
- **Genera embeddings multivectoriales** usando el modelo [ColPali](https://github.com/ColPaliEngine/colpali)
- **Almacena los embeddings** en una base de datos vectorial ([Qdrant](https://qdrant.tech/))
- **Mantiene metadatos** de documentos en una base de datos relacional ([MariaDB](https://mariadb.org/))
- **Proporciona búsqueda semántica** para recuperar contexto relevante
- **Genera prompts contextualizados** listos para ser utilizados por modelos de lenguaje

## 🛠️ Tecnología

### Stack Principal
- **Backend**: [FastAPI](https://fastapi.tiangolo.com/) con [Uvicorn](https://www.uvicorn.org/)
- **Contenedores**: [Docker](https://www.docker.com/) y [Docker Compose](https://docs.docker.com/compose/)
- **Base de Datos Relacional**: MariaDB 11.8
- **Base de Datos Vectorial**: Qdrant
- **Modelo de IA**: ColPali (embeddings multivectoriales)

### Dependencias Python Principales
- `colpali-engine` - Generación de embeddings multivectoriales
- `fastapi` - Framework web asincrónico
- `pymupdf` - Extracción de contenido de PDFs
- `pymysql` - Cliente MySQL/MariaDB
- `qdrant-client` - Cliente para Qdrant
- `scipy` - Cálculos científicos
- `uvicorn` - Servidor ASGI
- `python-multipart` - Soporte para formularios multipartes

## 🚀 Instalación y Configuración

### Requisitos Previos
- Python 3.13 o superior
- Docker y Docker Compose
- [uv](https://github.com/astral-sh/uv) (gestor de dependencias y entornos Python)

### Paso 1: Clonar el Repositorio
```bash
git clone <repositorio>
cd RAG-MariaDb-Qdrant
```

### Paso 2: Configurar las Variables de Entorno
Crea un archivo `.env.example` o `.env` con las siguientes variables:

```env
# MariaDB
MARIADB_HOST=localhost
MARIADB_USER=user
MARIADB_PORT=3306
MARIADB_PASSWORD=password
MARIADB_DATABASE=rag_db

# Qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=rag_collection

# Aplicación
APP_HOST=0.0.0.0
APP_PORT=8000
DATA_DIR=./data
TEMP_DIR=./temp
```

### Paso 3: Crear el Entorno Virtual
```bash
uv venv
```

### Paso 4: Instalar Dependencias

**Opción A: Instalar todas las dependencias (producción + desarrollo)**
```bash
uv sync
```

**Opción B: Instalar solo dependencias de producción**
```bash
uv sync --no-dev
```

### Paso 5: Ejecutar la Aplicación
```bash
chmod +x run.sh
./run.sh
```

Este script:
1. Inicia los servicios Docker (MariaDB y Qdrant)
2. Activa el entorno virtual
3. Instala las dependencias necesarias
4. Crea las carpetas requeridas (`data/` y `temp/`)
5. Inicia el servidor FastAPI

## 📁 Estructura del Proyecto

```
RAG-MariaDb-Qdrant/
├── app/                           # Código fuente de la aplicación
│   ├── main.py                    # Punto de entrada y definición de endpoints
│   ├── config.py                  # Configuración centralizada
│   ├── classes/                   # Clases principales
│   │   ├── colpaliModel.py        # Gestor del modelo ColPali
│   │   ├── database.py            # Gestor de conexión con MariaDB
│   │   └── document.py            # Clase para procesar documentos PDF
│   ├── services/                  # Servicios de negocio
│   │   └── ingestion.py           # Servicio de ingestión de documentos
│   └── helpers/                   # Funciones auxiliares
│       ├── build_llm_context.py   # Construcción de contexto para LLMs
│       └── fill_page_number.py    # Gestión de números de página
├── data/                          # Almacenamiento de PDFs procesados
├── temp/                          # Almacenamiento temporal durante el procesamiento
├── docker-compose.yml             # Configuración de servicios Docker
├── pyproject.toml                 # Definición de dependencias y metadatos
├── .env.example                   # Plantilla de variables de entorno
├── .gitignore                     # Configuración de Git
└── run.sh                         # Script de inicio rápido
```

## 🔌 API Endpoints

### 1. Subir PDFs para Ingestión
**`POST /upload-pdfs/`**

Permite subir uno o múltiples archivos PDF para ser procesados y almacenados en la base de datos de conocimiento.

**Funcionalidades:**
- Validación de archivos PDF
- Cálculo de hash SHA-256 para detectar duplicados
- Extracción de texto e imágenes
- Generación de embeddings multivectoriales
- Almacenamiento en MariaDB y Qdrant

**Respuesta:**
```json
{
  "total_processing_time": "45.123456",
  "results": [
    {
      "filename": "documento.pdf",
      "hash": "abc123...",
      "pages": 25,
      "status": "success",
      "processing_time": "45.123456"
    }
  ]
}
```

### 2. Búsqueda Semántica
**`POST /search`**

Realiza búsquedas semánticas en los documentos indexados y retorna contexto relevante listo para ser usado en prompts.

**Parámetros:**
```json
{
  "text": "Tu consulta aquí",
  "limit": 5
}
```

**Respuesta:**
```json
{
  "query": "Tu consulta aquí",
  "results": [
    {
      "page_number": 3,
      "document_hash": "abc123...",
      "filename": "documento.pdf",
      "score": 0.95,
      "content": "Contenido de la página...",
      "formated_context": "Contexto formateado para el prompt..."
    }
  ],
  "full_prompt_context": "Todo el contexto unido para usar en el LLM..."
}
```

**Documentación interactiva:** Accede a `http://localhost:8000/docs` cuando la aplicación esté en ejecución.

## 💾 Gestión de Datos

### Almacenamiento de Documentos
Los PDFs procesados se guardan en `./data/` con el nombre `{hash_sha256}.pdf`, lo que permite:
- Evitar duplicados mediante hash
- Recuperar documentos originales cuando sea necesario
- Mantener un histórico completo de ingestión

### Almacenamiento Temporal
Los archivos subidos se guardan temporalmente en `./temp/` y se eliminan después del procesamiento.

### Bases de Datos

**MariaDB**
- Almacena metadatos de documentos (nombre, hash, fecha, número de páginas)
- Gestiona las referencias entre documentos y sus páginas

**Qdrant**
- Almacena los embeddings multivectoriales de cada página
- Permite búsquedas semánticas rápidas y precisas
- Mantiene metadatos de contexto para cada embedding

## 🔧 Configuración Avanzada

### Variables de Entorno Personalizadas
Puedes personalizar la configuración editando archivos `.env.{ambiente}`:

```bash
APP_ENV=development  # Cargar .env.development
APP_ENV=production   # Cargar .env.production
```

### Logging
La aplicación genera logs en `rag_system.log` con:
- Nivel WARNING para eventos importantes
- Timestamps y niveles de severidad
- Salida simultánea en archivo y consola

### Docker
Los servicios se ejecutan en una red interna (`app_network`):

- **MariaDB**: Puerto 3306, volumen persistente `mariadb_data`
- **Qdrant**: Puerto 6333, volumen persistente `qdrant_data`

## 📊 Flujo de Procesamiento

1. **Upload**: Usuario sube PDF mediante API
2. **Validación**: Se verifica que sea PDF válido
3. **Hash**: Se calcula SHA-256 del documento
4. **Deduplicación**: Se verifica si ya existe en la BD
5. **Extracción**: Se extrae texto e imágenes de cada página
6. **Vectorización**: Se generan embeddings con ColPali
7. **Almacenamiento**: Se guardan embeddings en Qdrant y metadatos en MariaDB
8. **Persistencia**: Se copia PDF a `./data/{hash}.pdf`

## 🔍 Búsqueda y Generación de Contexto

1. **Query**: Usuario realiza búsqueda con texto
2. **Vectorización**: Se convierte la consulta a embedding
3. **Búsqueda Vectorial**: Se buscan documentos similares en Qdrant
4. **Ranking**: Se ordenan resultados por similitud
5. **Formateado**: Se preparan bloques de contexto para el LLM
6. **Unificación**: Se crea un prompt unificado con todo el contexto

## 🐛 Troubleshooting

### Error: "No se encontró la carpeta .venv"
```bash
uv venv
source .venv/bin/activate
```

### Error: "Conexión a MariaDB rechazada"
Verifica que Docker esté ejecutando:
```bash
docker compose ps
```

### Error: "Qdrant no disponible"
Espera a que Qdrant inicie completamente (puede tardar 10-15 segundos):
```bash
docker compose logs qdrant
```

## 📝 Notas de Desarrollo

- El proyecto utiliza **type hints** en Python 3.13+
- Las dependencias de desarrollo incluyen `debugpy` para depuración remota
- Se recomienda usar `uv` para mejor rendimiento que `pip`
- Los logs muestran solo advertencias en archivo para mantener el archivo ligero

## 📄 Licencia

Por definir.

## 👤 Juanvi Durá (juan.dura@ibv.org)

Desarrollado como sistema RAG integrado con MariaDB y Qdrant.

---

**¿Necesitas ayuda?** Consulta la documentación interactiva en `http://localhost:8000/docs` cuando la aplicación esté en ejecución.

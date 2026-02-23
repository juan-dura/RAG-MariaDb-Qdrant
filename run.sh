#!/bin/bash

# 1. Activar el entorno virtual de uv
if [ -d ".venv" ]; then
    source .venv/bin/activate
    # Opcional: Sincronizar dependencias si has modificado el pyproject.toml
    uv sync
else
    echo "ERROR: No se encontró la carpeta .venv. Ejecuta 'uv venv' primero."
    exit 1
fi

# 2. Crear carpetas necesarias si no existen
mkdir -p data temp

# 3. Lanzar el servidor
echo "[*] Arrancando API RAG en http://localhost:8000"
echo "[*] Documentación disponible en http://localhost:8000/docs"

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
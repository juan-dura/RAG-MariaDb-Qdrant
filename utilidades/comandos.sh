# Comando de terminal útiles para verificar los contenedores Docker

# Para ver si MariaDB (3306) o Qdrant (6333) ya están ocupados por otro programa.
# Si no sale nada: Los puertos están libres.
ss -tulpn | grep -E '3306|6333'

# Arracncar docker-compose
docker compose -f ./docker-compose.yml up -d

# Ver los contenedores en ejecución
docker ps

# Ver los logs (por si algo falló)
docker compose logs -f

# Reiniciar docker de cero con borrado de volúmenes y datos
docker compose down -v
docker compose up -d

# levantar las apis con uvicorn
uvicorn main:app --reload --host 0.0.0.0 --port 8000
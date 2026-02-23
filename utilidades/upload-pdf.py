import requests

url = "http://localhost:8000/upload-pdf/"
file_path = "/home/jvdura/RAG-MariaDb-Qdrant/docs_prueba/IBV_Memoria_ANT4HEALTH_IVACE24_V2.pdf"

with open(file_path, "rb") as f:
    files = {"file": (file_path, f, "application/pdf")}
    response = requests.post(url, files=files)

print(response.json())

import requests
import os

url = "http://localhost:8000/upload-pdfs/"
folder_path = "/home/jvdura/RAG-MariaDb-Qdrant/docs_prueba/"

# Listar todos los archivos PDF en folder_path
pdf_files = [
	os.path.join(folder_path, f)
	for f in os.listdir(folder_path)
	if f.lower().endswith(".pdf") and os.path.isfile(os.path.join(folder_path, f))
]

if not pdf_files:
	print("No se encontraron archivos PDF en la carpeta.")
	exit(1)

# Preparar los archivos para multipart/form-data
files = [("files", (os.path.basename(f), open(f, "rb"), "application/pdf")) for f in pdf_files]

try:
	response = requests.post(url, files=files)
	print("Status code:", response.status_code)
	print("Respuesta:", response.text)
finally:
	# Cerrar todos los archivos abiertos
	for _, (filename, fileobj, _) in files:
		fileobj.close()


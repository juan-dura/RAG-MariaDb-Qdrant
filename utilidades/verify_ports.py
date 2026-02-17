# Utilidad para verificar si los puertos de MariaDB y Qdrant están accesibles.
import socket

def check_port(port, service_name):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        result = s.connect_ex(('127.0.0.1', port))
        if result == 0:
            print(f"✅ {service_name} en puerto {port} está ACCESIBLE.")
        else:
            print(f"❌ {service_name} en puerto {port} NO responde.")

check_port(3306, "MariaDB")
check_port(6333, "Qdrant")
import logging
from PIL.Image import Image
from colpali_engine.models import ColPali
import torch
from transformers import AutoProcessor

class ColPaliModel:
    def __init__(self, model_name: str = "vidore/colpali-v1.3"):
        self.model_name = model_name
        self.device = self._get_optimal_device() # Determina el dispositivo óptimo para procesamiento (GPU si está disponible, de lo contrario CPU)
        self.model = ColPali.from_pretrained(
            self.model_name,
            dtype=torch.bfloat16 if self.device == "cuda" else torch.float32,
            device_map=self.device) # Cargamos el modelo una sola vez en el dispositivo óptimo
        self.processor = AutoProcessor.from_pretrained(self.model_name) # Cargamos el procesador una sola vez

    # --- Metodos privados ---
    def _get_optimal_device(self):
        if torch.cuda.is_available():
            return "cuda"
        
        try:
            # Intentamos una operación minúscula en GPU para validar el driver
            torch.cuda.current_device()
            torch.tensor([0.0]).cuda() 
            return "cuda"
        except Exception as e:
            logging.warning(f"GPU detectada pero no funcional (posible error de driver): {e}")
            return "cpu"

    # --- Metodos publicos ---   
    def close(self):
        if self.model:
            del self.model
        if self.processor:
            del self.processor
        if self.device == "cuda":
            torch.cuda.empty_cache() # Libera memoria de video
    
    def process_page(self, image: Image) -> torch.Tensor:
        """
        Procesa una página combinando su imagen y texto para generar un embedding multi-vectorial.
        Utiliza el modelo ColPali para extraer características visuales y textuales, y las combina
        en un solo vector de alta dimensión que representa la información completa de la página.
        Args:
            image (PIL.Image): La imagen renderizada de la página PDF.
        Returns:
            torch.Tensor: Un tensor que representa el embedding multi-vectorial de la página.
        """
        inputs = self.processor(images=image, return_tensors="pt", padding=True, truncation=True).to(self.model.device)
        with torch.no_grad():
            embeddings = self.model(**inputs)
        return embeddings.cpu() # Devuelve el embedding en CPU para su posterior uso

    # --- Metodos de contexto ---
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        if exc_type:
           logging.error(f"Error {self.model_name}: {exc_val}")
        return False  # No suprime excepciones, permite que se propaguen

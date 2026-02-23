import logging
import os
import hashlib
import re
from collections import Counter
import uuid
from io import BytesIO

import fitz  # PyMuPDF
from PIL import Image
from qdrant_client.models import PointStruct

from app.classes.colpaliModel import ColPaliModel
from app.helpers.fill_page_number import fill_page_number

# --- Heurísticas para captions/paginación (Word -> PDF) ---
"""
La mayoría de los PDFs del IBV son genereado desde documentos de Word
Dado que la Word suele generar headers/footers repetitivos y captions con formatos típicos,
estas heurísticas buscan filtrar esos elementos para obtener un texto más limpio y relevante para el contexto LLM.
Estas heurísticas ayudan a filtrar headers/footers típicos de Word y a detectar captions de figuras/tablas.
Detecta captions típicos (Figura/Table X: ...) y paginación (Página X de Y) para filtrar de headers/footers.
"""
_CAPTION_RE = re.compile(r"^\s*(Figura|Fig\.|Ilustración|Ilus\.|Table|Tabla)\s*\d+(\.\d+)*\s*[:\.\-–]", re.IGNORECASE)
_PAGE_NUM_RE = re.compile(r"^\s*(p(á|a)gina|page)?\s*\d+\s*(de|/)\s*\d+\s*$", re.IGNORECASE)


def _norm_ws(s: str) -> str:
    """
    Normalize whitespace in a string by collapsing multiple consecutive whitespace 
    characters into a single space and removing leading/trailing whitespace.
    
    Args:
        s (str): The input string to normalize. Can be None or empty.
    
    Returns:
        str: The normalized string with:
            - All consecutive whitespace characters (spaces, tabs, newlines, etc.) 
              replaced with a single space
            - Leading and trailing whitespace removed
    
    Example:
        >>> _norm_ws("hello   world")
        'hello world'
        >>> _norm_ws("  text\n\twith\t  spaces  ")
        'text with spaces'
        >>> _norm_ws(None)
        ''
    """
    return re.sub(r"\s+", " ", (s or "")).strip()


class Document:
    def __init__(self, upload_path: str):
        self._validate_path(upload_path)

        self.upload_path = os.path.abspath(upload_path)
        self.hash = self._generate_file_hash()

        self.doc = fitz.open(self.upload_path)
        self.total_pages = self.doc.page_count
        self.metadata = self.doc.metadata

        # Cache para firmas header/footer (se calcula bajo demanda)
        self._hf_sigs = None

    # --- Métodos privados ---
    def _validate_path(self, path: str):
        if not path.lower().endswith(".pdf"):
            raise ValueError("Error: Solo se admiten archivos PDF.")
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
            for byte_block in iter(lambda: f.read(65536), b""):  # 64KB
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _compute_header_footer_signatures(self, sample_pages: int = 12):
        """
        Detecta textos repetidos en la franja superior/inferior (header/footer típicos de Word).
        Devuelve (header_sigs, footer_sigs) como sets en minúsculas.
        """
        n = min(self.total_pages, sample_pages)
        if n <= 1:
            return set(), set()

        top_texts = []
        bottom_texts = []

        for i in range(n):
            page = self.doc[i]
            h = page.rect.height

            # blocks: (x0, y0, x1, y1, text, block_no, block_type)
            for (x0, y0, x1, y1, t, *_rest) in page.get_text("blocks"):
                txt = _norm_ws(t).lower()
                if not txt:
                    continue

                # franjas 10% arriba/abajo
                if y1 <= 0.10 * h:
                    top_texts.append(txt)
                if y0 >= 0.90 * h:
                    bottom_texts.append(txt)

        # Umbral: aparece en >= 30% de las páginas muestreadas (min 2)
        thr = max(2, int(0.30 * n))
        header_sigs = {k for k, c in Counter(top_texts).items() if c >= thr}
        footer_sigs = {k for k, c in Counter(bottom_texts).items() if c >= thr}
        return header_sigs, footer_sigs

    def _extract_payload_text(self, page: fitz.Page) -> dict:
        """
        Extracción layout-aware para PDFs Word (sin columnas).
        Retorna:
          - text: texto limpio (ordenado por bloques)
          - blocks: lista de bloques con bbox y kind (text/caption/table_like)
          - tables_text: candidatos tabulares linealizados
          - figure_captions: captions detectados
        """
        if self._hf_sigs is None:
            self._hf_sigs = self._compute_header_footer_signatures(sample_pages=12)
        header_sigs, footer_sigs = self._hf_sigs

        h = page.rect.height
        blocks_out = []
        captions = []
        table_like = []

        for (x0, y0, x1, y1, t, *_rest) in page.get_text("blocks"):
            txt = _norm_ws(t)
            if not txt:
                continue

            low = txt.lower()
            is_top = (y1 <= 0.10 * h)
            is_bottom = (y0 >= 0.90 * h)

            # Filtra headers/footers repetidos y paginación típica
            if is_top and low in header_sigs:
                continue
            if is_bottom and (low in footer_sigs or _PAGE_NUM_RE.match(txt)):
                continue

            # Captions (Figura/Tabla/Table X: ...)
            if _CAPTION_RE.match(txt) and len(txt) <= 300:
                captions.append(txt)
                blocks_out.append({"bbox": [x0, y0, x1, y1], "text": txt, "kind": "caption"})
                continue

            # Heurística simple de tabla:
            # - tabs o pipes, o muchas dobles separaciones
            looks_tabular = ("\t" in txt) or ("|" in txt) or (txt.count("  ") >= 2)
            if looks_tabular:
                table_like.append(txt)
                blocks_out.append({"bbox": [x0, y0, x1, y1], "text": txt, "kind": "table_like"})
            else:
                blocks_out.append({"bbox": [x0, y0, x1, y1], "text": txt, "kind": "text"})

        # Sin columnas: ordenar por y0, luego x0 suele ir bien
        blocks_out.sort(key=lambda b: (b["bbox"][1], b["bbox"][0]))

        # Construir text “LLM-friendly” evitando duplicados consecutivos
        parts = []
        last = None
        for b in blocks_out:
            if b["text"] == last:
                continue
            last = b["text"]
            parts.append(b["text"])

        text_clean = "\n\n".join(parts).strip()

        return {
            "text": text_clean,
            "blocks": blocks_out,
            "tables_text": "\n".join(table_like).strip(),
            "figure_captions": captions,
        }

    # --- Métodos públicos ---
    def page_to_qdrant(self, page_number: int, model: ColPaliModel) -> dict:
        """
        Convierte una página PDF a un PointStruct de Qdrant con embedding multi-vector (ColPali)
        y payload textual layout-aware (mejor que page.get_text() plano).

        Devuelve:
          - point_struct: PointStruct listo para upsert en Qdrant
          - image: bytes PNG de la página renderizada
        """
        if page_number < 0 or page_number >= self.total_pages:
            raise IndexError("Número de página fuera de rango.")

        page = self.doc[page_number]

        # --- NUEVO: extracción de texto robusta para Word->PDF ---
        extracted = self._extract_payload_text(page)

        # Render 300 DPI
        zoom = 300 / 72
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)

        image_data = pix.tobytes("png")
        image = Image.open(BytesIO(image_data)).convert("RGB")

        # Embedding ColPali
        embeddings = model.process_page(image)
        multivector = embeddings.cpu().float().numpy()[0].tolist()

        result = PointStruct(
            id=str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{self.hash}_{fill_page_number(page_number, self.total_pages)}")),
            vector={"colbert": multivector},
            payload={
                "document_hash": self.hash,
                "page_number": page_number,

                # Texto para contexto LLM (limpio y mejor ordenado)
                "text": extracted["text"],

                # Extra opcional (muy útil en RAG de informes)
                "blocks": extracted["blocks"],
                "tables_text": extracted["tables_text"],
                "figure_captions": extracted["figure_captions"],

                "metadata": self.metadata,
                "device_used": model.device,
            },
        )

        return {
            "point_struct": result,
            "image": image_data,
        }

    def close(self):
        """Libera el archivo PDF."""
        if self.doc:
            self.doc.close()

    # --- Métodos de contexto ---
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        if exc_type:
            logging.error(f"Error procesando {self.upload_path}: {exc_val}")
        return False  # no suprime excepciones


# --- TESTING ---
if __name__ == "__main__":
    test_path = "/home/jvdura/RAG-MariaDb-Qdrant/docs_prueba/IBV_Memoria_ANT-INFANTIL_IVACE24_V2.pdf"
    try:
        with ColPaliModel() as model:
            with Document(test_path) as doc:
                print(f"Hash del documento: {doc.hash}")
                print(f"Número total de páginas: {doc.total_pages}")
                print(f"Metadatos: {doc.metadata}")
                page_result = doc.page_to_qdrant(0, model)

                print(f"ID del PointStruct: {page_result['point_struct'].id}")
                payload = page_result["point_struct"].payload
                print(f"Payload keys: {list(payload.keys())}")
                print(f"Text (primeros 400 chars): {payload['text'][:400]}")
                print(f"Captions: {payload['figure_captions'][:3]}")
    except Exception as e:
        print(f"Error durante el procesamiento del documento: {e}")
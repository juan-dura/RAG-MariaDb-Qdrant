import re
from typing import Dict, Any, List

# Palabras clave (ES/EN) para decidir si priorizar tablas/números o figuras
_NUMERIC_HINTS = re.compile(
    r"\b("
    r"presupuesto|budget|coste|costo|cost|importe|amount|total|subtotal|"
    r"euros?|€|usd|\$|"
    r"precio|price|tarifa|fee|"
    r"n[uú]mero|number|valor|value|"
    r"porcentaje|percent|%|"
    r"media|average|promedio|"
    r"ratio|tasa|rate|"
    r"incremento|decremento|variaci[oó]n|change|"
    r"comparar|compare|"
    r"202\d|203\d"
    r")\b",
    re.IGNORECASE
)

_FIGURE_HINTS = re.compile(
    r"\b("
    r"figura|fig\.|figure|gr[aá]fico|grafico|chart|plot|"
    r"imagen|image|capt(ion|i[oó]n)|"
    r"diagrama|diagram|"
    r"esquema|schema"
    r")\b",
    re.IGNORECASE
)

_TABLE_HINTS = re.compile(
    r"\b("
    r"tabla|table|"
    r"cuadro|"
    r"matriz|matrix"
    r")\b",
    re.IGNORECASE
)

_HAS_NUMBER = re.compile(r"\d")


def _is_numeric_question(q: str) -> bool:
    q = q or ""
    return bool(_NUMERIC_HINTS.search(q) or _HAS_NUMBER.search(q))


def _wants_figures(q: str) -> bool:
    q = q or ""
    return bool(_FIGURE_HINTS.search(q))


def _wants_tables(q: str) -> bool:
    q = q or ""
    return bool(_TABLE_HINTS.search(q) or _is_numeric_question(q))


def _clip(text: str, max_chars: int) -> str:
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    # recorte suave en límite de frase / salto
    cut = text.rfind("\n", 0, max_chars)
    if cut < int(max_chars * 0.6):
        cut = text.rfind(". ", 0, max_chars)
    if cut < int(max_chars * 0.6):
        cut = max_chars
    return text[:cut].rstrip() + "…"


def build_llm_context(payload: Dict[str, Any], question: str,
                      max_chars: int = 9000,
                      max_table_chars: int = 3500,
                      max_caption_chars: int = 1200,
                      max_text_chars: int = 6500) -> str:
    """
    Construye un contexto simple a partir del payload de Qdrant.
    Decide automáticamente si priorizar tablas/captions según la pregunta (ES/EN).
    Sin LLM extra, solo heurísticas.

    Espera keys típicas:
      - payload["text"] (texto limpio)
      - payload["tables_text"] (tablas linealizadas)
      - payload["figure_captions"] (lista de captions)
      - payload["page_number"], payload["document_hash"] (opcionales)
      - payload["table_weirdness"] (opcional)
    """
    question = (question or "").strip()

    text = (payload.get("text") or "").strip()
    tables_text = (payload.get("tables_text") or "").strip()
    captions_list: List[str] = payload.get("figure_captions") or []
    captions = "\n".join([c.strip() for c in captions_list if str(c).strip()]).strip()

    page_no = payload.get("page_number", None)
    doc_hash = payload.get("document_hash", None)
    weird = payload.get("table_weirdness", None)

    wants_tables = _wants_tables(question)
    wants_figures = _wants_figures(question)

    # Si el score sugiere tabla problemática, aún más razón para priorizar tablas_text (si existe)
    # (porque suele venir de extractor mejor / o al menos es el contenido numérico concentrado)
    if isinstance(weird, (int, float)) and weird >= 0.6:
        wants_tables = True

    # Orden de secciones según la intención
    sections = []

    # Encabezado corto de trazabilidad (opcional)
    meta_bits = []
    if page_no is not None:
        meta_bits.append(f"Página: {page_no}")
    if doc_hash:
        meta_bits.append(f"Doc: {str(doc_hash)[:12]}")
    if meta_bits:
        sections.append("[" + " | ".join(meta_bits) + "]")

    # Prioridad:
    # - Si piden cifras/tablas: TABLAS -> CAPTIONS -> TEXTO
    # - Si piden figuras: CAPTIONS -> TEXTO (+ TABLAS si la pregunta también es numérica)
    # - Si general: TEXTO -> CAPTIONS -> TABLAS (si hay)
    if wants_figures and not wants_tables:
        if captions:
            sections.append("FIGURAS / CAPTIONS:\n" + _clip(captions, max_caption_chars))
        if text:
            sections.append("TEXTO:\n" + _clip(text, max_text_chars))
        # añade tablas si existen pero en baja prioridad
        if tables_text:
            sections.append("TABLAS (baja prioridad):\n" + _clip(tables_text, max_table_chars))
    elif wants_tables:
        if tables_text:
            sections.append("TABLAS:\n" + _clip(tables_text, max_table_chars))
        if captions:
            sections.append("FIGURAS / CAPTIONS:\n" + _clip(captions, max_caption_chars))
        if text:
            sections.append("TEXTO:\n" + _clip(text, max_text_chars))
    else:
        if text:
            sections.append("TEXTO:\n" + _clip(text, max_text_chars))
        if captions:
            sections.append("FIGURAS / CAPTIONS:\n" + _clip(captions, max_caption_chars))
        if tables_text:
            sections.append("TABLAS:\n" + _clip(tables_text, max_table_chars))

    context = "\n\n---\n\n".join([s for s in sections if s.strip()]).strip()

    # Recorte final duro si hace falta
    return _clip(context, max_chars)
#!/usr/bin/env python
"""Modo PDF escaneado (imagem) com preservacao de layout.

Requisitos:
- PyMuPDF (fitz)
- pytesseract
- opencv-python (cv2)
- Pillow
- google-generativeai (Gemini API - motor principal)
- transformers (NLLB ou M2M100 - fallback offline)
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import fitz  # PyMuPDF
import cv2  # opencv-python
import pytesseract
from PIL import Image, ImageDraw, ImageFont, ImageStat

# Dependencia do OpenCV (mantida explicita para conversoes PIL <-> cv2)
import numpy as np  # noqa: F401

# --- Gemini API (motor principal) ---
try:
    import google.generativeai as genai
    from google.generativeai.types import HarmCategory, HarmBlockThreshold
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

# --- Transformers (fallback offline) ---
try:
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    TRANSFORMERS_AVAILABLE = True
except Exception:
    # Captura ImportError E erros internos do torch/accelerate (ex: torch 2.7+ incompativel)
    TRANSFORMERS_AVAILABLE = False


# ----------------------------
# Constantes Gemini
# ----------------------------

GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_FALLBACK_MODEL = "gemini-2.0-flash"
GEMINI_BATCH_SIZE = 40  # blocos por requisicao (eficiente sem estourar tokens)
GEMINI_RATE_DELAY = 4.0  # segundos entre requisicoes (free tier)

# Mapa de idiomas para nomes completos
_LANG_NAMES = {
    "pt": "Portuguese (Brazil)",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese (Simplified)",
    "ru": "Russian",
    "ar": "Arabic",
    "nl": "Dutch",
    "pl": "Polish",
    "tr": "Turkish",
    "hi": "Hindi",
    "en": "English",
}


def _lang_full_name(short: str) -> str:
    return _LANG_NAMES.get(short, short)


# ----------------------------
# Modelos offline / idiomas
# ----------------------------

NLLB_LANGS = {
    "en": "eng_Latn",
    "pt": "por_Latn",
    "es": "spa_Latn",
    "fr": "fra_Latn",
    "de": "deu_Latn",
    "it": "ita_Latn",
    "ja": "jpn_Jpan",
    "ko": "kor_Hang",
    "zh": "zho_Hans",
    "ru": "rus_Cyrl",
    "ar": "arb_Arab",
    "nl": "nld_Latn",
    "pl": "pol_Latn",
    "tr": "tur_Latn",
    "hi": "hin_Deva",
}

M2M_LANGS = {
    "en": "en",
    "pt": "pt",
    "es": "es",
    "fr": "fr",
    "de": "de",
    "it": "it",
    "ja": "ja",
    "ko": "ko",
    "zh": "zh",
    "ru": "ru",
    "ar": "ar",
    "nl": "nl",
    "pl": "pl",
    "tr": "tr",
    "hi": "hi",
}


def _is_nllb(model_name: str) -> bool:
    return "nllb" in (model_name or "").lower()


def _lang_code(model_name: str, short: str) -> str:
    if _is_nllb(model_name):
        return NLLB_LANGS.get(short, short)
    return M2M_LANGS.get(short, short)


# ----------------------------
# Blocos OCR
# ----------------------------


@dataclass
class TextStyle:
    """Estilo visual detectado pelo Gemini Vision."""
    color: str = "#FFFFFF"       # hex color do texto
    bold: bool = False
    italic: bool = False
    outline: bool = False
    outline_color: str = "#000000"
    shadow: bool = False
    approx_size: str = "medium"  # small, medium, large, xlarge
    block_type: str = "body"     # title, header, body, caption, label


@dataclass
class Block:
    page: int
    bbox: Tuple[int, int, int, int]
    src_text: str
    conf_avg: float
    dst_text: str = ""
    status: str = "PENDING"
    font_size_used: int = 0
    style: Optional[TextStyle] = None


# ----------------------------
# Utilidades gerais
# ----------------------------


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _has_letters(text: str) -> bool:
    return bool(re.search(r"[A-Za-z\u00C0-\u00FF]", text or ""))


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


# ----------------------------
# Detectar PDF escaneado
# ----------------------------


def detect_scanned_pdf(pdf_path: Path, check_pages: int = 2) -> bool:
    doc = fitz.open(str(pdf_path))
    pages = min(check_pages, doc.page_count)
    if pages <= 0:
        return False
    empty = 0
    for i in range(pages):
        page = doc.load_page(i)
        if not page.get_text("text").strip():
            empty += 1
    return empty == pages


# ----------------------------
# Renderizar paginas
# ----------------------------


def render_pages(pdf_path: Path, dpi: int = 300) -> List[Image.Image]:
    doc = fitz.open(str(pdf_path))
    images: List[Image.Image] = []
    for i in range(doc.page_count):
        page = doc.load_page(i)
        pix = page.get_pixmap(dpi=dpi, alpha=False)
        mode = "RGB"
        img = Image.frombytes(mode, (pix.width, pix.height), pix.samples)
        images.append(img)
    return images


# ----------------------------
# OCR para blocos
# ----------------------------


def ocr_to_blocks(
    image: Image.Image,
    page_index: int,
    min_conf: int = 60,
    lang: str = "eng",
) -> List[Block]:
    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT, lang=lang)

    by_line: Dict[Tuple[int, int, int], List[Dict[str, object]]] = {}
    n = len(data.get("text", []))
    for i in range(n):
        text = (data["text"][i] or "").strip()
        if not text:
            continue
        try:
            conf = float(data["conf"][i])
        except Exception:
            conf = -1.0
        key = (
            int(data["block_num"][i]),
            int(data["par_num"][i]),
            int(data["line_num"][i]),
        )
        by_line.setdefault(key, []).append(
            {
                "text": text,
                "conf": conf,
                "left": int(data["left"][i]),
                "top": int(data["top"][i]),
                "width": int(data["width"][i]),
                "height": int(data["height"][i]),
            }
        )

    blocks: List[Block] = []
    for _, items in by_line.items():
        items.sort(key=lambda x: int(x["left"]))
        texts = [str(x["text"]) for x in items if str(x["text"]).strip()]
        if not texts:
            continue
        src_text = " ".join(texts).strip()
        xs = [int(x["left"]) for x in items]
        ys = [int(x["top"]) for x in items]
        x2s = [int(x["left"]) + int(x["width"]) for x in items]
        y2s = [int(x["top"]) + int(x["height"]) for x in items]
        confs = [float(x["conf"]) for x in items if float(x["conf"]) >= 0]
        conf_avg = sum(confs) / max(1, len(confs)) if confs else 0.0
        bbox = (min(xs), min(ys), max(x2s), max(y2s))
        status = "PENDING" if conf_avg >= min_conf else "FILTER_CONF"
        blocks.append(
            Block(
                page=page_index,
                bbox=bbox,
                src_text=src_text,
                conf_avg=round(conf_avg, 2),
                status=status,
            )
        )

    blocks.sort(key=lambda b: (b.bbox[1], b.bbox[0]))
    return blocks


# ----------------------------
# Freeze/restore de padroes
# ----------------------------


_FREEZE_PATTERNS: List[re.Pattern] = [
    re.compile(r"\b\d+(?:[.,:/-]\d+)*%?\b"),
    re.compile(r"\b[A-Za-z]*\d+[A-Za-z]*\b"),
    re.compile(r"[%$\u20AC\u00A3\u00A5\u20BD\u20A9]+"),
    re.compile(r"[:;%]+"),
]


def _freeze_patterns(text: str) -> Tuple[str, Dict[str, str]]:
    mapping: Dict[str, str] = {}

    def _reserve(value: str) -> str:
        key = f"[[PH{len(mapping):04d}]]"
        mapping[key] = value
        return key

    out = text
    for pat in _FREEZE_PATTERNS:
        for m in list(pat.finditer(out)):
            val = m.group(0)
            token = _reserve(val)
            out = out.replace(val, token)
    return out, mapping


def _normalize_placeholder_tokens(text: str) -> str:
    return re.sub(r"\[\[\s*PH(\d{4})\s*\]\]", r"[[PH\1]]", text)


def _restore_patterns(text: str, mapping: Dict[str, str]) -> str:
    out = _normalize_placeholder_tokens(text)
    for k, v in mapping.items():
        out = out.replace(k, v)
    return out


# ============================================================
# MOTOR 1: Gemini API (principal - alta qualidade)
# ============================================================


def _build_pdf_system_prompt(
    target_language: str = "Portuguese (Brazil)",
    document_type: str = "game manual",
) -> str:
    """Prompt especializado para traducao de manuais/documentos PDF."""
    return (
        f"You are a professional translator specialized in {document_type} "
        f"localization with 20 years of experience.\n"
        f"Your goal is to produce publication-quality {target_language} "
        f"translations that read naturally and fluently.\n\n"
        f"TRANSLATION QUALITY RULES:\n"
        f"1. Use natural, fluent {target_language}. Avoid literal translations.\n"
        f"2. Adapt idioms and expressions to the target culture.\n"
        f"3. Keep proper names (characters, places, items, brands) UNCHANGED "
        f"unless they have an established localized name.\n"
        f"4. Maintain the original tone and style of the document.\n"
        f"5. For game manuals: keep gaming terminology accurate. "
        f"Examples: 'Hit Points'='Pontos de Vida', 'Magic Points'='Pontos de Magia', "
        f"'Save'='Salvar', 'Load'='Carregar', 'Equip'='Equipar', "
        f"'Inventory'='Inventario', 'Quest'='Missao', 'Level'='Nivel'.\n"
        f"6. For technical terms specific to console buttons, keep them: "
        f"'A Button', 'B Button', 'Control Pad', 'Start', 'Select', "
        f"'L-Button', 'R-Button', 'X Button', 'Y Button'.\n\n"
        f"FORMATTING RULES:\n"
        f"7. Each input line is numbered [N]. Return EACH line with the SAME [N] prefix.\n"
        f"8. Do NOT skip, merge, reorder, or add lines.\n"
        f"9. ONLY return translated lines. No explanations or commentary.\n"
        f"10. If input looks like OCR garbage or unreadable, return it UNCHANGED.\n"
        f"11. Preserve ALL numbers, dates, page references exactly as they appear.\n"
    )


def _get_gemini_safety_settings() -> list:
    if not GENAI_AVAILABLE:
        return []
    return [
        {"category": HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
         "threshold": HarmBlockThreshold.BLOCK_NONE},
        {"category": HarmCategory.HARM_CATEGORY_HATE_SPEECH,
         "threshold": HarmBlockThreshold.BLOCK_NONE},
        {"category": HarmCategory.HARM_CATEGORY_HARASSMENT,
         "threshold": HarmBlockThreshold.BLOCK_NONE},
        {"category": HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
         "threshold": HarmBlockThreshold.BLOCK_NONE},
    ]


_ID_RE = re.compile(r"^\[(\d+)\]\s?(.*)", re.MULTILINE)


def _parse_numbered_response(response_text: str, expected: int, originals: List[str]) -> Optional[List[str]]:
    """Mapeia resposta [N] da API. Retorna lista ordenada ou None."""
    matches = _ID_RE.findall(response_text)
    if not matches:
        return None
    result_map = {}
    for num_str, text in matches:
        idx = int(num_str) - 1
        if 0 <= idx < expected:
            result_map[idx] = text.strip()
    if len(result_map) < expected * 0.3:
        return None
    output = []
    for i in range(expected):
        output.append(result_map.get(i, originals[i]))
    return output


def _load_api_key(explicit_key: str = "") -> str:
    """Carrega API key: argumento > env > translator_config.json."""
    if explicit_key and explicit_key.strip():
        return explicit_key.strip()

    env_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if env_key:
        return env_key

    # Tenta ler do translator_config.json do projeto
    config_candidates = [
        Path(__file__).parent.parent / "interface" / "translator_config.json",
        Path.cwd() / "interface" / "translator_config.json",
    ]
    for cfg_path in config_candidates:
        if cfg_path.exists():
            try:
                data = json.loads(cfg_path.read_text(encoding="utf-8"))
                obf = data.get("api_key_obfuscated", "")
                if obf:
                    # Desobfuscar (XOR simples com chave fixa - mesmo metodo da GUI)
                    import base64
                    try:
                        raw = base64.b64decode(obf)
                        key_bytes = b"N3ur0R0M_K3y_2025!"
                        dec = bytes(b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(raw))
                        candidate = dec.decode("utf-8", errors="ignore").strip()
                        if candidate.startswith("AIza"):
                            return candidate
                    except Exception:
                        pass
            except Exception:
                pass

    return ""


class GeminiPDFTranslator:
    """Motor de traducao via Gemini API para PDFs."""

    def __init__(
        self,
        api_key: str,
        tgt_lang: str = "pt",
        document_type: str = "game manual",
        batch_size: int = GEMINI_BATCH_SIZE,
    ) -> None:
        self.api_key = api_key
        self.tgt_lang = tgt_lang
        self.tgt_lang_full = _lang_full_name(tgt_lang)
        self.document_type = document_type
        self.batch_size = batch_size
        self._model_name = GEMINI_MODEL
        self._configured = False

    def _ensure_configured(self) -> bool:
        if self._configured:
            return True
        if not GENAI_AVAILABLE:
            print("[GEMINI] google-generativeai nao instalado.")
            return False
        if not self.api_key:
            print("[GEMINI] API key nao encontrada.")
            return False
        try:
            genai.configure(api_key=self.api_key)
            self._configured = True
            return True
        except Exception as e:
            print(f"[GEMINI] Erro ao configurar: {e}")
            return False

    def translate_text(self, text: str) -> str:
        """Traduz um unico texto (fallback 1-a-1)."""
        results = self.translate_batch([text])
        return results[0] if results else text

    def translate_batch(self, texts: List[str]) -> List[str]:
        """Traduz uma lista de textos em batch via Gemini API."""
        if not self._ensure_configured():
            return texts

        numbered = [f"[{i+1}] {t}" for i, t in enumerate(texts)]
        text_block = "\n".join(numbered)

        generation_config = {
            "temperature": 0.3,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 8192,
        }

        for attempt in range(3):
            try:
                time.sleep(GEMINI_RATE_DELAY)

                model = genai.GenerativeModel(
                    model_name=self._model_name,
                    generation_config=generation_config,
                    safety_settings=_get_gemini_safety_settings(),
                    system_instruction=_build_pdf_system_prompt(
                        self.tgt_lang_full, self.document_type
                    ),
                )

                response = model.generate_content(text_block)

                if not response or not response.text:
                    continue

                translated = response.text.strip()

                # Parse por IDs numerados [N]
                parsed = _parse_numbered_response(translated, len(texts), texts)
                if parsed is not None:
                    return parsed

                # Fallback: split por linhas
                raw_lines = [ln for ln in translated.split("\n") if ln.strip()]
                if len(raw_lines) == len(texts):
                    return [ln.strip() for ln in raw_lines]

                # Mismatch - retenta
                continue

            except Exception as e:
                err = str(e).lower()
                # Se modelo nao encontrado, tenta fallback
                if "404" in err or "not found" in err:
                    if self._model_name != GEMINI_FALLBACK_MODEL:
                        print(f"[GEMINI] Modelo {self._model_name} nao encontrado, tentando {GEMINI_FALLBACK_MODEL}")
                        self._model_name = GEMINI_FALLBACK_MODEL
                        continue
                # Rate limit - espera e retenta
                if "429" in err or "resource" in err:
                    wait = (attempt + 1) * 10
                    print(f"[GEMINI] Rate limit, aguardando {wait}s...")
                    time.sleep(wait)
                    continue
                print(f"[GEMINI] Erro tentativa {attempt+1}: {e}")

        return texts  # falha total: retorna originais


# ============================================================
# MOTOR 1.5: Gemini VISION (PRO - le imagem direto)
# ============================================================


def _build_vision_prompt(
    target_language: str = "Portuguese (Brazil)",
    document_type: str = "game manual",
) -> str:
    """Prompt para Gemini Vision - le e traduz imagem de pagina."""
    return (
        f"You are analyzing a scanned page from a {document_type}.\n"
        f"Your task is to:\n"
        f"1. Read ALL visible text in this image (including decorative titles, "
        f"headers, body text, captions, labels, etc.)\n"
        f"2. Translate each text block to {target_language}\n\n"
        f"TRANSLATION RULES:\n"
        f"- Use natural, fluent {target_language}\n"
        f"- Keep proper names (characters, places, brands) UNCHANGED\n"
        f"- For game manuals: 'Hit Points'='Pontos de Vida', 'Magic Points'='Pontos de Magia', "
        f"'Save'='Salvar', 'Load'='Carregar', 'Equip'='Equipar', "
        f"'Inventory'='Inventario', 'Quest'='Missao', 'Level'='Nivel'\n"
        f"- Keep console button names: A Button, B Button, Control Pad, Start, Select, "
        f"L-Button, R-Button, X Button, Y Button\n"
        f"- Preserve all numbers, page references, dates\n\n"
        f"OUTPUT FORMAT (strict JSON array):\n"
        f"Return ONLY a JSON array. Each element must have:\n"
        f"- \"src\": original text exactly as it appears in the image\n"
        f"- \"dst\": translated text in {target_language}\n"
        f"- \"region\": approximate position as \"top-left\", \"top-center\", \"top-right\", "
        f"\"middle-left\", \"middle-center\", \"middle-right\", "
        f"\"bottom-left\", \"bottom-center\", \"bottom-right\"\n"
        f"- \"type\": \"title\", \"header\", \"body\", \"caption\", \"label\", or \"other\"\n"
        f"- \"style\": object with visual properties detected from the image:\n"
        f"  - \"color\": text color as hex string (e.g. \"#FFD700\" for gold, \"#FFFFFF\" for white)\n"
        f"  - \"bold\": true/false\n"
        f"  - \"italic\": true/false\n"
        f"  - \"outline\": true if text has outline/stroke effect, false otherwise\n"
        f"  - \"outline_color\": outline color as hex if outline is true (e.g. \"#000000\")\n"
        f"  - \"shadow\": true if text has drop shadow, false otherwise\n"
        f"  - \"approx_size\": approximate font size as \"small\", \"medium\", \"large\", \"xlarge\"\n\n"
        f"IMPORTANT:\n"
        f"- Read ALL text, even decorative/stylized fonts\n"
        f"- Do NOT include text from screenshots/game images embedded in the page\n"
        f"- Detect visual style ACCURATELY - color is critical for faithful reproduction\n"
        f"- Return ONLY the JSON array, no markdown fences, no explanation\n"
    )


def _fuzzy_match_score(a: str, b: str) -> float:
    """Score de similaridade simples entre duas strings (0.0 a 1.0)."""
    a_lower = a.lower().strip()
    b_lower = b.lower().strip()
    if not a_lower or not b_lower:
        return 0.0
    if a_lower == b_lower:
        return 1.0
    # Containment check
    if a_lower in b_lower or b_lower in a_lower:
        shorter = min(len(a_lower), len(b_lower))
        longer = max(len(a_lower), len(b_lower))
        return shorter / longer
    # Word overlap
    words_a = set(a_lower.split())
    words_b = set(b_lower.split())
    if not words_a or not words_b:
        return 0.0
    overlap = len(words_a & words_b)
    total = max(len(words_a), len(words_b))
    return overlap / total


def _parse_vision_entries(entries: list) -> List[Dict[str, object]]:
    """Parse e valida entradas JSON do Gemini Vision, incluindo style."""
    valid = []
    for e in entries:
        if not isinstance(e, dict) or "src" not in e or "dst" not in e:
            continue
        style_raw = e.get("style", {})
        if not isinstance(style_raw, dict):
            style_raw = {}
        style = TextStyle(
            color=str(style_raw.get("color", "#FFFFFF")),
            bold=bool(style_raw.get("bold", False)),
            italic=bool(style_raw.get("italic", False)),
            outline=bool(style_raw.get("outline", False)),
            outline_color=str(style_raw.get("outline_color", "#000000")),
            shadow=bool(style_raw.get("shadow", False)),
            approx_size=str(style_raw.get("approx_size", "medium")),
            block_type=str(e.get("type", "body")),
        )
        valid.append({
            "src": str(e.get("src", "")),
            "dst": str(e.get("dst", "")),
            "region": str(e.get("region", "middle-center")),
            "type": str(e.get("type", "body")),
            "style": style,
        })
    return valid


def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Converte '#RRGGBB' para (R, G, B)."""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return (255, 255, 255)
    try:
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    except ValueError:
        return (255, 255, 255)


class GeminiVisionTranslator:
    """Motor PRO: envia imagem da pagina para Gemini Vision, le e traduz em um passo."""

    def __init__(
        self,
        api_key: str,
        tgt_lang: str = "pt",
        document_type: str = "game manual",
    ) -> None:
        self.api_key = api_key
        self.tgt_lang = tgt_lang
        self.tgt_lang_full = _lang_full_name(tgt_lang)
        self.document_type = document_type
        self._model_name = GEMINI_MODEL
        self._configured = False

    def _ensure_configured(self) -> bool:
        if self._configured:
            return True
        if not GENAI_AVAILABLE:
            return False
        if not self.api_key:
            return False
        try:
            genai.configure(api_key=self.api_key)
            self._configured = True
            return True
        except Exception:
            return False

    def extract_and_translate_page(self, image: Image.Image) -> List[Dict[str, str]]:
        """Envia imagem da pagina para Gemini Vision.
        Retorna lista de dicts: {src, dst, region, type}."""
        if not self._ensure_configured():
            return []

        prompt = _build_vision_prompt(self.tgt_lang_full, self.document_type)

        generation_config = {
            "temperature": 0.2,
            "top_p": 0.95,
            "max_output_tokens": 8192,
        }

        for attempt in range(3):
            try:
                time.sleep(GEMINI_RATE_DELAY)

                model = genai.GenerativeModel(
                    model_name=self._model_name,
                    generation_config=generation_config,
                    safety_settings=_get_gemini_safety_settings(),
                )

                response = model.generate_content([prompt, image])

                if not response or not response.text:
                    continue

                raw = response.text.strip()

                # Limpar markdown fences se houver
                if raw.startswith("```"):
                    raw = re.sub(r"^```(?:json)?\s*\n?", "", raw)
                    raw = re.sub(r"\n?```\s*$", "", raw)

                entries = json.loads(raw)
                if isinstance(entries, list):
                    return _parse_vision_entries(entries)

            except json.JSONDecodeError:
                # Tentar extrair JSON parcial
                try:
                    match = re.search(r"\[.*\]", raw, re.DOTALL)
                    if match:
                        entries = json.loads(match.group(0))
                        if isinstance(entries, list):
                            return _parse_vision_entries(entries)
                except Exception:
                    pass
                print(f"[VISION] JSON invalido na tentativa {attempt+1}")

            except Exception as e:
                err = str(e).lower()
                if "404" in err or "not found" in err:
                    if self._model_name != GEMINI_FALLBACK_MODEL:
                        print(f"[VISION] Modelo {self._model_name} nao disponivel, tentando {GEMINI_FALLBACK_MODEL}")
                        self._model_name = GEMINI_FALLBACK_MODEL
                        continue
                if "429" in err or "resource" in err:
                    wait = (attempt + 1) * 15
                    print(f"[VISION] Rate limit, aguardando {wait}s...")
                    time.sleep(wait)
                    continue
                print(f"[VISION] Erro tentativa {attempt+1}: {e}")

        return []


def translate_page_vision(
    image: Image.Image,
    page_index: int,
    vision_translator: "GeminiVisionTranslator",
    ocr_blocks: List[Block],
    min_match_score: float = 0.35,
) -> List[Block]:
    """Combina Vision (leitura + traducao) com Tesseract (posicionamento).

    1. Gemini Vision le e traduz a imagem inteira
    2. Tesseract fornece bounding boxes
    3. Matching fuzzy associa traducao Vision -> bbox Tesseract
    4. Blocos sem match recebem traducao via texto Gemini normal
    """
    vision_entries = vision_translator.extract_and_translate_page(image)

    if not vision_entries:
        print(f"  [VISION] Pagina {page_index+1}: sem resultados, usando Tesseract puro")
        return ocr_blocks

    print(f"  [VISION] Pagina {page_index+1}: {len(vision_entries)} blocos lidos, {len(ocr_blocks)} bboxes Tesseract")

    # Matching: para cada bbox do Tesseract, encontrar o melhor match do Vision
    used_vision = set()

    for block in ocr_blocks:
        if block.status == "FILTER_CONF":
            block.dst_text = block.src_text
            continue
        if not _has_letters(block.src_text):
            block.dst_text = block.src_text
            block.status = "SKIP_NO_TEXT"
            continue

        best_score = 0.0
        best_idx = -1

        for vi, entry in enumerate(vision_entries):
            if vi in used_vision:
                continue
            score = _fuzzy_match_score(block.src_text, entry["src"])
            if score > best_score:
                best_score = score
                best_idx = vi

        if best_idx >= 0 and best_score >= min_match_score:
            entry = vision_entries[best_idx]
            block.dst_text = entry["dst"]
            block.status = "OK_VISION"
            # Transferir estilo visual detectado pelo Vision
            if "style" in entry and isinstance(entry["style"], TextStyle):
                block.style = entry["style"]
            used_vision.add(best_idx)
        else:
            # Sem match - mantem src_text para traduzir depois com Gemini text
            block.status = "PENDING"

    # Blocos Vision que nao tiveram match com Tesseract -> criar novos blocos
    # (textos que o Tesseract nao detectou, ex: fontes decorativas)
    unmatched_vision = [
        vision_entries[i] for i in range(len(vision_entries)) if i not in used_vision
    ]
    if unmatched_vision:
        print(f"  [VISION] {len(unmatched_vision)} textos lidos pelo Vision sem bbox Tesseract (decorativos/estilizados)")

    matched = sum(1 for b in ocr_blocks if b.status == "OK_VISION")
    pending = sum(1 for b in ocr_blocks if b.status == "PENDING")
    print(f"  [VISION] Matched: {matched}, Pendentes para Gemini text: {pending}")

    return ocr_blocks


# ============================================================
# MOTOR 2: Transformers offline (fallback)
# ============================================================


class TransformerTranslator:
    def __init__(
        self,
        model_name: str,
        src_lang: str,
        tgt_lang: str,
        max_new_tokens: int = 128,
        length_penalty: float = 0.8,
    ) -> None:
        self.model_name = model_name
        self.max_new_tokens = max_new_tokens
        self.length_penalty = length_penalty
        self.device = "cpu"
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
        self.model.to(self.device)

        self.src_code = _lang_code(model_name, src_lang)
        self.tgt_code = _lang_code(model_name, tgt_lang)

        if hasattr(self.tokenizer, "src_lang"):
            self.tokenizer.src_lang = self.src_code
        elif hasattr(self.tokenizer, "set_src_lang_special_tokens"):
            try:
                self.tokenizer.set_src_lang_special_tokens(self.src_code)
            except Exception:
                pass

    def translate_text(self, text: str) -> str:
        if not text.strip():
            return text

        enc = self.tokenizer(text, return_tensors="pt", truncation=True)
        enc = {k: v.to(self.device) for k, v in enc.items()}

        forced_bos_token_id = None
        if _is_nllb(self.model_name):
            if self.tgt_code:
                forced_bos_token_id = self.tokenizer.convert_tokens_to_ids(self.tgt_code)
        else:
            if hasattr(self.tokenizer, "get_lang_id") and self.tgt_code:
                forced_bos_token_id = self.tokenizer.get_lang_id(self.tgt_code)

        gen = self.model.generate(
            **enc,
            max_new_tokens=self.max_new_tokens,
            num_beams=4,
            length_penalty=self.length_penalty,
            forced_bos_token_id=forced_bos_token_id,
        )

        out = self.tokenizer.batch_decode(gen, skip_special_tokens=True)[0]
        return out.strip()


# ============================================================
# Traducao unificada de blocos
# ============================================================


def translate_blocks_gemini(blocks: List[Block], translator: GeminiPDFTranslator) -> None:
    """Traduz blocos em batch via Gemini API."""
    pending = [(i, b) for i, b in enumerate(blocks) if b.status == "PENDING"]

    # Filtrar blocos sem texto
    for i, b in enumerate(blocks):
        if b.status == "FILTER_CONF":
            b.dst_text = b.src_text
            continue
        if b.status == "PENDING" and not _has_letters(b.src_text):
            b.dst_text = b.src_text
            b.status = "SKIP_NO_TEXT"

    # Coletar pendentes com texto
    to_translate = [(i, b) for i, b in enumerate(blocks) if b.status == "PENDING"]
    if not to_translate:
        return

    # Processar em batches
    batch_size = translator.batch_size
    for start in range(0, len(to_translate), batch_size):
        chunk = to_translate[start : start + batch_size]
        src_texts = []
        mappings = []

        for _, b in chunk:
            frozen, mapping = _freeze_patterns(b.src_text)
            src_texts.append(frozen)
            mappings.append(mapping)

        try:
            translated = translator.translate_batch(src_texts)
            for j, (idx, b) in enumerate(chunk):
                restored = _restore_patterns(translated[j], mappings[j])
                b.dst_text = restored
                b.status = "OK"
        except Exception as e:
            for _, b in chunk:
                b.dst_text = b.src_text
                b.status = f"ERROR_TRANSLATE: {type(e).__name__}"

        if start + batch_size < len(to_translate):
            print(f"  [BATCH] {min(start + batch_size, len(to_translate))}/{len(to_translate)} blocos traduzidos")


def translate_blocks_offline(blocks: List[Block], translator: TransformerTranslator) -> None:
    """Traduz blocos 1-a-1 via modelo offline."""
    for b in blocks:
        if b.status == "FILTER_CONF":
            b.dst_text = b.src_text
            continue
        if not _has_letters(b.src_text):
            b.dst_text = b.src_text
            b.status = "SKIP_NO_TEXT"
            continue

        frozen, mapping = _freeze_patterns(b.src_text)
        try:
            out = translator.translate_text(frozen)
            restored = _restore_patterns(out, mapping)
            b.dst_text = restored
            b.status = "OK"
        except Exception as e:
            b.dst_text = b.src_text
            b.status = f"ERROR_TRANSLATE: {type(e).__name__}"


# ----------------------------
# Inpaint + escrita
# ----------------------------


def _clamp_bbox(bbox: Tuple[int, int, int, int], w: int, h: int, pad: int = 2) -> Tuple[int, int, int, int]:
    x0, y0, x1, y1 = bbox
    x0 = max(0, x0 - pad)
    y0 = max(0, y0 - pad)
    x1 = min(w - 1, x1 + pad)
    y1 = min(h - 1, y1 + pad)
    return x0, y0, x1, y1


def _sample_border_color(image_cv: "np.ndarray", bbox: Tuple[int, int, int, int]) -> Tuple[int, int, int]:
    x0, y0, x1, y1 = bbox
    h, w = image_cv.shape[:2]
    strips = []
    if y0 > 1:
        strips.append(image_cv[max(0, y0 - 2) : y0, x0:x1])
    if y1 < h - 2:
        strips.append(image_cv[y1 : min(h, y1 + 2), x0:x1])
    if x0 > 1:
        strips.append(image_cv[y0:y1, max(0, x0 - 2) : x0])
    if x1 < w - 2:
        strips.append(image_cv[y0:y1, x1 : min(w, x1 + 2)])

    if not strips:
        return (255, 255, 255)

    means = [cv2.mean(s)[:3] for s in strips if s.size > 0]
    if not means:
        return (255, 255, 255)
    b = sum(m[0] for m in means) / len(means)
    g = sum(m[1] for m in means) / len(means)
    r = sum(m[2] for m in means) / len(means)
    return (int(b), int(g), int(r))


def inpaint_bbox(image_cv: "np.ndarray", bbox: Tuple[int, int, int, int]) -> "np.ndarray":
    h, w = image_cv.shape[:2]
    bx0, by0, bx1, by1 = bbox
    box_h = by1 - by0
    box_w = bx1 - bx0
    # Margem adaptativa: blocos maiores precisam de mais margem
    pad = max(3, min(box_h, box_w) // 8)
    # Raio de inpainting proporcional ao bloco
    inpaint_radius = max(3, min(box_h, box_w) // 6)
    x0, y0, x1, y1 = _clamp_bbox(bbox, w, h, pad=pad)
    try:
        mask = np.zeros((h, w), dtype=np.uint8)
        cv2.rectangle(mask, (x0, y0), (x1, y1), 255, thickness=-1)
        return cv2.inpaint(image_cv, mask, inpaint_radius, cv2.INPAINT_TELEA)
    except Exception:
        color = _sample_border_color(image_cv, (x0, y0, x1, y1))
        cv2.rectangle(image_cv, (x0, y0), (x1, y1), color, thickness=-1)
        return image_cv


def _find_font_path(custom: str = "") -> Optional[str]:
    if custom:
        p = Path(custom)
        if p.exists():
            return str(p)
    candidates = [
        "C:/Windows/Fonts/DejaVuSans.ttf",
        "C:/Windows/Fonts/NotoSans-Regular.ttf",
        "C:/Windows/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    return None


# Mapa de fontes por estilo (titulo vs corpo)
_FONT_CANDIDATES = {
    "title_bold": [
        "C:/Windows/Fonts/Impact.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/georgiabd.ttf",
        "C:/Windows/Fonts/trebucbd.ttf",
        "C:/Windows/Fonts/verdanab.ttf",
    ],
    "title_bold_italic": [
        "C:/Windows/Fonts/arialbi.ttf",
        "C:/Windows/Fonts/georgiaz.ttf",
        "C:/Windows/Fonts/trebucbi.ttf",
    ],
    "title_regular": [
        "C:/Windows/Fonts/Georgia.ttf",
        "C:/Windows/Fonts/times.ttf",
        "C:/Windows/Fonts/trebuc.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ],
    "title_italic": [
        "C:/Windows/Fonts/georgiai.ttf",
        "C:/Windows/Fonts/timesi.ttf",
        "C:/Windows/Fonts/ariali.ttf",
    ],
    "body_bold": [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/calibrib.ttf",
        "C:/Windows/Fonts/verdanab.ttf",
    ],
    "body_bold_italic": [
        "C:/Windows/Fonts/arialbi.ttf",
        "C:/Windows/Fonts/calibriz.ttf",
        "C:/Windows/Fonts/verdanaz.ttf",
    ],
    "body_italic": [
        "C:/Windows/Fonts/ariali.ttf",
        "C:/Windows/Fonts/calibrii.ttf",
        "C:/Windows/Fonts/verdanai.ttf",
    ],
    "body_regular": [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        "C:/Windows/Fonts/verdana.ttf",
    ],
    "caption": [
        "C:/Windows/Fonts/calibri.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ],
}


def _find_styled_font(style: Optional[TextStyle], fallback: str) -> str:
    """Seleciona fonte com base no estilo detectado pelo Vision.
    Usa cadeia de fallback: estilo exato -> estilo parcial -> regular -> fallback."""
    if style is None:
        return fallback

    is_title = style.block_type in ("title", "header")
    is_caption = style.block_type in ("caption", "footnote")

    # Cadeia de prioridade: estilo exato primeiro, depois fallbacks progressivos
    if is_title and style.bold and style.italic:
        keys = ["title_bold_italic", "title_bold", "title_regular"]
    elif is_title and style.bold:
        keys = ["title_bold", "title_regular"]
    elif is_title and style.italic:
        keys = ["title_italic", "title_regular"]
    elif is_title:
        keys = ["title_regular"]
    elif is_caption:
        keys = ["caption", "body_regular"]
    elif style.bold and style.italic:
        keys = ["body_bold_italic", "body_bold", "body_regular"]
    elif style.bold:
        keys = ["body_bold", "body_regular"]
    elif style.italic:
        keys = ["body_italic", "body_regular"]
    else:
        keys = ["body_regular"]

    for key in keys:
        for candidate in _FONT_CANDIDATES.get(key, []):
            if Path(candidate).exists():
                return candidate

    return fallback


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> List[str]:
    words = text.split()
    if not words:
        return [text]
    lines: List[str] = []
    cur = ""
    for w in words:
        test = f"{cur} {w}".strip()
        if draw.textlength(test, font=font) <= max_width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)

    fixed: List[str] = []
    for line in lines:
        if draw.textlength(line, font=font) <= max_width:
            fixed.append(line)
            continue
        buf = ""
        for ch in line:
            test = buf + ch
            if draw.textlength(test, font=font) <= max_width:
                buf = test
            else:
                if buf:
                    fixed.append(buf)
                buf = ch
        if buf:
            fixed.append(buf)
    return fixed


def fit_text_in_box(
    draw: ImageDraw.ImageDraw,
    text: str,
    bbox: Tuple[int, int, int, int],
    font_path: str,
    min_size: int = 10,
) -> Tuple[List[str], int]:
    x0, y0, x1, y1 = bbox
    box_w = max(1, x1 - x0)
    box_h = max(1, y1 - y0)
    max_size = max(min_size, int(box_h * 0.85))

    for size in range(max_size, min_size - 1, -1):
        font = ImageFont.truetype(font_path, size)
        lines = _wrap_text(draw, text, font, box_w)
        line_heights = []
        max_w = 0
        for line in lines:
            bbox_line = draw.textbbox((0, 0), line, font=font)
            w = bbox_line[2] - bbox_line[0]
            h = bbox_line[3] - bbox_line[1]
            max_w = max(max_w, w)
            line_heights.append(h)
        spacing = max(1, int(size * 0.15))
        total_h = sum(line_heights) + spacing * (len(lines) - 1)
        if max_w <= box_w and total_h <= box_h:
            return lines, size

    font = ImageFont.truetype(font_path, min_size)
    lines = _wrap_text(draw, text, font, box_w)
    return lines, min_size


def _choose_text_color(image: Image.Image, bbox: Tuple[int, int, int, int], style: Optional[TextStyle] = None) -> Tuple[int, int, int]:
    # Se Vision detectou cor, usar ela
    if style and style.color and style.color != "#FFFFFF":
        detected = _hex_to_rgb(style.color)
        # Validar que a cor nao e muito proxima do fundo
        x0, y0, x1, y1 = bbox
        pad = 2
        x0c = max(0, x0 - pad)
        y0c = max(0, y0 - pad)
        x1c = min(image.width - 1, x1 + pad)
        y1c = min(image.height - 1, y1 + pad)
        crop = image.crop((x0c, y0c, x1c, y1c))
        stat = ImageStat.Stat(crop)
        bg_r, bg_g, bg_b = stat.mean[:3]
        # Diferenca de luminancia minima
        fg_lum = 0.299 * detected[0] + 0.587 * detected[1] + 0.114 * detected[2]
        bg_lum = 0.299 * bg_r + 0.587 * bg_g + 0.114 * bg_b
        if abs(fg_lum - bg_lum) > 40:
            return detected
        # Cor muito proxima do fundo - usar contraste
    # Fallback: preto ou branco baseado em luminancia do fundo
    x0, y0, x1, y1 = bbox
    pad = 2
    x0 = max(0, x0 - pad)
    y0 = max(0, y0 - pad)
    x1 = min(image.width - 1, x1 + pad)
    y1 = min(image.height - 1, y1 + pad)
    crop = image.crop((x0, y0, x1, y1))
    stat = ImageStat.Stat(crop)
    r, g, b = stat.mean[:3]
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    return (0, 0, 0) if luminance > 140 else (255, 255, 255)


def _draw_text_with_outline(
    draw: ImageDraw.ImageDraw,
    pos: Tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: Tuple[int, int, int],
    outline_color: Tuple[int, int, int] = (0, 0, 0),
    outline_width: int = 2,
    spacing: int = 2,
) -> None:
    """Desenha texto com contorno (outline) para legibilidade em fundos complexos."""
    x, y = pos
    for dx in range(-outline_width, outline_width + 1):
        for dy in range(-outline_width, outline_width + 1):
            if dx == 0 and dy == 0:
                continue
            draw.multiline_text((x + dx, y + dy), text, font=font, fill=outline_color, spacing=spacing)
    draw.multiline_text((x, y), text, font=font, fill=fill, spacing=spacing)


def _draw_text_with_shadow(
    draw: ImageDraw.ImageDraw,
    pos: Tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: Tuple[int, int, int],
    shadow_color: Tuple[int, int, int] = (0, 0, 0),
    shadow_offset: int = 2,
    spacing: int = 2,
) -> None:
    """Desenha texto com sombra (drop shadow)."""
    x, y = pos
    draw.multiline_text((x + shadow_offset, y + shadow_offset), text, font=font, fill=shadow_color, spacing=spacing)
    draw.multiline_text((x, y), text, font=font, fill=fill, spacing=spacing)


def draw_text_fit(
    image: Image.Image,
    bbox: Tuple[int, int, int, int],
    dst_text: str,
    font_path: str,
    style: Optional[TextStyle] = None,
) -> Tuple[Image.Image, int]:
    draw = ImageDraw.Draw(image)
    pad = 2
    x0, y0, x1, y1 = bbox
    box = (x0 + pad, y0 + pad, x1 - pad, y1 - pad)

    # Selecionar fonte com base no estilo
    actual_font_path = _find_styled_font(style, font_path)
    lines, size = fit_text_in_box(draw, dst_text, box, actual_font_path)
    font = ImageFont.truetype(actual_font_path, size)
    color = _choose_text_color(image, bbox, style)
    spacing = max(1, int(size * 0.15))
    text_content = "\n".join(lines)

    # Escolher metodo de renderizacao com base no estilo
    if style and style.outline:
        outline_col = _hex_to_rgb(style.outline_color) if style.outline_color else (0, 0, 0)
        outline_w = max(1, size // 12)
        _draw_text_with_outline(draw, (box[0], box[1]), text_content, font, color,
                                outline_color=outline_col, outline_width=outline_w, spacing=spacing)
    elif style and style.shadow:
        shadow_off = max(1, size // 10)
        _draw_text_with_shadow(draw, (box[0], box[1]), text_content, font, color,
                               shadow_offset=shadow_off, spacing=spacing)
    elif style and (style.block_type in ("title", "header") or style.approx_size in ("large", "xlarge")):
        # Titulos sempre com outline para legibilidade
        bg_lum = _get_bg_luminance(image, bbox)
        # Fundo claro -> texto escuro -> outline branco (glow)
        # Fundo escuro -> texto claro -> outline preto (sombra)
        outline_col = (255, 255, 255) if bg_lum > 128 else (0, 0, 0)
        outline_w = max(1, size // 14)
        _draw_text_with_outline(draw, (box[0], box[1]), text_content, font, color,
                                outline_color=outline_col, outline_width=outline_w, spacing=spacing)
    else:
        # Texto corpo simples
        draw.multiline_text((box[0], box[1]), text_content, font=font, fill=color, spacing=spacing)

    return image, size


def _get_bg_luminance(image: Image.Image, bbox: Tuple[int, int, int, int]) -> float:
    """Retorna luminancia media do fundo na area do bbox."""
    x0, y0, x1, y1 = bbox
    x0 = max(0, x0 - 2)
    y0 = max(0, y0 - 2)
    x1 = min(image.width - 1, x1 + 2)
    y1 = min(image.height - 1, y1 + 2)
    crop = image.crop((x0, y0, x1, y1))
    stat = ImageStat.Stat(crop)
    r, g, b = stat.mean[:3]
    return 0.299 * r + 0.587 * g + 0.114 * b


# ----------------------------
# Construir PDF final
# ----------------------------


def build_pdf_from_images(images: List[Image.Image], out_pdf_path: Path, dpi: int = 300) -> None:
    out_pdf_path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    for img in images:
        width_pt = img.width * 72.0 / dpi
        height_pt = img.height * 72.0 / dpi
        page = doc.new_page(width=width_pt, height=height_pt)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        page.insert_image(fitz.Rect(0, 0, width_pt, height_pt), stream=buf.getvalue())
    doc.save(str(out_pdf_path))


# ----------------------------
# Exports auditaveis
# ----------------------------


def write_exports(
    out_pdf_path: Path,
    blocks: List[Block],
    mapping: Dict[str, object],
    report: str,
    proof: Dict[str, object],
) -> None:
    base = out_pdf_path.with_suffix("").name
    out_dir = out_pdf_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    blocks_path = out_dir / f"{base}_blocks.jsonl"
    mapping_path = out_dir / f"{base}_mapping.json"
    report_path = out_dir / f"{base}_report.txt"
    proof_path = out_dir / f"{base}_proof.json"

    with blocks_path.open("w", encoding="utf-8") as f:
        for b in blocks:
            item = {
                "page": b.page + 1,
                "bbox": list(b.bbox),
                "src_text": b.src_text,
                "dst_text": b.dst_text,
                "conf_avg": b.conf_avg,
                "status": b.status,
                "font_size_used": b.font_size_used,
            }
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    mapping_path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(report, encoding="utf-8")
    proof_path.write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding="utf-8")


# ----------------------------
# CLI
# ----------------------------


def _map_lang_from_ocr(ocr_lang: str) -> str:
    """Converte codigo Tesseract para codigo curto de idioma."""
    ocr_lang = (ocr_lang or "eng").lower().split("+")[0].strip()
    _OCR_MAP = {
        "eng": "en",
        "por": "pt",
        "spa": "es",
        "fra": "fr",
        "deu": "de",
        "ita": "it",
        "jpn": "ja",
        "kor": "ko",
        "chi_sim": "zh",
        "chi_tra": "zh",
        "rus": "ru",
        "ara": "ar",
        "nld": "nl",
        "pol": "pl",
        "tur": "tr",
        "hin": "hi",
    }
    for prefix, code in _OCR_MAP.items():
        if ocr_lang.startswith(prefix):
            return code
    return "en"


def _resolve_model_name(model_arg: str) -> str:
    m = (model_arg or "").strip().lower()
    if m in ("nllb", "nllb-200", "nllb-200-distilled-600m"):
        return "facebook/nllb-200-distilled-600M"
    if m in ("m2m100", "m2m100-418m", "m2m100_418m"):
        return "facebook/m2m100_418M"
    return model_arg


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Traducao de PDF escaneado com preservacao de layout (Gemini + fallback offline)."
    )
    ap.add_argument("--input", required=True, help="PDF de entrada")
    ap.add_argument("--out", required=True, help="PDF de saida (ex.: out_translated.pdf)")
    ap.add_argument("--lang", default="eng", help="Idioma OCR (pytesseract), ex.: eng")
    ap.add_argument("--src", default="", help="Idioma origem (en/pt). Se vazio, usa --lang.")
    ap.add_argument("--tgt", default="pt", help="Idioma destino (pt)")
    ap.add_argument(
        "--engine", default="gemini-vision",
        choices=["gemini-vision", "gemini", "nllb", "m2m100"],
        help="Motor: gemini-vision (PRO, le imagem) | gemini (texto) | nllb | m2m100 (offline)"
    )
    ap.add_argument("--api-key", default="", help="Gemini API key (ou use GEMINI_API_KEY env var)")
    ap.add_argument(
        "--doc-type", default="game manual",
        help="Tipo de documento para contexto do prompt (ex.: 'game manual', 'technical document')"
    )
    ap.add_argument("--model", default="nllb", help="Modelo offline (nllb | m2m100 | caminho HF)")
    ap.add_argument("--dpi", type=int, default=300, help="DPI de renderizacao (ex.: 300)")
    ap.add_argument("--min-conf", type=int, default=60, help="Confianca minima do OCR")
    ap.add_argument("--max-new-tokens", type=int, default=128, help="Max new tokens (modelo offline)")
    ap.add_argument("--length-penalty", type=float, default=0.8, help="Length penalty (modelo offline)")
    ap.add_argument("--font", default="", help="Caminho opcional da fonte TTF")
    ap.add_argument("--force", action="store_true", help="Forcar modo escaneado mesmo se o PDF tiver texto")
    args = ap.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.out)
    if out_path.suffix.lower() != ".pdf":
        out_path = out_path.with_suffix(".pdf")

    if not in_path.exists():
        print(f"[ERRO] Arquivo nao encontrado: {in_path}")
        return 2

    try:
        pytesseract.get_tesseract_version()
    except Exception as e:
        print(f"[ERRO] Tesseract nao encontrado/ativo: {e}")
        return 2

    if not args.force:
        if not detect_scanned_pdf(in_path):
            print("[INFO] PDF parece ter texto (nao e escaneado). Use --force para continuar.")
            return 3

    ocr_lang = args.lang
    src_lang = args.src.strip() or _map_lang_from_ocr(ocr_lang)
    tgt_lang = args.tgt.strip() or "pt"
    engine = args.engine.strip().lower()
    font_path = _find_font_path(args.font)
    if not font_path:
        print("[ERRO] Fonte TTF nao encontrada. Informe --font com uma fonte valida.")
        return 2

    # --- Selecionar motor de traducao ---
    use_vision = False
    use_gemini = False
    vision_translator = None
    gemini_translator = None
    offline_translator = None
    engine_display = ""

    if engine == "gemini-vision":
        api_key = _load_api_key(args.api_key)
        if api_key and GENAI_AVAILABLE:
            vision_translator = GeminiVisionTranslator(
                api_key=api_key,
                tgt_lang=tgt_lang,
                document_type=args.doc_type,
            )
            # Tambem cria tradutor texto para blocos pendentes apos Vision
            gemini_translator = GeminiPDFTranslator(
                api_key=api_key,
                tgt_lang=tgt_lang,
                document_type=args.doc_type,
            )
            use_vision = True
            use_gemini = True
            engine_display = f"Gemini Vision PRO ({GEMINI_MODEL})"
            print(f"[ENGINE] Gemini Vision PRO selecionado (le imagem + traduz)")
        else:
            if not GENAI_AVAILABLE:
                print("[WARN] google-generativeai nao instalado.")
            elif not api_key:
                print("[WARN] API key nao encontrada.")
            print("[WARN] Caindo para Gemini texto...")
            engine = "gemini"

    if engine == "gemini" and not use_vision:
        api_key = _load_api_key(args.api_key)
        if api_key and GENAI_AVAILABLE:
            gemini_translator = GeminiPDFTranslator(
                api_key=api_key,
                tgt_lang=tgt_lang,
                document_type=args.doc_type,
            )
            use_gemini = True
            engine_display = f"Gemini API ({GEMINI_MODEL})"
            print(f"[ENGINE] Gemini API selecionado (alta qualidade)")
        else:
            if not GENAI_AVAILABLE:
                print("[WARN] google-generativeai nao instalado. Usando fallback offline.")
            elif not api_key:
                print("[WARN] API key nao encontrada. Usando fallback offline.")
            print("[WARN] Para usar Gemini: --api-key SUA_KEY ou GEMINI_API_KEY env var")
            engine = "nllb"

    if not use_gemini and not use_vision:
        if not TRANSFORMERS_AVAILABLE:
            print("[ERRO] Nem Gemini nem transformers estao disponiveis. Instale google-generativeai ou transformers.")
            return 2
        model_name = _resolve_model_name(args.model if engine in ("nllb", "m2m100") else engine)
        engine_display = f"Offline ({model_name})"
        print(f"[ENGINE] Modelo offline: {model_name}")
        offline_translator = TransformerTranslator(
            model_name=model_name,
            src_lang=src_lang,
            tgt_lang=tgt_lang,
            max_new_tokens=args.max_new_tokens,
            length_penalty=args.length_penalty,
        )

    print(f"[CFG] input={in_path}")
    print(f"[CFG] out={out_path}")
    print(f"[CFG] ocr_lang={ocr_lang} src={src_lang} tgt={tgt_lang}")
    print(f"[CFG] engine={engine_display} dpi={args.dpi} min_conf={args.min_conf}")
    print(f"[CFG] doc_type={args.doc_type}")
    print(f"[CFG] font={font_path}")

    images = render_pages(in_path, dpi=args.dpi)
    out_images: List[Image.Image] = []
    all_blocks: List[Block] = []

    stats = {
        "pages": len(images),
        "blocks_total": 0,
        "blocks_filtered_conf": 0,
        "blocks_skipped": 0,
        "blocks_translated": 0,
        "blocks_errors": 0,
    }

    for page_idx, img in enumerate(images):
        print(f"[PAGE] {page_idx + 1}/{len(images)}")
        blocks = ocr_to_blocks(img, page_idx, min_conf=args.min_conf, lang=ocr_lang)
        stats["blocks_total"] += len(blocks)
        stats["blocks_filtered_conf"] += sum(1 for b in blocks if b.status == "FILTER_CONF")

        # Traduzir com o motor selecionado
        if use_vision:
            # MODO PRO: Vision le a imagem + matching com bboxes Tesseract
            blocks = translate_page_vision(img, page_idx, vision_translator, blocks)
            # Blocos PENDING restantes -> traduzir com Gemini texto
            pending_blocks = [b for b in blocks if b.status == "PENDING"]
            if pending_blocks and gemini_translator:
                translate_blocks_gemini(pending_blocks, gemini_translator)
            # Normalizar status OK_VISION -> OK
            for b in blocks:
                if b.status == "OK_VISION":
                    b.status = "OK"
        elif use_gemini:
            translate_blocks_gemini(blocks, gemini_translator)
        else:
            translate_blocks_offline(blocks, offline_translator)

        stats["blocks_skipped"] += sum(1 for b in blocks if b.status == "SKIP_NO_TEXT")
        stats["blocks_errors"] += sum(1 for b in blocks if b.status.startswith("ERROR"))
        stats["blocks_translated"] += sum(1 for b in blocks if b.status == "OK")

        # Inpaint apenas blocos OK
        img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        for b in blocks:
            if b.status == "OK":
                img_cv = inpaint_bbox(img_cv, b.bbox)

        # Desenhar texto traduzido
        img_pil = Image.fromarray(cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB))
        for b in blocks:
            if b.status == "OK":
                img_pil, used = draw_text_fit(img_pil, b.bbox, b.dst_text, font_path, b.style)
                b.font_size_used = used

        out_images.append(img_pil)
        all_blocks.extend(blocks)

    build_pdf_from_images(out_images, out_path, dpi=args.dpi)

    mapping: Dict[str, object] = {
        "pages": [],
        "stats": stats,
    }
    for p in range(stats["pages"]):
        page_blocks = [b for b in all_blocks if b.page == p]
        mapping["pages"].append(
            {
                "page": p + 1,
                "blocks_total": len(page_blocks),
                "blocks_filtered_conf": sum(1 for b in page_blocks if b.status == "FILTER_CONF"),
                "blocks_translated": sum(1 for b in page_blocks if b.status == "OK"),
                "blocks_skipped": sum(1 for b in page_blocks if b.status == "SKIP_NO_TEXT"),
                "blocks_errors": sum(1 for b in page_blocks if b.status.startswith("ERROR")),
            }
        )

    report_lines = [
        "PDF SCANNED TRANSLATION REPORT",
        "===============================",
        f"input: {in_path}",
        f"output: {out_path}",
        f"engine: {engine_display}",
        f"pages: {stats['pages']}",
        f"blocks_total: {stats['blocks_total']}",
        f"blocks_translated: {stats['blocks_translated']}",
        f"blocks_filtered_conf: {stats['blocks_filtered_conf']}",
        f"blocks_skipped: {stats['blocks_skipped']}",
        f"blocks_errors: {stats['blocks_errors']}",
        f"min_conf: {args.min_conf}",
        f"dpi: {args.dpi}",
        f"doc_type: {args.doc_type}",
        f"src_lang: {src_lang}",
        f"tgt_lang: {tgt_lang}",
        f"ocr_lang: {ocr_lang}",
        f"timestamp: {_now_iso()}",
    ]
    report = "\n".join(report_lines) + "\n"

    proof = {
        "input": str(in_path),
        "output": str(out_path),
        "engine": engine_display,
        "input_sha256": _sha256_file(in_path),
        "output_sha256": _sha256_file(out_path),
        "stats": stats,
        "config": {
            "dpi": args.dpi,
            "min_conf": args.min_conf,
            "engine": engine_display,
            "doc_type": args.doc_type,
            "src_lang": src_lang,
            "tgt_lang": tgt_lang,
            "ocr_lang": ocr_lang,
        },
        "versions": {
            "pymupdf": getattr(fitz, "__version__", None),
            "pytesseract": getattr(pytesseract, "__version__", None),
            "tesseract": str(pytesseract.get_tesseract_version()),
            "opencv": getattr(cv2, "__version__", None),
            "pillow": getattr(sys.modules.get("PIL"), "__version__", None),
            "genai": getattr(sys.modules.get("google.generativeai"), "__version__", None) if GENAI_AVAILABLE else None,
        },
        "timestamp": _now_iso(),
    }

    write_exports(out_path, all_blocks, mapping, report, proof)
    print(f"[DONE] PDF traduzido gerado: {out_path}")
    print(f"[STATS] {stats['blocks_translated']} traduzidos, {stats['blocks_errors']} erros, {stats['blocks_skipped']} ignorados")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

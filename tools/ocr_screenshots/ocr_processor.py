# -*- coding: utf-8 -*-
"""
OCR por screenshots com pre-processamento por perfil de console.

Saida principal:
- Lista de deteccoes (texto, bbox, confianca, engine) por imagem.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None  # type: ignore[assignment]

try:
    import cv2
except Exception:  # pragma: no cover
    cv2 = None  # type: ignore[assignment]

try:
    from PIL import Image, ImageFilter, ImageOps
except Exception as exc:  # pragma: no cover
    raise RuntimeError("Pillow e obrigatorio para OCR por screenshots.") from exc

try:
    import pytesseract
except Exception as exc:  # pragma: no cover
    raise RuntimeError("pytesseract e obrigatorio para OCR por screenshots.") from exc


CONSOLE_ALIASES: Dict[str, str] = {
    "master": "master_system",
    "sms": "master_system",
    "mega_drive": "megadrive",
    "genesis": "megadrive",
    "md": "megadrive",
    "sfc": "snes",
    "super_nintendo": "snes",
    "famicon": "nes",
}

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tga", ".webp"}
WS_RE = re.compile(r"\s+")
RESAMPLE_NEAREST = getattr(getattr(Image, "Resampling", Image), "NEAREST")


_EASYOCR_CACHE: Dict[Tuple[str, ...], Any] = {}


def _default_logger(message: str) -> None:
    print(message, flush=True)


def _normalize_console(console: str) -> str:
    raw = str(console or "").strip().lower()
    if not raw:
        return ""
    return CONSOLE_ALIASES.get(raw, raw)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_profiles_path() -> Path:
    return _project_root() / "config" / "ocr_profiles.json"


def load_ocr_profiles(config_path: Optional[Path] = None) -> Dict[str, Any]:
    path = (config_path or default_profiles_path()).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"OCR profiles nao encontrado: {path}")
    obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    if not isinstance(obj, dict):
        raise RuntimeError(f"OCR profiles invalido (esperado objeto): {path}")
    profiles = obj.get("profiles", {})
    defaults = obj.get("default", {})
    if not isinstance(profiles, dict):
        profiles = {}
    if not isinstance(defaults, dict):
        defaults = {}
    return {
        "schema": str(obj.get("schema", "") or ""),
        "default": dict(defaults),
        "profiles": dict(profiles),
        "path": str(path),
    }


def resolve_console_profile(
    console: str,
    config_path: Optional[Path] = None,
) -> Dict[str, Any]:
    payload = load_ocr_profiles(config_path=config_path)
    defaults = dict(payload.get("default", {}))
    profiles = dict(payload.get("profiles", {}))
    console_norm = _normalize_console(console)
    profile = dict(defaults)
    profile.update(dict(profiles.get(console_norm, {})))
    profile["console"] = console_norm
    profile["profiles_path"] = str(payload.get("path", ""))
    return profile


def _iter_images(input_folder: Path) -> List[Path]:
    if not input_folder.exists() or not input_folder.is_dir():
        raise FileNotFoundError(f"Pasta de screenshots nao encontrada: {input_folder}")
    out: List[Path] = []
    for item in sorted(input_folder.iterdir(), key=lambda p: p.name.lower()):
        if not item.is_file():
            continue
        if item.suffix.lower() in IMAGE_EXTENSIONS:
            out.append(item)
    return out


def _to_odd(value: int, fallback: int = 3) -> int:
    v = int(value or 0)
    if v <= 1:
        v = int(fallback)
    if v % 2 == 0:
        v += 1
    return max(3, v)


def _pil_to_rgb(image: Image.Image) -> Image.Image:
    if image.mode != "RGB":
        return image.convert("RGB")
    return image


def _preprocess_with_cv2(image: Image.Image, profile: Dict[str, Any]) -> Image.Image:
    if cv2 is None or np is None:
        return image

    scale = float(profile.get("scale", 1.0) or 1.0)
    threshold_mode = str(profile.get("threshold_mode", "adaptive") or "adaptive").strip().lower()
    threshold_value = int(profile.get("threshold_value", 128) or 128)
    adaptive_block_size = _to_odd(int(profile.get("adaptive_block_size", 31) or 31), fallback=31)
    adaptive_c = int(profile.get("adaptive_c", 8) or 8)
    blur_kernel = int(profile.get("otsu_blur_kernel", 3) or 3)
    morph_open = int(profile.get("morphology_open", 0) or 0)
    morph_close = int(profile.get("morphology_close", 0) or 0)
    sharpen = bool(profile.get("sharpen", False))
    invert = bool(profile.get("invert", False))

    arr = np.array(_pil_to_rgb(image))
    if scale > 1.01:
        h, w = arr.shape[:2]
        arr = cv2.resize(
            arr,
            (max(1, int(round(w * scale))), max(1, int(round(h * scale)))),
            interpolation=cv2.INTER_NEAREST,
        )
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)

    if threshold_mode == "adaptive":
        bw = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            adaptive_block_size,
            adaptive_c,
        )
    elif threshold_mode == "otsu":
        k = _to_odd(max(3, blur_kernel), fallback=3)
        blur = cv2.GaussianBlur(gray, (k, k), 0)
        _, bw = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    else:
        _, bw = cv2.threshold(gray, threshold_value, 255, cv2.THRESH_BINARY)

    if sharpen:
        kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
        bw = cv2.filter2D(bw, -1, kernel)

    if morph_close > 0:
        k = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        bw = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, k, iterations=max(1, morph_close))
    if morph_open > 0:
        k = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        bw = cv2.morphologyEx(bw, cv2.MORPH_OPEN, k, iterations=max(1, morph_open))

    if invert:
        bw = cv2.bitwise_not(bw)
    return Image.fromarray(bw).convert("RGB")


def _preprocess_with_pil(image: Image.Image, profile: Dict[str, Any]) -> Image.Image:
    scale = float(profile.get("scale", 1.0) or 1.0)
    threshold_value = int(profile.get("threshold_value", 128) or 128)
    sharpen = bool(profile.get("sharpen", False))
    invert = bool(profile.get("invert", False))

    img = _pil_to_rgb(image)
    if scale > 1.01:
        w, h = img.size
        img = img.resize(
            (max(1, int(round(w * scale))), max(1, int(round(h * scale)))),
            RESAMPLE_NEAREST,
        )
    gray = img.convert("L")
    if sharpen:
        gray = gray.filter(ImageFilter.SHARPEN)
    bw = gray.point(lambda x: 255 if x >= threshold_value else 0, mode="1").convert("L")
    if invert:
        bw = ImageOps.invert(bw)
    return bw.convert("RGB")


def preprocess_image_for_console(
    image: Image.Image,
    profile: Dict[str, Any],
) -> Image.Image:
    """Aplica pre-processamento conforme perfil do console."""
    if cv2 is not None and np is not None:
        return _preprocess_with_cv2(image, profile)
    return _preprocess_with_pil(image, profile)


def _sanitize_text(value: Any) -> str:
    txt = str(value or "")
    txt = txt.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    txt = WS_RE.sub(" ", txt).strip()
    return txt


def _run_tesseract(
    image: Image.Image,
    profile: Dict[str, Any],
    min_confidence: float,
) -> List[Dict[str, Any]]:
    lang = str(profile.get("tesseract_lang", "por") or "por").strip()
    psm = int(profile.get("tesseract_psm", 6) or 6)
    oem = int(profile.get("tesseract_oem", 3) or 3)
    extra_config = str(profile.get("tesseract_extra_config", "") or "").strip()
    config = f"--oem {oem} --psm {psm}"
    if extra_config:
        config += f" {extra_config}"
    try:
        data = pytesseract.image_to_data(
            image,
            output_type=pytesseract.Output.DICT,
            lang=lang,
            config=config,
        )
    except Exception:
        # Fallback seguro para quando o idioma nao estiver instalado.
        try:
            data = pytesseract.image_to_data(
                image,
                output_type=pytesseract.Output.DICT,
                lang="eng",
                config=config,
            )
        except Exception:
            return []

    out: List[Dict[str, Any]] = []
    n = len(data.get("text", []))
    for i in range(n):
        text = _sanitize_text(data.get("text", [""])[i])
        if not text:
            continue
        conf_raw = data.get("conf", ["-1"])[i]
        try:
            conf = float(conf_raw) / 100.0
        except Exception:
            conf = 0.0
        if conf < float(min_confidence):
            continue
        left = int(data.get("left", [0])[i] or 0)
        top = int(data.get("top", [0])[i] or 0)
        width = int(data.get("width", [0])[i] or 0)
        height = int(data.get("height", [0])[i] or 0)
        if width <= 0 or height <= 0:
            continue
        out.append(
            {
                "text": text,
                "bbox": [left, top, left + width, top + height],
                "confidence": round(max(0.0, min(1.0, conf)), 4),
                "engine": "tesseract",
            }
        )
    return out


def _get_easyocr_reader(langs: List[str]) -> Optional[Any]:
    try:
        import easyocr  # type: ignore
    except Exception:
        return None
    key = tuple(sorted(str(x).strip() for x in langs if str(x).strip()))
    if not key:
        key = ("en",)
    if key in _EASYOCR_CACHE:
        return _EASYOCR_CACHE[key]
    reader = easyocr.Reader(list(key), gpu=False)
    _EASYOCR_CACHE[key] = reader
    return reader


def _run_easyocr(
    image: Image.Image,
    profile: Dict[str, Any],
    min_confidence: float,
) -> List[Dict[str, Any]]:
    reader = _get_easyocr_reader(list(profile.get("easyocr_langs", ["pt", "en"])))
    if reader is None:
        return []
    if np is None:
        return []

    arr = np.array(image.convert("RGB"))
    out: List[Dict[str, Any]] = []
    try:
        results = reader.readtext(arr)
    except Exception:
        return out

    for row in results:
        if not isinstance(row, (list, tuple)) or len(row) < 3:
            continue
        poly = row[0]
        text = _sanitize_text(row[1])
        conf = float(row[2] or 0.0)
        if not text or conf < float(min_confidence):
            continue
        try:
            xs = [int(float(pt[0])) for pt in poly]
            ys = [int(float(pt[1])) for pt in poly]
        except Exception:
            continue
        if not xs or not ys:
            continue
        x1, x2 = min(xs), max(xs)
        y1, y2 = min(ys), max(ys)
        if x2 <= x1 or y2 <= y1:
            continue
        out.append(
            {
                "text": text,
                "bbox": [x1, y1, x2, y2],
                "confidence": round(max(0.0, min(1.0, conf)), 4),
                "engine": "easyocr",
            }
        )
    return out


def _average_confidence(rows: List[Dict[str, Any]]) -> float:
    if not rows:
        return 0.0
    return float(sum(float(r.get("confidence", 0.0) or 0.0) for r in rows) / max(1, len(rows)))


def process_screenshot_file(
    image_path: Path,
    profile: Dict[str, Any],
    min_confidence: float = 0.6,
) -> Dict[str, Any]:
    """Executa OCR em uma imagem e decide fallback quando necessario."""
    image = Image.open(image_path).convert("RGB")
    processed = preprocess_image_for_console(image, profile)

    tess_rows = _run_tesseract(
        processed,
        profile=profile,
        min_confidence=min_confidence,
    )
    tess_avg = _average_confidence(tess_rows)

    use_easyocr = bool(profile.get("easyocr_fallback", False))
    if not tess_rows:
        # Degradação segura: se Tesseract indisponível/sem resultado, tenta EasyOCR.
        use_easyocr = True
    fallback_threshold = float(profile.get("fallback_conf_threshold", 0.55) or 0.55)
    final_rows = list(tess_rows)
    engine_used = "tesseract"

    if use_easyocr and (not tess_rows or tess_avg < fallback_threshold):
        easy_rows = _run_easyocr(
            processed,
            profile=profile,
            min_confidence=min_confidence,
        )
        easy_avg = _average_confidence(easy_rows)
        if easy_rows and (easy_avg >= tess_avg or not tess_rows):
            final_rows = easy_rows
            engine_used = "easyocr"

    return {
        "image_path": str(image_path),
        "detections": final_rows,
        "avg_confidence": round(_average_confidence(final_rows), 4),
        "engine_used": engine_used,
        "detections_total": int(len(final_rows)),
    }


def process_screenshots_folder(
    input_folder: Path,
    console: str,
    min_confidence: float = 0.6,
    config_path: Optional[Path] = None,
    logger: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """
    Processa todas as screenshots de uma pasta.

    Retorno:
    - rows: lista plana de deteccoes com metadados de imagem
    - images: resumo por imagem
    """
    log = logger or _default_logger
    profile = resolve_console_profile(console=console, config_path=config_path)
    images = _iter_images(input_folder.expanduser().resolve())
    log(
        "[OCR] Perfil carregado: "
        f"{profile.get('console')} | scale={profile.get('scale')} | "
        f"threshold={profile.get('threshold_mode')}"
    )

    all_rows: List[Dict[str, Any]] = []
    image_summaries: List[Dict[str, Any]] = []
    for image_path in images:
        info = process_screenshot_file(
            image_path=image_path,
            profile=profile,
            min_confidence=min_confidence,
        )
        image_summaries.append(info)
        for det in info.get("detections", []):
            row = {
                "image_path": str(image_path),
                "console": str(profile.get("console", "") or ""),
                "text": str(det.get("text", "") or ""),
                "bbox": list(det.get("bbox", [])),
                "confidence": float(det.get("confidence", 0.0) or 0.0),
                "engine": str(det.get("engine", info.get("engine_used", "tesseract")) or "tesseract"),
            }
            all_rows.append(row)
        log(
            "[OCR] "
            f"{image_path.name}: deteccoes={info.get('detections_total', 0)} "
            f"avg_conf={info.get('avg_confidence', 0.0):.3f} "
            f"engine={info.get('engine_used', 'tesseract')}"
        )

    avg_conf = _average_confidence(all_rows)
    return {
        "console": str(profile.get("console", "") or ""),
        "profile": profile,
        "images_total": int(len(images)),
        "detections_total": int(len(all_rows)),
        "avg_confidence": round(avg_conf, 4),
        "images": image_summaries,
        "rows": all_rows,
    }

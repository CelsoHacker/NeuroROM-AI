# -*- coding: utf-8 -*-
"""
Matching OCR -> glyph_hash desconhecido para expandir fontmap dinamico.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None  # type: ignore[assignment]

try:
    from PIL import Image
except Exception as exc:  # pragma: no cover
    raise RuntimeError("Pillow e obrigatorio para glyph matcher.") from exc

from .ocr_processor import (
    preprocess_image_for_console,
    process_screenshots_folder,
    resolve_console_profile,
)


HEX_HASH_RE = re.compile(r"^[0-9A-F]{8}$")
HEX_PATTERN_RE = re.compile(r"^[0-9A-F]+$")
CONTROL_RE = re.compile(r"[\x00-\x1F\x7F]")
WS_RE = re.compile(r"\s+")
RESAMPLE_NEAREST = getattr(getattr(Image, "Resampling", Image), "NEAREST")
RESAMPLE_LANCZOS = getattr(getattr(Image, "Resampling", Image), "LANCZOS")


def _default_logger(message: str) -> None:
    print(message, flush=True)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _sanitize_text(value: Any) -> str:
    txt = str(value or "")
    txt = CONTROL_RE.sub("", txt)
    txt = WS_RE.sub(" ", txt).strip()
    return txt


def _normalize_hash(value: Any) -> Optional[str]:
    txt = str(value or "").strip().upper()
    if txt.startswith("0X"):
        txt = txt[2:]
    if HEX_HASH_RE.fullmatch(txt):
        return txt
    return None


def _parse_tile_key(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, int):
        return int(value)
    txt = str(value or "").strip()
    if not txt:
        return None
    if txt.lower().startswith("0x"):
        try:
            return int(txt, 16)
        except Exception:
            return None
    try:
        return int(txt)
    except Exception:
        return None


def _normalize_pattern_hex(value: Any) -> str:
    txt = str(value or "").strip().upper()
    if txt.startswith("0X"):
        txt = txt[2:]
    txt = re.sub(r"[^0-9A-F]", "", txt)
    if not txt or not HEX_PATTERN_RE.fullmatch(txt):
        return ""
    if len(txt) % 2 != 0:
        return ""
    return txt


def _parse_bbox(raw: Any) -> Optional[Tuple[int, int, int, int]]:
    if not isinstance(raw, (list, tuple)) or len(raw) != 4:
        return None
    try:
        x1 = int(float(raw[0]))
        y1 = int(float(raw[1]))
        x2 = int(float(raw[2]))
        y2 = int(float(raw[3]))
    except Exception:
        return None
    if x2 <= x1 or y2 <= y1:
        return None
    return (x1, y1, x2, y2)


def _iter_char_bboxes_from_detection(
    text: str,
    bbox: Tuple[int, int, int, int],
) -> List[Tuple[str, Tuple[int, int, int, int]]]:
    """
    Expande uma detecção OCR em caracteres unitários.
    Para palavras, divide horizontalmente o bbox em N fatias.
    """
    clean_chars = [ch for ch in str(text or "") if not ch.isspace()]
    if not clean_chars:
        return []
    if len(clean_chars) == 1:
        return [(clean_chars[0], bbox)]

    x1, y1, x2, y2 = bbox
    width = max(1, x2 - x1)
    total = max(1, len(clean_chars))
    step = float(width) / float(total)
    out: List[Tuple[str, Tuple[int, int, int, int]]] = []
    for idx, ch in enumerate(clean_chars):
        cx1 = int(round(x1 + (step * idx)))
        cx2 = int(round(x1 + (step * (idx + 1))))
        if cx2 <= cx1:
            cx2 = cx1 + 1
        out.append((ch, (cx1, y1, cx2, y2)))
    return out


def _fnv1a_32_hex(data: bytes) -> str:
    h = 2166136261
    for b in data:
        h ^= int(b)
        h = (h * 16777619) & 0xFFFFFFFF
    return f"{h:08X}"


def _decode_pattern_to_bool_grid(pattern: bytes) -> Optional[List[int]]:
    if len(pattern) == 32:
        bits: List[int] = []
        for row in range(8):
            b0, b1, b2, b3 = pattern[row * 4 : row * 4 + 4]
            for col in range(8):
                bit = 7 - col
                value = (
                    ((b0 >> bit) & 1)
                    | (((b1 >> bit) & 1) << 1)
                    | (((b2 >> bit) & 1) << 2)
                    | (((b3 >> bit) & 1) << 3)
                )
                bits.append(1 if value > 0 else 0)
        return bits
    if len(pattern) == 16:
        bits = []
        for row in range(8):
            b0, b1 = pattern[row * 2 : row * 2 + 2]
            for col in range(8):
                bit = 7 - col
                value = ((b0 >> bit) & 1) | (((b1 >> bit) & 1) << 1)
                bits.append(1 if value > 0 else 0)
        return bits
    return None


def _encode_grid_to_pattern(bits64: List[int], bytes_len: int) -> bytes:
    if bytes_len <= 16:
        out = bytearray(16)
        for row in range(8):
            b0 = 0
            b1 = 0
            for col in range(8):
                bit = 7 - col
                idx = row * 8 + col
                value = 3 if int(bits64[idx]) else 0
                b0 |= ((value >> 0) & 1) << bit
                b1 |= ((value >> 1) & 1) << bit
            out[row * 2] = b0
            out[row * 2 + 1] = b1
        return bytes(out)

    out = bytearray(32)
    for row in range(8):
        p0 = p1 = p2 = p3 = 0
        for col in range(8):
            bit = 7 - col
            idx = row * 8 + col
            value = 15 if int(bits64[idx]) else 0
            p0 |= ((value >> 0) & 1) << bit
            p1 |= ((value >> 1) & 1) << bit
            p2 |= ((value >> 2) & 1) << bit
            p3 |= ((value >> 3) & 1) << bit
        out[row * 4 + 0] = p0
        out[row * 4 + 1] = p1
        out[row * 4 + 2] = p2
        out[row * 4 + 3] = p3
    return bytes(out)


def _crop_to_pattern_bytes(
    image: Image.Image,
    bbox: Tuple[int, int, int, int],
    profile: Dict[str, Any],
    bytes_len: int,
) -> bytes:
    crop = image.crop(bbox).convert("L")

    glyph_scale = float(profile.get("glyph_scale", 1.0) or 1.0)
    if glyph_scale > 1.01:
        w, h = crop.size
        crop = crop.resize(
            (max(1, int(round(w * glyph_scale))), max(1, int(round(h * glyph_scale)))),
            RESAMPLE_NEAREST,
        )

    crop = crop.resize((8, 8), RESAMPLE_LANCZOS)
    arr = np.array(crop) if np is not None else None
    threshold = int(profile.get("glyph_threshold", profile.get("threshold_value", 128)) or 128)
    auto_invert = bool(profile.get("glyph_auto_invert", True))

    bits64: List[int] = []
    if arr is not None:
        binary = (arr < threshold).astype("uint8")
        ratio_on = float(binary.mean())
        if auto_invert and ratio_on > 0.70:
            binary = 1 - binary
        for y in range(8):
            for x in range(8):
                bits64.append(int(binary[y, x] > 0))
    else:
        for px in crop.getdata():
            bits64.append(1 if int(px) < threshold else 0)
        if auto_invert:
            ratio_on = float(sum(bits64)) / max(1, len(bits64))
            if ratio_on > 0.70:
                bits64 = [0 if b else 1 for b in bits64]

    return _encode_grid_to_pattern(bits64, bytes_len=bytes_len)


def _similarity_bits(a: bytes, b: bytes, max_shift: int = 0) -> float:
    ga = _decode_pattern_to_bool_grid(a)
    gb = _decode_pattern_to_bool_grid(b)
    if ga is None or gb is None or len(ga) != len(gb):
        return 0.0

    shift = max(0, int(max_shift or 0))
    if shift <= 0:
        equal = sum(1 for i in range(len(ga)) if ga[i] == gb[i])
        return float(equal / max(1, len(ga)))

    side = int(round(len(ga) ** 0.5))
    if side <= 0:
        return 0.0

    best = 0.0
    for dy in range(-shift, shift + 1):
        for dx in range(-shift, shift + 1):
            total = 0
            equal = 0
            for y in range(side):
                yb = y + dy
                if yb < 0 or yb >= side:
                    continue
                for x in range(side):
                    xb = x + dx
                    if xb < 0 or xb >= side:
                        continue
                    total += 1
                    if ga[(y * side) + x] == gb[(yb * side) + xb]:
                        equal += 1
            if total <= 0:
                continue
            sim = float(equal / total)
            if sim > best:
                best = sim
    return best


def _safe_read_json(path: Path) -> Dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    if isinstance(obj, dict):
        return obj
    return {}


def _discover_runtime_artifacts(
    runtime_dir: Path,
    crc_hint: Optional[str],
) -> Dict[str, Optional[Path]]:
    crc = str(crc_hint or "").strip().upper()
    if not HEX_HASH_RE.fullmatch(crc):
        crc = ""

    roots: List[Path] = [runtime_dir]
    dyn_dir = runtime_dir / "2_runtime_dyn"
    if dyn_dir.exists():
        roots.insert(0, dyn_dir)

    def _pick(patterns: List[str]) -> Optional[Path]:
        for root in roots:
            for patt in patterns:
                for cand in sorted(root.glob(patt)):
                    if cand.is_file() and cand.stat().st_size > 0:
                        return cand
        return None

    unknown_patterns: List[str] = []
    bootstrap_patterns: List[str] = []
    fontmap_patterns: List[str] = []
    if crc:
        unknown_patterns.extend(
            [
                f"{crc}_unknown_glyphs.jsonl",
            ]
        )
        bootstrap_patterns.extend(
            [
                f"{crc}_dyn_fontmap_bootstrap.json",
            ]
        )
        fontmap_patterns.extend(
            [
                f"{crc}_dyn_fontmap_enhanced.json",
                f"{crc}_fontmap_enhanced.json",
                f"{crc}_dyn_fontmap_auto_from_tbl.json",
                f"{crc}_dyn_fontmap_manual.json",
                f"{crc}_dyn_fontmap.json",
            ]
        )
    unknown_patterns.append("*_unknown_glyphs.jsonl")
    bootstrap_patterns.append("*_dyn_fontmap_bootstrap.json")
    fontmap_patterns.extend(
        [
            "*_dyn_fontmap_enhanced.json",
            "*_fontmap_enhanced.json",
            "*_dyn_fontmap_auto_from_tbl.json",
            "*_dyn_fontmap_manual.json",
            "*_dyn_fontmap.json",
        ]
    )

    return {
        "unknown_jsonl": _pick(unknown_patterns),
        "bootstrap_json": _pick(bootstrap_patterns),
        "fontmap_json": _pick(fontmap_patterns),
    }


def _load_unknown_catalog(
    unknown_jsonl: Optional[Path],
    bootstrap_json: Optional[Path],
) -> Dict[str, Dict[str, Any]]:
    catalog: Dict[str, Dict[str, Any]] = {}

    if unknown_jsonl and unknown_jsonl.exists():
        for line in unknown_jsonl.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if not isinstance(obj, dict):
                continue
            if str(obj.get("type", "")).lower() == "meta":
                continue
            glyph_hash = _normalize_hash(obj.get("glyph_hash"))
            if not glyph_hash:
                continue
            entry = catalog.setdefault(
                glyph_hash,
                {
                    "glyph_hash": glyph_hash,
                    "hits": 0,
                    "pattern_hex": "",
                    "sample_contexts": [],
                },
            )
            entry["hits"] = int(entry.get("hits", 0) or 0) + int(obj.get("hits", 0) or 0)
            pattern_hex = _normalize_pattern_hex(obj.get("pattern_hex"))
            if pattern_hex and not entry.get("pattern_hex"):
                entry["pattern_hex"] = pattern_hex

    if bootstrap_json and bootstrap_json.exists():
        obj = _safe_read_json(bootstrap_json)
        rows = obj.get("rows", [])
        if isinstance(rows, list):
            for item in rows:
                if not isinstance(item, dict):
                    continue
                glyph_hash = _normalize_hash(item.get("glyph_hash"))
                if not glyph_hash:
                    continue
                entry = catalog.setdefault(
                    glyph_hash,
                    {
                        "glyph_hash": glyph_hash,
                        "hits": 0,
                        "pattern_hex": "",
                        "sample_contexts": [],
                    },
                )
                entry["hits"] = max(
                    int(entry.get("hits", 0) or 0),
                    int(item.get("hits", 0) or 0),
                )
                pattern_hex = _normalize_pattern_hex(item.get("pattern_hex"))
                if pattern_hex and not entry.get("pattern_hex"):
                    entry["pattern_hex"] = pattern_hex
                contexts = item.get("sample_contexts", [])
                if isinstance(contexts, list):
                    cur = list(entry.get("sample_contexts", []))
                    seen = set(cur)
                    for ctx in contexts:
                        t = _sanitize_text(ctx)
                        if not t or t in seen:
                            continue
                        cur.append(t)
                        seen.add(t)
                        if len(cur) >= 8:
                            break
                    entry["sample_contexts"] = cur
    return catalog


def _load_existing_fontmap(path: Optional[Path]) -> Dict[str, Dict[Any, str]]:
    empty = {"glyph_hash_to_char": {}, "tile_to_char": {}}
    if path is None or not path.exists():
        return empty
    obj = _safe_read_json(path)
    if not isinstance(obj, dict):
        return empty

    glyph_out: Dict[str, str] = {}
    tile_out: Dict[int, str] = {}
    containers: List[Dict[str, Any]] = []

    glyph_part = obj.get("glyph_hash_to_char")
    tile_part = obj.get("tile_to_char")
    mappings_part = obj.get("mappings")
    if isinstance(glyph_part, dict):
        containers.append({"kind": "hash", "map": glyph_part})
    if isinstance(mappings_part, dict):
        containers.append({"kind": "hash", "map": mappings_part})
    if isinstance(tile_part, dict):
        containers.append({"kind": "tile", "map": tile_part})
    if not containers:
        containers.append({"kind": "mixed", "map": obj})

    for chunk in containers:
        kind = str(chunk.get("kind", "mixed") or "mixed")
        raw_map = chunk.get("map")
        if not isinstance(raw_map, dict):
            continue
        for key, value in raw_map.items():
            txt = _sanitize_text(value)
            if not txt:
                continue
            ch = txt[0]
            glyph_hash = _normalize_hash(key)
            if glyph_hash and kind in {"hash", "mixed"}:
                glyph_out[glyph_hash] = ch
                continue
            tile_key = _parse_tile_key(key)
            if tile_key is not None and kind in {"tile", "mixed"}:
                tile_out[int(tile_key)] = ch

    return {"glyph_hash_to_char": glyph_out, "tile_to_char": tile_out}


def _write_jsonl(path: Path, rows: List[Dict[str, Any]], meta: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(meta, ensure_ascii=False) + "\n")
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _build_codex_dataset(
    codex_dir: Path,
    evidence_rows: List[Dict[str, Any]],
    image_cache: Dict[str, Image.Image],
) -> Tuple[int, Optional[Path]]:
    if not evidence_rows:
        return 0, None
    codex_dir.mkdir(parents=True, exist_ok=True)

    meta_rows: List[Dict[str, Any]] = []
    saved = 0
    for idx, ev in enumerate(evidence_rows):
        image_path = str(ev.get("image_path", "") or "")
        bbox = _parse_bbox(ev.get("bbox"))
        if not image_path or bbox is None:
            continue
        img = image_cache.get(image_path)
        if img is None:
            continue
        crop = img.crop(bbox)
        glyph_hash = str(ev.get("glyph_hash", "") or "")
        char = str(ev.get("char", "") or "")
        crop_name = f"{idx:05d}_{glyph_hash}_{ord(char) if char else 0}.png"
        crop_path = codex_dir / crop_name
        crop.save(crop_path)
        saved += 1
        row = dict(ev)
        row["crop_path"] = str(crop_path)
        meta_rows.append(row)

    if not meta_rows:
        return 0, None

    meta_path = codex_dir / "index.jsonl"
    _write_jsonl(
        meta_path,
        meta_rows,
        meta={
            "type": "meta",
            "schema": "neurorom.ocr_codex.v1",
            "rows_total": int(len(meta_rows)),
        },
    )
    return saved, meta_path


def run_ocr_screenshot_pipeline(
    *,
    input_folder: Path,
    runtime_dir: Path,
    console: str,
    min_confidence: float = 0.6,
    min_votes: int = 3,
    update_fontmap: bool = False,
    rom_crc32: Optional[str] = None,
    profiles_path: Optional[Path] = None,
    logger: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """
    Pipeline completo:
    1) OCR por screenshots
    2) Matching para glyph_hash desconhecido
    3) Fontmap enhanced + relatorios
    """
    log = logger or _default_logger
    runtime_dir = runtime_dir.expanduser().resolve()
    input_folder = input_folder.expanduser().resolve()
    profile = resolve_console_profile(console=console, config_path=profiles_path)

    runtime_artifacts = _discover_runtime_artifacts(runtime_dir=runtime_dir, crc_hint=rom_crc32)
    unknown_jsonl = runtime_artifacts.get("unknown_jsonl")
    bootstrap_json = runtime_artifacts.get("bootstrap_json")
    fontmap_base = runtime_artifacts.get("fontmap_json")

    if unknown_jsonl is None and bootstrap_json is None:
        raise FileNotFoundError(
            "Nao foi possivel localizar unknown_glyphs/bootstrap no runtime_dir."
        )

    catalog = _load_unknown_catalog(
        unknown_jsonl=unknown_jsonl,
        bootstrap_json=bootstrap_json,
    )
    if not catalog:
        raise RuntimeError("Catalogo de glyphs desconhecidos vazio.")

    crc = str(rom_crc32 or "").strip().upper()
    if not HEX_HASH_RE.fullmatch(crc):
        source_name = ""
        if unknown_jsonl is not None:
            source_name = unknown_jsonl.name
        elif bootstrap_json is not None:
            source_name = bootstrap_json.name
        m = re.search(r"([0-9A-F]{8})", source_name.upper())
        crc = m.group(1) if m else "UNKNOWN000"

    ocr_result = process_screenshots_folder(
        input_folder=input_folder,
        console=console,
        min_confidence=min_confidence,
        config_path=profiles_path,
        logger=log,
    )
    ocr_rows = list(ocr_result.get("rows", []))

    bytes_len = int(profile.get("tile_pattern_bytes", 32) or 32)
    min_similarity = float(profile.get("glyph_similarity_threshold", 0.90) or 0.90)
    max_shift = max(0, int(profile.get("glyph_similarity_max_shift", 1) or 1))

    unknown_patterns: Dict[str, bytes] = {}
    for glyph_hash, item in catalog.items():
        pattern_hex = _normalize_pattern_hex(item.get("pattern_hex"))
        if not pattern_hex:
            continue
        try:
            raw = bytes.fromhex(pattern_hex)
        except Exception:
            continue
        if len(raw) not in {16, 32}:
            continue
        unknown_patterns[glyph_hash] = raw

    image_cache: Dict[str, Image.Image] = {}
    votes: Dict[str, Counter[str]] = defaultdict(Counter)
    evidence: List[Dict[str, Any]] = []

    def _get_image(path: str) -> Optional[Image.Image]:
        if path in image_cache:
            return image_cache[path]
        p = Path(path)
        if not p.exists():
            return None
        try:
            img_src = Image.open(p).convert("RGB")
            # OCR roda sobre imagem pre-processada (com escala/filtros).
            # O crop precisa usar o mesmo espaço de coordenadas do bbox.
            img = preprocess_image_for_console(img_src, profile)
        except Exception:
            return None
        image_cache[path] = img
        return img

    for row in ocr_rows:
        text = _sanitize_text(row.get("text"))
        bbox = _parse_bbox(row.get("bbox"))
        if not text or bbox is None:
            continue
        image_path = str(row.get("image_path", "") or "")
        img = _get_image(image_path)
        if img is None:
            continue
        for char, char_bbox in _iter_char_bboxes_from_detection(text=text, bbox=bbox):
            pattern_bytes = _crop_to_pattern_bytes(
                image=img,
                bbox=char_bbox,
                profile=profile,
                bytes_len=bytes_len,
            )
            crop_hash = _fnv1a_32_hex(pattern_bytes)
            matched_hash = None
            matched_similarity = 0.0

            if crop_hash in catalog:
                matched_hash = crop_hash
                matched_similarity = 1.0
            else:
                for glyph_hash, ref_pattern in unknown_patterns.items():
                        sim = _similarity_bits(
                            pattern_bytes,
                            ref_pattern,
                            max_shift=max_shift,
                        )
                        if sim >= min_similarity and sim > matched_similarity:
                            matched_hash = glyph_hash
                            matched_similarity = sim

            if matched_hash is None:
                continue
            votes[matched_hash][char] += 1
            evidence.append(
                {
                    "glyph_hash": matched_hash,
                    "char": char,
                    "votes_now": int(votes[matched_hash][char]),
                    "confidence": float(row.get("confidence", 0.0) or 0.0),
                    "similarity": float(round(matched_similarity, 4)),
                    "image_path": image_path,
                    "bbox": list(char_bbox),
                    "ocr_engine": str(row.get("engine", "tesseract") or "tesseract"),
                    "ocr_text": text,
                    "crop_hash": crop_hash,
                }
            )

    resolved_map: Dict[str, str] = {}
    unresolved_by_votes: Dict[str, Dict[str, int]] = {}
    for glyph_hash, counter in votes.items():
        if not counter:
            continue
        best_char, best_count = counter.most_common(1)[0]
        if int(best_count) >= int(min_votes):
            resolved_map[glyph_hash] = str(best_char)[:1]
        else:
            unresolved_by_votes[glyph_hash] = {k: int(v) for k, v in counter.items()}

    existing_bundle = _load_existing_fontmap(fontmap_base)
    existing_map = {
        str(k): str(v)
        for k, v in dict(existing_bundle.get("glyph_hash_to_char", {})).items()
        if _normalize_hash(k) and _sanitize_text(v)
    }
    existing_tile_map = {
        int(k): str(v)[:1]
        for k, v in dict(existing_bundle.get("tile_to_char", {})).items()
        if _parse_tile_key(k) is not None and _sanitize_text(v)
    }

    # Quando o fontmap ativo não carrega tile_to_char, reaproveita fallback .tbl
    # já gerado no runtime (auto_from_tbl), evitando perda de cobertura entre rodadas.
    auto_tbl_fontmap = None
    if runtime_dir and crc:
        dyn_root = (runtime_dir / "2_runtime_dyn") if (runtime_dir / "2_runtime_dyn").exists() else runtime_dir
        candidate = dyn_root / f"{crc}_dyn_fontmap_auto_from_tbl.json"
        if candidate.exists() and candidate.is_file():
            auto_tbl_fontmap = candidate
    if auto_tbl_fontmap and (
        not existing_tile_map
        or not existing_map
        or (fontmap_base and auto_tbl_fontmap.resolve() != fontmap_base.resolve())
    ):
        auto_bundle = _load_existing_fontmap(auto_tbl_fontmap)
        for k, v in dict(auto_bundle.get("glyph_hash_to_char", {})).items():
            h = _normalize_hash(k)
            if h and h not in existing_map:
                txt = _sanitize_text(v)
                if txt:
                    existing_map[h] = txt[0]
        for k, v in dict(auto_bundle.get("tile_to_char", {})).items():
            tk = _parse_tile_key(k)
            if tk is None or int(tk) in existing_tile_map:
                continue
            txt = _sanitize_text(v)
            if txt:
                existing_tile_map[int(tk)] = txt[0]

    merged_map = dict(existing_map)
    merged_map.update(resolved_map)

    out_dir = (runtime_dir / "2_runtime_dyn") if (runtime_dir / "2_runtime_dyn").exists() else runtime_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    ocr_log_path = out_dir / f"{crc}_ocr_log.jsonl"
    _write_jsonl(
        ocr_log_path,
        rows=evidence,
        meta={
            "type": "meta",
            "schema": "neurorom.ocr_screenshots_log.v1",
            "rom_crc32": crc,
            "console": str(profile.get("console", "") or ""),
            "images_total": int(ocr_result.get("images_total", 0)),
            "detections_total": int(ocr_result.get("detections_total", 0)),
            "matches_total": int(len(evidence)),
        },
    )

    enhanced_path = out_dir / f"{crc}_fontmap_enhanced.json"
    enhanced_payload = {
        "schema": "runtime_dyn_fontmap_enhanced_ocr.v1",
        "rom_crc32": crc,
        "console": str(profile.get("console", "") or ""),
        "base_fontmap_path": str(fontmap_base) if fontmap_base else None,
        "base_fontmap_auto_tbl_path": str(auto_tbl_fontmap) if auto_tbl_fontmap else None,
        "source_unknown_glyphs_jsonl": str(unknown_jsonl) if unknown_jsonl else None,
        "source_bootstrap_json": str(bootstrap_json) if bootstrap_json else None,
        "source_ocr_log_jsonl": str(ocr_log_path),
        "glyph_hash_to_char": dict(sorted(merged_map.items())),
        "tile_to_char": {str(k): v for k, v in sorted(existing_tile_map.items())},
        "new_mappings_from_ocr": dict(sorted(resolved_map.items())),
        "unresolved_votes": unresolved_by_votes,
        "min_votes_applied": int(min_votes),
    }
    enhanced_path.write_text(
        json.dumps(enhanced_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    active_fontmap_path: Optional[Path] = None
    if bool(update_fontmap):
        active_fontmap_path = out_dir / f"{crc}_dyn_fontmap_enhanced.json"
        active_payload = dict(enhanced_payload)
        active_payload["schema"] = "runtime_dyn_fontmap_enhanced_ocr_active.v1"
        active_payload["source_fontmap_enhanced"] = str(enhanced_path)
        active_fontmap_path.write_text(
            json.dumps(active_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    codex_dir = _project_root() / "codex" / crc
    codex_saved, codex_index = _build_codex_dataset(
        codex_dir=codex_dir,
        evidence_rows=evidence,
        image_cache=image_cache,
    )

    report_path = out_dir / f"{crc}_ocr_match_report.txt"
    report_lines = [
        "OCR SCREENSHOTS MATCH REPORT",
        f"ROM_CRC32: {crc}",
        f"CONSOLE: {profile.get('console', '')}",
        f"INPUT_FOLDER: {input_folder}",
        f"IMAGES_TOTAL: {int(ocr_result.get('images_total', 0))}",
        f"OCR_DETECTIONS_TOTAL: {int(ocr_result.get('detections_total', 0))}",
        f"UNKNOWN_GLYPHS_TOTAL: {int(len(catalog))}",
        f"MATCH_EVIDENCE_ROWS: {int(len(evidence))}",
        f"MAPPINGS_ADDED: {int(len(resolved_map))}",
        f"MAPPINGS_TOTAL_ENHANCED: {int(len(merged_map))}",
        f"TILE_FALLBACK_TOTAL: {int(len(existing_tile_map))}",
        f"UNRESOLVED_BY_VOTES: {int(len(unresolved_by_votes))}",
        f"MIN_CONFIDENCE: {float(min_confidence):.4f}",
        f"MIN_VOTES: {int(min_votes)}",
        f"MIN_SIMILARITY: {float(min_similarity):.4f}",
        f"OCR_LOG: {ocr_log_path}",
        f"FONTMAP_ENHANCED: {enhanced_path}",
        f"FONTMAP_ACTIVE: {str(active_fontmap_path) if active_fontmap_path else ''}",
        f"CODEX_DIR: {codex_dir}",
        f"CODEX_SAVED_CROPS: {int(codex_saved)}",
        f"CODEX_INDEX: {str(codex_index) if codex_index else ''}",
        f"UPDATE_FONTMAP: {str(bool(update_fontmap)).lower()}",
    ]
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    status = "PASS" if resolved_map else "WARN"
    return {
        "status": status,
        "mode": "ocr_screenshots",
        "rom_crc32": crc,
        "console": str(profile.get("console", "") or ""),
        "images_total": int(ocr_result.get("images_total", 0)),
        "ocr_detections_total": int(ocr_result.get("detections_total", 0)),
        "unknown_glyphs_total": int(len(catalog)),
        "matches_total": int(len(evidence)),
        "mappings_added": int(len(resolved_map)),
        "mappings_total_enhanced": int(len(merged_map)),
        "unresolved_by_votes": int(len(unresolved_by_votes)),
        "artifacts": {
            "unknown_glyphs_jsonl": str(unknown_jsonl) if unknown_jsonl else "",
            "dyn_fontmap_bootstrap": str(bootstrap_json) if bootstrap_json else "",
            "ocr_log_jsonl": str(ocr_log_path),
            "fontmap_enhanced_json": str(enhanced_path),
            "fontmap_active_json": str(active_fontmap_path) if active_fontmap_path else "",
            "ocr_match_report_txt": str(report_path),
            "codex_dir": str(codex_dir),
            "codex_index_jsonl": str(codex_index) if codex_index else "",
        },
    }

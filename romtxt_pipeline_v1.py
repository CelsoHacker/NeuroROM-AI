#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
romtxt_pipeline_v1.py

Pipeline V1 (NES/SMS/MD/SNES) focado em:
1) Extração (SEM scan cego): a partir de um reinsertion_mapping existente
2) Tradução automática (japonês -> português) via Transformers (NLLB/M2M100)
3) Reinserção estrita mantendo offsets/tamanhos originais

Exports obrigatórios:
- {CRC32}_pure_text.jsonl
- {CRC32}_reinsertion_mapping.json
- {CRC32}_report.txt
- {CRC32}_proof.json

Neutralidade:
- Nunca usa nome do arquivo como identificação no report/log (somente CRC32 e ROM_SIZE).
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import re
import time
import zlib
import unicodedata
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


# =========================
# Utilitários básicos
# =========================

def _read_bytes(path: Path) -> bytes:
    with path.open("rb") as f:
        return f.read()

def _write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        f.write(data)

def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def _compute_crc32_hex(data: bytes) -> str:
    crc = zlib.crc32(data) & 0xFFFFFFFF
    return f"{crc:08X}"

def _safe_json_load(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def _safe_json_dump(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def _jsonl_write(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

def _infer_crc32_from_filename(p: Path) -> Optional[str]:
    m = re.search(r"([0-9A-Fa-f]{8})_reinsertion_mapping\.json$", p.name)
    if m:
        return m.group(1).upper()
    return None

# =========================
# Expansão por pointer tables (SEM scan cego)
# =========================

def _u16(data: bytes, offset: int, endian: str = "little") -> Optional[int]:
    if offset < 0 or offset + 2 > len(data):
        return None
    return int.from_bytes(data[offset:offset+2], endian, signed=False)

def _u24(data: bytes, offset: int, endian: str = "little") -> Optional[int]:
    if offset < 0 or offset + 3 > len(data):
        return None
    return int.from_bytes(data[offset:offset+3], endian, signed=False)

def _resolve_entry_abs(table_off: int, entry_off: int) -> int:
    return entry_off if entry_off >= table_off else (table_off + entry_off)

def _read_until_terminator(rom_bytes: bytes, start: int, terminator: bytes, max_scan: int = 1024) -> Optional[bytes]:
    if start < 0 or start >= len(rom_bytes):
        return None
    if not terminator:
        return None
    tlen = len(terminator)
    limit = min(len(rom_bytes), start + max_scan)
    i = start
    while i + tlen <= limit:
        if rom_bytes[i:i+tlen] == terminator:
            return rom_bytes[start:i]
        i += 1
    return None

def _find_sample_item_dict(mapping_obj: Any) -> Optional[Dict[str, Any]]:
    """
    Procura um item amostra com metadados de ponteiro:
      offset + max_length/max_bytes + source + pointer_table_offset + pointer_entry_offset
    """
    def walk(x):
        if isinstance(x, dict):
            yield x
            for v in x.values():
                yield from walk(v)
        elif isinstance(x, list):
            for v in x:
                yield from walk(v)

    for o in walk(mapping_obj):
        if not isinstance(o, dict):
            continue
        if "offset" not in o:
            continue
        if not any(k in o for k in ("max_length", "max_bytes", "max_len")):
            continue
        if not any(k in o for k in ("source", "source_text")):
            continue
        if "pointer_table_offset" in o and "pointer_entry_offset" in o:
            return o
    return None

def _infer_pointer_delta(rom_bytes: bytes, sample: Dict[str, Any]) -> Optional[int]:
    """
    delta = real_text_offset - raw_pointer_value (u16 LE), se plausível.
    """
    try:
        text_off = _hex_or_int(sample.get("offset"))
        table_off = _hex_or_int(sample.get("pointer_table_offset"))
        entry_off = _hex_or_int(sample.get("pointer_entry_offset"))
        if text_off is None or table_off is None or entry_off is None:
            return None
        entry_abs = _resolve_entry_abs(int(table_off), int(entry_off))
        raw = _u16(rom_bytes, entry_abs, "little")
        if raw is None:
            return None
        delta = int(text_off) - int(raw)
        if 0 <= delta <= len(rom_bytes):
            return delta
        return None
    except Exception:
        return None

def expand_items_from_pointer_tables(mapping_obj: Any, rom_bytes: bytes) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Expande itens a partir de discovered_pointer_tables sem scan cego.

    Segurança:
      - Expande SOMENTE a tabela do item amostra (evita banking/heurísticas perigosas).
    """
    errors: List[Dict[str, Any]] = []
    out_items: List[Dict[str, Any]] = []

    if not isinstance(mapping_obj, dict):
        errors.append({"reason": "mapping_not_dict"})
        return out_items, errors

    sample = _find_sample_item_dict(mapping_obj)
    if not sample:
        errors.append({"reason": "no_sample_item_with_pointer_meta"})
        return out_items, errors

    enc = (sample.get("encoding") or "ascii")
    term_b = _parse_hex_bytes(sample.get("terminator")) or b"\x00"

    table_off = _hex_or_int(sample.get("pointer_table_offset"))
    if table_off is None:
        errors.append({"reason": "sample_missing_pointer_table_offset"})
        return out_items, errors

    table_obj = None
    for t in (mapping_obj.get("discovered_pointer_tables") or []):
        if isinstance(t, dict):
            to = _hex_or_int(t.get("offset")) if t.get("offset") is not None else _hex_or_int(t.get("table_offset"))
            if to == table_off:
                table_obj = t
                break
    if table_obj is None:
        table_obj = {"offset": int(table_off)}

    endian = str(table_obj.get("endian") or table_obj.get("endianness") or "little").lower()
    ptr_size = _hex_or_int(table_obj.get("pointer_size")) or _hex_or_int(table_obj.get("ptr_size")) or 2
    stride = _hex_or_int(table_obj.get("entry_size")) or _hex_or_int(table_obj.get("stride")) or int(ptr_size)
    count = _hex_or_int(table_obj.get("count")) or _hex_or_int(table_obj.get("entries")) or _hex_or_int(table_obj.get("num_entries"))

    max_entries = int(count) if count is not None else 4096
    delta = _infer_pointer_delta(rom_bytes, sample)
    if delta is None:
        delta = 0

    invalid_run = 0
    base_id = _hex_or_int(sample.get("id")) or 0

    for i in range(max_entries):
        entry_abs = int(table_off) + i * int(stride)

        if int(ptr_size) == 2:
            raw = _u16(rom_bytes, entry_abs, endian)
        elif int(ptr_size) == 3:
            raw = _u24(rom_bytes, entry_abs, endian)
        else:
            errors.append({"reason": "unsupported_pointer_size", "ptr_size": int(ptr_size)})
            break

        if raw is None:
            break

        if raw in (0, 0xFFFF, 0xFFFFFF):
            invalid_run += 1
            if count is None and invalid_run >= 64:
                break
            continue
        invalid_run = 0

        text_off = int(raw) + int(delta)
        if text_off < 0 or text_off >= len(rom_bytes):
            continue

        btxt = _read_until_terminator(rom_bytes, text_off, term_b, max_scan=1024)
        if not btxt:
            continue

        try:
            stxt = btxt.decode(enc, errors="ignore")
        except Exception:
            stxt = ""

        if not stxt.strip():
            continue

        max_len = len(btxt) + len(term_b)

        out_items.append({
            "id": int(base_id) + i + 1,
            "offset": int(text_off),
            "max_length": int(max_len),
            "terminator": list(term_b),
            "source": stxt,
            "encoding": enc,
            "pointer_table_offset": int(table_off),
            "pointer_entry_offset": int(i * int(stride)),
        })

    if not out_items:
        errors.append({"reason": "no_items_expanded", "delta": int(delta), "table_offset": int(table_off)})

    return out_items, errors


def _hex_or_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, str):
        s = v.strip()
        if s.lower().startswith("0x"):
            try:
                return int(s, 16)
            except ValueError:
                return None
        try:
            return int(s, 10)
        except ValueError:
            return None
    return None

def _parse_hex_bytes(v: Any) -> Optional[bytes]:
    if v is None:
        return None
    if isinstance(v, (bytes, bytearray)):
        return bytes(v)
    if isinstance(v, list) and all(isinstance(x, int) for x in v):
        return bytes(v)
    if isinstance(v, str):
        s = v.strip().replace(" ", "")
        s = s.replace("\\x", "")
        if len(s) % 2 != 0:
            return None
        try:
            return bytes.fromhex(s)
        except ValueError:
            return None
    return None

def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


# =========================
# Placeholders / tokens
# =========================

PLACEHOLDER_PATTERNS: List[re.Pattern] = [
    re.compile(r"%[0-9]*[ds]"),
    re.compile(r"\{[0-9]+\}"),
    re.compile(r"\{[A-Z0-9_]+\}"),
    re.compile(r"\[[A-Z0-9_]+\]"),
    re.compile(r"<[^<>]{1,16}>"),
]

def extract_placeholders(text: str) -> List[str]:
    found: List[str] = []
    for pat in PLACEHOLDER_PATTERNS:
        found.extend(pat.findall(text))
    return found

def placeholders_equal(a: str, b: str) -> bool:
    pa = sorted(extract_placeholders(a))
    pb = sorted(extract_placeholders(b))
    return pa == pb


def latinize_pt_ascii(text: str) -> str:
    """
    Converte texto PT para ASCII seguro (remove acentos) para ROMs/fontes ASCII.
    Mantém placeholders/tokens intactos.
    """
    ph = {}

    def _protect(m):
        key = f"__PH{len(ph)}__"
        ph[key] = m.group(0)
        return key

    protected = text
    for pat in PLACEHOLDER_PATTERNS:
        protected = pat.sub(_protect, protected)

    norm = unicodedata.normalize("NFKD", protected)
    norm = "".join(ch for ch in norm if not unicodedata.combining(ch))
    norm = norm.replace("ß", "ss").replace("Ø", "O").replace("ø", "o")

    for key, val in ph.items():
        norm = norm.replace(key, val)

    return norm


# =========================
# Parsing do mapping (robusto)
# =========================

@dataclasses.dataclass
class MappingItem:
    id: int
    offset: int
    max_bytes: int
    encoding: str
    terminator: bytes
    pad_byte: int
    source_text: str
    source_bytes: Optional[bytes] = None
    translated_text: Optional[str] = None


def _score_candidate_list(lst: Any) -> int:
    """
    Pontua uma lista candidata de itens do mapping (lista de dicts).
    Quanto maior, mais provável que seja a lista real de reinserção.
    """
    if not isinstance(lst, list) or len(lst) == 0:
        return -1

    sample = [x for x in lst[:80] if isinstance(x, dict)]
    if len(sample) == 0:
        return -1

    offset_keys = ("offset", "off", "start", "address")
    size_keys = ("max_bytes", "max_len", "max_length", "allocated", "length", "size", "byte_length")
    text_keys = ("source_text", "original_text", "text", "src", "source")
    meta_keys = ("terminator", "term", "end_byte", "pad_byte", "encoding", "codec",
                 "source_bytes", "original_bytes", "raw_bytes")

    def score_dict(d: Dict[str, Any]) -> int:
        sc = 0
        if any(k in d for k in offset_keys):
            sc += 3
        if any(k in d for k in size_keys):
            sc += 3
        if any(k in d for k in text_keys):
            sc += 2
        if any(k in d for k in meta_keys):
            sc += 1
        return sc

    scores = sorted((score_dict(d) for d in sample), reverse=True)
    top = scores[:12]
    return sum(top) // max(1, len(top))


def _find_best_items_list_deep(mapping_obj: Any) -> Optional[List[Dict[str, Any]]]:
    """
    Busca profunda por uma lista candidata, sem depender de nomes de keys.
    Útil quando o mapping não tem 'items'/'entries' etc.
    """
    best_list: Optional[List[Dict[str, Any]]] = None
    best_score = -1
    best_len = -1

    stack = [mapping_obj]
    visited = 0
    max_nodes = 30000  # limite de segurança

    while stack and visited < max_nodes:
        cur = stack.pop()
        visited += 1

        if isinstance(cur, dict):
            for v in cur.values():
                stack.append(v)
            continue

        if isinstance(cur, list):
            sc = _score_candidate_list(cur)
            if sc >= 4:
                cand = [x for x in cur if isinstance(x, dict)]
                if cand:
                    if sc > best_score or (sc == best_score and len(cur) > best_len):
                        best_list = cand
                        best_score = sc
                        best_len = len(cur)
            # explora elementos (limitado)
            for v in cur[:80]:
                stack.append(v)

    return best_list


def _guess_items_root(mapping_obj: Any) -> List[Dict[str, Any]]:
    """
    Tenta achar onde estão os itens do mapping.
    1) formatos comuns (items/entries/...)
    2) fallback: busca profunda por uma lista candidata
    """
    if isinstance(mapping_obj, list):
        cand = [x for x in mapping_obj if isinstance(x, dict)]
        if cand:
            return cand

    if isinstance(mapping_obj, dict):
        for k in ("items", "entries", "strings", "texts", "data", "mapping", "records", "results"):
            v = mapping_obj.get(k)
            if isinstance(v, list):
                cand = [x for x in v if isinstance(x, dict)]
                if cand:
                    return cand

        deep = _find_best_items_list_deep(mapping_obj)
        if deep:
            return deep

        top_keys = list(mapping_obj.keys())
        raise ValueError(f"Formato de mapping não reconhecido: não achei lista de itens. Top keys: {top_keys}")

    raise ValueError("Formato de mapping não reconhecido: não achei lista de itens.")


def _guess_rom_meta(mapping_obj: Any, fallback_crc32: Optional[str]) -> Tuple[Optional[str], Optional[int]]:
    crc32 = None
    size = None
    if isinstance(mapping_obj, dict):
        for k in ("rom", "meta", "header"):
            v = mapping_obj.get(k)
            if isinstance(v, dict):
                if isinstance(v.get("crc32"), str):
                    crc32 = v["crc32"].upper()
                if v.get("size") is not None:
                    size = _hex_or_int(v.get("size"))
        if isinstance(mapping_obj.get("crc32"), str):
            crc32 = mapping_obj["crc32"].upper()
        # Formatos alternativos (schema interno): file_crc32 / file_size
        if isinstance(mapping_obj.get("file_crc32"), str):
            crc32 = mapping_obj["file_crc32"].upper()
        if mapping_obj.get("file_size") is not None:
            size = _hex_or_int(mapping_obj.get("file_size"))
        if mapping_obj.get("rom_size") is not None:
            size = _hex_or_int(mapping_obj.get("rom_size"))
        if mapping_obj.get("size") is not None and size is None:
            size = _hex_or_int(mapping_obj.get("size"))
    if crc32 is None:
        crc32 = fallback_crc32
    return crc32, size


def load_mapping_items(mapping_path: Path) -> Tuple[Any, List[MappingItem], Optional[str], Optional[int], Dict[str, Any]]:
    mapping_obj = _safe_json_load(mapping_path)

    fallback_crc32 = _infer_crc32_from_filename(mapping_path)
    crc32, rom_size = _guess_rom_meta(mapping_obj, fallback_crc32)

    raw_items = _guess_items_root(mapping_obj)

    codec: Dict[str, Any] = {}
    if isinstance(mapping_obj, dict) and isinstance(mapping_obj.get("codec"), dict):
        codec = mapping_obj["codec"]

    items: List[MappingItem] = []
    for idx, it in enumerate(raw_items, start=1):
        if not isinstance(it, dict):
            continue

        item_id = _hex_or_int(it.get("id")) or idx

        off = None
        for k in ("offset", "off", "start", "address"):
            off = _hex_or_int(it.get(k))
            if off is not None:
                break
        if off is None:
            continue

        mx = None
        mx_key = None
        for k in ("max_bytes", "max_len", "max_length", "allocated", "length", "size", "byte_length"):
            mx = _hex_or_int(it.get(k))
            if mx is not None:
                mx_key = k
                break
        if mx is None:
            sb = _parse_hex_bytes(it.get("source_bytes")) or _parse_hex_bytes(it.get("original_bytes")) or _parse_hex_bytes(it.get("raw_bytes"))
            if sb is not None:
                mx = len(sb)
        if mx is None:
            continue

        enc = it.get("encoding") or it.get("codec") or "ascii"
        if not isinstance(enc, str):
            enc = "ascii"
        enc = enc.strip().lower()

        term = it.get("terminator") or it.get("term") or it.get("end_byte") or "00"
        term_b = _parse_hex_bytes(term)
        if term_b is None or len(term_b) == 0:
            term_b = b"\x00"

        pad = it.get("pad_byte")
        pad_i = _hex_or_int(pad)
        if pad_i is None:
            sb = _parse_hex_bytes(it.get("source_bytes")) or _parse_hex_bytes(it.get("original_bytes")) or _parse_hex_bytes(it.get("raw_bytes"))
            if sb and len(sb) > 0:
                pad_i = sb[-1]
            else:
                pad_i = 0x00
        pad_i = int(pad_i) & 0xFF

        src = it.get("source_text") or it.get("original_text") or it.get("text") or it.get("src") or it.get("source")
        if not isinstance(src, str):
            src = ""

        src_b = _parse_hex_bytes(it.get("source_bytes")) or _parse_hex_bytes(it.get("original_bytes")) or _parse_hex_bytes(it.get("raw_bytes"))
        # Heurística: alguns mappings usam max_length (texto) sem contar o terminador.
        # Se o texto original + terminador não cabe, aumentamos a janela em len(terminator).
        if mx is not None and mx_key == "max_length":
            try:
                base_len = None
                if src_b is not None:
                    base_len = len(src_b)
                else:
                    base_len = len((src or "").encode(enc, errors="ignore"))
                if base_len is not None and (base_len + len(term_b)) > int(mx):
                    mx = int(mx) + len(term_b)
            except Exception:
                pass

        tr = it.get("translated_text") or it.get("dst") or it.get("translated")
        if not isinstance(tr, str):
            tr = None

        items.append(MappingItem(
            id=item_id,
            offset=off,
            max_bytes=int(mx),
            encoding=enc,
            terminator=bytes(term_b),
            pad_byte=pad_i,
            source_text=src,
            source_bytes=src_b,
            translated_text=tr,
        ))

    if len(items) == 0:
        # diagnóstico mínimo, sem inventar formato
        top_keys = list(mapping_obj.keys()) if isinstance(mapping_obj, dict) else ["<list>"]
        sample_keys = list(raw_items[0].keys()) if (len(raw_items) > 0 and isinstance(raw_items[0], dict)) else []
        raise ValueError(
            "Nenhum item válido encontrado no mapping.\n"
            f"Top keys do JSON: {top_keys}\n"
            f"Keys do primeiro item (se existir): {sample_keys}\n"
            "Cada item precisa de pelo menos: offset + max_bytes/size + source_text."
        )

    return mapping_obj, items, crc32, rom_size, codec


# =========================
# Tradução (Transformers)
# =========================

class Translator:
    """
    Tradutor via transformers (NLLB / M2M100).
    Bibliotecas: transformers + torch + sentencepiece (dependendo do modelo).
    """
    def __init__(self, model_name: str, src_lang: str, tgt_lang: str, device: str = "auto", max_new_tokens: int = 256):
        self.model_name = model_name
        self.src_lang = src_lang
        self.tgt_lang = tgt_lang
        self.device = device
        self.max_new_tokens = max_new_tokens

        try:
            import torch
            from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
        except Exception as e:
            raise RuntimeError(
                "Falha ao importar transformers/torch. Instale:\n"
                "  pip install transformers torch sentencepiece\n"
                f"Detalhe: {e}"
            )

        self.torch = torch
        self.AutoTokenizer = AutoTokenizer
        self.AutoModelForSeq2SeqLM = AutoModelForSeq2SeqLM
        self._load()

    def _pick_device(self) -> int:
        if self.device == "cpu":
            return -1
        if self.device == "cuda":
            if not self.torch.cuda.is_available():
                return -1
            return 0
        if self.torch.cuda.is_available():
            return 0
        return -1

    def _load(self) -> None:
        self.tokenizer = self.AutoTokenizer.from_pretrained(self.model_name)
        self.model = self.AutoModelForSeq2SeqLM.from_pretrained(self.model_name)

        dev_index = self._pick_device()
        self._dev_index = dev_index
        if dev_index >= 0:
            self.model = self.model.to("cuda")

        if hasattr(self.tokenizer, "src_lang"):
            try:
                self.tokenizer.src_lang = self.src_lang
            except Exception:
                pass

    def _forced_bos_id(self) -> Optional[int]:
        if hasattr(self.tokenizer, "lang_code_to_id") and isinstance(getattr(self.tokenizer, "lang_code_to_id"), dict):
            d = getattr(self.tokenizer, "lang_code_to_id")
            if self.tgt_lang in d:
                return int(d[self.tgt_lang])
        if hasattr(self.tokenizer, "get_lang_id"):
            try:
                return int(self.tokenizer.get_lang_id(self.tgt_lang))
            except Exception:
                pass
        try:
            return int(self.tokenizer.convert_tokens_to_ids(self.tgt_lang))
        except Exception:
            return None

    def translate_batch(self, texts: List[str]) -> List[str]:
        fb = self._forced_bos_id()
        inputs = self.tokenizer(texts, return_tensors="pt", padding=True, truncation=True)
        if self._dev_index >= 0:
            inputs = {k: v.to("cuda") for k, v in inputs.items()}

        gen_kwargs = {"max_new_tokens": self.max_new_tokens}
        if fb is not None:
            gen_kwargs["forced_bos_token_id"] = fb

        with self.torch.no_grad():
            out = self.model.generate(**inputs, **gen_kwargs)

        decoded = self.tokenizer.batch_decode(out, skip_special_tokens=True)
        return [d.strip() for d in decoded]


# =========================
# Encoding / Reinserção
# =========================

def _build_custom_tables(codec: Dict[str, Any]) -> Tuple[Dict[str, int], Dict[str, bytes]]:
    char_to_byte: Dict[str, int] = {}
    special_tokens: Dict[str, bytes] = {}

    if not isinstance(codec, dict):
        return char_to_byte, special_tokens

    ctb = codec.get("char_to_byte")
    if isinstance(ctb, dict):
        for ch, bv in ctb.items():
            bi = _hex_or_int(bv)
            if isinstance(ch, str) and bi is not None:
                char_to_byte[ch] = int(bi) & 0xFF

    st = codec.get("special_tokens")
    if isinstance(st, dict):
        for tok, hv in st.items():
            b = _parse_hex_bytes(hv)
            if isinstance(tok, str) and b is not None:
                special_tokens[tok] = b

    return char_to_byte, special_tokens

def encode_text_strict(text: str, encoding: str, char_to_byte: Dict[str, int], special_tokens: Dict[str, bytes]) -> bytes:
    if char_to_byte or special_tokens:
        out = bytearray()
        i = 0
        token_pat = re.compile(r"<[^<>]{1,16}>")
        while i < len(text):
            m = token_pat.match(text, i)
            if m:
                tok = m.group(0)
                if tok in special_tokens:
                    out.extend(special_tokens[tok])
                    i = m.end()
                    continue
                raise ValueError(f"Token especial não mapeado: {tok}")
            ch = text[i]
            if ch in char_to_byte:
                out.append(char_to_byte[ch])
            else:
                raise ValueError(f"Caractere não mapeado na tabela: {repr(ch)}")
            i += 1
        return bytes(out)

    try:
        return text.encode(encoding, errors="strict")
    except Exception as e:
        raise ValueError(f"Falha ao codificar em '{encoding}': {e}")


def sanitize_and_validate_translation(it: MappingItem, codec: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    """
    Garante que a tradução:
    - preserva placeholders
    - é codificável no encoding/tabela
    - cabe no orçamento (max_bytes considerando terminador)
    Se necessário, faz truncamento seguro para caber (sem quebrar placeholders).
    Retorna (texto_final, reason_ou_None).
    """
    # texto alvo (tradução) ou fallback para fonte
    dst_raw = it.translated_text if (it.translated_text is not None) else it.source_text

    # placeholders devem ser preservados
    if not placeholders_equal(it.source_text, dst_raw):
        return it.source_text, "placeholders_mismatch"

    char_to_byte, special_tokens = _build_custom_tables(codec)

    enc = (it.encoding or "ascii").lower().strip()

    def _sanitize(text: str) -> str:
        if enc in ("ascii", "us-ascii"):
            return latinize_pt_ascii(text)
        return text

    def _try_encode_len(text: str) -> Tuple[Optional[bytes], Optional[int], Optional[str]]:
        try:
            b = encode_text_strict(text, enc, char_to_byte, special_tokens)
            return b, len(b), None
        except Exception as e:
            return None, None, f"encode_error: {e}"

    def _truncate_to_fit(text: str, max_text_bytes: int) -> Optional[str]:
        # Truncamento conservador: remove caracteres do fim até caber.
        # Sempre revalida placeholders após cada corte para não quebrar tokens.
        cand = text.rstrip()
        while cand:
            if not placeholders_equal(it.source_text, cand):
                # se quebrou placeholders, corta mais
                cand = cand[:-1]
                continue
            b, blen, err = _try_encode_len(cand)
            if err is None and blen is not None and blen <= max_text_bytes:
                return cand
            cand = cand[:-1]
        return None

    # orçamento de bytes para o texto (sem terminador)
    max_text_bytes = int(it.max_bytes) - len(it.terminator)
    if max_text_bytes < 0:
        max_text_bytes = 0

    # 1) tenta com a tradução (saneada)
    dst = _sanitize(dst_raw)
    b, blen, err = _try_encode_len(dst)
    if err is not None:
        # se não codifica, cai para fonte
        dst = _sanitize(it.source_text)
        b, blen, err2 = _try_encode_len(dst)
        if err2 is not None:
            return it.source_text, err2
        # valida tamanho para fonte
        payload_len = int(blen) + len(it.terminator)
        if payload_len > int(it.max_bytes):
            shr = _truncate_to_fit(dst, max_text_bytes)
            if shr is not None:
                return shr, "source_truncated_to_fit"
            return it.source_text, f"overflow: payload={payload_len} > max_bytes={it.max_bytes}"
        return dst, "fallback_to_source_due_to_encode_error"

    # tamanho OK?
    payload_len = int(blen) + len(it.terminator)
    if payload_len <= int(it.max_bytes):
        return dst, None

    # 2) overflow: tenta truncar a tradução
    shr = _truncate_to_fit(dst, max_text_bytes)
    if shr is not None:
        return shr, "truncated_to_fit"

    # 3) se não deu, tenta truncar a fonte
    src_s = _sanitize(it.source_text)
    shr2 = _truncate_to_fit(src_s, max_text_bytes)
    if shr2 is not None:
        return shr2, "source_truncated_to_fit"

    # último recurso: volta para a fonte mesmo (pode falhar no reinsert; ficará registrado)
    return it.source_text, f"overflow: payload={payload_len} > max_bytes={it.max_bytes}"

def apply_reinsertion_strict(
    rom_data: bytearray,
    items: List[MappingItem],
    char_to_byte: Dict[str, int],
    special_tokens: Dict[str, bytes],
) -> Tuple[int, List[Dict[str, Any]]]:
    applied = 0
    errors: List[Dict[str, Any]] = []

    for it in items:
        dst = it.translated_text if (it.translated_text is not None) else it.source_text

        if not placeholders_equal(it.source_text, dst):
            errors.append({"id": it.id, "offset": f"0x{it.offset:X}", "reason": "placeholders_mismatch"})
            continue

        try:
            enc = encode_text_strict(dst, it.encoding, char_to_byte, special_tokens)
        except Exception as e:
            errors.append({"id": it.id, "offset": f"0x{it.offset:X}", "reason": f"encode_error: {e}"})
            continue

        payload = enc + it.terminator
        if len(payload) > it.max_bytes:
            errors.append({"id": it.id, "offset": f"0x{it.offset:X}", "reason": f"overflow: payload={len(payload)} > max_bytes={it.max_bytes}"})
            continue

        start = it.offset
        end = it.offset + it.max_bytes
        if end > len(rom_data):
            errors.append({"id": it.id, "offset": f"0x{it.offset:X}", "reason": "write_oob"})
            continue

        rom_data[start:start + len(payload)] = payload
        if start + len(payload) < end:
            rom_data[start + len(payload):end] = bytes([it.pad_byte]) * (end - (start + len(payload)))

        applied += 1

    return applied, errors


# =========================
# Reports / Proof
# =========================

def write_report(path: Path, lines: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for ln in lines:
            f.write(ln.rstrip("\n") + "\n")

def make_base_proof(crc32: Optional[str], rom_size: Optional[int]) -> Dict[str, Any]:
    return {"timestamp": _now_iso(), "rom": {"crc32": crc32, "size": rom_size}}


# =========================
# Comandos
# =========================

def cmd_expand_pointer_tables(args: argparse.Namespace) -> int:
    """
    Expande itens a partir de discovered_pointer_tables (SEM scan cego) e grava um NOVO mapping em out-dir.
    O novo mapping recebe a chave raiz "items" com os itens expandidos.
    """
    rom_path = Path(args.rom)
    mapping_path = Path(args.mapping)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rom_bytes = _read_bytes(rom_path)
    mapping_obj = _safe_json_load(mapping_path)

    items, errors = expand_items_from_pointer_tables(mapping_obj, rom_bytes)

    crc32 = None
    if isinstance(mapping_obj, dict) and isinstance(mapping_obj.get("file_crc32"), str):
        crc32 = mapping_obj.get("file_crc32")
    if not crc32:
        crc32 = _compute_crc32_hex(rom_bytes)

    crc32 = str(crc32).upper()
    rom_size = len(rom_bytes)

    new_map = dict(mapping_obj) if isinstance(mapping_obj, dict) else {"schema": "expanded"}
    new_map["file_crc32"] = crc32
    new_map["file_size"] = int(rom_size)
    new_map["items"] = items

    out_mapping = out_dir / f"{crc32}_reinsertion_mapping.json"
    _safe_json_dump(out_mapping, new_map)

    report = [
        f"[ROM] CRC32={crc32} ROM_SIZE={rom_size}",
        f"[EXPAND] expanded_items={len(items)} errors={len(errors)}",
        f"[EXPORT] mapping={out_mapping.name}",
    ]
    if errors:
        report.append("[EXPAND_ERRORS]")
        for e in errors[:80]:
            report.append(f"- {e}")
    (out_dir / f"{crc32}_report.txt").write_text("\n".join(report) + "\n", encoding="utf-8")
    _safe_json_dump(out_dir / f"{crc32}_proof.json", {
        "crc32": crc32,
        "rom_size": rom_size,
        "expanded_items": len(items),
        "expand_errors": errors,
    })

    print(f"[OK] EXPAND (pointer tables) | CRC32={crc32} | itens={len(items)}")
    return 0


def cmd_extract_from_mapping(args: argparse.Namespace) -> int:
    mapping_path = Path(args.mapping).resolve()
    out_dir = Path(args.out_dir).resolve()

    mapping_obj, items, crc32, rom_size, _codec = load_mapping_items(mapping_path)

    if crc32 is None and isinstance(args.crc32, str) and re.fullmatch(r"[0-9A-Fa-f]{8}", args.crc32.strip() or ""):
        crc32 = args.crc32.strip().upper()

    if crc32 is None:
        raise SystemExit("Não consegui inferir CRC32 do mapping. Use --crc32 8HEX ou renomeie para {CRC32}_reinsertion_mapping.json")

    pure_text_path = out_dir / f"{crc32}_pure_text.jsonl"
    report_path = out_dir / f"{crc32}_report.txt"
    proof_path = out_dir / f"{crc32}_proof.json"

    rows: List[Dict[str, Any]] = []
    for it in items:
        rows.append({
            "id": it.id,
            "offset": it.offset,
            "offset_hex": f"0x{it.offset:X}",
            "max_bytes": it.max_bytes,
            "encoding": it.encoding,
            "terminator_hex": it.terminator.hex().upper(),
            "source_text": it.source_text,
            "placeholders": extract_placeholders(it.source_text),
        })
    _jsonl_write(pure_text_path, rows)

    rep = []
    rep.append(f"[ROM] CRC32={crc32} ROM_SIZE={rom_size}")
    rep.append(f"[EXTRACT] itens={len(items)}")
    rep.append(f"[EXPORT] pure_text={pure_text_path.name}")
    rep.append(f"[EXPORT] report={report_path.name}")
    rep.append(f"[EXPORT] proof={proof_path.name}")
    write_report(report_path, rep)

    proof = make_base_proof(crc32, rom_size)
    proof.update({
        "stage": "extract_from_mapping",
        "inputs": {"mapping_sha256": _sha256_file(mapping_path)},
        "outputs": {"pure_text_sha256": _sha256_file(pure_text_path), "report_sha256": _sha256_file(report_path)},
        "items_total": len(items),
    })
    _safe_json_dump(proof_path, proof)

    print(f"[OK] EXTRACT (from mapping) | CRC32={crc32} | itens={len(items)}")
    return 0

def cmd_translate(args: argparse.Namespace) -> int:
    # TRANSLATE_DIAGNOSTICS_V1
    translate_diagnostics = []  # lista de dicts, 1 por erro contado

    mapping_path = Path(args.mapping).resolve()
    out_dir = Path(args.out_dir).resolve()

    mapping_obj, items, crc32, rom_size, codec = load_mapping_items(mapping_path)

    if crc32 is None:
        if isinstance(args.crc32, str) and re.fullmatch(r"[0-9A-Fa-f]{8}", args.crc32.strip() or ""):
            crc32 = args.crc32.strip().upper()
    if crc32 is None:
        raise SystemExit("Não consegui inferir CRC32 do mapping. Use --crc32 8HEX ou renomeie para {CRC32}_reinsertion_mapping.json")

    tr = Translator(
        model_name=args.model,
        src_lang=args.src_lang,
        tgt_lang=args.tgt_lang,
        device=args.device,
        max_new_tokens=args.max_new_tokens,
    )

    batch_size = int(args.batch_size)
    errors: List[Dict[str, Any]] = []
    translated_ok = 0

    def chunks(lst: List[MappingItem], n: int) -> Iterable[List[MappingItem]]:
        for i in range(0, len(lst), n):
            yield lst[i:i+n]

    for group in chunks(items, batch_size):
        src_texts = [it.source_text for it in group]
        out_texts = tr.translate_batch(src_texts)

        for it, out in zip(group, out_texts):
            # Validação/saneamento antes de gravar translated_text no mapping
            it.translated_text = out
            fixed, reason = sanitize_and_validate_translation(it, codec)
            if reason is not None:
                it.translated_text = fixed
                errors.append({"id": it.id, "offset": f"0x{it.offset:X}", "reason": reason})
                # Truncamentos ainda contam como "ok" (texto válido e reinserível)
                if reason in ("truncated_to_fit", "source_truncated_to_fit"):
                    translated_ok += 1
                continue
            it.translated_text = fixed
            translated_ok += 1

    out_mapping_path = out_dir / f"{crc32}_reinsertion_mapping.json"
    report_path = out_dir / f"{crc32}_report.txt"
    proof_path = out_dir / f"{crc32}_proof.json"

    try:
        raw_items = _guess_items_root(mapping_obj)
        i_map = 0
        for it in items:
            while i_map < len(raw_items) and not isinstance(raw_items[i_map], dict):
                i_map += 1
            if i_map >= len(raw_items):
                break
            raw_items[i_map]["translated_text"] = it.translated_text
            i_map += 1

        if isinstance(mapping_obj, dict):
            mapping_obj.setdefault("rom", {})
            if isinstance(mapping_obj["rom"], dict):
                mapping_obj["rom"]["crc32"] = crc32
                if rom_size is not None:
                    mapping_obj["rom"]["size"] = rom_size

        _safe_json_dump(out_mapping_path, mapping_obj)
    except Exception:
        simple = {"rom": {"crc32": crc32, "size": rom_size}, "codec": codec, "items": [dataclasses.asdict(it) for it in items]}
        _safe_json_dump(out_mapping_path, simple)

    rep = []
    rep.append(f"[ROM] CRC32={crc32} ROM_SIZE={rom_size}")
    rep.append(f"[TRANSLATE] model={args.model}")
    rep.append(f"[LANG] src={args.src_lang} tgt={args.tgt_lang}")
    rep.append(f"[TRANSLATE] itens_total={len(items)} ok={translated_ok} erros={len(errors)}")
    rep.append(f"[EXPORT] reinsertion_mapping={out_mapping_path.name}")
    rep.append(f"[EXPORT] report={report_path.name}")
    rep.append(f"[EXPORT] proof={proof_path.name}")
    if errors:
        rep.append("[ERRORS]")
        for e in errors[:200]:
            rep.append(f"- id={e['id']} off={e['offset']} reason={e['reason']}")
        if len(errors) > 200:
            rep.append(f"- ... truncado (total={len(errors)})")
    write_report(report_path, rep)

    proof = make_base_proof(crc32, rom_size)
    proof.update({
        "stage": "translate",
        "model": args.model,
        "lang": {"src": args.src_lang, "tgt": args.tgt_lang},
        "inputs": {"mapping_in_sha256": _sha256_file(mapping_path)},
        "outputs": {"mapping_out_sha256": _sha256_file(out_mapping_path), "report_sha256": _sha256_file(report_path)},
        "items_total": len(items),
        "translated_ok": translated_ok,
        "errors": errors,
    })
    _safe_json_dump(proof_path, proof)

    # TRANSLATE_DIAGNOSTICS_V1: exporta diagnósticos (somente os itens contados como erro)
    diag_path = out_dir / f"{crc32}_translate_diagnostics.jsonl"
    with diag_path.open("w", encoding="utf-8") as f:
        for row in translate_diagnostics:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"[OK] TRANSLATE | CRC32={crc32} | ok={translated_ok} | erros={len(errors)}")
    return 0

def cmd_reinsert(args: argparse.Namespace) -> int:
    rom_path = Path(args.rom).resolve()
    mapping_path = Path(args.mapping).resolve()
    out_dir = Path(args.out_dir).resolve()

    rom_bytes = _read_bytes(rom_path)
    crc32 = _compute_crc32_hex(rom_bytes)
    rom_size = len(rom_bytes)

    mapping_obj, items, m_crc32, m_size, codec = load_mapping_items(mapping_path)

    if m_crc32 is not None and m_crc32.upper() != crc32:
        raise SystemExit(f"Mapping CRC32={m_crc32} não corresponde à ROM CRC32={crc32}")
    if m_size is not None and int(m_size) != rom_size:
        raise SystemExit(f"Mapping ROM_SIZE={m_size} não corresponde à ROM_SIZE={rom_size}")

    out_rom_path = out_dir / f"{crc32}_patched.rom"
    report_path = out_dir / f"{crc32}_report.txt"
    proof_path = out_dir / f"{crc32}_proof.json"

    char_to_byte, special_tokens = _build_custom_tables(codec)

    rom_data = bytearray(rom_bytes)
    applied, errors = apply_reinsertion_strict(rom_data, items, char_to_byte, special_tokens)

    _write_bytes(out_rom_path, bytes(rom_data))

    rep = []
    rep.append(f"[ROM] CRC32={crc32} ROM_SIZE={rom_size}")
    rep.append(f"[REINSERT] itens_total={len(items)} applied={applied} erros={len(errors)}")
    rep.append(f"[EXPORT] patched_rom={out_rom_path.name}")
    rep.append(f"[EXPORT] report={report_path.name}")
    rep.append(f"[EXPORT] proof={proof_path.name}")
    if errors:
        rep.append("[ERRORS]")
        for e in errors[:300]:
            rep.append(f"- id={e['id']} off={e['offset']} reason={e['reason']}")
        if len(errors) > 300:
            rep.append(f"- ... truncado (total={len(errors)})")
    write_report(report_path, rep)

    proof = make_base_proof(crc32, rom_size)
    proof.update({
        "stage": "reinsert",
        "strict": bool(args.strict),
        "inputs": {"mapping_sha256": _sha256_file(mapping_path), "rom_sha256": _sha256_file(rom_path)},
        "outputs": {"patched_rom_sha256": _sha256_file(out_rom_path), "report_sha256": _sha256_file(report_path)},
        "items_total": len(items),
        "applied": applied,
        "errors": errors,
    })
    _safe_json_dump(proof_path, proof)

    if errors and args.strict:
        raise SystemExit(f"Reinserção falhou em modo estrito: applied={applied}, erros={len(errors)}")

    print(f"[OK] REINSERT | CRC32={crc32} | applied={applied} | erros={len(errors)}")
    return 0


# =========================
# CLI
# =========================

def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="romtxt_pipeline_v1.py", add_help=True)
    sub = p.add_subparsers(dest="cmd", required=True)

    pe = sub.add_parser("extract-from-mapping", help="Gera {CRC32}_pure_text.jsonl a partir do mapping (SEM scan cego).")
    pe.add_argument("--mapping", required=True, help="Caminho do {CRC32}_reinsertion_mapping.json")
    pe.add_argument("--out-dir", default="out", help="Diretório de saída")
    pe.add_argument("--crc32", default=None, help="CRC32 8HEX se não for inferível do filename/mapping")
    pe.set_defaults(func=cmd_extract_from_mapping)

    px = sub.add_parser("expand-pointer-tables", help="Expande itens a partir de discovered_pointer_tables (SEM scan cego).")
    px.add_argument("--rom", required=True, help="Caminho da ROM (binário).")
    px.add_argument("--mapping", required=True, help="Caminho do {CRC32}_reinsertion_mapping.json.")
    px.add_argument("--out-dir", required=True, help="Diretório de saída.")
    px.set_defaults(func=cmd_expand_pointer_tables)


    pt = sub.add_parser("translate", help="Traduz japonês->português e grava novo {CRC32}_reinsertion_mapping.json com translated_text.")
    pt.add_argument("--mapping", required=True, help="Caminho do reinsertion_mapping.json")
    pt.add_argument("--out-dir", default="out", help="Diretório de saída")
    pt.add_argument("--model", required=True, help="Ex: facebook/nllb-200-distilled-600M ou facebook/m2m100_418M")
    pt.add_argument("--src-lang", default="jpn_Jpan", help="NLLB: jpn_Jpan (padrão)")
    pt.add_argument("--tgt-lang", default="por_Latn", help="NLLB: por_Latn (padrão)")
    pt.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto", help="Dispositivo para inferência")
    pt.add_argument("--batch-size", type=int, default=8, help="Tamanho do batch")
    pt.add_argument("--max-new-tokens", type=int, default=256, help="Limite por string")
    pt.add_argument("--crc32", default=None, help="CRC32 8HEX se não for inferível do filename/mapping")
    pt.set_defaults(func=cmd_translate)

    pr = sub.add_parser("reinsert", help="Reinsere translated_text na ROM com validação estrita.")
    pr.add_argument("--rom", required=True, help="Caminho da ROM")
    pr.add_argument("--mapping", required=True, help="Caminho do reinsertion_mapping.json (com translated_text)")
    pr.add_argument("--out-dir", default="out", help="Diretório de saída")
    pr.add_argument("--strict", action="store_true", help="Falha se houver qualquer erro (recomendado)")
    pr.set_defaults(func=cmd_reinsert)

    return p

def main(argv: Optional[List[str]] = None) -> int:
    ap = build_argparser()
    args = ap.parse_args(argv)
    return int(args.func(args))

if __name__ == "__main__":
    raise SystemExit(main())

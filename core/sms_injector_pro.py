# -*- coding: utf-8 -*-
"""sms_injector_pro.py

Injector Master System (SMS) V6 PRO:

O que ele faz (do jeito mais 'nao vai quebrar tua ROM'):
- sobrescreve in-place quando cabe
- quando nao cabe: procura espaco livre DENTRO do mesmo bank 16KB
- se nao achar: expande a ROM (adiciona novos bancos 16KB) e tenta repoint
  via:
    * ponteiro banked 3 bytes (bank + addr16) OU
    * bank-table paralela (1 byte por entry) perto da pointer table

Checksum:
- recalcula checksum do header Sega (TMR SEGA) se encontrado

Limitacoes honestas:
- SMS tem varios mappers/engines; sem profile por jogo, ponteiros podem nao ser
  enderecos diretos. Entao o injector trabalha por inferencia e so atualiza
  ponteiros com evidencias fortes.

V6.0 PRO (NeuroROM AI)
"""

from __future__ import annotations

import hashlib
import json
import struct
import zlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from retro8_bank_tools import (
    find_free_space_in_bank,
    expand_rom_in_banks,
    detect_pointer_table_window_16,
    detect_parallel_bank_table,
    patch_bank_table_entry,
    patch_pointer16,
    patch_banked_pointer3,
    iter_pointer_refs16,
    iter_banked_pointer3,
    detect_sms_pointer_base,
)

try:
    from core.final_qa import evaluate_reinsertion_qa, write_qa_artifacts
except Exception:
    try:
        from final_qa import evaluate_reinsertion_qa, write_qa_artifacts
    except Exception:
        evaluate_reinsertion_qa = None
        write_qa_artifacts = None

NON_TEXT_REASON_CODES = {
    "NOT_PLAUSIBLE_TEXT_SMS",
    "NOT_PLAUSIBLE_TEXT",
    "TILEMAP_NO_POINTER",
    "NO_POINTER_INFO",
    "AUTOLEARN_NO_POINTER_INFO",
    "GRAPHIC_TILE_DATA",
    "NON_TEXT_DATA",
}


def _parse_int(v) -> Optional[int]:
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return int(v)
    if isinstance(v, float):
        return int(v)
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        try:
            return int(s, 16) if s.lower().startswith("0x") else int(s)
        except ValueError:
            return None
    return None


def _read_text_file_lines(path: str) -> List[Tuple[int, str]]:
    out: List[Tuple[int, str]] = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip("\n")
            if not line or not line.startswith("["):
                continue
            try:
                i = line.find("]")
                off = int(line[1:i], 16)
                text = line[i + 1 :].strip()
                out.append((off, text))
            except Exception:
                continue
    return out


def _read_jsonl_lines(path: str) -> Tuple[List[Tuple[int, str]], int]:
    ordered: List[Tuple[Tuple[int, int, int, int], Tuple[int, str]]] = []
    skipped_non_text = 0
    idx = 0
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            idx += 1
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if not isinstance(obj, dict):
                continue
            if str(obj.get("type", "")).lower() == "meta":
                continue

            reason = str(obj.get("reason_code") or obj.get("blocked_reason") or "").strip().upper()
            if reason in NON_TEXT_REASON_CODES:
                skipped_non_text += 1
                continue

            off = _parse_int(obj.get("rom_offset", obj.get("offset", obj.get("file_offset"))))
            if off is None:
                continue
            text = (
                obj.get("text_dst")
                or obj.get("translated")
                or obj.get("text_translated")
                or obj.get("text")
                or ""
            )
            text = str(text)
            seq = _parse_int(obj.get("seq"))
            seq_rank = seq if seq is not None else 10**12
            sort_key = (0 if seq is not None else 1, seq_rank, off, idx)
            ordered.append((sort_key, (off, text)))
    ordered.sort(key=lambda it: it[0])
    return [row for _, row in ordered], skipped_non_text


def _read_translation_entries(path: str) -> Tuple[List[Tuple[int, str]], int]:
    p = Path(path)
    if p.suffix.lower() == ".jsonl":
        return _read_jsonl_lines(str(p))
    return _read_text_file_lines(str(p)), 0


def _sha256_file(path: str) -> Optional[str]:
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except Exception:
        return None


def _jsonl_runtime_info(path: str) -> Dict[str, Any]:
    info: Dict[str, Any] = {
        "has_meta": False,
        "declared_crc32": None,
        "declared_size": None,
        "is_sorted_by_offset": False,
        "seq_consistent": False,
        "first_10_offsets": [],
        "last_10_offsets": [],
        "coverage_check": {
            "min_offset": None,
            "max_offset": None,
            "items_total": 0,
            "count_offsets_below_0x10000": 0,
            "first_20_items_summary": [],
        },
        "compression_policy": {},
    }
    p = Path(path)
    if p.suffix.lower() != ".jsonl" or not p.exists():
        return info

    rows: List[Tuple[Tuple[int, int, int, int], Dict[str, Any]]] = []
    idx = 0
    for raw in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line:
            continue
        idx += 1
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        if str(obj.get("type", "")).lower() == "meta":
            info["has_meta"] = True
            dec_crc = str(obj.get("rom_crc32") or "").strip().upper()
            if dec_crc:
                info["declared_crc32"] = dec_crc
            dec_size = _parse_int(obj.get("rom_size"))
            if dec_size is not None:
                info["declared_size"] = int(dec_size)
            if isinstance(obj.get("compression_policy"), dict):
                info["compression_policy"] = dict(obj.get("compression_policy") or {})
            continue
        off = _parse_int(obj.get("rom_offset", obj.get("offset", obj.get("file_offset"))))
        if off is None:
            continue
        seq = _parse_int(obj.get("seq"))
        seq_rank = seq if seq is not None else 10**12
        sort_key = (0 if seq is not None else 1, seq_rank, int(off), idx)
        rows.append(
            (
                sort_key,
                {
                    "seq": seq,
                    "offset": int(off),
                    "idx": idx,
                },
            )
        )

    if not rows:
        return info

    ordered = [row for _, row in sorted(rows, key=lambda it: it[0])]
    offsets = [int(r["offset"]) for r in ordered]
    seq_values = [r.get("seq") for r in ordered]
    has_seq = all(s is not None for s in seq_values)
    info["is_sorted_by_offset"] = bool(offsets == sorted(offsets))
    info["seq_consistent"] = bool(has_seq and [int(s) for s in seq_values] == list(range(len(seq_values))))
    if not has_seq:
        # Fallback por offset para entradas sem seq explícito.
        info["seq_consistent"] = bool(info["is_sorted_by_offset"])

    info["first_10_offsets"] = [
        {"seq": (int(r["seq"]) if r.get("seq") is not None else None), "offset": int(r["offset"])}
        for r in ordered[:10]
    ]
    info["last_10_offsets"] = [
        {"seq": (int(r["seq"]) if r.get("seq") is not None else None), "offset": int(r["offset"])}
        for r in ordered[-10:]
    ]
    info["coverage_check"] = {
        "min_offset": int(min(offsets)),
        "max_offset": int(max(offsets)),
        "items_total": int(len(ordered)),
        "count_offsets_below_0x10000": int(sum(1 for off in offsets if int(off) < 0x10000)),
        "first_20_items_summary": [
            {"seq": (int(r["seq"]) if r.get("seq") is not None else None), "offset": int(r["offset"])}
            for r in ordered[:20]
        ],
    }
    return info


SMS_DIALOG_WIDTH = 28  # 256px / 8px por tile = 32, com margem = 28


def _wrap_text_sms(text: str, width: int = SMS_DIALOG_WIDTH) -> str:
    """Aplica word-wrap para caber na largura de diálogo SMS."""
    import textwrap as _tw
    if "\n" in text or len(text) <= width:
        return text
    lines = _tw.wrap(text, width=width, break_long_words=False, break_on_hyphens=False)
    return "\n".join(lines) if lines else text


def _encode_ascii(text: str) -> bytes:
    # SMS normalmente nao tem acentos no charset original.
    # Aplica word-wrap automatico para textos longos.
    text = _wrap_text_sms(text)
    out = bytearray()
    for ch in text:
        code = ord(ch)
        if ch == "\n":
            out.append(0x0A)
        elif 32 <= code <= 126:
            out.append(code)
        else:
            out.append(0x3F)  # '?' fallback
    return bytes(out)


def _safe_original_length(rom: bytes, offset: int, max_len: int = 256) -> int:
    end = min(len(rom), offset + max_len)
    i = offset
    while i < end:
        b = rom[i]
        if b in (0x00, 0xFF):
            return (i - offset) + 1
        i += 1
    return end - offset


def _find_sega_header_offset(rom: bytes) -> Optional[int]:
    sig = b"TMR SEGA"
    # costuma aparecer no fim de um bank (ex 0x7FF0), mas vamos buscar geral.
    hits = []
    start = 0
    while True:
        idx = rom.find(sig, start)
        if idx == -1:
            break
        hits.append(idx)
        start = idx + 1
    if not hits:
        return None
    # pega a ultima ocorrencia
    return hits[-1]


def fix_sms_checksum(rom_data: bytearray) -> bool:
    """Recalcula checksum do header Sega, se assinatura TMR SEGA existir.

    Implementacao pratica (compat):
    - checksum_offset = header_off + 0x0A  (-> 0x7FFA quando header_off=0x7FF0)
    - checksum = soma de todos os bytes da ROM, pulando os 2 bytes de checksum
      (16-bit wrap)
    - grava little-endian
    """
    header_off = _find_sega_header_offset(rom_data)
    if header_off is None:
        return False

    checksum_off = header_off + 0x0A
    if checksum_off + 2 > len(rom_data):
        return False

    checksum = 0
    for i, b in enumerate(rom_data):
        if checksum_off <= i < checksum_off + 2:
            continue
        checksum = (checksum + b) & 0xFFFF

    rom_data[checksum_off : checksum_off + 2] = struct.pack("<H", checksum)
    return True


class SMSInjectorPro:
    def __init__(self, rom_path: str):
        self.rom_path = Path(rom_path)
        self.rom_data = bytearray(self.rom_path.read_bytes())
        self.source_crc32 = f"{zlib.crc32(bytes(self.rom_data)) & 0xFFFFFFFF:08X}"
        self.source_size = int(len(self.rom_data))

        self.stats = {
            "modified": 0,
            "relocated": 0,
            "truncated": 0,
            "skipped": 0,
            "non_text_meta_skipped": 0,
            "pointers_updated": 0,
            "bank_table_updates": 0,
            "bank_table_skipped_high_fanout": 0,
            "rom_expanded": 0,
            "checksum_fixed": 0,
        }

        # SMS: bancos de 16KB
        self.bank_size = 0x4000

        # Base de ponteiro mais provavel (0x8000 costuma ser bem comum)
        self.pointer_base = None
        # Índices de ponteiro (snapshot inicial) para evitar varredura O(n*m)
        self._pointer_scan_bytes: Optional[bytes] = None
        self._u16_positions: Optional[List[List[int]]] = None
        self._u16_plausible_mask: Optional[List[bool]] = None
        self._ptr_window_cache: Dict[int, Tuple[int, int]] = {}
        self._bank_table_cache: Dict[Tuple[int, int], Optional[int]] = {}
        self.last_qa_final: Optional[Dict[str, Any]] = None
        self.last_qa_paths: Dict[str, Optional[str]] = {"json": None, "txt": None}

    def _ensure_pointer_base(self, extracted_offsets: List[int]):
        if self.pointer_base is not None:
            return
        self.pointer_base = detect_sms_pointer_base(self.rom_data, extracted_offsets, self.bank_size)

    def _build_pointer_indexes(self, base: int) -> None:
        """Constrói índice de valores u16 em um snapshot inicial da ROM."""
        if (
            self._u16_positions is not None
            and self._pointer_scan_bytes is not None
            and self._u16_plausible_mask is not None
        ):
            return
        src = bytes(self.rom_data)
        positions: List[List[int]] = [[] for _ in range(65536)]
        lim = max(0, len(src) - 1)
        values = [0] * lim
        for off in range(lim):
            v = src[off] | (src[off + 1] << 8)
            values[off] = v
            positions[v].append(off)

        # Marca offsets em contexto plausível de tabela de ponteiro (u16 vizinho em passo 2)
        lo = int(base) & 0xFFFF
        hi = (int(base) + self.bank_size - 1) & 0xFFFF
        valid = [False] * lim
        if lo <= hi:
            for i, v in enumerate(values):
                valid[i] = lo <= v <= hi
        else:
            for i, v in enumerate(values):
                valid[i] = (v >= lo) or (v <= hi)
        plausible = [False] * lim
        for i in range(lim):
            if not valid[i]:
                continue
            left_ok = (i - 2 >= 0) and valid[i - 2]
            right_ok = (i + 2 < lim) and valid[i + 2]
            plausible[i] = left_ok or right_ok

        self._pointer_scan_bytes = src
        self._u16_positions = positions
        self._u16_plausible_mask = plausible
        self._ptr_window_cache = {}
        self._bank_table_cache = {}

    def _get_pointer_refs_fast(self, old_bank8: int, old_addr16: int, base: int) -> Tuple[List[int], List[Tuple[int, str]]]:
        """Retorna refs16 (offsets) e refs3 (offset, mode) a partir do índice."""
        self._build_pointer_indexes(base)
        assert self._u16_positions is not None
        assert self._pointer_scan_bytes is not None
        assert self._u16_plausible_mask is not None

        src = self._pointer_scan_bytes
        raw_offsets = self._u16_positions[old_addr16 & 0xFFFF]
        refs16_offsets = [o for o in raw_offsets if self._u16_plausible_mask[o]]
        refs3: List[Tuple[int, str]] = []

        # Deriva ponteiros 3-byte a partir dos matches 16-bit:
        # - BANK_ADDR_LE: [bank][lo][hi]  -> u16 começa em off+1
        # - ADDR_LE_BANK: [lo][hi][bank]  -> u16 começa em off
        seen3 = set()
        for off16 in refs16_offsets:
            cand_a = off16 - 1
            if cand_a >= 0 and src[cand_a] == (old_bank8 & 0xFF):
                if cand_a not in seen3:
                    seen3.add(cand_a)
                    refs3.append((cand_a, "BANK_ADDR_LE"))

            cand_b = off16
            if cand_b + 2 < len(src) and src[cand_b + 2] == (old_bank8 & 0xFF):
                if cand_b not in seen3:
                    seen3.add(cand_b)
                    refs3.append((cand_b, "ADDR_LE_BANK"))

        return refs16_offsets, refs3

    def reinsert(self, translation_file: str, output_path: Optional[str] = None,
                 allow_cross_bank_repoint: bool = True) -> Dict:
        translation_info = _jsonl_runtime_info(translation_file)
        entries, skipped_non_text = _read_translation_entries(translation_file)
        self.stats["non_text_meta_skipped"] = skipped_non_text
        self.stats["skipped"] += skipped_non_text
        if not entries:
            return {
                "success": False,
                "message": "Nenhuma entrada valida no arquivo de traducao",
                **self.stats,
            }

        extracted_offsets = [o for o, _ in entries]
        self._ensure_pointer_base(extracted_offsets)

        base = self.pointer_base or 0x8000
        self._build_pointer_indexes(base)

        # Para detecao de bank tables
        total_banks = max(1, (len(self.rom_data) + self.bank_size - 1) // self.bank_size)
        # Pool linear no fim da ROM para realocacoes cross-bank (evita scans O(n*banks))
        append_cursor = len(self.rom_data)

        for off, translated in entries:
            translated = translated.strip()
            if not translated:
                self.stats["skipped"] += 1
                continue

            new_bytes = _encode_ascii(translated)
            # garante terminador 0x00
            if not new_bytes.endswith(b"\x00"):
                new_bytes += b"\x00"

            orig_len = _safe_original_length(self.rom_data, off)

            if len(new_bytes) <= orig_len:
                self.rom_data[off:off+len(new_bytes)] = new_bytes
                # padding
                if orig_len > len(new_bytes):
                    self.rom_data[off+len(new_bytes):off+orig_len] = b"\x00" * (orig_len - len(new_bytes))
                self.stats["modified"] += 1
                continue

            # Tenta compressao DTE antes de realocar
            if hasattr(self, '_dte_helper') and self._dte_helper:
                dte_result = self._dte_helper.try_dte_compression(
                    new_bytes, orig_len
                )
                if dte_result is not None:
                    self.rom_data[off:off+len(dte_result)] = dte_result
                    if orig_len > len(dte_result):
                        pad_start = off + len(dte_result)
                        self.rom_data[pad_start:off+orig_len] = b"\x00" * (orig_len - len(dte_result))
                    self.stats["modified"] += 1
                    continue

            # nao cabe: tenta realocar dentro do mesmo bank
            old_bank = off // self.bank_size
            in_bank_start = old_bank * self.bank_size
            in_bank_end = in_bank_start + self.bank_size

            new_loc = find_free_space_in_bank(self.rom_data, len(new_bytes), in_bank_start, in_bank_end)

            if new_loc is None and allow_cross_bank_repoint:
                # Alocacao linear no fim da ROM: expande somente quando necessario
                if append_cursor & 1:
                    append_cursor += 1
                need_end = append_cursor + len(new_bytes)
                if need_end > len(self.rom_data):
                    extra_needed = need_end - len(self.rom_data)
                    old_size, new_size = expand_rom_in_banks(
                        self.rom_data, self.bank_size, extra_needed, fill=0xFF
                    )
                    self.stats["rom_expanded"] += (new_size - old_size) // self.bank_size
                    total_banks = max(total_banks, (len(self.rom_data) + self.bank_size - 1) // self.bank_size)
                new_loc = append_cursor
                append_cursor = new_loc + len(new_bytes)

            if new_loc is None:
                # fallback: truncar pra caber
                trunc = new_bytes[:orig_len]
                if not trunc.endswith(b"\x00"):
                    trunc = trunc[:-1] + b"\x00"
                self.rom_data[off:off+orig_len] = trunc
                self.stats["truncated"] += 1
                continue

            # escreve no novo lugar
            self.rom_data[new_loc:new_loc+len(new_bytes)] = new_bytes
            # limpa area antiga
            self.rom_data[off:off+orig_len] = b"\x00" * orig_len

            # repoint: procura referencias de ponteiro
            # 1) ponteiros 16-bit addr_in_bank + base
            old_addr16 = (base + (off % self.bank_size)) & 0xFFFF
            new_addr16 = (base + (new_loc % self.bank_size)) & 0xFFFF

            # refs de ponteiro (snapshot indexado) para evitar varredura completa por item
            old_bank8 = old_bank & 0xFF
            new_bank8 = (new_loc // self.bank_size) & 0xFF
            refs16_offsets, refs3 = self._get_pointer_refs_fast(old_bank8, old_addr16, base)

            updated_any = 0

            # patch 3-byte pointers primeiro
            for ptr_off, ptr_mode in refs3:
                patch_banked_pointer3(self.rom_data, ptr_off, new_bank8, new_addr16, mode=ptr_mode)
                updated_any += 1

            # patch 16-bit pointers
            skip_bank_table_due_fanout = allow_cross_bank_repoint and (len(refs16_offsets) > 512)
            if skip_bank_table_due_fanout and (new_loc // self.bank_size) != old_bank:
                self.stats["bank_table_skipped_high_fanout"] += 1

            for ptr_off in refs16_offsets:
                patch_pointer16(self.rom_data, ptr_off, new_addr16)
                updated_any += 1

                # tenta bank table paralela, se mudou de bank
                if (
                    allow_cross_bank_repoint
                    and (new_loc // self.bank_size) != old_bank
                    and (not skip_bank_table_due_fanout)
                ):
                    window = self._ptr_window_cache.get(ptr_off)
                    if window is None:
                        src_scan = self._pointer_scan_bytes if self._pointer_scan_bytes is not None else bytes(self.rom_data)
                        window = detect_pointer_table_window_16(src_scan, ptr_off)
                        self._ptr_window_cache[ptr_off] = window
                    if window is not None:
                        table_start, count = window
                        if int(count) < 2:
                            continue
                        idx = (ptr_off - table_start) // 2
                        expected_by_index = {idx: old_bank8}
                        cache_key = (int(table_start), int(count))
                        bank_table = self._bank_table_cache.get(cache_key)
                        if cache_key not in self._bank_table_cache:
                            src_scan = self._pointer_scan_bytes if self._pointer_scan_bytes is not None else bytes(self.rom_data)
                            bank_table = detect_parallel_bank_table(
                                src_scan,
                                table_start=table_start,
                                entry_count=count,
                                prg_bank_count=max(1, total_banks),
                                expected_bank_by_index=expected_by_index,
                                search_window=0x2000,
                            )
                            self._bank_table_cache[cache_key] = bank_table
                        if bank_table is not None:
                            patch_bank_table_entry(self.rom_data, bank_table, idx, new_bank8)
                            self.stats["bank_table_updates"] += 1

            self.stats["pointers_updated"] += updated_any
            self.stats["relocated"] += 1
            self.stats["modified"] += 1

        # checksum
        if fix_sms_checksum(self.rom_data):
            self.stats["checksum_fixed"] = 1

        if output_path is None:
            output_path = str(self.rom_path.with_name(self.rom_path.stem + "_TRANSLATED.sms"))

        Path(output_path).write_bytes(self.rom_data)

        qa_final = None
        qa_json_path = None
        qa_txt_path = None
        if evaluate_reinsertion_qa and write_qa_artifacts:
            try:
                declared_crc = translation_info.get("declared_crc32")
                declared_size = translation_info.get("declared_size")
                input_match = None
                if declared_crc and declared_size is not None:
                    input_match = bool(
                        str(declared_crc).upper() == self.source_crc32
                        and int(declared_size) == int(self.source_size)
                    )

                ordering_ok = bool(
                    translation_info.get("is_sorted_by_offset", False)
                    and translation_info.get("seq_consistent", False)
                )
                limitations: List[str] = []
                if translation_info.get("has_meta") is not True:
                    limitations.append("JSONL sem metadados rom_crc32/rom_size (input_match desconhecido).")
                cov = translation_info.get("coverage_check", {}) or {}
                if int(cov.get("count_offsets_below_0x10000", 0)) == 0:
                    limitations.append("intro possivelmente não extraído/mapeado (count_offsets_below_0x10000=0).")
                if int(self.stats.get("bank_table_skipped_high_fanout", 0)) > 0:
                    limitations.append(
                        f"Bank table pulada por high fanout em {self.stats.get('bank_table_skipped_high_fanout', 0)} casos."
                    )

                qa_translation_input = {
                    "path": str(translation_file),
                    "sha256": _sha256_file(translation_file),
                    "declared_crc32": declared_crc,
                    "declared_size": declared_size,
                }
                qa_final = evaluate_reinsertion_qa(
                    console="SMS",
                    rom_crc32=self.source_crc32,
                    rom_size=self.source_size,
                    stats=self.stats,
                    evidence={"truncated_count": int(self.stats.get("truncated", 0))},
                    checks={
                        "input_match": input_match,
                        "ordering": ordering_ok,
                        "emulator_smoke": None,
                    },
                    limitations=limitations,
                    compression_policy=translation_info.get("compression_policy", {}) or {},
                    translation_input=qa_translation_input,
                    require_manual_emulator=True,
                )
                qa_json_path, qa_txt_path = write_qa_artifacts(
                    Path(output_path).parent,
                    self.source_crc32,
                    qa_final,
                )
                self.last_qa_final = qa_final
                self.last_qa_paths = {
                    "json": str(qa_json_path),
                    "txt": str(qa_txt_path),
                }
            except Exception:
                qa_final = None
                qa_json_path = None
                qa_txt_path = None

        return {
            "success": True,
            "message": "Reinsercao SMS concluida",
            "output_path": output_path,
            **self.stats,
            "pointer_base": hex(base),
            "ordering_check": {
                "is_sorted_by_offset": bool(translation_info.get("is_sorted_by_offset", False)),
                "seq_consistent": bool(translation_info.get("seq_consistent", False)),
                "first_10_offsets": translation_info.get("first_10_offsets", []),
                "last_10_offsets": translation_info.get("last_10_offsets", []),
            },
            "coverage_check": translation_info.get("coverage_check", {}),
            "input_match_check": {
                "rom_crc32_match": (
                    None
                    if not translation_info.get("declared_crc32")
                    else bool(str(translation_info.get("declared_crc32")).upper() == self.source_crc32)
                ),
                "rom_size_match": (
                    None
                    if translation_info.get("declared_size") is None
                    else bool(int(translation_info.get("declared_size")) == int(self.source_size))
                ),
                "jsonl_declared_crc32": translation_info.get("declared_crc32"),
                "jsonl_declared_size": translation_info.get("declared_size"),
            },
            "qa_final": qa_final,
            "qa_final_json": str(qa_json_path) if qa_json_path else None,
            "qa_final_txt": str(qa_txt_path) if qa_txt_path else None,
        }


def reinsert_sms_rom(rom_path: str, translation_file: str, output_path: Optional[str] = None) -> Dict:
    inj = SMSInjectorPro(rom_path)
    return inj.reinsert(translation_file, output_path)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python sms_injector_pro.py <rom.sms> <translation.txt> [output.sms]")
        raise SystemExit(1)

    rom = sys.argv[1]
    tr = sys.argv[2]
    out = sys.argv[3] if len(sys.argv) > 3 else None

    res = reinsert_sms_rom(rom, tr, out)
    print(res["message"])
    for k in [
        "modified",
        "relocated",
        "truncated",
        "skipped",
        "non_text_meta_skipped",
        "pointers_updated",
        "bank_table_updates",
        "bank_table_skipped_high_fanout",
        "rom_expanded",
        "checksum_fixed",
    ]:
        print(f"{k}: {res.get(k)}")

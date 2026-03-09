# -*- coding: utf-8 -*-
"""nes_injector_pro.py

Injector NES V6 PRO:
- suporta traducoes maiores via realocacao dentro do mesmo bank (safe)
- quando precisar atravessar banks: tenta detectar e atualizar uma bank-table paralela
- quando necessario, expande PRG-ROM em bancos de 16KB e atualiza header iNES

Limitacoes (honestas):
- Sem profile especifico por jogo, nao da pra garantir suporte a TODAS as engines.
- Este injector cobre o caso mais comum: pointer tables 16-bit para enderecos $8000-$BFFF
  + bank table 1-byte opcional.

Formato esperado do arquivo de traducao:
- Linhas: [0xOFFSET] texto
- OFFSET e o offset no arquivo inteiro (inclui header iNES e trainer, se existir)
- Recomenda-se usar o META json gerado pelo nes_extractor_pro.py para max seguranca.

V6.0 PRO (NeuroROM AI)
"""

from __future__ import annotations

import hashlib
import json
import re
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from retro8_bank_tools import (
    PointerRef,
    find_free_space_in_bank,
    expand_by_banks,
    detect_pointer_table_window_2byte,
    detect_parallel_bank_table,
)

try:
    from core.final_qa import evaluate_reinsertion_qa, write_qa_artifacts
except Exception:
    try:
        from final_qa import evaluate_reinsertion_qa, write_qa_artifacts
    except Exception:
        evaluate_reinsertion_qa = None
        write_qa_artifacts = None


def parse_ines_header(data: bytes) -> Dict:
    if len(data) < 16 or data[:4] != b"NES\x1A":
        raise ValueError("Arquivo nao parece ser NES iNES (magic NES\\x1A ausente)")

    prg_16k = data[4]
    chr_8k = data[5]
    flags6 = data[6]
    flags7 = data[7]

    mapper = (flags7 & 0xF0) | (flags6 >> 4)
    has_trainer = bool(flags6 & 0x04)

    header_size = 16
    trainer_size = 512 if has_trainer else 0
    prg_size = prg_16k * 16 * 1024
    chr_size = chr_8k * 8 * 1024
    prg_start = header_size + trainer_size
    chr_start = prg_start + prg_size

    return {
        "prg_16k": prg_16k,
        "chr_8k": chr_8k,
        "mapper": mapper,
        "has_trainer": has_trainer,
        "prg_start": prg_start,
        "prg_size": prg_size,
        "chr_start": chr_start,
        "chr_size": chr_size,
    }


OFFSET_RE = re.compile(r"^\[(0x[0-9a-fA-F]+)\]\s*(.*)$")


@dataclass
class Entry:
    file_offset: int
    translated: str
    original_length: Optional[int] = None  # bytes no arquivo


def _sha256_file(path: str) -> Optional[str]:
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except Exception:
        return None


def _build_ordering_coverage(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not records:
        return {
            "ordering_check": {
                "is_sorted_by_offset": False,
                "seq_consistent": False,
                "first_10_offsets": [],
                "last_10_offsets": [],
            },
            "coverage_check": {
                "min_offset": None,
                "max_offset": None,
                "items_total": 0,
                "count_offsets_below_0x10000": 0,
                "first_20_items_summary": [],
            },
        }
    ordered = sorted(
        records,
        key=lambda r: (
            0 if r.get("seq") is not None else 1,
            int(r.get("seq")) if r.get("seq") is not None else 10**12,
            int(r.get("offset", 0)),
            int(r.get("index", 0)),
        ),
    )
    offsets = [int(r.get("offset", 0)) for r in ordered]
    seq_values = [r.get("seq") for r in ordered]
    has_seq = all(s is not None for s in seq_values)
    seq_consistent = bool(has_seq and [int(s) for s in seq_values] == list(range(len(seq_values))))
    if not has_seq:
        seq_consistent = bool(offsets == sorted(offsets))
    return {
        "ordering_check": {
            "is_sorted_by_offset": bool(offsets == sorted(offsets)),
            "seq_consistent": bool(seq_consistent),
            "first_10_offsets": [
                {"seq": (int(r.get("seq")) if r.get("seq") is not None else None), "offset": int(r.get("offset", 0))}
                for r in ordered[:10]
            ],
            "last_10_offsets": [
                {"seq": (int(r.get("seq")) if r.get("seq") is not None else None), "offset": int(r.get("offset", 0))}
                for r in ordered[-10:]
            ],
        },
        "coverage_check": {
            "min_offset": int(min(offsets)),
            "max_offset": int(max(offsets)),
            "items_total": int(len(ordered)),
            "count_offsets_below_0x10000": int(sum(1 for off in offsets if int(off) < 0x10000)),
            "first_20_items_summary": [
                {"seq": (int(r.get("seq")) if r.get("seq") is not None else None), "offset": int(r.get("offset", 0))}
                for r in ordered[:20]
            ],
        },
    }


class NESInjectorPro:
    NON_TEXT_REASON_CODES = {
        "NOT_PLAUSIBLE_TEXT_SMS",
        "NOT_PLAUSIBLE_TEXT",
        "TILEMAP_NO_POINTER",
        "NO_POINTER_INFO",
        "AUTOLEARN_NO_POINTER_INFO",
        "GRAPHIC_TILE_DATA",
        "NON_TEXT_DATA",
    }

    def __init__(self, rom_path: str):
        self.rom_path = Path(rom_path)
        self.rom_data = bytearray(self.rom_path.read_bytes())
        self.h = parse_ines_header(self.rom_data)
        self.source_crc32 = f"{zlib.crc32(bytes(self.rom_data)) & 0xFFFFFFFF:08X}"
        self.source_size = int(len(self.rom_data))

        self.bank_size = 0x4000  # 16KB PRG banks
        self.translation_runtime_info: Dict[str, Any] = {
            "has_meta": False,
            "declared_crc32": None,
            "declared_size": None,
            "ordering_check": {
                "is_sorted_by_offset": False,
                "seq_consistent": False,
                "first_10_offsets": [],
                "last_10_offsets": [],
            },
            "coverage_check": {
                "min_offset": None,
                "max_offset": None,
                "items_total": 0,
                "count_offsets_below_0x10000": 0,
                "first_20_items_summary": [],
            },
            "compression_policy": {},
        }
        self.last_qa_final: Optional[Dict[str, Any]] = None
        self.last_qa_paths: Dict[str, Optional[str]] = {"json": None, "txt": None}

    # --------------------------
    # Parsing de traducoes
    # --------------------------
    @staticmethod
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

    def load_translation_txt(self, translation_path: str) -> List[Entry]:
        p = Path(translation_path)
        lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
        out: List[Entry] = []
        records: List[Dict[str, Any]] = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = OFFSET_RE.match(line)
            if not m:
                continue
            off = int(m.group(1), 16)
            txt = m.group(2)
            out.append(Entry(file_offset=off, translated=txt))
            records.append({"seq": None, "offset": off, "index": len(records)})

        oc = _build_ordering_coverage(records)
        self.translation_runtime_info = {
            "has_meta": False,
            "declared_crc32": None,
            "declared_size": None,
            "ordering_check": oc["ordering_check"],
            "coverage_check": oc["coverage_check"],
            "compression_policy": {},
        }
        return out

    def load_translation_jsonl(self, translation_path: str) -> Tuple[List[Entry], int]:
        p = Path(translation_path)
        out_rows: List[Tuple[Tuple[int, int, int], Entry]] = []
        skipped_non_text = 0
        records: List[Dict[str, Any]] = []
        declared_crc32 = None
        declared_size = None
        compression_policy: Dict[str, Any] = {}
        line_idx = 0

        for raw_line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
            line_idx += 1
            line = raw_line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if not isinstance(obj, dict):
                continue
            if str(obj.get("type", "")).lower() == "meta":
                dec_crc = str(obj.get("rom_crc32") or "").strip().upper()
                if dec_crc:
                    declared_crc32 = dec_crc
                dec_size = self._parse_int(obj.get("rom_size"))
                if dec_size is not None:
                    declared_size = int(dec_size)
                if isinstance(obj.get("compression_policy"), dict):
                    compression_policy = dict(obj.get("compression_policy") or {})
                continue

            reason = str(obj.get("reason_code") or obj.get("blocked_reason") or "").strip().upper()
            if reason in self.NON_TEXT_REASON_CODES:
                skipped_non_text += 1
                continue

            off = self._parse_int(obj.get("rom_offset", obj.get("offset", obj.get("file_offset"))))
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
            seq = self._parse_int(obj.get("seq"))
            seq_rank = seq if seq is not None else 10**12
            out_rows.append(((0 if seq is not None else 1, seq_rank, off), Entry(file_offset=off, translated=text)))
            records.append({"seq": seq, "offset": int(off), "index": line_idx})

        out_rows.sort(key=lambda it: it[0])
        oc = _build_ordering_coverage(records)
        self.translation_runtime_info = {
            "has_meta": bool(declared_crc32 or declared_size is not None),
            "declared_crc32": declared_crc32,
            "declared_size": declared_size,
            "ordering_check": oc["ordering_check"],
            "coverage_check": oc["coverage_check"],
            "compression_policy": compression_policy,
        }
        return [entry for _, entry in out_rows], skipped_non_text

    def load_translation_entries(self, translation_path: str) -> Tuple[List[Entry], int]:
        p = Path(translation_path)
        if p.suffix.lower() == ".jsonl":
            return self.load_translation_jsonl(str(p))
        return self.load_translation_txt(str(p)), 0

    def load_meta_if_present(self, translation_path: str) -> Dict[int, Dict]:
        """Se existir um META json ao lado, usa para obter original_length."""
        p = Path(translation_path)
        candidates = [
            p.with_name(p.stem + "_META.json"),
            p.with_suffix("")
            .with_name(p.stem.replace("_TRANSLATED", "") + "_NES_EXTRACTED_META.json"),
        ]
        for c in candidates:
            if c.exists():
                try:
                    meta = json.loads(c.read_text(encoding="utf-8"))
                    # indexa por file_offset
                    return {int(k): v for k, v in meta.get("by_offset", {}).items()}
                except Exception:
                    continue
        return {}

    # --------------------------
    # Encoding
    # --------------------------
    @staticmethod
    def encode_ascii(text: str, terminator: int = 0x00) -> bytes:
        # NES classico: muitos jogos usam ASCII parcial, mas aqui a suite V5 ja assume ASCII.
        b = text.encode("latin-1", errors="replace")
        if terminator is not None:
            b += bytes([terminator])
        return b

    def _infer_original_length(self, file_offset: int, max_len: int = 256) -> int:
        """Fallback perigoso: varre ate 0x00/0xFF com limite."""
        end = min(len(self.rom_data), file_offset + max_len)
        i = file_offset
        while i < end:
            if self.rom_data[i] in (0x00, 0xFF):
                return (i - file_offset) + 1
            i += 1
        return max_len

    # --------------------------
    # Ponteiros (NES)
    # --------------------------
    def _expected_ptr_value_8000(self, prg_offset: int) -> int:
        return 0x8000 + (prg_offset % self.bank_size)

    def _expected_ptr_value_c000_lastbank(self, prg_offset: int, prg_banks: int) -> Optional[int]:
        # enderecos $C000-$FFFF normalmente apontam para o ultimo bank fixo.
        last_bank_start = (prg_banks - 1) * self.bank_size
        if prg_offset < last_bank_start:
            return None
        return 0xC000 + (prg_offset - last_bank_start)

    def _find_pointer_refs(self, prg_offset: int) -> List[PointerRef]:
        """Procura referencias de ponteiro para um offset PRG (sem header)."""
        prg_banks = max(1, self.h["prg_16k"])
        ptrs: List[PointerRef] = []

        p8000 = self._expected_ptr_value_8000(prg_offset)
        p8000_bytes = p8000.to_bytes(2, "little")
        pos = 0
        while True:
            off = self.rom_data.find(p8000_bytes, pos)
            if off < 0:
                break
            ptrs.append(PointerRef(ptr_offset=off, table_start=None, index=None, mode="NES_8000"))
            pos = off + 1

        pc000 = self._expected_ptr_value_c000_lastbank(prg_offset, prg_banks)
        if pc000 is not None:
            pc000_bytes = int(pc000).to_bytes(2, "little")
            pos = 0
            while True:
                off = self.rom_data.find(pc000_bytes, pos)
                if off < 0:
                    break
                ptrs.append(PointerRef(ptr_offset=off, table_start=None, index=None, mode="NES_C000"))
                pos = off + 1

        return ptrs

    # --------------------------
    # Injeção
    # --------------------------
    def inject(
        self,
        translation_txt: str,
        output_path: Optional[str] = None,
        fail_on_unbanked_crossbank: bool = True,
        verbose: bool = True,
    ) -> Tuple[bool, str, Dict]:
        entries, skipped_non_text = self.load_translation_entries(translation_txt)
        meta = self.load_meta_if_present(translation_txt)

        prg_start = self.h["prg_start"]
        prg_size = self.h["prg_size"]
        prg_banks = max(1, self.h["prg_16k"])

        stats = {
            "modified": 0,
            "relocated": 0,
            "truncated": 0,
            "skipped": skipped_non_text,
            "pointers_updated": 0,
            "bank_table_updates": 0,
            "rom_expanded": 0,
            "non_text_meta_skipped": skipped_non_text,
        }

        ordering_check = dict(self.translation_runtime_info.get("ordering_check", {}) or {})
        coverage_check = dict(self.translation_runtime_info.get("coverage_check", {}) or {})
        declared_crc = self.translation_runtime_info.get("declared_crc32")
        declared_size = self.translation_runtime_info.get("declared_size")
        input_match_check = {
            "rom_crc32_match": (
                None if not declared_crc else bool(str(declared_crc).upper() == self.source_crc32)
            ),
            "rom_size_match": (
                None if declared_size is None else bool(int(declared_size) == int(self.source_size))
            ),
            "jsonl_declared_crc32": declared_crc,
            "jsonl_declared_size": declared_size,
        }

        if not entries:
            return (
                False,
                "Nenhuma entrada valida para reinsercao.",
                {
                    **stats,
                    "ordering_check": ordering_check,
                    "coverage_check": coverage_check,
                    "input_match_check": input_match_check,
                },
            )

        # cache de deteccao de bank tables por tabela de ponteiros
        bank_table_cache: Dict[int, Optional[int]] = {}

        for e in entries:
            if not e.translated.strip():
                stats["skipped"] += 1
                continue

            if e.file_offset < prg_start or e.file_offset >= prg_start + prg_size:
                # fora de PRG: normalmente nao queremos mexer
                stats["skipped"] += 1
                continue

            prg_off = e.file_offset - prg_start
            old_bank = prg_off // self.bank_size

            # tamanho original
            if e.file_offset in meta:
                e.original_length = int(meta[e.file_offset].get("length", 0)) or None
            if not e.original_length:
                e.original_length = self._infer_original_length(e.file_offset)

            new_bytes = self.encode_ascii(e.translated)

            # 1) cabe in-place?
            if len(new_bytes) <= e.original_length:
                self.rom_data[e.file_offset : e.file_offset + len(new_bytes)] = new_bytes
                # padding
                pad = e.original_length - len(new_bytes)
                if pad > 0:
                    self.rom_data[e.file_offset + len(new_bytes) : e.file_offset + e.original_length] = b"\x00" * pad
                stats["modified"] += 1
                continue

            # 2) precisa realocar
            #   - tenta primeiro dentro do mesmo bank
            bank_file_start = prg_start + old_bank * self.bank_size
            new_file_offset = find_free_space_in_bank(
                self.rom_data,
                bank_start=bank_file_start,
                bank_size=self.bank_size,
                required_size=len(new_bytes),
                alignment=2,
                patterns=(0x00, 0xFF),
            )

            cross_bank = False
            new_bank = old_bank

            if new_file_offset is None:
                # 3) Expande ROM (novo bank) e coloca no final da PRG
                #    (mantem CHR depois; aqui a suite atual nao altera CHR)
                #    -> precisamos mover CHR para frente mantendo conteudo.
                #    Simplificacao segura: se CHR existir, regrava o arquivo como:
                #    header + PRG(expandido) + CHR(original)
                cross_bank = True

                # calcula novo PRG total (em 16KB)
                extra_needed = len(new_bytes)
                new_prg_size, added_banks = expand_by_banks(prg_size, extra_needed, self.bank_size)

                if added_banks <= 0:
                    return False, "Falha ao calcular expansao PRG", stats

                # extrai blocos
                header = self.rom_data[:prg_start]
                prg = self.rom_data[prg_start : prg_start + prg_size]
                chr_data = self.rom_data[prg_start + prg_size : prg_start + prg_size + self.h["chr_size"]]

                # expande PRG com 0xFF (padding comum)
                prg.extend(b"\xFF" * (added_banks * self.bank_size))

                new_file_offset = prg_start + len(prg) - (added_banks * self.bank_size)
                # coloca no comeco do primeiro bank novo (alinhado)
                new_file_offset = (new_file_offset + 1) & ~1

                # escreve bytes
                rel = new_file_offset - prg_start
                prg[rel : rel + len(new_bytes)] = new_bytes

                # remonta rom
                self.rom_data = bytearray(header + prg + chr_data)

                # atualiza header PRG count
                prg_banks += added_banks
                self.h["prg_16k"] = prg_banks
                self.h["prg_size"] = prg_banks * self.bank_size
                self.rom_data[4] = prg_banks & 0xFF

                stats["rom_expanded"] += added_banks

                new_bank = (rel // self.bank_size)

            else:
                # escreve dentro do mesmo bank
                self.rom_data[new_file_offset : new_file_offset + len(new_bytes)] = new_bytes

            # limpa texto antigo (evita lixo na comparacao + reduz risco de leituras erradas)
            self.rom_data[e.file_offset : e.file_offset + e.original_length] = b"\x00" * e.original_length

            # atualiza ponteiros
            ptr_refs = self._find_pointer_refs(prg_off)

            if not ptr_refs:
                # sem ponteiros detectados -> provavelmente texto inline.
                # Sem ponteiro, realocar pode quebrar: entao fallback.
                if fail_on_unbanked_crossbank and cross_bank:
                    return False, (
                        f"Texto precisou ir para outro bank, mas nenhum ponteiro foi detectado para 0x{e.file_offset:X}. "
                        "Para evitar crash, abortando."
                    ), stats
                # caso contrario, deixa realocado e segue.
                stats["relocated"] += 1
                continue

            # calcula novo prg_off
            new_prg_off = new_file_offset - prg_start

            # 2-byte pointer tables mais comuns: $8000 + addr_in_bank
            new_ptr_val_8000 = self._expected_ptr_value_8000(new_prg_off)

            for pref in ptr_refs:
                # atualiza 16-bit ponteiro
                self.rom_data[pref.ptr_offset : pref.ptr_offset + 2] = new_ptr_val_8000.to_bytes(2, "little")
                stats["pointers_updated"] += 1

                # se cruzou bank, tenta atualizar bank table
                if cross_bank:
                    # detecta janela da tabela e index
                    if pref.table_start is None or pref.index is None:
                        tstart, tend = detect_pointer_table_window_2byte(
                            self.rom_data,
                            pref.ptr_offset,
                            addr_min=0x8000,
                            addr_max=0xFFFF,
                            endian="little",
                        )
                        if tstart is not None:
                            pref.table_start = tstart
                            pref.index = (pref.ptr_offset - tstart) // 2

                    if pref.table_start is None or pref.index is None:
                        continue

                    # cacheia bank table por table_start
                    if pref.table_start not in bank_table_cache:
                        entry_count = max(16, int(tend) if tend else 32)
                        expected_by_index = {pref.index: old_bank}
                        bank_table_cache[pref.table_start] = detect_parallel_bank_table(
                            self.rom_data,
                            table_start=pref.table_start,
                            entry_count=entry_count,
                            prg_bank_count=max(1, prg_banks),
                            expected_bank_by_index=expected_by_index,
                            search_window=0x2000,
                        )

                    bt = bank_table_cache.get(pref.table_start)
                    if bt is not None:
                        self.rom_data[bt + pref.index] = new_bank & 0xFF
                        stats["bank_table_updates"] += 1

            stats["relocated"] += 1

        # salva
        if output_path is None:
            output_path = str(self.rom_path.with_name(self.rom_path.stem + "_TRANSLATED.nes"))

        Path(output_path).write_bytes(self.rom_data)
        qa_final = None
        qa_json_path = None
        qa_txt_path = None
        if evaluate_reinsertion_qa and write_qa_artifacts:
            try:
                limitations: List[str] = []
                if self.translation_runtime_info.get("has_meta") is not True:
                    limitations.append("JSONL sem metadados rom_crc32/rom_size (input_match desconhecido).")
                if int(coverage_check.get("count_offsets_below_0x10000", 0)) == 0:
                    limitations.append("intro possivelmente não extraído/mapeado (count_offsets_below_0x10000=0).")

                qa_input = {
                    "path": str(translation_txt),
                    "sha256": _sha256_file(translation_txt),
                    "declared_crc32": declared_crc,
                    "declared_size": declared_size,
                }
                qa_final = evaluate_reinsertion_qa(
                    console="NES",
                    rom_crc32=self.source_crc32,
                    rom_size=self.source_size,
                    stats=stats,
                    evidence={"truncated_count": int(stats.get("truncated", 0))},
                    checks={
                        "input_match": (
                            None
                            if input_match_check["rom_crc32_match"] is None or input_match_check["rom_size_match"] is None
                            else bool(
                                input_match_check["rom_crc32_match"]
                                and input_match_check["rom_size_match"]
                            )
                        ),
                        "ordering": bool(
                            ordering_check.get("is_sorted_by_offset", False)
                            and ordering_check.get("seq_consistent", False)
                        ),
                        "emulator_smoke": None,
                    },
                    limitations=limitations,
                    compression_policy=self.translation_runtime_info.get("compression_policy", {}) or {},
                    translation_input=qa_input,
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

        return True, f"OK: salvo em {output_path}", {
            **stats,
            "ordering_check": ordering_check,
            "coverage_check": coverage_check,
            "input_match_check": input_match_check,
            "qa_final": qa_final,
            "qa_final_json": str(qa_json_path) if qa_json_path else None,
            "qa_final_txt": str(qa_txt_path) if qa_txt_path else None,
        }


def reinsert_nes_rom(rom_path: str, translation_txt: str, output_path: Optional[str] = None) -> Dict:
    inj = NESInjectorPro(rom_path)
    ok, msg, stats = inj.inject(translation_txt, output_path=output_path)
    effective_out = output_path or str(Path(rom_path).with_name(Path(rom_path).stem + "_TRANSLATED.nes"))
    return {"success": ok, "message": msg, **stats, "output_path": effective_out}


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python nes_injector_pro.py <rom.nes> <translations.txt> [out.nes]")
        raise SystemExit(1)

    rom = sys.argv[1]
    tr = sys.argv[2]
    out = sys.argv[3] if len(sys.argv) > 3 else None

    res = reinsert_nes_rom(rom, tr, out)
    print(res["message"])
    for k in [
        "modified",
        "relocated",
        "truncated",
        "skipped",
        "non_text_meta_skipped",
        "pointers_updated",
        "bank_table_updates",
        "rom_expanded",
    ]:
        if k in res:
            print(f"{k}: {res[k]}")

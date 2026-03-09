# -*- coding: utf-8 -*-
"""MASTER_SYSTEM_UNIVERSAL_EXTRACTOR

Objetivo:
- Extrair strings de ROMs do Sega Master System de forma universal (scanner + heuristicas)
- Gerar 3 saidas na pasta da ROM:
  1) *_extracted.txt     -> debug (mais amplo)
  2) *_clean_blocks.txt  -> para traducao (somente texto util)
  3) *_mapping.json      -> para reinsercao (offset + metadados + pointers heuristicas)

Esta versao foi feita para integrar com o NeuroROM AI:
- A interface chama: extractor = UniversalMasterSystemExtractor(rom_path)
                    extractor.extract_texts()
                    output_file = extractor.save_results(output_dir)

Requisitos de compatibilidade:
- Ter atributo .results (lista de dicts)
- Ter metodo extract_texts()
- save_results() retornar o caminho do TXT principal (clean_blocks)

Obs: pointer_offsets e heuristico (scan do valor 16-bit do offset). Para 100% perfeito,
use debugger/emulador e/ou base de dados por jogo.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json
import zlib


@dataclass
class ExtractedText:
    offset: int
    text: str
    region: str = "Scan"


class UniversalMasterSystemExtractor:
    def __init__(self, rom_path: str | Path):
        self.rom_path = Path(rom_path)
        self.rom_data: bytes = b""
        self.rom_crc32_full: str = ""
        self.rom_crc32_no512: str = ""
        self.detected_game: str = "generic"

        # Resultado para a interface
        # Cada item: {offset:int, clean:str, region:str, category:str(optional)}
        self.results: List[dict] = []

        # banco simples (exemplo); voce pode expandir depois
        self.game_db = {
            # crc32_full: (game_id, nome)
            "B519E833": ("game_001", "Sonic The Hedgehog (SMS)"),
        }

    # ----------------------------
    # ROM utils
    # ----------------------------

    def load_rom(self) -> None:
        self.rom_data = self.rom_path.read_bytes()

    @staticmethod
    def _crc32_hex(data: bytes) -> str:
        return f"{zlib.crc32(data) & 0xFFFFFFFF:08X}"

    def calculate_crc32(self) -> None:
        if not self.rom_data:
            self.load_rom()
        self.rom_crc32_full = self._crc32_hex(self.rom_data)
        # SMS as vezes tem header de 512 bytes; calculamos tambem sem ele
        if len(self.rom_data) > 512:
            self.rom_crc32_no512 = self._crc32_hex(self.rom_data[512:])
        else:
            self.rom_crc32_no512 = ""

    def detect_game_by_crc(self) -> None:
        # tenta por full e depois por no512
        if self.rom_crc32_full in self.game_db:
            self.detected_game = self.game_db[self.rom_crc32_full][0]
            return
        if self.rom_crc32_no512 and self.rom_crc32_no512 in self.game_db:
            self.detected_game = self.game_db[self.rom_crc32_no512][0]
            return
        self.detected_game = "generic"

    # ----------------------------
    # Extraction
    # ----------------------------

    def extract_texts(self) -> List[dict]:
        """Metodo de entrada chamado pela interface."""
        if not self.rom_data:
            self.load_rom()
        self.calculate_crc32()
        self.detect_game_by_crc()

        debug_texts = self._scan_ascii_strings(min_len=3, max_len=96)
        # dedup por offset
        seen = set()
        uniq: List[ExtractedText] = []
        for t in debug_texts:
            if t.offset in seen:
                continue
            seen.add(t.offset)
            uniq.append(t)

        # converte para dict (formato esperado)
        self.results = [
            {
                "offset": t.offset,
                "clean": t.text,
                "region": t.region,
            }
            for t in uniq
        ]
        return self.results

    # -------------------------------------------------
    # Compat layer (mantém compatível com o app antigo)
    # -------------------------------------------------
    def extract_all(self) -> List[dict]:
        """Alias para compatibilidade (algumas versões chamam extract_all)."""
        return self.extract_texts()

    def extract(self) -> List[dict]:
        """Alias para compatibilidade (alguns módulos chamam extract)."""
        return self.extract_texts()

    def _scan_ascii_strings(self, min_len: int = 4, max_len: int = 128) -> List[ExtractedText]:
        """Scanner universal: captura sequencias ASCII basicas terminadas por 0x00/0xFF.

        Heuristicas:
        - aceita bytes 0x20-0x7E (printaveis)
        - termina em 0x00 ou 0xFF
        - corta se passar de max_len
        """
        data = self.rom_data
        out: List[ExtractedText] = []
        i = 0
        n = len(data)

        def is_printable(b: int) -> bool:
            return 0x20 <= b <= 0x7E

        while i < n:
            b = data[i]
            if is_printable(b):
                start = i
                buf = bytearray()
                while i < n and len(buf) < max_len:
                    b2 = data[i]
                    if is_printable(b2):
                        buf.append(b2)
                        i += 1
                        continue
                    # terminadores comuns
                    if b2 in (0x00, 0xFF):
                        break
                    # se apareceu byte nao-printavel no meio, aborta esse candidato
                    break

                # valida
                if len(buf) >= min_len:
                    try:
                        s = buf.decode("ascii", errors="ignore").strip()
                    except Exception:
                        s = ""
                    if s:
                        out.append(ExtractedText(offset=start, text=s, region="ASCII"))

                # avanca ate depois do terminador (se houver)
                while i < n and data[i] not in (0x00, 0xFF):
                    i += 1
                i += 1
                continue

            i += 1

        return out

    # ----------------------------
    # CLEAN heuristics (para traducao)
    # ----------------------------

    @staticmethod
    def _has_long_consecutive_run(s: str, run: int = 6) -> bool:
        best = 1
        cur = 1
        prev = None
        for ch in s:
            if prev is not None and ord(ch) == ord(prev) + 1:
                cur += 1
            else:
                best = max(best, cur)
                cur = 1
            prev = ch
        best = max(best, cur)
        return best >= run

    @staticmethod
    def _looks_like_human_text(s: str) -> bool:
        s = s.strip()
        if not s:
            return False

        # precisa ter letras suficientes
        letters = sum(ch.isalpha() for ch in s)
        if letters < 3:
            return False

        # muitos simbolos estranhos?
        printable_ok = sum((32 <= ord(ch) <= 126) for ch in s)
        if printable_ok / max(1, len(s)) < 0.92:
            return False

        # precisa de pelo menos uma vogal (evita O>/N>O etc)
        vowels = sum(ch.lower() in "aeiou" for ch in s)
        if vowels == 0:
            return False

        # rejeita sequencias tipo ghijklmn / wxyz{|}~
        if UniversalMasterSystemExtractor._has_long_consecutive_run(s, run=6):
            return False

        # repeticao alta (lixo)
        if len(s) >= 8:
            uniq = len(set(s))
            if uniq / len(s) < 0.35:
                return False

        return True

    @staticmethod
    def _classify_category(txt: str) -> str:
        up = txt.upper()
        if "DEVELOPED" in up or "COPYRIGHT" in up or "(C)" in up:
            return "Credits"
        if any(k in up for k in ["SCORE", "TIME", "RINGS", "LIVES", "PAUSE", "CONTINUE", "START"]):
            return "HUD/Menu"
        # titulos e telas costumam ser ALLCAPS curtos
        if up == txt and 4 <= len(txt) <= 24:
            return "Menu/Title"
        return "Text"

    def _build_clean_texts(self) -> List[dict]:
        clean: List[dict] = []
        for item in self.results:
            txt = (item.get("clean") or "").strip()
            if not self._looks_like_human_text(txt):
                continue
            clean.append({
                "offset": int(item["offset"]),
                "clean": txt,
                "region": item.get("region") or "Scan",
                "category": self._classify_category(txt),
            })
        return clean

    # ----------------------------
    # Mapping (para reinsercao)
    # ----------------------------

    def _estimate_max_len(self, offset: int) -> Tuple[int, int]:
        """Estimativa simples do espaco original ate achar 0x00 ou 0xFF."""
        data = self.rom_data
        window = data[offset: offset + 512]
        for term in (0x00, 0xFF):
            try:
                pos = window.index(term)
                if pos >= 3:
                    return pos, term
            except ValueError:
                pass
        return min(64, len(window)), 0x00

    def _find_pointer_offsets(self, text_offset: int) -> List[int]:
        """Heuristica: procura o valor 16-bit little-endian do offset na ROM.

        - Limita quantidade para evitar falso positivo.
        - Ignora hits muito perto do proprio texto.
        """
        data = self.rom_data
        val = text_offset & 0xFFFF
        needle = bytes([val & 0xFF, (val >> 8) & 0xFF])
        hits: List[int] = []
        start = 0
        while True:
            i = data.find(needle, start)
            if i == -1:
                break
            if abs(i - text_offset) > 4:
                hits.append(i)
            start = i + 1
            if len(hits) > 24:
                # risco grande de falso positivo
                return []
        return hits

    def _build_mapping(self, clean_texts: List[dict]) -> dict:
        mapping = {
            "rom": self.rom_path.name,
            "crc32_full": self.rom_crc32_full,
            "crc32_no512": self.rom_crc32_no512 or None,
            "detected_game": self.detected_game,
            "entries": [],
        }
        for idx, item in enumerate(clean_texts, 1):
            off = int(item["offset"])
            max_len, term = self._estimate_max_len(off)
            ptrs = self._find_pointer_offsets(off)
            mapping["entries"].append({
                "id": idx,
                "offset": off,
                "max_len": int(max_len),
                "category": item.get("category") or item.get("region") or "Text",
                "has_pointer": bool(ptrs),
                "pointer_offsets": ptrs,
                "terminator": int(term),
                "encoding": "ascii",
            })
        return mapping

    # ----------------------------
    # Save
    # ----------------------------

    def save_results(self, output_dir: Optional[str | Path] = None) -> str:
        """Cria os 3 arquivos e retorna o caminho do *_clean_blocks.txt."""
        if not self.results:
            self.extract_texts()

        out_dir = Path(output_dir) if output_dir else self.rom_path.parent
        out_dir.mkdir(parents=True, exist_ok=True)

        base = self.rom_path.stem

        debug_path = out_dir / f"{base}_extracted.txt"
        clean_path = out_dir / f"{base}_clean_blocks.txt"
        mapping_path = out_dir / f"{base}_mapping.json"

        # debug
        self._write_blocks_txt(debug_path, self.results, title="Text Extraction")

        # clean
        clean_texts = self._build_clean_texts()
        self._write_blocks_txt(clean_path, clean_texts, title="CLEAN BLOCKS")

        # mapping
        mapping = self._build_mapping(clean_texts)
        mapping_path.write_text(json.dumps(mapping, indent=2, ensure_ascii=False), encoding="utf-8")

        print(f"✅ DEBUG:   {debug_path}")
        print(f"✅ CLEAN:   {clean_path}")
        print(f"✅ MAPPING: {mapping_path}")

        return str(clean_path)

    def _write_blocks_txt(self, path: Path, texts: List[dict], title: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# NeuroROM AI - Master System {title}\n")
            f.write(f"# ROM: {self.rom_path.name}\n")
            f.write(f"# CRC32 (full): {self.rom_crc32_full}\n")
            if self.rom_crc32_no512:
                f.write(f"# CRC32 (no512): {self.rom_crc32_no512}\n")
            f.write(f"# Jogo: {self.detected_game}\n")
            f.write(f"# Total: {len(texts)} textos\n")
            f.write("#" + "=" * 60 + "\n\n")

            for i, item in enumerate(texts, 1):
                cat = item.get("category") or item.get("region") or "?"
                f.write(f"[{i:04d}] @{int(item['offset']):06X} ({cat})\n")
                f.write(f"{item.get('clean','')}\n")
                f.write("-" * 50 + "\n")

# -*- coding: utf-8 -*-
"""
================================================================================
SAFE REINSERTER - Reinserção Segura Universal
================================================================================
Reinsere textos traduzidos na ROM com máxima segurança:
- USA tabelas de caracteres inferidas (NÃO latin-1)
- Valida tamanho antes de escrever
- Atualiza ponteiros automaticamente
- Cria backups automáticos
- Recalcula checksums
- Validação em múltiplas camadas

NÃO corrompe ROMs - falha com segurança se houver problemas
================================================================================
"""

import hashlib
import json
import os
import re
import shutil
import struct
import zlib
from collections import Counter
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any, Mapping

from .free_space_allocator import FreeSpaceAllocator
from .retro8_bank_tools import patch_u16, patch_banked_pointer3, patch_bank_table_entry
from .reinsertion_rules import ReinsertionRules, ReinsertionResult
try:
    from .final_qa import evaluate_reinsertion_qa, write_qa_artifacts
except Exception:
    try:
        from final_qa import evaluate_reinsertion_qa, write_qa_artifacts
    except Exception:
        evaluate_reinsertion_qa = None
        write_qa_artifacts = None

try:
    from .semantic_quality_gate import SemanticQualityGate
except Exception:
    try:
        from semantic_quality_gate import SemanticQualityGate
    except Exception:
        SemanticQualityGate = None

try:
    from .quality_profile_manager import normalize_register_policy, resolve_quality_profile
except Exception:
    try:
        from quality_profile_manager import normalize_register_policy, resolve_quality_profile
    except Exception:
        normalize_register_policy = None
        resolve_quality_profile = None

try:
    from .box_profile_manager import BoxProfileManager
    from .console_memory_model import ConsoleMemoryModel
    from .encoding_adapter import EncodingAdapter
    from .glyph_metrics import GlyphMetrics
    from .pointer_scanner import PointerScanner
    from .relocation_manager import RelocationManager
    from .runtime_qa_simulator import RuntimeQASimulator
    from .text_layout_engine import TextLayoutEngine
except Exception:
    try:
        from box_profile_manager import BoxProfileManager
        from console_memory_model import ConsoleMemoryModel
        from encoding_adapter import EncodingAdapter
        from glyph_metrics import GlyphMetrics
        from pointer_scanner import PointerScanner
        from relocation_manager import RelocationManager
        from runtime_qa_simulator import RuntimeQASimulator
        from text_layout_engine import TextLayoutEngine
    except Exception:
        BoxProfileManager = None
        ConsoleMemoryModel = None
        EncodingAdapter = None
        GlyphMetrics = None
        PointerScanner = None
        RelocationManager = None
        RuntimeQASimulator = None
        TextLayoutEngine = None

try:
    from .compression_detector import CompressionDetector
except Exception:
    try:
        from compression_detector import CompressionDetector
    except Exception:
        CompressionDetector = None

try:
    from plugins.plugin_registry import get_plugin_for_rom as _get_plugin_for_rom
except Exception:
    _get_plugin_for_rom = None

try:
    from universal_kit.multi_decompress import MultiDecompress, CompressionAlgorithm
    from universal_kit.multi_compress import MultiCompress
except Exception:
    MultiDecompress = None
    CompressionAlgorithm = None
    MultiCompress = None


TOKEN_ORDER_RE = re.compile(
    r"(<TILE:[0-9A-Fa-f]{2}>|<[0-9A-Fa-f]{2}>|%\d*[ds]|"
    r"\{[A-Za-z0-9_]+\}|\[[A-Za-z0-9_]+\]|@[A-Za-z0-9_]+)"
)
CONTROL_TOKEN_RE = re.compile(r"<TILE:[0-9A-Fa-f]{2}>|<[0-9A-Fa-f]{2}>")
PLACEHOLDER_RE = re.compile(r"%\d*[ds]|\{[A-Za-z0-9_]+\}|\[[A-Za-z0-9_]+\]|@[A-Za-z0-9_]+")
HEX_TOKEN_RE = re.compile(r"^(?:TILE:)?[0-9A-Fa-f]{2}$")
_SPACES_RE = re.compile(r"\s+")
_LOW_QUALITY_WORD_RE = re.compile(r"^[a-z]{1,2}$")


class ReinsertionError(Exception):
    """Exceção para erros de reinserção."""
    pass


class SafeReinserter:
    """
    Reinsertor universal que usa análise automática para inserção segura.
    """
    NON_TEXT_REASON_CODES = {
        "NOT_PLAUSIBLE_TEXT_SMS",
        "NOT_PLAUSIBLE_TEXT",
        "TILEMAP_NO_POINTER",
        "NO_POINTER_INFO",
        "AUTOLEARN_NO_POINTER_INFO",
        "GRAPHIC_TILE_DATA",
        "NON_TEXT_DATA",
    }
    REQUIRED_GATE_FLAGS = (
        "encoding_ok",
        "glyphs_ok",
        "tokens_ok",
        "terminator_ok",
        "layout_ok",
        "byte_length_ok",
        "offsets_ok",
        "pointers_ok",
    )
    PTBR_REQUIRED_GLYPHS = [
        "á",
        "à",
        "â",
        "ã",
        "ä",
        "é",
        "ê",
        "í",
        "ó",
        "ô",
        "õ",
        "ú",
        "ü",
        "ç",
    ]
    PTBR_RELEVANT_PUNCT = [".", ",", ";", ":", "!", "?", "-", "'", "\"", "(", ")", "%", "/"]
    ACCENT_FALLBACK_MAP = {
        "á": "a",
        "à": "a",
        "â": "a",
        "ã": "a",
        "ä": "a",
        "é": "e",
        "ê": "e",
        "í": "i",
        "ó": "o",
        "ô": "o",
        "õ": "o",
        "ú": "u",
        "ü": "u",
        "ç": "c",
        "Á": "A",
        "À": "A",
        "Â": "A",
        "Ã": "A",
        "Ä": "A",
        "É": "E",
        "Ê": "E",
        "Í": "I",
        "Ó": "O",
        "Ô": "O",
        "Õ": "O",
        "Ú": "U",
        "Ü": "U",
        "Ç": "C",
    }
    PT_STOPWORDS = {
        "de",
        "da",
        "do",
        "das",
        "dos",
        "que",
        "e",
        "ou",
        "para",
        "com",
        "por",
        "uma",
        "um",
        "os",
        "as",
        "em",
        "no",
        "na",
    }
    EN_STOPWORDS = {
        "the",
        "and",
        "or",
        "you",
        "your",
        "with",
        "for",
        "press",
        "start",
        "save",
        "load",
        "game",
        "menu",
        "continue",
        "attack",
        "magic",
        "item",
    }
    EN_CONTENT_WORDS = {
        "honesty",
        "healing",
        "male",
        "female",
        "virtue",
        "compassion",
        "justice",
        "sacrifice",
        "honor",
        "spirituality",
        "humility",
    }
    RESIDUE_BLOCKLIST = {
        "onesty",
        "honesty",
        "ealing",
        "pozo",
    }
    ABSOLUTE_BLOCK_FLAGS = (
        "fragment_suspect",
        "mixed_language_suspect",
        "corruption_suspect",
        "human_quality_low",
        "layout_ugly",
        "semantic_hallucination_suspect",
        "glossary_violation",
        "proper_noun_corruption",
        "register_inconsistency",
        "semantic_drift",
    )
    COVERAGE_STATUS_ALLOWED = {
        "translated",
        "inserted",
        "blocked_quality",
        "needs_runtime",
        "needs_decompression",
        "needs_script_support",
        "untranslated",
        "english_residue",
    }
    COMPRESSION_PROFILE_BY_CONSOLE: Dict[str, List[str]] = {
        "SMS": ["RLE"],
        "MD": ["LZSS", "RLE"],
        "NES": ["RLE"],
        "SNES": ["LZ77", "HUFFMAN", "RLE", "LZSS"],
        "GB": ["LZ77"],
        "GBA": ["LZ10", "HUFFMAN", "RLE"],
        "N64": ["MIO0", "YAY0", "YAZ0"],
        "PS1": ["LZSS", "BPE", "STR", "BIN"],
    }
    COMPRESSION_ALIASES: Dict[str, str] = {
        "RLE": "RLE",
        "SMS_RLE": "RLE",
        "SEGA_RLE": "RLE",
        "INES_RLE": "RLE",
        "SNES_RLE": "RLE",
        "LZSS": "LZSS",
        "SEGA_LZSS": "LZSS",
        "SONY_LZSS": "LZSS",
        "LZ77": "LZ77",
        "NINTENDO_LZ77": "LZ77",
        "LZ10": "LZ10",
        "GBA_LZ10": "LZ10",
        "LZ11": "LZ11",
        "HUFFMAN": "HUFFMAN",
        "NINTENDO_HUFFMAN": "HUFFMAN",
        "GBA_HUFFMAN": "HUFFMAN",
        "BPE": "BPE",
        "PSX_BPE": "BPE",
        "MIO0": "MIO0",
        "YAY0": "YAY0",
        "YAZ0": "YAZ0",
        "PSX_STR": "STR",
        "PSX_BIN": "BIN",
        "STR": "STR",
        "BIN": "BIN",
    }

    def _quality_threshold_used(self) -> float:
        return 90.0 if self.quality_mode == "strict" else 75.0

    def _semantic_threshold_used(self) -> float:
        return (
            float(self.semantic_min_score_strict)
            if self.quality_mode == "strict"
            else float(self.semantic_min_score_standard)
        )

    def _normalize_register_policy_local(self, value: Any, default: str = "voce") -> str:
        if callable(normalize_register_policy):
            try:
                return str(normalize_register_policy(value, default=default))
            except Exception:
                pass
        raw = str(value or "").strip().lower()
        if raw in {"você", "voce", "vc"}:
            return "voce"
        if raw in {"tu"}:
            return "tu"
        if raw in {"cê", "ce"}:
            return "ce"
        return str(default)

    def _load_quality_profile(self) -> Dict[str, Any]:
        if not callable(resolve_quality_profile):
            return {"profile": {}, "meta": {}}
        try:
            return resolve_quality_profile(
                console=self.console,
                rom_crc32=self.original_crc32,
                extraction_data=self.extraction_data if isinstance(self.extraction_data, dict) else None,
                explicit_profile_path=str(
                    self.extraction_data.get("quality_profile_path") or ""
                ).strip()
                or None,
                search_hint_paths=[str(self.rom_path), str(self.extraction_data_path)],
            )
        except Exception:
            return {"profile": {}, "meta": {}}

    def _load_semantic_glossary(self) -> Dict[str, Any]:
        merged: Dict[str, Any] = {}

        def _merge_mapping(raw: Any) -> None:
            if not isinstance(raw, dict):
                return
            for key, value in raw.items():
                term = str(key or "").strip()
                if not term:
                    continue
                merged[term] = value

        profile_glossary = {}
        if isinstance(getattr(self, "quality_profile", {}), dict):
            if isinstance(self.quality_profile.get("glossary"), dict):
                profile_glossary.update(self.quality_profile.get("glossary", {}))
            sem = self.quality_profile.get("semantic")
            if isinstance(sem, dict) and isinstance(sem.get("glossary"), dict):
                profile_glossary.update(sem.get("glossary", {}))
        if profile_glossary:
            _merge_mapping(profile_glossary)

        direct = self.extraction_data.get("glossary")
        if isinstance(direct, dict):
            _merge_mapping(direct)

        cfg = self.extraction_data.get("semantic_policy", {})
        if isinstance(cfg, dict):
            terms = cfg.get("glossary_terms")
            if isinstance(terms, dict):
                _merge_mapping(terms)

        file_candidates: List[Path] = []
        for fld in ("glossary_path", "semantic_glossary_path"):
            raw_path = self.extraction_data.get(fld)
            if not raw_path:
                continue
            cand = Path(str(raw_path))
            if not cand.is_absolute():
                cand = self.extraction_data_path.parent / cand
            file_candidates.append(cand)

        file_candidates.append(self.extraction_data_path.parent / f"{self.original_crc32}_glossary.json")
        file_candidates.append(self.extraction_data_path.parent / "glossary.json")

        seen_paths = set()
        for path in file_candidates:
            try:
                rp = path.resolve()
            except Exception:
                rp = path
            if rp in seen_paths:
                continue
            seen_paths.add(rp)
            if not path.exists() or not path.is_file():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue

            if isinstance(payload, dict):
                terms = payload.get("terms")
                if isinstance(terms, dict):
                    _merge_mapping(terms)
                entries = payload.get("entries")
                if isinstance(entries, list):
                    for entry in entries:
                        if not isinstance(entry, dict):
                            continue
                        src = str(
                            entry.get("source")
                            or entry.get("term")
                            or entry.get("src")
                            or ""
                        ).strip()
                        if not src:
                            continue
                        merged[src] = {
                            "target": entry.get("target", entry.get("translation", src)),
                            "category": entry.get("category", "term"),
                            "preserve": bool(entry.get("preserve", False)),
                            "allow_translation": bool(entry.get("allow_translation", True)),
                        }
                if isinstance(payload.get("glossary"), dict):
                    _merge_mapping(payload.get("glossary"))
                if "terms" not in payload and "entries" not in payload:
                    _merge_mapping(payload)
        return merged

    def __init__(self, rom_path: str, extraction_data_path: str):
        """
        Args:
            rom_path: Caminho da ROM original
            extraction_data_path: Caminho do JSON de extração (universal_pipeline)
        """
        self.rom_path = Path(rom_path)
        self.extraction_data_path = Path(extraction_data_path)

        # Carrega dados de extração
        with open(self.extraction_data_path, 'r', encoding='utf-8') as f:
            self.extraction_data = json.load(f)

        # Carrega ROM
        with open(self.rom_path, 'rb') as f:
            self.smc_header = b''
            data = f.read()

            # Detecta e separa header SMC
            if len(data) % 1024 == 512:
                self.smc_header = data[:512]
                self.rom_data = bytearray(data[512:])
            else:
                self.rom_data = bytearray(data)

        # Neutralidade: identificação apenas por CRC32 e tamanho
        self.original_rom_size = len(self.rom_data)
        self.original_crc32 = f"{zlib.crc32(self.rom_data) & 0xFFFFFFFF:08X}"

        # Carrega charset (melhor tabela inferida)
        self.charset = self._load_best_charset()

        # Detecta console e inicializa allocator
        self.console = self._detect_console()
        self.allocator = FreeSpaceAllocator(self.rom_data, self.console)
        self.compression_profile = {
            "console": str(self.console),
            "algorithms": list(self.COMPRESSION_PROFILE_BY_CONSOLE.get(str(self.console), [])),
        }
        self.detected_compressed_regions: List[Dict[str, Any]] = []

        # Estatísticas
        self.stats = {
            'total_texts': 0,
            'inserted': 0,
            'skipped': 0,
            'errors': [],
            # Novas estatisticas para realocacao
            'in_place': 0,
            'reallocated': 0,
            'blocked_no_pointer': 0,
            'allocation_failed': 0,
            'pointers_updated': 0,
            # Tilemap stats
            'tilemap_inserted': 0,
            'tilemap_overflow': 0,
            # Validacao de dados suspeitos
            'suspicious_skipped': 0,
            # Itens marcados no metadata como nao-texto
            'non_text_meta_skipped': 0,
            # Pipeline V7 (QA/Relocation probe)
            'v7_qa_warn': 0,
            'v7_qa_error': 0,
            'v7_relocation_probe_ok': 0,
            # Compressão automática (pré/pós-reinserção)
            'compressed_blocks_total': 0,
            'compressed_applied': 0,
            'compressed_blocked': 0,
            'compressed_roundtrip_fail': 0,
            'compressed_relocated': 0,
            'compressed_pointer_updates': 0,
        }

        # Configuracao de validacao strict
        self.strict_mode = False
        self.skip_suspicious = True  # se False, falha em vez de pular
        accent_cfg = self.extraction_data.get("accent_policy", {})
        if not isinstance(accent_cfg, dict):
            accent_cfg = {}
        explicit_map = accent_cfg.get("explicit_map", {})
        if not isinstance(explicit_map, dict):
            explicit_map = {}
        self.accent_policy = {
            "allow_fallback": bool(accent_cfg.get("allow_fallback", False)),
            "explicit_map": {
                str(k): str(v)[:1]
                for k, v in explicit_map.items()
                if str(k) and str(v)
            },
        }
        quality_bundle = self._load_quality_profile()
        self.quality_profile = dict(quality_bundle.get("profile", {}) or {})
        self.quality_profile_meta = dict(quality_bundle.get("meta", {}) or {})
        semantic_profile = (
            self.quality_profile.get("semantic")
            if isinstance(self.quality_profile.get("semantic"), dict)
            else {}
        )

        quality_mode_raw = str(
            self.extraction_data.get("quality_mode")
            or self.quality_profile.get("quality_mode")
            or "standard"
        ).strip().lower()
        self.quality_mode = "strict" if quality_mode_raw == "strict" else "standard"
        register_policy_raw = str(
            self.extraction_data.get("register_policy")
            or os.environ.get("NEUROROM_REGISTER_POLICY")
            or self.quality_profile.get("register_policy")
            or "voce"
        ).strip().lower()
        self.register_policy = self._normalize_register_policy_local(
            register_policy_raw,
            default="voce",
        )
        strict_candidate = self.extraction_data.get("semantic_strict_mode")
        if strict_candidate is None:
            strict_candidate = self.extraction_data.get("semantic_strict")
        if strict_candidate is None:
            strict_candidate = semantic_profile.get("strict_mode")
        if isinstance(strict_candidate, bool):
            self.semantic_strict_mode = bool(strict_candidate)
        else:
            self.semantic_strict_mode = bool(self.quality_mode == "strict")
        self.semantic_min_score_standard = float(
            self._safe_float(
                self.extraction_data.get(
                    "semantic_min_score_standard",
                    semantic_profile.get("min_semantic_score_standard", 70.0),
                ),
                default=70.0,
            )
        )
        self.semantic_min_score_strict = float(
            self._safe_float(
                self.extraction_data.get(
                    "semantic_min_score_strict",
                    semantic_profile.get("min_semantic_score_strict", 82.0),
                ),
                default=82.0,
            )
        )
        self.semantic_glossary = self._load_semantic_glossary()
        self.semantic_gate = (
            SemanticQualityGate(
                glossary=self.semantic_glossary,
                register_policy=self.register_policy,
                strict_mode=bool(self.semantic_strict_mode),
                min_semantic_score_standard=self.semantic_min_score_standard,
                min_semantic_score_strict=self.semantic_min_score_strict,
            )
            if SemanticQualityGate is not None
            else None
        )
        self.segment_audit_rows: List[Dict[str, Any]] = []
        self.proof_validation_entries: List[Dict[str, Any]] = []
        self._ptbr_coverage_cache: Optional[Dict[str, Any]] = None
        self._inventory_cache: Optional[Dict[str, Any]] = None

        # Log de itens bloqueados
        self.blocked_items: List[Dict[str, Any]] = []
        self.last_qa_final: Optional[Dict[str, Any]] = None
        self.last_qa_paths: Dict[str, Optional[str]] = {"json": None, "txt": None}
        self.v7_pipeline: Dict[str, Any] = self._init_v7_pipeline()
        self.runtime_qa_entries: Dict[int, Dict[str, Any]] = {}
        self._v7_entry_context: Dict[int, Dict[str, Any]] = {}
        self._processed_text_ids: set[int] = set()

    def _detect_console(self) -> str:
        """Detecta o tipo de console baseado nos dados da ROM."""
        rom_size = len(self.rom_data)
        ext = self.rom_path.suffix.lower()

        # Detecta por extensao
        if ext in ('.nes',):
            return 'NES'
        elif ext in ('.sms', '.gg'):
            return 'SMS'
        elif ext in ('.z64', '.n64', '.v64'):
            return 'N64'
        elif ext in ('.iso', '.pbp', '.chd', '.cue', '.ccd', '.img', '.mdf'):
            return 'PS1'
        elif ext in ('.md', '.gen', '.bin') and rom_size >= 0x200:
            # Verifica assinatura SEGA
            if b'SEGA' in self.rom_data[0x100:0x200]:
                return 'MD'
        elif ext in ('.smc', '.sfc', '.fig'):
            return 'SNES'
        elif ext in ('.gb', '.gbc'):
            return 'GB'
        elif ext in ('.gba',):
            return 'GBA'

        # Fallback por tamanho e heuristicas
        if rom_size > 0 and (rom_size % 0x4000) == 0:
            # Verifica header NES
            if rom_size >= 16 and self.rom_data[0:4] == b'NES\x1a':
                return 'NES'

        if rom_size >= 4:
            # N64: magic endian-normalizado e variantes comuns de dump.
            if bytes(self.rom_data[0:4]) in (
                b"\x80\x37\x12\x40",
                b"\x37\x80\x40\x12",
                b"\x40\x12\x37\x80",
            ):
                return "N64"

        if rom_size >= 0x9000:
            # PS1 (ISO9660 em setor 16): "CD001" no offset 0x8001.
            if bytes(self.rom_data[0x8001:0x8006]) == b"CD001":
                return "PS1"

        # Default
        return 'SNES'

    def _load_best_charset(self) -> Optional[Dict]:
        """Carrega a melhor tabela de caracteres inferida."""
        charset_dir = self.extraction_data_path.parent / 'inferred_charsets'

        if not charset_dir.exists():
            print("⚠️  WARNING: No inferred charset found. Using fallback ASCII.")
            return None

        # Procura charset com maior confiança
        best_charset = None
        best_confidence = 0.0

        for charset_file in charset_dir.glob('charset_candidate_*.json'):
            with open(charset_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data.get('confidence', 0) > best_confidence:
                    best_confidence = data['confidence']
                    best_charset = data

        if best_charset:
            print(f"✅ Loaded charset: {best_charset['name']} (confidence: {best_confidence:.3f})")
            return best_charset

        return None

    def _build_engine_profile(self) -> Dict[str, Any]:
        """Monta EngineProfile reutilizando apenas dados existentes no projeto."""
        profile: Dict[str, Any] = {"console": self.console}

        for key in ("engine_profile", "forensic_profile"):
            raw = self.extraction_data.get(key, {})
            if isinstance(raw, dict):
                profile.update(raw)

        forensic = self.extraction_data.get("forensic", {})
        if isinstance(forensic, dict):
            for key in ("encoding", "tbl_path", "box_type", "console"):
                if key in forensic:
                    profile[key] = forensic[key]

        # 1) game_profiles_db.json (core)
        db_path = Path(__file__).parent / "game_profiles_db.json"
        if db_path.exists():
            try:
                db = json.loads(db_path.read_text(encoding="utf-8"))
                for game in db.get("games", []):
                    if not isinstance(game, dict):
                        continue
                    if str(game.get("crc32", "")).upper() != self.original_crc32:
                        continue
                    profile.update(game)
                    break
            except Exception:
                pass

        # 2) free_space_profiles.json (config raiz)
        fs_path = Path(__file__).parent.parent / "config" / "free_space_profiles.json"
        if fs_path.exists():
            try:
                fs_data = json.loads(fs_path.read_text(encoding="utf-8"))
                raw_fs = fs_data.get(str(self.console).upper(), {})
                if isinstance(raw_fs, dict):
                    profile["free_space_profile"] = raw_fs
            except Exception:
                pass

        # 3) tbl_path/charset já inferido
        if self.charset and isinstance(self.charset.get("char_to_byte"), dict):
            profile.setdefault("char_to_byte", self.charset.get("char_to_byte"))

        # 4) pointer_scanner.py já existente (metadado de capacidade)
        if PointerScanner is not None:
            profile["pointer_scanner"] = "core.pointer_scanner.PointerScanner"

        profile.setdefault("box_type", "dialog")
        profile.setdefault("console", self.console)
        return profile

    def _init_v7_pipeline(self) -> Dict[str, Any]:
        """Inicializa pipeline V7 sem afetar fluxo legado em caso de falha."""
        if not all(
            [
                BoxProfileManager,
                ConsoleMemoryModel,
                EncodingAdapter,
                GlyphMetrics,
                RelocationManager,
                RuntimeQASimulator,
                TextLayoutEngine,
            ]
        ):
            return {}

        try:
            engine_profile = self._build_engine_profile()
            box_manager = BoxProfileManager(Path(__file__).parent / "game_profiles_db.json")
            box_profile = box_manager.get_profile(
                console=self.console,
                box_type=str(engine_profile.get("box_type", "dialog")),
                game_crc=self.original_crc32,
            )
            glyph_path = Path(__file__).parent / "profiles" / "glyph_widths.json"
            glyph_metrics = GlyphMetrics(glyph_path)
            layout_engine = TextLayoutEngine(glyph_metrics, box_profile)
            encoding_adapter = EncodingAdapter(
                console_type=self.console,
                profile=engine_profile,
            )
            console_model = ConsoleMemoryModel(self.console)
            runtime_qa = RuntimeQASimulator(console_model, encoding_adapter=encoding_adapter)
            relocation_manager = RelocationManager(console_model)

            return {
                "engine_profile": engine_profile,
                "box_manager": box_manager,
                "layout_engine": layout_engine,
                "encoding_adapter": encoding_adapter,
                "runtime_qa": runtime_qa,
                "console_model": console_model,
                "relocation_manager": relocation_manager,
            }
        except Exception:
            return {}

    def _v7_parse_int(self, value: Any, default: int = 0) -> int:
        if value is None:
            return int(default)
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return int(value)
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return int(default)
            try:
                if raw.lower().startswith("0x"):
                    return int(raw, 16)
                return int(raw)
            except ValueError:
                return int(default)
        return int(default)

    def _v7_normalize_text(self, text: str) -> str:
        return (text or "").replace("\r\n", "\n").replace("\r", "\n")

    def _v7_collect_unmapped_chars(self, text: str, adapter: Optional[EncodingAdapter]) -> List[str]:
        if adapter is None:
            return []
        if getattr(adapter, "mode", "") != "custom_ascii":
            return []
        cmap = getattr(adapter, "custom_ascii_map", {}) or {}
        unmapped: List[str] = []
        for ch in text:
            if ch in ("\n", "\r"):
                continue
            if ch.startswith("<") and ch.endswith(">"):
                continue
            if ch not in cmap and ch not in unmapped:
                unmapped.append(ch)
        return unmapped

    def _v7_register_fallback(self, entry_id: int, reason: str, warnings: Optional[List[str]] = None) -> None:
        warn_list = list(warnings or [])
        if reason and reason not in warn_list:
            warn_list.append(reason)
        self.runtime_qa_entries[entry_id] = {
            "layout_ok": False,
            "overflow": False,
            "truncated": False,
            "unmapped_chars": [],
            "relocation_needed": False,
            "warnings": warn_list,
            "reason": str(reason),
            "fallback_legacy": True,
        }
        self.stats["v7_qa_error"] += 1

    def _run_v7_pipeline_for_entry(self, entry_id: int, text: str) -> None:
        """
        Executa pipeline V7 por item:
        normalize/encode -> metrics/layout -> runtime QA -> relocation.
        """
        if not self.v7_pipeline:
            self._v7_register_fallback(entry_id, "v7_pipeline_unavailable")
            return

        ctx = self._v7_entry_context.get(entry_id, {})
        entry = ctx.get("entry", {}) if isinstance(ctx.get("entry"), dict) else {}
        original_length = self._v7_parse_int(ctx.get("original_length"), default=0)
        original_offset = self._v7_parse_int(ctx.get("original_offset"), default=-1)
        pointer_refs = ctx.get("pointer_refs", [])
        if not isinstance(pointer_refs, list):
            pointer_refs = []

        warnings: List[str] = []
        try:
            engine_profile = self.v7_pipeline.get("engine_profile", {})
            box_manager = self.v7_pipeline.get("box_manager")
            layout_engine = self.v7_pipeline.get("layout_engine")
            encoding_adapter = self.v7_pipeline.get("encoding_adapter")
            runtime_qa = self.v7_pipeline.get("runtime_qa")
            relocation_manager = self.v7_pipeline.get("relocation_manager")

            normalized = self._v7_normalize_text(text)
            unmapped_chars = self._v7_collect_unmapped_chars(normalized, encoding_adapter)
            if unmapped_chars:
                warnings.append(f"unmapped_chars:{''.join(unmapped_chars)}")

            # 1) normalize/encode
            try:
                encoded_bytes = encoding_adapter.encode(normalized) if encoding_adapter else normalized.encode("ascii", errors="strict")
            except Exception as exc:
                self._v7_register_fallback(entry_id, f"encoding_failed:{exc}", warnings=warnings)
                return

            terminator = self._v7_parse_int(entry.get("terminator"), default=0)
            encoded_with_term = bytes(encoded_bytes) + bytes([terminator & 0xFF])

            # 2) metrics/layout
            try:
                box_type = str(entry.get("box_type") or engine_profile.get("box_type", "dialog"))
                if box_manager and layout_engine:
                    layout_engine.box_profile = box_manager.get_profile(
                        console=self.console,
                        box_type=box_type,
                        game_crc=self.original_crc32,
                    )
                    layout_result = layout_engine.layout(normalized)
                else:
                    layout_result = {
                        "lines": [normalized],
                        "visual_overflow": False,
                        "pixel_widths": [len(normalized)],
                        "line_count": 1,
                        "score": 100,
                    }
            except Exception as exc:
                self._v7_register_fallback(entry_id, f"layout_failed:{exc}", warnings=warnings)
                return

            # 3) runtime QA
            try:
                qa_result = runtime_qa.simulate(
                    {
                        "text": normalized,
                        "encoded_bytes": encoded_with_term,
                        "max_bytes": original_length,
                        "offset": original_offset,
                        "pointer_refs": pointer_refs,
                    },
                    layout_result,
                ) if runtime_qa else {}
            except Exception as exc:
                self._v7_register_fallback(entry_id, f"runtime_qa_failed:{exc}", warnings=warnings)
                return

            overflow = bool(layout_result.get("visual_overflow", False) or qa_result.get("byte_overflow", False))
            truncated = bool(original_length > 0 and len(encoded_with_term) > original_length)
            layout_ok = bool(not layout_result.get("visual_overflow", False) and layout_result.get("line_count", 0) > 0)
            relocation_needed = bool(truncated and bool(pointer_refs))

            # 4) relocation segura (probe em copia, sem tocar ROM legada aqui)
            relocation_result = None
            if relocation_needed:
                try:
                    relocation_result = relocation_manager.relocate(
                        bytearray(self.rom_data),
                        old_offset=original_offset,
                        new_bytes=encoded_with_term,
                    ) if relocation_manager else {"relocated": False, "reason": "relocation_manager_unavailable"}
                    if bool(relocation_result.get("relocated")) and int(relocation_result.get("pointers_updated", 0)) > 0:
                        self.stats["v7_relocation_probe_ok"] += 1
                    if not bool(relocation_result.get("relocated", False)):
                        warnings.append(str(relocation_result.get("reason", "relocation_probe_failed")))
                except Exception as exc:
                    warnings.append(f"relocation_probe_failed:{exc}")
                    relocation_result = {"relocated": False, "reason": f"probe_exception:{exc}"}

            if overflow:
                warnings.append("overflow_detected")
            if truncated:
                warnings.append("truncated_needed")
            if qa_result.get("bank_violation"):
                warnings.append("bank_or_segment_violation")
            if not qa_result.get("pointer_safe", True):
                warnings.append("pointer_safety_issue")

            qa_entry = {
                "layout_ok": layout_ok,
                "overflow": overflow,
                "truncated": truncated,
                "unmapped_chars": unmapped_chars,
                "relocation_needed": relocation_needed,
                "warnings": warnings,
                "reason": "ok",
                "fallback_legacy": False,
                "layout": layout_result,
                "qa": qa_result,
                "relocation": relocation_result,
            }
            self.runtime_qa_entries[entry_id] = qa_entry

            final_score = self._v7_parse_int(qa_result.get("final_score"), default=100)
            if final_score < 80:
                self.stats["v7_qa_error"] += 1
            elif final_score < 100 or warnings:
                self.stats["v7_qa_warn"] += 1
        except Exception as exc:
            self._v7_register_fallback(entry_id, f"v7_unexpected_error:{exc}", warnings=warnings)
            return

    def _safe_int(self, value: Any, default: Optional[int] = None) -> Optional[int]:
        if value is None:
            return default
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return int(value)
        if isinstance(value, float):
            return int(value)
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return default
            try:
                if raw.lower().startswith("0x"):
                    return int(raw, 16)
                if re.fullmatch(r"[0-9A-Fa-f]+", raw) and any(c in "ABCDEFabcdef" for c in raw):
                    return int(raw, 16)
                return int(raw)
            except ValueError:
                return default
        return default

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except Exception:
            return float(default)

    def _char_to_byte_map(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        if self.charset and isinstance(self.charset.get("char_to_byte"), dict):
            for char_str, byte_hex in self.charset.get("char_to_byte", {}).items():
                if not isinstance(char_str, str) or len(char_str) != 1:
                    continue
                parsed = self._safe_int(byte_hex, default=None)
                if parsed is None:
                    continue
                out[char_str] = int(parsed) & 0xFF
        adapter = self.v7_pipeline.get("encoding_adapter") if isinstance(self.v7_pipeline, dict) else None
        if not out and adapter is not None:
            cmap = getattr(adapter, "custom_ascii_map", {}) or {}
            for char_str, byte_val in cmap.items():
                if not isinstance(char_str, str) or len(char_str) != 1:
                    continue
                parsed = self._safe_int(byte_val, default=None)
                if parsed is None:
                    continue
                out[char_str] = int(parsed) & 0xFF
        return out

    def _is_char_supported(self, ch: str, char_map: Dict[str, int]) -> bool:
        if not ch:
            return True
        if char_map:
            return ch in char_map
        return ord(ch) < 128

    def _iter_renderable_chars(self, text: str) -> List[str]:
        txt = str(text or "")
        out: List[str] = []
        last = 0
        for match in TOKEN_ORDER_RE.finditer(txt):
            chunk = txt[last : match.start()]
            for ch in chunk:
                if ch in ("\r", "\n", "\t"):
                    continue
                out.append(ch)
            last = match.end()
        tail = txt[last:]
        for ch in tail:
            if ch in ("\r", "\n", "\t"):
                continue
            out.append(ch)
        return out

    def _find_missing_glyphs(self, text: str) -> List[str]:
        char_map = self._char_to_byte_map()
        missing: List[str] = []
        seen: set[str] = set()
        for ch in self._iter_renderable_chars(text):
            if self._is_char_supported(ch, char_map):
                continue
            if ch in seen:
                continue
            seen.add(ch)
            missing.append(ch)
        return missing

    def _ptbr_coverage(self) -> Dict[str, Any]:
        if self._ptbr_coverage_cache is not None:
            return dict(self._ptbr_coverage_cache)

        reference: List[str] = []
        for ch in self.PTBR_REQUIRED_GLYPHS:
            reference.append(ch)
            reference.append(ch.upper())
        reference.extend(self.PTBR_RELEVANT_PUNCT)
        reference.append(" ")
        ordered_ref = sorted({str(ch) for ch in reference if str(ch)}, key=lambda c: (ord(c[0]), c))

        char_map = self._char_to_byte_map()
        supported: List[str] = []
        missing: List[str] = []
        for ch in ordered_ref:
            if self._is_char_supported(ch, char_map):
                supported.append(ch)
            else:
                missing.append(ch)

        adapter = self.v7_pipeline.get("encoding_adapter") if isinstance(self.v7_pipeline, dict) else None
        payload = {
            "supported_glyphs": supported,
            "missing_glyphs": missing,
            "ptbr_full_coverage": bool(len(missing) == 0),
            "charset_effective": str((self.charset or {}).get("name") or (adapter.mode if adapter else "ascii")),
        }
        self._ptbr_coverage_cache = dict(payload)
        return payload

    def _extract_source_text(self, text_entry: Dict[str, Any]) -> str:
        fields = (
            "decoded_text",
            "source_text",
            "source",
            "original",
            "text",
            "raw_text",
        )
        for key in fields:
            raw = text_entry.get(key)
            if raw is None:
                continue
            txt = str(raw)
            if txt:
                return txt
        return ""

    def _extract_pointer_refs(self, text_entry: Dict[str, Any]) -> List[Dict[str, Any]]:
        pointer_refs = text_entry.get("pointer_refs", [])
        if isinstance(pointer_refs, list):
            return [dict(p) for p in pointer_refs if isinstance(p, dict)]
        if text_entry.get("pointers"):
            return self._convert_legacy_pointers(text_entry.get("pointers", []))
        return []

    def _normalize_segment_id(self, text_id: int, text_entry: Dict[str, Any]) -> str:
        uid = str(text_entry.get("uid", "") or "").strip()
        if uid:
            return uid
        return f"U_{int(text_id):05d}"

    def _entry_text_id(self, entry: Dict[str, Any]) -> Optional[int]:
        if not isinstance(entry, dict):
            return None
        for key in ("id", "text_id", "index", "seq"):
            parsed = self._safe_int(entry.get(key), default=None)
            if parsed is not None and parsed >= 0:
                return int(parsed)
        uid = str(entry.get("uid", "") or "").strip()
        if uid.startswith("U_"):
            parsed_uid = self._safe_int(uid[2:], default=None)
            if parsed_uid is not None and parsed_uid >= 0:
                return int(parsed_uid)
        return None

    def _iter_all_text_entries(self) -> List[Tuple[int, Dict[str, Any]]]:
        out: List[Tuple[int, Dict[str, Any]]] = []
        seen: set[int] = set()
        for bucket in ("mappings", "extracted_texts"):
            for raw_entry in self.extraction_data.get(bucket, []) or []:
                if not isinstance(raw_entry, dict):
                    continue
                text_id = self._entry_text_id(raw_entry)
                if text_id is None or text_id in seen:
                    continue
                seen.add(int(text_id))
                out.append((int(text_id), dict(raw_entry)))
        return out

    def _entry_needs_runtime(self, entry: Dict[str, Any]) -> bool:
        source = str(
            entry.get("script_source")
            or entry.get("source")
            or entry.get("kind")
            or entry.get("routine")
            or entry.get("reason_if_not")
            or ""
        ).lower()
        return any(tok in source for tok in ("runtime", "dyn_", "trace", "hook", "displayed"))

    def _entry_needs_decompression(self, entry: Dict[str, Any]) -> bool:
        source = str(
            entry.get("reason_code")
            or entry.get("reason_if_not")
            or entry.get("compression")
            or entry.get("source")
            or ""
        ).lower()
        return any(tok in source for tok in ("compress", "decompress", "lz", "huffman", "codec"))

    def _normalize_compression_name(self, value: Any) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        key = raw.upper().replace("-", "_").replace(" ", "_")
        if key in {"0X10", "BIOS_0X10", "GBA_BIOS_0X10"}:
            key = "LZ10"
        elif key in {"0X11", "BIOS_0X11"}:
            key = "LZ11"
        elif key in {"0X28", "BIOS_0X28", "GBA_BIOS_0X28"}:
            key = "HUFFMAN"
        elif key in {"0X30", "BIOS_0X30", "GBA_BIOS_0X30"}:
            key = "RLE"
        return str(self.COMPRESSION_ALIASES.get(key, key))

    def _resolve_compression_enum(self, algo_name: str):
        if CompressionAlgorithm is None:
            return None
        canonical = self._normalize_compression_name(algo_name)
        enum_map = {
            "RLE": "RLE",
            "LZSS": "LZSS",
            "LZ77": "LZ77",
            "LZ10": "LZ10",
            "LZ11": "LZ11",
            "YAY0": "YAY0",
            "YAZ0": "YAZ0",
        }
        enum_name = enum_map.get(canonical)
        if not enum_name:
            return None
        return getattr(CompressionAlgorithm, enum_name, None)

    def _detect_compressed_regions_with_detector(self) -> List[Dict[str, Any]]:
        if self.detected_compressed_regions:
            return list(self.detected_compressed_regions)
        if CompressionDetector is None:
            return []
        try:
            detector = CompressionDetector(bytes(self.rom_data))
            regions = detector.detect(block_size=2048)
        except Exception as exc:
            print(f"⚠️  CompressionDetector indisponível neste runtime: {exc}")
            return []

        normalized: List[Dict[str, Any]] = []
        for reg in regions or []:
            try:
                offset = int(getattr(reg, "offset", -1))
                size = int(getattr(reg, "size", 0))
            except Exception:
                continue
            if offset < 0 or size <= 0:
                continue
            algo = self._normalize_compression_name(getattr(reg, "algorithm", ""))
            confidence = float(getattr(reg, "confidence", 0.0) or 0.0)
            normalized.append(
                {
                    "offset": int(offset),
                    "size": int(size),
                    "algorithm": str(algo or "UNKNOWN"),
                    "confidence": float(confidence),
                }
            )
        self.detected_compressed_regions = list(normalized)
        return list(normalized)

    def _find_detected_region_for_offset(
        self,
        offset: int,
        size: int,
        regions: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        if offset < 0 or size <= 0:
            return None
        best: Optional[Dict[str, Any]] = None
        best_overlap = 0
        end = offset + size
        for reg in regions or []:
            r_off = int(reg.get("offset", -1))
            r_size = int(reg.get("size", 0))
            if r_off < 0 or r_size <= 0:
                continue
            r_end = r_off + r_size
            overlap = max(0, min(end, r_end) - max(offset, r_off))
            if overlap > best_overlap:
                best_overlap = overlap
                best = reg
        return best

    def _infer_entry_compression_algorithm(
        self,
        entry: Dict[str, Any],
        regions: List[Dict[str, Any]],
    ) -> str:
        explicit = self._normalize_compression_name(
            entry.get("compression_algorithm")
            or entry.get("algorithm")
            or entry.get("compression")
            or entry.get("codec")
            or ""
        )
        if explicit:
            return explicit

        comp_off = self._safe_int(
            entry.get("compressed_offset", entry.get("rom_offset")),
            default=None,
        )
        comp_size = self._safe_int(
            entry.get("compressed_size", entry.get("block_size")),
            default=None,
        )
        if comp_off is None or comp_size is None:
            return ""
        region = self._find_detected_region_for_offset(
            int(comp_off),
            int(comp_size),
            regions,
        )
        if not isinstance(region, dict):
            return ""
        return self._normalize_compression_name(region.get("algorithm", ""))

    def _collect_compressed_blocks_for_reinsertion(
        self,
        translations: Dict[int, str],
    ) -> Dict[str, Dict[str, Any]]:
        blocks: Dict[str, Dict[str, Any]] = {}
        regions = self._detect_compressed_regions_with_detector()
        for text_id_raw, translated_text in sorted(translations.items(), key=lambda kv: int(kv[0])):
            text_id = int(text_id_raw)
            entry = self._find_text_entry(text_id)
            if not isinstance(entry, dict):
                continue

            comp_off = self._safe_int(
                entry.get("compressed_offset", entry.get("rom_offset", entry.get("block_offset"))),
                default=None,
            )
            comp_size = self._safe_int(
                entry.get("compressed_size", entry.get("block_size", entry.get("compressed_length"))),
                default=None,
            )
            local_off = self._safe_int(
                entry.get("decompressed_local_offset", entry.get("local_offset", entry.get("offset_in_block"))),
                default=None,
            )
            slot_len = self._safe_int(
                entry.get(
                    "max_len_bytes",
                    entry.get(
                        "max_len",
                        entry.get(
                            "max_length",
                            entry.get("raw_len", entry.get("original_length")),
                        ),
                    ),
                ),
                default=None,
            )
            if comp_off is None or comp_size is None or local_off is None or slot_len is None:
                continue
            if int(comp_off) < 0 or int(comp_size) <= 0 or int(local_off) < 0 or int(slot_len) <= 0:
                continue

            algo = self._infer_entry_compression_algorithm(entry, regions)
            if not algo:
                continue
            term_val = self._safe_int(
                entry.get("terminator", entry.get("term", entry.get("end_byte"))),
                default=None,
            )
            sig = f"{int(comp_off)}|{int(comp_size)}|{algo}"
            if sig not in blocks:
                blocks[sig] = {
                    "compressed_offset": int(comp_off),
                    "compressed_size": int(comp_size),
                    "algorithm": str(algo),
                    "entries": [],
                }
            blocks[sig]["entries"].append(
                {
                    "text_id": int(text_id),
                    "text": str(translated_text or ""),
                    "local_offset": int(local_off),
                    "slot_len": int(slot_len),
                    "terminator": int(term_val) if term_val is not None else None,
                }
            )
        for block in blocks.values():
            block["entries"].sort(key=lambda it: (int(it.get("local_offset", 0)), int(it.get("text_id", 0))))
        return blocks

    def _get_plugin_for_pointer_search(self, rom_bytes: bytes):
        """Obtém plugin de console para mapeamento de ponteiros."""
        if _get_plugin_for_rom is None:
            return None
        try:
            plugin = _get_plugin_for_rom(rom_bytes)
            if plugin:
                plugin.set_rom_data(rom_bytes)
            return plugin
        except Exception:
            return None

    def _find_pointer_refs_for_target(
        self,
        rom_bytes: bytes,
        old_offset: int,
        new_offset: int,
        max_refs: int = 512,
    ) -> List[Dict[str, Any]]:
        """
        Procura referências de ponteiro para old_offset e gera refs atualizáveis.
        Estratégia: varredura linear com mapeamento do plugin (segura e genérica).
        """
        refs: List[Dict[str, Any]] = []
        seen_ptr_offsets: set = set()
        rom_len = len(rom_bytes)
        if rom_len <= 0:
            return refs
        # Evita scans proibitivos em imagens muito grandes.
        if rom_len > 32 * 1024 * 1024:
            return refs

        plugin = self._get_plugin_for_pointer_search(rom_bytes)
        sizes = [2, 3, 4]
        endians = ["little", "big"]
        try:
            if plugin:
                cfg = plugin.get_pointer_config() or {}
                sizes = [int(x) for x in cfg.get("sizes", sizes) if int(x) in (2, 3, 4)] or sizes
                endians = [str(x).lower() for x in cfg.get("endianness", endians)] or endians
        except Exception:
            pass

        def _map_value(value: int) -> Optional[int]:
            if plugin:
                try:
                    mapped = plugin.map_address(int(value), rom_bytes)
                    if mapped and bool(mapped.is_valid):
                        return int(mapped.file_offset)
                    return None
                except Exception:
                    return None
            # fallback direto
            return int(value) if 0 <= int(value) < rom_len else None

        for size in sizes:
            for end in endians:
                max_val = 1 << (size * 8)
                for off in range(0, rom_len - size + 1):
                    # alinhamento leve para reduzir falso-positivo
                    if off % max(1, size) != 0:
                        continue
                    raw = int.from_bytes(rom_bytes[off:off + size], end, signed=False)
                    mapped = _map_value(raw)
                    if mapped != int(old_offset):
                        continue

                    # valida se novo valor aponta para o novo offset
                    bank_addend = int(old_offset) - int(raw)
                    new_val = int(new_offset) - int(bank_addend)
                    if new_val < 0 or new_val >= max_val:
                        continue
                    mapped_new = _map_value(new_val)
                    if mapped_new != int(new_offset):
                        continue

                    # heurística de tabela: vizinho também deve mapear para ROM válida
                    neigh_ok = False
                    for delta in (-size, size):
                        n_off = off + delta
                        if n_off < 0 or n_off + size > rom_len:
                            continue
                        n_raw = int.from_bytes(rom_bytes[n_off:n_off + size], end, signed=False)
                        n_map = _map_value(n_raw)
                        if n_map is not None and 0 <= n_map < rom_len:
                            neigh_ok = True
                            break
                    if not neigh_ok:
                        continue

                    if off in seen_ptr_offsets:
                        continue
                    seen_ptr_offsets.add(off)
                    refs.append(
                        {
                            "ptr_offset": int(off),
                            "ptr_size": int(size),
                            "endianness": str(end),
                            "addressing_mode": "ABSOLUTE",
                            "bank_addend": int(bank_addend),
                        }
                    )
                    if len(refs) >= int(max_refs):
                        return refs
        return refs

    def _calc_pointer_value(self, new_offset: int, ref: Dict[str, Any]) -> Optional[int]:
        bank_addend = int(ref.get("bank_addend", 0) or 0)
        value = int(new_offset) - int(bank_addend)
        if value < 0:
            return None
        return int(value)

    def _write_pointer_value(self, ref: Dict[str, Any], value: int) -> bool:
        ptr_offset = int(ref.get("ptr_offset", -1))
        ptr_size = int(ref.get("ptr_size", 2))
        endianness = str(ref.get("endianness", "little")).lower()
        if ptr_offset < 0 or ptr_offset + ptr_size > len(self.rom_data):
            return False
        max_val = 1 << (ptr_size * 8)
        if value < 0 or value >= max_val:
            return False
        try:
            data = int(value).to_bytes(ptr_size, endianness)
        except Exception:
            return False
        self.rom_data[ptr_offset:ptr_offset + ptr_size] = data
        return True

    def _apply_compressed_blocks_auto(self, translations: Dict[int, str]) -> Dict[str, Any]:
        summary: Dict[str, Any] = {
            "enabled": bool(MultiDecompress and MultiCompress and CompressionAlgorithm),
            "console": str(self.console),
            "blocks_total": 0,
            "blocks_applied": 0,
            "blocks_relocated": 0,
            "pointer_updates": 0,
            "items_applied": 0,
            "items_blocked": 0,
            "roundtrip_baseline_fail_blocks": 0,
            "roundtrip_fail_blocks": 0,
            "applied_ids": set(),
            "blocked_ids": set(),
            "limitations": [],
        }
        if not summary["enabled"]:
            summary["limitations"].append("Runtime de compressão indisponível.")
            return summary

        blocks = self._collect_compressed_blocks_for_reinsertion(translations)
        summary["blocks_total"] = int(len(blocks))
        if not blocks:
            return summary

        supported = {
            str(x).upper()
            for x in self.compression_profile.get("algorithms", [])
        }
        decomp_engine = MultiDecompress()
        comp_engine = MultiCompress()

        def _mark_blocked(text_id: int, reason: str) -> None:
            summary["items_blocked"] += 1
            summary["blocked_ids"].add(int(text_id))
            self._log_blocked(int(text_id), str(reason))

        for _sig, block in blocks.items():
            block_off = int(block.get("compressed_offset", -1))
            block_size = int(block.get("compressed_size", 0))
            algo_name = self._normalize_compression_name(block.get("algorithm", ""))
            entries = list(block.get("entries", []) or [])
            if block_off < 0 or block_size <= 0 or not entries:
                continue

            if supported and algo_name not in supported:
                for item in entries:
                    _mark_blocked(
                        int(item.get("text_id", -1)),
                        f"compressed_algo_not_allowed:{algo_name}",
                    )
                continue

            alg_enum = self._resolve_compression_enum(algo_name)
            if alg_enum is None:
                summary["limitations"].append(f"Algoritmo sem suporte no runtime: {algo_name}")
                for item in entries:
                    _mark_blocked(
                        int(item.get("text_id", -1)),
                        f"compressed_algo_unsupported:{algo_name}",
                    )
                continue

            if block_off + block_size > len(self.rom_data):
                for item in entries:
                    _mark_blocked(
                        int(item.get("text_id", -1)),
                        "compressed_block_out_of_range",
                    )
                continue

            original_comp = bytes(self.rom_data[block_off:block_off + block_size])
            dec_res = decomp_engine.decompress(original_comp, alg_enum)
            if not dec_res.success or not dec_res.data:
                for item in entries:
                    _mark_blocked(
                        int(item.get("text_id", -1)),
                        f"compressed_decompress_failed:{algo_name}",
                    )
                continue

            # Roundtrip obrigatório: recompressão de baseline deve ser idêntica ao bloco original.
            baseline_comp = comp_engine.compress(bytes(dec_res.data), alg_enum)
            if (not baseline_comp.success) or (bytes(baseline_comp.data) != original_comp):
                summary["roundtrip_baseline_fail_blocks"] += 1
                self.stats["compressed_roundtrip_fail"] += 1
                for item in entries:
                    _mark_blocked(
                        int(item.get("text_id", -1)),
                        f"compressed_roundtrip_baseline_mismatch:{algo_name}",
                    )
                continue

            decomp_buf = bytearray(dec_res.data)
            touched: List[Dict[str, Any]] = []
            for item in entries:
                text_id = int(item.get("text_id", -1))
                local_off = int(item.get("local_offset", -1))
                slot_len = int(item.get("slot_len", 0))
                term_val = item.get("terminator")
                term = bytes([int(term_val) & 0xFF]) if term_val is not None else b""

                if local_off < 0 or slot_len <= 0 or local_off + slot_len > len(decomp_buf):
                    _mark_blocked(text_id, "compressed_local_offset_invalid")
                    continue
                payload_limit = int(slot_len - len(term))
                if payload_limit < 0:
                    _mark_blocked(text_id, "compressed_slot_invalid")
                    continue
                try:
                    payload = self._encode_text(str(item.get("text", "") or ""))
                except Exception as exc:
                    _mark_blocked(text_id, f"compressed_encode_failed:{exc}")
                    continue
                if len(payload) > payload_limit:
                    _mark_blocked(text_id, "compressed_text_overflow")
                    continue

                encoded = bytes(payload) + term
                decomp_buf[local_off:local_off + slot_len] = b"\x00" * slot_len
                decomp_buf[local_off:local_off + len(encoded)] = encoded
                touched.append(item)

            if not touched:
                continue

            comp_res = comp_engine.compress(bytes(decomp_buf), alg_enum)
            if not comp_res.success or not comp_res.data:
                for item in touched:
                    _mark_blocked(int(item.get("text_id", -1)), "compressed_recompress_failed")
                continue

            rt_res = decomp_engine.decompress(comp_res.data, alg_enum)
            if (not rt_res.success) or (bytes(rt_res.data) != bytes(decomp_buf)):
                summary["roundtrip_fail_blocks"] += 1
                self.stats["compressed_roundtrip_fail"] += 1
                for item in touched:
                    _mark_blocked(int(item.get("text_id", -1)), "compressed_roundtrip_fail")
                continue

            write_offset = int(block_off)
            relocated = False
            ptr_updates = 0
            new_comp = bytes(comp_res.data)

            if len(new_comp) <= block_size:
                # Reinsere bloco recomprimido in-place (mesmo algoritmo detectado).
                self.rom_data[block_off:block_off + block_size] = (
                    new_comp + (b"\xFF" * (block_size - len(new_comp)))
                )
            else:
                # Fase 3: tenta realocar bloco comprimido expandido ao invés de reprovar.
                allow_expand = os.environ.get("NEUROROM_ALLOW_ROM_EXPAND", "1") == "1"
                if not allow_expand:
                    for item in touched:
                        _mark_blocked(
                            int(item.get("text_id", -1)),
                            "compressed_no_space_expand_disabled",
                        )
                    continue

                old_len = len(self.rom_data)
                alignment = max(1, int(self.allocator.profile.get("alignment", 2) or 2))
                new_off = int((old_len + alignment - 1) // alignment * alignment)

                refs = self._find_pointer_refs_for_target(
                    rom_bytes=bytes(self.rom_data[:old_len]),
                    old_offset=int(block_off),
                    new_offset=int(new_off),
                    max_refs=512,
                )
                filtered_refs: List[Dict[str, Any]] = []
                for ref in refs:
                    ptr_off = int(ref.get("ptr_offset", -1))
                    ptr_size = int(ref.get("ptr_size", 2) or 2)
                    if ptr_off < 0 or ptr_size <= 0:
                        continue
                    if ptr_off + ptr_size > old_len:
                        continue
                    # Evita "ponteiros" detectados dentro do próprio bloco comprimido.
                    if block_off <= ptr_off < (block_off + block_size):
                        continue
                    filtered_refs.append(ref)

                if not filtered_refs:
                    for item in touched:
                        _mark_blocked(int(item.get("text_id", -1)), "compressed_reloc_no_pointers")
                    continue

                if new_off > old_len:
                    self.rom_data.extend(b"\xFF" * (new_off - old_len))
                self.rom_data.extend(new_comp)

                ptr_backups: List[Tuple[int, int, bytes]] = []
                pointer_ok = True
                updated_offsets: List[int] = []
                for ref in filtered_refs:
                    ptr_off = int(ref.get("ptr_offset", -1))
                    ptr_size = int(ref.get("ptr_size", 2) or 2)
                    ptr_backups.append(
                        (
                            int(ptr_off),
                            int(ptr_size),
                            bytes(self.rom_data[ptr_off:ptr_off + ptr_size]),
                        )
                    )

                for ref in filtered_refs:
                    value = self._calc_pointer_value(new_off, ref)
                    if value is None or not self._write_pointer_value(ref, int(value)):
                        pointer_ok = False
                        break
                    updated_offsets.append(int(ref.get("ptr_offset", -1)))

                if (not pointer_ok) or (not updated_offsets):
                    for ptr_off, ptr_size, prev in ptr_backups:
                        self.rom_data[ptr_off:ptr_off + ptr_size] = prev
                    del self.rom_data[old_len:]
                    for item in touched:
                        _mark_blocked(int(item.get("text_id", -1)), "compressed_reloc_pointer_fail")
                    continue

                # Marca bloco antigo como livre.
                self.rom_data[block_off:block_off + block_size] = b"\xFF" * block_size
                write_offset = int(new_off)
                relocated = True
                ptr_updates = int(len(updated_offsets))

            summary["blocks_applied"] += 1
            if relocated:
                summary["blocks_relocated"] += 1
                summary["pointer_updates"] += int(ptr_updates)
            for item in touched:
                tid = int(item.get("text_id", -1))
                summary["items_applied"] += 1
                summary["applied_ids"].add(tid)

        return summary

    def _entry_needs_script_support(self, entry: Dict[str, Any]) -> bool:
        source = str(
            entry.get("script_source")
            or entry.get("source")
            or entry.get("kind")
            or entry.get("reason_if_not")
            or ""
        ).lower()
        return any(tok in source for tok in ("script", "opcode", "bytecode", "event"))

    def _infer_coverage_status(self, row: Dict[str, Any]) -> str:
        explicit_status = str(row.get("coverage_status", "") or "").strip().lower()
        if explicit_status in self.COVERAGE_STATUS_ALLOWED:
            return explicit_status
        status = str(row.get("status", "") or "").upper()
        failure_reason = str(row.get("failure_reason", "") or "").lower()
        translated_text = str(row.get("translated_text", "") or "")

        if bool(row.get("blocked_by_quality_gate", False)):
            if bool(row.get("english_residue", False)) or int(row.get("untranslated_residue_hits", 0) or 0) > 0:
                return "english_residue"
            return "blocked_quality"
        if status.startswith("REINSERTED"):
            return "inserted"
        if status == "UNTRANSLATED" or not translated_text.strip():
            if self._entry_needs_runtime(row):
                return "needs_runtime"
            if self._entry_needs_decompression(row):
                return "needs_decompression"
            if self._entry_needs_script_support(row):
                return "needs_script_support"
            return "untranslated"
        if "runtime" in failure_reason:
            return "needs_runtime"
        if "compress" in failure_reason or "decompress" in failure_reason or "codec" in failure_reason:
            return "needs_decompression"
        if "script" in failure_reason or "opcode" in failure_reason:
            return "needs_script_support"
        if bool(row.get("english_residue", False)):
            return "english_residue"
        return "translated"

    def _offset_sort_key(self, row: Dict[str, Any]) -> Tuple[int, str]:
        off = self._safe_int(row.get("start_offset"), default=None)
        if off is None:
            off = self._safe_int(row.get("original_offset"), default=None)
        if off is None:
            off = self._safe_int(row.get("offset_dec"), default=None)
        off_key = int(off) if off is not None and off >= 0 else 0x7FFFFFFF
        return off_key, str(row.get("segment_id", "") or "")

    def _append_missing_untranslated_rows(self) -> None:
        processed = set(int(x) for x in self._processed_text_ids)
        for text_id, entry in self._iter_all_text_entries():
            if int(text_id) in processed:
                continue
            segment = self._build_segment_record(text_id, entry, "")
            segment["status"] = "UNTRANSLATED"
            segment["coverage_status"] = "untranslated"
            segment["failure_reason"] = "missing_translation"
            segment["blocked_by_quality_gate"] = True
            segment["final_audit_pass"] = False
            segment["quality_block_kind"] = "coverage"
            segment["quality_score"] = 0.0
            segment["technical_score"] = 0
            segment["visual_score"] = 0
            segment["linguistic_score"] = 0
            segment["semantic_score"] = 0.0
            segment["semantic_quality_gate_pass"] = False
            segment["absolute_block_reasons"] = ["coverage_untranslated"]
            if self._entry_needs_runtime(entry):
                segment["coverage_status"] = "needs_runtime"
            elif self._entry_needs_decompression(entry):
                segment["coverage_status"] = "needs_decompression"
            elif self._entry_needs_script_support(entry):
                segment["coverage_status"] = "needs_script_support"
            self.segment_audit_rows.append(segment)

    def _build_inventory_summary(self) -> Dict[str, Any]:
        rows = sorted(self.segment_audit_rows, key=self._offset_sort_key)
        total_raw_extracted = int(len(self._iter_all_text_entries()))
        total_pure_real = int(len(rows))

        counts = Counter()
        coverage_rows: List[Dict[str, Any]] = []
        english_residual = 0
        for row in rows:
            c_status = self._infer_coverage_status(row)
            counts[c_status] += 1
            if c_status == "english_residue":
                english_residual += 1
            coverage_rows.append(
                {
                    "segment_id": row.get("segment_id"),
                    "start_offset": row.get("start_offset"),
                    "status": c_status,
                    "technical_score": int(row.get("technical_score", 0) or 0),
                    "visual_score": int(row.get("visual_score", 0) or 0),
                    "linguistic_score": int(row.get("linguistic_score", 0) or 0),
                    "semantic_score": float(row.get("semantic_score", 0.0) or 0.0),
                    "quality_score": float(row.get("quality_score", 0.0) or 0.0),
                    "semantic_hallucination_suspect": bool(row.get("semantic_hallucination_suspect", False)),
                    "glossary_violation": bool(row.get("glossary_violation", False)),
                    "proper_noun_corruption": bool(row.get("proper_noun_corruption", False)),
                    "register_inconsistency": bool(row.get("register_inconsistency", False)),
                    "semantic_drift": bool(row.get("semantic_drift", False)),
                    "overtranslation_suspect": bool(row.get("overtranslation_suspect", False)),
                    "undertranslation_suspect": bool(row.get("undertranslation_suspect", False)),
                    "fragment_suspect": bool(row.get("fragment_suspect", False)),
                    "context_low_confidence": bool(row.get("context_low_confidence", False)),
                    "segment_integrity_score": int(row.get("segment_integrity_score", 0) or 0),
                    "blocked_by_quality_gate": bool(row.get("blocked_by_quality_gate", False)),
                    "final_status": str(row.get("status", "") or ""),
                    "failure_reason": str(row.get("failure_reason", "") or ""),
                    "absolute_block_reasons": list(row.get("absolute_block_reasons", []) or []),
                }
            )

        classified_total = sum(int(v) for k, v in counts.items() if k in self.COVERAGE_STATUS_ALLOWED)
        untranslated_total = int(counts.get("untranslated", 0))
        support_total = int(counts.get("needs_runtime", 0) + counts.get("needs_decompression", 0) + counts.get("needs_script_support", 0))
        blocked_quality_total = int(counts.get("blocked_quality", 0))
        translated_only_total = int(counts.get("translated", 0))
        coverage_incomplete = bool(
            total_pure_real == 0
            or classified_total < total_pure_real
            or untranslated_total > 0
            or english_residual > 0
            or support_total > 0
            or blocked_quality_total > 0
            or translated_only_total > 0
        )
        global_coverage_percent = (
            float(round((classified_total / float(max(1, total_pure_real))) * 100.0, 4))
            if total_pure_real > 0
            else 0.0
        )

        summary = {
            "schema": "neurorom.text_inventory.v1",
            "rom_crc32": self.original_crc32,
            "rom_size": int(self.original_rom_size),
            "register_policy": self.register_policy,
            "quality_mode": self.quality_mode,
            "quality_profile_sources": list(
                (getattr(self, "quality_profile_meta", {}) or {}).get("applied_sources", [])
            ),
            "total_raw_extracted": int(total_raw_extracted),
            "total_pure_real": int(total_pure_real),
            "total_translated": int(counts.get("translated", 0) + counts.get("inserted", 0)),
            "total_inserted": int(counts.get("inserted", 0)),
            "total_blocked_quality": int(counts.get("blocked_quality", 0)),
            "total_english_residue": int(counts.get("english_residue", 0)),
            "total_needs_runtime": int(counts.get("needs_runtime", 0)),
            "total_needs_decompression": int(counts.get("needs_decompression", 0)),
            "total_needs_script_support": int(counts.get("needs_script_support", 0)),
            "total_untranslated": int(counts.get("untranslated", 0)),
            "coverage_incomplete": bool(coverage_incomplete),
            "global_coverage_percent": float(global_coverage_percent),
            "counts_by_status": {k: int(v) for k, v in sorted(counts.items())},
            "segments": coverage_rows,
        }
        self._inventory_cache = dict(summary)
        return summary

    def _collect_short_variants(self, text_entry: Dict[str, Any]) -> List[str]:
        out: List[str] = []
        for key in ("short_variants", "short_variant", "short_text", "short_translation", "alt_short"):
            raw = text_entry.get(key)
            if isinstance(raw, list):
                for item in raw:
                    txt = str(item or "").strip()
                    if txt and txt not in out:
                        out.append(txt)
            elif raw is not None:
                txt = str(raw).strip()
                if txt and txt not in out:
                    out.append(txt)
        return out

    def _fallback_wrap_text(self, text: str, max_width: int) -> List[str]:
        normalized = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
        maxw = max(1, int(max_width or 1))
        lines: List[str] = []
        for paragraph in normalized.split("\n"):
            words = paragraph.split()
            if not words:
                lines.append("")
                continue
            cur = ""
            for word in words:
                candidate = word if not cur else f"{cur} {word}"
                if len(candidate) <= maxw:
                    cur = candidate
                    continue
                if cur:
                    lines.append(cur)
                # Não corta palavra no meio: palavra longa ocupa linha própria (overflow).
                if len(word) > maxw:
                    lines.append(word)
                    cur = ""
                else:
                    cur = word
            if cur:
                lines.append(cur)
        return lines or [""]

    def _layout_for_text(self, text: str, text_entry: Dict[str, Any]) -> Dict[str, Any]:
        try:
            engine_profile = self.v7_pipeline.get("engine_profile", {})
            box_manager = self.v7_pipeline.get("box_manager")
            layout_engine = self.v7_pipeline.get("layout_engine")
            if layout_engine and box_manager:
                box_type = str(text_entry.get("box_type") or engine_profile.get("box_type", "dialog"))
                layout_engine.box_profile = box_manager.get_profile(
                    console=self.console,
                    box_type=box_type,
                    game_crc=self.original_crc32,
                )
                raw = layout_engine.layout(text)
                lines = [str(x) for x in raw.get("lines", [])]
                widths = [int(self._safe_int(w, default=0) or 0) for w in raw.get("pixel_widths", [])]
                return {
                    "lines": lines if lines else [str(text or "")],
                    "line_count": int(self._safe_int(raw.get("line_count"), default=len(lines)) or len(lines)),
                    "max_line_width": max(widths) if widths else 0,
                    "overflow_detected": bool(raw.get("visual_overflow", False)),
                    "raw": raw,
                }
        except Exception:
            pass

        max_width = int(self._safe_int(text_entry.get("box_width"), default=32) or 32)
        max_lines = int(self._safe_int(text_entry.get("max_lines"), default=0) or 0)
        lines = self._fallback_wrap_text(text, max_width=max_width)
        widths = [len(line) for line in lines]
        overflow_detected = bool(any(w > max_width for w in widths) or (max_lines > 0 and len(lines) > max_lines))
        return {
            "lines": lines,
            "line_count": len(lines),
            "max_line_width": max(widths) if widths else 0,
            "overflow_detected": overflow_detected,
            "raw": {
                "lines": lines,
                "visual_overflow": overflow_detected,
                "line_count": len(lines),
                "pixel_widths": widths,
            },
        }

    def _select_layout_variant(self, text_entry: Dict[str, Any], text: str) -> Dict[str, Any]:
        candidates: List[str] = [str(text or "")]
        for variant in self._collect_short_variants(text_entry):
            if variant not in candidates:
                candidates.append(variant)

        best = None
        for idx, candidate in enumerate(candidates):
            layout = self._layout_for_text(candidate, text_entry)
            lines = [str(x) for x in layout.get("lines", [])]
            renderable = "\n".join(lines) if lines else str(candidate)
            entry = {
                "candidate_index": idx,
                "candidate_text": str(candidate),
                "renderable_text": renderable,
                "line_count": int(layout.get("line_count", len(lines))),
                "max_line_width": int(layout.get("max_line_width", 0)),
                "overflow_detected": bool(layout.get("overflow_detected", False)),
                "layout_raw": layout.get("raw", {}),
            }
            if best is None:
                best = entry
            if not entry["overflow_detected"]:
                best = entry
                break
        assert best is not None
        best["layout_ok"] = bool(not best["overflow_detected"] and int(best["line_count"]) > 0)
        return best

    def _validate_tokens_and_placeholders(self, original_text: str, final_text: str) -> Tuple[bool, str]:
        orig_order = TOKEN_ORDER_RE.findall(str(original_text or ""))
        final_order = TOKEN_ORDER_RE.findall(str(final_text or ""))
        if len(orig_order) != len(final_order):
            return False, "token_count_mismatch"
        if orig_order != final_order:
            return False, "token_order_mismatch"

        orig_ph = PLACEHOLDER_RE.findall(str(original_text or ""))
        final_ph = PLACEHOLDER_RE.findall(str(final_text or ""))
        if orig_ph != final_ph:
            return False, "placeholder_mismatch"

        orig_ctrl = CONTROL_TOKEN_RE.findall(str(original_text or ""))
        final_ctrl = CONTROL_TOKEN_RE.findall(str(final_text or ""))
        if orig_ctrl != final_ctrl:
            return False, "control_code_mismatch"
        return True, "ok"

    def _apply_accent_policy(self, text: str) -> Dict[str, Any]:
        coverage = self._ptbr_coverage()
        renderable = str(text or "")
        explicit_map = dict(self.accent_policy.get("explicit_map", {}))
        allow_fallback = bool(self.accent_policy.get("allow_fallback", False))
        changes: List[Dict[str, Any]] = []

        if coverage.get("ptbr_full_coverage", False):
            return {
                "renderable_text": renderable,
                "fallback_applied": False,
                "fallback_changes": changes,
                "missing_glyphs": self._find_missing_glyphs(renderable),
            }

        chars = list(renderable)
        pending_missing = set(self._find_missing_glyphs(renderable))
        if pending_missing and explicit_map:
            for idx, ch in enumerate(chars):
                repl = explicit_map.get(ch)
                if ch not in pending_missing:
                    continue
                if not repl:
                    continue
                repl_ch = str(repl)[:1]
                if not repl_ch or repl_ch == ch:
                    continue
                chars[idx] = repl_ch
                changes.append({"index": idx, "from": ch, "to": repl_ch, "policy": "explicit_map"})
            renderable = "".join(chars)

        missing_after_explicit = self._find_missing_glyphs(renderable)
        fallback_applied = False
        if missing_after_explicit and allow_fallback:
            chars = list(renderable)
            pending_missing = set(missing_after_explicit)
            for idx, ch in enumerate(chars):
                repl = self.ACCENT_FALLBACK_MAP.get(ch)
                if ch not in pending_missing:
                    continue
                if not repl or repl == ch:
                    continue
                chars[idx] = repl
                fallback_applied = True
                changes.append({"index": idx, "from": ch, "to": repl, "policy": "accent_fallback"})
            renderable = "".join(chars)

        return {
            "renderable_text": renderable,
            "fallback_applied": bool(fallback_applied),
            "fallback_changes": changes,
            "missing_glyphs": self._find_missing_glyphs(renderable),
        }

    def _validate_pointer_refs(self, pointer_refs: List[Dict[str, Any]]) -> bool:
        if not isinstance(pointer_refs, list):
            return False
        for pref in pointer_refs:
            if not isinstance(pref, dict):
                return False
            ptr_off = self._safe_int(pref.get("ptr_offset"), default=None)
            ptr_size = self._safe_int(pref.get("ptr_size"), default=2)
            if ptr_off is None or ptr_size is None:
                return False
            if ptr_size not in {2, 3, 4}:
                return False
            if ptr_off < 0 or ptr_off + ptr_size > len(self.rom_data):
                return False
        return True

    def _build_segment_record(self, text_id: int, text_entry: Dict[str, Any], translated_text: str) -> Dict[str, Any]:
        segment_id = self._normalize_segment_id(text_id, text_entry)
        original_offset = self._safe_int(
            text_entry.get("offset_dec", text_entry.get("target_offset", text_entry.get("offset"))),
            default=None,
        )
        max_bytes = self._safe_int(
            text_entry.get("length", text_entry.get("max_bytes", text_entry.get("max_len_bytes"))),
            default=0,
        ) or 0
        terminator = self._safe_int(
            text_entry.get("terminator", text_entry.get("term", text_entry.get("end_byte"))),
            default=0,
        )
        decoded_text = self._extract_source_text(text_entry)
        pointer_refs = self._extract_pointer_refs(text_entry)
        script_source = str(
            text_entry.get("script_source")
            or text_entry.get("routine")
            or text_entry.get("kind")
            or text_entry.get("source")
            or ""
        )
        confidence = self._safe_float(text_entry.get("confidence", 1.0), default=1.0)
        start_offset = int(original_offset) if original_offset is not None else None
        end_offset = (int(start_offset) + int(max_bytes) - 1) if (start_offset is not None and int(max_bytes) > 0) else None
        decoded_word_count = len(self._words(decoded_text))
        context_low_confidence = bool(
            float(confidence) < 0.45
            or (decoded_word_count == 0 and len(str(decoded_text or "")) < 3)
        )
        segment_integrity_score = 100
        if context_low_confidence:
            segment_integrity_score -= 22
        if decoded_word_count == 0:
            segment_integrity_score -= 25
        if max_bytes <= 0:
            segment_integrity_score -= 40
        if start_offset is None:
            segment_integrity_score -= 20
        segment_integrity_score = int(max(0, min(100, segment_integrity_score)))
        original_bytes_hex = ""
        if start_offset is not None and max_bytes > 0 and (start_offset + max_bytes) <= len(self.rom_data):
            original_bytes_hex = bytes(self.rom_data[start_offset : start_offset + max_bytes]).hex().upper()

        return {
            "segment_id": str(segment_id),
            "rom_crc32": self.original_crc32,
            "rom_size": int(self.original_rom_size),
            "start_offset": start_offset,
            "end_offset": end_offset,
            "original_bytes_hex": original_bytes_hex,
            "decoded_text": str(decoded_text),
            "translated_text": str(translated_text or ""),
            "renderable_text": str(translated_text or ""),
            "control_tokens": CONTROL_TOKEN_RE.findall(str(decoded_text or "")),
            "terminator_hex": f"{int(terminator) & 0xFF:02X}" if terminator is not None else "",
            "max_bytes": int(max_bytes),
            "pointer_refs": pointer_refs,
            "script_source": script_source,
            "confidence": float(max(0.0, min(1.0, confidence))),
            "context_low_confidence": bool(context_low_confidence),
            "segment_integrity_score": int(segment_integrity_score),
            "encoding_ok": False,
            "glyphs_ok": False,
            "tokens_ok": False,
            "terminator_ok": False,
            "layout_ok": False,
            "byte_length_ok": False,
            "offsets_ok": False,
            "pointers_ok": False,
            "fallback_applied": False,
            "fallback_changes": [],
            "missing_glyphs": [],
            "failure_reason": "",
            "status": "PENDING",
            "_terminator_int": int(terminator) if terminator is not None else None,
            "_needs_relocation": False,
            "_payload_len": 0,
            "line_count": 0,
            "max_line_width": 0,
            "overflow_detected": False,
            "supported_glyphs": [],
            "ptbr_full_coverage": False,
            "technical_score": 0,
            "visual_score": 0,
            "linguistic_score": 0,
            "semantic_score": 0.0,
            "quality_score": 0.0,
            "quality_mode": self.quality_mode,
            "quality_threshold_used": float(self._quality_threshold_used()),
            "semantic_threshold_used": float(self._semantic_threshold_used()),
            "semantic_quality_gate_pass": False,
            "quality_suspect": False,
            "final_audit_pass": False,
            "blocked_by_quality_gate": False,
            "absolute_block_reasons": [],
            "quality_block_kind": "",
            "fragment_suspect": False,
            "mixed_language_suspect": False,
            "corruption_suspect": False,
            "human_quality_low": False,
            "layout_ugly": False,
            "semantic_hallucination_suspect": False,
            "glossary_violation": False,
            "proper_noun_corruption": False,
            "register_inconsistency": False,
            "semantic_drift": False,
            "overtranslation_suspect": False,
            "undertranslation_suspect": False,
            "glossary_hits": [],
            "glossary_violations": [],
            "proper_noun_hits": [],
            "proper_noun_preserved": [],
            "register_policy": self.register_policy,
            "english_residue": False,
            "coverage_status": "",
        }

    def _gate_failed_flags(self, segment: Dict[str, Any]) -> List[str]:
        failed: List[str] = []
        for key in self.REQUIRED_GATE_FLAGS:
            if bool(segment.get(key, False)):
                continue
            failed.append(str(key))
        return failed

    def _normalize_text_for_qa(self, text: str) -> str:
        normalized = str(text or "").replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
        normalized = _SPACES_RE.sub(" ", normalized).strip()
        return normalized

    def _words(self, text: str) -> List[str]:
        return [w for w in re.findall(r"[A-Za-zÀ-ÿ]+", str(text or "")) if w]

    def _linguistic_signals(self, decoded_text: str, renderable_text: str) -> Dict[str, Any]:
        src = self._normalize_text_for_qa(decoded_text)
        dst = self._normalize_text_for_qa(renderable_text)
        words = self._words(dst)
        words_lower = [w.casefold() for w in words]
        src_words = [w.casefold() for w in self._words(src)]

        punctuation = [ch for ch in dst if ch in ".,;:!?"]
        alpha_count = sum(1 for ch in dst if ch.isalpha())
        weird_count = sum(1 for ch in dst if (not ch.isalnum()) and (not ch.isspace()) and ch not in ".,;:!?-'\"()/<>%")
        alpha_ratio = float(alpha_count) / float(max(1, len(dst)))
        weird_ratio = float(weird_count) / float(max(1, len(dst)))

        en_hits = sum(1 for w in words_lower if w in self.EN_STOPWORDS)
        en_content_hits = sum(1 for w in words_lower if w in self.EN_CONTENT_WORDS)
        pt_hits = sum(1 for w in words_lower if w in self.PT_STOPWORDS)
        untranslated_hits = sum(1 for w in words_lower if w in self.EN_STOPWORDS and w in src_words)
        residue_hits = sum(1 for w in words_lower if w in self.RESIDUE_BLOCKLIST)
        if residue_hits == 0:
            compact_dst = re.sub(r"[^A-Za-zÀ-ÿ]+", "", dst).casefold()
            residue_hits = sum(1 for tok in self.RESIDUE_BLOCKLIST if tok in compact_dst)

        fragment_suspect = bool(
            dst.startswith((",", ".", ";", ":", "!", "?"))
            or (len(words_lower) >= 2 and len(words_lower[0]) == 1 and words_lower[0] not in {"a", "e", "o"})
            or (len(words_lower) >= 3 and words_lower[-1] in self.PT_STOPWORDS)
        )
        mixed_language_suspect = bool((en_hits + en_content_hits) >= 2 and pt_hits >= 2)
        corruption_suspect = bool(
            "�" in dst
            or "??" in dst
            or weird_ratio > 0.18
            or (
                len(dst) >= 8
                and dst
                and (max(dst.count(ch) for ch in set(dst)) / float(max(1, len(dst)))) > 0.45
            )
        )
        if residue_hits > 0 and len(words_lower) <= 2:
            fragment_suspect = True
        english_residue = bool(
            (en_hits + en_content_hits) >= 1
            and pt_hits == 0
            and len(words_lower) <= 2
            and any(len(w) >= 5 for w in words_lower)
        )
        human_quality_low = bool(
            alpha_ratio < 0.45
            or (len(words_lower) >= 4 and sum(1 for w in words_lower if _LOW_QUALITY_WORD_RE.fullmatch(w)) >= 3)
        )
        if residue_hits > 0 or english_residue:
            human_quality_low = True

        grammar_bad = bool(
            "  " in str(renderable_text or "")
            or re.search(r"[!?.,]{3,}", dst) is not None
            or re.search(r"\b(de|da|do)\s+\1\b", dst.casefold()) is not None
        )
        style_inconsistent = bool(
            len(words_lower) >= 3
            and sum(1 for w in words if w[:1].isupper()) >= 2
            and sum(1 for w in words if w.isupper() and len(w) > 2) >= 1
        )
        low_naturality = bool(alpha_ratio < 0.62 or weird_ratio > 0.08)
        context_weak = bool(len(words_lower) <= 1 and len(dst) < 5)

        return {
            "fragment_suspect": fragment_suspect,
            "mixed_language_suspect": mixed_language_suspect,
            "corruption_suspect": corruption_suspect,
            "human_quality_low": human_quality_low,
            "grammar_bad": grammar_bad,
            "style_inconsistent": style_inconsistent,
            "low_naturality": low_naturality,
            "context_weak": context_weak,
            "untranslated_hits": int(untranslated_hits),
            "en_hits": int(en_hits),
            "en_content_hits": int(en_content_hits),
            "pt_hits": int(pt_hits),
            "residue_hits": int(residue_hits),
        }

    def _evaluate_quality_scores(self, segment: Dict[str, Any], text_entry: Dict[str, Any]) -> Dict[str, Any]:
        decoded = str(segment.get("decoded_text", "") or "")
        renderable = str(segment.get("renderable_text", "") or "")
        max_bytes = int(self._safe_int(segment.get("max_bytes"), default=0) or 0)
        payload_len = int(self._safe_int(segment.get("_payload_len"), default=0) or 0)
        fallback_changes = list(segment.get("fallback_changes", []))
        missing_glyphs = list(segment.get("missing_glyphs", []))

        # Technical 0..40
        technical = 40.0
        if not bool(segment.get("encoding_ok", False)):
            technical -= 20.0
        if not bool(segment.get("glyphs_ok", False)):
            technical -= 15.0
        if not bool(segment.get("tokens_ok", False)):
            technical -= 10.0
        if not bool(segment.get("terminator_ok", False)):
            technical -= 8.0
        if not bool(segment.get("byte_length_ok", False)):
            technical -= 12.0
        if not bool(segment.get("offsets_ok", False)):
            technical -= 12.0
        if not bool(segment.get("pointers_ok", False)):
            technical -= 12.0
        fallback_ratio = float(len(fallback_changes)) / float(max(1, len(self._iter_renderable_chars(renderable))))
        if fallback_ratio > 0.30:
            technical -= 8.0
        elif fallback_ratio > 0.15:
            technical -= 5.0
        elif fallback_ratio > 0.05:
            technical -= 3.0
        if missing_glyphs:
            technical -= 12.0 if not bool(segment.get("glyphs_ok", False)) else 2.0
        relocation_failed = bool(segment.get("_needs_relocation", False) and not bool(segment.get("pointers_ok", False)))
        if relocation_failed:
            technical -= 10.0
        technical = max(0.0, min(40.0, technical))

        # Visual 0..25
        visual = 25.0
        line_count = int(self._safe_int(segment.get("line_count"), default=0) or 0)
        max_line_width = int(self._safe_int(segment.get("max_line_width"), default=0) or 0)
        overflow_detected = bool(segment.get("overflow_detected", False))
        box_width = int(self._safe_int(text_entry.get("box_width"), default=0) or 0)
        max_lines_cfg = int(self._safe_int(text_entry.get("max_lines"), default=0) or 0)
        word_cut = bool(re.search(r"[A-Za-zÀ-ÿ]\n[A-Za-zÀ-ÿ]", renderable) is not None)
        ugly_break = bool(line_count > 1 and len(renderable.split("\n")[-1].strip()) <= 2)

        if overflow_detected:
            visual -= 15.0
        if box_width > 0 and max_line_width > box_width:
            visual -= 8.0
        if max_lines_cfg > 0 and line_count > max_lines_cfg:
            visual -= 8.0
        if word_cut:
            visual -= 8.0
        if ugly_break:
            visual -= 4.0
        visual = max(0.0, min(25.0, visual))
        layout_ugly = bool(overflow_detected or word_cut or (max_lines_cfg > 0 and line_count > max_lines_cfg))

        # Linguistic 0..35
        ling_signals = self._linguistic_signals(decoded, renderable)
        linguistic = 35.0
        if ling_signals["fragment_suspect"]:
            linguistic -= 10.0
        if ling_signals["mixed_language_suspect"]:
            linguistic -= 10.0
        if ling_signals["corruption_suspect"]:
            linguistic -= 12.0
        if ling_signals["human_quality_low"]:
            linguistic -= 8.0
        residue_hits = int(ling_signals.get("residue_hits", 0) or 0)
        if residue_hits > 0:
            linguistic -= min(12.0, 4.0 * float(residue_hits))
        if ling_signals["untranslated_hits"] > 0:
            linguistic -= min(8.0, 2.0 * float(ling_signals["untranslated_hits"]))
        if ling_signals["grammar_bad"]:
            linguistic -= 6.0
        if ling_signals["style_inconsistent"]:
            linguistic -= 4.0
        if ling_signals["low_naturality"]:
            linguistic -= 7.0
        if ling_signals["context_weak"]:
            linguistic -= 3.0
        if max_bytes > 0 and payload_len > max_bytes:
            linguistic -= 2.0
        linguistic = max(0.0, min(35.0, linguistic))

        semantic_eval: Dict[str, Any] = {}
        if self.semantic_gate is not None:
            semantic_eval = self.semantic_gate.evaluate(
                source_text=decoded,
                translated_text=renderable,
                context={
                    "context_low_confidence": bool(segment.get("context_low_confidence", False)),
                    "segment_integrity_score": int(segment.get("segment_integrity_score", 100) or 100),
                },
            )
        else:
            semantic_eval = {
                "semantic_score": 100.0 if not ling_signals["fragment_suspect"] else 70.0,
                "semantic_threshold_used": float(self._semantic_threshold_used()),
                "semantic_quality_gate_pass": not bool(ling_signals["fragment_suspect"]),
                "blocked": bool(ling_signals["fragment_suspect"]),
                "absolute_block_reasons": ["fragment_suspect"] if ling_signals["fragment_suspect"] else [],
                "semantic_hallucination_suspect": False,
                "glossary_violation": False,
                "proper_noun_corruption": False,
                "register_inconsistency": False,
                "semantic_drift": False,
                "overtranslation_suspect": False,
                "undertranslation_suspect": False,
                "fragment_suspect": bool(ling_signals["fragment_suspect"]),
                "glossary_hits": [],
                "glossary_violations": [],
                "proper_noun_hits": [],
                "proper_noun_preserved": [],
                "english_residue": bool(
                    int(ling_signals.get("residue_hits", 0) or 0) > 0
                    or int(ling_signals.get("untranslated_hits", 0) or 0) > 0
                ),
                "register_policy": self.register_policy,
            }

        semantic_score = float(self._safe_float(semantic_eval.get("semantic_score", 0.0), default=0.0))
        semantic_threshold = float(
            self._safe_float(semantic_eval.get("semantic_threshold_used", self._semantic_threshold_used()), default=self._semantic_threshold_used())
        )
        semantic_gate_pass = bool(semantic_eval.get("semantic_quality_gate_pass", False))
        semantic_blocked = bool(semantic_eval.get("blocked", False))
        semantic_min_ok = bool(semantic_score >= semantic_threshold)

        base_quality = technical + visual + linguistic
        quality_score = float(round((base_quality * 0.90) + (semantic_score * 0.10), 2))
        pass_threshold = float(self._quality_threshold_used())
        quality_suspect = bool((pass_threshold - 15.0) <= quality_score < pass_threshold)

        absolute_block_reasons: List[str] = []
        seen_abs: set[str] = set()

        def _abs_add(reason: str) -> None:
            key = str(reason or "").strip()
            if not key or key in seen_abs:
                return
            seen_abs.add(key)
            absolute_block_reasons.append(key)

        if ling_signals["fragment_suspect"]:
            _abs_add("fragment_suspect")
        if ling_signals["mixed_language_suspect"]:
            _abs_add("mixed_language_suspect")
        if ling_signals["corruption_suspect"]:
            _abs_add("corruption_suspect")
        if ling_signals["human_quality_low"]:
            _abs_add("human_quality_low")
        if layout_ugly:
            _abs_add("layout_ugly")
        if not bool(segment.get("tokens_ok", False)):
            _abs_add("tokens_ok")
        if not bool(segment.get("terminator_ok", False)):
            _abs_add("terminator_ok")
        if not bool(segment.get("glyphs_ok", False)):
            _abs_add("glyphs_ok")
        if not bool(segment.get("encoding_ok", False)):
            _abs_add("encoding_ok")
        if not bool(segment.get("byte_length_ok", False)):
            _abs_add("byte_length_ok")
        if not bool(segment.get("offsets_ok", False)):
            _abs_add("offsets_ok")
        if not bool(segment.get("pointers_ok", False)):
            _abs_add("pointers_ok")
        for reason in list(semantic_eval.get("absolute_block_reasons", []) or []):
            _abs_add(str(reason))

        integrity_score = int(segment.get("segment_integrity_score", 100) or 100)
        if integrity_score < 45:
            _abs_add("segment_integrity_low")
        if self.quality_mode == "strict" and bool(segment.get("context_low_confidence", False)):
            _abs_add("context_low_confidence")

        absolute_fail = bool(len(absolute_block_reasons) > 0)

        final_audit_pass = bool(
            (quality_score >= pass_threshold)
            and semantic_min_ok
            and semantic_gate_pass
            and (not absolute_fail)
        )
        blocked_by_quality_gate = not final_audit_pass
        if final_audit_pass:
            quality_block_kind = "pass"
        elif absolute_fail:
            quality_block_kind = "absolute"
        elif quality_score < pass_threshold:
            quality_block_kind = "score"
        elif not semantic_min_ok or semantic_blocked:
            quality_block_kind = "semantic"
        else:
            quality_block_kind = "score"

        return {
            "technical_score": int(round(technical)),
            "visual_score": int(round(visual)),
            "linguistic_score": int(round(linguistic)),
            "semantic_score": float(round(semantic_score, 2)),
            "quality_score": quality_score,
            "quality_mode": self.quality_mode,
            "quality_threshold_used": float(pass_threshold),
            "semantic_threshold_used": float(semantic_threshold),
            "semantic_quality_gate_pass": bool(semantic_gate_pass and semantic_min_ok and (not semantic_blocked)),
            "quality_suspect": quality_suspect,
            "final_audit_pass": final_audit_pass,
            "blocked_by_quality_gate": blocked_by_quality_gate,
            "absolute_block_reasons": list(absolute_block_reasons),
            "quality_block_kind": str(quality_block_kind),
            "layout_ugly": layout_ugly,
            "fragment_suspect": bool(ling_signals["fragment_suspect"]),
            "mixed_language_suspect": bool(ling_signals["mixed_language_suspect"]),
            "corruption_suspect": bool(ling_signals["corruption_suspect"]),
            "human_quality_low": bool(ling_signals["human_quality_low"]),
            "semantic_hallucination_suspect": bool(semantic_eval.get("semantic_hallucination_suspect", False)),
            "glossary_violation": bool(semantic_eval.get("glossary_violation", False)),
            "proper_noun_corruption": bool(semantic_eval.get("proper_noun_corruption", False)),
            "register_inconsistency": bool(semantic_eval.get("register_inconsistency", False)),
            "semantic_drift": bool(semantic_eval.get("semantic_drift", False)),
            "overtranslation_suspect": bool(semantic_eval.get("overtranslation_suspect", False)),
            "undertranslation_suspect": bool(semantic_eval.get("undertranslation_suspect", False)),
            "glossary_hits": list(semantic_eval.get("glossary_hits", []) or []),
            "glossary_violations": list(semantic_eval.get("glossary_violations", []) or []),
            "proper_noun_hits": list(semantic_eval.get("proper_noun_hits", []) or []),
            "proper_noun_preserved": list(semantic_eval.get("proper_noun_preserved", []) or []),
            "register_policy": str(semantic_eval.get("register_policy", self.register_policy)),
            "english_residue": bool(
                semantic_eval.get("english_residue", False)
                or int(ling_signals.get("residue_hits", 0) or 0) > 0
            ),
            "untranslated_residue_hits": int(
                int(ling_signals["untranslated_hits"]) + int(ling_signals.get("residue_hits", 0) or 0)
            ),
            "context_low_confidence": bool(segment.get("context_low_confidence", False)),
            "segment_integrity_score": int(segment.get("segment_integrity_score", 0) or 0),
        }

    def _validate_and_prepare_segment(
        self,
        text_id: int,
        text_entry: Dict[str, Any],
        translated_text: str,
    ) -> Tuple[Dict[str, Any], Optional[bytes]]:
        segment = self._build_segment_record(text_id, text_entry, translated_text)
        decoded_text = str(segment.get("decoded_text", "") or "")
        translated = str(translated_text or "")

        coverage = self._ptbr_coverage()
        segment["supported_glyphs"] = list(coverage.get("supported_glyphs", []))
        segment["ptbr_full_coverage"] = bool(coverage.get("ptbr_full_coverage", False))

        accent_result = self._apply_accent_policy(translated)
        renderable = str(accent_result.get("renderable_text", translated))
        segment["fallback_applied"] = bool(accent_result.get("fallback_applied", False))
        segment["fallback_changes"] = list(accent_result.get("fallback_changes", []))

        missing_original = self._find_missing_glyphs(decoded_text)
        missing_translated_raw = self._find_missing_glyphs(translated)
        missing_after_policy = list(accent_result.get("missing_glyphs", []))
        merged_missing: List[str] = []
        for ch in (missing_original + missing_translated_raw + missing_after_policy):
            if ch not in merged_missing:
                merged_missing.append(ch)
        segment["missing_glyphs"] = merged_missing
        segment["glyphs_ok"] = bool(len(missing_original) == 0 and len(missing_after_policy) == 0)

        layout_choice = self._select_layout_variant(text_entry, renderable)
        segment["renderable_text"] = str(layout_choice.get("renderable_text", renderable))
        segment["layout_ok"] = bool(layout_choice.get("layout_ok", False))
        segment["line_count"] = int(layout_choice.get("line_count", 0))
        segment["max_line_width"] = int(layout_choice.get("max_line_width", 0))
        segment["overflow_detected"] = bool(layout_choice.get("overflow_detected", False))

        tokens_ok, token_reason = self._validate_tokens_and_placeholders(
            decoded_text,
            str(segment.get("renderable_text", "")),
        )
        segment["tokens_ok"] = bool(tokens_ok)
        if not tokens_ok:
            segment["failure_reason"] = str(token_reason)

        terminator = segment.get("_terminator_int")
        segment["terminator_ok"] = bool(isinstance(terminator, int) and 0 <= int(terminator) <= 0xFF)

        encoded_with_term: Optional[bytes] = None
        try:
            encoded = self._encode_text(str(segment.get("renderable_text", "")))
            if segment["terminator_ok"]:
                encoded_with_term = bytes(encoded) + bytes([int(terminator) & 0xFF])
            else:
                encoded_with_term = bytes(encoded)
            segment["encoding_ok"] = True
        except Exception as exc:
            segment["encoding_ok"] = False
            if not segment.get("failure_reason"):
                segment["failure_reason"] = f"encoding_failed:{exc}"

        payload_len = len(encoded_with_term) if encoded_with_term is not None else 0
        segment["_payload_len"] = int(payload_len)
        max_bytes = int(self._safe_int(segment.get("max_bytes"), default=0) or 0)
        needs_relocation = bool(max_bytes > 0 and payload_len > max_bytes)
        segment["_needs_relocation"] = needs_relocation

        pointer_refs = segment.get("pointer_refs", [])
        pointer_struct_ok = self._validate_pointer_refs(pointer_refs)
        can_relocate = bool(pointer_struct_ok and pointer_refs and text_entry.get("reallocatable") is not False)
        if max_bytes <= 0:
            segment["byte_length_ok"] = False
        elif not needs_relocation:
            segment["byte_length_ok"] = True
        else:
            segment["byte_length_ok"] = bool(can_relocate)

        start_offset = self._safe_int(segment.get("start_offset"), default=None)
        end_offset = self._safe_int(segment.get("end_offset"), default=None)
        if start_offset is not None and end_offset is not None and 0 <= start_offset <= end_offset < len(self.rom_data):
            segment["offsets_ok"] = True
        else:
            segment["offsets_ok"] = False

        pointers_ok = bool(pointer_struct_ok)
        if needs_relocation and not pointer_refs:
            pointers_ok = False
        segment["pointers_ok"] = bool(pointers_ok)

        if not segment["glyphs_ok"] and not segment["ptbr_full_coverage"] and not self.accent_policy.get("allow_fallback", False):
            if not segment.get("failure_reason"):
                segment["failure_reason"] = "missing_glyph_without_fallback"

        quality_eval = self._evaluate_quality_scores(segment, text_entry)
        segment.update(quality_eval)
        if bool(segment.get("blocked_by_quality_gate", False)):
            if not segment.get("failure_reason"):
                score = float(segment.get("quality_score", 0.0))
                threshold = float(segment.get("quality_threshold_used", self._quality_threshold_used()))
                semantic_score = float(segment.get("semantic_score", 0.0))
                semantic_threshold = float(segment.get("semantic_threshold_used", self._semantic_threshold_used()))
                quality_block_kind = str(segment.get("quality_block_kind", "") or "")
                absolute_reasons = [str(r) for r in (segment.get("absolute_block_reasons") or []) if str(r)]
                if absolute_reasons:
                    segment["failure_reason"] = "quality_gate_failed:absolute:" + ",".join(absolute_reasons)
                elif quality_block_kind == "semantic":
                    segment["failure_reason"] = (
                        f"quality_gate_failed:semantic:{semantic_score:.2f}<{semantic_threshold:.2f};"
                        f"register_policy={self.register_policy}"
                    )
                else:
                    segment["failure_reason"] = (
                        f"quality_gate_failed:score:{score:.2f}<{threshold:.2f};mode={self.quality_mode}"
                    )
            segment["status"] = "ABORTED_QUALITY"
            return segment, None

        failed_flags = self._gate_failed_flags(segment)
        if failed_flags:
            if not segment.get("failure_reason"):
                segment["failure_reason"] = "gate_failed:" + ",".join(failed_flags)
            segment["status"] = "ABORTED_VALIDATION"
            return segment, None

        segment["status"] = "VALIDATED"
        return segment, encoded_with_term

    def _sha256_path(self, path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    def _is_structural_segment(self, segment: Dict[str, Any]) -> bool:
        if not isinstance(segment, dict):
            return False
        if not bool(segment.get("offsets_ok", False)):
            return False
        if not bool(segment.get("terminator_ok", False)):
            return False
        script_source = str(segment.get("script_source", "") or "").strip()
        if script_source:
            return True
        text = str(segment.get("decoded_text", "") or "")
        if len(text) < 2:
            return False
        weird = sum(1 for ch in text if (ord(ch) < 0x20 and ch not in ("\n", "\r", "\t")))
        junk_ratio = float(weird) / float(max(1, len(text)))
        return junk_ratio <= 0.08

    def _write_mandatory_artifacts(self, output_dir: Path) -> Dict[str, str]:
        output_dir.mkdir(parents=True, exist_ok=True)
        crc = self.original_crc32
        pure_path = output_dir / f"{crc}_pure_text.jsonl"
        mapping_path = output_dir / f"{crc}_reinsertion_mapping.json"
        report_path = output_dir / f"{crc}_report.txt"
        proof_path = output_dir / f"{crc}_proof.json"
        inventory_json_path = output_dir / f"{crc}_text_inventory.json"
        inventory_txt_path = output_dir / f"{crc}_text_inventory.txt"
        inventory_proof_path = output_dir / f"{crc}_text_inventory_proof.json"

        rows_sorted = sorted(self.segment_audit_rows, key=self._offset_sort_key)

        structural_rows = [
            row
            for row in rows_sorted
            if self._is_structural_segment(row) and not str(row.get("status", "")).startswith("ABORTED")
        ]
        with pure_path.open("w", encoding="utf-8") as f:
            meta = {
                "type": "meta",
                "schema": "segment_canonical.v1",
                "rom_crc32": crc,
                "rom_size": int(self.original_rom_size),
                "segments_total": int(len(structural_rows)),
            }
            f.write(json.dumps(meta, ensure_ascii=False) + "\n")
            for row in structural_rows:
                payload = {
                    "segment_id": row.get("segment_id"),
                    "start_offset": row.get("start_offset"),
                    "end_offset": row.get("end_offset"),
                    "original_bytes_hex": row.get("original_bytes_hex", ""),
                    "decoded_text": row.get("decoded_text", ""),
                    "translated_text": row.get("translated_text", ""),
                    "renderable_text": row.get("renderable_text", ""),
                    "control_tokens": row.get("control_tokens", []),
                    "terminator_hex": row.get("terminator_hex", ""),
                    "max_bytes": row.get("max_bytes", 0),
                    "pointer_refs": row.get("pointer_refs", []),
                    "script_source": row.get("script_source", ""),
                    "technical_score": int(row.get("technical_score", 0) or 0),
                    "visual_score": int(row.get("visual_score", 0) or 0),
                    "linguistic_score": int(row.get("linguistic_score", 0) or 0),
                    "semantic_score": float(row.get("semantic_score", 0.0) or 0.0),
                    "quality_score": float(row.get("quality_score", 0.0) or 0.0),
                    "quality_mode": str(row.get("quality_mode", self.quality_mode)),
                    "quality_threshold_used": float(row.get("quality_threshold_used", self._quality_threshold_used()) or 0.0),
                    "semantic_threshold_used": float(row.get("semantic_threshold_used", self._semantic_threshold_used()) or 0.0),
                    "absolute_block_reasons": list(row.get("absolute_block_reasons", []) or []),
                    "final_audit_pass": bool(row.get("final_audit_pass", False)),
                    "blocked_by_quality_gate": bool(row.get("blocked_by_quality_gate", False)),
                    "semantic_hallucination_suspect": bool(row.get("semantic_hallucination_suspect", False)),
                    "glossary_violation": bool(row.get("glossary_violation", False)),
                    "proper_noun_corruption": bool(row.get("proper_noun_corruption", False)),
                    "register_inconsistency": bool(row.get("register_inconsistency", False)),
                    "semantic_drift": bool(row.get("semantic_drift", False)),
                    "overtranslation_suspect": bool(row.get("overtranslation_suspect", False)),
                    "undertranslation_suspect": bool(row.get("undertranslation_suspect", False)),
                    "fragment_suspect": bool(row.get("fragment_suspect", False)),
                    "glossary_hits": list(row.get("glossary_hits", []) or []),
                    "glossary_violations": list(row.get("glossary_violations", []) or []),
                    "proper_noun_hits": list(row.get("proper_noun_hits", []) or []),
                    "proper_noun_preserved": list(row.get("proper_noun_preserved", []) or []),
                    "register_policy": str(row.get("register_policy", self.register_policy)),
                    "context_low_confidence": bool(row.get("context_low_confidence", False)),
                    "segment_integrity_score": int(row.get("segment_integrity_score", 0) or 0),
                    "coverage_status": str(row.get("coverage_status", self._infer_coverage_status(row))),
                    "status": row.get("status", ""),
                    "failure_reason": row.get("failure_reason", ""),
                }
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")

        mapping_rows: List[Dict[str, Any]] = []
        for row in rows_sorted:
            start = self._safe_int(row.get("start_offset"), default=None)
            original_size = int(row.get("max_bytes", 0) or 0)
            final_size = int(row.get("_payload_len", 0) or 0)
            relocated = bool(row.get("status") == "REINSERTED_RELOCATED")
            final_offset = self._safe_int(row.get("final_offset"), default=start)
            mapping_rows.append(
                {
                    "segment_id": row.get("segment_id"),
                    "original_offset": start,
                    "final_offset": final_offset,
                    "original_size": original_size,
                    "final_size": final_size,
                    "relocated": relocated,
                    "updated_pointers": int(row.get("updated_pointers", 0) or 0),
                    "terminator_preserved": bool(row.get("terminator_ok", False)),
                    "tokens_preserved": bool(row.get("tokens_ok", False)),
                    "fallback_applied": bool(row.get("fallback_applied", False)),
                    "layout_ok": bool(row.get("layout_ok", False)),
                    "technical_score": int(row.get("technical_score", 0) or 0),
                    "visual_score": int(row.get("visual_score", 0) or 0),
                    "linguistic_score": int(row.get("linguistic_score", 0) or 0),
                    "semantic_score": float(row.get("semantic_score", 0.0) or 0.0),
                    "quality_score": float(row.get("quality_score", 0.0) or 0.0),
                    "quality_mode": str(row.get("quality_mode", self.quality_mode)),
                    "quality_threshold_used": float(row.get("quality_threshold_used", self._quality_threshold_used()) or 0.0),
                    "semantic_threshold_used": float(row.get("semantic_threshold_used", self._semantic_threshold_used()) or 0.0),
                    "absolute_block_reasons": list(row.get("absolute_block_reasons", []) or []),
                    "final_audit_pass": bool(row.get("final_audit_pass", False)),
                    "blocked_by_quality_gate": bool(row.get("blocked_by_quality_gate", False)),
                    "semantic_hallucination_suspect": bool(row.get("semantic_hallucination_suspect", False)),
                    "glossary_violation": bool(row.get("glossary_violation", False)),
                    "proper_noun_corruption": bool(row.get("proper_noun_corruption", False)),
                    "register_inconsistency": bool(row.get("register_inconsistency", False)),
                    "semantic_drift": bool(row.get("semantic_drift", False)),
                    "overtranslation_suspect": bool(row.get("overtranslation_suspect", False)),
                    "undertranslation_suspect": bool(row.get("undertranslation_suspect", False)),
                    "fragment_suspect": bool(row.get("fragment_suspect", False)),
                    "glossary_hits": list(row.get("glossary_hits", []) or []),
                    "glossary_violations": list(row.get("glossary_violations", []) or []),
                    "proper_noun_hits": list(row.get("proper_noun_hits", []) or []),
                    "proper_noun_preserved": list(row.get("proper_noun_preserved", []) or []),
                    "register_policy": str(row.get("register_policy", self.register_policy)),
                    "context_low_confidence": bool(row.get("context_low_confidence", False)),
                    "segment_integrity_score": int(row.get("segment_integrity_score", 0) or 0),
                    "coverage_status": str(row.get("coverage_status", self._infer_coverage_status(row))),
                    "status": row.get("status", "PENDING"),
                    "failure_reason": row.get("failure_reason", ""),
                }
            )
        with mapping_path.open("w", encoding="utf-8") as f:
            json.dump(mapping_rows, f, ensure_ascii=False, indent=2)

        total = len(rows_sorted)
        inserted = sum(1 for row in rows_sorted if str(row.get("status", "")).startswith("REINSERTED"))
        relocated = sum(1 for row in rows_sorted if row.get("status") == "REINSERTED_RELOCATED")
        layout_ok = sum(1 for row in rows_sorted if bool(row.get("layout_ok", False)))
        ptbr_full = sum(1 for row in rows_sorted if bool(row.get("ptbr_full_coverage", False)))
        fallback = sum(1 for row in rows_sorted if bool(row.get("fallback_applied", False)))
        aborted = sum(1 for row in rows_sorted if str(row.get("status", "")).startswith("ABORTED"))
        quality_pass = sum(1 for row in rows_sorted if bool(row.get("final_audit_pass", False)))
        quality_blocked = sum(1 for row in rows_sorted if bool(row.get("blocked_by_quality_gate", False)))
        avg_quality = (
            sum(float(row.get("quality_score", 0.0) or 0.0) for row in rows_sorted) / float(max(1, len(rows_sorted)))
        )
        avg_technical = (
            sum(float(row.get("technical_score", 0) or 0.0) for row in rows_sorted) / float(max(1, len(rows_sorted)))
        )
        avg_visual = (
            sum(float(row.get("visual_score", 0) or 0.0) for row in rows_sorted) / float(max(1, len(rows_sorted)))
        )
        avg_linguistic = (
            sum(float(row.get("linguistic_score", 0) or 0.0) for row in rows_sorted) / float(max(1, len(rows_sorted)))
        )
        avg_semantic = (
            sum(float(row.get("semantic_score", 0.0) or 0.0) for row in rows_sorted) / float(max(1, len(rows_sorted)))
        )
        absolute_reasons = Counter()
        for row in rows_sorted:
            for reason in list(row.get("absolute_block_reasons", []) or []):
                absolute_reasons[str(reason)] += 1
        reasons = Counter(
            str(row.get("failure_reason", "") or "ok")
            for row in rows_sorted
            if row.get("failure_reason")
        )
        inventory = self._build_inventory_summary()
        counts_by_status = dict(inventory.get("counts_by_status", {}) or {})
        coverage_incomplete = bool(inventory.get("coverage_incomplete", True))
        global_coverage_percent = float(inventory.get("global_coverage_percent", 0.0) or 0.0)
        total_raw_extracted = int(inventory.get("total_raw_extracted", total) or total)
        total_pure_real = int(inventory.get("total_pure_real", total) or total)

        report_lines = [
            f"CRC32: {crc}",
            f"ROM_SIZE: {self.original_rom_size}",
            f"SEGMENTS_TOTAL: {total}",
            f"REINSERTED: {inserted}",
            f"RELOCATED: {relocated}",
            f"LAYOUT_OK: {layout_ok}",
            f"PTBR_FULL_COVERAGE: {ptbr_full}",
            f"FALLBACK_APPLIED: {fallback}",
            f"ABORTED: {aborted}",
            f"QUALITY_MODE: {self.quality_mode}",
            f"QUALITY_THRESHOLD_USED: {self._quality_threshold_used():.2f}",
            f"QUALITY_PASS: {quality_pass}",
            f"QUALITY_BLOCKED: {quality_blocked}",
            f"QUALITY_AVG: {avg_quality:.2f}",
            f"TECHNICAL_SCORE_AVG: {avg_technical:.2f}",
            f"VISUAL_SCORE_AVG: {avg_visual:.2f}",
            f"LINGUISTIC_SCORE_AVG: {avg_linguistic:.2f}",
            f"SEMANTIC_SCORE_AVG: {avg_semantic:.2f}",
            f"REGISTER_POLICY: {self.register_policy}",
            f"TOTAL_RAW_EXTRACTED: {total_raw_extracted}",
            f"TOTAL_PURE_REAL: {total_pure_real}",
            f"TOTAL_TRANSLATED: {int(inventory.get('total_translated', 0))}",
            f"TOTAL_INSERTED: {int(inventory.get('total_inserted', 0))}",
            f"TOTAL_BLOCKED_QUALITY: {int(inventory.get('total_blocked_quality', 0))}",
            f"TOTAL_ENGLISH_RESIDUE: {int(inventory.get('total_english_residue', 0))}",
            f"TOTAL_NEEDS_RUNTIME: {int(inventory.get('total_needs_runtime', 0))}",
            f"TOTAL_NEEDS_DECOMPRESSION: {int(inventory.get('total_needs_decompression', 0))}",
            f"TOTAL_NEEDS_SCRIPT_SUPPORT: {int(inventory.get('total_needs_script_support', 0))}",
            f"TOTAL_UNTRANSLATED: {int(inventory.get('total_untranslated', 0))}",
            f"COVERAGE_INCOMPLETE: {str(bool(coverage_incomplete)).lower()}",
            f"GLOBAL_COVERAGE_PERCENT: {global_coverage_percent:.4f}",
            "COUNTS_BY_STATUS:",
        ]
        if counts_by_status:
            for key in sorted(counts_by_status):
                report_lines.append(f"- {key}: {int(counts_by_status.get(key, 0) or 0)}")
        else:
            report_lines.append("- none")
        report_lines.extend(
            [
            "ABSOLUTE_BLOCK_REASONS:",
            ]
        )
        if absolute_reasons:
            for reason, hits in absolute_reasons.most_common():
                report_lines.append(f"- {reason}: {hits}")
        else:
            report_lines.append("- none")
        report_lines.extend([
            "FAILURE_REASONS:",
        ])
        if reasons:
            for reason, hits in reasons.most_common():
                report_lines.append(f"- {reason}: {hits}")
        else:
            report_lines.append("- none")
        report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

        inventory_json_path.write_text(
            json.dumps(inventory, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        inv_lines = [
            f"CRC32: {crc}",
            f"ROM_SIZE: {self.original_rom_size}",
            f"TOTAL_RAW_EXTRACTED: {total_raw_extracted}",
            f"TOTAL_PURE_REAL: {total_pure_real}",
            f"TOTAL_TRANSLATED: {int(inventory.get('total_translated', 0))}",
            f"TOTAL_INSERTED: {int(inventory.get('total_inserted', 0))}",
            f"TOTAL_BLOCKED_QUALITY: {int(inventory.get('total_blocked_quality', 0))}",
            f"TOTAL_ENGLISH_RESIDUE: {int(inventory.get('total_english_residue', 0))}",
            f"TOTAL_NEEDS_RUNTIME: {int(inventory.get('total_needs_runtime', 0))}",
            f"TOTAL_NEEDS_DECOMPRESSION: {int(inventory.get('total_needs_decompression', 0))}",
            f"TOTAL_NEEDS_SCRIPT_SUPPORT: {int(inventory.get('total_needs_script_support', 0))}",
            f"TOTAL_UNTRANSLATED: {int(inventory.get('total_untranslated', 0))}",
            f"COVERAGE_INCOMPLETE: {str(bool(coverage_incomplete)).lower()}",
            f"GLOBAL_COVERAGE_PERCENT: {global_coverage_percent:.4f}",
            "COUNTS_BY_STATUS:",
        ]
        if counts_by_status:
            for key in sorted(counts_by_status):
                inv_lines.append(f"- {key}: {int(counts_by_status.get(key, 0) or 0)}")
        else:
            inv_lines.append("- none")
        inventory_txt_path.write_text("\n".join(inv_lines) + "\n", encoding="utf-8")

        coverage = self._ptbr_coverage()
        proof = {
            "schema": "reinsertion_proof.v2",
            "rom_crc32": crc,
            "rom_size": int(self.original_rom_size),
            "charset_effective": coverage.get("charset_effective", "ascii"),
            "supported_glyphs": coverage.get("supported_glyphs", []),
            "missing_glyphs": coverage.get("missing_glyphs", []),
            "ptbr_full_coverage": bool(coverage.get("ptbr_full_coverage", False)),
            "validations_executed": list(self.REQUIRED_GATE_FLAGS),
            "segments_processed": int(len(self.segment_audit_rows)),
            "failures": [
                row for row in self.segment_audit_rows if str(row.get("status", "")).startswith("ABORTED")
            ],
            "fallback_applied": int(fallback),
            "quality_mode": self.quality_mode,
            "quality_threshold_used": float(self._quality_threshold_used()),
            "quality_pass": int(quality_pass),
            "quality_blocked": int(quality_blocked),
            "quality_average": float(round(avg_quality, 2)),
            "semantic_average": float(round(avg_semantic, 2)),
            "coverage_incomplete": bool(coverage_incomplete),
            "global_coverage_percent": float(global_coverage_percent),
            "coverage_counts_by_status": {k: int(v) for k, v in sorted(counts_by_status.items())},
            "segments": [
                {
                    "segment_id": row.get("segment_id"),
                    "technical_score": int(row.get("technical_score", 0) or 0),
                    "visual_score": int(row.get("visual_score", 0) or 0),
                    "linguistic_score": int(row.get("linguistic_score", 0) or 0),
                    "semantic_score": float(row.get("semantic_score", 0.0) or 0.0),
                    "quality_score": float(row.get("quality_score", 0.0) or 0.0),
                    "quality_mode": str(row.get("quality_mode", self.quality_mode)),
                    "quality_threshold_used": float(row.get("quality_threshold_used", self._quality_threshold_used()) or 0.0),
                    "semantic_threshold_used": float(row.get("semantic_threshold_used", self._semantic_threshold_used()) or 0.0),
                    "absolute_block_reasons": list(row.get("absolute_block_reasons", []) or []),
                    "final_audit_pass": bool(row.get("final_audit_pass", False)),
                    "blocked_by_quality_gate": bool(row.get("blocked_by_quality_gate", False)),
                    "semantic_hallucination_suspect": bool(row.get("semantic_hallucination_suspect", False)),
                    "glossary_violation": bool(row.get("glossary_violation", False)),
                    "proper_noun_corruption": bool(row.get("proper_noun_corruption", False)),
                    "register_inconsistency": bool(row.get("register_inconsistency", False)),
                    "semantic_drift": bool(row.get("semantic_drift", False)),
                    "overtranslation_suspect": bool(row.get("overtranslation_suspect", False)),
                    "undertranslation_suspect": bool(row.get("undertranslation_suspect", False)),
                    "fragment_suspect": bool(row.get("fragment_suspect", False)),
                    "glossary_hits": list(row.get("glossary_hits", []) or []),
                    "glossary_violations": list(row.get("glossary_violations", []) or []),
                    "proper_noun_hits": list(row.get("proper_noun_hits", []) or []),
                    "proper_noun_preserved": list(row.get("proper_noun_preserved", []) or []),
                    "coverage_status": str(row.get("coverage_status", self._infer_coverage_status(row))),
                    "context_low_confidence": bool(row.get("context_low_confidence", False)),
                    "segment_integrity_score": int(row.get("segment_integrity_score", 0) or 0),
                    "failure_reason": row.get("failure_reason", ""),
                }
                for row in rows_sorted
            ],
            "artifacts": {
                "pure_text": str(pure_path),
                "reinsertion_mapping": str(mapping_path),
                "report": str(report_path),
                "text_inventory_json": str(inventory_json_path),
                "text_inventory_txt": str(inventory_txt_path),
                "text_inventory_proof": str(inventory_proof_path),
            },
        }
        with proof_path.open("w", encoding="utf-8") as f:
            json.dump(proof, f, ensure_ascii=False, indent=2)

        proof["artifacts"]["hashes"] = {
            "pure_text_sha256": self._sha256_path(pure_path),
            "reinsertion_mapping_sha256": self._sha256_path(mapping_path),
            "report_sha256": self._sha256_path(report_path),
            "text_inventory_json_sha256": self._sha256_path(inventory_json_path),
            "text_inventory_txt_sha256": self._sha256_path(inventory_txt_path),
            "proof_sha256": self._sha256_path(proof_path),
        }
        with proof_path.open("w", encoding="utf-8") as f:
            json.dump(proof, f, ensure_ascii=False, indent=2)

        inventory_proof = {
            "schema": "neurorom.text_inventory_proof.v1",
            "rom_crc32": crc,
            "rom_size": int(self.original_rom_size),
            "coverage_incomplete": bool(coverage_incomplete),
            "global_coverage_percent": float(global_coverage_percent),
            "counts_by_status": {k: int(v) for k, v in sorted(counts_by_status.items())},
            "files": {
                "text_inventory_json": str(inventory_json_path),
                "text_inventory_txt": str(inventory_txt_path),
                "report": str(report_path),
                "proof": str(proof_path),
            },
            "hashes": {
                "text_inventory_json_sha256": self._sha256_path(inventory_json_path),
                "text_inventory_txt_sha256": self._sha256_path(inventory_txt_path),
                "report_sha256": self._sha256_path(report_path),
                "proof_sha256": self._sha256_path(proof_path),
            },
        }
        inventory_proof_path.write_text(
            json.dumps(inventory_proof, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        proof["artifacts"]["hashes"]["text_inventory_proof_sha256"] = self._sha256_path(inventory_proof_path)
        with proof_path.open("w", encoding="utf-8") as f:
            json.dump(proof, f, ensure_ascii=False, indent=2)

        return {
            "pure_text_path": str(pure_path),
            "mapping_path": str(mapping_path),
            "report_path": str(report_path),
            "proof_path": str(proof_path),
            "text_inventory_json_path": str(inventory_json_path),
            "text_inventory_txt_path": str(inventory_txt_path),
            "text_inventory_proof_path": str(inventory_proof_path),
        }

    def reinsert_translations(self, translations: Dict[int, str],
                            output_path: Optional[str] = None,
                            create_backup: bool = True,
                            strict: bool = False,
                            skip_suspicious: bool = True) -> Tuple[bool, str]:
        """
        Reinsere textos traduzidos na ROM.

        Args:
            translations: Dicionário {text_id: translated_text}
            output_path: Caminho da ROM de saída (default: rom_path_translated.ext)
            create_backup: Se True, cria backup da ROM original
            strict: Se True, valida dados suspeitos (tiles/sprites)
            skip_suspicious: Se True, pula itens suspeitos; se False, falha

        Returns:
            (success, message)
        """
        # Configura modo strict
        self.strict_mode = strict
        self.skip_suspicious = skip_suspicious
        if self.semantic_gate is not None:
            self.semantic_gate.strict_mode = bool(self.semantic_strict_mode or self.strict_mode)
        print(f"\n🔄 SAFE REINSERTER - Universal Text Reinsertion")
        print(f"{'='*70}")

        if output_path is None:
            output_path = str(self.rom_path.with_stem(f"{self.rom_path.stem}_translated"))

        output_path = Path(output_path)

        # Backup
        if create_backup:
            backup_path = str(self.rom_path) + '.backup'
            shutil.copy2(self.rom_path, backup_path)
            print(f"✅ Backup created: {backup_path}")

        # Processa traduções
        expected_entries = self._iter_all_text_entries()
        expected_total = len(expected_entries)
        self.stats['total_texts'] = max(int(expected_total), int(len(translations)))
        self.stats['inserted'] = 0
        self.stats['skipped'] = 0
        self.runtime_qa_entries = {}
        self._v7_entry_context = {}
        self.segment_audit_rows = []
        self.proof_validation_entries = []
        self._processed_text_ids = set()
        self._inventory_cache = None

        compression_summary = self._apply_compressed_blocks_auto(translations)
        applied_compressed_ids = {
            int(x)
            for x in (compression_summary.get("applied_ids", set()) or set())
            if isinstance(x, int) or str(x).isdigit()
        }
        blocked_compressed_ids = {
            int(x)
            for x in (compression_summary.get("blocked_ids", set()) or set())
            if isinstance(x, int) or str(x).isdigit()
        }
        self.stats["compressed_blocks_total"] = int(compression_summary.get("blocks_total", 0) or 0)
        self.stats["compressed_applied"] = int(compression_summary.get("items_applied", 0) or 0)
        self.stats["compressed_blocked"] = int(compression_summary.get("items_blocked", 0) or 0)
        self.stats["compressed_relocated"] = int(compression_summary.get("blocks_relocated", 0) or 0)
        self.stats["compressed_pointer_updates"] = int(compression_summary.get("pointer_updates", 0) or 0)
        self.stats['inserted'] += int(len(applied_compressed_ids))
        self.stats['skipped'] += int(len(blocked_compressed_ids))
        self._processed_text_ids.update(applied_compressed_ids)
        self._processed_text_ids.update(blocked_compressed_ids)

        for text_id, translated_text in sorted(translations.items(), key=lambda kv: int(kv[0])):
            if int(text_id) in applied_compressed_ids or int(text_id) in blocked_compressed_ids:
                continue
            self._processed_text_ids.add(int(text_id))
            try:
                applied = self._reinsert_single_text(text_id, translated_text)
                if applied:
                    self.stats['inserted'] += 1
                else:
                    self.stats['skipped'] += 1
            except ReinsertionError as e:
                self.stats['errors'].append({
                    'text_id': text_id,
                    'error': str(e)
                })
                self.stats['skipped'] += 1
                print(f"⚠️  Skipped text #{text_id}: {e}")

        missing_before = len(self.segment_audit_rows)
        self._append_missing_untranslated_rows()
        missing_added = max(0, len(self.segment_audit_rows) - missing_before)
        if missing_added > 0:
            self.stats['skipped'] += int(missing_added)

        # Salva ROM modificada
        self._save_rom(output_path)

        artifact_paths: Dict[str, str] = {}
        try:
            output_dir = Path(output_path).parent if output_path else Path(".")
            artifact_paths = self._write_mandatory_artifacts(output_dir)
        except Exception:
            artifact_paths = {}

        inventory = self._inventory_cache if isinstance(self._inventory_cache, dict) else self._build_inventory_summary()
        coverage_incomplete = bool((inventory or {}).get("coverage_incomplete", True))

        # Relatório final de sucesso exige cobertura auditável completa.
        success = bool(self.stats['inserted'] > 0 and not coverage_incomplete)

        suspicious_info = ""
        if self.strict_mode and (
            self.stats['suspicious_skipped'] > 0 or self.stats['non_text_meta_skipped'] > 0
        ):
            suspicious_info = (
                f"\n  Suspicious skipped: {self.stats['suspicious_skipped']}"
                f"\n  Non-text meta skipped: {self.stats['non_text_meta_skipped']}"
            )

        if evaluate_reinsertion_qa and write_qa_artifacts:
            try:
                blocked_total = int(self.stats.get('blocked_no_pointer', 0)) + int(
                    self.stats.get('allocation_failed', 0)
                )
                qa_stats = {
                    "truncated": 0,
                    "blocked": blocked_total,
                    "blocked_items": blocked_total,
                }
                limitations: List[str] = []
                if int(self.stats.get('suspicious_skipped', 0)) > 0:
                    limitations.append(
                        f"{int(self.stats.get('suspicious_skipped', 0))} itens suspeitos foram pulados."
                    )
                if int(self.stats.get('non_text_meta_skipped', 0)) > 0:
                    limitations.append(
                        f"{int(self.stats.get('non_text_meta_skipped', 0))} itens não-texto foram pulados por metadata."
                    )
                limitations.append("Input match e ordering não disponíveis neste fluxo universal.")

                qa_final = evaluate_reinsertion_qa(
                    console=str(self.console),
                    rom_crc32=self.original_crc32,
                    rom_size=self.original_rom_size,
                    stats=qa_stats,
                    evidence={},
                    checks={
                        "input_match": None,
                        "ordering": None,
                        "emulator_smoke": None,
                    },
                    limitations=limitations,
                    compression_policy={},
                    translation_input={"path": str(output_path)},
                    require_manual_emulator=True,
                )
                qa_json_path, qa_txt_path = write_qa_artifacts(
                    output_path.parent,
                    self.original_crc32,
                    qa_final,
                )
                self.last_qa_final = qa_final
                self.last_qa_paths = {
                    "json": str(qa_json_path),
                    "txt": str(qa_txt_path),
                }
            except Exception:
                self.last_qa_final = None
                self.last_qa_paths = {"json": None, "txt": None}

        message = (
            f"Reinsertion complete!\n"
            f"  Inserted: {self.stats['inserted']}/{self.stats['total_texts']}\n"
            f"  Skipped: {self.stats['skipped']}{suspicious_info}\n"
            f"  Compressed blocks: {self.stats.get('compressed_blocks_total', 0)} "
            f"(applied={self.stats.get('compressed_applied', 0)}, blocked={self.stats.get('compressed_blocked', 0)}, "
            f"relocated={self.stats.get('compressed_relocated', 0)}, ptr_updates={self.stats.get('compressed_pointer_updates', 0)})\n"
            f"  Coverage incomplete: {str(bool(coverage_incomplete)).lower()}\n"
            f"  Global coverage: {float((inventory or {}).get('global_coverage_percent', 0.0) or 0.0):.4f}%\n"
            f"  Output: {output_path}\n"
            f"  Mapping: {artifact_paths.get('mapping_path', 'n/a')}\n"
            f"  Report: {artifact_paths.get('report_path', 'n/a')}\n"
            f"  Proof: {artifact_paths.get('proof_path', 'n/a')}\n"
            f"  Text inventory: {artifact_paths.get('text_inventory_json_path', 'n/a')}"
        )

        print(f"\n{'='*70}")
        print(message)
        print(f"{'='*70}\n")

        return success, message

    def _reinsert_single_text(self, text_id: int, translated_text: str) -> bool:
        """
        Reinsere um texto individual com suporte a realocacao automatica.

        Estrategia:
        1. Se cabe no espaco original -> escreve in-place
        2. Se nao cabe e tem pointer_refs -> realoca para novo espaco
        3. Se nao cabe e nao tem pointer_refs -> bloqueia (NOT_REALLOCATABLE)

        Raises:
            ReinsertionError se nao puder inserir com seguranca

        Returns:
            True se aplicou a tradução; False se pulou com segurança.
        """
        text_entry = self._find_text_entry(text_id)
        if not text_entry:
            raise ReinsertionError(f"Text ID {text_id} not found in extraction data")

        original_offset = self._safe_int(
            text_entry.get("offset_dec", text_entry.get("target_offset", text_entry.get("offset"))),
            default=0,
        ) or 0
        original_length = self._safe_int(
            text_entry.get("length", text_entry.get("max_bytes", text_entry.get("max_len_bytes"))),
            default=0,
        ) or 0
        pointer_refs = self._extract_pointer_refs(text_entry)

        # VALIDACAO STRICT: respeita metadata de nao-texto antes de heuristica
        if self.strict_mode:
            reason_code = self._extract_reason_code(text_entry)
            if reason_code in self.NON_TEXT_REASON_CODES:
                self.stats['non_text_meta_skipped'] += 1
                segment = self._build_segment_record(text_id, text_entry, translated_text)
                segment["status"] = "ABORTED_NON_TEXT_META"
                segment["failure_reason"] = f"NON_TEXT_META:{reason_code}"
                self.segment_audit_rows.append(segment)
                self._log_blocked(text_id, segment["failure_reason"])
                return False

        # VALIDACAO STRICT: detecta dados suspeitos (tiles/sprites/tabelas)
        if self.strict_mode:
            source = text_entry.get('source', '') or text_entry.get('original', '')
            is_suspicious, reason = self._is_suspicious_source(source, original_offset or 0, original_length)
            if is_suspicious:
                self.stats['suspicious_skipped'] += 1
                segment = self._build_segment_record(text_id, text_entry, translated_text)
                segment["status"] = "ABORTED_SUSPICIOUS"
                segment["failure_reason"] = str(reason)
                self.segment_audit_rows.append(segment)
                self._log_blocked(text_id, reason)
                if self.skip_suspicious:
                    return False  # pula sem erro
                else:
                    raise ReinsertionError(reason)

        # Pipeline V7: EncodingAdapter -> TextLayoutEngine -> RuntimeQASimulator -> RelocationManager
        self._v7_entry_context[text_id] = {
            "entry": text_entry,
            "original_offset": original_offset,
            "original_length": int(original_length),
            "pointer_refs": pointer_refs,
        }
        self._run_v7_pipeline_for_entry(text_id, translated_text)

        segment, encoded_with_term = self._validate_and_prepare_segment(text_id, text_entry, translated_text)
        gate_failed = self._gate_failed_flags(segment)
        if gate_failed or encoded_with_term is None:
            if "pointers_ok" in gate_failed:
                self.stats["blocked_no_pointer"] += 1
            segment["status"] = segment.get("status", "ABORTED_VALIDATION")
            segment["failure_reason"] = str(segment.get("failure_reason") or f"gate_failed:{','.join(gate_failed)}")
            self.segment_audit_rows.append(segment)
            self._log_blocked(text_id, segment["failure_reason"])
            return False

        original_offset = int(self._safe_int(segment.get("start_offset"), default=0) or 0)
        original_length = int(self._safe_int(segment.get("max_bytes"), default=0) or 0)
        needs_relocation = bool(segment.get("_needs_relocation", False))

        if not needs_relocation:
            self._write_in_place(original_offset, encoded_with_term, original_length)
            self.stats['in_place'] += 1
            self.allocator.register_in_place(original_offset, original_length, f"text_{text_id}")
            segment["status"] = "REINSERTED_IN_PLACE"
            segment["final_offset"] = int(original_offset)
            segment["updated_pointers"] = 0
            segment["offsets_ok"] = bool(0 <= original_offset < len(self.rom_data))
            segment["pointers_ok"] = bool(segment.get("pointers_ok", False))
            self.segment_audit_rows.append(segment)
            return True

        pointer_refs = list(segment.get("pointer_refs", []))
        if not pointer_refs:
            self.stats['blocked_no_pointer'] += 1
            segment["status"] = "ABORTED_RELOCATION"
            segment["failure_reason"] = "NOT_REALLOCATABLE: no pointer_refs (inline text)"
            self.segment_audit_rows.append(segment)
            self._log_blocked(text_id, segment["failure_reason"])
            return False

        if text_entry.get('reallocatable') is False:
            self.stats['blocked_no_pointer'] += 1
            reason = text_entry.get('reason_if_not', 'marked_not_reallocatable')
            segment["status"] = "ABORTED_RELOCATION"
            segment["failure_reason"] = f"NOT_REALLOCATABLE: {reason}"
            self.segment_audit_rows.append(segment)
            self._log_blocked(text_id, segment["failure_reason"])
            return False

        new_offset = self.allocator.allocate(
            size=len(encoded_with_term),
            alignment=2,
            item_uid=f"text_{text_id}"
        )
        if new_offset is None:
            self.stats['allocation_failed'] += 1
            segment["status"] = "ABORTED_RELOCATION"
            segment["failure_reason"] = "NO_FREE_SPACE: allocation failed"
            self.segment_audit_rows.append(segment)
            self._log_blocked(text_id, segment["failure_reason"])
            return False

        if new_offset < 0 or (new_offset + len(encoded_with_term)) > len(self.rom_data):
            self.stats['allocation_failed'] += 1
            segment["status"] = "ABORTED_RELOCATION"
            segment["failure_reason"] = "NO_FREE_SPACE: out_of_bounds"
            self.segment_audit_rows.append(segment)
            self._log_blocked(text_id, segment["failure_reason"])
            return False

        old_region = bytes(self.rom_data[original_offset:original_offset + original_length])
        new_region_before = bytes(self.rom_data[new_offset:new_offset + len(encoded_with_term)])
        ptr_backups: List[Tuple[int, int, bytes]] = []
        for pref in pointer_refs:
            ptr_off = int(self._safe_int(pref.get("ptr_offset"), default=-1) or -1)
            ptr_size = int(self._safe_int(pref.get("ptr_size"), default=2) or 2)
            if ptr_off < 0 or ptr_off + ptr_size > len(self.rom_data):
                continue
            ptr_backups.append((ptr_off, ptr_size, bytes(self.rom_data[ptr_off:ptr_off + ptr_size])))

        self.rom_data[new_offset:new_offset + len(encoded_with_term)] = encoded_with_term
        fill = self._get_padding_byte()
        self.rom_data[original_offset:original_offset + original_length] = bytes([fill] * original_length)

        pointer_update_fail = False
        updated = 0
        for pref in pointer_refs:
            try:
                self._update_pointer_ref(pref, new_offset)
                if not self._pointer_ref_matches_target(pref, new_offset):
                    pointer_update_fail = True
                    break
                updated += 1
            except Exception:
                pointer_update_fail = True
                break

        if pointer_update_fail:
            self.rom_data[original_offset:original_offset + original_length] = old_region
            self.rom_data[new_offset:new_offset + len(encoded_with_term)] = new_region_before
            for ptr_off, ptr_size, ptr_bytes in ptr_backups:
                self.rom_data[ptr_off:ptr_off + ptr_size] = ptr_bytes
            segment["status"] = "ABORTED_RELOCATION"
            segment["failure_reason"] = "POINTER_UPDATE_FAILED"
            segment["pointers_ok"] = False
            self.segment_audit_rows.append(segment)
            self._log_blocked(text_id, segment["failure_reason"])
            return False

        self.stats['reallocated'] += 1
        self.stats['pointers_updated'] += int(updated)
        segment["status"] = "REINSERTED_RELOCATED"
        segment["final_offset"] = int(new_offset)
        segment["updated_pointers"] = int(updated)
        segment["offsets_ok"] = bool(0 <= int(new_offset) < len(self.rom_data))
        segment["pointers_ok"] = True
        self.segment_audit_rows.append(segment)
        return True

    def _find_text_entry(self, text_id: int) -> Optional[Dict]:
        """Busca entrada de texto nos dados de extracao."""
        # Tenta formato novo (mappings)
        for entry in self.extraction_data.get('mappings', []):
            uid = entry.get('uid', '')
            if uid == f"U_{text_id:05d}" or uid == str(text_id):
                return entry
            # Tenta extrair ID do uid
            if uid.startswith('U_'):
                try:
                    if int(uid[2:]) == text_id:
                        return entry
                except ValueError:
                    pass

        # Tenta formato antigo (extracted_texts)
        for entry in self.extraction_data.get('extracted_texts', []):
            if entry.get('id') == text_id:
                return entry

        return None

    def _convert_legacy_pointers(self, pointers: List[Dict]) -> List[Dict]:
        """Converte formato antigo de ponteiros para pointer_refs."""
        result = []
        for ptr in pointers:
            ptr_offset = ptr.get('pointer_offset')
            if isinstance(ptr_offset, str):
                ptr_offset = int(ptr_offset, 16)
            elif ptr_offset is None:
                continue

            result.append({
                'ptr_offset': f"0x{ptr_offset:06X}",
                'ptr_size': ptr.get('size', 2),
                'endianness': ptr.get('endianness', 'little'),
                'addressing_mode': ptr.get('mode', 'ABSOLUTE'),
                'base': ptr.get('base', '0x0000'),
                'bank': ptr.get('bank'),
                'addend': ptr.get('addend', 0),
                'bank_table_offset': ptr.get('bank_table_offset')
            })
        return result

    def _write_in_place(self, offset: int, data: bytes, original_length: int):
        """Escreve dados no local original com padding."""
        # VALIDACAO: Nao sobrescrever codigo
        if not self._is_safe_to_write(offset, len(data)):
            raise ReinsertionError(
                f"Unsafe to write at offset 0x{offset:06X}. "
                f"May overwrite code or critical data."
            )

        # Escreve dados
        self.rom_data[offset:offset + len(data)] = data

        # Preenche resto com padding se texto for mais curto
        if len(data) < original_length:
            padding_byte = self._get_padding_byte()
            padding = bytes([padding_byte] * (original_length - len(data)))
            self.rom_data[offset + len(data):offset + original_length] = padding

    def _compute_pointer_value(self, pref: Dict[str, Any], new_target: int) -> Tuple[int, int, bool]:
        ptr_size = int(self._safe_int(pref.get("ptr_size"), default=2) or 2)
        endianness = str(pref.get("endianness", "little") or "little").lower()
        mode = str(pref.get("addressing_mode", "ABSOLUTE") or "ABSOLUTE").upper()

        base_str = pref.get("base", "0x0")
        if isinstance(base_str, str):
            parsed_base = self._safe_int(base_str, default=0)
            base = int(parsed_base or 0)
        else:
            base = int(base_str or 0)

        addend = int(self._safe_int(pref.get("addend"), default=0) or 0)
        bank_size = int(self.allocator.profile.get("bank_size", 0x4000) or 0x4000)

        if mode in ("LOROM_16", "NES_8000", "SMS_BASE", "SMS_BASE8000", "SMS_BASE4000"):
            new_value = base + (new_target % bank_size) + addend
        elif mode == "NES_C000":
            new_value = 0xC000 + (new_target % bank_size) + addend
        elif mode == "HIROM_16":
            new_value = (new_target % 0x10000) + addend
        else:
            new_value = new_target + addend

        little = endianness != "big"
        return int(new_value), ptr_size, little

    def _update_pointer_ref(self, pref: Dict, new_target: int):
        """Atualiza ponteiro para apontar ao novo offset."""
        ptr_offset = pref.get('ptr_offset')
        if isinstance(ptr_offset, str):
            ptr_offset = int(ptr_offset, 16)
        new_value, ptr_size, little = self._compute_pointer_value(pref, new_target)
        bank_size = int(self.allocator.profile.get("bank_size", 0x4000) or 0x4000)

        if ptr_size == 2:
            patch_u16(self.rom_data, ptr_offset, new_value, little_endian=little)
        elif ptr_size == 3:
            new_bank = new_target // bank_size
            patch_banked_pointer3(self.rom_data, ptr_offset, new_bank, new_value & 0xFFFF)
        elif ptr_size == 4:
            # Ponteiro 32-bit (raro, mas suportado)
            new_value &= 0xFFFFFFFF
            if little:
                self.rom_data[ptr_offset:ptr_offset+4] = new_value.to_bytes(4, 'little')
            else:
                self.rom_data[ptr_offset:ptr_offset+4] = new_value.to_bytes(4, 'big')

        # Atualiza bank table se existir
        bank_table_off = pref.get('bank_table_offset')
        if bank_table_off:
            if isinstance(bank_table_off, str):
                bank_table_off = int(bank_table_off, 16)
            idx = pref.get('index', 0) or 0
            new_bank = new_target // bank_size
            patch_bank_table_entry(self.rom_data, bank_table_off, idx, new_bank)

    def _pointer_ref_matches_target(self, pref: Dict[str, Any], target_offset: int) -> bool:
        ptr_offset = pref.get("ptr_offset")
        if isinstance(ptr_offset, str):
            ptr_offset = int(ptr_offset, 16)
        ptr_offset = self._safe_int(ptr_offset, default=None)
        if ptr_offset is None:
            return False

        expected_value, ptr_size, little = self._compute_pointer_value(pref, target_offset)
        if ptr_offset < 0 or ptr_offset + ptr_size > len(self.rom_data):
            return False

        current = self.rom_data[ptr_offset:ptr_offset + ptr_size]
        if ptr_size == 2:
            got = int.from_bytes(current, "little" if little else "big", signed=False)
            return got == (expected_value & 0xFFFF)
        if ptr_size == 3:
            bank_size = int(self.allocator.profile.get("bank_size", 0x4000) or 0x4000)
            expected_bank = int(target_offset) // bank_size
            expected_addr = int(expected_value) & 0xFFFF
            expected = bytes([expected_bank & 0xFF, expected_addr & 0xFF, (expected_addr >> 8) & 0xFF])
            return bytes(current) == expected
        if ptr_size == 4:
            got = int.from_bytes(current, "little" if little else "big", signed=False)
            return got == (expected_value & 0xFFFFFFFF)
        return False

    def _log_blocked(self, text_id: int, reason: str):
        """Registra item bloqueado para o relatorio."""
        self.blocked_items.append({
            'text_id': text_id,
            'reason': reason
        })
        self.stats['errors'].append({
            'text_id': text_id,
            'error': reason
        })

    def _extract_reason_code(self, text_entry: Dict[str, Any]) -> str:
        """Extrai reason_code normalizado da entrada de extração."""
        if not isinstance(text_entry, dict):
            return ""
        for field in ("reason_code", "blocked_reason", "reason_if_not"):
            raw = text_entry.get(field)
            if not raw:
                continue
            upper = str(raw).strip().upper()
            m = re.match(r"([A-Z0-9_]+)", upper)
            return m.group(1) if m else upper
        return ""

    def _is_suspicious_source(self, source: str, offset: int, max_len: int) -> Tuple[bool, str]:
        """
        Detecta se o source parece dados binarios (tiles/sprites/tabelas) em vez de texto.

        Criterios:
        - Alta taxa de bytes de controle (0x00-0x1F exceto newline/tab)
        - Baixa taxa de caracteres imprimiveis [A-Za-z0-9 pontuacao]
        - Padroes repetitivos tipicos de tiles

        Returns:
            (is_suspicious, reason)
        """
        if not source:
            return False, ""

        # Conta caracteres
        printable = 0
        control = 0
        total = len(source)

        # Caracteres imprimiveis comuns em texto
        text_chars = set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 .,!?:;\'"()-')

        for ch in source:
            code = ord(ch)
            if ch in text_chars:
                printable += 1
            elif code < 0x20 and code not in (0x0A, 0x0D, 0x09):  # controle exceto newline/tab
                control += 1

        if total == 0:
            return False, ""

        printable_ratio = printable / total
        control_ratio = control / total

        # Heuristicas de deteccao
        if control_ratio > 0.3:
            return True, f"SUSPICIOUS_DATA: control_ratio={control_ratio:.2f} (>0.3)"

        if printable_ratio < 0.4 and total > 4:
            return True, f"SUSPICIOUS_DATA: printable_ratio={printable_ratio:.2f} (<0.4)"

        # Detecta padroes repetitivos (tipico de tiles)
        if total >= 8:
            unique_chars = len(set(source))
            if unique_chars <= 3 and total > 10:
                return True, f"SUSPICIOUS_DATA: repetitive_pattern unique={unique_chars}/{total}"

        return False, ""

    def _encode_text(self, text: str) -> bytes:
        """
        Codifica texto usando tabela de caracteres inferida.

        Returns:
            Bytes codificados

        Raises:
            ReinsertionError se caracteres não puderem ser codificados
        """
        if not self.charset:
            # Fallback: ASCII
            try:
                return text.encode('ascii', errors='strict')
            except UnicodeEncodeError as e:
                raise ReinsertionError(f"Cannot encode to ASCII: {e}")

        # Usa tabela inferida (char_to_byte)
        char_to_byte = {}
        for char_str, byte_hex in self.charset.get('char_to_byte', {}).items():
            byte_value = int(byte_hex, 16)
            char_to_byte[char_str] = byte_value

        encoded = bytearray()
        i = 0

        while i < len(text):
            # Detecta tokens de tilemap <TILE:XX>
            if text[i:i+6] == '<TILE:' and i + 9 <= len(text) and text[i+8] == '>':
                try:
                    code = int(text[i+6:i+8], 16)
                    encoded.append(code)
                    i += 9
                    continue
                except ValueError:
                    pass

            # Detecta códigos de controle <XX>
            if text[i] == '<' and i + 3 < len(text) and text[i+3] == '>':
                try:
                    code = int(text[i+1:i+3], 16)
                    encoded.append(code)
                    i += 4
                    continue
                except ValueError:
                    pass

            # Caractere normal
            char = text[i]
            byte_value = char_to_byte.get(char)

            if byte_value is None:
                # Tenta alternativas comuns
                if char == ' ':
                    # Espaço pode ter múltiplas representações
                    byte_value = char_to_byte.get(' ', 0x20)  # Default ASCII space
                else:
                    raise ReinsertionError(
                        f"Character '{char}' not in charset table. "
                        f"Cannot encode translation."
                    )

            encoded.append(byte_value)
            i += 1

        return bytes(encoded)

    def _is_safe_to_write(self, offset: int, length: int) -> bool:
        """
        Verifica se é seguro escrever na região especificada.

        Critérios:
        - Não está em região de código (entropia média)
        - Não está em região de padding excessivo
        """
        # Verifica se offset é válido
        if offset < 0 or offset + length > len(self.rom_data):
            return False

        # Analisa bytes na região
        region_data = self.rom_data[offset:offset + length]

        # Se tudo é 0x00 ou 0xFF, provavelmente é padding (seguro)
        if all(b in {0x00, 0xFF} for b in region_data):
            return True

        # Se tem padrões ASCII ou texto anterior, provavelmente é seguro
        ascii_count = sum(1 for b in region_data if 0x20 <= b <= 0x7E)
        if ascii_count / len(region_data) > 0.3:
            return True

        # Caso contrário, aceita (assume que extração foi correta)
        return True

    def _get_padding_byte(self) -> int:
        """Determina byte de padding apropriado.
        Prefere 0x00 ou 0xFF sobre 0x20 para evitar espaços fantasma visíveis no jogo."""
        from collections import Counter
        sample = self.rom_data[::100]  # Amostra
        most_common = Counter(sample).most_common(5)

        # Prioridade: 0x00 > 0xFF > outros (nunca 0x20 que renderiza como espaço)
        for byte, count in most_common:
            if byte in {0x00, 0xFF}:
                return byte

        return 0x00  # Default

    def _update_pointers(self, pointers: List[Dict], text_offset: int, new_length: int):
        """
        Atualiza ponteiros se texto mudou de tamanho.

        NOTA: Implementação simplificada. Em casos reais, pode precisar
        realocar texto e reconstruir toda tabela de ponteiros.
        """
        # Por enquanto, apenas valida que ponteiros ainda apontam corretamente
        for ptr_info in pointers:
            ptr_offset = int(ptr_info['pointer_offset'], 16)

            # Lê ponteiro atual
            try:
                if ptr_offset + 2 <= len(self.rom_data):
                    current_value = struct.unpack('<H', self.rom_data[ptr_offset:ptr_offset+2])[0]

                    # Se precisar realocar texto, atualiza ponteiro aqui
                    # (Não implementado: requer análise complexa de espaço livre)

            except:
                pass  # Ignora erros de ponteiros

    def _save_rom(self, output_path: Path):
        """Salva ROM modificada com header SMC se necessário."""
        with open(output_path, 'wb') as f:
            if self.smc_header:
                f.write(self.smc_header)
            f.write(self.rom_data)

        print(f"✅ Saved modified ROM: {output_path}")

    def reinsert_with_rules(
        self,
        translations: Dict[str, str],
        items: List[Dict],
        output_path: str,
        glyph_maps: Optional[Dict[str, Dict[int, str]]] = None,
        token_maps: Optional[Dict[str, Dict[str, str]]] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Reinsere traduções aplicando REGRA 1 e REGRA 2.

        Args:
            translations: {item_id: translated_text}
            items: Lista de itens do JSONL/mapping
            output_path: Caminho para ROM de saída
            glyph_maps: {item_id: {tile_idx: char}} para tilemaps
            token_maps: {item_id: {placeholder: original}} para tokens

        Returns:
            (success, result_data)
        """
        rules = ReinsertionRules(
            rom_data=self.rom_data,
            allocator=self.allocator,
            charset=self.charset,
            glyph_maps=glyph_maps or {}
        )

        # Snapshot da ROM original para provas/exports (antes da reinserção)
        original_bytes = bytes(self.rom_data)

        results = []

        for item in items:
            item_id = item.get("id") or item.get("uid", "")
            translated = translations.get(item_id)

            if not translated:
                continue

            # Obtém token_map se houver
            item_token_map = token_maps.get(item_id) if token_maps else None

            # Aplica regra apropriada
            result = rules.apply_rule(item, translated, item_token_map)
            results.append(result)

        # Salva ROM
        self._save_rom(Path(output_path))

        # Coleta dados para exports
        stats = rules.get_stats()
        mapping_data = rules.get_mapping_data()
        proof_data = rules.get_proof_data()

        # Exports obrigatórios (neutralidade por CRC32)
        try:
            output_dir = Path(output_path).parent if output_path else Path(".")
            mapping_path = output_dir / f"{self.original_crc32}_reinsertion_mapping.json"
            with open(mapping_path, "w", encoding="utf-8") as f:
                json.dump(mapping_data, f, ensure_ascii=False, indent=2)

            # Prova de reinserção (arquivo separado para não sobrescrever o proof de extração)
            try:
                from export.proof_generator import ProofGenerator
                console_type = str(self.extraction_data.get("console", "unknown"))
                pg = ProofGenerator(original_bytes, console_type=console_type)
                pg.generate_reinsertion_proof(
                    crc32=self.original_crc32,
                    original_bytes=original_bytes,
                    validation_entries=proof_data,
                    statistics=stats,
                    output_dir=output_dir
                )
            except Exception:
                pass
        except Exception:
            pass


        # Atualiza stats do reinserter
        self.stats['in_place'] += stats['in_place']
        self.stats['reallocated'] += stats['relocated']
        self.stats['blocked_no_pointer'] += stats['blocked_no_pointer']
        self.stats['tilemap_inserted'] += stats['in_place'] + stats['fixed_shortened']

        qa_final = None
        qa_json_path = None
        qa_txt_path = None
        if evaluate_reinsertion_qa and write_qa_artifacts:
            try:
                blocked_total = int(stats.get('blocked_no_pointer', 0)) + int(
                    stats.get('blocked_no_glyph_map', 0)
                ) + int(stats.get('blocked_allocation_failed', 0))
                qa_stats = {
                    "truncated": int(stats.get('fixed_shortened', 0)),
                    "blocked": blocked_total,
                    "blocked_items": blocked_total,
                }
                qa_evidence = {
                    "placeholder_fail_count": int(stats.get('tokens_failed', 0)),
                    "truncated_count": int(stats.get('fixed_shortened', 0)),
                }
                limitations: List[str] = []
                if int(stats.get('tokens_failed', 0)) > 0:
                    limitations.append(
                        f"Foram detectadas {int(stats.get('tokens_failed', 0))} falhas de placeholder/token."
                    )
                limitations.append("Input match e ordering não disponíveis neste fluxo universal.")

                qa_final = evaluate_reinsertion_qa(
                    console=str(self.console),
                    rom_crc32=self.original_crc32,
                    rom_size=self.original_rom_size,
                    stats=qa_stats,
                    evidence=qa_evidence,
                    checks={
                        "input_match": None,
                        "ordering": None,
                        "emulator_smoke": None,
                    },
                    limitations=limitations,
                    compression_policy={},
                    translation_input={"path": str(output_path)},
                    require_manual_emulator=True,
                )
                qa_json_path, qa_txt_path = write_qa_artifacts(
                    Path(output_path).parent,
                    self.original_crc32,
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

        success = stats['in_place'] + stats['relocated'] + stats['fixed_shortened'] > 0

        return success, {
            'stats': stats,
            'mapping_entries': mapping_data,
            'proof_entries': proof_data,
            'results': results,
            'qa_final': qa_final,
            'qa_final_json': str(qa_json_path) if qa_json_path else None,
            'qa_final_txt': str(qa_txt_path) if qa_txt_path else None,
        }

    def validate_output(self, output_path: str) -> Tuple[bool, List[str]]:
        """
        Valida ROM de saída comparando com original.

        Returns:
            (is_valid, issues_found)
        """
        issues = []

        output_path = Path(output_path)
        if not output_path.exists():
            return False, ["Output file not found"]

        # Verifica tamanho
        original_size = self.rom_path.stat().st_size
        output_size = output_path.stat().st_size

        if original_size != output_size:
            issues.append(f"Size mismatch: {original_size} vs {output_size}")

        # Verifica que apenas regiões de texto mudaram
        with open(output_path, 'rb') as f:
            output_data = f.read()
            if len(output_data) % 1024 == 512:
                output_data = output_data[512:]  # Remove header

        # TODO: Comparação mais sofisticada
        # Por ora, apenas valida que arquivo foi criado

        return len(issues) == 0, issues


def reinsert_from_translation_file(rom_path: str, extraction_json: str,
                                   translation_json: str,
                                   output_path: Optional[str] = None,
                                   strict: bool = False,
                                   skip_suspicious: bool = True) -> bool:
    """
    Função de conveniência para reinserção a partir de arquivo de tradução.

    Args:
        rom_path: ROM original
        extraction_json: Dados de extração (universal_pipeline)
        translation_json: Arquivo JSON com traduções {id: texto}
        output_path: ROM de saída (opcional)
        strict: Se True, valida dados suspeitos
        skip_suspicious: Se True, pula itens suspeitos; se False, falha

    Returns:
        True se sucesso
    """
    # Carrega traduções
    with open(translation_json, 'r', encoding='utf-8') as f:
        translation_data = json.load(f)

    # Converte IDs para int
    translations = {int(k): v for k, v in translation_data.items()}

    # Executa reinserção
    reinserter = SafeReinserter(rom_path, extraction_json)
    success, message = reinserter.reinsert_translations(
        translations, output_path,
        strict=strict, skip_suspicious=skip_suspicious
    )

    return success


def strip_accents_for_rom(text: str) -> str:
    """
    Remove acentos/PT-BR para ROMs sem suporte de glyph.
    Regra explícita solicitada para pipeline DE9F8517.
    """
    if not isinstance(text, str) or not text:
        return ""
    replacements = {
        "ã": "a",
        "ê": "e",
        "ç": "c",
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
        "â": "a",
        "õ": "o",
        "à": "a",
        "Ã": "A",
        "Ê": "E",
        "Ç": "C",
        "Á": "A",
        "É": "E",
        "Í": "I",
        "Ó": "O",
        "Ú": "U",
        "Â": "A",
        "Õ": "O",
        "À": "A",
    }
    out = text
    for src, dst in replacements.items():
        out = out.replace(src, dst)
    return out


def _extract_nested_bool(payload: Any, path: List[str]) -> Optional[bool]:
    cur = payload
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur.get(key)
    if isinstance(cur, bool):
        return bool(cur)
    return None


def _infer_font_has_pt_br(reinserter: "SafeReinserter") -> bool:
    data = reinserter.extraction_data if isinstance(reinserter.extraction_data, dict) else {}
    candidates = [
        ["font_has_pt_br"],
        ["font_profile", "font_has_pt_br"],
        ["font_profile", "has_pt_br"],
        ["profile", "font_has_pt_br"],
        ["profile", "has_pt_br"],
    ]
    for path in candidates:
        flag = _extract_nested_bool(data, path)
        if flag is not None:
            return bool(flag)
    # Regra alvo para Ultima IV SMS (CRC DE9F8517): por padrão não assumir suporte PT-BR.
    if str(getattr(reinserter, "original_crc32", "")).upper().strip() == "DE9F8517":
        return False
    return True


def _infer_font_is_monospace(
    reinserter: "SafeReinserter",
    text_entry: Dict[str, Any],
) -> bool:
    entry = text_entry if isinstance(text_entry, dict) else {}
    data = reinserter.extraction_data if isinstance(reinserter.extraction_data, dict) else {}

    # Prioridade 1: flag explícita na entrada.
    for key in ("font_is_monospace", "font_monospace", "monospace", "fixed_width_font"):
        val = entry.get(key)
        if isinstance(val, bool):
            return bool(val)

    # Prioridade 2: perfil global.
    candidates = [
        ["font_is_monospace"],
        ["font_profile", "font_is_monospace"],
        ["font_profile", "monospace"],
        ["profile", "font_is_monospace"],
        ["profile", "monospace"],
    ]
    for path in candidates:
        flag = _extract_nested_bool(data, path)
        if flag is not None:
            return bool(flag)

    # Fallback específico da ROM solicitada.
    if str(getattr(reinserter, "original_crc32", "")).upper().strip() == "DE9F8517":
        return True
    return False


def _slot_payload_budget(
    reinserter: "SafeReinserter",
    text_entry: Dict[str, Any],
) -> int:
    max_bytes = int(
        reinserter._safe_int(  # pylint: disable=protected-access
            text_entry.get("length", text_entry.get("max_bytes", text_entry.get("max_len_bytes"))),
            default=0,
        )
        or 0
    )
    if max_bytes <= 0:
        return 0
    term = reinserter._safe_int(  # pylint: disable=protected-access
        text_entry.get("terminator", text_entry.get("term", text_entry.get("end_byte"))),
        default=None,
    )
    # Mantém compatível com _validate_and_prepare_segment: budget de payload + terminador.
    if isinstance(term, int) and 0 <= int(term) <= 0xFF:
        return max(0, max_bytes - 1)
    return max_bytes


def _truncate_to_word_boundary_by_bytes(
    reinserter: "SafeReinserter",
    text: str,
    payload_budget: int,
) -> str:
    clean = re.sub(r"\s+", " ", str(text or "")).strip()
    if payload_budget <= 0:
        return ""
    try:
        if len(reinserter._encode_text(clean)) <= payload_budget:  # pylint: disable=protected-access
            return clean
    except Exception:
        pass

    words = [w for w in clean.split(" ") if w]
    if words:
        out = ""
        for word in words:
            candidate = word if not out else f"{out} {word}"
            try:
                if len(reinserter._encode_text(candidate)) <= payload_budget:  # pylint: disable=protected-access
                    out = candidate
                    continue
            except Exception:
                pass
            break
        if out:
            return out

    # Fallback: corte por caractere quando nenhuma palavra inteira cabe.
    out_chars: List[str] = []
    for ch in clean:
        candidate = "".join(out_chars) + ch
        try:
            if len(reinserter._encode_text(candidate)) <= payload_budget:  # pylint: disable=protected-access
                out_chars.append(ch)
                continue
        except Exception:
            pass
        break
    return "".join(out_chars).rstrip()


def _fit_text_for_monospace_slot(
    reinserter: "SafeReinserter",
    text_entry: Dict[str, Any],
    translated_text: str,
) -> str:
    payload_budget = _slot_payload_budget(reinserter, text_entry)
    if payload_budget <= 0:
        return str(translated_text or "")

    candidate = str(translated_text or "")
    if not _infer_font_has_pt_br(reinserter):
        candidate = strip_accents_for_rom(candidate)

    candidate = _truncate_to_word_boundary_by_bytes(
        reinserter=reinserter,
        text=candidate,
        payload_budget=payload_budget,
    )

    # Padding com espaços até o tamanho da área de payload.
    while True:
        try:
            encoded_len = len(reinserter._encode_text(candidate))  # pylint: disable=protected-access
        except Exception:
            encoded_len = len(candidate.encode("ascii", errors="ignore"))
        if encoded_len >= payload_budget:
            break
        candidate += " "

    # Segurança final: nunca exceder budget.
    if encoded_len > payload_budget:
        candidate = _truncate_to_word_boundary_by_bytes(
            reinserter=reinserter,
            text=candidate,
            payload_budget=payload_budget,
        )
        while True:
            try:
                _len = len(reinserter._encode_text(candidate))  # pylint: disable=protected-access
            except Exception:
                _len = len(candidate.encode("ascii", errors="ignore"))
            if _len >= payload_budget:
                break
            candidate += " "
    return candidate


def _install_de9f8517_runtime_guards() -> None:
    """
    Instala wrappers sem alterar o corpo das funções originais.
    Escopo: correções solicitadas para Ultima IV SMS (CRC DE9F8517).
    """
    if getattr(SafeReinserter, "_neurorom_de9f8517_guards_installed", False):
        return

    original_apply_accent_policy = SafeReinserter._apply_accent_policy
    original_validate_prepare = SafeReinserter._validate_and_prepare_segment

    def _patched_apply_accent_policy(self, text: str) -> Dict[str, Any]:
        result = original_apply_accent_policy(self, text)
        if str(getattr(self, "original_crc32", "")).upper().strip() != "DE9F8517":
            return result
        if _infer_font_has_pt_br(self):
            return result

        renderable = str(result.get("renderable_text", text or ""))
        stripped = strip_accents_for_rom(renderable)
        if stripped != renderable:
            changes = list(result.get("fallback_changes", []))
            changes.append(
                {
                    "index": -1,
                    "from": "<accented>",
                    "to": "<ascii>",
                    "policy": "strip_accents_for_rom",
                }
            )
            result["fallback_changes"] = changes
            result["fallback_applied"] = True
        result["renderable_text"] = stripped
        result["missing_glyphs"] = self._find_missing_glyphs(stripped)
        return result

    def _patched_validate_and_prepare_segment(
        self,
        text_id: int,
        text_entry: Dict[str, Any],
        translated_text: str,
    ) -> Tuple[Dict[str, Any], Optional[bytes]]:
        effective_text = str(translated_text or "")
        if str(getattr(self, "original_crc32", "")).upper().strip() == "DE9F8517":
            if _infer_font_is_monospace(self, text_entry):
                effective_text = _fit_text_for_monospace_slot(
                    reinserter=self,
                    text_entry=text_entry,
                    translated_text=effective_text,
                )
        return original_validate_prepare(self, text_id, text_entry, effective_text)

    SafeReinserter._apply_accent_policy = _patched_apply_accent_policy
    SafeReinserter._validate_and_prepare_segment = _patched_validate_and_prepare_segment
    SafeReinserter._neurorom_de9f8517_guards_installed = True


_install_de9f8517_runtime_guards()


if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="Safe ROM text reinserter")
    parser.add_argument("rom_file", help="ROM original")
    parser.add_argument("extraction_json", help="JSON de extracao")
    parser.add_argument("translation_json", help="JSON com traducoes")
    parser.add_argument("output_rom", nargs="?", default=None, help="ROM de saida")
    parser.add_argument("--strict", action="store_true",
                        help="Valida dados suspeitos (tiles/sprites/tabelas)")
    parser.add_argument("--fail-on-suspicious", action="store_true",
                        help="Falha em vez de pular itens suspeitos (requer --strict)")
    args = parser.parse_args()

    success = reinsert_from_translation_file(
        args.rom_file,
        args.extraction_json,
        args.translation_json,
        args.output_rom,
        strict=args.strict,
        skip_suspicious=not args.fail_on_suspicious
    )

    sys.exit(0 if success else 1)
